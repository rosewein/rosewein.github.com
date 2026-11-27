"""궁궐 위치 초안: OSM 추출본에서 지금 궁역·건물 자리를 뽑고, 옮겨 간 건물의 출발·도착 지점을 붙여 data/palace_geo.json을 만든다.

python3 src/palaces.py   (원자료: $SLM_RAW/osm/seoul/Seoul.osm.pbf)

- 궁역(areas)은 지금 모습이다. 옛 궁역(일제강점기 전 경희궁·경운궁 등)은 아직 그리지 않았다.
- 점(points)의 conf: 높음 = OSM에 그 건물이 있음, 중간 = 자료에 적힌 거리·방향으로 옮겨 잡음, 낮음 = 대략의 자리.
- 사건 id는 data/palace_events.csv의 id와 같다.
"""
import csv, json, math, os, osmium
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

# 사건표에서 지도에 쓰는 해: 자료마다 해가 다르면 가장 이른 해(「지도 해」)를 쓰고 다른 해는 괄호(「지도 괄호」)에 적는다(이지가 정함, 2026-11-26)
EV = {r["id"]: (int(r["지도 해"]), r["지도 괄호"]) for r in csv.DictReader(open(F("palace_events.csv"), encoding="utf-8-sig"))}
Y = lambda e: e if isinstance(e, int) else EV[e][0]   # 해 또는 사건 id

def spans(bounds, last=2100):
    """[[시작(해 또는 사건 id), 값], ...] → [[처음 해, 끝 해, 값], ...]. 다음 시작 전 해까지, 값이 None이면 그 구간은 뺌"""
    ys = [Y(b[0]) for b in bounds]
    return [[y, (ys[k + 1] - 1 if k + 1 < len(ys) else last), b[1]] for k, (y, b) in enumerate(zip(ys, bounds)) if b[1] is not None]

# 궁마다 상태가 바뀌는 때. 상태: 궁(궁으로 쓰임) / 훼손(크게 헐리거나 다른 쓰임) / 복원(복원 사업 중·뒤)
# 1899년 앞 시작 해는 조선 후기 단계(1898 자리)만 보므로 손으로 둔다
PHASES = {
    "gbg": [[1868, "궁"], ["gbg-1915-1", "훼손"], ["gbg-1990-1", "복원"]],
    "cdg": [[1610, "궁"], ["cdg-1917-1", "훼손"], ["cdg-1920-1", "궁"]],
    "cgg": [[1834, "궁"], ["cgg-1909-1", "훼손"], ["cgg-1983-1", "복원"]],
    "ghg": [[1832, "궁"], ["ghg-1865-1", "훼손"], ["ghg-1988-1", "복원"]],
    "gug": [[1897, "궁"], ["gug-1933-1", "훼손"], ["gug-2007-1", "복원"]],
}
# 궁 이름 아래 짧은 설명: [사건 id, 글]. 그 해부터 NOTE_YEARS 동안만 보인다. 해와 괄호는 사건표에서
NOTE_YEARS = 5
NOTES = {
    "gbg": [["gbg-1896-1", "아관파천으로 임금이 떠남"], ["gbg-1915-1", "공진회로 전각 헐림"], ["gbg-1926-1", "조선총독부 청사"],
            ["gbg-1927-1", "광화문을 동쪽으로 옮김"], ["gbg-1950-1", "광화문 문루 불탐"], ["gbg-1968-1", "광화문 다시 세움, 제자리 아님"],
            ["gbg-1990-1", "복원 사업 시작"], ["gbg-1995-1", "총독부 청사 철거 시작"], ["gbg-2010-1", "광화문 제자리로"]],
    "cdg": [["cdg-1907-1", "순종 거처"], ["cdg-1917-1", "내전 큰불"], ["cdg-1920-1", "내전 다시 지음"], ["cdg-1990-1", "복원 사업 시작"]],
    "cgg": [["cgg-1909-1", "동·식물원 들어섬"], ["cgg-1911-1", "창경원으로 낮춤"], ["cgg-1983-1", "창경궁으로 되돌림"], ["cgg-1984-1", "동물원 과천으로"]],
    "ghg": [["ghg-1910-1", "일본인 중학교 들어섬"], ["ghg-1926-1", "숭정전 팔려 감"], ["ghg-1932-1", "흥화문 옮겨 감"], ["ghg-1988-1", "흥화문 되옮김"]],
    "gug": [["gug-1897-2", "대한제국 황궁"], ["gug-1904-1", "큰불"], ["gug-1907-1", "덕수궁으로 이름 바꿈"], ["gug-1910-1", "석조전 준공"],
            ["gug-1933-1", "공원으로 엶"], ["gug-1970-1", "대한문 33m 물림"], ["gug-2007-1", "복원 사업 시작"]],
}
# 해에 따라 바뀌는 이름: 바뀌는 때와 이름(None이면 기본 이름으로)
NAMES = {
    "gug": [[1611, "경운궁"], ["gug-1907-1", "덕수궁"]],
    "cgg": [["cgg-1911-1", "창경원"], ["cgg-1983-1", None]],
}
note_out = lambda pid: [[Y(e), t, e, EV[e][1]] for e, t in NOTES[pid]]   # [해, 글, 사건 id, 괄호]
areas = []
for pid, (name, oid, note) in AREAS.items():
    g = geoms[oid].simplify(0.00002, preserve_topology=True)
    # d3-geo는 바깥 고리가 시계 방향이어야 작은 면으로 그린다(GeoJSON 표준과 반대). 반대로 두면 지구 전체를 칠함
    g = MultiPolygon([orient(q, sign=-1.0) for q in (g.geoms if g.geom_type == "MultiPolygon" else [g])])
    areas.append({"id": pid, "name": name, "osm": oid, "note": note,
                  "geom": json.loads(json.dumps(mapping(g), default=list)), "c": centroid(pid),
                  "phases": spans(PHASES[pid]), "notes": note_out(pid), "names": spans(NAMES.get(pid, []))})

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
for m in moves:   # 해와 괄호는 사건표(「지도 해」·「지도 괄호」)에서. 위 "y"는 읽기 쉽게 둔 사건표 「서기」
    m["y"], m["alt"] = EV[m["ev"]]
