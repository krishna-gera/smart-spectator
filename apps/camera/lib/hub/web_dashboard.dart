import 'brand_assets.dart';

/// Single-page web dashboard served by the main phone (see WebApi).
/// Self-contained: no external scripts, fonts or images (the logo is inlined).
/// All dynamic text is inserted with textContent, never as HTML.
final String dashboardHtml = _html.replaceAll('%VYRO_LOGO%', vyroLogoDataUri).replaceAll('%VYRO_FAVICON%', vyroFaviconDataUri);

const String _html = r'''<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>VYRO</title>
<meta name="theme-color" content="#1C1E24">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
<meta name="apple-mobile-web-app-title" content="VYRO">
<link rel="icon" type="image/png" href="%VYRO_FAVICON%">
<link rel="apple-touch-icon" href="/apple-touch-icon.png">
<link rel="manifest" href="/manifest.webmanifest">
<style>
  /* Same tokens as the app (lib/ui/theme.dart). */
  :root {
    --bg:#1C1E24; --surface:#262932; --surface-high:#30343E; --border:#373B47;
    --primary:#FACC2E; --on-primary:#15161A; --text:#F5F6F8; --muted:#9CA0AB; --faint:#6B7080;
    --success:#4ADE80; --warning:#FBBF24; --danger:#F25C70; --ai:#A78BFA; --ring:#8B7CF6;
    --radius:22px;
  }
  * { box-sizing:border-box; }
  html, body { margin:0; background:var(--bg); color:var(--text); }
  body { font:15px/1.45 -apple-system,BlinkMacSystemFont,"SF Pro Text","Segoe UI",Roboto,Helvetica,Arial,sans-serif; -webkit-font-smoothing:antialiased; }
  button, input, select, textarea { font:inherit; color:inherit; }
  .hidden { display:none !important; }
  .muted { color:var(--muted); } .faint { color:var(--faint); font-size:13px; }
  svg.i { width:20px; height:20px; fill:currentColor; flex:none; }
  svg.i.sm { width:16px; height:16px; }

  /* ---------- login */
  #login { min-height:100vh; display:grid; place-items:center; padding:24px; }
  .login-card { width:100%; max-width:400px; background:var(--surface); border-radius:28px; padding:34px 30px 28px; text-align:center; }
  .login-card .logo { width:76px; height:76px; margin:0 auto 18px; display:block; filter:drop-shadow(0 0 18px rgba(250,204,46,.35)); }
  .wordmark { font-weight:900; letter-spacing:.32em; margin-right:-.32em; }
  .login-card h1 { font-size:30px; margin:0 0 6px; }
  .code-input { width:100%; margin:22px 0 14px; padding:16px; border-radius:18px; border:2px solid transparent; background:var(--surface-high);
    text-align:center; font-size:30px; font-weight:800; letter-spacing:.45em; color:var(--primary); }
  .code-input:focus { outline:none; border-color:var(--primary); }
  .error { color:var(--danger); min-height:20px; margin-top:10px; font-size:14px; }

  /* ---------- buttons */
  .btn { display:inline-flex; align-items:center; justify-content:center; gap:8px; border:0; border-radius:999px; padding:10px 16px; cursor:pointer;
    background:var(--surface-high); color:var(--text); font-weight:600; font-size:14px; transition:filter .15s, transform .05s; white-space:nowrap; }
  .btn:hover { filter:brightness(1.12); } .btn:active { transform:scale(.98); }
  .btn:disabled { opacity:.45; cursor:default; filter:none; }
  .btn.primary { background:var(--primary); color:var(--on-primary); }
  .btn.big { width:100%; padding:15px; font-size:16px; font-weight:800; }
  .btn.ai { background:rgba(167,139,250,.16); color:var(--ai); }
  .btn.danger { background:rgba(242,92,112,.14); color:var(--danger); }
  .btn.ghost { background:transparent; color:var(--muted); }
  .icon-btn { width:38px; height:38px; padding:0; border-radius:50%; }

  /* ---------- header */
  header { position:sticky; top:0; z-index:5; background:rgba(28,30,36,.86); backdrop-filter:blur(14px); -webkit-backdrop-filter:blur(14px); border-bottom:1px solid rgba(55,59,71,.6); }
  .bar { max-width:1280px; margin:0 auto; padding:12px 20px; display:flex; align-items:center; gap:16px; }
  .brand { display:flex; align-items:center; gap:10px; font-size:18px; }
  .brand img { width:30px; height:30px; }
  .tabs { display:flex; gap:4px; background:var(--surface); padding:4px; border-radius:999px; margin-left:12px; }
  .tab { border:0; background:transparent; color:var(--muted); padding:8px 16px; border-radius:999px; cursor:pointer; font-weight:600; display:inline-flex; gap:8px; align-items:center; }
  .tab.active { background:var(--primary); color:var(--on-primary); }
  .badge { background:var(--danger); color:#fff; border-radius:999px; font-size:11px; font-weight:800; padding:1px 7px; }
  .hub { margin-left:auto; display:flex; align-items:center; gap:8px; color:var(--muted); font-size:13px; background:var(--surface); border-radius:999px; padding:7px 12px; }
  .dot { width:8px; height:8px; border-radius:50%; background:var(--success); box-shadow:0 0 0 3px rgba(74,222,128,.18); }
  .dot.off { background:var(--danger); box-shadow:0 0 0 3px rgba(242,92,112,.18); }

  main { max-width:1280px; margin:0 auto; padding:22px 20px 60px; }

  /* ---------- summary */
  .summary { display:flex; align-items:center; gap:18px; background:var(--surface); border-radius:var(--radius); padding:18px 22px; margin-bottom:22px; }
  .summary h2 { margin:0; font-size:26px; letter-spacing:-.3px; }
  .summary .count { color:var(--muted); }
  .summary .count b { color:var(--text); }
  .summary .ring { width:64px; height:64px; }
  .stats { margin-left:auto; display:flex; gap:10px; flex-wrap:wrap; justify-content:flex-end; }
  .stat { background:var(--surface-high); border-radius:16px; padding:10px 14px; min-width:96px; }
  .stat b { display:block; font-size:20px; }
  .stat span { color:var(--muted); font-size:12.5px; }

  .layout { display:grid; grid-template-columns:minmax(0,1fr) 380px; gap:22px; align-items:start; }
  .section-title { display:flex; align-items:center; gap:8px; font-size:18px; font-weight:700; margin:0 0 14px; }
  .section-title svg { color:var(--primary); }
  .section-title.ai svg { color:var(--ai); }

  /* ---------- camera cards */
  .grid { display:grid; grid-template-columns:repeat(auto-fill,minmax(300px,1fr)); gap:18px; }
  .card { background:var(--surface); border-radius:var(--radius); overflow:hidden; }
  .video { position:relative; aspect-ratio:16/10; background:#000; display:grid; place-items:center; overflow:hidden; cursor:default; }
  .video canvas { max-width:100%; max-height:100%; }
  .video canvas.stale { filter:brightness(.42); }
  .video .msg { position:absolute; inset:0; display:grid; place-items:center; align-content:center; gap:8px; color:var(--muted); font-size:14px; text-align:center; padding:16px; }
  .video .msg svg { width:30px; height:30px; color:var(--faint); }
  .video .msg.over { color:var(--text); font-weight:600; }
  .overlay { position:absolute; top:12px; left:12px; display:flex; gap:6px; flex-wrap:wrap; }
  .chip { display:inline-flex; align-items:center; gap:6px; padding:4px 10px; border-radius:999px; font-size:12px; font-weight:700; background:rgba(21,22,26,.7); }
  .chip::before { content:""; width:7px; height:7px; border-radius:50%; background:currentColor; }
  .chip.live { background:var(--danger); color:#fff; } .chip.live::before { background:#fff; }
  .chip.motion { background:var(--warning); color:var(--on-primary); } .chip.motion::before { background:var(--on-primary); }
  .chip.low { background:var(--danger); color:#fff; } .chip.low::before { background:#fff; }
  .chip.reconnecting { color:var(--warning); } .chip.offline { color:var(--danger); }
  .chip.ai { color:var(--ai); background:rgba(21,22,26,.7); }
  .card-body { padding:14px 16px 16px; }
  .row { display:flex; align-items:center; gap:10px; }
  .spacer { flex:1; }
  .name { font-size:18px; font-weight:700; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; min-width:0; }
  .battery { display:inline-flex; align-items:center; gap:4px; font-weight:700; font-size:13px; color:var(--muted); }
  .battery.low { color:var(--danger); } .battery.charging { color:var(--success); }
  .status { display:flex; align-items:center; gap:7px; margin-top:6px; font-size:13.5px; color:var(--muted); }
  .status.live { color:var(--success); } .status.reconnecting { color:var(--warning); } .status.offline { color:var(--danger); }
  .actions { display:flex; gap:8px; flex-wrap:wrap; margin-top:12px; }
  .menu { position:relative; }
  .menu-list { position:absolute; right:0; top:42px; z-index:4; background:var(--surface-high); border-radius:16px; padding:6px; min-width:210px; box-shadow:0 12px 40px rgba(0,0,0,.45); }
  .menu-list button { display:flex; width:100%; align-items:center; gap:10px; border:0; background:transparent; padding:10px 12px; border-radius:10px; cursor:pointer; text-align:left; }
  .menu-list button:hover { background:rgba(255,255,255,.06); }
  .menu-list button.danger { color:var(--danger); }
  .ai-answer { margin-top:12px; background:rgba(167,139,250,.1); border-radius:16px; padding:12px 14px; }
  .settings { margin-top:12px; display:grid; gap:12px; background:var(--surface-high); border-radius:16px; padding:14px; }
  .toggle { display:flex; align-items:center; justify-content:space-between; gap:12px; }
  .toggle input { width:44px; height:26px; appearance:none; -webkit-appearance:none; background:var(--border); border-radius:999px; position:relative; cursor:pointer; flex:none; transition:background .15s; }
  .toggle input::after { content:""; position:absolute; top:3px; left:3px; width:20px; height:20px; border-radius:50%; background:#fff; transition:left .15s; }
  .toggle input:checked { background:var(--primary); } .toggle input:checked::after { left:21px; background:var(--on-primary); }
  .toggle input:disabled { opacity:.4; }
  input[type=range] { width:100%; accent-color:var(--primary); }
  .add-card { border:2px dashed var(--border); background:transparent; border-radius:var(--radius); min-height:260px; display:grid; place-items:center; align-content:center; gap:10px; color:var(--muted); cursor:pointer; padding:20px; text-align:center; }
  .add-card:hover { border-color:var(--primary); color:var(--text); }
  .add-card .round { width:56px; height:56px; border-radius:50%; background:var(--primary); color:var(--on-primary); display:grid; place-items:center; }

  /* ---------- AI tasks */
  .side { position:sticky; top:84px; display:grid; gap:14px; }
  .task { background:var(--surface); border-radius:var(--radius); padding:14px 16px; }
  .task .title { font-weight:700; line-height:1.3; }
  .task .ring { width:40px; height:40px; flex:none; }
  .bar-track { height:6px; border-radius:6px; background:var(--surface-high); overflow:hidden; margin-top:10px; }
  .bar-track div { height:100%; background:var(--ai); border-radius:6px; transition:width .4s; }
  .bar-track.done div { background:var(--success); }
  .obs { margin-top:10px; font-size:14px; line-height:1.4; }
  .task-status { margin-top:10px; padding-top:10px; border-top:1px solid var(--border); font-size:13px; color:var(--muted); }
  .task-status.urgent { color:var(--danger); } .task-status.done { color:var(--success); }
  .task-form { background:var(--surface); border-radius:var(--radius); padding:16px; display:grid; gap:10px; }
  .field { display:grid; gap:6px; font-size:13px; color:var(--muted); }
  .task-form select, .task-form textarea, .dlg input[type=text]:not(.code-input) { background:var(--surface-high); border:2px solid transparent; border-radius:14px; padding:10px 12px; width:100%; color:var(--text); }
  .task-form textarea { resize:vertical; min-height:84px; }
  .task-form select:focus, .task-form textarea:focus, .dlg input:focus { outline:none; border-color:var(--primary); }
  .check { display:flex; align-items:center; gap:8px; font-size:14px; color:var(--text); }
  .check input { accent-color:var(--primary); width:18px; height:18px; }
  .examples { display:flex; flex-wrap:wrap; gap:6px; }
  .examples button { border:0; background:var(--surface-high); color:var(--muted); border-radius:999px; padding:5px 10px; font-size:12.5px; cursor:pointer; text-align:left; }
  .examples button:hover { color:var(--text); }

  /* ---------- events */
  .filters { display:flex; flex-wrap:wrap; gap:8px; margin-bottom:16px; }
  .filters select { background:var(--surface); border:2px solid transparent; border-radius:999px; padding:8px 14px; }
  .filters select:focus { outline:none; border-color:var(--primary); }
  .day { font-weight:700; margin:20px 4px 10px; color:var(--muted); font-size:13px; text-transform:uppercase; letter-spacing:.06em; }
  .events { display:grid; gap:10px; }
  .event { display:flex; gap:14px; background:var(--surface); border-radius:20px; padding:12px; cursor:pointer; align-items:center; border:2px solid transparent; }
  .event:hover { border-color:var(--border); }
  .thumb { width:132px; aspect-ratio:16/10; border-radius:14px; background:#000; overflow:hidden; flex:none; display:grid; place-items:center; color:var(--faint); }
  .thumb img { width:100%; height:100%; object-fit:cover; }
  .event .info { flex:1; min-width:0; }
  .event .summary-text { color:var(--muted); font-size:14px; margin-top:4px; display:-webkit-box; -webkit-line-clamp:2; -webkit-box-orient:vertical; overflow:hidden; }
  .unseen { width:8px; height:8px; border-radius:50%; background:var(--danger); flex:none; }
  .kind { display:inline-flex; align-items:center; gap:6px; font-weight:700; }
  .kind svg { width:18px; height:18px; }
  .empty { background:var(--surface); border-radius:var(--radius); padding:28px 20px; text-align:center; }

  /* ---------- dialogs */
  dialog { border:0; padding:0; background:var(--surface); color:var(--text); border-radius:26px; width:min(560px,calc(100vw - 28px)); box-shadow:0 30px 80px rgba(0,0,0,.6); overflow:hidden; }
  dialog::backdrop { background:rgba(0,0,0,.6); backdrop-filter:blur(4px); }
  dialog.wide { width:min(1100px,calc(100vw - 28px)); }
  .dlg { padding:22px; display:grid; gap:12px; }
  .dlg h3 { margin:0; font-size:22px; }
  .dlg-img { background:#000; display:grid; place-items:center; }
  .dlg-img canvas { max-width:100%; max-height:62vh; }
  .kv { display:grid; grid-template-columns:auto 1fr; gap:6px 16px; font-size:14px; }
  .kv div:nth-child(odd) { color:var(--muted); }
  #toast { position:fixed; left:50%; bottom:24px; transform:translateX(-50%) translateY(140px); background:var(--surface-high); padding:12px 18px; border-radius:16px;
    box-shadow:0 12px 40px rgba(0,0,0,.5); transition:transform .25s; z-index:20; max-width:calc(100vw - 32px); }
  #toast.show { transform:translateX(-50%) translateY(0); }

  @media (max-width:1000px) { .layout { grid-template-columns:1fr; } .side { position:static; } }
  @media (max-width:640px) {
    .bar { padding:10px 14px; gap:8px; } .tabs { margin-left:auto; } .tab { padding:8px 12px; }
    .brand .wordmark, .hub { display:none; } main { padding:16px 14px 50px; }
    .summary { flex-wrap:wrap; padding:16px; } .stats { margin-left:0; width:100%; justify-content:flex-start; }
    .stat { flex:1; min-width:0; } .grid { grid-template-columns:1fr; } .thumb { width:104px; }
  }
</style>
</head>
<body>

<svg width="0" height="0" style="position:absolute" aria-hidden="true">
  <symbol id="i-cam" viewBox="0 0 24 24"><path d="M17 10.5V7c0-.55-.45-1-1-1H4c-.55 0-1 .45-1 1v10c0 .55.45 1 1 1h12c.55 0 1-.45 1-1v-3.5l4 4v-11l-4 4z"/></symbol>
  <symbol id="i-bell" viewBox="0 0 24 24"><path d="M12 22c1.1 0 2-.9 2-2h-4c0 1.1.89 2 2 2zm6-6v-5c0-3.07-1.64-5.64-4.5-6.32V4c0-.83-.67-1.5-1.5-1.5s-1.5.67-1.5 1.5v.68C7.63 5.36 6 7.92 6 11v5l-2 2v1h16v-1l-2-2z"/></symbol>
  <symbol id="i-ai" viewBox="0 0 24 24"><path d="M19 9l1.25-2.75L23 5l-2.75-1.25L19 1l-1.25 2.75L15 5l2.75 1.25L19 9zm-7.5.5L9 4 6.5 9.5 1 12l5.5 2.5L9 20l2.5-5.5L17 12l-5.5-2.5zM19 15l-1.25 2.75L15 19l2.75 1.25L19 23l1.25-2.75L23 19l-2.75-1.25L19 15z"/></symbol>
  <symbol id="i-add" viewBox="0 0 24 24"><path d="M19 13h-6v6h-2v-6H5v-2h6V5h2v6h6v2z"/></symbol>
  <symbol id="i-close" viewBox="0 0 24 24"><path d="M19 6.41L17.59 5 12 10.59 6.41 5 5 6.41 10.59 12 5 17.59 6.41 19 12 13.41 17.59 19 19 17.59 13.41 12z"/></symbol>
  <symbol id="i-more" viewBox="0 0 24 24"><path d="M12 8c1.1 0 2-.9 2-2s-.9-2-2-2-2 .9-2 2 .9 2 2 2zm0 2c-1.1 0-2 .9-2 2s.9 2 2 2 2-.9 2-2-.9-2-2-2zm0 6c-1.1 0-2 .9-2 2s.9 2 2 2 2-.9 2-2-.9-2-2-2z"/></symbol>
  <symbol id="i-check" viewBox="0 0 24 24"><path d="M9 16.17L4.83 12l-1.42 1.41L9 19 21 7l-1.41-1.41z"/></symbol>
  <symbol id="i-logout" viewBox="0 0 24 24"><path d="M17 7l-1.41 1.41L18.17 11H8v2h10.17l-2.58 2.58L17 17l5-5zM4 5h8V3H4c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h8v-2H4V5z"/></symbol>
  <symbol id="i-tune" viewBox="0 0 24 24"><path d="M3 17v2h6v-2H3zM3 5v2h10V5H3zm10 16v-2h8v-2h-8v-2h-2v6h2zM7 9v2H3v2h4v2h2V9H7zm14 4v-2H11v2h10zm-6-4h2V7h4V5h-4V3h-2v6z"/></symbol>
  <symbol id="i-run" viewBox="0 0 24 24"><path d="M13.49 5.48c1.1 0 2-.9 2-2s-.9-2-2-2-2 .9-2 2 .9 2 2 2zm-3.6 13.9l1-4.4 2.1 2v6h2v-7.5l-2.1-2 .6-3c1.3 1.5 3.3 2.5 5.5 2.5v-2c-1.9 0-3.5-1-4.3-2.4l-1-1.6c-.4-.6-1-1-1.7-1-.3 0-.5.1-.8.1l-5.2 2.2v4.7h2v-3.4l1.8-.7-1.6 8.1-4.9-1-.4 2 7 1.4z"/></symbol>
  <symbol id="i-wifi" viewBox="0 0 24 24"><path d="M1 9l2 2c4.97-4.97 13.03-4.97 18 0l2-2C16.93 2.93 7.08 2.93 1 9zm8 8l3 3 3-3c-1.65-1.66-4.34-1.66-6 0zm-4-4l2 2c2.76-2.76 7.24-2.76 10 0l2-2C15.14 9.14 8.87 9.14 5 13z"/></symbol>
  <symbol id="i-wifi-off" viewBox="0 0 24 24"><path d="M22.99 9C19.15 5.16 13.8 3.76 8.84 4.78l2.52 2.52c3.47-.17 6.99 1.05 9.63 3.7l2-2zm-4 4c-1.29-1.29-2.84-2.13-4.49-2.56l3.53 3.53.96-.97zM2 3.05L5.07 6.1C3.6 6.82 2.22 7.78 1 9l1.99 2c1.24-1.24 2.67-2.16 4.2-2.77l2.24 2.24C7.81 10.89 6.27 11.73 5 13v.01L6.99 15c1.36-1.36 3.14-2.04 4.92-2.06L18.98 20l1.27-1.26L3.29 1.79 2 3.05zM9 17l3 3 3-3c-1.65-1.66-4.34-1.66-6 0z"/></symbol>
  <symbol id="i-sync" viewBox="0 0 24 24"><path d="M12 4V1L8 5l4 4V6c3.31 0 6 2.69 6 6 0 1.01-.25 1.97-.7 2.8l1.46 1.46C19.54 15.03 20 13.57 20 12c0-4.42-3.58-8-8-8zm0 14c-3.31 0-6-2.69-6-6 0-1.01.25-1.97.7-2.8L5.24 7.74C4.46 8.97 4 10.430 4 12c0 4.420 3.580 8 8 8v3l4-4-4-4v3z"/></symbol>
  <symbol id="i-edit" viewBox="0 0 24 24"><path d="M3 17.25V21h3.75L17.81 9.94l-3.75-3.75L3 17.25zM20.71 7.04c.39-.39.39-1.02 0-1.41l-2.34-2.34c-.39-.39-1.02-.39-1.41 0l-1.83 1.83 3.75 3.75 1.83-1.830z"/></symbol>
  <symbol id="i-delete" viewBox="0 0 24 24"><path d="M6 19c0 1.1.9 2 2 2h8c1.1 0 2-.9 2-2V7H6v12zM19 4h-3.5l-1-1h-5l-1 1H5v2h14V4z"/></symbol>
  <symbol id="i-pause" viewBox="0 0 24 24"><path d="M6 19h4V5H6v14zm8-14v14h4V5h-4z"/></symbol>
  <symbol id="i-play" viewBox="0 0 24 24"><path d="M8 5v14l11-7z"/></symbol>
  <symbol id="i-stop" viewBox="0 0 24 24"><path d="M6 6h12v12H6z"/></symbol>
  <symbol id="i-replay" viewBox="0 0 24 24"><path d="M12 5V1L7 6l5 5V7c3.31 0 6 2.69 6 6s-2.69 6-6 6-6-2.69-6-6H4c0 4.42 3.58 8 8 8s8-3.58 8-8-3.58-8-8-8z"/></symbol>
  <symbol id="i-eye" viewBox="0 0 24 24"><path d="M12 4.5C7 4.5 2.730 7.610 1 12c1.730 4.390 6 7.5 11 7.5s9.270-3.110 11-7.5c-1.730-4.390-6-7.5-11-7.5zM12 17c-2.760 0-5-2.240-5-5s2.240-5 5-5 5 2.240 5 5-2.240 5-5 5zm0-8c-1.660 0-3 1.340-3 3s1.340 3 3 3 3-1.340 3-3-1.340-3-3-3z"/></symbol>
</svg>

<section id="login" class="hidden">
  <div class="login-card">
    <img class="logo" src="%VYRO_LOGO%" alt="">
    <h1 class="wordmark">VYRO</h1>
    <div class="muted">Enter the dashboard code from your main phone<br>(Settings → Web dashboard code).</div>
    <input id="code" class="code-input" inputmode="numeric" maxlength="6" autocomplete="one-time-code" placeholder="••••••" aria-label="Dashboard code">
    <button id="signin" class="btn primary big">Sign in</button>
    <div id="login-error" class="error"></div>
    <div class="faint">Works while VYRO is open on the main phone, on the same Wi-Fi as this computer.</div>
  </div>
</section>

<section id="app" class="hidden">
  <header><div class="bar">
    <div class="brand"><img src="%VYRO_LOGO%" alt=""><span class="wordmark">VYRO</span></div>
    <nav class="tabs">
      <button class="tab active" data-tab="cameras"><svg class="i sm"><use href="#i-cam"/></svg>Cameras</button>
      <button class="tab" data-tab="events"><svg class="i sm"><use href="#i-bell"/></svg>Events<span id="unseen" class="badge hidden"></span></button>
    </nav>
    <div class="hub"><span id="hub-dot" class="dot"></span><span id="hub-name"></span></div>
    <button id="signout" class="btn ghost icon-btn" title="Sign out" aria-label="Sign out"><svg class="i"><use href="#i-logout"/></svg></button>
  </div></header>
  <main>
    <div id="tab-cameras">
      <div id="summary" class="summary"></div>
      <div class="layout">
        <section>
          <div class="section-title"><svg class="i"><use href="#i-cam"/></svg>Cameras</div>
          <div id="grid" class="grid"></div>
        </section>
        <aside class="side">
          <div class="section-title ai" style="margin:0"><svg class="i"><use href="#i-ai"/></svg>AI tasks</div>
          <div id="task-list" style="display:grid; gap:14px"></div>
          <div id="task-form-slot"></div>
        </aside>
      </div>
    </div>
    <div id="tab-events" class="hidden"></div>
  </main>
</section>

<dialog id="dlg"></dialog>
<div id="toast" role="status"></div>

<script>
"use strict";
const LABELS = { person:"Person", vehicle:"Vehicle", animal:"Animal", package:"Package", motion_other:"Motion", no_activity:"No activity", camera_problem:"Camera problem", task_done:"Task done" };
const STATUS = { live:"Live", connecting:"Connecting video…", online:"Online · not streaming", reconnecting:"Reconnecting…", offline:"Offline" };
const state = { data:null, tab:"cameras", openSettings:new Set(), answers:{}, frameTimers:{}, filters:{ camera:"", type:"", period:"" }, menu:null, online:true };

// ---------------------------------------------------------------- helpers
function el(tag, attrs, ...children) {
  const n = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs || {})) {
    if (v === null || v === undefined || v === false) continue;
    if (k === "class") n.className = v;
    else if (k.startsWith("on")) n.addEventListener(k.slice(2), v);
    else n.setAttribute(k, v === true ? "" : v);
  }
  for (const c of children.flat()) if (c !== null && c !== undefined && c !== false && c !== "") n.append(c.nodeType ? c : document.createTextNode(String(c)));
  return n;
}
function icon(name, cls) {
  const s = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  s.setAttribute("class", "i" + (cls ? " " + cls : ""));
  const u = document.createElementNS("http://www.w3.org/2000/svg", "use");
  u.setAttribute("href", "#i-" + name); s.append(u); return s;
}
async function api(path, opts = {}) {
  const res = await fetch(path, { credentials:"same-origin", headers:{ "Content-Type":"application/json" }, ...opts });
  if (res.status === 401 && path !== "/api/v1/web/login") { showLogin(); throw new Error("signed out"); }
  return res;
}
async function detail(res, fallback) { try { return (await res.json()).detail || fallback; } catch (_) { return fallback; } }
function toast(text) {
  const t = document.getElementById("toast"); t.textContent = text; t.classList.add("show");
  clearTimeout(toast.timer); toast.timer = setTimeout(() => t.classList.remove("show"), 3200);
}
function ago(iso) {
  if (!iso) return "not yet";
  const s = (Date.now() - new Date(iso)) / 1000;
  if (s < 10) return "just now"; if (s < 60) return `${Math.round(s)}s ago`;
  if (s < 3600) return `${Math.round(s / 60)} min ago`; if (s < 86400) return `${Math.round(s / 3600)} h ago`;
  return `${Math.round(s / 86400)} days ago`;
}
function time(iso) { return new Date(iso).toLocaleTimeString([], { hour:"2-digit", minute:"2-digit" }); }
function day(iso) {
  const d = new Date(iso), t = new Date(), y = new Date(Date.now() - 864e5);
  if (d.toDateString() === t.toDateString()) return "Today";
  if (d.toDateString() === y.toDateString()) return "Yesterday";
  return d.toLocaleDateString([], { weekday:"long", day:"numeric", month:"short" });
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
  drawRotated(canvas, await createImageBitmap(await res.blob()), deg || 0);
}
// Icon inside a coloured progress ring, like the app's RingHeader / ProgressRing.
function ring(color, progress, iconName) {
  const r = 17, c = 2 * Math.PI * r, ns = "http://www.w3.org/2000/svg";
  const s = document.createElementNS(ns, "svg"); s.setAttribute("viewBox", "0 0 40 40"); s.setAttribute("class", "ring");
  const mk = (attrs) => { const n = document.createElementNS(ns, "circle"); for (const [k, v] of Object.entries(attrs)) n.setAttribute(k, v); s.append(n); };
  mk({ cx:20, cy:20, r, fill:"none", stroke:color, "stroke-opacity":.22, "stroke-width":3.5 });
  if (progress > 0) mk({ cx:20, cy:20, r, fill:"none", stroke:color, "stroke-width":3.5, "stroke-linecap":"round",
    "stroke-dasharray":`${c * Math.min(1, progress)} ${c}`, transform:"rotate(-90 20 20)" });
  const u = document.createElementNS(ns, "use"); u.setAttribute("href", "#i-" + iconName);
  u.setAttribute("x", 11); u.setAttribute("y", 11); u.setAttribute("width", 18); u.setAttribute("height", 18); u.setAttribute("fill", "#fff");
  s.append(u); return s;
}

// ---------------------------------------------------------------- dialogs
function openDialog(...children) {
  const dlg = document.getElementById("dlg");
  dlg.className = "";
  dlg.replaceChildren(...children);
  if (!dlg.open) dlg.showModal();
  return dlg;
}
function closeDialog() { const d = document.getElementById("dlg"); if (d.open) d.close(); }
document.getElementById("dlg").addEventListener("click", e => { if (e.target.id === "dlg") closeDialog(); });
function confirmBox(title, text, action, danger) {
  return new Promise(resolve => {
    openDialog(el("div", { class:"dlg" }, el("h3", {}, title), el("div", { class:"muted" }, text),
      el("div", { class:"row", style:"justify-content:flex-end; margin-top:8px" },
        el("button", { class:"btn ghost", onclick:() => { closeDialog(); resolve(false); } }, "Cancel"),
        el("button", { class: danger ? "btn danger" : "btn primary", onclick:() => { closeDialog(); resolve(true); } }, action))));
  });
}

// ---------------------------------------------------------------- login
let refreshTimer = null;
function showLogin() {
  document.getElementById("app").classList.add("hidden");
  document.getElementById("login").classList.remove("hidden");
  Object.values(state.frameTimers).forEach(clearTimeout);
  state.frameTimers = {};
  clearInterval(refreshTimer);
  document.getElementById("code").focus();
}
async function signIn() {
  const input = document.getElementById("code"), err = document.getElementById("login-error");
  const code = input.value.trim(); err.textContent = "";
  if (!/^\d{6}$/.test(code)) { err.textContent = "The code has 6 digits."; return; }
  const res = await api("/api/v1/web/login", { method:"POST", body:JSON.stringify({ code }) });
  if (!res.ok) { err.textContent = await detail(res, "Sign-in failed."); input.select(); return; }
  input.value = ""; input.blur(); start();
}
document.getElementById("signin").onclick = signIn;
document.getElementById("code").addEventListener("keydown", e => { if (e.key === "Enter") signIn(); });
document.getElementById("code").addEventListener("input", e => { e.target.value = e.target.value.replace(/\D/g, "").slice(0, 6); if (e.target.value.length === 6) signIn(); });
document.getElementById("signout").onclick = async () => { await api("/api/v1/web/logout", { method:"POST" }); showLogin(); };
document.querySelectorAll(".tab").forEach(t => t.onclick = () => {
  state.tab = t.dataset.tab;
  document.querySelectorAll(".tab").forEach(x => x.classList.toggle("active", x === t));
  document.getElementById("tab-cameras").classList.toggle("hidden", state.tab !== "cameras");
  document.getElementById("tab-events").classList.toggle("hidden", state.tab !== "events");
  if (state.tab === "events" && state.data && state.data.unseen) api("/api/v1/web/events/seen", { method:"POST" }).then(refresh);
});
document.addEventListener("click", e => { if (state.menu && !e.target.closest(".menu")) { state.menu = null; render(); } });

// ---------------------------------------------------------------- data
async function refresh() {
  try {
    const res = await api("/api/v1/web/state");
    if (!res.ok) return;
    state.data = await res.json(); state.online = true;
    render();
  } catch (e) {
    if (e.message !== "signed out") { state.online = false; renderHub(); }
  }
}
async function start() {
  document.getElementById("login").classList.add("hidden");
  document.getElementById("app").classList.remove("hidden");
  await refresh();
  clearInterval(refreshTimer);
  refreshTimer = setInterval(refresh, 3000);
}
function render() {
  if (!state.data) return;
  renderHub();
  const badge = document.getElementById("unseen");
  badge.textContent = state.data.unseen; badge.classList.toggle("hidden", !state.data.unseen);
  renderSummary(state.data); renderCameras(state.data); renderTasks(state.data); renderTaskForm(state.data); renderEvents(state.data);
}
function renderHub() {
  document.getElementById("hub-name").textContent = state.online ? (state.data ? state.data.hub.name : "") : "Main phone not reachable";
  document.getElementById("hub-dot").classList.toggle("off", !state.online);
}

// ---------------------------------------------------------------- summary
function renderSummary(d) {
  const live = d.cameras.filter(c => c.status === "live").length;
  const today = d.events.filter(e => day(e.started_at) === "Today").length;
  const watching = d.tasks.filter(t => t.status === "watching").length;
  const stat = (n, label) => el("div", { class:"stat" }, el("b", {}, n), el("span", {}, label));
  document.getElementById("summary").replaceChildren(
    ring("#8B7CF6", d.cameras.length ? live / d.cameras.length : 0, "cam"),
    el("div", {}, el("h2", {}, d.cameras.length ? "Camera status" : "No cameras yet"),
      el("div", { class:"count" }, d.cameras.length ? [el("b", {}, `${live}/${d.cameras.length}`), " cameras live"] : "Turn a spare phone into a camera")),
    el("div", { class:"stats" }, stat(String(today), "events today"), stat(String(watching), "AI tasks watching"), stat(String(d.unseen), "unseen")));
}

// ---------------------------------------------------------------- cameras
const cards = {};
function renderCameras(d) {
  const grid = document.getElementById("grid");
  const ids = new Set(d.cameras.map(c => c.camera_id));
  for (const id of Object.keys(cards)) if (!ids.has(id)) { cards[id].remove(); delete cards[id]; clearTimeout(state.frameTimers[id]); delete state.frameTimers[id]; }
  for (const cam of d.cameras) {
    if (!cards[cam.camera_id]) cards[cam.camera_id] = el("div", { class:"card" });
    updateCard(cards[cam.camera_id], cam, d.hub.ai_available);
  }
  let add = grid.querySelector(".add-card");
  if (!add) add = el("button", { class:"add-card", onclick:addCameraDialog },
    el("div", { class:"round" }, icon("add")), el("b", {}, "Add camera"),
    el("span", { class:"faint" }, "Type the 6-digit code shown on the camera phone"));
  const wanted = [...d.cameras.map(c => cards[c.camera_id]), add];
  if (wanted.some((n, i) => grid.children[i] !== n) || grid.children.length !== wanted.length) grid.replaceChildren(...wanted);
}
function battery(cam) {
  if (cam.battery == null) return el("span", { class:"battery", title:"Battery unknown until the camera connects" }, "—");
  const cls = cam.charging ? "battery charging" : (cam.battery_low ? "battery low" : "battery");
  return el("span", { class:cls, title: cam.charging ? "Charging" : "Battery" }, `${cam.charging ? "⚡ " : ""}${cam.battery}%`);
}
function tasksOn(cameraId) { return state.data && state.data.tasks.some(t => t.camera_id === cameraId && t.status === "watching"); }
function updateCard(card, cam, aiAvailable) {
  if (!card.canvas) {
    card.canvas = el("canvas", { class:"hidden" });
    card.msg = el("div", { class:"msg" });
    card.overlay = el("div", { class:"overlay" });
    card.body = el("div", { class:"card-body" });
    card.video = el("div", { class:"video", onclick:() => card.live && openLive(card.cameraId) }, card.canvas, card.msg, card.overlay);
    card.append(card.video, card.body);
  }
  const live = cam.status === "live";
  card.live = live; card.cameraId = cam.camera_id;
  card.video.style.cursor = live ? "zoom-in" : "default";
  card.overlay.replaceChildren(
    live ? el("span", { class:"chip live" }, "LIVE") : "",
    cam.status === "reconnecting" ? el("span", { class:"chip reconnecting" }, "Reconnecting") : "",
    cam.status === "offline" ? el("span", { class:"chip offline" }, "Offline") : "",
    cam.motion_active ? el("span", { class:"chip motion" }, "Motion") : "",
    cam.battery_low ? el("span", { class:"chip low" }, "Low battery") : "",
    tasksOn(cam.camera_id) ? el("span", { class:"chip ai" }, "AI watching") : "");
  if (live) {
    card.stalePicture = null; card.canvas.classList.remove("stale");
    if (!card.hasFrame) { card.msg.className = "msg"; card.msg.replaceChildren(el("span", {}, "Loading picture…")); }
    if (!state.frameTimers[cam.camera_id]) pollFrame(card, cam.camera_id);
  } else if (cam.picture_at) {
    card.canvas.classList.add("stale");
    card.msg.className = "msg over"; card.msg.replaceChildren(el("span", {}, `Last picture · ${ago(cam.picture_at)}`));
    if (card.stalePicture !== cam.picture_at) {
      card.stalePicture = cam.picture_at;
      loadInto(card.canvas, `/api/v1/web/cameras/${encodeURIComponent(cam.camera_id)}/picture`, cam.picture_rotation)
        .then(() => card.canvas.classList.remove("hidden")).catch(() => {});
    }
  } else {
    card.canvas.classList.add("hidden"); card.msg.className = "msg";
    card.msg.replaceChildren(icon(cam.status === "online" ? "wifi" : "wifi-off"),
      el("span", {}, cam.status === "online" ? "Tap Start streaming on the camera phone" : (STATUS[cam.status] || "Offline")));
  }

  const statusIcon = { live:"wifi", online:"wifi", connecting:"sync", reconnecting:"sync", offline:"wifi-off" }[cam.status] || "wifi";
  const statusText = live ? `Live · ${cam.bitrate_kbps} kbps`
    : (cam.status === "offline" || cam.status === "reconnecting") ? `${STATUS[cam.status]} · last seen ${ago(cam.last_seen)}` : STATUS[cam.status];
  const s = cam.settings;
  const open = state.openSettings.has(cam.camera_id);
  const answer = state.answers[cam.camera_id];
  const menuOpen = state.menu === cam.camera_id;
  card.body.replaceChildren(
    el("div", { class:"row" }, el("span", { class:"name", title:cam.name }, cam.name), el("span", { class:"spacer" }), battery(cam),
      el("div", { class:"menu" },
        el("button", { class:"btn ghost icon-btn", "aria-label":"More", onclick:e => { e.stopPropagation(); state.menu = menuOpen ? null : cam.camera_id; render(); } }, icon("more")),
        menuOpen ? el("div", { class:"menu-list" },
          el("button", { onclick:() => { state.menu = null; renameDialog(cam); } }, icon("edit", "sm"), "Rename"),
          el("button", { onclick:() => { state.menu = null; open ? state.openSettings.delete(cam.camera_id) : state.openSettings.add(cam.camera_id); render(); } }, icon("tune", "sm"), "Motion, alerts & AI"),
          el("button", { class:"danger", onclick:() => { state.menu = null; removeCamera(cam); } }, icon("delete", "sm"), "Remove camera")) : "")),
    el("div", { class:`status ${cam.status === "connecting" ? "reconnecting" : cam.status}` }, icon(statusIcon, "sm"), statusText),
    el("div", { class:"faint", style:"margin-top:4px" }, [s.motion_enabled ? (cam.motion_active ? "Motion now" : "Motion on") : "Motion off", aiAvailable && s.ai_enabled ? "AI descriptions on" : null].filter(Boolean).join(" · ")),
    el("div", { class:"actions" },
      aiAvailable ? el("button", { class:"btn ai", disabled:cam.status === "offline" || answer === "…", onclick:() => askAi(cam) }, icon("ai", "sm"), answer === "…" ? "Asking AI…" : "Ask AI") : "",
      aiAvailable ? el("button", { class:"btn", onclick:() => watchFor(cam) }, icon("eye", "sm"), "Watch for…") : "",
      live ? el("button", { class:"btn", onclick:() => openLive(cam.camera_id) }, icon("cam", "sm"), "Full screen") : ""),
    answer && answer !== "…" ? aiAnswer(answer) : "",
    open ? settingsPanel(cam, aiAvailable) : "");
}
function pollFrame(card, id) {
  const tick = async () => {
    const cam = state.data && state.data.cameras.find(c => c.camera_id === id);
    if (!cam || cam.status !== "live" || document.getElementById("app").classList.contains("hidden")) { delete state.frameTimers[id]; card.hasFrame = false; return; }
    try {
      await loadInto(card.canvas, `/api/v1/web/cameras/${encodeURIComponent(id)}/frame`, cam.rotation);
      card.hasFrame = true; card.msg.className = "msg"; card.msg.replaceChildren(); card.canvas.classList.remove("hidden", "stale");
    } catch (_) {}
    state.frameTimers[id] = setTimeout(tick, 1000);
  };
  state.frameTimers[id] = setTimeout(tick, 0);
}
function openLive(id) {
  const cam = state.data.cameras.find(c => c.camera_id === id);
  if (!cam) return;
  const canvas = el("canvas");
  const dlg = openDialog(el("div", { class:"dlg-img" }, canvas),
    el("div", { class:"dlg" }, el("div", { class:"row" }, el("h3", {}, cam.name), el("span", { class:"chip live" }, "LIVE"), el("span", { class:"spacer" }),
      el("button", { class:"btn", onclick:closeDialog }, "Close"))));
  dlg.className = "wide";
  const loop = async () => {
    if (!dlg.open || !dlg.contains(canvas)) return;
    try { await loadInto(canvas, `/api/v1/web/cameras/${encodeURIComponent(id)}/frame`, cam.rotation); } catch (_) {}
    setTimeout(loop, 700);
  };
  loop();
}
function aiAnswer(a) {
  if (a.error) return el("div", { class:"ai-answer" }, el("span", { style:"color:var(--danger)" }, a.error));
  return el("div", { class:"ai-answer" }, el("div", {}, a.summary),
    el("div", { class:"actions" }, el("span", { class:"chip ai" }, LABELS[a.category] || a.category),
      a.people_count ? el("span", { class:"chip" }, `${a.people_count} ${a.people_count === 1 ? "person" : "people"}`) : "",
      el("span", { class:"chip" }, `Threat: ${a.threat_level}`)));
}
async function askAi(cam) {
  state.answers[cam.camera_id] = "…"; render();
  const res = await api(`/api/v1/web/cameras/${encodeURIComponent(cam.camera_id)}/ask-ai`, { method:"POST" });
  state.answers[cam.camera_id] = res.ok ? await res.json() : { error: await detail(res, "AI request failed") };
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
    el("input", { type:"checkbox", checked:value, disabled, onchange:async e => {
      if (key === "ai_enabled" && e.target.checked && !(await confirmBox("Turn on AI descriptions?",
        "When this camera detects motion, one snapshot is sent to Groq (an online AI service) to be described. Live video never leaves your Wi-Fi.", "Turn on"))) { e.target.checked = false; return; }
      save({ [key]: e.target.checked });
    } }));
  return el("div", { class:"settings" },
    toggle("Motion detection", "Runs on the camera phone.", "motion_enabled", s.motion_enabled),
    el("div", {}, el("div", { class:"row" }, el("span", {}, "Sensitivity"), el("span", { class:"spacer" }), el("span", { class:"faint" }, s.sensitivity < .34 ? "Low" : s.sensitivity < .67 ? "Medium" : "High")),
      el("input", { type:"range", min:"0", max:"1", step:"0.1", value:String(s.sensitivity), disabled:!s.motion_enabled, onchange:e => save({ sensitivity: Number(e.target.value) }) })),
    toggle("Alerts on the main phone", "At most one per minute.", "notify", s.notify),
    toggle("AI descriptions", aiAvailable ? "Describe motion snapshots." : "Not available on this main phone.", "ai_enabled", aiAvailable && s.ai_enabled, !aiAvailable));
}
function addCameraDialog() {
  const input = el("input", { type:"text", class:"code-input", inputmode:"numeric", maxlength:"6", placeholder:"••••••", autocomplete:"off", "aria-label":"Camera code", style:"margin:4px 0" });
  const msg = el("div", { class:"muted", style:"min-height:22px; text-align:center" });
  const go = el("button", { class:"btn primary big", disabled:true }, "Add camera");
  let busy = false;
  const submit = async () => {
    if (busy || !/^\d{6}$/.test(input.value)) return;
    busy = true; go.disabled = true; input.disabled = true; msg.style.color = ""; msg.textContent = "Looking for the camera… then tap Allow on the camera phone.";
    const res = await api("/api/v1/web/cameras/add", { method:"POST", body:JSON.stringify({ code: input.value }) });
    if (res.ok) { const b = await res.json(); closeDialog(); toast(`${b.name} added. Tap Start streaming on the camera.`); refresh(); return; }
    msg.style.color = "var(--danger)"; msg.textContent = await detail(res, "Could not add the camera.");
    busy = false; input.disabled = false; go.disabled = input.value.length !== 6; input.focus(); input.select();
  };
  input.addEventListener("input", () => { input.value = input.value.replace(/\D/g, "").slice(0, 6); go.disabled = input.value.length !== 6; if (input.value.length === 6) submit(); });
  input.addEventListener("keydown", e => { if (e.key === "Enter") submit(); });
  go.onclick = submit;
  openDialog(el("div", { class:"dlg" },
    el("div", { class:"row" }, el("h3", {}, "Add camera"), el("span", { class:"spacer" }), el("button", { class:"btn ghost icon-btn", "aria-label":"Close", onclick:closeDialog }, icon("close"))),
    el("div", { class:"muted" }, "On the camera phone, open VYRO and choose Camera. Type the 6-digit code it shows — VYRO finds the camera on your Wi-Fi and connects it."),
    input, go, msg));
  input.focus();
}
function renameDialog(cam) {
  const input = el("input", { type:"text", maxlength:"40", value:cam.name, "aria-label":"Camera name" });
  const save = async () => {
    const name = input.value.trim();
    if (!name || name === cam.name) { closeDialog(); return; }
    const res = await api(`/api/v1/web/cameras/${encodeURIComponent(cam.camera_id)}/rename`, { method:"POST", body:JSON.stringify({ name }) });
    if (res.ok) { closeDialog(); toast("Camera renamed"); refresh(); } else toast(await detail(res, "Could not rename."));
  };
  input.addEventListener("keydown", e => { if (e.key === "Enter") save(); });
  openDialog(el("div", { class:"dlg" }, el("h3", {}, "Rename camera"), input,
    el("div", { class:"row", style:"justify-content:flex-end" }, el("button", { class:"btn ghost", onclick:closeDialog }, "Cancel"), el("button", { class:"btn primary", onclick:save }, "Save"))));
  input.focus(); input.select();
}
async function removeCamera(cam) {
  if (!(await confirmBox(`Remove ${cam.name}?`, "It disconnects and must be added again with its code. Its AI tasks stop.", "Remove", true))) return;
  const res = await api(`/api/v1/web/cameras/${encodeURIComponent(cam.camera_id)}`, { method:"DELETE" });
  toast(res.ok ? `${cam.name} removed` : await detail(res, "Could not remove the camera."));
  refresh();
}
function watchFor(cam) {
  const sel = document.getElementById("task-camera"), text = document.getElementById("task-text");
  if (sel) sel.value = cam.camera_id;
  if (text) { text.scrollIntoView({ behavior:"smooth", block:"center" }); text.focus({ preventScroll:true }); }
}

// ---------------------------------------------------------------- AI tasks
function renderTasks(d) {
  const list = document.getElementById("task-list");
  if (!d.hub.ai_available) { list.replaceChildren(el("div", { class:"task faint" }, "AI tasks need the AI service, which is not set up on this main phone.")); return; }
  if (!d.tasks.length) {
    list.replaceChildren(el("div", { class:"task muted" },
      "Give a camera a job in plain words — \"tell me when the washing machine is full\" or \"when the download finishes\" — and the AI watches for it."));
    return;
  }
  const order = { watching:0, done:1, paused:2, stopped:3, expired:4 };
  const tasks = [...d.tasks].sort((a, b) => (b.needs_ack - a.needs_ack) || ((order[a.status] ?? 9) - (order[b.status] ?? 9)));
  list.replaceChildren(...tasks.map(t => {
    const done = t.status === "done", active = t.status === "watching";
    const act = (label, iconName, action, primary) => el("button", { class: primary ? "btn primary" : "btn", onclick: async () => {
      if (action === "delete" && !(await confirmBox("Delete this task?", t.description, "Delete", true))) return;
      await api(`/api/v1/web/tasks/${encodeURIComponent(t.id)}${action === "delete" ? "" : "/" + action}`, { method: action === "delete" ? "DELETE" : "POST" });
      refresh();
    } }, icon(iconName, "sm"), label);
    const pct = done ? 100 : (t.progress ?? 0);
    const color = done ? "#4ADE80" : active ? "#A78BFA" : "#6B7080";
    return el("div", { class:"task" },
      el("div", { class:"row", style:"align-items:flex-start" }, ring(color, done ? 1 : active ? Math.max(pct, 5) / 100 : 0, done ? "check" : "ai"),
        el("div", { style:"flex:1; min-width:0" }, el("div", { class:"title" }, t.description),
          el("div", { class:"faint" }, `${t.camera_name}${t.progress_applicable && t.progress != null ? ` · ~${t.progress}%` : ""}`))),
      t.progress_applicable || done ? el("div", { class: done ? "bar-track done" : "bar-track" }, el("div", { style:`width:${pct}%` })) : "",
      t.observation ? el("div", { class:"obs" }, `“${t.observation}”`) : "",
      el("div", { class: "task-status" + (t.needs_ack || t.has_error ? " urgent" : done ? " done" : "") }, t.status_text),
      el("div", { class:"actions" },
        t.needs_ack ? act("Handled", "check", "ack", true) : "",
        active ? act("Pause", "pause", "pause") : "",
        t.status === "paused" ? act("Resume", "play", "resume", true) : "",
        !active && t.status !== "paused" && !t.needs_ack ? act("Watch again", "replay", "resume") : "",
        active ? act("Stop", "stop", "stop") : act("Delete", "delete", "delete")));
  }));
}
function renderTaskForm(d) {
  const slot = document.getElementById("task-form-slot");
  if (!d.hub.ai_available || !d.cameras.length) { slot.replaceChildren(); return; }
  if (!slot.firstChild) slot.append(taskForm());
  const sel = document.getElementById("task-camera");
  const want = d.cameras.map(c => `${c.camera_id}|${c.name}`).join(",");
  if (sel.dataset.cams !== want) {
    const prev = sel.value;
    sel.replaceChildren(...d.cameras.map(c => el("option", { value:c.camera_id, selected: c.camera_id === prev }, c.name)));
    sel.dataset.cams = want;
  }
}
function taskForm() {
  const sel = el("select", { id:"task-camera" });
  const text = el("textarea", { id:"task-text", maxlength:"300", rows:"3", placeholder:"e.g. Tell me when the water in the washing machine reaches the MAX line" });
  const interval = el("select", { id:"task-interval" }, ...[[15,"15 s"],[30,"30 s"],[60,"1 min"],[300,"5 min"]].map(([v,l]) => el("option", { value:String(v), selected: v === 30 }, l)));
  const remind = el("input", { type:"checkbox", checked:true });
  const keep = el("input", { type:"checkbox" });
  const msg = el("div", { class:"error" });
  const examples = ["Tell me when someone waves at the camera", "Tell me when the progress bar reaches 100%", "Tell me when the kettle stops steaming", "Tell me when the parcel is taken from the doorstep"];
  const startBtn = el("button", { class:"btn primary big", onclick: async () => {
    msg.textContent = "";
    const res = await api("/api/v1/web/tasks", { method:"POST", body: JSON.stringify({ camera_id: sel.value, description: text.value,
      interval_seconds: Number(interval.value), remind_until_ack: remind.checked, keep_watching: keep.checked }) });
    if (!res.ok) { msg.textContent = await detail(res, "Could not start the task."); return; }
    text.value = ""; toast("AI is now watching"); refresh();
  } }, icon("ai", "sm"), "Start watching");
  return el("div", { class:"task-form" },
    el("b", {}, "New AI task"),
    el("label", { class:"field" }, "Camera", sel),
    el("label", { class:"field" }, "What should the AI watch for?", text),
    el("div", { class:"examples" }, examples.map(x => el("button", { onclick:() => { text.value = x; text.focus(); } }, x))),
    el("label", { class:"field" }, "Check every", interval),
    el("label", { class:"check" }, remind, "Remind me until handled"),
    el("label", { class:"check" }, keep, "Keep watching after it happens"),
    startBtn, msg,
    el("div", { class:"faint" }, "Pictures from this camera go to Groq (an online AI service) while the task runs. AI can be wrong — don't rely on it for safety."));
}

// ---------------------------------------------------------------- events
function eventKind(e) {
  if (e.type === "task_done") return ["Task done", "check", "var(--success)"];
  if (e.ai_category) return [LABELS[e.ai_category] || "Motion", e.ai_category === "person" ? "run" : "ai", "var(--ai)"];
  if (e.type === "ai_check") return ["AI check", "ai", "var(--ai)"];
  return ["Motion", "run", "var(--warning)"];
}
function renderEvents(d) {
  const root = document.getElementById("tab-events");
  // Redraw only when something changed, so an open filter menu stays open.
  const sig = JSON.stringify([d.unseen, state.filters, d.events.map(e => [e.id, e.seen, e.ended_at, e.ai_summary])]);
  if (root.sig === sig) return;
  root.sig = sig;
  const f = state.filters;
  const since = f.period === "today" ? new Date(new Date().toDateString()).getTime() : f.period === "week" ? Date.now() - 7 * 864e5 : 0;
  const shown = d.events.filter(e => (!f.camera || e.camera_id === f.camera)
    && (!f.type || (f.type === "ai" ? !!e.ai_summary : e.type === f.type))
    && new Date(e.started_at).getTime() >= since);
  const cams = new Map(d.events.map(e => [e.camera_id, e.camera_name]));
  const pick = (key, options) => el("select", { "aria-label":key, onchange:e => { f[key] = e.target.value; renderEvents(state.data); } },
    ...options.map(([v, l]) => el("option", { value:v, selected: f[key] === v }, l)));
  const out = [el("div", { class:"summary" }, ring("#F25C70", d.events.length ? (d.events.length - d.unseen) / d.events.length : 0, "bell"),
      el("div", {}, el("h2", {}, d.events.length ? "Activity" : "All quiet"), el("div", { class:"count" }, d.events.length ? `${d.events.length} events · ${d.unseen} new` : "Motion, AI checks and finished tasks appear here"))),
    el("div", { class:"filters" },
      pick("camera", [["", "All cameras"], ...[...cams]]),
      pick("type", [["", "All events"], ["motion", "Motion"], ["ai", "With AI description"], ["ai_check", "AI checks"], ["task_done", "Tasks done"]]),
      pick("period", [["", "Any time"], ["today", "Today"], ["week", "Last 7 days"]]))];
  if (d.events.length && !shown.length) out.push(el("div", { class:"empty muted" }, "No events match these filters."));
  let last = null; const list = el("div", { class:"events" });
  for (const e of shown) {
    const dd = day(e.started_at);
    if (dd !== last) { list.append(el("div", { class:"day" }, dd)); last = dd; }
    const [label, ic, color] = eventKind(e);
    const rot = e.rotation ? `transform:rotate(${e.rotation}deg)` : null;
    list.append(el("div", { class:"event", onclick:() => openEvent(e) },
      el("div", { class:"thumb" }, e.has_snapshot ? el("img", { src:`/api/v1/web/events/${encodeURIComponent(e.id)}/snapshot`, alt:"", loading:"lazy", style:rot }) : icon("cam")),
      el("div", { class:"info" },
        el("div", { class:"row" }, e.seen ? "" : el("span", { class:"unseen" }),
          el("span", { class:"kind", style:`color:${color}` }, icon(ic), label), el("span", { class:"spacer" }), el("span", { class:"faint" }, time(e.started_at))),
        el("div", { class:"faint", style:"margin-top:2px" }, e.camera_name),
        e.ai_summary ? el("div", { class:"summary-text" }, e.ai_summary) : "")));
  }
  out.push(list);
  root.replaceChildren(...out);
}
function openEvent(e) {
  const canvas = el("canvas");
  const [label] = eventKind(e);
  const dur = e.type !== "motion" ? "Snapshot" : e.ended_at ? `${Math.round((new Date(e.ended_at) - new Date(e.started_at)) / 1000)} s` : "Ongoing";
  openDialog(e.has_snapshot ? el("div", { class:"dlg-img" }, canvas) : "",
    el("div", { class:"dlg" },
      el("div", { class:"row" }, el("h3", {}, label), el("span", { class:"spacer" }), el("button", { class:"btn", onclick:closeDialog }, "Close")),
      e.ai_summary ? aiAnswer({ summary:e.ai_summary, category:e.ai_category, threat_level:e.ai_threat_level || "none", people_count:0 })
        : (e.ai_error ? el("div", { class:"faint" }, `No AI description: ${e.ai_error}`) : ""),
      el("div", { class:"kv" }, el("div", {}, "Camera"), el("div", {}, e.camera_name), el("div", {}, "When"), el("div", {}, `${day(e.started_at)} at ${time(e.started_at)}`),
        el("div", {}, "Duration"), el("div", {}, dur))));
  if (e.has_snapshot) loadInto(canvas, `/api/v1/web/events/${encodeURIComponent(e.id)}/snapshot`, e.rotation).catch(() => {});
}

// ---------------------------------------------------------------- boot
// The VYRO web apps open this page as http://<phone>:8000/#code=123456 after
// finding the phone by its code: sign in with it, then drop it from the URL.
const linkCode = (location.hash.match(/(?:^#|&)code=(\d{6})(?:&|$)/) || [])[1];
if (linkCode) history.replaceState(null, "", location.pathname + location.search);
fetch("/api/v1/web/state", { credentials:"same-origin" }).then(r => {
  if (r.ok) return start();
  showLogin();
  if (linkCode) { document.getElementById("code").value = linkCode; signIn(); }
}).catch(showLogin);
</script>
</body>
</html>
''';
