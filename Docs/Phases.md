# Claybank — Phases

**Status:** Locked (post-Phase 0 grilling, 2026-10-31)
**Purpose:** build order for the hackathon MVP first, then the post-hackathon path. Each phase is testable against prototype v2 screens and ends with a demoable outcome.

## Phase 0 — Decisions (done)

All Phase 0 questions are settled and recorded in `Docs/Memory.md`, `PRD.md`, `Architecture.md`, `DataModel.md`, and `adr/0001–0008`. The deliverables of this pass: six rewritten docs, `GLOSSARY.md`, `DataModel.md`, the API contract (`api/openapi.yaml` + `api/schemas/`), fixtures + contract test, ADRs, and prototype v2. Do not re-grill settled questions; new ones go through the grilling skill.

## Phase 1 — Contract first (hackathon)

Goal: the API shape exists and is enforced before any feature code.

- Scaffold `backend/` (FastAPI + SQLite) against `Docs/api/openapi.yaml`.
- `Docs/api/test_contract.py` green: fixtures valid against `api/schemas/*.json`.
- `POST /saves` implemented with capture-always-succeeds semantics, URL canonicalization, duplicate `409 already_saved`, `Idempotency-Key` replay.
- Seeded user + `DEV_TOKEN`/`X-Device-Id` middleware (`adr/0006`).

Demoable outcome: capture a link; get a durable save record. *Reference screens: Add link sheet.*

## Phase 2 — Capture + Inbox shell (Flet)

Goal: a user can create a save and see it in the Inbox.

- App shell: **4-tab** NavigationBar (Inbox · Folders · Search · Settings), theme tokens from `Design.md`.
- Paste sheet with clipboard detection; offline queue with `Idempotency-Key` replay.
- Inbox rendering: processing pill, new-save card, streamed stage statuses over SSE/polling.
- First-sync pull (cursor-based) so the device replica starts working.

Demoable outcome: laptop flow — paste link → card in Inbox with live stages.

## Phase 3 — Tier-1 extraction + ASR

Goal: a saved link becomes metadata + transcript.

