#!/usr/bin/env python3
"""shopkit 選商品加速離線測試（2026-10-18 dev-shop-speed）：捲動列數計算、一次命中、讀名反推偏移、退回逐列流程、買後輪詢、關店輪詢。完全不碰遊戲。
用法：uv run --no-project python tools/gui/test_shopspeed.py"""
import os
import sys
from pathlib import Path

os.environ.setdefault('PSA_LAYOUT', '2880x1659')
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import testenv  # noqa: E402,F401  紀錄檔轉向暫存
import numglyph  # noqa: E402
import shopkit  # noqa: E402
import uikit  # noqa: E402

fails = 0


def check(name, cond, extra=''):
    global fails
    print(('PASS' if cond else 'FAIL'), name, extra)
    if not cond:
        fails += 1


# ---- 純函式 ----
check('max_off：33 項 = 17 列 → 12；8 項 → 0；10 項 → 0', shopkit.max_off(33) == 12 and shopkit.max_off(8) == 0 and shopkit.max_off(10) == 0)
check('plan_scroll：視野內 → 0 次（第 9 項 row 4、off 0 → pos 4）', shopkit.plan_scroll(9, 33, 0) == (0, 0, 4))
check('plan_scroll：row 5 → 1 拖、pos 3；row 6 → 1 拖、pos 4', shopkit.plan_scroll(10, 33, 0) == (1, 2, 3) and shopkit.plan_scroll(12, 33, 0) == (1, 2, 4))
check('plan_scroll：row 9（log 19 項新鮮的蝦）→ 3 拖、pos 3；row 12 → 4 拖、pos 4', shopkit.plan_scroll(18, 33, 0) == (3, 6, 3) and shopkit.plan_scroll(24, 33, 0) == (4, 8, 4))
check('plan_scroll：到底夾住 33 項 row 16 → 6 拖、off 夾在 12、pos 4（不是預測 3）', shopkit.plan_scroll(32, 33, 0) == (6, 12, 4))
check('plan_scroll：已知 off=6、要 row 11 → 1 拖（用已知偏移，不從頭數）', shopkit.plan_scroll(22, 33, 6) == (1, 8, 3))
check('plan_scroll：目標在視野上方 → n=0、pos 負', shopkit.plan_scroll(2, 33, 6)[0] == 0 and shopkit.plan_scroll(2, 33, 6)[2] < 0)

ORDER = [f'商品{i:02d}' for i in range(33)]
check('read_idx：字串精確 / 逐倍率行 / 讀不出', shopkit.read_idx('商品07', ORDER) == 7
      and shopkit.read_idx([{'text': '商品12', 'zoom': 2}, {'text': '商品12', 'zoom': 3}], ORDER) == 12
      and shopkit.read_idx('', ORDER) is None and shopkit.read_idx(None, ORDER) is None)


# ---- select_item：假遊戲（清單 off = 真實視野第一列；每拖 drag_rows 列、夾 max_off；click 回該卡的商品）----
class FakeShop:
    def __init__(self, n=33, off=0, drag_rows=2, blank=False):
        self.n, self.off, self.drag_rows, self.blank = n, off, drag_rows, blank
        self.cur = None
        self.clicks, self.drags, self.tops = [], 0, 0

    def gui(self, *a, **k):
        if a and a[0] == 'seq':
            c = a[1].split(';')[0].split()
            if c[0] == 'drag':
                if int(c[2]) == shopkit.DRAG_DOWN[1]:      # 往回拖 = 回頂
                    self.off, self.tops = 0, self.tops + 1
                else:
                    self.off = min(shopkit.max_off(self.n), self.off + self.drag_rows)
                    self.drags += 1
            elif c[0] == 'click':
                x, y = int(c[1]), int(c[2])
                pos = round((y - shopkit.ROW_Y0) / shopkit.ROW_PITCH)
                self.cur = (self.off + pos) * 2 + (0 if x < 540 else 1)
                self.clicks.append(self.cur)
        return ''

    def reader(self):
        if self.blank or self.cur is None or not 0 <= self.cur < self.n:
            return ''
        return ORDER[self.cur]


