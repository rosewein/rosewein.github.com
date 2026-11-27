"""그림 3 다시: 역 둘레 개발 적음·많음 × 대조 세 가지.
    python3 -I station_rings_ctrl_plot.py <rings_ctrl.json> <출력 png>"""
import json, sys, numpy as np, matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager as fm
for f in fm.findSystemFonts():
    if 'NotoSansCJK-Regular' in f or 'NotoSansCJK-Medium' in f: fm.fontManager.addfont(f)
plt.rcParams.update({'font.family': 'Noto Sans CJK JP', 'font.size': 9.5, 'axes.edgecolor': '#999999', 'axes.labelcolor': '#666666',
    'xtick.color': '#666666', 'ytick.color': '#666666', 'axes.spines.top': False, 'axes.spines.right': False, 'figure.dpi': 150})
TXT, TXT2, GRID = '#191919', '#666666', '#e8e8e8'
RAMP = {'0-250': '#0f4a96', '250-500': '#257de0', '500-1000': '#84b9f3'}
R = json.load(open(sys.argv[1]))
dev = np.array([np.nan if r['dev'] is None else r['dev'] for r in R]); cut = float(np.nanmedian(dev))
G = {'lo': [r for r in R if r['dev'] is not None and r['dev'] <= cut], 'hi': [r for r in R if r['dev'] is not None and r['dev'] > cut]}
KS = list(range(-5, 6))
def mat(rs, ctrl, ring):
    return np.array([[np.nan if (r['years'][str(k)][ring] is None or r['years'][str(k)][ring][ctrl] is None) else r['years'][str(k)][ring][ctrl] for k in KS] for r in rs])
rng = np.random.default_rng(0)
def boot(a, B=2000):
    out = np.full((2, a.shape[1]), np.nan)
    for c in range(a.shape[1]):
        v = a[:, c]; v = v[~np.isnan(v)]
        if len(v) < 5: continue
        m = np.median(v[rng.integers(0, len(v), (B, len(v)))], axis=1); out[:, c] = np.percentile(m, [5, 95])
    return out
pct = lambda v: 100 * (2 ** np.asarray(v) - 1)
CT = [('seoul', '서울 전체와 견줌'), ('sim', '비슷한 땅과 견줌'), ('future', '나중에 역이 생길 곳과 견줌')]
fig, axes = plt.subplots(2, 3, figsize=(13.2, 8.4), sharex=True, sharey=True)
rows = [('lo', f'역 둘레 개발 적음 — 개통 10년 사이 500m 안 필지가 {100*cut:.0f}% 이하로 사라진 역'),
        ('hi', f'역 둘레 개발 많음 — {100*cut:.0f}%보다 많이 사라진 역(재개발·택지 등으로 지번이 바뀜)')]
summary = {}; ROWLAB = []
for ri, (g, rlab) in enumerate(rows):
    for ci, (c, clab) in enumerate(CT):
        ax = axes[ri, ci]
        ax.axhline(0, color='#999999', lw=0.8); ax.axvline(0, color='#bbbbbb', lw=0.8, ls=(0, (2, 2)))
        for ring in ('500-1000', '250-500', '0-250'):
            a = mat(G[g], c, ring); m = np.nanmedian(a, axis=0); n = (~np.isnan(a)).sum(0)
            if ring == '0-250':
                lo, hi = boot(a); ax.fill_between(KS, pct(lo), pct(hi), color=RAMP[ring], alpha=0.12, lw=0)
            ax.plot(KS, pct(m), color=RAMP[ring], lw=2.0 if ring == '0-250' else 1.6, marker='o', ms=3.2, mec='white', mew=0.6, zorder=3)
            summary[(g, c, ring)] = (pct(m[5]), pct(m[10]), int(n[10]))
        # 끝값 라벨(겹침 피하기)
        ends = sorted([(pct(np.nanmedian(mat(G[g], c, r), axis=0)[10]), r) for r in RAMP], reverse=True)
        ys = []; gap = 1.25
        for v, r in ends:
            y = v if not ys or ys[-1] - v >= gap else ys[-1] - gap; ys.append(y)
            ax.text(5.25, y, f'{r.replace("-", "–")}m {v:+.1f}%', fontsize=7.8, color=RAMP[r] if r != '500-1000' else '#5a8fc9', va='center')
        ax.grid(axis='y', color=GRID, lw=0.7); ax.set_axisbelow(True)
        ax.set_title(clab, fontsize=9.5, color=TXT, loc='left')
        ax.set_xlim(-5.4, 8.2)
        nst = len([r for r in G[g] if r['years']['5']['0-250'] is not None and r['years']['5']['0-250'][c] is not None])
        ax.text(-5.2, -7.6, f'0–250m {nst}곳', fontsize=7.5, color=TXT2)
    ROWLAB.append(rlab)
