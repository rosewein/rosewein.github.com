// 호출어 음성("알밤이 ○○"): 기기 안에서 듣는 Vosk 한국어 모델(voice/README.md)의 결과를 기록 종류로 바꾸는 규칙.
// 화면·마이크와 떨어진 순수 함수라서 tests/unit/voice-wake.test.mjs 로 시험한다.
//
//   알밤이 쉬야했어      → 기저귀 소변
//   알밤이 밥먹었어      → 수유
//   알밤이 응아 / 똥쌌어 → 기저귀 대변
//   알밤이 기저귀        → 기저귀 소변+대변
//   알밤이 목욕했어      → 목욕(기록 종류 표의 bath)
//   알밤이 코자          → 잠 시작
//   알밤이 깼다          → 잠 끝
//
// 모델은 단어를 띄어서 낸다("알밤 이 밥 먹었어", 쉬야 → "쉬 야"). 그래서 "알밤"을 잘 알아들은 다음에 나오는
// 낱말만 보고 종류를 고른다. 모델에는 '못 알아들음'([unk]) 낱말이 없어서, 평소 말이 명령으로 바뀌지 않게
// 흔한 낱말(DISTRACTORS)을 함께 넣어 그쪽으로 빠지게 한다.

/** 모델이 듣는 말(문장 + 흔한 낱말). 모두 모델 단어장에 있는 낱말만 쓴다(없는 낱말은 Vosk 가 버린다) */
export const WAKE_PHRASES = [
  '알밤 이 쉬 야 했어', '알밤 이 밥 먹었어', '알밤 이 응아', '알밤 이 똥 쌌어', '알밤 이 기저귀', '알밤 이 목욕 했어', '알밤 이 코자', '알밤 이 깼다', '알밤 이 깼',
];
export const DISTRACTORS = [
  '네', '아니', '그래', '엄마', '아빠', '뭐', '이거', '저거', '왜', '어', '응', '아', '오늘', '날씨', '좋다', '아기', '자',
  '먹어', '밥', '물', '이', '그', '저', '좀', '여기', '거기', '지금', '빨리', '잠깐', '괜찮아', '잠', '깨',
  // 아기 끙끙·옹알이 소리가 이쪽으로 빠지게(2026-11-10 S10 에서 끙끙 소리를 "알밤 날씨 물"로 들음).
  // '음·으·흠·흐'는 "응아"를 빼앗아 넣지 않는다
  '에', '애', '우', '오', '하', '히', '끙', '낑', '울',
];
export const WAKE_GRAMMAR = JSON.stringify([...WAKE_PHRASES, ...DISTRACTORS]);

/** 종류를 고르는 낱말(알밤 뒤에 나와야 한다). 앞의 것부터 본다: "똥 쌌어"는 대변, "쉬"는 소변 */
const RULES = [
  { kind: 'both', words: ['기저귀'], label: '기저귀 소변+대변' },   // 소·대를 같이 갈았을 때는 "알밤이 기저귀"(응아·쉬를 섞어 말하면 헷갈려서)
  { kind: 'poo', words: ['응아', '똥', '쌌어'], label: '기저귀 대변' },
  { kind: 'pee', words: ['쉬'], label: '기저귀 소변' },
  { kind: 'feed', words: ['밥', '먹었어'], label: '수유' },
  { kind: 'bath', words: ['목욕'], label: '목욕' },
  { kind: 'wake', words: ['깼다', '깼', '깨'], label: '잠 끝(깼어요)' },
  { kind: 'sleep', words: ['코자', '잠', '자'], label: '잠 시작' },
];

/** "알밤"이 이만큼 확실해야 호출로 본다 */
export const MIN_ANCHOR_CONF = 0.8;
/** 종류 낱말은 이만큼 */
export const MIN_KEY_CONF = 0.6;
/**
 * 결과 낱말이 이보다 많으면 '긴 말'(대화·TV·울음이 이어져 모델이 끊지 못함)로 본다.
 * 모델은 모르는 말도 아는 낱말로 끼워 맞춰서, 긴 말 속에 "알밤 이 … 목욕" 같은 조각이 우연히 생긴다(2026-11-10).
 * 긴 말에서는 "알밤 이" 바로 다음 낱말만, 더 확실할 때만 받는다
 */
