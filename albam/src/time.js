// 시각을 글자로 바꾸는 순수 함수들. 화면(DOM)과 상관없어서 node 로 시험한다.

const MINUTE = 60000;
const DAY = 86400000;

export const pad2 = (n) => String(n).padStart(2, '0');

/** "13:05" */
export function formatClock(value) {
  const d = new Date(value);
  return `${pad2(d.getHours())}:${pad2(d.getMinutes())}`;
}

/** 경과 시간을 "시:분"으로. 기록이 없으면 "-:--". 시는 99에서 멈춘다 */
export function formatElapsed(from, now) {
  if (!from) return '-:--';
  const min = Math.max(0, Math.floor((now - new Date(from)) / MINUTE));
  return `${Math.min(99, Math.floor(min / 60))}:${pad2(min % 60)}`;
}

/** "35분 전", "1:10 전" */
export function formatAgo(from, now) {
  const min = Math.max(0, Math.floor((now - new Date(from)) / MINUTE));
  return min < 60 ? `${min}분 전` : `${Math.floor(min / 60)}:${pad2(min % 60)} 전`;
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
