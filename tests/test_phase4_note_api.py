"""Tests for Phase 4 Cycle 4.4: Note API Endpoint PUT /saves/{id}/note (ADR 0005, note-put.json)."""
from __future__ import annotations

import json
from pathlib import Path
import pytest
from httpx import ASGITransport, AsyncClient

from backend.config import settings
from backend.contracts.ids import new_uuid7, now_iso_z
from backend.main import create_app
from backend.store.db import Store


@pytest.fixture
def api_client(tmp_path: Path):
    db_path = tmp_path / "test_api.db"
    store = Store(str(db_path))
    app = create_app(store)
    headers = {
        "Authorization": f"Bearer {settings.DEV_TOKEN}",
        "X-Device-Id": "test-device-42",
    }
    return app, store, headers


@pytest.mark.anyio
async def test_put_note_success(api_client) -> None:
    """Verify PUT /saves/{id}/note replaces note markdown, rebuilds section index, and updates FTS."""
    app, store, headers = api_client

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test", headers=headers) as client:
        # 1. Create a save
        post_resp = await client.post("/saves", json={"url": "https://example.com/note-api-test"})
        assert post_resp.status_code == 201
        save_id = post_resp.json()["data"]["id"]

        # Fetch current note to get updated_at
        get_resp = await client.get(f"/saves/{save_id}")
        assert get_resp.status_code == 200
        current_note = get_resp.json()["data"]["note"]
        client_updated_at = current_note["updated_at"]

        # 2. Put updated markdown note
        new_markdown = """---
source: web
channel: Expert Writer
video_url: null
duration: null
published: 2026-03-01T00:00:00Z
saved: 2026-03-02T00:00:00Z
folder: Articles/Tech
tags:
  - "architecture"
  - "python"
---
# Modern Cloud Architecture

## Overview
An updated comprehensive overview of cloud architectures written by user.

## Key points
- Modularity is essential
- Optimistic concurrency prevents overwrite clobbers

## Links mentioned
- [Architecture Ref](https://example.com/arch)
"""

        put_resp = await client.put(
            f"/saves/{save_id}/note",
            json={
                "markdown": new_markdown,
                "updated_at": client_updated_at,
            },
        )

        assert put_resp.status_code == 200
        data = put_resp.json()["data"]

        # 3. Verify returned payload matches note schema
        assert data["save_id"] == save_id
        assert data["markdown"] == new_markdown
        assert data["frontmatter"]["source"] == "web"
        assert data["frontmatter"]["channel"] == "Expert Writer"
        assert data["frontmatter"]["folder"] == "Articles/Tech"
        assert data["frontmatter"]["tags"] == ["architecture", "python"]
        assert data["updated_at"] > client_updated_at

        # 4. Verify sections indexed in database
        sections = await store.fetchall(
            "SELECT heading, anchor, seq FROM note_sections WHERE save_id=? ORDER BY seq ASC",
            (save_id,),
        )
        assert len(sections) == 4
        headings = [s["heading"] for s in sections]
        assert headings == [
            "Modern Cloud Architecture",
            "Overview",
            "Key points",
            "Links mentioned",
        ]

        # 5. Verify FTS index updated
        fts = await store.fetchall("SELECT save_id FROM notes_fts WHERE notes_fts MATCH 'concurrency'")
        assert len(fts) == 1
        assert fts[0]["save_id"] == save_id

        # 6. Verify changes table audited
        changes = await store.fetchall(
            "SELECT entity, entity_id, op FROM changes WHERE entity='note' AND entity_id=?",
            (save_id,),
        )
        assert len(changes) >= 1
        assert changes[-1]["op"] == "put"


@pytest.mark.anyio
async def test_put_note_optimistic_conflict_409(api_client) -> None:
    """Verify stale client updated_at returns 409 Conflict with server timestamp details."""
    app, store, headers = api_client

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test", headers=headers) as client:
        # Create a save
        post_resp = await client.post("/saves", json={"url": "https://example.com/conflict-test"})
        assert post_resp.status_code == 201
        save_id = post_resp.json()["data"]["id"]

        # Advance server timestamp in DB
        newer_server_time = "2026-03-02T15:00:00Z"
        await store.execute("UPDATE notes SET updated_at=? WHERE save_id=?", (newer_server_time, save_id))

        # Client submits older timestamp
        stale_client_time = "2026-03-02T10:00:00Z"
        put_resp = await client.put(
            f"/saves/{save_id}/note",
            json={
                "markdown": "# Stale Update\n\nContent",
                "updated_at": stale_client_time,
            },
        )

        assert put_resp.status_code == 409
        err_body = put_resp.json()
        assert err_body["error"]["code"] == "conflict"
        assert err_body["error"]["detail"]["server_updated_at"] == newer_server_time
        assert err_body["error"]["detail"]["client_updated_at"] == stale_client_time


@pytest.mark.anyio
async def test_put_note_validation_422(api_client) -> None:
    """Verify empty or missing fields trigger 422 validation error."""
    app, store, headers = api_client

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test", headers=headers) as client:
        post_resp = await client.post("/saves", json={"url": "https://example.com/validation-test"})
        save_id = post_resp.json()["data"]["id"]

        # Missing updated_at
        resp1 = await client.put(
            f"/saves/{save_id}/note",
            json={"markdown": "# Only markdown"},
        )
        assert resp1.status_code == 422
        assert resp1.json()["error"]["code"] == "validation"

        # Empty markdown
        resp2 = await client.put(
            f"/saves/{save_id}/note",
            json={"markdown": "   ", "updated_at": now_iso_z()},
        )
        assert resp2.status_code == 422
        assert resp2.json()["error"]["code"] == "validation"

        # Non-JSON body
        resp3 = await client.put(
            f"/saves/{save_id}/note",
            content="not-json",
            headers={**headers, "Content-Type": "application/json"},
        )
        assert resp3.status_code == 422


@pytest.mark.anyio
async def test_put_note_not_found_404(api_client) -> None:
    """Verify unknown save_id returns 404."""
    app, store, headers = api_client

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test", headers=headers) as client:
        random_id = new_uuid7()
        resp = await client.put(
            f"/saves/{random_id}/note",
            json={"markdown": "# Valid", "updated_at": now_iso_z()},
        )
        assert resp.status_code == 404
        assert resp.json()["error"]["code"] == "not_found"
