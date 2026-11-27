"""토지이동이력정보(dsId=13, CC BY)의 사유 문구에서 옛 지번 → 이어진 지번을 뽑아, 사라진 토지코드를 2016–2026년 공시지가에 있는 코드까지 따라간다.
쓰는 사유: 31 'X번과 합병되어 말소', 11 'X번으로 등록전환되어 말소'(앞으로 잇기), 43 'X에서 지번변경'(뒤로 잇기: X → 이 필지).
    python3 parcel_lineage.py <hist.parquet(AL_D157 CSV를 parquet으로)> <출력 lineage.pkl>
"""
import re, sys, numpy as np, pandas as pd, pickle
h = pd.read_parquet(sys.argv[1], columns=['고유번호','대장구분코드','토지이동사유코드','토지이동사유','토지이동일자'])
h = h[h['고유번호'].str.len() == 19]
JB = re.compile(r'^\s*(산)?\s*(\d+)(?:-(\d+))?\s*(?:번)?')
def to_pnu(src, txt, ledger=None):
    m = JB.match(txt or '')
    if not m: return None
    led = '2' if m.group(1) else (ledger or src[10])
    return int(src[:10] + led + f'{int(m.group(2)):04d}' + f'{int(m.group(3) or 0):04d}')
fwd = {}; why = {}
for code, led in (('31', None), ('11', '1')):
    sub = h[h['토지이동사유코드'] == code]
    for p, t, d in zip(sub['고유번호'], sub['토지이동사유'], sub['토지이동일자']):
        q = to_pnu(p, t, led)
        if q and q != int(p): fwd[int(p)] = q; why[int(p)] = (code, d)
sub = h[h['토지이동사유코드'] == '43']
n43 = 0
for p, t, d in zip(sub['고유번호'], sub['토지이동사유'], sub['토지이동일자']):
    q = to_pnu(p, t)
    if q and q != int(p) and q not in fwd: fwd[q] = int(p); why[q] = ('43', d); n43 += 1
pickle.dump((fwd, why), open(sys.argv[2], 'wb'))
print('잇기', len(fwd), '(43 뒤로잇기', n43, ')', '| 사유 문구에서 지번을 못 읽은 줄:',
      sum(1 for c in ('31','11') for t in h.loc[h['토지이동사유코드']==c,'토지이동사유'] if not JB.match(t or '')))
