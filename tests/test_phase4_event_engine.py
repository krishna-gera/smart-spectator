"""
Smart Spectator - Phase 4 Event Engine Unit Tests
Tests confidence filtering, debouncing, deduplication, state machine, and explanations.
Conforms to Sections 6, 7, 8, 9, 10, 68 of Phase 4 specification.
"""

from datetime import datetime, timezone
import pytest
import time

from shared.schemas.v1.models import (
    EventPrediction,
    Event,
    EventStatus,
    EventSeverity,
)
from services.event_engine.confidence import ConfidenceFilter
from services.event_engine.debouncer import TemporalDebouncer
from services.event_engine.state_machine import EventStateMachine, InvalidStateTransitionError
from services.event_engine.aggregator import PredictionAggregator
from services.event_engine.cooldown import CooldownManager
from services.event_engine.severity import SeverityCalculator
from services.event_engine.lifecycle import generate_event_explanation


def test_confidence_filter_thresholds():
    cf = ConfidenceFilter()
    # Below min_prediction (0.70 for OBJECT_REMOVED) -> not candidate
    pred_low = EventPrediction(
        camera_id="cam_test",
        event_type="OBJECT_REMOVED",
        confidence=0.65,
    )
    assert not cf.is_candidate(pred_low)

    # Candidate but not confirmed
    pred_cand = EventPrediction(
        camera_id="cam_test",
        event_type="OBJECT_REMOVED",
        confidence=0.75,
    )
    assert cf.is_candidate(pred_cand)
    assert not cf.is_confirmed(pred_cand)

    # Confirmed (>= 0.80)
    pred_conf = EventPrediction(
        camera_id="cam_test",
        event_type="OBJECT_REMOVED",
        confidence=0.85,
    )
    assert cf.is_confirmed(pred_conf)
    assert not cf.is_high_confidence(pred_conf)

    # High confidence (>= 0.90)
    pred_high = EventPrediction(
        camera_id="cam_test",
        event_type="OBJECT_REMOVED",
        confidence=0.92,
    )
    assert cf.is_high_confidence(pred_high)


def test_temporal_debouncer_consecutive_streaks():
    debouncer = TemporalDebouncer(min_consecutive=2, resolution_timeout_seconds=3.0)

    # First prediction: streak = 1 -> not yet confirmed
    is_conf, streak = debouncer.record_positive_prediction("cam_01", "PERSON_ENTERED", timestamp=100.0)
    assert not is_conf
    assert streak == 1

    # Second consecutive prediction: streak = 2 -> confirmed!
    is_conf, streak = debouncer.record_positive_prediction("cam_01", "PERSON_ENTERED", timestamp=101.0)
    assert is_conf
    assert streak == 2

    # Camera isolation: cam_02 streak must be 1, not 3
    is_conf_c2, streak_c2 = debouncer.record_positive_prediction("cam_02", "PERSON_ENTERED", timestamp=101.0)
    assert not is_conf_c2
    assert streak_c2 == 1


def test_temporal_debouncer_resolution_timeout():
    debouncer = TemporalDebouncer(min_consecutive=2, resolution_timeout_seconds=3.0)
    debouncer.record_positive_prediction("cam_01", "OBJECT_REMOVED", timestamp=100.0)

    # No timeout after 2 seconds
    timed_out = debouncer.check_resolution_timeouts([("cam_01", "OBJECT_REMOVED")], current_time=102.0)
    assert len(timed_out) == 0

    # Timed out after 3.5 seconds
    timed_out = debouncer.check_resolution_timeouts([("cam_01", "OBJECT_REMOVED")], current_time=103.5)
    assert len(timed_out) == 1
    assert timed_out[0] == ("cam_01", "OBJECT_REMOVED")


