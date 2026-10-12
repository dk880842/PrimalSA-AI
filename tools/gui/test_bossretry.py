#!/usr/bin/env python3
"""bossretry.py 離線測試：完全不碰遊戲（假 Tools）。用法：uv run --no-project python tools/gui/test_bossretry.py"""
import contextlib
import io
import os
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace as C

os.environ.setdefault('PSA_LAYOUT', '2880x1659')
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import testenv  # noqa: E402,F401  紀錄檔轉向暫存
import errlog  # noqa: E402
import questrun  # noqa: E402
import bossretry as br  # noqa: E402

TMP = Path(tempfile.mkdtemp())
questrun.EVENT_LOG = TMP / 'ev.log'
errlog.LOG = TMP / 'errlog.jsonl'
fails = 0


def check(name, cond, extra=''):
    global fails
    print(('PASS' if cond else 'FAIL'), name, extra)
    if not cond:
        fails += 1


def quiet(fn, *a, **k):
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        return fn(*a, **k)


def cards(leader='DKBO', members=('DKBO2', 'DKBO3', 'DKBO4'), solo=('DKBO5',)):
    out = []
    for n in ('DKBO', 'DKBO2', 'DKBO3', 'DKBO4', 'DKBO5'):
        lab = 'leader' if n == leader else 'member' if n in members else 'solo' if n in solo else 'other'
        out.append(C(name=n, label=lab))
    return out


class Fake:
    """steps：{角色: [步號序列]}（read_step 依當前角色取，最後一個重複）；quest：[rc…]；hp：{角色: %}"""

    def __init__(self, check_rcs=(41, 0), cards_=None, steps=None, quest=None, hp=None, cur='DKBO', **kw):
        self.calls, self.cur = [], cur
        self.check_rcs = list(check_rcs)
        self.cards = cards() if cards_ is None else cards_
        self.steps = {k: list(v) for k, v in (steps or {}).items()}
        self.quest_q = list(quest or [])
        self.hp = dict(hp or {})
        self.switch_rc = kw.get('switch_rc', {})
        self.form_rc = kw.get('form_rc', 0)
        self.disband_rc = kw.get('disband_rc', 0)
        self.pre_rc = kw.get('pre_rc', 0)

    def rec(self, *a):
        self.calls.append(a)

    def names(self):
        return [c[0] for c in self.calls]

    def sleep(self, s):
        pass

    def preflight(self):
        return self.pre_rc

    def team_check(self):
        self.rec('check')
        return self.check_rcs.pop(0) if len(self.check_rcs) > 1 else self.check_rcs[0]

    def team_cards(self):
        return self.cards, ''

    def current(self):
        return 0, self.cur

    def char_switch(self, n):
        self.rec('switch', n)
        rc = self.switch_rc.get(n, 0)
        if not rc:
            self.cur = n
        return rc

    def char_ensure(self, n):
        self.rec('ensure', n)
        self.cur = n
        return 0

    def read_step(self, track):
        q = self.steps.get(self.cur, [None])
        return q.pop(0) if len(q) > 1 else q[0]

    def hp_pct(self):
        return self.hp.get(self.cur, 100)

    def heal(self):
        self.rec('heal', self.cur)
        self.hp[self.cur] = 100

    def quest(self, args, timeout):
        self.rec('quest', self.cur, tuple(args))
        return (self.quest_q.pop(0) if self.quest_q else 0), []

    def team_form_regroup(self):
        self.rec('form_regroup', self.cur)
        return self.form_rc

    def team_disband(self):
        self.rec('disband', self.cur)
        return self.disband_rc

    def snap(self, tag):
        self.rec('snap', tag)


def go(T, **kw):
    return quiet(br.run, '琉璃洞窟', tools=T, **kw)


# ---- 純函式 ----
check('lag same', br.lag(3, 3) == 'same')
check('lag behind', br.lag(4, 3) == 'behind')
check('lag ref GONE → behind', br.lag('GONE', 4) == 'behind')
check('lag who GONE → ahead', br.lag(4, 'GONE') == 'ahead')
check('lag 讀不到 → unknown', br.lag(None, 3) == 'unknown' and br.lag(3, None) == 'unknown')
check('team_roles', br.team_roles(cards()) == ('DKBO', ['DKBO5']))
check('classify', [br.classify_quest(x) for x in (37, 38, 0, 21, 5, 39, 9, 10, 2, 77)] ==
      ['boss', 'boss', 'slice', 'knocked', 'gone', 'manual', 'verify', 'halt', 'verify', 'other'])

# ---- 其實沒缺人 ----
T = Fake(check_rcs=(0,))
rc = go(T)
check('team.check 0 → 0 不動', rc == 0 and T.names() == ['check'] and br.LAST.get('noop'), T.calls)

# ---- 掉隊者步號與隊長相同：只補血、不重打，重組 ----
T = Fake(steps={'DKBO': [4], 'DKBO5': [4]}, hp={'DKBO5': 1})
rc = go(T)
n = T.names()
check('步號相同 → 0、補血、沒跑 quest', rc == 0 and 'quest' not in n and ('heal', 'DKBO5') in T.calls, T.calls)
check('收尾 ensure DKBO → form_regroup → check', n[-3:] == ['ensure', 'form_regroup', 'check'] and T.cur == 'DKBO', T.calls)

# ---- 落後：一片 BOSS 戰後追上 ----
T = Fake(steps={'DKBO': [4], 'DKBO5': [3, 4]}, quest=[37], hp={'DKBO5': 1})
rc = go(T)
q = [c for c in T.calls if c[0] == 'quest']
check('落後 → 補血後 quest 一片追上 → 0', rc == 0 and len(q) == 1 and q[0][1] == 'DKBO5' and '--team-size' in q[0][2] and br.LAST['done'] == {'DKBO5': 'caught_up'}, T.calls)
check('quest 前先補血', T.names().index('heal') < T.names().index('quest'))

