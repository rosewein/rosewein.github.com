// 지난 기록 넣기(시각을 고쳐 넣기)와 최근 기록 보기.
// 시각은 날짜·시·분 바퀴(./wheel.js)로 고른다. 굴리거나, 위아래 칸을 누르거나,
// 가운데 숫자를 눌러 직접 입력(안드로이드 시간 고르기 창)한다.
// 수면은 시작·끝 바퀴가 나란히 있다. 미래로는 못 가고, 끝이 시작보다 앞서지 않는다.
// [아직 자는 중]을 켜면 끝 없이 넣는다(잠든 시각만 늦게 넣을 때). 깨면 거실 화면의 [잠](깼어요)으로 끝낸다.
//
//   [수유][기저귀][잠]
//   시각  오늘 │ 14 : 05 │        1시간 25분 전
//   (수유량 / 기저귀 종류 / 잠 길이)
//   [닫기] [최근 기록] [저장]

import { $, $$, el, setHidden } from './dom.js';
import { openSheet } from './sheets.js';
import { amountSteppers, amountView } from './amount.js';
import { createWheel } from './wheel.js';
import { DIAPER_BUTTON, KIND, SOURCE, describeRecent, sleepingNow } from '../domain.js';
import { agoParts, clockOnDay, formatClock, formatDay, formatDuration, minutes, pad2 } from '../time.js';

/** 이보다 오래된 시각으로는 못 돌린다 */
const MAX_DAYS_BACK = 7;
const DEFAULT_START_AGO_MIN = 30;
const DEFAULT_SLEEP_MIN = 60;
const UNIT_MS = { day: 86400000, hour: 3600000, minute: 60000 };

