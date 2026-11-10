// 호출어 음성 모델(Vosk 한국어 작은 모델, voice/README.md)을 열고 마이크 소리를 넣는 부분.
// 거실 앱(ui/wake-listener.js)과 시험 화면(voice-test.html)이 같이 쓴다.
//
//   openWakeModel()  모델 조각 두 개를 받아(한 번 받으면 기기 캐시에 보관) 엔진에 연다. 처음엔 1분쯤
//   listenMic(model, grammar, on)  마이크 → 인식기. 결과마다 on.result(res)
//
// 소리는 기기 밖으로 나가지 않는다.

const BASE = new URL('../', import.meta.url);
const ENGINE = new URL('vendor/vosk-browser-0.0.8.js', BASE).href;
const PARTS = ['voice/model-ko.tar.gz.0', 'voice/model-ko.tar.gz.1'].map((p) => new URL(p, BASE).href);
const PART_BYTES = [47185920, 39730838];
const MODEL_NAME = 'ko-small-0.22';            // 엔진 안에서 이 이름으로 푼다(vendor 수정 참고)
const CACHE = 'voice-model-ko-small-0.22';     // 'albam-' 로 시작하지 않아 앱 업데이트 때 지워지지 않는다

/** 엔진(5MB)은 쓸 때만 불러온다 */
function loadEngine() {
  if (window.Vosk) return Promise.resolve(window.Vosk);
  return new Promise((resolve, reject) => {
    const s = Object.assign(document.createElement('script'), { src: ENGINE });
    s.onload = () => resolve(window.Vosk);
    s.onerror = () => reject(new Error('음성 엔진을 못 불러왔어요'));
    document.head.append(s);
  });
}

/** 모델 조각 두 개를 받아 하나의 blob 주소로. onProgress(0~1, 글) */
async function modelUrl(onProgress) {
  const cache = await caches.open(CACHE);
  const blobs = [];
  const total = PART_BYTES.reduce((a, b) => a + b, 0);
  let done = 0;
  for (const [i, part] of PARTS.entries()) {
    // 예전 시험 화면은 상대 주소('voice/…')로 보관했다. 둘 다 찾아 다시 받지 않게 한다
    let res = (await cache.match(part)) || (await cache.match(part.slice(BASE.href.length)));
    if (!res) {
      const r = await fetch(part, { cache: 'no-store' });
      if (!r.ok) throw new Error(`모델 조각을 못 받았어요(${r.status})`);
      const reader = r.body.getReader();
      const chunks = [];
      for (;;) {
        const { done: end, value } = await reader.read();
        if (end) break;
        chunks.push(value);
        done += value.length;
        onProgress(done / total, `모델 받는 중 ${Math.round(done / 1048576)} / ${Math.round(total / 1048576)}MB`);
      }
      res = new Response(new Blob(chunks));
      await cache.put(part, res.clone());
    } else {
      done += PART_BYTES[i];
      onProgress(done / total, '모델 준비 중');
    }
    blobs.push(await res.blob());
  }
  return `${URL.createObjectURL(new Blob(blobs, { type: 'application/gzip' }))}#${MODEL_NAME}`;
}

/**
 * @param {(fraction: number, text: string) => void} [onProgress]
 * @returns {Promise<any>} Vosk 모델
 */
export async function openWakeModel(onProgress = () => {}) {
  const Vosk = await loadEngine();
  const url = await modelUrl(onProgress);
  onProgress(1, '모델 여는 중(처음엔 1분쯤)');
  return Vosk.createModel(url);
}

/**
 * 마이크 → 인식기. 크롬은 MediaStreamTrackProcessor 로 소리를 받는다(화면을 누르지 않아도 돈다:
 * 새벽에 앱이 새로 고쳐져도 계속 듣게). 없으면 AudioContext(누르기 전엔 멈춰 있을 수 있어 첫 터치 때 다시 켠다).
 * @param {any} model
 * @param {string} grammar
 * @param {{result: (res: any) => void, partial?: (text: string) => void}} on
 * @returns {Promise<{stop: () => void, path: 'track'|'audio'}>}
 */
export async function listenMic(model, grammar, on) {
  const stream = await navigator.mediaDevices.getUserMedia({ video: false, audio: { echoCancellation: true, noiseSuppression: true, channelCount: 1 } });
  const [track] = stream.getAudioTracks();
  let rec = null;
  let stopped = false;
  const makeRecognizer = (rate) => {
    rec = new model.KaldiRecognizer(rate, grammar);
    rec.setWords(true);
    rec.on('result', (m) => { if (!stopped && m.result?.text) on.result(m.result); });
    rec.on('partialresult', (m) => { if (!stopped) on.partial?.(m.result?.partial || ''); });
  };
  const cleanup = [];
  const stop = () => {
    stopped = true;
    cleanup.forEach((f) => { try { f(); } catch (e) { /* 이미 멈춤 */ } });
    track.stop();
    try { rec?.remove(); } catch (e) { /* 이미 지움 */ }
  };

  if ('MediaStreamTrackProcessor' in window) {
    const reader = new window.MediaStreamTrackProcessor({ track }).readable.getReader();
    cleanup.push(() => reader.cancel());
    (async () => {
      let buf = null;
      while (!stopped) {
        const { value: frame, done } = await reader.read().catch(() => ({ done: true }));
        if (done) break;
        try {
          if (!rec) makeRecognizer(frame.sampleRate);
          const n = frame.numberOfFrames;
          if (!buf || buf.length !== n) buf = new Float32Array(n);
          frame.copyTo(buf, { planeIndex: 0, format: 'f32-planar' });
          rec.acceptWaveformFloat(buf, frame.sampleRate);
        } catch (e) { /* 한 조각 실패는 넘긴다 */ }
        frame.close();
      }
    })();
    return { stop, path: 'track' };
  }

  const ctx = new AudioContext();
  makeRecognizer(ctx.sampleRate);
  const node = ctx.createScriptProcessor(4096, 1, 1);
  node.onaudioprocess = (e) => { try { if (!stopped) rec.acceptWaveform(e.inputBuffer); } catch (x) { /* 한 조각 실패는 넘긴다 */ } };
  ctx.createMediaStreamSource(stream).connect(node);
  node.connect(ctx.destination);   // 일부 브라우저는 출력에 이어야 돈다(소리는 나지 않는다: 출력 버퍼를 채우지 않음)
  const resume = () => { if (ctx.state === 'suspended') ctx.resume(); };
  resume();
  window.addEventListener('pointerdown', resume, true);
  cleanup.push(() => window.removeEventListener('pointerdown', resume, true), () => node.disconnect(), () => ctx.close());
  return { stop, path: 'audio' };
}
