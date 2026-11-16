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

test('문구 켜고 끄기: 메모에 " · " 로 붙이고, 다른 글은 그대로', async () => {
  const { toggleMemo, memoHas, memoParts } = await import('../../m/phrases.js');
  assert.equal(toggleMemo('', '유산균'), '유산균');
  assert.equal(toggleMemo('유산균', '비타민D'), '유산균 · 비타민D');
  assert.equal(toggleMemo('유산균 · 비타민D', '유산균'), '비타민D');
  assert.equal(toggleMemo('조금 토함 · 유산균', '유산균'), '조금 토함');
  assert.ok(memoHas('유산균 · 비타민D', '비타민D') && !memoHas('유산균균', '유산균'));
  assert.deepEqual(memoParts(' 유산균 ·  · 비타민D '), ['유산균', '비타민D']);
});

test('고치기: 바꿀 내용만, 메모는 비워도 보낸다', async () => {
  const { buildPatch, shapeOf } = await import('../../m/entry.js');
  assert.equal(shapeOf('feed'), 'feed');
  assert.equal(shapeOf('diaper'), 'diaper');
  assert.equal(shapeOf('sleep'), 'range');
  assert.equal(shapeOf('weight'), 'number');
  const feed = { kind: 'feed', shape: 'feed', start: at(11, 25), hasEnd: true, end: at(11, 37), value: null, amount: 230, memo: '유산균' };
  assert.deepEqual(buildPatch(feed, now).patch, { occurred_at: at(11, 25), ended_at: at(11, 37), amount_ml: 230, detail: { memo: '유산균', feeding: false } });
  assert.deepEqual(buildPatch({ ...feed, hasEnd: false, memo: '' }, now).patch, { occurred_at: at(11, 25), ended_at: null, amount_ml: 230, detail: { memo: '' } });
  assert.equal(buildPatch({ ...feed, amount: 2000 }, now).error, '양을 0~1000 사이로 넣어 주세요');
  const diaper = { kind: 'diaper', shape: 'diaper', start: at(9, 10), hasEnd: false, end: null, value: null, diaperType: 'both', memo: '' };
  assert.deepEqual(buildPatch(diaper, now).patch, { occurred_at: at(9, 10), detail: { memo: '', type: 'both' } });
  const sleep = { kind: 'sleep', shape: 'range', start: at(9, 0), hasEnd: false, end: at(10, 0), value: null, memo: '' };
  assert.equal(buildPatch(sleep, now).patch.ended_at, null, '끝을 끄면 자는 중');
});

test('기록 쪽: 한 줄 글과 그날 합계', async () => {
  const { describeRow, daySummary, addDays, dayKey } = await import('../../m/records.js');
  const from = new Date(2026, 10, 14, 0, 0);
  const to = new Date(2026, 10, 15, 0, 0);
  const iso = (d) => d.toISOString();
  const feed = { kind: 'feed', at: iso(at(11, 25)), ended_at: iso(at(11, 37)), ml: 200, detail: { memo: '유산균' } };
  assert.deepEqual(describeRow(feed, from), { time: '11:25~11:37', kind: '수유', text: '200ml · 12분 · 유산균' });
  assert.deepEqual(describeRow({ kind: 'feed', at: iso(at(13, 48)), ended_at: null, ml: 200, feeding: true, detail: {} }, from), { time: '13:48~', kind: '수유', text: '200ml · 먹는 중' });
  assert.deepEqual(describeRow({ kind: 'diaper', at: iso(at(9, 10)), type: 'both', detail: { type: 'both' } }, from), { time: '09:10', kind: '기저귀', text: '소변+대변' });
  const night = { kind: 'sleep', at: iso(new Date(2026, 10, 13, 22, 10)), ended_at: iso(at(6, 30)), detail: {} };
  assert.deepEqual(describeRow(night, from), { time: '전날 22:10~06:30', kind: '잠', text: '8시간 20분' });
  assert.deepEqual(describeRow({ kind: 'temperature', at: iso(at(8, 20)), value: 36.8, detail: {} }, from), { time: '08:20', kind: '체온', text: '36.8°C' });
  assert.deepEqual(describeRow({ kind: 'bath', at: iso(at(19, 0)), ended_at: iso(at(19, 10)), detail: { memo: '보습로션' } }, new Date(2026, 10, 14)), { time: '19:00~19:10', kind: '목욕', text: '10분 · 보습로션' });
  const nap = { kind: 'sleep', at: iso(at(9, 0)), ended_at: iso(at(10, 40)), detail: {} };
  assert.equal(daySummary([night, feed, nap, { kind: 'diaper', type: 'poo' }, { kind: 'diaper', type: 'pee' }], from, to, now), '수유 1회 200ml · 기저귀 2회(대변 1) · 잠 8시간 10분');
  assert.equal(daySummary([], from, to, now), '');
  assert.equal(addDays('2026-11-01', -1), '2026-10-31');
  assert.equal(dayKey(at(9, 0)), '2026-11-14');
});

