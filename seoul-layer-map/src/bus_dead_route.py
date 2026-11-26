"""2004년 7월 이후 없어진 노선(dead_parsed.json)의 경유지를 도로망 최단 경로로 잇는다 → dead_routes.json"""
import json, math, sys, collections, numpy as np
from scipy.sparse import csr_matrix
from scipy.sparse.csgraph import dijkstra
from scipy.spatial import cKDTree
from shapely.geometry import LineString
from paths import CODE, DATA, RAW, WORK
sys.path.insert(0, CODE)

B = DATA
R = np.load(f"{RAW}/osm/seoul/roads.npz")
lon, lat, u, v, d, c, cost = R["lon"], R["lat"], R["u"], R["v"], R["d"], R["c"], R["cost"]
N = len(lon)
w = d * cost[c]
G = csr_matrix((np.concatenate([w, w]), (np.concatenate([u, v]), np.concatenate([v, u]))), shape=(N, N))
XY = np.c_[lon * 88.4, lat * 111.0]
major = np.zeros(N, bool); mm = c <= 9; major[u[mm]] = True; major[v[mm]] = True
maj_idx = np.where(major)[0]
T_major = cKDTree(XY[maj_idx]); T_all = cKDTree(XY)
BOX = (126.64, 37.30, 127.31, 37.84)


def km(a, b):
    return math.hypot((a[0] - b[0]) * 88.4, (a[1] - b[1]) * 111.0)


def clean_pts(pts):
    """bus_build.clean_pts와 같은 규칙: 범위 밖 점과 혼자 튀는 점을 뺀다"""
    pts = [p for p in pts if BOX[0] <= p[0] <= BOX[2] and BOX[1] <= p[1] <= BOX[3]]
    changed = True
    while changed and len(pts) >= 3:
        changed = False
        for i in range(len(pts)):
            a = pts[i - 1] if i > 0 else None; b = pts[i + 1] if i + 1 < len(pts) else None
            dp = km(pts[i], a) if a else None; dn = km(pts[i], b) if b else None
            if a and b and dp > 4 and dn > 4 and km(a, b) < 0.6 * (dp + dn):
                pts.pop(i); changed = True; break
    return pts


def snap(x, y):
    p = (x * 88.4, y * 111.0)
    dm, im = T_major.query(p)
    if dm <= 0.5: return int(maj_idx[im])
    da, ia = T_all.query(p)
    if da <= 0.4: return int(ia)
    return None


def plen(seq):
    return sum(math.hypot(XY[seq[j + 1], 0] - XY[seq[j], 0], XY[seq[j + 1], 1] - XY[seq[j], 1]) for j in range(len(seq) - 1))


def main():
    D = [r for r in json.load(open(f"{RAW}/bus/namu_post/dead_parsed.json")) if not r.get("skip")]
    items = []
    pairs = collections.defaultdict(dict)
    for r in D:
        pts = clean_pts([(p["lng"], p["lat"]) for p in r["pts"] if p["lng"]])
        # 같은 자리 겹친 점 정리
        q = []
        for p in pts:
            if not q or km(q[-1], p) > 0.05: q.append(p)
        if len(q) < 2: continue
        sn = [snap(x, y) for x, y in q]
        L = []
        for k in range(len(q) - 1):
            a, b = sn[k], sn[k + 1]; st = km(q[k], q[k + 1])
            L.append((a, b, st, q[k], q[k + 1]))
            if a is not None and b is not None and a != b:
                pairs[a][b] = max(pairs[a].get(b, 0), max(3.0 * st + 2.0, 4.0))
        items.append((r, L))
    paths = {}
    for src, tg in pairs.items():
        dist, pred = dijkstra(G, indices=src, limit=max(tg.values()), return_predecessors=True)
        for dst in tg:
            if not np.isfinite(dist[dst]): continue
            seq = [dst]
            while seq[-1] != src:
                p = pred[seq[-1]]
                if p < 0: seq = None; break
                seq.append(p)
            if seq: paths[(src, dst)] = seq[::-1]
    out = []; stat = collections.Counter()
    for r, L in items:
        coords, edges = [], set()
        for a, b, st, pa, pb in L:
            seq = paths.get((a, b)) if a is not None and b is not None and a != b else None
            if seq and plen(seq) <= max(2.6 * st, st + 1.5):
                seg = [[float(lon[n]), float(lat[n])] for n in seq]
                for j in range(len(seq) - 1): edges.add((min(seq[j], seq[j + 1]), max(seq[j], seq[j + 1])))
                stat["road"] += 1
            else:
                seg = [list(pa), list(pb)]; stat["straight"] += 1
            coords.extend(seg if not coords else seg[1:])
        g = LineString(coords).simplify(0.00012)
        ends = f'{r["pts"][0]["label"]} – {r["pts"][-1]["label"]}' if r["pts"] else ""
        out.append({"no": r["no"], "head": r["head"], "page": r["page"], "oy": r["oy"], "cy": r["cy"],
                    "oy_ctx": r["oy_ctx"][:120], "cy_ctx": r["cy_ctx"][:120], "src": r["src"], "ends": ends[:60],
                    "merged_into": r.get("merged_into", ""),
                    "geom": [[round(x, 5), round(y, 5)] for x, y in g.coords], "edges": sorted([int(a), int(b)] for a, b in edges)})
    json.dump(out, open(f"{B}/dead_routes.json", "w"), ensure_ascii=False, separators=(",", ":"))
    print("dead routes drawn", len(out), "of", len(D), "legs", dict(stat), file=sys.stderr)


if __name__ == "__main__":
    main()
