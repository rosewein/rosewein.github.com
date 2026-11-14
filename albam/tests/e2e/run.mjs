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

/** 대시보드 큰 기록 버튼 하나의 글: "이름|지난 시간|세부" */
const card = (sel) => pageRef.$eval(sel, (c) => [...c.querySelectorAll('.rLbl, .rBig, .rSub')].map((x) => x.getAttribute('aria-label') ?? x.textContent).join('|'));
let pageRef;

/** 대시보드 배치: 서로 안 겹침, 화면 안, 글 안 넘침, 칸과 버튼 열이 같음 */
async function dashboardLayout(page, tag) {
  const bad = await page.evaluate(() => {
    const r = (sel) => document.querySelector(sel).getBoundingClientRect();
    const stage = r('#stage');
    const boxes = ['#corner', '#ageLine', '#bubble', '#micBtn', '#feedBtn', '#diaperBtn', '#sleepBtn', '#lateBtn', '#pageDots'].map((s) => [s, r(s)]);
    const out = [];
    boxes.forEach(([a, A], i) => boxes.slice(i + 1).forEach(([b, B]) => {
      if (A.right > B.left + 0.5 && B.right > A.left + 0.5 && A.bottom > B.top + 0.5 && B.bottom > A.top + 0.5) out.push(`${a}/${b} 겹침`);
    }));
    boxes.forEach(([a, A]) => { if (A.left < stage.left - 0.5 || A.right > stage.right + 0.5) out.push(`${a} 화면 밖`); });
    for (const x of document.querySelectorAll('#bubble > div, .rec > span, #actions button')) {
      if (x.scrollWidth > x.clientWidth + 1) out.push(`${x.parentElement.id}>${x.id || x.className} 넘침`);
    }
    // 알밤의 보이는 칸(그림 96 중 오른쪽 90까지)이 말풍선 꼬리(말풍선 왼쪽 8 바깥)에 닿지 않게
    const a = r('#albam');
    if (a.left + a.width * (90 / 96) > r('#bubble').left - a.width * (8 / 96)) out.push('알밤/말풍선 꼬리 겹침');
    return out;
  });
  check(bad.length === 0, `대시보드 배치(${tag}): 겹침·넘침 없음 ${bad.join(', ')}`);
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
  pageRef = page;

  check((await page.evaluate(() => document.querySelector('#stage').style.zoom)) === '2', 'S10 에서 6배(기기 화소) = CSS zoom 2');
  const label = (sel) => page.getAttribute(sel, 'aria-label');
  // 미리 보기 기록: 수유 11:25(2시간 35분), 기저귀 12:50 소변, 잠 09:00~10:40(깬 지 3시간 20분 > 기준 2시간)
  check(await text(page, '#bubbleText') === '졸려요…' && await label('#elapsed') === '깬 지 3시간 20분' && await text(page, '#bubbleLabel') === '깬 시각 10:40',
    `말풍선: 가장 급한 항목 하나(깬 지 200분/120분 > 수유 155분/180분) "${await text(page, '#bubble')}"`);
  const isUrgent = (sel) => page.$eval(sel, (x) => x.classList.contains('urgent'));
  check(await isUrgent('#bubble') && await isUrgent('#sleepBtn') && !(await isUrgent('#feedBtn')) && !(await isUrgent('#diaperBtn')), '빨강은 말풍선과 그 항목 칸에만');
  check(await text(page, '#corner') === '2026년 11월 6일 금요일14:00' && await text(page, '#ageLine') === 'D+142 · 4개월 20일 · 교정 3개월 28일', `구석: 날짜·요일·시각 / 나이 줄 ${await text(page, '#corner')} / ${await text(page, '#ageLine')}`);
  check(await page.$eval('#ageLine', (a) => a.getBoundingClientRect().top) > await page.$eval('#clock', (c) => c.getBoundingClientRect().bottom) - 0.5, 'D+ 는 시각 아랫줄');
  
  check(await card('#feedBtn') === '수유|2시간 35분|11:25 · 200ml', `수유 버튼 ${await card('#feedBtn')}`);
  check(await card('#diaperBtn') === '기저귀|1시간 10분|12:50 · 소변', `기저귀 버튼 ${await card('#diaperBtn')}`);
  check(await card('#sleepBtn') === '잠· 깬 지|3시간 20분|09:00~10:40', `잠 버튼 ${await card('#sleepBtn')}`);
  check(await text(page, '#today') === '오늘 3회 · 570ml' && await text(page, '#demoNote') === '미리 보기', '오늘 합계·미리 보기는 타임라인 머리줄로 옮김');
  check(await text(page, '#net') === '', '구석 연결 표시는 문제 있을 때만');
  await dashboardLayout(page, 'S10');
  const box = (sel) => page.$eval(sel, (b) => { const r = b.getBoundingClientRect(); return { w: r.width, h: r.height, top: r.top }; });
  const [feed, diaper, sleepB, late, mic] = [await box('#feedBtn'), await box('#diaperBtn'), await box('#sleepBtn'), await box('#lateBtn'), await box('#micBtn')];
  check(feed.w === diaper.w && diaper.w === sleepB.w && feed.h === diaper.h && feed.h === sleepB.h && feed.top === sleepB.top && feed.h > late.h * 1.5, `수유·기저귀·잠: 상태를 담은 같은 크기 큰 버튼 ${JSON.stringify(feed)}`);
  check(late.w < feed.w / 2 && mic.w === late.w && mic.top < late.top && Math.abs(late.top + late.h - feed.top - feed.h) < 0.5, '+ 는 좁게 버튼 아래 끝에 맞춤, 마이크는 + 위에 작게');
  check((await text(page, '#micBtn')) === '' && (await text(page, '#lateBtn')) === '' && (await page.getAttribute('#micBtn', 'aria-label')) === '호출어 꺼짐(누르면 켬)'
    && (await page.getAttribute('#lateBtn', 'aria-label')).startsWith('더보기'), '아이콘 버튼에 이름(화면 낭독용)');
  check((await text(page, '#sleepBtnText')) === '잠', '[잠] 버튼 글');
  const curved = await curvedEdgeOffenders(page, '#corner, #ageLine, #bubble, #actions button, #micBtn, #pageDots .dot');
  await sleepFlow(page);
  check(curved.length === 0, `위·아래 곡면(8px)에 글·버튼 없음 ${curved.join(' ')}`);
  const dotsMid = await page.$eval('#pageDots', (d) => { const s = document.querySelector('#stage').getBoundingClientRect(); const r = d.getBoundingClientRect(); return Math.abs((r.left + r.right) / 2 - (s.left + s.right) / 2); });
  check(dotsMid < 1, `쪽 점은 화면 가운데 (어긋남 ${dotsMid.toFixed(1)})`);

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
  check((await card('#feedBtn')).includes('230ml'), '230ml(브레짜 210) 로 저장');
  check(await page.getAttribute('#elapsed', 'aria-label') === '방금', '저장하면 상태 칸이 바로 바뀜(방금)');
  check(await page.isVisible('#micBtn'), '저장 알림 동안에도 마이크(호출어)는 보임');
  check(await text(page, '#today') === '오늘 4회 · 800ml', '오늘 횟수 증가(예시 3회 + 1)');
  await shot(page, 'saved');

  await page.click('#undoMsg');
  await page.click('#feedBtn');
  await page.click('#feedSave');
  await page.waitForSelector('#confirmSheet:not(.hidden)');
  check(true, '10분 안 같은 종류는 확인을 물음');
  await shot(page, 'confirm');
  await page.click('#confirmNo');
  check(await text(page, '#notice') === '안 넣었어요' && await page.isVisible('#notice'), '결과 알림은 아래 막대에("안 넣었어요")');
  const bubbleNow = await text(page, '#bubbleText');
  check(['고마워요!', '배고파요…', '졸려요…', '기분 좋아요', '쿨쿨'].includes(bubbleNow), `말풍선에는 알밤 말만 ("${bubbleNow}")`);

  await page.click('#diaperBtn');
  await page.click('#diaperSheet [data-type="poo"]');
  await page.waitForSelector('#undo:not(.hidden)');
  check((await card('#diaperBtn')).includes('대변'), '기저귀 저장');
  await page.click('#undoBtn');
  await page.waitForTimeout(300);
  check((await card('#diaperBtn')).includes('소변'), '취소하면 이전 기록으로');
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
  check((await text(page, '#feedBtn .rSub')).startsWith('14:00'), '3시간 전 기록은 마지막 수유를 바꾸지 않음');
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
  check(await page.getAttribute('#sleepBtn', 'aria-label') === '깼어요' && (await text(page, '#sleepBtnText')) === '깼어요', '자는 중이면 버튼이 "깼어요"');
  await page.click('#undoMsg');
  await page.evaluate(() => {   // 1시간 20분 전에 잠든 것으로
    const all = JSON.parse(localStorage.getItem('albam.demo.events'));
    all.find((e) => e.kind === 'sleep' && !e.ended_at).occurred_at = new Date(Date.now() - 80 * 60000).toISOString();
    localStorage.setItem('albam.demo.events', JSON.stringify(all));
  });
  await page.reload();
  await page.waitForTimeout(600);
  check(await text(page, '#bubbleText') === '쿨쿨' && await page.getAttribute('#elapsed', 'aria-label') === '잠든 지 1시간 20분' && await text(page, '#bubbleLabel') === '잠든 시각 12:40', `말풍선에 잔 시간(${await text(page, '#bubble')})`);
  check(await card('#sleepBtn') === '깼어요|1시간 20분째|12:40~', `잠 버튼: 자는 중 ${await card('#sleepBtn')}`);
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
  check(await text(page, '#bubbleText') === '냠냠' && await page.getAttribute('#elapsed', 'aria-label') === '먹는 중 12분', `말풍선에 먹은 시간 (${await text(page, '#bubble')})`);
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
  const nextLine = await text(page, '#bigNext');
  check(nextLine === '', `시계 쪽: 20일 남은 일정은 아직 안 띄움 (${nextLine})`);
  {
    // 이틀 전부터: 시계 쪽 맨 아랫줄과 대시보드 나이 줄 자리
    const p2 = await (await browser.newContext(DEVICE)).newPage();
    await p2.clock.install({ time: DAYTIME });
    await p2.goto(`${base}?demo&appt=2`);
    await p2.clock.runFor(800);
    await p2.waitForTimeout(100);
    await p2.clock.runFor(800);
    check(await text(p2, '#ageLine') === '예방접종 D-2 · 헥사심 3차 외 3', `대시보드: 이틀 전부터 나이 줄 자리에 일정 (${await text(p2, '#ageLine')})`);
    check(await p2.$eval('#ageLine', (a) => a.getBoundingClientRect().top) > await p2.$eval('#clock', (c) => c.getBoundingClientRect().bottom) - 0.5, '대시보드 일정 줄은 시각 아랫줄');
    await shot(p2, 'dashboard-appointment');
    await p2.evaluate(() => document.querySelector('#pageDots .dot').click());
    await p2.clock.runFor(800);
    const line2 = await text(p2, '#bigNext');
    check(/예방접종 D-2 · 헥사심 3차 외 3$/.test(line2), `시계 쪽: 이틀 전부터 가까운 일정 (${line2})`);
    await shot(p2, 'clock-appointment');
    await p2.close();
  }
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
  pageRef = page;
  check(await text(page, '#bubbleText') === '배고파요…' && await page.getAttribute('#elapsed', 'aria-label') === '먹은 지 12시간 35분', '10시간 넘어도 분까지(큰 글씨), 수유가 가장 급함');
  check(await card('#diaperBtn') === '기저귀|11시간 59분|02:01 · 소+대', `기저귀 버튼 소+대 ${await card('#diaperBtn')}`);
  await dashboardLayout(page, '긴 글');
  await shot(page, 'long');
  // 대변이 어제(26시간 전): 시각만 두면 오늘 아침처럼 보이므로 날을 붙인다
  await page.evaluate(() => {
    const ago = (m) => new Date(Date.now() - m * 60000).toISOString();
    localStorage.setItem('albam.demo.events', JSON.stringify([
      { id: 'a', kind: 'feed', occurred_at: ago(60), amount_ml: 160, detail: {} },
      { id: 'b', kind: 'diaper', occurred_at: ago(50), detail: { type: 'pee' } },
      { id: 'c', kind: 'diaper', occurred_at: ago(26 * 60), detail: { type: 'poo' } },
    ]));
  });
  await page.reload();
  await page.waitForTimeout(500);
  check(await text(page, '#diaperBtn .rSub') === '13:10 · 대 어제 12:00', `어제 대변은 '어제' 붙임 ${await text(page, '#diaperBtn .rSub')}`);
  await dashboardLayout(page, '어제 대변');
  // P4 7인치(1024x600) 비율: 높이 180 기준 가로 307
  await page.goto(`${base}?demo&w=307`);
  await page.waitForTimeout(500);
  check(await page.$eval('#stage', (s) => s.getBoundingClientRect().width / (parseFloat(s.style.zoom) || 1)) === 307 && await page.$eval('#stage', (s) => s.classList.contains('narrow')), 'P4 비율 미리 보기(?w=307): 가로 307, 좁은 화면');
  check(await text(page, '#today2') === '11월 6일 금요일', `P4: 날짜는 해를 빼고 ${await text(page, '#today2')}`);
  await dashboardLayout(page, 'P4 긴 글');
  await shot(page, 'long-p4');
  // P4: 소변 뒤에 대변이 따로 있던 경우(기저귀 칸 세부가 가장 김)
  await page.evaluate(() => {
    const ago = (m) => new Date(Date.now() - m * 60000).toISOString();
    localStorage.setItem('albam.demo.events', JSON.stringify([
      { id: 'a', kind: 'feed', occurred_at: ago(12 * 60 + 35), amount_ml: 160, detail: {} },
      { id: 'b', kind: 'diaper', occurred_at: ago(50), detail: { type: 'pee' } },
      { id: 'c', kind: 'diaper', occurred_at: ago(300), detail: { type: 'poo' } },
      { id: 'd', kind: 'sleep', occurred_at: ago(12 * 60), ended_at: ago(11 * 60 + 1), detail: {} },
    ]));
  });
  await page.reload();
  await page.waitForTimeout(500);
  check(await text(page, '#diaperBtn .rSub') === '13:10 · 대 09:00', `P4 기저귀 세부는 짧게 ${await text(page, '#diaperBtn .rSub')}`);
  // P4: 말풍선에서 가장 긴 앞말(기저귀 간 지 + 12시간 넘음)
  await page.evaluate(() => {
    const ago = (m) => new Date(Date.now() - m * 60000).toISOString();
    localStorage.setItem('albam.demo.events', JSON.stringify([
      { id: 'a', kind: 'feed', occurred_at: ago(60), amount_ml: 160, detail: {} },
      { id: 'b', kind: 'diaper', occurred_at: ago(12 * 60 + 35), detail: { type: 'pee' } },
    ]));
  });
  await page.reload();
  await page.waitForTimeout(500);
  check(await page.getAttribute('#elapsed', 'aria-label') === '기저귀 간 지 12시간 35분', `P4 말풍선 가장 긴 줄 ${await page.getAttribute('#elapsed', 'aria-label')}`);
  await dashboardLayout(page, 'P4 기저귀 간 지 12시간');
  await shot(page, 'longest-p4');
  await dashboardLayout(page, 'P4 대변 따로');
  await page.evaluate(() => {
    const ago = (m) => new Date(Date.now() - m * 60000).toISOString();
    localStorage.setItem('albam.demo.events', JSON.stringify([
      { id: 'a', kind: 'feed', occurred_at: ago(60), amount_ml: 160, detail: {} },
      { id: 'b', kind: 'diaper', occurred_at: ago(50), detail: { type: 'pee' } },
      { id: 'c', kind: 'diaper', occurred_at: ago(26 * 60), detail: { type: 'poo' } },
    ]));
  });
  await page.reload();
  await page.waitForTimeout(500);
  check(await text(page, '#diaperBtn .rSub') === '13:10 · 대 어제', `P4: 어제 대변은 날만 ${await text(page, '#diaperBtn .rSub')}`);
  await dashboardLayout(page, 'P4 어제 대변');
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
  check(await text(page, '#demoNote') === '미리 보기' && await text(page, '#net') === '', '미리 보기 표시(타임라인 머리줄)');

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
  check(await text(page, '#net') === '', '다시 연결되면 "대기" 사라짐');
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
  await page.touchscreen.tap(120, 100);   // 알밤 쪽(버튼이 아닌 곳)
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
  check(['산책', '목욕', '체온', '투약', '체중', '키', '메모', '터미타임', '놀이', '병원', '예방접종', '기타'].every((l) => labels.includes(l)) && !labels.includes('수유'),
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
  // 체중: 지난번 값(미리 보기 7.20kg)에서 시작하고 제목에 성장 백분위(기본 · 교정)
  await page.click('#lateSheet [data-close]');
  await page.click('#lateBtn');
  await page.click('#moreGrid button:text-is("체중")');
  check(await text(page, '#lateDetail .valueView') === '7.20kg', `체중 넣기: 지난번 값에서 시작 (${await text(page, '#lateDetail .valueView')})`);
  check(/^체중 넣기 · 백분위 \d+ · 교정 \d+$/.test(await text(page, '#lateTitle')), `체중 제목에 백분위 (${await text(page, '#lateTitle')})`);
  check(await page.$eval('#lateTitle', (h) => { const r = document.createRange(); r.selectNodeContents(h); return r.getBoundingClientRect().right; }) <= await page.$eval('#lateKindOther', (b) => b.getBoundingClientRect().left), '백분위 제목이 종류 버튼과 안 겹침');
  await shot(page, 'more-weight');
  await page.click('#lateSheet [data-close]');
  await page.click('#lateBtn');
  await page.click('#moreGrid button:text-is("체온")');
  await page.click('#lateDetail .stepBtn:text-is("+1.0")');
  await page.click('#lateDetail .stepBtn:text-is("+0.1")');
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
  check((await text(page, '#today')).startsWith('오늘 1회'), '요약 다시 받음');
  await page.click('#undoMsg');

  await fake.goOffline();
  await page.click('#diaperBtn');
  await page.click('#diaperSheet [data-type="poo"]');
  await page.waitForTimeout(400);
  check(fake.events.length === 1, '오프라인이면 보내지 않음');
  check((await text(page, '#net')) === '대기 1건', '"대기 1건" 표시');
  check((await text(page, '#diaperBtn')).includes('대변'), '못 보낸 기록도 상태 칸에 보임');
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
  check((await text(page, '#today')).startsWith('오늘 1회'), '갱신 뒤 요약');
  check(errors.length === 0, `페이지 오류 없음 ${errors.join(' ')}`);
}

/** 호출어: Vosk 결과(시험용 입구) → 확인 화면 → n초 뒤 저장 / 누르면 취소(시험 기록에 잘못으로) */
async function wakeFlow(browser, base) {
  const page = await (await browser.newContext(DEVICE)).newPage();
  const errors = [];
  page.on('pageerror', (e) => errors.push(String(e)));
  await page.clock.install({ time: DAYTIME });
  await page.goto(`${base}?demo`);
  await page.evaluate(() => localStorage.clear());
  await page.reload();
  await page.clock.runFor(800);
  check(!(await page.getAttribute('#micBtn', 'class')).includes('listening'), '호출어는 처음에 꺼짐');
  check(await page.$eval('#micBtn', (b) => { const r = b.getBoundingClientRect(); return document.elementFromPoint(r.x + r.width / 2, r.y + r.height / 2)?.closest('#micBtn') === b; }), '마이크 버튼을 누를 수 있음(버튼 줄에 가리지 않음)');
  const until = async (fn) => { for (let i = 0; i < 30 && !(await fn()); i += 1) { await page.clock.runFor(300); await page.waitForTimeout(50); } };
  const say = (words) => page.evaluate((w) => window.__albamWakeResult({ text: w.join(' '), result: w.map((word) => ({ word, conf: 1 })) }), words);

  await say(['알밤', '이', '기저귀']);
  await page.waitForSelector('#voiceSheet:not(.hidden)');
  check(await text(page, '#voiceLabel') === '기저귀 소변+대변' && (await text(page, '#voiceTitle')).includes('취소'), `확인 화면에 크게(${await text(page, '#voiceLabel')})`);
  await shot(page, 'wake-confirm');
  await say(['알밤', '이', '응아']);   // 확인 중에 들린 말은 넘김
  check(await text(page, '#voiceLabel') === '기저귀 소변+대변', '확인 중 다른 말은 넘김');
  await until(async () => page.isVisible('#undo'));
  check((await text(page, '#undoText')).startsWith('기저귀 소변+대변'), `n초 뒤 저장(${await text(page, '#undoText')})`);
  const saved = await page.evaluate(() => JSON.parse(localStorage.getItem('albam.demo.events')).find((e) => e.kind === 'diaper' && e.detail.type === 'both'));
  check(saved?.source === 'living_room_voice' && saved.voice_text === '알밤 이 기저귀', '음성 기록으로 남김(source·voice_text)');
  await page.click('#undoMsg').catch(() => {});
  await until(async () => !(await page.isVisible('#undo')));

  await say(['알밤', '이', '목욕', '했어']);
  await page.waitForSelector('#voiceSheet:not(.hidden)');
  check(await text(page, '#voiceLabel') === '목욕', '목욕');
  await page.click('#voiceCancel');
  check(await text(page, '#notice') === '안 넣었어요', '누르면 취소');
  const log = await page.evaluate(() => window.__albamVoiceLog || []);
  check(log.length === 3 && log.at(-1).kind === 'bath' && log.at(-1).wrong === true && log[0].wrong === false && log[0].device.endsWith('app'), `시험 기록: 취소는 잘못으로(${JSON.stringify(log.map((r) => [r.kind, r.wrong]))})`);
  const baths = await page.evaluate(() => JSON.parse(localStorage.getItem('albam.demo.events')).filter((e) => e.kind === 'bath').length);
  check(baths === 0, '취소하면 저장 안 함');

  await say(['알밤', '이', '깼다']);
  check(await text(page, '#notice') === '자는 중이 아니에요' && !(await page.isVisible('#voiceSheet')), '안 자는데 "깼다"는 알림만');
  await page.click('#sleepBtn');
  await until(async () => (await text(page, '#sleepBtnText')) === '깼어요');
  await page.click('#undoMsg').catch(() => {});
  await until(async () => !(await page.isVisible('#undo')));
  await page.clock.runFor(60000);
  await say(['알밤', '이', '깼다']);
  await page.waitForSelector('#voiceSheet:not(.hidden)');
  check(await text(page, '#voiceLabel') === '잠 끝(깼어요)', '자는 중이면 "깼다"는 잠 끝');
  await until(async () => (await text(page, '#sleepBtnText')) === '잠');
  check(!(await page.isVisible('#voiceSheet')) && (await text(page, '#sleepBtnText')) === '잠', '잠 끝 저장 뒤 확인 창이 닫힘(2026-11-11 S10: 저장됐는데 창이 남음)');
  await say(['알밤', '이', '울고']);
  check(!(await page.isVisible('#voiceSheet')), '명령이 아닌 말은 넘김');
  check(errors.length === 0, `오류 없음 ${errors.join(' ')}`);
}

// ── 개인 폰 화면(m/): 세로 390x844 ──
const PHONE = { viewport: { width: 390, height: 844 }, deviceScaleFactor: 2, hasTouch: true, isMobile: true, timezoneId: 'Asia/Seoul' };
async function phoneFlow(browser, base) {
  const page = await (await browser.newContext(PHONE)).newPage();
  const errors = [];
  page.on('pageerror', (e) => errors.push(String(e)));
  await page.goto(`${base}m/?demo`);
  await page.evaluate(() => localStorage.clear());
  await page.reload();
  await page.waitForFunction(() => document.querySelector('#feedBtn')?.textContent.startsWith('수유'));
  const noOverflow = () => page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth);
  const small = () => page.evaluate(() => [...document.querySelectorAll('button')].filter((b) => b.offsetParent && b.getBoundingClientRect().height < 44).map((b) => b.textContent));
  check(await text(page, '#feedBtn') === '수유 200ml' && await text(page, '#feedLabel') === '수유 · 먹은 지', `수유 카드: ${await text(page, '#feedLabel')} / ${await text(page, '#feedBtn')}`);
  check(/^\d+시간 \d+분$/.test(await text(page, '#feedAgo')) && /· 200ml$/.test(await text(page, '#feedDetail')), `수유 지난 시간·마지막 기록 (${await text(page, '#feedAgo')} / ${await text(page, '#feedDetail')})`);
  check(await text(page, '#sleepBtn') === '잠들었어요' && /~/.test(await text(page, '#sleepDetail')), '잠 카드: 깬 지 + 잠들었어요');
  check(/D\+\d+ · \d+개월/.test(await text(page, '#age')), `나이 줄 (${await text(page, '#age')})`);
  const more = await page.$$eval('#moreGrid button', (b) => b.map((x) => x.textContent));
  check(more[0] === '산책' && more.includes('예방접종') && !more.includes('수유'), `더 넣기 버튼 ${more.join(' ')}`);
  await page.waitForFunction(() => !document.querySelector('#upcomingSec').hidden);
  check(/예방접종 · 헥사심 3차, 폐렴구균 3차, 로타텍 3차, 독감 1차D-20$/.test(await text(page, '#upcomingList')), `다가오는 일정은 미리부터 다 보임 (${await text(page, '#upcomingList')})`);
  check(await noOverflow(), '옆으로 넘치지 않음');
  check((await small()).length === 0, `누르는 것은 모두 44px 이상 ${(await small()).join(' ')}`);
  await shot(page, 'phone-home');

  // 수유에 붙이는 문구: 먹이기 전에 켜 두면 다음 수유에 붙는다
  const chips = () => page.$$eval('#feedChips .chip', (b) => b.map((x) => `${x.textContent}${x.classList.contains('on') ? '*' : ''}`).join(' '));
  await page.waitForFunction(() => document.querySelectorAll('#feedChips .chip').length === 3);
  check(await chips() === '유산균 비타민D +', `수유 문구 줄 (${await chips()})`);
  await page.click('#feedChips .chip:text-is("유산균")');
  check(await chips() === '유산균* 비타민D +', '먹이기 전에 눌러 켜 둠');

  // 수유: 한 번 눌러 먹이기 시작 → 다 먹음
  await page.click('#feedBtn');
  await page.waitForFunction(() => document.querySelector('#feedBtn').textContent === '다 먹음');
  await page.waitForFunction(() => document.querySelector('#feedChips .chip.on')?.textContent === '유산균');
  check(true, '켜 둔 문구가 그 수유에 붙음');
  // 먹이는 중에는 누르는 대로 그 수유에 붙고 떨어진다
  await page.click('#feedChips .chip:text-is("비타민D")');
  await page.waitForFunction(() => document.querySelectorAll('#feedChips .chip.on').length === 2);
  await page.click('#feedChips .chip:text-is("유산균")');
  await page.waitForFunction(() => document.querySelectorAll('#feedChips .chip.on').length === 1);
  check(await chips() === '유산균 비타민D* +', `먹이는 중에 붙이고 떼기 (${await chips()})`);
  const savedMemo = await page.evaluate(() => JSON.parse(localStorage.getItem('albam.demo.summary')).recent[0].detail.memo);
  check(savedMemo === '비타민D', `기록의 메모에 들어감 (${savedMemo})`);
  check(await text(page, '#noticeText') === '수유 200ml 저장됨' && /^취소 \d$/.test(await text(page, '#undoBtn')), `저장 알림과 취소 (${await text(page, '#noticeText')} / ${await text(page, '#undoBtn')})`);
  check(await text(page, '#feedLabel') === '수유 · 먹는 중' && !(await page.isVisible('#feedAmountBtn')), '먹이는 중: 버튼이 [다 먹음], 양 바꾸기는 숨김');
  await shot(page, 'phone-feeding');
  await page.click('#feedBtn');
  await page.waitForFunction(() => document.querySelector('#feedBtn').textContent === '수유 200ml');
  check(/^수유 200ml · \d+분 저장됨$/.test(await text(page, '#noticeText')), `다 먹음 (${await text(page, '#noticeText')})`);

  // 양 바꾸기: 이번 한 번만
  await page.click('#feedAmountBtn');
  await page.click('#feedSteps [data-step="machine"]');
  check(await text(page, '#feedBtn') === '수유 230ml' && await text(page, '#feedMachine') === '브레짜 210', `양 바꾸기 +30 (${await text(page, '#feedBtn')} / ${await text(page, '#feedMachine')})`);
  await page.click('#feedSteps [data-step="-10"]');
  check(await text(page, '#feedBtn') === '수유 220ml' && await text(page, '#feedMachine') === '브레짜 칸 아님', '±10 은 브레짜 칸 아님');
  check(await noOverflow(), '양 바꾸기 줄도 옆으로 안 넘침');
  await page.click('#feedAmountBtn');
  check(await text(page, '#feedBtn') === '수유 200ml', '양 바꾸기를 닫으면 원래 양');

  // 방금 넣은 수유와 비슷한 기록: 확인 창
  await page.click('#feedBtn');
  await page.waitForSelector('#confirm[open]');
  check(/비슷한 기록이 이미 있어요/.test(await text(page, '#confirmText')), '10분 안 같은 종류는 확인 창');
  await page.click('#confirmNo');
  check(await text(page, '#noticeText') === '안 넣었어요', '안 넣기');

  // 기저귀: 저장 → 취소
  await page.click('[data-diaper="poo"]');
  await page.waitForFunction(() => document.querySelector('#noticeText').textContent === '기저귀 대변 저장됨');
  check(await text(page, '#diaperAgo') === '방금' && /대변$/.test(await text(page, '#diaperDetail')), `기저귀 카드가 바로 바뀜 (${await text(page, '#diaperAgo')} / ${await text(page, '#diaperDetail')})`);
  await page.click('#undoBtn');
  await page.waitForFunction(() => document.querySelector('#noticeText').textContent === '취소했어요');
  await page.waitForFunction(() => document.querySelector('#diaperAgo').textContent !== '방금');
  check(/소변$/.test(await text(page, '#diaperDetail')), '취소하면 앞 기록으로 돌아옴');

  // 잠: 잠들었어요 → 깼어요
  await page.click('#sleepBtn');
  await page.waitForFunction(() => document.querySelector('#sleepBtn').textContent === '깼어요');
  check(await text(page, '#sleepLabel') === '잠 · 자는 중', '자는 중');
  await page.click('#sleepBtn');
  await page.waitForFunction(() => document.querySelector('#sleepBtn').textContent === '잠들었어요');
  check(/^잠 \d+분 저장됨$/.test(await text(page, '#noticeText')), `깼어요 (${await text(page, '#noticeText')})`);

  // 더 넣기: 체중은 지난번 값에서 + 백분위, 산책은 시작~끝, 메모는 글이 꼭
  await page.click('#moreGrid button:text-is("체중")');
  check(await page.inputValue('#entryValue') === '7.20' && /^백분위 \d+ · 교정 \d+$/.test(await text(page, '#entryPercentile')), `체중: 지난번 값 + 백분위 (${await page.inputValue('#entryValue')} / ${await text(page, '#entryPercentile')})`);
  await page.click('#entry [data-n="10"]');
  await page.click('#entry [data-n="1"]');
  check(await page.inputValue('#entryValue') === '7.31', `± 버튼 (${await page.inputValue('#entryValue')})`);
  check(await noOverflow(), '체중 창이 옆으로 안 넘침');
  await shot(page, 'phone-weight');
  await page.click('#entrySave');
  await page.waitForFunction(() => document.querySelector('#noticeText').textContent.startsWith('체중 7.31kg'));
  await page.click('#moreGrid button:text-is("체중")');
  check(await page.inputValue('#entryValue') === '7.31', '다음에 열면 방금 넣은 값에서 시작');
  await page.click('#entryClose');
  await page.click('#moreGrid button:text-is("산책")');
  check(await page.isVisible('#entryEnd') && await text(page, '#entryStartLabel') === '시작' && !(await page.isVisible('#entryValue')), '산책: 시작·끝, 숫자 칸 없음');
  await page.click('#entrySave');
  await page.waitForFunction(() => document.querySelector('#noticeText').textContent.startsWith('산책 · 10분'));
  // 목욕: 문구를 눌러 메모에 넣기, 폰에서 문구 더하기·지우기
  await page.click('#moreGrid button:text-is("목욕")');
  await page.click('#entryChips .chip:text-is("보습로션")');
  check(await page.inputValue('#entryMemo') === '보습로션', '문구를 누르면 메모 칸에 들어감');
  await page.click('#entryChips .chip.add');
  check(await text(page, '#phrasesTitle') === '목욕 문구' && /보습로션/.test(await text(page, '#phrasesList')), '문구 창: 목욕 문구 목록');
  await page.fill('#phraseText', '머리 감김');
  await page.click('#phrasesForm button[type=submit]');
  await page.waitForFunction(() => /머리 감김/.test(document.querySelector('#phrasesList').textContent));
  check(await noOverflow(), '문구 창이 옆으로 안 넘침');
  await shot(page, 'phone-phrases');
  await page.click('#phrasesList .phraseRow:first-child button');
  await page.waitForFunction(() => !/보습로션/.test(document.querySelector('#phrasesList').textContent));
  await page.click('#phrasesClose');
  const bathChips = await page.$$eval('#entryChips .chip', (b) => b.map((x) => x.textContent).join(' '));
  check(bathChips === '머리 감김 +', `더한 문구가 버튼으로, 지운 문구는 사라짐 (${bathChips})`);
  check(await page.inputValue('#entryMemo') === '보습로션', '문구를 지워도 이미 넣은 메모는 그대로');
  await page.click('#entryChips .chip:text-is("머리 감김")');
  await shot(page, 'phone-bath');
  await page.click('#entrySave');
  await page.waitForFunction(() => document.querySelector('#noticeText').textContent.startsWith('목욕 · 10분 · 보습로션 · 머리 감김'));
  check(true, '목욕에 문구가 붙어 저장됨');
  await page.click('#moreGrid button:text-is("메모")');
  await page.click('#entrySave');
  check(await text(page, '#entryMsg') === '메모를 써 주세요' && await page.isVisible('#entry'), '메모는 글이 비면 저장 안 함');
  await page.fill('#entryMemo', '손톱 깎음');
  await page.click('#entrySave');
  await page.waitForFunction(() => document.querySelector('#noticeText').textContent.startsWith('메모 · 손톱 깎음'));

  // 기록 쪽: 오늘 목록, 눌러서 고치기·지우기, 날짜 넘기기
  await page.click('#tabs [data-view="records"]');
  await page.waitForFunction(() => document.querySelectorAll('#dayList .rec').length > 3);
  check(await text(page, '#daySub') === '오늘' && /^수유 \d+회 \d+ml · 기저귀 \d+회/.test(await text(page, '#daySummary')), `기록 쪽 머리 (${await text(page, '#daySub')} / ${await text(page, '#daySummary')})`);
  const rows = () => page.$$eval('#dayList .rec', (r) => r.map((x) => x.querySelector('.body').textContent));
  check((await rows()).includes('메모 손톱 깎음') && (await rows()).includes('목욕 10분 · 보습로션 · 머리 감김') && (await rows()).includes('체중 7.31kg'), `오늘 넣은 기록이 목록에 (${(await rows()).slice(0, 4).join(' | ')})`);
  const times = await page.$$eval('#dayList .rec .time', (t) => t.map((x) => x.textContent.replace('전날 ', '').slice(0, 5)));
  check(times.every((t, i) => i === 0 || t <= times[i - 1] || /전날/.test(t)), `시각 순, 최근 것이 위 (${times.slice(0, 5).join(' ')})`);
  check(!(await page.isEnabled('#dayNext')), '오늘에서는 다음날로 못 감');
  check(await noOverflow() && (await small()).length === 0, `기록 쪽: 안 넘치고 누르는 것은 44px 이상 ${(await small()).join(' ')}`);
  await shot(page, 'phone-records');
  // 지난 수유에 문구 붙이기 + 양 고치기
  await page.locator('#dayList .rec', { hasText: /수유 200ml · \d+분 · 비타민D›/ }).click();
  check(await text(page, '#entryTitle') === '기록 고치기 · 수유' && await page.inputValue('#entryAmount') === '200' && await page.inputValue('#entryMemo') === '비타민D', '수유 고치기 창: 양·메모가 채워짐');
  check(await page.isChecked('#entryHasEnd') && await page.isVisible('#entryDelete'), '끝 시각이 켜져 있고 [지우기]가 있음');
  check(await page.evaluate(() => document.activeElement?.id) === 'entryTitle', '창이 열릴 때 시각 칸에 초점이 가지 않음(아이폰에서 달력이 바로 뜨던 것)');
  const widths = await page.$$eval('#entryStart, #entryEnd, #entryAmount, #entryMemo', (els) => els.map((e) => Math.round(e.getBoundingClientRect().width)));
  check(new Set(widths).size === 1 && await page.$eval('#entryForm', (f) => f.scrollWidth <= f.clientWidth), `시각·양·메모 칸 폭이 같고 창 안에 들어감 (${widths.join(' ')})`);
  await page.fill('#entryAmount', '230');
  await page.click('#entryChips .chip:text-is("유산균")');
  await shot(page, 'phone-edit-feed');
  await page.click('#entrySave');
  await page.waitForFunction(() => document.querySelector('#noticeText').textContent === '고쳤어요 · 수유');
  await page.waitForFunction(() => [...document.querySelectorAll('#dayList .rec .body')].some((b) => /^수유 230ml · \d+분 · 비타민D · 유산균$/.test(b.textContent)));
  check(true, '고친 양과 붙인 문구가 목록에 보임');
  // 기저귀 종류 고치기
  await page.locator('#dayList .rec', { hasText: /기저귀 소변›/ }).first().click();
  await page.click('#entryDiaper [data-type="both"]');
  await page.click('#entrySave');
  await page.waitForFunction(() => [...document.querySelectorAll('#dayList .rec .body')].some((b) => b.textContent === '기저귀 소변+대변'));
  check(true, '기저귀 종류 고침');
  // 지우기는 두 번
  const before = (await rows()).length;
  await page.locator('#dayList .rec', { hasText: '메모 손톱 깎음' }).click();
  await page.click('#entryDelete');
  check(await text(page, '#entryDelete') === '한 번 더 누르면 지워요' && await page.isVisible('#entry'), '지우기 한 번: 다시 묻기');
  await page.click('#entryDelete');
  await page.waitForFunction(() => document.querySelector('#noticeText').textContent === '지웠어요 · 메모');
  await page.waitForFunction((n) => document.querySelectorAll('#dayList .rec').length === n - 1, before);
  check(true, '두 번 누르면 지워짐');
  await page.click('#dayPrev');
  await page.waitForFunction(() => document.querySelector('#daySub').textContent === '어제');
  check(await page.isEnabled('#dayNext'), '어제로 넘김');
  await page.click('#dayNext');
  await page.waitForFunction(() => document.querySelector('#daySub').textContent === '오늘');
  // 날짜를 누르면 달력: 날짜 글 한가운데를 누르면 투명한 날짜 칸이 받는다
  const hit = await page.evaluate(() => { const r = document.querySelector('#dayTitle').getBoundingClientRect(); return document.elementFromPoint(r.left + r.width / 2, r.top + r.height / 2).id; });
  check(hit === 'dayPick', `날짜 글을 누르면 날짜 칸이 받음 (${hit})`);
  const weekAgo = await page.evaluate(() => { const d = new Date(); d.setDate(d.getDate() - 7); return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`; });
  await page.fill('#dayPick', weekAgo);
  await page.waitForFunction(() => document.querySelector('#daySub').textContent === '7일 전');
  check(await text(page, '#dayMsg') === '이 날은 기록이 없어요', '달력으로 고른 날로 감');
  // 통계 쪽: 날짜별 막대와 평균, 성장곡선
  await page.click('#tabs [data-view="stats"]');
  await page.waitForFunction(() => document.querySelectorAll('#statBars .bar').length === 8);
  check(/^\d+ml$/.test(await text(page, '#statHeadline')) && /^하루 [\d.]+회 · 지난 7일 평균\(오늘 빼고\)$/.test(await text(page, '#statSub')), `수유 통계 (${await text(page, '#statHeadline')} / ${await text(page, '#statSub')})`);
  check(await page.$$eval('#statBars .bar.today', (b) => b.length) === 1 && (await page.$$eval('#statCards .stat', (c) => c.length)) >= 2, '막대는 오늘까지(오늘은 따로 표시), 아래 칸들');
  check(await page.$eval('#statTabs', (t) => t.getBoundingClientRect().height) < 60 && await page.$eval('#statRange', (t) => t.getBoundingClientRect().height) < 60, '고르는 버튼은 한 줄로');
  await page.waitForFunction(() => document.querySelector('#notice').hidden, null, { timeout: 10000 });
  await shot(page, 'phone-stats');
  await page.click('#statRange [data-days="30"]');
  await page.waitForFunction(() => document.querySelectorAll('#statBars .bar').length === 31);
  check(await noOverflow(), '30일 막대도 옆으로 안 넘침');
  await page.click('#statTabs [data-metric="sleep"]');
  await page.waitForFunction(() => /시간$/.test(document.querySelector('#statHeadline').textContent));
  check(/밤잠/.test(await text(page, '#statCards')), `잠 통계 (${await text(page, '#statHeadline')})`);
  await page.click('#statTabs [data-metric="growth"]');
  await page.waitForFunction(() => document.querySelectorAll('#growthSvg .pct').length === 5);
  check(await page.$$eval('#growthSvg .dot.actual', (d) => d.length) === 2 && await page.$$eval('#growthSvg .dot.corrected', (d) => d.length) === 2, '성장곡선: 기본 나이 점과 교정 나이 점');
  check(/^7\.31kg$/.test(await text(page, '#growthLast .big')) && /기본 · \d+개월 \d+일백분위 \d+/.test(await text(page, '#growthLast')) && /교정 · \d+개월 \d+일백분위 \d+/.test(await text(page, '#growthLast')), `마지막 측정과 백분위 두 가지 (${await text(page, '#growthLast')})`);
  check(/지난번보다 \+0\.11kg/.test(await text(page, '#growthLast')), '지난번과의 차이');
  check(await noOverflow() && (await small()).length === 0, `통계 쪽: 안 넘치고 누르는 것은 44px 이상 ${(await small()).join(' ')}`);
  await page.evaluate(() => window.scrollTo(0, 0));
  await shot(page, 'phone-growth');
  await page.click('#growthKinds [data-kind="height"]');
  check(/^65\.0cm$/.test(await text(page, '#growthLast .big')), '키로 바꿈');
  // 막대를 누르면 그날 기록으로
  await page.click('#statTabs [data-metric="feed"]');
  await page.click('#statRange [data-days="7"]');
  await page.waitForFunction(() => document.querySelectorAll('#statBars .bar').length === 8);
  await page.click('#statBars .bar:nth-child(7)');
  await page.waitForFunction(() => document.querySelector('#daySub').textContent === '어제' && !document.querySelector('#viewRecords').hidden);
  check(await page.$eval('#tabs [data-view="records"]', (b) => b.classList.contains('on')), '막대를 누르면 그날 기록 쪽으로');
  await page.click('#tabs [data-view="home"]');
  check(await page.isVisible('#feedCard') && !(await page.isVisible('#dayList')), '입력 쪽으로 돌아옴');

  // 연결이 끊기면 쌓았다가 보낸다
  await page.context().setOffline(true);
  await page.click('[data-diaper="pee"]');
  await page.waitForFunction(() => /대기 1건/.test(document.querySelector('#net').textContent));
  check(await text(page, '#noticeText') === '기저귀 소변 (대기) 저장됨', `오프라인 저장 (${await text(page, '#noticeText')})`);
  await page.context().setOffline(false);
  await page.waitForFunction(() => document.querySelector('#net').hidden, null, { timeout: 30000 });
  check(true, '다시 연결되면 대기가 사라짐');
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
  console.log('# 호출어'); await wakeFlow(browser, base);
  console.log('# Supabase(가짜)'); await supabaseFlow(browser, base);
  console.log('# 개인 폰 화면'); await phoneFlow(browser, base);
} finally {
  await browser.close();
  server.close();
}
console.log(failures ? `\n${failures}개 실패` : '\n모두 통과');
process.exit(failures ? 1 : 0);
