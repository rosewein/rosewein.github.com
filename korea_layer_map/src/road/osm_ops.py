import osmium, sys, json, collections
src=sys.argv[1]; out=sys.argv[2]
class H(osmium.SimpleHandler):
    def __init__(s):
        super().__init__(); s.ways=[]; s.rels=[]
    def way(s,w):
        t=w.tags
        if t.get('highway') in ('motorway',):
            try:
                coords=[(n.lon,n.lat) for n in w.nodes]
            except Exception:
                coords=[]
            s.ways.append(dict(id=w.id,ref=t.get('ref',''),name=t.get('name',''),operator=t.get('operator',''),
                               opening=t.get('opening_date','') or t.get('start_date',''),coords=coords))
    def relation(s,r):
        t=r.tags
        if t.get('route')=='road' and ('expressway' in t.get('network','') or t.get('highway')=='motorway' or 'KR:' in t.get('network','')):
            s.rels.append(dict(id=r.id,ref=t.get('ref',''),name=t.get('name',''),network=t.get('network',''),operator=t.get('operator',''),
                               start=t.get('start_date',''),opening=t.get('opening_date',''),
                               members=[m.ref for m in r.members if m.type=='w']))
h=H(); h.apply_file(src,locations=True)
json.dump(dict(ways=h.ways,rels=h.rels),open(out,'w'),ensure_ascii=False)
print(len(h.ways),len(h.rels))
