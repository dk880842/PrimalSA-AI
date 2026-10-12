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
check('new_unnamed：前一次空格、這次有沒名字 → 新增', [s['slot'] for s in rp.new_unnamed([S(1, name='x'), E(2), E(3)], [S(1, name='x'), S(2, unnamed='1/1/1/1'), E(3)])] == [2]
      and rp.new_unnamed([S(1, name='x'), E(2)], [S(1, name='x'), S(2, name='y')]) == [])
check('role_ident：騎寵 = 沒名字 → growth；戰寵 = name；找不到 / 兩隻 → None',
      rp.role_ident([S(1, unnamed='49/9/8/2', species=BRA), S(2, name=DOR)], BRA, DOR, '騎寵') == ('growth', '49/9/8/2')
      and rp.role_ident([S(1, unnamed='49/9/8/2', species=BRA), S(2, name=DOR)], BRA, DOR, '戰寵') == ('name', DOR)
      and rp.role_ident([S(1, name=DOR)], BRA, DOR, '騎寵') is None
      and rp.role_ident([S(1, unnamed='1/1/1/1', species=BRA), S(2, unnamed='2/2/2/2', species=BRA)], BRA, DOR, '騎寵') is None)
check('catch 不碰紅區：程式碼沒有點「+」1295,315 / 丟棄區座標', all('1295' not in str(v) for v in rp.CATCH_XY.values()))


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

    def c(self, *a):
        self.calls.append(a)

    def f(self, name):
        return self.fail.get(name, 0)

    # --- 基本 ---
    def sleep(self, s):
        pass

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
                dep = self.depot[r][depot]
                hit = next((k for k, c in enumerate(dep) if (c == nm) or (isinstance(c, dict) and c.get('species') == nm)), None)
                if hit is None:
                    return 72, {'msg': f'{depot} 沒有 {nm}'}
                c = dep.pop(hit)
                j = self.bar[r].index(None)
                self.bar[r][j] = ({'name': c, 'state': '等待'} if isinstance(c, str) else {'name': nm, 'unnamed': c['unnamed'], 'species': c['species'], 'state': '等待'})
        return 0, {}

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
check('結果：5 人寵物欄 = 布拉奇多斯（沒名字，騎乘）+ 朵拉比斯（出戰）', all(len(names_of(r)) == 2 and names_of(r)[0][1] == '騎乘' and names_of(r)[0][0].startswith('?') and names_of(r)[1] == (DOR, '出戰') for r in ROLES), str({r: names_of(r) for r in ROLES}))
check('5 人成長字串各不相同（5 隻）', len({names_of(r)[0][0] for r in ROLES}) == 5)
check('外掛：5 人鎖定騎寵（成長字串）與戰寵（名字）最後都勾、ident 正確', all(f.locks[r] == {'騎寵': True, '戰寵': True} and f.lock_ident[(r, '騎寵')] == ('growth', names_of(r)[0][0][1:]) and f.lock_ident[(r, '戰寵')] == ('name', DOR) for r in ROLES))
ci = lambda name: [i for i, c in enumerate(f.calls) if c[0] == name]    # noqa: E731
check('順序：preflight < 禮盒 < store < 抓寵 < distribute < ride < battle < lock < cleanup',
      ci('disband')[0] < ci('box_open')[0] < ci('store_many')[0] < ci('catch_setup')[0] < [i for i, c in enumerate(f.calls) if c[0] == 'store_many' and c[3] == 'public'][0]
      < [i for i, c in enumerate(f.calls) if c[0] == 'set_state' and c[3] == '騎乘'][0] < [i for i, c in enumerate(f.calls) if c[0] == 'take_many' and c[3] == 'personal'][0]
      < [i for i, c in enumerate(f.calls) if c[0] == 'lock_set' and c[3]][0] < ci('bait_return')[-1])
check('preflight：外掛解鎖先於存倉（5 人 × 2 項）、解散隊伍', len([c for c in f.calls if c[0] == 'lock_set' and c[3] is False]) == 10 and ci('disband'))
check('抓寵：先試 1（誘餌留 1、可抓捕數 1）、學物種、再 4', [c[1:] for c in f.calls if c[0] == 'catch_setup'] == [('DKBO2', '雷龍系', BRA, 1), ('DKBO2', '雷龍系', BRA, 4)]
      and [c[2] for c in f.calls if c[0] == 'bait_take'] == [1, 4] and len([c for c in f.calls if c[0] == 'learn_species']) == 1)
check('舊騎寵：--store-mount 瑪斯貝卡 → 先設等待（allow-mount）再存，存倉名單帶旗標', ('set_state', 'DKBO', '瑪斯貝卡', '等待', True) in f.calls and any(c[0] == 'store_many' and c[3] == 'personal' and '瑪斯貝卡' in c[2] and c[4] == ('瑪斯貝卡',) for c in f.calls))
check('分配：catcher 存 4 隻進公共（取最後格 pick=last、旗標只放行布拉奇多斯）、其他 4 人各取 1',
      ('store_many', ('DKBO2',), (BRA,) * 4, 'public', (BRA,), 'last') in f.calls and ('take_many', ('DKBO', 'DKBO3', 'DKBO4', 'DKBO5'), (BRA,), 'public') in f.calls)
check('戰寵：5 人從個人倉庫取朵拉比斯、設出戰（不帶 allow_mount）', ('take_many', tuple(ROLES), (DOR,), 'personal') in f.calls and all(('set_state', r, DOR, '出戰', False) in f.calls for r in ROLES))
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
f.fail['learn_species'] = 72
check('登錄物種失敗 → 103、沒繼續抓 4 隻', go(f)[0] == 103 and len(ci('catch_setup')) == 1)
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
saved = (ass._many, ass.panel_open, rp.ocr_lines, uikit.gui, rp.Tools._ass_tab, rp.Tools._checked)
ass._many, ass.panel_open, rp.ocr_lines, uikit.gui = fa.many, (lambda: True), fa.ocr, fa.gui
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
ass._many, ass.panel_open, rp.ocr_lines, uikit.gui, rp.Tools._ass_tab, rp.Tools._checked = saved

print(f'\n{fails} 項失敗' if fails else '\n全部通過')
sys.exit(1 if fails else 0)
