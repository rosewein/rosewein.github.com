"""큰 도로 갈래(roads): 국토지리정보원 옛 1:25,000 지형도(국토정보맵 「종이지도」)로 잰 결과를 자료로 만든다.

재기는 이지의 크롬에서 src/topo_probe.js로 한다(지형도 조각은 작업 공간에서 막혀 있음).
TP.codes()가 돌려준 글자열(majorroads.json 링크 순서, 링크마다 한 글자)을 파일로 두고:

  python3 -I src/majorroads_topo.py 글자열파일            → data/majorroads_topo.json
  python3 -I src/majorroads_topo.py 글자열파일 --report   개통일 아는 길과 견준 표도 보임

한 글자 = 판 넷(1970·1980·1990·2000년대 판)의 상태를 3진수로 묶은 것(0 없음, 1 있음, 2 모름. 1970년대 판이 가장 낮은 자리).
링크 열쇠는 majorroads.json의 첫 점과 끝 점이라, 뒤에 majorroads.json 링크 순서가 바뀌어도 build.py가 열쇠로 맞춘다.
"""
import json, os, sys, collections, hashlib
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from paths import DATA

ALPH = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz가나다라마바사아자차카타파하거너더러머"
# 판: 국토정보맵 종이지도 판 이름, 화면 이름, 그 판으로 보이는 도엽들의 조사 해(추정), 10년대 첫 해
# 조사 해는 공공데이터포털 「국토지리정보원_구지형도_지도메타데이터」의 서울 도엽 11장 판 목록과, 개통일을 아는 길이
# 어느 판에 처음 보이는지로 어림한 값(추정). 1970년대 판 ≈ 1977년 편집(1976년 촬영·조사), 1980년대 ≈ 1985년 촬영·조사,
# 1990년대 ≈ 1996년 편집(1995년 촬영·조사), 2000년대 ≈ 2005년 조사
EDS = [
    {"code": "PT025K_1970", "label": "1970년대", "survey": 1976, "dec": 1970},
    {"code": "PT025K_1980", "label": "1980년대", "survey": 1985, "dec": 1980},
    {"code": "PT025K_1990", "label": "1990년대", "survey": 1995, "dec": 1990},
    {"code": "PT025K_2000", "label": "2000년대", "survey": 2005, "dec": 2000},
]
OUT = os.path.join(DATA, "majorroads_topo.json")


def seg_key(sg):
    f = lambda p: ",".join(json.dumps(v) for v in p)
    return f(sg["g"][0]) + "|" + f(sg["g"][-1])


def decode(ch):
    v = ALPH.index(ch)
    return [(v // 3 ** i) % 3 for i in range(len(EDS))]


def first_last(st):
    """판 차례 상태로 (처음 있던 판 번호, 바로 앞 판이 분명히 없었으면 그 번호). 처음 있던 판 뒤로 없음이 나오면 잡지 않음"""
    for i, s in enumerate(st):
        if s != 1: continue
        if 0 in st[i + 1:]: return None, None
        return i, (i - 1 if i > 0 and st[i - 1] == 0 else None)
    return None, None


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    codes = "".join(open(args[0], encoding="utf-8").read().split())
    roads = json.load(open(os.path.join(DATA, "majorroads.json"), encoding="utf-8"))
    segs = roads["segs"]
    assert len(codes) == len(segs), f"글자 수 {len(codes)} ≠ 링크 수 {len(segs)} (majorroads.json이 바뀌었으면 다시 잴 것)"
    out, stat, rep = {}, collections.Counter(), collections.defaultdict(collections.Counter)
    for sg, ch in zip(segs, codes):
        st = decode(ch)
        out[seg_key(sg)] = "".join("01?"[s] for s in st)
        tg, tn = first_last(st)
        stat[("처음 판", EDS[tg]["label"] if tg is not None else "-", "사이" if tn is not None else "늦어도")] += 1
        if sg.get("o"):
            rep[(sg["o"][:4], sg["n"])]["".join("01?"[s] for s in st)] += 1
    keys_hash = hashlib.sha1("\n".join(seg_key(s) for s in segs).encode()).hexdigest()[:12]
    json.dump({"note": "국토지리정보원 1:25,000 지형도(국토정보맵 「역사지도 → 종이지도」)에서 큰 도로 링크 자리에 길이 그려져 있는지 판마다 잰 결과(시안, src/topo_probe.js). "
                       "값은 판 차례(1970·1980·1990·2000년대)의 상태: 1 있음, 0 없음, ? 모름. 1960–1990년대 판은 동경 측지계라 동쪽 184m·남쪽 311m 옮겨 읽음",
               "eds": EDS, "keysHash": keys_hash, "segs": out},
              open(OUT, "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
    print(f"링크 {len(out)}개 → {OUT}")
    for k, v in sorted(stat.items()): print("  ", k, v)
    if "--report" in sys.argv:
        print("개통일 아는 길(개통 해, 이름): 판 상태 → 링크 수")
        for (y, n), c in sorted(rep.items()):
            print(f"  {y} {n}: " + ", ".join(f"{k}×{v}" for k, v in c.most_common(4)))


if __name__ == "__main__":
    main()
