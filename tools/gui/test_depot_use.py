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
# 2026-10-12 千年龜的殼存入彈窗：第一組（-Light 170）讀成「三三」→ 給 want 時改用其餘參數讀、吻合才採用；不給 want 維持第一組
_oj, _uo = bag._ocr_join, uikit.ocr
bag._ocr_join = lambda box, opts: '三三' if box == bag.POPUP_NAME_ALT else ''
uikit.ocr = lambda box, *o: (['千年龜的殼', '消耗'] if tuple(box) == bag.POPUP_NAME_ALT and '-Dark' in o else [])
check('popup_name(want)：第一組雜訊 → 第二組吻合', bag.name_match(bag.popup_name('千年龜的殼'), '千年龜的殼') and bag.popup_name() == '三三')
check('popup_name(want)：第二組也不吻合 → 回第一組（核對失敗）', not bag.name_match(bag.popup_name('精靈王之弓'), '精靈王之弓'))
check('name_match：OCR 首/百混淆 薩姆百爾的百飾 吻合 薩姆吉爾的首飾', bag.name_match('薩姆吉爾百飾 薩姆百爾的百飾 姆百爾百飾 5 魅力', '薩姆吉爾的首飾'))
check('popup_buttons：OCR 讀成 穿 穿 仍判 equip', bag.popup_buttons('穿 穿').get('丟棄') == (826, 662))
bag._ocr_join, uikit.ocr = _oj, _uo

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
bag.popup_name = lambda *a: '龍王的守護' if opened[-1] == 3 else '木頭'
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
bag.popup_name = lambda *a: '龍王的守護'
check('find_item 有樣板 → 只開命中格', bag.find_item('龍王的守護') == 8 and opened == [8])
bag.popup_name = lambda *a: '木頭'
opened.clear()
check('圖示命中但彈窗名稱不符 → None', bag.find_item('龍王的守護') is None and opened == [8])
bag.load_icons = _real_icons
check('fixtures/item_icons.json 有龍王的守護 bag / depot 樣板', set(bag.load_icons().get('龍王的守護', {})) == {'bag', 'depot'})

# bag.Session 結束一定關自己開的背包（2026-10-13 08:04 depot_use rc 90：巡路抵達看門者 → NPC 對話框把背包藏起來，舊版看不到外框就不關）
_keep_s = (uikit.is_open, uikit.close_panel, uikit.screen, uikit.gui, uikit.preflight, uikit.open_panel_ex, bag.popup_open, bag.close_popup, bag.goto_page)
_st = {'dialog': True, 'bag': False, 'popup': False}
_ops = []


def _is_open(p):
    return _st['bag'] and not _st['dialog'] if p is bag.BAG or p is bag.BAGANY else False


def _gui(*a, note=''):
    if 'ESC' in ' '.join(a):
        _ops.append('esc')
        _st['dialog'] = False
    return ''


uikit.is_open = _is_open
uikit.close_panel = lambda p, known_open=False: (_ops.append('close'), _st.update(bag=False), True)[2]
uikit.screen = lambda full=False: {'state': 'dialog' if _st['dialog'] else ('panel' if _st['bag'] else 'idle')}
uikit.gui = _gui
bag.popup_open = lambda: _st['popup']
bag.close_popup = lambda: (_ops.append('popup'), _st.update(popup=False), True)[2]
_st.update(dialog=True, bag=True)
check('close_leftover：NPC 對話框蓋住背包 → ESC（不回答）→ 背包露出 → 點 ✕', bag.close_leftover() == 'dialog+closed' and _ops == ['esc', 'close'] and not _st['bag'])
_ops.clear()
_st.update(dialog=True, bag=True)
check('close_leftover(dialog_esc=False)：這次沒開成背包 → 不碰對話框', bag.close_leftover(dialog_esc=False) == '' and _ops == [])
_ops.clear()
_st.update(dialog=False, bag=True, popup=True)
check('close_leftover：道具彈窗 → 先關彈窗再關背包', bag.close_leftover() == 'popup+closed' and _ops == ['popup', 'close'])
_ops.clear()
_st.update(dialog=False, bag=False, popup=False)
check('close_leftover：什麼都沒開 → 不動', bag.close_leftover() == '' and _ops == [])
# 真的 Session：開成功 → 中途被對話框蓋住 → with 結束時 ESC + 關；本來就開著（巢狀）→ 不關
uikit.preflight = lambda src, fast=True: 0
uikit.open_panel_ex = lambda p, timeout=4.0, hud_wait=0.0: (_st.update(bag=True), (True, 'ok'))[1]
bag.goto_page = lambda page: 0
_ops.clear()
_st.update(dialog=False, bag=False)
with bag.Session() as _ss:
    _st['dialog'] = True                                      # 巡路抵達 NPC：對話框跳出、背包被藏
