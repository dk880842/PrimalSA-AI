#!/usr/bin/env python3
"""depot_use.py / char.read_analyse 重試的離線測試（不碰遊戲）。用法：uv run --no-project python tools/gui/test_depot_use.py"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import char  # noqa: E402
import depot_use  # noqa: E402
import team  # noqa: E402
import uikit  # noqa: E402

fails = 0


def check(name, ok):
    global fails
    print(('PASS ' if ok else 'FAIL ') + name)
    fails += 0 if ok else 1


# 彈窗按鈕列版型：使用（藍）+ 更多（橘）並排 / 單鈕
uikit.px = lambda pts: [(243, 180, 40), (40, 90, 150)]
check('is_pair_layout 並排', depot_use.is_pair_layout())
uikit.px = lambda pts: [(207, 203, 150), (243, 203, 151)]
check('is_pair_layout 單鈕 / 沒彈窗 → False', not depot_use.is_pair_layout())
uikit.px = lambda pts: None
check('is_pair_layout 讀不到 → False', not depot_use.is_pair_layout())


# char.read_analyse：61 / 63 重讀，矛盾 64 不重讀，第 3 次仍不準就回最後結果
class C:
    def __init__(self, slot, status, name, check_):
        self.slot, self.status, self.name, self.check, self.ocr = slot, status, name, check_, ''


GOOD = {'ok': True, 'cards': [C(0, 'current', 'DKBO', 'ok')]}
NONAME = {'ok': True, 'cards': [C(0, 'current', None, 'unread')]}
CONF = {'ok': True, 'cards': [C(0, 'current', 'DKBO', 'conflict')]}
char.uikit.sleep = lambda s: None
for label, seq, want_rc, want_calls in (('61 → 重讀 → 成功', [NONAME, GOOD], 0, 2), ('連 3 次 61 → 回 61', [NONAME] * 5, 61, 3),
                                        ('矛盾 64 不重讀', [CONF, GOOD], 64, 1)):
    calls = []
    team.read_state = lambda ocr=True, keep_open=False, s=list(seq): (calls.append(1), s.pop(0))[1]
    r, a = char.read_analyse()
    check(f'read_analyse {label}', a['rc'] == want_rc and len(calls) == want_calls)
print('失敗', fails)
sys.exit(1 if fails else 0)
