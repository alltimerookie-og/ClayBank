"""ClayBank Settings views and configuration components.

Derived from Docs/Phases.md Phase 7, Docs/Design.md §8, Docs/UIUX.md §11, and Prototype v2.
"""

from __future__ import annotations

from app.views.settings.chat_model_card import (
    MODEL_LABELS,
    MODEL_MINICPM,
    MODEL_QWEN,
    ChatModelCard,
)
from app.views.settings.profile_card import ProfileSyncCard

__all__ = [
    "ProfileSyncCard",
    "ChatModelCard",
    "MODEL_MINICPM",
    "MODEL_QWEN",
    "MODEL_LABELS",
]
