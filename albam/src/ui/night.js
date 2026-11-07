// 밤 화면. 화면을 끄지 않고 검게 바꿔서 앱이 살아 있게 한다(터치·음성을 바로 받으려고).
// 검은 바탕에 지금 가장 궁금한 것을 크게 띄우고, 번인이 생기지 않게 1분마다 자리를 옮긴다.
// 터치하면 몇 초 동안 원래 화면을 어둡게(brightness) 보여 준다.
// "전" 대신 "수유 후 … 지남"처럼 무엇이 얼마나 지났는지 글로 쓴다.
//
//   안 자는 중                               자는 중(잠 기록이 열려 있음)
//   🍼 │ 수유 후 2시간 16분 지남              🌙 │ 1시간 53분째 자는 중
//   ┌🍼 마지막 수유 19:46 │ 🕓 지금 22:03┐   ┌🍼 수유 후 2시간 16분 지남┐
//                                            마지막 수유 19:46 · 200ml │ 지금 22:03
// 가장 긴 경우(12시간 넘음)도 화면 폭(348) 안에 들어가게 작은 글을 섞었다.

import { $, el, setHidden } from './dom.js';
import { agoParts, formatClock } from '../time.js';
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
      const feedParts = feed ? agoParts(feed.at, now) : [];
      // 숫자는 크게(주황), 단위는 작게. small 이면 한 단계 작게(테두리 칸 안)
      const amount = (parts, { tail = '', last = '', small = false, tailSmall = false } = {}) => parts.flatMap(([n, u], i) => [
        el('span', { className: small ? 'vn' : 'num' }, n),
        el('span', { className: small ? 'vu' : 'unit' }, u + (i === parts.length - 1 ? last : '')),
      ]).concat(tail ? [el('span', { className: small || tailSmall ? 'vu tail' : 'unit' }, tail)] : []);
      const sinceFeed = (small) => (!feed ? [el('span', { className: small ? 'vu' : 't24' }, '수유 기록 없음')]
        : !feedParts.length ? [el('span', { className: small ? 'vu' : 'unit' }, '방금 먹음')]
          : [el('span', { className: small ? 'vu' : 'pre' }, '수유 후'), ...amount(feedParts, { tail: '지남', small })]);
      const nowBox = [el('span', { className: 'sep' }), el('span', { className: 'spr ico ico-clock' }), el('span', {}, '지금'), el('span', { className: 'v acc' }, formatClock(now))];

      if (sleeping) {
        const sleepParts = agoParts(sleeping.at, now);
        text.replaceChildren(
          el('div', { className: 'nightMain' },
            el('span', { className: 'spr ico x2 ico-moon' }), el('span', { className: 'sep' }),
            ...(sleepParts.length ? amount(sleepParts, { last: '째', tail: '자는 중', tailSmall: true }) : [el('span', { className: 'unit' }, '방금 잠들었어요')])),
          el('div', { className: 'nightBox' }, el('span', { className: 'spr ico ico-bottle' }), ...sinceFeed(true)),
          el('div', { className: 'nightSub' },
            ...(feed ? [el('span', {}, `마지막 수유 ${formatClock(feed.at)}${feed.ml != null ? ` · ${feed.ml}ml` : ''}`), el('span', { className: 'sep' })] : []),
            el('span', {}, '지금 '), el('span', { className: 'acc' }, formatClock(now))),
        );
      } else {
        text.replaceChildren(
          el('div', { className: 'nightMain' }, el('span', { className: 'spr ico x2 ico-bottle' }), el('span', { className: 'sep' }), ...sinceFeed(false)),
          el('div', { className: 'nightBox' },
            ...(feed ? [el('span', { className: 'spr ico ico-bottle' }), el('span', {}, '마지막 수유'), el('span', { className: 'v' }, formatClock(feed.at))] : []),
            ...(feed ? nowBox : nowBox.slice(1))),
        );
      }
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
