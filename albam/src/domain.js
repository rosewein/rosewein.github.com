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

/**
 * 기록 종류(supabase/008 의 care_record_types). 요약의 record_types 로 받고, 받기 전에는 아래 기본값을 쓴다.
 * @typedef {{key: string, label: string, shape: 'instant'|'range'|'number'|'text', unit?: string|null,
 *            step?: number|null, min?: number|null, max?: number|null, default?: number|null, in_more?: boolean}} RecordType
 */
/** @type {RecordType[]} */
export const DEFAULT_RECORD_TYPES = [
  { key: 'feed', label: '수유', shape: 'instant', unit: 'ml', in_more: false },
  { key: 'diaper', label: '기저귀', shape: 'instant', in_more: false },
  { key: 'sleep', label: '잠', shape: 'range', in_more: false },
  { key: 'bath', label: '목욕', shape: 'range', in_more: true },
  { key: 'temperature', label: '체온', shape: 'number', unit: '°C', step: 0.1, min: 34, max: 42, default: 36.8, in_more: true },
  { key: 'medication', label: '투약', shape: 'instant', in_more: true },
  { key: 'weight', label: '체중', shape: 'number', unit: 'kg', step: 0.01, min: 1, max: 30, default: 7, in_more: true },
  { key: 'height', label: '키', shape: 'number', unit: 'cm', step: 0.1, min: 30, max: 120, default: 65, in_more: true },
  { key: 'memo', label: '메모', shape: 'text', in_more: true },
  { key: 'tummy_time', label: '터미타임', shape: 'range', in_more: true },
  { key: 'play', label: '놀이', shape: 'range', in_more: true },
  { key: 'hospital', label: '병원', shape: 'instant', in_more: true },
  { key: 'other', label: '기타', shape: 'range', in_more: true },
];
let recordTypes = new Map(DEFAULT_RECORD_TYPES.map((t) => [t.key, t]));
/** 요약에서 받은 기록 종류로 바꾼다(비어 있으면 그대로) */
export function setRecordTypes(list) {
  if (Array.isArray(list) && list.length) recordTypes = new Map(list.map((t) => [t.key, t]));
}
/** @returns {RecordType|undefined} */
export const recordType = (kind) => recordTypes.get(kind);
/** [+] 더보기에 보일 종류(표의 순서대로) */
export const moreTypes = () => [...recordTypes.values()].filter((t) => t.in_more);
/** 수유·기저귀·잠은 큰 버튼과 따로 만든 창이 있다. 나머지는 기록 종류 표로 움직인다 */
export const isBuiltinKind = (kind) => kind === KIND.FEED || kind === KIND.DIAPER || kind === KIND.SLEEP;
/** 소수 자리는 한 번에 움직이는 양(step)을 따른다: 0.1 → 37.4, 0.01 → 7.35 */
export function formatValue(t, v) {
  if (v == null || Number.isNaN(Number(v))) return '';
  const digits = t?.step ? Math.max(0, Math.round(-Math.log10(t.step))) : 0;
  return `${Number(v).toFixed(digits)}${t?.unit || ''}`;
}
/** 세부 글 한 줄(약 이름, 병원, 놀이, 메모) */
export function detailText(detail = {}) {
  return ['medicine', 'what', 'hospital', 'reason', 'memo'].map((k) => detail?.[k]).filter(Boolean).join(' · ');
}
/** 수유·기저귀·잠 말고 다른 종류의 이름. 예: "체온 37.4°C", "목욕 · 10분 · 보습로션" */
export function describeOther(kind, { value = null, at = null, ended_at = null, detail = {} } = {}) {
  const t = recordType(kind);
  const parts = [t?.label || kind];
  if (t?.shape === 'number' && value != null) parts[0] += ` ${formatValue(t, value)}`;
  if (ended_at && at) parts.push(formatDuration(new Date(ended_at) - new Date(at)));
  const extra = detailText(detail);
  if (extra) parts.push(extra);
  return parts.join(' · ');
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
  let text = isBuiltinKind(ev.kind) ? ev.kind : describeOther(ev.kind, { value: ev.value_num, at: ev.occurred_at, ended_at: ev.ended_at, detail: ev.detail });
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
  return describeOther(r.kind, { value: r.value, at: r.at, ended_at: r.ended_at, detail: r.detail });
}
