/* 알밤보드 P4 펌웨어: 와이파이, 한국 시간, 무선 업데이트, 대시보드(읽기 전용).
 * 보드: Waveshare ESP32-P4-WIFI6-Touch-LCD-7 (7인치 올인원, 세로 720x1280 패널을 돌려 가로 1280x720) */
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "esp_log.h"
#include "esp_ota_ops.h"

#include "board.h"
#include "care.h"
#include "net.h"
#include "ota.h"
#include "store.h"
#include "update.h"
#include "ui.h"

#include <stdio.h>
#include <stdlib.h>
#include "esp_system.h"

/* 무선으로 받은 새 판이 이 시간 안에 와이파이에 못 붙으면 앞 판으로 되돌린다.
 * (와이파이가 안 되는 판이 올라가면 다시 무선으로 고칠 길이 없어서다) */
#define NEW_FIRMWARE_PROOF_SECONDS 120

/* 화면이 이만큼 멈춰 있으면 스스로 다시 켠다. 0.2.0 과 0.4.0 에서 밤새 화면이 멈춘 채 있었다.
 * 까닭을 찾을 때까지, 멈춘 채 두지 않고 1분 안에 되살아나게 한다. 멈춘 횟수와 그때 상태는 /info 에 남는다 */
#define UI_STALL_SECONDS 60

static const char *TAG = "main";

static void restart_if_ui_stalled(int uptime)
{
    static uint32_t last_ticks;
    static int stalled;
    uint32_t ticks = ui_ticks();
    stalled = ticks == last_ticks ? stalled + 1 : 0;
    last_ticks = ticks;
    if (stalled < UI_STALL_SECONDS) {
        return;
    }
    /* 다음에 켜졌을 때 볼 수 있게 남긴다: 몇 번째인지, 켠 지 얼마 만인지, 돌려 옮기기 안에서 멈췄는지 */
    char count[16], info[96];
    uint32_t started, finished;
    board_rotate_counts(&started, &finished);
    int stalls = store_get("stalls", count, sizeof(count)) ? atoi(count) : 0;
    snprintf(count, sizeof(count), "%d", stalls + 1);
    snprintf(info, sizeof(info), "uptime %ds, ticks %u, rotate %u/%u", uptime, (unsigned)ticks, (unsigned)finished, (unsigned)started);
    store_set("stalls", count);
    store_set("stall_info", info);
    ESP_LOGE(TAG, "화면이 %d초 멈춤(%s). 다시 켠다.", UI_STALL_SECONDS, info);
    esp_restart();
}

static bool on_trial(void)
{
    esp_ota_img_states_t state;
    return esp_ota_get_state_partition(esp_ota_get_running_partition(), &state) == ESP_OK &&
           state == ESP_OTA_IMG_PENDING_VERIFY;
}

void app_main(void)
{
    store_init();
    ota_init();
    net_init();
    care_start();
    update_start();
    board_start_ui();
    sound_start();

    bool trial = on_trial();
    bool server = false;
    for (int seconds = 0;; seconds++) {
        net_status_t net;
        net_get_status(&net);

        if (net.state == NET_CONNECTED && !server) {
            ota_start_server();
            server = true;
        }
        /* 화면을 그리다 죽는 판도 걸러지게, 켜진 지 조금 지난 뒤에 확정한다 */
        if (trial && net.state == NET_CONNECTED && seconds >= 15) {
            esp_ota_mark_app_valid_cancel_rollback();
            trial = false;
            ESP_LOGI(TAG, "새 판 확인 끝");
        } else if (trial && seconds >= NEW_FIRMWARE_PROOF_SECONDS) {
            ESP_LOGE(TAG, "새 판이 와이파이에 못 붙음. 앞 판으로 되돌린다.");
            esp_ota_mark_app_invalid_rollback_and_reboot();
        }
        restart_if_ui_stalled(seconds);
        vTaskDelay(pdMS_TO_TICKS(1000));
    }
}
