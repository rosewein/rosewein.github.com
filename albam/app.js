// 알밤케어 거실 화면 (갤럭시 S10 가로)
// 화면은 받아서 그리기만 하고, 계산은 Supabase 요약 함수가 한다. 경과 시간만 여기서 센다.
import { createApi, AuthError } from './api.js';
import { createDemoApi } from './demo-api.js';
import { parseUtterance } from './voice-parse.js';

const DEMO = new URLSearchParams(location.search).has('demo');
const baseCfg = window.ALBAM_CONFIG || {};
function loadCfg() {
  let local = {};
  try { local = JSON.parse(localStorage.getItem('albam.config') || '{}'); } catch (e) {}
  return { ...baseCfg, ...Object.fromEntries(Object.entries(local).filter(([, v]) => v)) };
}
let cfg = loadCfg();
let api = DEMO ? createDemoApi(cfg) : createApi(cfg);

const $ = (s) => document.querySelector(s);
const $$ = (s) => [...document.querySelectorAll(s)];
const pad = (n) => String(n).padStart(2, '0');
const hhmm = (d) => { d = new Date(d); return `${pad(d.getHours())}:${pad(d.getMinutes())}`; };
const DIAPER = { pee: '소변', poo: '대변', both: '소변+대변' };

// ── 상태 ─────────────────────────────────────────────────────
const st = {
  summary: null,
  stale: false,
  pending: 0,
  skew: 0,              // 서버 시각 - 기기 시각
  happyUntil: 0,
  bubble: null,         // { text, until, cls }
  wakeUntil: 0,         // 밤에 터치해서 밝힌 시각까지
  lastTouch: Date.now(),
  loadedAt: Date.now(),
  frame: 0,
  shiftIdx: 0,
  authProblem: '',
};
const now = () => new Date(Date.now() + st.skew);

// ── 화면 크기: 논리 380x180 을 기기 화소의 정수배로 ──────────
const LW = 380, LH = 180;
function fit() {
  const dpr = window.devicePixelRatio || 1;
  const W = window.innerWidth, H = window.innerHeight;
  const k = Math.max(1, Math.floor(Math.min((W * dpr) / LW, (H * dpr) / LH)));
  $('#stage').style.zoom = k / dpr;
  $('#wrap').style.left = `${Math.floor((W * dpr - LW * k) / 2) / dpr}px`;
  $('#wrap').style.top = `${Math.floor((H * dpr - LH * k) / 2) / dpr}px`;
}
window.addEventListener('resize', fit);
fit();

// ── 효과음 (WebAudio, 파일 없음) ─────────────────────────────
let ac = null;
function beep(notes) {
  try {
    ac = ac || new (window.AudioContext || window.webkitAudioContext)();
    if (ac.state === 'suspended') ac.resume();
    const vol = isNight() ? 0.02 : 0.06;
    let t = ac.currentTime + 0.01;
    for (const [f, d] of notes) {
      const o = ac.createOscillator(), g = ac.createGain();
      o.type = 'square';
      o.frequency.value = f;
      g.gain.setValueAtTime(vol, t);
      g.gain.exponentialRampToValueAtTime(0.0001, t + d);
      o.connect(g).connect(ac.destination);
      o.start(t);
      o.stop(t + d + 0.02);
      t += d * 0.85;
    }
  } catch (e) {}
}
const sfx = {
  save: () => beep([[660, 0.08], [880, 0.08], [1320, 0.14]]),
  cancel: () => beep([[660, 0.08], [440, 0.14]]),
  error: () => beep([[200, 0.12], [160, 0.2]]),
  listen: () => beep([[990, 0.06]]),
  tap: () => beep([[520, 0.03]]),
};

// ── 밤 ──────────────────────────────────────────────────────
function isNight(d = new Date()) {
  const h = d.getHours(), s = cfg.nightStartHour ?? 21, e = cfg.nightEndHour ?? 6;
  return s > e ? h >= s || h < e : h >= s && h < e;
}

// ── 그리기 ───────────────────────────────────────────────────
function elapsedText(at) {
  if (!at) return '-:--';
  const m = Math.max(0, Math.floor((now() - new Date(at)) / 60000));
  return `${Math.min(99, Math.floor(m / 60))}:${pad(m % 60)}`;
}
function sinceText(at) {
  const m = Math.max(0, Math.floor((now() - new Date(at)) / 60000));
  if (m < 60) return `${m}분 전`;
  return `${Math.floor(m / 60)}:${pad(m % 60)} 전`;
}

