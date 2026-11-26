"""2026년 11월 18일 버스 승하차 자료(정류장 순번 포함)로 지금 노선망을 도로 위에 그린다."""
import csv, io, json, math, re, sys, collections, numpy as np
from scipy.sparse import csr_matrix
from scipy.sparse.csgraph import dijkstra
from scipy.spatial import cKDTree
from shapely.geometry import LineString, MultiLineString
from shapely.ops import linemerge

from paths import CODE, DATA, RAW, WORK
B = DATA
RIDE = f"{RAW}/bus/ride/ride_20261118.csv"
R = np.load(f"{RAW}/osm/seoul/roads.npz")
lon, lat, u, v, d, c, cost = R["lon"], R["lat"], R["u"], R["v"], R["d"], R["c"], R["cost"]
N = len(lon)
w = d * cost[c]
G = csr_matrix((np.concatenate([w, w]), (np.concatenate([u, v]), np.concatenate([v, u]))), shape=(N, N))
XY = np.c_[lon * 88.4, lat * 111.0]
major = np.zeros(N, bool); mm = c <= 9; major[u[mm]] = True; major[v[mm]] = True
maj_idx = np.where(major)[0]
T_major = cKDTree(XY[maj_idx]); T_all = cKDTree(XY)

def snap(x, y):
    p = (x * 88.4, y * 111.0)
    da, ia = T_all.query(p)
    dm, im = T_major.query(p)
    if dm <= 0.12 or (dm <= 0.35 and da > 0.05): return int(maj_idx[im])
    if da <= 0.3: return int(ia)
    return None

stops = {s["node_id"]: s for s in csv.DictReader(open(f"{RAW}/bus/raw/seoul_bus_stops.csv"))}
rtype = {r["route_no"]: r["route_type"] for r in csv.DictReader(open(f"{RAW}/bus/raw/seoul_bus_routes.csv"))}
rows = list(csv.reader(io.StringIO(open(RIDE, "rb").read().decode("cp949"))))[1:]
by = collections.defaultdict(list)
names = {}
for r in rows:
    m = re.search(r"\((\d{5})\)\s*$", r[5])
    if not m: continue
    by[(r[1], r[2])].append((int(m.group(1)), r[3], re.sub(r"\(\d{5}\)\s*$", "", r[5]), int(r[6] or 0), int(r[7] or 0)))
    names[(r[1], r[2])] = r[2]

routes, legs = [], []
pairs = collections.defaultdict(dict)
SKIP_TYPES = {"village"}  # 2004년 단면(시내버스만)과 맞추려고 마을버스는 뺀다
skipped = 0
for key, lst in by.items():
    no = key[0]
    if rtype.get(no, "") in SKIP_TYPES:
        skipped += 1; continue
    lst.sort()
    pts = []
    for seq, nid, nm, on, off in lst:
        s = stops.get(nid)
        if not s: continue
        x, y = float(s["lng"]), float(s["lat"])
        if pts and pts[-1][3] == nid: continue
        pts.append((x, y, nm, nid, on + off))
    if len(pts) < 2: continue
    sn = [snap(x, y) for x, y, *_ in pts]
    L = []
    for k in range(len(pts) - 1):
        a, b = sn[k], sn[k + 1]
        st = math.hypot((pts[k][0] - pts[k + 1][0]) * 88.4, (pts[k][1] - pts[k + 1][1]) * 111.0)
        L.append((a, b, st, pts[k][:2], pts[k + 1][:2]))
        if a is not None and b is not None and a != b and st < 6:
            pairs[a][b] = max(pairs[a].get(b, 0), 3 * st + 1.0)
    routes.append({"no": no, "name": re.sub(r"^\S+번\(", "", names[key]).rstrip(")"), "type": rtype.get(no, ""),
                   "riders": sum(p[4] for p in pts), "stops": [(round(p[0], 5), round(p[1], 5), p[2]) for p in pts]})
    legs.append(L)
print("routes", len(routes), "skipped village", skipped, "unique sources", len(pairs), file=sys.stderr)

