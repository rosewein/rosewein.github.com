// 통계 쪽 그래프 값(순수 함수)
import test from 'node:test';
import assert from 'node:assert/strict';

const { buildChart } = await import('../../src/ui/stats.js');

const day = (d, o = {}) => ({
  day: `2026-11-0${d}`, feed_count: 5, feed_ml: 850, diaper_total: 7, diaper_pee: 5, diaper_poo: 1, diaper_both: 1,
  nap_min: 120, night_min: 600, sleep_min: 720, ...o,
});
const week = [1, 2, 3, 4, 5, 6].map((d) => day(d)).concat([day(7, { feed_count: 1, feed_ml: 200, diaper_total: 2, diaper_poo: 0, diaper_both: 1, nap_min: 0, night_min: 685, sleep_min: 685 })]);

const text = (foot) => foot.map(([t]) => t).join('');

test('수유: 막대는 하루 양, 가장 많은 날이 꽉 참, 마지막 날은 "오늘"', () => {
  const { columns, foot } = buildChart(week, 'feed');
  assert.equal(columns.length, 7);
  assert.deepEqual(columns.map((c) => c.label), ['11/1', '11/2', '11/3', '11/4', '11/5', '11/6', '오늘']);
  assert.equal(columns[0].value, '850ml');
  assert.equal(columns[0].height, 46);
  assert.equal(columns[6].height, Math.round((200 / 850) * 46));
  assert.ok(columns[6].today && !columns[0].today);
  assert.equal(text(foot), '지난 6일 평균 5.0회 · 850ml', '평균은 오늘 빼고');
});

test('기저귀: 대변 있는 횟수(대변 + 둘 다)를 막대 아래쪽에 강조', () => {
  const { columns, foot } = buildChart(week, 'diaper');
  assert.equal(columns[0].value, '7회');
  assert.equal(columns[0].part, Math.round((2 / 7) * 46));
  assert.equal(text(foot), '지난 6일 평균 7.0회 · 대변 2.0회');
  assert.deepEqual(buildChart(week, 'diaper').legend, ['소변만', '대변 있음'], '색 설명');
  assert.equal(columns[0].partText, '2', '강조 칸이 넉넉하면 안에 대변 횟수');
  assert.equal(columns[6].partText, '', '좁으면 비움');
  assert.equal(buildChart(week, 'feed').legend, null, '수유는 한 색이라 설명 없음');
});

test('잠: 시간(소수 한 자리), 낮잠 강조, 평균은 시간·분', () => {
  const { columns, foot } = buildChart(week, 'sleep');
  assert.equal(columns[0].value, '12.0시간');
  assert.equal(columns[6].value, '11.4시간');
  assert.equal(columns[0].part, Math.round((120 / 720) * 46));
  assert.equal(text(foot), '평균 낮잠 2시간 · 밤잠 10시간');
  assert.deepEqual(buildChart(week, 'sleep').legend, ['밤잠', '낮잠']);
});

test('기록이 하나도 없는 날도 그린다(막대 0)', () => {
  const { columns } = buildChart([day(1, { feed_ml: 0 }), day(2, { feed_ml: 0 })], 'feed');
  assert.deepEqual(columns.map((c) => c.height), [0, 0]);
});
