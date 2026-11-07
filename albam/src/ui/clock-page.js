// 시계 쪽: 지금 시각과 날짜·요일을 크게, 그 아래 아기 나이. 대시보드에서 오른쪽으로 밀면 나온다.
//
//            21:07
//      11월 7일 토요일
//   D+143 · 4개월 21일 · 교정 3개월 29일

import { $, el } from './dom.js';
import { ageParts } from './status.js';
import { formatClock } from '../time.js';

const WEEKDAY = ['일요일', '월요일', '화요일', '수요일', '목요일', '금요일', '토요일'];

/** "11월 7일" + "토요일" (순수 함수) */
export function formatLongDate(d) {
  return { date: `${d.getMonth() + 1}월 ${d.getDate()}일`, weekday: WEEKDAY[d.getDay()] };
}

/** @param {import('../main.js').AppContext} ctx */
export function setupClockPage(ctx) {
  let key = '';
  /** tick 마다 부름. 글이 그대로면 DOM 을 건드리지 않는다 */
  function update() {
    const now = ctx.now();
    const time = formatClock(now);
    const { date, weekday } = formatLongDate(now);
    const age = ctx.state.summary?.age;
    const next = `${time}|${date}|${weekday}|${JSON.stringify(age ?? null)}`;
    if (next === key) return;
    key = next;
    $('#bigClock').textContent = time;
    $('#bigDate').replaceChildren(date, ' ', el('span', { className: 'acc' }, weekday));
    $('#bigAge').replaceChildren(...(age ? ageParts(age).map(([text, val]) => el('span', { className: val ? 'val' : '' }, text)) : []));
  }
  return { update };
}
