// 알밤보드 거실 화면 시작점. 각 화면 모듈을 만들어 서로 이어 주고, 주기 작업을 건다.
// 화면은 받아서 그리기만 하고, 계산은 Supabase 요약 함수가 한다. 경과 시간만 여기서 센다.
// 구조는 docs/TECHNICAL.md 에 그림으로 있다.

import { loadConfig } from './config.js';
import { createApi, AuthError, STORAGE } from './api/index.js';
import { createDemoApi } from './api/demo.js';
import { isWithinHours } from './time.js';
import { createSound } from './ui/sound.js';
import { fitStage, keepScreenOn, startBurnInShift } from './ui/stage.js';
import { isSheetOpen, setupCloseButtons } from './ui/sheets.js';
import { createStatusView } from './ui/status.js';
import { setupNight } from './ui/night.js';
import { setupRecorder } from './ui/recorder.js';
import { setupQuickRecord } from './ui/quick-record.js';
import { setupFeedAmounts } from './ui/feed-amounts.js';
import { setupLateEntry } from './ui/late-entry.js';
import { setupDayList } from './ui/day-list.js';
import { setupMore } from './ui/more.js';
import { setupVoiceInput } from './ui/voice-input.js';
import { setupLogin } from './ui/login.js';
import { setupStats } from './ui/stats.js';
import { createMeasures } from './ui/measures.js';
import { createUpcoming } from './ui/upcoming.js';
import { setupPages } from './ui/pages.js';
import { setupTimeline } from './ui/timeline.js';
import { setupClockPage } from './ui/clock-page.js';
import { isDaylight } from './sun.js';

const DEMO = new URLSearchParams(location.search).has('demo');
/** 기기 시계가 서버와 이보다 덜 어긋나면 보정하지 않는다 */
const IGNORE_SKEW_MS = 5000;
const ANIMATION_MS = 600;
/** 새로 고침 전에 이만큼 아무도 안 만졌어야 함 */
const RELOAD_IDLE_MS = 120000;
const RELOAD_MIN_UPTIME_MS = 3 * 3600000;

/**
 * 화면 모듈이 함께 쓰는 것들. 모듈은 setupXxx(ctx) 로 만들어지고 ctx 를 통해서만 서로를 부른다.
 * @typedef {Object} AppContext
 * @property {import('./config.js').Config} cfg
 * @property {import('./api/index.js').CareApi & {demo?: boolean}} api  로그인 화면에서 바뀔 수 있어 늘 ctx.api 로 부른다
 * @property {AppState} state
 * @property {ReturnType<typeof createSound>} sfx
 * @property {ReturnType<typeof createUpcoming>} upcoming  다가오는 일정(예방접종 예약 등)
 * @property {ReturnType<typeof createMeasures>} measures  측정 기록: 지난번 값, 성장 백분위
 * @property {() => Date} now                 서버 시각에 맞춘 지금
 * @property {() => boolean} isNightTime      밤 시간대인가
 * @property {() => boolean} isNightAwake     밤에 터치해서 밝혀 둔 동안인가
 * @property {() => boolean} isBusy           창이 열렸거나 음성·취소 버튼이 떠 있음
 * @property {() => void} render              상태 칸 전체 다시 그리기
 * @property {() => void} tick                시계·캐릭터·밤 화면만 다시 그리기
 * @property {() => Promise<void>} refresh    요약 다시 받기
 * @property {(text: string, tone?: 'warn'|'') => void} notify  아래 알림 막대에 저장·취소 결과를 잠깐(말풍선은 알밤 말만)
 * @property {(ev: import('./domain.js').CareEvent, opts?: {force?: boolean}) => Promise<void>} save
 * @property {(sleep: {id: string, at: string}) => Promise<void>} wake   자는 중인 잠 끝내기(깼어요)
 * @property {(feed: {id: string, at: string, ml: number|null}) => Promise<void>} finishFeed  먹이는 중인 수유 끝내기(다 먹음)
 * @property {(id: string, patch: Object, ev: import('./domain.js').CareEvent) => Promise<void>} update  기록 고치기
 * @property {(id: string, ev: import('./domain.js').CareEvent) => Promise<void>} remove  기록 지우기(취소 표시)
 * @property {(back: number) => void} openDayList  그날 기록 목록(0 = 오늘)
 * @property {(message?: string) => void} showLogin
 * @property {() => void} reconnect           Supabase 주소·키를 바꾼 뒤 통신을 새로 만든다
 */

