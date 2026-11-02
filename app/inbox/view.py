"""Inbox tab — real GET /saves + GET /saves/{id} job states, cursor paging."""
from __future__ import annotations

import asyncio
import time
import flet as ft

from app.shell.components import banner, save_card
from app.shell.theme import Tokens as T


class InboxView:
    def __init__(self, state, on_add_link, on_open_save) -> None:
        self.state = state
        self.on_add_link = on_add_link
        self.on_open_save = on_open_save
        self.items: list[dict] = []
        self.jobs: dict[str, str] = {}
        self.cursor: str | None = None
        self.loading = False
        self.error: str | None = None
        self.offline = False
        self._polling = False
        self.poll_interval = 2.0
        self.max_duration = 120.0
        self.root = ft.Column(spacing=8, expand=True, scroll=ft.ScrollMode.AUTO)

    def build(self) -> ft.Control:
        return self.root

    async def refresh(self, page: ft.Page, reset: bool = True) -> None:
        if self.loading:
            return
        self.loading = True
        self.error = None
        if reset:
            self.items = []
            self.cursor = None
        self._paint(page, loading=True)
        try:
            res = await self.state.client.list_saves(
                inbox=True, cursor=None if reset else self.cursor, limit=20)
        except Exception as exc:
            # A dropped exception here = "Loading saves..." forever. Surface it.
            # Never include tokens, URLs, or bodies — type name only.
            self.loading = False
            self.offline = True
            self.error = f"{type(exc).__name__} (see logs)"
            self._paint(page)
            return
        self.loading = False
        if not res.ok:
            self.offline = res.status in (0, -1)
            if res.error is not None and res.status not in (0, -1):
                # HTTP error with a contract code (401/422/...) — show the
                # code, never the generic offline line. Chrome-vs-app lesson.
                self.error = f"{res.error.code}: {res.error.message}"
            else:
                self.error = res.error.message if res.error else "Request failed"
            self._paint(page)
            return
        data = res.data if isinstance(res.data, dict) else {}
        page_items = data.get("items", [])
        self.cursor = data.get("cursor")
        self.items.extend(page_items)
        self.offline = False
        # Per-save job state (Phase 1 backend serves {save,note,job}).
        # Serial per-item reads keep the companion event loop responsive and
        # any single failure must not abort the whole list paint.
        for it in page_items:
            try:
                job = await self.state.client.read_save(it["id"])
            except Exception:
                continue
            if job.ok and isinstance(job.data, dict) and job.data.get("job"):
                j = job.data["job"]
                state = "failed" if j.get("error") else (j.get("state") or "queued")
                self.jobs[it["id"]] = state
        self._paint(page)
        self._check_start_polling(page)

    def _check_start_polling(self, page: ft.Page) -> None:
        if self._polling:
            return
        active = any(
            state in ("queued", "extracting", "transcribing", "analyzing", "sorting")
            for state in self.jobs.values()
        )
        if active and hasattr(page, "run_task"):
            page.run_task(self._poll_active_jobs, page)

    async def _poll_active_jobs(self, page: ft.Page) -> None:
        if self._polling:
            return
        self._polling = True
        start_time = time.monotonic()
        try:
            while time.monotonic() - start_time < self.max_duration:
                # Navigation check: stop polling if user left Inbox tab
                if getattr(self.state, "tab", "inbox") != "inbox":
                    break

                # Stop polling when there are no active jobs
                active_ids = [
                    item_id for item_id, state in self.jobs.items()
                    if state in ("queued", "extracting", "transcribing", "analyzing", "sorting")
                ]
                if not active_ids:
                    break

                await asyncio.sleep(self.poll_interval)

                # Navigation check after sleep
                if getattr(self.state, "tab", "inbox") != "inbox":
                    break

                changed = False
                for item_id in active_ids:
                    if getattr(self.state, "tab", "inbox") != "inbox":
                        break
                    try:
                        res = await self.state.client.read_save(item_id)
                    except Exception:
                        continue

                    if res.ok and isinstance(res.data, dict):
                        job_data = res.data.get("job")
                        if job_data:
                            new_state = "failed" if job_data.get("error") else (job_data.get("state") or "queued")
                            if new_state != self.jobs.get(item_id):
                                self.jobs[item_id] = new_state
                                changed = True
                        save_data = res.data.get("save")
                        if save_data and isinstance(save_data, dict):
                            for idx, it in enumerate(self.items):
                                if it.get("id") == item_id:
                                    if it != save_data:
                                        self.items[idx] = save_data
                                        changed = True
                                    break

                if changed:
                    self._paint(page)
        finally:
            self._polling = False

    def _paint(self, page: ft.Page, loading: bool = False) -> None:
        self.root.controls.clear()
        header = ft.Row([
            ft.Text("Inbox", size=22, weight=ft.FontWeight.BOLD, color=T.INK),
            ft.Text(f"{len(self.items)} saves", size=12, color=T.MUTED),
        ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN)
        self.root.controls.append(header)
        if loading and not self.items:
            self.root.controls.append(ft.ProgressBar(color=T.ACCENT))
            self.root.controls.append(ft.Text("Loading saves…", color=T.MUTED))
        elif self.error and not self.items:
            tone = "warn" if self.offline else "info"
            label = ("You're offline — showing nothing yet. Reconnect and refresh."
                     if self.offline else f"Couldn't load inbox: {self.error}")
            self.root.controls.append(banner(label, tone))
            self.root.controls.append(ft.OutlinedButton(
                "Retry", on_click=lambda e: page.run_task(self.refresh, page, True)))
        elif not self.items:
            self.root.controls.append(banner(
                "Nothing here yet. Tap + to save your first link — capture always succeeds.", "info"))
        for it in self.items:
            self.root.controls.append(save_card(
                it, self.jobs.get(it["id"]),
                on_open=lambda e, s=it: self.on_open_save(s)))
        if self.items and not self.loading:
            if self.cursor:
                self.root.controls.append(ft.OutlinedButton(
                    "Load more",
                    on_click=lambda e: page.run_task(self.refresh, page, False)))
            else:
                self.root.controls.append(
                    ft.Text("You're all caught up.", size=12, color=T.MUTED))
        if self.error and self.items:
            self.root.controls.append(
                ft.Text(f"Refresh failed: {self.error}", size=12, color=T.MUTED))
        try:
            page.update()
        except Exception:
            pass
