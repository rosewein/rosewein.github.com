"""큰 도로 레이어(시안): 고속국도·도시고속도로, 서울시 주간선도로, 한 방향 3차로(왕복 6차로) 이상인 길을 그린다.

python3 src/majorroads.py --links   RAW/nodelink/의 표준노드링크 zip에서 서울 링크만 뽑아 RAW/nodelink/seoul_links.json으로
python3 src/majorroads.py --sudo 경로/data.json   「수도권 도시 연대지도 시안」 data.json에서 서울 둘레 도로 선(RAW/nodelink/sudo_roads.json)과
                                    구간 개통일 표(data/majorroads_open_sudo.csv)를 뽑는다
python3 src/majorroads_plan.py      연혁도 대조(data/majorroads_plan.json)
python3 src/majorroads.py           data/majorroads.json

원자료
- 국가교통정보센터(its.go.kr) 「전국표준노드링크」 [2026-11-11]NODELINKDATA.zip → RAW/nodelink/nodelink_20261111.zip
  MOCT_LINK: 방향마다 링크 하나. LANES는 그 방향 차로 수(중앙버스전용차로·가변차로·가감속차로는 빼고 셈, 구축기준 고시),
  ROAD_RANK 101 고속국도, 102 도시고속국도, 103 일반국도, 104 특별·광역시도. CONNECT 0 본선, 1 연결로. 좌표는 EPSG:5186.
  서울 링크는 LINK_ID 앞 세 자리(권역 번호) 100–129.
- 서울 열린데이터광장 「서울시 소통 돌발 도로 분류 정보」(OA-15059, 예전 이름 「서울시 도로 기능별 구분정보」) 2025년 파일
  → RAW/nodelink/seoul_road_class_2025.xlsx. 도로축코드·도로명·분류(도시고속도로·주간선·보조간선·기타). 교통정보용 링크 체계라
  도시계획상의 분류와 다를 수 있다는 안내가 붙어 있음.

고르는 것(cls)
- x: ROAD_RANK 101·102 본선(연결로 빼고)
- a: 서울시 분류의 주간선도로(차로 수와 상관없이)
- b: 서울시 분류의 보조간선도로(차로 수와 상관없이)
- m: 그 밖에 한 방향 3차로 이상(왕복 6차로 이상)인 국도·특별시도 본선

없어진 고가도로: data/majorroads_gone.csv(연 날·닫은 날·근거). 선은 OSM 서울 추출본(RAW/osm/seoul/Seoul.osm.pbf)의 지금 길·물길을
그 고가의 길이만큼 잘라 그린 근사(청계고가 = 청계천 물길, 삼일고가 = 삼일대로, 서울역고가 = 서울로 7017, 아현고가 = 신촌로).

해
- o(개통): 세 단계로 붙인다.
  1) data/majorroads_open.csv 가운데 쓰임이 '우선'인 줄. 노선 이름과 조건(링크 가운데 점의 경위도 x·y, 도로등급 rank)으로 고른다.
  2) 「수도권 도시 연대지도 시안」의 구간 개통일(data/majorroads_open_sudo.csv). 링크를 25m 간격 점으로 나눠 점의 절반 이상이
     같은 도로로 맞춘 수도권 시안 선(RAW/nodelink/sudo_roads.json)에서 45m 안이면, 가장 많이 닿은 선의 날짜를 붙인다.
     이름이 다른 길(고가 아래 길, 지하도로 위 길 등)에 날짜가 옮겨 붙지 않게 SUDO_NAME으로 짝지은 이름끼리만 맞춘다.
  3) majorroads_open.csv 가운데 쓰임이 '대신'인 줄(수도권 시안 선이 닿지 않은 링크에만).
- p(결정): data/majorroads_plan.json(연혁도 대조). 그 해 연혁도에 광로·대로로 그려져 있고, 그 뒤 그 링크를 덮는 연혁도의
  절반 이상에서도 그려져 있으면 그 해. 결정 해가 없는 링크가 같은 이름 링크 둘 이상과 이어져 있고 그 링크들에 결정 해가 있으면
  그 가운데 늦은 해를 붙인다(600m 이하 링크만, 다섯 번 되풀이: 그림 글자 등에 가려 빠진 짧은 틈을 메움). 연혁도는 「도시계획으로 결정된 길」이라 실제로 뚫린 해는 그 뒤일 수 있다.
"""
import csv, json, os, sys, zipfile, collections
sys.dont_write_bytecode = True
import numpy as np
from shapely.geometry import LineString, MultiLineString
from shapely.ops import linemerge
from pyproj import Transformer
from paths import DATA, RAW

