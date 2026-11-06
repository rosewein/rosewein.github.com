// 음성 인식 결과(한국어 문장)를 기록 하나로 바꾸는 규칙.
// 화면·통신과 떨어진 순수 함수라서 tests/voice-parse.test.mjs 로 시험한다.
//
// parseUtterance('수유 160 20분 전', new Date())
//   → { ok: true, event: { kind: 'feed', amount_ml: 160, occurred_at: Date }, label: '수유 160ml · 20분 전' }
// 못 알아들으면 { ok: false, reason }

const SINO_DIGIT = { 일: 1, 이: 2, 삼: 3, 사: 4, 오: 5, 육: 6, 륙: 6, 칠: 7, 팔: 8, 구: 9 };
const SINO_CHARS = '일이삼사오육륙칠팔구십백천';
const SINO_RE = new RegExp(`^(?:([이삼사오육륙칠팔구])?천)?(?:([이삼사오육륙칠팔구])?백)?(?:([이삼사오육륙칠팔구])?십)?([일이삼사오육륙칠팔구])?$`);
const NATIVE = [
  ['열두', 12], ['열한', 11], ['열', 10], ['아홉', 9], ['여덟', 8], ['일곱', 7], ['여섯', 6],
  ['다섯', 5], ['네', 4], ['세', 3], ['두', 2], ['한', 1],
];

// "백육십" → 160. 수사가 아니면 null
export function sinoToInt(s) {
  s = s.replace(/\s+/g, '');
  if (!s) return null;
  const m = s.match(SINO_RE);
  if (!m) return null;
  const d = (c, dflt) => (c ? SINO_DIGIT[c] : dflt);
  let n = 0;
  if (s.includes('천')) n += d(m[1], 1) * 1000;
  if (s.includes('백')) n += d(m[2], 1) * 100;
  if (s.includes('십')) n += d(m[3], 1) * 10;
  if (m[4]) n += SINO_DIGIT[m[4]];
  return n;
}

const UNIT_AFTER = /^\s*(시간|시|분|ml)/;

