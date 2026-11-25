"""버스 레이어 데이터: 2004년 6월 노선망 단면, 신설·폐선 사건, 규모 통계."""
import json, re, sys, math, collections
sys.path.insert(0, "/home/claude/data/build")
import gazetteer as G

SP = "/tmp/claude-0/-home-claude/438ad995-f3fd-5f5d-89cf-d7ca4fd5c542/scratchpad"
R = json.load(open("/home/claude/data/bus/namu/routes_parsed.json"))
PRE = json.load(open(f"{SP}/bus_events_pre2004.json"))["events"]
POSTD = json.load(open(f"{SP}/bus_events_post2004.json"))
CITY = (126.9780, 37.5665)

def km(a, b):
    return math.hypot((a[0] - b[0]) * 88.4, (a[1] - b[1]) * 111.0)

def place_locate(s):
    if not s: return None
    s = str(s)
    if re.search(r"전역|전반|외곽|생활권|노선별|통학|장거리|중복|회차", s) and not re.search(r"[가-힣]+\d*동", s):
        return None
    for cand in re.split(r"[,/~·()]|\s-\s", s):
        cand = cand.strip()
        if not cand: continue
        r = G.locate(cand)
        if r: return r
        for m in re.finditer(r"([가-힣]+\d*동)", cand):
            r = G.locate(m.group(1))
            if r: return r
        for w in cand.split():
            if len(w) >= 2:
                r = G.locate(w)
                if r and r[2] != "gu": return r
        m = re.search(r"([가-힣]+구)", cand)
        if m:
            r = G.locate(m.group(1))
            if r: return r
    return None

def norm_no(no):
    return re.sub(r"\s+", "", str(no or "")).replace("번", "")

# 1) 2004년 6월 노선망
routes, nodes = [], {}
BOX = (126.64, 37.30, 127.31, 37.84)  # 서울 경계에서 10km 남짓 바깥까지
def clean_pts(pts):
    pts = [p for p in pts if BOX[0] <= p[0] <= BOX[2] and BOX[1] <= p[1] <= BOX[3]]
    changed = True
    while changed and len(pts) >= 3:
        changed = False
        for i in range(len(pts)):
            a = pts[i - 1] if i > 0 else None; b = pts[i + 1] if i + 1 < len(pts) else None
            d_prev = km(pts[i], a) if a else None; d_next = km(pts[i], b) if b else None
            if a and b and d_prev > 4 and d_next > 4 and km(a, b) < 0.6 * (d_prev + d_next):
                pts.pop(i); changed = True; break
            if (a is None and d_next and d_next > 9) or (b is None and d_prev and d_prev > 9):
                # 끝점이 바로 옆 경유지와 9km 넘게 떨어지면 의심
                nb = pts[i + 1] if a is None else pts[i - 1]
                nb2 = pts[i + 2] if a is None and len(pts) > i + 2 else (pts[i - 2] if b is None and i >= 2 else None)
                if nb2 and km(nb, nb2) < 3:
                    pts.pop(i); changed = True; break
    return pts
DROPPED = 0
for r in R:
    raw = [(p["lng"], p["lat"], p["label"]) for p in r["pts"] if p["lng"]]
    pts = clean_pts(raw)
    DROPPED += len(raw) - len(pts)
    if len(pts) < 2: continue
    ri = len(routes)
    routes.append({"no": r["no"], "ops": r["ops"], "live": not r["star"], "pts": [[round(x, 4), round(y, 4)] for x, y, _ in pts],
                   "via": r["via_raw"][:300], "succ": r["succ"][:120],
                   "oy": int(r["open"][:4]) if r["open"] else None, "cy": int(r["close"][:4]) if (r["star"] and r["close"]) else None})
    if r["star"]: continue
    seen = set()
    for x, y, lab in pts:
        key = (round(x / 0.003), round(y / 0.003))
        if key in seen: continue
        seen.add(key)
        nd = nodes.setdefault(key, {"xs": [], "ys": [], "labels": collections.Counter(), "routes": []})
        nd["xs"].append(x); nd["ys"].append(y); nd["labels"][re.sub(r"\(.*?\)", "", lab).strip()] += 1; nd["routes"].append(ri)
node_list = []
for nd in nodes.values():
    node_list.append({"lng": round(sum(nd["xs"]) / len(nd["xs"]), 4), "lat": round(sum(nd["ys"]) / len(nd["ys"]), 4),
                      "name": nd["labels"].most_common(1)[0][0], "r": nd["routes"]})
node_list.sort(key=lambda n: -len(n["r"]))
route_index = {norm_no(rt["no"]): i for i, rt in enumerate(routes)}

