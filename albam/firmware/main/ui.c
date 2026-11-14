/* 화면 두 개: 시계(첫 화면)와 와이파이 고르기.
 * 글자는 아직 숫자·영문만 나온다(LVGL 기본 글꼴에 한글이 없다). 한글은 화면을 옮길 때 넣는다.
 * 여기 함수는 모두 LVGL 작업 안(타이머·터치)에서 돈다. 다른 작업의 상태는 1초마다 읽어 온다. */
#include "ui.h"
#include "net.h"
#include "ota.h"

#include <stdio.h>
#include <string.h>
#include <time.h>
#include "bsp/esp-bsp.h"
#include "esp_app_desc.h"
#include "lvgl.h"
#include "sdkconfig.h"

#define MAX_APS 20

static lv_obj_t *s_home, *s_clock, *s_date, *s_net, *s_foot, *s_bar;
static lv_obj_t *s_setup, *s_list, *s_ssid, *s_pass, *s_keyboard, *s_msg;
static net_ap_t s_aps[MAX_APS];
static bool s_waiting_scan, s_joining;

static lv_obj_t *label(lv_obj_t *parent, const lv_font_t *font, uint32_t color)
{
    lv_obj_t *l = lv_label_create(parent);
    lv_obj_set_style_text_font(l, font, 0);
    lv_obj_set_style_text_color(l, lv_color_hex(color), 0);
    return l;
}

static lv_obj_t *button(lv_obj_t *parent, const char *text, lv_event_cb_t cb)
{
    lv_obj_t *b = lv_button_create(parent);
    lv_obj_add_event_cb(b, cb, LV_EVENT_CLICKED, NULL);
    lv_obj_t *l = lv_label_create(b);
    lv_label_set_text(l, text);
    lv_obj_set_style_text_font(l, &lv_font_montserrat_20, 0);
    lv_obj_center(l);
    return b;
}

/* ---- 와이파이 고르기 ---- */

static void scan(void)
{
    lv_obj_clean(s_list);
    lv_label_set_text(s_msg, "Searching...");
    s_waiting_scan = true;
    net_scan_start();
}

static void ap_clicked(lv_event_t *e)
{
    net_ap_t *ap = lv_event_get_user_data(e);
    lv_label_set_text(s_ssid, ap->ssid);
    lv_textarea_set_text(s_pass, "");
    lv_label_set_text(s_msg, ap->open ? "Open network: press the check key" : "Type the password");
}

static void fill_list(int count)
{
    lv_obj_clean(s_list);
    for (int i = 0; i < count; i++) {
        lv_obj_t *b = lv_list_add_button(s_list, s_aps[i].open ? LV_SYMBOL_WIFI : LV_SYMBOL_WIFI " " LV_SYMBOL_EYE_CLOSE,
                                         s_aps[i].ssid);
        lv_obj_set_style_text_font(b, &lv_font_montserrat_20, 0);
        lv_obj_add_event_cb(b, ap_clicked, LV_EVENT_CLICKED, &s_aps[i]);
    }
    lv_label_set_text(s_msg, count ? "Pick your Wi-Fi" : "Nothing found");
}

static void join(lv_event_t *e)
{
    const char *ssid = lv_label_get_text(s_ssid);
    if (ssid[0] == '\0') {
        lv_label_set_text(s_msg, "Pick your Wi-Fi first");
        return;
    }
    net_connect(ssid, lv_textarea_get_text(s_pass));
    s_joining = true;
    lv_label_set_text(s_msg, "Connecting...");
}

static void rescan_clicked(lv_event_t *e)
{
    scan();
}

static void back_clicked(lv_event_t *e)
{
    lv_screen_load(s_home);
}

static void open_setup(lv_event_t *e)
{
    s_joining = false;
    lv_label_set_text(s_ssid, "");
    lv_textarea_set_text(s_pass, "");
    lv_screen_load(s_setup);
    scan();
}

