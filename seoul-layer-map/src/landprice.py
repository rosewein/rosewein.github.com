"""서울 열린데이터광장 「서울시 개별공시지가 정보」(OA-1180) 연도별 zip → landprice.json(법정동별 ㎡당 공시지가 중앙값)

    python3 landprice.py <zip 폴더> [--keep-other]

- <zip 폴더>에 공시지가_YYYY년.zip(또는 풀어 둔 공시지가_YYYY년.csv)을 넣어 둔다. 몇 해만 있어도 된다.
- 법정동 경계는 이 스크립트와 같은 폴더의 emd_topo.json(객체 seoul_neighborhoods_geo, 속성 cd 8자리)을 쓴다.
- 결과 landprice.json은 같은 폴더에 쓰고, build.py가 읽어 DATA.land로 넣는다.

계산
- 필지 하나 = 줄 하나. 파일에 면적이 없으므로 중앙값은 필지 수 기준이다(작은 필지가 많은 동은 그쪽으로 기운다).
- 기본은 필지구분 1(토지대장)·2(임야대장)만 쓴다. 가지번·블럭지번·기타지번(3~9)은 --keep-other로 넣을 수 있다.
- 같은 토지코드가 한 해에 두 번 나오면(1월 1일·7월 1일 기준 등) 기준년월이 이른 줄 하나만 남긴다.
- 그 해 서울 중앙값 = 서울 전체 필지를 한데 놓은 중앙값(동 중앙값들의 중앙값이 아님).
- 법정동 맞추기: 토지코드 앞 8자리(시군구 5 + 동 3) → 구 이름·동 이름 → 서울에 하나뿐인 동 이름 → land_alias.json 순서.
  끝까지 못 맞춘 동은 보고에 남기고 지도에서는 '자료 없음'이 된다.

2026년 파일의 열(시도명·시군구명·법정동명·토지코드·공시지가(원/㎡)·시군구코드·법정동코드·필지구분코드·필지구분명·
본번·부번·기준년도·기준년월, CP949)을 기준으로 썼다. 다른 해 파일의 열 이름이 다르면 머리줄을 찍고 멈춘다.
"""
import csv, io, json, os, re, sys, zipfile
from collections import Counter, defaultdict

B = os.path.dirname(os.path.abspath(__file__))
GU = {"11110":"종로구","11140":"중구","11170":"용산구","11200":"성동구","11215":"광진구","11230":"동대문구","11260":"중랑구",
"11290":"성북구","11305":"강북구","11320":"도봉구","11350":"노원구","11380":"은평구","11410":"서대문구","11440":"마포구",
"11470":"양천구","11500":"강서구","11530":"구로구","11545":"금천구","11560":"영등포구","11590":"동작구","11620":"관악구",
"11650":"서초구","11680":"강남구","11710":"송파구","11740":"강동구"}

# 열 이름 후보(앞쪽이 2026년 파일 이름). 다른 해에 다른 이름이 나오면 여기에 더한다.
ALT = {
    "code":  ["토지코드", "고유번호", "PNU"],
    "price": ["공시지가(원/㎡)", "공시지가", "공시지가(원/m2)"],
    "gu_nm": ["시군구명"],
    "dong_nm": ["법정동명"],
    "gu_cd": ["시군구코드"],
    "dong_cd": ["법정동코드"],
    "kind":  ["필지구분코드"],
    "year":  ["기준년도"],
    "ym":    ["기준년월"],
}
NEED = ["price", "kind", "year"]


