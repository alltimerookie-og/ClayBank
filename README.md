# Claybank

> Share it now. Find it later. — A save-everything app: capture any link today, find any moment in it later.

**Status:** planning complete and mutually consistent · prototype v2 built and verified · **no application code yet.**

`Docs/Memory.md` is the ground truth (decision log). Everything below defers to it; the prototype v2 wins on look, the docs win on meaning.

## Map

```
ClayBank/
├── README.md                        ← this index
├── Docs/                            ← product, architecture, and contract
│   ├── Memory.md                    ← GROUND TRUTH · decision log + doc inventory + next steps
│   ├── PRD.md                       ← product requirements (what & why)
│   ├── Architecture.md              ← system layout: Flet app · FastAPI · SQLite/faiss
│   ├── DataModel.md                 ← entities, fields, invariants, wire examples
│   ├── Design.md                    ← UI tokens + organization UX (typed chips)
│   ├── UIUX.md                      ← pages → components → API calls → JSON bodies per screen
│   ├── Rules.md                     ← working rules for agents/humans touching this repo
│   ├── Phases.md                    ← ordered build plan (source of "next step")
│   ├── GLOSSARY.md                  ← one name per concept — use these words in code
│   ├── adr/                         ← decision records, numbered, immutable unless a decision changes
│   │   ├── 0001-flet-over-flutter.md
│   │   ├── 0002-tiered-extraction.md
│   │   ├── 0003-content-acquisition-legality.md
│   │   ├── 0004-never-persist-media.md
│   │   ├── 0005-markdown-as-source-of-truth.md
│   │   ├── 0006-no-auth-for-hackathon.md
│   │   ├── 0007-extraction-library-comparison.md
│   │   └── 0008-on-device-inference-cpu-only.md
│   ├── api/                         ← the contract (keep green before any contract change)
│   │   ├── README.md                ← paths, schemas, error codes, fixture workflow
│   │   ├── openapi.yaml             ← all paths, $ref into schemas/
│   │   ├── schemas/                 ← 22 JSON Schemas — the one enum source
│   │   ├── fixtures/                ← 23 files — generated ONLY by generate_fixtures.py, never hand-edited
│   │   ├── generate_fixtures.py
│   │   └── test_contract.py
│   └── db/                          ← SQLite layer behind the contract
│       ├── 0001_core.sql            ← shared (applies to both store variants)
│       ├── 0002_server.sql          ← server additions (idempotency, changes log, audit)
│       ├── 0003_device.sql          ← device additions (sync_state, queue, settings)
│       ├── README.md
│       └── test_schema.py
└── PrototypingFiles/                ← interactive HTML prototypes (open in a browser)
    ├── Claybank_ Interactive Workflow v2.html   ← UI TRUTH · 13-step tour of the current product
    ├── Claybank App Wireframes.html             ← 14-screen board with Flet widget annotations
    └── archive/
        └── Claybank_ Interactive Workflow.html  ← v1, read-only "before" (has since-decided-away
                                                    features: resume, 5 tabs, sign-in). Do not edit.
```

## Entry points

| I want to…                          | Read                                         |
| ----------------------------------- | -------------------------------------------- |
| Know why anything is the way it is  | `Docs/Memory.md` → `Docs/adr/`               |
| Build the backend                   | `Docs/Architecture.md` + `Docs/api/`         |
| Build the app                       | `Docs/Architecture.md` + prototype v2        |
| Understand the data                 | `Docs/DataModel.md` + `Docs/db/`             |
| Change the UI                       | prototype v2 (screen truth) + `Docs/Design.md` |
| Know the working rules              | `Docs/Rules.md`                              |
| Know what comes next                | `Docs/Phases.md` (mirrored in `Docs/Memory.md`) |

## Keeping it green

From the repo root:

```bash
python Docs/api/test_contract.py   # schemas valid, fixtures conform, guard rails hold
python Docs/db/test_schema.py      # server + device DDL conform to DataModel.md invariants
```

Both must pass **before** shipping any contract-touching change, and fixtures are always regenerated via `python <path_to_repo>/Docs/api/generate_fixtures.py` — never hand-edited. The full working rules live in `Docs/Rules.md`.

## Current phases (see `Docs/Phases.md`)

1. Scaffold backend (FastAPI + SQLite) against `Docs/api/openapi.yaml`; contract test green
2. Flet app shell with 4 tabs + the paste sheet; `POST /saves` always succeeds
3. Tier-1 extraction (yt-dlp / trafilatura) + job states streamed
4. Cloud ASR + cloud note generation; transcript + note write-back
5. Local embeddings + FTS5 hybrid search with match reasons
6. Folders/tags/suggestions + review queue
7. Folder-scoped Ask with citations