export const LONG_RESULT_WORDS = 12;
const LONG_MIN = { anchor: 0.9, glue: 0.8, key: 0.9 };

/** 낱말 → 종류 */
const KIND_OF = new Map(RULES.flatMap((r) => r.words.map((w) => [w, r])));

/**
 * Vosk 결과 하나 → 알아들은 명령 모두. 이어서 말하면 결과 하나에 여러 문장이 붙어 온다
 * ("알밤 이 쉬 야 했어 알밤 이 응아"). "알밤"마다 끊어 문장마다 판정한다. 바로 이어진 같은 종류는 하나로 친다(되풀이).
 * @param {{text?: string, result?: {word: string, conf: number}[]}} res
 * @param {{anchor?: number, key?: number}} [min]
 * @returns {{kind: string, label: string, conf: number, text: string}[]}
 */
export function detectWakeAll(res, min = {}) {
  const words = toWords(res);
  const long = words.length > LONG_RESULT_WORDS;
  const starts = words.map((w, i) => (w.word === '알밤' ? i : -1)).filter((i) => i >= 0);
  const hits = [];
  starts.forEach((s, n) => {
    const seg = words.slice(s, starts[n + 1] ?? words.length);
    // "알밤 알밤 이 …"처럼 알밤만 되풀이한 조각은 다음 조각과 합친다
    if (seg.length === 1 && starts[n + 1] === s + 1) return;
    const hit = detectWake({ text: seg.map((w) => w.word).join(' '), result: seg }, long ? { ...LONG_MIN, long } : min);
    if (hit && hits.at(-1)?.kind !== hit.kind) hits.push(hit);
  });
  return hits;
}

const toWords = (res) => (res?.result?.length ? res.result
  : (res?.text || '').split(/\s+/).filter(Boolean).map((word) => ({ word, conf: 1 })));

/**
 * Vosk 결과 하나 → 알아들은 명령(없으면 null). 결과에 문장이 여럿이면 detectWakeAll.
 * "알밤"(0.8) 바로 뒤에 "이"가 오고, 그 **바로 다음 낱말**이 종류 낱말이어야 한다(위치로 고른다: "알밤 이 깼 쉬 야 했어"는 깼다).
 * 그 낱말이 흐리면(0.6 미만, 예: 밥을 "울"로 들음) 한 칸 더 본다. 긴 말 속에서는 한 칸 더 보지 않는다.
 * @param {{text?: string, result?: {word: string, conf: number}[]}} res  recognizer 의 "result" 메시지 result
 * @param {{anchor?: number, glue?: number, key?: number, long?: boolean}} [min]
 * @returns {{kind: 'pee'|'poo'|'both'|'feed'|'bath'|'sleep'|'wake', label: string, conf: number, text: string} | null}
 */
export function detectWake(res, min = {}) {
  const anchorMin = min.anchor ?? MIN_ANCHOR_CONF;
  const glueMin = min.glue ?? 0;
  const keyMin = min.key ?? MIN_KEY_CONF;
  const words = toWords(res);
  // "알밤" 바로 뒤에 "이"가 와야 부른 것으로 본다(끙끙 소리가 "알밤 날씨 물"처럼 들린 적이 있다)
  const at = words.findIndex((w, i) => w.word === '알밤' && w.conf >= anchorMin && words[i + 1]?.word === '이' && words[i + 1].conf >= glueMin);
  if (at < 0) return null;
  const pick = (w) => (w && KIND_OF.has(w.word) && w.conf >= keyMin ? w : null);
  let hit = pick(words[at + 2]);
  if (!hit && !min.long && words[at + 2] && words[at + 2].conf < MIN_KEY_CONF) hit = pick(words[at + 3]);
  if (!hit) return null;
  const rule = KIND_OF.get(hit.word);
  return { kind: rule.kind, label: rule.label, conf: Math.min(words[at].conf, hit.conf), text: res.text || words.map((w) => w.word).join(' ') };
}
