// 입력 쪽: 수유·기저귀·잠 카드(상태 + 바로 저장 버튼), 더 넣기 버튼, 다가오는 일정.
//
//   수유 · 먹은 지          11:25 · 200ml
//   2시간 35분
//   [ 수유 200ml ] [양 바꾸기]        ← 누르면 먹이기 시작, 먹이는 중이면 [다 먹음]
//
// 수유량은 마지막으로 먹인 양에서 시작한다. [양 바꾸기]는 이번 한 번만 다른 양으로.
//   같이 [유산균] [비타민D] [+]         ← 수유에 붙이는 문구. 먹이기 전에 켜 두면 다음 수유에, 먹이는 중이면 그 수유에 바로 붙는다
// 지난 시간이 기준(config.js hungryMinutes·diaperMinutes·awakeMinutes)을 넘은 카드는 빨간 테두리.

import { KIND, SOURCE, feedingNow, sleepingNow, moreTypes, setRecordTypes } from '../src/domain.js';
import { agoParts, formatClockOn, formatLongDate } from '../src/time.js';
import { stepMachine, machineLabel } from '../src/formula.js';
import { ageParts, diaperDetail, hungryLimit } from '../src/ui/status.js';
import { memoHas, toggleMemo } from './phrases.js';

const $ = (s) => document.querySelector(s);
const setText = (sel, text) => { const n = $(sel); if (n.textContent !== text) n.textContent = text; };
/** "2시간 35분", 1분이 안 되면 "방금" */
const ago = (from, now) => { const p = agoParts(from, now); return p.length ? p.map(([n, u]) => n + u).join(' ') : '방금'; };
/** 하는 중인 일: "12분째", 막 시작했으면 "방금 시작" */
const going = (from, now) => (agoParts(from, now).length ? `${ago(from, now)}째` : '방금 시작');
const minutesSince = (from, now) => (from ? (now - new Date(from)) / 60000 : null);
const MIN_ML = 10;
const MAX_ML = 500;

/**
 * @param {{cfg: object, state: {summary: object|null}, now: () => Date, save: Function, finishFeed: Function, wake: Function,
 *          openEntry: (kind: string) => void, upcoming: {all: (now: Date) => object[]},
 *          phrases: {renderChips: Function}, attachMemo: (id: string, memo: string) => Promise<void>}} ctx
 */
