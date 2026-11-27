"""연대별 물길(시안): 한강이 크게 바뀐 네 곳(잠실·저자도·여의도와 밤섬·난지도)의 옛 물길을 옛 지형도에서 골라 data/water_zones.json으로.

python3 src/water_zones.py <slm_water_bundle.json 또는 구역 이미지 폴더>   (기본: ~/work/wz — meta.json과 img/*.png)
  묶음 파일은 water_tiles.js의 WT.bundle()이 내려받게 하는 것(구역 16장을 PNG data URL로 담은 JSON)

원자료: 국토지리정보원 국토정보맵 「역사지도 → 종이지도」(map.ngii.go.kr)의 지형도 타일.
- 1910–30 판(PC050K_1945, 1:50,000. 경성 도엽 1919 인쇄, 뚝도 도엽 1926 인쇄 — 공공데이터포털 15067696 메타데이터)
- 1970·1980·1990년대 판(PT025K_1970·1980·1990, 1:25,000)
구역 이미지는 src/water_tiles.js(WT.cropUrl)로 이지의 크롬에서 4 m 격자(EPSG:5179)로 만든다. 타일이 실제 자리와 어긋나 있어
1914년 이전에 놓여 지금도 쓰는 철도선(경부·경인·경원)의 표본점이 지형도의 검은 선에 가장 많이 겹치는 만큼 옮겨 읽었다
(WT.offset, 20 m 간격으로 찾은 뒤 5 m 간격으로 다시). 잰 값은 OFFSETS에 적어 둔다.

물 고르기(색): 1910–30 판은 물을 칠로 나타낸다(경성 도엽은 올리브·녹청, 뚝도 도엽은 청록). 1970–90년대 판은 옅은 파랑.
글자·선·모래 점은 중앙값 거르기와 닫기(15칸 = 60 m)로 메우고, 0.5 ha보다 작은 조각은 버린다.
바뀐 해(PERIODS의 from)는 시안이다. 출처 확인 전인 해는 note에 「추정」으로 적는다.
"""
import json, os, sys
sys.dont_write_bytecode = True
import numpy as np, cv2
from PIL import Image
import shapely
from shapely.geometry import Polygon, box, mapping
from shapely.ops import unary_union
from pyproj import Transformer
from paths import DATA

SRC_DIR = sys.argv[1] if len(sys.argv) > 1 else os.path.expanduser("~/work/wz")
OUT = os.path.join(DATA, "water_zones.json")

ED = {
    "PC050K_1945": "1910–30 판 지형도(1:5만, 1919·1926 인쇄)",
    "PT025K_1970": "1970년대 판 지형도(1:2만5천)",
    "PT025K_1980": "1980년대 판 지형도(1:2만5천)",
    "PT025K_1990": "1990년대 판 지형도(1:2만5천)",
}
# 타일 → 실제 자리로 옮겨 읽은 값(m, 동쪽·북쪽 +). 경성(서)·뚝도(동) 도엽은 따로 쟀다
OFFSETS = {"PC050K_1945": {"경성 도엽": [-80, -330], "뚝도 도엽": [-80, -315]},
           "PT025K_1970": [160, -335], "PT025K_1980": [190, -310], "PT025K_1990": [185, -320]}
# 1910–30 판 도엽 범위(경위도). 구역이 도엽 밖으로 나가면 그 판의 물길은 도엽 안만 쓴다
SHEET = {"경성 도엽": (126.75, 37.5, 127.0, 37.6667), "뚝도 도엽": (127.0, 37.5, 127.25, 37.6667)}

