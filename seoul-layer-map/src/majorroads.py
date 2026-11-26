"""큰 도로 레이어(시안): 고속국도·도시고속도로, 서울시 주간선도로, 한 방향 3차로(왕복 6차로) 이상인 길을 그린다.

python3 src/majorroads.py --links   RAW/nodelink/의 표준노드링크 zip에서 서울 링크만 뽑아 RAW/nodelink/seoul_links.json으로
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
- m: 그 밖에 한 방향 3차로 이상(왕복 6차로 이상)인 국도·특별시도 본선

해
- o(개통): data/majorroads_open.csv. 노선 이름과 조건(링크 가운데 점의 경위도 x·y, 도로등급 rank)으로 붙인다.
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


def open_rows():
    rows = list(csv.DictReader(open(os.path.join(DATA, "majorroads_open.csv"), encoding="utf-8")))
    for r in rows:
        d = r["개통일"]; r["year"] = int(d[:4]); r["frac"] = (int(d[5:7]) - 1) / 12 if len(d) >= 7 else 0.0
    return rows


def plan_year(on, missing, years):
    for i, y in enumerate(years):
        if y not in on: continue
        later = [z for z in years[i + 1:] if z not in missing]
        if not later or sum(z in on for z in later) >= 0.5 * len(later): return y
    return None


def main():
    if "--links" in sys.argv: return extract_links()
    links = drop_parallel(select_links())
    plan = json.load(open(os.path.join(DATA, "majorroads_plan.json"))); years = plan["years"]
    rows = open_rows(); by_name = collections.defaultdict(list)
    for r in rows: by_name[r["노선"]].append(r)
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
        o = None
        for r in by_name.get(l["ROAD_NAME"], []):
            if not r["조건"] or eval(r["조건"], {}, {"x": cx, "y": cy, "rank": l["ROAD_RANK"]}):
                o = r["개통일"][:7]; break
        p = l["p"]
        if l.get("filled"): stat[("메운 링크", "")] += l["LENGTH"]
        stat[(l["cls"], "o" if o else "p" if p else "-")] += l["LENGTH"]
        groups[(l["ROAD_NAME"], l["cls"], o, p, min(l["LANES"], 6))].append(LineString(P))
    segs = []
    for (nm, c, o, p, ln), gs in groups.items():
        m = linemerge(gs); parts = list(getattr(m, "geoms", [m]))
        for g in parts:
            g = g.simplify(8)
            x, y = TO_LL.transform(*np.array(g.coords).T)
            s = {"n": nm, "c": c, "l": int(ln), "g": [[round(a, 5), round(b, 5)] for a, b in zip(x, y)]}
            if o: s["o"] = o
            if p: s["p"] = p
            segs.append(s)
    out = {"note": "큰 도로(시안). o = 개통(majorroads_open.csv), p = 연혁도에 광로·대로로 결정돼 그려진 첫 해. 선은 2026-11-11 표준노드링크(지금 모습)",
           "planSheets": plan["sheets"], "open": [{k: r[k] for k in ("노선", "구간", "개통일", "근거", "확인", "메모")} for r in rows], "segs": segs}
    json.dump(out, open(OUT, "w"), ensure_ascii=False, separators=(",", ":"))
    print("구간", len(segs), "점", sum(len(s["g"]) for s in segs), "bytes", os.path.getsize(OUT), file=sys.stderr)
    for k in sorted(stat): print(k, round(stat[k] / 1000), "km", file=sys.stderr)


if __name__ == "__main__":
    main()
