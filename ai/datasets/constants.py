"""
Smart Spectator - Dataset Constants & Event Taxonomy
Defines initial target classes and sequence configurations.
"""

from typing import List, Dict

DEFAULT_EVENT_CLASSES: List[str] = [
    "NORMAL_BACKGROUND",
    "OBJECT_PRESENT",
    "OBJECT_REMOVED",
    "OBJECT_MOVED",
    "PERSON_ENTERED",
    "PERSON_LEFT",
    "ZONE_LOITERING",
    "CAMERA_BLOCKED",
    "TASK_COMPLETED",
]

CLASS_TO_ID: Dict[str, int] = {name: idx for idx, name in enumerate(DEFAULT_EVENT_CLASSES)}
ID_TO_CLASS: Dict[int, str] = {idx: name for idx, name in enumerate(DEFAULT_EVENT_CLASSES)}

DEFAULT_SEQUENCE_LENGTH: int = 30
DEFAULT_SAMPLING_RATE_FPS: float = 5.0
DEFAULT_MAX_OBJECTS: int = 16
