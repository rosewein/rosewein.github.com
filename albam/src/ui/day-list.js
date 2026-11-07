// 그날 기록 목록. 타임라인의 날짜 줄을 누르거나 지난 기록 넣기의 [최근 기록]으로 연다.
// 줄이 크고(22px) 하나를 누르면 그 기록을 고치는 창(late-entry.js 의 openEdit)이 열린다.
//
//   오늘 기록 (11/7)                      ← 위아래로 끌어 넘긴다(마우스 휠도)
//   06:03   수유 200ml
//   06:05~07:50   잠 1시간 45분
//   08:30   기저귀 소변+대변   (대기)
//   [닫기] [◀ 전날] [다음날 ▶]
//
// 날짜는 타임라인과 같은 최근 3일(getTimeline). 아직 못 보낸 기록도 얹는다.

import { $, el, setHidden } from './dom.js';
import { openSheet } from './sheets.js';
import { LOGICAL } from './stage.js';
import { mergePending } from './timeline.js';
import { DIAPER_LABEL, describeOther, isBuiltinKind } from '../domain.js';
import { formatClock, formatDay, formatDuration } from '../time.js';

const DAYS = 3;
/** 이보다 덜 움직이고 떼면 누름(논리 픽셀) */
const TAP_SLOP = 4;

/**
 * 그날(하루 끊는 시각 기준) 기록만, 시각 순으로(순수 함수). 자정 넘어 이어진 잠은 시작한 날에 둔다
 * @param {import('./timeline.js').TimelineEvent[]} events
 * @param {Date} now
 * @param {number} back  0 = 오늘, 1 = 어제
 * @param {number} [dayStartHour]
 */
export function eventsOfDay(events, now, back, dayStartHour = 0) {
  const start = new Date(now);
  if (start.getHours() < dayStartHour) start.setDate(start.getDate() - 1);
  start.setHours(dayStartHour, 0, 0, 0);
  start.setDate(start.getDate() - back);
  const end = new Date(start); end.setDate(start.getDate() + 1);
  return {
    start,
    list: events.filter((e) => { const t = new Date(e.at); return t >= start && t < end; })
      .sort((a, b) => new Date(a.at) - new Date(b.at)),
  };
}

/** 목록 한 줄 글(순수 함수): ["06:03", "수유 200ml"] */
export function describeRow(e, now) {
  if (e.kind === 'sleep') {
    const time = e.ended_at ? `${formatClock(e.at)}~${formatClock(e.ended_at)}` : `${formatClock(e.at)}~`;
    return [time, e.ended_at ? `잠 ${formatDuration(new Date(e.ended_at) - new Date(e.at))}` : `잠 (자는 중 ${formatDuration(now - new Date(e.at))})`];
  }
  if (e.kind === 'feed') {
    if (e.ended_at) return [`${formatClock(e.at)}~${formatClock(e.ended_at)}`, `수유 ${e.ml ?? ''}ml · ${formatDuration(new Date(e.ended_at) - new Date(e.at))}`];
    if (e.feeding) return [`${formatClock(e.at)}~`, `수유 ${e.ml ?? ''}ml (먹는 중 ${formatDuration(now - new Date(e.at))})`];
    return [formatClock(e.at), `수유 ${e.ml ?? ''}ml`];
  }
  if (e.kind === 'diaper') return [formatClock(e.at), `기저귀 ${DIAPER_LABEL[e.type] || ''}`];
  if (!isBuiltinKind(e.kind)) {
    const time = e.ended_at ? `${formatClock(e.at)}~${formatClock(e.ended_at)}` : formatClock(e.at);
    return [time, describeOther(e.kind, { value: e.value, at: e.at, ended_at: e.ended_at, detail: { ...(e.detail || {}), ...(e.memo && { memo: e.memo }) } })];
  }
  return [formatClock(e.at), e.kind];
}

/**
 * @param {import('../main.js').AppContext} ctx
 * @param {{onEdit: (e: import('./timeline.js').TimelineEvent) => void}} o
 */
export function setupDayList(ctx, { onEdit }) {
  const list = $('#recentList');
  let back = 0;
  /** @type {import('./timeline.js').TimelineEvent[]} */
  let events = [];

  async function open(dayBack = 0) {
    back = dayBack;
    render();
    openSheet('recentSheet');
    try {
      events = await ctx.api.getTimeline(DAYS);
    } catch (e) {
      try { events = JSON.parse(localStorage.getItem(ctx.api.demo ? 'albam.demo.timeline' : 'albam.timeline') || '[]'); } catch (x) { events = []; }
    }
    render({ toEnd: back === 0 });
  }

  function render({ toEnd = false } = {}) {
    const now = ctx.now();
    const all = mergePending(events, ctx.state.summary?.recent);
    const pendingIds = new Set((ctx.state.summary?.recent || []).filter((r) => r.pending).map((r) => r.id));
    const { start, list: rows } = eventsOfDay(all, now, back, ctx.state.summary?.settings?.day_start_hour ?? 0);
    $('#recentTitle').textContent = `${formatDay(start, now)} 기록 (${start.getMonth() + 1}/${start.getDate()}) · 눌러서 고치기`;
    list.replaceChildren(...(rows.length ? rows.map((e) => {
      const [time, what] = describeRow(e, now);
      return el('button', { className: 'dayRow', onClick: () => { if (!dragged) { ctx.sfx.tap(); onEdit(e); } } },
        el('span', { className: 'tm' }, time), el('span', { className: 'what' }, what),
        ...(pendingIds.has(e.id) ? [el('span', { className: 'acc t9' }, '대기')] : []));
    }) : [el('div', { className: 'dim empty' }, '기록이 없어요')]));
    $('#dayPrev').disabled = back >= DAYS - 1;
    $('#dayNext').disabled = back <= 0;
    if (toEnd) list.scrollTop = list.scrollHeight;   // 오늘은 가장 최근 것이 보이게
  }

  // 위아래로 끌어 넘기기(거실 화면은 기본 스크롤을 꺼 두었다)
  let drag = null;
  let dragged = false;
  list.addEventListener('pointerdown', (e) => {
    const unit = $('#stage').getBoundingClientRect().width / LOGICAL.width;
    drag = { y: e.clientY, top: list.scrollTop, unit };
    dragged = false;
  });
  list.addEventListener('pointermove', (e) => {
    if (!drag) return;
    const dy = (e.clientY - drag.y) / drag.unit;
    if (Math.abs(dy) >= TAP_SLOP) dragged = true;
    if (dragged) list.scrollTop = drag.top - (e.clientY - drag.y);
  });
  const end = () => { drag = null; setTimeout(() => { dragged = false; }, 0); };
  list.addEventListener('pointerup', end);
  list.addEventListener('pointercancel', end);
  list.addEventListener('wheel', (e) => { e.preventDefault(); list.scrollTop += e.deltaY; }, { passive: false });

  $('#dayPrev').addEventListener('click', () => { ctx.sfx.tap(); back = Math.min(DAYS - 1, back + 1); render(); list.scrollTop = 0; });
  $('#dayNext').addEventListener('click', () => { ctx.sfx.tap(); back = Math.max(0, back - 1); render({ toEnd: back === 0 }); });
  setHidden(list, false);

  return { open };
}
