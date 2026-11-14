# 알밤보드 거실 화면 (1단계)

거실 갤럭시 S10(가로)에 띄워 두고 세훈이 수유·기저귀를 터치와 음성으로 기록하는 웹앱.
지금은 육아 기록이 중심이지만, 궁극적으로는 **집안 전체를 돌보는 가정 관리 보드**로 넓히는 게 목표다(할 일·집안일·가족 일정 등).
이름은 2026-11-10 '알밤케어'에서 '알밤보드'로 바꿨다. 주소(`/albam/`)와 Supabase 이름(`care_…` 표·함수)은 그대로 둔다.

- 주소: `https://rosewein.github.io/albam/` (GitHub Pages)
- 미리 보기(가짜 데이터, 이 기기에만 저장): `https://rosewein.github.io/albam/?demo`
- **설계·코드 안내: [docs/TECHNICAL.md](docs/TECHNICAL.md)** — 구조도, 데이터·함수 계약, 모듈 관계, 흐름, 고치고 늘리는 법

빌드도 의존성도 없다. 파일을 고쳐 올리면 그대로 반영된다.

## 폰에서 확인하기

화면은 GitHub Pages 로 나가므로 **이 작업 브랜치가 `master` 에 합쳐져야** 폰에서 열린다(합친 뒤 1~2분).

1. 폰 브라우저(아이폰 사파리·안드로이드 크롬 모두 됨)로 `https://rosewein.github.io/albam/?demo` 를 연다.
   Supabase 설정 없이 가짜 데이터로 돈다. 기록은 그 폰에만 남는다.
2. **폰을 가로로** 돌린다. 세로로 보면 아주 작게 보인다.
3. 눌러 볼 것: [수유] → 양 → 저장 → "저장됨 [취소 6]", 같은 걸 또 넣으면 확인 창, [수유] → [빠른 선택 바꾸기], [+] → [체온]·[목욕]…, [+] → [지난 기록 넣기], [+] → [오늘 기록].
4. **"대기 n건" 보기**: 화면이 뜬 상태에서 **비행기 모드를 켜고** [기저귀] → [대변].
   위쪽에 주황색 "대기 1건"이 뜨고 상태 칸은 바로 바뀐다. 비행기 모드를 끄면 몇 초 안에(늦어도 20초) "대기"가 사라지고 "미리 보기"로 돌아온다.
5. 처음 상태로 되돌리려면 브라우저의 사이트 데이터를 지운다.

호출어: 오른쪽 마이크 버튼을 누르면 켜진다(처음엔 꺼짐, 주황이면 듣는 중). "알밤이 쉬야했어 / 응아 / 기저귀 / 밥먹었어 / 목욕했어 / 코자 / 깼다"라고 말하면 크게 띄우고 4초 뒤 저장, 그 전에 누르면 취소. 처음 켤 때 모델 87MB 를 받는다. 안드로이드 크롬에서 확인한다.
실제 Supabase 로 확인하려면 아래 설정을 마치고 `?demo` 없이 연다.

## 처음 설정

### 1. Supabase (알밤위키 프로젝트)

