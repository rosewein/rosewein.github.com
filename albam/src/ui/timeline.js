// 타임라인 쪽: 최근 3일을 한 줄씩(0~24시) 그려 빼먹은 기록이 없는지 한눈에 본다.
//
//   타임라인  ▮수유 ▬잠 ▪소변 ▪대변
//          0     6     12     18     24
//   오늘   │200    200      200            ← 수유: 주황 세로줄 + 양
//          ▬▬▬▬▬         ▬▬    ┊           ← 잠: 파란 막대(자는 중이면 지금까지), ┊ 지금
//          ▪   ▪     ▪                     ← 기저귀: 소변(밝은 네모) / 대변 있음(갈색 네모)
//   어제   …
// 날짜 줄을 누르면 그날 기록 목록이 뜬다(day-list.js). 거기서 하나를 눌러 고치거나 지운다.
//
// 숫자는 Supabase care_timeline() 이 준다(supabase/005_timeline.sql). 아직 못 보낸 기록은 요약의 recent 에서 얹는다.

import { $, el } from './dom.js';
import { formatDay } from '../time.js';

const HOUR = 3600000;
/** 줄에서 시간 칸이 차지하는 폭(논리 픽셀) */
const TRACK = 300;
/** 수유량 글자끼리 이보다 가까우면 뒤의 것은 글자를 뺀다(논리 픽셀) */
const LABEL_GAP = 18;

/**
 * @typedef {Object} TimelineEvent
 * @property {string} id
 * @property {string} kind
 * @property {string} at
 * @property {string|null} [ended_at]
 * @property {number|null} [ml]
 * @property {string|null} [type]   기저귀 종류
 */

/**
 * @typedef {Object} TimelineRow
 * @property {string} label            "오늘", "어제", "11/5"
 * @property {Date} start              줄의 0시(하루 끊는 시각)
 * @property {{from: number, to: number, open: boolean}[]} sleeps   시간(0~24)
 * @property {{at: number, ml: number|null, label: boolean}[]} feeds
 * @property {{at: number, poo: boolean}[]} diapers
 * @property {number|null} now         오늘 줄이면 지금 시간(0~24)
 */

/**
 * 기록을 날짜 줄로 나눈다(순수 함수). 맨 위가 오늘.
 * @param {TimelineEvent[]} events
 * @param {Date} now
 * @param {{days?: number, dayStartHour?: number}} [o]
 * @returns {TimelineRow[]}
 */
export function layoutTimeline(events, now, { days = 3, dayStartHour = 0 } = {}) {
  const today = new Date(now);
  if (today.getHours() < dayStartHour) today.setDate(today.getDate() - 1);
  today.setHours(dayStartHour, 0, 0, 0);
  const pxPerHour = TRACK / 24;
  const rows = [];
  for (let i = 0; i < days; i += 1) {
    const start = new Date(today); start.setDate(today.getDate() - i);
    const end = new Date(start); end.setDate(start.getDate() + 1);
    const hours = (t) => (t - start) / HOUR;
    const inRow = (t) => t >= start && t < end;
    const row = { label: formatDay(start, now), start, sleeps: [], feeds: [], diapers: [], now: i === 0 ? hours(now) : null };
    for (const e of events) {
      const at = new Date(e.at);
      if (e.kind === 'sleep') {
        const to = e.ended_at ? new Date(e.ended_at) : now;
        if (to <= start || at >= end) continue;
        row.sleeps.push({ from: Math.max(0, hours(at)), to: Math.min(24, hours(to)), open: !e.ended_at });
      } else if (e.kind === 'feed' && inRow(at)) {
        row.feeds.push({ at: hours(at), ml: e.ml ?? null, label: true });
      } else if (e.kind === 'diaper' && inRow(at)) {
        row.diapers.push({ at: hours(at), poo: e.type === 'poo' || e.type === 'both' });
      }
    }
    row.feeds.sort((a, b) => a.at - b.at);
    let lastLabel = -Infinity;
    for (const f of row.feeds) {
      f.label = (f.at - lastLabel) * pxPerHour >= LABEL_GAP;
      if (f.label) lastLabel = f.at;
    }
    rows.push(row);
  }
  return rows;
}

