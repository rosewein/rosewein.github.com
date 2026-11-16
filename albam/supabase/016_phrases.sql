-- 알밤보드 016: 자주 쓰는 문구(기록에 눌러서 붙이는 메모)
--
-- 015 다음에 실행한다(여러 번 실행해도 안전, 지우는 문장 없음).
--   - care_phrases : 기록 종류마다 자주 쓰는 문구. 수유의 "유산균", 목욕의 "보습로션"처럼
--       글을 치기 어려운 화면(거실·보드)에서 눌러서 고르려고 둔다. 더하고 지우는 건 개인 폰 화면에서 한다.
--       고른 문구는 그 기록의 detail.memo 에 " · " 로 이어 붙는다(따로 표를 두지 않는다)
--   - care_phrases() : 전체 문구 [{id, kind, text}], 종류 → 순서 → 넣은 때
--   - care_add_phrase(kind, text) : 더하기. 같은 문구가 이미 있으면 그대로(exists), 지웠던 문구면 되살린다
--   - care_remove_phrase(id) : 지우기(취소 표시만). 이미 붙인 메모는 그대로 남는다

create table if not exists public.care_phrases (
  id          uuid primary key default gen_random_uuid(),
  kind        text not null check (kind ~ '^[a-z][a-z_]{1,30}$'),
  text        text not null check (length(text) between 1 and 30 and position(' · ' in text) = 0),
  sort        int not null default 100,
  created_at  timestamptz not null default now(),
  created_by  uuid default auth.uid(),
  deleted_at  timestamptz
);
create unique index if not exists care_phrases_kind_text_idx on public.care_phrases (kind, text);
alter table public.care_phrases enable row level security;
revoke all on public.care_phrases from anon, authenticated;
grant select on public.care_phrases to authenticated;
do $$ begin
  if not exists (select 1 from pg_policies where schemaname = 'public' and tablename = 'care_phrases' and policyname = 'care_phrases_read') then
    create policy care_phrases_read on public.care_phrases for select to authenticated using (public.care_is_family());
  end if;
end $$;

create or replace function public.care_phrases()
returns jsonb
language plpgsql stable security definer
set search_path = ''
as $$
begin
  if not public.care_is_family() then
    raise exception 'not_family' using errcode = '42501';
  end if;
  return (
    select coalesce(jsonb_agg(jsonb_build_object('id', p.id, 'kind', p.kind, 'text', p.text) order by p.kind, p.sort, p.created_at), '[]'::jsonb)
    from public.care_phrases p
    where p.deleted_at is null
  );
end;
$$;

create or replace function public.care_add_phrase(p_kind text, p_text text)
returns jsonb
language plpgsql volatile security definer
set search_path = ''
as $$
declare
  v_text text := trim(coalesce(p_text, ''));
  v_row  public.care_phrases;
begin
  if not public.care_is_family() then
    raise exception 'not_family' using errcode = '42501';
  end if;
  if coalesce(p_kind, '') !~ '^[a-z][a-z_]{1,30}$' or length(v_text) not between 1 and 30 or position(' · ' in v_text) > 0 then
    raise exception 'bad_phrase' using errcode = '22023';
  end if;
  select * into v_row from public.care_phrases where kind = p_kind and text = v_text;
  if found and v_row.deleted_at is null then
    return jsonb_build_object('status', 'exists', 'id', v_row.id);
  elsif found then
    update public.care_phrases set deleted_at = null, created_at = now() where id = v_row.id;
    return jsonb_build_object('status', 'saved', 'id', v_row.id);
  end if;
  insert into public.care_phrases (kind, text) values (p_kind, v_text) returning * into v_row;
  return jsonb_build_object('status', 'saved', 'id', v_row.id);
end;
$$;

create or replace function public.care_remove_phrase(p_id uuid)
returns jsonb
language plpgsql volatile security definer
set search_path = ''
as $$
begin
  if not public.care_is_family() then
    raise exception 'not_family' using errcode = '42501';
  end if;
  update public.care_phrases set deleted_at = now() where id = p_id and deleted_at is null;
  return jsonb_build_object('status', case when found then 'removed' else 'not_found' end, 'id', p_id);
end;
$$;

revoke all on function public.care_phrases() from public, anon;
revoke all on function public.care_add_phrase(text, text) from public, anon;
revoke all on function public.care_remove_phrase(uuid) from public, anon;
grant execute on function public.care_phrases() to authenticated;
grant execute on function public.care_add_phrase(text, text) to authenticated;
grant execute on function public.care_remove_phrase(uuid) to authenticated;
