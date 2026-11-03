"""Contract version single source.

The authoritative value lives in ``Docs/api/openapi.yaml`` as
``x-contract-version``; this module exposes it to the API layer so request
checks and response envelopes cannot drift from the contract.
"""

from __future__ import annotations

import pathlib
import re

_OPENAPI_PATH = pathlib.Path(__file__).resolve().parents[2] / "Docs" / "api" / "openapi.yaml"


def _load_contract_version() -> int:
    """Read ``x-contract-version`` from the OpenAPI contract."""
    match = re.search(
        r"x-contract-version:\s*(\d+)",
        _OPENAPI_PATH.read_text(encoding="utf-8"),
    )
    if match is None:
        raise RuntimeError("x-contract-version is missing from Docs/api/openapi.yaml")
    return int(match.group(1))


CONTRACT_VERSION: int = _load_contract_version()


def require_contract_version(contract_version: str | int | None) -> None:
    """Reject stale clients with the locked mismatch code."""
    from Backend.errors import DomainError

    if contract_version is None:
        return
    try:
        client_version = int(contract_version)
    except (TypeError, ValueError):
        raise DomainError(
            "contract_version_mismatch",
            "Unsupported contract version",
            {"client_contract_version": contract_version, "server_contract_version": CONTRACT_VERSION},
        ) from None
    if client_version != CONTRACT_VERSION:
        raise DomainError(
            "contract_version_mismatch",
            "Client contract is out of date; update the app",
            {"client_contract_version": client_version, "server_contract_version": CONTRACT_VERSION},
        )


def versioned(payload: dict) -> dict:
    """Add the contract version beside a ``data``/``error`` envelope."""
    return {**payload, "contract_version": CONTRACT_VERSION}
