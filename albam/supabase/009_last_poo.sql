-- 알밤케어 009: 요약에 마지막 대변
--
-- 008 다음에 실행한다(여러 번 실행해도 안전, 지우는 문장 없음).
--   - care_summary : last_poo(대변·둘 다 중 가장 최근)를 더함(008 과 나머지는 같음)
--   - 대변 기록을 빨리 찾게 기저귀 종류 색인을 더함

create index if not exists care_events_diaper_type_idx
  on public.care_events ((detail ->> 'type'), occurred_at desc)
  where kind = 'diaper' and deleted_at is null;

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

  v_local := v_now at time zone tz;
  v_day := (date_trunc('day', v_local - make_interval(hours => v_hour)) + make_interval(hours => v_hour)) at time zone tz;

  return jsonb_build_object(
    'server_time', v_now,
    'day_start', v_day,

    -- 아기와 오늘 나이(서울 날짜. 나이는 자정에 바뀐다)
    'baby', (select jsonb_build_object('name', b.name, 'nickname', b.nickname, 'birth_date', b.birth_date, 'due_date', b.due_date)
             from public.care_baby_profile b where b.id = 1),
    'age', public.care_age(v_local::date),

    'last_feed', (
      -- ended_at: 다 먹은 시각(없으면 모름), feeding: 지금 먹이는 중(먹이기 시작하고 아직 '다 먹음'을 안 누름)
      select jsonb_build_object('id', e.id, 'at', e.occurred_at, 'ml', e.amount_ml, 'ended_at', e.ended_at,
                                'feeding', e.ended_at is null and coalesce((e.detail ->> 'feeding')::boolean, false))
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

    -- 마지막 대변(대변·둘 다). 기저귀를 소변만 갈았어도 대변이 언제였는지 보이게
    'last_poo', (
      select jsonb_build_object('id', e.id, 'at', e.occurred_at, 'type', e.detail ->> 'type')
      from public.care_events e
      where e.kind = 'diaper' and e.deleted_at is null and e.detail ->> 'type' in ('poo', 'both')
      order by e.occurred_at desc limit 1
    ),

    'last_sleep', (
      select jsonb_build_object('id', e.id, 'at', e.occurred_at, 'ended_at', e.ended_at)
      from public.care_events e
      where e.kind = 'sleep' and e.deleted_at is null
      order by e.occurred_at desc limit 1
    ),

    'feed_amounts', coalesce((select s.value from public.care_settings s where s.key = 'feed_amounts'), '[200, 230, 270]'::jsonb),

    'recent', (
      select coalesce(jsonb_agg(jsonb_build_object(
               'id', r.id, 'kind', r.kind, 'at', r.occurred_at, 'ended_at', r.ended_at,
               'ml', r.amount_ml, 'value', r.value_num, 'detail', r.detail, 'source', r.source) order by r.occurred_at desc), '[]'::jsonb)
      from (
        select * from public.care_events e
        where e.deleted_at is null
        order by e.occurred_at desc limit v_recent
      ) r
    ),

    -- 기록 종류 표(화면의 [+] 더보기·이름·단위가 여기서 나온다)
    'record_types', (
      select coalesce(jsonb_agg(jsonb_build_object('key', t.key, 'label', t.label, 'shape', t.shape, 'unit', t.unit,
               'step', t.step, 'min', t.min_value, 'max', t.max_value, 'default', t.default_value,
               'icon', t.icon, 'in_more', t.show_in_more, 'aliases', t.voice_aliases) order by t.sort), '[]'::jsonb)
      from public.care_record_types t where t.active
    ),

    'due_chores', '[]'::jsonb,

    'settings', jsonb_build_object(
      'day_start_hour', v_hour,
      'dup_window_minutes', v_window
    )
  );
end;
$$;

revoke all on function public.care_summary() from public, anon;
grant execute on function public.care_summary() to authenticated;
