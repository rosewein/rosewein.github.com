"""python3 -m unittest discover -s tests/tools  (npm test)"""
import os
import sys
import tempfile
import unittest
import zipfile
from datetime import date, datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'tools'))
import import_babytime as ib  # noqa: E402

EN = """2024-10-27 07:37 PM
Type: Pumping
====================
2024-10-27 12:08 PM
Type: Pee
Diaper type: Poop
====================
2024-10-27 08:26 AM ~ 2024-10-27 10:01 AM
Type: Day Sleep
Duration: 95 (min)
====================
2024-10-27 08:25 AM
Type: Pumped Milk
Pumped Milk Total Amount(ml): 5 (fl_oz)
====================
2024-10-03
Here's some garbage data
====================
2024-10-26 11:58 PM ~ 2024-10-27 02:19 AM
Type: Night Sleep
Duration: 140 (min)
====================
2024-10-26 11:13 PM
Type: Medicine
Medicine type: Analgesic
Memo: Tylenol
====================
2024-10-26 10:06 PM
Type: Formula
Formula Amount(ml): 160 (ml)
Memo: 잘 먹음
둘째 줄
====================
"""

KO = """2026-11-01 오후 1:20
종류: 분유
양: 160ml
====================
2026-11-01 오후 2:05
종류: 기저귀
기저귀 종류: 둘 다
====================
2026-11-01 13:30 ~ 2026-11-01 14:40
종류: 낮잠
====================
2026-11-01 오후 3:00
종류: 신기한것
====================
"""


