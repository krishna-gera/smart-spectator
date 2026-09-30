"""
Phase 10 Tests — Anomaly Detection Engine & API
Conforms to Sections 9, 32 & 37 of Phase 10 Specification.
Validates:
1. Z-score anomaly evaluation against calculated baselines.
2. Structured explanation string generation.
3. REST API endpoints (/api/v1/anomalies).
"""

from fastapi.testclient import TestClient
import pytest

from services.event_engine.anomaly import (
    anomaly_detector,
    baseline_engine,
    BaselineProfile,
)
from services.hub_backend.config import settings
from services.hub_backend.database.connection import init_database
from services.hub_backend.main import app


@pytest.fixture(autouse=True)
def setup_test_db(tmp_path):
    orig = settings.DATABASE_PATH
    settings.DATABASE_PATH = tmp_path / "test_anomaly.db"
    init_database()
    yield
    settings.DATABASE_PATH = orig


def test_anomaly_zscore_evaluation_and_explanation():
    # Set a known baseline: Mean = 2.0, StdDev = 1.0 for hour 10
    profile = BaselineProfile(
        baseline_id="base_hr_10_cam_lobby",
        metric_name="hourly_event_frequency",
        camera_id="cam_lobby",
        hour_of_day=10,
        day_of_week=None,
        sample_count=10,
        mean_value=2.0,
        std_dev=1.0,
        median_value=2.0,
        min_value=0.0,
        max_value=5.0,
        last_updated="2026-09-30T00:00:00Z",
    )
    baseline_engine._save_baselines([profile])

    # 1. Normal count: 3 events/hr -> z = (3 - 2)/1 = 1.0 (< 2.5) -> No anomaly
    rep_normal = anomaly_detector.evaluate_frequency_anomaly(
        observed_count=3.0,
        hour_of_day=10,
        camera_id="cam_lobby",
    )
    assert rep_normal is None

    # 2. Unusual count: 12 events/hr -> z = (12 - 2)/1 = 10.0 (>= 2.5) -> Anomaly detected!
    rep_anomaly = anomaly_detector.evaluate_frequency_anomaly(
        observed_count=12.0,
        hour_of_day=10,
        camera_id="cam_lobby",
        persist=True,
    )
    assert rep_anomaly is not None
    assert rep_anomaly.score == 10.0
    assert rep_anomaly.anomaly_type == "UNUSUAL_ACTIVITY_FREQUENCY"
    assert "standard deviations above the local baseline" in rep_anomaly.explanation
    assert "10.0 standard deviations" in rep_anomaly.explanation


def test_anomalies_api_endpoints():
    client = TestClient(app)

    # 1. Pre-load a baseline
    profile = BaselineProfile(
        baseline_id="base_hr_15_global",
        metric_name="hourly_event_frequency",
        camera_id=None,
        hour_of_day=15,
        day_of_week=None,
        sample_count=5,
        mean_value=3.0,
        std_dev=1.0,
        median_value=3.0,
        min_value=1.0,
        max_value=5.0,
        last_updated="2026-09-30T00:00:00Z",
    )
    baseline_engine._save_baselines([profile])

    # 2. Evaluate anomaly via API endpoint
    res = client.post(
        "/api/v1/anomalies/evaluate",
        json={"observed_count": 15.0, "hour_of_day": 15, "persist": True}
    )
    assert res.status_code == 200
    data = res.json()
    assert data["is_anomaly"] is True
    assert "report" in data
    assert data["report"]["score"] == 12.0

    # 3. List anomalies via GET
    res_list = client.get("/api/v1/anomalies")
    assert res_list.status_code == 200
    anoms = res_list.json()
    assert len(anoms) >= 1
    assert anoms[0]["score"] == 12.0
