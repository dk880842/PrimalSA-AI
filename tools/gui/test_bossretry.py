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
    """steps：{角色: [步號序列]}（read_step 依當前角色取，最後一個重複）；quest：[rc…]；team_hp：[(rc, {角色: %})…]"""

    def __init__(self, check_rcs=(41, 0), cards_=None, steps=None, quest=None, team_hp=None, cur='DKBO', **kw):
        self.calls, self.cur = [], cur
        self.check_rcs = list(check_rcs)
        self.cards = cards() if cards_ is None else cards_
        self.steps = {k: list(v) for k, v in (steps or {}).items()}
        self.quest_q = list(quest or [])
        self.hp_q = list(team_hp or [])
        self.switch_rc = kw.get('switch_rc', {})
        self.form_rc = kw.get('form_rc', {})
        self.disband_rc = kw.get('disband_rc', 0)
        self.pre_rc = kw.get('pre_rc', 0)
        self.bad_lead = kw.get('bad_lead', ())

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

    def team_hp(self):
        return self.hp_q.pop(0) if self.hp_q else (0, {r: 100 for r in ('DKBO', 'DKBO2', 'DKBO3', 'DKBO4', 'DKBO5')})

    def heal(self):
        self.rec('heal', self.cur)

    def quest(self, args, timeout):
        self.rec('quest', self.cur, tuple(str(a) for a in args))
        return (self.quest_q.pop(0) if self.quest_q else 0), []

    def team_form_as(self, leader):
        self.rec('form', leader)
        rc = self.form_rc.get(leader, 0)
        if not rc:
            self.cur = leader
            names = ('DKBO', 'DKBO2', 'DKBO3', 'DKBO4', 'DKBO5')
            self.cards = cards(leader=leader, members=[n for n in names if n != leader], solo=())
            if leader in self.bad_lead:                     # 組完隊長不是 leader（測驗證）
                self.cards = cards(leader='DKBO', members=[n for n in names if n != 'DKBO'], solo=())
        return rc

    def team_disband(self):
        self.rec('disband', self.cur)
        if not self.disband_rc:
            self.cards = cards(leader=None, members=(), solo=('DKBO', 'DKBO2', 'DKBO3', 'DKBO4', 'DKBO5'))
        return self.disband_rc

    def snap(self, tag):
        self.rec('snap', tag)

    battle_rc = 0

    def battle_check(self):
        self.rec('battle_check')
        return self.battle_rc, {}, '假：戰鬥設定' if self.battle_rc else '', {'changed': {}, 'role': 'DKBO' if self.battle_rc else None}


def go(T, **kw):
    return quiet(br.run, '琉璃洞窟', tools=T, **kw)


LOW = (0, {'DKBO': 90, 'DKBO2': 90, 'DKBO3': 90, 'DKBO4': 90, 'DKBO5': 1})
FIVE = ('--team-size', '5')

# ---- 純函式 ----
check('lag same', br.lag(3, 3) == 'same')
check('lag behind', br.lag(4, 3) == 'behind')
check('lag ref GONE → behind', br.lag('GONE', 4) == 'behind')
check('lag who GONE → ahead', br.lag(4, 'GONE') == 'ahead')
check('lag 讀不到 → unknown', br.lag(None, 3) == 'unknown' and br.lag(3, None) == 'unknown')
check('team_roles', br.team_roles(cards()) == ('DKBO', ['DKBO5']))
check('classify', [br.classify_quest(x) for x in (37, 38, 0, 21, 5, 39, 9, 10, 2, 3, 30, 77)] ==
      ['boss', 'boss', 'slice', 'knocked', 'gone', 'manual', 'verify', 'halt', 'verify', 'no_track', 'team', 'other'])
check('classify --fight', [br.classify_quest(x, True) for x in (0, 35, 34)] == ['won', 'lost', 'manual'])

# ---- 其實沒缺人 ----
T = Fake(check_rcs=(0,))
rc = go(T)
check('team.check 0 → 0 不動', rc == 0 and T.names() == ['check'] and br.LAST.get('noop'), T.calls)

# ---- 掉隊者步號與隊長相同：不重打，DKBO 重組 ----
T = Fake(steps={'DKBO': [4], 'DKBO5': [4]})
rc = go(T)
n = T.names()
check('步號相同 → 0、沒跑 quest、DKBO 先解散舊隊', rc == 0 and 'quest' not in n and ('disband', 'DKBO') in T.calls, T.calls)
check('收尾 ensure DKBO → form DKBO → check', T.calls[-3:] == [('ensure', 'DKBO'), ('form', 'DKBO'), ('check',)] and T.cur == 'DKBO', T.calls)

