#!/usr/bin/env python3
"""rebirth_pets.py 離線測試：假 Tools（只模擬「動作的語意」：寵物欄 / 倉庫 / 誘餌 / 外掛鎖定），不碰遊戲。
用法：uv run --no-project python tools/gui/test_rebirth_pets.py"""
import contextlib
import io
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import testenv  # noqa: E402,F401  紀錄檔轉向暫存（不污染真 actions.log / quest-events.log / errlog）
import errlog  # noqa: E402
import rebirth_pets as rp  # noqa: E402
import uikit  # noqa: E402

errlog.LOG = Path(tempfile.mkdtemp()) / 'errlog.jsonl'
TMP = Path(tempfile.mkdtemp())
rp.PROGRESS, rp.EVENT_LOG, rp.QUEST_LOG = TMP / 'prog.json', TMP / 'events.log', TMP / 'quest-log.md'
fails = 0
BRA, DOR = '布拉奇多斯', '朵拉比斯'
ROLES = rp.ALL_ROLES


def check(name, cond, extra=''):
    global fails
    print(('PASS' if cond else 'FAIL'), name, extra)
    if not cond:
        fails += 1


def quiet(fn, *a, **k):
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
        rc = fn(*a, **k)
    return rc, buf.getvalue()


# ---------------- 純函式 ----------------
check('退出碼 100～109 不重複、不與 pet 70～78 / bag 90～96 衝突', len({rp.EXIT_PRE, rp.EXIT_BOX, rp.EXIT_STORE, rp.EXIT_CATCH, rp.EXIT_DIST, rp.EXIT_RIDE, rp.EXIT_BATTLE, rp.EXIT_LOCK, rp.EXIT_CLEAN, rp.EXIT_ARGS}) == 10
      and min(rp.EXIT_PRE, rp.EXIT_ARGS) == 100 and rp.EXIT_ARGS == 109)
check('box_names：1 轉 → 1轉新手禮盒 / 2轉新手禮盒', rp.box_names(1) == ('1轉新手禮盒', '2轉新手禮盒') and rp.box_names(3)[0] == '3轉新手禮盒')
check('family_for：布拉奇多斯 → 雷龍系；其他物種要 --family', rp.family_for(BRA, None) == '雷龍系' and rp.family_for('魯尼帖斯', None) is None and rp.family_for('魯尼帖斯', '呼拔拔系') == '呼拔拔系')
check('parse_growth_line：整行才算', rp.parse_growth_line('49/9/8/2') == '49/9/8/2' and rp.parse_growth_line(' 47 / 10/7/1 ') == '47/10/7/1'
      and rp.parse_growth_line('49/9/8/2 +') is None and rp.parse_growth_line('朵拉比斯') is None)
rows = [('朵拉比斯', 1100, 400), ('49/9/8/2', 1100, 442), ('49/9/7/2', 1100, 484)]
check('pick_row：成長字串剛好 1 列 → 該列座標', rp.pick_row(rows, ('growth', '49/9/7/2'))[0] == ('49/9/7/2', 1100, 484))
check('pick_row：名字走 snap_pet；沒有 / 重複 → None（不猜）', rp.pick_row(rows, ('name', DOR))[0] == ('朵拉比斯', 1100, 400)
      and rp.pick_row(rows, ('growth', '1/1/1/1'))[0] is None and rp.pick_row(rows + [('49/9/7/2', 1100, 526)], ('growth', '49/9/7/2'))[0] is None
      and rp.pick_row([], ('name', DOR))[0] is None)
check('parse_count：可抓捕數 5', rp.parse_count('自動抓寵自動存倉庫可抓捕數：5+') == 5 and rp.parse_count('自動抓寵') is None)


def S(n, **k):
    return dict({'slot': n, 'empty': False, 'name': None, 'state': '等待', 'mountlike': False}, **k)


E = lambda n: {'slot': n, 'empty': True}    # noqa: E731
bar = [S(1, name='瑪斯貝卡', state='騎乘', mountlike=True), S(2, name='迪基格斯', state='出戰'), S(3, unnamed='1/2/3/4', raw_name='?(1/2/3/4)'), E(4), E(5)]
check('store 段已拿掉：STAGES 沒有 store、stores_for 不存在', 'store' not in rp.STAGES and not hasattr(rp, 'stores_for'))
check('new_unnamed：前一次空格、這次有沒名字 → 新增', [s['slot'] for s in rp.new_unnamed([S(1, name='x'), E(2), E(3)], [S(1, name='x'), S(2, unnamed='1/1/1/1'), E(3)])] == [2]
      and rp.new_unnamed([S(1, name='x'), E(2)], [S(1, name='x'), S(2, name='y')]) == [])
check('role_ident：騎寵 = 沒名字 → growth；戰寵 = name；找不到 / 兩隻 → None',
      rp.role_ident([S(1, unnamed='49/9/8/2', species=BRA), S(2, name=DOR)], BRA, DOR, '騎寵') == ('growth', '49/9/8/2')
      and rp.role_ident([S(1, unnamed='49/9/8/2', species=BRA), S(2, name=DOR)], BRA, DOR, '戰寵') == ('name', DOR)
      and rp.role_ident([S(1, name=DOR)], BRA, DOR, '騎寵') is None
      and rp.role_ident([S(1, unnamed='1/1/1/1', species=BRA), S(2, unnamed='2/2/2/2', species=BRA)], BRA, DOR, '騎寵') is None)
check('catch 不碰紅區：程式碼沒有點「+」1295,315 / 丟棄區座標', all('1295' not in str(v) for v in rp.CATCH_XY.values()))


# 名字為主（2026-10-14）：新寵物（有沒有名字都算）、進度檔成長字串、鎖定下拉找不到物種名才退回成長字串（待實機確認）
_b = [S(1, name='布拉奇多斯', state='騎乘'), E(2), E(3)]
_a = [S(1, name='布拉奇多斯', state='騎乘'), S(2, name='布拉奇多斯'), S(3, unnamed='1/2/3/4')]
check('new_pets：前一次空格、這次有（有名字 / 成長字串都算）', [x['slot'] for x in rp.new_pets(_b, _a)] == [2, 3] and [x['slot'] for x in rp.new_unnamed(_b, _a)] == [3])
check('known_growths：攤平去重', rp.known_growths({'data': {'growths': {'DKBO2': ['1/2/3/4', '5/6/7/8', '1/2/3/4']}}}) == ['1/2/3/4', '5/6/7/8'] and rp.known_growths({}) == [])
_rows = [('朵拉比斯', 1000, 400), ('49/9/8/2', 1000, 442)]
check('pick_row 名字找不到 → 退回備援成長字串（剛好一列）', rp.pick_row(_rows, ('name', '布拉奇多斯', (), ('49/9/8/2', '48/9/7/1')))[0] == ('49/9/8/2', 1000, 442))
check('pick_row 名字找得到 → 用名字（不看成長字串）', rp.pick_row([('布拉奇多斯', 1000, 400), ('49/9/8/2', 1000, 442)], ('name', '布拉奇多斯', (), ('49/9/8/2',)))[0][2] == 400)
check('pick_row 名字找不到、成長字串兩列都吻合 → 不選', rp.pick_row([('49/9/8/2', 1, 400), ('48/9/7/1', 1, 442)], ('name', '布拉奇多斯', (), ('49/9/8/2', '48/9/7/1')))[0] is None)
check('pick_row 沒有備援 → 跟以前一樣只比名字', rp.pick_row(_rows, ('name', '布拉奇多斯'))[0] is None)
check('role_ident：騎寵有名字 + 備援字串 → (name, 物種, (), 字串)；沒備援 → (name, 物種)',
      rp.role_ident(_a, '布拉奇多斯', '朵拉比斯', '騎寵', ('9/9/9/9',)) is None
      and rp.role_ident(_a[:2], '布拉奇多斯', '朵拉比斯', '騎寵', ('9/9/9/9',)) is None
      and rp.role_ident([S(1, name='布拉奇多斯', state='騎乘')], '布拉奇多斯', '朵拉比斯', '騎寵', ('9/9/9/9',)) == ('name', '布拉奇多斯', (), ('9/9/9/9',))
      and rp.role_ident([S(1, name='布拉奇多斯', state='騎乘')], '布拉奇多斯', '朵拉比斯', '騎寵') == ('name', '布拉奇多斯'))

