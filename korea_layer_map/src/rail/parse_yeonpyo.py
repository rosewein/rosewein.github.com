import os as _os, sys as _sys
_sys.path.insert(0, _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), ".."))
from paths import RAW as _RAW, D as _D, W as _W  # 경로는 src/paths.py 한곳에서 정한다
import csv,re,json,collections
R=list(csv.DictReader(open(_RAW/"국가철도공단_철도 통합 연표_20260303.csv",encoding="utf-8-sig")))
SEC=re.compile(r"([가-힣A-Za-z0-9]+?)(?:역)?(?:\([^)]*\))?\s*[~\-–∼～]\s*(?:[가-힣A-Za-z0-9]+?(?:역)?\s*[~\-–∼～]\s*)?([가-힣A-Za-z0-9]+?)(?:역)?(?=\s|간|구간|$|\)|,|\.|\(|복|전|단|개|연|사|이|부)")
KM=re.compile(r"([0-9]+(?:\.[0-9]+)?)\s*(?:km|㎞|킬로)")
LINE=re.compile(r"([가-힣]{1,6}선)(?=\s|\(|$)")
def kind(s,t):
    if t=="사고·재해": return None
    if re.search(r"착공|기공|계획|타당성|예정|고시|승인",s): return None
    if re.search(r"전철화|전철\s*개통|복선\s*전철|복선전철|전철 연장|광역 전철",s): k="전철"
    elif re.search(r"복복선|2복선|3복선|복선",s): k="복선"
    elif re.search(r"이설|직선화|신선",s): k="이설"
    elif re.search(r"폐선|폐지|영업\s*중지|운행\s*중지|운행\s*중단|철거",s): k="폐지"
    elif re.search(r"개통|영업\s*개시|운수\s*영업|개업",s): k="개통"
    else: return None
    if re.search(r"여객|화물|열차|통일호|비둘기|새마을|무궁화|소화물|객차",s) and k=="폐지": k="여객 중지"
    return k
out=[]
for r in R:
    s=r["요약내용"].strip().strip('"').strip()
    k=kind(s,r["사건유형"])
    if not k: continue
    m=SEC.search(s)
    if not m: continue
    km=KM.search(s); ln=LINE.search(s)
    date=r["이벤트일자"] or (r["연도"]+("-"+r["월"].zfill(2) if r["월"] and r["월"]!="0" else ""))
    out.append(dict(no=int(r["연표순번"]),date=date,prec=r["날짜정밀도"],kind=k,line_rel=r["관계노선"],line_txt=ln.group(1) if ln else "",a=m.group(1),b=m.group(2),km=km.group(1) if km else "",text=s,imp=r["중요도"],org=r["관련기관"]))
json.dump(out,open(_W("rail","yp_events.json"),"w"),ensure_ascii=False,indent=0)
c=collections.Counter(o["kind"] for o in out); print(len(out),dict(c))
