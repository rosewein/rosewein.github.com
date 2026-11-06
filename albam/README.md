# 알밤케어 거실 화면 (1단계)

거실 갤럭시 S10(가로)에 띄워 두고 세훈이 수유·기저귀를 터치와 음성으로 기록하는 웹앱.
기준 문서는 '육아가정 대시보드 착수 문서'(2026-11-06)다.

- 주소(GitHub Pages): `https://rosewein.github.io/albam/`
- 미리 보기(이 기기 안에서만 도는 가짜 데이터): `https://rosewein.github.io/albam/?demo`

## 파일

| 파일 | 하는 일 |
| --- | --- |
| `supabase/001_care_schema.sql` | 표(care_events·care_chores·care_family·care_settings), RLS, 요약 함수 `care_summary()`, 기록 추가 `care_add_event()`, 취소 `care_cancel_event()` |
| `index.html`, `app.js` | 거실 화면. 논리 해상도 380×180을 기기 화소의 정수배로 키움 |
| `api.js` | 통신 전부. `getSummary()`, `addEvent()` (+ 저장 직후 취소용 `cancelEvent()`). 못 보낸 기록은 IndexedDB에 쌓았다 다시 보냄 |
| `demo-api.js` | `?demo` 일 때 쓰는 가짜 통신 |
| `voice-parse.js` | 음성 문장 → 기록 규칙 ("수유 160 20분 전", "기저귀 대변", "잠 1시 10분부터 2시 40분까지", 한글 수사 포함) |
| `config.js` | Supabase 주소·anon key, 밤 시간대 등 바꾸기 쉬운 설정값 |
| `sprites/` | 캐릭터·아이콘 PNG 스프라이트 시트와 칸 위치(`sprites.json`). `tools/make_sprites.py` 로 만듦. ESP32에서도 그대로 씀 |
| `fonts/` | 갈무리 도트 글꼴(Galmuri11·9, SIL OFL 1.1 — `fonts/OFL-Galmuri.txt`) |
| `tools/import_babytime.py` | 베이비타임 월별 내보내기(txt/zip) → `care_events` 넣는 SQL |
| `tests/` | SQL·음성 규칙·가져오기 시험 |

## 처음 설정

### 1. Supabase (알밤위키 프로젝트)

1. 대시보드에서 알밤위키 프로젝트가 **일시정지(Paused)** 상태인지 본다. 무료 요금제는 오래 안 쓰면 멈추므로 Restore 한다.
   거실 화면이 매일 부르니 다시 멈추지는 않는다.
2. Table Editor에서 기존 표 이름을 확인한다. 새 표는 모두 `care_` 로 시작해서 기존 표와 겹치지 않게 했다.
   따로 두고 싶으면 새 프로젝트를 만들어도 SQL은 그대로 쓸 수 있다.
3. SQL Editor에 `supabase/001_care_schema.sql` 전체를 붙여 실행한다(여러 번 실행해도 안전).
4. Authentication → Users → Add user 로 가족 계정을 만든다(이메일+비밀번호, "Auto confirm" 체크).
   거실 기기용 계정을 따로 하나 두면 나중에 기기만 로그아웃시키기 쉽다.
5. 만든 계정을 가족으로 등록한다. 여기 없는 계정은 로그인해도 아무것도 못 읽고 못 쓴다.
   ```sql
   insert into public.care_family (user_id, name)
   select id, '이지' from auth.users where email = '이지 이메일';
   ```
6. Authentication → Providers → Email 에서 회원가입(Allow new users to sign up)을 끈다. 계정은 위처럼 직접만 만든다.
7. Project Settings → API 의 Project URL과 `anon` key를 `config.js` 에 넣고 커밋한다.
   (비워 두면 첫 화면에서 기기마다 넣을 수 있다.) **service_role 키는 절대 넣지 않는다.**

설정값(하루 끊는 시각, 같은 종류 확인 간격 등)은 `care_settings` 표에서 바꾼다.

```sql
update public.care_settings set value = '5' where key = 'day_start_hour';      -- 새벽 5시에 하루를 끊기
update public.care_settings set value = '15' where key = 'dup_window_minutes'; -- 확인 간격 15분
```

### 2. 호스팅

이 저장소가 이미 GitHub Pages(HTTPS, 무료)로 `/log/` 앱을 내보내고 있어서 같은 곳에 `/albam/` 으로 두었다.
main에 합치면 바로 올라간다. 음성 인식·화면 켜짐 유지·홈 화면 앱 모두 HTTPS가 필요한데 Pages가 기본으로 HTTPS다.
저장소가 공개라면 코드와 anon key가 보이지만, 기록은 RLS로 가족 계정만 읽고 쓸 수 있다.

### 3. 거실 S10

1. 초기화 후 필요한 앱만 남기기, 설정 → 배터리 → 배터리 보호(85% 제한) 켜기.
2. 크롬으로 주소를 열고 로그인 → 메뉴 → **홈 화면에 추가**(앱 설치). 홈 화면 아이콘으로 열면 전체 화면 가로로 뜬다.
3. 처음 [말하기]를 누를 때 마이크 권한 **허용**. 시험 기간에 권한이 계속 유지되는지 본다.
4. 설정 → 보안 → **앱 고정** 켜고 알밤케어를 고정한다.
5. 디스플레이 → 화면 자동 꺼짐은 길게 둬도 되고 짧아도 된다(앱이 Wake Lock으로 켜 둠). 밝기는 낮게.

