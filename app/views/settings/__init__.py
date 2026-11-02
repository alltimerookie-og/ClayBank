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
from app.views.settings.privacy_banner import PRIVACY_BANNER_TEXT, PrivacyBanner
from app.views.settings.profile_card import ProfileSyncCard
from app.views.settings.settings_view import SettingsView
from app.views.settings.storage_card import (
    StorageUsedCard,
    format_split_storage,
    format_storage_size,
)
from app.views.settings.switch_card import SettingSwitchCard

__all__ = [
    "SettingsView",
    "ProfileSyncCard",
    "ChatModelCard",
    "StorageUsedCard",
    "SettingSwitchCard",
    "PrivacyBanner",
    "PRIVACY_BANNER_TEXT",
    "format_storage_size",
    "format_split_storage",
    "MODEL_MINICPM",
    "MODEL_QWEN",
    "MODEL_LABELS",
]
