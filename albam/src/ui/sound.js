// 효과음. 파일 없이 WebAudio 사각파로 8비트 소리를 낸다.
// 브라우저는 사용자가 한 번 화면을 누른 뒤에만 소리를 허락하므로, 처음 누를 때 만들어진다.

/** [주파수 Hz, 길이 초] 목록 */
const TUNES = {
  save: [[660, 0.08], [880, 0.08], [1320, 0.14]],
  cancel: [[660, 0.08], [440, 0.14]],
  error: [[200, 0.12], [160, 0.2]],
  listen: [[990, 0.06]],
  tap: [[520, 0.03]],
};
const VOLUME = { normal: 0.06, quiet: 0.02 };

/**
 * @param {() => boolean} isQuiet  밤에는 작게
 * @returns {Record<keyof TUNES, () => void>}
 */
export function createSound(isQuiet) {
  let ctx = null;

  function play(notes) {
    try {
      ctx ??= new (window.AudioContext || window.webkitAudioContext)();
      if (ctx.state === 'suspended') ctx.resume();
      const volume = isQuiet() ? VOLUME.quiet : VOLUME.normal;
      let t = ctx.currentTime + 0.01;
      for (const [freq, dur] of notes) {
        const osc = ctx.createOscillator();
        const gain = ctx.createGain();
        osc.type = 'square';
        osc.frequency.value = freq;
        gain.gain.setValueAtTime(volume, t);
        gain.gain.exponentialRampToValueAtTime(0.0001, t + dur);
        osc.connect(gain).connect(ctx.destination);
        osc.start(t);
        osc.stop(t + dur + 0.02);
        t += dur * 0.85;
      }
    } catch (e) { /* 소리가 안 나도 기록에는 지장 없음 */ }
  }

  return Object.fromEntries(Object.entries(TUNES).map(([name, notes]) => [name, () => play(notes)]));
}
