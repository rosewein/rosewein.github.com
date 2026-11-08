-- 알밤케어 010: 요약에 수유 간격 통계
--
-- 009 다음에 실행한다(여러 번 실행해도 안전, 지우는 문장 없음).
--   - care_summary : feed_gap {n, p25, p50, p75}(최근 14일 수유 간격, 분)을 더함(009 와 나머지는 같음)
--     화면은 p25(4번 중 3번은 이보다 늦게 먹음)를 "배고파요…" 기준으로 쓴다. 아기가 크면서 간격이 늘어도 따라간다

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

    -- 최근 14일 수유 간격(분): 20분~12시간 사이만. 화면의 "배고파요…" 기준을 자동으로 잡는 데 쓴다(config.js hungryMinutes: 'auto')
    'feed_gap', (
      select jsonb_build_object('n', count(*),
               'p25', round(percentile_cont(0.25) within group (order by g.gap)::numeric),
               'p50', round(percentile_cont(0.5) within group (order by g.gap)::numeric),
               'p75', round(percentile_cont(0.75) within group (order by g.gap)::numeric))
      from (
        select extract(epoch from e.occurred_at - lag(e.occurred_at) over (order by e.occurred_at)) / 60 as gap, e.occurred_at
        from public.care_events e
        where e.kind = 'feed' and e.deleted_at is null and e.occurred_at >= v_now - interval '15 days'
      ) g
      where g.occurred_at >= v_now - interval '14 days' and g.gap between 20 and 720
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
