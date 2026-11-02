"""Integration tests for Phase 6 Search & Ask Coordinator (P6-05).

Covers:
- AppShellLayout Tab 2 integration with SearchView and set_search_view.
- FolderDetailView overflow menu "Ask folder" integration.
- ClayBankApp Tab 2 navigation to SearchView.
- Opening AskView from library search banner.
- Opening AskView from folder detail overflow menu.
- AskView back button returning to previous view context.
- Citation chip navigation from AskView to ItemNoteView with jump_target.
- Returning from ItemNoteView back to AskView.
- ClayBankApp search and ask query dispatchers with citation invariants.
"""

from __future__ import annotations

import flet as ft
import pytest

from app.app import ClayBankApp
from app.shell.app_shell import AppShellLayout
from app.shell.nav import TAB_FOLDERS, TAB_INBOX, TAB_SEARCH
from app.views.folders.folder_detail_view import FolderDetailView
from app.views.note.note_view import ItemNoteView
from app.views.search.ask_view import AskView
from app.views.search.search_view import SearchView


def test_app_shell_search_view_integration():
    """AppShellLayout hosts SearchView at TAB_SEARCH and supports set_search_view."""
    search_placeholder = ft.Container(content=ft.Text("Initial Search"))
    shell = AppShellLayout(search_view=search_placeholder, initial_tab=TAB_SEARCH)

    assert shell.selected_index == TAB_SEARCH
    assert shell.content_area.content is search_placeholder

    updated_search = SearchView()
    shell.set_search_view(updated_search)
    assert shell.tab_views[TAB_SEARCH] is updated_search
    assert shell.content_area.content is updated_search


def test_folder_detail_view_ask_folder_menu():
    """FolderDetailView overflow menu contains 'Ask folder' and triggers callback."""
    asked: list[tuple[str, str]] = []

    def on_ask(folder_id: str, folder_name: str) -> None:
        asked.append((folder_id, folder_name))

    folder_data = {"id": "f_cook_01", "name": "Cooking", "save_count": 5}
    view = FolderDetailView(
        folder_data=folder_data,
        on_ask_folder=on_ask,
    )

    # Check overflow menu items
    menu_items = view.overflow_menu.items
    assert len(menu_items) >= 1
    # First item is Ask folder
    first_item = menu_items[0]
    row = first_item.content
    assert isinstance(row, ft.Row)
    texts = [c for c in row.controls if isinstance(c, ft.Text)]
    assert any(t.value == "Ask folder" for t in texts)

    # Trigger action
    view._handle_ask_folder()
    assert asked == [("f_cook_01", "Cooking")]


def test_claybank_app_search_tab_and_ask_library_flow():
    """ClayBankApp routes to SearchView on Tab 2 and can open library-scoped AskView."""
    sample_saves = [
        {
            "id": "save_bread_01",
            "title": "Sourdough Bread Science",
            "url": "https://example.com/bread",
            "tags": ["baking", "sourdough"],
        },
    ]

    app = ClayBankApp(has_seen_onboarding=True, saves=sample_saves)
    app.transition_to_shell()

    # Verify search view is wired to TAB_SEARCH
    app.app_shell.set_tab(TAB_SEARCH)
    assert isinstance(app.app_shell.content_area.content, SearchView)
    search_view = app.app_shell.content_area.content

    # Open Ask from library banner
    search_view._handle_open_ask()
    assert isinstance(app.viewport.content, AskView)
    assert app.current_ask_view is not None
    assert app.current_ask_view.scope == "library"

    # Close AskView and verify return to AppShell
    app.close_ask_view()
    assert app.current_ask_view is None
    assert app.viewport.content is app.app_shell


def test_claybank_app_folder_to_ask_folder_flow():
    """Triggering Ask folder in FolderDetailView opens folder-scoped AskView."""
    folders = [
        {"id": "f_recipes_01", "name": "Recipes", "parent_id": None, "save_count": 3},
    ]
    app = ClayBankApp(has_seen_onboarding=True, folders=folders)
    app.transition_to_shell()

    detail_view = app.open_folder_detail_view("f_recipes_01")
    assert app.viewport.content is detail_view

    # Trigger Ask folder
    detail_view._handle_ask_folder()
    assert isinstance(app.viewport.content, AskView)
    assert app.current_ask_view is not None
    assert app.current_ask_view.scope == "f_recipes_01"
    assert app.current_ask_view.folder_name == "Recipes"

    # Close AskView and verify return to folder detail view
    app.close_ask_view()
    assert app.viewport.content is detail_view


def test_ask_view_citation_jump_to_note_and_back():
    """Clicking citation in AskView opens ItemNoteView with jump_target and back restores AskView."""
    sample_saves = [
        {
            "id": "save_sourdough_01",
            "title": "Tartine Sourdough Guide",
            "url": "https://example.com/tartine",
            "tags": ["baking"],
        },
    ]
    app = ClayBankApp(has_seen_onboarding=True, saves=sample_saves)
    app.transition_to_shell()

    ask_view = app.open_ask_view(scope="library")
    assert app.viewport.content is ask_view

    # Simulate citation click
    assert ask_view.on_click_citation is not None
    ask_view.on_click_citation("save_sourdough_01", "fermentation")

    # Should have navigated to ItemNoteView
    assert isinstance(app.viewport.content, ItemNoteView)
    assert app.current_note_view is not None
    assert app.current_note_view.save_id == "save_sourdough_01"
    assert app.current_note_view.jump_target == "fermentation"

    # Close note view -> should restore AskView!
    app.close_note_view()
    assert app.viewport.content is ask_view


def test_claybank_app_search_and_ask_dispatchers():
    """ClayBankApp dispatches custom or fallback search and ask queries with valid citations."""
    sample_saves = [
        {
            "id": "save_01",
            "title": "Perfect Carbonara",
            "url": "https://example.com/carbonara",
            "tags": ["pasta", "italian"],
        },
    ]
    app = ClayBankApp(has_seen_onboarding=True, saves=sample_saves)

    # Search dispatcher
    results = app.handle_search_query("carbonara")
    assert len(results) == 1
    assert results[0]["id"] == "save_01"

    # Ask dispatcher
    answer = app.handle_ask_query("How to make carbonara?")
    assert "carbonara" in answer["answer"]
    assert len(answer["citations"]) >= 1
    assert answer["citations"][0]["save_id"] == "save_01"
