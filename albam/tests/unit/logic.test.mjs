// 화면과 떨어진 순수 함수들: 시각 글자, 기록 이름, 캐릭터 기분, 수유량 빠른 선택, 못 보낸 기록 얹기
import test from 'node:test';
import assert from 'node:assert/strict';
import { agoParts, formatAgo, formatClock, formatDay, formatDuration, isWithinHours } from '../../src/time.js';
import { describeEvent, describeRecent } from '../../src/domain.js';
import { applyPending, findLocalDuplicate } from '../../src/api/pending.js';

// status.js·quick-record.js 는 DOM 도움 함수를 가져오지만, 불러오는 순간에는 DOM 을 쓰지 않는다
const { chooseMood } = await import('../../src/ui/status.js');
const { feedAmountsOf, clampAmount } = await import('../../src/ui/quick-record.js');
const { toSlots } = await import('../../src/ui/feed-amounts.js');

const NOW = new Date(2026, 10, 6, 15, 0);
const ago = (min) => new Date(NOW - min * 60000);

test('시각 글자', () => {
  assert.equal(formatClock(new Date(2026, 0, 1, 9, 5)), '09:05');
  assert.deepEqual(agoParts(ago(155), NOW), [['2', '시간'], ['35', '분']]);
  assert.deepEqual(agoParts(ago(35), NOW), [['35', '분']]);
  assert.deepEqual(agoParts(ago(0.5), NOW), []);
  assert.equal(formatAgo(ago(155), NOW), '2시간 35분 전');
  assert.equal(formatAgo(ago(0.5), NOW), '방금');
  assert.equal(formatAgo(ago(12 * 60 + 5), NOW), '12시간 5분 전');
  assert.equal(formatAgo(ago(11 * 60 + 59), NOW, { hoursOnlyFrom: 10 }), '11시간 전');
  assert.equal(formatAgo(ago(9 * 60 + 59), NOW, { hoursOnlyFrom: 10 }), '9시간 59분 전');
  assert.equal(formatAgo(ago(35), NOW), '35분 전');
  assert.equal(formatAgo(ago(70), NOW), '1시간 10분 전');
  assert.equal(formatAgo(ago(120), NOW), '2시간 전');
  assert.equal(formatDay(ago(60), NOW), '오늘');
  assert.equal(formatDay(ago(16 * 60), NOW), '어제');
  assert.equal(formatDay(ago(3 * 24 * 60), NOW), '11/3');
  assert.equal(formatDuration(90 * 60000), '1시간 30분');
});

test('밤 시간대(자정 넘김 포함)', () => {
  const at = (h) => new Date(2026, 10, 6, h);
  assert.equal(isWithinHours(at(21), 21, 6), true);
  assert.equal(isWithinHours(at(3), 21, 6), true);
  assert.equal(isWithinHours(at(6), 21, 6), false);
  assert.equal(isWithinHours(at(12), 21, 6), false);
  assert.equal(isWithinHours(at(13), 13, 15), true);
});

test('기록 이름', () => {
  assert.equal(describeEvent({ kind: 'feed', amount_ml: 160, occurred_at: NOW }, NOW), '수유 160ml');
  assert.equal(describeEvent({ kind: 'diaper', detail: { type: 'poo' }, occurred_at: ago(30) }, NOW), '기저귀 대변 · 14:30');
  assert.equal(describeEvent({ kind: 'sleep', occurred_at: ago(120), ended_at: ago(30) }, NOW), '잠 13:00~14:30');
  assert.equal(describeRecent({ kind: 'diaper', detail: { type: 'both' } }), '기저귀 소변+대변');
});

test('캐릭터 기분 우선순위', () => {
  const base = { happy: false, night: false, nightAwake: false, minutesSinceFeed: 30, hungryMinutes: 180 };
  assert.equal(chooseMood(base), 'normal');
  assert.equal(chooseMood({ ...base, minutesSinceFeed: 200 }), 'hungry');
  assert.equal(chooseMood({ ...base, night: true }), 'sleep');
  assert.equal(chooseMood({ ...base, night: true, nightAwake: true, minutesSinceFeed: 200 }), 'hungry');
  assert.equal(chooseMood({ ...base, happy: true, night: true }), 'happy');
  assert.equal(chooseMood({ ...base, minutesSinceFeed: null }), 'normal');
});

