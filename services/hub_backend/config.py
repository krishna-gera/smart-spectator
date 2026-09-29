"""
Smart Spectator Desktop Hub - Configuration Module
"""

import os
from pathlib import Path
from pydantic import BaseModel


class Settings(BaseModel):
    # Networking
    HOST: str = os.getenv("HUB_HOST", "0.0.0.0")
    PORT: int = int(os.getenv("HUB_PORT", "8000"))
    STREAM_PORT: int = int(os.getenv("STREAM_PORT", "8554"))
    
    # Discovery
    MDNS_SERVICE_TYPE: str = "_smartspectator._tcp.local."
    MDNS_SERVICE_NAME: str = os.getenv("MDNS_NAME", "SmartSpectatorHub")
    
    # Storage & Database
    BASE_DIR: Path = Path(__file__).resolve().parent.parent.parent
    DATABASE_PATH: Path = Path(os.getenv("DATABASE_PATH", "smart_spectator.db"))
    RECORDINGS_DIR: Path = Path(os.getenv("RECORDINGS_DIR", "recordings"))
    SNAPSHOTS_DIR: Path = Path(os.getenv("SNAPSHOTS_DIR", "snapshots"))
    
    # Security & Auth
    PAIRING_PIN_LENGTH: int = 6
    PAIRING_PIN_TTL_SECONDS: int = 300  # 5 minutes
    AUTH_TOKEN_TTL_DAYS: int = 30
    HMAC_SECRET: str = os.getenv("HUB_HMAC_SECRET", "smart-spectator-local-secret-key-change-in-prod")
    
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

    # Recording Engine
    RECORDING_PRE_ROLL_SECONDS: float = float(os.getenv("RECORDING_PRE_ROLL", "10.0"))
    RECORDING_POST_ROLL_SECONDS: float = float(os.getenv("RECORDING_POST_ROLL", "5.0"))
    RECORDING_MAX_STORAGE_GB: float = float(os.getenv("RECORDING_MAX_STORAGE_GB", "10.0"))
    RECORDING_RETENTION_DAYS: int = int(os.getenv("RECORDING_RETENTION_DAYS", "14"))

    # Client App
    CLIENT_DIR: Path = Path(__file__).resolve().parent.parent.parent / "apps" / "client"


settings = Settings()

# Ensure directories exist
settings.RECORDINGS_DIR.mkdir(parents=True, exist_ok=True)
settings.SNAPSHOTS_DIR.mkdir(parents=True, exist_ok=True)
settings.CLIENT_DIR.mkdir(parents=True, exist_ok=True)
