# 간선도로 레이어: OSM trunk·primary 지금 선형(바탕) + 날짜를 찾은 자동차전용도로(구간 개통일)
# 입력: RAW/osm/art.geojsonseq (sudo_bb에서 highway=trunk,primary,secondary)
# 출력: SUDO2/art.json (RAW·SUDO2는 src/paths.py)
import os as _os, sys as _sys  # paths.py 찾기: 이 파일 폴더에서 위로 올라감(저장소 src/, 작업 공간 $MLM_SUDO·$MLM_SUDO2)
_d = _os.path.dirname(_os.path.abspath(__file__))
while _d != _os.path.dirname(_d) and not _os.path.isfile(_os.path.join(_d, 'paths.py')):
    _d = _os.path.dirname(_d)
_sys.path.insert(1, _d)
from paths import RAW, SUDO2  # noqa: E402
import json, math
from collections import defaultdict
from shapely.geometry import shape, LineString
from shapely.ops import linemerge

def rnd(cs): return [[round(x, 5), round(y, 5)] for x, y in cs]

WK = 'https://ko.wikipedia.org/wiki/'
S_SEOUL_SW = ['서울특별시 보도(2021-04-15)', 'https://news.seoul.go.kr/citybuild/?p=512261']
S_GN1 = ['서울특별시 보도(2016-07)', 'https://news.seoul.go.kr/citybuild/?p=232528']
S_GN2 = ['서울특별시 보도(2020-12-18)', 'https://news.seoul.go.kr/citybuild/archives/511089']
S_SP1 = ['아주경제 2014-12-25 기사', 'https://www.ajunews.com/view/20141225162831797']
S_SP2 = ['경기일보 2023-05-30 기사', 'https://www.kyeonggi.com/article/20230530580131']
S_SI1 = ['서울신문 2015-04-21 기사', 'https://m.go.seoul.co.kr/news/2015/04/21/20150421011009']
S_SI2 = ['서울신문 2018-01-01 기사', 'https://m.go.seoul.co.kr/news/2018/01/01/20180101500018']
S_UM = ['영어 위키백과(검색 결과 요약)', 'https://en.wikipedia.org/wiki/Umyeonsan-ro']
def wk(n): return ['한국어 위키백과 노선 문서 연혁', WK + n]

