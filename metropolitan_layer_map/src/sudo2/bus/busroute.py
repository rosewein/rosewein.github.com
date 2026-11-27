"""정류소 순서를 방향 도로 그래프 위 경로로 잇는다(탐욕 방식: 정류소마다 후보 노드 중 앞 정류소에서 가장 싸게 닿는 곳)."""
import numpy as np, math
from scipy.sparse import csr_matrix
from scipy.sparse.csgraph import dijkstra
from scipy.spatial import cKDTree
Z = np.load('/home/claude/sudo2/bus/busgraph.npz')
X, Y, U, V, Dk, C, COST = Z['x'], Z['y'], Z['u'], Z['v'], Z['d'], Z['c'], Z['cost']
N = len(X)
W = Dk * COST[C]
G = csr_matrix((W, (U, V)), shape=(N, N))
deg = np.bincount(U, minlength=N) + np.bincount(V, minlength=N)
XY = np.c_[X * 88.4, Y * 111.0]
alive = np.where(deg > 0)[0]
T = cKDTree(XY[alive])
EC = {}  # (u,v) -> class
for u, v, c in zip(U.tolist(), V.tolist(), C.tolist()): EC[(u, v)] = c

def cands(x, y, r=0.08, k=8):
    d, i = T.query((x * 88.4, y * 111.0), k=k, distance_upper_bound=r)
    out = [(float(dd), int(alive[ii])) for dd, ii in zip(d, i) if np.isfinite(dd)]
    if not out:
        dd, ii = T.query((x * 88.4, y * 111.0)); out = [(float(dd), int(alive[ii]))]
    return out

def path_to(pred, s, t):
    p = [t]
    while p[-1] != s:
        q = pred[p[-1]]
        if q < 0: return None
        p.append(int(q))
    return p[::-1]

GU = None
undirected = [0]
def route_seq(pts, snap_pen=3.0):
    """pts: [(x,y)] 정류소 순서. 반환: (노드 경로, 끊긴 구간 수)"""
    c0 = cands(*pts[0]); cur = c0[0][1]; full = [cur]; breaks = 0
    for (x0, y0), (x, y) in zip(pts, pts[1:]):
        cs = cands(x, y)
        straight = math.hypot((x - x0) * 88.4, (y - y0) * 111.0)
        lim = max(2.5, straight * 4 + 1.5)
        dist, pred = dijkstra(G, indices=cur, limit=lim, return_predecessors=True)
        best = None
        for sd, n in cs:
            if np.isfinite(dist[n]):
                sc = dist[n] + snap_pen * sd
                if best is None or sc < best[0]: best = (sc, n)
        if best is None:  # 일방통행 등으로 한 번에 못 닿으면 범위를 넓혀 한 번 더
            dist, pred = dijkstra(G, indices=cur, limit=max(15.0, straight * 8 + 5), return_predecessors=True)
            for sd, n in cs:
                if np.isfinite(dist[n]):
                    sc = dist[n] + snap_pen * sd
                    if best is None or sc < best[0]: best = (sc, n)
            if best is not None and dist[best[1]] > straight * 6 + 4: best = None  # 너무 돌아가면 끊어 둠
        if best is None:  # 그래도 못 닿으면 일방통행을 무시한 그래프로 이 구간만 잇는다(끊김 대신 근사)
            global GU
            if GU is None: GU = G.maximum(G.T).tocsr()
            dist, pred = dijkstra(GU, indices=cur, limit=max(15.0, straight * 8 + 5), return_predecessors=True)
            for sd, n in cs:
                if np.isfinite(dist[n]):
                    sc = dist[n] + snap_pen * sd
                    if best is None or sc < best[0]: best = (sc, n)
            if best is not None:
                p = path_to(pred, cur, best[1]); full.extend(p[1:]); cur = best[1]; undirected[0] += 1; continue
        if best is None:
            breaks += 1; cur = cs[0][1]; full.append(-1); full.append(cur); continue
        p = path_to(pred, cur, best[1]); full.extend(p[1:]); cur = best[1]
    return full, breaks
