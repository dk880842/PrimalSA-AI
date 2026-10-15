#!/usr/bin/env python3
"""buywendy.py 離線測試（假 Tools / 假 ass 內部函式；0 次 powershell、不碰遊戲）。
用法：uv run --no-project python tools/gui/test_buywendy.py"""
import contextlib
import io
import os
import sys
from pathlib import Path

os.environ.setdefault('PSA_CLIENT', 'PrimalSA2')
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import testenv  # noqa: E402,F401  紀錄檔轉向暫存
import winenv  # noqa: E402
import uikit  # noqa: E402

PS_CALLS = []


def _no_ps(*a, **k):
    PS_CALLS.append(a)
    raise RuntimeError('離線測試不准呼叫 powershell')


winenv.run_ps = _no_ps
uikit.gui = lambda *a, **k: _no_ps(*a)
uikit.snap = lambda *a, **k: None
import errlog  # noqa: E402
errlog.add = lambda *a, **k: 0
import buywendy as bw  # noqa: E402

fails = 0


def check(name, cond, extra=''):
    global fails
    print(('PASS' if cond else 'FAIL'), name, extra if not cond else '')
    if not cond:
        fails += 1


def quiet(fn, *a, **k):
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
        rc = fn(*a, **k)
    return rc, buf.getvalue()


# ---------------- 純函式 ----------------
check('parse_coin 150,000', bw.parse_coin('150,000') == 150000)
check('parse_coin 空白 / 句點', bw.parse_coin(' 149 500 ') == 149500 and bw.parse_coin('149.500') == 149500)
check('parse_coin 多倍率重複', bw.parse_coin('150,000150,000150,000') == 150000)
check('parse_coin 讀不到', bw.parse_coin('') is None and bw.parse_coin('abc') is None and bw.parse_coin(None) is None)
check('title_ok 正確', bw.title_ok('溫蒂妮Lv5的金幣') and bw.title_ok('溫蒂妮 Lv5 的金幣'))
check('title_ok 容錯 Lv 字形', bw.title_ok('溫蒂妮LV5的金幣') and bw.title_ok('溫蒂妮Lu5的金幣'))
check('title_ok 兄弟品項不算', not bw.title_ok('芙雷美雅Lv5金幣') and not bw.title_ok('溫蒂妮Lv4豎琴') and not bw.title_ok('阿薩Lv5金幣'))
check('title_ok 空 / 雜訊', not bw.title_ok('') and not bw.title_ok('蒼玉的石手環') and not bw.title_ok(None))
check('coin_delta_ok', bw.coin_delta_ok(150000, 149500) is True and bw.coin_delta_ok(150000, 149000) is False
      and bw.coin_delta_ok(None, 1) is None and bw.coin_delta_ok(1, None) is None)
lines = [('攻擊', 944, 355), ('防禦', 944, 397), ('逃跑', 944, 439), ('滋潤的精靈Lv.3', 944, 481), ('風的精靈Lv.5', 944, 523)]
check('option_pos 唯一', bw.option_pos(lines, '風的精靈') == (944, 523))
check('option_pos 多倍率同列重複算一個', bw.option_pos(lines + [('風的精靈Lv.5', 946, 525)], '風的精靈') == (944, 523))
check('option_pos 沒有', bw.option_pos(lines[:4], '風的精靈') is None)
check('option_pos 兩列都吻合 = 歧義', bw.option_pos(lines + [('風的精靈Lv.4', 944, 565)], '風的精靈') is None)
codes = [bw.EXIT_ARGS, bw.EXIT_PRE, bw.EXIT_BAG, bw.EXIT_TOWN, bw.EXIT_ARENA, bw.EXIT_SHOP, bw.EXIT_WEAR, bw.EXIT_FIRST, bw.EXIT_BACK, bw.EXIT_GRIND]
check('退出碼 200～209 各一個', codes == list(range(200, 210)))
check('名單 = PrimalSA2 DKBO6～10、隊長 DKBO6', bw.ALL_ROLES[0] == 'DKBO6' and len(bw.ALL_ROLES) == 5 and bw.LEADER == 'DKBO6', str(bw.ALL_ROLES))


