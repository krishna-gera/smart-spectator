"""
Application configuration — loaded from environment variables.
Never hardcode secrets here.
"""
from functools import lru_cache
from typing import List

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Application ─────────────────────────────────────────────
    APP_ENV: str = "development"
    APP_SECRET_KEY: str = "change-me-in-production"

    # ── Database ─────────────────────────────────────────────────
    DATABASE_URL: str = "postgresql+asyncpg://postgres:password@localhost:5432/smart_spectator"
    DATABASE_POOL_SIZE: int = 10
    DATABASE_MAX_OVERFLOW: int = 20

    # ── Supabase ─────────────────────────────────────────────────
    SUPABASE_URL: str = ""
    SUPABASE_ANON_KEY: str = ""
    SUPABASE_SERVICE_ROLE_KEY: str = ""
    SUPABASE_JWT_SECRET: str = ""

    # ── JWT ──────────────────────────────────────────────────────
    JWT_SECRET: str = "change-me-in-production"
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    JWT_REFRESH_TOKEN_EXPIRE_DAYS: int = 30

    # ── Redis / Celery ───────────────────────────────────────────
    REDIS_URL: str = "redis://localhost:6379/0"
    CELERY_BROKER_URL: str = "redis://localhost:6379/1"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/2"

    # ── Storage ──────────────────────────────────────────────────
    STORAGE_PROVIDER: str = "supabase"
    STORAGE_BUCKET: str = "smart-spectator-frames"
    STORAGE_PUBLIC_URL: str = ""
    S3_ENDPOINT_URL: str = ""
    S3_ACCESS_KEY: str = ""
    S3_SECRET_KEY: str = ""
    S3_BUCKET: str = ""

    # ── AI / Vision ──────────────────────────────────────────────
    VISION_PROVIDER: str = "yolo"
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_VLM_MODEL: str = "llava:7b"
    YOLO_MODEL_SIZE: str = "yolov8n"
    YOLO_MODEL_PATH: str = ""
    DEVICE: str = "auto"
    USE_EDGE_DETECTION: bool = True
    ANALYSIS_INTERVAL_SECONDS: int = 2
    CONFIDENCE_THRESHOLD: float = 0.75
    TEMPORAL_CONFIRMATION_FRAMES: int = 3
    FRAME_DIFF_THRESHOLD: float = 0.05

    # ── Push Notifications ───────────────────────────────────────
    FCM_SERVER_KEY: str = ""
    FCM_PROJECT_ID: str = ""
    APNS_KEY_ID: str = ""
    APNS_TEAM_ID: str = ""
    APNS_PRIVATE_KEY_PATH: str = ""

    # ── Email ────────────────────────────────────────────────────
    SMTP_HOST: str = "smtp.gmail.com"
    SMTP_PORT: int = 587
    SMTP_USERNAME: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM_EMAIL: str = "noreply@smart-spectator.app"

    # ── CORS ─────────────────────────────────────────────────────
    CORS_ORIGINS_RAW: str = "http://localhost:3000,http://localhost:3001"

    @property
    def CORS_ORIGINS(self) -> List[str]:
        return [origin.strip() for origin in self.CORS_ORIGINS_RAW.split(",")]

    # ── Rate Limiting ────────────────────────────────────────────
    RATE_LIMIT_PER_MINUTE: int = 60
    FRAME_UPLOAD_RATE_LIMIT_PER_MINUTE: int = 120

    # ── Frame Retention ──────────────────────────────────────────
    DEFAULT_FRAME_RETENTION: str = "standard"
    FRAME_SHORT_RETENTION_HOURS: int = 24
    FRAME_STANDARD_RETENTION_DAYS: int = 7

    # ── Logging ──────────────────────────────────────────────────
    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: str = "json"

    # ── Feature Flags ────────────────────────────────────────────
    DEMO_MODE: bool = False
    PRIVACY_MODE_DEFAULT: bool = False
    ENABLE_PUSH_NOTIFICATIONS: bool = True
    ENABLE_EMAIL_NOTIFICATIONS: bool = False


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
