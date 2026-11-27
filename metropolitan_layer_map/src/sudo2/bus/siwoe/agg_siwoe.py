"""신문 기사로 확인한 1960–80년대 시외버스 노선(서울 터미널–경기·인천)을 노선마다 따로 그릴 선으로 바꿔 page data.json의 sw에 넣는다"""
import json, pickle, numpy as np, shapely
Z = np.load('/home/claude/sudo2/bus/busgraph.npz'); X, Y = Z['x'], Z['y']
R = json.load(open('/home/claude/sudo2/bus/closed/routes_siwoe.json'))
import re
EN = {'X' + re.sub(r'\W', '', e['k']): e for e in json.load(open('/home/claude/sudo2/bus/siwoe/siwoe_entries.json'))}
P = pickle.load(open('/home/claude/sudo2/bus/closed/paths_siwoe.pkl', 'rb'))
out = []
for r in R:
    p = [n for n in P[r['id']]['path'] if n >= 0]
    ls = shapely.LineString([(X[i], Y[i]) for i in p]).simplify(0.00008)
    w = [x.strip() for x in EN[r['id']]['r'].split(' - ')]
    out.append(dict(n=EN[r['id']]['n'], o=w[0], e=w[-1], y=r['y'], z=r['z'], src=r['src'], nt=r.get('note'),
                    p=[[round(x, 5), round(y, 5)] for x, y in ls.coords]))
pg = '/home/claude/sudo/page/data.json'
s = open(pg, encoding='utf-8').read(); D = json.loads(s)
D['sw'] = out
sep = (',', ':') if '", "' not in s[:2000] else None
open(pg, 'w', encoding='utf-8').write(json.dumps(D, ensure_ascii=False, separators=sep))
print(len(out), sum(len(o['p']) for o in out), 'pts')