## 화면 동작

- **수유**: 누르면 양 고르기. 최근 먹인 양 세 가지(없으면 120·140·160)와 ±5·±10. 기본은 마지막으로 먹인 양.
- **기저귀**: 소변·대변·둘 다 중 누르면 바로 저장.
- **저장 직후**: 효과음, "저장됨", 6초 동안 [취소]. 취소한 기록은 지우지 않고 `deleted_at` 만 찍힌다.
- **같은 종류가 10분 안에 또 들어오면** 한 번 확인을 묻는다(연결이 끊겼을 때는 기기 안의 최근 기록으로 확인).
- **지난 기록 넣기**: 종류를 고르고 ±1분·10분·1시간으로 시각을 맞춘다. 잠은 시작·끝을 따로. [최근 기록]에서 실제 시각 순서로 자리 잡은 것을 본다.
- **말하기**: 한 번 누르면 듣는다. 알아들은 내용을 4초 띄우고 자동 저장, 그 전에 화면을 누르면 취소. 못 알아들으면 원문을 보여 주고 다시 말해 달라고 한다. 원문은 `voice_text` 에 남는다.
- **다른 기기 기록**: 20초마다 요약을 다시 읽는다(Realtime 구독 대신 짧은 주기 읽기).
- **연결이 끊기면**: 기록을 기기 안에 쌓고 오른쪽 구석에 "대기 n건". 연결되면 순서대로 보낸다. 앱을 다시 열어도 남아 있다.
- **번인 대비**: 어두운 바탕, 3분마다 화면 전체를 1~2 논리 픽셀 이동, 좌우 곡면 16 논리 픽셀은 비움.
- **밤(21~6시)**: 거의 검은 화면에 아주 어두운 글자(경과 시간·시각)만, 1분마다 자리 이동. 터치하면 30초 동안 어둡게 밝아진다.
- **24시간**: 하루 한 번 새벽 4시에, 아무도 만지지 않고 있으면 새로 고친다.
- 캐릭터(밤톨): 평소 / 수유 3시간 넘으면 배고픔(경과 시간도 주황) / 밤에는 잠 / 저장하면 기쁨.

## 시험

```sh
node --test tests/*.test.mjs                               # 음성 규칙
python3 -m unittest discover -s tests -p 'test_*.py'       # 베이비타임 가져오기
tests/run_sql_tests.sh                                     # SQL (로컬 PostgreSQL 14+ 필요)
python3 tools/make_sprites.py                              # 그림을 고쳤을 때
```

## 베이비타임 지난 기록 옮기기

```sh
python3 tools/import_babytime.py --until 2026-11-10 activity_세훈_*.zip -o import.sql
```

`import.sql` 을 SQL Editor에서 실행한다. 같은 파일을 두 번 넣어도 한 번만 들어간다.
`--until` 에는 거실 화면을 쓰기 시작한 날을 넣어 겹치지 않게 한다.
형식은 babyTimeR 의 영어 예시 파일로 맞췄고, 한국어 항목 이름은 짐작이다. 실행 끝의 보고에
"모르는 종류/항목"이 나오면 스크립트의 `TYPE_MAP`·`*_KEYS` 를 맞추면 된다. 엄마 유축·투약·이유식 등은 옮기지 않고 개수만 보고한다.

## 1단계 완료 기준과 상태

| 기준 | 상태 |
| --- | --- |
| 수유 양 고르면 기록, 상태 칸 바로 바뀜 | 구현·브라우저 시험 |
| 경과 시간 스스로 올라감 | 구현 (서버 시각과의 차이 보정) |
| 다른 기기 기록 1분 안 반영 | 20초 주기 읽기 |
| 10분 안 같은 종류 확인 | 구현·SQL 시험 |
| 저장 직후 취소, 취소 표시만 | 구현·SQL 시험 |
| 고쳐 넣은 기록이 실제 시각 순서로 | 구현·SQL 시험 |
| Wi-Fi 끊고 기록 → 재연결 시 들어감 | 구현·브라우저 시험(가짜 Supabase) |
| 음성 "수유 160", "기저귀 대변" | 규칙 시험 완료. **S10 실기 시험 필요** |
| 낮 켜짐, 밤 어둡게, 위치 이동 | 구현·브라우저 시험. Wake Lock은 **실기 확인 필요** |
| 로그인 안 하면 읽기·쓰기 불가 | RLS·권한 SQL 시험 |
| 베이비타임 기록 반영 | 스크립트 완료. **실제 내보내기 파일로 확인 필요** |
| 24시간 켜 두기 | 하루 한 번 새로 고침. **실기 확인 필요** |

## 아직 정할 것 (임시값으로 진행 중)

| 질문 | 임시값 | 바꾸는 곳 |
| --- | --- | --- |
| 수유량 빠른 선택 | 최근 먹인 서로 다른 양 3개 | `care_settings.quick_amount_count`, `config.js defaultAmounts` |
| 하루 끊는 시각 | 자정 | `care_settings.day_start_hour` |
| 밤 화면 시간대 | 21~6시 | `config.js nightStartHour/nightEndHour` |
| 캐릭터 그림 | 밤톨 도트 | `tools/make_sprites.py` |
| 같은 종류 확인 간격 | 10분 | `care_settings.dup_window_minutes` |
| 기록한 사람 표시 | 저장만(`recorded_by`), 화면에는 안 띄움 | — |
| 호스팅 | GitHub Pages | — |
