# VYRO app (Flutter)

One app with two modes:

- **Camera** — streams H.264 video to main phones over Wi-Fi, detects motion,
  shows a permanent 6-digit code (`lib/features/camera`, `lib/camera`).
- **Main phone** — adds cameras by their code, live video, events, AI watch
  tasks, and serves the web dashboard on port 8000 (`lib/features/viewer`, `lib/hub`).

| Folder | What |
|---|---|
| `lib/core` | AI client, video codec bridge, control channel, discovery, pairing, protocol, storage |
| `lib/hub` | Main-phone hub server, device registry, events, AI tasks, web dashboard and API |
| `lib/features` | Screens: onboarding, role, camera, pairing, viewer, settings |
| `ios/Runner`, `android/.../kotlin` | Native video encode/decode, Bonjour/NSD, notifications |

## Run

```bash
flutter test
flutter run --dart-define=AI_PROXY_URL=https://<worker>.workers.dev --dart-define=AI_PROXY_TOKEN=<token>
flutter build apk --release --split-per-abi --dart-define=AI_PROXY_URL=... --dart-define=AI_PROXY_TOKEN=...
```

Without the two `--dart-define`s the app works with AI features switched off.
