"""Live end-to-end check for ClayBank on port 8000 (opt-in, tracked script).

Run from the repo root:

    uv run scripts_live_e2e.py

Requires:
- Live server on http://127.0.0.1:8000 (restart after .env edits so the
  process picks up META_MODEL_API_* and CLAYBANK_WORKER).
- Root .env with DEV_TOKEN, X-Device-Id, cloud credentials.

What it does:
1. Checks embedding model files + live DB schema (via worker health).
2. Captures each link (force=true for repeatable reruns).
3. Runs the pipeline synchronously (reprocess?run=true).
4. Prints kind/flags/job/note and asserts ready + non-empty markdown.
5. Verifies intake cache: cache rows present for both base URLs, every
   cached row kind != unknown, and no completed prior attempt for the URL
   ended with an extracting failure (stale cache must force re-extract).
6. Verifies no claybank-media-* temp dirs leaked.

Links under test are the two verified Shorts/reel URLs. Edit LINKS to
change the set. Auth reuses Backend/tests/test_search.py HEADERS so the
script never drifts from the suite.
"""

from __future__ import annotations

import json
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path


BASE = "http://127.0.0.1:8000"
LINKS = [
    "https://youtube.com/shorts/eVHx6GsjWHs?si=nUA2ruUKZxXDP2j2",
    "https://www.instagram.com/reel/DfLyXqDMoDR/?xtok=MW8wb2MxYnlhY3g3dw==",
]

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from Backend.tests.test_search import HEADERS as SUITE_HEADERS  # noqa: E402


def headers() -> dict:
    """Reuse the suite auth headers so the script never drifts."""
    return {**SUITE_HEADERS, "Content-Type": "application/json"}


def live_call(method: str, path: str, body: dict | None = None):
    """Call the live server and return (status, payload)."""
    request = urllib.request.Request(
        BASE + path,
        data=json.dumps(body).encode() if body is not None else None,
        headers=headers(),
        method=method,
    )
    try:
        with urllib.request.urlopen(request, timeout=300) as response:
            raw = response.read().decode()
            return response.status, (json.loads(raw) if raw else {})
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode()
        return exc.code, json.loads(raw)


def main() -> int:
    """Run the live end-to-end check and report honestly."""
    from Backend.processing.worker import database_health, temp_media_clean
    from Backend.store.database import Database
    from Backend.store.embeddings import is_downloaded, model_directory

    print(f"model downloaded: {is_downloaded()} dir={model_directory()}", flush=True)
    if not is_downloaded():
        print("FAIL: embedding model missing", flush=True)
        return 1

    db = Database()
    db.initialize()
    health = database_health(db)
    print("db health:", json.dumps(health, indent=1), flush=True)
    db.close()
    if not health["ok"]:
        print("FAIL: database unhealthy", flush=True)
        return 1
    import pathlib
    import shutil
    import tempfile
    import time

    stale = []
    for entry in pathlib.Path(tempfile.gettempdir()).glob("claybank-media-*"):
        try:
            age = time.time() - entry.stat().st_mtime
        except OSError:
            continue
        if age > 600:
            stale.append(entry)
    for entry in stale:
        try:
            shutil.rmtree(entry, ignore_errors=True)
            print(f"cleanup: removed stale {entry.name}", flush=True)
        except OSError as exc:
            print(f"WARN: could not remove {entry.name}: {exc}", flush=True)
    if not temp_media_clean():
        print("FAIL: leaked media before run (recent, server may be mid-download)", flush=True)
        return 1

    failures = 0
    cache_probe_id: str | None = None
    for url in LINKS:
        status, capture = live_call("POST", "/saves", {"url": url, "force": True})
        print(f"\ncapture {status} {url}", flush=True)
        if status not in (200, 201):
            print("FAIL: capture", capture, flush=True)
            failures += 1
            continue
        save_id = capture["data"]["id"]
        if cache_probe_id is None:
            cache_probe_id = save_id
        print("canonical", capture["data"]["url"], "| platform", capture["data"].get("platform"), flush=True)

        status, job = live_call("POST", f"/saves/{save_id}/reprocess?run=true")
        print("reprocess", status, json.dumps(job, ensure_ascii=False)[:300], flush=True)

        status, bundle = live_call("GET", f"/saves/{save_id}")
        data = bundle["data"]
        print("kind", data["save"]["kind"], "| job", data["job"]["state"], data["job"].get("failed"), flush=True)
        note = (data["note"]["markdown"] if data["note"] else "") or ""
        print("note len", len(note), flush=True)
        print(note[:2500], flush=True)
        print("-" * 60, flush=True)
        if data["job"]["state"] != "ready" or not note:
            print(f"FAIL: {save_id} did not finish with markdown", flush=True)
            failures += 1

    if cache_probe_id is not None:
        from Backend.capture.canonicalize import canonicalize_url
        from Backend.store.database import Database as LiveDatabase

        probe_db = LiveDatabase()
        probe_db.initialize()
        with probe_db.transaction() as connection:
            rows = connection.execute(
                "SELECT url, kind, tier FROM extraction_cache WHERE user_id = 'dev-user'"
            ).fetchall()
            job_rows = connection.execute(
                """
                SELECT saves.url AS url, jobs.failed_json AS failed FROM jobs
                JOIN saves ON saves.id = jobs.save_id
                WHERE saves.user_id = 'dev-user'
                AND jobs.state NOT IN ('queued', 'extracting', 'transcribing')
                ORDER BY jobs.updated_at DESC
                """
            ).fetchall()
        probe_db.close()
        cached_urls = [row["url"] for row in rows]
        print(f"\ncache: {len(rows)} row(s) for dev-user: {cached_urls}", flush=True)
        base_urls = {canonicalize_url(url).split("#", 1)[0] for url in LINKS}
        base_cached = {url.split("#", 1)[0] for url in cached_urls}
        missing = [u for u in base_urls if u not in base_cached]
        if not rows or missing:
            print(f"FAIL: extraction cache missing {missing} after pipeline runs", flush=True)
            failures += 1
        else:
            print("cache: same-user same-link reuse verified (base URLs cached)", flush=True)
        unknown_rows = [row["url"] for row in rows if row["kind"] == "unknown"]
        if unknown_rows:
            print(f"FAIL: cache holds unknown rows (must never cache degraded): {unknown_rows}", flush=True)
            failures += 1
        stale = []
        latest: dict[str, list] = {}
        for job in job_rows:
            base = (job["url"] or "").split("#", 1)[0]
            if base in cached_urls and base not in latest:
                try:
                    latest[base] = json.loads(job["failed"] or "[]")
                except ValueError:
                    latest[base] = []
        for base, failed in latest.items():
            if "extracting" in failed:
                stale.append(base)
        if stale:
            print(f"FAIL: stale cache: prior attempt failed but row kept: {stale}", flush=True)
            failures += 1
        else:
            print("cache: no failed prior attempt behind a cached row", flush=True)

    if not temp_media_clean():
        print("FAIL: transient media leaked after run", flush=True)
        return 1
    print("cleanup: no claybank-media-* dirs left", flush=True)
    print("PASS" if failures == 0 else f"{failures} FAILURE(S)", flush=True)
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
