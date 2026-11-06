# 알밤케어 거실 화면 (1단계)

거실 갤럭시 S10(가로)에 띄워 두고 세훈이 수유·기저귀를 터치와 음성으로 기록하는 웹앱.

- 주소: `https://rosewein.github.io/albam/` (GitHub Pages)
- 미리 보기(가짜 데이터, 이 기기에만 저장): `https://rosewein.github.io/albam/?demo`
- **설계·코드 안내: [docs/TECHNICAL.md](docs/TECHNICAL.md)** — 구조도, 데이터·함수 계약, 모듈 관계, 흐름, 고치고 늘리는 법

빌드도 의존성도 없다. 파일을 고쳐 올리면 그대로 반영된다.

## 폰에서 확인하기

화면은 GitHub Pages 로 나가므로 **이 작업 브랜치가 `master` 에 합쳐져야** 폰에서 열린다(합친 뒤 1~2분).

1. 폰 브라우저(아이폰 사파리·안드로이드 크롬 모두 됨)로 `https://rosewein.github.io/albam/?demo` 를 연다.
   Supabase 설정 없이 가짜 데이터로 돈다. 기록은 그 폰에만 남는다.
2. **폰을 가로로** 돌린다. 세로로 보면 아주 작게 보인다.
3. 눌러 볼 것: [수유] → 양 → 저장 → "저장됨 [취소 6]", 같은 걸 또 넣으면 확인 창, [수유] → [빠른 선택 바꾸기], [지난 기록 넣기] → [최근 기록].
4. **"대기 n건" 보기**: 화면이 뜬 상태에서 **비행기 모드를 켜고** [기저귀] → [대변].
   위쪽에 주황색 "대기 1건"이 뜨고 상태 칸은 바로 바뀐다. 비행기 모드를 끄면 몇 초 안에(늦어도 20초) "대기"가 사라지고 "미리 보기"로 돌아온다.
5. 처음 상태로 되돌리려면 브라우저의 사이트 데이터를 지운다.

음성([말하기])은 안드로이드 크롬에서 확인한다(아이폰은 브라우저에 따라 안 될 수 있다).
실제 Supabase 로 확인하려면 아래 설정을 마치고 `?demo` 없이 연다.

## 처음 설정

### 1. Supabase (알밤위키 프로젝트)

1. 대시보드에서 프로젝트가 **일시정지(Paused)** 상태면 Restore 한다.
2. Table Editor에서 기존 표를 확인한다. 새 표는 모두 `care_` 로 시작해 겹치지 않는다.
3. SQL Editor에 [`supabase/001_care_schema.sql`](supabase/001_care_schema.sql), [`002_feed_amounts.sql`](supabase/002_feed_amounts.sql)을 **차례로** 붙여 실행한다(여러 번 실행해도 안전).
4. Authentication → Users → Add user 로 가족 계정을 만든다(이메일+비밀번호, Auto confirm). 거실 기기용 계정을 따로 두면 기기만 로그아웃시키기 쉽다.
5. 가족으로 등록한다. 여기 없는 계정은 로그인해도 아무것도 못 읽고 못 쓴다.
   ```sql
   insert into public.care_family (user_id, name)
   select id, '이지' from auth.users where email = '이지 이메일';
   ```
6. Authentication → Providers → Email 에서 회원가입(Allow new users to sign up)을 끈다.
7. Project Settings → API 의 Project URL과 `anon` key를 [`config.js`](config.js) 에 넣는다(비워 두면 기기 첫 화면에서 넣음). **service_role 키는 넣지 않는다.**

### 2. 거실 S10

1. 초기화 후 필요한 앱만 남기고, 배터리 보호(85% 제한)를 켠다.
2. 크롬으로 주소를 열고 로그인 → 메뉴 → **홈 화면에 추가**. 아이콘으로 열면 전체 화면 가로로 뜬다.
3. 처음 [말하기] 때 마이크 권한 **허용**.
4. 설정 → 보안 → **앱 고정**으로 알밤케어를 고정한다. 밝기는 낮게.

### 3. 베이비타임 지난 기록

```sh
python3 tools/import_babytime.py --until 2026-11-10 activity_세훈_*.zip -o import.sql
```

`import.sql` 을 SQL Editor에서 실행한다(두 번 넣어도 한 번만 들어감). `--until` 은 거실 화면을 쓰기 시작한 날.
끝에 "모르는 종류/항목" 보고가 나오면 스크립트의 `TYPE_MAP`·`*_KEYS` 를 맞춘다.

## 바꾸기 쉬운 값

| 무엇 | 지금(임시값) | 바꾸는 곳 |
| --- | --- | --- |
| 하루 끊는 시각 | 자정 | `care_settings.day_start_hour` |
| 같은 종류 확인 간격 | 10분 | `care_settings.dup_window_minutes` |
| 수유량 빠른 선택 | 180·200·220 | 화면: [수유] → [빠른 선택 바꾸기] (모든 기기에 같이 적용) |
| 밤 화면 | 21~6시, 터치하면 30초 | `config.js nightStartHour·nightEndHour·nightWakeSeconds` |
| 저장 직후 취소 / 음성 자동 저장 | 6초 / 4초 | `config.js undoSeconds·voiceConfirmSeconds` |
| 다른 기기 기록 다시 읽기 | 20초 | `config.js pollSeconds` |
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
| 음성 "수유 160", "기저귀 대변" | 규칙 시험 통과, **S10 실기 확인 필요** |
| 낮 켜짐, 밤 어둡게, 위치 이동 | 브라우저 시험 통과, Wake Lock **실기 확인 필요** |
| 로그인 안 하면 읽기·쓰기 불가 | SQL 시험 통과 |
| 베이비타임 기록 반영 | 스크립트 완료, **실제 파일로 확인 필요** |
| 24시간 켜 두기 | 하루 한 번 새로 고침, **실기 확인 필요** |

글꼴: 갈무리(Galmuri) — SIL Open Font License 1.1, [`fonts/OFL-Galmuri.txt`](fonts/OFL-Galmuri.txt)
