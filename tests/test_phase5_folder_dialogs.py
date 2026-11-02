"""Unit tests for folder dialogs, sheets, and validators (Phase 5 deliverable P5-03)."""

import flet as ft
import pytest

from app.views.folders.folder_dialogs import (
    CreateFolderSheet,
    DeleteFolderConfirmDialog,
    FolderContextMenu,
    MAX_FOLDER_DEPTH,
    RESERVED_FOLDER_NAMES,
    RenameFolderSheet,
    validate_folder_depth,
    validate_folder_name,
)


def test_validate_folder_name_empty():
    """Verify empty or whitespace-only folder names are rejected."""
    ok, err = validate_folder_name("")
    assert not ok
    assert err == "Folder name cannot be empty."

    ok, err = validate_folder_name("   ")
    assert not ok
    assert err == "Folder name cannot be empty."


def test_validate_folder_name_reserved_names():
    """Verify reserved folder names are rejected (Rules.md §3)."""
    for reserved in ["Other", "MISC", "unsorted", "Inbox", "  other  "]:
        ok, err = validate_folder_name(reserved)
        assert not ok, f"Expected {reserved} to be rejected"
        assert "reserved folder name" in (err or "")


def test_validate_folder_name_duplicates():
    """Verify duplicate folder names are rejected case-insensitively."""
    existing = ["Cooking", "Fitness", "Study"]
    ok, err = validate_folder_name("cooking", existing_names=existing)
    assert not ok
    assert err == "A folder with this name already exists."

    ok, err = validate_folder_name("Art", existing_names=existing)
    assert ok
    assert err is None


def test_validate_folder_depth():
    """Verify folder depth constraint (depth <= 3)."""
    assert validate_folder_depth(1) == (True, None)
    assert validate_folder_depth(2) == (True, None)

    ok, err = validate_folder_depth(3)
    assert not ok
    assert "cannot exceed 3 levels" in (err or "")

    ok, err = validate_folder_depth(4)
    assert not ok


def test_create_folder_sheet_root_creation():
    """Verify CreateFolderSheet creates a root folder payload."""
    created_payloads = []

    def on_create(payload):
        created_payloads.append(payload)

    sheet = CreateFolderSheet(on_create=on_create)
    assert sheet.title_text.value == "New folder"
    assert sheet.parent_id is None

    sheet.name_field.value = "  Recipes  "
    sheet._submit()

    assert len(created_payloads) == 1
    assert created_payloads[0] == {"name": "Recipes", "parent_id": None}


def test_create_folder_sheet_subfolder_creation():
    """Verify CreateFolderSheet creates a subfolder payload under parent."""
    created_payloads = []

    def on_create(payload):
        created_payloads.append(payload)

    sheet = CreateFolderSheet(
        parent_id="018f4c1a-0000-7de6-9c8e-000000000004",
        parent_name="Cooking",
        parent_depth=1,
        on_create=on_create,
    )
    assert sheet.title_text.value == "New Subfolder in Cooking"

    sheet.name_field.value = "Italian"
    sheet._submit()

    assert len(created_payloads) == 1
    assert created_payloads[0] == {
        "name": "Italian",
        "parent_id": "018f4c1a-0000-7de6-9c8e-000000000004",
    }


def test_create_folder_sheet_depth_exceeded():
    """Verify CreateFolderSheet prevents creating beyond depth 3."""
    created_payloads = []

    sheet = CreateFolderSheet(
        parent_id="018f4c1a-0000-7de6-9c8e-000000000005",
        parent_name="Sub-Sub",
        parent_depth=3,
        on_create=lambda p: created_payloads.append(p),
    )

    sheet.name_field.value = "TooDeep"
    sheet._submit()

    assert len(created_payloads) == 0
    assert sheet.error_text.visible is True
    assert "cannot exceed 3 levels" in sheet.error_text.value


def test_rename_folder_sheet():
    """Verify RenameFolderSheet pre-populates name and invokes callback."""
    renamed = []

    def on_rename(folder_id, new_name):
        renamed.append((folder_id, new_name))

    folder_data = {
        "id": "018f4c1a-0000-7de6-9c8e-000000000004",
        "name": "Cooking",
    }

    sheet = RenameFolderSheet(folder_data, on_rename=on_rename)
    assert sheet.name_field.value == "Cooking"

    sheet.name_field.value = "Culinary Arts"
    sheet._submit()

    assert len(renamed) == 1
    assert renamed[0] == ("018f4c1a-0000-7de6-9c8e-000000000004", "Culinary Arts")


def test_delete_folder_confirm_dialog():
    """Verify DeleteFolderConfirmDialog explains saves return to Inbox."""
    deleted_ids = []

    def on_confirm_delete(folder_id):
        deleted_ids.append(folder_id)

    folder_data = {
        "id": "018f4c1a-0000-7de6-9c8e-000000000004",
        "name": "Cooking",
    }

    dialog = DeleteFolderConfirmDialog(folder_data, on_confirm_delete=on_confirm_delete)

    assert isinstance(dialog.title, ft.Text)
    assert dialog.title.value is not None
    assert "Cooking" in dialog.title.value
    assert isinstance(dialog.content, ft.Text)
    assert dialog.content.value is not None
    assert "return unfiled to your Inbox" in dialog.content.value

    dialog._confirm()
    assert deleted_ids == ["018f4c1a-0000-7de6-9c8e-000000000004"]


def test_folder_context_menu_depth_limit():
    """Verify FolderContextMenu omits subfolder action when depth >= 3."""
    folder_data = {
        "id": "018f4c1a-0000-7de6-9c8e-000000000005",
        "name": "Level3Folder",
    }

    menu_at_depth_3 = FolderContextMenu(folder_data, folder_depth=3)
    col = menu_at_depth_3.content
    assert isinstance(col, ft.Column)
    action_titles = [
        c.title.value
        for c in col.controls
        if isinstance(c, ft.ListTile) and isinstance(c.title, ft.Text)
    ]
    assert "Add subfolder" not in action_titles

    menu_at_depth_1 = FolderContextMenu(folder_data, folder_depth=1)
    col_1 = menu_at_depth_1.content
    assert isinstance(col_1, ft.Column)
    action_titles_1 = [
        c.title.value
        for c in col_1.controls
        if isinstance(c, ft.ListTile) and isinstance(c.title, ft.Text)
    ]
    assert "Add subfolder" in action_titles_1

