"""
Smart Spectator - Local Query Interpreter
Conforms to Section 13 of Phase 10 Specification.
Deterministic, offline natural-language command interpreter converting operator
query phrases into validated StructuredQuery objects without any cloud LLMs.
"""

from datetime import datetime, timezone, timedelta
import re
from typing import Optional

from services.hub_backend.query.models import StructuredQuery


class LocalQueryInterpreter:
    """
    Interprets natural language operator queries into structured query objects
    using deterministic semantic regex matchers.
    Zero cloud or external network calls.
    """

    def interpret(self, query_text: str) -> StructuredQuery:
        text = query_text.strip().lower()
        now = datetime.now(timezone.utc)
        today_date = now.strftime("%Y-%m-%d")

        sq = StructuredQuery(raw_query_text=query_text)

        # 1. Check for anomaly queries
        if any(w in text for w in ["anomaly", "anomalies", "unusual", "outlier"]):
            sq.is_anomaly = True

        # 2. Check for priority
        if "critical" in text:
            sq.priority = "CRITICAL"
        elif "high" in text:
            sq.priority = "HIGH"
        elif "medium" in text:
            sq.priority = "MEDIUM"
        elif "low" in text:
            sq.priority = "LOW"

        # 3. Check for event types
        if any(w in text for w in ["person enter", "entered", "entry", "entries"]):
            sq.event_type = "person_entered"
        elif "person left" in text or "exit" in text:
            sq.event_type = "person_left"
        elif "loiter" in text:
            sq.event_type = "loitering_detected"
        elif "object remov" in text or "removed" in text:
            sq.event_type = "object_removed"
        elif "block" in text or "tamper" in text:
            sq.event_type = "camera_blocked"
        elif "motion" in text:
            sq.event_type = "motion_detected"

        # 4. Check for recordings
        if any(w in text for w in ["recording", "video", "clip"]):
            sq.has_recording = True

        # 5. Check for dates
        if "today" in text:
            sq.after = f"{today_date}T00:00:00"
        elif "yesterday" in text:
            yst = (now - timedelta(days=1)).strftime("%Y-%m-%d")
            sq.after = f"{yst}T00:00:00"
            sq.before = f"{yst}T23:59:59"

        # 6. Check for time clauses (e.g. "after 10pm", "after 22:00", "after 8 pm")
        time_match = re.search(r"\bafter\s+(\d{1,2})(?::(\d{2}))?\s*(am|pm)?\b", text)
        if time_match:
            hr = int(time_match.group(1))
            mn = int(time_match.group(2) or 0)
            ampm = time_match.group(3)
            if ampm == "pm" and hr < 12:
                hr += 12
            elif ampm == "am" and hr == 12:
                hr = 0
            # If no date was set, default date to today
            base_date = (sq.after[:10] if sq.after else today_date)
            sq.after = f"{base_date}T{hr:02d}:{mn:02d}:00"

        # 7. Check for camera references (e.g. "camera front_door", "on front_door", "on camera cam-1")
        cam_match = re.search(r"\b(?:on camera|camera|on)\s+([a-zA-Z0-9_\-]+)\b", text)
        if cam_match:
            cand = cam_match.group(1)
            if cand not in ["today", "yesterday", "critical", "high", "medium", "low", "camera", "person", "entries"]:
                sq.camera_id = cand

        return sq


query_interpreter = LocalQueryInterpreter()
