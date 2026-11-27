import os as _os, sys as _sys  # paths.py 찾기: 이 파일 폴더에서 위로 올라감(저장소 src/, 작업 공간 $MLM_SUDO·$MLM_SUDO2)
_d = _os.path.dirname(_os.path.abspath(__file__))
while _d != _os.path.dirname(_d) and not _os.path.isfile(_os.path.join(_d, 'paths.py')):
    _d = _os.path.dirname(_d)
_sys.path.insert(1, _d)
from paths import PAGE_DATA, RAW, SEOUL  # noqa: E402
import json, pickle, re, sqlite3, shapely.wkb
from shapely.geometry import mapping, LineString, Polygon, MultiPolygon
from shapely.geometry.polygon import orient
from shapely.ops import unary_union, polylabel
h45,h55=pickle.load(open('hgis.pkl','rb'))
old=json.load(open(PAGE_DATA))
def rnd(o):
    if isinstance(o,(list,tuple)):
        if o and isinstance(o[0],(int,float)): return [round(o[0],4),round(o[1],4)]
        return [rnd(x) for x in o]
    return o
def geo(g):
    g=g.simplify(0.0006,preserve_topology=True)
    if g.geom_type=='GeometryCollection': g=unary_union([x for x in g.geoms if x.area>0])
    if g.geom_type=='Polygon': g=orient(g,-1.0)
    elif g.geom_type=='MultiPolygon': g=MultiPolygon([orient(p,-1.0) for p in g.geoms])
    return {'type':g.geom_type,'coordinates':rnd(mapping(g)['coordinates'])}
def lab(g):
    if g.geom_type=='MultiPolygon': g=max(g.geoms,key=lambda p:p.area)
    try: p=polylabel(g,0.003)
    except Exception: p=g.representative_point()
    return [round(p.x,4),round(p.y,4)]
TR={1:'HGIS 신뢰도 1(확실)',2:'HGIS 신뢰도 2(유력)',3:'HGIS 신뢰도 3(추정)',4:'HGIS 신뢰도 4(뜻 설명 없음)'}
def kind45(x):
    if x['n']=='한성부': return 2
    return 1 if x['t'] in ('府','市') else 0
# ---- snapshot dates (pre-1975) ----
d45=sorted(set(x['b'] for x in h45))
gapd=['19450815','19460928','19490815','19530727','19541117']
d55=sorted(set(x['b'] for x in h55))
pre=[('h45',d) for d in d45]+[('fix',d) for d in gapd]+[('h55',d) for d in d55]
S45=[x for x in h45 if x['b']<='19450814'<=x['e']]
S55=[x for x in h55 if x['b']<='19550901'<=x['e']]
n55={x['n']:x for x in S55 if x['up']=='2'}
seoul55=unary_union([x['geom'] for x in S55 if x['up']=='16']).buffer(0.0002).buffer(-0.0002)
SRC_FIX={
 'seoul46':'1946년 9월 28일 서울이 경기도에서 분리됨(군정법률 제106호, 9월 18일 공표·28일 발효). 경계는 1945년 경성부 그대로',
 'seoul49':'1949년 8월 15일 고양군 뚝도·숭인·은평면과 시흥군 번대방리·도림리·구로리를 서울에 편입(대통령령 제159호, 1949년 8월 13일). 경계는 1955년 9월 HGIS 서울특별시를 앞당겨 씀',
 'goyang49':'1949년 8월 15일 일부가 서울로 편입됨. 경계는 1955년 9월 HGIS 경계를 앞당겨 씀',
 'suwon49':'1949년 8월 15일 수원읍이 수원시가 되고 수원군의 나머지가 화성군이 됨. 경계는 1955년 9월 HGIS 경계를 앞당겨 씀',
 'incheon49':'1949년 8월 15일 인천부가 인천시가 됨(지방자치법). 경계는 1955년 9월 HGIS 경계를 앞당겨 씀',
 'kaesong49':'1949년 개성부가 개성시가 됨. 경계는 1945년 HGIS 개성부 그대로',
 'north53':'휴전(1953년 7월 27일) 뒤 군사분계선 북쪽이 되어 지도에서 뺌',
 'yeoncheon54':'1954년 11월 17일 수복지구임시행정조치법으로 행정이 회복됨. 1945–1954년에는 38선 북쪽 땅이 북한 관할이었고 남쪽 일부(전곡·백학 등)는 파주군에 편입되어 있었는데, 이 지도는 그 사이를 1945년 경계로 그림(미보정). 경계는 1955년 9월 HGIS 경계를 앞당겨 씀',
 'same':'1945년 8월과 1955년 9월 HGIS 경계가 같아 그대로 이음',
}
def F(n,g,k,geom,src,note,tr=None,s=None):
    return dict(n=n,g=g,k=k,geom=geom,src=src,note=note,tr=tr,s=s or ('서울특별시' if g=='서울' else '경기도'))
