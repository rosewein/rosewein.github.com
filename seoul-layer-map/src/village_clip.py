"""village.json → village_layer.json: '마을버스로만 닿는 곳'을 서울시 경계로 자르고 면적을 다시 잰다."""
import json
from shapely.geometry import Polygon, MultiPolygon, shape, mapping
from shapely.ops import unary_union

B = "/home/claude/data/build"
KX, KY = 88.4, 111.0
topo = json.load(open(f"{B}/emd_topo.json"))
sx, sy = topo["transform"]["scale"]; tx, ty = topo["transform"]["translate"]
arcs = []
for a in topo["arcs"]:
    x = y = 0; pts = []
    for dx, dy in a:
        x += dx; y += dy
        pts.append(((x * sx + tx) * KX, (y * sy + ty) * KY))
    arcs.append(pts)


def ring(idx):
    pts = []
    for i in idx:
        seg = arcs[i] if i >= 0 else arcs[~i][::-1]
        pts.extend(seg if not pts else seg[1:])
    return pts


polys = []
for g in topo["objects"]["seoul_neighborhoods_geo"]["geometries"]:
    parts = g["arcs"] if g["type"] == "Polygon" else [p for mp in g["arcs"] for p in [mp]]
    if g["type"] == "Polygon": parts = [g["arcs"]]
    for p in parts:
        rr = [ring(r) for r in p]
        try: polys.append(Polygon(rr[0], rr[1:]).buffer(0))
        except Exception: pass
seoul = unary_union(polys).buffer(0.02).buffer(-0.02)
print("seoul area km2", round(seoul.area, 1))

V = json.load(open(f"{B}/village.json"))
out = {"years": {}}
for y, r in sorted(V["years"].items()):
    g = r.get("only")
    if g:
        mp = MultiPolygon([Polygon([(x * KX, yy * KY) for x, yy in poly[0]], [[(x * KX, yy * KY) for x, yy in h] for h in poly[1:]]) for poly in g["coordinates"]]).buffer(0)
        mp = mp.intersection(seoul)
    else:
        mp = None
    polys_out = []
    if mp is not None and not mp.is_empty:
        for p in (mp.geoms if hasattr(mp, "geoms") else [mp]):
            if p.geom_type != "Polygon" or p.area < 0.01: continue
            p = p.simplify(0.02)
            polys_out.append([[[round(x / KX, 5), round(yy / KY, 5)] for x, yy in rr.coords] for rr in [p.exterior] + list(p.interiors)])
    stops_in = [s for s in r["stops"]]
    out["years"][y] = {"routes": r["v_routes"], "stops": stops_in, "nstops": len(stops_in), "day": r.get("day"),
                       "only_km2": round(mp.area, 1) if mp is not None else 0,
                       "only": {"type": "MultiPolygon", "coordinates": polys_out}}
    print(y, r["v_routes"], len(stops_in), "only (clipped)", out["years"][y]["only_km2"], "of", r["only_area"])
json.dump(out, open(f"{B}/village_layer.json", "w"), ensure_ascii=False, separators=(",", ":"))
