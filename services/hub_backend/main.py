"""
Smart Spectator - Desktop Hub FastAPI Application Entrypoint
Orchestrates REST endpoints, WebSocket control/stream channels,
SQLite WAL storage, and mDNS zero-configuration discovery.
"""

import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse

from .config import settings
from .database.connection import init_database
from services.device_manager.discovery import hub_advertiser, get_local_ip
from services.stream_engine.server import stream_engine
from services.ai_engine.pipeline import ai_pipeline
from .routes import health, devices, cameras, streams, ai
from .websocket import control


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 1. Startup: Initialize SQLite database in WAL mode
    print("[Hub] Initializing SQLite database...")
    init_database()

    # 2. Startup: Start mDNS Hub Advertisement in background worker thread
    print("[Hub] Starting mDNS service advertisement...")
    await asyncio.to_thread(hub_advertiser.start)

    # 3. Startup: Start dedicated TCP binary media receiver
    print(f"[Hub] Launching dedicated TCP media receiver on {settings.HOST}:{settings.STREAM_PORT}...")
    try:
        await stream_engine.start_tcp_ingest_server(settings.HOST, settings.STREAM_PORT)
    except Exception as e:
        print(f"[Hub] Warning: TCP media receiver failed to bind: {e}")

    # 4. Startup: Launch AI Perception Pipeline
    print("[Hub] Launching AI Perception Pipeline...")
    ai_pipeline.start()

    yield

    # 5. Shutdown: Clean up resources
    print("[Hub] Shutting down AI Perception Pipeline...")
    ai_pipeline.stop()
    print("[Hub] Shutting down mDNS advertiser...")
    await asyncio.to_thread(hub_advertiser.stop)
    if stream_engine.tcp_server:
        stream_engine.tcp_server.close()
        await stream_engine.tcp_server.wait_closed()
    print("[Hub] Shutdown complete.")


app = FastAPI(
    title="Smart Spectator Desktop Hub",
    description="Local-first visual intelligence gateway and camera node manager.",
    version="1.0.0",
    lifespan=lifespan
)

# Enable CORS for local client and mobile dashboards
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register REST & WebSocket API Routers under /api/v1
API_PREFIX = "/api/v1"
app.include_router(health.router, prefix=API_PREFIX)
app.include_router(devices.router, prefix=API_PREFIX)
app.include_router(cameras.router, prefix=API_PREFIX)
app.include_router(streams.router, prefix=API_PREFIX)
app.include_router(control.router, prefix=API_PREFIX)
app.include_router(ai.router, prefix=API_PREFIX)


@app.get("/", response_class=HTMLResponse)
def index_dashboard():
    """Phase 1 Developer Hub Web Dashboard for instant verification."""
    local_ip = get_local_ip()
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Smart Spectator Desktop Hub</title>
    <style>
        :root {{
            --bg-color: #0f172a;
            --card-bg: #1e293b;
            --text-main: #f8fafc;
            --text-dim: #94a3b8;
            --accent: #38bdf8;
            --accent-green: #22c55e;
            --accent-amber: #f59e0b;
            --border: #334155;
        }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            background: var(--bg-color);
            color: var(--text-main);
            margin: 0;
            padding: 24px;
        }}
        .header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            border-bottom: 1px solid var(--border);
            padding-bottom: 16px;
            margin-bottom: 24px;
        }}
        .badge {{
            display: inline-flex;
            align-items: center;
            gap: 6px;
            padding: 4px 10px;
            border-radius: 9999px;
            font-size: 13px;
            font-weight: 600;
            background: rgba(34, 197, 94, 0.15);
            color: var(--accent-green);
        }}
        .pulse {{
            width: 8px;
            height: 8px;
            border-radius: 50%;
            background: var(--accent-green);
            box-shadow: 0 0 10px var(--accent-green);
        }}
        .grid {{
            display: grid;
            grid-template-columns: 320px 1fr;
            gap: 24px;
        }}
        .card {{
            background: var(--card-bg);
            border: 1px solid var(--border);
            border-radius: 12px;
            padding: 20px;
        }}
        .card h2 {{
            font-size: 16px;
            margin-top: 0;
            color: var(--text-dim);
            text-transform: uppercase;
            letter-spacing: 0.05em;
        }}
        .pin-box {{
            background: #090d16;
            border: 1px dashed var(--accent-amber);
            border-radius: 8px;
            padding: 16px;
            text-align: center;
            margin: 12px 0;
        }}
        .pin-code {{
            font-size: 32px;
            font-family: monospace;
            font-weight: 700;
            letter-spacing: 6px;
            color: var(--accent-amber);
        }}
        .video-container {{
            background: #000;
            border-radius: 8px;
            aspect-ratio: 16 / 9;
            display: flex;
            align-items: center;
            justify-content: center;
            overflow: hidden;
            border: 1px solid var(--border);
            position: relative;
        }}
        .video-container img {{
            width: 100%;
            height: 100%;
            object-fit: contain;
        }}
        .video-placeholder {{
            color: var(--text-dim);
            text-align: center;
        }}
        .telemetry-row {{
            display: flex;
            justify-content: space-between;
            padding: 8px 0;
            border-bottom: 1px solid rgba(255,255,255,0.05);
            font-size: 14px;
        }}
    </style>
