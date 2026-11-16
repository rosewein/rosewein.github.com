#!/usr/bin/env python3
"""웹앱의 글꼴과 알밤 그림을 보드용으로 바꾼다.

  python3 tools/make_assets.py        (albam/firmware 에서, pip install fonttools brotli pillow)

  ../fonts/Pretendard-*.subset.woff2  →  main/assets/pretendard-*.ttf   (보드가 그대로 읽는 TTF)
  ../sprites/albam.png                →  main/assets/sprites.c          (표정 4줄 x 2칸, 32x32)

웹앱의 글꼴이나 그림을 바꾸면 다시 돌리고 결과를 같이 올린다.
"""
import json
from pathlib import Path

from fontTools.ttLib import TTFont
from PIL import Image

HERE = Path(__file__).resolve().parent.parent
WEB = HERE.parent
OUT = HERE / "main" / "assets"

# 보드에서 안 쓰는 표(글자 바꿔치기·힌팅 등)는 뺀다
DROP = ["GSUB", "GPOS", "GDEF", "DSIG", "fpgm", "prep", "cvt ", "gasp", "meta", "STAT"]


def fonts():
    for weight in ("Regular", "SemiBold"):
        font = TTFont(WEB / "fonts" / f"Pretendard-{weight}.subset.woff2")
        font.flavor = None
        for table in DROP:
            if table in font:
                del font[table]
        target = OUT / f"pretendard-{weight.lower()}.ttf"
        font.save(target)
        print(target.name, target.stat().st_size, "bytes")


def sprites():
    sheet = Image.open(WEB / "sprites" / "albam.png").convert("RGBA")
    cells = json.loads((WEB / "sprites" / "sprites.json").read_text())["albam"]["states"]
    moods = ["normal", "hungry", "sleep", "happy"]   # care_text.h 의 care_mood_t 순서
    lines = [
        "/* tools/make_assets.py 가 만든 파일. 손으로 고치지 않는다. */",
        '#include "lvgl.h"',
        "",
    ]
    names = []
    for mood in moods:
        for frame, cell in enumerate(cells[mood]):
            image = sheet.crop((cell["x"], cell["y"], cell["x"] + cell["w"], cell["y"] + cell["h"]))
            name = f"albam_{mood}_{frame}"
            names.append(name)
            data = []
            for r, g, b, a in image.getdata():
                data += [b, g, r, a]   # LVGL ARGB8888 은 바이트 순서가 B G R A
            lines.append(f"static const uint8_t {name}_map[] = {{")
            for i in range(0, len(data), 32):
                lines.append("    " + ",".join(str(v) for v in data[i:i + 32]) + ",")
            lines.append("};")
            lines.append(f"static const lv_image_dsc_t {name} = {{")
            lines.append("    .header = { .magic = LV_IMAGE_HEADER_MAGIC, .cf = LV_COLOR_FORMAT_ARGB8888,")
            lines.append(f"                .w = {cell['w']}, .h = {cell['h']}, .stride = {cell['w'] * 4} }},")
            lines.append(f"    .data_size = sizeof({name}_map), .data = {name}_map,")
            lines.append("};")
            lines.append("")
    lines.append("/* [표정][칸] */")
    lines.append("const lv_image_dsc_t *const albam_sprites[4][2] = {")
    for i in range(0, len(names), 2):
        lines.append(f"    {{ &{names[i]}, &{names[i + 1]} }},")
    lines.append("};")
    (OUT / "sprites.c").write_text("\n".join(lines) + "\n")
    print("sprites.c", len(names), "cells")


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    fonts()
    sprites()
