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
  check(await text(page, '#age') === 'D+142 · 4개월 20일 · 교정 3개월 28일', `나이 줄(11/6 기준) ${await text(page, '#age')}`);
  check(await text(page, '#lastFeed') === '마지막 수유11:25 · 200ml', '마지막 수유 시각에 이름표');
  check(await text(page, '#clock') === '14:00', '맨 위 오른쪽 현재 시각');
  check(await text(page, '#today') === '오늘3회 · 570ml', '오늘 수유는 마지막 수유 오른쪽');
  check(await text(page, '#lastDiaper') === '마지막 기저귀소변 · 1시간 10분 전', '마지막 기저귀 "1시간 10분 전"');
  check((await text(page, '#lastSleep')).startsWith('마지막 잠') && (await text(page, '#lastSleep')).endsWith('깸'), `마지막 잠 줄 (${await text(page, '#lastSleep')})`);
  const statusOverlap = await page.$$eval('#status > div', (rows) => {
    const boxes = rows.filter((r) => r.offsetParent && r.textContent).map((r) => [r.id, r.getBoundingClientRect()]);
    const dots = document.querySelector('#pageDots').getBoundingClientRect();
    const bad = [];
    boxes.forEach(([id, a], i) => boxes.slice(i + 1).forEach(([id2, b]) => { if (a.bottom > b.top + 0.5 && b.bottom > a.top + 0.5 && a.right > b.left && b.right > a.left) bad.push(`${id}/${id2}`); }));
    boxes.forEach(([id, a]) => { if (a.bottom > dots.top + 4 * (dots.height / 12) && a.right > dots.left && a.left < dots.right) bad.push(`${id}/점`); });
    return bad;
  });
  check(statusOverlap.length === 0, `상태 줄끼리, 쪽 점과 안 겹침 ${statusOverlap.join()}`);
  const overflow = await page.$$eval('#status > div', (els) => els.filter((e) => e.getBoundingClientRect().right > document.querySelector('#status').getBoundingClientRect().right + 0.5).map((e) => e.id));
  check(overflow.length === 0, `상태 칸 글이 넘치지 않음 ${overflow.join()}`);
  const box = (sel) => page.$eval(sel, (b) => { const r = b.getBoundingClientRect(); const i = b.querySelector('.ico').getBoundingClientRect();
    return { w: r.width, h: r.height, top: r.top, ico: `${i.width}x${i.height}`, font: getComputedStyle(b).fontSize }; });
  const [mic, feed, diaper, late] = [await box('#micBtn'), await box('#feedBtn'), await box('#diaperBtn'), await box('#lateBtn')];
  check(mic.w === mic.h && JSON.stringify(mic) === JSON.stringify({ ...late, top: mic.top }) && (await text(page, '#micBtn')) === '' && (await text(page, '#lateBtn')) === '',
    `마이크·지난 기록은 아이콘만, 같은 정사각형 ${mic.w}x${mic.h}`);
  check((await page.getAttribute('#micBtn', 'aria-label')) === '말하기' && (await page.getAttribute('#lateBtn', 'aria-label')).startsWith('더보기'), '아이콘 버튼에 이름(화면 낭독용)');
  check(JSON.stringify(feed) === JSON.stringify(diaper), `수유·기저귀 크기·아이콘·글자 똑같음 ${JSON.stringify(feed)}`);
  check(feed.w > mic.w * 2.5 && feed.h === mic.h && feed.top === mic.top && feed.ico === mic.ico, '수유·기저귀가 크게, 높이·줄·아이콘 크기는 마이크와 같음');
  const sleepBox = await box('#sleepBtn');
  check(sleepBox.w === mic.w && sleepBox.h === mic.h && sleepBox.top === mic.top && (await text(page, '#sleepBtn')) === '', '[잠]은 마이크와 같은 정사각형 달 아이콘');
  const fits = await page.$$eval('#feedBtn, #diaperBtn', (bs) => bs.every((b) => b.scrollWidth <= b.clientWidth + 0.5));
  check(fits, '수유·기저귀 버튼 글이 넘치지 않음');
  const curved = await curvedEdgeOffenders(page, '#status > div, #actions button, #bubble, #albam');
  await sleepFlow(page);
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
  check(await text(page, '#today') === '오늘4회 · 800ml', '오늘 횟수 증가(예시 3회 + 1)');
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
  await page.click('#moreLate');
  await page.click('#lateSheet [data-kind="sleep"]');
  await shot(page, 'late-sleep');
  await page.click('#lateSheet [data-kind="feed"]');
  await shot(page, 'late-feed');
  check((await curvedEdgeOffenders(page, '#lateSheet h2, #lateSheet button, #lateSheet .wheel, #lateSheet .amount')).length === 0, '지난 기록 창: 위·아래 곡면에 글·버튼 없음');
  const lateOverflow = await page.$$eval('#lateSheet .row, #lateTimes', (rows) => {
    const foot = document.querySelector('#lateSheet .foot').getBoundingClientRect().top;
    return rows.filter((r) => r.offsetParent && r.getBoundingClientRect().bottom > foot).map((r) => r.id);
  });
  check(lateOverflow.length === 0, `지난 기록 창: 줄이 아래 버튼과 안 겹침 ${lateOverflow.join()}`);
  // 시각 바퀴: 처음은 30분 전(13:30)
  const lateTime = async (which = 'start') => (await page.$$eval(`#late-${which} .item.c`, (c) => c.map((x) => x.textContent))).join(' ');
  const wheelBox = (which, unit) => page.$eval(`#late-${which} .wheel.${unit}`, (w) => { const r = w.getBoundingClientRect(); return { x: r.x + r.width / 2, y: r.y, h: r.height }; });
  check(await lateTime() === '오늘 13 30' && await page.getAttribute('#lateTimes .lateAgo', 'aria-label') === '30분 전', '처음 시각은 30분 전, 옆에 "30분 전"');
  // 천천히 끌기: 한 칸 = 22 논리 픽셀. 아래로 끌면 작은 값이 가운데로
  const drag = async (which, unit, rows) => {
    const b = await wheelBox(which, unit);
    const unitPx = b.h / 66;
    await page.mouse.move(b.x, b.y + b.h / 2);
    await page.mouse.down();
    for (let i = 1; i <= 10; i += 1) { await page.mouse.move(b.x, b.y + b.h / 2 + (rows * 22 * unitPx * i) / 10); await page.waitForTimeout(20); }
    await page.waitForTimeout(150);
    await page.mouse.up();
    await page.waitForTimeout(100);
  };
  await drag('start', 'hour', 3);
  check(await lateTime() === '오늘 10 30', `시 바퀴를 아래로 세 칸 끌면 3시간 앞(${await lateTime()})`);
  const mb = await wheelBox('start', 'minute');
  await page.mouse.click(mb.x, mb.y + mb.h - 5);
  check(await lateTime() === '오늘 10 31', '분 바퀴 아래 칸을 누르면 +1분');
  await page.mouse.click(mb.x, mb.y + 5);
  check(await lateTime() === '오늘 10 30', '위 칸을 누르면 -1분');
  // 빠르게 튕기면 관성으로 여러 칸
  await page.mouse.move(mb.x, mb.y + mb.h / 2);
  await page.mouse.down();
  for (let i = 1; i <= 4; i += 1) await page.mouse.move(mb.x, mb.y + mb.h / 2 - i * 12);
  await page.mouse.up();
  await page.waitForTimeout(1500);
  const flung = Number((await lateTime()).split(' ')[2]);
  check(flung > 33, `분 바퀴를 위로 튕기면 관성으로 여러 칸(10:${flung})`);
  // 가운데를 누르면 직접 입력. 지금(14:00)보다 늦은 시각은 어제로
  await page.$eval('#lateTimeInput', (i) => { i.value = '23:15'; i.dispatchEvent(new Event('change')); });
  check(await lateTime() === '어제 23 15', '지금보다 늦은 시각을 넣으면 어제로');
  await page.$eval('#lateTimeInput', (i) => { i.value = '10:30'; i.dispatchEvent(new Event('change')); });
  check(await lateTime() === '어제 10 30', '날짜는 고른 날 그대로');
  await drag('start', 'day', -1);
  check(await lateTime() === '오늘 10 30', '날짜 바퀴를 위로 한 칸 끌면 오늘');
  await drag('start', 'hour', -5);
  check(await lateTime() === '오늘 14 00', '미래로는 못 감(지금에서 멈춤)');
  await drag('start', 'hour', 3);   // 14:00 → 11:00
  await page.$eval('#lateTimeInput', (i) => { i.value = '10:30'; i.dispatchEvent(new Event('change')); });
  check(await lateTime() === '오늘 10 30', '직접 입력 10:30');
  await page.click('#lateSheet [data-kind="sleep"]');
  check(await page.isVisible('#late-end') && await lateTime('end') === '오늘 14 00', '잠은 시작·끝 바퀴가 나란히');
  check((await text(page, '#lateDetail')).includes('3시간 30분'), '잠 길이 표시');
  await shot(page, 'late-sleep-wheels');
  await page.click('#lateOngoing');
  check(await page.isHidden('#late-end') && await page.isVisible('#lateTimes .lateAgo'), '[아직 자는 중]: 끝 바퀴 숨김');
  await page.click('#lateOngoing');
  check(await page.isVisible('#late-end'), '다시 누르면 끝 바퀴');
  await page.click('#lateSheet [data-kind="feed"]');
  await page.click('#lateSave');
  await page.waitForTimeout(300);
  check((await text(page, '#lastFeed')).startsWith('마지막 수유14:00'), '3시간 전 기록은 마지막 수유를 바꾸지 않음');
  await page.click('#undoMsg');
  await page.click('#lateBtn');
  await page.click('#moreToday');
  await page.waitForTimeout(400);
  const rows = await page.$$eval('#recentList .dayRow .tm', (d) => d.map((x) => x.textContent.slice(0, 5)));
  check(rows.includes('10:30') && rows.indexOf('10:30') > 0 && rows.join() === [...rows].sort().join(), `오늘 기록 목록에서 실제 시각 순서로 자리 잡음 ${rows.join(' ')}`);
  await shot(page, 'recent');
  check(errors.length === 0, `페이지 오류 없음 ${errors.join(' ')}`);
}

