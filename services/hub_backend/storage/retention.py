"""
Smart Spectator - Automated Storage & Event Retention Lifecycle Manager
Conforms to Sections 20 & 21 of Phase 9 Master Specification.
Executes deterministic retention pruning for event metadata and video recordings.
Guarantees retention lock protection, orphan cleanup, and comprehensive audit trails.
"""

from datetime import datetime, timezone, timedelta
import json
import os
import uuid
from pathlib import Path
from typing import Dict, Any, Optional

from services.hub_backend.config import settings
from services.hub_backend.database.connection import db_session


def get_retention_policies() -> Dict[str, Any]:
    """Retrieves active retention configuration."""
    event_days = getattr(settings, "EVENT_RETENTION_DAYS", 30)
    rec_days = getattr(settings, "RECORDING_RETENTION_DAYS", 7)
    max_storage_gb = getattr(settings, "RECORDING_MAX_STORAGE_GB", 20.0)

    try:
        with db_session() as conn:
            row = conn.execute(
                "SELECT value_json FROM system_configs WHERE category = 'STORAGE' AND key = 'retention'"
            ).fetchone()
            if row and row["value_json"]:
                cfg = json.loads(row["value_json"])
                event_days = cfg.get("event_retention_days", event_days)
                rec_days = cfg.get("recording_retention_days", rec_days)
                max_storage_gb = cfg.get("max_storage_gb", max_storage_gb)
    except Exception:
        pass

    return {
        "event_retention_days": int(event_days),
        "recording_retention_days": int(rec_days),
        "max_storage_gb": float(max_storage_gb),
    }


def run_retention_cleanup(
    event_retention_days: Optional[int] = None,
    recording_retention_days: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Executes safe cleanup cycle:
    1. Prunes recordings older than retention threshold (respects is_locked).
    2. Prunes events older than event retention threshold.
    3. Prunes orphan media files in recordings directory.
    4. Logs audit activity.
    """
    policies = get_retention_policies()
    evt_days = event_retention_days if event_retention_days is not None else policies["event_retention_days"]
    rec_days = recording_retention_days if recording_retention_days is not None else policies["recording_retention_days"]

    now = datetime.now(timezone.utc)
    rec_cutoff = (now - timedelta(days=rec_days)).isoformat()
    evt_cutoff = (now - timedelta(days=evt_days)).isoformat()

    deleted_recordings = 0
    deleted_events = 0
    deleted_orphans = 0
    freed_bytes = 0

    recordings_dir = settings.RECORDINGS_DIR.resolve()

    with db_session() as conn:
        # 1. Select expired, unlocked recordings
        cursor = conn.execute(
            """
            SELECT recording_id, file_path, thumbnail_path, file_size_bytes
            FROM recordings
            WHERE start_time < ? AND is_locked = 0
            """,
            (rec_cutoff,),
        )
        expired_recs = cursor.fetchall()

        for rec in expired_recs:
            rec_id = rec["recording_id"]
            fp = Path(rec["file_path"]).resolve()

            # Confinement check
            if recordings_dir in fp.parents or fp.parent == recordings_dir:
                try:
                    if fp.exists() and fp.is_file():
                        sz = fp.stat().st_size
                        fp.unlink()
                        freed_bytes += sz
                except Exception as e:
                    print(f"[Retention] Failed to unlink recording file '{fp}': {e}")

            if rec.get("thumbnail_path"):
                th = Path(rec["thumbnail_path"]).resolve()
                try:
                    if th.exists() and th.is_file():
                        th.unlink()
                except Exception:
                    pass

            conn.execute("DELETE FROM recordings WHERE recording_id = ?", (rec_id,))
            conn.execute("UPDATE events SET recording_id = NULL WHERE recording_id = ?", (rec_id,))
            deleted_recordings += 1

        # 2. Prune expired events
        ev_cursor = conn.execute(
            "SELECT COUNT(*) as cnt FROM events WHERE timestamp < ?",
            (evt_cutoff,),
        )
        cnt_row = ev_cursor.fetchone()
        deleted_events = cnt_row["cnt"] if cnt_row else 0
        conn.execute("DELETE FROM events WHERE timestamp < ?", (evt_cutoff,))

        # 3. Clean orphan MP4 files in storage directory
        if recordings_dir.exists():
            tracked_files = {
                Path(r["file_path"]).resolve()
                for r in conn.execute("SELECT file_path FROM recordings").fetchall()
            }
            one_hour_ago = time_thresh = datetime.now().timestamp() - 3600.0

            for p in recordings_dir.glob("*.mp4"):
                p_res = p.resolve()
                if p_res not in tracked_files:
                    try:
                        if p_res.stat().st_mtime < one_hour_ago:
                            sz = p_res.stat().st_size
                            p_res.unlink()
                            deleted_orphans += 1
                            freed_bytes += sz
                    except Exception:
                        pass

        # Count preserved locked recordings
        locked_preserved = conn.execute("SELECT COUNT(*) as c FROM recordings WHERE is_locked = 1").fetchone()["c"]

        # 4. Audit Log
        if deleted_recordings > 0 or deleted_events > 0 or deleted_orphans > 0:
            audit_meta = {
                "deleted_recordings": deleted_recordings,
                "deleted_events": deleted_events,
                "deleted_orphans": deleted_orphans,
                "locked_preserved": locked_preserved,
                "freed_bytes": freed_bytes,
                "event_retention_days": evt_days,
                "recording_retention_days": rec_days,
            }
            conn.execute(
                """
                INSERT INTO audit_logs (log_id, actor, action, resource, metadata_json)
                VALUES (?, 'system', 'RETENTION_CLEANUP', 'storage', ?)
                """,
                (
                    f"audit_retention_{uuid.uuid4().hex}",
                    json.dumps(audit_meta),
                ),
            )

    return {
        "status": "success",
        "deleted_recordings": deleted_recordings,
        "deleted_events": deleted_events,
        "deleted_orphans": deleted_orphans,
        "locked_preserved": locked_preserved,
        "freed_bytes": freed_bytes,
        "freed_mb": round(freed_bytes / (1024 * 1024), 2),
        "timestamp": now.isoformat(),
    }
