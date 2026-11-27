# 고속도로: OSM(Geofabrik 2026-11-24) highway=motorway 선형 + 구간별 처음 개통일(hw_segments.py)
import json,re,sys,math
sys.path.insert(0,'/home/claude/sudo2')
from hw_segments import SEG, SRC
from build2_util import rnd
import networkx as nx
from shapely.geometry import shape, Point, box, LineString
from shapely.ops import linemerge
from collections import defaultdict
BB=box(125.9,36.6,128.3,38.5); FR=box(126.0,36.8,128.05,38.35)
def norm(n): return re.sub(r'\s|IC|JC|JCT|나들목|분기점|요금소|교차로|\(.*?\)|하이패스|휴게소','',n or '')
REF={'1':'경부','120':'경인','100':'외곽','15':'서해안','50':'영동','110':'제2경인','35':'중부','37':'제2중부','45':'중부내륙','40':'평택제천','29':'세종포천','60':'서울양양','52':'광주원주','130':'공항','153':'평택시흥','400':'제2순환','55':'중앙'}
NAMES=[('경부고속도로','경부'),('제2경인','제2경인'),('인천대교','제2경인'),('경인고속도로','경인'),('수도권제1순환','외곽'),('서해안고속도로','서해안'),('영동고속도로','영동'),
 ('제2중부','제2중부'),('중부내륙','중부내륙'),('중부고속도로','중부'),('평택제천','평택제천'),('세종포천','세종포천'),('서울양양','서울양양'),('광주원주','광주원주'),('인천국제공항','공항'),
 ('평택시흥','평택시흥'),('용인서울','용인서울'),('오산화성','오산화성'),('평택화성','평택화성'),('익산평택','익산평택'),('수도권제2순환','제2순환'),('중앙고속도로','중앙'),('평택파주고속도로 지선','수원광명')]
J=defaultdict(list); WAYS=[]; ORPH=[]
for ln in open('/home/claude/raw/osm/mw.geojsonseq'):
    ln=ln.strip('\x1e\n ')
    if not ln: continue
    f=json.loads(ln); p=f['properties']; g=shape(f['geometry'])
    if not g.intersects(BB): continue
    if f['geometry']['type']=='Point':
        if p.get('name'): J[norm(p['name'])].append(g)
        continue
    if p.get('highway')!='motorway' or not g.intersects(FR): continue
    nm=p.get('name',''); ref=p.get('ref','')
    if '스마트하이웨이' in nm: continue
    rt=None
    for k,v in NAMES:
        if k in nm: rt=v; break
    if rt=='수원광명' and False: pass
    if '수원문산' in nm: rt='수원광명' if g.centroid.y<37.5 else '서울문산'
    if rt is None: rt=REF.get(ref.split(';')[0])
    if rt is None:
        if not nm and not ref: ORPH.append(g)
        continue
    rts={rt}|{REF[r] for r in ref.split(';') if r in REF}
    WAYS.append({'rt':rt,'rts':rts,'g':g,'nm':nm,'ref':ref,'d':None,'s':None})
# 이름·번호 없는 조각은 맞닿은(가까운) 노선에 붙임
for g in ORPH:
    best=min(WAYS,key=lambda w:w['g'].distance(g))
    if best['g'].distance(g)<0.002: WAYS.append({'rt':best['rt'],'rts':set(best['rts']),'g':g,'nm':best['nm'],'ref':best['ref'],'d':None,'s':None})
byrt=defaultdict(list)
for w in WAYS:
    for r in w['rts']: byrt[r].append(w)
K=lambda c:(round(c[0],6),round(c[1],6))
def graph(ws):
    G=nx.Graph()
    for i,w in enumerate(ws):
        cs=list(w['g'].coords)
        for a,b in zip(cs,cs[1:]):
            G.add_edge(K(a),K(b),w=math.dist(a,b),i=i)
    # 맞은편 차로·끊긴 선을 잇는 가상 연결(가까운 점끼리, 무게를 크게 줌)
    cell=defaultdict(list); C=0.0007
    for n in G.nodes: cell[(int(n[0]/C),int(n[1]/C))].append(n)
    for (cx,cy),ns in cell.items():
        near=[m for dx in (-1,0,1) for dy in (-1,0,1) for m in cell.get((cx+dx,cy+dy),[])]
        for n in ns:
            for m in near:
                if m<=n: continue
                d=math.dist(n,m)
                if d<C and not G.has_edge(n,m): G.add_edge(n,m,w=d*6+0.0005,i=-1)
    # 연결선(램프)을 빼서 끊긴 덩어리를 1.5km 안에서 가장 가까운 점끼리 이음
    import numpy as np
    from scipy.spatial import cKDTree
    tried=set()
    while True:
        comps=sorted(nx.connected_components(G),key=len)
        cand=[c for c in comps if min(c) not in tried]
        if len(comps)<2 or not cand: break
        small=list(cand[0]); sset=set(small); rest=[n for n in G.nodes if n not in sset]
        t=cKDTree(np.array(rest)); dd,ii=t.query(np.array(small))
        k=int(np.argmin(dd))
        if dd[k]>0.03: tried.add(min(cand[0])); continue
        G.add_edge(small[k],rest[ii[k]],w=dd[k]*6+0.002,i=-1)
    return G
def nearest(G,pt):
    return min(G.nodes,key=lambda n:(n[0]-pt.x)**2+(n[1]-pt.y)**2)