for ax in axes.flat: ax.tick_params(axis='x', labelsize=8)
for ax in axes[1]:
    ax.set_xticks(KS); ax.set_xticklabels([f'{x:+d}' if x else '개통' for x in KS]); ax.set_xlabel('개통 해로부터 몇 년(공시 1월 1일)')
for ax in axes[:, 0]: ax.set_ylabel('개통 5년 전보다 더 오른 정도(%)')
axes[0, 0].set_ylim(-8.5, 13.5)
from matplotlib.lines import Line2D
from matplotlib.patches import Patch
h = [Line2D([], [], color=RAMP[r], lw=2, marker='o', ms=3.2, mec='white') for r in RAMP] + [Patch(color=RAMP['0-250'], alpha=0.12)]
fig.legend(h, ['역에서 0–250m', '250–500m', '500–1000m', '0–250m 역 중앙값의 90% 범위(역을 다시 뽑아 2,000번)'], loc='upper left',
           bbox_to_anchor=(0.012, 0.962), ncol=4, fontsize=8.3, frameon=False)
fig.suptitle('그림 3(다시). 새로 생긴 역세권 93곳 — 대조를 바꾸고, 역 둘레 개발 정도로 나눠 보면', x=0.012, ha='left', fontsize=12.5, color=TXT, y=0.985)
fig.text(0.012, 0.902, '대조  비슷한 땅: 같은 구 · 개통 5년 전 값이 구 안 10분위로 같음 · 개통 5년 뒤 열려 있는 모든 역에서 1km 밖.   '
         '나중에 역이 생길 곳: 개통 6–15년 뒤 열릴 역의 500m 안 · 개통 5년 뒤 열려 있는 모든 역에서 1km 밖(서울 전체에서).', fontsize=8, color=TXT2)
import textwrap as _tw
fig.text(0.012, 0.012, '\n'.join(_tw.wrap('같은 필지 변화: 개통 5년 전과 그 해에 같은 토지코드로 있는 필지의 log2 변화 중앙값에서 대조 값을 뺀 뒤, 역마다 낸 값의 중앙값. 정확한 위치(코드·이력)만 썼다. '
         '1995–2018년 개통, 개통 때 1km 안에 먼저 열린 역이 없던 95곳 가운데 개발 정도를 잴 수 있는 93곳. 개발 정도 = 개통 5년 전 500m 안 필지 가운데 개통 5년 뒤 같은 코드가 없는 비율(가운데값 기준으로 나눔).', 175)),
         fontsize=7.4, color=TXT2, ha='left', va='bottom', linespacing=1.4)
fig.tight_layout(rect=(0, 0.045, 0.995, 0.875), h_pad=4.2)
for ri in range(2):
    bb = axes[ri, 0].get_position()
    fig.text(0.012, bb.y1 + 0.045, ROWLAB[ri], fontsize=10.5, color=TXT, ha='left', va='bottom')
fig.savefig(sys.argv[2], dpi=150)
for k, v in summary.items(): print(k, f'T0 {v[0]:+.1f} T+5 {v[1]:+.1f} n{v[2]}')
