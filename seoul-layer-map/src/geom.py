"""OSM 선로 형상(metroscope data/network.json, © OpenStreetMap contributors, ODbL)으로 역 사이 경로를 찾는다."""
import json, math
from paths import CODE, DATA, RAW, WORK
NET = json.load(open(f"{RAW}/osm/network.json"))
ALIAS = {"당고개": "불암산", "이수": "총신대입구", "4·19민주묘지": "4.19민주묘지", "갈매(신)": "갈매"}
CHAINS = {}
for l in NET["lines"]:
    for c in l["chains"]:
        CHAINS.setdefault(l["name"], []).append({"idx": {n: i for i, n in enumerate(c["stations"])}, "path": c["path"], "at": c["at"], "loop": c["loop"]})

def norm(n):
    return ALIAS.get(n, n)

def _slice(c, i, j):
    p, at = c["path"], c["at"]
    if i <= j:
        direct = p[at[i]:at[j] + 1]
    else:
        direct = p[at[j]:at[i] + 1][::-1]
    if not c["loop"]:
        return direct
    # 순환선: 반대 방향(끝을 돌아 이어지는) 경로가 더 짧으면 그쪽
    if i <= j:
        wrap = (p[at[j]:] + p[1:at[i] + 1])[::-1]
    else:
        wrap = p[at[i]:] + p[1:at[j] + 1]
    return wrap if len(wrap) < len(direct) else direct

def find(lines, a, b):
    a0, b0 = a, b
    a, b = norm(a), norm(b)
    for ln in lines:
        for c in CHAINS.get(ln, []):
            aa = a if a in c["idx"] else a0
            bb = b if b in c["idx"] else b0
            if aa in c["idx"] and bb in c["idx"]:
                a, b = aa, bb
                s = _slice(c, c["idx"][a], c["idx"][b])
                if len(s) >= 2:
                    return s
    return None

def known(lines, n):
    return any((norm(n) in c["idx"] or n in c["idx"]) for ln in lines for c in CHAINS.get(ln, []))

def _d(p, q):
    return math.hypot((p[0] - q[0]) * 0.795, p[1] - q[1])

def split(path, pts):
    """path를 중간 지점들(pts, 순서대로) 가까운 꼭짓점에서 잘라 len(pts)+1 조각으로."""
    cuts, start = [], 0
    for q in pts:
        k = min(range(start, len(path)), key=lambda i: _d(path[i], q))
        k = max(k, start)
        cuts.append(k); start = k
    pieces, prev = [], 0
    for k in cuts:
        seg = path[prev:k + 1]
        if len(seg) < 2: seg = [path[prev], q]
        pieces.append(seg); prev = k
    pieces.append(path[prev:])
    return pieces

def via_paths(lines, names, coords):
    """경유역 이름 목록 → 각 연속 구간의 경로(없으면 None). coords: 이름→(lng,lat)."""
    out = [None] * (len(names) - 1)
    k = 0
    while k < len(names) - 1:
        if not known(lines, names[k]):
            k += 1; continue
        # 다음으로 네트워크에 있는 역 찾기
        j = k + 1
        while j < len(names) and not known(lines, names[j]):
            j += 1
        if j >= len(names):
            break
        p = find(lines, names[k], names[j])
        if p:
            if j == k + 1:
                out[k] = p
            else:
                mids = [coords[n] for n in names[k + 1:j]]
                for t, piece in enumerate(split(p, mids)):
                    out[k + t] = piece
        k = j
    return out

def rnd(p):
    return [[round(x, 5), round(y, 5)] for x, y in p]
