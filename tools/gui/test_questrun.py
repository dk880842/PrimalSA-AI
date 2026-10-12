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
        self.team_hp_seq = list(kw.get('team_hp', []))     # 每次 team_hp 取一個 (rc, {角色: %})；空 = 全員 100
        self.team_hp_n = 0
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
        self.boss_q = list(kw.get('boss', [(144, {'msg': '假：重打失敗'})]))   # 每次 boss_retry 取一個 (rc, info)，最後一個重複

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
        self.rec('current')
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

    def team_hp(self):
        self.team_hp_n += 1
        if self.team_hp_seq:
            return self.team_hp_seq.pop(0)
        return 0, {r: 100 for r in questrun.ALL_ROLES}

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
        self.timeouts = getattr(self, 'timeouts', []) + [timeout]
        return self.quest_q.pop(0) if self.quest_q else (0, [])

    def read_pos(self):
        return self.pos

    def track(self, task):
        self.rec('track', task)
        return True

    def unstick_exit(self):
        self.rec('unstick_exit')
        return None

    def unfreeze(self):
        self.rec('unfreeze')
        return None

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

    def boss_retry(self, track, who=None):
        self.rec(*(('boss_retry', track) if who is None else ('boss_retry', track, tuple(who))))
        return self.boss_q.pop(0) if len(self.boss_q) > 1 else self.boss_q[0]

    def status_all(self, detail, roles):
        """all_q：每次取一個 {角色: 狀態 | None(讀不到)}（最後一個重複）；沒給 = 全員已完成"""
        self.rec('status_all', detail, tuple(roles))
        q = getattr(self, 'all_q', None)
        if not q:
            return 0, {r: {detail: '已完成'} for r in roles}
        m = q.pop(0) if len(q) > 1 else q[0]
        res = {r: (None if m.get(r, '已完成') is None else {detail: m.get(r, '已完成')}) for r in roles}
        return (1 if any(v is None for v in res.values()) else 0), res


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
check('交接 form + 接取後 form（傳送後一定重組）；接取前交接剛組過 → 略過（2026-10-12）', n.count('team_form') == 2 and n.index('accept') < len(n) - 1 - n[::-1].index('team_form') < n.index('quest'), str(n))
check('quest 指令帶追蹤標題（不含 1.82）、--max-seconds；接取後剛組過隊 → --team-fresh', ('quest', ('--task', '彌生和日美子', '--max-seconds', '60', '--team-fresh')) in f.calls, str(f.calls))
check('交接不再另讀當前角色（team.form 同一次面板確認）', 'current' not in n and 'char_ensure' not in n)
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
check('進行中 → 續跑（詳情只開 1 次；交接剛組過隊，接取前不重組）', rc == 0 and f.names().count('accept') == 1 and 'quest' in f.names() and f.names().count('team_form') == 1, str(f.names()))
_tf = questrun.TEAM_FRESH_S
questrun.TEAM_FRESH_S = -1.0                                   # 隊伍確認永遠「不新鮮」
f = Fake(status={D17: [questrun.PENDING, questrun.DONE]}, quest=[(0, [])])
go(f, [2017])
check('隊伍確認過期 → 交接 / 接取前 / 接取後各 form 一次、quest 不帶 --team-fresh', f.names().count('team_form') == 3 and not any('--team-fresh' in c[1] for c in f.calls if c[0] == 'quest'), str(f.calls))
questrun.TEAM_FRESH_S = _tf
f = Fake(status={D17: [questrun.DOING, questrun.DONE]}, quest=[(37, []), (0, ['時間到，結束']), (0, ['任務完成：x'])])
go(f, [2017])
qa = [c[1] for c in f.calls if c[0] == 'quest']
check('37（quest.py 剛驗過滿 5 人）→ 下一片帶 --team-fresh；「時間到」之後的那片不帶', len(qa) == 3 and '--team-fresh' in qa[1] and '--team-fresh' not in qa[2], str(qa))
f = Fake(status={D17: [questrun.DOING, questrun.DONE]}, quest=[(30, []), (0, ['任務完成：x'])])
go(f, [2017])
qa = [c[1] for c in f.calls if c[0] == 'quest']
check('30 → form 成功 → 下一片帶 --team-fresh', len(qa) == 2 and '--team-fresh' in qa[1], str(qa))

