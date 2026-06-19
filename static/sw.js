// Emporium Armani Studio — Service Worker
const CACHE_NAME = 'ea-studio-v2';

self.addEventListener('install', (e) => { self.skipWaiting(); });
self.addEventListener('activate', (e) => {
  // Clear old caches
  e.waitUntil(
    caches.keys().then(keys =>
      Promise.all(keys.filter(k => k !== CACHE_NAME).map(k => caches.delete(k)))
    ).then(() => clients.claim())
  );
});

self.addEventListener('fetch', (e) => {
  // Only handle GET requests
  if (e.request.method !== 'GET') return;

  // Skip navigation requests (page loads, form redirects)
  if (e.request.mode === 'navigate') return;

  // Skip external domains (Cloudflare analytics, CDNs, etc.)
  const url = new URL(e.request.url);
  if (url.origin !== location.origin) return;

  // Only cache static assets
  if (!e.request.url.includes('/static/')) return;

  e.respondWith(
    caches.match(e.request).then(cached => {
      if (cached) return cached;
      return fetch(e.request).then(response => {
        if (response.ok) {
          const clone = response.clone();
          caches.open(CACHE_NAME).then(cache => cache.put(e.request, clone));
        }
        return response;
      });
    })
  );
});