// 해 뜨는 시각·지는 시각(순수 함수). 낮에는 밝은 화면, 해가 지면 어두운 화면으로 바꾸는 데 쓴다.
// 계산은 널리 쓰이는 근사식(SunCalc 와 같은 방식)이라 몇 분 정도 차이는 날 수 있다. 화면 색을 바꾸는 데는 충분하다.

const RAD = Math.PI / 180;
const DAY_MS = 86400000;
const J1970 = 2440588;
const J2000 = 2451545;
const J0 = 0.0009;
const OBLIQUITY = RAD * 23.4397;
/** 해 윗부분이 지평선에 닿는 높이(대기 굴절 포함) */
const H0 = RAD * -0.833;

const toDays = (date) => date.getTime() / DAY_MS - 0.5 + J1970 - J2000;
const fromJulian = (j) => new Date((j + 0.5 - J1970) * DAY_MS);

/**
 * @param {Date} date   그날의 아무 시각(그날 정오 가까이를 쓰면 정확하다)
 * @param {number} lat  위도
 * @param {number} lon  경도
 * @returns {{sunrise: Date, sunset: Date}}
 */
export function sunTimes(date, lat, lon) {
  const lw = RAD * -lon;
  const phi = RAD * lat;
  const n = Math.round(toDays(date) - J0 - lw / (2 * Math.PI));
  const ds = J0 + lw / (2 * Math.PI) + n;
  const M = RAD * (357.5291 + 0.98560028 * ds);
  const C = RAD * (1.9148 * Math.sin(M) + 0.02 * Math.sin(2 * M) + 0.0003 * Math.sin(3 * M));
  const L = M + C + RAD * 102.9372 + Math.PI;
  const dec = Math.asin(Math.sin(OBLIQUITY) * Math.sin(L));
  const transit = (x) => J2000 + x + 0.0053 * Math.sin(M) - 0.0069 * Math.sin(2 * L);
  const noon = transit(ds);
  const w = Math.acos((Math.sin(H0) - Math.sin(phi) * Math.sin(dec)) / (Math.cos(phi) * Math.cos(dec)));
  const set = transit(J0 + (w + lw) / (2 * Math.PI) + n);
  return { sunrise: fromJulian(noon - (set - noon)), sunset: fromJulian(set) };
}

/**
 * 지금이 밝은 화면일 때인가. theme: 'auto'(해 뜬 동안 밝게) | 'light' | 'dark'
 * @param {Date} now
 * @param {{theme?: string, location?: {lat: number, lon: number}}} cfg
 */
export function isDaylight(now, { theme = 'auto', location = { lat: 37.5665, lon: 126.978 } } = {}) {
  if (theme === 'light') return true;
  if (theme === 'dark') return false;
  const noon = new Date(now); noon.setHours(12, 0, 0, 0);
  const { sunrise, sunset } = sunTimes(noon, location.lat, location.lon);
  return now >= sunrise && now < sunset;
}
