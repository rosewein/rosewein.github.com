#!/bin/sh
# 작업 폴더($MLM_SUDO, $MLM_SUDO2 — 기본 /home/claude/sudo, sudo2)에서 고친 스크립트와 사람이 정한 작은 자료, 페이지를 저장소로 되가져온다.
# 큰 중간 파일(.pkl, .npz, gj/, data_*.json, sgg_topo.json, hgis.pkl)과 페이지 백업은 가져오지 않는다.
# setup_workdirs.sh가 복사해 둔 paths.py 사본도 가져오지 않는다(원본은 src/paths.py).
set -e
HERE=$(cd "$(dirname "$0")" && pwd)
H=${MLM_HOME:-/home/claude}
SUDO=${MLM_SUDO:-$H/sudo}
SUDO2=${MLM_SUDO2:-$H/sudo2}
for pair in "$SUDO:sudo" "$SUDO2:sudo2"; do
  src=${pair%:*}; dst=$HERE/${pair##*:}
  mkdir -p "$dst"
  (cd "$src" && find . -type f ! -path "*/__pycache__/*" ! -path "*/shots/*" ! -path "./gj/*" ! -path "./page/*" ! -path "./paths.py" \
    \( -name "*.py" -o -name "*.tsv" -o -name "*.sh" -o -name "*.txt" -o \( -name "*.json" -size -700k ! -name "bus_gg.json" ! -name "data_*.json" \) \) \
    | grep -v index_before | tar cf - -T -) | (cd "$dst" && tar xf -)
done
cp "$SUDO/page/index.html" "$SUDO/page/data.json" "$HERE/.."
echo "저장소로 가져옴: $HERE"