function render() {
  const s = st.summary;
  const lf = s?.last_feed, ld = s?.last_diaper;
  $('#elapsed').textContent = elapsedText(lf?.at);
  $('#lastFeed').textContent = lf ? `수유 ${hhmm(lf.at)}${lf.ml != null ? ` · ${lf.ml}ml` : ''}` : '수유 기록 없음';
  $('#lastDiaper').textContent = ld ? `기저귀 ${hhmm(ld.at)} ${DIAPER[ld.type] || ''} · ${sinceText(ld.at)}` : '기저귀 기록 없음';
  $('#todayCount').textContent = s ? `${s.today?.feed_count ?? 0}회` : '-회';
  $('#todayMl').textContent = s ? `${s.today?.feed_ml ?? 0}ml` : '-ml';
  const net = $('#net');
  if (st.pending) { net.textContent = `대기 ${st.pending}건`; net.className = 't9 acc'; }
  else if (st.stale) { net.textContent = '연결 안 됨'; net.className = 't9 warn'; }
  else { net.textContent = DEMO ? '미리 보기' : ''; net.className = 't9 faint'; }
  tick();
}

function charState() {
  const t = Date.now();
  if (t < st.happyUntil) return 'happy';
  if (isNight() && t > st.wakeUntil) return 'sleep';
  const lf = st.summary?.last_feed;
  if (lf && now() - new Date(lf.at) > (cfg.hungryMinutes ?? 180) * 60000) return 'hungry';
  if (isNight()) return 'sleep';
  return 'normal';
}
const ROW = { normal: 0, hungry: 1, sleep: 2, happy: 3 };
const MOOD = { normal: '', hungry: '배고파요…', sleep: '쿨쿨', happy: '고마워요!' };

function tick() {
  const n = now();
  $('#clock').textContent = hhmm(n);
  $('#elapsed').textContent = elapsedText(st.summary?.last_feed?.at);
  const state = charState();
  $('#elapsed').classList.toggle('warn', state === 'hungry');
  $('#albam').style.backgroundPosition = `${-st.frame * 96}px ${-ROW[state] * 96}px`;
  const b = st.bubble && Date.now() < st.bubble.until ? st.bubble : null;
  const bub = $('#bubble');
  bub.textContent = b ? b.text : st.authProblem || MOOD[state];
  bub.className = b?.cls || (st.authProblem ? 'warn' : '');
  nightTick();
}
function say(text, seconds = 4, cls = '') { st.bubble = { text, until: Date.now() + seconds * 1000, cls }; tick(); }

// ── 요약 받기 ────────────────────────────────────────────────
let refreshing = false;
async function refresh() {
  if (refreshing || !api.isLoggedIn()) return;
  refreshing = true;
  try {
    const r = await api.getSummary();
    if (r.summary) {
      st.summary = r.summary;
      if (!r.stale && r.summary.server_time && r.summary._received_at) {
        st.skew = new Date(r.summary.server_time).getTime() - r.summary._received_at;
        if (Math.abs(st.skew) < 5000) st.skew = 0;
      }
    }
    st.stale = r.stale;
    st.pending = r.pending;
    st.authProblem = r.error instanceof AuthError ? '가족 계정이 아니에요' : '';
    render();
  } catch (e) {
    if (e instanceof AuthError) showLogin('다시 로그인해 주세요');
  } finally {
    refreshing = false;
  }
}
api.onChange(async () => { st.pending = await api.pendingCount(); render(); if (!api.isLoggedIn()) showLogin(); });

// ── 덮는 창 ──────────────────────────────────────────────────
function openSheet(id) {
  $$('.sheet').forEach((el) => el.classList.toggle('hidden', el.id !== id));
}
function closeSheets() { $$('.sheet').forEach((el) => el.classList.add('hidden')); }
const sheetOpen = () => $$('.sheet').some((el) => !el.classList.contains('hidden'));
$$('[data-close]').forEach((b) => b.addEventListener('click', () => { sfx.tap(); closeSheets(); }));