# 2) 사건
events = []
def frontier(pts):
    pts = clean_pts(list(pts))
    return max(pts, key=lambda p: km(p, CITY)) if pts else None
for r in R:
    pts = [(p["lng"], p["lat"]) for p in r["pts"] if p["lng"]]
    f = frontier(pts)
    ri = route_index.get(norm_no(r["no"]))
    ends = f'{r["pts"][0]["label"]} – {r["pts"][-1]["label"]}' if r["pts"] else ""
    if r["open"]:
        events.append({"y": int(r["open"][:4]), "d": r["open_label"] or r["open"], "t": "신설", "no": r["no"], "ends": ends,
                       "txt": r["open_ctx"], "src": "나무위키 본문(자동 추출)", "conf": "low", "approx": r["open_approx"],
                       "lng": f and round(f[0], 4), "lat": f and round(f[1], 4), "ri": ri})
    if r["star"] and r["close"]:
        events.append({"y": int(r["close"][:4]), "d": r["close_label"] or r["close"], "t": "폐선", "no": r["no"], "ends": ends,
                       "txt": r["close_ctx"], "src": "나무위키 본문(자동 추출)", "conf": "low", "approx": r["close_approx"],
                       "lng": f and round(f[0], 4), "lat": f and round(f[1], 4), "ri": ri})
cur = PRE + POSTD["events"]
cur_keys = set()
for e in cur:
    m = re.match(r"(\d{4})", str(e.get("date", "")))
    if not m: continue
    y = int(m.group(1))
    loc = place_locate(e.get("place")) or place_locate(e.get("end")) or place_locate(e.get("start"))
    no = str(e.get("route", ""))
    cur_keys.add((norm_no(no), y, e["type"]))
    events.append({"y": y, "d": str(e["date"]).replace("-", "."), "t": e["type"], "no": no,
                   "ends": " – ".join(x for x in [e.get("start", ""), e.get("end", "")] if x),
                   "txt": (e.get("reason") or "") + (" " + e["note"] if e.get("note") else ""), "place": e.get("place", ""),
                   "cnt": e.get("count", ""), "src": e.get("source", ""), "conf": e.get("conf", "medium"),
                   "lng": loc and round(loc[0], 4), "lat": loc and round(loc[1], 4), "ri": route_index.get(norm_no(no)), "cur": 1})
# 같은 노선·연도·유형이 조사 기록에 있으면 자동 추출본은 뺀다
events = [e for e in events if e.get("cur") or (norm_no(e["no"]), e["y"], e["t"]) not in cur_keys]
events.sort(key=lambda e: (e["y"], e["d"]))

# 3) 통계와 큰 사건
stats = [{"y": s["year"], "routes": s.get("routes"), "buses": s.get("buses")} for s in POSTD["stats"] if s.get("routes") or s.get("buses")]
stats.sort(key=lambda s: s["y"])
log = []
for m in POSTD["milestones"]:
    mm = re.match(r"(\d{4})", m["date"])
    if mm: log.append({"year": int(mm.group(1)), "date": m["date"].replace("-", "."), "kind": "bus", "text": "버스: " + m["text"], "sort": 5})
for e in cur:
    if e["type"] == "일괄조정":
        mm = re.match(r"(\d{4})", str(e.get("date", "")))
        if mm:
            c = f' ({e["count"]}개 노선)' if e.get("count") else ""
            log.append({"year": int(mm.group(1)), "date": str(e["date"]).replace("-", "."), "kind": "bus",
                        "text": "버스 노선 일괄 조정" + c + (": " + e["reason"][:70] if e.get("reason") else ""), "sort": 5})
seenlog = set(); log2 = []
for l in sorted(log, key=lambda l: (l["year"], l["date"])):
    k = (l["date"], l["text"][:30])
    if k in seenlog: continue
    seenlog.add(k); log2.append(l)

out = {"routes": routes, "nodes": node_list, "events": events, "stats": stats, "snapshot": {"from": 2003, "to": 2004, "label": "2004년 6월 노선망(개편 직전)"}}
json.dump(out, open("/home/claude/data/build/bus.json", "w"), ensure_ascii=False, separators=(",", ":"))
json.dump(log2, open("/home/claude/data/build/bus_events.json", "w"), ensure_ascii=False, indent=0)
live = sum(1 for r in routes if r["live"])
print("dropped outlier points:", DROPPED)
print(f"routes drawn {len(routes)} (live {live}), nodes {len(node_list)}, events {len(events)} (located {sum(1 for e in events if e['lng'])}), stats {len(stats)}, log {len(log2)}")
print("busiest nodes:", [(n["name"], len(n["r"])) for n in node_list[:12]])
print("events by decade:", sorted(collections.Counter(e["y"] // 10 * 10 for e in events).items()))
