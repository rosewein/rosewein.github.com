"""route_years_bus.py 결과(namu/years_bus_before_68.json)에 사람이 읽고 정한 연도(namu/decide_68.py)를 덧입혀 years_bus.json을 만든다.
- y·z·how·src·note를 덮어씀
- DROP: 같은 노선의 옛 등록·보조 운행분이라 그리지 않음(drop 사유 기록)
- 생긴 해를 못 찾았고 BMS 마지막 등록이 2020년 이전인 노선은 hide(지금 다니는지 확인 못 함)"""
import json, pickle, sys
sys.path.insert(0, '/home/claude/sudo2/bus/namu')
from decide_68 import D, Z, DROP
YB = json.load(open('/home/claude/sudo2/bus/namu/years_bus_before_68.json'))
S, N, R = pickle.load(open('/tmp/bms.pkl', 'rb'))
for rid, d in D.items():
    e = YB.setdefault(rid, {})
    for k in ('y', 'z', 'how', 'src', 'note'):
        if k in d: e[k] = d[k]
    if 'src' in d and 'y' not in d and e.get('y') is None and 'z' in d:
        pass
for rid, (z, src) in Z.items():
    e = YB[rid]; e['z'] = z; e['zsrc'] = src
for rid, why in DROP.items():
    YB[rid]['drop'] = why
# 8156 출근 급행은 운행 종료 기록이 있어 버리지 않고 끝난 해를 둔다
YB['233000269'].pop('drop', None); YB['233000269'].update(z=2020, zsrc='화성시·오산시 버스 목록/폐선')
hide = []
for rid, e in YB.items():
    if e.get('y') is None and not e.get('drop') and rid in R:
        last = max(r['등록일자'][:10] for r in R[rid])
        if last < '2020':
            e['hide'] = f'생긴 해 못 찾음, BMS 마지막 등록 {last[:4]}년(지금 다니는지 확인 못 함)'; hide.append((rid, e.get('name'), last))
json.dump(YB, open('/home/claude/sudo2/bus/years_bus.json', 'w'), ensure_ascii=False, indent=0)
import collections
print('how', collections.Counter(e.get('how') for e in YB.values() if not e.get('drop') and not e.get('hide')))
print('z', sum(1 for e in YB.values() if e.get('z')), 'drop', sum(1 for e in YB.values() if e.get('drop')), 'hide', len(hide))
for h in hide: print('  hide', h)
print('unknown shown', [(k, e.get('name')) for k, e in YB.items() if e.get('y') is None and not e.get('drop') and not e.get('hide')])
