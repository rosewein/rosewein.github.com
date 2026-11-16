// 측정 기록(체중·키): 지난번 값과 아기 생일·예정일·성별을 기기에 들고 있는다(care_measures(), supabase/014).
// 측정 창이 지난번 값에서 시작하고, 성장 백분위(src/growth.js)를 기본 나이·교정 나이로 보여 주는 데 쓴다.
// 연결이 안 되면 마지막으로 받은 것을 쓴다.

import { growthAt, formatPercentile, GROWTH_KINDS } from '../growth.js';

/**
 * @param {import('../main.js').AppContext} ctx
 * @param {string} cacheKey  기기에 둘 이름(미리 보기는 따로)
 */
export function createMeasures(ctx, cacheKey) {
  let data = null;
  try { data = JSON.parse(localStorage.getItem(cacheKey) || 'null'); } catch (e) { /* 없어도 됨 */ }
  const keep = () => { try { localStorage.setItem(cacheKey, JSON.stringify(data)); } catch (e) { /* 저장 못 해도 됨 */ } };

  /** 서버에서 다시 받는다. 실패하면 가진 것을 그대로 쓴다 */
  async function load() {
    try {
      const got = await ctx.api.getMeasures();
      if (got && Array.isArray(got.measures)) { data = got; keep(); }
    } catch (e) { /* 연결 안 됨: 지난번 것 */ }
  }

  /** 그 종류의 가장 최근 값(없으면 null) */
  function last(kind) {
    const list = (data?.measures || []).filter((m) => m.kind === kind && m.value != null);
    return list.length ? Number(list.reduce((a, b) => (new Date(b.at) >= new Date(a.at) ? b : a)).value) : null;
  }

  /** 방금 넣은 값을 바로 반영(다음에 열 때 이 값에서 시작) */
  function note(kind, value, at) {
    if (value == null) return;
    data = { baby: data?.baby ?? null, measures: [...(data?.measures || []), { kind, at: new Date(at).toISOString(), value }] };
    keep();
  }

  /** "백분위 48 · 교정 66". 성별을 모르거나 표 밖이면 '' */
  function percentileText(kind, value, at) {
    const b = data?.baby;
    if (!GROWTH_KINDS.includes(kind) || !b?.sex || value == null) return '';
    const g = growthAt({ kind, value, at, birth: b.birth_date, due: b.due_date, sex: b.sex });
    if (!g.actual) return '';
    return `백분위 ${formatPercentile(g.actual.pct)}${g.corrected ? ` · 교정 ${formatPercentile(g.corrected.pct)}` : ''}`;
  }

  return { load, last, note, percentileText };
}
