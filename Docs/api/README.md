# Claybank API contract

This directory is the **single source of truth** for every field name and enum in the Claybank backend. `openapi.yaml` describes the paths; `schemas/*.json` describes every request and response body. Code and other docs reference them — they never duplicate them.

```
Docs/api/
├── openapi.yaml            ← 13 paths, OpenAPI 3.1; every body is a $ref into schemas/
├── schemas/                ← 22 JSON Schemas (draft 2020-12), one per named shape
├── fixtures/               ← 23 generated example/counter-example files — build output, never hand-edited
├── generate_fixtures.py    ← the single authored source of example payloads
├── test_contract.py        ← validates schemas, fixtures, and grilling-locked guard rails
└── README.md               ← this file
```

## Conventions (enforced by schemas + contract test)

| Convention | Rule |
|---|---|
| IDs | UUIDv7 strings |
| Timestamps | ISO-8601 UTC with `Z` suffix |
| Success envelope | `{"data": …}` |
| Error envelope | `{"error": {"code", "message", "detail"}}` |
| Pagination | opaque `cursor` (query param on list requests, field on page responses) |
| Idempotency | writes accept `Idempotency-Key` header; capture also uses the canonicalized URL as a duplicate key |
| Contract version | `x-contract-version: 0` in `openapi.yaml`; clients send `contract_version` mismatch → `409 contract_version_mismatch` |
| Enums | defined once, in `schemas/*.json` only |

Success:

```json
{ "data": { … } }
```

Error:

```json
{ "error": { "code": "conflict", "message": "Stale write", "detail": { "expected_updated_at": "…" } } }
```

## Paths (13)

| Method | Path | Request body | Response body (`data`) | Notes |
|---|---|---|---|---|
| POST | `/saves` | `save-capture` | `save` | Capture. Kind is `unknown` until extraction. Duplicate canonicalized URL → `409 already_saved` (with existing id) unless `force=true`. Body never makes a network call. |
| GET | `/saves` | — | `save-page` | Cursor list. Filters: `folder_id`, `inbox`, `needs_review`, `kind`. |
| GET | `/saves/{save_id}` | — | `{save, note, job}` | One save with its note metadata and processing job. |
| PATCH | `/saves/{save_id}` | `save-patch` | `save` | Mutable fields only: folder, tags, user_context. |
| PUT | `/saves/{save_id}/note` | `note-put` | `note` | Markdown is source of truth; indexes rebuild from it. |
| POST | `/saves/{save_id}/reprocess` | — | `job` | Metadata & transcript only — the note body is never touched. |
| DELETE | `/saves/{save_id}` | — | `204` | Delete save + note. Undo on the device replays capture under the same `Idempotency-Key`. |
| GET | `/folders` | — | `folder-page` | Depth ≤ 3; one folder per save; `parent_id: null` = top level. |
| POST | `/folders` | `folder-write` | `folder` | Reserved names `Other`/`Misc` rejected; depth ≤ 3. |
| PATCH | `/folders/{folder_id}` | `folder-write` | `folder` | Rename / move / archive; rename is a bulk frontmatter rewrite. |
| DELETE | `/folders/{folder_id}` | — | `204` | Delete folder; member saves return to the Inbox. |
| PUT | `/saves/{save_id}/tags` | `tags-put` | `tag[]` | Flat tags, case-insensitively unique. |
| GET | `/suggestions` | — | `suggestion` (page) | Cluster-then-propose after ~3 similar saves. |
| POST | `/suggestions/accept` | `suggestion-accept` | `folder` | **The only** endpoint that creates a system folder. |
| GET | `/search` | `search-request` as query parameters | `search-page` | Hybrid FTS5 + faiss; every result explains itself. |
| POST | `/ask` | `ask-request` | `ask-answer` | Cites the saves it used — citations are mandatory. |
| GET | `/sync/pull` | — | `sync-pull` | Complete device replica since a cursor. |
| POST | `/sync/push` | `sync-push` | per-op results | Replays queued offline writes, each op carrying its own `idempotency_key`. |

## Schemas (22)

**Entities** (the canonical shapes)