# ---------------- 假 Tools ----------------
class Fake:
    def __init__(self, store_mount_ok=True):
        self.calls = []
        self.cur = 'DKBO'
        self.team = True
        self.locks = {r: {'騎寵': True, '戰寵': True} for r in ROLES}
        self.lock_ident = {}
        self.bar = {r: [None, None, None, None, None] for r in ROLES}      # 2026-10-16 起從空寵物欄開始（舊寵物已由 rebirth.py storepets 全存）
        self.depot = {r: {'personal': [DOR], 'public': []} for r in ROLES}
        shared = []
        for r in ROLES:
            self.depot[r]['public'] = shared               # 公共倉庫全帳號共用
        self.pub_baits = 0
        self.bag_baits = {r: 0 for r in ROLES}
        self.boxes = {r: 1 for r in ROLES}
        self.catching = None
        self.fail = {}                    # 方法名 → rc
        self.catch_extra = 0              # 試抓時多抓幾隻（測 103）
        self.catch_noreg = False
        self.registered = False
        self.n_catch = 0
        self.growths = ['49/9/8/2', '49/9/7/2', '48/9/7/1', '47/10/7/1', '45/10/8/1']
        self.snaps = []
        self.scan72 = False               # take_many 取戰寵回 72（倉庫同名多隻、等級讀不出）→ 走逐隻取出驗 Lv1
        self.scan_rc = 0
        self.stone = 3000000
        self.diamond = 0
        self.count = 0                    # 外掛可抓捕數
        self.press_fail = 0
        self.img = False

    def c(self, *a):
        self.calls.append(a)

    def f(self, name):
        return self.fail.get(name, 0)

    # --- 基本 ---
    def sleep(self, s):
        pass

    def grind_go(self, trans):
        self.c('grind_go', trans)
        return self.f('grind_go')

    def preflight(self):
        self.c('preflight')
        return self.f('preflight')

    def current(self):
        self.c('current')
        return 0, self.cur

    def char_ensure(self, n):
        self.c('char_ensure', n)
        self.cur = n
        return self.f('char_ensure')

    def team_disband(self):
        self.c('disband')
        self.team = False
        return self.f('disband')

    def encounter_on(self):
        return False

    def snap(self, tag):
        self.snaps.append(tag)

    # --- 外掛 ---
    def lock_get(self, r):
        self.c('lock_get', r)
        return 0, dict(self.locks[r])

    def lock_set(self, r, w, on, ident=None):
        self.c('lock_set', r, w, on, ident)
        if self.f('lock_set'):
            return self.f('lock_set')
        self.locks[r][w] = on
        self.lock_ident[(r, w)] = ident
        return 0

    def lock_get_many(self, roles):
        self.c('ass_open', tuple(roles))                 # 批次：外掛面板只開一次
        out = {}
        for r in roles:
            rc, st = self.lock_get(r)
            if rc:
                return rc, out
            out[r] = st
        return 0, out

    def lock_set_many(self, items):
        self.c('ass_open', tuple(dict.fromkeys(r for r, *_ in items)))
        for r, w, on, ident in items:
            rc = self.lock_set(r, w, on, ident)
            if rc:
                return rc, r
        return 0, None

    def pet_set_state_many(self, roles, name, state, allow_mount=False):
        self.c('pet_open', tuple(roles))
        for r in roles:
            rc = self.pet_set_state(r, name, state, allow_mount)
            if rc:
                return rc, r
        return 0, None

    # --- 寵物 ---
    def view(self, r):
        out = []
        for i, p in enumerate(self.bar[r]):
            if p is None:
                out.append(E(i + 1))
                continue
            d = S(i + 1, state=p['state'])
            if p.get('unnamed'):
                reg_species = p.get('species') if self.registered else None
                d.update(unnamed=p['unnamed'], raw_name=f'?({p["unnamed"]})', species=reg_species, mountlike=reg_species == BRA)
                if self.img:
                    d.update(img_species=p.get('species'), img_score=0.95)      # 縮圖比對（直接抓流程要靠它登錄物種）
            else:
                d.update(name=p['name'], mountlike=p['name'] in uikit.MOUNTS)
            out.append(d)
        return out

    def pets_list(self, roles):
        self.c('pets_list', tuple(roles))
        return self.f('pets_list'), {r: self.view(r) for r in roles}

    def pet_set_state(self, r, name, state, allow_mount=False):
        self.c('set_state', r, name, state, allow_mount)
        if self.f('set_state'):
            return self.f('set_state')
        hit = [p for p in self.bar[r] if p and (p.get('name') == name or (p.get('unnamed') and p.get('species') == name))]
        if not hit:
            return 72
        p = hit[0]
        if (name in uikit.MOUNTS or state == '騎乘') and not allow_mount:
            return 73
        if state == '騎乘':
            for q in self.bar[r]:
                if q and q['state'] == '騎乘':
                    q['state'] = '等待'
        p['state'] = state
        return 0

    def _match(self, p, name):
        return p.get('name') == name or (p.get('unnamed') and p.get('species') == name and self.registered)

    def pet_store_many(self, roles, pets, depot, allow_slot1=False, allow_mount_store=None, pick=None):
        self.c('store_many', tuple(roles), tuple(pets), depot, tuple(allow_mount_store or []), pick)
        if self.f('store_many'):
            return self.f('store_many'), {}
        for r in roles:
            for nm in pets:
                if (nm in uikit.MOUNTS) and nm not in (allow_mount_store or []):
                    return 73, {'msg': '騎寵不在名單'}
                hits = [i for i, p in enumerate(self.bar[r]) if p and self._match(p, nm)]
                if not hits:
                    return 72, {'msg': f'{r} 沒有 {nm}'}
                if len(hits) > 1 and pick is None:
                    return 72, {'msg': '同名多隻'}
                i = hits[-1] if pick == 'last' else hits[0]
                p = self.bar[r][i]
                if (nm in uikit.MOUNTS) and p['state'] != '等待':
                    return 73, {'msg': f'{nm} 不是等待'}
                self.depot[r][depot].append(p.get('name') or nm)
                if p.get('unnamed'):
                    self.depot[r][depot][-1] = {'unnamed': p['unnamed'], 'species': p['species']}
                self.bar[r][i] = None
                self.bar[r] = [x for x in self.bar[r] if x] + [None] * (5 - len([x for x in self.bar[r] if x]))
        return 0, {}

    def pet_take_many(self, roles, pets, depot):
        self.c('take_many', tuple(roles), tuple(pets), depot)
        if self.f('take_many'):
            return self.f('take_many'), {}
        for r in roles:
            for nm in pets:
                nm = nm.split('@')[0]                          # 「名字@等級」目標：假倉庫沒有等級，只比名字
                if nm == DOR and self.scan72:
                    return 72, {'msg': '同名多隻、卡片等級讀不出'}
                dep = self.depot[r][depot]
                hit = next((k for k, c in enumerate(dep) if (c == nm) or (isinstance(c, dict) and c.get('species') == nm)), None)
                if hit is None:
                    return 72, {'msg': f'{depot} 沒有 {nm}'}
                c = dep.pop(hit)
                j = self.bar[r].index(None)
                self.bar[r][j] = ({'name': c, 'state': '等待'} if isinstance(c, str) else {'name': nm, 'unnamed': c['unnamed'], 'species': c['species'], 'state': '等待'})
        return 0, {}

    def pet_take_lv1_scan(self, r, name):
        self.c('lv1_scan', r, name)
        if self.scan_rc:
            return self.scan_rc, {'tried': [[1, self.scan_rc]]}
        dep = self.depot[r]['personal']
        if name not in dep:
            return 72, {'msg': f'{r} 倉庫沒有 {name}'}
        dep.remove(name)
        j = self.bar[r].index(None)
        self.bar[r][j] = {'name': name, 'state': '等待'}
        return 0, {'tried': [[1, 0]]}

    def money(self):
        self.c('money')
        return self.stone, self.diamond

    def press_plus(self, r, limit=None):
        self.c('press_plus', r, limit)
        if self.press_fail:
            return self.press_fail, self.count, None
        if limit is not None and self.count >= limit:
            return 0, self.count, self.count
        before = self.count
        self.count += 1
        self.stone -= 50000
        return 0, before, self.count

    def reset_names(self, roles):
        """還原名字（pet.reset_soft 的假版）：沒名字的寵物 → 物種名。rename_rc = 67 / 9 → 原樣回；rename_soft = 66 → 不改、rc 0 + soft_rc"""
        self.c('reset_names', tuple(roles))
        rr = getattr(self, 'rename_rc', 0)
        if rr:
            return rr, {}
        soft = getattr(self, 'rename_soft', 0)
        if soft:
            return 0, {'soft_rc': soft, 'renamed': {}, 'msg': '看不到鉛筆鈕'}
        out = {}
        for r in roles:
            for p in self.bar[r]:
                if p and p.get('unnamed'):
                    out.setdefault(r, []).append(p.pop('unnamed'))
                    p['name'] = p.get('species') or p.get('name')
        return 0, {'renamed': out}

    def learn_species(self, r, slot, species, growth):
        self.c('learn_species', r, slot, species, growth)
        if self.f('learn_species'):
            return self.f('learn_species')
        self.registered = True
        return 0

    # --- 背包 / 禮盒 / 誘餌 ---
    def quiet(self):
        self.c('quiet')
        return self.f('quiet')

    def boxes_many(self, roles, trans, states, save):
        for r in roles:
            if states.get(r, {}).get('step') == 'done':
                continue
            self.c('box_open', r, trans)
            if self.f('box_open'):
                return self.f('box_open'), r
            if self.boxes[r]:
                self.boxes[r] = 0
                self.pub_baits += 10
                states[r] = {'step': 'done', 'stored': [[0, '寵物誘餌']]}
            else:
                states[r] = {'step': 'done', 'skipped': 'x'}
            save()
        return 0, None

    def bait_take(self, r, keep):
        self.c('bait_take', r, keep)
        if self.f('bait_take'):
            return self.f('bait_take')
        self.bag_baits[r] = keep
        return 0

    def bait_return(self, r):
        self.c('bait_return', r)
        self.pub_baits += self.bag_baits[r]
        self.bag_baits[r] = 0
        return self.f('bait_return')

    # --- 捉寵 ---
    def catch_setup(self, r, fam, sp, k):
        self.c('catch_setup', r, fam, sp, k)
        return self.f('catch_setup')

    def catch_start(self, r, k):
        self.c('catch_start', r, k)
        self.catching = (r, k)
        return self.f('catch_start')

    def catch_wait(self, r, timeout=0):
        self.c('catch_wait', r)
        if self.f('catch_wait'):
            return self.f('catch_wait'), 3
        rr, k = self.catching
        k2 = k + (self.catch_extra if k == 1 else 0)
        for _ in range(k2):
            j = self.bar[rr].index(None)
            g = self.growths[self.n_catch % 5]
            self.n_catch += 1
            self.bar[rr][j] = {'name': BRA, 'unnamed': g, 'species': BRA, 'state': '等待'}
        self.bag_baits[rr] = 0
        return 0, 0


