"""
Smart Spectator - Query API Route
Conforms to Sections 12 & 30 of Phase 10 Specification.
Executes structured search queries and interprets natural language commands locally.
"""

from typing import Dict, Any, Optional
from fastapi import APIRouter, HTTPException, Body, status

from services.hub_backend.query.models import StructuredQuery
from services.hub_backend.query.interpreter import query_interpreter
from services.hub_backend.query.query_engine import local_query_engine

router = APIRouter(prefix="/query", tags=["Local Query Engine"])


@router.post("", status_code=status.HTTP_200_OK)
def execute_query(payload: Dict[str, Any] = Body(...)):
    """
    Executes a structured or natural language search query.
    Zero raw SQL permitted. 100% parameter validated.
    """
    try:
        # If natural query provided, interpret it first
        if "natural_query" in payload or "query_text" in payload:
            text = payload.get("natural_query") or payload.get("query_text", "")
            sq = query_interpreter.interpret(text)
            # Allow explicit overrides
            if "limit" in payload:
                sq.limit = int(payload["limit"])
            if "offset" in payload:
                sq.offset = int(payload["offset"])
        else:
            sq = StructuredQuery(
                event_type=payload.get("event_type"),
                camera_id=payload.get("camera_id"),
                zone_id=payload.get("zone_id"),
                priority=payload.get("priority"),
                after=payload.get("after"),
                before=payload.get("before"),
                limit=int(payload.get("limit", 50)),
                offset=int(payload.get("offset", 0)),
                has_recording=payload.get("has_recording"),
                is_anomaly=bool(payload.get("is_anomaly", False)),
            )

        return local_query_engine.execute(sq)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Query execution failed: {e}")
