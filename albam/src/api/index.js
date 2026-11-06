// 화면 쪽 통신 창구. 화면은 여기 있는 함수만 부른다.
//   getSummary()  요약 읽기
//   addEvent()    기록 추가
//   cancelEvent() 저장 직후 취소(지우지 않고 취소 표시)
// 기기를 바꿀 때(개인 폰, ESP32) 다시 짜야 하는 범위를 이 폴더로 줄이려는 것이다.
// 미리 보기(?demo)도 이 함수를 그대로 쓰고, Supabase 대신 demo.js 의 가짜 서버만 끼운다.
// 그래서 미리 보기에서도 오프라인 저장·"대기 n건"·다시 보내기가 실제와 똑같이 동작한다.

import { AuthError, NetworkError } from './errors.js';
import { SupabaseRest } from './supabase-rest.js';
import { createQueue } from './queue.js';
import { applyPending, findLocalDuplicate } from './pending.js';

export { AuthError, NetworkError };

const DEFAULT_DUP_WINDOW_MIN = 10;

/** @typedef {import('../domain.js').CareEvent} CareEvent */
/** @typedef {import('../domain.js').Summary} Summary */

/**
 * @typedef {Object} SummaryResult
 * @property {(Summary & {_received_at?: number})|null} summary  못 보낸 기록까지 얹은 요약
 * @property {boolean} stale      서버에서 못 받고 마지막으로 받은 것을 보여 주는 중
 * @property {number} pending     못 보낸 기록 수
 * @property {Error} [error]
 */

/**
 * @typedef {Object} AddResult
 * @property {'saved'|'queued'|'confirm'} status  queued: 기기 안에 쌓아 둠 / confirm: 비슷한 기록이 있어 저장 안 함
 * @property {string} id
 * @property {Object} [existing]   confirm 일 때 이미 있는 기록
 */

/**
 * @typedef {Object} CareApi
 * @property {() => boolean} isConfigured
 * @property {() => boolean} isLoggedIn
 * @property {() => string} email
 * @property {(fn: () => void) => () => void} onChange   못 보낸 기록 수나 로그인 상태가 바뀔 때
 * @property {(email: string, password: string) => Promise<void>} signIn
 * @property {() => void} signOut
 * @property {() => Promise<number>} pendingCount
 * @property {() => Promise<void>} flush                 못 보낸 기록 다시 보내기
 * @property {() => Promise<SummaryResult>} getSummary
 * @property {(ev: CareEvent, opts?: {force?: boolean}) => Promise<AddResult>} addEvent
 * @property {(id: string) => Promise<{status: string}>} cancelEvent
 */

/**
 * 서버 쪽 창구. SupabaseRest 와 demo.js 의 DemoServer 가 이 모양이다.
 * @typedef {Object} Transport
 * @property {boolean} configured
 * @property {boolean} loggedIn
 * @property {{email: string}|null} session
 * @property {() => void} onSessionChange
 * @property {(email: string, password: string) => Promise<void>} signIn
 * @property {() => void} signOut
 * @property {(name: string, args?: Object) => Promise<any>} rpc   연결 문제는 NetworkError, 로그인 문제는 AuthError
 */

/** 기기 안에 남기는 것들의 이름. 실제와 미리 보기가 섞이지 않게 따로 쓴다 */
export const STORAGE = {
  real: { queueDb: 'albam', summaryKey: 'albam.summary' },
  demo: { queueDb: 'albam-demo', summaryKey: 'albam.demo.summary' },
};

/**
 * @param {{supabaseUrl: string, supabaseAnonKey: string}} cfg
 * @param {{transport?: Transport, storage?: {queueDb: string, summaryKey: string}}} [opts]  미리 보기·시험용
 * @returns {CareApi}
 */
