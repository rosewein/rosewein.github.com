-- 알밤보드 020: 영유아 건강검진(기록 종류, 받은 검진 모아 읽기)
--
-- 019 다음에 실행한다(여러 번 실행해도 안전, 지우는 문장 없음).
--   - 기록 종류 checkup(영유아검진): 한 시각 + 글("2차", "구강검진 1차"). 병원 기록과 따로 두어 검진만 모아 볼 수 있게
--   - care_vaccines() : 019 와 같고 checkups(받은 검진, 시각 순)를 더함.
--       화면이 검진 시기표(src/checkups.js)와 맞춰 받은 것·예약·남은 것을 보여 준다

insert into public.care_record_types (key, label, shape, unit, step, min_value, max_value, default_value, icon, voice_aliases, show_in_more, sort) values
  ('checkup', '영유아검진', 'instant', null, null, null, null, null, 'checkup', '{검진}', true, 97)
on conflict (key) do nothing;

create or replace function public.care_vaccines()
returns jsonb
language plpgsql stable security definer
set search_path = ''
as $$
begin
  if not public.care_is_family() then
    raise exception 'not_family' using errcode = '42501';
  end if;
  return jsonb_build_object(
    'baby', (select jsonb_build_object('birth_date', b.birth_date, 'sex', b.sex) from public.care_baby_profile b where b.id = 1),
    'records', (select coalesce(jsonb_agg(jsonb_build_object(
                         'id', e.id, 'at', e.occurred_at,
                         'text', coalesce(nullif(e.detail ->> 'memo', ''), e.detail ->> 'vaccine', ''),
                         'hospital', e.detail ->> 'hospital') order by e.occurred_at), '[]'::jsonb)
                from public.care_events e
                where e.deleted_at is null and e.kind = 'vaccine'),
    'checkups', (select coalesce(jsonb_agg(jsonb_build_object(
                         'id', e.id, 'at', e.occurred_at, 'text', coalesce(e.detail ->> 'memo', '')) order by e.occurred_at), '[]'::jsonb)
                 from public.care_events e
                 where e.deleted_at is null and e.kind = 'checkup')
  );
end;
$$;

revoke all on function public.care_vaccines() from public, anon;
grant execute on function public.care_vaccines() to authenticated;
