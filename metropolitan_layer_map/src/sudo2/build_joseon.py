# 조선 후기 대로(수도권): 서울 안은 「서울 도시 연대지도」 joseon.json의 선을 그대로 쓰고,
# 서울 밖은 경유지를 지금 도로(OSM trunk·primary·secondary·tertiary·unclassified, 자동차전용도로 제외) 위 최단 경로로 잇는다.
# 경유지 자리: 국사편찬위원회 HGIS 1912–1914년 동리·부군 포인트(그 이름을 가진 마을 자리). 몇 곳은 어림(추정).
import json, math
import numpy as np
from scipy.sparse import csr_matrix
from scipy.sparse.csgraph import dijkstra
from scipy.spatial import cKDTree
from shapely.geometry import LineString

SJ = json.load(open('/home/claude/repo/rg/seoul-layer-map/data/joseon.json'))
SR = {r['id']: r for r in SJ['roads']}
HG = 'HGIS 1912–1914 동리'
# 경유지: id -> (lat, lng, 이름, 자리 잡은 법, 종류)
W = {
 'gupabal': (37.63548, 126.91816, '구파발', '서울 지도 경유지', '경유지'),
 'goyang': (37.7063, 126.8994, '고양 읍치(벽제)', 'HGIS 1910 고양군 포인트', '읍치'),
 'hyeeum': (37.7300, 126.8903, '혜음령', 'OSM 혜음로 위 고개 마루 언저리(어림, 추정)', '고개'),
 'yongmi': (37.7440, 126.8868, '용미리(쌍미륵)', f'{HG} 파주군 광탄면 용미리(1914)', '경유지'),
 'bunsu': (37.7670, 126.8599, '분수원', f'{HG} 파주군 광탄면 분수원', '원'),
 'paju': (37.8328, 126.8222, '파주 읍치', f'{HG} 파주군 주내면 파주리(1914)', '읍치'),
 'imjin': (37.8889, 126.7991, '임진나루', f'{HG} 파주군 신속면 임진리', '나루'),
 'dongpa': (37.9037, 126.7993, '동파역', f'{HG} 장단군 진동면 동파리', '역'),
 'jangdan': (37.9376, 126.7537, '장단 읍치', f'{HG} 장단군 군내면 읍내리(1914)', '읍치'),
 'gaeseong': (37.9735, 126.5510, '개성', 'HGIS 1910 개성군 포인트', '읍치'),
 'nuwon': (37.68926, 127.04099, '누원(다락원)', '서울 지도 경유지', '원'),
 'nogyang': (37.7604, 127.0367, '녹양역', f'{HG} 양주군 시북면 녹양리', '역'),
 'chukseok': (37.7776, 127.1146, '축석령', 'OSM 축석령 지명 점', '고개'),
 'songu': (37.8288, 127.1499, '송우리', f'{HG} 포천군 소흘면 송우리(1914)', '경유지'),
 'pocheon': (37.8882, 127.2177, '포천 읍치', 'HGIS 1910 포천군 군내면 포인트', '읍치'),
 'yangmun': (38.0009, 127.2422, '양문역', f'{HG} 영평군 군내면 양문리', '역'),
 'mangu': (37.60167, 127.11554, '망우리고개', '서울 지도 경유지', '고개'),
 'pyeonggu': (37.5925, 127.1983, '평구역', f'{HG} 양주군 금촌면 삼패리', '역'),
 'bongan': (37.5297, 127.2853, '봉안역', f'{HG} 양주군 초부면 봉안리', '역'),
 'yongjin': (37.5367, 127.3304, '용진나루', f'{HG} 양평군 서중면 용진리', '나루'),
 'yanggeun': (37.4908, 127.4951, '양근 읍치', f'{HG} 양평군 갈산면 양근리(1914)', '읍치'),
 'jipyeong': (37.4777, 127.6414, '지평 읍치', f'{HG} 양평군 지제면 지평리(1914)', '읍치'),
 'dallae': (37.43945, 127.06088, '달래내고개', '서울 지도 경유지', '고개'),
 'pangyo': (37.3904, 127.0996, '판교(낙생)', f'{HG} 광주군 낙생면 판교리', '경유지'),
 'yongin': (37.2946, 127.1317, '용인 읍치(구성)', f'{HG} 용인군 읍삼면 언남리(1914)', '읍치'),
 'gimnyang': (37.2372, 127.2117, '김량장', f'{HG} 용인군 수여면 김량장리(1914)', '경유지'),
 'yangji': (37.2381, 127.2864, '양지 읍치', 'HGIS 1910 양지군 포인트', '읍치'),
 'geunchang': (37.1605, 127.3538, '백암 근창리', f'{HG} 용인군 외사면 근창리(1914)', '경유지'),
 'juksan': (37.0776, 127.4204, '죽산 읍치', 'HGIS 1910 죽산군 포인트', '읍치'),
 'namtae': (37.4650, 126.9879, '남태령', '서울 지도 경유지', '고개'),
 'namtae2': (37.45872, 126.98957, '남태령 마루', 'OSM 남태령고개 지명 점', '고개'),
 'gwanmun': (37.44645, 126.99563, '관문사거리', 'OSM 관문사거리 지명 점. 서울신문 2007-12-31 「옛길은 과천 관문사거리에서 남태령 고개로 향한다」', '경유지'),
 'gwacheon': (37.43387, 126.98739, '과천향교(과천 읍치 언저리)', 'OSM 과천향교 지명 점. 경기옛길 삼남길 한양관문길(남태령–온온사–과천향교–인덕원터)', '읍치'),
 'indeok': (37.40227, 126.9766, '인덕원', 'OSM 인덕원사거리 지명 점(인덕원 옛길터 표석 언저리)', '원'),
 'sageun': (37.3498, 126.9740, '사근평(고천)', f'{HG} 수원군 의왕면 고천리(1914)', '경유지'),
 'jiji': (37.3157, 126.9905, '지지대고개', '어림(추정)', '고개'),
 'suwon': (37.2835, 127.0128, '수원(화성)', 'HGIS 1910 수원군 포인트', '읍치'),
 'daehwang': (37.2269, 127.0191, '대황교', f'{HG} 수원군 안녕면 대황교', '경유지'),
 'cheongho': (37.1298, 127.0825, '청호', f'{HG} 진위군 일북면 청호리', '경유지'),
 'jinwi': (37.1012, 127.0897, '진위 읍치', 'HGIS 1910 진위군 포인트', '읍치'),
 'galwon': (37.0321, 127.1006, '갈원(칠원)', f'{HG} 진위군 여방면 칠원리', '원'),
 'yeomchang': (37.55442, 126.87369, '염창리', '서울 지도 경유지', '경유지'),
 'yangcheon': (37.5713, 126.8414, '양천 읍치', f'{HG} 양천군 군내면 가양동', '읍치'),
 'gimpo': (37.6250, 126.7076, '김포 읍치', f'{HG} 김포군 군내면 북변리', '읍치'),
 'tongjin': (37.7159, 126.5573, '통진 읍치', f'{HG} 통진군 군내면 군하리', '읍치'),
 'munsu': (37.7315, 126.5300, '문수산 아래 나루(김포 쪽)', '어림(추정)', '나루'),
 'gapgot': (37.7334, 126.5178, '갑곶나루', f'{HG} 강화군 장령면 갑곶동', '나루'),
 'ganghwa': (37.7536, 126.4861, '강화부', f'{HG} 강화군 부내면 관청리(1914)', '읍치'),
 'songpa': (37.51024, 127.10074, '송파나루', '서울 지도 경유지', '나루'),
 'gyeongan': (37.3945, 127.2321, '경안', 'HGIS 1910 광주군 경안면 포인트', '경유지'),
 'icheon': (37.2800, 127.4251, '이천 읍치', f'{HG} 이천군 읍내면 관고리(1914)', '읍치'),
}
SEOUL_KEEP = {'gupabal', 'nuwon', 'mangu', 'dallae', 'namtae', 'yeomchang', 'songpa'}
GG = 'https://www.gg.go.kr/myggd/oldstreet.html'
# 노선: (서울 지도 노선 id, 이름, 번호, 서울 밖 경유지, 근거[(이름,주소)], 확인 정도, 메모)
ROADS = [
 ('r1', '의주대로', '제1로', ['gupabal', 'goyang', 'hyeeum', '*bunsu', 'paju', 'imjin', '~dongpa', '=jangdan', 'gaeseong'],
  [('경기옛길 의주길 5개 구간(벽제관길·고양관청길·쌍미륵길·파주고을길·임진나루길), 경기일보 연재', 'https://kyeonggi.com/seriesList/005521')], '중간', '임진나루에서 동파역까지는 나룻배. 동파역–장단은 지금 비무장지대라 곧은 선. 분수원은 점만 찍고 선은 혜음로를 따름. 장단을 거쳐 개성까지 그림'),
 ('r2', '경흥대로', '제2로', ['nuwon', 'nogyang', 'chukseok', 'songu', 'pocheon', 'yangmun'],
  [('경기옛길 경흥길(사패산길·반월산성길·영평팔경길 등), 경기도 소식지', GG)], '낮음', '양문역(영평)에서 그침. 축석령 자리는 어림'),
 ('r3', '평해대로', '제3로', ['mangu', 'pyeonggu', 'bongan', '~yongjin', 'yanggeun', 'jipyeong'],
  [('경기옛길 평해길(망우왕숙길·두물머리나루길·물끝길·지평향교길), 경기도 소식지', GG)], '낮음', '봉안역에서 북한강을 건너 용진나루로 가는 길은 나룻배로 그림. 지평에서 그침'),
 ('r4', '영남대로', '제4로', ['dallae', 'pangyo', 'yongin', 'gimnyang', 'yangji', 'geunchang', 'juksan'],
  [('서울신문 2006-10-02 「부산에서 서울까지 다시 걷는 옛길」 용인길(죽산–양지–용인향교–판교)', 'https://m.seoul.co.kr/news/2006/10/02/20061002014001'),
   ('경기옛길 영남길(성남·용인·안성·이천 10구간), 경기도 소식지', 'https://www.gg.go.kr/myggd/vol168/sub3_1.html')], '중간', '죽산에서 그침. 양지–죽산 사이는 백암을 지나는 것으로 잡음(추정)'),
 ('r5', '삼남대로', '제5로', ['namtae', '=namtae2', 'gwanmun', 'gwacheon', 'indeok', 'sageun', 'jiji', 'suwon', 'daehwang', 'cheongho', 'jinwi', 'galwon'],
  [('서울신문 2007-12-31 「땅끝마을에서 한양까지 다시 걷는 옛길」 수원~과천 남태령', 'https://m.seoul.co.kr/news/2007/12/31/20071231016003'),
   ('경기옛길 삼남길(평택–오산–화성–수원–의왕–안양–과천), 경기도 소식지', 'https://www.gg.go.kr/myggd/vol174/sub3_1.html')], '중간', '갈원(평택 칠원)에서 그침'),
 ('r6', '강화대로', '제6로', ['yeomchang', 'yangcheon', 'gimpo', 'tongjin', 'munsu', '~gapgot', 'ganghwa'],
  [('경기옛길 강화길(금릉옛길 등), 경기도 소식지', 'https://www.gg.go.kr/myggd/vol171/sub3_1.html')], '낮음', '문수산 아래에서 갑곶나루까지 나룻배. 김포 쪽 나루 자리는 어림'),
 ('r4c', '봉화로', '『대동지지』 10대로', ['songpa', 'gyeongan', 'icheon'],
  [('경기옛길 봉화길(「대동지지」 10대로 중 봉화로, 한양–광주–이천–충주), 경기도 소식지', 'https://www.gg.go.kr/myggd/vol176/sub3_1.html')], '낮음', '서울 안은 「광주로(송파)」 선. 송파–경안–이천 경유는 추정'),
]

