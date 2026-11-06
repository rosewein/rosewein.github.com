#!/usr/bin/env python3
"""알밤 캐릭터·아이콘 도트 그림을 PNG 스프라이트 시트로 만든다.

    python3 tools/make_sprites.py

결과
  sprites/albam.png    캐릭터 32x32 칸, 줄마다 상태 하나(평소·배고픔·잠·기쁨), 칸 둘(애니메이션)
  sprites/icons.png    아이콘 12x12 칸
  sprites/sprites.json 칸 위치. 웹 화면과 나중의 ESP32(LVGL) 화면이 같이 쓴다

그림을 고칠 때는 이 파일을 고치고 다시 돌린다. PNG를 직접 고쳐도 되지만 그러면 이 파일과 어긋난다.
"""
import json
import math
import os

from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, '..', 'sprites')

PAL = {
    '.': None,
    'K': (42, 22, 12),      # 테두리
    'B': (138, 74, 34),     # 몸통
    'b': (104, 52, 24),     # 몸통 그늘
    'H': (196, 120, 70),    # 윤기
    'C': (214, 176, 122),   # 밑동
    'c': (176, 140, 92),    # 밑동 점
    'E': (24, 14, 8),       # 눈
    'W': (250, 240, 220),   # 눈 반짝
    'P': (224, 116, 100),   # 볼
    'M': (58, 26, 12),      # 입
    'S': (110, 180, 240),   # 땀
    'Z': (150, 170, 230),   # z
    'Y': (255, 214, 90),    # 반짝
    'w': (236, 230, 218),   # 아이콘 흰색
    'O': (255, 168, 72),    # 주황 강조
}

CELL = 32


def convex_hull(points):
    pts = sorted(set(points))

    def cross(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])
    lower, upper = [], []
    for p in pts:
        while len(lower) >= 2 and cross(lower[-2], lower[-1], p) <= 0:
            lower.pop()
        lower.append(p)
    for p in reversed(pts):
        while len(upper) >= 2 and cross(upper[-2], upper[-1], p) <= 0:
            upper.pop()
        upper.append(p)
    return lower[:-1] + upper[:-1]


def inside_convex(hull, x, y):
    n = len(hull)
    for i in range(n):
        ax, ay = hull[i]
        bx, by = hull[(i + 1) % n]
        if (bx - ax) * (y - ay) - (by - ay) * (x - ax) < 0:
            return False
    return True


