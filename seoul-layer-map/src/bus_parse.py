"""나무위키 '2004년 개편 전 목록' 추출본 → 노선 단면(2004.6)과 폐선 노선 연혁."""
import json, re, sys, math
sys.path.insert(0, "/home/claude/data/build")
import gazetteer as G

SRC = "/home/claude/data/bus/namu/namu_bus_pre2004.json"
CITY = (126.9780, 37.5665)  # 시청

HEAD = re.compile(r"^(\d+)\.\s+([0-9]+(?:-[0-9]+)?)\s*(\((?:좌석|고급좌석|직행좌석)\))?\s*\((.+?)\)\s*(\(★\))?\s*$")
VIA_LEAD = re.compile(r"운행\s*구간(?:\s*\(([^)]*)\))?\s*[:：]\s*")
YEAR = re.compile(r"(1[89]\d\d|20[0-2]\d)년(?:\s*(\d{1,2})월)?(?:\s*(\d{1,2})일)?")

def via_from_text(t):
    """본문에서 'A - B - C' 꼴 운행 구간을 찾는다. '운행구간(2기)'처럼 여러 개면 마지막 것."""
    segs = []
    for m in VIA_LEAD.finditer(t):
        segs.append(t[m.end():])
    cands = segs or [t]
    best = None
    for c in cands:
        m = re.search(r"[^.。:：]{1,40}?(?:\s[-–]\s[^.。:：\-–]{1,30}?){2,}(?=(?:\d{4}년|[.。]|$|운행\s*구간|[가-힣]{2,}(?:은|는|이|가)\s))", c)
        if m:
            best = m.group(0)
    return best

def tokens(via):
    via = re.sub(r"\((?:←|→)[^)]*(?:←|→)\)", "", via)          # 한 방향 경유 표기 제거
    via = re.sub(r"\(\s*[←→↔][^)]*\)", "", via)
    parts = [p.strip(" ·,") for p in re.split(r"\s[-–]\s|\s?⇄\s?|\s?↔\s?", via) if p.strip()]
    out = []
    for p in parts:
        p = re.sub(r"\s*\((?:경유|회차|일부|평일|주말)[^)]*\)", "", p)
        cur = re.search(r"\(현\s*([^)]+)\)", p)
        main = re.sub(r"\(.*?\)", "", p).strip()
        alt = re.findall(r"\(([^)]+)\)", p)
        names = ([cur.group(1).strip()] if cur else []) + ([main] if main else []) + [a.strip() for a in alt if not a.startswith("현")]
        more = []
        for nm in names:
            nm2 = re.sub(r"(\d+)~\d+가", r"\1가", nm)
            for piece in re.split(r"[,/·]", nm2):
                piece = re.sub(r"^(구|신)$", "", piece.strip())
                if piece: more.append(piece)
        names = names + [x for x in more if x not in names]
        out.append({"label": p, "names": [n for n in names if n and len(n) <= 20]})
    return out

def locate_tok(tok):
    for n in tok["names"]:
        r = G.locate(n)
        if r: return r
    return None

DEC = re.compile(r"(1[89]\d0|20[0-2]0)년대\s*(초반|초|중반|중후반|후반|말기|말)?")
DEC_OFF = {"초": 2, "초반": 2, "중반": 5, "중후반": 6, "후반": 8, "말": 8, "말기": 9, None: 5}

def _when(s, last=False):
    """문장 안의 날짜 표현 → (정렬용 'YYYY[-MM[-DD]]', 원문 표기, 근사 여부)."""
    found = []
    for m in YEAR.finditer(s):
        if s[m.end():m.end() + 1] == "대":  # '1990년대'는 아래에서
            continue
        v = m.group(1) + (f"-{int(m.group(2)):02d}" if m.group(2) else "") + (f"-{int(m.group(3)):02d}" if m.group(3) else "")
        found.append((m.start(), v, m.group(0), False))
    for m in DEC.finditer(s):
        y = int(m.group(1)) + DEC_OFF[m.group(2)]
        found.append((m.start(), str(y), m.group(0).strip(), True))
    if not found: return None
    found.sort()
    return found[-1][1:] if last else found[0][1:]

def years(t):
    """본문 문장에서 신설·폐선 시기를 뽑는다(자동 추출이라 정확도 낮음)."""
    o = c = None; oc = cc = ""
    sents = re.split(r"(?<=[.。])\s*|(?=운행\s*구간)", t)
    for s in sents:
        if not s: continue
        if c is None and re.search(r"폐선|폐지|운행을?\s*중단|사라졌|없어졌", s):
            w = _when(s, last=True)
            if w: c = w; cc = s[:180]
        if o is None and re.search(r"신설|생겼|생긴|시초|인가|개통|처음|모태", s):
            w = _when(s)
            if w: o = w; oc = s[:180]
    return o, oc, c, cc

def dist(a, b):
    return math.hypot((a[0] - b[0]) * 88.4, (a[1] - b[1]) * 111.0)

def main():
    d = json.load(open(SRC))
    routes = []
    for p in d["pages"]:
        pg = p["page"].split("/")[-1]
        for r in p["recs"]:
            m = HEAD.match(r["head"])
            if not m: continue
            no = m.group(2) + (" " + m.group(3).strip("()") if m.group(3) else "")
            star = bool(m.group(5))
            ops = [x.strip() for x in m.group(4).split("→")]
            text = r.get("text", "")
            via_raw = r["rows"].get("노선") or ""
            via_src = "표"
            if not via_raw:
                via_raw = via_from_text(text) or ""
                via_src = "본문" if via_raw else ""
            toks = tokens(via_raw) if via_raw else []
            pts = []
            for t in toks:
                loc = locate_tok(t)
                pts.append({"label": t["label"], "lng": round(loc[0], 5) if loc else None, "lat": round(loc[1], 5) if loc else None, "how": loc[2] if loc else None})
            o, oc, c, cc = years(text)
            oy = o[0] if o else None; cy = c[0] if c else None
            olab = o[1] if o else ""; clab = c[1] if c else ""
            oapp = o[2] if o else False; capp = c[2] if c else False
            routes.append({"page": pg, "no": no, "ops": ops, "star": star, "via_src": via_src, "via_raw": via_raw[:400],
                           "pts": pts, "succ": r["rows"].get("후신", ""), "alt": r["rows"].get("대체 노선", ""),
                           "open": oy, "open_label": olab, "open_approx": oapp, "open_ctx": oc,
                           "close": cy, "close_label": clab, "close_approx": capp, "close_ctx": cc})
    json.dump(routes, open("/home/claude/data/bus/namu/routes_parsed.json", "w"), ensure_ascii=False, indent=0)
    n = len(routes); live = [r for r in routes if not r["star"]]
    withvia = [r for r in live if r["pts"]]
    tot = sum(len(r["pts"]) for r in withvia); hit = sum(1 for r in withvia for p in r["pts"] if p["lng"])
    print(f"routes {n}, live(2004.6) {len(live)}, live with via {len(withvia)}, via points {tot}, located {hit} ({hit/max(tot,1):.0%})")
    st = [r for r in routes if r["star"]]
    print(f"abolished-before-2004 {len(st)}, with close year {sum(1 for r in st if r['close'])}, with open year {sum(1 for r in routes if r['open'])}, with via {sum(1 for r in st if r['pts'])}")
    miss = {}
    for r in routes:
        for p in r["pts"]:
            if not p["lng"]: miss[p["label"]] = miss.get(p["label"], 0) + 1
    print("top unmatched:", sorted(miss.items(), key=lambda x: -x[1])[:70])

if __name__ == "__main__":
    main()
