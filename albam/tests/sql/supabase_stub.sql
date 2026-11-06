-- 로컬 Postgres에서 001_care_schema.sql 을 시험하려고 Supabase의 auth 부분만 흉내 낸다.
-- 실제 Supabase에는 넣지 않는다.
create role anon nologin;
create role authenticated nologin;
create schema auth;
create table auth.users (id uuid primary key, email text);
create function auth.uid() returns uuid language sql stable as $$
  select nullif(current_setting('request.jwt.claim.sub', true), '')::uuid
$$;
grant usage on schema auth to anon, authenticated;
grant execute on function auth.uid() to anon, authenticated;
grant usage on schema public to anon, authenticated;
