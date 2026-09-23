"""
All SQLAlchemy ORM models for Smart Spectator.
"""
import uuid
from datetime import datetime
from enum import Enum as PyEnum
from typing import Optional

from sqlalchemy import (
    Boolean, Column, DateTime, Enum, Float, ForeignKey,
    Integer, JSON, String, Text, UniqueConstraint, func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.database.session import Base


def uuid_pk():
    return Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)


def now_utc():
    return Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


# ─── Enums ────────────────────────────────────────────────────────────────────

class UserRole(str, PyEnum):
    CAM_CODER = "CAM_CODER"
    VIEW_ACCESS = "VIEW_ACCESS"
    ADMIN = "ADMIN"


class DeviceType(str, PyEnum):
    CAMERA = "CAMERA"
    VIEWER = "VIEWER"


class DevicePlatform(str, PyEnum):
    ANDROID = "ANDROID"
    IOS = "IOS"
    WEB = "WEB"


class PairingStatus(str, PyEnum):
    PENDING = "PENDING"
    ACTIVE = "ACTIVE"
    REVOKED = "REVOKED"


class MonitoringType(str, PyEnum):
    WATER_LEVEL = "WATER_LEVEL"
    OBJECT_PRESENCE = "OBJECT_PRESENCE"
    DOOR_STATE = "DOOR_STATE"
    MACHINE_STATE = "MACHINE_STATE"
    MOTION_DETECTION = "MOTION_DETECTION"
    CUSTOM = "CUSTOM"


class TaskStatus(str, PyEnum):
    IDLE = "IDLE"
    MONITORING = "MONITORING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    PAUSED = "PAUSED"


class SessionStatus(str, PyEnum):
    ACTIVE = "ACTIVE"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    INTERRUPTED = "INTERRUPTED"


class EventType(str, PyEnum):
    OBJECT_DETECTED = "OBJECT_DETECTED"
    OBJECT_REMOVED = "OBJECT_REMOVED"
    STATE_CHANGED = "STATE_CHANGED"
    THRESHOLD_REACHED = "THRESHOLD_REACHED"
    MONITORING_COMPLETED = "MONITORING_COMPLETED"
    MONITORING_FAILED = "MONITORING_FAILED"
    CONNECTION_LOST = "CONNECTION_LOST"
    CONNECTION_RESTORED = "CONNECTION_RESTORED"
    LOW_CONFIDENCE = "LOW_CONFIDENCE"
    ALERT_TRIGGERED = "ALERT_TRIGGERED"


class AlertSeverity(str, PyEnum):
    INFO = "INFO"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"


class FrameRetention(str, PyEnum):
    NONE = "NONE"
    SHORT = "SHORT"
    STANDARD = "STANDARD"
    FULL = "FULL"


class NotificationStatus(str, PyEnum):
    PENDING = "PENDING"
    SENT = "SENT"
    FAILED = "FAILED"


# ─── Models ───────────────────────────────────────────────────────────────────

class User(Base):
    __tablename__ = "users"

    id = uuid_pk()
    email = Column(String(255), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=True)  # null if OAuth
    display_name = Column(String(100), nullable=False, default="")
    role = Column(Enum(UserRole), nullable=False, default=UserRole.VIEW_ACCESS)
    is_active = Column(Boolean, nullable=False, default=True)
    is_verified = Column(Boolean, nullable=False, default=False)
    avatar_url = Column(String(500), nullable=True)
    supabase_uid = Column(String(255), unique=True, nullable=True, index=True)
    created_at = now_utc()
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    devices = relationship("Device", back_populates="user", cascade="all, delete-orphan")
    monitoring_tasks = relationship("MonitoringTask", back_populates="user")
    alerts = relationship("Alert", back_populates="user")
    notifications = relationship("Notification", back_populates="user")
    permissions = relationship("Permission", back_populates="user")


