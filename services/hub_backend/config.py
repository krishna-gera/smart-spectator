"""
Smart Spectator Desktop Hub - Centralized Configuration Module
Conforms to Sections 14, 15, 16, 21, 23, 72 of Phase 6/7 Specification.
"""

import os
from pathlib import Path
from typing import List, Optional
from pydantic import BaseModel, Field


class Settings(BaseModel):
    # Environment & Product Info
    ENVIRONMENT: str = os.getenv("SMART_SPECTATOR_ENV", "development").lower()
    APP_VERSION: str = "2.0.0"
    HUB_VERSION: str = "2.0.0"
    SCHEMA_VERSION: str = "5"
    CLIENT_VERSION: str = "2.0.0"
    DETECTOR_VERSION: str = "1.0.0"
    SPECTATORNET_VERSION: str = "1.0.0"

    # Networking
    HOST: str = os.getenv("HUB_HOST", "0.0.0.0")
    PORT: int = int(os.getenv("HUB_PORT", "8000"))
    STREAM_PORT: int = int(os.getenv("STREAM_PORT", "8554"))
    
    # Discovery
    MDNS_SERVICE_TYPE: str = "_smartspectator._tcp.local."
    MDNS_SERVICE_NAME: str = os.getenv("MDNS_NAME", "SmartSpectatorHub")
    
    # Paths & Directories
    BASE_DIR: Path = Path(__file__).resolve().parent.parent.parent
    DATABASE_PATH: Path = Path(os.getenv("DATABASE_PATH", "smart_spectator.db"))
    RECORDINGS_DIR: Path = Path(os.getenv("RECORDINGS_DIR", "recordings"))
    SNAPSHOTS_DIR: Path = Path(os.getenv("SNAPSHOTS_DIR", "snapshots"))
    BACKUP_DIR: Path = Path(os.getenv("BACKUP_DIR", "backups"))
    LOGS_DIR: Path = Path(os.getenv("LOGS_DIR", "logs"))
    CLIENT_DIR: Path = Path(__file__).resolve().parent.parent.parent / "apps" / "client"
    
    # Security & Auth
    PAIRING_PIN_LENGTH: int = 6
    PAIRING_PIN_TTL_SECONDS: int = 300  # 5 minutes
    AUTH_TOKEN_TTL_DAYS: int = 30
    HMAC_SECRET: str = os.getenv("HUB_HMAC_SECRET", "smart-spectator-local-secret-key-change-in-prod")
    MAX_PIN_ATTEMPTS: int = int(os.getenv("MAX_PIN_ATTEMPTS", "5"))
    PIN_LOCKOUT_SECONDS: int = int(os.getenv("PIN_LOCKOUT_SECONDS", "60"))
    MAX_REQUEST_BODY_BYTES: int = 10 * 1024 * 1024  # 10 MB safety cap
    
    # Video & Pipeline Defaults
    TARGET_FPS: int = 30
    TARGET_WIDTH: int = 1280
    TARGET_HEIGHT: int = 720
    MAX_CONCURRENT_CAMERAS: int = 4
    
    DEV_MODE: bool = os.getenv("DEV_MODE", "true").lower() in ("true", "1", "yes")

    # Event Engine & Automation Defaults
    EVENT_DEFAULT_MIN_CONFIDENCE: float = float(os.getenv("EVENT_MIN_CONFIDENCE", "0.70"))
    EVENT_DEFAULT_CONFIRM_THRESHOLD: float = float(os.getenv("EVENT_CONFIRM_THRESHOLD", "0.80"))
    EVENT_DEFAULT_CONSECUTIVE: int = int(os.getenv("EVENT_CONSECUTIVE", "2"))
    EVENT_DEFAULT_COOLDOWN_SECONDS: int = int(os.getenv("EVENT_COOLDOWN_SECONDS", "15"))
    EVENT_RESOLUTION_TIMEOUT_SECONDS: float = float(os.getenv("EVENT_RESOLUTION_TIMEOUT", "3.0"))
    LOITERING_DEFAULT_DWELL_SECONDS: float = float(os.getenv("LOITERING_DWELL_SECONDS", "30.0"))

    # Recording Engine & Storage Management
    RECORDING_PRE_ROLL_SECONDS: float = float(os.getenv("RECORDING_PRE_ROLL", "10.0"))
    RECORDING_POST_ROLL_SECONDS: float = float(os.getenv("RECORDING_POST_ROLL", "5.0"))
    RECORDING_MAX_STORAGE_GB: float = float(os.getenv("RECORDING_MAX_STORAGE_GB", "10.0"))
    RECORDING_RETENTION_DAYS: int = int(os.getenv("RECORDING_RETENTION_DAYS", "14"))
    MIN_FREE_DISK_MB: float = float(os.getenv("MIN_FREE_DISK_MB", "500.0"))  # Degraded recording mode if < 500MB

    # Logging & Rotation
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    LOG_MAX_BYTES: int = int(os.getenv("LOG_MAX_BYTES", str(5 * 1024 * 1024)))  # 5 MB
    LOG_BACKUP_COUNT: int = int(os.getenv("LOG_BACKUP_COUNT", "5"))

    # AI Models & Hardware Acceleration (Snapdragon QNN / DirectML / CPU)
    AI_PROVIDER_PRIORITY: List[str] = Field(default_factory=lambda: ["qnn", "directml", "coreml", "cpu"])
    DETECTOR_MODEL_PATH: Path = Path("ai/models/yolov8n.onnx")
    SPECTATORNET_MODEL_PATH: Path = Path("ai/models/spectatornet.onnx")
    SPECTATORNET_INT8_MODEL_PATH: Path = Path("ai/models/spectatornet_int8.onnx")
    SPECTATORNET_NORMALIZATION_PATH: Path = Path("ai/datasets/smart_spectator/statistics/normalization.json")
    VERIFY_MODEL_CHECKSUMS: bool = os.getenv("VERIFY_MODEL_CHECKSUMS", "false").lower() in ("true", "1", "yes")

    # Optional Demo Mode
    DEMO_MODE: bool = os.getenv("SMART_SPECTATOR_DEMO_MODE", "false").lower() in ("true", "1", "yes")

    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT == "production"

    @property
    def is_testing(self) -> bool:
        return self.ENVIRONMENT == "test"


settings = Settings()

# Ensure directories exist
settings.RECORDINGS_DIR.mkdir(parents=True, exist_ok=True)
settings.SNAPSHOTS_DIR.mkdir(parents=True, exist_ok=True)
settings.BACKUP_DIR.mkdir(parents=True, exist_ok=True)
settings.LOGS_DIR.mkdir(parents=True, exist_ok=True)
settings.CLIENT_DIR.mkdir(parents=True, exist_ok=True)