</head>
<body>
    <div class="header">
        <div>
            <h1 style="margin:0; font-size: 24px;">Smart Spectator Hub</h1>
            <p style="margin: 4px 0 0; color: var(--text-dim); font-size: 13px;">Snapdragon-Powered Local Gateway & Perception Core</p>
        </div>
        <div class="badge"><div class="pulse"></div> Hub Online: {local_ip}:{settings.PORT}</div>
    </div>

    <div class="grid">
        <div>
            <div class="card" style="margin-bottom: 24px;">
                <h2>Active Pairing Requests</h2>
                <div id="pairing-section">
                    <p style="color: var(--text-dim); font-size: 14px;">Awaiting camera node requests...</p>
                </div>
            </div>

            <div class="card">
                <h2>Connected Devices</h2>
                <div id="devices-section">
                    <p style="color: var(--text-dim); font-size: 14px;">No devices connected.</p>
                </div>
            </div>
        </div>

        <div>
            <div class="card">
                <h2>Live Camera Preview</h2>
                <div class="video-container" id="video-box">
                    <div class="video-placeholder">
                        <p style="font-size: 18px; margin: 0 0 8px;">Awaiting Stream Ingestion</p>
                        <p style="font-size: 13px; margin: 0;">Pair an Android node to initiate live H.264 video feed.</p>
                    </div>
                </div>
                <div id="stream-telemetry" style="margin-top: 16px;"></div>
            </div>
        </div>
    </div>

    <script>
        async function refreshDashboard() {{
            try {{
                // 1. Fetch pending pairing PINs
                const pinRes = await fetch('/api/v1/devices/pairing/pending');
                const pins = await pinRes.json();
                const pinDiv = document.getElementById('pairing-section');
                if (pins.length > 0) {{
                    pinDiv.innerHTML = pins.map(p => `
                        <div class="pin-box">
                            <div style="font-size: 12px; color: var(--text-dim);">${{p.device_name}} (${{p.device_model || 'Android'}})</div>
                            <div class="pin-code">${{p.verification_pin}}</div>
                            <div style="font-size: 11px; color: var(--accent-amber);">Enter this 6-digit code on the phone</div>
                        </div>
                    `).join('');
                }} else {{
                    pinDiv.innerHTML = '<p style="color: var(--text-dim); font-size: 14px;">No pending pairing requests.</p>';
                }}

                // 2. Fetch connected devices & cameras
                const devRes = await fetch('/api/v1/devices');
                const devs = await devRes.json();
                const devDiv = document.getElementById('devices-section');
                if (devs.length > 0) {{
                    devDiv.innerHTML = devs.map(d => `
                        <div class="telemetry-row">
                            <span><b>${{d.device_name}}</b></span>
                            <span style="color: ${{d.status === 'connected' ? 'var(--accent-green)' : 'var(--text-dim)'}}">${{d.status.toUpperCase()}}</span>
                        </div>
                        <div class="telemetry-row" style="font-size: 12px; color: var(--text-dim);">
                            <span>Battery: ${{d.battery_level ? d.battery_level + '%' : 'N/A'}}</span>
                            <span>Temp: ${{d.battery_temperature_c ? d.battery_temperature_c + '°C' : 'N/A'}}</span>
                        </div>
                    `).join('');
                }}

                // 3. Fetch active stream
                const strRes = await fetch('/api/v1/streams');
                const streams = await strRes.json();
                const videoBox = document.getElementById('video-box');
                const telemBox = document.getElementById('stream-telemetry');
                if (streams.length > 0) {{
                    const s = streams[0];
                    if (!videoBox.querySelector('img')) {{
                        videoBox.innerHTML = `<img src="/api/v1/streams/${{s.camera_id}}/preview" alt="Live Stream">`;
                    }}
                    telemBox.innerHTML = `
                        <div class="telemetry-row">
                            <span><b>Active Camera:</b> ${{s.camera_id}}</span>
                            <span><b>Throughput:</b> ${{s.fps}} FPS | ${{s.bitrate_kbps}} kbps</span>
                        </div>
                        <div class="telemetry-row">
                            <span><b>Frames Ingested:</b> ${{s.frames_received}}</span>
                            <span><b>Dropped Packets:</b> ${{s.dropped_packets}}</span>
                        </div>
                    `;
                }}
            }} catch(e) {{
                console.error(e);
            }}
        }}

        setInterval(refreshDashboard, 1500);
        refreshDashboard();
    </script>
</body>
</html>
"""
