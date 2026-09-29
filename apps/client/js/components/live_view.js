/**
 * Smart Spectator Client - Live Camera View with AI Overlay
 * Conforms to Sections 38 & 39 of Phase 5 specification.
 */

export function renderLiveView(container, stores, actions, selectedCameraId) {
    const camState = stores.camera.get();
    const sysState = stores.system.get();
    const cameras = camState.cameras || [];

    const activeCam = cameras.find(c => c.camera_id === selectedCameraId) || cameras[0];
    if (!activeCam) {
        container.innerHTML = `
            <div class="empty-state-card">
                <p>No active cameras found.</p>
                <button class="btn btn-primary" id="btn-back-cams">Back to Cameras</button>
            </div>
        `;
        container.querySelector('#btn-back-cams')?.addEventListener('click', () => actions.navigateTo('cameras'));
        return;
    }

    const aiTele = sysState.aiTelemetry || {};
    const camCtx = aiTele.camera_contexts?.[activeCam.camera_id] || {};
    const fps = camCtx.inference_fps || activeCam.target_fps || 30;
    const latency = camCtx.latency_ms || 0;
    const activeTracks = camCtx.active_tracks_count || 0;

    let aiOverlayEnabled = true;

    container.innerHTML = `
        <div class="screen-header">
            <div>
                <h2>Live View: ${activeCam.name}</h2>
                <p class="subtitle">${activeCam.camera_id} • Lens: ${activeCam.lens_facing} • ${activeCam.width}x${activeCam.height}</p>
            </div>
            <div class="actions-row">
                <div class="switch-row">
                    <label for="toggle-ai-overlay"><b>AI Overlay:</b></label>
                    <input type="checkbox" id="toggle-ai-overlay" checked>
                </div>
                <button class="btn btn-secondary" id="btn-live-zones">Configure Zones</button>
                <button class="btn btn-secondary" id="btn-back-grid">Camera Grid</button>
            </div>
        </div>

        <div class="live-layout">
            <div class="live-video-box">
                <div class="video-wrapper">
                    <img id="live-stream-img" src="/api/v1/streams/${activeCam.camera_id}/preview?overlay=true" alt="Live Feed">
                    <div class="live-hud-top">
                        <span class="hud-tag"><span class="pulse-dot"></span> LIVE</span>
                        <span class="hud-tag" id="hud-fps">${fps} FPS</span>
                        <span class="hud-tag">AI Latency: ${latency} ms</span>
                        <span class="hud-tag">Active Tracks: ${activeTracks}</span>
                    </div>
                </div>
            </div>

            <div class="live-telemetry-sidebar">
                <div class="panel">
                    <div class="panel-header">
                        <h3>Stream & Perception Telemetry</h3>
                    </div>
                    <div class="telemetry-table">
                        <div class="telem-row"><span>Camera Status</span><span class="status-pill status-${activeCam.status}">${activeCam.status.toUpperCase()}</span></div>
                        <div class="telem-row"><span>Hardware Node</span><span>${activeCam.device_id || 'Direct'}</span></div>
                        <div class="telem-row"><span>Resolution</span><span>${activeCam.width} × ${activeCam.height}</span></div>
                        <div class="telem-row"><span>Detector Model</span><span>${aiTele.active_model || 'YOLOv8n'}</span></div>
                        <div class="telem-row"><span>Execution Backend</span><span style="color:#38bdf8">${aiTele.active_backend || 'CPU'}</span></div>
                        <div class="telem-row"><span>Tracker</span><span>ByteTrack (Kalman Filter)</span></div>
                        <div class="telem-row"><span>Temporal Classifier</span><span>SpectatorNet v1 (BiGRU)</span></div>
                        <div class="telem-row"><span>Frames Sampled</span><span>${camCtx.frames_sampled || 0}</span></div>
                        <div class="telem-row"><span>Frames Dropped</span><span>${camCtx.frames_dropped || 0}</span></div>
                    </div>
                </div>

                <div class="panel" style="margin-top: 16px;">
                    <div class="panel-header">
                        <h3>Switch Camera</h3>
                    </div>
                    <div class="cam-select-list">
                        ${cameras.map(c => `
                            <button class="cam-select-btn ${c.camera_id === activeCam.camera_id ? 'active' : ''}" data-camera-id="${c.camera_id}">
                                <span>${c.name}</span>
                                <span class="status-pill status-${c.status}">${c.status}</span>
                            </button>
                        `).join('')}
                    </div>
                </div>
            </div>
        </div>
    `;

    const imgEl = container.querySelector('#live-stream-img');
    const toggleEl = container.querySelector('#toggle-ai-overlay');

    toggleEl?.addEventListener('change', (e) => {
        aiOverlayEnabled = e.target.checked;
        imgEl.src = `/api/v1/streams/${activeCam.camera_id}/preview?overlay=${aiOverlayEnabled ? 'true' : 'false'}&t=${Date.now()}`;
    });

    container.querySelector('#btn-back-grid')?.addEventListener('click', () => actions.navigateTo('cameras'));
    container.querySelector('#btn-live-zones')?.addEventListener('click', () => actions.openZoneEditor(activeCam.camera_id));

    container.querySelectorAll('.cam-select-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            const camId = btn.getAttribute('data-camera-id');
            actions.openLiveView(camId);
        });
    });
}
