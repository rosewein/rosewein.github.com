// 덮는 창(.sheet). 한 번에 하나만 열린다.

import { $$, setHidden } from './dom.js';

export function openSheet(id) {
  for (const sheet of $$('.sheet')) setHidden(sheet, sheet.id !== id);
}

export function closeSheets() {
  for (const sheet of $$('.sheet')) setHidden(sheet, true);
}

export const isSheetOpen = () => $$('.sheet').some((s) => !s.classList.contains('hidden'));

/** [data-close] 버튼이 있는 창은 그 버튼으로 닫힌다 */
export function setupCloseButtons(onClose) {
  for (const btn of $$('[data-close]')) btn.addEventListener('click', () => { onClose(); closeSheets(); });
}
