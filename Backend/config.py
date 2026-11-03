"""Environment-backed backend configuration."""

from __future__ import annotations

import os
from dataclasses import dataclass


def _get(name: str, default: str = "") -> str:
    """Return a stripped environment value."""
    return os.environ.get(name, default).strip()


def _get_bool(name: str, default: bool = False) -> bool:
    """Parse a boolean environment value."""
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True, slots=True)
class Settings:
    """Typed backend settings loaded from process environment."""

    dev_token: str = ""
    device_id: str = ""
    db_path: str = "data/claybank.sqlite3"
    meta_model_base_url: str = ""
    meta_model_api_key: str = ""
    meta_model_name: str = ""
    meta_model_contributor_tier: bool = False
    local_chat_model_id: str = ""
    local_chat_model_path: str = ""
    crawl4ai_enabled: bool = False
    deep_crawl_enabled: bool = False


def load_settings(environ: dict[str, str] | None = None) -> Settings:
    """Load settings without importing optional dotenv dependencies."""
    if environ is not None:
        original = dict(os.environ)
        os.environ.clear()
        os.environ.update(environ)
        try:
            return _load()
        finally:
            os.environ.clear()
            os.environ.update(original)
    return _load()


def _load() -> Settings:
    """Read the supported backend environment variables."""
    return Settings(
        dev_token=_get("DEV_TOKEN", "dev-token"),
        device_id=_get("X_DEVICE_ID", "dev-laptop"),
        db_path=_get("CLAYBANK_DB_PATH", "data/claybank.sqlite3"),
        meta_model_base_url=_get("META_MODEL_API_BASE_URL"),
        meta_model_api_key=_get("META_MODEL_API_KEY"),
        meta_model_name=_get("META_MODEL_API_MODEL"),
        meta_model_contributor_tier=_get_bool("META_MODEL_CONTRIBUTOR_TIER", False),
        local_chat_model_id=_get("LOCAL_CHAT_MODEL_ID"),
        local_chat_model_path=_get("LOCAL_CHAT_MODEL_PATH"),
        crawl4ai_enabled=_get_bool("CRAWL4AI_ENABLED", False),
        deep_crawl_enabled=_get_bool("DEEP_CRAWL_ENABLED", False),
    )
