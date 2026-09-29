/**
 * Smart Spectator Client - Master Application Orchestrator
 * Coordinates state, APIs, WebSocket stream, screen routing, and UI lifecycle.
 * Conforms to Sections 33-57, 76-81 of Phase 5 specification.
 */

import { HubApiClient } from './api.js';
import { EventStreamClient } from './ws.js';
import {
    connectionStore,
    cameraStore,
    eventStore,
    ruleStore,
    zoneStore,
    recordingStore,
    deviceStore,
    systemStore
} from './state.js';

import { renderDashboard } from './components/dashboard.js';
import { renderCameras } from './components/cameras.js';
import { renderLiveView } from './components/live_view.js';
import { renderEvents } from './components/events.js';
import { renderEventDetail } from './components/event_detail.js';
import { renderRecordings } from './components/recordings.js';
import { renderZoneEditor } from './components/zones.js';
import { renderRules } from './components/rules.js';
import { renderDevices } from './components/devices.js';
import { renderAIStatus } from './components/ai_status.js';
import { renderSettings } from './components/settings.js';

class SmartSpectatorApp {
    constructor() {
        const customUrl = localStorage.getItem('ss_hub_url') || window.location.origin;
        this.api = new HubApiClient(customUrl);
        this.ws = new EventStreamClient(this.api);

        this.currentScreen = 'dashboard';
        this.screenParams = {};

        this.stores = {
            connection: connectionStore,
            camera: cameraStore,
            event: eventStore,
            rule: ruleStore,
            zone: zoneStore,
            recording: recordingStore,
            device: deviceStore,
            system: systemStore
        };

        this.actions = this.bindActions();
    }

    async init() {
        console.log('[App] Initializing Smart Spectator Monitoring Client...');

        // 1. Setup Navigation listener
        this.setupNavigation();

        // 2. Setup WebSocket event stream & state bindings
        this.setupWebSocket();

        // 3. Initial Data Fetch
        await this.refreshAll();

        // 4. Render initial screen
        this.renderCurrentScreen();

        // 5. Connect WebSocket
        this.ws.connect();
    }

    setupNavigation() {
        document.querySelectorAll('.nav-link').forEach(link => {
            link.addEventListener('click', (e) => {
                e.preventDefault();
                const screen = link.getAttribute('data-screen');
                this.navigateTo(screen);
            });
        });
    }

    navigateTo(screen, params = {}) {
        this.currentScreen = screen;
        this.screenParams = params;

        // Update active nav link
        document.querySelectorAll('.nav-link').forEach(link => {
            if (link.getAttribute('data-screen') === screen) {
                link.classList.add('active');
            } else {
                link.classList.remove('active');
            }
        });

        this.renderCurrentScreen();
    }

    renderCurrentScreen() {
        const container = document.getElementById('main-content');
        if (!container) return;

        switch (this.currentScreen) {
            case 'dashboard':
                renderDashboard(container, this.stores, this.actions);
                break;
            case 'cameras':
                renderCameras(container, this.stores, this.actions);
                break;
            case 'live_view':
                renderLiveView(container, this.stores, this.actions, this.screenParams.cameraId);
                break;
            case 'events':
                renderEvents(container, this.stores, this.actions);
                break;
            case 'event_detail':
                renderEventDetail(container, this.stores, this.actions, this.screenParams.eventId);
                break;
            case 'recordings':
                renderRecordings(container, this.stores, this.actions);
                break;
            case 'zones':
                renderZoneEditor(container, this.stores, this.actions, this.screenParams.cameraId);
                break;
            case 'rules':
                renderRules(container, this.stores, this.actions);
                break;
            case 'devices':
                renderDevices(container, this.stores, this.actions);
                break;
            case 'ai_status':
                renderAIStatus(container, this.stores, this.actions);
                break;
            case 'settings':
                renderSettings(container, this.stores, this.actions);
                break;
            default:
                renderDashboard(container, this.stores, this.actions);
        }
    }

