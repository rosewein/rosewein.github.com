-- 001_care_schema.sql 시험. tests/sql/run.sh 가 부른다.
\set ON_ERROR_STOP on
\set QUIET on

insert into auth.users values
  ('11111111-1111-1111-1111-111111111111', 'izzy@example.com'),
  ('22222222-2222-2222-2222-222222222222', 'stranger@example.com');
insert into public.care_family (user_id, name) values ('11111111-1111-1111-1111-111111111111', '이지');

create function pg_temp.check(ok boolean, label text) returns void language plpgsql as $$
begin
  if not ok then raise exception 'FAIL: %', label; end if;
  raise notice 'ok - %', label;
end $$;

-- ── 로그인 안 한 사람(anon) ─────────────────────────────
set role anon;
do $$ begin
  perform 1 from public.care_events;
  raise exception 'FAIL: anon read events';
exception when insufficient_privilege then raise notice 'ok - anon cannot read events';
end $$;
do $$ begin
  perform public.care_summary();
  raise exception 'FAIL: anon summary';
exception when insufficient_privilege then raise notice 'ok - anon cannot call summary';
end $$;
do $$ begin
  perform public.care_add_event('{"kind":"feed","amount_ml":100}');
  raise exception 'FAIL: anon add';
exception when insufficient_privilege then raise notice 'ok - anon cannot add';
end $$;
reset role;

-- ── 가족이 아닌 로그인 사용자 ────────────────────────────
set role authenticated;
set request.jwt.claim.sub = '22222222-2222-2222-2222-222222222222';
do $$ begin
  perform public.care_add_event('{"kind":"feed","amount_ml":100}');
  raise exception 'FAIL: stranger add';
exception when insufficient_privilege then raise notice 'ok - non-family cannot add';
end $$;
do $$ begin
  perform public.care_set_feed_amounts(array[100]);
  raise exception 'FAIL: stranger set amounts';
exception when insufficient_privilege then raise notice 'ok - non-family cannot change feed amounts';
end $$;
do $$ begin
  perform public.care_summary();
  raise exception 'FAIL: stranger summary';
exception when insufficient_privilege then raise notice 'ok - non-family cannot read summary';
end $$;
do $$ begin
  insert into public.care_events (kind, occurred_at) values ('feed', now());
  raise exception 'FAIL: direct insert';
exception when insufficient_privilege then raise notice 'ok - no direct insert';
end $$;

-- ── 가족 ────────────────────────────────────────────────
set request.jwt.claim.sub = '11111111-1111-1111-1111-111111111111';

do $$ begin
  insert into public.care_events (kind, occurred_at) values ('feed', now());
  raise exception 'FAIL: family direct insert';
exception when insufficient_privilege then raise notice 'ok - family writes only through functions';
end $$;

