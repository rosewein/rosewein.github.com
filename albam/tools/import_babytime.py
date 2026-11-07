#!/usr/bin/env python3
"""베이비타임 월별 내보내기 파일을 care_events 로 옮기는 SQL을 만든다.

    python3 tools/import_babytime.py activity_세훈_202610.zip activity_세훈_202611.txt > import.sql
    python3 tools/import_babytime.py --until 2026-11-10 activity_*.zip > import.sql
    python3 tools/import_babytime.py activity_*.zip -o import.sql --stats stats.md   # 날짜별 통계도

만든 import.sql 을 Supabase SQL Editor 에 붙여 실행한다. 표준 라이브러리만 쓴다(Python 3.9+).

- 파일 형식은 R 패키지 babyTimeR 가 읽는 형식을 따랐다. 기록 하나는
      2024-11-27 05:41 AM ~ 2024-11-27 06:20 AM
      Type: Night Sleep
      Duration: 39 (min)
      ====================
  처럼 날짜 줄, "이름: 값" 줄들, 구분선으로 되어 있다.
- 한국어로 내보낸 파일의 항목 이름은 아직 예시 파일을 못 봐서 짐작으로 넣어 두었다.
  처음 돌릴 때 끝에 나오는 "모르는 종류/항목" 보고를 보고 TYPE_MAP·KEY 목록을 맞춘다.
- 기록마다 한 줄('종류|시작|끝|양|세부')로 바꿔 보내고, id 는 그 줄의 md5 로 정한다.
  그래서 SQL 이 작고(2천여 건에 100KB 안팎), 같은 파일을 두 번 넣어도 한 번만 들어간다.
- 거실 화면을 쓰기 시작한 뒤의 기록은 --until 로 잘라서 겹치지 않게 한다.
"""
import argparse
import hashlib
import io
import json
import re
import sys
import uuid
import zipfile
from datetime import datetime, timedelta, date
from zoneinfo import ZoneInfo

TZ = ZoneInfo('Asia/Seoul')
SEP = re.compile(r'^\s*={5,}\s*$')
FL_OZ_ML = 29.5735

# 베이비타임 종류 → (kind, detail)
TYPE_MAP = {
    # 수유
    'formula': ('feed', {'method': 'formula'}),
    'pumped milk': ('feed', {'method': 'pumped'}),
    'bottle': ('feed', {'method': 'bottle'}),
    'breastfeeding': ('feed', {'method': 'breast'}),
    '분유': ('feed', {'method': 'formula'}),
    '유축수유': ('feed', {'method': 'pumped'}),
    '유축 수유': ('feed', {'method': 'pumped'}),
    '젖병': ('feed', {'method': 'bottle'}),
    '모유': ('feed', {'method': 'breast'}),
    '모유수유': ('feed', {'method': 'breast'}),
    '수유': ('feed', {}),
    # 기저귀
    'pee': ('diaper', {'type': 'pee'}),
    'poop': ('diaper', {'type': 'poo'}),
    'diaper': ('diaper', {}),
    '소변': ('diaper', {'type': 'pee'}),
    '대변': ('diaper', {'type': 'poo'}),
    '기저귀': ('diaper', {}),
    # 수면
    'sleep': ('sleep', {}),
    'day sleep': ('sleep', {'when': 'day'}),
    'night sleep': ('sleep', {'when': 'night'}),
    '수면': ('sleep', {}),
    '낮잠': ('sleep', {'when': 'day'}),
    '밤잠': ('sleep', {'when': 'night'}),
}
# 옮기지 않는 종류(엄마 유축, 투약 등). 보고에만 센다
SKIP_TYPES = {'pumping', '유축', 'medicine', '투약', 'baby food', '이유식', 'bath', '목욕', 'temperature', '체온', '열', '기타',
              'hospital', '병원', 'play', '놀이', 'tummy time', '터미타임', 'snack', '간식', 'growth', '성장'}

