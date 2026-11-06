// 화면 쪽 통신은 모두 이 파일 뒤에 숨긴다.
// 화면이 부르는 것은 getSummary(), addEvent() 둘(그리고 저장 직후 취소용 cancelEvent()).
// 기기를 바꿀 때(개인 폰, ESP32) 다시 짜야 하는 범위를 이 파일로 줄이려는 것이다.
//
// Supabase 라이브러리 없이 REST(PostgREST·GoTrue)를 fetch로 바로 부른다.
// 보내지 못한 기록은 IndexedDB 에 쌓아 두었다가 연결되면 순서대로 다시 보낸다.

const SESSION_KEY = 'albam.session';
const SUMMARY_KEY = 'albam.summary';
const TIMEOUT_MS = 10000;

export class AuthError extends Error {}
export class NetworkError extends Error {}

// ── 작은 IndexedDB 큐 ─────────────────────────────────────────
function openDb() {
  return new Promise((resolve, reject) => {
    const req = indexedDB.open('albam', 1);
    req.onupgradeneeded = () => req.result.createObjectStore('queue', { keyPath: 'seq', autoIncrement: true });
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error);
  });
}
async function tx(mode, fn) {
  const db = await openDb();
  try {
    return await new Promise((resolve, reject) => {
      const t = db.transaction('queue', mode);
      const out = fn(t.objectStore('queue'));
      t.oncomplete = () => resolve(out && 'result' in out ? out.result : undefined);
      t.onerror = () => reject(t.error);
    });
  } finally {
    db.close();
  }
}
const queue = {
  all: () => tx('readonly', (s) => s.getAll()),
  push: (item) => tx('readwrite', (s) => s.add(item)),
  remove: (seq) => tx('readwrite', (s) => s.delete(seq)),
};

// ── 도움 함수 ─────────────────────────────────────────────────
const iso = (d) => (d instanceof Date ? d.toISOString() : d);
const ms = (v) => (v ? new Date(v).getTime() : 0);

function toPayload(ev) {
  const p = { id: ev.id, kind: ev.kind, occurred_at: iso(ev.occurred_at || new Date()), detail: ev.detail || {}, source: ev.source || 'living_room_touch' };
  if (ev.ended_at) p.ended_at = iso(ev.ended_at);
  if (ev.amount_ml != null) p.amount_ml = ev.amount_ml;
  if (ev.voice_text) p.voice_text = ev.voice_text;
  return p;
}

// 아직 못 보낸 기록을 요약에 얹어 보여 준다(연결이 끊겼을 때만 쓰는 근사치).
// 진짜 계산은 Supabase 요약 함수가 한다.
export function applyPending(summary, items) {
  const s = JSON.parse(JSON.stringify(summary || {}));
  s.today = s.today || { feed_count: 0, feed_ml: 0 };
  s.recent = s.recent || [];
  const dayStart = ms(s.day_start);
  const cancelled = new Set(items.filter((i) => i.op === 'cancel').map((i) => i.id));
  for (const it of items) {
    if (it.op !== 'add' || cancelled.has(it.payload.id)) continue;
    const p = it.payload;
    const at = ms(p.occurred_at);
    if (s.recent.some((r) => r.id === p.id)) continue;
    s.recent.push({ id: p.id, kind: p.kind, at: p.occurred_at, ended_at: p.ended_at || null, ml: p.amount_ml ?? null, detail: p.detail, pending: true });
    if (p.kind === 'feed') {
      if (!s.last_feed || at > ms(s.last_feed.at)) s.last_feed = { id: p.id, at: p.occurred_at, ml: p.amount_ml ?? null };
      if (at >= dayStart && at < dayStart + 86400000) {
        s.today.feed_count += 1;
        s.today.feed_ml += p.amount_ml || 0;
      }
    } else if (p.kind === 'diaper') {
      if (!s.last_diaper || at > ms(s.last_diaper.at)) s.last_diaper = { id: p.id, at: p.occurred_at, type: p.detail?.type };
    } else if (p.kind === 'sleep') {
      if (!s.last_sleep || at > ms(s.last_sleep.at)) s.last_sleep = { id: p.id, at: p.occurred_at, ended_at: p.ended_at };
    }
  }
  // 취소한 기록 빼기: 최근 목록에서 다음 것으로
  if (cancelled.size) {
    const removed = s.recent.filter((r) => cancelled.has(r.id));
    s.recent = s.recent.filter((r) => !cancelled.has(r.id));
    for (const r of removed) {
      const at = ms(r.at);
      if (r.kind === 'feed' && at >= dayStart && !r.pending) {
        s.today.feed_count = Math.max(0, s.today.feed_count - 1);
        s.today.feed_ml = Math.max(0, s.today.feed_ml - (r.ml || 0));
      }
    }
    const latest = (kind) => s.recent.filter((r) => r.kind === kind).sort((a, b) => ms(b.at) - ms(a.at))[0];
    if (s.last_feed && cancelled.has(s.last_feed.id)) { const r = latest('feed'); s.last_feed = r ? { id: r.id, at: r.at, ml: r.ml } : null; }
    if (s.last_diaper && cancelled.has(s.last_diaper.id)) { const r = latest('diaper'); s.last_diaper = r ? { id: r.id, at: r.at, type: r.detail?.type } : null; }
  }
  s.recent.sort((a, b) => ms(b.at) - ms(a.at));
  return s;
}

