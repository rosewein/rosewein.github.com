import json, time, pickle, sys
import busroute as B
rs = json.load(open('/home/claude/sudo2/bus/routes_gg.json'))
PART = int(sys.argv[1]); rs = rs[PART::2]
out = {}
t = time.time()
for i, r in enumerate(rs):
    p, b = B.route_seq([tuple(x) for x in r['pts']])
    out[r['id']] = dict(path=p, breaks=b)
    if i % 25 == 0: print(i, r['name'], round(time.time() - t), 's', 'breaks', b, flush=True)
pickle.dump(out, open(f'/home/claude/sudo2/bus/paths_gg_{PART}.pkl', 'wb'))
print('done', round(time.time() - t))
