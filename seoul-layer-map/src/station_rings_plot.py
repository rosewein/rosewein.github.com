"""역 둘레 땅값 비교 방법 시험 그림 3장.
    python3 station_rings_plot.py <rings.json> <loc.npz> <pnu_price.npz> <출력 폴더> <제목 꼬리표>
"""
import json, sys, numpy as np, matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager as fm
from scipy.spatial import cKDTree
import os; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from station_rings_summary import series
for f in fm.findSystemFonts():
    if 'NotoSansCJK-Regular' in f or 'NotoSansCJK-Medium' in f: fm.fontManager.addfont(f)
plt.rcParams.update({'font.family': 'Noto Sans CJK JP', 'font.size': 10, 'axes.edgecolor': '#999999', 'axes.labelcolor': '#666666',
    'xtick.color': '#666666', 'ytick.color': '#666666', 'axes.spines.top': False, 'axes.spines.right': False, 'figure.dpi': 150})
TXT, TXT2, GRID = '#191919', '#666666', '#e8e8e8'
S1, S2, S3, S4 = '#257de0', '#f47230', '#00b894', '#f2a600'
RAMP = {'0-250': '#0f4a96', '250-500': '#257de0', '500-1000': '#84b9f3'}
R = json.load(open(sys.argv[1])); L = np.load(sys.argv[2]); Z = np.load(sys.argv[3]); out = sys.argv[4]; tag = sys.argv[5]
St = {s['name']: s for s in R['stations']}
pct = lambda v: None if v is None else 100 * (2 ** v - 1)
# ── 그림 1: 예시 역 두 곳의 필지 위치와 찾은 방법
import pyproj
metro = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'data', 'metro.json')))
tr = pyproj.Transformer.from_crs(4326, 5186, always_xy=True).transform
allst = [(s['name'], s['first'], tr(s['lng'], s['lat'])) for s in metro['stations']]
fig, axes = plt.subplots(1, 2, figsize=(11, 5.6))
for ax, name in zip(axes, ['중곡', '공덕']):
    s = St[name]; T = s['T']; y0 = T - 5; x0, yy0 = s['xy']
    X, Y, M = L[f'x{y0}'], L[f'y{y0}'], L[f'm{y0}']
    ok = ~np.isnan(X); d = np.hypot(X - x0, Y - yy0); sel = ok & (d < 1150)
    op = np.array([xy for n, f, xy in allst if f <= T + 5]); _, k = cKDTree(op).query(np.c_[X[sel], Y[sel]])
    mine = np.hypot(op[k, 0] - x0, op[k, 1] - yy0) < 1
    xs, ys, ms = X[sel] - x0, Y[sel] - yy0, M[sel]
    ax.scatter(xs[~mine], ys[~mine], s=2, c='#d6d6d6', lw=0, label='다른 역에 가까운 필지')
    for grp, col, lab in [((0, 1), S1, '코드 그대로(2026·2016 지적도)'), ((2,), S3, '이력으로 이음')]:
        g = mine & np.isin(ms, grp)
        ax.scatter(xs[g], ys[g], s=3, c=col, lw=0, label=f'{lab} {g.sum():,}')
    g = mine & np.isin(ms, (3, 4))
    if g.any():
        u, cnt = np.unique(np.round(np.c_[xs[g], ys[g]], 0), axis=0, return_counts=True)
        ax.scatter(u[:, 0], u[:, 1], s=6 * np.sqrt(cnt), facecolors='none', edgecolors=S2, lw=1.0,
                   label=f'같은·이웃 본번 자리로 대신 {g.sum():,}(원 크기 = 필지 수)')
    for r in (250, 500, 1000):
        ax.add_patch(plt.Circle((0, 0), r, fill=False, ec='#555555', lw=0.8, ls=(0, (3, 3))))
        ax.text(0, -r - 10, f'{r}m' if r < 1000 else '1km', color=TXT2, fontsize=8, ha='center', va='top',
                bbox=dict(fc='white', ec='none', pad=0.5, alpha=0.85))
    for n, f, (sx, sy) in allst:
        if f <= T + 5 and abs(sx - x0) < 1150 and abs(sy - yy0) < 1150:
            ax.plot(sx - x0, sy - yy0, 'o', ms=6 if n == name else 3.5, mfc='white', mec=TXT, mew=1.4)
            ax.text(sx - x0 + 35, sy - yy0 + 35, n, fontsize=9 if n == name else 7.5, color=TXT if n == name else TXT2, bbox=dict(fc='white', ec='none', pad=0.4, alpha=0.8))
    n500 = s['years'][str(y0)]['all']['cs']['0-500'][1]; e500 = s['years'][str(y0)]['exact']['cs']['0-500'][1]
    ax.set_title(f'{name}역({"·".join(s["lines"][:2])}, {T}년 개통) — {y0}년 필지\n500m 안 {n500:,}필지 중 정확한 위치(코드·이력) {100*e500/n500:.0f}%', fontsize=10.5, color=TXT, loc='left')
    ax.set_xlim(-1150, 1150); ax.set_ylim(-1150, 1150); ax.set_aspect('equal'); ax.set_xticks([]); ax.set_yticks([])
    for sp in ax.spines.values(): sp.set_visible(False)
    from matplotlib.lines import Line2D
    hs, ls_ = ax.get_legend_handles_labels()
    hh = [Line2D([], [], ls='', marker='o', ms=5, mfc=(h.get_facecolor()[0] if len(h.get_facecolor()) else 'none'), mec=(S2 if '대신' in l else 'none'), mew=1.2) for h, l in zip(hs, ls_)]
    ax.legend(hh, ls_, loc='upper left', fontsize=8, frameon=True, framealpha=0.9, edgecolor='none')