def body(squash=0):
    """밤톨 몸 모양. 위는 뾰족, 아래는 둥글고 밑동은 밝다."""
    g = [['.'] * CELL for _ in range(CELL)]
    cx = 15.5
    cy = 19.5 + squash * 0.5
    rx = 13.0 + squash * 0.6
    ry = 10.5 - squash * 0.5
    bottom = int(cy + ry)
    # 타원 몸통과 꼭지점을 함께 감싸는 볼록 껍질 안쪽을 칠한다
    pts = [(cx + 0.5 + rx * math.cos(math.radians(a)), cy + 0.5 + ry * math.sin(math.radians(a))) for a in range(0, 360, 3)]
    pts.append((cx + 0.5, 1.5 + squash))
    hull = convex_hull(pts)
    for y in range(CELL):
        for x in range(CELL):
            if inside_convex(hull, x + 0.5, y + 0.5):
                g[y][x] = 'B'
    # 밑동
    base_from = bottom - 6
    for y in range(base_from, CELL):
        for x in range(CELL):
            if g[y][x] == 'B':
                g[y][x] = 'C'
    for y in range(base_from + 1, CELL, 2):
        for x in range((y % 4) // 2 + 1, CELL, 4):
            if g[y][x] == 'C':
                g[y][x] = 'c'
    # 오른쪽 그늘
    for y in range(CELL):
        row = [x for x in range(CELL) if g[y][x] == 'B']
        if row:
            for x in row[-3:]:
                g[y][x] = 'b'
    # 윤기
    for (x, y) in [(8, 12), (9, 11), (10, 10), (7, 13), (11, 9)]:
        y2 = y + squash
        if g[y2][x] == 'B':
            g[y2][x] = 'H'
    # 테두리
    out = [r[:] for r in g]
    for y in range(CELL):
        for x in range(CELL):
            if g[y][x] != '.':
                for ax, ay in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
                    if not (0 <= ax < CELL and 0 <= ay < CELL) or g[ay][ax] == '.':
                        out[y][x] = 'K'
                        break
    return out


def put(g, x, y, art):
    for j, line in enumerate(art):
        for i, ch in enumerate(line):
            if ch != ' ' and 0 <= y + j < CELL and 0 <= x + i < CELL:
                g[y + j][x + i] = ch


EYE_OPEN = ['EE', 'WE', 'EE']
EYE_HAPPY = [' E ', 'E E']
EYE_CLOSED = ['EEE']
EYE_WORRY = ['E  ', ' EE', ' WE', ' EE']
EYE_WORRY_R = ['  E', 'EE ', 'EW ', 'EE ']


def face(g, state, frame, squash):
    oy = squash
    if state == 'normal':
        put(g, 10, 16 + oy, EYE_OPEN)
        put(g, 20, 16 + oy, EYE_OPEN)
        put(g, 8, 20 + oy, ['PP'])
        put(g, 22, 20 + oy, ['PP'])
        put(g, 14, 20 + oy, ['M  M', ' MM '])
    elif state == 'hungry':
        put(g, 9, 15 + oy, EYE_WORRY)
        put(g, 20, 15 + oy, EYE_WORRY_R)
        put(g, 15, 20 + oy, [' M ', 'M M', ' M '])
        sy = 12 + (frame * 2)
        put(g, 25, sy, [' S', 'SS', 'SS'])
    elif state == 'sleep':
        put(g, 9, 18 + oy, EYE_CLOSED)
        put(g, 20, 18 + oy, EYE_CLOSED)
        put(g, 8, 20 + oy, ['PP'])
        put(g, 22, 20 + oy, ['PP'])
        put(g, 15, 21 + oy, ['MM'])
        if frame == 0:
            put(g, 24, 4, ['ZZZ', '  Z', ' Z ', 'ZZZ'])
        else:
            put(g, 26, 1, ['ZZZ', '  Z', ' Z ', 'ZZZ'])
            put(g, 22, 7, ['ZZ', 'ZZ'])
    elif state == 'happy':
        put(g, 9, 16 + oy, EYE_HAPPY)
        put(g, 20, 16 + oy, EYE_HAPPY)
        put(g, 8, 19 + oy, ['PP'])
        put(g, 22, 19 + oy, ['PP'])
        put(g, 13, 19 + oy, ['MMMMM', ' MPM ', '  M  '] if frame == 0 else ['MMMMM', 'M P M', ' MMM '])
        if frame == 0:
            put(g, 2, 6, [' Y ', 'YYY', ' Y '])
            put(g, 27, 10, ['Y'])
        else:
            put(g, 27, 4, [' Y ', 'YYY', ' Y '])
            put(g, 3, 11, ['Y'])


STATES = ['normal', 'hungry', 'sleep', 'happy']


def character_frames():
    rows = []
    for state in STATES:
        frames = []
        for frame in range(2):
            squash = 1 if frame == 1 and state != 'sleep' else 0
            if state == 'sleep':
                squash = frame  # 숨쉬기
            g = body(squash)
            face(g, state, frame, squash)
            frames.append(g)
        rows.append(frames)
    return rows


ICON = 12
ICONS = {
    'bottle': [
        '     OO     ',
        '    OOOO    ',
        '   wwwwww   ',
        '   w    w   ',
        '   wSSSSw   ',
        '   wSSSSw   ',
        '   wSSSSw   ',
        '   wSSSSw   ',
        '   wSSSSw   ',
        '   wSSSSw   ',
        '   wwwwww   ',
        '            ',
    ],
    'diaper': [
        '            ',
        '            ',
        ' wwwwwwwwww ',
        ' wwwwwwwwww ',
        ' wwOwwwwOww ',
        ' wwwwwwwwww ',
        '  wwwwwwww  ',
        '   wwwwww   ',
        '    wwww    ',
        '            ',
        '            ',
        '            ',
    ],
    'mic': [
        '    wwww    ',
        '   wwwwww   ',
        '   wwwwww   ',
        '   wwwwww   ',
        ' w wwwwww w ',
        ' w wwwwww w ',
        '  w wwww w  ',
        '   w    w   ',
        '    wwww    ',
        '     ww     ',
        '   wwwwww   ',
        '            ',
    ],
    'clock': [
        '   wwwwww   ',
        '  w      w  ',
        ' w   w    w ',
        ' w   w    w ',
        ' w   w    w ',
        ' w   wwww w ',
        ' w        w ',
        ' w        w ',
        '  w      w  ',
        '   wwwwww   ',
        '            ',
        '            ',
    ],
    'moon': [
        '   YYY      ',
        '  YYY       ',
        ' YYY        ',
        ' YYY        ',
        ' YYY        ',
        ' YYYY       ',
        '  YYYYY  Y  ',
        '   YYYYYYY  ',
        '    YYYYY   ',
        '            ',
        '            ',
        '            ',
    ],
    'check': [
        '            ',
        '          O ',
        '         OO ',
        '        OO  ',
        '       OO   ',
        ' O    OO    ',
        ' OO  OO     ',
        '  OOOO      ',
        '   OO       ',
        '            ',
        '            ',
        '            ',
    ],
}


def draw(img, ox, oy, grid):
    px = img.load()
    for y, line in enumerate(grid):
        for x, ch in enumerate(line):
            c = PAL.get(ch)
            if c:
                px[ox + x, oy + y] = c + (255,)


def main():
    os.makedirs(OUT, exist_ok=True)
    rows = character_frames()
    sheet = Image.new('RGBA', (CELL * 2, CELL * len(rows)), (0, 0, 0, 0))
    frames = {}
    for r, (state, row) in enumerate(zip(STATES, rows)):
        frames[state] = []
        for f, g in enumerate(row):
            draw(sheet, f * CELL, r * CELL, g)
            frames[state].append({'x': f * CELL, 'y': r * CELL, 'w': CELL, 'h': CELL})
    sheet.save(os.path.join(OUT, 'albam.png'))

    names = list(ICONS)
    icons = Image.new('RGBA', (ICON * len(names), ICON), (0, 0, 0, 0))
    icon_map = {}
    for i, name in enumerate(names):
        draw(icons, i * ICON, 0, ICONS[name])
        icon_map[name] = {'x': i * ICON, 'y': 0, 'w': ICON, 'h': ICON}
    icons.save(os.path.join(OUT, 'icons.png'))

    with open(os.path.join(OUT, 'sprites.json'), 'w', encoding='utf-8') as fh:
        json.dump({
            'albam': {'image': 'albam.png', 'frame_ms': 600, 'states': frames},
            'icons': {'image': 'icons.png', 'cells': icon_map},
        }, fh, ensure_ascii=False, indent=2)
        fh.write('\n')

    # 홈 화면 아이콘: 평소 얼굴 첫 칸을 어두운 바탕에
    face_img = sheet.crop((0, 0, CELL, CELL))
    for size, name in ((180, 'icon-180.png'), (192, 'icon-192.png'), (512, 'icon-512.png')):
        k = (size * 3 // 4) // CELL
        bg = Image.new('RGBA', (size, size), (14, 11, 9, 255))
        big = face_img.resize((CELL * k, CELL * k), Image.NEAREST)
        bg.alpha_composite(big, ((size - CELL * k) // 2, (size - CELL * k) // 2))
        bg.convert('RGB').save(os.path.join(HERE, '..', name))

    # 미리보기(저장소에는 안 넣음)
    prev = sheet.resize((sheet.width * 8, sheet.height * 8), Image.NEAREST)
    bg = Image.new('RGBA', prev.size, (16, 12, 10, 255))
    bg.alpha_composite(prev)
    bg.save(os.path.join(os.environ.get('PREVIEW_DIR', '/tmp'), 'albam_preview.png'))


if __name__ == '__main__':
    main()
