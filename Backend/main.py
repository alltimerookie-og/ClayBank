"""Create the Claybank FastAPI application."""

import asyncio
from contextlib import asynccontextmanager
from typing import cast

from fastapi import FastAPI
from starlette.types import ExceptionHandler

from Backend.api.routes import router
from Backend.config import load_settings
from Backend.errors import DomainError, domain_error_handler
from Backend.processing.worker import worker_loop
from Backend.store.database import Database


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Open the database, run the pipeline worker, close on shutdown."""
    import os
    import sys

    owned = getattr(app.state, "database", None) is None
    database = app.state.database if not owned else Database()
    if owned:
        database.initialize()
    app.state.database = database
    worker_task = None
    testing = "pytest" in sys.modules or os.environ.get("PYTEST_CURRENT_TEST") is not None
    if not testing and os.environ.get("CLAYBANK_WORKER", "0").strip().lower() in {"1", "true", "yes", "on"}:
        worker_task = asyncio.create_task(worker_loop(database, load_settings()))
    try:
        yield
    finally:
        if worker_task is not None:
            worker_task.cancel()
        if owned:
            database.close()


app = FastAPI(root_path="/api/v1", lifespan=lifespan)
app.add_exception_handler(
    DomainError,
    cast(ExceptionHandler, domain_error_handler),
)
app.include_router(router)


@app.get("/status")
async def status() -> dict[str, str]:
    """Return a lightweight liveness response."""
    return {"status": "running"}