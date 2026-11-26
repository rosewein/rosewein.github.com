"""경로를 한곳에 모은다.
- CODE: 이 폴더(src/). 틀·설명문·스크립트
- DATA: 저장소의 data/. 지도에 들어가는 자료(스크립트가 여기서 읽고 여기에 쓴다)
- RAW: 저장소 밖 원자료(OSM 추출본, 열린데이터광장 CSV, 나무위키 문서 모음 등). 환경변수 SLM_RAW로 바꾼다
- WORK: RAW/build. 저장소에 넣지 않는 중간 파일(village.json, rail_parts/, landprice_report.json)
- FONTS: 저장소의 fonts/. 페이지 글자만 담은 글꼴(fonts.py가 만듦). FONTSRC: RAW/fonts. 받은 글꼴 원본(TTF)
옛 방식처럼 src와 data의 파일을 한 폴더에 모아 돌리면(옆에 data/가 없으면) DATA는 그 폴더가 된다."""
import os

CODE = os.path.dirname(os.path.abspath(__file__))
_d = os.path.join(os.path.dirname(CODE), "data")
DATA = _d if os.path.isdir(_d) else CODE
RAW = os.environ.get("SLM_RAW", "/home/claude/data")
WORK = os.path.join(RAW, "build")
FONTS = os.path.join(os.path.dirname(CODE), "fonts")
FONTSRC = os.path.join(RAW, "fonts")
