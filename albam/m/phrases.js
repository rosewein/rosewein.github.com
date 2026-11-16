// 자주 쓰는 문구: 기록에 눌러서 붙이는 메모(supabase/016). 수유의 "유산균", 목욕의 "보습로션" 같은 것.
//
//   같이  [유산균] [비타민D] [+]      ← 누르면 켜짐/꺼짐, [+]는 문구 더하기·지우기 창
//
// 고른 문구는 그 기록의 메모(detail.memo)에 " · " 로 이어 붙는다: "유산균 · 비타민D".
// 문구를 더하고 지우는 건 이 화면(개인 폰)에서 한다. 연결이 안 되면 마지막으로 받은 목록을 쓴다.

const SEP = ' · ';
const $ = (s) => document.querySelector(s);

/** 메모 → 조각들 */
export const memoParts = (memo) => String(memo || '').split(SEP).map((s) => s.trim()).filter(Boolean);
/** 메모에 그 문구가 들어 있나 */
export const memoHas = (memo, phrase) => memoParts(memo).includes(phrase);
/** 문구를 켜고 끈다(있으면 빼고, 없으면 뒤에 붙임). 다른 글은 그대로 둔다 */
export function toggleMemo(memo, phrase) {
  const parts = memoParts(memo);
  return (parts.includes(phrase) ? parts.filter((p) => p !== phrase) : [...parts, phrase]).join(SEP);
}

/**
 * @param {{api: object}} ctx
 * @param {string} cacheKey
 * @param {{labelOf: (kind: string) => string, onChange: () => void, notify: (text: string, tone?: string) => void}} o
 */
export function createPhrases(ctx, cacheKey, { labelOf, onChange, notify }) {
  let list = [];
  try { list = JSON.parse(localStorage.getItem(cacheKey) || '[]') || []; } catch (e) { /* 없어도 됨 */ }
  const dialog = $('#phrases');
  let managing = null;

  async function load() {
    try {
      const got = await ctx.api.getPhrases();
      if (Array.isArray(got)) {
        list = got;
        try { localStorage.setItem(cacheKey, JSON.stringify(list)); } catch (e) { /* 저장 못 해도 됨 */ }
        onChange();
        if (dialog.open) renderManage();
      }
    } catch (e) { /* 연결 안 됨: 지난번 것 */ }
  }

  /** 그 종류의 문구들(글만) */
  const of = (kind) => list.filter((p) => p.kind === kind).map((p) => p.text);

  /**
   * 문구 버튼 줄을 그린다.
   * @param {Element} box
   * @param {string} kind
   * @param {{isOn: (text: string) => boolean, onToggle: (text: string) => void, lead?: string}} o
   */
  function renderChips(box, kind, { isOn, onToggle, lead = '' }) {
    const nodes = [];
    if (lead) { const s = document.createElement('span'); s.className = 'hint'; s.textContent = lead; nodes.push(s); }
    for (const text of of(kind)) {
      const b = document.createElement('button');
      b.type = 'button';
      b.className = `chip${isOn(text) ? ' on' : ''}`;
      b.textContent = text;
      b.setAttribute('aria-pressed', String(isOn(text)));
      b.addEventListener('click', () => onToggle(text));
      nodes.push(b);
    }
    const add = document.createElement('button');
    add.type = 'button';
    add.className = 'chip add';
    add.textContent = of(kind).length ? '+' : '+ 문구';
    add.setAttribute('aria-label', '문구 더하기·지우기');
    add.addEventListener('click', () => manage(kind));
    nodes.push(add);
    box.replaceChildren(...nodes);
  }

  // ── 문구 더하기·지우기 창 ──
  function renderManage() {
    $('#phrasesTitle').textContent = `${labelOf(managing)} 문구`;
    const mine = list.filter((p) => p.kind === managing);
    $('#phrasesList').replaceChildren(...mine.map((p) => {
      const row = document.createElement('div');
      row.className = 'phraseRow';
      const t = document.createElement('span');
      t.textContent = p.text;
      const del = document.createElement('button');
      del.type = 'button';
      del.className = 'btn';
      del.textContent = '지우기';
      del.addEventListener('click', async () => {
        try { await ctx.api.removePhrase(p.id); await load(); } catch (e) { $('#phrasesMsg').textContent = '지우지 못했어요(연결을 확인해 주세요)'; }
      });
      row.append(t, del);
      return row;
    }));
    $('#phrasesEmpty').hidden = mine.length > 0;
  }
  function manage(kind) {
    managing = kind;
    $('#phraseText').value = '';
    $('#phrasesMsg').textContent = '';
    renderManage();
    dialog.showModal();
  }
  $('#phrasesForm').addEventListener('submit', async (e) => {
    e.preventDefault();
    const text = $('#phraseText').value.trim();
    if (!text) return;
    if (text.includes(SEP)) { $('#phrasesMsg').textContent = '문구에 " · " 는 넣을 수 없어요'; return; }
    try {
      const r = await ctx.api.addPhrase(managing, text);
      $('#phraseText').value = '';
      $('#phrasesMsg').textContent = r?.status === 'exists' ? '이미 있는 문구예요' : '';
      await load();
    } catch (err) {
      $('#phrasesMsg').textContent = '더하지 못했어요(연결을 확인해 주세요)';
    }
  });
  $('#phrasesClose').addEventListener('click', () => { dialog.close(); notify('문구를 고쳤어요'); onChange(); });

  return { load, of, renderChips, manage, labelOf };
}