    setupWebSocket() {
        const connBadge = document.getElementById('hub-connection-badge');
        const connText = document.getElementById('hub-connection-text');

        this.ws.onStatusChange((status, details) => {
            connectionStore.set({ status, statusMessage: details });
            if (connBadge && connText) {
                connBadge.className = `status-indicator status-${status}`;
                connText.textContent = status.toUpperCase();
            }
            const banner = document.getElementById('reconnect-banner');
            if (banner) {
                if (status === 'reconnecting' || status === 'disconnected') {
                    banner.style.display = 'block';
                    banner.textContent = `⚠️ Hub Disconnected. ${details || 'Reconnecting...'}`;
                } else {
                    banner.style.display = 'none';
                }
            }
        });

        // Push handlers (Section 32)
        this.ws.on('event_created', (data) => {
            const current = eventStore.get().events;
            eventStore.set({
                events: [data, ...current.filter(e => e.event_id !== data.event_id)],
                unreadCount: eventStore.get().unreadCount + 1
            });
            this.showToast(`🚨 New Event: ${data.event_type.replace(/_/g, ' ')} on ${data.camera_id}`, data.severity);
            if (this.currentScreen === 'dashboard' || this.currentScreen === 'events') {
                this.renderCurrentScreen();
            }
        });

        this.ws.on('event_updated', (data) => {
            const current = eventStore.get().events;
            const idx = current.findIndex(e => e.event_id === data.event_id);
            if (idx >= 0) {
                current[idx] = data;
                eventStore.set({ events: [...current] });
            }
            if (this.currentScreen === 'dashboard' || this.currentScreen === 'events' || this.currentScreen === 'event_detail') {
                this.renderCurrentScreen();
            }
        });

        this.ws.on('event_resolved', (data) => {
            const current = eventStore.get().events;
            const idx = current.findIndex(e => e.event_id === data.event_id);
            if (idx >= 0) {
                current[idx] = data;
                eventStore.set({ events: [...current] });
            }
            if (this.currentScreen === 'dashboard' || this.currentScreen === 'events' || this.currentScreen === 'event_detail') {
                this.renderCurrentScreen();
            }
        });

        this.ws.on('recording_created', (data) => {
            this.showToast(`📹 Video Clip Saved for ${data.event_id}`, 'info');
            this.refreshRecordings();
        });

        this.ws.on('camera_connected', (data) => {
            this.showToast(`📹 Camera Connected: ${data.camera_id}`, 'info');
            this.refreshCameras();
        });

        this.ws.on('camera_disconnected', (data) => {
            this.showToast(`⚠️ Camera Disconnected: ${data.camera_id}`, 'high');
            this.refreshCameras();
        });
    }

    showToast(message, severity = 'info') {
        const toastContainer = document.getElementById('toast-container');
        if (!toastContainer) return;

        const toast = document.createElement('div');
        toast.className = `toast toast-${severity}`;
        toast.textContent = message;
        toastContainer.appendChild(toast);

        setTimeout(() => {
            toast.style.opacity = '0';
            setTimeout(() => toast.remove(), 400);
        }, 4000);
    }