test('통계: 평균은 오늘을 빼고, 막대는 오늘까지', async () => {
  const { summarize, gapsByPeriod } = await import('../../m/stats.js');
  const d = (day, o) => ({ day, feed_count: 0, feed_ml: 0, feed_min: null, diaper_total: 0, diaper_pee: 0, diaper_poo: 0, diaper_both: 0, nap_min: 0, night_min: 0, sleep_min: 0, ...o });
  const days = [
    d('2026-11-12', { feed_count: 4, feed_ml: 800, feed_min: 10, diaper_total: 6, diaper_pee: 5, diaper_poo: 1, nap_min: 120, night_min: 600, sleep_min: 720 }),
    d('2026-11-13', { feed_count: 5, feed_ml: 1000, feed_min: 12, diaper_total: 4, diaper_pee: 4, nap_min: 60, night_min: 540, sleep_min: 600 }),
    d('2026-11-14', { feed_count: 1, feed_ml: 200, diaper_total: 1, diaper_pee: 1 }),
  ];
  const feed = summarize('feed', days);
  assert.equal(feed.headline, '900ml');
  assert.equal(feed.sub, '하루 4.5회');
  assert.deepEqual(feed.bars.map((b) => [b.value, b.today]), [[800, false], [1000, false], [200, true]]);
  assert.deepEqual(feed.cards.map((c) => c.value), ['200ml', '11분']);
  const diaper = summarize('diaper', days);
  assert.equal(`${diaper.headline} / ${diaper.sub}`, '5.0회 / 대변 하루 0.5회');
  assert.equal(diaper.cards[1].value, '1일');
  const sleep = summarize('sleep', days);
  assert.equal(sleep.headline, '11.0시간');
  assert.deepEqual(sleep.cards.map((c) => c.value), ['9.5시간', '1.5시간']);
  assert.equal(summarize('feed', [d('2026-11-14', {})]).headline, '기록 없음');
  const periods = [{ from: 6, to: 18, label: '낮' }, { from: 18, to: 24, label: '저녁' }, { from: 0, to: 6, label: '새벽' }];
  const gaps = [[7, 240], [10, 250], [14, 260], [19, 480], [20, 500], [21, 490], [2, 270]];
  assert.deepEqual(gapsByPeriod(gaps, periods).map((g) => `${g.label} ${g.text}`), ['낮 4시간 10분', '저녁 8시간 10분']);
});

test('성장곡선 좌표: 기본 나이와 교정 나이 두 줄, 또래 줄 다섯', async () => {
  const { growthChart } = await import('../../m/stats.js');
  const baby = { birth_date: '2026-06-18', due_date: '2026-07-10', sex: 'boy' };
  const measures = [
    { kind: 'weight', at: '2026-06-25T10:00:00+09:00', value: 3.1 },
    { kind: 'weight', at: '2026-11-10T10:00:00+09:00', value: 7.35 },
    { kind: 'height', at: '2026-11-10T10:00:00+09:00', value: 65.5 },
  ];
  const c = growthChart({ kind: 'weight', measures, baby, w: 340, h: 240 });
  assert.equal(c.lines.length, 5);
  assert.equal(c.actual.length, 2);
  assert.equal(c.corrected.length, 1, '예정일 전에 잰 값은 교정 줄에서 뺀다');
  assert.ok(c.corrected[0].x < c.actual[1].x, '교정 나이가 더 어려서 왼쪽');
  assert.equal(c.corrected[0].y, c.actual[1].y);
  assert.equal(c.months, 7);
  assert.equal(c.last.value, 7.35);
  assert.equal(growthChart({ kind: 'weight', measures, baby: { ...baby, sex: null }, w: 340, h: 240 }).lines.length, 0);
  assert.equal(growthChart({ kind: 'weight', measures: [], baby, w: 340, h: 240 }).last, null);
});

