idf_component_register(
    SRCS "main.c" "store.c" "net.c" "ota.c" "ui.c"
    INCLUDE_DIRS "."
    REQUIRES nvs_flash esp_wifi esp_netif esp_event esp_http_server app_update esp_timer esp_driver_i2c
)
