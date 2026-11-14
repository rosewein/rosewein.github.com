/* 화면 네 개: 대시보드(첫 화면), 설정, 와이파이 고르기, 로그인.
 * LVGL 과 우리 모듈(net·care·ota)만 쓴다. 보드 쪽 일(화면 켜기·글꼴 읽기)은 board.c 가 맡는다.
 * 그래서 PC 미리 보기(sim/)에서도 같은 코드를 그려 볼 수 있다.
 * 여기 함수는 모두 LVGL 작업 안(타이머·터치)에서 돈다. 다른 작업의 상태는 1초마다 읽어 온다. */
#include "ui.h"
#include "care.h"
#include "care_text.h"
#include "net.h"
#include "ota.h"
#include "update.h"

#include <stdio.h>
#include <string.h>
#include <time.h>
#include "lvgl.h"

#define W 1280
#define H 720
#define MAX_APS 20
#define FRAME_MS 600          /* 알밤 두 칸 애니메이션(sprites.json frame_ms) */
#define SPRITE_SCALE 7        /* 32px 그림을 7배로 */

/* 웹앱의 어두운 화면 색(styles/app.css) */
#define C_BG 0x0b0908
#define C_PANEL 0x15100d
#define C_LINE 0x3b2c21
#define C_TEXT 0xe6d8c0
#define C_STRONG 0xf6ead3     /* 수치(값)는 가장 밝게 */
#define C_DIM 0x94866f        /* 이름표는 흐리게 */
#define C_ACCENT 0xe9a253
#define C_WARN 0xff8a65       /* 급한 항목 */
#define C_BTN 0x2a1f17

extern const lv_image_dsc_t *const albam_sprites[4][2];   /* assets/sprites.c: [표정][칸] */

static ui_fonts_t F;
static const char *s_version = "";

/* 지난 시간 한 줄: 앞말(작게) + 숫자(크게) + 단위(작게). 조각 다섯 개를 만들어 두고 글만 바꾼다 */
typedef struct {
    lv_obj_t *group;
    lv_span_t *prefix, *num[2], *unit[2];
    char key[96];
} ago_line_t;

typedef struct {
    lv_obj_t *box, *title, *detail;
    ago_line_t ago;
} card_t;

static lv_obj_t *s_home, *s_age, *s_total, *s_today, *s_clock, *s_status, *s_sprite, *s_words, *s_label, *s_bar;
static ago_line_t s_bubble_ago;
static card_t s_feed, s_diaper, s_sleep;
static care_mood_t s_mood;
static int s_frame;

static lv_obj_t *s_settings, *s_info;
static lv_obj_t *s_wifi, *s_list, *s_ssid, *s_pass, *s_wifi_msg;
static lv_obj_t *s_login, *s_email, *s_login_pass, *s_login_msg, *s_login_keyboard;
static net_ap_t s_aps[MAX_APS];
static bool s_waiting_scan, s_joining, s_logging_in;

/* ---- 조각 ---- */

static void set_text(lv_obj_t *label, const char *text)
{
    if (strcmp(lv_label_get_text(label), text) != 0) {
        lv_label_set_text(label, text);
    }
}

static lv_obj_t *label(lv_obj_t *parent, const lv_font_t *font, uint32_t color, const char *text)
{
    lv_obj_t *l = lv_label_create(parent);
    lv_obj_set_style_text_font(l, font, 0);
    lv_obj_set_style_text_color(l, lv_color_hex(color), 0);
    lv_label_set_text(l, text);
    return l;
}

static lv_obj_t *button(lv_obj_t *parent, const char *text, lv_event_cb_t cb, int w, int h)
{
    lv_obj_t *b = lv_button_create(parent);
    lv_obj_set_size(b, w, h);
    lv_obj_set_style_bg_color(b, lv_color_hex(C_BTN), 0);
    lv_obj_set_style_border_color(b, lv_color_hex(C_LINE), 0);
    lv_obj_set_style_border_width(b, 2, 0);
    lv_obj_set_style_shadow_width(b, 0, 0);
    lv_obj_add_event_cb(b, cb, LV_EVENT_CLICKED, NULL);
    lv_obj_t *l = label(b, F.text, C_TEXT, text);
    lv_obj_center(l);
    return b;
}

