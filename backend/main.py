"""FastAPI application factory — Phase 1: contract-first scaffold.

Routers align 1:1 with openapi.yaml tags. Phase 1 ships saves capture+reads;
remaining routers land in their phases behind the same envelopes/middleware.
"""
from __future__ import annotations

from contextlib import asynccontextmanager
import logging
from pathlib import Path

from fastapi import FastAPI

from backend.api.auth import DevAuthMiddleware
from backend.api.saves import router as saves_router
from backend.config import settings
from backend.processing.media import cleanup_stale_media_directories
from backend.processing.pipeline import PipelineEngine
from backend.processing.recovery import recover_stale_jobs
from backend.store.db import Store

log = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifecycle: purge stale temporary media before handling requests."""
    media_root = getattr(app.state, "media_base_dir", None)
    cleanup_stale_media_directories(base_dir=media_root)

    store = getattr(app.state, "store", None)
    pipeline = getattr(app.state, "pipeline", None)
    if store is not None:
        await recover_stale_jobs(store, pipeline)

    yield


def create_app(store: Store | None = None, *, media_base_dir: Path | None = None) -> FastAPI:
    """Create and configure the FastAPI application instance.

    Args:
        store: SQLite Store instance (defaults to a new Store).
        media_base_dir: Optional custom directory for media storage and sweeping (for isolated testing).

    Returns:
        FastAPI: Configured application instance.
    """
    app = FastAPI(title="Claybank API", version="0.1.0", lifespan=lifespan)
    app.state.store = store or Store()
    app.state.media_base_dir = media_base_dir
    app.state.pipeline = PipelineEngine(app.state.store, media_base_dir=media_base_dir)
    app.add_middleware(DevAuthMiddleware)
    app.include_router(saves_router)

    @app.get("/health")
    async def health():
        return {"data": {"ok": True, "contract_version": 0}}

    return app


app = create_app()


def serve() -> None:
    import uvicorn
    uvicorn.run("backend.main:app", host=settings.CLAYBANK_HOST,
                port=settings.CLAYBANK_PORT, reload=False)


if __name__ == "__main__":
    serve()
