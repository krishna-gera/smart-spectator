"""
Smart Spectator - Categorized Configuration & Safe Export/Import Manager
Conforms to Sections 18, 19, 24 of Phase 9 Master Specification.
Categories: SYSTEM, NETWORK, CAMERAS, AI, EVENTS, RECORDING, STORAGE, NOTIFICATIONS, SECURITY.
Strictly strips secrets, PINs, and authentication tokens during export.
"""

from datetime import datetime, timezone
import json
import uuid
from typing import Dict, Any, List, Optional, Tuple
from pydantic import BaseModel, Field, ValidationError

from services.hub_backend.config import settings
from services.hub_backend.database.connection import db_session


VALID_CATEGORIES = {
    "SYSTEM", "NETWORK", "CAMERAS", "AI", "EVENTS",
    "RECORDING", "STORAGE", "NOTIFICATIONS", "SECURITY"
}

# Sensitive keys that must NEVER be exported or exposed
SENSITIVE_KEYS = {
    "HMAC_SECRET", "HUB_HMAC_SECRET", "auth_token", "auth_token_hash",
    "password", "secret", "verification_pin", "private_key"
}


def get_default_config() -> Dict[str, Dict[str, Any]]:
    """Returns baseline categorized configuration defaults."""
    return {
        "SYSTEM": {
            "environment": settings.ENVIRONMENT,
            "app_version": settings.APP_VERSION,
            "hub_version": settings.HUB_VERSION,
            "dev_mode": settings.DEV_MODE,
            "max_request_body_bytes": settings.MAX_REQUEST_BODY_BYTES,
        },
        "NETWORK": {
            "host": settings.HOST,
            "port": settings.PORT,
            "stream_port": settings.STREAM_PORT,
            "mdns_name": settings.MDNS_SERVICE_NAME,
        },
        "CAMERAS": {
            "max_concurrent_cameras": settings.MAX_CONCURRENT_CAMERAS,
            "target_fps": settings.TARGET_FPS,
            "target_width": settings.TARGET_WIDTH,
            "target_height": settings.TARGET_HEIGHT,
        },
        "AI": {
            "preferred_provider": "auto",
            "detector_model": settings.DETECTOR_VERSION,
            "spectatornet_model": settings.SPECTATORNET_VERSION,
            "confidence_threshold": 0.35,
            "iou_threshold": 0.45,
            "motion_gate_enabled": True,
        },
        "EVENTS": {
            "min_confidence": settings.EVENT_DEFAULT_MIN_CONFIDENCE,
            "confirm_threshold": settings.EVENT_DEFAULT_CONFIRM_THRESHOLD,
            "consecutive_frames": settings.EVENT_DEFAULT_CONSECUTIVE,
            "resolution_timeout_seconds": settings.EVENT_RESOLUTION_TIMEOUT_SECONDS,
        },
        "RECORDING": {
            "pre_roll_seconds": settings.RECORDING_PRE_ROLL_SECONDS,
            "post_roll_seconds": settings.RECORDING_POST_ROLL_SECONDS,
            "codec": "h264",
            "max_storage_gb": settings.RECORDING_MAX_STORAGE_GB,
        },
        "STORAGE": {
            "event_retention_days": getattr(settings, "EVENT_RETENTION_DAYS", 30),
            "recording_retention_days": settings.RECORDING_RETENTION_DAYS,
            "min_free_disk_mb": settings.MIN_FREE_DISK_MB,
        },
        "NOTIFICATIONS": {
            "global_cooldown_seconds": 2.0,
            "camera_cooldown_seconds": 5.0,
            "websocket_enabled": True,
        },
        "SECURITY": {
            "pairing_pin_ttl_seconds": settings.PAIRING_PIN_TTL_SECONDS,
            "pairing_pin_length": settings.PAIRING_PIN_LENGTH,
            "max_pin_attempts": settings.MAX_PIN_ATTEMPTS,
            "pin_lockout_seconds": settings.PIN_LOCKOUT_SECONDS,
        },
    }


def load_categorized_config() -> Dict[str, Dict[str, Any]]:
    """Loads all configuration categories, overlaying persistent overrides from database."""
    config = get_default_config()

    try:
        with db_session() as conn:
            rows = conn.execute("SELECT category, key, value_json FROM system_configs").fetchall()
            for r in rows:
                cat = r["category"]
                k = r["key"]
                if cat in config and k not in SENSITIVE_KEYS:
                    try:
                        config[cat][k] = json.loads(r["value_json"])
                    except Exception:
                        pass
    except Exception:
        pass

    return config