// 비슷한 시각에 같은 종류가 있는지 (연결이 끊겼을 때 기기 안에서만 하는 확인)
export function findLocalDuplicate(summary, ev, windowMin) {
  const at = ms(iso(ev.occurred_at || new Date()));
  const win = windowMin * 60000;
  return (summary?.recent || []).find((r) => r.kind === ev.kind && r.id !== ev.id && Math.abs(ms(r.at) - at) <= win) || null;
}

// ── 본체 ─────────────────────────────────────────────────────
export function createApi(cfg) {
  const url = (cfg.supabaseUrl || '').replace(/\/+$/, '');
  const key = cfg.supabaseAnonKey || '';
  let session = null;
  let refreshing = null;
  let flushing = null;
  const listeners = new Set();
  const emit = () => listeners.forEach((fn) => { try { fn(); } catch (e) { console.error(e); } });

  try { session = JSON.parse(localStorage.getItem(SESSION_KEY) || 'null'); } catch (e) { session = null; }
  const saveSession = (s) => {
    session = s;
    try { s ? localStorage.setItem(SESSION_KEY, JSON.stringify(s)) : localStorage.removeItem(SESSION_KEY); } catch (e) {}
  };

  async function request(path, body, auth = true) {
    const ctrl = new AbortController();
    const timer = setTimeout(() => ctrl.abort(), TIMEOUT_MS);
    const headers = { apikey: key, 'Content-Type': 'application/json' };
    if (auth && session) headers.Authorization = `Bearer ${session.access_token}`;
    let res;
    try {
      res = await fetch(url + path, { method: 'POST', headers, body: JSON.stringify(body || {}), signal: ctrl.signal, cache: 'no-store' });
    } catch (e) {
      throw new NetworkError(e.message || 'network');
    } finally {
      clearTimeout(timer);
    }
    let data = null;
    try { data = await res.json(); } catch (e) {}
    if (!res.ok) {
      const msg = (data && (data.message || data.error_description || data.msg || data.error)) || `HTTP ${res.status}`;
      if (res.status === 401 || res.status === 403 || /JWT|not_family/i.test(msg)) throw new AuthError(msg);
      if (res.status >= 500) throw new NetworkError(msg);
      const err = new Error(msg);
      err.status = res.status;
      throw err;
    }
    return data;
  }

  function storeTokens(d) {
    saveSession({
      access_token: d.access_token,
      refresh_token: d.refresh_token,
      expires_at: d.expires_at ? d.expires_at * 1000 : Date.now() + (d.expires_in || 3600) * 1000,
      email: d.user?.email || session?.email || '',
    });
  }

  async function refresh() {
    if (!session?.refresh_token) throw new AuthError('no session');
    if (!refreshing) {
      refreshing = request('/auth/v1/token?grant_type=refresh_token', { refresh_token: session.refresh_token }, false)
        .then(storeTokens)
        .catch((e) => {
          if (!(e instanceof NetworkError)) { saveSession(null); emit(); throw new AuthError(e.message); }
          throw e;
        })
        .finally(() => { refreshing = null; });
    }
    return refreshing;
  }

  async function rpc(name, args) {
    if (!session) throw new AuthError('no session');
    if (session.expires_at - Date.now() < 120000) await refresh();
    try {
      return await request(`/rest/v1/rpc/${name}`, args);
    } catch (e) {
      if (e instanceof AuthError && session) {
        await refresh();
        return request(`/rest/v1/rpc/${name}`, args);
      }
      throw e;
    }
  }

  function cachedSummary() {
    try { return JSON.parse(localStorage.getItem(SUMMARY_KEY) || 'null'); } catch (e) { return null; }
  }

  async function sendAdd(payload) {
    return rpc('care_add_event', { p: payload });
  }

  // 큐를 순서대로 보낸다. 연결이 안 되면 멈추고 다음에 다시
  async function flush() {
    if (flushing) return flushing;
    flushing = (async () => {
      const items = await queue.all();
      for (const it of items) {
        try {
          if (it.op === 'add') {
            // 기기 안에서 이미 확인을 거쳤거나 확인할 수 없던 기록이므로 force
            await sendAdd({ ...it.payload, force: true });
          } else if (it.op === 'cancel') {
            await rpc('care_cancel_event', { p_id: it.id });
          }
          await queue.remove(it.seq);
        } catch (e) {
          if (e instanceof NetworkError || e instanceof AuthError) break;
          // 서버가 받지 않는 기록(형식 오류 등)은 버리고 콘솔에 남긴다
          console.error('dropped queued item', it, e);
          await queue.remove(it.seq);
        }
      }
      emit();
    })().finally(() => { flushing = null; });
    return flushing;
  }

  const api = {
    isConfigured: () => !!(url && key),
    isLoggedIn: () => !!session,
    email: () => session?.email || '',
    onChange(fn) { listeners.add(fn); return () => listeners.delete(fn); },

    async signIn(email, password) {
      const d = await request('/auth/v1/token?grant_type=password', { email, password }, false);
      storeTokens(d);
      emit();
    },
    signOut() { saveSession(null); emit(); },

    async pendingCount() {
      try { return (await queue.all()).length; } catch (e) { return 0; }
    },

    flush,

    // 요약 읽기. 연결이 안 되면 마지막으로 받은 요약 + 못 보낸 기록
    async getSummary() {
      let items = [];
      try { items = await queue.all(); } catch (e) {}
      if (items.length && navigator.onLine) {
        await flush().catch(() => {});
        try { items = await queue.all(); } catch (e) {}
      }
      try {
        const s = await rpc('care_summary', {});
        s._received_at = Date.now();
        try { localStorage.setItem(SUMMARY_KEY, JSON.stringify(s)); } catch (e) {}
        return { summary: applyPending(s, items), stale: false, pending: items.length };
      } catch (e) {
        if (e instanceof AuthError && !session) throw e;
        const c = cachedSummary();
        return { summary: c ? applyPending(c, items) : null, stale: true, pending: items.length, error: e };
      }
    },

    // 기록 추가.
    //   { status: 'saved', id } | { status: 'queued', id } | { status: 'confirm', existing }
    // force: 비슷한 기록이 있어도 저장
    async addEvent(ev, { force = false } = {}) {
      const payload = toPayload({ ...ev, id: ev.id || crypto.randomUUID() });
      const enqueue = async () => {
        if (!force) {
          const base = applyPending(cachedSummary(), await queue.all().catch(() => []));
          const win = base?.settings?.dup_window_minutes ?? 10;
          const dup = findLocalDuplicate(base, payload, win);
          if (dup) return { status: 'confirm', existing: dup, local: true, id: payload.id };
        }
        await queue.push({ op: 'add', id: payload.id, payload, created: Date.now() });
        emit();
        return { status: 'queued', id: payload.id };
      };
      let pending = [];
      try { pending = await queue.all(); } catch (e) {}
      if (pending.length) await flush().catch(() => {});
      try { pending = await queue.all(); } catch (e) {}
      if (!navigator.onLine || pending.length) return enqueue();
      try {
        const r = await sendAdd({ ...payload, force });
        return { ...r, id: payload.id };
      } catch (e) {
        if (e instanceof NetworkError) return enqueue();
        throw e;
      }
    },

    // 저장 직후 취소. 아직 못 보낸 기록이면 큐에서 빼기만 한다
    async cancelEvent(id) {
      const items = await queue.all().catch(() => []);
      const unsent = items.find((i) => i.op === 'add' && i.id === id);
      if (unsent) {
        await queue.remove(unsent.seq);
        emit();
        return { status: 'cancelled', id };
      }
      try {
        return await rpc('care_cancel_event', { p_id: id });
      } catch (e) {
        if (!(e instanceof NetworkError)) throw e;
        await queue.push({ op: 'cancel', id, created: Date.now() });
        emit();
        return { status: 'queued', id };
      }
    },
  };
  return api;
}
