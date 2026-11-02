"""Startup recovery for interrupted and orphaned pipeline jobs (ADR 0004, Rules.md §8).

Reclaims jobs left in transient states ('extracting', 'transcribing') when the backend
restarts after a crash or shutdown, resetting them to 'queued' and resuming processing.
"""
from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

from backend.contracts.ids import now_iso_z
from backend.store.db import Store

if TYPE_CHECKING:
    from backend.processing.pipeline import PipelineEngine

logger = logging.getLogger(__name__)


async def recover_stale_jobs(store: Store, pipeline: PipelineEngine | None = None) -> int:
    """Recover jobs left in transient states ('extracting', 'transcribing').

    Args:
        store: SQLite Store instance.
        pipeline: Optional PipelineEngine to resume processing for recovered jobs.

    Returns:
        int: Number of recovered jobs.
    """
    now = now_iso_z()
    stale_jobs = await store.fetchall(
        "SELECT save_id, state FROM jobs WHERE state IN ('extracting', 'transcribing')"
    )

    if not stale_jobs:
        return 0

    recovered_count = 0
    for job in stale_jobs:
        save_id = job["save_id"]
        await store.execute(
            "UPDATE jobs SET state='queued', error=NULL, updated_at=? WHERE save_id=?",
            (now, save_id),
        )
        recovered_count += 1
        logger.info(
            "Recovered stale job %s from state=%s to state=queued",
            save_id,
            job["state"],
        )
        if pipeline is not None:
            asyncio.create_task(pipeline.process_save(save_id))

    return recovered_count
