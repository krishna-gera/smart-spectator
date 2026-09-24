"use client";

import React, { useState, useEffect } from "react";
import {
  Camera,
  Eye,
  Activity,
  Settings,
  Home,
  Bell,
  Clock,
  Battery,
  ChevronRight,
  Monitor,
  Plus,
  RefreshCw,
  X,
  Link as LinkIcon,
  Shield,
  Unlink,
  CheckCircle2,
  AlertCircle
} from "lucide-react";

// API Base
const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface CameraDevice {
  id: string;
  name: string;
  host: string;
  isOnline: boolean;
  batteryLevel?: number;
  lastSeen: string;
}

interface AlertItem {
  id: string;
  severity: "INFO" | "WARNING" | "CRITICAL";
  title: string;
  message: string;
  createdAt: string;
}

interface EventItem {
  id: string;
  type: string;
  description: string;
  timestamp: string;
}

// Navigation Items
const NAV_ITEMS = [
  { id: "overview", label: "Overview", icon: Home },
  { id: "monitoring", label: "Live Feeds", icon: Monitor },
  { id: "cameras", label: "Cameras", icon: Camera },
  { id: "events", label: "Events", icon: Activity },
  { id: "alerts", label: "Alerts", icon: Bell },
  { id: "settings", label: "Settings", icon: Settings },
];