# ---------------- 假 Tools ----------------
class Fake:
    def __init__(self, bag=None, worn=False, coin=150000, buy_cost=500, title='溫蒂妮Lv5的金幣', price='500', pos=(11004, 7, 8),
                 stop_ok=True, rc=None, got=True, first_rc=0, team_rc=0, grind_rc=0, wear_rc=0, follow=True):
        self.s = dict(bag=bag, worn=worn, coin=coin)
        self.cost, self.title, self.price, self._pos = buy_cost, title, price, list(pos)
        self.stop_ok, self.rc, self.got = stop_ok, rc or {}, got
        self.first_rc, self.team_rc, self.grind_rc, self.wear_rc = first_rc, team_rc, grind_rc, wear_rc
        self.calls = []

    def _c(self, n, *a):
        self.calls.append(n)
        return self.rc.get(n, 0)

    def preflight(self): return self._c('preflight')
    def char_ensure(self, n): return self._c('char_ensure')
    def sleep(self, s): pass

    def inspect(self):
        rc = self._c('inspect')
        return (rc, dict(self.s)) if not rc else (rc, dict(self.s))

    def stop_follow(self):
        self.calls.append('stop_follow')
        return self.stop_ok

    def encounter_off(self): self.calls.append('encounter_off')
    def pos(self): return tuple(self._pos)

    def to_town(self):
        self.calls.append('to_town')
        self._pos = [1000, 92, 99]
        return True

    def disband(self): return self._c('disband')

    def walk_to(self, m, x, y):
        self.calls.append(f'walk_to {m}')
        return True

    def talk(self, npc, at, then=''):
        self.calls.append(f'talk {npc}')
        if npc == bw.GUIDE:
            self._pos = [130, 52, 19]
        return True

    def wait_map(self, m, tries=10):
        self.calls.append('wait_map')
        return self._pos[0] == m

    def shop_open(self): return True

    def shop_select_read(self):
        self.calls.append('shop_select_read')
        return self.title, '風的精靈Lv.5', self.price

    def shop_buy(self):
        self.calls.append('shop_buy')
        if self.got:
            self.s['bag'] = 0
            self.s['coin'] = None if self.s['coin'] is None else self.s['coin'] - self.cost

    def shop_close(self): self.calls.append('shop_close')

    def wear(self):
        self.calls.append('wear')
        if not self.wear_rc:
            self.s['bag'], self.s['worn'] = None, True
        return self.wear_rc

    def set_first(self, dry_run=False):
        self.calls.append('set_first dry' if dry_run else 'set_first')
        return self.first_rc, {'人物首次動作': '風的精靈Lv.5', '人物首次勾選': True}, ''

    def team_form(self): return self._c('team_form') or self.team_rc
    def grind_go(self): return self._c('grind_go') or self.grind_rc


def go(**kw):
    ra = {k: kw.pop(k) for k in ('confirm_buy', 'dry_run', 'form', 'grind') if k in kw}
    f = Fake(**kw)
    rc, out = quiet(bw.run, tools=f, **ra)
    return rc, f, out


# 已穿：只做 first，不出門、不買、不回村（人在練功地圖）
rc, f, _ = go(worn=True)
check('已穿 → rc 0、只 set_first', rc == 0 and f.calls[-1] == 'set_first' and 'shop_buy' not in f.calls and 'to_town' not in f.calls and 'team_form' not in f.calls, str(f.calls))
check('已穿：不需要 --confirm-buy', rc == 0)
# 在背包：wear → first
rc, f, _ = go(bag=3)
check('在背包 → wear 再 first、不買', rc == 0 and f.calls[-3:] == ['wear', 'inspect', 'set_first'] and 'shop_buy' not in f.calls, str(f.calls))
# 沒有、沒給 confirm
rc, f, out = go()
check('沒有且沒 --confirm-buy → 201、什麼都沒做', rc == bw.EXIT_PRE and 'stop_follow' not in f.calls and 'shop_buy' not in f.calls, str(f.calls))
# 完整買
rc, f, _ = go(confirm_buy=True)
i = f.calls
order = ['stop_follow', 'encounter_off', 'to_town', 'disband', 'walk_to 1000', 'talk (56, 59)', 'wait_map', 'walk_to 130', 'talk (43, 3)',
         'shop_select_read', 'shop_buy', 'shop_close', 'wear', 'set_first', 'team_form', 'grind_go']
