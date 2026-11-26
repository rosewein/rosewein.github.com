"""궁궐 위치 초안: OSM 추출본에서 지금 궁역·건물 자리를 뽑고, 옮겨 간 건물의 출발·도착 지점을 붙여 data/palace_geo.json을 만든다.

python3 src/palaces.py   (원자료: $SLM_RAW/osm/seoul/Seoul.osm.pbf)

- 궁역(areas)은 지금 모습이다. 옛 궁역(일제강점기 전 경희궁·경운궁 등)은 아직 그리지 않았다.
- 점(points)의 conf: 높음 = OSM에 그 건물이 있음, 중간 = 자료에 적힌 거리·방향으로 옮겨 잡음, 낮음 = 대략의 자리.
- 사건 id는 data/palace_events.csv의 id와 같다.
"""
import json, math, os, osmium
from shapely.geometry import shape, mapping, MultiPolygon
from shapely.geometry.polygon import orient
from paths import RAW, DATA
F = lambda n: os.path.join(DATA, n)

PBF = os.path.join(RAW, "osm", "seoul", "Seoul.osm.pbf")

AREAS = {  # 궁 id: (이름, OSM id, 메모)
    "gbg": ("경복궁", "r5501517", ""),
    "cdg": ("창덕궁", "w789965985", "후원 포함"),
    "cgg": ("창경궁", "w380863257", ""),
    "ghg": ("경희궁", "w768471592", "지금 남은 터(경희궁공원). 옛 궁역은 훨씬 넓었음(1910년 뒤 절반 가까이 줄었다는 2차 서술)"),
    "gug": ("덕수궁", "w26658458", "지금 궁역. 대한제국 때 궁역은 더 넓었음"),
}
BLDG = {  # 건물 이름: OSM id
    "광화문": "w170199440", "흥화문": "w196071778", "숭정전(경희궁, 복원)": "w196072052",
    "정각원(동국대, 옛 숭정전)": "w268779564", "구세군회관": "w518561419", "서울신라호텔": "w268851642",
    "대한문": "w377289797", "강녕전": "w170199477", "교태전": "w279961704", "대조전": "w612979921", "희정당": "w612979907",
    "황학정": "n12040274799", "구러시아공사관": "n6072006686", "중명전": "w646147127", "석조전": "r19357693",
}

want = {v for _, v, _ in AREAS.values()} | set(BLDG.values())
geoms = {}
fab = osmium.geom.GeoJSONFactory()

class H(osmium.SimpleHandler):
    def area(self, a):
        k = ("w" if a.from_way() else "r") + str(a.orig_id())
        if k in want:
            try: geoms[k] = shape(json.loads(fab.create_multipolygon(a)))
            except Exception: pass
    def node(self, n):
        k = "n" + str(n.id)
        if k in want: geoms[k] = (n.location.lon, n.location.lat)

H().apply_file(PBF, locations=True)

def pt(name):
    g = geoms[BLDG[name]]
    if isinstance(g, tuple): return [round(g[0], 6), round(g[1], 6)]
    c = g.representative_point(); return [round(c.x, 6), round(c.y, 6)]

def offset(p, north_m=0.0, east_m=0.0):
    lat = p[1] + north_m / 111320.0
    lng = p[0] + east_m / (111320.0 * math.cos(math.radians(p[1])))
    return [round(lng, 6), round(lat, 6)]

def centroid(pid):
    c = geoms[AREAS[pid][1]].representative_point(); return [round(c.x, 6), round(c.y, 6)]

