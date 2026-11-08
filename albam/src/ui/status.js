// 대시보드: 알밤 + 말풍선(위층), 수유·기저귀·잠 세 칸(아래층), 오른쪽 위 구석(나이·지금).
// render(): 요약이 바뀌었을 때 / tick(): 0.6초마다(시계, 지난 시간, 캐릭터). 글이 그대로면 DOM 을 건드리지 않는다.
//
//   말풍선  배고파요…            ← 상태 문구(가장 급한 항목, chooseFocus)
//           12시간 35분          ← 그 항목의 지난 시간(가장 큰 글씨, 급하면 빨강)
//           마지막 수유 01:25    ← 무엇의 시간인지
//   칸      수유 / 2시간 35분 / 11:25 · 200ml    기저귀 / 1시간 10분 / 12:50 · 소변    잠 · 깬 지 / 3시간 20분 / 09:00~10:40

import { $, el } from './dom.js';
import { feedingNow, setRecordTypes, sleepingNow } from '../domain.js';
import { agoParts, formatClock } from '../time.js';

/** 스프라이트 시트(sprites/albam.png)의 줄 순서. sprites.json 과 같다 */
const MOOD_ROW = { normal: 0, hungry: 1, sleep: 2, happy: 3 };
/** 스프라이트 한 칸(32px)을 3배로 그린다 */
const SPRITE_PX = 96;

/**
 * 나이 줄 조각(순수 함수): [[글, 값인가]]. 교정 나이가 없으면(예정일 전) 실제 나이만
 * @param {{day: number, months: number, days: number, corrected_months?: number|null, corrected_days?: number|null}} a
 */
export function ageParts(a) {
  const parts = [[`D+${a.day}`, true], [' · ', false], [`${a.months}개월 ${a.days}일`, true]];
  if (a.corrected_months != null) parts.push([' · 교정 ', false], [`${a.corrected_months}개월 ${a.corrected_days}일`, true]);
  return parts;
}

/** 글이 바뀌었을 때만 고친다 */
function setText(node, text) {
  if (node && node.textContent !== text) node.textContent = text;
}

/** 급한 항목의 말풍선 문구 */
export const FOCUS_TEXT = Object.freeze({ feed: '배고파요…', diaper: '기저귀 봐 주세요…', sleep: '졸려요…' });

/**
 * 말풍선과 표정이 따를 항목 고르기(순수 함수).
 * 기쁨(방금 저장) > 먹이는 중 > 자는 중(잠 기록이 열려 있음) > 잠(밤, 화면 꺼진 상태) > 급한 항목 > 밤 > 평온
 * 급한 항목: 지난 시간 ÷ 기준 시간(cfg.hungryMinutes·diaperMinutes·awakeMinutes)이 가장 크고 1 이상인 것 하나
 * @param {{happy?: boolean, feeding?: boolean, sleeping?: boolean, night?: boolean, nightAwake?: boolean,
 *          minutes: {feed?: number|null, diaper?: number|null, awake?: number|null},
 *          limits: {feed: number, diaper: number, awake: number}}} p
 * @returns {{mood: 'normal'|'hungry'|'sleep'|'happy', focus: 'feed'|'diaper'|'sleep', urgent: boolean, words: string}}
 */
export function chooseFocus({ happy = false, feeding = false, sleeping = false, night = false, nightAwake = false, minutes, limits }) {
  if (happy) return { mood: 'happy', focus: feeding ? 'feed' : sleeping ? 'sleep' : 'feed', urgent: false, words: '고마워요!' };
  if (feeding) return { mood: 'normal', focus: 'feed', urgent: false, words: '냠냠' };
  if (sleeping) return { mood: 'sleep', focus: 'sleep', urgent: false, words: '쿨쿨' };
  if (night && !nightAwake) return { mood: 'sleep', focus: 'feed', urgent: false, words: '쿨쿨' };
  let worst = null;
  for (const [key, limit] of [['feed', limits.feed], ['diaper', limits.diaper], ['sleep', limits.awake]]) {
    const m = key === 'sleep' ? minutes.awake : minutes[key];
    if (m == null || !limit) continue;
    const ratio = m / limit;
    if (ratio >= 1 && (!worst || ratio > worst.ratio)) worst = { key, ratio };
  }
  if (worst) return { mood: 'hungry', focus: worst.key, urgent: true, words: FOCUS_TEXT[worst.key] };
  if (night) return { mood: 'sleep', focus: 'feed', urgent: false, words: '쉿, 밤이에요' };
  return { mood: 'normal', focus: 'feed', urgent: false, words: '기분 좋아요' };
}

