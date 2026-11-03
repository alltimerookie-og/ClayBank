# ADR 0005 — Markdown is the source of truth

**Status:** Accepted · **Date:** 2026-10-31

## Context

Every save carries one note. Three storage shapes were possible: DB-first rows with a rendered markdown export, markdown files with a DB index, or markdown-as-truth with derived indexes. The prototype's item view is already rendered Markdown ("like Obsidian"), with a properties block, headings, checkboxes and a transcript — and the product wants portability and user ownership of notes.

## Decision

**The note's Markdown file content is authoritative.** Frontmatter holds *stable facts only*:

```yaml
source, channel, video_url, duration, published, saved, folder, tags
```

Confidence, suggested folder, and processing state are **API metadata on the save/job — never frontmatter**. A user deleting a frontmatter line must never be able to break the review queue or a job.

- On write, the note is parsed to rebuild the derived indexes: FTS5 row, section index (heading → anchor, for match reasons and jump targets), and the embedding input (`title + overview + key points + transcript excerpt`).
- LLM **generation creates** the note's body sections (Overview, Key points, Links guaranteed; others dynamic); system code writes the **frontmatter facts**; the user may edit or delete anything afterward.
- **Reprocessing never modifies the note body.** A re-run updates metadata, transcript and folder suggestion; regenerating body text is a separate, explicit action.
- Folder **renames are bulk frontmatter rewrites** over member notes. That cost is accepted and is the recorded reason the folder model is shallow (depth ≤ 3) and small (~25 folders) — write this reasoning next to the limits so no future agent "helpfully" removes them.
- Machine state in the *API*, stable facts in the *document*: each layer owns exactly one kind of truth.

## Consequences

- Portability for free: "export library as a folder tree of `.md` files" is a day-one feature; anyone can take their notes into Obsidian.
- The product divergence risk moves into the parser: the note must survive user edits (sections, ordering, missing properties). Parsers tolerate missing sections; renderers fall back to the raw markdown view.
- Vectors and FTS5 are caches over the note — losing them is an inconvenience, not data loss (`index_meta` guards model/dim mismatch; rebuild is always possible from the replica).
