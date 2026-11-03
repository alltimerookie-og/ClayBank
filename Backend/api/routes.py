"""FastAPI routes implemented against the Claybank API contract."""

from typing import Annotated

from fastapi import APIRouter, Depends, Header, Query, Request, Response, status
from fastapi.responses import JSONResponse

from Backend.capture.service import CaptureService
from Backend.contracts.organization import FolderWrite, SuggestionAccept
from Backend.contracts.saves import NotePut, SaveCapture, SavePatch, TagsPut
from Backend.contracts.search import AskRequest, SearchQuery
from Backend.contracts.sync import SyncPush
from Backend.contracts.version import (
    CONTRACT_VERSION,
    require_contract_version,
    versioned,
)
from Backend.errors import DomainError
from Backend.organization.service import FolderService
from Backend.search.service import SearchService
from Backend.store.database import Database
from Backend.sync.service import SyncService

router = APIRouter()

VERSION_HEADER = "X-Contract-Version"

VersionHeader = Annotated[str | None, Header(alias="x-contract-version")]


def versioned_response(payload: dict, status_code: int = status.HTTP_200_OK) -> JSONResponse:
    """Return a versioned data envelope with the contract header."""
    return JSONResponse(
        status_code=status_code,
        content=versioned({"data": payload}),
        headers={VERSION_HEADER: str(CONTRACT_VERSION)},
    )


def get_database(request: Request) -> Database:
    """Return the database attached to the application lifespan."""
    return request.app.state.database


def get_capture_service(
    database: Annotated[Database, Depends(get_database)],
) -> CaptureService:
    """Build the capture service for a request."""
    return CaptureService(database)


@router.post("/saves", status_code=status.HTTP_201_CREATED)
async def capture_save(
    payload: SaveCapture,
    service: Annotated[CaptureService, Depends(get_capture_service)],
    authorization: Annotated[str | None, Header()] = None,
    x_device_id: Annotated[str | None, Header()] = None,
    idempotency_key: Annotated[str | None, Header()] = None,
    x_contract_version: VersionHeader = None,
) -> JSONResponse:
    """Persist a capture without waiting for downstream processing."""
    require_contract_version(x_contract_version)
    if authorization != "Bearer DEV_TOKEN" or not x_device_id:
        raise DomainError("unauthorized", "Valid DEV_TOKEN and X-Device-Id are required")

    try:
        result, replay = service.capture(
            payload,
            user_id="dev-user",
            device_id=x_device_id,
            idempotency_key=idempotency_key,
        )
    except DomainError:
        raise

    response_status = status.HTTP_200_OK if replay else status.HTTP_201_CREATED
    return versioned_response(result, status_code=response_status)


def require_auth(
    authorization: str | None,
    x_device_id: str | None,
) -> None:
    """Validate the MVP bearer token and device identity."""
    if authorization != "Bearer DEV_TOKEN" or not x_device_id:
        raise DomainError("unauthorized", "Valid DEV_TOKEN and X-Device-Id are required")


@router.get("/saves")
async def list_saves(
    request: Request,
    authorization: Annotated[str | None, Header()] = None,
    x_device_id: Annotated[str | None, Header()] = None,
    cursor: str | None = None,
    folder_id: str | None = None,
    inbox: bool = False,
    needs_review: bool | None = None,
    kind: str | None = Query(default=None, pattern="^(video|article|unknown)$"),
    x_contract_version: VersionHeader = None,
) -> JSONResponse:
    """List saves using the contract filters."""
    require_contract_version(x_contract_version)
    require_auth(authorization, x_device_id)
    service = CaptureService(get_database(request))
    return versioned_response(service.list_saves(
        folder_id=folder_id,
        inbox=inbox,
        needs_review=needs_review,
        kind=kind,
        cursor=cursor,
    ))


@router.get("/saves/{save_id}")
async def get_save(
    save_id: str,
    request: Request,
    authorization: Annotated[str | None, Header()] = None,
    x_device_id: Annotated[str | None, Header()] = None,
    x_contract_version: VersionHeader = None,
) -> JSONResponse:
    """Return one save with its note and job."""
    require_contract_version(x_contract_version)
    require_auth(authorization, x_device_id)
    return versioned_response(CaptureService(get_database(request)).get_save_bundle(save_id))


