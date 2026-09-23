"""
Frame storage service for saving, retrieving, and purging frames.
Supports local filesystem, S3-compatible object storage, and Supabase storage.
"""
import os
import aiofiles
import structlog
from typing import Optional
from pathlib import Path
from app.core.config import settings

log = structlog.get_logger(__name__)

class StorageService:
    def __init__(self):
        self.provider = settings.STORAGE_PROVIDER
        self.bucket = settings.STORAGE_BUCKET
        self.local_dir = Path("/tmp/smart_spectator_frames")
        self.local_dir.mkdir(parents=True, exist_ok=True)

    async def save_frame(
        self,
        frame_id: str,
        camera_id: str,
        raw_bytes: bytes,
        extension: str = "jpg",
    ) -> str:
        """
        Persist frame bytes and return the stored URI or key.
        """
        filename = f"{camera_id}_{frame_id}.{extension}"
        
        if self.provider == "s3" and settings.S3_BUCKET:
            try:
                import boto3
                s3 = boto3.client(
                    "s3",
                    endpoint_url=settings.S3_ENDPOINT_URL or None,
                    aws_access_key_id=settings.S3_ACCESS_KEY,
                    aws_secret_access_key=settings.S3_SECRET_KEY,
                )
                key = f"frames/{camera_id}/{filename}"
                s3.put_object(
                    Bucket=settings.S3_BUCKET,
                    Key=key,
                    Body=raw_bytes,
                    ContentType=f"image/{extension}",
                )
                return f"s3://{settings.S3_BUCKET}/{key}"
            except Exception as e:
                log.error("Failed to upload frame to S3, falling back to local", error=str(e))

        # Local filesystem fallback
        file_path = self.local_dir / filename
        async with aiofiles.open(file_path, "wb") as f:
            await f.write(raw_bytes)
        return str(file_path)

    async def get_frame(self, file_path_or_uri: str) -> Optional[bytes]:
        """Retrieve stored frame bytes."""
        if file_path_or_uri.startswith("s3://"):
            try:
                import boto3
                parts = file_path_or_uri[5:].split("/", 1)
                bucket, key = parts[0], parts[1]
                s3 = boto3.client(
                    "s3",
                    endpoint_url=settings.S3_ENDPOINT_URL or None,
                    aws_access_key_id=settings.S3_ACCESS_KEY,
                    aws_secret_access_key=settings.S3_SECRET_KEY,
                )
                response = s3.get_object(Bucket=bucket, Key=key)
                return response["Body"].read()
            except Exception as e:
                log.error("Failed to read frame from S3", error=str(e))
                return None
        else:
            p = Path(file_path_or_uri)
            if not p.exists():
                return None
            async with aiofiles.open(p, "rb") as f:
                return await f.read()

    async def delete_frame(self, file_path_or_uri: str) -> bool:
        """Delete stored frame."""
        try:
            if file_path_or_uri.startswith("s3://"):
                import boto3
                parts = file_path_or_uri[5:].split("/", 1)
                bucket, key = parts[0], parts[1]
                s3 = boto3.client("s3")
                s3.delete_object(Bucket=bucket, Key=key)
                return True
            else:
                p = Path(file_path_or_uri)
                if p.exists():
                    p.unlink()
                return True
        except Exception as e:
            log.warn("Failed to delete frame", path=file_path_or_uri, error=str(e))
            return False

storage_service = StorageService()
