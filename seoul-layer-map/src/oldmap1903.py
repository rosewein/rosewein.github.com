"""1903 「韓國京城全圖」(서울역사022829)를 1899–1906년 옛 지도로 깔기 위한 맞춤·재투영

python3 src/oldmap1903.py   (원자료: $SLM_RAW/oldmaps/1903_한국경성전도_서울역사022829_사진2.jpg,
                             아카이브 상세 이미지 14장 중 2번째, 3750×3339. 제목·부산·대구 삽도가 있는 위쪽을 뺀 지도 본체 사진)
→ img/oldmap1903.webp, data/oldmap1903.json(build.py가 DATA.oldmapsMore로 넣고, 지도는 해에 맞는 옛 지도 한 장을 고른다)

- 판권: 明治三十六年五月二十六日印刷, 同五月三十日發行. 著作兼發行者 京釜鐵道株式會社(東京市京橋區山城町), 右代表者 取締役 澁澤榮一.
  印刷所 贇々舍, 印刷者 星野隆吉. 축척 표기 「縮尺壹万分之壹」(아카이브 상세 이미지 7번째·2번째에서 읽음, 2026-11-27).
- 범례(凡例): 道路, 人家, 京仁鐵道, 電氣鐵道, 坊界, 署界(×표를 단 점선), 川, 畑, 山岳, 樹木, 池, 城壁(톱니선), 京釜鐵道豫定線路(점선).
- 이지가 1907 지도에서 고른 대로 테두리째 깐다(제목·삽도가 있는 위쪽은 사진에 없어서 대구 삽도 밑에서 자른다).
  판권 칸과 범례 칸은 비운다. 나침반과 축척 막대는 지도 안의 것이라 둔다.
- 기준점은 1907 지도와 같은 성문 7곳(경위도는 kanggye1914.py·joseon.json과 같다. 돈의문은 1915년 헐린 자리).
  아핀 변환으로 맞춘다. 축척은 약 1:10,000에 해당하는 2.2m/px, 지도가 북쪽에서 약 4.7° 돌아가 있다(1907 지도도 약 5°).
"""
import json, math, os
import numpy as np
from PIL import Image
from pyproj import Transformer
import cv2
from paths import RAW, DATA

SRC = os.path.join(RAW, "oldmaps", "1903_한국경성전도_서울역사022829_사진2.jpg")
OUT_IMG = os.path.join(os.path.dirname(DATA), "img", "oldmap1903.webp")
URL = "https://museum.seoul.go.kr/archive/archiveNew/NR_relicView.do?mcsjgbnc=PS01003026001&mcseqno1=022829&mcseqno2=00000&cdLanguage=KOR"
RES = 3.0  # m/px. 원본 사진은 약 2.2m/px

GCP = [  # 이름, 원본 픽셀 x, y, 경도, 위도
    ("숭례문", 1250, 2193, 126.97534, 37.55993),
    ("흥인지문", 2676, 1728, 127.00979, 37.57115),
    ("광화문", 1386, 1380, 126.97689, 37.57594),
    ("창의문", 1068, 510, 126.96652, 37.59262),
    ("혜화문", 2525, 887, 127.00387, 37.58795),
    ("광희문", 2653, 2067, 127.01012, 37.56438),
    ("돈의문", 1046, 1739, 126.96881, 37.56831),
]
FRAME = (358, 110, 3442, 3068)                               # 지도 안쪽 테두리(위는 대구 삽도 밑)
HOLES = [(358, 2255, 700, 3068), (3098, 260, 3332, 845)]     # 판권 칸(왼쪽 테두리까지), 범례 칸

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
# 원본이 출력보다 촘촘하므로(2.2→3m/px) 먼저 살짝 흐려 계단 무늬를 줄인다
srcb = np.dstack([cv2.GaussianBlur(src, (0, 0), 0.6), alpha])
out = cv2.remap(srcb, px[0].reshape(ny, nx).astype(np.float32), px[1].reshape(ny, nx).astype(np.float32),
                cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT, borderValue=(0, 0, 0, 0))
Image.fromarray(out, "RGBA").save(OUT_IMG, "WEBP", quality=78, method=6)
nw = T3857i.transform(mx0, my1); se = T3857i.transform(mx1, my0)
lo, hi = min(loo), max(loo)
meta = {
    "id": "hanguk1903", "title": "한국경성전도(韓國京城全圖)",
    "date": "1903년 5월 30일 발행(京釜鐵道株式會社, 대표 澁澤榮一)",
    "imgs": [{"src": "img/oldmap1903.webp", "nw": [round(nw[0], 6), round(nw[1], 6)], "se": [round(se[0], 6), round(se[1], 6)]}],
    "from": 1899, "to": 1906, "dimWater": False,
    "src": "서울역사아카이브 소장유물 「한국경성전도」(서울역사022829, 1:10,000, 도성과 그 둘레만 그림, ×표 점선이 5서 경계). 서울역사박물관 소장, 공공누리 제1유형",
    "credit": "서울역사박물관 소장", "url": URL,
    "fit": f"성문 {len(GCP)}곳(헐린 돈의문은 옛 자리)으로 아핀 맞춤. 기준점 하나를 빼고 맞췄을 때 그 점의 어긋남 {round(lo)}–{round(hi)}m. 1903년 지도라 1899–1902년에는 몇 해 뒤, 1904–1906년에는 몇 해 앞 모습이다",
    "gcp": [{"name": g[0], "px": g[1], "py": g[2], "lng": g[3], "lat": g[4]} for g in GCP]}
json.dump(meta, open(os.path.join(DATA, "oldmap1903.json"), "w"), ensure_ascii=False, indent=1)
print(nx, ny, OUT_IMG, os.path.getsize(OUT_IMG), "bytes")
