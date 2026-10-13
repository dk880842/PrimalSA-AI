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

    def clear_screen(self):
        """假 quest.clear_leftovers：對話框 / 面板殘留 → 記 esc / close 後回主畫面；unknown 不碰"""
        self.rec('clear')
        if self.screen in ('dialog', 'bye'):
            self.rec('esc')
            self.screen = 'idle'
        elif self.screen == 'panel':
            self.rec('close_panel')
            self.screen = 'idle'
        return self.screen

    purge_rc = 0
    mail_q = None                                         # 每次 mail_claim 取一個 rc（最後一個重複）；None = 0
    glow_q = None                                         # 每次 mail_glow 取一個 bool（最後一個重複）；None = False

    def bag_purge(self, roles):
        self.rec('purge', tuple(roles))
        if not self.purge_rc:
            for r in roles:                               # 刪了 1 格
                self.bag[r] = (self.bag.get(r) or 0) + getattr(self, 'purge_frees', 1)
        return self.purge_rc, {r: {'deleted': ['薩頓家的秘藥']} for r in roles}

    def mail_claim(self):
        self.rec('mail_claim')
        q = self.mail_q
        return (q.pop(0) if len(q) > 1 else q[0]) if q else 0

    def mail_glow(self):
        q = self.glow_q
        return (q.pop(0) if len(q) > 1 else q[0]) if q else False

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

    def team_regroup(self):
        self.rec('team_regroup')
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
        self.rec('bag_free')
        return 0, dict(self.bag)

    def team_scan(self, roles, free=True, hp=True):
        """假 bag.team_scan：同一次讀空格（self.bag）+ HP（取 team_hp 序列一個）"""
        self.rec('team_scan')
        out = {r: {} for r in roles}
        if hp:
            rc, pct = self.team_hp()
            if rc:
                return rc, {}
            for r in roles:
                out[r]['hp'] = (pct or {}).get(r)
        if free:
            for r in roles:
                out[r]['free'] = self.bag.get(r)
        return 0, out

    def dragon_active(self):
        return self.active

    dragon_step = 'done'
    store_rc = 0

    def dragon(self, have=False):
        self.rec('dragon', have)
        return (self.dragon_rc, {'warn': '已取出', 'step': 'use'} if self.dragon_rc else {'step': self.dragon_step})

    def dragon_store(self):
        self.rec('dragon_store')
        return self.store_rc

    def quest(self, args, timeout=0):
        self.rec('quest', tuple(str(a) for a in args))
        self.timeouts = getattr(self, 'timeouts', []) + [timeout]
        # 2026-10-14：questrun 不再開詳情判完成；quest.py 回 0 沒有「任務完成」= 下一片。
        # 舊測試腳本的 (0, []) 當「這片做完」：最後一個腳本片 / 腳本用完 → 印「任務完成」（模擬追蹤欄找不到任務）
        rc, tail = self.quest_q.pop(0) if self.quest_q else (0, [])
        if rc == 0 and not tail and not self.quest_q:
            tail = ['任務完成：假']
        return rc, tail

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

    reward_rr = 'closed'

    def reward_retry(self):
        self.rec('reward_retry')
        return self.reward_rr

    vs_stuck_val = False
    relogin_rc = 0

    def vs_stuck(self):
        self.rec('vs_stuck')
        return self.vs_stuck_val

    def relogin(self):
        self.rec('relogin')
        return self.relogin_rc

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

    def boss_retry(self, track, who=None, **kw):
        self.rec(*(('boss_retry', track) if who is None else ('boss_retry', track, tuple(who))))
        self.boss_kw = getattr(self, 'boss_kw', []) + [kw]
        return self.boss_q.pop(0) if len(self.boss_q) > 1 else self.boss_q[0]

    # 戰鬥設定檢查：battle_q 每次取一個 (rc, sts, msg, info)，最後一個重複；沒給 = 全對
    def battle_check(self):
        self.rec('battle_check')
        q = getattr(self, 'battle_q', None)
        if not q:
            return 0, {r: {'自動戰鬥': True} for r in questrun.ALL_ROLES}, '', {'changed': {}, 'role': None, 'secs': {}}
        return q.pop(0) if len(q) > 1 else q[0]

    rest_rc = 0
    disband_rc = 0

    def pet_rest_all(self):
        self.rec('rest_all')
        return self.rest_rc

    def team_disband(self):
        self.rec('disband')
        return self.disband_rc

    def pet_turnin(self, kind, roles, steps):
        self.rec('pet_turnin', kind, tuple(roles), tuple(steps))
        q = getattr(self, 'turnin_q', None)
        r = (q.pop(0) if len(q) > 1 else q[0]) if q else (0, {x: {'step1': True, 'step2': True} for x in roles})
        return r

    def pet_drop(self, name, max_level):
        self.rec('pet_drop', name, max_level)
        q = getattr(self, 'drop_q', None)
        return (q.pop(0) if len(q) > 1 else q[0]) if q else (0, {'dropped': [[x, 3] for x in questrun.ALL_ROLES]})

    def status_all(self, details, roles):
        """all_q：每次取一個 {角色: 狀態 | None(讀不到)} 或 {角色: {標題: 狀態}}（最後一個重複）；沒給 = 全員已完成"""
        details = tuple(details)
        self.rec('status_all', details, tuple(roles))
        q = getattr(self, 'all_q', None)
        if not q:
            return 0, {r: {x: '已完成' for x in details} for r in roles}
        m = q.pop(0) if len(q) > 1 else q[0]
        res = {}
        for r in roles:
            v = m.get(r, '已完成')
            res[r] = None if v is None else ({x: v.get(x, '已完成') for x in details} if isinstance(v, dict) else {x: v for x in details})
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
check('quest 指令帶追蹤標題（不含 1.82）、--max-seconds；接取後剛組過隊 → --team-fresh；片內 HP 檢查門檻 = --team-hp-min', ('quest', ('--task', '彌生和日美子', '--max-seconds', '60', '--team-fresh')) in f.calls, str(f.calls))
f = Fake(status={D17: [questrun.PENDING, questrun.DONE]}, quest=[(0, [])])
go(f, [2017], team_hp_min=60)
check('--team-hp-min 60（舊行為）→ quest.py 帶 --hp-check-min 60 --hp-check-every 3', ('quest', ('--task', '彌生和日美子', '--max-seconds', '60', '--team-fresh', '--hp-check-min', '60', '--hp-check-every', '3')) in f.calls, str(f.calls))
check('交接不再另讀當前角色（team.form 同一次面板確認）', 'current' not in n and 'char_ensure' not in n)
check('預設不吃龍王的守護（2026-10-12 起要 --dragon）', 'dragon' not in n, str(n))
check('交接：關遇敵 → 戰鬥設定檢查 → team.form（battle_check 只 1 次）', n.count('battle_check') == 1 and n.index('enc_off') < n.index('battle_check') < n.index('team_form'), str(n))
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
check('完成後逐人驗：其他 4 人都已完成 → 0、只讀 1 次、沒 bossretry', go(f, [2017]) == 0 and f.calls.count(('status_all', (D17,), others)) == 1
      and 'boss_retry' not in f.names(), str([c for c in f.calls if c[0] == 'status_all']))
f = Fake(status={D17: [questrun.DOING]}, quest=[DONE_TAIL], boss=[(0, {})])
f.all_q = [{'DKBO3': questrun.DOING, 'DKBO5': questrun.DOING}, {}]
rc = go(f, [2017])
check('有人進行中 → bossretry --who 落後者 → 只重讀那兩人 → 0', rc == 0 and ('boss_retry', questdefs.get(2017)['track'], ('DKBO3', 'DKBO5')) in f.calls
      and ('status_all', (D17,), ('DKBO3', 'DKBO5')) in f.calls and 'grind_start' in f.names(), str(f.calls[-6:]))
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

# 8-pp) 2019 卡坦步 2 需先抓雞：追蹤沒反應 → 不刷新，直接 155 + 指令；步號讀不到 → 照舊刷新後 112
D19 = questdefs.get(2019)['detail']
f = Fake(status={D19: [questrun.DOING]}, steps=[2] * 6, quest=[(3, [])] * 8)
rc = go(f, [2019])
check('2019 步 2 追蹤沒反應 → 155、不 unfreeze', rc == questrun.EXIT_NEEDPETS and 'unfreeze' not in f.names(), str(f.names()))
check('155 訊息帶 pet_catch 指令與火雞系', 'pet_catch.py' in questrun.LAST['info'].get('msg', '') and '火雞系' in questrun.LAST['info'].get('msg', ''), questrun.LAST['info'].get('msg'))
f = Fake(status={D19: [questrun.DOING]}, steps=[], quest=[(3, [])] * 8)
rc = go(f, [2019])
check('2019 步號讀不到 → 照舊 112（刷新重試）', rc == questrun.EXIT_STEP and f.names().count('unfreeze') >= 1, str(f.names()))

# 8a) quest.py 18 領獎窗關不掉：重試成功續跑 / 仍失敗 152 / 畫面已不是 reward 不點（Fake.reward_rr）
f = Fake(status={D17: [questrun.DOING, questrun.DONE]}, quest=[(18, []), (0, [])])
rc = go(f, [2017])
check('18 → 重試關窗成功 → 續跑下一片', rc == 0 and f.names().count('reward_retry') == 1 and f.names().count('quest') == 2, str(f.names()))
f = Fake(status={D17: [questrun.DOING]}, quest=[(18, [])] * 3)
f.reward_rr = 'stuck'
rc = go(f, [2017])
check('18 → 重試仍失敗 → 152、不續跑、不恢復掛機', rc == questrun.EXIT_REWARD == 152 and f.names().count('quest') == 1 and 'grind_start' not in f.names() and 'snap' in f.names(), f'{rc} {f.names()}')
f = Fake(status={D17: [questrun.DOING, questrun.DONE]}, quest=[(18, []), (0, [])])
f.reward_rr = 'not_reward'
rc = go(f, [2017])
check('18 → 畫面已不是 reward（不點）→ 當已關、續跑', rc == 0 and f.names().count('reward_retry') == 1 and f.names().count('quest') == 2, str(f.names()))
f = Fake(status={D17: [questrun.DOING]}, quest=[(18, [])] * 10)
rc = go(f, [2017])
check('18 反覆（每次重試都「成功」）→ 超過 REWARD_RETRY_MAX 次 152，不無限迴圈', rc == 152 and f.names().count('reward_retry') == questrun.REWARD_RETRY_MAX, f'{rc} {f.names().count("reward_retry")}')

