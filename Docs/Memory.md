# Claybank — Memory

**Status:** Docs locked after Phase 0 grilling (2026-10-31) · frontend implemented (Phases 2+4+5+6+7+8-preview) · backend pending (see Current state below)
**Purpose:** track what has been completed and what is currently being worked on. Update this regularly once coding starts.

## Project root

`D:\Projects\PersonalProjects\ClayBank`

Earlier versions of this file named `C:\Users\shefa_hqr4jwj\Project39\Proto39`. That was wrong and has been corrected. This file (`Docs/Memory.md`) is ground truth for session orientation; every new session should read it first.

## Source of truth

| Artifact | Role |
|---|---|
| `PrototypingFiles/Claybank_ Interactive Workflow v2.html` | **UI truth.** All screens, flows, and copy live here. |
| `PrototypingFiles/archive/Claybank_ Interactive Workflow.html` | archived v1 (has since-decided-away features: resume, 5 tabs, sign-in). Keep read-only as the "before". |
| `PrototypingFiles/Claybank App Wireframes.html` | 14-screen board with Flet widget annotations per screen. |
| `Docs/` | product + architecture truth. If docs and prototype disagree in *look*, docs defer to the prototype; if they disagree in *meaning*, the docs win and the prototype gets fixed. |

## Docs created

- `Docs/PRD.md` — product, scope, non-goals
- `Docs/Architecture.md` — stack, modules, sync, processing
- `Docs/DataModel.md` — entities, fields, states, invariants
- `Docs/GLOSSARY.md` — single source for domain terms
- `Docs/Rules.md` — hard boundaries and hard no's
- `Docs/Phases.md` — hackathon MVP vs post-hackathon path
- `Docs/Design.md` — tokens, components, organization UX
- `Docs/UIUX.md` — pages, components, and the API/JSON wiring per screen
- `Docs/api/openapi.yaml`, `Docs/api/schemas/*.json` — shared contract
- `Docs/api/README.md` — contract map: paths, schemas, error codes, fixture workflow
- `Docs/api/generate_fixtures.py`, `Docs/api/fixtures/*.json`, `Docs/api/test_contract.py`
- `Docs/db/0001_core.sql` + `0002_server.sql` + `0003_device.sql` + `README.md` + `test_schema.py` (shared SQLite schema for server-authoritative store and device replica; guard rails enforced at the SQL level, tested stdlib-only)
- `Docs/adr/0001` … `0008`

## Phase 0 decisions (settled 2026-10-31, after a full grilling pass)

