"""
Rule Engine — evaluates monitoring conditions against AI observations.
Separates "what do I see?" (vision model) from "what does this mean?" (rules).
"""
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import structlog

from app.models.models import EventType, MonitoringType

log = structlog.get_logger(__name__)


@dataclass
class RuleResult:
    triggered: bool
    event_type: Optional[EventType] = None
    severity: str = "normal"
    description: str = ""
    metadata: Dict[str, Any] = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


class RuleEngine:
    """
    Evaluates monitoring rules against AI observations.

    Rule config schema (stored in MonitoringTask.rule_config):
    {
        "type": "threshold" | "presence" | "state_change" | "custom",
        "target_object": "washing_machine",
        "measurement_key": "water_level_percent",
        "operator": ">=" | "<=" | "==" | "!=" | ">" | "<",
        "threshold_value": 80,
        "state_match": "DOOR_OPEN",
        "require_consecutive": 3,
        "alert_once": true
    }
    """

    def evaluate(
        self,
        observation: Dict[str, Any],
        task_config: Dict[str, Any],
        monitoring_type: MonitoringType,
        history: List[Dict[str, Any]],
    ) -> RuleResult:
        """
        Evaluate rules against the current observation and history.
        Returns a RuleResult indicating whether a rule triggered.
        """
        try:
            if monitoring_type == MonitoringType.WATER_LEVEL:
                return self._eval_water_level(observation, task_config)
            elif monitoring_type == MonitoringType.OBJECT_PRESENCE:
                return self._eval_object_presence(observation, task_config)
            elif monitoring_type == MonitoringType.DOOR_STATE:
                return self._eval_door_state(observation, task_config, history)
            elif monitoring_type == MonitoringType.MACHINE_STATE:
                return self._eval_machine_state(observation, task_config, history)
            elif monitoring_type == MonitoringType.MOTION_DETECTION:
                return self._eval_motion(observation, task_config)
            else:
                return self._eval_generic(observation, task_config)
        except Exception as e:
            log.error("Rule evaluation error", error=str(e))
            return RuleResult(triggered=False)

    def _eval_water_level(self, obs: dict, config: dict) -> RuleResult:
        """IF water_level >= threshold THEN THRESHOLD_REACHED."""
        measurements = obs.get("measurements", {})
        level = measurements.get("water_level_percent")
        threshold = config.get("threshold", 80)

        if level is None:
            # Try from state string if no measurement
            state = obs.get("state", "")
            if "THRESHOLD_REACHED" in state or "FULL" in state:
                return RuleResult(
                    triggered=True,
                    event_type=EventType.THRESHOLD_REACHED,
                    severity="warning",
                    description=f"Water level threshold reached. AI state: {state}",
                    metadata={"state": state, "threshold": threshold},
                )
            return RuleResult(triggered=False)

        if level >= threshold:
            return RuleResult(
                triggered=True,
                event_type=EventType.THRESHOLD_REACHED,
                severity="warning",
                description=f"Water level reached {level:.1f}% (threshold: {threshold}%)",
                metadata={"water_level_percent": level, "threshold": threshold},
            )
        return RuleResult(triggered=False)

    def _eval_object_presence(self, obs: dict, config: dict) -> RuleResult:
        """IF target_object is present/absent THEN trigger."""
        target = config.get("target_object", "")
        expect_present = config.get("expect_present", True)
        objects = obs.get("objects", [])
        labels = [o.get("label", "").lower() for o in objects]
        is_present = any(target.lower() in label for label in labels)

        if expect_present and is_present:
            return RuleResult(
                triggered=True,
                event_type=EventType.OBJECT_DETECTED,
                severity="normal",
                description=f"Target object '{target}' detected.",
                metadata={"target": target, "objects": labels},
            )
        elif not expect_present and not is_present:
            return RuleResult(
                triggered=True,
                event_type=EventType.OBJECT_REMOVED,
                severity="warning",
                description=f"Target object '{target}' is no longer present.",
                metadata={"target": target},
            )
        return RuleResult(triggered=False)

    def _eval_door_state(self, obs: dict, config: dict, history: list) -> RuleResult:
        """IF door == OPEN THEN alert (with temporal confirmation)."""
        state = obs.get("state", "")
        is_open = "OPEN" in state.upper()
        require_consecutive = config.get("require_consecutive", 2)

        if is_open:
            # Check how many consecutive frames show OPEN
            consecutive = 1
            for h in reversed(history[-require_consecutive:]):
                if "OPEN" in h.get("state", "").upper():
                    consecutive += 1
                else:
                    break

            if consecutive >= require_consecutive:
                return RuleResult(
                    triggered=True,
                    event_type=EventType.ALERT_TRIGGERED,
                    severity="critical",
                    description="Door is open — confirmed across multiple frames.",
                    metadata={"state": state, "consecutive_frames": consecutive},
                )
        return RuleResult(triggered=False)

    def _eval_machine_state(self, obs: dict, config: dict, history: list) -> RuleResult:
        """IF machine transitions from RUNNING to STOPPED THEN event."""
        state = obs.get("state", "")
        is_stopped = "STOP" in state.upper() or "OFF" in state.upper() or "IDLE" in state.upper()

        if is_stopped and history:
            last_state = history[-1].get("state", "")
            was_running = "RUNNING" in last_state.upper() or "ON" in last_state.upper() or "ACTIVE" in last_state.upper()
            if was_running:
                return RuleResult(
                    triggered=True,
                    event_type=EventType.STATE_CHANGED,
                    severity="normal",
                    description="Machine has stopped.",
                    metadata={"previous_state": last_state, "current_state": state},
                )
        return RuleResult(triggered=False)

    def _eval_motion(self, obs: dict, config: dict) -> RuleResult:
        """IF change_detected THEN event."""
        if obs.get("change_detected", False):
            confidence = obs.get("confidence", 0.0)
            threshold = config.get("threshold", 0.5)
            if confidence >= threshold:
                return RuleResult(
                    triggered=True,
                    event_type=EventType.STATE_CHANGED,
                    severity="normal",
                    description="Motion detected.",
                    metadata={"confidence": confidence},
                )
        return RuleResult(triggered=False)

    def _eval_generic(self, obs: dict, config: dict) -> RuleResult:
        """Generic rule evaluation using config-specified conditions."""
        state = obs.get("state", "")
        state_match = config.get("state_match")
        if state_match and state_match.upper() in state.upper():
            return RuleResult(
                triggered=True,
                event_type=EventType.STATE_CHANGED,
                severity=config.get("severity", "normal"),
                description=f"Condition met: state matches '{state_match}'",
                metadata={"state": state, "matched": state_match},
            )

        # Threshold check on any measurement
        measurement_key = config.get("measurement_key")
        threshold_value = config.get("threshold_value")
        operator = config.get("operator", ">=")
        if measurement_key and threshold_value is not None:
            value = obs.get("measurements", {}).get(measurement_key)
            if value is not None:
                triggered = self._compare(value, operator, threshold_value)
                if triggered:
                    return RuleResult(
                        triggered=True,
                        event_type=EventType.THRESHOLD_REACHED,
                        severity=config.get("severity", "warning"),
                        description=f"{measurement_key} {operator} {threshold_value} (actual: {value})",
                        metadata={"key": measurement_key, "value": value, "threshold": threshold_value},
                    )
        return RuleResult(triggered=False)

    def _compare(self, value: Any, operator: str, threshold: Any) -> bool:
        try:
            v, t = float(value), float(threshold)
            ops = {">=": v >= t, "<=": v <= t, ">": v > t, "<": v < t, "==": v == t, "!=": v != t}
            return ops.get(operator, False)
        except (TypeError, ValueError):
            return str(value) == str(threshold)
