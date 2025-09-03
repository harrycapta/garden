const CACHE_NAME = 'garden-cache-v3';
const ASSETS = [
  '/',
  '/index.html',
  '/manifest.json',
  '/css/style.css',
  '/js/theme.js',
  '/js/seer.js',
  '/js/imagesloaded.js',
  '/js/masonry.js',
  '/js/settings.js',
  '/js/util.js',
  '/js/grid.js',
  '/js/nav.js',
  '/js/wrap.js',
  '/js/add.js',
  '/js/main.js',
  '/js/lightbox.js'
];

self.addEventListener('install', event => {
  event.waitUntil(
    caches.open(CACHE_NAME).then(cache => cache.addAll(ASSETS))
  );
});

self.addEventListener('activate', event => {
  event.waitUntil(
    caches.keys().then(keys =>
      Promise.all(keys.filter(key => key !== CACHE_NAME).map(key => caches.delete(key)))
    )
  );
});

self.addEventListener('fetch', event => {
  event.respondWith(
    caches.match(event.request).then(response => response || fetch(event.request))
  );
});
