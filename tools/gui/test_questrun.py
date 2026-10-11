#!/usr/bin/env python3
"""questrun.py / questhandlers.py 離線測試：完全不碰遊戲（假 Tools）。涵蓋 quest.py 退出碼各分支、續跑、dry-run / plan 輸出、
walk handler、龍王的守護節奏、失敗不恢復掛機。用法：uv run --no-project python tools/gui/test_questrun.py"""
import contextlib
import io
import os
import sys
import tempfile
from pathlib import Path

os.environ.setdefault('PSA_LAYOUT', '2880x1659')
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import errlog  # noqa: E402
import questdefs  # noqa: E402
import questhandlers  # noqa: E402
import questrun  # noqa: E402
import uikit  # noqa: E402

TMP = Path(tempfile.mkdtemp())
questrun.EVENT_LOG, questrun.QUEST_LOG, questrun.PROGRESS = TMP / 'ev.log', TMP / 'ql.md', TMP / 'qr.json'
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


def reset():
    for p in (questrun.PROGRESS, questrun.QUEST_LOG, questrun.EVENT_LOG):
        p.unlink(missing_ok=True)


# ================= FakeTools =================
class Fake:
    """status：{詳情標題: 狀態序列（每次 task_status 取一個，最後一個重複）}；quest：[(rc, tail)] 依序；steps：read_step 序列"""

    def __init__(self, status=None, quest=None, steps=None, **kw):
        self.calls = []
        self.status = {k: list(v) for k, v in (status or {}).items()}
        self.quest_q = list(quest or [])
        self.steps = list(steps or [])
        self.team_rcs = list(kw.get('team_rcs', []))
        self.accept_rc = kw.get('accept_rc', 0)
        self.hp = kw.get('hp', 100)
        self.bag = kw.get('bag', {r: 5 for r in questrun.ALL_ROLES})
        self.dragon_rc = kw.get('dragon_rc', 0)
        self.follow = kw.get('follow', False)
        self.cur = kw.get('cur', 'DKBO')
        self.walk_script = list(kw.get('walk', []))       # 每次 walk_to：Exception 或 (地圖, x, y)
        self.pos = kw.get('pos', (10204, 14, 7))
        self.grind_rc = kw.get('grind_rc', 0)
        self.pre_rc = kw.get('pre_rc', 0)

    def rec(self, *a):
        self.calls.append(a)

    def names(self):
        return [c[0] for c in self.calls]

    def sleep(self, s):
        pass

    def preflight(self):
        return self.pre_rc

    def follow_active(self):
        return 1234 if self.follow else None

    def follow_stop(self):
        self.rec('follow_stop')
        self.follow = False

    def encounter_off_wait(self):
        self.rec('enc_off')

    def current(self):
        return 0, self.cur

    def char_ensure(self, n):
        self.rec('char_ensure', n)
        self.cur = n
        return 0

    def team_form(self):
        self.rec('team_form')
        return self.team_rcs.pop(0) if self.team_rcs else 0

    def task_status(self, detail):
        self.rec('status', detail)
        q = self.status.get(detail)
        if q is None:
            return 0, None
        return 0, (q.pop(0) if len(q) > 1 else q[0])

    def accept(self, detail):
        self.rec('accept', detail)
        return self.accept_rc

    def read_step(self, track):
        return self.steps.pop(0) if self.steps else None

    def gone(self):
        return 'GONE'

    def hp_pct(self):
        return self.hp

    def heal(self):
        self.rec('heal')

    def bag_free(self, roles):
        return 0, dict(self.bag)

    def dragon(self, have=False):
        self.rec('dragon', have)
        return (self.dragon_rc, {'warn': '已取出'} if self.dragon_rc else {})

    def quest(self, args, timeout=0):
        self.rec('quest', tuple(str(a) for a in args))
        return self.quest_q.pop(0) if self.quest_q else (0, [])

    def read_pos(self):
        return self.pos

    def track(self, task):
        self.rec('track', task)
        return True

    def walk_to(self, m, x, y):
        self.rec('walk_to', m, x, y)
        r = self.walk_script.pop(0) if self.walk_script else (m, x, y)
        if isinstance(r, Exception):
            raise r
        self.pos = r
        return r

    def snap(self, tag):
        self.rec('snap', tag)

    def grind_start(self, spot):
        self.rec('grind_start', spot)
        return self.grind_rc