def validate_config_category(category: str, values: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
    """
    Validates parameter values for a specific category.
    Returns (True, None) if valid, or (False, error_message) on failure.
    """
    cat = category.upper()
    if cat not in VALID_CATEGORIES:
        return False, f"Unknown configuration category '{category}'."

    # Prevent writing sensitive keys
    for k in values:
        if k in SENSITIVE_KEYS:
            return False, f"Modification of security sensitive parameter '{k}' is prohibited."

    if cat == "CAMERAS":
        fps = values.get("target_fps")
        if fps is not None and not (1 <= fps <= 60):
            return False, "Parameter 'target_fps' must be between 1 and 60."
        w = values.get("target_width")
        if w is not None and not (320 <= w <= 3840 and w % 16 == 0):
            return False, "Parameter 'target_width' must be a multiple of 16 between 320 and 3840."
        h = values.get("target_height")
        if h is not None and not (240 <= h <= 2160 and h % 2 == 0):
            return False, "Parameter 'target_height' must be an even integer between 240 and 2160."

    elif cat == "AI":
        conf = values.get("confidence_threshold")
        if conf is not None and not (0.05 <= conf <= 0.99):
            return False, "Parameter 'confidence_threshold' must be between 0.05 and 0.99."
        iou = values.get("iou_threshold")
        if iou is not None and not (0.10 <= iou <= 0.90):
            return False, "Parameter 'iou_threshold' must be between 0.10 and 0.90."

    elif cat == "EVENTS":
        min_c = values.get("min_confidence")
        if min_c is not None and not (0.10 <= min_c <= 1.0):
            return False, "Parameter 'min_confidence' must be between 0.10 and 1.0."
        consec = values.get("consecutive_frames")
        if consec is not None and not (1 <= consec <= 10):
            return False, "Parameter 'consecutive_frames' must be between 1 and 10."

    elif cat == "STORAGE":
        evt_ret = values.get("event_retention_days")
        if evt_ret is not None and not (1 <= evt_ret <= 365):
            return False, "Parameter 'event_retention_days' must be between 1 and 365 days."
        rec_ret = values.get("recording_retention_days")
        if rec_ret is not None and not (1 <= rec_ret <= 180):
            return False, "Parameter 'recording_retention_days' must be between 1 and 180 days."

    elif cat == "NOTIFICATIONS":
        g_cool = values.get("global_cooldown_seconds")
        if g_cool is not None and not (0.0 <= g_cool <= 60.0):
            return False, "Parameter 'global_cooldown_seconds' must be between 0.0 and 60.0."

    return True, None


def save_config_category(category: str, values: Dict[str, Any]) -> Dict[str, Any]:
    """Validates and persists updates for a configuration category."""
    is_valid, err_msg = validate_config_category(category, values)
    if not is_valid:
        raise ValueError(err_msg)

    cat = category.upper()
    now_iso = datetime.now(timezone.utc).isoformat()

    with db_session() as conn:
        for k, v in values.items():
            if k in SENSITIVE_KEYS:
                continue
            conn.execute(
                """
                INSERT INTO system_configs (category, key, value_json, updated_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(category, key) DO UPDATE SET
                    value_json = excluded.value_json,
                    updated_at = excluded.updated_at
                """,
                (cat, k, json.dumps(v), now_iso)
            )

        # Audit configuration update
        conn.execute(
            """
            INSERT INTO audit_logs (log_id, actor, action, resource, metadata_json)
            VALUES (?, 'operator', 'UPDATE_CONFIG', ?, ?)
            """,
            (
                f"audit_cfg_{uuid.uuid4().hex}",
                f"config:{cat}",
                json.dumps({"updated_keys": list(values.keys())})
            )
        )

    return {"status": "success", "category": cat, "updated_keys": list(values.keys()), "timestamp": now_iso}


def export_safe_configuration() -> Dict[str, Any]:
    """
    Exports full system configuration manifest.
    Guarantees zero leakage of secrets, auth tokens, or private keys.
    """
    cfg = load_categorized_config()
    safe_manifest = {
        "manifest_type": "smart_spectator_config_export",
        "schema_version": "1.2.0",
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "app_version": settings.APP_VERSION,
        "categories": cfg,
    }
    return safe_manifest


def import_safe_configuration(manifest: Dict[str, Any]) -> Dict[str, Any]:
    """
    Validates and applies an imported configuration manifest.
    Enforces schema compatibility and validates values.
    """
    if manifest.get("manifest_type") != "smart_spectator_config_export":
        raise ValueError("Invalid manifest type. Must be 'smart_spectator_config_export'.")

    schema_ver = manifest.get("schema_version", "")
    if not schema_ver.startswith("1."):
        raise ValueError(f"Incompatible schema version '{schema_ver}'. Required '1.x'.")

    categories = manifest.get("categories", {})
    applied_categories = []

    for cat_name, cat_values in categories.items():
        if cat_name in VALID_CATEGORIES and isinstance(cat_values, dict):
            is_valid, err = validate_config_category(cat_name, cat_values)
            if not is_valid:
                raise ValueError(f"Category '{cat_name}' validation error: {err}")
            save_config_category(cat_name, cat_values)
            applied_categories.append(cat_name)

    return {
        "status": "success",
        "applied_categories": applied_categories,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
