"""Pydantic models derived from the organization contract."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class FolderWrite(BaseModel):
    """Validate the request body defined by ``folder-write.json``."""

    model_config = ConfigDict(extra="forbid")

    name: str
    parent_id: UUID | None = None
    archived_at: datetime | None = None


class ClusterMember(BaseModel):
    """Validate one proposed cluster member."""

    model_config = ConfigDict(extra="forbid")

    save_id: UUID
    title: str | None = None


class SuggestionAccept(BaseModel):
    """Validate the request body defined by ``suggestion-accept.json``."""

    model_config = ConfigDict(extra="forbid")

    type: str
    save_id: UUID | None = None
    cluster: list[ClusterMember] | None = None
    path: str
    confidence: float
    accept: bool = True
    dismissed_at: datetime | None = None