def test_event_state_machine_valid_and_invalid_transitions():
    sm = EventStateMachine()

    # Valid transitions: DETECTED -> CONFIRMED -> ACTIVE -> RESOLVED
    assert sm.can_transition(EventStatus.DETECTED, EventStatus.CONFIRMED)
    s1 = sm.transition(EventStatus.DETECTED, EventStatus.CONFIRMED)
    assert s1 == EventStatus.CONFIRMED

    assert sm.can_transition(EventStatus.CONFIRMED, EventStatus.ACTIVE)
    s2 = sm.transition(EventStatus.CONFIRMED, EventStatus.ACTIVE)
    assert s2 == EventStatus.ACTIVE

    assert sm.can_transition(EventStatus.ACTIVE, EventStatus.RESOLVED)
    s3 = sm.transition(EventStatus.ACTIVE, EventStatus.RESOLVED)
    assert s3 == EventStatus.RESOLVED

    # Terminal state: RESOLVED cannot transition back to DETECTED
    assert not sm.can_transition(EventStatus.RESOLVED, EventStatus.DETECTED)
    with pytest.raises(InvalidStateTransitionError):
        sm.transition(EventStatus.RESOLVED, EventStatus.DETECTED)

    # DISMISSED cannot transition to ACTIVE
    with pytest.raises(InvalidStateTransitionError):
        sm.transition(EventStatus.DISMISSED, EventStatus.ACTIVE)


def test_prediction_aggregator_deduplication():
    aggregator = PredictionAggregator(event_window_seconds=5.0)

    # Initial event
    now = datetime.now(timezone.utc)
    ev = Event(
        event_id="ev_test_1",
        camera_id="cam_01",
        event_type="OBJECT_REMOVED",
        status=EventStatus.ACTIVE,
        confidence=0.82,
        summary="Test event",
        timestamp=now,
        created_at=now,
        updated_at=now,
        involved_track_ids=[101],
    )
    aggregator.register_active_event(ev)

    # Incoming prediction within 2 seconds with overlapping track
    pred = EventPrediction(
        camera_id="cam_01",
        event_type="OBJECT_REMOVED",
        confidence=0.89,
        affected_tracks=[101, 102],
        timestamp=now,
    )

    is_existing, existing = aggregator.correlate(pred, now=now.timestamp() + 2.0)
    assert is_existing is True
    assert existing is not None
    assert existing.event_id == "ev_test_1"
    # Max confidence updated
    assert existing.confidence == 0.89
    # Tracks merged
    assert 101 in existing.involved_track_ids
    assert 102 in existing.involved_track_ids

    # Unrelated prediction on cam_02 -> not existing
    pred_c2 = EventPrediction(
        camera_id="cam_02",
        event_type="OBJECT_REMOVED",
        confidence=0.90,
    )
    is_ext_c2, _ = aggregator.correlate(pred_c2, now=now.timestamp() + 2.0)
    assert is_ext_c2 is False


def test_severity_calculator():
    calc = SeverityCalculator()
    # Baseline defaults
    assert calc.calculate("NORMAL_BACKGROUND", 0.95) == EventSeverity.LOW
    assert calc.calculate("OBJECT_REMOVED", 0.85) == EventSeverity.MEDIUM
    assert calc.calculate("CAMERA_BLOCKED", 0.75) == EventSeverity.HIGH

    # High confidence camera blockage escalates to CRITICAL
    assert calc.calculate("CAMERA_BLOCKED", 0.95) == EventSeverity.CRITICAL

    # Rule override takes precedence
    assert calc.calculate("OBJECT_REMOVED", 0.80, rule_override=EventSeverity.CRITICAL) == EventSeverity.CRITICAL


def test_deterministic_explanations():
    exp_rem = generate_event_explanation(
        "OBJECT_REMOVED", 0.88, "Front Door", affected_tracks=[42], metadata={"presence_duration_seconds": 4.5}
    )
    assert "disappeared from Front Door" in exp_rem
    assert "4.5s" in exp_rem
    assert "Track #42" in exp_rem

    exp_loit = generate_event_explanation(
        "ZONE_LOITERING", 0.92, "Backyard", zone_name="Restricted Zone", metadata={"dwell_seconds": 35.0}
    )
    assert "'Restricted Zone' zone" in exp_loit
    assert "35 seconds" in exp_loit
