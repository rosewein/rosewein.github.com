// 시계 쪽: 지금 시각과 날짜·요일을 크게. 대시보드에서 오른쪽으로 밀면 나온다.
//
//            21:07
//      11월 7일 토요일

import { $ } from './dom.js';
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
    const next = `${time}|${date}|${weekday}`;
    if (next === key) return;
    key = next;
    $('#bigClock').textContent = time;
    $('#bigDate').replaceChildren(date, ' ', Object.assign(document.createElement('span'), { className: 'acc', textContent: weekday }));
  }
  return { update };
}