# ---- 도로 그래프 ----
COST = {'trunk': 1.15, 'primary': 1.0, 'secondary': 1.0, 'tertiary': 1.0, 'unclassified': 1.1}
idx = {}; xs = []; ys = []; U = []; V = []; Wt = []; MR = set(); MAJ = set()
def nid(c):
    k = (round(c[0], 6), round(c[1], 6))
    i = idx.get(k)
    if i is None:
        i = idx[k] = len(xs); xs.append(k[0]); ys.append(k[1])
    return i
COST['track'] = 1.3; COST['residential'] = 1.4; COST['living_street'] = 1.5
import itertools
for ln in itertools.chain(open('/home/claude/raw/osm/rd.geojsonseq'), open('/home/claude/raw/osm/kprd.geojsonseq'), open('/home/claude/raw/osm/res.geojsonseq')):
    ln = ln.strip('\x1e\n ')
    if not ln: continue
    f = json.loads(ln); p = f['properties']; g = f['geometry']
    if g['type'] != 'LineString': continue
    hw = p.get('highway'); cf = COST.get(hw)
    if cf is None: continue
    if p.get('motorroad') == 'yes': cf = 2.0   # 자동차전용도로는 되도록 피함
    cs = g['coordinates']
    for a, b in zip(cs, cs[1:]):
        ia, ib = nid(a), nid(b)
        d = math.hypot((a[0] - b[0]) * 88.4, (a[1] - b[1]) * 111.0)
        U.append(ia); V.append(ib); Wt.append(d * cf)
        if cf == 2.0: MR.add(ia); MR.add(ib)
        if hw in ('trunk', 'primary', 'secondary', 'tertiary'): MAJ.add(ia); MAJ.add(ib)
