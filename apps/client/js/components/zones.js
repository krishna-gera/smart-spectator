/**
 * Smart Spectator Client - Interactive Polygon Zone Editor
 * Conforms to Section 44 of Phase 5 specification.
 */

export function renderZoneEditor(container, stores, actions, selectedCameraId) {
    const camState = stores.camera.get();
    const zoneState = stores.zone.get();
    const cameras = camState.cameras || [];

    const activeCam = cameras.find(c => c.camera_id === selectedCameraId) || cameras[0];
    if (!activeCam) {
        container.innerHTML = `
            <div class="empty-state-card">
                <p>No camera available to configure zones.</p>
                <button class="btn btn-primary" id="btn-back-cams">View Cameras</button>
            </div>
        `;
        container.querySelector('#btn-back-cams')?.addEventListener('click', () => actions.navigateTo('cameras'));
        return;
    }

    const zones = zoneState.zones[activeCam.camera_id] || [];
    let draftPoints = []; // normalized coordinates [[x, y], ...]

    container.innerHTML = `
        <div class="screen-header">
            <div>
                <h2>Spatial Zone Editor</h2>
                <p class="subtitle">Draw normalized polygon regions of interest on ${activeCam.name}</p>
            </div>
            <div class="actions-row">
                <select id="zone-cam-select">
                    ${cameras.map(c => `<option value="${c.camera_id}" ${c.camera_id === activeCam.camera_id ? 'selected' : ''}>${c.name}</option>`).join('')}
                </select>
                <button class="btn btn-secondary" id="btn-reset-draft">Clear Draft</button>
                <button class="btn btn-primary" id="btn-save-zone">Save Polygon Zone</button>
            </div>
        </div>

        <div class="zone-editor-layout">
            <div class="canvas-container panel">
                <div class="canvas-wrapper" style="position: relative; display: inline-block; width: 100%; aspect-ratio: 16/9; background: #000; border-radius: 8px; overflow: hidden;">
                    <img id="zone-bg-img" src="/api/v1/streams/${activeCam.camera_id}/preview" style="width: 100%; height: 100%; object-fit: contain; display: block;">
                    <canvas id="zone-canvas" style="position: absolute; top: 0; left: 0; width: 100%; height: 100%; cursor: crosshair;"></canvas>
                </div>
                <div class="canvas-instructions">
                    <span>💡 Click points on the video frame to outline your zone (minimum 3 points). Coordinates are automatically normalized to [0.0, 1.0].</span>
                </div>
            </div>

            <div class="zone-sidebar panel">
                <div class="panel-header">
                    <h3>New Zone Details</h3>
                </div>
                <div class="form-group">
                    <label>Zone Name:</label>
                    <input type="text" id="zone-name-input" placeholder="e.g. Front Door, Restricted Desk" class="form-input">
                </div>
                <div class="form-group">
                    <label>Zone Color:</label>
                    <input type="color" id="zone-color-input" value="#38bdf8" class="form-input-color">
                </div>
                <div class="form-group">
                    <label>Points Defined: <b id="point-count">0</b></label>
                </div>

                <div class="panel-header" style="margin-top: 24px;">
                    <h3>Configured Zones (${zones.length})</h3>
                </div>
                <div class="zones-list">
                    ${zones.length === 0 ? '<p class="empty-state">No zones defined yet for this camera.</p>' : ''}
                    ${zones.map(z => `
                        <div class="zone-item-row" data-zone-id="${z.zone_id}">
                            <div class="zone-color-tag" style="background-color: ${z.color || '#38bdf8'};"></div>
                            <div class="zone-info">
                                <b>${z.name}</b>
                                <small>${z.polygon.length} vertices</small>
                            </div>
                            <button class="btn btn-small btn-danger btn-del-zone" data-zone-id="${z.zone_id}">Delete</button>
                        </div>
                    `).join('')}
                </div>
            </div>
        </div>
    `;

    const canvas = container.querySelector('#zone-canvas');
    const ctx = canvas.getContext('2d');
    const img = container.querySelector('#zone-bg-img');
    const pointCountEl = container.querySelector('#point-count');
    const zoneNameInput = container.querySelector('#zone-name-input');
    const zoneColorInput = container.querySelector('#zone-color-input');

    // Resize canvas to match display size
    const resizeCanvas = () => {
        canvas.width = canvas.offsetWidth;
        canvas.height = canvas.offsetHeight;
        drawAll();
    };

    window.addEventListener('resize', resizeCanvas);
    setTimeout(resizeCanvas, 100);

    const drawAll = () => {
        ctx.clearRect(0, 0, canvas.width, canvas.height);
        const w = canvas.width;
        const h = canvas.height;

        // 1. Draw existing zones
        zones.forEach(z => {
            if (!z.polygon || z.polygon.length < 3) return;
            ctx.beginPath();
            ctx.moveTo(z.polygon[0][0] * w, z.polygon[0][1] * h);
            for (let i = 1; i < z.polygon.length; i++) {
                ctx.lineTo(z.polygon[i][0] * w, z.polygon[i][1] * h);
            }
            ctx.closePath();
            ctx.fillStyle = (z.color || '#38bdf8') + '33'; // 20% opacity
            ctx.fill();
            ctx.strokeStyle = z.color || '#38bdf8';
            ctx.lineWidth = 2;
            ctx.stroke();

            // Label
            const cx = z.polygon[0][0] * w;
            const cy = z.polygon[0][1] * h;
            ctx.fillStyle = '#fff';
            ctx.font = '12px sans-serif';
            ctx.fillText(z.name, cx + 5, cy + 15);
        });

        // 2. Draw draft polygon
        if (draftPoints.length > 0) {
            ctx.beginPath();
            ctx.moveTo(draftPoints[0][0] * w, draftPoints[0][1] * h);
            for (let i = 1; i < draftPoints.length; i++) {
                ctx.lineTo(draftPoints[i][0] * w, draftPoints[i][1] * h);
            }
            if (draftPoints.length >= 3) {
                ctx.closePath();
                ctx.fillStyle = (zoneColorInput.value || '#38bdf8') + '44';
                ctx.fill();
            }
            ctx.strokeStyle = zoneColorInput.value || '#38bdf8';
            ctx.lineWidth = 2;
            ctx.setLineDash([4, 4]);
            ctx.stroke();
            ctx.setLineDash([]);

            // Draw vertices
            draftPoints.forEach(pt => {
                ctx.beginPath();
                ctx.arc(pt[0] * w, pt[1] * h, 5, 0, Math.PI * 2);
                ctx.fillStyle = '#fbbf24';
                ctx.fill();
                ctx.strokeStyle = '#000';
                ctx.stroke();
            });
        }
    };

    // Canvas click event to place points
    canvas.addEventListener('click', (e) => {
        const rect = canvas.getBoundingClientRect();
        const normX = Math.max(0, Math.min(1, (e.clientX - rect.left) / rect.width));
        const normY = Math.max(0, Math.min(1, (e.clientY - rect.top) / rect.height));

        draftPoints.push([parseFloat(normX.toFixed(3)), parseFloat(normY.toFixed(3))]);
        pointCountEl.textContent = draftPoints.length;
        drawAll();
    });

    container.querySelector('#btn-reset-draft')?.addEventListener('click', () => {
        draftPoints = [];
        pointCountEl.textContent = 0;
        drawAll();
    });

    container.querySelector('#btn-save-zone')?.addEventListener('click', async () => {
        const name = zoneNameInput.value.trim();
        if (!name) {
            alert('Please enter a zone name.');
            return;
        }
        if (draftPoints.length < 3) {
            alert('Please click at least 3 points to outline a polygon zone.');
            return;
        }

        try {
            await actions.createZone(activeCam.camera_id, {
                name: name,
                polygon: draftPoints,
                color: zoneColorInput.value || '#38bdf8',
                is_active: true
            });
            draftPoints = [];
            zoneNameInput.value = '';
            pointCountEl.textContent = 0;
            await actions.refreshZones(activeCam.camera_id);
            renderZoneEditor(container, stores, actions, activeCam.camera_id);
        } catch (err) {
            alert(`Error saving zone: ${err.message}`);
        }
    });

    container.querySelector('#zone-cam-select')?.addEventListener('change', (e) => {
        actions.openZoneEditor(e.target.value);
    });

    container.querySelectorAll('.btn-del-zone').forEach(btn => {
        btn.addEventListener('click', async () => {
            const zid = btn.getAttribute('data-zone-id');
            if (confirm('Delete this zone?')) {
                await actions.deleteZone(zid);
                await actions.refreshZones(activeCam.camera_id);
                renderZoneEditor(container, stores, actions, activeCam.camera_id);
            }
        });
    });
}
