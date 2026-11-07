// [+] 더보기: 목욕·체온·투약·체중·키·메모… 를 고르는 창. 종류는 기록 종류 표(supabase/008)에서 온다.
// 하나를 누르면 지난 기록 넣기 창이 그 종류로 열린다(시각은 지금, 시작~끝 종류는 10분 전~지금).
// 표에 한 줄 더하면(show_in_more = true) 여기 버튼이 하나 늘어난다. 코드는 고치지 않아도 된다.

import { $, el } from './dom.js';
import { openSheet } from './sheets.js';
import { moreTypes } from '../domain.js';

/**
 * @param {import('../main.js').AppContext} ctx
 * @param {{openNew: (kind: string) => void, openLate: () => void, openDayList: (back: number) => void}} o
 */
export function setupMore(ctx, { openNew, openLate, openDayList }) {
  function open() {
    $('#moreGrid').replaceChildren(...moreTypes().map((t) => el('button', {
      className: 'px', onClick: () => { ctx.sfx.tap(); openNew(t.key); },
    }, t.label)));
    openSheet('moreSheet');
  }
  $('#lateBtn').addEventListener('click', () => { ctx.sfx.tap(); open(); });
  $('#moreLate').addEventListener('click', () => { ctx.sfx.tap(); openLate(); });
  $('#moreToday').addEventListener('click', () => { ctx.sfx.tap(); openDayList(0); });
  return { open };
}
