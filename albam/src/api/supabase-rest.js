// Supabase 를 라이브러리 없이 REST 로 부른다.
//   로그인·토큰 갱신: GoTrue  POST /auth/v1/token
//   함수 호출:        PostgREST POST /rest/v1/rpc/<함수>
// 라이브러리를 안 쓰는 이유: 오프라인 캐시에 넣을 파일을 줄이고, ESP32 등으로 옮길 때 같은 HTTP 호출만 따라 하면 되게.

import { AuthError, NetworkError } from './errors.js';

const SESSION_KEY = 'albam.session';
const TIMEOUT_MS = 10000;
/** 만료 2분 전이면 미리 갱신 */
const REFRESH_MARGIN_MS = 120000;

/**
 * @typedef {Object} Session
 * @property {string} access_token
 * @property {string} refresh_token
 * @property {number} expires_at   ms
 * @property {string} email
 */

export class SupabaseRest {
  /** @param {{url: string, anonKey: string}} opts */
  constructor({ url, anonKey }) {
    this.url = (url || '').replace(/\/+$/, '');
    this.anonKey = anonKey || '';
    /** @type {Session|null} */
    this.session = readSession();
    /** 동시에 여러 번 갱신하지 않게(갱신 토큰은 한 번 쓰면 바뀜) */
    this.refreshing = null;
    /** 로그인 상태가 바뀌면 부름 */
    this.onSessionChange = () => {};
  }

  get configured() { return !!(this.url && this.anonKey); }
  get loggedIn() { return !!this.session; }

  async signIn(email, password) {
    const data = await this.post('/auth/v1/token?grant_type=password', { email, password }, false);
    this.storeTokens(data);
  }

  signOut() { this.setSession(null); }

  /** 데이터베이스 함수 부르기. 토큰이 곧 끝나면 먼저 갱신, 401이면 한 번 갱신 후 다시 */
  async rpc(name, args = {}) {
    if (!this.session) throw new AuthError('no session');
    if (this.session.expires_at - Date.now() < REFRESH_MARGIN_MS) await this.refresh();
    try {
      return await this.post(`/rest/v1/rpc/${name}`, args);
    } catch (e) {
      if (!(e instanceof AuthError) || !this.session) throw e;
      await this.refresh();
      return this.post(`/rest/v1/rpc/${name}`, args);
    }
  }

  refresh() {
    if (!this.session?.refresh_token) return Promise.reject(new AuthError('no session'));
    this.refreshing ??= this.post('/auth/v1/token?grant_type=refresh_token', { refresh_token: this.session.refresh_token }, false)
      .then((data) => this.storeTokens(data))
      .catch((e) => {
        if (e instanceof NetworkError) throw e;   // 연결 문제면 로그인은 그대로 둔다
        this.setSession(null);                    // 갱신 토큰이 무효 → 다시 로그인
        throw new AuthError(e.message);
      })
      .finally(() => { this.refreshing = null; });
    return this.refreshing;
  }

  /** POST 한 번. 오류를 AuthError / NetworkError / 그 밖의 Error 로 나눈다 */
  async post(path, body, withAuth = true) {
    const headers = { apikey: this.anonKey, 'Content-Type': 'application/json' };
    if (withAuth && this.session) headers.Authorization = `Bearer ${this.session.access_token}`;

    const ctrl = new AbortController();
    const timer = setTimeout(() => ctrl.abort(), TIMEOUT_MS);
    let res;
    try {
      res = await fetch(this.url + path, { method: 'POST', headers, body: JSON.stringify(body), signal: ctrl.signal, cache: 'no-store' });
    } catch (e) {
      throw new NetworkError(e.message || 'network');
    } finally {
      clearTimeout(timer);
    }

    const data = await res.json().catch(() => null);
    if (res.ok) return data;
    const message = data?.message || data?.error_description || data?.msg || data?.error || `HTTP ${res.status}`;
    if (res.status === 401 || res.status === 403 || /JWT|not_family/i.test(message)) throw new AuthError(message);
    if (res.status >= 500) throw new NetworkError(message);
    throw Object.assign(new Error(message), { status: res.status });
  }

  storeTokens(data) {
    this.setSession({
      access_token: data.access_token,
      refresh_token: data.refresh_token,
      expires_at: data.expires_at ? data.expires_at * 1000 : Date.now() + (data.expires_in || 3600) * 1000,
      email: data.user?.email || this.session?.email || '',
    });
  }

  setSession(session) {
    this.session = session;
    try {
      if (session) localStorage.setItem(SESSION_KEY, JSON.stringify(session));
      else localStorage.removeItem(SESSION_KEY);
    } catch (e) { /* 저장 못 해도 이번 실행 동안은 쓸 수 있음 */ }
    this.onSessionChange();
  }
}

function readSession() {
  try { return JSON.parse(localStorage.getItem(SESSION_KEY) || 'null'); } catch (e) { return null; }
}
