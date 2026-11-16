// 통계 쪽: 수유·기저귀·잠은 날짜별 막대(7·30·90일), 성장은 성장곡선(기본 나이·교정 나이).
//
//   [수유] [기저귀] [잠] [성장]            [7일] [30일] [90일]
//   하루 평균 865ml · 4.2회                 ← 오늘은 아직 안 끝나서 평균에서 뺀다
//   ▁▃▅▇▅▆▂  막대 = 하루 양, 오늘은 주황, 누르면 그날 기록으로
//   한 번 양 206ml │ 한 번 11분 │ 수유 간격 낮 4시간 14분 …
//
// 숫자는 care_stats()(supabase/003, 최대 92일)가 센다. 날짜 규칙은 베이비타임과 같다(밤잠은 깨는 날).
// 성장은 care_measures()(014)의 기록을 WHO 기준(src/growth.js)에 얹는다.

import { formatDuration } from '../src/time.js';
import { curve, growthAt, daysSince, formatPercentile, DAYS_PER_MONTH } from '../src/growth.js';

const $ = (s) => document.querySelector(s);
const el = (tag, cls, text) => { const n = document.createElement(tag); if (cls) n.className = cls; if (text != null) n.textContent = text; return n; };
const avg = (list, f) => (list.length ? list.reduce((s, d) => s + f(d), 0) / list.length : 0);
const one = (n) => (Math.round(n * 10) / 10).toFixed(1);
const hours = (min) => `${one(min / 60)}시간`;
const median = (list) => { const s = [...list].sort((a, b) => a - b); const m = Math.floor(s.length / 2); return s.length % 2 ? s[m] : (s[m - 1] + s[m]) / 2; };
const poo = (d) => d.diaper_poo + d.diaper_both;
const PERCENTILES = [3, 15, 50, 85, 97];
const SVG = 'http://www.w3.org/2000/svg';

/**
 * 항목마다: 막대 값, 큰 글, 아래 칸들(순수 함수)
 * @param {'feed'|'diaper'|'sleep'} metric
 * @param {object[]} days  care_stats() 결과(날짜 오름차순, 마지막이 오늘)
 * @returns {{headline: string, sub: string, bars: {day: string, value: number, label: string, today: boolean}[], cards: {label: string, value: string, hint: string}[]}}
 */
export function summarize(metric, days) {
  const past = days.slice(0, -1);   // 오늘은 아직 안 끝난 날
  const bar = (f, label) => days.map((d, i) => ({ day: d.day, value: f(d), label: label(d), today: i === days.length - 1 }));
  const none = { headline: '기록 없음', sub: '', cards: [] };
  if (metric === 'feed') {
    const fed = past.filter((d) => d.feed_count > 0);
    const bars = bar((d) => d.feed_ml, (d) => `${d.feed_ml}ml · ${d.feed_count}회`);
    if (!fed.length) return { ...none, bars };
    const ml = fed.reduce((s, d) => s + d.feed_ml, 0);
    const count = fed.reduce((s, d) => s + d.feed_count, 0);
    const timed = fed.filter((d) => d.feed_min != null);
    return {
      headline: `${Math.round(ml / fed.length)}ml`, sub: `하루 ${one(count / fed.length)}회`, bars,
      cards: [
        { label: '한 번 양', value: `${Math.round(ml / count)}ml`, hint: '하루 양 ÷ 횟수' },
        { label: '한 번 걸린 시간', value: timed.length ? `${Math.round(avg(timed, (d) => d.feed_min))}분` : '기록 없음', hint: '끝을 넣은 수유만' },
      ],
    };
  }
  if (metric === 'diaper') {
    const had = past.filter((d) => d.diaper_total > 0);
    const bars = bar((d) => d.diaper_total, (d) => `${d.diaper_total}회 · 대변 ${poo(d)}`);
    if (!had.length) return { ...none, bars };
    return {
      headline: `${one(avg(had, (d) => d.diaper_total))}회`, sub: `대변 하루 ${one(avg(had, poo))}회`, bars,
      cards: [
        { label: '소변만', value: `${one(avg(had, (d) => d.diaper_pee))}회`, hint: '하루 평균' },
        { label: '대변 없는 날', value: `${had.filter((d) => poo(d) === 0).length}일`, hint: `${had.length}일 중` },
      ],
    };
  }
  const slept = past.filter((d) => d.sleep_min > 0);
  const bars = bar((d) => d.sleep_min, (d) => formatDuration(d.sleep_min * 60000));
  if (!slept.length) return { ...none, bars };
  return {
    headline: hours(avg(slept, (d) => d.sleep_min)), sub: '하루 잠', bars,
    cards: [
      { label: '밤잠', value: hours(avg(slept, (d) => d.night_min)), hint: '깨는 날에 센다' },
      { label: '낮잠', value: hours(avg(slept, (d) => d.nap_min)), hint: '하루 평균' },
    ],
  };
}

