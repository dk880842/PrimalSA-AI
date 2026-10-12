#!/usr/bin/env python3
"""depot_use.py / char.read_analyse 重試的離線測試（不碰遊戲）。用法：uv run --no-project python tools/gui/test_depot_use.py"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import testenv  # noqa: E402,F401  紀錄檔轉向暫存（不污染真 actions.log / quest-events.log / errlog）
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
uikit.px = lambda pts: [(55, 106, 163), (183, 115, 54)]
check('is_pair_layout 並排', depot_use.is_pair_layout())
uikit.px = lambda pts: [(42, 39, 42), (55, 106, 163)]
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

# ---- bag 彈窗 / 找格 / 流程（龍王的守護短彈窗）----
import bag  # noqa: E402

# 彈窗特徵：只有第三組（短彈窗）吻合也算開著；全不吻合 = 沒開
sigs = {'s1': bag.POPUP_SIG, 's2': bag.POPUP_SIG2, 's3': bag.POPUP_SIG3, 's4': bag.POPUP_SIG4}
for only, want in (('s4', True), ('s3', True), ('s2', True), ('s1', True), (None, False)):
    uikit.sig_match = lambda g, o=only: g is sigs.get(o)
    check(f'popup_open 只有 {only} 吻合 → {want}', bag._popup_sig_open() == want)

# popup_name：兩框都讀串起來（短彈窗預設框是雜訊也不能吃掉真標題）
bag._ocr_join = lambda box, opts: '聊天雜訊' if box == bag.POPUP_NAME_BOX else '龍王的守護'
check('popup_name 串兩框仍吻合', bag.name_match(bag.popup_name(), '龍王的守護'))

# 使用鈕座標：OCR 漏讀「更多」(single) 但像素是並排 → 619；單鈕 → 732
clicks = []
bag._click = lambda x, y, panel, note, allow=(), wait_ms=350: (clicks.append((x, y)), True)[1]
bag._ocr_join = lambda box, opts: '使用'
uikit.px = lambda pts: [(55, 106, 163), (183, 115, 54)]
bag.click_popup_button('使用')
uikit.px = lambda pts: [(42, 39, 42), (55, 106, 163)]
bag.click_popup_button('使用')
check('使用鈕 並排 619 / 單鈕 732', clicks == [(619, 648), (732, 648)])

_real_icons = bag.load_icons
bag.load_icons = lambda: {}                       # 先測無樣板的舊路徑
# find_item：格名稱 OCR 讀歪（「守 4-0」）→ 逐格開彈窗核對名稱找到
opened = []
bag.read_slot_name = lambda i, depot=False: '守 4-0' if i == 3 else ('' if i > 3 else '木頭')
bag.open_slot_popup = lambda i, depot=False: (opened.append(i), i in (0, 3))[1]
bag.popup_name = lambda: '龍王的守護' if opened[-1] == 3 else '木頭'
bag.close_popup = lambda: True
check('find_item OCR 讀歪 → 逐格彈窗核對', bag.find_item('龍王的守護') == 3 and opened[0] == 3)
_real_find_item = bag.find_item
_real_take, _real_store = bag.depot_take, bag.depot_store
check('find_item popup_fallback=False 讀歪 → None', bag.find_item('龍王的守護', popup_fallback=False) is None)

# 兩段式：有圖示樣板 → 只有圖示吻合的格才開彈窗核對名稱，不掃其他格、不靠格名 OCR
TPL = [[dx, dy, 200, 30, 30] for dx in (-4, 0, 4) for dy in (-4, 0, 4)]
bag.load_icons = lambda: {'龍王的守護': {'bag': TPL, 'depot': TPL}}
RED, BROWN = (205, 35, 25), (90, 60, 40)
uikit.px = lambda pts: [RED if (abs(x - bag.slot_xy(8)[0]) <= 4 and abs(y - bag.slot_xy(8)[1]) <= 4) else BROWN for x, y in pts]
check('icon_match_slots 只命中第 9 格', bag.icon_match_slots('龍王的守護') == [8])
check('沒樣板的道具 → None', bag.icon_match_slots('別的') is None)
opened.clear()
bag.read_slot_name = lambda *a: (_ for _ in ()).throw(AssertionError('不該讀格名'))
bag.open_slot_popup = lambda i, depot=False: (opened.append(i), True)[1]
bag.popup_name = lambda: '龍王的守護'
check('find_item 有樣板 → 只開命中格', bag.find_item('龍王的守護') == 8 and opened == [8])
bag.popup_name = lambda: '木頭'
opened.clear()
check('圖示命中但彈窗名稱不符 → None', bag.find_item('龍王的守護') is None and opened == [8])
bag.load_icons = _real_icons
check('fixtures/item_icons.json 有龍王的守護 bag / depot 樣板', set(bag.load_icons().get('龍王的守護', {})) == {'bag', 'depot'})

# depot_use.run：吃失敗仍存回；成功全流程
import heal  # noqa: E402
heal.set_encounter = lambda on: None
heal.gui = lambda *a, **k: ''
class FakeSession:
    rc = 0
    def __enter__(self): return self
    def __exit__(self, *e): return False


bag.Session = FakeSession
bag._buff_icon_seq = None
calls = []
bag.depot_take = lambda *a: (calls.append('take'), 0)[1]
bag._buff_icon = lambda: False
_real_wait = bag._wait
bag._wait = lambda pred, secs=2.0: pred()
bag.depot_store = lambda *a: (calls.append('store'), 0)[1]
bag.use_item = lambda r, w, verify_buff=False: (calls.append('use'), bag.EXIT_PANEL)[1]
rc, info = depot_use.run('DKBO', '龍王的守護', reopen=False)
check('吃失敗 → 仍存回、回吃的 rc', rc == bag.EXIT_PANEL and calls == ['take', 'use', 'store'])
calls.clear()
_seq = [False, True]
bag._buff_icon = lambda: _seq.pop(0) if len(_seq) > 1 else _seq[0]          # 吃之前沒圖示、吃完關背包後看到
bag.use_item = lambda r, w, verify_buff=False: (calls.append('use'), 0)[1]
rc, info = depot_use.run('DKBO', '龍王的守護', reopen=False)
check('全流程成功 rc 0 buff', rc == 0 and info.get('buff') and calls == ['take', 'use', 'store'])
calls.clear()
bag._buff_icon = lambda: False
bag.use_item = lambda r, w, verify_buff=False: (calls.append('use'), 0)[1]
rc, info = depot_use.run('DKBO', '龍王的守護', reopen=False)
check('沒看到人形圖示 → 95 但仍存回', rc == bag.EXIT_VERIFY and calls[-1] == 'store')
bag.goto_page = lambda page: 0
bag.find_item = lambda *a, **k: None
bag.depot_take = lambda *a: bag.EXIT_ITEM
bag._buff_icon = lambda: True
calls.clear()
rc, info = depot_use.run('DKBO', '龍王的守護', reopen=False)
check('人形圖示已在 → 整個跳過（不取不吃不存）', rc == 0 and info['step'] == 'skip' and not calls)
bag._buff_icon = lambda: False
calls.clear()
rc, info = depot_use.run('DKBO', '龍王的守護', reopen=False)
check('倉庫沒有 → 92 不吃不存', rc == bag.EXIT_ITEM and 'use' not in calls)

# 倉庫空但背包有（上次取出後失敗沒存回）→ 用背包那份吃、剩的存回
bag.find_item = lambda *a, **k: 4
bag.use_item = lambda r, w, verify_buff=False: (calls.append('use'), 0)[1]
_seq = [False, True]
bag._buff_icon = lambda: _seq.pop(0) if len(_seq) > 1 else _seq[0]
calls.clear()
rc, info = depot_use.run('DKBO', '龍王的守護', reopen=False)
check('倉庫空但背包有 → 用背包那份', rc == 0 and calls == ['use', 'store'] and '背包' in info.get('note', ''))
# 取出後驗證失敗（背包找不到）→ 一定嘗試存回，仍回取出的 rc
bag.find_item = lambda *a, **k: None
bag._buff_icon = lambda: False
bag.depot_take = lambda *a: (calls.append('take'), bag.EXIT_VERIFY)[1]
calls.clear()
rc, info = depot_use.run('DKBO', '龍王的守護', reopen=False)
check('取出驗證失敗 → 仍嘗試存回、不吃', rc == bag.EXIT_VERIFY and calls == ['take', 'store'])

# ---- bag 新增：settle 等待 / 圖示嚴格→放寬 / 取出存入輪詢 ----
sleeps = []
uikit.sleep = lambda s: sleeps.append(s)
bag._ocr_join = lambda box, opts: '使用'
uikit.px = lambda pts: [(42, 39, 42), (55, 106, 163)]
order = []
bag._click = lambda x, y, panel, note, allow=(), wait_ms=350: (order.append(('click', len(sleeps))), True)[1]
sleeps.clear()
bag.click_popup_button('使用')
check('click_popup_button 先等 POPUP_SETTLE_S 再點', bag.POPUP_SETTLE_S in sleeps and order == [('click', len(sleeps))] and sleeps[-1] == bag.POPUP_SETTLE_S)

# 圖示：嚴格全不中 → 放寬（命中率 0.6 的第 5 格），依命中率排序
TPL = [[dx, dy, 200, 30, 30] for dx in (-4, 0, 4) for dy in (-4, 0, 4)]          # 9 點
bag.load_icons = lambda: {'龍王的守護': {'bag': TPL, 'depot': TPL}}
def _partial(slot, nhit):
    cx, cy = bag.slot_xy(slot)
    want = {(cx + d[0], cy + d[1]) for d in TPL[:nhit]}
    return lambda pts: [(205, 35, 25) if (x, y) in want else (90, 60, 40) for x, y in pts]
uikit.px = _partial(5, 6)                                                           # 6/9 = 0.67：< 0.85 > 0.45
check('嚴格不中 → 放寬命中第 6 格', bag.icon_match_slots('龍王的守護') == [5])
uikit.px = _partial(5, 3)                                                           # 3/9 = 0.33 < 0.45
check('連放寬也不中 → 空 list', bag.icon_match_slots('龍王的守護') == [])
uikit.px = _partial(5, 8)                                                           # 8/9 = 0.89 嚴格就中
check('嚴格命中 → 只回嚴格', bag.icon_match_slots('龍王的守護') == [5])
# 放寬命中但彈窗名稱不符 → find_item None（不會按任何按鈕，close_popup 有呼叫）
uikit.px = _partial(5, 6)
bag.find_item = _real_find_item
closed, opened = [], []
bag.open_slot_popup = lambda i, depot=False: (opened.append(i), True)[1]
bag.popup_name = lambda: '木頭'
bag.close_popup = lambda: (closed.append(1), True)[1]
check('放寬命中但名稱不符 → None 且 ESC 關彈窗', bag.find_item('龍王的守護') is None and opened == [5] and closed == [1])
bag.popup_name = lambda: '龍王的守護'
check('放寬命中且名稱相符 → 回該格', bag.find_item('龍王的守護') == 5)

# depot_take / depot_store：點按鈕前等 settle；取出 / 存入後輪詢（慢更新成功、逾時失敗）
bag.depot_take, bag.depot_store = _real_take, _real_store
bag.select_role = lambda r: 0
bag.open_depot = lambda d: 0
bag.goto_page = lambda p: 0
bag.protected = lambda w: False
bag._fail = lambda rc, msg, tag='': rc
bag.popup_open = lambda: False
bag.open_slot_popup = lambda i, depot=False: True
bag.popup_name = lambda: '龍王的守護'
bag._ocr_join = lambda box, opts: '取出 存入'
bag._click = lambda x, y, panel, note, allow=(), wait_ms=350: (order.append(('click', len(sleeps))), True)[1]
bag._wait = _real_wait
clk = [0.0]
uikit.clock = lambda: clk[0]
uikit.sleep = lambda s: (sleeps.append(s), clk.__setitem__(0, clk[0] + s))
# 取出：第 1 次找不到、第 3 次才出現 → 成功
n = [0]
def _fi(want, depot=False, popup_fallback=True):
    if depot:
        return 0
    n[0] += 1
    return 2 if n[0] >= 3 else None
bag.find_item = _fi
order.clear(); sleeps.clear()
check('depot_take 背包慢更新 → 輪詢成功且先 settle', bag.depot_take('DKBO', '龍王的守護') == 0 and n[0] == 3 and sleeps[0] == bag.POPUP_SETTLE_S)
bag.find_item = lambda want, depot=False, popup_fallback=True: 0 if depot else None
clk[0] = 0.0
check('depot_take 逾時仍找不到 → EXIT_VERIFY', bag.depot_take('DKBO', '龍王的守護') == bag.EXIT_VERIFY and clk[0] >= 4.0)
# 存入：那一格（像素）第 1、2 次仍有、第 3 次變空 → 成功；一直有 → 逾時失敗（2026-10-12 改看格子變空，同名多格不誤報）
_real_occ = bag.slot_occupancy
n = [0]
def _occ():
    n[0] += 1
    return [i == 1 and n[0] < 3 for i in range(15)]
bag.slot_occupancy = _occ
bag.find_item = lambda want, depot=False, popup_fallback=True: 1
sleeps.clear()
_po = [True, False]                                    # 點背包格後彈窗開（True），按存入後關（False）
bag.popup_open = lambda: _po.pop(0) if len(_po) > 1 else _po[0]
check('depot_store 背包慢更新 → 輪詢成功且先 settle', bag.depot_store('DKBO', '龍王的守護') == 0 and n[0] == 3 and bag.POPUP_SETTLE_S in sleeps)
bag.slot_occupancy = lambda: [i == 1 for i in range(15)]
_po = [True, False]
bag.popup_open = lambda: _po.pop(0) if len(_po) > 1 else _po[0]
clk[0] = 0.0
check('depot_store 逾時仍有 → EXIT_VERIFY', bag.depot_store('DKBO', '龍王的守護') == bag.EXIT_VERIFY and clk[0] >= 4.0)
# --all-copies：同名 3 格（不疊加，千年龜的殼）→ 一格一格存到沒有；每次驗「那一格變空」
_bagx = [True, True, True] + [False] * 12
def _fi3(want, depot=False, popup_fallback=True):
    return next((i for i in range(3) if _bagx[i]), None)
bag.find_item = _fi3
bag.popup_name = lambda: '千年龜的殼'
bag.slot_occupancy = lambda: list(_bagx)
_open = [False]
bag.popup_open = lambda: _open[0]
def _clk3b(x, y, panel, note, allow=(), wait_ms=350):
    if (x, y) == (732, 648):
        _bagx[_fi3('')] = False
        _open[0] = False
    else:
        _open[0] = True
    return True
bag._click = _clk3b
clk[0] = 0.0
rc = bag.depot_store('DKBO', '千年龜的殼', all_copies=True)
check('depot_store --all-copies：3 格全存、LAST stored=3', rc == 0 and _bagx[:3] == [False] * 3 and bag.LAST.get('stored') == 3)
_bagx[:] = [True, True] + [False] * 13
rc = bag.depot_store('DKBO', '千年龜的殼')
check('depot_store 預設只存 1 格（同名另一格還在也不誤報 95）', rc == 0 and _bagx[:2] == [False, True] and bag.LAST.get('stored') == 1)
bag.slot_occupancy = _real_occ
# ---- depot_many：多人批次（2026-10-12）----
opened = []
class CountSession(FakeSession):
    def __enter__(self):
        opened.append(1)
        return self
bag.Session = CountSession
seen = []
bag.depot_store = lambda r, w, d='public', keep_ok=False, **k: (seen.append(r), bag.EXIT_ITEM if r == 'DKBO3' else 0)[1]
rc, d = bag.depot_many('store', ['DKBO', 'DKBO2', 'DKBO3', 'DKBO4'], '人龍隨機蛋', skip_missing=True)
check('depot_many store --skip-missing：外層 Session 1 次、4 人都做、沒有的略過 rc 0', rc == 0 and len(opened) == 1 and seen == ['DKBO', 'DKBO2', 'DKBO3', 'DKBO4'] and d['DKBO3'] == bag.EXIT_ITEM)
seen.clear()
rc, d = bag.depot_many('store', ['DKBO', 'DKBO3', 'DKBO4'], '人龍隨機蛋')
check('depot_many 沒 --skip-missing：沒有 → 92 停、後面不做', rc == bag.EXIT_ITEM and seen == ['DKBO', 'DKBO3'])
check('_roles：逗號多人 / 不認得 → None', bag._roles('DKBO2,DKBO3') == ['DKBO2', 'DKBO3'] and bag._roles('DKBO,XYZ') is None)
print('失敗', fails)
sys.exit(1 if fails else 0)
