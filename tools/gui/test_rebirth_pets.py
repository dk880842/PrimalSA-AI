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
names, mount, left = rp.stores_for(bar, None)
check('stores_for：沒給 --store-mount → 騎寵與沒名字未確認的留下，只存迪基格斯', names == ['迪基格斯'] and mount is None and [x[0] for x in left] == [1, 3], str(left))
names, mount, left = rp.stores_for(bar, '瑪斯貝卡')
check('stores_for：--store-mount 瑪斯貝卡 → 騎寵也存、回報要先設等待', names == ['瑪斯貝卡', '迪基格斯'] and mount == '瑪斯貝卡')
names, mount, left = rp.stores_for(bar, '布拉奇多斯')
check('stores_for：--store-mount 名字與寵物不同 → 瑪斯貝卡仍不碰', '瑪斯貝卡' not in names and mount is None)
bar2 = [S(1, unnamed='49/9/8/2', raw_name='?(49/9/8/2)', species=BRA, mountlike=True), S(2, name=DOR)]
check('stores_for：沒名字但物種是騎寵（布拉奇多斯）→ 沒給旗標不存', rp.stores_for(bar2, None)[0] == [DOR] and rp.stores_for(bar2, BRA)[0] == [BRA, DOR])
# 縮圖比對認物種（3d0362b）：沒名字 + mountlike + img_score >= 0.9 + img_species == --store-mount 才放行
def _um(**k):
    d = {'slot': 1, 'unnamed': True, 'mountlike': True, 'img_species': BRA, 'img_score': 0.95}
    d.update(k)
    return d
check('stores_for：縮圖 0.95 認出 --store-mount 物種 → 存', rp.stores_for([_um()], BRA) == ([BRA], BRA, []))
check('stores_for：縮圖 0.9（邊界）→ 存', rp.stores_for([_um(img_score=0.9)], BRA)[0] == [BRA])
check('stores_for：縮圖 0.89 → 留下回報', rp.stores_for([_um(img_score=0.89)], BRA)[0] == [] and len(rp.stores_for([_um(img_score=0.89)], BRA)[2]) == 1)
check('stores_for：縮圖物種與 --store-mount 不同 → 留下', rp.stores_for([_um(img_species=DOR)], BRA)[0] == [])
check('stores_for：沒給 --store-mount → 縮圖再準也不存', rp.stores_for([_um()], None)[0] == [])
check('stores_for：不是 mountlike 的沒名字寵物，縮圖不放行', rp.stores_for([_um(mountlike=False)], BRA)[0] == [])
check('stores_for：img_score 缺 → 當 0、留下', rp.stores_for([_um(img_score=None)], BRA)[0] == [])
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
        self.bar = {r: [dict(name='迪基格斯', state='出戰'), dict(name='瑪斯貝卡', state='騎乘'), None, None, None] for r in ROLES}
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
    def box_open(self, r, trans):
        self.c('box_open', r, trans)
        if self.f('box_open'):
            return self.f('box_open'), {}
        if self.boxes[r]:
            self.boxes[r] = 0
            self.pub_baits += 10
            return 0, {'stored': ['寵物誘餌'], 'personal': ['2轉新手禮盒']}
        return 0, {'skipped': 'x'}

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
    return dict(mount_species=BRA, battle_pet=DOR, catcher='DKBO2', count=5, store_mount='瑪斯貝卡', **kw)


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
check('--dry-run：rc 0、完全沒呼叫 Tools、印出 9 個階段', rc == 0 and f.calls == [] and all(s in out for s in rp.STAGES), out[-200:])
check('--dry-run 的計畫列出舊騎寵處理（--store-mount）與雷龍系', '瑪斯貝卡' in out and '雷龍系' in out)
f = Fake()
check('參數：catcher 不認得 / count 超範圍 / 騎寵名不在 Monster 表 / store-mount 不是騎寵 / --from 在 --to 後 → 109 且零呼叫',
      all(go(Fake(), **kw)[0] == 109 for kw in ({'catcher': 'XYZ'}, {'count': 9}, {'mount_species': '亂碼寵'}, {'store_mount': '迪基格斯'}, {'from_stage': 'lock', 'to_stage': 'store'})))

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
check('順序：preflight < 禮盒 < store < 抓寵 < distribute < ride < battle < lock < cleanup',
      ci('disband')[0] < ci('box_open')[0] < ci('store_many')[0] < ci('catch_setup')[0] < [i for i, c in enumerate(f.calls) if c[0] == 'store_many' and c[3] == 'public'][0]
      < [i for i, c in enumerate(f.calls) if c[0] == 'set_state' and c[3] == '騎乘'][0] < [i for i, c in enumerate(f.calls) if c[0] == 'take_many' and c[3] == 'personal'][0]
      < [i for i, c in enumerate(f.calls) if c[0] == 'lock_set' and c[3]][0] < ci('bait_return')[-1])
