// 브라우저 시험용 가짜 Supabase. Playwright 가 https://fake.supabase.co 로 가는 요청을 가로채 대답한다.
// 규칙은 supabase/*.sql 의 함수를 간단히 흉내 낸 것이다.

const URL_BASE = 'https://fake.supabase.co';
const PASSWORD = 'pw';
const DUP_WINDOW_MS = 10 * 60000;

/** @param {import('playwright').BrowserContext} context */
export async function createFakeSupabase(context) {
  const events = [];
  const calls = [];
  let offline = false;
  let tokenNo = 0;
  let feedAmounts = [200, 230, 270];

  const live = () => events.filter((e) => !e.deleted).sort((a, b) => new Date(b.occurred_at) - new Date(a.occurred_at));

  function summary() {
    const all = live();
    const feeds = all.filter((e) => e.kind === 'feed');
    const feed = feeds[0];
    const diaper = all.find((e) => e.kind === 'diaper');
    const dayStart = new Date(); dayStart.setHours(0, 0, 0, 0);
    return {
      server_time: new Date().toISOString(),
      day_start: dayStart.toISOString(),
      last_feed: feed ? { id: feed.id, at: feed.occurred_at, ml: feed.amount_ml } : null,
      last_diaper: diaper ? { id: diaper.id, at: diaper.occurred_at, type: diaper.detail.type } : null,
      today: { feed_count: feeds.length, feed_ml: feeds.reduce((s, e) => s + (e.amount_ml || 0), 0) },
      feed_amounts: feedAmounts,
      recent: all.slice(0, 8).map((e) => ({ id: e.id, kind: e.kind, at: e.occurred_at, ml: e.amount_ml, detail: e.detail })),
      due_chores: [],
      settings: { dup_window_minutes: 10, day_start_hour: 0 },
    };
  }

  function addEvent(p) {
    if (events.some((e) => e.id === p.id)) return { status: 'saved', id: p.id, repeat: true };
    if (!p.force) {
      const dup = live().find((e) => e.kind === p.kind && Math.abs(new Date(e.occurred_at) - new Date(p.occurred_at)) <= DUP_WINDOW_MS);
      if (dup) return { status: 'confirm', existing: { id: dup.id, kind: dup.kind, at: dup.occurred_at, ml: dup.amount_ml, detail: dup.detail } };
    }
    events.push({ ...p });
    return { status: 'saved', id: p.id };
  }

  await context.route(`${URL_BASE}/**`, async (route) => {
    if (offline) return route.abort('internetdisconnected');
    const req = route.request();
    const url = new URL(req.url());
    const body = req.postDataJSON() || {};
    calls.push(url.pathname + url.search);
    const reply = (status, json) => route.fulfill({ status, contentType: 'application/json', body: JSON.stringify(json) });

    if (url.pathname === '/auth/v1/token') {
      if (url.searchParams.get('grant_type') === 'password' && body.password !== PASSWORD) {
        return reply(400, { error_description: 'Invalid login credentials' });
      }
      tokenNo += 1;
      return reply(200, { access_token: `at${tokenNo}`, refresh_token: `rt${tokenNo}`, expires_in: 3600, user: { email: body.email || 'izzy@example.com' } });
    }
    if (!/^Bearer at\d+$/.test(req.headers().authorization || '')) return reply(401, { message: 'JWT expired' });

    switch (url.pathname) {
      case '/rest/v1/rpc/care_summary': return reply(200, summary());
      case '/rest/v1/rpc/care_add_event': return reply(200, addEvent(body.p));
      case '/rest/v1/rpc/care_stats': {
        const days = [];
        for (let i = (body.p_days || 7) - 1; i >= 0; i -= 1) {
          const d = new Date(); d.setHours(0, 0, 0, 0); d.setDate(d.getDate() - i);
          days.push({ day: d.toISOString().slice(0, 10), feed_count: 4, feed_ml: 800, diaper_total: 6, diaper_pee: 4, diaper_poo: 1, diaper_both: 1, sleep_min: 660, from_history: true });
        }
        return reply(200, days);
      }
      case '/rest/v1/rpc/care_set_feed_amounts':
        feedAmounts = [...new Set(body.p_amounts)].sort((a, b) => a - b);
        return reply(200, { status: 'saved', feed_amounts: feedAmounts });
      case '/rest/v1/rpc/care_cancel_event': {
        const e = events.find((x) => x.id === body.p_id);
        if (e) e.deleted = true;
        return reply(200, { status: e ? 'cancelled' : 'not_found', id: body.p_id });
      }
      default: return reply(404, { message: 'not found' });
    }
  });

  return {
    url: URL_BASE,
    password: PASSWORD,
    events,
    calls,
    get feedAmounts() { return feedAmounts; },
    async goOffline() { offline = true; await context.setOffline(true); },
    async goOnline() { offline = false; await context.setOffline(false); },
  };
}
