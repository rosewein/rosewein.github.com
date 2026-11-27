"""나무위키 노선 글(기점 - 경유지 - … - 종점)의 지명을 전국 버스정류장 이름으로 찾아 좌표 순서로 바꾼다.
같은 이름이 여러 곳이면 앞 지점에 가장 가까운 것을 고른다(첫 지점은 기점 주소의 시·군 안에서)."""
import os as _os, sys as _sys  # paths.py 찾기: 이 파일 폴더에서 위로 올라감(저장소 src/, 작업 공간 $MLM_SUDO·$MLM_SUDO2)
_d = _os.path.dirname(_os.path.abspath(__file__))
while _d != _os.path.dirname(_d) and not _os.path.isfile(_os.path.join(_d, 'paths.py')):
    _d = _os.path.dirname(_d)
_sys.path.insert(1, _d)
from paths import UPLOADS  # noqa: E402
import csv, re, math, collections, pickle, os

FN = f'{UPLOADS}/국토교통부_전국 버스정류장 위치정보_20261109.csv'
CACHE = '/tmp/stops_capital.pkl'

def norm(s):
    s = re.sub(r'\(.*?\)', '', s)
    s = re.sub(r'[\s·.,\-]', '', s)
    s = s.replace('입구', '입구').replace('사거리', '사거리')
    return s

def load():
    if os.path.exists(CACHE): return pickle.load(open(CACHE, 'rb'))
    rows = []
    with open(FN, encoding='cp949', errors='replace') as f:
        rd = csv.reader(f); next(rd)
        for r in rd:
            try: la, lo = float(r[2]), float(r[3])
            except: continue
            if not (126.2 < lo < 128.0 and 36.8 < la < 38.4): continue
            rows.append((r[1], lo, la, r[7]))
    idx = collections.defaultdict(list)   # 정류장 이름의 '.'로 나뉜 조각마다
    for nm, lo, la, city in rows:
        parts = [nm] + re.split(r'[.·]', nm)
        for p in set(norm(x) for x in parts if x):
            if len(p) >= 2: idx[p].append((lo, la, city, nm))
    out = (rows, dict(idx))
    pickle.dump(out, open(CACHE, 'wb'))
    return out

ROWS, IDX = load()
KEYS = list(IDX)

def km(a, b):
    return math.hypot((a[0] - b[0]) * 88.4, (a[1] - b[1]) * 111.0)

ALIAS = {'청량리역환승센터': '청량리역환승센터', '서울역버스환승센터': '서울역버스환승센터', '강남역': '강남역', '사당역': '사당역'}

def cands(name):
    c = _cands(name)
    if c: return c
    for alt in (name.replace('주민센터', '행정복지센터'), name.replace('여객자동차터미널', '터미널'), name.replace('공용버스터미널', '터미널')):
        if alt != name:
            c = _cands(alt)
            if c: return c
    for part in re.split(r'[.·,]', name):   # '세이브존.단대오거리역'처럼 여러 이름을 붙인 것
        part = part.strip()
        if part and part != name:
            c = _cands(part)
            if c: return c
    return []

def _cands(name):
    n = norm(name)
    if not n: return []
    if n in IDX: return IDX[n]
    # 역·터미널 꼴 줄임말 맞춤
    for suf in ('시외버스터미널', '버스터미널', '터미널', '종점', '차고지', '정류장', '정류소'):
        if n.endswith(suf) and n[:-len(suf)] + '터미널' in IDX: return IDX[n[:-len(suf)] + '터미널']
    hit = [k for k in KEYS if len(n) >= 3 and (k.startswith(n) or (len(k) >= 3 and n.startswith(k) and len(k) >= len(n) - 2))]
    out = []
    for k in hit[:40]: out += IDX[k]
    return out

