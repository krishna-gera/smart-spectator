/**
 * Smart Spectator Client - Local Recordings Component
 * Conforms to Section 43 of Phase 5 specification.
 */

export function renderRecordings(container, stores, actions) {
    const recState = stores.recording.get();
    const recordings = recState.recordings || [];

    const formatBytes = (bytes) => {
        if (!bytes || bytes === 0) return '0 B';
        const k = 1024;
        const sizes = ['B', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
    };

    container.innerHTML = `
        <div class="screen-header">
            <div>
                <h2>Recordings Vault (${recordings.length})</h2>
                <p class="subtitle">Protected local event video clips generated from the rolling media ring buffer</p>
            </div>
            <div class="actions-row">
                <button class="btn btn-secondary" id="btn-refresh-recs">Refresh</button>
            </div>
        </div>

        ${recordings.length === 0 ? `
            <div class="empty-state-card">
                <p>No video clips recorded yet.</p>
                <small style="color: #94a3b8;">Clips are automatically generated with pre-roll and post-roll when AI events are confirmed.</small>
            </div>
        ` : `
            <div class="recordings-grid">
                ${recordings.map(r => `
                    <div class="recording-card" data-rec-id="${r.recording_id}">
                        <div class="rec-thumb-container">
                            <img src="/api/v1/recordings/${r.recording_id}/thumbnail" alt="Thumbnail" onerror="this.src='data:image/svg+xml;utf8,<svg xmlns=\\'http://www.w3.org/2000/svg\\' width=\\'320\\' height=\\'180\\'><rect width=\\'100%\\' height=\\'100%\\' fill=\\'%231e293b\\'/><text x=\\'50%\\' y=\\'50%\\' fill=\\'%2364748b\\' text-anchor=\\'middle\\' dy=\\'.3em\\'>Video Clip</text></svg>'">
                            <span class="rec-duration-badge">${r.duration_seconds}s</span>
                            <span class="badge ${r.is_locked ? 'badge-locked' : 'badge-unlocked'}" style="position: absolute; top: 8px; left: 8px; font-size: 0.7rem;">${r.is_locked ? '🔒 Locked' : 'Unlocked'}</span>
                        </div>
                        <div class="rec-card-body">
                            <div class="rec-card-title">
                                <b>Camera: ${r.camera_id}</b>
                                <span class="rec-size">${formatBytes(r.file_size_bytes)}</span>
                            </div>
                            <div class="rec-card-meta">
                                <span>Event: ${r.event_id || 'Triggered Clip'}</span><br>
                                <small>${new Date(r.created_at).toLocaleString()}</small>
                            </div>
                            <div class="rec-card-actions" style="display: flex; gap: 6px; flex-wrap: wrap;">
                                <button class="btn btn-small btn-primary btn-play-clip" data-rec-id="${r.recording_id}">Play</button>
                                <a href="/api/v1/recordings/${r.recording_id}/download" download="recording_${r.recording_id}.mp4" class="btn btn-small btn-secondary">Download</a>
                                <button class="btn btn-small btn-secondary btn-lock-clip" data-rec-id="${r.recording_id}" data-locked="${r.is_locked ? 'true' : 'false'}">${r.is_locked ? 'Unlock' : 'Lock'}</button>
                                <button class="btn btn-small btn-danger btn-delete-clip" data-rec-id="${r.recording_id}" data-locked="${r.is_locked ? 'true' : 'false'}">Delete</button>
                            </div>
                        </div>
                    </div>
                `).join('')}
            </div>
        `}

        <div id="video-modal-overlay" class="modal-overlay hidden">
            <div class="modal-card">
                <div class="modal-header">
                    <h3 id="modal-video-title">Video Clip Player</h3>
                    <button class="btn-close" id="modal-video-close">&times;</button>
                </div>
                <div class="modal-body">
                    <video id="modal-video-player" controls autoplay style="width: 100%; border-radius: 8px; max-height: 70vh;">
                        Your browser does not support HTML5 video.
                    </video>
                </div>
            </div>
        </div>
    `;

    container.querySelector('#btn-refresh-recs')?.addEventListener('click', () => actions.refreshRecordings());

    const modalOverlay = container.querySelector('#video-modal-overlay');
    const videoPlayer = container.querySelector('#modal-video-player');
    const modalTitle = container.querySelector('#modal-video-title');

    container.querySelectorAll('.btn-play-clip').forEach(btn => {
        btn.addEventListener('click', () => {
            const recId = btn.getAttribute('data-rec-id');
            modalTitle.textContent = `Clip: ${recId}`;
            videoPlayer.src = `/api/v1/recordings/${recId}/stream`;
            modalOverlay.classList.remove('hidden');
        });
    });

    container.querySelectorAll('.btn-lock-clip').forEach(btn => {
        btn.addEventListener('click', async () => {
            const recId = btn.getAttribute('data-rec-id');
            const isCurrentlyLocked = btn.getAttribute('data-locked') === 'true';
            try {
                await window.app.api.recordings.toggleLock(recId, !isCurrentlyLocked);
                await actions.refreshRecordings();
            } catch (err) {
                alert('Failed to update recording lock: ' + err.message);
            }
        });
    });

    container.querySelectorAll('.btn-delete-clip').forEach(btn => {
        btn.addEventListener('click', async () => {
            const recId = btn.getAttribute('data-rec-id');
            const isLocked = btn.getAttribute('data-locked') === 'true';
            if (isLocked) {
                alert('Cannot delete a locked recording. Unlock it first.');
                return;
            }
            if (confirm(`Are you sure you want to permanently delete recording '${recId}'?`)) {
                try {
                    await actions.deleteRecording(recId);
                    await actions.refreshRecordings();
                } catch (err) {
                    alert('Delete failed: ' + err.message);
                }
            }
        });
    });

    container.querySelector('#modal-video-close')?.addEventListener('click', () => {
        videoPlayer.pause();
        videoPlayer.src = '';
        modalOverlay.classList.add('hidden');
    });

    modalOverlay?.addEventListener('click', (e) => {
        if (e.target === modalOverlay) {
            videoPlayer.pause();
            videoPlayer.src = '';
            modalOverlay.classList.add('hidden');
        }
    });
}
