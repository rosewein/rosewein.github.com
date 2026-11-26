"""건축물대장 표제부(지금 대장) + 폐쇄말소대장 표제부 → data/building.json(법정동·사용승인 연도별 연면적·세대수)

    python3 src/building.py <자료 폴더>      (예: $SLM_RAW/bld_raw)

<자료 폴더>에 넣을 파일(zip이나 csv 그대로, 파일 이름으로 가린다)
- 지금 대장 표제부: 이름에 '표제부'가 있고 '폐쇄'·'말소'·'총괄'이 없는 파일
  (서울 열린데이터광장 「서울시 건축물대장 표제부」 OA-22424)
- 폐쇄말소대장 표제부: 이름에 '폐쇄' 또는 '말소'와 '표제부'가 있고 '총괄'이 없는 파일
  (서울 열린데이터광장 「서울시 폐쇄말소대장 표제부」)
- 총괄표제부(선택): 이름에 '총괄'이 있는 파일. 단지 이름을 붙이는 데만 쓴다.

셈하는 법
- 줄 하나 = 건축물 한 동(표제부). 연면적은 표제부의 연면적(㎡)을 그대로 더한다. 총괄표제부는 합계라서 더하지 않는다.
- 연도는 사용승인일의 해. 사용승인일이 비었거나 이상하면 그 줄은 연도별 합계에서 빼고 보고에 남긴다(허가일·착공일로 메우지 않음).
- 폐쇄말소대장은 '말소'·'일부말소'(해체·멸실로 건축물의 전부 또는 일부가 없어짐)만 쓴다. '폐쇄'와 '…에 의한 폐쇄'
  (전환·합병·지번변경·재작성으로 대장을 새로 만든 것)는 지금 대장에 같은 건물이 다시 있으므로 더하면 두 번 세게 된다
  — 「건축물대장의 기재 및 관리 등에 관한 규칙」 제2조 제7호·제9호. 2026-11-26 파일에서 대지위치·동명·사용승인일이 지금 대장과
  같은 줄의 비율은 말소 0%, 일부말소 4%, 폐쇄 갈래 10–79%였다. 말소·일부말소도 지금 대장과 그 셋이 같은 줄은 뺀다.
- 일련번호(건축물대장일련번호)는 대장을 새로 만들면 바뀌므로 지금 대장과 겹치는지 가리는 데 쓸 수 없다.
- 용도는 주용도코드명으로 서울시 「건축물 현황 통계」(국토교통부 건축물통계)의 다섯 갈래에 넣는다:
  주거(res)·상업(com)·공업(ind)·교육사회(edu)·기타(etc). 비었으면 unk.
- 법정동은 시군구코드 5자리 + 법정동코드 앞 3자리 = emd_topo.json의 cd 8자리. 코드가 없으면 구·동 이름으로 맞춘다.

결과
- building.json  {years:[y0..y1], dong:{cd:{cur:{res:[..],..}, gone:{..}, hh:[..], hhGone:[..], demol:[..]}}, seoul:{..}, big:[..]}
  cur = 지금도 있는 건물의 사용승인 연도별 연면적, gone = 그 뒤 말소된 건물의 사용승인 연도별 연면적,
  demol = 말소된 해별 연면적(헐린 양), hh = 공동주택 세대수. 단위 ㎡(정수)
- building_report.json  파일별 줄 수, 열 맞춘 결과, 사용승인일 빈 비율(시대별), 폐쇄·말소 구분, 말소 연도 분포 등

열 이름은 파일을 받기 전에 건축HUB 표제부 항목(국토교통부 건축물대장 표제부 설명)과 열린데이터광장 설명문에서 뽑은 후보로 맞춘다.
못 맞추면 머리줄을 찍고 멈추므로, 그때 ALT에 실제 이름을 더한다.
"""
import csv, io, json, os, re, sys, zipfile
from collections import Counter, defaultdict

