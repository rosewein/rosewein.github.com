"""큰 개발 건물명 받기 도구(HTML) 만들기: python3 src/building_names_tool.py <building.json> <출력 html>

작업 공간은 공공데이터포털 API(apis.data.go.kr)에 닿지 못하므로, 이지의 크롬에서 여는 HTML 한 장을 만든다.
- 정보창에 큰 개발로 뜨는 줄(3만㎡ 또는 300세대 이상) 가운데 지금 대장에 남은 건물의 지번(PNU)만 넣는다(헐린 것은 같은 지번의 새 건물이 나오므로 뺌).
- 지번마다 국토교통부 「건축HUB 건축물대장정보 서비스」의 표제부(getBrTitleInfo)와 총괄표제부(getBrRecapTitleInfo)를 부르고,
  건물명·동명·사용승인일·연면적·세대수 등 몇 항목만 JSON으로 내려받게 한다. 인증키는 페이지 안에서만 쓰고 파일에는 남기지 않는다.
- 2026-11-26 확인: 크롬에서 apis.data.go.kr 응답은 다른 출처(로컬 파일 포함)에서도 읽힘. 개발계정 하루 10,000건, 개발단계 자동승인.
"""
import json, sys

src, out = sys.argv[1], sys.argv[2]
b = json.load(open(src))
lots = sorted({x["pnu"] for x in b["big"] if (x["a"] >= 30000 or x["hh"] >= 300) and not x["gone"] and x.get("pnu")})
print("지번", len(lots))

