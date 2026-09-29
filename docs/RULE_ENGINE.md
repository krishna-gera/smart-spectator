# Rule Engine Specification & Automation Architecture
## Smart Spectator Event Rule Evaluation

---

### 1. Overview

The `RuleEngine` (`services/event_engine/rules.py`) allows operators to define deterministic automation rules that trigger specific actions when perception events meet user criteria.

---

### 2. Rule Schema

Stored in the `event_rules` table and modeled via `EventRule` in `shared/schemas/v1/models.py`:

```json
{
  "rule_id": "rule_front_door_night",
  "name": "Front Door Overnight Intrusion",
  "is_active": true,
  "condition": {
    "camera_id": "cam_front_door",
    "event_type": "PERSON_ENTERED",
    "zone_id": "zone_porch",
    "min_confidence": 0.75,
    "time_window": {
      "start": "22:00",
      "end": "06:00",
      "days_of_week": [0, 1, 2, 3, 4, 5, 6]
    }
  },
  "actions": [
    "CREATE_EVENT",
    "SAVE_CLIP",
    "CLIENT_NOTIFICATION",
    "LOG_EVENT"
  ],
  "severity_override": "high",
  "cooldown_seconds": 60.0
}
```

---

### 3. Evaluation Pipeline

For every confirmed event candidate:

1. **Active Check:** Ignored if `is_active` is `false`.
2. **Camera Matching:** Optional wildcard (`null` or `""`) or explicit camera match.
3. **Event Type Matching:** Exact match against `event_type`.
4. **Confidence Threshold:** Candidate confidence must be $\ge$ `rule.condition.min_confidence`.
5. **Zone Matching:** If specified, candidate's `zone_id` must match.
6. **Time-of-Day Evaluation:**
   - Evaluated using `is_time_in_range(now_time, start_str, end_str)`.
   - **Overnight Wrap-around Handling:** When `start > end` (e.g. `22:00` to `06:00`), the condition evaluates to true if `now >= start` OR `now <= end`.
   - Normal windows (e.g. `09:00` to `17:00`) evaluate as `start <= now <= end`.
7. **Day-of-Week Matching:** Evaluated against `datetime.weekday()` (Monday = 0, Sunday = 6).
8. **Cooldown Check:** Evaluated against the rule's specific cooldown window.

---

### 4. Pluggable Actions (`services/event_engine/actions.py`)

- `CREATE_EVENT`: Persists the event in the SQLite database and pushes to the active memory table.
- `SAVE_CLIP`: Triggers pre/post-roll MP4 clip capture in `RecordingManager`.
- `CLIENT_NOTIFICATION`: Broadcasts a high-priority alert over the WebSocket connection to all connected monitoring clients.
- `LOG_EVENT`: Records an immutable audit log entry in the `audit_logs` table.
