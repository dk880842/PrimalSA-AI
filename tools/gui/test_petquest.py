#!/usr/bin/env python3
"""petquest.py 離線測試：完全不碰遊戲（假 Tools + 小型寵物欄 / 倉庫模擬器回應各腳本子程序）。
用法：uv run --no-project python tools/gui/test_petquest.py"""
import contextlib
import io
import json
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

    def __init__(self, qid, bait=50, orig=125, step=1, stone=3_000_000):
        self.qid, self.bait, self.stone, self.dia, self.step = qid, bait, stone, 0, step
        self.bar = {r: [P('布拉奇多斯', '騎乘', 5), P('朵拉比斯', '出戰', orig + i)] for i, r in enumerate(ROLES)}
        self.personal = {r: [P('朵拉比斯', '等待', 130)] for r in ROLES}
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

    def clock(self):
        return 0.0

    def encounter_off(self):
        self.calls.append(('enc_off',))

    def read_step(self, track):
        return self.step

    def money(self):
        return self.stone, self.dia

    def press_plus(self, role):
        b = self.plus.get(role, 0) + self.bag_bait.get(role, 0)
        self.plus[role] = self.plus.get(role, 0) + 1
        self.stone -= self.plus_cost
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
                if p['name'] == '朵拉比斯':
                    p['state'] = '出戰'
        return self.out(0)

    def petdrop(self, args):
        name = args[1]
        for r in ROLES:
            self.bar[r] = [p for p in self.bar[r] if not (p['name'] == name and p['level'] <= 1)]
        return self.out(0)

    def pet_catch(self, args):
        if '--assign' not in args:
            return self.out(0)
        assign = [a.split(':') for a in self.opt(args, '--assign').split(',')]
        k = int(self.opt(args, '--count'))
        stages = self.opt(args, '--stages')
        if stages == 'bait':
            lines = []
            for r, _, _ in assign:
                if self.bait < k:
                    return self.out(92, *lines)
                self.bait -= k
                self.bag_bait[r] = k
                lines.append(f'rebirth_pets：{r} 背包誘餌 = {k}')
            return self.out(0, *lines)
        for r, _, sp in assign:
            have = self.bag_bait.get(r, 0) + self.plus.get(r, 0)
            if have != k:
                return self.out(4, f'{r} 可抓捕數 {have} ≠ {k}')
            if len(self.bar[r]) + k > 5:
                return self.out(103, '寵物欄放不下（模擬：會進個人倉庫）')
            self.bar[r] += [P(sp) for _ in range(k)]
            self.bag_bait[r] = self.plus[r] = 0
        return self.out(0)

    def pet(self, args):
        cmd = args[0]
        if cmd == 'list':
            if self.train_calls is not None:
                self.train_calls += 1
            return self.out(0, js={'roles': {r: [dict(p, slot=i + 1, nh=p['name']) for i, p in enumerate(self.bar[r])] for r in ROLES}, 'rc': 0})
        if cmd == 'levels':                  # 只讀等級：格號 + 等級 + 名字框指紋（模擬用名字）
            self.levels_calls = getattr(self, 'levels_calls', 0) + 1
            sl = [int(x) for x in self.opt(args, '--slots', '').split(',') if x]
            return self.out(0, js={'roles': {r: [{'slot': i + 1, 'level': p['level'], 'nh': p['name']} for i, p in enumerate(self.bar[r]) if not sl or i + 1 in sl]
                                             for r in ROLES}, 'rc': 0})
        if cmd == 'store-many':
            roles = ROLES if self.opt(args, '--role') == 'all' else self.opt(args, '--role').split(',')
            depot = self.opt(args, '--depot')
            for r in roles:
                for name in self.opt(args, '--pets').split(','):
                    hits = [p for p in self.bar[r] if p['name'] == name and p['state'] != '騎乘']
                    if not hits:
                        if '--skip-missing' in args:
                            continue
                        return self.out(72)
                    p = hits[-1]
                    self.bar[r].remove(p)
                    p['state'] = '等待'
                    (self.public if depot == 'public' else self.personal[r]).append(p)
            return self.out(0)
        if cmd == 'take-many':
            depot = self.opt(args, '--depot')
            for part in self.opt(args, '--plan').split(','):
                r, t = part.split(':')
                name, lv = (t.split('@') + [None])[:2]
                src = self.public if depot == 'public' else self.personal[r]
                hit = next((p for p in src if p['name'] == name and (lv is None or p['level'] == int(lv))), None)
                if not hit or len(self.bar[r]) >= 5:
                    return self.out(72 if not hit else 77)
                src.remove(hit)
                self.bar[r].append(hit)
            return self.out(0)
        if cmd == 'set-state-many':
            name, st = args[3], args[4]
            for r in ROLES:
                for p in self.bar[r]:
                    if p['name'] == name:
                        p['state'] = st
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
                    if p['name'] not in ('布拉奇多斯', '朵拉比斯', '金布伊'):
                        p['level'] += by
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
check('batches：5 隻 / 4 空格 → [4, 1]；3 空格 → [3, 2]；0 → []', pq.batches(5, 4) == [4, 1] and pq.batches(5, 3) == [3, 2] and pq.batches(0, 4) == [])
check('store_after_batch：非最後一批全存、最後一批留 1', pq.store_after_batch(4, False) == 4 and pq.store_after_batch(1, True) == 0 and pq.store_after_batch(3, True) == 2)
tp = pq.take_plan([('DKBO2', 'x', '魯尼帖斯'), ('DKBO3', 'y', '貝魯卡')])
check('take_plan：抓寵者自己那種不取、其他人每種 1 隻', ('DKBO2', '魯尼帖斯') not in tp and ('DKBO2', '貝魯卡') in tp and ('DKBO', '魯尼帖斯') in tp and len(tp) == 8)
check('parse_money：依 x 排序，第一個石幣、第二個鑽石（逗號去掉）', pq.parse_money([('0', 520, 23), ('3,264,500', 335, 23)]) == (3264500, 0)
      and pq.parse_money([]) == (None, None))
