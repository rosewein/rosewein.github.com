"""지도 만들기: python3 src/build.py [출력 폴더] [--fragment 조각.html]
src/의 틀·설명문과 data/의 자료를 읽어 출력 폴더(기본: seoul-layer-map/)에 index.html을 쓴다.
--fragment를 주면 Claude 아티팩트용 조각(<title>부터 본문 끝까지)도 그 경로에 쓴다."""
import json, os, re, sys
sys.dont_write_bytecode = True   # 저장소에 __pycache__가 생기지 않게
from paths import CODE as SRC, DATA
def F(name):
    """자료 파일은 data/, 틀·설명문은 src/에서 찾는다"""
    for d in (DATA, SRC):
        if os.path.exists(os.path.join(d, name)): return os.path.join(d, name)
    return os.path.join(DATA, name)
_a = sys.argv[1:]
FRAG = _a[_a.index("--fragment") + 1] if "--fragment" in _a else None
_pos = [a for i, a in enumerate(_a) if not a.startswith("--") and not (i and _a[i - 1] == "--fragment")]
OUT = _pos[0] if _pos else os.path.dirname(SRC)
topo = json.load(open(F("emd_topo.json")))
obj = topo["objects"].pop("seoul_neighborhoods_geo")
topo["objects"]["emd"] = obj
trams = json.load(open(F("tram.json")))
years = json.load(open(F("years.json"))) if os.path.exists(F("years.json")) else {}
gu_periods = json.load(open(F("gu_periods.json"))) if os.path.exists(F("gu_periods.json")) else []
extra_events = json.load(open(F("events_extra.json"))) if os.path.exists(F("events_extra.json")) else []
method_html = open(F("method.html")).read() if os.path.exists(F("method.html")) else ""

GU = {"11110":"종로구","11140":"중구","11170":"용산구","11200":"성동구","11215":"광진구","11230":"동대문구","11260":"중랑구",
"11290":"성북구","11305":"강북구","11320":"도봉구","11350":"노원구","11380":"은평구","11410":"서대문구","11440":"마포구",
"11470":"양천구","11500":"강서구","11530":"구로구","11545":"금천구","11560":"영등포구","11590":"동작구","11620":"관악구",
"11650":"서초구","11680":"강남구","11710":"송파구","11740":"강동구"}

missing = []
for g in obj["geometries"]:
    p = g["properties"]
    key = f'{GU[p["gu"]]}/{p["nm"]}'
    rec = years.get(key)
    if rec is None:
        missing.append(key); p["y"] = 1963; p["yc"] = "미확인(기본값)"
    else:
        p["y"] = int(rec["y"]);
        if rec.get("note"): p["yn"] = rec["note"]
        if rec.get("conf"): p["yc"] = rec["conf"]
print("missing years:", len(missing), missing[:40], file=sys.stderr)

eras = [
  {"year":1914, "label":"1914 부제 실시(축소)", "official":"36.18"},
  {"year":1936, "label":"1936 경성부 확장", "official":"133.94"},
  {"year":1949, "label":"1949 서울특별시 확장", "official":"268.35"},
  {"year":1963, "label":"1963 대확장", "official":"613.04"},
  {"year":1973, "label":"1973 고양 신도면 일부 편입", "official":"627.06"},
  {"year":1995, "label":"현재(1995 이후)", "official":"605.2"},
]

events = []
import re as _re
def short(lbl, y):
    m=_re.match(r'^(\d{4}(?:\.\d{1,2}){0,2})', lbl or "")
    return m.group(1) if m else str(y)
seen={}
for l in trams["lines"]:
    kind = "kido" if l["op"] == "기동차" else "tram"
    key=(l["line"], l["openLabel"])
    conf = None if l["conf"] in ("확인",) else l["conf"]
    if key in seen:
        seen[key]["text"] = seen[key]["text"].replace(" 개통", "") + " · " + l["name"] + " 개통"; continue
    ev={"year": l["open"], "date": short(l["openLabel"], l["open"]), "kind": kind, "text": f'{l["line"]} {l["name"]} 개통', "conf": conf, "sort": 2}
    seen[key]=ev; events.append(ev)
