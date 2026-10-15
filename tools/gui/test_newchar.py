#!/usr/bin/env python3
"""newchar.py 離線測試（假 Tools：只模擬背包 / 寵物 / 外掛 / 隊伍 / 任務的語意，不碰遊戲、0 次 powershell）
＋ 同日新增的 bag.wear_item / wear_many / depot_store_items（假背包內部函式）。
用法：uv run --no-project python tools/gui/test_newchar.py"""
import contextlib
import io
import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import testenv  # noqa: E402,F401  紀錄檔 / 進度檔轉向暫存
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
import newchar as nc  # noqa: E402

fails = 0
ROLES = nc.ALL_ROLES
L = nc.LEADER


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


def reset_progress():
    try:
        nc.PROGRESS.unlink()
    except OSError:
        pass


# ---------------- 純函式 / 常數 ----------------
codes = [nc.EXIT_ARGS, nc.EXIT_PRE, nc.EXIT_BOX, nc.EXIT_PET, nc.EXIT_STORE, nc.EXIT_BATTLE, nc.EXIT_TEAM, nc.EXIT_QUEST, nc.EXIT_GRIND, nc.EXIT_PENDING]
check('退出碼 190～199 連號不重複', codes == list(range(190, 200)))
import shopbuy  # noqa: E402
import postrebirth  # noqa: E402
check('不與 shopbuy 180～184 / postrebirth 170～176 衝突', not set(codes) & {shopbuy.EXIT_BAG, shopbuy.EXIT_PRE, shopbuy.EXIT_BUY, shopbuy.EXIT_STILL, shopbuy.EXIT_FORM,
                                                                    *range(170, 177)})
check('名單 = clients.roster()（主視窗 DKBO～DKBO5，隊長 DKBO）', ROLES == ['DKBO', 'DKBO2', 'DKBO3', 'DKBO4', 'DKBO5'] and L == 'DKBO')
check('存倉清單：4 樣公共 + 1轉新手禮盒 個人', nc.STORE_ITEMS[-1] == ('1轉新手禮盒', 'personal') and [d for _, d in nc.STORE_ITEMS[:-1]] == ['public'] * 4
      and '寵物誘餌' in dict(nc.STORE_ITEMS))
check('present 照順序只回有的', nc.present({'a': 3, 'b': None, 'c': 0}, ['c', 'b', 'a', 'z']) == ['c', 'a'])
check('quest_args', nc.quest_args('初入石器', 5) == ['--task', '初入石器', '--max-seconds', nc.QUEST_SLICE_S, '--team-size', 5])
st = dict((s, status) for s, status, _ in nc.plan({}))
check('plan 標出 points 座標待量測 / buy 未支援', st['points'] == '座標待量測' and st['buy'] == '未支援' and list(st) == nc.STAGES)


# ---------------- 假 Tools ----------------
class Sess:
    def __init__(self, T, rc=0):
        self.T, self.rc = T, rc

    def __enter__(self):
        self.T.calls.append(('bag_open',))
        return self

    def __exit__(self, *e):
        self.T.calls.append(('bag_close',))
        return False


