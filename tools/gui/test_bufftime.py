#!/usr/bin/env python3
"""bufftime.py 離線測試（0 次真 powershell、不碰遊戲）：時間解析 / 到期計算 / 假 gui 流程 / 浮窗沒關 / p2（PSA_CLIENT）。
用法：uv run --no-project python tools/gui/test_bufftime.py"""
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import testenv  # noqa: E402,F401
import bufftime as bt  # noqa: E402
import uikit  # noqa: E402

fails = 0


def check(name, cond, extra=''):
    global fails
    print(('PASS' if cond else 'FAIL'), name, extra)
    if not cond:
        fails += 1


P = bt.parse_remaining
check('標準 0天0時55分6秒', P('0天0時55分6秒') == 55 * 60 + 6)
check('5 小時多', P('0天5時12分30秒') == 5 * 3600 + 12 * 60 + 30)
check('全形數字 + 空白', P('０天 ０時 ５５分 ６秒') == 55 * 60 + 6)
check('簡體 时', P('0天0时55分6秒') == 55 * 60 + 6)
check('時被認成別字', P('0天0肘55分6秒') == 55 * 60 + 6)
check('O 當 0、l 當 1', P('O天O時l5分O秒') == 15 * 60)
check('結尾少秒字', P('0天0時55分6') == 55 * 60 + 6)
check('帶前後雜字', P('剩餘 1天2時3分4秒 x') == 86400 + 7200 + 180 + 4)
check('缺分 → None', P('0天0時556秒') is None)
check('分 >= 60 → None', P('0天0時75分6秒') is None)
check('空 / None → None', P('') is None and P(None) is None)
check('vote 取多數', bt.vote(['0天0時55分6秒', '0天0時55分6秒', '0天0時35分6秒', 'xx']) == 55 * 60 + 6)
check('vote 全無 → None', bt.vote(['a', 'b']) is None)
check('title exp', bt.title_kind('2倍智慧果') == 'exp' and bt.title_kind('龍王的守護') == 'dragon' and bt.title_kind('abc') is None)
check('到期計算', bt.expires_at(1000.0, 3306) == 4306.0)
check('fmt', bt.fmt(5 * 3600 + 750) == '0天5時12分30秒')
check('第 1 格中心 (98,172)', bt.slot_center(0) == (98, 172))

# ---- 假 gui ----
class Fake:
    def __init__(self, row, popups, stuck=False, esc_closes=True, title_override=None, time_text=None):
        self.row, self.popups, self.stuck, self.esc_closes = row, popups, stuck, esc_closes
        self.open_slot = None
        self.clicks, self.keys = [], []
        self.title_override, self.time_text = title_override, time_text

    def gui(self, *args, note=''):
        if args[0] == 'key':
            self.keys.append(args[1])
            if self.esc_closes:
                self.open_slot = None
            return ''
        if args[0] == 'seq':
            k = {98: 0, 144: 1, 190: 2}[int(args[1].split()[1])]
            self.clicks.append(k)
            if self.open_slot == k:
                if not self.stuck:
                    self.open_slot = None
            elif self.row[k]:
                self.open_slot = k
        return ''

    def ocr(self, box, *opts):
        if self.open_slot is None:
            return []
        title, t = self.popups[self.open_slot]
        if box == bt.TITLE_BOX:
            return [self.title_override or title]
        if box == bt.TIME_BOX:
            return [self.time_text or t]
        return [title, self.time_text or t]


def run(fake, kind='all', client=None):
    os.environ.pop('PSA_CLIENT', None)
    if client:
        os.environ['PSA_CLIENT'] = client
    saved = (uikit.gui, uikit.ocr, uikit.preflight, uikit.hud_visible, uikit.sleep, uikit.snap, bt.bag.buff_row)
    clock = [1000.0]
    uikit.gui, uikit.ocr = fake.gui, fake.ocr
    uikit.preflight = lambda src, fast=True: 0
    uikit.hud_visible = lambda: True
    uikit.sleep = lambda s: clock.__setitem__(0, clock[0] + s)
    uikit.clock = lambda: clock[0]
    uikit.snap = lambda tag: None
    bt.bag.buff_row = lambda: list(fake.row)
    try:
        return bt.read(kind)
    finally:
        uikit.gui, uikit.ocr, uikit.preflight, uikit.hud_visible, uikit.sleep, uikit.snap, bt.bag.buff_row = saved
        import time
        uikit.clock = time.time
        os.environ.pop('PSA_CLIENT', None)