states=[]
for fam,d in pre:
    st=[]
    if fam=='h45':
        for x in h45:
            if x['b']<=d<=x['e']:
                g='서울' if x['n']=='한성부' else '경기'
                st.append(F(x['n'],g,kind45(x),x['geom'],'h45',x['ref'][:160],x['tr'],'한성부' if x['n']=='한성부' else '경기도'))
    elif fam=='fix':
        for x in S45:
            n=x['n']; geom=x['geom']; note=SRC_FIX['same'] if n in n55 and n55[n]['geom'].symmetric_difference(geom).area<1e-6 else '1945년 8월 HGIS 경계'
            g='경기'; k=kind45(x)
            if n=='경성부':
                if d>='19460928': n,g,k,note='서울','서울',2,SRC_FIX['seoul46']
                if d>='19490815': geom,note=seoul55,SRC_FIX['seoul49']
            if d>='19490815':
                if n in ('고양군','시흥군'): geom,note=n55[n]['geom'],SRC_FIX['goyang49']
                if n=='수원군':
                    st.append(F('수원시','경기',1,n55['수원시']['geom'],'fix',SRC_FIX['suwon49'])); n,geom,note='화성군',n55['화성군']['geom'],SRC_FIX['suwon49']
                if n=='인천부': n,geom,note,k='인천시',n55['인천시']['geom'],SRC_FIX['incheon49'],1
                if n=='개성부': n,note='개성시',SRC_FIX['kaesong49']
            if d>='19530727' and n in ('개성시','개풍군','장단군'): continue
            if d>='19541117' and n=='연천군': geom,note=n55[n]['geom'],SRC_FIX['yeoncheon54']
            st.append(F(n,g,k,geom,'fix',note))
    else:
        for x in h55:
            if x['b']<=d<=x['e']:
                g='서울' if x['up']=='16' else '경기'
                k=2 if g=='서울' else (1 if x['t']=='市' else 0)
                st.append(F(x['n'],g,k,x['geom'],'h55',x['ref'][:160],x['tr']))
    states.append(st)
# ---- versioning ----
vers=[]; last={}
for i,st in enumerate(states):
    for f in st:
        key=(f['g'],f['n']); v=last.get(key)
        if v is not None and v['to']==i-1:
            sd=v['geom'].symmetric_difference(f['geom']).area/max(v['geom'].area,f['geom'].area)
            if sd<0.06:
                v['to']=i
                if f['src']!=v['srcs'][-1][0] or f['note']!=v['srcs'][-1][1]: v['srcs'].append((f['src'],f['note'],i))
                continue
            why='경계' if f['src']==v['src'] else '자료'
            if f['src']=='fix' or v['src']=='fix': why='경계'
        else:
            why='처음' if v is None else '다시'
            if i==0: why='처음'
        nv=dict(f,fr=i,to=i,why=why,srcs=[(f['src'],f['note'],i)]); vers.append(nv); last[key]=nv
print('pre versions',len(vers))
def city(n):
    m=re.match(r'^(.+?시)(.+구)$',n); return (m.group(1),m.group(2)) if m else (n,'')
out=[]
for v in vers:
    c,sub=city(v['n'])
    out.append({'n':v['n'],'c':c,'sub':sub,'g':v['g'],'s':v['s'],'k':v['k'],'fr':v['fr'],'to':v['to'],'why':v['why'],
                'src':v['src'],'tr':v['tr'],'notes':[[s,n,i] for s,n,i in v['srcs']],'geo':geo(v['geom'])})
# sido outlines per state
sido=[]; lastS={}
for i,st in enumerate(states):
    by={}
    for f in st: by.setdefault(f['g'],[]).append(f['geom'])
    for g,gs in by.items():
        u=unary_union(gs).buffer(0.0003).buffer(-0.0003)
        v=lastS.get(g)
        if v is not None and v['to']==i-1 and v['geom'].symmetric_difference(u).area/u.area<0.02: v['to']=i; continue
        nv={'g':g,'geom':u,'fr':i,'to':i}; sido.append(nv); lastS[g]=nv
