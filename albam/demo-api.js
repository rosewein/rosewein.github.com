// ?demo 로 열면 Supabase 대신 이 기기 안에서만 도는 가짜 통신을 쓴다.
// 화면을 미리 보거나 시험할 때만 쓴다. 규칙은 supabase/001_care_schema.sql 을 흉내 낸다.

const KEY = 'albam.demo.events';

function load() {
  try { return JSON.parse(localStorage.getItem(KEY) || 'null'); } catch (e) { return null; }
}
function seed() {
  const now = Date.now();
  const m = (min) => new Date(now - min * 60000).toISOString();
  return [
    { id: crypto.randomUUID(), kind: 'feed', occurred_at: m(155), amount_ml: 160, detail: {} },
    { id: crypto.randomUUID(), kind: 'diaper', occurred_at: m(70), detail: { type: 'pee' } },
    { id: crypto.randomUUID(), kind: 'feed', occurred_at: m(330), amount_ml: 140, detail: {} },
    { id: crypto.randomUUID(), kind: 'feed', occurred_at: m(520), amount_ml: 120, detail: {} },
    { id: crypto.randomUUID(), kind: 'sleep', occurred_at: m(300), ended_at: m(200), detail: {} },
  ];
}

export function createDemoApi(cfg) {
  let events = load() || seed();
  const save = () => { try { localStorage.setItem(KEY, JSON.stringify(events)); } catch (e) {} };
  save();
  const live = () => events.filter((e) => !e.deleted_at).sort((a, b) => new Date(b.occurred_at) - new Date(a.occurred_at));
  const listeners = new Set();
  const dupWindow = 10;

  function summary() {
    const now = new Date();
    const day = new Date(now); day.setHours(0, 0, 0, 0);
    const l = live();
    const feeds = l.filter((e) => e.kind === 'feed');
    const lastOf = (k) => l.find((e) => e.kind === k);
    const lf = lastOf('feed'), ld = lastOf('diaper'), ls = lastOf('sleep');
    const today = feeds.filter((e) => new Date(e.occurred_at) >= day);
    const amounts = [];
    for (const f of feeds) if (f.amount_ml != null && !amounts.includes(f.amount_ml) && amounts.length < 3) amounts.push(f.amount_ml);
    return {
      server_time: now.toISOString(),
      day_start: day.toISOString(),
      last_feed: lf ? { id: lf.id, at: lf.occurred_at, ml: lf.amount_ml } : null,
      today: { feed_count: today.length, feed_ml: today.reduce((a, e) => a + (e.amount_ml || 0), 0) },
      last_diaper: ld ? { id: ld.id, at: ld.occurred_at, type: ld.detail.type } : null,
      last_sleep: ls ? { id: ls.id, at: ls.occurred_at, ended_at: ls.ended_at } : null,
      recent_feed_amounts: amounts,
      recent: l.slice(0, 8).map((e) => ({ id: e.id, kind: e.kind, at: e.occurred_at, ended_at: e.ended_at || null, ml: e.amount_ml ?? null, detail: e.detail, source: e.source })),
      due_chores: [],
      settings: { day_start_hour: 0, dup_window_minutes: dupWindow },
    };
  }

  return {
    demo: true,
    isConfigured: () => true,
    isLoggedIn: () => true,
    email: () => 'demo',
    onChange(fn) { listeners.add(fn); return () => listeners.delete(fn); },
    async signIn() {},
    signOut() { localStorage.removeItem(KEY); events = seed(); save(); },
    async pendingCount() { return 0; },
    async flush() {},
    async getSummary() { return { summary: summary(), stale: false, pending: 0 }; },
    async addEvent(ev, { force = false } = {}) {
      const id = ev.id || crypto.randomUUID();
      const at = new Date(ev.occurred_at || Date.now());
      if (!force) {
        const dup = live().find((e) => e.kind === ev.kind && Math.abs(new Date(e.occurred_at) - at) <= dupWindow * 60000);
        if (dup) return { status: 'confirm', id, existing: { id: dup.id, kind: dup.kind, at: dup.occurred_at, ml: dup.amount_ml, detail: dup.detail } };
      }
      events.push({ id, kind: ev.kind, occurred_at: at.toISOString(), ended_at: ev.ended_at ? new Date(ev.ended_at).toISOString() : null,
        amount_ml: ev.amount_ml ?? null, detail: ev.detail || {}, source: ev.source, voice_text: ev.voice_text || null, recorded_at: new Date().toISOString() });
      save();
      return { status: 'saved', id };
    },
    async cancelEvent(id) {
      const e = events.find((x) => x.id === id);
      if (!e) return { status: 'not_found', id };
      if (e.deleted_at) return { status: 'already_cancelled', id };
      e.deleted_at = new Date().toISOString();
      save();
      return { status: 'cancelled', id };
    },
  };
}