# 8b) VS 牌卡死：刷新 2 次無效 → 全員重登 → 續跑；重登失敗 → 112；沒卡 VS 不重登
f = Fake(status={D17: [questrun.DOING, questrun.DONE]}, quest=[(3, [])] * 3 + [(0, [])])
f.vs_stuck_val = True
rc = go(f, [2017])
check('3 連續 + VS 卡死 → relogin 一次後續跑', rc == 0 and f.names().count('relogin') == 1 and f.names().count('unfreeze') == 2, str(f.names()))
f = Fake(status={D17: [questrun.DOING]}, quest=[(3, [])] * 8)
f.vs_stuck_val = True
f.relogin_rc = 103
check('VS 卡死但重登失敗（103）→ 112', go(f, [2017]) == questrun.EXIT_STEP and f.names().count('relogin') == 1)
f = Fake(status={D17: [questrun.DOING, questrun.DONE]}, quest=[(3, [])] * 3 + [(0, ['任務完成：x'])])
f.vs_stuck_val = True
f.relogin_rc = 105
rc = go(f, [2017])
n = f.names()
check('重登進遊戲但隊伍不對（105）→ team.form --regroup → 關遇敵 → 續跑', rc == 0 and n.index('relogin') < n.index('team_regroup') < len(n) - 1 - n[::-1].index('quest')
      and n.count('enc_off') == 2, str(n))
f = Fake(status={D17: [questrun.DOING]}, quest=[(3, [])] * 8)
check('沒 VS 卡死 → 不重登', go(f, [2017]) == questrun.EXIT_STEP and 'relogin' not in f.names())

# 9) 5：詳情已完成 → 成功；仍進行中 → 112
f = Fake(status={D17: [questrun.DOING, questrun.DONE]}, quest=[(5, [])])
check('5 且詳情已完成 → 成功', go(f, [2017]) == 0)
f = Fake(status={D17: [questrun.DOING, questrun.DOING]}, quest=[(5, [])])
check('5 → 追蹤欄找不到 = 完成（2026-10-14 不開詳情）', go(f, [2017]) == 0 and 'status' not in f.names(), str(f.names()))

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
f.purge_frees = 0                                                  # 白名單沒東西可刪
check('背包空位不足、白名單刪不出空位 → 110', go(f, [2999]) == questrun.EXIT_PREFLIGHT and 'quest' not in f.names() and ('purge', ('DKBO2',)) in f.calls, str(f.calls))
f = Fake(status={D99: [questrun.DOING, questrun.DONE]}, bag={'DKBO': 5, 'DKBO2': 0, 'DKBO3': 5, 'DKBO4': 5, 'DKBO5': 5})
rc = go(f, [2999])
check('背包空位不足 → 只對不足的人 purge 白名單 → 夠了就續跑（2026-10-13 頭盔進信箱）', rc == 0 and ('purge', ('DKBO2',)) in f.calls and 'quest' in f.names(), f'rc={rc} {f.calls}')
f = Fake(status={D99: [questrun.DOING]}, bag={'DKBO': 5, 'DKBO2': 0, 'DKBO3': 5, 'DKBO4': 5, 'DKBO5': 5})
f.purge_rc = 96
check('purge 失敗（提示窗清單核對不過 96）→ 110、不跑', go(f, [2999]) == questrun.EXIT_PREFLIGHT and 'quest' not in f.names())
f = Fake(status={D17: [questrun.DOING, questrun.DONE]}, quest=[(0, [])], hp=30)
go(f, [2017], team_hp_min=60)
check('HP 30% < 50% → 補血後重組隊', 'heal' in f.names() and f.names().index('heal') < f.names().index('quest'))
# 13b) 全隊 HP（2026-10-12 四寶玉之謎：只看隊長 → 隊員約 50% 連打 BOSS 被打死踢隊 4 次 38）
f = Fake(status={D17: [questrun.DOING, questrun.DONE]}, quest=[(0, [])], team_hp=[(0, {'DKBO': 90, 'DKBO2': 95, 'DKBO3': 45, 'DKBO4': 100, 'DKBO5': None})])
go(f, [2017], team_hp_min=60)
n = f.names()
check('任務前隊員 DKBO3 45% < 60% → 補血（整隊）→ team.form → 才跑 quest', 'heal' in n and n.index('heal') < n.index('quest') and 'team_form' in n[n.index('heal'):n.index('quest')], str(n))
f = Fake(status={D17: [questrun.DOING, questrun.DONE]}, quest=[(0, [])], team_hp=[(0, {'DKBO': 90, 'DKBO2': 95, 'DKBO3': 80, 'DKBO4': 100, 'DKBO5': None})])
go(f, [2017], team_hp_min=60)
check('全隊 ≥ 60%（有人讀不出）→ 不補血', 'heal' not in f.names() and f.team_hp_n == 1)
f = Fake(status={D17: [questrun.DOING, questrun.DONE]}, quest=[(37, []), (0, ['任務完成：x'])],
         team_hp=[(0, {r: 100 for r in questrun.ALL_ROLES}), (0, {'DKBO': 70, 'DKBO2': 70, 'DKBO3': 70, 'DKBO4': 70, 'DKBO5': 30})])
rc = go(f, [2017], team_hp_min=60)
n = f.names()
qs = [i for i, c in enumerate(n) if c == 'quest']
check('BOSS 戰後（37）DKBO5 30% → 下一片前補血 + 組隊', rc == 0 and f.team_hp_n == 2 and len(qs) == 2 and 'heal' in n and qs[0] < n.index('heal') < qs[1]
      and 'team_form' in n[n.index('heal'):qs[1]], str(n))
# 隊伍散了（30）：先讀全隊 HP → 偏低先補血 → team.form --regroup（2026-10-13 四寶玉之謎 DKBO3 / DKBO5 戰後掉隊）
f = Fake(status={D17: [questrun.DOING, questrun.DONE]}, quest=[(30, []), (0, ['任務完成：x'])],
         team_hp=[(0, {r: 100 for r in questrun.ALL_ROLES}), (0, {'DKBO': 80, 'DKBO2': 80, 'DKBO3': 0, 'DKBO4': 80, 'DKBO5': 0})])
rc = go(f, [2017], team_hp_min=60)
n = f.names()
qs = [i for i, c in enumerate(n) if c == 'quest']
check('30 隊伍散了、掉隊者 HP 0 → 補血後 team.form --regroup 再跑', rc == 0 and f.team_hp_n == 2 and 'heal' in n and 'team_regroup' in n
      and qs[0] < n.index('heal') < n.index('team_regroup') < qs[1], str(n))
f = Fake(status={D17: [questrun.DOING, questrun.DONE]}, quest=[(30, []), (0, ['任務完成：x'])],
         team_hp=[(0, {r: 100 for r in questrun.ALL_ROLES}), (0, {r: 90 for r in questrun.ALL_ROLES})])
rc = go(f, [2017], team_hp_min=60)
n = f.names()
check('30 隊伍散了、HP 都夠 → 不補血、直接 --regroup', rc == 0 and 'heal' not in n and 'team_regroup' in n, str(n))
f = Fake(status={D17: [questrun.DOING, questrun.DONE]}, quest=[(0, [])], team_hp=[(90, {})])
check('全隊讀不到（bag 90）→ 不補血、照跑（只看隊長）', go(f, [2017], team_hp_min=60) == 0 and 'heal' not in f.names() and 'quest' in f.names())
f = Fake(status={D17: [questrun.DOING, questrun.DONE]}, quest=[(0, [])], team_hp=[(9, {})])
check('全隊讀 HP 時 bag 回 9（驗證視窗）→ 透傳 9、不跑 quest', go(f, [2017], team_hp_min=60) == 9 and 'quest' not in f.names())
f = Fake(status={D17: [questrun.DOING, questrun.DONE]}, quest=[(0, [])])
go(f, [2017], team_hp_min=0)
check('--team-hp-min 0 → 不讀全隊', f.team_hp_n == 0)
f = Fake(status={D17: [questrun.DOING]}, quest=[(19, [])] * 10)
rc = go(f, [2017])
check(f'quest.py 19 一直卡（解卡 / 走出口都無效）→ 全員重登 {questrun.RELOGIN_MAX} 次仍卡 → 112', rc == questrun.EXIT_STEP and f.names().count('relogin') == questrun.RELOGIN_MAX
      and f.names().count('unstick_exit') == 3, f'rc={rc} {f.names()}')
f = Fake(status={D17: [questrun.DOING, questrun.DONE]}, quest=[(19, []), (0, ['任務完成：x'])])
rc = go(f, [2017])
n = f.names()
check('quest.py 19 → 走出口沒有可走的 → 全員重登 1 次 → 續跑完成；重登後重查戰鬥設定（不沿用快取）', rc == 0 and n.count('relogin') == 1 and n.count('battle_check') == 2, f'rc={rc} {n}')
f = Fake(status={D17: [questrun.DOING]}, quest=[(19, [])] * 10)
f.relogin_rc = 9
check('重登回 9（驗證視窗）→ 透傳 9', go(f, [2017]) == 9)
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

