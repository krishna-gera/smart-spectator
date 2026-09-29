"""
Smart Spectator - Event Engine: User Rule Engine
Evaluates structured JSON rules without dangerous arbitrary code execution.
Conforms to Sections 11, 12, 22 of Phase 4 specification.
"""

from datetime import datetime, time as dtime, timezone
import json
import uuid
from typing import List, Dict, Any, Optional, Tuple
import sqlite3

from shared.schemas.v1.models import EventRule, EventPrediction, EventSeverity
from services.hub_backend.database.connection import db_session
from .cooldown import CooldownManager


def parse_time_str(time_str: Optional[str]) -> Optional[dtime]:
    """Parses 'HH:MM' string into datetime.time object."""
    if not time_str:
        return None
    try:
        parts = time_str.strip().split(":")
        return dtime(hour=int(parts[0]), minute=int(parts[1]))
    except Exception:
        return None


def is_time_in_range(current_time: dtime, start: Optional[dtime], end: Optional[dtime]) -> bool:
    """
    Checks if current_time falls between start and end.
    Correctly handles midnight wrap-around (e.g. 22:00 to 06:00).
    """
    if start is None or end is None:
        return True
    if start <= end:
        return start <= current_time <= end
    else: # Crosses midnight
        return current_time >= start or current_time <= end


class RuleEngine:
    """
    Structured Rule Engine.
    Matches events against user-defined automation rules and dispatches actions.
    """

    def __init__(self, cooldown_manager: Optional[CooldownManager] = None):
        self.cooldown_manager = cooldown_manager or CooldownManager()
        self._rules: Dict[str, EventRule] = {}
        self.load_rules_from_db()

    def load_rules_from_db(self) -> None:
        """Loads all enabled and disabled rules from SQLite."""
        try:
            with db_session() as conn:
                cursor = conn.execute(
                    "SELECT rule_id, name, enabled, conditions_json, actions_json, "
                    "cooldown_seconds, severity_override, created_at, updated_at "
                    "FROM event_rules"
                )
                rows = cursor.fetchall()
                self._rules.clear()
                for r in rows:
                    cond = json.loads(r["conditions_json"])
                    acts = json.loads(r["actions_json"])
                    sev_override = None
                    if r.get("severity_override"):
                        try:
                            sev_override = EventSeverity(r["severity_override"].lower())
                        except Exception:
                            pass

                    rule = EventRule(
                        rule_id=r["rule_id"],
                        name=r["name"],
                        enabled=bool(r["enabled"]),
                        conditions=cond,
                        actions=acts,
                        cooldown_seconds=r["cooldown_seconds"],
                        severity_override=sev_override,
                        created_at=datetime.fromisoformat(r["created_at"]) if isinstance(r["created_at"], str) else r["created_at"],
                        updated_at=datetime.fromisoformat(r["updated_at"]) if isinstance(r["updated_at"], str) else r["updated_at"],
                    )
                    self._rules[rule.rule_id] = rule
        except Exception as e:
            print(f"[RuleEngine] Database load note: {e}")

    def get_all_rules(self) -> List[EventRule]:
        return list(self._rules.values())

    def get_rule(self, rule_id: str) -> Optional[EventRule]:
        return self._rules.get(rule_id)

    def save_rule_to_db(self, rule: EventRule) -> None:
        with db_session() as conn:
            conn.execute(
                """
                INSERT INTO event_rules (
                    rule_id, name, enabled, conditions_json, actions_json,
                    cooldown_seconds, severity_override, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(rule_id) DO UPDATE SET
                    name = excluded.name,
                    enabled = excluded.enabled,
                    conditions_json = excluded.conditions_json,
                    actions_json = excluded.actions_json,
                    cooldown_seconds = excluded.cooldown_seconds,
                    severity_override = excluded.severity_override,
                    updated_at = excluded.updated_at
                """,
                (
                    rule.rule_id,
                    rule.name,
                    1 if rule.enabled else 0,
                    json.dumps(rule.conditions),
                    json.dumps(rule.actions),
                    rule.cooldown_seconds,
                    rule.severity_override.value if rule.severity_override else None,
                    rule.created_at.isoformat(),
                    rule.updated_at.isoformat(),
                )
            )
        self._rules[rule.rule_id] = rule

    def delete_rule(self, rule_id: str) -> bool:
        if rule_id in self._rules:
            del self._rules[rule_id]
        with db_session() as conn:
            cursor = conn.execute("DELETE FROM event_rules WHERE rule_id = ?", (rule_id,))
            return cursor.rowcount > 0

    def evaluate_rule(
        self,
        rule: EventRule,
        camera_id: str,
        event_type: str,
        confidence: float,
        zone_id: Optional[str] = None,
        event_time: Optional[datetime] = None,
    ) -> bool:
        """Evaluates structured rule conditions safely against candidate event parameters."""
        if not rule.enabled:
            return False

        # Check rule cooldown
        if self.cooldown_manager.is_rule_in_cooldown(rule.rule_id):
            return False

        cond = rule.conditions

        # 1. Event Type condition
        expected_type = cond.get("event_type")
        if expected_type and expected_type != "*":
            if isinstance(expected_type, list):
                if event_type not in expected_type:
                    return False
            elif expected_type != event_type:
                return False

        # 2. Camera ID condition
        expected_cam = cond.get("camera_id")
        if expected_cam and expected_cam != "*":
            if expected_cam != camera_id:
                return False

        # 3. Zone ID condition
        expected_zone = cond.get("zone_id")
        if expected_zone and expected_zone != "*":
            if expected_zone != zone_id:
                return False

        # 4. Minimum Confidence condition
        min_conf = cond.get("minimum_confidence")
        if min_conf is not None:
            if confidence < float(min_conf):
                return False

        # 5. Time of day condition
        t_start = parse_time_str(cond.get("time_start"))
        t_end = parse_time_str(cond.get("time_end"))
        if t_start or t_end:
            now_dt = event_time or datetime.now()
            if not is_time_in_range(now_dt.time(), t_start, t_end):
                return False

        return True

    def match_rules(
        self,
        camera_id: str,
        event_type: str,
        confidence: float,
        zone_id: Optional[str] = None,
        event_time: Optional[datetime] = None,
    ) -> List[Tuple[EventRule, List[str]]]:
        """
        Matches active event parameters against all configured rules.
        Returns list of matched (Rule, Actions).
        Triggers rule cooldown upon match.
        """
        matched: List[Tuple[EventRule, List[str]]] = []
        for rule in self._rules.values():
            if self.evaluate_rule(rule, camera_id, event_type, confidence, zone_id, event_time):
                self.cooldown_manager.trigger_rule_cooldown(rule.rule_id, float(rule.cooldown_seconds))
                matched.append((rule, rule.actions))
        return matched
