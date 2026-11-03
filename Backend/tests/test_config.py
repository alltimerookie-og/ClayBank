"""Focused tests for environment-backed settings."""

from Backend.config import load_settings


def test_settings_support_all_provider_keys() -> None:
    """Every documented provider variable maps to typed settings."""
    settings = load_settings(
        {
            "DEV_TOKEN": "test-token",
            "X_DEVICE_ID": "test-device",
            "CLAYBANK_DB_PATH": "data/test.sqlite3",
            "META_MODEL_API_BASE_URL": "https://example.com/compat/v1",
            "META_MODEL_API_KEY": "meta-key",
            "META_MODEL_API_MODEL": "test-model",
            "META_MODEL_CONTRIBUTOR_TIER": "true",
            "LOCAL_CHAT_MODEL_ID": "minicpm5-2b",
            "LOCAL_CHAT_MODEL_PATH": "/models/minicpm.gguf",
            "CRAWL4AI_ENABLED": "true",
            "DEEP_CRAWL_ENABLED": "true",
        }
    )

    assert settings.dev_token == "test-token"
    assert settings.device_id == "test-device"
    assert settings.db_path == "data/test.sqlite3"
    assert settings.meta_model_base_url == "https://example.com/compat/v1"
    assert settings.meta_model_api_key == "meta-key"
    assert settings.meta_model_name == "test-model"
    assert settings.meta_model_contributor_tier is True
    assert settings.local_chat_model_id == "minicpm5-2b"
    assert settings.local_chat_model_path == "/models/minicpm.gguf"
    assert settings.crawl4ai_enabled is True
    assert settings.deep_crawl_enabled is True
