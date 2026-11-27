"""수도권 도시 연대지도 스크립트가 읽고 쓰는 자리를 한곳에 모은다.

기본값은 처음 만든 작업 공간(claude.ai 작업 공간)의 경로이고, 환경변수로 바꿀 수 있다.

  MLM_HOME     작업 공간 뿌리. 아래 기본값이 모두 이것을 따른다(기본 /home/claude)
  MLM_SUDO     1단계 작업 폴더(기본 $MLM_HOME/sudo). page/ 아래에 페이지 사본을 두고 고친다
  MLM_SUDO2    2단계 작업 폴더(기본 $MLM_HOME/sudo2). 버스 스크립트는 bus/ 아래
  MLM_RAW      원자료(HGIS·OSM·Natural Earth·택지정보시스템, 기본 $MLM_HOME/raw)
  MLM_EXT      GitHub에서 받은 외부 자료(admdongkor·metroscope, 기본 $MLM_HOME/ext)
  MLM_SEOUL    「서울 도시 연대지도」의 data 폴더(metro.json·metro_dates.json·rail.json·joseon.json,
               기본 $MLM_HOME/repo/seoul-layer-map/data). 저장소를 나누면 서울 저장소를 받은 자리로 바꾼다
  MLM_UPLOADS  이지의 다운로드 폴더에서 올린 버스 CSV(기본 /mnt/user-data/uploads/Downloads)
  MLM_VENDOR   npm으로 받은 d3(화면 찍기용, 기본 $MLM_HOME/vendor)

스크립트는 자기 폴더에서 위로 올라가며 paths.py를 찾아 읽는다. 저장소에서는 src/paths.py,
작업 공간에서는 setup_workdirs.sh가 $MLM_SUDO·$MLM_SUDO2 바로 아래에 복사해 둔 것을 읽는다.
"""
import os

_env = os.environ.get

HOME = _env('MLM_HOME', '/home/claude')
SUDO = _env('MLM_SUDO', os.path.join(HOME, 'sudo'))
SUDO2 = _env('MLM_SUDO2', os.path.join(HOME, 'sudo2'))
RAW = _env('MLM_RAW', os.path.join(HOME, 'raw'))
EXT = _env('MLM_EXT', os.path.join(HOME, 'ext'))
SEOUL = _env('MLM_SEOUL', os.path.join(HOME, 'repo', 'seoul-layer-map', 'data'))
UPLOADS = _env('MLM_UPLOADS', '/mnt/user-data/uploads/Downloads')
VENDOR = _env('MLM_VENDOR', os.path.join(HOME, 'vendor'))

PAGE = os.path.join(SUDO, 'page')
PAGE_DATA = os.path.join(PAGE, 'data.json')
PAGE_HTML = os.path.join(PAGE, 'index.html')

if __name__ == '__main__':
    for k in ('HOME', 'SUDO', 'SUDO2', 'RAW', 'EXT', 'SEOUL', 'UPLOADS', 'VENDOR', 'PAGE_DATA', 'PAGE_HTML'):
        print(f'{k:9} {globals()[k]}')
