/**
 * Smart Spectator Client - Event Detail & Timeline Component
 * Conforms to Sections 41 & 42 of Phase 5 specification.
 */

export function renderEventDetail(container, stores, actions, eventId) {
    const evState = stores.event.get();
    const event = evState.events.find(e => e.event_id === eventId) || evState.selectedEvent;

    if (!event) {
        container.innerHTML = `
            <div class="empty-state-card">
                <p>Event '${eventId}' not found.</p>
                <button class="btn btn-secondary" id="btn-back-events">Back to Events</button>
            </div>
        `;
        container.querySelector('#btn-back-events')?.addEventListener('click', () => actions.navigateTo('events'));
        return;
    }

    const startStr = event.start_time ? new Date(event.start_time).toLocaleTimeString() : 'N/A';
    const endStr = event.end_time ? new Date(event.end_time).toLocaleTimeString() : 'Ongoing';
    const tracksStr = (event.involved_track_ids && event.involved_track_ids.length > 0)
        ? event.involved_track_ids.map(t => `#${t}`).join(', ')
        : 'None recorded';

    const priority = event.priority || 'MEDIUM';
    const milestones = (event.timeline_milestones && event.timeline_milestones.length > 0)
        ? event.timeline_milestones
        : [
            { timestamp: event.start_time || new Date().toISOString(), title: 'Motion Detected', description: `Motion registered on camera ${event.camera_id}` },
            { timestamp: event.timestamp || new Date().toISOString(), title: 'Pattern Confirmed', description: `${event.event_type.replace(/_/g, ' ')} confirmed with ${Math.round(event.confidence * 100)}% confidence` },
            { timestamp: event.timestamp || new Date().toISOString(), title: 'Event Triggered', description: `Assigned priority ${priority}` }
        ];

    container.innerHTML = `
        <div class="screen-header">
            <div>
                <button class="btn-text" id="btn-back-events">&larr; Back to Events Feed</button>
                <div style="display: flex; align-items: center; gap: 12px; margin-top: 6px;">
                    <h2>Event: ${event.event_type.replace(/_/g, ' ')}</h2>
                    <span class="badge badge-priority-${priority.toLowerCase()}">${priority}</span>
                    <span class="badge badge-${event.severity}">${event.severity.toUpperCase()}</span>
                </div>
                <p class="subtitle">ID: ${event.event_id} • Camera: ${event.camera_id}</p>
            </div>
            <div class="actions-row">
                ${event.status !== 'resolved' && event.status !== 'dismissed' ? `
                    <button class="btn btn-secondary" id="btn-ack-event">Acknowledge</button>
                    <button class="btn btn-danger" id="btn-dismiss-event">Dismiss</button>
                    <button class="btn btn-primary" id="btn-resolve-event">Resolve Event</button>
                ` : `
                    <span class="status-pill status-${event.status}">${event.status.toUpperCase()}</span>
                `}
            </div>
        </div>

        <div class="explanation-card">
            <div class="explanation-title">
                <span>🔍</span> Why This Event Was Triggered
            </div>
            <div class="explanation-text">
                ${event.explanation || event.summary || 'Event pattern verified deterministically by SpectatorNet and Event Engine rules.'}
            </div>
        </div>

        <div class="event-detail-grid">
            <div class="panel">
                <div class="panel-header">
                    <h3>Causal Timeline Milestones</h3>
                </div>
                <div class="timeline-milestones">
                    ${milestones.map((m, idx) => `
                        <div class="timeline-node">
                            <div class="timeline-marker ${idx === milestones.length - 1 ? priority.toLowerCase() : ''}"></div>
                            <div class="timeline-content">
                                <div class="timeline-header">
                                    <span class="timeline-title">${m.title}</span>
                                    <span class="timeline-time">${m.timestamp ? new Date(m.timestamp).toLocaleTimeString() : ''}</span>
                                </div>
                                <div class="timeline-desc">${m.description}</div>
                            </div>
                        </div>
                    `).join('')}
                </div>

                <div class="panel-header" style="margin-top: 24px;">
                    <h3>Event Parameters</h3>
                </div>
                <div class="telemetry-table">
                    <div class="telem-row"><span>Priority</span><span class="badge badge-priority-${priority.toLowerCase()}">${priority}</span></div>
                    <div class="telem-row"><span>Severity</span><span class="badge badge-${event.severity}">${event.severity.toUpperCase()}</span></div>
                    <div class="telem-row"><span>Model Confidence</span><span>${Math.round(event.confidence * 100)}%</span></div>
                    <div class="telem-row"><span>Triggered Rule</span><span>${event.rule_id || 'System Default Policy'}</span></div>
                    <div class="telem-row"><span>Associated Zone</span><span>${event.zone_id || 'Full Scene'}</span></div>
                    <div class="telem-row"><span>Involved Tracks</span><span>${tracksStr}</span></div>
                    <div class="telem-row"><span>Start Time</span><span>${startStr}</span></div>
                    <div class="telem-row"><span>End Time</span><span>${endStr}</span></div>
                </div>
            </div>

            <div class="panel">
                <div class="panel-header">
                    <h3>Event Evidence Recording</h3>
                </div>
                ${event.recording_id ? `
                    <div class="recording-player-box">
                        <video controls autoplay loop class="clip-video" poster="/api/v1/recordings/${event.recording_id}/thumbnail">
                            <source src="/api/v1/recordings/${event.recording_id}/stream" type="video/mp4">
                            Your browser does not support HTML5 video streaming.
                        </video>
                        <div class="clip-meta">
                            <span><b>Clip ID:</b> ${event.recording_id}</span>
                            <a href="/api/v1/recordings/${event.recording_id}/download" download="event_${event.event_id}.mp4" class="btn btn-small btn-secondary">Download MP4</a>
                        </div>
                    </div>
                ` : `
                    <div class="empty-state" style="padding: 40px 20px;">
                        <p>No video recording attached to this event yet.</p>
                        <small style="color: #94a3b8;">${event.status === 'active' ? 'Media buffer is actively recording. Clip will finalize upon resolution.' : 'Recording was disabled or buffer was empty.'}</small>
                    </div>
                `}
            </div>
        </div>
    `;

    container.querySelector('#btn-back-events')?.addEventListener('click', () => actions.navigateTo('events'));

    container.querySelector('#btn-ack-event')?.addEventListener('click', async () => {
        await actions.acknowledgeEvent(event.event_id);
        renderEventDetail(container, stores, actions, eventId);
    });

    container.querySelector('#btn-dismiss-event')?.addEventListener('click', async () => {
        await actions.dismissEvent(event.event_id);
        renderEventDetail(container, stores, actions, eventId);
    });

    container.querySelector('#btn-resolve-event')?.addEventListener('click', async () => {
        await actions.resolveEvent(event.event_id);
        renderEventDetail(container, stores, actions, eventId);
    });
}
