"""연대별 물길(시안): 지금 물길(data/water.json)은 그대로 두고, 해에 따라 달라지는 곳만 data/water_hist.json에 따로 둔다.

python3 src/water_hist.py   (읽는 것: data/water.json. 원자료 없이 돈다)

지금 들어 있는 것: 청계천 복개 구간.
- water.json의 청계천 선(OSM, 청계광장 → 중랑천 합류, 8.25km)을 다리 자리에서 끊어 구간마다 덮인 해(c)와 다시 열린 해(o)를 붙인다.
  지도는 c <= 해 < o 인 해에 그 구간을 「덮임」으로 그린다. c가 없는 구간(신답철교 아래)은 늘 열려 있다.
- 다리 자리는 OSM 다리 길(bridge)의 가운데 점(Overpass, 2026-11-27, 이지의 크롬)을 청계천 선에 내린 것이다.
  광교 상류 138.5m 지점은 광교(남대문로) 자리에서 선을 따라 138.5m 거슬러 올라간 점이다.
- 해는 끝난 해(준공)로 잡는다. 공사 중인 해는 덮이지 않은 것으로 그린다(시안, 이지와 정할 일).
  복원은 2003-07-01 착공, 2005-10-01 완료라 2003–2004년은 덮인 채(공사 중), 2005년부터 열림으로 그린다.
- 수면 면: water.json의 수면(area)에도 복원된 청계천 물길이 면으로 들어 있다(OSM natural=water). 청계천 선에서 45m 안(복개 구간만,
  구간 끝은 직각으로 자름)을 「복개 띠」로 잡아, 지도는 지금 수면을 그릴 때 이 띠를 잘라 내고(clipPath), 띠 안의 수면 조각(a)을 해에 따라 따로 그린다.
- 근거 등급: A 원문 직접(청계천박물관 연표), B 공공기관 누리집을 변환된 페이지로 봄(서울시설공단), C 자료끼리 어긋남.
"""
import json, math, os, sys
sys.dont_write_bytecode = True
import numpy as np, shapely
from shapely.geometry import shape, LineString, Point, mapping
from shapely.ops import substring, unary_union
from pyproj import Transformer
from paths import DATA

WATER = os.path.join(DATA, "water.json")
OUT = os.path.join(DATA, "water_hist.json")

# OSM 다리 가운데 점(경도, 위도). 이름은 지금 다리 이름
BR = {
    "광교": (126.98277, 37.56888),        # 남대문로. 옛 광통교 자리(복원 광통교는 상류 155m로 옮김)
    "오간수교": (127.00976, 37.56979),    # 장충단로, 청계6가·동대문운동장 앞
    "황학교": (127.02335, 37.57173),      # 난계로, 청계8가(서울시설공단 청계천 다리 안내)
    "신답철교": (127.04144, 37.57182),    # 복원 구간 끝(태평로 시점에서 5.84km)
}
SRC = {
    "museum": "청계천박물관 「청계천 연표」(museum.seoul.go.kr/cgcm, 2026-11-27 원문 확인)",
    "sisul": "서울시설공단 청계천 누리집 「1950년대 이후」·「일제강점기 청계천」·「사업의 개요」(변환된 페이지로 확인)",
}
# (끝 지점, 덮인 해, 다시 열린 해, 구간, 근거, 등급)
PLAN = [
    ("광교-138.5", 1942, 2005, "태평로–광교 상류",
     "1937–1942 복개(청계천박물관 연표 「태평로에서 광교까지 복개함(~1942)」, 서울시설공단은 「1937년 태평로에서 무교동 구간」)", "C"),
    ("광교", 1955, 2005, "광교 상류 138.5m",
     "1955 복개(청계천박물관 연표 「광교 상류 138.5m 복개」, 서울시설공단은 「광통교 상류 약 136m」)", "A"),
    ("오간수교", 1961, 2005, "광교–오간수교(청계6가)",
     "1958-05-25 착공, 1961-12-05 복개도로 준공(청계천박물관 연표 「광통교~동대문 오간수문」)", "A"),
    ("황학교", 1967, 2005, "오간수교–황학교(청계6가–8가, 신설동)",
     "1965–1967 복개(서울시설공단 「청계 6가에서부터 청계8가 신설동까지」). 서울신문(2005-07-18)은 1960–1969년이라 적음", "C"),
    ("신답철교", 1977, 2005, "황학교–신답철교(신설동–마장동)",
     "1970-11-20 착공, 1977-12-31 완공(청계천박물관 연표)", "A"),
    ("끝", None, None, "신답철교–중랑천", "복개 구간 밖(늘 열림)", ""),
]
# 그 해 사건 카드(연도 판 아래)와 연표에 넣을 청계천 사건. 색은 물길 색(--river-cov)
EV_COLOR = "var(--river-cov)"
EVENTS = [
    (1937, "1937", "청계천 태평로–광교 복개 시작(1942년까지)", "구간은 자료마다 다름"),
    (1955, "1955", "청계천 광교 상류 138.5m 복개", None),
    (1958, "1958.05.25", "청계천 복개 공사 착공(광통교–오간수문)", None),
    (1961, "1961.12.05", "청계천 복개도로 준공(광통교–동대문 오간수문)", None),
    (1965, "1965", "청계천 청계6가–8가(신설동) 복개 시작(1967년까지)", "연도는 자료마다 다름"),
    (1970, "1970.11.20", "청계천 신설동–신답철교 복개 착공", None),
    (1977, "1977.12.31", "청계천 복개 완공(신설동–마장동 신답철교)", None),
    (2003, "2003.07.01", "청계천 복원 공사 착공", None),
    (2005, "2005.10.01", "청계천 복원 완료(태평로–신답철교 5.84km)", None),
]
BAND = 45     # 복개 띠 반폭(m)
fw = Transformer.from_crs(4326, 5179, always_xy=True).transform
bw = Transformer.from_crs(5179, 4326, always_xy=True).transform
to_m = lambda g: shapely.transform(g, lambda c: np.column_stack(fw(c[:, 0], c[:, 1])))
to_ll = lambda g: shapely.transform(g, lambda c: np.column_stack(bw(c[:, 0], c[:, 1])))


