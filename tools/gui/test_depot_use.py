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
bag.depot_take = lambda *a: bag.EXIT_ITEM
bag._buff_icon = lambda: True
calls.clear()
rc, info = depot_use.run('DKBO', '龍王的守護', reopen=False)
check('人形圖示已在 → 整個跳過（不取不吃不存）', rc == 0 and info['step'] == 'skip' and not calls)
bag._buff_icon = lambda: False
calls.clear()
rc, info = depot_use.run('DKBO', '龍王的守護', reopen=False)
check('倉庫沒有 → 92 不吃不存', rc == bag.EXIT_ITEM and 'use' not in calls)
print('失敗', fails)
sys.exit(1 if fails else 0)
