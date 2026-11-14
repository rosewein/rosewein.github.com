// 영유아 건강검진 시기: 생일로 검진 기간을 세고, 받은 기록·예약과 맞춰 본다. 순수 함수.
//
// 국민건강보험공단 영유아건강검진의 차수별 검진 시기를 옮겼다(2026-11-14, 기억에 기댄 것이라 공단 안내문으로 확인이 필요하다).
//   건강검진 1차 생후 14~35일, 2차 4~6개월, 3차 9~12개월, 4차 18~24개월, 5차 30~36개월, 6차 42~48개월, 7차 54~60개월, 8차 66~71개월
//   구강검진 1차 18~29개월, 2차 30~41개월, 3차 42~53개월, 4차 54~65개월
// 기간이 바뀌면 CHECKUPS 만 고친다. 예방접종처럼 태어난 날 기준으로 센다.
//
//   checkupStatus({ birth: '2026-06-18', records, appointments, now })
//   → { rows: [{ key: 'health', name: '건강검진', n: 2, period: '4~6개월', status: 'due', from, until, date }], counts }

import { addMonths } from './vaccines.js';

const DAY_MS = 86400000;
const m = (from, to, label) => ({ from, to, label });   // 생후 from 개월 되는 날 ~ to 개월이 끝나는 날

/** 차수별 검진 시기. days 가 있으면 생후 며칠(1차 건강검진) */
export const CHECKUPS = [
  { key: 'health', name: '건강검진', rounds: [
    { days: [14, 35], label: '생후 14~35일' }, m(4, 6, '4~6개월'), m(9, 12, '9~12개월'), m(18, 24, '18~24개월'),
    m(30, 36, '30~36개월'), m(42, 48, '42~48개월'), m(54, 60, '54~60개월'), m(66, 71, '66~71개월'),
  ] },
  { key: 'dental', name: '구강검진', rounds: [m(18, 29, '18~29개월'), m(30, 41, '30~41개월'), m(42, 53, '42~53개월'), m(54, 65, '54~65개월')] },
];

const dayOf = (s) => { const [y, mo, d] = String(s).slice(0, 10).split('-').map(Number); return new Date(y, mo - 1, d); };
const keyOf = (d) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
const isDental = (text) => /구강|치과/.test(String(text || ''));
/** "2차 검진" → 2. 차수가 안 적혀 있으면 null */
const roundOf = (text) => { const x = /(\d+)\s*차/.exec(String(text || '')); return x ? Number(x[1]) : null; };

/**
 * @param {{birth: string, records?: {at: string, text: string}[], appointments?: {on_date: string, title?: string, items?: string[]}[], now: Date}} o
 *   records: 받은 검진(kind = checkup). text 에 "2차"처럼 차수가 있으면 그 차수, 없으면 받은 차례대로 센다. '구강'·'치과'가 있으면 구강검진
 *   appointments: 앞으로의 예약 중 이름에 '검진'이 들어간 것
 */
export function checkupStatus({ birth, records = [], appointments = [], now }) {
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const sorted = [...records].sort((a, b) => new Date(a.at) - new Date(b.at));
  const future = appointments.filter((a) => dayOf(a.on_date) >= today && /검진/.test(`${a.title || ''} ${(a.items || []).join(' ')}`))
    .sort((a, b) => a.on_date.localeCompare(b.on_date));
  const rows = [];
  const counts = { done: 0, booked: 0, due: 0, overdue: 0 };
  for (const c of CHECKUPS) {
    const mine = sorted.filter((r) => isDental(r.text) === (c.key === 'dental'));
    const booked = future.filter((a) => isDental(`${a.title || ''} ${(a.items || []).join(' ')}`) === (c.key === 'dental'));
    // 차수가 적힌 기록은 그 차수에, 안 적힌 기록은 비어 있는 앞 차수부터
    const done = new Map();
    for (const r of mine.filter((x) => roundOf(x.text))) done.set(roundOf(r.text), r);
    for (const r of mine.filter((x) => !roundOf(x.text))) {
      let n = 1; while (done.has(n)) n += 1;
      done.set(n, r);
    }
    let nextBooked = 0;
    c.rounds.forEach((p, i) => {
      const n = i + 1;
      const from = p.days ? new Date(dayOf(birth).getTime() + p.days[0] * DAY_MS) : addMonths(birth, p.from);
      const end = p.days ? new Date(dayOf(birth).getTime() + (p.days[1] + 1) * DAY_MS) : addMonths(birth, p.to + 1);   // 이 날부터는 지남
      let status; let date = null;
      if (done.has(n)) { status = 'done'; date = keyOf(new Date(done.get(n).at)); }
      else if (today >= end) status = 'overdue';
      else if (booked[nextBooked] && (roundOf(`${booked[nextBooked].title || ''} ${(booked[nextBooked].items || []).join(' ')}`) ?? n) === n) { status = 'booked'; date = booked[nextBooked].on_date; nextBooked += 1; }
      else if (today >= from) status = 'due';
      else status = 'later';
      if (status !== 'later') counts[status] += 1;
      rows.push({ key: c.key, name: c.name, n, period: p.label, from: keyOf(from), until: keyOf(new Date(end - DAY_MS)), status, date });
    });
  }
  return { rows, counts };
}