// ── 저장 공통 ─────────────────────────────────────────────────
function describe(ev) {
  let t = '';
  if (ev.kind === 'feed') t = `수유 ${ev.amount_ml ?? ''}ml`;
  else if (ev.kind === 'diaper') t = `기저귀 ${DIAPER[ev.detail?.type] || ''}`;
  else if (ev.kind === 'sleep') return `잠 ${hhmm(ev.occurred_at)}~${hhmm(ev.ended_at)}`;
  else t = ev.kind;
  const at = new Date(ev.occurred_at || Date.now());
  if (now() - at > 2 * 60000) t += ` · ${hhmm(at)}`;
  return t;
}

let pendingConfirm = null;
async function save(ev, opts = {}) {
  try {
    const r = await api.addEvent(ev, opts);
    if (r.status === 'confirm') {
      pendingConfirm = { ev: { ...ev, id: r.id } };
      const ex = r.existing;
      const exEv = { kind: ex.kind || ev.kind, occurred_at: ex.at, amount_ml: ex.ml, detail: ex.detail };
      const mins = Math.round(Math.abs(new Date(ev.occurred_at || now()) - new Date(ex.at)) / 60000);
      $('#confirmText').innerHTML = '';
      $('#confirmText').append(
        `${mins}분 차이로 비슷한 기록이 이미 있어요.`, document.createElement('br'),
        `있는 것: ${describe(exEv)} (${hhmm(ex.at)})`, document.createElement('br'),
        `넣을 것: ${describe(ev)}`,
      );
      openSheet('confirmSheet');
      sfx.error();
      return;
    }
    closeSheets();
    sfx.save();
    st.happyUntil = Date.now() + 3000;
    showUndo(r.id, describe(ev) + (r.status === 'queued' ? ' (대기)' : ''));
    await refresh();
  } catch (e) {
    sfx.error();
    if (e instanceof AuthError) { showLogin('다시 로그인해 주세요'); return; }
    say(`저장 못 함: ${e.message}`.slice(0, 40), 6, 'warn');
    console.error(e);
  }
}
$('#confirmYes').addEventListener('click', () => { const p = pendingConfirm; pendingConfirm = null; if (p) save(p.ev, { force: true }); });
$('#confirmNo').addEventListener('click', () => { pendingConfirm = null; sfx.cancel(); closeSheets(); say('안 넣었어요'); });

// 저장 직후 몇 초 동안 [취소]
let undo = null;
function showUndo(id, text) {
  clearInterval(undo?.timer);
  const until = Date.now() + (cfg.undoSeconds ?? 6) * 1000;
  undo = { id, until };
  $('#undoText').textContent = `${text} 저장됨`;
  $('#actions').classList.add('hidden');
  $('#undo').classList.remove('hidden');
  const step = () => {
    const left = Math.ceil((until - Date.now()) / 1000);
    if (left <= 0) return hideUndo();
    $('#undoCount').textContent = left;
  };
  step();
  undo.timer = setInterval(step, 250);
}
function hideUndo() {
  clearInterval(undo?.timer);
  undo = null;
  $('#undo').classList.add('hidden');
  $('#actions').classList.remove('hidden');
}
$('#undoBtn').addEventListener('click', async () => {
  if (!undo) return;
  const id = undo.id;
  hideUndo();
  try {
    await api.cancelEvent(id);
    sfx.cancel();
    st.happyUntil = 0;
    say('취소했어요');
  } catch (e) {
    sfx.error();
    say('취소 못 함', 5, 'warn');
  }
  refresh();
});
$('#undoMsg').addEventListener('click', hideUndo);

// ── 수유 ────────────────────────────────────────────────────
let feedAmount = 160;
function quickAmounts() {
  const rec = (st.summary?.recent_feed_amounts || []).filter((x) => x != null);
  const list = [...rec];
  for (const d of cfg.defaultAmounts || [120, 140, 160]) if (list.length < 3 && !list.includes(d)) list.push(d);
  return list.slice(0, 3).sort((a, b) => a - b);
}
function renderFeed() {
  const row = $('#amountRow');
  row.innerHTML = '';
  for (const a of quickAmounts()) {
    const b = document.createElement('button');
    b.className = `px${a === feedAmount ? ' on' : ''}`;
    b.textContent = a;
    b.addEventListener('click', () => { sfx.tap(); feedAmount = a; renderFeed(); });
    row.append(b);
  }
  $('#stepVal').textContent = `${feedAmount}ml`;
}
$('#feedBtn').addEventListener('click', () => {
  sfx.tap();
  feedAmount = st.summary?.last_feed?.ml ?? quickAmounts()[0] ?? 160;
  renderFeed();
  openSheet('feedSheet');
});
$$('#stepRow [data-step]').forEach((b) => b.addEventListener('click', () => {
  sfx.tap();
  feedAmount = Math.min(500, Math.max(5, feedAmount + Number(b.dataset.step)));
  renderFeed();
}));
$('#feedSave').addEventListener('click', () => save({ kind: 'feed', amount_ml: feedAmount, occurred_at: now(), detail: {}, source: 'living_room_touch' }));