# 궁마다 상태 구간 [처음 해, 끝 해, 상태]. 상태: 궁(궁으로 쓰임) / 훼손(크게 헐리거나 다른 쓰임) / 복원(복원 사업 중·뒤)
# 사건표(palace_events.csv)를 보고 손으로 정한 것. 1899년 앞은 조선 후기 단계(1898 자리)만 보므로 거칠게 둔다
PHASES = {
    "gbg": [[1868, 1914, "궁"], [1915, 1989, "훼손"], [1990, 2100, "복원"]],
    "cdg": [[1610, 1916, "궁"], [1917, 1919, "훼손"], [1920, 2100, "궁"]],
    "cgg": [[1834, 1908, "궁"], [1909, 1983, "훼손"], [1984, 2100, "복원"]],
    "ghg": [[1832, 1864, "궁"], [1865, 1987, "훼손"], [1988, 2100, "복원"]],
    "gug": [[1897, 1932, "궁"], [1933, 2006, "훼손"], [2007, 2100, "복원"]],
}
# 궁 이름 아래 짧은 설명: [해, 글, 사건 id]. 그 해부터 NOTE_YEARS 동안만 보인다
NOTE_YEARS = 5
NOTES = {
    "gbg": [[1896, "임금이 떠남(아관파천)", "gbg-1896-1"], [1915, "공진회로 전각 헐림", "gbg-1915-1"], [1926, "조선총독부 청사", "gbg-1926-1"],
            [1927, "광화문을 동쪽으로 옮김", "gbg-1927-1"], [1950, "광화문 문루 불탐", "gbg-1950-1"], [1968, "광화문 다시 세움(제자리 아님)", "gbg-1968-1"],
            [1990, "복원 사업 시작", "gbg-1990-1"], [1995, "총독부 청사 철거(–1996)", "gbg-1995-1"], [2010, "광화문 제자리로", "gbg-2010-1"]],
    "cdg": [[1907, "순종 거처", "cdg-1907-1"], [1917, "내전 큰불", "cdg-1917-1"], [1920, "내전 다시 지음", "cdg-1920-1"], [1990, "복원 사업 시작", "cdg-1990-1"]],
    "cgg": [[1909, "동·식물원 엶", "cgg-1909-1"], [1911, "창경원으로 낮춤", "cgg-1911-1"], [1983, "창경궁으로 되돌림", "cgg-1983-1"], [1984, "동물원 과천으로", "cgg-1984-1"]],
    "ghg": [[1910, "경성중학교 들어섬", "ghg-1910-1"], [1926, "숭정전 팔려 감", "ghg-1926-1"], [1932, "흥화문 옮겨 감", "ghg-1932-1"], [1988, "흥화문 되옮김", "ghg-1988-1"]],
    "gug": [[1897, "대한제국 황궁", "gug-1897-2"], [1904, "큰불", "gug-1904-1"], [1907, "덕수궁으로 이름 바꿈", "gug-1907-1"], [1910, "석조전 준공", "gug-1910-1"],
            [1933, "공원으로 엶", "gug-1933-1"], [1970, "대한문 33m 물림", "gug-1970-1"], [2007, "복원 사업 시작", "gug-2007-1"]],
}
# 해에 따라 바뀌는 이름: [처음 해, 끝 해, 이름]. 없으면 기본 이름
NAMES = {
    "gug": [[1611, 1906, "경운궁"], [1907, 2100, "덕수궁"]],
    "cgg": [[1911, 1983, "창경원"]],
}
areas = []
for pid, (name, oid, note) in AREAS.items():
    g = geoms[oid].simplify(0.00002, preserve_topology=True)
    # d3-geo는 바깥 고리가 시계 방향이어야 작은 면으로 그린다(GeoJSON 표준과 반대). 반대로 두면 지구 전체를 칠함
    g = MultiPolygon([orient(q, sign=-1.0) for q in (g.geoms if g.geom_type == "MultiPolygon" else [g])])
    areas.append({"id": pid, "name": name, "osm": oid, "note": note,
                  "geom": json.loads(json.dumps(mapping(g), default=list)), "c": centroid(pid),
                  "phases": PHASES[pid], "notes": NOTES[pid], "names": NAMES.get(pid, [])})

