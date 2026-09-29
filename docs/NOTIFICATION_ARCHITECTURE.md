# Notification Dispatcher & Multi-Tier Cooldown Architecture

## 1. Overview
Smart Spectator features an intelligent notification dispatch system designed to alert operators promptly without inducing notification fatigue during continuous or noisy events.

## 2. Multi-Tier Cooldown Hierarchy

```
                    Incoming Event
                          │
                          ▼
            [ 1. Global Cooldown Check ]
            - Default: 5 seconds between any hub alerts
            - Suppresses barrage when multiple cameras trigger simultaneously
                          │ PASS
                          ▼
            [ 2. Camera-Level Cooldown ]
            - Default: 15 seconds per individual camera
            - Ensures camera-specific throttle
                          │ PASS
                          ▼
          [ 3. Event-Type Cooldown Check ]
            - Default: 60 seconds for identical event_type on same camera
            - Prevents continuous repeated alerts for uninterrupted loitering
                          │ PASS
                          ▼
              [ Dispatch Notification ]
               ├── WebSocket Stream (Broadcast)
               └── Optional Local Webhook / Audit Log
```

## 3. WebSocket Streaming Protocol (Schema 1.2.0)

### Connection
- **Endpoint**: `/api/v1/events/stream`
- **Protocol**: Standard WebSocket (WSS / WS)

### Client Heartbeat
Clients send ping frames to maintain liveness and verify latency:
```json
{
  "type": "ping"
}
```
Hub response:
```json
{
  "type": "pong",
  "schema_version": "1.2.0",
  "timestamp": 1727657280.123
}
```

### Dynamic Subscription Filtering
Monitoring clients can modify their stream subscription filter on the fly without reconnecting:
```json
{
  "type": "subscribe",
  "filter": {
    "min_priority": "HIGH",
    "camera_ids": ["cam-front-door", "cam-vault"],
    "event_types": ["loitering", "zone_intrusion"]
  }
}
```
Hub response:
```json
{
  "type": "subscription_ack",
  "schema_version": "1.2.0",
  "filter": {
    "min_priority": "HIGH",
    "camera_ids": ["cam-front-door", "cam-vault"],
    "event_types": ["loitering", "zone_intrusion"]
  }
}
```
