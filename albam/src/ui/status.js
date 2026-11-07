// 오른쪽 위 상태 칸과 왼쪽 캐릭터.
// render(): 요약이 바뀌었을 때 / tick(): 0.6초마다(시계, 지난 시간, 캐릭터). 글이 그대로면 DOM 을 건드리지 않는다.
//
// 시각은 모두 무엇의 시각인지 글로 붙인다:
//   마지막 수유 11:25 · 160ml        지금 14:00
//   2시간 35분 전                     ← 마지막 수유 뒤 지난 시간(숫자 크게)
//   오늘 수유 3회 · 420ml             대기 n건
//   마지막 기저귀 소변 · 1시간 10분 전
//   D+143 · 4개월 21일 · 교정 3개월 29일

import { $, el } from './dom.js';
import { DIAPER_LABEL, feedingNow, setRecordTypes, sleepingNow } from '../domain.js';
import { agoParts, formatAgo, formatClock, formatDuration } from '../time.js';

/** 스프라이트 시트(sprites/albam.png)의 줄 순서. sprites.json 과 같다 */
const MOOD_ROW = { normal: 0, hungry: 1, sleep: 2, happy: 3 };
const MOOD_TEXT = { normal: '', hungry: '배고파요…', sleep: '쿨쿨', happy: '고마워요!' };
/** 스프라이트 한 칸(32px)을 3배로 그린다 */
const SPRITE_PX = 96;
/** 기저귀 줄은 좁아서 이 시간 넘으면 "11시간 전"처럼 분을 뺀다 */
const DIAPER_HOURS_ONLY = 10;

/**
 * 나이 줄 조각(순수 함수): [[글, 값인가]]. 교정 나이가 없으면(예정일 전) 실제 나이만
 * @param {{day: number, months: number, days: number, corrected_months?: number|null, corrected_days?: number|null}} a
 */
export function ageParts(a) {
  const parts = [[`D+${a.day}`, true], [' · ', false], [`${a.months}개월 ${a.days}일`, true]];
  if (a.corrected_months != null) parts.push([' · 교정 ', false], [`${a.corrected_months}개월 ${a.corrected_days}일`, true]);
  return parts;
}

/** 흐린 이름표 + 굵은 값 한 줄. 글이 같으면 다시 그리지 않는다 */
function setLine(node, label, value) {
  const key = `${label}|${value}`;
  if (node.dataset.key === key) return;
  node.dataset.key = key;
  node.replaceChildren(el('span', { className: 'lbl' }, label), el('span', { className: 'val' }, value));
}

/**
 * 캐릭터 기분 고르기(순수 함수).
 * 기쁨(방금 저장) > 자는 중(잠 기록이 열려 있음) > 잠(밤, 화면 꺼진 상태) > 배고픔(수유 후 오래) > 밤이면 잠 > 평소
 * @param {{happy: boolean, sleeping?: boolean, night: boolean, nightAwake: boolean, minutesSinceFeed: number|null, hungryMinutes: number}} p
 * @returns {'normal'|'hungry'|'sleep'|'happy'}
 */
export function chooseMood({ happy, sleeping = false, night, nightAwake, minutesSinceFeed, hungryMinutes }) {
  if (happy) return 'happy';
  if (sleeping) return 'sleep';
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
    setRecordTypes(s?.record_types);
    const feed = s?.last_feed;
    setLine($('#lastFeed'), '마지막 수유', feed ? `${formatClock(feed.at)}${feed.ml != null ? ` · ${feed.ml}ml` : ''}` : '기록 없음');
    setLine($('#today'), '오늘 수유', s ? `${s.today?.feed_count ?? 0}회 · ${s.today?.feed_ml ?? 0}ml` : '-');
    renderAge(s?.age);
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

  /** 나이 줄: D+143 · 4개월 21일 · 교정 3개월 29일 (베이비타임과 같은 규칙, 서버 care_age) */
  function renderAge(age) {
    const box = $('#age');
    const key = JSON.stringify(age ?? null);
    if (box.dataset.key === key) return;
    box.dataset.key = key;
    box.replaceChildren(...(age ? ageParts(age).map(([text, val]) => el('span', { className: val ? 'val' : '' }, text)) : []));
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
    const sleeping = sleepingNow(state.summary);
    const mood = chooseMood({
      happy: Date.now() < state.happyUntil,
      sleeping: !!sleeping,
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

    // [잠] 버튼: 자는 중이면 "깼어요"
    const sleepBtn = $('#sleepBtn');
    if (sleepBtn.classList.contains('on') !== !!sleeping) {
      sleepBtn.classList.toggle('on', !!sleeping);
      sleepBtn.setAttribute('aria-label', sleeping ? '깼어요' : '잠들었어요');
      $('#sleepBtnText').textContent = sleeping ? '깼어요' : '';
    }

    // 말풍선(알밤 위): 알밤이 하는 말만. 할 말이 없으면(평소) 숨김. 자는 중이면 얼마나 잤는지
    // [수유] 버튼: 먹이는 중이면 "다 먹음"
    const feeding = feedingNow(state.summary);
    const feedBtn = $('#feedBtn');
    if (feedBtn.classList.contains('feeding') !== !!feeding) {
      feedBtn.classList.toggle('feeding', !!feeding);
      $('#feedBtnText').textContent = feeding ? '다 먹음' : '수유';
      feedBtn.setAttribute('aria-label', feeding ? '다 먹음' : '수유');
    }
    const words = feeding && mood !== 'happy' ? `냠냠 ${formatDuration(now - new Date(feeding.at))}`
      : sleeping && mood === 'sleep' ? `쿨쿨 ${formatDuration(now - new Date(sleeping.at))}` : MOOD_TEXT[mood];
    $('#bubbleText').textContent = words;
    $('#bubble').className = words ? '' : 'empty';
  }

  /** 캐릭터 두 칸 애니메이션 */
  function nextFrame() { frame ^= 1; tick(); }

  return { render, tick, nextFrame };
}