# ---- 落後：以掉隊者為隊長組 5 人、補血、5 人一起打一片追上 → 掉隊者解散 → DKBO 重組 ----
T = Fake(steps={'DKBO': [4], 'DKBO5': [3, 4]}, quest=[37], team_hp=[LOW])
rc = go(T)
q = [c for c in T.calls if c[0] == 'quest']
check('落後 → 0、quest 1 片由 DKBO5 當隊長、--team-size 5', rc == 0 and len(q) == 1 and q[0][1] == 'DKBO5' and q[0][2][-2:] == FIVE and br.LAST['done'] == {'DKBO5': 'caught_up'}, T.calls)
order = [c for c in T.calls if c[0] in ('disband', 'switch', 'form', 'heal', 'quest', 'ensure')]
want = [('disband', 'DKBO'), ('switch', 'DKBO5'), ('form', 'DKBO5'), ('heal', 'DKBO5'), ('quest',), ('disband', 'DKBO5'), ('ensure', 'DKBO'), ('form', 'DKBO')]
check('順序：DKBO 解散 → 切 DKBO5 → 以 DKBO5 組隊 → 補血 → 打 → DKBO5 解散 → 切回 DKBO → DKBO 組隊',
      [c[:1] if c[0] == 'quest' else c for c in order] == want, order)

# ---- 輸一次（步號沒前進）→ 補血、重打追上 ----
T = Fake(steps={'DKBO': [4], 'DKBO5': [3, 3, 4]}, quest=[37, 37], team_hp=[(0, {'DKBO': 90}), LOW], check_rcs=(41, 0, 0))
rc = go(T, max_tries=2)
check('輸 1 次 → 補血 → 再打追上 = 0', rc == 0 and T.names().count('heal') == 1 and T.names().count('quest') == 2 and br.LAST['tries'] == {'DKBO5': 1}, T.calls)

# ---- 組完隊長不是落後者 → 145 ----
T = Fake(steps={'DKBO': [4], 'DKBO5': [3]}, quest=[37], bad_lead=('DKBO5',))
rc = go(T)
check('組完隊長不是 DKBO5 → 145、沒打', rc == br.EXIT_REGROUP and 'quest' not in T.names() and '隊長 DKBO' in br.LAST.get('msg', ''), br.LAST.get('msg'))
# ---- 隊伍散掉後隊長自動換人（實機 09:49：DKBO3 陣亡，剩下的隊長變 DKBO）→ 由真正的隊長解散再以落後者重組 ----
T = Fake(steps={'DKBO': ['GONE'], 'DKBO3': [4, 4, 'GONE']}, quest=[38, 0], check_rcs=(41, 0))
orig_q = T.quest
def q38(args, timeout, T=T, orig=orig_q):
    r = orig(args, timeout)
    if r[0] == 38:                                    # DKBO3 陣亡踢出，剩下的隊伍隊長變 DKBO
        T.cards = cards(leader='DKBO', members=('DKBO4', 'DKBO5'), solo=('DKBO2', 'DKBO3'))
    return r
T.quest = q38
rc = quiet(br.run, '四寶玉之謎', tools=T, who=['DKBO3'])
dis = [c for c in T.calls if c[0] == 'disband']
check('--who 隊散了 → 由現任隊長 DKBO 解散 → 以 DKBO3 重組 → 追上 0', rc == 0 and ('disband', 'DKBO') in dis[1:] and T.calls.count(('form', 'DKBO3')) == 2, T.calls)

# ---- --who 續跑：隊伍已由落後者帶滿 5 人 → 不解散、不重組 ----
T = Fake(steps={'DKBO5': [2, 'GONE'], 'DKBO3': ['GONE']}, quest=[0], cur='DKBO5', cards_=cards(leader='DKBO5', members=('DKBO', 'DKBO2', 'DKBO3', 'DKBO4'), solo=()), check_rcs=(0,))
rc = quiet(br.run, '四寶玉之謎', tools=T, who=['DKBO3', 'DKBO5'])
nm = [c for c in T.calls if c[0] in ('disband', 'form', 'switch')]
check('--who 續跑：DKBO5 帶的 5 人隊沿用（先處理 DKBO5、第一個動作不是解散 / 組隊）', rc == 0 and nm[0] == ('disband', 'DKBO5') and ('form', 'DKBO5') not in T.calls, T.calls)

