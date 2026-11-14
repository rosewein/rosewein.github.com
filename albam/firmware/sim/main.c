/* PC 미리 보기: 보드 없이 화면(ui.c)을 그려 그림 파일로 남긴다. 쓰는 법은 sim/build.sh.
 * 통신(net·care·ota)은 가짜 값으로 바꿔 끼운다. */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>

#include "lvgl.h"
#include "care.h"
#include "net.h"
#include "ota.h"
#include "ui.h"

#define W 1280
#define H 720

static uint32_t s_ms;
static uint8_t s_pixels[W * H * 4];

/* ---- 가짜 통신 ---- */
static net_status_t s_net = { NET_CONNECTED, "우리집 5G", "192.168.1.40" };
static care_state_t s_care = CARE_OK;
static care_summary_t s_summary;
static uint32_t s_generation = 1;
static int s_ota = -1;

void net_get_status(net_status_t *out) { *out = s_net; }
void net_connect(const char *ssid, const char *password) { (void)ssid; (void)password; }
void net_scan_start(void) {}
int net_scan_results(net_ap_t *out, int max)
{
    static const net_ap_t APS[] = { { "우리집 5G", -40, false }, { "우리집 2.4G", -48, false }, { "KT_GiGA_2F", -70, false }, { "Cafe Free", -80, true } };
    (void)max;
    memcpy(out, APS, sizeof(APS));
    return 4;
}
bool net_time_synced(void) { return true; }
const char *ota_code(void) { return "123456"; }
int ota_progress(void) { return s_ota; }
care_state_t care_state(void) { return s_care; }
const char *care_email(void) { return s_care == CARE_OK || s_care == CARE_OFFLINE ? "family@example.com" : ""; }
bool care_copy_summary(care_summary_t *out, uint32_t *seen)
{
    if (*seen == s_generation) {
        return false;
    }
    *out = s_summary;
    *seen = s_generation;
    return true;
}
void care_login(const char *email, const char *password) { (void)email; (void)password; }
void care_logout(void) { s_care = CARE_NEED_LOGIN; }
void care_diag(care_diag_t *out)
{
    *out = (care_diag_t){ .ok = 512, .fails = 3, .seconds_since_ok = 4, .seconds_since_error = 1260 };
    snprintf(out->last_error, sizeof(out->last_error), "connect: ESP_ERR_HTTP_CONNECT (errno 113)");
}
static int s_brightness = 70;
int ui_brightness_get(void) { return s_brightness; }
void ui_brightness_set(int percent) { s_brightness = percent; }

/* ---- 그리기 ---- */
static uint32_t tick_now(void) { return s_ms; }

static void flush(lv_display_t *display, const lv_area_t *area, uint8_t *pixels)
{
    (void)area; (void)pixels;
    lv_display_flush_ready(display);
}

static void run(int ms)
{
    for (int i = 0; i < ms; i += 10) {
        s_ms += 10;
        lv_timer_handler();
    }
}

static void save(const char *name)
{
    char path[256];
    snprintf(path, sizeof(path), "%s.ppm", name);
    FILE *f = fopen(path, "wb");
    fprintf(f, "P6 %d %d 255\n", W, H);
    for (int i = 0; i < W * H; i++) {
        fputc(s_pixels[i * 4 + 2], f);
        fputc(s_pixels[i * 4 + 1], f);
        fputc(s_pixels[i * 4 + 0], f);
    }
    fclose(f);
    printf("%s\n", path);
}

static void *read_file(const char *path, size_t *size)
{
    FILE *f = fopen(path, "rb");
    if (!f) {
        fprintf(stderr, "%s 를 못 읽음\n", path);
        exit(1);
    }
    fseek(f, 0, SEEK_END);
    *size = ftell(f);
    rewind(f);
    void *data = malloc(*size);
    if (fread(data, 1, *size, f) != *size) {
        exit(1);
    }
    fclose(f);
    return data;
}

static const lv_font_t *font(const void *data, size_t size, int px, const lv_font_t *symbols)
{
    lv_font_t *f = lv_tiny_ttf_create_data_ex(data, size, px, LV_FONT_KERNING_NONE, 96);
    f->fallback = symbols;
    return f;
}

static time_t at(int day, int hour, int minute)
{
    struct tm t = { .tm_year = 126, .tm_mon = 10, .tm_mday = day, .tm_hour = hour, .tm_min = minute, .tm_isdst = -1 };
    return mktime(&t);
}

/* 누를 곳을 좌표로 정해 버튼을 눌러 본다 */
static lv_point_t s_touch;
static bool s_pressed;
static void read_touch(lv_indev_t *indev, lv_indev_data_t *data)
{
    (void)indev;
    data->point = s_touch;
    data->state = s_pressed ? LV_INDEV_STATE_PRESSED : LV_INDEV_STATE_RELEASED;
}
static void tap(int x, int y)
{
    s_touch = (lv_point_t){ x, y };
    s_pressed = true;
    run(100);
    s_pressed = false;
    run(300);
}