paths = {}
for i, (src, tg) in enumerate(pairs.items()):
    dist, pred = dijkstra(G, indices=src, limit=max(tg.values()), return_predecessors=True)
    for dst in tg:
        if not np.isfinite(dist[dst]): continue
        seq = [dst]
        while seq[-1] != src:
            p = pred[seq[-1]]
            if p < 0: seq = None; break
            seq.append(p)
        if seq: paths[(src, dst)] = seq[::-1]
    if i % 2000 == 0: print(" ..", i, file=sys.stderr)

def plen(seq):
    return sum(math.hypot(XY[seq[j + 1], 0] - XY[seq[j], 0], XY[seq[j + 1], 1] - XY[seq[j], 1]) for j in range(len(seq) - 1))

usage = collections.Counter(); stat = collections.Counter()
edges_by_no = collections.defaultdict(set)
for rt, L in zip(routes, legs):
    coords, edges = [], set()
    for a, b, st, pa, pb in L:
        seq = paths.get((a, b)) if a is not None and b is not None and a != b else None
        if seq and plen(seq) <= max(2.2 * st, st + 0.8):
            seg = [[float(lon[n]), float(lat[n])] for n in seq]
            for j in range(len(seq) - 1): edges.add((min(seq[j], seq[j + 1]), max(seq[j], seq[j + 1])))
            stat["road"] += 1
        else:
            seg = [list(pa), list(pb)]; stat["straight"] += 1
            inside = all(126.58 < q[0] < 127.31 and 37.35 < q[1] < 37.72 for q in (pa, pb))
            stat["straight_inside" if inside else "straight_outside"] += 1
            if inside: stat["straight_km_inside"] += st
        coords.extend(seg if not coords else seg[1:])
    g = LineString(coords).simplify(0.00012)
    rt["geom"] = [[round(x, 5), round(y, 5)] for x, y in g.coords]
    edges_by_no[rt["no"]] |= edges
print("legs", dict(stat), file=sys.stderr)

for es in edges_by_no.values():
    for e in es: usage[e] += 1  # 굵기 단계 corr는 2026년 노선만
# 2004년 7월 이후 없어진 노선(나무위키 폐선 문서에서 복원): 번호 자리에 "†번호#순번"으로 넣는다
import os
dead = json.load(open(f"{B}/dead_routes.json")) if os.path.exists(f"{B}/dead_routes.json") else []
dead_key = {}
for j, dr in enumerate(dead):
    key = f"†{dr['no']}#{j}"
    dead_key[key] = dr
    edges_by_no[key] = {(a, b) for a, b in dr["edges"]}
    routes.append({"no": dr["no"], "name": dr["ends"], "type": "dead", "riders": 0, "geom": dr["geom"], "dead": 1})
nums = sorted(edges_by_no)
num_idx = {n: i for i, n in enumerate(nums)}
dk = iter(sorted(dead_key, key=lambda k: int(k.split("#")[1])))
for rt in routes: rt["k"] = num_idx[next(dk)] if rt.get("dead") else num_idx[rt["no"]]
edge_nums = collections.defaultdict(set)
for n, es in edges_by_no.items():
    for e in es: edge_nums[e].add(num_idx[n])
groups = collections.defaultdict(list)
for e, ks in edge_nums.items(): groups[frozenset(ks)].append(e)
segs = []
for ks, es in groups.items():
    merged = linemerge(MultiLineString([LineString([(lon[a], lat[a]), (lon[b], lat[b])]) for a, b in es]))
    geoms = list(merged.geoms) if hasattr(merged, "geoms") else [merged]
    segs.append({"r": sorted(ks), "g": [[[round(x, 5), round(y, 5)] for x, y in gg.simplify(0.00008).coords] for gg in geoms]})