# 각 노선: [(날짜, 조건(x,y)->bool, 구간 이름, 출처, 메모)]  위에서부터 처음 맞는 것
R = {
 '올림픽대로': [
  ('1986-05-02', lambda x, y: x < 126.9825, '개화–동작대교', wk('올림픽대로'), '1986년 5월 2일 행주대교 남단–동작대교 신설로 올림픽대로가 이어짐'),
  ('1971-08-15', lambda x, y: x < 127.013, '동작대교(국립묘지)–한남대교', wk('올림픽대로'), '처음에는 강변5로라는 이름의 강변도로'),
  ('1974', lambda x, y: x < 127.0579, '한남대교–영동대교', wk('올림픽대로'), '처음에는 강남2로. 날짜는 해만 확인'),
  ('1975-08-26', lambda x, y: x < 127.093, '영동대교–잠실대교', wk('올림픽대로'), '처음에는 강남2로'),
  ('1980-12-16', lambda x, y: x < 127.115, '잠실대교–광진교', wk('올림픽대로'), '처음에는 강남1로'),
  ('1979', lambda x, y: True, '광진교–하일(암사 분기점–하일)', wk('올림픽대로'), '암사–하일은 1979년(해만 확인). 광진교–암사 사이 처음 개통일은 찾지 못해 같은 해로 둠(추정)'),
 ],
 '강변북로': [
  ('1982-07', lambda x, y: x < 126.904, '행주대교 북단–양화대교 북단', wk('강변북로'), '1982년 7월은 성산대교 북단–행주대교 북단. 성산–양화 사이는 처음 개통일을 찾지 못해 같은 때로 둠(추정)'),
  ('1969-12-25', lambda x, y: x < 126.959, '양화대교 북단–한강대교 북단', wk('강변북로'), ''),
  ('1970-12-23', lambda x, y: x < 127.0306, '한강대교 북단–용비교', wk('강변북로'), ''),
  ('1972-07', lambda x, y: x < 127.093, '용비교–잠실대교 북단', wk('강변북로'), ''),
  ('1981-06-26', lambda x, y: x < 127.111, '잠실대교 북단–천호대교 북단', wk('강변북로'), ''),
  ('2003', lambda x, y: True, '천호대교 북단–구리', wk('강변북로'), '해만 확인'),
 ],
 '자유로': [
  ('1982-07', lambda x, y: x > 126.8169, '가양대교 북단–행주대교 북단', wk('강변북로'), '이 구간은 1982년 7월 강변북로(성산대교 북단–행주대교 북단)로 먼저 열림'),
  ('1994-09', lambda x, y: y >= 37.773, '오두산 통일전망대–임진각', wk('자유로'), '날짜는 달까지만 확인'),
  ('1992-08-15', lambda x, y: True, '행주대교–오두산 통일전망대', wk('자유로'), ''),
 ],
 '동부간선로': [
  ('1997-12-02', lambda x, y: y < 37.4911, '장지–수서', wk('동부간선도로'), ''),
  ('1998-12', lambda x, y: y < 37.5148, '수서–올림픽대로', wk('동부간선도로'), '날짜는 달까지만 확인'),
  ('1999-12-23', lambda x, y: y < 37.5459, '청담대교 구간', wk('동부간선도로'), '청담대교 개통일. 성수 쪽 접속부도 같은 때로 둠(추정)'),
  ('1992-12-18', lambda x, y: y < 37.5602, '용비교–군자교', wk('동부간선도로'), ''),
  ('1992-01-29', lambda x, y: y < 37.6382, '군자교–당현4교', wk('동부간선도로'), ''),
  ('1988', lambda x, y: y < 37.6653, '당현4교–상계주공 16단지', wk('동부간선도로'), '해만 확인. 상계주공 16단지 위치는 상계교 언저리로 잡음(추정)'),
  ('1994-07-31', lambda x, y: y < 37.685, '상계주공 16단지–수락지하차도', wk('동부간선도로'), '수락지하차도 위치는 지도에서 어림함(추정)'),
  ('2017-01-01', lambda x, y: True, '수락지하차도–상촌IC(의정부)', wk('동부간선도로'), '서울 방향. 의정부 방향은 2018-12-31'),
 ],
 '분당수서로': [
  ('2008-12-30', lambda x, y: y < 37.343, '풍덕천–구미동 연결도로', wk('분당수서로'), ''),
  ('1997-01-24', lambda x, y: y < 37.38, '수내사거리–금곡동(구미동)', wk('분당수서로'), ''),
  ('1994-09-02', lambda x, y: y < 37.477, '백현동–장지동', wk('분당수서로'), ''),
  ('1997-12-02', lambda x, y: y < 37.4911, '장지–수서', wk('분당수서로'), ''),
  ('1998-12', lambda x, y: y < 37.5148, '수서–올림픽대로', wk('분당수서로'), '날짜는 달까지만 확인'),
  ('1999-12-23', lambda x, y: True, '청담대교 구간', wk('분당수서로'), ''),
 ],
 '내부순환로': [
  ('1999-02-01', lambda x, y: x > 127.02 and y < 37.596, '월곡–성동 분기점', wk('내부순환로'), '이날 전 구간 개통'),
  ('1995-10-31', lambda x, y: x < 126.937, '성산대교 북단–홍제', wk('내부순환로'), ''),
  ('1998-12-15', lambda x, y: True, '홍제–월곡', wk('내부순환로'), ''),
 ],
 '북부간선도로': [
  ('2002-01-16', lambda x, y: x < 127.0924, '하월곡 분기점–묵동', wk('북부간선도로'), ''),
  ('1997-06', lambda x, y: x < 127.102, '묵동–신내', wk('북부간선도로'), '날짜는 달까지만 확인'),
  ('1993', lambda x, y: x < 127.117, '신내–서울시계', wk('북부간선도로'), '해만 확인. 서울시계 위치는 어림함'),
  ('1997-06', lambda x, y: True, '서울시계–구리', wk('북부간선도로'), '날짜는 달까지만 확인'),
 ],
 '서부간선도로': [('1988-09-14', lambda x, y: True, '시흥대교–목동교', wk('서부간선도로'), '')],
 '서부간선지하도로': [('2021-09-01', lambda x, y: True, '성산대교 남단–금천IC', wk('서부간선도로'), '')],
 '신월여의지하도로': [('2021-04-16', lambda x, y: True, '신월IC–여의대로·올림픽대로', S_SEOUL_SW, '')],
 '강남순환로': [
  ('2016-07-03', lambda x, y: x < 127.0201, '금천–선암', S_GN1, '1단계 13.8km'),
  ('2020-12-19', lambda x, y: True, '선암–구룡', S_GN2, '이날 19.7km 전 구간 개통. 양재대로 아래 지하차도들은 2014–2020년에 나뉘어 열림'),
 ],
 '우면산로': [('2004-01-06', lambda x, y: True, '과천–우면산터널', S_UM, '우면산터널 개통. 출처는 검색 결과 요약')],
 '제2자유로': [
  ('2010-07-31', lambda x, y: x >= 126.8361, '강매 동쪽 구간', wk('제2자유로'), '위키백과는 탑골–강매로 적음. 탑골 위치는 확인 못 함'),
  ('2011-07-13', lambda x, y: True, '강매–파주(전 구간 개통)', wk('제2자유로'), '강매–구룡은 2011-01-14에 먼저 열림'),
 ],
 '제3경인고속화도로': [
  ('2010-03-18', lambda x, y: x < 126.7522, '정왕–월곶 분기점', wk('제3경인고속화도로'), ''),
  ('2010-05-03', lambda x, y: True, '월곶 분기점–목감', wk('제3경인고속화도로'), ''),
 ],
 '김포한강로': [('2011-07-11', lambda x, y: True, '개화동–김포 운양동', wk('김포한강로'), '위키백과에는 전체 개통일 하나만 있음')],
 '신평화로': [
  ('2014-12-30', lambda x, y: y < 37.836, '장암–자금–회천', S_SP1, '국도 3호선 대체우회도로. 그 전 2010–2011년에 일부 임시 개통'),
  ('2014-10', lambda x, y: y < 37.905, '회천–상패', S_SP1, '날짜는 달까지만 확인'),
  ('2023-05-30', lambda x, y: True, '상패–청산(전 구간)', S_SP2, '동두천–소요산은 그 전에 먼저 열렸으나 날짜는 확인 못 함'),
 ],
 '성남이천로': [
  ('2015-04-23', lambda x, y: x < 127.2936, '대원 분기점(성남)–쌍동(광주 초월)', S_SI1, '국도 3호선 자동차전용도로'),
  ('2017-12', lambda x, y: True, '광주–이천', S_SI2, '2018-01-01 기사가 전면 개통을 알림. 날짜는 달까지만 확인'),
 ],
}
RN = {'서부간선지하도로': '서부간선지하도로', '분당수서로': '분당수서로(분당–수서 도시고속화도로)', '신평화로': '신평화로(국도 3호선 대체우회도로)', '성남이천로': '성남이천로(국도 3호선 자동차전용도로)'}