from paths import CODE, DATA, RAW, WORK
B = DATA
GU = {"11110":"종로구","11140":"중구","11170":"용산구","11200":"성동구","11215":"광진구","11230":"동대문구","11260":"중랑구",
"11290":"성북구","11305":"강북구","11320":"도봉구","11350":"노원구","11380":"은평구","11410":"서대문구","11440":"마포구",
"11470":"양천구","11500":"강서구","11530":"구로구","11545":"금천구","11560":"영등포구","11590":"동작구","11620":"관악구",
"11650":"서초구","11680":"강남구","11710":"송파구","11740":"강동구"}
Y0, Y1 = 1900, 2026
CLASSES = ["res", "com", "ind", "edu", "etc", "unk"]

def norm(h):
    """머리줄 이름 비교용: 공백·밑줄·괄호·BOM을 빼고 영문은 소문자로"""
    return re.sub(r"[\s_()\[\]﻿]", "", h).lower()

# 열 이름 후보(norm 한 뒤 비교). 앞쪽을 먼저 본다.
ALT = {
    "sgg_cd":  ["시군구코드"],
    "bjd_cd":  ["법정동코드"],
    "sgg_nm":  ["시군구코드명", "시군구명"],
    "bjd_nm":  ["법정동코드명", "법정동명"],
    "plat":    ["대지위치"],
    "platgb":  ["대지구분코드", "대지구분코드명"],
    "bun":     ["번", "주지번", "본번"],
    "ji":      ["지", "부지번", "부번"],
    "pk":      ["관리건축물대장pk", "관리폐쇄말소대장pk", "건축물대장일련번호", "폐쇄말소대장일련번호"],
    "regstr":  ["대장구분코드명", "대장구분"],
    "kind":    ["대장종류코드명", "대장종류"],
    "mainatch":["주부속구분코드명", "주부속구분"],
    "bldnm":   ["건물명"],
    "dongnm":  ["동명칭", "동명"],
    "area":    ["연면적", "연면적㎡"],
    "purps":   ["주용도코드명", "주용도"],
    "purpscd": ["주용도코드"],
    "hhld":    ["세대수", "세대수세대"],
    "fmly":    ["가구수", "가구수가구"],
    "ho":      ["호수", "호수호"],
    "useapr":  ["사용승인일", "사용승인일자"],
    "pms":     ["허가일", "건축허가일", "허가일자"],
    "stcns":   ["착공일", "착공일자"],
    "closegb": ["폐쇄말소구분코드명", "폐쇄말소구분", "폐쇄말소구분코드"],
    "closeday":["폐쇄말소일", "폐쇄말소일자", "말소일", "말소일자", "철거멸실일", "멸실일"],
    "collected":["데이터수집일", "생성일자"],
}
NEED = ["area", "useapr"]

# 서울시 「건축물 현황 통계」 용도 갈래(열린데이터광장 DT201004K030003 설명). 먼저 맞는 쪽으로 간다.
USE_RULES = [
    ("etc", ["공공업무"]),
    ("res", ["단독주택", "공동주택", "아파트", "연립", "다세대", "다가구", "다중주택", "기숙사", "공관"]),
    ("com", ["근린생활", "판매", "운수", "업무시설", "숙박", "위락", "위험물저장", "자동차관련", "야영장"]),
    ("ind", ["공장", "위험물제조"]),
    ("edu", ["묘지", "관광휴게", "장례", "문화및집회", "문화집회", "종교", "의료", "교육연구", "노유자", "수련", "운동"]),
    ("etc", ["창고", "동식물", "동물및식물", "교정", "군사", "방송통신", "발전", "분뇨", "쓰레기", "자원순환", "가설"]),
]

def use_class(nm):
    s = (nm or "").replace(" ", "")
    if not s: return "unk"
    for c, keys in USE_RULES:
        if any(k in s for k in keys): return c
    return "etc"