# 4) 續跑 / 一片沒完成：回 0 但狀態進行中 → 下一片
f = Fake(status={D17: [questrun.DOING, questrun.DOING, questrun.DONE]}, quest=[(0, []), (0, [])])
rc = go(f, [2017])
check('quest 回 0 但仍進行中 → 再跑一片', rc == 0 and f.names().count('quest') == 2)

# 5) 37 = BOSS 贏且滿員 → 下一片
f = Fake(status={D17: [questrun.DOING, questrun.DONE]}, quest=[(37, []), (0, [])])
rc = go(f, [2017])
check('37 → 下一片', rc == 0 and f.names().count('quest') == 2)

# 6) 38 → bossretry：失敗 → 114、不恢復掛機
f = Fake(status={D17: [questrun.DOING]}, quest=[(38, [])])
rc = go(f, [2017])
check('38 → bossretry 失敗 → 114、不恢復掛機', rc == questrun.EXIT_TEAM and f.names().count('boss_retry') == 1 and 'grind_start' not in f.names()
      and questrun.LAST['info'].get('boss_retry_rc') == 144, str(questrun.LAST.get('info')))
# 6b) 38 → bossretry 成功 → 補血檢查 → 下一片（--team-fresh）→ 完成
f = Fake(status={D17: [questrun.DOING, questrun.DONE]}, quest=[(38, []), (0, [])], boss=[(0, {'done': {'DKBO5': 'caught_up'}})])
rc = go(f, [2017])
qs = [c for c in f.calls if c[0] == 'quest']
check('38 → bossretry 0 → 下一片續跑、完成', rc == 0 and f.names().count('boss_retry') == 1 and len(qs) == 2 and '--team-fresh' in qs[1][1], str(f.calls))
check('bossretry 帶追蹤標題、結果記進 info', ('boss_retry', questdefs.get(2017)['track']) in f.calls)
# 6c) 21 被打飛也走 bossretry
f = Fake(status={D17: [questrun.DOING, questrun.DONE]}, quest=[(21, []), (0, [])], boss=[(0, {})])
check('21 → bossretry 0 → 續跑完成', go(f, [2017]) == 0 and f.names().count('boss_retry') == 1)
# 6d) 每任務最多 BOSS_RETRY_MAX 次
f = Fake(status={D17: [questrun.DOING]}, quest=[(38, [])] * 6, boss=[(0, {})])
rc = go(f, [2017])
check(f'38 連續 → bossretry {questrun.BOSS_RETRY_MAX} 次後 114', rc == questrun.EXIT_TEAM and f.names().count('boss_retry') == questrun.BOSS_RETRY_MAX, str(f.names().count('boss_retry')))
# 6e) --no-boss-retry → 直接 114；bossretry 9 透傳
f = Fake(status={D17: [questrun.DOING]}, quest=[(38, [])], boss=[(0, {})])
check('--no-boss-retry → 114、沒呼叫 bossretry', go(f, [2017], boss_retry=False) == questrun.EXIT_TEAM and 'boss_retry' not in f.names())
f = Fake(status={D17: [questrun.DOING]}, quest=[(38, [])], boss=[(9, {})])
check('bossretry 9 → 9 透傳', go(f, [2017]) == uikit.EXIT_UNKNOWN_SCREEN)

# 6f) 逐人驗證（2026-10-12 四寶玉之謎：隊長完成、DKBO3 / DKBO5 沒完成）
DONE_TAIL = (0, ['任務完成'])
others = tuple(r for r in questrun.ALL_ROLES if r != questrun.LEADER)
f = Fake(status={D17: [questrun.DOING]}, quest=[DONE_TAIL])
check('完成後逐人驗：其他 4 人都已完成 → 0、只讀 1 次、沒 bossretry', go(f, [2017]) == 0 and f.calls.count(('status_all', D17, others)) == 1
      and 'boss_retry' not in f.names(), str([c for c in f.calls if c[0] == 'status_all']))
