"""구간 사건표의 양 끝(과 경유) 역 이름을 OSM 역에 잇는다(철도 선형 잇기 1단계).

python3 src/rail/station_match.py

입력: data/rail/국철_구간사건표_*.csv, 도시철도_구간사건표_*.csv, work/rail/osm_rail_s.json·osm_rail_n.json,
      RAW/국가철도공단_철도 통합 연표_20260303.csv(역명 변경 줄)
출력: work/rail/station_match.json(줄마다 구간·점·후보), work/rail/station_match_report.md

정해진 기법이 아니라 이 작업에서 짠 방식이다.
- 구간 칸 읽기: '~'로 점을 나누고, ', '는 여러 구간, '→'는 이설 전·후, 'X(Y 경유)'는 경유점,
  'X(a~b~c)'는 전체 경유 목록, 'X(Y)'의 Y는 비고 낱말이 아니면 다른 이름으로 본다.
- 이름 잇기 순서(먼저 걸린 것을 쓴다):
  1) OSM 역 name·name:ko·official_name·short_name이 그대로 같음('역'과 괄호 안은 떼고 견줌)
  2) 연표 역명 변경 사슬(사건 날짜 뒤에 일어난 변경만 따라감). 사슬이 있는데 OSM에 없으면 '없음'
  3) OSM old_name·alt_name·loc_name
  3-1) 연표 사슬을 날짜를 보지 않고 한 번 더(사건표가 바뀐 뒤에도 옛 이름을 쓴 줄)
  0) station_alias.MANUAL 손 자리(기간이 맞으면 가장 먼저), 날짜가 붙은 대응표(이름이 그대로 맞는 역보다 먼저)
  4) station_alias.py 대응표('정함'만. '제안'은 how 칸에만 반영, how0 칸은 제안 없이 낸 결과)
  5) 괄호 안 다른 이름으로 0)~4), 그래도 없으면 지역 칸과 다른 쪽 pbf에서 찾음
- 같은 이름 지금 역·옛 역 쌍은 station_alias.RELOC의 옮긴 날(없으면 OSM 태그)로 나눈다.
- 역이 아닌 끝(군사분계선·화물기지·제철소)은 station_alias.ENDS대로 OSM 선 끝점이나 남북 선 이름이 바뀌는 점.
- 금강산선 역은 OSM 금강산선 폐선 선 위 철원 기점 거리로 놓는다(station_alias.GKS_KM).
- 후보가 여럿이면 구간 안 이웃 점과의 직선거리 합이 가장 작은 조합을 고른다. 국철 줄은 일반 역(train),
  도시철도 줄은 지하철·경전철 역을 먼저 쓰게 작은 벌점을 준다. 지역 칸(남/북)에 맞는 pbf 쪽 역만 쓴다.
"""
import os as _os, sys as _sys
_sys.path.insert(0, _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), ".."))
from paths import RAW, DATA, W
import csv, re, json, math, glob, collections, itertools

# ---------- OSM 역 ----------
def norm(s):
    s = re.sub(r"\s+", "", s or "")
    s = re.sub(r"\(.*?\)", "", s)
    s = re.sub(r"(폐역|폐지)$", "", s)
    if s.endswith("역") and len(s) > 2:
        s = s[:-1]
    return s


ST = {}
for reg in ("s", "n"):
    d = json.load(open(W("rail", f"osm_rail_{reg}.json")))
    for x in d["st"]:
        k = (x["otype"], x["id"])
        if k in ST:
            ST[k]["reg"].add(reg)
            continue
        x["reg"] = {reg}
        ST[k] = x
STL = list(ST.values())


def sttype(x):
    s = x.get("station", "")
    if x.get("subway") == "yes" or x.get("light_rail") == "yes" or s in ("subway", "light_rail", "monorail"):
        return "urban"
    return "train"


IDX1, IDX2 = collections.defaultdict(list), collections.defaultdict(list)
for x in STL:
    for k in ("name", "name:ko", "official_name", "short_name"):
        for v in (x.get(k) or "").split(";"):
            if v.strip():
                IDX1[norm(v)].append(x)
    for k in ("old_name", "old_name:ko", "alt_name", "loc_name"):
        for v in (x.get(k) or "").split(";"):
            if v.strip():
                IDX2[norm(v)].append(x)
for idx in (IDX1, IDX2):
    for k in idx:
        seen = set(); u = []
        for x in idx[k]:
            if id(x) not in seen:
                seen.add(id(x)); u.append(x)
        idx[k] = u

