"""1914년 6월 「경성부시가강계도」(京城府市街疆界圖) 원본 이미지를 지도 위에 깔 수 있게 맞춘다(시안).
python3 src/kanggye1914.py → img/kanggye1914.webp, data/oldmap.json

- 원자료: 서울역사아카이브 소장유물 「경성부시가강계도」(유물번호 서울역사001349, 6671×5000 이미지).
  서울역사박물관이 창작한 저작물, 공공누리 제1유형(출처표시). 원본은 RAW/oldmaps/에 둔다.
- 맞추는 법: 지금도 같은 자리에 있는 것(성문·궁궐 문·성당·산꼭대기·한강철교 북단)과 용산의 한강통·경부선을 기준점으로
  얇은 판 스플라인(thin plate spline)으로 늘이고 줄인다. 기준점 사이는 매끄럽게 이어지지만, 기준점이 없는
  변두리(마포·청량리 쪽, 지도 가장자리)는 수십~수백 m 어긋날 수 있다. 가장자리가 마구 휘지 않게 테두리에는
  아핀 변환으로 얻은 가짜 기준점을 둔다.
- 지도 밖 여백, 제목, 좌우 색인, 창신·숭인동 덧붙인 그림, 범례 칸은 투명하게 지운다.
- 결과는 웹 메르카토르(EPSG:3857) 격자로 다시 그린 WebP(투명)이다. d3.geoMercator와 같은 투영이라
  네 모서리 경위도만 알면 지도에 사각형 그대로 얹을 수 있다.
"""
import json, math, os, sys
sys.dont_write_bytecode = True
import numpy as np
from PIL import Image, ImageDraw
from pyproj import Transformer
from scipy.interpolate import RBFInterpolator
from scipy.ndimage import map_coordinates
from paths import DATA, RAW

Image.MAX_IMAGE_PIXELS = None
SRC = os.path.join(RAW, "oldmaps", "경성부시가강계도_1914_서울역사001349.jpg")
OUT_IMG = os.path.join(os.path.dirname(DATA), "img", "kanggye1914.webp")
RES = 3.0   # 출력 해상도(m/px). 원본은 약 2.7m/px

# 기준점: 원본 이미지 픽셀(x, y) ↔ 지금 경위도. 위치는 OSM(성문·산꼭대기·철교)과 지금 자리(복원·이전 여부는 note)
GCP = [
  ("숭례문", 3249, 2361, 126.97534, 37.55993, ""),
  ("남산 정상", 3667, 2739, 126.98796, 37.55221, ""),
  ("한강철교 북단", 2440, 3872, 126.9564, 37.5237, ""),
  ("독립문", 2770, 1773, 126.9605, 37.5719, "1979년 옮기기 전 자리로 추정"),
  ("광화문", 3348, 1726, 126.97689, 37.57594, "2010년 원래 자리에 복원"),
  ("명동성당", 3633, 2251, 126.98726, 37.5633, "지도의 (C) 표시"),
  ("흥인지문", 4385, 2000, 127.00979, 37.57115, "지도 오른쪽 끝이라 ±20px"),
  ("창의문", 3090, 1053, 126.96652, 37.59262, ""),
  ("인왕산", 2768, 1315, 126.95788, 37.585, "성벽 꺾이는 곳"),
  ("혜화문", 4267, 1325, 127.00387, 37.58795, "1994년 조금 북쪽에 다시 지음"),
  ("광희문", 4376, 2276, 127.01012, 37.56438, "지도의 (W) 표시, 왕십리로 가는 길이 성벽을 지나는 곳"),
  ("한강통 꺾이는 곳(삼각지)", 3153, 3300, 126.9741, 37.5358, "지금 한강대로가 남북에서 남서로 꺾이는 곳"),
  ("한강통(한강대로) 선", 3150, 3125, 126.97291, 37.54181, "선 위의 점: 지금 한강대로에서 가장 가까운 곳"),
  ("경부선 선로", 3067, 3125, 126.97137, 37.54191, "선 위의 점: 지금 경부선에서 가장 가까운 곳"),
]
FRAME = (2008, 625, 4682, 4412)          # 지도 안쪽 테두리
HOLES = [                                # 지도가 아닌 칸(제목·색인·덧그림·범례)
  (2700, 625, 3960, 862), (3840, 895, 4440, 975), (2280, 895, 2720, 975),      # 제목·발행 정보
  (4440, 1050, 4682, 3090), (4372, 1500, 4440, 1975), (4392, 1975, 4440, 3090), (4530, 3800, 4682, 4412),  # 오른쪽 색인
  (2008, 1540, 2215, 2580), (2215, 1755, 2580, 2215), (2215, 2215, 2565, 2450),  # 왼쪽 색인
  (2008, 3500, 2230, 3640), (2008, 3980, 2080, 4412),                          # 왼쪽 아래 주기
  (4020, 3090, 4530, 3770), (4530, 3090, 4682, 3800),                          # 창신·숭인동 덧그림과 그 옆 색인
  (3790, 3880, 4190, 4260),                                                    # 축척·범례
]