class FakeTools:
    def __init__(self, bags=None, pets=None, rc=None):
        self.bags = bags if bags is not None else {r: ['迎新助力禮盒'] for r in ROLES}
        self.pets = pets if pets is not None else {r: {'迪基格斯': '等待', '瑪斯貝卡': '等待'} for r in ROLES}
        self.depot = {'public': [], 'personal': {}}
        self.rc = dict(rc or {})          # 動作名 → 退出碼（或 callable(args) → 退出碼）
        self.calls = []
        self.worn = {r: [] for r in ROLES}
        self.auto = {r: False for r in ROLES}
        self.points_rc = 15
        self.quest_rc = {'初入石器': 0, '覲見村長': 0}
        self.use_noop = set()             # 使用了但沒消失的道具（模擬按鈕落空）

    def _rc(self, k, *a):
        v = self.rc.get(k, 0)
        return v(*a) if callable(v) else v

    def preflight(self):
        self.calls.append(('preflight',))
        return self._rc('preflight')

    def char_ensure(self, name):
        self.calls.append(('ensure', name))
        return self._rc('ensure')

    def snap(self, tag):
        pass

    def sleep(self, s):
        pass

    def bag_session(self):
        return Sess(self, self._rc('bag_session'))

    def find_items(self, role, names):
        self.calls.append(('find', role))
        rc = self._rc('find')
        if rc:
            return rc, {}
        bag = self.bags[role]
        return 0, {n: (bag.index(n) if n in bag else None) for n in names}

    def use(self, role, name):
        self.calls.append(('use', role, name))
        rc = self._rc('use', role, name)
        if rc:
            return rc
        if name in self.use_noop:
            return 0
        self.bags[role].remove(name)
        if name == '迎新助力禮盒':
            self.bags[role] += ['新手棍棒', '新手鎧甲', '新手頭盔', '石幣2萬', '離線水晶', '2倍智慧果', '寵物誘餌', '安撫之素', '1轉新手禮盒']
        return 0

    def wear(self, role, name):
        self.calls.append(('wear', role, name))
        rc = self._rc('wear', role, name)
        if rc:
            return rc
        if name not in self.bags[role]:
            return 92
        self.bags[role].remove(name)
        self.worn[role].append(name)
        return 0

    def store_items(self, roles, items):
        self.calls.append(('store', tuple(roles), tuple(items)))
        rc = self._rc('store')
        out = {}
        if rc:
            return rc, out
        for r in roles:
            res = out.setdefault(r, {})
            for nm, dep in items:
                if nm in self.bags[r]:
                    self.bags[r].remove(nm)
                    (self.depot['public'].append(nm) if dep == 'public' else self.depot['personal'].setdefault(r, []).append(nm))
                    res[nm] = 0
                else:
                    res[nm] = 92
        return 0, out

    def pet_state_many(self, roles, pet, state, allow_mount=False):
        self.calls.append(('pet', pet, state, allow_mount))
        rc = self._rc('pet', pet)
        if rc:
            return rc
        if state == '騎乘' and not allow_mount:
            return 73
        for r in roles:
            self.pets[r][pet] = state
        return 0

    def ass_set_many(self, plan_):
        self.calls.append(('ass', tuple(plan_)))
        rc = self._rc('ass')
        if rc:
            return rc, {}, 'x', {}
        changed = {r: ['自動戰鬥'] for r, ch in plan_.items() if not self.auto[r]}
        for r in plan_:
            self.auto[r] = True
        return 0, {r: {'自動戰鬥': True} for r in plan_}, '', {'changed': changed}

    def points_set(self, leader, verify):
        self.calls.append(('points', leader, tuple(verify)))
        return self.points_rc, {}, '方案不同' if self.points_rc else '', {}

    def team_form(self, leader, size):
        self.calls.append(('team', leader, size))
        return self._rc('team')

    def quest(self, args):
        task = args[args.index('--task') + 1]
        self.calls.append(('quest', task))
        return self.quest_rc[task]

    def grind_go(self):
        self.calls.append(('grind',))
        return self._rc('grind')

    def names(self):
        return [c[0] for c in self.calls]


# ---------------- 整段 ----------------
reset_progress()
T = FakeTools()
rc, out = quiet(nc.run, tools=T, fresh=True)
check('全新 5 人：跑完、只有 points 待手動 → 199', rc == nc.EXIT_PENDING and set(nc.LAST['pending']) == {'points'}, f'rc={rc} {out[-400:]}')
check('步驟順序 preflight → 背包 → 寵物 → 存倉 → 外掛 → 加點 → 組隊 → 任務 → 練功',
      [n for n in T.names() if n in ('preflight', 'bag_open', 'pet', 'store', 'ass', 'points', 'team', 'quest', 'grind')][:1] == ['preflight']
      and T.names().index('pet') > T.names().index('bag_close') and T.names().index('store') > T.names().index('pet')
      and T.names().index('ass') < T.names().index('points') < T.names().index('team') < T.names().index('quest') < T.names().index('grind'))
check('背包面板只開一次（boxes），5 人連續做完', T.names().count('bag_open') == 1)
check('每人：開迎新助力禮盒 → 石幣2萬 → 穿 3 件', all(('use', r, '迎新助力禮盒') in T.calls and ('use', r, '石幣2萬') in T.calls and T.worn[r] == nc.GEAR for r in ROLES))
check('禮盒內容存倉：公共 4 樣 × 5、1轉新手禮盒 每人個人倉庫', T.depot['public'].count('寵物誘餌') == 5 and len(T.depot['public']) == 20
      and all(T.depot['personal'][r] == ['1轉新手禮盒'] for r in ROLES))
