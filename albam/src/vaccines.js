// 표준예방접종일정표: 생일로 접종 시기를 세고, 맞은 기록·예약과 맞춰 본다. 순수 함수.
//
// 출처: 「표준예방접종일정표(2024)」 질병관리청 · 대한의사협회 · 예방접종전문위원회(발행 2023.11.20).
//   표의 칸(출생 시, 4주 이내, 1개월 … 12세)을 그대로 옮겼다. 표가 바뀌면 SCHEDULE 만 고친다.
// 예방접종은 교정 나이가 아니라 태어난 날 기준으로 센다.
// 접종 여부를 판단하는 도구가 아니라 "언제 무엇이 남았나"를 보는 메모다. 실제 접종은 병원 안내를 따른다.
//
//   vaccineStatus({ birth: '2026-06-18', sex: 'boy', records, appointments, now })
//   → [{ period: '6개월', rows: [{ name: 'B형간염', dose: 3, of: 3, status: 'booked', date: '2026-12-22', … }] }, …]

const DAY_MS = 86400000;

/** 표의 칸. from~to 는 생후 개월(to 는 그 칸이 끝나는 개월, 넘으면 '시기 지남') */
const P = {
  birth: { label: '출생 시', from: 0, to: 1 },
  w4: { label: '4주 이내', from: 0, to: 1 },
  m1: { label: '1개월', from: 1, to: 2 },
  m2: { label: '2개월', from: 2, to: 3 },
  m4: { label: '4개월', from: 4, to: 5 },
  m6: { label: '6개월', from: 6, to: 7 },
  m6_18: { label: '6~18개월', from: 6, to: 19 },
  m12_15: { label: '12~15개월', from: 12, to: 16 },
  m15_18: { label: '15~18개월', from: 15, to: 19 },
  m12_23: { label: '12~23개월', from: 12, to: 24 },
  m24_35: { label: '24~35개월', from: 24, to: 36 },
  y4_6: { label: '4~6세', from: 48, to: 84 },
  y6: { label: '6세', from: 72, to: 84 },
  y11_12: { label: '11~12세', from: 132, to: 156 },
  y12: { label: '12세', from: 144, to: 156 },
};

/**
 * 표의 줄. words: 기록·예약의 글에서 이 백신을 알아보는 낱말(제품 이름 포함).
 * 혼합백신은 여러 줄에 같이 센다: 6가(헥사심) = DTaP·폴리오·Hib·B형간염, 5가(펜탁심) = DTaP·폴리오·Hib, 4가(테트락심) = DTaP·폴리오
 */
