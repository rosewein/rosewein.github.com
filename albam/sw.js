// 알밤케어 오프라인 캐시(서비스 워커).
// 파일을 더하거나 이름을 바꾸면 FILES 에 반영하고 VERSION 을 올린다.
// (tests/unit/service-worker.test.mjs 가 src·styles 의 파일이 모두 들어 있는지 확인한다.)
// Supabase 요청(다른 출처)은 건드리지 않는다. 기록 다시 보내기는 src/api/queue.js 가 맡는다.

const VERSION = 'albam-v20';
const FILES = [
  './',
  './index.html',
  './config.js',
  './manifest.webmanifest',
  './icon-180.png',
  './icon-192.png',
  './icon-512.png',
  './styles/app.css',
  './fonts/Galmuri11.woff2',
  './fonts/Galmuri9.woff2',
  './sprites/albam.png',
  './sprites/icons.png',
  './src/main.js',
  './src/config.js',
  './src/domain.js',
  './src/time.js',
  './src/formula.js',
  './src/voice-parse.js',
  './src/api/index.js',
  './src/api/supabase-rest.js',
  './src/api/queue.js',
  './src/api/pending.js',
  './src/api/errors.js',
  './src/api/demo.js',
  './src/ui/dom.js',
  './src/ui/sound.js',
  './src/ui/stage.js',
  './src/ui/sheets.js',
  './src/ui/status.js',
  './src/ui/night.js',
  './src/ui/recorder.js',
  './src/ui/amount.js',
  './src/ui/quick-record.js',
  './src/ui/feed-amounts.js',
  './src/ui/late-entry.js',
  './src/ui/voice-input.js',
  './src/ui/login.js',
  './src/ui/stats.js',
  './src/ui/pages.js',
  './src/ui/wheel.js',
];

self.addEventListener('install', (e) => {
  e.waitUntil(caches.open(VERSION).then((c) => c.addAll(FILES)).then(() => self.skipWaiting()));
});

self.addEventListener('activate', (e) => {
  e.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(keys.filter((k) => k.startsWith('albam-') && k !== VERSION).map((k) => caches.delete(k))))
      .then(() => self.clients.claim()),
  );
});

// 먼저 네트워크(고친 파일이 바로 보이게), 안 되면 캐시.
// cache: 'no-cache' 로 브라우저 HTTP 캐시(GitHub Pages 는 10분)도 매번 서버에 확인한다(바뀌지 않았으면 304 라 가볍다).
// 이게 없으면 배포 직후 새 index.html 에 옛 app.css 가 섞일 수 있다.
self.addEventListener('fetch', (e) => {
  if (e.request.method !== 'GET' || new URL(e.request.url).origin !== location.origin) return;
  e.respondWith(
    fetch(e.request, { cache: 'no-cache' })
      .then((res) => {
        if (res.ok) {
          const copy = res.clone();
          caches.open(VERSION).then((c) => c.put(e.request, copy));
        }
        return res;
      })
      .catch(() => caches.match(e.request, { ignoreSearch: true }).then((r) => r || caches.match('./index.html'))),
  );
});
