/**
 * Smart Spectator Client - Events Feed & Audit Log
 * Conforms to Section 40 of Phase 5 specification.
 */

import { DEFAULT_EVENT_CLASSES } from '../models.js';

export function renderEvents(container, stores, actions) {
    const evState = stores.event.get();
    const camState = stores.camera.get();
    const cameras = camState.cameras || [];
    const events = evState.events || [];
    const filters = evState.filters || {};

    container.innerHTML = `
        <div class="screen-header">
            <div>
                <h2>Events Intelligence Feed</h2>
                <p class="subtitle">Validated temporal occurrences evaluated by SpectatorNet and Event Engine</p>
            </div>
            <div class="actions-row">
                <button class="btn btn-secondary" id="btn-refresh-events">Refresh</button>
            </div>
        </div>

        <div class="filters-bar panel">
            <div class="filter-item">
                <label>Camera:</label>
                <select id="filter-camera">
                    <option value="">All Cameras</option>
                    ${cameras.map(c => `<option value="${c.camera_id}" ${filters.camera_id === c.camera_id ? 'selected' : ''}>${c.name}</option>`).join('')}
                </select>
            </div>

            <div class="filter-item">
                <label>Event Type:</label>
                <select id="filter-type">
                    <option value="">All Event Types</option>
                    ${DEFAULT_EVENT_CLASSES.map(t => `<option value="${t}" ${filters.event_type === t ? 'selected' : ''}>${t.replace(/_/g, ' ')}</option>`).join('')}
                    <option value="CAMERA_CONNECTED" ${filters.event_type === 'CAMERA_CONNECTED' ? 'selected' : ''}>Camera Connected</option>
                    <option value="CAMERA_DISCONNECTED" ${filters.event_type === 'CAMERA_DISCONNECTED' ? 'selected' : ''}>Camera Disconnected</option>
                </select>
            </div>

            <div class="filter-item">
                <label>Severity:</label>
                <select id="filter-severity">
                    <option value="">All Severities</option>
                    <option value="info" ${filters.severity === 'info' ? 'selected' : ''}>Info</option>
                    <option value="low" ${filters.severity === 'low' ? 'selected' : ''}>Low</option>
                    <option value="medium" ${filters.severity === 'medium' ? 'selected' : ''}>Medium</option>
                    <option value="high" ${filters.severity === 'high' ? 'selected' : ''}>High</option>
                    <option value="critical" ${filters.severity === 'critical' ? 'selected' : ''}>Critical</option>
                </select>
            </div>

            <div class="filter-item">
                <label>Priority:</label>
                <select id="filter-priority">
                    <option value="">All Priorities</option>
                    <option value="CRITICAL" ${filters.priority === 'CRITICAL' ? 'selected' : ''}>Critical</option>
                    <option value="HIGH" ${filters.priority === 'HIGH' ? 'selected' : ''}>High</option>
                    <option value="MEDIUM" ${filters.priority === 'MEDIUM' ? 'selected' : ''}>Medium</option>
                    <option value="LOW" ${filters.priority === 'LOW' ? 'selected' : ''}>Low</option>
                </select>
            </div>

            <div class="filter-item">
                <label>Status:</label>
                <select id="filter-status">
                    <option value="">All Statuses</option>
                    <option value="confirmed" ${filters.status === 'confirmed' ? 'selected' : ''}>Confirmed</option>
                    <option value="active" ${filters.status === 'active' ? 'selected' : ''}>Active</option>
                    <option value="resolved" ${filters.status === 'resolved' ? 'selected' : ''}>Resolved</option>
                    <option value="dismissed" ${filters.status === 'dismissed' ? 'selected' : ''}>Dismissed</option>
                </select>
            </div>

            <div class="filter-actions">
                <button class="btn btn-secondary btn-small" id="btn-clear-filters">Clear</button>
            </div>
        </div>

        <div class="panel events-table-container">
            ${events.length === 0 ? `
                <div class="empty-state">
                    <p>No events match the selected filters.</p>
                </div>
            ` : `
                <table class="data-table">
                    <thead>
                        <tr>
                            <th>Priority</th>
                            <th>Severity</th>
                            <th>Event Type</th>
                            <th>Camera</th>
                            <th>Explanation</th>
                            <th>Confidence</th>
                            <th>Timestamp</th>
                            <th>Status</th>
                            <th>Actions</th>
                        </tr>
                    </thead>
                    <tbody>
                        ${events.map(ev => `
                            <tr class="event-row" data-event-id="${ev.event_id}">
                                <td><span class="badge badge-priority-${(ev.priority || 'medium').toLowerCase()}">${ev.priority || 'MEDIUM'}</span></td>
                                <td><span class="badge badge-${ev.severity}">${ev.severity.toUpperCase()}</span></td>
                                <td><b>${ev.event_type.replace(/_/g, ' ')}</b></td>
                                <td>${ev.camera_id}</td>
                                <td class="table-summary-cell">${ev.explanation || ev.summary}</td>
                                <td>${Math.round(ev.confidence * 100)}%</td>
                                <td>${new Date(ev.timestamp).toLocaleString()}</td>
                                <td><span class="status-pill status-${ev.status}">${ev.status.toUpperCase()}</span></td>
                                <td>
                                    <button class="btn btn-small btn-secondary btn-inspect-event" data-event-id="${ev.event_id}">Inspect</button>
                                </td>
                            </tr>
                        `).join('')}
                    </tbody>
                </table>
            `}
        </div>
    `;

    // Filter bindings
    const updateFilters = () => {
        const cam = container.querySelector('#filter-camera').value;
        const type = container.querySelector('#filter-type').value;
        const sev = container.querySelector('#filter-severity').value;
        const prio = container.querySelector('#filter-priority').value;
        const stat = container.querySelector('#filter-status').value;
        actions.setEventFilters({ camera_id: cam, event_type: type, severity: sev, priority: prio, status: stat });
    };

    container.querySelector('#filter-camera')?.addEventListener('change', updateFilters);
    container.querySelector('#filter-type')?.addEventListener('change', updateFilters);
    container.querySelector('#filter-severity')?.addEventListener('change', updateFilters);
    container.querySelector('#filter-priority')?.addEventListener('change', updateFilters);
    container.querySelector('#filter-status')?.addEventListener('change', updateFilters);

    container.querySelector('#btn-clear-filters')?.addEventListener('click', () => {
        actions.setEventFilters({ camera_id: '', event_type: '', severity: '', priority: '', status: '' });
    });

    container.querySelector('#btn-refresh-events')?.addEventListener('click', () => actions.refreshEvents());

    container.querySelectorAll('.event-row, .btn-inspect-event').forEach(el => {
        el.addEventListener('click', (e) => {
            const evId = el.getAttribute('data-event-id');
            actions.openEventDetail(evId);
        });
    });
}
