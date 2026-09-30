"""
Phase 10 Tests — Context Engine
Conforms to Sections 5 & 37 of Phase 10 Specification.
Validates:
1. Operational hours vs after-hours context calculation.
2. Weekend detection.
3. Recent activity querying without network access.
"""

from datetime import datetime, timezone
import pytest

from services.event_engine.context_engine import context_engine
from services.hub_backend.config import settings
from services.hub_backend.database.connection import init_database, get_db


@pytest.fixture(autouse=True)
def setup_test_db(tmp_path):
    orig = settings.DATABASE_PATH
    settings.DATABASE_PATH = tmp_path / "test_context.db"
    init_database()
    yield
    settings.DATABASE_PATH = orig


def test_context_engine_temporal_rules():
    # 1. Tuesday at 14:00 (Business hours)
    tuesday_day = datetime(2026, 9, 29, 14, 0, 0, tzinfo=timezone.utc)
    ctx1 = context_engine.build_context(camera_id="cam_main", event_time=tuesday_day)
    assert ctx1.hour_of_day == 14
    assert ctx1.day_of_week == 1  # Tuesday
    assert ctx1.is_weekend is False
    assert ctx1.is_after_hours is False

    # 2. Tuesday at 23:30 (After hours)
    tuesday_night = datetime(2026, 9, 29, 23, 30, 0, tzinfo=timezone.utc)
    ctx2 = context_engine.build_context(camera_id="cam_main", event_time=tuesday_night)
    assert ctx2.hour_of_day == 23
    assert ctx2.is_after_hours is True

    # 3. Sunday at 12:00 (Weekend -> After hours)
    sunday_noon = datetime(2026, 9, 27, 12, 0, 0, tzinfo=timezone.utc)
    ctx3 = context_engine.build_context(camera_id="cam_main", event_time=sunday_noon)
    assert ctx3.day_of_week == 6  # Sunday
    assert ctx3.is_weekend is True
    assert ctx3.is_after_hours is True


def test_context_recent_activity_integration():
    now = datetime.now(timezone.utc)
    with get_db() as conn:
        conn.execute("INSERT OR IGNORE INTO cameras (camera_id, name, source_type) VALUES ('cam_dock', 'Dock Cam', 'phone')")
        conn.execute(
            """
            INSERT INTO events (event_id, camera_id, event_type, severity, priority, confidence, summary, timestamp)
            VALUES ('ev_recent_1', 'cam_dock', 'motion_detected', 'low', 'LOW', 0.8, 'motion', ?)
            """,
            (now.isoformat(),),
        )
        conn.commit()

    ctx = context_engine.build_context(camera_id="cam_dock", event_time=now)
    assert ctx.recent_events_count_5m == 1
    assert ctx.active_events_count == 1