export function setupHome(ctx) {
  const { cfg, state } = ctx;
  /** 이번에 넣을 수유량. null 이면 마지막으로 먹인 양 */
  let chosen = null;
  /** 다음 수유에 붙일 문구(먹이기 전에 켜 둔 것) */
  let pre = '';
  /** 먹이는 중인 수유의 지금 메모(요약의 최근 기록에서) */
  const memoOf = (id) => state.summary?.recent?.find((r) => r.id === id)?.detail?.memo || '';
  const amount = () => chosen ?? state.summary?.last_feed?.ml ?? state.summary?.feed_amounts?.[0] ?? cfg.defaultAmounts[0] ?? 200;

  function renderFeed(s, now) {
    const last = s?.last_feed;
    const feeding = feedingNow(s);
    setText('#feedLabel', feeding ? '수유 · 먹는 중' : '수유 · 먹은 지');
    setText('#feedAgo', !last ? '기록 없음' : feeding ? going(last.at, now) : ago(last.at, now));
    setText('#feedDetail', last ? `${formatClockOn(last.at, now)}${feeding ? '~' : ''} · ${last.ml ?? '?'}ml` : '');
    setText('#feedBtn', feeding ? '다 먹음' : `수유 ${amount()}ml`);
    $('#feedBtn').classList.toggle('on', !!feeding);
    $('#feedAmountBtn').hidden = !!feeding;
    if (feeding) $('#feedSteps').hidden = true;
    setText('#feedAmount', `${amount()}ml`);
    setText('#feedMachine', machineLabel(amount(), cfg.formula, cfg.machine));
    const limit = hungryLimit(cfg.hungryMinutes, s, last?.at, cfg.feedPeriods);
    $('#feedCard').classList.toggle('urgent', !feeding && !!last && minutesSince(last.at, now) >= limit.minutes);
    const memo = feeding ? memoOf(feeding.id) : pre;
    const key = JSON.stringify([feeding?.id ?? null, memo, ctx.phrases.of(KIND.FEED)]);
    if (key !== chipsKey) {
      chipsKey = key;
      ctx.phrases.renderChips($('#feedChips'), KIND.FEED, {
        lead: '같이',
        isOn: (text) => memoHas(memo, text),
        onToggle: async (text) => {
          const now2 = feedingNow(state.summary);
          if (now2) await ctx.attachMemo(now2.id, toggleMemo(memoOf(now2.id), text));
          else { pre = toggleMemo(pre, text); render(); }
        },
      });
    }
  }
  let chipsKey = '';

  function renderDiaper(s, now) {
    const d = s?.last_diaper;
    setText('#diaperAgo', d ? ago(d.at, now) : '기록 없음');
    setText('#diaperDetail', d ? diaperDetail(d, s?.last_poo, false, now) : '');
    $('#diaperCard').classList.toggle('urgent', !!d && minutesSince(d.at, now) >= cfg.diaperMinutes);
  }

  function renderSleep(s, now) {
    const sl = s?.last_sleep;
    const sleeping = sleepingNow(s);
    setText('#sleepLabel', sleeping ? '잠 · 자는 중' : '잠 · 깬 지');
    setText('#sleepAgo', !sl ? '기록 없음' : sleeping ? going(sl.at, now) : ago(sl.ended_at, now));
    setText('#sleepDetail', !sl ? '' : sleeping ? `${formatClockOn(sl.at, now)}~` : `${formatClockOn(sl.at, now)}~${formatClockOn(sl.ended_at, now)}`);
    setText('#sleepBtn', sleeping ? '깼어요' : '잠들었어요');
    $('#sleepBtn').classList.toggle('on', !!sleeping);
    $('#sleepCard').classList.toggle('urgent', !sleeping && !!sl && minutesSince(sl.ended_at, now) >= cfg.awakeMinutes);
  }

  let moreKey = '';
  function renderMore(s) {
    setRecordTypes(s?.record_types);
    const types = moreTypes();
    const key = types.map((t) => `${t.key}:${t.label}`).join('|');
    if (key === moreKey) return;
    moreKey = key;
    $('#moreGrid').replaceChildren(...types.map((t) => {
      const b = document.createElement('button');
      b.className = 'btn';
      b.textContent = t.label;
      b.addEventListener('click', () => ctx.openEntry(t.key));
      return b;
    }));
  }

  let upcomingKey = '';
  function renderUpcoming(now) {
    const list = ctx.upcoming.all(now);
    const key = JSON.stringify(list);
    if (key === upcomingKey) return;
    upcomingKey = key;
    $('#upcomingSec').hidden = !list.length;
    $('#upcomingList').replaceChildren(...list.map((a) => {
      const row = document.createElement('div');
      row.className = 'appt';
      const what = document.createElement('span');
      what.textContent = `${a.date} ${a.title}${a.all.length ? ` · ${a.all.join(', ')}` : ''}`;
      const left = document.createElement('span');
      left.className = 'left';
      left.textContent = a.left;
      row.append(what, left);
      return row;
    }));
  }

  function render() {
    const now = ctx.now();
    const s = state.summary;
    const { date, weekday } = formatLongDate(now);
    setText('#today', `${date} ${weekday}`);
    setText('#age', s?.age ? ageParts(s.age).map(([t]) => t).join('') : '');
    renderFeed(s, now);
    renderDiaper(s, now);
    renderSleep(s, now);
    renderMore(s);
    renderUpcoming(now);
  }

  // ── 누르기 ──
  $('#feedBtn').addEventListener('click', () => {
    const feeding = feedingNow(state.summary);
    if (feeding) { ctx.finishFeed(feeding); return; }
    const ml = amount();
    chosen = null;
    $('#feedSteps').hidden = true;
    const detail = pre ? { feeding: true, memo: pre } : { feeding: true };
    pre = '';
    ctx.save({ kind: KIND.FEED, amount_ml: ml, occurred_at: ctx.now(), detail, source: SOURCE.PHONE });
  });
  $('#feedAmountBtn').addEventListener('click', () => {
    const steps = $('#feedSteps');
    steps.hidden = !steps.hidden;
    if (steps.hidden) chosen = null;
    render();
  });
  for (const b of document.querySelectorAll('#feedSteps [data-step]')) {
    b.addEventListener('click', () => {
      const step = b.dataset.step;
      const next = step.endsWith('machine') ? stepMachine(amount(), step.startsWith('-') ? -1 : 1, cfg.formula, cfg.machine) : amount() + Number(step);
      chosen = Math.min(MAX_ML, Math.max(MIN_ML, next));
      render();
    });
  }
  for (const b of document.querySelectorAll('[data-diaper]')) {
    b.addEventListener('click', () => ctx.save({ kind: KIND.DIAPER, occurred_at: ctx.now(), detail: { type: b.dataset.diaper }, source: SOURCE.PHONE }));
  }
  $('#sleepBtn').addEventListener('click', () => {
    const sleeping = sleepingNow(state.summary);
    if (sleeping) ctx.wake(sleeping);
    else ctx.save({ kind: KIND.SLEEP, occurred_at: ctx.now(), detail: {}, source: SOURCE.PHONE });
  });

  return { render };
}
