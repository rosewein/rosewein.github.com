// 음성 입력. 아기를 안고 있어서 버튼을 고르기 어려울 때 쓴다. 두 가지:
//
//   호출어(마이크 버튼으로 켜고 끔, 처음엔 꺼짐): "알밤이 쉬야했어"처럼 부르면 기록
//     마이크 켬 → 모델 열기(처음엔 1분쯤) → 계속 듣는 중(버튼 주황) → 알아들음
//       → 확인 화면(크게) → n초 뒤 자동 저장 / 그 전에 누르면 취소(시험 기록에 [잘못]으로 남김)
//     인식은 기기 안 Vosk 모델(../voice-model.js), 말 → 종류는 ../voice-wake.js.
//     켜 둔 상태는 기기에 기억해서 새로 고쳐도 다시 듣는다. 밤새 아기 소리로 기록되지 않게 필요할 때만 켠다
//
//   한 번 듣기(listen(), 지금은 버튼 없음. 호출어 전에 마이크 버튼이 하던 일): 듣는 중 → 알아들음
//     ├ 규칙으로 알아들음 → 확인 화면(크게) → n초 뒤 자동 저장 / 그 전에 누르면 취소
//     └ 못 알아들음      → 원문을 보여 주고 [다시 말하기]
//     인식은 크롬의 Web Speech API(ko-KR), 문장 해석은 ../voice-parse.js.

import { $, setHidden } from './dom.js';
import { closeSheets, isSheetOpen, openSheet } from './sheets.js';
import { SOURCE } from '../domain.js';
import { parseUtterance } from '../voice-parse.js';
import { detectWakeAll, wakeAction, WAKE_GRAMMAR } from '../voice-wake.js';

const WAKE_KEY = 'albam.wake';   // 'on' 이면 켜고 시작
const DEVICE = `${screen.width}x${screen.height} ${/Android/.test(navigator.userAgent) ? 'Android' : 'other'} app`;

const Recognition = window.SpeechRecognition || window.webkitSpeechRecognition;
const EXAMPLES = '예: 수유 200 · 브레짜 210 · 기저귀 대변 · 잠 1시부터 2시 40분까지';
const ERROR_TEXT = {
  'not-allowed': '마이크 권한을 허용해 주세요',
  'service-not-allowed': '마이크 권한을 허용해 주세요',
  'no-speech': '아무 말도 못 들었어요',
  network: '음성 인식은 인터넷이 필요해요',
};

