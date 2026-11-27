import json, pickle, sys, time
import busroute as B
P = pickle.load(open('/home/claude/sudo2/bus/paths_gg_0.pkl', 'rb'))
P.update(pickle.load(open('/home/claude/sudo2/bus/paths_gg_1.pkl', 'rb')))
ch = set(json.load(open('/tmp/rerun_gg.json')))
rs = json.load(open('routes_gg.json')) + json.load(open('routes_ic.json')) + json.load(open('routes_se.json'))
t = time.time(); n = 0
for r in rs:
    if r['id'] in ch or r['id'] not in P:
        p, b = B.route_seq([tuple(x) for x in r['pts']]); P[r['id']] = dict(path=p, breaks=b); n += 1
        if b: print('break', r['name'], b, flush=True)
pickle.dump(P, open('/home/claude/sudo2/bus/paths_all.pkl', 'wb'))
print('routed', n, round(time.time() - t))
