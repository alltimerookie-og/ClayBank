"""Markdown note synthesis, frontmatter serialization, and section indexing (ADR 0005, DataModel.md §2.4)."""
from __future__ import annotations

import json
import re
import unicodedata
from typing import Any

from backend.contracts.ids import now_iso_z
from backend.llm.models import LinkItem, NoteStructuredOutput

_FRONTMATTER_PATTERN = re.compile(r"^---\s*\n(.*?)\n---\s*(?:\n|$)", re.DOTALL)
_HEADING_PATTERN = re.compile(r"^(#{1,6})\s+(.+)$", re.MULTILINE)
_TIMESTAMP_PATTERN = re.compile(r"^\d{1,2}:\d{2}(?::\d{2})?$")


def slugify_heading(heading: str) -> str:
    """Generate a clean, deterministic anchor slug from a heading string.

    Preserves timestamps (e.g. '0:42' or '01:23:45') as clean anchors.
    Normalizes unicode, lowercases, and replaces non-alphanumerics with hyphens.

    Args:
        heading: Raw heading text.

    Returns:
        str: Normalized anchor slug.
    """
    cleaned = heading.strip()
    if _TIMESTAMP_PATTERN.match(cleaned):
        return cleaned

    # Normalize unicode characters
    normalized = unicodedata.normalize("NFKD", cleaned)
    ascii_text = normalized.encode("ascii", "ignore").decode("ascii")

    # Lowercase and replace non-alphanumeric with hyphens
    slug = re.sub(r"[^\w\s-]", "", ascii_text.lower())
    slug = re.sub(r"[\s_-]+", "-", slug).strip("-")
    return slug or "section"


def parse_markdown_headings(markdown: str) -> list[dict[str, Any]]:
    """Parse all Markdown headings from body into structured section entries.

    Deduplicates identical anchors with numeric suffixes (-1, -2).

    Args:
        markdown: Raw markdown document text.

    Returns:
        list[dict[str, Any]]: List of dicts with 'heading', 'anchor', and 'seq'.
    """
    sections: list[dict[str, Any]] = []
    seen_anchors: dict[str, int] = {}
    seq = 1

    # Strip frontmatter before parsing headings
    body = re.sub(_FRONTMATTER_PATTERN, "", markdown)

    for match in _HEADING_PATTERN.finditer(body):
        _level_hashes, raw_heading = match.groups()
        heading_text = raw_heading.strip()
        if not heading_text:
            continue

        base_slug = slugify_heading(heading_text)
        if base_slug in seen_anchors:
            seen_anchors[base_slug] += 1
            anchor = f"{base_slug}-{seen_anchors[base_slug]}"
        else:
            seen_anchors[base_slug] = 0
            anchor = base_slug

        sections.append({
            "heading": heading_text,
            "anchor": anchor,
            "seq": seq,
        })
        seq += 1

    return sections


def build_frontmatter_yaml(facts: dict[str, Any]) -> str:
    """Serialize stable frontmatter facts to strict YAML without external dependencies.

    Only stable facts are permitted per ADR 0005:
    source, channel, video_url, duration, published, saved, folder, tags.

    Args:
        facts: Dictionary of stable facts.

    Returns:
        str: Formatted YAML frontmatter block enclosed in --- delimiters.
    """
    lines: list[str] = ["---"]

    # Allowed stable fields strictly ordered
    keys = ("source", "channel", "video_url", "duration", "published", "saved", "folder", "tags")

    for k in keys:
        v = facts.get(k)
        if k == "tags":
            tags_list = v if isinstance(v, list) else []
            if tags_list:
                lines.append("tags:")
                for tag in tags_list:
                    tag_clean = str(tag).strip()
                    lines.append(f"  - {json.dumps(tag_clean)}")
            else:
                lines.append("tags: []")
        elif v is None:
            lines.append(f"{k}: null")
        elif isinstance(v, (int, float)):
            lines.append(f"{k}: {int(v)}")
        elif isinstance(v, bool):
            lines.append(f"{k}: {'true' if v else 'false'}")
        else:
            s_val = str(v).strip()
            # Quote strings safely if they contain special YAML characters
            if any(ch in s_val for ch in (":", "#", "[", "]", "{", "}", "\n", "\"", "'")) or s_val == "":
                lines.append(f"{k}: {json.dumps(s_val)}")
            else:
                lines.append(f"{k}: {s_val}")

    lines.append("---\n")
    return "\n".join(lines)


