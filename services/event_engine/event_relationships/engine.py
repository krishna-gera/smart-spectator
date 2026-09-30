"""
Smart Spectator - Event Relationship Engine
Conforms to Section 3 of Phase 10 Specification.
Identifies temporal and spatial relationships between events deterministically.
"""

from datetime import datetime, timezone
import json
import logging
from typing import Dict, Any, List, Optional
import uuid

from services.event_engine.event_relationships.models import (
    EventRelationship,
    RelationshipRule,
    RelationshipType,
    ScopeFilter,
)
from services.hub_backend.database.connection import get_db

logger = logging.getLogger("EventRelationshipEngine")


class EventRelationshipEngine:
    """
    Evaluates incoming events against sliding history to discover causal,
    temporal, and spatial relationships without cloud/external LLMs.
    """

    def __init__(self):
        self._rules: List[RelationshipRule] = []
        self._init_default_rules()

    def _init_default_rules(self) -> None:
        """Initializes canonical deterministic relationship templates."""
        self._rules = [
            RelationshipRule(
                rule_id="rel_entry_exit",
                name="Person Entered followed by Person Left",
                event_type_a="person_entered",
                event_type_b="person_left",
                relationship_type=RelationshipType.FOLLOWED_BY,
                max_time_window_seconds=1800.0,  # 30 minutes
                camera_scope=ScopeFilter.SAME,
            ),
            RelationshipRule(
                rule_id="rel_entry_object_removed",
                name="Person Entered followed by Object Removed",
                event_type_a="person_entered",
                event_type_b="object_removed",
                relationship_type=RelationshipType.FOLLOWED_BY,
                max_time_window_seconds=600.0,  # 10 minutes
                camera_scope=ScopeFilter.SAME,
            ),
            RelationshipRule(
                rule_id="rel_camera_handoff",
                name="Cross-Camera Person Handoff",
                event_type_a="person_entered",
                event_type_b="person_entered",
                relationship_type=RelationshipType.CAMERA_HANDOFF,
                max_time_window_seconds=120.0,  # 2 minutes
                camera_scope=ScopeFilter.DIFFERENT,
            ),
            RelationshipRule(
                rule_id="rel_camera_tamper_recovery",
                name="Camera Blocked followed by Recovered",
                event_type_a="camera_blocked",
                event_type_b="camera_recovered",
                relationship_type=RelationshipType.STATE_CHANGE,
                max_time_window_seconds=3600.0,  # 1 hour
                camera_scope=ScopeFilter.SAME,
            ),
            RelationshipRule(
                rule_id="rel_repeated_loitering",
                name="Repeated Loitering in Same Zone",
                event_type_a="loitering_detected",
                event_type_b="loitering_detected",
                relationship_type=RelationshipType.REPEATED_ACTIVITY,
                max_time_window_seconds=900.0,  # 15 minutes
                camera_scope=ScopeFilter.SAME,
                zone_scope=ScopeFilter.SAME,
            ),
        ]

    def register_rule(self, rule: RelationshipRule) -> None:
        self._rules.append(rule)

    def evaluate_relationships(
        self,
        new_event: Dict[str, Any],
        recent_events: List[Dict[str, Any]],
        persist: bool = True,
    ) -> List[EventRelationship]:
        """
        Evaluates a new event against recent prior events to discover matches.
        Handles possible timestamp disorder gracefully.
        """
        discovered: List[EventRelationship] = []
        new_time_val = new_event.get("timestamp") or new_event.get("start_time")
        if isinstance(new_time_val, str):
            try:
                new_dt = datetime.fromisoformat(new_time_val.replace("Z", "+00:00"))
            except Exception:
                new_dt = datetime.now(timezone.utc)
        elif isinstance(new_time_val, datetime):
            new_dt = new_time_val
        else:
            new_dt = datetime.now(timezone.utc)

        new_type = str(new_event.get("event_type", "")).lower()
        new_camera = str(new_event.get("camera_id", ""))
        new_zone = str(new_event.get("zone_id", ""))

        for prior in recent_events:
            prior_id = prior.get("event_id")
            if not prior_id or prior_id == new_event.get("event_id"):
                continue

            prior_time_val = prior.get("timestamp") or prior.get("start_time")
            if isinstance(prior_time_val, str):
                try:
                    prior_dt = datetime.fromisoformat(prior_time_val.replace("Z", "+00:00"))
                except Exception:
                    continue
            elif isinstance(prior_time_val, datetime):
                prior_dt = prior_time_val
            else:
                continue

            delta_sec = (new_dt - prior_dt).total_seconds()
            # If events arrived slightly out of order, handle symmetrically or safely
            abs_delta_sec = abs(delta_sec)

            prior_type = str(prior.get("event_type", "")).lower()
            prior_camera = str(prior.get("camera_id", ""))
            prior_zone = str(prior.get("zone_id", ""))

            for rule in self._rules:
                # Rule expects A -> B
                # Case 1: prior is A, new is B (normal chronological order)
                match_normal = (
                    prior_type == rule.event_type_a.lower()
                    and new_type == rule.event_type_b.lower()
                    and delta_sec >= rule.min_time_window_seconds
                    and delta_sec <= rule.max_time_window_seconds
                )

                if match_normal:
                    # Check camera scope
                    cam_match = True
                    if rule.camera_scope == ScopeFilter.SAME:
                        cam_match = (prior_camera == new_camera)
                    elif rule.camera_scope == ScopeFilter.DIFFERENT:
                        cam_match = (prior_camera != new_camera)

                    # Check zone scope
                    zone_match = True
                    if rule.zone_scope == ScopeFilter.SAME:
                        zone_match = bool(prior_zone and new_zone and prior_zone == new_zone)
                    elif rule.zone_scope == ScopeFilter.DIFFERENT:
                        zone_match = (prior_zone != new_zone)

                    if cam_match and zone_match:
                        conf = round(
                            float(prior.get("confidence", 0.8))
                            * float(new_event.get("confidence", 0.8))
                            * rule.confidence_weight,
                            3,
                        )
                        rel = EventRelationship(
                            relationship_id=f"rel_{uuid.uuid4().hex[:12]}",
                            relationship_type=rule.relationship_type.value,
                            event_a_id=prior_id,
                            event_b_id=str(new_event.get("event_id")),
                            time_delta_seconds=round(delta_sec, 2),
                            confidence=min(1.0, conf),
                            camera_id=new_camera if prior_camera == new_camera else None,
                            zone_id=new_zone if prior_zone == new_zone else None,
                            details={
                                "rule_id": rule.rule_id,
                                "rule_name": rule.name,
                                "event_a_type": prior_type,
                                "event_b_type": new_type,
                                "camera_a": prior_camera,
                                "camera_b": new_camera,
                            },
                        )
                        discovered.append(rel)

        if persist and discovered:
            self._persist_relationships(discovered)

        return discovered

    def _persist_relationships(self, relationships: List[EventRelationship]) -> None:
        try:
            with get_db() as conn:
                for rel in relationships:
                    conn.execute(
                        """
                        INSERT OR REPLACE INTO event_relationships (
                            relationship_id, relationship_type, event_a_id, event_b_id,
                            camera_id, zone_id, time_delta_seconds, confidence,
                            details_json, created_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            rel.relationship_id,
                            rel.relationship_type,
                            rel.event_a_id,
                            rel.event_b_id,
                            rel.camera_id,
                            rel.zone_id,
                            rel.time_delta_seconds,
                            rel.confidence,
                            json.dumps(rel.details),
                            rel.created_at,
                        ),
                    )
                conn.commit()
        except Exception as e:
            logger.error(f"Failed to persist event relationships: {e}")


relationship_engine = EventRelationshipEngine()
