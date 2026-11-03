# Claybank - Remote Submission Index

Branch: `aqib` · Remote: `https://github.com/alltimerookie-og/ClayBank.git` · See `Docs/TEST_REPORT.md` for the exact submission SHA.

## Overview

One link = one Save + one note + one job. Share now, find later. Text-only, videos never saved.

## Where to look

| Item | Link |
|---|---|
| Project guide | `README.md` |
| Setup + env | `Docs/SETUP.md` + `.env.example` |
| Architecture | `Docs/Architecture.md` |
| Data model | `Docs/DataModel.md` + `Docs/db/` |
| Contract | `Docs/api/README.md` + `openapi.yaml` + `schemas/` |
| DB invariants | `Docs/db/README.md` |
| Design tokens | `Docs/Design.md` |
| Pages -> API | `Docs/UIUX.md` |
| Decisions | `Docs/Memory.md` + `Docs/adr/` |
| Prototype (design truth) | `PrototypingFiles/Claybank_ Interactive Workflow v2.html` |
| Demo script (shot list) | `Docs/DEMO_SCRIPT.md` |
| Demo assets (pending recording) | `demo/` (directory if useful; no dummy files) |
| Test evidence | `Docs/TEST_REPORT.md` |
| Limitations disclosure | `Docs/LIMITATIONS.md` |
| Rules / Build order / Glossary | `Docs/Rules.md` / `Docs/Phases.md` / `Docs/GLOSSARY.md` |

Prototype is **interactive design truth** (`Docs/Phases.md:104`) - not a claim that every screen is fully implemented. Unfinished screens are represented by the prototype.

## Run and verify

```bash
python Docs/api/test_contract.py
python Docs/db/test_schema.py
python -m pytest -q
python -m compileall app tests
flet run
```

## Phase completion

| Phase | Outcome |
|---|---|
| 0 Decisions | Done |
| 1 Contract | Done |
| 2 Capture+Inbox shell | Done (frontend) |
| 3 Extraction+ASR | Deferred - backend |
| 4 Note gen+editor | Frontend done; generation is backend |
| 5 Organization | Done (frontend) |
| 6 Search+Ask | Done (frontend; retrieval fixture-backed) |
| 7 Sync+Settings | Done (frontend; live sync is backend) |
| 8 Capture surfaces | **Frontend accepted, native spike INCONCLUSIVE** |
| 9 Submission package | In progress (this index; video + tag pending) |

## Submission checklist

- [x] Docs, ADRs, API contracts/schemas/fixtures, DB schemas, prototype tracked on `aqib`
- [x] README cold-reviewer guide (no stale "no code yet")
- [x] Setup + `.env.example` placeholders
- [x] Test evidence for this SHA (contract + schema + 374 pytest + compile)
- [x] Limitations with Phase 8 INCONCLUSIVE disclosure
- [ ] Demo recording + screenshots (see `Docs/DEMO_SCRIPT.md`) - pending user recording
- [ ] `Docs/Memory.md` close-out
- [ ] Release hygiene final check
- [ ] Tag `claybank-submission-v1` - awaiting user authorization after this report

## Honest dependencies

- Backend (FastAPI capture, extraction, ASR, LLM note generation, FTS5+faiss, sync cursor) not implemented in this repo; fixtures stand in.
- Native notification delivery / `POST_NOTIFICATIONS` / share-target / GGUF inference are device-runtime and remain unverified on hardware. Paste sheet is the guaranteed path.

Video URL: **[PLACEHOLDER - user will supply recording link/file]**.

## External information still missing

Platform/portal, team metadata, public/private visibility, video host/length, deadline, rubric, presentation format - not specified in `Docs/` and left as unresolved external information pending user input.
