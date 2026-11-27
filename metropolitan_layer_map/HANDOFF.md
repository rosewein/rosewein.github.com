# 수도권 도시 연대지도 — 인수인계

2026-11-27 기준(시안 열여덟 번째 판). 이 지도를 이어서 작업하는 채팅은 이 문서를 먼저 읽고, 필요한 절만 `docs/구상.md`·`docs/버스.md`에서 찾아 본다. 지도 소개·출처 표·변경 기록은 `README.md`에 있다.

## 지금 상태

- 저장소 `rosewein/rosewein.github.com`의 작업 브랜치 `metropolitan-layer-map`, 폴더 `metropolitan_layer_map/`. master에는 아직 없다(공개 전).
- 공개: 이지가 화면을 더 확인한 뒤 master에 합친다. 합치면 GitHub Pages로 <https://rosewein.github.io/metropolitan_layer_map/>에 몇 분 안에 반영된다. master에 올리기 전에는 무엇을 올리는지 이지에게 한 번 더 확인한다.
- 같은 저장소 master에서는 「서울 도시 연대지도」 v2.0 통합이 진행 중이다(2026-11-27). 이 폴더만 더하는 것이라 파일이 부딪치지는 않지만, master에 합치는 때는 이지와 맞춘다.
- 처음 만든 곳은 claude.ai 아티팩트 「수도권 도시 연대지도 시안」(https://claude.ai/artifact/KYtRcKmEQWUzJBxEYaL9Mp, 2026-11-27 판 `1795754017-f029`, 공개 링크로 공유됨)이다. 저장소로 옮긴 뒤로는 저장소가 원본이다. 아티팩트를 함께 고칠지는 이지가 정한다.
- 페이지 제목은 아직 「수도권 도시 연대지도 시안」, 머리글은 「수도권 도시 연대지도 — 자료 시안」이다. 공개할 때 「시안」을 뺄지 이지와 정한다.

## 이 지도에서 따르는 것

- 지도 이름은 「수도권 도시 연대지도」(2026-11-27 이지가 정함), 폴더와 주소는 `metropolitan_layer_map`.
- 보고는 한국어로, 사실은 원문으로 확인하며 쓰고 '확인한 것 / 추정 / 확인 못 한 것'으로 나눈다.
- 레이어마다 한 색상의 밝기 단계(무지개 금지), 밝은 화면과 어두운 화면 색을 모두 정의한다.
- 보는 사람이 느끼는 게 바뀌는 것(레이어 순서·색·배치)은 고치기 전에 시안을 먼저 보여 준다.
- 새 자료를 넣으면 `README.md` 출처 표와 지도 아래 「지금 자료로 닿는 범위」 표·출처 문단에 이용 조건과 함께 적는다.
- GitHub에 올리는 것은 이지가 하자고 할 때만 한다.
- 버전 매기는 법은 아직 정하지 않았다(「서울 도시 연대지도」처럼 `vX.Y`를 둘지). 그때까지는 `README.md` 「변경 기록」에 날짜와 한 일을 적는다.

## 새 작업 공간에서 시작하는 법

1. 저장소를 받고 `metropolitan-layer-map` 브랜치로 옮긴다. 저장소가 크므로 `git clone --depth 1` 뒤 `git sparse-checkout set metropolitan_layer_map`으로 이 폴더만 꺼내면 된다.
2. 지도만 고칠 때는 `index.html`을 바로 고친다. 화면 확인은 이 폴더에서 `python3 -m http.server 8765`를 띄우고 Playwright로 찍는다. 작업 공간은 cdnjs에 닿지 못하므로 npm으로 받은 d3(`d3/dist/d3.min.js`)를 `**/d3.min.js` 요청에 가로채 넣는다. 밝은·어두운 화면을 모두 찍는다.
3. 자료를 다시 만들 때는 `sh src/setup_workdirs.sh`로 스크립트를 `/home/claude/sudo`·`/home/claude/sudo2`에 복사한다. 스크립트가 이 절대 경로를 그대로 쓰기 때문이다(경로를 한 파일로 모으는 정리는 아직 안 함, 「다음 할 일」). 다 고친 뒤 `sh src/collect_back.sh`로 고친 스크립트와 페이지를 저장소로 되가져온다.
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
- 터미널: `bus/siwoe/terminals.py`(→ `tm`).
- `patch_page_*.py`는 페이지에 레이어를 처음 넣을 때 한 번만 돌린 것이라 다시 돌리지 않는다.

## 조사 도구 메모

- 조선일보 「조선 뉴스 라이브러리 100」: 이지의 크롬(Claude in Chrome)에서 `https://newslibrary.chosun.com/`을 열고 같은 사이트 안에서 `/priv/data/jsonData.php?case_num=1&query=…&field=&ds=1960.01.01&de=1999.12.31&type=article&wrt=&sort=2&page=N&size=100`을 fetch하면 본문(`body.archaic_hangul`)까지 온다. 기간을 좁게 주면 0건이 되는 일이 있어 넓게 받고 브라우저 안에서 거른다. 검색어 여러 개는 모두 든 기사만 나온다. 물음표·등호가 든 주소를 그대로 출력하면 도구가 막는다.
- 네이버 뉴스 라이브러리는 크롬 안전 제한으로 열리지 않았다.
- 나무위키: 크롬에서 열고, 문서를 옮길 때 `history.pushState` 뒤 `PopStateEvent`를 보내고 제목(h1)이 바뀔 때까지 기다린다. `/raw/` 주소는 확인 페이지가 떠서 쓰지 못했다.

## 정할 것(이지)

1. master에 합쳐 공개하는 때와, 그때 페이지 제목의 「시안」을 뺄지.
2. 버전 매기는 법.
3. claude.ai 아티팩트를 계속 함께 고칠지, 저장소만 고칠지.

## 다음 할 일

- 스크립트 경로를 한 파일(예: `src/paths.py`, 환경변수로 원자료 자리를 받음)로 모으기.
- 시외버스 터미널: 신촌·불광동·상봉의 문 연 날·닫은 날, 1985-08 구의 102개 노선 기사 다시 확인, 동아·경향 등 다른 신문, 2000년 뒤.
- 시외버스 노선: 노선 면허·고시 원문, 빠진 노선(부천, 인천–신촌 1998 등).
- 광역버스: 생긴 해를 못 찾은 13개, 2004년 뒤 서울 9xxx 번호가 끝난 해.
- 그 밖에 `docs/구상.md` 「확인 못 한 것」(1974년 전 국철 서울 밖 구간, 간선도로 날짜, 옛 물길 등).
- 공개 전 점검: `data.json`이 6.9MB라 휴대폰에서 처음 열 때 받는 양을 확인한다.