fig.suptitle(f'그림 1. 개통 5년 전 필지를 어디에 찍었나 — 고리마다 쓰는 필지와 찾은 방법 ({tag})', x=0.02, ha='left', fontsize=12, color=TXT)
fig.text(0.02, 0.015, '점 하나가 필지 하나(대표점). 필지는 개통 5년 뒤에 열려 있는 역 가운데 가장 가까운 역에만 붙였다. 대신 찍은 필지는 실제 위치와 수백 m 어긋날 수 있다.', fontsize=8.5, color=TXT2)
fig.tight_layout(rect=(0, 0.03, 1, 0.95)); fig.savefig(f'{out}/fig1_parcels.png'); plt.close(fig)
# ── 그림 2: 같은 역, 네 가지 계산
VARS = [('A_seoul', '가. 그 해 필지 중앙값 ÷ 서울', S1), ('A_ctrl', '가. 그 해 필지 중앙값 ÷ 1–2km 바깥', S3),
        ('B_seoul', '나. 같은 필지 변화 − 서울', S2), ('B_ctrl', '나. 같은 필지 변화 − 1–2km 바깥', S4)]
fig, axes = plt.subplots(1, 2, figsize=(11, 5.4), sharey=True)
xs = np.arange(-5, 6)
for ax, name in zip(axes, ['중곡', '공덕']):
    s = St[name]
    ax.axhline(0, color='#999999', lw=0.8); ax.axvline(0, color='#bbbbbb', lw=0.8, ls=(0, (2, 2)))
    T = s['T']; y0 = s['years'][str(T - 5)]['exact']; ends = []
    for v, lab, col in VARS:
        ys = [pct(x) for x in series(s, v, 'exact', '0-500')]
        yv = np.array([np.nan if y is None else y for y in ys])
        ax.plot(xs, yv, color=col, lw=2, marker='o', ms=4, mec='white', mew=0.8, ls='-' if 'ctrl' not in v else (0, (4, 2)))
        ends.append([yv[-1], lab.split('.')[0] + ('·바깥' if 'ctrl' in v else '·서울')])
    ends.sort(key=lambda e: e[0])
    for k in range(1, len(ends)):
        if ends[k][0] - ends[k-1][0] < 2.4: ends[k][0] = ends[k-1][0] + 2.4
    for yv_, lab_ in ends: ax.text(5.15, yv_, lab_, fontsize=8, color=TXT2, va='center')
    nc = y0['cs']['ctrl'][1]
    note = f"5년 전 필지: 0–500m {y0['cs']['0-500'][1]:,} / 1–2km 바깥 {nc:,}" + (" ← 너무 적음" if nc < 200 else '')
    ax.set_title(f'{name}역 둘레 0–500m ({s["T"]}년 개통)\n' + note, fontsize=10.5, color=TXT, loc='left')
    ax.set_xlim(-5.4, 6.6)
    ax.set_xticks(xs); ax.set_xticklabels([f'{x:+d}' if x else '개통' for x in xs])
    ax.set_xlabel('개통 해로부터 몇 년'); ax.grid(axis='y', color=GRID, lw=0.8)