/** @param {import('../main.js').AppContext} ctx */
export function setupLateEntry(ctx) {
  const { state, sfx, cfg } = ctx;
  /** 화면에서 고치는 중인 기록 */
  const draft = {
    kind: KIND.FEED,
    start: new Date(),
    end: new Date(),
    amount: 200,
    diaperType: 'pee',
    /** 잠: 끝 없이 넣기(아직 자는 중) */
    ongoing: false,
  };
  const isSleep = () => draft.kind === KIND.SLEEP;

  // ── 시각 고르기 ──
  const limits = () => {
    const max = ctx.now().getTime();
    return { min: max - MAX_DAYS_BACK * UNIT_MS.day, max };
  };
  const clamp = (t) => { const { min, max } = limits(); return Math.min(max, Math.max(min, t)); };

  /** 시작이나 끝을 바꾼다. 수면은 시작이 끝을 넘으면 끝도 밀고, 끝이 시작 앞으로 가면 시작도 당긴다 */
  function setTime(which, t) {
    const next = new Date(clamp(t));
    next.setSeconds(0, 0);
    if (which === 'start') {
      draft.start = next;
      if (draft.end < draft.start) draft.end = new Date(draft.start);
    } else {
      draft.end = next;
      if (draft.end < draft.start) draft.start = new Date(draft.end);
    }
  }

  const FORMAT = {
    day: (d) => formatDay(d, ctx.now()),
    hour: (d) => pad2(d.getHours()),
    minute: (d) => pad2(d.getMinutes()),
  };

  /** 한 묶음: 이름표 + [날짜] [시] : [분] */
  function timeGroup(which) {
    const wheels = ['day', 'hour', 'minute'].map((unit) => createWheel({
      className: unit,
      label: (k) => {
        const t = draft[which].getTime();
        const text = (n) => FORMAT[unit](new Date(clamp(t + n * UNIT_MS[unit])));
        // 끝(지금, 7일 전)에 닿아 같은 글이 되풀이되는 칸은 비운다
        return k !== 0 && text(k) === text(k - Math.sign(k)) ? '' : text(k);
      },
      step: (d) => {
        const before = draft[which].getTime();
        setTime(which, before + d * UNIT_MS[unit]);
        if (draft[which].getTime() === before) return false;
        render({ except: wheelsOf[which][unit] });
        return true;
      },
      onTapStep: () => sfx.tap(),
      onCenterTap: () => typeTime(which),
    }));
    const [day, hour, minute] = wheels;
    wheelsOf[which] = { day, hour, minute };
    const label = el('span', { className: 'lbl' });
    const box = el('div', { className: 'timeGroup', id: `late-${which}` },
      label, day.el, hour.el, el('span', { className: 'colon t24' }, ':'), minute.el);
    return { box, label, refresh: (except) => wheels.forEach((w) => w !== except && w.refresh()) };
  }
  const wheelsOf = { start: null, end: null };
  const groups = { start: timeGroup('start'), end: timeGroup('end') };
  const ago = el('div', { className: 'lateAgo' });
  $('#lateTimes').replaceChildren(groups.start.box, groups.end.box, ago);

  /** 가운데 숫자를 누르면: 안드로이드 시간 고르기 창(키보드로도 입력) */
  const input = $('#lateTimeInput');
  let typing = 'start';
  function typeTime(which) {
    typing = which;
    input.value = `${pad2(draft[which].getHours())}:${pad2(draft[which].getMinutes())}`;
    sfx.tap();
    try { input.showPicker(); } catch (e) { input.focus(); }
  }
  input.addEventListener('change', () => {
    const m = /^(\d{1,2}):(\d{2})/.exec(input.value);
    if (!m) return;
    setTime(typing, clockOnDay(draft[typing], Number(m[1]), Number(m[2]), ctx.now()).getTime());
    render();
  });

  // ── 창 ──
  function open() {
    const now = ctx.now();
    now.setSeconds(0, 0);
    Object.assign(draft, {
      start: new Date(now - minutes(DEFAULT_START_AGO_MIN)),
      end: now,
      amount: state.summary?.last_feed?.ml ?? 200,
      ongoing: false,
    });
    render();
    openSheet('lateSheet');
  }

  /** @param {{except?: object}} [o] 지금 끄는 중인 바퀴는 바퀴가 스스로 다시 그린다 */
  function render({ except } = {}) {
    for (const b of $$('#lateSheet [data-kind]')) b.classList.toggle('on', b.dataset.kind === draft.kind);
    groups.start.label.textContent = isSleep() ? '시작' : '시각';
    groups.end.label.textContent = '끝';
    const open = isSleep() && draft.ongoing;
    setHidden(groups.end.box, !isSleep() || open);
    setHidden(ago, isSleep() && !open);
    groups.start.refresh(except);
    if (isSleep() && !open) groups.end.refresh(except);
    else renderAgo();
    $('#lateDetail').replaceChildren(...detailControls());
    $('#lateSave').disabled = isSleep() && !open && draft.end - draft.start < minutes(1);
  }

  /** 오른쪽: "1시간 25분 전" (숫자 크게) */
  function renderAgo() {
    const parts = agoParts(draft.start, ctx.now());
    ago.setAttribute('aria-label', parts.length ? `${parts.map(([n, u]) => n + u).join(' ')} 전` : '방금');
    ago.replaceChildren(...(parts.length
      ? [...parts.flatMap(([n, u]) => [el('span', { className: 't24 val' }, n), el('span', { className: 'unit' }, u)]), el('span', { className: 'unit' }, '전')]
      : [el('span', { className: 't24 val' }, '방금')]));
  }

  /** 종류별 아랫줄: 수유량 / 기저귀 종류 / 잠 길이 */
  function detailControls() {
    if (draft.kind === KIND.FEED) {
      // 수유 창과 같은 줄: [-10] [-30 브레짜] 200ml 브레짜 180 [+30 브레짜] [+10]
      const steps = amountSteppers({
        get: () => draft.amount,
        set: (ml) => { draft.amount = ml; render(); },
        mixing: cfg,
        tap: sfx.tap,
      });
      return [...steps.before, amountView(draft.amount, cfg, { inline: true }), ...steps.after];
    }
    if (draft.kind === KIND.DIAPER) {
      return Object.entries(DIAPER_BUTTON).map(([type, label]) => el('button', {
        className: `px grow${draft.diaperType === type ? ' on' : ''}`,
        onClick: () => { sfx.tap(); draft.diaperType = type; render(); },
      }, label));
    }
    // 잠: [아직 자는 중] + 잠 길이(또는 안내). 이미 자는 중인 잠이 있으면 하나 더 열 수 없다
    const alreadyOpen = !!sleepingNow(state.summary);
    const toggle = el('button', {
      className: `px${draft.ongoing ? ' on' : ''}`, id: 'lateOngoing', disabled: alreadyOpen && !draft.ongoing,
      onClick: () => { sfx.tap(); draft.ongoing = !draft.ongoing; render(); },
    }, '아직 자는 중');
    return [toggle, draft.ongoing
      ? el('div', { className: 't9 dim' }, '깨면 [잠] 버튼으로 끝내요')
      : el('div', { className: 'sleepLen' }, el('span', { className: 'lbl' }, '잠 길이'), el('span', { className: 't24 val' }, formatDuration(draft.end - draft.start)))];
  }

  function toEvent() {
    const ev = { kind: draft.kind, occurred_at: draft.start, detail: {}, source: SOURCE.TOUCH };
    if (draft.kind === KIND.FEED) ev.amount_ml = draft.amount;
    if (draft.kind === KIND.DIAPER) ev.detail = { type: draft.diaperType };
    if (draft.kind === KIND.SLEEP && !draft.ongoing) ev.ended_at = draft.end;
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
