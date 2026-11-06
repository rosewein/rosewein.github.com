// ?demo 로 열면 Supabase 대신 쓰는 가짜 통신. 이 기기의 localStorage 에만 저장한다.
// index.js 의 CareApi 와 모양이 같고, 규칙은 supabase/001_care_schema.sql 을 흉내 낸다.
// 화면을 미리 보거나 브라우저 시험(tests/e2e)을 돌릴 때만 쓴다.

const STORE_KEY = 'albam.demo.events';
const DUP_WINDOW_MIN = 10;
const QUICK_AMOUNT_COUNT = 3;
const RECENT_LIMIT = 8;

const minutesAgo = (n) => new Date(Date.now() - n * 60000).toISOString();

function sampleEvents() {
  const ev = (kind, min, extra = {}) => ({ id: crypto.randomUUID(), kind, occurred_at: minutesAgo(min), detail: {}, ...extra });
  return [
    ev('feed', 155, { amount_ml: 160 }),
    ev('diaper', 70, { detail: { type: 'pee' } }),
    ev('feed', 330, { amount_ml: 140 }),
    ev('feed', 520, { amount_ml: 120 }),
    ev('sleep', 300, { ended_at: minutesAgo(200) }),
  ];
}

/** @returns {import('./index.js').CareApi & {demo: true}} */
export function createDemoApi() {
  let events = load() ?? sampleEvents();
  save();

  function load() { try { return JSON.parse(localStorage.getItem(STORE_KEY) || 'null'); } catch (e) { return null; } }
  function save() { try { localStorage.setItem(STORE_KEY, JSON.stringify(events)); } catch (e) { /* 미리 보기라 괜찮음 */ } }
  const live = () => events.filter((e) => !e.deleted_at).sort((a, b) => new Date(b.occurred_at) - new Date(a.occurred_at));

  function summary() {
    const now = new Date();
    const dayStart = new Date(now); dayStart.setHours(0, 0, 0, 0);
    const all = live();
    const feeds = all.filter((e) => e.kind === 'feed');
    const todayFeeds = feeds.filter((e) => new Date(e.occurred_at) >= dayStart);
    const lastOf = (kind) => all.find((e) => e.kind === kind);
    const [feed, diaper, sleep] = ['feed', 'diaper', 'sleep'].map(lastOf);
    const amounts = [...new Set(feeds.map((e) => e.amount_ml).filter((x) => x != null))].slice(0, QUICK_AMOUNT_COUNT);
    return {
      server_time: now.toISOString(),
      day_start: dayStart.toISOString(),
      last_feed: feed ? { id: feed.id, at: feed.occurred_at, ml: feed.amount_ml } : null,
      today: { feed_count: todayFeeds.length, feed_ml: todayFeeds.reduce((sum, e) => sum + (e.amount_ml || 0), 0) },
      last_diaper: diaper ? { id: diaper.id, at: diaper.occurred_at, type: diaper.detail.type } : null,
      last_sleep: sleep ? { id: sleep.id, at: sleep.occurred_at, ended_at: sleep.ended_at } : null,
      recent_feed_amounts: amounts,
      recent: all.slice(0, RECENT_LIMIT).map((e) => ({
        id: e.id, kind: e.kind, at: e.occurred_at, ended_at: e.ended_at ?? null, ml: e.amount_ml ?? null, detail: e.detail, source: e.source,
      })),
      due_chores: [],
      settings: { day_start_hour: 0, dup_window_minutes: DUP_WINDOW_MIN },
    };
  }

  return {
    demo: true,
    isConfigured: () => true,
    isLoggedIn: () => true,
    email: () => 'demo',
    onChange: () => () => {},
    async signIn() {},
    signOut() { events = sampleEvents(); save(); },
    async pendingCount() { return 0; },
    async flush() {},
    async getSummary() { return { summary: summary(), stale: false, pending: 0 }; },

    async addEvent(ev, { force = false } = {}) {
      const id = ev.id || crypto.randomUUID();
      const at = new Date(ev.occurred_at || Date.now());
      if (!force) {
        const dup = live().find((e) => e.kind === ev.kind && Math.abs(new Date(e.occurred_at) - at) <= DUP_WINDOW_MIN * 60000);
        if (dup) return { status: 'confirm', id, existing: { id: dup.id, kind: dup.kind, at: dup.occurred_at, ml: dup.amount_ml, detail: dup.detail } };
      }
      events.push({
        id, kind: ev.kind, occurred_at: at.toISOString(), ended_at: ev.ended_at ? new Date(ev.ended_at).toISOString() : null,
        amount_ml: ev.amount_ml ?? null, detail: ev.detail || {}, source: ev.source, voice_text: ev.voice_text || null,
        recorded_at: new Date().toISOString(),
      });
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