def open_rows(path):
    """zip(또는 csv/txt) → (머리줄, 줄 반복자, 인코딩, 구분자). 큰 파일이라 한 줄씩 읽는다."""
    if path.lower().endswith(".zip"):
        zf = zipfile.ZipFile(path)
        member = max((i for i in zf.infolist() if i.filename.lower().endswith((".csv", ".txt"))), key=lambda i: i.file_size)
        raw = zf.open(member)
        peek = zf.open(member).read(200000)
    else:
        raw = open(path, "rb"); peek = open(path, "rb").read(200000)
    # 앞부분을 두 인코딩으로 풀어 깨진 글자가 적은 쪽을 고른다(열린데이터광장 파일에는 깨진 바이트가 몇 개씩 섞여 있음)
    bad = {e: peek[:-4].decode(e, errors="replace").count("\ufffd") for e in ("utf-8-sig", "cp949")}
    enc = min(bad, key=bad.get)
    if bad[enc] > 20: raise RuntimeError(f"{path}: 인코딩을 알 수 없음 {bad}")
    first = peek.decode(enc, errors="replace").split("\n", 1)[0]
    delim = max([",", "|", "\t"], key=first.count)
    text = io.TextIOWrapper(raw, encoding=enc, errors="replace", newline="")
    rd = csv.reader(text, delimiter=delim)
    head = [h.strip() for h in next(rd)]
    return head, rd, enc, delim


def colmap(head, path):
    nh = [norm(h) for h in head]
    m = {}
    for k, names in ALT.items():
        for nm in names:
            if nm in nh: m[k] = nh.index(nm); break
    miss = [k for k in NEED if k not in m]
    if miss or not ({"sgg_cd", "bjd_cd"} <= m.keys() or {"sgg_nm", "bjd_nm"} <= m.keys() or "plat" in m):
        raise RuntimeError(f"{path}: 열 이름이 예상과 다름(못 찾은 것 {miss}) — 머리줄 {head}")
    return m


def ymd(s):
    s = re.sub(r"\D", "", s or "")
    if len(s) >= 4 and s[:4].isdigit():
        y = int(s[:4])
        if Y0 <= y <= Y1: return y, s
    return None, s


