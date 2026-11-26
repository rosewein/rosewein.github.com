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

def _m(p, q):
    """두 점(경도, 위도) 사이 거리(m, 서울 위도 근사)."""
    return math.hypot((p[0] - q[0]) * 88200, (p[1] - q[1]) * 110540)

def _dir(c, i, j):
    """_slice(c, i, j)가 꼭짓점 번호를 따라 앞으로 가면 +1, 뒤로 가면 -1."""
    d = 1 if i <= j else -1
    if c["loop"]:
        p, at = c["path"], c["at"]
        lo, hi = sorted((at[i], at[j]))
        direct, wrap = hi - lo + 1, (len(p) - hi) + lo   # _slice와 같은 꼭짓점 수
        if wrap < direct:
            d = -d
    return d

def _walk(c, k, step, maxlen):
    """선로 꼭짓점 k에서 step 방향으로 maxlen(m)까지 걸어간 꼭짓점들(k 제외). 순환선은 끝을 돌아 이어 간다."""
    p, n = c["path"], len(c["path"])
    out, acc, prev = [], 0.0, p[k]
    for _ in range(n):
        k += step
        if c["loop"]:
            k %= n - 1
        elif k < 0 or k >= n:
            break
        acc += _m(prev, p[k]); prev = p[k]; out.append(p[k])
        if acc >= maxlen:
            break
    return out

def _proj(q, E, lo, hi):
    """점 q를 꺾은선 E의 토막 lo..hi-1 위에 내린 가장 가까운 자리 → (거리 m, 토막 번호, 0–1 위치, 점)."""
    best = None
    qx, qy = q[0] * 88200, q[1] * 110540
    for s in range(max(lo, 0), min(hi, len(E) - 1)):
        a, b = E[s], E[s + 1]
        ax, ay, bx, by = a[0] * 88200, a[1] * 110540, b[0] * 88200, b[1] * 110540
        dx, dy = bx - ax, by - ay
        L2 = dx * dx + dy * dy
        t = 0.0 if L2 == 0 else max(0.0, min(1.0, ((qx - ax) * dx + (qy - ay) * dy) / L2))
        d = math.hypot(qx - ax - t * dx, qy - ay - t * dy)
        if best is None or d < best[0]:
            best = (d, s, t, [a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t])
    return best

def find_snap(lines, a, b, A, B, ext=600):
    """find()처럼 OSM 선로에서 두 역 사이 경로를 찾되, 역 좌표 A·B(경도, 위도)를 선로 위에 내린 자리에서 자른다.
    역 좌표가 OSM 역 자리와 어긋나도 선이 역을 지나쳤다 되돌아오거나(갈고리) 선로 밖으로 꺾여 나가지 않는다.
    역 좌표가 OSM 역 자리 바깥(앞뒤 역 쪽)에 있으면 앞뒤 선로를 ext(m)까지 이어 붙여 그 위에 내린다.
    돌려주는 경로의 두 끝은 선로 위의 자리이고, 역 점까지 잇는 짧은 선은 부르는 쪽이 정한다. 못 찾으면 None."""
    a0, b0 = a, b
    a, b = norm(a), norm(b)
    for ln in lines:
        for c in CHAINS.get(ln, []):
            aa = a if a in c["idx"] else a0
            bb = b if b in c["idx"] else b0
            if not (aa in c["idx"] and bb in c["idx"]):
                continue
            i, j = c["idx"][aa], c["idx"][bb]
            s = _slice(c, i, j)
            if len(s) < 2:
                continue
            d = _dir(c, i, j)
            before = _walk(c, c["at"][i], -d, ext)[::-1]
            after = _walk(c, c["at"][j], d, ext)
            E = before + s + after
            s0, s1 = len(before), len(before) + len(s) - 1   # E 안에서 두 OSM 역 꼭짓점의 번호
            pa = _proj(A, E, 0, s1)                           # A는 앞 연장 + 두 역 사이에서
            pb = _proj(B, E, s0, len(E) - 1)                  # B는 두 역 사이 + 뒤 연장에서
            if pa is None or pb is None or (pa[1], pa[2]) >= (pb[1], pb[2]):
                return s
            out = [pa[3]] + E[pa[1] + 1:pb[1] + 1] + [pb[3]]
            q = [out[0]]
            for x in out[1:]:
                if _m(x, q[-1]) > 0.5:                        # 거의 같은 점이 잇달아 나오면 하나만
                    q.append(x)
            return q if len(q) >= 2 else s
    return None