check('bait_ok_roles 讀「背包誘餌 = N」', pq.bait_ok_roles(['rebirth_pets：DKBO2 背包誘餌 = 4', 'x', 'rebirth_pets：DKB03 背包誘餌 = 4']) == {'DKBO2', 'DKBO3'})
ok, lag = pq.train_status({'DKBO': [P('魯尼帖斯', level=18), P('貝魯卡', level=29)]}, {'魯尼帖斯': 18, '貝魯卡': 30}, roles=['DKBO'])
check('train_status：門檻 ≥（18 過、29 < 30 沒過）', not ok and lag == {'DKBO': {'貝魯卡': 29}})
check('battle_levels：出戰那隻優先', pq.battle_levels({'DKBO': [P('朵拉比斯', '等待', 1), P('朵拉比斯', '出戰', 126)]}) == {'DKBO': 126})
check('stage_base：catch2 → catch、step1 不拆', pq.stage_base('catch2') == 'catch' and pq.stage_base('step1') == 'step1' and pq.stage_round('turnin2') == 2)
check('stages_of 卡坦兩輪、恐龍一輪、猜謎', pq.stages_of(2019)[2:7] == ['catch1', 'distribute1', 'train1', 'turnin1', 'drop1'] and 'store_reward' in pq.stages_of(2019)
      and pq.stages_of(2016)[2] == 'catch' and pq.stages_of(3003)[1] == 'step1')

# ---------------- 恐龍博士 happy path
s = grow(Sim(2016))
rc = go(2016, s, confirm_drop=True)
check('恐龍博士 happy：rc 0', rc == 0, f'rc={rc} {pq.LAST.get("info")}')
check('每人寵物欄 = 騎寵 + 原朵拉比斯出戰（等級 = 原等級）、布克布克已丟', all([p['name'] for p in s.bar[r]] == ['布拉奇多斯', '朵拉比斯'] and s.bar[r][1]['state'] == '出戰'
      and s.bar[r][1]['level'] == 125 + i for i, r in enumerate(ROLES)), str(s.bar))
check('分批抓 [4, 1]：bait 兩次、setup 兩次；誘餌 50 → 40', len([a for a in names(s, 'pet_catch.py') if 'bait' in a]) == 2 and s.bait == 40)
check('抓前關遇敵 + 解散；收尾鎖定戰寵 + 一般動作攻擊', ('enc_off',) in s.calls and ('team.py', ('disband',)) in s.calls
      and any(a[:2] == ('--lock', '戰寵') for a in names(s, 'pet_catch.py')) and ('pet', 'all', 'normal', '攻擊', '--no-resume') in names(s, 'ass.py'))
