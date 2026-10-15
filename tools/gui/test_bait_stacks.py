#!/usr/bin/env python3
"""同名多疊誘餌離線測試（不碰遊戲；2026-10-15 p1 petquest 恐龍博士 rc 95 / 164 / 175 的兩個 bug）。
用法：uv run --no-project python tools/gui/test_bait_stacks.py
驗：bag.pick_stack / parse_qty 純函式；bag.depot_store 依疊數選格（最大疊 / 剛好 N 個）、存之前疊數對不上不按存入；
rebirth_pets.bait_take 重跑冪等（背包已剛好 keep → 不取不拆）、多疊存回「不是要留的那疊」、拆分後存 原疊 − keep 那疊、不夠 → 全存回回 92。"""
import contextlib
import io
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import testenv  # noqa: E402,F401
import bag  # noqa: E402
import rebirth_pets as rp  # noqa: E402
import uikit  # noqa: E402

fails = 0


def check(name, cond, extra=''):
    global fails
    print(('PASS' if cond else 'FAIL'), name, extra)
    if not cond:
        fails += 1


class _S:
    rc = 0

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


# ---- 純函式 ----
S = [(0, 4), (3, 46), (5, None)]
check('pick largest = 46 那疊', bag.pick_stack(S, 'largest') == 3)
check('pick smallest 略過讀不出的', bag.pick_stack(S, 'smallest') == 0)
check('want_count 46 → 格 3；找不到 → None', bag.pick_stack(S, None, 46) == 3 and bag.pick_stack(S, None, 7) is None)
check('沒指定 = 第一格；空 = None', bag.pick_stack(S) == 0 and bag.pick_stack([]) is None)
check('parse_qty', bag.parse_qty(['x 46 y']) == 46 and bag.parse_qty('abc') is None)

# ---- bag.depot_store：依疊數選格、對不上不按存入 ----
names = ('Session', 'select_role', 'find_item', 'stacks_of', 'stack_qty', 'open_depot', '_click', 'popup_open', 'popup_name', 'name_match',
         '_ocr_join', '_learn_verified', 'goto_page', '_wait', 'slot_xy', 'close_popup', '_fail')
keep = {k: getattr(bag, k) for k in names}
clicks = []
try:
    bag.Session, bag.select_role = _S, lambda r: 0
    bag.find_item = lambda w, **k: 0
    bag.open_depot = lambda d: 0
    bag._click = lambda x, y, panel, note, **k: clicks.append(note) or True
    bag.popup_open, bag.popup_name, bag.name_match = lambda: True, lambda w=None: w, lambda a, b, *r: a == b
    bag._ocr_join = lambda box, o: '存入'
    bag._learn_verified = lambda *a: None
    bag.goto_page = lambda p: 0
    bag._wait = lambda pred, secs=0: True
    bag.slot_xy = lambda i: (100 + i, 100)
    bag.close_popup = lambda: True
    bag._fail = lambda rc, msg, tag='': rc
    bag.stacks_of = lambda w: [(0, 4), (1, 46)]
    live = {0: 4, 1: 46}
    bag.stack_qty = lambda i, w: live.get(i)
    with contextlib.redirect_stdout(io.StringIO()):
        rc = bag.depot_store('DKBO2', rp.BAIT, 'public', pick='largest')
    check('depot_store pick=largest：點第 2 格（46 那疊）存入', rc == 0 and any('第 2 格' in c for c in clicks) and any('存入' in c for c in clicks), str(clicks))
    clicks.clear()
    with contextlib.redirect_stdout(io.StringIO()):
        rc = bag.depot_store('DKBO2', rp.BAIT, 'public', want_count=46)
    check('depot_store want_count=46：同上，且不存 4 那疊', rc == 0 and not any('第 1 格' in c for c in clicks), str(clicks))
    clicks.clear()
    live[1] = 45                                     # 存之前再讀疊數對不上
    with contextlib.redirect_stdout(io.StringIO()):
        rc = bag.depot_store('DKBO2', rp.BAIT, 'public', want_count=46)
    check('疊數對不上 → 回 95、沒按存入', rc == bag.EXIT_VERIFY and not any('存入' in c for c in clicks), str(clicks))
    with contextlib.redirect_stdout(io.StringIO()):
        rc = bag.depot_store('DKBO2', rp.BAIT, 'public', want_count=7)
    check('沒有符合疊數的格 → 92', rc == bag.EXIT_ITEM)
    bag.stacks_of = lambda w: [(0, None), (1, 46)]
    live[1] = 46
    with contextlib.redirect_stdout(io.StringIO()):
        rc = bag.depot_store('DKBO2', rp.BAIT, 'public', want_count=46)
    check('有疊數讀不出的格 → 95 不存', rc == bag.EXIT_VERIFY)
