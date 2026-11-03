"""Claybank database schema test.

Builds BOTH store variants in memory (server = core + server-only, device =
core + device-only), applies the migrations, and asserts the invariants from
Docs/DataModel.md + Rules.md. Stdlib only — run from the repo root:

    python Docs/db/test_schema.py

Pairs with `Docs/api/test_contract.py`: the same invariants the JSON Schemas
guard on the wire must hold in the SQL layer.
"""
from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

HERE = Path(__file__).parent
CORE = HERE / "0001_core.sql"
SERVER = HERE / "0002_server.sql"
DEVICE = HERE / "0003_device.sql"
SCHEMAS = HERE.parent / "api" / "schemas"

T1 = "2026-10-31T12:00:00Z"
failures: list[str] = []


def fail(msg: str) -> None:
    failures.append(msg)
    print(f"FAIL: {msg}")


def build(*files: Path) -> sqlite3.Connection:
    db = sqlite3.connect(":memory:")
    db.execute("PRAGMA foreign_keys = ON")
    for f in files:
        db.executescript(f.read_text(encoding="utf-8"))
    return db


def expect_fail(db: sqlite3.Connection, fn, needle: str, label: str) -> None:
    """Run fn; expect an sqlite error containing `needle`.

    Does NOT roll back: a failed statement aborts only itself in sqlite, so
    seed data committed earlier (or auto-begun and later committed) stays.
    """
    try:
        fn()
    except sqlite3.Error as exc:
        if needle not in str(exc):
            fail(f"{label}: raised `{exc}` — expected it to contain `{needle}`")
        return
    db.rollback()  # only on unexpected success, to undo the bad-but-accepted row
    fail(f"{label}: expected failure (`{needle}`) but the statement succeeded")


def seed_folders(db: sqlite3.Connection) -> None:
    db.execute("INSERT INTO folders(id,parent_id,name,depth,created_at,updated_at,archived_at)"
               " VALUES('f-cook',NULL,'Cooking',0,?,?,NULL)", (T1, T1))
    db.execute("INSERT INTO folders(id,parent_id,name,depth,created_at,updated_at,archived_at)"
               " VALUES('f-pasta','f-cook','Pasta',1,?,?,NULL)", (T1, T1))


def seed_save(db: sqlite3.Connection, sid: str, url: str, kind: str = "video",
              folder: str | None = "f-pasta") -> None:
    db.execute(
        "INSERT INTO saves(id,raw_url,url,platform,source_app,user_context,kind,"
        "folder_id,suggested_folder_path,suggested_folder_confidence,"
        "captured_at,created_at,updated_at)"
        " VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (sid, url, url, "instagram", "instagram", "", kind, folder,
         "Cooking / Pasta" if folder else None,
         0.94 if folder else None, T1, T1, T1))


