// Emporium Armani Studio — Service Worker
const CACHE_NAME = 'ea-studio-v1';

// Install — skip waiting so it activates immediately
self.addEventListener('install', (e) => {
  self.skipWaiting();
});

// Activate — take control of all clients
self.addEventListener('activate', (e) => {
  e.waitUntil(clients.claim());
});

// Fetch — network first, fallback to cache for offline
self.addEventListener('fetch', (e) => {
  // Only handle GET requests
  if (e.request.method !== 'GET') return;

  e.respondWith(
    fetch(e.request)
      .then((response) => {
        // Cache successful responses for static assets
        if (response.ok && e.request.url.includes('/static/')) {
          const clone = response.clone();
          caches.open(CACHE_NAME).then(cache => cache.put(e.request, clone));
        }
        return response;
      })
      .catch(() => {
        // Offline fallback — try cache
        return caches.match(e.request);
      })
  );
});
