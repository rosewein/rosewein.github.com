-- 알밤케어 004: 잠을 "잠들 때 시작, 깰 때 끝"으로 넣기
--
-- 003 다음에 실행한다(여러 번 실행해도 안전).
-- 언제 깰지 모르니 잠은 끝 없이(ended_at = null) 먼저 넣고, 깨면 끝 시각만 채운다.
--   - 끝이 없는 잠 = 자는 중. 요약의 last_sleep.ended_at 이 null 이면 화면이 "자는 중"으로 그린다
--   - 통계(care_stats)는 끝이 있는 잠만 센다(003 그대로)
--   - 끝을 null 로 되돌리면 "다시 자는 중"(깼어요를 잘못 눌렀을 때 저장 직후 취소)

create or replace function public.care_set_sleep_end(p_id uuid, p_ended_at timestamptz)
returns jsonb
language plpgsql volatile security definer
set search_path = ''
as $$
declare
  v_ev public.care_events;
begin
  if not public.care_is_family() then
    raise exception 'not_family' using errcode = '42501';
  end if;
  select * into v_ev from public.care_events e where e.id = p_id and e.kind = 'sleep' and e.deleted_at is null;
  if not found then
    return jsonb_build_object('status', 'not_found', 'id', p_id);
  end if;
  if p_ended_at is not null and p_ended_at > now() + interval '5 minutes' then
    raise exception 'ended_at_in_future' using errcode = '22023';
  end if;
  if p_ended_at is not null and p_ended_at < v_ev.occurred_at then
    raise exception 'ended_before_started' using errcode = '22023';
  end if;
  update public.care_events set ended_at = p_ended_at where id = p_id;
  return jsonb_build_object('status', 'saved', 'id', p_id, 'ended_at', p_ended_at);
end;
$$;

revoke all on function public.care_set_sleep_end(uuid, timestamptz) from public, anon;
grant execute on function public.care_set_sleep_end(uuid, timestamptz) to authenticated;