# ---------- 연표 역명 변경 ----------
YP = list(csv.DictReader(open(RAW / "국가철도공단_철도 통합 연표_20260303.csv", encoding="utf-8-sig")))
REN = []  # (old, new, date, no, 이전 여부)
PAT = [re.compile(r"역명\s*(?:변경|개정|개칭)\s*\(([^()→]+?)(?:역)?\s*→\s*([^()]+?)(?:역)?\)"),
       re.compile(r"([가-힣]+?)역(?:에서|을|,)\s*([가-힣]+?)역(?:\([^)]*\))?(?:으로|로)\s*(?:개칭|개명|역명\s*변경|역명\s*개칭|역명\s*개정)"),
       re.compile(r"([가-힣]+?)(?:를|을)\s*([가-힣]+?)(?:으로|로)\s*개칭")]
for r in YP:
    s = r["요약내용"] + " " + r["상세내용"]
    date = r["이벤트일자"] or r["연도"]
    for p in PAT:
        for m in p.finditer(s):
            a, b = norm(m.group(1)), norm(m.group(2))
            if a and b and a != b and not a.endswith("선") and not b.endswith("선") and re.fullmatch(r"[가-힣]+", a + b):
                REN.append((a, b, date, int(r["연표순번"]), bool(re.search(r"이설|이전", s))))
REN = sorted(set(REN), key=lambda t: (t[2], t[3]))


def ren_chain(name, date):
    """사건 날짜 뒤의 역명 변경을 차례로 따라가 지금 이름 후보를 낸다."""
    cur, d, steps = name, date or "0", []
    for _ in range(6):
        if steps:  # 두 번째부터는 앞 변경보다 늦은 것만(같은 날 바뀐 다른 역으로 건너가지 않게)
            nx = [t for t in REN if t[0] == cur and t[2] > d]
        else:
            nx = [t for t in REN if t[0] == cur and t[2] >= d[:len(t[2])]]
        if not nx:
            break
        t = nx[0]
        steps.append(t); cur, d = t[1], t[2]
    return cur, steps


# ---------- 구간 칸 읽기 ----------
REMARK = {"지하", "신선", "옛 선", "1단계", "2단계", "우회선", "솔안터널", "울산 시가지", "응암순환 포함", "쌍용"}
SPECIAL = {"38선 이북", "마산 시내(통합 마산역)", "2단계 전 구간", "대전·대구 도심 구간"}


def split_out(s, ch):
    out, dep, cur = [], 0, ""
    for c in s:
        if c == "(":
            dep += 1
        elif c == ")":
            dep -= 1
        if c == ch and dep == 0:
            out.append(cur); cur = ""
        else:
            cur += c
    out.append(cur)
    return [o.strip() for o in out]


def parse_sec(sec):
    if sec in SPECIAL:
        return None
    parts = [p.strip() for p in sec.split("→")]
    roles = ["전", "후"] if len(parts) == 2 else [""]
    segs = []
    for role, part in zip(roles, parts):
        for s in split_out(part, ","):
            s = re.sub(r"\s+(복선|복선전철|전철화)$", "", s)
            pts = []
            for t in split_out(s, "~"):
                m = re.match(r"^(.*?)\((.*)\)$", t)
                if not m:
                    pts.append(dict(nm=t)); continue
                nm, par = m.group(1).strip(), m.group(2).strip()
                if "~" in par:
                    vs = [v.strip() for v in par.split("~")]
                    if vs and vs[-1] == nm:
                        vs = vs[:-1]
                    if pts and vs and vs[0] == pts[-1]["nm"]:
                        vs = vs[1:]
                    pts += [dict(nm=v, via=True) for v in vs]
                    pts.append(dict(nm=nm))
                elif par.endswith("경유"):
                    pts.append(dict(nm=par[:-2].strip(), via=True)); pts.append(dict(nm=nm))
                elif par in REMARK:
                    pts.append(dict(nm=nm, note=par))
                else:
                    pts.append(dict(nm=nm, alt=par))
            segs.append(dict(role=role, pts=pts))
    return segs


# ---------- 이름 잇기 ----------
def regs_of(row, kind):
    if kind == "urban":
        return {"s"}
    g = row["지역"]
    return {"남": {"s"}, "북": {"n"}, "남북": {"s", "n"}}.get(g, {"s", "n"})