/**
 * @typedef {Object} AppState
 * @property {import('./domain.js').Summary|null} summary  화면에 보여 주는 요약(못 보낸 기록 포함)
 * @property {boolean} stale            서버에서 못 받은 요약을 보여 주는 중
 * @property {number} pending           못 보낸 기록 수
 * @property {number} clockSkewMs       서버 시각 - 기기 시각
 * @property {number} happyUntil        캐릭터 기쁨 끝 시각(ms)
 * @property {number} nightWakeUntil    밤에 밝혀 둔 끝 시각(ms)
 * @property {number} lastTouchAt
 * @property {number} startedAt
 */

function main() {
  const cfg = loadConfig();
  const makeApi = () => (DEMO ? createDemoApi() : createApi(loadConfig()));

  /** @type {AppState} */
  const state = {
    summary: readCachedSummary(DEMO ? STORAGE.demo.summaryKey : STORAGE.real.summaryKey),
    stale: false,
    pending: 0,
    clockSkewMs: 0,
    happyUntil: 0,
    nightWakeUntil: 0,
    lastTouchAt: Date.now(),
    startedAt: Date.now(),
  };

  /** @type {AppContext} */
  const ctx = {
    cfg,
    api: makeApi(),
    state,
    sfx: null,
    now: () => new Date(Date.now() + state.clockSkewMs),
    isNightTime: () => isWithinHours(new Date(), cfg.nightStartHour, cfg.nightEndHour),
    isNightAwake: () => Date.now() < state.nightWakeUntil,
    isBusy: () => isSheetOpen() || voice.isBusy() || recorder.isUndoShowing(),
    render: () => { status.render(); timeline.onSummary(); },
    tick: () => { status.tick(); night.update(); },
    refresh,
    notify: (text, tone) => recorder.notify(text, tone),
    save: (ev, opts) => recorder.save(ev, opts),
    wake: (sleep) => recorder.wake(sleep),
    finishFeed: (feed) => recorder.finishFeed(feed),
    update: (id, patch, ev) => recorder.update(id, patch, ev),
    remove: (id, ev) => recorder.remove(id, ev),
    openDayList: (back) => dayList.open(back),
    showLogin: (message) => login.show(message),
    reconnect() {
      Object.assign(cfg, loadConfig());
      ctx.api = makeApi();
      watchApi();
    },
  };
  ctx.sfx = createSound(ctx.isNightTime);
  ctx.measures = createMeasures(ctx, DEMO ? 'albam.demo.measures' : 'albam.measures');
  ctx.measures.load();
  ctx.upcoming = createUpcoming(ctx, DEMO ? 'albam.demo.upcoming' : 'albam.upcoming');
  ctx.upcoming.load().then(() => clockPage.update());

  // ── 화면 모듈 ──
  const status = createStatusView(ctx);
  const night = setupNight(ctx);
  const recorder = setupRecorder(ctx);
  const voice = setupVoiceInput(ctx);
  const login = setupLogin(ctx);
  const quick = setupQuickRecord(ctx);
  setupFeedAmounts(ctx, { current: quick.quickAmounts, back: () => quick.openFeed({ keepAmount: true }) });
  const lateEntry = setupLateEntry(ctx, { openDayList: (back) => dayList.open(back) });
  const dayList = setupDayList(ctx, { onEdit: (e) => lateEntry.openEdit(e) });
  setupMore(ctx, { openNew: (kind) => lateEntry.openNew(kind), openLate: () => lateEntry.open(), openDayList: (back) => dayList.open(back) });
  setupCloseButtons(() => ctx.sfx.tap());
  const stats = setupStats(ctx);
  const timeline = setupTimeline(ctx);
  const clockPage = setupClockPage(ctx);
  setupPages(ctx, {
    onShow: { stats: () => stats.load(), timeline: () => timeline.show(), clock: () => { clockPage.update(); ctx.upcoming.load().then(() => clockPage.update()); } },
    onHide: { timeline: () => timeline.hide() },
  });

  /** 해 뜬 동안 밝은 화면, 해 지면 어두운 화면(config.js theme) */
  function applyTheme() {
    const light = isDaylight(ctx.now(), cfg);
    document.body.classList.toggle('light', light);
    document.querySelector('meta[name="theme-color"]')?.setAttribute('content', light ? '#efe5d3' : '#0e0b09');
  }
  applyTheme();
  setInterval(applyTheme, 60000);

  // ── 요약 받기 ──
  let refreshing = false;
  async function refresh() {
    if (refreshing || !ctx.api.isLoggedIn()) return;
    refreshing = true;
    try {
      const result = await ctx.api.getSummary();
      if (result.summary) state.summary = result.summary;
      if (!result.stale) state.clockSkewMs = measureSkew(result.summary);
      state.stale = result.stale;
      state.pending = result.pending;
      ctx.render();
      // 로그인은 됐는데 가족 명단(care_family)에 없는 계정
      if (result.error instanceof AuthError) ctx.showLogin('이 계정은 가족 명단에 없어요. 가족 계정으로 로그인해 주세요');
    } catch (e) {
      if (e instanceof AuthError) ctx.showLogin('다시 로그인해 주세요');
      else console.error(e);
    } finally {
      refreshing = false;
    }
  }

  /** 못 보낸 기록 수나 로그인 상태가 바뀌면 */
  function watchApi() {
    ctx.api.onChange(async () => {
      state.pending = await ctx.api.pendingCount();
      ctx.render();
      if (!ctx.api.isLoggedIn()) ctx.showLogin();
    });
  }
  watchApi();

  // ── 기기 쪽 설정 ──
  fitStage();
  window.addEventListener('resize', fitStage);
  keepScreenOn();
  startBurnInShift(cfg.shiftMinutes);
  document.addEventListener('pointerdown', () => { state.lastTouchAt = Date.now(); }, true);
  document.addEventListener('contextmenu', (e) => e.preventDefault());
  if ('serviceWorker' in navigator) navigator.serviceWorker.register('sw.js').catch(() => {});

  // ── 주기 작업 ──
  setInterval(() => { status.nextFrame(); night.update(); clockPage.update(); }, ANIMATION_MS);
  setInterval(() => { if (document.visibilityState === 'visible') refresh(); }, cfg.pollSeconds * 1000);
  setInterval(() => reloadOncePerDay(ctx), 60000);
  document.addEventListener('visibilitychange', () => { if (document.visibilityState === 'visible') refresh(); });
  window.addEventListener('online', () => ctx.api.flush().then(refresh).catch(() => {}));
  window.addEventListener('offline', () => { state.stale = true; ctx.render(); });

  // ── 시작 ──
  ctx.render();
  if (ctx.api.isConfigured() && ctx.api.isLoggedIn()) refresh();
  else ctx.showLogin();
}

/** 서버가 요약을 만든 시각과 받은 시각의 차이. 작으면 0 */
function measureSkew(summary) {
  if (!summary?.server_time || !summary._received_at) return 0;
  const skew = new Date(summary.server_time).getTime() - summary._received_at;
  return Math.abs(skew) < IGNORE_SKEW_MS ? 0 : skew;
}

/** 마지막으로 받은 요약(연결 없이 켜도 바로 보이게) */
function readCachedSummary(key) {
  try { return JSON.parse(localStorage.getItem(key) || 'null'); } catch (e) { return null; }
}

/** 24시간 켜 두면 쌓일 수 있는 것을 비우려고 하루 한 번(새벽) 새로 고친다. 누가 쓰는 중이면 미룬다 */
function reloadOncePerDay(ctx) {
  const { state, cfg } = ctx;
  if (new Date().getHours() !== cfg.dailyReloadHour) return;
  if (Date.now() - state.startedAt < RELOAD_MIN_UPTIME_MS) return;
  if (ctx.isBusy() || Date.now() - state.lastTouchAt < RELOAD_IDLE_MS) return;
  location.reload();
}

main();