T5186 = Transformer.from_crs(4326, 5186, always_xy=True)
T3857 = Transformer.from_crs(4326, 3857, always_xy=True)
T3857i = Transformer.from_crs(3857, 4326, always_xy=True)
G = np.array([T5186.transform(g[3], g[4]) for g in GCP]); P = np.array([[g[1], g[2]] for g in GCP], float)
# 기준점이 없는 가장자리가 마구 휘지 않도록, 테두리를 따라 '가짜 기준점'을 둔다. 가짜 점의 경위도는 기준점 10곳으로 맞춘
# 아핀(평행이동·회전·축척·기울임) 변환에서 얻는다. 진짜 기준점에서 700px(약 1.9km) 안쪽에는 두지 않는다
_A = np.c_[P, np.ones(len(P))]
_aff = np.linalg.lstsq(_A, G, rcond=None)[0]
_fx0, _fy0, _fx1, _fy1 = FRAME
VIRT = [(x, y) for x in np.linspace(_fx0, _fx1, 6) for y in np.linspace(_fy0, _fy1, 8)
        if min(np.hypot(x - P[:, 0], y - P[:, 1])) > 700]
VP = np.array(VIRT, float); VG = np.c_[VP, np.ones(len(VP))] @ _aff
GG = np.r_[G, VG]; PP = np.r_[P, VP]
geo2px = RBFInterpolator(GG, PP, kernel="thin_plate_spline")
px2geo = RBFInterpolator(PP, GG, kernel="thin_plate_spline")
print("virtual points", len(VP), file=sys.stderr)
T5186i = Transformer.from_crs(5186, 4326, always_xy=True)

# 출력 범위: 테두리를 따라 점을 찍어 경위도로 옮긴 뒤 3857 상자
x0, y0, x1, y1 = FRAME
edge = [(x, y0) for x in np.linspace(x0, x1, 40)] + [(x1, y) for y in np.linspace(y0, y1, 40)] + \
       [(x, y1) for x in np.linspace(x1, x0, 40)] + [(x0, y) for y in np.linspace(y1, y0, 40)]
eg = px2geo(np.array(edge, float))
ell = np.array([T5186i.transform(*p) for p in eg])
em = np.array([T3857.transform(*p) for p in ell])
mx0, my0 = em.min(0); mx1, my1 = em.max(0)
k = 1 / math.cos(math.radians(ell[:, 1].mean()))      # 3857 단위/지상 m
step = RES * k
W = int((mx1 - mx0) / step) + 1; H = int((my1 - my0) / step) + 1
print("output", W, "x", H, file=sys.stderr)

# 출력 격자 → 경위도 → 5186 → 원본 픽셀
xs = mx0 + (np.arange(W) + 0.5) * step; ys = my1 - (np.arange(H) + 0.5) * step
src = np.zeros((H, W, 2), np.float32)
for r in range(0, H, 200):
    yy = ys[r:r + 200]
    MX, MY = np.meshgrid(xs, yy)
    lon, lat = T3857i.transform(MX.ravel(), MY.ravel())
    X, Y = T5186.transform(lon, lat)
    src[r:r + 200] = geo2px(np.c_[X, Y]).reshape(len(yy), W, 2)

im = Image.open(SRC).convert("RGB")
mask = Image.new("L", im.size, 0); md = ImageDraw.Draw(mask)
md.rectangle(FRAME, fill=255)
for h in HOLES: md.rectangle(h, fill=0)
A = np.asarray(im)
# 종이가 찢겨 배경(회색)이 보이는 곳도 지운다: 채도가 거의 없고 잉크보다 밝은 픽셀
_r, _g, _b = (A[..., i].astype(int) for i in range(3))
_gray = (abs(_r - _b) < 14) & (abs(_r - _g) < 10) & (_r > 115) & (_r < 215)
M = np.where(_gray, 0, np.asarray(mask)).astype(np.uint8)
out = np.zeros((H, W, 4), np.uint8)
cx, cy = src[..., 0], src[..., 1]
for ch in range(3):
    out[..., ch] = map_coordinates(A[..., ch], [cy, cx], order=1, mode="constant", cval=0)
