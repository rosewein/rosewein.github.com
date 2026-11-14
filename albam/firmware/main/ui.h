#pragma once
#include "lvgl.h"

/* 화면이 쓰는 글꼴(Pretendard). board.c 가 TTF 에서 만들어 넘긴다 */
typedef struct {
    const lv_font_t *huge;    /* 말풍선의 지난 시간 숫자 */
    const lv_font_t *big;     /* 칸의 지난 시간 숫자 */
    const lv_font_t *title;   /* 문구, 시계, 단위 */
    const lv_font_t *text;    /* 본문 */
    const lv_font_t *small;   /* 맨 위 줄 */
} ui_fonts_t;

/* 화면 밝기(5~100%). 낮과 밤(오후 8시~오전 6시)을 따로 둔다. 보드 쪽(board.c)이 맡는다 */
#include <stdbool.h>
int ui_brightness_get(bool night);
void ui_brightness_set(bool night, int percent, bool save);   /* 막대를 움직이는 동안은 save 없이, 손을 떼면 저장 */
void ui_brightness_refresh(void);                              /* 1초마다: 지금 시각에 맞는 밝기로 */

/* 문제를 찾을 때: 지금까지 들어온 터치 수와 마지막으로 누른 자리 */
void ui_touch_diag(int *presses, int *x, int *y);

/* 화면을 만들고 첫 화면을 띄운다. LVGL 잠금을 잡은 채로 부른다 */
void ui_build(const ui_fonts_t *fonts, const char *version);
