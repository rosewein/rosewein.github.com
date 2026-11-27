import os as _os, sys as _sys
_sys.path.insert(0, _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), ".."))
from paths import RAW as _RAW, D as _D, W as _W  # 경로는 src/paths.py 한곳에서 정한다
import json, csv, math, sys, os, collections
import numpy as np
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import dijkstra, connected_components
from scipy.spatial import cKDTree
sys.path.insert(0,os.path.dirname(os.path.abspath(__file__)))
from names import norm
from mapping import M, NONE
SRC=_W("road","osm_mw2.json")
TABLE=_D("road","재정고속도로_구간표_20261127.csv")
CX=111320*math.cos(math.radians(36)); CY=110574
def xy(c): return (c[0]*CX, c[1]*CY)
def hav(a,b):
    dx=(b[0]-a[0])*111320*math.cos(math.radians((a[1]+b[1])/2)); dy=(b[1]-a[1])*CY
    return math.hypot(dx,dy)
d=json.load(open(SRC))
ways=[]
for w in d["ways"]:
    if w["name"] in ("평택화성고속도로","스마트하이웨이 체험도로","담양로","용인서울고속도로"): continue
    if w["op"] in ("한국도로공사",""):
        w=dict(w); w["refs"]=set(r for r in w["ref"].split(";") if r); w["patch"]=""; ways.append(w)
    elif w["ref"]=="55" and "대구부산" in w["op"] and max(y for x,y in w["coords"])<35.2785:
        w=dict(w); w["refs"]={"55대저"}; w["patch"]="운영자 태그 新대구부산(대동JC 남쪽)"; ways.append(w)
anch=collections.defaultdict(list)
for j in d["jn"]:
    if not j["name"]: continue
    for nm in j["name"].split(";"):
        if any(k in nm for k in ("휴게소","쉼터","영업소","요금소","주차")): continue
        b,t=norm(nm); anch[b+t].append(xy((j["lon"],j["lat"])))
class G:
    def __init__(s,refs):
        s.W=[(wi,w) for wi,w in enumerate(ways) if w["refs"]&refs]
        idx={}; pos=[]; R=[];C=[];V=[]
        s.ek={}  # (a,b)->(wi,k)
        for wi,w in s.W:
            for n,c in zip(w["nodes"],w["coords"]):
                if n not in idx: idx[n]=len(idx); pos.append(c)
            for k in range(len(w["nodes"])-1):
                a=idx[w["nodes"][k]]; b=idx[w["nodes"][k+1]]
                L=hav(w["coords"][k],w["coords"][k+1])+1e-3
                R+=[a,b];C+=[b,a];V+=[L,L]; s.ek[(a,b)]=(wi,k); s.ek[(b,a)]=(wi,k)
        s.n=len(idx); s.pos=np.array(pos); s.xy=np.c_[s.pos[:,0]*CX,s.pos[:,1]*CY]
        s.M=coo_matrix((V,(R,C)),shape=(s.n,s.n)).tocsr()
        s.M.sum_duplicates()
        s.nc,s.lab=connected_components(s.M,directed=False)
        s.deg=np.array([len(set(s.M.indices[s.M.indptr[i]:s.M.indptr[i+1]])) for i in range(s.n)])
_cache={}
def graph(refstr):
    k=frozenset(refstr.split(","))
    if k not in _cache: _cache[k]=G(set(k))
    return _cache[k]
SPECIAL={}
def cand(g,spec,comp):
    """spec에 맞는 (노드번호 배열, 기준점 배열, 허용 거리)"""
    nodes=np.where(g.lab==comp)[0]
    if spec.startswith("끝@"):
        x,y=map(float,spec[2:].split(",")); pts=[xy((x,y))]; nodes=nodes[g.deg[nodes]==1]; th=8000
    elif spec.startswith("@"):
        if spec in SPECIAL: pts=[SPECIAL[spec]]
        else: x,y=map(float,spec[1:].split(",")); pts=[xy((x,y))]
        th=3000
    else:
        b,t=norm(spec); pts=anch.get(b+t,[]); th=1500
        if not pts: raise KeyError(spec)
    return nodes,np.array(pts),th
def nearest(g,nodes,pts,th,ok=None):
    if ok is not None: nodes=nodes[ok[nodes]]
    if len(nodes)==0: return None
    t=cKDTree(g.xy[nodes]); dd,ii=t.query(pts)
    j=int(np.argmin(dd))
    return int(nodes[ii[j]]) if dd[j]<=th else None
def path(g,a,b):
    dist,pred=dijkstra(g.M,directed=False,indices=a,return_predecessors=True)
    if np.isinf(dist[b]): return None,dist
    seq=[b]
    while seq[-1]!=a: seq.append(int(pred[seq[-1]]))
    seq.reverse(); return seq,dist
