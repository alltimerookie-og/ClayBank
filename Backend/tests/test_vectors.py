"""Focused tests for real faiss vector indexing."""

from pathlib import Path

from fastapi.testclient import TestClient

from Backend.main import app
from Backend.store.database import Database
from Backend.store.vectors import VectorIndex


HEADERS = {
    "Authorization": "Bearer DEV_TOKEN",
    "X-Device-Id": "test-device",
}


def make_client(tmp_path: Path) -> TestClient:
    """Build a test client with an isolated SQLite database."""
    database = Database(tmp_path / "vectors.sqlite3")
    database.initialize()
    app.state.database = database
    return TestClient(app)


def test_vector_indexing_and_semantic_search(tmp_path: Path) -> None:
    """Real embeddings persist recovery vectors and return cosine matches."""
    with make_client(tmp_path) as client:
        save = client.post("/saves", headers=HEADERS, json={"url": "https://example.com/garlic"}).json()["data"]
        markdown = "---\nsource: example\n---\n# Garlic\n\nCream sauce with garlic and pasta.\n"
        client.put(
            f"/saves/{save['id']}/note",
            headers=HEADERS,
            json={"markdown": markdown, "updated_at": save["updated_at"]},
        )
        index = VectorIndex(app.state.database, root=tmp_path)
        count = index.rebuild()
        results = index.query("garlic cream pasta")

        assert count >= 1
        assert any(save_id == save["id"] for save_id, _ in results)
        response = client.get("/search", params={"q": "garlic"}, headers=HEADERS)
        assert response.status_code == 200