NL = os.path.join(RAW, "nodelink")
ZIP = os.path.join(NL, "nodelink_20261111.zip")
LINKS = os.path.join(NL, "seoul_links.json")
XLSX = os.path.join(NL, "seoul_road_class_2025.xlsx")
OUT = os.path.join(DATA, "majorroads.json")
SUDO = os.path.join(NL, "sudo_roads.json")
SUDO_CSV = os.path.join(DATA, "majorroads_open_sudo.csv")
# 표준노드링크 이름 → 수도권 시안 노선 이름(art·hw). 여기 없는 이름은 수도권 시안 날짜를 받지 않는다.
# 국회대로(신월여의지하도로 위)·화랑로(북부간선 아래)·노들로·정릉로처럼 겹쳐 지나는 길은 일부러 뺐다(2026-11-26 대조)
SUDO_NAME = {
    "올림픽대로": {"올림픽대로"}, "강변북로": {"강변북로", "자유로"}, "내부순환도로": {"내부순환로"},
    "동부간선도로": {"동부간선로", "분당수서로"}, "동부간선로": {"동부간선로"}, "분당수서로": {"분당수서로"},
    "북부간선도로": {"북부간선도로"}, "강남순환도시고속도로": {"강남순환로"}, "강남순환로": {"강남순환로"}, "신월여의지하도로": {"신월여의지하도로"},
    "김포한강로": {"김포한강로"}, "우면산로": {"우면산로"},
    "경부고속도로": {"경부"}, "경인고속도로": {"경인"}, "수도권제1순환고속도로": {"외곽"}, "세종포천고속도로": {"세종포천"},
    "인천국제공항고속도로": {"공항"}, "서해안고속도로": {"서해안"}, "용인서울고속도로": {"용인서울"}, "서울양양고속도로": {"서울양양"},
}
CLS_NAME = {"x": "고속국도·도시고속국도", "a": "주간선도로(서울시 분류)", "b": "보조간선도로(서울시 분류)", "m": "왕복 6차로 이상"}
TO_LL = Transformer.from_crs(5186, 4326, always_xy=True)


def extract_links():
    import shapefile, tempfile
    with zipfile.ZipFile(ZIP) as z, tempfile.TemporaryDirectory() as td:
        for n in z.namelist():
            if n.startswith("MOCT_LINK."): z.extract(n, td)
        r = shapefile.Reader(os.path.join(td, "MOCT_LINK"), encoding="cp949"); F = [f[0] for f in r.fields[1:]]; out = []
        for sr in r.iterShapeRecords():
            rec = dict(zip(F, sr.record))
            if not (100 <= int(rec["LINK_ID"][:3]) <= 129): continue
            rec["pts"] = [[round(x, 1), round(y, 1)] for x, y in sr.shape.points]; out.append(rec)
    json.dump(out, open(LINKS, "w"), ensure_ascii=False)
    print("서울 링크", len(out), file=sys.stderr)


def road_class():
    import openpyxl
    rows = list(openpyxl.load_workbook(XLSX, read_only=True).worksheets[0].iter_rows(values_only=True))[1:]
    return {r[1]: r[3] for r in rows}