out[..., 3] = map_coordinates(M, [cy, cx], order=1, mode="constant", cval=0)
os.makedirs(os.path.dirname(OUT_IMG), exist_ok=True)
Image.fromarray(out, "RGBA").save(OUT_IMG, "WEBP", quality=70, method=6)

# 모서리 경위도(왼쪽 위, 오른쪽 아래)와 기준점 잔차
nw = T3857i.transform(mx0, my1); se = T3857i.transform(mx1, my0)
loo = []
for i in range(len(GCP)):
    m = np.arange(len(GCP)) != i
    f = RBFInterpolator(np.r_[G[m], VG], np.r_[P[m], VP], kernel="thin_plate_spline")
    loo.append(round(float(np.hypot(*(f(G[i:i + 1])[0] - P[i]))) * 2.7))
# ---------- 덧그림(창신동·숭인동) ----------
# 지면이 모자라 오른쪽 아래 칸에 따로 그린 약도. 건물 없이 성벽·큰길·남북 길·산·1914 경계선만 있다.
# 점 3곳(흥인지문, 지봉로가 종로에서 갈라지는 곳, 동망봉)과 선 3개(성벽, 종로·왕산로, 지봉로)에 가장 잘 맞는 아핀 변환을 찾는다
# 약도라 축척이 고르지 않다(남북이 실제보다 1.5–2배 늘어나 그려짐). 아핀으로 맞추면 남북이 눌린 모양이 되는데, 그게 약도의 비뚤어짐이다
INSET = (4036, 3110, 4518, 3760)          # 덧그림 칸 안쪽
INSET_PTS = [("흥인지문", 4088, 3670, 127.00979, 37.57115), ("지봉로 갈림", 4267, 3623, 127.01563, 37.57302), ("동망봉", 4322, 3288, 127.01796, 37.5782)]
INSET_TRACE = {   # 덧그림 위에서 따라 찍은 선(원본 픽셀)
  "wall": [(4074, 3119), (4077, 3197), (4070, 3304), (4063, 3411), (4066, 3519), (4081, 3604), (4089, 3654)],
  "road": [(4091, 3676), (4199, 3644), (4306, 3608), (4377, 3590), (4449, 3570)],
  "jibong": [(4249, 3169), (4241, 3269), (4234, 3376), (4241, 3483), (4256, 3583)],
}
import osmium
from shapely.geometry import LineString as _LS, MultiLineString as _MLS, Point as _Pt
from scipy.optimize import least_squares
_lines = {"wall": [], "road": [], "jibong": []}
class _H(osmium.SimpleHandler):
    def way(self, w):
        t = w.tags; nm = t.get("name", "")
        k = "wall" if (t.get("barrier") == "city_wall" or t.get("historic") == "citywalls" or "한양도성" in nm) else \
            "road" if nm in ("종로", "왕산로") and t.get("highway") else "jibong" if nm == "지봉로" and t.get("highway") else None
        if not k: return
        try: pts = [(n.lon, n.lat) for n in w.nodes]
        except osmium.InvalidLocationError: return
        box = {"wall": (127.0060, 127.0110, 37.5700, 37.5810), "road": (127.0090, 127.0320, 37.5690, 37.5790), "jibong": (127.0, 127.04, 37.56, 37.60)}[k]
        pts = [p for p in pts if box[0] < p[0] < box[1] and box[2] < p[1] < box[3]]
        if len(pts) >= 2: _lines[k].append(np.array([T5186.transform(*p) for p in pts]))
_H().apply_file(os.path.join(RAW, "osm", "seoul", "Seoul.osm.pbf"), locations=True)
_IG = np.array([T5186.transform(p[3], p[4]) for p in INSET_PTS]); _IP = np.array([[p[1], p[2]] for p in INSET_PTS], float); _ig0 = _IG.mean(0)
def _iapply(a, XY): X = (np.atleast_2d(XY) - _ig0) / 1000; return np.c_[X, np.ones(len(X))] @ a.reshape(2, 3).T
def _ires(a):
    r = list((_iapply(a, _IG) - _IP).ravel())
    for k, pts in INSET_TRACE.items():
        mls = _MLS([_LS(_iapply(a, l)) for l in _lines[k]])
        r += [0.5 * mls.distance(_Pt(p)) for p in pts]
    return np.array(r)
