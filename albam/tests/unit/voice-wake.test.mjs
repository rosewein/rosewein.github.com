// 호출어 음성 규칙: Vosk 가 낸 결과(띄어 쓴 낱말 + 확실한 정도) → 기록 종류
import test from 'node:test';
import assert from 'node:assert/strict';
import { detectWake, detectWakeAll, WAKE_GRAMMAR, WAKE_PHRASES } from '../../src/voice-wake.js';

const res = (pairs) => ({ text: pairs.map(([w]) => w).join(' '), result: pairs.map(([word, conf]) => ({ word, conf })) });

test('알밤이 ○○ 다섯 가지', () => {
  assert.equal(detectWake(res([['알밤', 1], ['이', 1], ['쉬', 0.9], ['야', 1], ['했어', 1]])).kind, 'pee');
  assert.equal(detectWake(res([['알밤', 1], ['이', 1], ['밥', 1], ['먹었어', 1]])).kind, 'feed');
  assert.equal(detectWake(res([['알밤', 1], ['이', 1], ['응아', 0.85]])).kind, 'poo');
  assert.equal(detectWake(res([['알밤', 1], ['이', 1], ['응아', 0.65], ['자', 0.67]])), null, '흐린 응아는 넘김(대변으로 잡아 [잘못]이 눌렸음)');
  assert.equal(detectWake(res([['알밤', 1], ['이', 1], ['똥', 1], ['쌌어', 1]])).kind, 'poo');
  assert.equal(detectWake(res([['알밤', 1], ['이', 1], ['코자', 1]])).kind, 'sleep');
  assert.equal(detectWake(res([['알밤', 1], ['이', 1], ['깼다', 0.9]])).kind, 'wake');
});

test('실제 모델이 낸 결과(합성 음성): 소변을 "저 이 여기 야 했어"로 들어도 "쉬"가 없으면 넘기지 않음', () => {
  assert.equal(detectWake(res([['알밤', 1], ['이', 0.95], ['저', 0.79], ['이', 1], ['여기', 0.93], ['야', 1], ['했어', 1]])), null);
  assert.equal(detectWake(res([['알밤', 1], ['이', 1], ['응아', 0.48], ['야', 0.58]])), null, '종류 낱말이 흐리면 넘김');
});

test('알밤이 없거나 흐리면, 평소 말은 명령이 아님', () => {
  assert.equal(detectWake(res([['먹었어', 1]])), null);
  assert.equal(detectWake(res([['응', 0.46], ['이', 0.63], ['아기', 0.67], ['좀', 0.6], ['자', 0.96]])), null);
  assert.equal(detectWake(res([['알밤', 0.5], ['이', 1], ['밥', 1]])), null);
  assert.equal(detectWake({ text: '' }), null);
});

test('문법 목록', () => {
  const g = JSON.parse(WAKE_GRAMMAR);
  assert.ok(WAKE_PHRASES.every((p) => g.includes(p)) && g.includes('아니'));
  assert.ok(!g.some((w) => /알밤이|쉬야|깼어/.test(w)), '모델 단어장에 없는 낱말은 쓰지 않음');
});

test('이어서 말한 여러 문장(S10 실제 기록 2026-11-10)', () => {
  const parse = (s) => res(s.split(' ').map((x) => { const m = x.match(/^(.+)\((\d\.\d+)\)$/); return [m[1], Number(m[2])]; }));
  const kinds = (s) => detectWakeAll(parse(s)).map((h) => h.kind).join(',');
  assert.equal(kinds('쉬(0.91) 야(0.68) 했어(0.68) 알밤(1.00) 이(1.00) 알밤(1.00) 이(1.00) 응아(1.00) 알밤(1.00) 이(1.00) 쉬(0.74) 자(0.81)'), 'poo', '"쉬 자"는 소변 문장(쉬 야 / 쉬 했어)이 아님');
  assert.equal(kinds('알밤(1.00) 알밤(1.00) 이(1.00) 아빠(0.91) 알밤(1.00) 이(0.82) 쌌어(0.81)'), 'poo', '알밤에서 멀리 떨어진 쌌어도 문장마다 끊으면 잡힘');
  assert.equal(kinds('알밤(1.00) 이(1.00) 쉬(1.00) 야(0.44) 알밤(1.00) 이(0.87) 쉬(1.00) 야(1.00) 알밤(1.00) 이(1.00) 이(1.00) 쉬(1.00) 자(0.63)'), 'pee', '같은 말 되풀이는 한 번');
  assert.equal(kinds('야(0.35) 알밤(1.00) 이(1.00) 밥(1.00) 먹었어(1.00)'), 'feed');
  assert.equal(kinds('알밤(1.00) 이(1.00) 이(1.00)'), '');
});

test('아기 끙끙 소리: "알밤" 뒤에 "이"가 없으면 부른 게 아님', () => {
  assert.equal(detectWake(res([['알밤', 1], ['날씨', 1], ['물', 1]])), null);
  assert.equal(detectWake(res([['알밤', 1], ['응아', 1]])), null, '"알밤 응아"(이 없음)도 넘김');
  assert.equal(detectWake(res([['알밤', 1], ['이', 1], ['끙', 1], ['에', 1], ['어', 1], ['응아', 1]])), null, '"알밤 이" 뒤 세 낱말 안에만');
  assert.ok(!JSON.parse(WAKE_GRAMMAR).includes('으'), '"응아"와 비슷한 소리는 넣지 않음');
  assert.ok(JSON.parse(WAKE_GRAMMAR).includes('끙'));
});