TYPE_KEYS = {'type', '종류', '기록 종류', '타입', '유형'}
DIAPER_KEYS = {'diaper type', '기저귀 종류', '기저귀 상태', '배변', '배변 형태'}
DURATION_KEYS = {'duration', '시간', '소요 시간', '소요시간'}
MEMO_KEYS = {'memo', '메모'}
COLOR_KEYS = {'배변색', 'poop color'}
DIAPER_VALUES = {'pee': 'pee', 'wet': 'pee', '소변': 'pee', 'poop': 'poo', 'poo': 'poo', 'dirty': 'poo', '대변': 'poo',
                 'both': 'both', 'mixed': 'both', 'pee and poop': 'both', '둘 다': 'both', '둘다': 'both', '소변+대변': 'both', '혼합': 'both'}

DT_RE = re.compile(r'(\d{4})[-./](\d{1,2})[-./](\d{1,2})\.?\s+(?:(오전|오후|AM|PM|am|pm)\s*)?(\d{1,2}):(\d{2})\s*(AM|PM|am|pm|오전|오후)?')


def parse_dt(text):
    m = DT_RE.search(text)
    if not m:
        return None
    y, mo, d, p1, h, mi, p2 = m.groups()
    h, mi = int(h), int(mi)
    period = (p1 or p2 or '').lower()
    if period in ('pm', '오후') and h < 12:
        h += 12
    if period in ('am', '오전') and h == 12:
        h = 0
    return datetime(int(y), int(mo), int(d), h, mi, tzinfo=TZ)


def parse_amount(key, value):
    """'9.5 (fl_oz)', '160 ml', '160' → ml(정수). 온스면 ml 로 바꾼다.
    'Amount(ml): 9.5 (fl_oz)' 처럼 이름과 값의 단위가 다르면 값 쪽 단위를 믿는다."""
    m = re.search(r'(\d+(?:\.\d+)?)', value)
    if not m:
        return None
    n = float(m.group(1))
    value_unit = value[m.end():].lower()
    key_unit = key.lower()
    if 'oz' in value_unit or ('oz' in key_unit and 'ml' not in value_unit):
        n *= FL_OZ_ML
    return int(round(n))


def parse_minutes(value):
    """'95 (min)', '1시간 35분', '35분', '95' → 분"""
    hours = re.search(r'(\d+)\s*(?:시간|h)', value)
    mins = re.search(r'(\d+)\s*(?:\(min\)|min|분)', value)
    h = int(hours.group(1)) if hours else 0
    if mins:
        return h * 60 + int(mins.group(1))
    if hours:
        return h * 60
    bare = re.search(r'(\d+)', value)
    return int(bare.group(1)) if bare else None


def read_blocks(text):
    """구분선(=====)으로 나눈 기록 덩어리들. 빈 줄은 뺀다."""
    block = []
    for line in text.splitlines():
        if SEP.match(line):
            if block:
                yield block
            block = []
        elif line.strip():
            block.append(line.rstrip('\ufeff').rstrip())
    if block:
        yield block


def bump(report, name, key=None):
    """보고서 숫자 올리기. key 가 있으면 report[name][key] 를 센다."""
    if key is None:
        report[name] += 1
    else:
        report[name][key] = report[name].get(key, 0) + 1


def parse_header(line):
    """'2024-11-27 05:41 AM ~ 2024-11-27 06:20 AM' → (시작, 끝 또는 None)"""
    parts = re.split(r'\s+~\s+', line)
    start = parse_dt(parts[0])
    end = parse_dt(parts[1]) if len(parts) > 1 else None
    return start, end


def parse_fields(lines):
    """'이름: 값' 줄들 → dict. 'Memo:' 뒤는 여러 줄이어도 모두 메모로 합친다."""
    fields = {}
    for i, line in enumerate(lines):
        if ':' not in line:
            continue
        key, value = (x.strip() for x in line.split(':', 1))
        if key.lower() in MEMO_KEYS:
            fields['memo'] = '\n'.join([value] + lines[i + 1:]).strip()
            break
        fields[key] = value
    return fields


