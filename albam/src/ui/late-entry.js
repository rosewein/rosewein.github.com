// 지난 기록 넣기(시각을 고쳐 넣기)와 최근 기록 보기.
// 키보드 없이 ±버튼으로 시각을 맞춘다. 수면은 시작·끝 두 줄 중 고른 줄이 움직인다.

import { $, $$, el, setHidden } from './dom.js';
import { openSheet } from './sheets.js';
import { amountSteppers, amountView } from './amount.js';
import { DIAPER_BUTTON, KIND, SOURCE, describeRecent } from '../domain.js';
import { formatClock, formatDay, formatDuration, minutes } from '../time.js';

/** 이보다 오래된 시각으로는 못 돌린다 */
const MAX_DAYS_BACK = 7;
const DEFAULT_START_AGO_MIN = 30;
const DEFAULT_SLEEP_MIN = 60;

/** @param {import('../main.js').AppContext} ctx */
export function setupLateEntry(ctx) {
  const { state, sfx, cfg } = ctx;
  /** 화면에서 고치는 중인 기록 */
  const draft = {
    kind: KIND.FEED,
    start: new Date(),
    end: new Date(),
    /** ±버튼이 움직일 줄 */
    editing: /** @type {'start'|'end'} */ ('start'),
    amount: 200,
    diaperType: 'pee',
  };
  const isSleep = () => draft.kind === KIND.SLEEP;

  function open() {
    const now = ctx.now();
    now.setSeconds(0, 0);
    Object.assign(draft, {
      start: new Date(now - minutes(DEFAULT_START_AGO_MIN)),
      end: now,
      editing: 'start',
      amount: state.summary?.last_feed?.ml ?? 200,
    });
    render();
    openSheet('lateSheet');
  }

  function render() {
    const now = ctx.now();
    for (const b of $$('#lateSheet [data-kind]')) b.classList.toggle('on', b.dataset.kind === draft.kind);
    if (!isSleep()) draft.editing = 'start';

    $('#lateStartLbl').textContent = isSleep() ? '시작' : '시각';
    $('#lateStart').textContent = `${formatDay(draft.start, now)} ${formatClock(draft.start)}`;
    setHidden($('#lateEndRow'), !isSleep());
    if (isSleep()) {
      $('#lateEnd').textContent = `${formatDay(draft.end, now)} ${formatClock(draft.end)}`;
      $('#lateDur').textContent = formatDuration(draft.end - draft.start);
    }
    $('#lateStartRow').classList.toggle('sel', draft.editing === 'start');
    $('#lateEndRow').classList.toggle('sel', draft.editing === 'end');
    $('#lateDetail').replaceChildren(...detailControls());
    $('#lateSave').disabled = isSleep() && draft.end - draft.start < minutes(1);
  }

  /** 종류별 아랫줄: 수유량 / 기저귀 종류 / (수면은 없음) */
  function detailControls() {
    const button = (text, { on = false, width, grow = false } = {}, change) => el('button', {
      className: `px${on ? ' on' : ''}${grow ? ' grow' : ''}`,
      style: width ? { width: `${width}px` } : {},
      onClick: () => { sfx.tap(); change(); render(); },
    }, text);

    if (draft.kind === KIND.FEED) {
      // 수유 창과 같은 줄: [-10] [-30 브레짜] 200ml/브레짜 180 [+30 브레짜] [+10]
      const steps = amountSteppers({
        get: () => draft.amount,
        set: (ml) => { draft.amount = ml; render(); },
        mixing: cfg,
        tap: sfx.tap,
      });
      return [...steps.before, amountView(draft.amount, cfg), ...steps.after];
    }
    if (draft.kind === KIND.DIAPER) {
      return Object.entries(DIAPER_BUTTON).map(([type, label]) =>
        button(label, { on: draft.diaperType === type, grow: true }, () => { draft.diaperType = type; }));
    }
    return [];
  }

  /** ±버튼: 고른 줄을 움직인다. 미래로는 못 가고, 수면은 끝이 시작보다 앞서지 않게 */
  function shift(deltaMin) {
    const max = ctx.now().getTime();
    const min = max - MAX_DAYS_BACK * 86400000;
    const clamp = (t) => new Date(Math.min(max, Math.max(min, t)));
    if (draft.editing === 'start') {
      draft.start = clamp(draft.start.getTime() + minutes(deltaMin));
      if (isSleep() && draft.start > draft.end) draft.end = new Date(draft.start);
    } else {
      draft.end = clamp(draft.end.getTime() + minutes(deltaMin));
      if (draft.end < draft.start) draft.start = new Date(draft.end);
    }
  }

  function toEvent() {
    const ev = { kind: draft.kind, occurred_at: draft.start, detail: {}, source: SOURCE.TOUCH };
    if (draft.kind === KIND.FEED) ev.amount_ml = draft.amount;
    if (draft.kind === KIND.DIAPER) ev.detail = { type: draft.diaperType };
    if (draft.kind === KIND.SLEEP) ev.ended_at = draft.end;
    return ev;
  }

  // ── 연결 ──
  $('#lateBtn').addEventListener('click', () => { sfx.tap(); open(); });
  for (const b of $$('#lateSheet [data-kind]')) {
    b.addEventListener('click', () => {
      sfx.tap();
      draft.kind = b.dataset.kind;
      if (isSleep() && draft.end - draft.start < minutes(DEFAULT_START_AGO_MIN)) {
        draft.start = new Date(draft.end - minutes(DEFAULT_SLEEP_MIN));
      }
      render();
    });
  }
  $('#lateStartRow').addEventListener('click', () => { draft.editing = 'start'; render(); });
  $('#lateEndRow').addEventListener('click', () => { draft.editing = 'end'; render(); });
  for (const b of $$('#lateSteps [data-min]')) {
    b.addEventListener('click', () => { sfx.tap(); shift(Number(b.dataset.min)); render(); });
  }
  $('#lateSave').addEventListener('click', () => ctx.save(toEvent()));
  $('#recentBtn').addEventListener('click', () => { sfx.tap(); showRecent(); });

  // ── 최근 기록: 실제 시각 순서로 자리 잡았는지 보는 곳 ──
  function showRecent() {
    const now = ctx.now();
    const rows = (state.summary?.recent || []).map((r) => el('div', { className: `t9${r.pending ? ' pending' : ''}` },
      `${formatDay(r.at, now)} ${formatClock(r.at)}  ${describeRecent(r)}${r.pending ? '  (대기)' : ''}`));
    $('#recentList').replaceChildren(...(rows.length ? rows : ['기록이 없어요']));
    openSheet('recentSheet');
  }
}
