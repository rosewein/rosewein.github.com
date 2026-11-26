"""물길(지금 기준): OSM 추출본에서 한강 등 수면 면과 이름 있는 물길 선을 뽑아 data/water.json을 만든다.

python3 src/water.py   (원자료: $SLM_RAW/osm/seoul/Seoul.osm.pbf, BBBike 서울 추출본. pip install osmium shapely pyproj)

- 수면: natural=water(water=river·lake·reservoir 등), waterway=riverbank, landuse=reservoir 면을 합친다.
  3ha보다 작은 못과 하수처리장 물(wastewater)은 뺀다. 서울 경계 밖 1km까지 남겨 강서–고양처럼 경계가 강 한가운데를 지나는 곳에서도 강폭이 잘리지 않게 한다.
- 추출본 가장자리에서 회원 길(way)이 빠져 면이 안 만들어지는 물 관계(한강 152336 등)는, 남은 바깥 테두리 길을 이어 빈 곳을 곧은 선으로 닫아 만든다.
  닫는 선은 추출본 가장자리(서울에서 멀리)에 생기므로 서울 둘레 1km로 자르면 남지 않는다.
- 물길 선: waterway=river·stream 가운데 이름 있고, 터널·복개(tunnel·covered)가 아니며, 서울 경계 150m 안에서 1.5km 넘는 것.
  한강은 수면 면이 있으므로 선은 뺀다. cls: r = OSM river, s = stream(OSM 기여자가 붙인 등급이라 법정 하천 등급과 다름).
- 형상은 EPSG:5179에서 12m로 단순화하고 경위도 소수 다섯째 자리로 줄인다.
"""
import json, os, sys
sys.dont_write_bytecode = True
from collections import defaultdict
import numpy as np
import osmium
from shapely.geometry import LineString, Polygon, MultiPolygon, mapping
from shapely import wkb, ops
import shapely
from pyproj import Transformer
from paths import DATA, RAW

PBF = os.path.join(RAW, "osm/seoul/Seoul.osm.pbf")
TOPO = os.path.join(DATA, "emd_topo.json")
OUT = os.path.join(DATA, "water.json")
BUF, LBUF, TOL = 1000, 150, 12
fw = Transformer.from_crs(4326, 5179, always_xy=True).transform
bw = Transformer.from_crs(5179, 4326, always_xy=True).transform
fab = osmium.geom.WKBFactory()


def seoul_poly():
    t = json.load(open(TOPO)); sx, sy = t["transform"]["scale"]; tx, ty = t["transform"]["translate"]
    arcs = []
    for a in t["arcs"]:
        x = y = 0; pts = []
        for dx, dy in a: x += dx; y += dy; pts.append((x * sx + tx, y * sy + ty))
        arcs.append(pts)
    def ring(idx):
        out = []
        for i in idx:
            p = arcs[i] if i >= 0 else arcs[~i][::-1]
            out.extend(p if not out else p[1:])
        return out
    polys = []
    for g in t["objects"]["seoul_neighborhoods_geo"]["geometries"]:
        for p in ([g["arcs"]] if g["type"] == "Polygon" else g["arcs"]):
            polys.append(Polygon(ring(p[0]), [ring(r) for r in p[1:]]).buffer(0))
    return shapely.transform(ops.unary_union(polys), _xy)


def _xy(c):
    x, y = fw(c[:, 0], c[:, 1]); return np.column_stack([x, y])


def to5179(g):
    return shapely.transform(g, _xy)


def merge(gs):
    u = ops.unary_union(gs)
    if u.geom_type == "LineString": return [u]
    m = ops.linemerge(u)
    return list(getattr(m, "geoms", [m]))