_a0 = np.linalg.lstsq(np.c_[(_IG - _ig0) / 1000, np.ones(3)], _IP, rcond=None)[0].T.ravel()
_ia = least_squares(_ires, _a0, loss="soft_l1", f_scale=10).x
_ir = _ires(_ia); inset_pt_err = [round(float(np.hypot(_ir[2 * i], _ir[2 * i + 1])) * 2.7) for i in range(3)]
inset_line_err = round(float(np.median(np.abs(_ir[6:]) * 2)) * 2.7)
# 덧그림 칸 네 모서리를 경위도로(아핀의 역)
_M = _ia.reshape(2, 3); _Minv = np.linalg.inv(_M[:, :2])
def _ipx2geo(px): return ((np.atleast_2d(px) - _M[:, 2]) @ _Minv.T) * 1000 + _ig0
ix0, iy0, ix1, iy1 = INSET
ic = np.array([T5186i.transform(*q) for q in _ipx2geo(np.array([(ix0, iy0), (ix1, iy0), (ix1, iy1), (ix0, iy1)], float))])
icm = np.array([T3857.transform(*q) for q in ic])
jx0, jy0 = icm.min(0); jx1, jy1 = icm.max(0)
IW = int((jx1 - jx0) / step) + 1; IH = int((jy1 - jy0) / step) + 1
ixs = jx0 + (np.arange(IW) + 0.5) * step; iys = jy1 - (np.arange(IH) + 0.5) * step
MX, MY = np.meshgrid(ixs, iys)
lon, lat = T3857i.transform(MX.ravel(), MY.ravel())
X, Y = T5186.transform(lon, lat)
ipx = _iapply(_ia, np.c_[X, Y]).reshape(IH, IW, 2)
imask = Image.new("L", im.size, 0); ImageDraw.Draw(imask).rectangle(INSET, fill=255)
IM = np.where(_gray, 0, np.asarray(imask)).astype(np.uint8)
iout = np.zeros((IH, IW, 4), np.uint8)
for ch in range(3):
    iout[..., ch] = map_coordinates(A[..., ch], [ipx[..., 1], ipx[..., 0]], order=1, mode="constant", cval=0)
iout[..., 3] = map_coordinates(IM, [ipx[..., 1], ipx[..., 0]], order=1, mode="constant", cval=0)
OUT_INSET = OUT_IMG.replace(".webp", "_inset.webp")
Image.fromarray(iout, "RGBA").save(OUT_INSET, "WEBP", quality=70, method=6)
inw = T3857i.transform(jx0, jy1); ise = T3857i.transform(jx1, jy0)
print("inset", IW, "x", IH, os.path.getsize(OUT_INSET), "bytes; point err m", inset_pt_err, "line median m", inset_line_err, file=sys.stderr)

meta = {"id": "kanggye1914", "title": "경성부시가강계도(京城府市街疆界圖)", "date": "1914년 6월 수정판(같은 해 5월 초판을 조선총독부 토지조사국 교열로 고쳐 찍음)",
        "imgs": [{"src": "img/kanggye1914.webp", "nw": [round(nw[0], 6), round(nw[1], 6)], "se": [round(se[0], 6), round(se[1], 6)]},
                 {"src": "img/kanggye1914_inset.webp", "nw": [round(inw[0], 6), round(inw[1], 6)], "se": [round(ise[0], 6), round(ise[1], 6)]}],
        "insetFit": f"창신동·숭인동 덧그림은 약도라 따로 맞춤(흥인지문·지봉로 갈림·동망봉과 성벽·종로·지봉로 선). 점 어긋남 {min(inset_pt_err)}–{max(inset_pt_err)}m, 선 어긋남 중앙값 약 {inset_line_err}m",
        "from": 1914, "to": 1935,
        "src": "서울역사아카이브 소장유물 「경성부시가강계도」(서울역사001349). 서울역사박물관 소장, 공공누리 제1유형",
        "fit": f"기준점 {len(GCP)}곳(성문·궁궐 문·성당·산꼭대기·한강철교 북단·한강통·경부선)으로 맞춤. 기준점 하나를 빼고 맞췄을 때 그 점의 어긋남 {min(loo)}–{max(loo)}m",
        "gcp": [{"name": g[0], "px": g[1], "py": g[2], "lng": g[3], "lat": g[4], "note": g[5]} for g in GCP]}
json.dump(meta, open(os.path.join(DATA, "oldmap.json"), "w"), ensure_ascii=False, indent=1)
print("wrote", OUT_IMG, os.path.getsize(OUT_IMG), "bytes; LOO m", loo, file=sys.stderr)
