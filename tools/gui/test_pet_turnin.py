#!/usr/bin/env python3
"""pet_turnin.py / petdrop.confirm_names_ok 純函式離線測試（不碰遊戲）。
用法：uv run --no-project python tools/gui/test_pet_turnin.py"""
import os
import sys
from pathlib import Path

os.environ.setdefault('PSA_LAYOUT', '2880x1659')
sys.path.insert(0, str(Path(__file__).resolve().parent))
import testenv  # noqa: E402,F401
import pet_turnin as pt  # noqa: E402
import petdrop  # noqa: E402

fails = 0


def check(name, cond):
    global fails
    print(('PASS' if cond else 'FAIL'), name)
    if not cond:
        fails += 1


# 實機 OCR（2026-10-12 選擇視窗，兩個放大倍數各一次 → 每張卡兩行重複）
LINES = [('朵拉比斯', 616, 341), ('0轉6級', 617, 373), ('魯尼帖斯', 620, 446), ('0轉級', 615, 478),
         ('朵拉比斯', 617, 340), ('0轉6級', 618, 372), ('魯尼帖斯', 620, 444), ('0轉級', 614, 476), ('鱼上', 622, 544)]
check('pick_card 重複行併成一張', pt.pick_card(LINES, '魯尼帖斯') == (620, 446))
check('pick_card 朵拉比斯', pt.pick_card(LINES, '朵拉比斯') == (616, 341))
check('pick_card 沒有貝魯卡 → None（鱼上 是被截半的貝魯卡，不猜）', pt.pick_card(LINES, '貝魯卡') is None)
check('pick_card 順序不同', pt.pick_card([('貝魯卡', 600, 340), ('魯尼帖斯', 600, 446)], '魯尼帖斯') == (600, 446))
check('pick_card 同名兩張 → None', pt.pick_card([('貝魯卡', 600, 340), ('貝魯卡', 600, 446)], '貝魯卡') is None)
check('snap_name OCR 錯字', pt.snap_name('魯尼帖') == '魯尼帖斯' and pt.snap_name('貝魯上') == '貝魯卡')
check('snap_name 等級行不是寵物', pt.snap_name('0轉54級') is None)
check('is_yellow 選中', pt.is_yellow((236, 220, 120)) and not pt.is_yellow((244, 232, 210)))

ok = petdrop.confirm_names_ok
check('丟棄提示窗 名字在括號裡', ok('確定要丟棄【布克布克】嗎? 回站保存48小時!', '布克布克'))
check('丟棄提示窗 別隻寵物', not ok('確定要丟棄【朵拉比斯】嗎?', '布克布克'))
check('丟棄提示窗 只讀到第二行', not ok('回收站保存48小時! 回收站保存48小時!', '布克布克'))
check('丟棄提示窗 騎寵', not ok('確定要丟棄【布拉奇多斯】嗎?', '布克布克'))
check('丟棄提示窗 空', not ok('', '布克布克'))

# questrun.special_step：全 manual 任務步號讀不到 → manual（2026-10-12 恐龍博士 117 的根因）
import questrun  # noqa: E402


class _T:
    def __init__(self, step):
        self.step = step

    def read_step(self, track):
        return self.step

    def gone(self):
        return 'GONE'


def _sp(step, d):
    r = questrun.Run.__new__(questrun.Run)
    r.T, r.pending = _T(step), None
    return r.special_step(d)


D_ALL = dict(track='恐龍博士', steps_total=2, steps={1: dict(kind='manual'), 2: dict(kind='manual')})
D_PART = dict(track='猜謎三兄弟', steps_total=3, steps={1: dict(kind='manual')})
check('special_step 全 manual、步號讀不到 → manual', _sp(None, D_ALL)[1] == 'manual')
check('special_step 全 manual、讀到步 2 → manual', _sp(2, D_ALL)[:2] == (2, 'manual'))
check('special_step 全 manual、任務已消失 → default（不誤停）', _sp('GONE', D_ALL)[1] == 'default')
check('special_step 只有部分 manual、讀不到 → default', _sp(None, D_PART)[1] == 'default')
print('失敗', fails)
sys.exit(1 if fails else 0)
