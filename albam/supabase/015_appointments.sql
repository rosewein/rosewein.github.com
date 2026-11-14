-- 알밤보드 015: 다가오는 일정(예방접종 예약 등)
--
-- 014 다음에 실행한다(여러 번 실행해도 안전, 지우는 문장 없음).
--   - care_appointments : 앞으로 있을 일. care_events 는 미래 시각을 받지 않아서(이미 일어난 일만) 따로 둔다.
--       날짜는 꼭, 시각·장소는 모르면 비운다. items 는 그날 할 것(예: 맞을 백신)
--   - care_upcoming(p_limit) : 오늘(서울)부터의 일정을 가까운 순으로. days_left = 남은 날(오늘이면 0)
--       [{"id": "…", "on_date": "2026-12-22", "at_time": null, "kind": "vaccine", "title": "예방접종", "place": null, "items": ["…"], "days_left": 38}]
--   - care_set_appointment(p) : 넣기·고치기(id 가 있으면 고치기). care_cancel_appointment(id) : 취소 표시
--   지우지 않고 취소 표시만 한다(care_events 와 같은 원칙).

create table if not exists public.care_appointments (
  id          uuid primary key default gen_random_uuid(),
  on_date     date not null,
  at_time     time,
  kind        text not null default 'vaccine' check (kind ~ '^[a-z][a-z_]{1,30}$'),
  title       text not null check (length(title) between 1 and 60),
  place       text,
  items       text[] not null default '{}',
  note        text,
  created_at  timestamptz not null default now(),
  created_by  uuid default auth.uid(),
  deleted_at  timestamptz
);
create index if not exists care_appointments_on_date_idx on public.care_appointments (on_date) where deleted_at is null;
alter table public.care_appointments enable row level security;
revoke all on public.care_appointments from anon, authenticated;
grant select on public.care_appointments to authenticated;
do $$ begin
  if not exists (select 1 from pg_policies where schemaname = 'public' and tablename = 'care_appointments' and policyname = 'care_appointments_read') then
    create policy care_appointments_read on public.care_appointments for select to authenticated using (public.care_is_family());
  end if;
end $$;

create or replace function public.care_upcoming(p_limit int default 5)
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
    from (select * from public.care_appointments
          where deleted_at is null and on_date >= v_today
          order by on_date, at_time nulls last
          limit least(greatest(coalesce(p_limit, 5), 1), 50)) a
  );
end;
$$;

create or replace function public.care_set_appointment(p jsonb)
returns jsonb
language plpgsql volatile security definer
set search_path = ''
as $$
declare
  v_id uuid := coalesce(nullif(p ->> 'id', '')::uuid, gen_random_uuid());
begin
  if not public.care_is_family() then
    raise exception 'not_family' using errcode = '42501';
  end if;
  if nullif(p ->> 'on_date', '') is null or nullif(trim(p ->> 'title'), '') is null then
    raise exception 'bad_appointment' using errcode = '22023';
  end if;
  insert into public.care_appointments (id, on_date, at_time, kind, title, place, items, note)
  values (v_id, (p ->> 'on_date')::date, nullif(p ->> 'at_time', '')::time, coalesce(nullif(p ->> 'kind', ''), 'vaccine'),
          trim(p ->> 'title'), nullif(trim(p ->> 'place'), ''),
          coalesce((select array_agg(x) from jsonb_array_elements_text(coalesce(p -> 'items', '[]'::jsonb)) x), '{}'),
          nullif(trim(p ->> 'note'), ''))
  on conflict (id) do update
    set on_date = excluded.on_date, at_time = excluded.at_time, kind = excluded.kind, title = excluded.title,
        place = excluded.place, items = excluded.items, note = excluded.note, deleted_at = null;
  return jsonb_build_object('status', 'saved', 'id', v_id);
end;
$$;

create or replace function public.care_cancel_appointment(p_id uuid)
returns jsonb
language plpgsql volatile security definer
set search_path = ''
as $$
begin
  if not public.care_is_family() then
    raise exception 'not_family' using errcode = '42501';
  end if;
  update public.care_appointments set deleted_at = now() where id = p_id and deleted_at is null;
  return jsonb_build_object('status', case when found then 'cancelled' else 'not_found' end, 'id', p_id);
end;
$$;

revoke all on function public.care_upcoming(int) from public, anon;
revoke all on function public.care_set_appointment(jsonb) from public, anon;
revoke all on function public.care_cancel_appointment(uuid) from public, anon;
grant execute on function public.care_upcoming(int) to authenticated;
grant execute on function public.care_set_appointment(jsonb) to authenticated;
grant execute on function public.care_cancel_appointment(uuid) to authenticated;
