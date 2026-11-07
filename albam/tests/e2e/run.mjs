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

/**
 * S10 을 가로로 두면 위·아래가 곡면이다. 보이는 글·버튼이 위·아래 8 논리 픽셀 안으로 들어가지 않았는지.
 * @returns {Promise<string[]>} 들어간 요소 목록
 */
const SAFE_Y = 8;
function curvedEdgeOffenders(page, selector) {
  return page.evaluate(({ selector, safe }) => {
    const stage = document.querySelector('#stage');
    const zoom = parseFloat(stage.style.zoom) || 1;
    const top = stage.getBoundingClientRect().top;
    return [...document.querySelectorAll(selector)]
      .filter((e) => e.offsetParent && getComputedStyle(e).visibility !== 'hidden')
      .map((e) => { const r = e.getBoundingClientRect(); return { id: e.id || e.className || e.tagName, t: (r.top - top) / zoom, b: (r.bottom - top) / zoom }; })
      .filter((r) => r.t < safe - 0.5 || r.b > 180 - safe + 0.5)
      .map((r) => `${r.id}(${r.t.toFixed(0)}~${r.b.toFixed(0)})`);
  }, { selector, safe: SAFE_Y });
}

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
  const label = (sel) => page.getAttribute(sel, 'aria-label');
  check(await label('#elapsed') === '2시간 35분 전', '큰 글씨: 마지막 수유 뒤 "2시간 35분 전"');
  check(await text(page, '#lastFeed') === '마지막 수유11:25 · 200ml', '마지막 수유 시각에 이름표');
  check(await text(page, '#clock') === '지금14:00', '현재 시각에 "지금"');
  check(await text(page, '#today') === '오늘 수유3회 · 570ml', '오늘 수유 한 줄');
  check(await text(page, '#lastDiaper') === '마지막 기저귀소변 · 1시간 10분 전', '마지막 기저귀 "1시간 10분 전"');
  const overflow = await page.$$eval('#status > div', (els) => els.filter((e) => e.getBoundingClientRect().right > document.querySelector('#status').getBoundingClientRect().right + 0.5).map((e) => e.id));
  check(overflow.length === 0, `상태 칸 글이 넘치지 않음 ${overflow.join()}`);
  const box = (sel) => page.$eval(sel, (b) => { const r = b.getBoundingClientRect(); const i = b.querySelector('.ico').getBoundingClientRect();
    return { w: r.width, h: r.height, top: r.top, ico: `${i.width}x${i.height}`, font: getComputedStyle(b).fontSize }; });
  const [mic, feed, diaper, late] = [await box('#micBtn'), await box('#feedBtn'), await box('#diaperBtn'), await box('#lateBtn')];
  check(mic.w === mic.h && JSON.stringify(mic) === JSON.stringify({ ...late, top: mic.top }) && (await text(page, '#micBtn')) === '' && (await text(page, '#lateBtn')) === '',
    `마이크·지난 기록은 아이콘만, 같은 정사각형 ${mic.w}x${mic.h}`);
  check((await page.getAttribute('#micBtn', 'aria-label')) === '말하기' && (await page.getAttribute('#lateBtn', 'aria-label')).startsWith('지난 기록'), '아이콘 버튼에 이름(화면 낭독용)');
  check(JSON.stringify(feed) === JSON.stringify(diaper), `수유·기저귀 크기·아이콘·글자 똑같음 ${JSON.stringify(feed)}`);
  check(feed.w > mic.w * 3 && feed.h === mic.h && feed.top === mic.top && feed.ico === mic.ico, '수유·기저귀가 크게, 높이·줄·아이콘 크기는 마이크와 같음');
  const curved = await curvedEdgeOffenders(page, '#status > div, #actions button, #bubble, #albam');
  check(curved.length === 0, `위·아래 곡면(8px)에 글·버튼 없음 ${curved.join(' ')}`);

  await page.click('#feedBtn');
  const quick = () => page.$$eval('#amountRow button', (b) => b.map((x) => `${x.querySelector('.t24').textContent}/${x.querySelector('.machine').textContent}`).join());
  const chosen = async () => `${await text(page, '#stepRow .amount .t24')} ${await text(page, '#stepRow .amount .machine')}`;
  check((await curvedEdgeOffenders(page, '#feedSheet h2, #feedSheet button, #feedSheet .amount')).length === 0, '수유 창: 위·아래 곡면에 글·버튼 없음');
  check(await quick() === '200/브레짜 180,230/브레짜 210,270/브레짜 240', '빠른 선택 처음 값: 브레짜 180·210·240 (200·230·270)');
  check(await chosen() === '200ml 브레짜 180', '기본 선택은 마지막으로 먹인 양, 브레짜 물 양 같이');

  // ± 버튼: 브레짜 한 칸(물 30ml) 단위, ±10 은 덜 먹었을 때
  await page.click('#stepRow .machineBtn >> nth=1');   // +30 브레짜
  check(await chosen() === '230ml 브레짜 210', '+30 브레짜 → 230ml');
  await page.click('#stepRow .fineBtn >> nth=0');      // -10
  check(await chosen() === '220ml 브레짜 칸 아님', '-10 하면 브레짜 칸이 아님을 표시');
  await page.click('#stepRow .machineBtn >> nth=0');   // -30 브레짜 → 아래 칸에 맞춤
  check(await chosen() === '200ml 브레짜 180', '-30 브레짜 는 아래쪽 칸(180)에 맞춤');

  // 수유량 설정: 셋째 칸 270 → 300(브레짜 270), 저장하면 수유 창으로 돌아와 새 양이 보임
  await page.click('#amountEditBtn');
  await page.waitForSelector('#amountSheet:not(.hidden)');
  const slots = () => page.$$eval('#amountSlots .amount .t24', (v) => v.map((x) => x.textContent).join());
  check(await slots() === '200ml,230ml,270ml', '수유량 설정 창에 지금 양');
  check((await curvedEdgeOffenders(page, '#amountSheet h2, #amountSheet button, #amountSheet .amount')).length === 0, '수유량 설정 창: 위·아래 곡면에 글·버튼 없음');
  check((await page.$$eval('#amountSlots .fineBtn', (b) => b.length)) === 0, '수유량 설정은 브레짜 칸 단위로만');
  await page.click('#amountSlots .slot:nth-child(3) .machineBtn >> nth=1');  // +30 브레짜
  check(await slots() === '200ml,230ml,300ml', '+30 브레짜 → 300ml(브레짜 270)');
  await shot(page, 'feed-amounts');
  await page.click('#amountSave');
  await page.waitForSelector('#feedSheet:not(.hidden)');
  check(await quick() === '200/브레짜 180,230/브레짜 210,300/브레짜 270', '저장하면 빠른 선택이 바뀜');
  check(await chosen() === '200ml 브레짜 180', '돌아와도 고르던 양은 그대로');
  await page.click('#amountRow button:nth-child(2)');
  check(await chosen() === '230ml 브레짜 210', '빠른 선택 230 누르면 브레짜 210');
  await shot(page, 'feed');
  await page.click('#feedSave');
  await page.waitForSelector('#undo:not(.hidden)');
  check((await text(page, '#lastFeed')).includes('230ml'), '230ml(브레짜 210) 로 저장');
  check(await page.getAttribute('#elapsed', 'aria-label') === '방금', '저장하면 상태 칸이 바로 바뀜(방금)');
  check(await page.isVisible('#micBtn'), '저장 알림 동안에도 [말하기]는 보임');
  check(await text(page, '#today') === '오늘 수유4회 · 800ml', '오늘 횟수 증가(예시 3회 + 1)');
  await shot(page, 'saved');

  await page.click('#undoMsg');
  await page.click('#feedBtn');
  await page.click('#feedSave');
  await page.waitForSelector('#confirmSheet:not(.hidden)');
  check(true, '10분 안 같은 종류는 확인을 물음');
  await shot(page, 'confirm');
  await page.click('#confirmNo');
  check(await text(page, '#notice') === '안 넣었어요' && await page.isVisible('#notice'), '결과 알림은 아래 막대에("안 넣었어요")');
  const bubbleNow = await page.$eval('#bubble', (b) => (b.classList.contains('empty') ? '' : b.textContent));
  check(['', '고마워요!', '배고파요…', '쿨쿨'].includes(bubbleNow), `말풍선에는 알밤 말만 ("${bubbleNow}")`);

  await page.click('#diaperBtn');
  await page.click('#diaperSheet [data-type="poo"]');
  await page.waitForSelector('#undo:not(.hidden)');
  check((await text(page, '#lastDiaper')).includes('대변'), '기저귀 저장');
  await page.click('#undoBtn');
  await page.waitForTimeout(300);
  check((await text(page, '#lastDiaper')).includes('소변'), '취소하면 이전 기록으로');
  check(await text(page, '#notice') === '취소했어요', '취소 결과는 아래 막대에("취소했어요")');
  check(!(await text(page, '#bubble')).includes('취소'), '말풍선에는 취소 알림이 안 뜸');
  const kept = await page.evaluate(() => JSON.parse(localStorage.getItem('albam.demo.events')).filter((e) => e.deleted_at).length);
  check(kept === 1, '취소한 기록은 지우지 않고 표시만');

  await page.click('#lateBtn');
  await page.click('#lateSheet [data-kind="sleep"]');
  await shot(page, 'late-sleep');
  await page.click('#lateSheet [data-kind="feed"]');
  await shot(page, 'late-feed');
  check((await curvedEdgeOffenders(page, '#lateSheet h2, #lateSheet button, #lateSheet .timeRow, #lateSheet .amount')).length === 0, '지난 기록 창: 위·아래 곡면에 글·버튼 없음');
  const lateOverflow = await page.$$eval('#lateSheet .row, #lateSheet .timeRow', (rows) => {
    const foot = document.querySelector('#lateSheet .foot').getBoundingClientRect().top;
    return rows.filter((r) => r.offsetParent && r.getBoundingClientRect().bottom > foot).map((r) => r.id);
  });
  check(lateOverflow.length === 0, `지난 기록 창: 줄이 아래 버튼과 안 겹침 ${lateOverflow.join()}`);
  for (let i = 0; i < 3; i += 1) await page.click('#lateSteps [data-min="-60"]');
  await page.click('#lateSave');
  await page.waitForTimeout(300);
  check((await text(page, '#lastFeed')).startsWith('마지막 수유14:00'), '3시간 전 기록은 마지막 수유를 바꾸지 않음');
  await page.click('#undoMsg');
  await page.click('#lateBtn');
  await page.click('#recentBtn');
  const rows = await page.$$eval('#recentList div', (d) => d.map((x) => x.textContent));
  check(rows.some((r) => r.includes('10:30')) && rows.indexOf(rows.find((r) => r.includes('10:30'))) > 0, '최근 기록에서 실제 시각 순서로 자리 잡음');
  await shot(page, 'recent');
  check(errors.length === 0, `페이지 오류 없음 ${errors.join(' ')}`);
}

