-- 알밤케어 008: 기록 종류 표와 숫자 값(목욕·체온·투약·체중·키·메모 등)
--
-- 007 다음에 실행한다(여러 번 실행해도 안전, 지우는 문장 없음).
--   - care_record_types : 기록 종류마다 이름·모양·단위·범위. 여기에 한 줄 더하면 화면의 [+] 더보기에 나타난다
--       shape: instant(시각만) / range(시작~끝) / number(시각 + 숫자) / text(메모)
--   - care_events.value_num : 숫자 하나(체온 °C, 체중 kg, 키 cm). 수유량은 그대로 amount_ml
--   - 메모·약 이름 같은 글은 detail.memo / detail.medicine 처럼 detail 에 둔다
--   - care_add_event / care_update_event : value_num 을 받고, 숫자 기록은 범위를 확인한다
--   - care_summary : recent 에 value, 그리고 record_types 를 더함(007 과 나머지는 같음)
--   - care_timeline : value, memo, feeding, detail 을 더함(005 와 나머지는 같음)

alter table public.care_events add column if not exists value_num numeric;

create table if not exists public.care_record_types (
  key            text primary key check (key ~ '^[a-z][a-z_]{1,30}$'),
  label          text not null,
  shape          text not null check (shape in ('instant', 'range', 'number', 'text')),
  unit           text,
  step           numeric,          -- ± 버튼 한 번에(숫자 기록)
  min_value      numeric,
  max_value      numeric,
  default_value  numeric,          -- 처음 보여 줄 값(이전 기록이 없을 때)
  icon           text,
  voice_aliases  text[] not null default '{}',
  show_in_more   boolean not null default true,   -- [+] 더보기에 보일지(수유·기저귀·잠은 큰 버튼이 따로 있다)
  sort           int not null default 100,
  active         boolean not null default true
);
alter table public.care_record_types enable row level security;
revoke all on public.care_record_types from anon, authenticated;
grant select on public.care_record_types to authenticated;
do $$ begin
  if not exists (select 1 from pg_policies where schemaname = 'public' and tablename = 'care_record_types' and policyname = 'care_record_types_read') then
    create policy care_record_types_read on public.care_record_types for select to authenticated using (public.care_is_family());
  end if;
end $$;

-- 처음 종류들. 이미 있으면 그대로 둔다(가족이 SQL Editor 에서 고친 값을 덮지 않게)
insert into public.care_record_types (key, label, shape, unit, step, min_value, max_value, default_value, icon, voice_aliases, show_in_more, sort) values
  ('feed',        '수유',     'instant', 'ml', null, null, null, null, 'bottle', '{분유,수유,맘마}', false, 1),
  ('diaper',      '기저귀',   'instant', null, null, null, null, null, 'diaper', '{기저귀,소변,대변,오줌,응가}', false, 2),
  ('sleep',       '잠',       'range',   null, null, null, null, null, 'moon', '{잠,수면}', false, 3),
  ('bath',        '목욕',     'range',   null, null, null, null, null, 'bath', '{목욕}', true, 10),
  ('temperature', '체온',     'number',  '°C', 0.1, 34, 42, 36.8, 'thermo', '{체온,열}', true, 20),
  ('medication',  '투약',     'instant', null, null, null, null, null, 'pill', '{투약,약}', true, 30),
  ('weight',      '체중',     'number',  'kg', 0.01, 1, 30, 7.00, 'scale', '{체중,몸무게}', true, 40),
  ('height',      '키',       'number',  'cm', 0.1, 30, 120, 65.0, 'ruler', '{키}', true, 50),
  ('memo',        '메모',     'text',    null, null, null, null, null, 'memo', '{메모}', true, 60),
  ('tummy_time',  '터미타임', 'range',   null, null, null, null, null, 'tummy', '{터미타임}', true, 70),
  ('play',        '놀이',     'range',   null, null, null, null, null, 'play', '{놀이}', true, 80),
  ('hospital',    '병원',     'instant', null, null, null, null, null, 'hospital', '{병원}', true, 90),
  ('other',       '기타',     'range',   null, null, null, null, null, 'other', '{기타,산책}', true, 100)