# 이름표의 칭호: 고종은 1897년 10월 12일 황제 즉위(대한제국 선포) 전까지 왕, 그 뒤 황제. 순종은 황제(1907–1910)
# 연도 단위 지도라 즉위한 해(1897)는 "왕 → 황제"로 적는다
# 1868–1896년 고종의 경복궁·창덕궁 오가기는 몇 해씩 머문 것만 넣는다(이지가 정함, 2026-11-27: 「거처 별표에만 쓰고 너무 자세히는 들어가지 말자」).
# 지도는 해마다 from 해 ≤ 그 해 < to 해인 구간 하나를 고르므로, 1894년 창덕궁(양력 5월 7일–6월 27일)처럼 한 해 안에 돌아온 이동은 넣지 않는다.
# 날짜는 『고종실록』(음력)을 양력으로 바꾼 것. 사건표에 줄을 따로 두지 않은 이동의 근거는 줄 끝 주석
residence = [  # 임금이 머문 곳(1868년부터, 큰 이동만)
    {"from": "1868-08-19", "to": "1874-02-06", "who": "고종", "title": "왕", "at": P("경복궁", centroid("gbg"), "높음"), "ev": "gbg-1868-1"},
    {"from": "1874-02-06", "to": "1875-06-30", "who": "고종", "title": "왕", "at": P("창덕궁", centroid("cdg"), "높음"), "ev": "gbg-1873-2"},   # 『고종실록』 10년 12월 20일 기사 1(자경전 화재 뒤 창덕궁 이어), 12년 5월 27일 기사 2(경복궁 이어)
    {"from": "1875-06-30", "to": "1877-04-23", "who": "고종", "title": "왕", "at": P("경복궁", centroid("gbg"), "높음")},   # 『고종실록』 12년 5월 27일 기사 2, 14년 3월 10일 기사 1(창덕궁 이어)
    {"from": "1877-04-23", "to": "1885", "who": "고종", "title": "왕", "at": P("창덕궁", centroid("cdg"), "높음")},   # 『고종실록』 14년 3월 10일 기사 1. 경복궁으로 돌아간 것은 고종 행장(『순종실록부록』 12년 3월 4일 기사 4)의 을유년(1885) 기사, 날짜는 안 봄
    {"from": "1885", "to": "1896-02-11", "who": "고종", "title": "왕", "at": P("경복궁", centroid("gbg"), "높음")},   # 고종 행장 을유년. 1894년 양력 5–6월 창덕궁에 머문 것(『고종실록』 31년 4월 3일·5월 24일)은 넣지 않음
    {"from": "1896-02-11", "to": "1897-02-20", "who": "고종", "title": "왕", "at": P("러시아 공사관", pt("구러시아공사관"), "높음", "OSM(옛 공사관 탑)"), "ev": "gbg-1896-1"},
    {"from": "1897-02-20", "to": "1907-11", "who": "고종", "title": "황제", "title_y": {"1897": "왕 → 황제"}, "at": P("경운궁", centroid("gug"), "높음"), "ev": "gug-1897-1", "note": "1904년 화재 뒤 한동안 수옥헌(중명전)"},
    {"from": "1907-11", "to": "1910-08-29", "who": "순종", "title": "황제", "at": P("창덕궁", centroid("cdg"), "높음"), "ev": "cdg-1907-1", "note": "11월 날짜는 2차 자료"},
]
out = {"note": "궁궐 위치 초안(옛 지도 갈래). 궁역은 지금 모습(OSM 2026-11-22 추출본). 사건은 data/palace_events.csv", "noteYears": NOTE_YEARS,
       "areas": areas, "moves": moves, "residence": residence}
json.dump(out, open(F("palace_geo.json"), "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
print("areas", len(areas), "moves", len(moves), "residence", len(residence), os.path.getsize(F("palace_geo.json")), "bytes")
