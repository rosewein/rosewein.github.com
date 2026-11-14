// 설정 쪽: 다가오는 일정(넣기·고치기·지우기, 맞은 접종을 기록으로), 자주 쓰는 문구 모아 보기,
// 더 넣기 버튼 고르기·순서, 로그아웃.
//
//   다가오는 일정      12월 22일 화 예방접종 · 헥사심 3차 …   D-38 ›     [+ 일정 넣기]
//                      지난 2주 안의 일정도 남아 있다("3일 지남"): 접종한 날 [맞았어요]를 잊어도 나중에 옮길 수 있게
//   예방접종 일정표    맞음 14 · 예약 5 · 지금 맞을 때 0 · 시기 지남 0
//                      6개월(12/18~)  DTaP 3차 …… 예약 12/22         ← 표준예방접종일정표에 맞은 기록·예약을 맞춰 본다
//   자주 쓰는 문구     수유 · 유산균, 비타민D ›   목욕 · 보습로션 ›  …
//   더 넣기 버튼       [▲][▼] 산책 [보임]   …                        ← 모든 화면에 같이 적용
//
// 여기서 바꾼 것은 Supabase 에 들어가서 거실 화면·보드에도 같이 적용된다. 연결돼 있을 때만 된다.

import { SOURCE, isBuiltinKind, recordTypes } from '../src/domain.js';
import { describeAppointment } from '../src/ui/upcoming.js';
import { vaccineStatus, statusText } from '../src/vaccines.js';
import { dayKey } from './records.js';

const $ = (s) => document.querySelector(s);
const el = (tag, cls, text) => { const n = document.createElement(tag); if (cls) n.className = cls; if (text != null) n.textContent = text; return n; };
const DELETE_CONFIRM_MS = 3000;

/** "헥사심 3차, 독감 1차" → ['헥사심 3차', '독감 1차'](쉼표나 줄바꿈으로 나눔, 순수 함수) */
export const parseItems = (text) => String(text || '').split(/[,\n]/).map((s) => s.trim()).filter(Boolean);

/**
 * 일정 칸 → care_set_appointment 입력, 또는 못 넣는 이유(순수 함수)
 * @returns {{p?: object, error?: string}}
 */
export function buildAppointment({ id = null, on_date, at_time, title, place, items, note }) {
  if (!on_date) return { error: '날짜를 넣어 주세요' };
  if (!String(title || '').trim()) return { error: '무슨 일정인지 써 주세요' };
  const p = { on_date, at_time: at_time || '', title: title.trim(), place: (place || '').trim(), items: parseItems(items), note: (note || '').trim(),
    kind: /접종/.test(title) ? 'vaccine' : 'appointment' };
  if (id) p.id = id;
  return { p };
}

/**
 * 맞은 접종을 기록으로(순수 함수): 항목 하나에 예방접종 기록 한 줄. 항목이 없으면 일정 이름으로 한 줄.
 * 시각은 일정의 시각, 없으면 오늘이면 지금·지난 날이면 오전 9시.
 * @param {{on_date: string, at_time?: string|null, title: string, place?: string|null, items?: string[]}} a
 * @param {Date} now
 */
export function vaccineEvents(a, now) {
  const [y, m, d] = a.on_date.split('-').map(Number);
  const [hh, mm] = a.at_time ? a.at_time.split(':').map(Number) : (a.on_date === dayKey(now) ? [now.getHours(), now.getMinutes()] : [9, 0]);
  const at = new Date(y, m - 1, d, hh, mm);
  const when = at > now ? now : at;
  const items = a.items?.length ? a.items : [a.title];
  return items.map((text) => {
    const dose = /(\d+)\s*차/.exec(text);
    const detail = { vaccine: text.replace(/\s*\d+\s*차\s*$/, ''), memo: text };
    if (dose) detail.dose = Number(dose[1]);
    if (a.place) detail.hospital = a.place;
    return { kind: 'vaccine', occurred_at: when, detail, source: SOURCE.PHONE };
  });
}

/**
 * @param {{api: object, now: () => Date, refresh: () => Promise<void>, notify: (text: string, tone?: string) => void,
 *          phrases: {of: Function, manage: Function, labelOf: Function}, upcoming: {load: Function}}} ctx
 */
