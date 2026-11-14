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

/* 무선으로 받은 새 판이 이 시간 안에 와이파이에 못 붙으면 앞 판으로 되돌린다.
 * (와이파이가 안 되는 판이 올라가면 다시 무선으로 고칠 길이 없어서다) */
#define NEW_FIRMWARE_PROOF_SECONDS 120

static const char *TAG = "main";

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
    board_start_ui();

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
        vTaskDelay(pdMS_TO_TICKS(1000));
    }
}
