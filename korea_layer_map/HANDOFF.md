# 전국 연대지도 — HANDOFF

2026-11-27 기준(철도 선형 잇기 1단계 끝). 이 폴더를 맡은 채팅은 이 문서를 먼저 읽고, 자세한 기록은 `docs/`에서 필요한 절만 찾아 읽는다.

## 원본과 읽는 순서

- 원본: 저장소 `rosewein/rosewein.github.com`의 작업 브랜치 `korea-layer-map`, 폴더 `korea_layer_map/`(2026-11-27 이지가 정함). master에는 아직 합치지 않았다. master에 올리기 전에는 무엇을 올리는지 이지에게 한 번 더 확인한다.
- 이 작업은 claude.ai 「서울 도시 연대지도」 프로젝트의 한 채팅에서 시작했다. 거기서 쓴 프로젝트 문서 세 개를 `docs/`로 옮겼고(2026-11-27 사본), 이 뒤로는 저장소의 `docs/`와 이 문서를 고친다. 새 프로젝트에서는 그 프로젝트의 문서를 읽을 수 없다.
- 읽는 순서: 이 문서 → 할 일에 맞는 `docs/` 문서의 해당 절 → 필요하면 `README.md`(출처·이용 조건).

## 지금 상태(2026-11-27)

| 갈래 | 상태 | 자세한 기록 |
|---|---|---|
| 고속도로 | 끝. 재정 구간표 131행, 민자 개통일 24번, 재정+민자 전국 선형(OSM 선에 날짜), 노선마다 한 줄로 줄인 단순 선형 | `docs/도로.md` |
| 표준노드링크 판별 비교 | 러프 시안 아티팩트 「표준노드링크 판별 비교」(<https://claude.ai/artifact/ToNP7evBzkBRPCcVAktX8d>, 이지만 볼 수 있음). 페이지 소스는 `src/nodelink/site/` | `docs/도로.md` 「표준노드링크 판별 비교」 |
| 철도 | 국철 340행·도시철도 79행 구간 사건표. 선형 잇기 1단계(역 이름 → OSM 역·손 자리 대응) 끝: 모든 구간의 끝·경유 역이 자리를 얻음(손 자리 64점은 추정). 2단계(그래프·경로 배정)는 아직 | `docs/철도.md` 「선형 잇기 1단계」 |
| 공단·택지 | 자료 후보만 적음 | `docs/자료후보.md` 「지역개발(공단·택지)」 |
| 지도 화면 | 없음 | — |

## 다음 할 일: 철도 선형 잇기

이지가 새 프로젝트에서 이 일부터 하자고 했다(2026-11-27). 아래는 고속도로 때 쓴 방식을 철도에 맞게 고친 계획이다. 정해진 기법이 아니라 이 작업에서 짠 방식이다.

입력:
- `data/rail/국철_구간사건표_20261127.csv`, `data/rail/도시철도_구간사건표_20261127.csv`
- OSM 철도 추출: `src/rail/osm_rail.py`로 남쪽·북쪽 pbf에서 `work/rail/osm_rail_s.json`, `osm_rail_n.json`을 만든다(2026-11-27 고친 스크립트로 다시 뽑은 결과: 남쪽 26,884선·1,772역·474관계, 북쪽 13,596선·865역·179관계. 역에는 화물역·신호장(kind=service)과 폐역(kind=hist)도 들어 있다). 선마다 노드 id와 railway·usage·service·폐선 태그(abandoned:railway 등)·start_date 같은 태그가 들어 있다.
- 고속도로 때 쓴 그래프·끝점·최단 경로 코드: `src/road/graph.py`, `src/road/assign.py`(노드 그래프, 끝점 이름 찾기, scipy dijkstra). 그대로 쓰기보다 참고한다.

진행(2026-11-27): 1단계를 끝냈다. 이지가 정한 것(제안 대응은 묶어 원문 확인, 옛 역·지금 역은 옮긴 날로, 폐역은 폐선 위 자리와 손 자리로 반드시 지도에, 역이 아닌 끝은 인입선 끝처럼, 금강산선·북쪽 동해북부선은 보여 주었다 없앰)을 `src/rail/station_alias.py`에 넣었다. 국철 336줄·도시철도 79줄의 모든 점이 OSM 역이나 손 자리에 이어졌다. 손 자리 가운데 소재지 근거 없이 역 이름과 같은 지명 점에 둔 10역은 다듬어야 한다(`docs/철도.md` 「확인 못 한 것」). 다음은 2단계(그래프·경로 배정)다.

순서(계획):
1. 역 이름 잇기: 구간 칸의 양 끝을 OSM 역(railway=station·halt) 이름에 잇는다. 옛 이름 대응표를 둔다(예: 경성·남대문 → 서울, 이리 → 익산, 송정리 → 광주송정). 북쪽 역 이름은 OSM에서 조선어 표기일 수 있다.
2. 그래프: railway=rail·narrow_gauge·abandoned·disused 같은 선로로 만든다. 측선·차량기지 같은 service 선은 뺀다.
3. 경로 배정: 개통·이설 줄을 늦은 것부터 처리해서, 나중에 놓인 새 선로가 먼저 선을 차지하게 한다. 앞 시기 줄은 이미 차지된 선에 벌점을 받아 폐선 쪽 옛 선로로 돌게 한다.
4. 선마다 열린 날과 닫힌 날을 붙인다. 이설은 옛 경로를 닫고, 폐지는 그 구간을 닫는다. 복선·전철화는 그 선의 속성(해)으로 붙인다.
5. 북쪽 선은 1945년까지만 보이게 한다.
6. 검사: 고속도로 때처럼 연말 상태 그림을 몇 해 그려 구간 사건표와 맞는지 보고, 구간 연장과 잰 길이를 견준다.

미리 알아 둘 것:
- 날짜가 연도만이거나 연월만인 줄이 있다(1906, 1943, 1994, 2015, 2021 등).
- OSM에 선이 없는 옛 폐선이 있을 수 있다. 그때는 역 사이를 직선으로 이을지, HGIS 철도망·옛 지형도에서 선을 구할지 이지와 정한다.
- 확인 못 한 날짜와 자료끼리 다른 날짜는 `docs/철도.md` 「자료끼리 날짜가 다른 곳」「확인 못 한 것」에 있다.

## 그다음 할 일(제안, 정하지 않음)

- 공단·택지 레이어(자료 후보는 `docs/자료후보.md`).
- 지도 화면. 서울·수도권 지도와 같은 구조로 할지, 전국 화면에는 굵은 것(간선철도·고속도로·시군구 경계·택지·산업단지)만 둘지(`docs/자료후보.md` 「채팅에서 Claude가 제안했지만 정하지 않은 것」).

## 원자료 자리

모두 이지 컴퓨터의 다운로드 폴더(`C:\Users\ryura\Downloads`)에 있다. 저장소에는 넣지 않는다.

| 파일 | 쓰는 곳 |
|---|---|
| `south-korea-261124.osm.pbf`, `north-korea-261124.osm.pbf`(Geofabrik 2026-11-24) | 고속도로 선형(남쪽), 철도 선로(남·북) |
| 표준노드링크 19판 zip(`[20081105버전]전국표준노드링크.zip`부터 `[2026-11-11]NODELINKDATA.zip`까지, 1.9GB 안팎. 판과 파일 이름 대응은 `src/nodelink/process.py`의 `ED`) | 판별 비교, 고속도로 개통일 검사 |
| `한국도로공사_고속도로 건설공사_20260729.csv`(cp949) | 재정 구간표 대조 |
| `R26090541.pdf`(민자 운영평가), `R0011254.HWP`(인천공항고속도로 개통) | 민자 개통일 |
| `국가철도공단_철도 통합 연표_20260303.csv` | 국철 구간 사건표 |
| `50. 한국철도의 역사(철도정책과).hwp`, `정책_Q`(확장자 없는 hwp), `광역철도_도시철도_운영 현황.egg` | 국철·도시철도 구간 사건표 |
| `철도망_라인정보_공간데이터.zip`(HGIS) | 옛 선로(경인선·경부선 서울 구간만 시기별) |

받는 법 가운데 이 작업에 필요한 것은 이 문서 끝 「자료 받기 메모」에 옮겨 두었다(원래 기록은 「서울 도시 연대지도」 프로젝트의 「자료 받기 메모」).

## 새 작업 공간에서 시작하는 법

1. 저장소 받기: `git clone --depth 1 -b korea-layer-map https://github.com/rosewein/rosewein.github.com`
2. 패키지: `pip install --break-system-packages osmium shapely scipy pyproj geopandas pyogrio matplotlib olefile lxml pyhwp`. 검사 그림은 Noto Sans CJK 글꼴을 찾아 쓴다. 판별 비교 페이지 화면 찍기(`src/nodelink/shot.py`)는 playwright와 `work/vendor/`에 npm으로 받은 d3가 필요하다.
3. 원자료: 데스크톱 앱에 연결한 다운로드 폴더에서 필요한 파일만 작업 공간으로 옮긴다. 옮긴 자리(`/mnt/user-data/uploads/Downloads`)가 `KLM_RAW`의 기본값이다. 다른 자리면 `export KLM_RAW=…`.
4. 중간 파일은 `korea_layer_map/work/`(기본값, git에 안 올림)에 쌓인다. 다른 자리면 `export KLM_WORK=…`.
5. 고속도로 선형을 다시 만들 필요가 없으면 `data/road/전국고속도로_선형_20261127.zip`을 풀어 쓴다.

## 스크립트 자리와 돌리는 순서

모두 `korea_layer_map/`에서 `python3 src/…`로 돌린다. 경로는 `src/paths.py`의 `_RAW`(원자료)·`_D`(data/)·`_W`(work/)로 받는다.

고속도로:
1. `src/road/osm_ex.py <RAW>/south-korea-261124.osm.pbf work/road/osm_mw2.json`: 고속도로 본선 선(노드 id 포함)과 나들목·분기점.
2. `src/road/osm_ops.py <RAW>/south-korea-261124.osm.pbf work/road/osm_mw.json`: 운영자·개통일 태그와 노선 관계(민자 대조용).
3. `src/nodelink/process.py`: 표준노드링크 19판을 차례로 풀어 등급별 길이 요약, 판마다 50m 격자, 앞 판에 없던 길을 `work/nodelink/`에 만든다(오래 걸림. 인자로 판 날짜를 주면 그 판부터 이어서 함).
4. `src/road/way_first.py work/road/osm_mw2.json work/nodelink work/road/way_first.json`, `src/road/first_ed.py work/road/osm_mw.json work/nodelink work/road/first_ed.json`: 선마다·민자 노선마다 처음 실린 판.
5. `src/road/make_table.py`: 재정 구간표 → `data/road/`. 표 내용은 스크립트 안에 손으로 적혀 있다.
6. 민자 개통일 CSV(`data/road/민자고속도로_개통일_20261127.csv`)는 손으로 고쳐 온 표라 스크립트가 없다. 파일을 직접 고친다.
7. `src/road/run_jaejeong.py`(assign.py → build.py를 한 번에): 재정 선형 → `work/road/재정고속도로_선형_20261127.geojson`. 대응표는 `src/road/mapping.py`, 나들목 이름 다듬기는 `names.py`.
8. `src/road/check.py`(표준노드링크 판과 견줌), `src/road/merge.py`(민자 합침 → `work/road/전국고속도로_선형_20261127.geojson`, `cum_len.json`), `src/road/simplify2.py`(→ `data/road/전국고속도로_단순_20261127.geojson`).
9. 검사 그림: `src/road/plot.py`, `plot2.py`, `plot3.py` → `work/checks/`. 민자 구간별 길이 대조는 `src/road/segs.py`. 한국도로공사 CSV 살펴보기는 `src/road/hw_csv_check.py`.

표준노드링크 판별 비교 페이지: `process.py` → `build_data.py`(→ `site/data.json`, `site/net_*.png`) → `crop.py` → `topnames.py`(판마다 새로 실린 큰 도로 이름 확인용). 페이지는 d3(cdnjs)와 IBM Plex Sans KR(Google Fonts)을 불러 쓴다.

철도:
1. `src/rail/osm_rail.py <RAW>/south-korea-261124.osm.pbf work/rail/osm_rail_s.json`, 북쪽도 같게 `osm_rail_n.json`.
2. `src/rail/parse_yeonpyo.py`: 철도 통합 연표에서 개통·개량·폐지 문장을 골라 `work/rail/yp_events.json`(394건).
3. `src/rail/make_rail_table.py`: 국철 구간 사건표 → `data/rail/`. 줄은 스크립트 안에 손으로 적혀 있고, 국토부 한글 파일과 맞춰 고친 내역은 `molit_patch.py`(make_rail_table.py가 읽어 씀)에 따로 있다.
4. `src/rail/make_urban_table.py`: 도시철도 구간 사건표 → `data/rail/`.
5. `src/rail/station_match.py`: 구간 사건표 양 끝·경유 역을 OSM 역·손 자리에 잇는다(→ `work/rail/station_match.json`, `station_manual_points.json`, `yp_renames.json`). 대응표·옮긴 날·손 자리·끝 처리는 `station_alias.py`(손으로 적는 표). 연표 CSV(RAW)를 읽는다. `src/rail/station_report.py` → `work/rail/station_match_report.md`.
6. 국토부 파일 여는 도구: `unegg.py <egg> <폴더>`(알집 EGG 풀기, 암호 없는 파일·deflate 방식만 시험함), `hwp5html --output <폴더> <hwp>` 뒤 `xhtml_tables.py <폴더>/index.xhtml`(표 칸 읽기), `hwp5`가 오류를 내는 파일은 `hwp_rawtext.py <hwp>`.

옮길 때 확인한 것(2026-11-27): 경로를 `paths.py`로 바꾼 뒤 다시 돌려 옮기기 전 결과와 바이트까지 같게 나온 것은 make_table, make_rail_table, make_urban_table, parse_yeonpyo, hw_csv_check, segs, run_jaejeong(재정 선형), merge(전국 선형·cum_len), simplify2(단순 선형)다. check.py와 plot3.py는 돌아가는 것만 봤다. osm_ex·osm_ops·osm_rail, way_first·first_ed, 표준노드링크 스크립트 전부, plot.py·plot2.py는 경로만 바꾸고 다시 돌려 보지 않았다.

## 정할 것(이지)

0. 철도 손 자리 다듬기: 지명 점에 둔 폐역 자리를 무엇으로 고칠지(옛 지형도·역 터 표지 등), 금강산선 역 거리를 어느 자료로 할지(`docs/철도.md` 「확인 못 한 것」).
1. 지도 이름(작업 이름 「전국 연대지도」).
2. master에 합쳐 공개하는 때. 폴더 이름대로면 주소는 `rosewein.github.io/korea_layer_map/`이 된다.
3. 버전 매기는 법.
4. 표준노드링크 판별 비교 아티팩트를 계속 쓸지.

## 확인 못 한 것

갈래마다 `docs/` 문서의 「확인 못 한 것」 절에 있다. 철도는 `docs/철도.md`, 고속도로는 `docs/도로.md`, 공단·택지와 1945–1955년 경계 등은 `docs/자료후보.md`.

## 자료 받기 메모

「서울 도시 연대지도」 프로젝트의 「자료 받기 메모」에서 이 작업에 쓰는 것만 옮겼다(2026-11-27). 새로 알게 된 받는 법은 여기에 한 줄씩 더한다.

- 작업 공간에서는 공공데이터포털(`data.go.kr`, `apis.data.go.kr`), 국가교통정보센터(`its.go.kr`), V-World, 국토교통부 누리집(`molit.go.kr`, robots.txt로 웹 가져오기도 막힘)에 바로 접속하지 못한다. GitHub·npm·pip은 된다. 파일은 이지의 크롬(Claude in Chrome)으로 받아, 데스크톱 앱에 연결한 다운로드 폴더에서 작업 공간으로 옮긴다.
- 작업 공간에서 이지 컴퓨터로 되돌려 쓰는 파일은 한 파일에 25MB까지다.
- 공공데이터포털 파일데이터는 크롬의 그 페이지에서 `/tcs/dss/selectFileDataDownload.do` → `/cmm/cmm/check-limit.json` → `/cmm/cmm/fileDownload.do`를 차례로 불러, 내려받지 않고 메모리에서 읽을 수도 있다.
- 표준노드링크 자료실(`its.go.kr/nodelink/nodelinkRef`)은 조회 기간을 한 해까지만 받고, 두 해를 넣으면 알림창이 떠서 크롬 탭이 멈춘다. 받는 주소는 `/opendata/nodelinkFileSDownload/DF_…/n` 꼴이다. 큰 판은 받다가 멈추는 일이 있어 크기를 보고 다시 받았다. 크롬이 `.tmp` 이름으로 남긴 파일도 끝까지 받아져 있었다.
- 국토교통부 정책자료·정책Q&A 첨부 파일: 「정책_Q」는 확장자가 빠졌지만 한글(hwp) 파일이었고, 「광역철도_도시철도_운영 현황」은 알집 형식(`.egg`)이었다. EGG는 `src/rail/unegg.py`로 풀었다. 한글 파일의 표는 `hwp5txt`로는 「<표>」로만 나오므로 `hwp5html`로 바꿔 읽는다.
- 한국어 위키백과 노선 문서는 작업 공간의 웹 가져오기로 읽힌다(주소에 한글 제목을 그대로 넣음). 「중앙선_(한국철도공사)」, 「부산–김해_경전철」, 「우이신설선」, 「신림선」으로 넣은 주소는 찾지 못함(url_not_found)으로 나왔다. 실제 문서 제목이 달랐는지는 확인하지 못했다.
- 국가기록원 「기록으로 보는 한국」(`theme.archives.go.kr`)과 서울시 「내 손안에 서울」(`mediahub.seoul.go.kr`)은 작업 공간의 웹 가져오기로 읽힌다.
- 작업 공간에서 git 태그는 올리지 못한다. 태그는 GitHub 화면의 Releases에서 만든다.
- 웹 가져오기는 한국어 위키백과(ko.wikipedia.org)는 주소를 바로 넣어도 열리지만, 일본어 위키백과는 승인 요청이 떴다(2026-11-27). 영어 위키백과는 검색 결과에 나온 주소로 열었다. 북한 역의 옛 이름은 영어 위키백과 노선 문서 표의 「Former Name」 칸에 잘 정리돼 있다.