f = Fake(status={D17: [questrun.DOING]}, quest=[DONE_TAIL], boss=[(0, {})])
f.all_q = [{'DKBO3': questrun.DOING, 'DKBO5': questrun.DOING}, {}]
rc = go(f, [2017])
check('有人進行中 → bossretry --who 落後者 → 只重讀那兩人 → 0', rc == 0 and ('boss_retry', questdefs.get(2017)['track'], ('DKBO3', 'DKBO5')) in f.calls
      and ('status_all', D17, ('DKBO3', 'DKBO5')) in f.calls and 'grind_start' in f.names(), str(f.calls[-6:]))
f = Fake(status={D17: [questrun.DOING]}, quest=[DONE_TAIL], boss=[(0, {})])
f.all_q = [{'DKBO5': questrun.DOING}]
rc = go(f, [2017])
check('bossretry 後仍進行中 → 108、不恢復掛機', rc == questrun.EXIT_LAGGARD and f.names().count('boss_retry') == 1 and 'grind_start' not in f.names()
      and questrun.LAST['info'].get('laggards') == ['DKBO5'], str(questrun.LAST.get('info', {}).get('msg')))
f = Fake(status={D17: [questrun.DOING]}, quest=[DONE_TAIL], boss=[(144, {'msg': '假'})])
f.all_q = [{'DKBO3': questrun.DOING}]
check('bossretry 失敗 → 108（boss_retry_rc 記下）', go(f, [2017]) == questrun.EXIT_LAGGARD and questrun.LAST['info'].get('boss_retry_rc') == 144)
f = Fake(status={D17: [questrun.DOING]}, quest=[DONE_TAIL], boss=[(9, {})])
f.all_q = [{'DKBO3': questrun.DOING}]
check('bossretry 9 → 9 透傳', go(f, [2017]) == uikit.EXIT_UNKNOWN_SCREEN)
f = Fake(status={D17: [questrun.DOING]}, quest=[DONE_TAIL])
f.all_q = [{'DKBO4': None}]
check('某人讀不到 → 108、不盲打 bossretry', go(f, [2017]) == questrun.EXIT_LAGGARD and 'boss_retry' not in f.names())
f = Fake(status={D17: [questrun.DOING]}, quest=[DONE_TAIL])
f.all_q = [{'DKBO2': questrun.PENDING}]
check('某人待接取（沒接到）→ 108、不 bossretry', go(f, [2017]) == questrun.EXIT_LAGGARD and 'boss_retry' not in f.names())
f = Fake(status={D17: [questrun.DOING]}, quest=[DONE_TAIL])
f.all_q = [{'DKBO3': questrun.DOING}]
check('--no-boss-retry：有人沒完成 → 108', go(f, [2017], boss_retry=False) == questrun.EXIT_LAGGARD and 'boss_retry' not in f.names())
f = Fake(status={D17: [questrun.DOING]}, quest=[DONE_TAIL])
f.all_q = [{'DKBO3': questrun.DOING}]
check('--no-verify-all → 不讀、0', go(f, [2017], verify_all=False) == 0 and 'status_all' not in f.names())
f = Fake(status={D17: [questrun.DONE]})
check('詳情一開就已完成 → 預設不逐人驗', go(f, [2017]) == 0 and 'status_all' not in f.names())
f = Fake(status={D17: [questrun.DONE]}, boss=[(0, {})])
f.all_q = [{'DKBO3': questrun.DOING}, {}]
check('--verify-skipped：已完成跳過的也驗 → 補人 → 0', go(f, [2017], verify_skipped=True) == 0 and f.names().count('boss_retry') == 1)

# 7) 30 隊伍不符：team.form 一次再跑；連續兩次 → 111
f = Fake(status={D17: [questrun.DOING, questrun.DONE]}, quest=[(30, []), (0, [])])
rc = go(f, [2017])
check('30 → team.form 後重跑成功', rc == 0 and f.names().count('quest') == 2)
f = Fake(status={D17: [questrun.DOING]}, quest=[(32, [])] * 4)
check('32 連續 4 次 → 111', go(f, [2017]) == questrun.EXIT_HANDOVER)