D17 = '彌生和日美子(1.82)'
D15 = '亞姆的斧頭(1.82)'
D99 = '成人儀式'


def go(fake, ids, **kw):
    reset()
    kw.setdefault('after', 'grind')
    return quiet(questrun.run, ids, tools=fake, **kw)


# ================= 純函式 / plan =================
check('classify 對照', [questrun.classify(c) for c in (0, 37, 38, 3, 5, 30, 32, 33, 25, 39, 2, 10, 21, 99)]
      == ['check', 'boss', 'boss_team', 'no_track', 'gone', 'team', 'team', 'stall', 'battle', 'irrev', 'verify', 'halt', 'knocked', 'other'])
buf = io.StringIO()
with contextlib.redirect_stdout(buf):
    rc_plan = questrun.run([2999, 2017], dry_run=True)
txt = buf.getvalue()
check('dry-run：rc 0、不碰 Tools（沒傳 tools 也不會建立遊戲動作）', rc_plan == 0 and '[任務 2999]' in txt and '[任務 2017]' in txt)
check('dry-run：列出 walk 步驟 / 退出碼 / 交接回去', 'kind=walk' in txt and '10204:188,13' in txt and '110 preflight' in txt and 'grind.py start --spot 地雷區' in txt)
check('dry-run：2017 不含 walk', txt.split('[任務 2017]')[1].count('kind=walk') == 0)
check('不認得的任務 ID → 1', quiet(questrun.run, [1234], dry_run=True) == uikit.EXIT_USAGE)
check('--after 非法 → 1', quiet(questrun.run, [2017], after='follow', dry_run=True) == uikit.EXIT_USAGE)

# ================= 流程 =================
# 1) 待接取 → 接取 → quest 回 0 → 已完成 → 恢復掛機
f = Fake(status={D17: [questrun.PENDING, questrun.DONE]}, quest=[(0, [])])
rc = go(f, [2017])
n = f.names()
check('待接取任務：交接 → 接取 → 跑 → 完成 → grind start', rc == 0 and n.count('accept') == 1 and ('grind_start', '地雷區') in f.calls and n.index('enc_off') < n.index('accept') < n.index('quest'), str(n))
check('接取前 / 後都 team.form（交任務前一定組隊）', n.count('team_form') >= 3)
check('quest 指令帶追蹤標題（不含 1.82）與 --max-seconds', ('quest', ('--task', '彌生和日美子', '--max-seconds', '300')) in f.calls)
check('龍王的守護跑第一片前吃（have=False）', ('dragon', False) in f.calls and n.index('dragon') < n.index('quest'))
check('進度檔記完成；quest-log 追加一筆', '"done"' in questrun.PROGRESS.read_text(encoding='utf-8') and '彌生和日美子' in questrun.QUEST_LOG.read_text(encoding='utf-8'))
check('LAST', questrun.LAST.get('ok') and questrun.LAST.get('done') == [2017])

# 2) 已完成 → 跳過（不接、不跑、不吃龍王），仍恢復掛機
f = Fake(status={D17: [questrun.DONE]})
rc = go(f, [2017])
check('已完成 → 跳過', rc == 0 and 'accept' not in f.names() and 'quest' not in f.names() and 'dragon' not in f.names() and ('grind_start', '地雷區') in f.calls)

# 3) 進行中（續跑）→ 不 accept、先 team.form
f = Fake(status={D17: [questrun.DOING, questrun.DONE]}, quest=[(0, [])])
rc = go(f, [2017])
check('進行中 → 續跑（不接取、先組隊）', rc == 0 and 'accept' not in f.names() and 'quest' in f.names() and f.names().count('team_form') >= 2)