def broken_relations():
    """회원 길이 빠진 물 관계를 손으로 닫아 면으로 만든다."""
    rels = {}
    class R(osmium.SimpleHandler):
        def relation(self, r):
            t = r.tags
            if t.get("type") == "multipolygon" and (t.get("natural") == "water" or t.get("waterway") == "riverbank"):
                rels[r.id] = (t.get("name", ""), t.get("water", ""), [(m.ref, m.role) for m in r.members if m.type == "w"])
    R().apply_file(PBF)
    want = {m[0] for v in rels.values() for m in v[2]}
    geo = {}
    class W(osmium.SimpleHandler):
        def way(self, w):
            if w.id in want:
                try: geo[w.id] = to5179(wkb.loads(fab.create_linestring(w), hex=True))
                except Exception: pass
    W().apply_file(PBF, locations=True)
    out = []
    for rid, (nm, wt, ms) in rels.items():
        if all(m in geo for m, _ in ms) or wt not in ("river", ""): continue
        outer = [geo[m] for m, r in ms if m in geo and r in ("outer", "")]
        inner = [geo[m] for m, r in ms if m in geo and r == "inner"]
        if not outer: continue
        chains = merge(outer)
        rings = [c for c in chains if c.is_ring]
        opn = [list(c.coords) for c in chains if not c.is_ring]
        while opn:   # 열린 사슬은 끝을 가장 가까운 사슬에 잇고, 마지막에 처음으로 닫는다
            cur = opn.pop(0)
            while opn:
                end = cur[-1]
                d = lambda k: min(LineString([end, opn[k][0]]).length, LineString([end, opn[k][-1]]).length)
                nxt = opn.pop(min(range(len(opn)), key=d))
                if LineString([end, nxt[-1]]).length < LineString([end, nxt[0]]).length: nxt = nxt[::-1]
                cur = cur + nxt
            rings.append(LineString(cur + [cur[0]]))
        poly = ops.unary_union([Polygon(r.coords).buffer(0) for r in rings])
        holes = [Polygon(r.coords).buffer(0) for r in merge(inner) if r.is_ring] if inner else []
        if holes: poly = poly.difference(ops.unary_union(holes))
        print("closed relation", rid, nm, "missing", sum(1 for m, _ in ms if m not in geo), "of", len(ms), file=sys.stderr)
        out.append(poly)
    return out


def main():
    seoul = seoul_poly(); clip = seoul.buffer(BUF); lclip = seoul.buffer(LBUF)
    areas = []; lines = defaultdict(list)
    class H(osmium.SimpleHandler):
        def way(self, w):
            tg = w.tags
            if tg.get("waterway") not in ("river", "stream") or not tg.get("name"): return
            if tg.get("tunnel") or tg.get("covered") == "yes" or tg.get("layer", "0").startswith("-"): return
            try: g = to5179(wkb.loads(fab.create_linestring(w), hex=True))
            except Exception: return
            if g.intersects(lclip): lines[(tg["name"], tg["waterway"])].append(g)
        def area(self, a):
            tg = a.tags
            if not (tg.get("natural") == "water" or tg.get("waterway") == "riverbank" or tg.get("landuse") == "reservoir"): return
            kind = tg.get("water", tg.get("waterway", tg.get("landuse", "")))
            if kind in ("wastewater", "reflecting_pool", "fountain"): return
            try: g = to5179(wkb.loads(fab.create_multipolygon(a), hex=True))
            except Exception: return
            if not g.intersects(clip): return
            if kind in ("lake", "reservoir", "pond", "basin") and g.area < 30000: return
            areas.append(g.buffer(0))
    H().apply_file(PBF, locations=True)
    areas += [p for p in broken_relations() if p.intersects(clip)]
    water = shapely.make_valid(ops.unary_union(areas).intersection(clip).simplify(TOL, preserve_topology=True))
    parts = [p for p in getattr(water, "geoms", [water]) if p.geom_type == "Polygon" and p.area > 5000]
    water = MultiPolygon(parts)
    print(f"water: {water.area / 1e6:.2f}km² (서울 안 {water.intersection(seoul).area / 1e6:.2f}km²), {len(parts)} parts", file=sys.stderr)
    feats = []
    for (nm, ww), gs in lines.items():
        if nm == "한강": continue
        m = (ops.linemerge(ops.unary_union(gs)) if len(gs) > 1 else gs[0]).intersection(lclip)
        if m.length < 1500: continue
        feats.append((-m.length, nm, "r" if ww == "river" else "s", m.simplify(TOL)))
    feats.sort()
    def ll(g):
        gj = mapping(shapely.transform(g, lambda c: np.column_stack(bw(c[:, 0], c[:, 1]))))
        def rnd(c):
            if c and isinstance(c[0], (int, float)): return [round(c[0], 5), round(c[1], 5)]
            return [rnd(x) for x in c]
        return {"type": gj["type"], "coordinates": rnd(gj["coordinates"])}
    out = {"src": "OSM BBBike 서울 추출본 2026-11-22", "area": ll(water),
           "lines": [{"name": nm, "cls": c, "km": round(-L / 1000, 1), "geom": ll(g)} for L, nm, c, g in feats]}
    s = json.dumps(out, ensure_ascii=False, separators=(",", ":"))
    open(OUT, "w").write(s)
    print("lines", len(feats), ", ".join(f"{nm}({c})" for _, nm, c, _ in feats), file=sys.stderr)
    print("wrote", OUT, len(s.encode()), "bytes", file=sys.stderr)


if __name__ == "__main__":
    main()