check('Session：自己開的背包被對話框蓋住 → 結束時 ESC + 點 ✕（任何失敗出口都一樣）', _ss.opened and _ops == ['esc', 'close'] and not _st['bag'])
_ops.clear()
_st.update(dialog=False, bag=True)
with bag.Session() as _ss:
    pass
check('Session：進來時背包已開（外層 Session）→ 不關', not _ss.opened and _ops == [] and _st['bag'])
(uikit.is_open, uikit.close_panel, uikit.screen, uikit.gui, uikit.preflight, uikit.open_panel_ex, bag.popup_open, bag.close_popup, bag.goto_page) = _keep_s

# depot_use.run：吃失敗仍存回；成功全流程
import heal  # noqa: E402
heal.set_encounter = lambda on: None
heal.gui = lambda *a, **k: ''
class FakeSession:
    rc = 0
    def __enter__(self): return self
    def __exit__(self, *e): return False


bag.Session = FakeSession
calls = []
tidied = []                                                   # depot_use.tidy → bag.close_leftover（不讀真畫面）
_real_close_leftover, _real_usleep = bag.close_leftover, depot_use.uikit.sleep
bag.close_leftover = lambda dialog_esc=True: (tidied.append(dialog_esc), 'closed')[1]
depot_use.uikit.sleep = lambda s: None
bag.depot_take = lambda *a: (calls.append('take'), 0)[1]
bag.buff_row = lambda: [None, None, None]
_real_wait = bag._wait
bag._wait = lambda pred, secs=2.0: pred()
bag.depot_store = lambda *a: (calls.append('store'), 0)[1]
bag.use_item = lambda r, w, verify_buff=False: (calls.append('use'), bag.EXIT_PANEL)[1]
rc, info = depot_use.run('DKBO', '龍王的守護', reopen=False)
check('吃失敗 → 仍存回、回吃的 rc', rc == bag.EXIT_PANEL and calls == ['take', 'use', 'store'])
check('吃失敗 → 收尾 tidy（close_leftover dialog_esc=True）', tidied == [True] and info.get('tidy') == 'closed')
# 2026-10-14 08:21 / 08:49：Session 開背包判失敗（step=open, rc 90）但面板晚一步出現 → tidy 一定再關一次
class FailSession(FakeSession):
    rc = bag.EXIT_PANEL
bag.Session = FailSession
tidied.clear()
calls.clear()
rc, info = depot_use.run('DKBO', '龍王的守護', reopen=False)
check('step=open 失敗 90 → 不取不吃、tidy 關殘留', rc == bag.EXIT_PANEL and info['step'] == 'open' and not calls and tidied == [True])
bag.Session = FakeSession
tidied.clear()
calls.clear()
_seq = [[None, None, None], ['dragon', None, None]]
bag.buff_row = lambda: _seq.pop(0) if len(_seq) > 1 else _seq[0]          # 吃之前沒圖示、吃完關背包後看到
bag.use_item = lambda r, w, verify_buff=False: (calls.append('use'), 0)[1]
rc, info = depot_use.run('DKBO', '龍王的守護', reopen=False)
check('全流程成功 rc 0 buff', rc == 0 and info.get('buff') and calls == ['take', 'use', 'store'])
check('成功 → 不 tidy', not tidied and 'tidy' not in info)
import json as _json, time as _time  # noqa: E402
import bufftime  # noqa: E402
_cp = bufftime.cache_path()
_d = _json.loads(_cp.read_text(encoding='utf-8'))
_dg = _d['buffs']['dragon']
check('吃成功 → bufftime.json 寫 dragon 到期（src=eat、約 10 分鐘）',
      info.get('bufftime') == 'eat' and _dg['src'] == 'eat' and 595 <= _dg['expires_ts'] - _time.time() <= 600 and _dg['remaining_s'] == 600)
