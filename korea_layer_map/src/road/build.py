# assign.py 다음에 실행: 맞은편 차로·틈 메우기, GeoJSON, 통계
import json, collections
from scipy.spatial import cKDTree
E=[]  # (wi,k,midxy,len,refs)
for wi,w in enumerate(ways):
    for k in range(len(w["nodes"])-1):
        a,b=w["coords"][k],w["coords"][k+1]
        E.append((wi,k,((a[0]+b[0])/2*CX,(a[1]+b[1])/2*CY),hav(a,b),w["refs"]))
orig={wk:dict(v) for wk,v in state.items()}
def fill(radius,tag,base):
    by=collections.defaultdict(list)
    for wi,k,m,L,refs in E:
        if (wi,k) in base:
            for r in refs: by[r].append(((wi,k),m))
    trees={r:(cKDTree([m for _,m in v]),[wk for wk,_ in v]) for r,v in by.items()}
    n=0
    for wi,k,m,L,refs in E:
        if (wi,k) in state: continue
        best=None
        for r in refs:
            if r not in trees: continue
            t,keys=trees[r]; dd,ii=t.query(m)
            if dd<=radius and (best is None or dd<best[0]): best=(dd,keys[ii])
        if best:
            s=dict(base[best[1]]); s["fill"]=tag; state[(wi,k)]=s; n+=1
    return n
n1=fill(150,"맞은편 차로",orig)
snap={wk:dict(v) for wk,v in state.items()}
n2=fill(800,"틈 메움",snap)
tot=sum(e[3] for e in E)/1000
def L_of(pred): return sum(e[3] for e in E if pred((e[0],e[1])))/1000
print(f"전체 {tot:.0f}km(양방향 합), 구간표로 붙음 {L_of(lambda wk: wk in orig):.0f}, 맞은편 차로 {L_of(lambda wk: state.get(wk,{}).get('fill')=='맞은편 차로'):.0f}, 틈 메움 {L_of(lambda wk: state.get(wk,{}).get('fill')=='틈 메움'):.0f}, 안 붙음 {L_of(lambda wk: wk not in state):.0f}")
# 안 붙은 선 묶음
un=collections.defaultdict(lambda:[0,[]])
for wi,k,m,L,refs in E:
    if (wi,k) not in state:
        w=ways[wi]; key=(w["ref"],w["name"]); un[key][0]+=L; un[key][1].append(w["coords"][k])
print("안 붙은 선(노선별, 1km 넘는 것):")
for key,(L,cs) in sorted(un.items(),key=lambda x:-x[1][0]):
    if L<1000: continue
    xs=[c[0] for c in cs]; ys=[c[1] for c in cs]
    print(f"  {key} {L/1000:.1f}km  경도 {min(xs):.3f}~{max(xs):.3f} 위도 {min(ys):.3f}~{max(ys):.3f}")
# GeoJSON
feats=[]
def props(s,w):
    g=rows[s["geom"]]; rt=rows[s["route"]]
    return dict(ref=w["ref"],name=w["name"],osm_way=w["id"],
        geom_date=g["개통일"],geom_row=s["geom"],geom_kind=g["성격"],geom_section=g["구간"],
        route_date=rt["개통일"],route_row=s["route"],check=g["확인 정도"],fill=s.get("fill",""),note=w["patch"])
for wi,w in enumerate(ways):
    run=None
    for k in range(len(w["nodes"])-1):
        s=state.get((wi,k)); key=None if s is None else (s["geom"],s["route"],s.get("fill",""))
        if run and run[0]==key: run[2].append(w["coords"][k+1])
        else:
            if run: feats.append(run)
            run=[key,(wi,s),[w["coords"][k],w["coords"][k+1]]]
    if run: feats.append(run)
out=[]
for key,(wi,s),cs in feats:
    w=ways[wi]
    p=props(s,w) if s else dict(ref=w["ref"],name=w["name"],osm_way=w["id"],geom_date="",geom_row=None,geom_kind="",geom_section="",route_date="",route_row=None,check="",fill="안 붙음",note=w["patch"])
    out.append({"type":"Feature","properties":p,"geometry":{"type":"LineString","coordinates":[[round(x,5),round(y,5)] for x,y in cs]}})
json.dump({"type":"FeatureCollection","features":out},open(_W("road","재정고속도로_선형_20261127.geojson"),"w"),ensure_ascii=False,separators=(",",":"))
print("피처",len(out))
import pickle; pickle.dump(state,open(_W("road","state_filled.pkl"),"wb"))
