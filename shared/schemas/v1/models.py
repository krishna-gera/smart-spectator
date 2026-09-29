"""
Smart Spectator - Versioned Data Contracts (Schema v1)
Defines strongly typed, decoupled contracts for Hub, Camera Nodes, AI Pipeline, and Clients.
"""

from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field


class DeviceStatus(str, Enum):
    DISCOVERED = "discovered"
    PAIRING = "pairing"
    PAIRED = "paired"
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    REVOKED = "revoked"


class CameraSourceType(str, Enum):
    PHONE = "phone"
    RTSP = "rtsp"
    ONVIF = "onvif"
    IP = "ip"
    USB = "usb"


class StreamStatus(str, Enum):
    IDLE = "idle"
    STARTING = "starting"
    STREAMING = "streaming"
    DEGRADED = "degraded"
    STOPPED = "stopped"
    ERROR = "error"


class EventSeverity(str, Enum):
    INFO = "info"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class HardwareBackend(str, Enum):
    NPU_QNN = "npu_qnn"          # Snapdragon Hexagon NPU via Qualcomm AI Engine Direct
    GPU_DIRECTML = "gpu_directml" # Windows DirectML
    GPU_COREML = "gpu_coreml"     # macOS Apple Silicon CoreML
    GPU_CUDA = "gpu_cuda"         # NVIDIA fallback
    CPU = "cpu"                   # Universal fallback


# ---------------------------------------------------------------------------
# Device & Camera Schemas
# ---------------------------------------------------------------------------

class Device(BaseModel):
    device_id: str = Field(..., description="Unique hardware or generated UUID")
    device_name: str = Field(..., description="Human-readable device label")
    device_type: str = Field(default="android_phone", description="Type of device (e.g. android_phone)")
    ip_address: Optional[str] = Field(None, description="Current local IPv4/IPv6 address")
    mac_address: Optional[str] = Field(None, description="MAC address if discoverable")
    auth_token_hash: Optional[str] = Field(None, description="Hashed session credential")
    status: DeviceStatus = Field(default=DeviceStatus.DISCOVERED)
    battery_level: Optional[float] = Field(None, description="Battery percentage (0.0 to 100.0)")
    is_charging: Optional[bool] = Field(None, description="True if connected to power")
    battery_temperature_c: Optional[float] = Field(None, description="Thermal sensor reading in Celsius")
    app_version: Optional[str] = Field(None, description="Client app build version")
    last_seen: datetime = Field(default_factory=datetime.utcnow)
    created_at: datetime = Field(default_factory=datetime.utcnow)


class Camera(BaseModel):
    camera_id: str = Field(..., description="Unique camera UUID")
    device_id: Optional[str] = Field(None, description="Parent device UUID if attached to a phone/station")
    name: str = Field(..., description="Camera label (e.g. Front Camera, Living Room)")
    source_type: CameraSourceType = Field(default=CameraSourceType.PHONE)
    stream_url: Optional[str] = Field(None, description="RTSP/SRT/WS endpoint URL")
    width: int = Field(default=1280, description="Native video width")
    height: int = Field(default=720, description="Native video height")
    target_fps: int = Field(default=30, description="Target frame rate")
    is_active: bool = Field(default=True)
    status: StreamStatus = Field(default=StreamStatus.IDLE)
    lens_facing: Optional[str] = Field("back", description="back, front, external")
    created_at: datetime = Field(default_factory=datetime.utcnow)


# ---------------------------------------------------------------------------
# Video & Frame Processing Schemas
# ---------------------------------------------------------------------------

class FrameMetadata(BaseModel):
    camera_id: str
    frame_index: int
    pts: int = Field(..., description="Presentation timestamp in microseconds")
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    width: int
    height: int
    channels: int = 3
    stride: Optional[int] = None
    codec: str = "raw_bgr"
    is_sampled_for_ai: bool = False


# ---------------------------------------------------------------------------
# AI Detection & Tracking Schemas
# ---------------------------------------------------------------------------

class Detection(BaseModel):
    detection_id: str
    class_id: int
    class_name: str
    confidence: float
    bbox_xyxy: List[float] = Field(..., description="[x_min, y_min, x_max, y_max] normalized (0.0-1.0)")
    attributes: Dict[str, Any] = Field(default_factory=dict)


class TrackedObject(BaseModel):
    track_id: int
    camera_id: str
    class_name: str
    current_bbox: List[float]
    velocity_vector: Optional[List[float]] = Field(None, description="[vx, vy] normalized px/sec")
    first_seen_timestamp: datetime
    last_seen_timestamp: datetime
    trajectory: List[List[float]] = Field(default_factory=list, description="Historical centroid positions")
    confidence: float
    is_active: bool = True