static lv_obj_t *screen(void)
{
    lv_obj_t *s = lv_obj_create(NULL);
    lv_obj_set_style_bg_color(s, lv_color_hex(C_BG), 0);
    lv_obj_remove_flag(s, LV_OBJ_FLAG_SCROLLABLE);
    return s;
}

static lv_obj_t *panel(lv_obj_t *parent, int x, int y, int w, int h)
{
    lv_obj_t *p = lv_obj_create(parent);
    lv_obj_set_pos(p, x, y);
    lv_obj_set_size(p, w, h);
    lv_obj_set_style_bg_color(p, lv_color_hex(C_PANEL), 0);
    lv_obj_set_style_border_color(p, lv_color_hex(C_LINE), 0);
    lv_obj_set_style_border_width(p, 3, 0);
    lv_obj_set_style_radius(p, 18, 0);
    lv_obj_set_style_pad_all(p, 0, 0);
    lv_obj_remove_flag(p, LV_OBJ_FLAG_SCROLLABLE);
    return p;
}

static lv_obj_t *textarea(lv_obj_t *parent, const char *placeholder, int x, int y, int w)
{
    lv_obj_t *t = lv_textarea_create(parent);
    lv_textarea_set_one_line(t, true);
    lv_textarea_set_max_length(t, 64);
    lv_textarea_set_placeholder_text(t, placeholder);
    lv_obj_set_style_text_font(t, F.text, 0);
    lv_obj_set_pos(t, x, y);
    lv_obj_set_size(t, w, 62);
    return t;
}

static void ago_line_create(ago_line_t *line, lv_obj_t *parent, const lv_font_t *num, const lv_font_t *unit, const lv_font_t *prefix)
{
    line->group = lv_spangroup_create(parent);
    lv_spangroup_set_mode(line->group, LV_SPAN_MODE_EXPAND);
    lv_obj_set_style_text_color(line->group, lv_color_hex(C_TEXT), 0);
    lv_obj_set_style_text_font(line->group, unit, 0);
    line->prefix = lv_spangroup_add_span(line->group);
    lv_style_set_text_font(lv_span_get_style(line->prefix), prefix);
    lv_style_set_text_color(lv_span_get_style(line->prefix), lv_color_hex(C_DIM));
    for (int i = 0; i < 2; i++) {
        line->num[i] = lv_spangroup_add_span(line->group);
        lv_style_set_text_font(lv_span_get_style(line->num[i]), num);
        line->unit[i] = lv_spangroup_add_span(line->group);
        lv_style_set_text_font(lv_span_get_style(line->unit[i]), unit);
    }
    line->key[0] = '\0';
}

/* "먹은 지 2시간 35분", "12분째", "방금", "—". 급하면 숫자와 단위가 빨강 */
static void ago_line_set(ago_line_t *line, const char *prefix, care_ago_t ago, bool ongoing, bool urgent)
{
    char key[96], whole[48];
    care_ago_text(ago, ongoing, whole, sizeof(whole));
    snprintf(key, sizeof(key), "%s|%s|%d", prefix, whole, urgent);
    if (strcmp(key, line->key) == 0) {
        return;
    }
    snprintf(line->key, sizeof(line->key), "%s", key);

    char texts[5][48] = { "", "", "", "", "" };   /* 앞말, 숫자1, 단위1, 숫자2, 단위2 */
    const char *tail = ongoing ? "째" : "";
    if (!ago.has || (!ago.hours && !ago.minutes)) {
        snprintf(texts[1], sizeof(texts[1]), "%s", whole);   /* "—", "방금" 은 통째로 크게 */
    } else {
        if (prefix[0]) {
            snprintf(texts[0], sizeof(texts[0]), "%s ", prefix);
        }
        if (ago.hours) {
            snprintf(texts[1], sizeof(texts[1]), "%d", ago.hours);
            snprintf(texts[2], sizeof(texts[2]), "시간%s", ago.minutes ? " " : tail);
        }
        if (ago.minutes) {
            int at = ago.hours ? 3 : 1;
            snprintf(texts[at], sizeof(texts[at]), "%d", ago.minutes);
            snprintf(texts[at + 1], sizeof(texts[at + 1]), "분%s", tail);
        }
    }
    lv_span_set_text(line->prefix, texts[0]);
    for (int i = 0; i < 2; i++) {
        lv_span_set_text(line->num[i], texts[1 + i * 2]);
        lv_span_set_text(line->unit[i], texts[2 + i * 2]);
        lv_style_set_text_color(lv_span_get_style(line->num[i]), lv_color_hex(urgent ? C_WARN : C_STRONG));
        lv_style_set_text_color(lv_span_get_style(line->unit[i]), lv_color_hex(urgent ? C_WARN : C_TEXT));
    }
    lv_spangroup_refresh(line->group);
}