/**
 * 예전 이름(수유만 보던 때). 시험과 다른 곳에서 쓰던 그대로 기분만 돌려준다
 * @param {{happy: boolean, sleeping?: boolean, night: boolean, nightAwake: boolean, minutesSinceFeed: number|null, hungryMinutes: number}} p
 */
export function chooseMood({ happy, sleeping = false, night, nightAwake, minutesSinceFeed, hungryMinutes }) {
  return chooseFocus({ happy, sleeping, night, nightAwake, minutes: { feed: minutesSinceFeed }, limits: { feed: hungryMinutes, diaper: 0, awake: 0 } }).mood;
}

/** 기저귀 종류 짧게(칸이 좁아서) */
const DIAPER_SHORT = { pee: '소변', poo: '대변', both: '소+대' };

/**
 * 기저귀 칸 세부(순수 함수): "12:50 · 소변", 소변 뒤에 대변이 따로 있었으면 "12:50 소변 · 대 09:10"
 * @param {{at: string, type: string} | null | undefined} diaper
 * @param {{at: string} | null | undefined} poo  마지막 대변(009)
 */
export function diaperDetail(diaper, poo) {
  if (!diaper) return '기록 없음';
  if (diaper.type === 'pee' && poo) return `${formatClock(diaper.at)} 소변 · 대 ${formatClock(poo.at)}`;
  return `${formatClock(diaper.at)} · ${DIAPER_SHORT[diaper.type] || ''}`;
}

