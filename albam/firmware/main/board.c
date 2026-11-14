/* 보드: Waveshare ESP32-P4-WIFI6-Touch-LCD-7 (7인치 올인원). 화면 ILI9881C(세로 720x1280), 터치 GT9271 */
#include "board.h"
#include "ota.h"
#include "store.h"
#include "ui.h"

#include <stdio.h>
#include <stdlib.h>

#include <string.h>
#include <time.h>
#include "bsp/esp-bsp.h"
#include "driver/ppa.h"
#include "esp_cache.h"
#include "esp_app_desc.h"
#include "lvgl.h"
#include "sdkconfig.h"

/* main/assets 의 TTF 두 개를 펌웨어에 그대로 넣은 것(CMakeLists.txt EMBED_FILES) */
extern const uint8_t regular_start[] asm("_binary_pretendard_regular_ttf_start");
extern const uint8_t regular_end[] asm("_binary_pretendard_regular_ttf_end");
extern const uint8_t semibold_start[] asm("_binary_pretendard_semibold_ttf_start");
extern const uint8_t semibold_end[] asm("_binary_pretendard_semibold_ttf_end");

/* 화면을 돌려 옮기는 일을 P4 의 그림 가속기(PPA) 대신 CPU 로 한다.
 *
 * 화면 패키지(esp_lvgl_adapter)는 고친 부분을 세로 패널 방향으로 돌려 옮길 때 PPA 를 부르고 끝나기를 기다린다.
 * 그런데 P4 에서는 PPA 가 끝내 답을 안 줘서 화면이 통째로 멈추는 일이 있다(0.2.2 에서 시계까지 멈춤. 패키지 README 의
 * "PPA Freeze Fix"). 그 함수를 링커에서 바꿔 끼워(CMakeLists.txt 의 --wrap) 같은 일을 CPU 로 한다.
 * 크기를 바꾸거나 색을 바꾸는 부름은 우리 화면에서 쓰지 않으며, 오면 원래 함수로 넘긴다. */
esp_err_t __real_ppa_do_scale_rotate_mirror(ppa_client_handle_t client, const ppa_srm_oper_config_t *config);

esp_err_t __wrap_ppa_do_scale_rotate_mirror(ppa_client_handle_t client, const ppa_srm_oper_config_t *c)
{
    int bytes = c->in.srm_cm == PPA_SRM_COLOR_MODE_RGB565 ? 2 : c->in.srm_cm == PPA_SRM_COLOR_MODE_RGB888 ? 3 : 0;
    bool plain = bytes && c->out.srm_cm == c->in.srm_cm && c->scale_x == 1.0f && c->scale_y == 1.0f &&
                 !c->mirror_x && !c->mirror_y && !c->rgb_swap && !c->byte_swap;
    if (!plain) {
        return __real_ppa_do_scale_rotate_mirror(client, c);
    }

    const int w = c->in.block_w, h = c->in.block_h;
    const size_t src_stride = (size_t)c->in.pic_w * bytes, dst_stride = (size_t)c->out.pic_w * bytes;
    const uint8_t *src = (const uint8_t *)c->in.buffer + c->in.block_offset_y * src_stride + (size_t)c->in.block_offset_x * bytes;
    uint8_t *dst = (uint8_t *)c->out.buffer + c->out.block_offset_y * dst_stride + (size_t)c->out.block_offset_x * bytes;
    /* 돌린 뒤의 크기: 90·270도면 가로세로가 바뀐다 */
    const bool turned = c->rotation_angle == PPA_SRM_ROTATION_ANGLE_90 || c->rotation_angle == PPA_SRM_ROTATION_ANGLE_270;
    const int out_w = turned ? h : w, out_h = turned ? w : h;

    /* 옮길 자리(dx, dy)를 한 줄씩 채운다. 그 자리에 올 원본 점(sx, sy):
     *   270(시계 방향 90도): sx = dy,         sy = h - 1 - dx
     *   90:                  sx = w - 1 - dy, sy = dx
     *   180:                 sx = w - 1 - dx, sy = h - 1 - dy */
    for (int dy = 0; dy < out_h; dy++) {
        uint8_t *out = dst + dy * dst_stride;
        if (c->rotation_angle == PPA_SRM_ROTATION_ANGLE_0) {
            memcpy(out, src + dy * src_stride, (size_t)w * bytes);
            continue;
        }
        for (int dx = 0; dx < out_w; dx++) {
            int sx, sy;
            if (c->rotation_angle == PPA_SRM_ROTATION_ANGLE_270) {
                sx = dy;
                sy = h - 1 - dx;
            } else if (c->rotation_angle == PPA_SRM_ROTATION_ANGLE_90) {
                sx = w - 1 - dy;
                sy = dx;
            } else {
                sx = w - 1 - dx;
                sy = h - 1 - dy;
            }
            const uint8_t *in = src + sy * src_stride + (size_t)sx * bytes;
            if (bytes == 2) {
                *(uint16_t *)(out + dx * 2) = *(const uint16_t *)in;
            } else {
                memcpy(out + dx * 3, in, 3);
            }
        }
    }
    /* 화면 패키지는 PPA 가 메모리에 바로 썼다고 여긴다. CPU 로 쓴 것을 메모리까지 내보낸다 */
    esp_cache_msync(dst - (size_t)c->out.block_offset_x * bytes, out_h * dst_stride,
                    ESP_CACHE_MSYNC_FLAG_DIR_C2M | ESP_CACHE_MSYNC_FLAG_UNALIGNED);
    return ESP_OK;
}

