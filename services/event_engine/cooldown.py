"""
Smart Spectator - Event Engine: Cooldown Manager
Prevents duplicate event flooding by enforcing temporal cooldowns per camera and rule.
"""

import time
from typing import Dict, Tuple, Optional


class CooldownManager:
    """Tracks and enforces cooldown windows for events and rule executions."""

    def __init__(self, default_cooldown_seconds: float = 15.0):
        self.default_cooldown_seconds = default_cooldown_seconds
        # Key: (camera_id, event_type) -> expiration timestamp
        self._event_cooldowns: Dict[Tuple[str, str], float] = {}
        # Key: rule_id -> expiration timestamp
        self._rule_cooldowns: Dict[str, float] = {}

    def is_event_in_cooldown(self, camera_id: str, event_type: str, now: Optional[float] = None) -> bool:
        t = now if now is not None else time.time()
        key = (camera_id, event_type)
        return self._event_cooldowns.get(key, 0.0) > t

    def trigger_event_cooldown(
        self, camera_id: str, event_type: str, duration: Optional[float] = None, now: Optional[float] = None
    ) -> None:
        t = now if now is not None else time.time()
        d = duration if duration is not None else self.default_cooldown_seconds
        self._event_cooldowns[(camera_id, event_type)] = t + d

    def is_rule_in_cooldown(self, rule_id: str, now: Optional[float] = None) -> bool:
        t = now if now is not None else time.time()
        return self._rule_cooldowns.get(rule_id, 0.0) > t

    def trigger_rule_cooldown(self, rule_id: str, duration: float, now: Optional[float] = None) -> None:
        t = now if now is not None else time.time()
        self._rule_cooldowns[rule_id] = t + duration

    def reset_event_cooldown(self, camera_id: str, event_type: str) -> None:
        self._event_cooldowns.pop((camera_id, event_type), None)

    def reset_rule_cooldown(self, rule_id: str) -> None:
        self._rule_cooldowns.pop(rule_id, None)

    def clear(self) -> None:
        self._event_cooldowns.clear()
        self._rule_cooldowns.clear()
