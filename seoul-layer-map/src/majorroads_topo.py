"""큰 도로 갈래(roads): 국토지리정보원 옛 1:25,000 지형도(국토정보맵 「종이지도」)로 잰 결과를 모은다.

재기는 이지의 크롬에서 src/topo_probe.js로 한다(지형도 조각은 작업 공간에서 막혀 있음).
TP.dump(판)의 출력을 $SLM_RAW/build/topo/<판>.json(여러 조각이면 <판>_1.json …)으로 두고:

  python3 -I src/majorroads_topo.py --report      판마다 링크별 길 무늬 비율과 개통일 아는 길 대조를 보임
  python3 -I src/majorroads_topo.py               data/majorroads_topo.json을 씀(문턱은 아래 P_ON·P_OFF)

링크 열쇠는 majorroads.json의 첫 점과 끝 점(topo_probe.js의 TP.segKey와 같음)이라, 링크 순서가 바뀌어도 맞는다.
"""
import glob, json, os, re, sys, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from paths import DATA, WORK

TOPO = os.path.join(WORK, "topo")
OUT = os.path.join(DATA, "majorroads_topo.json")
ROADS = os.path.join(DATA, "majorroads.json")
# 국토정보맵 「종이지도」의 1:25,000 판(select#old_select2 값). 실제 수정 연도는 도엽마다 다르다(아직 확인 못 함)
EDS = ["PT025K_1960", "PT025K_1970", "PT025K_1980", "PT025K_1990", "PT025K_2000", "PT025K_2011", "PT025K_2013", "PT025K_2015"]
LABEL = {e: (e[-4:] + "년대" if e[-2:] in ("60", "70", "80", "90") or e.endswith("2000") else e[-4:] + "년") for e in EDS}
# 문턱(시안): 길 무늬가 점의 P_ON 넘게서 보이고 대조 단면보다 D_ON 넘게 많으면 있음, P_OFF 아래면 없음. 개통일 아는 길로 맞춰 고친다
P_ON, D_ON, P_OFF = 0.55, 0.25, 0.25
COL = {"n": 0, "nv": 1, "s1": 2, "s2": 3, "s3": 4, "sa": 5, "cv": 6, "c1": 7, "c2": 8, "c3": 9, "ca": 10}


def seg_key(sg):
    a, b = sg["g"][0], sg["g"][-1]
    f = lambda p: ",".join(str(v) for v in p)
    return f(a) + "|" + f(b)


def load_runs():
    runs = {}
    for e in EDS:
        rows = {}
        for f in sorted(glob.glob(os.path.join(TOPO, e + "*.json"))):
            d = json.load(open(f, encoding="utf-8"))
            rows.update(d["rows"])
        if rows:
            runs[e] = rows
    return runs


def state(r):
    """r = [점, 읽힌 점, sig1, sig2, sig3, 셋 중 하나, 대조 단면, 대조 sig1·2·3, 대조 셋 중 하나] → 1 있음, 0 없음, None 모름"""
    if not r or r[COL["nv"]] < max(2, 0.6 * r[COL["n"]]):
        return None, None
    p = r[COL["sa"]] / r[COL["nv"]]
    c = r[COL["ca"]] / r[COL["cv"]] if r[COL["cv"]] else 0
    if p >= P_ON and p - c >= D_ON:
        return 1, p
    if p <= P_OFF:
        return 0, p
    return None, p


def first_last(states):
    """판 차례의 상태로 (마지막으로 없던 판 번호, 처음 있던 판 번호). 처음 있던 판 뒤로는 없음이 한 번까지만 끼어도 됨"""
    idx = [i for i, s in enumerate(states) if s == 1]
    for i in idx:
        later = [s for s in states[i + 1:] if s is not None]
        if later.count(0) <= 1 and (not later or later[-1] == 1):
            prev0 = [j for j in range(i) if states[j] == 0]
            return (prev0[-1] if prev0 else None), i
    return None, None


def main(report=False):
    roads = json.load(open(ROADS, encoding="utf-8"))
    runs = load_runs()
    if not runs:
        sys.exit(f"{TOPO}에 판 결과가 없음(TP.dump 출력을 <판>.json으로 둠)")
    eds = [e for e in EDS if e in runs]
    out, rep = {}, collections.defaultdict(lambda: collections.Counter())
    for sg in roads["segs"]:
        k = seg_key(sg)
        st = [state(runs[e].get(k))[0] for e in eds]
        tn, tg = first_last(st)
        if tg is not None:
            out[k] = [tn, tg]
        if report and sg.get("o"):
            y = int(sg["o"][:4])
            rep[(sg["n"], sg["o"])]["".join("·" if s is None else str(s) for s in st)] += 1
    json.dump({"eds": [[e, LABEL[e]] for e in eds], "note": "국토지리정보원 국토정보맵 종이지도 1:25,000 지형도에서 잰 결과(시안). 값 = [마지막으로 없던 판 번호, 처음 있던 판 번호]",
               "segs": out}, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
    print(f"판 {len(eds)}개({', '.join(LABEL[e] for e in eds)}), 처음 있던 판을 잡은 링크 {len(out)}개 → {OUT}")
    if report:
        print("개통일 아는 길: 판 차례 상태(1 있음, 0 없음, · 모름) → 링크 수")
        for (n, o), c in sorted(rep.items(), key=lambda kv: kv[0][1]):
            print(f"  {o} {n}: " + ", ".join(f"{k}×{v}" for k, v in c.most_common(4)))


if __name__ == "__main__":
    main(report="--report" in sys.argv)
