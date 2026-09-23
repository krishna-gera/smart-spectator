"use client";

import { useState, useEffect, useCallback } from "react";
import {
  Camera, Eye, AlertTriangle, Activity, Settings, Home, Bell,
  Clock, Wifi, Battery, ChevronRight, BarChart3, Calendar,
  Shield, Users, LogOut, TrendingUp, Zap, Monitor, RefreshCw
} from "lucide-react";
import { formatDistanceToNow, format } from "date-fns";

// ─── API Client ───────────────────────────────────────────────────────────────
const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

async function apiGet(path: string, token?: string) {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
    cache: "no-store",
  });
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return res.json();
}

// ─── Types ────────────────────────────────────────────────────────────────────
interface Camera {
  camera_id: string;
  name: string;
  is_online: boolean;
  is_monitoring: boolean;
  battery_level: number | null;
  network_type: string | null;
  analysis_interval: number;
  last_heartbeat_at: string | null;
}

interface Alert {
  id: string;
  severity: "INFO" | "WARNING" | "CRITICAL";
  title: string;
  message: string;
  is_read: boolean;
  created_at: string;
}

interface Event {
  id: string;
  type: string;
  description: string;
  confidence: number | null;
  timestamp: string;
}

// ─── Demo data for showcase ───────────────────────────────────────────────────
const DEMO_CAMERAS: Camera[] = [
  { camera_id: "cam1", name: "Kitchen Camera", is_online: true, is_monitoring: true, battery_level: 72, network_type: "wifi", analysis_interval: 2, last_heartbeat_at: new Date().toISOString() },
  { camera_id: "cam2", name: "Garage Monitor", is_online: true, is_monitoring: false, battery_level: 45, network_type: "cellular", analysis_interval: 5, last_heartbeat_at: new Date(Date.now() - 30000).toISOString() },
  { camera_id: "cam3", name: "Water Tank", is_online: false, is_monitoring: false, battery_level: null, network_type: null, analysis_interval: 10, last_heartbeat_at: null },
];

const DEMO_ALERTS: Alert[] = [
  { id: "a1", severity: "WARNING", title: "Water Level Alert", message: "Water level reached 80% in Kitchen Monitor", is_read: false, created_at: new Date(Date.now() - 120000).toISOString() },
  { id: "a2", severity: "INFO", title: "Monitoring Started", message: "Kitchen Camera began monitoring session", is_read: false, created_at: new Date(Date.now() - 600000).toISOString() },
];

const DEMO_EVENTS: Event[] = [
  { id: "e1", type: "THRESHOLD_REACHED", description: "Water level reached 81% — threshold condition met", confidence: 0.94, timestamp: new Date(Date.now() - 120000).toISOString() },
  { id: "e2", type: "STATE_CHANGED", description: "Water level rising — detected at approximately 65%", confidence: 0.89, timestamp: new Date(Date.now() - 300000).toISOString() },
  { id: "e3", type: "OBJECT_DETECTED", description: "Washing machine detected in frame", confidence: 0.97, timestamp: new Date(Date.now() - 600000).toISOString() },
  { id: "e4", type: "CONNECTION_RESTORED", description: "Kitchen Camera came online", confidence: null, timestamp: new Date(Date.now() - 1800000).toISOString() },
];

const DEMO_LIVE_STATE = {
  state: "WATER_LEVEL_RISING",
  confidence: 0.94,
  explanation: "Water level has increased to approximately 81%. Threshold condition met.",
  measurements: { water_level_percent: 81 },
  last_update: new Date().toISOString(),
  battery: 72,
  network: "wifi",
};

// ─── Sidebar ──────────────────────────────────────────────────────────────────
const navItems = [
  { id: "overview", label: "Overview", icon: Home },
  { id: "monitoring", label: "Live Monitoring", icon: Monitor },
  { id: "cameras", label: "Cameras", icon: Camera },
  { id: "events", label: "Events", icon: Activity },
  { id: "alerts", label: "Alerts", icon: Bell },
  { id: "settings", label: "Settings", icon: Settings },
];

