"""Tests for Phase 3 Task 6: Inbox UI processing status polling."""
from __future__ import annotations

import asyncio
import os
import sys
import time
from typing import Any, cast

import flet as ft

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.api_client import ApiResult
from app.inbox.view import InboxView


class FakeClient:
    def __init__(self, saves=None, read_responses=None):
        self.saves = saves or []
        self.read_responses = read_responses or {}
        self.read_calls: list[str] = []

    async def list_saves(self, inbox=True, cursor=None, limit=20):
        return ApiResult(ok=True, status=200, data={"items": self.saves, "cursor": None})

    async def read_save(self, save_id):
        self.read_calls.append(save_id)
        if save_id in self.read_responses:
            resp = self.read_responses[save_id]
            if callable(resp):
                return resp()
            return resp
        return ApiResult(
            ok=True,
            status=200,
            data={
                "save": {"id": save_id, "title": "Test Save", "url": "https://example.com"},
                "job": {"save_id": save_id, "state": "ready", "error": None},
            },
        )


class FakeState:
    def __init__(self, client=None, tab="inbox"):
        self.client = client or FakeClient()
        self.tab = tab


class FakePage:
    def __init__(self):
        self.tasks: list[tuple[Any, tuple[Any, ...]]] = []
        self.updates: int = 0

    def run_task(self, fn: Any, *args: Any) -> None:
        self.tasks.append((fn, args))

    def update(self) -> None:
        self.updates += 1


def test_polling_starts_when_active_jobs_present():
    client = FakeClient(
        saves=[{"id": "s1", "title": "Vid", "url": "https://youtube.com/watch?v=1"}],
        read_responses={
            "s1": ApiResult(
                ok=True,
                status=200,
                data={
                    "save": {"id": "s1", "title": "Vid", "url": "https://youtube.com/watch?v=1"},
                    "job": {"save_id": "s1", "state": "extracting", "error": None},
                },
            )
        },
    )
    state = FakeState(client=client)
    page = FakePage()
    view = InboxView(state, on_add_link=lambda: None, on_open_save=lambda s: None)

    asyncio.run(view.refresh(cast(ft.Page, page)))

    assert view.jobs["s1"] == "extracting"
    assert len(page.tasks) == 1
    assert page.tasks[0][0] == view._poll_active_jobs


def test_polling_does_not_start_when_all_jobs_terminal():
    client = FakeClient(
        saves=[{"id": "s1", "title": "Article", "url": "https://example.com"}],
        read_responses={
            "s1": ApiResult(
                ok=True,
                status=200,
                data={
                    "save": {"id": "s1", "title": "Article", "url": "https://example.com"},
                    "job": {"save_id": "s1", "state": "ready", "error": None},
                },
            )
        },
    )
    state = FakeState(client=client)
    page = FakePage()
    view = InboxView(state, on_add_link=lambda: None, on_open_save=lambda s: None)

    asyncio.run(view.refresh(cast(ft.Page, page)))

    assert view.jobs["s1"] == "ready"
    assert len(page.tasks) == 0


def test_poll_updates_state_and_terminates_on_completion():
    states = ["extracting", "transcribing", "ready"]
    idx = 0

    def get_resp():
        nonlocal idx
        st = states[min(idx, len(states) - 1)]
        idx += 1
        return ApiResult(
            ok=True,
            status=200,
            data={
                "save": {"id": "s1", "title": "Done Title", "url": "https://example.com"},
                "job": {"save_id": "s1", "state": st, "error": None},
            },
        )

    client = FakeClient(read_responses={"s1": get_resp})
    state = FakeState(client=client)
    page = FakePage()
    view = InboxView(state, on_add_link=lambda: None, on_open_save=lambda s: None)
    view.items = [{"id": "s1", "title": "Old Title", "url": "https://example.com"}]
    view.jobs["s1"] = "queued"
    view.poll_interval = 0.01  # fast for testing

    asyncio.run(view._poll_active_jobs(cast(ft.Page, page)))

    assert view.jobs["s1"] == "ready"
    assert view.items[0]["title"] == "Done Title"
    assert view._polling is False


