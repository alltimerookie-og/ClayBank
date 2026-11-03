"""Focused tests for contract-version response handling."""

from pathlib import Path

from fastapi.testclient import TestClient

from Backend.contracts.version import CONTRACT_VERSION
from Backend.main import app
from Backend.store.database import Database
from Backend.tests.test_search import HEADERS as AUTH_HEADERS


def make_client(tmp_path: Path) -> TestClient:
    """Build a test client with an isolated SQLite database."""
    database = Database(tmp_path / "version.sqlite3")
    database.initialize()
    app.state.database = database
    return TestClient(app)


def create_save(client) -> dict:
    """Create one save and return its wire representation."""
    post = client.post("/saves", headers=AUTH_HEADERS, json={"url": "https://example.com/item"})
    assert post.status_code == 201
    return post.json()["data"]


def test_success_carries_contract_version_and_header(tmp_path: Path) -> None:
    """Success envelopes carry the contract version in body and header."""
    with make_client(tmp_path) as client:
        create_save(client)
        response = client.get("/saves?inbox=true", headers=AUTH_HEADERS)

        assert response.status_code == 200
        assert response.json()["contract_version"] == CONTRACT_VERSION
        assert response.headers["X-Contract-Version"] == str(CONTRACT_VERSION)


def test_explicit_current_version_is_accepted(tmp_path: Path) -> None:
    """A client sending the current version keeps working."""
    with make_client(tmp_path) as client:
        response = client.get(
            "/saves",
            headers={**AUTH_HEADERS, "X-Contract-Version": str(CONTRACT_VERSION)},
        )

        assert response.status_code == 200
        assert response.json()["contract_version"] == CONTRACT_VERSION


def test_stale_version_returns_mismatch(tmp_path: Path) -> None:
    """A stale explicit version fails with the locked 409 code."""
    with make_client(tmp_path) as client:
        response = client.get(
            "/saves",
            headers={**AUTH_HEADERS, "X-Contract-Version": str(CONTRACT_VERSION + 1)},
        )

        assert response.status_code == 409
        body = response.json()
        assert body["error"]["code"] == "contract_version_mismatch"
        assert body["error"]["detail"]["server_contract_version"] == CONTRACT_VERSION
        assert body["contract_version"] == CONTRACT_VERSION
        assert response.headers["X-Contract-Version"] == str(CONTRACT_VERSION)


def test_error_envelope_carries_contract_version(tmp_path: Path) -> None:
    """Non-version errors also carry the version for client gating."""
    with make_client(tmp_path) as client:
        response = client.get("/saves/does-not-exist", headers=AUTH_HEADERS)

        assert response.status_code == 404
        assert response.json()["contract_version"] == CONTRACT_VERSION