/* ---- 대시보드 ---- */

static void card_create(card_t *card, lv_obj_t *parent, int x)
{
    card->box = panel(parent, x, 424, 400, 276);
    card->title = label(card->box, F.text, C_DIM, "");
    lv_obj_align(card->title, LV_ALIGN_TOP_LEFT, 24, 18);
    ago_line_create(&card->ago, card->box, F.big, F.title, F.title);
    lv_obj_align(card->ago.group, LV_ALIGN_LEFT_MID, 24, 4);
    card->detail = label(card->box, F.text, C_TEXT, "");
    lv_obj_align(card->detail, LV_ALIGN_BOTTOM_LEFT, 24, -18);
}

static void card_set(card_t *card, const care_card_t *view)
{
    set_text(card->title, view->title);
    set_text(card->detail, view->detail);
    ago_line_set(&card->ago, "", view->ago, view->ongoing, view->urgent);
    lv_obj_set_style_border_color(card->box, lv_color_hex(view->urgent ? C_WARN : C_LINE), 0);
}

static void open_settings(lv_event_t *e);

static void build_home(void)
{
    s_home = screen();

    /* 맨 위 줄: 나이 · 오늘 합계 / 오늘 날짜, 지금 시각, 설정 */
    s_age = label(s_home, F.small, C_DIM, "");
    lv_obj_set_pos(s_age, 28, 20);
    s_total = label(s_home, F.small, C_TEXT, "");
    lv_obj_set_pos(s_total, 28, 58);
    lv_obj_t *gear = button(s_home, "설정", open_settings, 110, 64);
    lv_obj_align(gear, LV_ALIGN_TOP_RIGHT, -24, 16);
    s_clock = label(s_home, F.title, C_STRONG, "--:--");
    lv_obj_align(s_clock, LV_ALIGN_TOP_RIGHT, -156, 22);
    s_today = label(s_home, F.small, C_DIM, "");
    lv_obj_align(s_today, LV_ALIGN_TOP_RIGHT, -290, 34);
    s_status = label(s_home, F.small, C_WARN, "");
    lv_obj_align(s_status, LV_ALIGN_TOP_RIGHT, -156, 70);

    /* 가운데: 알밤 + 말풍선(문구 / 지난 시간 / 무엇의 시간인지) */
    s_sprite = lv_image_create(s_home);
    lv_image_set_src(s_sprite, albam_sprites[MOOD_NORMAL][0]);
    lv_image_set_antialias(s_sprite, false);       /* 도트 그림은 또렷하게 */
    lv_image_set_scale(s_sprite, 256 * SPRITE_SCALE);
    lv_obj_set_pos(s_sprite, 28 + (32 * SPRITE_SCALE - 32) / 2, 130 + (32 * SPRITE_SCALE - 32) / 2);

    lv_obj_t *bubble = panel(s_home, 290, 104, 962, 300);
    s_words = label(bubble, F.title, C_ACCENT, "");
    lv_obj_align(s_words, LV_ALIGN_TOP_LEFT, 32, 20);
    ago_line_create(&s_bubble_ago, bubble, F.huge, F.big, F.title);
    lv_obj_align(s_bubble_ago.group, LV_ALIGN_LEFT_MID, 32, 6);
    s_label = label(bubble, F.text, C_DIM, "");
    lv_obj_align(s_label, LV_ALIGN_BOTTOM_LEFT, 32, -20);

    /* 아래: 수유 · 기저귀 · 잠 */
    card_create(&s_feed, s_home, 28);
    card_create(&s_diaper, s_home, 440);
    card_create(&s_sleep, s_home, 852);

    /* 새 펌웨어를 받는 동안만 보이는 막대 */
    s_bar = lv_bar_create(s_home);
    lv_obj_set_size(s_bar, W, 10);
    lv_obj_set_pos(s_bar, 0, 0);
    lv_bar_set_range(s_bar, 0, 100);
    lv_obj_add_flag(s_bar, LV_OBJ_FLAG_HIDDEN);
}

