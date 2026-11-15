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
#include "hal/wdt_hal.h"
#include "soc/rtc.h"
#include "esp_timer.h"
#include "esp_private/freertos_debug.h"
#include "riscv/rvruntime-frames.h"

/* 무선으로 받은 새 판이 이 시간 안에 와이파이에 못 붙으면 앞 판으로 되돌린다.
 * (와이파이가 안 되는 판이 올라가면 다시 무선으로 고칠 길이 없어서다) */
#define NEW_FIRMWARE_PROOF_SECONDS 120

/* 화면이 이만큼 멈춰 있으면 스스로 다시 켠다. 0.2.0 과 0.4.0 에서 밤새 화면이 멈춘 채 있었다.
 *
 * 0.4.1 은 멈추면 무조건 다시 켰는데(esp_restart), 그렇게 다시 켜도 화면이 안 풀려서 68초마다 다시 켜지는
 * 고리에 빠졌다(서버 접속 기록으로 확인. 전원을 뽑았다 꽂으면 풀린다). 그래서
 *   - 더 깊이 다시 켠다: 칩의 주변 장치까지 모두 초기화하는 방식(RTC 감시 타이머)으로
 *   - 그래도 또 멈추면 한 번만 더 해 보고 그만둔다. 화면은 멈춰 있어도 통신은 살아 있으므로
 *     자동 업데이트와 서버에 상태 남기기는 계속 된다
 * 멈춘 횟수와 그때 상태는 /info 의 ui 와 서버(care_device_log)에 남는다 */
#define UI_STALL_SECONDS 20
#define UI_STALL_RESTARTS 2      /* 잇달아 이만큼까지만 다시 켠다 */
#define UI_HEALTHY_SECONDS 600   /* 이만큼 멀쩡히 돌면 '잇달아'를 다시 0 부터 센다 */

static const char *TAG = "main";

static int stored_int(const char *key)
{
    char text[16];
    return store_get(key, text, sizeof(text)) ? atoi(text) : 0;
}

static void store_int(const char *key, int value)
{
    char text[16];
    snprintf(text, sizeof(text), "%d", value);
    store_set(key, text);
}

/* 칩 전체를 초기화하며 다시 켠다(주 시스템과 RTC 까지). esp_restart 는 CPU 와 일부 장치만 초기화해서
 * 화면 쪽 장치가 멈춘 상태가 그대로 남는 것으로 보인다 */
static void deep_restart(void)
{
    wdt_hal_context_t rwdt = RWDT_HAL_CONTEXT_DEFAULT();
    wdt_hal_init(&rwdt, WDT_RWDT, 0, false);
    wdt_hal_write_protect_disable(&rwdt);
    wdt_hal_config_stage(&rwdt, WDT_STAGE0, rtc_clk_slow_freq_get_hz() / 2, WDT_STAGE_ACTION_RESET_RTC);   /* 0.5초 뒤 */
    wdt_hal_enable(&rwdt);
    wdt_hal_write_protect_enable(&rwdt);
    vTaskDelay(pdMS_TO_TICKS(3000));
    esp_restart();   /* 감시 타이머가 안 먹었을 때만 여기까지 온다 */
}

/* 1초마다 화면이 움직이는지 본다. 화면 작업보다 높은 우선순위의 따로 된 작업에서 돈다.
 * 0.4.3 은 이것을 app_main 고리(우선순위 1)에서 돌렸는데, 화면이 멈춘 뒤로 이 고리도 같이 멈춰서
 * 한 번도 움직이지 못했다(화면 작업이 CPU 를 붙들고 있었던 것으로 보인다) */
