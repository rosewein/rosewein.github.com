# 양방향 차로 가운데 한쪽만 남기기: 노선번호마다 기준선(가장 긴 경로)을 잡아, 선의 진행 방향이 기준선 거리값을 늘리는 쪽만 남긴다
import os as _os, sys as _sys
_sys.path.insert(0, _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), ".."))
from paths import RAW as _RAW, D as _D, W as _W  # 경로는 src/paths.py 한곳에서 정한다
import json, math, collections, numpy as np
from scipy.spatial import cKDTree
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import dijkstra, connected_components
from shapely.geometry import LineString, MultiLineString
from shapely.ops import linemerge
CX=111320*math.cos(math.radians(36)); CY=110574
def P(c): return (c[0]*CX,c[1]*CY)
def L(cs): return sum(math.hypot((x2-x1)*CX,(y2-y1)*CY) for (x1,y1),(x2,y2) in zip(cs,cs[1:]))
F=json.load(open(_W("road","전국고속도로_선형_20261127.geojson")))["features"]
def first_ref(f):
    r=[x for x in f["properties"]["ref"].split(";") if x]
    return r[0] if r else ""
byref=collections.defaultdict(list)
for i,f in enumerate(F): byref[first_ref(f)].append(i)
allref=collections.defaultdict(list)
for i,f in enumerate(F):
    for r in [x for x in f["properties"]["ref"].split(";") if x]: allref[r].append(i)