# 4) 續跑 / 一片沒完成：回 0 但狀態進行中 → 下一片
f = Fake(status={D17: [questrun.DOING, questrun.DOING, questrun.DONE]}, quest=[(0, []), (0, [])])
rc = go(f, [2017])
check('quest 回 0 但仍進行中 → 再跑一片', rc == 0 and f.names().count('quest') == 2)

# 5) 37 = BOSS 贏且滿員 → 下一片
f = Fake(status={D17: [questrun.DOING, questrun.DONE]}, quest=[(37, []), (0, [])])
rc = go(f, [2017])
check('37 → 下一片', rc == 0 and f.names().count('quest') == 2)

# 6) 38 → 114，不恢復掛機
f = Fake(status={D17: [questrun.DOING]}, quest=[(38, [])])
rc = go(f, [2017])
check('38 → 114、不恢復掛機', rc == questrun.EXIT_TEAM and 'grind_start' not in f.names())

# 7) 30 隊伍不符：team.form 一次再跑；連續兩次 → 111
f = Fake(status={D17: [questrun.DOING, questrun.DONE]}, quest=[(30, []), (0, [])])
rc = go(f, [2017])
check('30 → team.form 後重跑成功', rc == 0 and f.names().count('quest') == 2)
f = Fake(status={D17: [questrun.DOING]}, quest=[(32, []), (32, [])])
check('32 連續兩次 → 111', go(f, [2017]) == questrun.EXIT_HANDOVER)

# 8) 3 追蹤沒反應、沒 walk 步驟 → 112
f = Fake(status={D17: [questrun.DOING]}, quest=[(3, [])])
check('3 且無 walk 步驟 → 112', go(f, [2017]) == questrun.EXIT_STEP and 'grind_start' not in f.names())

# 9) 5：詳情已完成 → 成功；仍進行中 → 112
f = Fake(status={D17: [questrun.DOING, questrun.DONE]}, quest=[(5, [])])
check('5 且詳情已完成 → 成功', go(f, [2017]) == 0)
f = Fake(status={D17: [questrun.DOING, questrun.DOING]}, quest=[(5, [])])
check('5 且仍進行中 → 112', go(f, [2017]) == questrun.EXIT_STEP)

# 10) 33 / 25 / 39 / 2 / 10 / 21 / 其他
for code, want, label in ((33, questrun.EXIT_STALL, '117'), (25, questrun.EXIT_BATTLE, '118'), (39, questrun.EXIT_IRREV, '116'),
                          (2, uikit.EXIT_UNKNOWN_SCREEN, '9（疑似驗證視窗）'), (10, uikit.EXIT_HALT, '10（斷線）'), (21, questrun.EXIT_TEAM, '114'), (77, questrun.EXIT_STEP, '112')):
    f = Fake(status={D17: [questrun.DOING]}, quest=[(code, [])])
    rc = go(f, [2017])
    check(f'quest {code} → {label}，不恢復掛機', rc == want and 'grind_start' not in f.names(), str(rc))
f = Fake(status={D17: [questrun.DOING]}, quest=[(2, [])])
go(f, [2017])
check('驗證視窗：存截圖、不再送任何 quest', ('snap', 'questrun-verify') in f.calls and f.names().count('quest') == 1)

# 11) 片數上限 / 時間上限
f = Fake(status={D17: [questrun.DOING]}, quest=[(0, [])] * 5)
check('片數上限 → 113', go(f, [2017], max_slices=3) == questrun.EXIT_SLICES and f.names().count('quest') == 3)

# 12) 接取失敗：119（含 128 條件不達標）；驗證 / 斷線碼透傳
f = Fake(status={D17: [questrun.PENDING]}, accept_rc=128)
check('accept 128 → 119、不跑 quest', go(f, [2017]) == questrun.EXIT_ACCEPT and 'quest' not in f.names())
f = Fake(status={D17: [questrun.PENDING]}, accept_rc=9)
check('accept 9 → 9 透傳', go(f, [2017]) == 9)