static void update_home(const net_status_t *net, care_state_t care)
{
    static care_summary_t summary;
    static uint32_t seen;
    care_copy_summary(&summary, &seen);

    care_view_t v;
    care_build_view(&summary, time(NULL), &v);

    if (net_time_synced()) {
        set_text(s_clock, v.clock);
        set_text(s_today, v.today);
    }
    set_text(s_age, v.age);
    set_text(s_total, v.total);
    set_text(s_words, v.words);
    set_text(s_label, v.label);
    ago_line_set(&s_bubble_ago, v.prefix, v.ago, false, v.urgent);
    lv_obj_set_style_text_color(s_words, lv_color_hex(v.urgent ? C_WARN : C_ACCENT), 0);
    card_set(&s_feed, &v.feed);
    card_set(&s_diaper, &v.diaper);
    card_set(&s_sleep, &v.sleep);
    s_mood = v.mood;

    char status[64] = "";
    int progress = ota_progress();
    if (progress >= 0) {
        snprintf(status, sizeof(status), "새 펌웨어 받는 중 %d%%", progress);
        lv_obj_remove_flag(s_bar, LV_OBJ_FLAG_HIDDEN);
        lv_bar_set_value(s_bar, progress, LV_ANIM_OFF);
    } else {
        lv_obj_add_flag(s_bar, LV_OBJ_FLAG_HIDDEN);
        if (net->state != NET_CONNECTED) {
            snprintf(status, sizeof(status), net->state == NET_CONNECTING ? "와이파이 연결 중" : "와이파이 없음");
        } else if (care == CARE_OFFLINE) {
            snprintf(status, sizeof(status), "연결 안 됨");
        } else if (care != CARE_OK && care != CARE_STARTING) {
            snprintf(status, sizeof(status), "로그인 필요");
        }
    }
    set_text(s_status, status);
}

static void animate(lv_timer_t *timer)
{
    s_frame ^= 1;
    lv_image_set_src(s_sprite, albam_sprites[s_mood][s_frame]);
}

/* ---- 와이파이 고르기 ---- */

static void scan(void)
{
    lv_obj_clean(s_list);
    set_text(s_wifi_msg, "찾는 중…");
    s_waiting_scan = true;
    net_scan_start();
}

static void ap_clicked(lv_event_t *e)
{
    net_ap_t *ap = lv_event_get_user_data(e);
    lv_label_set_text(s_ssid, ap->ssid);
    lv_textarea_set_text(s_pass, "");
    set_text(s_wifi_msg, ap->open ? "비밀번호 없는 와이파이예요. [연결]을 누르세요" : "비밀번호를 넣으세요");
}

static void fill_list(int count)
{
    lv_obj_clean(s_list);
    for (int i = 0; i < count; i++) {
        lv_obj_t *b = lv_list_add_button(s_list, LV_SYMBOL_WIFI, s_aps[i].ssid);
        lv_obj_set_style_text_font(b, F.small, 0);
        lv_obj_add_event_cb(b, ap_clicked, LV_EVENT_CLICKED, &s_aps[i]);
    }
    set_text(s_wifi_msg, count ? "와이파이를 고르세요" : "찾은 와이파이가 없어요");
}

