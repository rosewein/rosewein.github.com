import json, pickle, re
from shapely.geometry import shape, mapping, LineString, MultiLineString
from shapely.ops import unary_union
sel=open('/home/claude/ext/sel.txt').read().split()
def grp(s): return '서울' if '서울' in s else '인천' if '인천' in s else '경기'
snaps=[]
for d in sel:
    fc=json.load(open(f'gj/y{d}.json'))
    snaps.append([(grp(f['properties']['s']),f['properties']['n'],f['properties']['s'],shape(f['geometry']).buffer(0)) for f in fc['features']])
TH=0.06
vers=[]; last={}
for i,feats in enumerate(snaps):
    for g,n,s,geom in feats:
        k=(g,n); v=last.get(k)
        if v is not None and v['to']==i-1:
            sd=v['geom'].symmetric_difference(geom).area/max(v['geom'].area,geom.area)
            if sd<TH and v['sido']==s:
                v['to']=i; continue
            new={'k':k,'n':n,'sido':s,'geom':geom,'fr':i,'to':i,'why':'경계' if v['sido']==s else '소속'}
        else:
            new={'k':k,'n':n,'sido':s,'geom':geom,'fr':i,'to':i,'why':'처음' if v is None else '다시'}
        vers.append(new); last[k]=new
print('versions',len(vers))
def rnd(o):
    if isinstance(o,(list,tuple)):
        if o and isinstance(o[0],(int,float)): return [round(o[0],4),round(o[1],4)]
        return [rnd(x) for x in o]
    return o
def cls(n,s):
    if n.endswith('군'): return 0
    if '출장소' in n: return 0
    if n.endswith('구') and ('특별시' in s or '광역시' in s or '직할시' in s): return 2
    return 1
def city(n):
    m=re.match(r'^(.+?시)(.+구)$',n)
    return (m.group(1),m.group(2)) if m else (n,'')
out_sgg=[]
for v in vers:
    gm=v['geom'].simplify(0.0006,preserve_topology=True)
    from shapely.geometry.polygon import orient
    from shapely.geometry import MultiPolygon, Polygon
    gm=MultiPolygon([orient(p,-1.0) for p in gm.geoms]) if gm.geom_type=='MultiPolygon' else orient(gm,-1.0)
    c,sub=city(v['n'])
    rp=v['geom'].representative_point()
    out_sgg.append({'n':v['n'],'c':c,'sub':sub,'g':v['k'][0],'s':v['sido'],'k':cls(v['n'],v['sido']),'fr':v['fr'],'to':v['to'],'why':v['why'],
                    'lp':[round(rp.x,4),round(rp.y,4)],'geo':{'type':gm.geom_type,'coordinates':rnd(mapping(gm)['coordinates'])}})
# city label points per snapshot group (for 일반구 cities): union of parts
# sido outlines per snapshot
sido=[]; lastS={}
for i,feats in enumerate(snaps):
    by={}
    for g,n,s,geom in feats: by.setdefault(g,[]).append(geom)
    for g,gs in by.items():
        u=unary_union(gs).buffer(0.0003).buffer(-0.0003)
        v=lastS.get(g)
        if v is not None and v['to']==i-1 and v['geom'].symmetric_difference(u).area/u.area<0.02:
            v['to']=i; continue
        nv={'g':g,'geom':u,'fr':i,'to':i}; sido.append(nv); lastS[g]=nv
out_sido=[]
for v in sido:
    b=v['geom'].boundary.simplify(0.0008)
    out_sido.append({'g':v['g'],'fr':v['fr'],'to':v['to'],'geo':{'type':b.geom_type,'coordinates':rnd(mapping(b)['coordinates'])}})
print('sido versions',len(out_sido))
snapmeta=[{'d':f'{d[:4]}-{d[4:6]}-{d[6:]}','y':int(d[:4])} for d in sel]

# ---------- metro ----------
import importlib.util
spec=importlib.util.spec_from_file_location('sd','/home/claude/sudo/sudo_dates.py'); sd=importlib.util.module_from_spec(spec); spec.loader.exec_module(sd)
m=json.load(open('/home/claude/repo/seoul-layer-map/data/metro.json'))
md=json.load(open('/home/claude/repo/seoul-layer-map/data/metro_dates.json'))
n=json.load(open('/home/claude/ext/kimmdr2_metroscope/data/network.json'))
def al(ln,nm): return sd.ALIAS.get((ln,nm)) or sd.ALIAS.get(('*',nm)) or nm
rec={}   # (line,name)->dict(d,y,inf,src,conf,note)
for s0 in m['stations']:
    for ln,y in s0['opens'].items():
        r=md.get(ln,{}).get(s0['name'],{})
        rec[(ln,s0['name'])]={'d':s0['dates'].get(ln,str(y)).replace('.','-'),'y':y,'inf':bool(r.get('infill')),'src':'slm','conf':'s','note':r.get('note','') or s0.get('note','')}
seoul_keys=set(rec)
added=0
for ln,rows in sd.D.items():
    for dt,names,src,conf,note in rows:
        inf=dt.endswith('*'); dt=dt.rstrip('*')
        for nm in names:
            k=(ln,nm)
            if k in rec: print('dup',k); continue
            rec[k]={'d':dt,'y':int(dt[:4]),'inf':inf,'src':src,'conf':conf,'note':note}; added+=1
print('added dates',added)
colors={l['name']:l['color'] for l in n['lines']}
for l in m['lines']: colors.setdefault(l['name'],l['color'])
dated_edges=[]
for l in m['lines']:
    for e in l['edges']:
        dated_edges.append({'l':l['name'],'y':e['open'],'p':rnd(LineString(e['p']).simplify(0.0002).coords[:])})
