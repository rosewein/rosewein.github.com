-- 알밤보드 019: 맞은 예방접종 모아 읽기(개인 폰 화면의 예방접종 일정표)
--
-- 018 다음에 실행한다(여러 번 실행해도 안전, 지우는 문장 없음).
--   - care_vaccines() : 예방접종 기록(kind = 'vaccine') 전체를 시각 순으로, 그리고 아기 생일·성별.
--       {"baby": {"birth_date": "…", "sex": "boy"}, "records": [{"id": "…", "at": "…", "text": "헥사심 1차", "hospital": "…"}]}
--       text 는 백신 이름(detail.memo, 없으면 detail.vaccine).
--       화면이 표준예방접종일정표(src/vaccines.js)와 맞춰 맞은 것·예약·남은 것을 보여 준다.

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
                where e.deleted_at is null and e.kind = 'vaccine')
  );
end;
$$;

revoke all on function public.care_vaccines() from public, anon;
grant execute on function public.care_vaccines() to authenticated;
