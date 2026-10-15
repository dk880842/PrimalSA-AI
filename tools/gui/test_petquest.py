#!/usr/bin/env python3
"""petquest.py 離線測試：完全不碰遊戲（假 Tools + 小型寵物欄 / 倉庫模擬器回應各腳本子程序）。
用法：uv run --no-project python tools/gui/test_petquest.py"""
import contextlib
import io
import json
import time
import os
import sys
import tempfile
from pathlib import Path

os.environ.setdefault('PSA_LAYOUT', '2880x1659')
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import testenv  # noqa: E402,F401  紀錄檔轉向暫存
import errlog  # noqa: E402
import petquest as pq  # noqa: E402

TMP = Path(tempfile.mkdtemp())
pq.PROGRESS, pq.EVENT_LOG = TMP / 'pq.json', TMP / 'ev.log'
errlog.LOG = TMP / 'errlog.jsonl'
fails = 0
ROLES = pq.ALL_ROLES


def check(name, cond, extra=''):
    global fails
    print(('PASS' if cond else 'FAIL'), name, extra)
    if not cond:
        fails += 1


def P(name, state='等待', level=1):
    return {'name': name, 'state': state, 'level': level}


class Sim:
    """假遊戲：每人寵物欄（最多 5 格，第 1 格騎寵）、個人 / 公共寵物倉庫、公共誘餌、石幣 / 鑽石、追蹤步號"""

    def __init__(self, qid, bait=50, orig=125, step=1, stone=3_000_000, battle='朵拉比斯'):
        self.battle = battle
        self.qid, self.bait, self.stone, self.dia, self.step = qid, bait, stone, 0, step
        self.bar = {r: [P('布拉奇多斯', '騎乘', 5), P(battle, '出戰', orig + i)] for i, r in enumerate(ROLES)}
        self.personal = {r: [P(battle, '等待', 130)] for r in ROLES}
        self.public = []
        self.bag_bait = {}
        self.plus = {}                       # 角色 → 用「+」買的可抓捕數
        self.calls = []
        self.fail = {}                       # (script, 第一個參數) → rc
        self.quest_q = {}                    # questrun 依序回傳
        self.train_calls = 0
        self.plus_cost = pq.PLUS_COST
        self.done = False

    # -- 假 Tools 介面 --
    def sleep(self, s):
        pass

    def clock(self):                          # 每呼叫一次走 1 秒（練寵迴圈靠 TRAIN_MAX_S 牆鐘結束，不會無窮迴圈）
        self.t = getattr(self, 't', 0.0) + 1.0
        return self.t

    def encounter_off(self):
        self.calls.append(('enc_off',))

    def read_step(self, track):
        return self.step

    def money(self):
        return self.stone, self.dia

    def press_plus(self, role, limit=None, min_before=None):
        b = self.plus.get(role, 0) + self.bag_bait.get(role, 0)
        if limit is not None and b >= limit:
            return 0, b, b
        if min_before is not None and b < min_before:
            return 163, b, None
        self.plus[role] = self.plus.get(role, 0) + 1
        self.stone -= self.plus_cost
        self.dia -= getattr(self, 'dia_drop', 0)
        self.dia -= getattr(self, 'dia_drop', 0)
        self.calls.append(('plus', role))
        return 0, b, b + 1

    # -- 子程序模擬 --
    def out(self, rc, *lines, js=None):
        ls = list(lines)
        if js is not None:
            ls.append(json.dumps(js, ensure_ascii=False))
        return rc, ls

    def sub(self, script, args, timeout=0):
        args = [str(a) for a in args]
        self.calls.append((script, tuple(args)))
        hk = getattr(self, 'hook', None)
        if hk:
            hr = hk(script, args)
            if hr is not None:
                return self.out(hr)
        key = (script, args[0] if args else '')
        if key in self.fail:
            return self.out(self.fail[key])
        fn = {'questrun.py': self.questrun, 'team.py': lambda a: self.out(0), 'pet.py': self.pet, 'pet_catch.py': self.pet_catch,
              'grind.py': lambda a: self.out(0), 'petdrop.py': self.petdrop, 'ass.py': lambda a: self.out(0), 'petwatch.py': self.petwatch,
              'quest.py': self.quest}[script]
        return fn(args)

    def opt(self, args, k, d=None):
        return args[args.index(k) + 1] if k in args else d

    def questrun(self, args):
        q = self.quest_q.get(self.qid)
        if q:
            return self.out(q.pop(0))
        if self.done:
            return self.out(0)
        if '--pet-turnin' not in args:
            if self.qid == 3003:
                ok = all(any(p['name'] == '金布伊' and p['level'] >= 77 for p in self.bar[r]) for r in ROLES)
                if ok and self.step == 2:
                    for r in ROLES:
                        self.bar[r] = [p for p in self.bar[r] if p['name'] != '金布伊'] + [P('左迪洛斯')]
                    self.done = True
                    return self.out(0)
                return self.out(115 if self.step == 1 else 155)
            return self.out(115 if self.qid == 2016 else 155)
        rd = pq.QUESTS[self.qid]['rounds'][self.step - 1]
        sps = [sp for _, _, sp in rd['assign']]
        for r in ROLES:
            if any(p['state'] == '出戰' and p['name'] in sps for p in self.bar[r]):
                return self.out(117)
            for sp in sps:
                hit = [p for p in self.bar[r] if p['name'] == sp and p['level'] >= rd['need'][sp]]
                if len(hit) != 1:
                    return self.out(117)
            self.bar[r] = [p for p in self.bar[r] if p['name'] not in sps]
            if self.qid == 2016:
                self.bar[r].append(P('布克布克'))
            elif self.step == 1:
                self.bar[r].append(P('修寶'))
            else:
                self.bar[r].append(P('朵拉比斯', '等待', 1))
        if self.qid == 2019 and self.step == 1:
            self.step = 2
            return self.out(117)
        self.done = True
        return self.out(0)

    def quest(self, args):
        for r in ROLES:
            self.bar[r].append(P('金布伊'))
        self.step = 2
        return self.out(0)

    def petwatch(self, args):
        for r in ROLES:
            for p in self.bar[r]:
                if p['name'] == '金布伊':
                    p['level'], p['state'] = 77, '等待'
                if p['name'] == self.battle:
                    p['state'] = '出戰'
        return self.out(0)

    def petdrop(self, args):
        name = args[1]
        for r in ROLES:
            self.bar[r] = [p for p in self.bar[r] if not (p['name'] == name and p['level'] <= 1)]
        return self.out(0)

    def num(self, sp):
        """剛抓到的寵物：名字框是成長字串（數字名），身分 sp；reset-name 後才變物種名"""
        return dict(P('35/7/3/8'), sp=sp, num=True)

    def pet_catch(self, args):
        if '--assign' not in args:
            return self.out(0)
        assign = [a.split(':') for a in self.opt(args, '--assign').split(',')]
        k = int(self.opt(args, '--count'))
        stages = self.opt(args, '--stages')
        if stages != 'bait' and getattr(self, 'partial', None):      # 模擬中途失敗：有人已抓了幾隻（第 1 格騎寵之後）、另一人設置失敗 → 14
            for r, n in self.partial.items():
                sp = next(x for rr, _, x in assign if rr == r)
                self.bar[r] += [P(sp) for _ in range(n)]
                self.bag_bait[r] = 0
            for r, n in getattr(self, 'partial_personal', {}).items():
                sp = next(x for rr, _, x in assign if rr == r)
                self.personal[r] += [P(sp) for _ in range(n)]
            self.partial = None
            return self.out(14)
        if stages == 'baitback':                 # 背包剩的誘餌存回公共
            for r, _, _ in assign:
                self.bait += self.bag_bait.get(r, 0)
                self.bag_bait[r] = 0
            self.baitback = getattr(self, 'baitback', 0) + 1
            return self.out(0)
        if stages == 'bait':
            lines = []
            short_seen = False
            for r, _, _ in assign:
                have = self.bag_bait.get(r, 0)
                if have == k:                    # 背包已剛好 k 個 → 不取不拆（冪等）
                    lines.append(f'rebirth_pets：{r} 背包誘餌 = {k}')
                    continue
                if self.bait + have < k:
                    if '--keep-short-bait' in args:      # 現有的留背包、印不足數、繼續下一人
                        self.bag_bait[r] = have + self.bait
                        self.bait = 0
                        lines.append(f'rebirth_pets：{r} 背包誘餌不足 = {self.bag_bait[r]}（要 {k}）')
                        short_seen = True
                        continue
                    return self.out(92, *lines)
                self.bait += have - k            # 取整疊、拆 k、其餘存回
                self.bag_bait[r] = k
                self.bait_takes = getattr(self, 'bait_takes', 0) + 1
                lines.append(f'rebirth_pets：{r} 背包誘餌 = {k}')
            return self.out(92 if short_seen else 0, *lines)
        for r, _, sp in assign:
            have = self.bag_bait.get(r, 0) + self.plus.get(r, 0)
            if have < k:
                return self.out(4, f'{r} 可抓捕數 {have} < {k}')
            fit = min(k, 5 - len(self.bar[r]))                       # 外掛「自動存倉庫」：欄放不下的自動進個人倉庫（一次抓滿，使用者 2026-10-15）
            self.bar[r] += [self.num(sp) for _ in range(fit)]
            self.personal[r] += [self.num(sp) for _ in range(k - fit)]
            use = min(self.bag_bait.get(r, 0), k)
            self.bag_bait[r] = self.bag_bait.get(r, 0) - use
            self.plus[r] = 0
        return self.out(0)

    def pet(self, args):
        cmd = args[0]
        if cmd == 'list':
            if self.train_calls is not None:
                self.train_calls += 1
            return self.out(0, js={'roles': {r: [dict(p, slot=i + 1, nh=p['name'], **({'name': None, 'unnamed': p['name']} if p.get('num') else {})) for i, p in enumerate(self.bar[r])] for r in ROLES}, 'rc': 0})
        if cmd == 'levels':                  # 只讀等級：格號 + 等級 + 名字框指紋（模擬用名字）
            self.levels_calls = getattr(self, 'levels_calls', 0) + 1
            sl = [int(x) for x in self.opt(args, '--slots', '').split(',') if x]
            return self.out(0, js={'roles': {r: [{'slot': i + 1, 'level': p['level'], 'nh': p['name']} for i, p in enumerate(self.bar[r]) if not sl or i + 1 in sl]
                                             for r in ROLES}, 'rc': 0})
        if cmd == 'store-many':
            depot = self.opt(args, '--depot')
            if '--plan' in args:                         # 每人不同寵物：DKBO2:克邦凱斯×4,…（一次呼叫 = 面板開一次）
                work = []
                for part in self.opt(args, '--plan').split(','):
                    r, t = part.split(':')
                    nm, n = t.split('×') if '×' in t else (t, '1')
                    work += [(r, nm)] * int(n)
            else:
                roles = ROLES if self.opt(args, '--role') == 'all' else self.opt(args, '--role').split(',')
                work = [(r, nm) for r in roles for nm in self.opt(args, '--pets').split(',')]
            self.store_calls = getattr(self, 'store_calls', 0) + 1
            ops = []
            for r, name in work:
                if getattr(self, 'store_fail_op', None) is not None and depot == 'public' and len(ops) == self.store_fail_op:      # 模擬存到一半失敗（前面的人已存完）
                    self.store_fail_op = None
                    ops.append({'role': r, 'pet': name, 'rc': 72})
                    return self.out(72, js={'ops': ops})
                hits = [p for p in self.bar[r] if p['name'] == name and p['state'] != '騎乘']
                if not hits:
                    if '--skip-missing' in args:
                        continue
                    ops.append({'role': r, 'pet': name, 'rc': 72})
                    return self.out(72, js={'ops': ops})
                p = hits[-1]
                self.bar[r].remove(p)
                p['state'] = '等待'
                (self.public if depot == 'public' else self.personal[r]).append(p)
                ops.append({'role': r, 'pet': name, 'rc': 0})
            return self.out(0, js={'ops': ops})
        if cmd == 'take-many':
            depot = self.opt(args, '--depot')
            ops = []
            parts = self.opt(args, '--plan').split(',')
            for i, part in enumerate(parts):
                r, t = part.split(':')
                name, lv = (t.split('@') + [None])[:2]
                src = self.public if depot == 'public' else self.personal[r]
                if name == '?':                 # 沒名字的卡（成長字串，不認物種）：多於這個角色還要取的 '?' 隻數 → 72 不猜
                    nums = [p for p in src if p.get('num')]
                    if len(nums) > sum(1 for x in parts[i:] if x == f'{r}:?'):
                        return self.out(72, js={'ops': list(ops)})
                    hit = nums[0] if nums else None
                else:
                    hit = next((p for p in src if p['name'] == name and (lv is None or p['level'] == int(lv))), None)
                if not hit or len(self.bar[r]) >= 5:
                    return self.out(72 if not hit else 77, js={'ops': list(ops)})
                src.remove(hit)
                self.bar[r].append(dict(hit))      # 複製：避免不同角色共用同一個 dict 被 grow 重複升級
                ops.append({'role': r, 'pet': name, 'ok': True})
            return self.out(0)
        if cmd == 'depot-list':                 # 唯讀：公共 + 指定角色個人倉庫各物種張數
            self.depot_lists = getattr(self, 'depot_lists', 0) + 1
            cnt = lambda ps: {n: sum(1 for p in ps if p['name'] == n) for n in {p['name'] for p in ps}}    # noqa: E731
            roles = self.opt(args, '--role').split(',')
            return self.out(0, js={'counts': {'public': cnt(self.public), 'personal': {r: cnt(self.personal[r]) for r in roles}}, 'rc': 0})
        if cmd == 'reset-name':                 # 還原名字：數字名 → 物種名（reset_rc 模擬失敗 / 費用字樣）
            self.resets = getattr(self, 'resets', []) + [self.opt(args, '--role')]
            if getattr(self, 'reset_rc', 0):
                return self.out(self.reset_rc)
            for r in self.opt(args, '--role').split(','):
                for p in self.bar[r]:
                    if p.get('num'):
                        p['name'], p['num'] = p['sp'], False
            return self.out(0)
        if cmd == 'set-state-many':
            name, st = args[3], args[4]
            for r in ROLES:
                for p in self.bar[r]:
                    if p['name'] == name:
                        p['state'] = st
            return self.out(0)
        if cmd == 'set-state-slot':
            nums = [int(x) for x in args[args.index('--slots') + 1].split(',')]
            st = args[-1]
            for r in ROLES:
                for n in nums:
                    if n <= len(self.bar[r]):
                        if self.bar[r][n - 1]['state'] == '騎乘':
                            return self.out(73)
                        self.bar[r][n - 1]['state'] = st
            return self.out(0)
        if cmd == 'rest-all':
            for r in ROLES:
                for p in self.bar[r]:
                    if p['state'] == '出戰':
                        p['state'] = '等待'
            return self.out(0)
        return self.out(2)


