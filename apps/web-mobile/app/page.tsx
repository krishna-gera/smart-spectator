"use client";

import React, { useState, useEffect, useRef, useCallback } from "react";
import {
  Camera,
  Eye,
  RefreshCw,
  Zap,
  Battery,
  Wifi,
  Settings,
  AlertTriangle,
  CheckCircle2,
  Clock,
  Play,
  Square,
  Sliders,
  ChevronRight,
  ShieldAlert,
  Moon,
  Volume2,
  VolumeX,
  PlusCircle,
  X,
  Share2
} from "lucide-react";

type RoleMode = "CAM_CODER" | "VIEW_ACCESS";

interface MonitoringPreset {
  id: string;
  title: string;
  icon: string;
  prompt: string;
  targetState: string;
  intervalSec: number;
}

const PRESETS: MonitoringPreset[] = [
  {
    id: "water_tank",
    title: "Water Tank",
    icon: "🚰",
    prompt: "Monitor water tank level. Alert when level reaches the top overflow rim.",
    targetState: "TANK_FULL",
    intervalSec: 3,
  },
  {
    id: "washing_machine",
    title: "Washing Machine",
    icon: "🌊",
    prompt: "Monitor washing machine cycle. Detect when drum stops spinning and cycle is complete.",
    targetState: "CYCLE_FINISHED",
    intervalSec: 5,
  },
  {
    id: "cooking_boil",
    title: "Cooking Boil",
    icon: "🍳",
    prompt: "Observe cooking pot. Alert if foam or water begins boiling over rim.",
    targetState: "BOIL_OVER_RISK",
    intervalSec: 2,
  },
  {
    id: "door_security",
    title: "Door Status",
    icon: "🚪",
    prompt: "Detect whether front door is open or closed. Alert immediately when opened.",
    targetState: "DOOR_OPEN",
    intervalSec: 2,
  },
  {
    id: "pet_monitoring",
    title: "Pet Watch",
    icon: "🐾",
    prompt: "Detect presence and movement of pet on sofa or dining area.",
    targetState: "PET_ON_FURNITURE",
    intervalSec: 4,
  },
];

interface EventItem {
  id: string;
  timestamp: string;
  type: "ALERT" | "INFO" | "STATUS_CHANGE";
  message: string;
  confidence: number;
}

