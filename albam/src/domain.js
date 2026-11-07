// 기록(이벤트)과 요약의 모양, 그리고 화면에 보여 줄 이름.
// 종류를 늘릴 때(예: 이유식) 먼저 고칠 곳이 이 파일이다. docs/TECHNICAL.md '새 기록 종류 추가' 참고.

import { formatClock, formatDuration } from './time.js';

/**
 * 기록 하나. Supabase public.care_events 의 한 줄과 같다.
 * @typedef {Object} CareEvent
 * @property {string} [id]            화면이 만드는 uuid. 다시 보내도 한 번만 저장되게 하는 열쇠
 * @property {EventKind} kind
 * @property {Date|string} occurred_at 실제 일어난 시각. 정렬·계산 기준
 * @property {Date|string} [ended_at]  수면처럼 끝이 있는 기록
 * @property {number} [amount_ml]      수유량
 * @property {{type?: DiaperType} & Object<string, any>} [detail]
 * @property {EventSource} [source]
 * @property {string} [voice_text]     음성으로 넣었을 때 인식된 원문
 */

/** @typedef {'feed'|'diaper'|'sleep'|'chore_done'} EventKind */
/** @typedef {'pee'|'poo'|'both'} DiaperType */
/** @typedef {'living_room_touch'|'living_room_voice'|'phone'|'import'} EventSource */

/**
 * care_summary() 가 돌려주는 요약. 화면은 이것만 읽는다.
 * @typedef {Object} Summary
 * @property {string} server_time
 * @property {string} day_start                     오늘이 시작된 시각(설정한 '하루 끊는 시각' 기준)
 * @property {{id: string, at: string, ml: number|null, ended_at?: string|null, feeding?: boolean} | null} last_feed  ended_at: 다 먹은 시각, feeding: 먹이는 중(007)
 * @property {{feed_count: number, feed_ml: number}} today
 * @property {{id: string, at: string, type: DiaperType} | null} last_diaper
 * @property {{id: string, at: string, ended_at: string|null} | null} last_sleep  ended_at 이 null 이면 자는 중
 * @property {{day: number, months: number, days: number, corrected_day: number|null, corrected_months: number|null, corrected_days: number|null} | null} [age]  오늘 나이(006)
 * @property {number[]} feed_amounts                 수유량 빠른 선택(ml, 작은 것부터). '수유량 설정'에서 바꾼다
 * @property {RecentItem[]} recent                  최근 기록, 실제 시각 역순
 * @property {Array} due_chores                     2단계
 * @property {{day_start_hour: number, dup_window_minutes: number}} settings
 */

/**
 * @typedef {Object} RecentItem
 * @property {string} id
 * @property {EventKind} kind
 * @property {string} at
 * @property {string|null} [ended_at]
 * @property {number|null} [ml]
 * @property {Object} [detail]
 * @property {boolean} [pending]   아직 서버에 못 보낸 기록
 */

export const KIND = Object.freeze({ FEED: 'feed', DIAPER: 'diaper', SLEEP: 'sleep', CHORE_DONE: 'chore_done' });

export const SOURCE = Object.freeze({
  TOUCH: 'living_room_touch',
  VOICE: 'living_room_voice',
  PHONE: 'phone',
  IMPORT: 'import',
});

/** 기저귀 종류 → 화면 이름. 순서는 버튼 순서 */
export const DIAPER_LABEL = Object.freeze({ pee: '소변', poo: '대변', both: '소변+대변' });

/**
 * 지금 먹이는 중인 수유([먹이기 시작]을 누르고 아직 [다 먹음]을 안 누름). 없으면 null
 * @param {Summary|null} summary
 * @returns {{id: string, at: string, ml: number|null} | null}
 */
export function feedingNow(summary) {
  const f = summary?.last_feed;
  return f && f.feeding && !f.ended_at ? f : null;
}

/**
 * 지금 자는 중인 잠(끝이 아직 없는 마지막 잠). 없으면 null
 * @param {Summary|null} summary
 * @returns {{id: string, at: string} | null}
 */
export function sleepingNow(summary) {
  const s = summary?.last_sleep;
  return s && !s.ended_at ? s : null;
}

/** 버튼에 쓰는 짧은 이름 */
export const DIAPER_BUTTON = Object.freeze({ pee: '소변', poo: '대변', both: '둘 다' });

/** 이만큼 지난 기록이면 이름 뒤에 시각을 붙인다 */
const SHOW_TIME_AFTER_MS = 2 * 60000;

/**
 * 기록을 한 줄 이름으로. 예: "수유 160ml", "기저귀 대변 · 13:20", "잠 13:10~14:40"
 * @param {CareEvent} ev
 * @param {Date} now
 */
export function describeEvent(ev, now = new Date()) {
  if (ev.kind === KIND.SLEEP) return ev.ended_at ? `잠 ${formatClock(ev.occurred_at)}~${formatClock(ev.ended_at)}` : `잠 시작 ${formatClock(ev.occurred_at)}`;
  let text = ev.kind;
  if (ev.kind === KIND.FEED) text = `수유 ${ev.amount_ml ?? ''}ml${ev.ended_at ? ` · ${formatDuration(new Date(ev.ended_at) - new Date(ev.occurred_at))}` : ''}`;
  if (ev.kind === KIND.DIAPER) text = `기저귀 ${DIAPER_LABEL[ev.detail?.type] || ''}`;
  const at = new Date(ev.occurred_at || now);
  if (now - at > SHOW_TIME_AFTER_MS) text += ` · ${formatClock(at)}`;
  return text;
}

/**
 * 요약의 최근 기록 한 줄 이름(시각 제외). 예: "수유 160ml", "잠 ~14:40"
 * @param {RecentItem} r
 */
export function describeRecent(r) {
  if (r.kind === KIND.FEED) return `수유 ${r.ml ?? ''}ml`;
  if (r.kind === KIND.DIAPER) return `기저귀 ${DIAPER_LABEL[r.detail?.type] || ''}`;
  if (r.kind === KIND.SLEEP) return r.ended_at ? `잠 ~${formatClock(r.ended_at)}` : '잠 (자는 중)';
  return r.kind;
}