- `save` — id, url (canonicalized), platform (server-derived from host, never user-supplied), source_app, captured_at, user_context, kind (`video` | `article` | `unknown`), needs_review
- `note` — save_id, markdown (full document: YAML frontmatter + body), frontmatter (stable facts only — no suggested folder / confidence / processing state; those live on save/job)
- `job` — save_id, state (`queued → extracting → transcribing → analyzing → sorting → ready`, linear for display; per-stage `skipped`/`failed` flags travel separately so stages can skip or fail independently), tier (1; 2 = agent rescue, post-hackathon), error
- `folder` — id (null in create requests), parent_id, name, save_count (computed, never a stale counter)
- `tag` — id, name, save_count
- `suggestion` — type (`single` | `cluster`), save_id or cluster[], path (`"Cooking / Pasta"`), confidence 0–1, dismissed_at
- `extraction-result` — tier-1/tier-2 shared shape; missing fields degrade to `unknown`, never partial writes

**Pages** (cursor-paginated lists — `{items: <shape>[]`, `cursor}`, wrapped by the envelope as `{"data": {…}}`)

- `save-page`, `folder-page`, `search-page`

**Requests** (writes)

- `save-capture` — url required; source_app, user_context, suggested_folder_id (one-tap chip), force
- `save-patch` — folder/tags/user_context only
- `note-put` — the full markdown replacement (PUT semantics, not a diff)
- `tags-put` — whole tag set replacement for one save
- `folder-write` — create + patch in one shape (id null = create)
- `suggestion-accept` — accept or dismiss a proposal
- `search-request` — query, scope (folder or everything), filters
- `ask-request` — question + folder scope

**Reads & sync**

- `search-result` — save + match_reason (`title | transcript | body | tag | folder | semantic`) + fragment (matched phrase) + jump_target (`0:42` timestamp or heading anchor) + score. Results explain themselves.
- `ask-answer` — answer text + **mandatory citations** to saves
- `sync-push` — op list (`save_create`, `save_patch`, `note_put`, `folder_create`, `folder_patch`, `tags_put`, `suggestion_accept`), payload shaped like the referenced request schema, plus `device_cursor`
- `sync-pull` — saves, notes, folders, jobs, tombstoned ids, next cursor
- `error` — 13 locked codes (below)

## Error codes

| Code | Meaning |
|---|---|
| `already_saved` | Duplicate canonicalized URL; detail carries the existing id |
| `conflict` | Stale device write (409 + conflict banner pattern) |
| `not_found` | Unknown id |
| `validation` | Body failed its schema |
| `contract_version_mismatch` | Client/server `contract_version` differ |
| `folder_depth_exceeded` | Depth > 3 |
| `reserved_folder_name` | `Other` / `Misc` |
| `extraction_failed` | Tier-1 failed and no fallback |
| `transcription_failed` | ASR failed (cloud and fallback) |
| `asr_unavailable` | No ASR path reachable right now |
| `llm_unavailable` | Note generation / chat backend down |
| `index_mismatch` | Search index out of step with stores |
| `unauthorized` | Bad `DEV_TOKEN` / `X-Device-Id` |

## Fixtures — generated, never hand-edited

Every example payload is authored **once**, inside `generate_fixtures.py`, and written to `fixtures/<schema-name>.fixtures.json` (each file holds one or more cases: valid examples plus intentional counter-examples). `test_contract.py` then validates:

1. every schema parses as draft 2020-12;
2. every fixture case conforms to the schema it name-matches;
3. the grilling-locked guard rails hold — `kind` enum is exactly the locked set; citations are mandatory in Ask answers; reserved folder names are rejected; domain/env searches always include a local `engine`.

Change workflow for any contract change:

```bash
# from the repo root
python Docs/api/generate_fixtures.py    # regenerate fixtures from the edited script
python Docs/api/test_contract.py        # must be green (requires jsonschema>=4.21)
```

Never edit `fixtures/*.json` in place and never add an enum or field name outside `schemas/*.json` — `test_contract.py` is also usable as plain pytest (`pytest Docs/api/test_contract.py`), and wire examples in `Docs/DataModel.md` §5.1 must be updated to stay consistent with any schema change.
