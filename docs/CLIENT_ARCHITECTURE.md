# Client Application Architecture
## Local Monitoring Single Page Application

---

### 1. Design Overview

The Smart Spectator Client (`apps/client/`) is an operator-focused, local-first web application engineered for maximum reliability, low resource consumption, and rapid interaction.

---

### 2. File Organization

```
apps/client/
├── index.html                   # HTML5 layout shell & navigation structure
├── css/
│   └── styles.css               # Design system: OLED dark theme, flex/grid layouts
└── js/
    ├── app.js                   # Main application orchestrator & hash router
    ├── api.js                   # Fetch-based REST API client with error handling
    ├── ws.js                    # Auto-reconnecting WebSocket client
    ├── state.js                 # Central pub/sub reactive store
    ├── models.js                # JSDoc type definitions
    └── components/              # Self-contained screen view renderers
        ├── dashboard.js         # Operations overview, metrics counters, quick feed
        ├── cameras.js           # Multi-camera matrix view
        ├── live_view.js         # Fullscreen single camera live player + bounding box canvas
        ├── events.js            # Real-time event log with filter controls & actions
        ├── event_detail.js      # Modal inspector for event explanation & video player
        ├── recordings.js        # Video recording browser & player
        ├── zones.js             # Interactive HTML5 Canvas polygon boundary editor
        ├── rules.js             # Automation rule builder & condition toggles
        ├── devices.js           # Android phone pairing & telemetry viewer
        ├── ai_status.js         # NPU/GPU inference latency and FPS charts
        └── settings.js          # Hub configuration & audit logs
```

---

### 3. State Management & Pub/Sub Pattern

`apps/client/js/state.js` implements a lightweight publish-subscribe reactive store:
```javascript
class Store {
  constructor(initialState) {
    this._state = initialState;
    this._listeners = new Set();
  }
  get() { return this._state; }
  set(newState) {
    this._state = { ...this._state, ...newState };
    this._listeners.forEach(fn => fn(this._state));
  }
  subscribe(fn) {
    this._listeners.add(fn);
    return () => this._listeners.delete(fn);
  }
}
```

Components subscribe to updates relevant to their domain (e.g., `eventsStore`, `camerasStore`, `connectionStore`), allowing decoupled re-renders without full-page reloads.

---

### 4. Interactive Canvas Polygon Editor (`zones.js`)

- Real-time drawing over live camera snapshots.
- Mouse/Touch event handlers:
  - Click to add vertex.
  - Hover near first point highlights close-polygon trigger.
  - Double-click closes polygon.
  - Clear, reset, and hex color selection.
- Vertices are automatically normalized to $[0.0, 1.0]$ based on current canvas dimension before persisting to the Hub.

---

### 5. WebSocket Resilience (`ws.js`)

- Establishes connection to `ws://{host}:{port}/api/v1/events/stream`.
- Heartbeat ping-pong every 15 seconds to detect half-open sockets.
- Automatic exponential backoff reconnection:
  $$T_{\text{reconnect}} = \min(30.0, 1.0 \times 1.5^{\text{attempts}})$$
- On reconnect, automatically triggers a REST sync to backfill any events missed during disconnection.