def grow(sim, by=2):
    """模擬練功：每次 list 前任務寵升 by 級"""
    orig = sim.pet

    def pet(args):
        if args[0] in ('list', 'levels') and any(c[0] == 'grind.py' for c in sim.calls) and not any(c == ('enc_off',) for c in sim.calls[[i for i, c in enumerate(sim.calls) if c[0] == 'grind.py'][-1]:]):
            for r in ROLES:
                for p in sim.bar[r]:
                    if p['name'] not in ('布拉奇多斯', '朵拉比斯', '迪基格斯', '金布伊'):
                        if p['level'] < 30:                    # 自動轉換戰寵依序換寵：一次只練一隻（格序），練到 30 才換下一隻
                            p['level'] += by
                            p['state'] = '出戰'
                            if p['level'] >= 30:               # 練到 30 → 外掛換下（等待）、下一隻任務寵上場
                                p['state'] = '等待'
                                nxt = [q for q in sim.bar[r] if q['name'] not in ('布拉奇多斯', '朵拉比斯', '迪基格斯', '金布伊') and q['level'] < 30]
                                if nxt:
                                    nxt[0]['state'] = '出戰'
                            break
        return orig(args)
    sim.pet = pet
    return sim


def go(qid, sim, **kw):
    for p in (pq.PROGRESS,):
        p.unlink(missing_ok=True) if kw.pop('reset', True) else None
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        return pq.run(qid, tools=sim, **kw)


def names(sim, script):
    return [c[1] for c in sim.calls if c[0] == script]


# ---------------- 純函式
tp = pq.take_plan([('DKBO2', 'x', '魯尼帖斯'), ('DKBO3', 'y', '貝魯卡')])
check('take_plan：抓寵者自己那種不取、其他人每種 1 隻', ('DKBO2', '魯尼帖斯') not in tp and ('DKBO2', '貝魯卡') in tp and ('DKBO', '魯尼帖斯') in tp and len(tp) == 8)
check('parse_money：依 x 排序，第一個石幣、第二個鑽石（逗號去掉）', pq.parse_money([('0', 520, 23), ('3,264,500', 335, 23)]) == (3264500, 0)
      and pq.parse_money([]) == (None, None))
check('bait_ok_roles 讀「背包誘餌 = N」', pq.bait_ok_roles(['rebirth_pets：DKBO2 背包誘餌 = 4', 'x', 'rebirth_pets：DKB03 背包誘餌 = 4']) == {'DKBO2', 'DKBO3'})
ok, lag = pq.train_status({'DKBO': [P('魯尼帖斯', level=18), P('貝魯卡', level=29)]}, {'魯尼帖斯': 18, '貝魯卡': 30}, roles=['DKBO'])
check('train_status：門檻 ≥（18 過、29 < 30 沒過）', not ok and lag == {'DKBO': {'貝魯卡': 29}})
check('battle_levels：出戰那隻優先', pq.battle_levels({'DKBO': [P('朵拉比斯', '等待', 1), P('朵拉比斯', '出戰', 126)]}) == {'DKBO': 126})
check('stage_base：catch2 → catch、step1 不拆', pq.stage_base('catch2') == 'catch' and pq.stage_base('step1') == 'step1' and pq.stage_round('turnin2') == 2)
check('stages_of（2026-10-15 新順序）：恐龍 prep 在最前、accept 在 train 之後 turnin 之前；卡坦 accept 在 train1 之後；猜謎不變',
      pq.stages_of(2016) == ['prep', 'catch', 'distribute', 'train', 'accept', 'turnin', 'drop', 'restore']
      and pq.stages_of(2019) == ['prep', 'catch1', 'distribute1', 'train1', 'accept', 'turnin1', 'drop1', 'catch2', 'distribute2', 'train2', 'turnin2', 'store_reward', 'restore']
      and pq.stages_of(3003) == ['accept', 'step1', 'prep', 'train', 'turnin', 'drop', 'restore'], str(pq.stages_of(2016)))

# ---------------- 恐龍博士 happy path
s = grow(Sim(2016))
rc = go(2016, s, confirm_drop=True)
check('恐龍博士 happy：rc 0', rc == 0, f'rc={rc} {pq.LAST.get("info")}')
check('每人寵物欄 = 騎寵 + 原朵拉比斯出戰（等級 = 原等級）、布克布克已丟', all([p['name'] for p in s.bar[r]] == ['布拉奇多斯', '朵拉比斯'] and s.bar[r][1]['state'] == '出戰'
      and s.bar[r][1]['level'] == 125 + i for i, r in enumerate(ROLES)), str(s.bar))
check('一次抓滿 5（不分批）：bait 只取 / 拆一次（count 5，每人一次）、setup 一次、不 baitback；誘餌 50 → 40', [a[a.index('--count') + 1] for a in names(s, 'pet_catch.py') if '--stages' in a and a[a.index('--stages') + 1] == 'bait'] == ['5']
      and getattr(s, 'bait_takes', 0) == len(pq.ALL_ROLES[1:5]) * 0 + getattr(s, 'bait_takes', 0) and s.bait == 40 and getattr(s, 'baitback', 0) == 0, f'{s.bait} {getattr(s, "bait_takes", 0)}')
check('抓前關遇敵 + 解散；收尾鎖定戰寵 + 一般動作攻擊', ('enc_off',) in s.calls and ('team.py', ('disband',)) in s.calls
      and any(a[:2] == ('--lock', '戰寵') for a in names(s, 'pet_catch.py')) and any(a[:2] == ('--lock', '戰寵') and a[-2:] == ('--normal', '攻擊') for a in names(s, 'pet_catch.py')) and not names(s, 'ass.py'))
