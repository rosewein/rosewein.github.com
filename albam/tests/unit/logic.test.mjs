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
const { mlForScoops, mlForWater, waterFor, machineLabel, machineAmounts, stepMachine } = await import('../../src/formula.js');

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
  assert.equal(formatDuration(15 * 60000), '15분', '한 시간이 안 되면 분만');
  assert.equal(formatDuration(120 * 60000), '2시간', '분이 0이면 시간만');
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
  assert.equal(describeEvent({ kind: 'sleep', occurred_at: NOW }, NOW), '잠 시작 15:00');
  assert.equal(describeRecent({ kind: 'sleep', ended_at: null }), '잠 (자는 중)');
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
  assert.equal(chooseMood({ ...base, sleeping: true, minutesSinceFeed: 200 }), 'sleep', '자는 중이면 낮에도, 배고픈 시간이어도 잠');
  assert.equal(chooseMood({ ...base, sleeping: true, happy: true }), 'happy');
});

test('브레짜(물 30ml 단위) + 압타밀(물 30ml에 1스푼) → 완성량', () => {
  assert.deepEqual(machineAmounts(), [70, 100, 130, 170, 200, 230, 270, 300, 330], '브레짜 60~300, 10ml 단위 반올림');
  assert.deepEqual([180, 210, 240].map((w) => mlForWater(w)), [200, 230, 270]);
  assert.equal(mlForScoops(7), 230);
  assert.equal(waterFor(200), 180);
  assert.equal(waterFor(230), 210);
  assert.equal(waterFor(220), null, '브레짜 칸이 아님');
  assert.equal(waterFor(330), 300);
  assert.equal(waterFor(170), 150);
  assert.equal(waterFor(400), null, '브레짜 범위 밖');
  assert.equal(machineLabel(200), '브레짜 180');
  assert.equal(machineLabel(220), '브레짜 칸 아님');
  assert.equal(stepMachine(200, +1), 230);
  assert.equal(stepMachine(200, -1), 170);
  assert.equal(stepMachine(230, +1), 270, '반올림한 양에서도 한 칸씩');
  assert.equal(stepMachine(270, -1), 230);
  assert.equal(stepMachine(220, +1), 230, '칸이 아니면 위쪽 칸으로 맞춤');
  assert.equal(stepMachine(220, -1), 200, '칸이 아니면 아래쪽 칸으로 맞춤');
  assert.equal(stepMachine(70, -1), 70, '브레짜 60 아래로는 안 감');
  assert.equal(stepMachine(330, +1), 330, '브레짜 300 위로는 안 감');
  const other = { formula: { name: '다른 분유', waterMlPerScoop: 20, mlPerScoop: 22 }, machine: { name: '기계', minWaterMl: 40, maxWaterMl: 200, stepWaterMl: 20 } };
  assert.equal(machineLabel(220, other.formula, other.machine), '기계 200', '분유·기계를 바꾸면 설정값만 바꾸면 됨');
});

