"""
Smart Spectator - Audit Repository
Encapsulates all database operations for system and security audit logs.
"""

from datetime import datetime, timezone
import json
from typing import List, Dict, Any, Optional
import uuid

from services.hub_backend.database.connection import db_session


class AuditRepository:
    def log(
        self,
        action: str,
        actor: str = "system",
        resource: str = "general",
        details: Optional[Dict[str, Any]] = None,
        ip_address: Optional[str] = None,
    ) -> str:
        log_id = f"audit_{uuid.uuid4().hex}"
        now_str = datetime.now(timezone.utc).isoformat()
        metadata_json = json.dumps(details or {})

        with db_session() as conn:
            conn.execute(
                """
                INSERT INTO audit_logs (log_id, actor, action, resource, metadata_json, timestamp)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (log_id, actor, action, resource, metadata_json, now_str),
            )
        return log_id

    def list_logs(self, limit: int = 50, offset: int = 0) -> List[Dict[str, Any]]:
        with db_session() as conn:
            cursor = conn.execute(
                "SELECT * FROM audit_logs ORDER BY timestamp DESC LIMIT ? OFFSET ?",
                (limit, offset),
            )
            return cursor.fetchall()


audit_repository = AuditRepository()
