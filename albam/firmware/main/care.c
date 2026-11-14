/* 알밤보드 서버(Supabase)에 로그인하고 20초마다 요약을 읽어 온다.
 * 웹앱 src/api/supabase-rest.js 와 같은 HTTP 호출이다:
 *   로그인      POST /auth/v1/token?grant_type=password       { email, password }
 *   토큰 갱신   POST /auth/v1/token?grant_type=refresh_token  { refresh_token }
 *   요약        POST /rest/v1/rpc/care_summary                 {}
 * 머리말은 apikey 와 Authorization: Bearer. 비밀번호는 저장하지 않고 갱신 토큰만 보드에 남긴다. */
#include "care.h"
#include "net.h"
#include "store.h"

#include <stdlib.h>
#include <string.h>
#include "freertos/FreeRTOS.h"
#include "freertos/semphr.h"
#include "freertos/task.h"
#include "cJSON.h"
#include "esp_crt_bundle.h"
#include "esp_http_client.h"
#include "esp_log.h"
#include "esp_timer.h"
#include "sdkconfig.h"

#define POLL_SECONDS 20          /* 다른 기기 기록을 다시 읽는 주기(웹앱 pollSeconds) */
#define REFRESH_MARGIN 120       /* 만료 2분 전이면 미리 갱신 */
#define RETRY_SECONDS 5          /* 못 읽었으면 조금 뒤 다시 */
#define OFFLINE_AFTER 3          /* 이만큼 잇달아 못 읽어야 "연결 안 됨"(한 번 끊긴 것으로는 안 띄운다) */
#define TIMEOUT_MS 10000
#define MAX_RESPONSE (512 * 1024)

/* post() 가 주는 값 */
#define RESULT_OK 0
#define RESULT_AUTH 1            /* 로그인이 틀렸거나 끝났다 */
#define RESULT_NETWORK 2         /* 못 닿았다(나중에 다시) */
#define RESULT_OTHER 3

static const char *TAG = "care";

static SemaphoreHandle_t s_lock;
static TaskHandle_t s_task;
static care_state_t s_state = CARE_STARTING;
static care_summary_t s_summary;
static uint32_t s_generation = 1;
static char s_email[96];

/* 아래는 care 작업만 만진다 */
static char s_refresh[512];
static char *s_access;
static int64_t s_expires;        /* 켠 뒤 지난 초 기준 */
static char s_message[160];      /* 마지막 오류 글 */

/* 문제를 찾을 때 보는 값(/info 와 설정 화면) */
static int s_fails, s_total_fails, s_total_ok;
static char s_last_error[200];
static int64_t s_last_error_at, s_last_ok_at;

/* 화면이 넣어 둔 로그인 요청 */
static bool s_want_login, s_want_logout;
static char s_login_email[96], s_login_password[96];

static int64_t uptime(void)
{
    return esp_timer_get_time() / 1000000;
}

static void set_state(care_state_t state)
{
    xSemaphoreTake(s_lock, portMAX_DELAY);
    s_state = state;
    xSemaphoreGive(s_lock);
}

