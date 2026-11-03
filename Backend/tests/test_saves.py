"""Focused tests for the implemented save capture route."""

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
    database = Database(tmp_path / "test.sqlite3")
    database.initialize()
    app.state.database = database
    return TestClient(app)


def test_capture_persists_canonical_save(tmp_path: Path) -> None:
    """Capture strips tracking parameters and returns a durable save."""
    with make_client(tmp_path) as client:
        response = client.post(
            "/saves",
            headers={**HEADERS, "Idempotency-Key": "capture-1"},
            json={
                "url": "https://www.youtube.com/shorts/abc123?utm_source=test",
                "source_app": " YouTube ",
            },
        )

        assert response.status_code == 201
        save = response.json()["data"]
        assert save["url"] == "https://www.youtube.com/watch?v=abc123"
        assert save["raw_url"].endswith("utm_source=test")
        assert save["platform"] == "youtube"
        assert save["source_app"] == "youtube"
        assert save["kind"] == "unknown"


def test_same_idempotency_key_replays_without_duplicate(tmp_path: Path) -> None:
    """A repeated write returns the original save and does not insert twice."""
    with make_client(tmp_path) as client:
        payload = {"url": "https://example.com/article?utm_campaign=x"}
        first = client.post(
            "/saves",
            headers={**HEADERS, "Idempotency-Key": "capture-2"},
            json=payload,
        )
        replay = client.post(
            "/saves",
            headers={**HEADERS, "Idempotency-Key": "capture-2"},
            json=payload,
        )

        assert first.status_code == 201
        assert replay.status_code == 200
        assert replay.json() == first.json()


def test_duplicate_url_returns_existing_id_unless_forced(tmp_path: Path) -> None:
    """Canonical duplicate URLs return 409, while force creates a second save."""
    with make_client(tmp_path) as client:
        first = client.post("/saves", headers=HEADERS, json={"url": "https://example.com/a"})
        duplicate = client.post(
            "/saves",
            headers=HEADERS,
            json={"url": "https://example.com/a?utm_source=share"},
        )
        forced = client.post(
            "/saves",
            headers=HEADERS,
            json={"url": "https://example.com/a", "force": True},
        )

        assert first.status_code == 201
        assert duplicate.status_code == 409
        assert duplicate.json()["error"]["code"] == "already_saved"
        assert duplicate.json()["error"]["detail"]["existing_id"] == first.json()["data"]["id"]
        assert forced.status_code == 201
        assert forced.json()["data"]["id"] != first.json()["data"]["id"]


def test_capture_requires_dev_authentication(tmp_path: Path) -> None:
    """The MVP bearer token and device identity are required."""
    with make_client(tmp_path) as client:
        response = client.post("/saves", json={"url": "https://example.com/a"})

        assert response.status_code == 401
        assert response.json()["error"]["code"] == "unauthorized"


def test_database_initialization_is_safe_to_repeat(tmp_path: Path) -> None:
    """Application reloads do not replay already-applied DDL."""
    database = Database(tmp_path / "reload.sqlite3")
    database.initialize()
    database.close()

    database.initialize()
    database.close()


def create_save(client: TestClient) -> dict:
    """Create one save and return its wire representation."""
    response = client.post("/saves", headers=HEADERS, json={"url": "https://example.com/item"})
    assert response.status_code == 201
    return response.json()["data"]


def test_save_read_list_patch_and_reprocess(tmp_path: Path) -> None:
    """The remaining mutable save operations use the contract envelopes."""
    with make_client(tmp_path) as client:
        save = create_save(client)
        read = client.get(f"/saves/{save['id']}", headers=HEADERS)
        listed = client.get("/saves?inbox=true", headers=HEADERS)
        patched = client.patch(
            f"/saves/{save['id']}",
            headers=HEADERS,
            json={"user_context": "keep this", "updated_at": save["updated_at"]},
        )
        conflict = client.patch(
            f"/saves/{save['id']}",
            headers=HEADERS,
            json={"user_context": "stale", "updated_at": save["updated_at"]},
        )
        reprocessed = client.post(
            f"/saves/{save['id']}/reprocess?from=transcribing",
            headers=HEADERS,
        )

        assert read.status_code == 200
        assert read.json()["data"]["job"]["state"] == "queued"
        assert listed.status_code == 200
        assert listed.json()["data"]["items"][0]["id"] == save["id"]
        assert patched.status_code == 200
        assert patched.json()["data"]["user_context"] == "keep this"
        assert conflict.status_code == 409
        assert conflict.json()["error"]["code"] == "conflict"
        assert reprocessed.status_code == 202
        assert reprocessed.json()["data"]["state"] == "transcribing"


def test_note_put_and_delete(tmp_path: Path) -> None:
    """Note replacement persists Markdown and delete cascades the save."""
    with make_client(tmp_path) as client:
        save = create_save(client)
        markdown = "---\nsource: example\nsaved: 2026-11-02\n---\n# Item\n"
        note = client.put(
            f"/saves/{save['id']}/note",
            headers=HEADERS,
            json={"markdown": markdown, "updated_at": save["updated_at"]},
        )
        read = client.get(f"/saves/{save['id']}", headers=HEADERS)
        deleted = client.delete(f"/saves/{save['id']}", headers=HEADERS)
        missing = client.get(f"/saves/{save['id']}", headers=HEADERS)

        assert note.status_code == 200
        assert note.json()["data"]["markdown"] == markdown
        assert note.json()["data"]["frontmatter"]["source"] == "example"
        assert read.json()["data"]["note"]["save_id"] == save["id"]
        assert deleted.status_code == 204
        assert missing.status_code == 404
        assert missing.json()["error"]["code"] == "not_found"
