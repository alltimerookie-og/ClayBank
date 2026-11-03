# Backend developer instructions

You build the FastAPI + SQLite backend that the contract in `Docs/api/` already defines. Your product is **durable saves and a working pipeline**; the UI consumes it over the contract.

**Hard rule this file exists to serve:** capture always succeeds (`POST /saves` returns success in-process, without network calls and without waiting on the pipeline) — *Rules.md §2*. Everything else around it degrades, never blocks.

## Before the first endpoint

1. Read `Docs/api/README.md` (paths, schemas, error codes, fixture workflow), then `Docs/api/openapi.yaml` with `Docs/api/schemas/*.json` open beside it.
2. Run both suites from the repo root and confirm green:
   - `python Docs/api/test_contract.py`
   - `python Docs/db/test_schema.py`
3. Read `Docs/Rules.md` §5 (error handling) and §8 (Python code standards) — both are binding; §8 includes the contract-boundary rule below.
4. Apply the DB DDL as-is: `Docs/db/0001_core.sql` → `0002_server.sql` → `0003_device.sql` (shared SQLite; server additions live in 0002, device-only in 0003). Do not invent a migration layer the phases don't ask for.

## Step sequence (phases from `Docs/Phases.md`)

1. **Phase 1 — contract first:** scaffold `backend/` with the module layout of `Docs/Architecture.md` §5. Pydantic request/response models are **derived from** `Docs/api/schemas/*.json` (codegen or conformance-tested against every fixture) — hand-retyping the contract is a failure the contract test should catch. Seed user + `DEV_TOKEN` / `X-Device-Id` middleware (same bearer shape as the future JWT).
   *Done when:* both tests green; `POST /saves` succeeds in-process and replays under the same `Idempotency-Key`; duplicate → `409 already_saved` carrying the existing id unless `force=true`.
2. **Phase 3 — tier-1 extraction + transcription:** `yt-dlp` (video metadata/captions) and `trafilatura` (article body) onto one `ExtractionResult`; multimodal-only transcription (no local fallback); job states streamed `queued → extracting → transcribing → analyzing → sorting → ready`.
   *Done when:* a YouTube and an Instagram reel land with a transcript or a clear degraded state — never a partial write, never media persisted (temp files scrubbed in `finally` on every path, including failure).
3. **Phase 4 — note generation:** cloud-only LLM behind the provider Protocol, structured outputs guaranteeing Overview + Key points + Links; write-through updates FTS5/section index + `index_meta` in the same transaction boundary as the note.
   *Done when:* a fresh save produces a note matching the prototype's item note shape.
4. **Phase 5 — organization:** folder CRUD with depth ≤ 3 and one-folder-per-save enforced at API level; tags flat/unique/many; single `suggested_folder {path, confidence}`; cluster-then-propose on ≥3 similar unfiled saves.
   *Done when:* filing, undo, and review-queue states hold against `DataModel.md` invariants.
5. **Phase 6 — search + Ask:** FTS5 + faiss (384-dim, `query:`/`passage:` prefixed), reciprocal rank fusion, `index_meta` mismatch → refuse; match reason + matched fragment + jump target on every result; folder-scoped Ask responses carry **mandatory citations** per the `ask-answer` schema.
   *Done when:* searching a phrase spoken in a video returns the transcript hit with a timestamp jump target.
6. **Phase 7 — sync hardening:** server-authoritative cursor sync; stale writes → `409` + preserved server version; `agent_trace` never leaves the server.
   *Done when:* an offline write replays without duplicates on reconnect.

## Boundaries (short list — full set in `Docs/Rules.md` §3)

- One error mapping: domain exceptions raised where the code is known, mapped to `error.code`s in exactly one handler location.
- Async all the way through I/O: no blocking the event loop, timeouts on every external-service await.
- No provider tier that trains on user content; no telemetry-first dependencies; no new Python deps outside `pyproject.toml` without pinning + a row in `LICENSE` §Component Record.
- Tier-2 agent rescue (interface only in this build): fails or overruns caps → degrade to `unknown`; never partial-write.

## Standing checks

- Keep `contract_version` on every response (body sibling + `X-Contract-Version` header); reject stale explicit clients with `409 contract_version_mismatch`; bump only deliberately, and only with fixtures regenerated (`python Docs/api/generate_fixtures.py` — fixtures are never hand-edited).
- `contract_version` mismatch across README, schemas, and fixtures is a bug in the docs, not something the code works around.
