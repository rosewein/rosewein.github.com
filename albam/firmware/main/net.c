/* 와이파이(보드의 C6 칩을 거친다), 한국 시간, albam-board.local 이름 */
#include "net.h"
#include "store.h"

#include <string.h>
#include <time.h>
#include "freertos/FreeRTOS.h"
#include "freertos/semphr.h"
#include "freertos/task.h"
#include "esp_event.h"
#include "esp_log.h"
#include "esp_netif.h"
#include "esp_netif_sntp.h"
#include "esp_wifi.h"
#include "mdns.h"
#include "sdkconfig.h"

#define HOSTNAME "albam-board"
#define NEW_WIFI_TRIES 4
#define MAX_APS 20

static const char *TAG = "net";

static SemaphoreHandle_t s_lock;
static net_status_t s_status;
static bool s_want;            /* 끊기면 다시 붙는다 */
static bool s_unsaved;         /* 화면에서 넣은 새 와이파이: 붙으면 저장, 계속 실패하면 멈춘다 */
static int s_fails;
static char s_password[65];
static bool s_services;        /* 시간 받기와 이름 알리기를 시작했는가 */

static net_ap_t s_aps[MAX_APS];
static int s_ap_count;
static volatile bool s_scanning;

static void set_state(net_state_t state)
{
    xSemaphoreTake(s_lock, portMAX_DELAY);
    s_status.state = state;
    if (state != NET_CONNECTED) {
        s_status.ip[0] = '\0';
    }
    xSemaphoreGive(s_lock);
}

static void start_services(void)
{
    if (s_services) {
        return;
    }
    s_services = true;

    esp_sntp_config_t sntp = ESP_NETIF_SNTP_DEFAULT_CONFIG_MULTIPLE(
        2, ESP_SNTP_SERVER_LIST("time.google.com", "pool.ntp.org"));
    esp_netif_sntp_init(&sntp);

    if (mdns_init() == ESP_OK) {
        mdns_hostname_set(HOSTNAME);
        mdns_instance_name_set("Albam board");
        mdns_service_add(NULL, "_http", "_tcp", 80, NULL, 0);
    }
}

static void on_event(void *arg, esp_event_base_t base, int32_t id, void *data)
{
    if (base == WIFI_EVENT && id == WIFI_EVENT_STA_START) {
        if (s_want) {
            esp_wifi_connect();
        }
    } else if (base == WIFI_EVENT && id == WIFI_EVENT_STA_DISCONNECTED) {
        if (!s_want) {
            return;
        }
        if (s_unsaved && ++s_fails >= NEW_WIFI_TRIES) {
            ESP_LOGW(TAG, "새 와이파이에 못 붙음");
            s_want = false;
            set_state(NET_FAILED);
            return;
        }
        set_state(NET_CONNECTING);
        esp_wifi_connect();
    } else if (base == IP_EVENT && id == IP_EVENT_STA_GOT_IP) {
        ip_event_got_ip_t *event = data;
        xSemaphoreTake(s_lock, portMAX_DELAY);
        snprintf(s_status.ip, sizeof(s_status.ip), IPSTR, IP2STR(&event->ip_info.ip));
        s_status.state = NET_CONNECTED;
        xSemaphoreGive(s_lock);
        ESP_LOGI(TAG, "연결됨 %s", s_status.ip);

        s_fails = 0;
        if (s_unsaved) {
            s_unsaved = false;
            store_set("wifi_ssid", s_status.ssid);
            store_set("wifi_pass", s_password);
        }
        start_services();
    }
}

static void apply_and_connect(const char *ssid, const char *password)
{
    wifi_config_t cfg = { 0 };
    strlcpy((char *)cfg.sta.ssid, ssid, sizeof(cfg.sta.ssid));
    strlcpy((char *)cfg.sta.password, password, sizeof(cfg.sta.password));

    xSemaphoreTake(s_lock, portMAX_DELAY);
    strlcpy(s_status.ssid, ssid, sizeof(s_status.ssid));
    s_status.state = NET_CONNECTING;
    s_status.ip[0] = '\0';
    xSemaphoreGive(s_lock);
    strlcpy(s_password, password, sizeof(s_password));

    s_fails = 0;
    s_want = false;              /* 아래 끊기에서 옛 설정으로 다시 붙지 않게 */
    esp_wifi_disconnect();
    esp_wifi_set_config(WIFI_IF_STA, &cfg);
    s_want = true;
    esp_wifi_connect();
}

