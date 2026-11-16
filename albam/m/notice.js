// 아래 알림 막대: 저장·취소 결과를 잠깐 보여 주고, 저장 직후에는 [취소 n]을 같이 띄운다.
//   show('취소했어요')           3초 뒤 사라짐
//   showUndo('수유 200ml', fn)   config undoSeconds 동안 [취소 6] … 누르면 fn()

const NOTICE_MS = 3000;
const $ = (s) => document.querySelector(s);

/** @param {{undoSeconds: number, onUndone: () => void}} o */
export function createNotice({ undoSeconds, onUndone }) {
  const bar = $('#notice');
  const btn = $('#undoBtn');
  let timer = null;
  let undo = null;

  function hide() {
    clearTimeout(timer); clearInterval(timer);
    undo = null;
    bar.hidden = true;
  }

  /** @param {'warn'|''} [tone] */
  function show(text, tone = '') {
    hide();
    $('#noticeText').textContent = text;
    bar.className = tone;
    btn.hidden = true;
    bar.hidden = false;
    timer = setTimeout(hide, NOTICE_MS);
  }

  /** @param {() => Promise<any>} revert [취소]를 누르면 할 일 */
  function showUndo(text, revert) {
    hide();
    const until = Date.now() + undoSeconds * 1000;
    undo = revert;
    $('#noticeText').textContent = `${text} 저장됨`;
    bar.className = '';
    btn.hidden = false;
    bar.hidden = false;
    const tick = () => {
      const left = Math.ceil((until - Date.now()) / 1000);
      if (left <= 0) hide(); else btn.textContent = `취소 ${left}`;
    };
    tick();
    timer = setInterval(tick, 250);
  }

  btn.addEventListener('click', async () => {
    const revert = undo;
    if (!revert) return;
    hide();
    try { await revert(); show('취소했어요'); } catch (e) { show('취소 못 했어요', 'warn'); }
    onUndone();
  });

  return { show, showUndo, hide };
}
