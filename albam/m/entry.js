// 넣기·고치기 창. 새로 넣을 때는 더 넣기의 종류(기록 종류 표)로, 고칠 때는 기록 쪽에서 누른 기록으로 연다.
//
//   모양(shapeOf)       칸
//   feed    수유        시작 + [끝 시각](다 먹은 때) + 양 + 메모
//   diaper  기저귀      시각 + 종류(소변·대변·소+대) + 메모
//   range   잠·산책…    시작 + [끝 시각] + 메모          (잠은 끝을 끄면 '자는 중')
//   number  체온·체중…  시각 + 숫자 ± + 메모            (체중·키는 지난번 값에서 시작, 성장 백분위)
//   instant 투약·병원…  시각 + 메모
//   text    메모        시각 + 메모(꼭)
//
// 시각은 폰의 기본 날짜·시간 고르기를 쓴다. 미래 시각은 서버가 받지 않아서 여기서도 막는다.
// 고칠 때는 종류를 못 바꾼다. [지우기]는 두 번 눌러야 지워진다(지우지 않고 취소 표시).

import { KIND, SOURCE, recordType, formatValue } from '../src/domain.js';
import { pad2 } from '../src/time.js';
import { memoHas, toggleMemo } from './phrases.js';

const $ = (s) => document.querySelector(s);
const DEFAULT_RANGE_MIN = 10;
const DELETE_CONFIRM_MS = 3000;
const MEMO_HINT = { medication: '약 이름', hospital: '병원 · 사유', play: '무슨 놀이', bath: '예: 보습로션', vaccine: '백신 이름', other: '무엇' };
const BUILTIN_LABEL = { feed: '수유', diaper: '기저귀', sleep: '잠' };

/** Date → datetime-local 값("2026-11-14T09:30", 기기 시간대) */
export const toLocalInput = (d) => `${d.getFullYear()}-${pad2(d.getMonth() + 1)}-${pad2(d.getDate())}T${pad2(d.getHours())}:${pad2(d.getMinutes())}`;
/** 종류 → 창의 모양 */
export function shapeOf(kind) {
  if (kind === KIND.FEED) return 'feed';
  if (kind === KIND.DIAPER) return 'diaper';
  if (kind === KIND.SLEEP) return 'range';
  return recordType(kind)?.shape || 'instant';
}
export const labelOf = (kind) => BUILTIN_LABEL[kind] || recordType(kind)?.label || kind;

/**
 * 창에 넣은 값이 맞는지(순수 함수). 틀리면 이유, 맞으면 ''
 * @typedef {{kind: string, shape: string, start: Date|null, hasEnd: boolean, end: Date|null, value: number|null, memo: string,
 *            amount?: number|null, diaperType?: string, min?: number|null, max?: number|null}} Form
 * @param {Form} f
 * @param {Date} now
 */
export function checkForm(f, now) {
  if (!(f.start instanceof Date) || Number.isNaN(f.start.getTime())) return '시각을 넣어 주세요';
  if (f.start > now) return '아직 안 온 시각이에요';
  if ((f.shape === 'range' || f.shape === 'feed') && f.hasEnd) {
    if (!f.end || Number.isNaN(f.end.getTime())) return '끝 시각을 넣어 주세요';
    if (f.end > now) return '끝이 아직 안 온 시각이에요';
    // 같은 분은 받는다: 1분 안에 끝낸 수유를 고칠 때 막히지 않게(시각 칸은 분까지만 보인다)
    if (f.end < f.start) return '끝이 시작보다 뒤여야 해요';
  }
  if (f.shape === 'number') {
    if (f.value == null || Number.isNaN(f.value)) return '숫자를 넣어 주세요';
    if ((f.min != null && f.value < f.min) || (f.max != null && f.value > f.max)) return `${f.min}~${f.max} 사이로 넣어 주세요`;
  }
  if (f.shape === 'feed' && !(f.amount >= 0 && f.amount <= 1000)) return '양을 0~1000 사이로 넣어 주세요';
  if (f.shape === 'text' && !f.memo.trim()) return '메모를 써 주세요';
  return '';
}

/**
 * 새 기록(순수 함수)
 * @param {Form} f
 * @param {Date} now
 * @returns {{ev?: object, error?: string}}
 */
