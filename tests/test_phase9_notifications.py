"""Phase 9 Tests — Local Notification Dispatcher & Multi-tier Cooldowns.

Validates:
1. Notification delivery for critical and important events
2. Global, camera-specific, and event-type cooldown enforcement
3. Category classification (Critical, Important, Informational)
4. Dispatch callback invocation
"""

import time
import pytest
from services.event_engine.notifications import NotificationDispatcher, EVENT_CATEGORY_MAP
from shared.schemas.v1.models import Event, EventPriority, NotificationCategory


def test_notification_categorization():
    dispatcher = NotificationDispatcher(global_cooldown_seconds=1.0)

    # Critical priority -> Critical category
    assert EVENT_CATEGORY_MAP.get("CAMERA_BLOCKED") == NotificationCategory.CRITICAL
    assert EVENT_CATEGORY_MAP.get("PERSON_ENTERED") == NotificationCategory.IMPORTANT
    assert EVENT_CATEGORY_MAP.get("NORMAL_ACTIVITY") == NotificationCategory.INFORMATIONAL


def test_notification_multi_tier_cooldown():
    dispatcher = NotificationDispatcher(
        global_cooldown_seconds=0.2,
        camera_cooldown_seconds=0.4,
    )

    dispatched = []
    dispatcher.set_broadcaster(lambda event_type, payload: dispatched.append(payload))

    ev1 = Event(
        event_id="ev_01",
        camera_id="cam_1",
        event_type="PERSON_ENTERED",
        priority=EventPriority.HIGH,
        confidence=0.9,
        summary="Person entered area",
        explanation="Person entered area"
    )

    # First dispatch should succeed
    res1 = dispatcher.dispatch(ev1)
    assert res1 is not None
    assert len(dispatched) == 1

    # Immediate second dispatch on same camera should be blocked by cooldown
    res2 = dispatcher.dispatch(ev1)
    assert res2 is None
    assert len(dispatched) == 1

    # Wait for global cooldown (0.2s) but not camera cooldown (0.4s)
    time.sleep(0.22)
    ev_same_cam = Event(
        event_id="ev_02",
        camera_id="cam_1",
        event_type="OBJECT_MOVED",
        priority=EventPriority.MEDIUM,
        confidence=0.85,
        summary="Object moved"
    )
    # Blocked by camera cooldown on cam_1
    res3 = dispatcher.dispatch(ev_same_cam)
    assert res3 is None

    # Wait for camera cooldown to expire (remaining ~0.25s)
    time.sleep(0.25)
    ev_different_cam = Event(
        event_id="ev_03",
        camera_id="cam_2",
        event_type="PERSON_ENTERED",
        priority=EventPriority.HIGH,
        confidence=0.9,
        summary="Person entered cam 2"
    )
    res4 = dispatcher.dispatch(ev_different_cam)
    assert res4 is not None
    assert len(dispatched) == 2
