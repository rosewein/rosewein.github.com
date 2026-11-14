-- 알밤보드 017: 하루 기록 읽기(개인 폰 화면의 기록 쪽)
--
-- 016 다음에 실행한다(여러 번 실행해도 안전, 지우는 문장 없음).
--   - care_day(p_day) : 그날(서울, 하루 끊는 시각 day_start_hour 기준)의 기록을 실제 시각 순으로.
--       care_timeline 은 최근 7일까지만이라, 베이비타임에서 옮긴 지난 기록도 날짜로 열어 보려고 따로 둔다.
--       {"day": "2026-11-14", "from": "…", "to": "…", "events": [{id, kind, at, ended_at, ml, value, type, memo, feeding, detail}]}
--       전날 잠들어 그날 깬 잠(또는 아직 자는 중)도 들어간다. p_day 가 없으면 오늘

create or replace function public.care_day(p_day date default null)
returns jsonb
language plpgsql stable security definer
set search_path = ''
as $$
declare
  tz     constant text := 'Asia/Seoul';
  v_hour int := public.care_setting_int('day_start_hour', 0);
  v_day  date := coalesce(p_day, ((now() at time zone tz) - make_interval(hours => v_hour))::date);
  v_from timestamptz := (v_day::timestamp + make_interval(hours => v_hour)) at time zone tz;
  v_to   timestamptz := v_from + interval '1 day';
begin
  if not public.care_is_family() then
    raise exception 'not_family' using errcode = '42501';
  end if;
  return jsonb_build_object(
    'day', v_day, 'from', v_from, 'to', v_to,
    'events', (
      select coalesce(jsonb_agg(jsonb_build_object(
               'id', e.id, 'kind', e.kind, 'at', e.occurred_at, 'ended_at', e.ended_at,
               'ml', e.amount_ml, 'value', e.value_num, 'type', e.detail ->> 'type',
               'memo', e.detail ->> 'memo', 'feeding', coalesce((e.detail ->> 'feeding')::boolean, false),
               'detail', e.detail) order by e.occurred_at), '[]'::jsonb)
      from public.care_events e
      where e.deleted_at is null
        and ((e.occurred_at >= v_from and e.occurred_at < v_to)
          or (e.kind = 'sleep' and e.occurred_at < v_from and e.occurred_at >= v_from - interval '1 day'
              and (e.ended_at is null or e.ended_at > v_from)))
    )
  );
end;
$$;

revoke all on function public.care_day(date) from public, anon;
grant execute on function public.care_day(date) to authenticated;
