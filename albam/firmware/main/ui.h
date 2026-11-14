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

/* 화면 밝기(5~100%). 보드 쪽(board.c)이 맡고, 바꾸면 저장한다 */
int ui_brightness_get(void);
void ui_brightness_set(int percent);

/* 화면을 만들고 첫 화면을 띄운다. LVGL 잠금을 잡은 채로 부른다 */
void ui_build(const ui_fonts_t *fonts, const char *version);