/**
 * 수유 간격의 가운데 값을 시간대별로(순수 함수). 요약의 feed_gaps = [[앞 수유 시(0~23), 간격 분], …](최근 14일)
 * @returns {{label: string, text: string, minutes: number}[]}
 */
export function gapsByPeriod(gaps, periods) {
  const inPeriod = (h, p) => (p.from <= p.to ? h >= p.from && h < p.to : h >= p.from || h < p.to);
  return periods.map((p) => {
    const mine = (gaps || []).filter(([h]) => inPeriod(h, p)).map(([, g]) => g);
    return mine.length >= 3 ? { label: p.label, minutes: median(mine), text: formatDuration(median(mine) * 60000) } : null;
  }).filter(Boolean);
}

/**
 * 성장곡선 그림에 필요한 좌표(순수 함수). 가로 = 개월, 세로 = 값.
 * @param {{kind: 'weight'|'height', measures: {kind: string, at: string, value: number}[], baby: {birth_date: string, due_date?: string|null, sex?: string|null}, w: number, h: number}} o
 */
export function growthChart({ kind, measures, baby, w, h }) {
  const mine = measures.filter((m) => m.kind === kind && m.value != null).sort((a, b) => new Date(a.at) - new Date(b.at));
  const month = (date, at) => daysSince(date, at) / DAYS_PER_MONTH;
  const actual = mine.map((m) => [month(baby.birth_date, m.at), Number(m.value)]);
  const corrected = baby.due_date ? mine.map((m) => [month(baby.due_date, m.at), Number(m.value)]).filter(([x]) => x >= 0) : [];
  const lastMonth = Math.max(0, ...actual.map(([x]) => x));
  const months = Math.min(24, Math.max(6, Math.ceil(lastMonth) + 2));
  const lines = baby.sex ? PERCENTILES.map((p) => ({ pct: p, points: curve(kind, baby.sex, p, { months }) })) : [];
  const values = [...lines.flatMap((l) => l.points.map(([, v]) => v)), ...actual.map(([, v]) => v)];
  const lo = values.length ? Math.floor(Math.min(...values)) : 0;
  const hi = values.length ? Math.ceil(Math.max(...values)) : 1;
  const pad = { l: 30, r: 26, t: 8, b: 20 };
  const X = (m) => pad.l + (m / months) * (w - pad.l - pad.r);
  const Y = (v) => h - pad.b - ((v - lo) / (hi - lo || 1)) * (h - pad.t - pad.b);
  const path = (pts) => pts.map(([m, v]) => `${X(m).toFixed(1)},${Y(v).toFixed(1)}`).join(' ');
  const stepY = (hi - lo) > 12 ? 5 : (hi - lo) > 6 ? 2 : 1;
  const yTicks = []; for (let v = Math.ceil(lo / stepY) * stepY; v <= hi; v += stepY) yTicks.push({ v, y: Y(v) });
  const xTicks = []; for (let m = 0; m <= months; m += months > 12 ? 4 : 2) xTicks.push({ m, x: X(m) });
  return {
    months, lo, hi, yTicks, xTicks,
    lines: lines.map((l) => ({ pct: l.pct, path: path(l.points), endY: Y(l.points[l.points.length - 1][1]) })),
    actual: actual.map(([m, v]) => ({ x: X(m), y: Y(v) })), actualPath: path(actual),
    corrected: corrected.map(([m, v]) => ({ x: X(m), y: Y(v) })), correctedPath: path(corrected),
    last: mine[mine.length - 1] || null, prev: mine[mine.length - 2] || null,
  };
}

/**
 * 그날의 나이 글 "4개월 28일"(순수 함수). 화면의 나이 줄(베이비타임 방식, supabase/006 care_age)과 같게 센다:
 * 개월 = 기준일에 몇 달을 더해도 그날을 넘지 않는 가장 큰 수, 일 = 그날 - (기준일 + 개월) + 1
 * @param {string} from 'YYYY-MM-DD'(생일 또는 예정일)
 * @param {Date|string} at
 */
