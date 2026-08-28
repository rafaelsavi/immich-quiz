/**
 * Service Worker for Immich Quiz PWA
 * Caches UI shell and static assets for instant load and offline resiliency.
 * API calls and dynamic Immich media streams bypass cache.
 */

const CACHE_NAME = 'immich-quiz-v2';

const PRECACHE_ASSETS = [
  '/',
  '/manifest.webmanifest',
  '/static/favicon.svg',
  '/static/favicons/favicon.ico',
  '/static/favicons/favicon-16x16.png',
  '/static/favicons/favicon-32x32.png',
  '/static/favicons/apple-touch-icon.png',
  '/static/favicons/android-chrome-192x192.png',
  '/static/favicons/android-chrome-512x512.png',
  '/static/favicons/manifest.json',
  '/static/css/style.css',
  '/static/js/app.js',
  '/static/js/modules/router.js',
  '/static/js/modules/state.js'
];

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches
      .open(CACHE_NAME)
      .then((cache) => {
        return cache.addAll(PRECACHE_ASSETS).catch((err) => {
          console.warn('[SW] Pre-cache partial failure:', err);
        });
      })
      .then(() => self.skipWaiting())
  );
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((cacheNames) => {
        return Promise.all(
          cacheNames.map((cache) => {
            if (cache !== CACHE_NAME) {
              return caches.delete(cache);
            }
          })
        );
      })
      .then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', (event) => {
  const url = new URL(event.request.url);

  // Only handle GET requests
  if (event.request.method !== 'GET') {
    return;
  }

  // Bypass cache for API calls and Immich media proxy
  if (url.pathname.startsWith('/api/')) {
    return;
  }

  // Navigation requests: fetch from network, fallback to cached App Shell on failure/offline
  if (event.request.mode === 'navigate') {
    event.respondWith(
      fetch(event.request).catch(() => caches.match('/'))
    );
    return;
  }

  // Stale-While-Revalidate strategy for static UI assets
  event.respondWith(
    caches.match(event.request).then((cachedResponse) => {
      const fetchPromise = fetch(event.request)
        .then((networkResponse) => {
          if (
            networkResponse &&
            networkResponse.status === 200 &&
            networkResponse.type === 'basic'
          ) {
            const responseToCache = networkResponse.clone();
            caches.open(CACHE_NAME).then((cache) => {
              cache.put(event.request, responseToCache);
            });
          }
          return networkResponse;
        })
        .catch(() => cachedResponse);

      return cachedResponse || fetchPromise;
    })
  );
});
