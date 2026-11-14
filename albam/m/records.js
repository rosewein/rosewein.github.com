// 기록 쪽: 날짜를 넘기며 그날 기록을 본다. 줄을 누르면 고치기 창(m/entry.js).
//
//   [◀]   11월 14일 토요일 · 오늘   [▶]
//   수유 4회 780ml · 기저귀 5회(대변 1) · 잠 9시간 10분
//   11:25~11:37  수유 200ml · 12분 · 유산균            ›
//   09:10        기저귀 대변                            ›
//
// 기록은 care_day()(supabase/017)로 받는다. 최근 며칠만이 아니라 지난 기록(베이비타임에서 옮긴 것)도 날짜로 열린다.

import { KIND, DIAPER_LABEL, describeOther, detailText } from '../src/domain.js';
import { formatClock, formatDuration, formatLongDate, pad2 } from '../src/time.js';

const $ = (s) => document.querySelector(s);
const DAY_MS = 86400000;

/** Date → 'YYYY-MM-DD'(기기 날짜) */
export const dayKey = (d) => `${d.getFullYear()}-${pad2(d.getMonth() + 1)}-${pad2(d.getDate())}`;
/** 'YYYY-MM-DD' 에 n일 더하기 */
export function addDays(key, n) {
  const [y, m, d] = key.split('-').map(Number);
  return dayKey(new Date(y, m - 1, d + n));
}

/**
 * 한 줄 글(순수 함수). time 은 "11:25~11:37", 그날 전에 시작한 잠은 "전날 22:10~06:30".
 * @param {object} e  care_day 의 기록
 * @param {Date} from 그날의 시작
 * @returns {{time: string, kind: string, text: string}}
 */
export function describeRow(e, from) {
  const before = new Date(e.at) < from;
  const start = `${before ? '전날 ' : ''}${formatClock(e.at)}`;
  const time = e.ended_at ? `${start}~${formatClock(e.ended_at)}` : (e.kind === KIND.SLEEP || e.feeding) ? `${start}~` : start;
  const dur = e.ended_at ? formatDuration(new Date(e.ended_at) - new Date(e.at)) : '';
  const memo = detailText(e.detail || {});
  const join = (...parts) => parts.filter(Boolean).join(' · ');
  if (e.kind === KIND.FEED) return { time, kind: '수유', text: join(`${e.ml ?? '?'}ml`, e.feeding && !e.ended_at ? '먹는 중' : dur, memo) };
  if (e.kind === KIND.DIAPER) return { time, kind: '기저귀', text: join(DIAPER_LABEL[e.type] || '', memo) };
  if (e.kind === KIND.SLEEP) return { time, kind: '잠', text: join(e.ended_at ? dur : '자는 중', memo) };
  const all = describeOther(e.kind, { value: e.value, at: e.at, ended_at: e.ended_at, detail: e.detail || {} });
  const [label, ...rest] = all.split(' · ');
  // 숫자 종류는 "체온 37.4°C"처럼 이름 뒤에 값이 붙어 온다
  const sp = label.indexOf(' ');
  return sp > 0 ? { time, kind: label.slice(0, sp), text: join(label.slice(sp + 1), ...rest) } : { time, kind: label, text: rest.join(' · ') };
}

/**
 * 그날 합계 한 줄(순수 함수). 잠은 그날 안에 잔 시간만(전날 밤부터 이어진 잠은 그날 몫만, 자는 중이면 지금까지)
 * @returns {string}
 */
