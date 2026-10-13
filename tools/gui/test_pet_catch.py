#!/usr/bin/env python3
"""pet_catch.py 離線測試（假 Tools，不碰遊戲）。用法：uv run --no-project python tools/gui/test_pet_catch.py"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import testenv  # noqa: E402,F401
import pet_catch  # noqa: E402
import rebirth_pets as rp  # noqa: E402
import petmatch  # noqa: E402

fails = 0


def check(name, ok, extra=''):
    global fails
    print(('PASS ' if ok else 'FAIL ') + name + (f' {extra}' if extra and not ok else ''))
    fails += 0 if ok else 1


check('parse_assign', pet_catch.parse_assign('DKBO2:鯊魚系:克邦凱斯,DKBO3:鯊魚系:加克拉') == [('DKBO2', '鯊魚系', '克邦凱斯'), ('DKBO3', '鯊魚系', '加克拉')])
try:
    pet_catch.parse_assign('DKBO2:鯊魚系')
    check('parse_assign 格式錯 → ValueError', False)
except ValueError:
    check('parse_assign 格式錯 → ValueError', True)


class FakeT:
    def __init__(self, fail_at=None):
        self.calls, self.fail_at = [], fail_at

    def _r(self, tag, role):
        self.calls.append((tag, role))
        return 7 if self.fail_at == (tag, role) else 0

    def bait_take(self, role, keep):
        return self._r('bait', role)

    def bait_take_many(self, roles, keep):
        self.calls.append(('bait_many', tuple(roles)))
        for r in roles:
            rc = self._r('bait', r)
            if rc:
                self.bait_failed = r
                return rc
        return 0

    def catch_setup(self, role, fam, sp, count):
        return self._r('setup', role)

    def catch_start(self, role, count):
        return self._r('start', role)

    def catch_setup_many(self, assign, count, reuse=False):
        self.calls.append(('ass_open', tuple(r for r, _, _ in assign)) + (('reuse',) if reuse else ()))
        for r, fam, sp in assign:
            for tag in ('setup', 'start'):
                rc = self._r(tag, r)
                if rc:
                    return rc, r
        return 0, None

    def sleep(self, s):
        pass


A = [('DKBO2', '鯊魚系', '克邦凱斯'), ('DKBO3', '鯊魚系', '加克拉')]
f = FakeT()
check('dry-run 零呼叫', pet_catch.run(A, dry_run=True, tools=f) == 0 and not f.calls)
f = FakeT()
rc = pet_catch.run(A, stages=('setup',), tools=f)
check('setup：外掛面板開 1 次、逐人 setup + start', rc == 0 and f.calls == [('ass_open', ('DKBO2', 'DKBO3')), ('setup', 'DKBO2'), ('start', 'DKBO2'), ('setup', 'DKBO3'), ('start', 'DKBO3')])
f = FakeT(fail_at=('setup', 'DKBO2'))
check('setup 失敗 → 該 rc、不繼續下一人', pet_catch.run(A, stages=('setup',), tools=f) == 7 and f.calls[1:] == [('setup', 'DKBO2')])
f = FakeT(fail_at=('bait', 'DKBO2'))
check('bait 失敗 → rc、不繼續', pet_catch.run(A, stages=('bait',), tools=f) == 7 and f.calls == [('bait_many', ('DKBO2', 'DKBO3')), ('bait', 'DKBO2')])
f = FakeT()
check('bait：一次 bait_take_many 帶全部人（背包只開一次）', pet_catch.run(A, stages=('bait',), tools=f) == 0 and f.calls[0] == ('bait_many', ('DKBO2', 'DKBO3')))

# register_growths：撞到別的物種 → 刪除（只靠縮圖）
import tempfile
reg = {'thumb': {}, 'growth': {'1/1/1/1': '甲'}}
petmatch.load_species = lambda: reg
petmatch.save_species = lambda r: None
dropped = pet_catch.register_growths({'1/1/1/1': '乙', '2/2/2/2': '乙'})
check('register_growths：新字串登錄、撞別種的刪掉並計數', dropped == 1 and reg['growth'] == {'2/2/2/2': '乙'})

# rebirth_pets 純函式：系別清單鄰居備援表、物種列順序
check('FAMILY_NEIGHBORS / SPECIES_ORDER 有鯊魚系與火雞系', '鯊魚系' in rp.FAMILY_NEIGHBORS and rp.SPECIES_ORDER['鯊魚系'][0] == '克邦凱斯' and rp.SPECIES_ORDER['火雞系'][3] == '奇寶')
class FT2:
    def __init__(self, pets):
        self.pets = pets

    def pets_list(self, roles):
        return 0, self.pets


_ok = {'DKBO': [{'empty': False, 'state': '騎乘'}, {'empty': False, 'state': '出戰'}], 'DKBO4': [{'empty': False, 'state': '騎乘'}, {'empty': False, 'state': '等待'}, {'empty': True}]}
check('missing_battle：騎乘 / 等待 / 空格都不算出戰', pet_catch.missing_battle(_ok) == ['DKBO4'])
check('verify_battle：有人沒出戰寵 → 105；全有 → 0', pet_catch.verify_battle(['DKBO', 'DKBO4'], FT2(_ok)) == 105
      and pet_catch.verify_battle(['DKBO'], FT2({'DKBO': _ok['DKBO']})) == 0)


class FT3(FT2):
    """relock / wait / autoswap 用：記錄外掛開面板次數"""
    def __init__(self, pets, polls=None):
        super().__init__(pets)
        self.opens, self.items, self.polls = [], None, list(polls or [])
        self.locks = {r: {'騎寵': False, '戰寵': False} for r in pets}

    def lock_set_many(self, items):
        self.opens.append('set')
        self.items = items
        for r, w, on, _ in items:
            self.locks[r][w] = on
        return 0, None

    def lock_get_many(self, roles):
        self.opens.append('get')
        return 0, {r: dict(self.locks[r]) for r in roles}

    def catch_poll_many(self, roles):
        self.opens.append(tuple(roles))
        return 0, self.polls.pop(0)

    def ass_each(self, roles, tab, fn):
        self.opens.append(('each', tab, tuple(roles)))
        return 0, {}, None

    def _toggle(self, xy, want, note):
        return 0

    def sleep(self, s):
        pass


BRA, DOR = '布拉奇多斯', '朵拉比斯'
pp = {r: [{'slot': 1, 'empty': False, 'unnamed': '49/9/8/2', 'species': BRA, 'state': '騎乘'}, {'slot': 2, 'empty': False, 'name': DOR, 'state': '出戰'}] for r in ('DKBO', 'DKBO3')}
f3 = FT3(pp)
check('relock：一次 lock_set_many（2 人 × 2 項，騎寵用成長字串）→ 0', pet_catch.relock(['DKBO', 'DKBO3'], tools=f3) == 0 and f3.opens == ['set']
      and ('DKBO3', '騎寵', True, ('growth', '49/9/8/2')) in f3.items and ('DKBO3', '戰寵', True, ('name', DOR)) in f3.items)
f3 = FT3({'DKBO': [{'slot': 1, 'empty': False, 'name': DOR}, {'slot': 2, 'empty': False, 'name': DOR}]})
check('relock：戰寵同名 2 隻 → 107、不開外掛', pet_catch.relock(['DKBO'], which=('戰寵',), tools=f3) == rp.EXIT_LOCK and f3.opens == [])
f3 = FT3({}, polls=[{'DKBO2': (3, True), 'DKBO3': (0, False)}, {'DKBO2': (None, False)}])
check('wait：每輪外掛只開一次讀所有沒抓完的人、抓完的移除', pet_catch.run(A, stages=('wait',), tools=f3) == 0 and f3.opens == [('DKBO2', 'DKBO3'), ('DKBO2',)])
f3 = FT3({})
check('autoswap：ass_each 一次（一般設置分頁）', pet_catch.set_autoswap(['DKBO', 'DKBO2'], False, tools=f3) == 0 and f3.opens == [('each', 'general', ('DKBO', 'DKBO2'))])

# ---- 2026-10-13：物種下拉重試 / 收起 / 讀回 / 輪詢間隔 ----
import ass
import uikit


class Pick:
    """假 OCR / 假點擊：scripts = 每次 ocr_lines 回傳的列表（依序）；記錄點擊"""
    def __init__(self, scripts, field=''):
        self.scripts, self.clicks, self.field = list(scripts), [], field

    def ocr(self, box, *opts):
        if box == rp.CATCH_LIST_PET:
            return self.scripts.pop(0) if len(self.scripts) > 1 else (self.scripts[0] if self.scripts else [])
        return [(self.field, 0, 0)]

    def gui(self, *a, **k):
        self.clicks.append(a)
        if a[0] == 'seq' and 'click 1115' in a[1]:
            self.field = '貝魯卡'


def with_pick(p, fn):
    saved = (rp.ocr_lines, uikit.gui, uikit.sleep, uikit.snap, ass.panel_open)
    rp.ocr_lines, uikit.gui, uikit.sleep, uikit.snap, ass.panel_open = p.ocr, p.gui, lambda s: None, lambda *a, **k: None, lambda: True
    try:
        return fn()
    finally:
        rp.ocr_lines, uikit.gui, uikit.sleep, uikit.snap, ass.panel_open = saved


row = [('貝魯卡', 1115, 463)]
T = rp.Tools()
p = Pick([[], [], row])
ok = with_pick(p, lambda: T._pick_dropdown(rp.CATCH_XY['pet_dd'], rp.CATCH_LIST_PET, rp.OCR_PET_FIELD, ('name', '貝魯卡'), scroll=False, snap_tag='species'))
check('物種下拉：清單先空白 → 重點下拉再讀到目標才選（成功）', ok and sum('click 1283' in str(c) for c in p.clicks) == 2 and any('click 1115 463' in str(c) for c in p.clicks))
p = Pick([[('魯尼帖斯', 1115, 421)]])
ok = with_pick(p, lambda: T._pick_dropdown(rp.CATCH_XY['pet_dd'], rp.CATCH_LIST_PET, rp.OCR_PET_FIELD, ('name', '貝魯卡'), scroll=False, snap_tag='species'))
check('物種下拉：清單開著但沒目標 → False、原因寫進 pick_why、點回欄位收起', not ok and '貝魯卡' in T.pick_why and 'click 1283' in str(p.clicks[-1]))
p = Pick([[]])
ok = with_pick(p, lambda: T._pick_dropdown(rp.CATCH_XY['pet_dd'], rp.CATCH_LIST_PET, rp.OCR_PET_FIELD, ('name', '貝魯卡'), scroll=False, snap_tag='species'))
check('物種下拉：一直空白 → False，沒亂點選項', not ok and not any('click 1115' in str(c) for c in p.clicks))

# _catch_verify
class V(rp.Tools):
    def __init__(self, fam, pet, auto, store):
        self.fam, self.pet, self.chk = fam, pet, {rp.CATCH_XY['auto']: auto, rp.CATCH_XY['store']: store}

    def _checked(self, xy):
        return self.chk[xy]


def verify(fam, pet, auto=True, store=True):
    v = V(fam, pet, auto, store)
    saved = (rp.ocr_lines, uikit.snap)
    rp.ocr_lines = lambda box, *o: [(v.fam if box == rp.OCR_FAMILY_FIELD else v.pet, 0, 0)]
    uikit.snap = lambda *a, **k: None
    try:
        return v._catch_verify('DKBO3', '老虎系', '貝魯卡')
    finally:
        rp.ocr_lines, uikit.snap = saved


check('_catch_verify：全對 → 0', verify('老虎系', '貝魯卡') == 0)
check('_catch_verify：物種欄位不對 → 14', verify('老虎系', '魯尼帖斯') == rp.EXIT_CATCH_PICK)
check('_catch_verify：自動抓寵沒勾 → 14', verify('老虎系', '貝魯卡', auto=False) == rp.EXIT_CATCH_PICK)
check('_catch_verify：欄位 OCR 讀不到字 → 不誤判（略過文字，勾選對就 0）', verify('', '') == 0)
check('輪詢間隔預設 ≥ 120 秒', rp.CATCH_POLL_S >= 120)
f3 = FT3({}, polls=[{'DKBO2': (0, False), 'DKBO3': (0, False)}])
slept = []
f3.sleep = slept.append
pet_catch.run(A, stages=('wait',), tools=f3, poll=77)
check('wait：--poll 秒數有帶進 sleep', slept == [77])
# review 1013b §2.4：第一次輪詢依隻數估、之後 60 秒
check('first_poll_s：4 隻 100、1 隻 40、5 隻 120（夾在 [40, 120]）', pet_catch.first_poll_s(4) == 100 and pet_catch.first_poll_s(1) == 40
      and pet_catch.first_poll_s(5) == 120 and pet_catch.first_poll_s(9) == rp.CATCH_POLL_S)
f3 = FT3({}, polls=[{'DKBO2': (2, True), 'DKBO3': (1, True)}, {'DKBO2': (1, True), 'DKBO3': (0, False)}, {'DKBO2': (0, False)}])
slept = []
f3.sleep = slept.append
rc = pet_catch.run(A, count=4, stages=('wait',), tools=f3)
check('wait 預設：4 隻第一次等 100 秒、之後每 60 秒', rc == 0 and slept == [100.0, 60.0, 60.0], str(slept))
f3 = FT3({}, polls=[{'DKBO2': (0, False), 'DKBO3': (0, False)}])
slept = []
f3.sleep = slept.append
pet_catch.run(A, count=1, stages=('wait',), tools=f3)
check('wait 預設：第 2 批只抓 1 隻 → 40 秒就讀（舊版固定 120）', slept == [40.0], str(slept))
# review 1013b §2.5-A：第 2 批沿用捉寵設置
f = FakeT()
pet_catch.run(A, count=1, stages=('setup',), tools=f, reuse_setup=True)
check('--reuse-setup → catch_setup_many(reuse=True)', ('ass_open', ('DKBO2', 'DKBO3'), 'reuse') in f.calls, str(f.calls))
f = FakeT()
pet_catch.run(A, count=1, stages=('setup',), tools=f)
check('預設不沿用', ('ass_open', ('DKBO2', 'DKBO3')) in f.calls)


class R(rp.Tools):
    """_catch_setup_pick reuse：欄位 OCR 結果可設；記錄有沒有開下拉"""
    def __init__(self, fam, pet, n):
        self.fam, self.pet, self.n, self.dd = fam, pet, n, []

    def _pick_dropdown(self, dd, *a, **k):
        self.dd.append(dd)
        return True


def pick_reuse(fam, pet, reuse, n=1):
    t = R(fam, pet, n)
    saved = (rp.ocr_lines, uikit.snap)
    rp.ocr_lines = lambda box, *o: [((t.fam if box == rp.OCR_FAMILY_FIELD else t.pet if box == rp.OCR_PET_FIELD else f'可抓捕數 {t.n}'), 0, 0)]
    uikit.snap = lambda *a, **k: None
    try:
        return t._catch_setup_pick('DKBO2', '鯊魚系', '克邦凱斯', 1, reuse), t.dd
    finally:
        rp.ocr_lines, uikit.snap = saved


rc, dd = pick_reuse('', '', True)
check('reuse：欄位 OCR 讀不到字（鯊魚系常讀不出）→ 不重選下拉、只驗可抓捕數', rc == 0 and dd == [], f'{rc} {dd}')
rc, dd = pick_reuse('', '', False)
check('不 reuse：欄位讀不到 → 照舊重選系別 / 物種下拉', rc == 0 and len(dd) == 2, f'{rc} {dd}')
rc, dd = pick_reuse('火雞系', '火雞', True)
check('reuse：欄位讀到別的字 → 照樣重選（不盲信上一批）', len(dd) == 2, f'{rc} {dd}')
rc, dd = pick_reuse('', '', True, n=3)
check('reuse：可抓捕數不對 → 照樣 4 停（不勾自動抓寵）', rc == 4 and dd == [], f'{rc} {dd}')

# bag.find_item hint / select_role 已選著不重點頭像
import bag
calls = []
sv = (bag.open_slot_popup, bag.popup_name, bag.close_popup, bag.n_slots, bag.icon_match_slots)
bag.open_slot_popup = lambda i, depot=False: calls.append(i) or True
bag.popup_name = lambda want=None: '寵物誘餌'
bag.close_popup = lambda: True
bag.n_slots = lambda depot=False: 20
bag.icon_match_slots = lambda want, depot=False: (calls.append('icon') or [])
r = bag.find_item('寵物誘餌', depot=True, hint=4)
check('find_item：hint 格名稱吻合 → 只點那一格就回傳（不掃圖示 / 逐格）', r == 4 and calls == [4])
bag.popup_name = lambda want=None: '離線水晶'
calls.clear()
r = bag.find_item('寵物誘餌', depot=True, hint=4)
check('find_item：hint 格名稱不符 → 退回原流程', r is None and calls[0] == 4 and 'icon' in calls)
bag.open_slot_popup, bag.popup_name, bag.close_popup, bag.n_slots, bag.icon_match_slots = sv
clicks = []
sv2 = (bag._avatar_sel, bag._click, bag._ocr_join)
bag._avatar_sel = lambda role: True
bag._click = lambda *a, **k: clicks.append(a) or True
bag._ocr_join = lambda *a, **k: 'DKBO2'
check('select_role：頭像已選著 → 不點頭像、回 0', bag.select_role('DKBO2') == 0 and not clicks)
bag._avatar_sel, bag._click, bag._ocr_join = sv2

# ---- 2026-10-13 register：抓寵來源當主鍵（卡坦 4 鯊 / 4 雞縮圖會混）----
SH = [('DKBO2', '鯊魚系', '克邦凱斯'), ('DKBO3', '鯊魚系', '加克拉'), ('DKBO4', '鯊魚系', '加格'), ('DKBO5', '鯊魚系', '邦恩吉')]
u = lambda n, g, **k: dict({'slot': n, 'empty': False, 'name': None, 'unnamed': g, 'state': '等待'}, **k)    # noqa: E731
mount = {'slot': 1, 'empty': False, 'name': None, 'unnamed': '49/9/8/2', 'species': '布拉奇多斯', 'species_src': 'reg', 'state': '騎乘'}
pets = {'DKBO2': [mount, u(2, '35/7/3/8'), u(3, '36/7/3/8', img_species='克邦凱斯'), u(4, '34/7/4/8')],
        'DKBO3': [mount, u(2, '33/7/3/8'), u(3, '32/7/3/8', img_species='邦恩吉')],            # 縮圖有把握認成別的 → 矛盾
        'DKBO4': [mount, u(2, '30/8/3/8', species='加格', species_src='img')],
        'DKBO5': [mount, u(2, '35/7/3/8'), u(3, '31/8/2/8')]}                                   # 35/7/3/8 跟 DKBO2 撞號
todo, bad = pet_catch.plan_register(SH, pets, {'49/9/8/2': '布拉奇多斯'})
check('plan_register：依抓寵者登錄（騎寵已登錄別種略過）',
      todo == {'36/7/3/8': ('克邦凱斯', 'DKBO2'), '34/7/4/8': ('克邦凱斯', 'DKBO2'), '33/7/3/8': ('加克拉', 'DKBO3'),
               '30/8/3/8': ('加格', 'DKBO4'), '31/8/2/8': ('邦恩吉', 'DKBO5')}, str(todo))
check('plan_register：縮圖有把握是別種 → 矛盾不登錄；兩人同字串不同種 → 都不登錄',
      ('DKBO3', 3, '32/7/3/8', '邦恩吉', '加克拉') in bad and any(b[0] == 'DKBO5' and b[2] == '35/7/3/8' for b in bad) and '35/7/3/8' not in todo, str(bad))
todo, bad = pet_catch.plan_register(SH[:1], {'DKBO2': [u(2, '1/2/3/4')]}, {'1/2/3/4': '加格'})
check('plan_register：字串已登錄成別種（以前分來的）→ 不是這次抓的，略過', todo == {} and bad == [])


class FR:
    def __init__(self, pets):
        self.pets, self.args = pets, None

    def pets_list(self, roles, img_only=None):
        self.args = (list(roles), img_only)
        return 0, {r: self.pets.get(r, []) for r in roles}


reg = {'thumb': {}, 'growth': {'49/9/8/2': '布拉奇多斯'}}
petmatch.load_species = lambda: reg
petmatch.TPL_DIR = Path(tempfile.mkdtemp())
fr = FR(pets)
rc = pet_catch.register_catches(SH, fr)
check('register_catches：有矛盾 → 15，其餘照登錄（登錄檔 + 來源檔）', rc == pet_catch.EXIT_CATCH_SPECIES and reg['growth'].get('33/7/3/8') == '加克拉'
      and reg['growth'].get('31/8/2/8') == '邦恩吉' and '32/7/3/8' not in reg['growth'] and pet_catch.load_src()['33/7/3/8']['catcher'] == 'DKBO3', str(reg['growth']))
check('register_catches：寵物面板只讀一次、候選 = 本次 4 種', fr.args == (['DKBO2', 'DKBO3', 'DKBO4', 'DKBO5'], ['克邦凱斯', '加克拉', '加格', '邦恩吉']))
fr = FR({'DKBO2': [u(2, '40/7/3/8')]})
check('register_catches：沒有矛盾 → 0', pet_catch.register_catches(SH[:1], fr) == 0 and reg['growth']['40/7/3/8'] == '克邦凱斯')
f3 = FT3({}, polls=[{'DKBO2': (0, False)}])
f3.pets_list = lambda roles, img_only=None: (0, {'DKBO2': [u(2, '41/7/3/8')]})
check('run 預設階段含 register（wait 完接著登錄）', pet_catch.run(A[:1], stages=('wait', 'register'), tools=f3) == 0 and reg['growth']['41/7/3/8'] == '克邦凱斯')
print('\n失敗 %d' % fails if fails else '\n全部通過')
sys.exit(1 if fails else 0)
