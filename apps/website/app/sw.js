// Keeps the VYRO web app shells available offline (they only need to open
// the main phone's dashboard on the home Wi-Fi).
const CACHE = "vyro-app-v2";
const SHELL = [
  "/app/app-mobile/", "/app/app-desktop/", "/app/connect.js", "/app/app.css",
  "/assets/vyro-mark.png", "/assets/apple-touch-icon.png", "/assets/icon-192.png", "/assets/icon-512.png",
];

self.addEventListener("install", e => {
  e.waitUntil(caches.open(CACHE).then(c => c.addAll(SHELL)).then(() => self.skipWaiting()));
});

self.addEventListener("activate", e => {
  e.waitUntil(caches.keys().then(keys => Promise.all(keys.filter(k => k !== CACHE).map(k => caches.delete(k))))
    .then(() => self.clients.claim()));
});

// Network first (fresh pages when online), cache when offline.
self.addEventListener("fetch", e => {
  const url = new URL(e.request.url);
  if (e.request.method !== "GET" || url.origin !== self.location.origin) return;
  e.respondWith(
    fetch(e.request)
      .then(res => {
        if (res.ok) {
          const copy = res.clone(); // before the page reads the body
          caches.open(CACHE).then(c => c.put(e.request, copy));
        }
        return res;
      })
      .catch(() => caches.match(e.request, { ignoreSearch: true }))
  );
});
