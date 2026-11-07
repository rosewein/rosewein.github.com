-- 날짜별 통계(서울 시각). 베이비타임에서 옮긴 뒤, import_babytime.py --stats 표와 맞춰 볼 때 SQL Editor 에서 실행한다.
-- 하루를 끊는 시각은 care_settings.day_start_hour 를 따른다. 잠은 시작한 날에 넣는다. 취소한 기록은 뺀다.
with s as (
  select coalesce((select (value #>> '{}')::int from public.care_settings where key = 'day_start_hour'), 0) as h
), e as (
  select ((occurred_at at time zone 'Asia/Seoul') - make_interval(hours => s.h))::date as day, *
  from public.care_events, s
  where deleted_at is null
)
select
  day as "날짜",
  count(*) filter (where kind = 'feed')                                   as "수유(회)",
  coalesce(sum(amount_ml) filter (where kind = 'feed'), 0)                as "수유량(ml)",
  count(*) filter (where kind = 'diaper' and detail ->> 'type' = 'pee')   as "소변",
  count(*) filter (where kind = 'diaper' and detail ->> 'type' = 'poo')   as "대변",
  count(*) filter (where kind = 'diaper' and detail ->> 'type' = 'both')  as "둘 다",
  coalesce(sum(extract(epoch from ended_at - occurred_at) / 60) filter (where kind = 'sleep'), 0)::int as "잠(분)"
from e
group by day
order by day desc;