def mkopts(**kw):
    return dict(mount_species=BRA, battle_pet=DOR, catcher='DKBO2', count=5, **kw)


def go(fake, **kw):
    kw = dict(mkopts(), **kw)
    kw.setdefault('from_stage', 'preflight')
    rp.PROGRESS.unlink(missing_ok=True) if kw['from_stage'] == 'preflight' else None
    return quiet(rp.run, 1, tools=fake, **kw)


# ---------------- 去練功（2026-10-15）----------------
f = Fake()
rc, out = go(f, no_grind=True)
check('--no-grind：完成後不去練功', rc == 0 and not any(c[0] == 'grind_go' for c in f.calls))
f = Fake()
rc, out = go(f, to_stage='lock')
check('--to lock（沒跑到 cleanup）→ 不去練功', rc == 0 and not any(c[0] == 'grind_go' for c in f.calls))
f = Fake()
f.fail['grind_go'] = 55
rc, out = go(f)
check('去練功失敗 → 回 grind 的碼（55）、寵物重整仍記完成', rc == 55 and rp.LAST['done'] == rp.STAGES and rp.LAST.get('grind_rc') == 55, f'rc={rc}')
f = Fake()
rc, out = go(f, dry_run=True)
check('--dry-run 計畫列出去練功（grind.go）', 'grind.go' in out and not f.calls)
_run0, _kw = rp.run, {}
rp.run = lambda *a, **k: _kw.update(k) or 0
quiet(rp.main, ['--no-grind'])
rp.run = _run0
check('CLI --no-grind 帶入 run', _kw.get('no_grind') is True, str(_kw))

# ---------------- dry-run / 參數 ----------------
f = Fake()
rc, out = go(f, dry_run=True)
check('--dry-run：rc 0、完全沒呼叫 Tools、印出全部階段', rc == 0 and f.calls == [] and all(s in out for s in rp.STAGES), out[-200:])
check('--dry-run 的計畫沒有 store 段、有雷龍系', '[store]' not in out and '雷龍系' in out)
f = Fake()
check('參數：catcher 不認得 / count 超範圍 / 騎寵名不在 Monster 表 / --from 在 --to 後 → 109 且零呼叫',
      all(go(Fake(), **kw)[0] == 109 for kw in ({'catcher': 'XYZ'}, {'count': 9}, {'mount_species': '亂碼寵'}, {'from_stage': 'lock', 'to_stage': 'catch'})))

# ---------------- 完整流程 ----------------
f = Fake()
rc, out = go(f)
names_of = lambda r: [(p['name'] if not p.get('unnamed') else '?' + p['unnamed'], p['state']) for p in f.bar[r] if p]    # noqa: E731
check('完整流程 rc 0、9 階段都完成', rc == 0 and rp.LAST['done'] == rp.STAGES, f'rc={rc} {out[-400:]}')
check('全部完成 → 最後去練功 grind_go（轉數提示 = --trans 1），不帶固定點', f.calls[-1] == ('grind_go', 1) and rp.LAST.get('grind_rc') == 0, str(f.calls[-3:]))
check('結果（名字為主）：5 人寵物欄 = 布拉奇多斯（已還原名字，騎乘）+ 朵拉比斯（出戰）', all(names_of(r) == [(BRA, '騎乘'), (DOR, '出戰')] for r in ROLES), str({r: names_of(r) for r in ROLES}))
G5 = tuple(rp.load_progress()['data']['growths']['DKBO2'])
check('進度檔記 5 隻還原名字前的成長字串（各不相同；鎖定下拉備援用）', len(set(G5)) == 5 and set(G5) == set(f.growths), str(G5))
check('外掛：5 人鎖定騎寵（物種名，找不到退回成長字串）與戰寵（名字）最後都勾、ident 正確',
      all(f.locks[r] == {'騎寵': True, '戰寵': True} and f.lock_ident[(r, '騎寵')] == ('name', BRA, (), G5) and f.lock_ident[(r, '戰寵')] == ('name', DOR) for r in ROLES),
      str(f.lock_ident.get(('DKBO', '騎寵'))))
ci = lambda name: [i for i, c in enumerate(f.calls) if c[0] == name]    # noqa: E731
check('順序：preflight < 禮盒 < 抓寵 < distribute < ride < battle < lock < cleanup（沒有 store 段）',
      ci('disband')[0] < ci('box_open')[0] < ci('catch_setup')[0] < [i for i, c in enumerate(f.calls) if c[0] == 'store_many' and c[3] == 'public'][0]
      < [i for i, c in enumerate(f.calls) if c[0] == 'set_state' and c[3] == '騎乘'][0] < [i for i, c in enumerate(f.calls) if c[0] == 'take_many' and c[3] == 'personal'][0]
      < [i for i, c in enumerate(f.calls) if c[0] == 'lock_set' and c[3]][0] < ci('bait_return')[-1])
check('preflight：外掛解鎖先於存倉（5 人 × 2 項）、解散隊伍', len([c for c in f.calls if c[0] == 'lock_set' and c[3] is False]) == 10 and ci('disband'))
check('抓寵：先試 1（誘餌留 1、可抓捕數 1）、還原名字、再 4、再還原名字；名字對 → 不學物種（learn-species 只當備援）',
      [c[1:] for c in f.calls if c[0] == 'catch_setup'] == [('DKBO2', '雷龍系', BRA, 1), ('DKBO2', '雷龍系', BRA, 4)]
      and [c[2] for c in f.calls if c[0] == 'bait_take'] == [1, 4] and [c[1] for c in f.calls if c[0] == 'reset_names'] == [('DKBO2',), ('DKBO2',)]
      and not ci('learn_species') and ci('catch_wait')[0] < ci('reset_names')[0] < ci('catch_setup')[1])