/* 패널은 세로(720x1280)다. 90도(설정에 따라 270도) 돌려 가로 1280x720 으로 쓴다.
 * 터치는 화면과 따로라서 같은 방향으로 맞춰 준다(칩이 준 좌표를 뒤집고 x·y 를 바꾼다). */
static lv_display_t *start_landscape(void)
{
    bool other_way = false, touch_other_way = false;
#ifdef CONFIG_ALBAM_ROTATE_270
    other_way = true;
    touch_other_way = true;
#endif
#ifdef CONFIG_ALBAM_TOUCH_FLIP
    touch_other_way = !touch_other_way;
#endif
    bsp_display_cfg_t cfg = {
        .lv_adapter_cfg = ESP_LV_ADAPTER_DEFAULT_CONFIG(),
        .rotation = other_way ? ESP_LV_ADAPTER_ROTATE_270 : ESP_LV_ADAPTER_ROTATE_90,
        /* 고친 부분만 다시 그려 보낸다. 돌려 옮기는 일은 위의 CPU 함수가 한다 */
        .tear_avoid_mode = ESP_LV_ADAPTER_TEAR_AVOID_MODE_DOUBLE_PARTIAL,
        .touch_flags = {
            .swap_xy = 1,
            .mirror_x = touch_other_way ? 0 : 1,
            .mirror_y = touch_other_way ? 1 : 0,
        },
    };
    /* 글꼴(TTF)을 그릴 때 스택을 많이 쓴다 */
    cfg.lv_adapter_cfg.task_stack_size = 32 * 1024;

    /* I2C 버스를 화면보다 먼저 연다. 7인치 패널 드라이버가 같은 버스(1번)를 따로 열어 버려서,
     * 나중에 터치를 붙일 때 보드 패키지가 버스를 또 열다가 멈춘다. 먼저 열어 두면 드라이버가 그 버스를 같이 쓴다. */
    ESP_ERROR_CHECK(bsp_i2c_init());
    return bsp_display_start_with_config(&cfg);
}

/* Pretendard 를 크기별로 만든다. 그림 글자(와이파이 표시 등)는 LVGL 기본 글꼴에서 빌린다 */
static const lv_font_t *font(bool semibold, int size, const lv_font_t *symbols)
{
    const uint8_t *start = semibold ? semibold_start : regular_start;
    const uint8_t *end = semibold ? semibold_end : regular_end;
    lv_font_t *f = lv_tiny_ttf_create_data_ex(start, end - start, size, LV_FONT_KERNING_NONE, 96);
    assert(f);
    f->fallback = symbols;
    return f;
}