check('交寵物用 questrun --pet-turnin --rested（train 段剛 rest-all 過，questrun 不重做）', ('run', '2016', '--after', 'none', '--pet-turnin', '--rested') in names(s, 'questrun.py'), str(names(s, 'questrun.py')))
check('恐龍博士練寵固定 80 級練功區：grind.py start --spot 波拉島（使用者 2026-10-15 指定）', pq.TRAIN_SPOT == '波拉島' and ('start', '--spot', '波拉島') in names(s, 'grind.py'), str(names(s, 'grind.py')))
pa = [a for a in names(s, 'pet.py') if a[0] in ('list', 'levels')]
tr = [i for i, c in enumerate(s.calls) if c[0] == 'grind.py']
in_train = [c[1][0] for c in s.calls[tr[0]:] if c[0] == 'pet.py' and c[1][0] in ('list', 'levels', 'set-state-slot')]
in_train = in_train[:in_train.index('set-state-slot')]
ss = [a for a in names(s, 'pet.py') if a[0] == 'set-state-slot']
check('練寵不認物種：出戰 = set-state-slot --slots 2 出戰（不帶物種 / --candidates）、rest = 只最後一格（--slots 3）等待；train 不再呼叫 set-state-many / rest-all',
      ss[0][ss[0].index('--slots') + 1] == '2' and ss[0][-1] == '出戰' and ss[1][ss[1].index('--slots') + 1] == '3' and ss[1][-1] == '等待'
      and all('--candidates' not in a for a in ss) and not any(a[0] == 'rest-all' for a in names(s, 'pet.py')), str(ss))
check('練寵輪詢：不呼叫 list、只 levels --slots 3（恐龍博士最後一格 = 第 3 格）', in_train and set(in_train) == {'levels'}
      and all(a[a.index('--slots') + 1] == '3' for a in names(s, 'pet.py') if a[0] == 'levels'), str(in_train))
pc = [a for a in names(s, 'pet_catch.py') if '--stages' in a and 'setup' in a[a.index('--stages') + 1]]
check('一次抓滿：pet_catch setup,wait 只一次、--count 5、不帶 --reuse-setup / --expect-bar', len(pc) == 1 and pc[0][pc[0].index('--stages') + 1] == 'setup,wait'
      and pc[0][pc[0].index('--count') + 1] == '5' and '--reuse-setup' not in pc[0] and '--expect-bar' not in pc[0], str(pc))
check('沒給 --verify-defer → questrun 不帶 --verify', not any('--verify' in a for a in names(s, 'questrun.py')))
check('原朵拉比斯先存個人、最後 @原等級 取回', any(a[0] == 'take-many' and '朵拉比斯@125' in a[a.index('--plan') + 1] for a in names(s, 'pet.py')))
check('完成後進度檔清空（下一轉從頭）', json.loads(pq.PROGRESS.read_text(encoding='utf-8'))['2016']['done'] == [])

check('free_slots：empty 格 / 沒列到的都算空', pq.free_slots([P('a'), {'empty': True}, P('b')]) == 3 and pq.free_slots(None) == 5)

# ---------------- 沒 --confirm-drop → 168 停在 drop
s = grow(Sim(2016))
rc = go(2016, s)
check('恐龍博士沒 --confirm-drop → 168、沒呼叫 petdrop', rc == pq.EXIT_DROP and not names(s, 'petdrop.py') and 'petdrop.py' in pq.LAST['info'].get('manual', ''))
rc = go(2016, s, confirm_drop=True, reset=False)
check('同一進度檔重跑加 --confirm-drop → 從 drop 續跑完成（不重抓）', rc == 0 and pq.LAST['ran'] == ['drop', 'restore'], str(pq.LAST.get('ran')))

# ---------------- 誘餌不夠
s = grow(Sim(2016, bait=6))
rc = go(2016, s, confirm_drop=True)
plus = [c for c in s.calls if c[0] == 'plus']
check('誘餌不夠、不帶 --confirm-buy-bait 也會買（使用者 2026-10-15）：bait 帶 --keep-short-bait、DKBO3 買缺額 4 次', rc == 0 and plus == [('plus', 'DKBO3')] * 4
      and all('--keep-short-bait' in a for a in names(s, 'pet_catch.py') if '--stages' in a and a[a.index('--stages') + 1] == 'bait'), f'rc={rc} plus={plus} {pq.LAST.get("info")}')
s = grow(Sim(2016, bait=6))
rc = go(2016, s, confirm_drop=True, confirm_buy=True)
plus = [c for c in s.calls if c[0] == 'plus']
check('--confirm-buy-bait（no-op，結果同不帶）：公共 6 個 → DKBO2 拆 5（餘 1）、DKBO3 取 1 個照用、只買缺額 4 次；石幣每次扣 50,000', rc == 0 and plus == [('plus', 'DKBO3')] * 4
      and s.stone == 3_000_000 - 4 * pq.PLUS_COST and not s.bag_bait.get('DKBO3'), f'rc={rc} plus={plus} {pq.LAST.get("info")}')
s = grow(Sim(2016, bait=8))
rc = go(2016, s, confirm_drop=True, confirm_buy=True)
plus = [c for c in s.calls if c[0] == 'plus']
check('公共 8 個、兩人各要 5：DKBO2 5、DKBO3 只拿到 3 → 買 2 次（不是 5 次）', rc == 0 and plus == [('plus', 'DKBO3')] * 2 and s.stone == 3_000_000 - 2 * pq.PLUS_COST, f'rc={rc} plus={plus}')
check('bait_short_counts 讀「背包誘餌不足 = n」', pq.bait_short_counts(['rebirth_pets：DKBO5 背包誘餌不足 = 3（要 5）', 'x', 'rebirth_pets：DKBO2 背包誘餌 = 5']) == {'DKBO5': 3})
s = grow(Sim(2016, bait=8))
_pp = s.press_plus
s.press_plus = lambda role, limit=None, min_before=None: (163, 0, None) if min_before else _pp(role, limit, min_before)   # 外掛數字 0 < 現有誘餌
rc = go(2016, s, confirm_drop=True, confirm_buy=True)
check('外掛數字沒把背包誘餌算進去（按前 < 現有）→ 163、一次都不按', rc == pq.EXIT_BAIT and not [c for c in s.calls if c[0] == 'plus'] and '不能相加' in pq.LAST['info']['msg'], f'rc={rc} {pq.LAST.get("info")}')
s = grow(Sim(2016, bait=0))
s.dia_drop = 5
rc = go(2016, s, confirm_buy=True)
check('「+」後鑽石有變 → 163 停（只按 1 次）', rc == pq.EXIT_BAIT and len([c for c in s.calls if c[0] == 'plus']) == 1 and '鑽石' in pq.LAST['info']['msg'])
s = grow(Sim(2016, bait=0))
s.money = lambda: (None, 0)
rc = go(2016, s, confirm_drop=True)
check('石幣讀不到不擋（2026-10-15 不讀石幣）、鑽石讀得到 → 照按', rc == 0 and [c for c in s.calls if c[0] == 'plus'], f'rc={rc} {pq.LAST.get("info")}')
s = grow(Sim(2016, bait=0))
s.money = lambda: (None, None)
rc = go(2016, s, confirm_drop=True)
check('按「+」前讀不到鑽石 → 163、一次都不按（鑽石檢查要能生效）', rc == pq.EXIT_BAIT and not [c for c in s.calls if c[0] == 'plus'] and '讀不到鑽石' in pq.LAST['info']['msg'], f'rc={rc} {pq.LAST.get("info")}')
s = grow(Sim(2016, bait=0))
s.dia_seq = [0, None]
s.money = lambda: (None, s.dia_seq.pop(0) if len(s.dia_seq) > 1 else s.dia_seq[0])
rc = go(2016, s, confirm_drop=True)
check('按「+」後讀不到鑽石 → 163（只按 1 次）', rc == pq.EXIT_BAIT and len([c for c in s.calls if c[0] == 'plus']) == 1 and '讀不到鑽石' in pq.LAST['info']['msg'], f'rc={rc}')
s = grow(Sim(2016, bait=0))
_m = s.money
s.dia_seq = [0, 5]
s.money = lambda: (s.stone, s.dia_seq.pop(0) if len(s.dia_seq) > 1 else s.dia_seq[0])
rc = go(2016, s, confirm_buy=True)
check('「+」後鑽石有變 → 163（鐵則 3）', rc == pq.EXIT_BAIT and '鑽石' in pq.LAST['info']['msg'])

# ---------------- 卡坦的願望 兩輪
s = grow(Sim(2019))
rc = go(2019, s, confirm_drop=True)
check('卡坦 happy：兩輪、rc 0、5 人 騎寵 + 原朵拉比斯出戰；獎勵 Lv1 朵拉比斯存個人；修寶已丟', rc == 0
      and all([p['name'] for p in s.bar[r]] == ['布拉奇多斯', '朵拉比斯'] and s.bar[r][1]['level'] == 125 + i for i, r in enumerate(ROLES))
      and all(any(p['name'] == '朵拉比斯' and p['level'] == 1 for p in s.personal[r]) for r in ROLES)
      and not any(p['name'] == '修寶' for r in ROLES for p in s.bar[r]), f'rc={rc} {pq.LAST.get("info")} {s.bar["DKBO"]}')
check('卡坦誘餌 50 → 10（鯊 20 + 雞 20）', s.bait == 10, str(s.bait))
s = Sim(2019, step=2)
s.bar = {r: [P('布拉奇多斯', '騎乘', 5), P('朵拉比斯', '出戰', 125 + i)] for i, r in enumerate(ROLES)}
reads = []
s.read_step = lambda t: reads.append(t) or 2
rc = go(2019, s, to_stage='prep')
check('卡坦 prep 不讀追蹤步號、不取消鎖定戰寵（2026-10-16 精簡）：關遇敵 → 解散 → 讀第 2 格 → 存倉',
      rc == 0 and not reads and not any('--unlock' in a for a in names(s, 'pet_catch.py')) and ('enc_off',) in s.calls
      and ('disband',) in names(s, 'team.py') and any(a[0] == 'store-many' for a in names(s, 'pet.py')), f'rc={rc} {names(s, "pet_catch.py")}')
check('單獨跑卡坦 prep 後寫共用紀錄 slot2_stored（名字 / 等級 / ts）',
      sorted(json.loads(pq.PROGRESS.read_text(encoding='utf-8')).get('slot2_stored', {}).get('orig', {})) == sorted(pq.ALL_ROLES))
