import os as _os, sys as _sys  # paths.py 찾기: 이 파일 폴더에서 위로 올라감(저장소 src/, 작업 공간 $MLM_SUDO·$MLM_SUDO2)
_d = _os.path.dirname(_os.path.abspath(__file__))
while _d != _os.path.dirname(_d) and not _os.path.isfile(_os.path.join(_d, 'paths.py')):
    _d = _os.path.dirname(_d)
_sys.path.insert(1, _d)
from paths import PAGE_DATA, SUDO2  # noqa: E402
import json
P=PAGE_DATA
d=json.load(open(P)); j=json.load(open(f'{SUDO2}/joseon_sudo.json'))
d['joseon']=j
json.dump(d,open(P,'w'),ensure_ascii=False,separators=(',',':'))
print(len(j['roads']),len(j['pts']))
