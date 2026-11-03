"""Background pipeline worker draining queued jobs."""

from __future__ import annotations

import asyncio
import logging

from Backend.config import Settings, load_settings
from Backend.processing.pipeline import PipelineService
from Backend.store.database import Database


log = logging.getLogger(__name__)


def database_health(database: Database) -> dict:
    """Check the database file, schema, and embedding model artifacts."""
    from Backend.store.embeddings import is_downloaded, model_directory

    info: dict = {"ok": True, "checks": {}}
    path = getattr(database, "path", None)
    info["checks"]["db_path"] = str(path) if path else None
    info["checks"]["db_file_exists"] = bool(path and path.exists())
    try:
        with database.transaction() as connection:
            tables = {
                row["name"]
                for row in connection.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
            }
        required = {"saves", "notes", "jobs", "save_vectors"}
        info["checks"]["schema_ok"] = required.issubset(tables)
        info["checks"]["missing_tables"] = sorted(required - tables)
    except Exception as exc:
        info["ok"] = False
        info["checks"]["schema_ok"] = False
        info["checks"]["schema_error"] = str(exc)
    model_dir = model_directory()
    info["checks"]["model_dir"] = str(model_dir)
    info["checks"]["model_downloaded"] = is_downloaded()
    info["checks"]["model_onnx_bytes"] = (model_dir / "model.onnx").stat().st_size if (model_dir / "model.onnx").exists() else 0
    info["checks"]["model_tokenizer_bytes"] = (model_dir / "tokenizer.json").stat().st_size if (model_dir / "tokenizer.json").exists() else 0
    info["ok"] = bool(info["checks"].get("schema_ok") and info["checks"].get("model_downloaded"))
    log.info(
        "worker: health db=%s schema=%s model=%s",
        info["checks"].get("db_file_exists"),
        info["checks"].get("schema_ok"),
        info["checks"].get("model_downloaded"),
    )
    return info


def temp_media_clean() -> bool:
    """Check no transient media directories leaked."""
    import pathlib
    import tempfile

    leaked = [p for p in pathlib.Path(tempfile.gettempdir()).glob("claybank-media-*")]
    log.info("worker: temp media leaked=%d", len(leaked))
    return not leaked


def fetch_queued_save_ids(database: Database, limit: int = 5) -> list[str]:
    """Return save ids whose jobs are still queued or extracting."""
    with database.transaction() as connection:
        rows = connection.execute(
            "SELECT save_id FROM jobs WHERE state IN ('queued', 'extracting') ORDER BY updated_at LIMIT ?",
            (limit,),
        ).fetchall()
        return [row["save_id"] for row in rows]


def process_due_jobs(database: Database, settings: Settings | None = None, limit: int = 5) -> list[str]:
    """Run the pipeline for due jobs; failures stay on the job row."""
    service = PipelineService(database, settings=settings)
    done: list[str] = []
    for save_id in fetch_queued_save_ids(database, limit):
        try:
            service.process_save(save_id)
            done.append(save_id)
        except Exception as exc:  # noqa: BLE001 - job row already records the failure
            log.warning("pipeline failed for %s: %s", save_id, exc)
    return done


async def worker_loop(database: Database, settings: Settings, interval_seconds: float = 5.0) -> None:
    """Poll the jobs table and process anything queued."""
    while True:
        try:
            await asyncio.to_thread(process_due_jobs, database, settings)
        except Exception as exc:  # noqa: BLE001 - worker must survive bad polls
            log.warning("pipeline worker poll failed: %s", exc)
        await asyncio.sleep(interval_seconds)


def worker_settings() -> Settings:
    """Load worker settings from process environment."""
    return load_settings()
