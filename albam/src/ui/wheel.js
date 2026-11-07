// 굴리는 바퀴(날짜·시·분 고르기). 세 칸이 보이고 가운데가 고른 값이다.
//   - 위아래로 끌면 한 칸(22px)마다 한 단위씩 움직이고, 튕기면 관성으로 더 돈다
//   - 위 칸을 누르면 -1, 아래 칸을 누르면 +1
//   - 가운데를 누르면 onCenterTap(직접 입력)
//   - 마우스 휠도 된다
// 값 자체는 바깥이 가진다: label(k) 는 지금 값에서 k 칸 떨어진 글, step(d) 는 d 칸 움직이고 움직였는지 돌려준다.

import { el } from './dom.js';
import { LOGICAL } from './stage.js';

const ROW = 22;
/** 이보다 덜 움직이고 떼면 누름으로 본다(논리 픽셀) */
const TAP_SLOP = 4;
/** 관성: 칸/ms. 이보다 느리면 멈춤, 이보다 빠르면 자름 */
const MIN_FLING = 0.004;
const MAX_FLING = 0.06;
/** 1ms 마다 속도에 곱하는 값(마찰) */
const FRICTION = 0.996;
/** 떼기 직전 이만큼(ms)의 움직임으로 속도를 잰다 */
const VELOCITY_WINDOW = 100;

/**
 * @param {{className?: string, label: (k: number) => string, step: (d: number) => boolean,
 *          onCenterTap?: () => void, onTapStep?: () => void}} o
 * @returns {{el: HTMLElement, refresh: () => void}}
 */
export function createWheel({ className = '', label, step, onCenterTap, onTapStep }) {
  const col = el('div', { className: 'col' });
  const root = el('div', { className: `wheel ${className}` }, el('div', { className: 'band' }), col);
  /** 끄는 중 조금 밀린 정도(칸). 양수 = 글이 아래로 내려감 = 작은 값이 가운데로 */
  let offset = 0;
  let drag = null;
  let anim = 0;

  function refresh() {
    col.replaceChildren(...[-2, -1, 0, 1, 2].map((k) => el('div', { className: `item${k === 0 ? ' c' : ''}` }, label(k))));
    col.style.transform = `translateY(${offset * ROW}px)`;
  }

  /** 반 칸 넘게 밀리면 값을 한 칸 옮긴다. 끝에 닿으면 false */
  function settle() {
    let changed = false;
    let ok = true;
    while (ok && offset >= 0.5) { ok = step(-1); if (ok) { offset -= 1; changed = true; } }
    while (ok && offset <= -0.5) { ok = step(1); if (ok) { offset += 1; changed = true; } }
    if (!ok) offset = 0;
    if (changed || !ok) refresh(); else col.style.transform = `translateY(${offset * ROW}px)`;
    return ok;
  }

  const unit = () => root.closest('#stage').getBoundingClientRect().width / LOGICAL.width;   // 화면 픽셀 → 논리 픽셀
  const stopAnim = () => { cancelAnimationFrame(anim); anim = 0; };

  function fling(v) {
    let last = performance.now();
    const frame = (t) => {
      const dt = Math.min(50, t - last);
      last = t;
      offset += v * dt;
      v *= FRICTION ** dt;
      if (!settle() || Math.abs(v) < MIN_FLING) { offset = 0; refresh(); anim = 0; return; }
      anim = requestAnimationFrame(frame);
    };
    anim = requestAnimationFrame(frame);
  }

  root.addEventListener('pointerdown', (e) => {
    stopAnim();
    root.setPointerCapture?.(e.pointerId);
    drag = { y: e.clientY, startY: e.clientY, moved: 0, samples: [{ t: e.timeStamp, y: e.clientY }], u: unit() };
  });
  root.addEventListener('pointermove', (e) => {
    if (!drag) return;
    const dy = (e.clientY - drag.y) / drag.u;
    drag.y = e.clientY;
    drag.moved = Math.max(drag.moved, Math.abs(e.clientY - drag.startY) / drag.u);
    drag.samples.push({ t: e.timeStamp, y: e.clientY });
    while (drag.samples.length > 2 && e.timeStamp - drag.samples[0].t > VELOCITY_WINDOW) drag.samples.shift();
    offset += dy / ROW;
    settle();
  });
  const end = (e) => {
    if (!drag) return;
    const d = drag;
    drag = null;
    if (d.moved < TAP_SLOP) {
      offset = 0;
      const y = (e.clientY - root.getBoundingClientRect().top) / d.u;
      if (y < ROW) { if (step(-1)) onTapStep?.(); } else if (y > ROW * 2) { if (step(1)) onTapStep?.(); } else onCenterTap?.();
      refresh();
      return;
    }
    // 떼기 직전 VELOCITY_WINDOW 동안 움직인 빠르기. 멈췄다 떼면 관성 없음
    const recent = d.samples.filter((s) => e.timeStamp - s.t <= VELOCITY_WINDOW);
    const first = recent[0];
    const last = recent[recent.length - 1];
    const dt = recent.length > 1 ? last.t - first.t : 0;
    const v = dt > 0 ? (last.y - first.y) / d.u / ROW / dt : 0;
    if (Math.abs(v) > MIN_FLING * 2) fling(Math.sign(v) * Math.min(MAX_FLING, Math.abs(v)));
    else { offset = 0; refresh(); }
  };
  root.addEventListener('pointerup', end);
  root.addEventListener('pointercancel', (e) => { drag = null; offset = 0; refresh(); });
  root.addEventListener('wheel', (e) => { e.preventDefault(); stopAnim(); if (step(Math.sign(e.deltaY))) refresh(); }, { passive: false });

  refresh();
  return { el: root, refresh };
}