# ---------------------------------------------------------------------------
# Observations & Events Schemas
# ---------------------------------------------------------------------------

class Observation(BaseModel):
    observation_id: str
    camera_id: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    frame_index: int
    detections: List[Detection] = Field(default_factory=list)
    tracked_objects: List[TrackedObject] = Field(default_factory=list)
    scene_state: Dict[str, Any] = Field(default_factory=dict, description="Aggregated spatial and temporal attributes")


class Event(BaseModel):
    event_id: str
    camera_id: str
    task_id: Optional[str] = Field(None, description="Associated MonitoringTask if triggered by policy")
    event_type: str = Field(..., description="e.g. OBJECT_REMOVED, PERSON_ENTERED, CAMERA_BLOCKED")
    severity: EventSeverity = Field(default=EventSeverity.INFO)
    confidence: float = Field(..., description="Event classification score (0.0 to 1.0)")
    summary: str = Field(..., description="Human-readable event description")
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    trigger_observation_id: Optional[str] = None
    involved_track_ids: List[int] = Field(default_factory=list)
    recording_id: Optional[str] = Field(None, description="Associated clip ID if recorded")
    metadata: Dict[str, Any] = Field(default_factory=dict)


class EventPrediction(BaseModel):
    """
    Phase 3/4 Data Contract: Emitted by SpectatorNet temporal inference engine.
    Consumable by Phase 4 Event Engine to evaluate monitoring policies.
    """
    schema_version: str = "1.0"
    camera_id: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    event_type: str = Field(..., description="e.g. OBJECT_REMOVED, PERSON_ENTERED, NORMAL_BACKGROUND")
    confidence: float = Field(..., description="Classification probability (0.0 to 1.0)")
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    affected_tracks: List[int] = Field(default_factory=list)
    class_probabilities: Dict[str, float] = Field(default_factory=dict)
    sequence_length: int = 30
    metadata: Dict[str, Any] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Recording & Storage Schemas
# ---------------------------------------------------------------------------

class Recording(BaseModel):
    recording_id: str
    camera_id: str
    event_id: Optional[str] = None
    file_path: str = Field(..., description="Local path to .mp4 or .mkv clip")
    thumbnail_path: Optional[str] = None
    start_time: datetime
    end_time: datetime
    duration_seconds: float
    file_size_bytes: int
    codec: str = "h264"
    width: int
    height: int
    fps: float
    metadata: Dict[str, Any] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Monitoring Task Schemas
# ---------------------------------------------------------------------------

class MonitoringTask(BaseModel):
    task_id: str
    camera_id: str
    name: str = Field(..., description="Human task label, e.g. 'Watch Coffee Mug'")
    target_class: str = Field(..., description="Object class of interest, e.g. bottle, person")
    expected_state: str = Field(..., description="e.g. PRESENT, STATIONARY, ABSENT")
    trigger_condition: str = Field(..., description="e.g. DISAPPEARED_FOR_10S, MOVED_BEYOND_ZONE, ENTERED_ZONE")
    event_type: str = Field(..., description="Event code emitted when triggered")
    roi_polygon: Optional[List[List[float]]] = Field(None, description="Normalized coordinates of monitoring zone")
    notification_policy: Dict[str, Any] = Field(default_factory=dict, description="Sound, UI banner, webhook")
    is_active: bool = True
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


# ---------------------------------------------------------------------------
# AI Model & Hardware Performance Schemas
# ---------------------------------------------------------------------------

class ModelMetadata(BaseModel):
    model_id: str
    name: str
    version: str
    task_type: str = Field(..., description="detection, tracking, temporal_event, vlm")
    format: str = Field(..., description="onnx, qnn_dlc, tflite, pytorch")
    input_resolution: List[int] = Field(..., description="[Batch, Channels, Height, Width]")
    mean_inference_latency_ms: float
    current_backend: HardwareBackend
    supports_npu: bool = False
    weights_path: str
    checksum_sha256: str


class SystemHealth(BaseModel):
    hub_timestamp: datetime = Field(default_factory=datetime.utcnow)
    cpu_percent: float
    memory_percent: float
    memory_used_mb: float
    memory_total_mb: float
    storage_free_gb: float
    storage_total_gb: float
    npu_available: bool
    npu_backend_name: Optional[str] = None
    npu_utilization_percent: Optional[float] = None
    connected_cameras_count: int
    active_streams_count: int
    current_total_inference_fps: float
    dropped_frames_last_minute: int
