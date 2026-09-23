"""
Notification service for dispatching alerts via WebSockets, Push (FCM/APNs), and webhooks.
"""
import structlog
from typing import Dict, Any, Optional
from app.core.config import settings

log = structlog.get_logger(__name__)

class NotificationService:
    def __init__(self):
        self.enable_push = settings.ENABLE_PUSH_NOTIFICATIONS

    async def broadcast_alert(
        self,
        user_id: str,
        camera_id: str,
        title: str,
        message: str,
        severity: str = "INFO",
        metadata: Optional[Dict[str, Any]] = None,
    ):
        """
        Dispatches an alert to active WebSocket connections and mobile push notification services.
        """
        payload = {
            "type": "alert",
            "title": title,
            "message": message,
            "severity": severity,
            "camera_id": camera_id,
            "metadata": metadata or {},
        }

        # 1. Real-time WebSocket dispatch
        try:
            from app.api.websocket import manager
            # Broadcast to specific camera channel
            await manager.broadcast_to_camera(camera_id, payload)
        except Exception as e:
            log.warn("WebSocket alert broadcast failed", error=str(e))

        # 2. Push notification dispatch (FCM)
        if self.enable_push and settings.FCM_SERVER_KEY:
            try:
                import httpx
                headers = {
                    "Authorization": f"key={settings.FCM_SERVER_KEY}",
                    "Content-Type": "application/json",
                }
                body = {
                    "to": f"/topics/user_{user_id}",
                    "notification": {
                        "title": title,
                        "body": message,
                        "sound": "default",
                    },
                    "data": {
                        "camera_id": camera_id,
                        "severity": severity,
                        **(metadata or {}),
                    },
                }
                async with httpx.AsyncClient() as client:
                    resp = await client.post("https://fcm.googleapis.com/fcm/send", json=body, headers=headers, timeout=5.0)
                    log.info("FCM push notification sent", status_code=resp.status_code)
            except Exception as e:
                log.error("FCM push notification failed", error=str(e))

notification_service = NotificationService()