export function createApi(cfg, { transport, storage = STORAGE.real } = {}) {
  const rest = transport ?? new SupabaseRest({ url: cfg.supabaseUrl, anonKey: cfg.supabaseAnonKey });
  const queue = createQueue(storage.queueDb);
  const SUMMARY_CACHE_KEY = storage.summaryKey;
  const listeners = new Set();
  const notify = () => listeners.forEach((fn) => fn());
  rest.onSessionChange = notify;
  let flushing = null;

  // ── 요약 캐시: 연결이 끊겼을 때 마지막으로 받은 요약을 보여 주려고 ──
  const readCache = () => { try { return JSON.parse(localStorage.getItem(SUMMARY_CACHE_KEY) || 'null'); } catch (e) { return null; } };
  const writeCache = (s) => { try { localStorage.setItem(SUMMARY_CACHE_KEY, JSON.stringify(s)); } catch (e) { /* 캐시는 없어도 됨 */ } };

  /** 쌓인 기록을 순서대로 보낸다. 연결이 안 되면 거기서 멈추고 다음에 다시 */
  function flush() {
    flushing ??= (async () => {
      for (const item of await queue.all()) {
        try {
          if (item.op === 'add') {
            // 기기 안에서 이미 확인을 거쳤거나, 확인할 수 없던 기록이므로 force
            await rest.rpc('care_add_event', { p: { ...item.payload, force: true } });
          } else {
            await rest.rpc('care_cancel_event', { p_id: item.id });
          }
          await queue.remove(item.seq);
        } catch (e) {
          if (e instanceof NetworkError || e instanceof AuthError) break;
          // 서버가 받지 않는 기록(형식 오류 등)은 계속 막고 있지 않게 버린다
          console.error('queued item rejected by server, dropped', item, e);
          await queue.remove(item.seq);
        }
      }
      notify();
    })().finally(() => { flushing = null; });
    return flushing;
  }

  /** 쌓인 게 있으면 먼저 보내 보고, 남은 것을 돌려준다 */
  async function flushThenList() {
    const before = await queue.all();
    if (!before.length || !navigator.onLine) return before;
    await flush().catch(() => {});
    return queue.all();
  }

  /** 연결이 안 될 때: 기기 안에서 비슷한 기록을 확인하고 쌓아 둔다 */
  async function enqueueAdd(payload, force) {
    if (!force) {
      const view = applyPending(readCache(), await queue.all());
      const windowMin = view.settings?.dup_window_minutes ?? DEFAULT_DUP_WINDOW_MIN;
      const existing = findLocalDuplicate(view, payload, windowMin);
      if (existing) return { status: 'confirm', id: payload.id, existing, local: true };
    }
    await queue.push({ op: 'add', id: payload.id, payload, created: Date.now() });
    notify();
    return { status: 'queued', id: payload.id };
  }

  return {
    isConfigured: () => rest.configured,
    isLoggedIn: () => rest.loggedIn,
    email: () => rest.session?.email || '',
    onChange(fn) { listeners.add(fn); return () => listeners.delete(fn); },
    signIn: (email, password) => rest.signIn(email, password),
    signOut: () => rest.signOut(),
    pendingCount: async () => (await queue.all()).length,
    flush,

    async getSummary() {
      const pending = await flushThenList();
      try {
        const summary = await rest.rpc('care_summary');
        summary._received_at = Date.now();
        writeCache(summary);
        return { summary: applyPending(summary, pending), stale: false, pending: pending.length };
      } catch (error) {
        if (error instanceof AuthError && !rest.loggedIn) throw error;
        const cached = readCache();
        return { summary: cached && applyPending(cached, pending), stale: true, pending: pending.length, error };
      }
    },

    async addEvent(ev, { force = false } = {}) {
      const payload = toPayload(ev);
      // 앞서 못 보낸 기록이 남아 있으면 순서를 지키려고 이것도 뒤에 쌓는다
      const pending = await flushThenList();
      if (!navigator.onLine || pending.length) return enqueueAdd(payload, force);
      try {
        const result = await rest.rpc('care_add_event', { p: { ...payload, force } });
        return { ...result, id: payload.id };
      } catch (e) {
        if (e instanceof NetworkError) return enqueueAdd(payload, force);
        throw e;
      }
    },

    async cancelEvent(id) {
      // 아직 못 보낸 기록이면 쌓인 곳에서 빼기만 하면 된다
      const unsent = (await queue.all()).find((i) => i.op === 'add' && i.id === id);
      if (unsent) {
        await queue.remove(unsent.seq);
        notify();
        return { status: 'cancelled', id };
      }
      try {
        return await rest.rpc('care_cancel_event', { p_id: id });
      } catch (e) {
        if (!(e instanceof NetworkError)) throw e;
        await queue.push({ op: 'cancel', id, created: Date.now() });
        notify();
        return { status: 'queued', id };
      }
    },
  };
}

/** 화면의 기록 → care_add_event 입력. id 가 없으면 여기서 만든다 */
function toPayload(ev) {
  const iso = (d) => (d instanceof Date ? d.toISOString() : d);
  const p = {
    id: ev.id || crypto.randomUUID(),
    kind: ev.kind,
    occurred_at: iso(ev.occurred_at || new Date()),
    detail: ev.detail || {},
    source: ev.source || 'living_room_touch',
  };
  if (ev.ended_at) p.ended_at = iso(ev.ended_at);
  if (ev.amount_ml != null) p.amount_ml = ev.amount_ml;
  if (ev.voice_text) p.voice_text = ev.voice_text;
  return p;
}