def run(want, **kw):
    fs = FakeShop(**kw)
    st = kw.pop('state', None) or {'drags': 0}
    orig = uikit.gui
    uikit.gui = fs.gui
    uikit.snap = lambda *a, **k: 'snap'
    try:
        ok = shopkit.select_item(want, ORDER, st, reader=fs.reader)
    finally:
        uikit.gui = orig
    return ok, fs, st


ok, fs, st = run('商品18')
check('一次命中：第 19 項（row 9）→ 3 拖 + 1 點、st.off = 6', ok and fs.drags == 3 and fs.clicks == [18] and st['off'] == 6 and st['drags'] == 3, f'{fs.drags} {fs.clicks} {st}')
ok, fs, st = run('商品32')
check('一次命中：最後一項（到底夾住）→ 6 拖 + 1 點', ok and fs.clicks == [32] and fs.drags == 6, f'{fs.drags} {fs.clicks}')
ok, fs, st = run('商品02')
check('一次命中：第 3 項 → 0 拖 1 點', ok and fs.drags == 0 and fs.clicks == [2])
# 慣性少捲 1 列（實際 off 比預測小 1）：點到別的商品 → 讀名反推 → 第 2 次點準
fs2 = FakeShop()
orig_gui = fs2.gui


def short_drag(*a, **k):
    r = orig_gui(*a, **k)
    if a and a[0] == 'seq' and a[1].startswith('drag') and int(a[1].split()[2]) != shopkit.DRAG_DOWN[1] and fs2.drags == 3:
        fs2.off -= 1                                       # 第 3 拖少捲 1 列
    return r


uikit.gui = short_drag
try:
    st = {'drags': 0}
    ok = shopkit.select_item('商品18', ORDER, st, reader=fs2.reader)
finally:
    uikit.gui = orig_gui
check('偏差 1 列：2 次點擊內中（舊逐列流程要 2～4 次）、不再多拖', ok and len(fs2.clicks) == 2 and fs2.clicks[-1] == 18 and fs2.drags == 3, f'{fs2.clicks} {fs2.drags}')
# 多捲 1 列（慣性）→ 預測列之上一列
fs3 = FakeShop(drag_rows=2)
orig3 = fs3.gui


def long_drag(*a, **k):
    r = orig3(*a, **k)
    if a and a[0] == 'seq' and a[1].startswith('drag') and int(a[1].split()[2]) != shopkit.DRAG_DOWN[1] and fs3.drags == 2:
        fs3.off += 1
    return r


uikit.gui = long_drag
try:
    st = {'drags': 0}
    ok = shopkit.select_item('商品17', ORDER, st, reader=fs3.reader)
finally:
    uikit.gui = orig_gui
check('多捲 1 列：2 次點擊內中', ok and len(fs3.clicks) <= 2 and fs3.clicks[-1] == 17, f'{fs3.clicks}')
# 店內由小到大連買：第 2 項沿用已知偏移，不從頭算
fs4 = FakeShop()
uikit.gui = fs4.gui
st = {'drags': 0}
try:
    r1 = shopkit.select_item('商品12', ORDER, st, reader=fs4.reader)
    d1 = fs4.drags
    r2 = shopkit.select_item('商品13', ORDER, st, reader=fs4.reader)
    r3 = shopkit.select_item('商品22', ORDER, st, reader=fs4.reader)
finally:
    uikit.gui = orig_gui
check('連買：同視野不再拖；往後一項只補需要的拖數', r1 and r2 and r3 and d1 == 1 and fs4.drags == 4 and fs4.clicks == [12, 13, 22], f'{fs4.drags} {fs4.clicks}')
# 往回選（在視野上方）→ scroll_top 後再選
fs5 = FakeShop(off=8)
uikit.gui = fs5.gui
try:
    st = {'drags': 4, 'off': 8}
    ok = shopkit.select_item('商品03', ORDER, st, reader=fs5.reader)
