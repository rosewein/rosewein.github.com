-- 알밤케어 006: 기록 고치기와 고친 내역, 아기 나이
--
-- 005 다음에 실행한다(여러 번 실행해도 안전, 지우는 문장 없음).
--   - care_events.updated_at / updated_by : 마지막으로 고친 때·사람
--   - care_event_history : 기록을 고치거나 취소할 때마다 이전 값을 자동으로 한 줄씩(트리거)
--   - care_update_event(p) : 화면의 '기록 고치기'. 시각·끝·양·기저귀 종류를 바꾼다(세부값은 합친다)
--   - care_baby_profile : 아기 프로필 한 줄(이름, 생일, 예정일)
--   - care_age(날짜) : 베이비타임과 같은 나이. 태어난 날이 D+1, "4개월 21일"도 같은 방식(+1)
--   - care_summary() : 002 와 같고 baby·age 를 더함

-- ── 고친 때·사람 ──
alter table public.care_events add column if not exists updated_at timestamptz;
alter table public.care_events add column if not exists updated_by uuid;

-- ── 고친 내역 ──
create table if not exists public.care_event_history (
  id         bigint generated always as identity primary key,
  event_id   uuid not null references public.care_events (id),
  action     text not null check (action in ('update', 'cancel')),
  before     jsonb not null,                 -- 고치기 전 기록 한 줄 전체
  changed_at timestamptz not null default now(),
  changed_by uuid
);
create index if not exists care_event_history_event on public.care_event_history (event_id, changed_at desc);
alter table public.care_event_history enable row level security;
revoke all on public.care_event_history from anon, authenticated;
grant select on public.care_event_history to authenticated;   -- 가족만(아래 정책). 쓰기는 트리거로만
do $$ begin
  if not exists (select 1 from pg_policies where schemaname = 'public' and tablename = 'care_event_history' and policyname = 'care_event_history_read') then
    create policy care_event_history_read on public.care_event_history for select to authenticated using (public.care_is_family());
  end if;
end $$;

-- 고칠 때: 고친 때·사람을 채우고, 바뀐 게 있으면 이전 값을 내역에
create or replace function public.care_events_on_update()
returns trigger
language plpgsql security definer
set search_path = ''
as $$
begin
  if not (old.occurred_at is distinct from new.occurred_at or old.ended_at is distinct from new.ended_at
          or old.amount_ml is distinct from new.amount_ml or old.detail is distinct from new.detail
          or old.deleted_at is distinct from new.deleted_at) then
    return new;
  end if;
  new.updated_at := now();
  new.updated_by := auth.uid();
  insert into public.care_event_history (event_id, action, before, changed_by)
  values (old.id, case when new.deleted_at is not null and old.deleted_at is null then 'cancel' else 'update' end,
          to_jsonb(old), auth.uid());
  return new;
end;
$$;
create or replace trigger care_events_history before update on public.care_events
  for each row execute function public.care_events_on_update();

-- ── 기록 고치기 ──
--   입력: {"id", "occurred_at"?, "ended_at"?(null 이면 자는 중으로), "amount_ml"?, "detail"?(있는 세부값에 합침)}
--   돌려줌: {"status": "saved", "id"} / {"status": "not_found", "id"}
create or replace function public.care_update_event(p jsonb)
returns jsonb
language plpgsql volatile security definer
set search_path = ''
as $$
declare
  v_id  uuid := nullif(p ->> 'id', '')::uuid;
  v_ev  public.care_events;
  v_at  timestamptz;
  v_end timestamptz;
  v_ml  int;
  v_det jsonb;
