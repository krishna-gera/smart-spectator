"""
Smart Spectator - Incidents API Route
Conforms to Sections 4 & 31 of Phase 10 Specification.
Lists, inspects, acknowledges, and resolves security/operational incidents.
"""

from typing import Dict, Any, List, Optional
from fastapi import APIRouter, HTTPException, Query, Body, status

from services.event_engine.incident_engine import incident_engine

router = APIRouter(prefix="/incidents", tags=["Incidents Engine"])


@router.get("", response_model=List[Dict[str, Any]])
def list_incidents(
    status_filter: Optional[str] = Query(None, alias="status"),
    severity: Optional[str] = Query(None),
    camera_id: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    """Lists incidents with optional status, severity, and camera filters."""
    incidents = incident_engine.list_incidents(
        status=status_filter,
        severity=severity,
        camera_id=camera_id,
        limit=limit,
        offset=offset,
    )
    return [i.to_dict() for i in incidents]


@router.get("/{incident_id}", response_model=Dict[str, Any])
def get_incident(incident_id: str):
    """Retrieves full details for a specific incident."""
    inc = incident_engine.get_incident(incident_id)
    if not inc:
        raise HTTPException(status_code=404, detail=f"Incident '{incident_id}' not found.")
    return inc.to_dict()


@router.post("/{incident_id}/acknowledge", response_model=Dict[str, Any])
def acknowledge_incident(incident_id: str, payload: Dict[str, Any] = Body(default_factory=dict)):
    """Operator acknowledgement of an open incident."""
    operator_id = payload.get("operator_id", "operator")
    inc = incident_engine.acknowledge_incident(incident_id, operator_id=operator_id)
    if not inc:
        raise HTTPException(status_code=404, detail=f"Incident '{incident_id}' not found.")
    return inc.to_dict()


@router.post("/{incident_id}/resolve", response_model=Dict[str, Any])
def resolve_incident(incident_id: str, payload: Dict[str, Any] = Body(default_factory=dict)):
    """Operator resolution of an incident with optional notes."""
    operator_id = payload.get("operator_id", "operator")
    notes = payload.get("resolution_notes", "")
    inc = incident_engine.resolve_incident(incident_id, operator_id=operator_id, notes=notes)
    if not inc:
        raise HTTPException(status_code=404, detail=f"Incident '{incident_id}' not found.")
    return inc.to_dict()