def test_poll_terminates_immediately_on_navigation_away():
    client = FakeClient()
    state = FakeState(client=client, tab="inbox")
    page = FakePage()
    view = InboxView(state, on_add_link=lambda: None, on_open_save=lambda s: None)
    view.jobs["s1"] = "extracting"
    view.poll_interval = 0.01

    # Switch tab before polling starts
    state.tab = "folders"
    asyncio.run(view._poll_active_jobs(cast(ft.Page, page)))

    assert view._polling is False
    assert len(client.read_calls) == 0


def test_poll_terminates_on_navigation_during_sleep():
    call_count = 0

    def slow_resp():
        nonlocal call_count
        call_count += 1
        return ApiResult(
            ok=True,
            status=200,
            data={
                "save": {"id": "s1", "title": "T"},
                "job": {"save_id": "s1", "state": "extracting", "error": None},
            },
        )

    client = FakeClient(read_responses={"s1": slow_resp})
    state = FakeState(client=client, tab="inbox")
    page = FakePage()
    view = InboxView(state, on_add_link=lambda: None, on_open_save=lambda s: None)
    view.jobs["s1"] = "extracting"
    view.poll_interval = 0.02

    async def run_and_navigate():
        task = asyncio.create_task(view._poll_active_jobs(cast(ft.Page, page)))
        await asyncio.sleep(0.01)
        state.tab = "search"
        await task

    asyncio.run(run_and_navigate())
    assert view._polling is False


def test_poll_terminates_on_timeout():
    def stuck_resp():
        return ApiResult(
            ok=True,
            status=200,
            data={
                "save": {"id": "s1", "title": "T"},
                "job": {"save_id": "s1", "state": "extracting", "error": None},
            },
        )

    client = FakeClient(read_responses={"s1": stuck_resp})
    state = FakeState(client=client, tab="inbox")
    page = FakePage()
    view = InboxView(state, on_add_link=lambda: None, on_open_save=lambda s: None)
    view.jobs["s1"] = "extracting"
    view.poll_interval = 0.01
    view.max_duration = 0.03  # expires in 30ms

    start = time.monotonic()
    asyncio.run(view._poll_active_jobs(cast(ft.Page, page)))
    elapsed = time.monotonic() - start

    assert elapsed < 0.2
    assert view._polling is False


def test_poll_maps_error_to_failed_state():
    client = FakeClient(
        read_responses={
            "s1": ApiResult(
                ok=True,
                status=200,
                data={
                    "save": {"id": "s1", "title": "T"},
                    "job": {"save_id": "s1", "state": "ready", "error": "Extraction failed: 404"},
                },
            )
        }
    )
    state = FakeState(client=client, tab="inbox")
    page = FakePage()
    view = InboxView(state, on_add_link=lambda: None, on_open_save=lambda s: None)
    view.jobs["s1"] = "extracting"
    view.poll_interval = 0.01

    asyncio.run(view._poll_active_jobs(cast(ft.Page, page)))

    assert view.jobs["s1"] == "failed"
    assert view._polling is False


def test_poll_handles_exception_without_crashing():
    def throwing_resp():
        raise RuntimeError("Network reset")

    client = FakeClient(read_responses={"s1": throwing_resp})
    state = FakeState(client=client, tab="inbox")
    page = FakePage()
    view = InboxView(state, on_add_link=lambda: None, on_open_save=lambda s: None)
    view.jobs["s1"] = "extracting"
    view.poll_interval = 0.01
    view.max_duration = 0.02

    # Must complete cleanly without raising
    asyncio.run(view._poll_active_jobs(cast(ft.Page, page)))
    assert view._polling is False


def test_polling_does_not_spawn_duplicate_tasks():
    client = FakeClient()
    state = FakeState(client=client)
    page = FakePage()
    view = InboxView(state, on_add_link=lambda: None, on_open_save=lambda s: None)
    view.jobs["s1"] = "extracting"
    view._polling = True

    view._check_start_polling(cast(ft.Page, page))
    assert len(page.tasks) == 0
