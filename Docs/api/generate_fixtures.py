"""Claybank contract fixtures — generated, not hand-maintained.

Run from the repo root:

    python Docs/api/generate_fixtures.py

Writes one JSON file per case into ``Docs/api/fixtures/``. The single authored
source of example payloads *is this script*; fixtures on disk are build output,
so the contract test in ``test_contract.py`` can validate the examples against
``Docs/api/schemas/*.json`` without hand-synced drift.

Validation must stay green for any contract-touching change; see Docs/Phases.md
Phase 1.
"""
from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).parent
FIXTURES_DIR = HERE / "fixtures"

# All dates are stable literals — regenerating must be idempotent.
T1 = "2026-10-31T12:00:00Z"

# Stable placeholder UUIDv7 shapes (deterministic across runs).
_CACHE: dict[str, str] = {}

def _uuid7(n: str) -> str:
    """Deterministic UUIDv7-shaped placeholder per short name (e.g. 'save')."""
    if n in _CACHE:
        return _CACHE[n]
    seq = len(_CACHE) + 1
    v = f"018f4c1a-0000-7de6-9c8e-{seq:012d}"
    _CACHE[n] = v
    return v

SAVE_ID = _uuid7("save")
SAVE2_ID = _uuid7("save2")
ARTICLE_ID = _uuid7("article")
FOLDER_COOK_ID = _uuid7("cook")
FOLDER_PASTA_ID = _uuid7("pasta")
TAG_ID = _uuid7("tag")

