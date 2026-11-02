"""Folder Cover Collage component adhering to ClayBank design specifications.

Derived from Docs/Design.md §2.3, Docs/UIUX.md §7, and Prototype v2 (.c4).
Renders a 2x2 grid of gradient cells deterministically assigned from folder identity.
"""

from __future__ import annotations

import hashlib
from typing import Sequence
import flet as ft

from app.shell.theme import COVER_GRADIENTS

GRADIENT_KEYS = ("g1", "g2", "g3", "g4")
DEFAULT_COLLAGE_HEIGHT = 72.0
DEFAULT_COLLAGE_RADIUS = 10.0
DEFAULT_COLLAGE_GAP = 3.0


def resolve_gradient_keys(
    seed: str | None = None,
    explicit_keys: Sequence[str] | None = None,
) -> list[str]:
    """Deterministically select 4 gradient keys using SHA-256 or explicit overrides."""
    if explicit_keys and len(explicit_keys) >= 4:
        # Validate that each key exists in COVER_GRADIENTS, fallback to g1 if invalid
        return [k if k in COVER_GRADIENTS else "g1" for k in explicit_keys[:4]]

    raw_seed = (seed or "claybank-folder-root").encode("utf-8")
    digest = hashlib.sha256(raw_seed).digest()
    return [GRADIENT_KEYS[digest[i] % len(GRADIENT_KEYS)] for i in range(4)]


def _create_gradient_cell(key: str) -> ft.Container:
    """Create a single gradient cell for the 2x2 collage."""
    start_color, end_color = COVER_GRADIENTS.get(key, COVER_GRADIENTS["g1"])
    return ft.Container(
        expand=True,
        gradient=ft.LinearGradient(
            begin=ft.Alignment(-1.0, -1.0),
            end=ft.Alignment(1.0, 1.0),
            colors=[start_color, end_color],
        ),
    )


class FolderCoverCollage(ft.Container):
    """4-cell 2x2 gradient collage thumbnail representing a folder cover."""

    def __init__(
        self,
        folder_id: str | None = None,
        *,
        folder_name: str | None = None,
        gradients: Sequence[str] | None = None,
        width: float | None = None,
        height: float = DEFAULT_COLLAGE_HEIGHT,
        border_radius: float = DEFAULT_COLLAGE_RADIUS,
        gap: float = DEFAULT_COLLAGE_GAP,
        theme_mode: ft.ThemeMode | str = ft.ThemeMode.LIGHT,
    ) -> None:
        self.folder_id = folder_id
        self.folder_name = folder_name
        self.gradient_keys = resolve_gradient_keys(
            seed=folder_id or folder_name,
            explicit_keys=gradients,
        )

        top_left = _create_gradient_cell(self.gradient_keys[0])
        top_right = _create_gradient_cell(self.gradient_keys[1])
        bottom_left = _create_gradient_cell(self.gradient_keys[2])
        bottom_right = _create_gradient_cell(self.gradient_keys[3])

        row_top = ft.Row(
            controls=[top_left, top_right],
            spacing=gap,
            expand=True,
        )
        row_bottom = ft.Row(
            controls=[bottom_left, bottom_right],
            spacing=gap,
            expand=True,
        )

        collage_grid = ft.Column(
            controls=[row_top, row_bottom],
            spacing=gap,
            expand=True,
        )

        super().__init__(
            content=collage_grid,
            width=width,
            height=height,
            border_radius=ft.BorderRadius.all(border_radius),
            clip_behavior=ft.ClipBehavior.HARD_EDGE,
            padding=0,
            theme_mode=theme_mode if isinstance(theme_mode, ft.ThemeMode) else None,
        )
