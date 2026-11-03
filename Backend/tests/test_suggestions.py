"""Focused tests for the suggestions and review queue routes."""

from pathlib import Path

from fastapi.testclient import TestClient

from Backend.main import app
from Backend.store.database import Database


HEADERS = {
    "Authorization": "Bearer DEV_TOKEN",
    "X-Device-Id": "test-device",
}


def make_client(tmp_path: Path) -> TestClient:
    """Build a test client with an isolated SQLite database."""
    database = Database(tmp_path / "suggestions.sqlite3")
    database.initialize()
    app.state.database = database
    return TestClient(app)


def create_save(client: TestClient, url: str) -> dict:
    """Create one save and return its wire representation."""
    response = client.post("/saves", headers=HEADERS, json={"url": url})
    assert response.status_code == 201
    return response.json()["data"]


def test_review_queue_and_single_accept(tmp_path: Path) -> None:
    """Needs-review saves appear in review and a single accept files them."""
    with make_client(tmp_path) as client:
        save = create_save(client, "https://example.com/a")
        with app.state.database.transaction() as connection:
            connection.execute("UPDATE saves SET needs_review = 1 WHERE id = ?", (save["id"],))
        suggestions = client.get("/suggestions", headers=HEADERS)

        assert suggestions.status_code == 200
        assert suggestions.json()["data"]["review"][0]["id"] == save["id"]

        accepted = client.post(
            "/suggestions/accept",
            headers=HEADERS,
            json={
                "type": "single",
                "save_id": save["id"],
                "path": "Cooking / Pasta",
                "confidence": 0.94,
                "accept": True,
            },
        )
        assert accepted.status_code == 200
        assert accepted.json()["data"]["name"] == "Pasta"
        filed = client.get(f"/saves/{save['id']}", headers=HEADERS)
        assert filed.json()["data"]["save"]["folder_id"] == accepted.json()["data"]["id"]


def test_cluster_accept_files_members_and_dismissal_sticks(tmp_path: Path) -> None:
    """Cluster proposals file members and dismissed clusters are not re-proposed."""
    with make_client(tmp_path) as client:
        first = create_save(client, "https://example.com/a")
        second = create_save(client, "https://example.com/b")
        third = create_save(client, "https://example.com/c")
        proposals = client.get("/suggestions", headers=HEADERS)
        cluster = proposals.json()["data"]["clusters"][0]
        members = [{"save_id": member["save_id"]} for member in cluster["cluster"]]

        dismissed = client.post(
            "/suggestions/accept",
            headers=HEADERS,
            json={
                "type": "cluster",
                "cluster": members,
                "path": "Cooking",
                "confidence": 0.8,
                "accept": False,
            },
        )
        assert dismissed.status_code == 422
        reproposed = client.get("/suggestions", headers=HEADERS)
        assert reproposed.json()["data"]["clusters"] == []

        accepted = client.post(
            "/suggestions/accept",
            headers=HEADERS,
            json={
                "type": "cluster",
                "cluster": [
                    {"save_id": first["id"]},
                    {"save_id": second["id"]},
                    {"save_id": third["id"]},
                ],
                "path": "Projects",
                "confidence": 0.9,
                "accept": True,
            },
        )
        assert accepted.status_code == 200
        for member_id in (first["id"], second["id"], third["id"]):
            member = client.get(f"/saves/{member_id}", headers=HEADERS)
            assert member.json()["data"]["save"]["folder_id"] == accepted.json()["data"]["id"]