def classify(type_value):
    """베이비타임 종류 → (kind, detail) / 'skip' / None(모름)"""
    t = type_value.strip().lower()
    if t in SKIP_TYPES:
        return 'skip'
    if t in TYPE_MAP:
        return TYPE_MAP[t]
    # "Breastfeeding (Left)" 같은 변형
    return next((val for name, val in TYPE_MAP.items() if t.startswith(name)), None)


def apply_fields(ev, fields, report):
    """종류 말고 나머지 항목(기저귀 종류, 시간, 양, 메모)을 기록에 채운다."""
    detail = ev['detail']
    for key, value in fields.items():
        k = key.lower()
        if k in TYPE_KEYS:
            continue
        if key == 'memo':
            detail['memo'] = value
        elif k in COLOR_KEYS:
            detail['color'] = value
        elif k in DIAPER_KEYS:
            if value.strip().lower() in DIAPER_VALUES:
                detail['type'] = DIAPER_VALUES[value.strip().lower()]
        elif k in DURATION_KEYS:
            minutes = parse_minutes(value)
            if minutes is not None:
                detail['duration_min'] = minutes
        elif 'amount' in k or '양' in key or 'ml' in k:
            # 양 줄이 여럿(왼쪽·오른쪽·합계)이면 합계를 쓴다
            if ev['amount_ml'] is None or 'total' in k or '합계' in key or '총' in key:
                ev['amount_ml'] = parse_amount(key, value)
        else:
            bump(report, 'unknown_keys', key)


def parse_block(lines, report):
    """기록 덩어리 하나 → care_events 한 줄(dict). 옮기지 않을 것이면 None 이고 이유를 report 에 센다."""
    start, end = parse_header(lines[0])
    if not start:
        bump(report, 'bad_date')
        return None

    fields = parse_fields(lines[1:])
    type_value = next((v for k, v in fields.items() if k.lower() in TYPE_KEYS), None)
    if not type_value:
        bump(report, 'no_type')
        return None
    mapped = classify(type_value)
    if mapped == 'skip':
        bump(report, 'skipped', type_value)
        return None
    if mapped is None:
        bump(report, 'unknown_types', type_value)
        return None

    kind, base_detail = mapped
    ev = {'kind': kind, 'occurred_at': start, 'ended_at': None, 'amount_ml': None,
          'detail': {**base_detail, 'babytime_type': type_value}}
    apply_fields(ev, fields, report)

    # 종류별 마무리 확인
    if kind == 'diaper' and 'type' not in ev['detail']:
        bump(report, 'diaper_without_type')
        return None
    if kind == 'sleep':
        if end is None and ev['detail'].get('duration_min'):
            end = start + timedelta(minutes=ev['detail']['duration_min'])
        if end is None or end <= start:
            bump(report, 'sleep_without_end')
            return None
        ev['ended_at'] = end
    if kind == 'feed' and ev['amount_ml'] is not None and not 0 <= ev['amount_ml'] <= 1000:
        bump(report, 'bad_amount')
        ev['amount_ml'] = None
    # 수유 '소요시간'은 다 먹은 시각(끝)으로 둔다(supabase/007)
    if kind == 'feed' and ev['detail'].get('duration_min'):
        ev['ended_at'] = start + timedelta(minutes=ev['detail']['duration_min'])

    # 내용으로 id 를 정해 같은 파일을 다시 넣어도 한 번만 들어가게
    ev['id'] = line_id(id_line(compact_line(ev)))
    return ev


def read_input(path):
    if path.lower().endswith('.zip'):
        with zipfile.ZipFile(path) as z:
            for name in z.namelist():
                if name.lower().endswith('.txt'):
                    yield name, z.read(name).decode('utf-8-sig', errors='replace')
    else:
        with open(path, encoding='utf-8-sig', errors='replace') as fh:
            yield path, fh.read()


