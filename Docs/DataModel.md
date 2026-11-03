# Claybank — Data Model

**Status:** Locked (post-Phase 0 grilling, 2026-10-31)
**Companion:** `GLOSSARY.md` (terms) · `api/openapi.yaml` + `api/schemas/*.json` (wire shape) · `Architecture.md` (how it moves)
**Context:** one SQLite schema (`Docs/db/0001_core.sql`) serves the server (authoritative; server-only additions in `0002_server.sql`) and the device (complete replica; device-only additions in `0003_device.sql` — offline queue, sync cursors, local settings). SQLite stores FTS5 full-text rows (`notes_fts`, trigger-maintained); a faiss flat index (384-dim) sits next to the DB with `save_vectors` as the rebuildable recovery store; `index_meta` pins the embedding model. Guard rails (depth cap, reserved names, kind enum, duplicate-URL key, suggestion pairing, case-insensitive tag uniqueness) are **enforced by the schema itself**, not by caller discipline — `Docs/db/test_schema.py` proves both variants green.

## 1. Conventions

- IDs: **UUIDv7 strings**; times: **ISO-8601 UTC `Z`**; wire envelope: `{data, error:{code, message, detail}}`; pagination: cursors; `contract_version` on every response.
- **One enum source:** JSON Schemas in `api/schemas/` — code types are generated/checked against them, never duplicated.
- Soft-delete is not used; deletion is hard for notes, with an undo action client-side, not a tombstone.

## 2. Entities

### 2.1 `saves`
| Field | Type | Notes |
|---|---|---|
| `id` | UUIDv7 | |
| `url` | text | canonicalized capture-time (tracking stripped, `/shorts/x` ↔ `watch?v=x`) |
| `raw_url` | text | as captured, for provenance/audits |
| `platform` | text | derived from host (server-computed) |
| `source_app` | text | client-sent sharing app (`Instagram`) — never inferred |
| `user_context` | text | save-time note, optional |
| `kind` | enum | `video | article | unknown` — pipeline selector, never an organizing axis |
| `has_audio / has_timeline / has_images` | bool | capability flags; optional fields, never required |
| `duration` | int·sec | nullable |
| `title` | text | from extraction or agent fallback |
| `needs_review` | bool | derived: suggestion below threshold / conflict |
| `folder_id` | UUID·null | nullable → **Inbox-as-state**; zero or one folder per save |
| `captured_at` | time | |
| `captured_by_device` | text | id only, for provenance |
| `created_at / updated_at` | time | |
| `suggested_folder` | json | `{path, confidence}` — metadata only, never frontmatter |

### 2.2 `folders`
| Field | Type | Notes |
|---|---|---|
| `id` | UUIDv7 | |
| `parent_id` | UUID·null | nesting; depth ≤ 3 enforced at API |
| `name` | text | unique among siblings |
| `created_at / updated_at` | time | |
| `archived_at` | time·null | finished projects ironed over time |

No color, no icon, no cover representation at MVP (post-hackathon). No `cover_collage` requirement at schema level — collage tints come from item gradients (g1–g4) as a rendering choice.

### 2.3 `tags` + `save_tags`
| Field | Type | Notes |
|---|---|---|
| `id` | UUIDv7 | |
| `name` | text | unique, case-insensitive |

`save_tags`: `(save_id, tag_id)` many-to-many. Tags are flat labels; no hierarchy, no per-tag metadata at MVP.

### 2.4 `notes`
| Field | Type | Notes |
|---|---|---|
| `save_id` | UUIDv7 | 1:1 with save |
| `markdown` | text | **source of truth**; frontmatter facts only |
| `frontmatter` | json | parsed stable facts (see §3.1) |
| `overview` | text | LLM-guaranteed summary |
| `key_points` | json | list, LLM-guaranteed |
| `links` | json | links mentioned, with anchor text |
| `transcript` | text·null | text only; **audio/video never persisted** |
| `created_at / updated_at` | time | |

**Note structure (ADR 0005):** frontmatter + `# Title` + `## Overview` + `## Key points` (guaranteed) + dynamic sections (Steps, Links mentioned, Transcript excerpt, Related — optional). The user may **delete any section**; the parser tolerates missing sections; the section index (§4) is rebuilt on write.

### 2.5 `jobs`
| Field | Type | Notes |
|---|---|---|
| `save_id` | UUIDv7 | 1:1 |
| `state` | enum | `queued → extracting → transcribing → analyzing → sorting → ready` + per-stage `failed`/`skipped` flags |
| `tier` | enum | `1 | 2` (tier 2 post-hackathon) |
| `agent_trace` | json·null | tier 2 only; stored here, **excluded from sync** |
| `error` | text·null | last failed stage error |
| `timing` | json | per-stage durations; budget 30 s target / 2 min cap |

