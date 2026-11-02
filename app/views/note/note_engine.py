"""Frontmatter parser and Markdown partitioning engine for ClayBank Item Notes.

Handles extracting stable system facts from YAML frontmatter, formatting facts for
display in the PropertiesGrid, splitting markdown into jump-target blocks, and
safely updating frontmatter values.

Derived from Docs/adr/0005-markdown-as-source-of-truth.md, Docs/api/schemas/note.json,
and Docs/UIUX.md §6.
"""

from __future__ import annotations

import re
from typing import Any
import yaml

# Standard frontmatter keys defined in DataModel.md and note.json
KNOWN_FRONTMATTER_KEYS = {
    "source",
    "channel",
    "video_url",
    "duration",
    "published",
    "saved",
    "folder",
    "tags",
}

# Regex to detect YAML frontmatter block
_FRONTMATTER_RE = re.compile(r"^---\r?\n(.*?)\r?\n---\r?\n(.*)$", re.DOTALL)
# Regex to match timestamp in text or blockquote (e.g., "0:42", "1:23:45")
_TIMESTAMP_RE = re.compile(r"\b(\d{1,2}:\d{2}(?::\d{2})?)\b")
# Regex for heading lines (e.g. "## Key points")
_HEADING_RE = re.compile(r"^(#{1,6})\s+(.+)$")


def format_duration(seconds: int | float | str | None) -> str:
    """Format duration into human-readable mm:ss or hh:mm:ss.

    Args:
        seconds: Numeric seconds or preformatted duration string.

    Returns:
        Formatted string (e.g. '0:58', '1:23:45') or empty string if None.
    """
    if seconds is None:
        return ""
    if isinstance(seconds, str):
        seconds = seconds.strip()
        if ":" in seconds:
            return seconds
        try:
            total_sec = int(float(seconds))
        except ValueError:
            return seconds
    else:
        total_sec = int(seconds)

    if total_sec < 0:
        return "0:00"

    h = total_sec // 3600
    m = (total_sec % 3600) // 60
    s = total_sec % 60

    if h > 0:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m}:{s:02d}"


def normalize_tags(raw_tags: Any) -> list[str]:
    """Normalize raw tags data into a clean list of string tags without '#' prefix.

    Args:
        raw_tags: List of strings or scalar string representation.

    Returns:
        List of trimmed tag strings without leading '#'.
    """
    if raw_tags is None:
        return []
    if isinstance(raw_tags, list):
        clean_tags: list[str] = []
        for tag in raw_tags:
            tag_str = str(tag).strip()
            if tag_str.startswith("#"):
                tag_str = tag_str.lstrip("#").strip()
            if tag_str and tag_str not in clean_tags:
                clean_tags.append(tag_str)
        return clean_tags
    if isinstance(raw_tags, str):
        # Handle string like "#recipe #pasta #dinner" or "recipe, pasta"
        tokens = re.split(r"[,\s]+", raw_tags.strip())
        clean_tags = []
        for t in tokens:
            cleaned = t.lstrip("#").strip()
            if cleaned and cleaned not in clean_tags:
                clean_tags.append(cleaned)
        return clean_tags
    return [str(raw_tags).strip()]


