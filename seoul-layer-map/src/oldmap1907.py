"""1907 「實測詳密 最新京城全圖」(서울역사015439)를 1907–1913년 옛 지도로 깔기 위한 맞춤·재투영

python3 src/oldmap1907.py   (원자료: $SLM_RAW/oldmaps/1907_실측상밀최신경성전도_서울역사015439.jpg, 아카이브 전도 이미지 1500×2109)
→ img/oldmap1907.webp, data/oldmap1907.json(build.py가 DATA.oldmapsMore로 넣고, 지도는 해에 맞는 옛 지도 한 장을 고른다)

- 이지가 시안(가. 테두리째 / 나. 성벽 둘레만)에서 테두리째 까는 쪽을 골랐다(2026-11-27). 나 안 코드는 지웠다(커밋 aa62467에 있음).
- 처음에는 1899–1913년에 깔았으나, 1903 「韓國京城全圖」(oldmap1903.py)를 받은 뒤 1899–1906년은 그 지도에 넘기고 1907–1913년만 맡는다(2026-11-27).

- 기준점은 성문 7곳. 경위도는 kanggye1914.py·joseon.json과 같다(돈의문은 1915년 헐린 자리).
- 아핀 변환으로 맞춘다. 축척은 약 1:10,400(지도 표기 1:10,000), 지도가 북쪽에서 약 5° 돌아가 있다.
  어긋남 7–38m, 하나 빼고 맞추면 그 점이 11–77m 어긋남(2026-11-27).
- 범례(凡例): 道路, 署界(붉은 점선), 坊界(검은 쇄선), 電氣鐵道(붉은 실선), 鐵道線路, 川, 池, 城壁(분홍 물결선), 山.
"""
import json, math, os
import numpy as np
from PIL import Image
from pyproj import Transformer
import cv2
from paths import RAW, DATA

SRC = os.path.join(RAW, "oldmaps", "1907_실측상밀최신경성전도_서울역사015439.jpg")
OUT_IMG = os.path.join(os.path.dirname(DATA), "img", "oldmap1907.webp")
URL = "https://museum.seoul.go.kr/archive/archiveNew/NR_relicView.do?mcsjgbnc=PS01003026001&mcseqno1=015439&mcseqno2=00000&cdLanguage=KOR"
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
Image.fromarray(out, "RGBA").save(OUT_IMG, "WEBP", quality=80, method=6)
nw = T3857i.transform(mx0, my1); se = T3857i.transform(mx1, my0)
lo, hi = min(loo), max(loo)
meta = {
    "id": "silcheuk1907", "title": "실측상밀 최신경성전도(實測詳密 最新京城全圖)",
    "date": "1907년 11월 수정 재판(같은 해 3월 초판, 日韓書房, 저작겸발행자 森山美夫)",
    "imgs": [{"src": "img/oldmap1907.webp", "nw": [round(nw[0], 6), round(nw[1], 6)], "se": [round(se[0], 6), round(se[1], 6)]}],
    "from": 1907, "to": 1913, "dimWater": False,
    "src": "서울역사아카이브 소장유물 「실측상밀 최신경성전도」(서울역사015439, 1:10,000, 도성 둘레만 그림, 붉은 점선이 5서 경계). 서울역사박물관 소장, 공공누리 제1유형",
    "credit": "서울역사박물관 소장", "url": URL,
    "fit": f"성문 {len(GCP)}곳(헐린 돈의문은 옛 자리)으로 아핀 맞춤. 기준점 하나를 빼고 맞췄을 때 그 점의 어긋남 {round(lo)}–{round(hi)}m. 1907년 지도라 1908–1913년에는 몇 해 앞 모습이다",
    "gcp": [{"name": g[0], "px": g[1], "py": g[2], "lng": g[3], "lat": g[4]} for g in GCP]}
json.dump(meta, open(os.path.join(DATA, "oldmap1907.json"), "w"), ensure_ascii=False, indent=1)
print(nx, ny, OUT_IMG, os.path.getsize(OUT_IMG), "bytes")
