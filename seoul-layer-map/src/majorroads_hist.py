"""큰 도로 레이어(시안): 표준노드링크 옛 판(2008–2025)에 지금 큰 도로 링크가 몇 년 판부터 나오는지 잰다.

python3 src/majorroads_hist.py --extract 2014 경로/zip   옛 판 zip에서 서울 둘레 링크 선만 뽑아 RAW/nodelink/hist/links_2014.json으로
python3 src/majorroads_hist.py                          → data/majorroads_hist.json

원자료: 국가교통정보센터 「전국표준노드링크」 자료실(its.go.kr/nodelink/nodelinkRef)에서 해마다 그해 마지막 판 하나(VERS).
2008–2025년 판은 좌표가 경위도(ITRF2000)이고, 2026-11-11 판(majorroads.py가 쓰는 지금 판)은 EPSG:5186이다.

재는 법
- 지금 큰 도로 링크(majorroads.select_links(), 나뉜 차도 한쪽만 남기기 전)를 25m 간격 점으로 나눈다.
- 옛 판마다 두 기준으로 「있음」을 잰다. 촘촘히: 점의 80% 넘게가 옛 판 링크 선에서 30m 안. 느슨하게: 점의 50% 넘게가 70m 안.
  30m는 판마다 선형을 다시 그린 차이와 예전에 한 줄로 그리던 나뉜 차도를 견디려고 잡은 값이고, 느슨한 기준은 옛 판이 선을 30m 넘게
  비껴 그렸던 길을 새 길로 잘못 보지 않으려고 둔다.
- 해 매기기는 majorroads.py(hist_year)가 한다. 처음 나온 판(그 뒤 판에서 한 번까지 빠져도 됨)의 해를 두 기준 가운데 이른 쪽으로 잡고,
  2010년 판까지(실린 길이 적음)와 2020·2025년 판(실린 길이 크게 늘어남)에 처음 나오면 「늦어도 그 판에는 있었음」만,
  그 밖의 판에 처음 나오면 「바로 앞 판에는 없다가 이 판에 나옴(그 사이 개통한 것으로 추정)」으로 본다.
- 검증: 개통일을 아는 길 가운데 강남순환로(2016-07)·세종포천(2017-06)·서부간선지하도로(2021-09)는 개통 뒤 첫 판에 나오고,
  김포한강로(2011-07)는 두 판 늦은 2013년 판에, 동부간선로 한 구간(2017-01-01)은 개통 전인 2016-12-23 판에 먼저 나온다.
"""
import json, os, sys, zipfile, io
import numpy as np
import shapefile
from pyproj import Transformer
from shapely.geometry import LineString, Point
from shapely.strtree import STRtree

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.dont_write_bytecode = True
from paths import RAW, DATA

HIST = os.path.join(RAW, "nodelink", "hist")
OUT = os.path.join(DATA, "majorroads_hist.json")
# 해 → (판 날짜, 자료실 파일 이름)
VERS = {
    2008: ("2008-11-05", "[20081105버전]전국표준노드링크.zip"),
    2009: ("2009-12-16", "전국표준노드링크2009_12_16.zip"),
    2010: ("2010-12-31", "[전국표준노드링크]20101231.zip"),
    2011: ("2011-12-07", "[전국표준노드링크]20111207.zip"),
    2012: ("2012-11-20", "[전국표준노드링크]20121120.zip"),
    2013: ("2013-11-28", "[전국표준노드링크]20131128.zip"),
    2014: ("2014-11-17", "[전국표준노드링크]20141117.zip"),
    2015: ("2015-12-31", "[2015-12-31] 전국표준노드링크.zip"),
    2016: ("2016-12-23", "[2016-12-23] 전국표준노드링크.zip"),
    2017: ("2017-12-21", "[2017-12-21] 전국표준노드링크.zip"),
    2018: ("2018-12-21", "[2018-12-21]전국표준노드링크.zip"),
    2019: ("2019-09-20", "[2019-09-20] 전국표준노드링크.zip"),
    2020: ("2020-11-30", "[2020-11-30]NODELINKDATA.zip"),
    2021: ("2021-12-09", "[2021-12-09]NODELINKDATA.zip"),
    2022: ("2022-07-08", "[2022-07-08]NODELINKDATA.zip"),
    2023: ("2023-12-18", "[2023-12-18]NODELINKDATA.zip"),
    2024: ("2024-11-29", "[2024-11-29]NODELINKDATA.zip"),
    2025: ("2025-12-30", "[2025-12-30]NODELINKDATA.zip"),
}
NOW = (2026, "2026-11-11")
BBOX = (126.70, 37.40, 127.27, 37.73)
TOL, SHARE = 30.0, 0.8
LOOSE, LOOSE_SHARE = 70.0, 0.5   # 선을 다시 그려 30m 넘게 옮겨진 것과 새로 난 길을 가르려는 느슨한 기준
TO5186 = Transformer.from_crs(4326, 5186, always_xy=True)


