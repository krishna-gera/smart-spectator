/// Single-page web dashboard served by the main phone (see WebApi).
/// Self-contained: no external scripts, fonts or images. All dynamic text is
/// inserted with textContent, never as HTML.
const String dashboardHtml = r'''<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Smart Spectator</title>
<style>
  :root {
    --bg:#0a0f1c; --surface:#111827; --surface-high:#1a2335; --border:#243049;
    --primary:#4f8cff; --code:#f5b544; --success:#34d399; --warning:#fbbf24; --danger:#f87171;
    --ai:#a78bfa; --text:#e8edf6; --muted:#94a3b8; --faint:#64748b;
  }
  * { box-sizing:border-box; }
  body { margin:0; background:var(--bg); color:var(--text); font:15px/1.45 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif; }
  button { font:inherit; cursor:pointer; }
  .hidden { display:none !important; }
  .muted { color:var(--muted); } .faint { color:var(--faint); font-size:13px; }
  /* login */
  #login { min-height:100vh; display:grid; place-items:center; padding:24px; }
  .login-card { width:100%; max-width:420px; background:var(--surface); border:1px solid var(--border); border-radius:20px; padding:32px; }
  .logo { width:56px; height:56px; border-radius:16px; background:linear-gradient(135deg,var(--primary),var(--ai)); display:grid; place-items:center; font-size:28px; margin-bottom:18px; }
  h1 { margin:0 0 6px; font-size:26px; letter-spacing:-.4px; }
  .code-input { width:100%; margin:22px 0 12px; padding:14px; border-radius:14px; border:1.5px solid var(--border); background:var(--surface-high);
    color:var(--code); font-size:32px; font-weight:800; letter-spacing:12px; text-align:center; outline:none; }
  .code-input:focus { border-color:var(--primary); }
  .btn { border:0; border-radius:12px; padding:12px 18px; font-weight:600; background:var(--surface-high); color:var(--text); border:1px solid var(--border); }
  .btn:hover { border-color:var(--primary); }
  .btn.primary { background:var(--primary); border-color:var(--primary); color:#fff; width:100%; padding:14px; font-size:16px; }
  .btn.ai { background:var(--ai); border-color:var(--ai); color:#111; }
  .btn:disabled { opacity:.5; cursor:default; }
  .error { color:var(--danger); min-height:22px; margin-top:10px; font-size:14px; }
  /* app */
  header { position:sticky; top:0; z-index:5; background:rgba(10,15,28,.92); backdrop-filter:blur(8px); border-bottom:1px solid var(--border); }
  .bar { max-width:1200px; margin:0 auto; padding:14px 20px; display:flex; align-items:center; gap:16px; }
  .brand { display:flex; align-items:center; gap:10px; font-weight:700; font-size:18px; }
  .brand .logo { width:34px; height:34px; border-radius:10px; font-size:17px; margin:0; }
  .tabs { display:flex; gap:6px; margin-left:12px; }
  .tab { background:none; border:0; color:var(--muted); padding:8px 14px; border-radius:10px; font-weight:600; }
  .tab.active { background:rgba(79,140,255,.16); color:var(--text); }
  .badge { background:var(--code); color:#111; border-radius:999px; font-size:11px; padding:1px 7px; margin-left:6px; font-weight:800; }
  .spacer { flex:1; }
  main { max-width:1200px; margin:0 auto; padding:20px; }
  .section-title { text-transform:uppercase; letter-spacing:1.1px; font-size:12px; font-weight:700; color:var(--muted); margin:8px 4px 12px; }
  .grid { display:grid; grid-template-columns:repeat(auto-fill,minmax(320px,1fr)); gap:16px; }
  .card { background:var(--surface); border:1px solid var(--border); border-radius:18px; overflow:hidden; }
  .video { position:relative; aspect-ratio:16/10; background:#000; display:grid; place-items:center; }
  .video canvas { max-width:100%; max-height:100%; }
  .video .msg { position:absolute; color:var(--muted); font-size:14px; text-align:center; padding:16px; }
  .overlay { position:absolute; top:10px; left:10px; display:flex; gap:6px; }
  .chip { display:inline-flex; align-items:center; gap:6px; padding:3px 10px; border-radius:999px; font-size:12px; font-weight:700; }
  .chip::before { content:""; width:7px; height:7px; border-radius:50%; background:currentColor; }
  .chip.live { background:var(--danger); color:#111; } .chip.live::before { background:#111; }
  .chip.motion { background:var(--warning); color:#111; } .chip.motion::before { background:#111; }
  .chip.s-live { color:var(--success); background:rgba(52,211,153,.12); }
  .chip.s-online { color:var(--primary); background:rgba(79,140,255,.12); }
  .chip.s-connecting { color:var(--warning); background:rgba(251,191,36,.12); }
  .chip.s-offline { color:var(--faint); background:rgba(100,116,139,.15); }
  .chip.ai { color:var(--ai); background:rgba(167,139,250,.14); }
  .card-body { padding:14px 16px 16px; }
  .row { display:flex; align-items:center; gap:10px; }
  .name { font-weight:700; font-size:16px; }
  .actions { display:flex; gap:8px; margin-top:12px; flex-wrap:wrap; }
  .settings { margin-top:12px; padding-top:12px; border-top:1px solid var(--border); display:grid; gap:10px; }
  .toggle { display:flex; align-items:center; justify-content:space-between; gap:12px; }
  .toggle input[type=checkbox] { width:42px; height:24px; accent-color:var(--primary); }
  input[type=range] { width:100%; accent-color:var(--primary); }
  .ai-answer { margin-top:12px; padding:12px 14px; border-radius:12px; background:rgba(167,139,250,.10); border:1px solid rgba(167,139,250,.3); }
  .empty { text-align:center; padding:60px 20px; color:var(--muted); }
  .empty .big { font-size:20px; color:var(--text); font-weight:700; margin-bottom:6px; }
  .code-box { display:inline-block; margin-top:14px; padding:12px 20px; border-radius:14px; background:var(--surface); border:1px solid var(--border); color:var(--code); font-size:32px; font-weight:800; letter-spacing:6px; }
  /* events */
  .events { display:grid; gap:10px; }
  .event { display:flex; gap:14px; background:var(--surface); border:1px solid var(--border); border-radius:16px; overflow:hidden; cursor:pointer; }
  .event:hover { border-color:var(--primary); }
  .thumb { width:140px; min-height:92px; background:var(--surface-high); flex:none; overflow:hidden; display:grid; place-items:center; }
  .thumb img { width:100%; height:100%; object-fit:cover; }
  .event .info { padding:12px 14px 12px 0; flex:1; min-width:0; }
  .dot { width:8px; height:8px; border-radius:50%; background:var(--code); display:inline-block; margin-right:6px; }
  .summary { margin-top:6px; font-size:14px; }
  .summary::before { content:"✦ "; color:var(--ai); }
  dialog { border:1px solid var(--border); border-radius:20px; background:var(--surface); color:var(--text); padding:0; max-width:min(860px,94vw); width:100%; }
  dialog::backdrop { background:rgba(0,0,0,.7); }
  .dlg-body { padding:18px 20px 22px; }
  .dlg-img { background:#000; display:grid; place-items:center; max-height:60vh; }
  .dlg-img canvas { max-width:100%; max-height:60vh; }
  .kv { display:grid; grid-template-columns:150px 1fr; gap:6px 12px; margin-top:12px; font-size:14px; }
  .kv div:nth-child(odd) { color:var(--muted); }
  @media (max-width:640px) { .tabs { margin-left:0; } .brand span { display:none; } .thumb { width:110px; } }
</style>
</head>
<body>
<section id="login" class="hidden">
  <div class="login-card">
    <div class="logo">👁</div>
    <h1>Smart Spectator</h1>
    <div class="muted">Enter the pairing code shown on your main phone (Cameras screen).</div>
    <input id="code" class="code-input" inputmode="numeric" maxlength="6" autocomplete="one-time-code" placeholder="••••••">
    <button id="signin" class="btn primary">Sign in</button>
    <div id="login-error" class="error"></div>
    <div class="faint">The dashboard works while the main phone has Smart Spectator open on this network.</div>
  </div>
</section>

<section id="app" class="hidden">
  <header><div class="bar">
    <div class="brand"><div class="logo">👁</div><span>Smart Spectator</span></div>
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
const state = { data:null, tab:"cameras", openSettings:new Set(), answers:{}, frameTimers:{} };

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
function renderCameras(d) {
  const root = document.getElementById("tab-cameras");
  if (!d.cameras.length) {
    root.replaceChildren(el("div", { class:"empty" },
      el("div", { class:"big" }, "No cameras yet"),
      "On another phone open Smart Spectator, choose Camera, and enter the main phone's pairing code."));
    return;
  }
  const grid = root.querySelector(".grid") || (() => { const g = el("div", { class:"grid" }); root.replaceChildren(el("div", { class:"section-title" }, "Cameras"), g); return g; })();
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
  card.overlay.replaceChildren(live ? el("span", { class:"chip live" }, "LIVE") : "", cam.motion_active ? el("span", { class:"chip motion" }, "Motion") : "");
  card.msg.textContent = live ? (card.hasFrame ? "" : "Loading picture…") : (cam.status === "offline" ? "Camera offline" : "Camera is not streaming");
  card.canvas.classList.toggle("hidden", !live || !card.hasFrame);
  if (live && !state.frameTimers[cam.camera_id]) pollFrame(card, cam.camera_id);

  const details = [cam.battery != null ? `${cam.battery}% battery${cam.charging ? " ⚡" : ""}` : null,
    live ? `${cam.bitrate_kbps} kbps` : null,
    cam.settings.motion_enabled ? (cam.motion_active ? "motion now" : "motion on") : "motion off",
    aiAvailable && cam.settings.ai_enabled ? "AI on" : null].filter(Boolean).join(" · ");
  const open = state.openSettings.has(cam.camera_id);
  const answer = state.answers[cam.camera_id];
  card.body.replaceChildren(
    el("div", { class:"row" }, el("span", { class:"name" }, cam.name), el("span", { class:`chip s-${cam.status}` }, cam.status[0].toUpperCase() + cam.status.slice(1))),
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
    if (!cam || cam.status !== "live" || document.getElementById("app").classList.contains("hidden")) { delete state.frameTimers[id]; card.hasFrame = false; return; }
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

// ---------------------------------------------------------------- events
function eventTitle(e) { return e.ai_category ? (LABELS[e.ai_category] || "Motion") : (e.type === "ai_check" ? "AI check" : "Motion"); }
function renderEvents(d) {
  const root = document.getElementById("tab-events");
  if (!d.events.length) { root.replaceChildren(el("div", { class:"empty" }, el("div", { class:"big" }, "No events yet"), "Motion and AI checks appear here with snapshots.")); return; }
  const out = []; let last = null;
  for (const e of d.events) {
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
