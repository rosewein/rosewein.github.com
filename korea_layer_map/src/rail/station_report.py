"""station_match.json을 읽어 역 이름 대응 점검 보고(work/rail/station_match_report.md)를 만든다.

python3 src/rail/station_report.py
"""
import os as _os, sys as _sys
_sys.path.insert(0, _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), ".."))
from paths import W
import json, math, collections, re

R = json.load(open(W("rail", "station_match.json")))

# OSM 폐선·운휴 선(이름별 길이)
HW = collections.defaultdict(float)
for f in "sn":
    for w in json.load(open(W("rail", f"osm_rail_{f}.json")))["ways"]:
        hist = w["railway"] in ("abandoned", "disused", "razed", "preserved") or any(
            w.get(k) for k in ("abandoned:railway", "disused:railway", "razed:railway", "historic:railway",
                               "was:railway", "railway:historic"))
        if not hist or not w["name"]:
            continue
        c = w["coords"]
        HW[w["name"]] += sum(math.hypot((x - a) * math.cos(math.radians(b)) * 111.32, (y - b) * 110.57)
                             for (a, b), (x, y) in zip(c, c[1:]))


def hist_km(o):
    keys = set()
    for v in re.split(r"[·,]", o["노선"] + "·" + re.sub(r"\(.*?\)", "", o["당시"])):
        v = v.strip()
        if v:
            keys.add(v)
    out = []
    for nm, km in HW.items():
        if any(k in nm for k in keys):
            out.append(f"{nm} {km:.0f}km")
    return ", ".join(sorted(out))


def pts(o):
    return [p for sg in o.get("segs", []) for p in sg["pts"]]


# 1. 집계
L = ["# 철도 선형 잇기 1단계: 구간 사건표 역 이름 → OSM 역 대응 점검", "",
     "station_match.py가 만든 결과를 station_report.py로 정리했다. '제안'은 Claude가 짠 대응(이지 확인 전)이다.", ""]
L += ["## 집계", "", "| 표 | 줄 | 특수 줄 | 모든 점이 이어진 줄(제안 없이) | 모든 점이 이어진 줄(제안까지) | 점 | 이어진 점(제안 없이) | 이어진 점(제안까지) |",
      "|---|---|---|---|---|---|---|---|"]
for tag in ("국철", "도시철도"):
    rs = [o for o in R if o["표"] == tag]
    sp = [o for o in rs if o.get("특수")]
    nr = [o for o in rs if not o.get("특수")]
    ok0 = sum(all(p["how0"] != "없음" for p in pts(o)) for o in nr)
    ok1 = sum(all(p["how"] != "없음" for p in pts(o)) for o in nr)
    P = [p for o in nr for p in pts(o)]
    L.append(f"| {tag} | {len(rs)} | {len(sp)} | {ok0} | {ok1} | {len(P)} | {sum(p['how0'] != '없음' for p in P)} | {sum(p['how'] != '없음' for p in P)} |")
L.append("")
c = collections.Counter(p["how"] for o in R for p in pts(o))
L += ["이은 방법(제안까지, 점 수): " + ", ".join(f"{k} {v}" for k, v in c.most_common()), ""]
reg = collections.Counter()
for o in R:
    if o.get("특수") or o["표"] != "국철":
        continue
    reg[(o["지역"], all(p["how"] != "없음" for p in pts(o)))] += 1
L += ["국철 지역별 줄(모든 점 이어짐/아님, 제안까지): " + ", ".join(
    f"{g} {reg[(g, True)]}/{reg[(g, False)]}" for g in ("남", "남북", "북")), ""]

# 2. 안 이어진 구간
L += ["## 안 이어진 구간(제안까지 써도 한 점 이상 없는 줄)", "",
      "마지막 칸은 노선 이름(지금·당시)이 이름에 든 OSM 폐선·운휴 선의 길이 합이다. 이름만 맞춘 것이라 그 구간을 덮는지는 따로 봐야 한다.", "",
      "| 표·순번 | 노선 | 날짜 | 사건 | 구간 | 안 이어진 이름 | OSM 폐선·운휴 선(노선 이름이 든 것) |", "|---|---|---|---|---|---|---|"]
for o in R:
    if o.get("특수"):
        continue
    miss = [p["nm"] + (f"({p['rej']})" if p.get("rej") else "") for p in pts(o) if p["how"] == "없음"]
    if miss:
        L.append(f"| {o['표'][0]}{o['순번']} | {o['노선']} | {o['날짜']} | {o['사건']} | {o['구간']} | {', '.join(dict.fromkeys(miss))} | {hist_km(o)} |")
L.append("")
L += ["## 특수 줄(구간이 역 두 개로 적혀 있지 않음)", ""]
for o in R:
    if o.get("특수"):
        L.append(f"- {o['표'][0]}{o['순번']} {o['노선']} {o['날짜']} {o['사건']}: {o['구간']}")
L.append("")

# 3. 확인이 필요한 대응
def rows_with(cond):
    out = []
    for o in R:
        for p in pts(o):
            if cond(p):
                out.append((o, p))
    return out

L += ["## 연표 역명 변경으로 이은 이름", "", "| 이름 | OSM 역 | 사슬(연표 순번) | 줄 |", "|---|---|---|---|"]
g = collections.defaultdict(list)
for o, p in rows_with(lambda p: p["how"].startswith("연표") or "연표" in p["how"]):
    g[(p["nm"], p["pick_info"]["name"] if p.get("pick_info") else "-", p["note"])].append(o["표"][0] + o["순번"])
