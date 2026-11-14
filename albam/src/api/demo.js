// 미리 보기(?demo). 진짜 통신 창구(index.js)에 Supabase 대신 이 가짜 서버를 끼운다.
// 그래서 오프라인 저장, "대기 n건", 다시 연결되면 보내기까지 실제와 똑같이 동작한다.
// 가짜 서버의 기록은 이 기기의 localStorage 에만 있고, 기기 안 큐·캐시도 실제와 다른 이름을 쓴다.
// 규칙은 supabase/*.sql 의 함수를 흉내 낸다.

import { createApi, STORAGE } from './index.js';
import { DEFAULT_RECORD_TYPES } from '../domain.js';
import { NetworkError } from './errors.js';

const EVENTS_KEY = 'albam.demo.events';
const AMOUNTS_KEY = 'albam.demo.feedAmounts';
const DEFAULT_FEED_AMOUNTS = [200, 230, 270];
const DUP_WINDOW_MIN = 10;
const RECENT_LIMIT = 8;

/** 미리 보기 아기. 나이 규칙은 supabase/006 의 care_age 와 같다(태어난 날 D+1, 개월 뒤 남은 날 +1) */
const DEMO_BABY = { name: '세훈', nickname: '알밤', birth_date: '2026-06-18', due_date: '2026-07-10' };
function monthsDays(on, from) {
  let m = (on.getFullYear() - from.getFullYear()) * 12 + on.getMonth() - from.getMonth();
  const plus = (n) => { const d = new Date(from); d.setMonth(d.getMonth() + n); if (d.getDate() !== from.getDate()) d.setDate(0); return d; };
  if (plus(m) > on) m -= 1;
  return [m, Math.round((on - plus(m)) / 86400000) + 1];
}
function ageOn(now, baby) {
  const on = new Date(now); on.setHours(0, 0, 0, 0);
  const day = (s) => { const [y, mo, d] = s.split('-').map(Number); return new Date(y, mo - 1, d); };
  const birth = day(baby.birth_date);
  const due = day(baby.due_date);
  const [months, days] = monthsDays(on, birth);
  const [cm, cd] = monthsDays(on, due);
  return { day: Math.round((on - birth) / 86400000) + 1, months, days, corrected_day: Math.round((on - due) / 86400000) + 1, corrected_months: cm, corrected_days: cd };
}

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
      case 'care_stats': return this.stats(args.p_days);
      case 'care_update_event': return this.updateEvent(args.p);
      case 'care_timeline': return this.timeline(args.p_days);
      case 'care_measures': return this.measures();
      case 'care_upcoming': return this.upcoming();
      case 'care_set_sleep_end': return this.setSleepEnd(args.p_id, args.p_ended_at);
      case 'care_voice_log': {   // 호출어 시험 기록: 미리 보기에서는 화면 시험용으로만 남긴다
        const log = (window.__albamVoiceLog ??= []);
        const i = log.findIndex((r) => r.id === args.p.id);
        if (i >= 0) log[i] = { ...log[i], wrong: args.p.wrong }; else log.push(args.p);
        return null;
      }
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
    const [feed, diaper, sleep] = ['feed', 'diaper', 'sleep'].map((kind) => all.find((e) => e.kind === kind));  // live() 는 실제 시각 역순
    return {
      server_time: now.toISOString(),
      day_start: dayStart.toISOString(),
      last_feed: feed ? { id: feed.id, at: feed.occurred_at, ml: feed.amount_ml, ended_at: feed.ended_at ?? null, feeding: !feed.ended_at && !!feed.detail?.feeding } : null,
      today: { feed_count: todayFeeds.length, feed_ml: todayFeeds.reduce((sum, e) => sum + (e.amount_ml || 0), 0) },
      last_diaper: diaper ? { id: diaper.id, at: diaper.occurred_at, type: diaper.detail.type } : null,
      last_poo: (({ id, occurred_at: at, detail } = {}) => (id ? { id, at, type: detail.type } : null))(all.find((e) => e.kind === 'diaper' && ['poo', 'both'].includes(e.detail?.type))),
      last_sleep: sleep ? { id: sleep.id, at: sleep.occurred_at, ended_at: sleep.ended_at } : null,
      feed_amounts: this.feedAmounts(),
      record_types: DEFAULT_RECORD_TYPES,
      baby: DEMO_BABY,
      age: ageOn(now, DEMO_BABY),
      recent: all.slice(0, RECENT_LIMIT).map((e) => ({
        id: e.id, kind: e.kind, at: e.occurred_at, ended_at: e.ended_at ?? null, ml: e.amount_ml ?? null, value: e.value_num ?? null, detail: e.detail, source: e.source,
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
      id: p.id, kind: p.kind, occurred_at: at.toISOString(), ended_at: p.ended_at ?? null, amount_ml: p.amount_ml ?? null, value_num: p.value_num ?? null,
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

  /** 다가오는 일정: 미리 보기라 20일 뒤 예방접종 하나(?demo&appt=2 처럼 남은 날을 바꿔 볼 수 있다) */
  upcoming() {
    const left = Number(new URLSearchParams(location.search).get('appt') ?? 20);
    const d = new Date(); d.setDate(d.getDate() + left);
    const on = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
    return [{ id: 'demo-appointment', on_date: on, at_time: null, kind: 'vaccine', title: '예방접종', place: null, items: ['헥사심 3차', '폐렴구균 3차', '로타텍 3차', '독감 1차'], days_left: left }];
  }

  /** 측정 기록: 미리 보기라 지난번 값 두 개를 넣어 둔다(성별도 예시) */
  measures() {
    const sample = [{ kind: 'weight', at: minutesAgo(60 * 24 * 13), value: 7.2 }, { kind: 'height', at: minutesAgo(60 * 24 * 13), value: 65 }];
    const mine = this.live().filter((e) => (e.kind === 'weight' || e.kind === 'height') && e.value_num != null)
      .map((e) => ({ id: e.id, kind: e.kind, at: e.occurred_at, value: e.value_num }));
    return { baby: { birth_date: DEMO_BABY.birth_date, due_date: DEMO_BABY.due_date, sex: 'boy' }, measures: [...sample, ...mine] };
  }

  /** 최근 n일 날짜별 통계. 미리 보기라 지난날은 그럴듯한 가짜 숫자로 채운다 */
  stats(days = 7) {
    const out = [];
    for (let i = days - 1; i >= 0; i -= 1) {
      const d = new Date(); d.setHours(0, 0, 0, 0); d.setDate(d.getDate() - i);
      const next = new Date(d); next.setDate(d.getDate() + 1);
      const inDay = this.live().filter((e) => new Date(e.occurred_at) >= d && new Date(e.occurred_at) < next);
      const feeds = inDay.filter((e) => e.kind === 'feed');
      const diapers = inDay.filter((e) => e.kind === 'diaper');
      const fake = i > 0;   // 오늘은 실제 미리 보기 기록, 지난날은 고정 예시
      const seed = (d.getDate() * 37) % 7;
      out.push({
        day: `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`,
        feed_count: fake ? 4 + (seed % 2) : feeds.length,
        feed_ml: fake ? 760 + seed * 20 : feeds.reduce((s, e) => s + (e.amount_ml || 0), 0),
        feed_min: fake ? 10 + (seed % 3) : null,
        diaper_total: fake ? 6 + (seed % 3) : diapers.length,
        diaper_pee: fake ? 4 : diapers.filter((e) => e.detail.type === 'pee').length,
        diaper_poo: fake ? 1 + (seed % 2) : diapers.filter((e) => e.detail.type === 'poo').length,
        diaper_both: fake ? 1 : diapers.filter((e) => e.detail.type === 'both').length,
        nap_min: fake ? 120 + seed * 10 : 0,
        night_min: fake ? 600 + seed * 5 : 0,
        sleep_min: fake ? 720 + seed * 15 : 0,
      });
    }
    return out;
  }

  updateEvent(p) {
    const e = this.events.find((x) => x.id === p.id && !x.deleted_at);
    if (!e) return { status: 'not_found', id: p.id };
    if (p.occurred_at) e.occurred_at = new Date(p.occurred_at).toISOString();
    if ('ended_at' in p) e.ended_at = p.ended_at ?? null;
    if (p.amount_ml != null) e.amount_ml = p.amount_ml;
    if (p.value_num != null) e.value_num = p.value_num;
    if (p.detail) e.detail = { ...(e.detail || {}), ...p.detail };
    this.save();
    return { status: 'saved', id: p.id };
  }

  timeline(days = 3) {
    const from = new Date(); from.setHours(0, 0, 0, 0); from.setDate(from.getDate() - (days - 1));
    return this.live().filter((e) => new Date(e.occurred_at) >= from || (e.kind === 'sleep' && (!e.ended_at || new Date(e.ended_at) >= from)))
      .reverse().map((e) => ({ id: e.id, kind: e.kind, at: e.occurred_at, ended_at: e.ended_at ?? null, ml: e.amount_ml ?? null, value: e.value_num ?? null,
        type: e.detail?.type ?? null, memo: e.detail?.memo ?? null, feeding: !!e.detail?.feeding, detail: e.detail || {} }));
  }

  setSleepEnd(id, endedAt) {
    const e = this.events.find((x) => x.id === id && x.kind === 'sleep' && !x.deleted_at);
    if (!e) return { status: 'not_found', id };
    e.ended_at = endedAt ?? null;
    this.save();
    return { status: 'saved', id, ended_at: e.ended_at };
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
