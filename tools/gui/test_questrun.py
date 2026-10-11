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
import testenv  # noqa: E402,F401  紀錄檔轉向暫存（不污染真 actions.log / quest-events.log / errlog）
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
        self.screen = kw.get('screen', 'idle')
        self.active = kw.get('active', False)

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

    def screen_state(self):
        return self.screen

    def esc(self):
        self.rec('esc')
        self.screen = 'idle'

    def encounter_off_wait(self):
        self.rec('enc_off')

    def current(self):
        return 0, self.cur

    def char_ensure(self, n):
        self.rec('char_ensure', n)
        self.cur = n
        return 0

    def close_stray(self):
        self.rec('close_stray')
        return False

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
        if self.accept_rc:
            return self.accept_rc, None
        q = self.status.get(detail)
        if q is None:
            return 121, None
        first = q.pop(0) if len(q) > 1 else q[0]
        return 0, {'已完成': 'done', '進行中': 'doing', '待接取': 'accepted'}[first]

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

    def dragon_active(self):
        return self.active

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


# ================= buff 列判斷（真實截圖 fixture）=================
import bag  # noqa: E402
import pngread  # noqa: E402
_, _, _bpp, _rows = pngread.decode((HERE / 'fixtures' / 'buff_row.png').read_bytes())
_OX, _OY = 70, 145


def _px(x, y):
    xx, yy = x - _OX, y - _OY
    if 0 <= yy < len(_rows) and 0 <= xx * _bpp < len(_rows[0]):
        i = xx * _bpp
        return _rows[yy][i], _rows[yy][i + 1], _rows[yy][i + 2]
    return 0, 0, 0


check('buff_classify：第 1 格 EXP、第 2 格龍王人形、第 3 格空', bag.buff_classify(_px) == ['exp', 'dragon', None], str(bag.buff_classify(_px)))
check('buff_classify：全黑 = 全空', bag.buff_classify(lambda x, y: (0, 0, 0)) == [None, None, None])

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

# 1b) quest.py 印「任務完成」→ 完全不再開詳情（整個任務詳情只開 1 次 = 接取那次）
f = Fake(status={D17: [questrun.PENDING, questrun.PENDING]}, quest=[(0, ['任務完成：彌生和日美子'])])
rc = go(f, [2017])
check('「任務完成」→ 不再讀詳情；詳情只開 1 次', rc == 0 and f.names().count('accept') == 1 and 'status' not in f.names())
check('quest-log 記詳情開啟次數 1', '詳情開啟 1 次' in questrun.QUEST_LOG.read_text(encoding='utf-8'))

# 2) 已完成 → 跳過（不接、不跑、不吃龍王），仍恢復掛機
f = Fake(status={D17: [questrun.DONE]})
rc = go(f, [2017])
check('已完成 → 跳過（只開一次詳情）', rc == 0 and f.names().count('accept') == 1 and 'status' not in f.names() and 'quest' not in f.names() and 'dragon' not in f.names() and ('grind_start', '地雷區') in f.calls)

# 3) 進行中（續跑）→ 不 accept、先 team.form
f = Fake(status={D17: [questrun.DOING, questrun.DONE]}, quest=[(0, [])])
rc = go(f, [2017])
check('進行中 → 續跑（詳情只開 1 次、先組隊）', rc == 0 and f.names().count('accept') == 1 and 'quest' in f.names() and f.names().count('team_form') >= 2)

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
f = Fake(status={D17: [questrun.DOING]}, quest=[(32, [])] * 4)
check('32 連續 4 次 → 111', go(f, [2017]) == questrun.EXIT_HANDOVER)

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
check('詳情列表找不到 → 119（接取失敗）', go(f, [2017]) == questrun.EXIT_ACCEPT)
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
f = Fake(status={D17: [questrun.DONE]}, team_rcs=[41, 41, 41])
check('交接 team.form 連續失敗 3 次 → 111', go(f, [2017]) == questrun.EXIT_HANDOVER and 'status' not in f.names() and f.names().count('team_form') == 3 and f.names().count('close_stray') == 3)
f = Fake(status={D17: [questrun.DONE]}, team_rcs=[42])
check('交接 team.form 失敗 1 次 → 關誤開面板後原地重試成功（不退出 111）', go(f, [2017]) == 0 and f.names().count('close_stray') == 1)
f = Fake(status={D17: [questrun.DONE]}, team_rcs=[9])
check('team.form 回 9（驗證視窗）→ 立即透傳、不重試', go(f, [2017]) == 9 and f.names().count('team_form') == 1)
f = Fake(status={D17: [questrun.PENDING, questrun.DONE]}, quest=[(32, []), (0, ['任務完成：x'])], team_rcs=[0, 42, 0])
rc = go(f, [2017])
check('接取後 / quest 回 32：原地 form 重試 + 再起一片，整個流程不退出（單次 run 完成）', rc == 0 and f.names().count('quest') == 2 and ('grind_start', '地雷區') in f.calls)