export const SCHEDULE = [
  { key: 'hepb', name: 'B형간염', doses: [P.birth, P.m1, P.m6], words: ['B형간염', 'HepB', '헤파뮨', '유박스', '헥사심', '6가'] },
  { key: 'bcg', name: 'BCG(결핵)', doses: [P.w4], words: ['BCG', '결핵'] },
  { key: 'dtap', name: 'DTaP(디프테리아·파상풍·백일해)', doses: [P.m2, P.m4, P.m6, P.m15_18, P.y4_6], words: ['DTaP', '디프테리아', '백일해', '헥사심', '6가', '펜탁심', '5가', '테트락심', '4가', '인판릭스'] },
  { key: 'tdap', name: 'Tdap/Td', doses: [P.y11_12], words: ['Tdap', 'Td'] },
  { key: 'ipv', name: '폴리오', doses: [P.m2, P.m4, P.m6_18, P.y4_6], words: ['폴리오', 'IPV', '헥사심', '6가', '펜탁심', '5가', '테트락심', '4가'] },
  { key: 'hib', name: 'Hib(b형헤모필루스인플루엔자)', doses: [P.m2, P.m4, P.m6, P.m12_15], words: ['Hib', '헤모필루스', '뇌수막염', '헥사심', '6가', '펜탁심', '5가'] },
  { key: 'pcv', name: '폐렴구균', doses: [P.m2, P.m4, P.m6, P.m12_15], words: ['폐렴구균', 'PCV', '프리베나', '신플로릭스', '박스뉴반스'] },
  // 로타바이러스는 백신에 따라 2회(RV1, 로타릭스) 또는 3회(RV5, 로타텍)
  { key: 'rv5', name: '로타바이러스(로타텍, 3회)', doses: [P.m2, P.m4, P.m6], words: ['로타텍', 'RV5'], alt: 'rv1' },
  { key: 'rv1', name: '로타바이러스(로타릭스, 2회)', doses: [P.m2, P.m4], words: ['로타릭스', 'RV1', '로타바이러스', '로타'], alt: 'rv5' },
  { key: 'mmr', name: 'MMR(홍역·유행성이하선염·풍진)', doses: [P.m12_15, P.y4_6], words: ['MMR', '홍역'] },
  { key: 'var', name: '수두', doses: [P.m12_15], words: ['수두', 'VAR'] },
  { key: 'hepa', name: 'A형간염', doses: [P.m12_23, P.m12_23], words: ['A형간염', 'HepA'], note: '2차는 1차 뒤 6개월 이상 지나서' },
  // 일본뇌염은 불활성화 백신 5회 또는 약독화 생백신 2회
  { key: 'ijev', name: '일본뇌염(불활성화, 5회)', doses: [P.m12_23, P.m12_23, P.m24_35, P.y6, P.y12], words: ['일본뇌염', 'IJEV', '불활성화'], alt: 'ljev', note: '2차는 1차 뒤 1개월, 3차는 2차 뒤 11개월' },
  { key: 'ljev', name: '일본뇌염(생백신, 2회)', doses: [P.m12_23, P.m24_35], words: ['생백신', 'LJEV'], alt: 'ijev', note: '2차는 1차 뒤 12개월' },
  { key: 'hpv', name: 'HPV(사람유두종바이러스)', doses: [P.y11_12, P.y11_12], words: ['HPV', '사람유두종', '가다실', '서바릭스'], only: 'girl', note: '6~12개월 간격으로 2회' },
];
/** 인플루엔자는 횟수가 정해져 있지 않다: 생후 6개월부터 매년, 접종 첫 해는 4주 간격으로 2회 */
export const FLU = { key: 'iiv', name: '인플루엔자(독감)', fromMonths: 6, words: ['인플루엔자', '독감', 'IIV'] };

const has = (text, words) => words.some((w) => String(text || '').toLowerCase().includes(w.toLowerCase()));
/** 'YYYY-MM-DD' → 그날(기기 시간대) */
const dayOf = (s) => { const [y, m, d] = String(s).slice(0, 10).split('-').map(Number); return new Date(y, m - 1, d); };
const keyOf = (d) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
/** 생일에 n개월 더한 날(31일생의 다음 달은 그 달 끝 날) */
export function addMonths(birth, n) {
  const b = dayOf(birth);
  const last = new Date(b.getFullYear(), b.getMonth() + n + 1, 0).getDate();
  return new Date(b.getFullYear(), b.getMonth() + n, Math.min(b.getDate(), last));
}

/** 로타·일본뇌염처럼 둘 중 하나를 고르는 줄: 기록이 있는 쪽, 없으면 앞의 것(로타텍·불활성화) */
function chosen(rows, counts) {
  return rows.filter((r) => {
    if (!r.alt) return true;
    const mine = counts[r.key] || 0; const other = counts[r.alt] || 0;
    if (mine !== other) return mine > other;
    return rows.findIndex((x) => x.key === r.key) < rows.findIndex((x) => x.key === r.alt);
  });
}

/**
 * @param {{birth: string, sex?: string|null, records?: {at: string, text: string}[], appointments?: {on_date: string, items?: string[], title?: string}[], now: Date}} o
 *   records: 맞은 접종(시각 순이 아니어도 됨). text 는 백신 이름("헥사심 1차")
 *   appointments: 앞으로의 예약
 * @returns {{periods: {label: string, from: number, rows: object[]}[], flu: object, others: {at: string, text: string}[], counts: {done: number, booked: number, due: number, overdue: number}}}
 */