/* POST 한 번. 답은 *response 에(부른 쪽이 free). 오류면 s_message 에 서버가 준 글 */
static int post(const char *path, const char *body, bool with_auth, char **response)
{
    char url[256];
    snprintf(url, sizeof(url), "%s%s", CONFIG_ALBAM_SUPABASE_URL, path);
    *response = NULL;
    s_message[0] = '\0';

    esp_http_client_config_t config = {
        .url = url,
        .method = HTTP_METHOD_POST,
        .timeout_ms = TIMEOUT_MS,
        .crt_bundle_attach = esp_crt_bundle_attach,
        .buffer_size = 4096,
        .buffer_size_tx = 4096,      /* Authorization 머리말(토큰)이 길다 */
    };
    esp_http_client_handle_t client = esp_http_client_init(&config);
    if (!client) {
        return RESULT_NETWORK;
    }
    esp_http_client_set_header(client, "apikey", CONFIG_ALBAM_SUPABASE_KEY);
    esp_http_client_set_header(client, "Content-Type", "application/json");
    if (with_auth && s_access) {
        size_t len = strlen(s_access) + 8;
        char *bearer = malloc(len);
        snprintf(bearer, len, "Bearer %s", s_access);
        esp_http_client_set_header(client, "Authorization", bearer);
        free(bearer);
    }

    int result = RESULT_NETWORK, status = 0;
    size_t size = 0, room = 8192;
    char *text = malloc(room);
    int body_len = strlen(body);
    /* 어느 단계에서 막혔는지 남긴다: 연결(TLS 포함) / 보내기 / 답 머리말 / 답 읽기 */
    const char *stage = "memory";
    esp_err_t err = text ? esp_http_client_open(client, body_len) : ESP_ERR_NO_MEM;
    if (err == ESP_OK) {
        stage = "send";
        err = esp_http_client_write(client, body, body_len) == body_len ? ESP_OK : ESP_FAIL;
    } else if (text) {
        stage = "connect";
    }
    if (err == ESP_OK) {
        stage = "headers";
        err = esp_http_client_fetch_headers(client) >= 0 ? ESP_OK : ESP_FAIL;
    }
    if (err != ESP_OK) {
        snprintf(s_message, sizeof(s_message), "%s: %s (errno %d)", stage, esp_err_to_name(err), esp_http_client_get_errno(client));
        ESP_LOGW(TAG, "%s → %s", path, s_message);
    } else {
        status = esp_http_client_get_status_code(client);
        for (;;) {
            if (size + 1 >= room) {
                char *bigger = room < MAX_RESPONSE ? realloc(text, room * 2) : NULL;
                if (!bigger) {
                    status = 0;      /* 너무 큰 답은 버린다 */
                    break;
                }
                text = bigger;
                room *= 2;
            }
            int got = esp_http_client_read(client, text + size, room - size - 1);
            if (got <= 0) {
                if (got < 0) {
                    status = 0;
                }
                break;
            }
            size += got;
        }
    }
    if (err == ESP_OK && !status) {
        snprintf(s_message, sizeof(s_message), "read: stopped after %u bytes", (unsigned)size);
        ESP_LOGW(TAG, "%s → %s", path, s_message);
    }
    esp_http_client_close(client);
    esp_http_client_cleanup(client);

    if (text && status) {
        text[size] = '\0';
        if (status >= 200 && status < 300) {
            *response = text;
            return RESULT_OK;
        }
        /* 오류 글: message / error_description / msg / error 중 있는 것 */
        cJSON *json = cJSON_Parse(text);
        static const char *const KEYS[] = { "message", "error_description", "msg", "error" };
        for (size_t i = 0; json && i < sizeof(KEYS) / sizeof(KEYS[0]) && !s_message[0]; i++) {
            const cJSON *item = cJSON_GetObjectItem(json, KEYS[i]);
            if (cJSON_IsString(item)) {
                snprintf(s_message, sizeof(s_message), "%s", item->valuestring);
            }
        }
        cJSON_Delete(json);
        ESP_LOGW(TAG, "%s → HTTP %d %s", path, status, s_message);
        if (!s_message[0]) {
            snprintf(s_message, sizeof(s_message), "HTTP %d", status);
        }
        if (status == 401 || status == 403 || strstr(s_message, "JWT") || strstr(s_message, "not_family")) {
            result = RESULT_AUTH;
        } else if (status >= 500) {
            result = RESULT_NETWORK;
        } else {
            result = RESULT_OTHER;
        }
    }
    free(text);
    return result;
}

static void forget_session(void)
{
    free(s_access);
    s_access = NULL;
    s_refresh[0] = '\0';
    store_set("care_refresh", "");
    store_set("care_email", "");
    xSemaphoreTake(s_lock, portMAX_DELAY);
    s_email[0] = '\0';
    memset(&s_summary, 0, sizeof(s_summary));
    s_generation++;
    xSemaphoreGive(s_lock);
}