// ── 기저귀 ──────────────────────────────────────────────────
$('#diaperBtn').addEventListener('click', () => { sfx.tap(); openSheet('diaperSheet'); });
$$('#diaperSheet [data-type]').forEach((b) => b.addEventListener('click', () =>
  save({ kind: 'diaper', occurred_at: now(), detail: { type: b.dataset.type }, source: 'living_room_touch' })));

// ── 지난 기록 넣기 ───────────────────────────────────────────
const late = { kind: 'feed', start: null, end: null, sel: 'start', amount: 160, dtype: 'pee' };
function dayLabel(d) {
  const a = new Date(d); a.setHours(0, 0, 0, 0);
  const b = now(); b.setHours(0, 0, 0, 0);
  const diff = Math.round((b - a) / 86400000);
  return diff === 0 ? '오늘' : diff === 1 ? '어제' : `${a.getMonth() + 1}/${a.getDate()}`;
}
function renderLate() {
  $$('#lateSheet [data-kind]').forEach((b) => b.classList.toggle('on', b.dataset.kind === late.kind));
  const sleep = late.kind === 'sleep';
  $('#lateStartLbl').textContent = sleep ? '시작' : '시각';
  $('#lateStart').textContent = `${dayLabel(late.start)} ${hhmm(late.start)}`;
  $('#lateEndRow').classList.toggle('hidden', !sleep);
  if (sleep) {
    $('#lateEnd').textContent = `${dayLabel(late.end)} ${hhmm(late.end)}`;
    const m = Math.round((late.end - late.start) / 60000);
    $('#lateDur').textContent = `${Math.floor(m / 60)}시간 ${m % 60}분`;
  } else {
    late.sel = 'start';
  }
  $('#lateStartRow').classList.toggle('sel', late.sel === 'start');
  $('#lateEndRow').classList.toggle('sel', late.sel === 'end');
  const d = $('#lateDetail');
  d.innerHTML = '';
  const btn = (text, on, fn, w) => {
    const b = document.createElement('button');
    b.className = `px${on ? ' on' : ''}`;
    b.textContent = text;
    if (w) b.style.width = `${w}px`;
    b.addEventListener('click', () => { sfx.tap(); fn(); renderLate(); });
    d.append(b);
  };
  if (late.kind === 'feed') {
    btn('-10', false, () => { late.amount = Math.max(5, late.amount - 10); }, 40);
    btn('-5', false, () => { late.amount = Math.max(5, late.amount - 5); }, 40);
    const v = document.createElement('div'); v.className = 'amt t24'; v.textContent = `${late.amount}ml`; d.append(v);
    btn('+5', false, () => { late.amount = Math.min(500, late.amount + 5); }, 40);
    btn('+10', false, () => { late.amount = Math.min(500, late.amount + 10); }, 40);
  } else if (late.kind === 'diaper') {
    for (const [k, label] of Object.entries({ pee: '소변', poo: '대변', both: '둘 다' })) {
      btn(label, late.dtype === k, () => { late.dtype = k; });
      d.lastChild.classList.add('grow');
    }
  }
  // 수면은 끝 줄이 하나 더 있어서 아래 줄이 없음
  $('#lateSave').disabled = sleep && late.end - late.start < 60000;
}
$('#lateBtn').addEventListener('click', () => {
  sfx.tap();
  const n = now(); n.setSeconds(0, 0);
  late.start = new Date(n.getTime() - 30 * 60000);
  late.end = new Date(n);
  late.sel = 'start';
  late.amount = st.summary?.last_feed?.ml ?? 160;
  renderLate();
  openSheet('lateSheet');
});
$$('#lateSheet [data-kind]').forEach((b) => b.addEventListener('click', () => {
  sfx.tap();
  late.kind = b.dataset.kind;
  if (late.kind === 'sleep' && late.end - late.start < 30 * 60000) late.start = new Date(late.end.getTime() - 60 * 60000);
  renderLate();
}));
$('#lateStartRow').addEventListener('click', () => { late.sel = 'start'; renderLate(); });
$('#lateEndRow').addEventListener('click', () => { late.sel = 'end'; renderLate(); });
$$('#lateSteps [data-min]').forEach((b) => b.addEventListener('click', () => {
  sfx.tap();
  const delta = Number(b.dataset.min) * 60000;
  const max = now().getTime();
  const min = max - 7 * 86400000;
  const clamp = (t) => Math.min(max, Math.max(min, t));
  if (late.sel === 'start') {
    late.start = new Date(clamp(late.start.getTime() + delta));
    if (late.kind === 'sleep' && late.start > late.end) late.end = new Date(late.start);
  } else {
    late.end = new Date(clamp(late.end.getTime() + delta));
    if (late.end < late.start) late.start = new Date(late.end);
  }
  renderLate();
}));
$('#lateSave').addEventListener('click', () => {
  const ev = { kind: late.kind, occurred_at: late.start, detail: {}, source: 'living_room_touch' };
  if (late.kind === 'feed') ev.amount_ml = late.amount;
  if (late.kind === 'diaper') ev.detail = { type: late.dtype };
  if (late.kind === 'sleep') ev.ended_at = late.end;
  save(ev);
});
$('#recentBtn').addEventListener('click', () => {
  sfx.tap();
  const list = $('#recentList');
  list.innerHTML = '';
  for (const r of st.summary?.recent || []) {
    const div = document.createElement('div');
    div.className = `t9${r.pending ? ' pending' : ''}`;
    const d = new Date(r.at);
    const what = r.kind === 'feed' ? `수유 ${r.ml ?? ''}ml` : r.kind === 'diaper' ? `기저귀 ${DIAPER[r.detail?.type] || ''}`
      : r.kind === 'sleep' ? `잠 ~${r.ended_at ? hhmm(r.ended_at) : ''}` : r.kind;
    div.textContent = `${dayLabel(d)} ${hhmm(d)}  ${what}${r.pending ? '  (대기)' : ''}`;
    list.append(div);
  }
  if (!list.children.length) list.textContent = '기록이 없어요';
  openSheet('recentSheet');
});