export function buildEvent(f, now) {
  const error = checkForm(f, now);
  if (error) return { error };
  const ev = { kind: f.kind, occurred_at: f.start, detail: {}, source: SOURCE.PHONE };
  if ((f.shape === 'range' || f.shape === 'feed') && f.hasEnd) ev.ended_at = f.end;
  if (f.shape === 'number') ev.value_num = f.value;
  if (f.shape === 'feed') ev.amount_ml = f.amount;
  if (f.shape === 'diaper') ev.detail.type = f.diaperType;
  const memo = f.memo.trim();
  if (memo) ev.detail.memo = memo;
  return { ev };
}

/**
 * 고칠 내용(순수 함수). care_update_event 는 detail 을 있는 값에 합치므로 메모를 비우려면 '' 를 보낸다
 * @param {Form} f
 * @param {Date} now
 * @returns {{patch?: object, error?: string}}
 */
export function buildPatch(f, now) {
  const error = checkForm(f, now);
  if (error) return { error };
  const patch = { occurred_at: f.start, detail: { memo: f.memo.trim() } };
  if (f.shape === 'range' || f.shape === 'feed') patch.ended_at = f.hasEnd ? f.end : null;
  // 끝을 넣은 수유는 더는 먹이는 중이 아니다. 끝을 안 넣으면 그대로(먹이는 중이면 계속)
  if (f.shape === 'feed') { patch.amount_ml = f.amount; if (f.hasEnd) patch.detail.feeding = false; }
  if (f.shape === 'number') patch.value_num = f.value;
  if (f.shape === 'diaper') patch.detail.type = f.diaperType;
  return { patch };
}

/**
 * @param {{now: () => Date, save: Function, update: (id: string, patch: object, label: string) => void, remove: (id: string, label: string) => void,
 *          measures: {last: Function, note: Function, percentileText: Function}, phrases: {renderChips: Function}}} ctx
 */