export function vaccineStatus({ birth, sex = null, records = [], appointments = [], now }) {
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const sorted = [...records].sort((a, b) => new Date(a.at) - new Date(b.at));
  const future = appointments.filter((a) => dayOf(a.on_date) >= today).sort((a, b) => a.on_date.localeCompare(b.on_date));
  const textsOf = (a) => (a.items?.length ? a.items : [a.title || '']);
  // '로타바이러스'처럼 넓은 낱말이 로타텍 기록까지 세지 않게, 더 좁은 줄(alt)이 알아본 글은 뺀다
  const matches = (row, text) => has(text, row.words) && !(row.alt && row.key === 'rv1' && has(text, SCHEDULE.find((r) => r.key === 'rv5').words))
    && !(row.key === 'ijev' && has(text, SCHEDULE.find((r) => r.key === 'ljev').words));
  const doneOf = (row) => sorted.filter((r) => matches(row, r.text));
  const counts0 = Object.fromEntries(SCHEDULE.map((r) => [r.key, doneOf(r).length + future.filter((a) => textsOf(a).some((t) => matches(r, t))).length]));
  const rows = chosen(SCHEDULE.filter((r) => !r.only || r.only === sex), counts0);

  const out = [];
  const tally = { done: 0, booked: 0, due: 0, overdue: 0 };
  for (const row of rows) {
    const done = doneOf(row);
    const booked = future.filter((a) => textsOf(a).some((t) => matches(row, t)));
    row.doses.forEach((p, i) => {
      const from = addMonths(birth, p.from);
      const to = addMonths(birth, p.to);
      let status; let date = null;
      if (done[i]) { status = 'done'; date = keyOf(new Date(done[i].at)); }
      else if (booked[i - done.length]) { status = 'booked'; date = booked[i - done.length].on_date; }
      else if (today >= to) status = 'overdue';
      else if (today >= from) status = 'due';
      else status = 'later';
      if (status !== 'later') tally[status] += 1;
      out.push({ key: row.key, name: row.name, dose: i + 1, of: row.doses.length, period: p.label, fromMonths: p.from, from: keyOf(from), until: keyOf(new Date(to - DAY_MS)), status, date, note: row.note || '' });
    });
  }
  // 표의 칸 차례(시작 개월 → 표에 적힌 차례)로 묶는다
  const order = Object.values(P).map((p) => p.label);
  const periods = [];
  for (const label of order) {
    const mine = out.filter((r) => r.period === label);
    if (mine.length) periods.push({ label, from: mine[0].fromMonths, rows: mine });
  }
  const fluDone = sorted.filter((r) => has(r.text, FLU.words));
  const fluBooked = future.filter((a) => textsOf(a).some((t) => has(t, FLU.words)));
  const fluFrom = addMonths(birth, FLU.fromMonths);
  const flu = { name: FLU.name, from: keyOf(fluFrom), started: today >= fluFrom, done: fluDone.map((r) => keyOf(new Date(r.at))), booked: fluBooked.map((a) => a.on_date) };
  const known = (text) => SCHEDULE.some((r) => has(text, r.words)) || has(text, FLU.words);
  return { periods, flu, others: sorted.filter((r) => !known(r.text)), counts: tally };
}

/** 화면 글: 맞음 6/18 · 예약 12/22 · 지금 맞을 때(1/17까지) · 시기 지남 · 12/18부터 */
export function statusText(r) {
  const md = (s) => { const d = dayOf(s); return `${d.getMonth() + 1}/${d.getDate()}`; };
  if (r.status === 'done') return `맞음 ${md(r.date)}`;
  if (r.status === 'booked') return `예약 ${md(r.date)}`;
  if (r.status === 'due') return `지금 맞을 때(${md(r.until)}까지)`;
  if (r.status === 'overdue') return '시기 지남';
  const d = dayOf(r.from);
  return `${d.getFullYear() === new Date().getFullYear() ? '' : `${d.getFullYear()}년 `}${md(r.from)}부터`;
}