class FrontmatterParser:
    """Parser and serializer for Obsidian-like Markdown notes with YAML frontmatter."""

    @classmethod
    def parse(cls, raw_text: str) -> tuple[dict[str, Any], str]:
        """Parse raw note text into frontmatter dictionary and clean markdown body.

        Args:
            raw_text: Full note text starting with '---' or plain markdown.

        Returns:
            Tuple of (frontmatter_dict, clean_body_markdown).
        """
        if not raw_text or not raw_text.strip():
            return {}, ""

        match = _FRONTMATTER_RE.match(raw_text.strip())
        if not match:
            return {}, raw_text.strip()

        yaml_content = match.group(1)
        body_content = match.group(2).strip()

        frontmatter: dict[str, Any] = {}
        try:
            loaded = yaml.safe_load(yaml_content)
            if isinstance(loaded, dict):
                frontmatter = loaded
        except yaml.YAMLError:
            # Tolerant fallback: parse line-by-line using regex if user created invalid YAML
            frontmatter = cls._fallback_parse_yaml_lines(yaml_content)

        # Standardize known fields
        standardized: dict[str, Any] = {}
        for k, v in frontmatter.items():
            key = str(k).strip()
            if key == "tags":
                standardized["tags"] = normalize_tags(v)
            elif key == "duration" and v is not None:
                try:
                    standardized["duration"] = int(v)
                except (ValueError, TypeError):
                    standardized["duration"] = v
            else:
                standardized[key] = v

        if "tags" not in standardized:
            standardized["tags"] = []

        return standardized, body_content

    @staticmethod
    def _fallback_parse_yaml_lines(yaml_text: str) -> dict[str, Any]:
        """Tolerant regex line parser for malformed YAML frontmatter blocks."""
        result: dict[str, Any] = {}
        current_list_key: str | None = None

        for line in yaml_text.splitlines():
            line_str = line.rstrip()
            if not line_str or line_str.startswith("#"):
                continue

            # Check for list items under a key
            if line_str.lstrip().startswith("- ") and current_list_key:
                item_val = line_str.lstrip()[2:].strip()
                if not isinstance(result.get(current_list_key), list):
                    result[current_list_key] = []
                result[current_list_key].append(item_val)
                continue

            colon_idx = line_str.find(":")
            if colon_idx > 0:
                key = line_str[:colon_idx].strip()
                val = line_str[colon_idx + 1:].strip()
                if not val:
                    # Possible start of a list
                    current_list_key = key
                    result[key] = []
                else:
                    current_list_key = None
                    # Strip quotes if present
                    if (val.startswith('"') and val.endswith('"')) or (
                        val.startswith("'") and val.endswith("'")
                    ):
                        val = val[1:-1]
                    result[key] = val

        return result

    @classmethod
    def serialize(cls, frontmatter: dict[str, Any], body: str) -> str:
        """Serialize frontmatter dictionary and body into a complete Markdown document.

        Args:
            frontmatter: Facts dictionary.
            body: Clean markdown body without YAML boundaries.

        Returns:
            Full Markdown string with '---' delimited YAML frontmatter.
        """
        # Ensure ordered serialization of known keys first
        ordered_keys = [
            "source",
            "channel",
            "video_url",
            "duration",
            "published",
            "saved",
            "folder",
            "tags",
        ]
        doc_dict: dict[str, Any] = {}
        for key in ordered_keys:
            if key in frontmatter:
                doc_dict[key] = frontmatter[key]

        # Add any custom / extra fields
        for key, val in frontmatter.items():
            if key not in doc_dict:
                doc_dict[key] = val

        yaml_str = yaml.dump(
            doc_dict,
            default_flow_style=False,
            allow_unicode=True,
            sort_keys=False,
        ).strip()

        return f"---\n{yaml_str}\n---\n\n{body.strip()}"

    @classmethod
    def update_field(cls, raw_markdown: str, key: str, value: Any) -> str:
        """Update a single frontmatter field while preserving document integrity."""
        fm, body = cls.parse(raw_markdown)
        fm[key] = value
        return cls.serialize(fm, body)


class NoteBlock:
    """Represents a discrete block within the Note Markdown body for targeted rendering."""

    def __init__(
        self,
        key: str,
        kind: str,
        content: str,
        anchor: str | None = None,
        timestamps: list[str] | None = None,
    ) -> None:
        self.key = key
        self.kind = kind  # "heading", "blockquote", "paragraph", "list"
        self.content = content
        self.anchor = anchor
        self.timestamps = timestamps or []

    def __repr__(self) -> str:
        return f"<NoteBlock key={self.key} kind={self.kind} anchor={self.anchor}>"