static void build_setup(void)
{
    s_setup = lv_obj_create(NULL);
    lv_obj_set_style_bg_color(s_setup, lv_color_hex(0x101418), 0);

    /* 왼쪽: 찾은 와이파이 */
    s_list = lv_list_create(s_setup);
    lv_obj_set_size(s_list, 480, 316);
    lv_obj_set_pos(s_list, 12, 12);

    /* 오른쪽: 고른 이름, 비밀번호, 버튼 */
    s_ssid = label(s_setup, &lv_font_montserrat_28, 0xffffff);
    lv_obj_set_pos(s_ssid, 512, 16);
    lv_obj_set_width(s_ssid, 750);
    lv_label_set_long_mode(s_ssid, LV_LABEL_LONG_MODE_DOTS);
    lv_label_set_text(s_ssid, "");

    s_pass = lv_textarea_create(s_setup);
    lv_textarea_set_one_line(s_pass, true);
    lv_textarea_set_max_length(s_pass, 64);
    lv_textarea_set_placeholder_text(s_pass, "Password");
    lv_obj_set_style_text_font(s_pass, &lv_font_montserrat_20, 0);
    lv_obj_set_size(s_pass, 750, 54);
    lv_obj_set_pos(s_pass, 512, 68);

    s_msg = label(s_setup, &lv_font_montserrat_20, 0xffd27a);
    lv_obj_set_pos(s_msg, 512, 146);
    lv_obj_set_width(s_msg, 750);
    lv_label_set_text(s_msg, "");

    lv_obj_t *rescan = button(s_setup, LV_SYMBOL_REFRESH " Search", rescan_clicked);
    lv_obj_set_size(rescan, 200, 64);
    lv_obj_set_pos(rescan, 512, 258);

    lv_obj_t *connect = button(s_setup, LV_SYMBOL_OK " Connect", join);
    lv_obj_set_size(connect, 200, 64);
    lv_obj_set_pos(connect, 732, 258);

    lv_obj_t *back = button(s_setup, LV_SYMBOL_LEFT " Back", back_clicked);
    lv_obj_set_size(back, 180, 64);
    lv_obj_set_pos(back, 1082, 258);

    /* 아래: 글자판. 체크 키는 연결과 같다 */
    s_keyboard = lv_keyboard_create(s_setup);
    lv_obj_set_size(s_keyboard, 1280, 380);
    lv_obj_align(s_keyboard, LV_ALIGN_BOTTOM_MID, 0, 0);
    lv_keyboard_set_textarea(s_keyboard, s_pass);
    lv_obj_add_event_cb(s_keyboard, join, LV_EVENT_READY, NULL);
}

/* ---- 시계 ---- */

static void build_home(void)
{
    s_home = lv_obj_create(NULL);
    lv_obj_set_style_bg_color(s_home, lv_color_hex(0x101418), 0);
    lv_obj_remove_flag(s_home, LV_OBJ_FLAG_SCROLLABLE);

    s_clock = label(s_home, &lv_font_montserrat_48, 0xffffff);
    lv_obj_set_style_transform_scale(s_clock, 768, 0);   /* 48 글꼴을 3배로 */
    lv_obj_set_style_transform_pivot_x(s_clock, lv_pct(50), 0);
    lv_obj_set_style_transform_pivot_y(s_clock, lv_pct(50), 0);
    lv_obj_align(s_clock, LV_ALIGN_CENTER, 0, -90);
    lv_label_set_text(s_clock, "--:--");

    s_date = label(s_home, &lv_font_montserrat_28, 0xb8c0c8);
    lv_obj_align(s_date, LV_ALIGN_CENTER, 0, 70);
    lv_label_set_text(s_date, "");

    s_net = label(s_home, &lv_font_montserrat_20, 0x8fd18f);
    lv_obj_align(s_net, LV_ALIGN_CENTER, 0, 150);
    lv_label_set_text(s_net, "");

    s_bar = lv_bar_create(s_home);
    lv_obj_set_size(s_bar, 720, 18);
    lv_obj_align(s_bar, LV_ALIGN_CENTER, 0, 210);
    lv_bar_set_range(s_bar, 0, 100);
    lv_obj_add_flag(s_bar, LV_OBJ_FLAG_HIDDEN);

    s_foot = label(s_home, &lv_font_montserrat_20, 0x70787f);
    lv_obj_align(s_foot, LV_ALIGN_BOTTOM_LEFT, 16, -14);
    lv_label_set_text_fmt(s_foot, "Albam board v%s   OTA code %s", esp_app_get_description()->version, ota_code());

    lv_obj_t *wifi = button(s_home, LV_SYMBOL_WIFI " Wi-Fi", open_setup);
    lv_obj_set_size(wifi, 150, 56);
    lv_obj_align(wifi, LV_ALIGN_TOP_RIGHT, -16, 16);
}

