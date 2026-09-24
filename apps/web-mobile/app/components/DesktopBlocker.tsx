'use client';

import React, { useEffect, useState } from 'react';
import { Monitor, Smartphone, ArrowRight, ExternalLink } from 'lucide-react';

const DASHBOARD_URL = 'https://web-dashboard-two-pied.vercel.app';

export default function DesktopBlocker() {
  const [isDesktop, setIsDesktop] = useState(false);
  const [mounted, setMounted] = useState(false);
  const [currentUrl, setCurrentUrl] = useState('');

  useEffect(() => {
    setMounted(true);
    setCurrentUrl(window.location.href);

    const checkViewport = () => {
      // 768px threshold for tablet/desktop
      setIsDesktop(window.innerWidth >= 768);
    };

    checkViewport();
    window.addEventListener('resize', checkViewport);
    return () => window.removeEventListener('resize', checkViewport);
  }, []);

  const isVisible = mounted ? isDesktop : true;

  if (mounted && !isDesktop) {
    return null;
  }

  return (
    <div
      id="desktop-screen-blocker"
      className="desktop-blocker-overlay fixed inset-0 z-[999999] bg-black/80 backdrop-blur-md flex items-center justify-center p-6"
      style={{ display: isVisible ? 'flex' : 'none' }}
    >
      <div className="w-full max-w-md bg-[#1c1c1e] border border-white/10 rounded-2xl p-8 text-center shadow-2xl">
        {/* Device transition label */}
        <div className="flex items-center justify-center gap-2 text-xs text-[#8e8e93] font-medium mb-4">
          <Monitor className="w-4 h-4" />
          <span>Desktop Viewport</span>
          <ArrowRight className="w-3.5 h-3.5 text-[#636366]" />
          <Smartphone className="w-4 h-4 text-white" />
          <span className="text-white">Mobile Device</span>
        </div>

        <h2 className="text-xl font-semibold text-white tracking-tight mb-2">
          Designed for Mobile
        </h2>
        <p className="text-sm text-[#8e8e93] leading-relaxed mb-6">
          Smart Spectator Web Mobile is intended for mobile browsers. For desktop computers, open the Desktop Dashboard.
        </p>

        {/* Primary Action Button (Apple HIG System Blue) */}
        <div className="w-full mb-6">
          <a
            href={DASHBOARD_URL}
            className="w-full h-11 px-4 rounded-xl bg-[#0071e3] hover:bg-[#0077ed] text-white font-medium text-sm transition-colors flex items-center justify-center gap-2"
          >
            <span>Open Desktop Dashboard</span>
            <ExternalLink className="w-4 h-4 opacity-80" />
          </a>
        </div>

        {/* Clean QR code for mobile handoff */}
        <div className="pt-6 border-t border-white/10 flex flex-col items-center">
          <p className="text-xs text-[#8e8e93] mb-3">Scan with your camera to open on mobile:</p>
          <div className="bg-white p-2.5 rounded-lg mb-2">
            <svg className="w-24 h-24" viewBox="0 0 200 200">
              <rect width="200" height="200" fill="#ffffff" />
              <rect x="20" y="20" width="50" height="50" fill="#000000" />
              <rect x="28" y="28" width="34" height="34" fill="#ffffff" />
              <rect x="36" y="36" width="18" height="18" fill="#000000" />

              <rect x="130" y="20" width="50" height="50" fill="#000000" />
              <rect x="138" y="28" width="34" height="34" fill="#ffffff" />
              <rect x="146" y="36" width="18" height="18" fill="#000000" />

              <rect x="20" y="130" width="50" height="50" fill="#000000" />
              <rect x="28" y="138" width="34" height="34" fill="#ffffff" />
              <rect x="36" y="146" width="18" height="18" fill="#000000" />

              <rect x="80" y="24" width="8" height="8" fill="#000000" />
              <rect x="96" y="24" width="16" height="8" fill="#000000" />
              <rect x="80" y="40" width="16" height="8" fill="#000000" />
              <rect x="104" y="48" width="8" height="16" fill="#000000" />
              <rect x="88" y="56" width="8" height="8" fill="#000000" />
              <rect x="24" y="80" width="8" height="16" fill="#000000" />
              <rect x="40" y="88" width="16" height="8" fill="#000000" />
              <rect x="64" y="80" width="8" height="8" fill="#000000" />
              <rect x="80" y="80" width="40" height="8" fill="#000000" />
              <rect x="88" y="96" width="16" height="16" fill="#000000" />
              <rect x="128" y="80" width="8" height="24" fill="#000000" />
              <rect x="144" y="88" width="16" height="8" fill="#000000" />
              <rect x="168" y="80" width="8" height="16" fill="#000000" />
              <rect x="80" y="128" width="16" height="8" fill="#000000" />
              <rect x="104" y="128" width="8" height="16" fill="#000000" />
              <rect x="88" y="144" width="8" height="16" fill="#000000" />
              <rect x="104" y="152" width="24" height="8" fill="#000000" />
              <rect x="136" y="128" width="16" height="24" fill="#000000" />
              <rect x="160" y="136" width="16" height="8" fill="#000000" />
              <rect x="144" y="160" width="24" height="16" fill="#000000" />
            </svg>
          </div>
          <span className="text-[11px] font-mono text-[#636366] select-all">
            {currentUrl || 'https://web-mobile-nine-weld.vercel.app'}
          </span>
        </div>
      </div>
    </div>
  );
}
