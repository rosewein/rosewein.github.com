// 오른쪽 위 상태 칸과 왼쪽 캐릭터.
// render(): 요약이 바뀌었을 때 전부 다시 그림 / tick(): 0.6초마다 시계·경과 시간·캐릭터만

import { $ } from './dom.js';
import { DIAPER_LABEL } from '../domain.js';
import { formatAgo, formatClock, formatElapsed } from '../time.js';

/** 스프라이트 시트(sprites/albam.png)의 줄 순서. sprites.json 과 같다 */
const MOOD_ROW = { normal: 0, hungry: 1, sleep: 2, happy: 3 };
const MOOD_TEXT = { normal: '', hungry: '배고파요…', sleep: '쿨쿨', happy: '고마워요!' };
/** 스프라이트 한 칸(32px)을 3배로 그린다 */
const SPRITE_PX = 96;

/**
 * 캐릭터 기분 고르기(순수 함수).
 * 기쁨(방금 저장) > 잠(밤, 화면 꺼진 상태) > 배고픔(수유 후 오래) > 밤이면 잠 > 평소
 * @param {{happy: boolean, night: boolean, nightAwake: boolean, minutesSinceFeed: number|null, hungryMinutes: number}} p
 * @returns {'normal'|'hungry'|'sleep'|'happy'}
 */
export function chooseMood({ happy, night, nightAwake, minutesSinceFeed, hungryMinutes }) {
  if (happy) return 'happy';
  if (night && !nightAwake) return 'sleep';
  if (minutesSinceFeed != null && minutesSinceFeed > hungryMinutes) return 'hungry';
  if (night) return 'sleep';
  return 'normal';
}

/** @param {import('../main.js').AppContext} ctx */
export function createStatusView(ctx) {
  const { state, cfg } = ctx;
  let frame = 0;

  function render() {
    const s = state.summary;
    const feed = s?.last_feed;
    const diaper = s?.last_diaper;
    const now = ctx.now();

    $('#lastFeed').textContent = feed
      ? `수유 ${formatClock(feed.at)}${feed.ml != null ? ` · ${feed.ml}ml` : ''}`
      : '수유 기록 없음';
    $('#lastDiaper').textContent = diaper
      ? `기저귀 ${formatClock(diaper.at)} ${DIAPER_LABEL[diaper.type] || ''} · ${formatAgo(diaper.at, now)}`
      : '기저귀 기록 없음';
    $('#todayCount').textContent = s ? `${s.today?.feed_count ?? 0}회` : '-회';
    $('#todayMl').textContent = s ? `${s.today?.feed_ml ?? 0}ml` : '-ml';
    renderConnection();
    tick();
  }

  /** 상태 칸 위쪽('오늘' 왼쪽): 못 보낸 기록 수, 연결 상태 */
  function renderConnection() {
    const net = $('#net');
    if (state.pending) { net.textContent = `대기 ${state.pending}건`; net.className = 't9 acc'; }
    else if (state.stale) { net.textContent = '연결 안 됨'; net.className = 't9 warn'; }
    else { net.textContent = ctx.api.demo ? '미리 보기' : ''; net.className = 't9 faint'; }
  }

  function tick() {
    const now = ctx.now();
    const lastFeedAt = state.summary?.last_feed?.at;
    const mood = chooseMood({
      happy: Date.now() < state.happyUntil,
      night: ctx.isNightTime(),
      nightAwake: ctx.isNightAwake(),
      minutesSinceFeed: lastFeedAt ? (now - new Date(lastFeedAt)) / 60000 : null,
      hungryMinutes: cfg.hungryMinutes,
    });

    $('#clock').textContent = formatClock(now);
    $('#elapsed').textContent = formatElapsed(lastFeedAt, now);
    $('#elapsed').classList.toggle('warn', mood === 'hungry');
    $('#albam').style.backgroundPosition = `${-frame * SPRITE_PX}px ${-MOOD_ROW[mood] * SPRITE_PX}px`;

    // 말풍선: 잠깐 띄운 말 > 로그인 문제 > 기분
    const bubble = state.bubble && Date.now() < state.bubble.until ? state.bubble : null;
    $('#bubble').textContent = bubble?.text ?? (state.authProblem || MOOD_TEXT[mood]);
    $('#bubble').className = bubble?.tone || (state.authProblem ? 'warn' : '');
  }

  /** 캐릭터 두 칸 애니메이션 */
  function nextFrame() { frame ^= 1; tick(); }

  return { render, tick, nextFrame };
}