check('沒有 store 段：不存個人倉庫、不設等待', not any(c[0] == 'store_many' and c[3] == 'personal' for c in f.calls) and not any(c[0] == 'set_state' and c[3] == '等待' for c in f.calls))
check('分配：catcher 存 4 隻進公共（取最後格 pick=last、旗標只放行布拉奇多斯）、其他 4 人各取 1',
      ('store_many', ('DKBO2',), (BRA,) * 4, 'public', (BRA,), 'last') in f.calls and ('take_many', ('DKBO', 'DKBO3', 'DKBO4', 'DKBO5'), (BRA,), 'public') in f.calls)
check('戰寵：5 人從個人倉庫取朵拉比斯、設出戰（不帶 allow_mount）', ('take_many', tuple(ROLES), (DOR + '@1',), 'personal') in f.calls and all(('set_state', r, DOR, '出戰', False) in f.calls for r in ROLES))
check('誘餌：公共 = 禮盒 50 個（沒有花石幣），catcher 背包最後 0 個', f.pub_baits == 50 and f.bag_baits['DKBO2'] == 0)
check('收尾：當前 DKBO、quest-log 有寫', f.cur == 'DKBO' and '轉生後寵物重整' in rp.QUEST_LOG.read_text(encoding='utf-8'))
check('騎寵保護：所有 store_many 呼叫中，騎寵名只在 allow 名單內', all(set(c[2]) & set(uikit.MOUNTS) <= set(c[4]) for c in f.calls if c[0] == 'store_many'))

# ---------------- --store-mount 已無作用 ----------------
f = Fake()
rc, out = go(f, store_mount='瑪斯貝卡')
check('--store-mount：只印提示、rc 0、不存倉不設等待（沒有 store 段）', rc == 0 and '已無作用' in out and not any(c[0] == 'set_state' and c[3] == '等待' for c in f.calls) and 'store' not in rp.LAST['done'], f'rc={rc}')
f = Fake()
rc, _ = go(f, to_stage='store')
check('舊的 --to store → 改到 boxes', rc == 0 and rp.LAST['done'] == ['preflight', 'boxes'], str(rp.LAST.get('done')))

# ---------------- 失敗路徑 ----------------
f = Fake()
f.cur = 'DKBO3'
rc, out = go(f, to_stage='preflight')
check('當前不是 DKBO → char.ensure DKBO 後繼續', rc == 0 and ('char_ensure', 'DKBO') in f.calls)
f = Fake()
f.fail['char_ensure'] = 62
f.cur = 'DKBO3'
check('切不回 DKBO → 100，沒解散、沒碰外掛', go(f)[0] == 100 and not ci('disband') and not ci('lock_set'))
f = Fake()
f.fail['disband'] = 45
check('解散失敗 → 100', go(f)[0] == 100 and not ci('lock_set'))
f = Fake()
f.fail['lock_set'] = 4
check('外掛取消鎖定失敗 → 100、沒進存倉', go(f)[0] == 100 and not ci('store_many'))
f = Fake()
f.fail['box_open'] = 95
check('禮盒失敗 → 101', go(f)[0] == 101 and not ci('store_many'))
f = Fake()
f.fail['store_many'] = 76
check('pet_store_many 失敗（現在只剩 distribute 用）→ 104、info 有 pet_rc', go(f)[0] == 104 and rp.LAST.get('pet_rc') == 76)
f = Fake()
f.fail['bait_take'] = 95
check('取誘餌失敗 → 103、沒設外掛', go(f)[0] == 103 and not ci('catch_setup'))
f = Fake()
f.fail['catch_setup'] = 4
check('外掛捉寵設置失敗 → 103、沒勾自動抓寵', go(f)[0] == 103 and not ci('catch_start'))
f = Fake()
f.fail['catch_wait'] = 103
check('抓寵逾時 → 103，之後階段沒跑', go(f)[0] == 103 and not any(c[0] == 'store_many' and c[3] == 'public' for c in f.calls))
f = Fake()
f.catch_extra = 1
rc, out = go(f)
check('試抓 1 隻卻多出 2 隻沒名字 → 103、沒登錄物種', rc == 103 and not ci('learn_species'), f'rc={rc}')
f = Fake()
f.rename_soft = 66
f.fail['learn_species'] = 72
check('還原名字失敗（備援）+ 登錄物種失敗 → 103、沒繼續抓 4 隻', go(f)[0] == 103 and len(ci('catch_setup')) == 1)
f = Fake()
f.rename_soft = 66
rc, out = go(f)
check('還原名字一般失敗（66）→ 記事件、走 learn-species 備援（試抓那隻學 1 次）、照常跑完；騎寵仍是成長字串、鎖定用成長字串',
      rc == 0 and len(ci('learn_species')) == 1 and all(names_of(r)[0][0].startswith('?') for r in ROLES)
      and all(f.lock_ident[(r, '騎寵')][0] == 'growth' for r in ROLES) and '還原名字沒全部成功' in rp.EVENT_LOG.read_text(encoding='utf-8'), f'rc={rc}')
f = Fake()
f.rename_rc = 67
rc, out = go(f)
check('還原名字讀到費用字樣（67）→ 103 停手、沒繼續抓 4 隻、沒分配', rc == 103 and len(ci('catch_setup')) == 1 and rp.LAST.get('pet_rc') == 67
      and '鐵則 3' in rp.LAST.get('msg', '') and not any(c[0] == 'store_many' and c[3] == 'public' for c in f.calls), f'rc={rc} {rp.LAST.get("msg")}')
f = Fake()
f.rename_rc = 9
check('還原名字遇驗證視窗（9）→ 透傳 9', go(f)[0] == 9)
f = Fake()
orig_cw = f.catch_wait


def _cw_wrong(r, timeout=0, _o=orig_cw, _f=f):
    rc_, left = _o(r, timeout)
    for q in _f.bar[r]:
        if q and q.get('unnamed'):
            q['species'] = '迪基格斯'                                  # 還原後名字是別的物種
    return rc_, left


f.catch_wait = _cw_wrong
check('試抓新寵物還原後名字是別的物種 → 103、不學物種', go(f)[0] == 103 and not ci('learn_species') and len(ci('catch_setup')) == 1)
f = Fake()
f.fail['take_many'] = 72
check('分配取不到 → 104（或戰寵取不到 106）；先到的是 distribute', go(f)[0] == 104)
f = Fake()
orig = f.pet_set_state
f.pet_set_state = lambda r, name, state, allow_mount=False: (105 if state == '騎乘' else orig(r, name, state, allow_mount))
check('設騎乘失敗 → 105', go(f)[0] == 105)
f = Fake()
f.depot['DKBO3']['personal'] = []
rc, out = go(f)
check('個人倉庫沒有戰寵 → 106', rc == 106 or rc == 104, f'rc={rc}')
f = Fake()
orig_l = f.lock_set
f.lock_set = lambda r, w, on, ident=None: 7 if on else orig_l(r, w, on, ident)
check('鎖定 OCR 找不到選項 → 107', go(f)[0] == 107)

# ---------------- --from 續跑 ----------------
f = Fake()
rc, _ = go(f, to_stage='catch')
check('--to catch：跑到抓寵就停（進度檔有 3 個階段）', rc == 0 and rp.LAST['done'] == ['preflight', 'boxes', 'catch'])
n0 = len(f.calls)
rc, _ = go(f, from_stage='distribute')
check('--from distribute 接著跑完：rc 0、沒有重做 preflight / 禮盒 / 存倉 / 抓寵', rc == 0 and rp.LAST['done'][-1] == 'cleanup'
      and not [c for c in f.calls[n0:] if c[0] in ('disband', 'box_open', 'catch_setup', 'bait_take')], str(rp.LAST['done']))
f2 = Fake()
rp.PROGRESS.unlink(missing_ok=True)
check('進度檔沒有前置階段就 --from lock → 109、零呼叫', go(f2, from_stage='lock')[0] == 109 and f2.calls == [])
f = Fake()
rc, _ = go(f, no_boxes=True)
check('--no-boxes：不開禮盒、其餘照跑、誘餌 0 → 取誘餌由 bag 失敗之外的路徑（假 Tools 照給）', not ci('box_open') and rc == 0)