// [잠]: 누르면 잠 시작(끝 없음) → 알밤이 자고 버튼이 "깼어요" → 누르면 끝. 취소하면 다시 자는 중
async function sleepFlow(page) {
  await page.click('#sleepBtn');
  await page.waitForSelector('#undo:not(.hidden)');
  check((await text(page, '#undoText')).startsWith('잠 시작 14:00'), `잠 시작 저장(${await text(page, '#undoText')})`);
  check(await page.getAttribute('#sleepBtn', 'aria-label') === '깼어요' && (await text(page, '#sleepBtn')) === '깼어요', '자는 중이면 버튼이 "깼어요"');
  await page.click('#undoMsg');
  await page.evaluate(() => {   // 1시간 20분 전에 잠든 것으로
    const all = JSON.parse(localStorage.getItem('albam.demo.events'));
    all.find((e) => e.kind === 'sleep' && !e.ended_at).occurred_at = new Date(Date.now() - 80 * 60000).toISOString();
    localStorage.setItem('albam.demo.events', JSON.stringify(all));
  });
  await page.reload();
  await page.waitForTimeout(600);
  check(await text(page, '#bubble') === '쿨쿨 1시간 20분', `말풍선에 잔 시간(${await text(page, '#bubble')})`);
  await shot(page, 'sleeping');
  await page.click('#sleepBtn');
  await page.waitForSelector('#undo:not(.hidden)');
  check(await text(page, '#undoText') === '잠 1시간 20분 저장됨', `깼어요: 잔 시간과 함께 저장(${await text(page, '#undoText')})`);
  check(await page.getAttribute('#sleepBtn', 'aria-label') === '잠들었어요', '깨면 버튼이 다시 잠');
  await page.click('#undoBtn');
  await page.waitForTimeout(300);
  check(await page.getAttribute('#sleepBtn', 'aria-label') === '깼어요', '깼어요를 취소하면 다시 자는 중');
  await page.click('#sleepBtn');
  await page.waitForSelector('#undo:not(.hidden)');
  await page.click('#undoMsg');
  const ended = await page.evaluate(() => JSON.parse(localStorage.getItem('albam.demo.events')).filter((e) => e.kind === 'sleep' && !e.deleted_at && !e.ended_at).length);
  check(ended === 0, '열린 잠 없음');
}

