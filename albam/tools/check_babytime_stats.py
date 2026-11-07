#!/usr/bin/env python3
"""베이비타임에서 옮긴 기록이 맞는지, 베이비타임 자체 통계와 날짜별로 맞춰 본다.

    python3 tools/check_babytime_stats.py --activity activity_알밤_*_asc.txt --stat stat_알밤_*.zip

- activity: 기록 하나하나(import_babytime.py 가 읽는 파일)
- stat: 베이비타임 '통계 내보내기'(zip 안 other_stat_이름_연월.csv). 하루 합계가 들어 있다
- 날짜별로 분유 횟수·양, 기저귀(총·소변·대변), 잠(낮잠+밤잠) 합계를 비교하고 다른 날만 보여 준다.
  베이비타임 통계는 기저귀 '둘 다'를 소변·대변 양쪽에 센다. 잠은 낮잠은 그날, 밤잠은 깨는 아침의 날에 센다
  (import_babytime.stat_day, supabase/003_stats.sql 과 같은 규칙).
  2026년 7월 말~8월 초는 베이비타임이 밤잠을 다르게 나눠 잠 합계가 다를 수 있다. 기록 자체는 같다.
"""
import argparse
import csv
import io
import os
import re
import sys
import zipfile
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import import_babytime as ib  # noqa: E402

STAT_COLUMNS = {
    'feed_count': '분유 횟수', 'feed_ml': '분유 총 양(ml)',
    'diaper_total': '기저귀 총 횟수', 'pee': '기저귀 소변 횟수', 'poo': '기저귀 대변 횟수',
    'nap_min': '낮잠 시간', 'night_min': '밤잠 시간',
}


def read_stat(paths):
    """통계 파일 → {날짜: {항목: 값}}. 기록이 없는 날은 뺀다"""
    days = {}
    for path in paths:
        texts = []
        if path.lower().endswith('.zip'):
            with zipfile.ZipFile(path) as z:
                texts = [z.read(n).decode('utf-8-sig') for n in z.namelist() if re.search(r'other_stat_.*\.csv$', n)]
        else:
            with open(path, encoding='utf-8-sig') as fh:
                texts = [fh.read()]
        for text in texts:
            for row in csv.DictReader(io.StringIO(text)):
                v = {k: int(round(float(row.get(c) or 0))) for k, c in STAT_COLUMNS.items()}
                if any(v.values()):
                    v['sleep_min'] = v.pop('nap_min') + v.pop('night_min')
                    days[date.fromisoformat(row['date'].split()[0])] = v
    return days


def from_events(events):
    """옮긴 기록 → 베이비타임 통계와 같은 규칙의 날짜별 합계"""
    days = {}
    for e in events:
        d = days.setdefault(ib.stat_day(e), {'feed_count': 0, 'feed_ml': 0, 'diaper_total': 0, 'pee': 0, 'poo': 0, 'sleep_min': 0})
        if e['kind'] == 'feed':
            d['feed_count'] += 1
            d['feed_ml'] += e['amount_ml'] or 0
        elif e['kind'] == 'diaper':
            t = e['detail']['type']
            d['diaper_total'] += 1
            d['pee'] += t in ('pee', 'both')
            d['poo'] += t in ('poo', 'both')
        elif e['kind'] == 'sleep':
            d['sleep_min'] += int((e['ended_at'] - e['occurred_at']).total_seconds() // 60)
    return days


def compare(mine, theirs):
    """다른 날 목록: [(날짜, 항목, 옮긴 값, 베이비타임 값)]"""
    diffs = []
    for day in sorted(set(mine) | set(theirs)):
        a, b = mine.get(day, {}), theirs.get(day, {})
        for key in ('feed_count', 'feed_ml', 'diaper_total', 'pee', 'poo', 'sleep_min'):
            if a.get(key, 0) != b.get(key, 0):
                diffs.append((day, key, a.get(key, 0), b.get(key, 0)))
    return diffs


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--activity', nargs='+', required=True)
    ap.add_argument('--stat', nargs='+', required=True)
    args = ap.parse_args(argv)
    events, report = ib.parse_files(args.activity)
    mine, theirs = from_events(events), read_stat(args.stat)
    diffs = compare(mine, theirs)
    print(f'날짜 {len(theirs)}일, 기록 {len(events)}건을 맞춰 봄. 다른 곳 {len(diffs)}개')
    for day, key, a, b in diffs:
        print(f'  {day} {key}: 옮긴 기록 {a} / 베이비타임 {b}')
    print('옮기지 않은 기록:', {k: v for k, v in report.items() if k in ('skipped', 'diaper_without_type', 'sleep_without_end') and v})


if __name__ == '__main__':
    main()
