// 음성 입력. 아기를 안고 있어서 버튼을 고르기 어려울 때 쓴다.
//
//   [말하기] 한 번 누름 → 듣는 중 → 알아들음
//     ├ 규칙으로 알아들음 → 확인 화면(크게) → n초 뒤 자동 저장 / 그 전에 누르면 취소
//     └ 못 알아들음      → 원문을 보여 주고 [다시 말하기]
//
// 인식은 크롬의 Web Speech API(ko-KR), 문장 해석은 ../voice-parse.js.

import { $, setHidden } from './dom.js';
import { closeSheets, openSheet } from './sheets.js';
import { SOURCE } from '../domain.js';
import { parseUtterance } from '../voice-parse.js';

const Recognition = window.SpeechRecognition || window.webkitSpeechRecognition;
const EXAMPLES = '예: 수유 160 · 기저귀 대변 · 잠 1시부터 2시 40분까지';
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

  const setMic = (listening) => $('#micBtn').classList.toggle('listening', listening);

  function stop() {
    clearInterval(countdown);
    countdown = null;
    try { recognition?.abort(); } catch (e) { /* 이미 끝남 */ }
    recognition = null;
    phase = 'idle';
    setMic(false);
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
    setMic(true);
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
      const parsed = parseUtterance(text, now);
      if (parsed.ok) return confirmThenSave({ ...parsed.event, source: SOURCE.VOICE, voice_text: text }, parsed.label, text);
    }
    sfx.error();
    show({ title: '못 알아들었어요. 다시 말해 주세요', label: `“${alternatives[0] || ''}”`, raw: EXAMPLES, retry: true });
  }

  /** 크게 띄우고 막대가 줄어들다 0이 되면 저장 */
  function confirmThenSave(event, label, heard) {
    phase = 'confirm';
    pendingEvent = event;
    show({ title: '이렇게 넣을게요 · 누르면 취소', label, raw: `“${heard}”`, bar: true });
    const total = cfg.voiceConfirmSeconds * 1000;
    const until = Date.now() + total;
    countdown = setInterval(() => {
      const left = until - Date.now();
      $('#voiceBarFill').style.width = `${Math.max(0, (left / total) * 100)}%`;
      if (left > 0) return;
      const ev = pendingEvent;
      stop();
      ctx.save(ev);
    }, 50);
  }

  function cancel() {
    const wasConfirming = phase === 'confirm';
    stop();
    closeSheets();
    if (wasConfirming) { sfx.cancel(); ctx.say('안 넣었어요'); }
  }

  $('#micBtn').addEventListener('click', () => (phase === 'listening' ? cancel() : listen()));
  $('#voiceRetry').addEventListener('click', (e) => { e.stopPropagation(); listen(); });
  $('#voiceCancel').addEventListener('click', (e) => { e.stopPropagation(); cancel(); });
  // 확인 중에는 창 어디를 눌러도 취소
  $('#voiceSheet').addEventListener('click', () => { if (phase === 'confirm') cancel(); });

  return { isBusy: () => phase !== 'idle' };
}