export function setupEntry(ctx) {
  const dialog = $('#entry');
  /** 지금 연 종류와 모양, 고치는 중이면 그 기록 */
  let kind = '';
  let shape = '';
  let type = null;
  let editing = null;
  let diaperType = 'pee';
  let deleteArmedUntil = 0;
  const read = (id) => { const v = $(id).value; return v ? new Date(v) : null; };
  const step = () => Number(type?.step || 1);
  const digits = () => Math.max(0, Math.round(-Math.log10(step())));
  const num = (id) => { const v = $(id).value; return v === '' ? null : Number(v); };
  const hasEndToggle = () => shape === 'range' || shape === 'feed';

  function renderPercentile() {
    $('#entryPercentile').textContent = shape === 'number' ? ctx.measures.percentileText(kind, num('#entryValue'), read('#entryStart') ?? ctx.now()) : '';
  }
  /** 그 종류의 자주 쓰는 문구: 누르면 메모 칸에 들어가고 빠진다 */
  function renderChips() {
    if (!kind) return;
    ctx.phrases.renderChips($('#entryChips'), kind, {
      isOn: (text) => memoHas($('#entryMemo').value, text),
      onToggle: (text) => { $('#entryMemo').value = toggleMemo($('#entryMemo').value, text); renderChips(); },
    });
  }
  function renderEnd() {
    const on = hasEndToggle() && $('#entryHasEnd').checked;
    $('#entryEndField').hidden = !on;
    $('#entryStartLabel').textContent = on || kind === KIND.SLEEP ? '시작' : '시각';
  }
  function renderDiaper() {
    for (const b of dialog.querySelectorAll('[data-type]')) b.classList.toggle('on', b.dataset.type === diaperType);
  }
  function renderDelete() {
    const armed = Date.now() < deleteArmedUntil;
    $('#entryDelete').hidden = !editing;
    $('#entryDelete').textContent = armed ? '한 번 더 누르면 지워요' : '지우기';
    $('#entryDelete').classList.toggle('warnBtn', armed);
  }

  /** 칸을 채우고 창을 연다 */
  function fill({ start, end, hasEnd, value, amount, memo }) {
    const now = ctx.now();
    $('#entryTitle').textContent = editing ? `기록 고치기 · ${labelOf(kind)}` : `${labelOf(kind)} 넣기`;
    $('#entryStart').value = toLocalInput(start);
    $('#entryEnd').value = toLocalInput(end);
    for (const id of ['#entryStart', '#entryEnd']) $(id).max = toLocalInput(now);
    $('#entryEndToggle').hidden = !hasEndToggle();
    $('#entryEndToggleText').textContent = kind === KIND.SLEEP ? '깬 시각도 넣기(끄면 자는 중)' : kind === KIND.FEED ? '다 먹은 시각도 넣기' : '끝 시각도 넣기';
    $('#entryHasEnd').checked = hasEnd;
    $('#entryNumber').hidden = shape !== 'number';
    if (shape === 'number') {
      $('#entryValue').value = Number(value).toFixed(digits());
      $('#entryValue').step = String(step());
      for (const b of dialog.querySelectorAll('[data-n]')) {
        const d = Number(b.dataset.n) * step();
        b.textContent = `${d > 0 ? '+' : '-'}${formatValue({ step: step() }, Math.abs(d))}`;
      }
    }
    $('#entryAmountField').hidden = shape !== 'feed';
    $('#entryAmount').value = amount ?? '';
    $('#entryDiaper').hidden = shape !== 'diaper';
    renderDiaper();
    $('#entryMemo').value = memo;
    $('#entryMemo').placeholder = MEMO_HINT[kind] || '';
    $('#entryMsg').textContent = '';
    deleteArmedUntil = 0;
    renderDelete();
    renderChips();
    renderEnd();
    renderPercentile();
    dialog.showModal();
  }

  /** 새로 넣기(더 넣기에서) */
  function open(k) {
    if (!recordType(k)) return;
    kind = k; shape = shapeOf(k); type = recordType(k); editing = null;
    const now = ctx.now();
    now.setSeconds(0, 0);
    const range = shape === 'range';
    fill({
      start: range ? new Date(now - DEFAULT_RANGE_MIN * 60000) : now, end: now, hasEnd: range,
      value: ctx.measures.last(k) ?? type.default ?? 0, amount: null, memo: '',
    });
  }

  /** 고치기(기록 쪽에서 누른 기록) */
  function openEdit(e) {
    kind = e.kind; shape = shapeOf(e.kind); type = recordType(e.kind) || null; editing = e;
    diaperType = e.type || 'pee';
    const now = ctx.now();
    now.setSeconds(0, 0);
    fill({
      start: new Date(e.at), end: e.ended_at ? new Date(e.ended_at) : now, hasEnd: !!e.ended_at,
      value: e.value ?? type?.default ?? 0, amount: e.ml, memo: e.detail?.memo ?? e.memo ?? '',
    });
  }

  const form = () => ({
    kind, shape, start: read('#entryStart'), hasEnd: hasEndToggle() && $('#entryHasEnd').checked, end: read('#entryEnd'),
    value: num('#entryValue'), amount: num('#entryAmount'), diaperType, memo: $('#entryMemo').value, min: type?.min, max: type?.max,
  });

  for (const b of dialog.querySelectorAll('[data-n]')) {
    b.addEventListener('click', () => {
      const next = (num('#entryValue') ?? type.default ?? 0) + Number(b.dataset.n) * step();
      $('#entryValue').value = Math.min(type.max ?? Infinity, Math.max(type.min ?? -Infinity, next)).toFixed(digits());
      renderPercentile();
    });
  }
  for (const b of dialog.querySelectorAll('[data-type]')) {
    b.addEventListener('click', () => { diaperType = b.dataset.type; renderDiaper(); });
  }
  $('#entryMemo').addEventListener('input', renderChips);
  $('#entryValue').addEventListener('input', renderPercentile);
  $('#entryStart').addEventListener('change', renderPercentile);
  $('#entryHasEnd').addEventListener('change', renderEnd);
  $('#entryClose').addEventListener('click', () => dialog.close());
  $('#entryDelete').addEventListener('click', () => {
    if (!editing) return;
    if (Date.now() < deleteArmedUntil) { dialog.close(); ctx.remove(editing.id, labelOf(kind)); return; }
    deleteArmedUntil = Date.now() + DELETE_CONFIRM_MS;
    renderDelete();
    setTimeout(renderDelete, DELETE_CONFIRM_MS + 50);
  });

  $('#entryForm').addEventListener('submit', (e) => {
    e.preventDefault();
    const now = ctx.now();
    if (editing) {
      const { patch, error } = buildPatch(form(), now);
      if (error) { $('#entryMsg').textContent = error; return; }
      dialog.close();
      ctx.update(editing.id, patch, labelOf(kind));
      return;
    }
    const { ev, error } = buildEvent(form(), now);
    if (error) { $('#entryMsg').textContent = error; return; }
    if (ev.value_num != null) ctx.measures.note(ev.kind, ev.value_num, ev.occurred_at);
    dialog.close();
    ctx.save(ev);
  });

  return { open, openEdit, refreshChips: () => { if (dialog.open) renderChips(); } };
}
