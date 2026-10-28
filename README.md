<p align="center"><img src="apps/website/assets/vyro-mark.png" width="96" alt="VYRO logo"></p>

<h1 align="center">VYRO</h1>

<p align="center"><b>Spare phones become smart cameras.</b><br>
Live video stays on your Wi-Fi, and AI watches for exactly what you ask.</p>

---

## What it is

VYRO is one app with two jobs:

- **Camera** — a spare phone streams live video, detects motion, and shows a
  permanent 6-digit code.
- **Main phone** — type a camera's code to add it; then watch live video, get
  alerts, and give cameras **AI watch tasks** in plain words
  ("tell me when the washing machine reaches MAX").

The main phone also serves a **web dashboard** at `http://<main-phone>:8000`
for any computer on the same Wi-Fi. There is no PC hub and no VYRO account.

```
Camera phone(s) ──H.264 over Wi-Fi──▶ Main phone (hub + web dashboard)
                                          │  one reduced picture, only for AI
                                          ▼  tasks / descriptions you turn on
                              VYRO AI service (Cloudflare Worker) ──▶ Groq
```

## Repository

| Path | What |
|---|---|
| `apps/camera` | The VYRO app (Flutter; iOS + Android). Camera mode, main-phone hub, web dashboard (`lib/hub/web_dashboard.dart`). |
| `services/ai_proxy` | VYRO AI service (Cloudflare Worker) — holds the AI key; plan/check watch tasks, describe snapshots. |
| `apps/website` | Website, downloads and the mobile/desktop web apps — **https://smart-vyro.vercel.app** (Vercel). |
| `scripts/check_website.mjs` | Website link/asset check (CI and `deploy.sh`). |

The earlier PC-hub design (Python backend, Snapdragon models, docs) was retired; it is preserved in git at the tag `legacy-pc-hub`.

## Develop

```bash
# App
cd apps/camera && flutter test
flutter build ios --simulator --debug \
  --dart-define=AI_PROXY_URL=https://<your-worker>.workers.dev \
  --dart-define=AI_PROXY_TOKEN=<proxy token>

# AI service (copy services/ai_proxy/.dev.vars.example to .dev.vars; never committed)
cd services/ai_proxy && npm test
npm run dev            # local, port 8787
npm run deploy         # Cloudflare

# Website (deploys to smart-vyro.vercel.app)
apps/website/deploy.sh
```

## Privacy

- Live video goes straight from camera phones to the main phone over your Wi-Fi.
- Events and snapshots are stored on the main phone.
- Single, reduced pictures go to the AI service only for AI tasks or AI
  descriptions you turn on; cameras show an "AI watching" badge.
- Cameras join with their own code; the web dashboard needs a separate code;
  repeated wrong codes are locked out.
