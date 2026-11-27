# 1910년 5월 전(경계 자료 없는 해)에 깔 땅 모양: 첫 경계 시점(1910-05-10)의 부·군 폴리곤을 합침
import os as _os, sys as _sys  # paths.py 찾기: 이 파일 폴더에서 위로 올라감(저장소 src/, 작업 공간 $MLM_SUDO·$MLM_SUDO2)
_d = _os.path.dirname(_os.path.abspath(__file__))
while _d != _os.path.dirname(_d) and not _os.path.isfile(_os.path.join(_d, 'paths.py')):
    _d = _os.path.dirname(_d)
_sys.path.insert(1, _d)
from paths import PAGE_DATA  # noqa: E402
import json
from shapely.geometry import shape, mapping, MultiPolygon
from shapely.geometry.polygon import orient
from shapely.ops import unary_union
P=PAGE_DATA
d=json.load(open(P))
print('snap0', d['snaps'][0])
g=unary_union([shape(v['geo']).buffer(0) for v in d['sgg'] if v['fr']<=0<=v['to']])
g=g.buffer(0.0005).buffer(-0.0005).simplify(0.0008,preserve_topology=True)
ps=[g] if g.geom_type=='Polygon' else list(g.geoms)
g=MultiPolygon([orient(p,-1.0) for p in ps if p.area>1e-7])
def rnd(o):
    if isinstance(o,(list,tuple)):
        if o and isinstance(o[0],(int,float)): return [round(o[0],4),round(o[1],4)]
        return [rnd(x) for x in o]
    return o
m=mapping(g); d['land0']={'type':m['type'],'coordinates':rnd(m['coordinates'])}
json.dump(d,open(P,'w'),ensure_ascii=False,separators=(',',':'))
print(len(ps), len(json.dumps(d['land0'])))