    bindActions() {
        return {
            navigateTo: (screen, params) => this.navigateTo(screen, params),
            openLiveView: (cameraId) => this.navigateTo('live_view', { cameraId }),
            openEventDetail: (eventId) => this.navigateTo('event_detail', { eventId }),
            openZoneEditor: (cameraId) => this.navigateTo('zones', { cameraId }),
            refreshAll: () => this.refreshAll(),
            refreshCameras: () => this.refreshCameras(),
            refreshEvents: () => this.refreshEvents(),
            refreshRecordings: () => this.refreshRecordings(),
            refreshZones: (camId) => this.refreshZones(camId),
            refreshRules: () => this.refreshRules(),
            refreshDevices: () => this.refreshDevices(),
            refreshSystem: () => this.refreshSystem(),
            acknowledgeEvent: async (evId) => {
                await this.api.events.acknowledge(evId);
                await this.refreshEvents();
            },
            dismissEvent: async (evId) => {
                await this.api.events.dismiss(evId);
                await this.refreshEvents();
            },
            resolveEvent: async (evId) => {
                await this.api.events.resolve(evId);
                await this.refreshEvents();
            },
            createZone: async (camId, data) => this.api.zones.createZone(camId, data),
            deleteZone: async (zoneId) => this.api.zones.deleteZone(zoneId),
            createRule: async (data) => this.api.rules.createRule(data),
            deleteRule: async (ruleId) => this.api.rules.deleteRule(ruleId),
            enableRule: async (ruleId) => this.api.rules.enableRule(ruleId),
            disableRule: async (ruleId) => this.api.rules.disableRule(ruleId),
            deleteRecording: async (recId) => this.api.recordings.deleteRecording(recId),
            revokeDevice: async (devId) => this.api.devices.revokeDevice(devId),
            setEventFilters: (filters) => {
                eventStore.set({ filters });
                this.refreshEvents();
            },
            updateHubUrl: (url) => {
                this.api.setBaseUrl(url);
                this.ws.disconnect();
                this.ws.connect();
                this.refreshAll();
            }
        };
    }

    async refreshAll() {
        await Promise.allSettled([
            this.refreshCameras(),
            this.refreshEvents(),
            this.refreshRecordings(),
            this.refreshRules(),
            this.refreshDevices(),
            this.refreshSystem()
        ]);
        this.renderCurrentScreen();
    }

    async refreshCameras() {
        try {
            const cameras = await this.api.cameras.listCameras();
            cameraStore.set({ cameras });
        } catch (e) {
            console.error('[App] Failed to fetch cameras:', e);
        }
    }

    async refreshEvents() {
        try {
            const filters = eventStore.get().filters;
            const events = await this.api.events.listEvents(filters);
            eventStore.set({ events });
        } catch (e) {
            console.error('[App] Failed to fetch events:', e);
        }
    }

    async refreshRecordings() {
        try {
            const recordings = await this.api.recordings.listRecordings();
            recordingStore.set({ recordings });
        } catch (e) {
            console.error('[App] Failed to fetch recordings:', e);
        }
    }

    async refreshZones(cameraId) {
        if (!cameraId) return;
        try {
            const zones = await this.api.zones.listZones(cameraId);
            const current = zoneStore.get().zones;
            zoneStore.set({
                zones: { ...current, [cameraId]: zones }
            });
        } catch (e) {
            console.error(`[App] Failed to fetch zones for ${cameraId}:`, e);
        }
    }

    async refreshRules() {
        try {
            const rules = await this.api.rules.listRules();
            ruleStore.set({ rules });
        } catch (e) {
            console.error('[App] Failed to fetch rules:', e);
        }
    }

    async refreshDevices() {
        try {
            const [devices, pending] = await Promise.all([
                this.api.devices.listDevices(),
                this.api.devices.listPendingPairings()
            ]);
            deviceStore.set({ devices, pendingPairings: pending });
        } catch (e) {
            console.error('[App] Failed to fetch devices:', e);
        }
    }

    async refreshSystem() {
        try {
            const [health, compHealth, metrics, aiTele] = await Promise.all([
                this.api.system.getHealth(),
                this.api.system.getComponentHealth(),
                this.api.system.getMetrics(),
                this.api.system.getAITelemetry()
            ]);
            systemStore.set({
                health,
                componentHealth: compHealth,
                metrics,
                aiTelemetry: aiTele
            });
        } catch (e) {
            console.error('[App] Failed to fetch system status:', e);
        }
    }
}

// Instantiate and launch client on window load
window.addEventListener('DOMContentLoaded', () => {
    window.app = new SmartSpectatorApp();
    window.app.init();
});
