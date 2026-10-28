"""
Smart Spectator - Resource Priority & Performance Budget Manager
Conforms to Sections 34 & 35 of Phase 10 Specification.
Enforces strict separation between REAL_TIME vision pipeline and BACKGROUND analytics.
Ensures baseline calculation, pattern detection, and memory pruning yield
whenever real-time frame queues experience load.
"""

from concurrent.futures import ThreadPoolExecutor
from enum import Enum
import logging
from typing import Callable, Any, Optional

logger = logging.getLogger("ResourceManager")


class ExecutionTier(str, Enum):
    REAL_TIME = "REAL_TIME"
    EVENT_PROCESSING = "EVENT_PROCESSING"
    BACKGROUND_ANALYTICS = "BACKGROUND_ANALYTICS"
    ON_DEMAND = "ON_DEMAND"


class ResourcePriorityManager:
    """
    Guarantees that secondary background workloads (anomaly baselines, pattern scans,
    memory summarization) do not block or degrade primary real-time vision pipelines.
    """

    def __init__(self, max_background_workers: int = 2, queue_backpressure_threshold: int = 2):
        self._bg_pool = ThreadPoolExecutor(max_workers=max_background_workers, thread_name_prefix="ss-background")
        self.queue_backpressure_threshold = queue_backpressure_threshold

    def is_realtime_congested(self) -> bool:
        """
        Checks whether any active camera context in the AI pipeline has queue depth
        exceeding backpressure threshold (bounded queue capacity is 2).
        """
        try:
            from services.ai_engine.pipeline import ai_pipeline
            for ctx in ai_pipeline.contexts.values():
                if ctx.queue.full() or ctx.queue.qsize() >= self.queue_backpressure_threshold:
                    return True
        except Exception:
            pass
        return False

    def submit_background_task(self, fn: Callable[..., Any], *args, **kwargs) -> bool:
        """
        Submits task to background execution tier.
        If real-time pipeline is currently experiencing congestion, yields and skips/defers.
        """
        if self.is_realtime_congested():
            logger.warning("[ResourceManager] Real-time vision pipeline congested. Deferring background task.")
            return False

        try:
            self._bg_pool.submit(fn, *args, **kwargs)
            return True
        except Exception as e:
            logger.error(f"[ResourceManager] Failed to schedule background task: {e}")
            return False

    def shutdown(self) -> None:
        self._bg_pool.shutdown(wait=False)


resource_manager = ResourcePriorityManager()
