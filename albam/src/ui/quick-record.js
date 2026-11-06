// 큰 버튼 [수유] [기저귀] 과 그 창.
// 수유 창의 빠른 선택 양은 '수유량 설정'(feed-amounts.js)에서 정한 값이다.

import { $, $$, el } from './dom.js';
import { openSheet } from './sheets.js';
import { KIND, SOURCE } from '../domain.js';

const AMOUNT = { min: 5, max: 500 };

/**
 * 수유량 빠른 선택(순수 함수): 요약의 feed_amounts, 아직 못 받았으면 설정 기본값. 작은 것부터
 * @param {import('../domain.js').Summary|null} summary
 * @param {number[]} defaults
 */
export function feedAmountsOf(summary, defaults) {
  const list = summary?.feed_amounts?.length ? summary.feed_amounts : defaults;
  return [...new Set(list)].sort((a, b) => a - b);
}

export const clampAmount = (ml) => Math.min(AMOUNT.max, Math.max(AMOUNT.min, ml));

/** @param {import('../main.js').AppContext} ctx */
export function setupQuickRecord(ctx) {
  const { state, cfg, sfx } = ctx;
  let amount = 200;

  // ── 수유 ──
  const quickAmounts = () => feedAmountsOf(state.summary, cfg.defaultAmounts);

  function renderFeed() {
    $('#amountRow').replaceChildren(...quickAmounts().map((ml) => el('button', {
      className: `px${ml === amount ? ' on' : ''}`,
      onClick: () => { sfx.tap(); amount = ml; renderFeed(); },
    }, String(ml))));
    $('#stepVal').textContent = `${amount}ml`;
  }

  /** 수유 창 열기. keepAmount 면 고르던 양을 그대로(수유량 설정에서 돌아올 때) */
  function openFeed({ keepAmount = false } = {}) {
    // 기본 선택은 마지막으로 먹인 양
    if (!keepAmount) amount = state.summary?.last_feed?.ml ?? quickAmounts()[0] ?? 200;
    renderFeed();
    openSheet('feedSheet');
  }

  $('#feedBtn').addEventListener('click', () => { sfx.tap(); openFeed(); });
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

  return { openFeed, quickAmounts };
}
