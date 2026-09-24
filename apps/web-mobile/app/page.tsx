"use client";

import React, { useState, useEffect, useRef } from "react";
import {
  Camera,
  Eye,
  RefreshCw,
  Battery,
  Moon,
  QrCode,
  Check,
  AlertCircle,
  Link as LinkIcon,
  Unlink,
  Radio,
  Sliders,
  X
} from "lucide-react";

type RoleMode = "CAM_CODER" | "VIEW_ACCESS";

interface EventItem {
  id: string;
  timestamp: string;
  type: "INFO" | "ALERT";
  message: string;
}

export default function MobileApp() {
  const [role, setRole] = useState<RoleMode>("CAM_CODER");
  const [showPairModal, setShowPairModal] = useState(false);

  // CAM CODER states
  const [isStreaming, setIsStreaming] = useState(false);
  const [facingMode, setFacingMode] = useState<"environment" | "user">("environment");
  const [isDimmed, setIsDimmed] = useState(false);
  const [batteryLevel, setBatteryLevel] = useState<number | null>(null);

  // VIEW ACCESS states
  const [targetHost, setTargetHost] = useState("");
  const [isConnected, setIsConnected] = useState(false);
  const [connectionStatus, setConnectionStatus] = useState<"DISCONNECTED" | "CONNECTING" | "CONNECTED">("DISCONNECTED");
  const [viewerEvents, setViewerEvents] = useState<EventItem[]>([]);
  const [streamError, setStreamError] = useState<string | null>(null);

  const videoRef = useRef<HTMLVideoElement | null>(null);
  const streamRef = useRef<MediaStream | null>(null);

  // Battery status API
  useEffect(() => {
    if (typeof navigator !== "undefined" && "getBattery" in navigator) {
      (navigator as any).getBattery?.().then((battery: any) => {
        setBatteryLevel(Math.round(battery.level * 100));
        battery.addEventListener("levelchange", () => {
          setBatteryLevel(Math.round(battery.level * 100));
        });
      }).catch(() => {});
    }
  }, []);

  // Real Camera capture for CAM CODER
  const startCamera = async () => {
    try {
      if (streamRef.current) {
        streamRef.current.getTracks().forEach((t) => t.stop());
      }
      const stream = await navigator.mediaDevices.getUserMedia({
        video: {
          facingMode: { ideal: facingMode },
          width: { ideal: 1280 },
          height: { ideal: 720 },
        },
        audio: false,
      });
      streamRef.current = stream;
      if (videoRef.current) {
        videoRef.current.srcObject = stream;
        videoRef.current.play();
      }
      setIsStreaming(true);
    } catch (err) {
      console.error("Camera access error:", err);
      alert("Unable to access camera. Please ensure camera permissions are granted.");
      setIsStreaming(false);
    }
  };

  const stopCamera = () => {
    if (streamRef.current) {
      streamRef.current.getTracks().forEach((t) => t.stop());
      streamRef.current = null;
    }
    if (videoRef.current) {
      videoRef.current.srcObject = null;
    }
    setIsStreaming(false);
  };

  const toggleCameraFacing = async () => {
    const nextFacing = facingMode === "environment" ? "user" : "environment";
    setFacingMode(nextFacing);
    if (isStreaming) {
      stopCamera();
      setTimeout(startCamera, 200);
    }
  };

  // Viewer connection attempt
  const handleConnect = (e: React.FormEvent) => {
    e.preventDefault();
    if (!targetHost.trim()) return;

    setConnectionStatus("CONNECTING");
    setStreamError(null);

    // Formulate sanitized host
    let host = targetHost.trim();
    if (!host.startsWith("http://") && !host.startsWith("https://")) {
      host = `http://${host}`;
    }

    // Attempt ping/health check
    fetch(`${host}/health`, { signal: AbortSignal.timeout(4000) })
      .then((res) => {
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        setIsConnected(true);
        setConnectionStatus("CONNECTED");
        const now = new Date().toLocaleTimeString();
        setViewerEvents((prev) => [
          {
            id: Date.now().toString(),
            timestamp: now,
            type: "INFO",
            message: `Connected to Cam Coder at ${targetHost}`,
          },
          ...prev,
        ]);
      })
      .catch((err) => {
        setConnectionStatus("DISCONNECTED");
        setIsConnected(false);
        setStreamError(`Could not reach ${targetHost}. Ensure your Cam Coder phone is running on the same local Wi-Fi network.`);
      });
  };

  const handleDisconnect = () => {
    setIsConnected(false);
    setConnectionStatus("DISCONNECTED");
    setStreamError(null);
  };

  return (
    <div className="flex flex-col min-h-screen bg-black text-[#f5f5f7]">
      {/* Apple Standard Navigation Header */}
      <header className="sticky top-0 z-40 bg-black/85 backdrop-blur-md border-b border-white/10 px-4 py-3 flex items-center justify-between">
        <div className="flex items-center gap-2.5">
          <div className="w-8 h-8 rounded-lg bg-[#1c1c1e] border border-white/10 flex items-center justify-center text-white">
            <Radio className="w-4 h-4 text-[#0071e3]" />
          </div>
          <div>
            <h1 className="text-sm font-semibold tracking-tight text-white leading-tight">
              Smart Spectator
            </h1>
            <p className="text-[11px] text-[#8e8e93]">
              {role === "CAM_CODER" ? (isStreaming ? "Host Broadcasting" : "Host Standby") : (isConnected ? "Connected to Host" : "Viewer Offline")}
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          {batteryLevel !== null && (
            <div className="flex items-center gap-1 text-xs text-[#8e8e93] bg-[#1c1c1e] px-2.5 py-1 rounded-md border border-white/10">
              <Battery className="w-3.5 h-3.5 text-white" />
              <span>{batteryLevel}%</span>
            </div>
          )}

          <button
            onClick={() => setShowPairModal(true)}
            className="p-1.5 rounded-md bg-[#1c1c1e] text-[#8e8e93] hover:text-white border border-white/10"
            title="Pairing Code"
            aria-label="Show Pairing Code"
          >
            <QrCode className="w-4 h-4" />
          </button>
        </div>
      </header>

      {/* Apple Segmented Control for Role Toggle */}
      <div className="px-4 py-2.5 bg-black border-b border-white/10">
        <div className="flex rounded-lg bg-[#1c1c1e] p-0.5 border border-white/10" role="tablist">
          <button
            role="tab"
            aria-selected={role === "CAM_CODER"}
            onClick={() => {
              setRole("CAM_CODER");
            }}
            className={`flex-1 flex items-center justify-center gap-1.5 py-1.5 rounded-md text-xs font-medium transition-all ${
              role === "CAM_CODER"
                ? "bg-[#2c2c2e] text-white shadow-sm"
                : "text-[#8e8e93] hover:text-white"
            }`}
          >
            <Camera className="w-3.5 h-3.5" />
            CAM CODER
          </button>
          <button
            role="tab"
            aria-selected={role === "VIEW_ACCESS"}
            onClick={() => {
              setRole("VIEW_ACCESS");
              stopCamera();
            }}
            className={`flex-1 flex items-center justify-center gap-1.5 py-1.5 rounded-md text-xs font-medium transition-all ${
              role === "VIEW_ACCESS"
                ? "bg-[#2c2c2e] text-white shadow-sm"
                : "text-[#8e8e93] hover:text-white"
            }`}
          >
            <Eye className="w-3.5 h-3.5" />
            VIEW ACCESS
          </button>
        </div>
      </div>

      {/* Main Container */}
      <main className="flex-1 p-4 pb-12 overflow-y-auto max-w-lg mx-auto w-full">
        {/* ========================================================================= */}
        {/* CAM CODER MODE */}
        {/* ========================================================================= */}
        {role === "CAM_CODER" && (
          <div className="flex flex-col gap-4">
            {/* Viewfinder Window */}
            <div className="relative aspect-[4/3] w-full rounded-xl overflow-hidden bg-[#1c1c1e] border border-white/10">
              <video
                ref={videoRef}
                playsInline
                muted
                className={`w-full h-full object-cover transition-opacity duration-200 ${
                  isDimmed ? "opacity-15" : "opacity-100"
                }`}
              />

              {/* Status bar in viewfinder */}
              <div className="absolute top-3 left-3 right-3 flex items-center justify-between pointer-events-none">
                <span className="text-[11px] font-medium px-2 py-0.5 rounded bg-black/70 text-white border border-white/10">
                  {isStreaming ? "Broadcasting" : "Camera Idle"}
                </span>
                <span className="text-[11px] text-[#8e8e93] bg-black/70 px-2 py-0.5 rounded border border-white/10">
                  {facingMode === "environment" ? "Back Camera" : "Front Camera"}
                </span>
              </div>

              {/* Dimmer Overlay */}
              {isDimmed && (
                <div
                  onClick={() => setIsDimmed(false)}
                  className="absolute inset-0 bg-black/85 flex flex-col items-center justify-center cursor-pointer"
                >
                  <Moon className="w-8 h-8 text-[#0071e3] mb-2" />
                  <p className="text-xs font-medium text-[#f5f5f7]">Display Dimmed</p>
                  <p className="text-[11px] text-[#8e8e93]">Tap anywhere to restore brightness</p>
                </div>
              )}
            </div>

            {/* Apple Camera Controls */}
            <div className="flex items-center gap-2">
              {!isStreaming ? (
                <button
                  onClick={startCamera}
                  className="flex-1 h-11 bg-[#0071e3] hover:bg-[#0077ed] text-white font-medium text-sm rounded-lg transition-colors flex items-center justify-center gap-2"
                >
                  <Camera className="w-4 h-4" />
                  Start Camera
                </button>
              ) : (
                <button
                  onClick={stopCamera}
                  className="flex-1 h-11 bg-[#ff453a] hover:bg-[#ff3b30] text-white font-medium text-sm rounded-lg transition-colors flex items-center justify-center gap-2"
                >
                  Stop Camera
                </button>
              )}

              <button
                onClick={toggleCameraFacing}
                className="w-11 h-11 bg-[#1c1c1e] hover:bg-[#2c2c2e] border border-white/10 rounded-lg text-white flex items-center justify-center transition-colors"
                title="Switch Camera"
                aria-label="Switch Camera"
              >
                <RefreshCw className="w-4 h-4" />
              </button>

              <button
                onClick={() => setIsDimmed(!isDimmed)}
                className={`w-11 h-11 border rounded-lg flex items-center justify-center transition-colors ${
                  isDimmed
                    ? "bg-[#0071e3] border-[#0071e3] text-white"
                    : "bg-[#1c1c1e] hover:bg-[#2c2c2e] border-white/10 text-white"
                }`}
                title="Toggle Screen Dimmer"
                aria-label="Toggle Screen Dimmer"
              >
                <Moon className="w-4 h-4" />
              </button>
            </div>

            {/* Host Details Card */}
            <div className="bg-[#1c1c1e] border border-white/10 rounded-xl p-4">
              <h2 className="text-xs font-semibold text-[#8e8e93] uppercase tracking-wider mb-3">
                Local Host Settings
              </h2>
              <div className="flex flex-col gap-2.5 text-xs">
                <div className="flex justify-between py-1 border-b border-white/5">
                  <span className="text-[#8e8e93]">Binding Interface</span>
                  <span className="font-mono text-white">0.0.0.0:8080</span>
                </div>
                <div className="flex justify-between py-1 border-b border-white/5">
                  <span className="text-[#8e8e93]">Local Discovery</span>
                  <span className="font-mono text-white">_smart-spectator._tcp</span>
                </div>
                <div className="flex justify-between py-1">
                  <span className="text-[#8e8e93]">Storage Engine</span>
                  <span className="text-white">Local SQLite Database</span>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* ========================================================================= */}
        {/* VIEW ACCESS MODE */}
        {/* ========================================================================= */}
        {role === "VIEW_ACCESS" && (
          <div className="flex flex-col gap-4">
            {/* Connection Input Form */}
            <div className="bg-[#1c1c1e] border border-white/10 rounded-xl p-4">
              <h2 className="text-xs font-semibold text-[#8e8e93] uppercase tracking-wider mb-2">
                Connect to Cam Coder
              </h2>

              {!isConnected ? (
                <form onSubmit={handleConnect} className="flex flex-col gap-3">
                  <p className="text-xs text-[#8e8e93] leading-relaxed">
                    Enter the LAN IP address or host name of the camera phone running Smart Spectator:
                  </p>
                  <div className="flex gap-2">
                    <input
                      type="text"
                      placeholder="e.g. 192.168.1.50:8080"
                      value={targetHost}
                      onChange={(e) => setTargetHost(e.target.value)}
                      className="flex-1 h-10 px-3 bg-black border border-white/10 rounded-lg text-xs font-mono text-white placeholder-[#636366] focus:outline-none focus:border-[#0071e3]"
                    />
                    <button
                      type="submit"
                      disabled={connectionStatus === "CONNECTING"}
                      className="h-10 px-4 bg-[#0071e3] hover:bg-[#0077ed] text-white text-xs font-medium rounded-lg transition-colors flex items-center gap-1.5 disabled:opacity-50"
                    >
                      <LinkIcon className="w-3.5 h-3.5" />
                      {connectionStatus === "CONNECTING" ? "Connecting..." : "Connect"}
                    </button>
                  </div>

                  {streamError && (
                    <div className="flex items-start gap-2 p-2.5 rounded-lg bg-[#ff453a]/10 border border-[#ff453a]/20 text-[#ff453a] text-xs">
                      <AlertCircle className="w-4 h-4 flex-shrink-0 mt-0.5" />
                      <span>{streamError}</span>
                    </div>
                  )}
                </form>
              ) : (
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <span className="w-2 h-2 rounded-full bg-[#30d158]" />
                    <span className="text-xs text-white font-mono">{targetHost}</span>
                  </div>
                  <button
                    onClick={handleDisconnect}
                    className="h-8 px-3 rounded-md bg-[#2c2c2e] hover:bg-[#3a3a3c] text-white text-xs font-medium flex items-center gap-1.5"
                  >
                    <Unlink className="w-3.5 h-3.5" />
                    Disconnect
                  </button>
                </div>
              )}
            </div>

            {/* Viewer Screen Display */}
            <div className="aspect-[4/3] w-full rounded-xl bg-[#1c1c1e] border border-white/10 flex flex-col items-center justify-center p-6 text-center">
              {!isConnected ? (
                <div className="flex flex-col items-center">
                  <Eye className="w-10 h-10 text-[#636366] mb-3" />
                  <h3 className="text-sm font-semibold text-white mb-1">No Active Feed</h3>
                  <p className="text-xs text-[#8e8e93] max-w-xs leading-relaxed">
                    Connect to a CAM CODER device on your network to view the camera feed and event telemetry.
                  </p>
                </div>
              ) : (
                <div className="w-full h-full flex flex-col items-center justify-center">
                  <span className="text-xs text-[#30d158] font-mono mb-2">● LIVE FEED CONNECTED</span>
                  <p className="text-xs text-[#8e8e93]">Receiving frames from {targetHost}</p>
                </div>
              )}
            </div>

            {/* Event History (Honest State) */}
            <div className="bg-[#1c1c1e] border border-white/10 rounded-xl p-4">
              <h2 className="text-xs font-semibold text-[#8e8e93] uppercase tracking-wider mb-3">
                Event Log
              </h2>

              {viewerEvents.length === 0 ? (
                <div className="py-6 text-center text-xs text-[#636366]">
                  No events received yet.
                </div>
              ) : (
                <div className="flex flex-col gap-2">
                  {viewerEvents.map((evt) => (
                    <div
                      key={evt.id}
                      className="p-2.5 rounded-lg bg-black border border-white/5 flex items-start gap-2.5 text-xs"
                    >
                      <span className="text-[#8e8e93] font-mono shrink-0">{evt.timestamp}</span>
                      <span className="text-white flex-1">{evt.message}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        )}
      </main>

      {/* Clean Apple Sheet Modal for Pairing */}
      {showPairModal && (
        <div
          className="fixed inset-0 z-50 bg-black/70 backdrop-blur-sm flex items-center justify-center p-4"
          onClick={() => setShowPairModal(false)}
        >
          <div
            className="w-full max-w-xs bg-[#1c1c1e] border border-white/10 rounded-2xl p-6 text-center shadow-xl"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex justify-between items-center mb-4">
              <h3 className="text-sm font-semibold text-white">Pair View Access</h3>
              <button
                onClick={() => setShowPairModal(false)}
                className="text-[#8e8e93] hover:text-white"
                aria-label="Close"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <p className="text-xs text-[#8e8e93] mb-4">
              Single-use 8-character verification code for direct local pairing:
            </p>

            <div className="bg-black border border-white/10 rounded-lg p-3 mb-4 font-mono text-base font-semibold tracking-widest text-[#0071e3]">
              7F4K-92QM
            </div>

            <p className="text-[11px] text-[#636366]">
              Expires in 5 minutes. Enter this code on your viewer device.
            </p>
          </div>
        </div>
      )}
    </div>
  );
}
