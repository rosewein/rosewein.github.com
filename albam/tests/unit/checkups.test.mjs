// 영유아 건강검진 시기(src/checkups.js): 세훈이 생일(2026-06-18)로 맞춰 본다.
import test from 'node:test';
import assert from 'node:assert/strict';
import { checkupStatus, CHECKUPS } from '../../src/checkups.js';

const birth = '2026-06-18';
const now = new Date(2026, 10, 14, 14, 0);
const row = (s, key, n) => s.rows.find((r) => r.key === key && r.n === n);

test('검진 기간: 1차 생후 14~35일, 2차 4~6개월(7개월 되기 전날까지)', () => {
  const s = checkupStatus({ birth, now });
  assert.deepEqual([row(s, 'health', 1).from, row(s, 'health', 1).until, row(s, 'health', 1).status], ['2026-07-02', '2026-07-23', 'overdue']);
  assert.deepEqual([row(s, 'health', 2).from, row(s, 'health', 2).until, row(s, 'health', 2).status], ['2026-10-18', '2027-01-17', 'due']);
  assert.deepEqual([row(s, 'health', 3).from, row(s, 'health', 3).until, row(s, 'health', 3).status], ['2027-03-18', '2027-07-17', 'later']);
  assert.deepEqual([row(s, 'dental', 1).from, row(s, 'dental', 1).until], ['2027-12-18', '2028-12-17']);
  assert.deepEqual(s.counts, { done: 0, booked: 0, due: 1, overdue: 1 });
  assert.equal(CHECKUPS[0].rounds.length, 8);
  assert.equal(CHECKUPS[1].rounds.length, 4);
});

test('받은 검진: 차수가 적혀 있으면 그 차수, 없으면 앞에서부터. 구강검진은 따로', () => {
  const s = checkupStatus({ birth, now, records: [{ at: '2026-07-10T10:00:00+09:00', text: '' }] });
  assert.deepEqual([row(s, 'health', 1).status, row(s, 'health', 1).date], ['done', '2026-07-10']);
  const only2 = checkupStatus({ birth, now, records: [{ at: '2026-11-10T10:00:00+09:00', text: '2차 검진' }] });
  assert.equal(row(only2, 'health', 1).status, 'overdue');
  assert.deepEqual([row(only2, 'health', 2).status, row(only2, 'health', 2).date], ['done', '2026-11-10']);
  const dental = checkupStatus({ birth, now: new Date(2028, 0, 10), records: [{ at: '2028-01-05T10:00:00+09:00', text: '구강검진' }] });
  assert.equal(row(dental, 'dental', 1).status, 'done');
  assert.equal(row(dental, 'health', 1).status, 'overdue');
});

test('예약: 이름에 검진이 들어간 앞으로의 일정', () => {
  const s = checkupStatus({ birth, now, records: [{ at: '2026-07-10T10:00:00+09:00', text: '1차' }],
    appointments: [{ on_date: '2026-12-22', title: '예방접종', items: ['헥사심 3차'] }, { on_date: '2026-12-01', title: '영유아검진', items: [] }] });
  assert.deepEqual([row(s, 'health', 2).status, row(s, 'health', 2).date], ['booked', '2026-12-01']);
  assert.equal(row(s, 'health', 3).status, 'later');
  assert.deepEqual(s.counts, { done: 1, booked: 1, due: 0, overdue: 0 });
});
