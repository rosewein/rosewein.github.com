"""없어진 광역버스(나무위키 폐선 문서의 기점–경유지–종점 글)를 정류장 이름 → 좌표 → 버스 도로 그래프 경로로 바꾼다.
결과: routes_closed.json(노선 메타·찾은 점), paths_closed.pkl(노드 경로)"""
import json, re, pickle, sys
sys.path.insert(0, '/home/claude/sudo2/bus')
import geo_names as g

ROAD = re.compile(r'(고속도로|고속화도로|국지도|국도|대로$|로$|JC$|TG$|톨게이트|영업소|IC$|IC\)|나들목|대교$|교차로$|지하차도|고가차도|터널$)')
def city_of(a):
    if '강화군' in a: return '강화군'
    m = re.search(r'(서울특별시|인천광역시)|([가-힣]+[시군])\s', a + ' ')
    if not m: return None
    s = m.group(1) or m.group(2)
    return {'서울특별시': '서울', '인천광역시': '인천'}.get(s, s.replace('경기도', ''))

def run(entries):
    import busroute as br
    out, paths = [], {}
    for e in entries:
        names = [x for x in g.split_route(e['r'].replace('. ', ' - ')) if not ROAD.search(x)]
        res, miss = g.locate(names, city_of(e['a']))
        if len(res) < 3:
            print('SKIP', e['k'], len(res), miss); continue
        pts = [(x, y) for _, x, y, _ in res]
        path, breaks = br.route_seq(pts)
        rid = 'X' + re.sub(r'\W', '', e['k'])
        paths[rid] = dict(path=path, breaks=breaks)
        out.append(dict(id=rid, name=e['n'], o=res[0][3], e=res[-1][3], pts=[[round(x, 6), round(y, 6)] for x, y in pts],
                        reg=e.get('reg', '경기'), y=e['y'], z=e['z'], src=e['src'], note=e.get('note'), how=e.get('how'), miss=miss, found=[r[0] + '→' + r[3] for r in res]))
        print(e['k'], 'pts', len(res), 'miss', len(miss), miss[:6], 'breaks', breaks, 'undirected', br.undirected[0])
    return out, paths

if __name__ == '__main__':
    inp = sys.argv[1] if len(sys.argv) > 1 else '/home/claude/sudo2/bus/closed/new_closed.json'
    tag = sys.argv[2] if len(sys.argv) > 2 else 'closed'
    E = json.load(open(inp))
    out, paths = run(E)
    json.dump(out, open(f'/home/claude/sudo2/bus/closed/routes_{tag}.json', 'w'), ensure_ascii=False)
    pickle.dump(paths, open(f'/home/claude/sudo2/bus/closed/paths_{tag}.pkl', 'wb'))
