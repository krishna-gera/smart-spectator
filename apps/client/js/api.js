/**
 * Smart Spectator Client - Strongly Typed Hub API Client
 * Conforms to Section 53 of Phase 5 specification.
 */

class BaseApi {
    constructor(client) {
        this.client = client;
    }

    async get(endpoint, params = {}) {
        const url = new URL(this.client.baseUrl + endpoint);
        Object.keys(params).forEach(key => {
            if (params[key] !== undefined && params[key] !== null && params[key] !== '') {
                url.searchParams.append(key, params[key]);
            }
        });
        const res = await fetch(url.toString(), {
            method: 'GET',
            headers: this.client.getHeaders()
        });
        if (!res.ok) {
            const err = await res.json().catch(() => ({ detail: res.statusText }));
            throw new Error(err.detail || `GET ${endpoint} failed with ${res.status}`);
        }
        return res.json();
    }

    async post(endpoint, data = {}) {
        const res = await fetch(this.client.baseUrl + endpoint, {
            method: 'POST',
            headers: this.client.getHeaders(),
            body: JSON.stringify(data)
        });
        if (!res.ok) {
            const err = await res.json().catch(() => ({ detail: res.statusText }));
            throw new Error(err.detail || `POST ${endpoint} failed with ${res.status}`);
        }
        return res.status === 204 ? null : res.json();
    }

    async put(endpoint, data = {}) {
        const res = await fetch(this.client.baseUrl + endpoint, {
            method: 'PUT',
            headers: this.client.getHeaders(),
            body: JSON.stringify(data)
        });
        if (!res.ok) {
            const err = await res.json().catch(() => ({ detail: res.statusText }));
            throw new Error(err.detail || `PUT ${endpoint} failed with ${res.status}`);
        }
        return res.json();
    }

    async delete(endpoint) {
        const res = await fetch(this.client.baseUrl + endpoint, {
            method: 'DELETE',
            headers: this.client.getHeaders()
        });
        if (!res.ok) {
            const err = await res.json().catch(() => ({ detail: res.statusText }));
            throw new Error(err.detail || `DELETE ${endpoint} failed with ${res.status}`);
        }
        return res.status === 204 ? null : res.json();
    }
}

export class AiApi extends BaseApi {
    async getStatus() {
        return this.get('/api/v1/ai/status');
    }

    async listModels() {
        return this.get('/api/v1/ai/models');
    }

    async getModel(modelId) {
        return this.get(`/api/v1/ai/models/${modelId}`);
    }

    async activateModel(taskType, modelId) {
        return this.post(`/api/v1/ai/models/${taskType}/activate`, { model_id: modelId });
    }

    async runAbEvaluation(modelAId, modelBId, taskType = 'temporal_classification', numFrames = 50) {
        return this.post('/api/v1/ai/ab-evaluate', {
            model_a_id: modelAId,
            model_b_id: modelBId,
            task_type: taskType,
            num_test_frames: numFrames
        });
    }
}

export class CameraApi extends BaseApi {
    async listCameras() {
        return this.get('/api/v1/cameras');
    }

    async getCamera(cameraId) {
        return this.get(`/api/v1/cameras/${cameraId}`);
    }

    async renameCamera(cameraId, name) {
        return this.put(`/api/v1/cameras/${cameraId}`, { name });
    }

    async disconnectCamera(cameraId) {
        return this.post(`/api/v1/cameras/${cameraId}/disconnect`);
    }

    async reconnectCamera(cameraId) {
        return this.post(`/api/v1/cameras/${cameraId}/reconnect`);
    }

    getLivePreviewUrl(cameraId) {
        return `${this.client.baseUrl}/api/v1/streams/${cameraId}/preview`;
    }
}

export class EventApi extends BaseApi {
    async listEvents(filters = {}) {
        return this.get('/api/v1/events', filters);
    }

    async getEventStats() {
        return this.get('/api/v1/events/stats');
    }

    async getEvent(eventId) {
        return this.get(`/api/v1/events/${eventId}`);
    }

    async getEventPredictions(eventId) {
        return this.get(`/api/v1/events/${eventId}/predictions`);
    }

    async acknowledge(eventId) {
        return this.post(`/api/v1/events/${eventId}/acknowledge`);
    }

    async dismiss(eventId) {
        return this.post(`/api/v1/events/${eventId}/dismiss`);
    }

    async resolve(eventId) {
        return this.post(`/api/v1/events/${eventId}/resolve`);
    }
}

export class ZoneApi extends BaseApi {
    async listZones(cameraId) {
        return this.get(`/api/v1/cameras/${cameraId}/zones`);
    }

    async createZone(cameraId, zoneData) {
        return this.post(`/api/v1/cameras/${cameraId}/zones`, zoneData);
    }

    async updateZone(zoneId, zoneData) {
        return this.put(`/api/v1/zones/${zoneId}`, zoneData);
    }

    async deleteZone(zoneId) {
        return this.delete(`/api/v1/zones/${zoneId}`);
    }
}

