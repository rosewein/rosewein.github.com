// 성장 백분위(src/growth.js): WHO 표에 적힌 값과 맞는지.
import test from 'node:test';
import assert from 'node:assert/strict';
import { lmsAt, zScore, valueAtZ, percentile, growthAt, daysSince, curve, formatPercentile, DAYS_PER_MONTH } from '../../src/growth.js';

const near = (a, b, tol, msg) => assert.ok(Math.abs(a - b) <= tol, `${msg}: ${a} ≠ ${b}`);

test('WHO 표의 가운데 값·±2SD 와 같다(남아 4개월)', () => {
  const w = lmsAt('weight', 'boy', 4 * DAYS_PER_MONTH);
  near(w.M, 7.0023, 1e-4, '체중 가운데');
  near(valueAtZ(2, w), 8.7, 0.05, '체중 +2SD(표 8.7)');
  near(valueAtZ(-2, w), 5.6, 0.05, '체중 -2SD(표 5.6)');
  const h = lmsAt('height', 'boy', 4 * DAYS_PER_MONTH);
  near(valueAtZ(0, h), 63.886, 1e-3, '키 가운데');
  near(valueAtZ(-2, h), 59.7, 0.05, '키 -2SD(표 59.7)');
  near(valueAtZ(1, lmsAt('head', 'boy', 4 * DAYS_PER_MONTH)), 42.8, 0.05, '머리둘레 +1SD(표 42.8)');
});

test('여아 표는 따로(6개월 체중 가운데 7.297)', () => {
  near(lmsAt('weight', 'girl', 6 * DAYS_PER_MONTH).M, 7.297, 1e-3, '여아 6개월');
});

test('z 점수와 값은 서로 되돌아간다, 백분위는 정규분포', () => {
  const lms = lmsAt('weight', 'boy', 150);
  near(zScore(valueAtZ(1.3, lms), lms), 1.3, 1e-9, '되돌리기');
  near(percentile(0), 50, 1e-4, '가운데');
  near(percentile(1.88079), 97, 0.01, '97백분위');
  near(percentile(-1.03643), 15, 0.01, '15백분위');
});

test('달 사이는 곧게 잇는다, 표 밖은 null', () => {
  const mid = lmsAt('weight', 'boy', 4.5 * DAYS_PER_MONTH);
  near(mid.M, (7.0023 + 7.5105) / 2, 1e-4, '4.5개월');
  assert.equal(lmsAt('weight', 'boy', -1), null);
  assert.equal(lmsAt('weight', 'boy', 25 * DAYS_PER_MONTH), null);
  assert.equal(lmsAt('weight', 'x', 10), null);
});

test('기본 나이와 교정 나이를 같이: 교정 나이가 어려서 백분위가 더 높다', () => {
  const g = growthAt({ kind: 'weight', value: 7.35, at: '2026-11-10T14:00:00+09:00', birth: '2026-06-18', due: '2026-07-10', sex: 'boy' });
  assert.equal(g.actual.days, 145);
  assert.equal(g.corrected.days, 123);
  assert.ok(g.corrected.pct > g.actual.pct);
  assert.ok(g.actual.pct > 30 && g.actual.pct < 60, `기본 ${g.actual.pct}`);
});

test('성별을 모르거나 예정일 전이면 셈하지 않는다', () => {
  assert.deepEqual(growthAt({ kind: 'weight', value: 7, at: new Date(), birth: '2026-06-18', sex: null }), { actual: null, corrected: null });
  const early = growthAt({ kind: 'weight', value: 3, at: '2026-07-01T12:00:00+09:00', birth: '2026-06-18', due: '2026-07-10', sex: 'boy' });
  assert.ok(early.actual && early.corrected === null);
});

test('날 수는 서울 날짜로, 태어난 날이 0', () => {
  assert.equal(daysSince('2026-06-18', '2026-06-18T23:00:00+09:00'), 0);
  assert.equal(daysSince('2026-06-18', '2026-06-19T00:10:00+09:00'), 1);
});

test('성장곡선 줄과 화면 글', () => {
  const c = curve('weight', 'boy', 50);
  assert.equal(c.length, 25);
  near(c[4][1], 7.0023, 1e-4, '50백분위 4개월');
  assert.ok(curve('weight', 'boy', 97)[4][1] > c[4][1]);
  assert.equal(formatPercentile(48.2), '48');
  assert.equal(formatPercentile(0.4), '1 미만');
  assert.equal(formatPercentile(99.7), '99 초과');
});

test('다가오는 일정 글: 남은 날, 여러 개면 "외 n"', async () => {
  const { describeAppointment } = await import('../../src/ui/upcoming.js');
  const now = new Date(2026, 10, 14, 9, 0);
  const a = { on_date: '2026-12-22', title: '예방접종', items: ['헥사심 3차', '폐렴구균 3차', '로타텍 3차', '독감 1차'] };
  assert.deepEqual(describeAppointment(a, now), { date: '12월 22일 화', title: '예방접종', left: 'D-38', items: '헥사심 3차 외 3', days: 38 });
  assert.equal(describeAppointment({ ...a, on_date: '2026-11-14', at_time: '10:30', items: [] }, now).left, '오늘');
  assert.equal(describeAppointment({ ...a, on_date: '2026-11-15' }, now).left, '내일');
  assert.equal(describeAppointment({ ...a, on_date: '2026-11-13' }, now), null);
});
