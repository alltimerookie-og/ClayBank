"""Focused tests for search and Ask routes."""

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
    database = Database(tmp_path / "search.sqlite3")
    database.initialize()
    app.state.database = database
    return TestClient(app)


def test_search_returns_match_reason_and_jump_target(tmp_path: Path) -> None:
    """FTS matches explain themselves with reason, fragment, and timestamp."""
    with make_client(tmp_path) as client:
        save = client.post("/saves", headers=HEADERS, json={"url": "https://example.com/garlic"}).json()["data"]
        markdown = "---\nsource: example\n---\n# Garlic\n\n## Transcript\n> 0:42 — add cream\n"
        client.put(
            f"/saves/{save['id']}/note",
            headers=HEADERS,
            json={"markdown": markdown, "updated_at": save["updated_at"]},
        )
        response = client.get("/search", params={"q": "cream"}, headers=HEADERS)

        assert response.status_code == 200
        result = response.json()["data"]["results"][0]
        assert result["save"]["id"] == save["id"]
        assert result["match_reason"] == "transcript"
        assert "cream" in (result["fragment"] or "").lower()
        assert result["jump_target"] == "0:42"


def test_ask_requires_citations_and_scope(tmp_path: Path) -> None:
    """Ask answers cite the saves used and echo the requested engine."""
    with make_client(tmp_path) as client:
        save = client.post("/saves", headers=HEADERS, json={"url": "https://example.com/a"}).json()["data"]
        markdown = "---\nsource: example\n---\n# Pasta\n\nCream sauce basics\n"
        client.put(
            f"/saves/{save['id']}/note",
            headers=HEADERS,
            json={"markdown": markdown, "updated_at": save["updated_at"]},
        )
        response = client.post(
            "/ask",
            headers=HEADERS,
            json={"question": "pasta", "save_scope": "library", "engine": "local"},
        )

        assert response.status_code == 200
        answer = response.json()["data"]
        assert answer["scope"] == "library"
        assert answer["engine"] == "local"
        assert answer["citations"]
        assert answer["citations"][0]["save_id"] == save["id"]


def test_search_refuses_index_mismatch(tmp_path: Path) -> None:
    """A mismatched embedding model blocks search."""
    with make_client(tmp_path) as client:
        with app.state.database.transaction() as connection:
            connection.execute(
                "UPDATE index_meta SET model_id = ?, dim = ?, version = ? WHERE id = 1",
                ("other-model", 128, 9),
            )
        response = client.get("/search", params={"q": "cream"}, headers=HEADERS)

        assert response.status_code == 409
        assert response.json()["error"]["code"] == "index_mismatch"
