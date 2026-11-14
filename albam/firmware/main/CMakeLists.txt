idf_component_register(
    SRCS "main.c" "store.c" "net.c" "ota.c" "care.c" "care_text.c" "update.c" "board.c" "lv_mem_psram.c" "ui.c" "assets/sprites.c"
    INCLUDE_DIRS "."
    # 한글 글꼴(Pretendard)은 TTF 그대로 넣고 보드에서 크기별로 그린다
    EMBED_FILES "assets/pretendard-regular.ttf" "assets/pretendard-semibold.ttf"
    REQUIRES esp_driver_ppa esp_mm nvs_flash esp_wifi esp_netif esp_event esp_http_server esp_http_client esp_https_ota mbedtls json app_update esp_timer
)

# 화면을 돌려 옮기는 PPA 부름을 board.c 의 CPU 함수로 바꿔 끼운다(PPA 가 멈추는 문제)
target_link_libraries(${COMPONENT_LIB} INTERFACE "-Wl,--wrap=ppa_do_scale_rotate_mirror")

# LVGL 라이브러리가 lv_mem_psram.c 의 함수를 찾을 수 있게, 링커가 이 파일을 먼저 집어 들게 한다
target_link_libraries(${COMPONENT_LIB} INTERFACE "-u lv_malloc_core")
