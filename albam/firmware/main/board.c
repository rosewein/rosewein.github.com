/* 보드: Waveshare ESP32-P4-WIFI6-Touch-LCD-7 (7인치 올인원). 화면 ILI9881C(세로 720x1280), 터치 GT9271 */
#include "board.h"
#include "ui.h"

#include "bsp/esp-bsp.h"
#include "esp_app_desc.h"
#include "lvgl.h"
#include "sdkconfig.h"

/* main/assets/*.ttf 를 펌웨어에 그대로 넣은 것(CMakeLists.txt EMBED_FILES) */
extern const uint8_t regular_start[] asm("_binary_pretendard_regular_ttf_start");
extern const uint8_t regular_end[] asm("_binary_pretendard_regular_ttf_end");
extern const uint8_t semibold_start[] asm("_binary_pretendard_semibold_ttf_start");
extern const uint8_t semibold_end[] asm("_binary_pretendard_semibold_ttf_end");

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
        /* TRIPLE_PARTIAL 은 P4 에서 돌린 화면이 멈추는 문제가 알려져 있어 쓰지 않는다 */
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

void board_start_ui(void)
{
    lv_display_t *display = start_landscape();
    assert(display);

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

    /* 백라이트(GPIO 26 PWM)는 따로 켜 줘야 한다. 안 켜면 화면이 까맣다 */
    bsp_display_brightness_set(CONFIG_ALBAM_BRIGHTNESS);
}
