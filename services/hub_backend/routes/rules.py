"""
Smart Spectator - REST API: Automation Rules Management
Conforms to Section 22 of Phase 4 specification.
"""

from datetime import datetime, timezone
import json
from typing import List, Dict, Any, Optional
import uuid
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from shared.schemas.v1.models import EventRule, EventSeverity
from services.hub_backend.database.connection import db_session
from services.event_engine import event_engine

router = APIRouter(prefix="/rules", tags=["Rules"])


class RuleCreateRequest(BaseModel):
    name: str = Field(..., description="Human readable rule name")
    enabled: bool = Field(True)
    conditions: Dict[str, Any] = Field(..., description="Structured conditions")
    actions: List[str] = Field(default_factory=lambda: ["CREATE_EVENT", "CLIENT_NOTIFICATION"])
    cooldown_seconds: int = Field(60, ge=0)
    severity_override: Optional[str] = None


class RuleUpdateRequest(BaseModel):
    name: Optional[str] = None
    enabled: Optional[bool] = None
    conditions: Optional[Dict[str, Any]] = None
    actions: Optional[List[str]] = None
    cooldown_seconds: Optional[int] = None
    severity_override: Optional[str] = None


@router.get("", response_model=List[EventRule])
def list_rules():
    """Lists all configured automation rules."""
    return event_engine.rule_engine.get_all_rules()


@router.get("/{rule_id}", response_model=EventRule)
def get_rule(rule_id: str):
    """Retrieves a single rule by ID."""
    rule = event_engine.rule_engine.get_rule(rule_id)
    if not rule:
        raise HTTPException(status_code=404, detail=f"Rule '{rule_id}' not found.")
    return rule


@router.post("", response_model=EventRule, status_code=status.HTTP_201_CREATED)
def create_rule(req: RuleCreateRequest):
    """Creates a new automation rule."""
    rule_id = f"rule_{uuid.uuid4().hex[:8]}"
    now_dt = datetime.now(timezone.utc)
    sev_override = None
    if req.severity_override:
        try:
            sev_override = EventSeverity(req.severity_override.lower())
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid severity '{req.severity_override}'.")

    rule = EventRule(
        rule_id=rule_id,
        name=req.name,
        enabled=req.enabled,
        conditions=req.conditions,
        actions=req.actions,
        cooldown_seconds=req.cooldown_seconds,
        severity_override=sev_override,
        created_at=now_dt,
        updated_at=now_dt,
    )
    event_engine.rule_engine.save_rule_to_db(rule)

    with db_session() as conn:
        conn.execute(
            "INSERT INTO audit_logs (log_id, actor, action, resource, metadata_json) VALUES (?, ?, ?, ?, ?)",
            (str(uuid.uuid4()), "user", "rule_created", rule.rule_id, json.dumps({"name": rule.name})),
        )

    return rule


@router.put("/{rule_id}", response_model=EventRule)
def update_rule(rule_id: str, req: RuleUpdateRequest):
    """Updates an existing automation rule."""
    rule = event_engine.rule_engine.get_rule(rule_id)
    if not rule:
        raise HTTPException(status_code=404, detail=f"Rule '{rule_id}' not found.")

    if req.name is not None:
        rule.name = req.name
    if req.enabled is not None:
        rule.enabled = req.enabled
    if req.conditions is not None:
        rule.conditions = req.conditions
    if req.actions is not None:
        rule.actions = req.actions
    if req.cooldown_seconds is not None:
        rule.cooldown_seconds = req.cooldown_seconds
    if req.severity_override is not None:
        try:
            rule.severity_override = EventSeverity(req.severity_override.lower()) if req.severity_override else None
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid severity '{req.severity_override}'.")

    rule.updated_at = datetime.now(timezone.utc)
    event_engine.rule_engine.save_rule_to_db(rule)

    with db_session() as conn:
        conn.execute(
            "INSERT INTO audit_logs (log_id, actor, action, resource, metadata_json) VALUES (?, ?, ?, ?, ?)",
            (str(uuid.uuid4()), "user", "rule_updated", rule.rule_id, json.dumps({"name": rule.name})),
        )

    return rule


@router.delete("/{rule_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_rule(rule_id: str):
    """Deletes an automation rule."""
    rule = event_engine.rule_engine.get_rule(rule_id)
    if not rule:
        raise HTTPException(status_code=404, detail=f"Rule '{rule_id}' not found.")

    event_engine.rule_engine.delete_rule(rule_id)
    with db_session() as conn:
        conn.execute(
            "INSERT INTO audit_logs (log_id, actor, action, resource, metadata_json) VALUES (?, ?, ?, ?, ?)",
            (str(uuid.uuid4()), "user", "rule_deleted", rule_id, json.dumps({"name": rule.name})),
        )


@router.post("/{rule_id}/enable", response_model=EventRule)
def enable_rule(rule_id: str):
    """Enables an automation rule."""
    rule = event_engine.rule_engine.get_rule(rule_id)
    if not rule:
        raise HTTPException(status_code=404, detail=f"Rule '{rule_id}' not found.")
    rule.enabled = True
    rule.updated_at = datetime.now(timezone.utc)
    event_engine.rule_engine.save_rule_to_db(rule)
    return rule


@router.post("/{rule_id}/disable", response_model=EventRule)
def disable_rule(rule_id: str):
    """Disables an automation rule."""
    rule = event_engine.rule_engine.get_rule(rule_id)
    if not rule:
        raise HTTPException(status_code=404, detail=f"Rule '{rule_id}' not found.")
    rule.enabled = False
    rule.updated_at = datetime.now(timezone.utc)
    event_engine.rule_engine.save_rule_to_db(rule)
    return rule