// 옆으로 밀면 통계 쪽, 점을 눌러도 넘어감, 1분 안 만지면 대시보드로
async function statsFlow(browser, base) {
  const page = await (await browser.newContext(DEVICE)).newPage();
  const errors = [];
  page.on('pageerror', (e) => errors.push(String(e)));
  await page.clock.install({ time: DAYTIME });
  await page.goto(`${base}?demo`);
  await page.evaluate(() => localStorage.clear());
  await page.reload();
  await page.clock.runFor(500);
  const swipe = async (fromX, toX, y = 180) => {
    await page.mouse.move(fromX, y); await page.mouse.down();
    await page.mouse.move((fromX + toX) / 2, y); await page.mouse.move(toX, y); await page.mouse.up();
    await page.clock.runFor(500);   // 밀고 난 직후(0.4초) 클릭은 무시되므로
  };
  const onStats = () => page.isVisible('#pageStats');

  check(!(await onStats()) && await page.isVisible('#pageDots'), '처음엔 대시보드, 아래에 쪽 표시');
  await swipe(560, 200, 290);   // 수유 버튼 위에서 시작해 왼쪽으로
  check(await onStats(), '왼쪽으로 밀면 통계 쪽');
  check(await page.isHidden('#feedSheet'), '밀다가 버튼 위에서 떼도 버튼은 안 눌림');
  check(await page.isVisible('#actions'), '통계 쪽에서도 큰 버튼 줄은 그대로');
  check((await page.$$eval('#statsChart .col', (c) => c.length)) === 7, '막대 일곱 개');
  const labels = await page.$$eval('#statsChart .d', (d) => d.map((x) => x.textContent));
  check(labels[6] === '오늘' && labels[0] === '10/31', `날짜 아래 표시 ${labels.join(' ')}`);
  check((await text(page, '#statsFoot')).startsWith('지난 6일 평균'), '아래에 평균(오늘 빼고)');
  const curved = await curvedEdgeOffenders(page, '#statsHead span, #statsTabs button, #statsChart .v, #statsChart .d, #statsChart .bar, #statsFoot, #pageDots');
  check(curved.length === 0, `통계 쪽: 위·아래 곡면에 글·버튼 없음 ${curved.join(' ')}`);
  const over = await page.$$eval('#statsChart .v', (v) => v.filter((x) => x.getBoundingClientRect().top < document.querySelector('#statsChart').getBoundingClientRect().top - 0.5).length);
  check(over === 0, '막대 위 값이 그래프 칸 안');
  await shot(page, 'stats-feed');
  await page.click('#statsTabs [data-metric="diaper"]');
  check((await page.$$eval('#statsChart .v', (v) => v[0].textContent)).endsWith('회'), '기저귀 탭');
  await shot(page, 'stats-diaper');
  await page.click('#statsTabs [data-metric="sleep"]');
  check((await page.$$eval('#statsChart .v', (v) => v[0].textContent)).endsWith('시간'), '잠 탭');
  check((await text(page, '#statsFoot')).includes('낮잠') && (await text(page, '#statsFoot')).includes('밤잠'), '잠 평균: 낮잠·밤잠');
  await shot(page, 'stats-sleep');

  await swipe(200, 560);
  check(!(await onStats()), '오른쪽으로 밀면 대시보드');
  await page.click('#pageDots');
  await page.clock.runFor(300);
  check(await onStats(), '점을 눌러도 통계 쪽');
  await page.clock.runFor(65000);
  check(!(await onStats()), '1분 동안 안 만지면 대시보드로');
  await page.click('#pageDots');
  await page.click('#diaperBtn');
  check(!(await onStats()) && await page.isVisible('#diaperSheet'), '통계 쪽에서 큰 버튼 누르면 대시보드로 돌아와 창이 열림');
  await swipe(560, 200, 200);
  check(!(await onStats()), '창이 열려 있으면 밀어도 안 넘김');
  check(errors.length === 0, `페이지 오류 없음 ${errors.join(' ')}`);
}