f = Fake(status={D17: [questrun.PENDING, questrun.DONE]}, quest=[(0, [])])
go(f, [2017], use_dragon=True, dragon_all=True)
check('--dragon：龍王的守護跑第一片前吃（have=False）', ('dragon', False) in f.calls and f.names().index('dragon') < f.names().index('quest'))
f = Fake(status={D17: [questrun.DOING, questrun.DONE]}, quest=[(0, [])], active=True)
go(f, [2017], use_dragon=True, dragon_all=True)
check('人形圖示在 → 不吃', 'dragon' not in f.names())
f = Fake(status={D17: [questrun.DOING, questrun.DONE]}, quest=[(0, [])], active=None)
go(f, [2017], use_dragon=True, dragon_all=True)
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
rc = go(f, [2017], use_dragon=True, dragon_all=True)
check('龍王失敗只警告、任務照跑', rc == 0 and f.names().count('quest') == 2)
check('龍王取出後失敗 → 下次 have=True', ('dragon', True) in f.calls, str([c for c in f.calls if c[0] == 'dragon']))
f = Fake(status={D17: [questrun.DOING, questrun.DOING, questrun.DONE]}, quest=[(0, []), (0, [])], active=None)
go(f, [2017], use_dragon=True, dragon_all=True)
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
quiet(questrun.run, [2017], tools=f, after='none', use_dragon=True, dragon_all=True)
check('吃 1 顆：dragon_used 1、累計 7', questrun.LAST['dragon_used'] == 1 and questrun.LAST['dragon_used_total'] == 7, str(questrun.LAST))
check('quest-log 摘要寫本任務 1 顆', '本任務吃 1 顆' in questrun.QUEST_LOG.read_text(encoding='utf-8'))

# ================= 戰鬥設定檢查（A3，2026-10-12 四寶玉之謎 DKBO 人物首次動作沒勾）=================
f = Fake(status={D17: [questrun.DONE]})
f.battle_q = [(0, {'DKBO': {'自動戰鬥': True, '人物首次勾選': True}}, '', {'changed': {'DKBO': ['人物首次勾選']}, 'role': None})]
rc = go(f, [2017])
check('battle_check 有修正 → 照跑、事件記修正', rc == 0 and '已修正' in questrun.EVENT_LOG.read_text(encoding='utf-8'), str(rc))
f = Fake(status={D17: [questrun.DOING]})
f.battle_q = [(13, {'DKBO': {'人物首次動作': '攻擊'}}, 'DKBO 人物首次動作是「攻擊」', {'changed': {}, 'role': 'DKBO'})]
rc = go(f, [2017])
check('battle_check 值不對（ass 13）→ 109、不組隊不接任務、不恢復掛機', rc == questrun.EXIT_BATTLESET and 'team_form' not in f.names() and 'accept' not in f.names()
      and 'grind_start' not in f.names() and questrun.LAST['info'].get('battle_rc') == 13, str(f.names()))
f = Fake(status={D17: [questrun.DOING]})
f.battle_q = [(8, {}, '戰鬥中', {'changed': {}, 'role': None})]
check('battle_check 戰鬥中（ass 8）→ 109', go(f, [2017]) == questrun.EXIT_BATTLESET)
f = Fake(status={D17: [questrun.DOING]})
f.battle_q = [(9, {}, '', {'changed': {}, 'role': None})]
check('battle_check 9（驗證視窗）→ 透傳 9', go(f, [2017]) == 9)
f = Fake(status={D17: [questrun.DONE]})
f.battle_q = [(0, {'DKBO': {'自動戰鬥': True, 'first_unsure': '凰的精'}}, '', {'changed': {}, 'role': None})]
rc = go(f, [2017])
check('人物首次動作值讀不準 → 只警告、照跑', rc == 0 and any('認不出' in w for w in questrun.LAST['warnings']), str(questrun.LAST['warnings']))
f = Fake(status={D17: [questrun.DONE]})
rc = go(f, [2017], battle_check=False)
check('--no-battle-check → 不查', rc == 0 and 'battle_check' not in f.names())
# bossretry 帶 check：預設不傳（bossretry 自己查）；--no-battle-check 傳 check=False
f = Fake(status={'琉璃洞窟': [questrun.DOING, questrun.DONE]}, quest=[(38, []), (0, [])], boss=[(0, {})])
go(f, [2000])
check('預設：bossretry 不帶 check（= 重打前查）', f.boss_kw == [{}], str(getattr(f, 'boss_kw', None)))
f = Fake(status={'琉璃洞窟': [questrun.DOING, questrun.DONE]}, quest=[(38, []), (0, [])], boss=[(0, {})])
go(f, [2000], battle_check=False)
check('--no-battle-check：bossretry check=False', f.boss_kw == [{'check': False}], str(getattr(f, 'boss_kw', None)))

# ================= 龍王預設不吃（A5）/ plan 輸出 =================
buf = io.StringIO()
with contextlib.redirect_stdout(buf):
    questrun.run([2017], dry_run=True)
txt = buf.getvalue()
check('plan：預設不吃龍王、列戰鬥設定檢查', '預設不吃（要吃加 --dragon' in txt and '每片前：龍王' not in txt and 'ass.battle_check' in txt, txt[-400:])
buf = io.StringIO()
with contextlib.redirect_stdout(buf):
    questrun.run([2017], dry_run=True, use_dragon=True, dragon_all=True, battle_check=False)
txt = buf.getvalue()
check('plan --dragon --no-battle-check', '每片前：龍王' in txt and '--no-battle-check 不做' in txt)
import argparse as _ap  # noqa: E402
_seen = {}
_orig_run = questrun.run
questrun.run = lambda *a, **k: (_seen.update(a=a, k=k), 0)[1]
try:
    for argv, want in ((['plan', '2017'], False), (['plan', '2017', '--no-dragon'], False), (['plan', '2017', '--dragon'], True)):
        sys.argv = ['questrun.py'] + argv
        quiet(questrun.main)
        check(f'CLI {argv[2:] or "預設"} → use_dragon={want}', _seen['k'].get('use_dragon') is want, str(_seen))
    sys.argv = ['questrun.py', 'plan', '2017', '--dragon', '--no-dragon']
    check('CLI --dragon + --no-dragon → 1', quiet(questrun.main) == uikit.EXIT_USAGE)
    sys.argv = ['questrun.py', 'run', '2016', '--pet-turnin', '--no-battle-check', '--drop-reward', '布克布克', '--confirm-drop', '布克布克', '--dry-run']
    quiet(questrun.main)
    check('CLI 新旗標傳到 run()', _seen['k'].get('pet_turnin') is True and _seen['k'].get('battle_check') is False
          and _seen['k'].get('drop_reward') == '布克布克' and _seen['k'].get('confirm_drop') == '布克布克', str(_seen['k']))
finally:
    questrun.run = _orig_run

# ================= 交寵物（C）=================
D16, D19 = '恐龍博士(1.82)', '卡坦的願望(1.82)'
f = Fake(status={D16: [questrun.PENDING, questrun.DONE]}, steps=[1])
rc = go(f, [2016], after='none')
check('2016 預設（沒 --pet-turnin）→ 115、不交', rc == questrun.EXIT_MANUAL and 'pet_turnin' not in f.names() and 'rest_all' not in f.names(), str(f.names()))
f = Fake(status={D16: [questrun.PENDING, questrun.DONE]}, steps=[1])
rc = go(f, [2016], after='none', pet_turnin=True)
n = f.names()
check('2016 --pet-turnin：rest-all → 解散 → pet_turnin 5 人 → DKBO → 重組 → 讀詳情已完成', rc == 0
      and n.index('rest_all') < n.index('disband') < n.index('pet_turnin') < n.index('char_ensure') < len(n) - 1 - n[::-1].index('team_form')
      and ('pet_turnin', 'dino', tuple(questrun.ALL_ROLES), (1, 2)) in f.calls and ('char_ensure', 'DKBO') in f.calls, str(f.calls))
check('  交完逐人驗證（status_all）', 'status_all' in n)
f = Fake(status={D16: [questrun.DOING, questrun.DONE]}, steps=[2])
go(f, [2016], after='none', pet_turnin=True)
check('2016 步 2 → pet_turnin 只交步 2', ('pet_turnin', 'dino', tuple(questrun.ALL_ROLES), (2,)) in f.calls)
f = Fake(status={D16: [questrun.DOING]}, steps=[None])
go(f, [2016], after='none', pet_turnin=True)
check('2016 步號讀不到（全 manual → 步 0）→ 交步 1、2', ('pet_turnin', 'dino', tuple(questrun.ALL_ROLES), (1, 2)) in f.calls)
f = Fake(status={D16: [questrun.DOING]}, steps=[1, 1])
f.turnin_q = [(123, {'DKBO3': {'step1': False}})]
rc = go(f, [2016], after='none', pet_turnin=True)
check('pet_turnin 失敗 123 → 150，仍先切回 DKBO', rc == questrun.EXIT_TURNIN and ('char_ensure', 'DKBO') in f.calls and 'grind_start' not in f.names(), str(f.calls))
f = Fake(status={D16: [questrun.DOING]}, steps=[1])
f.rest_rc = 74
rc = go(f, [2016], after='none', pet_turnin=True)
check('rest-all 失敗 → 150、不解散不交', rc == questrun.EXIT_TURNIN and 'disband' not in f.names() and 'pet_turnin' not in f.names())
f = Fake(status={D16: [questrun.DOING]}, steps=[1])
f.disband_rc = 46
check('解散失敗 → 150、不交', go(f, [2016], after='none', pet_turnin=True) == questrun.EXIT_TURNIN and 'pet_turnin' not in f.names())
f = Fake(status={D16: [questrun.DOING, questrun.DOING]}, steps=[1, 1])
rc = go(f, [2016], after='none', pet_turnin=True)
check('交完詳情仍進行中、步驟還是 manual → 只試一次就 115', rc == questrun.EXIT_MANUAL and f.names().count('pet_turnin') == 1, str(f.names()))
f = Fake(status={D19: [questrun.PENDING, questrun.DONE]}, quest=[(0, [])])
go(f, [2019], after='none', pet_turnin=True)
n = f.names()
check('2019 --pet-turnin：接取後第一片前 rest-all（不解散、quest.py 隊長交）', 'rest_all' in n and n.index('accept') < n.index('rest_all') < n.index('quest') and 'disband' not in n, str(n))
f = Fake(status={D19: [questrun.PENDING, questrun.DONE]}, quest=[(0, [])])
go(f, [2019], after='none')
check('2019 預設 → 不 rest-all', 'rest_all' not in f.names())
buf = io.StringIO()
with contextlib.redirect_stdout(buf):
    questrun.run([2016, 2019], dry_run=True, pet_turnin=True)
