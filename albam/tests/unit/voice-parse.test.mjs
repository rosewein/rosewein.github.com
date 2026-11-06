// 음성 규칙 시험 (npm test)
import test from 'node:test';
import assert from 'node:assert/strict';
import { parseUtterance, sinoToInt, normalize } from '../../src/voice-parse.js';

// 기준 시각: 2026-11-06 15:00 (기기 시간대 기준)
const NOW = new Date(2026, 10, 6, 15, 0, 0);
const at = (h, m, dayOffset = 0) => new Date(2026, 10, 6 + dayOffset, h, m, 0).getTime();
const mins = (n) => NOW.getTime() - n * 60000;

test('한자어 수사', () => {
  assert.equal(sinoToInt('백육십'), 160);
  assert.equal(sinoToInt('이백'), 200);
  assert.equal(sinoToInt('백'), 100);
  assert.equal(sinoToInt('구십'), 90);
  assert.equal(sinoToInt('백이십오'), 125);
  assert.equal(sinoToInt('삼십'), 30);
  assert.equal(sinoToInt('오'), 5);
  assert.equal(sinoToInt('후'), null);
  assert.equal(sinoToInt('백백'), null);
});

test('정규화', () => {
  assert.equal(normalize('수유 백 육십 밀리'), '수유 160ml');
  assert.equal(normalize('이십 분 전'), '20분 전');
  assert.equal(normalize('한 시 반'), '1시30분');
  assert.equal(normalize('오후 두 시'), '오후 2시');
  assert.equal(normalize('수유 이백 이십 분 전'), '수유 200 20분 전');
});

const cases = [
  ['수유 160', { kind: 'feed', amount_ml: 160, at: NOW.getTime() }],
  ['160 먹였어', { kind: 'feed', amount_ml: 160, at: NOW.getTime() }],
  ['수유 160ml', { kind: 'feed', amount_ml: 160, at: NOW.getTime() }],
  ['수유 백육십', { kind: 'feed', amount_ml: 160, at: NOW.getTime() }],
  ['수유 백 육십', { kind: 'feed', amount_ml: 160, at: NOW.getTime() }],
  ['분유 이백 먹였어', { kind: 'feed', amount_ml: 200, at: NOW.getTime() }],
  ['수유 160 20분 전', { kind: 'feed', amount_ml: 160, at: mins(20) }],
  ['수유 백육십 이십 분 전', { kind: 'feed', amount_ml: 160, at: mins(20) }],
  ['20분 전에 160 먹였어', { kind: 'feed', amount_ml: 160, at: mins(20) }],
  ['수유 120 한 시간 전', { kind: 'feed', amount_ml: 120, at: mins(60) }],
  ['수유 120 1시간 반 전', { kind: 'feed', amount_ml: 120, at: mins(90) }],
  ['수유 140 2시 10분에', { kind: 'feed', amount_ml: 140, at: at(14, 10) }],
  ['기저귀 대변', { kind: 'diaper', type: 'poo', at: NOW.getTime() }],
  ['기저귀 소변', { kind: 'diaper', type: 'pee', at: NOW.getTime() }],
  ['기저귀 응가', { kind: 'diaper', type: 'poo', at: NOW.getTime() }],
  ['기저귀 쉬', { kind: 'diaper', type: 'pee', at: NOW.getTime() }],
  ['기저귀 둘 다', { kind: 'diaper', type: 'both', at: NOW.getTime() }],
  ['기저귀 소변 대변', { kind: 'diaper', type: 'both', at: NOW.getTime() }],
  ['기저귀 대변 10분 전', { kind: 'diaper', type: 'poo', at: mins(10) }],
  ['대변 기저귀 갈았어', { kind: 'diaper', type: 'poo', at: NOW.getTime() }],
  ['잠 1시 10분부터 2시 40분까지', { kind: 'sleep', at: at(13, 10), end: at(14, 40) }],
  ['잠 한 시 십 분부터 두 시 사십 분까지', { kind: 'sleep', at: at(13, 10), end: at(14, 40) }],
  ['낮잠 12시부터 1시 반까지', { kind: 'sleep', at: at(12, 0), end: at(13, 30) }],
  ['잠 11시부터 2시까지', { kind: 'sleep', at: at(11, 0), end: at(14, 0) }],
  ['밤잠 밤 9시부터 새벽 3시까지', { kind: 'sleep', at: at(21, 0, -1), end: at(3, 0) }],
];

for (const [text, want] of cases) {
  test(`"${text}"`, () => {
    const r = parseUtterance(text, NOW);
    assert.ok(r.ok, `parse failed: ${r.reason} / ${normalize(text)}`);
    assert.equal(r.event.kind, want.kind);
    if (want.amount_ml) assert.equal(r.event.amount_ml, want.amount_ml);
    if (want.type) assert.equal(r.event.detail.type, want.type);
    assert.equal(r.event.occurred_at.getTime(), want.at, `occurred_at ${r.event.occurred_at}`);
    if (want.end) assert.equal(r.event.ended_at.getTime(), want.end, `ended_at ${r.event.ended_at}`);
    assert.ok(r.label);
  });
}

for (const text of ['', '안녕', '기저귀', '수유', '잠 잤어', '오늘 날씨 어때']) {
  test(`못 알아들음: "${text}"`, () => {
    assert.equal(parseUtterance(text, NOW).ok, false);
  });
}

test('라벨', () => {
  assert.equal(parseUtterance('수유 160', NOW).label, '수유 160ml · 지금');
  assert.equal(parseUtterance('수유 160 20분 전', NOW).label, '수유 160ml · 20분 전');
  assert.equal(parseUtterance('기저귀 대변', NOW).label, '기저귀 대변 · 지금');
  assert.equal(parseUtterance('잠 1시 10분부터 2시 40분까지', NOW).label, '잠 13:10~14:40');
});