- **Stack:** Flet UI (Android-first; demo runs on a laptop) · FastAPI backend · SQLite + FTS5 + local vector index · `multilingual-e5-small` embeddings (384-dim, ONNX, MIT).
- **Hackathon submission is remote** (dated 2026-10-31): judges see only the video and the repo — no live device. The demo video is the demo (laptop screen recording, phone optional), the repo must be runnable by a cold reviewer with tests green, and prototype v2 is submitted as the interactive design artifact for any screen not finished in-app by the deadline. Phase 9 in `Docs/Phases.md` carries the package checklist.
- **Capture is durable, extraction is enrichment:** `POST /saves` always succeeds with `{url, platform, source_app, captured_at, user_context}`. `source_app` is client-sent; `platform` is derived from the URL host.
- **Kinds:** `video | article | unknown` with capability flags. Gallery/image posts dropped for MVP.
- **Organization:** folders are the only container (nested, `parent_id`, depth ≤ 3, one per save). Tags are flat labels, many per save. `category` and `genre` **deleted**. AI suggests one folder with one confidence; cluster-then-propose after ~3 similar saves; review queue is a derived filter, not a resource.
- **Resume feature deleted** from product, schema, and prototype.
- **AI split:** extraction server-side; ASR cloud by default (Muse Voice Transcribe) with `faster-whisper small` local fallback; note generation **cloud always**; embeddings and search **local always**; chat is the user's choice (cloud or on-device).
- **Local chat model:** on-device `llama_cpp_python`, user picks **MiniCPM5-2B Q4_K_M (1.56 GB)** or **Qwen3-1.7B (~1.1 GB)** in Settings. CPU-only (`n_ctx` 4096, 4 threads), 8 GB RAM floor, foreground service. Demo phone is **MediaTek** → no Hexagon NPU, GPU/Vulkan not in MVP (benchmark table in ADR 0008). No reliance on virtual RAM (RAM Plus). Both model files are downloadable; only one loaded at a time.
- **Backend LLM:** Meta Model API (`dev.meta.ai`, `/compat/v1`, OpenAI-compatible, structured outputs). Any OpenAI-compatible provider (e.g. Gemini) swappable behind one interface. **Never use Meta's contributor pricing tier** (models that train on user data).
- **Never persist media.** Transcripts are text and are kept; audio/video streams are processed transiently and discarded.
- **Sync:** server authoritative; device keeps a **complete replica** (notes, transcripts, vectors) so offline search/chat work; offline writes queue with `Idempotency-Key`; stale write → `409` + conflict banner. Item note edits **auto-save to the device SQLite immediately** (no save button; "Saved on device" state) and push later as queued `note_put` ops (dated 2026-11-01).
- **Auth:** fixed `DEV_TOKEN` + `X-Device-Id` middleware resolving a seeded user; same bearer shape as a future JWT. Auth screens documented as deferred, not deleted.
- **Contract:** UUIDv7 ids, ISO-8601 UTC `Z`, `{data, error:{code,message,detail}}`, cursor pagination, `contract_version`, one enum source (JSON Schema), `Idempotency-Key` on capture, duplicate saves → `409 already_saved` with the existing id unless `force=true`.
- **Tiered extraction:** tier 1 deterministic (yt-dlp for video, trafilatura for articles); tier 2 agent rescue only when a kind's required fields are *all* absent, capped at 5 tool calls / 45 s, same `ExtractionResult` schema, degrades to `unknown`, never partial writes, `agent_trace` stored on the job and excluded from sync. Tier 2 is cut from the hackathon; its interface and ADR stay.
- **UX decisions:** 4 tabs (Inbox · Folders · Search · Settings); Ask opens from Search ("Ask your library") and from a folder's `⋯`; no resume surfaces; Settings shows `Chat model: Cloud | Local` + local model picker, and a split storage row (`Library 4 MB · Local model 1.1 GB`).
- **Capture surfaces:** in-app paste sheet = guaranteed demo path; notification → foreground capture sheet (in scope, spike-gated — background clipboard reads are impossible on Android 10+); OS share target (in scope if the notification spike succeeds); floating bubble = post-hackathon. `POST_NOTIFICATIONS` is requested after the first successful save, never on launch. In-app link input is pure Flet (`ft.Clipboard().get/set`); the notification spike candidate is the `flet-android-notifications` extension (wraps `flutter_local_notifications`: action buttons, progress, foreground service; needs a one-time build patcher for manifest/Gradle). Spike risk narrowed to clipboard read timing — read after the sheet is visible, not on first frame; if the read is empty keep the TextField focused for keyboard paste.
- **Rejected with reasons (each recorded in an ADR):** Flutter (ADR 0001), Parakeet Redux (Avian languages only, no pip path — superseded by cloud-first ASR), EmbeddingGemma (good but 768-dim, Apache‑2.0, and 2.7× larger than e5-small on device; revisit if the index moves server-side), Ollama (external daemon), Virtual RAM (harmful — paging weights), NPU/GPU acceleration (MediaTek demo device), Agent-Reach as a dependency (ADR 0007), ScrapeGraphAI (ADR 0007).

## Current state (updated 2026-11-03)

Docs locked 2026-10-31 and tracked on `aqib`. Frontend phases implemented on `aqib` against those docs:

- **Phases 2, 4, 5, 6, 7, 8-preview implemented as Flet Python UI** — shell, paste sheet, Inbox/processing, note editor, folders/tags/suggestions/review, Search+Ask, Settings+sync coordinators, notification preview (`app/`, `tests/` — 52 test files, 374 passing on this host).
- **Phase 8 native notification spike: INCONCLUSIVE** — desktop preview exists (`app/views/capture/`); native `flet-android-notifications` delivery, `POST_NOTIFICATIONS`, and OS share-target are unverified on device. Guaranteed path is the in-app paste sheet (`Docs/LIMITATIONS.md`).
- **Backend not implemented here** — FastAPI capture/extraction/ASR/LLM/FTS5+faiss/cursor sync remain backend-dependent; fixtures in `Docs/api/fixtures/*.json` stand in.
- **Phase 9 submission package in progress** — this report; README cold-reviewer overhaul; `Docs/SETUP.md` + `.env.example` + `Docs/TEST_REPORT.md` (374+contract+schema green) + `Docs/LIMITATIONS.md` + `Docs/SUBMISSION.md` + `Docs/DEMO_SCRIPT.md` committed and pushed. Video + screenshots + tag pending user authorization.

## Next step

1. User records demo per `Docs/DEMO_SCRIPT.md` and supplies the link/file (video is still PENDING).
2. Tag `claybank-submission-v1` after user authorizes (do not create until then).
3. External submission fields (platform, metadata, visibility, deadline, rubric) remain unresolved — supplied by user when available.

Historical Phase order `Docs/Phases.md` remains the build order; Phases 3 and backend parts of 4/7 stay deferred and belong to the backend owner.

## Updating this file

Keep the decisions list current but concise; when a decision changes, add a dated correction on its bullet instead of silently editing (later sessions need the history), and update the affected ADR.