1. 대시보드에서 프로젝트가 **일시정지(Paused)** 상태면 Restore 한다.
2. Table Editor에서 기존 표를 확인한다. 새 표는 모두 `care_` 로 시작해 겹치지 않는다.
3. SQL Editor에 [`supabase/001_care_schema.sql`](supabase/001_care_schema.sql), [`002_feed_amounts.sql`](supabase/002_feed_amounts.sql), [`003_stats.sql`](supabase/003_stats.sql), [`004_sleep_end.sql`](supabase/004_sleep_end.sql), [`005_timeline.sql`](supabase/005_timeline.sql), [`006_edit_and_age.sql`](supabase/006_edit_and_age.sql), [`007_feed_duration.sql`](supabase/007_feed_duration.sql), [`008_record_types.sql`](supabase/008_record_types.sql), [`009_last_poo.sql`](supabase/009_last_poo.sql), [`010_feed_gap.sql`](supabase/010_feed_gap.sql), [`011_feed_gaps.sql`](supabase/011_feed_gaps.sql), [`012_voice_log.sql`](supabase/012_voice_log.sql), [`013_walk_vaccine.sql`](supabase/013_walk_vaccine.sql), [`014_measures.sql`](supabase/014_measures.sql), [`015_appointments.sql`](supabase/015_appointments.sql)을 **차례로** 붙여 실행한다(여러 번 실행해도 안전).
4. Authentication → Users → Add user 로 가족 계정을 만든다(이메일+비밀번호, Auto confirm). 거실 기기용 계정을 따로 두면 기기만 로그아웃시키기 쉽다.
5. 가족으로 등록한다. 여기 없는 계정은 로그인해도 아무것도 못 읽고 못 쓴다.
   ```sql
   insert into public.care_family (user_id, name)
   select id, '이지' from auth.users where email = '이지 이메일';
   ```
6. Authentication → Providers → Email 에서 회원가입(Allow new users to sign up)을 끈다.
7. Project Settings → API 의 Project URL과 publishable(또는 `anon`) key를 [`config.js`](config.js) 에 넣는다(비워 두면 기기 첫 화면에서 넣음). **service_role 키는 넣지 않는다.**
   지금은 `baby_archive_AlbamWiki` 프로젝트에 연결돼 있고 001~011 실행, 이지·준희 계정 가족 등록, 회원가입 끄기까지 끝났다(2026-11-07).

### 2. 거실 S10

1. 초기화 후 필요한 앱만 남기고, 배터리 보호(85% 제한)를 켠다.
2. 크롬으로 주소를 열고 로그인 → 메뉴 → **홈 화면에 추가**. 아이콘으로 열면 전체 화면 가로로 뜬다.
3. 처음 마이크 버튼을 누를 때 마이크 권한 **허용**.
4. 설정 → 보안 → **앱 고정**으로 알밤보드를 고정한다. 밝기는 낮게.

### 3. 베이비타임 지난 기록

```sh
python3 tools/import_babytime.py --until 2026-11-10 activity_세훈_*.zip -o import.sql
```

`import.sql` 을 SQL Editor에서 실행한다(두 번 넣어도 한 번만 들어감). `--until` 은 거실 화면을 쓰기 시작한 날.
기록 한 건이 한 줄(`종류|시작|끝|ml|세부`)이고 id 는 그 줄의 md5 라서, 파일이 커서 한 번에 안 들어가면 줄을 나눠 여러 번 실행해도 된다.

2026-11-07 에 2026-07-07 ~ 11-07 08:30 기록 2,283건(수유 700, 기저귀 960, 잠 623)을 넣었다. 2026-11-08 에 수유 '소요시간' 463건을 다 먹은 시각으로 채웠고, 그 밖의 기록 154건(목욕 108, 체온 13, 투약 13, 터미타임 7, 놀이 7, 병원 5, 기타 1)도 넣었다(유축·이유식·간식·성장은 아직 안 옮김). 그 뒤 기록은 거실 화면의 [+] 더보기로 넣는다.

**통계 맞춰 보기**: `--stats stats.md` 를 붙이면 날짜별 수유 횟수·양, 기저귀, 잠 합계 표를 만든다. 베이비타임 앱의 통계 화면과 비교하고,
넣은 뒤에는 [`supabase/queries/daily_stats.sql`](supabase/queries/daily_stats.sql) 을 SQL Editor에서 돌려 같은 숫자가 나오는지 본다.

```sh
python3 tools/import_babytime.py activity_세훈_*.zip -o import.sql --stats stats.md
# 베이비타임 '통계 내보내기'(stat_*.zip)와 날짜별로 자동 비교
python3 tools/check_babytime_stats.py --activity activity_세훈_*_asc.txt --stat stat_세훈_*.zip
```
2026-11-07 비교 결과: 122일 중 수유는 모든 날 같고, 기저귀는 2일(종류 없이 적힌 기저귀 2건은 옮기지 않음), 잠은 19일(7월 말~8월 초 베이비타임이 밤잠을 다르게 나눔, 8/17) 다르다. 기록 자체는 같다.
끝에 "모르는 종류/항목" 보고가 나오면 스크립트의 `TYPE_MAP`·`*_KEYS` 를 맞춘다.

