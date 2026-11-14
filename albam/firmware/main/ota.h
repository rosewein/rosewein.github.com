#pragma once

/* 무선 업데이트 번호(6자리)를 준비한다. 처음 켤 때 만들어 저장한다. */
void ota_init(void);
const char *ota_code(void);

/* 와이파이에 붙은 뒤 한 번 부른다: http://albam-board.local/ */
void ota_start_server(void);

/* 받는 중이면 0~100, 아니면 -1 */
int ota_progress(void);
void ota_set_progress(int percent);   /* 자동 업데이트(update.c)가 받는 동안 알린다 */
