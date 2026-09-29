/**
 * Smart Spectator Client - Device Management Component
 * Conforms to Section 46 of Phase 5 specification.
 */

export function renderDevices(container, stores, actions) {
    const devState = stores.device.get();
    const devices = devState.devices || [];
    const pending = devState.pendingPairings || [];

    container.innerHTML = `
        <div class="screen-header">
            <div>
                <h2>Device Registry (${devices.length})</h2>
                <p class="subtitle">Paired Android camera nodes, battery telemetry, and local pairing requests</p>
            </div>
            <div class="actions-row">
                <button class="btn btn-secondary" id="btn-refresh-devs">Refresh</button>
            </div>
        </div>

        ${pending.length > 0 ? `
            <div class="panel pairing-alert-panel">
                <div class="panel-header">
                    <h3 style="color: #f59e0b;">⏳ Pending Camera Pairing Requests (${pending.length})</h3>
                </div>
                <div class="pairing-grid">
                    ${pending.map(p => `
                        <div class="pin-approval-card">
                            <div>
                                <b>${p.device_name}</b> (${p.device_model || 'Android'})
                                <div style="color: #94a3b8; font-size: 0.85rem;">Device ID: ${p.device_id}</div>
                            </div>
                            <div class="pin-display">${p.verification_pin}</div>
                            <small style="color: #f59e0b;">Enter this 6-digit PIN on the phone to complete pairing</small>
                        </div>
                    `).join('')}
                </div>
            </div>
        ` : ''}

        <div class="panel devices-table-panel">
            <div class="panel-header">
                <h3>Authorized Camera Nodes</h3>
            </div>
            ${devices.length === 0 ? `
                <div class="empty-state">
                    <p>No paired devices found.</p>
                    <small style="color: #94a3b8;">Launch the Smart Spectator Android Camera app on your phone on this local network to pair.</small>
                </div>
            ` : `
                <table class="data-table">
                    <thead>
                        <tr>
                            <th>Device Label</th>
                            <th>Status</th>
                            <th>IP Address</th>
                            <th>Battery</th>
                            <th>Temperature</th>
                            <th>App Build</th>
                            <th>Last Seen</th>
                            <th>Actions</th>
                        </tr>
                    </thead>
                    <tbody>
                        ${devices.map(d => `
                            <tr>
                                <td>
                                    <b>${d.device_name}</b><br>
                                    <small style="color: #94a3b8;">${d.device_id}</small>
                                </td>
                                <td><span class="status-pill status-${d.status}">${d.status.toUpperCase()}</span></td>
                                <td><code>${d.ip_address || 'Local Wi-Fi'}</code></td>
                                <td>${d.battery_level !== null && d.battery_level !== undefined ? d.battery_level + '%' + (d.is_charging ? ' ⚡' : '') : 'N/A'}</td>
                                <td>${d.battery_temperature_c !== null && d.battery_temperature_c !== undefined ? d.battery_temperature_c + '°C' : 'N/A'}</td>
                                <td>${d.app_version || '1.0.0'}</td>
                                <td>${new Date(d.last_seen).toLocaleTimeString()}</td>
                                <td>
                                    <button class="btn btn-small btn-danger btn-revoke-dev" data-dev-id="${d.device_id}">Revoke</button>
                                </td>
                            </tr>
                        `).join('')}
                    </tbody>
                </table>
            `}
        </div>
    `;

    container.querySelector('#btn-refresh-devs')?.addEventListener('click', () => actions.refreshDevices());

    container.querySelectorAll('.btn-revoke-dev').forEach(btn => {
        btn.addEventListener('click', async () => {
            const devId = btn.getAttribute('data-dev-id');
            if (confirm(`Revoke authorization for '${devId}'?`)) {
                await actions.revokeDevice(devId);
                await actions.refreshDevices();
                renderDevices(container, stores, actions);
            }
        });
    });
}
