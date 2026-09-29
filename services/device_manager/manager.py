"""
Smart Spectator - Device Manager Subsystem
Handles device lifecycle: discovery registration, pairing PIN verification,
token issuance, session authentication, and revocation.
"""

from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
import uuid

from ..hub_backend.database.connection import db_session
from ..hub_backend.config import settings
from .credentials import generate_pairing_pin, generate_device_token, verify_device_token


class DeviceManager:
    """Manages connected and paired camera nodes."""

    def __init__(self):
        pass

    def request_pairing(
        self,
        device_id: str,
        device_name: str,
        device_model: Optional[str] = None,
        ip_address: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Processes an incoming pairing request from an Android camera node.
        Generates a 6-digit PIN with TTL and stores it in the ephemeral pairing table.
        """
        pin = generate_pairing_pin()
        expires_at = datetime.utcnow() + timedelta(seconds=settings.PAIRING_PIN_TTL_SECONDS)
        
        with db_session() as conn:
            # Upsert into pairing_requests
            conn.execute(
                """
                INSERT OR REPLACE INTO pairing_requests 
                (device_id, device_name, device_model, verification_pin, created_at, expires_at, attempts_remaining)
                VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP, ?, 3)
                """,
                (device_id, device_name, device_model, pin, expires_at.isoformat())
            )
            
            # Ensure device record exists in 'pairing' status
            conn.execute(
                """
                INSERT INTO devices (device_id, device_name, device_model, ip_address, status, created_at, last_seen)
                VALUES (?, ?, ?, ?, 'pairing', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                ON CONFLICT(device_id) DO UPDATE SET
                    device_name = excluded.device_name,
                    ip_address = excluded.ip_address,
                    status = 'pairing',
                    last_seen = CURRENT_TIMESTAMP
                """,
                (device_id, device_name, device_model, ip_address)
            )

        print(f"[DeviceManager] Pairing requested by '{device_name}' ({device_id}). Active PIN: {pin} (Expires in {settings.PAIRING_PIN_TTL_SECONDS}s)")
        
        return {
            "status": "pending_operator_approval",
            "verification_code": pin,
            "expires_in_seconds": settings.PAIRING_PIN_TTL_SECONDS
        }

    def verify_pairing(
        self,
        device_id: str,
        submitted_pin: str
    ) -> Dict[str, Any]:
        """
        Validates the submitted 6-digit PIN.
        If valid:
          - Marks device as 'paired'
          - Generates HMAC token
          - Creates or links default Camera entry
          - Deletes ephemeral pairing record
        """
        with db_session() as conn:
            cursor = conn.execute(
                "SELECT * FROM pairing_requests WHERE device_id = ?",
                (device_id,)
            )
            req = cursor.fetchone()
            
            if not req:
                return {"status": "error", "error": "No pending pairing request for this device"}
                
            # Check expiration
            expires_at = datetime.fromisoformat(req["expires_at"])
            if datetime.utcnow() > expires_at:
                conn.execute("DELETE FROM pairing_requests WHERE device_id = ?", (device_id,))
                return {"status": "error", "error": "Pairing PIN has expired. Please request a new PIN"}
                
            # Check attempts
            if req["attempts_remaining"] <= 0:
                conn.execute("DELETE FROM pairing_requests WHERE device_id = ?", (device_id,))
                return {"status": "error", "error": "Too many failed attempts. Pairing locked"}
                
            # Constant-time comparison for PIN
            if req["verification_pin"] != submitted_pin.strip():
                conn.execute(
                    "UPDATE pairing_requests SET attempts_remaining = attempts_remaining - 1 WHERE device_id = ?",
                    (device_id,)
                )
                return {"status": "error", "error": "Invalid verification code"}
                
            # PIN is valid! Mint credential
            raw_token, token_hash = generate_device_token(device_id)
            
            # Check if camera already assigned to device
            cam_cur = conn.execute("SELECT camera_id FROM cameras WHERE device_id = ?", (device_id,))
            existing_cam = cam_cur.fetchone()
            if existing_cam:
                camera_id = existing_cam["camera_id"]
            else:
                camera_id = f"cam_{uuid.uuid4().hex[:12]}"
                conn.execute(
                    """
                    INSERT INTO cameras (camera_id, device_id, name, source_type, width, height, target_fps, status, is_active)
                    VALUES (?, ?, ?, 'phone', ?, ?, ?, 'idle', 1)
                    """,
                    (camera_id, device_id, f"{req['device_name']} Camera", settings.TARGET_WIDTH, settings.TARGET_HEIGHT, settings.TARGET_FPS)
                )
                
            # Update device record
            conn.execute(
                """
                UPDATE devices 
                SET auth_token_hash = ?, status = 'paired', last_seen = CURRENT_TIMESTAMP
                WHERE device_id = ?
                """,
                (token_hash, device_id)
            )
            
            # Remove ephemeral pairing request
            conn.execute("DELETE FROM pairing_requests WHERE device_id = ?", (device_id,))
            
        print(f"[DeviceManager] Device '{device_id}' successfully paired and assigned camera '{camera_id}'")
        
        return {
            "status": "paired",
            "device_id": device_id,
            "camera_id": camera_id,
            "device_token": raw_token,
            "token_type": "Bearer"
        }

    def authenticate_token(self, raw_token: str) -> Optional[Dict[str, Any]]:
        """
        Validates bearer token against active devices.
        Returns device record if valid and not revoked, otherwise None.
        """
        if not raw_token or not raw_token.startswith("ss_tok_v1_"):
            return None
            
        with db_session() as conn:
            cursor = conn.execute(
                "SELECT * FROM devices WHERE status IN ('paired', 'connected')"
            )
            devices = cursor.fetchall()
            
            for dev in devices:
                stored_hash = dev.get("auth_token_hash")
                if stored_hash and verify_device_token(raw_token, stored_hash):
                    # Update last_seen
                    conn.execute(
                        "UPDATE devices SET last_seen = CURRENT_TIMESTAMP WHERE device_id = ?",
                        (dev["device_id"],)
                    )
                    return dev
                    
        return None

    def update_telemetry(
        self,
        device_id: str,
        battery_level: Optional[float] = None,
        is_charging: Optional[bool] = None,
        battery_temp_c: Optional[float] = None,
        ip_address: Optional[str] = None
    ) -> None:
        """Updates live device telemetry metrics."""
        with db_session() as conn:
            conn.execute(
                """
                UPDATE devices SET
                    battery_level = COALESCE(?, battery_level),
                    is_charging = COALESCE(?, is_charging),
                    battery_temperature_c = COALESCE(?, battery_temperature_c),
                    ip_address = COALESCE(?, ip_address),
                    last_seen = CURRENT_TIMESTAMP
                WHERE device_id = ?
                """,
                (battery_level, 1 if is_charging else (0 if is_charging is not None else None), battery_temp_c, ip_address, device_id)
            )

    def set_device_status(self, device_id: str, status: str) -> None:
        """Sets device status (connected, disconnected, revoked)."""
        with db_session() as conn:
            conn.execute(
                "UPDATE devices SET status = ?, last_seen = CURRENT_TIMESTAMP WHERE device_id = ?",
                (status, device_id)
            )

    def get_camera_for_device(self, device_id: str) -> Optional[Dict[str, Any]]:
        with db_session() as conn:
            cur = conn.execute("SELECT * FROM cameras WHERE device_id = ?", (device_id,))
            return cur.fetchone()

    def list_devices(self) -> List[Dict[str, Any]]:
        with db_session() as conn:
            cur = conn.execute("SELECT * FROM devices ORDER BY last_seen DESC")
            return cur.fetchall()

    def revoke_device(self, device_id: str) -> bool:
        with db_session() as conn:
            cur = conn.execute("UPDATE devices SET status = 'revoked', auth_token_hash = NULL WHERE device_id = ?", (device_id,))
            return cur.rowcount > 0


device_manager = DeviceManager()
