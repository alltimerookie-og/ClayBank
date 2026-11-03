# Claybank — Product Requirements Document

**Status:** Locked (post-Phase 0 grilling, 2026-10-31)
**UI truth:** `PrototypingFiles/Claybank_ Interactive Workflow v2.html` (v1 archived)
**Owner:** Md. Shefayet
**Companion docs:** `Architecture.md` · `DataModel.md` · `GLOSSARY.md` · `Rules.md` · `Phases.md` · `Design.md` · `adr/`

## 1. Vision

Claybank is a personal **save-for-later** app for links. The promise is the prototype's: **share it now, find it later**. One link becomes one **Save**; each Save is one **Markdown note** the user can read, edit, search, and ask questions about — "like Obsidian for saved videos", without any media stored.

Saving must never fail and never block on organization. Everything else is enrichment layered on top of a durable capture.

## 2. Users

- People who save Instagram/TikTok/YouTube/Facebook clips and articles into a messenger backlog and then lose them.
- People who want a **note attached to each save**, not a wall of URLs.
- People who organize lightly (a few folders, occasional tags) and mostly rely on search.
- Personal, single-user-per-account product. No team spaces, no public sharing.

The prototype's hard line stands: **videos are never saved — text only.** This is a privacy feature, not a limitation.

## 3. Product principles

1. **Capture is durable; extraction is enrichment.** `POST /saves` always succeeds with `{url, platform, source_app, captured_at, user_context}` — network failures affect the pipeline, never the capture.
2. **Retrieval over taxonomy.** Search (keyword + semantic) is the primary interface. Folders hold *intent* (projects that end), not topics; tags carry cross-cutting facets; the AI proposes and the user disposes.
3. **One note per save, Markdown is the source of truth.** The note is portable, greppable, and editable; the database is an index over it.
4. **Degraded is normal.** A save whose transcript failed renders as a smaller note, not an error page. Unknown kinds render as known things.
5. **Honest local.** "Offline" means search/chat/reading work; new processing waits for the network. The UI says so in exactly one line.

## 4. What a save is

```
Save = capture record (url, platform, source_app, captured_at, user_context)
     + kind (video | article | unknown)  + capability flags
     + one folder (nullable → Inbox)     + many tags
     + one processing job (stage states)
     + one Markdown note (frontmatter facts + LLM/fallback body)
     + transcript (when available)       + embedding (for search)
```

Platforms in scope: Instagram, Facebook, TikTok, YouTube (public) and arbitrary web pages. `kind` selects the extraction pipeline and the note template — **it is never an organizing axis in the UI**.

## 5. Features

### 5.1 Capture (in-scope surfaces)
- **In-app "Add link" sheet** with clipboard detection and paste — the guaranteed demo path.
- **Notification → foreground capture:** a persistent *"Save a link"* notification with `Paste and save`; tapping it opens the app into the sheet pre-filled from the clipboard. (Android 10+ forbids background clipboard reads, so the read happens while foregrounded — see `adr/0004` companion note in `Architecture.md` §Capture.) Spike-gated; `POST_NOTIFICATIONS` requested **after the first successful save**.
- **OS share target** ("Share → Claybank") — in scope if the notification spike succeeds.
- **Floating bubble** — post-hackathon (`PrototypingFiles v2` marks it as such).
- All captures land in the **Inbox** immediately with `user_context` note + one-tap folder chips.

### 5.2 Processing (`queued → extracting → transcribing → analyzing → sorting → ready`)
- Stages are individually skippable/failed; a save is visible from the instant of capture.
- Tier 1 deterministic extraction: yt-dlp (video), trafilatura (articles).
- ASR: cloud default (Muse Voice Transcribe), `faster-whisper small` local fallback; 10-minute duration cap.
- Note generation: cloud LLM, always. Guarantees Overview + Key points + Links; other sections are dynamic.
- Sorting: one `suggested_folder {path, confidence}`; above threshold → auto-file (undoable); below → review queue.
- Budget: 30 s target, 2 min cap, streamed per-stage status in the Inbox.
- Tier 2 agent rescue: interface exists, deferred post-hackathon (`adr/0002`).

### 5.3 Library
- **4 tabs: Inbox · Folders · Search · Settings** (Ask is reachable from Search and the folder `⋯`, not a tab).
- **Inbox:** processing pill, search bar, *"Needs a quick check"*, *"Recently added"*. The Inbox is a state, not a folder; no separate "Unsorted" container exists.
- **Folders:** grid with cover collages, counts, sort chips, `+ New`.
- **Folder view:** breadcrumb, child-folder chips (navigate) + separate Tags row (filter), item list.
- **Item note:** Obsidian-like — properties grid, headings, lists, toggleable checkboxes, links, timestamped transcript, related items. `⋯` menu: Move | Delete (with confirm). *Open original* opens the source.

### 5.4 Search + Ask
- **Hybrid search:** FTS5 keyword + `multilingual-e5-small` vectors (local, `index_meta` refuses model/dim mismatch). Results always show a **match reason** (title/transcript/body/tag/folder/semantic) with the matched fragment and a jump target (video timestamp / article heading).
- **Ask:** folder-scoped by default, library-scoped from Search. Answers cite the saves used (chips → note, at offset). Citation-less answers are a bug, not a style.

