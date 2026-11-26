"""역 둘레 땅값 계산용 노선별 승강장 좌표.
    python3 -I station_platforms.py <metro.json> <metro_extra.json> <역사마스터 json> <출력 json>

지도의 역 점(metro.json)은 환승역마다 점 하나이고, 처음 만나는 노선의 좌표를 쓴다. 그래서 환승역에서는
처음 연 노선이 아니라 나중에 생긴 노선 자리에 점이 찍힌 곳이 있다(공덕은 5호선 1996년 개통인데 점은
219m 떨어진 다른 노선 자리). 환승역은 노선마다 승강장이 따로 생기므로, 역 둘레 계산에서는
노선마다 승강장 좌표와 그 노선이 이 역에 선 해를 따로 둔다.

- 역사마스터 json: sudo-happy/data-archive(0abf98a)의 metro/station/data-metro-station-1.0.0.json.
  지도(metro_build.py)와 같은 원자료다. metro_extra.json의 줄이 있으면 그 좌표가 앞선다.
- (노선, 역 이름)이 같고 지도 역 점에서 1.5km 안인 줄 가운데 가장 가까운 것을 쓴다.
- 출력: metro.json의 stations와 같은 순서. 역마다
  pf      [[노선, 그 노선 개통 해, 경도, 위도], ...]
  center  처음 연 노선(들) 승강장의 평균 좌표. 고리의 중심으로 쓴다.
- 이 파일은 저장소에 넣지 않는 중간 파일이다(원자료와 이 스크립트로 다시 만들 수 있음)."""
import json, math, sys

metro = json.load(open(sys.argv[1])); extra = json.load(open(sys.argv[2])); src = json.load(open(sys.argv[3]))["DATA"]
KX = 111320 * math.cos(math.radians(37.55)); KY = 110950
dist = lambda a, b: math.hypot((a[0] - b[0]) * KX, (a[1] - b[1]) * KY)
rows = {}
for r in src:
    ln = "GTX-A" if r["line"] == "GTXA" else r["line"]
    rows.setdefault((ln, r["name"]), []).append((r["lng"], r["lat"]))
for r in extra.get("stations", []):
    rows[(r["line"], r["name"])] = [(r["lng"], r["lat"])]
out, moved = [], []
for s in metro["stations"]:
    p = (s["lng"], s["lat"]); pf = []
    for ln, y in sorted(s["opens"].items(), key=lambda kv: (kv[1], kv[0])):
        cand = [q for q in rows.get((ln, s["name"]), []) if dist(q, p) < 1500]
        q = min(cand, key=lambda q: dist(q, p)) if cand else p   # 못 찾으면 지도 점(지금은 없음)
        if not cand: print("승강장 좌표 없음:", s["name"], ln, file=sys.stderr)
        pf.append([ln, y, round(q[0], 6), round(q[1], 6)])
    f = [q for q in pf if q[1] == s["first"]]
    c = (sum(q[2] for q in f) / len(f), sum(q[3] for q in f) / len(f))
    out.append({"name": s["name"], "first": s["first"], "lng": s["lng"], "lat": s["lat"],
                "center": [round(c[0], 6), round(c[1], 6)], "pf": pf})
    if dist(c, p) > 50: moved.append((round(dist(c, p)), s["name"], s["first"]))
json.dump({"src": "sudo-happy/data-archive 0abf98a metro/station/data-metro-station-1.0.0.json + metro_extra.json",
           "stations": out}, open(sys.argv[4], "w"), ensure_ascii=False)
print("역", len(out), "· 승강장", sum(len(o["pf"]) for o in out), "· 고리 중심이 지도 점에서 50m 넘게 옮겨진 역:", sorted(moved, reverse=True))