class Device(Base):
    __tablename__ = "devices"

    id = uuid_pk()
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    device_name = Column(String(100), nullable=False)
    device_type = Column(Enum(DeviceType), nullable=False)
    platform = Column(Enum(DevicePlatform), nullable=False)
    push_token = Column(String(500), nullable=True)
    app_version = Column(String(20), nullable=True)
    os_version = Column(String(20), nullable=True)
    device_model = Column(String(100), nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)
    last_seen_at = Column(DateTime(timezone=True), nullable=True)
    created_at = now_utc()

    user = relationship("User", back_populates="devices")
    camera_device = relationship("CameraDevice", back_populates="device", uselist=False)
    viewer_device = relationship("ViewerDevice", back_populates="device", uselist=False)


class CameraDevice(Base):
    __tablename__ = "camera_devices"

    id = uuid_pk()
    device_id = Column(UUID(as_uuid=True), ForeignKey("devices.id", ondelete="CASCADE"), unique=True, nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(100), nullable=False, default="Smart Spectator Camera")
    description = Column(Text, nullable=True)
    is_online = Column(Boolean, nullable=False, default=False)
    battery_level = Column(Integer, nullable=True)
    network_type = Column(String(20), nullable=True)  # wifi, cellular, etc.
    ip_address = Column(String(45), nullable=True)
    firmware_version = Column(String(20), nullable=True)
    last_heartbeat_at = Column(DateTime(timezone=True), nullable=True)
    is_monitoring = Column(Boolean, nullable=False, default=False)
    camera_resolution = Column(String(20), nullable=True, default="720p")
    analysis_interval = Column(Integer, nullable=False, default=2)
    privacy_mode = Column(Boolean, nullable=False, default=False)
    created_at = now_utc()
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    device = relationship("Device", back_populates="camera_device")
    user = relationship("User")
    pairing_codes = relationship("PairingCode", back_populates="camera_device", cascade="all, delete-orphan")
    monitoring_tasks = relationship("MonitoringTask", back_populates="camera")
    observations = relationship("Observation", back_populates="camera")
    events = relationship("Event", back_populates="camera")
    frames = relationship("Frame", back_populates="camera")


