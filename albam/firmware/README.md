# 알밤보드 P4 펌웨어

거실 S10 대신 쓸 보드(Waveshare ESP32-P4-WIFI6-Touch-LCD-7, 7인치 올인원)의 첫 펌웨어다.
화면은 ILI9881C(세로 720×1280), 터치는 GT9271 이다. 보드 지원 패키지는 `waveshare/esp32_p4_wifi6_touch_lcd_x` 를 쓰고 7인치를 고른다(`CONFIG_BSP_LCD_TYPE_720_1280_7_INCH`).
아직 육아 기록 화면은 없다. 선으로 한 번 구운 뒤부터 무선으로 새 판을 보낼 수 있게 하는 뼈대다.

| 들어 있는 것 | 내용 |
| --- | --- |
| 와이파이 | 처음 켜면 화면에서 와이파이를 고르고 비밀번호를 넣는다. 보드에 저장된다 |
| 한국 시간 | 인터넷 시간(NTP)을 받아 한국 시간으로 시계를 보여 준다 |
| 가로 화면 | 세로 패널을 90도 돌려 1280×720 가로로 쓴다. 시계, 날짜, 연결 상태, 판 번호 |
| 무선 업데이트 | 같은 와이파이에서 `http://albam-board.local/` 로 새 `.bin` 을 보낸다 |

화면 글자는 아직 숫자와 영문뿐이다. LVGL 기본 글꼴에 한글이 없어서, 한글은 화면을 옮길 때 넣는다.

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

## 그다음부터: 무선으로 보내기

보드 화면 아래에 `OTA code 123456` 같은 6자리 번호가 나온다. 이 번호를 아는 사람만 새 판을 보낼 수 있다.

- 브라우저: `http://albam-board.local/` (안 열리면 화면에 나온 주소)에서 `build/albam_board.bin` 을 고르고 번호를 넣는다.
- 명령줄: `tools/ota.sh 123456` (주소를 직접 주려면 `tools/ota.sh 123456 192.168.0.12`)

새 판은 켜진 뒤 2분 안에 와이파이에 붙어야 확정된다. 못 붙으면 스스로 앞 판으로 되돌아간다.
와이파이가 안 되는 판이 올라가면 무선으로 고칠 길이 없기 때문이다.

새 판을 보낼 때는 `CMakeLists.txt` 의 `PROJECT_VER` 를 올린다. 화면 아래와 `/info` 에서 확인할 수 있다.

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
| `main/ota.c` | 무선 업데이트 서버(`/`, `/info`, `/update`) |
| `main/ui.c` | 시계 화면과 와이파이 고르기 화면(LVGL 9) |
| `main/store.c` | 꺼져도 남는 값(와이파이, 업데이트 번호) |
| `partitions.csv` | 앱 칸 두 개(무선 업데이트용) |

## 보드에서 확인할 것

빌드는 깃허브 Actions 가 확인한다. 아래는 보드에 구워야 알 수 있다.

- 화면이 바로 서 있는지. 거꾸로면 `sdkconfig.local` 에 `CONFIG_ALBAM_ROTATE_270=y` 를 넣는다.
- 누른 자리가 맞는지. 대각선 반대쪽이 눌리면 `CONFIG_ALBAM_TOUCH_FLIP=y` 를 넣는다.
- 화면이 멈추지 않는지. 돌린 화면은 `DOUBLE_PARTIAL` 방식으로 그린다(`ui.c` 의 `start_landscape()`).
- 와이파이가 붙는지. 보드의 C6 칩에 들어 있는 펌웨어가 오래됐으면 시작 로그에 판이 안 맞는다는 경고가 나온다.
- 무선으로 보낸 판이 켜지고, 일부러 잘못된 판을 보냈을 때 되돌아가는지.
