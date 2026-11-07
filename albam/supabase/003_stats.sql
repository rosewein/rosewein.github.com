-- 알밤케어 003: 날짜별 통계 함수(통계 화면)
--
-- 002 다음에 실행한다(여러 번 실행해도 안전). 통계는 care_events 에서 바로 센다.
--
-- 날짜 규칙(베이비타임 통계와 같게)
--   - 수유·기저귀: 일어난 날(서울, care_settings.day_start_hour 기준)
--   - 낮잠: 시작한 날
--   - 밤잠: 깨는 아침의 날. 시작 시각 + 12시간의 날짜로 센다(저녁 8시에 잠들면 다음 날)
--   - 낮잠/밤잠은 detail.when('day'/'night'). 없으면 시작이 18시~6시 사이면 밤잠으로 본다

create or replace function public.care_sleep_day(p_start timestamptz, p_detail jsonb, p_day_start_hour int)
returns date
language sql immutable
set search_path = ''
as $$
  select case
    when coalesce(p_detail ->> 'when',
                  case when extract(hour from p_start at time zone 'Asia/Seoul') >= 18
                         or extract(hour from p_start at time zone 'Asia/Seoul') < 6 then 'night' else 'day' end) = 'night'
      then ((p_start at time zone 'Asia/Seoul') + interval '12 hours')::date
    else ((p_start at time zone 'Asia/Seoul') - make_interval(hours => p_day_start_hour))::date
  end;
$$;

-- 최근 p_days 일(오늘 포함) 날짜별 통계. 날짜 오름차순
--   [{day, feed_count, feed_ml, diaper_total, diaper_pee, diaper_poo, diaper_both, sleep_min, nap_min, night_min}]
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

revoke all on function public.care_sleep_day(timestamptz, jsonb, int) from public, anon;
grant execute on function public.care_sleep_day(timestamptz, jsonb, int) to authenticated;
revoke all on function public.care_stats(int) from public, anon;
grant execute on function public.care_stats(int) to authenticated;
