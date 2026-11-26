"""나무위키 「서울특별시 시내버스/폐선」 하위 문서 → 2004년 7월 이후 없어진 노선의 운행 기간과 경유지.

나온 결과는 RAW/bus/namu_post/dead_parsed.json
"""
import json, re, sys, collections
from paths import CODE, DATA, RAW, WORK
sys.path.insert(0, CODE)
import gazetteer as G
from bus_parse import tokens, locate_tok, via_from_text
from dead_supp import SUPP

SRC = f"{RAW}/bus/namu_post/namu_bus_post2004.json"
OUT = f"{RAW}/bus/namu_post/dead_parsed.json"
B = DATA

# 문서마다 표식 뜻이 다르다
CONT_PAGES = ("간선버스", "순환버스", "광역버스", "심야버스")   # ☆ 형간전환, ★ 번호 변경 → 다른 번호로 이어짐
# 지선버스/n권역, 맞춤버스: ☆ 지금 노선과 번호만 같음(다른 노선), ★ 번호·회사 모두 같음(이어진 노선일 수 있음)

HEAD = re.compile(r"^\s*([A-Z]?\d{1,4}[A-Z]?(?:-\d)?(?:,\s*[A-Z]?\d{1,4}[A-Z]?)*)번?\s*(\(.*)?$")
DATE = re.compile(r"((?:19|20)\d\d)년(?:\s*(\d{1,2})월)?(?:\s*(\d{1,2})일)?")
REFORM = re.compile(r"대개편|2004년 7월 1일|개편 당시|개편 때|개편 이후|개편 전|구 도시형|구 좌석|구 일반좌석|구 심야|이 전신")


def dates_in(s):
    out = []
    for m in DATE.finditer(s):
        y = int(m.group(1))
        if 1950 <= y <= 2026:
            out.append((y, int(m.group(2) or 0), int(m.group(3) or 0)))
    return out


def sentences(t):
    t = re.sub(r"\[\d+\]", "", t)
    return [s for s in re.split(r"(?<=[다음함됨])\.\s*|\n", t) if s.strip()]


def via_of(t):
    m = re.search(r"\n노선\n\s*\n?([^\n]{8,})", t)
    if m and (" - " in m.group(1) or "→" in m.group(1)):
        return m.group(1), "표"
    m = re.search(r"운행\s*구간\s*(?:\([^)]*\))?\s*[:：]\s*([^\n]+)", t)
    if m and (" - " in m.group(1) or "→" in m.group(1)):
        return m.group(1), "운행구간"
    v = via_from_text(t)
    return (v, "본문") if v else ("", "")


def norm_via(v):
    v = re.sub(r"\(\s*(?:→|←)[^)]*\)", "", v)
    v = re.sub(r"(이하|이후)\s*역순.*$", "", v)
    v = re.sub(r"\((?:회차|U턴|유턴|P턴)\)", "", v)
    v = re.sub(r"\s*[→←]\s*", " - ", v)
    v = re.sub(r"(\s-\s){2,}", " - ", v)
    return v.strip(" -")


def frac(d):
    y, m, dd = d
    if not m: return y + 0.5
    return round(y + (m - 1) / 12 + (max(dd, 1) - 1) / 365, 3)


def period(t):
    """(신설 시점, 근거, 폐선 시점, 근거, 이어진 번호). 시점은 연 + 월 소수(월을 모르면 연 + 0.5)"""
    oy = cy = None; oc = cc = ""; succ = ""
    sents = sentences(t)
    for s in sents:
        ds = dates_in(s)
        closing = re.search(r"폐선|폐지|운행을?\s*종료|운행이\s*중단|사라졌|없어졌|통합|흡수|번호[가도를]?\s*(?:\S+\s*)?(?:변경|바뀌|바꾸)|형간\s*전환|전환되", s)
        if oy is None and ds and not closing and not re.search(r"현재|지금", s) and re.search(r"신설|개통|운행을\s*시작|운행\s*개시|첫\s*운행|생겼|만들어|분리", s):
            oy = frac(ds[0]); oc = s[:160]
        ds = [x for x in ds if x != (2004, 7, 1)]  # 개편 날짜는 끝이 아니라 시작
        if closing and ds and not re.search(r"현재 이 번호|번호는 .*사용", s):
            cy = frac(ds[-1]); cc = s[:160]
            m = re.search(r"([A-Z]?\d{2,4}[A-Z]?(?:-\d)?)번(?:으로|이|과|에)\s*(?:번호가?\s*)?(?:변경|바뀌|전환|통합|흡수|되었)", s)
            if m: succ = m.group(1)
    m = re.search(r"이후\s*(?:의\s*)?(?:내용|연혁|역사)은\s*서울 버스 ([^\s]+?)\s*(?:문서|항목|참조|을|를)", t)
    if m: succ = m.group(1)
    if oy is None and REFORM.search(t):
        oy = 2004.5; oc = "개편 때부터(본문에 개편 언급)"
    if oy is not None and oy < 2004.5:
        oy = 2004.5  # 이 지도에서는 개편 노선망부터
    if (oy is None or (cy is not None and oy >= cy)) and cy is not None and cy > 2004.5:
        oy = 2004.5; oc = "신설 시점이 안 적혀 있어 개편 때부터 있던 것으로 봄(추정)"
    return oy, oc, cy, cc, succ


