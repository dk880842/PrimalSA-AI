#!/usr/bin/env python3
"""petwatch.py 離線測試：不碰遊戲（gui / ocr / 外掛 / 寵物面板 / 遇敵都換成假的，不讀即時像素 / 截圖）。
用法：uv run --no-project python tools/gui/test_petwatch.py"""
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import testenv  # noqa: E402,F401  紀錄檔轉向暫存
import errlog  # noqa: E402
import petwatch  # noqa: E402

errlog.LOG = Path(tempfile.mkdtemp()) / 'errlog.jsonl'
petwatch.STATE = Path(tempfile.mkdtemp()) / 'petwatch.json'
petwatch.log = lambda *a, **k: None
petwatch.gui = lambda *a, **k: ''
fails = 0


def check(name, cond, extra=''):
    global fails
    print(('PASS' if cond else 'FAIL'), name, extra)
    if not cond:
        fails += 1


def raises(fn, *a):
    try:
        fn(*a)
    except ValueError:
        return True
    return False


# ---- 參數 ----
check('預設練功寵金布伊第 3 格、戰寵朵拉比斯', (petwatch.PET_NAME, petwatch.PET_SLOT, petwatch.BACK_NAME) == ('金布伊', 3, '朵拉比斯'))
check('name_key 前 2 字', petwatch.name_key('朵拉比斯') == '朵拉' and petwatch.name_key('迪基格斯') == '迪基')
check('configure 驗證：格號超界 / 同格 / 空名 / 同名',
      raises(petwatch.configure, '金布伊', 6, '朵拉比斯', 2) and raises(petwatch.configure, '金布伊', 2, '朵拉比斯', 2)
      and raises(petwatch.configure, ' ', 3, '朵拉比斯', 2) and raises(petwatch.configure, '金布伊', 3, '金布伊', 2))
check('configure 失敗不改現值', petwatch.BACK_NAME == '朵拉比斯' and petwatch.PET_SLOT == 3)
check('第 5 格可用（寵物欄 5 格）', not raises(petwatch.configure, '金布伊', 5, '朵拉比斯', 2) and petwatch.PET_SLOT == 5)
petwatch.configure()
check('configure() 無參數回預設', (petwatch.BACK_NAME, petwatch.PET_SLOT) == ('朵拉比斯', 3))
check('舊的盲點下拉 swap_back / lock_item_xy 已移除', not hasattr(petwatch, 'swap_back') and not hasattr(petwatch, 'lock_item_xy'))

# ---- 連續兩輪確認（讀值不穩不換）----
due, pend = petwatch.confirm_due({'DKBO': 77, 'DKBO2': 78, 'DKBO3': None, 'DKBO4': 70}, {}, 77)
check('第一輪 ≥ 門檻 → 只列待確認，不換', due == [] and pend == ['DKBO', 'DKBO2'])
due, pend = petwatch.confirm_due({'DKBO': 77, 'DKBO2': 78, 'DKBO3': 77}, {'DKBO': 77, 'DKBO2': 77, 'DKBO3': None}, 77)
check('連兩輪 ≥ 門檻（差 ≤ 2）→ 換；上一輪讀不到 → 還要再確認', due == ['DKBO', 'DKBO2'] and pend == ['DKBO3'])
due, pend = petwatch.confirm_due({'DKBO': 110}, {'DKBO': 77}, 77)
check('兩輪差太多（OCR 偶發錯值）→ 不換、再確認', due == [] and pend == ['DKBO'])
due, pend = petwatch.confirm_due({'DKBO': 17, 'DKBO2': 10}, {'DKBO': 33, 'DKBO2': 33}, 77)
check('低於門檻（含 33 讀成 10 / 17）→ 不動', due == [] and pend == [])