# 13) preflight：任務不在列表 / 狀態讀不到 → 110；follow 還在跑 → 先停；背包不足 → 110；HP 低 → 補血
f = Fake(status={})
check('詳情列表找不到 → 110', go(f, [2017]) == questrun.EXIT_PREFLIGHT)
f = Fake(status={D17: [questrun.DONE]}, follow=True)
go(f, [2017])
check('follow 在跑 → follow_stop', 'follow_stop' in f.names())
f = Fake(status={D99: [questrun.DOING]}, bag={'DKBO': 5, 'DKBO2': 0, 'DKBO3': 5, 'DKBO4': 5, 'DKBO5': 5})
check('背包空位不足 → 110', go(f, [2999]) == questrun.EXIT_PREFLIGHT and 'quest' not in f.names())
f = Fake(status={D17: [questrun.DOING, questrun.DONE]}, quest=[(0, [])], hp=30)
go(f, [2017])
check('HP 30% < 50% → 補血後重組隊', 'heal' in f.names() and f.names().index('heal') < f.names().index('quest'))
f = Fake(status={D17: [questrun.DONE]}, cur='DKBO3')
go(f, [2017])
check('當前角色不是 DKBO → char.ensure', ('char_ensure', 'DKBO') in f.calls)
f = Fake(status={D17: [questrun.DONE]}, team_rcs=[41])
check('交接 team.form 失敗 → 111', go(f, [2017]) == questrun.EXIT_HANDOVER and 'status' not in f.names())
f = Fake(status={D17: [questrun.DONE]}, pre_rc=9)
check('uikit.preflight 非 0 → 原碼', go(f, [2017]) == 9)

# 14) --after none：不恢復；grind 失敗 → 回 grind 碼
f = Fake(status={D17: [questrun.DONE]})
check('--after none 不恢復掛機', go(f, [2017], after='none') == 0 and 'grind_start' not in f.names())
f = Fake(status={D17: [questrun.DONE]}, grind_rc=55)
check('grind 失敗 → 55', go(f, [2017]) == 55)

# 15) 多任務：順序、一個失敗後面不跑
f = Fake(status={D99: [questrun.DONE], D17: [questrun.DOING, questrun.DONE], D15: [questrun.DONE]}, quest=[(0, [])])
rc = go(f, [2999, 2017, 2015])
check('多任務依序、已完成的跳過', rc == 0 and questrun.LAST['done'] == [2999, 2017, 2015] and f.names().count('quest') == 1)
f = Fake(status={D17: [questrun.DOING], D15: [questrun.DOING]}, quest=[(33, [])])
go(f, [2017, 2015])
check('第一個失敗 → 第二個不跑', f.names().count('quest') == 1 and D15 not in [c[1] for c in f.calls if c[0] == 'status'])

# 16) 龍王：失敗只警告、續跑（have=True）；9 分鐘內不重吃
f = Fake(status={D17: [questrun.DOING, questrun.DOING, questrun.DONE]}, quest=[(0, []), (0, [])], dragon_rc=92)
rc = go(f, [2017])
check('龍王失敗只警告、任務照跑', rc == 0 and f.names().count('quest') == 2)
check('龍王取出後失敗 → 下次 have=True', ('dragon', True) in f.calls, str([c for c in f.calls if c[0] == 'dragon']))
f = Fake(status={D17: [questrun.DOING, questrun.DOING, questrun.DONE]}, quest=[(0, []), (0, [])])
go(f, [2017])
check('9 分鐘內第二片不重吃', f.names().count('dragon') == 1)
f = Fake(status={D17: [questrun.DONE]})
go(f, [2017], use_dragon=False)
f = Fake(status={D17: [questrun.DOING, questrun.DONE]}, quest=[(0, [])])
go(f, [2017], use_dragon=False)
check('--no-dragon 不吃', 'dragon' not in f.names())

