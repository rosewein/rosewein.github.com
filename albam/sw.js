// 알밤케어 오프라인 캐시. 파일을 바꾸면 VERSION 을 올린다.
// Supabase 요청(다른 출처)은 건드리지 않는다. 기록 재전송은 app 쪽 IndexedDB 큐가 맡는다.
const VERSION = 'albam-v1';
const FILES = [
  './', './index.html', './app.js', './api.js', './demo-api.js', './voice-parse.js', './config.js',
  './manifest.webmanifest', './icon-180.png', './icon-192.png', './icon-512.png',
  './sprites/albam.png', './sprites/icons.png', './fonts/Galmuri11.woff2', './fonts/Galmuri9.woff2',
];

self.addEventListener('install', (e) => {
  e.waitUntil(caches.open(VERSION).then((c) => c.addAll(FILES)).then(() => self.skipWaiting()));
});

self.addEventListener('activate', (e) => {
  e.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(keys.filter((k) => k.startsWith('albam-') && k !== VERSION).map((k) => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

// 먼저 네트워크(바로 갱신), 안 되면 캐시
self.addEventListener('fetch', (e) => {
  if (e.request.method !== 'GET' || new URL(e.request.url).origin !== location.origin) return;
  e.respondWith(
    fetch(e.request)
      .then((res) => {
        if (res.ok) {
          const copy = res.clone();
          caches.open(VERSION).then((c) => c.put(e.request, copy));
        }
        return res;
      })
      .catch(() => caches.match(e.request, { ignoreSearch: true }).then((r) => r || caches.match('./index.html')))
  );
});
