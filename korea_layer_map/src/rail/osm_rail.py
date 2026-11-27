import osmium, sys, json
src,out=sys.argv[1],sys.argv[2]
RW={"rail","light_rail","subway","narrow_gauge","abandoned","disused","razed","construction","preserved","proposed","monorail","funicular"}
KEEP=("name","name:ko","ref","usage","service","operator","gauge","electrified","start_date","opening_date","end_date","railway:historic","abandoned:railway","disused:railway","razed:railway","historic:railway","construction","tunnel","bridge","old_name","was:railway","note")
class H(osmium.SimpleHandler):
    def __init__(s): super().__init__(); s.ways=[]; s.st=[]; s.rel=[]
    def node(s,n):
        t=n.tags; r=t.get("railway","")
        if r in ("station","halt") or t.get("public_transport")=="station" and t.get("train")=="yes":
            s.st.append(dict(id=n.id,lon=n.location.lon,lat=n.location.lat,**{k:t.get(k,"") for k in ("name","railway","station","operator","start_date","opening_date","end_date","subway","train","light_rail")}))
    def way(s,w):
        t=w.tags; r=t.get("railway","")
        hist=any(k in t for k in ("abandoned:railway","disused:railway","razed:railway","historic:railway","was:railway"))
        if r not in RW and not hist: return
        try: c=[(n.lon,n.lat) for n in w.nodes]; ids=[n.ref for n in w.nodes]
        except Exception: return
        s.ways.append(dict(id=w.id,railway=r,nodes=ids,coords=c,**{k:t.get(k,"") for k in KEEP}))
    def relation(s,r):
        t=r.tags
        if t.get("type")=="route" and t.get("route") in ("train","railway","subway","light_rail","tracks"):
            s.rel.append(dict(id=r.id,route=t.get("route"),name=t.get("name",""),ref=t.get("ref",""),operator=t.get("operator",""),members=[m.ref for m in r.members if m.type=="w"]))
h=H(); h.apply_file(src,locations=True)
json.dump(dict(ways=h.ways,st=h.st,rel=h.rel),open(out,"w"),ensure_ascii=False)
print(len(h.ways),len(h.st),len(h.rel))