int main(int argc, char **argv)
{
    const char *assets = argc > 1 ? argv[1] : "main/assets";
    const char *out = argc > 2 ? argv[2] : ".";
    char path[256], name[256];
    setenv("TZ", "KST-9", 1);
    tzset();

    lv_init();
    lv_tick_set_cb(tick_now);
    lv_display_t *display = lv_display_create(W, H);
    lv_display_set_buffers(display, s_pixels, NULL, sizeof(s_pixels), LV_DISPLAY_RENDER_MODE_DIRECT);
    lv_display_set_flush_cb(display, flush);
    lv_indev_t *touch = lv_indev_create();
    lv_indev_set_type(touch, LV_INDEV_TYPE_POINTER);
    lv_indev_set_read_cb(touch, read_touch);

    size_t regular_size, semibold_size;
    snprintf(path, sizeof(path), "%s/pretendard-regular.ttf", assets);
    void *regular = read_file(path, &regular_size);
    snprintf(path, sizeof(path), "%s/pretendard-semibold.ttf", assets);
    void *semibold = read_file(path, &semibold_size);
    const ui_fonts_t fonts = {
        .huge = font(semibold, semibold_size, 150, &lv_font_montserrat_48),
        .big = font(semibold, semibold_size, 80, &lv_font_montserrat_48),
        .title = font(semibold, semibold_size, 44, &lv_font_montserrat_28),
        .text = font(regular, regular_size, 34, &lv_font_montserrat_28),
        .small = font(regular, regular_size, 28, &lv_font_montserrat_28),
    };

    /* 지금 시각을 고정하려고 요약의 시각을 실제 지금에 맞춰 뒤로 민다 */
    time_t now = time(NULL);
    struct tm t;
    localtime_r(&now, &t);
#define AGO(minutes) (now - (minutes) * 60)

    /* 1. 평온: 수유 2시간 35분 전 */
    s_summary = (care_summary_t){ .valid = true, .feed = { .at = AGO(155), .ml = 200 }, .diaper = { .at = AGO(70), .type = DIAPER_PEE },
                                  .poo = { .at = AGO(290) }, .sleep = { .at = AGO(300), .ended_at = AGO(40) }, .today = { 3, 570 },
                                  .age = { true, 142, 4, 20, true, 3, 28 } };
    ui_build(&fonts, "0.2.1");
    run(1200);
    snprintf(name, sizeof(name), "%s/1-calm", out); save(name);

    /* 2. 급함: 가장 긴 글(기저귀 12시간 35분, 소변 뒤 어제 대변) */
    s_summary.feed.at = AGO(100);
    s_summary.diaper.at = AGO(755);
    s_summary.poo.at = AGO(1500);
    s_summary.sleep = (typeof(s_summary.sleep)){ .at = AGO(700), .ended_at = AGO(659) };
    s_generation++;
    run(1200);
    snprintf(name, sizeof(name), "%s/2-urgent-longest", out); save(name);

    /* 3. 자는 중 + 연결 안 됨 */
    s_summary.diaper.at = AGO(20); s_summary.diaper.type = DIAPER_BOTH;
    s_summary.sleep = (typeof(s_summary.sleep)){ .at = AGO(80) };
    s_generation++;
    s_care = CARE_OFFLINE;
    run(1200);
    snprintf(name, sizeof(name), "%s/3-sleeping-offline", out); save(name);

    /* 4. 먹이는 중(방금), 무선 업데이트 받는 중 */
    s_care = CARE_OK;
    s_summary.sleep.ended_at = AGO(30);
    s_summary.feed = (typeof(s_summary.feed)){ .at = AGO(0), .ml = 230, .feeding = true };
    s_generation++;
    s_ota = 42;
    run(1200);
    snprintf(name, sizeof(name), "%s/4-feeding-ota", out); save(name);
    s_ota = -1;

    /* 5. 아직 요약을 못 받음 */
    s_summary = (care_summary_t){ 0 };
    s_generation++;
    s_care = CARE_STARTING;
    run(1200);
    snprintf(name, sizeof(name), "%s/5-empty", out); save(name);

    /* 6. 설정 */
    s_care = CARE_OK;
    tap(1200, 48);
    run(1200);
    snprintf(name, sizeof(name), "%s/6-settings", out); save(name);

    /* 7. 와이파이 고르기 */
    tap(180, 640);
    run(1200);
    tap(200, 60);
    snprintf(name, sizeof(name), "%s/7-wifi", out); save(name);

    /* 8. 로그인(로그인이 필요하면 대시보드 대신 뜬다) */
    tap(1170, 290);
    s_care = CARE_NEED_LOGIN;
    run(2200);
    snprintf(name, sizeof(name), "%s/8-login", out); save(name);
    return 0;
}