/* 로그인·갱신의 답에서 토큰을 꺼내 둔다 */
static bool store_tokens(const char *response)
{
    cJSON *json = cJSON_Parse(response);
    const cJSON *access = cJSON_GetObjectItem(json, "access_token");
    const cJSON *refresh = cJSON_GetObjectItem(json, "refresh_token");
    const cJSON *expires_in = cJSON_GetObjectItem(json, "expires_in");
    const cJSON *email = cJSON_GetObjectItem(cJSON_GetObjectItem(json, "user"), "email");
    bool ok = cJSON_IsString(access) && cJSON_IsString(refresh) && strlen(refresh->valuestring) < sizeof(s_refresh);
    if (ok) {
        free(s_access);
        s_access = strdup(access->valuestring);
        s_expires = uptime() + (cJSON_IsNumber(expires_in) ? (int64_t)expires_in->valuedouble : 3600);
        /* 갱신 토큰은 한 번 쓰면 바뀐다. 바뀐 것을 바로 저장한다 */
        snprintf(s_refresh, sizeof(s_refresh), "%s", refresh->valuestring);
        store_set("care_refresh", s_refresh);
        if (cJSON_IsString(email)) {
            xSemaphoreTake(s_lock, portMAX_DELAY);
            snprintf(s_email, sizeof(s_email), "%s", email->valuestring);
            xSemaphoreGive(s_lock);
            store_set("care_email", email->valuestring);
        }
    }
    cJSON_Delete(json);
    return ok && s_access;
}

static int sign_in(const char *email, const char *password)
{
    cJSON *json = cJSON_CreateObject();
    cJSON_AddStringToObject(json, "email", email);
    cJSON_AddStringToObject(json, "password", password);
    char *body = cJSON_PrintUnformatted(json);
    cJSON_Delete(json);
    char *response;
    int result = post("/auth/v1/token?grant_type=password", body, false, &response);
    cJSON_free(body);
    if (result == RESULT_OK && !store_tokens(response)) {
        result = RESULT_OTHER;
    }
    free(response);
    return result;
}

static int refresh_session(void)
{
    cJSON *json = cJSON_CreateObject();
    cJSON_AddStringToObject(json, "refresh_token", s_refresh);
    char *body = cJSON_PrintUnformatted(json);
    cJSON_Delete(json);
    char *response;
    int result = post("/auth/v1/token?grant_type=refresh_token", body, false, &response);
    cJSON_free(body);
    if (result == RESULT_OK && !store_tokens(response)) {
        result = RESULT_OTHER;
    }
    free(response);
    return result;
}

static time_t time_of(const cJSON *object, const char *key)
{
    const cJSON *item = cJSON_GetObjectItem(object, key);
    return cJSON_IsString(item) ? care_parse_time(item->valuestring) : 0;
}

static int int_of(const cJSON *object, const char *key, int fallback)
{
    const cJSON *item = cJSON_GetObjectItem(object, key);
    return cJSON_IsNumber(item) ? (int)item->valuedouble : fallback;
}

