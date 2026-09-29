/**
 * Smart Spectator Client - Real-Time Event Stream WebSocket Client
 * Conforms to Sections 32, 54, 55 of Phase 5 specification.
 */

export class EventStreamClient {
    constructor(hubClient) {
        this.hubClient = hubClient;
        this.socket = null;
        this.isConnected = false;
        this.isReconnecting = false;
        this.reconnectAttempts = 0;
        this.maxReconnectDelayMs = 30000;
        this.listeners = new Map();
        this.statusListeners = new Set();
        this.subscriptionFilter = null;
    }

    setSubscription(filter = {}) {
        this.subscriptionFilter = filter;
        if (this.socket && this.socket.readyState === WebSocket.OPEN) {
            this.socket.send(JSON.stringify({
                type: 'subscription',
                camera_ids: filter.camera_ids || [],
                event_types: filter.event_types || [],
                min_confidence: filter.min_confidence || 0.0
            }));
        }
    }

    onStatusChange(listener) {
        this.statusListeners.add(listener);
    }

    emitStatus(status, details = '') {
        this.statusListeners.forEach(cb => cb(status, details));
    }

    on(messageType, callback) {
        if (!this.listeners.has(messageType)) {
            this.listeners.set(messageType, new Set());
        }
        this.listeners.get(messageType).add(callback);
    }

    off(messageType, callback) {
        if (this.listeners.has(messageType)) {
            this.listeners.get(messageType).delete(callback);
        }
    }

    emit(messageType, data) {
        if (this.listeners.has(messageType)) {
            this.listeners.get(messageType).forEach(cb => {
                try {
                    cb(data);
                } catch (e) {
                    console.error(`[EventStreamWS] Listener error for '${messageType}':`, e);
                }
            });
        }
    }

    connect() {
        if (this.socket && (this.socket.readyState === WebSocket.OPEN || this.socket.readyState === WebSocket.CONNECTING)) {
            return;
        }

        const base = this.hubClient.baseUrl || window.location.origin;
        const wsProtocol = base.startsWith('https') ? 'wss:' : 'ws:';
        const host = base.replace(/^https?:\/\//, '');
        const wsUrl = `${wsProtocol}//${host}/api/v1/events/stream`;

        this.emitStatus('connecting', wsUrl);

        try {
            this.socket = new WebSocket(wsUrl);

            this.socket.onopen = () => {
                this.isConnected = true;
                this.isReconnecting = false;
                this.reconnectAttempts = 0;
                this.emitStatus('connected');
                console.log('[EventStreamWS] Connected to Hub event stream.');

                // Start heartbeat ping
                this.startHeartbeat();

                // Restore subscription filter if configured
                if (this.subscriptionFilter) {
                    this.setSubscription(this.subscriptionFilter);
                }
            };

            this.socket.onmessage = (event) => {
                try {
                    const msg = JSON.parse(event.data);
                    if (msg.type === 'pong') {
                        return;
                    }
                    this.emit(msg.type, msg.data);
                    this.emit('*', msg);
                } catch (e) {
                    console.warn('[EventStreamWS] Failed to parse message:', event.data);
                }
            };

            this.socket.onclose = (event) => {
                this.isConnected = false;
                this.stopHeartbeat();
                this.emitStatus('disconnected', `Code: ${event.code}`);
                this.scheduleReconnect();
            };

            this.socket.onerror = (error) => {
                console.warn('[EventStreamWS] Socket error:', error);
                this.emitStatus('error');
            };

        } catch (e) {
            console.error('[EventStreamWS] Connection exception:', e);
            this.scheduleReconnect();
        }
    }

    startHeartbeat() {
        this.stopHeartbeat();
        this.pingInterval = setInterval(() => {
            if (this.socket && this.socket.readyState === WebSocket.OPEN) {
                this.socket.send(JSON.stringify({ type: 'ping', timestamp: Date.now() }));
            }
        }, 15000);
    }

    stopHeartbeat() {
        if (this.pingInterval) {
            clearInterval(this.pingInterval);
            this.pingInterval = null;
        }
    }

    scheduleReconnect() {
        if (this.isReconnecting) return;
        this.isReconnecting = true;

        this.reconnectAttempts++;
        // Exponential backoff with jitter
        const delay = Math.min(1000 * Math.pow(1.8, this.reconnectAttempts - 1), this.maxReconnectDelayMs);
        this.emitStatus('reconnecting', `Attempt ${this.reconnectAttempts} in ${Math.round(delay / 1000)}s`);

        setTimeout(() => {
            this.isReconnecting = false;
            this.connect();
        }, delay);
    }

    disconnect() {
        this.stopHeartbeat();
        if (this.socket) {
            this.socket.close();
            this.socket = null;
        }
        this.isConnected = false;
        this.isReconnecting = false;
        this.emitStatus('disconnected');
    }
}