FIXTURES: dict[str, list[dict]] = {
    # request bodies — valid -->
    "save-capture.json": [        {
            "url": "https://www.instagram.com/reel/Cx9abc/",
            "source_app": "instagram",
            "user_context": "Garlic cream sauce recipe try this weekend",
            "suggested_folder_id": FOLDER_PASTA_ID,
        },
        {
            "url": "https://example.com/posts/sous-vide-basics",
        },
    ],
    # response bodies — valid -->
    "error.json": [
        {
            "code": "already_saved",
            "message": "This link is already in your library.",
            "detail": {"existing_id": ARTICLE_ID},
        },
        {
            "code": "conflict",
            "message": "The note changed on another device.",
            "detail": {"server_updated_at": T1},
        },
    ],
    "folder.json": [
        {
            "id": FOLDER_COOK_ID,
            "parent_id": None,
            "name": "Cooking",
            "save_count": 24,
            "created_at": T1,
            "updated_at": T1,
            "archived_at": None,
        },
        {
            "id": FOLDER_PASTA_ID,
            "parent_id": FOLDER_COOK_ID,
            "name": "Pasta",
            "save_count": 6,
            "created_at": T1,
            "updated_at": T1,
            "archived_at": None,
        },
    ],
    "tag.json": [
        {"id": TAG_ID, "name": "recipe", "save_count": 11},
        {"id": _uuid7("tag2"), "name": "sourdough", "save_count": 3},
    ],
    "save.json": [
        {
            "id": SAVE_ID,
            "url": "https://www.instagram.com/reel/canonical_Cx9abc/",
            "raw_url": "https://www.instagram.com/reel/Cx9abc/?igsh=MTA2",
            "platform": "instagram",
            "source_app": "instagram",
            "user_context": "Garlic cream sauce recipe try this weekend",
            "kind": "video",
            "has_audio": True,
            "has_timeline": True,
            "has_images": False,
            "duration": 58,
            "title": "Creamy garlic pasta",
            "needs_review": False,
            "folder_id": FOLDER_PASTA_ID,
            "suggested_folder": {"path": "Cooking / Pasta", "confidence": 0.94},
            "captured_by_device": "dev-laptop",
            "captured_at": T1,
            "created_at": T1,
            "updated_at": T1,
        },
        {
            "id": ARTICLE_ID,
            "url": "https://example.com/posts/sous-vide-basics",
            "platform": "example.com",
            "source_app": "unknown",
            "user_context": "",
            "kind": "article",
            "has_audio": False,
            "has_timeline": False,
            "has_images": True,
            "duration": None,
            "title": "Sous vide basics",
            "needs_review": True,
            "folder_id": None,
            "suggested_folder": None,
            "captured_by_device": "dev-laptop",
            "captured_at": T1,
            "created_at": T1,
            "updated_at": T1,
        },
    ],
    "note.json": [
        {
            "save_id": SAVE_ID,
            "markdown": (
                "---\n"
                "source: Instagram\n"
                "channel: @chefmara\n"
                "video_url: instagram.com/reel/canonical_Cx9abc\n"
                "duration: 58\n"
                "published: \"2026-10-03\"\n"
                "saved: \"2026-10-31\"\n"
                "folder: Cooking / Pasta\n"
                "tags:\n  - recipe\n  - pasta\n  - dinner\n"
                "---\n"
                "# Creamy garlic pasta\n\n"
                "## Overview\n"
                "A 20 minute pasta with a garlic cream sauce. Five ingredients, one pan.\n\n"
                "## Key points\n"
                "- Salt the water well\n"
                "- Fry garlic on low heat\n"
                "- Add cream last, then pasta water\n\n"
                "## Transcript (excerpt)\n"
                "> 0:08 — Start with well salted water.\n"
                "> 0:42 — Now add the cream.\n"
            ),
            "frontmatter": {
                "source": "Instagram",
                "channel": "@chefmara",
                "video_url": "https://www.instagram.com/reel/canonical_Cx9abc/",
                "duration": 58,
                "published": "2026-10-03",
                "saved": "2026-10-31",
                "folder": "Cooking / Pasta",
                "tags": ["recipe", "pasta", "dinner"],
            },
            "overview": "A 20 minute pasta with a garlic cream sauce.",
            "key_points": [
                "Salt the water well",
                "Fry garlic on low heat",
                "Add cream last, then pasta water",
            ],
            "links": [
                {"url": "https://chefmara.example/garlic-pasta", "anchor_text": "chefmara", "jump_target": None},
                {"url": "https://shop.example/pan", "anchor_text": "pan", "jump_target": "0:12"},
            ],
            "transcript": "0:08 — Start with well salted water.\n0:42 — Now add the cream.",
            "created_at": T1,
            "updated_at": T1,
        },
    ],
    "job.json": [
        {
            "save_id": SAVE_ID,
            "state": "ready",
            "tier": 1,
            "skipped": [],
            "failed": [],
            "error": None,
            "agent_trace": None,
            "timing": {"extracting": 3100, "transcribing": 5400, "analyzing": 8100, "sorting": 900},
            "created_at": T1,
            "updated_at": T1,
        },
        {
            "save_id": ARTICLE_ID,
            "state": "analyzing",
            "tier": 1,
            "skipped": ["transcribing"],
            "failed": ["transcribing"],
            "error": "asr: no audio in source",
            "agent_trace": None,
            "timing": {"extracting": 2400, "transcribing": None, "analyzing": None, "sorting": None},
            "created_at": T1,
            "updated_at": T1,
        },
    ],
    "extraction-result.json": [
        {
            "tier": 1,
            "kind": "video",
            "title": "Creamy garlic pasta",
            "channel": "@chefmara",
            "duration": 58,
            "published": "2026-10-03",
            "body": None,
            "transcript_available": True,
            "capability_flags": {"has_audio": True, "has_timeline": True, "has_images": False},
            "source_meta": {"author_style": None},
        },
        {
            "tier": 1,
            "kind": "article",
            "title": "Sous vide basics",
            "channel": None,
            "duration": None,
            "published": "2026-10-14",
            "body": "Sous vide cooking keeps the water bath at the target temperature...",
            "transcript_available": False,
            "capability_flags": {"has_audio": False, "has_timeline": False, "has_images": True},
            "source_meta": {},
        },
        {
            "tier": 1,
            "kind": "unknown",
            "title": None,
            "channel": None,
            "duration": None,
            "published": None,
            "body": None,
            "transcript_available": False,
            "capability_flags": {"has_audio": False, "has_timeline": False, "has_images": False},
            "source_meta": {},
        },
    ],
    "search-result.json": [
        {
            "save": {
                "id": SAVE_ID,
                "url": "https://www.instagram.com/reel/canonical_Cx9abc/",
                "platform": "instagram",
                "source_app": "instagram",
                "user_context": "Garlic cream sauce recipe try this weekend",
                "kind": "video",
                "needs_review": False,
                "captured_at": T1,
            },
            "match_reason": "transcript",
            "fragment": "add cream at the end",
            "jump_target": "0:42",
            "score": 0.81,
        },
        {
            "save": {
                "id": ARTICLE_ID,
                "url": "https://example.com/posts/sous-vide-basics",
                "platform": "example.com",
                "source_app": "unknown",
                "user_context": "",
                "kind": "article",
                "needs_review": True,
                "captured_at": T1,
            },
            "match_reason": "semantic",
            "fragment": None,
            "jump_target": None,
            "score": 0.76,
        },
    ],
    "ask-answer.json": [
        {
            "answer": "Try the garlic pasta first. It takes 20 minutes and uses one pan.",
            "scope": FOLDER_COOK_ID,
            "engine": "cloud",
            "citations": [
                {"save_id": SAVE_ID, "anchor": "0:42", "quote": "Now add the cream"},
            ],
        },
    ],
    "suggestion.json": [
        {
            "type": "single",
            "save_id": SAVE_ID,
            "cluster": None,
            "path": "Cooking / Pasta",
            "confidence": 0.94,
            "dismissed_at": None,
            "accepted": False,
        },
        {
            "type": "cluster",
            "save_id": None,
            "cluster": [
                {"save_id": SAVE_ID, "title": "Creamy garlic pasta"},
                {"save_id": SAVE2_ID, "title": "One pot pasta"},
                {"save_id": _uuid7("save3"), "title": "Sauce basics"},
            ],
            "path": "Cooking",
            "confidence": 0.88,
            "dismissed_at": None,
            "accepted": False,
        },
        {
            "type": "cluster",
            "save_id": None,
            "cluster": [
                {"save_id": SAVE2_ID, "title": "One pot pasta"},
                {"save_id": _uuid7("save3"), "title": "Sauce basics"},
                {"save_id": _uuid7("save4"), "title": "No knead bread"},
            ],
            "path": "Cooking",
            "confidence": 0.83,
            "dismissed_at": T1,
            "accepted": False,
        },
    ],
    # --- request schemas for the write endpoints ---
    "save-patch.json": [
        {
            "folder_id": FOLDER_PASTA_ID,
            "tag_ids": [TAG_ID],
            "user_context": "Garlic cream sauce recipe try this weekend",
            "updated_at": T1,
        },
        {
            "folder_id": None,
            "updated_at": T1,
        },
    ],
    "note-put.json": [
        {
            "markdown": "---\nsource: Instagram\nchannel: @chefmara\nvideo_url: instagram.com/reel/canonical_Cx9abc\nfolder: Cooking / Pasta\n---\n# Creamy garlic pasta\n\n## Overview\nHand-edited by the user.",
            "updated_at": T1,
        },
    ],
    "tags-put.json": [
        {"tag_ids": [TAG_ID, _uuid7("tag2")], "updated_at": T1},
    ],
    "folder-write.json": [
        {
            "name": "Pasta",
            "parent_id": FOLDER_COOK_ID,
            "archived_at": None,
        },
        {
            "name": "Weeknight quick",
            "parent_id": FOLDER_COOK_ID,
        },
    ],
    "suggestion-accept.json": [
        {
            "type": "single",
            "save_id": SAVE_ID,
            "path": "Cooking / Pasta",
            "confidence": 0.94,
            "accept": True,
        },
        {
            "type": "cluster",
            "cluster": [
                {"save_id": SAVE_ID, "title": "Creamy garlic pasta"},
                {"save_id": _uuid7("save2"), "title": "One pot pasta"},
                {"save_id": _uuid7("save3"), "title": "Sauce basics"},
            ],
            "path": "Cooking",
            "confidence": 0.88,
            "accept": True,
        },
        {
            "type": "cluster",
            "cluster": [
                {"save_id": _uuid7("save2"), "title": "One pot pasta"},
                {"save_id": _uuid7("save3"), "title": "Sauce basics"},
                {"save_id": _uuid7("save4"), "title": "No knead bread"},
            ],
            "path": "Cooking",
            "confidence": 0.83,
            "accept": False,
            "dismissed_at": T1,
        },
    ],
    "search-request.json": [
        {"q": "garlic cream sauce", "folder_scope": FOLDER_COOK_ID},
        {"q": "sous vide"},
    ],
    "ask-request.json": [
        {"question": "What should I cook this week?", "save_scope": FOLDER_COOK_ID, "engine": "cloud"},
        {"question": "What did I never open?", "save_scope": "library", "engine": "local"},
    ],
    "sync-push.json": [
        {
            "ops": [
                {
                    "op": "save_create",
                    "payload": {
                        "url": "https://www.instagram.com/reel/offline_captured/",
                        "source_app": "instagram",
                        "user_context": "captured offline, queued",
                    },
                    "idempotency_key": "018f4c1a-0004-7de6-9c8e-000000000001",
                },
                {
                    "op": "folder_create",
                    "payload": {"name": "Weeknight quick", "parent_id": FOLDER_COOK_ID},
                    "idempotency_key": "018f4c1a-0004-7de6-9c8e-000000000002",
                },
            ],
            "device_cursor": "c-00042",
        },
    ],
    "sync-pull.json": [
        {
            "saves": [
                {
                    "id": SAVE_ID,
                    "url": "https://www.instagram.com/reel/canonical_Cx9abc/",
                    "platform": "instagram",
                    "source_app": "instagram",
                    "user_context": "",
                    "kind": "video",
                    "needs_review": False,
                    "captured_at": T1,
                },
            ],
            "notes": [],
            "folders": [
                {
                    "id": FOLDER_COOK_ID,
                    "parent_id": None,
                    "name": "Cooking",
                    "save_count": 24,
                    "created_at": T1,
                    "updated_at": T1,
                    "archived_at": None,
                },
            ],
            "jobs": [
                {
                    "save_id": SAVE_ID,
                    "state": "ready",
                    "tier": 1,
                    "skipped": [],
                    "failed": [],
                    "error": None,
                    "agent_trace": None,
                    "timing": {"extracting": 3100, "transcribing": 5400, "analyzing": 8100, "sorting": 900},
                    "created_at": T1,
                    "updated_at": T1,
                },
            ],
            "deleted": [],
            "cursor": "c-00042",
        },
    ],
    # --- page envelopes ---
    "save-page.json": [
        {
            "items": [
                {
                    "id": SAVE_ID,
                    "url": "https://www.instagram.com/reel/canonical_Cx9abc/",
                    "platform": "instagram",
                    "source_app": "instagram",
                    "user_context": "",
                    "kind": "video",
                    "needs_review": False,
                    "captured_at": T1,
                },
            ],
            "cursor": None,
        },
    ],
    "folder-page.json": [
        {
            "items": [
                {
                    "id": FOLDER_COOK_ID,
                    "parent_id": None,
                    "name": "Cooking",
                    "save_count": 24,
                    "created_at": T1,
                    "updated_at": T1,
                    "archived_at": None,
                },
            ],
            "cursor": None,
        },
    ],
    "search-page.json": [
        {
            "results": [
                {
                    "save": {
                        "id": SAVE_ID,
                        "url": "https://www.instagram.com/reel/canonical_Cx9abc/",
                        "platform": "instagram",
                        "source_app": "instagram",
                        "user_context": "",
                        "kind": "video",
                        "needs_review": False,
                        "captured_at": T1,
                    },
                    "match_reason": "transcript",
                    "fragment": "add cream at the end",
                    "jump_target": "0:42",
                    "score": 0.81,
                },
            ],
            "cursor": None,
        },
    ],
}


def main() -> None:
    FIXTURES_DIR.mkdir(parents=True, exist_ok=True)
    # Idempotent writes: drop previous outputs first so renames can't leave
    # stale fixtures behind.
    for stale in FIXTURES_DIR.glob("*.fixtures.json"):
        stale.unlink()
    written: list[str] = []
    for schema_name, cases in sorted(FIXTURES.items()):
        # Error-payload cases (consumers' failure bodies) are still valid Error
        # instances, so everything in FIXTURES validates against its schema.
        out = FIXTURES_DIR / f"{schema_name[:-5]}.fixtures.json"
        payload = {
            "valid": cases,
            "notes": "Generated by Docs/api/generate_fixtures.py — edit the generator, not this file.",
        }
        out.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        written.append(out.name)
    print(f"wrote {len(written)} fixture files to {FIXTURES_DIR}/")
    print(f"cases validated downstream: {sum(len(c) for c in FIXTURES.values())}")


if __name__ == "__main__":
    main()