// ── 음성 ────────────────────────────────────────────────────
const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
const voice = { rec: null, phase: 'idle', timer: null, ev: null, text: '' };

function voiceUi({ title, label = '', raw = '', retry = false, bar = false }) {
  $('#voiceTitle').textContent = title;
  $('#voiceLabel').textContent = label;
  $('#voiceRaw').textContent = raw;
  $('#voiceRetry').classList.toggle('hidden', !retry);
  $('#voiceBar').classList.toggle('hidden', !bar);
  openSheet('voiceSheet');
}
function stopVoice() {
  clearInterval(voice.timer);
  voice.timer = null;
  try { voice.rec?.abort(); } catch (e) {}
  voice.rec = null;
  voice.phase = 'idle';
  $('#micBtn').classList.remove('listening');
  $('#micLabel').textContent = '말하기';
}
function startVoice() {
  stopVoice();
  if (!SR) {
    voiceUi({ title: '음성 인식을 쓸 수 없어요', raw: '안드로이드 크롬에서 열어 주세요' });
    return;
  }
  const rec = new SR();
  rec.lang = 'ko-KR';
  rec.interimResults = true;
  rec.maxAlternatives = 5;
  rec.continuous = false;
  voice.rec = rec;
  voice.phase = 'listening';
  let final = false;
  $('#micBtn').classList.add('listening');
  $('#micLabel').textContent = '듣는 중';
  voiceUi({ title: '듣는 중… 말해 주세요', raw: '예: 수유 160 · 기저귀 대변 · 수유 160 20분 전' });
  sfx.listen();
  rec.onresult = (e) => {
    const res = e.results[e.results.length - 1];
    $('#voiceLabel').textContent = res[0].transcript;
    if (res.isFinal) {
      final = true;
      handleVoice([...res].map((a) => a.transcript));
    }
  };
  rec.onerror = (e) => {
    if (voice.phase !== 'listening') return;
    final = true;
    stopVoice();
    const msg = e.error === 'not-allowed' || e.error === 'service-not-allowed' ? '마이크 권한을 허용해 주세요'
      : e.error === 'no-speech' ? '아무 말도 못 들었어요'
      : e.error === 'network' ? '음성 인식은 인터넷이 필요해요' : `음성 인식 오류 (${e.error})`;
    sfx.error();
    voiceUi({ title: msg, retry: true });
  };
  rec.onend = () => {
    if (!final && voice.phase === 'listening') {
      stopVoice();
      voiceUi({ title: '아무 말도 못 들었어요', retry: true });
    }
  };
  try { rec.start(); } catch (e) { stopVoice(); voiceUi({ title: '음성 인식을 시작하지 못했어요', retry: true }); }
}
function handleVoice(alts) {
  stopVoice();
  const n = now();
  let hit = null;
  for (const t of alts) {
    const r = parseUtterance(t, n);
    if (r.ok) { hit = { ...r, text: t }; break; }
  }
  if (!hit) {
    sfx.error();
    voiceUi({ title: '못 알아들었어요. 다시 말해 주세요', label: `“${alts[0] || ''}”`, raw: '예: 수유 160 · 기저귀 대변 · 잠 1시부터 2시 40분까지', retry: true });
    return;
  }
  // 확인: 크게 띄우고 몇 초 뒤 자동 저장. 그 전에 누르면 취소
  voice.phase = 'confirm';
  voice.ev = { ...hit.event, source: 'living_room_voice', voice_text: hit.text };
  voiceUi({ title: '이렇게 넣을게요 · 누르면 취소', label: hit.label, raw: `“${hit.text}”`, bar: true });
  const total = (cfg.voiceConfirmSeconds ?? 4) * 1000;
  const until = Date.now() + total;
  const fill = $('#voiceBarFill');
  voice.timer = setInterval(() => {
    const left = until - Date.now();
    fill.style.width = `${Math.max(0, (left / total) * 100)}%`;
    if (left <= 0) {
      const ev = voice.ev;
      stopVoice();
      save(ev);
    }
  }, 50);
}
function cancelVoice() {
  const was = voice.phase;
  stopVoice();
  closeSheets();
  if (was === 'confirm') { sfx.cancel(); say('안 넣었어요'); }
}
$('#micBtn').addEventListener('click', () => { if (voice.phase === 'listening') cancelVoice(); else startVoice(); });
$('#voiceRetry').addEventListener('click', (e) => { e.stopPropagation(); startVoice(); });
$('#voiceCancel').addEventListener('click', (e) => { e.stopPropagation(); cancelVoice(); });
$('#voiceSheet').addEventListener('click', () => { if (voice.phase === 'confirm') cancelVoice(); });