# 8) 3 追蹤沒反應、沒 walk 步驟 → 112
f = Fake(status={D17: [questrun.DOING]}, quest=[(3, [])] * 8)
check('3 且無 walk 步驟 → 112', go(f, [2017]) == questrun.EXIT_STEP and 'grind_start' not in f.names())
f = Fake(status={D17: [questrun.DOING, questrun.DONE]}, quest=[(3, []), (0, [])])
rc = go(f, [2017])
check('3 且無 walk 步驟 → 先 unfreeze（刷新 + 出口格重踏）再重跑 quest', rc == 0 and f.names().count('unfreeze') == 1 and f.names().count('quest') == 2, str(f.names()))

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
# 13b) 全隊 HP（2026-10-12 四寶玉之謎：只看隊長 → 隊員約 50% 連打 BOSS 被打死踢隊 4 次 38）
f = Fake(status={D17: [questrun.DOING, questrun.DONE]}, quest=[(0, [])], team_hp=[(0, {'DKBO': 90, 'DKBO2': 95, 'DKBO3': 45, 'DKBO4': 100, 'DKBO5': None})])
go(f, [2017])
n = f.names()
check('任務前隊員 DKBO3 45% < 60% → 補血（整隊）→ team.form → 才跑 quest', 'heal' in n and n.index('heal') < n.index('quest') and 'team_form' in n[n.index('heal'):n.index('quest')], str(n))
f = Fake(status={D17: [questrun.DOING, questrun.DONE]}, quest=[(0, [])], team_hp=[(0, {'DKBO': 90, 'DKBO2': 95, 'DKBO3': 80, 'DKBO4': 100, 'DKBO5': None})])
go(f, [2017])
check('全隊 ≥ 60%（有人讀不出）→ 不補血', 'heal' not in f.names() and f.team_hp_n == 1)
f = Fake(status={D17: [questrun.DOING, questrun.DONE]}, quest=[(37, []), (0, ['任務完成：x'])],
         team_hp=[(0, {r: 100 for r in questrun.ALL_ROLES}), (0, {'DKBO': 70, 'DKBO2': 70, 'DKBO3': 70, 'DKBO4': 70, 'DKBO5': 30})])
rc = go(f, [2017])
n = f.names()
qs = [i for i, c in enumerate(n) if c == 'quest']
check('BOSS 戰後（37）DKBO5 30% → 下一片前補血 + 組隊', rc == 0 and f.team_hp_n == 2 and len(qs) == 2 and 'heal' in n and qs[0] < n.index('heal') < qs[1]
      and 'team_form' in n[n.index('heal'):qs[1]], str(n))
f = Fake(status={D17: [questrun.DOING, questrun.DONE]}, quest=[(0, [])], team_hp=[(90, {})])
check('全隊讀不到（bag 90）→ 不補血、照跑（只看隊長）', go(f, [2017]) == 0 and 'heal' not in f.names() and 'quest' in f.names())
f = Fake(status={D17: [questrun.DOING, questrun.DONE]}, quest=[(0, [])], team_hp=[(9, {})])
check('全隊讀 HP 時 bag 回 9（驗證視窗）→ 透傳 9、不跑 quest', go(f, [2017]) == 9 and 'quest' not in f.names())
f = Fake(status={D17: [questrun.DOING, questrun.DONE]}, quest=[(0, [])])
go(f, [2017], team_hp_min=0)
check('--team-hp-min 0 → 不讀全隊', f.team_hp_n == 0)
f = Fake(status={D17: [questrun.DOING]}, quest=[(19, [])])
check('quest.py 19（巡路卡住解卡失敗）→ 112', go(f, [2017]) == questrun.EXIT_STEP)
f = Fake(status={D17: [questrun.DOING, questrun.DONE]}, quest=[(19, []), (0, [])])
f.unstick_exit = lambda: (f.rec('unstick_exit'), (21010, 48, 48))[1]
check('quest.py 19 → 先 unstick_exit（刷新 + 走上附近出口）成功就再跑 quest', go(f, [2017]) == 0 and f.names().count('unstick_exit') == 1 and f.names().count('quest') == 2, str(f.names()))
f = Fake(status={D17: [questrun.DONE]}, cur='DKBO3')
go(f, [2017])
check('當前角色不是 DKBO：交接不另開面板讀（交給 team.form._finish 的 char.ensure）', 'current' not in f.names() and f.names().count('team_form') == 1, str(f.names()))
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