def main():
    d = json.load(open(SRC))
    nums2026 = {n["no"] for n in json.load(open(f"{B}/bus2026.json"))["nums"]}
    ry = json.load(open(f"{B}/route_years.json"))
    pages = d["pages"]
    out = []; stat = collections.Counter()
    for pg, secs in d["lists"].items():
        kind = pg.split("/폐선/")[1]
        cont = kind in CONT_PAGES
        for s in secs:
            m = HEAD.match(s["head"])
            if not m:
                continue
            nos = [x.strip() for x in m.group(1).split(",")]
            rest = m.group(2) or ""
            star = "★" in rest; wstar = "☆" in rest
            gi = re.findall(r"(\d)기", rest)
            text = s["text"]
            see = re.search(r"자세한 내용은 (서울 버스 \S+?) 문서", text) or re.search(r"(서울 버스 [^\s.]+?)\s*(?:문서|항목)?\s*(?:를|을)?\s*(?:참조|참고)", text)
            src = "목록"
            if see and len(text) < 900 and see.group(1) in pages:
                ptext = pages[see.group(1)]["text"]
                # 지금도 다니는 노선 문서면 1기·2기 부분만 쓴다
                cur = see.group(1).replace("서울 버스 ", "") in nums2026
                if cur and gi:
                    seg = re.split(r"\n\d+(?:\.\d+)*\. [^\n]*\n\[편집\]\n", ptext)
                    pick = [x for x in seg if re.search(rf"{gi[0]}기", x[:400])]
                    ptext = pick[0] if pick else ""
                elif cur:
                    ptext = ""
                if ptext:
                    text = text + "\n" + ptext; src = see.group(1)
            oy, oc, cy, cc, succ = period(text)
            sup = SUPP.get(see.group(1)) if see else None
            if sup and "oy" in sup:
                oy, cy = sup["oy"], sup["cy"]; oc = cc = "노선 문서: " + sup.get("note", ""); src = see.group(1)
            m2 = re.search(r"(?:^|\s)현\s*([A-Z]?\d{2,4}[A-Z]?)번", text) or re.search(r"이후\s*내용은\s*([A-Z]?\d{2,4}[A-Z]?)번", text)
            if m2 and not succ: succ = m2.group(1)
            village = bool(re.search(r"마을버스로\s*(?:\S+\s*)?(?:전환|강등|바뀌|변경)", text))
            via, vsrc = via_of(text)
            if sup and sup.get("via") and not via:
                via, vsrc = sup["via"], "노선 문서"
            for no in nos:
                rec = {"page": kind, "no": no, "head": s["head"], "star": star, "wstar": wstar, "gi": gi, "src": src,
                       "oy": oy, "oy_ctx": oc, "cy": cy, "cy_ctx": cc, "succ": succ, "via_src": vsrc, "via_raw": via[:400]}
                # 다른 번호로 이어진 노선(형간전환·번호변경)은 이어받은 번호가 2026년에도 있으면 그쪽이 이미 그려지므로 뺀다
                rec["village"] = village
                rec["see"] = see.group(1) if see else ""
                if succ and succ in nums2026 and cy is None:
                    rec["skip"] = f"{succ}번으로 이어져 2026년 노선망에 있음"
                if cont and (star or wstar):
                    rec["cont"] = True
                    if succ and succ in nums2026:
                        rec["skip"] = f"{succ}번으로 이어져 2026년 노선망에 있음"
                    elif cy is None and see and see.group(1).replace("서울 버스 ", "") in nums2026:
                        rec["skip"] = "번호가 바뀌어 지금 노선으로 이어짐"
                g26 = {re.sub(r"[AB]$", "", k): v for k, v in ry.items()}
                if not cont and star and re.sub(r"[AB]$", "", no) in g26 and (g26[re.sub(r"[AB]$", "", no)].get("oy") or 9999) <= (cy or 2004):
                    rec["skip"] = "번호·회사가 같은 지금 노선과 이어진 것으로 봄"
                if sup and "skip" in sup:
                    rec["skip"] = sup["skip"]
                if sup and sup.get("merged_into"):
                    rec["merged_into"] = sup["merged_into"]
                if cy is None and see and see.group(1).replace("서울 버스 ", "") in nums2026:
                    rec["skip"] = rec.get("skip") or "지금 노선 문서로 이어짐(같은 계보로 봄)"
                if cy is not None and cy < 2004.5:
                    rec["skip"] = "2004년 7월 전에 없어짐"
                if cy is None:
                    rec["skip"] = rec.get("skip") or ("마을버스로 바뀜(연도 못 찾음)" if village else "폐선 연도 못 찾음")
                toks = tokens(norm_via(via)) if via else []
                pts = []
                for t in toks:
                    loc = locate_tok(t)
                    pts.append({"label": t["label"], "lng": round(loc[0], 5) if loc else None, "lat": round(loc[1], 5) if loc else None})
                rec["pts"] = pts
                out.append(rec)
                stat["skip" if rec.get("skip") else "keep"] += 1
    # 신설 시점을 본문에서 못 찾은 노선은 나무위키 「YYYY년 개업한 버스 노선」 분류로 보완
    from namu_open_years import OPEN
    cat = collections.defaultdict(list)
    for y, sv in OPEN.items():
        for x in sv.split(","):
            x = x.strip()
            cat[x.replace("(폐선)", "")].append((y, "(폐선)" in x))
    for r in out:
        if r.get("skip") or not r["oy_ctx"].startswith("신설 시점이 안 적혀"): continue
        ys = [y for y, dead in cat.get(r["no"], []) if 2004 < y and y + 0.5 < (r["cy"] or 9999)]
        if ys:
            r["oy"] = max(ys) + 0.5 if len(ys) > 1 else ys[0] + 0.5
            r["oy_ctx"] = f"나무위키 분류 {int(r['oy'])}년 개업한 버스 노선"
        elif r["page"] in ("맞춤버스", "심야버스"):
            r["skip"] = "신설 시점 못 찾음(맞춤·심야는 개편 뒤에 생긴 유형)"
    # 형간전환·번호변경으로 다른 번호가 된 노선(간선·순환·광역·심야 문서의 ★☆)은 그 뒤 번호 쪽에서 그려지므로 뺀다
    for r in out:
        if r.get("cont") and not r.get("skip"):
            r["skip"] = "번호변경·형간전환(다른 번호로 이어짐)"
    # 번호가 바뀌어 이어진 경우: 뒤 번호는 앞 번호가 끝난 때부터
    kept = collections.defaultdict(list)
    for r in out:
        if not r.get("skip"): kept[r["no"]].append(r)
    for r in out:
        if r.get("skip") or not r.get("succ") or r["succ"] not in kept or r["cy"] is None: continue
        for t in kept[r["succ"]]:
            if t is not r and t["oy"] is not None and t["oy"] < r["cy"] and (t["cy"] or 9999) > r["cy"]:
                t["oy"] = r["cy"]; t["oy_ctx"] = f"{r['no']}번에서 번호가 바뀐 때부터"
    for r in out:
        if not r.get("skip") and r["oy"] is not None and r["cy"] is not None and r["cy"] <= r["oy"]:
            r["skip"] = "운행 기간이 0 이하(같은 해 신설·폐선 등)"
        if not r.get("skip") and r["oy"] is None:
            r["skip"] = "신설 시점 못 찾음"
    stat = collections.Counter("skip" if r.get("skip") else "keep" for r in out)
    json.dump(out, open(OUT, "w"), ensure_ascii=False, indent=0)
    keep = [r for r in out if not r.get("skip")]
    tot = sum(len(r["pts"]) for r in keep); hit = sum(1 for r in keep for p in r["pts"] if p["lng"])
    print(dict(stat), "via points", tot, "located", hit)
    print("skip reasons", collections.Counter(r["skip"] for r in out if r.get("skip")))
    print("keep with >=2 pts", sum(1 for r in keep if sum(1 for p in r["pts"] if p["lng"]) >= 2))
    print("keep by oy", sorted(collections.Counter(int(r["oy"]) for r in keep).items()))
    print("keep by cy", sorted(collections.Counter(int(r["cy"]) for r in keep).items()))


if __name__ == "__main__":
    main()
