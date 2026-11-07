-- 알밤케어 005: 타임라인(최근 며칠 기록을 시간 줄에)
--
-- 004 다음에 실행한다(여러 번 실행해도 안전).
-- 거실 화면의 타임라인 쪽이 부른다. 오늘 포함 최근 p_days 일(1~7)의 기록을 실제 시각 순으로.
--   [{id, kind, at, ended_at, ml, type}]   type: 기저귀 종류
-- 그날 시작 전에 잠들어 그날 깬 잠도 넣는다(줄의 왼쪽 끝에서 이어지게).

create or replace function public.care_timeline(p_days int default 3)
returns jsonb
language plpgsql stable security definer
set search_path = ''
as $$
declare
  tz     constant text := 'Asia/Seoul';
  v_hour int := public.care_setting_int('day_start_hour', 0);
  v_days int := least(greatest(coalesce(p_days, 3), 1), 7);
  v_today date := ((now() at time zone tz) - make_interval(hours => v_hour))::date;
  v_from timestamptz := ((v_today - (v_days - 1))::timestamp + make_interval(hours => v_hour)) at time zone tz;
begin
  if not public.care_is_family() then
    raise exception 'not_family' using errcode = '42501';
  end if;
  return (
    select coalesce(jsonb_agg(jsonb_build_object(
             'id', e.id, 'kind', e.kind, 'at', e.occurred_at, 'ended_at', e.ended_at,
             'ml', e.amount_ml, 'type', e.detail ->> 'type') order by e.occurred_at), '[]'::jsonb)
    from public.care_events e
    where e.deleted_at is null
      and (e.occurred_at >= v_from or (e.kind = 'sleep' and (e.ended_at is null or e.ended_at >= v_from)
                                       and e.occurred_at >= v_from - interval '1 day'))
  );
end;
$$;

revoke all on function public.care_timeline(int) from public, anon;
grant execute on function public.care_timeline(int) to authenticated;
