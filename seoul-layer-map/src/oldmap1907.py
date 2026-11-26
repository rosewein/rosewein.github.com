"""시안: 1907 「實測詳密 最新京城全圖」(서울역사015439)를 1899–1913년 밑그림으로 깔아 보기 위한 맞춤·재투영(지도에는 아직 넣지 않음)

python3 src/oldmap1907.py   (원자료: $SLM_RAW/oldmaps/1907_실측상밀최신경성전도_서울역사015439.jpg, 아카이브 전도 이미지 1500×2109)
→ $SLM_RAW/build/oldmap1907.webp(테두리째), oldmap1907_wall.webp(성벽에서 250m 바깥까지만), oldmap1907.json(nw·se)

- 기준점은 성문 7곳. 경위도는 kanggye1914.py·joseon.json과 같다(돈의문은 1915년 헐린 자리).
- 아핀 변환으로 맞춘다. 축척은 약 1:10,400(지도 표기 1:10,000), 지도가 북쪽에서 약 5° 돌아가 있다.
  어긋남 7–38m, 하나 빼고 맞추면 그 점이 11–77m 어긋남(2026-11-27).
- 범례(凡例): 道路, 署界(붉은 점선), 坊界(검은 쇄선), 電氣鐵道(붉은 실선), 鐵道線路, 川, 池, 城壁(분홍 물결선), 山.
- 시안 화면은 shot.py 장면 js에서 DATA.oldmap의 imgs·from·to를 바꿔 찍었다(HANDOFF 「1914년 앞 시역」).
"""
import json, math, os
import numpy as np
from PIL import Image, ImageDraw, ImageFilter
from pyproj import Transformer
from shapely.geometry import Polygon
import cv2
from paths import RAW, DATA

SRC = os.path.join(RAW, "oldmaps", "1907_실측상밀최신경성전도_서울역사015439.jpg")
OUT = os.path.join(RAW, "build"); os.makedirs(OUT, exist_ok=True)
RES = 3.0  # m/px. 원본은 약 3.7m/px

GCP = [  # 이름, 원본 픽셀 x, y, 경도, 위도
    ("숭례문", 343, 1562, 126.97534, 37.55993),
    ("흥인지문", 1207, 1290, 127.00979, 37.57115),
    ("광화문", 430, 1075, 126.97689, 37.57594),
    ("창의문", 243, 553, 126.96652, 37.59262),
    ("혜화문", 1117, 790, 127.00387, 37.58795),
    ("광희문", 1183, 1497, 127.01012, 37.56438),
    ("돈의문", 212, 1292, 126.96881, 37.56831),
]
FRAME = (84, 312, 1442, 1998)                              # 지도 안쪽 테두리(대략)
HOLES = [(84, 1836, 270, 1998), (1276, 1706, 1442, 1998)]  # 범례, 「不許複製」 판권 칸

T5186 = Transformer.from_crs(4326, 5186, always_xy=True); T5186i = Transformer.from_crs(5186, 4326, always_xy=True)
T3857 = Transformer.from_crs(4326, 3857, always_xy=True); T3857i = Transformer.from_crs(3857, 4326, always_xy=True)
P = np.array([[g[1], g[2]] for g in GCP], float); G = np.array([T5186.transform(g[3], g[4]) for g in GCP])
def fit(P, G): return np.linalg.lstsq(np.c_[P, np.ones(len(P))], G, rcond=None)[0]
M = fit(P, G)
res = np.hypot(*(np.c_[P, np.ones(len(P))] @ M - G).T)
loo = [np.hypot(*(np.r_[P[i], 1] @ fit(P[np.arange(len(P)) != i], G[np.arange(len(P)) != i]) - G[i])) for i in range(len(P))]
print("어긋남(m)", {g[0]: round(r) for g, r in zip(GCP, res)}, "하나 빼고", {g[0]: round(r) for g, r in zip(GCP, loo)})

src = np.array(Image.open(SRC).convert("RGB")); H, W = src.shape[:2]
alpha = np.zeros((H, W), np.uint8); x0, y0, x1, y1 = FRAME; alpha[y0:y1, x0:x1] = 255
for a, b, c, d in HOLES: alpha[b:d, a:c] = 0
corn = np.array([[x0, y0], [x1, y0], [x1, y1], [x0, y1]], float)
ll = np.array([T5186i.transform(*p) for p in np.c_[corn, np.ones(4)] @ M]); em = np.array([T3857.transform(*p) for p in ll])
k = 1 / math.cos(math.radians(ll[:, 1].mean())); step = RES * k
mx0, my0 = em.min(0); mx1, my1 = em.max(0); nx, ny = int((mx1 - mx0) / step), int((my1 - my0) / step)
MX, MY = np.meshgrid(mx0 + (np.arange(nx) + .5) * step, my1 - (np.arange(ny) + .5) * step)
lon, lat = T3857i.transform(MX.ravel(), MY.ravel()); ex, ey = T5186.transform(lon, lat)
px = np.linalg.inv(np.r_[M.T, [[0, 0, 1]]]) @ np.vstack([ex, ey, np.ones_like(ex)])
out = cv2.remap(np.dstack([src, alpha]), px[0].reshape(ny, nx).astype(np.float32), px[1].reshape(ny, nx).astype(np.float32),
                cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT, borderValue=(0, 0, 0, 0))
im = Image.fromarray(out, "RGBA"); im.save(os.path.join(OUT, "oldmap1907.webp"), "WEBP", quality=80, method=6)
# 안 나: 성벽(tram.json의 wall 고리)에서 250m 바깥까지만 남기고 가장자리를 흐리게
wall = json.load(open(os.path.join(DATA, "tram.json")))["wall"]
poly = Polygon([T3857.transform(*p) for p in wall]).buffer(250 * k)
mask = Image.new("L", (nx, ny), 0)
ImageDraw.Draw(mask).polygon([((x - mx0) / (mx1 - mx0) * nx, (my1 - y) / (my1 - my0) * ny) for x, y in poly.exterior.coords], fill=255)
mask = mask.filter(ImageFilter.GaussianBlur(12))
im.putalpha(Image.fromarray(np.minimum(np.array(im.getchannel("A")), np.array(mask))))
im.save(os.path.join(OUT, "oldmap1907_wall.webp"), "WEBP", quality=80, method=6)
nw = T3857i.transform(mx0, my1); se = T3857i.transform(mx1, my0)
json.dump({"nw": [round(nw[0], 6), round(nw[1], 6)], "se": [round(se[0], 6), round(se[1], 6)]}, open(os.path.join(OUT, "oldmap1907.json"), "w"))
print(nx, ny, "→", OUT)