## 바꾸기 쉬운 값

| 무엇 | 지금(임시값) | 바꾸는 곳 |
| --- | --- | --- |
| 하루 끊는 시각 | 자정 | `care_settings.day_start_hour` |
| 같은 종류 확인 간격 | 10분 | `care_settings.dup_window_minutes` |
| 수유량 빠른 선택 | 200·230·270 (브레짜 180·210·240) | 화면: [수유] → [빠른 선택 바꾸기] (모든 기기에 같이 적용) |
| 분유·기계 | 압타밀, 브레짜(물 30ml 단위). 기록은 완성량 | `config.js formula·machine` |
| 밤 화면 | 21~6시, 터치하면 30초 | `config.js nightStartHour·nightEndHour·nightWakeSeconds` |
| 저장 직후 취소 / 음성 자동 저장 | 6초 / 4초 | `config.js undoSeconds·voiceConfirmSeconds` |
| 다른 기기 기록 다시 읽기 | 20초 | `config.js pollSeconds` |
| 통계 쪽 날 수 / 안 만지면 대시보드로 | 7일 / 60초(타임라인·통계) | `config.js statsDays·statsIdleSeconds` |
| 밝은/어두운 화면 | 해 뜬 동안 밝게(서울 기준) | `config.js theme·location` |
| 캐릭터 배고픔 | 수유 후 3시간 | `config.js hungryMinutes` |
| 캐릭터 그림 | 밤톨 도트 | `tools/make_sprites.py` → `npm run sprites` |

```sql
update public.care_settings set value = '5' where key = 'day_start_hour';  -- 새벽 5시에 하루를 끊기
```

## 개발

```sh
npm run serve        # http://localhost:8000/albam/?demo
npm test             # 순수 함수·음성 규칙·가져오기 (Node 22+, Python 3.9+)
npm run test:sql     # SQL (PostgreSQL 14+)
npm run test:e2e     # S10 크기 브라우저 시험 (Playwright)
```

파일을 더하면 `sw.js` 의 `FILES` 에 넣고 `VERSION` 을 올린다(빠뜨리면 `npm test` 가 알려 줌).

## 1단계 완료 기준

| 기준 | 상태 |
| --- | --- |
| 수유 양 고르면 기록, 상태 칸 바로 바뀜 | 브라우저 시험 통과 |
| 지난 시간("2시간 35분 전") 스스로 올라감 | 구현(서버 시각 보정) |
| 다른 기기 기록 1분 안 반영 | 20초 주기 |
| 10분 안 같은 종류 확인 | SQL·브라우저 시험 통과 |
| 저장 직후 취소, 취소 표시만 | SQL·브라우저 시험 통과 |
| 고쳐 넣은 기록이 실제 시각 순서로 | SQL·브라우저 시험 통과 |
| Wi-Fi 끊고 기록 → 재연결 시 들어감 | 브라우저 시험 통과(가짜 Supabase) |
| 호출어 "알밤이 ○○" → 확인 → 저장 | 규칙·브라우저 시험(가짜 마이크) 통과, **S10 실기 확인 필요** |
| 낮 켜짐, 밤 어둡게, 위치 이동 | 브라우저 시험 통과, Wake Lock **실기 확인 필요** |
| 로그인 안 하면 읽기·쓰기 불가 | SQL 시험 통과 |
| 베이비타임 기록 반영 | 스크립트 완료, **실제 파일로 확인 필요** |
| 24시간 켜 두기 | 하루 한 번 새로 고침, **실기 확인 필요** |

글꼴: 프리텐다드(Pretendard) — SIL Open Font License 1.1, [`fonts/OFL-Pretendard.txt`](fonts/OFL-Pretendard.txt)