# 進度檔記「已完成」：重啟續跑直接跳過、不開詳情（2 小時內）；超過 / --no-trust-progress 就重讀
f = Fake(status={D17: [questrun.PENDING, questrun.DONE]}, quest=[(0, ['任務完成：x'])])
go(f, [2017])
f2 = Fake(status={D17: [questrun.DOING]})
quiet(questrun.run, [2017], tools=f2, after='grind')              # 不 reset：沿用上一輪的進度檔
check('進度檔已完成 → 重跑直接跳過：不 accept、不 team_form 組隊、不跑 quest、仍恢復掛機', f2.names().count('accept') == 0 and 'quest' not in f2.names() and ('grind_start', '地雷區') in f2.calls)
f3 = Fake(status={D17: [questrun.DONE]})
quiet(questrun.run, [2017], tools=f3, after='grind', trust_progress=False)
check('--no-trust-progress → 仍開詳情讀一次', f3.names().count('accept') == 1)
import json as _json
_st = _json.loads(questrun.PROGRESS.read_text(encoding='utf-8'))
_st['tasks']['2017']['ended_ts'] = 1.0
questrun.PROGRESS.write_text(_json.dumps(_st), encoding='utf-8')
f4 = Fake(status={D17: [questrun.DONE]})
quiet(questrun.run, [2017], tools=f4, after='grind')
check('完成記錄超過 2 小時 → 不信、開詳情讀一次（可能轉生重置過）', f4.names().count('accept') == 1)
f = Fake(status={D17: [questrun.DONE]}, pre_rc=9)
check('uikit.preflight 非 0 → 原碼', go(f, [2017]) == 9)

f = Fake(status={D99: [questrun.DOING, questrun.DONE]}, quest=[(0, [])], screen='dialog')
go(f, [2999])
check('畫面停在對話窗 → 先 ESC 再交接', f.names().index('esc') < f.names().index('enc_off') and f.names().count('quest') == 1)

f = Fake(status={D17: [questrun.DOING, questrun.DONE]}, quest=[(0, [])], active=True)
go(f, [2017])
check('人形圖示在 → 不吃', 'dragon' not in f.names())
f = Fake(status={D17: [questrun.DOING, questrun.DONE]}, quest=[(0, [])], active=None)
go(f, [2017])
check('圖示讀不到 → 退回計時（第一次會吃）', f.names().count('dragon') == 1)

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
f = Fake(status={D17: [questrun.DOING, questrun.DOING, questrun.DONE]}, quest=[(0, []), (0, [])], active=None)
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
check('2999：步 1 自動巡路優先（quest 回 0、不 walk）', rc == 0 and 'walk_to' not in f.names() and f.names().count('quest') == 1)
f = Fake(status={D99: [questrun.DOING, questrun.DONE]}, steps=[1, 1], quest=[(3, []), (0, [])], pos=(10204, 14, 7))
rc = go(f, [2999])
n = f.names()
check('2999：步 1 quest 回 3 → 才 walk 再 quest；完成後恢復掛機', rc == 0 and n.count('quest') == 2 and n.index('quest') < n.index('walk_to') < len(n) - n[::-1].index('quest') - 1 and ('grind_start', '地雷區') in f.calls, str(n))
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

# ================= quest.track_task：目前頁先看、命中就不捲動；標題不符絕不點 =================
import quest  # noqa: E402
_sv = (quest.gui, quest.ensure_task_tab, quest._tm_has, quest._find_on_page, quest.scroll_list, quest.list_signature, quest.event, quest.log)
clicks, scrolls = [], []
quest.gui = lambda *a, **k: clicks.append(a) or ''
quest.ensure_task_tab = lambda: None
quest._tm_has = lambda w: False
quest.list_signature = lambda: 'sig'
quest.event = lambda *a, **k: None
quest.log = lambda *a, **k: None
quest.scroll_list = lambda *a, **k: (scrolls.append(a), (False, 'sig'))[1]
quest._find_on_page = lambda want, mode: 310 if want == '彌生和日美子' else None
clicks.clear()
check('track_task：目前頁就是目標 → 直接點、0 次捲動', quest.track_task('彌生和日美子') is True and not scrolls and any('click 205' in str(c) for c in clicks))
clicks.clear()
check('track_task：目前頁是別的任務（漆黑洞窟二轉）→ 不點它；沒找到回 False 且不點任何卡片', quest.track_task('漆黑洞窟(二轉)') is False and not any('click 205' in str(c) for c in clicks))
(quest.gui, quest.ensure_task_tab, quest._tm_has, quest._find_on_page, quest.scroll_list, quest.list_signature, quest.event, quest.log) = _sv

# ================= quest.close_stray_panel：誤開的組隊 / 切換面板自動關、不算驗證視窗 =================
_so = (uikit.is_open, uikit.close_panel, quest.event, quest.log)
_closed = []
uikit.is_open = lambda p: p.name == 'TEAMPANEL'
uikit.close_panel = lambda p, known_open=False: (_closed.append(p.name), True)[1]
quest.event = lambda *a, **k: None
quest.log = lambda *a, **k: None
check('close_stray_panel：組隊面板開著 → 關它並回 True', quest.close_stray_panel() is True and _closed == ['TEAMPANEL'])
uikit.is_open = lambda p: False
check('close_stray_panel：沒有已知面板 → False（照舊當不認得）', quest.close_stray_panel() is False)
uikit.is_open, uikit.close_panel, quest.event, quest.log = _so

print(f'\n{"全部通過" if not fails else f"失敗 {fails} 項"}')
sys.exit(1 if fails else 0)
