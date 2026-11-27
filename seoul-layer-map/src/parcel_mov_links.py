"""토지이동정리전/후(30588) → 접수 단위로 이동 전 코드 → 이동 후 코드 묶음. 도형 좌표계가 섞여 있어(서울 5186 범위 안 52%) 도형 대신 코드 연결만 쓴다.
출력: {이동 전 코드: (이동 후 코드 배열, 접수연도, 이동종목)} pickle. 저장소에 넣지 않음(공공누리 4유형).
    python3 parcel_mov_links.py <mov_attr.parquet(30588 속성)> <출력 mov_links.pkl>
"""
import sys, pickle, numpy as np, pandas as pd
m = pd.read_parquet(sys.argv[1])
m = m[m['LEDG_GBN'].isin(['1','2']) & m[['ADM_SECT_C','LAND_LOC_C','BOBN','BUBN','ACC_NO','ACC_YEAR']].notna().all(axis=1)].copy()
m['pnu'] = m['ADM_SECT_C'].str.zfill(5) + m['LAND_LOC_C'].str.zfill(5) + m['LEDG_GBN'] + m['BOBN'].str.zfill(4) + m['BUBN'].str.zfill(4)
m = m[m['pnu'].str.fullmatch(r'\d{19}')]
m['pnu'] = m['pnu'].astype('int64')
m['key'] = m['ADM_SECT_C'] + '|' + m['ACC_YEAR'] + '|' + m['ACC_NO'] + '|' + m['LEDG_GBN'] + '|' + m['LAND_MOV_I'].fillna('')
aft = m[m['LAND_MOV_B'] == '2'].groupby('key')['pnu'].apply(lambda s: np.unique(s.values))
bef = m[m['LAND_MOV_B'] == '1'][['key','pnu','ACC_YEAR','LAND_MOV_I']]
links = {}
for k, p, y, it in zip(bef['key'], bef['pnu'], bef['ACC_YEAR'], bef['LAND_MOV_I']):
    a = aft.get(k)
    if a is None: continue
    a = a[a != p]
    if len(a) == 0: continue
    if p in links: links[p] = (np.unique(np.concatenate([links[p][0], a])), links[p][1], links[p][2])
    else: links[p] = (a, y, it)
pickle.dump(links, open(sys.argv[2], 'wb'))
sz = np.array([len(v[0]) for v in links.values()])
print('이동 전 코드', len(links), '| 이어지는 이동 후 코드 수 중앙값', np.median(sz), '90%', np.percentile(sz, 90), '최대', sz.max())
