"""Tests for Phase 4 Cycle 4.2: Markdown Note Parser & Section Indexer (ADR 0005, DataModel.md §2.4)."""
from __future__ import annotations

import json
from pathlib import Path
import pytest

from backend.contracts.ids import new_uuid7, now_iso_z
from backend.llm.models import LinkItem, NoteStructuredOutput
from backend.processing.notes import (
    build_frontmatter_yaml,
    execute_note_persistence_transaction,
    generate_note_markdown,
    parse_frontmatter,
    parse_markdown_headings,
    slugify_heading,
)
from backend.store.db import Store


# ==============================================================================
# Unit Tests: slugify_heading
# ==============================================================================

def test_slugify_heading_basic() -> None:
    assert slugify_heading("Overview") == "overview"
    assert slugify_heading("Key Points and Takeaways") == "key-points-and-takeaways"
    assert slugify_heading("  Spaced Heading   ") == "spaced-heading"


def test_slugify_heading_punctuation_and_unicode() -> None:
    assert slugify_heading("What's Next? (2026 Edition)") == "whats-next-2026-edition"
    assert slugify_heading("Café & Résumé!") == "cafe-resume"
    assert slugify_heading("$$$ Special $$$") == "special"
    # Fallback when no alphanumerics exist
    assert slugify_heading("???") == "section"


def test_slugify_heading_timestamps() -> None:
    # Timestamps should be preserved as exact clean anchors
    assert slugify_heading("0:42") == "0:42"
    assert slugify_heading("12:34") == "12:34"
    assert slugify_heading("01:23:45") == "01:23:45"


# ==============================================================================
# Unit Tests: parse_markdown_headings
# ==============================================================================

def test_parse_markdown_headings_hierarchy_and_sequence() -> None:
    markdown = """---
source: youtube
folder: AI
---
# Main Title
Introductory text here.

## Overview
High-level overview text.

### Background
Some background info.

## Key points
- Point 1
- Point 2

## 0:42
Anchor for timestamp.
"""
    sections = parse_markdown_headings(markdown)

    assert len(sections) == 5
    assert sections[0] == {"heading": "Main Title", "anchor": "main-title", "seq": 1}
    assert sections[1] == {"heading": "Overview", "anchor": "overview", "seq": 2}
    assert sections[2] == {"heading": "Background", "anchor": "background", "seq": 3}
    assert sections[3] == {"heading": "Key points", "anchor": "key-points", "seq": 4}
    assert sections[4] == {"heading": "0:42", "anchor": "0:42", "seq": 5}


def test_parse_markdown_headings_duplicate_disambiguation() -> None:
    markdown = """
## Summary
First summary.

## Details
Some details.

## Summary
Second summary.

## Summary
Third summary.
"""
    sections = parse_markdown_headings(markdown)
    assert len(sections) == 4
    assert sections[0]["anchor"] == "summary"
    assert sections[1]["anchor"] == "details"
    assert sections[2]["anchor"] == "summary-1"
    assert sections[3]["anchor"] == "summary-2"


def test_parse_markdown_headings_ignores_frontmatter_contents() -> None:
    markdown = """---
source: "# not a heading"
channel: "## still not a heading"
---
## Actual Heading
Body content.
"""
    sections = parse_markdown_headings(markdown)
    assert len(sections) == 1
    assert sections[0]["heading"] == "Actual Heading"
    assert sections[0]["anchor"] == "actual-heading"


# ==============================================================================
# Unit Tests: build_frontmatter_yaml & parse_frontmatter
# ==============================================================================

def test_build_frontmatter_yaml_stable_facts_only() -> None:
    facts = {
        "source": "youtube",
        "channel": "Tech Channel",
        "video_url": "https://youtube.com/watch?v=123",
        "duration": 360,
        "published": "2026-03-01T12:00:00Z",
        "saved": "2026-03-02T10:00:00Z",
        "folder": "Tech/AI",
        "tags": ["machine-learning", "python"],
        # Volatile machine states must be ignored
        "suggested_folder": "Should Not Appear",
        "state": "analyzing",
        "confidence": 0.95,
        "needs_review": 1,
    }
    yaml_text = build_frontmatter_yaml(facts)

    assert yaml_text.startswith("---\n")
    assert yaml_text.endswith("---\n")
    assert "source: Tech Channel" not in yaml_text  # source is youtube
    assert "source: youtube" in yaml_text
    assert "channel: Tech Channel" in yaml_text
    assert 'video_url: "https://youtube.com/watch?v=123"' in yaml_text
    assert "duration: 360" in yaml_text
    assert "folder: Tech/AI" in yaml_text
    assert "tags:" in yaml_text
    assert '  - "machine-learning"' in yaml_text
    assert '  - "python"' in yaml_text

    # Machine states MUST NOT be in frontmatter
    assert "suggested_folder" not in yaml_text
    assert "confidence" not in yaml_text
    assert "needs_review" not in yaml_text