N = len(xs); xs = np.array(xs); ys = np.array(ys)
# OSM에서 맞닿았지만 노드를 같이 쓰지 않는 곳을 12m 안이면 잇는다(조금 비싸게)
_TT = cKDTree(np.c_[xs * 88.4, ys * 111.0])
_pr = _TT.query_pairs(r=0.012, output_type='ndarray')
_d = np.hypot((xs[_pr[:, 0]] - xs[_pr[:, 1]]) * 88.4, (ys[_pr[:, 0]] - ys[_pr[:, 1]]) * 111.0)
U += list(_pr[:, 0]); V += list(_pr[:, 1]); Wt += list(_d * 1.5 + 0.01)
print('bridging pairs', len(_pr))
G = csr_matrix((np.r_[Wt, Wt], (np.r_[U, V], np.r_[V, U])), shape=(N, N))
from scipy.sparse.csgraph import connected_components
nc, lab = connected_components(G, directed=False)
big = np.bincount(lab).argmax(); keep = np.array([i for i in np.where(lab == big)[0] if i not in MR and i in MAJ])
print('components', nc, 'largest', len(keep))
T0 = cKDTree(np.c_[xs[keep] * 88.4, ys[keep] * 111.0])
class _T:
    def query(self, q):
        d, i = T0.query(q); return d, keep[i]
