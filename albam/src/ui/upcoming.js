// 다가오는 일정(예방접종 예약 등): care_upcoming()(supabase/015)으로 받아 시계 쪽 맨 아랫줄에 가장 가까운 것 하나를 띄운다.
//   12월 22일 화 예방접종 D-2 · 헥사심 3차 외 3
// 미리부터 띄우지 않는다: 이틀 전(config.js upcomingNoticeDays)부터 시계 쪽 맨 아랫줄과 대시보드 나이 줄 자리에 보인다.
// 연결이 안 되면 마지막으로 받은 것을 쓴다(남은 날은 기기 날짜로 다시 센다).

const DAY_MS = 86400000;
const WEEKDAYS = ['일', '월', '화', '수', '목', '금', '토'];

/** 'YYYY-MM-DD' → 그날 0시(기기 시간대) */
const dayOf = (s) => { const [y, m, d] = s.split('-').map(Number); return new Date(y, m - 1, d); };

/**
 * 일정 한 줄 글. 지난 일정이면 ''.  (순수 함수)
 * @param {{on_date: string, title: string, items?: string[], at_time?: string|null}} a
 * @param {Date} now
 * @returns {{date: string, title: string, left: string, items: string, days: number}|null}
 */
export function describeAppointment(a, now) {
  const day = dayOf(a.on_date);
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const left = Math.round((day - today) / DAY_MS);
  if (left < 0) return null;
  const items = a.items || [];
  return {
    date: `${day.getMonth() + 1}월 ${day.getDate()}일 ${WEEKDAYS[day.getDay()]}${a.at_time ? ` ${a.at_time}` : ''}`,
    title: a.title,
    left: left === 0 ? '오늘' : left === 1 ? '내일' : `D-${left}`,
    items: items.length > 1 ? `${items[0]} 외 ${items.length - 1}` : items[0] || '',
    days: left,
  };
}

/**
 * @param {import('../main.js').AppContext} ctx
 * @param {string} cacheKey
 */
export function createUpcoming(ctx, cacheKey) {
  let list = [];
  try { list = JSON.parse(localStorage.getItem(cacheKey) || '[]') || []; } catch (e) { /* 없어도 됨 */ }

  async function load() {
    try {
      const got = await ctx.api.getUpcoming();
      if (Array.isArray(got)) {
        list = got;
        try { localStorage.setItem(cacheKey, JSON.stringify(list)); } catch (e) { /* 저장 못 해도 됨 */ }
      }
    } catch (e) { /* 연결 안 됨: 지난번 것 */ }
  }

  /** 띄울 일정 하나: 가장 가까운 일정이 며칠 안(upcomingNoticeDays, 기본 2)으로 다가왔을 때만. 아니면 null */
  function next(now) {
    const within = Number(ctx.cfg.upcomingNoticeDays ?? 2);
    for (const a of list) {
      const d = describeAppointment(a, now);
      if (d) return d.days <= within ? d : null;
    }
    return null;
  }

  return { load, next };
}