for (a, b, n), rs in sorted(g.items()):
    L.append(f"| {a} | {b} | {n} | {', '.join(rs)} |")
L.append("")
L += ["## 대응표로 이은 이름(station_alias.ALIAS)", "", "| 이름 | OSM 역 | 방법(상태, 확인 정도) | 근거 | 줄 |", "|---|---|---|---|---|"]
g = collections.defaultdict(list)
for o, p in rows_with(lambda p: "대응표" in p["how"]):
    g[(p["nm"], p["pick_info"]["name"] if p.get("pick_info") else "-", p["how"], p["note"])].append(o["표"][0] + o["순번"])
for (a, b, h, n), rs in sorted(g.items()):
    L.append(f"| {a} | {b} | {h} | {n} | {', '.join(rs)} |")
L.append("")
L += ["## 손 자리·선 위 자리·끝점으로 이은 이름(station_alias.MANUAL·MANUAL_ALONG·GKS_KM·ENDS)", "",
      "| 이름 | 위도, 경도 | 근거 | 줄 |", "|---|---|---|---|"]
g = collections.defaultdict(list)
for o, p in rows_with(lambda p: "손 자리" in p["how"]):
    pi = p["pick_info"]
    g[(p.get("lk", p["nm"]), f"{pi['lat']:.5f}, {pi['lon']:.5f}", p["note"])].append(o["표"][0] + o["순번"])
for (a, b, n), rs in sorted(g.items()):
    L.append(f"| {a} | {b} | {n} | {', '.join(rs)} |")
L.append("")
L += ["## OSM 옛 이름 태그로 이은 이름", ""]
g = collections.defaultdict(list)
for o, p in rows_with(lambda p: "OSM 옛 이름" in p["how"]):
    g[(p["nm"], p["pick_info"]["name"])].append(o["표"][0] + o["순번"])
for (a, b), rs in sorted(g.items()):
    L.append(f"- {a} → {b}: {', '.join(rs)}")
L.append("")
L += ["## 같은 이름의 지금 역과 옛 역 자리가 둘 다 있는 곳(어느 쪽을 쓸지 날짜로 정해야 함)", "",
      "| 이름 | 옮긴 날(OSM 태그) | 옛 자리를 고른 줄 | 지금 역을 고른 줄 |", "|---|---|---|---|"]
g = collections.defaultdict(lambda: [None, [], []])
for o, p in rows_with(lambda p: p.get("relocated")):
    k = re.sub(r"\(.*?\)|역$", "", p["pick_info"]["name"].replace(" ", "")).replace("역(폐역)", "")
    g[k][0] = p["relocated"]["switch"] or g[k][0]
    g[k][1 if p["relocated"]["picked"] == "hist" else 2].append(f"{o['표'][0]}{o['순번']}({o['날짜'][:4]})")
for k, (d, h, l) in sorted(g.items()):
    L.append(f"| {k} | {d or '모름'} | {', '.join(h)} | {', '.join(l)} |")
L.append("")
L += ["## 고른 역이 같은 이름 OSM 노선 선에서 10km 넘게 떨어진 점", ""]
L.append("(북쪽 노선은 OSM 이름이 달라(평의선 등) 이 점검에서 뺐다.)")
L.append("")
for o, p in rows_with(lambda p: p.get("pick_info") and (p["pick_info"]["line_km"] or 0) > 10 and "n" not in p["pick_info"]["reg"]):
    L.append(f"- {o['표'][0]}{o['순번']} {o['노선']} {o['구간']}: {p['nm']} → {p['pick_info']['name']} ({p['pick_info']['line_km']}km)")
L.append("")
L += ["## 고른 역 사이 직선거리가 구간 연장보다 긴 줄(잘못 이었거나 연장이 일부 구간 길이)", ""]
for o in R:
    if o.get("특수") or not o["연장"]:
        continue
    if all(sg["직선km"] is not None for sg in o["segs"]):
        t = sum(sg["직선km"] for sg in o["segs"])
        if t > float(o["연장"]) * 1.02:
            L.append(f"- {o['표'][0]}{o['순번']} {o['노선']} {o['구간']} ({o['날짜']} {o['사건']}): 직선 {t:.1f}km, 연장 {o['연장']}km — "
                     + " ~ ".join(f"{p['nm']}→{p['pick_info']['name']}" for p in pts(o)))
L.append("")
L += ["## 이름을 바꿔 이었는데 OSM에서 도시철도 역으로 잡힌 국철 점", "",
      "(OSM은 수도권 전철이 서는 국철 역도 station=subway로 적은 곳이 많아, 이름이 그대로 맞은 것은 뺐다.)", ""]
for o, p in rows_with(lambda p: p.get("pick_info") and p["pick_info"]["type"] == "urban" and p["how"] != "그대로"):
    if o["표"] == "국철":
        L.append(f"- {o['표'][0]}{o['순번']} {o['노선']} {o['구간']}: {p['nm']} → {p['pick_info']['name']}({p['how']})")
L.append("")
open(W("rail", "station_match_report.md"), "w").write("\n".join(L))
print("\n".join(L[:20]))
