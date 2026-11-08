// 화면 틀: 도트 크기 맞추기, 번인 대비 이동, 화면 켜짐 유지.

import { $ } from './dom.js';

/**
 * 논리 해상도. S10(2280x1080, 3040x1440) 모두 정확히 정수배(6배, 8배)가 된다.
 * 가로는 ?w=307 처럼 바꿔 볼 수 있다(300~380). P4 7인치(1024x600)는 높이 180 기준 가로 약 307.
 * 지금은 대시보드만 가로에 맞춰 줄어든다(타임라인·통계·입력 창은 380 기준).
 */
export const LOGICAL = { width: stageWidth(), height: 180 };
/** 이보다 좁으면 기록 버튼의 아이콘을 뺀다(#stage.narrow) */
const NARROW_BELOW = 340;

function stageWidth() {
  const w = Number(new URLSearchParams(globalThis.location?.search || '').get('w'));
  return w >= 300 && w <= 380 ? Math.round(w) : 380;
}

/**
 * 논리 화면을 기기 화소의 정수배로 키우고 가운데 둔다. 남는 곳은 검은 여백.
 * CSS zoom 을 써서 글자도 다시 그려 흐려지지 않게 한다.
 */
export function fitStage() {
  const dpr = window.devicePixelRatio || 1;
  const devW = window.innerWidth * dpr;
  const devH = window.innerHeight * dpr;
  const scale = Math.max(1, Math.floor(Math.min(devW / LOGICAL.width, devH / LOGICAL.height)));
  $('#stage').style.setProperty('--W', `${LOGICAL.width}px`);
  $('#stage').classList.toggle('narrow', LOGICAL.width < NARROW_BELOW);
  $('#stage').style.zoom = String(scale / dpr);
  // 왼쪽 위 모서리도 기기 화소에 맞춘다
  $('#wrap').style.left = `${Math.floor((devW - LOGICAL.width * scale) / 2) / dpr}px`;
  $('#wrap').style.top = `${Math.floor((devH - LOGICAL.height * scale) / 2) / dpr}px`;
}

/** 번인 대비로 옮길 자리(논리 픽셀). 가운데를 중심으로 1~2칸씩 돈다 */
const SHIFT_PATH = [[0, 0], [1, 0], [2, 1], [1, 2], [0, 1], [-1, 2], [-2, 1], [-1, 0], [-2, -1], [-1, -2], [0, -1], [1, -2], [2, -1]];

/** 몇 분마다 화면 전체를 조금씩 옮긴다 */
export function startBurnInShift(everyMinutes) {
  let i = 0;
  setInterval(() => {
    i = (i + 1) % SHIFT_PATH.length;
    const [x, y] = SHIFT_PATH[i];
    $('#shift').style.transform = `translate(${x}px, ${y}px)`;
  }, everyMinutes * 60000);
}

/**
 * Screen Wake Lock 으로 화면이 꺼지지 않게. 다른 앱에 갔다 오거나 화면이 꺼지면 풀리므로
 * 돌아올 때, 터치할 때, 1분마다 다시 잡는다.
 */
export function keepScreenOn() {
  let lock = null;
  async function acquire() {
    if (lock || !('wakeLock' in navigator) || document.visibilityState !== 'visible') return;
    try {
      lock = await navigator.wakeLock.request('screen');
      lock.addEventListener('release', () => { lock = null; });
    } catch (e) { lock = null; }
  }
  document.addEventListener('visibilitychange', acquire);
  document.addEventListener('pointerdown', acquire, true);
  setInterval(acquire, 60000);
  acquire();
}
