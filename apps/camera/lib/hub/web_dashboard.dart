import 'brand_assets.dart';

/// Single-page web dashboard served by the main phone (see WebApi).
/// Self-contained: no external scripts, fonts or images (the logo is inlined).
/// All dynamic text is inserted with textContent, never as HTML.
final String dashboardHtml = _html.replaceAll('%VYRO_LOGO%', vyroLogoDataUri).replaceAll('%VYRO_FAVICON%', vyroFaviconDataUri);

const String _html = r'''<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>VYRO</title>
<link rel="icon" type="image/png" href="%VYRO_FAVICON%">
<style>
  :root {
    --bg:#1c1e24; --surface:#262932; --surface-high:#30343e; --border:#373b47;
    --primary:#facc2e; --on-primary:#15161a; --code:#facc2e; --success:#4ade80; --warning:#fbbf24; --danger:#f25c70;
    --ring-cameras:#8b7cf6; --ring-events:#f25c70; --ai:#a78bfa; --text:#f5f6f8; --muted:#9ca0ab; --faint:#6b7080;
  }
  * { box-sizing:border-box; }
  body { margin:0; background:var(--bg); color:var(--text); font:15px/1.45 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif; }
  button { font:inherit; cursor:pointer; }
  .hidden { display:none !important; }
  .muted { color:var(--muted); } .faint { color:var(--faint); font-size:13px; }
  /* login */
  #login { min-height:100vh; display:grid; place-items:center; padding:24px; }
  .login-card { width:100%; max-width:420px; background:var(--surface); border-radius:28px; padding:32px; }
  .logo { width:64px; height:64px; display:block; margin:6px 0 18px; filter:drop-shadow(0 0 14px rgba(250,204,46,.35)); }
  h1 { margin:0 0 6px; font-size:26px; letter-spacing:-.4px; }
  .code-input { width:100%; margin:22px 0 12px; padding:14px; border-radius:18px; border:1.5px solid transparent; background:var(--surface-high);
    color:var(--code); font-size:32px; font-weight:800; letter-spacing:12px; text-align:center; outline:none; }
  .code-input:focus { border-color:var(--primary); }
  .btn { border-radius:14px; padding:11px 18px; font-weight:600; background:var(--surface-high); color:var(--text); border:1px solid transparent; }
  .btn:hover { border-color:var(--primary); }
  .btn.primary { background:var(--primary); border-color:var(--primary); color:var(--on-primary); width:100%; padding:16px; font-size:17px; font-weight:800; border-radius:18px; }
  .btn.ai { background:var(--ai); border-color:var(--ai); color:#111; }
  .btn:disabled { opacity:.5; cursor:default; }
  .error { color:var(--danger); min-height:22px; margin-top:10px; font-size:14px; }
  /* app */
  header { position:sticky; top:0; z-index:5; background:rgba(28,30,36,.92); backdrop-filter:blur(8px); }
  .bar { max-width:1200px; margin:0 auto; padding:14px 20px; display:flex; align-items:center; gap:16px; }
  .brand { display:flex; align-items:center; gap:10px; font-weight:700; font-size:18px; }
  .brand .logo { width:30px; height:30px; margin:0 2px 0 0; filter:none; }
  .brand span { letter-spacing:.12em; font-weight:800; }
  .tabs { display:flex; gap:6px; margin-left:12px; }
  .tab { background:none; border:0; color:var(--muted); padding:8px 14px; border-radius:10px; font-weight:600; }
  .tab.active { background:var(--primary); color:var(--on-primary); }
  .badge { background:var(--danger); color:#fff; border-radius:999px; font-size:11px; padding:1px 7px; margin-left:6px; font-weight:800; }
  .spacer { flex:1; }
  main { max-width:1200px; margin:0 auto; padding:20px; }
  .section-title { text-align:center; font-size:18px; font-weight:600; color:var(--text); margin:22px 4px 14px; }
  .section-title::before { content:"☀  "; color:var(--primary); }
  .ring-header { text-align:center; margin:8px 0 22px; }
  .ring-header svg { display:block; margin:0 auto 12px; }
  .ring-header h2 { margin:0; font-size:30px; font-weight:800; letter-spacing:-.4px; }
  .ring-header .count { color:var(--muted); margin-top:4px; } .ring-header .count b { color:var(--text); }
  .banner { display:flex; align-items:center; gap:14px; background:var(--primary); color:var(--on-primary); border-radius:22px; padding:18px 16px 18px 22px; margin-bottom:8px; }
  .banner b { font-size:19px; font-weight:800; display:block; } .banner span { opacity:.75; font-size:14px; }
  .banner .round { margin-left:auto; width:46px; height:46px; border-radius:50%; background:var(--on-primary); color:#fff; display:grid; place-items:center; font-size:22px; flex:none; }
  .grid { display:grid; grid-template-columns:repeat(auto-fill,minmax(320px,1fr)); gap:16px; }
  .card { background:var(--surface); border-radius:22px; overflow:hidden; }
  .video { position:relative; aspect-ratio:16/10; background:#000; display:grid; place-items:center; }
  .video canvas { max-width:100%; max-height:100%; }
  .video .msg { position:absolute; color:var(--muted); font-size:14px; text-align:center; padding:16px; }
  .overlay { position:absolute; top:10px; left:10px; display:flex; gap:6px; }
  .chip { display:inline-flex; align-items:center; gap:6px; padding:3px 10px; border-radius:999px; font-size:12px; font-weight:700; }
  .chip::before { content:""; width:7px; height:7px; border-radius:50%; background:currentColor; }
  .chip.live { background:var(--danger); color:#fff; } .chip.live::before { background:#fff; }
  .chip.motion { background:var(--primary); color:var(--on-primary); } .chip.motion::before { background:var(--on-primary); }
  .chip.s-live { color:var(--success); background:rgba(52,211,153,.12); }
  .chip.s-online { color:var(--primary); background:rgba(79,140,255,.12); }
  .chip.s-connecting { color:var(--warning); background:rgba(251,191,36,.12); }
  .chip.s-offline { color:var(--faint); background:rgba(100,116,139,.15); }
  .chip.s-reconnecting { color:var(--warning); background:rgba(251,191,36,.12); }
  .chip.low { background:var(--danger); color:#fff; } .chip.low::before { background:#fff; }
  .video canvas.stale { filter:brightness(.45); }
  .filters { display:flex; flex-wrap:wrap; gap:8px; justify-content:center; margin:4px 0 6px; }
  .filters select { background:var(--surface); color:var(--text); border:1.5px solid transparent; border-radius:999px; padding:8px 14px; font:inherit; font-size:14px; }
  .filters select:focus { outline:none; border-color:var(--primary); }
  .empty-filter { text-align:center; padding:28px 12px; }
  header .btn { white-space:nowrap; }
  .chip.ai { color:var(--ai); background:rgba(167,139,250,.14); }
  .card-body { padding:14px 16px 16px; }
  .row { display:flex; align-items:center; gap:10px; }
  .name { font-weight:700; font-size:16px; }
  .actions { display:flex; gap:8px; margin-top:12px; flex-wrap:wrap; }
  .settings { margin-top:12px; padding-top:12px; border-top:1px solid var(--border); display:grid; gap:10px; }
  .toggle { display:flex; align-items:center; justify-content:space-between; gap:12px; }
  .toggle input[type=checkbox] { appearance:none; width:30px; height:30px; border-radius:50%; border:1.6px solid var(--faint); cursor:pointer; flex:none; }
  .toggle input[type=checkbox]:checked { background:#fff; border-color:#fff; background-image:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24'%3E%3Cpath d='M5 12.5l4.5 4.5L19 7.5' fill='none' stroke='%2315161a' stroke-width='3' stroke-linecap='round' stroke-linejoin='round'/%3E%3C/svg%3E"); background-size:62%; background-position:center; background-repeat:no-repeat; }
  .toggle input[type=checkbox]:disabled { opacity:.4; }
  input[type=range] { width:100%; accent-color:var(--primary); }
  .ai-answer { margin-top:12px; padding:12px 14px; border-radius:12px; background:rgba(167,139,250,.10); border:1px solid rgba(167,139,250,.3); }
  .empty { text-align:center; padding:60px 20px; color:var(--muted); }
  .empty .big { font-size:20px; color:var(--text); font-weight:700; margin-bottom:6px; }
  .code-box { display:inline-block; margin-top:14px; padding:12px 20px; border-radius:18px; background:var(--surface); color:var(--code); font-size:32px; font-weight:800; letter-spacing:6px; }
  /* AI tasks */
  .ai-title::before { content:"✦  " !important; color:var(--ai) !important; }
  .tasks { display:grid; gap:12px; margin-bottom:12px; }
  .task .name { font-size:15px; }
  .task-icon { width:44px; height:44px; border-radius:50%; display:grid; place-items:center; flex:none; font-size:18px;
    box-shadow:0 0 0 4px rgba(100,112,128,.5); background:var(--surface-high); }
  .task-icon.active { box-shadow:0 0 0 4px var(--ai); }
  .task-icon.done { box-shadow:0 0 0 4px var(--success); }
  .bar { height:8px; border-radius:99px; background:var(--surface-high); margin-top:12px; overflow:hidden; }
  .bar div { height:100%; background:var(--primary); border-radius:99px; }
  .obs { margin-top:10px; font-size:14px; }
  .status { margin-top:10px; padding-top:10px; border-top:1px solid var(--border); color:var(--muted); font-size:13.5px; }
  .status.urgent { color:var(--danger); }
  .btn.yellow { background:var(--primary); border-color:var(--primary); color:var(--on-primary); font-weight:700; }
  .task-form { display:grid; gap:10px; margin-bottom:6px; }
  .task-form select, .task-form textarea { background:var(--surface-high); color:var(--text); border:1.5px solid transparent; border-radius:14px; padding:10px 12px; font:inherit; }
  .task-form textarea { width:100%; resize:vertical; }
  .task-form textarea:focus, .task-form select:focus { outline:none; border-color:var(--primary); }
  .task-form label { display:flex; align-items:center; gap:10px; color:var(--muted); }
  /* events */
  .events { display:grid; gap:10px; }
  .event { display:flex; gap:14px; background:var(--surface); border:1px solid transparent; border-radius:22px; overflow:hidden; cursor:pointer; padding:12px; }
  .event:hover { border-color:var(--primary); }
  .thumb { width:120px; height:84px; border-radius:14px; background:var(--surface-high); flex:none; overflow:hidden; display:grid; place-items:center; }
  .thumb img { width:100%; height:100%; object-fit:cover; }
  .event .info { padding:2px 6px 2px 0; flex:1; min-width:0; }
  .dot { width:8px; height:8px; border-radius:50%; background:var(--danger); display:inline-block; margin-right:6px; }
  .summary { margin-top:6px; font-size:14px; }
  .summary::before { content:"✦ "; color:var(--ai); }
  dialog { border:0; border-radius:26px; background:var(--surface); color:var(--text); padding:0; max-width:min(860px,94vw); width:100%; }
  dialog::backdrop { background:rgba(0,0,0,.7); }
  .dlg-body { padding:18px 20px 22px; }
  .dlg-img { background:#000; display:grid; place-items:center; max-height:60vh; }
  .dlg-img canvas { max-width:100%; max-height:60vh; }
  .kv { display:grid; grid-template-columns:150px 1fr; gap:6px 12px; margin-top:12px; font-size:14px; }
  .kv div:nth-child(odd) { color:var(--muted); }
  @media (max-width:640px) { .tabs { margin-left:0; } .brand span, #hub-name { display:none; } .thumb { width:110px; } .bar { gap:10px; } }
</style>
</head>
<body>
<section id="login" class="hidden">
  <div class="login-card">
    <img class="logo" src="%VYRO_LOGO%" alt="">
    <h1>VYRO</h1>
    <div class="muted">Enter the pairing code shown on your main phone (Cameras screen).</div>
    <input id="code" class="code-input" inputmode="numeric" maxlength="6" autocomplete="one-time-code" placeholder="••••••">
    <button id="signin" class="btn primary">Sign in</button>
    <div id="login-error" class="error"></div>
    <div class="faint">The dashboard works while the main phone has VYRO open on this network.</div>
  </div>
</section>

<section id="app" class="hidden">
  <header><div class="bar">
    <div class="brand"><img class="logo" src="%VYRO_LOGO%" alt=""><span>VYRO</span></div>
    <nav class="tabs">
      <button class="tab active" data-tab="cameras">Cameras</button>
      <button class="tab" data-tab="events">Events<span id="unseen" class="badge hidden"></span></button>
    </nav>
    <div class="spacer"></div>
    <div id="hub-name" class="faint"></div>
    <button id="signout" class="btn">Sign out</button>
  </div></header>
  <main>
    <div id="tab-cameras"></div>
    <div id="tab-events" class="hidden"></div>
  </main>
</section>

<dialog id="dlg"><div class="dlg-img"><canvas id="dlg-canvas"></canvas></div><div class="dlg-body" id="dlg-body"></div></dialog>

<script>
"use strict";
const LABELS = { person:"Person", vehicle:"Vehicle", animal:"Animal", package:"Package", motion_other:"Motion", no_activity:"No activity", camera_problem:"Camera problem" };
const state = { data:null, tab:"cameras", openSettings:new Set(), answers:{}, frameTimers:{}, filters:{ camera:"", type:"", period:"" } };
const STATUS = { live:"Live", connecting:"Connecting", online:"Online", reconnecting:"Reconnecting…", offline:"Offline" };
function ago(iso) {
  if (!iso) return "not yet";
  const s = (Date.now() - new Date(iso)) / 1000;
  if (s < 10) return "just now"; if (s < 60) return `${Math.round(s)}s ago`;
  if (s < 3600) return `${Math.round(s / 60)} min ago`; if (s < 86400) return `${Math.round(s / 3600)} h ago`;
  return `${Math.round(s / 86400)} days ago`;
}

function el(tag, attrs, ...children) {
  const n = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs || {})) {
    if (v === null || v === undefined || v === false) continue;
    if (k === "class") n.className = v;
    else if (k.startsWith("on")) n.addEventListener(k.slice(2), v);
    else n.setAttribute(k, v === true ? "" : v);
  }
  for (const c of children.flat()) if (c !== null && c !== undefined && c !== false) n.append(c.nodeType ? c : document.createTextNode(String(c)));
  return n;
}
async function api(path, opts = {}) {
  const res = await fetch(path, { credentials:"same-origin", headers:{ "Content-Type":"application/json" }, ...opts });
  if (res.status === 401 && path !== "/api/v1/web/login") { showLogin(); throw new Error("signed out"); }
  return res;
}
function time(iso) { return new Date(iso).toLocaleTimeString([], { hour:"2-digit", minute:"2-digit" }); }
function day(iso) {
  const d = new Date(iso), t = new Date(), y = new Date(Date.now() - 864e5);
  if (d.toDateString() === t.toDateString()) return "Today";
  if (d.toDateString() === y.toDateString()) return "Yesterday";
  return d.toLocaleDateString();
}
function drawRotated(canvas, img, deg) {
  const side = deg % 180 !== 0;
  canvas.width = side ? img.height : img.width;
  canvas.height = side ? img.width : img.height;
  const ctx = canvas.getContext("2d");
  ctx.translate(canvas.width / 2, canvas.height / 2);
  ctx.rotate(deg * Math.PI / 180);
  ctx.drawImage(img, -img.width / 2, -img.height / 2);
}
async function loadInto(canvas, url, deg) {
  const res = await api(url);
  if (!res.ok) throw new Error(String(res.status));
  const bmp = await createImageBitmap(await res.blob());
  drawRotated(canvas, bmp, deg || 0);
}

// ---------------------------------------------------------------- login
function showLogin() {
  document.getElementById("app").classList.add("hidden");
  document.getElementById("login").classList.remove("hidden");
  Object.values(state.frameTimers).forEach(clearTimeout);
  state.frameTimers = {};
  document.getElementById("code").focus();
}
async function signIn() {
  const code = document.getElementById("code").value.trim();
  const err = document.getElementById("login-error");
  err.textContent = "";
  if (!/^\d{6}$/.test(code)) { err.textContent = "The code has 6 digits."; return; }
  const res = await api("/api/v1/web/login", { method:"POST", body:JSON.stringify({ code }) });
  if (!res.ok) { err.textContent = (await res.json()).detail || "Sign-in failed."; return; }
  document.getElementById("code").value = "";
  start();
}
document.getElementById("signin").onclick = signIn;
document.getElementById("code").addEventListener("keydown", e => { if (e.key === "Enter") signIn(); });
document.getElementById("signout").onclick = async () => { await api("/api/v1/web/logout", { method:"POST" }); showLogin(); };
document.querySelectorAll(".tab").forEach(t => t.onclick = () => {
  state.tab = t.dataset.tab;
  document.querySelectorAll(".tab").forEach(x => x.classList.toggle("active", x === t));
  document.getElementById("tab-cameras").classList.toggle("hidden", state.tab !== "cameras");
  document.getElementById("tab-events").classList.toggle("hidden", state.tab !== "events");
  if (state.tab === "events" && state.data && state.data.unseen) api("/api/v1/web/events/seen", { method:"POST" });
});

// ---------------------------------------------------------------- data
async function refresh() {
  try {
    const res = await api("/api/v1/web/state");
    if (!res.ok) return;
    state.data = await res.json();
    render();
  } catch (_) {}
}
let refreshTimer = null;
async function start() {
  document.getElementById("login").classList.add("hidden");
  document.getElementById("app").classList.remove("hidden");
  await refresh();
  clearInterval(refreshTimer);
  refreshTimer = setInterval(refresh, 3000);
}

// ---------------------------------------------------------------- cameras
const cards = {};
function render() {
  const d = state.data;
  document.getElementById("hub-name").textContent = d.hub.name || "";
  const badge = document.getElementById("unseen");
  badge.textContent = d.unseen; badge.classList.toggle("hidden", !d.unseen);
  renderCameras(d); renderEvents(d);
}
function svg(tag, attrs) { const n = document.createElementNS("http://www.w3.org/2000/svg", tag); for (const [k, v] of Object.entries(attrs)) n.setAttribute(k, v); return n; }
function ringHeader(icon, color, progress, title, strong, rest) {
  const r = 34, c = 2 * Math.PI * r;
  const s = svg("svg", { width:"76", height:"76", viewBox:"0 0 76 76" });
  s.append(svg("circle", { cx:"38", cy:"38", r:String(r), fill:"none", stroke:color, "stroke-opacity":"0.22", "stroke-width":"6" }));
  // An empty arc with round caps would still draw a dot, so skip it at 0%.
  if (progress > 0) s.append(svg("circle", { cx:"38", cy:"38", r:String(r), fill:"none", stroke:color, "stroke-width":"6", "stroke-linecap":"round",
      "stroke-dasharray":`${c * Math.min(1, progress)} ${c}`, transform:"rotate(-90 38 38)" }));
  s.append(svg("circle", { cx:"38", cy:"38", r:"25", fill:"#30343e" }));
  const t = svg("text", { x:"38", y:"46", "text-anchor":"middle", "font-size":"22" }); t.textContent = icon; s.append(t);
  return el("div", { class:"ring-header" }, s, el("h2", {}, title), el("div", { class:"count" }, strong ? el("b", {}, strong) : "", rest ? ` ${rest}` : ""));
}
function renderCameras(d) {
  const root = document.getElementById("tab-cameras");
  const live = d.cameras.filter(c => c.status === "live").length;
  const header = ringHeader("📹", "#8b7cf6", d.cameras.length ? live / d.cameras.length : 0,
    d.cameras.length ? "Camera status" : "No cameras yet", d.cameras.length ? `${live}/${d.cameras.length}` : "", d.cameras.length ? "cameras live" : "Turn a spare phone into a camera");
  const top = root.querySelector(".ring-header");
  if (top) top.replaceWith(header); else root.prepend(header);
  if (!d.cameras.length) {
    root.replaceChildren(header, el("div", { class:"banner" }, el("div", {}, el("b", {}, "Add a camera"),
      el("span", {}, "On another phone open VYRO, choose Camera, and enter the main phone's pairing code.")), el("div", { class:"round" }, "+")));
    return;
  }
  let grid = root.querySelector(".grid");
  if (!grid) {
    grid = el("div", { class:"grid" });
    root.replaceChildren(header, el("div", { class:"section-title ai-title" }, "AI tasks"), el("div", { id:"task-list", class:"tasks" }),
      d.hub.ai_available ? taskForm() : el("div", { class:"faint", style:"text-align:center" }, "AI tasks need the AI service."),
      el("div", { class:"section-title" }, "All cameras"), grid);
  }
  renderTasks(d);
  syncTaskFormCameras(d);
  const ids = new Set(d.cameras.map(c => c.camera_id));
  for (const id of Object.keys(cards)) if (!ids.has(id)) { cards[id].remove(); delete cards[id]; clearTimeout(state.frameTimers[id]); }
  for (const cam of d.cameras) {
    if (!cards[cam.camera_id]) { cards[cam.camera_id] = el("div", { class:"card" }); grid.append(cards[cam.camera_id]); }
    updateCard(cards[cam.camera_id], cam, d.hub.ai_available);
  }
}
function updateCard(card, cam, aiAvailable) {
  if (!card.canvas) {
    card.canvas = el("canvas");
    card.msg = el("div", { class:"msg" });
    card.overlay = el("div", { class:"overlay" });
    card.body = el("div", { class:"card-body" });
    card.append(el("div", { class:"video" }, card.canvas, card.msg, card.overlay), card.body);
  }
  const live = cam.status === "live";
  card.overlay.replaceChildren(live ? el("span", { class:"chip live" }, "LIVE") : "",
    cam.status === "reconnecting" ? el("span", { class:"chip s-reconnecting" }, "Reconnecting") : "",
    cam.motion_active ? el("span", { class:"chip motion" }, "Motion") : "",
    cam.battery_low ? el("span", { class:"chip low" }, "Low battery") : "");
  if (live) {
    card.stalePicture = null;
    card.canvas.classList.remove("stale");
    card.msg.textContent = card.hasFrame ? "" : "Loading picture…";
    card.canvas.classList.toggle("hidden", !card.hasFrame);
    if (!state.frameTimers[cam.camera_id]) pollFrame(card, cam.camera_id);
  } else if (cam.picture_at) {
    // Not streaming: show the last picture, dimmed, with its age.
    card.canvas.classList.add("stale");
    card.msg.textContent = `Last picture · ${ago(cam.picture_at)}`;
    if (card.stalePicture !== cam.picture_at) {
      card.stalePicture = cam.picture_at;
      loadInto(card.canvas, `/api/v1/web/cameras/${encodeURIComponent(cam.camera_id)}/picture`, cam.picture_rotation)
        .then(() => card.canvas.classList.remove("hidden")).catch(() => {});
    }
  } else {
    card.canvas.classList.add("hidden");
    card.msg.textContent = cam.status === "online" ? "Tap Start streaming on the camera phone" : (STATUS[cam.status] || "Camera offline");
  }

  const details = [cam.battery != null ? `${cam.battery}% battery${cam.charging ? " ⚡" : ""}` : null,
    live ? `${cam.bitrate_kbps} kbps` : null,
    cam.status === "offline" || cam.status === "reconnecting" ? `last seen ${ago(cam.last_seen)}` : null,
    cam.settings.motion_enabled ? (cam.motion_active ? "motion now" : "motion on") : "motion off",
    aiAvailable && cam.settings.ai_enabled ? "AI on" : null].filter(Boolean).join(" · ");
  const open = state.openSettings.has(cam.camera_id);
  const answer = state.answers[cam.camera_id];
  card.body.replaceChildren(
    el("div", { class:"row" }, el("span", { class:"name" }, cam.name), el("span", { class:`chip s-${cam.status}` }, STATUS[cam.status] || cam.status)),
    el("div", { class:"faint", style:"margin-top:4px" }, details),
    el("div", { class:"actions" },
      aiAvailable ? el("button", { class:"btn ai", disabled:!live || answer === "…", onclick:() => askAi(cam) }, answer === "…" ? "Asking AI…" : "✦ Ask AI") : "",
      el("button", { class:"btn", onclick:() => { open ? state.openSettings.delete(cam.camera_id) : state.openSettings.add(cam.camera_id); render(); } }, open ? "Close settings" : "Settings")),
    answer && answer !== "…" ? aiAnswer(answer) : "",
    open ? settingsPanel(cam, aiAvailable) : "");
}
function pollFrame(card, id) {
  const tick = async () => {
    const cam = state.data && state.data.cameras.find(c => c.camera_id === id);
    if (!cam || cam.status !== "live" || document.getElementById("app").classList.contains("hidden")) { delete state.frameTimers[id]; card.hasFrame = false; card.stalePicture = null; return; }
    try { await loadInto(card.canvas, `/api/v1/web/cameras/${encodeURIComponent(id)}/frame`, cam.rotation); card.hasFrame = true; card.msg.textContent = ""; card.canvas.classList.remove("hidden"); } catch (_) {}
    state.frameTimers[id] = setTimeout(tick, 1000);
  };
  state.frameTimers[id] = setTimeout(tick, 0);
}
function aiAnswer(a) {
  if (a.error) return el("div", { class:"ai-answer" }, el("span", { style:"color:var(--danger)" }, a.error));
  return el("div", { class:"ai-answer" }, el("div", {}, a.summary),
    el("div", { class:"actions" }, el("span", { class:"chip ai" }, LABELS[a.category] || a.category),
      a.people_count ? el("span", { class:"chip s-online" }, `${a.people_count} ${a.people_count === 1 ? "person" : "people"}`) : "",
      el("span", { class:"chip s-connecting" }, `Threat: ${a.threat_level}`)));
}
async function askAi(cam) {
  state.answers[cam.camera_id] = "…"; render();
  const res = await api(`/api/v1/web/cameras/${encodeURIComponent(cam.camera_id)}/ask-ai`, { method:"POST" });
  const body = await res.json();
  state.answers[cam.camera_id] = res.ok ? body : { error: body.detail || "AI request failed" };
  refresh();
}
function settingsPanel(cam, aiAvailable) {
  const s = cam.settings;
  const save = async patch => {
    await api(`/api/v1/web/cameras/${encodeURIComponent(cam.camera_id)}/settings`, { method:"PUT", body:JSON.stringify(patch) });
    refresh();
  };
  const toggle = (label, hint, key, value, disabled) => el("label", { class:"toggle" },
    el("span", {}, label, el("div", { class:"faint" }, hint)),
    el("input", { type:"checkbox", checked:value, disabled, onchange:e => {
      if (key === "ai_enabled" && e.target.checked && !confirm("Turn on AI descriptions?\n\nWhen this camera detects motion, one snapshot is sent to Groq (an online AI service). Live video never leaves your network.")) { e.target.checked = false; return; }
      save({ [key]: e.target.checked });
    } }));
  return el("div", { class:"settings" },
    toggle("Motion detection", "Runs on the camera phone.", "motion_enabled", s.motion_enabled),
    el("div", {}, el("div", { class:"row" }, el("span", {}, "Sensitivity"), el("span", { class:"spacer" }), el("span", { class:"faint" }, s.sensitivity < .34 ? "Low" : s.sensitivity < .67 ? "Medium" : "High")),
      el("input", { type:"range", min:"0", max:"1", step:"0.1", value:String(s.sensitivity), disabled:!s.motion_enabled, onchange:e => save({ sensitivity: Number(e.target.value) }) })),
    toggle("Alerts on the main phone", "At most one per minute.", "notify", s.notify),
    toggle("AI descriptions (Groq)", aiAvailable ? "Describe motion snapshots." : "Not available on this main phone.", "ai_enabled", aiAvailable && s.ai_enabled, !aiAvailable));
}

// ---------------------------------------------------------------- AI tasks
function renderTasks(d) {
  const list = document.getElementById("task-list");
  if (!list) return;
  if (!d.tasks.length) {
    list.replaceChildren(el("div", { class:"card card-body faint", style:"text-align:center" },
      "Give a camera a job in plain words — \"tell me when the washing machine is full\" — and the AI watches for it."));
    return;
  }
  list.replaceChildren(...d.tasks.map(t => {
    const done = t.status === "done", active = t.status === "watching";
    const act = (label, action, primary) => el("button", { class: primary ? "btn yellow" : "btn", onclick: async () => {
      if (action === "delete" && !confirm(`Delete this task?\n\n${t.description}`)) return;
      await api(`/api/v1/web/tasks/${encodeURIComponent(t.id)}${action === "delete" ? "" : "/" + action}`, { method: action === "delete" ? "DELETE" : "POST" });
      refresh();
    } }, label);
    const pct = done ? 100 : (t.progress ?? 0);
    return el("div", { class:"card card-body task" },
      el("div", { class:"row" },
        el("span", { class:"task-icon" + (done ? " done" : active ? " active" : "") }, done ? "✓" : "✦"),
        el("div", { style:"flex:1; min-width:0" }, el("div", { class:"name" }, t.description),
          el("div", { class:"faint" }, `${t.camera_name}${t.progress_applicable && t.progress != null ? ` · ~${t.progress}%` : ""}`))),
      t.progress_applicable || done ? el("div", { class:"bar" }, el("div", { style:`width:${pct}%` })) : "",
      t.observation ? el("div", { class:"obs" }, `“${t.observation}”`) : "",
      el("div", { class: t.has_error || t.needs_ack ? "status urgent" : "status" }, t.status_text),
      el("div", { class:"actions" },
        t.needs_ack ? act("Handled", "ack", true) : "",
        active ? act("Pause", "pause") : "",
        t.status === "paused" ? act("Resume", "resume", true) : "",
        !active && t.status !== "paused" && !t.needs_ack ? act("Watch again", "resume") : "",
        active ? act("Stop", "stop") : act("Delete", "delete")));
  }));
}
function taskForm() {
  const sel = el("select", { id:"task-camera" });
  const text = el("textarea", { id:"task-text", maxlength:"300", rows:"3", placeholder:"e.g. Tell me when the water in the washing machine reaches the MAX line" });
  const interval = el("select", { id:"task-interval" }, ...[[15,"15 s"],[30,"30 s"],[60,"1 min"],[300,"5 min"]].map(([v,l]) => el("option", { value:String(v), selected: v === 30 }, l)));
  const remind = el("input", { type:"checkbox", id:"task-remind", checked:true });
  const msg = el("div", { class:"error" });
  const start = el("button", { class:"btn yellow", onclick: async () => {
    msg.textContent = "";
    const res = await api("/api/v1/web/tasks", { method:"POST", body: JSON.stringify({ camera_id: sel.value, description: text.value,
      interval_seconds: Number(interval.value), remind_until_ack: remind.checked }) });
    if (!res.ok) { msg.textContent = (await res.json()).detail || "Could not start the task."; return; }
    text.value = ""; refresh();
  } }, "✦ Start watching");
  return el("div", { class:"card card-body task-form" },
    el("b", {}, "New AI task"),
    el("div", { class:"faint" }, "Describe what the AI should watch for. Pictures from that camera go to Groq while the task runs."),
    el("label", {}, "Camera", sel), text,
    el("div", { class:"row", style:"gap:16px; flex-wrap:wrap" }, el("label", {}, "Check every ", interval),
      el("label", { class:"row", style:"gap:8px" }, remind, "Remind me until handled")),
    start, msg);
}
function syncTaskFormCameras(d) {
  const sel = document.getElementById("task-camera");
  if (!sel) return;
  const want = d.cameras.map(c => `${c.camera_id}|${c.name}`).join(",");
  if (sel.dataset.cams === want) return;
  const prev = sel.value;
  sel.replaceChildren(...d.cameras.map(c => el("option", { value:c.camera_id, selected: c.camera_id === prev }, c.name)));
  sel.dataset.cams = want;
}

// ---------------------------------------------------------------- events
function eventTitle(e) { if (e.type === "task_done") return "Task done"; return e.ai_category ? (LABELS[e.ai_category] || "Motion") : (e.type === "ai_check" ? "AI check" : "Motion"); }
function renderEvents(d) {
  const root = document.getElementById("tab-events");
  // Redraw only when something changed, so an open filter menu stays open.
  const sig = JSON.stringify([d.unseen, state.filters, d.events.map(e => [e.id, e.seen, e.ended_at, e.ai_summary])]);
  if (root.sig === sig) return;
  root.sig = sig;
  const header = ringHeader("🔔", "#f25c70", d.events.length ? (d.events.length - d.unseen) / d.events.length : 0,
    d.events.length ? "Activity" : "All quiet", d.events.length ? String(d.unseen) : "", d.events.length ? (d.unseen === 1 ? "new event" : "new events") : "Motion and AI checks appear here");
  if (!d.events.length) { root.replaceChildren(header); return; }
  const f = state.filters;
  const since = f.period === "today" ? new Date(new Date().toDateString()).getTime() : f.period === "week" ? Date.now() - 7 * 864e5 : 0;
  const shown = d.events.filter(e => (!f.camera || e.camera_id === f.camera)
    && (!f.type || (f.type === "ai" ? !!e.ai_summary : e.type === f.type))
    && new Date(e.started_at).getTime() >= since);
  const out = [header, eventFilters(d)]; let last = null;
  if (!shown.length) out.push(el("div", { class:"faint empty-filter" }, "No events match these filters."));
  for (const e of shown) {
    const dd = day(e.started_at);
    if (dd !== last) { out.push(el("div", { class:"section-title", style:"margin-top:18px" }, dd)); last = dd; }
    const rot = e.rotation ? `transform:rotate(${e.rotation}deg)` : "";
    out.push(el("div", { class:"event", onclick:() => openEvent(e) },
      el("div", { class:"thumb" }, e.has_snapshot ? el("img", { src:`/api/v1/web/events/${encodeURIComponent(e.id)}/snapshot`, alt:"", loading:"lazy", style:rot }) : "—"),
      el("div", { class:"info" },
        el("div", { class:"row" }, e.seen ? "" : el("span", { class:"dot" }), el("b", {}, eventTitle(e)), el("span", { class:"spacer" }), el("span", { class:"faint" }, time(e.started_at))),
        el("div", { class:"faint" }, e.camera_name),
        e.ai_summary ? el("div", { class:"summary" }, e.ai_summary) : "")));
  }
  root.replaceChildren(el("div", { class:"events" }, out));
}
function eventFilters(d) {
  const f = state.filters;
  const cams = new Map(d.events.map(e => [e.camera_id, e.camera_name]));
  const pick = (key, options) => el("select", { "aria-label":key, onchange:e => { f[key] = e.target.value; renderEvents(state.data); } },
    ...options.map(([v, l]) => el("option", { value:v, selected: f[key] === v }, l)));
  return el("div", { class:"filters" },
    pick("camera", [["", "All cameras"], ...[...cams].map(([id, name]) => [id, name])]),
    pick("type", [["", "All events"], ["motion", "Motion"], ["ai", "With AI description"], ["ai_check", "AI checks"], ["task_done", "Tasks done"]]),
    pick("period", [["", "Any time"], ["today", "Today"], ["week", "Last 7 days"]]));
}
async function openEvent(e) {
  const dlg = document.getElementById("dlg"), canvas = document.getElementById("dlg-canvas");
  canvas.getContext("2d").clearRect(0, 0, canvas.width, canvas.height);
  const dur = e.type !== "motion" ? "snapshot" : e.ended_at ? `${Math.round((new Date(e.ended_at) - new Date(e.started_at)) / 1000)}s` : "ongoing";
  document.getElementById("dlg-body").replaceChildren(
    el("div", { class:"row" }, el("h1", { style:"font-size:22px" }, eventTitle(e)), el("span", { class:"spacer" }), el("button", { class:"btn", onclick:() => dlg.close() }, "Close")),
    e.ai_summary ? aiAnswer({ summary:e.ai_summary, category:e.ai_category, threat_level:e.ai_threat_level || "none", people_count:0 }) : (e.ai_error ? el("div", { class:"faint" }, `No AI description: ${e.ai_error}`) : ""),
    el("div", { class:"kv" }, el("div", {}, "Camera"), el("div", {}, e.camera_name), el("div", {}, "When"), el("div", {}, `${day(e.started_at)} at ${time(e.started_at)}`),
      el("div", {}, "Duration"), el("div", {}, dur)));
  dlg.showModal();
  if (e.has_snapshot) loadInto(canvas, `/api/v1/web/events/${encodeURIComponent(e.id)}/snapshot`, e.rotation).catch(() => {});
}

// ---------------------------------------------------------------- boot
fetch("/api/v1/web/state", { credentials:"same-origin" }).then(r => r.ok ? start() : showLogin()).catch(showLogin);
</script>
</body>
</html>
''';