def attach(path, A, B):
    """선로 위에서 끝나는 경로의 두 끝을 역 점 A·B에 잇는다. 3m 안이면 끝점을 역 점으로 바꾸고, 더 떨어져 있으면 짧은 선을 붙인다."""
    p = list(path)
    if _m(p[0], A) <= 3: p[0] = A
    else: p.insert(0, A)
    if _m(p[-1], B) <= 3: p[-1] = B
    else: p.append(B)
    return p

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

def via_paths(lines, names, coords, snap=False):
    """경유역 이름 목록 → 각 연속 구간의 경로(없으면 None). coords: 이름→(lng,lat).
    snap=True면 두 끝을 역 좌표로 맞춘 경로를 돌려준다. 이웃한 두 역이 모두 선로 자료에 있으면 find_snap으로
    선로를 따라가게 하고, 사이에 선로 자료에 없는 역이 끼면 예전처럼 가까운 꼭짓점에서 잘라 끝을 역 좌표로 바꾼다."""
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
                if snap and coords.get(names[k]) and coords.get(names[j]):
                    A, B = list(coords[names[k]]), list(coords[names[j]])
                    q = find_snap(lines, names[k], names[j], A, B)
                    out[k] = attach(q, A, B) if q else [A] + p[1:-1] + [B]
            else:
                mids = [coords.get(n) for n in names[k + 1:j]]
                if snap and coords.get(names[k]) and coords.get(names[j]) and all(mids):
                    # 선로 자료에 없는 사이 역(옛 역 등): 선로 위에 내린 자리에서 자르고, NEAR(m) 안일 때만 역 점까지 잇는다
                    A, B = list(coords[names[k]]), list(coords[names[j]])
                    q = find_snap(lines, names[k], names[j], A, B) or p
                    pieces, gaps = split_proj(q, mids)
                    pieces[0], pieces[-1] = attach(pieces[0], A, pieces[0][-1]), attach(pieces[-1], pieces[-1][0], B)
                    for t, (X, g) in enumerate(zip(mids, gaps)):
                        if g <= NEAR:
                            pieces[t] = pieces[t] + [list(X)]
                            pieces[t + 1] = [list(X)] + pieces[t + 1]
                    for t, piece in enumerate(pieces):
                        out[k + t] = piece
                else:
                    for t, piece in enumerate(split(p, mids)):
                        out[k + t] = piece
                        if snap and coords.get(names[k + t]) and coords.get(names[k + t + 1]):
                            out[k + t] = [list(coords[names[k + t]])] + piece[1:-1] + [list(coords[names[k + t + 1]])]
        k = j
    return out

NEAR = 60

def split_proj(path, pts):
    """path를 중간 지점들(pts, 순서대로)을 선로 위에 내린 자리에서 잘라 len(pts)+1 조각으로. 각 지점의 선로까지 거리(m)도 돌려준다."""
    pieces, gaps, cur = [], [], list(path)
    for q in pts:
        d, s, t, pt = _proj(q, cur, 0, len(cur) - 1)
        head = cur[:s + 1] + [pt]
        tail = [pt] + cur[s + 1:]
        pieces.append([x for i, x in enumerate(head) if i == 0 or _m(x, head[i - 1]) > 0.5])
        cur = [x for i, x in enumerate(tail) if i == 0 or _m(x, tail[i - 1]) > 0.5]
        gaps.append(d)
    pieces.append(cur)
    return pieces, gaps

def rnd(p):
    return [[round(x, 5), round(y, 5)] for x, y in p]
