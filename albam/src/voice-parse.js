// 음성 인식 결과(한국어 문장)를 기록 하나로 바꾸는 규칙.
// 화면·통신과 떨어진 순수 함수라서 tests/unit/voice-parse.test.mjs 로 시험한다.
//
//   parseUtterance('수유 160 20분 전', now)
//     → { ok: true, event: { kind: 'feed', amount_ml: 160, occurred_at: Date, detail: {} }, label: '수유 160ml · 20분 전' }
//   못 알아들으면 { ok: false, reason }
//
// 처리 순서
//   1. normalize(): 한글 수사·단위를 숫자와 정해진 꼴로 ("백 육십 밀리" → "160ml", "한 시 반" → "1시30분")
//   2. 종류별 규칙을 차례로 시도: 수면 → 기저귀 → 수유
//   3. 시각 말("20분 전", "2시 10분에")을 실제 시각으로
//
// 새 말투를 넣을 때는 아래 WORDS 의 정규식에 낱말을 더하고, 시험(tests/unit/voice-parse.test.mjs)에 문장을 하나 더한다.

import { DIAPER_LABEL, KIND } from './domain.js';
import { APTAMIL, BREZZA, mlForScoops, mlForWater } from './formula.js';
import { formatClock } from './time.js';

/** 종류를 알아보는 낱말. 정규화한 문장에 맞춘다 */
const WORDS = {
  sleep: /잠|수면|잤|재웠|자기/,
  feed: /수유|분유|먹였|먹었|먹음|맘마|ml|스푼|브레짜/,
  diaper: /기저귀|소변|대변|응가|오줌/,
  pee: /소변|쉬야|(^|\s)쉬(\s|했|$)|오줌/,
  poo: /대변|응가|똥/,
  both: /둘\s*다|다\s*했|소변\s*대변|대변\s*소변/,
};

/** 수유량으로 받아들이는 범위(ml) */
const FEED_ML = { min: 10, max: 500 };
/** 이보다 긴 잠은 잘못 알아들은 것으로 본다 */
const MAX_SLEEP_MS = 16 * 3600000;

// ───────────────────────── 1. 숫자 ─────────────────────────

const SINO_DIGIT = { 일: 1, 이: 2, 삼: 3, 사: 4, 오: 5, 육: 6, 륙: 6, 칠: 7, 팔: 8, 구: 9 };
const SINO_CHARS = '일이삼사오육륙칠팔구십백천';
const SINO_NUMBER = /^(?:([이삼사오육륙칠팔구])?천)?(?:([이삼사오육륙칠팔구])?백)?(?:([이삼사오육륙칠팔구])?십)?([일이삼사오육륙칠팔구])?$/;
/** 시각에 쓰는 고유어 수사. 긴 것부터(열두가 열보다 먼저) */
const NATIVE_HOURS = [
  ['열두', 12], ['열한', 11], ['열', 10], ['아홉', 9], ['여덟', 8], ['일곱', 7], ['여섯', 6],
  ['다섯', 5], ['네', 4], ['세', 3], ['두', 2], ['한', 1],
];
const UNIT = '시간|시|분|ml|스푼';

/** 한자어 수사 → 정수. "백육십" → 160. 수사가 아니면 null */
export function sinoToInt(text) {
  const s = text.replace(/\s+/g, '');
  const m = s && s.match(SINO_NUMBER);
  if (!m) return null;
  const digit = (c) => (c ? SINO_DIGIT[c] : 1);  // "백" 은 1백
  let n = 0;
  if (s.includes('천')) n += digit(m[1]) * 1000;
  if (s.includes('백')) n += digit(m[2]) * 100;
  if (s.includes('십')) n += digit(m[3]) * 10;
  if (m[4]) n += SINO_DIGIT[m[4]];
  return n;
}

// ───────────────────────── 2. 정규화 ─────────────────────────

