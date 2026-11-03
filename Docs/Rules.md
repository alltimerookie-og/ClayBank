# Claybank — Rules

**Status:** Locked (post-Phase 0 grilling, 2026-10-31)
**Purpose:** hard boundaries and hard no's for any agent building Claybank. When a decision here and a convenient shortcut disagree, this file wins.

## 1. What Claybank is

A personal save-and-note app for links to short video and other web content. One save = one Markdown note. The app organizes (folders + tags + suggestions), searches (keyword + semantic, with match reasons), and answers questions scoped to a folder, with citations. The name is **Claybank**. The promise is *share it now, find it later*, and the privacy line is *videos are never saved — text only*.

## 2. Hard yes

- **Capture always succeeds.** `POST /saves` returns success with `{url, platform, source_app, captured_at, user_context}` without calling the network and without waiting on the pipeline.
- One note per save, Obsidian-like: fact-only frontmatter + Markdown body; Markdown is the **source of truth** (ADR 0005).
- `kind: video | article | unknown` with capability flags; degraded saves render **normally** with a "transcript unavailable" chip — never an error page.
- Processing shown in the Inbox as streamed stages `queued → extracting → transcribing → analyzing → sorting → ready`.
- One suggested folder + one confidence per save; auto-file is **undoable and visible**; below-threshold saves queue for review.
- Match reasons, matched fragments, and jump targets on every search result. Citations on every Ask answer.
- Folders own one thing each: depth ≤ 3, one folder per save. Tags are flat labels, many per save.
- Settings show **"Chat model: Cloud | Local"** (+ local model picker) and a split storage row (`Library 4 MB · Local model 1.1 GB`); one honest offline line under the toggle.
- The device keeps a **complete replica**; sync is server-authoritative with queued, idempotent offline writes.
- Note generation runs in the **cloud, always**; embeddings and search run **locally, always**.

## 3. Hard no

**Media & extraction**
- Never persist audio or video — no files, no cache dir left dirty, temp files scrubbed even on failure (ADR 0004).
- Never turn this into a media manager or player app.
- Never route ASR or text through a provider tier that trains on user content. **Meta's contributor pricing tier is a hard no** — pay the regular rate or fall back locally.
- Never ship a scraper that works only by spoofing/attacking platforms; for fragile platforms (Instagram/TikTok/Facebook: cookies, datacenter-IP blocks) document the risk and keep the fallback ladder (ADR 0003). Respect robots-as-intended and platform ToS where they bind us.

**Organization**
- No auto-created folders, ever. Every folder comes from a user action or an accepted suggestion.
- No `Other` / `Misc` / `Unsorted` folder — the Inbox is already that state, and it empties itself.
- A save belongs to **zero or one** folder. No multi-parent.
- No topic tags. If a tag would fit more than a third of the library, it is a facet, not a tag.
- `kind` is a pipeline selector; it must never surface as an organizing axis in the UI.
- Depth ≤ 3 and ~25 folders before the UI proposes merges. **Reason to keep these limits: folder renames are bulk frontmatter rewrites because Markdown is the truth** — shallow and few keeps renames cheap. Do not remove the limits without renaming the cost.

**AI honesty**
- Don't name a toggle "AI model" — a toggle that changes one of three AI stages is a lie. It's "Chat model".
- Don't claim offline features that need the network: notes/transcription/extraction are cloud; offline means read/search/local-chat only.
- Don't show Local chat without the *"running on device · slower"* hint when it's actually slow, and don't hide first-use model downloads behind an invisible state.
- Don't rely on virtual RAM (RAM Plus/swap) for model capacity — paging weights makes it worse (ADR 0008).

**Stack**
- No Flutter in the hackathon build — Flet is the UI decision (ADR 0001).
- No Ollama or other external daemon for local chat — the local model must run **in-process** (`llama_cpp_python`).
- No GPU/NPU paths in the MVP — the demo device is MediaTek; there is no llama.cpp Hexagon backend, and mid-range mobile Vulkan is benchmarked slower than CPU (ADR 0008).
- No Agent-Reach, ScrapeGraphAI, or telemetry-first libraries as dependencies (ADR 0007); Crawl4AI is allowed only as an optional tier-1.5 slot.
- No new tabs beyond the proto v2 **4-tab** layout (Inbox · Folders · Search · Settings) without a real user need grilled first.
- No resume surfaces anywhere — the feature is deleted (product, schema, prototype); its absence is a product decision, not a bug.

## 4. What to use

- `PrototypingFiles/Claybank_ Interactive Workflow v2.html` as UI truth for flows; `Claybank App Wireframes.html` for Flet widget intent.
- The contract in `Docs/api/` as the single enum/field source; fixtures + `test_contract.py` must stay green before any feature that touches the contract.
- `GLOSSARY.md` terms, defined before first use; if the term is missing, define it there, not ad hoc.
- Markdown for notes; SQLite + FTS5 + faiss for the index; `multilingual-e5-small` (384-dim) for embeddings, pinned in `index_meta`.

## 5. Error handling

- Fetch fails → save stays in the Inbox with a visible error state; never a silent drop.
- Transcription/sort fails → the save survives with whatever metadata exists; the note is editable.
- Agent (tier 2, later) fails or overruns caps → degrade to `unknown`; never partial-write (ADR 0002).
- Sync conflict → `409`, banner in the app, user's edit survives, server version preserved for recovery. No silent overwrite.
- AI sort off/unavailable → save remains in Inbox, editable, unfiled; review queue is skippable forever and never becomes debt.
- Notification spike fails → paste sheet demo unaffected; mark the notification row spike-gated, don't slip the scope silently.