def parse_frontmatter(markdown: str) -> tuple[dict[str, Any], str]:
    """Extract frontmatter facts dictionary and remaining Markdown body.

    Tolerates missing frontmatter, deleted fields, or corrupted YAML.

    Args:
        markdown: Raw note markdown text.

    Returns:
        tuple[dict[str, Any], str]: (facts_dict, markdown_body).
    """
    if not markdown or not isinstance(markdown, str):
        return {}, ""

    match = _FRONTMATTER_PATTERN.match(markdown)
    if not match:
        return {}, markdown.strip()

    raw_yaml = match.group(1)
    body = markdown[match.end():].strip()

    facts: dict[str, Any] = {
        "source": None,
        "channel": None,
        "video_url": None,
        "duration": None,
        "published": None,
        "saved": None,
        "folder": None,
        "tags": [],
    }

    current_list_key: str | None = None

    for line in raw_yaml.splitlines():
        line_stripped = line.strip()
        if not line_stripped or line_stripped.startswith("#"):
            continue

        if line_stripped.startswith("- ") and current_list_key == "tags":
            item = line_stripped[2:].strip().strip("\"'")
            if item:
                facts["tags"].append(item)
            continue

        current_list_key = None
        if ":" in line_stripped:
            key, val = line_stripped.split(":", 1)
            key_clean = key.strip()
            val_clean = val.strip()

            if key_clean == "tags":
                current_list_key = "tags"
                if val_clean and val_clean != "[]":
                    # Handle inline array syntax e.g. [tag1, tag2]
                    try:
                        parsed_arr = json.loads(val_clean)
                        if isinstance(parsed_arr, list):
                            facts["tags"] = [str(t).strip() for t in parsed_arr if str(t).strip()]
                    except Exception:
                        pass
                continue

            if key_clean in facts:
                if val_clean.lower() in ("null", "~", ""):
                    facts[key_clean] = None
                elif key_clean == "duration":
                    try:
                        facts[key_clean] = int(val_clean)
                    except ValueError:
                        facts[key_clean] = None
                else:
                    # Strip surrounding quotes if present
                    if (val_clean.startswith('"') and val_clean.endswith('"')) or (
                        val_clean.startswith("'") and val_clean.endswith("'")
                    ):
                        facts[key_clean] = val_clean[1:-1]
                    else:
                        facts[key_clean] = val_clean

    return facts, body


def generate_note_markdown(
    title: str,
    facts: dict[str, Any],
    structured: NoteStructuredOutput | None = None,
    transcript: str | None = None,
    raw_body: str | None = None,
) -> str:
    """Synthesize complete Markdown note adhering to ADR 0005.

    Structure:
    1. YAML frontmatter facts
    2. # Title
    3. ## Overview (guaranteed)
    4. ## Key points (guaranteed)
    5. ## Links mentioned (guaranteed)
    6. ## Transcript excerpt (optional if transcript exists)

    Args:
        title: Title of the save.
        facts: Stable frontmatter facts.
        structured: Optional structured output from LLM provider.
        transcript: Optional full spoken transcript.
        raw_body: Optional fallback body text if LLM generation failed.

    Returns:
        str: Formatted Markdown document.
    """
    frontmatter = build_frontmatter_yaml(facts)
    clean_title = re.sub(r"\s+", " ", title).strip() if title else "Untitled Save"

    parts: list[str] = [
        frontmatter,
        f"# {clean_title}\n",
    ]

    if structured is not None:
        # 1. Overview
        parts.append("## Overview\n")
        parts.append(structured.overview.strip() + "\n")

        # 2. Key points
        parts.append("## Key points\n")
        for point in structured.key_points:
            parts.append(f"- {point.strip()}")
        parts.append("")

        # 3. Links mentioned
        parts.append("## Links mentioned\n")
        if structured.links:
            for link in structured.links:
                target_hint = f" ({link.jump_target})" if link.jump_target else ""
                parts.append(f"- [{link.anchor_text}]({link.url}){target_hint}")
        else:
            parts.append("_No external links mentioned._")
        parts.append("")

    elif raw_body and raw_body.strip():
        # Fallback body (e.g. degraded note with extracted article body)
        parts.append("## Overview\n")
        parts.append("_Note overview generation unavailable._\n")
        parts.append("## Key points\n")
        parts.append("- _Overview unavailable_\n")
        parts.append("## Links mentioned\n")
        parts.append("_No external links mentioned._\n")
        parts.append("## Content\n")
        parts.append(raw_body.strip() + "\n")

    else:
        # Minimal degraded note shell
        parts.append("## Overview\n")
        parts.append("_Transcript and content summary unavailable._\n")
        parts.append("## Key points\n")
        parts.append("- _Content summary unavailable_\n")
        parts.append("## Links mentioned\n")
        parts.append("_No external links mentioned._\n")

    # 4. Optional transcript excerpt (first ~1,200 chars if transcript is available)
    if transcript and transcript.strip():
        parts.append("## Transcript excerpt\n")
        excerpt = transcript.strip()
        if len(excerpt) > 1200:
            excerpt = excerpt[:1200].rsplit(" ", 1)[0] + " …"
        parts.append(f"> {excerpt}\n")

    return "\n".join(parts)