on conflict (key) do nothing;

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
  v_num    numeric := nullif(p ->> 'value_num', '')::numeric;
  v_type   public.care_record_types;
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
  -- 숫자 기록(체온·체중·키)은 기록 종류 표의 범위 안이어야 한다
  select * into v_type from public.care_record_types t where t.key = v_kind;
  if found and v_type.shape = 'number'
     and (v_num is null or v_num < coalesce(v_type.min_value, v_num) or v_num > coalesce(v_type.max_value, v_num)) then
    raise exception 'bad_value' using errcode = '22023';
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
                                       'ml', v_dup.amount_ml, 'value', v_dup.value_num, 'detail', v_dup.detail));
    end if;
  end if;

  insert into public.care_events (id, kind, occurred_at, ended_at, amount_ml, value_num, detail, chore_id,
                                  source, recorded_by, voice_text)
  values (v_id, v_kind, v_at, v_end, v_ml, v_num, v_detail, nullif(p ->> 'chore_id', '')::uuid,
          coalesce(nullif(p ->> 'source', ''), 'living_room_touch'), auth.uid(), nullif(p ->> 'voice_text', ''));

  return jsonb_build_object('status', 'saved', 'id', v_id);
end;
$$;


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
  v_num numeric;
  v_type public.care_record_types;
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
  v_num := case when p ? 'value_num' then nullif(p ->> 'value_num', '')::numeric else v_ev.value_num end;
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
  select * into v_type from public.care_record_types t where t.key = v_ev.kind;
  if found and v_type.shape = 'number'
     and (v_num is null or v_num < coalesce(v_type.min_value, v_num) or v_num > coalesce(v_type.max_value, v_num)) then
    raise exception 'bad_value' using errcode = '22023';
  end if;

  update public.care_events
     set occurred_at = v_at, ended_at = v_end, amount_ml = v_ml, value_num = v_num, detail = v_det
   where id = v_id;
  return jsonb_build_object('status', 'saved', 'id', v_id);
end;
$$;


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
      -- ended_at: 다 먹은 시각(없으면 모름), feeding: 지금 먹이는 중(먹이기 시작하고 아직 '다 먹음'을 안 누름)
      select jsonb_build_object('id', e.id, 'at', e.occurred_at, 'ml', e.amount_ml, 'ended_at', e.ended_at,
                                'feeding', e.ended_at is null and coalesce((e.detail ->> 'feeding')::boolean, false))
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
               'ml', r.amount_ml, 'value', r.value_num, 'detail', r.detail, 'source', r.source) order by r.occurred_at desc), '[]'::jsonb)
      from (
        select * from public.care_events e
        where e.deleted_at is null
        order by e.occurred_at desc limit v_recent
      ) r
    ),

    -- 기록 종류 표(화면의 [+] 더보기·이름·단위가 여기서 나온다)
    'record_types', (
      select coalesce(jsonb_agg(jsonb_build_object('key', t.key, 'label', t.label, 'shape', t.shape, 'unit', t.unit,
               'step', t.step, 'min', t.min_value, 'max', t.max_value, 'default', t.default_value,
               'icon', t.icon, 'in_more', t.show_in_more, 'aliases', t.voice_aliases) order by t.sort), '[]'::jsonb)
      from public.care_record_types t where t.active
    ),

    'due_chores', '[]'::jsonb,

    'settings', jsonb_build_object(
      'day_start_hour', v_hour,
      'dup_window_minutes', v_window
    )
  );
end;
$$;



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
             'ml', e.amount_ml, 'value', e.value_num, 'type', e.detail ->> 'type',
             'memo', e.detail ->> 'memo', 'feeding', coalesce((e.detail ->> 'feeding')::boolean, false),
             'detail', e.detail) order by e.occurred_at), '[]'::jsonb)
    from public.care_events e
    where e.deleted_at is null
      and (e.occurred_at >= v_from or (e.kind = 'sleep' and (e.ended_at is null or e.ended_at >= v_from)
                                       and e.occurred_at >= v_from - interval '1 day'))
  );
end;
$$;


revoke all on function public.care_add_event(jsonb) from public, anon;
grant execute on function public.care_add_event(jsonb) to authenticated;
revoke all on function public.care_update_event(jsonb) from public, anon;
grant execute on function public.care_update_event(jsonb) to authenticated;
revoke all on function public.care_summary() from public, anon;
grant execute on function public.care_summary() to authenticated;
revoke all on function public.care_timeline(int) from public, anon;
grant execute on function public.care_timeline(int) to authenticated;