Processing states are job‑local, never rendered into note frontmatter.

### 2.6 `device_queue` (device only)
Offline writes awaiting sync: `op`, `payload`, `Idempotency-Key`, `attempts`, `created_at`.
Note edits are the primary producer: **user edits auto-save to the device replica and immediately enqueue a `note_put` op** — no user-visible save button. An edit is durable on device before any sync; `attempts` grows when the server is unreachable; a `409` replay leaves both versions available to the conflict/recovery UI.

### 2.7 `index_meta` (both sides)
Pinned embedding model: `{model_id, dim, version}`. Search **refuses mismatch** rather than silently mixing incompatible vectors. Changing the model forces an explicit re-index.

## 3. Invariants (API-enforced)

1. **Capture is durable and immediate** — `POST /saves` succeeds without network calls; extraction is downstream.
2. **Zero or one folder per save; depth ≤ 3.** No multi-parent.
3. **No auto-created folders.** A folder exists only via user action or an accepted cluster proposal (`POST /suggestions/accept`).
4. **`kind` never surfaces as an organizing axis** — loaders/pipeline read it; list/card UI never groups or labels by it.
5. **Metadata only in API layer:** `suggested_folder`, confidence, processing state, `needs_review` are job/pipeline state, never frontmatter.
6. **Track changes by explicit action:** note-body writes and folder changes are frontmatter rewrites; renames are **bulk frontmatter rewrites** (ADR 0005).
7. **Text only** — no BLOB columns that could hold audio/video; transcript is text.
8. **`agent_trace` excluded from sync** payloads.

## 4. Indexes & derived structures

- **FTS5 row per note:** title, overview, key points, transcript, tags, folder name — powers keyword results + the **match reason** (which of these hit) + jump target (timestamp/heading) on results.
- **Section index (write-time parse):** heading → char anchor map, enabling "match in transcript at 0:42" precision in results.
- **Vector index (faiss):** per-note embedding of title+overview+key points+transcript excerpt with e5 `passage:` prefix; queries use `query:` prefix. 384-dim, flat, rebuilt-from-DB on device.
- **Confidence/threshold config** is repository config, not a per-user field at MVP.

## 5. Contract alignment

Wire-facing schemas live in `Docs/api/schemas/` — **entities** (responses):
`save.json`, `note.json`, `folder.json`, `tag.json`, `job.json`, `extraction-result.json`, `search-result.json`, `ask-answer.json`, `suggestion.json`, `error.json`
— pages (cursor envelopes): `save-page.json`, `folder-page.json`, `search-page.json`
— **requests** (write bodies + queries): `save-capture.json`, `save-patch.json`, `note-put.json`, `tags-put.json`, `folder-write.json`, `suggestion-accept.json`, `search-request.json`, `ask-request.json`, `sync-push.json`, `sync-pull.json`

Fixtures in `api/fixtures/` are **generated from `generate_fixtures.py`** (the single authored source; never hand-edit fixtures) and validated by `test_contract.py`, which also checks guard rails (locked enums, mandatory citations, reserved folder names identical in both folder schemas, `note-put.markdown` required, `force=false` default on capture). Adding a field: update schema → regenerate fixtures → contract test green → implement.

### 5.1 Wire examples (summary)
```jsonc
// POST /saves → 201
{ "data": { "id": "018f3a…", "url": "https://example.com/reel", "platform": "instagram",
            "source_app": "instagram", "captured_at": "2026-10-31T12:00:00Z",
            "user_context": "", "kind": "unknown" } }

// 409 duplicate
{ "error": { "code": "already_saved",
             "message": "This link is already in your library.",
             "detail": { "existing_id": "018f3b…" } } }

// GET /search → results always explain themselves
{ "data": { "results": [ { "save": {…}, "match_reason": "transcript",
                          "fragment": "add cream at the end", "jump_target": "0:42",
                          "score": 0.81 } ] }, "cursor": "…" }

// Ask answer — citations mandatory
{ "data": { "answer": "MD", "citations": [ { "save_id": "018f…", "anchor": "0:42" } ] } }
```

## 6. Migration notes

- Schema changes go through versioned SQL migrations; the sync cursor version must survive them.
- `index_meta` mismatch after a schema-version bump → device rebuilds its index from its replica; no partial upgrade paths.
