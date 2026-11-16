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
void ui_brightness_wake(void);                                 /* 화면을 눌렀다: 밤이면 30초 동안 낮 밝기로 */
void ui_brightness_refresh(void);                              /* 1초마다: 지금 시각에 맞는 밝기로 */

/* 효과음(sound.c). 소리 크기는 0~100, 0 이면 끔. 밤에는 절반으로 낸다 */
typedef enum { UI_SOUND_TAP, UI_SOUND_SAVE, UI_SOUND_CANCEL, UI_SOUND_ERROR } ui_sound_t;
void ui_sound(ui_sound_t sound);
int ui_volume_get(void);
void ui_volume_set(int percent, bool save);

/* 화면이 살아 있는지: 1초마다 는다(멈추면 화면이 멈춘 것) */
uint32_t ui_ticks(void);
const char *ui_where(void);   /* 마지막으로 연 화면("home", "day", "settings" …) */
/* 화면을 돌려 옮기는 일을 몇 번 시작해 몇 번 끝냈나(board.c). 다르면 그 안에서 멈춘 것 */
void board_rotate_counts(uint32_t *started, uint32_t *finished);
/* I2C(터치·소리 칩) 통신이 실패한 횟수와 버스를 초기화한 횟수(board.c) */
void board_i2c_counts(uint32_t *errors, uint32_t *resets);

/* 문제를 찾을 때: 지금까지 들어온 터치 수와 마지막으로 누른 자리 */
void ui_touch_diag(int *presses, int *x, int *y);

/* 화면을 만들고 첫 화면을 띄운다. LVGL 잠금을 잡은 채로 부른다 */
void ui_build(const ui_fonts_t *fonts, const char *version);
