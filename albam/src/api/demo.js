// 미리 보기(?demo). 진짜 통신 창구(index.js)에 Supabase 대신 이 가짜 서버를 끼운다.
// 그래서 오프라인 저장, "대기 n건", 다시 연결되면 보내기까지 실제와 똑같이 동작한다.
// 가짜 서버의 기록은 이 기기의 localStorage 에만 있고, 기기 안 큐·캐시도 실제와 다른 이름을 쓴다.
// 규칙은 supabase/*.sql 의 함수를 흉내 낸다.

import { createApi, STORAGE } from './index.js';
import { NetworkError } from './errors.js';

const EVENTS_KEY = 'albam.demo.events';
const AMOUNTS_KEY = 'albam.demo.feedAmounts';
const DEFAULT_FEED_AMOUNTS = [200, 230, 270];
const DUP_WINDOW_MIN = 10;
const RECENT_LIMIT = 8;

const minutesAgo = (n) => new Date(Date.now() - n * 60000).toISOString();

function sampleEvents() {
  const ev = (kind, min, extra = {}) => ({ id: crypto.randomUUID(), kind, occurred_at: minutesAgo(min), detail: {}, ...extra });
  return [
    ev('feed', 155, { amount_ml: 200 }),
    ev('diaper', 70, { detail: { type: 'pee' } }),
    ev('feed', 330, { amount_ml: 200 }),
    ev('feed', 520, { amount_ml: 170 }),
    ev('sleep', 300, { ended_at: minutesAgo(200) }),
  ];
}

/** Supabase 함수 세 개를 흉내 내는 가짜 서버. 기기가 오프라인이면 NetworkError 를 던진다 */
class DemoServer {
  configured = true;
  loggedIn = true;
  session = { email: 'demo' };
  onSessionChange = () => {};

  constructor() {
    this.events = this.load() ?? sampleEvents();
    this.save();
  }

  async signIn() {}
  signOut() { this.events = sampleEvents(); this.save(); }

  async rpc(name, args = {}) {
    if (!navigator.onLine) throw new NetworkError('offline (demo)');
    switch (name) {
      case 'care_summary': return this.summary();
      case 'care_add_event': return this.addEvent(args.p);
      case 'care_cancel_event': return this.cancelEvent(args.p_id);
      case 'care_set_feed_amounts': return this.setFeedAmounts(args.p_amounts);
      default: throw new Error(`unknown function ${name}`);
    }
  }

  // ── 함수 흉내 ──
  summary() {
    const now = new Date();
    const dayStart = new Date(now); dayStart.setHours(0, 0, 0, 0);
    const all = this.live();
    const feeds = all.filter((e) => e.kind === 'feed');
    const todayFeeds = feeds.filter((e) => new Date(e.occurred_at) >= dayStart);
    const [feed, diaper, sleep] = ['feed', 'diaper', 'sleep'].map((kind) => all.find((e) => e.kind === kind));
    return {
      server_time: now.toISOString(),
      day_start: dayStart.toISOString(),
      last_feed: feed ? { id: feed.id, at: feed.occurred_at, ml: feed.amount_ml } : null,
      today: { feed_count: todayFeeds.length, feed_ml: todayFeeds.reduce((sum, e) => sum + (e.amount_ml || 0), 0) },
      last_diaper: diaper ? { id: diaper.id, at: diaper.occurred_at, type: diaper.detail.type } : null,
      last_sleep: sleep ? { id: sleep.id, at: sleep.occurred_at, ended_at: sleep.ended_at } : null,
      feed_amounts: this.feedAmounts(),
      recent: all.slice(0, RECENT_LIMIT).map((e) => ({
        id: e.id, kind: e.kind, at: e.occurred_at, ended_at: e.ended_at ?? null, ml: e.amount_ml ?? null, detail: e.detail, source: e.source,
      })),
      due_chores: [],
      settings: { day_start_hour: 0, dup_window_minutes: DUP_WINDOW_MIN },
    };
  }

  addEvent(p) {
    if (this.events.some((e) => e.id === p.id)) return { status: 'saved', id: p.id, repeat: true };
    const at = new Date(p.occurred_at);
    if (!p.force) {
      const dup = this.live().find((e) => e.kind === p.kind && Math.abs(new Date(e.occurred_at) - at) <= DUP_WINDOW_MIN * 60000);
      if (dup) return { status: 'confirm', existing: { id: dup.id, kind: dup.kind, at: dup.occurred_at, ml: dup.amount_ml, detail: dup.detail } };
    }
    this.events.push({
      id: p.id, kind: p.kind, occurred_at: at.toISOString(), ended_at: p.ended_at ?? null, amount_ml: p.amount_ml ?? null,
      detail: p.detail || {}, source: p.source, voice_text: p.voice_text ?? null, recorded_at: new Date().toISOString(),
    });
    this.save();
    return { status: 'saved', id: p.id };
  }

  cancelEvent(id) {
    const e = this.events.find((x) => x.id === id);
    if (!e) return { status: 'not_found', id };
    if (e.deleted_at) return { status: 'already_cancelled', id };
    e.deleted_at = new Date().toISOString();
    this.save();
    return { status: 'cancelled', id };
  }

  setFeedAmounts(amounts) {
    const clean = [...new Set(amounts)].sort((a, b) => a - b);
    if (!clean.length || clean.length > 6 || clean.some((a) => a < 10 || a > 500)) throw new Error('bad_feed_amounts');
    localStorage.setItem(AMOUNTS_KEY, JSON.stringify(clean));
    return { status: 'saved', feed_amounts: clean };
  }

  feedAmounts() {
    try { return JSON.parse(localStorage.getItem(AMOUNTS_KEY) || 'null') ?? DEFAULT_FEED_AMOUNTS; } catch (e) { return DEFAULT_FEED_AMOUNTS; }
  }

  // ── 저장 ──
  live() {
    return this.events.filter((e) => !e.deleted_at).sort((a, b) => new Date(b.occurred_at) - new Date(a.occurred_at));
  }
  load() { try { return JSON.parse(localStorage.getItem(EVENTS_KEY) || 'null'); } catch (e) { return null; } }
  save() { try { localStorage.setItem(EVENTS_KEY, JSON.stringify(this.events)); } catch (e) { /* 미리 보기라 괜찮음 */ } }
}

/** @returns {import('./index.js').CareApi & {demo: true}} */
export function createDemoApi() {
  const api = createApi({}, { transport: new DemoServer(), storage: STORAGE.demo });
  return { ...api, demo: true };
}
