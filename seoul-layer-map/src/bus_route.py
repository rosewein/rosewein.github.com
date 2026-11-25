"""버스 노선 경유지를 OSM 도로망 위 최단 경로로 잇고, 2004년 6월 노선망의 구간별 노선 수를 센다."""
import json, math, sys, collections, numpy as np
from scipy.sparse import csr_matrix
from scipy.sparse.csgraph import dijkstra
from scipy.spatial import cKDTree
from shapely.geometry import LineString, MultiLineString
from shapely.ops import linemerge

B = "/home/claude/data/build"
R = np.load("/home/claude/data/osm/seoul/roads.npz")
lon, lat, u, v, d, c, cost = R["lon"], R["lat"], R["u"], R["v"], R["d"], R["c"], R["cost"]
N = len(lon)
w = d * cost[c]
G = csr_matrix((np.concatenate([w, w]), (np.concatenate([u, v]), np.concatenate([v, u]))), shape=(N, N))
XY = np.c_[lon * 88.4, lat * 111.0]
major = np.zeros(N, bool)
mm = c <= 9  # tertiary_link까지
major[u[mm]] = True; major[v[mm]] = True
maj_idx = np.where(major)[0]
T_major = cKDTree(XY[maj_idx]); T_all = cKDTree(XY)

def snap(x, y):
    p = (x * 88.4, y * 111.0)
    dm, im = T_major.query(p)
    if dm <= 0.5: return int(maj_idx[im])
    da, ia = T_all.query(p)
    if da <= 0.4: return int(ia)
    return None

bus = json.load(open(f"{B}/bus.json"))
routes = bus["routes"]
pairs = collections.defaultdict(dict)  # src -> {dst: limit}
legs = []
for ri, rt in enumerate(routes):
    sn = [snap(x, y) for x, y in rt["pts"]]
    L = []
    for k in range(len(sn) - 1):
        a, b = sn[k], sn[k + 1]
        pa, pb = rt["pts"][k], rt["pts"][k + 1]
        straight = math.hypot((pa[0] - pb[0]) * 88.4, (pa[1] - pb[1]) * 111.0)
        L.append((a, b, straight, pa, pb))
        if a is not None and b is not None and a != b:
            lim = max(3.0 * straight + 2.0, 4.0)
            pairs[a][b] = max(pairs[a].get(b, 0), lim)
    legs.append(L)
print("routes", len(routes), "unique sources", len(pairs), file=sys.stderr)

paths = {}
for i, (src, tg) in enumerate(pairs.items()):
    lim = max(tg.values())
    dist, pred = dijkstra(G, indices=src, limit=lim, return_predecessors=True)
    for dst in tg:
        if not np.isfinite(dist[dst]): continue
        seq = [dst]
        while seq[-1] != src:
            p = pred[seq[-1]]
            if p < 0: seq = None; break
            seq.append(p)
        if seq: paths[(src, dst)] = (seq[::-1], float(dist[dst]))
    if i % 300 == 0: print(" ..", i, file=sys.stderr)

def plen(seq):
    return sum(math.hypot(XY[seq[j + 1], 0] - XY[seq[j], 0], XY[seq[j + 1], 1] - XY[seq[j], 1]) for j in range(len(seq) - 1))

usage = collections.Counter()
stat = collections.Counter()
edge_routes = collections.defaultdict(set)
for ri, (rt, L) in enumerate(zip(routes, legs)):
    coords = []; edges = set()
    for a, b, straight, pa, pb in L:
        seq = paths.get((a, b)) if a is not None and b is not None and a != b else None
        if seq and plen(seq[0]) <= max(2.6 * straight, straight + 1.5):
            seq = seq[0]
            seg = [[float(lon[n]), float(lat[n])] for n in seq]
            for j in range(len(seq) - 1):
                edges.add((min(seq[j], seq[j + 1]), max(seq[j], seq[j + 1])))
            stat["road"] += 1
        else:
            seg = [pa, pb]; stat["straight"] += 1
        coords.extend(seg if not coords else seg[1:])
    if len(coords) >= 2:
        g = LineString(coords).simplify(0.00012)
        rt["geom"] = [[round(x, 5), round(y, 5)] for x, y in g.coords]
    if rt["live"]:
        for e in edges: usage[e] += 1
    for e in edges: edge_routes[e].add(ri)
print("legs on roads", stat["road"], "straight fallback", stat["straight"], file=sys.stderr)

# 구간별 노선 수 → 굵기 단계별 선
BK = [(1, 1), (2, 3), (4, 7), (8, 12), (13, 20), (21, 999)]
corr = []
for lo, hi in BK:
    segs = [LineString([(lon[a], lat[a]), (lon[b], lat[b])]) for (a, b), n in usage.items() if lo <= n <= hi]
    if not segs: continue
    merged = linemerge(MultiLineString(segs))
    geoms = list(merged.geoms) if hasattr(merged, "geoms") else [merged]
    lines = []
    for g in geoms:
        g = g.simplify(0.00008)
        lines.append([[round(x, 5), round(y, 5)] for x, y in g.coords])
    corr.append({"lo": lo, "hi": hi, "lines": lines})
    print(f" bucket {lo}-{hi}: {len(segs)} edges -> {len(lines)} lines", file=sys.stderr)
bus["corr"] = corr
groups = collections.defaultdict(list)
for e, rs in edge_routes.items(): groups[frozenset(rs)].append(e)
segs = []
for rs, es in groups.items():
    merged = linemerge(MultiLineString([LineString([(lon[a], lat[a]), (lon[b], lat[b])]) for a, b in es]))
    geoms = list(merged.geoms) if hasattr(merged, "geoms") else [merged]
    segs.append({"r": sorted(rs), "g": [[[round(x, 5), round(y, 5)] for x, y in gg.simplify(0.00008).coords] for gg in geoms]})
bus["segs"] = segs
print("segments", len(segs), "groups", len(groups), file=sys.stderr)
for rt in routes: rt.pop("pts_raw", None)
json.dump(bus, open(f"{B}/bus.json", "w"), ensure_ascii=False, separators=(",", ":"))
print("max routes on one edge:", max(usage.values()), "bus.json bytes:", len(json.dumps(bus, ensure_ascii=False, separators=(",", ":"))), file=sys.stderr)
