"""
Smart Spectator - Model Drift Monitoring
Conforms to Section 25 of Phase 10 Specification.
Tracks confidence score distributions and output shifts across evaluation windows.
Issues MODEL_DRIFT_WARNING only when documented statistical thresholds are crossed.
"""

from dataclasses import dataclass, asdict
from datetime import datetime, timezone, timedelta
import logging
from typing import Dict, Any, List, Optional
import uuid

from services.hub_backend.database.connection import get_db

logger = logging.getLogger("DriftMonitor")


@dataclass
class DriftCheckResult:
    log_id: str
    model_id: str
    window_start: str
    window_end: str
    mean_confidence: float
    expected_confidence: float
    sample_count: int
    drift_detected: bool
    drift_score: float  # Absolute difference between expected and observed mean
    warning_message: Optional[str]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class ModelDriftMonitor:
    """
    Monitors distribution of recent event confidence scores against baseline expectations.
    """

    def __init__(self, drift_threshold: float = 0.15, expected_baseline_conf: float = 0.82):
        self.drift_threshold = drift_threshold
        self.expected_baseline_conf = expected_baseline_conf

    def check_drift(
        self,
        model_id: str = "spectatornet_v1_int8",
        window_hours: int = 24,
        persist: bool = True,
    ) -> DriftCheckResult:
        now = datetime.now(timezone.utc)
        since = now - timedelta(hours=window_hours)
        since_str = since.isoformat()
        now_str = now.isoformat()

        with get_db() as conn:
            cursor = conn.execute(
                """
                SELECT confidence FROM events
                WHERE timestamp >= ?
                """,
                (since_str,),
            )
            rows = cursor.fetchall()
            confs = [r[0] if not isinstance(r, dict) else r["confidence"] for r in rows]

        n = len(confs)
        if n < 5:
            # Insufficient samples to assert drift
            return DriftCheckResult(
                log_id=f"drift_{uuid.uuid4().hex[:12]}",
                model_id=model_id,
                window_start=since_str,
                window_end=now_str,
                mean_confidence=0.0,
                expected_confidence=self.expected_baseline_conf,
                sample_count=n,
                drift_detected=False,
                drift_score=0.0,
                warning_message=None,
            )

        mean_c = sum(confs) / n
        drift_delta = abs(self.expected_baseline_conf - mean_c)
        is_drift = (drift_delta >= self.drift_threshold)

        warning = None
        if is_drift:
            warning = (
                f"MODEL_DRIFT_WARNING: Mean inference confidence ({round(mean_c, 3)}) deviated by "
                f"{round(drift_delta, 3)} from expected baseline ({self.expected_baseline_conf}) "
                f"across {n} samples in the last {window_hours}h."
            )

        result = DriftCheckResult(
            log_id=f"drift_{uuid.uuid4().hex[:12]}",
            model_id=model_id,
            window_start=since_str,
            window_end=now_str,
            mean_confidence=round(mean_c, 3),
            expected_confidence=self.expected_baseline_conf,
            sample_count=n,
            drift_detected=is_drift,
            drift_score=round(drift_delta, 3),
            warning_message=warning,
        )

        if persist:
            self._save_drift_log(result)

        return result

    def _save_drift_log(self, res: DriftCheckResult) -> None:
        try:
            with get_db() as conn:
                conn.execute(
                    """
                    INSERT INTO model_drift_logs (
                        log_id, model_id, window_start, window_end, mean_confidence,
                        sample_count, drift_detected, drift_score, warning_message, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        res.log_id,
                        res.model_id,
                        res.window_start,
                        res.window_end,
                        res.mean_confidence,
                        res.sample_count,
                        1 if res.drift_detected else 0,
                        res.drift_score,
                        res.warning_message,
                        res.window_end,
                    ),
                )
                conn.commit()
        except Exception as e:
            logger.error(f"Failed to persist drift log: {e}")


drift_monitor = ModelDriftMonitor()
