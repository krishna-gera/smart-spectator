# Event Intelligence & Forensic Attribution — v1.2.0

## 1. Deterministic Prioritization Engine

Smart Spectator calculates event priority through deterministic business logic, avoiding subjective or unpredictable heuristic scoring.

### Priority Levels

| Priority | Criteria | Example Event Types |
|---|---|---|
| **CRITICAL** | Security perimeter breach, unauthorized entry in high-security zone outside permitted schedule, rapid running motion combined with loitering | Perimeter Breach, Active Intrusion, Forced Boundary Crossing |
| **HIGH** | Loitering duration exceeding threshold in monitored zones, loitering in exclusion zones, directional tripwire violations | Extended Loitering, Restricted Zone Presence |
| **MEDIUM** | Standard person/vehicle detection in active monitored zone during business hours, brief loitering below threshold | Person in Zone, Vehicle Transit |
| **LOW** | Routine scene motion, object tracking without zone rule violation, transient crossings | Background Motion, Tracking Active |

### Priority Calculation Factors
The `calculate_event_priority()` function assesses:
1. **Rule Overrides**: If the triggered rule specifies an explicit priority override (`CRITICAL`, `HIGH`, etc.), that priority is honored immediately.
2. **Zone Type**: Events inside `exclusion` zones automatically elevate to at least `HIGH`, and during off-hours elevate to `CRITICAL`.
3. **Temporal Classification**: SpectatorNet action classifications (`running`, `loitering`, `pacing`) combined with dwell duration determine severity adjustments.
4. **AI Confidence**: High-confidence detections (>0.85) in sensitive zones maintain elevated priority.

---

## 2. Causal Timeline Milestones

Every event generated in Version 1.2.0 produces an immutable sequence of forensic milestones with real ISO-8601 timestamps:

```
[00:00:00.000] milestone: person_detected
               Actor first identified in camera field of view (Track ID: #42, Conf: 0.91)
      │
      ▼
[00:00:01.420] milestone: zone_entered
               Spatial boundary intersection detected in 'Server Room Vault'
      │
      ▼
[00:00:04.500] milestone: temporal_pattern_detected
               SpectatorNet classified recurrent sequence as 'loitering' (p=0.88)
      │
      ▼
[00:00:10.050] milestone: rule_condition_met
               Rule 'Vault Off-Hours Dwell' duration threshold (10.0s) exceeded
      │
      ▼
[00:00:10.100] milestone: event_confirmed
               Event #EV-1049 registered with priority CRITICAL
      │
      ▼
[00:00:10.250] milestone: recording_persisted
               Fragmented MP4 clip packaged (pre-roll: 5s, clip_id: REC-9021)
```

Operators inspecting events via the Monitoring Client can review the complete timeline to understand the causal chain behind each notification.
