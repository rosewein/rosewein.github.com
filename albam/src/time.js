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

/** "1시간 30분", 한 시간이 안 되면 "15분", 분이 0이면 "2시간" */
export function formatDuration(ms) {
  const min = Math.max(0, Math.round(ms / MINUTE));
  const h = Math.floor(min / 60);
  const m = min % 60;
  if (!h) return `${m}분`;
  return m ? `${h}시간 ${m}분` : `${h}시간`;
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

/**
 * 직접 입력한 시·분을 고른 날에 맞춘다. 그 시각이 아직 안 왔으면 하루 앞으로(새벽 1시에 23:30 → 어제 23:30)
 * @param {Date} day     지금 고른 날짜(시각은 무시)
 * @param {number} hour
 * @param {number} minute
 * @param {Date} now
 */
export function clockOnDay(day, hour, minute, now) {
  const d = new Date(day);
  d.setHours(hour, minute, 0, 0);
  if (d > now) d.setDate(d.getDate() - 1);
  return d;
}

const WEEKDAY = ['일요일', '월요일', '화요일', '수요일', '목요일', '금요일', '토요일'];

/** "11월 7일" + "토요일" (순수 함수). 시계 쪽과 대시보드 구석이 같이 쓴다 */
export function formatLongDate(d) {
  return { date: `${d.getMonth() + 1}월 ${d.getDate()}일`, weekday: WEEKDAY[d.getDay()] };
}

/** 대시보드 구석의 오늘: "2026년 11월 7일 토요일". short 면 해를 뺀다(좁은 화면) */
export function formatToday(d, short = false) {
  const { date, weekday } = formatLongDate(d);
  return `${short ? '' : `${d.getFullYear()}년 `}${date} ${weekday}`;
}

/**
 * 날이 다르면 날을 붙인 시각(순수 함수): 오늘 "09:00", 어제 "어제 09:00", 그 전 "11/8 09:00".
 * short 면(좁은 칸) 오늘이 아닐 때 시각을 빼고 날만: "어제", "11/8"
 */
export function formatClockOn(value, now, short = false) {
  const day = formatDay(value, now);
  if (day === '오늘') return formatClock(value);
  return short ? day : `${day} ${formatClock(value)}`;
}
