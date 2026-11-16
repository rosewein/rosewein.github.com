#pragma once
#include <stdbool.h>
#include <stdint.h>

typedef enum {
    NET_NO_WIFI,      /* 저장된 와이파이가 없다 */
    NET_CONNECTING,
    NET_CONNECTED,
    NET_FAILED,       /* 화면에서 넣은 새 와이파이로 못 붙었다 */
} net_state_t;

typedef struct {
    net_state_t state;
    char ssid[33];
    char ip[16];
} net_status_t;

typedef struct {
    char ssid[33];
    int8_t rssi;
    bool open;
} net_ap_t;

void net_init(void);
void net_get_status(net_status_t *out);

/* 새 와이파이로 붙어 본다. 붙으면 저장한다. */
void net_connect(const char *ssid, const char *password);

/* 주변 와이파이 찾기. 끝나기 전에는 net_scan_results 가 -1 을 준다. */
void net_scan_start(void);
int net_scan_results(net_ap_t *out, int max);

/* 한국 시간을 받아 왔는가 */
bool net_time_synced(void);
