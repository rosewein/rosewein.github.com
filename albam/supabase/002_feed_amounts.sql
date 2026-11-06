-- 알밤케어 002: 수유량 빠른 선택을 직접 정하기
--
-- 001 다음에 SQL Editor 에서 실행한다(여러 번 실행해도 안전).
-- 예전에는 '최근에 먹인 양 3개'를 자동으로 보여 줬는데, 양이 늘 때(지금 200ml) 바로 따라가지 못해서
-- 가족이 화면에서 직접 정하게 바꾼다.
--   - care_settings.feed_amounts : 빠른 선택 양(ml) 배열. 처음 값 180·200·220
--   - care_set_feed_amounts()    : 화면의 '수유량 설정'이 부르는 함수
--   - care_summary()             : recent_feed_amounts 대신 feed_amounts 를 돌려준다

insert into public.care_settings (key, value, note) values
  ('feed_amounts', '[180, 200, 220]', '수유량 빠른 선택(ml). 화면의 수유량 설정에서 바꾼다')
on conflict (key) do nothing;

delete from public.care_settings where key = 'quick_amount_count';

-- 빠른 선택 양 저장. 1~6개, 각 10~500ml. 같은 양은 하나로, 작은 것부터
create or replace function public.care_set_feed_amounts(p_amounts int[])
returns jsonb
language plpgsql volatile security definer
set search_path = ''
as $$
declare
  v_clean int[];
begin
  if not public.care_is_family() then
    raise exception 'not_family' using errcode = '42501';
  end if;
  select array_agg(distinct a order by a) into v_clean from unnest(p_amounts) a where a is not null;
  if v_clean is null or array_length(v_clean, 1) > 6 then
    raise exception 'bad_feed_amounts' using errcode = '22023';
  end if;
  if exists (select 1 from unnest(v_clean) a where a < 10 or a > 500) then
    raise exception 'bad_feed_amounts' using errcode = '22023';
  end if;

  insert into public.care_settings (key, value, note)
  values ('feed_amounts', to_jsonb(v_clean), '수유량 빠른 선택(ml). 화면의 수유량 설정에서 바꾼다')
  on conflict (key) do update set value = excluded.value;

  return jsonb_build_object('status', 'saved', 'feed_amounts', to_jsonb(v_clean));
end;
$$;

-- 요약 함수: 001 과 같고, 수유량 빠른 선택만 feed_amounts 로 바뀜
create or replace function public.care_summary()
returns jsonb
language plpgsql stable security definer
set search_path = ''
as $$
declare
  tz        constant text := 'Asia/Seoul';
  v_now     timestamptz := now();
  v_hour    int := public.care_setting_int('day_start_hour', 0);
  v_window  int := public.care_setting_int('dup_window_minutes', 10);
  v_recent  int := public.care_setting_int('recent_limit', 8);
  v_local   timestamp;
  v_day     timestamptz;
begin
  if not public.care_is_family() then
    raise exception 'not_family' using errcode = '42501';
  end if;

  -- 오늘의 시작: 서울 시각으로 v_hour 시. 그 전이면 어제 v_hour 시.
  v_local := v_now at time zone tz;
  v_day := (date_trunc('day', v_local - make_interval(hours => v_hour)) + make_interval(hours => v_hour)) at time zone tz;

  return jsonb_build_object(
    'server_time', v_now,
    'day_start', v_day,

    'last_feed', (
      select jsonb_build_object('id', e.id, 'at', e.occurred_at, 'ml', e.amount_ml)
      from public.care_events e
      where e.kind = 'feed' and e.deleted_at is null
      order by e.occurred_at desc limit 1
    ),

    'today', (
      select jsonb_build_object('feed_count', count(*), 'feed_ml', coalesce(sum(e.amount_ml), 0))
      from public.care_events e
      where e.kind = 'feed' and e.deleted_at is null
        and e.occurred_at >= v_day and e.occurred_at < v_day + interval '1 day'
    ),

    'last_diaper', (
      select jsonb_build_object('id', e.id, 'at', e.occurred_at, 'type', e.detail ->> 'type')
      from public.care_events e
      where e.kind = 'diaper' and e.deleted_at is null
      order by e.occurred_at desc limit 1
    ),

    'last_sleep', (
      select jsonb_build_object('id', e.id, 'at', e.occurred_at, 'ended_at', e.ended_at)
      from public.care_events e
      where e.kind = 'sleep' and e.deleted_at is null
      order by e.occurred_at desc limit 1
    ),

    -- 수유량 빠른 선택: 화면의 '수유량 설정'에서 정한 양(작은 것부터)
    'feed_amounts', coalesce((select s.value from public.care_settings s where s.key = 'feed_amounts'), '[180, 200, 220]'::jsonb),

    -- 최근 기록(실제 시각 순). 나중에 넣는 기록 화면에서 자리 잡은 걸 확인하는 용도
    'recent', (
      select coalesce(jsonb_agg(jsonb_build_object(
               'id', r.id, 'kind', r.kind, 'at', r.occurred_at, 'ended_at', r.ended_at,
               'ml', r.amount_ml, 'detail', r.detail, 'source', r.source) order by r.occurred_at desc), '[]'::jsonb)
      from (
        select * from public.care_events e
        where e.deleted_at is null
        order by e.occurred_at desc limit v_recent
      ) r
    ),

    'due_chores', '[]'::jsonb,  -- 2단계

    'settings', jsonb_build_object(
      'day_start_hour', v_hour,
      'dup_window_minutes', v_window
    )
  );
end;
$$;

revoke all on function public.care_set_feed_amounts(int[]) from public, anon;
grant execute on function public.care_set_feed_amounts(int[]) to authenticated;
revoke all on function public.care_summary() from public, anon;
grant execute on function public.care_summary() to authenticated;
