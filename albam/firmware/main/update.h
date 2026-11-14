#pragma once
/* 자동 업데이트: 깃허브에 올라온 새 펌웨어를 보드가 스스로 받아 바꾼다.
 * 빌드(.github/workflows/albam-firmware.yml)가 끝나면 릴리스에 albam_board.bin 과 version.txt 를 올리고,
 * 보드는 10분마다 version.txt 를 읽어 자기 판과 다르면 받는다.
 *   정식판: master 에서 빌드한 것(릴리스 albam-firmware)
 *   시험판: 다른 브랜치에서 빌드한 것(릴리스 albam-firmware-dev) */
#include <stdbool.h>
#include <stddef.h>

void update_start(void);

/* 설정 화면용 */
void update_check_now(void);
void update_status(char *out, size_t len);   /* "최신 판이에요", "새 판 받는 중" … */
bool update_dev_get(void);                   /* 시험판을 받는가 */
void update_dev_set(bool dev);