/* 화면 작업("lvgl")이 지금 코드의 어디에 서 있는지 적는다: 상태, 멈춘 자리(pc)와 돌아갈 자리(ra),
 * 그리고 그 작업의 스택에 쌓여 있는 코드 주소들(부른 순서를 거슬러 볼 수 있다).
 * 주소는 빌드할 때 나오는 map 파일(릴리스의 map-<커밋>.txt.gz)로 함수 이름을 찾는다.
 * 0.4.4 에서 화면이 두 번 멈췄는데(목록에서 돌아온 직후, 그리고 아무도 안 만진 99분째)
 * 어디서 멈추는지를 몰라 고치지 못하고 있다 */
static void trace_lvgl_task(char *out, size_t len)
{
    TaskHandle_t task = xTaskGetHandle("lvgl");
    TaskSnapshot_t snap;
    if (!task || !vTaskGetSnapshot(task, &snap)) {
        snprintf(out, len, "no lvgl task");
        return;
    }
    const RvExcFrame *frame = (const RvExcFrame *)snap.pxTopOfStack;
    int n = snprintf(out, len, "state %d pc %08x ra %08x stack", (int)eTaskGetState(task), (unsigned)frame->mepc, (unsigned)frame->ra);
    /* 스택에서 코드 주소처럼 보이는 값만 고른다(플래시의 코드 0x40000000~, 램의 코드 0x4ff00000~) */
    uint32_t last = 0;
    const uint32_t *word = (const uint32_t *)snap.pxTopOfStack, *end = (const uint32_t *)snap.pxEndOfStack;
    for (int seen = 0; word < end && seen < 2000 && n > 0 && n < (int)len - 10; word++, seen++) {
        uint32_t v = *word;
        bool code = (v >= 0x40000000 && v < 0x4c000000) || (v >= 0x4ff00000 && v < 0x4ffc0000);
        if (code && v != last) {
            n += snprintf(out + n, len - n, " %08x", (unsigned)v);
            last = v;
        }
    }
}

static void watch_ui(void)
{
    static uint32_t last_ticks;
    static int stalled, healthy;
    static bool gave_up;
    int uptime = (int)(esp_timer_get_time() / 1000000);
    uint32_t ticks = ui_ticks();
    bool moving = ticks != last_ticks;
    last_ticks = ticks;
    stalled = moving ? 0 : stalled + 1;
    healthy = moving ? healthy + 1 : 0;
    if (healthy == UI_HEALTHY_SECONDS && stored_int("stall_streak")) {
        store_int("stall_streak", 0);
    }
    if (gave_up || stalled < UI_STALL_SECONDS) {
        return;
    }

    /* 멈췄다. 다음에 볼 수 있게 남긴다: 몇 번째인지, 켠 지 얼마 만인지, 돌려 옮기기 안에서 멈췄는지 */
    char info[160];
    uint32_t started, finished;
    board_rotate_counts(&started, &finished);
    int streak = stored_int("stall_streak");
    snprintf(info, sizeof(info), "uptime %ds, ticks %u, rotate %u/%u, streak %d, at %.24s", uptime, (unsigned)ticks,
             (unsigned)finished, (unsigned)started, streak, ui_where());
    static char trace[420];
    trace_lvgl_task(trace, sizeof(trace));
    store_int("stalls", stored_int("stalls") + 1);
    store_set("stall_info", info);
    store_set("stall_trace", trace);
    care_report_stall();             /* 서버에도 남긴다(통신은 화면과 따로 돈다) */
    vTaskDelay(pdMS_TO_TICKS(12000));

    if (streak >= UI_STALL_RESTARTS) {
        ESP_LOGE(TAG, "화면이 멈춤(%s). 다시 켜도 안 풀려서 그대로 둔다.", info);
        gave_up = true;
        return;
    }
    ESP_LOGE(TAG, "화면이 멈춤(%s). 다시 켠다.", info);
    store_int("stall_streak", streak + 1);
    deep_restart();
}

static void watch_task(void *arg)
{
    for (;;) {
        vTaskDelay(pdMS_TO_TICKS(1000));
        watch_ui();
    }
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

    xTaskCreate(watch_task, "watch", 4096, NULL, configMAX_PRIORITIES - 2, NULL);

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