test('알밤이 기저귀 = 소변+대변', () => {
  assert.equal(detectWake(res([['알밤', 1], ['이', 1], ['기저귀', 1]])).kind, 'both');
  assert.equal(detectWake(res([['알밤', 1], ['이', 1], ['응아', 1], ['에', 1], ['쉬', 1]])).kind, 'poo', '응아·쉬를 섞어 말하면 앞의 것(대변)만');
});

test('알밤이 목욕했어 = 목욕', () => {
  assert.equal(detectWake(res([['알밤', 1], ['이', 1], ['목욕', 1], ['했어', 1]])).kind, 'bath');
});

test('시험 밖의 말(남편 시험 2026-11-10 21:06~21:15): 긴 말 속 우연한 조각은 넘김', () => {
  const parse = (s) => res(s.split(' ').map((x) => { const m = x.match(/^(.+)\((\d\.\d+)\)$/); return [m[1], Number(m[2])]; }));
  const kinds = (s) => detectWakeAll(parse(s)).map((h) => h.kind).join(',');
  // "알밤 이 깼(흐림) 왜 기저귀"를 소+대로 잡았었다
  assert.equal(kinds('애(0.49) 그래(1.00) 아빠(0.91) 이(0.82) 알밤(1.00) 이(0.78) 깼(0.51) 왜(1.00) 기저귀(1.00) 쉬(0.89) 어(0.80) 알밤(1.00) 이(1.00) 알밤(1.00) 거기(1.00) 엄마(0.33) 울(0.33) 지금(0.51) 목욕(1.00) 이(1.00) 쉬(0.80) 낑(0.36) 했어(1.00) 오(0.42)'), '');
  // "알밤 이 쉬(흐림) 목욕"을 목욕으로 잡았었다. 앞의 "알밤 이 똥 쌌어"(또렷)는 남김
  assert.equal(kinds('깼(1.00) 좋다(1.00) 했어(1.00) 알밤(1.00) 이(1.00) 똥(1.00) 쌌어(1.00) 오(1.00) 빨리(1.00) 이(1.00) 에(1.00) 알밤(1.00) 목욕(1.00) 했어(1.00) 오(0.87) 울(0.57) 알밤(1.00) 이(0.79) 알밤(1.00) 이(1.00) 쉬(0.52) 목욕(1.00) 오(0.83) 좀(0.78)'), 'poo');
  // "알밤 이 똥(흐림) 어 목욕"을 목욕으로 잡았었다. 맨 앞 "알밤 이 기저귀"(또렷)는 남김
  assert.equal(kinds('알밤(1.00) 이(1.00) 기저귀(1.00) 기저귀(1.00) 목욕(1.00) 했어(1.00) 목욕(0.52) 이(0.62) 목욕(1.00) 오(0.88) 네(0.91) 깨(1.00) 야(0.57) 알밤(1.00) 이(1.00) 똥(0.54) 어(0.61) 목욕(1.00) 하(0.92)'), 'both');
});

test('위치로 고름: "알밤 이" 바로 다음 낱말', () => {
  // 깼어를 말했는데 소변으로 잡혀 [잘못]이 눌렸던 기록
  assert.equal(detectWake(res([['알밤', 1], ['이', 1], ['깼', 0.94], ['쉬', 0.74], ['야', 0.74], ['했어', 0.74]])).kind, 'wake');
  assert.equal(detectWake(res([['알밤', 1], ['이', 0.58], ['울', 0.39], ['먹었어', 1]])).kind, 'feed', '바로 다음이 흐리면 한 칸 더');
  assert.equal(detectWake(res([['알밤', 1], ['이', 1], ['아빠', 0.91], ['쌌어', 1]])), null, '바로 다음이 또렷한 다른 낱말이면 넘김');
});

test('한 글자 말만으로는 기록 안 함("또 울어"가 "똥"으로 들림, 2026-11-10 [잘못] 기록)', () => {
  const parse = (s) => res(s.split(' ').map((x) => { const m = x.match(/^(.+)\((\d\.\d+)\)$/); return [m[1], Number(m[2])]; }));
  const kinds = (s) => detectWakeAll(parse(s)).map((h) => h.kind).join(',');
  assert.equal(kinds('알밤(1.00) 이(1.00) 똥(1.00) 알밤(1.00)'), '');
  assert.equal(kinds('이(0.62) 쉬(1.00) 자(1.00) 알밤(1.00) 이(1.00) 똥(1.00)'), '');
  assert.equal(kinds('알밤(1.00) 이(1.00) 자(1.00) 똥(1.00) 쌌어(1.00)'), '', '"자"는 잠이 아님(코자만)');
  assert.equal(kinds('알밤(1.00) 이(0.75) 똥(1.00) 쌌어(1.00)'), 'poo', '"똥 쌌어"는 대변');
  assert.equal(kinds('알밤(1.00) 이(1.00) 코자(0.69)'), 'sleep', '코자는 길고 또렷해서 보통 기준');
  assert.equal(kinds('알밤(1.00) 이(1.00) 쉬(1.00) 야(0.79) 지금(1.00) 알밤(1.00) 어(0.82)'), 'pee');
});