def find_link_shp(z):
    """zip 안(겹 zip이면 그 안까지)에서 링크 shp를 찾는다."""
    names = z.namelist()
    shp = [n for n in names if n.lower().endswith(".shp") and "link" in os.path.basename(n).lower() and "multi" not in n.lower()]
    if shp: return z, shp[0]
    for n in names:
        if n.lower().endswith(".zip"):
            r = find_link_shp(zipfile.ZipFile(io.BytesIO(z.read(n))))
            if r: return r
    return None


def extract(year, path):
    z, shp = find_link_shp(zipfile.ZipFile(path))
    base = shp[:-4]; get = lambda ext: io.BytesIO(z.read(next(n for n in z.namelist() if n.lower() == (base + ext).lower())))
    prj = z.read(next(n for n in z.namelist() if n.lower() == (base + ".prj").lower())).decode("latin1")
    geo = prj.startswith("GEOGCS")
    r = shapefile.Reader(shp=get(".shp"), shx=get(".shx"), dbf=get(".dbf"), encoding="cp949")
    if geo: x0, y0, x1, y1 = BBOX
    else:
        (x0, y0), (x1, y1) = TO5186.transform(BBOX[0], BBOX[1]), TO5186.transform(BBOX[2], BBOX[3])
    out = []
    for s in r.iterShapes():
        if not s.points: continue
        bx = s.bbox
        if bx[2] < x0 or bx[0] > x1 or bx[3] < y0 or bx[1] > y1: continue
        P = np.array(s.points)
        if geo: P = np.c_[TO5186.transform(P[:, 0], P[:, 1])]
        out.append([[round(a, 1), round(b, 1)] for a, b in P])
    os.makedirs(HIST, exist_ok=True)
    json.dump({"year": year, "file": os.path.basename(path), "geographic": geo, "lines": out}, open(os.path.join(HIST, f"links_{year}.json"), "w"))
    print(year, shp, "경위도" if geo else "투영", len(out), "선", file=sys.stderr)


def main():
    if "--extract" in sys.argv:
        i = sys.argv.index("--extract"); return extract(int(sys.argv[i + 1]), sys.argv[i + 2])
    import majorroads as M
    import shapely
    links = M.select_links()
    P, own = [], []
    for k, l in enumerate(links):
        ls = LineString(l["pts"]); n = max(2, int(ls.length // 25) + 1)
        P += [ls.interpolate(t, normalized=True) for t in np.linspace(0, 1, n)]; own += [k] * n
    P = np.array(P, dtype=object); own = np.array(own); cnt = np.bincount(own, None, len(links))
    res = {l["LINK_ID"]: [[], []] for l in links}; vers = []
    for y in sorted(VERS):
        f = os.path.join(HIST, f"links_{y}.json")
        if not os.path.exists(f): print("없음", f, file=sys.stderr); continue
        G = [LineString(c) for c in json.load(open(f))["lines"] if len(c) >= 2]; tree = STRtree(G); km = [0.0, 0.0]
        for t, (tol, share_min) in enumerate(((TOL, SHARE), (LOOSE, LOOSE_SHARE))):
            near = np.zeros(len(P), bool); near[np.unique(tree.query(P, predicate="dwithin", distance=tol)[0])] = True
            share = np.bincount(own, near, len(links)) / cnt
            for k, l in enumerate(links):
                if share[k] > share_min: res[l["LINK_ID"]][t].append(y); km[t] += l["LENGTH"] / 1000
        vers.append({"year": y, "date": VERS[y][0], "file": VERS[y][1], "lines": len(G), "onKm": round(km[0]), "looseKm": round(km[1])})
        print(y, VERS[y][0], "선", len(G), "지금 큰 도로 가운데 있는 것", round(km[0]), "km · 느슨하게", round(km[1]), "km", file=sys.stderr)
    json.dump({"note": f"지금 큰 도로 링크마다 표준노드링크 옛 판(해마다 그해 마지막 판)에 있던 해. [촘촘히, 느슨하게]: 점의 {SHARE:.0%} 넘게가 옛 판 링크에서 {TOL:.0f}m 안 / {LOOSE_SHARE:.0%} 넘게가 {LOOSE:.0f}m 안",
               "versions": vers, "now": {"year": NOW[0], "date": NOW[1]}, "links": res},
              open(OUT, "w"), ensure_ascii=False, separators=(",", ":"))


if __name__ == "__main__":
    main()
