idf_component_register(
    SRCS "main.c" "store.c" "net.c" "ota.c" "care.c" "care_text.c" "update.c" "board.c" "ui.c" "assets/sprites.c"
    INCLUDE_DIRS "."
    # 한글 글꼴(Pretendard)은 TTF 그대로 넣고 보드에서 크기별로 그린다
    EMBED_FILES "assets/pretendard-regular.ttf" "assets/pretendard-semibold.ttf"
    REQUIRES nvs_flash esp_wifi esp_netif esp_event esp_http_server esp_http_client esp_https_ota mbedtls json app_update esp_timer
)
