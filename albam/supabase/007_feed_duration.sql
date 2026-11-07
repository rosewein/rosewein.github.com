-- 알밤케어 007: 수유 걸린 시간(먹이기 시작 → 다 먹음)
--
-- 006 다음에 실행한다(여러 번 실행해도 안전, 지우는 문장 없음).
-- 수유도 잠처럼 시작과 끝을 둔다. occurred_at = 먹이기 시작, ended_at = 다 먹은 시각.
--   - 끝을 모르는 수유(예전 기록, [지금 저장])는 ended_at 이 null
--   - 먹이는 중은 ended_at 이 null 이고 detail.feeding = true. [다 먹음]은 care_update_event 로
--     {ended_at: 지금, detail: {feeding: false}} 를 보낸다(새 함수 없음)
--   - care_summary(): last_feed 에 ended_at, feeding 을 더함(006 과 나머지는 같음)
--   - care_stats(): 날짜별 feed_min(끝이 있는 수유의 평균 걸린 분)을 더함(003 과 나머지는 같음)

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
               'ml', r.amount_ml, 'detail', r.detail, 'source', r.source) order by r.occurred_at desc), '[]'::jsonb)
      from (
        select * from public.care_events e
        where e.deleted_at is null
        order by e.occurred_at desc limit v_recent
      ) r
    ),

    'due_chores', '[]'::jsonb,

    'settings', jsonb_build_object(
      'day_start_hour', v_hour,
      'dup_window_minutes', v_window
    )
  );
end;
$$;


create or replace function public.care_stats(p_days int default 7)
returns jsonb
language plpgsql stable security definer
set search_path = ''
as $$
declare
  tz     constant text := 'Asia/Seoul';
  v_hour int := public.care_setting_int('day_start_hour', 0);
  v_days int := least(greatest(coalesce(p_days, 7), 1), 92);
  v_today date := ((now() at time zone tz) - make_interval(hours => v_hour))::date;
  v_from  date := v_today - (v_days - 1);
begin
  if not public.care_is_family() then
    raise exception 'not_family' using errcode = '42501';
  end if;

  return (
    with ev as (
      select e.*,
        case when e.kind = 'sleep' then public.care_sleep_day(e.occurred_at, e.detail, v_hour)
             else ((e.occurred_at at time zone tz) - make_interval(hours => v_hour))::date end as day,
        coalesce(e.detail ->> 'when',
                 case when extract(hour from e.occurred_at at time zone tz) >= 18
                        or extract(hour from e.occurred_at at time zone tz) < 6 then 'night' else 'day' end) as sleep_when
      from public.care_events e
      where e.deleted_at is null
        -- 밤잠은 하루 앞에서 시작할 수 있어서 하루 더 넉넉히 읽는다
        and e.occurred_at >= ((v_from - 1)::timestamp + make_interval(hours => v_hour)) at time zone tz
    ), per_day as (
      select day,
        count(*) filter (where kind = 'feed') as feed_count,
        coalesce(sum(amount_ml) filter (where kind = 'feed'), 0) as feed_ml,
        round(avg(extract(epoch from ended_at - occurred_at) / 60) filter (where kind = 'feed' and ended_at is not null))::int as feed_min,
        count(*) filter (where kind = 'diaper') as diaper_total,
        count(*) filter (where kind = 'diaper' and detail ->> 'type' = 'pee') as diaper_pee,
        count(*) filter (where kind = 'diaper' and detail ->> 'type' = 'poo') as diaper_poo,
        count(*) filter (where kind = 'diaper' and detail ->> 'type' = 'both') as diaper_both,
        coalesce(sum(extract(epoch from ended_at - occurred_at) / 60) filter (where kind = 'sleep' and sleep_when = 'day'), 0)::int as nap_min,
        coalesce(sum(extract(epoch from ended_at - occurred_at) / 60) filter (where kind = 'sleep' and sleep_when = 'night'), 0)::int as night_min
      from ev where ended_at is not null or kind <> 'sleep'
      group by day
    )
    select coalesce(jsonb_agg(jsonb_build_object(
      'day', d.day,
      'feed_count', coalesce(p.feed_count, 0), 'feed_ml', coalesce(p.feed_ml, 0),
      'feed_min', p.feed_min,
      'diaper_total', coalesce(p.diaper_total, 0), 'diaper_pee', coalesce(p.diaper_pee, 0),
      'diaper_poo', coalesce(p.diaper_poo, 0), 'diaper_both', coalesce(p.diaper_both, 0),
      'nap_min', coalesce(p.nap_min, 0), 'night_min', coalesce(p.night_min, 0),
      'sleep_min', coalesce(p.nap_min, 0) + coalesce(p.night_min, 0)
    ) order by d.day), '[]'::jsonb)
    from generate_series(v_from, v_today, interval '1 day') as g(x)
    cross join lateral (select g.x::date as day) d
    left join per_day p on p.day = d.day
  );
end;
$$;


revoke all on function public.care_summary() from public, anon;
grant execute on function public.care_summary() to authenticated;
revoke all on function public.care_stats(int) from public, anon;
grant execute on function public.care_stats(int) to authenticated;
