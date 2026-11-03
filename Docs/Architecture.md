# Claybank — Architecture

**Status:** Locked (post-Phase 0 grilling, 2026-10-31)
**Source:** PRD.md + grilling decisions · UI truth is `PrototypingFiles/Claybank_ Interactive Workflow v2.html`
**Companion:** `DataModel.md` (entities/fields) · `GLOSSARY.md` (terms) · `api/openapi.yaml` (contract) · `adr/`

## 1. Product shape

Claybank is a **personal save-and-note app**. The unit of work is a **Save** = one captured link + one Markdown note + one processing job. The wireframes describe mobile-first capture (share, paste, notification), an Inbox processing flow, a folder library, search with match reasons, and folder-scoped Ask.

The product promise **text only, never keep videos** fixes most of the architecture before a line of code: no media storage, no transcoding, no blob store. Media streams are processed transiently and discarded end-to-end (`adr/0004`).

## 2. Architecture style

**Server-authoritative with a complete local replica.** The backend owns the canonical records and the processing pipeline; the Flet app owns a full mirror (notes, transcripts, folders, tags, suggestion metadata) so that **search, chat, and reading work offline**, and capture is durable offline.

```
[Flet app (Android-first, laptop demo)]
   capture sheet · inbox · folders · note editor · search · ask · settings
        │  HTTPS, bearer token           ▲ pull (cursor) ▲ push (queued, Idempotency-Key)
        ▼                                │
[FastAPI backend] ── authoritative store ── [processing workers]
   extraction (tier 1 / tier 2 stub) · ASR (cloud→local) · LLM (cloud)
        │                                        │
        └── transient media never retained after processing ──┘
```

- Writes may happen offline; they queue and replay idempotently. The server rejects stale writes with `409` and preserves both versions.
- Vectors are **derived** from note text with a pinned embedding model (`index_meta`); they are computed locally on both sides and excluded from the sync payload.

## 3. Stack

| Concern | Choice | Notes |
|---|---|---|
| UI | **Flet** (Python), Android-first | `flet build` targets Android; demo runs on laptop. Flutter rejected (`adr/0001`). |
| Backend | **FastAPI** (Python) | single service; workers are in-process tasks, not a queue product |
| Store | **SQLite** + FTS5 | server store and device replica share one schema (`DataModel.md`) |
| Vectors | **faiss-cpu** flat index | index file stored next to the DB; 384-dim |
| Embeddings | **`intfloat/multilingual-e5-small`** | ONNX Runtime, 118M params, MIT, 100 languages; `query:` / `passage:` input prefixes |
| Extraction | **yt-dlp** (video) · **trafilatura** (articles) | tier 1 deterministic; fallback chain in `adr/0007` |
| ASR | **Multimodal model only** | multimodal transcription/visual description through the configured cloud model; no separate audio STT or local fallback |
| Note gen | **Cloud, always** — Meta Model API (`api.meta.ai`, `/compat/v1`, OpenAI-compatible) | any OpenAI-compatible provider swappable behind one interface; **contributor (training-on-data) tier is a hard no** |
| Local chat | **`llama_cpp_python`** in-process | MiniCPM5-2B Q4_K_M (1.56 GB) or Qwen3-1.7B (~1.1 GB), user-picked; CPU-only (`n_ctx 4096`, 4 threads), 8 GB RAM floor, foreground service (`adr/0008`) |

### 3.1 The AI split (one table, one meaning)

| Stage | Where | Why |
|---|---|---|
| Extraction (yt-dlp / trafilatura) | server, network-bound | cannot run on device |
| Transcription | server; multimodal model only | one cloud transcription path, no local fallback |
| **Note generation** | **cloud always** | note quality; also keeps "Cloud AI gets the transcript and metadata only" literally true |
| **Embeddings + index** | **local always** | privacy, instant, offline |
| **Search** (FTS5 + vectors) | **local always** | offline by definition |
| **Chat / Ask** | **user choice** (cloud or on-device LLM) | the only AI toggle in Settings |

The Settings control is therefore named **"Chat model: Cloud | Local"** — one control, one meaning. There is no toggle named "AI model"; that phrasing was rejected because a toggle that changes one of three stages is a lie the demo can't afford.

## 4. Core modules

### 4.1 Capture
- **In-app paste sheet** — clipboard read happens in the foreground (guaranteed path).
- **Notification → foreground capture** — persistent *"Save a link"* notification; `Paste and save` is a `PendingIntent` that foregrounds the app **directly into the sheet, pre-filled from the clipboard**. Android 10+ denies background clipboard reads, so the tap must land in the app; that constraint is why the bubble is post-hackathon and the notification is a *foreground capture* (sheet pre-filled), not a background paste. `POST_NOTIFICATIONS` is requested after the first successful save. **Spike-gated (2 h):** if the Flet notification plugin path fails, the paste sheet still ships the demo.
- **Share target** — in scope only if the spike succeeds (it shares the same intent plumbing).
- **Floating bubble** — post-hackathon; needs `SYSTEM_ALERT_WINDOW` + a custom Flet extension (prototype marks it phase 2).

Responsibility: normalize any entrance into a **save intent** `{raw_url, source_app, user_context}` → canonicalize (strip tracking params, resolve `/shorts/x` ↔ `watch?v=x`, resolve platform from host) → dedupe (`409 already_saved` + existing id unless `force=true`) → persist capture. **This step never calls the network and never blocks on the pipeline** (PRD principle 1).

