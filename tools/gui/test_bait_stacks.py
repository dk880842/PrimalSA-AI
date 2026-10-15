#!/usr/bin/env python3
"""同名多疊誘餌離線測試（不碰遊戲；2026-10-15 p1 petquest 恐龍博士 rc 95 / 164 / 175 的兩個 bug）。
用法：uv run --no-project python tools/gui/test_bait_stacks.py
驗：bag.pick_stack / parse_qty 純函式；bag.depot_store 依疊數選格（最大疊 / 剛好 N 個）、存之前疊數對不上不按存入；
rebirth_pets.bait_take 最簡流程（背包已剛好 keep 跳過、不是 keep 全存回重取、拆分只讀整疊 qty < / == / > keep 三種、不做名稱 / 按鈕 / 標題 OCR）。"""
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
old_dc = bag.DCLICK
try:
    bag.DCLICK = False                               # 先驗彈窗流程（雙擊在下一段）
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
    bag.DCLICK = old_dc
    for k, v in keep.items():
        setattr(bag, k, v)

# ---- rebirth_pets.bait_take（2026-10-16 最簡流程）----
keep = {k: getattr(bag, k) for k in ('Session', 'select_role', 'stacks_of', 'depot_take', 'depot_store', 'find_item', 'open_slot_popup', 'name_match',
                                     'popup_name', '_ocr_join', '_click', 'close_popup', 'read_slot_name')}
keep_ocr, keep_gui, keep_fail, keep_open = rp.ocr_lines, uikit.gui, uikit.fail, uikit.is_open
calls, state = [], {'stacks': [], 'qty': '50'}
try:
    bag.Session, bag.select_role = _S, lambda r: 0
    bag.stacks_of = lambda w: list(state['stacks'])
    bag.find_item = lambda n, **k: 0 if state['stacks'] else None           # 背包有沒有誘餌（只看格名）
    bag.depot_take = lambda *a, **k: calls.append(('take',)) or state.update(stacks=[(0, int(state['qty']))]) or 0
    bag.depot_store = lambda role, w, d='public', **k: calls.append(('store', k)) or 0
    bag.open_slot_popup = lambda i: True
    # 名稱 / 按鈕 / 標題 OCR 一律炸掉：新流程不准再呼叫
    def boom(*a, **k):
        raise AssertionError('不該再做名稱 / 按鈕列 OCR')
    bag.name_match, bag.popup_name, bag._ocr_join = boom, boom, boom
    bag._click, bag.close_popup, bag.read_slot_name = lambda *a, **k: calls.append(('click', a[0], a[1])) or True, lambda: True, lambda i, d=False: rp.BAIT
    ocr_boxes = []
    rp.ocr_lines = lambda box, *o: ocr_boxes.append(box) or ([(state['qty'], 0, 0)] if state['qty'] else [])
    uikit.gui = lambda *a, **k: calls.append(('gui', a[1] if len(a) > 1 else a)) or ''
    uikit.fail = lambda src, rc, msg: rc
    uikit.is_open = lambda *a, **k: True
    t = rp.Tools()

    def run(stacks, keepn=4, qty='50', keep_short=False):
        calls.clear(); ocr_boxes.clear()
        state['stacks'], state['qty'] = stacks, qty
        with contextlib.redirect_stdout(io.StringIO()):
            return t.bait_take('DKBO2', keepn, keep_short)

    rc = run([(3, 4)])
    check('背包已剛好 4 個 → 跳過（不取、不拆、不存、不開彈窗）', rc == 0 and not calls and t.split_noop, str(calls))
    rc = run([(2, 1), (3, 3)])
    check('總數剛好 4（兩疊）也跳過', rc == 0 and not calls)
    rc = run([(0, 4), (1, 46)], qty='50')
    check('背包是 4 + 46（不是 keep）→ 全存回 → 重取整疊 → 拆 4 → 存 46',
          rc == 0 and calls[0] == ('store', {'all_copies': True}) and calls[1] == ('take',) and calls[-1] == ('store', {'keep_ok': True, 'want_count': 46}), str(calls))
    rc = run([(0, 10), (1, 20)], qty='30')
    check('多疊 10 + 20 也一律全存回重取（不回 95）', rc == 0 and calls[0] == ('store', {'all_copies': True}) and calls[1] == ('take',))
    rc = run([])
    check('第一次（背包沒誘餌）：不讀疊數、取整疊 50 → 拆 4（只讀 1 次數量）→ 存 46',
          rc == 0 and calls[0] == ('take',) and calls[-1] == ('store', {'keep_ok': True, 'want_count': 46}) and ocr_boxes == [(670, 430, 170, 45)]
          and any('755 451' in str(c) for c in calls) and any('610 545' in str(c) for c in calls), str(calls) + str(ocr_boxes))
    rc = run([], qty='4')
    check('整疊 == keep → 取消 828,545、不存回、split_noop', rc == 0 and t.split_noop and calls[-1] == ('gui', 'click 828 545; wait 600') and not any(c[0] == 'store' for c in calls), str(calls))
    rc = run([], qty='2')
    check('整疊 2 < 4（非 keep_short）→ 取消、全存回、回 92、split_short=2', rc == bag.EXIT_ITEM and t.split_short == 2 and calls[-1] == ('store', {'all_copies': True})
          and any('828 545' in str(c) for c in calls), str(calls))
    rc = run([], keepn=5, qty='3', keep_short=True)
    check('keep_short：整疊 3 < 5 → 取消、不存回、回 92、split_short=3', rc == bag.EXIT_ITEM and t.split_short == 3 and not any(c[0] == 'store' for c in calls), str(calls))
    state['stacks'] = []
    bag.depot_take = lambda *a, **k: calls.append(('take',)) or bag.EXIT_ITEM
    calls.clear()
    with contextlib.redirect_stdout(io.StringIO()) as out:
        rc = t.bait_take('DKBO5', 5, keep_short=True)
    check('keep_short：公共已空 → 現有 0、回 92、印「不足 = 0」', rc == bag.EXIT_ITEM and t.split_short == 0 and '背包誘餌不足 = 0' in out.getvalue())
    bag.depot_take = lambda *a, **k: calls.append(('take',)) or state.update(stacks=[(0, int(state['qty'] or 0))]) or 0
    rc = run([], qty='')
    check('整疊數量讀不出 → 取消、回 95、不存回', rc == bag.EXIT_VERIFY and not any(c[0] == 'store' for c in calls), str(calls))
