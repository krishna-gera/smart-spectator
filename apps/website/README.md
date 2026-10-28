# VYRO website

Static marketing site for VYRO (no build step). It uses the same colours,
icons and logo as the app and the web dashboard.

The web dashboard itself is not here: each main phone serves it at
`http://<main-phone-address>:8000` (see `apps/camera/lib/hub/web_dashboard.dart`).
The "Open my dashboard" box on this site just links there.

## Preview locally

```bash
python3 -m http.server 5173 --directory apps/website
```

Then open http://localhost:5173.

## Deploy (Cloudflare Pages)

```bash
cd services/ai_proxy && npx wrangler pages deploy ../../apps/website --project-name vyro
```

`_headers` sets the security headers on Cloudflare Pages.
