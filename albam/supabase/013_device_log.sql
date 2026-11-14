-- 알밤보드 013: 보드(펌웨어) 상태 기록
--
-- 012 다음에 실행한다(여러 번 실행해도 안전).
--   - care_device_log : 거실 보드(albam/firmware)가 켜질 때, 10분마다, 화면이 멈춰 스스로 다시 켜기 직전에
--     자기 상태(판 번호, 켠 시간, 남은 메모리, 서버 읽기 성공·실패, 멈춘 횟수)를 남긴다. 보드의 /info 와 같은 내용이다.
--     육아 기록(care_events)과 따로 둔다. 보드가 멈추거나 이상할 때 이 표를 읽는다(사람이 /info 를 붙여 넣지 않게)
--   - care_device_log(p jsonb) : 한 줄 넣기. 넣을 때 14일 지난 줄을 지운다

create table if not exists public.care_device_log (
  id          bigint generated always as identity primary key,
  logged_at   timestamptz not null default now(),
  device      text not null,              -- albam_board
  reason      text not null check (reason in ('boot', 'periodic', 'stall')),   -- 켜짐 / 10분마다 / 화면이 멈춤
  version     text,                       -- 0.4.2+1a2b3c4
  info        jsonb not null,             -- 보드의 /info 그대로
  recorded_by uuid default auth.uid()
);
create index if not exists care_device_log_logged_at_idx on public.care_device_log (logged_at desc);

alter table public.care_device_log enable row level security;
do $$
begin
  if not exists (select 1 from pg_policies where schemaname = 'public' and tablename = 'care_device_log' and policyname = 'care_device_log_family_read') then
    create policy care_device_log_family_read on public.care_device_log for select to authenticated using (public.care_is_family());
  end if;
end $$;

create or replace function public.care_device_log(p jsonb)
returns jsonb
language plpgsql security definer
set search_path = ''
as $$
declare
  v_info jsonb := p -> 'info';
begin
  if not public.care_is_family() then
    raise exception 'not_family' using errcode = '42501';
  end if;
  if jsonb_typeof(v_info) is distinct from 'object' or pg_column_size(v_info) > 8000 then
    raise exception 'bad_info' using errcode = '22023';
  end if;
  insert into public.care_device_log (device, reason, version, info)
  values (left(coalesce(p ->> 'device', 'albam_board'), 40), p ->> 'reason', left(v_info ->> 'version', 40), v_info);
  delete from public.care_device_log where logged_at < now() - interval '14 days';
  return jsonb_build_object('status', 'saved');
end;
$$;

revoke all on function public.care_device_log(jsonb) from public, anon;
grant execute on function public.care_device_log(jsonb) to authenticated;
grant select on public.care_device_log to authenticated;
