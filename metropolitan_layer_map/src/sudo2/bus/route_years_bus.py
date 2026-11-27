"""광역버스 노선마다 생긴 해를 나무위키 「YYYY년 개업한 버스 노선」 분류(2026-11-27 열람)에서 찾아 붙인다 → years_bus.json"""
import os as _os, sys as _sys  # paths.py 찾기: 이 파일 폴더에서 위로 올라감(저장소 src/, 작업 공간 $MLM_SUDO·$MLM_SUDO2)
_d = _os.path.dirname(_os.path.abspath(__file__))
while _d != _os.path.dirname(_d) and not _os.path.isfile(_os.path.join(_d, 'paths.py')):
    _d = _os.path.dirname(_d)
_sys.path.insert(1, _d)
from paths import EXT, SUDO2  # noqa: E402
import json, re, pickle, collections
D = f'{SUDO2}/bus/'
CITY = ['인천','수원','성남','고양','용인','부천','안산','안양','남양주','화성','평택','의정부','시흥','파주','김포','광명','경기광주','군포','하남','오산','이천','양주','구리','안성','포천','의왕','여주','동두천','과천','가평','양평','연천','서울']
ent = collections.defaultdict(list)  # (city, num) -> [(year, title)]
byn = collections.defaultdict(list)  # num -> [(city, year, title)]
for fn in ('namu/open_pre2001.tsv', 'namu/open_2001.tsv'):
    for ln in open(D + fn, encoding='utf-8'):
        y, title = ln.rstrip('\n').split('\t')
        if not y.isdigit(): continue
        if '(폐선)' in title: continue  # 없어진 노선 문서는 지금 노선과 맞추지 않음
        for part in title.split(', '):
            m = re.match(r'^(\S+) 버스 (.+)$', part)
            if m: city, nums = m.group(1), m.group(2); last_city = city
            else: city, nums = last_city, part
            for n in re.split(r',\s*', nums):
                n = re.sub(r'\(.*?\)', '', n).strip()
                ent[(city, n)].append((int(y), title)); byn[n].append((city, int(y), title))
mp = {}
for ln in open(D + 'namu/open_mp.tsv', encoding='utf-8'):
    y, title = ln.rstrip('\n').split('\t')
    for n in re.findall(r'[MP]\d{4}', title): mp.setdefault(n, (int(y), title))
oc = pickle.load(open('/tmp/origin_city.pkl', 'rb'))
import pyarrow.parquet as pq, shapely, shapely.wkb
from shapely.prepared import prep
_t = pq.read_table(f'{EXT}/vuski_admdongkor/parquet/simplified/sgg_20261001_light.parquet').to_pandas()
_cg = collections.defaultdict(list)
for row in _t.itertuples():
    g = shapely.wkb.loads(row.geometry)
    if row.sidonm.startswith('서울'): _cg['서울'].append(g)
    elif row.sidonm.startswith('인천'): _cg['인천'].append(g)
    elif row.sidonm == '경기도':
        c = '경기광주' if row.sggnm.startswith('광주시') else re.match(r'^(.+?)[시군]', row.sggnm).group(1)
        _cg[c].append(g)
CG = {c: prep(shapely.unary_union(v).buffer(0.003)) for c, v in _cg.items()}
def passes(r, city):  # 노선이 그 시·군을 지나가는지(면허 지역이면 대개 지나감)
    g = CG.get(city)
    return bool(g) and any(g.contains(shapely.Point(x, y)) for x, y in r['pts'])
def city_of(rid, reg):
    if reg == '인천': return '인천'
    if reg == '서울': return '서울'
    c = oc.get(rid)
    if not c: return None
    sido, sgg = c
    if sido.startswith('인천'): return '인천'
    if sgg == '광주시': return '경기광주'
    return re.match(r'^(.+?)[시군]', sgg).group(1)
def base(name):
    n = re.sub(r'\(.*?\)', '', name)
    n = re.sub(r'(번|전|급|예약)$', '', n)
    return n
rs = json.load(open(D + 'routes_gg.json')) + json.load(open(D + 'routes_ic.json')) + json.load(open(D + 'routes_se.json'))
out = {}; how = collections.Counter()
for r in rs:
    reg = r.get('reg', '경기'); nm = base(r['name']); city = city_of(r['id'], reg)
    cands = [nm, re.sub(r'[ABN]$', '', nm)]
    y = None
    for n in cands:
        if n in mp: y = (mp[n][0], mp[n][1], 'M·P 번호'); break
        if (city, n) in ent: e = min(ent[(city, n)]); y = (e[0], e[1], '시·번호'); break
    if y is None:  # 다른 시 문서라도 그 시를 지나가는 노선이면 받음
        for n in cands:
            cs = sorted([c for c in byn.get(n, []) if c[0] != '서울' and passes(r, c[0])], key=lambda c: c[1])
            if len({c[0] for c in cs}) == 1: y = (cs[0][1], cs[0][2], '번호·지나는 시'); break
    out[r['id']] = dict(y=y[0] if y else None, src=y[1] if y else None, how=y[2] if y else '못 찾음', city=city, name=r['name'], reg=reg)
    how[out[r['id']]['how']] += 1
json.dump(out, open(D + 'years_bus.json', 'w'), ensure_ascii=False, indent=0)
print(how)
miss = [(v['reg'], v['city'], v['name']) for v in out.values() if v['y'] is None]
print(len(miss)); print(sorted(miss))
print(collections.Counter((v['y'] // 5 * 5) if v['y'] else None for v in out.values()))
other = [(v['name'], v['city'], v['src']) for v in out.values() if v['how'].startswith('번호만')]
print(other)
