// 지난 기록 넣기(시각을 고쳐 넣기)와 기록 고치기. 같은 창을 쓴다.
//   - 넣기: [시계] 버튼 → 종류 고르고 시각·양 → [저장]
//   - 고치기: 그날 기록 목록(day-list.js)에서 하나를 누르면 openEdit(기록) → [저장] / [지우기](두 번 눌러야 지움)
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
import { DIAPER_BUTTON, KIND, SOURCE, sleepingNow } from '../domain.js';
import { agoParts, clockOnDay, formatDay, formatDuration, minutes, pad2 } from '../time.js';

/** 이보다 오래된 시각으로는 못 돌린다 */
const MAX_DAYS_BACK = 7;
const DEFAULT_START_AGO_MIN = 30;
const DEFAULT_SLEEP_MIN = 60;
/** 수유 끝 시각을 처음 켤 때 시작 뒤 몇 분으로 둘지(최근 걸린 시간 중간값 약 10분) */
const DEFAULT_FEED_MIN = 10;
const UNIT_MS = { day: 86400000, hour: 3600000, minute: 60000 };

const KIND_LABEL = { feed: '수유', diaper: '기저귀', sleep: '잠' };
/** [지우기]를 한 번 누르면 이 시간 동안 "한 번 더 누르면 지워요" */
const DELETE_CONFIRM_MS = 3000;

/**
 * @param {import('../main.js').AppContext} ctx
 * @param {{openDayList: (back: number) => void}} o
 */
export function setupLateEntry(ctx, { openDayList }) {
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
    /** 수유: 다 먹은 시각도 넣기 */
    feedEnd: false,
    /** 수유: 먹이는 중인 기록을 고치는 중 */
    feeding: false,
  };
  /** 고치는 중인 기록(넣기면 null) */
  let editing = null;
  let deleteArmedUntil = 0;
  const isSleep = () => draft.kind === KIND.SLEEP;
  /** 시작·끝 두 묶음을 보이나: 잠(끝을 넣을 때), 수유(끝 시각을 켰을 때) */
  const hasEnd = () => (isSleep() && !draft.ongoing) || (draft.kind === KIND.FEED && draft.feedEnd);

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
    editing = null;
    Object.assign(draft, {
      start: new Date(now - minutes(DEFAULT_START_AGO_MIN)),
      end: now,
      amount: state.summary?.last_feed?.ml ?? 200,
      ongoing: false,
      feedEnd: false,
      feeding: false,
    });
    render();
    openSheet('lateSheet');
  }

  /** 기록 고치기: 그날 기록 목록에서 누른 기록으로 창을 채운다 */
  function openEdit(ev) {
    const now = ctx.now();
    editing = ev;
    deleteArmedUntil = 0;
    Object.assign(draft, {
      kind: ev.kind,
      start: new Date(ev.at),
      end: ev.ended_at ? new Date(ev.ended_at) : (ev.kind === KIND.FEED ? new Date(Math.min(now.getTime(), new Date(ev.at).getTime() + minutes(DEFAULT_FEED_MIN))) : now),
      ongoing: ev.kind === KIND.SLEEP && !ev.ended_at,
      feedEnd: ev.kind === KIND.FEED && !!ev.ended_at,
      feeding: ev.kind === KIND.FEED && !ev.ended_at && !!ev.feeding,
      amount: ev.ml ?? state.summary?.last_feed?.ml ?? 200,
      diaperType: ev.type || 'pee',
    });
    render();
    openSheet('lateSheet');
  }

  /** @param {{except?: object}} [o] 지금 끄는 중인 바퀴는 바퀴가 스스로 다시 그린다 */
  function render({ except } = {}) {
    for (const b of $$('#lateSheet [data-kind]')) {
      b.classList.toggle('on', b.dataset.kind === draft.kind);
      setHidden(b, !!editing && b.dataset.kind !== draft.kind);   // 고칠 때는 종류를 못 바꾼다
    }
    $('#lateTitle').textContent = editing ? `기록 고치기 · ${KIND_LABEL[draft.kind] || draft.kind}` : '지난 기록 넣기';
    setHidden($('#recentBtn'), !!editing);
    setHidden($('#lateDelete'), !editing);
    const armed = Date.now() < deleteArmedUntil;
    $('#lateDelete').textContent = armed ? '한 번 더 누르면 지워요' : '지우기';
    $('#lateDelete').classList.toggle('warn', armed);
    groups.start.label.textContent = hasEnd() || isSleep() ? '시작' : '시각';
    groups.end.label.textContent = '끝';
    setHidden(groups.end.box, !hasEnd());
    setHidden(ago, hasEnd());
    groups.start.refresh(except);
    if (hasEnd()) groups.end.refresh(except);
    else renderAgo();
    // 수유: [끝 시각] 켜기/끄기
    const feedEndBtn = $('#lateFeedEnd');
    setHidden(feedEndBtn, draft.kind !== KIND.FEED);
    feedEndBtn.classList.toggle('on', draft.feedEnd);
    $('#lateDetail').replaceChildren(...detailControls());
    $('#lateSave').disabled = hasEnd() && draft.end - draft.start < minutes(1);
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
    const openSleep = sleepingNow(state.summary);
    const alreadyOpen = !!openSleep && openSleep.id !== editing?.id;
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
    if (draft.kind === KIND.FEED) {
      ev.amount_ml = draft.amount;
      if (draft.feedEnd) ev.ended_at = draft.end;
    }
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
  $('#lateFeedEnd').addEventListener('click', () => {
    sfx.tap();
    draft.feedEnd = !draft.feedEnd;
    if (draft.feedEnd && draft.end - draft.start < minutes(1)) {
      draft.end = new Date(Math.min(ctx.now().getTime(), draft.start.getTime() + minutes(DEFAULT_FEED_MIN)));
    }
    render();
  });
  $('#lateSave').addEventListener('click', () => {
    if (!editing) { ctx.save(toEvent()); return; }
    const ev = toEvent();
    const patch = { occurred_at: ev.occurred_at };
    if (draft.kind === KIND.FEED) {
      patch.amount_ml = ev.amount_ml;
      // 끝 시각을 넣으면 먹이는 중이 끝난다. 안 넣으면 그대로(먹이는 중이면 계속 먹이는 중)
      patch.ended_at = draft.feedEnd ? draft.end : null;
      if (draft.feedEnd) patch.detail = { feeding: false };
    }
    if (draft.kind === KIND.DIAPER) patch.detail = ev.detail;
    if (draft.kind === KIND.SLEEP) patch.ended_at = ev.ended_at ?? null;
    ctx.update(editing.id, patch, ev);
  });
  $('#lateDelete').addEventListener('click', () => {
    if (!editing) return;
    if (Date.now() < deleteArmedUntil) { ctx.remove(editing.id, toEvent()); return; }
    sfx.tap();
    deleteArmedUntil = Date.now() + DELETE_CONFIRM_MS;
    render();
    setTimeout(render, DELETE_CONFIRM_MS + 50);
  });
  // 그날 기록 목록(눌러서 고치기). 여기서는 오늘
  $('#recentBtn').addEventListener('click', () => { sfx.tap(); openDayList(0); });

  return { openEdit };
}
