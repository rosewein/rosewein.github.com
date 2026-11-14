/* 효과음. 웹앱 src/ui/sound.js 와 같은 가락을 사각파로 만들어 보드의 스피커(ES8311 코덱)로 낸다.
 * 소리가 안 나도 기록에는 지장이 없게, 준비에 실패하면 조용히 넘어간다. */
#include "ui.h"
#include "store.h"

#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <time.h>
#include "freertos/FreeRTOS.h"
#include "freertos/queue.h"
#include "freertos/task.h"
#include "bsp/esp-bsp.h"
#include "esp_log.h"

#define RATE 22050
#define DEFAULT_VOLUME 50
#define AMPLITUDE 28000          /* 파형 크기(최대 32767). 9000 일 때는 소리 크기 100% 에서도 작았다 */
#define NIGHT_START_HOUR 20      /* 밤에는 작게(board.c 의 밤 밝기와 같은 시간) */
#define NIGHT_END_HOUR 6

typedef struct { int hz, ms; } note_t;

/* [주파수 Hz, 길이 ms]. 끝은 { 0, 0 } */
static const note_t TUNES[][4] = {
    [UI_SOUND_TAP] = { { 520, 30 } },
    [UI_SOUND_SAVE] = { { 660, 80 }, { 880, 80 }, { 1320, 140 } },
    [UI_SOUND_CANCEL] = { { 660, 80 }, { 440, 140 } },
    [UI_SOUND_ERROR] = { { 200, 120 }, { 160, 200 } },
};

static const char *TAG = "sound";
static esp_codec_dev_handle_t s_speaker;
static QueueHandle_t s_queue;
static int s_volume;             /* 0 이면 끔 */

static bool is_night(void)
{
    time_t now = time(NULL);
    struct tm t;
    localtime_r(&now, &t);
    return now > 1700000000 && (t.tm_hour >= NIGHT_START_HOUR || t.tm_hour < NIGHT_END_HOUR);
}

static void play(const note_t *notes)
{
    static int16_t samples[RATE / 4];   /* 가장 긴 음(200ms)보다 넉넉히 */
    for (; notes->hz; notes++) {
        int count = RATE * notes->ms / 1000;
        if (count > (int)(sizeof(samples) / sizeof(samples[0]))) {
            count = sizeof(samples) / sizeof(samples[0]);
        }
        int half = RATE / notes->hz / 2;
        for (int i = 0; i < count; i++) {
            /* 사각파가 점점 작아진다(8비트 게임 소리) */
            float fade = expf(-5.0f * i / count);
            samples[i] = (int16_t)(((i / (half ? half : 1)) % 2 ? -1 : 1) * AMPLITUDE * fade);
        }
        esp_codec_dev_write(s_speaker, samples, count * sizeof(samples[0]));
    }
}

static void sound_task(void *arg)
{
    ui_sound_t sound;
    int applied = -1;
    for (;;) {
        xQueueReceive(s_queue, &sound, portMAX_DELAY);
        int volume = is_night() ? s_volume / 2 : s_volume;
        if (volume <= 0) {
            continue;
        }
        if (volume != applied) {
            esp_codec_dev_set_out_vol(s_speaker, volume);
            applied = volume;
        }
        play(TUNES[sound]);
    }
}

/* 켤 때 한 번. 여기서 멈추는 판은 켜지자마자 죽으므로 자동 업데이트가 앞 판으로 되돌린다 */
void sound_start(void)
{
    char saved[8];
    s_volume = store_get("volume", saved, sizeof(saved)) ? atoi(saved) : DEFAULT_VOLUME;

    s_speaker = bsp_audio_codec_speaker_init();
    esp_codec_dev_sample_info_t format = { .sample_rate = RATE, .channel = 1, .bits_per_sample = 16 };
    if (!s_speaker || esp_codec_dev_open(s_speaker, &format) != ESP_OK) {
        ESP_LOGW(TAG, "스피커를 못 켬. 소리 없이 간다");
        s_speaker = NULL;
        return;
    }
    s_queue = xQueueCreate(4, sizeof(ui_sound_t));
    xTaskCreate(sound_task, "sound", 4096, NULL, 4, NULL);
}

void ui_sound(ui_sound_t sound)
{
    if (s_queue) {
        xQueueSend(s_queue, &sound, 0);   /* 밀려 있으면 버린다 */
    }
}

int ui_volume_get(void)
{
    return s_volume;
}

void ui_volume_set(int percent, bool save)
{
    s_volume = percent < 0 ? 0 : percent > 100 ? 100 : percent;
    if (save) {
        char text[8];
        snprintf(text, sizeof(text), "%d", s_volume);
        store_set("volume", text);
        ui_sound(UI_SOUND_SAVE);   /* 맞춘 크기로 한 번 들려준다 */
    }
}