from station_alias import ALIAS, RELOC, MANUAL, MANUAL_ALONG, ENDS, GKS_KM, GKS_TOTAL
AL, ALD = {}, {}
for a, b, st_, lvl, why, until, rg in ALIAS:
    (ALD if until else AL)[norm(a)] = dict(dst=b, st=st_, lvl=lvl, why=why, until=until, reg=rg)
MAN = collections.defaultdict(list)   # 손 자리·선 위 자리·끝점(아래 WAYS를 읽은 뒤 채움)


def _get_all(k, regs):
    return [x for x in IDX1.get(k, []) if x["reg"] & regs] or [x for x in IDX2.get(k, []) if x["reg"] & regs]


def lookup1(nm, date, regs, prop, kind="train"):
    """한 이름을 찾는다. (방법, 후보, 비고)
    국철 줄에서 이름이 그대로 맞는 것이 도시철도 역뿐이면, 뒤 단계(연표·옛 이름·대응표)에서 일반 역을 더 찾아보고
    없을 때만 그 도시철도 역을 낸다."""
    r = _lookup1(nm, date, regs, prop)
    if kind == "train" and r[0] == "그대로" and all(sttype(x) == "urban" for x in r[1]):
        r2 = _lookup1(nm, date, regs, prop, skip_direct=True, only_train=True)
        if r2[1] and any(sttype(x) == "train" for x in r2[1]):
            return r2
    return r


def _alias(a, k, regs, prop, _get):
    if a["st"] != "정함" and not prop:
        return None
    rg = regs & {a["reg"]} if a["reg"] else regs
    c = _get(norm(a["dst"]), rg) if rg else []
    if c:
        return f"대응표({a['st']}, {a['lvl']})", c, a["why"]
    return None


def _lookup1(nm, date, regs, prop, skip_direct=False, only_train=False):
    k = norm(nm)
    def _get(k2, rg):
        c = _get_all(k2, rg)
        return [x for x in c if sttype(x) == "train"] if only_train else c
    d = date or ""
    if k in MAN:   # 손으로 넣은 자리는 그 기간 안 사건에서 가장 먼저 쓴다
        c = [x for x in MAN[k] if x["from"] <= d < (x["until"] or "9999") and x["reg"] & regs]
        if c:
            return f"손 자리({c[0]['lvl']})", c, c[0]["why"]
    if k in ALD and d < ALD[k]["until"]:
        r = _alias(ALD[k], k, regs, prop, _get)
        if r:
            return r
    c = [] if skip_direct else [x for x in IDX1.get(k, []) if x["reg"] & regs]
    if c:
        return "그대로", c, ""
    cur, steps = ren_chain(k, date)
    note = ""
    if steps:
        # 연표 원문에 사건 날짜 뒤 이름 변경이 있으면 그것을 먼저 따른다(옛 이름 태그보다 앞). 못 찾으면 없음.
        note = " → ".join(f"{t[1]}({t[2]}, 연표{t[3]}{', 역 자리 옮김' if t[4] else ''})" for t in steps)
        c = _get(cur, regs)
        if c:
            return "연표 역명 변경", c, note
        return "없음", [], "연표 변경 사슬: " + note
    c = [x for x in IDX2.get(k, []) if x["reg"] & regs and (not only_train or sttype(x) == "train")]
    if c:
        return "OSM 옛 이름 태그", c, ""
    cur2, steps2 = ren_chain(k, "0")
    if steps2 and not skip_direct:   # 도시철도 역만 맞아 다시 찾을 때는 날짜 앞 변경으로 건너가지 않는다(광명→모량 같은 잘못)
        n2 = " → ".join(f"{t[1]}({t[2]}, 연표{t[3]}{', 역 자리 옮김' if t[4] else ''})" for t in steps2)
        c = _get(cur2, regs)
        if c:
            return "연표 역명 변경(사건 날짜 앞 변경)", c, n2
    if k in AL:
        r = _alias(AL[k], k, regs, prop, _get)
        if r:
            return r
    return "없음", [], ("연표 변경 사슬: " + note if note else "")


def lookup(p, date, regs, prop, kind):
    how, c, note = lookup1(p.get("lk", p["nm"]), date, regs, prop, kind)
    if not c and p.get("alt"):
        how2, c2, note2 = lookup1(p["alt"], date, regs, prop, kind)
        if c2:
            return "괄호 안 이름 · " + how2, c2, note2
    if not c:
        other = {"s", "n"} - regs
        if other:
            how2, c2, note2 = lookup1(p["nm"], date, other, prop, kind)
            if c2:
                return "다른 쪽 pbf · " + how2, c2, note2
    return how, c, note