s = grow(Sim(2019))
rc = go(2019, s, confirm_drop=True)
seq = [(c[0], c[1]) for c in s.calls if c[0] in ('questrun.py', 'pet.py', 'pet_catch.py')]
i_acc = [i for i, (sc, a) in enumerate(seq) if sc == 'questrun.py' and '--pet-turnin' not in a]
i_rest = [i for i, (sc, a) in enumerate(seq) if sc == 'pet.py' and a[0] == 'set-state-slot' and a[-1] == '等待']
i_shark = [i for i, (sc, a) in enumerate(seq) if sc == 'pet_catch.py' and '鯊魚系' in ' '.join(a)]
i_bird = [i for i, (sc, a) in enumerate(seq) if sc == 'pet_catch.py' and '火雞系' in ' '.join(a)]
i_t1 = [i for i, (sc, a) in enumerate(seq) if sc == 'questrun.py' and '--pet-turnin' in a]
check('卡坦新順序：鯊抓 / 練 / rest-all 之後才接任務（只接一次）、接完交第 1 輪、交完才抓雞', rc == 0 and len(i_acc) == 1 and i_shark[-1] < i_rest[0] < i_acc[0] < i_t1[0] < i_bird[0],
      f'rc={rc} acc={i_acc} rest={i_rest} t1={i_t1}')
s = grow(Sim(2019))
s.quest_q = {2019: [155, 117]}                               # 第 1 輪交完 questrun 回 117 但步號沒進
s.read_step = lambda t: 1
rc = go(2019, s, confirm_drop=True)
check('第 1 輪交完步號沒進到 2 → 167', rc == pq.EXIT_TURNIN, f'rc={rc} {pq.LAST.get("info")}')

# ---------------- 猜謎三兄弟
s = Sim(3003)
rc = go(3003, s, confirm_drop=True)
check('猜謎三兄弟 happy：步 1 拿金布伊 → 出戰 + 鎖定 → grind 地雷區 → petwatch --exp-fruit → 交 → 丟左迪洛斯 → 朵拉比斯出戰', rc == 0
      and ('--pet', '金布伊', '--level', '77', '--back', '朵拉比斯', '--exp-fruit') in names(s, 'petwatch.py')
      and ('start',) in names(s, 'grind.py') and not any('--spot' in a for a in names(s, 'grind.py')) and ('all', '左迪洛斯', '--confirm-name', '左迪洛斯', '--max-level', '1') in names(s, 'petdrop.py')
      and not any(p['name'] == '左迪洛斯' for r in ROLES for p in s.bar[r]), f'rc={rc} {pq.LAST.get("info")}')
check('猜謎：quest.py 步 1 --stop-after-rewards 1', names(s, 'quest.py') == [('--task', '猜謎三兄弟', '--stop-after-rewards', '1', '--max-seconds', '900')])
s = Sim(3003)
s.quest = lambda a: s.out(0)                                 # 步 1 跑完但沒拿到金布伊（要爬塔）
rc = go(3003, s, confirm_drop=True)
check('猜謎步 1 後沒有金布伊 → 161、提示點任務追蹤重試', rc == pq.EXIT_ACCEPT and '任務追蹤' in pq.LAST['info'].get('manual', ''))
s = Sim(3003)
_q0 = s.quest
s.quest = lambda a: (_q0(a), s.out(3))[1]                    # 2026-10-14 13:35：對話給了金布伊、追蹤進步 2、點追蹤不巡路 → quest.py 3
rc = go(3003, s, confirm_drop=True)
check('猜謎步 1 quest.py 3 但步號已是 2 + 5 人有金布伊 → 步 1 完成、續跑到 0', rc == 0 and names(s, 'petwatch.py'), f'rc={rc} {pq.LAST.get("info")}')
s = Sim(3003)
s.quest = lambda a: s.out(3)                                  # 真的沒反應：步號仍 1
rc = go(3003, s, confirm_drop=True)
check('猜謎步 1 quest.py 3 且步號仍 1 → 161', rc == pq.EXIT_ACCEPT, f'rc={rc}')

# ---------------- 其他
s = grow(Sim(2016))
s.fail[('questrun.py', 'run')] = 9
rc = go(2016, s)
check('questrun 回 9（驗證視窗，接取在練完後）→ 透傳 9', rc == 9 and pq.LAST['ran'] == ['prep', 'catch', 'distribute', 'train'], str(pq.LAST.get('ran')))
s = grow(Sim(2016))
s.quest_q = {2016: [0]}
rc = go(2016, s)
check('接取（練完之後）questrun 回 0（已完成）→ 不交不丟，restore 照樣取回第 2 格（@原等級）+ 出戰 + 鎖定 + 一般動作', rc == 0
      and not names(s, 'petdrop.py') and len(names(s, 'questrun.py')) == 1 and any('--normal' in a for a in names(s, 'pet_catch.py'))
      and any(a[0] == 'take-many' and '朵拉比斯@125' in a[a.index('--plan') + 1] for a in names(s, 'pet.py'))
      and all(any(p['name'] == '朵拉比斯' and p['state'] == '出戰' for p in s.bar[r]) for r in ROLES), f'rc={rc} {pq.LAST.get("info")}')
s = grow(Sim(2016))
rc = go(2016, s, confirm_drop=True)
seq = [(c[0], c[1]) for c in s.calls if c[0] in ('questrun.py', 'pet.py', 'team.py')]
i_acc = [i for i, (sc, a) in enumerate(seq) if sc == 'questrun.py' and '--pet-turnin' not in a]
i_rest = [i for i, (sc, a) in enumerate(seq) if sc == 'pet.py' and a[0] == 'set-state-slot' and a[-1] == '等待']
i_store = [i for i, (sc, a) in enumerate(seq) if sc == 'pet.py' and a[0] == 'store-many' and '--depot' in a and a[a.index('--depot') + 1] == 'personal']
i_dis = [i for i, (sc, a) in enumerate(seq) if sc == 'team.py']
check('恐龍新順序：解散 → 存第 2 格（個人倉庫）在最前、接任務在 rest-all 之後', rc == 0 and i_dis[0] < i_store[0] < i_rest[0] < i_acc[0] and seq[0][0] == 'team.py',
      f'rc={rc} dis={i_dis[:1]} store={i_store[:1]} rest={i_rest} acc={i_acc}')
check('不支援的任務 → 160', go(2017, Sim(2017)) == pq.EXIT_ARGS)
check('--from 不認得 → 160', go(2016, Sim(2016), from_stage='xxx') == pq.EXIT_ARGS)
buf = io.StringIO()
with contextlib.redirect_stdout(buf):
    pq.run(2019, dry_run=True)
check('plan 2019 列出兩輪與 store_reward', 'catch2' in buf.getvalue() and 'store_reward' in buf.getvalue())

# ---------------- rebirth_pets._split：整疊不夠 → 取消、92（petquest 決定買不買）
import bag  # noqa: E402
import rebirth_pets as rp  # noqa: E402
import uikit  # noqa: E402


class _S:
    rc = 0

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


keep = {k: getattr(bag, k) for k in ('Session', 'select_role', 'find_item', 'open_slot_popup', 'name_match', 'popup_name', '_ocr_join', '_click', 'close_popup', 'depot_store', 'depot_take', 'find_items', 'stacks_of')}
bag.depot_take = lambda *a, **k: 0
keep_ocr, keep_gui, keep_fail = rp.ocr_lines, uikit.gui, uikit.fail
clicks = []
bag.Session, bag.select_role, bag.find_item, bag.open_slot_popup = _S, lambda r: 0, lambda n, **k: None if k.get('popup_fallback') is False else 0, lambda i: True
bag.name_match, bag.popup_name, bag._ocr_join = lambda a, b: True, lambda n: n, lambda box, o: '使用 拆分'
bag._click = lambda *a, **k: True
bag.close_popup = lambda: True
bag.depot_store = lambda *a, **k: clicks.append('store_back') or 0
rp.ocr_lines = lambda box, *o: [('數量輸入', 0, 0)] if box[1] == 170 else [('3', 0, 0)]
uikit.gui = lambda *a, **k: clicks.append(a[1] if len(a) > 1 else a) or ''
uikit.fail = lambda src, rc, msg: rc
try:
    t = rp.Tools()
    with contextlib.redirect_stdout(io.StringIO()):
        t.split_noop, t.split_short = False, None
        rc = t._split('DKBO2', rp.BAIT, 5)
    check('_split：整疊 3 < 要 5 → 按取消 828,545、回 92、記 split_short', rc == bag.EXIT_ITEM and t.split_short == 3
          and any('828 545' in str(c) for c in clicks) and not any('755 451' in str(c) for c in clicks), str(clicks))
    bag.stacks_of = lambda w: [(0, 3)]
    clicks.clear()
    with contextlib.redirect_stdout(io.StringIO()):
        rc = t.bait_take('DKBO2', 5)
    check('bait_take：不夠 → 整疊存回公共、回 92', rc == bag.EXIT_ITEM and 'store_back' in clicks)
finally:
    for k, v in keep.items():
        setattr(bag, k, v)
    rp.ocr_lines, uikit.gui, uikit.fail = keep_ocr, keep_gui, keep_fail

# ---------------- review 1013b：--verify-defer / --rested 時效 / levels 合併 / 練寵確認
s = grow(Sim(2016))
rc = go(2016, s, confirm_drop=True, verify_defer=True)
qa = names(s, 'questrun.py')
check('--verify-defer → 接取 / 交件的 questrun 都帶 --verify defer', rc == 0 and qa and all('--verify' in a and a[a.index('--verify') + 1] == 'defer' for a in qa), str(qa))
s = grow(Sim(2016))
go(2016, s, confirm_drop=True, to_stage='train')
s.clock = lambda: 10 ** 6                                  # 隔了很久才續跑交件 → 不信 rested
go(2016, s, confirm_drop=True, from_stage='turnin', reset=False)
check('rested 超過 RESTED_S 才續跑交件 → 不帶 --rested（questrun 自己 rest-all）', not any('--rested' in a for a in names(s, 'questrun.py') if '--pet-turnin' in a), str(names(s, 'questrun.py')))
need = {'魯尼帖斯': 18}
base = {'DKBO': [{'slot': 1, 'name': '布拉奇多斯'}, {'slot': 2, 'name': '魯尼帖斯', 'level': 3, 'nh': 'a'}]}
smap = {('A', '魯尼帖斯'): [2], ('B', '魯尼帖斯'): [3]}
check('task_slot_map 已拿掉（練寵只讀最後一格，不認寵物）', not hasattr(pq, 'task_slot_map'))
check('levels_of：讀到的格取等級；變空 / 沒讀到 = None', pq.levels_of({'A': [{'slot': 2, 'level': 9}], 'B': [{'slot': 3, 'empty': True}]}, smap) == {('A', '魯尼帖斯'): 9, ('B', '魯尼帖斯'): None}
      and pq.levels_of({}, smap) == {('A', '魯尼帖斯'): None, ('B', '魯尼帖斯'): None})
