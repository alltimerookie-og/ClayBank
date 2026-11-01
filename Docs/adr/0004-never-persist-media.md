# ADR 0004 — Never persist media

**Status:** Accepted · **Date:** 2026-10-31

## Context

The prototype states the product line outright: **"videos are never saved. Cloud AI gets the transcript and metadata only."** That line is a *product decision*, not an implementation detail — it is the difference between "a bookmarking app that summarizes" and "a private media library". But transcription and Ask both need audio content at some moment. The architecture has to be built so that the promise survives implementation.

## Decision

Media (audio or video streams) may be fetched, processed, and then **transiently discarded — never persisted**, anywhere in the stack, at any tier:

- no blob column in either the server store or the device replica (`DataModel.md` invariant 7);
- no media cache directories that outlive a request;
- temp files scrubbed on success **and on failure** — a crashed job leaves nothing behind;
- transcription is duration-capped (10-minute media cap), partly to bound how long a stream is held in memory/temp at all.

**What is kept:** transcript text, timestamps, metadata, note Markdown. Text *is* the product's material; media is never the product's material.

## Consequences

- The privacy banner in Settings ("Cloud AI gets the transcript and metadata only") stays literally true.
- Transcription is re-runnable but costs money per run (Muse Voice Transcribe ~$0.18/h); that's an accepted trade against storage and the product's own line.
- Re-doing work is genuinely costly: without media on disk, re-extraction always re-fetches. That is the accepted trade against storage and the product's own line. If a future feature needs media (e.g. audio clip sharing), this ADR is the one to change — per `Rules.md`, change these docs together, not just this one.