def slugify_anchor(title: str) -> str:
    """Convert heading text into a normalized anchor slug (e.g. 'Key points' -> 'key-points')."""
    text = title.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    return re.sub(r"[\s_-]+", "-", text).strip("-")


def split_markdown_into_blocks(body: str) -> list[NoteBlock]:
    """Split markdown body into discrete blocks for jump-target targeting and scrolling.

    Blocks are split primarily at headings and timestamped transcript blockquotes.

    Args:
        body: Clean markdown body without frontmatter.

    Returns:
        List of NoteBlock objects.
    """
    if not body or not body.strip():
        return []

    lines = body.strip().splitlines()
    blocks: list[NoteBlock] = []

    current_lines: list[str] = []
    current_kind = "paragraph"
    current_anchor: str | None = None
    current_timestamps: list[str] = []
    block_index = 0

    def flush_block() -> None:
        nonlocal current_lines, current_kind, current_anchor, current_timestamps, block_index
        if not current_lines:
            return
        content = "\n".join(current_lines).strip()
        if content:
            key = f"block-{block_index}"
            if current_anchor:
                key = f"heading-{current_anchor}"
            elif current_timestamps:
                key = f"timestamp-{current_timestamps[0].replace(':', '-')}"

            blocks.append(
                NoteBlock(
                    key=key,
                    kind=current_kind,
                    content=content,
                    anchor=current_anchor,
                    timestamps=list(current_timestamps),
                )
            )
            block_index += 1
        current_lines = []
        current_kind = "paragraph"
        current_anchor = None
        current_timestamps = []

    for line in lines:
        heading_match = _HEADING_RE.match(line)
        if heading_match:
            flush_block()
            h_text = heading_match.group(2).strip()
            anchor = slugify_anchor(h_text)
            blocks.append(
                NoteBlock(
                    key=f"heading-{anchor}",
                    kind="heading",
                    content=line,
                    anchor=anchor,
                )
            )
            block_index += 1
            continue

        if line.startswith(">"):
            # Transcript or blockquote line
            if current_kind != "blockquote" and current_lines:
                flush_block()
            current_kind = "blockquote"
            ts_matches = _TIMESTAMP_RE.findall(line)
            for ts in ts_matches:
                if ts not in current_timestamps:
                    current_timestamps.append(ts)
            current_lines.append(line)
        else:
            if current_kind == "blockquote" and current_lines:
                flush_block()
            current_kind = "paragraph"
            ts_matches = _TIMESTAMP_RE.findall(line)
            for ts in ts_matches:
                if ts not in current_timestamps:
                    current_timestamps.append(ts)
            current_lines.append(line)

    flush_block()
    return blocks


def find_jump_target_block_index(blocks: list[NoteBlock], target: str) -> int | None:
    """Find the index of the block matching a jump target (timestamp or heading anchor).

    Args:
        blocks: List of partitioned NoteBlocks.
        target: Target identifier (e.g. '0:42', '▶ 0:42', '#key-points', 'key-points').

    Returns:
        Index of matching block or None if not found.
    """
    if not target or not blocks:
        return None

    clean_target = target.strip()
    if clean_target.startswith("▶"):
        clean_target = clean_target.lstrip("▶").strip()
    if clean_target.startswith("#"):
        clean_target = clean_target.lstrip("#").strip()

    target_anchor = slugify_anchor(clean_target)

    # 1. Exact timestamp match
    for i, b in enumerate(blocks):
        for ts in b.timestamps:
            if ts == clean_target:
                return i

    # 2. Exact heading anchor match
    for i, b in enumerate(blocks):
        if b.anchor and b.anchor == target_anchor:
            return i

    # 3. Partial substring match in content or anchor
    for i, b in enumerate(blocks):
        if b.anchor and target_anchor in b.anchor:
            return i
        if clean_target in b.content:
            return i

    return None
