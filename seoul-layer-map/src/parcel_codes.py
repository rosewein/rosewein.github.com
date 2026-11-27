"""공시지가 zip 37개 → 해마다 (토지코드 int64, ㎡당 공시지가 float64) 배열을 npz로 저장. 필지구분 1·2만.

    python3 parcel_codes.py <landprice.py가 있는 src 폴더> <zip 폴더> <출력 .npz>

19자리 숫자가 아닌 토지코드는 뺀다(해마다 0–57개). 같은 코드가 두 번 나오면 기준년월이 이른 쪽을 남긴다(landprice.py와 같음).
37개를 도는 데 2분쯤, 메모리 약 3GB. 출력 npz(약 550MB)는 저장소에 넣지 않는다.
"""
import sys, os, re, time
import numpy as np
sys.path.insert(0, sys.argv[1])
import landprice as L
src, out = sys.argv[2], sys.argv[3]
arrs = {}; bad = {}
for f in sorted(os.listdir(src)):
    m = re.search(r'(\d{4})', f)
    if not (m and f.endswith('.zip')): continue
    y = int(m.group(1)); t = time.time()
    head, rd, enc = L.open_rows(os.path.join(src, f)); c = L.colmap(head, f)
    s = {}; nb = 0
    for r in rd:
        if len(r) < len(head): continue
        if r[c['kind']].strip() not in ('1', '2'): continue
        code = r[c['code']].strip()
        if len(code) != 19 or not code.isdigit(): nb += 1; continue
        try: p = float(r[c['price']].replace(',', ''))
        except ValueError: continue
        ym = r[c['ym']].strip() if 'ym' in c else ''
        k = int(code)
        if k not in s or ym < s[k][0]: s[k] = (ym, p)
    ks = np.fromiter(s.keys(), dtype=np.int64, count=len(s)); o = np.argsort(ks)
    ps = np.fromiter((v[1] for v in s.values()), dtype=np.float64, count=len(s))
    arrs[f'c{y}'] = ks[o]; arrs[f'p{y}'] = ps[o]; bad[y] = nb
    del s
    print(y, len(ks), 'bad', nb, f'{time.time()-t:.0f}s', flush=True)
np.savez(out, **arrs)