# ---- BOSS 贏了但有人陣亡（38、步號前進）→ 先重組、再看全隊 HP 補血（2026-10-12 DKBO5 實機全滅）----
T = Fake(steps={'DKBO': [4], 'DKBO5': [2, 3, 4]}, quest=[38, 37], team_hp=[(0, {'DKBO': 90}), LOW, (0, {'DKBO': 90})], check_rcs=(41, 41, 0))
rc = go(T)
seq = [c[:2] for c in T.calls if c[0] in ('form', 'heal', 'quest')]
i_form2 = [k for k, c in enumerate(seq) if c == ('form', 'DKBO5')][1]
check('38 但步號前進 → 重組 DKBO5 → 再補血 → 下一片', rc == 0 and ('heal', 'DKBO5') in seq[i_form2:] and seq.index(('heal', 'DKBO5'), i_form2) < len(seq) - 1, seq)

# ---- 輸到上限 → 144；失敗收尾：DKBO5 臨時隊解散、切回 DKBO ----
T = Fake(steps={'DKBO': [4], 'DKBO5': [3]}, quest=[37, 37, 37], check_rcs=(41, 0))
rc = go(T, max_tries=2)
check('輸 2 次 → 144', rc == br.EXIT_REFIGHT, T.calls)
check('144 收尾：DKBO5 解散臨時隊 → 切回 DKBO、沒有重組', T.calls[-2:] == [('disband', 'DKBO5'), ('ensure', 'DKBO')] and ('form', 'DKBO') not in T.calls, T.calls)

# ---- 被打飛（21）算一次 + 隊伍散了 → 解散重組 ----
T = Fake(steps={'DKBO': [4], 'DKBO5': [3, 3, 4]}, quest=[21, 0], check_rcs=(41, 41, 0))
rc = go(T)
check('21 → 算一次輸、DKBO5 解散重組後再打追上', rc == 0 and br.LAST['tries'] == {'DKBO5': 1} and T.names().count('form') == 3, T.calls)

# ---- 38 但步號已追上 → 不算輸，直接完成 ----
T = Fake(steps={'DKBO': [4], 'DKBO5': [3, 4]}, quest=[38])
check('38 但步號追上 → 0', go(T) == 0 and br.LAST['tries'] == {})

# ---- 追蹤沒反應（3）→ 改 --fight --npc auto，打贏 ----
T = Fake(steps={'DKBO': [4], 'DKBO5': [3, 4]}, quest=[3, 0])
rc = go(T)
q = [c[2] for c in T.calls if c[0] == 'quest']
check('3 → 下一片 --fight --npc auto --team-size 5 → 追上', rc == 0 and len(q) == 2 and q[1][0] == '--fight' and 'auto' in q[1] and '5' in q[1], q)
T = Fake(steps={'DKBO': [4], 'DKBO5': [3]}, quest=[3, 3])
check('3 後 --fight 也 3 → 146', go(T) == br.EXIT_QUEST_MANUAL)
T = Fake(steps={'DKBO': [4], 'DKBO5': [3, 3, 4]}, quest=[3, 35, 37], check_rcs=(41, 0, 0))
check('--fight 35 = 輸一次，下一片再打追上', go(T) == 0 and br.LAST['tries'] == {'DKBO5': 1})

# ---- 隊長步號讀不到 → 142，不解散、不打 ----
T = Fake(steps={'DKBO': [None]})
rc = go(T)
check('隊長步號讀不到 → 142、沒解散、沒 quest', rc == br.EXIT_STEP and 'disband' not in T.names() and 'quest' not in T.names(), T.calls)

# ---- 驗證視窗：9 透傳、不再點 ----
T = Fake(steps={'DKBO': [4], 'DKBO5': [3]}, quest=[9])
rc = go(T)
check('quest 9 → 9、之後沒有 ensure / disband', rc == 9 and T.calls[-1] == ('snap', 'bossretry-verify'), T.calls)

# ---- 不可逆對話 39 → 146 ----
T = Fake(steps={'DKBO': [4], 'DKBO5': [3]}, quest=[39])
check('quest 39 → 146', go(T) == br.EXIT_QUEST_MANUAL)

# ---- 隊長任務完成（GONE），掉隊者隊跑到任務完成 ----
T = Fake(steps={'DKBO': ['GONE'], 'DKBO5': [5, 'GONE']}, quest=[0])
check('ref GONE → 掉隊者隊跑到 GONE = 0', go(T) == 0)

