-- 알밤케어 1단계: 표, 권한(RLS), 요약 함수, 기록 추가·취소 함수
--
-- 알밤위키 Supabase 프로젝트의 SQL Editor에 그대로 붙여 넣어 실행한다.
-- 여러 번 실행해도 안전하게 짰다(if not exists / create or replace).
--
-- 기존 알밤위키 표와 이름이 겹치지 않도록 모든 이름 앞에 care_ 를 붙였다.
-- 시간대는 Asia/Seoul. 실제 시각(occurred_at)과 입력 시각(recorded_at)을 따로 두고,
-- 기록은 지우지 않고 deleted_at 으로 취소 표시만 한다.

-- ---------------------------------------------------------------------------
-- 표
-- ---------------------------------------------------------------------------

-- 가족 계정. 여기에 있는 로그인 사용자만 기록을 읽고 쓴다.
-- 계정은 Authentication > Users 에서 만들고, 그 id를 아래처럼 넣는다.
--   insert into public.care_family (user_id, name) values ('<uuid>', '이지');
create table if not exists public.care_family (
  user_id    uuid primary key references auth.users (id) on delete cascade,
  name       text not null,
  created_at timestamptz not null default now()
);

-- 바꾸기 쉬운 설정값. 화면은 요약 결과의 settings 로 받는다.
create table if not exists public.care_settings (
  key   text primary key,
  value jsonb not null,
  note  text
);

insert into public.care_settings (key, value, note) values
  ('day_start_hour',     '0',  '하루를 끊는 시각(0~23). 0이면 자정'),
  ('dup_window_minutes', '10', '같은 종류 기록이 이 시간(분) 안에 있으면 확인을 묻는다'),
  ('quick_amount_count', '3',  '수유량 빠른 선택에 보여 줄 최근 양 개수'),
  ('recent_limit',       '8',  '요약에 넣을 최근 기록 개수')
on conflict (key) do nothing;

-- 집안일 규칙(2단계에서 채움). events.chore_id 가 가리킬 수 있게 표만 먼저 만든다.
create table if not exists public.care_chores (
  id            uuid primary key default gen_random_uuid(),
  name          text not null,
  trigger       text not null check (trigger in ('feed_count', 'weekday', 'daily')),
  trigger_value int,
  assignee      text,
  active        boolean not null default true,
  created_at    timestamptz not null default now()
);

-- 기록
create table if not exists public.care_events (
  id          uuid primary key default gen_random_uuid(),
  kind        text not null check (kind ~ '^[a-z][a-z_]{1,30}$'),  -- feed, diaper, sleep, chore_done …
  occurred_at timestamptz not null,                                 -- 실제 일어난 시각. 정렬·계산 기준
  ended_at    timestamptz,                                          -- 수면처럼 끝이 있는 기록
  recorded_at timestamptz not null default now(),                   -- 입력한 시각
  amount_ml   int check (amount_ml is null or amount_ml between 0 and 1000),
  detail      jsonb not null default '{}'::jsonb,                   -- 예: {"type": "poo"}
  chore_id    uuid references public.care_chores (id),
  source      text not null default 'living_room_touch',            -- living_room_touch, living_room_voice, phone, import
  recorded_by uuid default auth.uid(),
  voice_text  text,
  deleted_at  timestamptz,                                          -- 취소 표시
  constraint care_events_end_after_start check (ended_at is null or ended_at >= occurred_at)
);

create index if not exists care_events_kind_time
  on public.care_events (kind, occurred_at desc) where deleted_at is null;
create index if not exists care_events_time
  on public.care_events (occurred_at desc) where deleted_at is null;

-- ---------------------------------------------------------------------------
-- 권한: 가족만 읽고, 쓰기는 아래 함수로만
-- ---------------------------------------------------------------------------

create or replace function public.care_is_family()
returns boolean
language sql stable security definer
set search_path = ''
as $$
  select exists (select 1 from public.care_family f where f.user_id = auth.uid());
$$;

alter table public.care_family   enable row level security;
alter table public.care_settings enable row level security;
alter table public.care_chores   enable row level security;
alter table public.care_events   enable row level security;