/** @param {import('../main.js').AppContext} ctx */
export function createStatusView(ctx) {
  const { state, cfg } = ctx;
  let frame = 0;

  function render() {
    const s = state.summary;
    setRecordTypes(s?.record_types);
    // 두 번째 쪽(타임라인) 머리줄: 오늘 합계, 미리 보기
    setText($('#today'), s ? `오늘 ${s.today?.feed_count ?? 0}회 · ${s.today?.feed_ml ?? 0}ml` : '');
    setText($('#demoNote'), ctx.api.demo ? '미리 보기' : '');
    renderAge(s?.age);
    renderConnection();
    tick();
  }

  /** 지난 시간 글 조각: 숫자는 크게, 단위는 작게. "방금", 기록 없으면 "—" */
  function renderAgo(box, from, now, { suffix = '' } = {}) {
    const parts = from ? agoParts(from, now) : [];
    const text = !from ? '—' : parts.length ? `${parts.map(([n, u]) => n + u).join(' ')}${suffix}` : '방금';
    if (box.dataset.key === text) return;
    box.dataset.key = text;
    box.setAttribute('aria-label', text);
    if (!from || !parts.length) { box.replaceChildren(el('span', { className: from ? 'num' : 'none' }, text)); return; }
    // "째"는 마지막 단위에 붙인다("20분째")
    box.replaceChildren(...parts.flatMap(([n, unit], i) => [el('span', { className: 'num' }, n),
      el('span', { className: 'unit' }, i === parts.length - 1 ? unit + suffix : unit)]));
  }

  /** 오른쪽 위 구석: D+142 (지금 시각은 tick) / 교정 3개월 28일(예정일 전이면 실제 개월) */
  function renderAge(age) {
    setText($('#age'), age ? `D+${age.day}` : '');
    setText($('#ageSub'), !age ? '' : age.corrected_months != null ? `교정 ${age.corrected_months}개월 ${age.corrected_days}일` : `${age.months}개월 ${age.days}일`);
  }

  /** 구석의 못 보낸 기록 수, 연결 끊김. 문제 없으면 비운다 */
  function renderConnection() {
    const net = $('#net');
    const [text, cls] = state.pending ? [`대기 ${state.pending}건`, 'acc'] : state.stale ? ['연결 안 됨', 'warn'] : ['', ''];
    setText(net, text);
    net.className = cls;
  }

  /** 칸 하나: 이름 / 지난 시간 / 시각·세부 */
  function renderCard(id, { label, from, suffix = '', detail, urgent }) {
    const card = $(id);
    setText(card.querySelector('.lbl'), label);
    renderAgo(card.querySelector('.big'), from, ctx.now(), { suffix });
    setText(card.querySelector('.sub'), detail);
    card.classList.toggle('urgent', !!urgent);
  }

  function tick() {
    const now = ctx.now();
    const s = state.summary;
    const feed = s?.last_feed;
    const diaper = s?.last_diaper;
    const sleep = s?.last_sleep;
    const sleeping = sleepingNow(s);
    const feeding = feedingNow(s);
    const mins = (at) => (at ? (now - new Date(at)) / 60000 : null);
    const pick = chooseFocus({
      happy: Date.now() < state.happyUntil,
      feeding: !!feeding,
      sleeping: !!sleeping,
      night: ctx.isNightTime(),
      nightAwake: ctx.isNightAwake(),
      minutes: { feed: mins(feed?.at), diaper: mins(diaper?.at), awake: sleep?.ended_at && !sleeping ? mins(sleep.ended_at) : null },
      limits: { feed: cfg.hungryMinutes, diaper: cfg.diaperMinutes, awake: cfg.awakeMinutes },
    });

    setText($('#clock'), formatClock(now));
    $('#albam').style.backgroundPosition = `${-frame * SPRITE_PX}px ${-MOOD_ROW[pick.mood] * SPRITE_PX}px`;

    // 아래층 세 칸(같은 형식)
    const urgent = pick.urgent ? pick.focus : null;
    renderCard('#cardFeed', feeding
      ? { label: '수유 · 먹는 중', from: feeding.at, suffix: '째', detail: `${formatClock(feeding.at)}~${feed?.ml != null ? ` · ${feed.ml}ml` : ''}` }
      : { label: '수유', from: feed?.at, detail: feed ? `${formatClock(feed.at)}${feed.ml != null ? ` · ${feed.ml}ml` : ''}` : '기록 없음', urgent: urgent === 'feed' });
    renderCard('#cardDiaper', { label: '기저귀', from: diaper?.at, detail: diaperDetail(diaper, s?.last_poo), urgent: urgent === 'diaper' });
    renderCard('#cardSleep', sleeping
      ? { label: '잠 · 자는 중', from: sleeping.at, suffix: '째', detail: `${formatClock(sleeping.at)}~` }
      : sleep?.ended_at
        ? { label: '잠 · 깬 지', from: sleep.ended_at, detail: `${formatClock(sleep.at)}~${formatClock(sleep.ended_at)}`, urgent: urgent === 'sleep' }
        : { label: '잠', from: null, detail: '기록 없음' });

    // 말풍선: 고른 항목 하나의 문구 / 지난 시간 / 이름표
    const bubble = { feed: feeding ? [feeding.at, '째', `먹이기 시작 ${formatClock(feeding.at)}`] : [feed?.at, '', feed ? `마지막 수유 ${formatClock(feed.at)}` : '수유 기록 없음'],
      diaper: [diaper?.at, '', diaper ? `마지막 기저귀 ${formatClock(diaper.at)}` : '기저귀 기록 없음'],
      sleep: sleeping ? [sleeping.at, '째', `잠든 시각 ${formatClock(sleeping.at)}`] : [sleep?.ended_at, '', sleep?.ended_at ? `깬 시각 ${formatClock(sleep.ended_at)}` : '잠 기록 없음'] }[pick.focus];
    setText($('#bubbleText'), pick.words);
    renderAgo($('#elapsed'), bubble[0], now, { suffix: bubble[1] });
    setText($('#bubbleLabel'), bubble[2]);
    $('#bubble').classList.toggle('urgent', pick.urgent);
    $('#bubble').dataset.focus = pick.focus;

    // [잠] 버튼: 자는 중이면 "깼어요"
    const sleepBtn = $('#sleepBtn');
    if (sleepBtn.classList.contains('on') !== !!sleeping) {
      sleepBtn.classList.toggle('on', !!sleeping);
      sleepBtn.setAttribute('aria-label', sleeping ? '깼어요' : '잠들었어요');
      $('#sleepBtnText').textContent = sleeping ? '깼어요' : '잠';
    }
    // [수유] 버튼: 먹이는 중이면 "다 먹음"
    const feedBtn = $('#feedBtn');
    if (feedBtn.classList.contains('feeding') !== !!feeding) {
      feedBtn.classList.toggle('feeding', !!feeding);
      $('#feedBtnText').textContent = feeding ? '다 먹음' : '수유';
      feedBtn.setAttribute('aria-label', feeding ? '다 먹음' : '수유');
    }
  }

  /** 캐릭터 두 칸 애니메이션 */
  function nextFrame() { frame ^= 1; tick(); }

  return { render, tick, nextFrame };
}
