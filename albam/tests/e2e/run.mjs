// 브라우저 시험. 갤럭시 S10 가로 크기(760x360, 화소 비율 3)로 실제 화면을 눌러 본다.
//
//   node tests/e2e/run.mjs            (playwright 와 크로미움이 있어야 함: npm i -g playwright && npx playwright install chromium)
//   SCREENSHOTS=/tmp/shots node tests/e2e/run.mjs   화면 사진도 남기기
//
// 1) 미리 보기(?demo): 수유·중복 확인·취소·지난 기록·밤 화면
// 2) 가짜 Supabase: 로그인, 오프라인 저장, 다시 연결되면 보내기, 토큰 갱신

import http from 'node:http';
import { readFile } from 'node:fs/promises';
import { extname, join, normalize } from 'node:path';
import { fileURLToPath } from 'node:url';
import { createRequire } from 'node:module';
import { createFakeSupabase } from './fake-supabase.mjs';

const require = createRequire(import.meta.url);
const { chromium } = require('playwright');

const ROOT = fileURLToPath(new URL('../../', import.meta.url));
const SHOTS = process.env.SCREENSHOTS;
const DEVICE = { viewport: { width: 760, height: 360 }, deviceScaleFactor: 3, hasTouch: true, isMobile: true, timezoneId: 'Asia/Seoul' };
const DAYTIME = new Date('2026-11-06T14:00:00+09:00');
const NIGHT = new Date('2026-11-06T23:30:00+09:00');

