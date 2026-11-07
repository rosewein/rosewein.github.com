// 해 뜨고 지는 시각(서울). 한국천문연구원 값과 몇 분 안에서 맞는지
import test from 'node:test';
import assert from 'node:assert/strict';
import { sunTimes, isDaylight } from '../../src/sun.js';

const SEOUL = { lat: 37.5665, lon: 126.978 };
const kst = (iso) => new Date(`${iso}+09:00`);
const near = (a, b, min, label) => assert.ok(Math.abs(a - b) <= min * 60000, `${label}: ${a.toISOString()} vs ${b.toISOString()}`);

test('서울 해 뜨고 지는 시각', () => {
  const nov = sunTimes(kst('2026-11-07T12:00'), SEOUL.lat, SEOUL.lon);
  near(nov.sunrise, kst('2026-11-07T07:01'), 5, '11/7 해 뜸');
  near(nov.sunset, kst('2026-11-07T17:28'), 5, '11/7 해 짐');
  const jun = sunTimes(kst('2026-06-21T12:00'), SEOUL.lat, SEOUL.lon);
  near(jun.sunrise, kst('2026-06-21T05:11'), 5, '6/21 해 뜸');
  near(jun.sunset, kst('2026-06-21T19:57'), 5, '6/21 해 짐');
});

test('밝은 화면일 때', () => {
  process.env.TZ = 'Asia/Seoul';
  assert.equal(isDaylight(kst('2026-11-07T14:00')), true);
  assert.equal(isDaylight(kst('2026-11-07T18:30')), false);
  assert.equal(isDaylight(kst('2026-11-07T06:30')), false);
  assert.equal(isDaylight(kst('2026-11-07T22:00'), { theme: 'light' }), true);
  assert.equal(isDaylight(kst('2026-11-07T14:00'), { theme: 'dark' }), false);
});
