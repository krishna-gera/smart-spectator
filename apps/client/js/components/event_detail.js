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

    container.innerHTML = `
        <div class="screen-header">
            <div>
                <button class="btn-text" id="btn-back-events">&larr; Back to Events Feed</button>
                <h2>Event: ${event.event_type.replace(/_/g, ' ')}</h2>
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

        <div class="event-detail-grid">
            <div class="panel">
                <div class="panel-header">
                    <h3>Deterministic Perception Explanation</h3>
                </div>
                <div class="explanation-box severity-border-${event.severity}">
                    <p style="font-size: 1.05rem; margin: 0; line-height: 1.5;">${event.explanation || event.summary}</p>
                </div>

                <div class="panel-header" style="margin-top: 24px;">
                    <h3>Lifecycle Timeline</h3>
                </div>
                <div class="timeline-container">
                    <div class="timeline-step step-complete">
                        <div class="step-marker">1</div>
                        <div class="step-label"><b>DETECTED</b><br><small>${startStr}</small></div>
                    </div>
                    <div class="timeline-line"></div>
                    <div class="timeline-step ${['confirmed', 'active', 'resolved'].includes(event.status) ? 'step-complete' : ''}">
                        <div class="step-marker">2</div>
                        <div class="step-label"><b>CONFIRMED</b><br><small>Debounced</small></div>
                    </div>
                    <div class="timeline-line"></div>
                    <div class="timeline-step ${['active', 'resolved'].includes(event.status) ? 'step-complete' : ''}">
                        <div class="step-marker">3</div>
                        <div class="step-label"><b>ACTIVE</b><br><small>Buffer Rolling</small></div>
                    </div>
                    <div class="timeline-line"></div>
                    <div class="timeline-step ${event.status === 'resolved' ? 'step-complete' : (event.status === 'dismissed' ? 'step-dismissed' : '')}">
                        <div class="step-marker">4</div>
                        <div class="step-label"><b>${event.status === 'dismissed' ? 'DISMISSED' : 'RESOLVED'}</b><br><small>${event.status === 'resolved' ? endStr : (event.status === 'dismissed' ? 'Canceled' : 'Pending')}</small></div>
                    </div>
                </div>

                <div class="panel-header" style="margin-top: 24px;">
                    <h3>Event Parameters</h3>
                </div>
                <div class="telemetry-table">
                    <div class="telem-row"><span>Severity</span><span class="badge badge-${event.severity}">${event.severity.toUpperCase()}</span></div>
                    <div class="telem-row"><span>Model Confidence</span><span>${Math.round(event.confidence * 100)}%</span></div>
                    <div class="telem-row"><span>Triggered Rule</span><span>${event.rule_id || 'System Default Policy'}</span></div>
                    <div class="telem-row"><span>Associated Zone</span><span>${event.zone_id || 'Full Scene'}</span></div>
                    <div class="telem-row"><span>Involved Tracks</span><span>${tracksStr}</span></div>
                    <div class="telem-row"><span>Confirmation Latency</span><span>${event.metadata?.confirmation_latency_ms ? event.metadata.confirmation_latency_ms + ' ms' : 'N/A'}</span></div>
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
                            <a href="/api/v1/recordings/${event.recording_id}/stream" download="event_${event.event_id}.mp4" class="btn btn-small btn-secondary">Download MP4</a>
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