closes={}
for l in trams["lines"]:
    if l["close"] == 1968: continue
    closes.setdefault((l["close"], l["op"]), []).append(l)
for (y,op),ls in sorted(closes.items()):
    names=[]
    for l in ls:
        if l["line"] not in names: names.append(l["line"])
    kind="kido" if op=="기동차" else "tram"
    if y==1904: txt=f'{", ".join(names)} 폐지'; conf="연도 추정"
    elif y==1950: txt=f'{", ".join(names)} 폐선(6·25 이후, 시기 미상)'; conf="시기 미확인"
    elif y==1966 and op=="기동차": txt="경성궤도 기동차(뚝섬선·광장리선) 운행 종료"; conf=None
    elif y==1966: txt=f'{", ".join(names)} 운행 중단(세종로 지하도 공사 뒤 재개 안 함)'; conf=None
    else: txt=f'{", ".join(names)} 폐지'; conf=None
    events.append({"year": y, "date": str(y), "kind": kind, "text": txt, "conf": conf, "sort": 3})
events.append({"year": 1968, "date": "1968.11.30", "kind": "tram", "text": "서울 전차 전 노선 운행 정지", "sort": 3})
events += extra_events
if os.path.exists(F("metro_events.json")): events += json.load(open(F("metro_events.json")))
if os.path.exists(F("rail_events.json")): events += json.load(open(F("rail_events.json")))
if os.path.exists(F("bus_events.json")): events += json.load(open(F("bus_events.json")))

data = {
  "topo": topo, "trams": trams, "eras": eras, "guPeriods": gu_periods, "events": events,
  "guNames": GU, "riverNorth": ["11440","11170","11200","11215"],
  "riverSouth": ["11500","11560","11590","11650","11680","11710","11740"],
  "methodHtml": method_html, "startYear": 1920,
  "rail": json.load(open(F("rail.json"))) if os.path.exists(F("rail.json")) else None,
  "metro": json.load(open(F("metro.json"))) if os.path.exists(F("metro.json")) else None,
  "bus": json.load(open(F("bus.json"))) if os.path.exists(F("bus.json")) else None,
  "bus2026": json.load(open(F("bus2026.json"))) if os.path.exists(F("bus2026.json")) else None,
  # 땅값: landprice.py가 만든 법정동별 ㎡당 공시지가 중앙값(1990–). 파일이 없으면 칩이 나타나지 않음
  "land": json.load(open(F("landprice.json"))) if os.path.exists(F("landprice.json")) else None,
}
# 땅값 설명문은 자료가 있을 때만 「이 지도를 읽는 법」에 넣는다(출처 문단 앞 + 출처 한 줄)
if data["land"] and os.path.exists(F("method_land.html")):
    SRC_AT = "연계 좌표정보」(2019년 6월 20일)."   # 출처 문단에서 버스 자료 다음, 나무위키 연혁 앞
    land_src = " 땅값은 서울 열린데이터광장 「서울시 개별공시지가 정보」(OA-1180, " + f'{data["land"]["years"][0]}~{data["land"]["years"][-1]}' + "년 파일, 원본 서울부동산정보광장)."
    assert method_html.count(SRC_AT) == 1, "method.html 출처 문단이 바뀜 — build.py의 SRC_AT을 고칠 것"
    data["methodHtml"] = method_html.replace('<p class="small">출처:', open(F("method_land.html")).read() + '<p class="small">출처:', 1).replace(SRC_AT, SRC_AT + land_src, 1)
