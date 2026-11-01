# ADR 0003 — Content acquisition: legality and the fragile-platforms ladder

**Status:** Accepted · **Date:** 2026-10-31

## Context

Claybank saves links from Instagram, Facebook, TikTok, YouTube (public content) and arbitrary websites, then extracts text (metadata/transcript/article body) from what the platform serves. Acquisition must be legal, respectful of platforms, and honest about failure.

## Facts researched (2026-10)

- **Instagram oEmbed** works tokenless (since May 2026) but returns **embed HTML only** — no caption text.
- **Instagram Graph API** reads only *your own* media — there is no sanctioned route to another creator's reel caption.
- **Instagram/TikTok/Facebook scraping is fragile by design:** guest sessions need cookies, blocks datacenter IPs, and breaks quietly when the platform rotates its private API.

## Decision — ordered fallback ladder, same for every platform

1. **But first: what the user already gives us.** The share/paste target hands over the URL as selected text; capture (`POST /saves`) needs nothing from the network.
2. **Official surface when available** — YouTube metadata + auto-captions via `yt-dlp` (public data served under ToS); oEmbed HTML for platforms that provide it.
3. **Tier-1 libraries** (`yt-dlp` / `trafilatura`) for the general web.
4. **Documented degraded mode.** If a fragile platform blocks extraction, the save stays `unknown`/title-only in the UI — never a silent failure, never a workaround ("pretend to be the app", rotate proxies).

**Non-negotiables:** no bypassing of access controls; no spoofing someone else's session; no heavy scraping of a platform's private endpoints; no wholesale caption harvesting at scale. Claybank is a *personal* tool processing a user's *own saves* — keep it at personal-tool etiquette.

**Named migration path for the fragile three:** (a) watch for official APIs (the Instagram Graph/Creator surfaces for *your own* media), and (b) **user-side capture** — the user shares/copies what they already see; Claybank stores what the user hands it plus metadata from public surfaces. Both are recorded in `Phases.md`.

## Rejected alternatives

- **Agent-Reach as a dependency** — see `adr/0007` (its *pattern* was adopted, not its code).
- **Headless-browser session copying** to mimic logged-in apps — brittle, ToS-hostile, and maintenance-heavy; not acceptable in a personal privacy product.
- **Paid scraping proxies** — moves legal risk into a product that has no model supporting it.

## Consequences

- Extraction reliability varies by platform by design; `Rules.md` §5 and the job model treat that as a first-class degraded state, not a bug.
- Privacy banner stays true: what leaves the device is the URL (to fetch public data) and transcript/meta (to cloud AI) — never the media.