finally:
    for k, v in keep.items():
        setattr(bag, k, v)
    rp.ocr_lines, uikit.gui, uikit.fail, uikit.is_open = keep_ocr, keep_gui, keep_fail, keep_open

# ---- 雙擊存取（未實機）----
names = ('Session', 'select_role', 'find_item', 'stacks_of', 'stack_qty', 'open_depot', '_click', 'popup_open', 'popup_name', 'name_match', '_ocr_join',
         '_learn_verified', 'goto_page', '_wait', 'slot_xy', 'depot_xy', 'close_popup', '_fail', 'read_slot_name', 'slot_occupancy', 'protected')
keep = {k: getattr(bag, k) for k in names}
keep_dc, keep_sd = uikit.safe_dclick, bag.DCLICK
ev = []
st = {'popup': False, 'bag': {0: rp.BAIT, 1: rp.BAIT}, 'depot': {5: rp.BAIT}, 'dc_effect': True}
try:
    bag.DCLICK = True
    bag.Session, bag.select_role = _S, lambda r: 0
    bag.find_item = lambda w, depot=False, hint=None, **k: 5 if depot else 1
    bag.stacks_of = lambda w: [(0, 4), (1, 46)]
    live = {0: 4, 1: 46}
    bag.stack_qty = lambda i, w: live.get(i)
    bag.open_depot = lambda d: 0
    bag.goto_page = lambda p: ev.append(('page', p)) or 0
    bag._wait = lambda pred, secs=0: pred()
    bag.slot_xy, bag.depot_xy = (lambda i: (100 + i, 100)), (lambda i: (500 + i, 100))
    bag.protected = lambda w: False
    bag.name_match = lambda a, b, *r: a == b
    bag.popup_open = lambda: st['popup']
    bag.close_popup = lambda: st.update(popup=False) or True
    bag._fail = lambda rc, msg, tag='': rc
    bag._click = lambda *a, **k: ev.append(('popupclick', a[3])) or True
    bag.popup_name = lambda w=None: w
    bag._ocr_join = lambda box, o: '存入 取出'
    bag._learn_verified = lambda *a: None
    bag.read_slot_name = lambda i, depot=False: (st['depot'] if depot else st['bag']).get(i, '')
    bag.slot_occupancy = lambda: [i in st['bag'] for i in range(15)]

    def fake_dclick(x, y, panel, note='', **k):
        ev.append(('dclick', x, note))
        if st['dc_effect']:
            if x >= 500:
                st['depot'].pop(x - 500, None)
                st['bag'][2] = rp.BAIT
            else:
                st['bag'].pop(x - 100, None)
        return True
    uikit.safe_dclick = fake_dclick

    with contextlib.redirect_stdout(io.StringIO()):
        rc = bag.depot_store('DKBO2', rp.BAIT, 'public', want_count=46)
    check('雙擊存入：雙擊第 2 格（46 那疊）、驗該格變空、不開彈窗不按存入', rc == 0 and [e[1] for e in ev if e[0] == 'dclick'] == [101] and not any(e[0] == 'popupclick' for e in ev), str(ev))
    ev.clear()
    st['bag'] = {0: rp.BAIT, 1: rp.BAIT}
    st['dc_effect'] = False
    with contextlib.redirect_stdout(io.StringIO()):
        rc = bag.depot_store('DKBO2', rp.BAIT, 'public', want_count=46)
    check('雙擊存入無效（格沒變空）→ 退回彈窗 + 存入鈕', any(e[0] == 'dclick' for e in ev) and any(e[0] == 'popupclick' for e in ev), str(ev))
    ev.clear()
    st['bag'] = {0: rp.BAIT, 1: '別的道具'}
    with contextlib.redirect_stdout(io.StringIO()):
        bag.depot_store('DKBO2', rp.BAIT, 'public')
    check('雙擊前該格名稱對不上 → 不雙擊、走彈窗', not any(e[0] == 'dclick' for e in ev))
    # 取出
    ev.clear()
    st.update(bag={0: '別的'}, depot={5: rp.BAIT}, dc_effect=True)

    def finder(w, depot=False, hint=None, **k):
        return 5 if depot else (2 if 2 in st['bag'] else None)
    bag.find_item = finder
    with contextlib.redirect_stdout(io.StringIO()):
        rc = bag.depot_take('DKBO2', rp.BAIT, 'public')
    check('雙擊取出：雙擊倉庫第 6 格、倉庫格清空、背包讀到、不按取出鈕', rc == 0 and any(e[0] == 'dclick' and e[1] == 505 for e in ev) and not any(e[0] == 'popupclick' for e in ev), str(ev))
    ev.clear()
    st.update(bag={0: '別的'}, depot={5: rp.BAIT}, dc_effect=False)
    with contextlib.redirect_stdout(io.StringIO()):
        bag.depot_take('DKBO2', rp.BAIT, 'public')
    check('雙擊取出無效 → 退回彈窗取出鈕', any(e[0] == 'dclick' for e in ev) and any(e[0] == 'popupclick' for e in ev), str(ev))
    ev.clear()
    st.update(depot={5: rp.BAIT}, dc_effect=True, popup=False)
    bag.DCLICK = False
    with contextlib.redirect_stdout(io.StringIO()):
        bag.depot_take('DKBO2', rp.BAIT, 'public')
    check('PSA_DEPOT_DCLICK=0 → 不雙擊', not any(e[0] == 'dclick' for e in ev))
finally:
    for k, v in keep.items():
        setattr(bag, k, v)
    uikit.safe_dclick, bag.DCLICK = keep_dc, keep_sd

print('全部通過' if not fails else f'{fails} 項失敗')
sys.exit(1 if fails else 0)
