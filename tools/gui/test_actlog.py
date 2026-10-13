#!/usr/bin/env python3
"""actlog 離線測試：分檔寫入、14 天清理、show 跨小時 / 跨午夜 / grep；全在暫存資料夾。"""
import testenv  # noqa: F401  必須最先
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

import actlog


class T(unittest.TestCase):
    def setUp(self):
        self.d = Path(tempfile.mkdtemp(prefix='actlogtest-'))
        self.log = self.d / 'actions.log'

    def test_add_writes_both(self):
        actlog.add('walk', 'a', path=self.log, keep=3)
        for i in range(5):
            actlog.add('click', str(i), path=self.log, keep=3)
        self.assertEqual(len(self.log.read_text(encoding='utf-8').splitlines()), 3)
        fs = list((self.d / 'actions').glob('*.log'))
        self.assertEqual(len(fs), 1)
        self.assertEqual(len(fs[0].read_text(encoding='utf-8').splitlines()), 6)  # 分檔不截斷
        self.assertRegex(fs[0].name, r'^\d{4}-\d\d-\d\d_\d\d\.log$')

    def test_prune(self):
        ad = self.d / 'actions'
        ad.mkdir()
        for n in ('2026-09-20_10', '2026-09-30_10', '2026-10-13_09', 'junk'):
            (ad / (n + '.log')).write_text('x\n')
        actlog.prune(self.log, now=datetime(2026, 10, 13, 12))
        self.assertEqual(sorted(p.stem for p in ad.glob('*.log')), ['2026-09-30_10', '2026-10-13_09', 'junk'])

    def test_show(self):
        ad = self.d / 'actions'
        ad.mkdir()
        (ad / '2026-10-13_09.log').write_text('09:10:00 a x\n09:59:59 b y\n', encoding='utf-8')
        (ad / '2026-10-13_10.log').write_text('10:00:01 c x\n10:30:00 d z\n', encoding='utf-8')
        (ad / '2026-10-13_23.log').write_text('23:59:00 e\n', encoding='utf-8')
        (ad / '2026-10-14_00.log').write_text('00:01:00 f\n', encoding='utf-8')
        r = actlog.show('2026-10-13', '09:30-10:30', path=self.log)
        self.assertEqual([x.split()[1] for x in r], ['b', 'c', 'd'])
        r = actlog.show('2026-10-13', '09:00-10:59', 'x', path=self.log)
        self.assertEqual([x.split()[1] for x in r], ['a', 'c'])
        r = actlog.show('2026-10-13', '23:00-00:30', path=self.log)
        self.assertEqual([x.split()[1] for x in r], ['e', 'f'])


if __name__ == '__main__':
    unittest.main()