txt = buf.getvalue()
check('plan --pet-turnin：2016 列 pet_turnin、2019 列 rest-all、獎勵寵', 'pet_turnin dino' in txt and '接取後第一片前 pet.py rest-all' in txt and '布克布克' in txt, txt[:300])

# ================= 丟獎勵寵（C）=================
f = Fake(status={D17: [questrun.DONE]})
check('--drop-reward 沒配 --confirm-drop → 1、不碰遊戲', go(f, [2017], drop_reward='左迪洛斯') == uikit.EXIT_USAGE and not f.calls)
check('--confirm-drop 名單不同 → 1', go(Fake(status={D17: [questrun.DONE]}), [2017], drop_reward='左迪洛斯,巴朵蘭恩', confirm_drop='左迪洛斯') == uikit.EXIT_USAGE)
check('--drop-reward 是騎寵 → 1', go(Fake(status={D17: [questrun.DONE]}), [2017], drop_reward='瑪斯貝卡', confirm_drop='瑪斯貝卡') == uikit.EXIT_USAGE)
check('parse_names：逗號 / 頓號 / 去重', questrun.parse_names('左迪洛斯、巴朵蘭恩, 左迪洛斯') == ['左迪洛斯', '巴朵蘭恩'])
f = Fake(status={D17: [questrun.DONE]})
rc = go(f, [2017], drop_reward='左迪洛斯,巴朵蘭恩', confirm_drop='巴朵蘭恩、左迪洛斯')
n = f.names()
check('全部成功 → 依序丟（max_level 1）→ 再恢復掛機', rc == 0 and [c for c in f.calls if c[0] == 'pet_drop'] == [('pet_drop', '左迪洛斯', 1), ('pet_drop', '巴朵蘭恩', 1)]
      and n.index('pet_drop') < n.index('grind_start'), str(f.calls))
f = Fake(status={D17: [questrun.DONE]})
f.drop_q = [(73, {})]
rc = go(f, [2017], drop_reward='左迪洛斯,巴朵蘭恩', confirm_drop='左迪洛斯,巴朵蘭恩')
check('丟失敗 73 → 151、後面的不丟、不恢復掛機', rc == questrun.EXIT_DROP and f.names().count('pet_drop') == 1 and 'grind_start' not in f.names())
f = Fake(status={D17: [questrun.DOING]}, quest=[(33, [])])
go(f, [2017], drop_reward='左迪洛斯', confirm_drop='左迪洛斯')
check('任務失敗 → 不丟', 'pet_drop' not in f.names())
buf = io.StringIO()
with contextlib.redirect_stdout(buf):
    questrun.run([3003], dry_run=True, drop_reward='左迪洛斯', confirm_drop='左迪洛斯')
check('plan 列丟獎勵寵', '[丟獎勵寵]' in buf.getvalue() and '左迪洛斯' in buf.getvalue())

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

# ================= review 1013b §1.4：追蹤卡片位置快取（樣板命中才點，對不上退回整輪掃描）=================
quest.TRACK_POS = TMP / 'track-pos.json'


