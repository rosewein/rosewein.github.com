"""조선 후기 역·원·나루와 도성에서 나가는 대로(시안).
python3 src/joseon.py → data/joseon.json

- 점의 위치는 두 가지로 잡는다.
  표석: 서울시가 세운 '○○ 터' 표석의 주소(서울신문 2022.2.11 「김별아의 도시기행문」에 실린 주소)를 OSM에서 찾은 자리.
  동리: 국사편찬위원회 HGIS 행정구역 포인트에서 1912–1914년 그 이름을 가진 동리의 자리(역·나루 터 자체가 아니라 마을 자리).
- 문헌 근거는 국사편찬위원회 「한양역사지리정보 역사지명데이터」(xlsx)에 실린 원문(『동국여지비고』 등)을 옮겼다.
- 대로는 경유지를 지금 도로(OSM) 위 최단 경로로 이은 근사선이다. 전차처럼 '지금 길을 따라 그린 선'이고 옛길 자체가 아니다.
  강은 나루와 나루 사이를 곧은 점선(나룻배)으로 잇는다.
"""
import json, math, sys
sys.dont_write_bytecode = True
import numpy as np
from scipy.sparse import csr_matrix
from scipy.sparse.csgraph import dijkstra
from scipy.spatial import cKDTree
from paths import DATA, RAW

