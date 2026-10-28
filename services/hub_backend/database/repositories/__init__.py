"""
Smart Spectator - Database Repositories Package
Encapsulates all direct database SQL queries behind repository abstractions.
"""

from .camera_repo import CameraRepository, camera_repository
from .event_repo import EventRepository, event_repository
from .recording_repo import RecordingRepository, recording_repository
from .zone_repo import ZoneRepository, zone_repository
from .rule_repo import RuleRepository, rule_repository
from .device_repo import DeviceRepository, device_repository
from .audit_repo import AuditRepository, audit_repository

__all__ = [
    "CameraRepository",
    "camera_repository",
    "EventRepository",
    "event_repository",
    "RecordingRepository",
    "recording_repository",
    "ZoneRepository",
    "zone_repository",
    "RuleRepository",
    "rule_repository",
    "DeviceRepository",
    "device_repository",
    "AuditRepository",
    "audit_repository",
]
