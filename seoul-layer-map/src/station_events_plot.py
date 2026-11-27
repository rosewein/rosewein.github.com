"""사건 시점 시험 그림: 서울 전체 한 해 변화 띠 + 네 사례(교통·개발) 2×2.
    python3 -I station_events_plot.py <events.json> <출력 png>"""
import json, sys, numpy as np, matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager as fm
from matplotlib.gridspec import GridSpec, GridSpecFromSubplotSpec
from matplotlib.lines import Line2D
for f in fm.findSystemFonts():
    if 'NotoSansCJK-Regular' in f or 'NotoSansCJK-Medium' in f or 'NotoSansCJK-Bold' in f: fm.fontManager.addfont(f)
plt.rcParams.update({'font.family': 'Noto Sans CJK JP', 'font.size': 9, 'axes.edgecolor': '#999999', 'axes.labelcolor': '#666666',
    'xtick.color': '#666666', 'ytick.color': '#666666', 'axes.spines.top': False, 'axes.spines.right': False, 'figure.dpi': 150})
TXT, TXT2, GRID, EV = '#191919', '#666666', '#ececec', '#8a8a8a'
DARK, LIGHT, KEEP, RING = '#0f4a96', '#84b9f3', '#9a9a9a', '#7a7a7a'
R = json.load(open(sys.argv[1]))
pct = lambda v: np.nan if v is None else 100 * (2 ** v - 1)
YRS = list(range(1990, 2027))
d = lambda y, m, dd=15: y + (m - 1) / 12 + (dd - 1) / 365
CASES = [
    ('7호선 1996 구간', '교통', '7호선 동북 구간 10개 역(중곡~마들) 500m 안', [
        (d(1990, 4, 3), '1990.4 5·7·8호선 그해 착공 발표, 1996 구간 공사 시작(1990)'),
        (d(1996, 10, 11), '1996.10.11 1996 구간 개통')]),
    ('신분당선 신설역', '교통', '신분당선 양재시민의숲·청계산입구 500m 안', [
        (d(2001, 8, 1), '2001.8 예비타당성 통과 보도'),
        (d(2003, 12, 1), '2003.12 판교 광역교통개선대책에 들어감'),
        (d(2005, 6, 24), '2005.6.24 기공식'),
        (d(2011, 10, 28), '2011.10.28 개통')]),
    ('은평뉴타운(도시개발구역)', '개발', '은평뉴타운 도시개발구역(3.5㎢) 안', [
        (d(2002, 10, 18), '2002.10.18 뉴타운 시범지구 발표'),
        (d(2004, 2, 4), '2004.2.4 도시개발구역 지정안 가결'),
        (d(2004, 12, 23), '2004.12.23 1지구 착공'),
        (d(2008, 8, 1), '2008 1지구 입주 시작(8월 보도)')]),
    ('마곡지구(도시개발구역)', '개발+교통', '마곡지구 도시개발구역(3.7㎢) 안', [
        (d(2005, 12, 20), '2005.12.20 R&D 시티 계획 발표'),
        (d(2007, 4, 4), '2007.4.4 구역 지정안 가결'),
        (d(2007, 12, 28), '2007.12.28 구역 지정 고시'),
        (d(2008, 6, 20), '2008.6.20 마곡역(5호선) 개통'),
        (d(2008, 12, 30), '2008.12.30 실시계획 인가'),
        (d(2014, 5, 24), '2014.5.24 마곡나루역(9호선) 개통')]),
]
NUM = '①②③④⑤⑥⑦⑧'
fig = plt.figure(figsize=(12.5, 13.2))
outer = GridSpec(3, 2, figure=fig, height_ratios=[0.6, 1, 1], hspace=0.44, wspace=0.17, left=0.06, right=0.975, top=0.925, bottom=0.095)
# ── 위 띠: 서울 전체 한 해 변화
ax0 = fig.add_subplot(outer[0, :])
yy = R['_seoul_yoy']; xs = np.array([int(k) for k in yy]); vs = np.array([pct(v) for v in yy.values()])
part = np.isin(xs, [2006, 2007])
ax0.bar(xs[~part], vs[~part], width=0.72, color='#b4b4b4', lw=0)
ax0.bar(xs[part], vs[part], width=0.72, color='white', ec='#b4b4b4', lw=0.9, hatch='////')
ax0.axhline(0, color='#999999', lw=0.8)
for x, lab, yt, ha in [(d(1997, 11, 21), '1997.11 외환위기', 31, 'left'), (d(2008, 9, 15), '2008.9 세계 금융위기', 31, 'left'),
               (d(2020, 11, 3), '2020.11.3 공시가격 현실화 계획', 31, 'right'), (d(2022, 11, 23), '2022.11.23 수정 계획\n(2023년 공시에 2020년 현실화율)', 25, 'right')]:
    ax0.axvline(x, color=EV, lw=0.8, ls=(0, (3, 2)))
    ax0.text(x + (0.15 if ha == 'left' else -0.15), yt, lab, fontsize=7.5, color=TXT2, va='top', ha=ha, linespacing=1.15,
             bbox=dict(fc='white', ec='none', pad=0.5, alpha=0.9))
