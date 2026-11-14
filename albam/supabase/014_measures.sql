-- 알밤보드 014: 측정 기록(체중·키·머리둘레) 모아 읽기, 아기 성별
--
-- 013 다음에 실행한다(여러 번 실행해도 안전, 지우는 문장 없음).
--   - care_baby_profile.sex : 'boy' / 'girl'. 성장 백분위(WHO 기준)는 성별마다 표가 달라서 필요하다.
--       처음엔 비어 있다. SQL Editor 에서 한 번 넣는다:  update public.care_baby_profile set sex = 'boy';
--   - care_measures() : 측정 기록 전체(시각 순)와 아기 생일·예정일·성별.
--       {"baby": {"birth_date": "…", "due_date": "…", "sex": "boy"}, "measures": [{"id": "…", "kind": "weight", "at": "…", "value": 7.35}]}
--       화면은 이것으로 (1) 측정 창을 지난번 값에서 시작하고 (2) 성장곡선·백분위(기본 나이·교정 나이)를 그린다.
--       백분위 셈은 화면이 한다(src/growth.js).

alter table public.care_baby_profile add column if not exists sex text;
do $$ begin
  if not exists (select 1 from pg_constraint where conname = 'care_baby_profile_sex_check') then
    alter table public.care_baby_profile add constraint care_baby_profile_sex_check check (sex in ('boy', 'girl'));
  end if;
end $$;

create or replace function public.care_measures()
returns jsonb
language plpgsql stable security definer
set search_path = ''
as $$
begin
  if not public.care_is_family() then
    raise exception 'not_family' using errcode = '42501';
  end if;
  return jsonb_build_object(
    'baby', (select jsonb_build_object('birth_date', b.birth_date, 'due_date', b.due_date, 'sex', b.sex)
             from public.care_baby_profile b where b.id = 1),
    'measures', (select coalesce(jsonb_agg(jsonb_build_object(
                          'id', e.id, 'kind', e.kind, 'at', e.occurred_at, 'value', e.value_num) order by e.occurred_at), '[]'::jsonb)
                 from public.care_events e
                 where e.deleted_at is null and e.value_num is not null and e.kind in ('weight', 'height', 'head'))
  );
end;
$$;

revoke all on function public.care_measures() from public, anon;
grant execute on function public.care_measures() to authenticated;
