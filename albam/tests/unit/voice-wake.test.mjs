// 호출어 음성 규칙: Vosk 가 낸 결과(띄어 쓴 낱말 + 확실한 정도) → 기록 종류
import test from 'node:test';
import assert from 'node:assert/strict';
import { detectWake, detectWakeAll, WAKE_GRAMMAR, WAKE_PHRASES } from '../../src/voice-wake.js';

const res = (pairs) => ({ text: pairs.map(([w]) => w).join(' '), result: pairs.map(([word, conf]) => ({ word, conf })) });

test('알밤이 ○○ 다섯 가지', () => {
  assert.equal(detectWake(res([['알밤', 1], ['이', 1], ['쉬', 0.9], ['야', 1], ['했어', 1]])).kind, 'pee');
  assert.equal(detectWake(res([['알밤', 1], ['이', 1], ['밥', 1], ['먹었어', 1]])).kind, 'feed');
  assert.equal(detectWake(res([['알밤', 1], ['이', 1], ['응아', 0.7]])).kind, 'poo');
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
  assert.equal(kinds('쉬(0.91) 야(0.68) 했어(0.68) 알밤(1.00) 이(1.00) 알밤(1.00) 이(1.00) 응아(1.00) 알밤(1.00) 이(1.00) 쉬(0.74) 자(0.81)'), 'poo,pee');
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