gw = pt("광화문")
P = lambda name, p, conf, src="": {"name": name, "p": p, "conf": conf, "src": src}
moves = [
    {"ev": "gbg-1920-1", "y": 1920, "what": "강녕전·교태전 → 창덕궁 내전", "from": P("경복궁 강녕전·교태전", pt("강녕전"), "높음", "OSM(지금 복원된 자리)"),
     "to": P("창덕궁 대조전·희정당", pt("대조전"), "높음", "OSM")},
    {"ev": "gbg-1927-1", "y": 1927, "what": "광화문 → 건춘문 북쪽", "from": P("광화문 원래 자리", gw, "높음", "OSM(2010년 원래 자리에 다시 세움)"),
     "to": P("건춘문 북쪽(지금 국립민속박물관 정문 쪽)", [126.9797, 37.5803], "낮음", "국가기록원 서술로 대략 잡음")},
    {"ev": "gbg-1968-1", "y": 1968, "what": "광화문 다시 세움(원래 자리 아님)", "from": P("건춘문 북쪽", [126.9797, 37.5803], "낮음"),
     "to": P("1968년 자리", offset(gw, 11.2, 13.5), "중간", "원래 자리에서 북 11.2m·동 13.5m(서울신문 2010-08-14)")},
    {"ev": "gbg-2010-1", "y": 2010, "what": "광화문 원래 자리로", "from": P("1968년 자리", offset(gw, 11.2, 13.5), "중간"),
     "to": P("원래 자리", gw, "높음", "OSM")},
    {"ev": "ghg-1923-1", "y": 1923, "what": "황학정 → 사직단 뒤", "from": P("경희궁 안(정확한 자리 모름)", centroid("ghg"), "낮음"),
     "to": P("사직단 뒤 황학정", pt("황학정"), "높음", "OSM")},
    {"ev": "ghg-1926-1", "y": 1926, "what": "숭정전 → 조계사(지금 동국대 정각원)", "from": P("경희궁 숭정전 자리", pt("숭정전(경희궁, 복원)"), "중간", "발굴로 찾은 자리에 복원(2차)"),
     "to": P("동국대 정각원", pt("정각원(동국대, 옛 숭정전)"), "높음", "OSM")},
    {"ev": "ghg-1928-1", "y": 1928, "what": "흥정당 → 광운사", "from": P("경희궁(정확한 자리 모름)", centroid("ghg"), "낮음"),
     "to": None, "note": "광운사 자리를 찾지 못함"},
    {"ev": "ghg-1932-1", "y": 1932, "what": "흥화문 → 박문사 산문(장충동)", "from": P("흥화문 원래 자리(지금 구세군회관 자리)", pt("구세군회관"), "중간", "서울시 글(2차)"),
     "to": P("박문사(지금 신라호텔 자리)", pt("서울신라호텔"), "낮음", "호텔 건물로 대략 잡음")},
    {"ev": "ghg-1988-1", "y": 1988, "what": "흥화문 → 경희궁 쪽(원래 자리 아님)", "from": P("신라호텔 정문", pt("서울신라호텔"), "낮음"),
     "to": P("지금 흥화문", pt("흥화문"), "높음", "OSM")},
    {"ev": "gug-1970-1", "y": 1970, "what": "대한문 33m 물림", "from": P("대한문 원래 자리", offset(pt("대한문"), 0, 33), "중간", "지금 자리에서 동쪽(세종대로 쪽) 33m로 잡음. 방향은 추정"),
     "to": P("지금 대한문", pt("대한문"), "높음", "OSM")},
]
# 이름표의 칭호: 고종은 1897년 10월 12일 황제 즉위(대한제국 선포) 전까지 왕, 그 뒤 황제. 순종은 황제(1907–1910)
# 연도 단위 지도라 즉위한 해(1897)는 "왕 → 황제"로 적는다
residence = [  # 임금이 머문 곳(1868년부터, 큰 이동만)
    {"from": "1868-08-19", "to": "1896-02-11", "who": "고종", "title": "왕", "at": P("경복궁", centroid("gbg"), "높음"), "ev": "gbg-1868-1", "note": "1873년 자경전 화재 뒤 창덕궁으로 옮긴 기간은 아직 넣지 않음"},
    {"from": "1896-02-11", "to": "1897-02-20", "who": "고종", "title": "왕", "at": P("러시아 공사관", pt("구러시아공사관"), "높음", "OSM(옛 공사관 탑)"), "ev": "gbg-1896-1"},
    {"from": "1897-02-20", "to": "1907-11", "who": "고종", "title": "황제", "title_y": {"1897": "왕 → 황제"}, "at": P("경운궁", centroid("gug"), "높음"), "ev": "gug-1897-1", "note": "1904년 화재 뒤 한동안 수옥헌(중명전)"},
    {"from": "1907-11", "to": "1910-08-29", "who": "순종", "title": "황제", "at": P("창덕궁", centroid("cdg"), "높음"), "ev": "cdg-1907-1", "note": "11월 날짜는 2차 자료"},
]
out = {"note": "궁궐 위치 초안(옛 지도 갈래). 궁역은 지금 모습(OSM 2026-11-22 추출본). 사건은 data/palace_events.csv", "noteYears": NOTE_YEARS,
       "areas": areas, "moves": moves, "residence": residence}
json.dump(out, open(F("palace_geo.json"), "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
print("areas", len(areas), "moves", len(moves), "residence", len(residence), os.path.getsize(F("palace_geo.json")), "bytes")