def within(g,nodes,pts,th):
    if len(nodes)==0: return np.array([],int)
    t=cKDTree(g.xy[nodes]); hit=set()
    for lst in t.query_ball_point(pts,th):
        hit.update(lst)
    return nodes[sorted(hit)] if hit else np.array([],int)
def pick(g,cands,pts,dist,exclude):
    """기준점에 가장 가까운 무리(+80m) 가운데 그래프 거리가 가장 짧은 노드"""
    c=cands[np.isfinite(dist[cands])&(cands!=exclude)]
    if len(c)==0: return None
    sd,_=cKDTree(pts).query(g.xy[c])
    pool=c[sd<=sd.min()+80]
    return int(pool[np.argmin(dist[pool])])
def leg_paths(refstr,A,B):
    g=graph(refstr); out=[]
    if A=="ALL":
        edges={(min(a,b),max(a,b)) for (a,b) in g.ek}
        L=sum(g.M[a,b] for a,b in edges)/1000
        return g,[("ALL",sorted(edges),L)]
    for comp in range(g.nc):
        na,pa,ta=cand(g,A,comp); nb,pb,tb=cand(g,B,comp)
        A_ok=within(g,na,pa,ta); B_ok=within(g,nb,pb,tb)
        if len(A_ok)==0 or len(B_ok)==0: continue
        a1=nearest(g,na,pa,ta)
        da,_=dijkstra(g.M,directed=False,indices=a1,return_predecessors=True)
        b1=pick(g,B_ok,pb,da,a1)
        if b1 is None: continue
        s1,_=path(g,a1,b1); L1=da[b1]/1000; out.append((comp,s1,L1))
        far=A_ok[da[A_ok]>3000]
        if len(far)==0: continue
        a2=nearest(g,far,pa,ta)
        if a2 is None: continue
        d2,_=dijkstra(g.M,directed=False,indices=a2,return_predecessors=True)
        b2=pick(g,B_ok,pb,d2,a2)
        if b2 is None: continue
        s2,_=path(g,a2,b2); L2=d2[b2]/1000
        e1=set(edges_of(s1)); e2=set(edges_of(s2))
        if 0.8<L2/max(L1,1e-6)<1.25 and len(e1&e2)<0.2*len(e2): out.append((comp,s2,L2))
    return g,out
def edges_of(seq): return [(min(a,b),max(a,b)) for a,b in zip(seq,seq[1:])]
# 향호리 근처 경계점: 동해고속도로 강릉JC에서 남양양IC 쪽으로 12.5km
g65,ps=leg_paths("65","강릉JC","남양양IC")
comp,seq,L=ps[0]; acc=0
for a,b in zip(seq,seq[1:]):
    acc+=g65.M[a,b]
    if acc>=12500: SPECIAL["@향호"]=tuple(g65.xy[b]); hyang=g65.pos[b]; break
rows={int(r["순번"]):r for r in csv.DictReader(open(TABLE,encoding="utf-8-sig"))}
order=sorted(rows,key=lambda i:(rows[i]["개통일"],i))
state={}  # (wi,k) -> dict
report=[]
for i in order:
    r=rows[i]; spec=M[i]
    if spec==NONE: report.append((i,r,"선형 없음",[],0)); continue
    kind="이설" if r["성격"]=="선형 이설" else "신설"
    legs=[]; tot=0
    for refstr,A,B in spec:
        g,ps=leg_paths(refstr,A,B)
        if not ps: legs.append((refstr,A,B,"경로 못 찾음",[])); continue
        lens=[round(p[2],1) for p in ps]; legs.append((refstr,A,B,"",lens))
        tot+=ps[0][2] if ps[0][0]!="ALL" else ps[0][2]/2
        for comp,seq,L in ps:
            es=seq if comp=="ALL" else edges_of(seq)
            for a,b in es:
                wk=g.ek[(a,b)]; s=state.setdefault(wk,{})
                if kind=="신설":
                    if "route" not in s: s["route"]=i
                    if "geom" not in s: s["geom"]=i
                else:
                    s["geom"]=i
                    if "route" not in s: s["route"]=i
    report.append((i,r,"",legs,tot))
json.dump({"state":{f"{w}:{k}":v for (w,k),v in state.items()},"hyang":list(hyang)},open(_W("road","state.json"),"w"))
import pickle; pickle.dump((report,state),open(_W("road","run.pkl"),"wb"))
for i,r,flag,legs,tot in sorted(report):
    km=r["연장(km)"]
    if flag: print(f"{i:3} {r['개통일']} {r['구간']}: {flag}"); continue
    ls="; ".join(f"{rs}:{A}→{B} {e or lens}" for rs,A,B,e,lens in legs)
    print(f"{i:3} {r['개통일']} {r['구간']} 표 {km} / 잰 {tot:.1f} | {ls}")
