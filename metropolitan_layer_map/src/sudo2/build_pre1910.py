# 1899–1910년 5월 보정: 1910-05-10 HGIS 군·면 경계 + 1906 칙령 제49호(지방구역정리) + 1908 양평군 출범
import json, pickle, sqlite3, shapely.wkb
from shapely.ops import unary_union
from build2_util import geo, lab, rnd
from shapely.geometry import mapping
BASE='/home/claude/sudo2/data_base_v5.json'; OUT='/home/claude/sudo/page/data.json'
d=json.load(open(BASE))
h45,_=pickle.load(open('hgis.pkl','rb'))
c=sqlite3.connect('/home/claude/raw/hgis_adm/adm.gpkg')
def gg(b):
    flags=b[3]; n={0:0,1:32,2:48,3:48,4:64}[(flags>>1)&7]
    return shapely.wkb.loads(bytes(b[8+n:])).buffer(0)
gun={}  # name -> (geom, kind, g, s, ref, tr)
for x in h45:
    if x['b']<='19100510'<=x['e']:
        g='서울' if x['n']=='한성부' else '경기'
        k=2 if x['n']=='한성부' else (1 if x['t'] in ('府','市') else 0)
        gun[x['n']]=dict(geom=x['geom'].buffer(0),k=k,g=g,s='한성부' if g=='서울' else '경기도',tr=x['tr'])
myeon={}
for key,full,cn,geom in c.execute("select key,fullname,name_cn,geom from 행정구역_GIS_폴리곤 where lv=3 and begin<='19100510' and end>='19100510' and (key like '2/%' or key='8/53/2225')"):
    _,gn,mn=full.split('/'); myeon[(gn,cn)]=gg(geom)
def M(gn,cn):
    return myeon[(gn,cn)]
NOTE_SAME='1910년 5월 HGIS 경계(민적통계표 기준)를 앞당겨 씀'
LAW49='1906년 9월 24일 칙령 제49호 「지방구역정리건」'
# ---- P2: 1908-09-14 ~ 1910-05-09 ----
P2={n:dict(v,note=NOTE_SAME) for n,v in gun.items()}
# ---- P1: 1906-09-24 ~ 1908-09-13 (양근·지평 따로) ----
JP=['郡內面','南面','上東面','上北面','下東面','下北面','上西面','下西面']
yp=[cn for (gn,cn) in myeon if gn=='양평군']
jg=unary_union([M('양평군',cn) for cn in JP]); yg=unary_union([M('양평군',cn) for cn in yp if cn not in JP])
P1={n:dict(v) for n,v in P2.items() if n!='양평군'}
note_yp='1908년 9월 14일 양근군과 지평군을 합쳐 양평군이 됨(순종실록). 1910년 양평군의 면을 위치로 나눠 그림(추정): 지평은 군내·남·상동·하동·상북·하북·상서·하서면'
P1['양근군']=dict(P2['양평군'],geom=yg,note=note_yp)
P1['지평군']=dict(P2['양평군'],geom=jg,note=note_yp)
# ---- P0: ~1906-09-23 (칙령 제49호 전) ----
# (1910년 군, 1910년 면 한자 이름, 원래 군, 1906년 칙령의 면 이름, 확실성)
MOVES=[
 ('고양군','神穴面','양주군','神穴面',''),
 ('포천군','山內面','양주군','山內面',''),('포천군','靑松面','양주군','靑松面',''),
 ('양주군','草阜面','광주군','草阜面','광주의 비입지'),
 ('연천군','官仁面','@강원 철원군','官仁面','철원의 두입지'),
 ('마전군','長新面','장단군','長東面','추정'),('마전군','江新面','장단군','江東面','추정'),
 ('마전군','河新面','적성군','河北面','적성의 비입지, 추정'),
 ('장단군','大南面','개성군','大南面',''),('장단군','小南面','개성군','小南面',''),
 ('안산군','聲串面','광주군','聲串面',''),('안산군','月谷面','광주군','月谷面',''),('안산군','北方面','광주군','北方面',''),
 ('남양군','八灘面','수원군','八灘面',''),('남양군','長安面','수원군','長安面',''),('남양군','草長面','수원군','草長面',''),('남양군','鴨汀面','수원군','鴨汀面',''),
 ('남양군','分鄕里面','수원군','汾鄕面','추정'),
 ('수원군','栗北面','양성군','栗北面','양성의 비입지'),('수원군','升良面','양성군','升良面','양성의 비입지'),('수원군','甘味面','양성군','甘味洞面','양성의 비입지, 추정'),
 ('진위군','五朶面','수원군','五朵面',''),('진위군','所古尼面','양성군','所古尼面',''),
 ('죽산군','蹄村面','양지군','蹄村面','양지의 비입지'),
 ('여주군','康川面','@강원 원주군','康川面','원주의 두입지'),('여주군','池內面','@강원 원주군','池內面','원주의 두입지'),
 ('@충북 음성군','無極面','음죽군','無極面',''),
]
UNRES='1910년 자료에서 짝을 찾지 못해 1910년 경계대로 둔 것: 인천 이포면(남양으로 감), 수원 오정면(남양으로 감), 양성 서생면, 직산 언리·외야곶·안중면과 평택 소북면(수원으로 옴), 수원 광덕면 일부·가사면 일부(아산으로 감)'
P0={n:dict(v,moved=[]) for n,v in P1.items()}
out0={}
for g10,cn,orig,cn06,memo in MOVES:
    src_g='음죽' if g10.startswith('@') else g10
    geom=myeon[('음성군' if g10.startswith('@') else g10, cn)]
    if not g10.startswith('@'):
        P0[g10]['geom']=P0[g10]['geom'].difference(geom.buffer(0.0003)).buffer(0)
        P0[g10]['moved'].append(f"{cn06[:-1]}면→{orig.lstrip('@').split(' ')[-1]}")
    if orig.startswith('@'):
        nm=f"{orig[1:].split(' ')[1]} {cn06[:-1]}면"; out0.setdefault(nm,[]).append(geom)
    else:
        P0[orig]['geom']=unary_union([P0[orig]['geom'],geom]).buffer(0.0002).buffer(-0.0002)
        P0[orig]['moved'].append(f"{cn06[:-1]}면←{('음성' if g10.startswith('@') else g10[:-1])}"+(f"({memo})" if memo else ''))