# 구역: 이름, 경위도 상자(서, 남, 동, 북). 상자 안에서는 해에 따라 그때 지형도의 물길을 그리고, 2000년부터는 지금 물길(OSM)
ZONES = [
    ("jamsil", "잠실", (127.055, 37.500, 127.125, 37.545)),
    ("jeoja", "저자도·압구정", (127.010, 37.525, 127.050, 37.545)),
    ("yeouido", "여의도·밤섬", (126.895, 37.510, 126.955, 37.545)),
    ("nanji", "난지도", (126.860, 37.555, 126.905, 37.585)),
]
# (구역, 처음 해, 판, 메모). 다음 줄의 처음 해 앞까지 쓴다. 마지막 판은 END 앞까지(구역마다 다를 수 있음)
# 1980·1990년대 판은 잠실·저자도·난지도에서 지금 물길과 거의 같아(구역 가장자리에 이음매만 생김) 여의도(밤섬이 다시 자람)에만 쓴다
ENDS = {"jamsil": 1980, "jeoja": 1980, "nanji": 1978, "yeouido": 2000}   # 이 해부터 지금 물길(OSM)
PERIODS = {
    "jamsil": [(None, "PC050K_1945", "1971년 공유수면 매립 착공 전(추정). 1925년 을축년 대홍수 뒤 물길이 바뀌었을 수 있으나 1930–1970년 사이 지형도는 아직 안 봄"),
               (1971, "PT025K_1970", "1971년 매립 착공(추정)부터. 이 판은 매립이 끝난 뒤 모습")],
    "jeoja": [(None, "PC050K_1945", "1970년 무렵 저자도 모래 채취 전(추정)"),
              (1970, "PT025K_1970", "압구정 매립 뒤, 저자도가 모래톱으로 남은 모습")],
    "yeouido": [(None, "PC050K_1945", "1968년 윤중제·밤섬 폭파 전(추정)"),
                (1968, "PT025K_1970", "1968년 윤중제(추정)부터. 둘레에 넓은 모래톱"),
                (1980, "PT025K_1980", ""), (1990, "PT025K_1990", "밤섬이 다시 자라난 모습")],
    "nanji": [(None, "PC050K_1945", ""),
              (1970, "PT025K_1970", "쓰레기 매립 전, 샛강이 둘러싼 섬")],
}
# 그 해 사건 카드(연도 판 아래)와 연표. (해, 날짜, 글, 확인 정도, 근거). 근거는 data에만 두고 카드에는 안 보인다
EVENTS = [
    (1968, "1968.02.10", "한강 밤섬 폭파(여의도 둘레 둑에 쓸 돌을 얻으려고)", None,
     "한강사업본부 누리집 밤섬 소개, 영등포구 누리집, 서울신문 1993-09-05(검색 결과·변환된 페이지)"),
    (1968, "1968.06.01", "여의도 윤중제(둘레 둑) 준공", None, "국가기록원 기록으로 보는 연표 「여의도 윤중제 준공」(원문 확인)"),
    (1970, "1970년대 초", "저자도의 흙·모래를 압구정 공유수면 매립에 쓰면서 섬이 사라짐", "해 추정",
     "서울신문 2013-01-02(성동구 저자도 안내판 기사, 「1970년대 … 공유수면 매립용으로 사용」)"),
    (1971, "1971.04.16", "송파강 물막이로 잠실섬이 뭍과 이어짐. 남은 송파강이 지금의 석촌호수", "날짜는 사진 설명으로만 확인",
     "서울역사아카이브 사진 설명(한국경제 2026-07-29 기사로 봄), 한국민족문화대백과 「석촌호수」(1971년 송파강을 메움)"),
    (1971, "1971.06", "잠실 공유수면 매립 공사 공식 착공(건설부 고시)", None, "국가기록원 「88서울올림픽 — 잠실 올림픽타운」(원문 확인)"),
    (1978, "1978.03", "난지도 쓰레기 매립 시작", None, "서울시 「난지도 그 향기를 되찾다」(검색 결과로 봄), 서울시 미디어허브(1978–1993)"),
    (1978, "1978.06", "잠실 공유수면 매립 끝남", "신문 기사로만 확인", "서울신문 2026-04-03"),
    (1993, "1993", "난지도 쓰레기 매립 끝남(15년 동안 약 9,200만 톤)", None, "서울시 미디어허브 「난지도 쓰레기가 우리에게 남긴 것」"),
    (1999, "1999.08.10", "밤섬 생태·경관보전지역 지정(폭파 뒤 흙이 쌓여 다시 자람)", None, "한강사업본부 누리집 밤섬 연혁(검색 결과로 봄)"),
]
END = 2000
MIN_HA = 0.5

fw = Transformer.from_crs(4326, 5179, always_xy=True).transform
bw = Transformer.from_crs(5179, 4326, always_xy=True).transform


def water_mask(a, ed, west):
    a = a.astype(np.int16)
    r, g, b = a[..., 0], a[..., 1], a[..., 2]
    if ed.startswith("PC050K"):
        if west:   # 경성 도엽: 종이는 누런빛(색상 약 40°), 물은 올리브·녹청(48° 이상)
            hsv = cv2.cvtColor(a.astype(np.uint8), cv2.COLOR_RGB2HSV_FULL).astype(np.int16)
            m = (hsv[..., 0] >= 34) & (hsv[..., 0] <= 185) & (hsv[..., 1] >= 25) & (hsv[..., 2] >= 80) & (hsv[..., 2] <= 238)   # 아주 밝은 누런 종이(색상 34°)는 뺌
        else:      # 뚝도 도엽: 종이가 더 노래서 청록만
            m = ((g - r) >= 12) & ((b - r) >= -12) & (np.maximum(np.maximum(r, g), b) > 70)
    else:
        m = ((b - r) >= 28) & (b >= 160) & ((b - g) >= 8)
    m = cv2.medianBlur(m.astype(np.uint8) * 255, 5)
    k = lambda n: cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (n, n))
    m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, k(15))
    m = cv2.morphologyEx(m, cv2.MORPH_OPEN, k(5))
    return m