static void join(lv_event_t *e)
{
    const char *ssid = lv_label_get_text(s_ssid);
    if (ssid[0] == '\0') {
        set_text(s_wifi_msg, "먼저 와이파이를 고르세요");
        return;
    }
    net_connect(ssid, lv_textarea_get_text(s_pass));
    s_joining = true;
    set_text(s_wifi_msg, "연결 중…");
}

static void rescan_clicked(lv_event_t *e)
{
    scan();
}

static void back_home(lv_event_t *e)
{
    lv_screen_load(s_home);
}

static void open_wifi(lv_event_t *e)
{
    s_joining = false;
    lv_label_set_text(s_ssid, "");
    lv_textarea_set_text(s_pass, "");
    lv_screen_load(s_wifi);
    scan();
}

static void build_wifi(void)
{
    s_wifi = screen();

    /* 왼쪽: 찾은 와이파이 */
    s_list = lv_list_create(s_wifi);
    lv_obj_set_size(s_list, 480, 316);
    lv_obj_set_pos(s_list, 12, 12);

    /* 오른쪽: 고른 이름, 비밀번호, 버튼 */
    s_ssid = label(s_wifi, F.title, C_STRONG, "");
    lv_obj_set_pos(s_ssid, 512, 12);
    lv_obj_set_width(s_ssid, 750);
    lv_label_set_long_mode(s_ssid, LV_LABEL_LONG_MODE_DOTS);
    s_pass = textarea(s_wifi, "비밀번호", 512, 76, 750);
    s_wifi_msg = label(s_wifi, F.text, C_ACCENT, "");
    lv_obj_set_pos(s_wifi_msg, 512, 156);
    lv_obj_set_width(s_wifi_msg, 750);

    lv_obj_set_pos(button(s_wifi, "다시 찾기", rescan_clicked, 200, 68), 512, 256);
    lv_obj_set_pos(button(s_wifi, "연결", join, 200, 68), 732, 256);
    lv_obj_set_pos(button(s_wifi, "닫기", back_home, 180, 68), 1082, 256);

    /* 아래: 글자판. 체크 키는 [연결]과 같다 */
    lv_obj_t *keyboard = lv_keyboard_create(s_wifi);
    lv_obj_set_size(keyboard, W, 380);
    lv_obj_align(keyboard, LV_ALIGN_BOTTOM_MID, 0, 0);
    lv_keyboard_set_textarea(keyboard, s_pass);
    lv_obj_add_event_cb(keyboard, join, LV_EVENT_READY, NULL);
}

/* ---- 로그인 ---- */

static void login(lv_event_t *e)
{
    const char *email = lv_textarea_get_text(s_email);
    const char *password = lv_textarea_get_text(s_login_pass);
    if (!email[0] || !password[0]) {
        set_text(s_login_msg, "이메일과 비밀번호를 넣으세요");
        return;
    }
    care_login(email, password);
    s_logging_in = true;
    set_text(s_login_msg, "로그인 중…");
}

/* 누른 칸에 글자판을 붙인다 */
static void field_focused(lv_event_t *e)
{
    lv_keyboard_set_textarea(s_login_keyboard, lv_event_get_target(e));
}

/* 체크 키: 이메일 칸에서는 비밀번호 칸으로, 비밀번호 칸에서는 로그인 */
static void login_keyboard_ready(lv_event_t *e)
{
    if (lv_keyboard_get_textarea(s_login_keyboard) == s_email) {
        lv_keyboard_set_textarea(s_login_keyboard, s_login_pass);
        lv_obj_add_state(s_login_pass, LV_STATE_FOCUSED);
        lv_obj_remove_state(s_email, LV_STATE_FOCUSED);
    } else {
        login(e);
    }
}

static void open_login(void)
{
    lv_textarea_set_text(s_login_pass, "");
    lv_screen_load(s_login);
}