/** 서버 기록 + 아직 못 보낸 기록(요약의 recent 중 pending) */
export function mergePending(events, recent = []) {
  const ids = new Set(events.map((e) => e.id));
  const extra = recent.filter((r) => r.pending && !ids.has(r.id))
    .map((r) => ({ id: r.id, kind: r.kind, at: r.at, ended_at: r.ended_at ?? null, ml: r.ml ?? null, type: r.detail?.type ?? null }));
  // 못 보낸 '깼어요'가 있으면 요약 쪽 끝 시각을 따른다
  const ends = new Map(recent.filter((r) => r.kind === 'sleep').map((r) => [r.id, r.ended_at ?? null]));
  return [...events.map((e) => (e.kind === 'sleep' && ends.has(e.id) ? { ...e, ended_at: ends.get(e.id) } : e)), ...extra];
}

/** @param {import('../main.js').AppContext} ctx */
export function setupTimeline(ctx) {
  const cacheKey = () => (ctx.api.demo ? 'albam.demo.timeline' : 'albam.timeline');
  let events = readCache();
  let note = '';
  let visible = false;

  function readCache() {
    try { return JSON.parse(localStorage.getItem(cacheKey()) || 'null'); } catch (e) { return null; }
  }

  const x = (h) => `${(h / 24) * TRACK}px`;

  function render() {
    $('#timelineNote').textContent = note;
    const all = mergePending(events || [], ctx.state.summary?.recent);
    const rows = layoutTimeline(all, ctx.now(), { days: 3, dayStartHour: ctx.state.summary?.settings?.day_start_hour ?? 0 });
    // 줄 전체가 버튼: 누르면 그날 기록 목록(눌러서 고치기)
    $('#timelineRows').replaceChildren(...rows.map((r, i) => el('button', { className: 'tlRow', onClick: () => { ctx.sfx.tap(); ctx.openDayList(i); } },
      el('div', { className: `tlLabel${r.now != null ? ' acc' : ''}` }, r.label),
      el('div', { className: 'tlTrack' },
        el('div', { className: 'tlBand' }),
        ...(r.now != null ? [el('div', { className: 'tlFuture', style: { left: x(r.now), width: x(24 - r.now) } })] : []),
        ...r.sleeps.map((s) => el('div', { className: `tlSleep${s.open ? ' open' : ''}`, style: { left: x(s.from), width: x(Math.max(0.15, s.to - s.from)) } })),
        ...r.feeds.flatMap((f) => [
          el('div', { className: 'tlFeed', style: { left: x(f.at) } }),
          ...(f.label && f.ml != null ? [el('div', { className: 'tlMl t9', style: { left: x(f.at) } }, String(f.ml))] : []),
        ]),
        ...r.diapers.map((d) => el('div', { className: `tlDiaper${d.poo ? ' poo' : ''}`, style: { left: x(d.at) } })),
        ...(r.now != null ? [el('div', { className: 'tlNow', style: { left: x(r.now) } })] : []),
      ))));
  }

  async function load() {
    if (!ctx.api.isLoggedIn()) return;
    render();
    try {
      events = await ctx.api.getTimeline(3);
      note = '';
      try { localStorage.setItem(cacheKey(), JSON.stringify(events)); } catch (e) { /* 캐시는 없어도 됨 */ }
    } catch (e) {
      note = events ? '연결 안 됨 · 지난번 기록' : '연결 안 됨';
    }
    render();
  }

  // 보이는 동안: 요약을 다시 받을 때마다(20초, 저장 직후) 같이 다시 받는다 → 다른 기기 기록, 지금 선
  let loading = false;
  async function onSummary() {
    if (!visible || loading) return;
    loading = true;
    try { await load(); } finally { loading = false; }
  }

  return {
    load,
    render,
    onSummary,
    show() { visible = true; load(); },
    hide() { visible = false; },
  };
}