check('交寵物用 questrun --pet-turnin --rested（train 段剛 rest-all 過，questrun 不重做）', ('run', '2016', '--after', 'none', '--pet-turnin', '--rested') in names(s, 'questrun.py'), str(names(s, 'questrun.py')))
pa = [a for a in names(s, 'pet.py') if a[0] in ('list', 'levels')]
tr = [i for i, c in enumerate(s.calls) if c[0] == 'grind.py']
in_train = [c[1][0] for c in s.calls[tr[0]:] if c[0] == 'pet.py' and c[1][0] in ('list', 'levels', 'rest-all')]
in_train = in_train[:in_train.index('rest-all')]
check('練寵輪詢：第一次 list（身分）、之後只 levels --slots 任務寵格', in_train[0] == 'list' and in_train[1:] and set(in_train[1:]) == {'levels'}
      and all('--slots' in a for a in names(s, 'pet.py') if a[0] == 'levels'), str(in_train))
pc = [a for a in names(s, 'pet_catch.py') if '--stages' in a and 'setup' in a[a.index('--stages') + 1]]
check('抓寵第 1 批不帶 --reuse-setup、第 2 批帶（沿用捉寵設置）', len(pc) == 2 and '--reuse-setup' not in pc[0] and '--reuse-setup' in pc[1], str(pc))
check('沒給 --verify-defer → questrun 不帶 --verify', not any('--verify' in a for a in names(s, 'questrun.py')))
check('原朵拉比斯先存個人、最後 @原等級 取回', any(a[0] == 'take-many' and '朵拉比斯@125' in a[a.index('--plan') + 1] for a in names(s, 'pet.py')))
check('完成後進度檔清空（下一轉從頭）', json.loads(pq.PROGRESS.read_text(encoding='utf-8'))['2016']['done'] == [])

# ---------------- 寵物欄只有 3 空格（獎勵寵沒丟）→ 分批 [3, 2]
s = grow(Sim(2016))
for r in pq.ALL_ROLES:
    s.bar[r].append(P('巴朵蘭恩'))
rc = go(2016, s, confirm_drop=True)
counts = [a[a.index('--count') + 1] for a in names(s, 'pet_catch.py') if '--stages' in a and a[a.index('--stages') + 1] == 'bait']
check('抓寵者寵物欄空格 3 → 分批 [3, 2]（不讓寵物溢到個人倉庫）', rc == 0 and counts == ['3', '2'], f'rc={rc} {counts} {pq.LAST.get("info")}')
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
check('誘餌不夠沒 --confirm-buy-bait → 163、沒按「+」', rc == pq.EXIT_BAIT and not [c for c in s.calls if c[0] == 'plus'], f'rc={rc}')
s = grow(Sim(2016, bait=6))
rc = go(2016, s, confirm_drop=True, confirm_buy=True)
plus = [c for c in s.calls if c[0] == 'plus']
check('--confirm-buy-bait：誘餌 6 個 → 第 1 批 DKBO2 拿 4、DKBO3 買 4 次；第 2 批剩 2 個兩人各 1（不買）；石幣每次扣 50,000', rc == 0 and plus == [('plus', 'DKBO3')] * 4
      and s.stone == 3_000_000 - 4 * pq.PLUS_COST and s.bait == 0, f'rc={rc} plus={plus} {pq.LAST.get("info")}')
s = grow(Sim(2016, bait=0))
s.plus_cost = 100000
rc = go(2016, s, confirm_buy=True)
check('「+」扣款不是剛好 50,000 → 163 停（只按 1 次）', rc == pq.EXIT_BAIT and len([c for c in s.calls if c[0] == 'plus']) == 1 and '扣' in pq.LAST['info']['msg'])
s = grow(Sim(2016, bait=0))
s.money = lambda: (None, None)
rc = go(2016, s, confirm_buy=True)
check('石幣讀不到 → 163、不按「+」', rc == pq.EXIT_BAIT and not [c for c in s.calls if c[0] == 'plus'])
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
s = grow(Sim(2019, step=2))
s.bar = {r: [P('布拉奇多斯', '騎乘', 5), P('朵拉比斯', '出戰', 125 + i)] for i, r in enumerate(ROLES)}
rc = go(2019, s, confirm_drop=True)
check('接取時步號已是 2 → 第 1 輪全跳過（不抓鯊）', rc == 0 and not any('鯊魚系' in ' '.join(a) for a in names(s, 'pet_catch.py')), f'rc={rc}')
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
      and ('start', '--spot', '地雷區') in names(s, 'grind.py') and ('all', '左迪洛斯', '--confirm-name', '左迪洛斯', '--max-level', '1') in names(s, 'petdrop.py')
      and not any(p['name'] == '左迪洛斯' for r in ROLES for p in s.bar[r]), f'rc={rc} {pq.LAST.get("info")}')
