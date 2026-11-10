// 호출어 음성 규칙: Vosk 가 낸 결과(띄어 쓴 낱말 + 확실한 정도) → 기록 종류
import test from 'node:test';
import assert from 'node:assert/strict';
import { detectWake, WAKE_GRAMMAR, WAKE_PHRASES } from '../../src/voice-wake.js';

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
