"""Domain errors and their HTTP representation."""

from fastapi import Request
from fastapi.responses import JSONResponse

from Backend.contracts.version import CONTRACT_VERSION, versioned


class DomainError(Exception):
    """Represent a contract-level domain failure."""

    def __init__(self, code: str, message: str, detail: dict | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.detail = detail


async def domain_error_handler(request: Request, exc: DomainError) -> JSONResponse:
    """Map a domain error to the single API error envelope."""
    del request
    status_code = {
        "already_saved": 409,
        "conflict": 409,
        "contract_version_mismatch": 409,
        "unauthorized": 401,
        "not_found": 404,
        "validation": 422,
        "folder_depth_exceeded": 422,
        "reserved_folder_name": 422,
        "index_mismatch": 409,
        "llm_unavailable": 503,
    }.get(exc.code, 422)
    return JSONResponse(
        status_code=status_code,
        content=versioned(
            {
                "error": {
                    "code": exc.code,
                    "message": exc.message,
                    "detail": exc.detail,
                }
            }
        ),
        headers={"X-Contract-Version": str(CONTRACT_VERSION)},
    )
