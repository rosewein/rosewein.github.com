// 연결이 끊겼을 때만 쓰는 근사 계산.
// 진짜 계산은 Supabase 요약 함수(care_summary)가 한다. 여기서는 마지막으로 받은 요약 위에
// 아직 못 보낸 기록을 얹어, 화면이 "방금 넣은 기록"을 바로 보여 줄 수 있게만 한다.
// 순수 함수라 tests/unit/pending.test.mjs 로 시험한다.

/** @typedef {import('../domain.js').Summary} Summary */
/** @typedef {import('./queue.js').QueueItem} QueueItem */

const DAY = 86400000;
const time = (v) => (v ? new Date(v).getTime() : 0);

/**
 * 요약 + 못 보낸 기록 → 화면에 보여 줄 요약
 * @param {Summary|null} summary
 * @param {QueueItem[]} items
 * @returns {Summary}
 */
export function applyPending(summary, items) {
  /** @type {Summary} */
  const s = structuredClone(summary || {});
  s.today ??= { feed_count: 0, feed_ml: 0 };
  s.recent ??= [];
  const dayStart = time(s.day_start);
  const isToday = (at) => at >= dayStart && at < dayStart + DAY;
  const cancelled = new Set(items.filter((i) => i.op === 'cancel').map((i) => i.id));

  // 1) 못 보낸 추가
  for (const item of items) {
    if (item.op !== 'add' || cancelled.has(item.id)) continue;
    const p = item.payload;
    if (s.recent.some((r) => r.id === p.id)) continue;
    const at = time(p.occurred_at);
    s.recent.push({ id: p.id, kind: p.kind, at: p.occurred_at, ended_at: p.ended_at ?? null, ml: p.amount_ml ?? null, detail: p.detail, pending: true });

    if (p.kind === 'feed') {
      if (at > time(s.last_feed?.at)) s.last_feed = { id: p.id, at: p.occurred_at, ml: p.amount_ml ?? null };
      if (isToday(at)) {
        s.today.feed_count += 1;
        s.today.feed_ml += p.amount_ml || 0;
      }
    } else if (p.kind === 'diaper') {
      if (at > time(s.last_diaper?.at)) s.last_diaper = { id: p.id, at: p.occurred_at, type: p.detail?.type };
    } else if (p.kind === 'sleep') {
      if (at > time(s.last_sleep?.at)) s.last_sleep = { id: p.id, at: p.occurred_at, ended_at: p.ended_at };
    }
  }

  // 2) 못 보낸 취소: 최근 목록에서 빼고, '마지막' 이 빠졌으면 그다음 것으로
  if (cancelled.size) {
    for (const r of s.recent.filter((x) => cancelled.has(x.id) && !x.pending)) {
      if (r.kind === 'feed' && isToday(time(r.at))) {
        s.today.feed_count = Math.max(0, s.today.feed_count - 1);
        s.today.feed_ml = Math.max(0, s.today.feed_ml - (r.ml || 0));
      }
    }
    s.recent = s.recent.filter((r) => !cancelled.has(r.id));
    const latest = (kind) => s.recent.filter((r) => r.kind === kind).sort((a, b) => time(b.at) - time(a.at))[0];
    if (cancelled.has(s.last_feed?.id)) {
      const r = latest('feed');
      s.last_feed = r ? { id: r.id, at: r.at, ml: r.ml } : null;
    }
    if (cancelled.has(s.last_diaper?.id)) {
      const r = latest('diaper');
      s.last_diaper = r ? { id: r.id, at: r.at, type: r.detail?.type } : null;
    }
  }

  // 3) 못 보낸 잠 끝(깼어요 / 되돌리기): 순서대로 덮어쓴다
  for (const item of items.filter((i) => i.op === 'sleep_end')) {
    for (const r of s.recent) if (r.id === item.id) r.ended_at = item.ended_at;
    if (s.last_sleep?.id === item.id) s.last_sleep = { ...s.last_sleep, ended_at: item.ended_at };
  }

  // 4) 못 보낸 수유량 설정: 가장 나중 것
  const amounts = items.filter((i) => i.op === 'feed_amounts').pop();
  if (amounts) s.feed_amounts = amounts.amounts;

  s.recent.sort((a, b) => time(b.at) - time(a.at));
  return s;
}

/**
 * 비슷한 시각에 같은 종류 기록이 있는지(기기 안에서만 하는 확인).
 * 연결돼 있으면 같은 확인을 Supabase 의 care_add_event 가 한다.
 * @param {Summary|null} summary
 * @param {{id?: string, kind: string, occurred_at: string}} payload
 * @param {number} windowMin
 */
export function findLocalDuplicate(summary, payload, windowMin) {
  const at = time(payload.occurred_at);
  const win = windowMin * 60000;
  return (summary?.recent || []).find((r) => r.kind === payload.kind && r.id !== payload.id && Math.abs(time(r.at) - at) <= win) || null;
}