test('수유량 빠른 선택', () => {
  assert.deepEqual(feedAmountsOf({ feed_amounts: [270, 200, 230] }, [100]), [200, 230, 270]);
  assert.deepEqual(feedAmountsOf({ feed_amounts: [] }, [200, 230, 270]), [200, 230, 270], '비어 있으면 기본값');
  assert.deepEqual(feedAmountsOf(null, [200, 230, 270]), [200, 230, 270], '요약 전에는 기본값');
  assert.deepEqual(toSlots([230, 200, 270]), [200, 230, 270]);
  assert.deepEqual(toSlots([200]), [200, 230, 270], '모자라면 브레짜 한 칸씩 채움');
  assert.deepEqual(toSlots([100, 130, 170, 200]), [100, 130, 170], '세 칸까지');
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

test('직접 입력한 시각: 고른 날에 맞추고, 아직 안 온 시각이면 하루 앞으로', async () => {
  const { clockOnDay } = await import('../../src/time.js');
  const now = new Date(2026, 10, 7, 1, 0);
  assert.deepEqual(clockOnDay(now, 0, 30, now), new Date(2026, 10, 7, 0, 30));
  assert.deepEqual(clockOnDay(now, 23, 30, now), new Date(2026, 10, 6, 23, 30), '새벽 1시에 23:30 → 어제');
  assert.deepEqual(clockOnDay(new Date(2026, 10, 5, 9, 0), 23, 30, now), new Date(2026, 10, 5, 23, 30), '지난날은 그날 그대로');
});

test('잠: 끝이 없으면 자는 중, 못 보낸 깼어요/되돌리기를 요약에 얹기', async () => {
  const { sleepingNow } = await import('../../src/domain.js');
  const base = { last_sleep: { id: 's1', at: ago(90).toISOString(), ended_at: null }, recent: [{ id: 's1', kind: 'sleep', at: ago(90).toISOString(), ended_at: null }] };
  assert.equal(sleepingNow(base)?.id, 's1');
  assert.equal(sleepingNow({ last_sleep: { id: 's0', at: 'x', ended_at: 'y' } }), null);
  assert.equal(sleepingNow(null), null);
  const woke = applyPending(base, [{ op: 'sleep_end', id: 's1', ended_at: NOW.toISOString() }]);
  assert.equal(woke.last_sleep.ended_at, NOW.toISOString());
  assert.equal(woke.recent[0].ended_at, NOW.toISOString());
  assert.equal(sleepingNow(woke), null);
  const undone = applyPending(base, [{ op: 'sleep_end', id: 's1', ended_at: NOW.toISOString() }, { op: 'sleep_end', id: 's1', ended_at: null }]);
  assert.equal(sleepingNow(undone)?.id, 's1', '깼어요를 취소하면 다시 자는 중');
});

test('그날 기록 목록: 그날 것만 시각 순, 자정 넘은 잠은 시작한 날', async () => {
  const { eventsOfDay, describeRow } = await import('../../src/ui/day-list.js');
  const now = new Date(2026, 10, 7, 14, 0);
  const at = (d, h, m = 0) => new Date(2026, 10, d, h, m).toISOString();
  const ev = [
    { id: 'b', kind: 'feed', at: at(7, 6), ml: 200 },
    { id: 'a', kind: 'sleep', at: at(6, 20), ended_at: at(7, 5, 40) },
    { id: 'c', kind: 'diaper', at: at(7, 8, 30), type: 'both' },
  ];
  assert.deepEqual(eventsOfDay(ev, now, 0).list.map((e) => e.id), ['b', 'c']);
  assert.deepEqual(eventsOfDay(ev, now, 1).list.map((e) => e.id), ['a']);
  assert.deepEqual(describeRow(ev[1], now), ['20:00~05:40', '잠 9시간 40분']);
  assert.deepEqual(describeRow(ev[0], now), ['06:00', '수유 200ml']);
  assert.deepEqual(describeRow(ev[2], now), ['08:30', '기저귀 소변+대변']);
  assert.deepEqual(describeRow({ kind: 'sleep', at: at(7, 13), ended_at: null }, now), ['13:00~', '잠 (자는 중 1시간)']);
});

test('나이 줄 조각', async () => {
  const { ageParts } = await import('../../src/ui/status.js');
  const text = (p) => p.map(([t]) => t).join('');
  assert.equal(text(ageParts({ day: 143, months: 4, days: 21, corrected_months: 3, corrected_days: 29 })), 'D+143 · 4개월 21일 · 교정 3개월 29일');
  assert.equal(text(ageParts({ day: 10, months: 0, days: 10, corrected_months: null })), 'D+10 · 0개월 10일', '예정일 전에는 교정 나이 없음');
});

test('못 보낸 고치기를 요약에 얹기', () => {
  const base = {
    day_start: ago(600).toISOString(), today: { feed_count: 1, feed_ml: 200 },
    last_feed: { id: 'f', at: ago(60).toISOString(), ml: 200 },
    recent: [{ id: 'f', kind: 'feed', at: ago(60).toISOString(), ml: 200, detail: { memo: 'x' } }],
  };
  const s = applyPending(base, [{ op: 'update', id: 'f', patch: { amount_ml: 230, occurred_at: ago(90).toISOString() } }]);
  assert.equal(s.last_feed.ml, 230);
  assert.equal(s.last_feed.at, ago(90).toISOString());
  assert.equal(s.today.feed_ml, 230, '오늘 합계는 양 차이만큼');
  assert.equal(s.recent[0].ml, 230);
  assert.equal(s.recent[0].detail.memo, 'x');
});

test('수유: 먹이는 중, 다 먹음, 걸린 시간 글', async () => {
  const { feedingNow } = await import('../../src/domain.js');
  const { describeRow } = await import('../../src/ui/day-list.js');
  const f = { id: 'f', at: ago(8).toISOString(), ml: 200, ended_at: null, feeding: true };
  assert.equal(feedingNow({ last_feed: f })?.id, 'f');
  assert.equal(feedingNow({ last_feed: { ...f, feeding: false } }), null, '시간 없이 저장한 수유는 먹이는 중이 아님');
  assert.equal(feedingNow({ last_feed: { ...f, ended_at: NOW.toISOString() } }), null);
  const done = applyPending({ last_feed: f, recent: [{ id: 'f', kind: 'feed', at: f.at, ml: 200, detail: { feeding: true } }] },
    [{ op: 'update', id: 'f', patch: { ended_at: NOW.toISOString(), detail: { feeding: false } } }]);
  assert.equal(feedingNow(done), null, '못 보낸 [다 먹음]도 바로 반영');
  assert.equal(done.last_feed.ended_at, NOW.toISOString());
  const started = applyPending({ recent: [] }, [{ op: 'add', id: 'n', payload: { id: 'n', kind: 'feed', occurred_at: NOW.toISOString(), amount_ml: 200, detail: { feeding: true } } }]);
  assert.equal(feedingNow(started)?.id, 'n', '못 보낸 [먹이기 시작]도 먹이는 중');
  assert.equal(describeEvent({ kind: 'feed', amount_ml: 200, occurred_at: ago(12), ended_at: NOW }, NOW), '수유 200ml · 12분 · 14:48');
  assert.deepEqual(describeRow({ kind: 'feed', at: ago(12).toISOString(), ended_at: NOW.toISOString(), ml: 200 }, NOW), ['14:48~15:00', '수유 200ml · 12분']);
  assert.deepEqual(describeRow({ kind: 'feed', at: ago(8).toISOString(), ended_at: null, ml: 200, feeding: true }, NOW), ['14:52~', '수유 200ml (먹는 중 8분)']);
});

test('그 밖의 기록 종류(체온·목욕·투약)', async () => {
  const { formatValue, describeOther, recordType, moreTypes, setRecordTypes, DEFAULT_RECORD_TYPES } = await import('../../src/domain.js');
  const { describeRow } = await import('../../src/ui/day-list.js');
  assert.equal(formatValue(recordType('temperature'), 37.4), '37.4°C');
  assert.equal(formatValue(recordType('weight'), 7.346), '7.35kg');
  assert.equal(describeOther('temperature', { value: 37.9 }), '체온 37.9°C');
  assert.equal(describeOther('bath', { at: ago(30), ended_at: ago(20), detail: { memo: '보습로션' } }), '목욕 · 10분 · 보습로션');
  assert.equal(describeOther('medication', { detail: { medicine: '해열제' } }), '투약 · 해열제');
  assert.ok(moreTypes().every((t) => t.in_more) && !moreTypes().some((t) => t.key === 'feed'), '더보기에 수유·기저귀·잠은 없음');
  assert.deepEqual(describeRow({ kind: 'temperature', at: new Date(2026, 10, 6, 8, 53), value: 37.1 }, NOW), ['08:53', '체온 37.1°C']);
  assert.deepEqual(describeRow({ kind: 'bath', at: new Date(2026, 10, 6, 19, 0), ended_at: new Date(2026, 10, 6, 19, 15), memo: '보습' }, NOW), ['19:00~19:15', '목욕 · 15분 · 보습']);
  assert.equal(describeRecent({ kind: 'temperature', value: 37.2 }), '체온 37.2°C');
  assert.equal(describeEvent({ kind: 'temperature', value_num: 38, occurred_at: NOW }, NOW), '체온 38.0°C');
  setRecordTypes([...DEFAULT_RECORD_TYPES, { key: 'vaccine', label: '예방접종', shape: 'instant', in_more: true }]);
  assert.ok(moreTypes().some((t) => t.label === '예방접종'), '표에 한 줄 더하면 더보기 버튼도 늘어남');
  setRecordTypes(DEFAULT_RECORD_TYPES);
});

test('못 보낸 대변 기록이 마지막 대변에 얹히고, 취소하면 빠진다', () => {
  const withPoo = { ...base, last_poo: null };
  const s = applyPending(withPoo, [add('p1', 'diaper', 3, { detail: { type: 'both' } }), add('p2', 'diaper', 1, { detail: { type: 'pee' } })]);
  assert.equal(s.last_poo.id, 'p1', '소변만인 기록은 마지막 대변이 아님');
  assert.equal(s.last_diaper.id, 'p2');
  const c = applyPending({ ...base, last_poo: { id: 'd9', at: ago(30).toISOString(), type: 'poo' },
    recent: [{ id: 'd9', kind: 'diaper', at: ago(30).toISOString(), detail: { type: 'poo' } }, ...base.recent] }, [{ op: 'cancel', id: 'd9' }]);
  assert.equal(c.last_poo, null);
});

test('말풍선·표정: 가장 급한 항목 하나', async () => {
  const { chooseFocus, diaperDetail } = await import('../../src/ui/status.js');
  const limits = { feed: 180, diaper: 180, awake: 120 };
  const calm = { minutes: { feed: 60, diaper: 30, awake: 40 }, limits };
  assert.deepEqual(chooseFocus(calm), { mood: 'normal', focus: 'feed', urgent: false, words: '기분 좋아요' });
  assert.deepEqual(chooseFocus({ ...calm, minutes: { feed: 200, diaper: 30, awake: 40 } }), { mood: 'hungry', focus: 'feed', urgent: true, words: '배고파요…' });
  // 수유 200/180 = 1.11, 깬 지 150/120 = 1.25 → 졸림이 더 급함
  assert.equal(chooseFocus({ ...calm, minutes: { feed: 200, diaper: 30, awake: 150 } }).focus, 'sleep');
  assert.equal(chooseFocus({ ...calm, minutes: { feed: 60, diaper: 240, awake: null } }).words, '기저귀 봐 주세요…');
  assert.equal(chooseFocus({ ...calm, minutes: { feed: 200, diaper: 240, awake: 150 }, sleeping: true }).words, '쿨쿨', '자는 중이면 급한 것보다 잠');
  assert.equal(chooseFocus({ ...calm, minutes: { feed: 200, diaper: 30, awake: 40 }, feeding: true }).words, '냠냠');
  assert.equal(chooseFocus({ ...calm, happy: true, feeding: true }).words, '고마워요!');
  assert.equal(chooseFocus({ ...calm, minutes: { feed: null, diaper: null, awake: null } }).urgent, false, '기록이 없으면 급하지 않음');
  assert.equal(chooseFocus({ ...calm, night: true }).mood, 'sleep');
  assert.equal(chooseFocus({ ...calm, night: true, nightAwake: true, minutes: { feed: 200, diaper: 0, awake: 0 } }).mood, 'hungry');
  const d = (day, h, m) => new Date(2026, 10, day, h, m);
  assert.equal(diaperDetail({ at: d(6, 12, 50), type: 'both' }, null, false, NOW), '12:50 · 소+대');
  assert.equal(diaperDetail({ at: d(6, 12, 50), type: 'pee' }, { at: d(6, 9, 10) }, false, NOW), '12:50 소변 · 대 09:10');
  assert.equal(diaperDetail({ at: d(6, 12, 50), type: 'pee' }, { at: d(6, 9, 10) }, true, NOW), '12:50 · 대 09:10', '좁은 화면');
  // 대변이 어제·그 전이면 날을 붙인다(24시간 넘었는데 아침 시각만 보이면 헷갈림)
  assert.equal(diaperDetail({ at: d(6, 12, 50), type: 'pee' }, { at: d(5, 9, 10) }, false, NOW), '12:50 · 대 어제 09:10');
  assert.equal(diaperDetail({ at: d(6, 12, 50), type: 'pee' }, { at: d(5, 9, 10) }, true, NOW), '12:50 · 대 어제');
  assert.equal(diaperDetail({ at: d(6, 12, 50), type: 'pee' }, { at: d(3, 9, 10) }, false, NOW), '12:50 · 대 11/3 09:10');
  assert.equal(diaperDetail({ at: d(5, 22, 10), type: 'both' }, null, false, NOW), '어제 22:10 · 소+대');
  assert.equal(diaperDetail(null, null), '기록 없음');
});

test('배고파요 기준: 숫자면 그대로, auto 면 마지막 수유 시간대의 수유 간격 25% 값', async () => {
  const { hungryLimit } = await import('../../src/ui/status.js');
  // 낮(06~18시)에 시작한 간격은 4시간 안팎, 저녁(18~24시)에 시작한 간격은 8시간 안팎, 새벽은 4시간 반
  const day = [220, 230, 240, 250, 260, 270, 280].map((g, i) => [8 + i, g]);
  const evening = [450, 480, 500, 520, 560, 600].map((g, i) => [19 + (i % 3), g]);
  const dawn = [250, 260, 270].map((g, i) => [2 + i, g]);
  const s = { feed_gaps: [...day, ...evening, ...dawn] };
  const at = (h) => new Date(2026, 10, 8, h, 30);
  assert.deepEqual(hungryLimit(200, s, at(10)), { minutes: 200, period: null });
  assert.deepEqual(hungryLimit('auto', s, at(10)), { minutes: 240, period: '낮' }, '낮 간격 25% = 235 → 240');
  assert.deepEqual(hungryLimit('auto', s, at(20)), { minutes: 490, period: '저녁' }, '저녁 수유 뒤에는 길게');
  assert.equal(hungryLimit('auto', s, at(3)).period, null, '새벽 간격이 6개 미만이면 전체 간격');
  assert.equal(hungryLimit('auto', { feed_gaps: day.slice(0, 3) }, at(10)).minutes, 180, '전체가 10개 미만이면 180');
  assert.equal(hungryLimit('auto', { feed_gap: { n: 64, p25: 246 } }, at(10)).minutes, 250, '010 만 있는 서버');
  assert.equal(hungryLimit('auto', null, null).minutes, 180);
});

test('날이 다르면 날을 붙인 시각', async () => {
  const { formatClockOn } = await import('../../src/time.js');
  assert.equal(formatClockOn(new Date(2026, 10, 6, 9, 0), NOW), '09:00');
  assert.equal(formatClockOn(new Date(2026, 10, 5, 9, 0), NOW), '어제 09:00');
  assert.equal(formatClockOn(new Date(2026, 10, 5, 9, 0), NOW, true), '어제');
  assert.equal(formatClockOn(new Date(2026, 10, 1, 9, 0), NOW), '11/1 09:00');
});