# 16) 龍王：失敗只警告、續跑（have=True）；人形圖示不在就吃
f = Fake(status={D17: [questrun.DOING, questrun.DOING, questrun.DONE]}, quest=[(0, []), (0, [])], dragon_rc=92)
rc = go(f, [2017])
check('龍王失敗只警告、任務照跑', rc == 0 and f.names().count('quest') == 2)
check('龍王取出後失敗 → 下次 have=True', ('dragon', True) in f.calls, str([c for c in f.calls if c[0] == 'dragon']))
f = Fake(status={D17: [questrun.DOING, questrun.DOING, questrun.DONE]}, quest=[(0, []), (0, [])], active=None)
go(f, [2017])
check('buff 列沒人形圖示 → 每次都吃（不看時間）', f.names().count('dragon') >= 2)
f = Fake(status={D17: [questrun.DONE]})
go(f, [2017], use_dragon=False)
f = Fake(status={D17: [questrun.DOING, questrun.DONE]}, quest=[(0, [])])
go(f, [2017], use_dragon=False)
check('--no-dragon 不吃', 'dragon' not in f.names())
# 16b) dragon_used = 本次 run 吃的（進度檔累計另放 dragon_used_total；舊版 --no-dragon 仍顯示 6）
reset()
questrun.save_progress({'tasks': {}, 'dragon_used': 6})
f = Fake(status={D17: [questrun.DOING, questrun.DONE]}, quest=[(0, [])])
quiet(questrun.run, [2017], tools=f, after='none', use_dragon=False)
check('--no-dragon：dragon_used 0、累計 6', questrun.LAST['dragon_used'] == 0 and questrun.LAST['dragon_used_total'] == 6, str(questrun.LAST))
log = questrun.QUEST_LOG.read_text(encoding='utf-8')
check('quest-log 摘要寫本任務 0 顆（不是累計 6）', '本任務吃 0 顆' in log and '累計吃 6' not in log, log[-200:])
reset()
questrun.save_progress({'tasks': {}, 'dragon_used': 6})
f = Fake(status={D17: [questrun.DOING, questrun.DONE]}, quest=[(0, [])], active=False)
quiet(questrun.run, [2017], tools=f, after='none')
check('吃 1 顆：dragon_used 1、累計 7', questrun.LAST['dragon_used'] == 1 and questrun.LAST['dragon_used_total'] == 7, str(questrun.LAST))
check('quest-log 摘要寫本任務 1 顆', '本任務吃 1 顆' in questrun.QUEST_LOG.read_text(encoding='utf-8'))

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
f = Fake(status={D99: [questrun.DOING, questrun.DOING, questrun.DONE]}, steps=[None, 2], quest=[(3, [])] * 8)
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

# ---- 追蹤欄只有 1 張別的任務 → 沒有捲動空間：不捲、旗標立起（龍的巢穴完成判斷太慢 2026-10-11）----
_sv2 = (quest.gui, quest.ensure_task_tab, quest._tm_has, quest._find_on_page, quest.scroll_list, quest.list_signature, quest.event, quest.log, quest.read_list_titles)
scrolls.clear()
quest.gui = lambda *a, **k: ''
quest.ensure_task_tab = lambda: None
quest._tm_has = lambda w: False
quest.list_signature = lambda: 'sig'
quest.event = lambda *a, **k: None
quest.log = lambda *a, **k: None
quest.scroll_list = lambda *a, **k: (scrolls.append(a), (True, 'sig2'))[1]
def _fp(want, mode):
    quest._PAGE_ROWS_N = 1
    quest._PAGE_ROWS = [{'y': 310, 'texts': ['漆黑洞窟(二轉)']}]
    return None
quest._find_on_page = _fp
check('無捲動空間（1 張別的卡）→ False、0 次捲動、旗標 True', quest.track_task('龍的巢穴') is False and not scrolls and quest.LAST_SCAN_NO_SCROLL is True)
def _fp2(want, mode):
    quest._PAGE_ROWS_N = 2
    quest._PAGE_ROWS = [{'y': 310, 'texts': ['漆黑洞窟(二轉)']}, {'y': 425, 'texts': ['龍的巢穴X']}]
    return None