@router.patch("/saves/{save_id}")
async def patch_save(
    save_id: str,
    payload: SavePatch,
    request: Request,
    authorization: Annotated[str | None, Header()] = None,
    x_device_id: Annotated[str | None, Header()] = None,
    idempotency_key: Annotated[str | None, Header()] = None,
    x_contract_version: VersionHeader = None,
) -> JSONResponse:
    """Update mutable save fields."""
    del idempotency_key
    require_contract_version(x_contract_version)
    require_auth(authorization, x_device_id)
    return versioned_response(CaptureService(get_database(request)).patch_save(save_id, payload))


@router.delete("/saves/{save_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_save(
    save_id: str,
    request: Request,
    authorization: Annotated[str | None, Header()] = None,
    x_device_id: Annotated[str | None, Header()] = None,
    x_contract_version: VersionHeader = None,
) -> Response:
    """Delete a save and its cascade-owned records."""
    require_contract_version(x_contract_version)
    require_auth(authorization, x_device_id)
    CaptureService(get_database(request)).delete_save(save_id)
    return Response(
        status_code=status.HTTP_204_NO_CONTENT,
        headers={VERSION_HEADER: str(CONTRACT_VERSION)},
    )


@router.put("/saves/{save_id}/tags")
async def put_save_tags(
    save_id: str,
    payload: TagsPut,
    request: Request,
    authorization: Annotated[str | None, Header()] = None,
    x_device_id: Annotated[str | None, Header()] = None,
    idempotency_key: Annotated[str | None, Header()] = None,
    x_contract_version: VersionHeader = None,
) -> JSONResponse:
    """Replace a save's complete tag set."""
    del idempotency_key
    require_contract_version(x_contract_version)
    require_auth(authorization, x_device_id)
    service = CaptureService(get_database(request))
    return versioned_response(service.replace_save_tags(save_id, payload))


@router.put("/saves/{save_id}/note")
async def put_note(
    save_id: str,
    payload: NotePut,
    request: Request,
    authorization: Annotated[str | None, Header()] = None,
    x_device_id: Annotated[str | None, Header()] = None,
    idempotency_key: Annotated[str | None, Header()] = None,
    x_contract_version: VersionHeader = None,
) -> JSONResponse:
    """Replace a save's Markdown note."""
    del idempotency_key
    require_contract_version(x_contract_version)
    require_auth(authorization, x_device_id)
    return versioned_response(CaptureService(get_database(request)).put_note(save_id, payload))


@router.post("/saves/{save_id}/reprocess", status_code=status.HTTP_202_ACCEPTED)
async def reprocess_save(
    save_id: str,
    request: Request,
    from_stage: str | None = Query(default=None, alias="from"),
    authorization: Annotated[str | None, Header()] = None,
    x_device_id: Annotated[str | None, Header()] = None,
    x_contract_version: VersionHeader = None,
) -> JSONResponse:
    """Requeue processing from a selected pipeline stage."""
    require_contract_version(x_contract_version)
    if from_stage is not None and from_stage not in {
        "extracting",
        "transcribing",
        "analyzing",
        "sorting",
    }:
        raise DomainError("validation", "Invalid reprocess stage")
    require_auth(authorization, x_device_id)
    return versioned_response(
        CaptureService(get_database(request)).reprocess(save_id, from_stage),
        status_code=status.HTTP_202_ACCEPTED,
    )


@router.post("/folders", status_code=status.HTTP_201_CREATED)
async def create_folder(
    payload: FolderWrite,
    request: Request,
    authorization: Annotated[str | None, Header()] = None,
    x_device_id: Annotated[str | None, Header()] = None,
    idempotency_key: Annotated[str | None, Header()] = None,
    x_contract_version: VersionHeader = None,
) -> JSONResponse:
    """Create a folder from an explicit user action."""
    del idempotency_key
    require_contract_version(x_contract_version)
    require_auth(authorization, x_device_id)
    return versioned_response(
        FolderService(get_database(request)).create_folder(payload),
        status_code=status.HTTP_201_CREATED,
    )


@router.get("/folders")
async def list_folders(
    request: Request,
    authorization: Annotated[str | None, Header()] = None,
    x_device_id: Annotated[str | None, Header()] = None,
    cursor: str | None = None,
    x_contract_version: VersionHeader = None,
) -> JSONResponse:
    """List folders with a cursor envelope."""
    require_contract_version(x_contract_version)
    require_auth(authorization, x_device_id)
    return versioned_response(FolderService(get_database(request)).list_folders(cursor=cursor))


