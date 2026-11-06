// 큰 버튼 [수유] [기저귀] 과 그 창.

import { $, $$, el } from './dom.js';
import { openSheet } from './sheets.js';
import { KIND, SOURCE } from '../domain.js';

const AMOUNT = { min: 5, max: 500 };
const QUICK_COUNT = 3;

/**
 * 수유량 빠른 선택: 최근 먹인 양을 먼저, 모자라면 기본값으로 채워 작은 것부터(순수 함수)
 * @param {number[]} recent  요약의 recent_feed_amounts
 * @param {number[]} defaults
 */
export function chooseQuickAmounts(recent, defaults) {
  const list = (recent || []).filter((x) => x != null).slice(0, QUICK_COUNT);
  for (const d of defaults) if (list.length < QUICK_COUNT && !list.includes(d)) list.push(d);
  return list.sort((a, b) => a - b);
}

export const clampAmount = (ml) => Math.min(AMOUNT.max, Math.max(AMOUNT.min, ml));

/** @param {import('../main.js').AppContext} ctx */
export function setupQuickRecord(ctx) {
  const { state, cfg, sfx } = ctx;
  let amount = 160;

  // ── 수유 ──
  const quickAmounts = () => chooseQuickAmounts(state.summary?.recent_feed_amounts, cfg.defaultAmounts);

  function renderFeed() {
    $('#amountRow').replaceChildren(...quickAmounts().map((ml) => el('button', {
      className: `px${ml === amount ? ' on' : ''}`,
      onClick: () => { sfx.tap(); amount = ml; renderFeed(); },
    }, String(ml))));
    $('#stepVal').textContent = `${amount}ml`;
  }

  $('#feedBtn').addEventListener('click', () => {
    sfx.tap();
    // 기본 선택은 마지막으로 먹인 양
    amount = state.summary?.last_feed?.ml ?? quickAmounts()[0] ?? 160;
    renderFeed();
    openSheet('feedSheet');
  });
  for (const btn of $$('#stepRow [data-step]')) {
    btn.addEventListener('click', () => { sfx.tap(); amount = clampAmount(amount + Number(btn.dataset.step)); renderFeed(); });
  }
  $('#feedSave').addEventListener('click', () => ctx.save({
    kind: KIND.FEED, amount_ml: amount, occurred_at: ctx.now(), detail: {}, source: SOURCE.TOUCH,
  }));

  // ── 기저귀: 종류를 누르면 바로 저장 ──
  $('#diaperBtn').addEventListener('click', () => { sfx.tap(); openSheet('diaperSheet'); });
  for (const btn of $$('#diaperSheet [data-type]')) {
    btn.addEventListener('click', () => ctx.save({
      kind: KIND.DIAPER, occurred_at: ctx.now(), detail: { type: btn.dataset.type }, source: SOURCE.TOUCH,
    }));
  }
}
