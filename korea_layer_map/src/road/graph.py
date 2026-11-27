import os as _os, sys as _sys
_sys.path.insert(0, _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), ".."))
from paths import RAW as _RAW, D as _D, W as _W  # 경로는 src/paths.py 한곳에서 정한다
import json, collections, math
import numpy as np
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import dijkstra
SRC=_W("road","osm_mw2.json")
def hav(a,b):
    (x1,y1),(x2,y2)=a,b
    dx=(x2-x1)*111320*math.cos(math.radians((y1+y2)/2)); dy=(y2-y1)*110574
    return math.hypot(dx,dy)
def load():
    d=json.load(open(SRC))
    ways=[w for w in d["ways"] if w["op"] in ("한국도로공사","") and w["name"] not in ("평택화성고속도로","스마트하이웨이 체험도로","담양로","용인서울고속도로")]
    jname={j["id"]:j["name"] for j in d["jn"] if j["name"]}
    jpos={j["id"]:(j["lon"],j["lat"]) for j in d["jn"]}
    return ways,jname,jpos
class G:
    """노드 단위 그래프. refs: 이 그래프에 넣을 노선번호 집합(None이면 전부)"""
    def __init__(s,ways,refs=None):
        s.ways=[w for w in ways if refs is None or set(w["ref"].split(";"))&refs]
        idx={}; pos=[]
        rows=[];cols=[];vals=[]
        s.edge_way={}
        for wi,w in enumerate(s.ways):
            for k,(n,c) in enumerate(zip(w["nodes"],w["coords"])):
                if n not in idx: idx[n]=len(idx); pos.append(c)
            for k in range(len(w["nodes"])-1):
                a=idx[w["nodes"][k]]; b=idx[w["nodes"][k+1]]
                L=hav(w["coords"][k],w["coords"][k+1])
                rows+= [a,b]; cols+=[b,a]; vals+=[L+1e-3,L+1e-3]
                s.edge_way[(a,b)]=(wi,k); s.edge_way[(b,a)]=(wi,k)
        s.idx=idx; s.pos=np.array(pos); s.n=len(idx)
        s.M=coo_matrix((vals,(rows,cols)),shape=(s.n,s.n)).tocsr()
    def sp(s,srcs):
        return dijkstra(s.M,directed=False,indices=srcs,return_predecessors=True)
