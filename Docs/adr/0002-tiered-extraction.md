# ADR 0002 — Tiered extraction: deterministic first, agent rescue gated

**Status:** Accepted (tier 2 deferred post-hackathon; interface implemented) · **Date:** 2026-10-31

## Context

Every save must eventually become a note with enough fields for search and Ask, but extraction quality varies wildly by platform: YouTube is deeply indexable, an Instagram reel may yield only a page title, some sites block anything. A pipeline must be **fast and cheap on the common path** and **expensive only on the rare path**, without ever producing a half-written note.

## Decision

Two tiers, one output contract (`api/schemas/extraction-result.json`):

**Tier 1 — deterministic.** `yt-dlp` for video (metadata + auto-captions when available), `trafilatura` for articles. No LLM, no agent, no cap beyond the job budget (30 s target / 2 min cap).

**Tier 2 — agent rescue.** Runs **only when** the extraction result is missing *every field required for its kind*:

| kind | fires when |
|---|---|
| `video` | no title **and** no transcript |
| `article` | no body |
| `unknown` | no title and no body |

Optional fields (duration, author, published, images) never trigger it — "we got a title but no transcript" is a **successful tier-1 save**, not a rescue case.

**Caps: 5 tool calls, 45 s.** Tier 2 emits the *same* `ExtractionResult` schema, so downstream stages can't tell which tier produced a field. If it fails or overruns, the save degrades to `unknown` — a **partial write is never allowed**. The agent's steps are kept on the job as `agent_trace`, which is excluded from sync payloads.

## Rejected alternatives

- **Everything through an agent:** expensive, slow, and nondeterministic on a path that runs per-save — violates the processing budget.
- **Partial commit:** a note with a title but no timestamp/anchor breaks match reasons and Ask citations; better to land in `unknown` and degrade in the UI.
- **Parallel tier 2 on every save:** doubles cost and API load of exactly the scrapes most likely to be blocked.

## Consequences

- The pipeline code burns nothing on the common path.
- Review queue and "degraded saves render normally" absorb tier-1 gaps; the agent only chases total failures.
- The hackathon ships tier 1 + the tier-2 *interface* so the deferred build is a drop-in (`Phases.md`, post-hackathon item 2).
