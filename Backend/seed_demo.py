"""Seed a demo library for frontend integration and showcases.

Run from the repo root:

    uv run Backend/seed_demo.py [--db PATH] [--force]

- Fills an empty database with folders, saves, notes, tags, jobs, and
  suggestions covering every UI surface (Inbox, folders, review queue,
  search hits, Ask citations).
- Refuses to touch a non-empty database unless --force is given.
- Deterministic: stable ids/URLs/timestamps, idempotent under --force.
- Removal: uv run Backend/seed_demo.py --wipe [--db PATH]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from Backend.store.database import Database  # noqa: E402

NOW = "2026-11-03T12:00:00Z"
USER = "dev-user"
DEVICE = "seed-script"

FOLDERS = [
    ("018f4c1a-0000-7de6-9c8e-000000000101", None, "Cooking", 0),
    ("018f4c1a-0000-7de6-9c8e-000000000102", "018f4c1a-0000-7de6-9c8e-000000000101", "Pasta", 1),
    ("018f4c1a-0000-7de6-9c8e-000000000103", None, "AI Notes", 0),
]

TAGS = [
    ("018f4c1a-0000-7de6-9c8e-000000000201", "recipe"),
    ("018f4c1a-0000-7de6-9c8e-000000000202", "weeknight"),
    ("018f4c1a-0000-7de6-9c8e-000000000203", "motion-design"),
]

SAVES = [
    {
        "id": "018f4c1a-0000-7de6-9c8e-000000000301",
        "url": "https://example.com/garlic-cream-pasta",
        "platform": "example.com",
        "title": "Garlic cream pasta in 20 minutes",
        "kind": "article",
        "folder": "018f4c1a-0000-7de6-9c8e-000000000102",
        "tags": ["recipe", "weeknight"],
        "note": (
            "---\nsource: example\n---\n# Garlic cream pasta in 20 minutes\n\n"
            "## Overview\nA weeknight garlic cream sauce with pasta water emulsion.\n\n"
            "## Key points\n- [00:42] bloom garlic gently, never brown it\n- reserve a cup of pasta water\n\n"
            "## Transcript\n[00:42] bloom the garlic gently in olive oil\n\n"
            "## Links\n- https://example.com/pasta-water-guide\n"
        ),
        "transcript": "[00:42] bloom the garlic gently in olive oil",
        "needs_review": 0,
    },
    {
        "id": "018f4c1a-0000-7de6-9c8e-000000000302",
        "url": "https://youtube.com/watch?v=NqX98qqlRnA",
        "platform": "youtube",
        "title": "The creator of Naruto",
        "kind": "video",
        "folder": "018f4c1a-0000-7de6-9c8e-000000000103",
        "tags": ["motion-design"],
        "note": (
            "---\nsource: youtube\n---\n# The creator of Naruto\n\n"
            "## Overview\nOutsource execution, don't outsource creative direction.\n\n"
            "## Key points\n- [01:10] teach motion principles before judging output\n- connect OBS to record a real interface\n\n"
            "## Links\n- https://obsproject.com\n"
        ),
        "transcript": "[01:10] teach it motion principles first",
        "needs_review": 0,
    },
    {
        "id": "018f4c1a-0000-7de6-9c8e-000000000303",
        "url": "https://example.com/sourdough-basics",
        "platform": "example.com",
        "title": "Sourdough basics for beginners",
        "kind": "article",
        "folder": None,
        "tags": ["recipe"],
        "note": (
            "---\nsource: example\n---\n# Sourdough basics\n\n"
            "## Overview\nStarter care and an overnight schedule.\n\n"
            "## Key points\n- feed at peak rise for a vigorous starter\n\n"
            "## Links\n"
        ),
        "transcript": None,
        "needs_review": 1,
    },
    {
        "id": "018f4c1a-0000-7de6-9c8e-000000000304",
        "url": "https://example.com/air-layering-fruit-trees",
        "platform": "example.com",
        "title": "Air layering fruit trees",
        "kind": "article",
        "folder": None,
        "tags": [],
        "note": (
            "---\nsource: example\n---\n# Air layering fruit trees\n\n"
            "## Overview\nClone outstanding trees by wounding a branch and wrapping it.\n\n"
            "## Key points\n- [03:20] cut the branch below the new roots\n\n"
            "## Links\n"
        ),
        "transcript": "[03:20] cut below the new roots",
        "needs_review": 1,
    },
]


def save_count(connection) -> int:
    """Count saves in the database."""
    return connection.execute("SELECT COUNT(*) AS n FROM saves").fetchone()["n"]


def seed(db: Database, *, force: bool = False) -> int:
    """Fill the database with the demo library."""
    db.initialize()
    with db.transaction() as connection:
        existing = save_count(connection)
        if existing and not force:
            print(f"seed: {existing} save(s) present, pass --force to overwrite")
            return existing
        for fid, parent, name, depth in FOLDERS:
            connection.execute(
                "INSERT OR REPLACE INTO folders (id, parent_id, name, depth, created_at, updated_at)"
                " VALUES (?, ?, ?, ?, ?, ?)",
                (fid, parent, name, depth, NOW, NOW),
            )
        tag_ids: dict[str, str] = {}
        for tid, name in TAGS:
            connection.execute(
                "INSERT OR IGNORE INTO tags (id, name) VALUES (?, ?)", (tid, name)
            )
            row = connection.execute("SELECT id FROM tags WHERE name = ?", (name,)).fetchone()
            tag_ids[name] = row["id"]
        for item in SAVES:
            connection.execute(
                """
                INSERT OR REPLACE INTO saves (
                    id, raw_url, url, platform, source_app, user_context, kind,
                    title, folder_id, needs_review, captured_by_device, user_id,
                    captured_at, created_at, updated_at
                ) VALUES (?, ?, ?, ?, 'seed', '', ?, ?, ?, ?, 'seed-script', 'dev-user', ?, ?, ?)
                """,
                (
                    item["id"], item["url"], item["url"], item["platform"], item["kind"],
                    item["title"], item["folder"], item["needs_review"], NOW, NOW, NOW,
                ),
            )
            connection.execute(
                """
                INSERT OR REPLACE INTO notes (
                    save_id, markdown, source, transcript, overview, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    item["id"], item["note"], item["platform"], item["transcript"],
                    item["note"].split("## Overview")[1].split("##")[0].strip() if "## Overview" in item["note"] else None,
                    NOW, NOW,
                ),
            )
            connection.execute(
                "INSERT OR REPLACE INTO jobs (save_id, state, tier, created_at, updated_at)"
                " VALUES (?, 'ready', 1, ?, ?)",
                (item["id"], NOW, NOW),
            )
            connection.execute(
                "INSERT OR REPLACE INTO extraction_results"
                " (save_id, tier, kind, title, body, transcript_available, created_at)"
                " VALUES (?, 1, ?, ?, ?, ?, ?)",
                (item["id"], item["kind"], item["title"], item["note"], int(bool(item["transcript"])), NOW),
            )
            from Backend.store.vectors import VectorIndex

            passage = f"{item['title']} {item['note']}"
            try:
                VectorIndex(db).index_note(item["id"], passage)
            except Exception as exc:
                print(f"seed: vector indexing skipped ({exc})")
            for tag in item["tags"]:
                connection.execute(
                    "INSERT OR IGNORE INTO save_tags (save_id, tag_id) VALUES (?, ?)",
                    (item["id"], tag_ids[tag]),
                )
        connection.execute("DELETE FROM suggestions")
        connection.execute(
            "INSERT OR REPLACE INTO suggestions (id, type, save_id, path, confidence, created_at)"
            " VALUES ('018f4c1a-0000-7de6-9c8e-000000000401', 'single',"
            " '018f4c1a-0000-7de6-9c8e-000000000303', 'Cooking / Pasta', 0.72, ?)",
            (NOW,),
        )
        total = save_count(connection)
    print(f"seed: demo library ready ({total} saves)")
    return total


