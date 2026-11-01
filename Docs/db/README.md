# Claybank — Database Schemas

**Status:** Locked (post-Phase 0 grilling, 2026-10-31) · SQLite on **both** sides.
**Companion:** `DataModel.md` (entity/invariant language) · `../api/schemas/*.json` (wire shapes) · `../adr/0004` (no media), `../adr/0005` (markdown truth), `../adr/0008` (index_meta)

Files:

| File | Applies to | Contents |
|---|---|---|
| `0001_core.sql` | **Server AND device** | saves, folders, tags, notes, jobs, suggestions, FTS5, vector recovery, views |
| `0002_server.sql` | Server only | users, idempotency keys, `changes` log (pull cursor), capture audit |
| `0003_device.sql` | Device only | `sync_state`, `device_queue` (offline replay), `settings` (Chat model toggle etc.) |

Apply order: `0001` then the side's file. Both stores run the **same 0001**, which is what makes "complete replica" true and lets the sync code diff on identical column names.

## Why both sides are SQLite

The stack decision locked SQLite + FTS5 + a local vector index (`Architecture.md` §3). Postgres is a real later option but is a deployment concern and explicitly not a hackathon one; nothing in this schema uses SQLite-only extensions outside FTS5, so the swap-lite path stays open.

## The guard rails live in the schema itself

- `folders.depth ≤ 3` enforced by triggers (`folder_depth_exceeded`), not by faith.
- Reserved names (`Other`, `Misc`, `Unsorted`, `Inbox`) rejected by a CHECK — the Inbox is a state, never a folder row.
- `saves.kind` CHECK ∈ `video | article | unknown` — one enum, mirrored from `api/schemas/save.json`.
- A canonicalized `url` unique index is the duplicate capture (`already_saved`) key.
- `suggested_folder` one-per-save enforced as paired `path`/`confidence` columns with a CHECK that they come together.
- `notes` rows cascade-delete with their save; suggestion rows cascade; `agent_trace` stays on the job and out of the sync payload.
- A save that deletes takes its note, job, tags, vector and FTS rows with it — zero orphan text.
- `save_vectors` is the rebuildable recovery store next to the faiss index file; `index_meta` pins `model_id`/`dim` and the app refuses to search on mismatch (ADR 0008).

These invariants pair with a test the same way `Docs/api/test_contract.py` pairs with the JSON Schemas:

`test_schema.py` (stdlib `sqlite3` only, no deps) builds **both DB variants in memory**, applies the migrations, and asserts the invariants: depth cap, reserved names, kind enum (cross-checked against `api/schemas/save.json`), unique tags (case-insensitively), cascade deletes, `changes`-log cursor (server), queue-key uniqueness (device), FTS rows following notes, and the `settings.chat_model` enum. Run from the repo root:

```
python Docs/db/test_schema.py
```

A red `test_schema.py` means a code↔schema divergence — the phase isn't done until it's green (`Rules.md` §7).