calls.clear()
_cp.unlink(missing_ok=True)
bag.buff_row = lambda: [None, None, None]
bag.use_item = lambda r, w, verify_buff=False: (calls.append('use'), 0)[1]
rc, info = depot_use.run('DKBO', '龍王的守護', reopen=False)
check('沒驗到圖示 → 不寫 bufftime.json', not _cp.exists())
check('沒看到人形圖示 → 95 但仍存回', rc == bag.EXIT_VERIFY and calls[-1] == 'store')
bag.goto_page = lambda page: 0
bag.find_item = lambda *a, **k: None
bag.depot_take = lambda *a: bag.EXIT_ITEM
bag.buff_row = lambda: ['dragon', None, None]
calls.clear()
rc, info = depot_use.run('DKBO', '龍王的守護', reopen=False)
check('人形圖示已在 → 整個跳過（不取不吃不存）', rc == 0 and info['step'] == 'skip' and not calls)
check('跳過不吃 → 不改 bufftime.json', not _cp.exists())
# 寫快取失敗不影響 depot_use
_rec = bufftime.record_eaten
bufftime.record_eaten = lambda *a, **k: (_ for _ in ()).throw(OSError('disk'))
_seq = [[None, None, None], ['dragon', None, None]]
bag.buff_row = lambda: _seq.pop(0) if len(_seq) > 1 else _seq[0]
bag.find_item = lambda *a, **k: 4
bag.depot_take = lambda *a: 0
rc, info = depot_use.run('DKBO', '龍王的守護', reopen=False)
check('record_eaten 丟例外 → depot_use 仍 rc 0、只記警告', rc == 0 and 'warn_bufftime' in info)
bufftime.record_eaten = _rec
bag.find_item = lambda *a, **k: None
bag.depot_take = lambda *a: bag.EXIT_ITEM
bag.buff_row = lambda: ['dragon', None, None]
bag.buff_row = lambda: [None, None, None]
calls.clear()
rc, info = depot_use.run('DKBO', '龍王的守護', reopen=False)
check('倉庫沒有 → 92 不吃不存', rc == bag.EXIT_ITEM and 'use' not in calls)

# 倉庫空但背包有（上次取出後失敗沒存回）→ 用背包那份吃、剩的存回
bag.find_item = lambda *a, **k: 4
bag.use_item = lambda r, w, verify_buff=False: (calls.append('use'), 0)[1]
_seq = [[None, None, None], ['dragon', None, None]]
bag.buff_row = lambda: _seq.pop(0) if len(_seq) > 1 else _seq[0]
calls.clear()
rc, info = depot_use.run('DKBO', '龍王的守護', reopen=False)
check('倉庫空但背包有 → 用背包那份', rc == 0 and calls == ['use', 'store'] and '背包' in info.get('note', ''))
# 取出後驗證失敗（背包找不到）→ 一定嘗試存回，仍回取出的 rc
bag.find_item = lambda *a, **k: None
bag.buff_row = lambda: [None, None, None]
bag.depot_take = lambda *a: (calls.append('take'), bag.EXIT_VERIFY)[1]
calls.clear()
rc, info = depot_use.run('DKBO', '龍王的守護', reopen=False)
check('取出驗證失敗 → 仍嘗試存回、不吃', rc == bag.EXIT_VERIFY and calls == ['take', 'store'])
# questrun --dragon（2026-10-13 review §3.1）：restore=False → 剩的留在 DKBO 背包不存；have=True → 不取直接從背包吃
bag.depot_take = lambda *a: (calls.append('take'), 0)[1]
bag.use_item = lambda r, w, verify_buff=False: (calls.append('use'), 0)[1]
_seq = [[None, None, None], ['dragon', None, None]]
bag.buff_row = lambda: _seq.pop(0) if len(_seq) > 1 else _seq[0]
calls.clear()
rc, info = depot_use.run('DKBO', '龍王的守護', 'public', restore=False, have=False, reopen=False)
check('restore=False：取出 → 吃 → 不存回（留背包）', rc == 0 and calls == ['take', 'use'] and info['step'] == 'done')
_seq = [[None, None, None], ['dragon', None, None]]
calls.clear()
rc, info = depot_use.run('DKBO', '龍王的守護', 'public', restore=False, have=True, reopen=False)
check('have=True + restore=False：不開倉庫，直接從背包吃', rc == 0 and calls == ['use'])
bag.buff_row = lambda: None
check('buff_state：讀不到 → None；has_buff → False', bag.buff_state('dragon') is None and bag.has_buff('dragon') is False)
bag.buff_row = lambda: ['dragon', None, None]
check('buff_state：有人形 → True、沒有 EXP → False', bag.buff_state('dragon') is True and bag.buff_state('exp') is False)
# bag.team_scan（review §5.3）：開背包一次，逐人同時讀空格（像素）+ HP
_k = (bag.select_role, bag.slot_occupancy, bag.read_hp)
_sel = []
bag.select_role = lambda r, ctx=None: (_sel.append(r), 0)[1]
bag.slot_occupancy = lambda: [True] * 12 + [False] * 3
bag.read_hp = lambda: (300, 600)
rc, d = bag.team_scan(['DKBO', 'DKBO3'])
check('team_scan：每人選一次、空格 3、HP 50%', rc == 0 and _sel == ['DKBO', 'DKBO3'] and d['DKBO3'] == {'free': 3, 'hp_raw': (300, 600), 'hp': 50})
bag.slot_occupancy = lambda: None
rc, d = bag.team_scan(['DKBO'], hp=False)
check('team_scan：空格像素讀不到 → None（不當滿）、hp=False 不讀 HP', rc == 0 and d['DKBO'] == {'free': None})
rc, d = bag.hps(['DKBO'])
check('hps 沿用 team_scan → (目前, 最大)', rc == 0 and d == {'DKBO': (300, 600)})
bag.select_role = lambda r, ctx=None: 91
check('team_scan：選不到角色 → 91', bag.team_scan(['DKBO'])[0] == 91)
bag.select_role, bag.slot_occupancy, bag.read_hp = _k