## 6. Boundaries for the agent

- Update `PRD.md`, `Architecture.md`, `Phases.md`, `Design.md`, and `Memory.md` together when a decision changes; a one-doc change is a bug in the docs.
- When unsure about product meaning, ask/grill rather than assume; when unsure about a term, check or extend the glossary before using it.
- Keep phases testable against prototype v2 screens (`Phases.md`); each phase has a demoable outcome.
- Keep ADRs updated when a decision they record actually changes; add dated corrections to `Memory.md`'s decision list instead of silently rewriting history.

## 7. Definition of done for a phase

- The screens and flows in the phase match prototype v2.
- The note model, job states, and folder model stay consistent with `DataModel.md` and `Architecture.md`.
- "Text only, never save videos" still holds.
- The contract test is green (fixtures valid against schemas; `contract_version` bumped only deliberately).
- `Memory.md` records what shipped and what's next.

## 8. Python code standards

Style is a contract too. Write for the next reader (usually the next grilling session or a cold reviewer from the remote submission), not for the interpreter.

**Baseline**
- **PEP 8**, mechanically: 4-space indents, ≤ 100 cols, `snake_case` functions/vars, `PascalCase` classes, `UPPER_CASE` constants, one import per line grouped stdlib → third-party → local. Enforced by tooling (`ruff check` + `ruff format`), never argued by hand.
- **PEP 257** docstrings: every module, public class, and public function carries one. One imperative line for the what; more only when the *why* isn't obvious. Google-style sections (`Args:`/`Returns:`/`Raises:`) when there are args worth naming.
- **PEP 20** (Zen): added value without being cited — refuse clever; prefer flat over nested; prefer one obvious way.

**Typing (PEP 484 / PEP 544 modern style)**
- Full annotations on every public function signature; module level via `from __future__ import annotations` (as `generate_fixtures.py` already does).
- PEP 604 unions only as `str | None`, never `Optional[str]`; built-in generics `list[int]`, not `typing.List`.
- Responsive to the tooling, not ceremonial: run `pyright`/`mypy` in CI; no blanket `type: ignore` — one precise ignore line + a comment, or a `typing.cast` for genuinely dynamic boundaries.
- **Contract boundary rule:** Pydantic request/response models must be *derived from* `Docs/api/schemas/*.json` — never an independent hand-retype. Any drift fails with the contract test (consider codegen, or a conformance test instantiating every model against its schema's fixtures).
- `typing.Protocol` for the seams that matter (`ExtractionProvider`, `ASRProvider`, `ChatProvider`, `EmbeddingBackend`) so providers stay swappable without inheritance; concrete classes stay concrete — helpers first, classes only when stateful.

**Async**
- FastAPI handlers, Flet event handlers, and anything I/O-bound on HTTP/DB/model APIs are `async def`; do not block the event loop — no `time.sleep`, `httpx` (not `requests`), `sqlite` behind the executor or `aiosqlite`.
- Prefer `asyncio.TaskGroup` over bare `gather` for fan-out; timeouts on every await of external services (`asr_unavailable`, `llm_unavailable` are the honest outcomes of a timeout, not exceptions leaked to the UI).

**Idioms**
- `pathlib.Path` for everything filesystem; `enum.StrEnum` for the locked vocabularies (`kind`, `job.state`, `error.code`, `match_reason`) — single definitions imported everywhere; never strings in comparisons at use sites.
- f-strings, pure data with `dataclass(frozen=True, slots=True)` where types are passed around, generators/lazy iterables over list building when sizes can grow, `contextlib.suppress`/`with` blocks with explicit cleanup — and the rule that **transient media cleanup happens in `finally`/context exits even on failure paths** (ADR 0004 is a code-level rule, not a GC hope).
- `match`/`case` allowed for kind-dispatch pipelines only; if-elif is fine elsewhere.
- Exceptions: domain-specific classes grouped in one module, raised at the boundary that knows the code, mapped to `error.code`s in exactly one place (the handler); **bare `except` and blanket-retry are forbidden** — a caught error either repairs, converts to a typed error, or re-raises.
- Logging via `logging` (module-level `log = logging.getLogger(__name__)`), never `print` in non-CLI code; no logging of transcript bodies or user content in full.

**Project hygiene (PEP 621 / conventions)**
- Metadata and deps in `pyproject.toml` only; pinned (`==`) for runtime reproducibility, ranged for dev tools; extras for test stacks; no requirements-untracked installs.
- Modules: `app/` (FastAPI), `client/` (Flet), `pipeline/`, `search/`, `sync/`, `contracts/` (generated/derived from `Docs/api/schemas`), tests mirroring that layout. No shared mutable singletons; config via `os.environ`/pydantic-settings, secrets never in code or fixtures.
- Tests: `pytest`-compatible, but every suite must also stay runnable plain (`python .../test_*.py`) as the DB/contract tests already are; in-memory SQLite over fixtures-with-side-effects; tests never touch the network (mock providers, never real ASR/LLM).

**Flet specifics**
- One `ft.Service` per capability (as `flet-android-notifications` does); UI code never imports pipeline internals directly — it calls the client use-case layer that owns the calls.
- No `page.update()` per cell in loops: batch updates; heavy work off the UI path with staged states shown in the UI (matching the streamed `job.state` flow).
- Handlers that replay real user intent (file/ignore/move/undo) must be idempotent-in-UI and re-dispatchable — same rule as the `Idempotency-Key` contract.
