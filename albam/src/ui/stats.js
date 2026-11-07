// 통계 화면(두 번째 쪽): 최근 7일 막대그래프. 수유·기저귀·잠을 위쪽 탭으로 바꾼다.
// 숫자는 Supabase care_stats() 가 센다(베이비타임에서 옮긴 기록 + 거실 화면 기록).
// 날짜 규칙은 베이비타임 통계와 같다: 밤잠은 깨는 아침의 날에 센다(supabase/003_stats.sql).
//
//   최근 7일                         [수유][기저귀][잠]
//    830ml  850ml  …                          ← 막대 위 값
//    ███    ███    …   ▯ (오늘은 아직 안 끝나서 테두리만)
//    11/1   11/2   …   오늘
//   지난 6일 평균 4.9회 · 830ml

import { $, $$, el } from './dom.js';

/** 막대 가장 긴 것(논리 픽셀) */
const BAR_MAX = 46;

/**
 * @typedef {Object} Column
 * @property {string} label    "11/6", 마지막 날은 "오늘"
 * @property {string} value    막대 위 글 "850ml"
 * @property {number} height   막대 전체 높이(px)
 * @property {number} part     막대 아래쪽 강조 부분 높이(대변 있는 기저귀, 낮잠). 없으면 0
 * @property {boolean} today
 */

const avg = (list, f) => (list.length ? list.reduce((s, d) => s + f(d), 0) / list.length : 0);
const one = (n) => (Math.round(n * 10) / 10).toFixed(1);
const hm = (min) => {
  const m = Math.round(min);
  return `${Math.floor(m / 60)}시간${m % 60 ? ` ${m % 60}분` : ''}`;
};

/** 항목마다: 막대 값, 강조 부분, 막대 위 글, 아래 평균 글 */
const METRICS = {
  feed: {
    value: (d) => d.feed_ml,
    part: () => 0,
    text: (d) => `${d.feed_ml}ml`,
    foot: (past) => [['지난 6일 평균 ', ''], [`${one(avg(past, (d) => d.feed_count))}회 · ${Math.round(avg(past, (d) => d.feed_ml))}ml`, 'val']],
  },
  diaper: {
    value: (d) => d.diaper_total,
    part: (d) => d.diaper_poo + d.diaper_both,
    text: (d) => `${d.diaper_total}회`,
    foot: (past) => [['지난 6일 평균 ', ''], [`${one(avg(past, (d) => d.diaper_total))}회`, 'val'],
      [' · ', ''], ['대변', 'acc'], [` ${one(avg(past, (d) => d.diaper_poo + d.diaper_both))}회`, 'val']],
  },
  sleep: {
    value: (d) => d.sleep_min,
    part: (d) => d.nap_min ?? 0,
    text: (d) => `${one(d.sleep_min / 60)}시간`,
    foot: (past) => [['평균 ', ''], ['낮잠', 'acc'], [` ${hm(avg(past, (d) => d.nap_min ?? 0))}`, 'val'],
      [' · 밤잠 ', ''], [hm(avg(past, (d) => d.night_min ?? 0)), 'val']],
  },
};

/**
 * 그래프 그릴 값 만들기(순수 함수). days 는 날짜 오름차순, 마지막이 오늘.
 * @param {import('../api/index.js').DayStat[]} days
 * @param {'feed'|'diaper'|'sleep'} metric
 * @returns {{columns: Column[], foot: [string, string][]}}  foot: [글, 꾸밈 class] 조각들
 */
export function buildChart(days, metric) {
  const m = METRICS[metric];
  const max = Math.max(1, ...days.map(m.value));
  const scale = (v) => Math.round((v / max) * BAR_MAX);
  const columns = days.map((d, i) => {
    const today = i === days.length - 1;
    const [, mm, dd] = d.day.split('-').map(Number);
    const height = scale(m.value(d));
    return { label: today ? '오늘' : `${mm}/${dd}`, value: m.text(d), height, part: Math.min(height, scale(m.part(d))), today };
  });
  // 오늘은 아직 안 끝났으니 평균에서 뺀다
  return { columns, foot: days.length > 1 ? m.foot(days.slice(0, -1)) : [] };
}

/** @param {import('../main.js').AppContext} ctx */
export function setupStats(ctx) {
  const cacheKey = () => (ctx.api.demo ? 'albam.demo.stats' : 'albam.stats');
  let metric = 'feed';
  /** @type {import('../api/index.js').DayStat[]|null} */
  let days = readCache();
  let note = '';

  function readCache() {
    try { return JSON.parse(localStorage.getItem(cacheKey()) || 'null'); } catch (e) { return null; }
  }

  function render() {
    for (const b of $$('#statsTabs button')) b.classList.toggle('on', b.dataset.metric === metric);
    $('#statsNote').textContent = note;
    if (!days?.length) {
      $('#statsChart').replaceChildren(el('div', { className: 'empty dim' }, note ? '' : '불러오는 중…'));
      $('#statsFoot').replaceChildren();
      return;
    }
    const { columns, foot } = buildChart(days, metric);
    $('#statsChart').replaceChildren(...columns.map((c) => el('div', { className: `col${c.today ? ' today' : ''}` },
      el('div', { className: 'v t9', style: { bottom: `${16 + c.height}px` } }, c.value),
      el('div', { className: 'bar', style: { height: `${c.height}px` } }, el('div', { className: 'part', style: { height: `${c.part}px` } })),
      el('div', { className: 'd t9' }, c.label))));
    $('#statsFoot').replaceChildren(...foot.map(([text, cls]) => el('span', { className: cls }, text)));
  }

  /** 서버에서 다시 받기. 안 되면 마지막으로 받은 것을 보여 주고 알린다 */
  async function load() {
    if (!ctx.api.isLoggedIn()) return;
    note = '';
    render();
    try {
      days = await ctx.api.getStats(ctx.cfg.statsDays);
      try { localStorage.setItem(cacheKey(), JSON.stringify(days)); } catch (e) { /* 저장 못 해도 화면은 그린다 */ }
    } catch (e) {
      days = days ?? readCache();
      note = days ? '연결 안 됨 · 지난번 통계' : '연결 안 됨';
    }
    render();
  }

  for (const b of $$('#statsTabs button')) {
    b.addEventListener('click', () => { ctx.sfx.tap(); metric = b.dataset.metric; render(); });
  }

  return { load, render };
}