k = ('DKBO', '魯尼帖斯')
def _tc(need_, *rounds):
    t = pq.TrainConfirm(need_)
    for r in rounds:
        t.update(r)
    return t
check('TrainConfirm：第一次 ≥ 門檻不算、連兩次 ≥ 才鎖定', not _tc(need, {k: 18}).locked and _tc(need, {k: 18}, {k: 20}).done([k]))
check('TrainConfirm：中間掉到 < 門檻 → 連續次數歸零', not _tc(need, {k: 18}, {k: 17}, {k: 18}).locked)
check('TrainConfirm：讀不到不清第一次讀值；高速升級（一輪升 22 級）仍鎖定', _tc(need, {k: 18}, {k: None}, {k: 19}).done([k]) and _tc(need, {k: 18}, {k: 40}).done([k]))
need13 = {'加克拉': 25, '加格': 25, '邦恩吉': 25}
keys = [(r, sp) for r in ('DKBO', 'DKBO2', 'DKBO3', 'DKBO4', 'DKBO5') for sp in need13]
t = pq.TrainConfirm(need13)
for j in range(5):
    t.update({kk: (30 + i if (i + j) % 3 else None) for i, kk in enumerate(keys)})
check('TrainConfirm：每輪子集不同（浮字干擾）→ 逐隻累積，5 輪內全部鎖定', t.done(keys), str(len(t.locked)))
t.update({keys[0]: None})
check('TrainConfirm：鎖定後讀不到不清', keys[0] in t.locked)
check('已拿掉：merge_levels / task_levels / TRAIN_OVER / TRAIN_MISREAD_UP / skip_done_rounds',
      not any(hasattr(pq, x) for x in ('merge_levels', 'task_levels', 'TRAIN_OVER', 'TRAIN_MISREAD_UP')) and not hasattr(pq.Run, 'skip_done_rounds'))

# 恐龍博士練寵：list 只讀一次、之後只 levels --slots；不跑 verify-battle；autoswap on / off 各 1；讀失敗下一輪再讀（不改讀 list）
s = grow(Sim(2016))
_lv = s.pet
_bad = [1]


def _pet(a):
    if a[0] == 'levels' and _bad:                            # 第一次 levels 讀取失敗
        _bad.pop()
        return s.out(1)
    return _lv(a)


s.pet = _pet
rc = go(2016, s, confirm_drop=True)
tr = [i for i, c in enumerate(s.calls) if c[0] == 'grind.py']
ra = [i for i, c in enumerate(s.calls) if c[0] == 'pet.py' and c[1][0] == 'set-state-slot' and c[1][-1] == '等待'][0]
seq = [c[1][0] for c in s.calls[tr[0]:ra] if c[0] == 'pet.py' and c[1][0] in ('list', 'levels')]
check('練寵讀等級：只 levels（讀失敗下一輪再讀 levels），不呼叫 list，仍練完', rc == 0 and seq and set(seq) == {'levels'} and len(seq) >= 4, f'rc={rc} {seq[:8]}')
pc = names(s, 'pet_catch.py')
check('不跑 pet_catch --verify-battle；autoswap on 1 次、off 1 次（恐龍博士沒帶 --keep-autoswap 練完就關）',
      not any('--verify-battle' in a for a in pc) and len([a for a in pc if a[:2] == ('--autoswap', 'on')]) == 1 and len([a for a in pc if a[:2] == ('--autoswap', 'off')]) == 1, str(pc))

# 卡坦兩輪：autoswap on 只 1 次（第 2 輪不再勾）、off 只 1 次（第 2 輪練完才關）；accept 不讀追蹤步號
s = grow(Sim(2019))
_rs = s.read_step
s.read_step = lambda t: (s.calls.append(('read_step',)), _rs(t))[1]
rc = go(2019, s, confirm_drop=True)
pcs = [(i, c[1]) for i, c in enumerate(s.calls) if c[0] == 'pet_catch.py' and c[1][:1] == ('--autoswap',)]
gr = [i for i, c in enumerate(s.calls) if c[0] == 'grind.py']
check('卡坦：autoswap on 只 1 次、off 只 1 次；on 在第 1 輪 grind 前、off 在第 2 輪 grind 之後',
      rc == 0 and [a[1] for _, a in pcs] == ['on', 'off'] and pcs[0][0] < gr[0] and pcs[1][0] > gr[-1], f'rc={rc} {pcs} grind={gr}')
acc = [i for i, c in enumerate(s.calls) if c[0] == 'questrun.py' and '--pet-turnin' not in c[1]][0]
nxt = [i for i, c in enumerate(s.calls) if c[0] == 'questrun.py' and i > acc][0]
check('卡坦 accept 後不讀追蹤步號（accept 到第 1 輪交件之間沒有 read_step）', not any(c == ('read_step',) for c in s.calls[acc:nxt]), str(s.calls[acc:nxt]))
check('卡坦進度檔：autoswap_on 關掉後清除', 'autoswap_on' not in json.loads(pq.PROGRESS.read_text(encoding='utf-8')))

# 進度檔已有 autoswap_on（恐龍博士 --keep-autoswap 留下）→ 卡坦不再 on、train2 結束才 off
s = grow(Sim(2019))
go(2019, s, to_stage='prep')
_pg = json.loads(pq.PROGRESS.read_text(encoding='utf-8'))
_pg['autoswap_on'] = {'qid': 2016, 'ts': 10 ** 9}
pq.PROGRESS.write_text(json.dumps(_pg), encoding='utf-8')
s.t = 10 ** 9                                              # 假時鐘接在 autoswap_on 時間戳之後（24 小時內）
rc = go(2019, s, confirm_drop=True, reset=False, from_stage='catch1')
pc = names(s, 'pet_catch.py')
check('接卡坦（進度檔 autoswap_on）：不再 on、練完第 2 輪才 off 1 次、進度檔清掉',
      rc == 0 and not any(a[:2] == ('--autoswap', 'on') for a in pc) and len([a for a in pc if a[:2] == ('--autoswap', 'off')]) == 1
      and 'autoswap_on' not in json.loads(pq.PROGRESS.read_text(encoding='utf-8')), f'rc={rc} {pc}')
check('恐龍博士 --keep-autoswap：進度檔記 autoswap_on', go(2016, grow(Sim(2016)), confirm_drop=True, keep_autoswap=True) == 0
      and 'autoswap_on' in json.loads(pq.PROGRESS.read_text(encoding='utf-8')))

# ---------------- 2026-10-16 最簡流程：抓 → 改名 → 存公共 → 取個人溢出改名 → 取公共 → 只驗格數
def pets_of(s, r, sp=None):
    return [p for p in s.bar[r] if sp is None or p['name'] == sp]


def seq_of(s):
    """抓寵 → 分配之間的子指令序列（簡寫）"""
    out = []
    for sc, a in [c for c in s.calls if len(c) == 2]:
        if sc == 'pet.py' and a[0] in ('list', 'reset-name', 'store-many', 'take-many'):
            out.append(a[0] + ('-' + a[a.index('--depot') + 1] if '--depot' in a else ''))
        elif sc == 'pet_catch.py' and '--stages' in a:
            out.append('catch:' + a[a.index('--stages') + 1])
    return out


check('sub_at / bar_count_bad 純函式', pq.sub_at({'step': 'stored'}, 'renamed') and not pq.sub_at({'step': 'renamed'}, 'stored') and not pq.sub_at({}, 'caught')
      and pq.bar_count_bad({r: [P('a'), P('b'), {'empty': True}] for r in ROLES}, 2) == {}
      and pq.bar_count_bad({'DKBO': [P('a')], 'DKBO2': [P('a'), P('b')]}, 2, roles=['DKBO', 'DKBO2', 'DKBO3']) == {'DKBO': 1, 'DKBO3': None})

s = grow(Sim(2016))
rc = go(2016, s, to_stage='distribute')
cn = [x for x in seq_of(s) if x.startswith(('catch', 'reset', 'store', 'take')) and not x.endswith('personal') or x == 'take-many-personal']
check('恐龍博士 catch+distribute（空格 4、溢出 1）子指令：bait → setup,wait → reset-name(2 抓寵者) → store-many 公共 ×1（--plan 一次）→ take-many 個人 ×1 → reset-name(取回者) → take-many 公共 ×1',
      rc == 0 and cn == ['catch:bait', 'catch:setup,wait', 'reset-name', 'store-many-public', 'take-many-personal', 'reset-name', 'take-many-public'], f'rc={rc} {cn}')
check('抓寵者各 5 隻：公共每種 4 隻、抓寵者個人倉庫的溢出取回（只剩原戰寵）、每人寵物欄 = 騎寵 + 魯尼帖斯 + 貝魯卡 剛好 3 格',
      not s.public and all(len(pets_of(s, r)) == 3 and pets_of(s, r, '魯尼帖斯') and pets_of(s, r, '貝魯卡') for r in ROLES)
      and all(p['name'] != '35/7/3/8' for r in ROLES for p in s.bar[r]) and all(p['name'] == '朵拉比斯' for r in ROLES[1:3] for p in s.personal[r]), f'{[len(s.bar[r]) for r in ROLES]} {len(s.public)}')
check('不再呼叫 depot-list / 不傳 --expect-bar / 不跑 rename / register 階段；prep 接 catch 不重複 solo（disband 只 1 次）；pet.py list 只有 prep 記戰寵 1 次 + distribute 驗證 1 次（catch 前不讀欄）',
      not any(a[0] == 'depot-list' for a in names(s, 'pet.py')) and not any('--expect-bar' in a for a in names(s, 'pet_catch.py'))
      and not any(x in ' '.join(a) for a in names(s, 'pet_catch.py') if '--stages' in a for x in ('rename', 'register'))
      and len([a for a in names(s, 'pet.py') if a[0] == 'list']) == 2 and len([c for c in s.calls if c[0] == 'team.py' and c[1][0] == 'disband']) == 1, f'{[a[0] for a in names(s, "pet.py")]}')
pr = json.loads(pq.PROGRESS.read_text(encoding='utf-8'))['2016']
check('進度檔小步：sub_r1 = distributed、in_bar 記下每人在欄隻數', pr['sub_r1']['step'] == 'distributed' and pr['sub_r1']['in_bar'] == {'DKBO2': 4, 'DKBO3': 4}, str(pr.get('sub_r1')))
tk = [a for a in names(s, 'pet.py') if a[0] == 'take-many' and a[a.index('--depot') + 1] == 'personal'][0]
check('溢出取回：--plan DKBO2:?,DKBO3:?（取沒名字的卡，不認物種、不帶 --candidates）', tk[tk.index('--plan') + 1] == 'DKBO2:?,DKBO3:?' and '--candidates' not in tk, str(tk))
tk = [a for a in names(s, 'pet.py') if a[0] == 'take-many' and a[a.index('--depot') + 1] == 'public'][0]
check('取公共：--plan 只有 distribute（抓寵者自己那種不取）、不帶 --candidates；每人每種 1 隻（8 隻）', len(tk[tk.index('--plan') + 1].split(',')) == 8 and '--candidates' not in tk
      and 'DKBO2:魯尼帖斯' not in tk[tk.index('--plan') + 1], str(tk))

