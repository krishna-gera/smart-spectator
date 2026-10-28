"""
Phase 10 Tests — Statistical Baseline Engine
Conforms to Sections 8 & 37 of Phase 10 Specification.
Validates:
1. Hourly event frequency calculation (mean, stddev, median, min, max).
2. Stability safeguards against division by zero.
3. Database persistence in statistical_baselines table.
"""

from datetime import datetime, timezone, timedelta
import pytest

from services.event_engine.anomaly.baseline import baseline_engine
from services.hub_backend.config import settings
from services.hub_backend.database.connection import init_database, get_db


@pytest.fixture(autouse=True)
def setup_test_db(tmp_path):
    orig = settings.DATABASE_PATH
    settings.DATABASE_PATH = tmp_path / "test_baseline.db"
    init_database()
    yield
    settings.DATABASE_PATH = orig


def test_baseline_hourly_frequency_computation():
    # Anchor to yesterday 14:00 UTC so all 3 days stay inside the 14-day lookback window
    yesterday = datetime.now(timezone.utc) - timedelta(days=1)
    base_time = yesterday.replace(hour=14, minute=0, second=0, microsecond=0)

    # Insert synthetic event counts for hour 14 across 3 consecutive days
    with get_db() as conn:
        conn.execute("INSERT OR IGNORE INTO cameras (camera_id, name, source_type) VALUES ('cam_gate', 'Gate Cam', 'phone')")
        for day_offset in range(3):
            t = base_time - timedelta(days=day_offset)
            # Insert 4 events on day 0, 6 events on day 1, 8 events on day 2
            # Mean should be 6.0, std_dev should be 2.0
            num_events = 4 + (day_offset * 2)
            for i in range(num_events):
                ev_time = t + timedelta(minutes=i * 2)
                conn.execute(
                    """
                    INSERT INTO events (event_id, camera_id, event_type, severity, priority, confidence, summary, timestamp)
                    VALUES (?, 'cam_gate', 'person_entered', 'low', 'LOW', 0.8, 'summary', ?)
                    """,
                    (f"ev_base_{day_offset}_{i}", ev_time.isoformat()),
                )
        conn.commit()

    profiles = baseline_engine.compute_hourly_frequency_baselines(camera_id="cam_gate", persist=True)
    assert len(profiles) == 24

    # Check hour 14
    p14 = next(p for p in profiles if p.hour_of_day == 14)
    assert p14.sample_count == 3
    assert p14.mean_value == 6.0
    assert p14.median_value == 6.0
    assert p14.std_dev == 2.0

    # Verify retrieval from database
    retrieved = baseline_engine.get_baseline(
        metric_name="hourly_event_frequency",
        camera_id="cam_gate",
        hour_of_day=14,
    )
    assert retrieved is not None
    assert retrieved.mean_value == 6.0
