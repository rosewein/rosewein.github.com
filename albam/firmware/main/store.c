#include "store.h"
#include "nvs.h"
#include "nvs_flash.h"

#define NS "albam"

void store_init(void)
{
    esp_err_t err = nvs_flash_init();
    if (err == ESP_ERR_NVS_NO_FREE_PAGES || err == ESP_ERR_NVS_NEW_VERSION_FOUND) {
        ESP_ERROR_CHECK(nvs_flash_erase());
        err = nvs_flash_init();
    }
    ESP_ERROR_CHECK(err);
}

bool store_get(const char *key, char *out, size_t len)
{
    nvs_handle_t h;
    out[0] = '\0';
    if (nvs_open(NS, NVS_READONLY, &h) != ESP_OK) {
        return false;
    }
    esp_err_t err = nvs_get_str(h, key, out, &len);
    nvs_close(h);
    if (err != ESP_OK) {
        out[0] = '\0';
    }
    return err == ESP_OK && out[0] != '\0';
}

void store_set(const char *key, const char *value)
{
    nvs_handle_t h;
    if (nvs_open(NS, NVS_READWRITE, &h) != ESP_OK) {
        return;
    }
    nvs_set_str(h, key, value);
    nvs_commit(h);
    nvs_close(h);
}