export default function DashboardPage() {
  const [activePage, setActivePage] = useState("overview");

  // Real data states (no dummy records)
  const [cameras, setCameras] = useState<CameraDevice[]>([]);
  const [alerts, setAlerts] = useState<AlertItem[]>([]);
  const [events, setEvents] = useState<EventItem[]>([]);
  const [selectedCamera, setSelectedCamera] = useState<CameraDevice | null>(null);

  // Pairing Modal state
  const [showPairModal, setShowPairModal] = useState(false);
  const [pairHost, setPairHost] = useState("");
  const [pairName, setPairName] = useState("");
  const [pairError, setPairError] = useState<string | null>(null);
  const [isTestingConnection, setIsTestingConnection] = useState(false);

  // Initial fetch for actual registered devices if API server is running
  useEffect(() => {
    let isSubscribed = true;

    async function loadData() {
      try {
        const res = await fetch(`${API_BASE}/cameras`, { signal: AbortSignal.timeout(3000) });
        if (res.ok) {
          const data = await res.json();
          if (isSubscribed && Array.isArray(data)) {
            setCameras(data);
            if (data.length > 0) setSelectedCamera(data[0]);
          }
        }
      } catch (_) {
        // Backend not currently running; state stays empty honestly
      }
    }

    loadData();
    return () => {
      isSubscribed = false;
    };
  }, []);

  // Connect / Pair new host
  const handlePairSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!pairHost.trim()) return;

    setIsTestingConnection(true);
    setPairError(null);

    let cleanHost = pairHost.trim();
    if (!cleanHost.startsWith("http://") && !cleanHost.startsWith("https://")) {
      cleanHost = `http://${cleanHost}`;
    }

    try {
      // Test ping to Cam Coder server
      const res = await fetch(`${cleanHost}/health`, { signal: AbortSignal.timeout(4000) });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);

      const newCam: CameraDevice = {
        id: `cam_${Date.now()}`,
        name: pairName.trim() || `Cam Coder (${cleanHost.replace(/https?:\/\//, "")})`,
        host: cleanHost,
        isOnline: true,
        lastSeen: new Date().toLocaleTimeString(),
      };

      setCameras((prev) => [...prev, newCam]);
      setSelectedCamera(newCam);

      // Add to event history
      setEvents((prev) => [
        {
          id: Date.now().toString(),
          type: "DEVICE_PAIRED",
          description: `Paired new Cam Coder: ${newCam.name}`,
          timestamp: new Date().toLocaleTimeString(),
        },
        ...prev,
      ]);

      setShowPairModal(false);
      setPairHost("");
      setPairName("");
    } catch (err) {
      setPairError(`Could not connect to ${cleanHost}. Ensure the camera phone is running Smart Spectator on your local network.`);
    } finally {
      setIsTestingConnection(false);
    }
  };

  const handleRemoveCamera = (id: string) => {
    setCameras((prev) => prev.filter((c) => c.id !== id));
    if (selectedCamera?.id === id) {
      setSelectedCamera(cameras.find((c) => c.id !== id) || null);
    }
  };

  return (
    <div className="flex h-screen overflow-hidden bg-black text-[#f5f5f7]">
      {/* Apple macOS-Style Sidebar */}
      <aside className="w-56 flex-shrink-0 flex flex-col bg-[#161618] border-r border-white/10">
        {/* App Title */}
        <div className="p-4 border-b border-white/10 flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <div className="w-7 h-7 rounded-md bg-[#2c2c2e] border border-white/10 flex items-center justify-center text-[#0071e3]">
              <Eye className="w-4 h-4" />
            </div>
            <span className="font-semibold text-sm tracking-tight text-white">Smart Spectator</span>
          </div>
        </div>

        {/* Navigation Items */}
        <nav className="flex-1 p-2 space-y-0.5">
          {NAV_ITEMS.map(({ id, label, icon: Icon }) => (
            <button
              key={id}
              onClick={() => setActivePage(id)}
              className={`sidebar-item ${activePage === id ? "active" : ""}`}
            >
              <Icon className="w-4 h-4 text-inherit" />
              <span>{label}</span>
            </button>
          ))}
        </nav>

        {/* Bottom Actions */}
        <div className="p-3 border-t border-white/10">
          <button
            onClick={() => setShowPairModal(true)}
            className="w-full h-8 px-3 rounded-md bg-[#0071e3] hover:bg-[#0077ed] text-white text-xs font-medium transition-colors flex items-center justify-center gap-1.5"
          >
            <Plus className="w-3.5 h-3.5" />
            Pair Camera
          </button>
        </div>
      </aside>

      {/* Main Window Area */}
      <div className="flex-1 flex flex-col min-w-0 overflow-hidden">
        {/* Top Window Bar */}
        <header className="h-12 border-b border-white/10 bg-black px-6 flex items-center justify-between flex-shrink-0">
          <div className="flex items-center gap-2 text-xs text-[#8e8e93]">
            <span>Command Center</span>
            <span className="text-[#636366]">/</span>
            <span className="text-white font-medium capitalize">{activePage}</span>
          </div>

          <div className="flex items-center gap-3">
            <span className="text-xs text-[#8e8e93]">
              {cameras.length} {cameras.length === 1 ? "device" : "devices"} connected
            </span>
          </div>
        </header>

        {/* Page Content */}
        <main className="flex-1 p-6 overflow-y-auto max-w-5xl w-full">
          {/* ──────────────── OVERVIEW PAGE ──────────────── */}
          {activePage === "overview" && (
            <div className="space-y-6">
              <div>
                <h1 className="text-xl font-bold tracking-tight text-white">System Overview</h1>
                <p className="text-xs text-[#8e8e93] mt-0.5">Local camera hosts and active observer telemetry.</p>
              </div>

              {/* Status Metric Grid */}
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                <div className="card">
                  <div className="label mb-2">Connected Hosts</div>
                  <div className="metric-value">{cameras.length}</div>
                  <div className="text-xs text-[#8e8e93] mt-1">{cameras.filter((c) => c.isOnline).length} active on LAN</div>
                </div>

                <div className="card">
                  <div className="label mb-2">Total Events</div>
                  <div className="metric-value">{events.length}</div>
                  <div className="text-xs text-[#8e8e93] mt-1">Recorded to local SQLite</div>
                </div>

                <div className="card">
                  <div className="label mb-2">Unread Alerts</div>
                  <div className="metric-value">{alerts.length}</div>
                  <div className="text-xs text-[#8e8e93] mt-1">Requiring action</div>
                </div>
              </div>

              {/* Connected Devices List or Clean Empty State */}
              <div className="card">
                <div className="flex items-center justify-between mb-4">
                  <h2 className="text-xs font-semibold uppercase tracking-wider text-[#8e8e93]">Registered Camera Devices</h2>
                  <button
                    onClick={() => setShowPairModal(true)}
                    className="text-xs text-[#0071e3] hover:underline flex items-center gap-1"
                  >
                    <Plus className="w-3.5 h-3.5" />
                    Add Device
                  </button>
                </div>

                {cameras.length === 0 ? (
                  <div className="py-12 flex flex-col items-center justify-center text-center">
                    <Camera className="w-8 h-8 text-[#636366] mb-3" />
                    <h3 className="text-sm font-semibold text-white mb-1">No Cameras Connected</h3>
                    <p className="text-xs text-[#8e8e93] max-w-sm mb-4">
                      Start the Smart Spectator app on your phone in CAM CODER mode, then add its host address to begin monitoring.
                    </p>
                    <button
                      onClick={() => setShowPairModal(true)}
                      className="btn-primary"
                    >
                      <Plus className="w-3.5 h-3.5" />
                      Pair First Device
                    </button>
                  </div>
                ) : (
                  <div className="divide-y divide-white/5">
                    {cameras.map((cam) => (
                      <div key={cam.id} className="py-3 flex items-center justify-between">
                        <div className="flex items-center gap-3">
                          <div className="w-2 h-2 rounded-full bg-[#30d158]" />
                          <div>
                            <div className="text-sm font-medium text-white">{cam.name}</div>
                            <div className="text-xs text-[#8e8e93] font-mono">{cam.host}</div>
                          </div>
                        </div>
                        <button
                          onClick={() => handleRemoveCamera(cam.id)}
                          className="text-xs text-[#8e8e93] hover:text-[#ff453a] transition-colors"
                        >
                          Remove
                        </button>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          )}

          {/* ──────────────── LIVE MONITORING PAGE ──────────────── */}
          {activePage === "monitoring" && (
            <div className="space-y-6">
              <div className="flex items-center justify-between">
                <div>
                  <h1 className="text-xl font-bold tracking-tight text-white">Live Feeds</h1>
                  <p className="text-xs text-[#8e8e93] mt-0.5">Real-time video stream from paired Cam Coder hosts.</p>
                </div>
              </div>

              {cameras.length === 0 ? (
                <div className="card py-16 flex flex-col items-center justify-center text-center">
                  <Monitor className="w-8 h-8 text-[#636366] mb-3" />
                  <h3 className="text-sm font-semibold text-white mb-1">No Active Feeds</h3>
                  <p className="text-xs text-[#8e8e93] max-w-sm mb-4">
                    Connect a Cam Coder device on your local Wi-Fi to watch live video and edge inference telemetry.
                  </p>
                  <button onClick={() => setShowPairModal(true)} className="btn-primary">
                    Pair Device
                  </button>
                </div>
              ) : (
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  {cameras.map((cam) => (
                    <div key={cam.id} className="card p-0 overflow-hidden flex flex-col">
                      <div className="p-3 bg-[#1c1c1e] border-b border-white/10 flex items-center justify-between">
                        <div className="flex items-center gap-2">
                          <span className="w-2 h-2 rounded-full bg-[#30d158]" />
                          <span className="text-xs font-semibold text-white">{cam.name}</span>
                        </div>
                        <span className="text-[11px] font-mono text-[#8e8e93]">{cam.host}</span>
                      </div>
                      <div className="aspect-[4/3] bg-black flex flex-col items-center justify-center p-4 text-center">
                        <Camera className="w-8 h-8 text-[#636366] mb-2" />
                        <span className="text-xs text-[#8e8e93]">Stream active on {cam.host}</span>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* ──────────────── CAMERAS LIST PAGE ──────────────── */}
          {activePage === "cameras" && (
            <div className="space-y-6">
              <div className="flex items-center justify-between">
                <div>
                  <h1 className="text-xl font-bold tracking-tight text-white">Registered Cameras</h1>
                  <p className="text-xs text-[#8e8e93] mt-0.5">Manage paired camera phones and connection endpoints.</p>
                </div>
                <button onClick={() => setShowPairModal(true)} className="btn-primary">
                  <Plus className="w-3.5 h-3.5" />
                  Pair New Camera
                </button>
              </div>

              {cameras.length === 0 ? (
                <div className="card py-16 flex flex-col items-center justify-center text-center">
                  <Camera className="w-8 h-8 text-[#636366] mb-3" />
                  <h3 className="text-sm font-semibold text-white mb-1">No Cameras Added</h3>
                  <p className="text-xs text-[#8e8e93] max-w-sm mb-4">
                    Add the IP address of any phone running Smart Spectator CAM CODER to register it.
                  </p>
                  <button onClick={() => setShowPairModal(true)} className="btn-primary">
                    Pair Device
                  </button>
                </div>
              ) : (
                <div className="space-y-3">
                  {cameras.map((cam) => (
                    <div key={cam.id} className="card flex items-center justify-between">
                      <div className="flex items-center gap-3">
                        <div className="w-9 h-9 rounded-md bg-[#2c2c2e] border border-white/10 flex items-center justify-center text-white">
                          <Camera className="w-4 h-4" />
                        </div>
                        <div>
                          <div className="text-sm font-semibold text-white">{cam.name}</div>
                          <div className="text-xs text-[#8e8e93] font-mono">{cam.host}</div>
                        </div>
                      </div>
                      <button
                        onClick={() => handleRemoveCamera(cam.id)}
                        className="text-xs text-[#8e8e93] hover:text-[#ff453a] transition-colors"
                      >
                        Unpair
                      </button>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* ──────────────── EVENTS PAGE ──────────────── */}
          {activePage === "events" && (
            <div className="space-y-6">
              <div>
                <h1 className="text-xl font-bold tracking-tight text-white">Event Log</h1>
                <p className="text-xs text-[#8e8e93] mt-0.5">Chronological record of detections and device heartbeats.</p>
              </div>

              {events.length === 0 ? (
                <div className="card py-16 flex flex-col items-center justify-center text-center">
                  <Activity className="w-8 h-8 text-[#636366] mb-3" />
                  <h3 className="text-sm font-semibold text-white mb-1">No Events Recorded</h3>
                  <p className="text-xs text-[#8e8e93] max-w-sm">
                    Events generated by active Cam Coder inference sessions will appear here in real time.
                  </p>
                </div>
              ) : (
                <div className="card divide-y divide-white/5 p-0 overflow-hidden">
                  {events.map((evt) => (
                    <div key={evt.id} className="p-3.5 flex items-center justify-between text-xs">
                      <div className="flex items-center gap-3">
                        <span className="font-mono text-[#8e8e93]">{evt.timestamp}</span>
                        <span className="text-white">{evt.description}</span>
                      </div>
                      <span className="font-mono text-[11px] text-[#8e8e93]">{evt.type}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* ──────────────── ALERTS PAGE ──────────────── */}
          {activePage === "alerts" && (
            <div className="space-y-6">
              <div>
                <h1 className="text-xl font-bold tracking-tight text-white">System Alerts</h1>
                <p className="text-xs text-[#8e8e93] mt-0.5">Rule violations and high-priority threshold triggers.</p>
              </div>

              {alerts.length === 0 ? (
                <div className="card py-16 flex flex-col items-center justify-center text-center">
                  <CheckCircle2 className="w-8 h-8 text-[#30d158] mb-3" />
                  <h3 className="text-sm font-semibold text-white mb-1">All Clear</h3>
                  <p className="text-xs text-[#8e8e93] max-w-sm">
                    No active threshold triggers or alerts across registered devices.
                  </p>
                </div>
              ) : (
                <div className="space-y-3">
                  {alerts.map((alert) => (
                    <div key={alert.id} className="card flex items-start gap-3">
                      <AlertCircle className="w-4 h-4 text-[#ff453a] mt-0.5" />
                      <div className="flex-1">
                        <div className="text-xs font-semibold text-white">{alert.title}</div>
                        <div className="text-xs text-[#8e8e93] mt-0.5">{alert.message}</div>
                      </div>
                      <span className="text-[11px] text-[#8e8e93] font-mono">{alert.createdAt}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* ──────────────── SETTINGS PAGE ──────────────── */}
          {activePage === "settings" && (
            <div className="space-y-6 max-w-lg">
              <div>
                <h1 className="text-xl font-bold tracking-tight text-white">Settings</h1>
                <p className="text-xs text-[#8e8e93] mt-0.5">Configuration and local server connectivity.</p>
              </div>

              <div className="card space-y-3">
                <div className="label">Network & Discovery</div>
                <div className="flex justify-between py-2 border-b border-white/5 text-xs">
                  <span className="text-[#8e8e93]">mDNS Discovery Service</span>
                  <span className="font-mono text-white">_smart-spectator._tcp</span>
                </div>
                <div className="flex justify-between py-2 border-b border-white/5 text-xs">
                  <span className="text-[#8e8e93]">Default Host Port</span>
                  <span className="font-mono text-white">8080</span>
                </div>
                <div className="flex justify-between py-2 text-xs">
                  <span className="text-[#8e8e93]">Data Sovereignty</span>
                  <span className="text-white">Local-Only (No Cloud Storage)</span>
                </div>
              </div>

              <div className="card space-y-3">
                <div className="label">About</div>
                <div className="flex justify-between py-2 border-b border-white/5 text-xs">
                  <span className="text-[#8e8e93]">Version</span>
                  <span className="font-mono text-white">0.1.0</span>
                </div>
                <div className="flex justify-between py-2 text-xs">
                  <span className="text-[#8e8e93]">License</span>
                  <span className="text-white">MIT Open Source</span>
                </div>
              </div>
            </div>
          )}
        </main>
      </div>

      {/* Apple Sheet Modal for Device Pairing */}
      {showPairModal && (
        <div
          className="fixed inset-0 z-50 bg-black/70 backdrop-blur-sm flex items-center justify-center p-4"
          onClick={() => setShowPairModal(false)}
        >
          <div
            className="w-full max-w-sm bg-[#1c1c1e] border border-white/10 rounded-2xl p-6 shadow-2xl"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex justify-between items-center mb-4">
              <h3 className="text-sm font-semibold text-white">Pair Camera Phone</h3>
              <button
                onClick={() => setShowPairModal(false)}
                className="text-[#8e8e93] hover:text-white"
                aria-label="Close"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <form onSubmit={handlePairSubmit} className="space-y-4">
              <div>
                <label className="block text-xs text-[#8e8e93] mb-1.5 font-medium">Device Name (Optional)</label>
                <input
                  type="text"
                  placeholder="e.g. Living Room Phone"
                  value={pairName}
                  onChange={(e) => setPairName(e.target.value)}
                  className="w-full h-9 px-3 bg-black border border-white/10 rounded-lg text-xs text-white placeholder-[#636366] focus:outline-none focus:border-[#0071e3]"
                />
              </div>

              <div>
                <label className="block text-xs text-[#8e8e93] mb-1.5 font-medium">Host Address / IP</label>
                <input
                  type="text"
                  placeholder="e.g. 192.168.1.50:8080"
                  value={pairHost}
                  onChange={(e) => setPairHost(e.target.value)}
                  required
                  className="w-full h-9 px-3 bg-black border border-white/10 rounded-lg text-xs font-mono text-white placeholder-[#636366] focus:outline-none focus:border-[#0071e3]"
                />
                <span className="text-[11px] text-[#636366] mt-1 block">
                  Find this address on your CAM CODER phone screen.
                </span>
              </div>

              {pairError && (
                <div className="p-2.5 rounded-lg bg-[#ff453a]/10 border border-[#ff453a]/20 text-[#ff453a] text-xs">
                  {pairError}
                </div>
              )}

              <div className="flex gap-2 pt-2">
                <button
                  type="button"
                  onClick={() => setShowPairModal(false)}
                  className="btn-secondary flex-1"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={isTestingConnection}
                  className="btn-primary flex-1 disabled:opacity-50"
                >
                  {isTestingConnection ? "Verifying..." : "Connect"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