/* care_summary() 의 답에서 대시보드가 쓰는 부분만 꺼낸다(모양은 웹앱 src/domain.js 의 Summary) */
static bool parse_summary(const char *response, care_summary_t *s)
{
    cJSON *json = cJSON_Parse(response);
    if (!cJSON_IsObject(json)) {
        cJSON_Delete(json);
        return false;
    }
    memset(s, 0, sizeof(*s));
    s->valid = true;

    const cJSON *feed = cJSON_GetObjectItem(json, "last_feed");
    s->feed.at = time_of(feed, "at");
    s->feed.ended_at = time_of(feed, "ended_at");
    s->feed.ml = int_of(feed, "ml", -1);
    s->feed.feeding = cJSON_IsTrue(cJSON_GetObjectItem(feed, "feeding"));

    const cJSON *diaper = cJSON_GetObjectItem(json, "last_diaper");
    const cJSON *type = cJSON_GetObjectItem(diaper, "type");
    s->diaper.at = time_of(diaper, "at");
    if (cJSON_IsString(type)) {
        s->diaper.type = !strcmp(type->valuestring, "pee") ? DIAPER_PEE : !strcmp(type->valuestring, "poo") ? DIAPER_POO
                         : !strcmp(type->valuestring, "both") ? DIAPER_BOTH : DIAPER_NONE;
    }
    s->poo.at = time_of(cJSON_GetObjectItem(json, "last_poo"), "at");

    const cJSON *sleep = cJSON_GetObjectItem(json, "last_sleep");
    s->sleep.at = time_of(sleep, "at");
    s->sleep.ended_at = time_of(sleep, "ended_at");

    const cJSON *today = cJSON_GetObjectItem(json, "today");
    s->today.count = int_of(today, "feed_count", 0);
    s->today.ml = int_of(today, "feed_ml", 0);

    const cJSON *age = cJSON_GetObjectItem(json, "age");
    if (cJSON_IsObject(age)) {
        s->age.has = true;
        s->age.day = int_of(age, "day", 0);
        s->age.months = int_of(age, "months", 0);
        s->age.days = int_of(age, "days", 0);
        s->age.corrected = cJSON_IsNumber(cJSON_GetObjectItem(age, "corrected_months"));
        s->age.c_months = int_of(age, "corrected_months", 0);
        s->age.c_days = int_of(age, "corrected_days", 0);
    }

    /* 수유 간격 [[앞 수유의 서울 시, 간격(분)], …] */
    const cJSON *gap;
    cJSON_ArrayForEach(gap, cJSON_GetObjectItem(json, "feed_gaps")) {
        const cJSON *hour = cJSON_GetArrayItem(gap, 0), *minutes = cJSON_GetArrayItem(gap, 1);
        if (s->gap_count < CARE_MAX_GAPS && cJSON_IsNumber(hour) && cJSON_IsNumber(minutes)) {
            s->gaps[s->gap_count].hour = (uint8_t)hour->valuedouble;
            s->gaps[s->gap_count].minutes = (uint16_t)minutes->valuedouble;
            s->gap_count++;
        }
    }
    const cJSON *old = cJSON_GetObjectItem(json, "feed_gap");
    const cJSON *p25 = cJSON_GetObjectItem(old, "p25");
    s->old_gap.n = int_of(old, "n", 0);
    s->old_gap.p25 = cJSON_IsNumber(p25) ? p25->valuedouble : 0;

    cJSON_Delete(json);
    return true;
}

static int fetch_summary(void)
{
    static care_summary_t fresh;     /* 커서 스택에 두지 않는다 */
    char *response;
    int result = post("/rest/v1/rpc/care_summary", "{}", true, &response);
    if (result == RESULT_OK) {
        if (parse_summary(response, &fresh)) {
            xSemaphoreTake(s_lock, portMAX_DELAY);
            s_summary = fresh;
            s_generation++;
            xSemaphoreGive(s_lock);
        } else {
            result = RESULT_OTHER;
        }
    }
    free(response);
    return result;
}

static void wait_for(int seconds)
{
    ulTaskNotifyTake(pdTRUE, seconds < 0 ? portMAX_DELAY : pdMS_TO_TICKS(seconds * 1000));
}