def new_report():
    return {'events': 0, 'by_kind': {}, 'bad_date': 0, 'no_type': 0, 'skipped': {}, 'unknown_types': {}, 'unknown_keys': {},
            'diaper_without_type': 0, 'sleep_without_end': 0, 'bad_amount': 0, 'out_of_range': 0}


def parse_files(paths, since=None, until=None, report=None):
    report = report or new_report()
    seen = {}
    for path in paths:
        for _, text in read_input(path):
            for block in read_blocks(text):
                ev = parse_block(block, report)
                if not ev:
                    continue
                d = ev['occurred_at'].date()
                if (since and d < since) or (until and d >= until):
                    report['out_of_range'] += 1
                    continue
                seen[ev['id']] = ev
    events = sorted(seen.values(), key=lambda e: e['occurred_at'])
    report['events'] = len(events)
    for e in events:
        report['by_kind'][e['kind']] = report['by_kind'].get(e['kind'], 0) + 1
    return events, report


def compact_line(e):
    """기록 → 한 줄. '종류|시작|끝|양|세부JSON'. 시각은 서울 'YYYY-MM-DD HH:MM'.
    세부에서 베이비타임 원래 이름과 소요시간(끝-시작으로 다시 셀 수 있음)은 뺀다."""
    fmt = lambda t: t.astimezone(TZ).strftime('%Y-%m-%d %H:%M') if t else ''
    detail = {k: (str(v).replace('|', '/').replace('\n', ' ') if k == 'memo' else v)
              for k, v in e['detail'].items() if k not in ('babytime_type', 'duration_min')}
    ml = '' if e['amount_ml'] is None else str(int(e['amount_ml']))
    return '|'.join([e['kind'], fmt(e['occurred_at']), fmt(e['ended_at']), ml,
                     json.dumps(detail, ensure_ascii=False, separators=(',', ':'))])


def id_line(line):
    """id 를 셀 때 쓰는 줄: 수유의 끝 칸은 비운다.
    2026-11-07 에 처음 옮길 때는 수유 끝을 넣지 않았으므로, 끝을 넣은 지금도 같은 id 가 나와야 다시 넣어도 겹치지 않는다.
    SQL_TEMPLATE 의 regexp_replace 와 같은 일을 한다."""
    if line.startswith('feed|'):
        kind, start, _end, rest = line.split('|', 3)
        return '|'.join([kind, start, '', rest])
    return line


def line_id(line):
    """한 줄의 id. SQL 의 md5('babytime|' || 줄)::uuid 와 같다(줄은 id_line 을 거친 것)"""
    return str(uuid.UUID(hashlib.md5(('babytime|' + line).encode('utf-8')).hexdigest()))


SQL_TEMPLATE = """-- 베이비타임에서 옮긴 기록 {count}건. Supabase SQL Editor 에서 실행(두 번 실행해도 한 번만 들어감)
insert into public.care_events (id, kind, occurred_at, ended_at, amount_ml, detail, source, recorded_by)
select md5('babytime|' || regexp_replace(l, '^(feed\\|[^|]*\\|)[^|]*', '\\1'))::uuid,   -- id 는 수유 끝 칸을 비우고 센다(id_line)
       split_part(l, '|', 1),
       split_part(l, '|', 2)::timestamp at time zone 'Asia/Seoul',
       nullif(split_part(l, '|', 3), '')::timestamp at time zone 'Asia/Seoul',
       nullif(split_part(l, '|', 4), '')::int,
       split_part(l, '|', 5)::jsonb,
       'import', null
from unnest(string_to_array($babytime$
{lines}
$babytime$, E'\\n')) as l
where l <> ''
on conflict (id) do nothing;
"""