# ---- 讀等級：拿掉單組 OCR 退路（會把 33 讀成 10 / 17）----
import pet  # noqa: E402
import petmatch  # noqa: E402
petmatch.grab = lambda specs, extra=(): ([['1' * 110] * 34], [])
pet.load_ctx = lambda learn, img_only=None: {'tpl': {'name': {}, 'avatar': {}, 'digit': {}}, 'learn': False, 'dirty': False}
pet.save_ctx = lambda ctx: None
calls = []
pet.level_from_rows = lambda rows, ctx: (calls.append(1), (None, 'ocr-conflict:10'))[1]
petwatch.ocr = lambda *a, **k: ['0轉10']                 # 舊版單組 OCR 會採用這個錯值
petwatch._LV_CTX.clear()
check('ocr_level：樣板 / 共識讀不準 → None（不再退回單組 OCR 的錯值）', petwatch.ocr_level() is None and calls == [1])
pet.level_from_rows = lambda rows, ctx: (33, 'tpl')
check('ocr_level：樣板讀得到 → 用它', petwatch.ocr_level() == 33)

# ---- each_batch：某人失敗就停的批次 → 跳過失敗的人繼續 ----
seen = []


def fn_fail(bad_map):
    def fn(rs):
        seen.append(list(rs))
        for r in rs:
            if r in bad_map:
                return bad_map[r], r
        return 0, None
    return fn


ok, bad, stop = petwatch.each_batch(['A', 'B', 'C', 'D'], fn_fail({'B': 74, 'D': 72}))
check('each_batch：B / D 失敗 → A、C 成功，從失敗者後面接著做', ok == ['A', 'C'] and bad == {'B': 74, 'D': 72} and stop == 0 and seen == [['A', 'B', 'C', 'D'], ['C', 'D']], str(seen))
ok, bad, stop = petwatch.each_batch(['A', 'B'], lambda rs: (2, None))
check('each_batch：整批沒做（面板打不開）→ 全部失敗、不重試', ok == [] and bad == {'A': 2, 'B': 2} and stop == 0)
ok, bad, stop = petwatch.each_batch(['A', 'B', 'C'], fn_fail({'B': 9}))
check('each_batch：驗證視窗 rc 9 → 立刻停、回停手 rc', ok == ['A'] and stop == 9 and 'C' in bad)


# ---- swap_back_many：假外掛 / 寵物面板（2026-10-13 實況：下拉順序每人不同，DKBO2/3/5 金布伊排在第 2 項）----
class FakeT:
    """每人：lock = (勾, 鎖誰)、fight = 出戰寵；dropdown 依名字選（新版讀字選，不靠第幾項）。
    fail = {角色: (階段, rc)} 模擬失敗；calls 記下批次呼叫"""

    def __init__(self, fail=None):
        self.st = {r: {'lock': (True, '金布伊'), 'fight': '金布伊'} for r in petwatch.CHARS}
        self.fail = fail or {}
        self.calls = []

    def _f(self, stage, rs):
        for r in rs:
            if self.fail.get(r, (None,))[0] == stage:
                return self.fail[r][1], r
        return 0, None

    def lock_set_many(self, items):
        rs = [i[0] for i in items]
        on = items[0][2] if items else None
        self.calls.append(('lock', on, rs))
        rc, who = self._f('unlock' if not on else 'relock', rs)
        for r, w, o, ident in items:
            if who == r:
                break
            self.st[r]['lock'] = (o, ident[1] if o else self.st[r]['lock'][1])
        return rc, who

    def pet_set_state_many(self, roles, name, state):
        self.calls.append(('state', name, list(roles)))
        rc, who = self._f('fight', roles)
        for r in roles:
            if r == who:
                break
            if self.st[r]['lock'][0]:                         # 鎖定戰寵還勾著 → 74（模擬遊戲擋下）
                return 74, r
            self.st[r]['fight'] = name
        return rc, who

    def pets_list(self, roles):
        self.calls.append(('list', list(roles)))
        return 0, {r: [{'slot': 1, 'empty': False, 'name': None, 'unnamed': '49/9/8/2', 'species': '布拉奇多斯', 'state': '騎乘'},
                       {'slot': 2, 'empty': False, 'name': '朵拉比斯', 'state': self.st[r]['fight'] == '朵拉比斯' and '出戰' or '等待'},
                       {'slot': 3, 'empty': False, 'name': '金布伊', 'state': self.st[r]['fight'] == '金布伊' and '出戰' or '等待'}]
                   for r in roles}


