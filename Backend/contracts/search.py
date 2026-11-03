"""Pydantic models derived from the search and Ask contract."""

from uuid import UUID

from pydantic import BaseModel, ConfigDict


class SearchQuery(BaseModel):
    """Validate the documented ``search-request.json`` query object."""

    model_config = ConfigDict(extra="forbid")

    q: str
    folder_scope: UUID | None = None
    cursor: str | None = None


class AskRequest(BaseModel):
    """Validate the request body defined by ``ask-request.json``."""

    model_config = ConfigDict(extra="forbid")

    question: str
    save_scope: str | None = None
    engine: str = "cloud"
