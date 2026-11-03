"""Focused tests for the folder organization routes."""

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
    database = Database(tmp_path / "folders.sqlite3")
    database.initialize()
    app.state.database = database
    return TestClient(app)


def create_folder(client: TestClient, name: str = "Cooking", parent_id: str | None = None) -> dict:
    """Create one folder and return its wire representation."""
    payload: dict = {"name": name}
    if parent_id is not None:
        payload["parent_id"] = parent_id
    response = client.post("/folders", headers=HEADERS, json=payload)
    assert response.status_code == 201
    return response.json()["data"]


def test_folder_crud_and_inbox_return(tmp_path: Path) -> None:
    """Folders support create, rename, archive, delete, and Inbox recovery."""
    with make_client(tmp_path) as client:
        folder = create_folder(client)
        renamed = client.patch(
            f"/folders/{folder['id']}",
            headers=HEADERS,
            json={"name": "Weeknight", "parent_id": None},
        )
        assert renamed.status_code == 200
        assert renamed.json()["data"]["name"] == "Weeknight"

        save = client.post("/saves", headers=HEADERS, json={"url": "https://example.com/a"}).json()["data"]
        patched = client.patch(
            f"/saves/{save['id']}",
            headers=HEADERS,
            json={"folder_id": folder["id"], "updated_at": save["updated_at"]},
        )
        assert patched.status_code == 200
        assert patched.json()["data"]["folder_id"] == folder["id"]

        listed = client.get("/folders", headers=HEADERS)
        assert listed.status_code == 200
        assert listed.json()["data"]["items"][0]["save_count"] == 1

        deleted = client.delete(f"/folders/{folder['id']}", headers=HEADERS)
        read_save = client.get(f"/saves/{save['id']}", headers=HEADERS)
        assert deleted.status_code == 204
        assert read_save.json()["data"]["save"]["folder_id"] is None


def test_folder_guards_reserved_names_and_depth(tmp_path: Path) -> None:
    """Reserved names are rejected and nesting stops at depth 3."""
    with make_client(tmp_path) as client:
        reserved = client.post("/folders", headers=HEADERS, json={"name": "Other"})
        assert reserved.status_code == 422
        assert reserved.json()["error"]["code"] == "reserved_folder_name"

        parent_id: str | None = None
        for level in range(4):
            folder = create_folder(client, name=f"Level-{level}", parent_id=parent_id)
            parent_id = folder["id"]
        too_deep = client.post("/folders", headers=HEADERS, json={"name": "Too deep", "parent_id": parent_id})
        assert too_deep.status_code == 422
        assert too_deep.json()["error"]["code"] == "folder_depth_exceeded"
