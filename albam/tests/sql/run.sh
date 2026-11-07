#!/usr/bin/env bash
# 임시 Postgres를 띄워 supabase/*.sql 을 시험한다. (npm run test:sql)
# 필요: PostgreSQL 14+ (initdb, pg_ctl, psql)
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
bin="${PG_BIN:-$(ls -d /usr/lib/postgresql/*/bin 2>/dev/null | sort -V | tail -1)}"
tmp="$(mktemp -d)"
trap '"$bin/pg_ctl" -D "$tmp/db" -m immediate stop >/dev/null 2>&1 || true; rm -rf "$tmp"' EXIT

run() { if [ "$(id -u)" = 0 ]; then su postgres -s /bin/bash -c "$*"; else bash -c "$*"; fi; }
[ "$(id -u)" = 0 ] && chown postgres "$tmp"

run "'$bin/initdb' -D '$tmp/db' -A trust -U postgres >/dev/null"
run "'$bin/pg_ctl' -D '$tmp/db' -o '-k $tmp -p 54329 -c listen_addresses=' -l '$tmp/log' start >/dev/null"
psql=(psql -h "$tmp" -p 54329 -U postgres -X -q -v ON_ERROR_STOP=1)
"${psql[@]}" -c 'create database t' >/dev/null
"${psql[@]}" -d t -f "$here/supabase_stub.sql" >/dev/null
# supabase/ 의 SQL 을 번호 순서대로, 두 번씩(여러 번 실행해도 되는지)
for round in 1 2; do
  for f in "$here"/../../supabase/[0-9]*.sql; do "${psql[@]}" -d t -f "$f" >/dev/null 2>&1 || { echo "FAIL: $f"; "${psql[@]}" -d t -f "$f"; exit 1; }; done
done
"${psql[@]}" -d t -f "$here/schema_test.sql"
# 확인용 쿼리(supabase/queries)가 문법 오류 없이 도는지
for q in "$here"/../../supabase/queries/*.sql; do
  "${psql[@]}" -d t -f "$q" >/dev/null || { echo "FAIL: $q"; exit 1; }
done
echo 'QUERIES OK'