finally:
    uikit.gui = orig_gui
check('目標在視野上方 → 回頂再選到、drags 歸零', ok and fs5.tops >= 1 and st['off'] == 0 and fs5.clicks[-1] == 3, f'{fs5.tops} {fs5.clicks} {st}')
# 讀不出標題 → 直接法放棄、退回逐列鄰近流程（舊行為）仍能選到：reader 前兩次空、之後正常
fs6 = FakeShop()
uikit.gui = fs6.gui
n_read = {'n': 0}


def flaky():
    n_read['n'] += 1
    return '' if n_read['n'] <= 1 else fs6.reader()


try:
    st = {'drags': 0}
    ok = shopkit.select_item('商品12', ORDER, st, reader=flaky)
finally:
    uikit.gui = orig_gui
check('第一次讀空 → 退回逐列流程仍選到', ok and fs6.clicks[-1] == 12 and len(fs6.clicks) >= 2, f'{fs6.clicks}')
fs7 = FakeShop(blank=True)
uikit.gui = fs7.gui
uikit.snap = lambda *a, **k: 'snap'
try:
    ok = shopkit.select_item('商品12', ORDER, {'drags': 0}, reader=fs7.reader)
finally:
    uikit.gui = orig_gui
check('全讀空 → False（不亂買）、有限次點擊', not ok and len(fs7.clicks) < 30, f'{len(fs7.clicks)}')
# 標題核對保留：點到的永遠是別的商品且讀得到 → 不會回 True
fs8 = FakeShop()
uikit.gui = fs8.gui
try:
    ok = shopkit.select_item('商品12', ORDER, {'drags': 0}, reader=lambda: ORDER[0])
finally:
    uikit.gui = orig_gui
check('標題一直是別的商品 → False（核對不放水）', not ok)

# ---- buy_checked 輪詢 / close_shop 輪詢 ----
sleeps = []
_keep = (uikit.sleep, shopkit.buy_once, numglyph.read_box, shopkit.shop_open, uikit.gui)
uikit.sleep = lambda s: sleeps.append(s)
shopkit.buy_once = lambda: None
R1, R0 = ('a',), ('b',)
seq = [{'n': 1, 'value': 1, 'rows': R1}, {'n': 1, 'value': 1, 'rows': R1}, {'n': 1, 'value': 1, 'rows': R1},   # 買前、買後前兩讀還沒變
       {'n': 1, 'value': 0, 'rows': R0}, {'n': 1, 'value': 0, 'rows': R0}]                                      # 變了 → 穩讀一次
numglyph.read_box = lambda kind, box=None: seq.pop(0) if len(seq) > 1 else seq[0]
check('buy_checked：框一變就繼續（讀 5 次、睡 3 次，不固定等）→ bought', shopkit.buy_checked(1) == 'bought' and len(seq) == 1 and len(sleeps) == 3, f'{sleeps}')
sleeps.clear()
seq[:] = [{'n': 1, 'value': 1, 'rows': R1}]
check('buy_checked：框一直沒變 → 輪詢到上限後 not_bought', shopkit.buy_checked(1) == 'not_bought' and len(sleeps) == shopkit.BUY_POLL_MAX, f'{len(sleeps)}')
state = {'open': 3}
shopkit.shop_open = lambda: (state.__setitem__('open', state['open'] - 1), state['open'] > 0)[1]
uikit.gui = lambda *a, **k: ''
sleeps.clear()
check('close_shop：✕ 一消失就回 True（只點一次）', shopkit.close_shop() is True)
uikit.sleep, shopkit.buy_once, numglyph.read_box, shopkit.shop_open, uikit.gui = _keep

print(f'\n{"全部通過" if not fails else f"失敗 {fails} 項"}')
sys.exit(1 if fails else 0)
