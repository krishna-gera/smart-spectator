/**
 * Smart Spectator Client - Cameras Grid View
 * Conforms to Section 37 of Phase 5 specification.
 */

export function renderCameras(container, stores, actions) {
    const camState = stores.camera.get();
    const evState = stores.event.get();
    const recState = stores.recording.get();

    const cameras = camState.cameras || [];
    const events = evState.events || [];
    const activeEvents = events.filter(e => e.status === 'active' || e.status === 'confirmed');

    container.innerHTML = `
        <div class="screen-header">
            <div>
                <h2>Cameras (${cameras.length})</h2>
                <p class="subtitle">Multi-stream layout with live preview and active status</p>
            </div>
            <div class="actions-row">
                <button class="btn btn-secondary" id="cam-grid-refresh">Refresh Streams</button>
            </div>
        </div>

        ${cameras.length === 0 ? `
            <div class="empty-state-card">
                <p><b>No Camera Nodes Connected</b></p>
                <p>Pair an Android phone running the Smart Spectator Camera app over the local Wi-Fi.</p>
                <button class="btn btn-primary" id="btn-goto-pair">Open Device Pairing</button>
            </div>
        ` : `
            <div class="camera-adaptive-grid grid-count-${Math.min(cameras.length, 4)}">
                ${cameras.map(c => {
                    const hasActiveEvent = activeEvents.some(e => e.camera_id === c.camera_id);
                    return `
                        <div class="camera-card ${hasActiveEvent ? 'cam-event-active' : ''}">
                            <div class="camera-card-header">
                                <div class="cam-title">
                                    <b>${c.name}</b>
                                    <span class="cam-sub">${c.camera_id} (${c.lens_facing})</span>
                                </div>
                                <div class="cam-indicators">
                                    ${hasActiveEvent ? '<span class="badge badge-high pulse-badge">EVENT</span>' : ''}
                                    <span class="status-pill status-${c.status}">${c.status.toUpperCase()}</span>
                                </div>
                            </div>
                            <div class="camera-preview-frame" data-camera-id="${c.camera_id}">
                                <img src="/api/v1/streams/${c.camera_id}/preview" alt="${c.name}" onerror="this.src='data:image/svg+xml;utf8,<svg xmlns=\\'http://www.w3.org/2000/svg\\' width=\\'640\\' height=\\'360\\'><rect width=\\'100%\\' height=\\'100%\\' fill=\\'%231e293b\\'/><text x=\\'50%\\' y=\\'50%\\' fill=\\'%2364748b\\' text-anchor=\\'middle\\' dy=\\'.3em\\'>Stream Inactive</text></svg>'">
                            </div>
                            <div class="camera-card-footer">
                                <span class="cam-meta-spec">${c.width}x${c.height} • ${c.target_fps} FPS</span>
                                <div class="footer-actions">
                                    <button class="btn btn-small btn-secondary btn-cam-zones" data-camera-id="${c.camera_id}">Zones</button>
                                    <button class="btn btn-small btn-primary btn-cam-live" data-camera-id="${c.camera_id}">Open Live</button>
                                </div>
                            </div>
                        </div>
                    `;
                }).join('')}
            </div>
        `}
    `;

    container.querySelector('#cam-grid-refresh')?.addEventListener('click', () => actions.refreshCameras());
    container.querySelector('#btn-goto-pair')?.addEventListener('click', () => actions.navigateTo('devices'));

    container.querySelectorAll('.camera-preview-frame, .btn-cam-live').forEach(el => {
        el.addEventListener('click', () => {
            const camId = el.getAttribute('data-camera-id');
            actions.openLiveView(camId);
        });
    });

    container.querySelectorAll('.btn-cam-zones').forEach(el => {
        el.addEventListener('click', (e) => {
            e.stopPropagation();
            const camId = el.getAttribute('data-camera-id');
            actions.openZoneEditor(camId);
        });
    });
}