export default function MobileApp() {
  const [role, setRole] = useState<RoleMode>("VIEW_ACCESS");
  const [activePreset, setActivePreset] = useState<MonitoringPreset>(PRESETS[0]);
  const [customPrompt, setCustomPrompt] = useState("");
  const [showConfigModal, setShowConfigModal] = useState(false);
  const [showPairModal, setShowPairModal] = useState(false);

  // CamCoder States
  const [isStreaming, setIsStreaming] = useState(false);
  const [facingMode, setFacingMode] = useState<"environment" | "user">("environment");
  const [motionDetected, setMotionDetected] = useState(false);
  const [fps, setFps] = useState(0);
  const [batteryLevel, setBatteryLevel] = useState(94);
  const [isDimmed, setIsDimmed] = useState(false);
  const [torchOn, setTorchOn] = useState(false);

  // Viewer States
  const [currentState, setCurrentState] = useState<string>("MONITORING_NORMAL");
  const [confidence, setConfidence] = useState<number>(0.92);
  const [lastCheckTime, setLastCheckTime] = useState<string>("Just now");
  const [isSoundMuted, setIsSoundMuted] = useState(false);
  const [events, setEvents] = useState<EventItem[]>([
    {
      id: "1",
      timestamp: "10:14:02",
      type: "INFO",
      message: "Monitoring session started for Water Tank",
      confidence: 1.0,
    },
    {
      id: "2",
      timestamp: "10:14:15",
      type: "STATUS_CHANGE",
      message: "Water level detected at 65% capacity",
      confidence: 0.89,
    },
    {
      id: "3",
      timestamp: "10:14:48",
      type: "ALERT",
      message: "Level rising rapidly approaching 90%",
      confidence: 0.94,
    },
  ]);

  const videoRef = useRef<HTMLVideoElement | null>(null);
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const prevFrameData = useRef<Uint8ClampedArray | null>(null);
  const frameCountRef = useRef(0);

  // Battery API check
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

  // Handle CamCoder streaming
  const startCamera = async () => {
    try {
      if (streamRef.current) {
        streamRef.current.getTracks().forEach((t) => t.stop());
      }
      const stream = await navigator.mediaDevices.getUserMedia({
        video: {
          facingMode: { ideal: facingMode },
          width: { ideal: 640 },
          height: { ideal: 480 },
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
      console.warn("Camera access fallback or denied:", err);
      setIsStreaming(true); // Demo mode fallback
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

  // Frame processing loop for CamCoder motion detection
  useEffect(() => {
    if (!isStreaming || role !== "CAM_CODER") return;

    let intervalId: any;
    intervalId = setInterval(() => {
      frameCountRef.current += 1;
      setFps(Math.min(15, frameCountRef.current * 2));
      frameCountRef.current = 0;

      if (!videoRef.current || !canvasRef.current) return;
      const video = videoRef.current;
      const canvas = canvasRef.current;
      const ctx = canvas.getContext("2d", { willReadFrequently: true });
      if (!ctx || video.videoWidth === 0) return;

      canvas.width = 160;
      canvas.height = 120;
      ctx.drawImage(video, 0, 0, 160, 120);

      try {
        const frame = ctx.getImageData(0, 0, 160, 120);
        const currentData = frame.data;
        if (prevFrameData.current) {
          let diffCount = 0;
          for (let i = 0; i < currentData.length; i += 16) {
            const diff = Math.abs(currentData[i] - prevFrameData.current[i]);
            if (diff > 35) diffCount++;
          }
          const isMotion = diffCount > 15;
          setMotionDetected(isMotion);
        }
        prevFrameData.current = new Uint8ClampedArray(currentData);
      } catch (_) {}
    }, 500);

    return () => clearInterval(intervalId);
  }, [isStreaming, role]);

  // Viewer simulated live updates
  useEffect(() => {
    if (role !== "VIEW_ACCESS") return;
    const interval = setInterval(() => {
      const now = new Date();
      const timeStr = now.toTimeString().split(" ")[0];
      setLastCheckTime(timeStr);

      // Random state evolution for live demo
      const states = ["NORMAL_FILLING", "NORMAL_OBSERVED", "APPROACHING_LIMIT", "CONDITION_MET"];
      const conf = +(0.85 + Math.random() * 0.14).toFixed(2);
      setConfidence(conf);

      if (Math.random() > 0.7) {
        const pickedState = states[Math.floor(Math.random() * states.length)];
        setCurrentState(pickedState);
        if (pickedState === "CONDITION_MET") {
          const newEvt: EventItem = {
            id: Date.now().toString(),
            timestamp: timeStr,
            type: "ALERT",
            message: `Target state reached: ${activePreset.targetState}`,
            confidence: conf,
          };
          setEvents((prev) => [newEvt, ...prev.slice(0, 8)]);
          if (!isSoundMuted && typeof window !== "undefined" && "navigator" in window) {
            try {
              navigator.vibrate?.([200, 100, 200]);
            } catch (_) {}
          }
        }
      }
    }, 4000);

    return () => clearInterval(interval);
  }, [role, activePreset, isSoundMuted]);

  return (
    <div className="flex flex-col min-h-screen bg-[#0A0D14] text-white">
      {/* Top Header / App Bar */}
      <header className="sticky top-0 z-40 bg-[#111827]/90 backdrop-blur-md border-b border-[#2A3347] px-4 py-3 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <div className="w-8 h-8 rounded-xl bg-gradient-to-tr from-[#4F6EF7] to-[#06B6D4] flex items-center justify-center shadow-lg shadow-indigo-500/20">
            <Eye className="w-5 h-5 text-white" />
          </div>
          <div>
            <h1 className="text-base font-bold tracking-tight text-white leading-tight">
              Smart Spectator
            </h1>
            <div className="flex items-center gap-1.5 text-[11px] text-[#9CA3AF]">
              <span className="w-2 h-2 rounded-full bg-[#22C55E] inline-block animate-pulse" />
              <span>AI Engine Active</span>
            </div>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <div className="flex items-center gap-1 text-xs text-[#9CA3AF] bg-[#1A2235] px-2.5 py-1 rounded-full border border-[#2A3347]">
            <Battery className="w-3.5 h-3.5 text-[#22C55E]" />
            <span>{batteryLevel}%</span>
          </div>

          <button
            onClick={() => setShowPairModal(true)}
            className="p-1.5 rounded-lg bg-[#1A2235] text-[#9CA3AF] hover:text-white border border-[#2A3347]"
            title="Pairing"
          >
            <Share2 className="w-4 h-4" />
          </button>
        </div>
      </header>

      {/* Role Toggle Selector */}
      <div className="px-4 py-3 bg-[#0E131F] border-b border-[#1E293B]">
        <div className="flex rounded-xl bg-[#111827] p-1 border border-[#2A3347]">
          <button
            onClick={() => {
              setRole("VIEW_ACCESS");
              stopCamera();
            }}
            className={`flex-1 flex items-center justify-center gap-2 py-2 rounded-lg text-xs font-semibold transition-all ${
              role === "VIEW_ACCESS"
                ? "bg-[#4F6EF7] text-white shadow-md"
                : "text-[#9CA3AF] hover:text-white"
            }`}
          >
            <Eye className="w-4 h-4" />
            VIEW ACCESS
          </button>
          <button
            onClick={() => setRole("CAM_CODER")}
            className={`flex-1 flex items-center justify-center gap-2 py-2 rounded-lg text-xs font-semibold transition-all ${
              role === "CAM_CODER"
                ? "bg-[#06B6D4] text-[#0A0D14] shadow-md font-bold"
                : "text-[#9CA3AF] hover:text-white"
            }`}
          >
            <Camera className="w-4 h-4" />
            CAM CODER
          </button>
        </div>
      </div>

      {/* Main Content Area */}
      <main className="flex-1 p-4 pb-20 overflow-y-auto">
        {/* ========================================================================= */}
        {/* ROLE: CAM CODER MODE */}
        {/* ========================================================================= */}
        {role === "CAM_CODER" && (
          <div className="flex flex-col gap-4">
            {/* Viewfinder Preview Box */}
            <div className="relative aspect-[4/3] w-full rounded-2xl overflow-hidden bg-black border border-[#2A3347] shadow-xl">
              <video
                ref={videoRef}
                playsInline
                muted
                className={`w-full h-full object-cover transition-opacity duration-300 ${
                  isDimmed ? "opacity-10" : "opacity-100"
                }`}
              />
              <canvas ref={canvasRef} className="hidden" />

              {/* Viewfinder Reticle / AI Overlay */}
              <div className="absolute inset-0 pointer-events-none p-4 flex flex-col justify-between">
                <div className="flex justify-between items-center">
                  <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-black/60 backdrop-blur-md text-[11px] text-white border border-white/20">
                    <span
                      className={`w-2 h-2 rounded-full ${
                        isStreaming ? "bg-[#22C55E] animate-ping" : "bg-[#EF4444]"
                      }`}
                    />
                    <span>{isStreaming ? "LIVE TRANSMITTING" : "STANDBY"}</span>
                  </div>

                  {motionDetected && (
                    <div className="flex items-center gap-1 px-2.5 py-1 rounded-full bg-[#F59E0B]/90 text-[11px] text-black font-bold">
                      <Zap className="w-3.5 h-3.5 fill-black" />
                      MOTION
                    </div>
                  )}
                </div>

                {/* Central Targeting Frame */}
                <div className="self-center w-48 h-48 border-2 border-dashed border-[#4F6EF7]/60 rounded-xl relative flex items-center justify-center">
                  <span className="text-[10px] text-[#4F6EF7] bg-black/70 px-2 py-0.5 rounded">
                    AI OBSERVATION REGION
                  </span>
                </div>

                <div className="flex justify-between text-[11px] text-white/80 bg-black/50 backdrop-blur-md p-2 rounded-xl">
                  <span>Target: {activePreset.targetState}</span>
                  <span>Interval: {activePreset.intervalSec}s</span>
                </div>
              </div>

              {/* Screen Dimmer Cover */}
              {isDimmed && (
                <div
                  onClick={() => setIsDimmed(false)}
                  className="absolute inset-0 bg-black/90 flex flex-col items-center justify-center cursor-pointer"
                >
                  <Moon className="w-10 h-10 text-[#4F6EF7] animate-pulse mb-2" />
                  <p className="text-sm font-medium text-gray-300">Power Saver Mode Active</p>
                  <p className="text-xs text-gray-500">Tap anywhere to wake display</p>
                </div>
              )}
            </div>

            {/* Camera Action Buttons */}
            <div className="flex items-center justify-between gap-3">
              {!isStreaming ? (
                <button
                  onClick={startCamera}
                  className="flex-1 flex items-center justify-center gap-2 bg-[#22C55E] hover:bg-[#16A34A] text-black font-bold py-3 px-4 rounded-xl shadow-lg transition-transform active:scale-95"
                >
                  <Play className="w-5 h-5 fill-black" />
                  START BROADCAST
                </button>
              ) : (
                <button
                  onClick={stopCamera}
                  className="flex-1 flex items-center justify-center gap-2 bg-[#EF4444] hover:bg-[#DC2626] text-white font-bold py-3 px-4 rounded-xl shadow-lg transition-transform active:scale-95"
                >
                  <Square className="w-5 h-5 fill-white" />
                  STOP BROADCAST
                </button>
              )}

              <button
                onClick={toggleCameraFacing}
                className="p-3 bg-[#111827] border border-[#2A3347] rounded-xl text-[#9CA3AF] hover:text-white"
                title="Flip Camera"
              >
                <RefreshCw className="w-5 h-5" />
              </button>

              <button
                onClick={() => setIsDimmed(!isDimmed)}
                className={`p-3 border rounded-xl transition-colors ${
                  isDimmed
                    ? "bg-[#4F6EF7] text-white border-[#4F6EF7]"
                    : "bg-[#111827] border-[#2A3347] text-[#9CA3AF]"
                }`}
                title="Dim Display (Power Saver)"
              >
                <Moon className="w-5 h-5" />
              </button>
            </div>

            {/* Current Objective Card */}
            <div className="bg-[#111827] border border-[#2A3347] rounded-2xl p-4">
              <div className="flex items-center justify-between mb-2">
                <span className="text-xs font-semibold tracking-wider text-[#9CA3AF] uppercase">
                  Active Monitoring Objective
                </span>
                <button
                  onClick={() => setShowConfigModal(true)}
                  className="text-xs text-[#4F6EF7] font-semibold"
                >
                  Change
                </button>
              </div>
              <div className="flex items-start gap-3">
                <span className="text-2xl">{activePreset.icon}</span>
                <div>
                  <h3 className="text-sm font-bold text-white">{activePreset.title}</h3>
                  <p className="text-xs text-[#9CA3AF] mt-0.5">{activePreset.prompt}</p>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* ========================================================================= */}
        {/* ROLE: VIEW ACCESS MODE */}
        {/* ========================================================================= */}
        {role === "VIEW_ACCESS" && (
          <div className="flex flex-col gap-4">
            {/* Live Observation Status Card */}
            <div className="bg-[#111827] border border-[#2A3347] rounded-2xl p-4 shadow-xl">
              <div className="flex items-center justify-between pb-3 border-b border-[#1E293B]">
                <div className="flex items-center gap-2">
                  <span className="text-2xl">{activePreset.icon}</span>
                  <div>
                    <h2 className="text-sm font-bold text-white leading-tight">
                      {activePreset.title}
                    </h2>
                    <span className="text-[11px] text-[#9CA3AF]">
                      Target: <span className="text-[#4F6EF7] font-semibold">{activePreset.targetState}</span>
                    </span>
                  </div>
                </div>

                <button
                  onClick={() => setIsSoundMuted(!isSoundMuted)}
                  className="p-2 rounded-lg bg-[#1A2235] text-[#9CA3AF] hover:text-white border border-[#2A3347]"
                >
                  {isSoundMuted ? (
                    <VolumeX className="w-4 h-4 text-[#EF4444]" />
                  ) : (
                    <Volume2 className="w-4 h-4 text-[#22C55E]" />
                  )}
                </button>
              </div>

              {/* Status Display Area */}
              <div className="my-4 p-4 rounded-xl bg-[#0A0D14] border border-[#1E293B]">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-[11px] text-[#6B7280] font-bold uppercase tracking-wider">
                    Current AI Assessment
                  </span>
                  <span className="text-[11px] text-[#9CA3AF] flex items-center gap-1">
                    <Clock className="w-3 h-3" />
                    {lastCheckTime}
                  </span>
                </div>

                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <div
                      className={`w-3.5 h-3.5 rounded-full ${
                        currentState === "CONDITION_MET"
                          ? "bg-[#EF4444] animate-ping"
                          : "bg-[#22C55E]"
                      }`}
                    />
                    <span className="text-lg font-extrabold text-white tracking-wide">
                      {currentState}
                    </span>
                  </div>

                  <div className="text-right">
                    <div className="text-xs font-bold text-[#4F6EF7]">
                      {Math.round(confidence * 100)}%
                    </div>
                    <div className="text-[10px] text-[#6B7280]">Confidence</div>
                  </div>
                </div>

                {/* Confidence Bar */}
                <div className="w-full bg-[#1E293B] h-1.5 rounded-full mt-3 overflow-hidden">
                  <div
                    className="bg-gradient-to-r from-[#4F6EF7] to-[#06B6D4] h-full transition-all duration-500 rounded-full"
                    style={{ width: `${confidence * 100}%` }}
                  />
                </div>
              </div>

              {/* Quick Preset Selector Carousel */}
              <div>
                <div className="flex items-center justify-between mb-2">
                  <span className="text-xs font-bold text-[#9CA3AF] uppercase tracking-wider">
                    Quick Preset Tasks
                  </span>
                  <button
                    onClick={() => setShowConfigModal(true)}
                    className="text-xs text-[#4F6EF7] font-semibold"
                  >
                    Custom
                  </button>
                </div>
                <div className="flex gap-2 overflow-x-auto pb-1 scrollbar-none">
                  {PRESETS.map((p) => (
                    <button
                      key={p.id}
                      onClick={() => setActivePreset(p)}
                      className={`flex-shrink-0 flex items-center gap-2 px-3 py-2 rounded-xl text-xs font-medium border transition-all ${
                        activePreset.id === p.id
                          ? "bg-[#1E293B] border-[#4F6EF7] text-white shadow-md shadow-indigo-500/10"
                          : "bg-[#111827] border-[#2A3347] text-[#9CA3AF] hover:text-white"
                      }`}
                    >
                      <span>{p.icon}</span>
                      <span>{p.title}</span>
                    </button>
                  ))}
                </div>
              </div>
            </div>

            {/* Live Observation Events Feed */}
            <div className="bg-[#111827] border border-[#2A3347] rounded-2xl p-4">
              <div className="flex items-center justify-between mb-3">
                <span className="text-xs font-bold text-[#9CA3AF] uppercase tracking-wider">
                  Real-Time Observation Log
                </span>
                <span className="text-xs text-[#4F6EF7] font-medium">{events.length} events</span>
              </div>

              <div className="flex flex-col gap-2.5">
                {events.map((evt) => {
                  const isAlert = evt.type === "ALERT";
                  return (
                    <div
                      key={evt.id}
                      className={`p-3 rounded-xl border flex items-start gap-3 transition-all ${
                        isAlert
                          ? "bg-[#EF4444]/10 border-[#EF4444]/40"
                          : "bg-[#0A0D14] border-[#1E293B]"
                      }`}
                    >
                      <div className="mt-0.5">
                        {isAlert ? (
                          <AlertTriangle className="w-4 h-4 text-[#EF4444]" />
                        ) : (
                          <CheckCircle2 className="w-4 h-4 text-[#4F6EF7]" />
                        )}
                      </div>
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center justify-between gap-1">
                          <p className="text-xs font-semibold text-white truncate">
                            {evt.message}
                          </p>
                          <span className="text-[10px] text-[#6B7280] shrink-0">
                            {evt.timestamp}
                          </span>
                        </div>
                        <div className="flex items-center gap-2 mt-1">
                          <span className="text-[10px] text-[#9CA3AF]">
                            Conf: {Math.round(evt.confidence * 100)}%
                          </span>
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          </div>
        )}
      </main>

      {/* ========================================================================= */}
      {/* TASK CONFIG MODAL */}
      {/* ========================================================================= */}
      {showConfigModal && (
        <div className="fixed inset-0 z-50 bg-black/80 backdrop-blur-sm flex items-end sm:items-center justify-center p-4">
          <div className="w-full max-w-md bg-[#111827] border border-[#2A3347] rounded-3xl p-5 shadow-2xl animate-in slide-in-from-bottom duration-200">
            <div className="flex items-center justify-between pb-3 border-b border-[#1E293B] mb-4">
              <h3 className="text-base font-bold text-white">Custom Monitoring Condition</h3>
              <button
                onClick={() => setShowConfigModal(false)}
                className="p-1 rounded-lg text-[#9CA3AF] hover:text-white"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="flex flex-col gap-3">
              <div>
                <label className="text-xs font-semibold text-[#9CA3AF] block mb-1">
                  What should Smart Spectator observe?
                </label>
                <textarea
                  value={customPrompt}
                  onChange={(e) => setCustomPrompt(e.target.value)}
                  placeholder="e.g. Watch the pressure cooker whistle. Alert when 3 whistles have passed or steam escapes violently."
                  className="w-full h-24 bg-[#0A0D14] border border-[#2A3347] rounded-xl p-3 text-xs text-white placeholder-gray-500 focus:outline-none focus:border-[#4F6EF7]"
                />
              </div>

              <button
                onClick={() => {
                  if (customPrompt.trim()) {
                    setActivePreset({
                      id: "custom_" + Date.now(),
                      title: "Custom Condition",
                      icon: "🎯",
                      prompt: customPrompt,
                      targetState: "TARGET_MET",
                      intervalSec: 3,
                    });
                  }
                  setShowConfigModal(false);
                }}
                className="w-full py-3 bg-[#4F6EF7] hover:bg-[#3A56D4] text-white font-bold rounded-xl text-xs shadow-lg transition-transform active:scale-95 mt-2"
              >
                APPLY MONITORING TASK
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ========================================================================= */}
      {/* PAIRING MODAL */}
      {/* ========================================================================= */}
      {showPairModal && (
        <div className="fixed inset-0 z-50 bg-black/80 backdrop-blur-sm flex items-end sm:items-center justify-center p-4">
          <div className="w-full max-w-md bg-[#111827] border border-[#2A3347] rounded-3xl p-5 shadow-2xl">
            <div className="flex items-center justify-between pb-3 border-b border-[#1E293B] mb-4">
              <h3 className="text-base font-bold text-white">Device Pairing</h3>
              <button
                onClick={() => setShowPairModal(false)}
                className="p-1 rounded-lg text-[#9CA3AF] hover:text-white"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="flex flex-col items-center gap-4 text-center">
              <div className="p-4 bg-white rounded-2xl shadow-lg">
                <div className="w-36 h-36 border-4 border-black flex items-center justify-center p-2 bg-white">
                  <div className="grid grid-cols-5 gap-1 w-full h-full">
                    {Array.from({ length: 25 }).map((_, i) => (
                      <div
                        key={i}
                        className={`rounded-sm ${
                          (i * 7) % 3 === 0 ? "bg-black" : "bg-transparent"
                        }`}
                      />
                    ))}
                  </div>
                </div>
              </div>

              <div>
                <p className="text-xs text-[#9CA3AF] mb-1">Single-use Pairing Code</p>
                <div className="text-2xl font-mono font-bold tracking-widest text-[#4F6EF7] bg-[#1A2235] px-4 py-2 rounded-xl border border-[#2A3347]">
                  749 - 281
                </div>
                <p className="text-[11px] text-[#6B7280] mt-1.5">Expires in 04:32</p>
              </div>

              <p className="text-xs text-[#9CA3AF] max-w-xs">
                Scan this code or enter the 6-digit number on your other device to securely link the camera and viewer.
              </p>

              <button
                onClick={() => setShowPairModal(false)}
                className="w-full py-2.5 bg-[#1A2235] hover:bg-[#2A3347] text-white font-semibold rounded-xl text-xs border border-[#2A3347]"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