check('寵物：迪基格斯 出戰、瑪斯貝卡 騎乘（allow_mount）', all(T.pets[r] == {'迪基格斯': '出戰', '瑪斯貝卡': '騎乘'} for r in ROLES)
      and ('pet', '瑪斯貝卡', '騎乘', True) in T.calls)
check('外掛自動戰鬥：5 人、隊長最後', ('ass', ('DKBO2', 'DKBO3', 'DKBO4', 'DKBO5', 'DKBO')) in T.calls and all(T.auto.values()))
check('加點：隊長設、其他 4 人看', ('points', 'DKBO', ('DKBO2', 'DKBO3', 'DKBO4', 'DKBO5')) in T.calls)
check('組隊：隊長 DKBO、5 人', ('team', 'DKBO', 5) in T.calls)
check('任務：初入石器 → 覲見村長', [c[1] for c in T.calls if c[0] == 'quest'] == ['初入石器', '覲見村長'])
check('沒給 --confirm-buy：buy 記完成（不買）、不算待手動', 'buy' in nc.LAST['done'] and 'buy' not in nc.LAST['pending'])
check('0 次 powershell', PS_CALLS == [])

# 重跑：進度檔已完成的步驟跳過（points 待手動會再試一次）
T2 = FakeTools(bags={r: [] for r in ROLES})
rc, out = quiet(nc.run, tools=T2)
check('重跑：只跑 preflight + 待手動的 points，其他跳過 → 仍 199', rc == nc.EXIT_PENDING and set(T2.names()) == {'preflight', 'ensure', 'points'}, f'{T2.names()}')
T2.points_rc = 0
rc, out = quiet(nc.run, tools=T2)
check('使用者手動設好方案後重跑：points 0 → 全部完成 rc 0', rc == 0 and nc.LAST['pending'] == {} and 'points' in nc.LAST['done'], f'rc={rc}')

# 已開過 / 已穿上：不重做（--fresh 從頭，但每步看狀態）
T3 = FakeTools(bags={r: ['寵物誘餌'] for r in ROLES}, pets={r: {'迪基格斯': '出戰', '瑪斯貝卡': '騎乘'} for r in ROLES})
T3.points_rc = 0
rc, out = quiet(nc.run, tools=T3, fresh=True)
check('禮盒已開、裝備已穿：0 次使用 / 穿戴，誘餌照存', rc == 0 and 'use' not in T3.names() and 'wear' not in T3.names() and T3.depot['public'] == ['寵物誘餌'] * 5, f'rc={rc}')

# 2轉新手禮盒（PrimalSA2 實機背包第 0 格）：條件不符 → 跳過只記錄，不是錯誤
T4 = FakeTools(bags={r: ['2轉新手禮盒', '迎新助力禮盒'] for r in ROLES})
rc, out = quiet(nc.run, tools=T4, fresh=True, to_stage='boxes')
check('2轉新手禮盒 不開、記 skipped；迎新照開', rc == 0 and not any(c[0] == 'use' and c[2] == '2轉新手禮盒' for c in T4.calls)
      and nc.LAST['done'] == ['boxes'] and all('2轉新手禮盒' in T4.bags[r] for r in ROLES), f'rc={rc}')
check('--to boxes：之後的步驟都沒跑', 'pet' not in T4.names() and 'grind' not in T4.names())

# 使用後還在（按鈕落空）→ 重用一次；仍在 → 95 → 192
T5 = FakeTools()
T5.use_noop = {'石幣2萬'}
rc, out = quiet(nc.run, tools=T5, fresh=True)
check('石幣2萬 用了還在 → 重用 1 次 → 192（bag_rc 95）', rc == nc.EXIT_BOX and nc.LAST.get('bag_rc') == 95
      and T5.calls.count(('use', 'DKBO', '石幣2萬')) == 2 and 'pet' not in T5.names(), f'rc={rc} {nc.LAST}')
check('失敗時背包 Session 照樣關（with 結束）', T5.names()[-1] == 'bag_close' or 'bag_close' in T5.names())

# 穿戴失敗 → 192；修好後 --from boxes 續跑
T6 = FakeTools(rc={'wear': lambda r, n: 95 if (r, n) == ('DKBO3', '新手鎧甲') else 0})
rc, out = quiet(nc.run, tools=T6, fresh=True)
check('DKBO3 穿鎧甲 95 → 192、DKBO4 之後沒動', rc == nc.EXIT_BOX and not any(c[0] == 'use' and c[1] == 'DKBO4' for c in T6.calls))
T6.rc = {}
T6.points_rc = 0
rc, out = quiet(nc.run, tools=T6, from_stage='boxes')
check('--from boxes 續跑：已開的不再開、DKBO3 補穿鎧甲、全部完成', rc == 0 and T6.worn['DKBO3'].count('新手鎧甲') == 1
      and T6.calls.count(('use', 'DKBO', '迎新助力禮盒')) == 1, f'rc={rc} {nc.LAST.get("msg")}')

