"""
Smart Spectator - REST API: Spatial Zones Management
Conforms to Section 21 of Phase 4 specification.
"""

from datetime import datetime, timezone
import json
from typing import List, Dict, Any, Optional
import uuid
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from shared.schemas.v1.models import Zone
from services.hub_backend.database.connection import db_session
from services.event_engine import event_engine

router = APIRouter(tags=["Zones"])


class ZoneCreateRequest(BaseModel):
    name: str = Field(..., description="Human readable zone name")
    polygon: List[List[float]] = Field(..., description="List of [x, y] normalized vertices (0.0 to 1.0)")
    color: Optional[str] = Field("#38bdf8", description="Hex display color")
    is_active: bool = Field(True)


class ZoneUpdateRequest(BaseModel):
    name: Optional[str] = None
    polygon: Optional[List[List[float]]] = None
    color: Optional[str] = None
    is_active: Optional[bool] = None


@router.get("/cameras/{camera_id}/zones", response_model=List[Zone])
def list_camera_zones(camera_id: str):
    """Retrieves all active zones configured for a camera."""
    return event_engine.zone_engine.get_zones_for_camera(camera_id)


@router.post("/cameras/{camera_id}/zones", response_model=Zone, status_code=status.HTTP_201_CREATED)
def create_camera_zone(camera_id: str, req: ZoneCreateRequest):
    """Creates a new polygon zone with strict coordinate validation."""
    try:
        event_engine.zone_engine.validate_polygon(req.polygon)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Verify camera exists
    with db_session() as conn:
        cursor = conn.execute("SELECT camera_id FROM cameras WHERE camera_id = ?", (camera_id,))
        if not cursor.fetchone():
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

    with db_session() as conn:
        conn.execute(
            """
            INSERT INTO zones (zone_id, camera_id, name, polygon_json, color, is_active, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                zone.zone_id,
                zone.camera_id,
                zone.name,
                json.dumps(zone.polygon),
                zone.color,
                1 if zone.is_active else 0,
                zone.created_at.isoformat(),
                zone.updated_at.isoformat(),
            ),
        )
        conn.execute(
            "INSERT INTO audit_logs (log_id, actor, action, resource, metadata_json) VALUES (?, ?, ?, ?, ?)",
            (str(uuid.uuid4()), "user", "zone_created", zone.zone_id, json.dumps({"name": zone.name, "camera_id": camera_id})),
        )

    event_engine.zone_engine.add_or_update_zone_memory(zone)
    return zone


@router.put("/zones/{zone_id}", response_model=Zone)
def update_zone(zone_id: str, req: ZoneUpdateRequest):
    """Updates an existing zone configuration."""
    with db_session() as conn:
        cursor = conn.execute("SELECT * FROM zones WHERE zone_id = ?", (zone_id,))
        row = cursor.fetchone()
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

    with db_session() as conn:
        conn.execute(
            """
            UPDATE zones SET name = ?, polygon_json = ?, color = ?, is_active = ?, updated_at = ?
            WHERE zone_id = ?
            """,
            (
                zone.name,
                json.dumps(zone.polygon),
                zone.color,
                1 if zone.is_active else 0,
                zone.updated_at.isoformat(),
                zone.zone_id,
            ),
        )
        conn.execute(
            "INSERT INTO audit_logs (log_id, actor, action, resource, metadata_json) VALUES (?, ?, ?, ?, ?)",
            (str(uuid.uuid4()), "user", "zone_updated", zone.zone_id, json.dumps({"name": zone.name})),
        )

    event_engine.zone_engine.add_or_update_zone_memory(zone)
    return zone


@router.delete("/zones/{zone_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_zone(zone_id: str):
    """Deletes a zone."""
    with db_session() as conn:
        cursor = conn.execute("SELECT camera_id, name FROM zones WHERE zone_id = ?", (zone_id,))
        row = cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail=f"Zone '{zone_id}' not found.")

        conn.execute("DELETE FROM zones WHERE zone_id = ?", (zone_id,))
        conn.execute(
            "INSERT INTO audit_logs (log_id, actor, action, resource, metadata_json) VALUES (?, ?, ?, ?, ?)",
            (str(uuid.uuid4()), "user", "zone_deleted", zone_id, json.dumps(row)),
        )

    event_engine.zone_engine.remove_zone_memory(row["camera_id"], zone_id)