# ---------- 점 ----------
# kind: 역(驛)·원(院)·나루(津·渡·浦)·문(도성 문)
# pos: 위치를 잡은 방법, src: 문헌 근거
HG = "HGIS 1912–1914 동리"
P = [
  # 역
  dict(id="cheongpa", name="청파역", hanja="靑坡驛", kind="역", lat=37.54467, lng=126.96515, pos=f"{HG} 청파삼계(신뢰도 2·추정)",
       src="『동국여지비고』 「在崇禮門外三里」, 『대동지지』 「崇禮門外二里」. 노원역과 함께 병조에 딸린 역(『대동지지』)", conf="중간"),
  dict(id="yeonseo", name="연서역", hanja="延曙驛", kind="역", lat=37.60587, lng=126.91836, pos=f"{HG} 은평면 역촌동(驛村洞)",
       src="「동여도」(연서역), 『대동여지도』·『청구요람』(영서역 迎曙驛)", conf="중간"),
  dict(id="yangjae", name="양재역", hanja="良才驛", kind="역", lat=37.49082, lng=127.04004, pos=f"{HG} 광주군 언주면 역촌(驛村)",
       src="영남대로가 지나던 역, 역말(驛村)·말죽거리(서울신문 2026.7.31 「서울 로드」 강남대로 편)", conf="중간"),
  # 원
  dict(id="hongje", name="홍제원", hanja="洪濟院", kind="원", lat=37.58817, lng=126.94642, pos=f"{HG} 은평면 홍제원내동",
       src="『동국여지비고』 「在追慕峴北」, 『동국여지지』 「在都城西八里」", conf="높음"),
  dict(id="boje", name="보제원", hanja="普濟院", kind="원", lat=37.58271, lng=127.02953, pos="보제원 터 표석(동대문구 약령시로 2, 안암오거리)",
       src="『동국여지비고』 「在興仁門外三里」", conf="높음"),
  dict(id="itaewon", name="이태원", hanja="利泰院", kind="원", lat=37.54614, lng=126.97951, pos="이태원 터 표석(용산구 두텁바위로 60, 용산고등학교 정문)",
       src="『동국여지비고』 「在木覓山南」", conf="높음"),
  dict(id="jeongwan", name="전관원", hanja="箭串院", kind="원", lat=37.55429, lng=127.04251, pos="전관원 터 표석(성동구 왕십리로 189, 행당중학교 정문)",
       src="『동국여지비고』 「在箭串橋西北」", conf="높음"),
  dict(id="nuwon", name="누원(다락원)", hanja="樓院", kind="원", lat=37.68926, lng=127.04099, pos=f"{HG} 양주군 해등촌면 상누원리",
       src="경흥대로가 혜화문을 나와 미아리고개를 넘어 누원(다락원)을 지남(서울신문 2018.6.28)", conf="중간"),
  # 나루
  dict(id="yanghwa", name="양화나루", hanja="楊花渡", kind="나루", lat=37.5447, lng=126.9124, pos="절두산 순교성지(양화진 옛 터 옆)",
       src="『동국여지지』 「在都城西十四里」, 『동국여지비고』 「即西江下流」", conf="중간"),
  dict(id="mapo", name="마포나루", hanja="麻浦", kind="나루", lat=37.53717, lng=126.94399, pos=f"{HG} 용산면 마포",
       src="『동국여지비고』 「在都城西十里」, 『대동지지』 마포진 「通始興間路」", conf="중간"),
  dict(id="noryang", name="노들나루", hanja="露梁", kind="나루", lat=37.51199, lng=126.94093, pos="HGIS 1914 시흥군 신북면 노량진리",
       src="『동국여지비고』 「在都城南十里」", conf="중간"),
  dict(id="dongjak", name="동작나루", hanja="銅雀津", kind="나루", lat=37.50332, lng=126.97508, pos=f"{HG} 과천군 상북면 동작리",
       src="『대동여지도』·「동여도」 동작진", conf="중간"),
  dict(id="seobinggo", name="서빙고나루", hanja="西氷庫津", kind="나루", lat=37.52285, lng=126.99615, pos=f"{HG} 한지면 서빙고동",
       src="『대동지지』 서빙고진", conf="중간"),
  dict(id="hangang", name="한강나루", hanja="漢江渡", kind="나루", lat=37.53394, lng=127.01024, pos="HGIS 1914 고양군 한지면 한강리",
       src="『세종실록』 지리지 「在木覓山南」", conf="중간"),
  dict(id="sapyeong", name="사평나루", hanja="沙平", kind="나루", lat=37.52049, lng=127.01529, pos=f"{HG} 광주군 언주면 사평리",
       src="한강진 맞은편, 대동여지도의 사평리(서울신문 2006.10.23)", conf="중간"),
  dict(id="dumo", name="두모포", hanja="豆毛浦", kind="나루", lat=37.5416, lng=127.01762, pos=f"{HG} 두모면 두모포",
       src="『동국여지비고』 「在都城東南十里」", conf="중간"),
  dict(id="ttukseom", name="뚝섬나루", hanja="纛島", kind="나루", lat=37.54304, lng=127.05621, pos=f"{HG} 두모면 둑도이계(신뢰도 2·추정)",
       src="송파로 건너가던 나루(서울신문 2006.10.23)", conf="낮음"),
  dict(id="songpa", name="송파나루", hanja="松坡津", kind="나루", lat=37.51024, lng=127.10074, pos=f"{HG} 광주군 중대면 송파동",
       src="「해동지도」 경성오부북한산성부 송파진", conf="중간"),
  dict(id="samjeon", name="삼밭나루", hanja="三田渡", kind="나루", lat=37.50436, lng=127.08856, pos=f"{HG} 광주군 중대면 삼전도동",
       src="『동국여지비고』 「在廣州境 去都城三十里」", conf="중간"),
  dict(id="gwangnaru", name="광나루", hanja="廣津", kind="나루", lat=37.55045, lng=127.10932, pos=f"{HG} 양주군 고양주면 광진리",
       src="한강 5대 나루의 하나(서울시 한강 누리집 「한강의 나루」)", conf="중간"),
  # 도성 문(OSM)
  dict(id="sungnye", name="숭례문", kind="문", lat=37.5599, lng=126.9753, pos="OSM"),
  dict(id="heungin", name="흥인지문", kind="문", lat=37.57115, lng=127.00979, pos="OSM"),
  dict(id="donui", name="돈의문", kind="문", lat=37.56831, lng=126.96881, pos="OSM 돈의문 터"),
  dict(id="soui", name="소의문", kind="문", lat=37.5623, lng=126.9717, pos="OSM 소의문 터"),
  dict(id="gwanghui", name="광희문", kind="문", lat=37.56438, lng=127.01012, pos="OSM"),
  dict(id="hyehwa", name="혜화문", kind="문", lat=37.58795, lng=127.00387, pos="OSM"),
  dict(id="changui", name="창의문", kind="문", lat=37.59262, lng=126.96652, pos="OSM"),
]
PT = {p["id"]: p for p in P}

