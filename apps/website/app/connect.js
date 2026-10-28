// Shared by the VYRO web apps (/app/app-mobile and /app/app-desktop).
//
// The live dashboard runs on the main phone itself (http://<phone>:8000) and
// never leaves the home Wi-Fi. A page on the internet cannot read a phone on
// the local network (browsers block that), so the web apps remember your main
// phones and open the phone's own dashboard in the same window.
"use strict";

const VYRO_KEY = "vyro_main_phones";

function vyroPhones() {
  try {
    const list = JSON.parse(localStorage.getItem(VYRO_KEY) || "[]");
    return Array.isArray(list) ? list.filter(p => p && typeof p.host === "string") : [];
  } catch (_) {
    return [];
  }
}

function vyroSavePhones(list) {
  try { localStorage.setItem(VYRO_KEY, JSON.stringify(list.slice(0, 8))); } catch (_) {}
}

/** "192.168.1.22", "192.168.1.22:8000", "http://phone.local:8000/" → {host, port} or null. */
function vyroParse(raw) {
  const s = String(raw || "").trim().replace(/^https?:\/\//i, "").replace(/\/.*$/, "");
  const m = s.match(/^((?:\d{1,3}\.){3}\d{1,3}|[a-z0-9-]+(?:\.[a-z0-9-]+)*\.local)(?::(\d{2,5}))?$/i);
  if (!m) return null;
  if (/^\d/.test(m[1]) && m[1].split(".").some(n => Number(n) > 255)) return null;
  const port = Number(m[2] || 8000);
  return port > 0 && port < 65536 ? { host: m[1].toLowerCase(), port } : null;
}

function vyroRemember(addr, name) {
  const list = vyroPhones().filter(p => !(p.host === addr.host && p.port === addr.port));
  list.unshift({ host: addr.host, port: addr.port, name: name || "", last: Date.now() });
  vyroSavePhones(list);
}

function vyroForget(addr) {
  vyroSavePhones(vyroPhones().filter(p => !(p.host === addr.host && p.port === addr.port)));
}

function vyroUrl(addr) { return `http://${addr.host}:${addr.port}/`; }

/** Opens the main phone's dashboard (same window, so it works as an installed app). */
function vyroOpen(addr, name) {
  vyroRemember(addr, name);
  window.location.href = vyroUrl(addr);
}

function vyroAgo(ms) {
  const s = (Date.now() - ms) / 1000;
  if (s < 60) return "just now";
  if (s < 3600) return `${Math.round(s / 60)} min ago`;
  if (s < 86400) return `${Math.round(s / 3600)} h ago`;
  return `${Math.round(s / 86400)} days ago`;
}

if ("serviceWorker" in navigator) {
  window.addEventListener("load", () => navigator.serviceWorker.register("/app/sw.js", { scope: "/app/" }).catch(() => {}));
}
