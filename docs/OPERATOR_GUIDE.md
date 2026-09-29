# Smart Spectator Operator Guide — v1.2.0

## 1. Quick Start
1. **Start the Hub**:
   ```bash
   cd /path/to/smart-spectator
   ./scripts/run_hub.sh
   # On Windows: scripts\run_hub.bat
   ```
2. **Open the Monitoring Client**:
   Navigate to `http://localhost:8000/client/` in any modern web browser (Edge, Chrome, Safari, Firefox).

---

## 2. Operating the Monitoring Client

### Dashboard
- **Live System Telemetry**: Displays connected camera count, active AI pipeline status, current inference latency, and system memory.
- **Recent High-Priority Events**: Highlights events tagged with `CRITICAL` or `HIGH` priority badges.
- **Camera Live Grid**: Shows live frame previews and quick navigation links to individual camera streams.

### Interactive Zone Management
- Select a camera from the dropdown to view its reference frame.
- Click **"Draw New Zone"** and click on the canvas to place vertices.
- Drag existing vertex handles to modify zone boundaries accurately.
- Set Zone Type (`detection`, `exclusion`, `loitering`, `transit`).
- Click **"Save Zone"** to commit the polygon to the hub database.

### Compound Automation Rules
- Construct conditional rules triggering on object classes (`person`, `vehicle`), zone intersections, and temporal actions (`loitering`, `running`).
- Specify dwell duration thresholds (e.g., minimum 5.0 seconds).
- Configure time windows and days of the week when the rule is active.
- Set priority overrides (`CRITICAL`, `HIGH`, `MEDIUM`, `LOW`).

### Forensic Event Analysis & Timelines
- Click any event row to open the **Event Detail Modal**.
- Review the **"Why this event was triggered"** explanation box detailing rule criteria and confidence scores.
- Inspect the **Causal Timeline Milestones** verifying the chronological progression from initial detection to clip persistence.
- Play the event clip directly with native controls or click **"Download MP4"** for local archival.

### Media & Retention Management
- In the **Recordings** tab, toggle the **Lock** button (`🔒 Locked` / `🔓 Unlocked`) to prevent retention pruning from purging critical evidence.
- In **Settings**, inspect the real-time **Storage Space Gauge**.
- Trigger manual retention pruning or adjust retention limits safely.
- Export safe sanitized configurations for backup or multi-station cloning.