void net_init(void)
{
    s_lock = xSemaphoreCreateMutex();
    setenv("TZ", "KST-9", 1);    /* 한국 시간(UTC+9, 서머타임 없음) */
    tzset();

    ESP_ERROR_CHECK(esp_netif_init());
    ESP_ERROR_CHECK(esp_event_loop_create_default());
    esp_netif_t *netif = esp_netif_create_default_wifi_sta();
    esp_netif_set_hostname(netif, HOSTNAME);

    wifi_init_config_t init = WIFI_INIT_CONFIG_DEFAULT();
    ESP_ERROR_CHECK(esp_wifi_init(&init));
    ESP_ERROR_CHECK(esp_event_handler_register(WIFI_EVENT, ESP_EVENT_ANY_ID, on_event, NULL));
    ESP_ERROR_CHECK(esp_event_handler_register(IP_EVENT, IP_EVENT_STA_GOT_IP, on_event, NULL));
    ESP_ERROR_CHECK(esp_wifi_set_storage(WIFI_STORAGE_RAM));
    ESP_ERROR_CHECK(esp_wifi_set_mode(WIFI_MODE_STA));
    ESP_ERROR_CHECK(esp_wifi_start());

    char ssid[33], password[65];
    if (store_get("wifi_ssid", ssid, sizeof(ssid))) {
        store_get("wifi_pass", password, sizeof(password));
        apply_and_connect(ssid, password);
    } else if (strlen(CONFIG_ALBAM_WIFI_SSID) > 0) {
        s_unsaved = false;       /* 펌웨어에 넣어 둔 값은 계속 다시 붙어 본다 */
        apply_and_connect(CONFIG_ALBAM_WIFI_SSID, CONFIG_ALBAM_WIFI_PASSWORD);
    } else {
        set_state(NET_NO_WIFI);
    }
}

void net_get_status(net_status_t *out)
{
    xSemaphoreTake(s_lock, portMAX_DELAY);
    *out = s_status;
    xSemaphoreGive(s_lock);
}

void net_connect(const char *ssid, const char *password)
{
    s_unsaved = true;
    apply_and_connect(ssid, password);
}

static void scan_task(void *arg)
{
    /* 붙는 중에는 찾기가 실패하므로, 못 붙고 있던 시도는 멈춘다 */
    net_status_t now;
    net_get_status(&now);
    if (now.state != NET_CONNECTED) {
        s_want = false;
        esp_wifi_disconnect();
        vTaskDelay(pdMS_TO_TICKS(200));
    }

    static wifi_ap_record_t records[MAX_APS];
    uint16_t found = 0;
    if (esp_wifi_scan_start(NULL, true) == ESP_OK) {
        found = MAX_APS;
        if (esp_wifi_scan_get_ap_records(&found, records) != ESP_OK) {
            found = 0;
        }
    }

    xSemaphoreTake(s_lock, portMAX_DELAY);
    s_ap_count = 0;
    for (int i = 0; i < found; i++) {
        const char *ssid = (const char *)records[i].ssid;
        bool seen = ssid[0] == '\0';   /* 숨은 이름은 뺀다 */
        for (int j = 0; j < s_ap_count && !seen; j++) {
            seen = strcmp(s_aps[j].ssid, ssid) == 0;
        }
        if (seen) {
            continue;
        }
        strlcpy(s_aps[s_ap_count].ssid, ssid, sizeof(s_aps[0].ssid));
        s_aps[s_ap_count].rssi = records[i].rssi;
        s_aps[s_ap_count].open = records[i].authmode == WIFI_AUTH_OPEN;
        s_ap_count++;
    }
    xSemaphoreGive(s_lock);

    s_scanning = false;
    vTaskDelete(NULL);
}

void net_scan_start(void)
{
    if (s_scanning) {
        return;
    }
    s_scanning = true;
    xTaskCreate(scan_task, "wifi_scan", 4096, NULL, 4, NULL);
}

int net_scan_results(net_ap_t *out, int max)
{
    if (s_scanning) {
        return -1;
    }
    xSemaphoreTake(s_lock, portMAX_DELAY);
    int n = s_ap_count < max ? s_ap_count : max;
    memcpy(out, s_aps, n * sizeof(net_ap_t));
    xSemaphoreGive(s_lock);
    return n;
}

bool net_time_synced(void)
{
    return time(NULL) > 1700000000;   /* 2023년 뒤면 받아 온 시간이다 */
}
