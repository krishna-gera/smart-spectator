"""
Smart Spectator - Human Feedback Collection
Conforms to Section 24 of Phase 10 Specification.
Collects and tracks operator validation ratings (CORRECT, INCORRECT, NOT_SURE) locally.
"""

from dataclasses import dataclass, asdict
from datetime import datetime, timezone
import logging
from typing import Dict, Any, List, Optional
import uuid

from services.hub_backend.database.connection import get_db

logger = logging.getLogger("HumanFeedback")


class HumanFeedbackManager:
    """Manages local operator feedback on automated event classifications."""

    ALLOWED_RATINGS = {"CORRECT", "INCORRECT", "NOT_SURE"}

    def record_feedback(
        self,
        event_id: str,
        feedback: str,
        notes: Optional[str] = None,
        model_version: Optional[str] = "spectatornet_v1_int8",
        operator_id: str = "operator",
    ) -> Dict[str, Any]:
        rating = feedback.strip().upper()
        if rating not in self.ALLOWED_RATINGS:
            raise ValueError(f"Feedback must be one of {self.ALLOWED_RATINGS}; got '{feedback}'.")

        feedback_id = f"fb_{uuid.uuid4().hex[:12]}"
        now_str = datetime.now(timezone.utc).isoformat()

        with get_db() as conn:
            conn.execute(
                """
                INSERT INTO human_feedback (
                    feedback_id, event_id, feedback, notes, model_version, operator_id, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (feedback_id, event_id, rating, notes, model_version, operator_id, now_str),
            )
            conn.commit()

        return {
            "feedback_id": feedback_id,
            "event_id": event_id,
            "feedback": rating,
            "notes": notes,
            "model_version": model_version,
            "created_at": now_str,
        }

    def list_feedback(
        self,
        event_id: Optional[str] = None,
        rating: Optional[str] = None,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        query = "SELECT * FROM human_feedback WHERE 1=1"
        params: List[Any] = []
        if event_id:
            query += " AND event_id = ?"
            params.append(event_id)
        if rating:
            query += " AND feedback = ?"
            params.append(rating.upper())
        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)

        with get_db() as conn:
            cursor = conn.execute(query, tuple(params))
            rows = cursor.fetchall()
            cols = [col[0] for col in cursor.description]
            return [dict(zip(cols, r)) if not isinstance(r, dict) else r for r in rows]

    def get_accuracy_summary(self) -> Dict[str, Any]:
        with get_db() as conn:
            cursor = conn.execute(
                """
                SELECT feedback, COUNT(*) as count
                FROM human_feedback
                GROUP BY feedback
                """
            )
            rows = cursor.fetchall()
            counts = {r[0] if not isinstance(r, dict) else r["feedback"]: r[1] if not isinstance(r, dict) else r["count"] for r in rows}
            total = sum(counts.values())
            correct = counts.get("CORRECT", 0)
            acc = round((correct / total) * 100.0, 2) if total > 0 else 0.0
            return {
                "total_ratings": total,
                "ratings_breakdown": counts,
                "operator_confirmed_accuracy_pct": acc,
            }


feedback_manager = HumanFeedbackManager()