dirn={}
def longest_path(idxs):
    # 피처 좌표로 노드 그래프(좌표 반올림으로 이음)
    key={}; pos=[]; R=[];C=[];V=[]
    def k(c):
        t=(round(c[0],6),round(c[1],6))
        if t not in key: key[t]=len(key); pos.append(P(c))
        return key[t]
    for i in idxs:
        cs=F[i]["geometry"]["coordinates"]
        for a,b in zip(cs,cs[1:]):
            u,v=k(a),k(b); d=math.hypot(*(np.subtract(P(a),P(b))))+1e-3
            R+=[u,v];C+=[v,u];V+=[d,d]
    n=len(key); M=coo_matrix((V,(R,C)),shape=(n,n)).tocsr(); pos=np.array(pos)
    nc,lab=connected_components(M,directed=False)
    big=np.argmax(np.bincount(lab)); s=int(np.where(lab==big)[0][0])
    d0=dijkstra(M,directed=False,indices=s); d0[np.isinf(d0)]=-1; a=int(d0.argmax())
    d1,pr=dijkstra(M,directed=False,indices=a,return_predecessors=True); d1c=d1.copy(); d1c[np.isinf(d1c)]=-1; b=int(d1c.argmax())
    seq=[b]
    while seq[-1]!=a: seq.append(int(pr[seq[-1]]))
    seq.reverse()
    pts=pos[seq]
    # 경로가 한쪽 차로로 내려갔다가 맞은편 차로로 돌아오면, 시작점에서 가장 먼 곳에서 자른다
    far=int(np.argmax(np.hypot(*(pts-pts[0]).T))); pts=pts[:far+1]
    ch=np.r_[0,np.cumsum(np.hypot(*np.diff(pts,axis=0).T))]
    # 25m 간격으로 촘촘하게
    dp=[];dc=[]
    for j in range(len(pts)-1):
        n_=max(1,int((ch[j+1]-ch[j])//25))
        for t in range(n_): dp.append(pts[j]+(pts[j+1]-pts[j])*t/n_); dc.append(ch[j]+(ch[j+1]-ch[j])*t/n_)
    return cKDTree(np.array(dp)),np.array(dc)
for r,idxs in allref.items():
    todo=set(i for i in byref.get(r,[]))
    pool=list(allref[r])
    for it in range(6):
        if not todo: break
        cand=[i for i in pool if i in todo] or list(todo)
        tree,dc=longest_path(cand if len(cand)>1 else pool)
        done=set()
        for i in todo:
            cs=F[i]["geometry"]["coordinates"]
            dd,ii=tree.query([P(c) for c in cs])
            if (dd<=300).mean()<0.8: continue
            ok=dd<=300; idx=np.where(ok)[0]
            dirn[i]=np.sign(dc[ii[idx[-1]]]-dc[ii[idx[0]]]) if len(idx)>1 else 0
            done.add(i)
        todo-=done
        if not done: break
    for i in todo: dirn[i]=0
for i in byref.get("",[]): dirn[i]=0
plus=[i for i in range(len(F)) if dirn.get(i,0)>=0]
# 맞은편이 없는 반대 방향 선(외줄 구간 등)은 살린다: 같은 노선번호의 남긴 선이 600m 안에 없는 경우만
trees={}
for r in set(first_ref(F[i]) for i in plus):
    q=[P(c) for i in plus if first_ref(F[i])==r for c in F[i]["geometry"]["coordinates"]]
    if q: trees[r]=cKDTree(np.array(q))
rescue=[]
for i in range(len(F)):
    if dirn.get(i,0)>=0: continue
    r=first_ref(F[i]); cs=F[i]["geometry"]["coordinates"]
    if r not in trees: rescue.append(i); continue
    q=[]
    for a,b in zip(cs,cs[1:]):
        pa,pb=np.array(P(a)),np.array(P(b)); n_=max(1,int(np.hypot(*(pb-pa))//25))
        for t in range(n_): q.append(pa+(pb-pa)*t/n_)
    dd,_=trees[r].query(np.array(q))
    if (dd>600).mean()>0.5: rescue.append(i)
keep=plus+rescue
tot=sum(L(f["geometry"]["coordinates"]) for f in F)/1000; kl=sum(L(F[i]["geometry"]["coordinates"]) for i in keep)/1000
print(f"전체 {tot:.0f}km → 남김 {kl:.0f}km (한쪽 방향 {len(plus)}개 + 맞은편 없는 선 {len(rescue)}개)")
by=collections.defaultdict(list)
for i in keep:
    p=F[i]["properties"]
    k=tuple(p.get(x) or "" for x in ("owner","row","route_row","route_date","geom_date","geom_kind","check","operator","section"))+(first_ref(F[i]),)
    by[k].append(LineString(F[i]["geometry"]["coordinates"]))
out=[]; tol=0.00022
for k,ls in by.items():
    m=linemerge(MultiLineString(ls)); parts=[m] if m.geom_type=="LineString" else list(m.geoms)
    for g in parts:
        s=g.simplify(tol,preserve_topology=False)
        cs=[[round(x,4),round(y,4)] for x,y in s.coords]; cs=[c for j,c in enumerate(cs) if j==0 or c!=cs[j-1]]
        if len(cs)<2: continue
        owner,row,rrow,rd,gd,gk,chk,op,sec,ref=k
        out.append({"type":"Feature","properties":{"ref":ref,"owner":owner,"route_date":rd,"geom_date":gd,"row":row,"route_row":rrow,"kind":gk,"section":sec,"operator":op,"check":chk},"geometry":{"type":"LineString","coordinates":cs}})
json.dump({"type":"FeatureCollection","features":out},open(_D("road","전국고속도로_단순_20261127.geojson"),"w"),ensure_ascii=False,separators=(",",":"))
cum=json.load(open(_W("road","cum_len.json")))
yr=collections.defaultdict(float)
for f in out:
    if f["properties"]["route_date"]: yr[int(f["properties"]["route_date"][:4])]+=L(f["geometry"]["coordinates"])/1000
acc=0; res={}
for y in range(1968,2027): acc+=yr.get(y,0); res[y]=acc
print("피처",len(out))
for y in (1970,1980,1990,2000,2010,2020,2026): print(y,round(res[y]),"/ 양방향 절반",round(cum[str(y)]), f"{res[y]/cum[str(y)]-1:+.1%}")
cat=collections.Counter(); byr=collections.Counter()
for i in range(len(F)):
    d_=dirn.get(i,0); c=("+" if d_>0 else "0" if d_==0 else "-")+("(살림)" if i in set(rescue) else "")
    l=L(F[i]["geometry"]["coordinates"])/1000; cat[c]+=l
    if d_==0: byr[F[i]["properties"]["ref"]]+=l
print({k:round(v) for k,v in cat.items()})
print("방향 0인 선, 노선번호별:",[(k,round(v)) for k,v in byr.most_common(15)])
pr=collections.defaultdict(lambda:[0,0,0]); rs=set(rescue)
for i in range(len(F)):
    r=first_ref(F[i]); l=L(F[i]["geometry"]["coordinates"])/1000; d_=dirn.get(i,0)
    pr[r][0 if d_>0 else 1 if d_<0 else 2]+=l
    if i in rs: pr[r][2]+=l
print("노선 +, -, (0+살림)")
for r,(a,b,c) in sorted(pr.items(),key=lambda x:-abs(x[1][0]-x[1][1])-x[1][2])[:20]: print(r,round(a),round(b),round(c))
