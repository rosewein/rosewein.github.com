// 알밤보드 개인 폰 화면의 시작점. 거실 화면(../src/main.js)과 같은 통신 창구(../src/api)·같은 Supabase 함수를 쓴다.
// 캐릭터·밤 화면·번인 대비·호출어는 없다. 화면을 얇게: 계산은 서버 요약(care_summary)이 한다.
//
//   save(ev)       비슷한 기록이 있으면 확인 창 → 저장 → "○○ 저장됨 [취소 6]"
//   finishFeed()   먹이는 중인 수유에 끝(다 먹음)   wake()  자는 중인 잠에 끝(깼어요)
//
// 주소 끝에 ?demo 를 붙이면 가짜 데이터로 돈다(거실 화면의 미리 보기와 같은 기기 안 저장소를 쓴다).

import { loadConfig } from '../src/config.js';
import { createApi, AuthError, STORAGE } from '../src/api/index.js';
import { createDemoApi } from '../src/api/demo.js';
import { describeEvent, recordType } from '../src/domain.js';
import { formatClock, formatDuration } from '../src/time.js';
import { isDaylight } from '../src/sun.js';
import { createMeasures } from '../src/ui/measures.js';
import { createUpcoming } from '../src/ui/upcoming.js';
import { createNotice } from './notice.js';
import { createPhrases } from './phrases.js';
import { setupHome } from './home.js';
import { setupEntry } from './entry.js';
import { setupRecords } from './records.js';
import { setupStats } from './stats.js';

const DEMO = new URLSearchParams(location.search).has('demo');
const IGNORE_SKEW_MS = 5000;
const TICK_MS = 15000;
const $ = (s) => document.querySelector(s);