def to_sql(events):
    lines = [compact_line(e) for e in events]
    return SQL_TEMPLATE.format(count=len(lines), lines='\n'.join(lines))


def stat_day(e, day_start_hour=0):
    """통계에서 이 기록을 셀 날짜(supabase/003_stats.sql 의 규칙과 같다).
    수유·기저귀·낮잠은 일어난 날, 밤잠은 깨는 아침의 날(시작 + 12시간)."""
    start = e['occurred_at'].astimezone(TZ)
    if e['kind'] == 'sleep':
        when = e['detail'].get('when') or ('night' if start.hour >= 18 or start.hour < 6 else 'day')
        if when == 'night':
            return (start + timedelta(hours=12)).date()
    return (start - timedelta(hours=day_start_hour)).date()


def daily_stats(events, day_start_hour=0):
    """날짜별 통계(서울 시각). 베이비타임 앱의 통계 화면과 맞춰 보려고 쓴다. 날짜 규칙은 stat_day()"""
    days = {}
    for e in events:
        d = days.setdefault(stat_day(e, day_start_hour), {'feed_count': 0, 'feed_ml': 0, 'pee': 0, 'poo': 0, 'both': 0, 'sleep_min': 0})
        if e['kind'] == 'feed':
            d['feed_count'] += 1
            d['feed_ml'] += e['amount_ml'] or 0
        elif e['kind'] == 'diaper':
            d[e['detail']['type']] += 1
        elif e['kind'] == 'sleep':
            d['sleep_min'] += int((e['ended_at'] - e['occurred_at']).total_seconds() // 60)
    return dict(sorted(days.items()))


def stats_table(days):
    """날짜별 통계를 마크다운 표로"""
    rows = ['| 날짜 | 수유 | 수유량 | 기저귀 소변 | 대변 | 둘 다 | 잠 |', '| --- | ---: | ---: | ---: | ---: | ---: | ---: |']
    for d, v in days.items():
        sleep = f"{v['sleep_min'] // 60}시간 {v['sleep_min'] % 60}분" if v['sleep_min'] else '-'
        rows.append(f"| {d.isoformat()} ({'월화수목금토일'[d.weekday()]}) | {v['feed_count']}회 | {v['feed_ml']}ml | "
                    f"{v['pee']} | {v['poo']} | {v['both']} | {sleep} |")
    return '\n'.join(rows) + '\n'


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('files', nargs='+', help='activity_이름_연월.txt 또는 .zip')
    ap.add_argument('--since', type=date.fromisoformat, help='이 날짜(포함)부터만')
    ap.add_argument('--until', type=date.fromisoformat, help='이 날짜(제외) 전까지만. 거실 화면을 쓰기 시작한 날')
    ap.add_argument('-o', '--output', help='SQL 파일 (없으면 화면에)')
    ap.add_argument('--stats', help='날짜별 통계 표(마크다운)를 이 파일에. 베이비타임 앱 통계와 맞춰 볼 때')
    ap.add_argument('--day-start-hour', type=int, default=0, help='하루를 끊는 시각(기본 0시). care_settings.day_start_hour 와 같게')
    args = ap.parse_args(argv)
    events, report = parse_files(args.files, args.since, args.until)
    if args.stats:
        with open(args.stats, 'w', encoding='utf-8') as fh:
            fh.write(stats_table(daily_stats(events, args.day_start_hour)))
    sql = to_sql(events)
    if args.output:
        with open(args.output, 'w', encoding='utf-8') as fh:
            fh.write(sql)
    else:
        sys.stdout.write(sql)
    print('\n[보고] ' + json.dumps(report, ensure_ascii=False, indent=1), file=sys.stderr)
    if report['unknown_types'] or report['unknown_keys']:
        print('모르는 종류/항목이 있어요. tools/import_babytime.py 의 TYPE_MAP·KEY 목록에 넣고 다시 돌려 주세요.', file=sys.stderr)


if __name__ == '__main__':
    main()
