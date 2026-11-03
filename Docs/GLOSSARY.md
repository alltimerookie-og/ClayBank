# Claybank — Glossary

**Status:** Locked · **Single definition source.** If a term is used anywhere in `Docs/` or the codebase, it must mean exactly what is defined here; if a needed term is missing, extend this file first, not the ad-hoc usage.

| Term | Definition |
|---|---|
| **Save** | One captured link: `{url, platform, source_app, captured_at, user_context}` + its note, kind, folder, tags, processing job, transcript, embedding. The unit of work. |
| **Capture** | The act of recording a save. Durable by contract: never requires the network, never blocks on the pipeline. |
| **Capture surface** | An entry point that creates a save: paste sheet, notification → foreground capture, share target, (post-hackathon) floating bubble. |
| **`source_app`** | The app the link came from (client-sent, e.g. `Instagram`). Free-form string; never inferred. |
| **`platform`** | Derived from the URL host (e.g. `youtube`). Server-computed; not user-supplied. |
| **`user_context`** | The user's save-time note ("why do you want this?"). Free text, optional, never generated. |
| **Kind (`kind`)** | `video | article | unknown`. A **pipeline selector** — chooses the extraction pipe and note template. Explicitly *not* an organizing axis in the UI. |
| **Capability flags** | `has_audio`, `has_timeline`, `has_images` on a save. Renderer and pipeline decisions read flags, not kind. |
| **Note** | The Markdown document attached to a save. **Source of truth** for everything textual. Frontmatter holds stable facts only (`source, channel, video_url, duration, published, saved, folder, tags`). |
| **Frontmatter facts** | The stable-fact block in a note's YAML header. Machine state (confidence, processing, suggestions) deliberately never goes here. |
| **Transcript** | Timestamped text extracted/transcribed from a save's audio or captions. Text — stored; audio — never persisted. |
| **Folder** | The **only container** in the product. Nested via `parent_id`, depth ≤ 3, holds one save each via a nullable `folder_id`. Represents a **project with a finish line**, not a topic. |
| **Inbox** | The *state* of having no folder (nullable folder). Administrative identity of the app's home tab. Not a folder; no `Unsorted` container exists. |
| **Tag** | A flat, freeform label; many per save; not a container. Normalized case-insensitively; `_tags` join table only. |
| **Facet** | A cross-cutting axis (e.g. platform, language, status). Expressed in UI filters or tags; never a folder. |
| **Suggested folder** | `{path, confidence}` — one per save, from the sorting stage. API metadata; never frontmatter. |
| **Review queue** | Derived filter `needs_review=true` (suggestion below threshold or conflict). Skippable forever; a resource, never a *filter*. |
| **Cluster-then-propose** | The folder-emergence mechanic: ≥3 saves in one similarity cluster with no folder → propose once with name+confidence+previews; rejects stick. |
| **Processing job** | Per-save background work with streamed stages: `queued → extracting → transcribing → analyzing → sorting → ready`. Stages individually skippable/failed. |
| **Tier 1 extraction** | Deterministic extraction: `yt-dlp` for videos, `trafilatura` for articles; emits an `ExtractionResult` (contract schema). |
| **Tier 2 (rescue agent)** | Agent-based extraction fallback. Fires only when a kind's required fields are **all absent** (video: no title *and* no transcript; article: no body; unknown: no title *and* no body). Caps 5 tool calls / 45 s; same output schema; degrades to `unknown`; `agent_trace` stored on the job, excluded from sync. Post-hackathon. |
| **`ExtractionResult`** | Contract schema for both tiers' output (title, platform-specific fields, body, transcript availability, capability flags). |
| **Match reason** | Why a save matched a search: `title | transcript | body | tag | folder | semantic`. Shown with the matched fragment and a jump target on every result. |
| **Jump target** | A stable in-note anchor: video timestamp (`0:42`) or article heading anchor; makes a match reason actionable. |
| **Ask** | Folder-scoped (or library-scoped from Search) Q&A over saves; **answers must carry citations** (save id + offset) to be valid. |
| **Citation** | An answer reference: the save used + the anchor in it, rendered as a chip that opens the note. Absence of a citation is a bug. |
| **Hybrid search** | FTS5 keyword (BM25) + vector (e5-small, faiss flat) with reciprocal rank fusion. |
| **`index_meta`** | The pinned model id + dim + version for the local index. Search refuses a mismatched index instead of silently returning wrong results. |
| **Complete replica** | The device's full local mirror (notes, transcripts, folders, tags, metadata) enabling offline read/search/local-chat. |
| **Idempotency-Key** | Header on writes so offline queuing can replay safely; replays dedupe server-side. |
| **Conflict** | Two writes vied for one save. Server keeps last write; the user's device edit survives as pushed; stale writes → `409 conflict` + banner with keep-both recovery. |
| **Local chat model** | On-device GGUF via `llama_cpp_python`. Hackathon pick: **MiniCPM5-2B Q4_K_M (1.56 GB)** or **Qwen3-1.7B (~1.1 GB)**, user-selected, CPU-only, one loaded at a time. |
| **Cloud model** | Meta Model API (`dev.meta.ai`, OpenAI-compatible `/compat/v1`); powers note generation always and chat when `Cloud` is selected. Contributor (training-on-data) tier is banned. |
| **Chat model setting** | The only AI toggle, `Cloud | Local` — controls chat only; embeddings/search are local always, note generation cloud always. |
| **ASR** | Automatic speech recognition. Multimodal model only: cloud transcription/visual description through the configured model, no separate audio STT and no local fallback; 10-minute duration cap. |
| **Filing sheet** | The bottom sheet for moving a save (searchable folder picker + tag chips + Done). Never a full page. |
| **Three-effort model** | Zero (capture, nothing asked) / one tap (accept suggestion, undoable) / deliberate (filing sheet). Deliberate must never be the default; one-tap must never be silent. |
| **Degraded save** | A save whose pipeline partially failed, rendered normally in UI with reduced sections — never an error page. |
| **Contract** | `Docs/api/openapi.yaml` + `api/schemas/*.json`: UUIDv7 ids, ISO-8601 UTC `Z`, `{data, error:{code,message,detail}}`, cursor pagination, `contract_version`. |
| **Contract test** | `Docs/api/test_contract.py` — fixtures validate against JSON Schemas; must stay green for any contract-touching change. |
| **Resume** | **Deleted feature.** No resume row, banner, progress state, or "stopped at" concept exists in product, schema, or UI. Its absence is deliberate. |
| **Genre** | **Deleted.** Old v1 note frontmatter field duplicating folder + tags; superseded by folder + tags. |
| **Category** | **Deleted.** Old v1 concept = suggested folder path + confidence, collapsed into the single `suggested_folder {path, confidence}` field. |
