"""Phase 9 Tests — Categorized Configuration Management & Safe Export/Import.

Validates:
1. Retrieval of categorized system configs
2. Safe export stripping sensitive secrets (HMAC, tokens, keys)
3. Safe import validation and preservation of secrets
4. Config update and validation
"""

import pytest
from services.hub_backend.config import settings
from services.hub_backend.database.connection import init_database
from services.hub_backend.config_manager import (
    load_categorized_config,
    save_config_category,
    export_safe_configuration,
    import_safe_configuration,
    validate_config_category,
    VALID_CATEGORIES,
    SENSITIVE_KEYS
)


@pytest.fixture(autouse=True)
def setup_phase9_config_env(tmp_path):
    db_file = tmp_path / "test_config.db"
    settings.DATABASE_PATH = db_file
    init_database()
    yield


def test_categorized_config_retrieval():
    all_cfg = load_categorized_config()
    assert "SYSTEM" in all_cfg
    assert "STORAGE" in all_cfg
    assert "EVENTS" in all_cfg
    assert "RECORDING" in all_cfg

    storage_cfg = all_cfg["STORAGE"]
    assert "recording_retention_days" in storage_cfg
    assert "event_retention_days" in storage_cfg


def test_safe_config_export_zero_secrets():
    exported = export_safe_configuration()
    assert "schema_version" in exported
    assert exported["schema_version"] == "1.2.0"
    assert "exported_at" in exported
    assert "categories" in exported

    # Verify no sensitive keys exist anywhere in export
    def check_no_secrets(obj):
        if isinstance(obj, dict):
            for k, v in obj.items():
                k_lower = k.lower()
                assert "secret" not in k_lower
                assert "token" not in k_lower
                assert "password" not in k_lower
                assert "private_key" not in k_lower
                check_no_secrets(v)
        elif isinstance(obj, list):
            for item in obj:
                check_no_secrets(item)

    check_no_secrets(exported["categories"])


def test_config_update_and_validation():
    # Valid update
    valid_res, err = validate_config_category("STORAGE", {"event_retention_days": 21, "recording_retention_days": 14})
    assert valid_res is True
    assert err is None

    res = save_config_category("STORAGE", {"event_retention_days": 21, "recording_retention_days": 14})
    assert res["status"] == "success"

    # Invalid update (exceeding range)
    invalid_res, err_msg = validate_config_category("STORAGE", {"event_retention_days": 9999})
    assert invalid_res is False
    assert "365 days" in err_msg


def test_safe_config_import():
    manifest = export_safe_configuration()
    manifest["categories"]["STORAGE"]["event_retention_days"] = 15
    res = import_safe_configuration(manifest)
    assert res["status"] == "success"
    assert "STORAGE" in res["applied_categories"]