print("segments", len(segs), file=sys.stderr)
BK = [(1, 1), (2, 3), (4, 7), (8, 12), (13, 20), (21, 999)]
corr = []
for lo, hi in BK:
    bsegs = [LineString([(lon[a], lat[a]), (lon[b], lat[b])]) for (a, b), n in usage.items() if lo <= n <= hi]
    if not bsegs: continue
    merged = linemerge(MultiLineString(bsegs))
    geoms = list(merged.geoms) if hasattr(merged, "geoms") else [merged]
    corr.append({"lo": lo, "hi": hi, "lines": [[[round(x, 5), round(y, 5)] for x, y in gg.simplify(0.00008).coords] for gg in geoms]})
    print(f" bucket {lo}-{hi}: {len(bsegs)} edges", file=sys.stderr)

# 클릭용 정류장 묶음(250m 격자)
nodes = {}
for ri, rt in enumerate(routes):
    seen = set()
    for x, y, nm in rt.get("stops", []):
        k = (round(x / 0.003), round(y / 0.003))
        if k in seen: continue
        seen.add(k)
        nd = nodes.setdefault(k, {"xs": [], "ys": [], "names": collections.Counter(), "r": []})
        nd["xs"].append(x); nd["ys"].append(y); nd["names"][nm] += 1; nd["r"].append(ri)
node_list = [{"lng": round(sum(n["xs"]) / len(n["xs"]), 4), "lat": round(sum(n["ys"]) / len(n["ys"]), 4),
              "name": n["names"].most_common(1)[0][0], "r": n["r"]} for n in nodes.values()]
node_list.sort(key=lambda n: -len(n["r"]))
for rt in routes: rt.pop("stops", None)
out = {"label": "2026년 11월 노선망", "date": "2026-11-18", "routes": routes, "corr": corr, "nodes": node_list,
       "segs": segs, "nums": [({"no": dead_key[n]["no"], "oy": dead_key[n]["oy"], "cy": dead_key[n]["cy"], "dead": 1,
                                 "src": (dead_key[n]["oy_ctx"] + " / " + dead_key[n]["cy_ctx"])[:220], "head": dead_key[n]["head"],
                                 "merged_into": dead_key[n]["merged_into"]} if n in dead_key else {"no": n, "oy": None}) for n in nums]}
print("max routes on one edge", max(usage.values()), "nodes", len(node_list), "bytes", len(json.dumps(out, ensure_ascii=False, separators=(",", ":"))), file=sys.stderr)
print("busiest:", [(n["name"], len(n["r"])) for n in node_list[:10]], file=sys.stderr)
print("types:", collections.Counter(r["type"] for r in routes), file=sys.stderr)

# 2004년 7월 개편 이후 사건은 2026년 노선 번호와 잇는다(옛 번호와 겹쳐도 다른 노선이라서)
bus = json.load(open(f"{B}/bus.json"))
idx_new, idx_dead = {}, collections.defaultdict(list)
for i, rt in enumerate(routes):
    if rt.get("dead"):
        n = out["nums"][rt["k"]]
        idx_dead[rt["no"]].append((i, n["oy"], n["cy"]))
    else:
        idx_new.setdefault(rt["no"], i)
linked = 0
for e in bus["events"]:
    post = (e["y"] > 2004) or (e["y"] == 2004 and re.match(r"2004\.(0?[7-9]|1[0-2])", str(e["d"])))
    if post:
        no = re.sub(r"\s+|번", "", str(e.get("no", "")))
        e["net"] = "new"; e["ri"] = None
        cand = idx_dead.get(no, [])
        if e["t"] == "폐선" and cand:
            e["ri"] = min(cand, key=lambda c: abs((c[2] or 0) - (e["y"] + 0.5)))[0]
        elif no in idx_new:
            e["ri"] = idx_new[no]
        elif cand:
            e["ri"] = min(cand, key=lambda c: abs((c[1] or 0) - (e["y"] + 0.5)))[0]
        if e["ri"] is not None:
            linked += 1
    else:
        e["net"] = "old"
json.dump(bus, open(f"{B}/bus.json", "w"), ensure_ascii=False, separators=(",", ":"))
json.dump(out, open(f"{B}/bus2026.json", "w"), ensure_ascii=False, separators=(",", ":"))
print("post-2004 events linked to 2026 routes:", linked, "numbers with known open year:", sum(1 for n in out["nums"] if n["oy"]), file=sys.stderr)