static void build_login(void)
{
    s_login = screen();
    lv_obj_set_pos(label(s_login, F.title, C_STRONG, "가족 계정으로 로그인"), 28, 20);
    lv_obj_set_pos(label(s_login, F.small, C_DIM, "알밤보드 앱에 로그인하는 이메일과 비밀번호예요. 비밀번호는 보드에 남기지 않아요."), 28, 84);

    s_email = textarea(s_login, "이메일", 28, 136, 600);
    s_login_pass = textarea(s_login, "비밀번호", 648, 136, 380);
    lv_textarea_set_password_mode(s_login_pass, true);
    lv_obj_add_event_cb(s_email, field_focused, LV_EVENT_FOCUSED, NULL);
    lv_obj_add_event_cb(s_login_pass, field_focused, LV_EVENT_FOCUSED, NULL);
    lv_obj_set_pos(button(s_login, "로그인", login, 200, 68), 1052, 132);

    s_login_msg = label(s_login, F.text, C_ACCENT, "");
    lv_obj_set_pos(s_login_msg, 28, 224);
    lv_obj_set_pos(button(s_login, "와이파이", open_wifi, 200, 68), 1052, 240);

    s_login_keyboard = lv_keyboard_create(s_login);
    lv_obj_set_size(s_login_keyboard, W, 380);
    lv_obj_align(s_login_keyboard, LV_ALIGN_BOTTOM_MID, 0, 0);
    lv_keyboard_set_textarea(s_login_keyboard, s_email);
    lv_obj_add_event_cb(s_login_keyboard, login_keyboard_ready, LV_EVENT_READY, NULL);
}

/* ---- 설정 ---- */

static void logout_clicked(lv_event_t *e)
{
    care_logout();
    open_login();
}

static void update_info(const net_status_t *net)
{
    char text[700], server[280];
    const char *email = care_email();
    care_diag_t diag;
    care_diag(&diag);
    if (diag.seconds_since_error < 0) {
        snprintf(server, sizeof(server), "읽음 %d번, 못 읽은 적 없음", diag.ok);
    } else {
        snprintf(server, sizeof(server), "읽음 %d번, 못 읽음 %d번 · 마지막 %d분 전: %.120s",
                 diag.ok, diag.fails, diag.seconds_since_error / 60, diag.last_error);
    }
    char update[96];
    update_status(update, sizeof(update));
    snprintf(text, sizeof(text), "계정  %s\n와이파이  %s\n주소  %s%s%s\n서버  %s\n펌웨어  v%s · %s\n무선 업데이트 번호  %s",
             email[0] ? email : "로그인 안 됨",
             net->state == NET_CONNECTED ? net->ssid : "연결 안 됨",
             net->ip[0] ? "http://" : "—", net->ip, net->ip[0] ? "/  ·  http://albam-board.local/" : "",
             server, s_version, update, ota_code());
    set_text(s_info, text);
}

static void open_settings(lv_event_t *e)
{
    net_status_t net;
    net_get_status(&net);
    update_info(&net);
    lv_screen_load(s_settings);
}

static void brightness_changed(lv_event_t *e)
{
    ui_brightness_set(lv_slider_get_value(lv_event_get_target(e)));
}

static void dev_changed(lv_event_t *e)
{
    update_dev_set(lv_obj_has_state(lv_event_get_target(e), LV_STATE_CHECKED));
}

static void check_update_clicked(lv_event_t *e)
{
    update_check_now();
}

