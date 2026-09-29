"""
Smart Spectator - Phase 4 Rule Engine Unit Tests
Tests structured JSON rules, time of day windows, cooldowns, and action dispatching.
Conforms to Sections 11, 12, 70 of Phase 4 specification.
"""

from datetime import datetime, time as dtime
import pytest

from shared.schemas.v1.models import EventRule, EventSeverity
from services.event_engine.rules import RuleEngine, is_time_in_range
from services.event_engine.cooldown import CooldownManager


def test_time_in_range():
    # Daytime: 09:00 to 17:00
    t_start = dtime(9, 0)
    t_end = dtime(17, 0)
    assert is_time_in_range(dtime(12, 0), t_start, t_end) is True
    assert is_time_in_range(dtime(8, 59), t_start, t_end) is False
    assert is_time_in_range(dtime(18, 0), t_start, t_end) is False

    # Nighttime (midnight wrap): 22:00 to 06:00
    n_start = dtime(22, 0)
    n_end = dtime(6, 0)
    assert is_time_in_range(dtime(23, 30), n_start, n_end) is True
    assert is_time_in_range(dtime(2, 0), n_start, n_end) is True
    assert is_time_in_range(dtime(14, 0), n_start, n_end) is False


def test_rule_matching_and_filtering():
    cd = CooldownManager()
    re = RuleEngine(cooldown_manager=cd)

    rule1 = EventRule(
        rule_id="r1",
        name="Front Door Person Alert",
        enabled=True,
        conditions={
            "event_type": "PERSON_ENTERED",
            "camera_id": "front_cam",
            "minimum_confidence": 0.80,
        },
        actions=["CREATE_EVENT", "SAVE_CLIP"],
        cooldown_seconds=30,
    )
    re._rules["r1"] = rule1

    # Matching case
    matched = re.match_rules("front_cam", "PERSON_ENTERED", 0.85)
    assert len(matched) == 1
    assert matched[0][0].rule_id == "r1"
    assert "SAVE_CLIP" in matched[0][1]

    # Non-matching camera
    matched_cam = re.match_rules("back_cam", "PERSON_ENTERED", 0.85)
    assert len(matched_cam) == 0

    # Non-matching confidence (below 0.80)
    matched_conf = re.match_rules("front_cam", "PERSON_ENTERED", 0.75)
    assert len(matched_conf) == 0

    # Non-matching event_type
    matched_type = re.match_rules("front_cam", "OBJECT_REMOVED", 0.85)
    assert len(matched_type) == 0


def test_rule_cooldown():
    cd = CooldownManager()
    re = RuleEngine(cooldown_manager=cd)

    rule = EventRule(
        rule_id="r_cool",
        name="Cooldown Test",
        enabled=True,
        conditions={"event_type": "PERSON_ENTERED"},
        actions=["CREATE_EVENT"],
        cooldown_seconds=10,
    )
    re._rules["r_cool"] = rule

    # 1st match: succeeds and enters cooldown
    matched1 = re.match_rules("cam_01", "PERSON_ENTERED", 0.90)
    assert len(matched1) == 1

    # Immediate 2nd match: blocked by cooldown!
    matched2 = re.match_rules("cam_01", "PERSON_ENTERED", 0.90)
    assert len(matched2) == 0

    # Reset cooldown: succeeds again
    cd.reset_rule_cooldown("r_cool")
    matched3 = re.match_rules("cam_01", "PERSON_ENTERED", 0.90)
    assert len(matched3) == 1


def test_disabled_rule():
    re = RuleEngine(cooldown_manager=CooldownManager())
    rule = EventRule(
        rule_id="r_dis",
        name="Disabled Rule",
        enabled=False,
        conditions={"event_type": "OBJECT_REMOVED"},
        actions=["CREATE_EVENT"],
    )
    re._rules["r_dis"] = rule

    matched = re.match_rules("cam_01", "OBJECT_REMOVED", 0.95)
    assert len(matched) == 0