### 4.2 Processing pipeline (per save, one job, streamed statuses)
```
queued → extracting → transcribing → analyzing → sorting → ready
           (tier 1)     (audio only)   (note gen)  (suggest)
```
- **extracting (tier 1):** `yt-dlp` for video metadata + captions when present; `trafilatura` for article body. Emits an `ExtractionResult` JSON (one schema, `Docs/api/schemas/extraction-result.json`).
- **tier 2 (agent rescue) — interface + ADR only in the hackathon:** fires only when a kind's required fields are all absent (video: no title *and* no transcript; article: no body; unknown: no title *and* no body). Caps: 5 tool calls / 45 s. Same `ExtractionResult` schema. Degrades to `unknown` rather than partial writes. `agent_trace` is stored on the job and excluded from sync.
- **transcribing:** multimodal transcription/visual description through the configured cloud model. Audio is fetched transiently and discarded after transcription (`adr/0004`).
- **analyzing (note gen):** cloud LLM with structured output: Overview + Key points + Links guaranteed; other sections dynamic; transcript excerpt appended. Frontmatter facts are written by the system, not the LLM.
- **sorting:** one `suggested_folder {path, confidence}` from the same embedding used for search; above threshold (config) → auto-file with visible undo; below → `needs_review=true`.
- **States live on the job, not the note.** Confidence and suggestion live in API metadata, never in note frontmatter.
- **Budget:** 30 s target, 2 min hard cap, 10-min media-duration cap on transcription; stages are individually skippable/failed; every failure degrades, never blocks (`Rules.md`).

### 4.3 Note (source of truth → index)
- Note Markdown is authoritative: frontmatter holds **stable facts only** (`source, channel, video_url, duration, published, saved, folder, tags`); LLM-generated body sections follow it.
- On write, the system parses the note into the index (`DataModel.md` §indexes): FTS5 row + section index (match reasons) + embedding.
- Derived fields (confidence, suggestion, processing state) are API metadata on the save/job, deliberately excluded from the note so user edits can't break the review queue.
- Editor renders frontmatter as **live controls** (folder → filing sheet, tags → chips); raw Markdown editing stays available (`Design.md` §Note).

### 4.4 Search & Ask
- **Local hybrid:** FTS5 (BM25) + faiss flat vector search; reciprocal rank fusion; configured offline-safe (the device replica holds both).
- **Result carries a match reason** — which field matched (title/transcript/body/tag/folder/semantic) + matched fragment + jump target (video timestamp / heading anchor). This data comes from the write-time section index.
- **Ask** runs over the same local index when scoped to a folder on the device; server-side Ask uses the same index shape. Answers must carry citations (save id + offset) — enforced in the LLM response schema.

### 4.5 Sync
- Device pulls `since=<cursor>`; server is authoritative; device writes queue offline with `Idempotency-Key` and replay safely.
- Conflicts: server keeps the last write; user's device edit survives as the pushed version; stale push → `409 conflict` + banner with a keep-both path.
- Payloads: saves/note metadata, notes, transcripts, folders, tags, jobs (without `agent_trace`). Vectors excluded (derived).
- Device and server SQLite schemas are the **same schema** (`DataModel.md`), with the device adding a dirty-queue table.

### 4.6 Auth (hackathon shape)
- `X-Device-Id` + `Authorization: Bearer DEV_TOKEN` middleware resolving a seeded user. The bearer shape is what a future JWT swap needs; no auth screens in the hackathon build (`adr/0006`).

## 5. Repository layout (planned)

```
backend/
  api/            # FastAPI routers aligned 1:1 with openapi.yaml tags
  capture/        # canonicalization, dedupe, idempotency, save intents
  processing/     # job orchestration + stage runners (extract, transcribe, analyze, sort)
  extraction/     # ytdlp.py, trafilatura.py, rescue.py (tier 2 stub interface)
  asr/            # muse_voice.py, whisper_local.py
  llm/            # provider.py (OpenAI-compatible), meta_model.py, prompts/, schemas
  store/          # sqlite.py, fts5.py, vectors.py, index_meta
  sync/           # cursor + idempotent replay + conflict rules
app/              # Flet
  shell/          # 4-tab NavigationBar, routing, theme
  capture/        # paste sheet, notification handler, share intent
  inbox/ folders/ search/ ask/ settings/ note/ suggestions/
  local/          # LocalProvider interface now; llama.cpp impl post-hackathon
data/             # server runtime: sqlite db, faiss index, index_meta.json
Docs/api/         # openapi.yaml, schemas/, fixtures/, contract check
```

## 6. Boundaries this architecture must respect

- **No media retained after processing** — fetch → transcribe/analyze → discard, scrub the temp dir on success and failure (`adr/0004`).
- **One note per save; Markdown is truth** — the DB is an index over it; renames are bulk frontmatter rewrites.
- **Folders are the only container; `kind` is never an organizing axis** (`DataModel.md` invariants).
- **Match reasons are visible in every search result** — write-time indexing is what makes the prototype's search real.
- **`agent_trace` never syncs**; tier 2 never partial-writes.
- **Every failure degrades to a usable save** — visible error state in Inbox, note still editable.
- **Local model downloads are visible states** ("setting up local model…"), never silent.
- **`index_meta` refuses model/dim mismatch** instead of searching across incompatible embeddings.
- **Keep `contract_version` on every response**; the contract is the source for fixtures + tests.
