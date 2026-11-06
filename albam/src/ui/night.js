// 밤 화면. 화면을 끄지 않고 거의 검게 바꿔서 앱이 살아 있게 한다(터치·음성을 바로 받으려고).
// 아주 어두운 글자로 경과 시간만 띄우고, 번인이 생기지 않게 1분마다 자리를 옮긴다.
// 터치하면 몇 초 동안 원래 화면을 어둡게(brightness) 보여 준다.

import { $, el, setHidden } from './dom.js';
import { formatClock, formatElapsed } from '../time.js';

const MOVE_EVERY_MS = 60000;
/** 글자 덩어리가 놓일 수 있는 범위(논리 픽셀). 곡면 가장자리는 피함 */
const AREA = { left: 24, top: 12, width: 230, height: 120 };

/** @param {import('../main.js').AppContext} ctx */
export function setupNight(ctx) {
  const { state, cfg } = ctx;
  let spot = { x: 140, y: 70, movedAt: 0 };
  const wakeFor = () => { state.nightWakeUntil = Date.now() + cfg.nightWakeSeconds * 1000; };

  // 검은 화면을 누르면 깨움. 그 누름이 아래 버튼까지 가지 않게 막는다
  $('#night').addEventListener('pointerdown', (e) => {
    e.preventDefault();
    e.stopPropagation();
    wakeFor();
    ctx.tick();
  });
  // 깨어 있는 동안 만지면 더 깨어 있음
  document.addEventListener('pointerdown', () => { if (ctx.isNightAwake()) wakeFor(); }, true);

  /** tick 마다 부름 */
  function update() {
    const dark = ctx.isNightTime() && !ctx.isNightAwake() && !ctx.isBusy();
    setHidden($('#night'), !dark);
    document.body.classList.toggle('nightWake', ctx.isNightTime() && !dark);
    if (!dark) return;

    if (Date.now() - spot.movedAt > MOVE_EVERY_MS) {
      spot = {
        x: AREA.left + Math.floor(Math.random() * AREA.width),
        y: AREA.top + Math.floor(Math.random() * AREA.height),
        movedAt: Date.now(),
      };
    }
    const now = ctx.now();
    const text = $('#nightText');
    text.style.left = `${spot.x}px`;
    text.style.top = `${spot.y}px`;
    text.replaceChildren(
      el('div', { className: 't24' }, formatElapsed(state.summary?.last_feed?.at, now)),
      el('div', { className: 't9', style: { marginTop: '4px' } }, `수유 후 · ${formatClock(now)}`),
    );
  }

  return { update };
}
