"""
Phase 10 Tests — Resource Priority & Performance Budget
Conforms to Sections 34, 35 & 37 of Phase 10 Specification.
Validates:
1. Separation between REAL_TIME vision pipeline and BACKGROUND analytics.
2. Backpressure detection and task yielding during camera queue congestion.
3. Thread pool execution isolation.
"""

import time
import pytest

from services.hub_backend.system.resource_manager import (
    ResourcePriorityManager,
    ExecutionTier,
)


def test_resource_manager_submits_and_executes_background_task():
    rm = ResourcePriorityManager(max_background_workers=2, queue_backpressure_threshold=8)
    
    executed = []
    def sample_task(val):
        executed.append(val)

    # When uncongested, task should be accepted and executed
    success = rm.submit_background_task(sample_task, 42)
    assert success is True

    # Give thread pool brief moment to complete
    time.sleep(0.05)
    assert 42 in executed
    rm.shutdown()


def test_resource_manager_yields_under_congestion(monkeypatch):
    rm = ResourcePriorityManager(max_background_workers=2, queue_backpressure_threshold=8)

    # Simulate congestion in real-time camera context
    monkeypatch.setattr(rm, "is_realtime_congested", lambda: True)

    executed = []
    def heavy_baseline_calc():
        executed.append(True)

    # Should yield and decline to run heavy background task
    success = rm.submit_background_task(heavy_baseline_calc)
    assert success is False
    assert len(executed) == 0
    rm.shutdown()
