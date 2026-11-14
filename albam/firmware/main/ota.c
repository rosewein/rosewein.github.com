/* 무선 업데이트: 같은 와이파이에서 새 펌웨어(.bin)를 POST /update 로 받는다.
 * 화면에 나오는 6자리 번호를 X-OTA-Code 머리말로 보내야 받는다. */
#include "ota.h"
#include "care.h"
#include "store.h"

#include <stdio.h>
#include <string.h>
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "esp_app_desc.h"
#include "esp_heap_caps.h"
#include "esp_http_server.h"
#include "esp_log.h"
#include "esp_ota_ops.h"
#include "esp_random.h"
#include "esp_system.h"
#include "esp_timer.h"

static const char *TAG = "ota";

static char s_code[8];
static httpd_handle_t s_server;
static volatile int s_progress = -1;

static const char PAGE[] =
    "<!doctype html><meta charset=utf-8><meta name=viewport content='width=device-width'>"
    "<title>알밤보드</title><body style='font:16px sans-serif;max-width:28em;margin:2em auto;padding:0 1em'>"
    "<h1>알밤보드</h1><p id=v></p>"
    "<p><input type=file id=f accept=.bin></p>"
    "<p><input id=c inputmode=numeric placeholder='화면의 6자리 번호'></p>"
    "<p><button id=b>새 펌웨어 보내기</button></p><p id=s></p>"
    "<script>"
    "fetch('/info').then(r=>r.json()).then(i=>v.textContent='지금 판 '+i.version+' ('+i.built+')');"
    "b.onclick=()=>{const file=f.files[0];if(!file){s.textContent='파일을 고르세요';return}"
    "const x=new XMLHttpRequest();x.open('POST','/update');x.setRequestHeader('X-OTA-Code',c.value.trim());"
    "x.upload.onprogress=e=>s.textContent='보내는 중 '+Math.round(e.loaded/e.total*100)+'%';"
    "x.onload=()=>s.textContent=x.status==200?'끝. 보드가 다시 켜져요.':'실패: '+x.responseText;"
    "x.onerror=()=>s.textContent='연결이 끊겼어요';x.send(file)}"
    "</script>";

static esp_err_t page_get(httpd_req_t *req)
{
    httpd_resp_set_type(req, "text/html; charset=utf-8");
    return httpd_resp_send(req, PAGE, HTTPD_RESP_USE_STRLEN);
}

static esp_err_t info_get(httpd_req_t *req)
{
    const esp_app_desc_t *app = esp_app_get_description();
    const esp_partition_t *running = esp_ota_get_running_partition();
    /* 문제를 찾을 때 브라우저로 볼 값: 켜진 시간, 남은 메모리(안쪽·PSRAM), 서버 읽기 상태 */
    care_diag_t care;
    care_diag(&care);
    for (char *p = care.last_error; *p; p++) {
        if (*p == '"' || *p == '\\' || (unsigned char)*p < 0x20) {
            *p = ' ';
        }
    }
    static char json[900];
    snprintf(json, sizeof(json),
             "{\"name\":\"%s\",\"version\":\"%s\",\"built\":\"%s %s\",\"slot\":\"%s\",\"uptime_s\":%d,"
             "\"heap\":{\"internal_free\":%u,\"internal_min\":%u,\"internal_largest\":%u,\"psram_free\":%u,\"psram_min\":%u},"
             "\"care\":{\"state\":%d,\"ok\":%d,\"fails\":%d,\"fails_in_a_row\":%d,\"seconds_since_ok\":%d,"
             "\"seconds_since_error\":%d,\"last_error\":\"%s\"}}",
             app->project_name, app->version, app->date, app->time, running ? running->label : "?",
             (int)(esp_timer_get_time() / 1000000),
             (unsigned)heap_caps_get_free_size(MALLOC_CAP_INTERNAL), (unsigned)heap_caps_get_minimum_free_size(MALLOC_CAP_INTERNAL),
             (unsigned)heap_caps_get_largest_free_block(MALLOC_CAP_INTERNAL),
             (unsigned)heap_caps_get_free_size(MALLOC_CAP_SPIRAM), (unsigned)heap_caps_get_minimum_free_size(MALLOC_CAP_SPIRAM),
             (int)care_state(), care.ok, care.fails, care.fails_in_a_row, care.seconds_since_ok, care.seconds_since_error, care.last_error);
    httpd_resp_set_type(req, "application/json");
    return httpd_resp_send(req, json, HTTPD_RESP_USE_STRLEN);
}