def test_build_frontmatter_yaml_nulls_and_empty() -> None:
    facts = {
        "source": None,
        "channel": None,
        "video_url": None,
        "duration": None,
        "published": None,
        "saved": None,
        "folder": None,
        "tags": [],
    }
    yaml_text = build_frontmatter_yaml(facts)
    assert "source: null" in yaml_text
    assert "duration: null" in yaml_text
    assert "tags: []" in yaml_text


def test_parse_frontmatter_roundtrip() -> None:
    original_facts = {
        "source": "youtube",
        "channel": "Awesome Dev",
        "video_url": "https://youtu.be/xyz",
        "duration": 420,
        "published": "2026-01-01T00:00:00Z",
        "saved": "2026-01-02T00:00:00Z",
        "folder": "Development",
        "tags": ["coding", "architecture"],
    }
    yaml_str = build_frontmatter_yaml(original_facts)
    doc = f"{yaml_str}# Document Title\n\nContent here."

    parsed_facts, body = parse_frontmatter(doc)

    assert parsed_facts["source"] == "youtube"
    assert parsed_facts["channel"] == "Awesome Dev"
    assert parsed_facts["video_url"] == "https://youtu.be/xyz"
    assert parsed_facts["duration"] == 420
    assert parsed_facts["published"] == "2026-01-01T00:00:00Z"
    assert parsed_facts["saved"] == "2026-01-02T00:00:00Z"
    assert parsed_facts["folder"] == "Development"
    assert parsed_facts["tags"] == ["coding", "architecture"]

    assert body.startswith("# Document Title")
    assert "Content here." in body


def test_parse_frontmatter_resilience() -> None:
    # 1. Missing frontmatter entirely
    raw_doc = "# Just Title\n\nParagraph."
    facts, body = parse_frontmatter(raw_doc)
    assert facts == {}
    assert body == raw_doc

    # 2. Corrupt / unrecognized frontmatter
    corrupt_doc = "---\nthis is not valid yaml ::::\n---\n# Title"
    facts, body = parse_frontmatter(corrupt_doc)
    assert isinstance(facts, dict)
    assert body == "# Title"

    # 3. Inline tags syntax [tag1, tag2]
    inline_tags_doc = """---
source: web
tags: ["alpha", "beta"]
---
Body text.
"""
    facts, body = parse_frontmatter(inline_tags_doc)
    assert facts["source"] == "web"
    assert facts["tags"] == ["alpha", "beta"]
    assert body == "Body text."


# ==============================================================================
# Unit Tests: generate_note_markdown
# ==============================================================================

def test_generate_note_markdown_structured() -> None:
    facts = {
        "source": "youtube",
        "channel": "Creator",
        "video_url": "https://example.com/v",
        "duration": 120,
        "published": "2026-02-01T00:00:00Z",
        "saved": "2026-02-02T00:00:00Z",
        "folder": "Inbox",
        "tags": ["ai"],
    }
    structured = NoteStructuredOutput(
        overview="A great video on AI.",
        key_points=["Point 1: intro", "Point 2: conclusion"],
        links=[
            LinkItem(anchor_text="Project Site", url="https://example.com", jump_target="0:42"),
            LinkItem(anchor_text="Doc", url="https://example.com/doc", jump_target=None),
        ],
        suggested_folder="AI/Research",
        tags=["ai", "deep-learning"],
    )

    md = generate_note_markdown(
        title="AI Overview",
        facts=facts,
        structured=structured,
        transcript="Spoken transcript text here.",
    )

    # Verify frontmatter presence
    assert md.startswith("---\n")
    assert "source: youtube" in md

    # Verify title
    assert "# AI Overview\n" in md

    # Verify guaranteed sections
    assert "## Overview\n" in md
    assert "A great video on AI." in md
    assert "## Key points\n" in md
    assert "- Point 1: intro" in md
    assert "- Point 2: conclusion" in md
    assert "## Links mentioned\n" in md
    assert "- [Project Site](https://example.com) (0:42)" in md
    assert "- [Doc](https://example.com/doc)" in md

    # Verify transcript excerpt
    assert "## Transcript excerpt\n" in md
    assert "> Spoken transcript text here." in md


def test_generate_note_markdown_degraded_fallback() -> None:
    facts = {"source": "web", "folder": "ReadLater", "tags": []}

    md = generate_note_markdown(
        title="Failed Article",
        facts=facts,
        structured=None,
        raw_body="Extracted article raw text here.",
    )

    assert "# Failed Article\n" in md
    assert "## Overview\n" in md
    assert "_Note overview generation unavailable._" in md
    assert "## Key points\n" in md
    assert "## Links mentioned\n" in md
    assert "## Content\n" in md
    assert "Extracted article raw text here." in md


def test_generate_note_markdown_transcript_truncation() -> None:
    facts = {"source": "youtube", "folder": "Videos", "tags": []}
    long_transcript = "word " * 400  # 2000 chars

    md = generate_note_markdown(
        title="Long Video",
        facts=facts,
        structured=None,
        transcript=long_transcript,
    )

    assert "## Transcript excerpt\n" in md
    assert " …\n" in md
    # Ensure excerpt length does not exceed 1300 chars
    excerpt_section = md.split("## Transcript excerpt\n")[1]
    assert len(excerpt_section) < 1300


