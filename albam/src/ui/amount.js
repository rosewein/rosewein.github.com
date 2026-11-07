// 수유량 표시와 브레짜 한 칸 버튼. 수유 창·수유량 설정·지난 기록이 같이 쓴다.
//   양 표시:  200ml        ← 크게(완성량)
//             브레짜 180   ← 작게(브레짜에서 고를 물 양)
// 계산은 ../formula.js. 분유·기계 값은 ../config.js 의 formula·machine.

import { el } from './dom.js';
import { machineLabel, stepMachine, waterFor } from '../formula.js';

const AMOUNT = { min: 5, max: 500 };
export const clampAmount = (ml) => Math.min(AMOUNT.max, Math.max(AMOUNT.min, ml));

/** @typedef {{formula: import('../formula.js').Formula, machine: import('../formula.js').Machine}} Mixing */

/** 양 + 브레짜 설명. 보통 두 줄, inline 이면 한 줄(좁은 창에서) */
export function amountView(ml, { formula, machine }, { inline = false } = {}) {
  return el('div', { className: `amount${inline ? ' inline' : ''}` },
    el('div', { className: 't24 val' }, `${ml}ml`),
    el('div', { className: 't9 machine' }, machineLabel(ml, formula, machine)));
}

/** 빠른 선택 버튼 안: "200" + "브레짜 180" */
export function quickAmountLabel(ml, { formula, machine }) {
  const water = waterFor(ml, formula, machine);
  return [el('span', { className: 't24 val' }, String(ml)), el('span', { className: 't9 machine' }, water ? `${machine.name} ${water}` : '')];
}

/**
 * ± 버튼 묶음. [-10] [-30 브레짜] … [+30 브레짜] [+10]
 * 브레짜 버튼은 기계 한 칸(물 30ml)씩, ±10 은 덜 먹었을 때 맞추려고 남긴다.
 * @param {{get: () => number, set: (ml: number) => void, mixing: Mixing, tap: () => void, fine?: boolean}} o
 *        fine=false 면 브레짜 버튼만(수유량 설정처럼 브레짜 칸으로만 정할 때)
 * @returns {{before: HTMLElement[], after: HTMLElement[]}}  양 표시 앞뒤에 넣을 버튼
 */
export function amountSteppers({ get, set, mixing, tap, fine = true }) {
  const { formula, machine } = mixing;
  const press = (next) => () => { tap(); set(clampAmount(next(get()))); };
  const machineButton = (dir) => el('button', { className: 'px machineBtn', onClick: press((ml) => stepMachine(ml, dir, formula, machine)) },
    el('span', {}, `${dir > 0 ? '+' : '-'}${machine.stepWaterMl}`),
    el('span', { className: 't9' }, machine.name));
  const fineButton = (d) => el('button', { className: 'px fineBtn', onClick: press((ml) => ml + d) }, d > 0 ? `+${d}` : String(d));

  if (!fine) return { before: [machineButton(-1)], after: [machineButton(+1)] };
  return { before: [fineButton(-10), machineButton(-1)], after: [machineButton(+1), fineButton(10)] };
}
