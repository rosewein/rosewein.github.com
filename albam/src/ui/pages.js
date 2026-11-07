// 쪽 넘기기: [시계] ← [대시보드] → [타임라인] → [통계]. 처음과 기본은 대시보드.
//   - 화면을 옆으로 밀면(왼쪽으로 밀면 오른쪽 쪽으로)
//   - 아래 가운데 점을 눌러도(점 하나 = 쪽 하나)
//   - 타임라인·통계에서 cfg.statsIdleSeconds 동안 아무도 안 만지면 대시보드로 돌아온다.
//     시계 쪽은 탁상시계처럼 두고 보라고 돌아오지 않는다
//   - 큰 버튼(말하기·수유·기저귀·잠·지난 기록)을 누르면 대시보드로 돌아와 결과를 보여 준다
// 창이 열려 있거나 밤 화면일 때는 밀어도 넘기지 않는다.

import { $, el, setHidden } from './dom.js';
import { LOGICAL } from './stage.js';
import { isSheetOpen } from './sheets.js';

/** 쪽 순서. id 는 index.html 의 쪽 요소 */
export const PAGES = [
  { name: 'clock', id: '#pageClock', label: '시계', returns: false },
  { name: 'main', id: '#pageMain', label: '대시보드', returns: false },
  { name: 'timeline', id: '#pageTimeline', label: '타임라인', returns: true },
  { name: 'stats', id: '#pageStats', label: '통계', returns: true },
];
const HOME = 'main';
/** 이만큼(논리 픽셀) 옆으로, 위아래보다 1.5배 넘게 밀어야 넘긴다 */
const SWIPE_MIN = 40;
const SWIPE_RATIO = 1.5;
/** 밀고 난 직후 손을 뗀 곳의 클릭은 버튼 누름으로 치지 않는다 */
const SUPPRESS_CLICK_MS = 400;

/**
 * @param {import('../main.js').AppContext} ctx
 * @param {{onShow?: Record<string, () => void>, onHide?: Record<string, () => void>}} hooks
 */
export function setupPages(ctx, { onShow = {}, onHide = {} }) {
  const stage = $('#stage');
  let current = HOME;
  let start = null;
  let suppressUntil = 0;
  const index = (name) => PAGES.findIndex((p) => p.name === name);

  const dots = PAGES.map((p) => el('button', {
    className: `dot${p.name === current ? ' on' : ''}`, title: p.label,
    onClick: () => { if (blocked()) return; ctx.sfx.tap(); show(p.name); },
  }));
  dots.forEach((d, i) => d.setAttribute('aria-label', PAGES[i].label));
  $('#pageDots').replaceChildren(...dots);

  function show(name) {
    if (name === current) return;
    onHide[current]?.();
    current = name;
    for (const p of PAGES) setHidden($(p.id), p.name !== name);
    dots.forEach((d, i) => d.classList.toggle('on', PAGES[i].name === name));
    onShow[name]?.();
  }

  // 창이 열려 있거나 밤 화면이면 안 넘긴다. 저장 직후 [취소]가 떠 있을 때는 넘겨도 된다(방금 넣은 걸 타임라인에서 보려고)
  const blocked = () => isSheetOpen() || !$('#night').classList.contains('hidden');

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
    const next = index(current) + (dx < 0 ? 1 : -1);
    if (next >= 0 && next < PAGES.length) {
      ctx.sfx.tap();
      show(PAGES[next].name);
    }
  }, true);
  stage.addEventListener('click', (e) => {
    if (Date.now() < suppressUntil) { e.stopPropagation(); e.preventDefault(); }
  }, true);

  $('#actions').addEventListener('click', () => show(HOME), true);

  setInterval(() => {
    const page = PAGES[index(current)];
    if (page.returns && !ctx.isBusy() && Date.now() - ctx.state.lastTouchAt > ctx.cfg.statsIdleSeconds * 1000) show(HOME);
  }, 5000);

  return { show, current: () => current };
}