class FakeListPx(FakeList):
    """FakeList + 假 pixel：y 附近（±8）有卡片 → 依標題字決定深 / 淺點（同標題同圖樣、不同標題不同）；沒卡 → 全淺色"""

    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        self.pixels = 0

    def gui(self, *a, **k):
        if a and a[0] == 'pixel':
            self.pixels += 1
            out = []
            for tok in str(a[1]).split():
                x, y = map(int, tok.split(','))
                card = next((n for n, cy in self.pages[self.pos].items() if abs(cy - y) <= 8), None)
                dark = card and (hash((card, x // 2, (y - self.pages[self.pos][card]) // 3)) % 3 == 0)
                out.append('60,40,20' if dark else '220,200,160')
            return ' '.join(out)
        return super().gui(*a, **k)


quest.TRACK_POS.unlink(missing_ok=True)
fl = FakeListPx([{'漆黑洞窟(二轉)': 310, '解救老爺爺': 366}], [{'up': False, 'down': False}], pos=0, has_tpl=False)
r = run_track(fl, '解救老爺爺')
check('位置快取：第一次照舊掃描（OCR）找到 → 點、記下 y + 標題列像素', r is True and fl.ocr == 1 and fl.clicks == ['205 382'] and quest.load_track_pos().get('解救老爺爺', {}).get('y') == 366, str(fl.clicks))
fl2 = FakeListPx([{'漆黑洞窟(二轉)': 310, '解救老爺爺': 366}], [{'up': False, 'down': False}], pos=0, has_tpl=False)
r = run_track(fl2, '解救老爺爺')
check('位置快取：第二次同一張卡在同一位置 → 不 OCR、不拖、直接點（_HIT_MODE=pos）', r is True and fl2.ocr == 0 and fl2.drags == [] and fl2.clicks == ['205 382'] and quest._HIT_MODE == 'pos', f'{fl2.clicks} ocr={fl2.ocr}')
fl3 = FakeListPx([{'漆黑洞窟(二轉)': 366, '解救老爺爺': 425}, {'解救老爺爺': 366}], [{'up': False, 'down': True}, {'up': True, 'down': False}], pos=0, has_tpl=False)
r = run_track(fl3, '解救老爺爺')
check('位置快取：上次的 y 現在是別的任務（漆黑洞窟(二轉)）→ 像素對不上、不點它 → 整輪掃描找到真的卡', r is True and fl3.ocr >= 1
      and '205 382' in fl3.clicks and fl3.drags == ['down'] and len(fl3.clicks) == 1, f'{fl3.drags} {fl3.clicks}')
fl4 = FakeListPx([{'解救老爺爺': 366}], [{'up': False, 'down': False}], pos=0, has_tpl=False)
r = run_track(fl4, '解救老爺爺', click=False)
check('位置快取：click=False（完成判斷）不走快取（0 次 pixel）', fl4.pixels == 0 and fl4.ocr >= 1, f'pixels={fl4.pixels}')
fl5 = FakeListPx([{'解救老爺爺': 366}], [{'up': False, 'down': False}], pos=0, has_tpl=False)
r = run_track(fl5, '解救老爺爺')
check('位置快取：第三次仍命中（記錄沒被別的掃描弄壞）', r is True and fl5.ocr == 0 and quest._HIT_MODE == 'pos')
a = [[60, 40, 20]] * 20 + [[220, 200, 160]] * 580
b = [list(c) for c in a]
b[5] = [220, 200, 160]
check('track_sig_match：完全相同 → 吻合；差 1 點（一個筆畫）→ 不吻合；沒字（全淺）→ 不吻合',
      quest.track_sig_match(a, [list(c) for c in a]) and not quest.track_sig_match(a, b) and not quest.track_sig_match([[220, 200, 160]] * 600, [[220, 200, 160]] * 600))
_e = quest.load_track_pos()
_e['解救老爺爺']['ts'] = 0
quest.TRACK_POS.write_text(__import__('json').dumps(_e), encoding='utf-8')
fl6 = FakeListPx([{'解救老爺爺': 366}], [{'up': False, 'down': False}], pos=0, has_tpl=False)
run_track(fl6, '解救老爺爺')
check('位置快取：超過 6 小時 → 不用、照舊掃描', fl6.ocr == 1)

# ================= quest.close_stray_panel：誤開的組隊 / 切換面板自動關、不算驗證視窗 =================
_so = (uikit.is_open, uikit.close_panel, quest.event, quest.log, uikit.known_panel, quest.snap)
_closed = []
uikit.known_panel = lambda: None                                   # 不讀真畫面（舊版這裡會讀遊戲像素；遊戲剛好開著面板時誤判 + 截圖）
quest.snap = lambda tag: None
uikit.is_open = lambda p: p.name == 'TEAMPANEL'
uikit.close_panel = lambda p, known_open=False: (_closed.append(p.name), True)[1]
quest.event = lambda *a, **k: None
quest.log = lambda *a, **k: None
check('close_stray_panel：組隊面板開著 → 關它並回 True', quest.close_stray_panel() is True and _closed == ['TEAMPANEL'])
uikit.is_open = lambda p: False
check('close_stray_panel：沒有已知面板 → False（照舊當不認得）', quest.close_stray_panel() is False)
uikit.is_open, uikit.close_panel, quest.event, quest.log, uikit.known_panel, quest.snap = _so


# ================= 走路不計時 / 時間到不開詳情（2026-10-11 馬祖快遞冗餘修正）=================
check('walk_secs：解析「走路不計時 N 秒」（取最後一行）、沒有 = 0', questrun.walk_secs(['x', '走路不計時 123 秒']) == 123 and questrun.walk_secs(['x']) == 0 and questrun.walk_secs(None) == 0)
check('time_up：事件行含「時間到」', questrun.time_up(['12:00 [..] 時間到，結束（對話 1）']) and not questrun.time_up(['步驟結束']))
f = Fake(status={D17: [questrun.DOING, questrun.DONE]}, quest=[(0, ['時間到，結束（對話 0、獎勵 0、戰鬥 0；巡路中不計時 280 秒）', '走路不計時 280 秒']), (0, ['任務完成：彌生和日美子'])])
rc = go(f, [2017])
check('slice「時間到」→ 不開詳情，直接下一片（只有開頭 accept 那一次讀詳情）', rc == 0 and f.names().count('quest') == 2 and f.names().count('status') == 0 and f.names().count('accept') == 1, str(f.names()))
f = Fake(status={D17: [questrun.DOING, questrun.DONE]}, quest=[(0, ['步驟結束（對話 1）'])])
rc = go(f, [2017])
check('不是時間到、也沒「任務完成」（模糊）→ 不開詳情、直接下一片（2026-10-14）', rc == 0 and f.names().count('status') == 0 and f.names().count('quest') == 2, str(f.names()))
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

# ================= 2026-10-13 二轉後重做：片內 HP / NPC 只有再見 / 背包滿進信箱 / 交接清殘留 / 巡路中不吃龍王 =================
check('classify 40 → bye、41 → hp_low', questrun.classify(40) == 'bye' and questrun.classify(41) == 'hp_low')
DONE_TAIL = ['任務完成：彌生和日美子']


class FullLater(Fake):
    """開始時背包都有空（preflight 過），第一片 quest.py 跑完 DKBO3 背包滿了（領到任務道具）"""
    def quest(self, args, timeout=0):
        r = super().quest(args, timeout)
        if self.names().count('quest') == 1:
            self.bag['DKBO3'] = 0
        return r


# quest.py 40（NPC 只有再見）+ DKBO3 背包滿 → 只對 DKBO3 purge 白名單 → 領信 → 續跑 → 完成
f = FullLater(status={D17: [questrun.DOING]}, quest=[(40, []), (0, DONE_TAIL)])
rc = go(f, [2017])
n = f.names()
check('40 + 背包滿：purge 不足的人 → mail_claim → 續跑完成（不重置任務）', rc == 0 and ('purge', ('DKBO3',)) in f.calls and n.index('quest') < n.index('purge') < n.index('mail_claim')
      and n.count('quest') == 2 and n.count('accept') == 1, f'rc={rc} {n}')
# 背包沒滿、信箱也沒有丟失信（112）→ 153 回報（不是背包問題）
f = Fake(status={D17: [questrun.DOING]}, quest=[(40, [])])
f.mail_q = [112]
rc = go(f, [2017])
check('40 + 背包有空 + 信箱沒丟失信 → 153、不恢復掛機', rc == questrun.EXIT_BYE and 'purge' not in f.names() and 'grind_start' not in f.names(), f'rc={rc}')
# 背包滿、白名單刪不出空位 → 154
f = FullLater(status={D17: [questrun.DOING]}, quest=[(40, [])])
f.purge_frees = 0
rc = go(f, [2017])
check('40 + 背包滿 + 白名單沒東西 → 154、沒開信箱', rc == questrun.EXIT_BAGMAIL and 'mail_claim' not in f.names(), f'rc={rc}')
# 領了沒消失（114）→ 154
f = FullLater(status={D17: [questrun.DOING]}, quest=[(40, [])])
f.mail_q = [114]
check('信箱領取 114 → 154', go(f, [2017]) == questrun.EXIT_BAGMAIL)
# 一直 40（領完信 NPC 還是只有再見）→ 處理 BYE_RECOVER_MAX 次後 153
f = Fake(status={D17: [questrun.DOING]}, quest=[(40, [])] * 5)
rc = go(f, [2017])
check(f'一直 40 → 處理 {questrun.BYE_RECOVER_MAX} 次後 153', rc == questrun.EXIT_BYE and f.names().count('mail_claim') == questrun.BYE_RECOVER_MAX, f'rc={rc} {f.names().count("mail_claim")}')
# 片後信封發亮 → 主動處理（不等 NPC 只剩再見）
f = FullLater(status={D17: [questrun.DOING, questrun.DOING, questrun.DONE]}, quest=[(0, ['時間到，結束']), (0, DONE_TAIL)])
f.glow_q = [True, False]
rc = go(f, [2017])
check('片後信封發亮 → purge 不足的人 + 領信 → 續跑', rc == 0 and f.names().count('mail_claim') == 1 and ('purge', ('DKBO3',)) in f.calls, f'rc={rc} {f.names()}')
# 發亮但信箱沒有丟失信（112）→ 不失敗、本次不再因發亮開信箱
f = Fake(status={D17: [questrun.DOING, questrun.DOING, questrun.DONE]}, quest=[(0, ['時間到，結束']), (0, ['時間到，結束']), (0, DONE_TAIL)])
f.glow_q = [True]
f.mail_q = [112]
rc = go(f, [2017])
check('發亮但沒有丟失信 → 不失敗、之後不再開信箱（只開 1 次）', rc == 0 and f.names().count('mail_claim') == 1, f'rc={rc} {f.names()}')
# quest.py 41（片內 HP 偏低）→ 補血 + 重組 → 續跑
f = Fake(status={D17: [questrun.DOING]}, quest=[(41, []), (0, DONE_TAIL)])
rc = go(f, [2017])
n = f.names()
check('41 片內 HP 偏低 → heal → team_form → 下一片 → 完成', rc == 0 and n.count('heal') == 1 and n.index('heal') < len(n) - 1 - n[::-1].index('team_form') < len(n) - 1 - n[::-1].index('quest'), f'rc={rc} {n}')
f = Fake(status={D17: [questrun.DOING]}, quest=[(41, [])] * 10)
rc = go(f, [2017])
check(f'一直 41 → 補血 {questrun.HP_LOW_MAX} 次後 111', rc == questrun.EXIT_HANDOVER and f.names().count('heal') == questrun.HP_LOW_MAX, f'rc={rc}')
f = Fake(status={D17: [questrun.DOING, questrun.DONE]}, quest=[(0, [])])
go(f, [2017], team_hp_min=0)
check('--team-hp-min 0 → quest.py 不帶 --hp-check-min', all('--hp-check-min' not in c[1] for c in f.calls if c[0] == 'quest'), str([c for c in f.calls if c[0] == 'quest']))
# 交接：背包面板殘留 → 先關再做戰鬥設定檢查；不認得 → 9、不開外掛面板
f = Fake(status={D17: [questrun.DOING, questrun.DONE]}, quest=[(0, [])], screen='panel')
rc = go(f, [2017])
n = f.names()
check('交接：殘留面板 → close_panel 在 battle_check 之前（2026-10-13 08:00 ass rc 3）', rc == 0 and n.index('close_panel') < n.index('battle_check'), str(n))
f = Fake(status={D17: [questrun.DOING, questrun.DONE]}, quest=[(0, [])], screen='unknown')
rc = go(f, [2017])
check('交接：清不掉的不認得畫面 → 9、不開外掛 / 不組隊', rc == uikit.EXIT_UNKNOWN_SCREEN and 'battle_check' not in f.names() and 'team_form' not in f.names(), f'rc={rc}')


class PreFake(Fake):
    """preflight 第一次 9（背包面板蓋住 HUD）、清掉殘留後 0"""
    def preflight(self):
        self.rec('preflight')
        return 9 if self.screen == 'panel' else 0


f = PreFake(status={D17: [questrun.DOING, questrun.DONE]}, quest=[(0, [])], screen='panel')
rc = go(f, [2017])
check('preflight 9 但畫面是已知面板 → 清掉後重驗 → 繼續', rc == 0 and f.names().count('preflight') == 2 and 'close_panel' in f.names(), f'rc={rc} {f.names()}')
# --dragon：遊戲還在自動巡路 → 這片不吃（08:04 depot_use 被 NPC 對話框打斷）
f = Fake(status={D17: [questrun.DOING, questrun.DONE]}, quest=[(0, [])])
f.screen = 'walking'
go(f, [2017], use_dragon=True, dragon_all=True)
check('--dragon：自動巡路中 → 不吃（下一片再看）', 'dragon' not in f.names(), str(f.names()))

# ================= 2026-10-13 冗餘 review 前 5 名 =================
D18 = '馬祖快遞(1.82)'
done_tail = ['任務完成：x']
# --- §2 逐人驗證：risk（預設）沒風險事件 → run 結束批次一次；有風險 → 當場；each = 舊行為 ---
f = Fake(status={D17: [questrun.DOING], D15: [questrun.DOING]}, quest=[(0, done_tail), (0, done_tail)])
rc = go(f, [2017, 2015])
sa = [c for c in f.calls if c[0] == 'status_all']
n = f.names()
check('risk：2 個任務都沒風險事件 → 只在全部結束後批次讀 1 次（兩個標題一起）、在恢復掛機之前', rc == 0 and sa == [('status_all', (D17, D15), others)]
      and n.index('status_all') > len(n) - 1 - n[::-1].index('quest') and n.index('status_all') < n.index('grind_start'), str(sa))
check('批次驗完 → 待驗清單清空', questrun.LAST.get('verify_pending') == [], str(questrun.LAST.get('verify_pending')))
f = Fake(status={D17: [questrun.DOING], D15: [questrun.DOING]}, quest=[(0, done_tail), (0, done_tail)])
go(f, [2017, 2015], verify='each')
check('--verify each：每任務完成當場驗（2 次）', [c[1] for c in f.calls if c[0] == 'status_all'] == [(D17,), (D15,)])
f = Fake(status={D17: [questrun.DOING], D15: [questrun.DOING]}, quest=[(30, []), (0, done_tail), (0, done_tail)])
go(f, [2017, 2015])
sa = [c[1] for c in f.calls if c[0] == 'status_all']
check('risk：2017 有 quest.py 30（隊伍散）→ 2017 當場驗；2015 沒事 → 結束批次驗', sa == [(D17,), (D15,)] and f.names().index('status_all') < f.names().index('accept', 8), str(sa))
f = Fake(status={D17: [questrun.DOING]}, quest=[(37, []), (0, done_tail)],
         team_hp=[(0, {r: 100 for r in questrun.ALL_ROLES}), (0, {'DKBO': 90, 'DKBO2': 90, 'DKBO3': 0, 'DKBO4': 90, 'DKBO5': 90})])
go(f, [2017], team_hp_min=60)
check('BOSS 戰後有人 HP 0（舊行為 team_hp_min=60）→ 補血，但不再記風險事件（2026-10-14）', 'heal' in f.names() and not any('當場逐人驗' in ln for ln in questrun.EVENT_LOG.read_text(encoding='utf-8').splitlines()))
f = Fake(status={D99: [questrun.DOING], D17: [questrun.PENDING]}, quest=[(0, done_tail), (0, done_tail)])
rc = go(f, [2999, 2017])
n = f.names()
sa = [i for i, c in enumerate(f.calls) if c[0] == 'status_all']
acc17 = f.calls.index(('accept', D17))
check('前置依賴：成人儀式待驗 → 接取彌生和日美子之前先批次驗（Task 表 finishTasks）', rc == 0 and f.calls[sa[0]][1] == (D99,) and sa[0] < acc17 and f.calls[sa[1]][1] == (D17,), str([f.calls[i] for i in sa]))
f = Fake(status={D17: [questrun.DOING], D15: [questrun.DOING]}, quest=[(0, done_tail), (33, [])])
rc = go(f, [2017, 2015])
check('中途失敗（117）→ 不批次驗、待驗 [2017] 留在進度檔', rc == questrun.EXIT_STALL and 'status_all' not in f.names() and questrun.LAST.get('verify_pending') == ['2017'], str(questrun.LAST.get('verify_pending')))
f2 = Fake(status={D15: [questrun.DOING]}, quest=[(0, done_tail)])
quiet(questrun.run, [2015], tools=f2, after='none')                 # 不 reset：沿用上一輪進度檔
check('下次 run 結束 → 上次留下的 2017 跟這次的 2015 一起批次驗', [c[1] for c in f2.calls if c[0] == 'status_all'] == [(D17, D15)], str([c for c in f2.calls if c[0] == 'status_all']))
f = Fake(status={D17: [questrun.DOING], D15: [questrun.DOING]}, quest=[(0, done_tail), (0, done_tail)], boss=[(0, {})])
f.all_q = [{'DKBO3': {D15: questrun.DOING}}, {}]
rc = go(f, [2017, 2015])
check('批次驗：DKBO3 只有 2015 沒完成 → 只對 2015 bossretry --who DKBO3 → 只重讀 DKBO3 的 2015', rc == 0 and ('boss_retry', questdefs.get(2015)['track'], ('DKBO3',)) in f.calls
      and ('status_all', (D15,), ('DKBO3',)) in f.calls, str([c for c in f.calls if c[0] in ('status_all', 'boss_retry')]))
# --- §6.1 提前結束 → 不開詳情直接下一片 ---
f = Fake(status={D17: [questrun.DOING]}, quest=[(0, ['步驟結束（對話 2、獎勵 1、戰鬥 0），連續閒置 3 次，提前結束']), (0, done_tail)])
rc = go(f, [2017])
check('quest.py「提前結束」→ 不讀詳情、直接下一片（碧青洞窟 09:31 多開一次詳情 32 秒）', rc == 0 and 'status' not in f.names() and f.names().count('quest') == 2, str(f.names()))
check('early_end / battles_in 純函式', questrun.early_end(['…提前結束']) and not questrun.early_end(['時間到']) and questrun.battles_in(['本片戰鬥 3 場']) == 3
      and questrun.battles_in(['x']) is None and questrun.battles_in(['本片戰鬥 0 場']) == 0)
# --- §5.1 戰鬥設定檢查 30 分快取 ---
reset()
questrun.save_progress({'tasks': {}, 'battle_ok_at': questrun.time.time() - 600})
f = Fake(status={D17: [questrun.DONE]})
quiet(questrun.run, [2017], tools=f, after='none')
check('戰鬥設定 10 分前查過 → 交接不再開外掛面板', 'battle_check' not in f.names(), str(f.names()))
reset()
questrun.save_progress({'tasks': {}, 'battle_ok_at': questrun.time.time() - 600})
f = Fake(status={D17: [questrun.DONE]})
quiet(questrun.run, [2017], tools=f, after='none', battle_cache=False)
check('--battle-check-always → 照查', f.names().count('battle_check') == 1)
reset()
questrun.save_progress({'tasks': {}, 'battle_ok_at': questrun.time.time() - questrun.BATTLE_OK_S - 5})
f = Fake(status={D17: [questrun.DONE]})
quiet(questrun.run, [2017], tools=f, after='none')
check('超過 30 分 → 照查', f.names().count('battle_check') == 1)
f = Fake(status={D17: [questrun.DOING, questrun.DONE]}, quest=[(38, []), (0, done_tail)], boss=[(0, {})])
go(f, [2017])
check('bossretry 後戰鬥設定快取作廢（進度檔 battle_ok_at = 0）', not questrun.load_progress().get('battle_ok_at'))
# --- §5.2 / §5.3 全隊 HP 5 分內且沒戰鬥沿用；背包空格與 HP 同一次開背包 ---
f = Fake(status={D17: [questrun.DOING], D15: [questrun.DOING]}, quest=[(0, done_tail + ['本片戰鬥 0 場']), (0, done_tail)])
go(f, [2017, 2015], team_hp_min=60)
check('第一任務沒打仗（本片戰鬥 0 場）→ 第二任務開始前全隊 HP 沿用（只讀 1 次）', f.team_hp_n == 1, str(f.team_hp_n))
check('任務開始前背包空格 + HP 用 team_scan 同一次讀；HP 沿用的那次只讀空格（bag_free）', f.names().count('team_scan') == 1 and f.names().count('bag_free') == 1
      and f.names().index('team_scan') < f.names().index('bag_free'), str(f.names()))
f = Fake(status={D17: [questrun.DOING], D15: [questrun.DOING]}, quest=[(0, done_tail + ['本片戰鬥 2 場']), (0, done_tail)])
go(f, [2017, 2015], team_hp_min=60)
check('第一任務打過仗 → 第二任務開始前重讀（2 次）', f.team_hp_n == 2, str(f.team_hp_n))
f = Fake(status={D17: [questrun.DOING], D15: [questrun.DOING]}, quest=[(0, done_tail), (0, done_tail)])
go(f, [2017, 2015], team_hp_min=60)
check('quest.py 沒印戰鬥場數（舊版）→ 當打過仗、重讀', f.team_hp_n == 2)
# --- §3 龍王：只對長巡路任務吃、整疊留背包、run 結束存回、skip 不計 ---
f = Fake(status={D17: [questrun.DOING, questrun.DONE]}, quest=[(0, done_tail)])
go(f, [2017], use_dragon=True)
check('--dragon：短巡路任務（彌生和日美子 2 秒）不吃', 'dragon' not in f.names())
f = Fake(status={D18: [questrun.DOING]}, quest=[(0, ['時間到，結束']), (0, done_tail)])
rc = go(f, [2018], use_dragon=True, after='none')
dc = [c for c in f.calls if c[0] == 'dragon']
n = f.names()
check('--dragon：長巡路（馬祖快遞）第一次 have=False 取出、第二片 have=True 直接從背包吃；結束存回 1 次', rc == 0 and dc == [('dragon', False), ('dragon', True)]
      and n.count('dragon_store') == 1 and n.index('dragon_store') > len(n) - 1 - n[::-1].index('quest'), str(n))
check('  存回後旗標清掉、LAST.dragon_in_bag False', questrun.LAST.get('dragon_in_bag') is False and not questrun.load_progress().get('dragon_in_bag'))
f = Fake(status={D18: [questrun.DOING]}, quest=[(0, done_tail)])
f.dragon_step = 'skip'
go(f, [2018], use_dragon=True, after='none')
check('depot_use 判 buff 已在（skip）→ 不計「已吃」、不留背包旗標、不存回', questrun.LAST.get('dragon_used') == 0 and 'dragon_store' not in f.names(), str(questrun.LAST.get('dragon_used')))
f = Fake(status={D18: [questrun.DOING]}, quest=[(0, ['時間到，結束']), (33, [])])
rc = go(f, [2018], use_dragon=True, after='none')
check('任務失敗（117）也存回龍王', rc == questrun.EXIT_STALL and f.names().count('dragon_store') == 1)
f = Fake(status={D18: [questrun.DOING]}, quest=[(0, ['時間到，結束']), (2, [])])
rc = go(f, [2018], use_dragon=True, after='none')
check('驗證視窗（9）→ 不碰畫面、不存；旗標留進度檔', rc == 9 and 'dragon_store' not in f.names() and questrun.load_progress().get('dragon_in_bag') is True)
f2 = Fake(status={D17: [questrun.DONE]})
quiet(questrun.run, [2017], tools=f2, after='none')                 # 沿用進度檔（dragon_in_bag True），這次不吃
n = f2.names()
check('下次 run（不吃龍王）→ 交接後先存回上次留在背包的龍王', n.count('dragon_store') == 1 and n.index('team_form') < n.index('dragon_store') < n.index('accept'), str(n))
f = Fake(status={D18: [questrun.DOING]}, quest=[(0, done_tail)])
f.store_rc = 90
go(f, [2018], use_dragon=True, after='none')
check('存回失敗 → 只警告、旗標留著（下次補存）', questrun.LAST.get('ok') and questrun.LAST.get('dragon_in_bag') is True and any('存回公共倉庫失敗' in w for w in questrun.LAST['warnings']))


class NoBagDragon(Fake):
    """進度檔說龍王在背包，但背包其實沒有（have=True → 92）"""
    def dragon(self, have=False):
        self.rec('dragon', have)
        return (92, {'step': 'use'}) if have else (0, {'step': 'done'})


reset()
questrun.save_progress({'tasks': {}, 'dragon_in_bag': True})
f = NoBagDragon(status={D18: [questrun.DOING]}, quest=[(0, done_tail)])
quiet(questrun.run, [2018], tools=f, after='none', use_dragon=True)
check('have=True 但背包沒有（92）→ 改從公共倉庫取（have=False）再吃', [c for c in f.calls if c[0] == 'dragon'] == [('dragon', True), ('dragon', False)] and questrun.LAST['dragon_used'] == 1)
f = Fake(status={D18: [questrun.DOING]}, quest=[(0, done_tail)], bag={'DKBO': 1, 'DKBO2': 5, 'DKBO3': 5, 'DKBO4': 5, 'DKBO5': 5})
go(f, [2018], use_dragon=True, after='none')
check('--dragon 且龍王還不在背包：DKBO 要 bag_slots + 1 格（馬祖快遞 1 + 1）→ 只空 1 格先 purge DKBO', ('purge', ('DKBO',)) in f.calls, str(f.calls[:12]))
f = Fake(status={D18: [questrun.DOING]}, quest=[(0, done_tail)], bag={'DKBO': 1, 'DKBO2': 5, 'DKBO3': 5, 'DKBO4': 5, 'DKBO5': 5})
go(f, [2018], after='none')
check('沒 --dragon：DKBO 1 格就夠、不 purge', 'purge' not in f.names())
# --- B6：quest.py 42 VS 牌卡死 → 全員重登；每任務最多 RELOGIN_MAX ---
f = Fake(status={D17: [questrun.DOING]}, quest=[(42, []), (0, done_tail)])
rc = go(f, [2017])
n = f.names()
check('quest.py 42（VS 牌卡死）→ 全員重登 → 關遇敵 → 戰鬥設定重查 → 續跑完成；重登 = 風險事件（當場驗）', rc == 0 and n.count('relogin') == 1
      and n.index('relogin') < n.index('enc_off', 2) < n.index('battle_check', n.index('relogin')) and n.index('status_all') < n.index('grind_start'), str(n))
f = Fake(status={D17: [questrun.DOING]}, quest=[(42, [])] * 5)
rc = go(f, [2017])
check(f'42 一直來 → 重登 {questrun.RELOGIN_MAX} 次後 112', rc == questrun.EXIT_STEP and f.names().count('relogin') == questrun.RELOGIN_MAX)
check('classify 29 → select_loop、42 → vs_stuck', questrun.classify(29) == 'select_loop' and questrun.classify(42) == 'vs_stuck')
# --- 交寵物（S5 / S6）---
f = Fake(status={D19: [questrun.DOING]}, quest=[(29, [])])
rc = go(f, [2019], after='none', pet_turnin=True)
check('卡坦的願望 quest.py 29（寵物沒湊齊按完成循環）→ 117、訊息提示寵物沒湊齊', rc == questrun.EXIT_STALL and '寵物沒湊齊' in questrun.LAST['info'].get('msg', ''), questrun.LAST['info'].get('msg'))
f = Fake(status={D16: [questrun.PENDING, questrun.DONE]}, steps=[1])
rc = go(f, [2016], after='none', pet_turnin=True)
check('恐龍博士 --pet-turnin：接取後已 rest-all → 交寵物前不重做（只 1 次）', rc == 0 and f.names().count('rest_all') == 1, str(f.names()))
f = Fake(status={D19: [questrun.DOING]}, quest=[(0, done_tail)])
f.rest_rc = 74
rc = go(f, [2019], after='none', pet_turnin=True)
check('rest-all 74（外掛鎖定戰寵）→ 150、訊息提示先取消鎖定', rc == questrun.EXIT_TURNIN and '鎖定戰寵' in questrun.LAST['info'].get('msg', ''), questrun.LAST['info'].get('msg'))
buf = io.StringIO()
with contextlib.redirect_stdout(buf):
    questrun.run([2018, 2017], dry_run=True, use_dragon=True)
txt = buf.getvalue()
check('plan --dragon：長巡路列「每片前」、短巡路列「不吃」、逐人驗證模式', '每片前：龍王' in txt.split('[任務 2017]')[0] and '龍王的守護：不吃' in txt.split('[任務 2017]')[1]
      and '--verify risk' in txt, txt[-600:])

# ================= 紅暴 2031（2026-10-13：有龍王就組隊打到底）=================
D31 = questdefs.get(2031)['detail']
STOP = ['已領 1 次獎勵視窗，停止（--stop-after-rewards）']


class Hero(Fake):
    """紅暴用：team_check / warp / team_read / store_many / bag_drop"""
    check_rc = 0
    levels = None                                          # {角色: (轉, 級)}；None = 全員 (2, 120)
    have = None                                            # {角色: bool}（耐久力回複藥）；None = 全有
    store_rc = 0
    drop_rc = 0
    no_dragon = False

    def team_check(self):
        self.rec('team_check')
        return self.check_rc

    def warp(self, dest, m, name, xy):
        self.rec('warp', tuple(dest), m, name)
        self.pos = (m, xy[0], xy[1])
        return self.pos

    def team_read(self, roles, names):
        self.rec('team_read', tuple(names))
        lv, hv = self.levels or {}, self.have or {}
        return 0, {r: {'level': lv.get(r, (2, 120)), 'have': {n: hv.get(r, True) for n in names}, 'free': 8} for r in roles}

    def store_many(self, roles, name, depot):
        self.rec('store_many', name, depot)
        return self.store_rc, {r: self.store_rc for r in roles}

    def pet_store(self, name, depot):
        self.rec('pet_store', name, depot)
        return 0

    def bag_drop(self, roles, names):
        self.rec('bag_drop', tuple(names))
        return self.drop_rc, {r: {'deleted': list(names)} for r in roles}

    def dragon(self, have=False):
        if self.no_dragon:
            self.rec('dragon', have)
            return 92, {'step': 'take', 'role': 'DKBO'}
        return super().dragon(have)


def hero(quest=None, steps=None, **kw):
    f = Hero(status={D31: [questrun.PENDING, questrun.DONE]}, quest=quest, steps=steps, bag={r: 8 for r in questrun.ALL_ROLES}, **kw)
    return f


HAPPY_Q = [(0, STOP)] * 5 + [(0, [])] + [(0, STOP)] * 2 + [(5, [])]
HAPPY_S = [1, 2, 3, 4, 5, 6, 7, 8, 'GONE']
f = hero(HAPPY_Q, HAPPY_S)
rc = go(f, [2031], after='none')
n = f.names()
qs = [c[1] for c in f.calls if c[0] == 'quest']
fight = [q for q in qs if '--fight' in q]
check('紅暴 happy path：rc 0、5 片 --stop-after-rewards 1 + 1 次 --fight --step 6 + 2 片 + 完成', rc == 0 and len(fight) == 1 and '6' in fight[0]
      and sum('--stop-after-rewards' in q for q in qs) == 8, f'rc={rc} {qs}')
check('紅暴：不加 --dragon 也吃龍王（dragon_required），且在接取前', 'dragon' in n and n.index('dragon') < n.index('accept'), str(n[:20]))
check('紅暴：前置 team_read（耐久力回複藥）在接取前', ('team_read', ('耐久力回複藥',)) in f.calls and n.index('team_read') < n.index('accept'))
check('紅暴步 6：便捷傳送龍王守衛 → --fight → team.check', ('warp', (1160, 646), 5510, '龍王守衛') in f.calls
      and n.index('warp') < n.index('team_check'), str([c for c in f.calls if c[0] in ('warp', 'team_check')]))
check('紅暴：完成後 英雄的祝福存個人、龍王的守護存公共；不另存 DKBO 那疊（dragon_store）', ('store_many', '英雄的祝福', 'personal') in f.calls
      and ('store_many', '龍王的守護', 'public') in f.calls and 'dragon_store' not in n, str([c for c in f.calls if c[0].startswith('store') or c[0] == 'dragon_store']))
check('--stop-after-rewards 收片不開詳情（完成判斷也不開）', n.count('status') == 0, str(n.count('status')))
check('步 6 BOSS 前不讀全隊 HP（2026-10-14）', f.team_hp_n == 0)

f = hero(HAPPY_Q, HAPPY_S)
f.no_dragon = True
rc = go(f, [2031], after='none')
check(f'背包 / 公共倉庫都沒有龍王 → {questrun.EXIT_NODRAGON}（改走單人逃跑）、不接取', rc == questrun.EXIT_NODRAGON and 'accept' not in f.names()
      and '單人逃跑' in questrun.LAST['info'].get('msg', ''), f'rc={rc} {questrun.LAST["info"].get("msg")}')
f = hero(HAPPY_Q, HAPPY_S, active=True)
rc = go(f, [2031], after='none')
check('龍王 buff 已在 → 不吃、照跑', rc == 0 and 'dragon' not in f.names())
f = hero(HAPPY_Q, HAPPY_S)
f.have = {'DKBO4': False}
rc = go(f, [2031], after='none')
check('有人沒有耐久力回複藥 → 110、不接取、訊息有去哪買', rc == questrun.EXIT_PREFLIGHT and 'accept' not in f.names()
      and 'DKBO4' in questrun.LAST['info'].get('msg', '') and 'psa.py item' in questrun.LAST['info'].get('msg', ''), questrun.LAST['info'].get('msg'))
f = hero(HAPPY_Q, HAPPY_S)
f.levels = {'DKBO3': (2, 79), 'DKBO5': None}
rc = go(f, [2031], after='none')
check('有人 < 80 級 / 讀不到 → 110', rc == questrun.EXIT_PREFLIGHT and 'DKBO3' in questrun.LAST['info'].get('msg', '') and 'DKBO5' in questrun.LAST['info'].get('msg', ''))
f = hero([(0, STOP)] * 5 + [(35, []), (0, [])] + [(0, STOP)] * 2 + [(5, [])], HAPPY_S)
rc = go(f, [2031], after='none')
check('步 6 輸了（35）→ 補血重組再打一次 → 贏 → 完成', rc == 0 and 'heal' in f.names() and sum('--fight' in c[1] for c in f.calls if c[0] == 'quest') == 2, f'rc={rc}')
f = hero([(0, STOP)] * 5 + [(35, []), (35, [])], HAPPY_S)
rc = go(f, [2031], after='none')
check(f'步 6 打 {questrun.FIGHT_TRIES} 次都輸 → 114', rc == questrun.EXIT_TEAM and '沒贏' in questrun.LAST['info'].get('msg', ''))
f = hero(HAPPY_Q, HAPPY_S, boss=[(0, {'msg': 'ok'})])
f.check_rc = 47
rc = go(f, [2031], after='none')
check('步 6 贏了但不滿 5 人 → bossretry 補人後續跑', rc == 0 and any(c[0] == 'boss_retry' for c in f.calls), f'rc={rc}')
f = hero(HAPPY_Q, HAPPY_S)
f.pos = (5510, 51, 17)
go(f, [2031], after='none')
check('已在龍穴門口附近 → 不再便捷傳送', 'warp' not in f.names())
f = hero(HAPPY_Q, HAPPY_S)
rc = go(f, [2031], after='none', post=False)
check('--no-post → 不存倉', rc == 0 and 'store_many' not in f.names())
f = hero(HAPPY_Q, HAPPY_S)
f.store_rc = 91
rc = go(f, [2031], after='none')
check(f'存倉失敗 → {questrun.EXIT_POST}', rc == questrun.EXIT_POST)
f = hero(HAPPY_Q, HAPPY_S)
rc = go(f, [2031], after='none', drop_items='薩姆吉爾的首飾', confirm_drop_items='薩姆吉爾的首飾', drop_reward='巴朵蘭恩', confirm_drop='巴朵蘭恩')
n = f.names()
check('--drop-items 首飾 + --drop-reward 巴朵蘭恩：全部成功後才丟（bag.purge / petdrop 1 級）', rc == 0 and ('bag_drop', ('薩姆吉爾的首飾',)) in f.calls
      and ('pet_drop', '巴朵蘭恩', 1) in f.calls and n.index('bag_drop') > n.index('store_many'), str(n[-8:]))
f = hero(HAPPY_Q, HAPPY_S)
rc = go(f, [2031], after='none', drop_items='薩姆吉爾的首飾', confirm_drop_items='')
check('--drop-items 沒配同名 --confirm-drop-items → 參數錯、不跑', rc == uikit.EXIT_USAGE and not f.calls)
f = hero(HAPPY_Q, HAPPY_S)
rc = go(f, [2031], after='none', drop_items='英雄的祝福', confirm_drop_items='英雄的祝福')
check('--drop-items 不在 questdefs drop_items（英雄的祝福）→ 參數錯', rc == uikit.EXIT_USAGE and not f.calls)
f = hero(HAPPY_Q, HAPPY_S)
f.drop_rc = 96
rc = go(f, [2031], after='none', drop_items='薩姆吉爾的首飾', confirm_drop_items='薩姆吉爾的首飾')
check('丟首飾提示窗對不上（96）→ 151', rc == questrun.EXIT_DROP)
D14, D12 = questdefs.get(2014)['detail'], questdefs.get(2012)['detail']
f = Hero(status={D14: [questrun.DOING]}, quest=[(0, ['任務完成：x'])], bag={r: 8 for r in questrun.ALL_ROLES})
rc = go(f, [2014], after='none')
check('黃金羚羊之謎完成 → post 摩娜西普 5 人存個人寵物倉庫', rc == 0 and ('pet_store', '摩娜西普', 'personal') in f.calls, str([c for c in f.calls if c[0] == 'pet_store']))
f = Hero(status={D12: [questrun.DOING]}, quest=[(0, ['任務完成：x'])], bag={r: 8 for r in questrun.ALL_ROLES})
rc = go(f, [2012], after='none')
check('五兄弟之謎完成 → post 人龍隨機蛋 5 人存公共倉庫', rc == 0 and ('store_many', '人龍隨機蛋', 'public') in f.calls)
check('early_end 認得 --stop-after-rewards 收片', questrun.early_end(STOP) and not questrun.early_end(['時間到，結束']))
buf = io.StringIO()
with contextlib.redirect_stdout(buf):
    questrun.run([2031], dry_run=True)
txt = buf.getvalue()
check('plan 2031：fight 步、前置、龍王必要、post、可丟道具都列出', all(k in txt for k in ('kind=fight', '耐久力回複藥', 'dragon_required', '英雄的祝福 5 人存個人倉庫', '薩姆吉爾的首飾')), txt[-400:])

# ================= 2026-10-13 加速 review 第 2 輪（notes/review-speedup-1013b.md）=================
# --- §2.2 --rested：petquest 練完已 rest-all → questrun 交件前不重做 ---
f = Fake(status={D19: [questrun.DOING]}, quest=[(0, done_tail)])
rc = go(f, [2019], after='none', pet_turnin=True, rested=True)
check('卡坦 --pet-turnin --rested → 接取後不 rest-all（呼叫端剛做過）', rc == 0 and 'rest_all' not in f.names(), str(f.names()))
f = Fake(status={D16: [questrun.PENDING, questrun.DONE]}, steps=[1])
rc = go(f, [2016], after='none', pet_turnin=True, rested=True)
n = f.names()
check('恐龍博士 --pet-turnin --rested → 交寵物前也不 rest-all，照樣解散 → pet_turnin', rc == 0 and 'rest_all' not in n and n.index('disband') < n.index('pet_turnin'), str(n))
f = Fake(status={D19: [questrun.DOING]}, quest=[(0, done_tail)])
go(f, [2019], after='none', rested=True)
check('--rested 沒配 --pet-turnin → 無作用（本來就不 rest-all）', 'rest_all' not in f.names())
_seen2 = {}
_orig_run2 = questrun.run
questrun.run = lambda ids, dry, after, **k: _seen2.update(k=k) or 0
try:
    sys.argv = ['questrun.py', 'run', '2019', '--pet-turnin', '--rested', '--verify', 'defer']
    quiet(questrun.main)
    check('CLI --rested / --verify defer 傳到 run()', _seen2['k'].get('rested') is True and _seen2['k'].get('verify') == 'defer', str(_seen2.get('k')))
finally:
    questrun.run = _orig_run2

# --- §2.1 --verify defer：沒風險事件 → run 結束不驗、留待驗清單；有風險照舊當場；依賴照舊先驗 ---
f = Fake(status={D17: [questrun.DOING], D15: [questrun.DOING]}, quest=[(0, done_tail), (0, done_tail)])
rc = go(f, [2017, 2015], verify='defer')
check('defer：2 個任務沒風險事件 → 不逐人驗、待驗 [2015, 2017] 留在進度檔、照樣恢復掛機', rc == 0 and 'status_all' not in f.names()
      and questrun.LAST.get('verify_pending') == ['2015', '2017'] and 'grind_start' in f.names(), str(questrun.LAST.get('verify_pending')))
f = Fake(status={D17: [questrun.DOING]}, quest=[(30, []), (0, done_tail)])
go(f, [2017], verify='defer')
check('defer：有風險事件（30 隊伍散）→ 照舊當場驗', [c[1] for c in f.calls if c[0] == 'status_all'] == [(D17,)], str(f.names()))
f = Fake(status={D99: [questrun.DOING], D17: [questrun.PENDING]}, quest=[(0, done_tail), (0, done_tail)])
rc = go(f, [2999, 2017], verify='defer')
sa = [c for c in f.calls if c[0] == 'status_all']
check('defer：依賴任務（成人儀式 → 彌生）接取前照舊先驗前置；彌生本身延後', rc == 0 and [c[1] for c in sa] == [(D99,)]
      and f.calls.index(sa[0]) < f.calls.index(('accept', D17)) and questrun.LAST.get('verify_pending') == ['2017'], str(sa))
# 待驗 12 小時內保留（defer），超過 2 小時的 risk 模式照舊丟
reset()
import json as _j2  # noqa: E402
questrun.PROGRESS.write_text(_j2.dumps({'tasks': {}, 'verify_pending': {'2017': questrun.time.time() - 5 * 3600}}), encoding='utf-8')
f = Fake(status={D15: [questrun.DOING]}, quest=[(0, done_tail)])
quiet(questrun.run, [2015], tools=f, after='none', verify='defer')
check('defer：5 小時前的待驗 2017 仍保留（DEFER_KEEP_S 12 小時）', questrun.LAST.get('verify_pending') == ['2015', '2017'], str(questrun.LAST.get('verify_pending')))
# questrun.py verify：沒給 ID = 驗待驗清單；全完成 → 不交接、清空
f = Fake()
rc = quiet(questrun.cmd_verify, [], '', tools=f)
check('verify（待驗清單）：全員已完成 → 0、不交接（不關遇敵 / 不組隊）、清單清空', rc == 0 and [c[1] for c in f.calls if c[0] == 'status_all'] == [(D17, D15)]
      and 'team_form' not in f.names() and 'enc_off' not in f.names() and questrun.LAST.get('verify_pending') == [], str(f.names()))
# verify ID + --role：有人進行中 → 先交接 → bossretry --who → 再讀 → 0
reset()
f = Fake(boss=[(0, {})])
f.all_q = [{'DKBO3': questrun.DOING}, {}]
rc = quiet(questrun.cmd_verify, [2015], 'DKBO3,DKBO5', tools=f)
n = f.names()
check('verify 2015 --role DKBO3,DKBO5：DKBO3 進行中 → 交接（關遇敵 + 組隊）→ bossretry --who DKBO3 → 重讀 DKBO3 → 0', rc == 0
      and ('status_all', (D15,), ('DKBO3', 'DKBO5')) in f.calls and n.index('team_form') < n.index('boss_retry')
      and ('boss_retry', questdefs.get(2015)['track'], ('DKBO3',)) in f.calls and ('status_all', (D15,), ('DKBO3',)) in f.calls, str(f.calls))
f = Fake(boss=[(144, {'msg': '假'})])
f.all_q = [{'DKBO3': questrun.DOING}]
rc = quiet(questrun.cmd_verify, [2015], 'DKBO3', tools=f)
check('verify：bossretry 失敗 → 108', rc == questrun.EXIT_LAGGARD, str(rc))
f = Fake()
f.all_q = [{'DKBO3': questrun.PENDING}]
rc = quiet(questrun.cmd_verify, [2015], 'DKBO3', tools=f)
check('verify：待接取（沒接到）→ 108 不 bossretry、不交接', rc == questrun.EXIT_LAGGARD and 'boss_retry' not in f.names() and 'team_form' not in f.names())
check('verify --role 不認得 → 用法錯誤', quiet(questrun.cmd_verify, [2015], 'XYZ', tools=Fake()) == uikit.EXIT_USAGE)
# clear_pending：status --role all 讀到全員完成的任務移出待驗清單
reset()
questrun.PROGRESS.write_text(_j2.dumps({'tasks': {}, 'verify_pending': {'2017': questrun.time.time(), '2015': questrun.time.time()}}), encoding='utf-8')
check('clear_pending：只讀了 2 人 → 不算驗過、不移', quiet(questrun.clear_pending, [2017], ['DKBO2', 'DKBO3']) == [])
check('clear_pending：讀了全部 5 人 → 移掉 2017、2015 留著', quiet(questrun.clear_pending, [2017], questrun.ALL_ROLES) == [2017]
      and list(questrun.load_progress()['verify_pending']) == ['2015'])
buf = io.StringIO()
with contextlib.redirect_stdout(buf):
    questrun.run([2017], dry_run=True, verify='defer')
check('plan --verify defer 說明延後到呼叫端收尾', 'defer' in buf.getvalue() and '收尾' in buf.getvalue())

print(f'\n{"全部通過" if not fails else f"失敗 {fails} 項"}')
sys.exit(1 if fails else 0)
