"""건축물대장 표제부(지금 대장) + 폐쇄말소대장 표제부 → data/building.json(법정동·사용승인 연도별 연면적·세대수)

    python3 src/building.py <자료 폴더>      (예: $SLM_RAW/bld_raw)

<자료 폴더>에 넣을 파일(zip이나 csv 그대로, 파일 이름으로 가린다)
- 지금 대장 표제부: 이름에 '표제부'가 있고 '폐쇄'·'말소'·'총괄'이 없는 파일
  (서울 열린데이터광장 「서울시 건축물대장 표제부」 OA-22424)
- 폐쇄말소대장 표제부: 이름에 '폐쇄' 또는 '말소'와 '표제부'가 있고 '총괄'이 없는 파일
  (서울 열린데이터광장 「서울시 폐쇄말소대장 표제부」)
- 총괄표제부(선택): 이름에 '총괄'이 있는 파일. 지금은 읽지 않는다(서울 열린데이터광장 파일에 건물명 열이 없음).
- 기본개요(선택): 이름에 '기본개요'가 있는 파일. 큰 개발 이름을 붙이는 데만 쓴다
  (「서울시 건축물대장 기본개요」 OA-22422, 「서울시 폐쇄말소대장 기본개요」 OA-22430).
  표제부의 건축물대장일련번호로 건물명을 찾고, 그 줄의 상위건축물대장일련번호(총괄표제부)에 건물명이 있으면 그쪽을 먼저 쓴다.
  (2026-11-26 이지의 크롬에서 두 번 내려받기를 눌렀으나 파일이 생기지 않아, 아래 건축HUB 파일로 대신함)
- 건축HUB 건물명(선택): 이름에 '건축HUB'가 있는 .json. src/building_names_tool.py로 만든 HTML에서 받은 파일로,
  큰 개발 지번(PNU)마다 국토교통부 「건축HUB 건축물대장정보 서비스」 표제부·총괄표제부의 건물명·동명·사용승인일·연면적이 들어 있다.
  지금 대장에 남은 큰 개발 줄만 이름을 붙인다: 같은 지번에서 사용승인 해가 같은 총괄표제부 건물명을 먼저 쓰고, 없으면 같은 해
  표제부 건물명 가운데 연면적이 가장 큰 것. 헐린 줄은 같은 지번에 새 건물이 있으므로 붙이지 않는다.
  이름은 받은 날 대장에 적힌 지금 이름이라, 리모델링이나 이름 바꾸기를 거친 건물은 지은 해의 이름과 다르다
  (예: 당산동 374는 1995년 사용승인 동들이 '래미안당산1차아파트', 같은 해 상가동이 '당산동삼성아파트').

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
AREA_MAX = 1_000_000   # 한 동 연면적이 이보다 크면 자릿수 오류로 본다(2026-11 자료에서 이 다섯 줄 다음으로 큰 동은 지금 대장 약 39만㎡)
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


# 건축HUB 건물명: 짧은 기호(101동·A동·제1동)와 부속 이름은 버린다. '○○상가'처럼 뜻 있는 이름은 남긴다
HUB_GENERIC = re.compile(r"^(지하)?주차장$|^관리(동|사무소)$|^(경비실|기계실|전기실|창고|부속동?|주건축물|상가|상가동|근린상가|노인정|경로당|어린이집|유치원|주민공동시설|복리시설|본관|별관|신관|구관|공장|주공장)$|^[가-힣]동$")


def hub_clean(s):
    s = re.sub(r"\s+", " ", s or "").strip()
    return re.sub(r"\s*(제?\s*[A-Za-z]?\d+(-\d+)?\s*동)$", "", s).strip()   # 끝의 '101동'·'제1동'·'A1동'


def hub_ok(s):
    if not s or HUB_GENERIC.search(s) or not re.search(r"[가-힣]{2,}|[A-Za-z]{3,}", s): return False   # '..'처럼 글자가 없는 것도 버림
    return not (len(s) <= 6 and re.fullmatch(r"[\s\d\-()A-Za-z제동호층]*", s))


def hub_names(bl, paths, report):
    H = {}
    for p in paths: H.update(json.load(open(p))["done"])
    how = Counter()
    for b in bl:
        if b["gone"]: continue
        L = H.get(b.get("pnu") or "")
        if L is None:
            if b["a"] >= 30000 or b["hh"] >= 300: how["받은 자료에 지번 없음"] += 1
            continue
        y = str(b["y"])
        ty = [t for t in L["t"] if t["useAprDay"][:4] == y]
        rn = Counter(hub_clean(r["bldNm"]) for r in L["r"] if r["useAprDay"][:4] == y and hub_ok(hub_clean(r["bldNm"])))
        tn = Counter()
        for t in ty:
            c = hub_clean(t["bldNm"])
            if hub_ok(c): tn[c] += float(t["totArea"] or 0)
        if rn: b["nm"] = rn.most_common(1)[0][0]; how["총괄표제부 이름"] += 1
        elif tn: b["nm"] = tn.most_common(1)[0][0]; how["표제부 이름"] += 1
        elif ty: how["같은 해 줄은 있으나 이름 없음"] += 1
        else: how["같은 해 사용승인 줄 없음"] += 1
    report["건축HUB 이름"] = {"파일": [os.path.basename(p) for p in paths], "지번": len(H), "큰 개발 줄(헐린 것 뺌)": dict(how)}
    return max(json.load(open(p)).get("made", "")[:10] for p in paths)
    print(f"건축HUB 이름: {dict(how)}", file=sys.stderr)


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if not args:
        print(__doc__); sys.exit(1)
    src = args[0]
    topo = json.load(open(f"{B}/emd_topo.json"))
    geoms = topo["objects"]["seoul_neighborhoods_geo"]["geometries"]
    emd = {g["properties"]["cd"]: g["properties"] for g in geoms}
    by_gu_nm = {(GU[p["gu"]], p["nm"]): cd for cd, p in emd.items()}

    files = {"cur": [], "gone": [], "recap": [], "names": [], "hub": []}
    for f in sorted(os.listdir(src)):
        p = os.path.join(src, f)
        if "건축HUB" in f and f.lower().endswith(".json"): files["hub"].append(p); continue
        if not f.lower().endswith((".zip", ".csv", ".txt")): continue
        if "기본개요" in f: files["names"].append(p)
        elif "총괄" in f: files["recap"].append(p)
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
    fixed = []   # 연면적 자릿수를 고친 줄
    out_asof = []
    GONE_OK = {"말소", "일부말소"}
    cur_keys = set()   # 지금 대장의 (대지위치, 동명, 사용승인일) — 말소대장 줄이 지금 건물과 같은지 가리는 데 씀

    # 기본개요에서 일련번호 → 건물명, 일련번호 → 상위(총괄표제부) 일련번호. 전유부 줄은 이름이 같아 읽지 않는다
    NAMES, PARENT = {}, {}
    for path in files["names"]:
        head, rd, enc, delim = open_rows(path)
        h = {norm(x): i for i, x in enumerate(head)}
        ipk, iup, inm, ikind = (h.get(norm(k)) for k in ("건축물대장일련번호", "상위건축물대장일련번호", "건물명", "대장종류코드명"))
        if ipk is None or inm is None:
            print(f"{os.path.basename(path)}: 일련번호·건물명 열이 없어 건너뜀", file=sys.stderr); continue
        nrow = 0
        for r in rd:
            if len(r) < len(head) or (ikind is not None and r[ikind].strip() == "전유부"): continue
            nrow += 1
            sn = r[ipk].strip()
            if r[inm].strip(): NAMES[sn] = r[inm].strip()
            if iup is not None and r[iup].strip(): PARENT[sn] = r[iup].strip()
        report[os.path.basename(path)] = {"종류": "기본개요(이름)", "encoding": enc, "읽은 줄(전유부 뺌)": nrow, "건물명 있는 줄": len(NAMES)}
        print(f"{os.path.basename(path)} [이름] 읽은 줄 {nrow:,} · 이름 {len(NAMES):,}", file=sys.stderr)
    GENERIC = re.compile(r"^[\s\d\-()A-Za-z제동호층]*$|주차장|관리동|경비실|기계실|전기실|창고|부속|주건축물|상가동?$")
    def name_for(sn):
        """표제부 일련번호의 건물명: 총괄표제부 이름을 먼저, 없으면 그 동의 이름. '101동'·'지하주차장' 같은 이름은 버린다"""
        for k in (PARENT.get(sn), sn):
            nm = NAMES.get(k) if k else None
            if nm and not GENERIC.search(nm): return nm
        return ""

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
                if area > AREA_MAX:
                    # 한 동의 연면적이 100만㎡를 넘는 줄은 서울에 있을 수 없는 값이다. 지금까지 본 다섯 줄은 모두 소수점이 빠져
                    # 1,000배로 적힌 것으로 보여(용적률산정연면적·건축면적×층수와 견줘 맞음) 1/1000로 고쳐 넣고 보고서에 남긴다
                    fixed.append({"파일": which, "대지위치": r[c["plat"]].strip() if "plat" in c else "", "동명": r[c["dongnm"]].strip() if "dongnm" in c else "",
                                  "적힌 연면적": area, "고친 연면적": round(area / 1000, 3), "사용승인일": r[c["useapr"]].strip()})
                    why["연면적 100만㎡ 넘음(소수점 빠진 것으로 보고 1/1000로 고침)"] += 1
                    area /= 1000
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
                elif NAMES and "pk" in c:
                    nm = name_for(r[c["pk"]].strip())
                    if nm: bg["names"][nm] += 1
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
    if files["hub"]: out["nmAsof"] = hub_names(bl, files["hub"], report)   # 이름을 받은 날(YYYY-MM-DD)
    out["big"] = sorted(bl, key=lambda b: (b["y"], -b["a"]))
    report["연면적 자릿수를 고친 줄"] = fixed
    out["asof"] = max(out_asof) if out_asof else ""
    out["src"] = {"cur": [os.path.basename(p) for p in files["cur"]], "gone": [os.path.basename(p) for p in files["gone"]]}
    json.dump(out, open(f"{B}/building.json", "w"), ensure_ascii=False, separators=(",", ":"))
    os.makedirs(WORK, exist_ok=True)
    json.dump(report, open(f"{WORK}/building_report.json", "w"), ensure_ascii=False, indent=1)
    print(f"wrote building.json (동 {len(out['dong'])}, 해 {out['years']}, 큰 개발 {len(bl)}), building_report.json", file=sys.stderr)


if __name__ == "__main__":
    main()
