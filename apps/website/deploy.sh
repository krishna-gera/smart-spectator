#!/usr/bin/env bash
# Deploys the VYRO website to Vercel production and points smart-vyro.vercel.app
# at it. Needs `vercel login` once. Download APKs are copied in from the latest
# app build (they are not committed).
set -euo pipefail
cd "$(dirname "$0")"
apk=../camera/build/app/outputs/flutter-apk
mkdir -p downloads
if [[ -f $apk/app-arm64-v8a-release.apk ]]; then
  cp "$apk/app-arm64-v8a-release.apk" downloads/vyro-android.apk
  cp "$apk/app-armeabi-v7a-release.apk" downloads/vyro-android-32bit.apk
fi
[[ -f downloads/vyro-android.apk ]] || { echo "Build the APK first: flutter build apk --release --split-per-abi"; exit 1; }
node ../../scripts/check_website.mjs .
url=$(vercel deploy --prod --yes | grep -oE 'https://[a-z0-9-]+\.vercel\.app' | tail -1)
vercel alias set "$url" smart-vyro.vercel.app
echo "Live: https://smart-vyro.vercel.app ($url)"