for x, v in zip(xs, vs):
    if abs(v) >= 9: ax0.text(x, v + (1 if v > 0 else -1), f'{v:+.0f}', fontsize=7, color=TXT2, ha='center', va='bottom' if v > 0 else 'top')
ax0.set_xlim(1989.3, 2026.7); ax0.set_ylim(-14, 36); ax0.set_xticks(range(1990, 2027, 5))
ax0.yaxis.grid(True, color=GRID, lw=0.6); ax0.set_axisbelow(True)
ax0.set_ylabel('앞 해 대비(%)')
ax0.set_title('서울 전체 — 같은 필지 공시지가의 한 해 변화(중앙값). 아래 네 칸의 점선은 이 변화를 뺀 값이다.', loc='left', fontsize=10, color=TXT)
ax0.text(2026.6, -13, '빗금: 2006년 파일에 필지가 3분의 2만 실려 그 해가 걸린 값(2006·2007)', fontsize=7, color=TXT2, ha='right', va='bottom')
# ── 네 사례
for idx, (key, kind, title, events) in enumerate(CASES):
    r, c = divmod(idx, 2)
    sub = GridSpecFromSubplotSpec(2, 1, subplot_spec=outer[r + 1, c], height_ratios=[3.2, 1], hspace=0.08)
    ax = fig.add_subplot(sub[0]); axk = fig.add_subplot(sub[1], sharex=ax)
    S = R[key]; b = S['b']; Yd = S['years']
    sp = np.array([pct(Yd[str(t)]['sp']) for t in YRS]); spc = np.array([pct(Yd[str(t)]['spc']) for t in YRS])
    keep = np.array([Yd[str(t)]['keep'] for t in YRS]); yrs = np.array(YRS)
    # 기준 해 필지가 15% 밑으로 남은 해는 그리지 않는다(남은 필지가 몇 안 되고 성격이 달라 값이 튐)
    ok = (yrs != 2006) & (keep >= 0.15)
    main = ok & (keep >= 0.5); surv = ok & (keep < 0.5)
    gone = np.where((yrs != 2006) & (keep < 0.15) & (yrs > b))[0]
    # 남은 필지가 절반 밑으로 떨어진 뒤는 남은 필지만의 값 → 옅은 점선
    first_surv = yrs[surv].min() if surv.any() else None
    if first_surv:
        seg = ok & (yrs < first_surv); seg2 = ok & (yrs >= yrs[seg].max())
    else:
        seg = ok; seg2 = np.zeros_like(ok)
    ax.plot(yrs[seg], sp[seg], color=LIGHT, lw=1.3, ls=(0, (4, 2)), zorder=3)
    ax.plot(yrs[seg], spc[seg], color=DARK, lw=2.0, zorder=4)
    if seg2.any():
        ax.plot(yrs[seg2], sp[seg2], color=LIGHT, lw=1.0, ls=(0, (1, 2)), zorder=3)
        ax.plot(yrs[seg2], spc[seg2], color=DARK, lw=1.3, ls=(0, (1, 1.5)), alpha=0.8, zorder=4)
    i06 = YRS.index(2006)
    ax.plot([2006], [spc[i06]], 'o', mfc='white', mec=DARK, ms=4.2, mew=1.1, zorder=5)
    # 구역 바깥 1km 띠(같은 구 대비): 개발이 둘레로 번졌는지
    RG = R.get(key + ' 바깥 1km')
    if RG:
        rv = np.array([pct(RG['years'][str(t)]['spc']) for t in YRS]); okr = (yrs != 2006) & ~np.isnan(rv)
        ax.plot(yrs[okr], rv[okr], color=RING, lw=1.5, zorder=3)
        lr = np.where(okr)[0][-1]; ax.text(YRS[lr], rv[lr] + 3, f'바깥 1km {rv[lr]:+.0f}%', fontsize=7.5, color=RING, ha='right', va='bottom')
        jr = int(np.nanargmax(np.where(okr, rv, np.nan)))
        if rv[jr] > 5: ax.text(YRS[jr], rv[jr] + 2, f'{rv[jr]:+.0f}%', fontsize=7.5, color=RING, ha='center', va='bottom')
    ax.axhline(0, color='#999999', lw=0.8, zorder=1)
    ax.plot([b], [0], 'o', color=TXT, ms=4, zorder=6)
    RGv = np.array([pct(R[key + ' 바깥 1km']['years'][str(t)]['spc']) for t in YRS]) if (key + ' 바깥 1km') in R else np.array([])
    lo = np.nanmin(np.r_[sp, spc, RGv]); hi = np.nanmax(np.r_[sp, spc, RGv]); pad = (hi - lo) * 0.08
    ymin, ymax = lo - pad, hi + pad + (hi - lo) * 0.34
    ax.set_ylim(ymin, ymax)
    ax.text(b, ymin + (ymax - ymin) * 0.015, f'기준 {b}', fontsize=7.5, color=TXT, ha='center', va='bottom',
            bbox=dict(fc='white', ec='none', pad=0.6, alpha=0.9), zorder=7)
    # 사건 세로선과 번호
    lv = 0; prev = -99
    for k, (x, lab) in enumerate(events):
        for a in (ax, axk): a.axvline(x, color=EV, lw=0.8, ls=(0, (3, 2)), zorder=2)
        lv = (lv + 1) % 3 if x - prev < 1.6 else 0; prev = x
        ax.text(x, ymax - (ymax - ymin) * (0.03 + 0.085 * lv), NUM[k], fontsize=9, color=TXT, ha='center', va='top',
                bbox=dict(fc='white', ec='none', pad=0.3), zorder=8)
    # 끝값 라벨
    last = np.where(ok & ~np.isnan(spc))[0][-1]; lastb = np.where(ok & ~np.isnan(sp))[0][-1]
    jm0 = int(np.nanargmax(np.where(main, spc, np.nan)))
    ya, yb = spc[last], sp[lastb]; gap = (ymax - ymin) * 0.06
    if abs(ya - yb) < gap:
        ya, yb = (ya + gap / 2, yb - gap / 2) if ya >= yb else (ya - gap / 2, yb + gap / 2)
    if last - jm0 > 3 or last == jm0:
        ax.text(YRS[last] + 0.4, ya, f'{spc[last]:+.0f}%', fontsize=8, color=DARK, va='center')
        ax.text(YRS[lastb] + 0.4, yb, f'{sp[lastb]:+.0f}%', fontsize=7.5, color=TXT2, va='center')
    # 꼭짓점 라벨(같은 구 대비 최대, 끝점이 아닐 때)
    jm = int(np.nanargmax(np.where(main, spc, np.nan)))
    if spc[jm] > 15 and jm != last:
        ax.text(YRS[jm] + 0.45, spc[jm], f'{YRS[jm]}년 {spc[jm]:+.0f}%', fontsize=8, color=DARK, ha='left', va='center',
                bbox=dict(fc='white', ec='none', pad=0.4, alpha=0.9), zorder=9)
    ax.yaxis.grid(True, color=GRID, lw=0.6); ax.set_axisbelow(True)
    ax.set_ylabel('기준 해보다 더 오른 정도(%)', fontsize=8)
    plt.setp(ax.get_xticklabels(), visible=False)
    nb = S['n_base']
    ax.set_title(f'{kind} — {title}\n기준 해 필지 {nb:,}개', loc='left', fontsize=9.5, color=TXT, linespacing=1.3)
    # 남은 비율 띠
    kk = yrs != 2006
    axk.fill_between(yrs[kk], 0, 100 * keep[kk], color='#e4e4e4', lw=0, step=None)
    axk.plot(yrs[kk], 100 * keep[kk], color=KEEP, lw=1.0)
    axk.set_ylim(0, 105); axk.set_yticks([0, 50, 100]); axk.set_yticklabels(['0', '50', '100%'], fontsize=7)
    axk.set_xlim(1989.3, 2026.7); axk.set_xticks(range(1990, 2027, 5))
    axk.text(1989.6, 8, '기준 해 필지 가운데 같은 코드로 남은 비율', fontsize=7, color=TXT2, va='bottom')
    if len(gone):
        g0 = YRS[gone[0]]; axk.text(g0 + 0.3, 100 * keep[gone[0]] + 6, f'{g0}년 {100*keep[gone[0]]:.0f}% — 이 뒤는 선 없음(필지가 거의 사라짐)', fontsize=7, color=TXT2, va='bottom')
    elif first_surv:
        axk.text(first_surv + 0.3, 100 * keep[YRS.index(first_surv)] + 6, f'{first_surv}년 {100*keep[YRS.index(first_surv)]:.0f}% — 이 뒤 선은 남은 필지만', fontsize=7, color=TXT2, va='bottom')
    # 사건 설명
    items = [f'{NUM[k]} {lab}' for k, (x, lab) in enumerate(events)]; lines = ['']
    for it in items:
        if lines[-1] and len(lines[-1]) + len(it) + 3 > 80: lines.append('')
        lines[-1] += ('   ' if lines[-1] else '') + it
    axk.text(0, -0.36, '\n'.join(lines), transform=axk.transAxes, fontsize=7.3, color=TXT2, va='top', ha='left', linespacing=1.35)