// [수유] → [먹이기 시작] → 버튼이 [다 먹음] → 누르면 걸린 시간과 함께 저장. 취소하면 다시 먹이는 중
async function feedTimerFlow(browser, base) {
  const page = await (await browser.newContext(DEVICE)).newPage();
  const errors = [];
  page.on('pageerror', (e) => errors.push(String(e)));
  await page.clock.install({ time: DAYTIME });
  await page.goto(`${base}?demo`);
  await page.evaluate(() => localStorage.clear());
  await page.reload();
  await page.clock.runFor(800);
  await page.click('#feedBtn');
  check(await page.isVisible('#feedStart') && (await text(page, '#feedSave')) === '지금 저장', '수유 창: [지금 저장] [먹이기 시작]');
  // 저장·요약 받기는 가짜 시계와 따로 돌므로, 시계를 조금씩 돌리며 기다린다
  const until = async (fn) => { for (let i = 0; i < 20 && !(await fn()); i += 1) { await page.clock.runFor(300); await page.waitForTimeout(50); } };
  await page.click('#feedStart');
  await until(async () => (await text(page, '#feedBtnText')) === '다 먹음');
  check(await text(page, '#feedBtnText') === '다 먹음', `먹이는 중: [수유]가 [다 먹음] (${await text(page, '#feedBtnText')})`);
  await page.click('#undoMsg');
  await page.clock.runFor(12 * 60000);
  check(await text(page, '#bubble') === '냠냠 12분', `말풍선에 먹은 시간 (${await text(page, '#bubble')})`);
  const feedFits = await page.$eval('#feedBtn', (b) => b.scrollWidth <= b.clientWidth + 0.5);
  check(feedFits, '"다 먹음"이 버튼 안에 들어감');
  await shot(page, 'feeding');
  await page.click('#feedBtn');
  await until(async () => (await text(page, '#feedBtnText')) === '수유');
  check((await text(page, '#undoText')).startsWith('수유 200ml · 12분'), `다 먹음: 걸린 시간과 함께 (${await text(page, '#undoText')})`);
  check(await text(page, '#feedBtnText') === '수유', '다시 [수유]');
  await page.click('#undoBtn');
  await until(async () => (await text(page, '#feedBtnText')) === '다 먹음');
  check(await text(page, '#feedBtnText') === '다 먹음', '[취소]하면 다시 먹이는 중');
  await page.click('#feedBtn');
  await until(async () => (await text(page, '#feedBtnText')) === '수유');
  await page.click('#undoMsg');
  const saved = await page.evaluate(() => JSON.parse(localStorage.getItem('albam.demo.events')).filter((e) => e.kind === 'feed' && e.ended_at && e.detail.feeding === false).length);
  check(saved === 1, '서버(미리 보기)에 끝 시각이 들어감');
  // 기록 목록과 고치기 창에서 끝 시각
  await page.click('#lateBtn');
  await page.click('#moreToday');
  await page.clock.runFor(800);
  const rows = await page.$$eval('#recentList .dayRow', (r) => r.map((x) => x.textContent));
  check(rows.some((r) => r.includes('수유 200ml · 12분')), `기록 목록에 걸린 시간 ${rows.join(' / ')}`);
  await page.click('#recentList .dayRow:has-text("· 12분")');
  check(await page.isVisible('#late-end') && await page.$eval('#lateFeedEnd', (b) => b.classList.contains('on')), '고치기 창: 시작·끝 바퀴, [끝 시각] 켜짐');
  await shot(page, 'edit-feed-end');
  await page.click('#lateFeedEnd');
  check(await page.isHidden('#late-end'), '[끝 시각]을 끄면 끝 바퀴 숨김');
  await page.click('[data-close]:visible');
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
  const pageNow = () => page.evaluate(() => ['Clock', 'Main', 'Timeline', 'Stats'].find((n) => !document.querySelector(`#page${n}`).classList.contains('hidden')));
  const dot = (i) => page.click(`#pageDots .dot:nth-child(${i})`);

  check(await pageNow() === 'Main' && (await page.$$eval('#pageDots .dot', (d) => d.length)) === 4, '처음엔 대시보드, 아래에 쪽 표시 점 넷');
  check(await page.evaluate(() => document.body.classList.contains('light')), '낮(14시)에는 밝은 화면');
  await shot(page, 'main-light');

  // 시계 쪽: 오른쪽으로 밀면
  await swipe(200, 560);
  check(await pageNow() === 'Clock', '오른쪽으로 밀면 시계 쪽');
  check(await text(page, '#bigClock') === '14:00' && await text(page, '#bigDate') === '11월 6일 금요일', `시각·날짜·요일 크게(${await text(page, '#bigDate')})`);
  check(await text(page, '#bigAge') === 'D+142 · 4개월 20일 · 교정 3개월 28일', `시계 쪽에도 나이 ${await text(page, '#bigAge')}`);
  check((await curvedEdgeOffenders(page, '#bigClock, #bigDate, #bigAge, #pageDots')).length === 0, '시계 쪽: 위·아래 곡면에 글 없음');
  const clockOverlap = await page.evaluate(() => { const a = document.querySelector('#bigAge span:last-child').getBoundingClientRect(); const d = document.querySelector('#pageDots').getBoundingClientRect(); const t = document.querySelector('#bigDate').getBoundingClientRect(); return a.bottom > d.top + 4 || t.bottom > a.top + 1; });
  check(!clockOverlap, '시계 쪽: 날짜·나이·점이 안 겹침');
  await shot(page, 'clock');
  await page.clock.runFor(65000);
  check(await pageNow() === 'Clock', '시계 쪽은 안 만져도 그대로(탁상시계)');
  check(await text(page, '#bigClock') === '14:01', '시계가 간다');

  // 타임라인 쪽
  await swipe(560, 200);
  await swipe(560, 200, 290);   // 수유 버튼 위에서 시작해 왼쪽으로
  check(await pageNow() === 'Timeline', '대시보드에서 왼쪽으로 밀면 타임라인');
  check(await page.isHidden('#feedSheet'), '밀다가 버튼 위에서 떼도 버튼은 안 눌림');
  check(await page.isVisible('#actions'), '다른 쪽에서도 큰 버튼 줄은 그대로');
  await page.clock.runFor(500);
  const tl = await page.$$eval('.tlRow', (rows) => rows.map((r) => ({
    label: r.querySelector('.tlLabel').textContent, feeds: r.querySelectorAll('.tlFeed').length,
    sleeps: r.querySelectorAll('.tlSleep').length, diapers: r.querySelectorAll('.tlDiaper').length, now: !!r.querySelector('.tlNow') })));
  check(tl.length === 3 && tl[0].label === '오늘' && tl[1].label === '어제' && tl[0].now, `줄 셋(오늘·어제·그저께), 오늘에 지금 선 ${JSON.stringify(tl.map((r) => r.label))}`);
  check(tl[0].feeds === 3 && tl[0].diapers === 1 && tl[0].sleeps === 1, `오늘 줄: 수유 3·기저귀 1·잠 1 ${JSON.stringify(tl[0])}`);
  const tlOut = await page.$$eval('.tlTrack *', (els) => {
    const box = document.querySelector('#timelineRows').getBoundingClientRect();
    return els.filter((e) => { const r = e.getBoundingClientRect(); return r.right > box.right + 0.5 || r.left < box.left - 0.5; }).length;
  });
  check(tlOut === 0, '타임라인 표시가 칸 밖으로 안 나감');
  check((await curvedEdgeOffenders(page, '#timelineHead span, #timelineAxis span, .tlRow, #pageDots')).length === 0, '타임라인 쪽: 위·아래 곡면에 글 없음');
  await shot(page, 'timeline');
  // 기록하면 바로 타임라인에도(대시보드로 돌아갔다 와도)
  await page.click('#diaperBtn');
  await page.click('#diaperSheet [data-type="poo"]');
  await page.clock.runFor(500);
  await dot(3);
  await page.clock.runFor(500);
  check((await page.$$eval('.tlRow:first-child .tlDiaper.poo', (d) => d.length)) === 1, '방금 넣은 대변이 타임라인에');

  // 고치기: 날짜 줄을 누르면 그날 기록 목록 → 줄을 누르면 고치기 창
  await page.click('.tlRow:first-child');
  await page.waitForSelector('#recentSheet:not(.hidden)');
  const dayRows = await page.$$eval('#recentList .dayRow', (r) => r.map((x) => x.textContent));
  check(dayRows.length >= 4 && (await text(page, '#recentTitle')).startsWith('오늘 기록'), `오늘 기록 목록(${dayRows.length}줄)`);
  const rowH = await page.$eval('#recentList .dayRow', (r) => r.getBoundingClientRect().height / (parseFloat(document.querySelector('#stage').style.zoom) || 1));
  check(rowH >= 22, `목록 줄이 누르기 좋게 큼(${rowH})`);
  await shot(page, 'day-list');
  await page.click('#recentList .dayRow:has-text("수유 200ml") >> nth=0');
  await page.waitForSelector('#lateSheet:not(.hidden)');
  check((await text(page, '#lateTitle')) === '기록 고치기 · 수유' && await page.isVisible('#lateDelete') && await page.isHidden('#recentBtn'), '고치기 창: 제목, [지우기]');
  check((await page.$$eval('#lateSheet .kinds [data-kind]', (b) => b.filter((x) => !x.classList.contains('hidden')).length)) === 1, '고칠 때는 종류를 못 바꿈');
  await page.click("#lateDetail .machineBtn >> nth=1");   // +30 브레짜
  await shot(page, 'edit-feed');
  await page.click('#lateSave');
  await page.clock.runFor(800);
  check((await text(page, '#notice')).startsWith('고쳤어요 · 수유 230ml'), `고친 결과 알림(${await text(page, '#notice')})`);
  const edited = await page.evaluate(() => JSON.parse(localStorage.getItem('albam.demo.events')).filter((e) => e.kind === 'feed' && e.amount_ml === 230).length);
  check(edited === 1, '서버(미리 보기) 기록이 230ml 로');
  check((await page.$$eval('.tlRow:first-child .tlMl', (m) => m.map((x) => x.textContent))).includes('230'), '타임라인에도 230');
  // 지우기: 두 번 눌러야
  await page.click('.tlRow:first-child');
  await page.waitForSelector('#recentSheet:not(.hidden)');
  await page.clock.runFor(300);
  await page.click('#recentList .dayRow:has-text("기저귀") >> nth=0');
  await page.click('#lateDelete');
  check(await text(page, '#lateDelete') === '한 번 더 누르면 지워요' && await page.isVisible('#lateSheet'), '[지우기] 한 번은 확인만');
  await page.click('#lateDelete');
  await page.clock.runFor(800);
  check((await text(page, '#notice')).startsWith('지웠어요 · 기저귀'), '두 번 누르면 지움');
  const deleted = await page.evaluate(() => JSON.parse(localStorage.getItem('albam.demo.events')).filter((e) => e.deleted_at).length);
  check(deleted === 1, '지운 기록은 취소 표시만(남아 있음)');

  // 통계 쪽
  await swipe(560, 200);
  check(await pageNow() === 'Stats', '한 번 더 밀면 통계');
  check((await page.$$eval('#statsChart .card', (c) => c.length)) === 7, '날짜 카드 일곱 장');
  const labels = await page.$$eval('#statsChart .card .d', (d) => d.map((x) => x.textContent));
  check(labels[6] === '오늘' && labels[0] === '10/31', `카드 위에 날짜 ${labels.join(' ')}`);
  check((await text(page, '#statsFoot')).startsWith('지난 6일 평균'), '아래에 평균(오늘 빼고)');
  check((await text(page, '#statsLegend')).startsWith('숫자 = 횟수'), '카드 읽는 법');
  const curved = await curvedEdgeOffenders(page, '#statsLegend span, #statsTabs button, #statsChart .card, #statsFoot, #pageDots');
  check(curved.length === 0, `통계 쪽: 위·아래 곡면에 글·버튼 없음 ${curved.join(' ')}`);
  const cardOverflow = await page.$$eval('#statsChart .card', (cs) => cs.filter((c) => [...c.children].some((x) => {
    const r = x.getBoundingClientRect(); const b = c.getBoundingClientRect(); return r.left < b.left - 0.5 || r.right > b.right + 0.5 || r.bottom > b.bottom + 0.5;
  })).length);
  check(cardOverflow === 0, '카드 안 글·칸이 카드 밖으로 안 나감');
  await shot(page, 'stats-feed');
  await page.click('#statsTabs [data-metric="diaper"]');
  check((await page.$$eval('#statsChart .card .badge .ico-poo', (v) => v.length)) === 7, '기저귀 탭: 카드마다 💩 칸');
  check((await text(page, '#statsLegend')) === '숫자 = 전체 ·  = 대변 있음', '기저귀 탭: 읽는 법');
  await shot(page, 'stats-diaper');
  await page.click('#statsTabs [data-metric="sleep"]');
  check((await page.$$eval('#statsChart .card .badge', (v) => v[0].textContent)).startsWith('낮'), '잠 탭: 낮잠 칸');
  check((await text(page, '#statsFoot')).includes('낮잠') && (await text(page, '#statsFoot')).includes('밤잠'), '잠 평균: 낮잠·밤잠');
  await shot(page, 'stats-sleep');
  await page.evaluate(() => document.body.classList.remove('light'));
  await shot(page, 'stats-sleep-dark');
  await page.evaluate(() => document.body.classList.add('light'));

  await page.clock.runFor(65000);
  check(await pageNow() === 'Main', '1분 동안 안 만지면 대시보드로');
  await dot(4);
  await page.clock.runFor(300);
  check(await pageNow() === 'Stats', '넷째 점을 누르면 통계');
  await page.click('#diaperBtn');
  check(await pageNow() === 'Main' && await page.isVisible('#diaperSheet'), '다른 쪽에서 큰 버튼 누르면 대시보드로 돌아와 창이 열림');
  await swipe(560, 200, 200);
  check(await pageNow() === 'Main', '창이 열려 있으면 밀어도 안 넘김');
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
  check(!(await page.isHidden('#night')), '밤에는 검은 화면');
  check(!(await page.evaluate(() => document.body.classList.contains('light'))), '밤에는 어두운 화면');
  const nightText = await page.$eval('#nightText', (n) => ({ t: n.textContent, r: n.getBoundingClientRect(), s: document.querySelector('#stage').getBoundingClientRect() }));
  check(/^수유 후\d+시간\d*분?지남/.test(nightText.t) && nightText.t.includes('마지막 수유') && nightText.t.includes('지금'), `밤 화면: "수유 후 … 지남"·마지막 수유·지금 (${nightText.t})`);
  check(nightText.r.right <= nightText.s.right + 0.5 && nightText.r.bottom <= nightText.s.bottom + 0.5, '밤 화면 글이 화면 안');
  await shot(page, 'night');
  // 자는 중이면 잔 시간이 가장 크게
  await page.evaluate(() => {
    const all = JSON.parse(localStorage.getItem('albam.demo.events'));
    all.push({ id: 'night-sleep', kind: 'sleep', occurred_at: new Date(Date.now() - 113 * 60000).toISOString(), ended_at: null, detail: {} });
    localStorage.setItem('albam.demo.events', JSON.stringify(all));
  });
  await page.reload();
  await page.clock.runFor(2000);
  const sleepText = await page.$eval('#nightText', (n) => ({ main: n.querySelector('.nightMain').textContent, box: n.querySelector('.nightBox').textContent, r: n.getBoundingClientRect(), s: document.querySelector('#stage').getBoundingClientRect() }));
  check(sleepText.main === '1시간53분째자는 중' && sleepText.box.startsWith('수유 후') && sleepText.box.endsWith('지남'), `자는 중: "1시간 53분째 자는 중" 크게, 아래에 수유 후 (${sleepText.main} / ${sleepText.box})`);
  check(sleepText.r.right <= sleepText.s.right + 0.5 && sleepText.r.bottom <= sleepText.s.bottom + 0.5, '자는 중 밤 화면 글이 화면 안');
  await shot(page, 'night-sleeping');
  // 가장 긴 경우: 12시간 넘게 자는 중, 수유 후 13시간도 화면 안
  await page.evaluate(() => {
    const all = JSON.parse(localStorage.getItem('albam.demo.events'));
    all.find((e) => e.id === 'night-sleep').occurred_at = new Date(Date.now() - (12 * 60 + 59) * 60000).toISOString();
    for (const e of all.filter((x) => x.kind === 'feed')) e.occurred_at = new Date(Date.now() - (13 * 60 + 58) * 60000).toISOString();
    localStorage.setItem('albam.demo.events', JSON.stringify(all));
  });
  await page.reload();
  await page.clock.runFor(70000);
  const longest = await page.$eval('#nightText', (n) => { const r = n.getBoundingClientRect(); const s = document.querySelector('#stage').getBoundingClientRect(); return { w: r.width, inside: r.left >= s.left - 0.5 && r.right <= s.right + 0.5 && r.bottom <= s.bottom + 0.5 }; });
  check(longest.inside, `가장 긴 밤 화면 글도 화면 안(폭 ${Math.round(longest.w)})`);
  await shot(page, 'night-longest');
  await page.touchscreen.tap(300, 200);
  await page.clock.runFor(1000);
  check(await page.isHidden('#night'), '터치하면 밝아짐');
  await shot(page, 'night-wake');
  await page.clock.runFor(31000);
  check(!(await page.isHidden('#night')), '30초 뒤 다시 어두워짐');
  await page.clock.runFor(3 * 60000);
  check((await page.evaluate(() => document.querySelector('#shift').style.transform)) !== '', '몇 분마다 화면 위치 이동');
}

