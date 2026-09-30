"""
Smart Spectator - Anomaly Detection Engine
Conforms to Section 9 of Phase 10 Specification.
Evaluates current activity metrics against local statistical baselines using z-scores.
Zero external cloud or LLM dependencies.
"""

from dataclasses import dataclass, asdict, field
from datetime import datetime, timezone
import json
import logging
from typing import Dict, Any, List, Optional
import uuid

from services.event_engine.anomaly.baseline import baseline_engine
from services.hub_backend.database.connection import get_db

logger = logging.getLogger("AnomalyDetector")


@dataclass
class AnomalyReport:
    anomaly_id: str
    anomaly_type: str
    score: float  # e.g., z-score
    explanation: str
    camera_id: Optional[str]
    source_event_ids: List[str]
    metric_name: str
    baseline_mean: float
    observed_value: float
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class AnomalyDetector:
    """
    Detects statistical deviations from normal activity patterns.
    Produces structured explanation strings strictly from calculated math.
    """

    def __init__(self, default_z_threshold: float = 2.5):
        self.default_z_threshold = default_z_threshold

    def evaluate_frequency_anomaly(
        self,
        observed_count: float,
        hour_of_day: int,
        camera_id: Optional[str] = None,
        source_event_ids: Optional[List[str]] = None,
        z_threshold: Optional[float] = None,
        persist: bool = True,
    ) -> Optional[AnomalyReport]:
        """
        Calculates z-score for observed activity count relative to the historical baseline for that hour.
        Returns AnomalyReport if z-score exceeds threshold.
        """
        threshold = z_threshold if z_threshold is not None else self.default_z_threshold
        baseline = baseline_engine.get_baseline(
            metric_name="hourly_event_frequency",
            camera_id=camera_id,
            hour_of_day=hour_of_day,
        )

        if not baseline:
            # Try global baseline (camera_id=None)
            baseline = baseline_engine.get_baseline(
                metric_name="hourly_event_frequency",
                camera_id=None,
                hour_of_day=hour_of_day,
            )

        if not baseline:
            # Insufficient baseline data to evaluate anomaly
            return None

        # Compute z-score: (x - mean) / std_dev
        std = max(baseline.std_dev, 0.5)
        z_score = (observed_count - baseline.mean_value) / std

        if z_score >= threshold:
            rounded_z = round(z_score, 1)
            rounded_obs = round(observed_count, 1)
            rounded_mean = round(baseline.mean_value, 1)
            cam_desc = f" on camera '{camera_id}'" if camera_id else ""
            explanation = (
                f"Event frequency ({rounded_obs}/hr) is {rounded_z} standard deviations "
                f"above the local baseline ({rounded_mean}/hr){cam_desc} for hour {hour_of_day}:00."
            )

            report = AnomalyReport(
                anomaly_id=f"anom_{uuid.uuid4().hex[:12]}",
                anomaly_type="UNUSUAL_ACTIVITY_FREQUENCY",
                score=round(z_score, 2),
                explanation=explanation,
                camera_id=camera_id,
                source_event_ids=source_event_ids or [],
                metric_name="hourly_event_frequency",
                baseline_mean=baseline.mean_value,
                observed_value=observed_count,
            )

            if persist:
                self._save_anomaly(report)

            return report

        return None

    def _save_anomaly(self, report: AnomalyReport) -> None:
        try:
            with get_db() as conn:
                conn.execute(
                    """
                    INSERT INTO anomalies (
                        anomaly_id, anomaly_type, score, explanation, camera_id,
                        source_event_ids_json, metric_name, baseline_mean, observed_value, timestamp
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        report.anomaly_id,
                        report.anomaly_type,
                        report.score,
                        report.explanation,
                        report.camera_id,
                        json.dumps(report.source_event_ids),
                        report.metric_name,
                        report.baseline_mean,
                        report.observed_value,
                        report.timestamp,
                    ),
                )
                conn.commit()
        except Exception as e:
            logger.error(f"Failed to persist anomaly: {e}")

    def list_anomalies(
        self,
        camera_id: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[AnomalyReport]:
        query = "SELECT * FROM anomalies WHERE 1=1"
        params: List[Any] = []
        if camera_id:
            query += " AND camera_id = ?"
            params.append(camera_id)
        query += " ORDER BY timestamp DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        with get_db() as conn:
            cursor = conn.execute(query, tuple(params))
            rows = cursor.fetchall()
            cols = [col[0] for col in cursor.description]
            reports = []
            for row in rows:
                d = dict(zip(cols, row)) if not isinstance(row, dict) else row
                reports.append(
                    AnomalyReport(
                        anomaly_id=d["anomaly_id"],
                        anomaly_type=d["anomaly_type"],
                        score=float(d["score"]),
                        explanation=d["explanation"],
                        camera_id=d.get("camera_id"),
                        source_event_ids=json.loads(d.get("source_event_ids_json") or "[]"),
                        metric_name=d["metric_name"],
                        baseline_mean=float(d.get("baseline_mean", 0.0)),
                        observed_value=float(d.get("observed_value", 0.0)),
                        timestamp=d["timestamp"],
                    )
                )
            return reports


anomaly_detector = AnomalyDetector()