und=[]; newe=[]
missing=set()
for l in n['lines']:
    ln=l['name']
    for ch in l['chains']:
        sts=[al(ln,x) for x in ch['stations']]; path=ch['path']; at=ch['at']
        own=[rec.get((ln,x)) for x in sts]
        for x,r in zip(sts,own):
            if r is None: missing.add((ln,x))
        def t(i):
            r=own[i]
            if r is None: return None
            if not r['inf']: return r['y']
            ys=[r['y']]
            for step in (-1,1):
                j=i+step
                while 0<=j<len(sts) and own[j] is not None and own[j]['inf']: j+=step
                if 0<=j<len(sts) and own[j] is not None: ys.append(own[j]['y'])
            nb=[y for y in ys[1:]]
            return max(nb) if nb else r['y']
        for i in range(len(sts)-1):
            a,b=sts[i],sts[i+1]
            if (ln,a) in seoul_keys and (ln,b) in seoul_keys: continue
            seg=path[at[i]:at[i+1]+1]
            if len(seg)<2: continue
            ta,tb=t(i),t(i+1)
            p=rnd(LineString(seg).simplify(0.0002).coords[:])
            if ta is None or tb is None: und.append({'l':ln,'p':p})
            else: newe.append({'l':ln,'y':max(ta,tb),'p':p})
print('missing',sorted(missing))
dated_edges+=newe
stations={}
def findkey(a,x,y):
    for k,st in stations.items():
        if st['n']==a and ((st['x']-x)*88)**2+((st['y']-y)*111)**2<1.5**2: return k
    k=a; i=2
    while k in stations: k=f'{a}#{i}'; i+=1
    return k
for l in n['lines']:
    ln=l['name']
    for nm,xy in l['stations'].items():
        a=al(ln,nm); k=findkey(a,xy[0],xy[1])
        st=stations.setdefault(k,{'n':a,'x':round(xy[0],4),'y':round(xy[1],4),'ls':{}})
        st['ls'][ln]=rec.get((ln,a))
for s0 in m['stations']:
    k=findkey(s0['name'],s0['lng'],s0['lat'])
    st=stations.setdefault(k,{'n':s0['name'],'x':round(s0['lng'],4),'y':round(s0['lat'],4),'ls':{}})
    for ln in s0['opens']: st['ls'].setdefault(ln,rec.get((ln,s0['name'])))
st_out=[]
for st in stations.values():
    ys=[r['y'] for r in st['ls'].values() if r]
    st_out.append({'n':st['n'],'x':st['x'],'y':st['y'],
                   'ls':[[ln,(r['y'] if r else None),(r['d'] if r else ''),(r['src'] if r else ''),(r['conf'] if r else ''),(r['note'] if r else '')] for ln,r in st['ls'].items()],
                   'f':min(ys) if ys else None})
lines=[{'n':l['name'],'c':colors[l['name']]} for l in n['lines']]
nd=sum(1 for s0 in st_out if s0['f'] is None)
from collections import Counter
cc=Counter(); 
for s0 in st_out:
    for e in s0['ls']: cc[e[4] or 'none']+=1
print('stations',len(st_out),'undated',nd,'edges',len(dated_edges),'new',len(newe),'undated segs',len(und),'conf',dict(cc))
data={'src':{k:v for k,v in sd.SRC.items()},'snaps':snapmeta,'sgg':out_sgg,'sido':out_sido,'lines':lines,'dedges':dated_edges,'uedges':und,'stations':st_out,
      'stats':{'st_total':len(st_out),'st_undated':nd,'conf':dict(cc)}}
json.dump(data,open('page/data.json','w'),ensure_ascii=False,separators=(',',':'))

# ---------- labels per snapshot ----------
from shapely.ops import polylabel
def lab(geom):
    g=geom
    if g.geom_type=='MultiPolygon': g=max(g.geoms,key=lambda p:p.area)
    try: p=polylabel(g,0.003)
    except Exception: p=g.representative_point()
    return [round(p.x,4),round(p.y,4)]
labels=[]; counts=[]
for i,feats in enumerate(snaps):
    L=[]; ent={}
    for g,n,s,geom in feats:
        c,sub=city(n)
        if g=='서울': key=('서울','서울',1)
        elif g=='인천' and n not in ('강화군','옹진군'): key=('인천','인천',1)
        else: key=(g,c,0)
        ent.setdefault(key,[]).append(geom)
        # sub-level label (zoomed): every feature
        L.append([n if not sub else sub, *lab(geom), 2, round(geom.area*1e4,2)])
    for (g,c,big),gs in ent.items():
        u=unary_union(gs)
        L.append([c,*lab(u),1 if big else 0,round(u.area*1e4,2)])
    labels.append(L)
    cnt={}
    for g,n,s,geom in feats:
        c,sub=city(n)
        if g=='경기' or (g=='인천' and False): pass
    gy=sorted({city(n)[0] for g,n,s,geom in feats if g=='경기'})
    counts.append({'서울':sum(1 for f in feats if f[0]=='서울'),'인천':sum(1 for f in feats if f[0]=='인천'),
                   '경기시':sum(1 for c in gy if c.endswith('시')),'경기군':sum(1 for c in gy if c.endswith('군')),
                   '경기기타':[c for c in gy if not (c.endswith('시') or c.endswith('군'))]})
data['labels']=labels; data['counts']=counts
json.dump(data,open('page/data.json','w'),ensure_ascii=False,separators=(',',':'))
for s,c in zip(snapmeta,counts): print(s['d'],c)