check('preflight：外掛解鎖先於存倉（5 人 × 2 項）、解散隊伍', len([c for c in f.calls if c[0] == 'lock_set' and c[3] is False]) == 10 and ci('disband'))
check('抓寵：先試 1（誘餌留 1、可抓捕數 1）、還原名字、再 4、再還原名字；名字對 → 不學物種（learn-species 只當備援）',
      [c[1:] for c in f.calls if c[0] == 'catch_setup'] == [('DKBO2', '雷龍系', BRA, 1), ('DKBO2', '雷龍系', BRA, 4)]
      and [c[2] for c in f.calls if c[0] == 'bait_take'] == [1, 4] and [c[1] for c in f.calls if c[0] == 'reset_names'] == [('DKBO2',), ('DKBO2',)]
      and not ci('learn_species') and ci('catch_wait')[0] < ci('reset_names')[0] < ci('catch_setup')[1])
check('舊騎寵：--store-mount 瑪斯貝卡 → 先設等待（allow-mount）再存，存倉名單帶旗標', ('set_state', 'DKBO', '瑪斯貝卡', '等待', True) in f.calls and any(c[0] == 'store_many' and c[3] == 'personal' and '瑪斯貝卡' in c[2] and c[4] == ('瑪斯貝卡',) for c in f.calls))
check('分配：catcher 存 4 隻進公共（取最後格 pick=last、旗標只放行布拉奇多斯）、其他 4 人各取 1',
      ('store_many', ('DKBO2',), (BRA,) * 4, 'public', (BRA,), 'last') in f.calls and ('take_many', ('DKBO', 'DKBO3', 'DKBO4', 'DKBO5'), (BRA,), 'public') in f.calls)
check('戰寵：5 人從個人倉庫取朵拉比斯、設出戰（不帶 allow_mount）', ('take_many', tuple(ROLES), (DOR + '@1',), 'personal') in f.calls and all(('set_state', r, DOR, '出戰', False) in f.calls for r in ROLES))
check('誘餌：公共 = 禮盒 50 個（沒有花石幣），catcher 背包最後 0 個', f.pub_baits == 50 and f.bag_baits['DKBO2'] == 0)
check('收尾：當前 DKBO、quest-log 有寫', f.cur == 'DKBO' and '轉生後寵物重整' in rp.QUEST_LOG.read_text(encoding='utf-8'))
check('騎寵保護：所有 store_many 呼叫中，騎寵名只在 allow 名單內', all(set(c[2]) & set(uikit.MOUNTS) <= set(c[4]) for c in f.calls if c[0] == 'store_many'))