# ---------- 경유 지점(점으로 그리지 않음) ----------
W = {
  "yeongeun": (37.57118, 126.96156, "영은문·모화관(독립문)"), "muak": (37.5823, 126.9503, "무악재"),
  "nokbeon": (37.60114, 126.93798, "녹번현(HGIS 1912)"), "gupabal": (37.63548, 126.91816, "구파발(HGIS 1912)"),
  "miari": (37.59808, 127.0216, "미아리고개"), "suyu": (37.6372, 127.0249, "수유현 부근"),
  "jungnang": (37.5925, 127.0703, "중랑교(중량포 부근, 추정)"), "mangu": (37.60167, 127.11554, "망우리고개"),
  "jangchung": (37.5590, 127.0058, "장충동"), "yaksu": (37.5548, 127.0106, "약수동"), "beoti": (37.54823, 127.00659, "버티고개"),
  "sinsa": (37.5160, 127.0195, "신사동"), "wonji": (37.44499, 127.04933, "원지동"), "dallae": (37.43945, 127.06088, "달래내고개"),
  "jamwon": (37.5130, 127.0115, "잠원(상림)"), "noksapyeong": (37.5345, 126.9870, "녹사평"),
  "wangsimni": (37.5610, 127.0362, "왕십리"), "hanyang": (37.5560, 127.0450, "한양대 앞"), "neungdong": (37.5480, 127.0740, "능동"),
  "baedari": (37.5470, 126.9700, "청파 배다리 터 부근(추정)"), "dolmoru": (37.5350, 126.9735, "돌모루(삼각지 부근, 추정)"),
  "ichon": (37.5205, 126.9770, "이촌 강변(모래톱, 추정)"), "seungbang": (37.4790, 126.9820, "승방뜰(사당 부근, 추정)"),
  "namtae": (37.4650, 126.9879, "남태령"), "ahyeon": (37.5572, 126.9568, "아현"),
  "yangwha_s": (37.54348, 126.89987, "양화리(남쪽 나루, HGIS 1912)"), "yeomchang": (37.55442, 126.87369, "염창리(HGIS 1912)"),
  "noryang_n": (37.5235, 126.9580, "노들나루 북쪽 기슭(추정)"), "dongjak_n": (37.5130, 126.9790, "동작나루 북쪽 기슭(추정)"),
}
def ll(k):
    if k in PT: return (PT[k]["lat"], PT[k]["lng"])
    return W[k][:2]

# ---------- 대로 ----------
# legs: 경유지 id 목록. "~"로 시작하면 앞 지점에서 그 지점까지 나룻배(곧은 점선)
ROADS = [
  dict(id="r1", name="의주대로", no="제1로", legs=["donui", "yeongeun", "muak", "hongje", "nokbeon", "gupabal"], conf="중간",
       src="돈의문–영은문·모화관–무악재–녹번현(서울신문 2018.12.20, 『택리지』 인용), 홍제원 「在追慕峴北」(『동국여지비고』)"),
  dict(id="r2", name="경흥대로", no="제2로", legs=["hyehwa", "miari", "suyu", "nuwon"], conf="중간",
       src="혜화문–미아리고개–누원(다락원)(서울신문 2018.6.28), 동소문–적유현–수유현–양주(서울신문 2019.11.7)"),
  dict(id="r3", name="평해대로", no="제3로", legs=["heungin", "boje", "jungnang", "mangu"], conf="낮음",
       src="망우리고개가 평해길(관동대로)의 들머리(경기도 웹진 「경기옛길」). 흥인지문–보제원–중량포 구간은 추정"),
  dict(id="r4", name="영남대로(동래대로)", no="제4로", legs=["gwanghui", "jangchung", "yaksu", "beoti", "hangang", "~sapyeong", "sinsa", "yangjae", "wonji", "dallae"], conf="중간", lab=5,
       src="광희문–장충동–약수동–버티고개–한강진–사평나루–양재역–원지동–달래내고개(서울신문 2006.10.23, 「대동여지도」 경조오부도 바탕, 나각순 자문)"),
  dict(id="r4b", name="영남대로 서빙고 갈래", no="제4로", legs=["sungnye", "itaewon", "noksapyeong", "seobinggo", "~jamwon", "yangjae"], conf="낮음",
       src="남대문–용산–녹사평–서빙고–잠원나루–양재(서울신문 2006.10.23). 이태원(院) 경유는 추정"),
  dict(id="r4c", name="광주로(송파)", no="제4로 갈래", legs=["gwanghui", "wangsimni", "jeongwan", "ttukseom", "~songpa"], conf="중간",
       src="광희문–왕십리–살곶이다리–뚝섬나루–송파나루(서울신문 2006.10.23 「또다른 영남대로」)"),
  dict(id="r4d", name="광주로(광나루)", no="제4로 갈래", legs=["wangsimni", "hanyang", "neungdong", "gwangnaru"], conf="중간",
       src="왕십리–한양대–능동–광나루(서울신문 2006.10.23)"),
  dict(id="r5", name="삼남대로(제주대로)", no="제5로", legs=["sungnye", "baedari", "cheongpa", "dolmoru", "ichon", "dongjak_n", "~dongjak", "seungbang", "namtae"], conf="중간", lab=5,
       src="칠패–도저골–청파 배다리–돌모루–모래톱–동작이–승방뜰–남태령(『대동지지』 정리고 경로를 다룬 글에 인용된 노랫말, 공유마당 「청파 배다리」)"),
  dict(id="r6", name="강화대로", no="제6로", legs=["soui", "ahyeon", "yanghwa", "~yangwha_s", "yeomchang"], conf="낮음",
       src="양화나루는 서울에서 인천·강화로 가는 길목(서울시 한강 누리집). 소의문–아현–양화나루 구간은 추정"),
]