static esp_err_t fail(httpd_req_t *req, httpd_err_code_t code, const char *message)
{
    s_progress = -1;
    ESP_LOGW(TAG, "%s", message);
    httpd_resp_send_err(req, code, message);
    return ESP_FAIL;
}

static esp_err_t update_post(httpd_req_t *req)
{
    char code[16] = "";
    httpd_req_get_hdr_value_str(req, "X-OTA-Code", code, sizeof(code));
    if (strcmp(code, s_code) != 0) {
        return fail(req, HTTPD_403_FORBIDDEN, "wrong code");
    }
    if (s_progress >= 0) {
        return fail(req, HTTPD_400_BAD_REQUEST, "update already running");
    }

    const esp_partition_t *target = esp_ota_get_next_update_partition(NULL);
    if (!target || req->content_len <= 0 || req->content_len > target->size) {
        return fail(req, HTTPD_400_BAD_REQUEST, "bad size");
    }

    s_progress = 0;
    esp_ota_handle_t handle;
    if (esp_ota_begin(target, OTA_SIZE_UNKNOWN, &handle) != ESP_OK) {
        return fail(req, HTTPD_500_INTERNAL_SERVER_ERROR, "cannot start");
    }

    static char buf[4096];
    int total = req->content_len, done = 0, timeouts = 0;
    while (done < total) {
        int want = total - done < (int)sizeof(buf) ? total - done : (int)sizeof(buf);
        int got = httpd_req_recv(req, buf, want);
        if (got == HTTPD_SOCK_ERR_TIMEOUT && ++timeouts < 5) {
            continue;
        }
        if (got <= 0) {
            esp_ota_abort(handle);
            return fail(req, HTTPD_408_REQ_TIMEOUT, "connection lost");
        }
        timeouts = 0;
        if (esp_ota_write(handle, buf, got) != ESP_OK) {
            esp_ota_abort(handle);
            return fail(req, HTTPD_500_INTERNAL_SERVER_ERROR, "write failed");
        }
        done += got;
        s_progress = (int)((int64_t)done * 100 / total);
    }

    /* 끝에서 파일이 P4용 펌웨어가 맞는지 검사한다 */
    if (esp_ota_end(handle) != ESP_OK) {
        return fail(req, HTTPD_400_BAD_REQUEST, "not a valid firmware file");
    }
    if (esp_ota_set_boot_partition(target) != ESP_OK) {
        return fail(req, HTTPD_500_INTERNAL_SERVER_ERROR, "cannot switch");
    }

    ESP_LOGI(TAG, "새 펌웨어 %d바이트를 %s 에 받음. 다시 켠다.", total, target->label);
    httpd_resp_sendstr(req, "ok");
    vTaskDelay(pdMS_TO_TICKS(1500));
    esp_restart();
    return ESP_OK;
}

void ota_init(void)
{
    if (!store_get("ota_code", s_code, sizeof(s_code))) {
        snprintf(s_code, sizeof(s_code), "%06u", (unsigned)(esp_random() % 1000000));
        store_set("ota_code", s_code);
    }
}

const char *ota_code(void)
{
    return s_code;
}

void ota_start_server(void)
{
    if (s_server) {
        return;
    }
    httpd_config_t config = HTTPD_DEFAULT_CONFIG();
    config.stack_size = 8192;
    config.recv_wait_timeout = 10;
    if (httpd_start(&s_server, &config) != ESP_OK) {
        ESP_LOGE(TAG, "서버를 못 켬");
        s_server = NULL;
        return;
    }
    static const httpd_uri_t page = { .uri = "/", .method = HTTP_GET, .handler = page_get };
    static const httpd_uri_t info = { .uri = "/info", .method = HTTP_GET, .handler = info_get };
    static const httpd_uri_t update = { .uri = "/update", .method = HTTP_POST, .handler = update_post };
    httpd_register_uri_handler(s_server, &page);
    httpd_register_uri_handler(s_server, &info);
    httpd_register_uri_handler(s_server, &update);
}

void ota_set_progress(int percent)
{
    s_progress = percent;
}

int ota_progress(void)
{
    return s_progress;
}
