from shapely.geometry import mapping, MultiPolygon
from shapely.geometry.polygon import orient
from shapely.ops import unary_union, polylabel
def rnd(o):
    if isinstance(o,(list,tuple)):
        if o and isinstance(o[0],(int,float)): return [round(o[0],4),round(o[1],4)]
        return [rnd(x) for x in o]
    return o
def geo(g):
    g=g.simplify(0.0006,preserve_topology=True)
    if g.geom_type=='GeometryCollection': g=unary_union([x for x in g.geoms if x.area>0])
    if g.geom_type=='Polygon': g=orient(g,-1.0)
    elif g.geom_type=='MultiPolygon': g=MultiPolygon([orient(p,-1.0) for p in g.geoms])
    return {'type':g.geom_type,'coordinates':rnd(mapping(g)['coordinates'])}
def lab(g):
    if g.geom_type=='MultiPolygon': g=max(g.geoms,key=lambda p:p.area)
    try: p=polylabel(g,0.003)
    except Exception: p=g.representative_point()
    return [round(p.x,4),round(p.y,4)]
