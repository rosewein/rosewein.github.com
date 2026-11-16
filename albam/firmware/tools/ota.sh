#!/bin/sh
# 무선으로 새 펌웨어 보내기 (보드와 같은 와이파이에서)
#   tools/ota.sh 123456                 화면에 나온 6자리 번호
#   tools/ota.sh 123456 192.168.0.12    albam-board.local 이 안 잡히면 주소를 직접
set -e
CODE="$1"
HOST="${2:-albam-board.local}"
BIN="$(dirname "$0")/../build/albam_board.bin"
[ -n "$CODE" ] || { echo "쓰는 법: $0 <화면의 6자리 번호> [주소]"; exit 1; }
[ -f "$BIN" ] || { echo "$BIN 이 없어요. 먼저 idf.py build"; exit 1; }
curl --fail-with-body -H "X-OTA-Code: $CODE" --data-binary "@$BIN" "http://$HOST/update"
echo