class ViewerDevice(Base):
    __tablename__ = "viewer_devices"

    id = uuid_pk()
    device_id = Column(UUID(as_uuid=True), ForeignKey("devices.id", ondelete="CASCADE"), unique=True, nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    created_at = now_utc()

    device = relationship("Device", back_populates="viewer_device")
    user = relationship("User")


class DevicePair(Base):
    __tablename__ = "device_pairs"
    __table_args__ = (UniqueConstraint("camera_id", "viewer_device_id", name="uq_camera_viewer"),)

    id = uuid_pk()
    camera_id = Column(UUID(as_uuid=True), ForeignKey("camera_devices.id", ondelete="CASCADE"), nullable=False)
    viewer_device_id = Column(UUID(as_uuid=True), ForeignKey("viewer_devices.id", ondelete="CASCADE"), nullable=False)
    status = Column(Enum(PairingStatus), nullable=False, default=PairingStatus.ACTIVE)
    paired_at = now_utc()
    revoked_at = Column(DateTime(timezone=True), nullable=True)

    camera = relationship("CameraDevice")
    viewer_device = relationship("ViewerDevice")


class PairingCode(Base):
    __tablename__ = "pairing_codes"

    id = uuid_pk()
    camera_device_id = Column(UUID(as_uuid=True), ForeignKey("camera_devices.id", ondelete="CASCADE"), nullable=False)
    code = Column(String(16), nullable=False, index=True)
    qr_data = Column(Text, nullable=True)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    is_used = Column(Boolean, nullable=False, default=False)
    used_at = Column(DateTime(timezone=True), nullable=True)
    used_by_device_id = Column(UUID(as_uuid=True), nullable=True)
    created_at = now_utc()

    camera_device = relationship("CameraDevice", back_populates="pairing_codes")


class MonitoringTask(Base):
    __tablename__ = "monitoring_tasks"

    id = uuid_pk()
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    camera_id = Column(UUID(as_uuid=True), ForeignKey("camera_devices.id", ondelete="SET NULL"), nullable=True, index=True)
    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    monitoring_type = Column(Enum(MonitoringType), nullable=False, default=MonitoringType.CUSTOM)
    condition = Column(Text, nullable=True)  # human-language description
    target_object = Column(String(100), nullable=True)
    threshold = Column(Float, nullable=True)  # e.g. 0.8 for 80%
    analysis_interval = Column(Integer, nullable=False, default=2)  # seconds
    status = Column(Enum(TaskStatus), nullable=False, default=TaskStatus.IDLE)
    rule_config = Column(JSON, nullable=True)  # structured rule configuration
    created_at = now_utc()
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    user = relationship("User", back_populates="monitoring_tasks")
    camera = relationship("CameraDevice", back_populates="monitoring_tasks")
    sessions = relationship("MonitoringSession", back_populates="task", cascade="all, delete-orphan")
    events = relationship("Event", back_populates="task")


class MonitoringSession(Base):
    __tablename__ = "monitoring_sessions"

    id = uuid_pk()
    task_id = Column(UUID(as_uuid=True), ForeignKey("monitoring_tasks.id", ondelete="CASCADE"), nullable=False, index=True)
    camera_id = Column(UUID(as_uuid=True), ForeignKey("camera_devices.id", ondelete="SET NULL"), nullable=True)
    status = Column(Enum(SessionStatus), nullable=False, default=SessionStatus.ACTIVE)
    started_at = now_utc()
    ended_at = Column(DateTime(timezone=True), nullable=True)
    frame_count = Column(Integer, nullable=False, default=0)
    event_count = Column(Integer, nullable=False, default=0)

    task = relationship("MonitoringTask", back_populates="sessions")
    observations = relationship("Observation", back_populates="session", cascade="all, delete-orphan")


class Observation(Base):
    __tablename__ = "observations"

    id = uuid_pk()
    session_id = Column(UUID(as_uuid=True), ForeignKey("monitoring_sessions.id", ondelete="CASCADE"), nullable=False, index=True)
    camera_id = Column(UUID(as_uuid=True), ForeignKey("camera_devices.id", ondelete="CASCADE"), nullable=False, index=True)
    frame_id = Column(UUID(as_uuid=True), ForeignKey("frames.id", ondelete="SET NULL"), nullable=True)
    state = Column(String(100), nullable=False)
    confidence = Column(Float, nullable=False, default=0.0)
    objects_detected = Column(JSON, nullable=True)
    measurements = Column(JSON, nullable=True)
    change_detected = Column(Boolean, nullable=False, default=False)
    severity = Column(String(20), nullable=True)
    explanation = Column(Text, nullable=True)
    raw_ai_output = Column(JSON, nullable=True)
    timestamp = now_utc()

    session = relationship("MonitoringSession", back_populates="observations")
    camera = relationship("CameraDevice", back_populates="observations")


class Event(Base):
    __tablename__ = "events"

    id = uuid_pk()
    camera_id = Column(UUID(as_uuid=True), ForeignKey("camera_devices.id", ondelete="SET NULL"), nullable=True, index=True)
    task_id = Column(UUID(as_uuid=True), ForeignKey("monitoring_tasks.id", ondelete="SET NULL"), nullable=True, index=True)
    session_id = Column(UUID(as_uuid=True), nullable=True)
    type = Column(Enum(EventType), nullable=False)
    confidence = Column(Float, nullable=True)
    description = Column(Text, nullable=False)
    evidence_frame_id = Column(UUID(as_uuid=True), ForeignKey("frames.id", ondelete="SET NULL"), nullable=True)
    metadata = Column(JSON, nullable=True)
    is_read = Column(Boolean, nullable=False, default=False)
    timestamp = now_utc()

    camera = relationship("CameraDevice", back_populates="events")
    task = relationship("MonitoringTask", back_populates="events")
    alerts = relationship("Alert", back_populates="event")


class Alert(Base):
    __tablename__ = "alerts"

    id = uuid_pk()
    event_id = Column(UUID(as_uuid=True), ForeignKey("events.id", ondelete="CASCADE"), nullable=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    severity = Column(Enum(AlertSeverity), nullable=False, default=AlertSeverity.INFO)
    title = Column(String(200), nullable=False)
    message = Column(Text, nullable=False)
    is_read = Column(Boolean, nullable=False, default=False)
    is_dismissed = Column(Boolean, nullable=False, default=False)
    metadata = Column(JSON, nullable=True)
    created_at = now_utc()
    read_at = Column(DateTime(timezone=True), nullable=True)

    event = relationship("Event", back_populates="alerts")
    user = relationship("User", back_populates="alerts")
    notifications = relationship("Notification", back_populates="alert")


class Frame(Base):
    __tablename__ = "frames"

    id = uuid_pk()
    camera_id = Column(UUID(as_uuid=True), ForeignKey("camera_devices.id", ondelete="CASCADE"), nullable=False, index=True)
    session_id = Column(UUID(as_uuid=True), ForeignKey("monitoring_sessions.id", ondelete="SET NULL"), nullable=True)
    storage_path = Column(String(500), nullable=True)
    file_size_bytes = Column(Integer, nullable=True)
    width = Column(Integer, nullable=True)
    height = Column(Integer, nullable=True)
    format = Column(String(10), nullable=True, default="jpeg")
    retention_policy = Column(Enum(FrameRetention), nullable=False, default=FrameRetention.STANDARD)
    is_evidence = Column(Boolean, nullable=False, default=False)
    expires_at = Column(DateTime(timezone=True), nullable=True)
    created_at = now_utc()

    camera = relationship("CameraDevice", back_populates="frames")


class Notification(Base):
    __tablename__ = "notifications"

    id = uuid_pk()
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    alert_id = Column(UUID(as_uuid=True), ForeignKey("alerts.id", ondelete="SET NULL"), nullable=True)
    provider = Column(String(30), nullable=False)  # push, email, in_app
    status = Column(Enum(NotificationStatus), nullable=False, default=NotificationStatus.PENDING)
    error_message = Column(Text, nullable=True)
    sent_at = Column(DateTime(timezone=True), nullable=True)
    created_at = now_utc()

    user = relationship("User", back_populates="notifications")
    alert = relationship("Alert", back_populates="notifications")


class Permission(Base):
    __tablename__ = "permissions"
    __table_args__ = (UniqueConstraint("user_id", "camera_id", "permission_type", name="uq_user_camera_perm"),)

    id = uuid_pk()
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    camera_id = Column(UUID(as_uuid=True), ForeignKey("camera_devices.id", ondelete="CASCADE"), nullable=False)
    permission_type = Column(String(50), nullable=False)  # view, control, configure, admin
    granted_at = now_utc()
    granted_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)

    user = relationship("User", back_populates="permissions", foreign_keys=[user_id])


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = uuid_pk()
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    action = Column(String(100), nullable=False)
    resource_type = Column(String(50), nullable=True)
    resource_id = Column(String(100), nullable=True)
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(String(500), nullable=True)
    metadata = Column(JSON, nullable=True)
    success = Column(Boolean, nullable=False, default=True)
    timestamp = now_utc()


class UserSettings(Base):
    __tablename__ = "user_settings"

    id = uuid_pk()
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False)
    notification_push = Column(Boolean, nullable=False, default=True)
    notification_email = Column(Boolean, nullable=False, default=False)
    notification_in_app = Column(Boolean, nullable=False, default=True)
    privacy_mode = Column(Boolean, nullable=False, default=False)
    frame_retention = Column(Enum(FrameRetention), nullable=False, default=FrameRetention.STANDARD)
    theme = Column(String(20), nullable=False, default="system")
    analysis_interval = Column(Integer, nullable=False, default=2)
    confidence_threshold = Column(Float, nullable=False, default=0.75)
    created_at = now_utc()
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
