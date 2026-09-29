"""
Smart Spectator - Event Engine Package
"""

from .engine import EventEngine
from .service import event_engine_service, event_engine
from .confidence import ConfidenceFilter
from .debouncer import TemporalDebouncer
from .state_machine import EventStateMachine, InvalidStateTransitionError
from .aggregator import PredictionAggregator
from .zones import ZoneEngine, point_inside_polygon
from .rules import RuleEngine
from .severity import SeverityCalculator
from .actions import ActionDispatcher
from .recorder import RecordingManager, CameraRollingBuffer

__all__ = [
    "EventEngine",
    "event_engine_service",
    "event_engine",
    "ConfidenceFilter",
    "TemporalDebouncer",
    "EventStateMachine",
    "InvalidStateTransitionError",
    "PredictionAggregator",
    "ZoneEngine",
    "point_inside_polygon",
    "RuleEngine",
    "SeverityCalculator",
    "ActionDispatcher",
    "RecordingManager",
    "CameraRollingBuffer",
]