export class RuleApi extends BaseApi {
    async listRules() {
        return this.get('/api/v1/rules');
    }

    async getRule(ruleId) {
        return this.get(`/api/v1/rules/${ruleId}`);
    }

    async createRule(ruleData) {
        return this.post('/api/v1/rules', ruleData);
    }

    async updateRule(ruleId, ruleData) {
        return this.put(`/api/v1/rules/${ruleId}`, ruleData);
    }

    async deleteRule(ruleId) {
        return this.delete(`/api/v1/rules/${ruleId}`);
    }

    async enableRule(ruleId) {
        return this.post(`/api/v1/rules/${ruleId}/enable`);
    }

    async disableRule(ruleId) {
        return this.post(`/api/v1/rules/${ruleId}/disable`);
    }
}

export class RecordingApi extends BaseApi {
    async listRecordings(filters = {}) {
        return this.get('/api/v1/recordings', filters);
    }

    async getRecording(recordingId) {
        return this.get(`/api/v1/recordings/${recordingId}`);
    }

    getStreamUrl(recordingId) {
        return `${this.client.baseUrl}/api/v1/recordings/${recordingId}/stream`;
    }

    getThumbnailUrl(recordingId) {
        return `${this.client.baseUrl}/api/v1/recordings/${recordingId}/thumbnail`;
    }

    getDownloadUrl(recordingId) {
        return `${this.client.baseUrl}/api/v1/recordings/${recordingId}/download`;
    }

    async toggleLock(recordingId, isLocked) {
        const res = await fetch(`${this.client.baseUrl}/api/v1/recordings/${recordingId}/lock`, {
            method: 'PATCH',
            headers: this.client.getHeaders(),
            body: JSON.stringify({ is_locked: isLocked })
        });
        if (!res.ok) {
            const err = await res.json().catch(() => ({ detail: res.statusText }));
            throw new Error(err.detail || `Lock update failed: ${res.status}`);
        }
        return res.json();
    }

    async deleteRecording(recordingId) {
        return this.delete(`/api/v1/recordings/${recordingId}`);
    }
}

export class DeviceApi extends BaseApi {
    async listDevices() {
        return this.get('/api/v1/devices');
    }

    async listPendingPairings() {
        return this.get('/api/v1/devices/pairing/pending');
    }

    async revokeDevice(deviceId) {
        return this.delete(`/api/v1/devices/${deviceId}`);
    }
}

export class SystemApi extends BaseApi {
    async getHealth() {
        return this.get('/api/v1/health');
    }

    async getComponentHealth() {
        return this.get('/api/v1/system/health/components');
    }

    async getStatus() {
        return this.get('/api/v1/system/status');
    }

    async getMetrics() {
        return this.get('/api/v1/system/metrics');
    }

    async getAuditLogs(params = {}) {
        return this.get('/api/v1/system/audit', params);
    }

    async getAITelemetry() {
        return this.get('/api/v1/ai/telemetry');
    }

    async getStorage() {
        return this.get('/api/v1/system/storage');
    }

    async runRetentionCleanup(dryRun = false) {
        return this.post('/api/v1/system/storage/retention/cleanup', { dry_run: dryRun });
    }

    async getConfig(category = null) {
        return this.get('/api/v1/system/config', category ? { category } : {});
    }

    async updateConfig(category, settings) {
        return this.put(`/api/v1/system/config/${category}`, settings);
    }

    async exportConfig() {
        return this.get('/api/v1/system/config/export');
    }

    async importConfig(configData) {
        return this.post('/api/v1/system/config/import', configData);
    }

    async getActivityLogs(params = {}) {
        return this.get('/api/v1/system/activity', params);
    }

    async getNotifications() {
        return this.get('/api/v1/system/notifications');
    }

    async updateNotification(eventType, settings) {
        return this.put(`/api/v1/system/notifications/${eventType}`, settings);
    }

    async backupDatabase() {
        return this.post('/api/v1/system/backup');
    }
}

export class HubApiClient {
    constructor(baseUrl = '') {
        this.baseUrl = baseUrl || window.location.origin;
        this.authToken = localStorage.getItem('ss_auth_token') || null;

        this.cameras = new CameraApi(this);
        this.events = new EventApi(this);
        this.zones = new ZoneApi(this);
        this.rules = new RuleApi(this);
        this.recordings = new RecordingApi(this);
        this.devices = new DeviceApi(this);
        this.system = new SystemApi(this);
        this.ai = new AiApi(this);
    }

    setBaseUrl(url) {
        this.baseUrl = url.replace(/\/+$/, '');
    }

    setAuthToken(token) {
        this.authToken = token;
        if (token) {
            localStorage.setItem('ss_auth_token', token);
        } else {
            localStorage.removeItem('ss_auth_token');
        }
    }

    getHeaders() {
        const headers = {
            'Content-Type': 'application/json'
        };
        if (this.authToken) {
            headers['Authorization'] = `Bearer ${this.authToken}`;
        }
        return headers;
    }
}
