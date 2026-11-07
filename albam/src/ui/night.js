// 밤 화면. 화면을 끄지 않고 거의 검게 바꿔서 앱이 살아 있게 한다(터치·음성을 바로 받으려고).
// 아주 어두운 글자로 마지막 수유 뒤 지난 시간만 띄우고, 번인이 생기지 않게 1분마다 자리를 옮긴다.
// 터치하면 몇 초 동안 원래 화면을 어둡게(brightness) 보여 준다.

import { $, el, setHidden } from './dom.js';
import { formatAgo, formatClock } from '../time.js';

const MOVE_EVERY_MS = 60000;
/** 글자 덩어리(약 180x40)가 놓일 수 있는 왼쪽 위 범위(논리 픽셀). 위·아래 곡면 8px 과 좌우 16px 을 넘지 않게 */
const AREA = { left: 24, top: 14, width: 150, height: 110 };

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
    const feed = state.summary?.last_feed;
    const text = $('#nightText');
    text.style.left = `${spot.x}px`;
    text.style.top = `${spot.y}px`;
    // "2시간 35분 전" / "마지막 수유 21:05 · 지금 23:40"
    text.replaceChildren(
      el('div', { className: 't24' }, feed ? formatAgo(feed.at, now) : '수유 기록 없음'),
      el('div', { className: 't9', style: { marginTop: '4px' } },
        `${feed ? `마지막 수유 ${formatClock(feed.at)} · ` : ''}지금 ${formatClock(now)}`),
    );
  }

  return { update };
}