HTML = r"""<!DOCTYPE html>
<html lang="ko"><head><meta charset="utf-8"><title>큰 개발 건물명 받기 · 서울 도시 연대지도</title>
<meta name="viewport" content="width=device-width,initial-scale=1">
<style>
body { font: 15px/1.6 system-ui, "Malgun Gothic", sans-serif; max-width: 760px; margin: 32px auto; padding: 0 18px; color: #1c211e; background: #f6f6f2; }
h1 { font-size: 22px; margin: 0 0 6px; } p { margin: 6px 0; } .meta { color: #5b625e; font-size: 13px; }
.row { display: flex; flex-wrap: wrap; gap: 8px; align-items: center; margin: 14px 0; }
input[type=password], input[type=text] { flex: 1 1 360px; font: 14px ui-monospace, monospace; padding: 8px 10px; border: 1px solid #a9b0ab; border-radius: 6px; }
button { font: 600 14px system-ui, sans-serif; padding: 8px 14px; border-radius: 6px; border: 1px solid #1c211e; background: #fff; cursor: pointer; }
button.main { background: #1c211e; color: #fff; } button:disabled { opacity: .4; cursor: default; }
#bar { height: 10px; background: #dfe2dd; border-radius: 5px; overflow: hidden; } #bar i { display: block; height: 100%; width: 0; background: #2f5d50; }
#log { font: 12.5px/1.5 ui-monospace, monospace; background: #fff; border: 1px solid #dfe2dd; border-radius: 6px; padding: 10px; height: 220px; overflow: auto; white-space: pre-wrap; }
.err { color: #a1271b; } .ok { color: #2f5d50; }
</style></head><body>
<h1>큰 개발 건물명 받기</h1>
<p>「서울 도시 연대지도」 정보창의 큰 개발(3만㎡ 또는 300세대 이상, 지금 건축물대장에 남은 것) __N__개 지번의 건물명을 국토교통부 「건축HUB 건축물대장정보 서비스」에서 받습니다. 지번마다 표제부와 총괄표제부를 한 번씩 불러 약 __C__번 호출합니다(개발계정 하루 10,000건).</p>
<p class="meta">공공데이터포털 마이페이지의 인증키(Decoding 키)를 넣어 주세요. Encoding 키를 넣어도 됩니다. 키는 이 페이지 안에서만 쓰이고 저장되는 결과 파일에는 들어가지 않습니다. 진행 상황은 이 브라우저에 저장되므로 창을 닫았다 다시 열어도 이어 받을 수 있습니다(키는 저장하지 않음).</p>
<div class="row"><input id="key" type="password" placeholder="인증키" autocomplete="off" spellcheck="false"><label class="meta"><input id="show" type="checkbox"> 보이기</label></div>
<div class="row">
  <button id="test">시험 10곳</button>
  <button id="run" class="main">전체 받기</button>
  <button id="stop" disabled>멈춤</button>
  <button id="save">결과 저장</button>
  <button id="reset">처음부터</button>
</div>
<div id="bar"><i></i></div>
<p id="stat" class="meta">아직 시작하지 않았습니다.</p>
<div id="log"></div>
<script>
const LOTS = __LOTS__;
const BASE = "https://apis.data.go.kr/1613000/BldRgstHubService";
const KEEP_T = ["mgmBldrgstPk", "bldNm", "dongNm", "regstrGbCdNm", "regstrKindCdNm", "mainAtchGbCdNm", "useAprDay", "pmsDay", "totArea", "hhldCnt", "mainPurpsCdNm", "platPlc"];
const KEEP_R = ["mgmBldrgstPk", "bldNm", "regstrGbCdNm", "regstrKindCdNm", "useAprDay", "pmsDay", "totArea", "hhldCnt", "mainPurpsCdNm", "platPlc"];
const STORE = "slm_bldnm_v1", CALL_CAP = 9500, CONC = 1;
// 초당 호출 한도(HTTP 429)가 있어 한 번에 하나씩, 호출 사이를 띄운다. 429가 오면 간격을 1.5배로 늘려 같은 호출을 다시 하고, 잘 되면 조금씩 줄인다
let gap = 350, last429 = 0; const GAP_MIN = 350, GAP_MAX = 8000;
const sleep = (ms) => new Promise(z => setTimeout(z, ms));
let st = load(), running = false, stopReq = false;
const $ = (id) => document.getElementById(id);
function load() { try { return JSON.parse(localStorage.getItem(STORE)) || { done: {}, errors: {}, calls: 0, day: "" }; } catch (e) { return { done: {}, errors: {}, calls: 0, day: "" }; } }
function persist() { try { localStorage.setItem(STORE, JSON.stringify(st)); } catch (e) { log("브라우저 저장 공간이 모자라 진행 상황을 저장하지 못했습니다. 「결과 저장」으로 파일을 받아 두세요.", "err"); } }
function log(m, cls) { const d = document.createElement("div"); if (cls) d.className = cls; d.textContent = new Date().toLocaleTimeString("ko-KR") + "  " + m; $("log").prepend(d); }
function today() { return new Date().toISOString().slice(0, 10); }
function keyEnc() { const k = $("key").value.trim(); return k.includes("%") ? k : encodeURIComponent(k); }
function show() {
  const n = Object.keys(st.done).length, e = Object.keys(st.errors).length;
  $("bar").firstElementChild.style.width = (n / LOTS.length * 100).toFixed(1) + "%";
  $("stat").textContent = `받은 지번 ${n} / ${LOTS.length} · 실패 ${e} · 오늘 호출 ${st.day === today() ? st.calls : 0}번`;
}
class Fatal extends Error {}
class Slow extends Error {}   // 429: 실패로 세지 않고 쉬었다 다시
// 응답 읽기: JSON이면 header.resultCode, XML이면 오류 메시지. 인증키·권한·트래픽 오류는 멈춤(Fatal)
async function call(op, pnu, page) {
  const sg = pnu.slice(0, 5), bj = pnu.slice(5, 10), gb = String(+pnu[10] - 1), bun = pnu.slice(11, 15), ji = pnu.slice(15, 19);
  const q = `serviceKey=${keyEnc()}&sigunguCd=${sg}&bjdongCd=${bj}&platGbCd=${gb}&bun=${bun}&ji=${ji}&numOfRows=100&pageNo=${page}&_type=json`;
  if (st.day !== today()) { st.day = today(); st.calls = 0; }
  if (st.calls >= CALL_CAP) throw new Fatal(`오늘 호출이 ${CALL_CAP}번에 이르러 멈춥니다(하루 한도 10,000). 내일 「전체 받기」를 다시 누르면 이어 받습니다.`);
  st.calls++;
  await sleep(gap);
  const ctl = new AbortController(), tm = setTimeout(() => ctl.abort(), 25000);
  let r, t;
  try { r = await fetch(`${BASE}/${op}?${q}`, { signal: ctl.signal }); t = await r.text(); } finally { clearTimeout(tm); }
  if (r.status === 429) {   // 초당 한도면 쉬었다 다시, 하루 한도면 멈춤. 서버가 보낸 글을 1분에 한 번 기록에 남김(주소·키는 빼고)
    const body = t.trim().replace(/https?:\/\/\S+/g, "").replace(/\s+/g, " ").slice(0, 200);
    if (Date.now() - last429 > 60000) { last429 = Date.now(); log(`서버 응답(HTTP 429): ${body || "(내용 없음)"}`); }
    if (/일일|LIMITED_NUMBER|DAILY|quota/i.test(body)) throw new Fatal(`하루 호출 한도에 걸린 것으로 보여 멈춥니다: ${body}`);
    gap = Math.min(GAP_MAX, gap * 1.5); throw new Slow();
  }
  const s = t.trim();
  let code = "", msg = "";
  if (s.startsWith("<")) {
    const g = (tag) => (s.match(new RegExp(`<${tag}>([^<]*)</${tag}>`)) || [])[1] || "";
    code = g("returnReasonCode") || g("resultCode"); msg = g("returnAuthMsg") || g("errMsg") || g("resultMsg") || s.slice(0, 120);
  } else {
    let j; try { j = JSON.parse(s); } catch (e) { throw new Error(`읽을 수 없는 응답(HTTP ${r.status}): ${s.slice(0, 120)}`); }
    const h = (j.response && j.response.header) || j.header || {};
    code = String(h.resultCode ?? ""); msg = h.resultMsg || "";
    if (code === "00" || code === "0" || code === "000" || code === "0000") {
      const body = j.response.body || {}; let it = body.items && body.items.item ? body.items.item : [];
      if (!Array.isArray(it)) it = [it];
      return { total: +body.totalCount || 0, items: it };
    }
    if (!code && j.response && j.response.body) { const body = j.response.body; let it = body.items && body.items.item ? body.items.item : []; if (!Array.isArray(it)) it = [it]; return { total: +body.totalCount || 0, items: it }; }
  }
  const all = `${code} ${msg}`;
  if (/KEY|인증키|LIMITED|트래픽|호출 허용량|권한|UNAUTHORIZED|IP/i.test(all) || ["20", "22", "30", "31", "32", "33"].includes(code) || r.status === 401 || r.status === 403)
    throw new Fatal(`멈춤: ${all.trim()} (HTTP ${r.status}). 새로 받은 키는 쓸 수 있게 되기까지 시간이 걸리기도 합니다.`);
  throw new Error(`${all.trim()} (HTTP ${r.status})`);
}
async function fetchAll(op, pnu, keep) {
  let page = 1, out = [];
  for (;;) {
    let res, tries = 0, slow = 0, longWait = 0;
    for (;;) {
      try { res = await call(op, pnu, page); gap = Math.max(GAP_MIN, gap * 0.95); break; }
      catch (e) {
        if (e instanceof Fatal) throw e;
        if (e instanceof Slow) {   // 429가 8번 넘게 이어지면 1분씩 쉬고, 10분 넘게 이어지면 멈춤
          if (++slow > 8) { if (++longWait > 10) throw new Fatal("10분 넘게 HTTP 429가 이어져 멈춥니다. 위 기록의 서버 응답을 알려 주세요.");
            slow = 0; $("stat").textContent = `HTTP 429가 이어져 1분 쉽니다(${longWait}/10)`; await sleep(60000); continue; }
          $("stat").textContent = `받은 지번 ${Object.keys(st.done).length} / ${LOTS.length} · 잠시 쉼(간격 ${Math.round(gap)}ms)`; await sleep(gap * 2); continue;
        }
        if (++tries >= 3) throw e; await sleep(1500 * tries);
      }
    }
    out = out.concat(res.items.map(it => Object.fromEntries(keep.map(k => [k, it[k] ?? ""]))));
    if (page * 100 >= res.total || !res.items.length) return out;
    page++;
  }
}
async function one(pnu) {
  const t = await fetchAll("getBrTitleInfo", pnu, KEEP_T);
  const r = await fetchAll("getBrRecapTitleInfo", pnu, KEEP_R);
  st.done[pnu] = { t, r }; delete st.errors[pnu];
}
async function go(list) {
  if (!$("key").value.trim()) { log("인증키를 먼저 넣어 주세요.", "err"); return; }
  running = true; stopReq = false; ["test", "run", "reset"].forEach(i => $(i).disabled = true); $("stop").disabled = false;
  const todo = list.filter(p => !st.done[p]); let i = 0, fatal = null, n0 = Object.keys(st.done).length;
  log(`${todo.length}개 지번을 받습니다.`);
  async function worker() {
    while (!stopReq && !fatal && i < todo.length) {
      const p = todo[i++];
      try { await one(p); } catch (e) { if (e instanceof Fatal) { fatal = e; break; } st.errors[p] = String(e.message || e); log(`${p} 실패: ${st.errors[p]}`, "err"); }
      if ((Object.keys(st.done).length - n0) % 25 === 0) persist();
      show();
    }
  }
  await Promise.all(Array.from({ length: CONC }, worker));
  persist(); show();
  if (fatal) log(fatal.message, "err");
  else if (stopReq) log("멈췄습니다. 「전체 받기」를 누르면 이어 받습니다.");
  else log(`끝. 받은 지번 ${Object.keys(st.done).length}개, 실패 ${Object.keys(st.errors).length}개. 「결과 저장」을 눌러 파일을 받아 주세요.`, "ok");
  running = false; ["test", "run", "reset"].forEach(i => $(i).disabled = false); $("stop").disabled = true;
}
function sample() {   // 시험 10곳: 받은 것 가운데 이름이 있는 줄을 몇 개 보여 줌
  const ps = LOTS.filter(p => st.done[p]).slice(0, 10);
  ps.forEach(p => { const d = st.done[p]; const nm = [...new Set(d.r.concat(d.t).map(x => x.bldNm).filter(Boolean))].slice(0, 3).join(" / ");
    log(`${d.t[0] ? d.t[0].platPlc : p} · 표제부 ${d.t.length}줄 · 총괄 ${d.r.length}줄 · 이름: ${nm || "(없음)"}`, "ok"); });
}
$("show").onchange = () => { $("key").type = $("show").checked ? "text" : "password"; };
$("test").onclick = async () => { await go(LOTS.slice(0, 10)); sample(); };
$("run").onclick = () => go(LOTS);
$("stop").onclick = () => { stopReq = true; log("지금 받는 지번까지 마치고 멈춥니다."); };
$("reset").onclick = () => { if (running) return; st = { done: {}, errors: {}, calls: st.calls, day: st.day }; persist(); show(); log("받은 것을 지웠습니다(오늘 호출 수는 남김)."); };
$("save").onclick = () => {
  const out = { made: new Date().toISOString(), source: "국토교통부 건축HUB 건축물대장정보 서비스(공공데이터포털 15134735) 표제부·총괄표제부", lots: LOTS.length, done: st.done, errors: st.errors };
  const a = document.createElement("a"); a.href = URL.createObjectURL(new Blob([JSON.stringify(out)], { type: "application/json" }));
  a.download = `건물이름_건축HUB_${today().replaceAll("-", "")}.json`; a.click(); setTimeout(() => URL.revokeObjectURL(a.href), 5000);
  log(`파일로 저장: 지번 ${Object.keys(st.done).length}개`, "ok");
};
show();
if (Object.keys(st.done).length) log(`이전에 받은 지번 ${Object.keys(st.done).length}개가 있습니다. 「전체 받기」를 누르면 나머지를 이어 받습니다.`);
</script></body></html>
"""
html = HTML.replace("__LOTS__", json.dumps(lots)).replace("__N__", f"{len(lots):,}").replace("__C__", f"{len(lots) * 2:,}")
open(out, "w").write(html)
print("wrote", out, len(html), "bytes")