T = _T()
_ka = np.array([i for i in np.where(lab == big)[0] if i in MAJ]); _TA0 = cKDTree(np.c_[xs[_ka] * 88.4, ys[_ka] * 111.0])
class _TA:
    def query(self, q):
        d, i = _TA0.query(q); return d, _ka[i]
TA = _TA()
ALLMR = {'namtae', 'namtae2', 'gwanmun'}   # 남태령 고갯길(과천대로)은 자동차전용도로라 이 점들은 그 위에도 붙임
print('graph nodes', N, 'edges', len(U))
def snap(la, lo, allmr=False):
    d, i = (TA if allmr else T).query((lo * 88.4, la * 111.0)); return int(i), d
def route(a, b, ka='', kb=''):
    (sa, da), (sb, db) = snap(a[0], a[1], ka in ALLMR), snap(b[0], b[1], kb in ALLMR)
    dist, pred = dijkstra(G, indices=sa, return_predecessors=True, limit=150)
    if not np.isfinite(dist[sb]): return [[a[1], a[0]], [b[1], b[0]]], None, (da, db)
    seq = [sb]
    while seq[-1] != sa: seq.append(pred[seq[-1]])
    seq = seq[::-1]
    pts = [[a[1], a[0]]] + [[float(xs[i]), float(ys[i])] for i in seq] + [[b[1], b[0]]]
    straight = math.hypot((a[1] - b[1]) * 88.4, (a[0] - b[0]) * 111.0)
    return pts, dist[sb] / max(straight, 0.05), (round(da, 2), round(db, 2))
def simp(pts, tol=0.00012):
    ls = LineString(pts).simplify(tol, preserve_topology=False)
    return [[round(x, 5), round(y, 5)] for x, y in ls.coords]

out = {'roads': [], 'pts': []}
seen = set()
for sid, name, no, legs, srcs, conf, note in ROADS:
    s = SR[sid]
    segs = [dict(sg, seoul=True) for sg in s['segs']]
    via = list(s['via'])
    cur = None; rep = []
    for k, step in enumerate([l for l in legs if not l.startswith('*')]):
        ferry = step.startswith('~'); key = step.lstrip('~=')
        if k == 0: cur = key; continue
        a, b = W[cur], W[key]
        if step.startswith('='):   # 0.7km 고갯길: 곧은 선으로 이음
            segs.append({'p': [[round(a[1], 5), round(a[0], 5)], [round(b[1], 5), round(b[0], 5)]]})
        elif ferry:
            segs.append({'ferry': True, 'p': [[round(a[1], 5), round(a[0], 5)], [round(b[1], 5), round(b[0], 5)]]})
        else:
            pts, ratio, snapd = route(a, b, cur, key)
            rep.append((cur, key, None if ratio is None else round(ratio, 2), snapd))
            segs.append({'p': simp(pts)})
        via.append(W[key][2]); cur = key
    via = list(s['via']) + [W[l.lstrip('~=*')][2] for l in legs[1:]]
    for st in legs:
        key = st.lstrip('~=*')
        if key in SEOUL_KEEP or key in seen: continue
        seen.add(key); la, lo, nm, pos, kind = W[key]
        out['pts'].append({'n': nm, 'k': kind, 'x': lo, 'y': la, 'pos': pos, 'r': name})
    out['roads'].append({'name': name, 'no': no, 'segs': segs, 'via': via, 'src': [[a, b] for a, b in srcs],
                         'seoul_src': s['src'], 'conf': conf, 'note': note})
    print(name, rep)
# 서울 지도 점(역·원·나루·문)
for p in SJ['points']:
    out['pts'].append({'n': p['name'], 'k': p['kind'], 'x': p['lng'], 'y': p['lat'], 'pos': p.get('pos', ''), 'src': p.get('src', ''), 'seoul': True})
json.dump(out, open('/home/claude/sudo2/joseon_sudo.json', 'w'), ensure_ascii=False, separators=(',', ':'))
print('pts', len(out['pts']), 'bytes', len(json.dumps(out, ensure_ascii=False, separators=(',', ':'))))
