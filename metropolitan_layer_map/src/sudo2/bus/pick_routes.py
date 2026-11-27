"""경기 BMS(2023-09)에서 서울로 들어가는 광역 노선(M·G·P·네 자리 번호)을 골라, 서울 쪽으로 가는 한 방향 정류소 좌표열을 만든다."""
import os as _os, sys as _sys  # paths.py 찾기: 이 파일 폴더에서 위로 올라감(저장소 src/, 작업 공간 $MLM_SUDO·$MLM_SUDO2)
_d = _os.path.dirname(_os.path.abspath(__file__))
while _d != _os.path.dirname(_d) and not _os.path.isfile(_os.path.join(_d, 'paths.py')):
    _d = _os.path.dirname(_d)
_sys.path.insert(1, _d)
from paths import SUDO2, UPLOADS  # noqa: E402
import csv, io, re, pickle, json, collections, math
import shapely
from shapely.prepared import prep
D = f'{UPLOADS}/'
S, nm, R = pickle.load(open('/tmp/bms.pkl', 'rb'))
sido = pickle.load(open('/tmp/sido.pkl', 'rb')); seoul = sido['seoul']; ps = prep(seoul)
prep_all = prep(shapely.unary_union([sido['seoul'], sido['incheon'], sido['gg']]).buffer(0.01))
def look(s):
    for p in ('GGB', 'SEB', 'ICB'):
        if p + s in S: return S[p + s]
PAT = re.compile(r'^([MGP]?\d{4}(?:-\d+)?)')
SKIP = ('예약', '전세', '예비', '(퇴근)')
CEN = (126.978, 37.5665)
def dkm(a, b): return math.hypot((a[0]-b[0])*88.4, (a[1]-b[1])*111.0)
out = []
for rid, rows in R.items():
    name = nm.get(rid)
    if not name: continue
    m = PAT.match(name)
    if not m or any(s in name for s in SKIP): continue
    # 상행·하행이 순서 번호를 따로 매긴 노선이 있어, 진행 방향별로 따로 줄 세운 뒤 상행→하행으로 잇는다
    byc = collections.defaultdict(list)
    seen_ = set()
    for r_ in rows:
        k_ = (r_['진행구분코드'], r_['정류장순서'], r_['정류장아이디'], r_['등록일자'])
        if k_ in seen_: continue  # 똑같은 줄이 두 번 들어간 곳
        seen_.add(k_); byc[r_['진행구분코드']].append(r_)
    for c_ in list(byc):  # 같은 방향에 순서 번호가 겹치면 판이 여럿 → 가장 늦게 등록한 판만
        rr = byc[c_]
        if len({x['정류장순서'] for x in rr}) < len(rr):
            last = max(x['등록일자'] for x in rr); byc[c_] = [x for x in rr if x['등록일자'] == last]
    rows = [x for c_ in sorted(byc, key=lambda c: {'F': 0, 'B': 1}.get(c, 2)) for x in sorted(byc[c_], key=lambda r: int(r['정류장순서']))]
    seq = [(look(r['정류장아이디']), r['정류장아이디']) for r in rows]
    n0 = len(seq); seq = [(p, s) for p, s in seq if p]
    if len(seq) < 3: continue
    ins = [ps.contains(shapely.Point(p[0], p[1])) for p, _ in seq]
    if not any(ins): continue
    dout = [0 if i else shapely.Point(p[0], p[1]).distance(seoul) for (p, _), i in zip(seq, ins)]
    i_far = max(range(len(seq)), key=lambda i: dout[i])
    dc = [dkm(p, CEN) for p, _ in seq]
    # 바깥 끝에서 앞으로 가며(되돌아 이어지면 처음으로) 시청에 가장 가까운 정류소까지
    order = list(range(i_far, len(seq))) + list(range(0, i_far))
    wrapj = dkm(seq[-1][0], seq[0][0])
    if wrapj > 2.0: order = list(range(i_far, len(seq)))
    if not any(ins[i] for i in order):  # 앞으로 가서는 서울에 못 닿으면(한 방향만 있는 자료) 거꾸로
        order = list(range(i_far, -1, -1)); code = 'rev'
    else: code = 'fwd'
    # 바깥 끝에서 앞으로 가다 처음 들어간 서울 구간에서, 바깥 끝과 가장 먼 정류소(되돌아 나가는 곳)까지
    t0 = next(t for t, i in enumerate(order) if ins[i]); t1 = t0
    while True:  # 서울 밖으로 잠깐(3km 안) 나갔다 다시 들어오는 곳은 한 구간으로 본다
        while t1 + 1 < len(order) and ins[order[t1 + 1]]: t1 += 1
        k = t1 + 1
        while k < len(order) and not ins[order[k]] and dout[order[k]] < 0.03: k += 1
        if k < len(order) and ins[order[k]] and k > t1 + 1: t1 = k; continue
        break
    j = max(order[t0:t1 + 1], key=lambda i: dkm(seq[i][0], seq[i_far][0])); order = order[:order.index(j) + 1]
    ok = [seq[i] for i in order]; insq = [ins[i] for i in order]
    if len(ok) < 3 or not any(insq): continue
    far = max(shapely.Point(p[0], p[1]).distance(seoul) for p, _ in ok) * 100
    if far < 5: continue  # 서울 바로 옆만 오가는 노선은 뺌
    if not any(prep_all.contains(shapely.Point(p[0], p[1])) for p, _ in ok[:1]): continue  # 바깥 끝이 수도권 밖(시외 성격)이면 뺌
    # 서울 첫 정류소 순서
    k_in = insq.index(True)
    out.append(dict(id=rid, name=name, base=m.group(1), dir=code, n=n0, nok=len(ok), far=round(far, 1),
                    o=ok[0][0][2], e=ok[-1][0][2], k_in=k_in,
                    pts=[(round(p[0], 6), round(p[1], 6)) for p, _ in ok], sid=[s for _, s in ok], sn=[p[2] for p, _ in ok]))
# 같은 번호·같은 출발지(1.5km 안) 변형은 정류소가 많은 하나만
out.sort(key=lambda r: -r['nok'])
keep = []
for r in out:
    dup = [k for k in keep if k['base'] == r['base'] and dkm(k['pts'][0], r['pts'][0]) < 1.5]
    if dup: dup[0].setdefault('variants', []).append(r['name']); continue
    keep.append(r)
for r in keep:  # 표시 이름: 변형 가운데 기본 번호가 있으면 그것으로
    names = [r['name']] + r.get('variants', [])
    disp = r['base'] if r['base'] in names else r['name']
    r['name'] = disp; r['variants'] = sorted({n for n in names if n != disp})
print('후보', len(out), '→ 남김', len(keep))
c = collections.Counter(r['base'][0] if r['base'][0] in 'MGP' else 'num' for r in keep); print(c)
miss = sum(r['n'] - r['nok'] for r in keep); tot = sum(r['n'] for r in keep); print('좌표 없는 정류소', miss, '/', tot)
json.dump(keep, open(f'{SUDO2}/bus/routes_gg.json', 'w'), ensure_ascii=False)
for r in sorted(keep, key=lambda r: r['name'])[:300:6]: print(r['name'], r['o'], '→', r['e'], r['far'], r['nok'], '/', r['n'], r.get('variants', ''))
