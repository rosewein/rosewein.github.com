#!/bin/sh
# 작업 공간(/home/claude/sudo, sudo2)에서 고친 스크립트와 사람이 정한 작은 자료, 페이지를 저장소로 되가져온다.
# 큰 중간 파일(.pkl, .npz, gj/, data_*.json, sgg_topo.json, hgis.pkl)과 페이지 백업은 가져오지 않는다.
set -e
HERE=$(cd "$(dirname "$0")" && pwd)
cd /home/claude
find sudo sudo2 -type f ! -path "*/__pycache__/*" ! -path "*/shots/*" ! -path "sudo/gj/*" ! -path "sudo/page/*" \
  \( -name "*.py" -o -name "*.tsv" -o -name "*.sh" -o -name "*.txt" -o \( -name "*.json" -size -700k ! -name "bus_gg.json" ! -name "data_*.json" \) \) \
  | grep -v index_before | tar cf - -T - | (cd "$HERE" && tar xf -)
cp /home/claude/sudo/page/index.html /home/claude/sudo/page/data.json "$HERE/.."
echo "저장소로 가져옴: $HERE"