quest._find_on_page = _fp2
check('2 張卡沒目標 → 照舊捲動掃，旗標 False', quest.track_task('龍的巢穴') is False and scrolls and quest.LAST_SCAN_NO_SCROLL is False)
(quest.gui, quest.ensure_task_tab, quest._tm_has, quest._find_on_page, quest.scroll_list, quest.list_signature, quest.event, quest.log, quest.read_list_titles) = _sv2

# ================= 追蹤列表冗餘捲動修正（2026-10-12 解救老爺爺：111 秒裡約 48 秒在捲列表）=================
import json as _json  # noqa: E402
check('is_noise_title：虛線讀成「一乛乛」/ 單字 / 空 → 雜訊', quest.is_noise_title('一乛乛') and quest.is_noise_title('一') and quest.is_noise_title('') and quest.is_noise_title('—— ·'))
check('is_noise_title：真標題（含 OCR 讀壞的括號）不是雜訊', not any(quest.is_noise_title(t) for t in ('解救老爺爺', '漆黑洞窟(;轉)', '漆黑洞窟(一轉)', '龍的巢穴', '伐木證書')))
_sv3 = (quest.ps_json,)
quest.ps_json = lambda *a, **k: {'lines': [{'y': 310, 'text': '漆黑洞窟(二轉)'}, {'y': 338, 'text': '一乛乛'}, {'y': 312, 'text': '漆黑洞窟(二轉)'}]}
_rows = quest.read_list_titles()
check('read_list_titles：濾掉「一乛乛」雜訊列 → 只剩 1 張卡（無捲動空間規則才會觸發）', len(_rows) == 1 and _rows[0]['y'] == 310, str(_rows))
(quest.ps_json,) = _sv3
_fx = _json.loads((HERE / 'fixtures' / 'questlist_px.json').read_text(encoding='utf-8'))
for _name, _img in _fx['images'].items():
    _cols = [tuple(_img['px'][f'{x},{y}']) for x, y in _fx['points']]
    _got = quest.classify_arrows(_cols)
    check(f'classify_arrows 真實截圖 {_name} → {_img["expect"]}', _got == _img['expect'], str(_got))
check('classify_arrows：點數不夠 → None', quest.classify_arrows([]) is None and quest.classify_arrows(None) is None)


class FakeList:
    """假追蹤列表：cards = 由上到下的任務名；pos = 捲動位置（0 = 頂）；每頁標題 y 依 pages[pos]（任務名 → y）；
    arrows[pos] = {'up','down'} 或 None（讀不到）；tpl = 樣板是否命中（模擬剛點完 / 剛領獎時樣板暫時比不中）"""

    def __init__(self, pages, arrows, pos=0, tpl=True, has_tpl=True):
        self.pages, self.arrows, self.pos, self.tpl, self.has_tpl = pages, arrows, pos, tpl, has_tpl
        self.drags, self.clicks, self.ocr = [], [], 0

    def gui(self, *a, **k):
        cmd = ' '.join(str(x) for x in a)
        if cmd.startswith('seq') and 'click 1215 18' in cmd:
            return ''                                  # PRIMER（點遠方空地喚醒畫面）不算點卡片
        if 'drag 200 420 200 300' in cmd:
            self.drags.append('down')
            self.pos = min(self.pos + 1, len(self.pages) - 1)
        elif 'drag 200 300 200 420' in cmd:
            self.drags.append('up')
            self.pos = max(self.pos - 1, 0)
        elif 'click' in cmd:
            self.clicks.append(cmd.split('click ')[1].split(';')[0].strip())
        return ''

    def titles(self):
        self.ocr += 1
        return [{'y': y, 'texts': [n]} for n, y in sorted(self.pages[self.pos].items(), key=lambda kv: kv[1])]

    def tm_find(self, want):
        return self.pages[self.pos].get(want) if self.tpl else None


def run_track(fl, want, click=True):
    sv = (quest.gui, quest.ensure_task_tab, quest._tm_has, quest._tm_find, quest._tm_learn, quest.read_list_titles, quest.list_signature,
          quest.list_arrows, quest.read_screen, quest.event, quest.log)
    quest.gui, quest.ensure_task_tab = fl.gui, (lambda: None)
    quest._tm_has, quest._tm_find, quest._tm_learn = (lambda w: fl.has_tpl), fl.tm_find, (lambda w, y: None)
    quest.read_list_titles, quest.list_signature = fl.titles, (lambda: str(fl.pos))
    quest.list_arrows = lambda: fl.arrows[fl.pos]
    quest.read_screen = lambda: {'state': 'idle'}
    quest.event = quest.log = lambda *a, **k: None
    try:
        return quest.track_task(want, click=click)
    finally:
        (quest.gui, quest.ensure_task_tab, quest._tm_has, quest._tm_find, quest._tm_learn, quest.read_list_titles, quest.list_signature,
         quest.list_arrows, quest.read_screen, quest.event, quest.log) = sv