// ── 로그인 ──────────────────────────────────────────────────
function showLogin(msg = '') {
  if (DEMO) return;
  $('#setupFields').classList.toggle('hidden', api.isConfigured());
  $('#cfgUrl').value = cfg.supabaseUrl || '';
  $('#cfgKey').value = cfg.supabaseAnonKey || '';
  $('#email').value = api.email() || $('#email').value;
  $('#loginMsg').textContent = msg;
  openSheet('loginSheet');
}
$('#loginForm').addEventListener('submit', async (e) => {
  e.preventDefault();
  const btn = $('#loginBtn');
  btn.disabled = true;
  $('#loginMsg').textContent = '';
  try {
    if (!$('#setupFields').classList.contains('hidden')) {
      const local = { supabaseUrl: $('#cfgUrl').value.trim(), supabaseAnonKey: $('#cfgKey').value.trim() };
      localStorage.setItem('albam.config', JSON.stringify(local));
      cfg = loadCfg();
      api = createApi(cfg);
      api.onChange(async () => { st.pending = await api.pendingCount(); render(); });
    }
    await api.signIn($('#email').value.trim(), $('#password').value);
    $('#password').value = '';
    closeSheets();
    sfx.save();
    await refresh();
  } catch (err) {
    sfx.error();
    $('#loginMsg').textContent = /invalid/i.test(err.message) ? '이메일이나 비밀번호가 맞지 않아요' : `로그인 실패: ${err.message}`;
  } finally {
    btn.disabled = false;
  }
});

