"""
Smart Spectator - Incident Engine
Conforms to Section 4 of Phase 10 Specification.
Assembles Event + Context + Relationships -> Incident using deterministic rules.
"""

from datetime import datetime, timezone
import json
import logging
from typing import Dict, Any, List, Optional
import uuid

from services.event_engine.incident_engine.models import (
    Incident,
    IncidentSeverity,
    IncidentStatus,
)
from services.event_engine.context_engine.models import EnvironmentalContext
from services.event_engine.event_relationships.models import EventRelationship
from services.hub_backend.database.connection import get_db

logger = logging.getLogger("IncidentEngine")


class IncidentEngine:
    """
    Evaluates correlated events, environmental context, and spatial rules
    to generate, update, and track macro incidents without external LLMs.
    """

    def evaluate_incident(
        self,
        event: Dict[str, Any],
        context: Optional[EnvironmentalContext] = None,
        relationships: Optional[List[EventRelationship]] = None,
        persist: bool = True,
    ) -> Optional[Incident]:
        """
        Determines if an event warrants incident generation or incident linking.
        """
        event_id = str(event.get("event_id", ""))
        event_type = str(event.get("event_type", "")).lower()
        priority = str(event.get("priority", "MEDIUM")).upper()
        camera_id = str(event.get("camera_id", ""))
        zone_id = str(event.get("zone_id", ""))
        zone_type = str(event.get("zone_type", "")).lower()

        is_after_hours = context.is_after_hours if context else False
        recent_count = context.recent_events_count_5m if context else 0

        incident: Optional[Incident] = None

        # Rule 1: After-Hours Intrusion in restricted or exclusion zone
        if (is_after_hours and ("enter" in event_type or "intrusion" in event_type or priority == "CRITICAL")):
            incident = Incident(
                incident_id=f"inc_{uuid.uuid4().hex[:12]}",
                incident_type="AFTER_HOURS_ENTRY",
                title=f"After-Hours Presence Detected on {camera_id}",
                severity=IncidentSeverity.CRITICAL if priority == "CRITICAL" else IncidentSeverity.HIGH,
                status=IncidentStatus.OPEN,
                summary=f"Person entry detected during non-operational hours (hour={context.hour_of_day if context else 'N/A'}) on camera '{camera_id}'.",
                camera_ids=[camera_id] if camera_id else [],
                zone_ids=[zone_id] if zone_id else [],
                source_event_ids=[event_id] if event_id else [],
                context=context.to_dict() if context else {},
            )

        # Rule 2: Multi-event chain (e.g. entry followed by object removal)
        elif relationships:
            for rel in relationships:
                if rel.relationship_type == "followed_by" and "object_removed" in str(rel.details.get("event_b_type", "")):
                    incident = Incident(
                        incident_id=f"inc_{uuid.uuid4().hex[:12]}",
                        incident_type="UNAUTHORIZED_REMOVAL",
                        title=f"Potential Object Removal Incident on {camera_id}",
                        severity=IncidentSeverity.HIGH,
                        status=IncidentStatus.OPEN,
                        summary=f"Person entry was rapidly followed by object removal within {rel.time_delta_seconds}s.",
                        camera_ids=[camera_id] if camera_id else [],
                        zone_ids=[zone_id] if zone_id else [],
                        source_event_ids=[rel.event_a_id, rel.event_b_id],
                        context=context.to_dict() if context else {},
                    )
                    break
                elif rel.relationship_type == "camera_handoff":
                    incident = Incident(
                        incident_id=f"inc_{uuid.uuid4().hex[:12]}",
                        incident_type="CROSS_CAMERA_ACTIVITY",
                        title=f"Cross-Camera Sequential Activity Detected",
                        severity=IncidentSeverity.MEDIUM,
                        status=IncidentStatus.OPEN,
                        summary=f"Coordinated motion detected across {rel.details.get('camera_a')} and {rel.details.get('camera_b')} within {rel.time_delta_seconds}s.",
                        camera_ids=list(filter(None, [rel.details.get("camera_a"), rel.details.get("camera_b")])),
                        zone_ids=[zone_id] if zone_id else [],
                        source_event_ids=[rel.event_a_id, rel.event_b_id],
                        context=context.to_dict() if context else {},
                    )
                    break

        # Rule 3: Prolonged loitering in exclusion zone
        elif "loiter" in event_type and (zone_type == "exclusion" or priority in ("HIGH", "CRITICAL")):
            incident = Incident(
                incident_id=f"inc_{uuid.uuid4().hex[:12]}",
                incident_type="RESTRICTED_ZONE_DWELL",
                title=f"Prolonged Dwell in Restricted Zone on {camera_id}",
                severity=IncidentSeverity.HIGH,
                status=IncidentStatus.OPEN,
                summary=f"Actor loitered in designated restricted zone '{zone_id}' exceeding dwell thresholds.",
                camera_ids=[camera_id] if camera_id else [],
                zone_ids=[zone_id] if zone_id else [],
                source_event_ids=[event_id] if event_id else [],
                context=context.to_dict() if context else {},
            )

        if incident and persist:
            self._save_incident(incident)

        return incident

    def _save_incident(self, incident: Incident) -> None:
        try:
            with get_db() as conn:
                conn.execute(
                    """
                    INSERT INTO incidents (
                        incident_id, incident_type, title, severity, status, summary,
                        camera_ids_json, zone_ids_json, source_event_ids_json, context_json,
                        created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        incident.incident_id,
                        incident.incident_type,
                        incident.title,
                        incident.severity.value,
                        incident.status.value,
                        incident.summary,
                        json.dumps(incident.camera_ids),
                        json.dumps(incident.zone_ids),
                        json.dumps(incident.source_event_ids),
                        json.dumps(incident.context),
                        incident.created_at,
                        incident.updated_at,
                    ),
                )
                conn.commit()
        except Exception as e:
            logger.error(f"Failed to persist incident: {e}")

    def get_incident(self, incident_id: str) -> Optional[Incident]:
        with get_db() as conn:
            cursor = conn.execute("SELECT * FROM incidents WHERE incident_id = ?", (incident_id,))
            row = cursor.fetchone()
            if not row:
                return None
            return self._row_to_incident(row)

    def list_incidents(
        self,
        status: Optional[str] = None,
        severity: Optional[str] = None,
        camera_id: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[Incident]:
        query = "SELECT * FROM incidents WHERE 1=1"
        params: List[Any] = []
        if status:
            query += " AND status = ?"
            params.append(status.upper())
        if severity:
            query += " AND severity = ?"
            params.append(severity.upper())
        if camera_id:
            query += " AND camera_ids_json LIKE ?"
            params.append(f"%{camera_id}%")

        query += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        with get_db() as conn:
            cursor = conn.execute(query, tuple(params))
            return [self._row_to_incident(row) for row in cursor.fetchall()]

    def acknowledge_incident(self, incident_id: str, operator_id: str = "operator") -> Optional[Incident]:
        now_str = datetime.now(timezone.utc).isoformat()
        with get_db() as conn:
            conn.execute(
                """
                UPDATE incidents
                SET status = 'ACKNOWLEDGED', acknowledged_at = ?, acknowledged_by = ?, updated_at = ?
                WHERE incident_id = ?
                """,
                (now_str, operator_id, now_str, incident_id),
            )
            conn.commit()
        return self.get_incident(incident_id)

    def resolve_incident(self, incident_id: str, operator_id: str = "operator", notes: str = "") -> Optional[Incident]:
        now_str = datetime.now(timezone.utc).isoformat()
        with get_db() as conn:
            conn.execute(
                """
                UPDATE incidents
                SET status = 'RESOLVED', resolved_at = ?, resolved_by = ?, resolution_notes = ?, updated_at = ?
                WHERE incident_id = ?
                """,
                (now_str, operator_id, notes, now_str, incident_id),
            )
            conn.commit()
        return self.get_incident(incident_id)

    def _row_to_incident(self, row: Any) -> Incident:
        # Check dict vs tuple
        if isinstance(row, dict):
            r = row
        else:
            cols = [
                "incident_id", "incident_type", "title", "severity", "status", "summary",
                "camera_ids_json", "zone_ids_json", "source_event_ids_json", "context_json",
                "acknowledged_at", "acknowledged_by", "resolved_at", "resolved_by",
                "resolution_notes", "created_at", "updated_at"
            ]
            r = dict(zip(cols, row))

        return Incident(
            incident_id=r["incident_id"],
            incident_type=r["incident_type"],
            title=r["title"],
            severity=IncidentSeverity(r["severity"]),
            status=IncidentStatus(r["status"]),
            summary=r["summary"],
            camera_ids=json.loads(r["camera_ids_json"] or "[]"),
            zone_ids=json.loads(r["zone_ids_json"] or "[]"),
            source_event_ids=json.loads(r["source_event_ids_json"] or "[]"),
            context=json.loads(r["context_json"] or "{}"),
            acknowledged_at=r.get("acknowledged_at"),
            acknowledged_by=r.get("acknowledged_by"),
            resolved_at=r.get("resolved_at"),
            resolved_by=r.get("resolved_by"),
            resolution_notes=r.get("resolution_notes"),
            created_at=r["created_at"],
            updated_at=r["updated_at"],
        )


incident_engine = IncidentEngine()
