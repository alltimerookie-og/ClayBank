"""Pydantic models derived from the save contract."""

from datetime import datetime
from uuid import UUID

from pydantic import AnyUrl, BaseModel, ConfigDict


class SaveCapture(BaseModel):
    """Validate the request body defined by ``save-capture.json``."""

    model_config = ConfigDict(extra="forbid")

    url: AnyUrl
    source_app: str = "unknown"
    user_context: str = ""
    suggested_folder_id: UUID | None = None
    force: bool = False


class SavePatch(BaseModel):
    """Validate the request body defined by ``save-patch.json``."""

    model_config = ConfigDict(extra="forbid")

    folder_id: UUID | None = None
    tag_ids: list[UUID] | None = None
    user_context: str | None = None
    updated_at: datetime | None = None


class NotePut(BaseModel):
    """Validate the request body defined by ``note-put.json``."""

    model_config = ConfigDict(extra="forbid")

    markdown: str
    updated_at: datetime


class TagsPut(BaseModel):
    """Validate the request body defined by ``tags-put.json``."""

    model_config = ConfigDict(extra="forbid")

    tag_ids: list[UUID]
    updated_at: datetime | None = None