POP = [('2倍智慧果', '0天0時55分6秒'), ('龍王的守護', '0天1時2分3秒'), ('', '')]
f = Fake(['exp', None, None], POP)
r = run(f)
check('單一 exp：rc 0、點開再點關 = 同一格兩次', r['rc'] == 0 and f.clicks == [0, 0] and not f.keys, str(f.clicks))
check('剩餘秒數 + 名稱 + 到期', r['buffs'][0]['remaining_s'] == 3306 and r['buffs'][0]['name'] == '2倍智慧果'
      and r['buffs'][0]['expires_ts'] - r['buffs'][0]['read_ts'] == 3306 and r['buffs'][0]['title_verified'])
check('浮窗已關', f.open_slot is None)

f = Fake(['exp', 'dragon', None], POP)
r = run(f)
check('兩個 buff 都讀（--kind all）', [b['kind'] for b in r['buffs']] == ['exp', 'dragon'] and f.clicks == [0, 0, 1, 1])
f = Fake(['exp', 'dragon', None], POP)
r = run(f, 'dragon')
check('--kind dragon 只點第 2 格', f.clicks == [1, 1] and len(r['buffs']) == 1 and r['buffs'][0]['remaining_s'] == 3723)

f = Fake([None, None, None], POP)
r = run(f)
check('沒有 buff → rc 0、空清單、不點', r['rc'] == 0 and r['buffs'] == [] and f.clicks == [])

f = Fake(['exp', None, None], POP, stuck=True, esc_closes=True)
r = run(f)
check('再點沒關 → ESC 補關，仍算成功', r['rc'] == 0 and f.keys == ['{ESC}'] and f.open_slot is None)
f = Fake(['exp', None, None], POP, stuck=True, esc_closes=False)
r = run(f)
check('浮窗關不掉 → 133 且記錄', r['rc'] == bt.EXIT_STUCK and r['errors'])
f = Fake(['exp', 'dragon', None], POP, stuck=True, esc_closes=False)
r = run(f)
check('133 立刻停手不點第 2 格', f.clicks == [0, 0])

f = Fake(['exp', None, None], POP, time_text='糊掉了')
r = run(f)
check('時間讀不出 → 132，浮窗仍關', r['rc'] == bt.EXIT_TIME and f.open_slot is None)
f = Fake(['exp', None, None], POP, title_override='龍王的守護')
r = run(f)
check('標題對不上 → 131，浮窗仍關', r['rc'] == bt.EXIT_TITLE and f.open_slot is None)
f = Fake(['exp', None, None], POP)
f.row = ['exp', None, None]
f.popups = [('', '')] * 3          # 浮窗沒內容 = 沒出現
r = run(f)
check('浮窗沒出現 → 130', r['rc'] == bt.EXIT_NOPOPUP)

f = Fake(['exp', None, None], POP)
r = run(f, client='PrimalSA2')
check('p2（PSA_CLIENT=PrimalSA2）同流程', r['rc'] == 0 and r['buffs'][0]['remaining_s'] == 3306)

# preflight 9 → 不點
f = Fake(['exp', None, None], POP)
uikit_pf = uikit.preflight
uikit.preflight = lambda src, fast=True: 9
try:
    r = bt.read('all')
finally:
    uikit.preflight = uikit_pf
check('preflight 9 → rc 9、沒點', r['rc'] == 9 and f.clicks == [])

print('失敗', fails)
sys.exit(1 if fails else 0)
