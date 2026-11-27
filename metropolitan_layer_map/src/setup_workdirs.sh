#!/bin/sh
# 저장소의 src/sudo·src/sudo2를 작업 폴더에 복사하고(있는 파일은 덮지 않음), 페이지 사본을 $MLM_SUDO/page에 둔다.
# 작업 폴더 자리는 src/paths.py와 같은 환경변수로 바꿀 수 있다(기본 /home/claude/sudo, /home/claude/sudo2).
# 스크립트가 paths.py를 찾도록 두 작업 폴더 바로 아래에 paths.py를 복사한다(이것은 덮어씀).
# 원자료는 $MLM_RAW(/home/claude/raw), $MLM_EXT(/home/claude/ext) 등에 이지의 다운로드 폴더에서 옮겨 둔다(HANDOFF.md 「새 작업 공간에서 시작하는 법」).
set -e
HERE=$(cd "$(dirname "$0")" && pwd)
H=${MLM_HOME:-/home/claude}
SUDO=${MLM_SUDO:-$H/sudo}
SUDO2=${MLM_SUDO2:-$H/sudo2}
mkdir -p "$SUDO" "$SUDO2"
cp -Rn "$HERE/sudo/." "$SUDO/"
cp -Rn "$HERE/sudo2/." "$SUDO2/"
cp "$HERE/paths.py" "$SUDO/paths.py"
cp "$HERE/paths.py" "$SUDO2/paths.py"
mkdir -p "$SUDO/page"
[ -f "$SUDO/page/data.json" ] || cp "$HERE/../data.json" "$SUDO/page/"
[ -f "$SUDO/page/index.html" ] || cp "$HERE/../index.html" "$SUDO/page/"
echo "작업 경로 준비됨: $SUDO, $SUDO2"
