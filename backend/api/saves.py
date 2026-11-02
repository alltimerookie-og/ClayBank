"""Saves router — capture + reads (Phase 1 scope; pipeline enqueued, not awaited)."""
from __future__ import annotations

import asyncio
import logging

from fastapi import APIRouter, Header, Query, Request

from backend.api.envelope import err, ok
from backend.capture.service import CaptureError, capture_save, save_to_contract
from backend.contracts.ids import now_iso_z
from backend.processing.notes import execute_note_persistence_transaction

log = logging.getLogger(__name__)
router = APIRouter(tags=["saves"])


def _key(value: str | None) -> str | None:
    v = (value or "").strip()
    return v or None


@router.post("/saves")
async def post_saves(request: Request,
                     idempotency_key: str | None = Header(default=None,
                                                         alias="Idempotency-Key")):
    try:
        body = await request.json()
    except Exception:
        return err("validation", "Body must be JSON", None, 422)
    if not isinstance(body, dict):
        return err("validation", "Body must be an object", None, 422)

    def _tx(conn):
        return capture_save(
            conn,
            url=body.get("url", ""),
            source_app=body.get("source_app"),
            user_context=body.get("user_context"),
            suggested_folder_id=body.get("suggested_folder_id"),
            force=bool(body.get("force", False)),
            idempotency_key=_key(idempotency_key),
            device_id=getattr(request.state, "device_id", "unknown"),
            user_id=getattr(request.state, "user_id", "seed"),
        )

    try:
        result = await request.app.state.store.run_tx(_tx)
    except CaptureError as exc:
        return err(exc.code, exc.message, exc.detail, exc.status)
    status = 200 if result["replayed"] else 201
    if status == 201 and hasattr(request.app.state, "pipeline") and request.app.state.pipeline is not None:
        asyncio.create_task(request.app.state.pipeline.process_save(result["save"]["id"]))
    return ok(save_to_contract(result["save"]), status=status)


@router.get("/saves")
async def list_saves(request: Request, cursor: str | None = None,
                     folder_id: str | None = None, inbox: bool | None = None,
                     needs_review: bool | None = None, kind: str | None = None,
                     limit: int = 20):
    limit = max(1, min(limit if limit is not None else 20, 100))
    where = []
    params: list = []
    if inbox:
        where.append("folder_id IS NULL")
    elif folder_id:
        where.append("folder_id = ?")
        params.append(folder_id)
    if needs_review is not None:
        where.append("needs_review = ?")
        params.append(1 if needs_review else 0)
    if kind:
        where.append("kind = ?")
        params.append(kind)
    if cursor:
        where.append("captured_at < ?")
        params.append(cursor)
    clause = (" WHERE " + " AND ".join(where)) if where else ""
    rows = await request.app.state.store.fetchall(
        f"SELECT * FROM saves{clause} ORDER BY captured_at DESC, id DESC LIMIT ?",
        tuple(params) + (limit + 1,))
    items = [save_to_contract(r) for r in rows[:limit]]
    next_cursor = items[-1]["captured_at"] if len(rows) > limit and items else None
    return ok({"items": items, "cursor": next_cursor})


@router.get("/saves/{save_id}")
async def read_save(request: Request, save_id: str):
    store = request.app.state.store
    row = await store.fetchone("SELECT * FROM saves WHERE id=?", (save_id,))
    if row is None:
        return err("not_found", "Unknown id", None, 404)
    note = await store.fetchone("SELECT * FROM notes WHERE save_id=?", (save_id,))
    job = await store.fetchone("SELECT * FROM jobs WHERE save_id=?", (save_id,))
    return ok({"save": save_to_contract(row), "note": _note(note), "job": _job(job)})


