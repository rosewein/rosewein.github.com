// 호출어 음성("알밤이 ○○"): 기기 안에서 듣는 Vosk 한국어 모델(voice/README.md)의 결과를 기록 종류로 바꾸는 규칙.
// 화면·마이크와 떨어진 순수 함수라서 tests/unit/voice-wake.test.mjs 로 시험한다.
//
//   알밤이 쉬야했어 / 오줌쌌어 → 기저귀 소변
//   알밤이 밥먹었어      → 수유
//   알밤이 응아 / 똥쌌어 → 기저귀 대변
//   알밤이 기저귀        → 기저귀 소변+대변
//   알밤이 목욕했어      → 목욕(기록 종류 표의 bath)
//   알밤이 코자 / 잔다   → 잠 시작
//   알밤이 깼다 / 깼네   → 잠 끝
//
// 모델은 단어를 띄어서 낸다("알밤 이 밥 먹었어", 쉬야 → "쉬 야"). 그래서 "알밤"을 잘 알아들은 다음에 나오는
// 낱말만 보고 종류를 고른다. 모델에는 '못 알아들음'([unk]) 낱말이 없어서, 평소 말이 명령으로 바뀌지 않게
// 흔한 낱말(DISTRACTORS)을 함께 넣어 그쪽으로 빠지게 한다.

/** 모델이 듣는 말(문장 + 흔한 낱말). 모두 모델 단어장에 있는 낱말만 쓴다(없는 낱말은 Vosk 가 버린다) */
export const WAKE_PHRASES = [
  '알밤 이 쉬 야 했어', '알밤 이 밥 먹었어', '알밤 이 응아', '알밤 이 똥 쌌어', '알밤 이 기저귀', '알밤 이 목욕 했어', '알밤 이 코자', '알밤 이 깼다', '알밤 이 깼',
  '알밤 이 오줌 쌌어', '알밤 이 잔다', '알밤 이 깼 네',   // 2026-11-10 더함(깼네는 단어장에 없어 '깼 네')
];
export const DISTRACTORS = [
  '네', '아니', '그래', '엄마', '아빠', '뭐', '이거', '저거', '왜', '어', '응', '아', '오늘', '날씨', '좋다', '아기', '자',
  '먹어', '밥', '물', '이', '그', '저', '좀', '여기', '거기', '지금', '빨리', '잠깐', '괜찮아', '잠', '깨',
  // 아기 끙끙·옹알이 소리가 이쪽으로 빠지게(2026-11-10 S10 에서 끙끙 소리를 "알밤 날씨 물"로 들음).
  // '음·으·흠·흐'는 "응아"를 빼앗아 넣지 않는다
  '에', '애', '우', '오', '하', '히', '끙', '낑', '울',
  // "~ㄴ다"로 끝나는 흔한 말. 없으면 "알밤이 운다"가 "잔다"로 들린다(2026-11-10 [잘못] 2건)
  '운다', '울어', '울고', '웃는다', '웃어', '논다', '간다', '온다', '한다', '된다',
];
export const WAKE_GRAMMAR = JSON.stringify([...WAKE_PHRASES, ...DISTRACTORS]);

/**
 * 종류마다 알아듣는 말(낱말 차례). "알밤 이" 바로 다음부터 맞춰 본다.
 * 한 글자 말(똥·쉬·밥·자·깨)만으로는 기록하지 않는다. "또 울어"가 "똥"으로, 아무 말이 "자"로 들려서(2026-11-10):
 * 똥 → "똥 쌌어", 쉬 → "쉬 야 / 쉬 했어", 밥 → "밥 먹었어". 낱말 하나로 되는 말은 두 글자 이상이고 더 또렷해야(SINGLE_MIN) 한다
 */
const RULES = [
  { kind: 'both', label: '기저귀 소변+대변', says: [['기저귀']] },   // 소·대를 같이 갈았을 때는 "알밤이 기저귀"(응아·쉬를 섞어 말하면 헷갈려서)
  // '쌌어'만으로는 대변으로 보지 않는다(오줌 쌌어도 있어서)
  { kind: 'poo', label: '기저귀 대변', says: [['똥', '쌌어'], ['응아']] },
  { kind: 'pee', label: '기저귀 소변', says: [['쉬', '야'], ['쉬', '했어'], ['오줌', '쌌어'], ['오줌']] },
  { kind: 'feed', label: '수유', says: [['밥', '먹었어'], ['먹었어']] },
  { kind: 'bath', label: '목욕', says: [['목욕']] },
  { kind: 'wake', label: '잠 끝(깼어요)', says: [['깼', '네'], ['깼다'], ['깼']] },
  { kind: 'sleep', label: '잠 시작', says: [['코자'], ['잔다']] },
];
/** 낱말 하나로 되는 말 중 헷갈리기 쉬운 것(응아는 끙끙 소리, 깼은 한 글자, 먹었어는 앞말이 빠진 꼴, 오줌·잔다는 새로 넣은 말)은 이만큼 또렷해야.
 *  코자·기저귀·목욕은 길고 또렷해서 보통 기준(MIN_KEY_CONF) */
export const SINGLE_MIN = 0.8;
const STRICT_SINGLE = new Set(['응아', '먹었어', '깼', '깼다', '오줌', '잔다']);

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
 * "알밤"(0.8) 바로 뒤에 "이"가 오고, 그 **바로 다음부터** RULES 의 말이 맞아야 한다(위치로 고른다: "알밤 이 깼 쉬 야 했어"는 깼다).
 * 바로 다음 낱말이 흐리면(0.6 미만, 예: 밥을 "울"로 들음) 한 칸 더 본다. 긴 말 속에서는 한 칸 더 보지 않는다.
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
  // p 자리부터 말 하나(낱말 차례)가 맞는지. 맞으면 [규칙, 가장 흐린 낱말의 정도]
  const match = (p) => {
    for (const rule of RULES) {
      for (const say of rule.says) {
        const got = say.map((word, i) => words[p + i]).filter((w, i) => w && w.word === say[i]);
        if (got.length !== say.length) continue;
        const conf = Math.min(...got.map((w) => w.conf));
        if (conf >= (say.length === 1 && STRICT_SINGLE.has(say[0]) ? Math.max(keyMin, SINGLE_MIN) : keyMin)) return [rule, conf];
      }
    }
    return null;
  };
  let found = match(at + 2);
  if (!found && !min.long && words[at + 2] && words[at + 2].conf < MIN_KEY_CONF) found = match(at + 3);
  if (!found) return null;
  const [rule, conf] = found;
  return { kind: rule.kind, label: rule.label, conf: Math.min(words[at].conf, conf), text: res.text || words.map((w) => w.word).join(' ') };
}