def vectorize(m, it):
    """마스크 → EPSG:5179 다각형(구멍 포함)"""
    x0, y1, s = it["x0"], it["y1"], it["m"]
    cs, hier = cv2.findContours(m, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_SIMPLE)
    if hier is None: return Polygon()
    hier = hier[0]; polys = []
    xy = lambda c: [(x0 + (p[0][0] + 0.5) * s, y1 - (p[0][1] + 0.5) * s) for p in c]
    for i, c in enumerate(cs):
        if hier[i][3] != -1 or len(c) < 3: continue
        holes = []; j = hier[i][2]
        while j != -1:
            if len(cs[j]) >= 3 and cv2.contourArea(cs[j]) * s * s >= 3000: holes.append(xy(cs[j]))
            j = hier[j][0]
        p = Polygon(xy(c), holes).buffer(0)
        if p.area >= MIN_HA * 1e4: polys.append(p)
    return unary_union(polys)


def gj(g, nd=5):
    g = shapely.transform(g, lambda c: np.column_stack(bw(c[:, 0], c[:, 1])))
    m = mapping(g)
    def rnd(c):
        if c and isinstance(c[0], (int, float)): return [round(c[0], nd), round(c[1], nd)]
        return [rnd(x) for x in c]
    return {"type": m["type"], "coordinates": rnd(m["coordinates"])}


def to5179(b):
    xs, ys = fw([b[0], b[2], b[2], b[0]], [b[1], b[1], b[3], b[3]])
    return Polygon(list(zip(xs, ys)))


def load_items():
    """(구역, 판) → 메타와 RGB 배열. 묶음 JSON이면 그 안의 PNG를 바로 푼다"""
    import base64, io
    if SRC_DIR.endswith(".json"):
        meta = json.load(open(SRC_DIR))
        for it in meta["items"]:
            it["rgb"] = np.asarray(Image.open(io.BytesIO(base64.b64decode(it.pop("png").split(",", 1)[1]))).convert("RGB"))
    else:
        meta = json.load(open(os.path.join(SRC_DIR, "meta.json")))
        for it in meta["items"]:
            it["rgb"] = np.asarray(Image.open(os.path.join(SRC_DIR, "img", it["file"])).convert("RGB"))
    return meta, {(it["name"], it["ed"]): it for it in meta["items"]}


def main():
    meta, items = load_items()
    zones = []
    for zid, zname, zb in ZONES:
        Z = to5179(zb); periods = []
        P = PERIODS[zid]
        for k, (frm, ed, note) in enumerate(P):
            to = P[k + 1][0] if k + 1 < len(P) else ENDS.get(zid, END)
            it = items[(zid, ed)]
            a = it["rgb"]
            west = zb[2] <= 127.0
            g = vectorize(water_mask(a, ed, west), it)
            if ed == "PC050K_1945":
                sheet = "경성 도엽" if west else "뚝도 도엽"
                g = g.intersection(to5179(SHEET[sheet]))
            g = g.intersection(Z).simplify(5)
            periods.append({"from": frm, "to": to, "ed": ed, "label": ED[ed], "note": note,
                            "dxdy": [it["dx"], it["dy"]], "old": gj(g)})
            print(f"{zname} {frm}–{to} {ed}: 물 {g.area / 1e4:.0f} ha", file=sys.stderr)
        zones.append({"id": zid, "name": zname, "box": list(zb), "periods": periods})
    evs = [dict({"year": y, "date": d, "kind": "water", "text": t, "sort": 4, "color": "var(--river-cov)", "src": src}, **({"conf": c} if c else {}))
           for y, d, t, c, src in EVENTS]
    out = {"zones": zones, "offsets": OFFSETS, "events": evs,
           "src": "국토지리정보원 국토정보맵 역사지도 종이지도(map.ngii.go.kr) — 1910–30 판(1:5만)·1970·1980·1990년대 판(1:2만5천). "
                  "공공데이터포털 15062206 「국토지리정보원_종이지도」 공공누리 제1유형(출처표시)",
           "made": meta.get("made")}
    s = json.dumps(out, ensure_ascii=False, separators=(",", ":"))
    open(OUT, "w").write(s)
    print("wrote", OUT, len(s.encode()), "bytes", file=sys.stderr)


if __name__ == "__main__":
    main()