begin
  if not public.care_is_family() then
    raise exception 'not_family' using errcode = '42501';
  end if;
  select * into v_ev from public.care_events e where e.id = v_id and e.deleted_at is null;
  if not found then
    return jsonb_build_object('status', 'not_found', 'id', v_id);
  end if;
  v_at  := coalesce(nullif(p ->> 'occurred_at', '')::timestamptz, v_ev.occurred_at);
  v_end := case when p ? 'ended_at' then nullif(p ->> 'ended_at', '')::timestamptz else v_ev.ended_at end;
  v_ml  := case when p ? 'amount_ml' then nullif(p ->> 'amount_ml', '')::numeric::int else v_ev.amount_ml end;
  -- 세부값은 합친다(메모·낮잠/밤잠 같은 건 그대로 두고 바꾼 것만). 객체가 아닌 값은 무시
  v_det := (case when jsonb_typeof(v_ev.detail) = 'object' then v_ev.detail else '{}'::jsonb end)
        || (case when jsonb_typeof(p -> 'detail') = 'object' then p -> 'detail' else '{}'::jsonb end);

  if v_at > now() + interval '5 minutes' or (v_end is not null and v_end > now() + interval '5 minutes') then
    raise exception 'occurred_at_in_future' using errcode = '22023';
  end if;
  if v_end is not null and v_end < v_at then
    raise exception 'ended_before_started' using errcode = '22023';
  end if;
  if v_ev.kind = 'feed' and v_ml is not null and (v_ml < 0 or v_ml > 1000) then
    raise exception 'bad_amount' using errcode = '22023';
  end if;
  if v_ev.kind = 'diaper' and coalesce(v_det ->> 'type', '') not in ('pee', 'poo', 'both') then
    raise exception 'bad_diaper_type' using errcode = '22023';
  end if;

  update public.care_events
     set occurred_at = v_at, ended_at = v_end, amount_ml = v_ml, detail = v_det
   where id = v_id;
  return jsonb_build_object('status', 'saved', 'id', v_id);
end;
$$;

-- ── 아기 프로필과 나이 ──
create table if not exists public.care_baby_profile (
  id         int primary key default 1 check (id = 1),   -- 한 줄만
  name       text not null,
  nickname   text,
  birth_date date not null,
  due_date   date                                        -- 예정일. 있으면 교정 나이를 센다
);
alter table public.care_baby_profile enable row level security;
revoke all on public.care_baby_profile from anon, authenticated;
grant select on public.care_baby_profile to authenticated;   -- 가족만(아래 정책). 고치기는 SQL Editor 에서
do $$ begin
  if not exists (select 1 from pg_policies where schemaname = 'public' and tablename = 'care_baby_profile' and policyname = 'care_baby_profile_read') then
    create policy care_baby_profile_read on public.care_baby_profile for select to authenticated using (public.care_is_family());
  end if;
end $$;
insert into public.care_baby_profile (id, name, nickname, birth_date, due_date)
values (1, '세훈', '알밤', '2026-06-18', '2026-07-10')
on conflict (id) do nothing;

-- 그날의 나이. 베이비타임처럼 태어난 날을 D+1, 개월 뒤 남은 날도 +1 로 센다
--   개월 = 생일에서 몇 달을 더해도 그날을 넘지 않는 가장 큰 수, 일 = 그날 - (생일 + 개월) + 1
--   2026-11-07: {"day":143,"months":4,"days":21,"corrected_day":121,"corrected_months":3,"corrected_days":29}
--   (Postgres age() 의 일 수는 달 길이를 다르게 빌려 와서 베이비타임과 하루 어긋날 수 있어 쓰지 않는다)
create or replace function public.care_months_days(p_on date, p_from date)
returns int[]
language sql immutable
set search_path = ''
as $$
  with m as (
    select (extract(year from age(p_on, p_from)) * 12 + extract(month from age(p_on, p_from)))::int as n
  )
  select array[m.n, (p_on - (p_from + make_interval(months => m.n))::date) + 1] from m;
$$;

create or replace function public.care_age(p_on date)
returns jsonb
language sql stable security definer
set search_path = ''
as $$
  select case when b.birth_date is null then null else jsonb_build_object(
    'day', p_on - b.birth_date + 1,
    'months', (public.care_months_days(p_on, b.birth_date))[1],
    'days', (public.care_months_days(p_on, b.birth_date))[2],
    'corrected_day', case when b.due_date is not null and p_on >= b.due_date then p_on - b.due_date + 1 end,
    'corrected_months', case when b.due_date is not null and p_on >= b.due_date then (public.care_months_days(p_on, b.due_date))[1] end,
    'corrected_days', case when b.due_date is not null and p_on >= b.due_date then (public.care_months_days(p_on, b.due_date))[2] end
  ) end
  from (select 1) one left join public.care_baby_profile b on b.id = 1;
$$;

-- ── 요약: 002 와 같고 baby·age 를 더함 ──
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
      select jsonb_build_object('id', e.id, 'at', e.occurred_at, 'ml', e.amount_ml)
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

revoke all on function public.care_update_event(jsonb) from public, anon;
grant execute on function public.care_update_event(jsonb) to authenticated;
revoke all on function public.care_months_days(date, date) from public, anon;
grant execute on function public.care_months_days(date, date) to authenticated;
revoke all on function public.care_age(date) from public, anon;
grant execute on function public.care_age(date) to authenticated;
revoke all on function public.care_summary() from public, anon;
grant execute on function public.care_summary() to authenticated;
revoke all on function public.care_events_on_update() from public, anon;