/* ---- 밝기: 낮과 밤을 따로 둔다 ----
 * 밤(오후 8시 ~ 오전 6시)에는 거실 불이 꺼지므로 어둡게(처음 값 20%). 설정 화면에서 둘 다 바꿀 수 있다.
 * 백라이트는 GPIO 26 의 PWM 이다. */
#define NIGHT_START_HOUR 20
#define NIGHT_END_HOUR 6
#define NIGHT_DEFAULT 20
#define PREVIEW_SECONDS 3     /* 설정에서 막대를 움직이면 그 밝기를 잠깐 보여 준다 */
#define WAKE_SECONDS 30       /* 밤에 화면을 누르면 이만큼 낮 밝기로(웹앱 nightWakeSeconds) */

static int s_day, s_night, s_shown = -1;
static time_t s_preview_until, s_wake_until;

static int clamp_percent(int percent)
{
    return percent < 5 ? 5 : percent > 100 ? 100 : percent;
}

static void show_brightness(int percent)
{
    if (percent != s_shown) {
        s_shown = percent;
        bsp_display_brightness_set(percent);
    }
}

static bool is_night(time_t now)
{
    if (now < 1700000000) {
        return false;   /* 아직 시각을 못 받았으면 낮으로 */
    }
    struct tm t;
    localtime_r(&now, &t);
    return t.tm_hour >= NIGHT_START_HOUR || t.tm_hour < NIGHT_END_HOUR;
}

int ui_brightness_get(bool night)
{
    return night ? s_night : s_day;
}

void ui_brightness_set(bool night, int percent, bool save)
{
    percent = clamp_percent(percent);
    *(night ? &s_night : &s_day) = percent;
    show_brightness(percent);
    s_preview_until = time(NULL) + PREVIEW_SECONDS;
    if (save) {
        char text[8];
        snprintf(text, sizeof(text), "%d", percent);
        store_set(night ? "night_bri" : "brightness", text);
    }
}

/* 화면을 눌렀다: 밤이면 잠깐 낮 밝기로. 누를 때마다 30초가 다시 시작된다 */
void ui_brightness_wake(void)
{
    time_t now = time(NULL);
    s_wake_until = now + WAKE_SECONDS;
    if (is_night(now) && now >= s_preview_until && ota_progress() < 0) {
        show_brightness(s_day);
    }
}

/* 1초마다: 지금이 낮인지 밤인지에 맞춘다 */
void ui_brightness_refresh(void)
{
    time_t now = time(NULL);
    /* 새 펌웨어를 받는 동안에는 화면을 끈다. 플래시에 쓰는 동안 패널이 번쩍이는데,
     * 까만 화면으로 바꿔도 그대로여서(0.3.4) 백라이트를 꺼서 가린다. 다 받으면 다시 켜지며 돌아온다 */
    if (ota_progress() >= 0) {
        show_brightness(0);
    } else if (now >= s_preview_until) {
        show_brightness(is_night(now) && now >= s_wake_until ? s_night : s_day);
    }
}

void board_start_ui(void)
{
    lv_display_t *display = start_landscape();
    assert(display);

    char saved[8];
    s_day = clamp_percent(store_get("brightness", saved, sizeof(saved)) ? atoi(saved) : CONFIG_ALBAM_BRIGHTNESS);
    s_night = clamp_percent(store_get("night_bri", saved, sizeof(saved)) ? atoi(saved) : NIGHT_DEFAULT);

    bsp_display_lock(-1);
    const ui_fonts_t fonts = {
        .huge = font(true, 150, &lv_font_montserrat_48),
        .big = font(true, 80, &lv_font_montserrat_48),
        .title = font(true, 44, &lv_font_montserrat_28),
        .text = font(false, 34, &lv_font_montserrat_28),
        .small = font(false, 28, &lv_font_montserrat_28),
    };
    ui_build(&fonts, esp_app_get_description()->version);
    bsp_display_unlock();

    /* 백라이트는 따로 켜 줘야 한다. 안 켜면 화면이 까맣다 */
    ui_brightness_refresh();
}
