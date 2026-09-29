/**
 * Smart Spectator Client - Data Models
 * Strictly mirrors shared/schemas/v1/models.py
 */

export const EventSeverity = Object.freeze({
    INFO: 'info',
    LOW: 'low',
    MEDIUM: 'medium',
    HIGH: 'high',
    CRITICAL: 'critical'
});

export const EventStatus = Object.freeze({
    DETECTED: 'detected',
    CONFIRMED: 'confirmed',
    ACTIVE: 'active',
    RESOLVED: 'resolved',
    DISMISSED: 'dismissed'
});

export const DeviceStatus = Object.freeze({
    DISCOVERED: 'discovered',
    PAIRING: 'pairing',
    PAIRED: 'paired',
    CONNECTED: 'connected',
    DISCONNECTED: 'disconnected',
    REVOKED: 'revoked'
});

export const StreamStatus = Object.freeze({
    IDLE: 'idle',
    STARTING: 'starting',
    STREAMING: 'streaming',
    DEGRADED: 'degraded',
    STOPPED: 'stopped',
    ERROR: 'error'
});

export const DEFAULT_EVENT_CLASSES = [
    'NORMAL_BACKGROUND',
    'OBJECT_PRESENT',
    'OBJECT_REMOVED',
    'OBJECT_MOVED',
    'PERSON_ENTERED',
    'PERSON_LEFT',
    'ZONE_LOITERING',
    'CAMERA_BLOCKED',
    'TASK_COMPLETED'
];