for n,v in P0.items():
    if v['moved']:
        v['note']=f"{LAW49} 전 경계. 1910년 HGIS 면 경계로 되돌려 그림: "+', '.join(v['moved'])+'. '+UNRES
    elif n in ('양근군','지평군'): v['note']=note_yp+'. 1906년 칙령 전과 뒤의 변동 없음'
    else: v['note']=NOTE_SAME+'. '+LAW49+'에서 이 군은 면을 주고받지 않음'
for n in P1:
    if n in ('양근군','지평군'): continue
    if P0[n]['moved']: P1[n]['note']=f"{LAW49}로 면을 주고받은 뒤 경계. "+NOTE_SAME
    else: P1[n]['note']=NOTE_SAME
states=[]
for P in (P0,P1,P2):
    st=[dict(n=n,g=v['g'],k=v['k'],s=v['s'],geom=v['geom'],note=v['note'],tr=None) for n,v in P.items()]
    states.append(st)
for nm,gs in out0.items():
    states[0].append(dict(n=nm,g='강원',k=3,s='강원도',geom=unary_union(gs),note=f"{LAW49} 전에는 강원도 소속(두입지). 1910년 HGIS 면 경계로 그림",tr=None))
# ---- versions across the 3 new snapshots ----
vers=[];last={}
for i,st in enumerate(states):
    for f in st:
        key=(f['g'],f['n']);v=last.get(key)
        if v is not None and v['to']==i-1 and v['geom'].symmetric_difference(f['geom']).area<1e-7:
            v['to']=i
            if f['note']!=v['notes'][-1][1]: v['notes'].append(['fix0',f['note'],i])
            continue
        why='처음' if v is None else '경계'
        nv=dict(f,fr=i,to=i,why=why,notes=[['fix0',f['note'],i]]);vers.append(nv);last[key]=nv
N=3
new=[]
for v in vers:
    new.append({'n':v['n'],'c':v['n'],'sub':'','g':v['g'],'s':v['s'],'k':v['k'],'fr':v['fr'],'to':v['to'],'why':v['why'],'src':'fix0','tr':None,'notes':v['notes'],'geo':geo(v['geom'])})
for v in d['sgg']:
    v['fr']+=N;v['to']+=N
    if v['fr']==N: v['why']='자료'
sido=[]
for i,st in enumerate(states):
    for g in ('경기','서울'):
        u=unary_union([f['geom'] for f in st if f['g']==g]).buffer(0.0003).buffer(-0.0003)
        b=u.boundary.simplify(0.0008)
        sido.append({'g':g,'fr':i,'to':i,'geo':{'type':b.geom_type,'coordinates':rnd(mapping(b)['coordinates'])}})
for v in d['sido']: v['fr']+=N;v['to']+=N
labels=[];ct=[]
for st in states:
    labels.append([[f['n'],*lab(f['geom']),1 if f['k']==2 else 0,round(f['geom'].area*1e4,2)] for f in st if f['g']!='강원'])
    gy=[f for f in st if f['g']=='경기']
    ct.append(f"한성부 · 경기도 {sum(f['k']==1 for f in gy)}부 {sum(f['k']==0 for f in gy)}군")
snaps=[{'d':'1899년','y':1899,'src':'fix0','lab':'1906년 9월 칙령 제49호 전 경계(되짚음)'},
       {'d':'1906-09-24','y':1906,'src':'fix0','lab':'칙령 제49호 시행일 1906-09-24'},
       {'d':'1908-09-14','y':1908,'src':'fix0','lab':'양평군 출범 1908-09-14'}]
d['snaps']=snaps+d['snaps']; d['sgg']=new+d['sgg']; d['sido']=sido+d['sido']
d['labels']=labels+d['labels']; d['ct']=ct+d['ct']
d['fixnotes']['law49']=LAW49
json.dump(d,open(OUT,'w'),ensure_ascii=False,separators=(',',':'))
print(len(new),[ (v['n'],v['fr'],v['to'],v['why']) for v in new if v['why']!='처음' or v['fr']>0][:40])
print(ct)