static void care_task(void *arg)
{
    for (;;) {
        /* 화면이 넣어 둔 요청 */
        xSemaphoreTake(s_lock, portMAX_DELAY);
        bool want_login = s_want_login, want_logout = s_want_logout;
        char email[96], password[96];
        strlcpy(email, s_login_email, sizeof(email));
        strlcpy(password, s_login_password, sizeof(password));
        s_want_login = s_want_logout = false;
        memset(s_login_password, 0, sizeof(s_login_password));
        xSemaphoreGive(s_lock);

        if (want_logout) {
            forget_session();
            set_state(CARE_NEED_LOGIN);
        }
        if (want_login) {
            int result = sign_in(email, password);
            memset(password, 0, sizeof(password));
            if (result != RESULT_OK) {
                set_state(result == RESULT_NETWORK ? CARE_LOGIN_OFFLINE : CARE_LOGIN_FAILED);
                wait_for(-1);
                continue;
            }
            /* 요약을 읽어 봐야 가족 계정인지 안다. 그때까지는 '로그인 중' */
        }
        if (!s_refresh[0]) {
            if (care_state() == CARE_STARTING) {
                set_state(CARE_NEED_LOGIN);
            }
            wait_for(-1);
            continue;
        }

        net_status_t net;
        net_get_status(&net);
        if (net.state != NET_CONNECTED) {
            if (care_state() == CARE_OK) {
                set_state(CARE_OFFLINE);
            }
            wait_for(2);
            continue;
        }

        /* 갱신이 연결 문제 말고 다른 까닭으로 안 되면 갱신 토큰이 무효다 → 다시 로그인 */
        int result = RESULT_OK;
        bool session_dead = false;
        if (!s_access || s_expires - uptime() < REFRESH_MARGIN) {
            result = refresh_session();
            session_dead = result != RESULT_OK && result != RESULT_NETWORK;
        }
        if (result == RESULT_OK) {
            result = fetch_summary();
            if (result == RESULT_AUTH && !strstr(s_message, "not_family")) {
                /* 토큰이 끝났다고 하면 한 번 갱신하고 다시 */
                result = refresh_session();
                session_dead = result != RESULT_OK && result != RESULT_NETWORK;
                if (result == RESULT_OK) {
                    result = fetch_summary();
                }
            }
        }

        bool not_family = result == RESULT_AUTH && strstr(s_message, "not_family") != NULL;
        if (result == RESULT_OK) {
            xSemaphoreTake(s_lock, portMAX_DELAY);
            s_fails = 0;
            s_total_ok++;
            s_last_ok_at = uptime();
            xSemaphoreGive(s_lock);
            set_state(CARE_OK);
            wait_for(POLL_SECONDS);
            continue;
        }
        if (session_dead || not_family || result == RESULT_AUTH) {
            forget_session();
            set_state(not_family ? CARE_NOT_FAMILY : CARE_NEED_LOGIN);
            continue;
        }
        /* 못 읽음: 로그인은 그대로 두고 조금 뒤 다시. 잇달아 실패해야 "연결 안 됨" */
        xSemaphoreTake(s_lock, portMAX_DELAY);
        int fails = ++s_fails;
        s_total_fails++;
        s_last_error_at = uptime();
        snprintf(s_last_error, sizeof(s_last_error), "%s", s_message[0] ? s_message : "unknown");
        xSemaphoreGive(s_lock);
        if (fails >= OFFLINE_AFTER) {
            set_state(CARE_OFFLINE);
        }
        wait_for(RETRY_SECONDS);
    }
}

void care_start(void)
{
    s_lock = xSemaphoreCreateMutex();
    store_get("care_refresh", s_refresh, sizeof(s_refresh));
    store_get("care_email", s_email, sizeof(s_email));
    xTaskCreate(care_task, "care", 12288, NULL, 4, &s_task);
}

care_state_t care_state(void)
{
    xSemaphoreTake(s_lock, portMAX_DELAY);
    care_state_t state = s_state;
    xSemaphoreGive(s_lock);
    return state;
}

const char *care_email(void)
{
    static char copy[96];
    xSemaphoreTake(s_lock, portMAX_DELAY);
    strlcpy(copy, s_email, sizeof(copy));
    xSemaphoreGive(s_lock);
    return copy;
}

void care_diag(care_diag_t *out)
{
    xSemaphoreTake(s_lock, portMAX_DELAY);
    int64_t now = uptime();
    out->ok = s_total_ok;
    out->fails = s_total_fails;
    out->fails_in_a_row = s_fails;
    out->seconds_since_ok = s_last_ok_at ? (int)(now - s_last_ok_at) : -1;
    out->seconds_since_error = s_last_error_at ? (int)(now - s_last_error_at) : -1;
    strlcpy(out->last_error, s_last_error, sizeof(out->last_error));
    xSemaphoreGive(s_lock);
}

bool care_copy_summary(care_summary_t *out, uint32_t *seen)
{
    xSemaphoreTake(s_lock, portMAX_DELAY);
    bool changed = *seen != s_generation;
    if (changed) {
        *out = s_summary;
        *seen = s_generation;
    }
    xSemaphoreGive(s_lock);
    return changed;
}

void care_login(const char *email, const char *password)
{
    xSemaphoreTake(s_lock, portMAX_DELAY);
    strlcpy(s_login_email, email, sizeof(s_login_email));
    strlcpy(s_login_password, password, sizeof(s_login_password));
    s_want_login = true;
    s_state = CARE_LOGGING_IN;
    xSemaphoreGive(s_lock);
    xTaskNotifyGive(s_task);
}

void care_logout(void)
{
    xSemaphoreTake(s_lock, portMAX_DELAY);
    s_want_logout = true;
    s_state = CARE_NEED_LOGIN;
    xSemaphoreGive(s_lock);
    xTaskNotifyGive(s_task);
}
