-- 알밤보드 018: 개인 폰 화면의 설정 쪽(더 넣기 버튼 고르기·순서, 일정 목록)
--
-- 017 다음에 실행한다(여러 번 실행해도 안전, 지우는 문장 없음).
--   - care_show_record_type(key, show) : 그 종류를 [+] 더 넣기에 보일지. 숨겨도 기록은 그대로 남고 목록·통계에는 나온다
--   - care_order_record_types(keys[]) : 버튼 순서. 적은 차례대로 sort 를 10, 20, 30 … 으로 매긴다
--   - care_appointments(p_past_days) : 설정 쪽의 일정 목록(앞으로의 일정 + 지난 며칠)
--   수유·기저귀·잠은 큰 버튼이 따로 있어서 바꾸지 못한다. 모든 화면(거실·폰·보드)에 같이 적용된다.

create or replace function public.care_show_record_type(p_key text, p_show boolean)
returns jsonb
language plpgsql volatile security definer
set search_path = ''
as $$
begin
  if not public.care_is_family() then
    raise exception 'not_family' using errcode = '42501';
  end if;
  if p_key in ('feed', 'diaper', 'sleep') or p_show is null then
    raise exception 'bad_record_type' using errcode = '22023';
  end if;
  update public.care_record_types set show_in_more = p_show where key = p_key and active;
  return jsonb_build_object('status', case when found then 'saved' else 'not_found' end, 'key', p_key);
end;
$$;

create or replace function public.care_order_record_types(p_keys text[])
returns jsonb
language plpgsql volatile security definer
set search_path = ''
as $$
begin
  if not public.care_is_family() then
    raise exception 'not_family' using errcode = '42501';
  end if;
  if p_keys is null or cardinality(p_keys) = 0 or p_keys && array['feed', 'diaper', 'sleep'] then
    raise exception 'bad_record_type' using errcode = '22023';
  end if;
  update public.care_record_types t
     set sort = k.ord * 10
    from unnest(p_keys) with ordinality as k(key, ord)
   where t.key = k.key;
  return jsonb_build_object('status', 'saved');
end;
$$;

revoke all on function public.care_show_record_type(text, boolean) from public, anon;
revoke all on function public.care_order_record_types(text[]) from public, anon;
grant execute on function public.care_show_record_type(text, boolean) to authenticated;
grant execute on function public.care_order_record_types(text[]) to authenticated;

-- 설정 쪽의 일정 목록: 앞으로의 일정 + 지난 p_past_days 일 안의 일정(취소한 것 빼고).
-- care_upcoming 은 오늘부터만 주는데, 접종한 날 기록으로 옮기는 걸 잊어도 며칠 동안은 목록에 남아 있게 하려는 것이다.
-- days_left 는 지난 일정이면 음수
create or replace function public.care_appointments(p_past_days int default 14)
returns jsonb
language plpgsql stable security definer
set search_path = ''
as $$
declare
  v_today date := (now() at time zone 'Asia/Seoul')::date;
begin
  if not public.care_is_family() then
    raise exception 'not_family' using errcode = '42501';
  end if;
  return (
    select coalesce(jsonb_agg(jsonb_build_object(
             'id', a.id, 'on_date', a.on_date, 'at_time', to_char(a.at_time, 'HH24:MI'), 'kind', a.kind, 'title', a.title,
             'place', a.place, 'items', to_jsonb(a.items), 'note', a.note, 'days_left', a.on_date - v_today)
             order by a.on_date, a.at_time nulls last), '[]'::jsonb)
    from public.care_appointments a
    where a.deleted_at is null and a.on_date >= v_today - least(greatest(coalesce(p_past_days, 14), 0), 365)
  );
end;
$$;

revoke all on function public.care_appointments(int) from public, anon;
grant execute on function public.care_appointments(int) to authenticated;
