import os as _os, sys as _sys
_sys.path.insert(0, _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), ".."))
from paths import RAW as _RAW, D as _D, W as _W  # 경로는 src/paths.py 한곳에서 정한다
import csv, re, collections
rows=list(csv.DictReader(open(_RAW/"한국도로공사_고속도로 건설공사_20260729.csv",encoding="cp949",newline="")))
out=[]
for r in rows:
    p=r["공사기간"].replace("～","~").replace(" ","")
    m=re.match(r"^(\d{4})(?:[-.](\d{1,2}))?(?:[-.](\d{1,2}))?~(\d{4})(?:[-.](\d{1,2}))?(?:[-.](\d{1,2}))?$",p)
    if not m: out.append((r["구분"],r["구간"],r["연장(km)"],p,"?","?")); continue
    s="-".join(x for x in m.groups()[:3] if x); e="-".join(x for x in m.groups()[3:] if x)
    prec="일" if m.group(6) else ("월" if m.group(5) else "년")
    out.append((r["구분"],r["구간"],r["연장(km)"],s,e,prec))
for o in out: print(" | ".join(o))
print()
print("정밀도", collections.Counter(o[5] for o in out))
print("끝 해 10년", sorted(collections.Counter((int(o[4][:4])//10*10) if o[4][:4].isdigit() else "?" for o in out).items(), key=str))
print("2026 이후 끝", [(o[0],o[1],o[4]) for o in out if o[4][:4].isdigit() and int(o[4][:4])>=2026])
print("노선 수", len(set(o[0] for o in out)), "합계 km", round(sum(float(o[2] or 0) for o in out),1))
