/**
 * Smart Spectator Client - Automation Rules Builder Component
 * Conforms to Section 45 of Phase 5 specification.
 */

import { DEFAULT_EVENT_CLASSES } from '../models.js';

export function renderRules(container, stores, actions) {
    const ruleState = stores.rule.get();
    const camState = stores.camera.get();
    const zoneState = stores.zone.get();

    const rules = ruleState.rules || [];
    const cameras = camState.cameras || [];

    // Collect all zones across cameras
    const allZones = [];
    Object.values(zoneState.zones).forEach(zList => {
        allZones.push(...zList);
    });

    container.innerHTML = `
        <div class="screen-header">
            <div>
                <h2>Automation Rules (${rules.length})</h2>
                <p class="subtitle">Structured event triggers, automated clip recording, and local client alerts</p>
            </div>
            <div class="actions-row">
                <button class="btn btn-secondary" id="btn-refresh-rules">Refresh</button>
            </div>
        </div>

        <div class="rules-builder-layout">
            <div class="panel rule-form-panel">
                <div class="panel-header">
                    <h3>Create Automation Rule</h3>
                </div>
                <form id="create-rule-form">
                    <div class="form-group">
                        <label>Rule Name:</label>
                        <input type="text" id="rule-name" placeholder="e.g. Front Door Person Entry Alert" required class="form-input">
                    </div>

                    <div class="form-group">
                        <label>WHEN (Event Type):</label>
                        <select id="rule-event-type" class="form-select">
                            <option value="*">Any Event Type (*)</option>
                            ${DEFAULT_EVENT_CLASSES.map(t => `<option value="${t}">${t.replace(/_/g, ' ')}</option>`).join('')}
                        </select>
                    </div>

                    <div class="form-group">
                        <label>ON CAMERA:</label>
                        <select id="rule-camera" class="form-select">
                            <option value="*">All Cameras (*)</option>
                            ${cameras.map(c => `<option value="${c.camera_id}">${c.name} (${c.camera_id})</option>`).join('')}
                        </select>
                    </div>

                    <div class="form-group">
                        <label>IN ZONE (Optional):</label>
                        <select id="rule-zone" class="form-select">
                            <option value="">Anywhere in scene</option>
                            ${allZones.map(z => `<option value="${z.zone_id}">${z.name} (${z.camera_id})</option>`).join('')}
                        </select>
                    </div>

                    <div class="form-group">
                        <label>MINIMUM CONFIDENCE:</label>
                        <select id="rule-min-confidence" class="form-select">
                            <option value="0.70">70% Confidence</option>
                            <option value="0.75">75% Confidence</option>
                            <option value="0.80" selected>80% Confidence (Recommended)</option>
                            <option value="0.85">85% Confidence</option>
                            <option value="0.90">90% Confidence (Strict)</option>
                        </select>
                    </div>

                    <div class="form-group">
                        <label>ACTIVE TIME RANGE (Optional 24h):</label>
                        <div style="display: flex; gap: 8px;">
                            <input type="time" id="rule-time-start" class="form-input" title="Start Time">
                            <span style="align-self: center;">to</span>
                            <input type="time" id="rule-time-end" class="form-input" title="End Time">
                        </div>
                    </div>

                    <div class="form-group">
                        <label>SEVERITY OVERRIDE:</label>
                        <select id="rule-severity-override" class="form-select">
                            <option value="">Default Taxonomic Severity</option>
                            <option value="low">Low</option>
                            <option value="medium">Medium</option>
                            <option value="high">High</option>
                            <option value="critical">Critical</option>
                        </select>
                    </div>

                    <div class="form-group">
                        <label>PRIORITY OVERRIDE:</label>
                        <select id="rule-priority-override" class="form-select">
                            <option value="">Default Deterministic Priority</option>
                            <option value="CRITICAL">Critical</option>
                            <option value="HIGH">High</option>
                            <option value="MEDIUM">Medium</option>
                            <option value="LOW">Low</option>
                        </select>
                    </div>

                    <div class="form-group">
                        <label>THEN ACTIONS:</label>
                        <div class="checkbox-group">
                            <label><input type="checkbox" id="act-create" checked disabled> Create Confirmed Event</label>
                            <label><input type="checkbox" id="act-clip" checked> Save Video Clip (Rolling Buffer)</label>
                            <label><input type="checkbox" id="act-notify" checked> Client Notification</label>
                            <label><input type="checkbox" id="act-audit" checked> Record Audit Log</label>
                        </div>
                    </div>

                    <div class="form-group">
                        <label>COOLDOWN (Seconds):</label>
                        <input type="number" id="rule-cooldown" value="60" min="0" max="3600" class="form-input">
                    </div>

                    <button type="submit" class="btn btn-primary" style="width: 100%; margin-top: 12px;">Save Automation Rule</button>
                </form>
            </div>

            <div class="panel rules-list-panel">
                <div class="panel-header">
                    <h3>Active Policies</h3>
                </div>
                <div class="rules-list">
                    ${rules.length === 0 ? '<p class="empty-state">No custom rules configured yet. The Event Engine uses standard perception policy defaults.</p>' : ''}
                    ${rules.map(r => `
                        <div class="rule-card ${!r.enabled ? 'rule-disabled' : ''}">
                            <div class="rule-card-header">
                                <div class="rule-card-title">
                                    <b>${r.name}</b>
                                    <span class="rule-id-sub">${r.rule_id}</span>
                                </div>
                                <div class="rule-toggle-row">
                                    <button class="btn btn-small ${r.enabled ? 'btn-secondary' : 'btn-primary'} btn-toggle-rule" data-rule-id="${r.rule_id}" data-enabled="${r.enabled}">
                                        ${r.enabled ? 'Disable' : 'Enable'}
                                    </button>
                                    <button class="btn btn-small btn-danger btn-delete-rule" data-rule-id="${r.rule_id}">Delete</button>
                                </div>
                            </div>
                            <div class="rule-card-body">
                                <div><b>Trigger:</b> IF <code>${r.conditions?.event_type || '*'}</code> ON <code>${r.conditions?.camera_id || 'All Cameras'}</code></div>
                                ${r.conditions?.zone_id ? `<div><b>Zone:</b> <code>${r.conditions.zone_id}</code></div>` : ''}
                                <div><b>Min Confidence:</b> ${Math.round((r.conditions?.minimum_confidence || 0.70) * 100)}%</div>
                                <div><b>Actions:</b> ${r.actions.join(', ')}</div>
                                <div><b>Cooldown:</b> ${r.cooldown_seconds}s</div>
                            </div>
                        </div>
                    `).join('')}
                </div>
            </div>
        </div>
    `;

    container.querySelector('#btn-refresh-rules')?.addEventListener('click', () => actions.refreshRules());

    container.querySelector('#create-rule-form')?.addEventListener('submit', async (e) => {
        e.preventDefault();
        const name = container.querySelector('#rule-name').value.trim();
        const eventType = container.querySelector('#rule-event-type').value;
        const camera = container.querySelector('#rule-camera').value;
        const zone = container.querySelector('#rule-zone').value || null;
        const minConf = parseFloat(container.querySelector('#rule-min-confidence').value);
        const timeStart = container.querySelector('#rule-time-start').value || null;
        const timeEnd = container.querySelector('#rule-time-end').value || null;
        const sevOverride = container.querySelector('#rule-severity-override').value || null;
        const prioOverride = container.querySelector('#rule-priority-override').value || null;
        const cooldown = parseInt(container.querySelector('#rule-cooldown').value, 10);

        const actionsList = ['CREATE_EVENT'];
        if (container.querySelector('#act-clip').checked) actionsList.push('SAVE_CLIP');
        if (container.querySelector('#act-notify').checked) actionsList.push('CLIENT_NOTIFICATION');
        if (container.querySelector('#act-audit').checked) actionsList.push('LOG_EVENT');

        const conditions = {
            event_type: eventType,
            camera_id: camera,
            minimum_confidence: minConf
        };
        if (zone) conditions.zone_id = zone;
        if (timeStart) conditions.time_start = timeStart;
        if (timeEnd) conditions.time_end = timeEnd;

        try {
            await actions.createRule({
                name,
                enabled: true,
                conditions,
                actions: actionsList,
                cooldown_seconds: cooldown,
                severity_override: sevOverride,
                priority_override: prioOverride
            });
            await actions.refreshRules();
            renderRules(container, stores, actions);
        } catch (err) {
            alert(`Error creating rule: ${err.message}`);
        }
    });

    container.querySelectorAll('.btn-toggle-rule').forEach(btn => {
        btn.addEventListener('click', async () => {
            const ruleId = btn.getAttribute('data-rule-id');
            const isEnabled = btn.getAttribute('data-enabled') === 'true';
            if (isEnabled) {
                await actions.disableRule(ruleId);
            } else {
                await actions.enableRule(ruleId);
            }
            await actions.refreshRules();
            renderRules(container, stores, actions);
        });
    });

    container.querySelectorAll('.btn-delete-rule').forEach(btn => {
        btn.addEventListener('click', async () => {
            const ruleId = btn.getAttribute('data-rule-id');
            if (confirm(`Delete rule '${ruleId}'?`)) {
                await actions.deleteRule(ruleId);
                await actions.refreshRules();
                renderRules(container, stores, actions);
            }
        });
    });
}