# ==============================================================================
# Database / Transaction Tests: execute_note_persistence_transaction
# ==============================================================================

@pytest.mark.anyio
async def test_execute_note_persistence_transaction_insert_and_fts(tmp_path: Path) -> None:
    db_path = tmp_path / "test_notes.db"
    store = Store(str(db_path))

    save_id = new_uuid7()
    now = now_iso_z()

    # Seed parent save
    def _seed(conn):
        conn.execute(
            "INSERT INTO saves(id, raw_url, url, platform, source_app, user_context, captured_at, created_at, updated_at)"
            " VALUES (?, 'https://example.com', 'https://example.com', 'web', 'test', '', ?, ?, ?)",
            (save_id, now, now, now),
        )

    await store.run_tx(_seed)

    markdown = """---
source: web
channel: Author
video_url: null
duration: null
published: 2026-01-01T00:00:00Z
saved: 2026-01-02T00:00:00Z
folder: Tech
tags:
  - "python"
  - "sqlite"
---
# Python SQLite Testing

## Overview
Comprehensive overview of SQLite testing in Python applications.

## Key points
- Point one
- Point two

## Conclusion
Final concluding thoughts.
"""

    def _persist(conn):
        execute_note_persistence_transaction(
            conn=conn,
            save_id=save_id,
            markdown=markdown,
            overview="Comprehensive overview of SQLite testing",
            key_points=["Point one", "Point two"],
            links=[],
            transcript="Spoken audio transcript",
            now=now,
        )

    await store.run_tx(_persist)

    # 1. Verify notes row
    note_row = await store.fetchone("SELECT * FROM notes WHERE save_id=?", (save_id,))
    assert note_row is not None
    assert note_row["save_id"] == save_id
    assert note_row["source"] == "web"
    assert note_row["channel"] == "Author"
    assert note_row["folder_path"] == "Tech"
    assert json.loads(note_row["tags_json"]) == ["python", "sqlite"]
    assert note_row["overview"] == "Comprehensive overview of SQLite testing"
    assert json.loads(note_row["key_points_json"]) == ["Point one", "Point two"]
    assert note_row["transcript"] == "Spoken audio transcript"

    # 2. Verify note_sections table
    sections = await store.fetchall(
        "SELECT heading, anchor, seq FROM note_sections WHERE save_id=? ORDER BY seq ASC",
        (save_id,),
    )
    assert len(sections) == 4
    assert [s["heading"] for s in sections] == [
        "Python SQLite Testing",
        "Overview",
        "Key points",
        "Conclusion",
    ]
    assert [s["anchor"] for s in sections] == [
        "python-sqlite-testing",
        "overview",
        "key-points",
        "conclusion",
    ]
    assert [s["seq"] for s in sections] == [1, 2, 3, 4]

    # 3. Verify notes_fts virtual table indexation
    fts_rows = await store.fetchall(
        "SELECT save_id, overview FROM notes_fts WHERE notes_fts MATCH 'Comprehensive'",
    )
    assert len(fts_rows) == 1
    assert fts_rows[0]["save_id"] == save_id


@pytest.mark.anyio
async def test_execute_note_persistence_transaction_update_and_rebuild_sections(tmp_path: Path) -> None:
    db_path = tmp_path / "test_notes_update.db"
    store = Store(str(db_path))

    save_id = new_uuid7()
    now = now_iso_z()

    def _seed(conn):
        conn.execute(
            "INSERT INTO saves(id, raw_url, url, platform, source_app, user_context, captured_at, created_at, updated_at)"
            " VALUES (?, 'https://example.com', 'https://example.com', 'web', 'test', '', ?, ?, ?)",
            (save_id, now, now, now),
        )

    await store.run_tx(_seed)

    # Initial note with 2 sections
    initial_md = """---
source: web
tags: []
---
# Initial Title
## Initial Section
Body.
"""
    await store.run_tx(lambda conn: execute_note_persistence_transaction(conn, save_id, initial_md, now=now))

    sections_1 = await store.fetchall("SELECT * FROM note_sections WHERE save_id=?", (save_id,))
    assert len(sections_1) == 2

    # Updated note with 3 completely different sections
    updated_now = "2026-03-02T15:00:00Z"
    updated_md = """---
source: web
tags: ["updated"]
---
# Updated Title
## Section Alpha
## Section Beta
"""
    await store.run_tx(lambda conn: execute_note_persistence_transaction(conn, save_id, updated_md, now=updated_now))

    note_row = await store.fetchone("SELECT * FROM notes WHERE save_id=?", (save_id,))
    assert note_row is not None
    assert json.loads(note_row["tags_json"]) == ["updated"]
    assert note_row["updated_at"] == updated_now

    sections_2 = await store.fetchall(
        "SELECT heading, anchor, seq FROM note_sections WHERE save_id=? ORDER BY seq ASC",
        (save_id,),
    )
    assert len(sections_2) == 3
    assert [s["heading"] for s in sections_2] == ["Updated Title", "Section Alpha", "Section Beta"]
    assert [s["seq"] for s in sections_2] == [1, 2, 3]
