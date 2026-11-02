"""Phase 5 Integration and End-to-End Navigation Test Suite.

Verifies:
- 4-tab contract with FoldersGridView on TAB_FOLDERS (app_shell.py)
- Cluster suggestion proposals in Inbox review queue (inbox_view.py)
- Folder drill-down, subfolder navigation, and back navigation (app.py)
- In-place tag filtering and note opening from folder detail view
- Folder CRUD lifecycle (create, rename, delete) with 5000ms UndoSnackBar
- Member saves returning unfiled to Inbox upon folder deletion
"""

import copy
import flet as ft
import pytest

from app.app import ClayBankApp, UNDO_DURATION_MS
from app.shell.app_shell import AppShellLayout
from app.shell.nav import TAB_COUNT, TAB_FOLDERS, TAB_INBOX
from app.ui.snackbar import UndoSnackBar
from app.views.folders.cluster_card import ClusterSuggestionCard
from app.views.folders.folder_detail_view import FolderDetailView
from app.views.folders.folders_grid_view import FoldersGridView
from app.views.note.note_view import ItemNoteView

SAMPLE_FOLDERS = [
    {
        "id": "018f4c1a-0000-7de6-9c8e-000000000004",
        "parent_id": None,
        "name": "Cooking",
        "save_count": 24,
    },
    {
        "id": "018f4c1a-0000-7de6-9c8e-000000000005",
        "parent_id": "018f4c1a-0000-7de6-9c8e-000000000004",
        "name": "Pasta",
        "save_count": 6,
    },
]

SAMPLE_SAVES = [
    {
        "id": "018f4c1a-0000-7de6-9c8e-000000000001",
        "title": "Creamy garlic pasta",
        "platform": "instagram",
        "folder": "Cooking",
        "tags": ["pasta", "dinner"],
    },
    {
        "id": "018f4c1a-0000-7de6-9c8e-000000000002",
        "title": "One pot pasta",
        "platform": "tiktok",
        "folder": "Cooking",
        "tags": ["pasta", "quick"],
    },
    {
        "id": "018f4c1a-0000-7de6-9c8e-000000000008",
        "title": "Sauce basics",
        "platform": "web",
        "folder": None,  # unfiled
        "tags": ["sauces"],
    },
]

SAMPLE_CLUSTER_SUGGESTION = {
    "type": "cluster",
    "save_id": None,
    "cluster": [
        {"save_id": "018f4c1a-0000-7de6-9c8e-000000000001", "title": "Creamy garlic pasta"},
        {"save_id": "018f4c1a-0000-7de6-9c8e-000000000002", "title": "One pot pasta"},
        {"save_id": "018f4c1a-0000-7de6-9c8e-000000000008", "title": "Sauce basics"},
    ],
    "path": "Cooking",
    "confidence": 0.88,
    "dismissed_at": None,
    "accepted": False,
}


def test_app_shell_folders_tab_integration():
    """Verify AppShellLayout integrates FoldersGridView on Tab 1 with exactly 4 tabs."""
    grid = FoldersGridView(folders=copy.deepcopy(SAMPLE_FOLDERS))
    shell = AppShellLayout(folders_view=grid, initial_tab=TAB_INBOX)

    assert len(shell.tab_views) == TAB_COUNT == 4
    assert shell.tab_views[TAB_FOLDERS] is grid

    # Switch to Folders tab
    shell.set_tab(TAB_FOLDERS)
    assert shell.selected_index == TAB_FOLDERS
    assert shell.content_area.content is grid
    assert shell.header._title == "Folders"


def test_inbox_cluster_suggestion_integration():
    """Verify cluster proposal suggestion in InboxView renders ClusterSuggestionCard and files saves."""
    app = ClayBankApp(
        has_seen_onboarding=True,
        saves=copy.deepcopy(SAMPLE_SAVES),
        suggestions=[SAMPLE_CLUSTER_SUGGESTION],
        folders=copy.deepcopy(SAMPLE_FOLDERS),
    )
    app.transition_to_shell()

    # Inbox review queue should have ClusterSuggestionCard
    sugg_col = app.inbox_view.suggestions_column
    assert sugg_col.visible is True
    # The first control after the header text is the card
    cluster_card = next((c for c in sugg_col.controls if isinstance(c, ClusterSuggestionCard)), None)
    assert cluster_card is not None
    assert cluster_card.target_path == "Cooking"

    # Accept cluster proposal
    cluster_card.accept()

    # Save 8 should now be filed to Cooking
    save_8 = next(s for s in app.inbox_view._saves if s["id"] == "018f4c1a-0000-7de6-9c8e-000000000008")
    assert save_8["folder"] == "Cooking"

    # 5000ms UndoSnackBar should be presented
    assert app.last_snackbar is not None
    assert "Filed 3 saves to 'Cooking'" in app.last_snackbar.message
    assert app.last_snackbar.duration_ms == UNDO_DURATION_MS

    # Trigger Undo
    app.last_snackbar.trigger_undo()
    assert save_8["folder"] is None


