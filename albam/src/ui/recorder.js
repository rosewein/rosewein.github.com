// 기록 저장의 공통 흐름. 버튼·음성·지난 기록 화면이 모두 save() 하나로 저장한다.
//
//   save(ev)
//    ├ 비슷한 기록이 있음(confirm) → 확인 창 → [그래도 저장] → save(ev, {force: true})
//    ├ 저장됨/대기(queued) → 효과음, 캐릭터 기쁨, 버튼 자리에 "저장됨 + [취소 n]"
//    └ 실패 → 아래 알림 막대에 이유, 로그인 문제면 로그인 창
//   wake(sleep)  자는 중인 잠에 끝(지금)을 넣는다. [취소]를 누르면 다시 자는 중으로
//
// 아래 알림 막대(#notice)는 저장·취소 결과를 잠깐 보여 준다. 말풍선은 알밤이 하는 말만 쓴다.

import { $, setHidden } from './dom.js';
import { closeSheets, openSheet } from './sheets.js';
import { AuthError } from '../api/index.js';
import { describeEvent } from '../domain.js';
import { formatClock, formatDuration } from '../time.js';

const HAPPY_MS = 3000;
const NOTICE_MS = 3000;

/** @param {import('../main.js').AppContext} ctx */
export function setupRecorder(ctx) {
  const { state, cfg, sfx } = ctx;
  /** 확인 창이 떠 있는 동안 저장하려던 기록 */
  let waitingConfirm = null;
  /** 취소 버튼이 떠 있는 동안의 기록 */
  let undo = null;
  let noticeTimer = null;

  async function save(ev, opts = {}) {
    let result;
    try {
      result = await ctx.api.addEvent(ev, opts);
    } catch (e) {
      sfx.error();
      if (e instanceof AuthError) ctx.showLogin('다시 로그인해 주세요');
      else notify('저장 못 했어요', 'warn');
      console.error(e);
      return;
    }

    if (result.status === 'confirm') {
      askConfirm({ ...ev, id: result.id }, result.existing);
      return;
    }
    closeSheets();
    sfx.save();
    state.happyUntil = Date.now() + HAPPY_MS;
    showUndo(result.id, describeEvent(ev, ctx.now()) + (result.status === 'queued' ? ' (대기)' : ''));
    await ctx.refresh();
  }

  /** 깼어요: 자는 중인 잠에 끝을 넣는다 */
  async function wake(sleep) {
    const end = ctx.now();
    let result;
    try {
      result = await ctx.api.endSleep(sleep.id, end);
    } catch (e) {
      sfx.error();
      if (e instanceof AuthError) ctx.showLogin('다시 로그인해 주세요');
      else notify('저장 못 했어요', 'warn');
      console.error(e);
      return;
    }
    if (result.status === 'not_found') { sfx.error(); notify('자는 중인 잠을 못 찾았어요', 'warn'); await ctx.refresh(); return; }
    sfx.save();
    const text = `잠 ${formatDuration(end - new Date(sleep.at))}${result.status === 'queued' ? ' (대기)' : ''}`;
    showUndo(sleep.id, text, async () => { await ctx.api.endSleep(sleep.id, null); });
    await ctx.refresh();
  }

  // ── 비슷한 기록 확인 ──
  function askConfirm(ev, existing) {
    waitingConfirm = ev;
    const existingEv = { kind: existing.kind || ev.kind, occurred_at: existing.at, amount_ml: existing.ml, detail: existing.detail };
    const gapMin = Math.round(Math.abs(new Date(ev.occurred_at || ctx.now()) - new Date(existing.at)) / 60000);
    $('#confirmText').replaceChildren(
      `${gapMin}분 차이로 비슷한 기록이 이미 있어요.`, document.createElement('br'),
      `있는 것: ${describeEvent(existingEv, ctx.now())} (${formatClock(existing.at)})`, document.createElement('br'),
      `넣을 것: ${describeEvent(ev, ctx.now())}`,
    );
    openSheet('confirmSheet');
    sfx.error();
  }
  $('#confirmYes').addEventListener('click', () => {
    const ev = waitingConfirm;
    waitingConfirm = null;
    if (ev) save(ev, { force: true });
  });
  $('#confirmNo').addEventListener('click', () => {
    waitingConfirm = null;
    sfx.cancel();
    closeSheets();
    notify('안 넣었어요');
  });

  // ── 아래 알림 막대: 저장·취소 결과를 잠깐 ──
  /** @param {'warn'|''} [tone] */
  function notify(text, tone = '') {
    hideUndo();
    clearTimeout(noticeTimer);
    const bar = $('#notice');
    bar.textContent = text;
    bar.className = `box${tone ? ` ${tone}` : ''}`;
    noticeTimer = setTimeout(() => setHidden(bar, true), NOTICE_MS);
  }
  const hideNotice = () => { clearTimeout(noticeTimer); setHidden($('#notice'), true); };
  $('#notice').addEventListener('click', hideNotice);

  // ── 저장 직후 취소 ──
  /** @param {() => Promise<any>} [revert] [취소]를 누르면 할 일. 없으면 그 기록을 취소 */
  function showUndo(id, text, revert) {
    hideUndo();
    hideNotice();
    const until = Date.now() + cfg.undoSeconds * 1000;
    const update = () => {
      const left = Math.ceil((until - Date.now()) / 1000);
      if (left <= 0) hideUndo();
      else $('#undoCount').textContent = String(left);
    };
    undo = { id, revert: revert ?? (() => ctx.api.cancelEvent(id)), timer: setInterval(update, 250) };
    $('#undoText').textContent = `${text} 저장됨`;
    setHidden($('#undo'), false);
    update();
  }
  function hideUndo() {
    if (undo) clearInterval(undo.timer);
    undo = null;
    setHidden($('#undo'), true);
  }
  $('#undoBtn').addEventListener('click', async () => {
    if (!undo) return;
    const { revert } = undo;
    hideUndo();
    try {
      await revert();
      sfx.cancel();
      state.happyUntil = 0;
      notify('취소했어요');
    } catch (e) {
      sfx.error();
      notify('취소 못 했어요', 'warn');
    }
    ctx.refresh();
  });
  // 알림 부분을 누르면 바로 버튼으로 돌아감
  $('#undoMsg').addEventListener('click', hideUndo);

  return { save, wake, notify, isUndoShowing: () => !!undo };
}
