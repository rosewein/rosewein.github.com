-- 알밤보드 013: 기록 종류에 산책·예방접종 더하기
--
-- 012 다음에 실행한다(여러 번 실행해도 안전, 지우는 문장 없음).
--   - walk    산책(시작~끝). 거의 매일 하는 일이라 [+] 더보기 맨 앞에 둔다. 전에는 '기타'에 묻혀 있었다
--   - vaccine 예방접종(한 시각 + 글). 백신 이름은 detail.memo. 병원 기록과 따로 두어 접종만 모아 볼 수 있게
--   - '기타'의 음성 이름에서 '산책'을 뺀다(산책이 따로 생겨서)

insert into public.care_record_types (key, label, shape, unit, step, min_value, max_value, default_value, icon, voice_aliases, show_in_more, sort) values
  ('walk',    '산책',     'range',   null, null, null, null, null, 'walk',    '{산책}', true, 5),
  ('vaccine', '예방접종', 'instant', null, null, null, null, null, 'vaccine', '{예방접종,접종}', true, 95)
on conflict (key) do nothing;

update public.care_record_types
   set voice_aliases = array_remove(voice_aliases, '산책')
 where key = 'other' and '산책' = any(voice_aliases);