def test_folder_drill_down_and_back_navigation():
    """Verify navigating from Folders grid into FolderDetailView and drill down to subfolder."""
    app = ClayBankApp(
        has_seen_onboarding=True,
        saves=copy.deepcopy(SAMPLE_SAVES),
        folders=copy.deepcopy(SAMPLE_FOLDERS),
    )
    app.transition_to_shell()

    # Navigate to Cooking folder detail view
    cooking_folder = copy.deepcopy(SAMPLE_FOLDERS[0])
    detail_view = app.open_folder_detail_view(cooking_folder)

    assert app.viewport.content is detail_view
    assert detail_view.title_text.value == "Cooking"
    assert "Folders / Cooking" in detail_view.breadcrumb_text.value

    # Drill down into Pasta subfolder
    pasta_folder = copy.deepcopy(SAMPLE_FOLDERS[1])
    pasta_detail = app.open_folder_detail_view(pasta_folder)
    assert app.viewport.content is pasta_detail
    assert pasta_detail.title_text.value == "Pasta"
    assert "Folders / Cooking / Pasta" in pasta_detail.breadcrumb_text.value

    # Navigate back from Pasta -> should return to Cooking parent
    app.close_folder_detail_view()
    assert app.viewport.content.title_text.value == "Cooking"

    # Navigate back from Cooking -> should return to AppShell on Tab 1
    app.close_folder_detail_view()
    assert app.viewport.content is app.app_shell
    assert app.app_shell.selected_index == TAB_FOLDERS


def test_folder_detail_view_open_note():
    """Verify tapping a save inside FolderDetailView opens ItemNoteView."""
    app = ClayBankApp(
        has_seen_onboarding=True,
        saves=copy.deepcopy(SAMPLE_SAVES),
        folders=copy.deepcopy(SAMPLE_FOLDERS),
    )
    app.transition_to_shell()

    cooking_folder = copy.deepcopy(SAMPLE_FOLDERS[0])
    detail_view = app.open_folder_detail_view(cooking_folder)

    # Click first save card in detail view
    save_card = detail_view.saves_column.controls[0]
    detail_view.on_select_save(save_card.save_item)

    assert isinstance(app.viewport.content, ItemNoteView)
    assert app.current_note_view is not None
    assert app.current_note_view.save_id == "018f4c1a-0000-7de6-9c8e-000000000001"

    # Close note view -> returns to folder detail view
    app.close_note_view()
    assert app.viewport.content is detail_view


def test_folder_creation_lifecycle_and_undo():
    """Verify creating a folder updates grid, shows snackbar, and supports undo."""
    app = ClayBankApp(
        has_seen_onboarding=True,
        folders=copy.deepcopy(SAMPLE_FOLDERS),
    )
    initial_count = len(app._folders_collection)

    # Open create folder sheet
    app.open_create_folder_sheet()
    assert app.overlay_container.visible is True
    sheet = app.overlay_container.content
    assert sheet is not None

    sheet.name_field.value = "Gardening"
    sheet._submit()

    assert app.overlay_container.visible is False
    assert len(app._folders_collection) == initial_count + 1
    new_folder = next(f for f in app._folders_collection if f["name"] == "Gardening")
    assert new_folder is not None

    # Verify 5000ms UndoSnackBar
    assert app.last_snackbar is not None
    assert "Created folder 'Gardening'" in app.last_snackbar.message
    assert app.last_snackbar.duration_ms == UNDO_DURATION_MS

    # Trigger Undo
    app.last_snackbar.trigger_undo()
    assert len(app._folders_collection) == initial_count
    assert not any(f["name"] == "Gardening" for f in app._folders_collection)


def test_folder_rename_lifecycle_and_undo():
    """Verify renaming a folder updates folder name and member saves with undo support."""
    app = ClayBankApp(
        has_seen_onboarding=True,
        saves=copy.deepcopy(SAMPLE_SAVES),
        folders=copy.deepcopy(SAMPLE_FOLDERS),
    )

    cooking_folder = copy.deepcopy(SAMPLE_FOLDERS[0])
    app.open_rename_folder_sheet(cooking_folder)
    assert app.overlay_container.visible is True
    sheet = app.overlay_container.content

    sheet.name_field.value = "Culinary Arts"
    sheet._submit()

    # Folder renamed
    updated_f = next(f for f in app._folders_collection if f["id"] == cooking_folder["id"])
    assert updated_f["name"] == "Culinary Arts"

    # Member saves updated
    save_1 = next(s for s in app.inbox_view._saves if s["id"] == "018f4c1a-0000-7de6-9c8e-000000000001")
    assert save_1["folder"] == "Culinary Arts"

    assert app.last_snackbar is not None
    assert "Renamed to 'Culinary Arts'" in app.last_snackbar.message

    # Trigger Undo
    app.last_snackbar.trigger_undo()
    assert updated_f["name"] == "Cooking"
    assert save_1["folder"] == "Cooking"


def test_folder_delete_unfiles_saves_with_undo():
    """Verify deleting a folder returns member saves to Inbox unfiled and undo restores them."""
    app = ClayBankApp(
        has_seen_onboarding=True,
        saves=copy.deepcopy(SAMPLE_SAVES),
        folders=copy.deepcopy(SAMPLE_FOLDERS),
    )

    cooking_folder = copy.deepcopy(SAMPLE_FOLDERS[0])
    # Delete folder
    app.confirm_delete_folder(cooking_folder)

    # Folder should be removed from active collection
    assert not any(f["id"] == cooking_folder["id"] for f in app._folders_collection)

    # Member saves (save 1 & save 2) return to Inbox unfiled
    save_1 = next(s for s in app.inbox_view._saves if s["id"] == "018f4c1a-0000-7de6-9c8e-000000000001")
    save_2 = next(s for s in app.inbox_view._saves if s["id"] == "018f4c1a-0000-7de6-9c8e-000000000002")
    assert save_1["folder"] is None
    assert save_2["folder"] is None

    # 5000ms UndoSnackBar
    assert app.last_snackbar is not None
    assert "Deleted folder 'Cooking'" in app.last_snackbar.message
    assert "returned to Inbox" in app.last_snackbar.message

    # Trigger Undo -> restores folder and member saves assignment
    app.last_snackbar.trigger_undo()
    assert any(f["id"] == cooking_folder["id"] for f in app._folders_collection)
    assert save_1["folder"] == "Cooking"
    assert save_2["folder"] == "Cooking"