// 가장 긴 글(12시간 넘게 지남, 소변+대변)도 상태 칸을 넘지 않는지
async function longTextFlow(browser, base) {
  const page = await (await browser.newContext(DEVICE)).newPage();
  await page.clock.setFixedTime(DAYTIME);
  await page.goto(`${base}?demo`);
  await page.evaluate(() => {
    localStorage.clear();
    const ago = (m) => new Date(Date.now() - m * 60000).toISOString();
    localStorage.setItem('albam.demo.events', JSON.stringify([
      { id: 'a', kind: 'feed', occurred_at: ago(12 * 60 + 35), amount_ml: 160, detail: {} },
      { id: 'b', kind: 'diaper', occurred_at: ago(11 * 60 + 59), detail: { type: 'both' } },
    ]));
  });
  await page.reload();
  await page.waitForTimeout(500);
  check(await page.getAttribute('#elapsed', 'aria-label') === '12시간 35분 전', '10시간 넘어도 분까지(큰 글씨)');
  check((await text(page, '#lastDiaper')).endsWith('11시간 전'), '기저귀 줄은 10시간 넘으면 시간만');
  const overflow = await page.$$eval('#status > div', (els) => {
    const right = document.querySelector('#status').getBoundingClientRect().right;
    return els.filter((e) => e.getBoundingClientRect().right > right + 0.5).map((e) => e.id);
  });
  check(overflow.length === 0, `긴 글도 상태 칸 안 ${overflow.join()}`);
  await shot(page, 'long');
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
  // config.js 에 실제 주소·키가 들어 있으므로, 이 시험에서는 빈 설정으로 바꿔 '처음 설치' 화면부터 본다
  await context.route('**/albam/config.js', async (route) => {
    const body = (await (await route.fetch()).text()).replace(/supabaseUrl: '[^']*'/, "supabaseUrl: ''").replace(/supabaseAnonKey: '[^']*'/, "supabaseAnonKey: ''");
    await route.fulfill({ body, contentType: 'text/javascript' });
  });
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
  check(fake.events[0].amount_ml === 200, '기록이 없으면 빠른 선택 첫 값(200, 브레짜 180)으로');
  check((await text(page, '#today')).startsWith('오늘 수유1회'), '요약 다시 받음');
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

  // 오프라인에서 수유량 설정 바꾸기 → 쌓였다가 연결되면 보냄
  await page.click('#feedBtn');
  await page.click('#amountEditBtn');
  for (let i = 0; i < 2; i += 1) await page.click('#amountSlots .slot:nth-child(3) .machineBtn >> nth=1');  // 브레짜 240 → 270 → 300
  await page.click('#amountSave');
  await page.waitForSelector('#feedSheet:not(.hidden)');
  check((await page.$$eval('#amountRow .t24', (b) => b.map((x) => x.textContent).join())) === '200,230,330', '오프라인에서도 바꾼 양이 바로 보임');
  check((await text(page, '#net')) === '대기 2건', '수유량 설정도 대기에 쌓임');
  await page.click('#feedSheet [data-close]');

  await fake.goOnline();
  await page.evaluate(() => window.dispatchEvent(new Event('online')));
  await page.waitForTimeout(800);
  check(fake.events.length === 2 && fake.events[1].kind === 'diaper', '다시 연결되면 보냄');
  check(fake.feedAmounts.join() === '200,230,330', '쌓였던 수유량 설정도 Supabase 로 감');
  check((await text(page, '#net')) === '', '"대기" 사라짐');

  await page.evaluate(() => {
    const s = JSON.parse(localStorage.getItem('albam.session'));
    s.access_token = 'expired';
    localStorage.setItem('albam.session', JSON.stringify(s));
  });
  await page.reload();
  await page.waitForTimeout(600);
  check(fake.calls.some((c) => c.includes('grant_type=refresh_token')), '토큰이 만료되면 갱신');
  check((await text(page, '#today')).startsWith('오늘 수유1회'), '갱신 뒤 요약');
  check(errors.length === 0, `페이지 오류 없음 ${errors.join(' ')}`);
}

const server = await serve();
const base = `http://localhost:${server.address().port}/albam/`;
const browser = await chromium.launch();
try {
  console.log('# 미리 보기'); await demoFlow(browser, base);
  console.log('# 통계 쪽'); await statsFlow(browser, base);
  console.log('# 긴 글'); await longTextFlow(browser, base);
  console.log('# 미리 보기 오프라인'); await demoOfflineFlow(browser, base);
  console.log('# 밤 화면'); await nightFlow(browser, base);
  console.log('# Supabase(가짜)'); await supabaseFlow(browser, base);
} finally {
  await browser.close();
  server.close();
}
console.log(failures ? `\n${failures}개 실패` : '\n모두 통과');
process.exit(failures ? 1 : 0);