- `yt-dlp` (video metadata + captions) and `trafilatura` (article body), one `ExtractionResult` schema.
- Cloud ASR (Muse Voice Transcribe) with `faster-whisper small` local fallback; 10-minute duration cap; **temp media scrubbed in all paths (ADR 0004)**.
- Job states + per-stage failures degrade without blocking (`Rules.md` §5).
- `flet-libffmpeg` used on device only if needed for audio fetch in the local chat era (not in this phase's critical path).

Demoable outcome: YouTube + an Instagram public reel land with transcript or a clear degraded state.

## Phase 4 — Cloud note generation + note editor

Goal: each save reads like the prototype note.

- LLM provider interface (OpenAI-compatible; Meta Model API first), structured outputs: Overview + Key points + Links guaranteed.
- Note write-through: frontmatter facts (system-written), body (LLM), transcript excerpt; `index_meta` + FTS5/section index updated on write.
- Note editor: properties grid, headings, checkbox toggles, quick-insert chips, `⋯` Move | Delete, *Open original*.
- Frontmatter rendered as live controls (folder → filing sheet, tags → chips) per `Design.md`.

Demoable outcome: the prototype's item note, real, for a freshly saved link.

## Phase 5 — Organization: folders, tags, suggestions, review

Goal: the organization model is real, not cosmetic.

- Folder CRUD + nesting (depth ≤ 3), one-folder-per-save invariant enforced at API level.
- Tags: flat, unique-normalized, many-per-save; tag chips filter in place.
- `suggested_folder {path, confidence}` single field; auto-file above threshold (undoable), review queue below.
- Cluster-then-propose: ≥3 saves in one similarity cluster with no folder → propose once; rejects stick.
- Folder view: breadcrumb, child-folder chips (navigate), separate Tags row (filter); no Resume banner exists.

Demoable outcome: save → suggestion → accepted in one tap → filed with undo visible.

## Phase 6 — Hybrid search + Ask

Goal: the retrieval bet pays off.

- FTS5 + faiss flat index (384-dim e5-small), reciprocal rank fusion, `query:`/`passage:` prefixes, `index_meta` mismatch → refuse.
- Match reason + matched fragment + jump target (video timestamp / heading anchor) on every result.
- Ask: folder-scoped (device-local context when offline) + library-scoped from Search; **citation chips mandatory** in the response schema; suggested prompts.
- *"Ask your library"* entry at the top of Search (Ask is not a tab).

Demoable outcome: search a phrase spoken in a video → transcript-matched result with timestamp jump; ask a folder → cited answer.

## Phase 7 — Sync hardening + settings

Goal: the full-replica claim is true.

- Complete replica on device (notes, transcripts, section indexes); offline search/chat/reading proven with the network off.
- Offline writes replay; `409` conflicts → banner + keep-both recovery; `agent_trace`-style fields excluded from payload.
- Settings: `Chat model: Cloud | Local` + local model picker (files downloadable for later), split storage row, auto-sort/digest/Wi-Fi-only/notification toggles, sync state + backup time.
- `POST_NOTIFICATIONS` requested after first successful save only.

Demoable outcome: demo on laptop + phone; writes queue offline, sync on reconnect without duplicates.

## Phase 8 — Spike-gated capture surfaces (hackathon, conditional)

Goal: one capture path outside the app, honestly gated.

- Spike (2 h): Flet notification plugin on the demo device.
  - **Success:** persistent *"Save a link"* notification with `Paste and save` → foregrounds app into pre-filled capture sheet; share-target intent reuses the same plumbing.
  - **Failure:** paste sheet ships as the demo path; notification documented as post-hackathon; no silent scope creep.

Demoable outcome: capture from the notification shade (or documented fallback), still one-tap.

## Phase 9 — Remote submission package

Submission is **remote**: judges do not see the device or laptop live — the video is the demo and the repo must stand alone. The phone is optional; a laptop screen recording is the safest capture path.

- **Demo video** (the demo itself, not a trailer): Inbox → capture → processing → note → folders → review-with-undo → search (match reasons, timestamp jump) → Ask (citations) → Settings; offline queue/sync shown with the network visibly off; every functionality-aesthetic line gets bullets, not prose — the recording shows one decision at a time.
- **Runnable repo:** `README.md` setup + `run` instructions a cold reviewer can follow in minutes; contract + schema tests green on a fresh clone (`python Docs/api/test_contract.py`, `python Docs/db/test_schema.py`); secrets via env with documented values; no `dev`-only state committed.
- **Design artifact attached:** prototype v2 stands in for any in-app screen not finished by the deadline — submitted as a link/file alongside the video, clearly labeled as interactive design truth.
- Edge cases from `Rules.md` §5 on screen (degraded saves, conflicts, offline).
- Update `Memory.md` with final state; tag the submission build; declare recovered-vs-failed items honestly if any phase was cut.

## Post-hackathon path (recorded, not built)

Ordered by payoff per risk:

1. **On-device local chat** — `llama_cpp_python` wheels exist (`pypi.flet.dev`); `LocalProvider` interface ships in Phase 2. Includes model download UX, foreground service, thermal testing, *"running on device · slower"* hint.
2. **Tier-2 extraction agent rescue** — interface + ADR exist; only fires on total tier-1 failure.
3. **Floating bubble capture** — `SYSTEM_ALERT_WINDOW` + custom Flet extension.
4. **Gallery/image posts** — `kind: gallery`, flag-gated renderer slots already in place.
5. **Auth** — JWT swap over the same bearer shape; sign-in screens from prototype v1 come back as deferred-designed UI.
6. **iOS** — capture surfaces first, library features after.
7. **Embedding upgrade option** — EmbeddingGemma (768-dim) if the index moves server-side; requires re-index (pinned in `index_meta`), never a silent swap.
8. **Parakeet Redux fast-path** — European-language ASR re-evaluated only if Photon gets a pip path.
