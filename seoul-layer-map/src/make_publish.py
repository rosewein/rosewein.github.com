"""seoul-tram-boundary.html(아티팩트용 조각) → 공개용 폴더(index.html + src + data)"""
import re, shutil, os, sys
B = "/home/claude/data/build"
P = sys.argv[1] if len(sys.argv) > 1 else "/home/claude/data/publish/seoul-layer-map"
os.makedirs(f"{P}/src", exist_ok=True); os.makedirs(f"{P}/data", exist_ok=True)
html = open(f"{B}/seoul-tram-boundary.html").read().replace('<meta name="claude:viewport-fit-sides" content="cover">\n', '')
m = re.match(r'\s*<title>(.*?)</title>\n', html)
title = m.group(1); body = html[m.end():]
k = body.index('<style>'); pre, rest = body[:k], body[k:]
e = rest.index('</style>') + len('</style>'); style, rest = rest[:e], rest[e:]
desc = "1899년 경인선과 전차부터 지하철·철도·버스까지, 서울의 교통망과 시역·행정구역이 바뀌어 온 과정을 연도별 레이어로 겹쳐 보는 지도"
doc = f'''<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>{title}</title>
<meta name="description" content="{desc}">
<meta property="og:title" content="{title}">
<meta property="og:description" content="{desc}">
<meta property="og:type" content="website">
{pre}{style}
</head>
<body>
{rest}
</body>
</html>
'''
open(f"{P}/index.html", "w").write(doc)
SRC = ["template.html", "method.html", "build.py", "make_publish.py", "gazetteer.py", "geom.py", "roads.py", "rail_build.py", "metro_build.py",
       "gu_periods.py", "bus_parse.py", "bus_build.py", "bus_route.py", "bus2026.py", "route_years.py", "bus_dead_parse.py", "bus_dead_route.py", "village.py", "village_clip.py"]
for f in SRC:
    if os.path.exists(f"{B}/{f}"): shutil.copy(f"{B}/{f}", f"{P}/src/{f}")
shutil.copy("/home/claude/data/bus/namu/namu_open_years.py", f"{P}/src/namu_open_years.py")
shutil.copy("/home/claude/data/bus/namu_post/dead_supp.py", f"{P}/src/dead_supp.py")
DATA = ["tram.json", "years.json", "gu_periods.json", "emd_topo.json", "events_extra.json", "metro.json", "metro_events.json", "metro_dates.json",
        "metro_extra.json", "rail.json", "rail_events.json", "rail_open.json", "rail_alias.json", "place_alias.json", "bus.json", "bus_events.json",
        "bus2026.json", "route_years.json", "dead_routes.json", "village_layer.json"]
for f in DATA:
    if os.path.exists(f"{B}/{f}"): shutil.copy(f"{B}/{f}", f"{P}/data/{f}")
print("index.html", len(doc), "bytes →", P)