@router.patch("/folders/{folder_id}")
async def patch_folder(
    folder_id: str,
    payload: FolderWrite,
    request: Request,
    authorization: Annotated[str | None, Header()] = None,
    x_device_id: Annotated[str | None, Header()] = None,
    idempotency_key: Annotated[str | None, Header()] = None,
    x_contract_version: VersionHeader = None,
) -> JSONResponse:
    """Rename, move, or archive one folder."""
    del idempotency_key
    require_contract_version(x_contract_version)
    require_auth(authorization, x_device_id)
    return versioned_response(FolderService(get_database(request)).patch_folder(folder_id, payload))


@router.delete("/folders/{folder_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_folder(
    folder_id: str,
    request: Request,
    authorization: Annotated[str | None, Header()] = None,
    x_device_id: Annotated[str | None, Header()] = None,
    x_contract_version: VersionHeader = None,
) -> Response:
    """Delete a folder and return member saves to the Inbox."""
    require_contract_version(x_contract_version)
    require_auth(authorization, x_device_id)
    FolderService(get_database(request)).delete_folder(folder_id)
    return Response(
        status_code=status.HTTP_204_NO_CONTENT,
        headers={VERSION_HEADER: str(CONTRACT_VERSION)},
    )


@router.get("/suggestions")
async def list_suggestions(
    request: Request,
    authorization: Annotated[str | None, Header()] = None,
    x_device_id: Annotated[str | None, Header()] = None,
    x_contract_version: VersionHeader = None,
) -> JSONResponse:
    """Return review saves and outstanding cluster proposals."""
    require_contract_version(x_contract_version)
    require_auth(authorization, x_device_id)
    database = get_database(request)
    service = FolderService(database)
    return versioned_response(service.list_suggestions(CaptureService(database)))


@router.post("/suggestions/accept")
async def accept_suggestion(
    payload: SuggestionAccept,
    request: Request,
    authorization: Annotated[str | None, Header()] = None,
    x_device_id: Annotated[str | None, Header()] = None,
    idempotency_key: Annotated[str | None, Header()] = None,
    x_contract_version: VersionHeader = None,
) -> JSONResponse:
    """Accept or dismiss one single or cluster suggestion."""
    del idempotency_key
    require_contract_version(x_contract_version)
    require_auth(authorization, x_device_id)
    database = get_database(request)
    service = FolderService(database)
    folder = service.accept_suggestion(payload, CaptureService(database))
    if folder is None:
        raise DomainError("validation", "Suggestion dismissed")
    return versioned_response(folder)


@router.get("/search")
async def search_saves(
    request: Request,
    q: str,
    authorization: Annotated[str | None, Header()] = None,
    x_device_id: Annotated[str | None, Header()] = None,
    folder_scope: str | None = None,
    cursor: str | None = None,
    x_contract_version: VersionHeader = None,
) -> JSONResponse:
    """Search saves with keyword plus semantic retrieval."""
    require_contract_version(x_contract_version)
    require_auth(authorization, x_device_id)
    query = SearchQuery(q=q, folder_scope=folder_scope, cursor=cursor)
    return versioned_response(SearchService(get_database(request)).search(query))


@router.post("/ask")
async def ask_library(
    payload: AskRequest,
    request: Request,
    authorization: Annotated[str | None, Header()] = None,
    x_device_id: Annotated[str | None, Header()] = None,
    x_contract_version: VersionHeader = None,
) -> JSONResponse:
    """Answer a folder- or library-scoped question with citations."""
    require_contract_version(x_contract_version)
    require_auth(authorization, x_device_id)
    return versioned_response(SearchService(get_database(request)).ask(payload))


@router.get("/sync/pull")
async def sync_pull(
    request: Request,
    since: str,
    authorization: Annotated[str | None, Header()] = None,
    x_device_id: Annotated[str | None, Header()] = None,
    x_contract_version: VersionHeader = None,
) -> JSONResponse:
    """Pull everything changed since a cursor."""
    require_contract_version(x_contract_version)
    require_auth(authorization, x_device_id)
    return versioned_response(SyncService(get_database(request)).pull(since))


@router.post("/sync/push")
async def sync_push(
    payload: SyncPush,
    request: Request,
    authorization: Annotated[str | None, Header()] = None,
    x_device_id: Annotated[str | None, Header()] = None,
    idempotency_key: Annotated[str | None, Header()] = None,
    x_contract_version: VersionHeader = None,
) -> JSONResponse:
    """Replay queued offline writes with per-operation results."""
    del idempotency_key
    require_contract_version(x_contract_version)
    require_auth(authorization, x_device_id)
    return versioned_response(SyncService(get_database(request)).push(payload, user_id="dev-user"))