R = np.load(f"{RAW}/osm/seoul/roads.npz")
lon, lat, u, v, d, c, cost, cls = R["lon"], R["lat"], R["u"], R["v"], R["d"], R["c"], R["cost"], [str(x) for x in R["cls"]]
ok = np.array([cls[k] not in ("motorway", "motorway_link") for k in c])   # 도시고속도로는 쓰지 않는다
w = (d * cost[c])[ok]
N = len(lon)
G = csr_matrix((np.concatenate([w, w]), (np.concatenate([u[ok], v[ok]]), np.concatenate([v[ok], u[ok]]))), shape=(N, N))
XY = np.c_[lon * 88.4, lat * 111.0]
major = np.zeros(N, bool); mm = ok & (c <= cls.index("tertiary_link"))   # 큰길에만 붙인다
major[u[mm]] = True; major[v[mm]] = True
mi = np.where(major)[0]; TM = cKDTree(XY[mi])
def snap(la, lo):
    dm, im = TM.query((lo * 88.4, la * 111.0)); return int(mi[im]), dm
def route(a, b, ea=True, eb=True):
    (sa, da), (sb, db) = snap(*a), snap(*b)
    dist, pred = dijkstra(G, indices=sa, return_predecessors=True, limit=40)
    if not np.isfinite(dist[sb]): return [[a[1], a[0]], [b[1], b[0]]], None
    seq = [sb]
    while seq[-1] != sa: seq.append(pred[seq[-1]])
    seq = seq[::-1]
    straight = math.hypot((a[1] - b[1]) * 88.4, (a[0] - b[0]) * 111.0)
    pts = [[float(lon[i]), float(lat[i])] for i in seq]
    if ea: pts = [[a[1], a[0]]] + pts      # 점으로 그리는 곳(역·원·나루·문)만 선을 점까지 잇는다
    if eb: pts = pts + [[b[1], b[0]]]
    return pts, dist[sb] / max(straight, 0.05)

def simplify(pts, tol=0.00004):
    from shapely.geometry import LineString
    ls = LineString(pts).simplify(tol, preserve_topology=False)
    return [[round(x, 5), round(y, 5)] for x, y in ls.coords]

out_roads = []
for r in ROADS:
    segs, cur, detours = [], None, []
    for k, step in enumerate(r["legs"]):
        ferry = step.startswith("~"); key = step.lstrip("~")
        if k == 0: cur = key; continue
        a, b = ll(cur), ll(key)
        if ferry:
            segs.append({"ferry": True, "p": [[round(a[1], 5), round(a[0], 5)], [round(b[1], 5), round(b[0], 5)]]})
        else:
            pts, ratio = route(a, b, cur in PT, key in PT)
            detours.append(round(ratio, 2) if ratio else None)
            segs.append({"p": simplify(pts)})
        cur = key
    via = [PT[s.lstrip("~")]["name"] if s.lstrip("~") in PT else W[s.lstrip("~")][2] for s in r["legs"]]
    o = {"id": r["id"], "name": r["name"], "no": r["no"], "via": via, "segs": segs, "conf": r["conf"], "src": r["src"]}
    if "lab" in r: o["lab"] = r["lab"]   # 이름을 쓸 구간(나룻배를 뺀 몇 번째 구간). 없으면 6할쯤
    out_roads.append(o)
    print(r["name"], "detour ratios", detours, file=sys.stderr)

out = {"points": [{k: p[k] for k in ("id", "name", "hanja", "kind", "lng", "lat", "pos", "src", "conf") if k in p} for p in P],
       "roads": out_roads,
       "note": "조선 후기 역·원·나루와 6대로(시안). 점은 표석 자리나 1912–1914년 같은 이름 동리 자리, 대로는 지금 도로를 따라 그린 근사선"}
json.dump(out, open(f"{DATA}/joseon.json", "w"), ensure_ascii=False, separators=(",", ":"))
print("points", len(P), "roads", len(out_roads), "bytes", len(json.dumps(out, ensure_ascii=False, separators=(",", ":"))), file=sys.stderr)