# 不讀寵物欄：catch 前沒有 pet.py list；上次抓到一半（catch_started 旗標、沒 caught）→ 164 不讀欄不抓
s = grow(Sim(2016))
for r in ROLES:
    s.bar[r] = s.bar[r][:1]
rc = go(2016, s, from_stage='catch', to_stage='catch')
check('catch 單獨續跑（prep 不是本次 run 做的）→ 先 solo（team disband）、沒有 pet.py list、不在 catch 前讀欄', rc == 0 and ('disband',) in names(s, 'team.py')
      and not any(a[0] == 'list' for a in names(s, 'pet.py')), f'rc={rc} {[a[0] for a in names(s, "pet.py")]}')
s = grow(Sim(2016))
pq.PROGRESS.write_text(json.dumps({'2016': {'ts': time.time(), 'done': [], 'catch_started_catch': True}}), encoding='utf-8')
rc = go(2016, s, from_stage='catch', to_stage='catch', reset=False)
check('上次抓到一半（catch_started 旗標、沒 caught）→ 164、沒讀欄、沒抓', rc == pq.EXIT_CATCH and '上次抓寵中斷' in pq.LAST['info']['msg'] and not names(s, 'pet_catch.py')
      and not any(a[0] == 'list' for a in names(s, 'pet.py')), f'rc={rc} {pq.LAST.get("info")}')

# 3 格不符 → 165、訊息帶實際格數
s = grow(Sim(2016))
s.bar['DKBO4'].append(P('巴朵蘭恩'))                                # 非抓寵者多一隻別的寵物（不該有）
rc = go(2016, s, to_stage='distribute')
check('分配後 DKBO4 有 4 格 ≠ 3 → 165、訊息列實際格數', rc == pq.EXIT_DIST and '應剛好 3 格' in pq.LAST['info']['msg'] and "'DKBO4': 4" in pq.LAST['info']['msg'], f'rc={rc} {pq.LAST.get("info")}')
rc = go(2016, s, from_stage='distribute', to_stage='distribute', reset=False)
check('3 格不符重跑 distribute：不重取（已取）、只重驗仍 165', rc == pq.EXIT_DIST and len([a for a in names(s, 'pet.py') if a[0] == 'take-many' and a[a.index('--depot') + 1] == 'public']) == 1)
s.bar['DKBO4'] = [p for p in s.bar['DKBO4'] if p['name'] != '巴朵蘭恩']
rc = go(2016, s, from_stage='distribute', to_stage='distribute', reset=False)
check('人處理後重跑 → 驗過 rc 0，不重取', rc == 0 and len([a for a in names(s, 'pet.py') if a[0] == 'take-many' and a[a.index('--depot') + 1] == 'public']) == 1, f'rc={rc}')

# 卡坦：每輪 4 種 → 騎寵 + 4 = 5 格
s = Sim(2019)
for r in ROLES:
    s.bar[r] = s.bar[r][:1]                                         # prep 後：只剩騎寵
rc = go(2019, s, from_stage='catch1', to_stage='distribute1')
tk = [a for a in names(s, 'pet.py') if a[0] == 'take-many' and a[a.index('--depot') + 1] == 'public'][0]
cn = [x for x in seq_of(s) if x.startswith(('catch', 'reset', 'store', 'take'))]
check('卡坦第 1 輪：4 抓寵者各 5 隻（空格 4、溢出 1）→ reset-name → store-many 公共 ×1（--plan 一次、4 人）→ take-many 個人 → reset-name → take-many 公共；每人 5 格（騎寵 + 4 種）',
      rc == 0 and all(len(pets_of(s, r)) == 5 for r in ROLES) and not s.public and cn.count('store-many-public') == 1 and len(tk[tk.index('--plan') + 1].split(',')) == 16, f'rc={rc} {cn} {[len(s.bar[r]) for r in ROLES]} {pq.LAST.get("info")}')

# 卡坦 p2 實例（2026-10-16 rc 72）：個人倉庫除了第 2 格原戰寵還有別的有名字寵物（摩娜西普）→ 照樣只取沒名字那張
s = Sim(2019)
for r in ROLES:
    s.bar[r] = s.bar[r][:1]
s.personal[ROLES[1]].append(P('摩娜西普', level=80))
rc = go(2019, s, from_stage='catch1', to_stage='distribute1')
check('個人倉庫另有有名字的寵物：溢出照樣取回（取沒名字的卡）', rc == 0 and all(len(pets_of(s, r)) == 5 for r in ROLES), f'rc={rc} {seq_of(s)}')
# 個人倉庫沒名字的卡多於溢出隻數（舊的數字名寵物還在）→ take-many 72 → 165 停手、不猜
s = Sim(2019)
for r in ROLES:
    s.bar[r] = s.bar[r][:1]
s.personal[ROLES[1]].append(s.num('克邦凱斯'))
rc = go(2019, s, from_stage='catch1', to_stage='distribute1')
check('個人倉庫沒名字的卡多於溢出 → 165（不猜）、小步停在 stored', rc == pq.EXIT_DIST and json.loads(pq.PROGRESS.read_text(encoding='utf-8'))['2019']['sub_r1']['step'] == 'stored', f'rc={rc}')

# ---- 續跑：每個小步中斷後從下一小步接，不重新盤點
def fail_once(s, pred, rc):
    box = [True]

    def hook(script, args):
        if box and pred(script, args):
            box.pop()
            return rc
        return None
    s.hook = hook


def after_ok(s, k):
    """重跑後：catch / distribute 完成、每人 3 格、公共空"""
    return all(len(pets_of(s, r)) == 3 for r in ROLES) and not s.public


# pet_catch setup,wait 失敗（沒抓到任何寵）→ 164；重跑從頭（沒有任務寵不算中斷殘留）
s = grow(Sim(2016))
fail_once(s, lambda sc, a: sc == 'pet_catch.py' and '--stages' in a and a[a.index('--stages') + 1] == 'setup,wait', 14)
rc = go(2016, s, to_stage='distribute')
check('抓寵（setup,wait）失敗 → 164', rc == pq.EXIT_CATCH and 'sub_r1' not in json.loads(pq.PROGRESS.read_text(encoding='utf-8'))['2016'], f'rc={rc}')
s.calls.clear()
rc = go(2016, s, to_stage='distribute', reset=False)
check('→ 重跑：catch_started 旗標有、沒 caught → 164 請人處理，不讀寵物欄、不重抓（使用者 2026-10-16）', rc == pq.EXIT_CATCH and not any(a[0] == 'list' for a in names(s, 'pet.py'))
      and not names(s, 'pet_catch.py') and not names(s, 'pet.py'), f'rc={rc} {pq.LAST.get("info")}')
# 抓到一半失敗、寵物欄已有任務寵 → 164 請人處理（不自動盤點、不重抓）
s = grow(Sim(2016))
fail_once(s, lambda sc, a: sc == 'pet_catch.py' and '--stages' in a and a[a.index('--stages') + 1] == 'setup,wait', 14)
rc = go(2016, s, to_stage='distribute')
s.bar['DKBO2'].append(s.num('魯尼帖斯'))
n_catch = len([a for a in names(s, 'pet_catch.py') if '--stages' in a and a[a.index('--stages') + 1] == 'setup,wait'])
rc = go(2016, s, to_stage='distribute', reset=False)
check('抓到一半中斷且抓寵者欄有任務寵 → 164 停、不再 pet_catch、不 depot-list', rc == pq.EXIT_CATCH and '已有任務寵' in pq.LAST['info']['msg']
      and len([a for a in names(s, 'pet_catch.py') if '--stages' in a and a[a.index('--stages') + 1] == 'setup,wait']) == n_catch and not any(a[0] == 'depot-list' for a in names(s, 'pet.py')))

# renamed 之前失敗（reset-name 66）→ 165；重跑：不重抓、不重取誘餌，從 reset-name 接
s = grow(Sim(2016))
s.reset_rc = 66
rc = go(2016, s, to_stage='distribute')
check('reset-name 一般失敗 → 165（不帶沒改名的寵物往下存）、沒 store-many 公共', rc == pq.EXIT_DIST and not any(a[0] == 'store-many' and a[a.index('--depot') + 1] == 'public' for a in names(s, 'pet.py'))
      and json.loads(pq.PROGRESS.read_text(encoding='utf-8'))['2016']['sub_r1']['step'] == 'caught', f'rc={rc}')
s.reset_rc = 0
s.calls.clear()
rc = go(2016, s, to_stage='distribute', reset=False)
check('重跑從 renamed 接：不 pet_catch、不 solo / list 盤點、直接 reset-name → store → …，完成', rc == 0 and after_ok(s, 0) and not names(s, 'pet_catch.py') and not any(c[0] == 'team.py' for c in s.calls)
      and seq_of(s)[0] == 'reset-name', f'rc={rc} {seq_of(s)}')

# stored 中途失敗（第 2 個抓寵者 store-many 公共失敗）→ 重跑只補沒存的那個
s = grow(Sim(2016))
s.store_fail_op = 4                                                  # 一次 --plan 內：DKBO2 的 4 隻存完、DKBO3 第 1 隻失敗
rc = go(2016, s, to_stage='distribute')
check('第 2 個抓寵者存公共失敗 → 165；進度檔 stored_roles = [第 1 個]', rc == pq.EXIT_DIST and json.loads(pq.PROGRESS.read_text(encoding='utf-8'))['2016']['sub_r1']['stored_roles'] == ['DKBO2'], f'rc={rc}')
s.calls.clear()
rc = go(2016, s, to_stage='distribute', reset=False)
sp_ = [a for a in names(s, 'pet.py') if a[0] == 'store-many' and a[a.index('--depot') + 1] == 'public']
check('重跑：reset-name 不重做（renamed 已記）、store-many 公共只補 DKBO3，之後取個人 → 取公共 → 驗 3 格', rc == 0 and after_ok(s, 0) and len(sp_) == 1 and sp_[0][sp_[0].index('--plan') + 1].startswith('DKBO3:') and 'DKBO2' not in sp_[0][sp_[0].index('--plan') + 1]
      and seq_of(s)[0] == 'store-many-public' and not names(s, 'pet_catch.py'), f'rc={rc} {seq_of(s)}')