finally:
    for k, v in keep.items():
        setattr(bag, k, v)

# ---- rebirth_pets.bait_take ----
keep = {k: getattr(bag, k) for k in ('Session', 'select_role', 'stacks_of', 'depot_take', 'depot_store', 'find_item', 'open_slot_popup', 'name_match',
                                     'popup_name', '_ocr_join', '_click', 'close_popup', 'read_slot_name')}
keep_ocr, keep_gui, keep_fail, keep_open = rp.ocr_lines, uikit.gui, uikit.fail, uikit.is_open
calls, state = [], {'stacks': [], 'qty': '50'}
try:
    bag.Session, bag.select_role = _S, lambda r: 0
    bag.stacks_of = lambda w: list(state['stacks'])
    bag.depot_take = lambda *a, **k: calls.append(('take',)) or state.update(stacks=[(0, 50)]) or 0
    bag.depot_store = lambda role, w, d='public', **k: calls.append(('store', k)) or 0
    bag.find_item, bag.open_slot_popup = lambda n: 0, lambda i: True
    bag.name_match, bag.popup_name, bag._ocr_join = lambda a, b: True, lambda n=None: n, lambda box, o: '使用 拆分'
    bag._click, bag.close_popup, bag.read_slot_name = lambda *a, **k: True, lambda: True, lambda i, d=False: rp.BAIT
    rp.ocr_lines = lambda box, *o: [('數量輸入', 0, 0)] if box[1] == 170 else [(state['qty'], 0, 0)]
    uikit.gui = lambda *a, **k: calls.append(('gui', a[1] if len(a) > 1 else a)) or ''
    uikit.fail = lambda src, rc, msg: rc
    uikit.is_open = lambda *a, **k: True
    t = rp.Tools()

    def run(stacks, keepn=4):
        calls.clear()
        state['stacks'] = stacks
        with contextlib.redirect_stdout(io.StringIO()):
            return t.bait_take('DKBO2', keepn)

    rc = run([(3, 4)])
    check('重跑冪等：背包已剛好 4 個一疊 → 不取、不拆、不存（rc 0）', rc == 0 and not calls and t.split_noop, str(calls))
    rc = run([(2, 1), (3, 3)])
    check('總數剛好 4（兩疊）也不動', rc == 0 and not calls)
    rc = run([(0, 4), (1, 46)])
    check('多疊 4 + 46：存回 46 那疊（want_count=46），不拆', rc == 0 and calls == [('store', {'want_count': 46, 'keep_ok': True})], str(calls))
    rc = run([(0, 50)])
    check('單疊 50 → 拆 4 → 存 want_count=46 那疊', rc == 0 and calls[-1] == ('store', {'keep_ok': True, 'want_count': 46}) and any('755 451' in str(c) for c in calls), str(calls))
    rc = run([])
    check('背包沒有 → 先取公共整疊再拆存', rc == 0 and calls[0] == ('take',) and calls[-1][0] == 'store', str(calls))
    rc = run([(0, 2)])
    check('只有 2 < 4 → 全存回、回 92、split_short=2', rc == bag.EXIT_ITEM and t.split_short == 2 and calls == [('store', {'all_copies': True})], str(calls))
    rc = run([(0, None)])
    check('疊數讀不出 → 95、不動', rc == bag.EXIT_VERIFY and not calls)
    rc = run([(0, 10), (1, 20)])
    check('多疊但沒有剛好 keep → 95 停手、不動', rc == bag.EXIT_VERIFY and not calls)
finally:
    for k, v in keep.items():
        setattr(bag, k, v)
    rp.ocr_lines, uikit.gui, uikit.fail, uikit.is_open = keep_ocr, keep_gui, keep_fail, keep_open

print('全部通過' if not fails else f'{fails} 項失敗')
sys.exit(1 if fails else 0)