class ImportTest(unittest.TestCase):
    def parse(self, text, **kw):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, 'activity_Sehun_202410.txt')
            with open(p, 'w', encoding='utf-8') as fh:
                fh.write(text)
            return ib.parse_files([p], **kw)

    def test_english(self):
        events, rep = self.parse(EN)
        kinds = [e['kind'] for e in events]
        self.assertEqual(kinds, ['feed', 'medication', 'sleep', 'feed', 'sleep', 'diaper'], '투약도 옮긴다(008)')
        events = [e for e in events if e['kind'] != 'medication']
        formula = events[0]
        self.assertEqual(formula['amount_ml'], 160)
        self.assertEqual(formula['occurred_at'], datetime(2024, 10, 26, 22, 6, tzinfo=ib.TZ))
        self.assertEqual(formula['detail']['memo'], '잘 먹음\n둘째 줄')
        night = events[1]
        self.assertEqual(night['ended_at'], datetime(2024, 10, 27, 2, 19, tzinfo=ib.TZ))
        pumped = events[2]
        self.assertEqual(pumped['amount_ml'], 148)  # 5 fl oz
        self.assertEqual(events[4]['detail']['type'], 'poo')
        self.assertEqual(rep['skipped'], {'Pumping': 1}, '엄마 유축만 건너뜀')
        self.assertEqual(rep['bad_date'] + rep['no_type'], 1)

    def test_korean_guess(self):
        events, rep = self.parse(KO)
        self.assertEqual([e['kind'] for e in events], ['feed', 'sleep', 'diaper'])
        self.assertEqual(events[0]['amount_ml'], 160)
        self.assertEqual(events[0]['occurred_at'].hour, 13)
        self.assertEqual(events[2]['detail']['type'], 'both')
        self.assertEqual(rep['unknown_types'], {'신기한것': 1})

    def test_idempotent_ids_and_range(self):
        a, _ = self.parse(EN)
        b, _ = self.parse(EN)
        self.assertEqual([e['id'] for e in a], [e['id'] for e in b])
        c, rep = self.parse(EN, until=date(2024, 10, 27))
        self.assertTrue(all(e['occurred_at'].date() < date(2024, 10, 27) for e in c))
        self.assertGreater(rep['out_of_range'], 0)

    def test_daily_stats(self):
        events, _ = self.parse(EN)
        days = ib.daily_stats(events)
        d26, d27 = days[date(2024, 10, 26)], days[date(2024, 10, 27)]
        self.assertEqual((d26['feed_count'], d26['feed_ml']), (1, 160))
        self.assertEqual(d26['sleep_min'], 0)
        self.assertEqual((d27['feed_count'], d27['feed_ml'], d27['poo']), (1, 148, 1))
        self.assertEqual(d27['sleep_min'], 95 + 141, '낮잠 95분 + 26일 23:58~27일 02:19 밤잠(깨는 아침 27일) 141분')
        table = ib.stats_table(days)
        self.assertIn('| 2024-10-26 (토) | 1회 | 160ml |', table)
        # 하루를 새벽 5시에 끊으면 26일 22:06 수유와 27일 08:25 수유가 각자 날짜에 남는다
        days5 = ib.daily_stats(events, day_start_hour=5)
        self.assertEqual(days5[date(2024, 10, 26)]['feed_count'], 1)

    def test_zip_and_sql(self):
        with tempfile.TemporaryDirectory() as d:
            z = os.path.join(d, 'activity_Sehun_202410.zip')
            with zipfile.ZipFile(z, 'w') as zf:
                zf.writestr('activity_Sehun_202410.txt', EN)
            events, _ = ib.parse_files([z])
        sql = ib.to_sql(events)
        self.assertIn('on conflict (id) do nothing', sql)
        self.assertIn("'import'", sql)
        lines = sql.split('$babytime$')[1].strip().split('\n')
        self.assertEqual(len(lines), len(events))
        self.assertEqual([ib.line_id(ib.id_line(l)) for l in lines], [e['id'] for e in events], 'id = md5(줄, 수유 끝 칸은 비움)')
        self.assertTrue(lines[0].startswith('feed|2024-10-26 22:06||160|'))


    def test_feed_duration_becomes_end_and_keeps_id(self):
        ko = '''====================
2026-11-01 06:14 AM
기록 종류: 분유
소요시간: 8 (분)
분유 총 양(ml): 170 (ml)
메모: 유산균
====================
2026-11-01 11:05 AM
기록 종류: 분유
분유 총 양(ml): 170 (ml)
====================
'''
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, 'activity_Sehun_202611.txt')
            with open(path, 'w', encoding='utf-8') as fh:
                fh.write(ko)
            events, _ = ib.parse_files([path])
        timed, untimed = events
        self.assertEqual(timed['ended_at'] - timed['occurred_at'], ib.timedelta(minutes=8), '소요시간 8분 → 끝')
        self.assertIsNone(untimed['ended_at'], '소요시간이 없으면 끝도 없음')
        line = ib.compact_line(timed)
        self.assertTrue(line.startswith('feed|2026-11-01 06:14|2026-11-01 06:22|170|'))
        legacy = line.replace('|2026-11-01 06:22|', '||')
        self.assertEqual(timed['id'], ib.line_id(legacy), '처음 옮긴 때(끝 없음)와 같은 id')
        self.assertIn("regexp_replace(l, '^(feed\\|[^|]*\\|)[^|]*', '\\1')", ib.SQL_TEMPLATE)


    def test_other_kinds(self):
        ko = '''====================
2026-08-18 08:53 AM
기록 종류: 열
체온: 37.1 (°C)
====================
2026-07-14 04:45 PM ~ 2026-07-14 04:50 PM
기록 종류: 목욕
소요시간: 5 (분)
메모: 보습로션
====================
2026-09-01 08:12 AM
기록 종류: 투약
약 종류: 기침감기약&비염콧물약
메모: 암브로콜시럽/코미에스시럽
====================
2026-08-18 08:50 AM
기록 종류: 병원
방문유형: 문진
병원명: 고려대학교 구로병원
방문사유: 예방접종(2개월 접종)
====================
2026-09-17 04:40 PM
기록 종류: 터미타임
소요시간: 4 (분)
====================
'''
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, 'activity_Sehun_202609.txt')
            with open(path, 'w', encoding='utf-8') as fh:
                fh.write(ko)
            events, rep = ib.parse_files([path])
        by = {e['kind']: e for e in events}
        self.assertEqual(set(by), {'temperature', 'bath', 'medication', 'hospital', 'tummy_time'})
        self.assertEqual(by['temperature']['value_num'], 37.1)
        self.assertTrue(ib.compact_line(by['temperature']).endswith('|37.1'), '체온은 여섯째 칸')
        self.assertEqual(by['bath']['ended_at'] - by['bath']['occurred_at'], ib.timedelta(minutes=5))
        self.assertEqual(by['bath']['detail']['memo'], '보습로션')
        self.assertEqual(by['medication']['detail']['medicine'], '기침감기약&비염콧물약')
        self.assertEqual(by['hospital']['detail']['hospital'], '고려대학교 구로병원')
        self.assertEqual(by['hospital']['detail']['reason'], '예방접종(2개월 접종)')
        self.assertEqual(by['tummy_time']['ended_at'] - by['tummy_time']['occurred_at'], ib.timedelta(minutes=4), '소요시간으로 끝')
        self.assertFalse(rep['unknown_keys'], rep['unknown_keys'])
        self.assertIn("nullif(split_part(l, '|', 6), '')::numeric", ib.SQL_TEMPLATE)


if __name__ == '__main__':
    unittest.main()