/* 1초마다: 시계, 연결 상태, 받는 중 표시, 와이파이 찾기 결과 */
static void tick(lv_timer_t *timer)
{
    static const char *const DAYS[] = { "Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat" };

    if (net_time_synced()) {
        time_t now = time(NULL);
        struct tm t;
        localtime_r(&now, &t);
        lv_label_set_text_fmt(s_clock, "%02d:%02d", t.tm_hour, t.tm_min);
        lv_label_set_text_fmt(s_date, "%04d-%02d-%02d  %s", t.tm_year + 1900, t.tm_mon + 1, t.tm_mday, DAYS[t.tm_wday]);
    }

    net_status_t net;
    net_get_status(&net);
    switch (net.state) {
    case NET_CONNECTED:
        lv_label_set_text_fmt(s_net, LV_SYMBOL_WIFI "  %s   http://%s/   albam-board.local", net.ssid, net.ip);
        break;
    case NET_CONNECTING:
        lv_label_set_text_fmt(s_net, "Connecting to %s...", net.ssid);
        break;
    case NET_FAILED:
        lv_label_set_text_fmt(s_net, "Could not join %s", net.ssid);
        break;
    default:
        lv_label_set_text(s_net, "No Wi-Fi yet: press Wi-Fi");
        break;
    }

    int progress = ota_progress();
    if (progress >= 0) {
        lv_obj_remove_flag(s_bar, LV_OBJ_FLAG_HIDDEN);
        lv_bar_set_value(s_bar, progress, LV_ANIM_OFF);
        lv_label_set_text_fmt(s_net, "Receiving new firmware %d%%", progress);
        if (lv_screen_active() != s_home) {
            lv_screen_load(s_home);
        }
    } else {
        lv_obj_add_flag(s_bar, LV_OBJ_FLAG_HIDDEN);
    }

    if (s_waiting_scan) {
        int count = net_scan_results(s_aps, MAX_APS);
        if (count >= 0) {
            s_waiting_scan = false;
            fill_list(count);
        }
    }
    if (s_joining && net.state == NET_CONNECTED) {
        s_joining = false;
        lv_screen_load(s_home);
    } else if (s_joining && net.state == NET_FAILED) {
        s_joining = false;
        lv_label_set_text(s_msg, "Could not connect. Check the password");
    }
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
        /* TRIPLE_PARTIAL 은 P4 에서 돌린 화면이 멈추는 문제가 알려져 있어 쓰지 않는다 */
        .tear_avoid_mode = ESP_LV_ADAPTER_TEAR_AVOID_MODE_DOUBLE_PARTIAL,
        .touch_flags = {
            .swap_xy = 1,
            .mirror_x = touch_other_way ? 0 : 1,
            .mirror_y = touch_other_way ? 1 : 0,
        },
    };
    /* I2C 버스를 화면보다 먼저 연다. 7인치 패널 드라이버가 같은 버스(1번)를 따로 열어 버려서,
     * 나중에 터치를 붙일 때 보드 패키지가 버스를 또 열다가 멈춘다. 먼저 열어 두면 드라이버가 그 버스를 같이 쓴다. */
    ESP_ERROR_CHECK(bsp_i2c_init());
    return bsp_display_start_with_config(&cfg);
}

void ui_start(void)
{
    lv_display_t *display = start_landscape();
    assert(display);
    /* 백라이트(GPIO 26 PWM)는 따로 켜 줘야 한다. 안 켜면 화면이 까맣다 */
    bsp_display_brightness_set(CONFIG_ALBAM_BRIGHTNESS);

    bsp_display_lock(-1);
    build_home();
    build_setup();
    lv_screen_load(s_home);

    net_status_t net;
    net_get_status(&net);
    if (net.state == NET_NO_WIFI) {
        open_setup(NULL);
    }
    lv_timer_create(tick, 1000, NULL);
    bsp_display_unlock();
}