test('수유량 빠른 선택', () => {
  assert.deepEqual(feedAmountsOf({ feed_amounts: [220, 180, 200] }, [100]), [180, 200, 220]);
  assert.deepEqual(feedAmountsOf({ feed_amounts: [] }, [180, 200, 220]), [180, 200, 220], '비어 있으면 기본값');
  assert.deepEqual(feedAmountsOf(null, [180, 200, 220]), [180, 200, 220], '요약 전에는 기본값');
  assert.deepEqual(toSlots([200, 180, 220]), [180, 200, 220]);
  assert.deepEqual(toSlots([200]), [200, 220, 240], '모자라면 20ml씩 채움');
  assert.deepEqual(toSlots([100, 120, 140, 160]), [100, 120, 140], '세 칸까지');
  assert.equal(clampAmount(1000), 500);
  assert.equal(clampAmount(0), 5);
});

// ── 못 보낸 기록 얹기 ──
const base = {
  day_start: new Date(2026, 10, 6).toISOString(),
  last_feed: { id: 'f1', at: ago(120).toISOString(), ml: 140 },
  last_diaper: { id: 'd1', at: ago(60).toISOString(), type: 'pee' },
  today: { feed_count: 2, feed_ml: 260 },
  recent: [
    { id: 'd1', kind: 'diaper', at: ago(60).toISOString(), detail: { type: 'pee' } },
    { id: 'f1', kind: 'feed', at: ago(120).toISOString(), ml: 140 },
    { id: 'f0', kind: 'feed', at: ago(300).toISOString(), ml: 120 },
  ],
  settings: { dup_window_minutes: 10 },
};
const add = (id, kind, min, extra = {}) => ({ op: 'add', id, payload: { id, kind, occurred_at: ago(min).toISOString(), detail: {}, ...extra } });

test('못 보낸 수유가 요약에 얹힌다', () => {
  const s = applyPending(base, [add('f2', 'feed', 5, { amount_ml: 160 })]);
  assert.equal(s.last_feed.id, 'f2');
  assert.deepEqual(s.today, { feed_count: 3, feed_ml: 420 });
  assert.equal(s.recent[0].id, 'f2');
  assert.equal(s.recent[0].pending, true);
  assert.equal(base.today.feed_count, 2, '원본은 그대로');
});

test('나중에 넣은 옛 기록은 마지막 수유를 바꾸지 않는다', () => {
  const s = applyPending(base, [add('fx', 'feed', 200, { amount_ml: 90 })]);
  assert.equal(s.last_feed.id, 'f1');
  assert.equal(s.recent.map((r) => r.id).join(), 'd1,f1,fx,f0');
});

test('못 보낸 취소: 다음 기록이 마지막이 된다', () => {
  const s = applyPending(base, [{ op: 'cancel', id: 'f1' }]);
  assert.equal(s.last_feed.id, 'f0');
  assert.deepEqual(s.today, { feed_count: 1, feed_ml: 120 });
});

test('이미 요약에 들어간 기록은 두 번 세지 않는다', () => {
  const s = applyPending(base, [add('f1', 'feed', 120, { amount_ml: 140 })]);
  assert.equal(s.today.feed_count, 2);
});

test('못 보낸 수유량 설정이 얹힌다(가장 나중 것)', () => {
  const s = applyPending({ ...base, feed_amounts: [180, 200, 220] }, [
    { op: 'feed_amounts', id: 'x1', amounts: [190, 200, 210] },
    { op: 'feed_amounts', id: 'x2', amounts: [200, 210, 220] },
  ]);
  assert.deepEqual(s.feed_amounts, [200, 210, 220]);
});

test('요약이 없을 때(처음부터 오프라인)', () => {
  const s = applyPending(null, [add('d9', 'diaper', 1, { detail: { type: 'poo' } })]);
  assert.equal(s.last_diaper.type, 'poo');
});

test('기기 안 중복 확인', () => {
  assert.equal(findLocalDuplicate(base, { kind: 'diaper', occurred_at: ago(55).toISOString() }, 10)?.id, 'd1');
  assert.equal(findLocalDuplicate(base, { kind: 'diaper', occurred_at: ago(40).toISOString() }, 10), null);
  assert.equal(findLocalDuplicate(base, { id: 'd1', kind: 'diaper', occurred_at: ago(60).toISOString() }, 10), null);
});