T = FakeT()
res, stop = petwatch.swap_back_many(['DKBO2', 'DKBO3', 'DKBO5'], T)
check('換回 3 人全部成功（下拉依名字選，不是第 2 項）', stop == 0 and all(res[r][0] for r in ('DKBO2', 'DKBO3', 'DKBO5'))
      and all(T.st[r] == {'lock': (True, '朵拉比斯'), 'fight': '朵拉比斯'} for r in ('DKBO2', 'DKBO3', 'DKBO5')), str(T.st))
check('批次：取消鎖定 / 出戰 / 讀寵物欄 / 重勾 各只呼叫一次（面板各開一次）',
      [c[0] for c in T.calls] == ['lock', 'state', 'list', 'lock'] and T.calls[0][1] is False and T.calls[3][1] is True, str(T.calls))

T = FakeT({'DKBO3': ('unlock', 4), 'DKBO5': ('fight', 74)})
res, stop = petwatch.swap_back_many(['DKBO2', 'DKBO3', 'DKBO4', 'DKBO5'], T)
check('DKBO3 取消鎖定失敗、DKBO5 出戰 74 → 其他人照做完', res['DKBO2'][0] and res['DKBO4'][0] and not res['DKBO3'][0] and not res['DKBO5'][0], str(res))
check('失敗原因明確：取消鎖定 rc / 74 提示先 pet_catch --unlock 戰寵',
      '取消鎖定戰寵失敗' in res['DKBO3'][1] and '74' in res['DKBO5'][1] and 'pet_catch.py --unlock 戰寵' in res['DKBO5'][1], str(res))
check('出戰失敗的人鎖定戰寵勾回練功寵（恢復原狀）', T.st['DKBO5'] == {'lock': (True, '金布伊'), 'fight': '金布伊'}, str(T.st['DKBO5']))
T = FakeT({'DKBO2': ('fight', 9)})
res, stop = petwatch.swap_back_many(['DKBO2', 'DKBO4'], T)
check('出戰時遇到驗證視窗（rc 9）→ 停手、不重勾', stop == 9 and not any(c[0] == 'list' for c in T.calls), str(T.calls))
check('why_state 72 / 78 訊息', '找不到唯一一隻朵拉比斯' in petwatch.why_state(72) and '戰鬥中' in petwatch.why_state(78))


# ---- run_swaps：遇敵只關 / 開一次、失敗計次、達上限放棄（不無限迴圈）----
class Enc:
    def __init__(self):
        self.on, self.log = True, []

    def encounter_on(self):
        return self.on

    def set_encounter(self, v):
        self.on = v
        self.log.append(v)


enc = Enc()
petwatch.heal.encounter_on = enc.encounter_on
petwatch.heal.set_encounter = enc.set_encounter
petwatch.battle_free = lambda timeout_ms=20000: True
T = FakeT({'DKBO3': ('relock', 7)})
done, gave, tries, st = set(), set(), {}, {'done': [], 'levels': {}}
due = ['DKBO', 'DKBO2', 'DKBO3', 'DKBO4', 'DKBO5']
rc = petwatch.run_swaps(due, done, gave, tries, st, {c: 77 for c in due}, 2, T=T)
check('第 1 輪：4 人換回、DKBO3 重勾失敗計 1 次', rc == 0 and done == {'DKBO', 'DKBO2', 'DKBO4', 'DKBO5'} and tries == {'DKBO3': 1} and not gave, f'{done} {tries}')
check('遇敵：整批前關一次、做完開一次', enc.log == [False, True], str(enc.log))
check('errlog 有原因（重勾鎖定失敗）', any('DKBO3' in e['error'] and '重勾鎖定戰寵' in e['error'] for e in errlog._read(errlog.LOG)))
rc = petwatch.run_swaps(['DKBO3'], done, gave, tries, st, {'DKBO3': 78}, 2, T=T)
check('第 2 輪 DKBO3 又失敗 → 放棄（gave），之後不再換', rc == 0 and gave == {'DKBO3'} and tries['DKBO3'] == 2 and st['gave_up'] == ['DKBO3'])
check('state 記 done / gave_up', st['done'] == ['DKBO', 'DKBO2', 'DKBO4', 'DKBO5'])
enc.log.clear()
T = FakeT({'DKBO2': ('unlock', 9)})
rc = petwatch.run_swaps(['DKBO2'], set(), set(), {}, {'done': []}, {}, 2, T=T)
check('驗證視窗 rc 9 → 回 9、遇敵不開回', rc == 9 and enc.log == [False], str(enc.log))
enc.on, enc.log = True, []
petwatch.battle_free = lambda timeout_ms=20000: False
tries = {}
rc = petwatch.run_swaps(['DKBO2'], set(), set(), tries, {'done': []}, {}, 2, T=FakeT())
check('等不到戰鬥結束 → 不換、不計失敗、遇敵開回', rc == 0 and tries == {} and enc.log == [False, True], str(enc.log))

