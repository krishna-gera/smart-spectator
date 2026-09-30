"""
Phase 10 Tests — Security & Action Safety Enforcement
Conforms to Sections 16, 27, 36 & 37 of Phase 10 Specification.
Validates:
1. ActionSafetyValidator strict rejection of shell commands, SQL, path traversal, and network calls.
2. Query API parameter injection resistance.
3. Privacy mask application without biometric processing.
"""

import numpy as np
import pytest

from ai.orchestration.safety import (
    action_safety_validator,
    PermittedActionType,
)
from services.hub_backend.query import local_query_engine, StructuredQuery
from services.stream_engine.privacy import privacy_mask_engine


def test_action_safety_validator_enforces_whitelist_and_blocks_attacks():
    # 1. Valid action proposal
    assert action_safety_validator.validate_action_proposal(
        action_type="FLAG_EVENT",
        payload={"event_id": "ev_123", "reason": "operator_review"}
    ) is True

    # 2. Unknown / unauthorized action
    with pytest.raises(ValueError, match="not a permitted system action"):
        action_safety_validator.validate_action_proposal(
            action_type="DELETE_ALL_RECORDINGS",
            payload={}
        )

    # 3. Payload with shell command injection pattern
    with pytest.raises(ValueError, match="forbidden command pattern"):
        action_safety_validator.validate_action_proposal(
            action_type="DISPATCH_NOTIFICATION",
            payload={"summary": "test; rm -rf /; bash -i"}
        )

    # 4. Payload with SQL injection pattern
    with pytest.raises(ValueError, match="forbidden command pattern"):
        action_safety_validator.validate_action_proposal(
            action_type="DISPATCH_NOTIFICATION",
            payload={"summary": "'; SELECT * FROM users WHERE '1'='1"}
        )

    # 5. Payload with path traversal pattern
    with pytest.raises(ValueError, match="forbidden command pattern"):
        action_safety_validator.validate_action_proposal(
            action_type="DISPATCH_NOTIFICATION",
            payload={"summary": "reading ../../../etc/passwd"}
        )


def test_query_engine_sql_injection_defense():
    # Attempt SQL injection via string parameters
    malicious_query = StructuredQuery(
        event_type="'; DROP TABLE events; --",
        camera_id="' OR '1'='1",
    )
    # Must execute safely without corrupting the database or injecting raw SQL
    res = local_query_engine.execute(malicious_query)
    assert res["total_count"] == 0


def test_privacy_mask_engine_application():
    # Create blank 100x100 white image
    frame = np.ones((100, 100, 3), dtype=np.uint8) * 255

    # Configure privacy mask: top-left quadrant [0.0, 0.0, 0.5, 0.5]
    privacy_mask_engine.set_privacy_masks("cam_test", [(0.0, 0.0, 0.5, 0.5)])

    masked = privacy_mask_engine.apply_mask("cam_test", frame, fill_color=(0, 0, 0))

    # Masked region should be black (0, 0, 0)
    assert np.all(masked[10:40, 10:40] == [0, 0, 0])
    # Unmasked region should remain white (255, 255, 255)
    assert np.all(masked[60:90, 60:90] == [255, 255, 255])