// ── 아주 작은 정적 서버 (albam 폴더를 /albam/ 으로) ──
const TYPES = { '.html': 'text/html', '.js': 'text/javascript', '.mjs': 'text/javascript', '.css': 'text/css', '.png': 'image/png', '.woff2': 'font/woff2', '.webmanifest': 'application/manifest+json' };
function serve() {
  const server = http.createServer(async (req, res) => {
    const path = decodeURIComponent(new URL(req.url, 'http://x').pathname).replace(/^\/albam\//, '/');
    const file = normalize(join(ROOT, path.endsWith('/') ? `${path}index.html` : path));
    if (!file.startsWith(ROOT)) { res.writeHead(403).end(); return; }
    try {
      const body = await readFile(file);
      res.writeHead(200, { 'Content-Type': TYPES[extname(file)] || 'application/octet-stream' }).end(body);
    } catch { res.writeHead(404).end(); }
  });
  return new Promise((resolve) => server.listen(0, () => resolve(server)));
}

// ── 결과 모으기 ──
let failures = 0;
function check(ok, label) {
  console.log(`${ok ? 'ok  ' : 'FAIL'} ${label}`);
  if (!ok) failures += 1;
}
const shot = (page, name) => (SHOTS ? page.screenshot({ path: join(SHOTS, `${name}.png`) }) : null);
const text = (page, sel) => page.textContent(sel);

async function demoFlow(browser, base) {
  const page = await (await browser.newContext(DEVICE)).newPage();
  const errors = [];
  page.on('pageerror', (e) => errors.push(String(e)));
  await page.clock.setFixedTime(DAYTIME);
  await page.goto(`${base}?demo`);
  await page.evaluate(() => localStorage.clear());
  await page.reload();
  await page.waitForTimeout(500);
  await shot(page, 'main');

  check((await page.evaluate(() => document.querySelector('#stage').style.zoom)) === '2', 'S10 에서 6배(기기 화소) = CSS zoom 2');
  check(await text(page, '#elapsed') === '2:35', '경과 시간 표시');
  const sizes = await page.$$eval('#actions .action', (bs) => bs.map((b) => {
    const r = b.getBoundingClientRect();
    const i = b.querySelector('.ico').getBoundingClientRect();
    return [r.width, r.height, r.top, i.width, i.height, getComputedStyle(b).fontSize].join('/');
  }));
  check(sizes.length === 3 && new Set(sizes).size === 1, `큰 버튼 셋 크기·아이콘·글자 똑같음 ${sizes.join(' | ')}`);

  await page.click('#feedBtn');
  await shot(page, 'feed');
  check((await page.$$eval('#amountRow button', (b) => b.map((x) => x.textContent))).join() === '120,140,160', '최근 양 세 가지');
  check((await text(page, '#amountRow .on')) === '160', '기본 선택은 마지막 양');
  await page.click('#feedSave');
  await page.waitForSelector('#undo:not(.hidden)');
  check(await text(page, '#elapsed') === '0:00', '저장하면 상태 칸이 바로 바뀜');
  check(await page.isVisible('#micBtn'), '저장 알림 동안에도 [말하기]는 보임');
  check(await text(page, '#todayCount') === '4회', '오늘 횟수 증가(예시 3회 + 1)');
  await shot(page, 'saved');

  await page.click('#undoMsg');
  await page.click('#feedBtn');
  await page.click('#feedSave');
  await page.waitForSelector('#confirmSheet:not(.hidden)');
  check(true, '10분 안 같은 종류는 확인을 물음');
  await shot(page, 'confirm');
  await page.click('#confirmNo');

  await page.click('#diaperBtn');
  await page.click('#diaperSheet [data-type="poo"]');
  await page.waitForSelector('#undo:not(.hidden)');
  check((await text(page, '#lastDiaper')).includes('대변'), '기저귀 저장');
  await page.click('#undoBtn');
  await page.waitForTimeout(300);
  check((await text(page, '#lastDiaper')).includes('소변'), '취소하면 이전 기록으로');
  const kept = await page.evaluate(() => JSON.parse(localStorage.getItem('albam.demo.events')).filter((e) => e.deleted_at).length);
  check(kept === 1, '취소한 기록은 지우지 않고 표시만');

  await page.click('#lateBtn');
  await page.click('#lateSheet [data-kind="sleep"]');
  await shot(page, 'late-sleep');
  await page.click('#lateSheet [data-kind="feed"]');
  for (let i = 0; i < 3; i += 1) await page.click('#lateSteps [data-min="-60"]');
  await page.click('#lateSave');
  await page.waitForTimeout(300);
  check((await text(page, '#lastFeed')).startsWith('수유 14:00'), '3시간 전 기록은 마지막 수유를 바꾸지 않음');
  await page.click('#undoMsg');
  await page.click('#lateBtn');
  await page.click('#recentBtn');
  const rows = await page.$$eval('#recentList div', (d) => d.map((x) => x.textContent));
  check(rows.some((r) => r.includes('10:30')) && rows.indexOf(rows.find((r) => r.includes('10:30'))) > 0, '최근 기록에서 실제 시각 순서로 자리 잡음');
  await shot(page, 'recent');
  check(errors.length === 0, `페이지 오류 없음 ${errors.join(' ')}`);
}

// 미리 보기에서도 오프라인 저장·"대기 n건"이 실제와 똑같이 동작하고, 실제 큐와 섞이지 않는지
async function demoOfflineFlow(browser, base) {
  const context = await browser.newContext(DEVICE);
  const page = await context.newPage();
  await page.clock.setFixedTime(DAYTIME);
  await page.goto(`${base}?demo`);
  await page.evaluate(() => { localStorage.clear(); indexedDB.deleteDatabase('albam-demo'); indexedDB.deleteDatabase('albam'); });
  await page.reload();
  await page.waitForTimeout(400);
  check(await text(page, '#net') === '미리 보기', '미리 보기 표시');

  await context.setOffline(true);
  await page.click('#diaperBtn');
  await page.click('#diaperSheet [data-type="poo"]');
  await page.waitForTimeout(300);
  check(await text(page, '#net') === '대기 1건', '미리 보기에서 오프라인 기록 → "대기 1건"');
  check((await text(page, '#undoText')).includes('(대기)'), '저장 알림에 (대기) 표시');
  await shot(page, 'demo-pending');
  const realQueue = await page.evaluate(() => new Promise((res) => {
    const r = indexedDB.open('albam');
    r.onupgradeneeded = () => r.result.createObjectStore('queue', { keyPath: 'seq', autoIncrement: true });
    r.onsuccess = () => { const q = r.result.transaction('queue').objectStore('queue').count(); q.onsuccess = () => res(q.result); };
  }));
  check(realQueue === 0, '미리 보기 기록은 실제 큐(albam)에 들어가지 않음');

  await context.setOffline(false);
  await page.evaluate(() => window.dispatchEvent(new Event('online')));
  await page.waitForTimeout(500);
  check(await text(page, '#net') === '미리 보기', '다시 연결되면 "대기" 사라짐');
  const saved = await page.evaluate(() => JSON.parse(localStorage.getItem('albam.demo.events')).filter((e) => e.kind === 'diaper' && e.detail.type === 'poo').length);
  check(saved === 1, '쌓였던 기록이 (가짜) 서버로 들어감');
}

async function nightFlow(browser, base) {
  const page = await (await browser.newContext(DEVICE)).newPage();
  await page.clock.install({ time: NIGHT });
  await page.goto(`${base}?demo`);
  await page.evaluate(() => localStorage.clear());
  await page.reload();
  await page.clock.runFor(2000);
  check(!(await page.isHidden('#night')), '밤에는 거의 검은 화면');
  await shot(page, 'night');
  await page.touchscreen.tap(300, 200);
  await page.clock.runFor(1000);
  check(await page.isHidden('#night'), '터치하면 밝아짐');
  await shot(page, 'night-wake');
  await page.clock.runFor(31000);
  check(!(await page.isHidden('#night')), '30초 뒤 다시 어두워짐');
  await page.clock.runFor(3 * 60000);
  check((await page.evaluate(() => document.querySelector('#shift').style.transform)) !== '', '몇 분마다 화면 위치 이동');
}

async function supabaseFlow(browser, base) {
  const context = await browser.newContext(DEVICE);
  const fake = await createFakeSupabase(context);
  const page = await context.newPage();
  const errors = [];
  page.on('pageerror', (e) => errors.push(String(e)));
  await page.clock.setFixedTime(DAYTIME);
  await page.goto(base);
  await page.evaluate(() => { localStorage.clear(); indexedDB.deleteDatabase('albam'); });
  await page.reload();
  await page.waitForTimeout(300);

  check(await page.isVisible('#loginSheet') && await page.isVisible('#setupFields'), '설정이 없으면 주소·키·로그인 칸');
  await page.fill('#cfgUrl', fake.url);
  await page.fill('#cfgKey', 'anon');
  await page.fill('#email', 'izzy@example.com');
  await page.fill('#password', 'wrong');
  await page.click('#loginBtn');
  await page.waitForTimeout(200);
  check((await text(page, '#loginMsg')).includes('맞지 않아요'), '틀린 비밀번호 안내');
  await page.fill('#password', fake.password);
  await page.click('#loginBtn');
  await page.waitForTimeout(400);
  check(await page.isHidden('#loginSheet'), '로그인');

  await page.click('#feedBtn');
  await page.click('#feedSave');
  await page.waitForTimeout(400);
  check(fake.events.length === 1, '기록이 Supabase 로 감');
  check(await text(page, '#todayCount') === '1회', '요약 다시 받음');
  await page.click('#undoMsg');

  await fake.goOffline();
  await page.click('#diaperBtn');
  await page.click('#diaperSheet [data-type="poo"]');
  await page.waitForTimeout(400);
  check(fake.events.length === 1, '오프라인이면 보내지 않음');
  check((await text(page, '#net')) === '대기 1건', '"대기 1건" 표시');
  check((await text(page, '#lastDiaper')).includes('대변'), '못 보낸 기록도 상태 칸에 보임');
  await page.click('#undoMsg');

  await page.click('#feedBtn');
  await page.click('#feedSave');
  await page.waitForTimeout(300);
  check(await page.isVisible('#confirmSheet'), '오프라인에서도 기기 안에서 중복 확인');
  await page.click('#confirmYes');
  await page.waitForTimeout(300);
  check((await text(page, '#net')) === '대기 2건', '"대기 2건"');
  await page.click('#undoBtn');
  await page.waitForTimeout(300);
  check((await text(page, '#net')) === '대기 1건', '못 보낸 기록 취소는 쌓인 곳에서 빼기만');

  await page.reload();
  await page.waitForTimeout(600);
  check((await text(page, '#net')) === '대기 1건', '앱을 다시 열어도 남아 있음');

  await fake.goOnline();
  await page.evaluate(() => window.dispatchEvent(new Event('online')));
  await page.waitForTimeout(800);
  check(fake.events.length === 2 && fake.events[1].kind === 'diaper', '다시 연결되면 보냄');
  check((await text(page, '#net')) === '', '"대기" 사라짐');

  await page.evaluate(() => {
    const s = JSON.parse(localStorage.getItem('albam.session'));
    s.access_token = 'expired';
    localStorage.setItem('albam.session', JSON.stringify(s));
  });
  await page.reload();
  await page.waitForTimeout(600);
  check(fake.calls.some((c) => c.includes('grant_type=refresh_token')), '토큰이 만료되면 갱신');
  check(await text(page, '#todayCount') === '1회', '갱신 뒤 요약');
  check(errors.length === 0, `페이지 오류 없음 ${errors.join(' ')}`);
}

const server = await serve();
const base = `http://localhost:${server.address().port}/albam/`;
const browser = await chromium.launch();
try {
  console.log('# 미리 보기'); await demoFlow(browser, base);
  console.log('# 미리 보기 오프라인'); await demoOfflineFlow(browser, base);
  console.log('# 밤 화면'); await nightFlow(browser, base);
  console.log('# Supabase(가짜)'); await supabaseFlow(browser, base);
} finally {
  await browser.close();
  server.close();
}
console.log(failures ? `\n${failures}개 실패` : '\n모두 통과');
process.exit(failures ? 1 : 0);