def gj(g):
    """경위도 GeoJSON(소수 다섯째 자리)"""
    m = mapping(to_ll(g))
    def rnd(c):
        if c and isinstance(c[0], (int, float)): return [round(c[0], 5), round(c[1], 5)]
        return [rnd(x) for x in c]
    return {"type": m["type"], "coordinates": rnd(m["coordinates"])}


REOPEN = "2003-07-01 복원 공사 착공, 2005-10-01 복원 완료(청계천박물관 연표). 사업 범위 태평로 시점–신답철교 5.84km(서울시설공단)"


def m_per_deg(lat):
    return 111320 * math.cos(math.radians(lat)), 110540


def cum(line):
    out = [0.0]
    for a, b in zip(line, line[1:]):
        kx, ky = m_per_deg((a[1] + b[1]) / 2)
        out.append(out[-1] + math.hypot((b[0] - a[0]) * kx, (b[1] - a[1]) * ky))
    return out


def locate(line, acc, p):
    """점 p를 선에 내린 자리의 선 따라 거리(m)와 떨어진 거리"""
    kx, ky = m_per_deg(p[1]); best = None
    for i in range(1, len(line)):
        a, b = line[i - 1], line[i]
        ax, ay, bx, by, px, py = a[0] * kx, a[1] * ky, b[0] * kx, b[1] * ky, p[0] * kx, p[1] * ky
        dx, dy = bx - ax, by - ay
        t = max(0, min(1, ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy)))
        d = math.hypot(px - ax - t * dx, py - ay - t * dy)
        if best is None or d < best[0]: best = (d, acc[i - 1] + t * math.hypot(dx, dy))
    return best[1], best[0]


def cut(line, acc, s0, s1):
    """선 따라 s0–s1 m 구간의 좌표"""
    def at(s):
        for i in range(1, len(line)):
            if acc[i] >= s:
                t = (s - acc[i - 1]) / ((acc[i] - acc[i - 1]) or 1)
                a, b = line[i - 1], line[i]
                return [round(a[0] + t * (b[0] - a[0]), 5), round(a[1] + t * (b[1] - a[1]), 5)]
        return list(line[-1])
    pts = [at(s0)] + [list(line[i]) for i in range(len(line)) if s0 < acc[i] < s1] + [at(s1)]
    return pts


ZONES = os.path.join(DATA, "water_zones.json")


