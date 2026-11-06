#!/usr/bin/env bash
# 임시 Postgres를 띄워 supabase/001_care_schema.sql 을 시험한다.
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
"${psql[@]}" -d t -f "$here/../supabase/001_care_schema.sql" >/dev/null
# 두 번 실행해도 되는지
"${psql[@]}" -d t -f "$here/../supabase/001_care_schema.sql" >/dev/null
"${psql[@]}" -d t -f "$here/schema_test.sql"
