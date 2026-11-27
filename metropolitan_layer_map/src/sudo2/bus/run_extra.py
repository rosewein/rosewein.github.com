import os as _os, sys as _sys  # paths.py 찾기: 이 파일 폴더에서 위로 올라감(저장소 src/, 작업 공간 $MLM_SUDO·$MLM_SUDO2)
_d = _os.path.dirname(_os.path.abspath(__file__))
while _d != _os.path.dirname(_d) and not _os.path.isfile(_os.path.join(_d, 'paths.py')):
    _d = _os.path.dirname(_d)
_sys.path.insert(1, _d)
from paths import SUDO2  # noqa: E402
import json, pickle, sys, time
import busroute as B
P = pickle.load(open(f'{SUDO2}/bus/paths_gg_0.pkl', 'rb'))
P.update(pickle.load(open(f'{SUDO2}/bus/paths_gg_1.pkl', 'rb')))
ch = set(json.load(open('/tmp/rerun_gg.json')))
rs = json.load(open('routes_gg.json')) + json.load(open('routes_ic.json')) + json.load(open('routes_se.json'))
t = time.time(); n = 0
for r in rs:
    if r['id'] in ch or r['id'] not in P:
        p, b = B.route_seq([tuple(x) for x in r['pts']]); P[r['id']] = dict(path=p, breaks=b); n += 1
        if b: print('break', r['name'], b, flush=True)
pickle.dump(P, open(f'{SUDO2}/bus/paths_all.pkl', 'wb'))
print('routed', n, round(time.time() - t))