def wipe(db: Database) -> None:
    """Remove all seeded demo rows, leaving schema and config intact."""
    db.initialize()
    with db.transaction() as connection:
        connection.execute("PRAGMA foreign_keys = OFF")
        try:
            for table in ("suggestions", "suggestion_rejections", "save_tags", "save_vectors",
                          "extraction_results", "extraction_cache", "note_sections", "notes_fts",
                          "jobs", "notes", "saves", "tags", "folders", "changes",
                          "idempotency_keys", "capture_audit"):
                try:
                    connection.execute(f"DELETE FROM {table}")
                except Exception:
                    pass
        finally:
            connection.execute("PRAGMA foreign_keys = ON")
    print("seed: demo library wiped (schema kept)")


def main() -> int:
    """Parse args and seed or wipe the demo library."""
    parser = argparse.ArgumentParser(description="Seed or wipe the ClayBank demo library.")
    parser.add_argument("--db", default=None, help="SQLite path (default: backend data dir)")
    parser.add_argument("--force", action="store_true", help="Overwrite a non-empty database")
    parser.add_argument("--wipe", action="store_true", help="Remove seeded rows instead of seeding")
    args = parser.parse_args()
    from pathlib import Path as _Path

    db = Database(_Path(args.db)) if args.db else Database()
    if args.wipe:
        wipe(db)
    else:
        seed(db, force=args.force)
    db.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
