"""Focused tests for the pipeline worker and sync reprocess."""

from pathlib import Path

from fastapi.testclient import TestClient

from Backend.main import app
from Backend.processing.worker import fetch_queued_save_ids, process_due_jobs
from Backend.store.database import Database
from Backend.tests.test_search import HEADERS


def make_client(tmp_path: Path) -> TestClient:
    """Build a test client with an isolated SQLite database."""
    database = Database(tmp_path / "worker.sqlite3")
    database.initialize()
    app.state.database = database
    return TestClient(app)


def test_worker_drains_queued_unknown_save(tmp_path: Path) -> None:
    """The worker finishes a queued job without a live network."""
    with make_client(tmp_path) as client:
        save = client.post("/saves", headers=HEADERS, json={"url": "https://example.com/missing"}).json()["data"]
        assert fetch_queued_save_ids(app.state.database) == [save["id"]]
        done = process_due_jobs(app.state.database)
        assert done == [save["id"]]
        bundle = client.get(f"/saves/{save['id']}", headers=HEADERS).json()["data"]
        assert bundle["job"]["state"] == "ready"
        assert fetch_queued_save_ids(app.state.database) == []


def test_reprocess_run_executes_synchronously(tmp_path: Path) -> None:
    """Opt-in run=true processes inline and returns the finished job."""
    with make_client(tmp_path) as client:
        save = client.post("/saves", headers=HEADERS, json={"url": "https://example.com/missing"}).json()["data"]
        response = client.post(f"/saves/{save['id']}/reprocess?run=true", headers=HEADERS)

        assert response.status_code == 202
        assert response.json()["data"]["state"] == "ready"
        assert response.json()["contract_version"] == 0