# 2026-10-12 實況：漆黑洞窟(二轉) + 解救老爺爺 兩張卡；頂端時解救老爺爺標題 y=425（下半截被裁、正下方 ▼），往下捲一格後 y=366
P2023 = [{'漆黑洞窟(二轉)': 310, '解救老爺爺': 425}, {'解救老爺爺': 366}]
A2023 = [{'up': False, 'down': True}, {'up': True, 'down': False}]
fl = FakeList(P2023, A2023, pos=0, has_tpl=False)
r = run_track(fl, '解救老爺爺')
check('下緣被裁的卡（y=425）→ 先往下捲一格再點整張卡 205,382；不點 205,441（▼ 上緣）', r is True and fl.drags == ['down'] and fl.clicks == ['205 382'], f'{fl.drags} {fl.clicks}')
fl = FakeList(P2023, A2023, pos=1, tpl=False)
r = run_track(fl, '解救老爺爺')
check('有樣板但這頁暫時比不中 → 同一頁直接 OCR 找到、0 次拖曳（舊版先拖 4 下 12～14 秒）', r is True and fl.drags == [] and fl.clicks == ['205 382'] and fl.ocr == 1 and quest._HIT_MODE == 'ocr', f'{fl.drags} {fl.clicks} ocr={fl.ocr}')
fl = FakeList(P2023, A2023, pos=1, tpl=True)
r = run_track(fl, '解救老爺爺')
check('樣板命中 → 不 OCR、不拖', r is True and fl.drags == [] and fl.ocr == 0 and quest._HIT_MODE == 'tpl')
fl = FakeList(P2023, A2023, pos=1, has_tpl=False)
r = run_track(fl, '漆黑洞窟(二轉)')
check('捲到底時只看得到 1 列（y=366，上一張標題捲出框外）→ 不可判「沒有捲動空間」，要往上捲找到', r is True and fl.drags == ['up'] and fl.clicks == ['205 326'], f'{fl.drags} {fl.clicks}')
fl = FakeList([{'漆黑洞窟(二轉)': 310}], [{'up': True, 'down': False}], pos=0, tpl=False)
r = run_track(fl, '解救老爺爺', click=False)
check('完成判斷：只剩 1 張別的卡（▲ 殘留）→ 一輪判不在、0 次拖曳、LAST_SCAN_NO_SCROLL（舊版 8 下 21 秒）', r is False and fl.drags == [] and quest.LAST_SCAN_NO_SCROLL is True, f'{fl.drags}')
P3 = [{'A任務': 310, 'B任務': 425}, {'B任務': 366, 'C任務': 425}, {'C任務': 366}]
A3 = [{'up': False, 'down': True}, {'up': True, 'down': True}, {'up': True, 'down': False}]
fl = FakeList(P3, A3, pos=0, has_tpl=False)
r = run_track(fl, '不存在的任務', click=False)
check('3 張卡、在頂端、目標不在：沒有 ▲ 不往上拖；往下拖到 ▼ 消失就停（不多拖一下確認）→ 2 下', r is False and fl.drags == ['down', 'down'], str(fl.drags))
fl = FakeList(P3, A3, pos=2, has_tpl=False)
r = run_track(fl, 'A任務')
check('在底端找最上面那張：往上拖到找到為止、點它', r is True and fl.drags == ['up', 'up'] and fl.clicks == ['205 326'], f'{fl.drags} {fl.clicks}')
fl = FakeList(P3, [None, None, None], pos=0, has_tpl=False)
r = run_track(fl, '不存在的任務', click=False)
check('箭頭讀不到 → 照舊拖到像素不變（上 1 下沒動、下 3 下最後一下沒動）', r is False and fl.drags == ['up', 'down', 'down', 'down'], str(fl.drags))
fl = FakeList([{'A任務': 310, 'B任務': 425}, {'B任務': 366}], [{'up': False, 'down': False}] * 2, pos=0, has_tpl=False)
r = run_track(fl, '不存在的任務', click=False)
check('箭頭說「都捲不動」但有 2 張卡（矛盾）→ 不信箭頭，照舊拖到盡頭', r is False and 'down' in fl.drags, str(fl.drags))
fl = FakeList([{'解救老爺爺': 425}], [{'up': False, 'down': True}], pos=0, has_tpl=False)
fl.pages = [{'解救老爺爺': 425, 'X任務': 310}]
r = run_track(fl, '解救老爺爺')
check('下緣的卡捲不動 → 點標題本身 205,425（避開 ▼）', r is True and fl.clicks == ['205 425'], f'{fl.drags} {fl.clicks}')

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


