// 수유량 설정: 수유 창의 빠른 선택 양 세 개를 바꾸는 창.
// 저장하면 Supabase care_settings.feed_amounts 에 들어가 모든 기기가 같은 양을 쓴다.
// 연결이 끊겼으면 기록처럼 쌓아 두었다가 보낸다(api/index.js updateFeedAmounts).

import { $, el } from './dom.js';
import { openSheet } from './sheets.js';
import { clampAmount } from './quick-record.js';

/** 칸 수. 수유 창에 버튼 세 개가 들어간다 */
export const SLOT_COUNT = 3;
const STEPS = [-10, -5, 5, 10];

/**
 * 지금 양 목록을 칸 수에 맞춘다(순수 함수). 모자라면 마지막 양에서 20ml씩 더해 채운다.
 * @param {number[]} amounts
 */
export function toSlots(amounts) {
  const slots = [...amounts].sort((a, b) => a - b).slice(0, SLOT_COUNT);
  while (slots.length < SLOT_COUNT) slots.push(clampAmount((slots.at(-1) ?? 180) + 20));
  return slots;
}

/**
 * @param {import('../main.js').AppContext} ctx
 * @param {{current: () => number[], back: () => void}} deps  current: 지금 빠른 선택, back: 수유 창으로 돌아가기
 */
export function setupFeedAmounts(ctx, { current, back }) {
  const { sfx } = ctx;
  let slots = [];

  function render() {
    $('#amountSlots').replaceChildren(...slots.map((ml, i) => el('div', { className: 'row slot' },
      el('span', { className: 'lbl' }, `${i + 1}`),
      ...STEPS.slice(0, 2).map((d) => stepButton(i, d)),
      el('div', { className: 'val t24' }, `${ml}ml`),
      ...STEPS.slice(2).map((d) => stepButton(i, d)),
    )));
    const dup = new Set(slots).size < slots.length;
    $('#amountMsg').textContent = dup ? '같은 양이 있어요. 하나로 합쳐 저장돼요' : '';
  }

  function stepButton(i, delta) {
    return el('button', {
      className: 'px',
      onClick: () => { sfx.tap(); slots[i] = clampAmount(slots[i] + delta); render(); },
    }, delta > 0 ? `+${delta}` : String(delta));
  }

  $('#amountEditBtn').addEventListener('click', () => {
    sfx.tap();
    slots = toSlots(current());
    render();
    openSheet('amountSheet');
  });
  $('#amountCancel').addEventListener('click', () => { sfx.tap(); back(); });
  $('#amountSave').addEventListener('click', async () => {
    try {
      const r = await ctx.api.updateFeedAmounts(slots);
      sfx.save();
      ctx.say(r.status === 'queued' ? '수유량 저장(대기)' : '수유량을 바꿨어요');
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