function main() {
  const cfg = loadConfig();
  const keys = DEMO ? STORAGE.demo : STORAGE.real;
  let cached = null;
  try { cached = JSON.parse(localStorage.getItem(keys.summaryKey) || 'null'); } catch (e) { /* 없어도 됨 */ }
  const state = { summary: cached, stale: false, pending: 0, clockSkewMs: 0 };

  const ctx = {
    cfg,
    state,
    api: DEMO ? createDemoApi() : createApi(cfg),
    now: () => new Date(Date.now() + state.clockSkewMs),
    save, finishFeed, wake, attachMemo, update, remove,
    openEntry: (kind) => entry.open(kind),
    openEdit: (e) => entry.openEdit(e),
  };
  ctx.measures = createMeasures(ctx, DEMO ? 'albam.demo.measures' : 'albam.measures');
  ctx.upcoming = createUpcoming(ctx, DEMO ? 'albam.demo.upcoming' : 'albam.upcoming');
  const notice = createNotice({ undoSeconds: cfg.undoSeconds, onUndone: async () => { await refresh(); if (view === 'records') records.reload(); } });
  ctx.phrases = createPhrases(ctx, DEMO ? 'albam.demo.phrases' : 'albam.phrases', {
    labelOf: (kind) => recordType(kind)?.label || kind,
    onChange: () => { render(); entry.refreshChips(); },
    notify: (text, tone) => notice.show(text, tone),
  });
  const home = setupHome(ctx);
  const entry = setupEntry(ctx);
  const records = setupRecords(ctx);
  ctx.openDay = (day) => { showView('records'); records.showDay(day); };
  const stats = setupStats(ctx);

  // ── 쪽 바꾸기(아래 탭) ──
  let view = 'home';
  function showView(next) {
    view = next;
    for (const t of document.querySelectorAll('#tabs [data-view]')) t.classList.toggle('on', t.dataset.view === view);
    $('#viewHome').hidden = view !== 'home';
    $('#viewRecords').hidden = view !== 'records';
    $('#viewStats').hidden = view !== 'stats';
    $('#top').hidden = view !== 'home';   // 다른 쪽은 머리가 따로 있다
    window.scrollTo(0, 0);
  }
  for (const b of document.querySelectorAll('#tabs [data-view]')) {
    b.addEventListener('click', () => {
      showView(b.dataset.view);
      if (view === 'records') records.show();
      if (view === 'stats') stats.show();
    });
  }

  function render() {
    home.render();
    const net = $('#net');
    const [text, tone] = state.pending ? [`대기 ${state.pending}건 · 연결되면 보내요`, ''] : state.stale ? ['연결 안 됨 · 지난번 내용', 'warn'] : ['', ''];
    net.textContent = text;
    net.className = tone;
    net.hidden = !text;
    const light = isDaylight(ctx.now(), cfg);
    document.body.classList.toggle('light', light);
    document.querySelector('meta[name="theme-color"]').setAttribute('content', light ? '#efe5d3' : '#0b0908');
  }

  // ── 요약 받기 ──
  let refreshing = false;
  async function refresh() {
    if (refreshing || !ctx.api.isLoggedIn()) return;
    refreshing = true;
    try {
      const r = await ctx.api.getSummary();
      if (r.summary) state.summary = r.summary;
      if (!r.stale && r.summary?.server_time && r.summary._received_at) {
        const skew = new Date(r.summary.server_time).getTime() - r.summary._received_at;
        state.clockSkewMs = Math.abs(skew) < IGNORE_SKEW_MS ? 0 : skew;
      }
      state.stale = r.stale;
      state.pending = r.pending;
      render();
      if (r.error instanceof AuthError) showLogin('이 계정은 가족 명단에 없어요. 가족 계정으로 로그인해 주세요');
    } catch (e) {
      if (e instanceof AuthError) showLogin('다시 로그인해 주세요');
      else console.error(e);
    } finally {
      refreshing = false;
    }
  }

  // ── 저장 ──
  const failed = (e) => {
    if (e instanceof AuthError) showLogin('다시 로그인해 주세요');
    else notice.show('저장 못 했어요', 'warn');
    console.error(e);
  };
  const queued = (r) => (r.status === 'queued' ? ' (대기)' : '');
  let waiting = null;

  async function save(ev, opts = {}) {
    let r;
    try { r = await ctx.api.addEvent(ev, opts); } catch (e) { failed(e); return; }
    if (r.status === 'confirm') {
      waiting = { ...ev, id: r.id };
      const ex = r.existing;
      const old = { kind: ex.kind || ev.kind, occurred_at: ex.at, amount_ml: ex.ml, detail: ex.detail };
      const gap = Math.round(Math.abs(new Date(ev.occurred_at || ctx.now()) - new Date(ex.at)) / 60000);
      $('#confirmText').textContent = `${gap}분 차이로 비슷한 기록이 이미 있어요. 있는 것: ${describeEvent(old, ctx.now())} (${formatClock(ex.at)}) / 넣을 것: ${describeEvent(ev, ctx.now())}`;
      $('#confirm').showModal();
      return;
    }
    notice.showUndo(describeEvent(ev, ctx.now()) + queued(r), () => ctx.api.cancelEvent(r.id));
    await refresh();
    if (view === 'records') records.reload();
    if (view === 'stats') stats.reload();
  }

  /** 기록 고치기(기록 쪽) */
  async function update(id, patch, label) {
    let r;
    try { r = await ctx.api.updateEvent(id, patch); } catch (e) { failed(e); return; }
    notice.show(r.status === 'not_found' ? '그 기록을 못 찾았어요' : `고쳤어요 · ${label}${queued(r)}`, r.status === 'not_found' ? 'warn' : '');
    await refresh();
    records.reload();
  }

  /** 기록 지우기(지우지 않고 취소 표시. 서버가 내역에 남긴다) */
  async function remove(id, label) {
    let r;
    try { r = await ctx.api.cancelEvent(id); } catch (e) { failed(e); return; }
    notice.show(`지웠어요 · ${label}${queued(r)}`);
    await refresh();
    records.reload();
  }
  $('#confirmYes').addEventListener('click', () => { const ev = waiting; waiting = null; $('#confirm').close(); if (ev) save(ev, { force: true }); });
  $('#confirmNo').addEventListener('click', () => { waiting = null; $('#confirm').close(); notice.show('안 넣었어요'); });

  /** 다 먹음: 먹이는 중인 수유에 끝(지금). [취소]는 다시 먹이는 중으로 */
  async function finishFeed(feed) {
    const end = ctx.now();
    let r;
    try { r = await ctx.api.updateEvent(feed.id, { ended_at: end, detail: { feeding: false } }); } catch (e) { failed(e); return; }
    if (r.status === 'not_found') { notice.show('먹이는 중인 수유를 못 찾았어요', 'warn'); await refresh(); return; }
    notice.showUndo(`수유 ${feed.ml ?? ''}ml · ${formatDuration(end - new Date(feed.at))}${queued(r)}`,
      () => ctx.api.updateEvent(feed.id, { ended_at: null, detail: { feeding: true } }));
    await refresh();
  }

  /** 깼어요: 자는 중인 잠에 끝(지금). [취소]는 다시 자는 중으로 */
  async function wake(sleep) {
    const end = ctx.now();
    let r;
    try { r = await ctx.api.endSleep(sleep.id, end); } catch (e) { failed(e); return; }
    if (r.status === 'not_found') { notice.show('자는 중인 잠을 못 찾았어요', 'warn'); await refresh(); return; }
    notice.showUndo(`잠 ${formatDuration(end - new Date(sleep.at))}${queued(r)}`, () => ctx.api.endSleep(sleep.id, null));
    await refresh();
  }

  /** 먹이는 중인 수유에 문구를 붙이거나 뗀다(detail.memo) */
  async function attachMemo(id, memo) {
    try { await ctx.api.updateEvent(id, { detail: { memo } }); } catch (e) { failed(e); return; }
    await refresh();
  }

  // ── 로그인 ──
  function showLogin(message = '') {
    if (ctx.api.demo) return;
    $('#email').value = ctx.api.email() || $('#email').value;
    $('#loginMsg').textContent = message;
    if (!$('#login').open) $('#login').showModal();
  }
  $('#login').addEventListener('cancel', (e) => e.preventDefault());   // 로그인 전에는 닫지 못한다
  $('#loginForm').addEventListener('submit', async (e) => {
    e.preventDefault();
    $('#loginBtn').disabled = true;
    $('#loginMsg').textContent = '';
    try {
      await ctx.api.signIn($('#email').value.trim(), $('#password').value);
      $('#password').value = '';
      $('#login').close();
      await start();
    } catch (err) {
      $('#loginMsg').textContent = /invalid/i.test(err.message) ? '이메일이나 비밀번호가 맞지 않아요' : `로그인 실패: ${err.message}`;
    } finally {
      $('#loginBtn').disabled = false;
    }
  });

  ctx.api.onChange(async () => {
    state.pending = await ctx.api.pendingCount();
    render();
    if (!ctx.api.isLoggedIn()) showLogin();
  });

  /** 로그인된 뒤: 요약, 측정 기록(지난번 값), 다가오는 일정 */
  async function start() {
    await refresh();
    ctx.measures.load();
    ctx.phrases.load();
    ctx.upcoming.load().then(render);
  }

  // ── 주기 작업 ──
  setInterval(render, TICK_MS);
  setInterval(() => { if (document.visibilityState === 'visible') refresh(); }, cfg.pollSeconds * 1000);
  document.addEventListener('visibilitychange', () => { if (document.visibilityState === 'visible') refresh(); });
  window.addEventListener('online', () => ctx.api.flush().then(refresh).catch(() => {}));
  window.addEventListener('offline', () => { state.stale = true; render(); });
  if ('serviceWorker' in navigator) navigator.serviceWorker.register('../sw.js').catch(() => {});

  render();
  if (ctx.api.isConfigured() && ctx.api.isLoggedIn()) start();
  else showLogin();
}

main();
