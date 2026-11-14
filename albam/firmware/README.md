# 알밤보드 P4 펌웨어

거실 S10 대신 쓸 보드(Waveshare ESP32-P4-WIFI6-Touch-LCD-7, 7인치 올인원)의 첫 펌웨어다.
화면은 ILI9881C(세로 720×1280), 터치는 GT9271 이다. 보드 지원 패키지는 `waveshare/esp32_p4_wifi6_touch_lcd_x` 를 쓰고 7인치를 고른다(`CONFIG_BSP_LCD_TYPE_720_1280_7_INCH`).
수유·기저귀·잠이 얼마나 지났는지 보여 주고, 칸을 눌러 기록한다. 지난 기록 넣기·고치기, 그 밖의 종류(목욕·체온 등), 음성, 통계는 아직 S10 웹앱에서 한다.

| 들어 있는 것 | 내용 |
| --- | --- |
| 와이파이 | 처음 켜면 화면에서 와이파이를 고르고 비밀번호를 넣는다. 보드에 저장된다 |
| 한국 시간 | 인터넷 시간(NTP)을 받아 한국 시간으로 보여 준다 |
| 가로 화면 | 세로 패널을 90도 돌려 1280×720 가로로 쓴다 |
| 한글 | 웹앱과 같은 Pretendard. TTF 를 넣어 두고 보드에서 크기별로 그린다 |
| 로그인 | 화면 글자판으로 가족 계정 이메일과 비밀번호를 넣는다. 비밀번호는 저장하지 않고 갱신 토큰만 남긴다 |
| 대시보드 | 20초마다 `care_summary` 를 읽어 알밤·말풍선과 수유·기저귀·잠 세 칸을 보여 준다(웹앱과 같은 규칙) |
| 기록 | 수유(양을 골라 [지금 저장]·[먹이기 시작], 먹이는 중이면 [다 먹음]), 기저귀(소변·대변·둘 다), 잠([잠들었어요]·[깼어요]). 비슷한 기록이 있으면 물어보고, 저장 직후 6초 동안 [취소] |
| 밝기 | 낮과 밤(오후 8시~오전 6시)을 따로 둔다. 밤은 처음 값 20%. 설정 화면에서 바꾼다 |
| 소리 | 누를 때·저장·취소·실패에 효과음(웹앱과 같은 가락). 설정에서 크기를 바꾸고 맨 왼쪽이면 끈다. 밤에는 절반 |
| 자동 업데이트 | 깃허브에 올라온 새 펌웨어를 스스로 받아 바꾼다. 받는 1분쯤은 화면이 꺼진다(패널이 번쩍여서 가린다). 손으로 보낼 수도 있다(`http://albam-board.local/`) |

## 처음 한 번: 선으로 굽기

칩은 ESP32-P4 리비전 v3.2 이고, 그에 맞춰 `CONFIG_ESP32P4_SELECTS_REV_LESS_V3=n` 으로 빌드한다(`sdkconfig.defaults`).
ESP-IDF v5.5.6 으로 빌드를 확인했다. v5.5.2 는 부품을 고르는 단계에서 멈춘다("Missing required kconfig option").

```sh
cd albam/firmware
idf.py set-target esp32p4
idf.py build
idf.py -p <포트> flash monitor
```

빌드 도구가 없으면 깃허브 Actions 의 `albam-firmware` 실행에서 `albam-board-firmware` 를 내려받는다.
그 안의 `albam_board_full.bin` 은 주소 0 에 그대로 구우면 되는 한 덩어리 파일이다.

```sh
esptool.py --chip esp32p4 -p <포트> write_flash 0x0 albam_board_full.bin
```

## 그다음부터: 자동 업데이트

펌웨어를 고쳐 깃허브에 올리면 보드가 스스로 받아 바꾼다. 손으로 할 일은 없다.

1. `albam/firmware` 를 고쳐 올리면 깃허브 Actions(`albam-firmware`)가 빌드해 릴리스에 `albam_board.bin` 과 `version.txt` 를 올린다.
2. 보드는 켜지고 1분 뒤, 그다음부터 10분마다 `version.txt` 를 읽는다. 자기 판과 다르면 받아서 다시 켜진다.
3. 급하면 보드의 설정 → [업데이트 확인].

| 어디서 빌드했나 | 릴리스 | 받는 보드 |
| --- | --- | --- |
| `master` | `albam-firmware` (정식판) | '시험판 받기'를 끈 보드 |
| 다른 브랜치 | `albam-firmware-dev` (시험판) | '시험판 받기'를 켠 보드(처음 값은 켜짐) |

- 판 번호는 `CMakeLists.txt` 의 `PROJECT_VER` 에 커밋 번호가 붙은 것이다(`0.2.2+1a2b3c4`). 빌드마다 달라서 번호를 손으로 올리지 않아도 새 판으로 본다.
- 새 판이 켜지다 죽거나 2분 안에 와이파이에 못 붙으면 앞 판으로 되돌아가고, 그 판은 다시 받지 않는다(설정 화면에 "켜지지 않아 건너뜀").
- 저장소가 공개라 펌웨어도 누구나 받을 수 있다. 펌웨어에는 비밀번호나 토큰이 들어 있지 않다(와이파이·로그인은 보드에 따로 저장된다).
- 이 저장소에 올릴 수 있는 사람은 보드의 펌웨어를 바꿀 수 있다.

## 손으로 보내기

보드의 설정 화면에 6자리 무선 업데이트 번호가 나온다. 이 번호를 아는 사람만 새 판을 보낼 수 있다.

