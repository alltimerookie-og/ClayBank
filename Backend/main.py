"""Create the Claybank FastAPI application."""

from contextlib import asynccontextmanager
from typing import cast

from fastapi import FastAPI
from starlette.types import ExceptionHandler

from Backend.api.routes import router
from Backend.errors import DomainError, domain_error_handler
from Backend.store.database import Database


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Open the application database and close it during shutdown."""
    database = getattr(app.state, "database", None)
    if database is None:
        database = Database()
        database.initialize()
    app.state.database = database
    yield
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