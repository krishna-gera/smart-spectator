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
                <h2>Settings & Platform Management</h2>
                <p class="subtitle">Categorized system configuration, storage retention, database maintenance, and operator audit trail</p>
            </div>
            <div class="actions-row">
                <button class="btn btn-secondary" id="btn-export-config">Export Config (Safe)</button>
                <label class="btn btn-secondary" style="cursor: pointer; margin-bottom: 0;">
                    Import Config <input type="file" id="file-import-config" accept=".json" style="display: none;">
                </label>
                <button class="btn btn-primary" id="btn-save-settings">Save Settings</button>
            </div>
        </div>

        <div class="storage-gauge-container">
            <div style="display: flex; justify-content: space-between; align-items: center;">
                <div>
                    <h3 style="margin-bottom: 4px;">Local Storage & Retention Lifecycle</h3>
                    <p style="font-size: 0.8rem; color: var(--text-dim);">Automated pruning maintains ring buffer quota while preserving locked evidence</p>
                </div>
                <div>
                    <button class="btn btn-secondary btn-small" id="btn-run-retention">Run Retention Prune</button>
                    <button class="btn btn-primary btn-small" id="btn-backup-db">Backup Database</button>
                </div>
            </div>
            <div class="storage-bar-track">
                <div id="storage-bar-recs" class="storage-bar-recordings" style="width: 15%;"></div>
                <div id="storage-bar-db" class="storage-bar-database" style="width: 5%;"></div>
            </div>
            <div class="storage-stats-grid">
                <div><small style="color: var(--text-muted);">Total Disk Space</small><div id="st-total" style="font-weight: 600;">--</div></div>
                <div><small style="color: var(--accent-blue);">Recordings Directory</small><div id="st-recs" style="font-weight: 600;">--</div></div>
                <div><small style="color: var(--accent-purple);">Database Size</small><div id="st-db" style="font-weight: 600;">--</div></div>
                <div><small style="color: var(--accent-green);">Available Free Space</small><div id="st-free" style="font-weight: 600;">--</div></div>
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
                    <h3>Storage Quota & Retention Policy</h3>
                </div>
                <div class="form-group">
                    <label>Maximum Recordings Storage (GB):</label>
                    <input type="number" id="settings-max-storage" value="10" min="1" max="1000" class="form-input">
                    <small style="color: #94a3b8;">Unlocked clips purge when storage threshold is reached.</small>
                </div>
                <div class="form-group">
                    <label>Retention Window (Days):</label>
                    <input type="number" id="settings-retention-days" value="14" min="1" max="365" class="form-input">
                    <small style="color: #94a3b8;">Expired unlocked clips are pruned automatically.</small>
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
                    <input type="checkbox" id="settings-audio-alert" checked>
                    <label for="settings-audio-alert" style="display:inline; margin-left: 4px;">Synthesize chime on Critical & High events</label>
                </div>
            </div>
        </div>

        <div class="panel" style="margin-top: 24px;">
            <div class="panel-header">
                <h3>Operator Activity & Audit Trail</h3>
                <button class="btn btn-small btn-secondary" id="btn-refresh-audit">Refresh Audit</button>
            </div>
            <div id="audit-logs-table-container">
                <p style="color: var(--text-muted); font-size: 0.85rem;">Loading activity log...</p>
            </div>
        </div>
    `;

    // Load real storage info
    const loadStorage = async () => {
        try {
            const data = await window.app.api.system.getStorage();
            if (!data) return;
            const fmt = (bytes) => {
                if (!bytes) return '0 B';
                const k = 1024;
                const s = ['B', 'KB', 'MB', 'GB', 'TB'];
                const i = Math.floor(Math.log(bytes) / Math.log(k));
                return (bytes / Math.pow(k, i)).toFixed(2) + ' ' + s[i];
            };
            container.querySelector('#st-total').textContent = fmt(data.total_space_bytes);
            container.querySelector('#st-recs').textContent = `${fmt(data.recordings_space_bytes)} (${data.recordings_count} clips)`;
            container.querySelector('#st-db').textContent = fmt(data.database_space_bytes);
            container.querySelector('#st-free').textContent = fmt(data.free_space_bytes);

            const total = data.total_space_bytes || 1;
            const recPct = Math.min(100, Math.max(1, (data.recordings_space_bytes / total) * 100));
            const dbPct = Math.min(100, Math.max(1, (data.database_space_bytes / total) * 100));
            container.querySelector('#storage-bar-recs').style.width = `${recPct}%`;
            container.querySelector('#storage-bar-db').style.width = `${dbPct}%`;
        } catch (e) {
            console.error('Failed to load storage status:', e);
        }
    };

    // Load real audit logs
    const loadAudit = async () => {
        try {
            const data = await window.app.api.system.getActivityLogs({ limit: 10 });
            const list = data.activities || [];
            const el = container.querySelector('#audit-logs-table-container');
            if (!el) return;
            if (list.length === 0) {
                el.innerHTML = '<p class="empty-state">No operator activity logged yet.</p>';
                return;
            }
            el.innerHTML = `
                <table class="data-table">
                    <thead>
                        <tr>
                            <th>Action</th>
                            <th>Resource</th>
                            <th>Status</th>
                            <th>Timestamp</th>
                            <th>Details</th>
                        </tr>
                    </thead>
                    <tbody>
                        ${list.map(a => `
                            <tr>
                                <td><b>${a.action}</b></td>
                                <td>${a.resource_type} ${a.resource_id ? `#${a.resource_id}` : ''}</td>
                                <td><span class="badge ${a.status === 'success' ? 'badge-info' : 'badge-danger'}">${(a.status || 'INFO').toUpperCase()}</span></td>
                                <td>${new Date(a.timestamp).toLocaleString()}</td>
                                <td><small style="color: var(--text-dim);">${JSON.stringify(a.details || {})}</small></td>
                            </tr>
                        `).join('')}
                    </tbody>
                </table>
            `;
        } catch (e) {
            console.error('Failed to load activity log:', e);
        }
    };

    loadStorage();
    loadAudit();

    container.querySelector('#btn-refresh-audit')?.addEventListener('click', loadAudit);

    container.querySelector('#btn-run-retention')?.addEventListener('click', async () => {
        if (confirm('Run automated retention pruning now? Expired and quota-exceeded unlocked clips will be deleted.')) {
            try {
                const res = await window.app.api.system.runRetentionCleanup(false);
                alert(`Retention cleanup complete: ${res.recordings_deleted} recordings and ${res.events_deleted} events pruned.`);
                loadStorage();
                loadAudit();
                actions.refreshRecordings();
            } catch (err) {
                alert('Retention cleanup failed: ' + err.message);
            }
        }
    });

    container.querySelector('#btn-backup-db')?.addEventListener('click', async () => {
        try {
            const res = await window.app.api.system.backupDatabase();
            alert(`Database backup created successfully: ${res.backup_file}`);
            loadAudit();
        } catch (err) {
            alert('Database backup failed: ' + err.message);
        }
    });

    container.querySelector('#btn-export-config')?.addEventListener('click', async () => {
        try {
            const cfg = await window.app.api.system.exportConfig();
            const blob = new Blob([JSON.stringify(cfg, null, 2)], { type: 'application/json' });
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `smart_spectator_config_${new Date().toISOString().substring(0, 10)}.json`;
            a.click();
            URL.revokeObjectURL(url);
        } catch (err) {
            alert('Export failed: ' + err.message);
        }
    });

    container.querySelector('#file-import-config')?.addEventListener('change', async (e) => {
        const file = e.target.files[0];
        if (!file) return;
        const reader = new FileReader();
        reader.onload = async (evt) => {
            try {
                const parsed = JSON.parse(evt.target.result);
                if (confirm(`Import configuration dated ${parsed.exported_at || 'unknown'}? Sensitive secrets will be preserved.`)) {
                    await window.app.api.system.importConfig(parsed);
                    alert('Configuration successfully imported.');
                    loadAudit();
                }
            } catch (err) {
                alert('Import failed: ' + err.message);
            }
        };
        reader.readAsText(file);
    });

    container.querySelector('#btn-save-settings')?.addEventListener('click', () => {
        const hubUrl = container.querySelector('#settings-hub-url').value.trim();
        if (hubUrl) {
            localStorage.setItem('ss_hub_url', hubUrl);
            actions.updateHubUrl(hubUrl);
        }
        alert('Settings saved locally.');
    });
}
