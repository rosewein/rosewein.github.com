// 시각을 글자로 바꾸는 순수 함수들. 화면(DOM)과 상관없어서 node 로 시험한다.

const MINUTE = 60000;
const DAY = 86400000;

export const pad2 = (n) => String(n).padStart(2, '0');

/** "13:05" */
export function formatClock(value) {
  const d = new Date(value);
  return `${pad2(d.getHours())}:${pad2(d.getMinutes())}`;
}

/**
 * 지난 시간을 [숫자, 단위] 조각으로. 화면에서 숫자는 크게, 단위는 작게 그리려고 나눈다.
 *   35분 → [['35','분']], 2시간 35분 → [['2','시간'],['35','분']], 2시간 → [['2','시간']], 1분 안 → []
 * @param {{hoursOnlyFrom?: number}} [opts]  이 시간 이상 지나면 분은 뺀다(좁은 줄에 넣을 때)
 */
export function agoParts(from, now, { hoursOnlyFrom = Infinity } = {}) {
  const min = Math.max(0, Math.floor((now - new Date(from)) / MINUTE));
  const h = Math.floor(min / 60);
  const m = min % 60;
  const parts = [];
  if (h) parts.push([String(h), '시간']);
  if (m && h < hoursOnlyFrom) parts.push([String(m), '분']);
  return parts;
}

/** "방금", "35분 전", "1시간 10분 전", "2시간 전" */
export function formatAgo(from, now, opts) {
  const parts = agoParts(from, now, opts);
  return parts.length ? `${parts.map(([n, u]) => n + u).join(' ')} 전` : '방금';
}

/** "오늘", "어제", 그 전은 "11/4" */
export function formatDay(value, now) {
  const day = new Date(value); day.setHours(0, 0, 0, 0);
  const today = new Date(now); today.setHours(0, 0, 0, 0);
  const diff = Math.round((today - day) / DAY);
  if (diff === 0) return '오늘';
  if (diff === 1) return '어제';
  return `${day.getMonth() + 1}/${day.getDate()}`;
}

/** "1시간 30분" */
export function formatDuration(ms) {
  const min = Math.round(ms / MINUTE);
  return `${Math.floor(min / 60)}시간 ${min % 60}분`;
}

/**
 * 밤 시간대인가. start > end 이면 자정을 넘는 구간(예: 21~6시)
 * @param {Date} date
 * @param {number} startHour
 * @param {number} endHour
 */
export function isWithinHours(date, startHour, endHour) {
  const h = date.getHours();
  return startHour > endHour ? h >= startHour || h < endHour : h >= startHour && h < endHour;
}

export const minutes = (n) => n * MINUTE;
