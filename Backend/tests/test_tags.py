"""Focused tests for the save tag replacement route."""

from pathlib import Path
from uuid import uuid4

from fastapi.testclient import TestClient

from Backend.main import app
from Backend.store.database import Database


HEADERS = {
    "Authorization": "Bearer DEV_TOKEN",
    "X-Device-Id": "test-device",
}


def make_client(tmp_path: Path) -> TestClient:
    """Build a test client with an isolated SQLite database."""
    database = Database(tmp_path / "tags.sqlite3")
    database.initialize()
    database.connection.execute(
        "INSERT INTO tags (id, name) VALUES (?, ?), (?, ?)",
        ("018f4c1a-0000-7de6-9c8e-000000000006", "recipe", "018f4c1a-0000-7de6-9c8e-000000000007", "sourdough"),
    )
    database.connection.commit()
    app.state.database = database
    return TestClient(app)


def test_replace_save_tags_updates_save_and_conflicts_on_stale_write(tmp_path: Path) -> None:
    """Tags replace as a whole set and stale writes return 409."""
    with make_client(tmp_path) as client:
        save = client.post("/saves", headers=HEADERS, json={"url": "https://example.com/a"}).json()["data"]
        tag_ids = ["018f4c1a-0000-7de6-9c8e-000000000006", "018f4c1a-0000-7de6-9c8e-000000000007"]
        replaced = client.put(
            f"/saves/{save['id']}/tags",
            headers=HEADERS,
            json={"tag_ids": tag_ids, "updated_at": save["updated_at"]},
        )

        assert replaced.status_code == 200
        assert replaced.json()["data"]["id"] == save["id"]

        unknown = client.put(
            f"/saves/{save['id']}/tags",
            headers=HEADERS,
            json={"tag_ids": [str(uuid4())], "updated_at": replaced.json()["data"]["updated_at"]},
        )
        assert unknown.status_code == 404
        assert unknown.json()["error"]["code"] == "not_found"

        conflict = client.put(
            f"/saves/{save['id']}/tags",
            headers=HEADERS,
            json={"tag_ids": tag_ids, "updated_at": save["updated_at"]},
        )
        assert conflict.status_code == 409
        assert conflict.json()["error"]["code"] == "conflict"
