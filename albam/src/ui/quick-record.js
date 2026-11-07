// 큰 버튼 [수유] [기저귀] 과 그 창, 그리고 [잠](달) 버튼.
// [잠]: 안 자고 있으면 누르는 순간 '잠 시작(지금)'을 넣고, 자는 중이면 '깼어요(지금)'로 끝을 넣는다.
//       언제 깰지 모르니 잠은 끝 없이 먼저 넣는다(supabase/004_sleep_end.sql). 둘 다 저장 직후 [취소]가 뜬다.
// 수유 창의 빠른 선택 양은 '수유량 설정'(feed-amounts.js)에서 정한 값이다.
// 양은 완성량(ml)으로 기록하고, 브레짜에서 고를 물 양을 같이 보여 준다(../formula.js).

import { $, $$, el } from './dom.js';
import { openSheet } from './sheets.js';
import { amountSteppers, amountView, quickAmountLabel } from './amount.js';
import { KIND, SOURCE, sleepingNow } from '../domain.js';

export { clampAmount } from './amount.js';

/**
 * 수유량 빠른 선택(순수 함수): 요약의 feed_amounts, 아직 못 받았으면 설정 기본값. 작은 것부터
 * @param {import('../domain.js').Summary|null} summary
 * @param {number[]} defaults
 */
export function feedAmountsOf(summary, defaults) {
  const list = summary?.feed_amounts?.length ? summary.feed_amounts : defaults;
  return [...new Set(list)].sort((a, b) => a - b);
}

/** @param {import('../main.js').AppContext} ctx */
export function setupQuickRecord(ctx) {
  const { state, cfg, sfx } = ctx;
  let amount = 200;

  // ── 수유 ──
  const quickAmounts = () => feedAmountsOf(state.summary, cfg.defaultAmounts);
  const steppers = amountSteppers({
    get: () => amount,
    set: (ml) => { amount = ml; renderFeed(); },
    mixing: cfg,
    tap: sfx.tap,
  });

  function renderFeed() {
    $('#amountRow').replaceChildren(...quickAmounts().map((ml) => el('button', {
      className: `px${ml === amount ? ' on' : ''}`,
      onClick: () => { sfx.tap(); amount = ml; renderFeed(); },
    }, ...quickAmountLabel(ml, cfg))));
    // [-10] [-30 브레짜] 200ml/브레짜 180 [+30 브레짜] [+10]
    $('#stepRow').replaceChildren(...steppers.before, amountView(amount, cfg), ...steppers.after);
  }

  /** 수유 창 열기. keepAmount 면 고르던 양을 그대로(수유량 설정에서 돌아올 때) */
  function openFeed({ keepAmount = false } = {}) {
    // 기본 선택은 마지막으로 먹인 양
    if (!keepAmount) amount = state.summary?.last_feed?.ml ?? quickAmounts()[0] ?? 200;
    renderFeed();
    openSheet('feedSheet');
  }

  $('#feedBtn').addEventListener('click', () => { sfx.tap(); openFeed(); });
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

  // ── 잠: 시작 / 깼어요 ──
  $('#sleepBtn').addEventListener('click', () => {
    sfx.tap();
    const sleeping = sleepingNow(state.summary);
    if (sleeping) ctx.wake(sleeping);
    else ctx.save({ kind: KIND.SLEEP, occurred_at: ctx.now(), detail: {}, source: SOURCE.TOUCH });
  });

  return { openFeed, quickAmounts };
}