pos_ = [i.index(x) for x in order if x in i]
check('完整買：全部步驟都有、順序正確', rc == 0 and len(pos_) == len(order) and pos_ == sorted(pos_), str(i))
check('完整買：只按一次購買', i.count('shop_buy') == 1)
check('完整買：回村時不再傳送（已在 130 → 要傳）', i.count('to_town') == 2, str(i))
# 人本來就在薩姆吉爾 / 競技場
rc, f, _ = go(confirm_buy=True, pos=(1000, 60, 60))
check('已在薩姆吉爾：不先傳送', rc == 0 and f.calls.count('to_town') == 1, str(f.calls))
rc, f, _ = go(confirm_buy=True, pos=(130, 46, 6))
check('已在競技場：不走嚮導', rc == 0 and 'talk (56, 59)' not in f.calls and 'wait_map' not in f.calls, str(f.calls))
# --no-form / --no-grind
rc, f, _ = go(confirm_buy=True, form=False, grind=False)
check('--no-form --no-grind：回村但不組隊不練功', rc == 0 and 'team_form' not in f.calls and 'grind_go' not in f.calls and f.calls.count('to_town') == 2, str(f.calls))
# 標題不符 → 不買、關店
rc, f, _ = go(confirm_buy=True, title='芙雷美雅Lv5金幣')
check('標題不符 → 205、不買、關店', rc == bw.EXIT_SHOP and 'shop_buy' not in f.calls and 'shop_close' in f.calls, str(f.calls))
rc, f, _ = go(confirm_buy=True, title='')
check('標題讀不到 → 205、不買', rc == bw.EXIT_SHOP and 'shop_buy' not in f.calls)
rc, f, _ = go(confirm_buy=True, price='1000')
check('價格不是 500 → 205、不買', rc == bw.EXIT_SHOP and 'shop_buy' not in f.calls)
# 買完驗證
rc, f, _ = go(confirm_buy=True, buy_cost=1000)
check('石幣少 1000（買兩個？）→ 205、不穿', rc == bw.EXIT_SHOP and 'wear' not in f.calls, str(f.calls))
rc, f, _ = go(confirm_buy=True, got=False)
check('按了購買但沒進背包 → 205、不重買', rc == bw.EXIT_SHOP and f.calls.count('shop_buy') == 1 and 'wear' not in f.calls)
rc, f, _ = go(confirm_buy=True, coin=None)
check('石幣讀不到但背包有 → 繼續（以背包為準）', rc == 0 and 'wear' in f.calls, str(f.calls))
# 失敗碼
rc, f, _ = go(confirm_buy=True, stop_ok=False)
check('follow 停不掉 → 203、不傳送', rc == bw.EXIT_TOWN and 'to_town' not in f.calls)
rc, f, _ = go(confirm_buy=True, rc={'disband': 47})
check('解散失敗 → 203', rc == bw.EXIT_TOWN and 'walk_to 1000' not in f.calls)
rc, f, _ = go(bag=1, wear_rc=95)
check('穿戴失敗 → 206', rc == bw.EXIT_WEAR and 'set_first' not in f.calls)
rc, f, _ = go(worn=True, first_rc=12)
check('首次動作 12 → 207', rc == bw.EXIT_FIRST)
rc, f, _ = go(confirm_buy=True, team_rc=45)
check('組隊失敗 → 208、不練功', rc == bw.EXIT_BACK and 'grind_go' not in f.calls)
rc, f, _ = go(confirm_buy=True, grind_rc=55)
check('練功失敗 → 209', rc == bw.EXIT_GRIND)
rc, f, _ = go(worn=True, rc={'inspect': 90})
check('讀背包失敗 90 → 202', rc == bw.EXIT_BAG)
rc, f, _ = go(worn=True, rc={'char_ensure': 58})
check('切不回隊長 → 201', rc == bw.EXIT_PRE)
# 8 / 9 / 10 原碼
for code in (8, 9, 10):
    rc, f, _ = go(worn=True, rc={'preflight': code})
    check(f'preflight {code} 原碼停手、不碰任何東西', rc == code and f.calls == ['preflight'], str(f.calls))
    rc, f, _ = go(confirm_buy=True, rc={'disband': code})
    check(f'disband {code} 原碼', rc == code)
    rc, f, _ = go(bag=1, rc={'inspect': code})
    check(f'inspect {code} 原碼', rc == code)
# dry-run
rc, f, out = go(confirm_buy=True, dry_run=True)
check('dry-run 沒有金幣：不買不停 follow 不出門', rc == 0 and f.calls == ['preflight', 'char_ensure', 'inspect'], str(f.calls))
rc, f, out = go(worn=True, dry_run=True)
check('dry-run 已穿：只讀首次動作（dry）', rc == 0 and f.calls[-1] == 'set_first dry' and 'wear' not in f.calls, str(f.calls))
# 上次中斷在競技場：已穿 + 人在競技場 → first 後回村
rc, f, _ = go(worn=True, pos=(130, 52, 19))
check('已穿但人在競技場（上次中斷）→ first 後回村組隊練功', rc == 0 and f.calls[-3:] == ['to_town', 'team_form', 'grind_go'] or f.calls[-4:] == ['set_first', 'to_town', 'team_form', 'grind_go'], str(f.calls))