sido_out=[{'g':v['g'],'fr':v['fr'],'to':v['to'],'geo':{'type':(b:=v['geom'].boundary.simplify(0.0008)).geom_type,'coordinates':rnd(mapping(b)['coordinates'])}} for v in sido]
# labels + counts text
labels=[]; ct=[]
for i,(fam,d) in enumerate(pre):
    st=states[i]; L=[]
    for f in st:
        big=f['g']=='서울' and f['k']==2 and fam!='h55'
        L.append([f['n'],*lab(f['geom']),1 if big else 0,round(f['geom'].area*1e4,2)])
        if f['g']=='서울' and fam=='h55': L[-1][3]=2
    if fam=='h55':
        u=unary_union([f['geom'] for f in st if f['g']=='서울']); L.append(['서울',*lab(u),1,round(u.area*1e4,2)])
    labels.append(L)
    gy=[f for f in st if f['g']=='경기']; nfu=sum(1 for f in gy if f['k']==1); ngun=sum(1 for f in gy if f['k']==0)
    if fam=='h45':
        t=('한성부 · ' if any(f['n']=='한성부' for f in st) else '')+f'경기도 {nfu}부 {ngun}군'
    elif fam=='fix':
        sp='서울 · ' if any(f['g']=='서울' for f in st) else ''
        t=sp+f'경기도 {nfu}{"부" if d<"19490815" else "시"} {ngun}군'
    else:
        t=f'서울 {sum(1 for f in st if f["g"]=="서울")}구 · 경기도 {nfu}시 {ngun}군'
    ct.append(t)
snaps=[{'d':f'{d[:4]}-{d[4:6]}-{d[6:]}','y':int(d[:4]),'src':fam} for fam,d in pre]
# ---- append admdongkor part ----
off=len(snaps)
for s in old['snaps']: snaps.append({'d':s['d'],'y':s['y'],'src':'adm'})
for v in old['sgg']:
    v=dict(v); v['fr']+=off; v['to']+=off; v['src']='adm'; v['tr']=None; v['notes']=[]
    if v['fr']==off: v['why']='자료'
    v.pop('lp',None); out.append(v)
for v in old['sido']:
    v=dict(v); v['fr']+=off; v['to']+=off; sido_out.append(v)
labels+=old['labels']
for c in old['counts']:
    ic=f"인천 {c['인천']}구·군" if c['인천'] else '인천은 경기도의 시'
    etc=(' · '+'·'.join(c['경기기타'])) if c['경기기타'] else ''
    ct.append(f"서울 {c['서울']}구 · {ic} · 경기 {c['경기시']}시 {c['경기군']}군{etc}")
# ---- pre-1974 rail ----
rc=sqlite3.connect(f'{RAW}/hgis_rail/rail.gpkg')
def rg(b):
    flags=b[3]; env=(flags>>1)&7; el={0:0,1:32,2:48,3:48,4:64}[env]
    return shapely.wkb.loads(bytes(b[8+el:]))
rail0=[]
for sp,grp,g in rc.execute('select sp_id,group_id,geom from "철도망_GIS_LINE"'):
    G=rg(g)
    if G.bounds[1]>38.35 or G.bounds[3]<36.85: continue
    if sp.startswith('(todo)'):
        nm=re.search(r'\((.+?)\)_',sp.replace('(todo)','')); l='경부선'; d0='1905-01-01'; d1=None; todo=True
    else:
        l,a,b=sp.split('_'); d0=f'{a[:4]}-{a[4:6]}-{a[6:]}'; d1=None if b=='19450814' else f'{b[:4]}-{b[4:6]}-{b[6:] if b[6:]!="00" else "01"}'; todo=False
    lines=[G] if G.geom_type=='LineString' else list(G.geoms)
    for ln in lines:
        rail0.append({'l':l,'d0':d0,'d1':d1,'todo':todo,'s':'hgis','p':rnd(ln.simplify(0.0002).coords[:])})
r=json.load(open(f'{SEOUL}/rail.json'))
skip={'경인선','경부선','경부고속철도','경의선(용산선 지하)'}
for s in r['segs']:
    if s['line'] in skip or 'p' not in s: continue
    rail0.append({'l':s['line'],'d0':f"{s['open']}-01-01",'d1':(f"{s['close']}-12-31" if s['close'] else None),'todo':False,'s':'slm','p':rnd(LineString(s['p']).simplify(0.0002).coords[:])})
print('rail0',len(rail0))
data=dict(old); data.update({'snaps':snaps,'sgg':out,'sido':sido_out,'labels':labels,'ct':ct,'rail0':rail0,'fixnotes':SRC_FIX})
for k in ('counts',): data.pop(k,None)
json.dump(data,open(PAGE_DATA,'w'),ensure_ascii=False,separators=(',',':'))
for s,t in zip(snaps[:off+1],ct[:off+1]): print(s['d'],s['src'],t)