# ---------------- 2026-10-12：外掛批次（面板只開一次）+ 鎖定下拉讀字選（D，errlog #257）----------------
import ass  # noqa: E402
check('role_ident：騎寵物種沒登錄 → 用騎乘中的那隻（成長字串）；騎乘中 0 隻 → None',
      rp.role_ident([S(1, unnamed='49/9/8/2', species=None, state='騎乘'), S(2, name=DOR, state='出戰')], BRA, DOR, '騎寵') == ('growth', '49/9/8/2')
      and rp.role_ident([S(1, unnamed='49/9/8/2', species=None, state='等待')], BRA, DOR, '騎寵') is None)
check('lock_items：5 人 × 2 項、騎寵用成長字串 / 戰寵用名字；找不到唯一一隻 → 訊息',
      rp.lock_items({'DKBO': [S(1, unnamed='49/9/8/2', species=BRA, state='騎乘'), S(2, name=DOR, state='出戰')]}, ['DKBO'], BRA, DOR)[0]
      == [('DKBO', '騎寵', True, ('growth', '49/9/8/2')), ('DKBO', '戰寵', True, ('name', DOR))]
      and rp.lock_items({'DKBO': [S(1, name=DOR), S(2, name=DOR)]}, ['DKBO'], BRA, DOR)[1] != '')


class FakeAss:
    """假外掛面板：每人的鎖定下拉列順序不同（DKBO3 朵拉比斯在上，#257）、欄位 / 勾選狀態；記錄點擊與開關次數"""
    def __init__(self):
        self.opens, self.closes, self.clicks, self.role = 0, 0, [], None
        self.order = {r: [('49/9/8/2', 'm'), (DOR, 'b')] for r in ROLES}
        self.order['DKBO3'] = [(DOR, 'b'), ('49/9/8/2', 'm')]
        self.field = {r: {'騎寵': '', '戰寵': ''} for r in ROLES}
        self.chk = {r: {'騎寵': False, '戰寵': False} for r in ROLES}
        self.dd = None

    def many(self, plan, visit, no_wait=False):
        self.opens += 1
        out, info = {}, {'secs': {}, 'changed': {}, 'role': None}
        try:
            for r in plan:
                self.role = r
                rc, st, msg, _ = visit(r)
                if rc:
                    info['role'] = r
                    return rc, out, msg, info
                out[r] = st
            return 0, out, '', info
        finally:
            self.closes += 1

    def ocr(self, box, *opts):
        x, y, w, h = box
        for which, xy in rp.LOCK_XY.items():
            dy = xy['dd'][1]
            if y == dy - 17:
                return [(self.field[self.role][which], 1100, dy)] if self.field[self.role][which] else []
            if y == dy + 22 and self.dd == which:
                return [(t, 1047, dy + 45 + 42 * k) for k, (t, _) in enumerate(self.order[self.role])]
        return []

    def gui(self, *a, note=''):
        for part in a[1].split(';') if a and a[0] == 'seq' else []:
            w = part.split()
            if w and w[0] == 'click':
                xy = (int(w[1]), int(w[2]))
                self.clicks.append((self.role, xy, note))
                for which, d in rp.LOCK_XY.items():
                    if xy == d['dd']:
                        self.dd = None if self.dd == which else which
                    elif xy == d['check']:
                        self.chk[self.role][which] = not self.chk[self.role][which]
                if self.dd and xy[0] == 1047:
                    dy = rp.LOCK_XY[self.dd]['dd'][1]
                    k = (xy[1] - dy - 45) // 42
                    self.field[self.role][self.dd] = self.order[self.role][k][0]
                    self.dd = None
        return ''


fa = FakeAss()
T = rp.Tools()
saved = (ass._many, ass.panel_open, rp.ocr_lines, uikit.gui, rp.Tools._ass_tab, rp.Tools._checked, ass.gui)
# ass.gui 是 walk.gui（真的 gui.ps1）：不換掉的話 ass.close_panel 會在真遊戲上點 1318,90（2026-10-14 實際點了 6 輪 × 4 下，打開地圖傳送面板）
ass._many, ass.panel_open, rp.ocr_lines, uikit.gui, ass.gui = fa.many, (lambda: True), fa.ocr, fa.gui, fa.gui
rp.Tools._ass_tab = lambda self, role, tab: 0
rp.Tools._checked = lambda self, xy: next(fa.chk[fa.role][w] for w, d in rp.LOCK_XY.items() if d['check'] == xy)
pets = {r: [S(1, unnamed='49/9/8/2', species=BRA, state='騎乘'), S(2, name=DOR, state='出戰')] for r in ROLES}
items, _ = rp.lock_items(pets, ROLES, BRA, DOR)
(rc, bad), _ = quiet(T.lock_set_many, items)
check('lock_set_many 5 人 × 2 項：rc 0、外掛面板只開 / 關 1 次（舊版每人每項各開關一次 = 10 次）', rc == 0 and fa.opens == 1 and fa.closes == 1, f'rc={rc} opens={fa.opens}')
check('  每人欄位都是對的（DKBO3 下拉順序相反也選對朵拉比斯 / 成長字串）、兩項都勾',
      all(fa.field[r] == {'騎寵': '49/9/8/2', '戰寵': DOR} and fa.chk[r] == {'騎寵': True, '戰寵': True} for r in ROLES), str(fa.field['DKBO3']))
n = len(fa.clicks)
(rc, bad), _ = quiet(T.lock_set_many, items)
check('  再跑一次：欄位已是目標、已勾 → 0 次點擊（不開下拉）', rc == 0 and len(fa.clicks) == n, str(fa.clicks[n:]))
fa.order['DKBO2'] = [('49/9/8/2', 'm')]
fa.field['DKBO2']['戰寵'] = ''
fa.chk['DKBO2']['戰寵'] = False
(rc, bad), _ = quiet(T.lock_set_many, [('DKBO2', '戰寵', True, ('name', DOR))])
check('  下拉讀不到目標 → 7、不選不勾、收下拉', rc == 7 and bad == 'DKBO2' and fa.chk['DKBO2']['戰寵'] is False and fa.dd is None, f'rc={rc} {bad}')
(rc, sts), _ = quiet(T.lock_get_many, ROLES)
check('lock_get_many：一次讀 5 人', rc == 0 and len(sts) == 5 and sts['DKBO']['戰寵'] is True)
ass._many, ass.panel_open, rp.ocr_lines, uikit.gui, rp.Tools._ass_tab, rp.Tools._checked, ass.gui = saved


# ---------------- 2026-10-13：--confirm-buy-catch / 戰寵逐隻驗 Lv1 / 禮盒 95 重試 ----------------
f = Fake()
f.img = True
rc, out = go(f, confirm_buy_catch=True)
buys = [c for c in f.calls if c[0] == 'press_plus']
check('--confirm-buy-catch：外掛「+」按到可抓捕數 = 5（5 次 +1 次確認已夠）、石幣少 250,000、鑽石不變', rc == 0 and f.count == 5 and f.stone == 3000000 - 250000 and f.diamond == 0 and len(buys) == 6, f'rc={rc} {len(buys)}')
cs = [c[1:] for c in f.calls if c[0] == 'catch_setup']
check('--confirm-buy-catch：直接抓 5（不取誘餌、不試抓）', cs == [('DKBO2', '雷龍系', BRA, 5)] and 'bait_take' not in [c[0] for c in f.calls], str(cs))
check('--confirm-buy-catch：買完才設外掛、順序 press_plus < catch_setup', [i for i, c in enumerate(f.calls) if c[0] == 'press_plus'][-1] < [c[0] for c in f.calls].index('catch_setup'))
f = Fake()
rc, out = go(f)
check('沒給旗標：不按「+」（舊行為，不花石幣）', 'press_plus' not in [c[0] for c in f.calls] and f.stone == 3000000)
f = Fake()
f.img = True
f.count = 3
rc, _ = go(f, confirm_buy_catch=True)
check('續跑：可抓捕數已有 3 → 只再按 2 次', rc == 0 and f.count == 5 and f.stone == 3000000 - 100000)
f = Fake()
f.img = True
f.stone = 120000
rc, _ = go(f, confirm_buy_catch=True)
check('石幣不讀、不擋（catchbuy 2026-10-15 使用者）：石幣看起來不夠也照按到 5', rc == 0 and f.count == 5, f'rc={rc} {f.count}')
f = Fake()
f.money = lambda: (None, None)
rc, _ = go(f, confirm_buy_catch=True)
check('按「+」前讀不到鑽石 → 103、一次都不按、不設外掛', rc == 103 and f.count == 0 and 'catch_setup' not in [c[0] for c in f.calls], f'rc={rc}')
f = Fake()
f.press_fail = 4
check('「+」失敗（讀不到可抓捕數）→ 103', go(f, confirm_buy_catch=True)[0] == 103)
f = Fake()
orig_press = f.press_plus
def _bad_press(r, limit=None):                                  # 按了但石幣沒扣 50,000（扣了別的 / 沒扣）
    rc_, b_, a_ = orig_press(r, limit)
    f.stone += 10000
    return rc_, b_, a_
