"""
Smart Spectator - REST API: Detection Zones Management
Conforms to Section 21 of Phase 4 specification.
"""

from datetime import datetime, timezone
import json
from typing import List, Dict, Any, Optional
import uuid
from fastapi import APIRouter, HTTPException, Depends, status
from pydantic import BaseModel, Field

from shared.schemas.v1.models import Zone
from services.hub_backend.database.repositories.camera_repo import camera_repository
from services.hub_backend.database.repositories.zone_repo import zone_repository
from services.hub_backend.database.repositories.audit_repo import audit_repository
from services.event_engine import event_engine
from ..auth.dependencies import require_operator, require_viewer
from ..auth.models import Principal

router = APIRouter(tags=["Zones"])


class ZoneCreateRequest(BaseModel):
    name: str = Field(..., description="Human readable zone name")
    polygon: List[List[float]] = Field(..., min_length=3, description="List of [x, y] coordinates in [0.0, 1.0]")
    color: Optional[str] = Field("#38bdf8", description="Hex color string for UI overlay")
    is_active: bool = Field(True)


class ZoneUpdateRequest(BaseModel):
    name: Optional[str] = None
    polygon: Optional[List[List[float]]] = None
    color: Optional[str] = None
    is_active: Optional[bool] = None


@router.get("/cameras/{camera_id}/zones", response_model=List[Zone])
def list_zones_for_camera(camera_id: str, viewer: Principal = Depends(require_viewer)):
    """Lists all configured detection zones for a camera."""
    return event_engine.zone_engine.get_zones_for_camera(camera_id)


@router.get("/zones", response_model=List[Zone])
def list_all_zones(viewer: Principal = Depends(require_viewer)):
    """Lists all configured detection zones across all cameras."""
    return event_engine.zone_engine.get_all_zones()


@router.post("/cameras/{camera_id}/zones", response_model=Zone, status_code=status.HTTP_201_CREATED)
def create_zone(camera_id: str, req: ZoneCreateRequest, operator: Principal = Depends(require_operator)):
    """Creates a new detection zone for a specific camera."""
    try:
        event_engine.zone_engine.validate_polygon(req.polygon)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Verify camera exists via repository
    cam = camera_repository.get_by_id(camera_id)
    if not cam:
        raise HTTPException(status_code=404, detail=f"Camera '{camera_id}' not found.")

    zone_id = f"zone_{uuid.uuid4().hex[:8]}"
    now_dt = datetime.now(timezone.utc)
    zone = Zone(
        zone_id=zone_id,
        camera_id=camera_id,
        name=req.name,
        polygon=req.polygon,
        color=req.color or "#38bdf8",
        is_active=req.is_active,
        created_at=now_dt,
        updated_at=now_dt,
    )

    zone_repository.create(
        zone_id=zone.zone_id,
        camera_id=zone.camera_id,
        name=zone.name,
        polygon_json=json.dumps(zone.polygon),
        color=zone.color,
        is_active=zone.is_active,
        created_at=zone.created_at.isoformat(),
        updated_at=zone.updated_at.isoformat(),
    )

    audit_repository.log(
        action="zone_created",
        actor=operator.username,
        resource=zone.zone_id,
        details={"name": zone.name, "camera_id": camera_id}
    )

    event_engine.zone_engine.add_or_update_zone_memory(zone)
    return zone


@router.put("/zones/{zone_id}", response_model=Zone)
def update_zone(zone_id: str, req: ZoneUpdateRequest, operator: Principal = Depends(require_operator)):
    """Updates an existing zone configuration."""
    row = zone_repository.get_by_id(zone_id)
    if not row:
        raise HTTPException(status_code=404, detail=f"Zone '{zone_id}' not found.")

    current_polygon = json.loads(row["polygon_json"])
    new_polygon = req.polygon if req.polygon is not None else current_polygon
    if req.polygon is not None:
        try:
            event_engine.zone_engine.validate_polygon(new_polygon)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

    new_name = req.name if req.name is not None else row["name"]
    new_color = req.color if req.color is not None else row.get("color", "#38bdf8")
    new_active = req.is_active if req.is_active is not None else bool(row["is_active"])
    now_dt = datetime.now(timezone.utc)

    zone = Zone(
        zone_id=zone_id,
        camera_id=row["camera_id"],
        name=new_name,
        polygon=new_polygon,
        color=new_color,
        is_active=new_active,
        created_at=datetime.fromisoformat(row["created_at"]),
        updated_at=now_dt,
    )

    zone_repository.update(
        zone_id=zone_id,
        name=zone.name,
        polygon_json=json.dumps(zone.polygon),
        color=zone.color,
        is_active=zone.is_active,
        updated_at=zone.updated_at.isoformat(),
    )

    audit_repository.log(
        action="zone_updated",
        actor=operator.username,
        resource=zone.zone_id,
        details={"name": zone.name}
    )

    event_engine.zone_engine.add_or_update_zone_memory(zone)
    return zone


@router.delete("/zones/{zone_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_zone(zone_id: str, operator: Principal = Depends(require_operator)):
    """Deletes a zone."""
    deleted_row = zone_repository.delete(zone_id)
    if not deleted_row:
        raise HTTPException(status_code=404, detail=f"Zone '{zone_id}' not found.")

    audit_repository.log(
        action="zone_deleted",
        actor=operator.username,
        resource=zone_id,
        details=deleted_row
    )

    event_engine.zone_engine.remove_zone_memory(deleted_row["camera_id"], zone_id)