export function setupSettings(ctx) {
  const dialog = $('#appt');
  let list = [];
  let editing = null;
  let deleteArmedUntil = 0;
  const fail = (what) => ctx.notify(`${what} 못 했어요. 연결을 확인해 주세요`, 'warn');

  // ── 다가오는 일정 ──
  function renderAppointments() {
    const now = ctx.now();
    $('#apptList').replaceChildren(...list.map((a) => {
      const d = describeAppointment(a, now, { past: true });
      const b = el('button', 'rec');
      b.append(el('span', 'body', `${d.date} ${a.title}${a.items?.length ? ` · ${a.items.join(', ')}` : ''}${a.place ? ` · ${a.place}` : ''}`), el('span', 'left', d.left), el('span', 'go', '›'));
      b.addEventListener('click', () => openAppointment(a));
      return b;
    }));
    $('#apptEmpty').hidden = list.length > 0;
  }
  async function loadAppointments() {
    try { list = await ctx.api.getAppointments(); renderAppointments(); renderVaccines(); } catch (e) { $('#apptEmpty').hidden = false; $('#apptEmpty').textContent = '일정을 못 받았어요. 연결을 확인해 주세요'; }
  }
  function renderApptButtons() {
    const armed = Date.now() < deleteArmedUntil;
    $('#apptDelete').hidden = !editing;
    $('#apptDelete').textContent = armed ? '한 번 더 누르면 지워요' : '지우기';
    $('#apptDelete').classList.toggle('warnBtn', armed);
    // 오늘이거나 지난 접종 일정: 맞은 것을 기록으로 옮길 수 있다
    $('#apptDone').hidden = !(editing && editing.kind === 'vaccine' && editing.on_date <= dayKey(ctx.now()));
  }
  function openAppointment(a) {
    editing = a;
    deleteArmedUntil = 0;
    $('#apptTitle').textContent = a ? '일정 고치기' : '일정 넣기';
    $('#apptDate').value = a?.on_date ?? '';
    $('#apptDate').min = a ? '' : dayKey(ctx.now());   // 새 일정은 오늘부터
    $('#apptTime').value = a?.at_time ?? '';
    $('#apptName').value = a?.title ?? '예방접종';
    $('#apptPlace').value = a?.place ?? '';
    $('#apptItems').value = (a?.items ?? []).join(', ');
    $('#apptNote').value = a?.note ?? '';
    $('#apptMsg').textContent = '';
    renderApptButtons();
    dialog.showModal();
  }
  const afterChange = async () => { await loadAppointments(); await loadVaccines(); ctx.upcoming.load().then(() => ctx.refresh()); };

  $('#apptAdd').addEventListener('click', () => openAppointment(null));
  $('#apptClose').addEventListener('click', () => dialog.close());
  $('#apptForm').addEventListener('submit', async (e) => {
    e.preventDefault();
    const { p, error } = buildAppointment({ id: editing?.id, on_date: $('#apptDate').value, at_time: $('#apptTime').value, title: $('#apptName').value,
      place: $('#apptPlace').value, items: $('#apptItems').value, note: $('#apptNote').value });
    if (error) { $('#apptMsg').textContent = error; return; }
    try { await ctx.api.setAppointment(p); } catch (err) { $('#apptMsg').textContent = '저장 못 했어요. 연결을 확인해 주세요'; return; }
    dialog.close();
    ctx.notify(editing ? '일정을 고쳤어요' : '일정을 넣었어요');
    await afterChange();
  });
  $('#apptDelete').addEventListener('click', async () => {
    if (!editing) return;
    if (Date.now() >= deleteArmedUntil) {
      deleteArmedUntil = Date.now() + DELETE_CONFIRM_MS;
      renderApptButtons();
      setTimeout(renderApptButtons, DELETE_CONFIRM_MS + 50);
      return;
    }
    try { await ctx.api.cancelAppointment(editing.id); } catch (err) { $('#apptMsg').textContent = '지우지 못했어요. 연결을 확인해 주세요'; return; }
    dialog.close();
    ctx.notify('일정을 지웠어요');
    await afterChange();
  });
  // 맞았어요: 항목마다 예방접종 기록을 넣고 일정을 닫는다
  $('#apptDone').addEventListener('click', async () => {
    if (!editing) return;
    const events = vaccineEvents({ ...editing, place: $('#apptPlace').value.trim() || editing.place, items: parseItems($('#apptItems').value) }, ctx.now());
    try {
      for (const ev of events) await ctx.api.addEvent(ev, { force: true });
      await ctx.api.cancelAppointment(editing.id);
    } catch (err) { $('#apptMsg').textContent = '기록으로 옮기지 못했어요. 연결을 확인해 주세요'; return; }
    dialog.close();
    ctx.notify(`예방접종 ${events.length}건을 기록에 넣었어요`);
    await afterChange();
  });

  // ── 예방접종 일정표 ──
  let vax = null;
  let vaxAll = false;
  function renderVaccines() {
    if (!vax?.baby?.birth_date) return;
    const now = ctx.now();
    const s = vaccineStatus({ birth: vax.baby.birth_date, sex: vax.baby.sex, records: vax.records, appointments: list, now });
    const c = s.counts;
    $('#vaxSummary').textContent = `맞음 ${c.done} · 예약 ${c.booked} · 지금 맞을 때 ${c.due} · 시기 지남 ${c.overdue}`;
    // 처음엔 지난 것과 곧 올 것(아직 안 온 시기 둘)까지만. [전체 일정 보기]로 12세까지
    const started = s.periods.filter((p) => p.rows.some((r) => r.status !== 'later'));
    const coming = s.periods.filter((p) => p.rows.every((r) => r.status === 'later'));
    const shown = vaxAll ? s.periods : [...started, ...coming.slice(0, 2)];
    const nodes = [];
    for (const p of shown) {
      const open = p.rows.find((r) => r.status !== 'done');
      const head = el('div', 'vaxPeriod');
      head.append(el('span', '', p.label), el('span', '', open ? '' : '모두 맞음'));
      nodes.push(head);
      for (const r of p.rows) {
        const row = el('div', `vaxRow ${r.status}`);
        row.append(el('span', '', `${r.name}${r.of > 1 ? ` ${r.dose}차` : ''}`), el('span', 'st', statusText(r)));
        nodes.push(row);
      }
    }
    const fluHead = el('div', 'vaxPeriod'); fluHead.append(el('span', '', '6개월부터 매년'));
    const flu = el('div', `vaxRow ${s.flu.booked.length ? 'booked' : s.flu.done.length ? 'done' : s.flu.started ? 'due' : 'later'}`);
    const md = (k) => { const [, m, d] = k.split('-').map(Number); return `${m}/${d}`; };
    flu.append(el('span', '', `${s.flu.name} · 첫해는 4주 간격 2회`),
      el('span', 'st', s.flu.booked.length ? `예약 ${md(s.flu.booked[0])}` : s.flu.done.length ? `맞음 ${s.flu.done.map(md).join(', ')}` : s.flu.started ? '지금 맞을 때' : `${md(s.flu.from)}부터`));
    nodes.push(fluHead, flu);
    if (s.others.length) {
      const head = el('div', 'vaxPeriod'); head.append(el('span', '', '표에 없는 접종'));
      nodes.push(head, ...s.others.map((o) => { const row = el('div', 'vaxRow done'); const d = new Date(o.at); row.append(el('span', '', o.text), el('span', 'st', `맞음 ${d.getMonth() + 1}/${d.getDate()}`)); return row; }));
    }
    $('#vaxList').replaceChildren(...nodes);
    $('#vaxMore').hidden = !coming.length;
    $('#vaxMore').textContent = vaxAll ? '곧 올 것까지만 보기' : '전체 일정 보기(12세까지)';
  }
  async function loadVaccines() {
    try { vax = await ctx.api.getVaccines(); renderVaccines(); } catch (e) { $('#vaxSummary').textContent = '접종 기록을 못 받았어요. 연결을 확인해 주세요'; }
  }
  $('#vaxMore').addEventListener('click', () => { vaxAll = !vaxAll; renderVaccines(); });

  // ── 자주 쓰는 문구: 종류마다 한 줄, 누르면 더하기·지우기 창 ──
  function renderPhrases() {
    const kinds = ['feed', ...recordTypes().filter((t) => !isBuiltinKind(t.key)).map((t) => t.key)];
    $('#phraseKinds').replaceChildren(...kinds.map((kind) => {
      const texts = ctx.phrases.of(kind);
      const b = el('button', 'rec two');
      const body = el('span', 'body');
      body.append(el('span', 'val', ctx.phrases.labelOf(kind)), texts.length ? ` ${texts.join(', ')}` : '');
      if (!texts.length) body.append(el('span', 'hint', ' 문구 없음'));
      b.append(body, el('span', 'go', '›'));
      b.addEventListener('click', () => ctx.phrases.manage(kind));
      return b;
    }));
  }

  // ── 더 넣기 버튼: 보임/숨김, 순서 ──
  function renderTypes() {
    const types = recordTypes().filter((t) => !isBuiltinKind(t.key));
    $('#typeList').replaceChildren(...types.map((t, i) => {
      const row = el('div', 'typeRow');
      const up = el('button', 'btn step', '▲'); up.setAttribute('aria-label', `${t.label} 위로`); up.disabled = i === 0;
      const down = el('button', 'btn step', '▼'); down.setAttribute('aria-label', `${t.label} 아래로`); down.disabled = i === types.length - 1;
      const move = async (to) => {
        const keys = types.map((x) => x.key);
        keys.splice(to, 0, keys.splice(i, 1)[0]);
        try { await ctx.api.orderRecordTypes(keys); await ctx.refresh(); render(); } catch (e) { fail('순서를 바꾸지'); }
      };
      up.addEventListener('click', () => move(i - 1));
      down.addEventListener('click', () => move(i + 1));
      const show = el('button', `btn toggle${t.in_more ? ' on' : ''}`, t.in_more ? '보임' : '숨김');
      show.setAttribute('aria-pressed', String(!!t.in_more));
      show.setAttribute('aria-label', `${t.label} 더 넣기에 ${t.in_more ? '보임' : '숨김'}`);
      show.addEventListener('click', async () => {
        try { await ctx.api.showRecordType(t.key, !t.in_more); await ctx.refresh(); render(); } catch (e) { fail('바꾸지'); }
      });
      row.append(up, down, el('span', 'grow', t.label), show);
      return row;
    }));
  }

  function render() {
    renderAppointments();
    renderPhrases();
    renderTypes();
    $('#account').textContent = ctx.api.demo ? '미리 보기(가짜 데이터)' : ctx.api.email();
    $('#logout').hidden = !!ctx.api.demo;
  }
  $('#logout').addEventListener('click', () => ctx.api.signOut());

  return { show() { render(); loadAppointments(); loadVaccines(); }, render };
}
