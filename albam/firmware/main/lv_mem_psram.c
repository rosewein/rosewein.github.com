/* LVGL 이 쓰는 메모리를 모두 PSRAM(32MB)에서 받게 한다(sdkconfig.defaults 의 CONFIG_LV_USE_CUSTOM_MALLOC).
 *
 * 보드 안쪽 메모리는 0.7MB 쯤인데 와이파이·화면 드라이버가 써야 한다. LVGL 을 보통 malloc 에 맡기면
 * 16KB 보다 작은 조각(화면 부품, 글자 그림)이 안쪽 메모리로 가서, 0.2.4 에서 켠 지 23초에 65KB 만 남았다.
 * 글자를 새로 그릴수록 더 줄어 서버 연결이 실패하게 된다. */
#include <string.h>
#include "esp_heap_caps.h"
#include "lvgl.h"

#define CAPS (MALLOC_CAP_SPIRAM | MALLOC_CAP_8BIT)

void lv_mem_init(void)
{
}

void lv_mem_deinit(void)
{
}

lv_mem_pool_t lv_mem_add_pool(void *mem, size_t bytes)
{
    return NULL;
}

void lv_mem_remove_pool(lv_mem_pool_t pool)
{
}

void *lv_malloc_core(size_t size)
{
    return heap_caps_malloc(size, CAPS);
}

void *lv_realloc_core(void *p, size_t new_size)
{
    return heap_caps_realloc(p, new_size, CAPS);
}

void lv_free_core(void *p)
{
    heap_caps_free(p);
}

void lv_mem_monitor_core(lv_mem_monitor_t *mon)
{
    memset(mon, 0, sizeof(*mon));
    mon->total_size = heap_caps_get_total_size(CAPS);
    mon->free_size = heap_caps_get_free_size(CAPS);
    mon->free_biggest_size = heap_caps_get_largest_free_block(CAPS);
}

lv_result_t lv_mem_test_core(void)
{
    return LV_RESULT_OK;
}