static void build_settings(void)
{
    s_settings = screen();
    lv_obj_set_pos(label(s_settings, F.title, C_STRONG, "설정"), 28, 20);
    s_info = label(s_settings, F.text, C_TEXT, "");
    lv_obj_set_pos(s_info, 28, 96);
    lv_obj_set_width(s_info, W - 56);
    lv_label_set_long_mode(s_info, LV_LABEL_LONG_MODE_DOTS);
    lv_obj_set_style_text_line_space(s_info, 16, 0);

    /* 밝기: 손을 떼면 저장된다 */
    lv_obj_set_pos(label(s_settings, F.text, C_TEXT, "밝기"), 28, 492);
    lv_obj_t *slider = lv_slider_create(s_settings);
    lv_obj_set_pos(slider, 130, 500);
    lv_obj_set_size(slider, 640, 24);
    lv_slider_set_range(slider, 5, 100);
    lv_slider_set_value(slider, ui_brightness_get(), LV_ANIM_OFF);
    lv_obj_add_event_cb(slider, brightness_changed, LV_EVENT_VALUE_CHANGED, NULL);

    /* 시험판: master 에 합치기 전 브랜치에서 빌드한 펌웨어도 받는다 */
    lv_obj_set_pos(label(s_settings, F.text, C_TEXT, "시험판 받기"), 900, 492);
    lv_obj_t *dev = lv_switch_create(s_settings);
    lv_obj_set_pos(dev, 1090, 490);
    lv_obj_set_size(dev, 90, 46);
    if (update_dev_get()) {
        lv_obj_add_state(dev, LV_STATE_CHECKED);
    }
    lv_obj_add_event_cb(dev, dev_changed, LV_EVENT_VALUE_CHANGED, NULL);

    lv_obj_set_pos(button(s_settings, "와이파이 바꾸기", open_wifi, 320, 84), 28, 600);
    lv_obj_set_pos(button(s_settings, "로그아웃", logout_clicked, 200, 84), 368, 600);
    lv_obj_set_pos(button(s_settings, "업데이트 확인", check_update_clicked, 280, 84), 588, 600);
    lv_obj_set_pos(button(s_settings, "닫기", back_home, 200, 84), 1052, 600);
}

/* ---- 1초마다: 화면 고치기, 화면 옮기기 ---- */

static void tick(lv_timer_t *timer)
{
    net_status_t net;
    net_get_status(&net);
    care_state_t care = care_state();
    lv_obj_t *now = lv_screen_active();

    update_home(&net, care);
    if (now == s_settings) {
        update_info(&net);
    }

    /* 새 펌웨어를 받는 동안에는 대시보드에서 진행을 보여 준다 */
    if (ota_progress() >= 0 && now != s_home) {
        lv_screen_load(s_home);
        return;
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
        set_text(s_wifi_msg, "연결하지 못했어요. 비밀번호를 확인하세요");
    }

    /* 로그인이 필요하면 대시보드 대신 로그인 화면 */
    bool need_login = care == CARE_NEED_LOGIN || care == CARE_LOGIN_FAILED || care == CARE_NOT_FAMILY || care == CARE_LOGIN_OFFLINE;
    if (s_logging_in && care != CARE_LOGGING_IN) {
        s_logging_in = false;
        if (care == CARE_LOGIN_FAILED) {
            set_text(s_login_msg, "이메일이나 비밀번호가 달라요");
        } else if (care == CARE_NOT_FAMILY) {
            set_text(s_login_msg, "이 계정은 가족 명단에 없어요");
        } else if (care == CARE_LOGIN_OFFLINE) {
            set_text(s_login_msg, "서버에 연결하지 못했어요. 잠시 뒤 다시 해 보세요");
        } else if (!need_login) {
            set_text(s_login_msg, "");
            lv_screen_load(s_home);
        }
    }
    if (need_login && lv_screen_active() == s_home && net.state == NET_CONNECTED) {
        if (care == CARE_NOT_FAMILY) {
            set_text(s_login_msg, "이 계정은 가족 명단에 없어요");
        }
        open_login();
    }
}

void ui_build(const ui_fonts_t *fonts, const char *version)
{
    F = *fonts;
    s_version = version;

    /* 어두운 바탕. 글자판의 글자·그림 글자는 LVGL 기본 글꼴(28)로 */
    lv_display_t *display = lv_display_get_default();
    lv_display_set_theme(display, lv_theme_default_init(display, lv_color_hex(C_ACCENT), lv_color_hex(C_DIM), true, &lv_font_montserrat_28));

    build_home();
    build_settings();
    build_wifi();
    build_login();
    lv_screen_load(s_home);

    net_status_t net;
    net_get_status(&net);
    if (net.state == NET_NO_WIFI) {
        open_wifi(NULL);
    }
    lv_timer_create(tick, 1000, NULL);
    lv_timer_create(animate, FRAME_MS, NULL);
    tick(NULL);
}
