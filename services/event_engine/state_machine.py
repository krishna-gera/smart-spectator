"""
Smart Spectator - Event Engine: State Machine
Strictly manages and validates event lifecycle transitions.
"""

from typing import Set, Dict
from shared.schemas.v1.models import EventStatus


class InvalidStateTransitionError(ValueError):
    """Raised when an illegal event state transition is attempted."""
    pass


class EventStateMachine:
    """
    Validates and executes lifecycle state transitions.
    Supported states:
      DETECTED   -> Prediction received and passed confidence filter
      CONFIRMED  -> Debounced over consecutive observations
      ACTIVE     -> Event is occurring in real-time
      RESOLVED   -> Event condition has ceased
      DISMISSED  -> Canceled by user or rejected as false positive
    """

    ALLOWED_TRANSITIONS: Dict[EventStatus, Set[EventStatus]] = {
        EventStatus.DETECTED: {
            EventStatus.CONFIRMED,
            EventStatus.DISMISSED,
        },
        EventStatus.CONFIRMED: {
            EventStatus.ACTIVE,
            EventStatus.RESOLVED,
            EventStatus.DISMISSED,
        },
        EventStatus.ACTIVE: {
            EventStatus.RESOLVED,
            EventStatus.DISMISSED,
        },
        EventStatus.RESOLVED: set(),  # Terminal state
        EventStatus.DISMISSED: set(), # Terminal state
    }

    @classmethod
    def can_transition(cls, current: EventStatus, target: EventStatus) -> bool:
        if current == target:
            return True
        return target in cls.ALLOWED_TRANSITIONS.get(current, set())

    @classmethod
    def transition(cls, current: EventStatus, target: EventStatus) -> EventStatus:
        if current == target:
            return current
        if not cls.can_transition(current, target):
            raise InvalidStateTransitionError(
                f"Illegal event state transition from '{current.value}' to '{target.value}'."
            )
        return target