def execute_note_persistence_transaction(
    conn: Any,
    save_id: str,
    markdown: str,
    overview: str | None = None,
    key_points: list[str] | None = None,
    links: list[dict[str, Any]] | None = None,
    transcript: str | None = None,
    now: str | None = None,
) -> None:
    """Execute synchronous atomic SQLite write-through for a note and its section index.

    Updates notes row and rebuilds note_sections. Triggers automatically update notes_fts.

    Args:
        conn: Open sqlite3.Connection with active transaction.
        save_id: UUID string of the save.
        markdown: Complete Markdown note text.
        overview: Optional summary text.
        key_points: Optional list of bullet key points.
        links: Optional list of structured links.
        transcript: Optional full transcript text.
        now: Optional ISO-8601 UTC timestamp.
    """
    ts = now or now_iso_z()
    facts, _body = parse_frontmatter(markdown)
    sections = parse_markdown_headings(markdown)

    # Encode JSON columns safely
    tags_json = json.dumps(facts.get("tags") or [])
    kp_json = json.dumps(key_points) if key_points is not None else None
    links_json = json.dumps(links) if links is not None else None

    # Upsert notes table
    conn.execute(
        """
        INSERT INTO notes(
            save_id, markdown, source, channel, video_url, duration,
            published, saved_date, folder_path, tags_json, overview,
            key_points_json, links_json, transcript, created_at, updated_at
        ) VALUES (
            ?, ?, ?, ?, ?, ?,
            ?, ?, ?, ?, ?,
            ?, ?, ?, ?, ?
        )
        ON CONFLICT(save_id) DO UPDATE SET
            markdown = excluded.markdown,
            source = COALESCE(excluded.source, notes.source),
            channel = COALESCE(excluded.channel, notes.channel),
            video_url = COALESCE(excluded.video_url, notes.video_url),
            duration = COALESCE(excluded.duration, notes.duration),
            published = COALESCE(excluded.published, notes.published),
            saved_date = COALESCE(excluded.saved_date, notes.saved_date),
            folder_path = COALESCE(excluded.folder_path, notes.folder_path),
            tags_json = excluded.tags_json,
            overview = COALESCE(excluded.overview, notes.overview),
            key_points_json = COALESCE(excluded.key_points_json, notes.key_points_json),
            links_json = COALESCE(excluded.links_json, notes.links_json),
            transcript = COALESCE(excluded.transcript, notes.transcript),
            updated_at = excluded.updated_at
        """,
        (
            save_id,
            markdown,
            facts.get("source"),
            facts.get("channel"),
            facts.get("video_url"),
            facts.get("duration"),
            facts.get("published"),
            facts.get("saved"),
            facts.get("folder"),
            tags_json,
            overview,
            kp_json,
            links_json,
            transcript,
            ts,
            ts,
        ),
    )

    # Rebuild note_sections index atomically
    conn.execute("DELETE FROM note_sections WHERE save_id=?", (save_id,))
    for sec in sections:
        conn.execute(
            "INSERT INTO note_sections(save_id, heading, anchor, seq) VALUES (?, ?, ?, ?)",
            (save_id, sec["heading"], sec["anchor"], sec["seq"]),
        )