def hav(a, b):
    R = 6371.0
    la1, lo1, la2, lo2 = map(math.radians, (a["lat"], a["lon"], b["lat"], b["lon"]))
    h = math.sin((la2 - la1) / 2) ** 2 + math.cos(la1) * math.cos(la2) * math.sin((lo2 - lo1) / 2) ** 2
    return 2 * R * math.asin(math.sqrt(h))


CITY = {"서울": (37.5665, 126.978), "경기": (37.5665, 126.978), "인천": (37.4563, 126.7052),
        "부산": (35.1796, 129.0756), "경남": (35.1796, 129.0756), "대구": (35.8714, 128.6014),
        "경북": (35.8714, 128.6014), "광주": (35.1595, 126.8526), "대전": (36.3504, 127.3845)}


def city_ok(row, x):
    cs = [CITY[c] for c in row["지역"].split("·") if c in CITY]
    return not cs or any(hav(dict(lat=a, lon=b), x) < 45 for a, b in cs)


def rel_date(x, cands):
    """같은 이름의 지금 역(live)과 옛 역(hist)이 20km 안에 함께 있으면 옮긴 날을 돌려준다.
    station_alias.RELOC(연표 원문·사건표)을 먼저 보고, 없으면 OSM 태그(start_date·end_date)."""
    pair = [y for y in cands if y is not x and norm(y["name"]) == norm(x["name"]) and y["kind"] != x["kind"]
            and "hist" in (x["kind"], y["kind"]) and hav(x, y) < 20]
    if not pair:
        return None, False
    if norm(x["name"]) in RELOC:
        return RELOC[norm(x["name"])][0], True
    live = x if x["kind"] != "hist" else pair[0]
    hist = x if x["kind"] == "hist" else pair[0]
    d = live.get("start_date") or live.get("opening_date") or hist.get("end_date") or ""
    return (d or None), True


def resolve(pts, kind, row):
    """후보가 여럿인 점은 이웃과의 거리 합에 벌점을 더한 값이 가장 작은 조합으로 고른다(동적 계획).
    벌점: 역 종류가 표와 다름 10(맞는 종류 후보가 있을 때만), 화물역·신호장 0.3, 옛 역 0.5,
    이름에 괄호가 붙은 역 30(괄호 없는 후보가 있을 때만),
    노선 선이 있는데 그 선에서 2km 넘게 떨어짐(같은 점의 다른 후보는 2km 안) 100,
    같은 이름 지금 역·옛 역 쌍에서 옮긴 날(OSM 태그)과 사건 날짜가 맞지 않음 8."""
    for p in pts:
        c = p["cand"]
        if kind == "urban":
            c2 = [x for x in c if city_ok(row, x)]
            if c and not c2:
                p["rej"] = "도시 범위 밖 후보만 있음"
            c = c2
        for x in c:
            x["_ld"] = line_dist(row, x)
        if kind == "train" and c and all(sttype(x) == "urban" for x in c):
            if all(x["_ld"] is not None and x["_ld"] > 20 for x in c):
                p["rej"] = "이름 같은 도시철도 역만 있음(노선에서 멂)"
                c = []
        p["cand"] = c
    idx = [i for i, p in enumerate(pts) if p["cand"]]
    if not idx:
        return
    def pen(x, cands, q):
        v = (0 if sttype(x) == kind or not any(sttype(y) == kind for y in cands) else 10.0)
        v += {"live": 0, "service": 0.3, "hist": 0.5, "manual": 0}[x["kind"]]
        if "(" in x["name"] and any("(" not in y["name"] for y in cands):
            v += 30
        if x["_ld"] is not None and x["_ld"] > 2 and any(y["_ld"] is not None and y["_ld"] <= 2 for y in cands):
            v += 100
        d, has = rel_date(x, cands)
        if has and d:
            before = row["날짜"] < d
            if (x["kind"] == "hist") != before:
                v += 8
        return v
    best = {id(x): (pen(x, pts[idx[0]]["cand"], pts[idx[0]]), [x]) for x in pts[idx[0]]["cand"]}
    for i in idx[1:]:
        nb = {}
        for x in pts[i]["cand"]:
            px = pen(x, pts[i]["cand"], pts[i])
            v = min(((c + hav(path[-1], x) + px, path + [x]) for c, path in best.values()), key=lambda t: t[0])
            nb[id(x)] = v
        best = nb
    _, path = min(best.values(), key=lambda t: t[0])
    for i, x in zip(idx, path):
        pts[i]["pick"] = x
    # 다른 쪽 pbf에서 찾은 점은 구간의 다른 점과 60km 안일 때만 받는다
    for i in idx:
        p = pts[i]
        if p["how"].startswith("다른 쪽 pbf"):
            others = [pts[j]["pick"] for j in idx if j != i]
            if others and min(hav(p["pick"], o) for o in others) > 60:
                p["rej"] = f'다른 쪽 pbf의 같은 이름 역({p["pick"]["name"]})이 구간에서 너무 멂'
                p.pop("pick"); p["cand"] = []