# ---- 輸一次後補血再打贏 ----
T = Fake(steps={'DKBO': [4], 'DKBO5': [3, 3, 4]}, quest=[37, 37], hp={'DKBO5': 1})
T_hp_drop = T


def q2(args, timeout, T=T):
    T.rec('quest', T.cur, tuple(args))
    T.hp[T.cur] = 1                       # 每場打完都 HP 1
    return T.quest_q.pop(0), []


T.quest = q2
rc = go(T, max_tries=2)
check('輸 1 次 → 補血 → 再打追上 = 0', rc == 0 and T.names().count('heal') == 2 and br.LAST['tries'] == {'DKBO5': 1}, T.calls)

# ---- 輸到上限 → 144，且切回 DKBO ----
T = Fake(steps={'DKBO': [4], 'DKBO5': [3]}, quest=[37, 37, 37])
rc = go(T, max_tries=2)
check('輸 2 次 → 144、切回 DKBO', rc == br.EXIT_REFIGHT and T.calls[-1] == ('ensure', 'DKBO') and 'form_regroup' not in T.names(), T.calls)

# ---- 被打飛（21）算一次 ----
T = Fake(steps={'DKBO': [4], 'DKBO5': [3, 3, 4]}, quest=[21, 0])
rc = go(T)
check('21 → 算一次輸、下一片追上', rc == 0 and br.LAST['tries'] == {'DKBO5': 1}, T.calls)

# ---- 隊長步號讀不到 → 142，不打 ----
T = Fake(steps={'DKBO': [None]})
rc = go(T)
check('隊長步號讀不到 → 142、沒切掉隊者、沒 quest', rc == br.EXIT_STEP and ('switch', 'DKBO5') not in T.calls and 'quest' not in T.names(), T.calls)

# ---- 驗證視窗：9 透傳、不再點（不 ensure） ----
T = Fake(steps={'DKBO': [4], 'DKBO5': [3]}, quest=[9])
rc = go(T)
check('quest 9 → 9、之後沒有 ensure / form', rc == 9 and 'ensure' not in T.names() and 'form_regroup' not in T.names(), T.calls)

# ---- 不可逆對話 39 → 146 ----
T = Fake(steps={'DKBO': [4], 'DKBO5': [3]}, quest=[39])
rc = go(T)
check('quest 39 → 146', rc == br.EXIT_QUEST_MANUAL, T.calls)

# ---- 隊長任務完成（GONE），掉隊者跑到任務完成 ----
T = Fake(steps={'DKBO': ['GONE'], 'DKBO5': [5, 'GONE']}, quest=[0])
rc = go(T)
check('ref GONE → 掉隊者跑到 GONE = 0', rc == 0, T.calls)

# ---- 兩人掉隊：依序各自單人 ----
T = Fake(cards_=cards(members=('DKBO2', 'DKBO3'), solo=('DKBO4', 'DKBO5')), steps={'DKBO': [4], 'DKBO4': [3, 4], 'DKBO5': [4]}, quest=[37])
rc = go(T)
sw = [c[1] for c in T.calls if c[0] == 'switch']
check('兩人掉隊：DKBO4 重打、DKBO5 不用 = 0', rc == 0 and sw == ['DKBO4', 'DKBO5'] and br.LAST['done'] == {'DKBO4': 'caught_up', 'DKBO5': 'same'}, T.calls)

# ---- DKBO 自己被打飛：ref = DKBO2，收尾先切 DKBO2 解散 ----
T = Fake(cards_=cards(leader='DKBO2', members=('DKBO3', 'DKBO4', 'DKBO5'), solo=('DKBO',)), steps={'DKBO2': [4], 'DKBO': [4]})
rc = go(T)
check('DKBO 掉隊：讀 DKBO2 步號、DKBO2 解散、DKBO 重組 = 0', rc == 0 and ('disband', 'DKBO2') in T.calls and ('form_regroup', 'DKBO') in T.calls, T.calls)

# ---- 沒隊長 → 140 ----
T = Fake(cards_=cards(leader=None, members=(), solo=('DKBO', 'DKBO2', 'DKBO3', 'DKBO4', 'DKBO5')))
rc = go(T)
check('沒有隊長 → 140', rc == br.EXIT_TEAM_READ and 'quest' not in T.names(), T.calls)

# ---- 掉隊者名字讀不出 → 140 ----
cs = cards()
cs[4].name = None
T = Fake(cards_=cs, steps={'DKBO': [4]})
check('掉隊者名字讀不出 → 140', go(T) == br.EXIT_TEAM_READ)

# ---- 步號超前 → 144 ----
T = Fake(steps={'DKBO': [3], 'DKBO5': [5]})
check('掉隊者步號比隊長前 → 144', go(T) == br.EXIT_REFIGHT)

# ---- 重組失敗 → 145 ----
T = Fake(steps={'DKBO': [4], 'DKBO5': [4]}, form_rc=41)
check('form --regroup 失敗 → 145', go(T) == br.EXIT_REGROUP)

# ---- 切角色失敗 → 141 ----
T = Fake(steps={'DKBO': [4]}, switch_rc={'DKBO5': 62})
check('切到掉隊者失敗 → 141', go(T) == br.EXIT_SWITCH)

# ---- dry-run / plan 不碰遊戲 ----
out = io.StringIO()
with contextlib.redirect_stdout(out):
    rc = br.main(['plan', '--track', '琉璃洞窟'])
check('plan 印流程、rc 0', rc == 0 and 'team.check' in out.getvalue() and '144' in out.getvalue())

print('全部通過' if not fails else f'{fails} 項失敗')
sys.exit(1 if fails else 0)
