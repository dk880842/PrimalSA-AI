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


def check(name, cond, extra=''):
    global fails
    print(('PASS' if cond else 'FAIL'), name, extra if not cond else '')
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

# ---- 追蹤列表剛切角色還沒載入（2026-10-13：DKBO2～5 第一次 121、重跑才過）----
A = pt.track_miss_action
check('track_miss_action：列表 0 列（沒載入）→ wait；等太久 → fail', A(0, 0, 5) == 'wait' and A(0, None, 5) == 'wait' and A(0, 0, pt.TRACK_LOAD_MAX_S) == 'fail')
check('track_miss_action：有內容沒找到 → 未滿 retry、滿 fail', A(1, 3, 5) == 'retry' and A(pt.TRACK_MISS_MAX - 1, 3, 5) == 'retry' and A(pt.TRACK_MISS_MAX, 3, 5) == 'fail')

import types  # noqa: E402


class Clock:
    def __init__(self):
        self.t = 1000.0

    def time(self):
        return self.t

    def sleep(self, s):
        self.t += s

    def strftime(self, *a):
        return '00:00:00'


def turnin_with(track_seq, rows_seq):
    """假 quest：每次 track_task 依序回 track_seq、_PAGE_ROWS_N 依序 rows_seq；找到後選擇視窗開 → pick_in_window 假成功"""
    clk = Clock()
    q = types.SimpleNamespace(_PAGE_ROWS_N=None, calls=0)
    state = {'found': False}

    def track_task(title, click=True):
        k = q.calls
        q.calls += 1
        q._PAGE_ROWS_N = rows_seq[min(k, len(rows_seq) - 1)]
        clk.t += 6                                        # 掃一次列表約 6 秒
        r = track_seq[min(k, len(track_seq) - 1)]
        state['found'] = r is True
        return r
    q.track_task = track_task
    q.read_screen = lambda: {'state': 'idle'}
    saved = (sys.modules.get('quest'), pt.time, pt.uikit.sleep, pt.uikit.snap, pt.select_window_open, pt.pick_in_window, pt.log)
    sys.modules['quest'] = q
    pt.time, pt.uikit.sleep, pt.uikit.snap = clk, clk.sleep, lambda *a, **k: None
    pt.select_window_open = lambda: state['found']
    pt.pick_in_window = lambda want, dry_run=False: 0
    pt.log = lambda *a, **k: None
    try:
        return pt.turnin_step('魯尼帖斯'), q.calls, clk.t - 1000.0
    finally:
        q0, pt.time, pt.uikit.sleep, pt.uikit.snap, pt.select_window_open, pt.pick_in_window, pt.log = saved
        if q0 is not None:
            sys.modules['quest'] = q0
        else:
            sys.modules.pop('quest', None)


rc, n, el = turnin_with([False, False, True], [0, 0, 4])
check('列表前兩次 0 列（沒載入）→ 不判 121，第 3 次找到 → 交出', rc == 0 and n == 3, f'rc {rc} n {n} {el:.0f}s')
rc, n, el = turnin_with([False], [3])
check('列表有內容但一直沒有恐龍博士 → 連 3 次才 121', rc == pt.EXIT_TRACK and n == pt.TRACK_MISS_MAX, f'rc {rc} n {n}')
rc, n, el = turnin_with([False], [0])
check('列表一直 0 列 → 等到 TRACK_LOAD_MAX_S 才 121（不無限等）', rc == pt.EXIT_TRACK and el >= pt.TRACK_LOAD_MAX_S and el < 90, f'rc {rc} n {n} {el:.0f}s')
rc, n, el = turnin_with([True], [4])
check('第一次就找到 → 不多掃', rc == 0 and n == 1)

# ---- 2026-10-14 恐龍博士：DKBO 交魯尼帖斯按確定、視窗消失就判 step1 True，伺服器其實沒收走 → 交後驗證 ----
J = pt.judge_taken
check('judge_taken：步號前進 ok、停在原步 same、讀不到 unknown', J(1, 2) == 'ok' and J(1, 1) == 'same' and J(1, None) == 'unknown' and J(2, 2) == 'same')
check('judge_taken：最後一步交完任務消失 = ok；非最後一步消失 = unknown（讀不準）', J(2, 'GONE') == 'ok' and J(1, 'GONE') == 'unknown')


def verify_with(step_seq, there=None):
    """假 quest.read_step_no 依序回 step_seq；假 pet_still_there 回 there（呼叫次數記在 calls）"""
    clk = Clock()
    q = types.SimpleNamespace(k=0)

    def rsn(task, cur_map_fn=None, reveal=True):
        v = step_seq[min(q.k, len(step_seq) - 1)]
        q.k += 1
        clk.t += 1
        return v
    q.read_step_no = rsn
    calls = []
    saved = (sys.modules.get('quest'), pt.time, pt.uikit.sleep, pt.uikit.snap, pt.pet_still_there, pt.log)
    sys.modules['quest'] = q
    pt.time, pt.uikit.sleep, pt.uikit.snap = clk, clk.sleep, lambda *a, **k: None
    pt.pet_still_there = lambda role, want: calls.append((role, want)) or there
    pt.log = lambda *a, **k: None
    try:
        return pt.verify_taken('DKBO', '魯尼帖斯', 1), q.k, calls
    finally:
        q0, pt.time, pt.uikit.sleep, pt.uikit.snap, pt.pet_still_there, pt.log = saved
        if q0 is not None:
            sys.modules['quest'] = q0
        else:
            sys.modules.pop('quest', None)


rc, n, calls = verify_with([2])
check('verify_taken：第一次就讀到步 2 → 0、不開寵物面板', rc == 0 and n == 1 and calls == [])
rc, n, calls = verify_with([1, 1, 2])
check('verify_taken：伺服器 / 列表慢一點（1、1、2）→ 等到前進 → 0', rc == 0 and n == 3)
rc, n, calls = verify_with([1])
check('verify_taken：步號一直是 1（實機情況）→ 126、不開寵物面板', rc == pt.EXIT_NOT_TAKEN and calls == [] and n >= 2)
rc, n, calls = verify_with([None], there=False)
check('verify_taken：步號讀不到 → 讀寵物欄，魯尼帖斯已不在 → 0', rc == 0 and calls == [('DKBO', '魯尼帖斯')])
rc, n, calls = verify_with([None], there=True)
check('verify_taken：步號讀不到、寵物還在 → 126', rc == pt.EXIT_NOT_TAKEN)
rc, n, calls = verify_with([None], there=None)
check('verify_taken：步號、寵物欄都驗不到 → 126（不猜）', rc == pt.EXIT_NOT_TAKEN)

saved = (pt.uikit.preflight, pt.turnin_step, pt.verify_taken)
pt.uikit.preflight = lambda src: 0
pt.turnin_step = lambda want, dry_run=False: 0
pt.verify_taken = lambda role, want, step: pt.EXIT_NOT_TAKEN if step == 1 else 0
rc, res = pt.run(['DKBO'], (1, 2), switch=False)
check('run：確定後驗不到交出 → step1 False、rc 126、不接著交步 2', rc == pt.EXIT_NOT_TAKEN and res == {pt.charname.canon('DKBO'): {'step1': False}}, str(res))
pt.verify_taken = lambda role, want, step: 0
rc, res = pt.run(['DKBO'], (1, 2), switch=False)
check('run：兩步都驗到 → 0', rc == 0 and res == {pt.charname.canon('DKBO'): {'step1': True, 'step2': True}}, str(res))
pt.uikit.preflight, pt.turnin_step, pt.verify_taken = saved

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
