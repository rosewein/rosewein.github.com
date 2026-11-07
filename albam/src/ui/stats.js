// 통계 쪽: 최근 7일을 날짜 카드 일곱 장으로. 수유·기저귀·잠을 위쪽 탭으로 바꾼다.
// 숫자는 Supabase care_stats() 가 센다(베이비타임에서 옮긴 기록 + 거실 화면 기록).
// 날짜 규칙은 베이비타임 통계와 같다: 밤잠은 깨는 아침의 날에 센다(supabase/003_stats.sql).
//
//   숫자 = 전체 · 💩 = 대변 있음          [수유][기저귀][잠]   ← 왼쪽: 카드 읽는 법
//   ┌11/1┐┌11/2┐ …  ┌오늘┐                                  ← 오늘 카드는 주황 테두리
//   │ 8  ││ 8  │      │ 4  │   큰 숫자: 수유 횟수 / 기저귀 횟수 / 잠 시간
//   │💩2 ││💩0 │      │💩2 │   주황 칸: 하루 수유량(ml) / 대변 있는 횟수 / 낮잠 시간
//   │▬── ││─── │      │▬▬─ │   아래 막대: 수유는 7일 중 가장 많은 날 대비, 기저귀·잠은 전체 중 주황 칸의 몫
//   지난 6일 평균 6.7회 · 대변 1.2회

import { $, $$, el } from './dom.js';

/**
 * @typedef {Object} Card
 * @property {string} label     "11/6", 마지막 날은 "오늘"
 * @property {string} big       큰 숫자 "5", "8", "12"
 * @property {string} small     큰 숫자 뒤 작은 글 "", ".5"
 * @property {string} badge     주황 칸 글 "850", "2", "2.5"
 * @property {string} icon      주황 칸 아이콘 이름(sprites) 또는 ''
 * @property {string} badgeText 주황 칸 앞 글(아이콘 대신) "낮"
 * @property {number} bar       아래 막대 채움 0~1
 * @property {boolean} today
 */

const avg = (list, f) => (list.length ? list.reduce((s, d) => s + f(d), 0) / list.length : 0);
const one = (n) => (Math.round(n * 10) / 10).toFixed(1);
const hm = (min) => {
  const m = Math.round(min);
  return `${Math.floor(m / 60)}시간${m % 60 ? ` ${m % 60}분` : ''}`;
};
const share = (part, total) => (total > 0 ? Math.min(1, part / total) : 0);
const poo = (d) => d.diaper_poo + d.diaper_both;

/** 항목마다: 카드 읽는 법, 카드 값, 아래 평균 글 */
const METRICS = {
  feed: {
    legend: [['숫자', 'val'], [' = 횟수 · ', ''], ['', 'ico-bottle'], [' = 하루 양(ml)', '']],
    card: (d, max) => ({ big: String(d.feed_count), small: '', icon: 'bottle', badgeText: '', badge: String(d.feed_ml), bar: share(d.feed_ml, max.feed_ml) }),
    foot: (past) => [['지난 6일 평균 ', ''], [`${one(avg(past, (d) => d.feed_count))}회 · ${Math.round(avg(past, (d) => d.feed_ml))}ml`, 'val']],
  },
  diaper: {
    legend: [['숫자', 'val'], [' = 전체 · ', ''], ['', 'ico-poo'], [' = 대변 있음', 'acc']],
    card: (d) => ({ big: String(d.diaper_total), small: '', icon: 'poo', badgeText: '', badge: String(poo(d)), bar: share(poo(d), d.diaper_total) }),
    foot: (past) => [['지난 6일 평균 ', ''], [`${one(avg(past, (d) => d.diaper_total))}회`, 'val'],
      [' · ', ''], ['대변', 'acc'], [` ${one(avg(past, poo))}회`, 'val']],
  },
  sleep: {
    legend: [['숫자', 'val'], [' = 전체 잠(시간) · ', ''], ['낮', 'acc'], [' = 낮잠', 'acc']],
    card: (d) => {
      const [whole, frac] = one(d.sleep_min / 60).split('.');
      return { big: whole, small: `.${frac}`, icon: '', badgeText: '낮', badge: one((d.nap_min ?? 0) / 60), bar: share(d.nap_min ?? 0, d.sleep_min) };
    },
    foot: (past) => [['평균 ', ''], ['낮잠', 'acc'], [` ${hm(avg(past, (d) => d.nap_min ?? 0))}`, 'val'],
      [' · 밤잠 ', ''], [hm(avg(past, (d) => d.night_min ?? 0)), 'val']],
  },
};

/**
 * 카드 값 만들기(순수 함수). days 는 날짜 오름차순, 마지막이 오늘.
 * @param {import('../api/index.js').DayStat[]} days
 * @param {'feed'|'diaper'|'sleep'} metric
 * @returns {{cards: Card[], foot: [string, string][], legend: [string, string][]}}
 *   foot·legend: [글, 꾸밈 class] 조각들. class 가 ico-… 이면 그 아이콘
 */
export function buildCards(days, metric) {
  const m = METRICS[metric];
  const max = { feed_ml: Math.max(1, ...days.map((d) => d.feed_ml)) };
  const cards = days.map((d, i) => {
    const today = i === days.length - 1;
    const [, mm, dd] = d.day.split('-').map(Number);
    return { label: today ? '오늘' : `${mm}/${dd}`, today, ...m.card(d, max) };
  });
  // 오늘은 아직 안 끝났으니 평균에서 뺀다
  return { cards, foot: days.length > 1 ? m.foot(days.slice(0, -1)) : [], legend: m.legend };
}

const pieces = (list) => list.map(([text, cls]) => (cls.startsWith('ico-')
  ? el('span', { className: `spr ico ${cls}` })
  : el('span', { className: cls }, text)));

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
      $('#statsLegend').replaceChildren();
      return;
    }
    const { cards, foot, legend } = buildCards(days, metric);
    $('#statsLegend').replaceChildren(...pieces(legend));
    $('#statsChart').replaceChildren(...cards.map((c) => el('div', { className: `card${c.today ? ' today' : ''}` },
      el('div', { className: 'd t9' }, c.label),
      el('div', { className: 'n' }, el('span', { className: 'big' }, c.big), ...(c.small ? [el('span', { className: 'small t9' }, c.small)] : [])),
      el('div', { className: 'badge t9' },
        ...(c.icon ? [el('span', { className: `spr ico ico-${c.icon}` })] : [el('span', {}, c.badgeText)]),
        el('span', {}, c.badge)),
      el('div', { className: 'meter' }, el('div', { className: 'fill', style: { width: `${Math.round(c.bar * 100)}%` } })))));
    $('#statsFoot').replaceChildren(...pieces(foot));
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
