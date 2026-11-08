// 설정 읽기. 값의 뜻은 ../config.js 에 적혀 있다.
// ../config.js 는 빌드 없이 고칠 수 있게 일반 <script> 로 읽어 window.ALBAM_CONFIG 에 둔다.
// Supabase 주소·키만은 기기에서 직접 넣을 수 있어서(로그인 화면) localStorage 값이 있으면 그것을 쓴다.

import { APTAMIL, BREZZA } from './formula.js';

const CONNECTION_KEY = 'albam.config';

/** config.js 에 값이 빠졌을 때 쓰는 기본값 */
const DEFAULTS = {
  supabaseUrl: '',
  supabaseAnonKey: '',
  nightStartHour: 21,
  nightEndHour: 6,
  nightWakeSeconds: 30,
  undoSeconds: 6,
  voiceConfirmSeconds: 4,
  pollSeconds: 20,
  shiftMinutes: 3,
  hungryMinutes: 'auto',
  diaperMinutes: 180,
  awakeMinutes: 120,
  defaultAmounts: [200, 230, 270],
  formula: APTAMIL,
  machine: BREZZA,
  dailyReloadHour: 4,
  statsDays: 7,
  statsIdleSeconds: 60,
  theme: 'auto',
  location: { lat: 37.5665, lon: 126.978 },
};

/** @typedef {typeof DEFAULTS} Config */

/** @returns {Config} */
export function loadConfig() {
  const cfg = { ...DEFAULTS, ...(window.ALBAM_CONFIG || {}) };
  const local = readLocalConnection();
  if (local.supabaseUrl) cfg.supabaseUrl = local.supabaseUrl;
  if (local.supabaseAnonKey) cfg.supabaseAnonKey = local.supabaseAnonKey;
  return cfg;
}

/** 로그인 화면에서 넣은 Supabase 주소·키를 이 기기에 저장 */
export function saveLocalConnection(supabaseUrl, supabaseAnonKey) {
  localStorage.setItem(CONNECTION_KEY, JSON.stringify({ supabaseUrl, supabaseAnonKey }));
}

function readLocalConnection() {
  try { return JSON.parse(localStorage.getItem(CONNECTION_KEY) || '{}'); } catch (e) { return {}; }
}
