/* Freemium service worker — installability + an offline fallback page.
 * Deliberately minimal and honest: it does NOT cache portfolio data (which must
 * always be fresh from the server), only an offline page shown when a page
 * navigation fails with no network. */
const CACHE = "freemium-offline-v1";
const OFFLINE_URL = "/offline/";

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE).then((cache) => cache.add(OFFLINE_URL)).then(() => self.skipWaiting())
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((keys) => Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", (event) => {
  const request = event.request;
  // Only handle top-level page navigations; everything else hits the network as
  // usual so data is never served stale from the cache.
  if (request.method !== "GET" || request.mode !== "navigate") {
    return;
  }
  event.respondWith(fetch(request).catch(() => caches.match(OFFLINE_URL)));
});