base = []; segs = defaultdict(list); hwx = defaultdict(list)
sec_used = defaultdict(set)
for ln in open(f'{RAW}/osm/art.geojsonseq'):
    ln = ln.strip('\x1e\n ')
    if not ln: continue
    f = json.loads(ln); p = f['properties']
    if f['geometry']['type'] != 'LineString': continue
    hw = p.get('highway'); nm = p.get('name', '')
    g = shape(f['geometry'])
    if nm == '경부고속도로':  # 한남–양재 서울 구간(OSM trunk)
        c = g.centroid
        hwx['1969-12-26' if c.y >= 37.523 else '1968-12-21'].append(g); continue
    if nm not in R and p.get('motorroad') == 'yes' and p.get('alt_name') in R: nm = p['alt_name']
    if nm in R:
        if nm in R:
            c = g.centroid
            for i, (d0, fn, lab, src, note) in enumerate(R[nm]):
                if fn(c.x, c.y):
                    segs[(nm, d0, i)].append(g); sec_used[nm].add(i); break
            continue
    if hw in ('trunk', 'primary'):
        base.append(g)

def merged(gs, tol):
    m = linemerge(gs); ls = [m] if m.geom_type == 'LineString' else list(m.geoms)
    return [rnd(l.simplify(tol).coords) for l in ls if l.length > 0.0004]

out = {'seg': [], 'base': [], 'sec': {}, 'rn': {}, 'hwx': []}
for (nm, d0, i), gs in segs.items():
    for p in merged(gs, 0.00015): out['seg'].append({'r': nm, 'd': d0, 'p': p})
for nm, rows in R.items():
    out['sec'][nm] = [[d0, lab, src[0], src[1], note] for i, (d0, fn, lab, src, note) in enumerate(rows) if i in sec_used[nm]]
    out['rn'][nm] = RN.get(nm, nm)
# 바탕: 이름별로 합친 뒤 줄임
bl = merged(base, 0.0003)
out['base'] = bl
for d0, gs in hwx.items():
    for p in merged(gs, 0.00015): out['hwx'].append({'r': '경부', 'd': d0, 'p': p})
json.dump(out, open(f'{SUDO2}/art.json', 'w'), ensure_ascii=False, separators=(',', ':'))
print('seg', len(out['seg']), sum(len(o['p']) for o in out['seg']), 'base', len(bl), sum(len(p) for p in bl), 'hwx', len(out['hwx']))
for nm in R: print(nm, [r[0] for r in out['sec'][nm]], 'unused', [R[nm][i][0] for i in range(len(R[nm])) if i not in sec_used[nm]])
import os; print(os.path.getsize(f'{SUDO2}/art.json'))