function Sidebar({ active, onSelect }: { active: string; onSelect: (id: string) => void }) {
  return (
    <aside className="w-60 flex-shrink-0 flex flex-col border-r border-[#2A3347] bg-[#0D1119]">
      {/* Logo */}
      <div className="p-5 border-b border-[#2A3347]">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-[#4F6EF7] to-[#7B94FF] flex items-center justify-center shadow-lg shadow-blue-500/20">
            <Eye className="w-5 h-5 text-white" />
          </div>
          <div>
            <div className="font-bold text-[#F9FAFB] text-sm tracking-wide">SMART</div>
            <div className="font-bold text-[#4F6EF7] text-sm tracking-widest -mt-0.5">SPECTATOR</div>
          </div>
        </div>
      </div>

      {/* Nav */}
      <nav className="flex-1 p-3 space-y-0.5">
        {navItems.map(({ id, label, icon: Icon }) => (
          <button
            key={id}
            onClick={() => onSelect(id)}
            className={`sidebar-item w-full text-left ${active === id ? "active" : ""}`}
          >
            <Icon className="w-4 h-4 flex-shrink-0" />
            {label}
          </button>
        ))}
      </nav>

      {/* Footer */}
      <div className="p-3 border-t border-[#2A3347]">
        <div className="flex items-center gap-3 px-3 py-2">
          <div className="w-8 h-8 rounded-full bg-gradient-to-br from-[#4F6EF7] to-[#7B94FF] flex items-center justify-center text-white text-xs font-bold">
            K
          </div>
          <div className="flex-1 min-w-0">
            <div className="text-xs font-medium text-[#F9FAFB] truncate">Krishna G.</div>
            <div className="text-[11px] text-[#6B7280]">VIEW ACCESS</div>
          </div>
          <LogOut className="w-4 h-4 text-[#6B7280] cursor-pointer hover:text-[#EF4444] transition-colors" />
        </div>
      </div>
    </aside>
  );
}

// ─── Status Dot ───────────────────────────────────────────────────────────────
function StatusDot({ status }: { status: "online" | "offline" | "monitoring" | "warning" }) {
  const colors = {
    online: "bg-[#22C55E]",
    offline: "bg-[#6B7280]",
    monitoring: "bg-[#06B6D4]",
    warning: "bg-[#F59E0B]",
  };

  const glow = {
    online: "shadow-[0_0_6px_#22C55E80]",
    monitoring: "shadow-[0_0_6px_#06B6D480]",
    offline: "",
    warning: "shadow-[0_0_6px_#F59E0B80]",
  };

  return (
    <span className={`inline-block w-2 h-2 rounded-full ${colors[status]} ${glow[status]}`} />
  );
}

// ─── Confidence Bar ───────────────────────────────────────────────────────────
function ConfidenceBar({ value }: { value: number }) {
  const pct = Math.round(value * 100);
  const color = pct >= 75 ? "#22C55E" : pct >= 50 ? "#F59E0B" : "#EF4444";
  return (
    <div className="flex items-center gap-3">
      <div className="flex-1 h-1.5 bg-[#1A2235] rounded-full overflow-hidden">
        <div
          className="h-full rounded-full transition-all duration-700"
          style={{ width: `${pct}%`, backgroundColor: color }}
        />
      </div>
      <span className="text-xs font-bold w-8 text-right" style={{ color }}>{pct}%</span>
    </div>
  );
}

// ─── Overview Page ────────────────────────────────────────────────────────────
function OverviewPage({ cameras, alerts, events, liveState }: {
  cameras: Camera[];
  alerts: Alert[];
  events: Event[];
  liveState: typeof DEMO_LIVE_STATE;
}) {
  const onlineCams = cameras.filter(c => c.is_online).length;
  const monitoringCams = cameras.filter(c => c.is_monitoring).length;
  const unreadAlerts = alerts.filter(a => !a.is_read).length;

  return (
    <div className="p-6 space-y-6 animate-slide-in">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-[#F9FAFB]">Overview</h1>
        <p className="text-[#9CA3AF] text-sm mt-1">
          {format(new Date(), "EEEE, MMMM d")} · {cameras.length} camera{cameras.length !== 1 ? "s" : ""} registered
        </p>
      </div>

      {/* Stats Row */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        {[
          { label: "Active Cameras", value: onlineCams, icon: Camera, color: "#22C55E", sub: `of ${cameras.length} total` },
          { label: "Monitoring", value: monitoringCams, icon: Activity, color: "#06B6D4", sub: "sessions active" },
          { label: "Unread Alerts", value: unreadAlerts, icon: Bell, color: "#F59E0B", sub: "need attention" },
          { label: "AI Confidence", value: `${Math.round(liveState.confidence * 100)}%`, icon: Zap, color: "#4F6EF7", sub: "last analysis" },
        ].map(({ label, value, icon: Icon, color, sub }) => (
          <div key={label} className="card">
            <div className="flex items-start justify-between mb-3">
              <div className="p-2 rounded-lg" style={{ backgroundColor: `${color}18` }}>
                <Icon className="w-4 h-4" style={{ color }} />
              </div>
            </div>
            <div className="metric-value">{value}</div>
            <div className="label mt-1">{label}</div>
            <div className="text-[#6B7280] text-xs mt-0.5">{sub}</div>
          </div>
        ))}
      </div>

      {/* Main content: Live AI + Recent Events */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* Live AI State */}
        <div className="card space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <div className="label">Live AI State</div>
              <div className="text-[#F9FAFB] font-semibold mt-0.5">Kitchen Camera</div>
            </div>
            <div className="flex items-center gap-2 text-[11px] text-[#06B6D4] font-semibold">
              <div className="w-1.5 h-1.5 rounded-full bg-[#06B6D4] animate-pulse" />
              LIVE
            </div>
          </div>
          <div className="bg-[#1A2235] rounded-xl p-4 space-y-3">
            <div className="flex items-center justify-between">
              <div className="text-[#9CA3AF] text-xs">STATE</div>
              <div className="text-[#F9FAFB] font-bold text-sm">{liveState.state.replace(/_/g, " ")}</div>
            </div>
            <div className="space-y-1">
              <div className="text-[#9CA3AF] text-xs">CONFIDENCE</div>
              <ConfidenceBar value={liveState.confidence} />
            </div>
            {Object.keys(liveState.measurements).length > 0 && (
              <div className="flex flex-wrap gap-2">
                {Object.entries(liveState.measurements).map(([k, v]) => (
                  <span key={k} className="text-[11px] px-2 py-1 rounded-lg bg-[#4F6EF7]/10 text-[#4F6EF7] border border-[#4F6EF7]/20">
                    {k.replace(/_/g, " ")}: {String(v)}
                  </span>
                ))}
              </div>
            )}
            <p className="text-[#9CA3AF] text-xs leading-relaxed">{liveState.explanation}</p>
          </div>
          <div className="flex items-center gap-4 text-xs text-[#6B7280]">
            <div className="flex items-center gap-1">
              <Clock className="w-3 h-3" />
              {formatDistanceToNow(new Date(liveState.last_update), { addSuffix: true })}
            </div>
            {liveState.battery && (
              <div className="flex items-center gap-1">
                <Battery className="w-3 h-3" />
                {liveState.battery}%
              </div>
            )}
            <div className="flex items-center gap-1">
              <Wifi className="w-3 h-3" />
              {liveState.network}
            </div>
          </div>
        </div>

        {/* Recent Events */}
        <div className="card space-y-3">
          <div className="flex items-center justify-between">
            <div className="label">Recent Events</div>
            <span className="text-[11px] text-[#4F6EF7] cursor-pointer hover:underline">View all</span>
          </div>
          <div className="space-y-2">
            {events.map((event, i) => {
              const isAlert = event.type.includes("ALERT") || event.type.includes("THRESHOLD");
              return (
                <div key={event.id} className="flex items-start gap-3 p-3 rounded-xl bg-[#1A2235] hover:bg-[#1E2843] transition-colors cursor-pointer">
                  <div className={`w-1.5 h-1.5 rounded-full mt-1.5 flex-shrink-0 ${isAlert ? "bg-[#F59E0B]" : "bg-[#4F6EF7]"}`} />
                  <div className="flex-1 min-w-0">
                    <div className="text-[#F9FAFB] text-xs leading-relaxed line-clamp-1">{event.description}</div>
                    <div className="flex items-center gap-3 mt-0.5">
                      {event.confidence && (
                        <span className="text-[11px] text-[#6B7280]">{Math.round(event.confidence * 100)}% confidence</span>
                      )}
                      <span className="text-[11px] text-[#6B7280]">
                        {formatDistanceToNow(new Date(event.timestamp), { addSuffix: true })}
                      </span>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      </div>

      {/* Cameras */}
      <div className="card space-y-4">
        <div className="label">Camera Status</div>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
          {cameras.map((cam) => {
            const statusKey = cam.is_monitoring ? "monitoring" : cam.is_online ? "online" : "offline";
            return (
              <div key={cam.camera_id}
                className="bg-[#1A2235] rounded-xl p-4 flex items-start gap-3 hover:bg-[#1E2843] transition-colors cursor-pointer">
                <div className={`p-2 rounded-lg ${cam.is_online ? "bg-[#22C55E18]" : "bg-[#1A2235]"}`}>
                  <Camera className={`w-4 h-4 ${cam.is_online ? "text-[#22C55E]" : "text-[#6B7280]"}`} />
                </div>
                <div className="flex-1 min-w-0">
                  <div className="text-[#F9FAFB] text-sm font-medium truncate">{cam.name}</div>
                  <div className="flex items-center gap-1.5 mt-0.5">
                    <StatusDot status={statusKey as "online" | "offline" | "monitoring"} />
                    <span className={`text-[11px] font-semibold ${
                      cam.is_monitoring ? "text-[#06B6D4]" : cam.is_online ? "text-[#22C55E]" : "text-[#6B7280]"
                    }`}>
                      {cam.is_monitoring ? "MONITORING" : cam.is_online ? "ONLINE" : "OFFLINE"}
                    </span>
                  </div>
                  <div className="flex items-center gap-2 mt-1">
                    {cam.battery_level !== null && (
                      <span className="text-[10px] text-[#6B7280] flex items-center gap-0.5">
                        <Battery className="w-2.5 h-2.5" />{cam.battery_level}%
                      </span>
                    )}
                    <span className="text-[10px] text-[#6B7280]">Every {cam.analysis_interval}s</span>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}

// ─── Live Monitoring Page ─────────────────────────────────────────────────────
function LiveMonitoringPage({ camera, liveState, events }: {
  camera: Camera;
  liveState: typeof DEMO_LIVE_STATE;
  events: Event[];
}) {
  return (
    <div className="p-6 space-y-6 animate-slide-in">
      <div>
        <h1 className="text-2xl font-bold text-[#F9FAFB]">Live Monitoring</h1>
        <p className="text-[#9CA3AF] text-sm mt-1">{camera.name}</p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {/* Main AI State */}
        <div className="lg:col-span-2 space-y-4">
          {/* Camera placeholder */}
          <div className="card aspect-video flex items-center justify-center bg-[#0A0D14] relative overflow-hidden">
            <div className="absolute inset-0 bg-gradient-to-br from-[#0A0D14] via-[#111827] to-[#0A0D14]" />
            <div className="relative z-10 text-center">
              <Camera className="w-12 h-12 text-[#2A3347] mx-auto mb-3" />
              <div className="text-[#4B5563] text-sm">Camera stream not available in web dashboard.</div>
              <div className="text-[#6B7280] text-xs mt-1">Use the mobile app to view the live feed.</div>
            </div>
            {/* Recording indicator */}
            <div className="absolute top-4 right-4 flex items-center gap-2 bg-black/60 px-3 py-1.5 rounded-lg">
              <div className="w-2 h-2 rounded-full bg-[#EF4444] animate-pulse" />
              <span className="text-white text-xs font-semibold">MONITORING</span>
            </div>
          </div>

          {/* AI Result */}
          <div className="card space-y-4">
            <div className="flex items-center justify-between">
              <div className="label">AI Analysis</div>
              <span className="text-[11px] px-2 py-0.5 rounded-md bg-[#F59E0B]/10 text-[#F59E0B] border border-[#F59E0B]/20 font-semibold">
                CONDITION MET
              </span>
            </div>

            <div>
              <div className="text-[#F9FAFB] text-xl font-bold">{liveState.state.replace(/_/g, " ")}</div>
              <p className="text-[#9CA3AF] text-sm mt-2 leading-relaxed">{liveState.explanation}</p>
            </div>

            <div className="space-y-2">
              <div className="flex items-center justify-between text-xs text-[#9CA3AF]">
                <span>CONFIDENCE</span>
                <span className="font-semibold text-[#22C55E]">{Math.round(liveState.confidence * 100)}%</span>
              </div>
              <div className="h-2 bg-[#1A2235] rounded-full overflow-hidden">
                <div
                  className="h-full rounded-full transition-all duration-700 bg-[#22C55E]"
                  style={{ width: `${Math.round(liveState.confidence * 100)}%` }}
                />
              </div>
            </div>

            {Object.entries(liveState.measurements).map(([k, v]) => (
              <div key={k} className="flex items-center justify-between py-2 border-t border-[#2A3347]">
                <span className="text-[#9CA3AF] text-xs">{k.replace(/_/g, " ").toUpperCase()}</span>
                <span className="text-[#F9FAFB] font-bold">{String(v)}%</span>
              </div>
            ))}
          </div>
        </div>

        {/* Right: Task + Timeline */}
        <div className="space-y-4">
          <div className="card space-y-3">
            <div className="label">Monitoring Task</div>
            <div>
              <div className="text-[#F9FAFB] font-semibold text-sm">Monitor washing machine water level</div>
              <div className="text-[#9CA3AF] text-xs mt-1">Tell me when water level reaches 80%</div>
            </div>
            <div className="space-y-2">
              {[
                { label: "Camera", value: camera.name },
                { label: "Status", value: "MONITORING" },
                { label: "Interval", value: `${camera.analysis_interval}s` },
                { label: "Battery", value: `${camera.battery_level ?? "N/A"}%` },
              ].map(({ label, value }) => (
                <div key={label} className="flex items-center justify-between text-xs py-1.5 border-b border-[#2A3347] last:border-0">
                  <span className="text-[#6B7280]">{label}</span>
                  <span className="text-[#F9FAFB] font-medium">{value}</span>
                </div>
              ))}
            </div>
          </div>

          {/* Timeline */}
          <div className="card space-y-3">
            <div className="label">Event Timeline</div>
            <div className="space-y-3">
              {events.slice(0, 5).map((event) => (
                <div key={event.id} className="flex gap-3">
                  <div className="flex flex-col items-center">
                    <div className={`w-2 h-2 rounded-full mt-1 ${
                      event.type.includes("THRESHOLD") ? "bg-[#F59E0B]" : "bg-[#4F6EF7]"
                    }`} />
                    <div className="w-px flex-1 bg-[#2A3347] mt-1" />
                  </div>
                  <div className="pb-3 flex-1 min-w-0">
                    <div className="text-[#F9FAFB] text-xs leading-relaxed line-clamp-2">{event.description}</div>
                    <div className="text-[#6B7280] text-[11px] mt-0.5">
                      {formatDistanceToNow(new Date(event.timestamp), { addSuffix: true })}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

// ─── Alerts Page ──────────────────────────────────────────────────────────────
function AlertsPage({ alerts }: { alerts: Alert[] }) {
  const severityConfig = {
    CRITICAL: { color: "#EF4444", bg: "#EF444410", border: "#EF444440", icon: AlertTriangle },
    WARNING: { color: "#F59E0B", bg: "#F59E0B10", border: "#F59E0B40", icon: AlertTriangle },
    INFO: { color: "#4F6EF7", bg: "#4F6EF710", border: "#4F6EF740", icon: Bell },
  };

  return (
    <div className="p-6 space-y-6 animate-slide-in">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-[#F9FAFB]">Alerts</h1>
          <p className="text-[#9CA3AF] text-sm mt-1">{alerts.filter(a => !a.is_read).length} unread</p>
        </div>
        <button className="btn-ghost flex items-center gap-2">
          <RefreshCw className="w-4 h-4" /> Refresh
        </button>
      </div>

      <div className="space-y-3">
        {alerts.map((alert) => {
          const cfg = severityConfig[alert.severity];
          const Icon = cfg.icon;
          return (
            <div
              key={alert.id}
              className="rounded-2xl p-5 border cursor-pointer hover:opacity-90 transition-opacity"
              style={{ backgroundColor: cfg.bg, borderColor: cfg.border }}
            >
              <div className="flex items-start gap-4">
                <div className="p-2 rounded-xl" style={{ backgroundColor: `${cfg.color}20` }}>
                  <Icon className="w-5 h-5" style={{ color: cfg.color }} />
                </div>
                <div className="flex-1">
                  <div className="flex items-center gap-2 mb-1">
                    <span className="font-semibold text-sm text-[#F9FAFB]">{alert.title}</span>
                    {!alert.is_read && (
                      <span className="w-1.5 h-1.5 rounded-full" style={{ backgroundColor: cfg.color }} />
                    )}
                  </div>
                  <p className="text-[#9CA3AF] text-sm">{alert.message}</p>
                  <div className="text-[#6B7280] text-xs mt-2">
                    {formatDistanceToNow(new Date(alert.created_at), { addSuffix: true })}
                  </div>
                </div>
                <span className="text-[11px] font-bold px-2 py-0.5 rounded-md" style={{ color: cfg.color, backgroundColor: `${cfg.color}15` }}>
                  {alert.severity}
                </span>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ─── Main App ─────────────────────────────────────────────────────────────────
export default function DashboardPage() {
  const [activePage, setActivePage] = useState("overview");
  const [cameras] = useState<Camera[]>(DEMO_CAMERAS);
  const [alerts] = useState<Alert[]>(DEMO_ALERTS);
  const [events] = useState<Event[]>(DEMO_EVENTS);
  const [liveState] = useState(DEMO_LIVE_STATE);

  return (
    <div className="flex h-screen overflow-hidden bg-[#0A0D14]">
      <Sidebar active={activePage} onSelect={setActivePage} />

      {/* Main content */}
      <main className="flex-1 overflow-y-auto">
        {/* Top bar */}
        <div className="sticky top-0 z-10 bg-[#0A0D14]/80 backdrop-blur border-b border-[#2A3347] px-6 py-3 flex items-center justify-between">
          <div className="flex items-center gap-2 text-sm text-[#9CA3AF]">
            <span className="text-[#6B7280]">Smart Spectator</span>
            <span className="text-[#4B5563]">/</span>
            <span className="text-[#F9FAFB] font-medium capitalize">{activePage.replace("-", " ")}</span>
          </div>
          <div className="flex items-center gap-3">
            {/* Live indicator */}
            <div className="flex items-center gap-2 text-[11px] font-semibold text-[#06B6D4]">
              <div className="w-1.5 h-1.5 rounded-full bg-[#06B6D4] animate-pulse" />
              LIVE
            </div>
            <div className="relative">
              <Bell className="w-4 h-4 text-[#9CA3AF] cursor-pointer hover:text-[#F9FAFB]" />
              {alerts.filter(a => !a.is_read).length > 0 && (
                <div className="absolute -top-1 -right-1 w-3.5 h-3.5 rounded-full bg-[#EF4444] text-white text-[9px] font-bold flex items-center justify-center">
                  {alerts.filter(a => !a.is_read).length}
                </div>
              )}
            </div>
          </div>
        </div>

        {/* Pages */}
        {activePage === "overview" && (
          <OverviewPage cameras={cameras} alerts={alerts} events={events} liveState={liveState} />
        )}
        {activePage === "monitoring" && (
          <LiveMonitoringPage camera={cameras[0]} liveState={liveState} events={events} />
        )}
        {activePage === "alerts" && <AlertsPage alerts={alerts} />}
        {activePage === "cameras" && (
          <div className="p-6 animate-slide-in">
            <h1 className="text-2xl font-bold text-[#F9FAFB] mb-6">Cameras</h1>
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
              {cameras.map((cam) => (
                <div key={cam.camera_id} className="card flex items-center gap-4 cursor-pointer hover:border-[#4F6EF7]/50 transition-colors">
                  <div className={`p-3 rounded-xl ${cam.is_online ? "bg-[#22C55E18]" : "bg-[#1A2235]"}`}>
                    <Camera className={`w-6 h-6 ${cam.is_online ? "text-[#22C55E]" : "text-[#6B7280]"}`} />
                  </div>
                  <div className="flex-1">
                    <div className="text-[#F9FAFB] font-semibold">{cam.name}</div>
                    <div className="flex items-center gap-2 mt-1">
                      <StatusDot status={cam.is_monitoring ? "monitoring" : cam.is_online ? "online" : "offline"} />
                      <span className="text-xs text-[#9CA3AF]">
                        {cam.is_monitoring ? "Monitoring" : cam.is_online ? "Online" : "Offline"}
                      </span>
                      {cam.battery_level && (
                        <span className="text-xs text-[#6B7280] flex items-center gap-1">
                          · <Battery className="w-3 h-3" /> {cam.battery_level}%
                        </span>
                      )}
                    </div>
                  </div>
                  <ChevronRight className="w-4 h-4 text-[#6B7280]" />
                </div>
              ))}
            </div>
          </div>
        )}
        {activePage === "events" && (
          <div className="p-6 animate-slide-in">
            <h1 className="text-2xl font-bold text-[#F9FAFB] mb-6">Events</h1>
            <div className="space-y-3">
              {events.map((event) => (
                <div key={event.id} className="card flex items-start gap-4 hover:border-[#4F6EF7]/30 transition-colors cursor-pointer">
                  <div className={`w-2 h-2 rounded-full mt-2 flex-shrink-0 ${
                    event.type.includes("THRESHOLD") || event.type.includes("ALERT") ? "bg-[#F59E0B]" : "bg-[#4F6EF7]"
                  }`} />
                  <div className="flex-1">
                    <div className="flex items-center gap-2 mb-1">
                      <span className="text-[11px] font-semibold text-[#9CA3AF] tracking-wide">
                        {event.type.replace(/_/g, " ")}
                      </span>
                    </div>
                    <div className="text-[#F9FAFB] text-sm">{event.description}</div>
                    <div className="flex items-center gap-3 mt-2 text-xs text-[#6B7280]">
                      {event.confidence && <span>{Math.round(event.confidence * 100)}% confidence</span>}
                      <span>{formatDistanceToNow(new Date(event.timestamp), { addSuffix: true })}</span>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
        {activePage === "settings" && (
          <div className="p-6 animate-slide-in">
            <h1 className="text-2xl font-bold text-[#F9FAFB] mb-6">Settings</h1>
            <div className="max-w-xl space-y-4">
              {[
                { label: "Account", items: ["Profile", "Change Password"] },
                { label: "AI Configuration", items: ["Vision Provider", "Analysis Interval", "Confidence Threshold"] },
                { label: "Privacy", items: ["Privacy Mode", "Frame Retention", "Data Export"] },
                { label: "Notifications", items: ["Push Notifications", "Email Notifications"] },
              ].map(({ label, items }) => (
                <div key={label} className="card space-y-1">
                  <div className="label mb-3">{label}</div>
                  {items.map((item) => (
                    <div key={item} className="flex items-center justify-between py-2.5 border-b border-[#2A3347] last:border-0 cursor-pointer hover:text-[#F9FAFB] text-[#9CA3AF] transition-colors text-sm">
                      {item}
                      <ChevronRight className="w-4 h-4" />
                    </div>
                  ))}
                </div>
              ))}
            </div>
          </div>
        )}
      </main>
    </div>
  );
}
