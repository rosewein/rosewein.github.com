// 오른쪽 위 상태 칸과 왼쪽 캐릭터.
// render(): 요약이 바뀌었을 때 / tick(): 0.6초마다(시계, 지난 시간, 캐릭터). 글이 그대로면 DOM 을 건드리지 않는다.
//
// 시각은 모두 무엇의 시각인지 글로 붙인다:
//   마지막 수유 11:25 · 160ml        지금 14:00
//   2시간 35분 전                     ← 마지막 수유 뒤 지난 시간(숫자 크게)
//   오늘 수유 3회 · 420ml             대기 n건
//   마지막 기저귀 소변 · 1시간 10분 전

import { $, el } from './dom.js';
import { DIAPER_LABEL } from '../domain.js';
import { agoParts, formatAgo, formatClock } from '../time.js';

/** 스프라이트 시트(sprites/albam.png)의 줄 순서. sprites.json 과 같다 */
const MOOD_ROW = { normal: 0, hungry: 1, sleep: 2, happy: 3 };
const MOOD_TEXT = { normal: '', hungry: '배고파요…', sleep: '쿨쿨', happy: '고마워요!' };
/** 스프라이트 한 칸(32px)을 3배로 그린다 */
const SPRITE_PX = 96;
/** 기저귀 줄은 좁아서 이 시간 넘으면 "11시간 전"처럼 분을 뺀다 */
const DIAPER_HOURS_ONLY = 10;

/** 흐린 이름표 + 굵은 값 한 줄. 글이 같으면 다시 그리지 않는다 */
function setLine(node, label, value) {
  const key = `${label}|${value}`;
  if (node.dataset.key === key) return;
  node.dataset.key = key;
  node.replaceChildren(el('span', { className: 'lbl' }, label), el('span', { className: 'val' }, value));
}

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
    setLine($('#lastFeed'), '마지막 수유', feed ? `${formatClock(feed.at)}${feed.ml != null ? ` · ${feed.ml}ml` : ''}` : '기록 없음');
    setLine($('#today'), '오늘 수유', s ? `${s.today?.feed_count ?? 0}회 · ${s.today?.feed_ml ?? 0}ml` : '-');
    renderConnection();
    tick();
  }

  /** 큰 글씨: 마지막 수유 뒤 지난 시간. 숫자는 크게, 단위는 작게 */
  function renderElapsed(lastFeedAt, now, hungry) {
    const box = $('#elapsed');
    const text = lastFeedAt ? formatAgo(lastFeedAt, now) : '수유 기록 없음';
    box.classList.toggle('warn', hungry);
    if (box.dataset.key === text) return;
    box.dataset.key = text;
    box.setAttribute('aria-label', text);
    const parts = lastFeedAt ? agoParts(lastFeedAt, now) : [];
    if (!lastFeedAt || !parts.length) {
      box.replaceChildren(el('span', { className: lastFeedAt ? 'num' : 'none' }, lastFeedAt ? '방금' : text));
      return;
    }
    box.replaceChildren(
      ...parts.flatMap(([n, unit]) => [el('span', { className: 'num' }, n), el('span', { className: 'unit' }, unit)]),
      el('span', { className: 'unit' }, '전'),
    );
  }

  /** '오늘 수유' 줄 오른쪽: 못 보낸 기록 수, 연결 상태 */
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

    setLine($('#clock'), '지금', formatClock(now));
    renderElapsed(lastFeedAt, now, mood === 'hungry');
    const diaper = state.summary?.last_diaper;
    setLine($('#lastDiaper'), '마지막 기저귀', diaper ? `${DIAPER_LABEL[diaper.type] || ''} · ${formatAgo(diaper.at, now, { hoursOnlyFrom: DIAPER_HOURS_ONLY })}` : '기록 없음');
    $('#albam').style.backgroundPosition = `${-frame * SPRITE_PX}px ${-MOOD_ROW[mood] * SPRITE_PX}px`;

    // 말풍선(알밤 위): 잠깐 띄운 말 > 로그인 문제 > 기분. 할 말이 없으면 숨김
    const bubble = state.bubble && Date.now() < state.bubble.until ? state.bubble : null;
    const words = bubble?.text ?? (state.authProblem || MOOD_TEXT[mood]);
    $('#bubbleText').textContent = words;
    $('#bubble').className = [bubble?.tone || (state.authProblem ? 'warn' : ''), words ? '' : 'empty'].join(' ').trim();
  }

  /** 캐릭터 두 칸 애니메이션 */
  function nextFrame() { frame ^= 1; tick(); }

  return { render, tick, nextFrame };
}
