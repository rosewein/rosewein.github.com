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
        self.assertEqual(kinds, ['feed', 'sleep', 'feed', 'sleep', 'diaper'])
        formula = events[0]
        self.assertEqual(formula['amount_ml'], 160)
        self.assertEqual(formula['occurred_at'], datetime(2024, 10, 26, 22, 6, tzinfo=ib.TZ))
        self.assertEqual(formula['detail']['memo'], '잘 먹음\n둘째 줄')
        night = events[1]
        self.assertEqual(night['ended_at'], datetime(2024, 10, 27, 2, 19, tzinfo=ib.TZ))
        pumped = events[2]
        self.assertEqual(pumped['amount_ml'], 148)  # 5 fl oz
        self.assertEqual(events[4]['detail']['type'], 'poo')
        self.assertEqual(rep['skipped'], {'Pumping': 1, 'Medicine': 1})
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
        self.assertIn("on conflict (id) do nothing", sql)
        self.assertIn("'import'", sql)
        self.assertEqual(sql.count("\n  ("), len(events))


if __name__ == '__main__':
    unittest.main()