# 버스: 2004년 7월 개편 이후 해마다 그릴 노선(2026년 노선망에서 그 해 뒤에 생긴 노선을 뺀다)
OLD_FROM = 1998
if data["bus2026"] and os.path.exists(F("route_years.json")):
    ry = json.load(open(F("route_years.json")))
    nums = data["bus2026"]["nums"]
    for n in nums:
        if n.get("dead"): continue
        r = ry.get(n["no"], {})
        n["oy"] = r.get("oy"); n["kind"] = r.get("kind"); n["src"] = r.get("src")
    # 통합으로 생긴 계승 노선: 통합 전 노선들이 모두 폐선 노선으로 복원됐으면 통합한 해부터 그린다(겹쳐 세지 않게)
    deadby = {}
    for n in nums:
        if n.get("dead"): deadby.setdefault(n["no"], []).append(n)
    merged = []
    for n in nums:
        if n.get("dead") or n.get("kind") != "계승": continue
        m = _re.search(r"([0-9A-Z·]+)번 (\d{4}) 통합", n.get("src") or "")
        if not m: continue
        preds, Y = m.group(1).split("·"), int(m.group(2))
        hits = [max(deadby.get(p, []), key=lambda d: d["cy"], default=None) for p in preds]
        if all(h and abs(h["cy"] - (Y + 0.5)) <= 1.5 for h in hits):
            n["oy"] = Y; n["src"] += f" — 통합 전 노선을 따로 그려서 {Y}년부터"
            merged.append((n["no"], Y))
    print("merger-adjusted:", merged, file=sys.stderr)
    grp = lambda no: _re.sub(r"(출근|퇴근|구산출|구산퇴|홍대출|홍대퇴|[AB])$", "", no)
    def old_active(r, y):
        oy = r.get("oy") if (r.get("oy") or 0) <= 2004 else None
        return (oy is None or oy <= y) and (r["live"] or (r.get("cy") is not None and r["cy"] > y))
    drawn = {}
    for y in range(OLD_FROM, 2004):
        drawn[y] = len({r["no"] for r in data["bus"]["routes"] if old_active(r, y)})
    for y in range(2004, 2027):
        live = {grp(n["no"]) for n in nums if not n.get("dead") and n["oy"] and n["oy"] <= y}
        dead_n = sum(1 for n in nums if n.get("dead") and n["oy"] <= y + 0.5 < n["cy"])
        drawn[y] = len(live) + dead_n
    data["busDrawn"] = drawn; data["busOldFrom"] = OLD_FROM
    print("bus drawn by year:", drawn, file=sys.stderr)
# 마을버스: 해마다 정류장 목록(번호로)과 '마을버스로만 닿는 땅'
if os.path.exists(F("village_layer.json")):
    VL = json.load(open(F("village_layer.json")))
    pts, idx = [], {}
    vy = {}
    for y, r in VL["years"].items():
        ids = []
        for p in r["stops"]:
            k = (round(p[0], 4), round(p[1], 4))
            if k not in idx: idx[k] = len(pts); pts.append([k[0], k[1]])
            ids.append(idx[k])
        vy[y] = {"routes": r["routes"], "nstops": r["nstops"], "only_km2": r["only_km2"], "day": r["day"], "stops": sorted(set(ids)), "only": r["only"]}
    data["village"] = {"pts": pts, "years": vy}
    print("village pts", len(pts), file=sys.stderr)
# 지도 버전: 레이어가 늘면 소수점을 올리고(v1.2 → v1.3), 화면·기술만 고치면 셋째 자리를 올린다(v1.3 → v1.3.1). README 「변경 기록」과 git 태그(seoul-layer-map-vX.Y)도 같이 적는다
data["version"] = {"v": "1.4.4", "date": "2026-11-26"}