export function daySummary(events, from, to, now) {
  const feeds = events.filter((e) => e.kind === KIND.FEED);
  const diapers = events.filter((e) => e.kind === KIND.DIAPER);
  const poo = diapers.filter((e) => e.type === 'poo' || e.type === 'both').length;
  const until = Math.min(to.getTime(), now.getTime());
  const sleepMs = events.filter((e) => e.kind === KIND.SLEEP).reduce((sum, e) => {
    const a = Math.max(new Date(e.at).getTime(), from.getTime());
    const b = Math.min(e.ended_at ? new Date(e.ended_at).getTime() : until, until);
    return sum + Math.max(0, b - a);
  }, 0);
  const parts = [];
  if (feeds.length) parts.push(`수유 ${feeds.length}회 ${feeds.reduce((s, e) => s + (e.ml || 0), 0)}ml`);
  if (diapers.length) parts.push(`기저귀 ${diapers.length}회${poo ? `(대변 ${poo})` : ''}`);
  if (sleepMs >= 60000) parts.push(`잠 ${formatDuration(sleepMs)}`);
  return parts.join(' · ');
}

/** @param {{api: object, now: () => Date, openEdit: (e: object) => void}} ctx */
export function setupRecords(ctx) {
  let day = dayKey(ctx.now());
  let loaded = null;
  let seq = 0;
  const today = () => dayKey(ctx.now());

  function renderHead() {
    const [y, m, d] = day.split('-').map(Number);
    const { date, weekday } = formatLongDate(new Date(y, m - 1, d));
    const diff = Math.round((new Date(...today().split('-').map((v, i) => (i === 1 ? v - 1 : Number(v)))) - new Date(y, m - 1, d)) / DAY_MS);
    $('#dayTitle').textContent = `${date} ${weekday}`;
    $('#daySub').textContent = diff === 0 ? '오늘' : diff === 1 ? '어제' : `${diff}일 전`;
    $('#dayNext').disabled = day >= today();
    $('#dayPick').value = day;
    $('#dayPick').max = today();
  }

  function renderList() {
    const list = $('#dayList');
    if (!loaded) return;
    const from = new Date(loaded.from);
    const events = [...loaded.events].reverse();   // 최근 것이 위
    $('#daySummary').textContent = daySummary(loaded.events, from, new Date(loaded.to), ctx.now());
    $('#dayMsg').textContent = events.length ? '' : '이 날은 기록이 없어요';
    list.replaceChildren(...events.map((e) => {
      const r = describeRow(e, from);
      const b = document.createElement('button');
      b.className = 'rec';
      const t = document.createElement('span'); t.className = 'time'; t.textContent = r.time;
      const body = document.createElement('span'); body.className = 'body';
      const k = document.createElement('span'); k.className = 'val'; k.textContent = r.kind;
      body.append(k, r.text ? ` ${r.text}` : '');
      const go = document.createElement('span'); go.className = 'go'; go.textContent = '›'; go.setAttribute('aria-hidden', 'true');
      b.append(t, body, go);
      b.addEventListener('click', () => ctx.openEdit(e));
      return b;
    }));
  }

  async function load() {
    renderHead();
    const mine = ++seq;
    try {
      const got = await ctx.api.getDay(day);
      if (mine !== seq) return;   // 그사이 다른 날로 넘김
      loaded = got;
      renderList();
    } catch (e) {
      if (mine !== seq) return;
      loaded = null;
      $('#dayList').replaceChildren();
      $('#daySummary').textContent = '';
      $('#dayMsg').textContent = '기록을 못 받았어요. 연결을 확인해 주세요';
    }
  }

  function go(next) {
    if (next > today()) return;
    day = next;
    $('#dayList').replaceChildren();
    $('#daySummary').textContent = '';
    $('#dayMsg').textContent = '';
    load();
  }
  $('#dayPrev').addEventListener('click', () => go(addDays(day, -1)));
  $('#dayNext').addEventListener('click', () => go(addDays(day, 1)));
  $('#dayPick').addEventListener('change', () => { if ($('#dayPick').value) go($('#dayPick').value); });
  $('#dayTitleBtn').addEventListener('click', () => { try { $('#dayPick').showPicker(); } catch (e) { $('#dayPick').focus(); } });

  return {
    /** 쪽을 열 때: 오늘로 */
    show() { day = today(); load(); },
    /** 고치거나 지운 뒤, 요약을 다시 받았을 때: 보던 날을 다시 */
    reload: load,
  };
}