- 브라우저: `http://albam-board.local/` (안 열리면 화면에 나온 주소)에서 `build/albam_board.bin` 을 고르고 번호를 넣는다.
- 명령줄: `tools/ota.sh 123456` (주소를 직접 주려면 `tools/ota.sh 123456 192.168.0.12`)

새 판은 켜진 뒤 2분 안에 와이파이에 붙어야 확정된다. 못 붙으면 스스로 앞 판으로 되돌아간다.
와이파이가 안 되는 판이 올라가면 무선으로 고칠 길이 없기 때문이다.

판 번호는 설정 화면과 `/info` 에서 확인할 수 있다. `/info` 에는 남은 메모리와 서버 읽기 상태(못 읽은 횟수, 마지막 까닭)도 나온다.

## 와이파이를 펌웨어에 미리 넣기 (선택)

화면에서 고르는 대신 미리 넣어 구우려면 `sdkconfig.local` 파일을 만든다. 이 파일은 저장소에 올라가지 않는다.

```
CONFIG_ALBAM_WIFI_SSID="집 와이파이 이름"
CONFIG_ALBAM_WIFI_PASSWORD="비밀번호"
```

## 코드

| 파일 | 하는 일 |
| --- | --- |
| `main/main.c` | 시작 순서, 새 판 확정·되돌리기 |
| `main/net.c` | 와이파이(보드의 C6 칩을 거친다), 한국 시간, `albam-board.local` |
| `main/care.c` | 서버(Supabase) 로그인·토큰 갱신, 20초마다 요약 읽기, 기록 보내기. 웹앱 `src/api/supabase-rest.js` 와 같은 HTTP 호출 |
| `main/care_text.c` | 요약을 화면에 보일 글로 바꾸는 규칙(지난 시간, 급한 항목, 기저귀 세부). 웹앱 `src/time.js`·`src/ui/status.js` 와 같다 |
| `main/ui.c` | 화면 네 개: 대시보드, 설정, 와이파이 고르기, 로그인(LVGL 9) |
| `main/lv_mem_psram.c` | LVGL 메모리를 PSRAM 에서 받는다(안쪽 메모리는 와이파이·드라이버 몫) |
| `main/sound.c` | 효과음: 사각파 가락을 만들어 스피커(ES8311)로 낸다 |
| `main/board.c` | 보드에 붙은 일: 화면·터치 켜기, 가로 회전, 글꼴 읽기 |
| `main/update.c` | 자동 업데이트: 깃허브 릴리스의 새 판을 받아 바꾼다 |
| `main/ota.c` | 손으로 보내는 업데이트 서버(`/`, `/update`)와 상태 보기(`/info`) |
| `main/store.c` | 꺼져도 남는 값(와이파이, 갱신 토큰, 업데이트 번호) |
| `main/assets/` | 글꼴(TTF)과 알밤 그림. `tools/make_assets.py` 가 웹앱의 `fonts/`·`sprites/` 에서 만든다 |
| `partitions.csv` | 앱 칸 두 개(무선 업데이트용) |

웹앱의 대시보드 규칙(`status.js`, `time.js`, `config.js` 의 기준 시간)이나 분유 양 계산(`formula.js`)을 바꾸면 `care_text.c` 도 같이 고친다.

웹앱과 다른 점: 연결이 안 될 때 기록을 쌓아 두었다가 보내지 않는다. 못 보내면 "저장 못 했어요. 다시 눌러 주세요"로 끝난다.

## 보드 없이 확인하기

```sh
# 글 규칙 시험(웹앱 tests/unit/logic.test.mjs 와 같은 경우들)
cc -I main test/test_care_text.c main/care_text.c -o /tmp/test_care_text && /tmp/test_care_text

# 화면 미리 보기: ui.c 를 PC 에서 그려 sim/out/*.png 로 남긴다(통신은 가짜 값)
sim/build.sh
```

미리 보기는 화면 배치와 글이 넘치는지를 보는 용도다. 통신(`care.c`)과 보드 쪽(`board.c`)은 들어가지 않는다.

## 보드에서 확인할 것

빌드는 깃허브 Actions 가 확인한다. 아래는 보드에 구워야 알 수 있다.

- 화면이 바로 서 있는지. 거꾸로면 `sdkconfig.local` 에 `CONFIG_ALBAM_ROTATE_270=y` 를 넣는다.
- 로그인이 되고 대시보드 숫자가 S10 웹앱과 같은지(0.2.0 에서 확인).
- 보드에서 넣은 기록이 S10 웹앱에 그대로 보이는지, [취소]가 되는지.
- 누른 자리가 맞는지. 대각선 반대쪽이 눌리면 `CONFIG_ALBAM_TOUCH_FLIP=y` 를 넣는다.
- 화면이 멈추지 않는지(시계가 계속 가는지). 0.2.2 에서 화면이 통째로 멈췄다. 화면을 돌려 옮기는 P4 그림 가속기(PPA)가 멈추는 문제로 보고, 그 일을 CPU 로 하게 바꿨다(`board.c` 의 `__wrap_ppa_do_scale_rotate_mirror`).
- 와이파이가 붙는지. 시작 로그에 `Version mismatch: Host [2.13.0] > Co-proc [0.0.0]` 경고가 나온다(보드의 C6 칩 펌웨어가 오래됨). 와이파이 찾기나 연결이 안 되면 C6 펌웨어를 올려야 한다.
- 밝기가 바뀌는지(`CONFIG_ALBAM_BRIGHTNESS`). 백라이트는 GPIO 26 의 PWM 이고 `bsp_display_brightness_set()` 으로 켠다. 시작 로그에 `ledc: GPIO 26 is not usable` 경고가 나온다.
- 무선으로 보낸 판이 켜지고, 일부러 잘못된 판을 보냈을 때 되돌아가는지.
