const CACHE_NAME = 'scanner-cache-v2';
const OFFLINE_URL = 'offline.html';

// Use relative paths so this worker works under /scanner/ when installed there.
const ASSETS_TO_CACHE = [
  './',
  OFFLINE_URL,
  'manifest.json',
  'static/icons/icon-192.png',
  'static/icons/icon-512.png',
];

// Resilient precache: try to fetch each asset and only cache the ones that succeed.
self.addEventListener('install', (event) => {
  event.waitUntil((async () => {
    const cache = await caches.open(CACHE_NAME);
    const base = new URL('./', self.location);
    await Promise.all(
      ASSETS_TO_CACHE.map(async (asset) => {
        try {
          const url = new URL(asset, base).href;
          const res = await fetch(url, { cache: 'no-cache' });
          if (res && res.ok) {
            await cache.put(url, res.clone());
          } else {
            // skip non-OK responses
            console.warn('SW: asset not cached (non-OK):', url, res && res.status);
          }
        } catch (err) {
          // ignore individual failures
          console.warn('SW: failed to fetch asset', asset, err);
        }
      })
    );
  })());
  self.skipWaiting();
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keys) => {
      return Promise.all(
        keys.filter((key) => key !== CACHE_NAME).map((key) => caches.delete(key))
      );
    })
  );
  self.clients.claim();
});


// Listen for messages from the page (e.g., SKIP_WAITING)
self.addEventListener('message', (event) => {
  if (!event.data) return;
  if (event.data.type === 'SKIP_WAITING') {
    self.skipWaiting();
  }
});

self.addEventListener('fetch', (event) => {
  if (event.request.method !== 'GET') return;

  // Navigation requests: serve cached offline page when network fails
  if (event.request.mode === 'navigate') {
    event.respondWith(
      fetch(event.request)
        .then((response) => response)
        .catch(() => caches.match(OFFLINE_URL))
    );
    return;
  }

  event.respondWith(
    fetch(event.request)
      .then((response) => {
        const resClone = response.clone();
        caches.open(CACHE_NAME).then((cache) => cache.put(event.request, resClone));
        return response;
      })
      .catch(() => caches.match(event.request))
  );
});


// Handle push events (display notifications)
self.addEventListener('push', function(event) {
  let payload = {};
  try {
    if (event.data) payload = event.data.json();
  } catch (e) {
    try { payload = { message: event.data.text() }; } catch (e2) { payload = { message: 'New notification' }; }
  }

  const title = (payload && payload.title) || 'Scanner';
  const options = {
    body: (payload && payload.message) || '',
    icon: 'static/icons/icon-192.png',
    badge: 'static/icons/icon-192.png',
    data: payload.data || {}
  };

  event.waitUntil(self.registration.showNotification(title, options));
});


// Handle notification click
self.addEventListener('notificationclick', function(event) {
  event.notification.close();
  const urlToOpen = new URL('/scanner/', self.location.origin).href;
  event.waitUntil(
    clients.matchAll({ type: 'window', includeUncontrolled: true }).then( windowClients => {
      for (let i = 0; i < windowClients.length; i++) {
        const client = windowClients[i];
        if (client.url === urlToOpen && 'focus' in client) return client.focus();
      }
      if (clients.openWindow) return clients.openWindow(urlToOpen);
    })
  );
});
