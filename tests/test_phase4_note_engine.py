"""Unit tests for P4-01: FrontmatterParser and Note Engine."""

from __future__ import annotations

import json
from pathlib import Path

from app.views.note.note_engine import (
    FrontmatterParser,
    find_jump_target_block_index,
    format_duration,
    normalize_tags,
    slugify_anchor,
    split_markdown_into_blocks,
)


def test_frontmatter_parser_valid_fixtures() -> None:
    """Verify parsing valid fixture markdown."""
    fixture_path = Path("Docs/api/fixtures/note.fixtures.json")
    assert fixture_path.exists()

    with fixture_path.open("r", encoding="utf-8") as f:
        data = json.load(f)

    valid_note = data["valid"][0]
    raw_md = valid_note["markdown"]

    fm, body = FrontmatterParser.parse(raw_md)

    assert fm["source"] == "Instagram"
    assert fm["channel"] == "@chefmara"
    assert fm["video_url"] == "instagram.com/reel/canonical_Cx9abc"
    assert fm["duration"] == 58
    assert fm["published"] == "2026-10-03"
    assert fm["saved"] == "2026-10-31"
    assert fm["folder"] == "Cooking / Pasta"
    assert fm["tags"] == ["recipe", "pasta", "dinner"]

    # Verify body is stripped of frontmatter
    assert not body.startswith("---")
    assert "# Creamy garlic pasta" in body
    assert "## Overview" in body


def test_frontmatter_parser_missing_frontmatter() -> None:
    """Verify raw markdown without frontmatter returns empty dict and intact body."""
    raw = "# Just a Title\n\nSome body text without YAML."
    fm, body = FrontmatterParser.parse(raw)

    assert fm == {}
    assert body == raw


def test_frontmatter_parser_empty_input() -> None:
    """Verify empty or whitespace strings return empty results."""
    fm, body = FrontmatterParser.parse("")
    assert fm == {}
    assert body == ""

    fm, body = FrontmatterParser.parse("   \n\n  ")
    assert fm == {}
    assert body == ""


def test_frontmatter_parser_missing_optional_fields() -> None:
    """Verify frontmatter with only some fields parses without error."""
    raw = """---
source: YouTube
video_url: https://youtube.com/watch?v=123
---
# Video Note
"""
    fm, body = FrontmatterParser.parse(raw)
    assert fm["source"] == "YouTube"
    assert fm["video_url"] == "https://youtube.com/watch?v=123"
    assert "channel" not in fm
    assert fm["tags"] == []
    assert body == "# Video Note"


def test_frontmatter_tags_normalization() -> None:
    """Verify tags normalization from list, space-separated string, or hashtag format."""
    # List of hashtags
    assert normalize_tags(["#recipe", " #pasta ", "#dinner"]) == ["recipe", "pasta", "dinner"]
    # Space-separated hashtag string
    assert normalize_tags("#recipe #pasta #dinner") == ["recipe", "pasta", "dinner"]
    # Comma-separated string
    assert normalize_tags("recipe, pasta, dinner") == ["recipe", "pasta", "dinner"]
    # None or empty
    assert normalize_tags(None) == []
    assert normalize_tags("") == []


def test_frontmatter_malformed_yaml_tolerant_fallback() -> None:
    """Verify malformed YAML syntax does not crash and extracts key-value pairs."""
    malformed = """---
source: Instagram
channel: @chefmara: invalid: yaml [unclosed
folder: Cooking / Pasta
tags:
  - recipe
  - pasta
---
# Tolerant Body
"""
    fm, body = FrontmatterParser.parse(malformed)
    assert fm["source"] == "Instagram"
    assert fm["folder"] == "Cooking / Pasta"
    assert "recipe" in fm.get("tags", [])
    assert body == "# Tolerant Body"


def test_frontmatter_serialization_and_round_trip() -> None:
    """Verify serializing frontmatter produces clean Markdown that parses back identically."""
    original_fm = {
        "source": "Instagram",
        "channel": "@chefmara",
        "video_url": "https://instagram.com/reel/123",
        "duration": 58,
        "published": "2026-10-03",
        "saved": "2026-10-31",
        "folder": "Cooking / Pasta",
        "tags": ["recipe", "pasta"],
    }
    body = "# Title\n\nContent paragraph."

    serialized = FrontmatterParser.serialize(original_fm, body)
    assert serialized.startswith("---\n")
    assert "---\n\n# Title" in serialized

    parsed_fm, parsed_body = FrontmatterParser.parse(serialized)
    assert parsed_fm["source"] == original_fm["source"]
    assert parsed_fm["channel"] == original_fm["channel"]
    assert parsed_fm["duration"] == original_fm["duration"]
    assert parsed_fm["folder"] == original_fm["folder"]
    assert parsed_fm["tags"] == original_fm["tags"]
    assert parsed_body == body


def test_frontmatter_update_field() -> None:
    """Verify updating a single field in a note document."""
    raw = """---
source: Instagram
folder: Cooking
tags:
  - food
---
# Content
"""
    updated = FrontmatterParser.update_field(raw, "folder", "Cooking / Pasta")
    fm, body = FrontmatterParser.parse(updated)
    assert fm["folder"] == "Cooking / Pasta"
    assert fm["source"] == "Instagram"
    assert body == "# Content"


def test_duration_formatting() -> None:
    """Verify duration helper formats seconds into mm:ss or hh:mm:ss."""
    assert format_duration(58) == "0:58"
    assert format_duration(65) == "1:05"
    assert format_duration(3665) == "1:01:05"
    assert format_duration("0:58") == "0:58"
    assert format_duration("58") == "0:58"
    assert format_duration(None) == ""
    assert format_duration(-10) == "0:00"


def test_slugify_anchor() -> None:
    """Verify heading anchor slugification."""
    assert slugify_anchor("Key points") == "key-points"
    assert slugify_anchor("Links mentioned (spoken)") == "links-mentioned-spoken"
    assert slugify_anchor("## Transcript") == "transcript"


def test_split_markdown_into_blocks_and_jump_matching() -> None:
    """Verify partitioning markdown into discrete blocks for jump target scrolling."""
    body = """# Creamy garlic pasta

## Overview
A 20 minute pasta with a garlic cream sauce.

## Key points
- Salt the water well
- Fry garlic on low heat

## Transcript
> 0:08 Start with well salted water.
> 0:42 Now add the cream.
"""
    blocks = split_markdown_into_blocks(body)
    assert len(blocks) >= 4

    # Check block kinds
    kinds = [b.kind for b in blocks]
    assert "heading" in kinds
    assert "blockquote" in kinds

    # Test jump lookup for timestamp
    idx_ts = find_jump_target_block_index(blocks, "0:42")
    assert idx_ts is not None
    assert "0:42" in blocks[idx_ts].content

    # Test jump lookup with prefix "▶ 0:42"
    idx_chip = find_jump_target_block_index(blocks, "▶ 0:42")
    assert idx_chip == idx_ts

    # Test jump lookup for heading anchor
    idx_h = find_jump_target_block_index(blocks, "#key-points")
    assert idx_h is not None
    assert blocks[idx_h].anchor == "key-points"

    # Test jump lookup for non-existent target
    assert find_jump_target_block_index(blocks, "non-existent-anchor") is None
