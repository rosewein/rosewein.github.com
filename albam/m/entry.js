// 다른 종류 넣기 창(더 넣기에서): 기록 종류 표의 모양(shape)을 따른다.
//   instant  시각 + 메모            (투약, 병원, 예방접종)
//   range    시작 + [끝 시각] + 메모 (산책, 목욕, 놀이 …). 처음엔 10분 전~지금
//   number   시각 + 숫자 ± + 메모    (체온, 체중, 키). 체중·키는 지난번 값에서 시작하고 성장 백분위를 보여 준다
//   text     시각 + 메모(꼭)         (메모)
// 시각은 폰의 기본 날짜·시간 고르기를 쓴다. 미래 시각은 서버가 받지 않아서 여기서도 막는다.

import { SOURCE, recordType, formatValue } from '../src/domain.js';
import { pad2 } from '../src/time.js';
import { memoHas, toggleMemo } from './phrases.js';

const $ = (s) => document.querySelector(s);
const DEFAULT_RANGE_MIN = 10;
const MEMO_HINT = { medication: '약 이름', hospital: '병원 · 사유', play: '무슨 놀이', bath: '예: 보습로션', vaccine: '백신 이름', other: '무엇' };

/** Date → datetime-local 값("2026-11-14T09:30", 기기 시간대) */
export const toLocalInput = (d) => `${d.getFullYear()}-${pad2(d.getMonth() + 1)}-${pad2(d.getDate())}T${pad2(d.getHours())}:${pad2(d.getMinutes())}`;

/**
 * 창에 넣은 값 → 기록, 또는 못 넣는 이유(순수 함수)
 * @param {{kind: string, shape: string, start: Date, hasEnd: boolean, end: Date|null, value: number|null, memo: string,
 *          min?: number|null, max?: number|null}} f
 * @param {Date} now
 * @returns {{ev?: object, error?: string}}
 */
export function buildEvent(f, now) {
  if (!(f.start instanceof Date) || Number.isNaN(f.start.getTime())) return { error: '시각을 넣어 주세요' };
  if (f.start > now) return { error: '아직 안 온 시각이에요' };
  const ev = { kind: f.kind, occurred_at: f.start, detail: {}, source: SOURCE.PHONE };
  if (f.shape === 'range' && f.hasEnd) {
    if (!f.end || Number.isNaN(f.end.getTime())) return { error: '끝 시각을 넣어 주세요' };
    if (f.end > now) return { error: '끝이 아직 안 온 시각이에요' };
    if (f.end - f.start < 60000) return { error: '끝이 시작보다 뒤여야 해요' };
    ev.ended_at = f.end;
  }
  if (f.shape === 'number') {
    if (f.value == null || Number.isNaN(f.value)) return { error: '숫자를 넣어 주세요' };
    if ((f.min != null && f.value < f.min) || (f.max != null && f.value > f.max)) return { error: `${f.min}~${f.max} 사이로 넣어 주세요` };
    ev.value_num = f.value;
  }
  const memo = f.memo.trim();
  if (f.shape === 'text' && !memo) return { error: '메모를 써 주세요' };
  if (memo) ev.detail = { memo };
  return { ev };
}

/** @param {{now: () => Date, save: Function, measures: {last: Function, note: Function, percentileText: Function}, phrases: {renderChips: Function}}} ctx */
export function setupEntry(ctx) {
  const dialog = $('#entry');
  let type = null;
  const read = (id) => { const v = $(id).value; return v ? new Date(v) : null; };
  const step = () => Number(type?.step || 1);
  const digits = () => Math.max(0, Math.round(-Math.log10(step())));
  const value = () => { const v = $('#entryValue').value; return v === '' ? null : Number(v); };

  function renderPercentile() {
    $('#entryPercentile').textContent = type?.shape === 'number' ? ctx.measures.percentileText(type.key, value(), read('#entryStart') ?? ctx.now()) : '';
  }
  /** 그 종류의 자주 쓰는 문구: 누르면 메모 칸에 들어가고 빠진다 */
  function renderChips() {
    if (!type) return;
    ctx.phrases.renderChips($('#entryChips'), type.key, {
      isOn: (text) => memoHas($('#entryMemo').value, text),
      onToggle: (text) => { $('#entryMemo').value = toggleMemo($('#entryMemo').value, text); renderChips(); },
    });
  }
  function renderEnd() {
    $('#entryEndField').hidden = !(type?.shape === 'range' && $('#entryHasEnd').checked);
    $('#entryStartLabel').textContent = !$('#entryEndField').hidden ? '시작' : '시각';
  }

  function open(kind) {
    type = recordType(kind);
    if (!type) return;
    const now = ctx.now();
    now.setSeconds(0, 0);
    const range = type.shape === 'range';
    $('#entryTitle').textContent = `${type.label} 넣기`;
    $('#entryStart').value = toLocalInput(range ? new Date(now - DEFAULT_RANGE_MIN * 60000) : now);
    $('#entryEnd').value = toLocalInput(now);
    for (const id of ['#entryStart', '#entryEnd']) $(id).max = toLocalInput(now);
    $('#entryEndToggle').hidden = !range;
    $('#entryHasEnd').checked = range;
    $('#entryNumber').hidden = type.shape !== 'number';
    if (type.shape === 'number') {
      const start = ctx.measures.last(kind) ?? type.default ?? 0;
      $('#entryValue').value = Number(start).toFixed(digits());
      $('#entryValue').step = String(step());
      for (const b of dialog.querySelectorAll('[data-n]')) {
        const d = Number(b.dataset.n) * step();
        b.textContent = `${d > 0 ? '+' : '-'}${formatValue({ step: step() }, Math.abs(d))}`;
      }
    }
    $('#entryMemo').value = '';
    $('#entryMemo').placeholder = MEMO_HINT[kind] || '';
    $('#entryMsg').textContent = '';
    renderChips();
    renderEnd();
    renderPercentile();
    dialog.showModal();
  }

  for (const b of dialog.querySelectorAll('[data-n]')) {
    b.addEventListener('click', () => {
      const next = (value() ?? type.default ?? 0) + Number(b.dataset.n) * step();
      const clamped = Math.min(type.max ?? Infinity, Math.max(type.min ?? -Infinity, next));
      $('#entryValue').value = clamped.toFixed(digits());
      renderPercentile();
    });
  }
  $('#entryMemo').addEventListener('input', renderChips);
  $('#entryValue').addEventListener('input', renderPercentile);
  $('#entryStart').addEventListener('change', renderPercentile);
  $('#entryHasEnd').addEventListener('change', renderEnd);
  $('#entryClose').addEventListener('click', () => dialog.close());

  $('#entryForm').addEventListener('submit', (e) => {
    e.preventDefault();
    const { ev, error } = buildEvent({
      kind: type.key, shape: type.shape, start: read('#entryStart'), hasEnd: $('#entryHasEnd').checked, end: read('#entryEnd'),
      value: value(), memo: $('#entryMemo').value, min: type.min, max: type.max,
    }, ctx.now());
    if (error) { $('#entryMsg').textContent = error; return; }
    if (ev.value_num != null) ctx.measures.note(ev.kind, ev.value_num, ev.occurred_at);
    dialog.close();
    ctx.save(ev);
  });

  return { open, refreshChips: () => { if (dialog.open) renderChips(); } };
}