f.press_plus = _bad_press
f.img = True
check('石幣扣多少不檢查（不讀石幣）→ 照買完', go(f, confirm_buy_catch=True)[0] == 0 and f.count == 5)
f = Fake()
orig_press = f.press_plus
def _dia_press(r, limit=None):
    rc_, b_, a_ = orig_press(r, limit)
    f.diamond -= 5
    return rc_, b_, a_
f.press_plus = _dia_press
check('鑽石有變 → 103 停手（鐵則 3）', go(f, confirm_buy_catch=True)[0] == 103 and f.count == 1)
f = Fake()
f.fail['preflight'] = 9
check('--confirm-buy-catch：preflight 9 透傳', go(f, confirm_buy_catch=True)[0] == 9)
rc, out = go(Fake(), dry_run=True, confirm_buy_catch=True)
check('--dry-run 計畫列出「+」花石幣，且零呼叫', rc == 0 and '花石幣買可抓捕數' in out and '50,000' in out)

# 戰寵逐隻驗 Lv1
f = Fake()
f.scan72 = True
rc, out = go(f)
check('取戰寵 take_many 回 72 → 5 人逐隻取出（pet_take_lv1_scan）→ 照樣設出戰完成', rc == 0 and [c[1] for c in f.calls if c[0] == 'lv1_scan'] == ROLES
      and all(any(p and p.get('name') == DOR and p['state'] == '出戰' for p in f.bar[r]) for r in ROLES), f'rc={rc}')
f = Fake()
f.scan72 = True
f.scan_rc = 76
rc, out = go(f)
check('逐隻驗 Lv1 全部不對（76）→ 106，沒設出戰', rc == 106 and not any(c[0] == 'set_state' and c[3] == '出戰' for c in f.calls))
check('scan_candidates：只取名字吻合且等級讀不出（@None）的格，排序', rp.scan_candidates({'3': '朵拉比斯@None', '5': '朵拉比斯@130', '2': '迪基格斯@None', '7': '?(1/2/3/4)≈朵拉比斯(圖)@None'}, DOR) == [3, 7]
      and rp.scan_candidates({}, DOR) == [] and rp.scan_candidates(None, DOR) == [])

# pet_take_lv1_scan 的真實邏輯（假 pet 模組）。depot：int = 朵拉比斯等級（卡片等級讀不出）、str = 別的寵物、None = 空洞
# mode 'hole'（2026-10-13 三轉實機）：取出留空洞、存回填第一個空洞 → 其他卡格號不變；'compact'：取出後面遞補、存回接在最後
import pet as _pet  # noqa: E402
class _FakePet:
    EXIT_NAME, EXIT_VERIFY = 72, 76
    def __init__(self, lvs, mode='hole'):
        self.depot, self.bar, self.LAST, self.calls, self.mode = list(lvs), [], {}, [], mode
    def take(self, role, depot, index, expect, pause, learn, pet_name, growth, level):
        self.calls.append(('take', index))
        if index is None:
            self.LAST = {'cards': {str(i + 1): (f'{DOR}@None' if isinstance(e, int) else f'{e}@5') for i, e in enumerate(self.depot) if e is not None}}
            return 72
        e = self.depot[index - 1] if index <= len(self.depot) else None
        if not isinstance(e, int):                       # 卡片名字不符 → 72、不取
            self.LAST = {}
            return 72
        if self.mode == 'hole':
            self.depot[index - 1] = None
        else:
            self.depot.pop(index - 1)
        self.bar.append(e)
        self.LAST = {'level': e}
        return 0 if e == 1 else 76
    def store_many(self, *a):
        self.calls.append(('store', a[1]))
        e = self.bar.pop()
        if self.mode == 'hole' and None in self.depot:
            self.depot[self.depot.index(None)] = e
        else:
            self.depot.append(e)
        return 0
S_ = ('store', [DOR])
for lvs, mode, want_rc, want_calls in (
        ([130, '摩娜西普', 1], 'hole', 0, [('take', None), ('take', 1), S_, ('take', 3)]),                 # DKBO2 實況：存回後原第 3 格不動（舊版會試 2 → 72）
        ([1, 130], 'hole', 0, [('take', None), ('take', 1)]),
        ([130, 129], 'hole', 72, [('take', None), ('take', 1), S_, ('take', 2), S_]),
        ([130, 1, '迪基格斯'], 'compact', 0, [('take', None), ('take', 1), S_, ('take', 2), ('take', 1)]),   # 遞補模型：原格號 72（沒取）→ 退一格
        ([130, '摩娜西普', '迪基格斯', 1], 'hole', 0, [('take', None), ('take', 1), S_, ('take', 4)])):
    fp_ = _FakePet(lvs, mode)
    saved = {k: getattr(_pet, k) for k in ('take', 'store_many', 'EXIT_NAME', 'EXIT_VERIFY')}
    saved_last = _pet.LAST
    for k in saved:
        setattr(_pet, k, getattr(fp_, k))
    try:
        _pet.LAST = fp_.LAST
        _orig_take = fp_.take
        def _t(*a, _o=_orig_take, _fp=fp_):
            r_ = _o(*a)
            _pet.LAST = _fp.LAST
            return r_
        _pet.take = _t
        rc, info = rp.Tools().pet_take_lv1_scan('DKBO2', DOR)
    finally:
        for k, v in saved.items():
            setattr(_pet, k, v)
        _pet.LAST = saved_last
    check(f'pet_take_lv1_scan 倉庫 {lvs}（{mode}）：rc {want_rc}、呼叫序列', rc == want_rc and fp_.calls == want_calls, f'rc={rc} {fp_.calls}')

# ---- 2026-10-13 三轉實跑寫回 ----
# 鎖定騎寵成長字串漏段（errlog 584 / 585）
check('growth_partial：漏一段當萬用；讀錯一段 / 漏兩段 / 不是 4 段都不算',
      rp.growth_partial('48/10//2', '48/10/7/2') and rp.growth_partial('48//7/2', '48/10/7/2') and rp.growth_partial('49//8/1', '49/10/8/1')
      and not rp.growth_partial('48/10/8/2', '48/10/7/2') and not rp.growth_partial('48///2', '48/10/7/2') and not rp.growth_partial('48/10/7', '48/10/7/2'))
L584 = [('48/10//2', 1100, 360), ('48//7/2', 1100, 362), ('48//7/2', 1101, 361)]          # 同一列多個放大倍數
check('pick_row：errlog 584 同一列三種漏段讀法 → 併成 1 列命中', rp.pick_row(L584, ('growth', '48/10/7/2'))[0] is not None)
L585 = [('49//8/1', 1100, 360), ('49//8/1', 1100, 361), ('49//8/1', 1100, 360)]
check('pick_row：errlog 585 → 命中', rp.pick_row(L585, ('growth', '49/10/8/1'))[0] is not None)
check('pick_row：兩列（y 不同）都漏段吻合 → None（多候選停）', rp.pick_row([('48/10//2', 1100, 360), ('48//7/2', 1100, 402)], ('growth', '48/10/7/2'))[0] is None)
check('pick_row：有整行相同的列就不用萬用（漏段列不搶）', rp.pick_row([('48/10/7/2', 1100, 402), ('48//7/2', 1100, 360)], ('growth', '48/10/7/2'))[0] == ('48/10/7/2', 1100, 402))
hit_, why_ = rp.pick_row([('48/10//2', 1100, 360)], ('growth', '48/10/7/2', ('48/10/9/2',)))
check('pick_row：漏的那段剛好是同角色別隻的差別（48/10/9/2）→ None + 歧義說明', hit_ is None and '歧義' in why_, why_)
check('pick_row：同角色別隻不吻合漏段 → 照常命中', rp.pick_row([('48/10//2', 1100, 360)], ('growth', '48/10/7/2', ('30/5/5/5',)))[0] is not None)
check('role_ident：同角色有別隻沒名字寵物 → ident 第 3 項帶它的成長字串；只有一隻 → 2 項（舊格式）',
      rp.role_ident([S(1, unnamed='48/10/7/2', species=BRA), S(2, unnamed='48/10/9/2', species=None), S(3, name=DOR)], BRA, DOR, '騎寵') == ('growth', '48/10/7/2', ('48/10/9/2',))
      and rp.role_ident([S(1, unnamed='48/10/7/2', species=BRA), S(3, name=DOR)], BRA, DOR, '騎寵') == ('growth', '48/10/7/2'))
