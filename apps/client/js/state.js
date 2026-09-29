/**
 * Smart Spectator Client - State Management
 * Conforms to Section 80 of Phase 5 specification.
 * Separates camera, event, rule, zone, system, and connection stores.
 */

class Store {
    constructor(initialState = {}) {
        this.state = initialState;
        this.subscribers = new Set();
    }

    get() {
        return this.state;
    }

    set(updates) {
        this.state = { ...this.state, ...updates };
        this.notify();
    }

    subscribe(listener) {
        this.subscribers.add(listener);
        return () => this.subscribers.delete(listener);
    }

    notify() {
        this.subscribers.forEach(cb => {
            try {
                cb(this.state);
            } catch (e) {
                console.error('[Store] Subscriber error:', e);
            }
        });
    }
}

export const connectionStore = new Store({
    status: 'connecting', // 'connected', 'connecting', 'reconnecting', 'disconnected'
    statusMessage: '',
    hubUrl: '',
    lastPingMs: null
});

export const cameraStore = new Store({
    cameras: [],
    selectedCameraId: null,
    isLoading: false,
    error: null
});

export const eventStore = new Store({
    events: [],
    selectedEvent: null,
    filters: {
        camera_id: '',
        event_type: '',
        severity: '',
        status: ''
    },
    unreadCount: 0,
    isLoading: false,
    error: null
});

export const ruleStore = new Store({
    rules: [],
    editingRule: null,
    isLoading: false,
    error: null
});

export const zoneStore = new Store({
    zones: {}, // camera_id -> [Zone]
    selectedCameraId: null,
    editingZone: null,
    isDrawing: false,
    draftPolygon: [],
    isLoading: false,
    error: null
});

export const recordingStore = new Store({
    recordings: [],
    selectedRecording: null,
    isLoading: false,
    error: null
});

export const deviceStore = new Store({
    devices: [],
    pendingPairings: [],
    isLoading: false,
    error: null
});

export const systemStore = new Store({
    health: null,
    componentHealth: null,
    status: null,
    metrics: null,
    aiTelemetry: null,
    auditLogs: [],
    isLoading: false,
    error: null
});