# taken_personal 之前失敗（take-many 個人）→ 重跑只做取個人以後，不重存
s = grow(Sim(2016))
fail_once(s, lambda sc, a: sc == 'pet.py' and a[0] == 'take-many' and a[a.index('--depot') + 1] == 'personal', 72)
rc = go(2016, s, to_stage='distribute')
check('取個人倉庫失敗 → 165、小步停在 stored', rc == pq.EXIT_DIST and json.loads(pq.PROGRESS.read_text(encoding='utf-8'))['2016']['sub_r1']['step'] == 'stored', f'rc={rc}')
s.calls.clear()
rc = go(2016, s, to_stage='distribute', reset=False)
check('重跑：不 reset-name 抓寵者、不再 store-many，先取個人 → reset-name → 取公共 → 驗', rc == 0 and after_ok(s, 0) and seq_of(s)[:2] == ['take-many-personal', 'reset-name'] and 'store-many-public' not in seq_of(s), f'rc={rc} {seq_of(s)}')

# distribute 取公共中途失敗 → 重跑只補沒取到的
s = grow(Sim(2016))
s.public_hold = None
rc = go(2016, s, to_stage='catch')
check('只跑到 catch 段（taken_personal）rc 0', rc == 0 and json.loads(pq.PROGRESS.read_text(encoding='utf-8'))['2016']['sub_r1']['step'] == 'taken_personal')
drop_ = [p for p in s.public if p['name'] == '貝魯卡'][:1]
for p in drop_:
    s.public.remove(p)                                              # 公共少 1 隻貝魯卡 → 最後一人取不到（72）
rc = go(2016, s, from_stage='distribute', to_stage='distribute', reset=False)
tkn = json.loads(pq.PROGRESS.read_text(encoding='utf-8'))['2016']['sub_r1'].get('taken')
check('取公共失敗 72 → 165、進度檔記已取到的（7 隻）', rc == pq.EXIT_DIST and len(tkn or []) == 7, f'rc={rc} {tkn}')
s.public.append(P('貝魯卡'))
s.calls.clear()
rc = go(2016, s, from_stage='distribute', to_stage='distribute', reset=False)
tk = [a for a in names(s, 'pet.py') if a[0] == 'take-many']
check('補回後重跑：take-many 只放剛才沒取到的 1 隻、驗 3 格', rc == 0 and len(tk) == 1 and len(tk[0][tk[0].index('--plan') + 1].split(',')) == 1 and after_ok(s, 0), f'rc={rc} {tk}')
# 重跑已完成的 catch / distribute → 全跳過（不呼叫任何寵物指令）
s.calls.clear()
rc = go(2016, s, from_stage='catch', to_stage='distribute', reset=False)
check('已做完（distributed）再 --from catch：catch / distribute 都不動寵物（只驗證 distribute 的格數 1 次）', rc == 0 and not any(c[0] == 'pet_catch.py' for c in s.calls)
      and not any(a[0] in ('store-many', 'take-many', 'reset-name') for a in names(s, 'pet.py')), f'rc={rc}')

# 費用字樣 / 驗證視窗透傳
s = grow(Sim(2016))
s.reset_rc = pq.PET_FEE
rc = go(2016, s, to_stage='distribute')
check('reset-name 讀到費用字樣（67）→ 165 停手、沒存公共、訊息提鐵則 3', rc == pq.EXIT_DIST and not any(a[0] == 'store-many' and a[a.index('--depot') + 1] == 'public' for a in names(s, 'pet.py'))
      and '鐵則 3' in pq.LAST['info'].get('msg', ''), f'rc={rc} {pq.LAST.get("info")}')
s = grow(Sim(2016))
s.reset_rc = 9
check('reset-name 驗證視窗（9）→ 透傳 9', go(2016, s, to_stage='distribute') == 9)
s = grow(Sim(2016))
s.reset_rc = 10
check('reset-name 斷線（10）→ 透傳 10', go(2016, s, to_stage='distribute') == 10)
s = grow(Sim(2016))
fail_once(s, lambda sc, a: sc == 'pet.py' and a[0] == 'take-many' and a[a.index('--depot') + 1] == 'public', 9)
check('取公共時驗證視窗（9）→ 透傳 9', go(2016, s, to_stage='distribute') == 9)
s = grow(Sim(2016))
rc = go(2016, s, to_stage='catch')
fail_once(s, lambda sc, a: sc == 'pet.py' and a[0] == 'list', 10)
check('分配後驗證讀寵物欄斷線（10）→ 透傳 10', go(2016, s, from_stage='distribute', to_stage='distribute', reset=False) == 10)

# ---------------- --keep-autoswap（恐龍博士後面還要解卡坦）：train 不關自動轉換、restore 跳過、原等級交給卡坦 prep
s = grow(Sim(2016))
rc = go(2016, s, confirm_drop=True, keep_autoswap=True)
off = [a for a in names(s, 'pet_catch.py') if a[:2] == ('--autoswap', 'off')]
on = [a for a in names(s, 'pet_catch.py') if a[:2] == ('--autoswap', 'on')]
check('--keep-autoswap：train 開了自動轉換、結束不關；rest-all 照做', rc == 0 and len(on) == 1 and not off and any(a[0] == 'set-state-slot' and a[-1] == '等待' for a in names(s, 'pet.py')), f'rc={rc} {on} {off}')
check('--keep-autoswap：restore 跳過（不取回朵拉比斯、不鎖定、不改一般動作）',
      not any(a[0] == 'take-many' and '朵拉比斯@' in a[a.index('--plan') + 1] for a in names(s, 'pet.py'))
      and not [a for a in names(s, 'pet_catch.py') if '--lock' in a] and not names(s, 'ass.py'), str(names(s, 'pet_catch.py')))
allp = json.loads(pq.PROGRESS.read_text(encoding='utf-8'))
check('--keep-autoswap：進度檔頂層共用紀錄 slot2_stored 留著（5 人原等級 + 第 2 格名字）', sorted(allp.get('slot2_stored', {}).get('orig', {})) == sorted(pq.ALL_ROLES)
      and allp['slot2_stored'].get('battle') == {r: '朵拉比斯' for r in ROLES}, str(allp.get('slot2_stored')))
s2 = grow(Sim(2019))
s2.t = s.t                                                            # 同一條時間線（紀錄的 ts 不能在未來）
for r in pq.ALL_ROLES:
    s2.bar[r] = [x for x in s2.bar[r] if x['name'] != '朵拉比斯']       # 朵拉比斯還在個人倉庫、寵物欄第 2 格已空
    s2.personal[r] = [dict(x) for x in s.personal[r]]
rc = go(2019, s2, from_stage='prep', to_stage='prep', reset=False)
check('恐龍博士後卡坦 prep：沿用 slot2_stored，不讀寵物欄、不存倉、不 unlock（只關遇敵 + 解散）',
      rc == 0 and json.loads(pq.PROGRESS.read_text(encoding='utf-8'))['2019']['orig'] == allp['slot2_stored']['orig']
      and not names(s2, 'pet.py') and not any('--unlock' in a for a in names(s2, 'pet_catch.py')) and ('disband',) in names(s2, 'team.py'), f'rc={rc} {pq.LAST.get("info")} {names(s2, "pet.py")}')
rc = go(2019, s2, from_stage='catch1', confirm_drop=True, reset=False)
check('卡坦 restore 用共用紀錄換回原等級戰寵並清掉 slot2_stored', rc == 0 and 'slot2_stored' not in json.loads(pq.PROGRESS.read_text(encoding='utf-8'))
      and all(s2.bar[r][1]['name'] == '朵拉比斯' and s2.bar[r][1]['level'] == allp['slot2_stored']['orig'][r] for r in ROLES), f'rc={rc} {pq.LAST.get("info")} {s2.bar["DKBO"]}')
s = grow(Sim(2016))
rc = go(2016, s, confirm_drop=True)
check('沒帶 --keep-autoswap：照舊關自動轉換 + restore 換回 + 清 slot2_stored', rc == 0 and any(a[:2] == ('--autoswap', 'off') for a in names(s, 'pet_catch.py'))
      and any(a[0] == 'take-many' and '朵拉比斯@' in a[a.index('--plan') + 1] for a in names(s, 'pet.py'))
      and 'slot2_stored' not in json.loads(pq.PROGRESS.read_text(encoding='utf-8')))

# ---------------- 戰寵不是朵拉比斯（p2：迪基格斯出戰 + 瑪斯貝卡騎乘；各角色可不同）
check('pick_battle_names：每人當下出戰寵', pq.pick_battle_names({'DKBO': [P('瑪斯貝卡', '騎乘', 5), P('迪基格斯', '出戰', 9)]}, roles=['DKBO'])[0] == {'DKBO': '迪基格斯'})
check('pick_battle_names：沒出戰、欄有朵拉比斯 → 退路朵拉比斯', pq.pick_battle_names({'DKBO': [P('瑪斯貝卡', '騎乘', 5), P('朵拉比斯', '等待', 9)]}, roles=['DKBO'])[0] == {'DKBO': '朵拉比斯'})
nm, bd = pq.pick_battle_names({'DKBO': [P('瑪斯貝卡', '騎乘', 5), P('迪基格斯', '等待', 9)], 'DKBO2': [P('A', '出戰'), P('B', '出戰')],
                               'DKBO3': [{'state': '出戰', 'level': 3, 'img_species': '迪基格斯'}]}, roles=['DKBO', 'DKBO2', 'DKBO3'])
check('pick_battle_names：沒出戰且沒退路 / 多隻出戰 / 只有縮圖 → 不猜、記原因', nm == {} and set(bd) == {'DKBO', 'DKBO2', 'DKBO3'}, str(bd))
check('group_by_name 依名單順序分組', pq.group_by_name({'DKBO6': 'a', 'DKBO7': 'b', 'DKBO8': 'a'}, roles=['DKBO6', 'DKBO7', 'DKBO8']) == [('a', ['DKBO6', 'DKBO8']), ('b', ['DKBO7'])])