# 8 / 9 / 10 原碼停手
for code in (8, 9, 10):
    T7 = FakeTools(rc={'pet': code})
    rc, out = quiet(nc.run, tools=T7, fresh=True)
    check(f'寵物步驟回 {code} → 原碼 {code} 停手、後面沒跑', rc == code and 'store' not in T7.names() and 'grind' not in T7.names())
T7 = FakeTools(rc={'preflight': 9})
rc, out = quiet(nc.run, tools=T7, fresh=True)
check('preflight 9（疑似驗證視窗）→ 9、零動作', rc == 9 and T7.names() == ['preflight'])
T7 = FakeTools(rc={'pet': 73})
rc, out = quiet(nc.run, tools=T7, fresh=True)
check('寵物其他失敗 73 → 193（pet_rc）', rc == nc.EXIT_PET and nc.LAST.get('pet_rc') == 73)
T7 = FakeTools(rc={'team': 41})
rc, out = quiet(nc.run, tools=T7, fresh=True)
check('組隊失敗 → 196、不跑任務', rc == nc.EXIT_TEAM and 'quest' not in T7.names())

# 任務：5 = 追蹤欄沒有 → 已做完；2 = 不認得畫面 → 9；其他 → 197
T8 = FakeTools()
T8.points_rc = 0
T8.quest_rc = {'初入石器': 5, '覲見村長': 0}
rc, out = quiet(nc.run, tools=T8, fresh=True)
check('初入石器 回 5（已做完）→ 跳過、覲見村長照跑 → 0', rc == 0 and [c[1] for c in T8.calls if c[0] == 'quest'] == ['初入石器', '覲見村長'])
T8 = FakeTools()
T8.quest_rc = {'初入石器': 2, '覲見村長': 0}
rc, out = quiet(nc.run, tools=T8, fresh=True)
check('quest.py 2（不認得畫面）→ 9 停手、不去練功', rc == 9 and 'grind' not in T8.names())
T8 = FakeTools()
T8.quest_rc = {'初入石器': 0, '覲見村長': 30}
rc, out = quiet(nc.run, tools=T8, fresh=True)
check('quest.py 30 → 197（quest_rc）', rc == nc.EXIT_QUEST and nc.LAST.get('quest_rc') == 30)

# --confirm-buy：未支援 → 記待手動、最後 199；--no-grind
T9 = FakeTools()
T9.points_rc = 0
rc, out = quiet(nc.run, tools=T9, fresh=True, confirm_buy=True, no_grind=True)
check('--confirm-buy → buy 待手動（未支援）、--no-grind 不呼叫 grind → 199', rc == nc.EXIT_PENDING and set(nc.LAST['pending']) == {'buy'} and 'grind' not in T9.names())
T9 = FakeTools(rc={'grind': 52})
T9.points_rc = 0
rc, out = quiet(nc.run, tools=T9, fresh=True)
check('grind 失敗 → 198（grind_rc）', rc == nc.EXIT_GRIND and nc.LAST.get('grind_rc') == 52)
T9 = FakeTools()
T9.points_rc = 9
rc, out = quiet(nc.run, tools=T9, fresh=True)
check('加點回 9 → 9 停手（不當待手動）', rc == 9 and 'team' not in T9.names())

# 參數
reset_progress()
rc, out = quiet(nc.run, tools=FakeTools(), from_stage='store')
check('--from store 但 boxes / pets 沒做 → 190、零動作', rc == nc.EXIT_ARGS)
rc, out = quiet(nc.run, tools=FakeTools(), from_stage='grind', to_stage='boxes')
check('--from 在 --to 之後 → 190', rc == nc.EXIT_ARGS)
_keep = nc.ALL_ROLES
nc.ALL_ROLES = []
rc, out = quiet(nc.run, tools=FakeTools())
check('名單是空的（PSA_CLIENT 沒登錄）→ 190', rc == nc.EXIT_ARGS)
nc.ALL_ROLES = _keep

