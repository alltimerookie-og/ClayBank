"""ClayBank Phase 2 application — 4-tab shell over the real Phase 1 backend.

Evolves the Phase 1 companion shell in place: splash → onboarding →
Inbox/Folders/Search/Settings + Add-link sheet + note dialog + offline outbox.
Folders/Search/Settings show honest phase-locked states; Ask never a 5th tab.
"""
from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path

# Ensure repo root is importable whether launched as `python app/main.py`,
# `flet run app/main.py`, or `flet run --android app/main.py`.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import flet as ft

from app.capture.sheet import AddLinkSheet
from app.client_config import DEV_TOKEN_DEFAULT, resolve_api_base
from app.inbox.view import InboxView
from app.note.dialog import open_note_dialog
from app.note.editor import open_note_editor
from app.shell.onboarding import onboarding, splash
from app.shell.state import TABS, build_state
from app.shell.tabs import folders_tab, search_tab, settings_tab
from app.shell.theme import Tokens as T

log = logging.getLogger(__name__)


class ClayBankApp:
    def __init__(self, page: ft.Page, api_base: str, dev_token: str,
                 device_id: str) -> None:
        self.page = page
        self.state = build_state(api_base, dev_token, device_id)
        self.inbox = InboxView(self.state, self.open_sheet, self.open_save)
        self.sheet = AddLinkSheet(self.state, self.after_saved)
        self.conn = ft.Text("Checking backend…", size=12, color=T.MUTED)
        self.body = ft.Container(expand=True, padding=12)
        self.nav = ft.NavigationBar(
            selected_index=0, bgcolor=T.CARD,
            destinations=[
                ft.NavigationBarDestination(icon=ft.Icons.ALL_INBOX_OUTLINED,
                                            selected_icon=ft.Icons.ALL_INBOX,
                                            label="Inbox"),
                ft.NavigationBarDestination(icon=ft.Icons.FOLDER_OUTLINED,
                                            selected_icon=ft.Icons.FOLDER,
                                            label="Folders"),
                ft.NavigationBarDestination(icon=ft.Icons.SEARCH_OUTLINED,
                                            selected_icon=ft.Icons.SEARCH,
                                            label="Search"),
                ft.NavigationBarDestination(icon=ft.Icons.SETTINGS_OUTLINED,
                                            selected_icon=ft.Icons.SETTINGS,
                                            label="Settings"),
            ], on_change=self._nav_changed)
    async def boot(self) -> None:
        page = self.page
        page.title = "ClayBank"
        page.bgcolor = T.BG
        page.theme_mode = ft.ThemeMode.LIGHT
        await splash(page, self.state, self._after_splash)

    async def _after_splash(self) -> None:
        if not self.state.onboarding_done:
            await onboarding(self.page, self.state, self.enter)
        else:
            await self.enter()

    async def enter(self) -> None:
        page = self.page
        page.clean()
        page.floating_action_button = ft.FloatingActionButton(
            icon=ft.Icons.ADD, bgcolor=T.ACCENT, foreground_color=T.ACCENT_FG,
            on_click=lambda e: self.open_sheet())
        page.navigation_bar = self.nav
        # SafeArea keeps the header clear of the Android status bar / notch.
        page.add(ft.SafeArea(ft.Column([
            ft.Row([ft.Text("ClayBank", weight=ft.FontWeight.BOLD, color=T.INK),
                    self.conn],
                   alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
            self.body,
        ], expand=True), expand=True))
        await self.show_tab("inbox")
        page.run_task(self._check_connection)

    async def _check_connection(self) -> None:
        res = await self.state.client.health()
        if res.ok:
            self.state.connected = True
            self.conn.value = f"connected · {self.state.api_base}"
            self.conn.color = T.OK_INK
        else:
            self.state.connected = False
            # Distinguish transport (status 0/-1) from HTTP errors so a 401
            # never masquerades as "offline" the way Chrome-vs-app did.
            code = res.error.code if res.error else f"http_{res.status}"
            self.conn.value = ("offline — saves queue on device"
                               if res.status in (0, -1)
                               else f"backend {res.status} {code}")
            self.conn.color = T.MUTED
        self.page.update()

    def _nav_changed(self, e) -> None:
        # NavigationBar on_change fires with e.data == selected index (string).
        # Companion/desktop payloads differ, so resolve defensively and swap
        # the body content synchronously — never leave a stale tab mounted.
        try:
            idx = int(e.data)
        except (TypeError, ValueError):
            try:
                idx = int(e.control.selected_index)
            except (TypeError, ValueError, AttributeError):
                return
        tab = TABS[max(0, min(idx, len(TABS) - 1))]
        self.state.tab = tab
        self.nav.selected_index = idx
        if tab == "inbox":
            self.body.content = self.inbox.build()
        elif tab == "folders":
            self.body.content = folders_tab()
        elif tab == "search":
            self.body.content = search_tab()
        else:
            self.body.content = settings_tab(self.state)
        self.page.update()
        if tab == "inbox":
            e.page.run_task(self.inbox.refresh, self.page, True)

    async def show_tab(self, tab: str) -> None:
        self.state.tab = tab
        self.nav.selected_index = TABS.index(tab)
        self.body.content = None
        if tab == "inbox":
            self.body.content = self.inbox.build()
            await self.inbox.refresh(self.page, reset=True)
            return
        if tab == "folders":
            self.body.content = folders_tab()
        elif tab == "search":
            self.body.content = search_tab()
        else:
            self.body.content = settings_tab(self.state)
        self.page.update()

    def open_sheet(self, prefill: str = "") -> None:
        self.sheet.open(self.page, prefill=prefill)

    async def after_saved(self, save: dict) -> None:
        self.page.overlay.append(ft.SnackBar(content=ft.Text("Saved ✓")))
        self.page.update()
        if self.state.tab == "inbox":
            await self.inbox.refresh(self.page, reset=True)
        self.page.run_task(self._check_connection)

    async def open_save(self, save: dict) -> None:
        open_note_editor(self.page, self.state, save)


async def _run(page: ft.Page, api_base: str, token: str, device: str) -> None:
    await ClayBankApp(page, api_base, token, device).boot()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--api", default=None)
    parser.add_argument("--token", default=None)
    parser.add_argument("--device", default="dev-device-01")
    args, _ = parser.parse_known_args()
    api_base = resolve_api_base(args.api or os.environ.get("CLAYBANK_API_URL"))
    token = args.token or os.environ.get("DEV_TOKEN") or DEV_TOKEN_DEFAULT

    async def _target(page: ft.Page):
        await _run(page, api_base, token, args.device)

    ft.run(_target)


if __name__ == "__main__":
    main()
