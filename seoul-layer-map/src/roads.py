"""BBBike 서울 OSM 추출본에서 버스가 다닐 만한 도로망을 뽑아 그래프로 저장."""
import osmium, numpy as np, json, math, sys
PBF = "/home/claude/data/osm/seoul/Seoul.osm.pbf"
OUT = "/home/claude/data/osm/seoul/roads.npz"
COST = {"motorway": 1.05, "motorway_link": 1.1, "trunk": 0.95, "trunk_link": 1.05, "primary": 0.9, "primary_link": 1.0,
        "secondary": 1.0, "secondary_link": 1.05, "tertiary": 1.15, "tertiary_link": 1.15, "unclassified": 1.5, "residential": 1.9}
CLS = {k: i for i, k in enumerate(COST)}

class H(osmium.SimpleHandler):
    def __init__(self):
        super().__init__()
        self.ways = []
    def way(self, w):
        hw = w.tags.get("highway")
        if hw not in COST: return
        if w.tags.get("access") in ("private", "no"): return
        try:
            pts = [(n.ref, n.lon, n.lat) for n in w.nodes]
        except osmium.InvalidLocationError:
            return
        self.ways.append((CLS[hw], pts))

h = H()
h.apply_file(PBF, locations=True)
print("ways", len(h.ways), file=sys.stderr)
idx, lon, lat = {}, [], []
eu, ev, ew, ec = [], [], [], []
def nid(ref, x, y):
    i = idx.get(ref)
    if i is None:
        i = idx[ref] = len(lon); lon.append(x); lat.append(y)
    return i
for c, pts in h.ways:
    prev = None
    for ref, x, y in pts:
        i = nid(ref, x, y)
        if prev is not None and prev != i:
            px, py = lon[prev], lat[prev]
            d = math.hypot((x - px) * 88.4, (y - py) * 111.0)
            eu.append(prev); ev.append(i); ew.append(d); ec.append(c)
        prev = i
np.savez_compressed(OUT, lon=np.array(lon), lat=np.array(lat), u=np.array(eu, dtype=np.int32), v=np.array(ev, dtype=np.int32),
                    d=np.array(ew, dtype=np.float32), c=np.array(ec, dtype=np.int8), cls=np.array(list(COST)), cost=np.array(list(COST.values())))
print("nodes", len(lon), "edges", len(eu), file=sys.stderr)
