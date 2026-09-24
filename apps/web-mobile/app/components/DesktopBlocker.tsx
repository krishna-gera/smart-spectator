'use client';

import React, { useEffect, useState } from 'react';
import { Monitor, Smartphone, ExternalLink, ArrowRight, ShieldCheck } from 'lucide-react';

const DASHBOARD_URL = 'https://web-dashboard-two-pied.vercel.app';

export default function DesktopBlocker() {
  const [isDesktop, setIsDesktop] = useState(false);
  const [mounted, setMounted] = useState(false);
  const [currentUrl, setCurrentUrl] = useState('');

  useEffect(() => {
    setMounted(true);
    setCurrentUrl(window.location.href);

    const checkViewport = () => {
      // Threshold for mobile devices: 768px width
      setIsDesktop(window.innerWidth >= 768);
    };

    checkViewport();
    window.addEventListener('resize', checkViewport);
    return () => window.removeEventListener('resize', checkViewport);
  }, []);

  // During SSR / before hydration, let CSS handle display
  const isVisible = mounted ? isDesktop : true;

  if (mounted && !isDesktop) {
    return null;
  }

  return (
    <div
      id="desktop-screen-blocker"
      className="desktop-blocker-overlay fixed inset-0 z-[999999] bg-[#07090ecf] backdrop-blur-2xl flex items-center justify-center p-4 sm:p-6"
      style={{ display: isVisible ? 'flex' : 'none' }}
    >
      {/* Background ambient glow effect */}
      <div className="absolute w-[500px] h-[500px] bg-gradient-to-tr from-indigo-600/20 via-sky-500/20 to-emerald-500/10 rounded-full blur-[120px] pointer-events-none" />

      {/* Popup Modal Window */}
      <div className="relative w-full max-w-lg bg-[#0e1422] border border-white/10 rounded-3xl p-8 sm:p-10 shadow-2xl shadow-black/80 flex flex-col items-center text-center overflow-hidden">
        
        {/* Top Decorative Device Transition Badge */}
        <div className="flex items-center gap-3 bg-white/5 border border-white/10 px-4 py-2 rounded-full mb-6">
          <div className="flex items-center gap-1.5 text-slate-400">
            <Monitor className="w-4 h-4 text-indigo-400" />
            <span className="text-xs font-medium">Desktop Screen</span>
          </div>
          <ArrowRight className="w-3.5 h-3.5 text-slate-500" />
          <div className="flex items-center gap-1.5 text-emerald-400">
            <Smartphone className="w-4 h-4" />
            <span className="text-xs font-semibold">Mobile Only</span>
          </div>
        </div>

        {/* Title & Description */}
        <h2 className="text-2xl sm:text-3xl font-bold tracking-tight text-white mb-3">
          Mobile App Experience
        </h2>
        <p className="text-sm sm:text-base text-slate-400 leading-relaxed max-w-md mb-8">
          The <span className="text-sky-400 font-semibold">Smart Spectator Web Mobile</span> client is specifically optimized for smartphone handheld viewports and touch interaction.
        </p>

        {/* Action 1: Redirect to Desktop Web Dashboard */}
        <div className="w-full mb-6">
          <a
            href={DASHBOARD_URL}
            className="w-full py-4 px-6 rounded-2xl bg-gradient-to-r from-sky-500 via-indigo-600 to-indigo-700 hover:from-sky-400 hover:via-indigo-500 hover:to-indigo-600 text-white font-semibold text-base shadow-lg shadow-indigo-600/30 hover:shadow-indigo-600/50 hover:scale-[1.01] active:scale-[0.99] transition-all flex items-center justify-center gap-3 group"
          >
            <Monitor className="w-5 h-5 text-sky-200 group-hover:scale-110 transition-transform" />
            <span>Open Desktop Web Dashboard</span>
            <ExternalLink className="w-4 h-4 opacity-70 group-hover:opacity-100 group-hover:translate-x-0.5 transition-all" />
          </a>
          <span className="text-[11px] text-slate-500 mt-2 block font-mono">
            Optimized for widescreen monitors & multi-stream grid
          </span>
        </div>

        {/* Action 2: QR Code / Mobile continuation helper */}
        <div className="w-full pt-6 border-t border-white/10 flex flex-col items-center">
          <div className="flex items-center gap-2 text-xs text-slate-400 mb-3">
            <Smartphone className="w-3.5 h-3.5 text-emerald-400" />
            <span>Scan with your phone to use Web Mobile:</span>
          </div>

          <div className="bg-white p-2.5 rounded-xl shadow-md mb-3">
            {/* Inline SVG QR Code for instant crisp rendering without external scripts */}
            <svg className="w-28 h-28" viewBox="0 0 200 200">
              <rect width="200" height="200" fill="#ffffff" rx="8" />
              {/* Corner position locators */}
              <rect x="20" y="20" width="50" height="50" fill="#0f172a" rx="4" />
              <rect x="28" y="28" width="34" height="34" fill="#ffffff" rx="2" />
              <rect x="36" y="36" width="18" height="18" fill="#0f172a" rx="1" />

              <rect x="130" y="20" width="50" height="50" fill="#0f172a" rx="4" />
              <rect x="138" y="28" width="34" height="34" fill="#ffffff" rx="2" />
              <rect x="146" y="36" width="18" height="18" fill="#0f172a" rx="1" />

              <rect x="20" y="130" width="50" height="50" fill="#0f172a" rx="4" />
              <rect x="28" y="138" width="34" height="34" fill="#ffffff" rx="2" />
              <rect x="36" y="146" width="18" height="18" fill="#0f172a" rx="1" />

              {/* Data matrix nodes */}
              <rect x="80" y="24" width="8" height="8" fill="#0f172a" />
              <rect x="96" y="24" width="16" height="8" fill="#0f172a" />
              <rect x="80" y="40" width="16" height="8" fill="#0f172a" />
              <rect x="104" y="48" width="8" height="16" fill="#0f172a" />
              <rect x="88" y="56" width="8" height="8" fill="#0f172a" />
              <rect x="24" y="80" width="8" height="16" fill="#0f172a" />
              <rect x="40" y="88" width="16" height="8" fill="#0f172a" />
              <rect x="64" y="80" width="8" height="8" fill="#0f172a" />
              <rect x="80" y="80" width="40" height="8" fill="#0f172a" />
              <rect x="88" y="96" width="16" height="16" fill="#0f172a" />
              <rect x="128" y="80" width="8" height="24" fill="#0f172a" />
              <rect x="144" y="88" width="16" height="8" fill="#0f172a" />
              <rect x="168" y="80" width="8" height="16" fill="#0f172a" />
              <rect x="80" y="128" width="16" height="8" fill="#0f172a" />
              <rect x="104" y="128" width="8" height="16" fill="#0f172a" />
              <rect x="88" y="144" width="8" height="16" fill="#0f172a" />
              <rect x="104" y="152" width="24" height="8" fill="#0f172a" />
              <rect x="136" y="128" width="16" height="24" fill="#0f172a" />
              <rect x="160" y="136" width="16" height="8" fill="#0f172a" />
              <rect x="144" y="160" width="24" height="16" fill="#0f172a" />
            </svg>
          </div>

          <span className="text-[11px] text-slate-500 font-mono select-all">
            {currentUrl || 'https://web-mobile-nine-weld.vercel.app'}
          </span>
        </div>

      </div>
    </div>
  );
}
