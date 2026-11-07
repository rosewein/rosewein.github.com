// 쪽 넘기기: [대시보드] ↔ [통계]. 아래 큰 버튼 줄은 두 쪽 모두에 그대로 있다.
//   - 화면을 옆으로 밀면(왼쪽 → 통계, 오른쪽 → 대시보드)
//   - 아래 가운데 점 두 개를 눌러도
//   - 통계 쪽에서 cfg.statsIdleSeconds 동안 아무도 안 만지면 대시보드로 돌아온다(거실 화면은 늘 대시보드가 기본)
//   - 큰 버튼(말하기·수유·기저귀·지난 기록)을 누르면 대시보드로 돌아와 결과를 보여 준다
// 창이 열려 있거나 밤 화면일 때는 밀어도 넘기지 않는다.

import { $, $$, setHidden } from './dom.js';
import { LOGICAL } from './stage.js';

const PAGES = ['main', 'stats'];
const PAGE_ID = { main: '#pageMain', stats: '#pageStats' };
/** 이만큼(논리 픽셀) 옆으로, 위아래보다 1.5배 넘게 밀어야 넘긴다 */
const SWIPE_MIN = 40;
const SWIPE_RATIO = 1.5;
/** 밀고 난 직후 손을 뗀 곳의 클릭은 버튼 누름으로 치지 않는다 */
const SUPPRESS_CLICK_MS = 400;

/**
 * @param {import('../main.js').AppContext} ctx
 * @param {{onShow: Record<string, () => void>}} hooks
 */
export function setupPages(ctx, { onShow }) {
  const stage = $('#stage');
  let current = 'main';
  let start = null;
  let suppressUntil = 0;

  function show(page) {
    if (page === current) return;
    current = page;
    for (const p of PAGES) setHidden($(PAGE_ID[p]), p !== page);
    $$('#pageDots .dot').forEach((d, i) => d.classList.toggle('on', PAGES[i] === page));
    $('#pageDots').setAttribute('aria-label', page === 'main' ? '통계 보기' : '대시보드로');
    onShow[page]?.();
  }

  const blocked = () => ctx.isBusy() || !$('#night').classList.contains('hidden');

  stage.addEventListener('pointerdown', (e) => {
    start = e.isPrimary ? { x: e.clientX, y: e.clientY } : null;
  }, true);
  stage.addEventListener('pointercancel', () => { start = null; }, true);
  stage.addEventListener('pointerup', (e) => {
    if (!start || !e.isPrimary) return;
    const unit = stage.getBoundingClientRect().width / LOGICAL.width;   // 화면 픽셀 → 논리 픽셀
    const dx = (e.clientX - start.x) / unit;
    const dy = (e.clientY - start.y) / unit;
    start = null;
    if (Math.abs(dx) < SWIPE_MIN || Math.abs(dx) < Math.abs(dy) * SWIPE_RATIO || blocked()) return;
    suppressUntil = Date.now() + SUPPRESS_CLICK_MS;
    const next = PAGES.indexOf(current) + (dx < 0 ? 1 : -1);
    if (next >= 0 && next < PAGES.length) {
      ctx.sfx.tap();
      show(PAGES[next]);
    }
  }, true);
  stage.addEventListener('click', (e) => {
    if (Date.now() < suppressUntil) { e.stopPropagation(); e.preventDefault(); }
  }, true);

  $('#pageDots').addEventListener('click', () => {
    if (blocked()) return;
    ctx.sfx.tap();
    show(current === 'main' ? 'stats' : 'main');
  });
  $('#actions').addEventListener('click', () => show('main'), true);

  setInterval(() => {
    if (current !== 'main' && !ctx.isBusy() && Date.now() - ctx.state.lastTouchAt > ctx.cfg.statsIdleSeconds * 1000) show('main');
  }, 5000);

  return { show, current: () => current };
}
