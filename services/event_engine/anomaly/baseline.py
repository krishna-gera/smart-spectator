"""
Smart Spectator - Statistical Baseline Engine
Conforms to Section 8 of Phase 10 Specification.
Computes and maintains local behavioral baselines (mean, median, stddev)
using pure statistical methods. 100% local, zero cloud dependencies.
"""

from dataclasses import dataclass, asdict
from datetime import datetime, timezone, timedelta
import logging
import math
from typing import Dict, Any, List, Optional
import uuid

from services.hub_backend.database.connection import get_db

logger = logging.getLogger("BaselineEngine")


@dataclass
class BaselineProfile:
    baseline_id: str
    metric_name: str
    camera_id: Optional[str]
    hour_of_day: Optional[int]
    day_of_week: Optional[int]
    sample_count: int
    mean_value: float
    std_dev: float
    median_value: float
    min_value: float
    max_value: float
    last_updated: str


class BaselineEngine:
    """
    Computes rolling behavioral baselines from historical event frequencies.
    Runs asynchronously/in background to avoid degrading real-time vision pipelines.
    """

    def compute_hourly_frequency_baselines(
        self,
        camera_id: Optional[str] = None,
        lookback_days: int = 14,
        persist: bool = True,
    ) -> List[BaselineProfile]:
        """
        Calculates hourly event frequency distribution (events/hour) for each hour (0..23).
        """
        since_dt = datetime.now(timezone.utc) - timedelta(days=lookback_days)
        since_str = since_dt.isoformat()

        # Query events bucketed by date and hour
        query = """
        SELECT DATE(timestamp) as dt,
               CAST(strftime('%H', timestamp) AS INTEGER) as hr,
               COUNT(*) as hourly_count
        FROM events
        WHERE timestamp >= ?
        """
        params: List[Any] = [since_str]
        if camera_id:
            query += " AND camera_id = ?"
            params.append(camera_id)
        query += " GROUP BY dt, hr"

        hour_samples: Dict[int, List[float]] = {h: [] for h in range(24)}

        with get_db() as conn:
            cursor = conn.execute(query, tuple(params))
            for row in cursor.fetchall():
                hr = row[1] if not isinstance(row, dict) else row["hr"]
                cnt = float(row[2] if not isinstance(row, dict) else row["hourly_count"])
                if 0 <= hr < 24:
                    hour_samples[hr].append(cnt)

        profiles: List[BaselineProfile] = []
        now_str = datetime.now(timezone.utc).isoformat()

        for hr, samples in hour_samples.items():
            n = len(samples)
            if n == 0:
                mean_v = 0.0
                std_v = 0.5  # Small default prior to prevent division by zero
                median_v = 0.0
                min_v = 0.0
                max_v = 0.0
            else:
                mean_v = sum(samples) / n
                variance = sum((x - mean_v) ** 2 for x in samples) / max(1, n - 1) if n > 1 else 0.0
                std_v = math.sqrt(variance)
                sorted_s = sorted(samples)
                median_v = sorted_s[n // 2]
                min_v = sorted_s[0]
                max_v = sorted_s[-1]

            # Ensure minimum non-zero standard deviation for stability
            std_v = max(std_v, 0.5)

            p_id = f"base_hr_{hr}_{camera_id or 'all'}"
            profile = BaselineProfile(
                baseline_id=p_id,
                metric_name="hourly_event_frequency",
                camera_id=camera_id,
                hour_of_day=hr,
                day_of_week=None,
                sample_count=n,
                mean_value=round(mean_v, 3),
                std_dev=round(std_v, 3),
                median_value=round(median_v, 3),
                min_value=round(min_v, 3),
                max_value=round(max_v, 3),
                last_updated=now_str,
            )
            profiles.append(profile)

        if persist:
            self._save_baselines(profiles)

        return profiles

    def get_baseline(
        self,
        metric_name: str,
        camera_id: Optional[str] = None,
        hour_of_day: Optional[int] = None,
    ) -> Optional[BaselineProfile]:
        query = "SELECT * FROM statistical_baselines WHERE metric_name = ?"
        params: List[Any] = [metric_name]
        if camera_id:
            query += " AND camera_id = ?"
            params.append(camera_id)
        else:
            query += " AND camera_id IS NULL"
        if hour_of_day is not None:
            query += " AND hour_of_day = ?"
            params.append(hour_of_day)

        with get_db() as conn:
            cursor = conn.execute(query, tuple(params))
            row = cursor.fetchone()
            if not row:
                return None
            cols = [col[0] for col in cursor.description]
            d = dict(zip(cols, row)) if not isinstance(row, dict) else row
            return BaselineProfile(**d)

    def _save_baselines(self, profiles: List[BaselineProfile]) -> None:
        try:
            with get_db() as conn:
                for p in profiles:
                    conn.execute(
                        """
                        INSERT OR REPLACE INTO statistical_baselines (
                            baseline_id, metric_name, camera_id, hour_of_day, day_of_week,
                            sample_count, mean_value, std_dev, median_value, min_value,
                            max_value, last_updated
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            p.baseline_id,
                            p.metric_name,
                            p.camera_id,
                            p.hour_of_day,
                            p.day_of_week,
                            p.sample_count,
                            p.mean_value,
                            p.std_dev,
                            p.median_value,
                            p.min_value,
                            p.max_value,
                            p.last_updated,
                        ),
                    )
                conn.commit()
        except Exception as e:
            logger.error(f"Failed to persist baselines: {e}")


baseline_engine = BaselineEngine()
