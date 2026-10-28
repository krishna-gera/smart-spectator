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

// ---------------------------------------------------------------- find by code
//
// The main phone registers its local address with the VYRO cloud service
// under its dashboard code. The web apps look it up, then open the phone's
// dashboard with the code so it signs in by itself (the code travels in the
// URL fragment, which is never sent to any server, and the dashboard removes it).
const VYRO_DIRECTORY = "https://smart-spectator-ai-proxy.krishna-gera.workers.dev";

async function vyroFind(code) {
  if (!/^\d{6}$/.test(code)) return { error: "The code has 6 digits." };
  try {
    const res = await fetch(`${VYRO_DIRECTORY}/v1/hub/lookup`, {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ code }),
    });
    if (res.status === 404) return { error: "No main phone with that code. Open VYRO on the main phone (Main phone mode) and check Settings → Web dashboard code." };
    if (res.status === 429) return { error: "Too many tries. Wait a minute and try again." };
    if (!res.ok) return { error: "VYRO could not look up the code right now. Try again, or use the phone's address." };
    const hub = await res.json();
    return { addr: { host: hub.address, port: hub.port || 8000 }, name: hub.name || "Main phone" };
  } catch (_) {
    return { error: "No internet connection. You can still use the phone's address." };
  }
}

/** Opens the dashboard and signs in with [code]. */
function vyroOpenWithCode(addr, code, name) {
  vyroRemember(addr, name);
  window.location.href = `${vyroUrl(addr)}#code=${code}`;
}

/** Keeps a code box to digits, submits at 6. */
function vyroCodeInput(input, onComplete) {
  input.addEventListener("input", () => {
    input.value = input.value.replace(/\D/g, "").slice(0, 6);
    if (input.value.length === 6) onComplete(input.value);
  });
  input.addEventListener("keydown", e => { if (e.key === "Enter" && input.value.length === 6) onComplete(input.value); });
}

// ---------------------------------------------------------------- right device only

function vyroIsPhone() {
  const ua = navigator.userAgent;
  if (/android.+mobile|iphone|ipod|windows phone|mobile safari/i.test(ua)) return true;
  const coarse = window.matchMedia("(pointer: coarse)").matches;
  return coarse && Math.min(screen.width, screen.height) < 600;
}

function vyroIsDesktop() {
  return !vyroIsPhone() && window.matchMedia("(pointer: fine)").matches && window.innerWidth >= 900;
}

/** "mobile": the mobile web app is blocked on computers; "desktop": blocked on phones. */
function vyroDeviceGuard(kind) {
  const blocked = kind === "mobile" ? vyroIsDesktop() : vyroIsPhone();
  if (!blocked) return false;
  const other = kind === "mobile" ? { href: "/app/app-desktop/", label: "Open the desktop web app" } : { href: "/app/app-mobile/", label: "Open the mobile web app" };
  const wall = document.createElement("div");
  wall.className = "device-wall";
  wall.innerHTML = `
    <div class="device-card">
      <img src="/assets/vyro-mark.png" alt="">
      <h1></h1><p class="muted"></p>
      <a class="btn primary block"></a>
      <a class="faint" href="/">Back to the VYRO website</a>
    </div>`;
  wall.querySelector("h1").textContent = kind === "mobile" ? "This is the mobile web app" : "This is the desktop web app";
  wall.querySelector("p").textContent = kind === "mobile"
    ? "It is made for phones. On a computer, use the desktop web app — same cameras, a bigger dashboard."
    : "It is made for computers. On a phone, use the mobile web app — it fits your screen and installs to the home screen.";
  const a = wall.querySelector("a.btn");
  a.href = other.href; a.textContent = other.label;
  document.body.replaceChildren(wall);
  return true;
}
