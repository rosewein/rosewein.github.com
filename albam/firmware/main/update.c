#include "update.h"
#include "net.h"
#include "ota.h"
#include "store.h"

#include <stdio.h>
#include <string.h>
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "esp_app_desc.h"
#include "esp_crt_bundle.h"
#include "esp_http_client.h"
#include "esp_https_ota.h"
#include "esp_log.h"
#include "esp_system.h"
#include "sdkconfig.h"

#define FIRST_CHECK_SECONDS 60
#define CHECK_SECONDS 600

static const char *TAG = "update";

static TaskHandle_t s_task;
static volatile bool s_dev;
static char s_status[96] = "아직 확인 안 함";
static char s_bad[40];          /* 받아 봤는데 못 켜져서 되돌아온 판. 다시 받지 않는다 */

static void set_status(const char *text)
{
    strlcpy(s_status, text, sizeof(s_status));   /* 짧은 글이라 잠금 없이 바꾼다 */
}

/* 깃허브 릴리스 파일은 긴 주소로 한 번 넘겨 준다(redirect). 머리말 버퍼가 넉넉해야 따라간다 */
static void fill_config(esp_http_client_config_t *config, const char *url)
{
    config->url = url;
    config->crt_bundle_attach = esp_crt_bundle_attach;
    config->timeout_ms = 15000;
    config->buffer_size = 4096;
    config->buffer_size_tx = 4096;
    config->max_redirection_count = 5;
    config->keep_alive_enable = true;
}

static void release_url(const char *file, char *out, size_t len)
{
    snprintf(out, len, "https://github.com/%s/releases/download/%s/%s", CONFIG_ALBAM_UPDATE_REPO,
             s_dev ? "albam-firmware-dev" : "albam-firmware", file);
}

typedef struct { char text[48]; size_t size; } small_text_t;

static esp_err_t collect(esp_http_client_event_t *event)
{
    small_text_t *got = event->user_data;
    if (event->event_id == HTTP_EVENT_ON_DATA && esp_http_client_get_status_code(event->client) == 200) {
        size_t room = sizeof(got->text) - 1 - got->size;
        size_t n = event->data_len < room ? event->data_len : room;
        memcpy(got->text + got->size, event->data, n);
        got->size += n;
    }
    return ESP_OK;
}

/* 릴리스의 version.txt. 못 읽으면 false */
static bool remote_version(char *out, size_t len)
{
    char url[200];
    small_text_t got = { 0 };
    release_url("version.txt", url, sizeof(url));
    esp_http_client_config_t config = { .event_handler = collect, .user_data = &got };
    fill_config(&config, url);
    esp_http_client_handle_t client = esp_http_client_init(&config);
    if (!client) {
        return false;
    }
    bool ok = esp_http_client_perform(client) == ESP_OK && esp_http_client_get_status_code(client) == 200;
    esp_http_client_cleanup(client);
    while (got.size && (got.text[got.size - 1] == '\n' || got.text[got.size - 1] == '\r' || got.text[got.size - 1] == ' ')) {
        got.size--;
    }
    got.text[got.size] = '\0';
    strlcpy(out, got.text, len);
    return ok && got.size > 0;
}

static bool download(const char *version)
{
    char url[200];
    release_url("albam_board.bin", url, sizeof(url));
    esp_http_client_config_t http = { 0 };
    fill_config(&http, url);
    esp_https_ota_config_t config = { .http_config = &http };
    esp_https_ota_handle_t handle;
    if (esp_https_ota_begin(&config, &handle) != ESP_OK) {
        return false;
    }
    ota_set_progress(0);
    esp_err_t err;
    while ((err = esp_https_ota_perform(handle)) == ESP_ERR_HTTPS_OTA_IN_PROGRESS) {
        int total = esp_https_ota_get_image_size(handle);
        if (total > 0) {
            ota_set_progress((int)((int64_t)esp_https_ota_get_image_len_read(handle) * 100 / total));
        }
    }
    bool ok = err == ESP_OK && esp_https_ota_is_complete_data_received(handle);
    if (ok) {
        ok = esp_https_ota_finish(handle) == ESP_OK;   /* 여기서 P4용 펌웨어가 맞는지 검사하고 다음에 켤 칸으로 정한다 */
    } else {
        esp_https_ota_abort(handle);
    }
    ota_set_progress(-1);
    if (ok) {
        store_set("ota_try", version);   /* 다음에 켜졌을 때 이 판이 아니면 실패한 것 */
    }
    return ok;
}

static void check(void)
{
    const char *running = esp_app_get_description()->version;
    char remote[40], text[96];
    net_status_t net;
    net_get_status(&net);
    if (net.state != NET_CONNECTED || ota_progress() >= 0) {
        return;
    }
    if (!remote_version(remote, sizeof(remote))) {
        set_status(s_dev ? "확인 못 함(시험판)" : "확인 못 함(정식판이 아직 없을 수 있어요)");
        return;
    }
    if (strcmp(remote, running) == 0) {
        set_status("최신 판이에요");
        return;
    }
    if (strcmp(remote, s_bad) == 0) {
        snprintf(text, sizeof(text), "v%s 는 켜지지 않아 건너뜀", remote);
        set_status(text);
        return;
    }
    snprintf(text, sizeof(text), "v%s 받는 중", remote);
    set_status(text);
    ESP_LOGI(TAG, "%s → %s", running, remote);
    if (download(remote)) {
        vTaskDelay(pdMS_TO_TICKS(1000));
        esp_restart();
    }
    set_status("받다가 끊김. 다음에 다시");
}

static void update_task(void *arg)
{
    ulTaskNotifyTake(pdTRUE, pdMS_TO_TICKS(FIRST_CHECK_SECONDS * 1000));
    for (;;) {
        check();
        ulTaskNotifyTake(pdTRUE, pdMS_TO_TICKS(CHECK_SECONDS * 1000));
    }
}

void update_start(void)
{
    /* 지난번에 받은 판이 지금 켜진 판이 아니면, 그 판은 못 켜져서 되돌아온 것이다 */
    char tried[40], channel[8];
    if (store_get("ota_try", tried, sizeof(tried))) {
        if (strcmp(tried, esp_app_get_description()->version) != 0) {
            store_set("ota_bad", tried);
        }
        store_set("ota_try", "");
    }
    store_get("ota_bad", s_bad, sizeof(s_bad));
    s_dev = store_get("channel", channel, sizeof(channel)) ? strcmp(channel, "dev") == 0 : true;
    xTaskCreate(update_task, "update", 10240, NULL, 3, &s_task);
}

void update_check_now(void)
{
    set_status("확인 중…");
    xTaskNotifyGive(s_task);
}

void update_status(char *out, size_t len)
{
    strlcpy(out, s_status, len);
}

bool update_dev_get(void)
{
    return s_dev;
}

void update_dev_set(bool dev)
{
    s_dev = dev;
    store_set("channel", dev ? "dev" : "stable");
    update_check_now();
}