fig.suptitle('사건 시점 시험 그림 — 발표·지정·착공·개통 가운데 언제 땅값이 갈라지나 (공시지가, 1월 1일 기준)', x=0.012, ha='left', fontsize=13, color=TXT, y=0.99)
h = [Line2D([], [], color=DARK, lw=2.0), Line2D([], [], color=LIGHT, lw=1.3, ls=(0, (4, 2))), Line2D([], [], color=RING, lw=1.5), Line2D([], [], color=DARK, lw=1.3, ls=(0, (1, 1.5))),
     Line2D([], [], ls='', marker='o', mfc='white', mec=DARK, ms=4.2), Line2D([], [], color=EV, lw=0.8, ls=(0, (3, 2)))]
fig.legend(h, ['같은 구 다른 땅 대비', '서울 전체 대비', '구역 바깥 1km 띠(같은 구 대비)', '남은 필지가 절반 밑일 때(남은 필지만)', '2006년(파일 일부)', '사건'],
           loc='upper left', bbox_to_anchor=(0.012, 0.968), ncol=6, fontsize=8, frameon=False, handlelength=2.4, columnspacing=1.6)
import textwrap as _tw
fig.text(0.012, 0.008, '\n'.join(_tw.wrap('같은 필지 변화: 기준 해와 그 해에 같은 토지코드로 있는 필지의 log2(그 해 값 ÷ 기준 해 값) 중앙값에서 대조의 같은 값을 뺐다. 역 사례는 위치를 코드·이력으로 정확히 찾은 필지만, '
         '대조는 같은 구에서 그때 열린 모든 역과 1km 넘게 떨어진 필지(구마다 따로 빼고 모음). 은평·마곡은 V-World 도시개발구역(2026년 경계) 안 필지이고, 대조는 같은 구에서 구역과 그 바깥 1km 띠 밖인 필지. 공시는 1월 1일 기준이라 사건 뒤 첫 값은 다음 해 점이다.', 150)),
         fontsize=7.3, color=TXT2, ha='left', va='bottom', linespacing=1.4)
fig.savefig(sys.argv[2], dpi=150)
print('저장', sys.argv[2])