# ---------------- _visit_first（假 ass 內部函式）----------------
import ass  # noqa: E402


class FakeAss:
    """模擬外掛面板人物首次動作欄：value / checked；下拉選項清單 options"""
    def __init__(self, value='攻擊', checked=False, options=('攻擊', '防禦', '逃跑', '滋潤的精靈Lv.3', '風的精靈Lv.5'), panel=True):
        self.value, self.checked, self.options = value, checked, list(options)
        self.open, self.panel, self.clicks = False, panel, []

    def install(self):
        ass.pet_on_top = lambda: True
        ass.panel_open = lambda: self.panel
        ass.selected_role = lambda: 'DKBO6'
        ass.sleep = lambda s: None
        ass.log = lambda m: None
        ass.read_role_first = self.read
        ass._ocr_lines = self.list_ocr
        ass.gui = self.gui

    def read(self, ocr=True):
        return {'first_on': self.checked, 'first': self.value.replace('Lv.5', 'Lv.5') if ocr else None}

    def list_ocr(self, box, *opts):
        base = bw.ROLE_FIRST_DD[1] + 42
        return [(o, 944, base + 42 * k) for k, o in enumerate(self.options)] if self.open else []

    def gui(self, *a, note=''):
        cmd = a[1] if a and a[0] == 'seq' else ''
        self.clicks.append(cmd)
        parts = cmd.split(';')[0].split()
        x, y = int(parts[1]), int(parts[2])
        if (x, y) == bw.ROLE_FIRST_DD:
            self.open = not self.open
        elif (x, y) == ass.ROLE_FIRST_CHK:
            self.checked = not self.checked
        elif self.open and x == ass.PET_OPT_X:
            k = round((y - (bw.ROLE_FIRST_DD[1] + 42)) / 42)
            if 0 <= k < len(self.options):
                self.value = self.options[k]
            self.open = False
        return 'ok'


def visit(fa, dry=False):
    fa.install()
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
        return bw._visit_first('DKBO6', dry)


fa = FakeAss()
rc, st, msg, todo = visit(fa)
check('visit：攻擊 + 未勾 → 選風的精靈 + 勾', rc == 0 and fa.value == '風的精靈Lv.5' and fa.checked and todo == ['人物首次動作', '人物首次勾選'], f'{rc} {fa.value} {fa.checked} {todo}')
fa = FakeAss(value='風的精靈Lv.5', checked=True)
rc, st, msg, todo = visit(fa)
check('visit：已是風的精靈 + 已勾 → 一次都不點', rc == 0 and fa.clicks == [] and todo == [])
fa = FakeAss(value='風的精靈Lv.5', checked=False)
rc, st, msg, todo = visit(fa)
check('visit：值對、沒勾 → 只點勾選框', rc == 0 and fa.checked and todo == ['人物首次勾選'] and len(fa.clicks) == 1)
fa = FakeAss(options=('攻擊', '防禦', '逃跑', '滋潤的精靈Lv.3'))
rc, st, msg, todo = visit(fa)
check('visit：下拉沒有風的精靈 → rc 12、收下拉、沒選任何選項', rc == ass.EXIT_NO_OPTION and not fa.open and fa.value == '攻擊' and len(fa.clicks) == 2, f'{rc} {fa.clicks}')
fa = FakeAss()
rc, st, msg, todo = visit(fa, dry=True)
check('visit：dry-run 不點、wrong 列出兩項', rc == 0 and fa.clicks == [] and st['wrong'] == ['人物首次動作', '人物首次勾選'], str(st))
fa = FakeAss(panel=False)
rc, st, msg, todo = visit(fa)
check('visit：面板不在 → 6、不點', rc == ass.EXIT_PANEL_LOST and fa.clicks == [])

# 主視窗 ass.LEADER_FIRST 原值逐字不變（新增 PrimalSA2 只是純資料）
check('LEADER_FIRST 主視窗仍是風的精靈', ass.LEADER_FIRST.get('PrimalSA') == '風的精靈')
check('0 次 powershell（import walk 時唯讀 gui info 版面偵測除外）', not [c for c in PS_CALLS if c[1:2] != ('info',)], str(PS_CALLS[:2]))
print('FAILED' if fails else 'ALL PASS', fails)
sys.exit(1 if fails else 0)