# 系別清單（雷龍系被上緣切半）
check('plain_row：完整字串優先；同列多倍數併 1；兩列 → None', rp.plain_row([('雷龍系', 750, 476), ('雷龍系', 752, 478)], '雷龍系') == ('雷龍系', 750, 476)
      and rp.plain_row([('雷龍系', 750, 476), ('雷龍系', 750, 560)], '雷龍系') is None)
check('plain_row：讀不全（雷龍 / 雷系）→ 寬鬆比對；只有首字以外 / 太長 → None', rp.plain_row([('雷龍', 750, 476), ('大象系', 750, 518)], '雷龍系') == ('雷龍', 750, 476)
      and rp.plain_row([('龍系', 750, 476)], '雷龍系') is None and rp.plain_row([('雷龍系的寵物很多很多', 750, 476)], '雷龍系') == ('雷龍系的寵物很多很多', 750, 476)
      and rp.plain_row([('雷系寵物很多很多', 750, 476)], '雷龍系') is None)
top_ = rp.CATCH_LIST_FAMILY[1]
check('family_below_action：大象系貼上緣（y 430）→ back；捲滿 2 次仍貼 → stop', rp.family_below_action([('大象系', 752, 430)], '雷龍系', 0, top_) == ('back', None)
      and rp.family_below_action([('大象系', 752, 430)], '雷龍系', 2, top_) == ('stop', None))
check('family_below_action：往回捲後大象系在 518 → 點 476（= 518 - 42，人手動點的位置）', rp.family_below_action([('大象系', 752, 518)], '雷龍系', 1, top_) == ('pick', ('雷龍系', 752, 476)))
check('family_below_action：沒看到大象系：沒捲過 → 照常往下捲；捲過 → stop（不震盪）', rp.family_below_action([('鯊魚系', 752, 500)], '雷龍系', 0, top_) == ('', None)
      and rp.family_below_action([('鯊魚系', 752, 500)], '雷龍系', 1, top_) == ('stop', None))
# 外掛面板失敗出口保險關閉
import ass as _ass  # noqa: E402
class _FakeAss:
    def __init__(self, opens):
        self.opens, self.closes = list(opens), 0
    def panel_open(self):
        return self.opens.pop(0) if self.opens else False
    def close_panel(self):
        self.closes += 1
        return True
for opens, want, n_close, label in (([False], True, 0, '已關 → 不點'), ([True, False], True, 1, '還開著 → 再關一次'),
                                    ([True, True, True], False, 2, '關不掉 → 2 輪後 False（snap + 警告）')):
    fa = _FakeAss(opens)
    saved = (_ass.panel_open, _ass.close_panel, rp.uikit.sleep, rp.uikit.snap)
    _ass.panel_open, _ass.close_panel, rp.uikit.sleep, rp.uikit.snap = fa.panel_open, fa.close_panel, (lambda s: None), (lambda t: None)
    try:
        import contextlib as _cl, io as _io
        with _cl.redirect_stdout(_io.StringIO()):
            got_ = rp.Tools().ass_close_hard()
    finally:
        _ass.panel_open, _ass.close_panel, rp.uikit.sleep, rp.uikit.snap = saved
    check(f'ass_close_hard：{label}', got_ is want and fa.closes == n_close, f'{got_} {fa.closes}')

# ---------------- boxes 精簡（2026-10-17）：假遊戲計數 ----------------
# 模擬背包 15 格 / 個人 / 公共倉庫，計：背包面板開幾次、彈窗開幾次、一次截圖幾次、分頁切幾次。
import bag as _bag  # noqa: E402


class GameBag:
    EXIT_PANEL, EXIT_SELECT, EXIT_ITEM, EXIT_VERIFY, EXIT_NAME = 90, 91, 92, 95, 96

    def __init__(self, trans=1, hidden=(), personal0=None, box_slot=0, bag_init=None, no_box=(), store_fail=None):
        self.trans = trans
        self.spec = rp.box_spec(trans)
        self.box = self.spec['box']
        self.cur = None
        self.bags = {r: list(bag_init or [None] * 15) for r in ROLES}
        self.personal = {}
        for r in ROLES:
            d = [None] * 20
            if r not in no_box:
                d[box_slot] = ('box', self.box, 'v1')          # ('box', 名稱, 版本)：v1 = 這轉要開的；v140 = 五轉開出的同名 140 版
            if personal0 and box_slot != 0:
                d[0] = personal0
            self.personal[r] = d
        self.public = []
        self.hidden = set(hidden)                              # 名字樣板認不出的道具（要靠新格彈窗）
        self.sessions = self.popups = self.shots = self.tabs = 0
        self.page = 'bag'
        self.store_fail = store_fail                           # (角色, 名稱) → 存倉回 95 一次
        self.ops = []

    # 道具在格裡：(種類, 名稱, 版本)；名稱以 Item 表為準
    def nm(self, x):
        return x[1] if x else None

    def Session(self):
        g = self

        class S:
            rc = 0

            def __enter__(s):
                g.sessions += 1
                return s

            def __exit__(s, *a):
                return False
        return S()

    def select_role(self, r):
        self.cur = r
        return 0

    def goto_page(self, page):
        if page != self.page:
            self.tabs += 1
            self.page = page
        return 0

    def open_depot(self, sub):
        return self.goto_page('depot-' + sub)

    def _wait(self, pred, secs=0):
        return pred()

    def slot_occupancy(self):
        return [x is not None for x in self.bags[self.cur]]

    def _first_empty(self):
        return self.bags[self.cur].index(None)

    def take_slot(self, i, want, sub='personal', kind='consumable'):
        self.open_depot(sub)
        self.popups += 1
        d = self.personal[self.cur]
        if d[i] is None:
            return 92, []
        if self.nm(d[i]) != want:
            return 96, []
        j = self._first_empty()
        self.bags[self.cur][j], d[i] = d[i], None
        self.ops.append(('take', self.cur, i, j))
        return 0, [j]

    def use_slot(self, i, want, stay_ok=False, strict_digits=False):
        assert self.page == 'bag'
        self.popups += 1
        b = self.bags[self.cur]
        if self.nm(b[i]) != want or b[i][2] != 'v1':
            return 96
        b[i] = None
        self.ops.append(('use', self.cur, i))
        for it in self.spec['items']:
            same = [k for k, x in enumerate(b) if x and x[1] == it['name'] and not it['box']]
            if same:                                       # 疊加（禮盒不疊）
                continue
            b[self._first_empty()] = ('box' if it['box'] else 'item', it['name'], 'v140' if it['box'] and it['name'] == want else 'v1')
        return 0

    def icon_read(self, kind='bag', want=(), pool=None, expand=True):
        self.shots += 1
        cells = self.bags[self.cur] if kind == 'bag' else self.personal[self.cur]
        named = {i: x[1] for i, x in enumerate(cells) if x and x[1] not in self.hidden}
        hits = {n: [i for i, v in named.items() if _bag.norm_name(v) == _bag.norm_name(n)] for n in want}
        return {'occ': [x is not None for x in cells], 'named': named, 'hits': hits, 'cells': {i: {'by': 'name', 'ok': True} for i in named}}

    def popup_read(self, i, depot=False):
        self.popups += 1
        return self.nm(self.bags[self.cur][i])

    def _popup_verify(self, i, depot, want, tried):
        self.popups += 1
        cells = self.personal[self.cur] if depot else self.bags[self.cur]
        return self.nm(cells[i]) == want

    def store_slot(self, i, want, sub='public'):
        self.open_depot(sub)
        b = self.bags[self.cur]
        if self.nm(b[i]) != want:
            return 96
        if self.store_fail == (self.cur, want):
            self.store_fail = None
            return 95
        (self.public if sub == 'public' else self.personal[self.cur]).append(b[i]) if sub == 'public' else self.personal[self.cur].__setitem__(self.personal[self.cur].index(None), b[i])
        b[i] = None
        self.ops.append(('store', self.cur, want, sub))
        return 0


