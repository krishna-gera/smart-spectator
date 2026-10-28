# VYRO website — smart-vyro.vercel.app

Static site (no build step) in the same theme as the app and dashboard.

| Path | What |
|---|---|
| `/` | Website: features, AI tasks, privacy, FAQ, **Download** (Android APK, iPhone, both web apps) |
| `/app/` | Sends phones to the mobile web app, computers to the desktop one |
| `/app/app-mobile/` | Mobile web app (installable; home-screen icon) |
| `/app/app-desktop/` | Desktop web app (installable in Chrome / Edge) |
| `/downloads/vyro-android.apk` | Android APK (64-bit ARM); `vyro-android-32bit.apk` for older phones |

The live dashboard runs on the main phone (`http://<main-phone>:8000`) and stays
on the home Wi-Fi. Browsers do not let an internet page read a phone on the
local network, so the web apps remember your main phones and open the phone's
own dashboard in the same window.

## Preview

```bash
python3 -m http.server 5173 --directory apps/website
```

## Deploy (Vercel)

```bash
cd apps/camera && flutter build apk --release --split-per-abi \
  --dart-define=AI_PROXY_URL=... --dart-define=AI_PROXY_TOKEN=...
apps/website/deploy.sh
```

`deploy.sh` copies the APKs in (they are not committed), checks every page,
deploys to production and points `smart-vyro.vercel.app` at it.
`vercel.json` sets security headers, the APK download type and short redirects.

Note: the public APK includes the AI service token, so AI works for everyone
who installs it. Rotate `PROXY_TOKEN` (Cloudflare secret) and rebuild if it is abused.
