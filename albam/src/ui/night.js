// 밤 화면. 화면을 끄지 않고 검게 바꿔서 앱이 살아 있게 한다(터치·음성을 바로 받으려고).
// 검은 바탕에 마지막 수유 뒤 지난 시간을 크게 띄우고, 번인이 생기지 않게 1분마다 자리를 옮긴다.
// 터치하면 몇 초 동안 원래 화면을 어둡게(brightness) 보여 준다.
//
//   ⏰ │ 1시간 20분 전                  ← 숫자 크게(주황)
//   ┌🍼 마지막 수유 19:46 │ 🕓 지금 21:07┐
//   🌙 자는 중 2시간 10분               ← 자는 중일 때만

import { $, el, setHidden } from './dom.js';
import { agoParts, formatClock, formatDuration } from '../time.js';
import { sleepingNow } from '../domain.js';

const MOVE_EVERY_MS = 60000;
/** 글자 덩어리가 놓일 수 있는 범위(논리 픽셀). 위·아래 곡면 8px 과 좌우 16px 을 넘지 않게 */
const AREA = { left: 16, top: 10, right: 364, bottom: 170 };

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

    const now = ctx.now();
    const feed = state.summary?.last_feed;
    const sleeping = sleepingNow(state.summary);
    const text = $('#nightText');
    const key = `${feed?.at}|${formatClock(now)}|${sleeping?.at}`;
    if (text.dataset.key !== key) {
      text.dataset.key = key;
      const parts = feed ? agoParts(feed.at, now) : [];
      text.replaceChildren(
        el('div', { className: 'nightMain' },
          el('span', { className: 'spr ico x2 ico-alarm' }), el('span', { className: 'sep' }),
          ...(!feed ? [el('span', { className: 't24' }, '수유 기록 없음')]
            : !parts.length ? [el('span', { className: 'num' }, '방금')]
              : [...parts.flatMap(([n, u]) => [el('span', { className: 'num' }, n), el('span', { className: 'unit' }, u)]), el('span', { className: 'unit' }, '전')])),
        el('div', { className: 'nightBox' },
          ...(feed ? [el('span', { className: 'spr ico ico-bottle' }), el('span', {}, '마지막 수유'), el('span', { className: 'v' }, formatClock(feed.at)), el('span', { className: 'sep' })] : []),
          el('span', { className: 'spr ico ico-clock' }), el('span', {}, '지금'), el('span', { className: 'v acc' }, formatClock(now))),
        ...(sleeping ? [el('div', { className: 'nightSleep' }, el('span', { className: 'spr ico ico-moon' }), el('span', {}, '자는 중'),
          el('span', { className: 'v' }, formatDuration(now - new Date(sleeping.at))))] : []),
      );
    }
    // 1분마다 자리 옮기기. 글 덩어리 크기를 재서 화면 밖으로 나가지 않게
    if (Date.now() - spot.movedAt > MOVE_EVERY_MS) {
      const w = text.offsetWidth || 260;
      const h = text.offsetHeight || 90;
      spot = {
        x: AREA.left + Math.floor(Math.random() * Math.max(1, AREA.right - AREA.left - w)),
        y: AREA.top + Math.floor(Math.random() * Math.max(1, AREA.bottom - AREA.top - h)),
        movedAt: Date.now(),
      };
      text.style.left = `${spot.x}px`;
      text.style.top = `${spot.y}px`;
    }
  }

  return { update };
}