def select_links():
    """고를 링크(본선, 사용 중). 양방향이 같은 두 마디를 잇는 짝은 하나만 남긴다."""
    L = json.load(open(LINKS)); cls_by_name = road_class(); seen = set(); out = []
    for l in L:
        if l["ROAD_USE"] != "0" or l["CONNECT"] != "0" or l["ROAD_RANK"] not in ("101", "102", "103", "104"): continue
        if l["ROAD_RANK"] in ("101", "102"): c = "x"
        elif cls_by_name.get(l["ROAD_NAME"]) == "주간선도로": c = "a"
        elif cls_by_name.get(l["ROAD_NAME"]) == "보조간선도로": c = "b"
        elif l["LANES"] >= 3: c = "m"
        else: continue
        k = tuple(sorted((l["F_NODE"], l["T_NODE"])))
        if k in seen: continue
        seen.add(k); l = dict(l); l["cls"] = c; out.append(l)
    return out


def drop_parallel(links, near=32.0, share=0.5):
    """나뉜 차도(상·하행 따로 그린 링크)는 한쪽만 남긴다: 이름이 같은 이미 남긴 링크에 점의 절반 넘게 32m 안이면 뺌."""
    grid = collections.defaultdict(list); keep = []
    def pts(l, step=20):
        ls = LineString(l["pts"]); n = max(2, int(ls.length // step) + 1)
        return np.array([ls.interpolate(t, normalized=True).coords[0] for t in np.linspace(0, 1, n)])
    for l in sorted(links, key=lambda l: -l["LENGTH"]):
        P = pts(l); nm = l["ROAD_NAME"]; close = 0
        for x, y in P:
            gx, gy = int(x // near), int(y // near); hit = False
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    for (qx, qy) in grid.get((nm, gx + dx, gy + dy), ()):
                        if (qx - x) ** 2 + (qy - y) ** 2 < near * near: hit = True; break
                    if hit: break
                if hit: break
            close += hit
        if close / len(P) > share: continue
        keep.append(l)
        for x, y in P: grid[(nm, int(x // near), int(y // near))].append((x, y))
    return keep


def extract_sudo(path):
    """수도권 시안 data.json → 서울 둘레 선(RAW)과 구간 개통일 표(data). 선은 OSM(ODbL)에서 온 것이라 저장소에는 표만 넣는다."""
    d = json.load(open(path)); B = (126.70, 37.40, 127.25, 37.73); seg = {}
    for k in ("art", "hw"):
        seg[k] = [{"r": s["r"], "d": s["d"], "p": s["p"]} for s in d[k]["seg"]
                  if any(B[0] <= x <= B[2] and B[1] <= y <= B[3] for x, y in s["p"])]
    json.dump({"note": "「수도권 도시 연대지도 시안」 data.json의 art(자동차전용도로)·hw(고속도로) 선 가운데 서울 둘레에 걸친 것. 선형은 OSM(ODbL)",
               "seg": seg}, open(SUDO, "w"), ensure_ascii=False)
    used = {(k, s["r"]) for k in seg for s in seg[k]}
    with open(SUDO_CSV, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f); w.writerow(["갈래", "노선", "노선이름", "구간", "개통일", "근거", "주소", "메모"])
        for k in ("art", "hw"):
            for r, rows in d[k]["sec"].items():
                if (k, r) not in used: continue
                for dt, lab, sn, su, nt in rows: w.writerow([k, r, d[k]["rn"].get(r, r), lab, dt, sn, su, nt])
    print("수도권 시안 선", {k: len(v) for k, v in seg.items()}, file=sys.stderr)


def sudo_level(src):
    """수도권 시안 채팅의 확인 정도(구상 문서 「고속도로」·「간선도로」 절): 위키백과·국가기록원 연표는 WebFetch 변환 페이지, 나머지는 검색 결과 요약."""
    if "국가기록원" in src or ("위키백과" in src and "영어" not in src) or "머니투데이" in src: return "변환된 페이지"
    return "검색 결과 요약"


def open_rows():
    """개통일 표 하나로 합친다(팝업에서 번호로 가리킴). 내 표(majorroads_open.csv) 다음에 수도권 시안 표."""
    rows = []
    for r in csv.DictReader(open(os.path.join(DATA, "majorroads_open.csv"), encoding="utf-8")):
        r["from"] = "csv"; rows.append(r)
    if os.path.exists(SUDO_CSV):
        seen = {}
        for r in csv.DictReader(open(SUDO_CSV, encoding="utf-8")):
            k = (r["갈래"], r["노선"], r["개통일"])
            if k in seen:   # 같은 날 연 구간이 둘(외곽 2006-06-30 일산–송추·퇴계원–의정부 등): 선에는 날짜만 있어 어느 쪽인지 못 가르므로 함께 적는다
                q = seen[k]; q["구간"] += " 또는 " + r["구간"]
                if r["메모"] and r["메모"] not in q["메모"]: q["메모"] = (q["메모"] + " " if q["메모"] else "") + r["메모"]
                continue
            seen[k] = {"from": "sudo", "노선": r["노선이름"], "key": k, "구간": r["구간"], "개통일": r["개통일"],
                       "근거": "「수도권 도시 연대지도 시안」 정리: " + r["근거"], "주소": r["주소"], "확인": sudo_level(r["근거"]), "메모": r["메모"]}
            rows.append(seen[k])
    return rows


def sudo_match(links):
    """링크 → (갈래, 노선, 날짜). SUDO_NAME으로 짝지은 이름의 수도권 시안 선에만 맞춘다."""
    if not os.path.exists(SUDO): return {}
    from shapely.strtree import STRtree
    to5186 = Transformer.from_crs(4326, 5186, always_xy=True); S = json.load(open(SUDO)); G, meta = [], []
    for k, ss in S["seg"].items():
        for s in ss:
            x, y = to5186.transform(*np.array(s["p"]).T); G.append(LineString(np.c_[x, y])); meta.append((k, s["r"], s["d"]))
    tree = STRtree(G); out = {}
    for l in links:
        ok = SUDO_NAME.get(l["ROAD_NAME"])
        if not ok: continue
        ls = LineString(l["pts"]); n = max(2, int(ls.length // 25) + 1); hits = collections.Counter()
        for t in np.linspace(0, 1, n):
            p = ls.interpolate(t, normalized=True); best = None
            for i in tree.query(p.buffer(45)):
                if meta[i][1] not in ok: continue
                dd = G[i].distance(p)
                if dd < 45 and (best is None or dd < best[0]): best = (dd, meta[i])
            if best: hits[best[1]] += 1
        if hits and sum(hits.values()) / n >= 0.5: out[l["LINK_ID"]] = hits.most_common(1)[0][0]
    return out


def plan_year(on, missing, years):
    for i, y in enumerate(years):
        if y not in on: continue
        later = [z for z in years[i + 1:] if z not in missing]
        if not later or sum(z in on for z in later) >= 0.5 * len(later): return y
    return None


GONE_CSV = os.path.join(DATA, "majorroads_gone.csv")


def gone_roads():
    """없어진 고가도로(data/majorroads_gone.csv). 선은 OSM에서 지금 길·물길을 따라 길이만큼 잘라 그린 근사."""
    from paths import WORK
    from shapely.ops import substring
    from shapely.geometry import Point
    cache = os.path.join(WORK, "gone_osm.json")
    if not os.path.exists(cache):
        import osmium
        pbf = os.path.join(RAW, "osm", "seoul", "Seoul.osm.pbf")
        class H(osmium.SimpleHandler):
            def __init__(s): super().__init__(); s.out = []
            def way(s, w):
                nm = w.tags.get("name", ""); t = dict(w.tags)
                ok = (nm == "청계천" and t.get("waterway") == "river") or nm == "서울로 7017" or (nm in ("삼일대로", "신촌로") and t.get("highway") == "primary")
                if ok: s.out.append({"name": nm, "oneway": t.get("oneway"), "p": [(n.lon, n.lat) for n in w.nodes]})
        h = H(); h.apply_file(pbf, locations=True); os.makedirs(WORK, exist_ok=True)
        json.dump(h.out, open(cache, "w"), ensure_ascii=False)
    W = json.load(open(cache)); to5186 = Transformer.from_crs(4326, 5186, always_xy=True)
    def pj(p): x, y = to5186.transform(*np.array(p).T); return LineString(np.c_[x, y])
    def pt(lon, lat): return Point(*to5186.transform(lon, lat))
    def ways(nm, keep=lambda p: True): return [pj(w["p"]) for w in W if w["name"] == nm and keep(w["p"])]
    def longest(gs):
        m = linemerge(gs); return max(getattr(m, "geoms", [m]), key=lambda g: g.length)
    ch = longest(ways("청계천"))
    geo = {}
    s0 = ch.project(pt(126.9806, 37.5692)); geo["청계고가도로"] = [substring(ch, s0, s0 + 5650)]
    sam = linemerge(ways("삼일대로", lambda p: p[-1][1] < p[0][1] and 37.55 < p[0][1] < 37.575))   # 남쪽 방향 차로
    sam = min(getattr(sam, "geoms", [sam]), key=lambda g: g.distance(pt(126.98757, 37.5690)))
    s0 = sam.project(sam.intersection(ch) if sam.intersects(ch) else pt(126.98757, 37.5690)); geo["삼일고가도로"] = [substring(sam, s0, s0 + 870)]
    geo["서울역고가도로"] = ways("서울로 7017")
    sc = longest(ways("신촌로", lambda p: p[-1][0] > p[0][0] and p[0][0] > 126.94))   # 동쪽 방향 차로
    geo["아현고가도로"] = [substring(sc, sc.length - 940, sc.length)]
    rows, out = [], []
    for i, r in enumerate(csv.DictReader(open(GONE_CSV, encoding="utf-8"))):
        rows.append({k: r[k] for k in ("이름", "연날", "닫은날", "길이", "구간", "근거", "주소", "확인", "메모", "선")})
        lines = []
        for g in geo[r["이름"]]:
            g = g.simplify(4); x, y = TO_LL.transform(*np.array(g.coords).T); lines.append([[round(a, 5), round(b, 5)] for a, b in zip(x, y)])
        out.append({"n": r["이름"], "o": r["연날"], "c": r["닫은날"], "i": i, "g": lines})
        print("없어진 고가", r["이름"], [round(g.length) for g in geo[r["이름"]]], "m", file=sys.stderr)
    return rows, out


def main():
    if "--links" in sys.argv: return extract_links()
    if "--sudo" in sys.argv: return extract_sudo(sys.argv[sys.argv.index("--sudo") + 1])
    links = drop_parallel(select_links())
    plan = json.load(open(os.path.join(DATA, "majorroads_plan.json"))); years = plan["years"]
    rows = open_rows(); by_name = collections.defaultdict(list); by_key = {}
    for i, r in enumerate(rows):
        r["i"] = i
        if r["from"] == "csv": by_name[r["노선"]].append(r)
        else: by_key[r["key"]] = r
    sm = sudo_match(links); nb2 = collections.defaultdict(list)
    for l in links:
        for n in (l["F_NODE"], l["T_NODE"]): nb2[(l["ROAD_NAME"], n)].append(l)
    # 수도권 시안 선에서 조금 비껴 맞지 않은 링크(1.5km 이하)는 같은 이름으로 이어진 링크의 날짜 가운데 늦은 것을 받는다(열 번까지)
    for _ in range(10):
        add = {}
        for l in links:
            if l["LINK_ID"] in sm or l["ROAD_NAME"] not in SUDO_NAME or l["LENGTH"] > 1500: continue
            ks = [sm[q["LINK_ID"]] for n in (l["F_NODE"], l["T_NODE"]) for q in nb2[(l["ROAD_NAME"], n)] if q is not l and q["LINK_ID"] in sm]
            if ks: add[l["LINK_ID"]] = max(ks, key=lambda k: k[2])
        if not add: break
        sm.update(add)
    for l in links:
        on, miss = plan["links"].get(l["LINK_ID"], [[], years]); l["p"] = plan_year(on, miss, years)
    # 짧은 틈 메우기
    nb = collections.defaultdict(list)
    for l in links:
        for n in (l["F_NODE"], l["T_NODE"]): nb[(l["ROAD_NAME"], n)].append(l)
    for _ in range(5):
        fill = {}
        for l in links:
            if l["p"] is not None or l["LENGTH"] > 600: continue
            ps = [q["p"] for n in (l["F_NODE"], l["T_NODE"]) for q in nb[(l["ROAD_NAME"], n)] if q is not l and q["p"] is not None]
            if len(ps) >= 2: fill[id(l)] = max(ps)
        if not fill: break
        for l in links:
            if id(l) in fill: l["p"] = fill[id(l)]; l["filled"] = True
    stat = collections.Counter(); groups = collections.defaultdict(list)
    for l in links:
        P = np.array(l["pts"]); cx, cy = TO_LL.transform(*P.mean(0))
        def pick(use):
            for r in by_name.get(l["ROAD_NAME"], []):
                if r["쓰임"] == use and (not r["조건"] or eval(r["조건"], {}, {"x": cx, "y": cy, "rank": l["ROAD_RANK"]})): return r
        r = pick("우선") or by_key.get(sm.get(l["LINK_ID"])) or pick("대신")
        o, oi = (r["개통일"][:10], r["i"]) if r else (None, None)
        p = l["p"]
        if l.get("filled"): stat[("메운 링크", "")] += l["LENGTH"]
        if r: stat[("개통일 출처", r["from"] + ("" if r["from"] == "sudo" else "·" + r["쓰임"]))] += l["LENGTH"]
        stat[(l["cls"], "o" if o else "p" if p else "-")] += l["LENGTH"]
        groups[(l["ROAD_NAME"], l["cls"], o, oi, p, min(l["LANES"], 6))].append(LineString(P))
    segs = []
    for (nm, c, o, oi, p, ln), gs in groups.items():
        m = linemerge(gs); parts = list(getattr(m, "geoms", [m]))
        for g in parts:
            g = g.simplify(12 if c in "bm" else 8)
            x, y = TO_LL.transform(*np.array(g.coords).T)
            s = {"n": nm, "c": c, "l": int(ln), "g": [[round(a, 5), round(b, 5)] for a, b in zip(x, y)]}
            if o: s["o"] = o; s["oi"] = oi
            if p: s["p"] = p
            segs.append(s)
    # 쓰인 개통일 줄만 남기고 번호를 다시 매긴다
    used = sorted({s["oi"] for s in segs if "oi" in s}); re_i = {o: i for i, o in enumerate(used)}
    for s in segs:
        if "oi" in s: s["oi"] = re_i[s["oi"]]
    rows = [rows[o] for o in used]
    out = {"note": "큰 도로(시안). o = 개통일(oi = open 표 번호), p = 연혁도에 광로·대로로 결정돼 그려진 첫 해. 선은 2026-11-11 표준노드링크(지금 모습)",
           "cls": CLS_NAME, "planSheets": [{"year": s["year"], "title": s["title"]} for s in plan["sheets"]],
           "open": [{k: r.get(k, "") for k in ("노선", "구간", "개통일", "근거", "주소", "확인", "메모")} for r in rows], "segs": segs}
    if os.path.exists(GONE_CSV): out["goneRows"], out["gone"] = gone_roads()
    json.dump(out, open(OUT, "w"), ensure_ascii=False, separators=(",", ":"))
    print("구간", len(segs), "점", sum(len(s["g"]) for s in segs), "bytes", os.path.getsize(OUT), file=sys.stderr)
    for k in sorted(stat): print(k, round(stat[k] / 1000), "km", file=sys.stderr)


if __name__ == "__main__":
    main()
