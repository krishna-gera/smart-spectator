/**
 * Smart Spectator Client - Dashboard Component
 * Conforms to Section 36 of Phase 5 specification.
 */

export function renderDashboard(container, stores, actions) {
    const sysState = stores.system.get();
    const camState = stores.camera.get();
    const evState = stores.event.get();
    const recState = stores.recording.get();

    const cameras = camState.cameras || [];
    const activeCameras = cameras.filter(c => c.status === 'streaming');
    const events = evState.events || [];
    const activeEvents = events.filter(e => e.status === 'active' || e.status === 'confirmed');
    const recordings = recState.recordings || [];

    // AI Provider info (Distinguish actual provider vs unavailable provider, Section 36)
    const aiTele = sysState.aiTelemetry || {};
    const rawBackend = aiTele.active_backend || 'CPU';
    let aiProviderLabel = 'CPU';
    let isNpu = false;
    if (rawBackend.toLowerCase().includes('qnn')) {
        aiProviderLabel = 'Snapdragon NPU (QNN Direct)';
        isNpu = true;
    } else if (rawBackend.toLowerCase().includes('coreml')) {
        aiProviderLabel = 'Apple Silicon GPU (CoreML)';
    } else if (rawBackend.toLowerCase().includes('directml')) {
        aiProviderLabel = 'DirectML GPU';
    } else {
        aiProviderLabel = 'Host CPU (Local Fallback)';
    }

    const aiStatus = (sysState.componentHealth?.components?.ai_engine === 'healthy') ? 'Running' : 'Degraded';
    const eeStatus = (sysState.componentHealth?.components?.event_engine === 'healthy') ? 'Active' : 'Degraded';

    container.innerHTML = `
        <div class="screen-header">
            <div>
                <h2>Intelligence Overview</h2>
                <p class="subtitle">Real-time local perceptual awareness & monitoring metrics</p>
            </div>
            <div class="actions-row">
                <button class="btn btn-secondary" id="btn-refresh-dashboard">Refresh</button>
            </div>
        </div>

        <div class="metrics-grid">
            <div class="metric-card">
                <div class="metric-label">Connected Cameras</div>
                <div class="metric-value">${cameras.length}</div>
                <div class="metric-sub">${activeCameras.length} active streams</div>
            </div>
            <div class="metric-card ${activeEvents.length > 0 ? 'card-alert' : ''}">
                <div class="metric-label">Active Events</div>
                <div class="metric-value">${activeEvents.length}</div>
                <div class="metric-sub">${events.length} total historical</div>
            </div>
            <div class="metric-card">
                <div class="metric-label">Local Recordings</div>
                <div class="metric-value">${recordings.length}</div>
                <div class="metric-sub">Rolling ring buffer protected</div>
            </div>
            <div class="metric-card">
                <div class="metric-label">Perception Engine</div>
                <div class="metric-value" style="font-size: 1.15rem; color: #38bdf8;">${aiProviderLabel}</div>
                <div class="metric-sub">AI: ${aiStatus} | Event Engine: ${eeStatus}</div>
            </div>
        </div>

        <div class="dashboard-split">
            <div class="panel">
                <div class="panel-header">
                    <h3>Active & Recent Events</h3>
                    <button class="btn-text" id="dash-view-all-events">View All &rarr;</button>
                </div>
                <div class="event-feed-list">
                    ${events.length === 0 ? '<p class="empty-state">No events recorded yet. AI perception is actively monitoring streams.</p>' : ''}
                    ${events.slice(0, 5).map(ev => `
                        <div class="feed-event-item severity-${ev.severity}" data-event-id="${ev.event_id}">
                            <div class="event-item-badge badge-${ev.severity}">${ev.severity.toUpperCase()}</div>
                            <div class="event-item-body">
                                <div class="event-item-title">
                                    <b>${ev.event_type.replace(/_/g, ' ')}</b>
                                    <span class="event-time">${new Date(ev.timestamp).toLocaleTimeString()}</span>
                                </div>
                                <div class="event-item-summary">${ev.explanation || ev.summary}</div>
                                <div class="event-item-meta">
                                    <span>Camera: ${ev.camera_id}</span>
                                    <span>Confidence: ${Math.round(ev.confidence * 100)}%</span>
                                    <span class="status-pill status-${ev.status}">${ev.status.toUpperCase()}</span>
                                </div>
                            </div>
                        </div>
                    `).join('')}
                </div>
            </div>

            <div class="panel">
                <div class="panel-header">
                    <h3>Camera Grid Quick View</h3>
                    <button class="btn-text" id="dash-view-cameras">Manage &rarr;</button>
                </div>
                <div class="dash-cam-mini-grid">
                    ${cameras.length === 0 ? '<p class="empty-state">No cameras paired. Open Devices to pair an Android node.</p>' : ''}
                    ${cameras.map(c => `
                        <div class="dash-cam-card" data-camera-id="${c.camera_id}">
                            <div class="dash-cam-preview">
                                <img src="/api/v1/streams/${c.camera_id}/preview" alt="${c.name}" onerror="this.src='data:image/svg+xml;utf8,<svg xmlns=\\'http://www.w3.org/2000/svg\\' width=\\'320\\' height=\\'180\\'><rect width=\\'100%\\' height=\\'100%\\' fill=\\'%231e293b\\'/><text x=\\'50%\\' y=\\'50%\\' fill=\\'%2364748b\\' text-anchor=\\'middle\\' dy=\\'.3em\\'>No Video Feed</text></svg>'">
                                <span class="cam-status-pill status-${c.status}">${c.status.toUpperCase()}</span>
                            </div>
                            <div class="dash-cam-info">
                                <b>${c.name}</b>
                                <span>${c.width}x${c.height} @ ${c.target_fps} FPS</span>
                            </div>
                        </div>
                    `).join('')}
                </div>
            </div>
        </div>
    `;

    // Event listeners
    container.querySelector('#btn-refresh-dashboard')?.addEventListener('click', () => actions.refreshAll());
    container.querySelector('#dash-view-all-events')?.addEventListener('click', () => actions.navigateTo('events'));
    container.querySelector('#dash-view-cameras')?.addEventListener('click', () => actions.navigateTo('cameras'));

    container.querySelectorAll('.feed-event-item').forEach(el => {
        el.addEventListener('click', () => {
            const evId = el.getAttribute('data-event-id');
            actions.openEventDetail(evId);
        });
    });

    container.querySelectorAll('.dash-cam-card').forEach(el => {
        el.addEventListener('click', () => {
            const camId = el.getAttribute('data-camera-id');
            actions.openLiveView(camId);
        });
    });
}
