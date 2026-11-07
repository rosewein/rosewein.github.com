// 수유량 설정: 수유 창의 빠른 선택 양 세 개를 바꾸는 창.
// 브레짜로 타므로 브레짜 한 칸(물 30ml) 단위로만 바꾼다(브레짜 180 = 200ml, 210 = 230ml, 240 = 270ml).
// 저장하면 Supabase care_settings.feed_amounts 에 들어가 모든 기기가 같은 양을 쓴다.
// 연결이 끊겼으면 기록처럼 쌓아 두었다가 보낸다(api/index.js updateFeedAmounts).

import { $, el } from './dom.js';
import { openSheet } from './sheets.js';
import { amountSteppers, amountView } from './amount.js';
import { APTAMIL, BREZZA, stepMachine } from '../formula.js';

/** 칸 수. 수유 창에 버튼 세 개가 들어간다 */
export const SLOT_COUNT = 3;

/**
 * 지금 양 목록을 칸 수에 맞춘다(순수 함수). 모자라면 마지막 양에서 브레짜 한 칸씩 더해 채운다.
 * @param {number[]} amounts
 * @param {import('./amount.js').Mixing} [mixing]
 */
export function toSlots(amounts, { formula = APTAMIL, machine = BREZZA } = {}) {
  const slots = [...amounts].sort((a, b) => a - b).slice(0, SLOT_COUNT);
  while (slots.length < SLOT_COUNT) slots.push(stepMachine(slots.at(-1) ?? 170, +1, formula, machine));
  return slots;
}

/**
 * @param {import('../main.js').AppContext} ctx
 * @param {{current: () => number[], back: () => void}} deps  current: 지금 빠른 선택, back: 수유 창으로 돌아가기
 */
export function setupFeedAmounts(ctx, { current, back }) {
  const { sfx, cfg } = ctx;
  let slots = [];

  function render() {
    $('#amountSlots').replaceChildren(...slots.map((ml, i) => {
      // 칸마다 [-30 브레짜] 230ml 브레짜 210 [+30 브레짜]
      const steps = amountSteppers({
        get: () => slots[i],
        set: (v) => { slots[i] = v; render(); },
        mixing: cfg,
        tap: sfx.tap,
        fine: false,
      });
      return el('div', { className: 'row slot' },
        el('span', { className: 'lbl' }, `${i + 1}`), ...steps.before, amountView(ml, cfg, { inline: true }), ...steps.after);
    }));
    const dup = new Set(slots).size < slots.length;
    $('#amountMsg').textContent = dup ? '같은 양이 있어요. 하나로 합쳐 저장돼요' : '';
  }

  $('#amountEditBtn').addEventListener('click', () => {
    sfx.tap();
    slots = toSlots(current(), cfg);
    render();
    openSheet('amountSheet');
  });
  $('#amountCancel').addEventListener('click', () => { sfx.tap(); back(); });
  $('#amountSave').addEventListener('click', async () => {
    try {
      const r = await ctx.api.updateFeedAmounts(slots);
      sfx.save();
      // 따로 알리지 않는다: 돌아간 수유 창에 새 양이 바로 보이고, 못 보냈으면 "대기 n건"이 뜬다
      await ctx.refresh();
      // 연결이 끊겨 refresh 가 못 받아도 바로 보이게
      if (ctx.state.summary) ctx.state.summary.feed_amounts = r.feed_amounts;
      back();
    } catch (e) {
      sfx.error();
      $('#amountMsg').textContent = `저장 못 함: ${e.message}`;
    }
  });
}
