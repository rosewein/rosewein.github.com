-- 알밤보드 012: 호출어 시험 기록
--
-- 011 다음에 실행한다(여러 번 실행해도 안전, 지우는 문장 없음).
--   - care_voice_log : 호출어 시험 화면(voice-test.html)이 알아들은 것·잘못·못 알아들음을 남긴다.
--     육아 기록(care_events)과 따로 둔다. 규칙을 다듬을 때 이 표를 읽는다(사람이 결과를 붙여 넣지 않게)
--   - care_voice_log(p jsonb) : 한 줄 넣기, 같은 id 가 있으면 '잘못' 표시만 바꾸기

create table if not exists public.care_voice_log (
  id          uuid primary key,
  heard_at    timestamptz not null default now(),
  event       text not null check (event in ('hit', 'unsure', 'missed')),   -- 알아들음 / 알밤은 들었는데 종류 모름 / 말했는데 못 알아들음
  kind        text,                       -- pee / poo / feed / sleep / wake
  conf        numeric,
  heard       text,                       -- 들은 낱말과 확실한 정도: "알밤(1.00) 이(1.00) 밥(0.53) 먹었어(1.00)"
  wrong       boolean not null default false,
  device      text,
  recorded_by uuid default auth.uid()
);
create index if not exists care_voice_log_heard_at_idx on public.care_voice_log (heard_at desc);

alter table public.care_voice_log enable row level security;
do $$
begin
  if not exists (select 1 from pg_policies where schemaname = 'public' and tablename = 'care_voice_log' and policyname = 'care_voice_log_family_read') then
    create policy care_voice_log_family_read on public.care_voice_log for select to authenticated using (public.care_is_family());
  end if;
end $$;

create or replace function public.care_voice_log(p jsonb)
returns uuid
language plpgsql security definer
set search_path = ''
as $$
declare
  v_id uuid := (p ->> 'id')::uuid;
begin
  if not public.care_is_family() then
    raise exception 'not_family' using errcode = '42501';
  end if;
  if v_id is null then
    raise exception 'bad_id' using errcode = '22023';
  end if;
  insert into public.care_voice_log (id, heard_at, event, kind, conf, heard, wrong, device)
  values (v_id, coalesce((p ->> 'heard_at')::timestamptz, now()), p ->> 'event', p ->> 'kind',
          (p ->> 'conf')::numeric, left(p ->> 'heard', 500), coalesce((p ->> 'wrong')::boolean, false), left(p ->> 'device', 100))
  on conflict (id) do update set wrong = excluded.wrong;
  return v_id;
end;
$$;

revoke all on function public.care_voice_log(jsonb) from public, anon;
grant execute on function public.care_voice_log(jsonb) to authenticated;
grant select on public.care_voice_log to authenticated;