_BAG_FNS = ('Session', 'select_role', 'goto_page', 'open_depot', '_wait', 'slot_occupancy', 'take_slot', 'use_slot', 'icon_read', 'popup_read', '_popup_verify', 'store_slot')


def run_boxes(g, states=None, roles=None):
    saved = {k: getattr(_bag, k) for k in _BAG_FNS}
    for k in _BAG_FNS:
        setattr(_bag, k, getattr(g, k))
    saves = []
    states = {} if states is None else states
    try:
        t = rp.Tools()
        out = quiet(t.boxes_many, roles or ROLES, g.trans, states, lambda: saves.append(1))
        return out[0][0], states, saves
    finally:
        for k, v in saved.items():
            setattr(_bag, k, v)


check('new_slots：之前空 / 被釋放的格現在有 → 新格；讀不到 → []', _bag.new_slots([1, 0, 0], [1, 1, 0]) == [1] and _bag.new_slots([1, 0], [1, 1], freed=[0]) == [0, 1]
      and _bag.new_slots(None, [1]) == [])
sp1, sp5 = rp.box_spec(1), rp.box_spec(5)
check('box_spec：1轉從 Item 表讀到誘餌 / 離線水晶 / 智慧果 / 安撫之素存公共、2轉禮盒存個人',
      sp1['src'] == 'table' and [(i['name'], i['depot']) for i in sp1['items']] == [('寵物誘餌', 'public'), ('離線水晶（8H）', 'public'), ('2倍智慧果（綁定）', 'public'), ('安撫之素', 'public'), ('2轉新手禮盒', 'personal')], str(sp1))
check('box_spec：5轉 = 90332（等級 1 那筆）→ 誘餌 / 智慧果 / 同名 5轉新手禮盒（個人）', [(i['name'], i['depot'], i['box']) for i in sp5['items']] == [('寵物誘餌', 'public', False), ('2倍智慧果（綁定）', 'public', False), ('5轉新手禮盒', 'personal', True)], str(sp5))
check('box_spec：表讀不到 → 舊寫死清單', rp.box_spec(2, table=[])['src'] == 'fallback' and rp.box_spec(2, table=[])['items'][-1]['name'] == '3轉新手禮盒')
pl, pend = rp.plan_box_stores(sp5, {0: '寵物誘餌', 1: '5轉新手禮盒', 3: '5轉新手禮盒', 4: '某道具'}, {'寵物誘餌': [0], '5轉新手禮盒': [1, 3]}, {0: {'by': 'name'}}, new=[0, 3, 5])
check('plan_box_stores：禮盒只認新格（舊格 1 不碰）、新格沒認出的回給彈窗', pl == {0: ('寵物誘餌', 'public'), 3: ('5轉新手禮盒', 'personal')} and pend == [5], f'{pl} {pend}')
check('match_box_item：禮盒忽略數字、清單外 → None', rp.match_box_item(sp1, '2轉新手禮盒')['depot'] == 'personal' and rp.match_box_item(sp1, '安撫之素')['name'] == '安撫之素'
      and rp.match_box_item(sp1, '千年龜的殼') is None)

g = GameBag(1)
rc, st, saves = run_boxes(g)
check('1轉 5 人：rc 0、背包面板整段只開 1 次', rc == 0 and g.sessions == 1, f'rc={rc} sessions={g.sessions}')
check('1轉：每人彈窗 2 次（取出核對 + 使用核對）、一次截圖 1 次，沒有逐格彈窗掃', g.popups == 2 * len(ROLES) and g.shots == len(ROLES), f'popups={g.popups} shots={g.shots}')
check('1轉：公共 = 4 種內容物 × 5 人、個人倉庫 = 2轉新手禮盒', sorted(x[1] for x in g.public) == sorted(['寵物誘餌', '離線水晶（8H）', '2倍智慧果（綁定）', '安撫之素'] * len(ROLES))
      and all(any(x and x[1] == '2轉新手禮盒' for x in g.personal[r]) for r in ROLES) and all(not any(g.bags[r]) for r in ROLES), str(g.public[:4]))
check('1轉：分頁切換每人 ≤ 4 次（個人取 → 背包使用 → 公共存 → 個人存）', g.tabs <= 4 * len(ROLES), f'tabs={g.tabs}')
check('1轉：每人進度 done、每步都記（take / use / store 至少 3 次 save）', all(st[r]['step'] == 'done' for r in ROLES) and len(saves) >= 3 * len(ROLES))

g = GameBag(5)
rc, st, _ = run_boxes(g)
check('5轉：開出的同名 140 版禮盒（新格）存個人、背包清空，不開額外彈窗', rc == 0 and all(any(x and x[2] == 'v140' for x in g.personal[r]) for r in ROLES)
      and all(not any(g.bags[r]) for r in ROLES) and g.popups == 2 * len(ROLES), f'popups={g.popups}')

g = GameBag(1, hidden={'安撫之素'})
rc, st, _ = run_boxes(g)
check('名字樣板認不出安撫之素 → 只對那 1 個新格開彈窗（每人 +1），照樣存公共', rc == 0 and g.popups == 3 * len(ROLES) and sum(1 for x in g.public if x[1] == '安撫之素') == len(ROLES), f'popups={g.popups}')

g = GameBag(1, bag_init=[('item', '千年龜的殼', 'v1')] + [None] * 14)
rc, st, _ = run_boxes(g)
check('清單外的舊道具（千年龜的殼）不碰、不開彈窗', rc == 0 and all(g.bags[r][0][1] == '千年龜的殼' for r in ROLES) and g.popups == 2 * len(ROLES))

g = GameBag(1, personal0=('item', '朵拉比斯蛋', 'v1'), box_slot=3)
rc, st, _ = run_boxes(g, roles=['DKBO'])
check('個人倉庫第 1 格不是禮盒 → 只核對一次截圖命中的格（背包 0 命中、倉庫 1 格）→ 取出照開', rc == 0 and st['DKBO']['step'] == 'done' and g.popups == 1 + 1 + 1 + 1 and g.shots == 3,
      f'popups={g.popups} shots={g.shots} ops={g.ops}')

g = GameBag(1, no_box=('DKBO2',))
rc, st, _ = run_boxes(g)
check('背包 / 個人倉庫都沒有 → skipped、不使用，其他人照開', rc == 0 and 'skipped' in st['DKBO2'] and not [o for o in g.ops if o[0] == 'use' and o[1] == 'DKBO2']
      and len([o for o in g.ops if o[0] == 'use']) == len(ROLES) - 1)

g = GameBag(1, store_fail=('DKBO3', '離線水晶（8H）'))
rc, st, _ = run_boxes(g)
check('DKBO3 存倉失敗 → 回 95、停在 DKBO3（step used）', rc == 95 and st['DKBO3']['step'] == 'used' and 'DKBO4' not in st, str(st.get('DKBO3')))
n_use = len([o for o in g.ops if o[0] == 'use'])
rc, st, _ = run_boxes(g, states=st)
check('續跑：done 的人跳過、DKBO3 從存倉接（不再取 / 開）、DKBO4～5 照開', rc == 0 and len([o for o in g.ops if o[0] == 'use']) == n_use + 2
      and not [o for o in g.ops if o[0] == 'take' and o[1] in ('DKBO', 'DKBO2', 'DKBO3')][3:] and all(st[r]['step'] == 'done' for r in ROLES) and g.sessions == 2,
      f'{g.ops[-6:]}')

f = Fake()
rc, _ = go(f, to_stage='boxes')
check('boxes 段開頭先 quiet（停 follow / 關遇敵 / 等戰鬥）再開箱', rc == 0 and ci('quiet') and ci('quiet')[0] < ci('box_open')[0])
f = Fake()
f.fail['quiet'] = 3
rc, _ = go(f, to_stage='boxes')
check('quiet 失敗 → 101、沒開背包', rc == 101 and not ci('box_open') and rp.LAST.get('quiet_rc') == 3)

print(f'\n{fails} 項失敗' if fails else '\n全部通過')
sys.exit(1 if fails else 0)