# ---- 兩人掉隊：逐一以落後者為隊長 ----
T = Fake(cards_=cards(members=('DKBO2', 'DKBO3'), solo=('DKBO4', 'DKBO5')), steps={'DKBO': [4], 'DKBO4': [3, 4], 'DKBO5': [3, 4]}, quest=[37, 37])
rc = go(T)
forms = [c[1] for c in T.calls if c[0] == 'form']
check('兩人掉隊：DKBO4 隊、DKBO5 隊各打一次，最後 DKBO 組隊', rc == 0 and forms == ['DKBO4', 'DKBO5', 'DKBO'] and br.LAST['done'] == {'DKBO4': 'caught_up', 'DKBO5': 'caught_up'}, T.calls)
T = Fake(cards_=cards(members=('DKBO2', 'DKBO3'), solo=('DKBO4', 'DKBO5')), steps={'DKBO': [4], 'DKBO4': [3, 4], 'DKBO5': [4]}, quest=[37])
rc = go(T)
check('兩人掉隊、DKBO5 已同步 → 只組 DKBO4 隊', rc == 0 and [c[1] for c in T.calls if c[0] == 'form'] == ['DKBO4', 'DKBO'], T.calls)

# ---- DKBO 自己被打飛：ref = DKBO2 讀步號並解散 ----
T = Fake(cards_=cards(leader='DKBO2', members=('DKBO3', 'DKBO4', 'DKBO5'), solo=('DKBO',)), steps={'DKBO2': [4], 'DKBO': [3, 4]}, quest=[37])
rc = go(T)
check('DKBO 掉隊：DKBO2 解散、DKBO 當隊長打、最後 DKBO 組隊 = 0', rc == 0 and ('disband', 'DKBO2') in T.calls and [c[1] for c in T.calls if c[0] == 'form'] == ['DKBO', 'DKBO'], T.calls)

# ---- 沒隊長 / 名字讀不出 → 140 ----
T = Fake(cards_=cards(leader=None, members=(), solo=('DKBO', 'DKBO2', 'DKBO3', 'DKBO4', 'DKBO5')))
check('沒有隊長 → 140', go(T) == br.EXIT_TEAM_READ and 'quest' not in T.names())
cs = cards()
cs[4].name = None
T = Fake(cards_=cs, steps={'DKBO': [4]})
check('掉隊者名字讀不出 → 140', go(T) == br.EXIT_TEAM_READ)

# ---- 步號超前 → 144 ----
T = Fake(steps={'DKBO': [3], 'DKBO5': [5]})
check('掉隊者步號比隊長前 → 144', go(T) == br.EXIT_REFIGHT)

# ---- 以掉隊者為隊長組隊失敗 → 145；DKBO 最後重組失敗 → 145 ----
T = Fake(steps={'DKBO': [4], 'DKBO5': [3]}, form_rc={'DKBO5': 44})
check('以 DKBO5 組隊失敗 → 145、沒打', go(T) == br.EXIT_REGROUP and 'quest' not in T.names())
T = Fake(steps={'DKBO': [4], 'DKBO5': [4]}, form_rc={'DKBO': 41})
check('最後 DKBO 組隊失敗 → 145', go(T) == br.EXIT_REGROUP)
T = Fake(steps={'DKBO': [4]}, disband_rc=45)
check('舊隊解散失敗 → 145', go(T) == br.EXIT_REGROUP)

# ---- 切角色失敗 → 141 ----
T = Fake(steps={'DKBO': [4]}, switch_rc={'DKBO5': 62})
check('切到掉隊者失敗 → 141', go(T) == br.EXIT_SWITCH)

# ---- 補血失敗 → 143 ----
T = Fake(steps={'DKBO': [4], 'DKBO5': [3]}, team_hp=[LOW])
T.heal = lambda: (_ for _ in ()).throw(RuntimeError('假：傳送失敗'))
check('補血失敗 → 143', go(T) == br.EXIT_HEAL)