@router.put("/saves/{save_id}/note")
async def put_save_note(request: Request, save_id: str):
    store = request.app.state.store

    # 1. Verify parent save exists
    save = await store.fetchone("SELECT * FROM saves WHERE id=?", (save_id,))
    if save is None:
        return err("not_found", "Save not found", None, 404)

    # 2. Parse request JSON body
    try:
        body = await request.json()
    except Exception:
        return err("validation", "Body must be JSON", None, 422)
    if not isinstance(body, dict):
        return err("validation", "Body must be an object", None, 422)

    markdown = body.get("markdown")
    client_updated_at = body.get("updated_at")

    if not isinstance(markdown, str) or not markdown.strip():
        return err("validation", "Field 'markdown' must be a non-empty string", None, 422)
    if not isinstance(client_updated_at, str) or not client_updated_at.strip():
        return err("validation", "Field 'updated_at' must be a valid ISO datetime string", None, 422)

    # 3. Optimistic concurrency control (409 Conflict)
    existing_note = await store.fetchone("SELECT * FROM notes WHERE save_id=?", (save_id,))
    if existing_note is not None and existing_note.get("updated_at"):
        server_updated_at = existing_note["updated_at"]
        if client_updated_at < server_updated_at:
            return err(
                "conflict",
                "Note has been modified on server since your last fetch",
                {"server_updated_at": server_updated_at, "client_updated_at": client_updated_at},
                409,
            )

    # 4. Atomic write-through and section index rebuild
    now = now_iso_z()

    def _tx(conn):
        execute_note_persistence_transaction(
            conn=conn,
            save_id=save_id,
            markdown=markdown,
            now=now,
        )
        conn.execute(
            "INSERT INTO changes(entity, entity_id, op, at) VALUES ('note', ?, 'put', ?)",
            (save_id, now),
        )

    await store.run_tx(_tx)

    # 5. Return updated note according to Docs/api/schemas/note.json
    updated_row = await store.fetchone("SELECT * FROM notes WHERE save_id=?", (save_id,))
    return ok(_note(updated_row))


@router.post("/saves/{save_id}/reprocess")
async def reprocess_save(request: Request, save_id: str, from_: str | None = Query(default="extracting", alias="from")):
    store = request.app.state.store
    save = await store.fetchone("SELECT * FROM saves WHERE id=?", (save_id,))
    if save is None:
        return err("not_found", "Save not found", None, 404)

    valid_stages = ("extracting", "transcribing", "analyzing", "sorting")
    stage = (from_ or "extracting").lower()
    if stage not in valid_stages:
        return err("validation", f"Invalid 'from' stage: must be one of {list(valid_stages)}", None, 422)

    now = now_iso_z()
    await store.execute(
        "UPDATE jobs SET state='queued', error=NULL, updated_at=? WHERE save_id=?",
        (now, save_id),
    )

    if hasattr(request.app.state, "pipeline") and request.app.state.pipeline is not None:
        asyncio.create_task(request.app.state.pipeline.process_save(save_id, from_stage=stage))

    return ok({"save_id": save_id, "state": "queued", "from": stage}, status=202)


def _note(row: dict | None) -> dict | None:
    if row is None:
        return None
    import json

    def _j(v, default):
        try:
            return json.loads(v) if v else default
        except Exception:
            return default
    return {
        "save_id": row["save_id"],
        "markdown": row["markdown"],
        "frontmatter": {
            "source": row.get("source"),
            "channel": row.get("channel"),
            "video_url": row.get("video_url"),
            "duration": row.get("duration"),
            "published": row.get("published"),
            "saved": row.get("saved_date"),
            "folder": row.get("folder_path"),
            "tags": _j(row.get("tags_json"), []),
        },
        "overview": row.get("overview"),
        "key_points": _j(row.get("key_points_json"), None),
        "links": _j(row.get("links_json"), None),
        "transcript": row.get("transcript"),
        "created_at": row.get("created_at"),
        "updated_at": row.get("updated_at"),
    }


def _job(row: dict | None) -> dict | None:
    if row is None:
        return None
    import json

    def _j(v):
        try:
            return json.loads(v) if v else []
        except Exception:
            return []
    timing = None
    try:
        timing = json.loads(row["timing_json"]) if row.get("timing_json") else None
    except Exception:
        timing = None
    trace = None
    try:
        trace = json.loads(row["agent_trace"]) if row.get("agent_trace") else None
    except Exception:
        trace = None
    return {
        "save_id": row["save_id"],
        "state": row["state"],
        "tier": row["tier"],
        "skipped": _j(row.get("skipped_json")),
        "failed": _j(row.get("failed_json")),
        "error": row.get("error"),
        "agent_trace": trace,
        "timing": timing,
        "created_at": row.get("created_at"),
        "updated_at": row.get("updated_at"),
    }
