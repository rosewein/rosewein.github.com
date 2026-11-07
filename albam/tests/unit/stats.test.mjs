// 통계 쪽 날짜 카드 값, 타임라인 줄, 시계 쪽 날짜(순수 함수)
import test from 'node:test';
import assert from 'node:assert/strict';

const { buildCards } = await import('../../src/ui/stats.js');
const { layoutTimeline, mergePending } = await import('../../src/ui/timeline.js');
const { formatLongDate } = await import('../../src/ui/clock-page.js');

const day = (d, o = {}) => ({
  day: `2026-11-0${d}`, feed_count: 5, feed_ml: 850, diaper_total: 7, diaper_pee: 5, diaper_poo: 1, diaper_both: 1,
  nap_min: 120, night_min: 600, sleep_min: 720, ...o,
});
const week = [1, 2, 3, 4, 5, 6].map((d) => day(d)).concat([day(7, { feed_count: 1, feed_ml: 200, diaper_total: 2, diaper_poo: 0, diaper_both: 1, nap_min: 0, night_min: 685, sleep_min: 685 })]);
const text = (pieces) => pieces.map(([t]) => t).join('');

test('수유 카드: 큰 숫자 = 횟수, 주황 칸 = 하루 양, 막대 = 가장 많은 날 대비', () => {
  const { cards, foot, legend } = buildCards(week, 'feed');
  assert.equal(cards.length, 7);
  assert.deepEqual(cards.map((c) => c.label), ['11/1', '11/2', '11/3', '11/4', '11/5', '11/6', '오늘']);
  assert.deepEqual([cards[0].big, cards[0].badge, cards[0].icon, cards[0].bar], ['5', '850', 'bottle', 1]);
  assert.equal(cards[6].bar, 200 / 850);
  assert.ok(cards[6].today && !cards[0].today);
  assert.equal(text(foot), '지난 6일 평균 5.0회 · 850ml', '평균은 오늘 빼고');
  assert.equal(text(legend), '숫자 = 횟수 ·  = 하루 양(ml)');
});

test('기저귀 카드: 큰 숫자 = 전체, 💩 = 대변 있는 횟수(대변 + 둘 다), 막대 = 그 몫', () => {
  const { cards, foot } = buildCards(week, 'diaper');
  assert.deepEqual([cards[0].big, cards[0].badge, cards[0].icon], ['7', '2', 'poo']);
  assert.equal(cards[0].bar, 2 / 7);
  assert.deepEqual([cards[6].big, cards[6].badge, cards[6].bar], ['2', '1', 0.5]);
  assert.equal(text(foot), '지난 6일 평균 7.0회 · 대변 2.0회');
});

test('잠 카드: 큰 숫자 = 시간(소수는 작게), 주황 칸 = 낮잠 시간', () => {
  const { cards, foot } = buildCards(week, 'sleep');
  assert.deepEqual([cards[0].big, cards[0].small, cards[0].badgeText, cards[0].badge], ['12', '.0', '낮', '2.0']);
  assert.deepEqual([cards[6].big, cards[6].small, cards[6].badge, cards[6].bar], ['11', '.4', '0.0', 0]);
  assert.equal(text(foot), '평균 낮잠 2시간 · 밤잠 10시간');
});

test('기록이 하나도 없는 날도 카드(0)', () => {
  const { cards } = buildCards([day(1, { feed_ml: 0, diaper_total: 0, diaper_poo: 0, diaper_both: 0 })], 'diaper');
  assert.deepEqual([cards[0].big, cards[0].badge, cards[0].bar], ['0', '0', 0]);
});

const NOW = new Date(2026, 10, 7, 14, 0);
const at = (d, h, m = 0) => new Date(2026, 10, d, h, m).toISOString();

test('타임라인: 오늘·어제·그저께 줄, 자정을 넘는 잠은 두 줄로 나눔', () => {
  const rows = layoutTimeline([
    { id: 'a', kind: 'sleep', at: at(6, 20), ended_at: at(7, 5, 30) },
    { id: 'b', kind: 'feed', at: at(7, 6), ml: 200 },
    { id: 'c', kind: 'feed', at: at(7, 6, 40), ml: 200 },
    { id: 'd', kind: 'diaper', at: at(7, 8), type: 'both' },
    { id: 'e', kind: 'diaper', at: at(6, 9), type: 'pee' },
    { id: 'f', kind: 'sleep', at: at(7, 13), ended_at: null },
    { id: 'g', kind: 'feed', at: at(1, 6), ml: 200 },
  ], NOW, { days: 3 });
  assert.deepEqual(rows.map((r) => r.label), ['오늘', '어제', '11/5']);
  const [today, yday] = rows;
  assert.equal(today.now, 14);
  assert.deepEqual(today.sleeps, [{ from: 0, to: 5.5, open: false }, { from: 13, to: 14, open: true }], '자는 중이면 지금까지');
  assert.deepEqual(yday.sleeps, [{ from: 20, to: 24, open: false }]);
  assert.deepEqual(today.feeds.map((f) => [f.at, f.label]), [[6, true], [6 + 40 / 60, false]], '40분 차이 수유는 양 글자를 하나만');
  assert.deepEqual(today.diapers, [{ at: 8, poo: true }]);
  assert.deepEqual(yday.diapers, [{ at: 9, poo: false }]);
  assert.equal(yday.now, null);
  assert.equal(rows[2].feeds.length, 0, '3일보다 전 기록은 없음');
});

test('타임라인: 아직 못 보낸 기록과 못 보낸 깼어요를 얹음', () => {
  const merged = mergePending([{ id: 's', kind: 'sleep', at: at(7, 12), ended_at: null }], [
    { id: 's', kind: 'sleep', at: at(7, 12), ended_at: at(7, 13), pending: false },
    { id: 'p', kind: 'diaper', at: at(7, 13, 30), detail: { type: 'poo' }, pending: true },
  ]);
  assert.equal(merged.find((e) => e.id === 's').ended_at, at(7, 13));
  assert.deepEqual(merged.find((e) => e.id === 'p'), { id: 'p', kind: 'diaper', at: at(7, 13, 30), ended_at: null, ml: null, type: 'poo' });
});

test('시계 쪽 날짜', () => {
  assert.deepEqual(formatLongDate(new Date(2026, 10, 7)), { date: '11월 7일', weekday: '토요일' });
});