revoke all on public.care_family, public.care_settings, public.care_chores, public.care_events from anon, authenticated;
grant select on public.care_family, public.care_settings, public.care_chores, public.care_events to authenticated;

drop policy if exists care_family_read   on public.care_family;
drop policy if exists care_settings_read on public.care_settings;
drop policy if exists care_chores_read   on public.care_chores;
drop policy if exists care_events_read   on public.care_events;
create policy care_family_read   on public.care_family   for select to authenticated using (public.care_is_family());
create policy care_settings_read on public.care_settings for select to authenticated using (public.care_is_family());
create policy care_chores_read   on public.care_chores   for select to authenticated using (public.care_is_family());
create policy care_events_read   on public.care_events   for select to authenticated using (public.care_is_family());

-- 설정값 읽기 (없으면 기본값)
create or replace function public.care_setting_int(p_key text, p_default int)
returns int
language sql stable security definer
set search_path = ''
as $$
  select coalesce((select (s.value #>> '{}')::int from public.care_settings s where s.key = p_key), p_default);
$$;

-- ---------------------------------------------------------------------------
-- 요약 함수: 화면은 이것 하나만 읽는다
-- 항목을 더할 때는 jsonb_build_object 에 키를 하나 더하면 된다.
-- ---------------------------------------------------------------------------

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
  v_quick   int := public.care_setting_int('quick_amount_count', 3);
  v_recent  int := public.care_setting_int('recent_limit', 8);
  v_local   timestamp;
  v_day     timestamptz;
begin
  if not public.care_is_family() then
    raise exception 'not_family' using errcode = '42501';
  end if;

  -- 오늘의 시작: 서울 시각으로 v_hour 시. 그 전이면 어제 v_hour 시.
  v_local := v_now at time zone tz;
  v_day := (date_trunc('day', v_local - make_interval(hours => v_hour)) + make_interval(hours => v_hour)) at time zone tz;

  return jsonb_build_object(
    'server_time', v_now,
    'day_start', v_day,

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

    -- 수유량 빠른 선택: 최근에 먹인 서로 다른 양, 최근 것부터
    'recent_feed_amounts', (
      select coalesce(jsonb_agg(t.ml order by t.last_at desc), '[]'::jsonb)
      from (
        select r.amount_ml as ml, max(r.occurred_at) as last_at
        from (
          select e.amount_ml, e.occurred_at
          from public.care_events e
          where e.kind = 'feed' and e.deleted_at is null and e.amount_ml is not null
          order by e.occurred_at desc limit 50
        ) r
        group by r.amount_ml
        order by last_at desc
        limit v_quick
      ) t
    ),

    -- 최근 기록(실제 시각 순). 나중에 넣는 기록 화면에서 자리 잡은 걸 확인하는 용도
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

    'due_chores', '[]'::jsonb,  -- 2단계

    'settings', jsonb_build_object(
      'day_start_hour', v_hour,
      'dup_window_minutes', v_window
    )
  );
end;
$$;

-- ---------------------------------------------------------------------------
-- 기록 추가 함수
--   입력: {"id"?, "kind", "occurred_at"?, "ended_at"?, "amount_ml"?, "detail"?,
--          "source"?, "voice_text"?, "force"?}
--   돌려줌: {"status": "saved", "id": …}
--          {"status": "confirm", "existing": {…}}   비슷한 시각에 같은 종류가 있음. force=true 로 다시 보내면 저장
--   id 를 화면이 만들어 보내므로, 연결이 끊겨 다시 보낸 기록은 두 번 들어가지 않는다.
-- ---------------------------------------------------------------------------

create or replace function public.care_add_event(p jsonb)
returns jsonb
language plpgsql volatile security definer
set search_path = ''
as $$
declare
  v_id     uuid := coalesce(nullif(p ->> 'id', '')::uuid, gen_random_uuid());
  v_kind   text := p ->> 'kind';
  v_at     timestamptz := coalesce(nullif(p ->> 'occurred_at', '')::timestamptz, now());
  v_end    timestamptz := nullif(p ->> 'ended_at', '')::timestamptz;
  v_ml     int := nullif(p ->> 'amount_ml', '')::numeric::int;
  v_detail jsonb := coalesce(p -> 'detail', '{}'::jsonb);
  v_force  boolean := coalesce((p ->> 'force')::boolean, false);
  v_window interval := make_interval(mins => public.care_setting_int('dup_window_minutes', 10));
  v_dup    public.care_events;
begin
  if not public.care_is_family() then
    raise exception 'not_family' using errcode = '42501';
  end if;

  -- 이미 받은 기록(재전송)이면 그대로 성공
  if exists (select 1 from public.care_events e where e.id = v_id) then
    return jsonb_build_object('status', 'saved', 'id', v_id, 'repeat', true);
  end if;

  if v_kind is null or v_kind !~ '^[a-z][a-z_]{1,30}$' then
    raise exception 'bad_kind' using errcode = '22023';
  end if;
  if v_at > now() + interval '5 minutes' then
    raise exception 'occurred_at_in_future' using errcode = '22023';
  end if;
  if v_kind = 'feed' and v_ml is not null and (v_ml < 0 or v_ml > 1000) then
    raise exception 'bad_amount' using errcode = '22023';
  end if;
  if v_kind = 'diaper' and coalesce(v_detail ->> 'type', '') not in ('pee', 'poo', 'both') then
    raise exception 'bad_diaper_type' using errcode = '22023';
  end if;
  if v_end is not null and v_end < v_at then
    raise exception 'ended_before_started' using errcode = '22023';
  end if;

  if not v_force then
    select e.* into v_dup
    from public.care_events e
    where e.kind = v_kind and e.deleted_at is null
      and e.occurred_at between v_at - v_window and v_at + v_window
    order by abs(extract(epoch from e.occurred_at - v_at))
    limit 1;
    if found then
      return jsonb_build_object(
        'status', 'confirm',
        'existing', jsonb_build_object('id', v_dup.id, 'kind', v_dup.kind, 'at', v_dup.occurred_at,
                                       'ml', v_dup.amount_ml, 'detail', v_dup.detail));
    end if;
  end if;

  insert into public.care_events (id, kind, occurred_at, ended_at, amount_ml, detail, chore_id,
                                  source, recorded_by, voice_text)
  values (v_id, v_kind, v_at, v_end, v_ml, v_detail, nullif(p ->> 'chore_id', '')::uuid,
          coalesce(nullif(p ->> 'source', ''), 'living_room_touch'), auth.uid(), nullif(p ->> 'voice_text', ''));

  return jsonb_build_object('status', 'saved', 'id', v_id);
end;
$$;

-- 취소: 지우지 않고 표시만
create or replace function public.care_cancel_event(p_id uuid)
returns jsonb
language plpgsql volatile security definer
set search_path = ''
as $$
begin
  if not public.care_is_family() then
    raise exception 'not_family' using errcode = '42501';
  end if;
  update public.care_events set deleted_at = now() where id = p_id and deleted_at is null;
  if found then
    return jsonb_build_object('status', 'cancelled', 'id', p_id);
  end if;
  return jsonb_build_object('status', case when exists (select 1 from public.care_events where id = p_id)
                                          then 'already_cancelled' else 'not_found' end, 'id', p_id);
end;
$$;

-- 함수는 로그인한 사용자만 부를 수 있게
revoke all on function public.care_is_family()            from public, anon;
revoke all on function public.care_setting_int(text, int) from public, anon;
revoke all on function public.care_summary()              from public, anon;
revoke all on function public.care_add_event(jsonb)       from public, anon;
revoke all on function public.care_cancel_event(uuid)     from public, anon;
grant execute on function public.care_is_family()            to authenticated;
grant execute on function public.care_setting_int(text, int) to authenticated;
grant execute on function public.care_summary()              to authenticated;
grant execute on function public.care_add_event(jsonb)       to authenticated;
grant execute on function public.care_cancel_event(uuid)     to authenticated;
