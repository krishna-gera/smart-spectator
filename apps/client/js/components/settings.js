/**
 * Smart Spectator Client - Settings & Configuration Component
 * Conforms to Section 49 of Phase 5 specification.
 */

export function renderSettings(container, stores, actions) {
    const connState = stores.connection.get();
    const currentBaseUrl = localStorage.getItem('ss_hub_url') || window.location.origin;

    container.innerHTML = `
        <div class="screen-header">
            <div>
                <h2>Settings & Preferences</h2>
                <p class="subtitle">Local-first node parameters, recording retention limits, and storage quotas</p>
            </div>
            <div class="actions-row">
                <button class="btn btn-primary" id="btn-save-settings">Save Changes</button>
            </div>
        </div>

        <div class="settings-grid">
            <div class="panel">
                <div class="panel-header">
                    <h3>Hub Connection</h3>
                </div>
                <div class="form-group">
                    <label>Hub Endpoint Address:</label>
                    <input type="text" id="settings-hub-url" value="${currentBaseUrl}" class="form-input">
                    <small style="color: #94a3b8;">Format: <code>http://&lt;hub-ip&gt;:8000</code>. Leave blank for auto-origin.</small>
                </div>
                <div class="form-group">
                    <label>Connection Status:</label>
                    <div><span class="status-pill status-${connState.status}">${connState.status.toUpperCase()}</span></div>
                </div>
            </div>

            <div class="panel">
                <div class="panel-header">
                    <h3>Storage Quota & Retention</h3>
                </div>
                <div class="form-group">
                    <label>Maximum Recordings Storage (GB):</label>
                    <input type="number" id="settings-max-storage" value="10" min="1" max="1000" class="form-input">
                    <small style="color: #94a3b8;">Oldest clips automatically purge when quota is exceeded.</small>
                </div>
                <div class="form-group">
                    <label>Retention Window (Days):</label>
                    <input type="number" id="settings-retention-days" value="14" min="1" max="365" class="form-input">
                    <small style="color: #94a3b8;">Clips older than this window are safely removed.</small>
                </div>
            </div>

            <div class="panel">
                <div class="panel-header">
                    <h3>Event Perception Defaults</h3>
                </div>
                <div class="form-group">
                    <label>Default Confirmation Threshold:</label>
                    <select id="settings-confirm-thresh" class="form-select">
                        <option value="0.75">75% Confidence</option>
                        <option value="0.80" selected>80% Confidence (Standard)</option>
                        <option value="0.85">85% Confidence</option>
                        <option value="0.90">90% Confidence (Strict)</option>
                    </select>
                </div>
                <div class="form-group">
                    <label>Default Event Cooldown (Seconds):</label>
                    <input type="number" id="settings-cooldown" value="15" min="1" max="600" class="form-input">
                </div>
            </div>

            <div class="panel">
                <div class="panel-header">
                    <h3>UI & Notifications</h3>
                </div>
                <div class="form-group">
                    <label>Display Theme:</label>
                    <select id="settings-theme" class="form-select">
                        <option value="dark" selected>Spectator Dark (OLED Optimized)</option>
                        <option value="light">Daylight Light</option>
                    </select>
                </div>
                <div class="form-group">
                    <label>In-App Audio Alert:</label>
                    <input type="checkbox" id="settings-audio-alert">
                    <label for="settings-audio-alert" style="display:inline; margin-left: 4px;">Chime on Critical & High events</label>
                </div>
            </div>
        </div>
    `;

    container.querySelector('#btn-save-settings')?.addEventListener('click', () => {
        const hubUrl = container.querySelector('#settings-hub-url').value.trim();
        if (hubUrl) {
            localStorage.setItem('ss_hub_url', hubUrl);
            actions.updateHubUrl(hubUrl);
        }
        alert('Settings saved locally.');
    });
}