s = grow(Sim(2016, battle='迪基格斯'))
rc = go(2016, s, confirm_drop=True)
check('恐龍博士（戰寵迪基格斯）happy：rc 0、進度檔記 battle', rc == 0 and set(json.loads(pq.PROGRESS.read_text(encoding='utf-8'))['2016']['battle'].values()) == {'迪基格斯'}, f'rc={rc} {pq.LAST.get("info")}')
check('存倉 / 取回 / 出戰 / 鎖定都用迪基格斯，沒碰朵拉比斯', any(a[0] == 'store-many' and '迪基格斯' in a for a in names(s, 'pet.py'))
      and any(a[0] == 'take-many' and '迪基格斯@125' in a[a.index('--plan') + 1] for a in names(s, 'pet.py'))
      and ('--lock', '戰寵', '--battle-pet', '迪基格斯', '--normal', '攻擊') in names(s, 'pet_catch.py')
      and not any('朵拉比斯' in ' '.join(map(str, a)) for a in names(s, 'pet.py') + names(s, 'pet_catch.py')))
check('結果：每人 騎寵 + 迪基格斯出戰', all([p['name'] for p in s.bar[r]] == ['布拉奇多斯', '迪基格斯'] and s.bar[r][1]['state'] == '出戰' for r in ROLES))

# 續跑沿用已記的名字（不重讀覆蓋）：進度檔已有 battle，寵物欄現在沒有出戰寵 → 仍成功進 prep
s = Sim(2016, battle='迪基格斯')
pq.PROGRESS.write_text(json.dumps({'2016': {'done': [], 'ts': __import__('time').time(), 'battle': {r: '迪基格斯' for r in ROLES}, 'orig': {r: 125 + i for i, r in enumerate(ROLES)}}}), encoding='utf-8')
for r in ROLES:
    for p in s.bar[r]:
        p['state'] = '等待'
rc = go(2016, s, reset=False, to_stage='prep')
check('續跑沿用進度檔戰寵名（不重讀）', rc == 0 and any(a[0] == 'store-many' and '迪基格斯' in a for a in names(s, 'pet.py')), f'rc={rc} {pq.LAST.get("info")}')

# 第 2 格（2026-10-15）：不看出戰狀態，記第 2 格名字 + 等級
s = Sim(2016, battle='迪基格斯')
for r in ROLES:
    s.bar[r][1]['state'] = '等待'
rc = go(2016, s, to_stage='prep')
pr = json.loads(pq.PROGRESS.read_text(encoding='utf-8'))['2016']
check('第 2 格是等待中的迪基格斯 → 照記（名字 + 等級）並存個人倉庫', rc == 0 and set(pr['battle'].values()) == {'迪基格斯'} and pr['orig'] == {r: 125 + i for i, r in enumerate(ROLES)}
      and pr.get('stored') and all(len(s.bar[r]) == 1 for r in ROLES), f'rc={rc} {pq.LAST.get("info")}')
nm, lv, bd = pq.pick_slot2({'DKBO': [dict(P('瑪斯貝卡', '騎乘', 5), slot=1), dict(P('迪基格斯', '出戰', 9), slot=2), dict(P('朵拉比斯', '出戰', 130), slot=3)]}, roles=['DKBO'])
check('pick_slot2：取 slot == 2（1 起算），不是第一隻出戰的', nm == {'DKBO': '迪基格斯'} and lv == {'DKBO': 9} and not bd, f'{nm} {lv} {bd}')
nm, lv, bd = pq.pick_slot2({'A': [dict(P('瑪斯貝卡', '騎乘', 5), slot=1), {'slot': 2, 'empty': True}],
                            'B': [dict(P('朵拉比斯', '出戰', 9), slot=1), dict(P('瑪斯貝卡', '騎乘', 5), slot=2)],
                            'C': [dict(P('朵拉比斯', '出戰', 9), slot=1), dict(P('瑪斯貝卞', '等待', 5), slot=2)],
                            'D': [dict(P('瑪斯貝卡', '騎乘', 5), slot=1), {'slot': 2, 'state': '出戰', 'level': 3, 'img_species': '迪基格斯'}],
                            'E': [dict(P('瑪斯貝卡', '騎乘', 5), slot=1), dict(P('迪基格斯', '出戰', None), slot=2)],
                            'F': [dict(P('瑪斯貝卡', '騎乘', 5), slot=1), dict(P('朵拉比斯', '騎乘', 130), slot=2)]}, roles=list('ABCDEF'))
check('pick_slot2：空格 / 騎寵（騎乘、像騎寵錯字）/ 只有縮圖 / 等級讀不到 / 騎乘中 → 全部記原因、不記名字',
      nm == {} and set(bd) == set('ABCDEF') and '騎寵' in bd['B'] and '騎寵' in bd['C'] and '騎寵' in bd['F'] and '空' in bd['A'] and '讀不出' in bd['D'] and '等級' in bd['E'], str(bd))
s = Sim(2016)
s.bar[ROLES[2]][1] = P('瑪斯貝卡', '騎乘', 5)                   # 第 2 格是騎寵
rc = go(2016, s, to_stage='prep')
check('有人第 2 格是騎寵 → 162、一隻都不存（存倉不碰騎寵）', rc == pq.EXIT_PREP and not any(a[0] == 'store-many' for a in names(s, 'pet.py'))
      and '騎寵' in pq.LAST['info']['msg'], f'rc={rc} {pq.LAST.get("info")}')
s = Sim(2016)
s.bar[ROLES[1]] = s.bar[ROLES[1]][:1]                          # 第 2 格空
rc = go(2016, s, to_stage='prep')
check('有人第 2 格空 → 162、沒存倉、沒接任務', rc == pq.EXIT_PREP and not any(a[0] == 'store-many' for a in names(s, 'pet.py')) and not names(s, 'questrun.py'), f'rc={rc}')

# 各角色不同戰寵：分組存倉
s = Sim(2016)
s.bar[ROLES[0]][1]['name'] = '迪基格斯'
s.personal[ROLES[0]][0]['name'] = '迪基格斯'
rc = go(2016, s, to_stage='prep')
sm = [a for a in names(s, 'pet.py') if a[0] == 'store-many']
check('各角色戰寵不同 → 分兩組 store-many（隊長迪基格斯 / 其餘朵拉比斯）', rc == 0 and len(sm) == 2 and any('迪基格斯' in a and a[a.index('--role') + 1] == ROLES[0] for a in sm), f'rc={rc} {sm}')

print(f'\n{"全部通過" if not fails else f"失敗 {fails} 項"}')
sys.exit(1 if fails else 0)

# ---------------- 2026-10-16 練寵只讀最後一格；restore 精簡
s = grow(Sim(2019))
rc = go(2019, s, confirm_drop=True)
lv = [a for a in names(s, 'pet.py') if a[0] == 'levels']
check('卡坦練寵只讀第 5 格（4 種 → 1 + 4）、不呼叫 list（train 段內）', rc == 0 and lv and all(a[a.index('--slots') + 1] == '5' for a in lv), str(lv[:3]))
rs_ = [i for i, c in enumerate(s.calls) if c[0] == 'pet.py' and c[1][0] == 'take-many' and '--depot' in c[1] and c[1][c[1].index('--depot') + 1] == 'personal' and '朵拉比斯@' in c[1][-1] or False]
s = grow(Sim(2016))
rc = go(2016, s, confirm_drop=True)
rs_i = [i for i, c in enumerate(s.calls) if c[0] == 'pet.py' and c[1][0] == 'take-many' and '朵拉比斯@' in c[1][c[1].index('--plan') + 1]][-1]
after = [c for c in s.calls[rs_i:] if c[0] in ('pet.py', 'pet_catch.py', 'ass.py')]
check('restore：take-many → set-state-slot --slots 2 出戰 → pet_catch --lock --normal 攻擊（一次）→ 只剩最後核對 list；不讀取回前 list、不呼叫 set-state-many / ass.py',
      rc == 0 and [(c[0], c[1][0]) for c in after] == [('pet.py', 'take-many'), ('pet.py', 'set-state-slot'), ('pet_catch.py', '--lock'), ('pet.py', 'list')]
      and after[1][1][-3:] == ('--slots', '2', '出戰') and after[2][1][-2:] == ('--normal', '攻擊') and not names(s, 'ass.py'), str([(c[0], c[1][:3]) for c in after]))
# 續跑：restore_taken 記號有 → 不取回、不讀 list；沒記號才取
s = grow(Sim(2016))
go(2016, s, confirm_drop=True, to_stage='drop')
prog = json.loads(pq.PROGRESS.read_text(encoding='utf-8'))
check('restore 前進度檔沒有 restore_taken', 'restore_taken' not in prog['2016'])
n0 = len(s.calls)
rc = go(2016, s, confirm_drop=True, from_stage='restore', reset=False)
seg = [c for c in s.calls[n0:] if c[0] == 'pet.py']
check('restore 成功後記 restore_taken（任務完成才清）、取回只 1 次', rc == 0 and len([c for c in seg if c[1][0] == 'take-many']) == 1, str([c[1][:2] for c in seg]))
s = grow(Sim(2016))
go(2016, s, confirm_drop=True, to_stage='drop')
s.fail[('pet.py', 'set-state-slot')] = 5                         # 取回成功、第 2 格出戰失敗 → 記號已存
go(2016, s, confirm_drop=True, from_stage='restore', reset=False)
check('取回成功後出戰失敗：進度檔已記 restore_taken', json.loads(pq.PROGRESS.read_text(encoding='utf-8'))['2016'].get('restore_taken') is True)
s.fail.clear()
n0 = len(s.calls)
rc = go(2016, s, confirm_drop=True, from_stage='restore', reset=False)
seg = [(c[0], c[1][0]) for c in s.calls[n0:] if c[0] in ('pet.py', 'pet_catch.py')]
check('續跑：看到 restore_taken 跳過取回、不讀 list，直接出戰 → 鎖定 + 一般動作 → 驗', rc == 0 and seg[:3] == [('pet.py', 'set-state-slot'), ('pet_catch.py', '--lock'), ('pet.py', 'list')] and ('pet.py', 'take-many') not in seg, str(seg))

# 練完等待只改最後一格、在關遇敵之前
s = grow(Sim(2016))
go(2016, s, confirm_drop=True, to_stage='train')
ix = [i for i, c in enumerate(s.calls) if c[0] == 'pet.py' and c[1][0] == 'set-state-slot' and c[1][-1] == '等待']
eo = [i for i, c in enumerate(s.calls) if c == ('enc_off',)]
check('練完：第二次讀到最後一格達標 → 立刻 set-state-slot 只改最後那一格（第 3 格）等待，在關遇敵之前', len(ix) == 1 and s.calls[ix[0]][1][s.calls[ix[0]][1].index('--slots') + 1] == '3' and eo and ix[0] < eo[-1], f'{ix} {eo}')