// 한글 수사·단위 말투를 숫자와 정해진 꼴로 바꾼다
export function normalize(text) {
  let t = ` ${String(text || '')} `
    .toLowerCase()
    .replace(/[.,!?~"'“”‘’]/g, ' ')
    .replace(/(밀리\s*리터|밀리리터|밀리|미리|씨씨|cc|㎖|mL|ml)/gi, 'ml');
  // 고유어 시각·시간: "한 시", "두시간"
  for (const [w, n] of NATIVE) {
    t = t.replace(new RegExp(`(^|[^가-힣])${w}\\s*(?=시)`, 'g'), `$1${n}`);
  }
  // 띄어 말한 수사 붙이기: "백 육십" → "백육십"
  // (뒤 덩어리에 시·분이 붙으면 따로 둔다: "이백 이십 분 전")
  t = t.replace(new RegExp(`(^|[^가-힣])([${SINO_CHARS}]+)\\s+(?=[${SINO_CHARS}]+(?![${SINO_CHARS}])(?!\\s*(?:시간|시|분))(?:[^가-힣]|ml|$))`, 'g'), '$1$2');
  // 한자어 수사 → 숫자. 십·백·천이 들어 있거나 바로 뒤에 단위가 올 때만
  t = t.replace(new RegExp(`(^|[^가-힣])([${SINO_CHARS}]+)(?=([^가-힣]|시간|시|분|ml|$))`, 'g'), (all, pre, run, _n, off, str) => {
    const after = str.slice(off + all.length);
    const n = sinoToInt(run);
    if (n == null) return all;
    if (/[십백천]/.test(run) || UNIT_AFTER.test(after)) return `${pre}${n}`;
    return all;
  });
  // 숫자와 단위 사이 띄움 정리, "1시 반"
  t = t
    .replace(/(\d+)\s*(시간|시|분|ml)/g, '$1$2')
    .replace(/(\d+)시간\s*반/g, (a, h) => `${h}시간30분`)
    .replace(/(\d+)시\s*반/g, '$1시30분')
    .replace(/\s+/g, ' ')
    .trim();
  return t;
}

const pad = (n) => String(n).padStart(2, '0');
const hhmm = (d) => `${pad(d.getHours())}:${pad(d.getMinutes())}`;

// 말한 시각(시·분, 오전/오후 같은 말)을, 기준 시각 이전 가장 가까운 실제 시각으로
function resolveClock(h, m, period, ref) {
  const cands = [];
  if (period === 'am') cands.push(h % 12);
  else if (period === 'pm') cands.push((h % 12) + 12);
  else if (period === 'night') cands.push(h >= 6 && h < 12 ? h + 12 : h % 12 === 0 ? 0 : h);
  else if (h >= 13 || h === 0) cands.push(h % 24);
  else cands.push(h % 12, (h % 12) + 12);
  let best = null;
  for (const hh of cands) {
    for (let back = 0; back <= 1; back++) {
      const d = new Date(ref);
      d.setDate(d.getDate() - back);
      d.setHours(hh, m, 0, 0);
      if (d <= ref && (!best || d > best)) best = d;
    }
  }
  return best;
}

function periodOf(word) {
  if (!word) return null;
  if (/오전|새벽|아침/.test(word)) return 'am';
  if (/오후|저녁|낮/.test(word)) return 'pm';
  if (/밤/.test(word)) return 'night';
  return null;
}

const CLOCK = '(오전|오후|새벽|아침|저녁|낮|밤)?\\s*(\\d{1,2})시(?:\\s*(\\d{1,2})분)?';

// "20분 전", "1시간 전", "1시간30분 전", "3시 10분에"
function parseWhen(t, now) {
  let m = t.match(/(?:(\d+)시간)?\s*(?:(\d+)분)?\s*전/);
  if (m && (m[1] || m[2])) {
    const mins = (+m[1] || 0) * 60 + (+m[2] || 0);
    return { at: new Date(now.getTime() - mins * 60000), rel: mins, span: m[0] };
  }
  m = t.match(new RegExp(CLOCK + '\\s*(?:에|쯤)?'));
  if (m && !/부터|까지/.test(t)) {
    const at = resolveClock(+m[2], +(m[3] || 0), periodOf(m[1]), now);
    if (at) return { at, rel: Math.round((now - at) / 60000), span: m[0] };
  }
  return { at: now, rel: 0, span: '' };
}

function whenLabel(w) {
  if (!w.rel) return '지금';
  if (w.rel < 60) return `${w.rel}분 전`;
  if (w.rel < 180 && w.rel % 60) return `${Math.floor(w.rel / 60)}시간 ${w.rel % 60}분 전`;
  return hhmm(w.at);
}

const DIAPER_LABEL = { pee: '소변', poo: '대변', both: '소변+대변' };

export function parseUtterance(text, now = new Date()) {
  const raw = String(text || '').trim();
  if (!raw) return { ok: false, reason: 'empty' };
  const t = normalize(raw);

  // 수면: "잠 1시 10분부터 2시 40분까지"
  if (/잠|수면|잤|재웠|자기/.test(t)) {
    const re = new RegExp(`${CLOCK}\\s*부터\\s*${CLOCK}\\s*까지`);
    const m = t.match(re);
    if (m) {
      const endP = periodOf(m[4]) || periodOf(m[1]);
      const end = resolveClock(+m[5], +(m[6] || 0), endP, now);
      const startP = periodOf(m[1]);
      const start = end && resolveClock(+m[2], +(m[3] || 0), startP, new Date(end.getTime() - 1));
      if (start && end && end - start <= 16 * 3600000) {
        return {
          ok: true,
          event: { kind: 'sleep', occurred_at: start, ended_at: end, detail: {} },
          label: `잠 ${hhmm(start)}~${hhmm(end)}`,
        };
      }
    }
    if (!/수유|분유|기저귀|먹/.test(t)) return { ok: false, reason: 'sleep_needs_range' };
  }

  // 기저귀
  const pee = /소변|쉬야|(^|\s)쉬(\s|했|$)|오줌/.test(t);
  const both = /둘\s*다|다\s*했|소변\s*대변|대변\s*소변/.test(t) || (pee && /대변|응가|똥/.test(t));
  if (/기저귀/.test(t) || /소변|대변|응가|오줌/.test(t)) {
    const type = both ? 'both' : /대변|응가|똥/.test(t) ? 'poo' : pee ? 'pee' : null;
    if (!type) return { ok: false, reason: 'diaper_type' };
    const w = parseWhen(t, now);
    return {
      ok: true,
      event: { kind: 'diaper', occurred_at: w.at, detail: { type } },
      label: `기저귀 ${DIAPER_LABEL[type]} · ${whenLabel(w)}`,
    };
  }

  // 수유: "수유 160", "160 먹였어", "분유 백육십 이십 분 전"
  if (/수유|분유|먹였|먹었|먹음|맘마|ml/.test(t)) {
    const w = parseWhen(t, now);
    const rest = w.span ? t.replace(w.span, ' ') : t;
    const nums = [...rest.matchAll(/(\d+)(?!\d)(?!\s*(?:시간|시|분))/g)].map((x) => +x[1]);
    const ml = nums.find((n) => n >= 10 && n <= 500);
    if (!ml) return { ok: false, reason: 'feed_amount' };
    return {
      ok: true,
      event: { kind: 'feed', amount_ml: ml, occurred_at: w.at, detail: {} },
      label: `수유 ${ml}ml · ${whenLabel(w)}`,
    };
  }

  return { ok: false, reason: 'unknown' };
}