test('나이 글은 화면의 나이 줄과 같은 방식(2026-11-07 = 4개월 21일, 교정 3개월 29일)', async () => {
  const { ageText } = await import('../../m/stats.js');
  assert.equal(ageText('2026-06-18', new Date(2026, 10, 7, 10, 0)), '4개월 21일');
  assert.equal(ageText('2026-07-10', new Date(2026, 10, 7, 10, 0)), '3개월 29일');
  assert.equal(ageText('2026-06-18', new Date(2026, 5, 18, 23, 0)), '0개월 1일');
  assert.equal(ageText('2026-07-10', new Date(2026, 6, 1)), '');
  assert.equal(ageText('2026-01-31', new Date(2026, 2, 1)), '1개월 2일');
});

test('설정: 일정 칸 → 저장 내용, 맞은 접종 → 기록', async () => {
  const { parseItems, buildAppointment, vaccineEvents } = await import('../../m/settings.js');
  const { describeAppointment } = await import('../../src/ui/upcoming.js');
  assert.deepEqual(parseItems(' 헥사심 3차, 독감 1차 ,,\n로타텍 3차'), ['헥사심 3차', '독감 1차', '로타텍 3차']);
  assert.equal(buildAppointment({ on_date: '', title: '예방접종' }).error, '날짜를 넣어 주세요');
  assert.equal(buildAppointment({ on_date: '2026-12-22', title: ' ' }).error, '무슨 일정인지 써 주세요');
  assert.deepEqual(buildAppointment({ id: 'x', on_date: '2026-12-22', at_time: '', title: '예방접종', place: ' 구로병원 ', items: '헥사심 3차, 독감 1차', note: '' }).p,
    { id: 'x', on_date: '2026-12-22', at_time: '', title: '예방접종', place: '구로병원', items: ['헥사심 3차', '독감 1차'], note: '', kind: 'vaccine' });
  assert.equal(buildAppointment({ on_date: '2026-12-01', title: '영유아검진', items: '' }).p.kind, 'appointment');
  // 오늘 맞음: 지금 시각으로, 항목마다 한 줄
  const today = vaccineEvents({ on_date: '2026-11-14', at_time: null, title: '예방접종', place: '구로병원', items: ['헥사심 3차', '독감 1차'] }, now);
  assert.deepEqual(today.map((e) => [e.kind, e.detail.vaccine, e.detail.dose, e.detail.memo, e.detail.hospital]), [['vaccine', '헥사심', 3, '헥사심 3차', '구로병원'], ['vaccine', '독감', 1, '독감 1차', '구로병원']]);
  assert.equal(today[0].occurred_at.getTime(), now.getTime());
  // 지난 날: 오전 9시(시각을 넣어 뒀으면 그 시각). 항목이 없으면 일정 이름으로 한 줄
  const past = vaccineEvents({ on_date: '2026-11-11', at_time: null, title: '예방접종', items: [] }, now);
  assert.deepEqual([past.length, past[0].detail.memo, past[0].detail.dose, past[0].occurred_at.getTime()], [1, '예방접종', undefined, new Date(2026, 10, 11, 9, 0).getTime()]);
  assert.equal(vaccineEvents({ on_date: '2026-11-11', at_time: '10:30', title: '예방접종', items: ['BCG'] }, now)[0].occurred_at.getHours(), 10);
  // 오늘인데 넣어 둔 시각이 아직 안 왔으면 지금으로(미래 시각은 서버가 받지 않는다)
  assert.equal(vaccineEvents({ on_date: '2026-11-14', at_time: '18:00', title: '예방접종', items: ['BCG'] }, now)[0].occurred_at.getTime(), now.getTime());
  assert.equal(describeAppointment({ on_date: '2026-11-11', title: '예방접종' }, now), null);
  assert.equal(describeAppointment({ on_date: '2026-11-11', title: '예방접종' }, now, { past: true }).left, '3일 지남');
});