# ================= 走路不計時 / 時間到不開詳情（2026-10-11 馬祖快遞冗餘修正）=================
check('walk_secs：解析「走路不計時 N 秒」（取最後一行）、沒有 = 0', questrun.walk_secs(['x', '走路不計時 123 秒']) == 123 and questrun.walk_secs(['x']) == 0 and questrun.walk_secs(None) == 0)
check('time_up：事件行含「時間到」', questrun.time_up(['12:00 [..] 時間到，結束（對話 1）']) and not questrun.time_up(['步驟結束']))
f = Fake(status={D17: [questrun.DOING, questrun.DONE]}, quest=[(0, ['時間到，結束（對話 0、獎勵 0、戰鬥 0；巡路中不計時 280 秒）', '走路不計時 280 秒']), (0, ['任務完成：彌生和日美子'])])
rc = go(f, [2017])
check('slice「時間到」→ 不開詳情，直接下一片（只有開頭 accept 那一次讀詳情）', rc == 0 and f.names().count('quest') == 2 and f.names().count('status') == 0 and f.names().count('accept') == 1, str(f.names()))
f = Fake(status={D17: [questrun.DOING, questrun.DONE]}, quest=[(0, ['步驟結束（對話 1）'])])
rc = go(f, [2017])
check('不是時間到、也沒「任務完成」（模糊）→ 仍讀一次詳情確認', rc == 0 and f.names().count('status') == 1, str(f.names()))
check('quest 子程序逾時 = slice + WALK_CAP_S + 120（巡路不計時，不能被 slice+120 砍）', f.timeouts and f.timeouts[0] == questrun.SLICE_S + questrun.WALK_CAP_S + 120, str(getattr(f, 'timeouts', None)))
# 巡路時間不計入 --max-min：假時鐘，每次 quest 過 40 秒，max_min=1（60 秒）
import types as _ty  # noqa: E402
import time as _t  # noqa: E402
_clk = {'t': 1000.0}
_real_time = questrun.time
questrun.time = _ty.SimpleNamespace(time=lambda: _clk['t'], sleep=lambda s: None, strftime=_t.strftime, localtime=_t.localtime)


class ClockFake(Fake):
    def quest(self, args, timeout=0):
        _clk['t'] += 40
        return super().quest(args, timeout)


tail_walk = ['時間到，結束', '走路不計時 40 秒']
f = ClockFake(status={D17: [questrun.DOING, questrun.DONE]}, quest=[(0, tail_walk)] * 3 + [(0, ['任務完成：x'])])
rc = go(f, [2017], max_min=1)
check('巡路 40 秒 / 片不計入 --max-min 1：4 片（160 秒）仍不超時', rc == 0 and f.names().count('quest') == 4, f'rc={rc}')
_clk['t'] = 1000.0
f = ClockFake(status={D17: [questrun.DOING, questrun.DONE]}, quest=[(0, ['時間到，結束'])] * 4 + [(0, ['任務完成：x'])])
rc = go(f, [2017], max_min=1)
check('沒有巡路時間（對照）：每片 40 秒 → 第 3 片起超過 1 分鐘 → 113', rc == questrun.EXIT_SLICES, f'rc={rc}')
questrun.time = _real_time

print(f'\n{"全部通過" if not fails else f"失敗 {fails} 項"}')
sys.exit(1 if fails else 0)