def num(s):
    s = (s or "").replace(",", "").strip()
    try: return float(s)
    except ValueError: return 0.0


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if not args:
        print(__doc__); sys.exit(1)
    src = args[0]
    topo = json.load(open(f"{B}/emd_topo.json"))
    geoms = topo["objects"]["seoul_neighborhoods_geo"]["geometries"]
    emd = {g["properties"]["cd"]: g["properties"] for g in geoms}
    by_gu_nm = {(GU[p["gu"]], p["nm"]): cd for cd, p in emd.items()}

    files = {"cur": [], "gone": [], "recap": []}
    for f in sorted(os.listdir(src)):
        if not f.lower().endswith((".zip", ".csv", ".txt")): continue
        p = os.path.join(src, f)
        if "총괄" in f: files["recap"].append(p)
        elif ("폐쇄" in f or "말소" in f) and "표제부" in f: files["gone"].append(p)
        elif "표제부" in f: files["cur"].append(p)
    if not files["cur"]:
        raise SystemExit(f"{src}에 건축물대장 표제부 파일이 없음")

    n = Y1 - Y0 + 1
    zero = lambda: [0] * n
    dong = defaultdict(lambda: {"cur": {c: zero() for c in CLASSES}, "gone": {c: zero() for c in CLASSES},
                                "hh": zero(), "hhGone": zero(), "demol": zero(), "demolHh": zero()})
    big = defaultdict(lambda: {"a": 0.0, "hh": 0, "dongs": 0, "names": Counter(), "use": Counter()})
    report = {}
    out_asof = []
    GONE_OK = {"말소", "일부말소"}
    cur_keys = set()   # 지금 대장의 (대지위치, 동명, 사용승인일) — 말소대장 줄이 지금 건물과 같은지 가리는 데 씀

    def locate(r, c):
        sgg = r[c["sgg_cd"]].strip() if "sgg_cd" in c else ""
        bjd = r[c["bjd_cd"]].strip() if "bjd_cd" in c else ""
        if sgg.isdigit() and bjd.isdigit():
            d8 = sgg[:5] + bjd[:3]
            if d8 in emd: return d8, "코드"
        if "sgg_nm" in c and "bjd_nm" in c:
            # 열린데이터광장 파일은 시군구코드명이 '서울특별시 강서구'처럼 시도 이름까지 붙어 있다
            k = (r[c["sgg_nm"]].strip().split()[-1] if r[c["sgg_nm"]].strip() else "", r[c["bjd_nm"]].strip())
            if k in by_gu_nm: return by_gu_nm[k], "구·동 이름"
        if "plat" in c:
            parts = r[c["plat"]].split()
            if len(parts) >= 3 and (parts[1], parts[2]) in by_gu_nm: return by_gu_nm[(parts[1], parts[2])], "대지위치"
        return None, None

    for which in ("cur", "gone"):
        for path in files[which]:
            head, rd, enc, delim = open_rows(path)
            c = colmap(head, path)
            rows = 0; asof = ""
            why, how, gb, uses, unmatched = Counter(), Counter(), Counter(), Counter(), Counter()
            noapr_by_dec, all_by_dec, close_by_year, regstr, mainatch = Counter(), Counter(), Counter(), Counter(), Counter()
            for r in rd:
                rows += 1
                if len(r) < len(head):
                    why["칸 모자람"] += 1; continue
                if "collected" in c and r[c["collected"]] > asof: asof = r[c["collected"]]
                cd, h = locate(r, c)
                if cd is None:
                    why["법정동 못 맞춤"] += 1
                    unmatched[(r[c["sgg_cd"]] if "sgg_cd" in c else "") + "/" + (r[c["bjd_cd"]] if "bjd_cd" in c else "") + " " + (r[c["plat"]][:20] if "plat" in c else "")] += 1
                    continue
                how[h] += 1
                ck = (r[c["plat"]].strip() if "plat" in c else "", r[c["dongnm"]].strip() if "dongnm" in c else "", r[c["useapr"]].strip())
                if which == "cur":
                    cur_keys.add(ck)
                else:
                    g = r[c["closegb"]].strip() if "closegb" in c else ""
                    gb[g] += 1
                    if g not in GONE_OK:
                        why[f"폐쇄말소구분 '{g}'(뺌)"] += 1; continue
                    if ck[2] and ck in cur_keys:
                        why[f"{g}인데 지금 대장에 대지위치·동명·사용승인일이 같은 줄이 있음(뺌)"] += 1; continue
                if "regstr" in c: regstr[r[c["regstr"]].strip()] += 1
                if "mainatch" in c: mainatch[r[c["mainatch"]].strip()] += 1
                area = num(r[c["area"]])
                uc = use_class(r[c["purps"]] if "purps" in c else "")
                uses[(r[c["purps"]].strip() if "purps" in c else "") + " → " + uc] += 1
                y, raw = ymd(r[c["useapr"]])
                # 시대별 사용승인일 빈 비율을 보려고, 허가일·착공일로 시대를 어림한다(합계에는 쓰지 않음)
                yh = y or ymd(r[c["pms"]])[0] if "pms" in c else y
                yh = yh or (ymd(r[c["stcns"]])[0] if "stcns" in c else None)
                dec = f"{(yh // 10) * 10}년대" if yh else "연도 모름"
                all_by_dec[dec] += 1
                hh = int(num(r[c["hhld"]])) if "hhld" in c else 0
                D = dong[cd]
                if which == "gone":
                    cy, _ = ymd(r[c["closeday"]]) if "closeday" in c else (None, "")
                    close_by_year[cy or "모름"] += 1
                    if cy:
                        D["demol"][cy - Y0] += round(area)
                        if uc == "res": D["demolHh"][cy - Y0] += hh
                if y is None:
                    noapr_by_dec[dec] += 1
                    why["사용승인일 없음·이상(연도 합계에서 뺌)"] += 1; continue
                D[which][uc][y - Y0] += round(area)
                if uc == "res": D["hh" if which == "cur" else "hhGone"][y - Y0] += hh
                # 큰 개발 묶음: 같은 대지(동·대지구분·번·지)에 같은 해 사용승인된 동들
                bun = r[c["bun"]].strip().lstrip("0") if "bun" in c else ""
                ji = r[c["ji"]].strip().lstrip("0") if "ji" in c else ""
                key = (which, cd, {"1": "산", "산": "산"}.get(r[c["platgb"]].strip(), "") if "platgb" in c else "", bun, ji, y)
                bg = big[key]; bg["a"] += area; bg["hh"] += hh; bg["dongs"] += 1
                if "bldnm" in c and r[c["bldnm"]].strip(): bg["names"][r[c["bldnm"]].strip()] += 1
                bg["use"][uc] += area
                if "pnu" not in bg:
                    # PNU 19자리 = 법정동 10자리(서울은 리가 없어 cd 8자리 + 00) + 대지·산 구분(1·2) + 본번 4 + 부번 4
                    pg = {"0": "1", "1": "2", "대지": "1", "산": "2"}.get(r[c["platgb"]].strip() if "platgb" in c else "0", "")
                    if pg and bun.isdigit():
                        bg["pnu"] = cd + "00" + pg + bun.zfill(4) + (ji if ji.isdigit() else "0").zfill(4)
            report[os.path.basename(path)] = {
                "종류": which, "가장 늦은 수집일": asof, "encoding": enc, "구분자": delim, "줄": rows, "머리줄": head,
                "맞춘 열": {k: head[v] for k, v in c.items()}, "뺀 이유": dict(why), "동 맞춘 방법": dict(how),
                "못 맞춘 동(많은 순)": dict(unmatched.most_common(20)), "폐쇄말소구분": dict(gb), "대장구분": dict(regstr),
                "주부속구분": dict(mainatch), "주용도→갈래(많은 순)": dict(uses.most_common(60)),
                "시대별 줄(허가·착공일로 어림)": dict(sorted(all_by_dec.items())),
                "시대별 사용승인일 빈 줄": dict(sorted(noapr_by_dec.items())),
                "말소 연도별 줄": {str(k): v for k, v in sorted(close_by_year.items(), key=lambda kv: (isinstance(kv[0], str), kv[0]))},
            }
            print(f"{os.path.basename(path)} [{which}] 줄 {rows:,} · 뺀 것 {dict(why)}", file=sys.stderr)
            if which == "cur": out_asof.append(asof[:10])

    # 쓸 범위: 어느 해든 값이 있는 해부터
    used = [i for i in range(n) if any(D[w][k][i] for D in dong.values() for w in ("cur", "gone") for k in CLASSES)]
    lo, hi = (min(used), max(used)) if used else (0, n - 1)
    cut = lambda a: a[lo:hi + 1]
    out = {"years": [Y0 + lo, Y0 + hi], "classes": CLASSES, "dong": {}, "seoul": {}}
    for cd, D in dong.items():
        out["dong"][cd] = {"cur": {k: cut(v) for k, v in D["cur"].items() if any(cut(v))},
                           "gone": {k: cut(v) for k, v in D["gone"].items() if any(cut(v))},
                           "hh": cut(D["hh"]), "hhGone": cut(D["hhGone"]), "demol": cut(D["demol"]), "demolHh": cut(D["demolHh"])}
    for w in ("cur", "gone"):
        out["seoul"][w] = {k: [sum(D[w][k][i] for D in dong.values()) for i in range(lo, hi + 1)] for k in CLASSES}
    out["seoul"]["demol"] = [sum(D["demol"][i] for D in dong.values()) for i in range(lo, hi + 1)]
    # 정보창에 이름을 띄울 큰 개발: 연면적 1만㎡ 이상 또는 공동주택 300세대 이상
    bl = []
    for (which, cd, pg, bun, ji, y), bg in big.items():
        if bg["a"] >= 10000 or bg["hh"] >= 300:
            bl.append({"cd": cd, "y": y, "a": round(bg["a"]), "hh": bg["hh"], "n": bg["dongs"], "gone": which == "gone",
                       "nm": bg["names"].most_common(1)[0][0] if bg["names"] else "", "use": bg["use"].most_common(1)[0][0],
                       "jb": f"{pg}{bun}{'-' + ji if ji else ''}", "pnu": bg.get("pnu")})
    out["big"] = sorted(bl, key=lambda b: (b["y"], -b["a"]))
    out["asof"] = max(out_asof) if out_asof else ""
    out["src"] = {"cur": [os.path.basename(p) for p in files["cur"]], "gone": [os.path.basename(p) for p in files["gone"]]}
    json.dump(out, open(f"{B}/building.json", "w"), ensure_ascii=False, separators=(",", ":"))
    os.makedirs(WORK, exist_ok=True)
    json.dump(report, open(f"{WORK}/building_report.json", "w"), ensure_ascii=False, indent=1)
    print(f"wrote building.json (동 {len(out['dong'])}, 해 {out['years']}, 큰 개발 {len(bl)}), building_report.json", file=sys.stderr)


if __name__ == "__main__":
    main()