check('猜謎：quest.py 步 1 --stop-after-rewards 1', names(s, 'quest.py') == [('--task', '猜謎三兄弟', '--stop-after-rewards', '1', '--max-seconds', '900')])
s = Sim(3003)
s.quest = lambda a: s.out(0)                                 # 步 1 跑完但沒拿到金布伊（要爬塔）
rc = go(3003, s, confirm_drop=True)
check('猜謎步 1 後沒有金布伊 → 161、提示點任務追蹤重試', rc == pq.EXIT_ACCEPT and '任務追蹤' in pq.LAST['info'].get('manual', ''))

# ---------------- 其他
s = Sim(2016)
s.fail[('questrun.py', 'run')] = 9
rc = go(2016, s)
check('questrun 回 9（驗證視窗）→ 透傳 9', rc == 9)
s = Sim(2016)
s.quest_q = {2016: [0]}
rc = go(2016, s)
check('接取時 questrun 回 0（已完成）→ 不抓不交不丟，只收尾（鎖定 + 一般動作 + 驗）', rc == 0 and not any('--assign' in a for a in names(s, 'pet_catch.py'))
      and not names(s, 'petdrop.py') and len(names(s, 'questrun.py')) == 1 and names(s, 'ass.py'), f'rc={rc}')
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


keep = {k: getattr(bag, k) for k in ('Session', 'select_role', 'find_item', 'open_slot_popup', 'name_match', 'popup_name', '_ocr_join', '_click', 'close_popup', 'depot_store', 'find_items')}
keep_ocr, keep_gui, keep_fail = rp.ocr_lines, uikit.gui, uikit.fail
clicks = []
bag.Session, bag.select_role, bag.find_item, bag.open_slot_popup = _S, lambda r: 0, lambda n: 0, lambda i: True
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
    bag.find_items = lambda role, names: (0, {rp.BAIT: 0})
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
m, why = pq.merge_levels(base, {'DKBO': [{'slot': 2, 'level': 9, 'nh': 'a'}]}, need)
check('merge_levels：nh 相同 → 等級換新、其他格照舊', why is None and m['DKBO'][1]['level'] == 9 and m['DKBO'][0]['name'] == '布拉奇多斯')
check('merge_levels：nh 不同 / 變空格 / 沒讀到 → 不合併（改讀完整 list）', pq.merge_levels(base, {'DKBO': [{'slot': 2, 'level': 9, 'nh': 'b'}]}, need)[0] is None
      and pq.merge_levels(base, {'DKBO': [{'slot': 2, 'empty': True}]}, need)[0] is None and pq.merge_levels(base, {'DKBO': []}, need)[0] is None)
check('task_slots：各角色任務寵格聯集', pq.task_slots({'A': [{'slot': 2, 'name': '魯尼帖斯'}], 'B': [{'slot': 3, 'name': '魯尼帖斯'}, {'slot': 1, 'name': 'x'}]}, need) == [2, 3])
k = ('DKBO', '魯尼帖斯')
check('train_confirm：第一次 ≥ 門檻 → pending；連兩輪 ≥ 且不降、升 ≤ 10 → due', pq.train_confirm({k: 18}, {}, need) == ([], [k]) and pq.train_confirm({k: 20}, {k: 18}, need) == ([k], []))
check('train_confirm：前一輪沒達標 / 讀值下降 / 大跳（OCR 錯值）→ 不算', pq.train_confirm({k: 18}, {k: 17}, need)[0] == [] and pq.train_confirm({k: 19}, {k: 25}, need)[0] == []
      and pq.train_confirm({k: 128}, {k: 18}, need)[0] == [] and pq.train_confirm({k: None}, {k: 20}, need) == ([], []))
s = grow(Sim(2016))
_lv = s.pet
_bad = [1]


def _pet(a):
    rc, ls = _lv(a)
    if a[0] == 'levels' and _bad:                            # 第一次 levels：魯尼帖斯那格指紋變了（被浮字蓋住）
        _bad.pop()
        ls = [ls[0].replace('"nh": "魯尼帖斯"', '"nh": "x"')]
    return rc, ls


s.pet = _pet
rc = go(2016, s, confirm_drop=True)
tr = [i for i, c in enumerate(s.calls) if c[0] == 'grind.py']
seq = [c[1][0] for c in s.calls[tr[0]:] if c[0] == 'pet.py' and c[1][0] in ('list', 'levels')]
check('levels 指紋對不上 → 那一輪改讀完整 list，之後回到只讀等級，仍練完', rc == 0 and seq[:3] == ['list', 'levels', 'list'] and seq[3] == 'levels', f'rc={rc} {seq[:6]}')

print(f'\n{"全部通過" if not fails else f"失敗 {fails} 項"}')
sys.exit(1 if fails else 0)