/** 문장을 규칙이 읽기 쉬운 꼴로. 예: "수유 백 육십 밀리 이십 분 전" → "수유 160ml 20분 전" */
export function normalize(text) {
  let t = ` ${String(text || '')} `
    .toLowerCase()
    .replace(/[.,!?~"'“”‘’]/g, ' ')
    .replace(/(밀리\s*리터|밀리리터|밀리|미리|씨씨|cc|㎖|ml)/gi, 'ml')
    .replace(/(스쿱|숟가락|숟갈|스푼)/g, '스푼');

  // 고유어 수: "한 시" → "1시", "두시간" → "2시간", "일곱 스푼" → "7스푼"
  for (const [word, n] of NATIVE_HOURS) {
    t = t.replace(new RegExp(`(^|[^가-힣])${word}\\s*(?=시|스푼)`, 'g'), `$1${n}`);
  }

  // 띄어 말한 한자어 수사 붙이기: "백 육십" → "백육십".
  // 뒤 덩어리에 시·분이 붙으면 다른 숫자라 붙이지 않는다: "이백 이십 분 전"
  const S = `[${SINO_CHARS}]`;
  t = t.replace(new RegExp(`(^|[^가-힣])(${S}+)\\s+(?=${S}+(?!${S})(?!\\s*(?:시간|시|분))(?:[^가-힣]|ml|$))`, 'g'), '$1$2');

  // 한자어 수사 → 숫자. "오후"의 "오" 같은 낱말을 건드리지 않으려고,
  // 십·백·천이 들어 있거나 바로 뒤에 단위가 올 때만 바꾼다
  t = t.replace(new RegExp(`(^|[^가-힣])(${S}+)(?=[^가-힣]|${UNIT}|$)`, 'g'), (whole, before, run, offset, str) => {
    const n = sinoToInt(run);
    const unitFollows = new RegExp(`^\\s*(${UNIT})`).test(str.slice(offset + whole.length));
    return n != null && (/[십백천]/.test(run) || unitFollows) ? `${before}${n}` : whole;
  });

  return t
    .replace(new RegExp(`(\\d+)\\s*(${UNIT})`, 'g'), '$1$2')   // "160 ml" → "160ml"
    .replace(/(\d+)시간\s*반/g, '$1시간30분')
    .replace(/(\d+)시\s*반/g, '$1시30분')
    .replace(/\s+/g, ' ')
    .trim();
}

// ───────────────────────── 3. 시각 ─────────────────────────

/** "(오후) 2시 (10분)" — 앞의 낮/밤 말, 시, 분 */
const CLOCK = '(오전|오후|새벽|아침|저녁|낮|밤)?\\s*(\\d{1,2})시(?:\\s*(\\d{1,2})분)?';

/** @returns {'am'|'pm'|'night'|null} */
function periodOf(word) {
  if (!word) return null;
  if (/오전|새벽|아침/.test(word)) return 'am';
  if (/오후|저녁|낮/.test(word)) return 'pm';
  if (/밤/.test(word)) return 'night';   // 밤 9시는 21시, 밤 1시는 1시
  return null;
}

/** 말한 시·분을 기준 시각 이전 가장 가까운 실제 시각으로. "2시" 는 2시와 14시 중 가까운 과거 */
function resolveClock(hour, minute, period, ref) {
  const candidates =
    period === 'am' ? [hour % 12]
    : period === 'pm' ? [(hour % 12) + 12]
    : period === 'night' ? [hour >= 6 && hour < 12 ? hour + 12 : hour % 12]
    : hour >= 13 || hour === 0 ? [hour % 24]
    : [hour % 12, (hour % 12) + 12];
  let best = null;
  for (const h of candidates) {
    for (const daysBack of [0, 1]) {
      const d = new Date(ref);
      d.setDate(d.getDate() - daysBack);
      d.setHours(h, minute, 0, 0);
      if (d <= ref && (!best || d > best)) best = d;
    }
  }
  return best;
}

/**
 * 문장 속 시각 말. "20분 전", "1시간 30분 전", "3시 10분에". 없으면 지금
 * @returns {{at: Date, minutesAgo: number, matched: string}}
 */
function parseWhen(t, now) {
  const ago = t.match(/(?:(\d+)시간)?\s*(?:(\d+)분)?\s*전/);
  if (ago && (ago[1] || ago[2])) {
    const min = (+ago[1] || 0) * 60 + (+ago[2] || 0);
    return { at: new Date(now.getTime() - min * 60000), minutesAgo: min, matched: ago[0] };
  }
  const clock = !/부터|까지/.test(t) && t.match(new RegExp(`${CLOCK}\\s*(?:에|쯤)?`));
  if (clock) {
    const at = resolveClock(+clock[2], +(clock[3] || 0), periodOf(clock[1]), now);
    if (at) return { at, minutesAgo: Math.round((now - at) / 60000), matched: clock[0] };
  }
  return { at: now, minutesAgo: 0, matched: '' };
}

/** 확인 화면용: "지금", "20분 전", "1시간 30분 전", 그보다 오래면 "13:20" */
function whenLabel({ at, minutesAgo: m }) {
  if (!m) return '지금';
  if (m < 60) return `${m}분 전`;
  if (m < 180 && m % 60) return `${Math.floor(m / 60)}시간 ${m % 60}분 전`;
  return formatClock(at);
}

// ───────────────────────── 4. 종류별 규칙 ─────────────────────────

const ok = (event, label) => ({ ok: true, event, label });
const fail = (reason) => ({ ok: false, reason });

/** "잠 1시 10분부터 2시 40분까지" */
function parseSleep(t, now) {
  const m = t.match(new RegExp(`${CLOCK}\\s*부터\\s*${CLOCK}\\s*까지`));
  if (!m) return null;
  const [, startWord, startH, startM, endWord, endH, endM] = m;
  const end = resolveClock(+endH, +(endM || 0), periodOf(endWord) || periodOf(startWord), now);
  const start = end && resolveClock(+startH, +(startM || 0), periodOf(startWord), new Date(end.getTime() - 1));
  if (!start || end - start > MAX_SLEEP_MS) return null;
  return ok({ kind: KIND.SLEEP, occurred_at: start, ended_at: end, detail: {} }, `잠 ${formatClock(start)}~${formatClock(end)}`);
}

/** "기저귀 대변", "기저귀 소변 10분 전", "기저귀 둘 다" */
function parseDiaper(t, now) {
  const pee = WORDS.pee.test(t);
  const poo = WORDS.poo.test(t);
  const type = WORDS.both.test(t) || (pee && poo) ? 'both' : poo ? 'poo' : pee ? 'pee' : null;
  if (!type) return fail('diaper_type');
  const when = parseWhen(t, now);
  return ok({ kind: KIND.DIAPER, occurred_at: when.at, detail: { type } }, `기저귀 ${DIAPER_LABEL[type]} · ${whenLabel(when)}`);
}

/** "수유 160", "160 먹였어", "분유 백육십 이십 분 전", "수유 7스푼", "브레짜 210"(뒤 둘은 완성량으로 바꿈) */
function parseFeed(t, now, formula, machine) {
  const when = parseWhen(t, now);
  const rest = when.matched ? t.replace(when.matched, ' ') : t;
  // 브레짜 숫자는 물 양 → 완성량
  const brezza = rest.match(/브레짜\s*(\d+)/);
  if (brezza) {
    const water = +brezza[1];
    if (water < machine.minWaterMl || water > machine.maxWaterMl || water % machine.stepWaterMl) return fail('feed_amount');
    const ml = mlForWater(water, formula);
    return ok({ kind: KIND.FEED, amount_ml: ml, occurred_at: when.at, detail: {} }, `수유 ${ml}ml(${machine.name} ${water}) · ${whenLabel(when)}`);
  }
  const scoops = rest.match(/(\d+)스푼/);
  if (scoops) {
    const n = +scoops[1];
    const ml = mlForScoops(n, formula);
    if (ml < FEED_ML.min || ml > FEED_ML.max) return fail('feed_amount');
    return ok({ kind: KIND.FEED, amount_ml: ml, occurred_at: when.at, detail: {} }, `수유 ${ml}ml(${n}스푼) · ${whenLabel(when)}`);
  }
  const numbers = [...rest.matchAll(/(\d+)(?!\d)(?!\s*(?:시간|시|분))/g)].map((x) => +x[1]);
  const ml = numbers.find((n) => n >= FEED_ML.min && n <= FEED_ML.max);
  if (!ml) return fail('feed_amount');
  return ok({ kind: KIND.FEED, amount_ml: ml, occurred_at: when.at, detail: {} }, `수유 ${ml}ml · ${whenLabel(when)}`);
}

// ───────────────────────── 5. 입구 ─────────────────────────

/**
 * @param {string} text  음성 인식 원문
 * @param {Date} now
 * @param {{formula?: import('./formula.js').Formula, machine?: import('./formula.js').Machine}} [opts]  "n스푼"·"브레짜 n"을 완성량으로 바꿀 때
 * @returns {{ok: true, event: import('./domain.js').CareEvent, label: string} | {ok: false, reason: string}}
 */
export function parseUtterance(text, now = new Date(), { formula = APTAMIL, machine = BREZZA } = {}) {
  const t = normalize(text);
  if (!t) return fail('empty');

  if (WORDS.sleep.test(t)) {
    const sleep = parseSleep(t, now);
    if (sleep) return sleep;
    // "잠" 이 들어 있어도 다른 종류 말이 없으면 시작·끝을 말해 달라고 한다
    if (!/수유|분유|기저귀|먹/.test(t)) return fail('sleep_needs_range');
  }
  if (WORDS.diaper.test(t)) return parseDiaper(t, now);
  if (WORDS.feed.test(t)) return parseFeed(t, now, formula, machine);
  return fail('unknown');
}
