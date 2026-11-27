import os as _os, sys as _sys  # paths.py 찾기: 이 파일 폴더에서 위로 올라감(저장소 src/, 작업 공간 $MLM_SUDO·$MLM_SUDO2)
_d = _os.path.dirname(_os.path.abspath(__file__))
while _d != _os.path.dirname(_d) and not _os.path.isfile(_os.path.join(_d, 'paths.py')):
    _d = _os.path.dirname(_d)
_sys.path.insert(1, _d)
from paths import SUDO2  # noqa: E402
import json, time, pickle, sys
import busroute as B
rs = json.load(open(f'{SUDO2}/bus/routes_gg.json'))
PART = int(sys.argv[1]); rs = rs[PART::2]
out = {}
t = time.time()
for i, r in enumerate(rs):
    p, b = B.route_seq([tuple(x) for x in r['pts']])
    out[r['id']] = dict(path=p, breaks=b)
    if i % 25 == 0: print(i, r['name'], round(time.time() - t), 's', 'breaks', b, flush=True)
pickle.dump(out, open(f'{SUDO2}/bus/paths_gg_{PART}.pkl', 'wb'))
print('done', round(time.time() - t))