# dry-run / plan：不碰遊戲（tools=None 也不建 Tools）
rc, out = quiet(nc.run, dry_run=True, confirm_buy=True)
check('plan：rc 0、印出待量測 / 未支援 / 退出碼', rc == 0 and '座標待量測' in out and '未支援' in out and '199' in out and PS_CALLS == [])
rc, out = quiet(nc.main, ['plan'])
check('CLI plan：rc 0、0 次 powershell', rc == 0 and PS_CALLS == [] and '"dry_run": true' in out)

# PSA_CLIENT=PrimalSA2：名單 DKBO6～DKBO10（子程序 import，不碰遊戲）
env = dict(os.environ, PSA_CLIENT='PrimalSA2', PYTHONIOENCODING='utf-8')
r = subprocess.run([sys.executable, '-c', 'import sys; sys.path.insert(0, r"%s"); import testenv, newchar as n; print(n.ALL_ROLES, n.LEADER, n.PROGRESS.name)' % HERE],
                   capture_output=True, text=True, encoding='utf-8', env=env, timeout=60)
check('PSA_CLIENT=PrimalSA2 → 名單 DKBO6～DKBO10、隊長 DKBO6', "['DKBO6', 'DKBO7', 'DKBO8', 'DKBO9', 'DKBO10'] DKBO6 newchar.json" in r.stdout, r.stdout + r.stderr[-300:])

# ---------------- bag.wear_item / wear_many / depot_store_items（假背包內部） ----------------
import bag  # noqa: E402


class BS:
    rc = 0

    def __enter__(self):
        return self

    def __exit__(self, *e):
        return False


bag.Session = BS
bag.select_role = lambda role, ctx=None: 0
bag.uikit.sleep = lambda s: None
bag._wait = lambda pred, secs=2.0: pred()
bag._learn_verified = lambda *a, **k: False
SLOTS = {}
state = {'popup': False, 'clicked': []}


def _find(want, depot=False, popup_fallback=True, hint=None):
    return next((i for i, n in SLOTS.items() if n == want), None)


bag.find_item = _find
bag.open_slot_popup = lambda i, depot=False: (state.__setitem__('popup', True), state.__setitem__('i', i), True)[2]
bag.popup_name = lambda want=None: SLOTS.get(state.get('i'), '')
bag.popup_open = lambda: state['popup']
bag.close_popup = lambda: state.__setitem__('popup', False)
bag.slot_occupancy = lambda: [i in SLOTS for i in range(15)]


def _press(label, allow=()):
    state['clicked'].append(label)
    if label != '穿戴':
        return 96, 'consumable'
    state['popup'] = False
    if not state.get('stuck'):
        old = state.get('swap')
        if old:
            SLOTS[state['i']] = old
        else:
            SLOTS.pop(state['i'], None)
    return 0, 'equip'


bag.click_popup_button = _press
SLOTS.update({1: '新手棍棒', 2: '新手鎧甲'})
check('wear_item：穿上 → 那格變空 → 0', bag.wear_item('DKBO', '新手棍棒') == 0 and 1 not in SLOTS and state['clicked'] == ['穿戴'])
check('wear_item：背包沒有 → 92、沒點', bag.wear_item('DKBO', '新手頭盔') == bag.EXIT_ITEM and state['clicked'] == ['穿戴'])
state['swap'] = '木棒'
check('wear_item：有舊裝備換到那格（格子不空、但不再是鎧甲）→ 0', bag.wear_item('DKBO', '新手鎧甲') == 0 and SLOTS[2] == '木棒')
state['swap'] = None
SLOTS.clear()
SLOTS.update({0: '新手頭盔'})
state['stuck'] = True
check('wear_item：按了穿戴但格子沒變 → 95（不重點）', bag.wear_item('DKBO', '新手頭盔') == bag.EXIT_VERIFY and state['clicked'].count('穿戴') == 3)
state['stuck'] = False
_pn = bag.popup_name
bag.popup_name = lambda want=None: '石幣2萬'
check('wear_item：彈窗名稱不符 → 96、不按穿戴', bag.wear_item('DKBO', '新手頭盔') == bag.EXIT_NAME and state['clicked'].count('穿戴') == 3)
bag.popup_name = _pn
SLOTS.clear()
SLOTS.update({0: '新手頭盔', 3: '新手棍棒'})
rc, d = bag.wear_many(['DKBO'], ['新手棍棒', '新手鎧甲', '新手頭盔'])
check('wear_many：沒有的（鎧甲）略過，其他穿上', rc == 0 and d['DKBO'] == {'新手棍棒': 0, '新手鎧甲': bag.EXIT_ITEM, '新手頭盔': 0} and not SLOTS)
rc, d = bag.wear_many(['DKBO'], ['新手鎧甲'], skip_missing=False)
check('wear_many --strict：沒有 → 92', rc == bag.EXIT_ITEM)

