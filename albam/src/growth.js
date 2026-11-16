// 성장 백분위: 체중·키·머리둘레가 또래 100명 중 몇 번째인지(WHO 성장 기준, 0~24개월). 순수 함수.
//
//   growthAt({ kind: 'weight', value: 7.35, at, birth: '2026-06-18', due: '2026-07-10', sex: 'boy' })
//   → { actual: { days: 145, z: -0.05, pct: 48 }, corrected: { days: 123, z: 0.33, pct: 63 } }
//
// 기본 나이는 태어난 날부터, 교정 나이는 예정일부터 센다(예정일 전이면 corrected 는 null).
// 한국 2017 소아청소년 성장도표도 만 3세 미만은 이 WHO 기준을 쓴다. 표는 growth-data.js(월별 L·M·S),
// 달 사이는 곧게 이어서 셈한다. 진단용이 아니라 흐름을 보는 용도다.

import { WHO_LMS } from './growth-data.js';

const DAY_MS = 86400000;
/** WHO 가 쓰는 한 달 길이(일) */
export const DAYS_PER_MONTH = 30.4375;
/** 기록 종류 → 표 이름 */
export const GROWTH_KINDS = ['weight', 'height', 'head'];

/** 날짜(YYYY-MM-DD, 서울) 0시부터 그 시각까지 지난 날 수. 태어난 날이 0 */
export function daysSince(date, at) {
  return Math.floor((new Date(at).getTime() - new Date(`${date}T00:00:00+09:00`).getTime()) / DAY_MS);
}

/** 그 나이(일)의 L·M·S. 표 밖(0일 전, 24개월 뒤)이나 모르는 종류·성별이면 null */
export function lmsAt(kind, sex, days) {
  const rows = WHO_LMS[kind]?.[sex];
  const months = days / DAYS_PER_MONTH;
  if (!rows || !(days >= 0) || months > rows.length - 1) return null;
  const i = Math.min(Math.floor(months), rows.length - 2);
  const t = months - i;
  const [L, M, S] = rows[i].map((v, k) => v + (rows[i + 1][k] - v) * t);
  return { L, M, S };
}

/** 값 → z 점수(가운데에서 표준편차 몇 개만큼 떨어졌나) */
export function zScore(value, { L, M, S }) {
  return Math.abs(L) < 1e-6 ? Math.log(value / M) / S : ((value / M) ** L - 1) / (L * S);
}

/** z 점수 → 값(성장곡선 한 줄을 그릴 때) */
export function valueAtZ(z, { L, M, S }) {
  return Math.abs(L) < 1e-6 ? M * Math.exp(S * z) : M * (1 + L * S * z) ** (1 / L);
}

/** z 점수 → 백분위(0~100). 정규분포 누적값(Abramowitz–Stegun 근사, 오차 1e-7) */
export function percentile(z) {
  const x = Math.abs(z) / Math.SQRT2;
  const t = 1 / (1 + 0.3275911 * x);
  const erf = 1 - (((((1.061405429 * t - 1.453152027) * t) + 1.421413741) * t - 0.284496736) * t + 0.254829592) * t * Math.exp(-x * x);
  return 50 * (1 + (z < 0 ? -erf : erf));
}

function at(kind, sex, value, days) {
  const lms = lmsAt(kind, sex, days);
  if (!lms || !(value > 0)) return null;
  const z = zScore(value, lms);
  return { days, z, pct: percentile(z) };
}

/**
 * 잰 값 하나의 백분위를 기본 나이와 교정 나이로.
 * @param {{kind: string, value: number, at: Date|string, birth: string, due?: string|null, sex?: string|null}} m
 * @returns {{actual: {days: number, z: number, pct: number}|null, corrected: {days: number, z: number, pct: number}|null}}
 */
export function growthAt({ kind, value, at: when, birth, due = null, sex = null }) {
  if (!sex || !birth) return { actual: null, corrected: null };
  return {
    actual: at(kind, sex, value, daysSince(birth, when)),
    corrected: due ? at(kind, sex, value, daysSince(due, when)) : null,
  };
}

/** 성장곡선 한 줄: 그 백분위(예: 3, 15, 50, 85, 97)의 값을 달마다. [[개월, 값], …] */
export function curve(kind, sex, pct, { months = 24 } = {}) {
  const z = Z_OF[pct];
  const out = [];
  for (let m = 0; m <= months; m += 1) {
    const lms = lmsAt(kind, sex, m * DAYS_PER_MONTH);
    if (lms && z != null) out.push([m, valueAtZ(z, lms)]);
  }
  return out;
}
/** 성장도표에 흔히 그리는 줄의 z 점수 */
const Z_OF = { 3: -1.88079, 15: -1.03643, 50: 0, 85: 1.03643, 97: 1.88079 };

/** 화면 글: 48.2 → "48", 0.4 → "1 미만", 99.7 → "99 초과" */
export function formatPercentile(pct) {
  if (pct == null) return '';
  if (pct < 1) return '1 미만';
  if (pct > 99) return '99 초과';
  return String(Math.round(pct));
}
