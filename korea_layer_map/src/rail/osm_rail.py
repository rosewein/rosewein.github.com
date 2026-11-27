"""OSM pbf에서 철도 선로·역·노선 관계를 뽑는다.

python3 src/rail/osm_rail.py <pbf> <out.json>

- 선(ways): railway가 RW 안에 있거나, 폐선 표시(abandoned:railway 등)가 있는 선. 노드 id와 좌표, KEEP 태그.
- 역(st): 노드·선(넓이로 그린 역은 중심점) 가운데
  railway=station·halt, public_transport=station+train=yes, 그리고 폐역 표시
  (disused:railway·abandoned:railway·razed:railway·historic:railway·railway:historic=station·halt 등,
  railway=disused_station, railway=historic+historic=railway_station, historic=railway_station)가 있는 것.
  이름 있는 화물역·조차장·신호장(railway=service_station·yard·signal_box)도 kind=service로 넣는다(2026-11-27 더함.
  OSM에서 화물역·신호장이 이 꼴로 많이 그려져 있어서).
  옛 이름 대응에 쓰려고 name:ko·old_name·alt_name 같은 이름 태그를 함께 담는다(2026-11-27 더함).
- 관계(rel): route=train·railway·subway·light_rail·tracks.
"""
import osmium, sys, json

src, out = sys.argv[1], sys.argv[2]
RW = {"rail", "light_rail", "subway", "narrow_gauge", "abandoned", "disused", "razed", "construction",
      "preserved", "proposed", "monorail", "funicular"}
HISTK = ("abandoned:railway", "disused:railway", "razed:railway", "historic:railway", "was:railway",
         "railway:historic")
KEEP = ("name", "name:ko", "ref", "usage", "service", "operator", "gauge", "electrified", "start_date",
        "opening_date", "end_date", "railway:historic", "abandoned:railway", "disused:railway", "razed:railway",
        "historic:railway", "construction", "tunnel", "bridge", "old_name", "was:railway", "note", "historic",
        "railway:preserved", "highway", "tracks", "passenger", "line")
STK = ("name", "name:ko", "name:ko-Hani", "name:ja", "name:en", "name:ko-Latn", "old_name", "old_name:ko",
       "alt_name", "official_name", "short_name", "loc_name", "railway", "station", "operator", "network",
       "line", "start_date", "opening_date", "end_date", "subway", "train", "light_rail", "public_transport",
       "disused:railway", "abandoned:railway", "razed:railway", "historic:railway", "railway:historic",
       "historic", "disused", "abandoned", "wikidata", "railway:ref", "ref")
STV = ("station", "halt")
SVC = ("service_station", "yard", "signal_box")          # 화물역·조차장·신호장(이름 있는 것만)
HSV = STV + SVC + ("disused_station", "abandoned_station")


def st_kind(t):
    r = t.get("railway", "")
    if r in STV:
        return "live"
    if t.get("public_transport") == "station" and t.get("train") == "yes":
        return "live"
    if r in SVC and t.get("name"):
        return "service"
    if r in ("disused_station", "abandoned_station"):
        return "hist"
    for k in HISTK:
        if t.get(k, "") in HSV:
            return "hist"
    if r == "historic" and t.get("historic") == "railway_station":
        return "hist"
    if t.get("historic") == "railway_station":
        return "hist"
    return None


class H(osmium.SimpleHandler):
    def __init__(s):
        super().__init__(); s.ways = []; s.st = []; s.rel = []

    def _st(s, oid, otype, lon, lat, t, kind):
        d = dict(id=oid, otype=otype, lon=lon, lat=lat, kind=kind)
        d.update({k: t.get(k, "") for k in STK})
        s.st.append(d)

    def node(s, n):
        t = n.tags; k = st_kind(t)
        if k:
            s._st(n.id, "n", n.location.lon, n.location.lat, t, k)

    def way(s, w):
        t = w.tags; r = t.get("railway", "")
        k = st_kind(t)
        if k:
            try:
                c = [(n.lon, n.lat) for n in w.nodes]
                s._st(w.id, "w", sum(x for x, _ in c) / len(c), sum(y for _, y in c) / len(c), t, k)
            except Exception:
                pass
            return
        hist = any(kk in t for kk in HISTK)
        if r not in RW and not hist:
            return
        try:
            c = [(n.lon, n.lat) for n in w.nodes]; ids = [n.ref for n in w.nodes]
        except Exception:
            return
        s.ways.append(dict(id=w.id, railway=r, nodes=ids, coords=c, **{kk: t.get(kk, "") for kk in KEEP}))

    def relation(s, r):
        t = r.tags
        if t.get("type") == "route" and t.get("route") in ("train", "railway", "subway", "light_rail", "tracks"):
            s.rel.append(dict(id=r.id, route=t.get("route"), name=t.get("name", ""), ref=t.get("ref", ""),
                              operator=t.get("operator", ""), members=[m.ref for m in r.members if m.type == "w"],
                              stops=[m.ref for m in r.members if m.type == "n" and m.role.startswith("stop")]))


h = H(); h.apply_file(src, locations=True)
json.dump(dict(ways=h.ways, st=h.st, rel=h.rel), open(out, "w"), ensure_ascii=False)
print(len(h.ways), len(h.st), len(h.rel), sum(1 for x in h.st if x["kind"] == "hist"))