# ---------------- 沒給 --store-mount ----------------
f = Fake()
rc, out = go(f, store_mount=None)
check('沒給 --store-mount：舊騎寵不碰 → catch 欄位不夠 rc 103、沒抓寵、沒設任何等待', rc == 103 and not ci('catch_setup') and not any(c[0] == 'set_state' for c in f.calls) and 'store-mount' in out.replace('--store-mount', 'store-mount'), f'rc={rc}')
check('  瑪斯貝卡仍在寵物欄（沒存）', all(any(p and p['name'] == '瑪斯貝卡' for p in f.bar[r]) for r in ROLES))

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
check('存倉失敗 → 102（info 有 pet_rc）', go(f)[0] == 102 and rp.LAST.get('pet_rc') == 76)
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
f.fail['set_state'] = 74
rc, _ = go(f, store_mount=None, from_stage='preflight', to_stage='preflight')
rc2 = go(f)[0]
check('設狀態失敗（鎖定擋住 74）→ 先在 store 設舊騎寵等待就停 102', rc2 == 102)
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
check('--to catch：跑到抓寵就停（進度檔有 4 個階段）', rc == 0 and rp.LAST['done'] == ['preflight', 'boxes', 'store', 'catch'])
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
f.stone = 120000
rc, _ = go(f, confirm_buy_catch=True)
check('石幣不夠（第 3 個買不起）→ 103、不設外掛', rc == 103 and f.count == 2 and 'catch_setup' not in [c[0] for c in f.calls])
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
check('石幣扣的不是 50,000 → 103 停手', go(f, confirm_buy_catch=True)[0] == 103 and f.count == 1)
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

# 禮盒 95 重試（bag 假函式）
import bag as _bag  # noqa: E402
class _FakeBag:
    EXIT_VERIFY, EXIT_ITEM = 95, 92
    def __init__(self, store_script, use_script=(0,), box_left=(1,)):
        self.store_script, self.use_script, self.box_left, self.calls = list(store_script), list(use_script), list(box_left), []
    def find_items(self, role, names):
        self.calls.append('find')
        return 0, {names[0]: (None if not self.box_left or self.box_left.pop(0) == 0 else 3)}
    def use_item(self, role, name, verify_buff=False):
        self.calls.append('use')
        return self.use_script.pop(0) if self.use_script else 0
    def depot_store(self, role, name, depot, **k):
        self.calls.append(('store', name))
        return self.store_script.pop(0) if self.store_script else 92
def _box(fb):
    saved = {k: getattr(_bag, k) for k in ('find_items', 'use_item', 'depot_store')}
    for k in saved:
        setattr(_bag, k, getattr(fb, k))
    try:
        t = rp.Tools()
        t.sleep = lambda s: None
        return t.box_open('DKBO4', 1)
    finally:
        for k, v in saved.items():
            setattr(_bag, k, v)
fb = _FakeBag([95, 0, 0, 0, 0, 0])                 # 第 1 項存倉 95 → 重試成功
rc, info = _box(fb)
check('box_open：存倉 95 → 重試 1 次成功，整體 0', rc == 0 and info.get('retry') == ['寵物誘餌'] and info['stored'][0] == '寵物誘餌', str(info))
fb = _FakeBag([95, 95])
rc, info = _box(fb)
check('box_open：重試仍 95 → 回 95（info.failed）', rc == 95 and info.get('failed') == '寵物誘餌')
fb = _FakeBag([95, 92, 92, 92, 92, 92])             # 重試時回 92 = 其實已存成功（驗證誤判）
rc, info = _box(fb)
check('box_open：95 後重試回 92（已存好）→ 視為成功繼續', rc == 0, str(info))
fb = _FakeBag([], use_script=[95, 0], box_left=[1, 1])    # 用禮盒 95、禮盒還在 → 重用一次
rc, info = _box(fb)
check('box_open：使用 95 且禮盒還在 → 重用 1 次', rc == 0 and fb.calls.count('use') == 2 and info.get('retry', [None])[0] == 'use', str(fb.calls))
fb = _FakeBag([], use_script=[95], box_left=[1, 0])        # 用禮盒 95、禮盒已不在 = 已用掉 → 不重用
rc, info = _box(fb)
check('box_open：使用 95 但禮盒已不在 → 不重用、繼續存倉', rc == 0 and fb.calls.count('use') == 1, str(fb.calls))

print(f'\n{fails} 項失敗' if fails else '\n全部通過')
sys.exit(1 if fails else 0)