export function ageText(from, at) {
  const [y, m, d] = from.split('-').map(Number);
  const on = new Date(at);
  const day = new Date(on.getFullYear(), on.getMonth(), on.getDate());
  // 31일에 태어난 아기의 '한 달 뒤'가 다음다음 달로 넘어가지 않게 그 달의 끝 날로 맞춘다
  const plus = (n) => { const last = new Date(y, m - 1 + n + 1, 0).getDate(); return new Date(y, m - 1 + n, Math.min(d, last)); };
  let months = (day.getFullYear() - y) * 12 + (day.getMonth() - (m - 1));
  if (plus(months) > day) months -= 1;
  if (months < 0) return '';
  return `${months}개월 ${Math.round((day - plus(months)) / 86400000) + 1}일`;
}

/** @param {{api: object, cfg: object, state: {summary: object|null}, now: () => Date, openDay: (day: string) => void, openEntry: (kind: string) => void}} ctx */
export function setupStats(ctx) {
  let metric = 'feed';
  let range = 7;
  let growthKind = 'weight';
  let days = null;
  let measures = null;
  let seq = 0;

  function renderTabs() {
    for (const b of document.querySelectorAll('#statTabs [data-metric]')) b.classList.toggle('on', b.dataset.metric === metric);
    for (const b of document.querySelectorAll('#statRange [data-days]')) b.classList.toggle('on', Number(b.dataset.days) === range);
    for (const b of document.querySelectorAll('#growthKinds [data-kind]')) b.classList.toggle('on', b.dataset.kind === growthKind);
    $('#statRange').hidden = metric === 'growth';
    $('#statDays').hidden = metric === 'growth';
    $('#statGrowth').hidden = metric !== 'growth';
  }

  const card = (c) => { const n = el('div', 'stat'); n.append(el('div', 'hint', c.label), el('div', 'val', c.value), el('div', 'hint', c.hint)); return n; };

  function renderDays() {
    if (!days) return;
    const s = summarize(metric, days);
    $('#statHeadline').textContent = s.headline;
    $('#statSub').textContent = s.sub ? `${s.sub} · 지난 ${days.length - 1}일 평균(오늘 빼고)` : '';
    const max = Math.max(1, ...s.bars.map((b) => b.value));
    $('#statBars').className = `bars n${range}`;
    $('#statBars').replaceChildren(...s.bars.map((b) => {
      const btn = el('button', `bar${b.today ? ' today' : ''}`);
      btn.setAttribute('aria-label', `${b.day.slice(5).replace('-', '/')} ${b.label}`);
      const fill = el('span', 'fill');
      fill.style.height = `${Math.round((b.value / max) * 100)}%`;
      btn.append(fill);
      btn.addEventListener('click', () => ctx.openDay(b.day));
      return btn;
    }));
    const first = s.bars[0]?.day.slice(5).replace('-', '/') ?? '';
    $('#statAxis').replaceChildren(el('span', '', first), el('span', '', '막대를 누르면 그날 기록'), el('span', '', '오늘'));
    const cards = s.cards.map(card);
    if (metric === 'feed') {
      const gaps = gapsByPeriod(ctx.state.summary?.feed_gaps, ctx.cfg.feedPeriods);
      if (gaps.length) {
        const g = el('div', 'stat wide');
        g.append(el('div', 'hint', '수유 간격(가운데 값, 최근 14일)'));
        const longest = Math.max(...gaps.map((x) => x.minutes));
        for (const x of gaps) {
          const row = el('div', 'gap');
          const track = el('span', 'track'); const fill = el('span', 'fill'); fill.style.width = `${Math.round((x.minutes / longest) * 100)}%`; track.append(fill);
          row.append(el('span', '', x.label), track, el('span', 'val', x.text));
          g.append(row);
        }
        cards.push(g);
      }
    }
    $('#statCards').replaceChildren(...cards);
  }

  function svg(tag, attrs, text) {
    const n = document.createElementNS(SVG, tag);
    for (const [k, v] of Object.entries(attrs)) n.setAttribute(k, String(v));
    if (text != null) n.textContent = text;
    return n;
  }

  function renderGrowth() {
    if (!measures) return;
    const baby = measures.baby || {};
    const unit = growthKind === 'weight' ? 'kg' : 'cm';
    const W = 340; const H = 240;
    const c = growthChart({ kind: growthKind, measures: measures.measures, baby, w: W, h: H });
    const g = $('#growthSvg');
    g.setAttribute('viewBox', `0 0 ${W} ${H}`);
    g.setAttribute('aria-label', `${growthKind === 'weight' ? '체중' : '키'} 성장곡선: 또래 백분위 줄과 잰 값`);
    const nodes = [];
    for (const t of c.yTicks) nodes.push(svg('line', { x1: 30, x2: W - 26, y1: t.y, y2: t.y, class: 'grid' }), svg('text', { x: 26, y: t.y + 3, 'text-anchor': 'end', class: 'tick' }, t.v));
    for (const t of c.xTicks) nodes.push(svg('text', { x: t.x, y: H - 5, 'text-anchor': 'middle', class: 'tick' }, `${t.m}개월`));
    for (const l of c.lines) nodes.push(svg('polyline', { points: l.path, class: l.pct === 50 ? 'pct mid' : 'pct' }), svg('text', { x: W - 23, y: l.endY + 3, class: 'tick' }, l.pct));
    if (c.corrected.length) nodes.push(svg('polyline', { points: c.correctedPath, class: 'line corrected' }));
    if (c.actual.length) nodes.push(svg('polyline', { points: c.actualPath, class: 'line actual' }));
    for (const p of c.corrected) nodes.push(svg('circle', { cx: p.x, cy: p.y, r: 3.5, class: 'dot corrected' }));
    for (const p of c.actual) nodes.push(svg('circle', { cx: p.x, cy: p.y, r: 3.5, class: 'dot actual' }));
    g.replaceChildren(...nodes);

    $('#growthNote').textContent = !baby.sex ? '성별이 없어 또래 곡선을 그리지 못했어요' : !c.last ? '아직 잰 기록이 없어요. [+ 측정 넣기]로 넣어 주세요' : '';
    const box = $('#growthLast');
    if (!c.last) { box.replaceChildren(); return; }
    const when = new Date(c.last.at);
    const diff = c.prev ? Number(c.last.value) - Number(c.prev.value) : null;
    const digits = growthKind === 'weight' ? 2 : 1;
    const head = el('div', 'head');
    head.append(el('span', 'label', `마지막 측정 · ${when.getMonth() + 1}월 ${when.getDate()}일`),
      el('span', 'detail', diff == null ? '' : `지난번보다 ${diff >= 0 ? '+' : ''}${diff.toFixed(digits)}${unit}`));
    const r = growthAt({ kind: growthKind, value: Number(c.last.value), at: c.last.at, birth: baby.birth_date, due: baby.due_date, sex: baby.sex });
    const two = el('div', 'two');
    const pctCard = (title, cls, x) => { const n = el('div', `stat ${cls}`); n.append(el('div', 'hint', title), el('div', 'val', x ? `백분위 ${formatPercentile(x.pct)}` : '셈할 수 없음'), el('div', 'hint', x ? `또래 100명 중 ${formatPercentile(x.pct)}번째` : '')); return n; };
    two.append(pctCard(`기본${r.actual ? ` · ${ageText(baby.birth_date, c.last.at)}` : ''}`, 'actual', r.actual),
      pctCard(`교정${r.corrected ? ` · ${ageText(baby.due_date, c.last.at)}` : ''}`, 'corrected', r.corrected));
    box.replaceChildren(head, el('div', 'big', `${Number(c.last.value).toFixed(digits)}${unit}`), two);
  }

  async function load() {
    renderTabs();
    const mine = ++seq;
    $('#statMsg').textContent = '';
    try {
      if (metric === 'growth') {
        const got = await ctx.api.getMeasures();
        if (mine !== seq) return;
        measures = got;
        renderGrowth();
      } else {
        const got = await ctx.api.getStats(range + 1);   // 오늘 + 지난 n일
        if (mine !== seq) return;
        days = got;
        renderDays();
      }
    } catch (e) {
      if (mine !== seq) return;
      $('#statMsg').textContent = '통계를 못 받았어요. 연결을 확인해 주세요';
    }
  }

  for (const b of document.querySelectorAll('#statTabs [data-metric]')) b.addEventListener('click', () => { metric = b.dataset.metric; load(); });
  for (const b of document.querySelectorAll('#statRange [data-days]')) b.addEventListener('click', () => { range = Number(b.dataset.days); load(); });
  for (const b of document.querySelectorAll('#growthKinds [data-kind]')) b.addEventListener('click', () => { growthKind = b.dataset.kind; renderTabs(); renderGrowth(); });
  $('#growthAdd').addEventListener('click', () => ctx.openEntry(growthKind));

  return { show: load, reload: load };
}