# ---------- 노선 선 모양(점검용) ----------
WAYS = []
for reg in ("s", "n"):
    d = json.load(open(W("rail", f"osm_rail_{reg}.json")))
    rel_ways = collections.defaultdict(set)
    for r in d["rel"]:
        for m in r["members"]:
            rel_ways[m].add(r["name"])
    for w in d["ways"]:
        nms = {w["name"]} | rel_ways.get(w["id"], set())
        WAYS.append((nms, w["coords"][::max(1, len(w["coords"]) // 20)]))


def line_keys(row):
    ks = set()
    for v in re.split(r"[·,]", row["노선(지금 이름)"] + "·" + re.sub(r"\(.*?\)", "", row["당시 이름"])):
        v = v.strip()
        if not v:
            continue
        m = re.match(r"(서울|부산|대구|인천|광주|대전) (\d)호선", v)
        if m:
            ks.add(m.group(2) + "호선"); continue
        ks.add(v.replace(" ", ""))
    return ks


LGEOM = {}


def line_dist(row, x):
    ks = frozenset(line_keys(row))
    if ks not in LGEOM:
        pts = []
        for nms, cs in WAYS:
            if any(k in n.replace(" ", "") for n in nms for k in ks if n):
                pts += cs
        LGEOM[ks] = pts
    pts = LGEOM[ks]
    if not pts:
        return None
    p = dict(lat=x["lat"], lon=x["lon"])
    return min(hav(p, dict(lon=a, lat=b)) for a, b in pts[:: max(1, len(pts) // 4000)])


# ---------- 손 자리·선 위 자리·끝점(station_alias.MANUAL·GKS_KM·ENDS) ----------
RAWW = []
for reg in ("s", "n"):
    d = json.load(open(W("rail", f"osm_rail_{reg}.json")))
    relm = collections.defaultdict(set)
    for r in d["rel"]:
        for m in r["members"]:
            relm[m].add(r["name"])
    for w in d["ways"]:
        w["_names"] = {w["name"]} | relm.get(w["id"], set())
        w["_reg"] = reg
        RAWW.append(w)


def _pt(lat, lon):
    return dict(lat=lat, lon=lon)


def _mk(name, lat, lon, reg, frm, until, lvl, why):
    return dict(name=name, lat=lat, lon=lon, kind="manual", otype="m", id=name, reg={reg}, station="train",
                subway="", light_rail="", start_date="", opening_date="", end_date="", **{"from": frm, "until": until},
                lvl=lvl, why=why)


def _snap(lat, lon, key, maxkm=2.0):
    best = None
    for w in RAWW:
        if not any(key in n for n in w["_names"] if n):
            continue
        for a, b in w["coords"]:
            dd = hav(_pt(lat, lon), _pt(b, a))
            if best is None or dd < best[0]:
                best = (dd, b, a)
    if best and best[0] <= maxkm:
        return best[1], best[2], best[0]
    return lat, lon, None


for nm, lat, lon, frm, until, snapkey, lvl, why in MANUAL:
    la, lo, dd = (_snap(lat, lon, snapkey) if snapkey else (lat, lon, None))
    why2 = why + (f" / OSM {snapkey} 선에 {dd:.2f}km 옮겨 붙임" if dd is not None else (" / 붙일 선을 2km 안에서 못 찾아 지명 점 그대로" if snapkey else ""))
    MAN[norm(nm)].append(_mk(nm, la, lo, "s", frm, until, lvl, why2))


for nm, key, base, toward, km, lvl, why in MANUAL_ALONG:
    b0 = [x for x in IDX1.get(norm(base), []) if sttype(x) == "train" and "s" in x["reg"]]
    t0 = IDX1.get(norm(toward), [])
    if b0 and t0:
        b, tw = b0[0], t0[0]
        vx, vy = tw["lon"] - b["lon"], tw["lat"] - b["lat"]
        best = None
        for w in RAWW:
            if not any(key in n for n in w["_names"] if n):
                continue
            for lo, la in w["coords"]:
                if (lo - b["lon"]) * vx + (la - b["lat"]) * vy <= 0:
                    continue
                dd = abs(hav(b, _pt(la, lo)) - km)
                if best is None or dd < best[0]:
                    best = (dd, la, lo)
        if best:
            MAN[norm(nm)].append(_mk(nm, best[1], best[2], "s", "", "", lvl,
                                     why + f" / OSM {key} 선에서 {base}역 기준 {toward} 쪽 직선 {km}km 점"))


def _chain(ways, start):
    """이름이 같은 선 조각들을 시작점에서 가장 가까운 끝부터 차례로 이어 한 줄로 만든다(틈은 곧게 잇는다)."""
    segs = [list(w["coords"]) for w in {w["id"]: w for w in ways}.values()]
    line = []
    cur = (start["lon"], start["lat"])
    while segs:
        best = None
        for i, s_ in enumerate(segs):
            for rev in (False, True):
                e = s_[-1] if rev else s_[0]
                dd = hav(_pt(cur[1], cur[0]), _pt(e[1], e[0]))
                if best is None or dd < best[0]:
                    best = (dd, i, rev)
        dd, i, rev = best
        s_ = segs.pop(i)
        s_ = s_[::-1] if rev else s_
        if dd > 30:   # 너무 먼 조각(다른 곳의 같은 이름 선)은 버린다
            continue
        line += s_
        cur = line[-1]
    return line


def _along(line, km):
    acc = 0.0
    for (a, b), (c_, d_) in zip(line, line[1:]):
        seg = hav(_pt(b, a), _pt(d_, c_))
        if acc + seg >= km and seg > 0:
            t = (km - acc) / seg
            return b + (d_ - b) * t, a + (c_ - a) * t, True
        acc += seg
    return line[-1][1], line[-1][0], False


GKS_INFO = {}
_cw = [x for x in IDX1.get("철원", []) if x["kind"] == "hist"] or IDX1.get("철원", [])
if _cw:
    gl = _chain([w for w in RAWW if w["name"] == "금강산선"], _cw[0])
    tot = sum(hav(_pt(b, a), _pt(d_, c_)) for (a, b), (c_, d_) in zip(gl, gl[1:]))
    GKS_INFO = dict(osm_km=round(tot, 1), table_km=GKS_TOTAL)
    for nm, km in GKS_KM:
        la, lo, inside = _along(gl, km)
        MAN[norm(nm)].append(_mk(nm, la, lo, "n" if la > 38.33 else "s", "", "", "추정",
                                 f"OSM 금강산선 폐선 선(이은 길이 {tot:.1f}km) 위 철원 기점 {km}km(위키백과 역 목록)"
                                 + ("" if inside else " — 선 길이를 넘어 끝점에 둠")))
        MAN[norm(nm)][-1]["reg"] = {"s", "n"}


for key, spec in ENDS.items():
    if spec[0] == "선끝":
        ws = [w for w in RAWW if spec[1] in w["_names"]]
        deg = collections.Counter()
        pos = {}
        for w in {w["id"]: w for w in ws}.values():
            for i in (0, -1):
                deg[w["nodes"][i]] += 1
                pos[w["nodes"][i]] = w["coords"][i]
        ends = [pos[n] for n, c_ in deg.items() if c_ == 1]
        st0 = IDX1.get(norm(spec[2]), [])
        if ends and st0:
            near = min(st0, key=lambda x: min(hav(x, _pt(b, a)) for a, b in ends))
            far = max(ends, key=lambda e: hav(near, _pt(e[1], e[0])))
            MAN[norm(key)].append(_mk(key, far[1], far[0], "s", "", "", "추정",
                                      f"OSM '{spec[1]}' 선에서 {spec[2]}역에서 가장 먼 끝점(인입선 끝과 같게)"))
    else:
        na = {n for w in RAWW if w["name"] == spec[1] for n in w["nodes"]}
        for w in RAWW:
            if w["name"] == spec[2]:
                for n, (a, b) in zip(w["nodes"], w["coords"]):
                    if n in na:
                        MAN[norm(key)].append(_mk(key, b, a, "s", "", "", "추정",
                                                  f"OSM '{spec[1]}' 선과 '{spec[2]}' 선이 만나는 점(남북 선 이름이 바뀌는 곳)"))
                        MAN[norm(key)][-1]["reg"] = {"s", "n"}
                        break
            if MAN.get(norm(key)):
                break


# ---------- 돌리기 ----------
rows_out = []
for f, kind, tag in ((sorted(glob.glob(str(DATA / "rail" / "국철_구간사건표_*.csv")))[-1], "train", "국철"),
                     (sorted(glob.glob(str(DATA / "rail" / "도시철도_구간사건표_*.csv")))[-1], "urban", "도시철도")):
    for row in csv.DictReader(open(f, encoding="utf-8-sig")):
        segs = parse_sec(row["구간"])
        o = dict(표=tag, 순번=row["순번"], 노선=row["노선(지금 이름)"], 당시=row["당시 이름"], 구간=row["구간"],
                 연장=row["연장(km)"], 날짜=row["날짜"], 사건=row["사건"], 지역=row["지역"], segs=[])
        if segs is None:
            o["특수"] = True; rows_out.append(o); continue
        regs = regs_of(row, kind)
        for sg in segs:
            for p in sg["pts"]:
                if p["nm"] == "군사분계선":
                    p["lk"] = "군사분계선@" + row["노선(지금 이름)"]
                how0, c0, note0 = lookup(p, row["날짜"], regs, False, kind)
                how, c, note = lookup(p, row["날짜"], regs, True, kind)
                p.update(how0=how0, how=how, cand=c, note=note)
            resolve(sg["pts"], kind, row)
            for p in sg["pts"]:
                x = p.get("pick")
                if x:
                    ld = x["_ld"]
                    rd, has = rel_date(x, p["cand"])
                    if has:
                        p["relocated"] = dict(switch=rd, picked=x["kind"])
                    same = [y for y in p["cand"] if y is not x and norm(y["name"]) == norm(x["name"]) and hav(x, y) < 20
                            and "hist" in (x["kind"], y["kind"]) and x["kind"] != y["kind"]]
                    p["pick_info"] = dict(name=x["name"], id=f'{x["otype"]}{x["id"]}', lon=round(x["lon"], 6),
                                          lat=round(x["lat"], 6), kind=x["kind"], type=sttype(x),
                                          reg="".join(sorted(x["reg"])), line_km=None if ld is None else round(ld, 2),
                                          same_name_near=[f'{y["name"]}[{y["kind"]}] {hav(x, y):.1f}km' for y in same])
                    far = [y for y in p["cand"] if hav(x, y) >= 20]
                    p["far_cand"] = len(far)
                elif p["how"] != "없음" and not p.get("rej"):
                    p["rej"] = "후보를 고르지 못함"
                p["ncand"] = len(p["cand"])
                p["cand_brief"] = [f'{x["name"]}[{x["kind"]},{sttype(x)},{x["lat"]:.3f},{x["lon"]:.3f}]' for x in p["cand"][:6]]
                if p.get("rej") and "pick_info" not in p:
                    p["how"] = "없음"
                del p["cand"]
                p.pop("pick", None)
            ok = [p["pick_info"] for p in sg["pts"] if "pick_info" in p]
            sg["직선km"] = round(sum(hav(a, b) for a, b in zip(ok, ok[1:])), 1) if len(ok) == len(sg["pts"]) else None
        o["segs"] = segs
        rows_out.append(o)

json.dump(rows_out, open(W("rail", "station_match.json"), "w"), ensure_ascii=False, indent=1)
json.dump(dict(gks=GKS_INFO, man={k: [dict(name=x["name"], lat=round(x["lat"], 6), lon=round(x["lon"], 6), why=x["why"],
                                           frm=x["from"], until=x["until"]) for x in v] for k, v in MAN.items()}),
          open(W("rail", "station_manual_points.json"), "w"), ensure_ascii=False, indent=1)
json.dump([list(t) for t in REN], open(W("rail", "yp_renames.json"), "w"), ensure_ascii=False, indent=0)
print(len(rows_out), "줄,", len(REN), "역명 변경")