// ── 화면 켜짐 유지 ───────────────────────────────────────────
let wakeLock = null;
async function keepAwake() {
  if (!('wakeLock' in navigator) || document.visibilityState !== 'visible' || wakeLock) return;
  try {
    wakeLock = await navigator.wakeLock.request('screen');
    wakeLock.addEventListener('release', () => { wakeLock = null; });
  } catch (e) { wakeLock = null; }
}
document.addEventListener('visibilitychange', () => {
  if (document.visibilityState === 'visible') { keepAwake(); refresh(); }
});

// ── 번인 대비: 몇 분마다 화면 전체를 1~2 논리 픽셀 옮김 ─────
const SHIFTS = [[0, 0], [1, 0], [2, 1], [1, 2], [0, 1], [-1, 2], [-2, 1], [-1, 0], [-2, -1], [-1, -2], [0, -1], [1, -2], [2, -1]];
function shift() {
  st.shiftIdx = (st.shiftIdx + 1) % SHIFTS.length;
  const [x, y] = SHIFTS[st.shiftIdx];
  $('#shift').style.transform = `translate(${x}px, ${y}px)`;
}

// ── 밤 화면 ─────────────────────────────────────────────────
let nightPos = { x: 140, y: 70, until: 0 };
function nightTick() {
  const night = isNight() && Date.now() > st.wakeUntil && !sheetOpen() && voice.phase === 'idle';
  $('#night').classList.toggle('hidden', !night);
  document.body.classList.toggle('nightWake', isNight() && !night);
  if (!night) return;
  if (Date.now() > nightPos.until) {
    nightPos = { x: 24 + Math.floor(Math.random() * 230), y: 12 + Math.floor(Math.random() * 120), until: Date.now() + 60000 };
  }
  const el = $('#nightText');
  el.style.left = `${nightPos.x}px`;
  el.style.top = `${nightPos.y}px`;
  const lf = st.summary?.last_feed;
  el.innerHTML = '';
  const big = document.createElement('div');
  big.className = 't24';
  big.textContent = elapsedText(lf?.at);
  const small = document.createElement('div');
  small.className = 't9';
  small.style.marginTop = '4px';
  small.textContent = `수유 후 · ${hhmm(now())}`;
  el.append(big, small);
}
$('#night').addEventListener('pointerdown', (e) => {
  e.preventDefault();
  e.stopPropagation();
  st.wakeUntil = Date.now() + (cfg.nightWakeSeconds ?? 30) * 1000;
  tick();
});
document.addEventListener('pointerdown', () => {
  st.lastTouch = Date.now();
  keepAwake();
  if (isNight() && Date.now() < st.wakeUntil) st.wakeUntil = Date.now() + (cfg.nightWakeSeconds ?? 30) * 1000;
}, true);
document.addEventListener('contextmenu', (e) => e.preventDefault());

// ── 하루 한 번 새로 고침 (24시간 켜 둘 때 쌓이는 것 비우기) ───
function maybeDailyReload() {
  const h = new Date().getHours();
  if (h !== (cfg.dailyReloadHour ?? 4)) return;
  if (Date.now() - st.loadedAt < 3 * 3600000) return;
  if (sheetOpen() || undo || voice.phase !== 'idle' || Date.now() - st.lastTouch < 120000) return;
  location.reload();
}

// ── 시작 ────────────────────────────────────────────────────
setInterval(() => { st.frame ^= 1; tick(); }, 600);
setInterval(shift, (cfg.shiftMinutes ?? 3) * 60000);
setInterval(() => { if (document.visibilityState === 'visible') refresh(); }, (cfg.pollSeconds ?? 20) * 1000);
setInterval(() => { keepAwake(); maybeDailyReload(); }, 60000);
window.addEventListener('online', () => api.flush().then(refresh).catch(() => {}));
window.addEventListener('offline', () => { st.stale = true; render(); });

if ('serviceWorker' in navigator && !DEMO) navigator.serviceWorker.register('sw.js').catch(() => {});

render();
keepAwake();
if (!api.isConfigured() || !api.isLoggedIn()) showLogin();
else {
  if (!DEMO) try { st.summary = JSON.parse(localStorage.getItem('albam.summary') || 'null'); } catch (e) {}
  render();
  refresh();
}
