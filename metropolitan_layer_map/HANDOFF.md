# 수도권 도시 연대지도 — 인수인계

2026-11-27 기준(v1.0, 공개 준비). 이 지도를 이어서 작업하는 채팅은 이 문서를 먼저 읽고, 필요한 절만 `docs/구상.md`·`docs/버스.md`에서 찾아 본다. 지도 소개·출처 표·변경 기록은 `README.md`에 있다.

## 지금 상태

- 저장소 `rosewein/rosewein.github.com`의 작업 브랜치 `metropolitan-layer-map`, 폴더 `metropolitan_layer_map/`. v1.0을 이 브랜치에 올렸고, master에는 이지가 확인한 뒤 합친다.
- 공개: master에 합치면 GitHub Pages로 <https://rosewein.github.io/metropolitan_layer_map/>에 몇 분 안에 반영된다. master에 올리기 전에는 무엇을 올리는지 이지에게 한 번 더 확인한다.
- 같은 저장소에서 「서울 도시 연대지도」 v2.0 통합이 `v2-integration` 브랜치에서 진행 중이다(2026-11-27 14:19 `66d0a35`까지 확인, master에는 아직 안 들어옴). 이 폴더만 더하는 것이라 파일이 부딪치지는 않지만, master에 합치는 때는 이지와 맞춘다.
- 처음 만든 곳은 claude.ai 아티팩트(https://claude.ai/artifact/KYtRcKmEQWUzJBxEYaL9Mp, 2026-11-27 판 `1795754017-f029`, 공개 링크로 공유됨)이다. 아티팩트 제목은 아직 「수도권 도시 연대지도 시안」이다. 저장소로 옮긴 뒤로는 저장소가 원본이고, 아티팩트를 함께 고칠지는 이지가 정한다.
- 페이지 제목·머리글은 「수도권 도시 연대지도」(2026-11-27 이지가 정함). 「시안」 표기는 페이지·`data.json`·README·docs·스크립트 주석에서 모두 뺐고, `docs/구상.md`의 아티팩트 제목 한 곳에만 남아 있다.

## 이 지도에서 따르는 것

- 지도 이름은 「수도권 도시 연대지도」(2026-11-27 이지가 정함), 폴더와 주소는 `metropolitan_layer_map`.
- 보고는 한국어로, 사실은 원문으로 확인하며 쓰고 '확인한 것 / 추정 / 확인 못 한 것'으로 나눈다.
- 레이어마다 한 색상의 밝기 단계(무지개 금지), 밝은 화면과 어두운 화면 색을 모두 정의한다.
- 보는 사람이 느끼는 게 바뀌는 것(레이어 순서·색·배치)은 고치기 전에 시안을 먼저 보여 준다.
- 새 자료를 넣으면 `README.md` 출처 표와 지도 아래 「지금 자료로 닿는 범위」 표·출처 문단에 이용 조건과 함께 적는다.
- GitHub에 올리는 것은 이지가 하자고 할 때만 한다.
- 버전(2026-11-27 이지가 정함): 공개한 판이 v1.0. 레이어를 더하거나 화면이 크게 바뀌면 둘째 자리(v1.1), 화면·기술만 고치면 셋째 자리(v1.0.1)를 올린다. 「서울 도시 연대지도」와 같은 규칙이다. 버전은 `index.html` 출처 문단 아래 줄(「v1.0 · 2026-11-27 · 변경 기록」)에 손으로 적고, README 「변경 기록」 표에 버전·날짜·커밋·바뀐 점을 한 줄 적는다.

## 새 작업 공간에서 시작하는 법

1. 저장소를 받고 `metropolitan-layer-map` 브랜치로 옮긴다. 저장소가 크므로 `git clone --filter=blob:none --no-checkout --branch metropolitan-layer-map` 뒤 `git sparse-checkout set metropolitan_layer_map`으로 이 폴더만 꺼내면 된다.
2. 지도만 고칠 때는 `index.html`을 바로 고친다. 화면 확인은 이 폴더에서 `python3 -m http.server 8765`를 띄우고 Playwright로 찍는다. 작업 공간은 cdnjs와 구글 글꼴에 닿지 못하므로 npm으로 받은 d3(`npm i d3@7.8.5`, `d3/dist/d3.min.js`)를 `**/d3.min.js` 요청에 가로채 넣고, 글꼴 요청은 막아 둔다(대체 글꼴로 찍힘). 밝은·어두운 화면과 휴대폰 폭(390px)을 모두 찍는다.
3. 자료를 다시 만들 때는 `sh src/setup_workdirs.sh`로 스크립트를 `/home/claude/sudo`·`/home/claude/sudo2`에 복사한다. 스크립트가 이 절대 경로를 그대로 쓰기 때문이다(경로를 한 파일로 모으는 정리는 아직 안 함, 「다음 할 일」). 다 고친 뒤 `sh src/collect_back.sh`로 고친 스크립트와 페이지를 저장소로 되가져온다. 페이지에 손으로 고친 것(v1.0의 첫 문단·출처·터미널 점 등)은 스크립트로 다시 만들지 않으므로, 자료만 바꿀 때 `index.html`을 덮어쓰지 않게 주의한다.
4. 원자료는 저장소에 없다. 이지의 다운로드 폴더(데스크톱 앱 연결)에서 아래 자리로 옮긴다.
   - `/home/claude/raw/hgis_adm/adm.gpkg`(HGIS 1910–1945), `/home/claude/raw/hgis_5575/`(HGIS 1955–1975), `/home/claude/raw/hgis_rail/rail.gpkg`(HGIS 철도망)
   - `/home/claude/ext/vuski_admdongkor/`, `/home/claude/ext/kimmdr2_metroscope/`(GitHub에서 받음)
   - `/home/claude/raw/ne/ne_10m_admin_0_countries.geojson`(Natural Earth)
   - `/home/claude/raw/osm/*.geojsonseq`: Geofabrik `south-korea-261124.osm.pbf`·`north-korea-261124.osm.pbf`에서 osmium-tool로 뽑은 것. 뽑은 범위와 태그는 `docs/구상.md` 각 절에 있고, 명령 자체는 스크립트로 남기지 않았다.
   - `/home/claude/raw/jigu/`(택지정보시스템 zip 넷)
   - `/mnt/user-data/uploads/Downloads/`의 경기 BMS·인천 BIS·국토교통부 전국 버스정류장 CSV(cp949)
   - 서울 안 국철·조선 후기 대로는 같은 저장소 `seoul-layer-map/data/`(`rail.json`, `metro.json`, `metro_dates.json`, `joseon.json`)를 `/home/claude/repo/` 아래에 받아 읽는다.
5. 큰 중간 파일(버스 도로 그래프 `busgraph.npz` 41MB, 경로 `paths_*.pkl`, HGIS 추출 `hgis.pkl`, 연도별 경계 `gj/`)은 저장소에 넣지 않았다. 버스 경로를 다시 이으려면 `busgraph.py`부터 다시 돌린다(약 7분).

## 스크립트 순서

- 경계·전철: `sudo/build_data.py` → `sudo2/build2.py` → `build_sea.py` → `build_land0.py` → `build_pre1910.py` → `build_water.py` → `build_jigu.py` → `build_tidal.py` → `build_hw.py` → `build_art.py` → `build_hw_page.py` → `build_joseon.py` → `merge_joseon.py`. 역 개통일은 `sudo/sudo_dates.py`, 고속도로 구간 개통일은 `sudo2/hw_segments.py`.
- 광역버스: `sudo2/bus/busgraph.py` → `pick_routes.py`·`pick_ic_seoul.py` → `run_routes.py`·`run_extra.py` → `route_years_bus.py` → `namu/decide_68.py`·`apply_68.py`(→ `years_bus.json`) → 없어진 노선·2004년 전 노선 `closed/build_closed.py`(입력 `closed/new_closed.json`, `pre2004/pre2004_entries.json`) → `agg_bus.py`(→ page `data.json`의 `bus`).
- 시외버스: `bus/siwoe/siwoe_entries.json` → `closed/build_closed.py siwoe_entries.json siwoe` → `siwoe/agg_siwoe.py`(→ `sw`).
- 터미널: `bus/siwoe/terminals.py`(→ `tm`). 방면별 평균 방위 `tm[].dr[].b`는 v1.0부터 페이지에서 쓰지 않는다.
- `patch_page_*.py`는 페이지에 레이어를 처음 넣을 때 한 번만 돌린 것이라 다시 돌리지 않는다(`patch_page_tm.py`가 넣은 화살표는 v1.0에서 뺐다).

## 조사 도구 메모

- 조선일보 「조선 뉴스 라이브러리 100」: 이지의 크롬(Claude in Chrome)에서 `https://newslibrary.chosun.com/`을 열고 같은 사이트 안에서 `/priv/data/jsonData.php?case_num=1&query=…&field=&ds=1960.01.01&de=1999.12.31&type=article&wrt=&sort=2&page=N&size=100`을 fetch하면 본문(`body.archaic_hangul`)까지 온다. 기간을 좁게 주면 0건이 되는 일이 있어 넓게 받고 브라우저 안에서 거른다. 검색어 여러 개는 모두 든 기사만 나온다. 물음표·등호가 든 주소를 그대로 출력하면 도구가 막는다.
- 네이버 뉴스 라이브러리는 크롬 안전 제한으로 열리지 않았다.
- 나무위키: 크롬에서 열고, 문서를 옮길 때 `history.pushState` 뒤 `PopStateEvent`를 보내고 제목(h1)이 바뀔 때까지 기다린다. `/raw/` 주소는 확인 페이지가 떠서 쓰지 못했다.

## v1.0 정리(2026-11-27)

한 일:
- 탭 제목·머리글·첫 문단·연천군 보정 메모(`data.json` 두 곳과 `src/sudo2/build2.py` 44행)·CSS 주석·스크립트 주석 두 곳·README·docs에서 「시안」을 뺐다.
- 첫 문단: 끊겨 있던 마지막 문장(1899–1910·1945–1955 보정)을 마무리하고, 동사가 빠진 광역버스 문장을 고치고, 레이어 목록에 조선 후기 대로·광역버스·시외버스를 넣고, 시외버스·터미널 문장을 더했다. 범례 마지막 줄에 마침표.
- 출처 문단: 1899–1910 보정(칙령 제49호 위키문헌 전사본, 한국민족문화대백과사전), 시화 간석지(택지정보시스템 반월특수지역 경계·OSM 수면·한국수자원공사 시화지구 누리집), 시외버스 지명 자리(국토교통부 전국 버스정류장)·경로(OSM)를 더했다. README 출처 표에도 1945–1955 보정 날짜 출처와 한국수자원공사 줄을 더했다.
- 적용 범위 표 터미널 줄의 「비는 곳」에 터미널 자리를 동네 이름으로 어림했다는 것을 적었다.
- 시외버스 터미널 방면 화살표를 뺐다(이유는 `docs/버스.md` 터미널 절). 점만 그리고, 누른 점은 1.8배로 키운다. 전철 선 위·역 점 아래에 보이지 않는 누르는 원(`gTmHit`)을 두어 선이 지나가는 점(동마장·서울역)도 눌린다.
- 출처 문단 아래에 「v1.0 · 2026-11-27 · 변경 기록」 줄, README 「변경 기록」을 서울 지도처럼 표로 바꾸고 공개 전 18판을 따로 묶었다.
- 화면 확인: 1280px 밝은·어두운 화면, 390px 휴대폰 폭에서 머리 부분·출처 끝·1950년 연천군 정보창·1972년 전체·1980년 서울 확대와 동마장 터미널 누르기를 찍어 봤고, 페이지 오류는 없었다.

확인 못 한 것:
- 이번에 첫 문단과 출처 문단에 더한 사실은 적용 범위 표와 `docs/`에 이미 적혀 있던 것을 옮긴 것이고, 원문을 다시 열어 대조하지는 않았다.
- 화면은 대체 글꼴로 찍었다(작업 공간에서 구글 글꼴이 막힘). 실제 글꼴로는 이지 화면에서 확인한다.
- 「변경 기록」 링크(`master/metropolitan_layer_map#변경-기록`)는 master에 합친 뒤에만 열린다.

## 정할 것(이지)

1. master에 합쳐 공개하는 때(v1.0을 브랜치에 올림, 이지 확인 기다림).
2. claude.ai 아티팩트를 계속 함께 고칠지, 저장소만 고칠지. 아티팩트 제목의 「시안」을 뺄지.
3. 갈래를 나눠 작업할 때 버전 번호를 붙이는 때. 서울 지도에서는 브랜치에서 먼저 적은 번호를 master가 먼저 써서 합칠 때 바꾼 일이 두 번 있었다. 브랜치에서는 번호 없이 '다음 판'으로 적고 master에 합칠 때 붙이는 안을 제안해 두었다(정하지 않음).
4. 터미널 방면을 정보창 안에 작은 나침반 그림(아홉 방면 막대)으로 보일지(v1.1 후보).

## 다음 할 일

- README 「변경 기록」 v1.0 줄의 커밋 칸(master에 합칠 때 커밋이 바뀌면 고침).
- 스크립트 경로를 한 파일(예: `src/paths.py`, 환경변수로 원자료 자리를 받음)로 모으기.
- 시외버스 터미널: 신촌·불광동·상봉의 문 연 날·닫은 날, 1985-08 구의 102개 노선 기사 다시 확인, 동아·경향 등 다른 신문, 2000년 뒤.
- 시외버스 노선: 노선 면허·고시 원문, 빠진 노선(부천, 인천–신촌 1998 등).
- 광역버스: 생긴 해를 못 찾은 13개, 2004년 뒤 서울 9xxx 번호가 끝난 해.
- 그 밖에 `docs/구상.md` 「확인 못 한 것」(1974년 전 국철 서울 밖 구간, 간선도로 날짜, 옛 물길 등).
- 공개 전 점검: `data.json`이 6.9MB라 휴대폰에서 처음 열 때 받는 양을 확인한다.