// [+] 더보기: 체온(숫자 ±), 목욕(시작~끝 + 메모)
async function moreFlow(browser, base) {
  const page = await (await browser.newContext(DEVICE)).newPage();
  const errors = [];
  page.on('pageerror', (e) => errors.push(String(e)));
  await page.clock.install({ time: DAYTIME });
  await page.goto(`${base}?demo`);
  await page.evaluate(() => localStorage.clear());
  await page.reload();
  await page.clock.runFor(800);
  await page.click('#lateBtn');
  const labels = await page.$$eval('#moreGrid button', (b) => b.map((x) => x.textContent));
  check(['목욕', '체온', '투약', '체중', '키', '메모', '터미타임', '놀이', '병원', '기타'].every((l) => labels.includes(l)) && !labels.includes('수유'),
    `더보기 창에 종류 버튼 ${labels.join(' ')}`);
  check((await curvedEdgeOffenders(page, '#moreSheet h2, #moreSheet button')).length === 0, '더보기 창: 위·아래 곡면에 글·버튼 없음');
  await shot(page, 'more');
  await page.click('#moreGrid button:text-is("체온")');
  check(await text(page, '#lateTitle') === '체온 넣기' && await text(page, '#lateDetail .valueView') === '36.8°C', '체온 넣기: 처음 값 36.8°C');
  await page.click('#lateDetail .stepBtn:text-is("+1.0")');
  await page.click('#lateDetail .stepBtn:text-is("+0.1")');
  check(await text(page, '#lateDetail .valueView') === '37.9°C', `± 버튼으로 37.9°C (${await text(page, '#lateDetail .valueView')})`);
  const fits = await page.$eval('#lateDetail', (r) => r.scrollWidth <= r.clientWidth + 0.5);
  check(fits, '체온 줄이 창 안에 들어감');
  await shot(page, 'more-temperature');
  await page.click('#lateSave');
  await page.waitForTimeout(400);
  check((await text(page, '#undoText')).startsWith('체온 37.9°C'), `저장: ${await text(page, '#undoText')}`);
  await page.click('#undoMsg');
  await page.click('#lateBtn');
  await page.click('#moreGrid button:text-is("목욕")');
  check(await page.isVisible('#late-end') || await page.isVisible('#lateFeedEnd'), '목욕: 끝 시각이 있음');
  await page.fill('#lateMemo', '보습로션');
  await shot(page, 'more-bath');
  await page.click('#lateSave');
  await page.waitForTimeout(400);
  check((await text(page, '#undoText')).startsWith('목욕 · 10분 · 보습로션'), `목욕 저장: ${await text(page, '#undoText')}`);
  await page.click('#undoMsg');
  const saved = await page.evaluate(() => JSON.parse(localStorage.getItem('albam.demo.events')).filter((e) => !['feed', 'diaper', 'sleep'].includes(e.kind)).map((e) => [e.kind, e.value_num, e.detail?.memo || '']));
  check(JSON.stringify(saved) === JSON.stringify([['temperature', 37.9, ''], ['bath', null, '보습로션']]), `미리 보기에 저장 ${JSON.stringify(saved)}`);
  await page.click('#lateBtn');
  await page.click('#moreToday');
  await page.clock.runFor(800);
  const rows = await page.$$eval('#recentList .dayRow', (r) => r.map((x) => x.textContent));
  check(rows.some((r) => r.includes('체온 37.9°C')) && rows.some((r) => r.includes('목욕 · 10분 · 보습로션')), `오늘 기록에 보임 ${rows.join(' / ')}`);
  await page.click('#recentList .dayRow:has-text("체온")');
  check(await text(page, '#lateTitle') === '기록 고치기 · 체온' && await text(page, '#lateDetail .valueView') === '37.9°C', '체온 고치기 창: 값 그대로');
  await page.click('#lateDetail .stepBtn:text-is("-0.1")');
  await page.click('#lateSave');
  await page.waitForTimeout(400);
  const after = await page.evaluate(() => JSON.parse(localStorage.getItem('albam.demo.events')).find((e) => e.kind === 'temperature').value_num);
  check(after === 37.8, `고친 값 37.8 (${after})`);
  check(errors.length === 0, `페이지 오류 없음 ${errors.join(' ')}`);
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
  check((await text(page, '#today')).startsWith('오늘1회'), '요약 다시 받음');
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
  check((await text(page, '#today')).startsWith('오늘1회'), '갱신 뒤 요약');
  check(errors.length === 0, `페이지 오류 없음 ${errors.join(' ')}`);
}

const server = await serve();
const base = `http://localhost:${server.address().port}/albam/`;
const browser = await chromium.launch();
try {
  console.log('# 미리 보기'); await demoFlow(browser, base);
  console.log('# 수유 걸린 시간'); await feedTimerFlow(browser, base);
  console.log('# 통계 쪽'); await statsFlow(browser, base);
  console.log('# 긴 글'); await longTextFlow(browser, base);
  console.log('# 미리 보기 오프라인'); await demoOfflineFlow(browser, base);
  console.log('# 밤 화면'); await nightFlow(browser, base);
  console.log('# 더보기'); await moreFlow(browser, base);
  console.log('# Supabase(가짜)'); await supabaseFlow(browser, base);
} finally {
  await browser.close();
  server.close();
}
console.log(failures ? `\n${failures}개 실패` : '\n모두 통과');
process.exit(failures ? 1 : 0);
