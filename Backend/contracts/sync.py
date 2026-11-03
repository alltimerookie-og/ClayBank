"""Pydantic models derived from the sync contract."""

from uuid import UUID

from pydantic import BaseModel, ConfigDict


class SyncOperation(BaseModel):
    """Validate one queued offline operation."""

    model_config = ConfigDict(extra="forbid")

    op: str
    payload: dict
    idempotency_key: str


class SyncPush(BaseModel):
    """Validate the request body defined by ``sync-push.json``."""

    model_config = ConfigDict(extra="forbid")

    ops: list[SyncOperation]
    device_cursor: str | None = None