def main() -> None:
    server = build(CORE, SERVER)
    device = build(CORE, DEVICE)

    # --- 0. one enum source: SQL kind enum == save.json ----------------------
    save_schema = json.loads((SCHEMAS / "save.json").read_text(encoding="utf-8"))
    kind_json = set(save_schema["properties"]["kind"]["enum"])
    ddl = device.execute("SELECT sql FROM sqlite_master WHERE name='saves'").fetchone()[0]
    kind_sql = {k.strip(" '") for k in ddl.split("kind IN (")[1].split(")")[0].split(",")}
    if kind_sql != kind_json:
        fail(f"saves.kind enum drifted from save.json: {sorted(kind_sql)} vs {sorted(kind_json)}")

    folder_json = json.loads((SCHEMAS / "folder.json").read_text(encoding="utf-8"))
    reserved_json = folder_json["allOf"][0]["if"]["properties"]["name"]["enum"]

    # --- 1. folders: reserved names + depth cap -------------------------------
    seed_folders(device)
    device.commit()
    for name in reserved_json:
        expect_fail(device,
                    lambda n=name: device.execute(
                        "INSERT INTO folders(id,parent_id,name,depth,created_at,updated_at)"
                        " VALUES('f-x',NULL,?,0,?,?)", (n, T1, T1)),
                    "CHECK", f"folders rejects reserved name `{name}` (root)")
        expect_fail(device,
                    lambda n=name: device.execute(
                        "INSERT INTO folders(id,parent_id,name,depth,created_at,updated_at)"
                        " VALUES('f-y','f-cook',?,1,?,?)", (n, T1, T1)),
                    "CHECK", f"folders rejects reserved name `{name}` (child)")

    # a child claiming to skip levels (parent depth 1, child claims 3) aborts
    expect_fail(device,
                lambda: device.execute(
                    "INSERT INTO folders(id,parent_id,name,depth,created_at,updated_at)"
                    " VALUES('f-lv3','f-pasta','Lvl3Jump',3,?,?)", (T1, T1)),
                "folder_depth_exceeded", "child depth must be parent.depth + 1")

    # legitimate depth-3 grandchild passes
    device.execute("INSERT INTO folders(id,parent_id,name,depth,created_at,updated_at,archived_at)"
                   " VALUES('f-lv2','f-pasta','Level2',2,?,?,NULL)", (T1, T1))
    device.execute("INSERT INTO folders(id,parent_id,name,depth,created_at,updated_at,archived_at)"
                   " VALUES('f-lv3','f-lv2','Level3',3,?,?,NULL)", (T1, T1))
    device.commit()

    # --- 2. saves: duplicate url, kind enum, suggestion pairing ---------------
    seed_save(device, "s1", "https://instagram.com/p/x")
    device.commit()

    expect_fail(device,
                lambda: device.execute(
                    "INSERT INTO saves(id,raw_url,url,platform,captured_at,created_at,updated_at,kind)"
                    " VALUES('s-dup','https://instagram.com/p/x','https://instagram.com/p/x',"
                    "'instagram',?,?,?,'video')", (T1, T1, T1)),
                "UNIQUE", "canonicalized url is the duplicate key (409 already_saved)")
    device.commit()

    expect_fail(device,
                lambda: device.execute(
                    "INSERT INTO saves(id,raw_url,url,platform,captured_at,created_at,updated_at,kind)"
                    " VALUES('s-gal','g','g','gallery_source',?,?,?,'gallery')", (T1, T1, T1)),
                "CHECK", "kind enum (video|article|unknown; gallery dropped)")
    device.commit()

    expect_fail(device,
                lambda: device.execute(
                    "INSERT INTO saves(id,raw_url,url,platform,captured_at,created_at,updated_at,"
                    "suggested_folder_path) VALUES('s-half','h','h','instagram',?,?,?,'Cooking')",
                    (T1, T1, T1)),
                "CHECK", "suggested_folder path/confidence must travel as a pair")
    device.commit()

    # --- 3. notes: FTS triggers join denormalized save columns ------------------
    device.execute("INSERT INTO notes(save_id,markdown,overview,tags_json,transcript,created_at,updated_at)"
                   " VALUES('s1','---\nfolder: Cooking / Pasta\n---\n# Creamy garlic pasta\n',"
                   "'overview text','[]','0:42 now add cream',?,?)", (T1, T1))

    row = device.execute("SELECT save_id, kind, platform, title FROM notes_fts WHERE save_id='s1'").fetchone()
    if row is None:
        fail("notes_fts trigger did not index a new note")
    elif (row[1], row[2], row[3]) != ("video", "instagram", None):
        fail(f"notes_fts did not pick up kind/platform/title from saves: {row}")

    device.execute("UPDATE saves SET title='Garlic pasta title', platform='youtube' WHERE id='s1'")
    device.commit()
    row = device.execute("SELECT title, platform FROM notes_fts WHERE save_id='s1'").fetchone()
    if row != ("Garlic pasta title", "youtube"):
        fail(f"notes_fts save-side update trigger broke: {row}")

    # --- 4. full delete cascade: zero orphan text --------------------------------
    device.execute("DELETE FROM saves WHERE id='s1'")
    device.commit()
    for table in ("notes", "notes_fts"):
        c = device.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        if c:
            fail(f"cascade delete left {c} row(s) in {table}")

    seed_save(device, "s1", "https://instagram.com/p/x")
    device.execute("INSERT INTO notes(save_id,markdown,created_at,updated_at) VALUES('s1','# t',?,?)", (T1, T1))
    device.execute("INSERT INTO jobs(save_id,state,tier,created_at,updated_at) VALUES('s1','ready',1,?,?)", (T1, T1))
    device.execute("INSERT INTO tags(id,name) VALUES('t-recipe','recipe')")
    device.execute("INSERT INTO save_tags(save_id,tag_id) VALUES('s1','t-recipe')")
    device.execute("INSERT INTO save_vectors(save_id,vector,dim) VALUES('s1',X'00003f80',384)")
    device.execute("DELETE FROM saves WHERE id='s1'")
    device.commit()
    for table in ("notes", "jobs", "save_tags", "notes_fts", "save_vectors"):
        c = device.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        if c:
            fail(f"cascade delete left {c} row(s) in {table}")

    # --- 5. tags: case-insensitive uniqueness -------------------------------------
    device.execute("INSERT INTO tags(id,name) VALUES('t1','Sourdough')")
    device.commit()
    expect_fail(device,
                lambda: device.execute("INSERT INTO tags(id,name) VALUES('t2','sourdough')"),
                "UNIQUE", "tags are unique case-insensitively")

    # --- 6. jobs: state + tier enums -----------------------------------------------
    seed_save(device, "s9", "https://instagram.com/p/y")
    device.commit()
    expect_fail(device,
                lambda: device.execute(
                    "INSERT INTO jobs(save_id,state,tier,created_at,updated_at) VALUES('s9','gotten',1,?,?)",
                    (T1, T1)),
                "CHECK", "job state enum")
    device.commit()
    expect_fail(device,
                lambda: device.execute(
                    "INSERT INTO jobs(save_id,state,tier,created_at,updated_at) VALUES('s9','ready',3,?,?)",
                    (T1, T1)),
                "CHECK", "tier enum (1|2)")
    device.commit()

    # --- 7. suggestions: single/cluster pairing + rejection tombstones ---------------
    expect_fail(device,
                lambda: device.execute(
                    "INSERT INTO suggestions(id,type,save_id,cluster_json,path,confidence,created_at)"
                    " VALUES('sg1','cluster',NULL,NULL,'Cooking',0.9,?)", (T1,)),
                "CHECK", "cluster suggestion requires cluster_json")
    device.commit()
    expect_fail(device,
                lambda: device.execute(
                    "INSERT INTO suggestions(id,type,save_id,cluster_json,path,confidence,created_at)"
                    " VALUES('sg2','single',NULL,NULL,'Cooking / Pasta',0.94,?)", (T1,)),
                "CHECK", "single suggestion requires save_id")
    device.commit()

    device.execute("INSERT INTO suggestions(id,type,save_id,cluster_json,path,confidence,created_at)"
                   " VALUES('sg3','single','s9',NULL,'Cooking / Pasta',0.94,?)", (T1,))
    device.execute("INSERT INTO suggestion_rejections(fingerprint,dismissed_at)"
                   " VALUES('cook-cluster-1',?)", (T1,))
    device.execute("DELETE FROM saves WHERE id='s9'")
    device.commit()
    left = device.execute("SELECT COUNT(*) FROM suggestions").fetchone()[0]
    if left:
        fail(f"suggestion rows should cascade with their save ({left} left)")

    # --- 8. review queue / inbox views -------------------------------------------------
    seed_save(device, "r1", "https://instagram.com/p/z", folder=None)
    device.execute("UPDATE saves SET needs_review=1 WHERE id='r1'")
    device.commit()
    if device.execute("SELECT COUNT(*) FROM review_queue WHERE id='r1'").fetchone()[0] != 1:
        fail("review_queue view missed a needs_review save")
    if device.execute("SELECT COUNT(*) FROM inbox WHERE id='r1'").fetchone()[0] != 1:
        fail("inbox view missed an unfiled save")
    device.execute("UPDATE saves SET needs_review=0 WHERE id='r1'")
    device.commit()
    if device.execute("SELECT COUNT(*) FROM review_queue WHERE id='r1'").fetchone()[0] != 0:
        fail("review_queue view kept a save that no longer needs review")

    # --- 9. server-only: changes log cursor + idempotency by (user, key) ---------------
    server.execute("INSERT INTO users(id,name,created_at) VALUES('u1','Md. Shefayet',?)", (T1,))
    server.execute("INSERT INTO changes(entity,entity_id,op,at) VALUES('save','s1','put',?)", (T1,))
    server.commit()
    cursor = server.execute("SELECT MAX(id) FROM changes").fetchone()[0]
    if not cursor or cursor < 1:
        fail("changes log did not produce a pull cursor")

    server.execute("INSERT INTO idempotency_keys(key,user_id,op,payload_hash,resulting_id,created_at,expires_at)"
                   " VALUES('k1','u1','save_create','h','s1',?,?)", (T1, "2026-12-31T00:00:00Z"))
    server.commit()
    expect_fail(server,
                lambda: server.execute(
                    "INSERT INTO idempotency_keys(key,user_id,op,payload_hash,resulting_id,created_at,expires_at)"
                    " VALUES('k1','u1','save_create','h','s1',?,?)", (T1, "2026-12-31T00:00:00Z")),
                "UNIQUE", "same Idempotency-Key must not double-apply")

    # --- 10. device-only: queue uniqueness + settings enum --------------------------------
    device.execute("INSERT INTO sync_state(id,device_id,created_at) VALUES(1,'dev-a',?)", (T1,))
    device.execute("INSERT INTO device_queue(op,payload_json,idempotency_key,created_at)"
                   " VALUES('save_create','{}','qk1',?)", (T1,))
    device.commit()
    expect_fail(device,
                lambda: device.execute(
                    "INSERT INTO device_queue(op,payload_json,idempotency_key,created_at)"
                    " VALUES('note_put','{}','qk1',?)", (T1,)),
                "UNIQUE", "device queue replay must not duplicate on the same key")

    expect_fail(device,
                lambda: device.execute(
                    "INSERT INTO settings(id,chat_model,updated_at) VALUES(1,'ollama',?)", (T1,)),
                "CHECK", "chat_model enum (ollama is not a value — no external daemon)")
    device.commit()

    # --- 11. table separation: each store only its own additions ----------------------------
    for tbl, db, store in (("device_queue", server, "server"), ("users", device, "device"),
                           ("sync_state", server, "server"), ("changes", device, "device")):
        if db.execute("SELECT 1 FROM sqlite_master WHERE name=?", (tbl,)).fetchone():
            fail(f"{store} store must not contain `{tbl}`")

    print()
    if failures:
        print(f"schema test: {len(failures)} failure(s)")
        raise SystemExit(1)
    print("schema test: OK — server and device variants conform to DataModel.md invariants")


if __name__ == "__main__":
    main()
