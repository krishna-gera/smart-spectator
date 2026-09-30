"""
Phase 10 Tests — Local Query Engine & Natural Language Interpreter
Conforms to Sections 12, 13, 30 & 37 of Phase 10 Specification.
Validates:
1. Deterministic natural-language command interpretation to StructuredQuery objects.
2. Parameterized execution of structured queries against events and anomalies.
3. Query API endpoint (/api/v1/query).
"""

from datetime import datetime, timezone
from fastapi.testclient import TestClient
import pytest

from services.hub_backend.query import (
    query_interpreter,
    local_query_engine,
    StructuredQuery,
)
from services.hub_backend.config import settings
from services.hub_backend.database.connection import init_database, get_db
from services.hub_backend.main import app


@pytest.fixture(autouse=True)
def setup_test_db(tmp_path):
    orig = settings.DATABASE_PATH
    settings.DATABASE_PATH = tmp_path / "test_query.db"
    init_database()
    yield
    settings.DATABASE_PATH = orig


def test_local_query_interpreter_natural_commands():
    # 1. "show today's events"
    sq1 = query_interpreter.interpret("show today's events")
    assert sq1.after is not None
    assert "T00:00:00" in sq1.after

    # 2. "show person entries after 10pm"
    sq2 = query_interpreter.interpret("show person entries after 10pm")
    assert sq2.event_type == "person_entered"
    assert "22:00:00" in sq2.after

    # 3. "show critical events on front_door"
    sq3 = query_interpreter.interpret("show critical events on front_door")
    assert sq3.priority == "CRITICAL"
    assert sq3.camera_id == "front_door"

    # 4. "show anomalies"
    sq4 = query_interpreter.interpret("show anomalies")
    assert sq4.is_anomaly is True


def test_query_engine_and_api_integration():
    client = TestClient(app)

    # Insert test events
    now_str = datetime.now(timezone.utc).isoformat()
    with get_db() as conn:
        conn.execute("INSERT OR IGNORE INTO cameras (camera_id, name, source_type) VALUES ('front_door', 'Front Door', 'phone')")
        conn.execute("INSERT OR IGNORE INTO cameras (camera_id, name, source_type) VALUES ('back_door', 'Back Door', 'phone')")
        conn.execute(
            """
            INSERT INTO events (event_id, camera_id, event_type, severity, priority, confidence, summary, timestamp)
            VALUES
            ('ev_q1', 'front_door', 'person_entered', 'high', 'HIGH', 0.92, 'entry', ?),
            ('ev_q2', 'back_door', 'motion_detected', 'low', 'LOW', 0.70, 'motion', ?)
            """,
            (now_str, now_str),
        )
        conn.commit()

    # 1. Test structured query via API
    res1 = client.post(
        "/api/v1/query",
        json={"event_type": "person_entered", "camera_id": "front_door"}
    )
    assert res1.status_code == 200
    data1 = res1.json()
    assert data1["total_count"] == 1
    assert data1["results"][0]["event_id"] == "ev_q1"

    # 2. Test natural language query via API
    res2 = client.post(
        "/api/v1/query",
        json={"natural_query": "show person entries on front_door"}
    )
    assert res2.status_code == 200
    data2 = res2.json()
    assert data2["total_count"] == 1
    assert data2["results"][0]["event_id"] == "ev_q1"