# 지도에서 읽지 않는 필드는 index.html에 넣기 직전에 덜어 낸다(data/*.json 원본은 그대로 둔다).
# 근거 문장·운수회사·승하차 인원처럼 나중에 분석이나 정보창에 쓸 수 있는 기록이라 원본에서는 지우지 않는다.
# 새로 지도에서 이 필드를 읽게 되면 여기서 빼야 한다.
def slim(d):
    gone = 0
    def pop(obj, *keys):
        nonlocal gone
        for k in keys:
            if k in obj: gone += len(json.dumps(obj[k], ensure_ascii=False, separators=(",", ":")).encode()); del obj[k]
    for net in ("bus", "bus2026"):
        N = d.get(net)
        if not N: continue
        pop(N, "corr", "snapshot")          # corr: 한 시점에 고정된 구간 묶음. 지도는 해마다 segs에서 다시 셈(corrFor)
        for r in N["routes"]:
            pop(r, "ops", "succ", "type", "riders")   # 운수회사, 뒤를 이은 노선, 노선 유형, 승하차 인원
            if r.get("geom"): pop(r, "pts")           # 경유지 점: 선형(geom)이 없을 때만 대신 씀
        for e in N.get("events", []): pop(e, "cnt", "cur")
        for n in N.get("nums", []): pop(n, "src", "head", "merged_into")   # 운행 시작 연도의 근거 문장 등(연도만 씀)
    if d.get("land"): pop(d["land"], "seoulN", "basis", "src")
    if d.get("village"):
        for v in d["village"]["years"].values(): pop(v, "day", "nstops")
    for l in d["trams"]["lines"]: pop(l, "id")
    return gone
print("slim: removed", slim(data), "bytes of unused fields", file=sys.stderr)
tpl = open(F("template.html")).read()
out = tpl.replace("/*__DATA__*/", "const DATA = " + json.dumps(data, ensure_ascii=False, separators=(",", ":")) + ";")

# 글꼴: 페이지에 든 글자만 담아 fonts/에 만든다(src/fonts.py). 제목 글꼴은 제목·시기 이름·연도 숫자 글자만
def display_text(html):
    if html.count("var(--display)") != 5:   # 글꼴 설명 주석 1 + 쓰는 곳 4(h1, 연도, 연표 시기 제목, h2)
        print("fonts: var(--display)를 쓰는 곳 수가 바뀜 — display_text()에 그 글자를 더했는지 확인", file=sys.stderr)
    heads = "".join(re.findall(r"<h[12][^>]*>(.*?)</h[12]>", html))
    eras = "".join(e["label"] for e in data["eras"])
    return heads + eras + "한성부 시기 현재 시역 –·0123456789"
sys.path.insert(0, SRC)
from paths import FONTS, FONTSRC
import fonts as fontmod
fv = fontmod.build(out, display_text(out), FONTS, FONTSRC)
out = out.replace("__FV__", fv)
GOOGLE = ('<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Hahmlet:wght@500;700'
          '&family=IBM+Plex+Sans+KR:wght@400;500;600&family=IBM+Plex+Mono:wght@400;500&display=swap">')
PRELOAD = "\n".join(f'<link rel="preload" href="fonts/{n}?v={fv}" as="font" type="font/woff2" crossorigin>'
                    for n in ("slm-sans-kr-400.woff2", "slm-sans-kr-500.woff2", "hahmlet-500.woff2", "hahmlet-700.woff2"))
if FRAG:   # 아티팩트용 조각은 fonts/ 폴더가 없는 곳에서 열리므로 예전처럼 구글 폰트를 부른다(CSS에 원래 이름도 적어 둠)
    frag = out.replace("<!--__FONTLINKS__-->", GOOGLE)
    open(FRAG, "w").write(frag); print("wrote", FRAG, len(frag), "chars", file=sys.stderr)
out = out.replace("<!--__FONTLINKS__-->", PRELOAD)
from make_publish import wrap
os.makedirs(OUT, exist_ok=True)
doc = wrap(out)
open(os.path.join(OUT, "index.html"), "w").write(doc)
if os.path.abspath(OUT) != os.path.abspath(os.path.dirname(FONTS)):   # 다른 폴더로 빌드하면 글꼴도 같이 옮긴다
    import shutil
    shutil.copytree(FONTS, os.path.join(OUT, "fonts"), dirs_exist_ok=True)
print("wrote", os.path.join(OUT, "index.html"), len(doc.encode()), "bytes", file=sys.stderr)
