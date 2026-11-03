# Claybank

> Share it now. Find it later. — A save-everything app: capture any link today, find any moment in it later.

**Status:** backend API complete and tested (§6.1–§6.6 + contract-version responses) · prototype v2 built and verified · Flet app not yet built.

A private internal decision log drives this repository: the published docs defer to it; the prototype v2 wins on look, the docs win on meaning.

**License:** `LICENSE` — GNU Affero General Public License v3.0 only (`AGPL-3.0-only`, SPDX identifier `AGPL-3.0-only`). Copyright 2026 Md. Shefayet Hossain ([@alltimerookie-og](https://github.com/alltimerookie-og) · <shefayet.dev@gmail.com>). Contributions are accepted under the same license; third-party components stay under their own upstream licenses (§Third-party Components + §Component Record).

## Map

```
ClayBank/
├── README.md                        ← this index
├── LICENSE                          ← AGPL-3.0-only; copyright 2026 Md. Shefayet Hossain (alltimerookie-og · shefayet.dev@gmail.com); contributions under the same license; third-party rules in §Third-party Components, per-component record in §Component Record
├── Instructions/                    ← per-role build instructions
│   ├── README.md                    ← index + orientation order
│   ├── ui-developer.md              ← Flet app role: fidelity to prototype v2 + honest states
│   └── backend-developer.md         ← FastAPI backend role: contract-first, capture never blocks
├── Docs/                            ← product, architecture, and contract
│   ├── PRD.md                       ← product requirements (what & why)
│   ├── Architecture.md              ← system layout: Flet app · FastAPI · SQLite/faiss
│   ├── DataModel.md                 ← entities, fields, invariants, wire examples
│   ├── Design.md                    ← UI tokens + organization UX (typed chips)
│   ├── UIUX.md                      ← pages → components → API calls → JSON bodies per screen
│   ├── Rules.md                     ← working rules for agents/humans touching this repo
│   ├── Phases.md                    ← ordered build plan (source of "next step")
│   ├── GLOSSARY.md                  ← one name per concept — use these words in code
│   ├── api/                         ← the contract (keep green before any contract change)
│   │   ├── README.md                ← paths, schemas, error codes, fixture workflow
│   │   ├── openapi.yaml             ← all paths, $ref into schemas/
│   │   ├── schemas/                 ← 23 JSON Schemas — the one enum source
│   │   ├── fixtures/                ← 23 files — generated ONLY by generate_fixtures.py, never hand-edited
│   │   ├── generate_fixtures.py
│   │   └── test_contract.py
│   └── db/                          ← SQLite layer behind the contract
│       ├── 0001_core.sql            ← shared (applies to both store variants)
│       ├── 0002_server.sql          ← server additions (idempotency, changes log, audit)
│       ├── 0003_device.sql          ← device additions (sync_state, queue, settings)
│       ├── README.md
│       └── test_schema.py
├── Backend/                         ← FastAPI service (single service, in-process workers)
│   ├── main.py                      ← app entrypoint + lifespan (optional CLAYBANK_WORKER loop)
│   ├── api/                         ← routes, one-to-one with OpenAPI tags
│   ├── capture/                     ← canonicalization, dedupe, idempotency, save intents
│   ├── processing/                  ← pipeline.py (extract→ready), orchestrator.py, worker.py
│   ├── extraction/                  ← ytdlp.py, trafilatura.py, rescue.py, result.py
│   ├── asr/                         ← multimodal-only transcription
│   ├── llm/                         ← OpenAI-compatible provider (Meta Model API first)
│   ├── search/                      ← FTS5 + faiss hybrid, RRF fusion, cited Ask
│   ├── sync/                        ← cursor pull + idempotent push replay
│   ├── store/                       ← sqlite/database.py, fts5.py, vectors.py, embeddings.py
│   ├── contracts/                   ← Pydantic models derived from Docs/api/schemas
│   ├── tests/                       ← focused suites (43 passed)
│   ├── seed_demo.py                 ← demo library seed + wipe (see Setup)
│   ├── models/                      ← embedding weights (gitignored; downloaded on first use)
│   └── data/                        ← dev SQLite + faiss index (gitignored; rebuilt from DDL)
├── scripts_live_e2e.py              ← opt-in live E2E (needs server on :8000; see Setup)
└── PrototypingFiles/                ← interactive HTML prototypes (open in a browser)
    ├── Claybank_ Interactive Workflow v2.html   ← UI TRUTH · 13-step tour of the current product
    ├── Claybank App Wireframes.html             ← 14-screen board with Flet widget annotations
    └── archive/
        └── Claybank_ Interactive Workflow.html  ← v1, read-only "before" (has since-decided-away
                                                    features: resume, 5 tabs, sign-in). Do not edit.
```

## Setup (local backend)

Prereqs: Python 3.12+, [uv](https://docs.astral.sh/uv/), Node.js (yt-dlp JS challenges), git.

```bash
git clone https://github.com/alltimerookie-og/ClayBank.git
cd ClayBank
uv sync --extra dev --extra vectors
copy .env.example .env
uv run fastapi dev Backend/main.py --port 8000
```

What happens automatically on first run:

- `Backend/data/claybank.sqlite3` is created from `Docs/db/*.sql` (dir is
  gitignored; schema comes from the repo).
- `Backend/models/multilingual-e5-small/` downloads on first embedding use
  (~500 MB: 448 MB `model.onnx` + 16 MB `tokenizer.json`; dir is gitignored).
- `faiss.index` rebuilds in-memory from the `save_vectors` table on search.

`.env` is gitignored. `DEV_TOKEN`/`X_DEVICE_ID` work as-is; cloud features
need `META_MODEL_API_KEY` (without it, Ask/extraction degrade to deterministic
local synthesis). Set `CLAYBANK_WORKER=true` before starting for the background
pipeline worker; otherwise run `POST /saves/{id}/reprocess?run=true` for
synchronous processing.

Demo library (for frontend integration and showcases):

```bash
uv run Backend/seed_demo.py --force        # fill empty DB: folders, saves, notes, tags, suggestions
uv run Backend/seed_demo.py --wipe         # remove demo rows, keep schema
```

Live end-to-end (needs the server on :8000):

```bash
uv run scripts_live_e2e.py
```

## Entry points

| I want to…                          | Read                                         |
| ----------------------------------- | -------------------------------------------- |
| Know why anything is the way it is  | internal decision log (private, not published in this repository) |
| Build the backend                   | `Docs/Architecture.md` + `Docs/api/`         |
| Build the app                       | `Docs/Architecture.md` + prototype v2        |
| Understand the data                 | `Docs/DataModel.md` + `Docs/db/`             |
| Change the UI                       | prototype v2 (screen truth) + `Docs/Design.md` |
| Know the working rules              | `Docs/Rules.md`                              |
| Know what comes next                | `Docs/Phases.md` |

## Keeping it green

From the repo root:

```bash
uv run pytest Backend/tests -q             # 43 passed: saves/folders/tags/suggestions/search/sync/extraction/vectors/pipeline/worker/cache/version
uv run python Docs/api/test_contract.py    # schemas valid, fixtures conform, guard rails hold
uv run python Docs/db/test_schema.py       # server + device DDL conform to DataModel.md invariants
```

Both must pass **before** shipping any contract-touching change, and fixtures are always regenerated via `python <path_to_repo>/Docs/api/generate_fixtures.py` — never hand-edited. The full working rules live in `Docs/Rules.md`.

## Current phases (see `Docs/Phases.md`)

1. Backend API complete: §6.1 saves, §6.2 folders, §6.3 tags, §6.4 suggestions/review,
   §6.5 search/Ask, §6.6 sync + contract-version responses, worker, extraction cache
2. Flet app shell with 4 tabs + the paste sheet; `POST /saves` always succeeds
3. Tier-1 extraction (yt-dlp / trafilatura) + job states streamed — done (transient media, multimodal-only)
4. Cloud note generation; transcript + note write-back — done (timestamped key points, Links section)
5. Local embeddings + FTS5 hybrid search with match reasons — done (faiss RRF, jump targets)
6. Folders/tags/suggestions + review queue — done
7. Folder-scoped Ask with citations — done (cloud/local engines)
