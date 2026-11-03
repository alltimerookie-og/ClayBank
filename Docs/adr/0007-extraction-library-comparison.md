# ADR 0007 — Extraction library comparison (why not Agent-Reach / ScrapeGraphAI / Crawl4AI)

**Status:** Accepted · **Date:** 2026-10-31
**Companion:** `adr/0002` (tiered extraction), `adr/0003` (acquisition legality)

## Context

Tier-1 extraction has to cover: YouTube (metadata + captions), Instagram/Facebook/TikTok reels (the hard three), and arbitrary article pages. We evaluated four candidate libraries before committing.

## Comparison

| Candidate | What it is | Why it was not adopted |
|---|---|---|
| **Agent-Reach** | "reach any API" toolkit (wraps other providers behind one CLI-ish surface) | Rejected as a dependency: CLI-subprocess shape, **browser-session copying** baked in (ToS-hostile for a privacy product, `adr/0003`), experimental Instagram support that can break weekly. Its *ordered-fallback pattern* is what we kept — see Decision. |
| **ScrapeGraphAI** | LLM-driven scraping graphs | Rejected: duplicates our formatting step (it re-formats what we already parse into `ExtractionResult`), and **telemetry is on by default** — the opposite of the privacy line. |
| **Crawl4AI** | web-crawler library with LLM hooks | Optional **tier-1.5 only** (deep sites needing JS render where trafilatura gives up); not a default. LLM hooks stay off. |
| **yt-dlp + trafilatura** | dedicated extractors per content kind | **Adopted**, as `adr/0002` tier 1: deterministic, maintained, pip-only, and each is the best-in-class tool for exactly one of our kinds. |

## Decision

1. **Tier 1 = `yt-dlp` + `trafilatura`** — the lowest-risk, best-maintained pair for video/article.
2. **Adopt Agent-Reach's architecture, not its code:** platform orderings live in config (fallback ladder per platform: official surface → oEmbed/embed HTML → tier-1 extract → degrade), so a platform that changes behavior is a config edit, not a code edit.
3. **Anything that needs a logged-in session or a headless browser** is out of the MVP and only reached via the post-hackathon path with its own ADR.
4. Crawl4AI may fill tier-1.5 later if a real evidence case appears (site where trafilatura fails and JS rendering fixes it) — with the ladder and budget unchanged.

## Consequences

- Extraction cover is honest: the fragile three will sometimes fail by design; `Rules.md` §5 and the review queue absorb that.
- No tool in the stack phones home by default; telemetry of any candidate library must be re-audited before adoption.
- The fallback ladder lives in config, giving each platform one file to edit instead of scattered conditionals.
