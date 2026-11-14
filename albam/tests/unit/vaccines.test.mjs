// 표준예방접종일정표(src/vaccines.js): 세훈이 실제 기록으로 맞춰 본다(2026-11-14 기준).
import test from 'node:test';
import assert from 'node:assert/strict';
import { vaccineStatus, statusText, addMonths, SCHEDULE } from '../../src/vaccines.js';

const birth = '2026-06-18';
const now = new Date(2026, 10, 14, 14, 0);
const rec = (day, text) => ({ at: `${day}T09:00:00+09:00`, text });
const records = [
  rec('2026-06-18', 'B형간염 1차'), rec('2026-07-07', 'BCG'),
  rec('2026-08-18', '헥사심 1차'), rec('2026-08-18', '폐렴구균 1차'), rec('2026-08-18', '로타텍 1차'),
  rec('2026-09-29', 'RSV 항체 주사'),
  rec('2026-10-20', '헥사심 2차'), rec('2026-10-20', '폐렴구균 2차'), rec('2026-10-20', '로타텍 2차'),
];
const appointments = [{ on_date: '2026-12-22', title: '예방접종', items: ['헥사심 3차', '폐렴구균 3차', '로타텍 3차', '독감 1차'] }];
const s = vaccineStatus({ birth, sex: 'boy', records, appointments, now });
const row = (key, dose) => s.periods.flatMap((p) => p.rows).find((r) => r.key === key && r.dose === dose);

test('표의 칸 차례로 묶인다', () => {
  assert.deepEqual(s.periods.slice(0, 6).map((p) => p.label), ['출생 시', '4주 이내', '1개월', '2개월', '4개월', '6개월']);
  assert.deepEqual(s.periods[3].rows.map((r) => r.key), ['dtap', 'ipv', 'hib', 'pcv', 'rv5']);
});

test('맞은 것: 단독 백신과 6가 혼합백신(헥사심 = DTaP·폴리오·Hib·B형간염)', () => {
  assert.deepEqual([row('hepb', 1).status, row('hepb', 1).date], ['done', '2026-06-18']);
  assert.deepEqual([row('bcg', 1).status, row('bcg', 1).date], ['done', '2026-07-07']);
  for (const key of ['dtap', 'ipv', 'hib', 'pcv', 'rv5']) {
    assert.deepEqual([row(key, 1).date, row(key, 2).date], ['2026-08-18', '2026-10-20'], key);
  }
  // 헥사심에 B형간염이 들어 있어 1개월 칸의 2차는 8/18 접종으로 채워진다
  assert.deepEqual([row('hepb', 2).status, row('hepb', 2).date], ['done', '2026-08-18']);
  assert.deepEqual([row('hepb', 3).status, row('hepb', 3).date], ['done', '2026-10-20']);
});

test('예약: 12/22 의 헥사심·폐렴구균·로타텍 3차', () => {
  for (const key of ['dtap', 'ipv', 'hib', 'pcv', 'rv5']) assert.deepEqual([row(key, 3).status, row(key, 3).date], ['booked', '2026-12-22'], key);
  assert.equal(statusText(row('pcv', 3)), '예약 12/22');
  assert.equal(statusText(row('bcg', 1)), '맞음 7/7');
});

test('로타바이러스는 맞은 백신 쪽 줄만(로타텍 3회), 남아에게 HPV 는 없다', () => {
  assert.ok(row('rv5', 3) && !row('rv1', 1));
  assert.ok(!row('hpv', 1));
  assert.ok(vaccineStatus({ birth, sex: 'girl', now }).periods.some((p) => p.rows.some((r) => r.key === 'hpv')));
  assert.ok(vaccineStatus({ birth, sex: 'boy', records: [rec('2026-08-18', '로타릭스 1차')], now }).periods.flatMap((p) => p.rows).some((r) => r.key === 'rv1' && r.status === 'done'));
});

test('아직 안 온 것, 지금 맞을 때, 시기 지남', () => {
  assert.equal(row('mmr', 1).status, 'later');
  assert.equal(row('mmr', 1).from, '2027-06-18');
  assert.equal(statusText(row('mmr', 1)), `${new Date().getFullYear() === 2027 ? '' : '2027년 '}6/18부터`);
  const none = vaccineStatus({ birth, sex: 'boy', now });
  const r = (key, dose) => none.periods.flatMap((p) => p.rows).find((x) => x.key === key && x.dose === dose);
  assert.equal(r('bcg', 1).status, 'overdue');
  assert.equal(r('dtap', 2).status, 'due', '4개월 칸은 10/18~11/17');
  assert.equal(r('dtap', 2).until, '2026-11-17');
  assert.equal(statusText(r('dtap', 2)), '지금 맞을 때(11/17까지)');
  assert.equal(r('dtap', 1).status, 'overdue');
  assert.equal(r('dtap', 3).status, 'later');
});

test('세는 수, 독감, 표에 없는 접종', () => {
  assert.deepEqual(s.counts, { done: 14, booked: 5, due: 0, overdue: 0 });
  assert.deepEqual(s.flu, { name: '인플루엔자(독감)', from: '2026-12-18', started: false, done: [], booked: ['2026-12-22'] });
  assert.deepEqual(s.others.map((o) => o.text), ['RSV 항체 주사']);
});

test('개월 더하기와 표의 줄', () => {
  assert.equal(addMonths('2026-06-18', 6).getMonth(), 11);
  assert.equal(addMonths('2026-01-31', 1).getDate(), 28);
  assert.equal(SCHEDULE.find((r) => r.key === 'dtap').doses.length, 5);
  assert.equal(SCHEDULE.find((r) => r.key === 'ijev').doses.length, 5);
});