# ================= 2999：walk handler =================
S1 = questdefs.get(2999)['steps'][1]
f = Fake(pos=(10204, 14, 7))
rc, info = questhandlers.walk_step(f, '成人儀式', S1, log=lambda *a: None)
check('walk：在目標地圖 → walk_to 一次到達', rc == 0 and ('walk_to', 10204, 188, 13) in f.calls and info['tries'] == 2, str(info))
f = Fake(pos=(10204, 14, 7), walk=[RuntimeError('讀不到目前座標'), RuntimeError('不在地圖'), (10204, 188, 13)])
rc, info = questhandlers.walk_step(f, '成人儀式', S1, log=lambda *a: None)
check('walk：RuntimeError 外層重試直到到達', rc == 0 and f.names().count('walk_to') == 3 and len(info['errors']) == 2)
f = Fake(pos=(10204, 14, 7), walk=[RuntimeError('x')] * 30)
rc, info = questhandlers.walk_step(f, '成人儀式', S1, log=lambda *a: None, max_tries=5)
check('walk：一直失敗 → 112', rc == questrun.EXIT_STEP and f.names().count('walk_to') == 5)
f = Fake(pos=(60049, 30, 25))
rc, info = questhandlers.walk_step(f, '成人儀式', S1, log=lambda *a: None)
check('walk：不在目標地圖 → 點追蹤最多 2 次，仍不在 → 112（不亂 walk_to）', rc == questrun.EXIT_STEP and f.names().count('track') == 2 and 'walk_to' not in f.names())
f = Fake(pos=(10204, 187, 14))
rc, info = questhandlers.walk_step(f, '成人儀式', S1, log=lambda *a: None)
check('walk：已在 ±2 格內 → 0、不走', rc == 0 and 'walk_to' not in f.names())
f = Fake(pos=None)
rc, info = questhandlers.walk_step(f, '成人儀式', S1, log=lambda *a: None, max_tries=3)
check('walk：座標一直讀不到 → 112', rc == questrun.EXIT_STEP)

# 2999 整段：步 1（walk）→ quest 回 0（處理對話、巡路回審判）→ 已完成
f = Fake(status={D99: [questrun.DOING, questrun.DONE]}, steps=[1], quest=[(0, [])], pos=(10204, 14, 7))
rc = go(f, [2999])
n = f.names()
check('2999：步 1 先 walk 再 quest；背包 / HP 檢查；完成後恢復掛機', rc == 0 and n.index('walk_to') < n.index('quest') and ('grind_start', '地雷區') in f.calls, str(n))
f = Fake(status={D99: [questrun.DOING, questrun.DONE]}, steps=[2], quest=[(0, [])])
go(f, [2999])
check('2999：步 2（default）不 walk', 'walk_to' not in f.names() and 'quest' in f.names())
f = Fake(status={D99: [questrun.DOING, questrun.DOING, questrun.DONE]}, steps=[None, 2], quest=[(3, []), (0, [])])
rc = go(f, [2999])
check('2999：步號讀不到時 quest 回 3 → 112（沒有可走的 walk 步驟）', rc == questrun.EXIT_STEP)
f = Fake(status={D99: [questrun.DOING, questrun.DONE]}, steps=[None, 1], quest=[(3, []), (0, [])], pos=(10204, 14, 7))
rc = go(f, [2999])
check('2999：quest 回 3 後讀到步 1 → walk → 再跑 quest', rc == 0 and 'walk_to' in f.names() and f.names().count('quest') == 2)

# manual 步驟
orig = dict(questdefs.BY_ID[2017])
questdefs.BY_ID[2017]['steps'] = {1: dict(kind='manual')}
f = Fake(status={D17: [questrun.DOING]}, steps=[1])
rc = go(f, [2017])
check('kind=manual → 115、不跑 quest', rc == questrun.EXIT_MANUAL and 'quest' not in f.names())
questdefs.BY_ID[2017].clear()
questdefs.BY_ID[2017].update(orig)

print(f'\n{"全部通過" if not fails else f"失敗 {fails} 項"}')
sys.exit(1 if fails else 0)