do $$
declare r jsonb; s jsonb;
begin
  -- 빈 상태 요약
  s := public.care_summary();
  perform pg_temp.check(s -> 'last_feed' = 'null'::jsonb, 'empty summary has null last_feed');
  perform pg_temp.check((s #>> '{today,feed_count}')::int = 0, 'empty today count 0');

  r := public.care_add_event(jsonb_build_object('id', 'aaaaaaaa-0000-0000-0000-000000000001', 'kind', 'feed',
         'amount_ml', 160, 'occurred_at', now() - interval '30 minutes'));
  perform pg_temp.check(r ->> 'status' = 'saved', 'feed saved');

  -- 같은 id 재전송 → 한 번만
  r := public.care_add_event(jsonb_build_object('id', 'aaaaaaaa-0000-0000-0000-000000000001', 'kind', 'feed',
         'amount_ml', 160, 'occurred_at', now() - interval '30 minutes'));
  perform pg_temp.check(r ->> 'status' = 'saved' and (r ->> 'repeat')::boolean, 'resend is idempotent');
  perform pg_temp.check((select count(*) from public.care_events) = 1, 'only one row after resend');

  -- 10분 안 같은 종류 → 확인
  r := public.care_add_event(jsonb_build_object('kind', 'feed', 'amount_ml', 120, 'occurred_at', now() - interval '25 minutes'));
  perform pg_temp.check(r ->> 'status' = 'confirm', 'duplicate within window asks to confirm');
  perform pg_temp.check((r #>> '{existing,ml}')::int = 160, 'confirm returns existing record');
  perform pg_temp.check((select count(*) from public.care_events) = 1, 'confirm does not save');

  -- force 로 저장
  r := public.care_add_event(jsonb_build_object('id', 'aaaaaaaa-0000-0000-0000-000000000002', 'kind', 'feed',
         'amount_ml', 120, 'occurred_at', now() - interval '25 minutes', 'force', true));
  perform pg_temp.check(r ->> 'status' = 'saved', 'force saves');

  -- 다른 종류는 확인 안 함
  r := public.care_add_event(jsonb_build_object('kind', 'diaper', 'detail', jsonb_build_object('type', 'poo'),
         'occurred_at', now() - interval '20 minutes', 'source', 'living_room_voice', 'voice_text', '기저귀 대변'));
  perform pg_temp.check(r ->> 'status' = 'saved', 'diaper saved without confirm');

  -- 잘못된 기저귀 종류
  begin
    perform public.care_add_event('{"kind":"diaper","detail":{"type":"x"}}');
    raise exception 'FAIL: bad diaper type accepted';
  exception when invalid_parameter_value then raise notice 'ok - bad diaper type rejected';
  end;

  -- 미래 시각
  begin
    perform public.care_add_event(jsonb_build_object('kind', 'feed', 'occurred_at', now() + interval '1 hour'));
    raise exception 'FAIL: future accepted';
  exception when invalid_parameter_value then raise notice 'ok - future time rejected';
  end;

  -- 나중에 넣은 기록(3시간 전)은 마지막 수유를 바꾸지 않는다
  r := public.care_add_event(jsonb_build_object('id', 'aaaaaaaa-0000-0000-0000-000000000003', 'kind', 'feed',
         'amount_ml', 90, 'occurred_at', now() - interval '3 hours'));
  s := public.care_summary();
  perform pg_temp.check((s #>> '{last_feed,id}') = 'aaaaaaaa-0000-0000-0000-000000000002', 'late entry keeps real-time order');
  perform pg_temp.check(s -> 'feed_amounts' = '[200, 230, 270]'::jsonb, 'default feed amounts: ' || (s -> 'feed_amounts')::text);
  perform pg_temp.check(not (s ? 'recent_feed_amounts'), 'recent_feed_amounts replaced by feed_amounts');

  -- 수유량 빠른 선택 바꾸기: 정렬·중복 제거
  r := public.care_set_feed_amounts(array[220, 190, 190, 210]);
  perform pg_temp.check(r -> 'feed_amounts' = '[190, 210, 220]'::jsonb, 'feed amounts sorted and deduped');
  perform pg_temp.check(public.care_summary() -> 'feed_amounts' = '[190, 210, 220]'::jsonb, 'summary shows new feed amounts');
  begin
    perform public.care_set_feed_amounts(array[5]);
    raise exception 'FAIL: tiny amount accepted';
  exception when invalid_parameter_value then raise notice 'ok - feed amount out of range rejected';
  end;
  begin
    perform public.care_set_feed_amounts(array[]::int[]);
    raise exception 'FAIL: empty amounts accepted';
  exception when invalid_parameter_value then raise notice 'ok - empty feed amounts rejected';
  end;
  perform pg_temp.check(s #>> '{last_diaper,type}' = 'poo', 'last diaper type');
  perform pg_temp.check((s -> 'recent' -> 0 ->> 'kind') = 'diaper', 'recent sorted by occurred_at');

  -- 수면: 끝이 시작보다 앞이면 거절
  begin
    perform public.care_add_event(jsonb_build_object('kind', 'sleep', 'occurred_at', now() - interval '1 hour', 'ended_at', now() - interval '2 hours'));
    raise exception 'FAIL: reversed sleep accepted';
  exception when invalid_parameter_value then raise notice 'ok - reversed sleep rejected';
  end;
  r := public.care_add_event(jsonb_build_object('kind', 'sleep', 'occurred_at', now() - interval '2 hours', 'ended_at', now() - interval '1 hour'));
  perform pg_temp.check(r ->> 'status' = 'saved', 'sleep with range saved');

  -- 취소: 지우지 않고 표시만
  r := public.care_cancel_event('aaaaaaaa-0000-0000-0000-000000000002');
  perform pg_temp.check(r ->> 'status' = 'cancelled', 'cancel works');
  perform pg_temp.check((select deleted_at is not null from public.care_events where id = 'aaaaaaaa-0000-0000-0000-000000000002'), 'cancelled row kept with deleted_at');
  s := public.care_summary();
  perform pg_temp.check((s #>> '{last_feed,id}') = 'aaaaaaaa-0000-0000-0000-000000000001', 'cancelled feed leaves summary');
  r := public.care_cancel_event('aaaaaaaa-0000-0000-0000-000000000002');
  perform pg_temp.check(r ->> 'status' = 'already_cancelled', 'cancel twice reports already_cancelled');
  r := public.care_cancel_event('aaaaaaaa-0000-0000-0000-00000000ffff');
  perform pg_temp.check(r ->> 'status' = 'not_found', 'cancel unknown id');

  -- recorded_by 가 채워진다
  perform pg_temp.check((select recorded_by from public.care_events where id = 'aaaaaaaa-0000-0000-0000-000000000001')
                        = '11111111-1111-1111-1111-111111111111', 'recorded_by is set');
end $$;

reset role;

-- ── 하루 끊는 시각 ──────────────────────────────────────
-- 서울 기준 오늘 00:10, 어제 23:50 수유. 자정 기준이면 오늘 1회, 새벽 5시 기준이면(지금이 5시 이후라고 가정 못 하므로) day_start 만 확인
truncate public.care_event_history, public.care_events;
insert into public.care_events (kind, occurred_at, amount_ml) values
  ('feed', (date_trunc('day', now() at time zone 'Asia/Seoul') + interval '10 minutes') at time zone 'Asia/Seoul', 100),
  ('feed', (date_trunc('day', now() at time zone 'Asia/Seoul') - interval '10 minutes') at time zone 'Asia/Seoul', 80);
set role authenticated;
set request.jwt.claim.sub = '11111111-1111-1111-1111-111111111111';
do $$
declare s jsonb := public.care_summary();
begin
  perform pg_temp.check((s ->> 'day_start')::timestamptz = (date_trunc('day', now() at time zone 'Asia/Seoul')) at time zone 'Asia/Seoul',
                        'day starts at Seoul midnight');
  perform pg_temp.check((s #>> '{today,feed_count}')::int = case when now() >= (s ->> 'day_start')::timestamptz + interval '10 minutes' then 1 else 0 end,
                        'yesterday 23:50 not counted today');
end $$;
reset role;
update public.care_settings set value = '5' where key = 'day_start_hour';
set role authenticated;
do $$
declare s jsonb := public.care_summary(); h int := extract(hour from now() at time zone 'Asia/Seoul');
begin
  perform pg_temp.check(extract(hour from ((s ->> 'day_start')::timestamptz at time zone 'Asia/Seoul')) = 5, 'day_start_hour=5 moves the cut');
  perform pg_temp.check((s ->> 'day_start')::timestamptz <= now() and (s ->> 'day_start')::timestamptz > now() - interval '1 day', 'day_start within last 24h');
  perform pg_temp.check((s #>> '{settings,day_start_hour}')::int = 5, 'settings exposed');
end $$;
reset role;

-- ── 통계 함수(care_stats): 날짜 규칙 ──
reset role;
update public.care_settings set value = '0' where key = 'day_start_hour';
truncate public.care_event_history, public.care_events;
-- 기준: 어제(서울) y, 오늘 t
create temp table d as select (now() at time zone 'Asia/Seoul')::date as t;
grant select on d to authenticated;
insert into public.care_events (kind, occurred_at, ended_at, amount_ml, detail)
select k, s at time zone 'Asia/Seoul', e at time zone 'Asia/Seoul', ml, det::jsonb from d, (values
  -- 어제 낮 수유 2번
  ('feed',   (select t from d) - 1 + time '10:00', null::timestamp, 200, '{}'),
  ('feed',   (select t from d) - 1 + time '14:00', null, 230, '{}'),
  -- 어제 기저귀 둘 다
  ('diaper', (select t from d) - 1 + time '11:00', null, null, '{"type":"both"}'),
  -- 어제 낮잠 60분
  ('sleep',  (select t from d) - 1 + time '13:00', (select t from d) - 1 + time '14:00', null, '{"when":"day"}'),
  -- 어제 저녁 20시 ~ 오늘 5시 밤잠 540분: 오늘(깨는 아침)로
  ('sleep',  (select t from d) - 1 + time '20:00', (select t from d) + time '05:00', null, '{"when":"night"}'),
  -- when 이 없는 잠(거실 화면): 21시 시작이면 밤잠 → 다음 날, 그래서 오늘 이후라 7일 안 오늘엔 안 들어감
  ('sleep',  (select t from d) - 2 + time '21:00', (select t from d) - 2 + time '23:00', null, '{}')
) as v(k, s, e, ml, det);
set role authenticated;
set request.jwt.claim.sub = '22222222-2222-2222-2222-222222222222';
do $$ begin
  perform public.care_stats(7);
  raise exception 'FAIL: stranger stats';
exception when insufficient_privilege then raise notice 'ok - non-family cannot read stats';
end $$;
set request.jwt.claim.sub = '11111111-1111-1111-1111-111111111111';
do $$
declare st jsonb := public.care_stats(7); y jsonb := st -> 5; t jsonb := st -> 6;
begin
  perform pg_temp.check(jsonb_array_length(st) = 7, 'stats returns 7 days');
  perform pg_temp.check((y ->> 'feed_count')::int = 2 and (y ->> 'feed_ml')::int = 430, 'yesterday feeds');
  perform pg_temp.check((y ->> 'diaper_both')::int = 1 and (y ->> 'diaper_total')::int = 1, 'yesterday diaper both');
  perform pg_temp.check((y ->> 'nap_min')::int = 60, 'nap counted on its own day');
  perform pg_temp.check((y ->> 'night_min')::int = 120, 'evening sleep without when = night of the next day (2 days ago 21-23 → yesterday)');
  perform pg_temp.check((t ->> 'night_min')::int = 540, 'night sleep counted on the waking morning');
  perform pg_temp.check(jsonb_array_length(public.care_stats(1000)) = 92, 'stats capped at 92 days');
end $$;
reset role;

-- ── 004: 잠은 끝 없이 시작하고, 깨면 끝을 채운다 ─────────────
set role authenticated;
set request.jwt.claim.sub = '11111111-1111-1111-1111-111111111111';
do $$
declare r jsonb; s jsonb;
begin
  r := public.care_add_event(jsonb_build_object('id', '33333333-3333-3333-3333-333333333333', 'kind', 'sleep',
         'occurred_at', now() - interval '90 minutes', 'force', true));
  perform pg_temp.check(r ->> 'status' = 'saved', 'sleep can start without an end');
  s := public.care_summary();
  perform pg_temp.check(s -> 'last_sleep' ->> 'id' = '33333333-3333-3333-3333-333333333333' and s -> 'last_sleep' -> 'ended_at' = 'null'::jsonb, 'summary shows the open sleep (sleeping)');
  r := public.care_set_sleep_end('33333333-3333-3333-3333-333333333333', now());
  perform pg_temp.check(r ->> 'status' = 'saved', 'wake: end saved');
  perform pg_temp.check((public.care_summary() -> 'last_sleep' ->> 'ended_at') is not null, 'summary shows the end');
  r := public.care_set_sleep_end('33333333-3333-3333-3333-333333333333', null);
  perform pg_temp.check((public.care_summary() -> 'last_sleep' -> 'ended_at') = 'null'::jsonb, 'undo wake: sleeping again');
  perform pg_temp.check(public.care_set_sleep_end(gen_random_uuid(), now()) ->> 'status' = 'not_found', 'unknown id: not_found');
  begin
    perform public.care_set_sleep_end('33333333-3333-3333-3333-333333333333', now() - interval '3 hours');
    raise exception 'FAIL: end before start accepted';
  exception when sqlstate '22023' then raise notice 'ok - end before start rejected';
  end;
  begin
    perform public.care_set_sleep_end('33333333-3333-3333-3333-333333333333', now() + interval '1 hour');
    raise exception 'FAIL: future end accepted';
  exception when sqlstate '22023' then raise notice 'ok - future end rejected';
  end;
end $$;
set request.jwt.claim.sub = '22222222-2222-2222-2222-222222222222';
do $$ begin
  perform public.care_set_sleep_end('33333333-3333-3333-3333-333333333333', now());
  raise exception 'FAIL: stranger set sleep end';
exception when insufficient_privilege then raise notice 'ok - non-family cannot end sleep';
end $$;
reset role;

-- ── 005: 타임라인 ─────────────────────────────
set role authenticated;
set request.jwt.claim.sub = '11111111-1111-1111-1111-111111111111';
do $$
declare tl jsonb := public.care_timeline(3); ats timestamptz[];
begin
  perform pg_temp.check(jsonb_typeof(tl) = 'array' and jsonb_array_length(tl) > 0, 'timeline returns events');
  select array_agg((x ->> 'at')::timestamptz order by ord) into ats from jsonb_array_elements(tl) with ordinality as a(x, ord);
  perform pg_temp.check(ats = (select array_agg(v order by v) from unnest(ats) v), 'timeline in time order');
  perform pg_temp.check(not exists (select 1 from jsonb_array_elements(tl) x where (x ->> 'at')::timestamptz < now() - interval '4 days'), 'only recent days (plus overnight sleep)');
  perform pg_temp.check(exists (select 1 from jsonb_array_elements(tl) x where x ->> 'kind' = 'diaper' and x ->> 'type' is not null), 'diaper type included');
  perform pg_temp.check(jsonb_array_length(public.care_timeline(1)) <= jsonb_array_length(tl), 'fewer days, fewer events');
end $$;
set request.jwt.claim.sub = '22222222-2222-2222-2222-222222222222';
do $$ begin
  perform public.care_timeline(3);
  raise exception 'FAIL: stranger timeline';
exception when insufficient_privilege then raise notice 'ok - non-family cannot read timeline';
end $$;
reset role;

-- ── 006: 고치기, 고친 내역, 나이 ─────────────
set role authenticated;
set request.jwt.claim.sub = '11111111-1111-1111-1111-111111111111';
do $$
declare v_id uuid := gen_random_uuid(); r jsonb; h record; n int;
begin
  perform public.care_add_event(jsonb_build_object('id', v_id, 'kind', 'feed', 'amount_ml', 200,
    'occurred_at', now() - interval '2 hours', 'detail', '{"memo":"유산균"}'::jsonb, 'force', true));
  r := public.care_update_event(jsonb_build_object('id', v_id, 'amount_ml', 230, 'occurred_at', now() - interval '3 hours'));
  perform pg_temp.check(r ->> 'status' = 'saved', 'update saved');
  perform pg_temp.check((select amount_ml = 230 and occurred_at < now() - interval '170 minutes' and detail ->> 'memo' = '유산균'
                         and updated_by = '11111111-1111-1111-1111-111111111111' from public.care_events where id = v_id),
                        'update changes amount/time, keeps memo, records who');
  select * into h from public.care_event_history where event_id = v_id order by id desc limit 1;
  perform pg_temp.check(h.action = 'update' and (h.before ->> 'amount_ml')::int = 200, 'history keeps the value before');
  select count(*) into n from public.care_event_history where event_id = v_id;
  perform public.care_update_event(jsonb_build_object('id', v_id, 'amount_ml', 230));
  perform pg_temp.check((select count(*) from public.care_event_history where event_id = v_id) = n, 'no history when nothing changed');
  perform public.care_cancel_event(v_id);
  perform pg_temp.check((select action from public.care_event_history where event_id = v_id order by id desc limit 1) = 'cancel', 'cancel goes to history');
  perform pg_temp.check(public.care_update_event(jsonb_build_object('id', v_id, 'amount_ml', 100)) ->> 'status' = 'not_found', 'cancelled record cannot be edited');
  begin
    perform public.care_update_event(jsonb_build_object('id', '33333333-3333-3333-3333-333333333333', 'ended_at', now() - interval '10 hours'));
    raise exception 'FAIL: end before start accepted';
  exception when sqlstate '22023' then raise notice 'ok - edit: end before start rejected';
  end;
  r := public.care_update_event(jsonb_build_object('id', '33333333-3333-3333-3333-333333333333', 'ended_at', null));
  perform pg_temp.check((select ended_at is null from public.care_events where id = '33333333-3333-3333-3333-333333333333'), 'edit: ended_at null reopens sleep');
end $$;
do $$
declare a jsonb := public.care_age('2026-11-07'); s jsonb := public.care_summary();
begin
  perform pg_temp.check(a = '{"day":143,"months":4,"days":21,"corrected_day":121,"corrected_months":3,"corrected_days":29}'::jsonb,
                        'age on 2026-11-07 matches BabyTime: ' || a::text);
  perform pg_temp.check((public.care_age('2026-06-18') ->> 'day')::int = 1 and (public.care_age('2026-06-18') ->> 'days')::int = 1, 'birthday is D+1, 0개월 1일');
  perform pg_temp.check(public.care_months_days('2026-07-18', '2026-06-18') = array[1, 1], 'exactly one month later: 1개월 1일');
  perform pg_temp.check(public.care_months_days('2026-07-17', '2026-06-18') = array[0, 30], 'day before: 0개월 30일');
  perform pg_temp.check(public.care_months_days('2026-03-01', '2026-01-31') = array[1, 2], 'month end: 1/31 + 1개월 = 2/28, 3/1 is 1개월 2일');
  perform pg_temp.check(public.care_age('2026-07-01') -> 'corrected_day' = 'null'::jsonb, 'no corrected age before due date');
  perform pg_temp.check(s -> 'baby' ->> 'name' = '세훈' and (s -> 'age' ->> 'day')::int > 0, 'summary has baby and age');
end $$;
set request.jwt.claim.sub = '22222222-2222-2222-2222-222222222222';
do $$ begin
  perform public.care_update_event('{"id":"33333333-3333-3333-3333-333333333333","amount_ml":1}');
  raise exception 'FAIL: stranger update';
exception when insufficient_privilege then raise notice 'ok - non-family cannot edit';
end $$;
do $$ begin
  perform pg_temp.check((select count(*) from public.care_event_history) = 0 and (select count(*) from public.care_baby_profile) = 0, 'non-family sees no history or profile');
end $$;
reset role;

-- ── 007: 수유 걸린 시간 ─────────────
set role authenticated;
set request.jwt.claim.sub = '11111111-1111-1111-1111-111111111111';
do $$
declare v_id uuid := gen_random_uuid(); s jsonb; st jsonb;
begin
  perform public.care_add_event(jsonb_build_object('id', v_id, 'kind', 'feed', 'amount_ml', 200,
    'occurred_at', now() - interval '12 minutes', 'detail', '{"feeding": true}'::jsonb, 'force', true));
  s := public.care_summary();
  perform pg_temp.check(s -> 'last_feed' ->> 'id' = v_id::text and (s -> 'last_feed' ->> 'feeding')::boolean, 'feeding now shows in summary');
  perform public.care_update_event(jsonb_build_object('id', v_id, 'ended_at', now(), 'detail', '{"feeding": false}'::jsonb));
  s := public.care_summary();
  perform pg_temp.check(not (s -> 'last_feed' ->> 'feeding')::boolean and (s -> 'last_feed' ->> 'ended_at') is not null, 'done feeding: end saved, not feeding');
  st := public.care_stats(1);
  perform pg_temp.check((st -> 0 ->> 'feed_min')::int = 12, 'stats: average feed minutes ' || (st -> 0 ->> 'feed_min'));
  perform pg_temp.check(public.care_stats(7) -> 0 -> 'feed_min' = 'null'::jsonb or (public.care_stats(7) -> 0) ? 'feed_min', 'feed_min present (null when unknown)');
end $$;
reset role;

-- ── 008: 기록 종류 표, 숫자 값 ─────────────
set role authenticated;
set request.jwt.claim.sub = '11111111-1111-1111-1111-111111111111';
do $$
declare s jsonb; r jsonb; v_id uuid := gen_random_uuid(); tl jsonb;
begin
  s := public.care_summary();
  perform pg_temp.check(jsonb_array_length(s -> 'record_types') >= 13, 'summary lists record types');
  perform pg_temp.check((select count(*) from jsonb_array_elements(s -> 'record_types') x where (x ->> 'in_more')::boolean) >= 10, 'more menu types');
  perform pg_temp.check(s -> 'record_types' -> 0 ->> 'key' = 'feed', 'record types sorted');
  r := public.care_add_event(jsonb_build_object('id', v_id, 'kind', 'temperature', 'value_num', 37.4, 'force', true));
  perform pg_temp.check(r ->> 'status' = 'saved' and (select value_num = 37.4 from public.care_events where id = v_id), 'temperature saved with value');
  begin
    perform public.care_add_event('{"kind":"temperature","value_num":45,"force":true}');
    raise exception 'FAIL: out of range temperature accepted';
  exception when sqlstate '22023' then raise notice 'ok - temperature out of range rejected';
  end;
  begin
    perform public.care_add_event('{"kind":"weight","force":true}');
    raise exception 'FAIL: weight without value accepted';
  exception when sqlstate '22023' then raise notice 'ok - number record needs a value';
  end;
  perform public.care_update_event(jsonb_build_object('id', v_id, 'value_num', 37.9));
  perform pg_temp.check((select value_num = 37.9 from public.care_events where id = v_id), 'update changes value');
  perform pg_temp.check(public.care_add_event(jsonb_build_object('kind', 'bath', 'occurred_at', now() - interval '20 minutes',
    'ended_at', now() - interval '10 minutes', 'detail', '{"memo":"보습로션"}'::jsonb, 'force', true)) ->> 'status' = 'saved', 'bath range saved');
  tl := public.care_timeline(1);
  perform pg_temp.check(exists (select 1 from jsonb_array_elements(tl) x where x ->> 'kind' = 'temperature' and (x ->> 'value')::numeric = 37.9), 'timeline has value');
  perform pg_temp.check(exists (select 1 from jsonb_array_elements(tl) x where x ->> 'kind' = 'bath' and x ->> 'memo' = '보습로션'), 'timeline has memo');
  perform pg_temp.check(exists (select 1 from jsonb_array_elements(public.care_summary() -> 'recent') x where x ->> 'kind' = 'temperature' and (x ->> 'value')::numeric = 37.9), 'recent has value');
end $$;
reset role;

\echo 'ALL SQL TESTS PASSED'