/** @param {import('../main.js').AppContext} ctx */
export function setupVoiceInput(ctx) {
  const { cfg, sfx } = ctx;
  /** @type {'idle'|'listening'|'confirm'} */
  let phase = 'idle';
  let recognition = null;
  let countdown = null;
  /** 확인 화면이 끝나면 할 일 */
  let pendingEvent = null;

  /** 음성 창 내용 바꾸기 */
  function show({ title, label = '', raw = '', retry = false, bar = false }) {
    $('#voiceTitle').textContent = title;
    $('#voiceLabel').textContent = label;
    $('#voiceRaw').textContent = raw;
    setHidden($('#voiceRetry'), !retry);
    setHidden($('#voiceBar'), !bar);
    openSheet('voiceSheet');
  }

  function stop() {
    clearInterval(countdown);
    countdown = null;
    try { recognition?.abort(); } catch (e) { /* 이미 끝남 */ }
    recognition = null;
    phase = 'idle';
  }

  function listen() {
    stop();
    if (!Recognition) {
      show({ title: '음성 인식을 쓸 수 없어요', raw: '안드로이드 크롬에서 열어 주세요' });
      return;
    }
    const rec = new Recognition();
    Object.assign(rec, { lang: 'ko-KR', interimResults: true, maxAlternatives: 5, continuous: false });
    recognition = rec;
    phase = 'listening';
    let gotFinal = false;
    show({ title: '듣는 중… 말해 주세요', raw: EXAMPLES });
    sfx.listen();

    rec.onresult = (e) => {
      const result = e.results[e.results.length - 1];
      $('#voiceLabel').textContent = result[0].transcript;   // 듣는 동안 중간 결과
      if (result.isFinal) {
        gotFinal = true;
        understand([...result].map((alt) => alt.transcript));
      }
    };
    rec.onerror = (e) => {
      if (phase !== 'listening') return;   // 우리가 멈춘 것
      gotFinal = true;
      stop();
      sfx.error();
      show({ title: ERROR_TEXT[e.error] || `음성 인식 오류 (${e.error})`, retry: true });
    };
    rec.onend = () => {
      if (gotFinal || phase !== 'listening') return;
      stop();
      show({ title: '아무 말도 못 들었어요', retry: true });
    };
    try { rec.start(); } catch (e) { stop(); show({ title: '음성 인식을 시작하지 못했어요', retry: true }); }
  }

  /** 인식 후보 여러 개 중 규칙에 맞는 첫 번째를 쓴다 */
  function understand(alternatives) {
    stop();
    const now = ctx.now();
    for (const text of alternatives) {
      const parsed = parseUtterance(text, now, { formula: cfg.formula, machine: cfg.machine });
      if (parsed.ok) return confirmThenSave({ ...parsed.event, source: SOURCE.VOICE, voice_text: text }, parsed.label, text);
    }
    sfx.error();
    show({ title: '못 알아들었어요. 다시 말해 주세요', label: `“${alternatives[0] || ''}”`, raw: EXAMPLES, retry: true });
  }

  /** 크게 띄우고 막대가 줄어들다 0이 되면 저장 */
  function confirmThenSave(event, label, heard) {
    confirmThen(() => ctx.save(event), label, heard);
  }

  /** 크게 띄우고 막대가 줄어들다 0이 되면 run() */
  function confirmThen(run, label, heard) {
    phase = 'confirm';
    pendingEvent = run;
    show({ title: '이렇게 넣을게요 · 누르면 취소', label, raw: heard ? `“${heard}”` : '', bar: true });
    ctx.tick();   // 밤 검은 화면이면 걷어 낸다(isBusy)
    const total = cfg.voiceConfirmSeconds * 1000;
    const until = Date.now() + total;
    countdown = setInterval(() => {
      const left = until - Date.now();
      $('#voiceBarFill').style.width = `${Math.max(0, (left / total) * 100)}%`;
      if (left > 0) return;
      const go = pendingEvent;
      pendingWake = null;
      stop();
      go();
    }, 50);
  }

  function cancel() {
    const wasConfirming = phase === 'confirm';
    stop();
    closeSheets();
    if (wasConfirming) {
      sfx.cancel();
      ctx.notify('안 넣었어요');
      if (pendingWake) logVoice({ ...pendingWake, wrong: true });   // 호출어를 잘못 알아들음
    }
    pendingWake = null;
  }

  // ── 호출어 ──
  let wakeOn = false;
  let wake = null;          // listenMic 결과
  let model = null;
  let starting = null;
  let pendingWake = null;   // 확인 중인 호출어의 기록(취소하면 wrong)

  const readWake = () => { try { return localStorage.getItem(WAKE_KEY) === 'on'; } catch (e) { return false; } };
  const writeWake = (on) => { try { localStorage.setItem(WAKE_KEY, on ? 'on' : 'off'); } catch (e) { /* 기억 못 해도 지금은 그대로 */ } };
  function setWakeButton(mode) {
    const b = $('#micBtn');
    b.classList.toggle('listening', mode === 'on');
    b.classList.toggle('loading', mode === 'loading');
    const label = { on: '호출어 듣는 중(누르면 끔)', loading: '호출어 준비 중', off: '호출어 꺼짐(누르면 켬)' }[mode];
    b.setAttribute('aria-label', label);
    b.title = label;
  }

  function logVoice(row) {
    ctx.api.logVoice?.({ device: DEVICE, ...row }).catch?.(() => {});
  }
  const wordsOf = (res) => (res.result?.length ? res.result.map((w) => `${w.word}(${w.conf.toFixed(2)})`).join(' ') : res.text);

  async function startWake() {
    if (wake || starting) return;
    setWakeButton('loading');
    starting = (async () => {
      try {
        model ??= await openWakeModelLazy((f, text) => { if (f < 1) $('#micBtn').dataset.progress = String(Math.round(f * 100)); else delete $('#micBtn').dataset.progress; void text; });
        if (!wakeOn) return;
        wake = await listenMicLazy(model, WAKE_GRAMMAR, { result: onWakeResult });
        if (!wakeOn) { wake.stop(); wake = null; return; }
        setWakeButton('on');
        ctx.notify('“알밤이 …” 들을게요');
      } catch (e) {
        console.error(e);
        wakeOn = false;
        writeWake(false);
        setWakeButton('off');
        sfx.error();
        ctx.notify(/Permission|NotAllowed/i.test(`${e.name} ${e.message}`) ? '마이크 권한을 허용해 주세요' : '호출어를 못 켰어요', 'warn');
      } finally {
        starting = null;
      }
    })();
    return starting;
  }

  function stopWake() {
    wake?.stop();
    wake = null;
    setWakeButton('off');
  }

  function toggleWake() {
    wakeOn = !wakeOn;
    writeWake(wakeOn);
    sfx.tap();
    if (wakeOn) startWake();
    else { stopWake(); ctx.notify('호출어 껐어요'); }
  }

  /** Vosk 결과 하나 → 알아들은 명령이 있으면 확인 화면. 창이 열려 있거나 확인 중이면 넘긴다 */
  function onWakeResult(res) {
    const hits = detectWakeAll(res);
    const heard = wordsOf(res);
    const at = new Date().toISOString();
    if (!hits.length) {
      if (/알밤 이/.test(res.text || '')) logVoice({ id: crypto.randomUUID(), heard_at: at, event: 'unsure', kind: null, conf: null, heard, wrong: false });
      return;
    }
    const rows = hits.map((h) => ({ id: crypto.randomUUID(), heard_at: at, event: 'hit', kind: h.kind, conf: Number(h.conf.toFixed(2)), heard, wrong: false }));
    rows.forEach(logVoice);
    if (phase !== 'idle' || isSheetOpen()) return;   // 다른 일을 하는 중(뒤 문장은 기록에만 남긴다)
    const action = wakeAction({ ...hits[0], text: res.text }, ctx.state.summary, ctx.now(), cfg);
    if (action.do === 'notice') { sfx.error(); ctx.notify(action.text); return; }
    pendingWake = rows[0];
    sfx.listen();
    const run = {
      save: () => ctx.save(action.event),
      wake: () => ctx.wake(action.sleep),
      finishFeed: () => ctx.finishFeed(action.feed),
    }[action.do];
    confirmThen(run, action.label, res.text);
  }

  $('#micBtn').addEventListener('click', () => (phase === 'listening' ? cancel() : toggleWake()));
  $('#voiceRetry').addEventListener('click', (e) => { e.stopPropagation(); listen(); });
  $('#voiceCancel').addEventListener('click', (e) => { e.stopPropagation(); cancel(); });
  // 확인 중에는 창 어디를 눌러도 취소
  $('#voiceSheet').addEventListener('click', () => { if (phase === 'confirm') cancel(); });

  wakeOn = readWake();
  setWakeButton('off');
  if (wakeOn) startWake();

  // 시험용(미리 보기에서만): Vosk 결과를 마이크 없이 넣어 본다
  if (ctx.api.demo) window.__albamWakeResult = onWakeResult;

  return { isBusy: () => phase !== 'idle', listen };
}

// 음성 엔진·모델은 호출어를 켤 때만 불러온다(앱 첫 화면을 가볍게)
const openWakeModelLazy = async (onProgress) => (await import('../voice-model.js')).openWakeModel(onProgress);
const listenMicLazy = async (...args) => (await import('../voice-model.js')).listenMic(...args);