### 5.5 Settings
- **`Chat model: Cloud | Local`** — the *only* AI toggle, with local model picker (MiniCPM5-2B / Qwen3-1.7B) and one honest line: *"Notes are always generated in the cloud. Chat can run on this device."*
- **Auto-sort new saves**, **Weekly digest of unopened saves**, **Wi-Fi only processing**, **Quick-save notification**.
- **Storage row (split):** `Library 4 MB · Local model 1.1 GB`.
- Sync state + backup timestamp. Privacy banner: *videos are never saved. Cloud AI gets the transcript and metadata only.*

## 6. Organization model

- **Folders are containers and the only one.** User-owned, nested via `parent_id` (depth ≤ 3), **one folder per save** (null = Inbox). A folder is a project with a finish line, not a topic ledger.
- **Tags are flat labels**, many per save, never a container. No topic tags (a tag applying to >⅓ of the library is a facet, not a tag).
- **AI proposes, user disposes.** One suggested folder per save with one confidence; no silent filing — above threshold auto-files with undo visible, below threshold queues for review.
- **Cluster-then-propose:** after ~3 saves share no folder and fall inside one similarity threshold, propose a folder (name + confidence + member previews). Rejecting a cluster never re-proposes it. No automatic folder creation, ever.
- **Renaming a folder is a bulk frontmatter rewrite** (Markdown is truth) — that cost is why the depth/count limits exist.
- The review queue is a derived filter (`needs_review=true`), skippable forever, never debt.

## 7. Data & sync

- Server authoritative; device keeps a **complete replica** (notes, transcripts, vectors) → offline search/chat/read all work; new processing needs the network.
- Offline writes queue with `Idempotency-Key`; replays are safe. Stale write → `409` + conflict banner; the user's edit wins, the server version is preserved for recovery.
- Contract: UUIDv7 strings, ISO-8601 UTC `Z`, `{data, error:{code,message,detail}}`, cursor pagination, `contract_version`, one enum source (JSON Schema in `Docs/api/schemas/`).
- **Duplicates:** URL canonicalized (tracking params stripped, `/shorts/x` ↔ `watch?v=x`); a duplicate capture returns `409 already_saved` with the existing id unless `force=true`.

## 8. Non-functional

- **Offline definition (used verbatim in copy):** capture, reading saves, search, and local chat work offline. Note generation, transcription, and extraction require the network.
- **Processing:** 30 s target, 2 min cap, streamed stage statuses.
- **Local chat:** CPU-only, ~6–10 tok/s expected; when online but Local is selected, show *"running on device · slower"*. Requires ≥ 8 GB RAM device; a smaller-footprint app (~2.7–3 GB with model loaded) is the design budget.
- **Device:** Android-first (MediaTek demo phone); iOS deferred; laptop + paste-a-link is the hackathon demo.
- **Privacy lines:** never persist media; cloud receives transcript + metadata only; ASR/text never routed through training-on-your-data tiers (Meta contributor tier is a hard no — `Rules.md`).

## 9. Hackathon scope vs post-hackathon

**In scope (hackathon):** paste-a-link capture (laptop), pipeline to note, folders/tags/suggestions + review, hybrid search with match reasons, folder-scoped Ask with citations, cloud note generation, cloud ASR, complete-replica sync with the dev token, the four-tab UI of prototype v2.

**Deliberate non-goals (with reasons, also in `Rules.md`):**

| Deferred/removed | Why |
|---|---|
| Floating bubble capture | overlay permission + custom Flet extension; week of work |
| Tier-2 extraction agent | interface kept; only fires on total extraction failure |
| Gallery/image posts (`kind: gallery`) | no vision pipeline in MVP; renderer stays flag-gated |
| On-device transcription | no `faster-whisper` Android wheel; needs an ONNX port |
| GPU/NPU acceleration | MediaTek demo device — no llama.cpp backend; CPU is the path |
| iOS capture surfaces | deferred entirely; demo is Android + laptop |
| Auth UI | dev-token middleware; screens documented as deferred, not deleted |
| Resume feature | **product decision — removed everywhere** (product, schema, prototype)༘ |
| On-device local chat | wheels exist (`pypi.flet.dev`); the *interface* ships now, the on-device build is the first post-hackathon task |
| Virtual RAM reliance | harmful for LLM weights (paging storm) |

## 10. Success criteria (hackathon demo)

1. Paste a link → Save visible in Inbox within ~2 s, note ready ≤ 30 s (typical).
2. Ask a folder a question → answer with ≥ 1 citation chip opening the right note.
3. Search a phrase spoken in a video → result with *"Match in transcript"* + timestamp jump.
4. Suggestion accepted from the review queue → save filed, undo visible.
5. Kill the network → saved items still searchable and readable ("offline" line holds).
6. No screen contains the word "resume", a progress bar, or a 6-tab bar from v1.

## 11. Deferred, not deleted

Sign-in screens (Google/Apple/email), GraphQL-era ideas, cover-collage editing, folder colors/icons, weekly digest UI, multi-device UI. These live in the prototype's v2 "Deferred screens" state and in `Phases.md`; nothing here removes them from the product vision — only from this build.
