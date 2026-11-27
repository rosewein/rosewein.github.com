# 고속도로 본선 way(노드 id·좌표 포함)와 나들목·분기점 노드를 뽑음
import osmium, sys, json
src,out=sys.argv[1],sys.argv[2]
class H(osmium.SimpleHandler):
    def __init__(s): super().__init__(); s.ways=[]; s.jn=[]
    def node(s,n):
        t=n.tags
        if t.get('highway')=='motorway_junction' or t.get('highway')=='motorway_junction;toll_gantry':
            s.jn.append(dict(id=n.id,name=t.get('name',''),ref=t.get('ref',''),lon=n.location.lon,lat=n.location.lat))
    def way(s,w):
        t=w.tags
        if t.get('highway')!='motorway': return
        try: c=[(n.lon,n.lat) for n in w.nodes]; ids=[n.ref for n in w.nodes]
        except Exception: return
        s.ways.append(dict(id=w.id,ref=t.get('ref',''),name=t.get('name',''),op=t.get('operator',''),
            od=t.get('opening_date','') or t.get('start_date',''),nodes=ids,coords=c))
h=H(); h.apply_file(src,locations=True)
json.dump(dict(ways=h.ways,jn=h.jn),open(out,'w'),ensure_ascii=False)
print(len(h.ways),len(h.jn))
