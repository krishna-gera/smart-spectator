"""
Smart Spectator - Rule Repository
Encapsulates all database operations for user-defined event and alert rules.
"""

from typing import List, Dict, Any, Optional
from services.hub_backend.database.connection import db_session


class RuleRepository:
    def list_rules(self) -> List[Dict[str, Any]]:
        with db_session() as conn:
            cursor = conn.execute("SELECT * FROM rules ORDER BY created_at ASC")
            return cursor.fetchall()

    def get_by_id(self, rule_id: str) -> Optional[Dict[str, Any]]:
        with db_session() as conn:
            cursor = conn.execute("SELECT * FROM rules WHERE rule_id = ?", (rule_id,))
            return cursor.fetchone()

    def create(
        self,
        rule_id: str,
        name: str,
        event_type: str,
        camera_id: Optional[str],
        zone_id: Optional[str],
        conditions_json: str,
        actions_json: str,
        priority: str,
        cooldown_seconds: int,
        is_active: bool = True,
    ) -> None:
        with db_session() as conn:
            conn.execute(
                """
                INSERT INTO rules (
                    rule_id, name, event_type, camera_id, zone_id, conditions_json,
                    actions_json, priority, cooldown_seconds, is_active
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    rule_id, name, event_type, camera_id, zone_id, conditions_json,
                    actions_json, priority, cooldown_seconds, 1 if is_active else 0,
                ),
            )

    def update(
        self,
        rule_id: str,
        name: str,
        event_type: str,
        camera_id: Optional[str],
        zone_id: Optional[str],
        conditions_json: str,
        actions_json: str,
        priority: str,
        cooldown_seconds: int,
        is_active: bool,
    ) -> bool:
        with db_session() as conn:
            cur = conn.execute(
                """
                UPDATE rules SET
                    name = ?, event_type = ?, camera_id = ?, zone_id = ?,
                    conditions_json = ?, actions_json = ?, priority = ?,
                    cooldown_seconds = ?, is_active = ?, updated_at = CURRENT_TIMESTAMP
                WHERE rule_id = ?
                """,
                (
                    name, event_type, camera_id, zone_id, conditions_json,
                    actions_json, priority, cooldown_seconds, 1 if is_active else 0, rule_id,
                ),
            )
            return cur.rowcount > 0

    def delete(self, rule_id: str) -> bool:
        with db_session() as conn:
            cur = conn.execute("DELETE FROM rules WHERE rule_id = ?", (rule_id,))
            return cur.rowcount > 0


rule_repository = RuleRepository()