CENTER = {  # 시·군 중심(어림, 첫 지점 고르기에만 씀)
    '서울': (126.98, 37.56), '인천': (126.70, 37.47), '안양': (126.93, 37.39), '군포': (126.93, 37.35), '의정부': (127.05, 37.74),
    '성남': (127.12, 37.42), '광명': (126.86, 37.46), '남양주': (127.22, 37.65), '고양': (126.83, 37.66), '구리': (127.13, 37.60),
    '의왕': (126.97, 37.34), '양주': (127.05, 37.80), '하남': (127.20, 37.54), '파주': (126.78, 37.76), '용인': (127.15, 37.27),
    '김포': (126.68, 37.63), '수원': (127.02, 37.28), '화성': (127.05, 37.20), '포천': (127.20, 37.89), '가평': (127.45, 37.80),
    '양평': (127.49, 37.49), '부천': (126.78, 37.50), '시흥': (126.80, 37.38), '안산': (126.83, 37.32), '오산': (127.07, 37.15),
    '과천': (126.99, 37.43), '강화': (126.49, 37.71), '연천': (127.07, 38.10), '광주': (127.25, 37.41), '이천': (127.44, 37.27), '평택': (127.10, 36.99), '동두천': (127.06, 37.90)}

def locate(seq, first_city=None, maxjump=35.0):
    """seq: 지명 목록. 반환: [(이름, lon, lat, 찾은 정류장 이름)]와 못 찾은 이름"""
    res, miss = [], []
    prev = None
    for name in seq:
        cs = cands(name)
        if not cs: miss.append(name); continue
        if prev is None:
            if first_city:
                # 첫 지점은 기점 시·군 중심에서 18km 안에서만 찾는다(같은 이름의 다른 지역을 잡지 않게).
                # 전국 정류장 파일의 도시명은 정류장을 관리하는 BIS 이름이라 위치 판정에 쓰지 않는다.
                cen = CENTER.get(first_city[:-1] if first_city[-1] in '시군' else first_city)
                c2 = [c for c in cs if cen and km((c[0], c[1]), cen) < 18] if cen else [c for c in cs if first_city in c[2]]
                if not c2:
                    miss.append(name + '(시·군 밖)'); continue
                cs = c2
            c = cs[0] if len(cs) == 1 else None
            if c is None:
                # 같은 이름이 여러 곳이면, 다음 지명들과 가장 잘 이어지는 것을 고른다
                nxt = [cands(x) for x in seq[seq.index(name) + 1: seq.index(name) + 4]]
                nxt = [x for x in nxt if x]
                def sc(c):
                    return sum(min(km((c[0], c[1]), (d[0], d[1])) for d in x) for x in nxt) if nxt else 0
                c = min(cs, key=sc)
        else:
            c = min(cs, key=lambda c: km((c[0], c[1]), prev))
            if km((c[0], c[1]), prev) > maxjump: miss.append(name + '(멂)'); continue
        res.append((name, c[0], c[1], c[3])); prev = (c[0], c[1])
    # 같은 이름의 엉뚱한 정류장(다른 시의 '현대아파트입구' 등)을 거른다: 앞뒤 점 사이로 크게 돌아가게 만드는 점은 뺀다
    changed = True
    while changed and len(res) > 2:
        changed = False
        for i in range(1, len(res) - 1):
            p, n, q = res[i - 1][1:3], res[i][1:3], res[i + 1][1:3]
            if km(p, n) + km(n, q) > 1.5 * km(p, q) + 2.0:
                miss.append(res[i][0] + '(돌아감)'); del res[i]; changed = True; break
    return res, miss

def split_route(r):
    """'A - B → C ← D' 꼴을 지명 목록으로. 한쪽 방향(→)만 있는 구간은 → 쪽을 따른다."""
    r = re.sub(r'\[.*?\]', '', r)
    r = r.split('이후 역순')[0]
    parts = re.split(r'\s+[-→↔]\s+|\s*→\s*', r)
    out = []
    for p in parts:
        p = p.strip(' .')
        if '←' in p: p = p.split('←')[0].strip()
        if not p or len(p) > 30: continue
        for q in re.split(r',\s*', p):
            q = q.strip()
            if q: out.append(q); break
    return out
