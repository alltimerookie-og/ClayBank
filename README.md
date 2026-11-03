# Claybank

> Share it now. Find it later. — A save-everything app: capture any link today, find any moment in it later.

**Status:** Frontend implemented (Phases 2 + 4 + 5 + 6 + 7 + 8-preview) · Contracts and schemas locked · Backend / native runtime pending. Phase 9 submission package in preparation.

`Docs/Memory.md` is the ground truth (decision log). Prototype v2 (`PrototypingFiles/Claybank_ Interactive Workflow v2.html`) wins on look; the docs win on meaning. Submission index: `Docs/SUBMISSION.md`.

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

## Quick Start

- **Setup:** `Docs/SETUP.md`
- **Manual testing:** `Docs/MANUAL_TESTING.md`
- **Automated tests:** `Docs/TEST_REPORT.md`
- **Limitations:** `Docs/LIMITATIONS.md`
- **Backend integration:** `Docs/MANUAL_TESTING.md#F` + `Docs/api/openapi.yaml`
- **Device-runtime boundary:** `Docs/MANUAL_TESTING.md#G` + `Docs/LIMITATIONS.md`

## Entry points

| I want to…                          | Read                                         |
| ----------------------------------- | -------------------------------------------- |
| Clone, install, and run locally     | `Docs/SETUP.md` → `Docs/MANUAL_TESTING.md`   |
| Manually test every screen          | `Docs/MANUAL_TESTING.md`                     |
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

## What is implemented (this repo is frontend-focused)

The Flet Python UI runs against fixtures/in-memory coordinators. There is no live backend or Android notification runtime yet.

- **Implemented (frontend, tested):** shell, paste sheet, Inbox, note editor, folders/tags/suggestions/review, Search+Ask UI, Settings+sync banners, notification preview — 52 test files, 374 tests.
- **Fixture/mock-backed:** capture, search, Ask, sync resolve from `Docs/api/fixtures/*.json` when no backend is attached (`app/app.py:_resolve_default_markdown`).
- **Backend-dependent (not yet implemented):** FastAPI routers, `POST /saves` canonicalization/dedupe, extraction, ASR, cloud note generation, FTS5+faiss, cursor sync, `DEV_TOKEN` middleware.
- **Device-runtime-dependent (preview only):** native notification delivery, `POST_NOTIFICATIONS`, OS share target, background clipboard reads (forbidden on Android 10+), GGUF inference.
- See `Docs/LIMITATIONS.md` for the full claims matrix.

## Installation and launch

```powershell
git clone --branch aqib https://github.com/alltimerookie-og/ClayBank.git
cd ClayBank
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -e .
pip install jsonschema>=4.21 referencing pytest
flet run
```

Full commands for Windows/macOS/Linux: `Docs/SETUP.md`. Step-by-step screen checks: `Docs/MANUAL_TESTING.md`. No backend or device runtime is required for the checks in those guides.

Secrets are placeholders (`DEV_TOKEN`, `X-Device-Id` per `Docs/adr/0006`); see `.env.example`.

## Verify

```bash
python Docs/api/test_contract.py
python Docs/db/test_schema.py
python -m pytest -q
python -m compileall app tests
```

Evidence for this SHA: `Docs/TEST_REPORT.md`. Prototype (design truth): `PrototypingFiles/Claybank_ Interactive Workflow v2.html`.

## Backend integration status

No live FastAPI backend is shipped in this repo. Capture, extraction, cloud note generation, FTS5+faiss indexing, Ask retrieval, folder/tag persistence, and sync cursor pull/push all run fixture-backed when `ClayBankApp`'s `on_*` callbacks are not wired. The API contract (`Docs/api/openapi.yaml` + `Docs/api/schemas/*.json`) is the single source for field names/enums; `Docs/MANUAL_TESTING.md#F` maps each frontend seam to its documented callback and how to verify it once the main developer wires a live backend.

## Device-runtime limitations

Native notification delivery, `POST_NOTIFICATIONS` permission, OS share-target, background clipboard reads (forbidden on Android 10+), and local GGUF inference are **not verified** on device. The In-app notification preview (`app/views/capture/`) is explicitly a **desktop preview, not native delivery**. See `Docs/MANUAL_TESTING.md#G` and `Docs/LIMITATIONS.md` for the full disclosure.

## Automated Tests

`Docs/TEST_REPORT.md` (branch `aqib`, 374 passed frontend suite + contract + schema + compile). Re-run `python Docs/api/test_contract.py && python Docs/db/test_schema.py && python -m pytest -q` to confirm green.


## Current phases (see `Docs/Phases.md`)

| Phase | Outcome |
|---|---|
| 0 Decisions | Done — 6 docs, ADRs 0001-0008, contracts, schemas, prototype v2 |
| 1 Contract first | Done (schemas+fixtures+contract test) |
| 2 Capture + Inbox shell | Done — frontend |
| 3 Tier-1 extraction + ASR | Backend-dependent — deferred (job shape present) |
| 4 Note generation + editor | Frontend done; generation is backend/cloud |
| 5 Organization (folders/tags/suggestions/review) | Done — frontend |
| 6 Search + Ask | Frontend done; retrieval is fixture-backed |
| 7 Sync + Settings | Frontend done; live sync is backend-dependent |
| 8 Spike-gated capture surfaces | **Frontend accepted, native spike INCONCLUSIVE** — paste sheet is shipped path |
| 9 Remote submission package | **In progress** — video + tag pending user authorization |
