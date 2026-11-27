"""인천 면허(BIS 노선별경유노드 2024-08)와 서울 면허(승하차 파일 2026-11) 광역버스를 경기와 같은 틀로 만든다 → routes_ic.json, routes_se.json"""
import csv, io, json, pickle, re, math, collections
import shapely
from shapely.prepared import prep
D = '/mnt/user-data/uploads/Downloads/'
S, nm, R = pickle.load(open('/tmp/bms.pkl', 'rb'))
N = pickle.load(open('/tmp/moct_node.pkl', 'rb'))
by = pickle.load(open('/tmp/ic_by.pkl', 'rb')); IC = pickle.load(open('/tmp/ic_map.pkl', 'rb'))
sido = pickle.load(open('/tmp/sido.pkl', 'rb')); seoul = sido['seoul']; ps = prep(seoul)
CEN = (126.978, 37.5665)
def dkm(a, b): return math.hypot((a[0]-b[0])*88.4, (a[1]-b[1])*111.0)
def stop(sid, prefs=('ICB', 'GGB', 'SEB')):
    for p in prefs:
        if p + sid in S: return S[p + sid]
def cut(seq):
    """seq: [(x,y,name or '', is_stop)] 순서열 → 바깥 끝에서 처음 서울 구간의 되돌아 나가는 곳까지"""
    ins = [ps.contains(shapely.Point(x, y)) for x, y, _, _ in seq]
    dout = [0 if i else shapely.Point(x, y).distance(seoul) for (x, y, _, _), i in zip(seq, ins)]
    i_far = max(range(len(seq)), key=lambda i: dout[i])
    order = list(range(i_far, len(seq))) + list(range(0, i_far))
    if dkm(seq[-1][:2], seq[0][:2]) > 2.0: order = list(range(i_far, len(seq)))
    if not any(ins[i] for i in order): order = list(range(i_far, -1, -1))
    t0 = next(t for t, i in enumerate(order) if ins[i]); t1 = t0
    while True:  # 서울 밖으로 잠깐(3km 안) 나갔다 다시 들어오는 곳은 한 구간으로 본다
        while t1 + 1 < len(order) and ins[order[t1 + 1]]: t1 += 1
        k = t1 + 1
        while k < len(order) and not ins[order[k]] and dout[order[k]] < 0.03: k += 1
        if k < len(order) and ins[order[k]] and k > t1 + 1: t1 = k; continue
        break
    j = max(order[t0:t1 + 1], key=lambda i: dkm(seq[i][:2], seq[i_far][:2]))
    order = order[:order.index(j) + 1]
    return [seq[i] for i in order], max(dout) * 100
out = []
for rid, name in IC.items():
    v = sorted(by[rid], key=lambda r: int(r['경로순번']))
    seq = []
    for r in v:
        if r['노드구분(코드)'] == '2':
            p = stop(r['노드(아이디)'])
            if p: seq.append((p[0], p[1], p[2], True))
        else:
            p = N.get(r['노드(아이디)'])
            if p: seq.append((p[0], p[1], '', False))
    # 교차로 노드 번호 가운데는 표준노드링크와 번호만 같고 다른 곳을 가리키는 것이 있어,
    # 앞뒤 정류소를 잇는 길에서 크게 벗어나는 노드는 버린다
    st_idx = [i for i, q in enumerate(seq) if q[3]]
    keep = []
    for i, q in enumerate(seq):
        if q[3]: keep.append(q); continue
        pv = max([k for k in st_idx if k < i], default=None); nx = min([k for k in st_idx if k > i], default=None)
        if pv is None or nx is None: continue
        a_, b_ = seq[pv][:2], seq[nx][:2]
        if dkm(a_, q[:2]) + dkm(q[:2], b_) <= 1.3 * dkm(a_, b_) + 0.5: keep.append(q)
    seq = keep
    # 연이은 같은 자리 정리
    s2 = [seq[0]]
    for q in seq[1:]:
        if dkm(q[:2], s2[-1][:2]) > 0.02: s2.append(q)
    part, far = cut(s2)
    stops = [q for q in part if q[3]]
    out.append(dict(id='IC' + rid, name=name, base=name, dir='ic', n=len(v), nok=len(part), far=round(far, 1),
                    o=stops[0][2] if stops else '', e=stops[-1][2] if stops else '', reg='인천',
                    pts=[(round(q[0], 6), round(q[1], 6)) for q in part], sn=[q[2] for q in part]))
json.dump(out, open('/home/claude/sudo2/bus/routes_ic.json', 'w'), ensure_ascii=False)
print('인천', len(out), [(r['name'], r['o'], r['e'], len(r['pts'])) for r in out][:30])
# 서울 면허 9xxx: 승하차 파일(정류장 순번은 역명 괄호 안 다섯 자리)
rows = list(csv.reader(io.StringIO(open(D + '서울시 버스노선별 정류장별 승하차 인원 정보.csv', 'rb').read().decode('cp949'))))[1:]
SR = collections.defaultdict(list)
for r in rows:
    if not re.fullmatch(r'9\d{3}(-1)?', r[1]): continue
    m = re.search(r'\((\d{5})\)\s*$', r[5])
    SR[r[1]].append((int(m.group(1)), r[3], re.sub(r'\(\d{5}\)\s*$', '', r[5])))
xl = {}
import openpyxl
wb = openpyxl.load_workbook(D + '서울시 버스노선별 표준정류장ID 연계 좌표정보(20190620).xlsx', read_only=True)
for r in list(wb.worksheets[0].iter_rows(values_only=True))[1:]: xl[str(r[0])] = (float(r[3]), float(r[4]), r[1])
se = []
for name, v in SR.items():
    v.sort(); seq = []; miss = 0
    for _, sid, nmx in v:
        p = stop(sid, ('SEB', 'GGB', 'ICB')) or xl.get(sid)
        if p: seq.append((p[0], p[1], nmx, True))
        else: miss += 1
    part, far = cut(seq)
    se.append(dict(id='SE' + name, name=name, base=name, dir='se', n=len(v), nok=len(part), far=round(far, 1), o=part[0][2], e=part[-1][2], reg='서울',
                   pts=[(round(q[0], 6), round(q[1], 6)) for q in part], sn=[q[2] for q in part], miss=miss))
json.dump(se, open('/home/claude/sudo2/bus/routes_se.json', 'w'), ensure_ascii=False)
print('서울', [(r['name'], r['o'], r['e'], len(r['pts']), r['miss'], r['far']) for r in se])