# 2倍智慧果（2026-10-12 bug：按了使用、彈窗關了卻沒扣道具，舊版沒驗就回 0）：成敗看 buff 列 EXP 圖示
uikit.snap = lambda tag: None
bag.depot_take = lambda *a: (calls.append('take'), 0)[1]
bag.use_item = lambda r, w, verify_buff=False: (calls.append('use'), 0)[1]
check('buff_kind 2倍智慧果 = exp、龍王 = dragon、其他 None', bag.buff_kind('2倍智慧果') == 'exp' and bag.buff_kind('龍王的守護') == 'dragon' and bag.buff_kind('木頭') is None)
_seq = [[None, None, None], ['exp', None, None]]                                # 吃前沒有 EXP、吃完關背包後出現
bag.buff_row = lambda: _seq.pop(0) if len(_seq) > 1 else _seq[0]
calls.clear()
rc, info = depot_use.run('DKBO', '2倍智慧果', reopen=False)
check('智慧果 吃前無 exp → 吃後有 exp → rc 0', rc == 0 and info.get('buff') and info['step'] == 'done' and calls == ['take', 'use', 'store'])
bag.buff_row = lambda: [None, None, None]                                         # 吃完仍沒有 EXP（就是 15:03 的情況）
calls.clear()
rc, info = depot_use.run('DKBO', '2倍智慧果', reopen=False)
check('智慧果 吃後沒 exp → 95、剩的已存回', rc == bag.EXIT_VERIFY and info['step'] == 'verify' and calls == ['take', 'use', 'store'])
bag.buff_row = lambda: ['dragon', None, None]                                     # 只有龍王圖示不能算智慧果吃到
calls.clear()
rc, info = depot_use.run('DKBO', '2倍智慧果', reopen=False)
check('智慧果 只有 dragon 圖示 → 95', rc == bag.EXIT_VERIFY and calls == ['take', 'use', 'store'])
bag.buff_row = lambda: ['dragon', 'exp', None]                                    # 吃前 EXP 已在 → 跳過（不取不吃）
calls.clear()
rc, info = depot_use.run('DKBO', '2倍智慧果', reopen=False)
check('智慧果 EXP 已在 → 跳過', rc == 0 and info['step'] == 'skip' and not calls)
bag.buff_row = lambda: None                                                       # 讀不到 buff 列 → 算沒看到
calls.clear()
rc, info = depot_use.run('DKBO', '2倍智慧果', reopen=False)
check('智慧果 buff 列讀不到 → 95', rc == bag.EXIT_VERIFY and calls == ['take', 'use', 'store'])

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
bag.popup_name = lambda *a: '木頭'
bag.close_popup = lambda: (closed.append(1), True)[1]
check('放寬命中但名稱不符 → None 且 ESC 關彈窗', bag.find_item('龍王的守護') is None and opened == [5] and closed == [1])
bag.popup_name = lambda *a: '龍王的守護'
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
bag.popup_name = lambda *a: '龍王的守護'
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
bag.popup_name = lambda *a: '千年龜的殼'
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
# bag.weapons：Session 開一次、逐人選角、讀武器格名稱（唯讀）
opened.clear()
sel, snaps = [], []
bag.select_role = lambda r, ctx=None: (sel.append(r), 0)[1]
bag.equipped_name = lambda: '精靈王之弓 (4~6) 攻擊'
uikit.snap = lambda tag: (snaps.append(tag), None)[1]
rc, d = bag.weapons(['DKBO', 'DKBO2', 'DKBO3'])
check('bag.weapons：Session 1 次、3 人逐一讀名稱 rc 0', rc == 0 and len(opened) == 1 and sel == ['DKBO', 'DKBO2', 'DKBO3'] and all('精靈王之弓' in v for v in d.values()))
print('失敗', fails)
sys.exit(1 if fails else 0)
