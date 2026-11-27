import sqlite3, shapely.wkb, json, pickle
from shapely.ops import unary_union
def geom(b):
    flags=b[3]; env=(flags>>1)&7; el={0:0,1:32,2:48,3:48,4:64}[env]
    return shapely.wkb.loads(bytes(b[8+el:])).buffer(0)
A='/home/claude/raw/hgis_adm/adm.gpkg'; B='/home/claude/raw/hgis_5575/1955-1970행정구역_GIS_데이터.gpkg'
c=sqlite3.connect(A)
h45=[]
for key,name,typ,b,e,up,tr,ref,g in c.execute('select key,name,type,begin,"end",up_key,trust,reference,geom from "행정구역_GIS_폴리곤" where lv=2 and up_key=\'2\''):
    h45.append(dict(key=key,n=name,t=typ,b=b,e=e,tr=tr,ref=ref or '',geom=geom(g)))
# 1910-05-10..09-30 한성부 (lv1 key 11)
for key,name,typ,b,e,g in c.execute('select key,name,type,begin,"end",geom from "행정구역_GIS_폴리곤" where lv=1 and name=\'한성부\''):
    h45.append(dict(key=key,n=name,t=typ,b=b,e=e,tr=2,ref='',geom=geom(g)))
# 1910-10-01..1914-02-28 경성부 = 5부 합침
parts=[geom(g) for (g,) in c.execute('select geom from "행정구역_GIS_폴리곤" where lv=3 and up_key=\'2/10\' and begin<=\'19120101\' and "end">=\'19120101\'')]
h45.append(dict(key='2/10',n='경성부',t='府',b='19101001',e='19140228',tr=2,ref='5부(部) 폴리곤을 합침',geom=unary_union(parts).buffer(0)))
print('h45',len(h45), sorted(set(x['b'] for x in h45)))
c2=sqlite3.connect(B)
h55=[]
for key,name,typ,b,e,up,tr,ref,g in c2.execute('select key,name,type,begin,"end",up_key,trust,reference,geom from "행정구역_GIS_폴리곤" where lv=2 and up_key in (\'2\',\'16\')'):
    h55.append(dict(key=key,n=name,t=typ,b=b,e=e,up=up,tr=tr,ref=ref or '',geom=geom(g)))
seoul55=[geom(g) for (g,b,e) in c2.execute('select geom,begin,"end" from "행정구역_GIS_폴리곤" where lv=1 and key=\'16\'')]
print('h55',len(h55), sorted(set(x['b'] for x in h55)))
pickle.dump((h45,h55),open('hgis.pkl','wb'))
# compare 1945 vs 1955
S45=[x for x in h45 if x['b']<='19450814'<=x['e']]
S55=[x for x in h55 if x['b']<='19550901'<=x['e']]
print('S45',[x['n'] for x in S45]); print('S55',[x['n'] for x in S55])
d55={x['n']:x for x in S55 if x['up']=='2'}
for x in S45:
    y=d55.get(x['n'])
    if y:
        iou=x['geom'].intersection(y['geom']).area/x['geom'].union(y['geom']).area
        print('%-6s IoU %.3f  area45 %.0f area55 %.0f km2'%(x['n'],iou,x['geom'].area*1e4*0.98,y['geom'].area*1e4*0.98))
    else: print(x['n'],'-- not in 1955')
s55=unary_union([x['geom'] for x in S55 if x['up']=='16'])
k45=[x for x in S45 if x['n']=='경성부'][0]
print('서울 1945→1955 area', k45['geom'].area*1e4*0.98, s55.area*1e4*0.98)