stores = []
seq = {}


def _store(role, want, depot='public', keep_ok=False, all_copies=False):
    stores.append((role, want, depot))
    v = seq.get((role, want))
    if isinstance(v, list):
        return v.pop(0)
    return v if v is not None else 0


bag.depot_store = _store
items = [('1轉新手禮盒', 'personal'), ('寵物誘餌', 'public'), ('離線水晶', 'public')]
seq.update({('DKBO2', '離線水晶'): 92})
rc, d = bag.depot_store_items(['DKBO', 'DKBO2'], items)
check('depot_store_items：逐人一次存完、公共先個人後、沒有的略過', rc == 0 and stores[:3] == [('DKBO', '寵物誘餌', 'public'), ('DKBO', '離線水晶', 'public'), ('DKBO', '1轉新手禮盒', 'personal')]
      and d['DKBO2']['離線水晶'] == bag.EXIT_ITEM and len(stores) == 6, str(stores))
stores.clear()
seq.clear()
seq.update({('DKBO', '寵物誘餌'): [bag.EXIT_VERIFY, bag.EXIT_ITEM]})
rc, d = bag.depot_store_items(['DKBO'], items)
check('depot_store_items：95 → 重存一次，回 92 = 第一次其實存了 → 0', rc == 0 and d['DKBO']['寵物誘餌'] == 0 and stores.count(('DKBO', '寵物誘餌', 'public')) == 2)
stores.clear()
seq.clear()
seq.update({('DKBO', '離線水晶'): bag.EXIT_FULL})
rc, d = bag.depot_store_items(['DKBO', 'DKBO2'], items)
check('depot_store_items：倉庫滿 94 → 立即停、不做下一人', rc == bag.EXIT_FULL and not any(s[0] == 'DKBO2' for s in stores))
check('bag 新函式測試也是 0 次 powershell', PS_CALLS == [])

# ---------------- --skip ----------------
reset_progress()
T = FakeTools()
rc, out = quiet(nc.run, tools=T, fresh=True, skip=['points'])
check('--skip points：不呼叫 points、不開加點、回 0（不是 199）', rc == 0 and not any(c[0] == 'points' for c in T.calls) and nc.LAST['skipped'] == ['points'], f'rc={rc} {out[-300:]}')
check('--skip：記「略過（--skip）」、不寫進完成 / 待手動', '略過（--skip）' in out and 'points' not in nc.LAST['done'] and 'points' not in nc.LAST['pending'])
reset_progress()
T = FakeTools()
rc, out = quiet(nc.run, from_stage='team', tools=T, fresh=True, skip=['boxes', 'pets', 'store', 'battle', 'points'])
check('--skip 的步驟視為滿足 --from 前置（不回 190）', rc == 0 and [c[0] for c in T.calls if c[0] in ('team', 'quest', 'grind', 'bag_open', 'pet')] == ['team', 'quest', 'quest', 'grind'], f'rc={rc} {out[-300:]}')
reset_progress()
T = FakeTools()
rc, out = quiet(nc.run, from_stage='team', tools=T, fresh=True)
check('沒 skip 時 --from team 前置缺 → 190', rc == nc.EXIT_ARGS)
rc, out = quiet(nc.run, tools=T, fresh=True, skip=['nope'])
check('--skip 不認得 / preflight → 190', rc == nc.EXIT_ARGS)
rc, out = quiet(nc.run, tools=T, fresh=True, skip=['preflight'])
check('--skip preflight 不行 → 190', rc == nc.EXIT_ARGS)
rc, out = quiet(nc.run, dry_run=True, fresh=True, skip=['points'])
check('plan 顯示略過', rc == 0 and '略過（--skip）' in out and nc.LAST['dry_run'])
rc, out = quiet(nc.main, ['plan', '--skip', 'points,buy'])
check('CLI --skip points,buy', rc == 0 and out.count('略過（--skip）') == 2)
check('--skip 測試 0 次 powershell', PS_CALLS == [])

print('全部通過' if not fails else f'{fails} 項失敗')
sys.exit(1 if fails else 0)