def median(v):
    v = sorted(v); n = len(v)
    if not n: return None
    return v[n // 2] if n % 2 else (v[n // 2 - 1] + v[n // 2]) / 2


def open_rows(path):
    """zip(또는 csv) → (머리줄, 줄 반복자). CP949가 아니면 UTF-8로 다시 읽는다."""
    if path.lower().endswith(".zip"):
        zf = zipfile.ZipFile(path)
        member = max((i for i in zf.infolist() if i.filename.lower().endswith((".csv", ".txt"))), key=lambda i: i.file_size)
        raw = zf.read(member)
    else:
        raw = open(path, "rb").read()
    for enc in ("cp949", "utf-8-sig"):
        try:
            text = raw.decode(enc); break
        except UnicodeDecodeError:
            continue
    else:
        raise RuntimeError(f"{path}: 인코딩을 알 수 없음")
    rd = csv.reader(io.StringIO(text, newline=""))
    head = [h.strip().strip("﻿") for h in next(rd)]
    return head, rd, enc


def colmap(head, path):
    m = {}
    for k, names in ALT.items():
        for nm in names:
            if nm in head: m[k] = head.index(nm); break
    miss = [k for k in NEED if k not in m]
    if miss or ("code" not in m and not {"gu_cd", "dong_cd"} <= m.keys()):
        raise RuntimeError(f"{path}: 열 이름이 예상과 다름 — 머리줄 {head}")
    return m


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    keep_other = "--keep-other" in sys.argv
    if not args:
        print(__doc__); sys.exit(1)
    src = args[0]
    topo = json.load(open(f"{B}/emd_topo.json"))
    geoms = topo["objects"]["seoul_neighborhoods_geo"]["geometries"]
    emd = {g["properties"]["cd"]: g["properties"] for g in geoms}
    by_gu_nm = {(GU[p["gu"]], p["nm"]): cd for cd, p in emd.items()}
    nm_count = Counter(p["nm"] for p in emd.values())
    by_nm = {p["nm"]: cd for cd, p in emd.items() if nm_count[p["nm"]] == 1}
    alias = json.load(open(f"{B}/land_alias.json")) if os.path.exists(f"{B}/land_alias.json") else {}
    # alias: {"구이름/옛 동이름": "지금 법정동 8자리", ...} — 보고의 unmatched를 보고 손으로 채운다

    files = {}
    for f in sorted(os.listdir(src)):
        m = re.search(r"(\d{4})", f)
        if m and f.lower().endswith((".zip", ".csv")) and "공시지가" in f:
            files.setdefault(int(m.group(1)), os.path.join(src, f))
    if not files:
        raise SystemExit(f"{src}에 공시지가_YYYY년.zip이 없음")

    out = {"years": [], "seoul": [], "seoulN": [], "dong": {}, "n": {}}
    report = {}
    per_year = {}
    for y, path in sorted(files.items()):
        head, rd, enc = open_rows(path)
        c = colmap(head, path)
        best = {}                 # 토지코드 → (기준년월, 단가, 동 8자리 또는 None, 이름 열쇠)
        kinds, yms, why, other_years = Counter(), Counter(), Counter(), Counter()
        rows = 0
        for r in rd:
            rows += 1
            if len(r) < len(head):
                why["칸 모자람"] += 1; continue
            kind = r[c["kind"]].strip()
            kinds[kind] += 1
            if kind not in ("1", "2") and not keep_other:
                why["가지번·블럭·기타지번(뺌)"] += 1; continue
            yr = r[c["year"]].strip()
            if yr != str(y):
                other_years[yr] += 1; continue
            p = r[c["price"]].strip().replace(",", "")
            if not p.isdigit() or int(p) <= 0:
                why["공시지가 없음"] += 1; continue
            code = r[c["code"]].strip() if "code" in c else ""
            if re.fullmatch(r"\d{19}", code):
                d8 = code[:8]
            elif "gu_cd" in c and "dong_cd" in c and r[c["gu_cd"]].strip().isdigit():
                d8 = r[c["gu_cd"]].strip() + r[c["dong_cd"]].strip()[:3]
                code = code or f'{d8}:{r[c["kind"]]}:{rows}'
            else:
                d8 = None; code = code or f"row{rows}"
            nmkey = (r[c["gu_nm"]].strip() if "gu_nm" in c else "", r[c["dong_nm"]].strip() if "dong_nm" in c else "")
            ym = r[c["ym"]].strip() if "ym" in c else ""
            yms[ym[:7]] += 1
            prev = best.get(code)
            if prev is None or ym < prev[0]:
                if prev is not None: why["같은 토지코드 중복(이른 기준월만 남김)"] += 1
                best[code] = (ym, int(p), d8, nmkey)
            else:
                why["같은 토지코드 중복(이른 기준월만 남김)"] += 1

        groups, unmatched, how = defaultdict(list), Counter(), Counter()
        for ym, p, d8, nmkey in best.values():
            if d8 in emd: cd = d8; how["코드"] += 1
            elif nmkey in by_gu_nm: cd = by_gu_nm[nmkey]; how["구·동 이름"] += 1
            elif nmkey[1] in by_nm: cd = by_nm[nmkey[1]]; how["동 이름"] += 1
            elif "/".join(nmkey) in alias: cd = alias["/".join(nmkey)]; how["별칭표"] += 1
            else:
                unmatched[f"{d8 or '-'} {nmkey[0]}/{nmkey[1]}"] += 1; continue
            groups[cd].append(p)
        allp = [p for v in groups.values() for p in v]
        per_year[y] = {cd: (median(v), len(v)) for cd, v in groups.items()}
        out["years"].append(y)
        out["seoul"].append(round(median(allp)) if allp else None)
        out["seoulN"].append(len(allp))
        no_dong = sorted(cd for cd in emd if cd not in groups)
        report[y] = {"file": os.path.basename(path), "encoding": enc, "rows": rows, "used": len(allp),
                     "필지구분": dict(kinds), "기준년월": dict(yms.most_common(6)), "다른 해 줄": dict(other_years),
                     "뺀 이유": dict(why), "동 맞춘 방법": dict(how), "못 맞춘 동": dict(unmatched.most_common(30)),
                     "자료 없는 동": [f"{cd} {GU[emd[cd]['gu']]}/{emd[cd]['nm']}" for cd in no_dong],
                     "서울 중앙값": out["seoul"][-1]}
        print(f"{y}: 줄 {rows:,} → 쓴 필지 {len(allp):,} · 서울 중앙값 {out['seoul'][-1]:,}원/㎡ · 동 {len(groups)}/{len(emd)}"
              f"{' · 못 맞춘 필지 ' + format(sum(unmatched.values()), ',') if unmatched else ''}", file=sys.stderr)

    ys = out["years"]
    # 덜 실린 해: 쓴 필지 수가 앞뒤 해(있는 것만) 평균의 90%에 못 미치면 표시(2006년 파일이 그렇다)
    out["partial"] = {}
    for i, y in enumerate(ys):
        nb = [out["seoulN"][j] for j in (i - 1, i + 1) if 0 <= j < len(ys)]
        if nb:
            cov = out["seoulN"][i] / (sum(nb) / len(nb))
            report[y]["앞뒤 해 대비 필지 수"] = round(cov, 3)
            if cov < 0.9: out["partial"][str(y)] = round(cov, 2)
    for cd in emd:
        meds = [per_year[y].get(cd, (None, 0))[0] for y in ys]
        if any(m is not None for m in meds):
            out["dong"][cd] = [None if m is None else round(m) for m in meds]
            out["n"][cd] = [per_year[y].get(cd, (None, 0))[1] for y in ys]
    out["src"] = "서울 열린데이터광장 「서울시 개별공시지가 정보」(OA-1180)"
    out["basis"] = "필지구분 1·2" + ("+기타" if keep_other else "")
    json.dump(out, open(f"{B}/landprice.json", "w"), ensure_ascii=False, separators=(",", ":"))
    json.dump(report, open(f"{B}/landprice_report.json", "w"), ensure_ascii=False, indent=1)
    print("wrote landprice.json, landprice_report.json", file=sys.stderr)


if __name__ == "__main__":
    main()