# ---- 主迴圈：舊 bug 重現（每輪關開遇敵無限迴圈）→ 新版放棄後結束 ----
petwatch.battle_free = lambda timeout_ms=20000: True
petwatch.layout.current = lambda: '2880x1659'
petwatch.take_lock = lambda: True
petwatch.LOCK = Path(tempfile.mkdtemp()) / 'petwatch.lock'
petwatch.netwatch.guard = lambda name: {'status': 'ok'}


class VG:
    def __init__(self, *a, **k):
        pass

    def check(self):
        return 'ok'


petwatch.watchstate.VerifyGuard = VG
petwatch.winenv.enable_server = lambda: None
petwatch.time.sleep = lambda s: None
scans = []


def fake_scan(skip):
    scans.append(sorted(skip))
    return {c: 78 for c in petwatch.CHARS if c not in skip}


petwatch.scan = fake_scan
FT = FakeT({'DKBO2': ('relock', 7), 'DKBO3': ('relock', 7), 'DKBO5': ('relock', 7)})
petwatch.tools = lambda: FT
enc.on, enc.log = True, []
rc = petwatch.main(['--interval', '1', '--max-tries', '2', '--for', '600'])
check('主迴圈：DKBO / DKBO4 換回、DKBO2/3/5 失敗 2 次後放棄 → 退出碼 4（不無限迴圈）', rc == petwatch.EXIT_GAVE_UP and len(scans) <= 5, f'rc {rc} scans {scans}')
check('主迴圈：遇敵開關次數有限（每批一次）', enc.log.count(False) <= 2, str(enc.log))

scans.clear()
FT = FakeT()
petwatch.tools = lambda: FT
petwatch.STATE.unlink(missing_ok=True)
enc.on, enc.log = False, []
rc = petwatch.main(['--once', '--apply'])
check('--once --apply：第一次到門檻馬上再讀一次確認 → 5 人換回、遇敵本來關就不開', rc == 0 and len(scans) == 2 and all(FT.st[c]['fight'] == '朵拉比斯' for c in petwatch.CHARS) and enc.log == [], f'{scans} {enc.log}')
scans.clear()
FT = FakeT()
petwatch.tools = lambda: FT
petwatch.STATE.unlink(missing_ok=True)
rc = petwatch.main(['--once'])
check('--once（沒 --apply）只讀不換', rc == 0 and len(scans) == 1 and not FT.calls)

# 補血預設關（2026-10-13：練功不自動補血）
check('預設不補血', petwatch.main([], dry_args=True).no_heal is True)
check('--heal 才補血', petwatch.main(['--heal'], dry_args=True).no_heal is False)
check('--no-heal 相容（= 預設）', petwatch.main(['--no-heal'], dry_args=True).no_heal is True and petwatch.main(['--heal', '--no-heal'], dry_args=True).no_heal is True)
check('--once 不補血（只讀）', petwatch.main(['--heal', '--once'], dry_args=True).no_heal is True)
check('--max-tries 預設 2、--back-slot 仍收（相容）', petwatch.main(['--back-slot', '1'], dry_args=True).max_tries == 2)
print(f'\n{"全部通過" if not fails else f"失敗 {fails} 項"}')
sys.exit(1 if fails else 0)
