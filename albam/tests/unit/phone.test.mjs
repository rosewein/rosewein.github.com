// 개인 폰 화면(m/)의 순수 함수: 넣기 창의 값 → 기록.
import test from 'node:test';
import assert from 'node:assert/strict';
import { buildEvent, toLocalInput } from '../../m/entry.js';

const now = new Date(2026, 10, 14, 14, 0);
const at = (h, m) => new Date(2026, 10, 14, h, m);
const base = { kind: 'walk', shape: 'range', start: at(13, 0), hasEnd: true, end: at(13, 40), value: null, memo: '' };

test('시작~끝 종류: 끝을 켜면 ended_at, 끄면 한 시각만', () => {
  const { ev } = buildEvent(base, now);
  assert.equal(ev.kind, 'walk');
  assert.equal(ev.source, 'phone');
  assert.deepEqual([ev.occurred_at, ev.ended_at], [at(13, 0), at(13, 40)]);
  assert.equal(buildEvent({ ...base, hasEnd: false }, now).ev.ended_at, undefined);
});

test('미래 시각, 끝이 시작보다 앞이면 못 넣는다', () => {
  assert.equal(buildEvent({ ...base, start: at(14, 30), hasEnd: false }, now).error, '아직 안 온 시각이에요');
  assert.equal(buildEvent({ ...base, end: at(14, 30) }, now).error, '끝이 아직 안 온 시각이에요');
  assert.equal(buildEvent({ ...base, end: at(12, 50) }, now).error, '끝이 시작보다 뒤여야 해요');
  assert.equal(buildEvent({ ...base, start: null }, now).error, '시각을 넣어 주세요');
});

test('숫자 종류: 값이 있어야 하고 범위 안이어야', () => {
  const w = { kind: 'weight', shape: 'number', start: at(13, 0), hasEnd: false, end: null, value: 7.35, memo: '', min: 1, max: 30 };
  assert.equal(buildEvent(w, now).ev.value_num, 7.35);
  assert.equal(buildEvent({ ...w, value: null }, now).error, '숫자를 넣어 주세요');
  assert.equal(buildEvent({ ...w, value: 45 }, now).error, '1~30 사이로 넣어 주세요');
});

test('메모 종류는 글이 꼭, 다른 종류는 글이 있으면 detail.memo', () => {
  const memo = { kind: 'memo', shape: 'text', start: at(13, 0), hasEnd: false, end: null, value: null, memo: '  ' };
  assert.equal(buildEvent(memo, now).error, '메모를 써 주세요');
  assert.deepEqual(buildEvent({ ...memo, memo: ' 손톱 깎음 ' }, now).ev.detail, { memo: '손톱 깎음' });
  assert.deepEqual(buildEvent({ ...base, memo: '공원' }, now).ev.detail, { memo: '공원' });
  assert.deepEqual(buildEvent(base, now).ev.detail, {});
});

test('날짜·시간 칸 값은 기기 시간대 그대로', () => {
  assert.equal(toLocalInput(at(9, 5)), '2026-11-14T09:05');
});
