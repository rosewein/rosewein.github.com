"""경로 한곳 모음(전국 연대지도).

- RAW: 원자료 폴더. 이지 컴퓨터의 다운로드 폴더를 작업 공간에 옮겨 둔 자리다(데스크톱 앱 연결 시
  /mnt/user-data/uploads/Downloads). 환경변수 KLM_RAW로 바꾼다. 원자료는 저장소에 넣지 않는다.
- WORK: 큰 중간 파일(OSM 추출 JSON, 표준노드링크 격자, 선형 GeoJSON 등). 환경변수 KLM_WORK로 바꾸고,
  기본은 korea_layer_map/work/(.gitignore로 빼 둠).
- DATA: 저장소에 올리는 작은 자료(korea_layer_map/data/).
"""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
RAW = Path(os.environ.get("KLM_RAW", "/mnt/user-data/uploads/Downloads"))
WORK = Path(os.environ.get("KLM_WORK", str(ROOT / "work")))


def _p(base, parts):
    p = base.joinpath(*parts)
    p.parent.mkdir(parents=True, exist_ok=True)
    return str(p)


def D(*parts):
    """저장소 data/ 아래 경로(문자열). 상위 폴더가 없으면 만든다."""
    return _p(DATA, parts)


def W(*parts):
    """중간 파일 work/ 아래 경로(문자열). 상위 폴더가 없으면 만든다."""
    return _p(WORK, parts)