def zones_from(area, bands):
    """한강 네 곳(src/water_zones.py가 만든 data/water_zones.json): 구역 안 지금 수면(now)과, 판마다 「지금은 물인데 그때는 물이 아니던 곳」(gone, 빗금).
    구역 자리를 bands에 더해 지금 수면에서 잘라 낸다(지도는 해에 맞는 판의 물길이나, 2000년부터는 now를 그린다)"""
    if not os.path.exists(ZONES): return None
    zj = json.load(open(ZONES)); out = {"src": zj["src"], "list": [], "events": [{k: v for k, v in e.items() if k != "src"} for e in zj.get("events", [])]}
    for z in zj["zones"]:
        b = z["box"]; Z = to_m(shapely.box(*b))
        now = area.intersection(Z)
        ps = []
        for p in z["periods"]:
            old = to_m(shape(p["old"]))
            gone = now.difference(old.buffer(25)).buffer(-12).buffer(12)       # 자리 어긋남(수십 m)으로 생기는 기슭 띠는 버린다
            gone = unary_union([g for g in getattr(gone, "geoms", [gone]) if g.area >= 1e4]).simplify(5)
            q = {k: p[k] for k in ("from", "to", "ed", "label", "note")}
            q.update({"old": p["old"], "gone": gj(gone) if not gone.is_empty else None})
            ps.append(q)
            print(f"  {z['name']} {p['from']}–{p['to']}: 빗금 {gone.area / 1e4:.0f} ha", file=sys.stderr)
        out["list"].append({"id": z["id"], "name": z["name"], "now": gj(now.simplify(3)), "periods": ps})
        bands.append(Z)
    return out


def main():
    w = json.load(open(WATER))
    ln = [l for l in w["lines"] if l["name"] == "청계천"]
    assert len(ln) == 1 and ln[0]["geom"]["type"] == "LineString", "water.json의 청계천 선이 하나의 LineString이어야 함"
    line = ln[0]["geom"]["coordinates"]; acc = cum(line)
    pos = {}
    for k, p in BR.items():
        s, off = locate(line, acc, p); pos[k] = s
        print(f"{k}: 선 따라 {s:.0f}m (선에서 {off:.0f}m)", file=sys.stderr)
    pos["광교-138.5"] = pos["광교"] - 138.5; pos["끝"] = acc[-1]
    area = to_m(shape(w["area"])); Lm = to_m(LineString(line)); f = Lm.length / acc[-1]
    segs, bands, s0 = [], [], 0.0
    for end, c, o, what, why, conf in PLAN:
        s1 = pos[end]
        seg = {"g": cut(line, acc, s0, s1), "k": what, "m": round(s1 - s0)}
        if c:
            sub = substring(Lm, s0 * f, s1 * f)
            band = sub.buffer(BAND, cap_style="flat")
            if s0 == 0: band = band.union(Point(sub.coords[0]).buffer(BAND))   # 청계광장 쪽 끝은 둥글게(수면이 선 끝보다 조금 서쪽까지 있음)
            piece = area.intersection(band).simplify(2)
            seg.update({"c": c, "o": o, "d": why, "q": conf, "a": gj(piece)}); bands.append(band)
            print(f"  {what}: {s0:.0f}–{s1:.0f}m ({s1 - s0:.0f}m) 덮임 {c}–{o}, 수면 {piece.area / 1e4:.2f}ha", file=sys.stderr)
        segs.append(seg)
        s0 = s1
    zones = zones_from(area, bands)
    hole = unary_union(bands).buffer(0.5).simplify(2)
    out = {"cgc": {"name": "청계천", "segs": segs, "reopen": REOPEN, "src": list(SRC.values()),
                   "note": "선은 OSM 지금 물길(복원된 청계천)이다. 복개 전 물길과 자리가 조금 다를 수 있다"},
           "replaces": ["청계천"], "hole": gj(hole), "zones": zones,
           "events": (zones.pop("events") if zones else []) + [dict({"year": y, "date": d, "kind": "water", "text": t, "sort": 4, "color": EV_COLOR}, **({"conf": c} if c else {}))
                      for y, d, t, c in EVENTS]}
    s = json.dumps(out, ensure_ascii=False, separators=(",", ":"))
    open(OUT, "w").write(s)
    print("wrote", OUT, len(s.encode()), "bytes", file=sys.stderr)


if __name__ == "__main__":
    main()
