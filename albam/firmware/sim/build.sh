#!/bin/sh
# PC 미리 보기: 화면을 그려 PNG 로 남긴다 (gcc, python3 + pillow 필요)
#   sim/build.sh [결과 폴더]        albam/firmware 에서. 기본 결과 폴더는 sim/out
# LVGL 9.5.0 소스는 부품 저장소에서 처음 한 번 받아 sim/.lvgl 에 둔다.
set -e
cd "$(dirname "$0")/.."
OUT="${1:-sim/out}"
LVGL=sim/.lvgl
BUILD=sim/.build
mkdir -p "$OUT" "$BUILD"

if [ ! -f "$LVGL/lvgl.h" ]; then
  mkdir -p "$LVGL"
  curl -sSL -o "$BUILD/lvgl.zip" https://components-file.espressif.com/components/lvgl/lvgl/9.5.0/lvgl__lvgl-v9.5.0.zip
  unzip -q -o "$BUILD/lvgl.zip" -d "$LVGL"
fi

CFLAGS="-O1 -w -DLV_CONF_INCLUDE_SIMPLE -Isim -I$LVGL -Imain"
if [ ! -f "$BUILD/liblvgl.a" ]; then
  echo "LVGL 빌드 중(처음 한 번, 1~2분)"
  find "$LVGL/src" -name '*.c' | while read -r src; do
    obj="$BUILD/$(echo "$src" | tr '/' '_').o"
    echo "$obj: $src; gcc $CFLAGS -c $src -o $obj"
  done > "$BUILD/rules"
  awk -F'; ' '{print $2}' "$BUILD/rules" | xargs -P "$(nproc)" -I{} sh -c '{}'
  ar rcs "$BUILD/liblvgl.a" "$BUILD"/*.o
fi

gcc $CFLAGS -Wall sim/main.c main/ui.c main/care_text.c main/assets/sprites.c "$BUILD/liblvgl.a" -lm -o "$BUILD/preview"
"$BUILD/preview" main/assets "$OUT"
python3 - "$OUT" <<'PY'
import sys, pathlib
from PIL import Image
for ppm in sorted(pathlib.Path(sys.argv[1]).glob("*.ppm")):
    Image.open(ppm).save(ppm.with_suffix(".png"))
    ppm.unlink()
PY
echo "그림: $OUT"