axes[0].set_ylabel('비교 기준보다 더 오른 정도(%)')
from matplotlib.lines import Line2D
fig.legend([Line2D([], [], color=c, lw=2, ls='-' if 'ctrl' not in v else (0, (4, 2))) for v, _, c in VARS], [l for _, l, _ in VARS],
           loc='lower center', ncol=2, fontsize=9, frameon=False, bbox_to_anchor=(0.5, 0.04))
fig.suptitle(f'그림 2. 같은 역도 무엇과 견주고 어떤 필지를 쓰느냐에 따라 선이 달라진다 ({tag})', x=0.02, ha='left', fontsize=12, color=TXT)
fig.text(0.02, 0.01, '정확한 위치(코드 그대로·이력으로 이음)만 썼다. 0 = 개통 5년 전과 같은 상대 수준. 나는 개통 5년 전과 그 해에 모두 있는 필지만 쓴다.', fontsize=8.5, color=TXT2)
fig.tight_layout(rect=(0, 0.13, 1, 0.93)); fig.savefig(f'{out}/fig2_two_stations.png'); plt.close(fig)
# ── 그림 3: 95곳 중앙값, 2×2
from station_rings_summary import agg
fig, axes = plt.subplots(2, 2, figsize=(11, 7.4), sharex=True, sharey=True)
titles = {'A_seoul': '가. 그 해 필지 중앙값 ÷ 서울 중앙값', 'A_ctrl': '가. 그 해 필지 중앙값 ÷ 1–2km 바깥 중앙값',
          'B_seoul': '나. 같은 필지 변화율 − 서울 같은 필지 변화율', 'B_ctrl': '나. 같은 필지 변화율 − 1–2km 바깥'}
for ax, v in zip(axes.flat, ['A_seoul', 'A_ctrl', 'B_seoul', 'B_ctrl']):
    ax.axhline(0, color='#999999', lw=0.8); ax.axvline(0, color='#bbbbbb', lw=0.8, ls=(0, (2, 2)))
    for ring in ('0-250', '250-500', '500-1000'):
        med, n = agg(v, 'exact', ring)
        yv = 100 * (2 ** med - 1)
        ax.plot(xs, yv, color=RAMP[ring], lw=2, marker='o', ms=3.5, mec='white', mew=0.6, label=f'{ring.replace("-", "–")}m')
        ax.text(5.15, yv[-1], f'{ring.replace("-", "–")}m {yv[-1]:+.1f}%', fontsize=8, color=TXT2, va='center')
    ax.set_title(titles[v], fontsize=10, color=TXT, loc='left'); ax.grid(axis='y', color=GRID, lw=0.8)
    ax.set_xlim(-5.4, 7.4)
for ax in axes[1]:
    ax.set_xticks(xs); ax.set_xticklabels([f'{x:+d}' if x else '개통' for x in xs]); ax.set_xlabel('개통 해로부터 몇 년')
for ax in axes[:, 0]: ax.set_ylabel('더 오른 정도(%, 역 중앙값)')
axes[0, 0].legend(title='역에서 거리', fontsize=8, title_fontsize=8, frameon=False, loc='upper left')
fig.suptitle(f'그림 3. 새로 생긴 역세권 95곳을 모아 보면 — 거리 고리별 중앙값 ({tag})', x=0.02, ha='left', fontsize=12, color=TXT)
fig.text(0.02, 0.01, '1995–2018년에 개통 때 1km 안에 먼저 열린 역이 없던 역. 정확한 위치(코드·이력)만 썼다. 역마다 고리 안 필지가 20개 미만이면 뺐다(0–250m 86곳, 250–500m 92곳, 500–1000m 95곳; 바깥 기준은 82–91곳).', fontsize=8.5, color=TXT2)
fig.tight_layout(rect=(0, 0.03, 1, 0.95)); fig.savefig(f'{out}/fig3_95_stations.png'); plt.close(fig)
print('ok')
