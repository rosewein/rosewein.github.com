// 분유 양 계산(순수 함수). 분유는 베이비브레짜로 탄다.
//
//   브레짜: 물 양을 60~300ml, 30ml 단위로 고른다(60, 90 … 300). 고른 숫자는 '물' 양이다.
//   압타밀: 물 30ml 에 1스푼, 다 타면 약 33.3ml. 그래서 브레짜 한 칸(물 30ml) = 1스푼.
//
// 기록하는 양(amount_ml)은 '완성량'을 10ml 단위로 반올림한 값이다(233 같은 숫자는 헷갈려서).
//   브레짜 180 → 200ml, 210 → 230ml, 240 → 270ml, 270 → 300ml, 300 → 330ml
// 분유나 기계를 바꾸면 ../config.js 의 formula·machine 값만 고친다.

/**
 * @typedef {Object} Formula   분유
 * @property {string} name
 * @property {number} waterMlPerScoop  1스푼에 넣는 물(ml)
 * @property {number} mlPerScoop       1스푼을 다 탄 완성량(ml)
 * @property {number} [roundMl]        완성량을 이 단위로 반올림(기본 10)
 */

/**
 * @typedef {Object} Machine   분유 타는 기계
 * @property {string} name
 * @property {number} minWaterMl
 * @property {number} maxWaterMl
 * @property {number} stepWaterMl      한 칸
 */

/** @type {Formula} */
export const APTAMIL = Object.freeze({ name: '압타밀', waterMlPerScoop: 30, mlPerScoop: 100 / 3, roundMl: 10 });
/** @type {Machine} */
export const BREZZA = Object.freeze({ name: '브레짜', minWaterMl: 60, maxWaterMl: 300, stepWaterMl: 30 });

/** 물 양 → 완성량(ml, roundMl 단위 반올림). 210 → 233.3 → 230 */
export function mlForWater(waterMl, f = APTAMIL) {
  const unit = f.roundMl || 1;
  return Math.round(((waterMl / f.waterMlPerScoop) * f.mlPerScoop) / unit) * unit;
}

/** 스푼 수 → 완성량. 7스푼 → 230 (음성 "수유 7스푼") */
export const mlForScoops = (scoops, f = APTAMIL) => mlForWater(scoops * f.waterMlPerScoop, f);

/** 완성량이 기계의 한 칸과 딱 맞으면 그 물 양, 아니면 null. 230 → 210, 220 → null */
export function waterFor(ml, f = APTAMIL, m = BREZZA) {
  const water = Math.round((ml / f.mlPerScoop) * f.waterMlPerScoop / m.stepWaterMl) * m.stepWaterMl;
  const fits = water >= m.minWaterMl && water <= m.maxWaterMl && Math.abs(mlForWater(water, f) - ml) <= 1;
  return fits ? water : null;
}

/**
 * 기계 한 칸 위/아래 양. 칸에 맞지 않는 양(220)이면 가까운 위/아래 칸(230/200)으로 맞춘다.
 * 기계 범위(물 60~300) 밖으로는 안 간다.
 */
export function stepMachine(ml, direction, f = APTAMIL, m = BREZZA) {
  // 칸에 맞는 양이면 그 칸의 물 양에서, 아니면 물 양을 거꾸로 셈해서 시작
  const exactWater = waterFor(ml, f, m) ?? (ml / f.mlPerScoop) * f.waterMlPerScoop;
  const steps = exactWater / m.stepWaterMl;
  const n = direction > 0 ? Math.floor(steps + 0.02) + 1 : Math.ceil(steps - 0.02) - 1;
  const water = Math.min(m.maxWaterMl, Math.max(m.minWaterMl, n * m.stepWaterMl));
  return mlForWater(water, f);
}

/** 화면 설명: "브레짜 180". 칸에 안 맞으면 "브레짜 칸 아님" */
export function machineLabel(ml, f = APTAMIL, m = BREZZA) {
  const water = waterFor(ml, f, m);
  return water ? `${m.name} ${water}` : `${m.name} 칸 아님`;
}

/** 기계에서 고를 수 있는 모든 양(완성량). 브레짜: 70, 100 … 330 */
export function machineAmounts(f = APTAMIL, m = BREZZA) {
  const list = [];
  for (let w = m.minWaterMl; w <= m.maxWaterMl; w += m.stepWaterMl) list.push(mlForWater(w, f));
  return list;
}