# ---- 重打前 HP 偏低（含 0）→ 先補血、補完重讀確認（2026-10-15 四寶玉之謎連輸 3 次）----
Z = (0, {'DKBO': 100, 'DKBO2': 100, 'DKBO3': 0, 'DKBO4': 81, 'DKBO5': 41})
OK = (0, {r: 100 for r in ('DKBO', 'DKBO2', 'DKBO3', 'DKBO4', 'DKBO5')})
T = Fake(steps={'DKBO': [4], 'DKBO5': [3, 4]}, quest=[37], team_hp=[Z, OK])
rc = go(T)
n = T.names()
check('HP 0 / 41 / 81 → 補血 1 次 → 重讀 OK → 才打', rc == 0 and n.count('heal') == 1 and n.index('heal') < n.index('quest'), T.calls)
T = Fake(steps={'DKBO': [4], 'DKBO5': [3, 4]}, quest=[37], team_hp=[Z, Z, OK])
rc = go(T)
check('補完仍偏低 → 再補第 2 輪 → 確認 OK → 打', rc == 0 and T.names().count('heal') == 2 and T.names().count('quest') == 1, T.calls)
T = Fake(steps={'DKBO': [4], 'DKBO5': [3]}, quest=[37], team_hp=[Z, Z, Z])
rc = go(T)
check('補 2 輪仍偏低 → 148、沒打、收尾切回 DKBO', rc == br.EXIT_HEAL_VERIFY == 148 and 'quest' not in T.names() and T.calls[-2:] == [('disband', 'DKBO5'), ('ensure', 'DKBO')], T.calls)
T = Fake(steps={'DKBO': [4], 'DKBO5': [3, 4]}, quest=[37], team_hp=[(0, {'DKBO': 100, 'DKBO2': 79, 'DKBO3': 100, 'DKBO4': 100, 'DKBO5': 100}), OK])
check('79% < 80 門檻也補', go(T) == 0 and T.names().count('heal') == 1)
T = Fake(steps={'DKBO': [4], 'DKBO5': [3, 4]}, quest=[37], team_hp=[Z, (8, {})])
rc = go(T)
check('補完讀不到 HP → 放行（無法驗證）', rc == 0 and 'quest' in T.names(), T.calls)

# ---- dry-run / plan 不碰遊戲 ----
out = io.StringIO()
with contextlib.redirect_stdout(out):
    rc = br.main(['plan', '--track', '琉璃洞窟'])
check('plan 印流程、rc 0', rc == 0 and 'team.check' in out.getvalue() and '--team-size 5' in out.getvalue())

# ---- 戰鬥設定檢查（重打前；2026-10-12 DKBO 人物首次動作沒勾 → 打火雞輸）----
T = Fake(steps={'DKBO': [4], 'DKBO5': [3, 4]}, quest=[37], team_hp=[LOW])
rc = go(T)
n = T.names()
check('一般模式：team.check 不滿 → 戰鬥設定檢查（1 次）→ 才解散 / 重打', rc == 0 and n.count('battle_check') == 1 and n.index('check') < n.index('battle_check') < n.index('disband'), T.calls)
T = Fake(steps={'DKBO': [4], 'DKBO5': [3, 4]}, quest=[37])
T.battle_rc = 13
rc = go(T)
check('戰鬥設定失敗 → 147、不解散不打', rc == br.EXIT_BATTLESET and 'disband' not in T.names() and 'quest' not in T.names(), T.calls)
T = Fake(steps={'DKBO': [4], 'DKBO5': [3, 4]}, quest=[37])
T.battle_rc = 9
check('戰鬥設定 9 → 透傳 9', go(T) == 9)
T = Fake(steps={'DKBO': [4], 'DKBO5': [3, 4]}, quest=[37], team_hp=[LOW])
rc = go(T, battle_check=False)
check('battle_check=False → 不查', rc == 0 and 'battle_check' not in T.names())
T = Fake(check_rcs=(0,))
go(T)
check('其實沒缺人 → 不查戰鬥設定', 'battle_check' not in T.names())
T = Fake(steps={'DKBO3': [3, 'GONE']}, quest=[37], cards_=cards(leader='DKBO', members=('DKBO2', 'DKBO3', 'DKBO4', 'DKBO5'), solo=()))
T.battle_rc = 4
check('--who 模式：開頭就查，失敗 147', go(T, who=['DKBO3']) == br.EXIT_BATTLESET and T.names()[0] == 'battle_check' and 'disband' not in T.names(), T.calls)
check('plan 列戰鬥設定', any('battle_check' in ln for ln in br.plan_text('琉璃洞窟', {'hp_min': 60, 'max_slices': 6, 'max_tries': 2}))
      and any('不查' in ln for ln in br.plan_text('琉璃洞窟', {'hp_min': 60, 'max_slices': 6, 'max_tries': 2, 'battle_check': False, 'who': ['DKBO3']})))

print('全部通過' if not fails else f'{fails} 項失敗')
sys.exit(1 if fails else 0)