unfound=[]
for rt,ws in byrt.items():
    G=graph(ws); segs=SEG.get(rt)
    if not segs: print('no segs for',rt); continue
    def node(name,other=None):
        if name.startswith('END_'):
            ends=[n for n in G.nodes if sum(1 for m in G[n] if G[n][m]['i']>=0)==1]
            f={'N':lambda n:-n[1],'S':lambda n:n[1],'E':lambda n:-n[0],'W':lambda n:n[0]}[name[4]]
            return min(ends,key=f)
        if name=='END':
            ends=[n for n in G.nodes if sum(1 for m in G[n] if G[n][m]['i']>=0)==1]
            if other is None: return ends[0]
            dist=nx.single_source_dijkstra_path_length(G,other,weight='w')
            return max((n for n in ends if n in dist),key=lambda n:dist[n])
        cands=J.get(name,[])
        best=None
        for c in cands:
            n=nearest(G,c); d=math.dist(n,(c.x,c.y))
            if best is None or d<best[0]: best=(d,n)
        if best is None or best[0]>0.02: unfound.append((rt,name,best and round(best[0],3))); return None
        return best[1]
    for d0,a,b,sk in segs:
        if a=='ALL':
            idx=range(len(ws))
        elif a=='BOX':
            bx=box(*b); idx=[i for i,w in enumerate(ws) if bx.contains(w['g'].centroid)]
        else:
            na=node(a) if a!='END' else None; nb=node(b) if b!='END' else None
            if a=='END' and nb: na=node('END',nb)
            if b=='END' and na: nb=node('END',na)
            if na is None or nb is None: continue
            idx=set()
            try:
                path=nx.shortest_path(G,na,nb,weight='w')
                used=set()
                for u,v in zip(path,path[1:]):
                    used.add(frozenset((u,v)))
                    if G[u][v]['i']>=0: idx.add(G[u][v]['i'])
                # 맞은편 차로: 처음 길의 무게를 크게 해서 한 번 더 찾음
                path2=nx.shortest_path(G,na,nb,weight=lambda u,v,d: d['w']*25 if frozenset((u,v)) in used else d['w'])
                for u,v in zip(path2,path2[1:]):
                    if G[u][v]['i']>=0: idx.add(G[u][v]['i'])
            except nx.NetworkXNoPath: unfound.append((rt,a+'-'+b,'nopath')); continue
        for i in idx:
            w=ws[i]
            if w['d'] is None or d0<w['d']: w['d'],w['s']=d0,sk
    pre=[w for w in ws if not w['d'] and w['rt']==rt]
    if pre:
        import collections
        ln=sum(w['g'].length for w in pre)*100
        if ln>3: print('PRE-unassigned',rt,round(ln,1),'bbox',[round(v,3) for v in __import__('shapely').ops.unary_union([w['g'] for w in pre]).bounds])
        if ln>3:
            u=linemerge([w['g'] for w in pre]); ls=[u] if u.geom_type=='LineString' else list(u.geoms)
            for l in sorted(ls,key=lambda l:-l.length)[:8]:
                if l.length*100>0.8: print('   piece',round(l.length*100,1),[round(v,3) for v in l.coords[0]],[round(v,3) for v in l.coords[-1]])
    # 끝점이 맞닿은 선에서 날짜를 물려받음(같은 노선)
    for it in range(4):
        ch=0
        ep={}
        for w in ws:
            if w['d']:
                for c in (w['g'].coords[0],w['g'].coords[-1]): ep.setdefault(K(c),w)
        for w in ws:
            if w['d']: continue
            for c in (w['g'].coords[0],w['g'].coords[-1]):
                o=ep.get(K(c))
                if o: w['d'],w['s']=o['d'],o['s']; ch+=1; break
        if not ch: break
    # 맞은편 차로 등 못 받은 것은 같은 노선의 가까운 선에서 물려받음
    for it in range(6):
        done=[w for w in ws if w['d']]
        for w in ws:
            if w['d']: continue
            m=w['g'].interpolate(0.5,normalized=True)
            best=min(done,key=lambda o:o['g'].distance(m),default=None)
            if best and best['g'].distance(m)<0.003: w['d'],w['s']=best['d'],best['s']
print('unfound',unfound)
left=[(w['rt'],w['nm'],round(w['g'].length*100,2),round(w['g'].centroid.x,3),round(w['g'].centroid.y,3)) for w in WAYS if not w['d']]
print('unassigned',len(left),sum(x[2] for x in left))
_c=defaultdict(float)
for x in left: _c[x[0]]+=x[2]
print('left by route',{k:round(v,2) for k,v in _c.items()})
print([x for x in left if x[0]!='제2순환'][:30])
# 같은 노선·날짜끼리 이어 붙여 줄임
out=[]
grp=defaultdict(list)
for w in WAYS:
    if w['d']: grp[(w['rt'],w['d'],w['s'])].append(w['g'])
for (rt,d0,sk),gs in grp.items():
    m=linemerge(gs); ls=[m] if m.geom_type=='LineString' else list(m.geoms)
    for l in ls:
        l=l.simplify(0.0002)
        out.append({'r':rt,'d':d0,'s':sk,'p':rnd(list(l.coords))})
json.dump({'hw':out,'src':SRC},open('/home/claude/sudo2/hw.json','w'),ensure_ascii=False)
from collections import Counter
print(len(out), Counter((o['r'],o['d']) for o in out).most_common(80))
