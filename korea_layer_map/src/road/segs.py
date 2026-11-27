import os as _os, sys as _sys
_sys.path.insert(0, _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), ".."))
from paths import RAW as _RAW, D as _D, W as _W  # 경로는 src/paths.py 한곳에서 정한다
import json, collections, math, sys
d=json.load(open(_W("road","osm_mw2.json"))); wf={r['id']:r for r in json.load(open(_W("road","way_first.json")))}
jn={j['id']:j for j in d['jn'] if j['name']}
def dist(a,b): return math.hypot((a[0]-b[0])*88.0,(a[1]-b[1])*111.0)
W=[w for w in d['ways'] if w['id'] in wf and w['op'] in ('한국도로공사','') and w['name']!='평택화성고속도로']
key=lambda w:(w['ref'].split(';')[0] or w['name'], wf[w['id']]['first'] or 'none')
groups=collections.defaultdict(list)
for w in W: groups[key(w)].append(w)
out=[]
for (ref,ed),ws in groups.items():
    # 같은 노선·같은 판끼리 노드를 공유하면 한 덩어리
    parent={}
    def f(x):
        while parent.setdefault(x,x)!=x: parent[x]=parent[parent[x]]; x=parent[x]
        return x
    for w in ws:
        for n in w['nodes'][1:]: parent[f(w['nodes'][0])]=f(n) if f(w['nodes'][0])!=f(n) else f(n)
    comp=collections.defaultdict(list)
    for w in ws: comp[f(w['nodes'][0])].append(w)
    for c in comp.values():
        L=sum(wf[w['id']]['len'] for w in c)/1000
        names={}
        for w in c:
            for n in w['nodes']:
                if n in jn: names[jn[n]['name']]=(jn[n]['lon'],jn[n]['lat'])
        pts=[p for w in c for p in (w['coords'][0],w['coords'][-1])]
        a,b=max(((p,q) for p in pts for q in pts),key=lambda pq:dist(*pq))
        def near(p):
            if not names: return ''
            nm,pos=min(names.items(),key=lambda kv:dist(kv[1],p)); return nm if dist(pos,p)<8 else ''
        out.append(dict(ref=ref,ed=ed,km=round(L,1),name=c[0]['name'],a=near(a),b=near(b),span=round(dist(a,b),1),n=len(c),lon=round(a[0],3),lat=round(a[1],3)))
out.sort(key=lambda r:(r['ed'],r['ref']))
json.dump(out,open(_W("road","segs.json"),"w"),ensure_ascii=False,indent=0)
EDS=sorted(set(r['ed'] for r in out))
for e in EDS:
    rs=[r for r in out if r['ed']==e and r['km']>=3]
    print(f"== {e}: {sum(r['km'] for r in out if r['ed']==e):.0f}km (양방향 합), 3km 이상 덩어리 {len(rs)}개")
    if e!='2008-11-05':
        for r in sorted(rs,key=lambda r:-r['km'])[:40]: print(f"   {r['ref']:>4} {r['name'][:12]:12s} {r['km']:6.1f} {r['a']}~{r['b']} (직선 {r['span']}km)")
