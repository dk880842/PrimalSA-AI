#!/usr/bin/env python3
"""quest.py --fight / --solo 的戰鬥分類模擬測試（不碰遊戲）：假時鐘 + 假 read_screen / gui，驗證 BOSS 戰 / 小怪判斷與退出碼。
用法：uv run --no-project python tools/gui/test_quest_fight.py"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import testenv  # noqa: E402,F401  紀錄檔轉向暫存（不污染真 actions.log / quest-events.log / errlog）
import quest  # noqa: E402

quest.CLOSE_ROW_DRAG_TRIES = 0   # 舊的「點關閉」測試維持原樣；拖移另有 (t4b) 測試
_REAL_PS_JSON = quest.ps_json   # 後面測試會把 ps_json 換成假的，這裡留真的給 ps_json 自己的測試
import battleguard  # noqa: E402
import tempfile as _tf
battleguard.LOCK_FILE = Path(_tf.mkdtemp()) / 'battle.lock'      # 測試用鎖檔位置，不碰真正的 tools/.cache/battle.lock
REAL_READ_SCREEN = quest.read_screen                             # 同上：真的 read_screen（測像素分類）
REAL_VERIFY = quest.verify_boss_result                           # 舊案例換成「一律 0」的假的（只測戰鬥分類）；A 區塊用真的
REAL_READ_DLG = quest.read_dialog_texts                          # 真的 read_dialog_texts（用假 ps_json 測）
REAL_CHECK_TEAM = quest.check_team                               # run() 會把 quest.check_team 換成假的；真函式留著測像素邏輯

IDLE = {'state': 'idle', 'gold': 0, 'full': False, 'cmd': False, 'auto_off': False}
DIALOG = dict(IDLE, state='dialog')


class Sim:
    """假遊戲：phase 依虛擬時間排程；點 1380,600 切換自動戰鬥、點逃跑 1283,168 結束小怪戰"""

    def __init__(self, battle_at=None, auto_on=False, dialog_at=None, boss_ends=8.0):
        self.t = 1000.0
        self.clicks = []
        self.battle_at, self.dialog_at = battle_at, dialog_at
        self.auto_on, self.battle_end = auto_on, None
        self.boss_ends = boss_ends
        self.fled = False
        self.dialog_given = False

    def time(self):
        return self.t

    def sleep(self, d):
        self.t += d

    def gui(self, *args, note=''):
        cmd = args[1] if args[0] == 'seq' else ''
        self.clicks.append((round(self.t - 1000, 1), cmd))
        if cmd.startswith('click 1380 600'):
            self.auto_on = not self.auto_on
        if cmd.startswith('click 1283 168'):
            self.fled = True
        return ''

    def screen(self):
        rel = self.t - 1000
        if self.dialog_at is not None and rel >= self.dialog_at and not self.dialog_given and (self.battle_at is None or rel < self.battle_at):
            self.dialog_given = True                     # 對話框出現一輪，按鈕被按掉後消失
            return dict(DIALOG)
        if self.battle_at is not None and rel >= self.battle_at and not self.fled:
            if self.battle_end is None:
                self.battle_end = rel + self.boss_ends
            if rel < self.battle_end:
                cmd = not self.auto_on
                return {'state': 'battle', 'gold': 0, 'full': True, 'cmd': cmd, 'auto_off': not self.auto_on}
        return dict(IDLE)


TEAM = {'ret': (True, 'fake 隊伍完整'), 'calls': []}


def fake_team(size, tag=''):
    TEAM['calls'].append((size, tag))
    if tag.startswith('BOSS 戰後') and 'after' in TEAM:
        return TEAM['after']
    return TEAM['ret']


POS_FN = lambda: (5510, 50, 17)
DLG = {'body': ['你要進入裏面嗎？那趕緊通過吧！'], 'buttons': ['完成', '再見'], 'body_ok': True}   # 假的對話框 OCR（絕不呼叫真的 ocr.ps1）
DLG_READS = []
DLG_SEQ = []                                       # 有排就依序回（重讀測試用），排完回 DLG
DLG_ZOOMS = []                                     # 每次讀的 zooms 參數（None = 預設）


def fake_dialog_texts(zooms=None):
    DLG_READS.append(1)
    DLG_ZOOMS.append(zooms)
    return dict(DLG_SEQ.pop(0) if DLG_SEQ else DLG)


def run(argv, sim, real_verify=False):
    quest.verify_boss_result = REAL_VERIFY if real_verify else (lambda *a, **k: 0)
    quest.time.time, quest.time.sleep = sim.time, sim.sleep
    quest.read_screen, quest.gui, quest.read_pos = sim.screen, sim.gui, lambda: POS_FN()
    quest.walk.gui = sim.gui
    quest.walk.pos = getattr(sim, 'pos', lambda: None)     # 巡路卡住偵測讀座標：測試一律假的（絕不讀真遊戲）
    quest.check_team = fake_team
    quest.read_dialog_texts = fake_dialog_texts
    quest.snap = lambda tag: 'sim.png'
    quest.event = lambda m, shot=None: print(f'   [{sim.t - 1000:5.1f}s] {m}')
    quest.layout.current = lambda: '2880x1659'
    quest.netwatch.guard = lambda *_: {'status': 'ok'}
    sys.argv = ['quest.py'] + argv
    return quest.main()


def check(name, cond, extra=''):
    print(('PASS ' if cond else 'FAIL ') + name + (' ' + extra if extra else ''))
    return cond


def has(sim, prefix):
    return [c for c in sim.clicks if c[1].startswith(prefix)]


ok = True
print('(a) 沒點 NPC 就進戰鬥（20 秒後）：逃跑、不開自動戰鬥')
s = Sim(battle_at=20.0, auto_on=False)
rc = run(['--fight', '--no-click', '--max-seconds', '60'], s)
ok &= check('exit 0（時間到）', rc == 0, f'rc={rc}')
ok &= check('有按逃跑', bool(has(s, 'click 1283 168')))
ok &= check('沒按自動戰鬥', not has(s, 'click 1380 600'))

print('(b) 點 NPC 後 3 秒進戰鬥：開自動戰鬥、打完退出')
s = Sim(battle_at=3.0, auto_on=False, boss_ends=10.0)
rc = run(['--fight', '--npc', '53,17', '--max-seconds', '120'], s)
ok &= check('exit 0（BOSS 戰結束）', rc == 0 and s.t - 1000 < 60, f'rc={rc} t={s.t - 1000:.0f}s')
ok &= check('先點 NPC', bool(s.clicks) and s.clicks[0][1].startswith('click 1215 18; wait 100; click '), str(s.clicks[:1]))
ok &= check('按了自動戰鬥、沒逃跑', len(has(s, 'click 1380 600')) == 1 and not has(s, 'click 1283 168'))

print('(b2) 點 NPC → 對話框 → 戰鬥：BOSS 戰')
s = Sim(dialog_at=2.0, battle_at=6.0, auto_on=False)
rc = run(['--fight', '--npc', '53,17', '--max-seconds', '120'], s)
ok &= check('exit 0', rc == 0, f'rc={rc}')
ok &= check('按對話左鈕 + 自動戰鬥、沒逃跑', bool(has(s, 'click 948 461')) and len(has(s, 'click 1380 600')) == 1 and not has(s, 'click 1283 168'))

print('(c) 自動戰鬥開著遇小怪：先關再逃')
s = Sim(battle_at=20.0, auto_on=True)
rc = run(['--fight', '--no-click', '--max-seconds', '60'], s)
seq = [c[1] for c in s.clicks if c[1].startswith(('click 1380 600', 'click 1283 168'))]
ok &= check('順序：關自動 → 逃跑', seq == ['click 1380 600', 'click 1283 168'], str(seq))
print('(c2) --solo 同樣情境')
s = Sim(battle_at=5.0, auto_on=True)
rc = run(['--solo', '--no-track', '--max-seconds', '40'], s)
seq = [c[1] for c in s.clicks if c[1].startswith(('click 1380 600', 'click 1283 168'))]
ok &= check('--solo 順序：關自動 → 逃跑', seq == ['click 1380 600', 'click 1283 168'], str(seq))

print('(c3) 外掛自動逃跑相關已全部移除：沒有 --manual-escape / --skip-ass-check、退出碼 27 / 28 / 29、讀外掛的程式')
for flag in ('--manual-escape', '--skip-ass-check'):
    s = Sim()
    try:
        run(['--solo', '--no-track', flag, '--max-seconds', '10'], s)
        rejected = False
    except SystemExit as e:
        rejected = e.code == 2
    ok &= check(f'{flag} 已移除（argparse 拒絕）', rejected)
ok &= check('沒有 EXIT_ESCAPE_TIMEOUT / EXIT_ESCAPE_ON / EXIT_ASS_SETUP / SOLO_BATTLE_MAX / check_ass_setup / import ass',
            not any(hasattr(quest, n) for n in ('EXIT_ESCAPE_TIMEOUT', 'EXIT_ESCAPE_ON', 'EXIT_ASS_SETUP', 'SOLO_BATTLE_MAX', 'check_ass_setup', 'ass')))
print('(c4) --solo 戰鬥 400 秒不結束：不再有 27 超時，只到 --max-seconds 結束（0）；第一輪就逃跑，不刷新角色')
s = Sim(battle_at=5.0, auto_on=False, boss_ends=400.0)
rc = run(['--solo', '--no-track', '--max-seconds', '100'], s)
ok &= check('exit 0（時間到）、有逃跑', rc == 0 and bool(has(s, 'click 1283 168')), f'rc={rc}')
ok &= check('--solo 不刷新角色（沒點切換 850,765 / 763,760）', not has(s, 'click 850 765') and not has(s, 'click 763 760'), str(s.clicks))
print('(c5) --fight --no-click：路上小怪（20 秒後才進戰鬥，不在 15 秒時間窗）→ 手動逃跑、不開自動、不刷新')
s = Sim(battle_at=20.0, auto_on=False, boss_ends=10.0)
rc = run(['--fight', '--no-click', '--max-seconds', '60'], s)
ok &= check('小怪：按逃跑、沒按自動戰鬥、沒刷新', bool(has(s, 'click 1283 168')) and not has(s, 'click 1380 600') and not has(s, 'click 850 765'), str(s.clicks))
print('(c6) --fight 任務 / BOSS 戰（點 NPC 後 3 秒開打）：自動戰鬥 + 刷新角色（完整戰鬥切換 850,765；打完前每 REFRESH_GAP 秒一次）')
s = Sim(battle_at=3.0, auto_on=False, boss_ends=20.0)
rc = run(['--fight', '--npc', '53,17', '--max-seconds', '120'], s)
seq = [c[1].split(';')[0] for c in s.clicks if c[1].startswith(('click 1380 600', 'click 850 765', 'click 1283 168'))]
ok &= check('順序：先自動戰鬥，再刷新；沒逃跑', seq[:2] == ['click 1380 600', 'click 850 765'] and 'click 1283 168' not in seq, str(seq))
ok &= check(f'20 秒的戰鬥刷新 2～{int(20 / quest.REFRESH_GAP) + 1} 次（照 REFRESH_GAP={quest.REFRESH_GAP:g} 秒，不是每秒一次）', 2 <= seq.count('click 850 765') <= int(20 / quest.REFRESH_GAP) + 1, str(seq))
ok &= check('刷新用 waitpix + ifok click 910 578', any('waitpix' in c[1] and 'ifok click 910 578' in c[1] for c in s.clicks))
s = Sim(battle_at=3.0, auto_on=False, boss_ends=10.0)
rc = run(['--fight', '--npc', '53,17', '--no-refresh', '--max-seconds', '120'], s)
ok &= check('--no-refresh 不刷新（仍開自動戰鬥）', not has(s, 'click 850 765') and len(has(s, 'click 1380 600')) == 1)
print('(d) 點 NPC 後沒反應')
s = Sim()
rc = run(['--fight', '--npc', '53,17', '--max-seconds', '120'], s)
ok &= check('exit 22', rc == quest.EXIT_NO_NPC, f'rc={rc} t={s.t - 1000:.0f}s')

print('(e) 對話後一直沒開打')
s = Sim(dialog_at=2.0)
rc = run(['--fight', '--npc', '53,17', '--max-seconds', '120'], s)
ok &= check('exit 23', rc == quest.EXIT_NO_BATTLE, f'rc={rc}')

# ---- 新增：--stop-after-dialog 跨步 / 組隊完整戰鬥 / --disband-after ----
class Script:
    """依序回傳預先排好的畫面（每次 read_screen 取下一個，最後一個重複）；gui 只記錄點擊"""

    def __init__(self, seq, pixel=None):
        self.seq, self.i, self.t, self.clicks = seq, 0, 1000.0, []
        self.pixel = pixel or (lambda args: '')

    def time(self):
        return self.t

    def sleep(self, d):
        self.t += d

    def screen(self):
        s = self.seq[min(self.i, len(self.seq) - 1)]
        self.i += 1
        return dict(s)

    def gui(self, *args, note=''):
        if args[0] == 'seq':
            self.clicks.append((round(self.t - 1000, 1), args[1]))
            return ''
        if args[0] == 'pixel':
            return self.pixel(args)
        return ''


def run2(argv, sim, team=False, real_verify=False, marker=None, pos=None, track=None):
    quest.verify_boss_result = REAL_VERIFY if real_verify else (lambda *a, **k: 0)
    if not team and '--team-size' not in argv and '--solo' not in argv:
        argv = argv + ['--team-size', '0']      # 舊案例不測隊伍；要測隊伍檢查的案例傳 team=True
    quest.time.time, quest.time.sleep = sim.time, sim.sleep
    quest.read_screen, quest.gui, quest.read_pos = sim.screen, sim.gui, lambda: None
    quest.read_pos = pos or (lambda: None)
    quest.walk.gui = sim.gui
    quest.snap = lambda tag: 'sim.png'
    quest.event = lambda m, shot=None: print(f'   [{sim.t - 1000:5.1f}s] {m}')
    quest.layout.current = lambda: '2880x1659'
    quest.check_team = fake_team
    quest.read_dialog_texts = fake_dialog_texts
    quest.netwatch.guard = lambda *_: {'status': 'ok'}
    quest.find_marker = marker or (lambda: (_ for _ in ()).throw(AssertionError('不該找黃問號')))
    quest.track_task = track or (lambda *a, **k: (_ for _ in ()).throw(AssertionError('不該點追蹤')))
    sys.argv = ['quest.py'] + argv
    return quest.main()


REWARD = dict(IDLE, state='reward')
WALK = dict(IDLE, state='walking')
FULL_CMD_OFF = {'state': 'battle', 'gold': 0, 'full': True, 'cmd': True, 'auto_off': True}

print('(f) --stop-after-dialog：步 1 對話完（含獎勵）→ 閒置滿 2.5 秒就停，沒點追蹤 / 黃問號（深紅事故）')
s = Script([DIALOG, DIALOG, REWARD, IDLE, IDLE, IDLE, IDLE, IDLE, DIALOG, DIALOG])   # 預設 --every 1.0：閒置要滿 2.5 秒（第 4 個閒置畫面）才停；第 1 個閒置是領獎後確認視窗已關的那次讀圖
rc = run2(['--stop-after-dialog', '--task', '深紅洞窟', '--max-seconds', '120'], s)
ok &= check('exit 0', rc == 0, f'rc={rc}')
ok &= check('停在步 1：只用掉 8 個畫面（含領獎後確認關閉 1 次；沒看到步 2 的對話）、花 6.3 秒', s.i == 8 and abs(s.t - 1000 - 6.3) < 1e-6, f'i={s.i} t={s.t - 1000}')
ok &= check('沒有任何追蹤 / 問號點擊（只有對話左鈕 + 獎勵確認）', all(c[1].startswith(('click 948 461', 'click 720 572')) for c in s.clicks), str(s.clicks))

print('(f1) 預設輪詢間隔 = 1.0 秒')
s = Script([DIALOG, IDLE, IDLE, IDLE, IDLE, IDLE])
rc = run2(['--stop-after-dialog', '--task', 'x', '--max-seconds', '120'], s)
ok &= check('每輪 sleep 1.0（點擊時間 0.0 / 之後每秒一輪）', quest.DEFAULT_EVERY == 1.0 and s.t - 1000 == 4.0, f't={s.t - 1000}')
print('(f2) --stop-after-dialog：步完成後遊戲自己開始 Auto Walking → 退出碼 24')
s = Script([DIALOG, IDLE, WALK])
rc = run2(['--stop-after-dialog', '--task', '深紅洞窟', '--max-seconds', '120'], s)
ok &= check('exit 24', rc == quest.EXIT_AUTOWALK, f'rc={rc}')

print('(g) 組隊預設模式完整戰鬥、自動戰鬥關：按 1380,600（不逃跑）')
s = Script([FULL_CMD_OFF, FULL_CMD_OFF, dict(FULL_CMD_OFF, cmd=False, auto_off=False), IDLE], None)
rc = run2(['--no-track', '--max-seconds', '30'], s)
ok &= check('有按自動戰鬥、沒按逃跑', len(has(s, 'click 1380 600')) == 1 and not has(s, 'click 1283 168'), str(s.clicks))
print('(g2) 按了 4 次仍關 → 退出碼 25')
s = Script([FULL_CMD_OFF])
rc = run2(['--no-track', '--max-seconds', '120'], s)
ok &= check('exit 25', rc == quest.EXIT_BATTLE_STUCK and len(has(s, 'click 1380 600')) == quest.AUTO_STUCK_MAX, f'rc={rc} n={len(has(s, "click 1380 600"))}')

print('(h) --disband-after（分頁 / 隊長紅標像素用 2026-10-10 實機量測值）')
TAB_TEAM_PX = {'130,222': '87,68,41', '130,250': '85,65,41', '270,222': '215,185,139', '270,250': '205,173,131'}   # 組隊分頁選中
TAB_TASK_PX = {'130,222': '213,179,128', '130,250': '211,179,128', '270,222': '90,69,41', '270,250': '87,70,41'}   # 任務分頁選中
BADGE_RED, BADGE_NONE = '217,33,33', '245,223,187'
# 實機樣本（fixtures/leader_badge_px.json）：新小「L」標 / 舊紅「隊」字標 / 已解散
import json as _json
_LB = _json.loads((Path(__file__).resolve().parent / 'fixtures' / 'leader_badge_px.json').read_text(encoding='utf-8'))['images']


def _lb_cols(h):
    return [tuple(int(h[i + j:i + j + 2], 16) for j in (0, 2, 4)) for i in range(0, len(h), 6)]


BADGE_L_PX = ['%d,%d,%d' % c for c in _lb_cols(_LB['quest-log/020133-disband-already-solo.png']['px'])]


def px_fake(tab=TAB_TEAM_PX, badges=(True, False)):
    """gui('pixel') 假回應：4 點分頁探針 / 4 點隊長紅標（依序消耗 badges；讀不到用 'err'）"""
    it = iter(badges)

    def pixel(args):
        pts = args[1].split()
        if pts[0] == '130,222':
            return ' '.join(tab[p] for p in pts)
        if pts[0] == '%d,%d' % quest.LEADER_BADGE_PTS[0]:
            b = next(it, False)
            return 'err' if b == 'err' else ' '.join(BADGE_L_PX if b else [BADGE_NONE] * len(pts))
        return ''
    return pixel


print('(h0) tab_state / has_leader_badge 像素判斷')
for nm, tab, want in [('組隊選中', TAB_TEAM_PX, 'team'), ('任務選中', TAB_TASK_PX, 'task'),
                      ('舊探針式混雜（y=225 邊緣一點不準）', dict(TAB_TEAM_PX, **{'130,250': '213,181,131'}), None)]:
    quest.gui = Script([IDLE], px_fake(tab)).gui
    ok &= check(f'tab_state {nm} → {want}', quest.tab_state() == want, str(quest.tab_state()))
quest.gui = Script([IDLE], px_fake(badges=(True, False))).gui
ok &= check('has_leader_badge 紅標 True', quest.has_leader_badge() is True)
ok &= check('has_leader_badge 米色 False', quest.has_leader_badge() is False)
quest.gui = Script([IDLE], px_fake(badges=('err',))).gui
ok &= check('has_leader_badge 讀不到 None', quest.has_leader_badge() is None)
for _k, _v in _LB.items():
    _n = quest.leader_badge_red(_lb_cols(_v['px']))
    ok &= check(f'隊長標實機樣本 {_k} → {_v["expect"]}', (_n >= quest.LEADER_BADGE_MIN) == _v['expect'], f'紅點 {_n}')


def disband_case(name, tab, badges, sigs, want_rc, want_btn, want_leader, expect_leader=False):
    s = Script([IDLE], px_fake(tab, badges))
    quest.time.time, quest.time.sleep = s.time, s.sleep
    quest.gui, quest.snap = s.gui, lambda tag: 'sim.png'
    quest.event = lambda m, shot=None: print(f'   {m}')
    sig_seq(*sigs)
    rc = quest.disband_team(expect_leader=expect_leader)
    ok_ = rc == want_rc and bool(has(s, 'click 200 372')) == want_btn and bool(has(s, 'click 210 320')) == want_leader
    return check(f'disband {name}', ok_, f'rc={rc} {[c[1][-14:] for c in s.clicks]}')


def sig_seq(*vals):
    it = iter(vals)
    quest.list_signature = lambda: next(it)


ok &= disband_case('成功（紅標消失、面板有變）', TAB_TEAM_PX, (True, False), ('a', 'b', 'c'), 0, True, True)
ok &= disband_case('分頁沒切過去 → 不點隊長列也不點解散', TAB_TASK_PX, (True, False), ('a', 'b', 'c'), quest.EXIT_DISBAND_FAIL, False, False)
ok &= disband_case('已是單人（無紅標）→ 不點任何東西、退出碼 0', TAB_TEAM_PX, (False,), ('a', 'b', 'c'), 0, False, False)
ok &= disband_case('expect_leader（team.py：面板說當前是隊長）但沒有隊長標 → 26 不點（不當已單人）', TAB_TEAM_PX, (False,), ('a', 'b', 'c'), quest.EXIT_DISBAND_FAIL, False, False, expect_leader=True)
ok &= disband_case('expect_leader + 小「L」標實機樣本 → 照常解散', TAB_TEAM_PX, (True, False), ('a', 'b', 'c'), 0, True, True, expect_leader=True)
ok &= disband_case('紅標讀不到 → 26 不點', TAB_TEAM_PX, ('err',), ('a', 'b', 'c'), quest.EXIT_DISBAND_FAIL, False, False)
ok &= disband_case('選單沒彈出 → 不點解散', TAB_TEAM_PX, (True, False), ('a', 'a', 'c'), quest.EXIT_DISBAND_FAIL, False, True)
ok &= disband_case('解散後畫面沒變 → 未確認', TAB_TEAM_PX, (True, False), ('a', 'b', 'b'), quest.EXIT_DISBAND_FAIL, True, True)
ok &= disband_case('解散後紅標還在 → 未確認', TAB_TEAM_PX, (True, True), ('a', 'b', 'c'), quest.EXIT_DISBAND_FAIL, True, True)

print('(h2) --stop-after-dialog --disband-after：停止後才解散；分頁沒切過去 → 26')
s = Script([DIALOG, IDLE, IDLE, IDLE, IDLE], px_fake(TAB_TASK_PX))
rc = run2(['--stop-after-dialog', '--disband-after', '--task', 'x', '--max-seconds', '60'], s)
ok &= check('exit 26 且沒點解散', rc == quest.EXIT_DISBAND_FAIL and not has(s, 'click 200 372') and not has(s, 'click 210 320'), f'rc={rc} {s.clicks}')

print('(i) 清理 3 天前截圖（暫存資料夾）')
import os, tempfile
from pathlib import Path as _P
with tempfile.TemporaryDirectory() as d:
    d = _P(d)
    now = 10_000_000.0
    def mk(n, age_days):
        (d / n).write_bytes(b'x')
        os.utime(d / n, (now - age_days * 86400, now - age_days * 86400))
    mk('old.png', 4)
    mk('old2.jpg', 10)
    mk('new.png', 1)
    mk('edge.png', 2.9)
    mk('old.json', 30)                                  # 非圖檔不碰
    (d / 'sub').mkdir()
    (d / 'sub' / 'deep.png').write_bytes(b'x')
    os.utime(d / 'sub' / 'deep.png', (now - 99 * 86400, now - 99 * 86400))   # 子資料夾內的不碰
    n = quest.cleanup_old_shots(3, d, now)
    left = sorted(f.name for f in d.iterdir())
    ok &= check('刪 2 張（old.png / old2.jpg）', n == 2 and left == ['edge.png', 'new.png', 'old.json', 'sub'], f'n={n} left={left}')
    ok &= check('子資料夾內檔案還在', (d / 'sub' / 'deep.png').exists())
ok &= check('資料夾不存在 → 0、不丟例外', quest.cleanup_old_shots(3, _P('/nonexistent-psa-dir'), 1.0) == 0)
calls = []
quest.cleanup_old_shots = lambda *a, **k: (calls.append(1), 7)[1]
s = Script([DIALOG, IDLE, IDLE, IDLE, IDLE])
run2(['--stop-after-dialog', '--task', 'x', '--max-seconds', '60'], s)
ok &= check('main 啟動時呼叫清理', len(calls) == 1)

UNK = dict(IDLE, state='unknown')
print('(k3) 鐵則 5：連續 3 次不認得但沒滿 5 秒不停；滿 5 秒才停')
s = Script([UNK])
rc = run2(['--no-track', '--max-seconds', '60'], s)
ok &= check('exit 2，t >= 5', rc == 2 and s.t - 1000 >= 5.0, f'rc={rc} t={s.t - 1000}')

print('(k4) 地圖轉場（載入圖 / 全黑）：等、不點、不計入不認得；載入圖超過 LOADING_MAX_S → 43，全黑超過 → 落回不認得規則 2')
_keep_tr = quest.transition_screen
_tr = {'until': 10.0, 'kind': 'loading'}
quest.transition_screen = lambda: _tr['kind'] if s.t - 1000 < _tr['until'] else None
s = Script([UNK])
rc = run2(['--no-track', '--max-seconds', '120'], s)
ok &= check('載入 10 秒後變真的不認得 → 等完載入才開始數，exit 2 且 t >= 15', rc == 2 and s.t - 1000 >= 15.0, f'rc={rc} t={s.t - 1000}')
ok &= check('載入期間 0 點擊', not [c for c in s.clicks if c[1].startswith('click')], str(s.clicks[:5]))
_tr['until'] = 1e9
s = Script([UNK])
rc = run2(['--no-track', '--max-seconds', '300'], s)
ok &= check(f'載入圖一直不結束 → 退出碼 {quest.EXIT_LOADING_STUCK}（約 {quest.LOADING_MAX_S:.0f} 秒，不是 2）', rc == quest.EXIT_LOADING_STUCK and quest.LOADING_MAX_S <= s.t - 1000 < quest.LOADING_MAX_S + 5,
            f'rc={rc} t={s.t - 1000}')
_tr['kind'] = 'black'
s = Script([UNK])
rc = run2(['--no-track', '--max-seconds', '300'], s)
ok &= check('全黑一直不結束 → 上限後落回不認得規則 → 2（全黑沒有正面特徵，鐵則 5 從嚴）', rc == 2 and s.t - 1000 >= quest.LOADING_MAX_S, f'rc={rc} t={s.t - 1000}')
s = Script([IDLE, UNK, UNK, IDLE, UNK])
_tr.update(kind='loading', until=1e9)
rc = run2(['--no-track', '--max-seconds', '300'], s)
ok &= check('轉場中間回過主畫面 → 計時重來（兩段各自 < 上限不誤判卡住）', rc == quest.EXIT_LOADING_STUCK and s.t - 1000 >= quest.LOADING_MAX_S + 3, f'rc={rc} t={s.t - 1000}')
ok &= check('transition_wait：上限內 True、超過 False', quest.transition_wait(100.0, 100.0 + quest.LOADING_MAX_S - 1) and not quest.transition_wait(100.0, 100.0 + quest.LOADING_MAX_S))
quest.transition_screen = _keep_tr

print('(k5) 停手前重讀（2026-10-17 p3 bow16 212648：過場連中 3 次，存證圖其實是 Auto Walking；p2 21:07 解決異常窗 → 加載中）')
ok &= check('unknown_recheck：重讀是 walking / idle / battle → resume；dialog / select / panel 不算過場 → stop',
            all(quest.unknown_recheck(x, None) == 'resume' for x in ('walking', 'idle', 'battle'))
            and all(quest.unknown_recheck(x, None) == 'stop' for x in ('dialog', 'select', 'panel', 'reward')))
ok &= check('unknown_recheck：重讀仍不認得 + 載入圖 → loading；全黑 / 沒特徵 / 讀失敗 → stop',
            quest.unknown_recheck('unknown', 'loading') == 'loading' and quest.unknown_recheck('unknown', 'black') == 'stop'
            and quest.unknown_recheck('unknown', None) == 'stop' and quest.unknown_recheck('error', 'loading') == 'stop' and quest.unknown_recheck(None, None) == 'stop')
s = Script([UNK] * 6 + [WALK])
rc = run2(['--no-track', '--max-seconds', '30'], s)
ok &= check('連 6 次不認得（滿 5 秒），停手前重讀已是跑路 → 不停手（rc 不是 2）、0 點擊', rc != 2 and not [c for c in s.clicks if c[1].startswith('click')], f'rc={rc} {s.clicks[:3]}')
s = Script([UNK])
rc = run2(['--no-track', '--max-seconds', '60'], s)
ok &= check('重讀仍不認得 → 照舊 rc 2（鐵則 5 不放寬）', rc == 2, f'rc={rc}')
_keep_tr = quest.transition_screen
_flag = {'n': 0}
def _tr_after():                                           # 前幾次轉場讀點都沒特徵，停手前那次才是載入圖
    _flag['n'] += 1
    return 'loading' if s.t - 1000 >= 5.0 else None
quest.transition_screen = _tr_after
s = Script([UNK] * 7 + [WALK])
rc = run2(['--no-track', '--max-seconds', '30'], s)
ok &= check('停手前那一刻換成載入圖 → 改等載入、不 rc 2', rc != 2, f'rc={rc}')
quest.transition_screen = _keep_tr

print('(k6) 戰鬥上疊寵物資訊浮窗（battle_tip）：當戰鬥、不點、等它消失；超過 TIP_MAX_S 才落回不認得規則')
_keep_tip = quest.battle_tip_screen
_tip = {'until': 25.0}
quest.battle_tip_screen = lambda: s.t - 1000 < _tip['until']
s = Script([DIALOG] + [UNK] * 25 + [IDLE])
rc = run2(['--no-track', '--max-seconds', '60', '--team-size', '0'], s)
_clk = [c for c in s.clicks if c[1].startswith('click') and c[1] != 'click 948 461']
ok &= check('浮窗 25 秒（模擬 p2 21:31:57～21:32:21）→ 不 rc 2、浮窗期間除了對話鈕 0 點擊（不按切換 / 刷新 / 自動戰鬥）', rc != 2 and not _clk, f'rc={rc} {_clk[:5]}')
_tip['until'] = 1e9
s = Script([UNK])
rc = run2(['--no-track', '--max-seconds', '300'], s)
ok &= check(f'浮窗一直不消失 → TIP_MAX_S（{quest.TIP_MAX_S:.0f} 秒）後照不認得規則 rc 2', rc == 2 and s.t - 1000 >= quest.TIP_MAX_S, f'rc={rc} t={s.t - 1000}')
quest.battle_tip_screen = _keep_tip


# ---- 事故後新增：隊伍檢查 / 戰鬥鎖檔 / --npc auto 取目前步驟 ----
import argparse
import os
print('(m) 隊伍標籤像素判斷（隊長紅、隊員黃、底深棕；2026-10-10 實機：隊長紅點 30、隊員黃點 42~44）')
RED, YEL, BG = (217, 33, 33), (240, 200, 60), (78, 66, 59)
n_s = len(quest.TEAM_SAMPLE)
ok &= check('紅點 >= 8 → leader', quest.classify_team_label([RED] * 12 + [BG] * (n_s - 12)) == 'leader')
ok &= check('黃點 >= 8 → member', quest.classify_team_label([YEL] * 12 + [BG] * (n_s - 12)) == 'member')
ok &= check('只有底色 / 白字 → other', quest.classify_team_label([BG] * n_s) == 'other' and quest.classify_team_label([(240, 240, 240)] * 12 + [BG] * (n_s - 12)) == 'other')
ok &= check('紅點太少（<8）→ other', quest.classify_team_label([RED] * 3 + [BG] * (n_s - 3)) == 'other')
ALL5 = {'DKBO': 'leader', 'DKBO2': 'member', 'DKBO3': 'member', 'DKBO4': 'member', 'DKBO5': 'member'}
ok &= check('judge 5 人隊 OK', quest.judge_team(ALL5, 5)[0])
four = dict(ALL5, DKBO4='other')
j = quest.judge_team(four, 5)
ok &= check('judge 4 人（DKBO4 單人）不符且說明點名 DKBO4', (not j[0]) and 'DKBO4' in j[1].split('不在隊')[1], j[1])
ok &= check('judge 兩個隊長 / 無隊長 不符', not quest.judge_team(dict(ALL5, DKBO2='leader'), 5)[0] and not quest.judge_team(dict(ALL5, DKBO='member'), 5)[0])
ok &= check('--team-size 4：4 人隊 + 另 1 人單人（DKBO4 other）→ 通過（單人卡片不算錯）', quest.judge_team(four, 4)[0])
ok &= check('--team-size 5 + 1 人單人 → 仍不符（5 人都要在隊）', not quest.judge_team(four, 5)[0])
ok &= check('--team-size 4 但只有 3 人在隊 → 不符', not quest.judge_team(dict(four, DKBO5='other'), 4)[0])
ok &= check('--team-size 2：隊長 + 1 隊員，其餘 3 張單人 → 通過', quest.judge_team({'DKBO': 'leader', 'DKBO2': 'member', 'DKBO3': 'other', 'DKBO4': 'other', 'DKBO5': 'other'}, 2)[0])
ok &= check('隊長是單人（全 other，沒有隊長）→ 不符', not quest.judge_team({r: 'other' for r in ALL5}, 4)[0])


class PanelGame:
    """假遊戲：點切換 763,760 開面板；點 ✕ 1064,208 關；pixel 回隊伍標籤顏色（其餘點回 SIG_PANEL 色 / 0）"""

    def __init__(self, kinds, opens=True):
        self.kinds, self.opens, self.panel, self.clicks = kinds, opens, False, []

    def gui(self, *args, note=''):
        if args[0] == 'seq':
            self.clicks.append(args[1])
            if args[1].startswith('click 763 760') and self.opens:
                self.panel = True
            if args[1].startswith('click 1064 208'):
                self.panel = False
            return ''
        if args[0] == 'key':
            self.clicks.append('key ' + args[1])
            self.panel = False
            return ''
        if args[0] == 'pixel':
            return team_px(self.kinds)(args)
        return ''

    def screen(self):
        return dict(IDLE, state='panel' if self.panel else 'idle')


def team_px(kinds):
    col = {'leader': RED, 'member': YEL, 'other': BG}
    return lambda args: ' '.join(' '.join(['%d,%d,%d' % col[kinds[r]]] * n_s) for r in quest.TEAM_CARDS)


print('(m2) check_team（真函式 + 假面板，開 / 關走 uikit.open_panel / close_panel）：5 人 OK / 4 人不符 / 面板沒開；每次都關面板、沒開就不讀')
import uikit  # noqa: E402


class PanelUi:
    """假 uikit：open_panel 前 fail 次失敗；close_panel 點 ✕ 1064,208；記錄開關次數"""

    def __init__(self, pg, fail=0):
        self.pg, self.fail, self.opens, self.closes = pg, fail, 0, 0

    def open_panel(self, p, timeout=4.0):
        self.opens += 1
        if self.fail > 0:
            self.fail -= 1
            return False
        self.pg.panel = self.pg.opens
        return self.pg.panel

    def close_panel(self, p, known_open=False):
        self.closes += 1
        self.pg.clicks.append('click 1064 208')
        self.pg.panel = False
        return True


_real_ui = (uikit.open_panel, uikit.close_panel)
quest.CHECK_TEAM_GAP = 0.0
for nm, kinds, opens, want, nopen in [('5 人', ALL5, True, True, 1), ('4 人', four, True, False, 1), ('面板打不開', ALL5, False, None, quest.CHECK_TEAM_TRIES)]:
    pg = PanelGame(kinds, opens)
    ui = PanelUi(pg)
    uikit.open_panel, uikit.close_panel = ui.open_panel, ui.close_panel
    quest.gui, quest.read_screen = pg.gui, pg.screen
    res = REAL_CHECK_TEAM(5, '測試：')
    ok &= check(f'{nm} → {want}（開面板 {nopen} 次）', res[0] is want and not pg.panel and ui.opens == nopen, str(res))
    if opens:
        ok &= check(f'{nm}：用 uikit.close_panel（✕ 1064,208）關面板', ui.closes == 1 and any(c.startswith('click 1064 208') for c in pg.clicks), str(pg.clicks))
pg = PanelGame(ALL5, True)
ui = PanelUi(pg, fail=2)
uikit.open_panel, uikit.close_panel = ui.open_panel, ui.close_panel
quest.gui, quest.read_screen = pg.gui, pg.screen
res = REAL_CHECK_TEAM(5, '測試：')
ok &= check('打不開 2 次、第 3 次開起來 → 原地重試成功（True、開 3 次）', res[0] is True and ui.opens == 3, str(res))
state = {'s': 'dialog'}
pg = PanelGame(ALL5, True)
ui = PanelUi(pg)
uikit.open_panel, uikit.close_panel = ui.open_panel, ui.close_panel
quest.gui, quest.read_screen = pg.gui, lambda: dict(IDLE, state=state['s'])
res = REAL_CHECK_TEAM(5, '測試：')
ok &= check('畫面是對話 / 戰鬥 → 不開面板（0 次點擊）、回 None', res[0] is None and ui.opens == 0 and not pg.clicks, str(res))
uikit.open_panel, uikit.close_panel = _real_ui

print('(n) --fight 4 人隊 → 不點 NPC，退出碼 30；5 人 → 照常點')
TEAM['ret'], TEAM['calls'] = (False, "隊長 ['DKBO']、隊員 ['DKBO2', 'DKBO3', 'DKBO5']、不在隊 / 單人 / 離線 ['DKBO4']"), []
s = Sim(battle_at=3.0)
rc = run(['--fight', '--npc', '53,17', '--max-seconds', '60'], s)
ok &= check('exit 30、沒任何點擊、檢查人數 5', rc == quest.EXIT_TEAM_MISMATCH and not s.clicks and TEAM['calls'] == [(5, '--fight 點 NPC 前：')], f'rc={rc} clicks={s.clicks} calls={TEAM["calls"]}')
TEAM['ret'], TEAM['calls'] = (None, '切換面板沒打開'), []
s = Sim(battle_at=3.0)
rc = run(['--fight', '--npc', '53,17', '--max-seconds', '60'], s)
ok &= check('讀不到隊伍 → 也不點 NPC（30）', rc == 30 and not s.clicks)
TEAM['ret'], TEAM['calls'] = (True, 'ok'), []
s = Sim(battle_at=3.0, boss_ends=8.0)
rc = run(['--fight', '--npc', '53,17', '--team-size', '4', '--max-seconds', '60'], s)
ok &= check('--team-size 4 傳給檢查；通過 → 點 NPC、BOSS 戰結束 0', rc == 0 and TEAM['calls'][0][0] == 4 and bool(s.clicks) and s.clicks[0][1].startswith('click 1215 18'), f'rc={rc} {TEAM["calls"]}')
TEAM['ret'], TEAM['calls'] = (False, 'x'), []
s = Sim(battle_at=3.0, boss_ends=8.0)
rc = run(['--fight', '--npc', '53,17', '--team-size', '0', '--max-seconds', '60'], s)
ok &= check('--team-size 0 跳過檢查', rc == 0 and not TEAM['calls'])
s = Sim(battle_at=3.0, boss_ends=8.0)
rc = run(['--fight', '--no-click', '--max-seconds', '60'], s)
ok &= check('--no-click 不檢查隊伍', rc == 0 and not TEAM['calls'])
TEAM['ret'] = (True, 'ok')

print('(n2) 預設模式（要點追蹤）：開跑前檢查；脫隊 → 退出碼 32，沒點追蹤 / 黃問號；--solo / --no-track 不檢查')
TEAM['calls'] = []
s = Script([IDLE, IDLE])
TEAM['ret'] = (False, "不在隊 ['DKBO3']")
rc = run2(['--task', 'x', '--max-seconds', '60'], s, team=True)
ok &= check('exit 30（開始前驗隊伍）且沒有點擊（find_marker / track_task 沒被呼叫）', rc == quest.EXIT_TEAM_MISMATCH and not s.clicks and len(TEAM['calls']) == 1, f'rc={rc} {s.clicks}')
for extra in (['--solo', '--no-track'], ['--no-track', '--team-size', '0']):
    TEAM['calls'] = []
    s = Script([IDLE, IDLE, IDLE, IDLE])
    rc = run2(extra + ['--max-seconds', '4'], s, team=True)
    ok &= check(f'{" ".join(extra)} 不檢查隊伍', not TEAM['calls'] and rc == 0, f'rc={rc}')
TEAM['calls'], TEAM['ret'] = [], (False, "不在隊 ['DKBO3']")
s = Script([IDLE, IDLE])
rc = run2(['--no-track', '--max-seconds', '4'], s, team=True)
ok &= check('預設模式 --no-track 也先驗隊伍：不符 → 30、沒點擊', rc == quest.EXIT_TEAM_MISMATCH and not s.clicks and len(TEAM['calls']) == 1, f'rc={rc} {s.clicks}')

TEAM['calls'], TEAM['ret'] = [], (False, "不在隊 ['DKBO3']")
s = Script([IDLE, IDLE])
rc = run2(['--no-track', '--team-fresh', '--max-seconds', '4'], s, team=True)
ok &= check('--team-fresh（questrun 剛驗過隊伍）：開始前不開切換面板驗隊伍（2026-10-12）', not TEAM['calls'] and rc == 0, f'rc={rc} {TEAM["calls"]}')
TEAM['calls'], TEAM['ret'] = [], (True, 'ok')
s = Script([IDLE, DIALOG, REWARD, IDLE, IDLE, IDLE])
rc = run2(['--task', 'x', '--team-fresh', '--max-seconds', '8'], s, team=True, marker=lambda: None, track=lambda *a, **k: True)
ok &= check('--team-fresh 略過開始前；領獎後點追蹤前也不驗隊伍（2026-10-17 精簡）→ 整片 0 次切換面板', not TEAM['calls'], str(TEAM['calls']))

print('(n4) 2026-10-10 18:44 事件：--solo 後隊伍散成單人，--stop-after-rewards 啟動 → 先驗隊伍，不符退出碼 30、沒有任何點擊')
TEAM['calls'], TEAM['ret'] = [], (False, "隊長 無、隊員 無、不在隊 / 單人 / 離線 ['DKBO', 'DKBO2', 'DKBO3', 'DKBO4', 'DKBO5']")
for first in (IDLE, DIALOG):
    s = Script([first, IDLE, IDLE, DIALOG, REWARD, IDLE])
    rc = run2(['--task', '碧青洞窟', '--stop-after-rewards', '1', '--max-seconds', '180'], s, team=True)
    ok &= check(f'起始畫面 {first["state"]}：exit 30、沒有任何點擊（含對話左鈕 / 獎勵確認）', rc == quest.EXIT_TEAM_MISMATCH and not s.clicks, f'rc={rc} clicks={s.clicks} calls={TEAM["calls"]}')
    ok &= check('  開始前驗了一次（人數 5）', TEAM['calls'] and TEAM['calls'][-1] == (5, '開始前：'), str(TEAM['calls']))
    TEAM['calls'] = []
print('(n5) 啟動時對話框已開：先 ESC（不按左鈕）、回 idle 驗隊伍；通過才處理對話 / 獎勵')
TEAM['calls'], TEAM['ret'] = [], (True, 'ok')
s = Script([DIALOG, IDLE, DIALOG, DIALOG, REWARD, IDLE])
rc = run2(['--no-track', '--stop-after-rewards', '1', '--max-seconds', '180'], s, team=True)
keys = [c for c in s.clicks if c[1].startswith('click 948 461')]
ok &= check('exit 0（5 人隊正常領獎）、第一次驗隊伍在第一次按左鈕之前', rc == 0 and len(TEAM['calls']) == 1 and len(keys) == 2 and bool(has(s, 'click 720 572')), f'rc={rc} {s.clicks} {TEAM["calls"]}')
s = Script([DIALOG])
rc = run2(['--task', 'x', '--max-seconds', '60'], s, team=True)
ok &= check('對話框 ESC 3 次仍關不掉 → 30、不按左鈕', rc == quest.EXIT_TEAM_MISMATCH and not has(s, 'click 948 461'), f'rc={rc} {s.clicks}')
print('(n6) 正常 5 人隊 idle 啟動：驗過一次後照常按對話 / 領獎')
TEAM['calls'] = []
s = Script([IDLE, DIALOG, DIALOG, REWARD, IDLE])
rc = run2(['--no-track', '--stop-after-rewards', '1', '--max-seconds', '180'], s, team=True)
ok &= check('exit 0、只驗 1 次（開始前）、有按對話左鈕', rc == 0 and TEAM['calls'] == [(5, '開始前：')] and len(has(s, 'click 948 461')) == 2, f'rc={rc} {TEAM["calls"]} {s.clicks}')
TEAM['ret'] = (True, 'ok')
print('(n3) 預設模式：只在必要時驗隊伍（開始前 1 次；平常點追蹤不再驗；任務戰打完後下一次點之前才驗）')
TEAM['ret'], TEAM['calls'] = (True, 'ok'), []
tracked_n = []
s = Script([IDLE] * 3)
quest.find_marker = lambda: None
quest.track_task = lambda *a, **k: (tracked_n.append(1), None)[1]       # None = 畫面變了，交回主迴圈（不計 task_miss）
rc = None
quest.time.time, quest.time.sleep = s.time, s.sleep
quest.read_screen, quest.gui, quest.read_pos = s.screen, s.gui, lambda: None
quest.walk.gui = s.gui
quest.snap = lambda tag: 'sim.png'
quest.event = lambda m, shot=None: None
quest.layout.current = lambda: '2880x1659'
quest.netwatch.guard = lambda *_: {'status': 'ok'}
sys.argv = ['quest.py', '--task', 'x', '--max-seconds', '8']
rc = quest.main()
ok &= check('8 秒內只檢查 1 次（開始前）、追蹤點了多次', len(TEAM['calls']) == 1 and len(tracked_n) >= 3, f'checks={len(TEAM["calls"])} tracks={len(tracked_n)}')
TEAM['ret'], TEAM['calls'] = (True, 'ok'), []
BATTLE_Q = {'state': 'battle', 'gold': 0, 'full': True, 'cmd': False, 'auto_off': False}
s = Script([IDLE, DIALOG, BATTLE_Q, BATTLE_Q, IDLE, IDLE, IDLE, IDLE, IDLE, IDLE, IDLE, IDLE])
tracked_n.clear()
quest.time.time, quest.time.sleep = s.time, s.sleep
quest.read_screen, quest.gui = s.screen, s.gui
quest.walk.gui = s.gui
sys.argv = ['quest.py', '--task', 'x', '--max-seconds', '14', '--no-stop-after-boss']
rc = quest.main()
tags = [t for _, t in TEAM['calls']]
ok &= check('一般任務（沒 --boss-team-check）任務戰打完：不開切換面板，只有開始前 1 次（2026-10-17）', tags == ['開始前：'] and len(tracked_n) >= 2, f'{tags} tracks={len(tracked_n)}')
TEAM['calls'] = []
s = Script([IDLE, DIALOG, BATTLE_Q, BATTLE_Q, IDLE, IDLE, IDLE, IDLE, IDLE, IDLE, IDLE, IDLE])
tracked_n.clear()
quest.time.time, quest.time.sleep = s.time, s.sleep
quest.read_screen, quest.gui = s.screen, s.gui
quest.walk.gui = s.gui
sys.argv = ['quest.py', '--task', 'x', '--max-seconds', '14', '--no-stop-after-boss', '--boss-team-check']
rc = quest.main()
tags = [t for _, t in TEAM['calls']]
ok &= check('--boss-team-check --no-stop-after-boss 任務戰打完後：下一次點追蹤前驗 1 次，之後不再驗', tags.count('點追蹤 / 黃問號前：') == 1 and tags[0] == '開始前：' and len(tags) == 2 and len(tracked_n) >= 2, f'{tags} tracks={len(tracked_n)}')

print('(o) 戰鬥鎖檔：戰鬥中存在（含 pid）、戰鬥結束 / 程式結束後刪除')
seen = []


class LockSim(Sim):
    def screen(self):
        r = super().screen()
        seen.append((r['state'], battleguard.locked() is not None))
        return r


s = LockSim(battle_at=3.0, auto_on=False, boss_ends=8.0)
rc = run(['--fight', '--no-click', '--max-seconds', '60'], s)
bat = [x for st_, x in seen if st_ == 'battle']
ok &= check('戰鬥畫面第 2 次讀起鎖檔都有效（第 1 次讀到戰鬥時才剛寫鎖）', len(bat) >= 2 and all(bat[1:]), str(bat))
ok &= check('戰鬥結束後鎖檔已刪', not battleguard.LOCK_FILE.exists())
idle_after = [x for st_, x in seen[seen.index(next(e for e in seen if e[0] == 'battle')):] if st_ == 'idle']
ok &= check('戰鬥後第一次看到閒置時鎖已刪', idle_after and not idle_after[-1], str(idle_after[:2]))
battleguard.acquire('x')
d = battleguard.locked()
ok &= check('locked() 回 pid = 自己', d and d['pid'] == os.getpid())
battleguard.LOCK_FILE.write_text('{"pid": 99999999, "start": %f}' % __import__('time').time())
ok &= check('死 pid 的鎖 → 視為無鎖並清掉', battleguard.locked() is None and not battleguard.LOCK_FILE.exists())
battleguard.LOCK_FILE.write_text('{"pid": %d, "start": 1}' % os.getpid())
ok &= check('超過 30 分鐘的鎖 → 無效', battleguard.locked(now=1e9) is None)
s = Sim(battle_at=3.0, boss_ends=1000.0)
try:
    run(['--fight', '--no-click', '--max-seconds', '30'], s)
except Exception:
    pass
ok &= check('--max-seconds 到時（戰鬥中）程式結束 → 鎖檔刪除', not battleguard.LOCK_FILE.exists())

print('(p) --npc auto 取「目前步驟」：追蹤說明文字對 Task 表（任務 碧青洞窟 2002）')


def ns(**kw):
    d = dict(npc='auto', task='碧青洞窟', step=0, at='', npc_map=None)
    d.update(kw)
    return argparse.Namespace(**d)


def with_ocr(lines):
    quest.ps_json = lambda script, *args: {'ok': True, 'lines': [{'text': t, 'y': y, 'x': 200} for t, y in lines]}


quest.event = lambda m, shot=None: None
with_ocr([('碧青洞窟', 309), ('找菲伊拿群青的水', 341), ('漆黑洞窟(一轉)', 426)])
a_ = ns()
ok &= check('說明「找菲伊拿群青的水」→ 步 6 菲伊 31302:27,31', quest.resolve_npc(a_) == (27, 31) and a_.npc_map == 31302)
with_ocr([('碧青洞窟', 309), ('獲取深藍色的石頭', 341)])
a_ = ns()
ok &= check('說明「獲取深藍色的石頭」→ 步 5（30305:57,48），不是第一個戰鬥步（8 樓）', quest.resolve_npc(a_) == (57, 48) and a_.npc_map == 30305)
with_ocr([('碧青洞窟', 309), ('獲取深籃色的石頭', 341), ('獲取深藍色的石頭', 341)])
ok &= check('OCR 錯 1 字也能對到（相似度 >= 0.8）', quest.resolve_npc(ns()) == (57, 48))
with_ocr([('碧青洞窟', 309), ('通過碧青9樓的挑戰', 341)])
ok &= check('步 2 / 7 同文字同 NPC（21208:30,16）→ 可判定', quest.resolve_npc(ns()) == (30, 16))
for nm, lines in [('說明文字對不到', [('碧青洞窟', 309), ('完全不相干的文字', 341)]),
                  ('讀不到說明行', [('碧青洞窟', 309)]),
                  ('標題不在這一頁', [('漆黑洞窟(一轉)', 309), ('找菲伊拿群青的水', 341)]),
                  ('兩步同文字但 NPC 不同（步 9 / 10）', [('碧青洞窟', 309), ('尋找水蒼洞窟賢者', 341)]),
                  ('OCR 整個空', [])]:
    with_ocr(lines)
    a_ = ns()
    r = quest.resolve_npc(a_)
    ok &= check(f'{nm} → None + 退出碼 31', r is None and a_.resolve_rc == quest.EXIT_STEP_UNKNOWN, f'r={r} rc={a_.resolve_rc}')
with_ocr([])
a_ = ns(step=9)
ok &= check('--step 9 不用 OCR → 賢者看門人 21308:20,10', quest.resolve_npc(a_) == (20, 10))
ok &= check('--step 99 不存在 → 31', quest.resolve_npc(ns(step=99)) is None)
a_ = ns(task='')
ok &= check('沒給 --task → None（退出碼 4）', quest.resolve_npc(a_) is None and a_.resolve_rc == 4)
a_ = ns(task='不存在的任務名xyz')
ok &= check('任務表找不到 → 31', quest.resolve_npc(a_) is None and a_.resolve_rc == 31)
print('(p1b) --npc auto 追蹤文字失敗 → 地圖反查（漆黑洞窟(二轉) 2005）')
_ev = []
quest.event = lambda m, shot=None: _ev.append(m)
with_ocr([])
quest.read_pos = lambda: (32020, 20, 10)
a_ = ns(task='漆黑洞窟(二轉)')
ok &= check('OCR 空 + 在 32020 → 步 4 帖拉所伊朵 20,9、npc_map 32020、事件 log 註明地圖反查', quest.resolve_npc(a_) == (20, 9) and a_.npc_map == 32020 and a_.step_no == 4 and any('地圖反查' in m for m in _ev), str(_ev))
with_ocr([('漆黑洞窟(二轉)', 309), ('亂七八糟的文字', 341)])
a_ = ns(task='漆黑洞窟(二轉)')
ok &= check('說明對不到任務表 + 在 32020 → 同樣用地圖反查', quest.resolve_npc(a_) == (20, 9))
with_ocr([])
quest.read_pos = lambda: (32021, 31, 50)
a_ = ns(task='漆黑洞窟(二轉)')
ok &= check('在 32021（步 5 / 6 兩步）→ 對應多個 → 31', quest.resolve_npc(a_) is None and a_.resolve_rc == quest.EXIT_STEP_UNKNOWN)
quest.read_pos = lambda: (1000, 50, 50)
a_ = ns(task='漆黑洞窟(二轉)')
ok &= check('在無關地圖 → 查不到 → 31', quest.resolve_npc(a_) is None and a_.resolve_rc == quest.EXIT_STEP_UNKNOWN)
quest.read_pos = lambda: None
a_ = ns(task='漆黑洞窟(二轉)')
ok &= check('讀不到所在地圖 → 31', quest.resolve_npc(a_) is None and a_.resolve_rc == quest.EXIT_STEP_UNKNOWN)
quest.read_pos = lambda: (32020, 20, 10)
a_ = ns(task='漆黑洞窟(二轉)', at='20,10')
ok &= check('給了 --at（地圖未知）→ 不用地圖反查 → 31', quest.resolve_npc(a_) is None and a_.resolve_rc == quest.EXIT_STEP_UNKNOWN)
quest.read_pos = lambda: (32010, 53, 30)
with_ocr([])
a_ = ns(task='漆黑洞窟(二轉)')
ok &= check('在 32010 → 步 2 守護獸 54,30', quest.resolve_npc(a_) == (54, 30))
quest.event = lambda m, shot=None: None
print('(p2) main：--fight --npc auto 讀不到步驟 → 退出碼 31，沒任何點擊')
with_ocr([('碧青洞窟', 309), ('亂七八糟', 341)])
s = Sim(battle_at=3.0)
rc = run(['--fight', '--npc', 'auto', '--task', '碧青洞窟', '--max-seconds', '30'], s)
ok &= check('exit 31 且沒點擊', rc == quest.EXIT_STEP_UNKNOWN and not s.clicks, f'rc={rc}')
s = Sim(battle_at=3.0)
rc = run(['--fight', '--step', '5', '--at', '57,47', '--task', '碧青洞窟', '--max-seconds', '30'], s)
ok &= check('--step 5（隱含 --npc auto）→ 通過隊伍檢查後點 NPC', rc == 0 and bool(s.clicks), f'rc={rc}')


# ---- 2026-10-10 外掛自動逃跑移除後新增：OCR 步驟比對 / 選擇對象面板 / 底部關閉列 / 刷新角色規則 ----
print('(q) --npc auto：OCR 把「9樓」讀成「婁」（2026-10-10 17:30 事故，相似度 0.67 → 退出碼 31）')
quest.event = lambda m, shot=None: None
INCIDENT = [('碧青洞窟', 309), ('通過碧青婁的', 341), ('通過碧青婁的扌覜戈', 341)]
with_ocr(INCIDENT)
quest.read_pos = lambda: (21208, 31, 16)
a_ = ns()
ok &= check('在 8 樓 21208 → 步 2（水的守護獸 30,16）', quest.resolve_npc(a_) == (30, 16) and a_.npc_map == 21208)
quest.read_pos = lambda: (21214, 30, 41)
a_ = ns()
ok &= check('在 14 樓 21214 → 步 3（NPC 不同的相似步驟，用所在地圖分辨）→ 30,40', quest.resolve_npc(a_) == (30, 40) and a_.npc_map == 21214)
quest.read_pos = lambda: (21215, 25, 31)
a_ = ns()
ok &= check('在第三張圖（兩個候選的地圖都不符）→ 31，不誤配', quest.resolve_npc(a_) is None and a_.resolve_rc == 31)
quest.read_pos = lambda: None
a_ = ns()
ok &= check('讀不到所在地圖 → 31', quest.resolve_npc(a_) is None and a_.resolve_rc == 31)
quest.read_pos = lambda: (21208, 31, 16)
a_ = ns(at='31,16')
ok &= check('手動給 --at（不知地圖）+ 相似步驟 NPC 不同 → 31', quest.resolve_npc(a_) is None and a_.resolve_rc == 31)
with_ocr([('碧青洞窟', 309), ('通過碧青9樓的', 341)])
quest.read_pos = lambda: None
ok &= check('被截斷但數字讀對「通過碧青9樓的」→ 步 2，不需要地圖', quest.resolve_npc(ns()) == (30, 16))
with_ocr([('碧青洞窟', 309), ('通過碧青14樓的', 341)])
ok &= check('被截斷「通過碧青14樓的」→ 步 3（30,40）', quest.resolve_npc(ns()) == (30, 40))
with_ocr([('碧青洞窟', 309), ('尋找水蒼洞窟賢', 341)])
quest.read_pos = lambda: (21308, 20, 11)
a_ = ns()
ok &= check('步 9 / 10 同文字同地圖、NPC 不同（賢者看門人 / 賢者）→ 仍 31（地圖分不出）', quest.resolve_npc(a_) is None and a_.resolve_rc == 31)
with_ocr([('碧青洞窟', 309), ('通過碧青婁的', 341)])
quest.read_pos = lambda: (21208, 31, 16)
ok &= check('step_score：完整相符 1.0 > 骨架相符；骨架相同的步 2/3 差 < 0.05（平手）',
            quest.step_score('通過碧青9樓的挑戰', '通過碧青9樓的挑戰') == 1.0 and abs(quest.step_score('通過碧青婁的', '通過碧青9樓的挑戰') - quest.step_score('通過碧青婁的', '通過碧青14樓的挑戰')) < 0.05)
ok &= check('step_score：太短的前綴（< 5 字）不當前綴用', quest.step_score('尋找女神', '尋找女神艾妮基') < 0.8)
ok &= check('step_score：不相干文字低分', quest.step_score('完全不相干的文字', '通過碧青9樓的挑戰') < 0.5)

print('(r) 選擇對象面板（樣本 tools/.cache/quest-log/172356-no-npc.png 離線算出的黃色色塊）')
SAMPLE_BLOBS = [dict(x=775, y=62, w=4, h=6, n=8), dict(x=720, y=292, w=7, h=9, n=22), dict(x=1353, y=265, w=4, h=3, n=6),
                dict(x=1171, y=331, w=14, h=4, n=21), dict(x=1208, y=337, w=15, h=15, n=50), dict(x=1138, y=337, w=11, h=14, n=37),
                dict(x=1154, y=337, w=15, h=14, n=71), dict(x=1189, y=336, w=2, h=7, n=10), dict(x=1193, y=335, w=2, h=6, n=9),
                dict(x=1131, y=338, w=5, h=9, n=18), dict(x=1172, y=339, w=15, h=11, n=41), dict(x=1185, y=342, w=5, h=5, n=15),
                dict(x=1193, y=342, w=9, h=4, n=19), dict(x=1174, y=364, w=4, h=3, n=8), dict(x=1264, y=364, w=5, h=3, n=7),
                dict(x=205, y=451, w=24, h=15, n=124), dict(x=261, y=582, w=18, h=18, n=233), dict(x=760, y=747, w=44, h=18, n=329)]
pt = quest.pick_select_card(SAMPLE_BLOBS)
ok &= check('黃字名字「水的守護獸」→ 點第 1 張卡片頭像（x≈1170、y≈289），場景 / UI 的黃色塊都不算', pt is not None and abs(pt[0] - 1171) <= 6 and abs(pt[1] - 289) <= 4, str(pt))
second = [dict(b, x=b['x'] + 90) for b in SAMPLE_BLOBS if 1100 < b['x'] < 1250 and 320 < b['y'] < 350]
pt2 = quest.pick_select_card(second)
ok &= check('NPC 在第 2 格（黃字右移 90）→ 點第 2 格，不寫死第一格', pt2 is not None and abs(pt2[0] - 1261) <= 6 and pt2[1] == pt[1], str(pt2))
row2 = [dict(b, y=b['y'] + 100) for b in SAMPLE_BLOBS if 1100 < b['x'] < 1250 and 320 < b['y'] < 350]
pt3 = quest.pick_select_card(row2)
ok &= check('NPC 在第 2 排（y+100）→ y 跟著下移', pt3 is not None and pt3[1] == pt[1] + 100, str(pt3))
ok &= check('沒有黃字（全是隊友白字）→ None，不亂點', quest.pick_select_card([b for b in SAMPLE_BLOBS if not (1100 < b['x'] < 1250 and 320 < b['y'] < 350)]) is None and quest.pick_select_card([]) is None)

SELECT_COL = {(x, y): (r, g, b) for x, y, r, g, b, *_ in quest.SIG_SELECT}
HUD_COL = {(x, y): (r, g, b) for x, y, r, g, b, *_ in quest.SIG_HUD}


def fake_pixel_gui(colors):
    return lambda *args, **k: ' '.join('%d,%d,%d' % colors.get(tuple(int(v) for v in p.split(',')), (60, 90, 60)) for p in args[1].split()) if args[0] == 'pixel' else ''


quest.gui = fake_pixel_gui({**SELECT_COL, **HUD_COL})
ok &= check('read_screen：選擇面板 + HUD 紅字 → state select（不是 idle）', REAL_READ_SCREEN()['state'] == 'select')
quest.gui = fake_pixel_gui(dict(HUD_COL))
ok &= check('read_screen：只有 HUD 紅字 → idle', REAL_READ_SCREEN()['state'] == 'idle')
quest.gui = fake_pixel_gui({**{k: v for k, v in list(SELECT_COL.items())[:-1]}, **HUD_COL})
ok &= check('read_screen：選擇面板少 1 點 → 不判 select', REAL_READ_SCREEN()['state'] == 'idle')

SELECT = dict(IDLE, state='select')
quest.ps_json = lambda script, *args: {'ok': True, 'blobs': SAMPLE_BLOBS}


def clicks_at(s, x, y):
    return [c for c in s.clicks if c[1] == f'click {x} {y}']


print('(r2) 對話步：點 NPC / 黃問號後跳出選擇面板 → 點黃字卡片，再按對話框')
s = Script([IDLE, SELECT, IDLE, DIALOG, IDLE, IDLE, IDLE, IDLE, IDLE])
rc = run2(['--no-track', '--stop-after-dialog', '--max-seconds', '60'], s)
card = [c for c in s.clicks if c[1].startswith('click 117')]
ok &= check('點了黃字卡片，之後按對話左鈕，exit 0', rc == 0 and len(card) == 1 and bool(has(s, 'click 948 461')) and s.clicks.index(card[0]) < s.clicks.index(has(s, 'click 948 461')[0]), f'rc={rc} {s.clicks}')
print('(r3) --fight：點 NPC 後跳出選擇面板（不是 22「沒點到 NPC」）；點了之後 NPC_WAIT 重新計時')
s = Script([IDLE] * 10 + [SELECT] + [IDLE] * 8 + [DIALOG] + [IDLE] * 20)
rc = run2(['--fight', '--npc', '53,17', '--at', '50,17', '--max-seconds', '120'], s)
ok &= check('有點卡片、有按對話左鈕、退出碼不是 22（沒面板處理的話第 12 秒就會 22）', bool(card_ := [c for c in s.clicks if c[1].startswith('click 117')]) and bool(has(s, 'click 948 461')) and rc != quest.EXIT_NO_NPC, f'rc={rc} {len(s.clicks)}')
print('(r4) 找不到黃字 → 不點任何卡片，當不認得，3 次 + 5 秒後退出碼 2（交給使用者）')
quest.ps_json = lambda script, *args: {'ok': True, 'blobs': []}
s = Script([SELECT])
rc = run2(['--no-track', '--max-seconds', '60'], s)
ok &= check('exit 2、沒點任何東西', rc == 2 and not s.clicks, f'rc={rc} {s.clicks}')
quest.ps_json = lambda script, *args: {'ok': True, 'blobs': SAMPLE_BLOBS}
print('(r5) 點了面板還在（連續 > SELECT_MAX_TRIES 輪）→ 不再一直點，改走不認得（退出碼 2）')
s = Script([SELECT])
rc = run2(['--no-track', '--max-seconds', '60'], s)
ok &= check(f'最多點 {quest.SELECT_MAX_TRIES} 次，exit 2', rc == 2 and len([c for c in s.clicks if c[1].startswith('click 117')]) == quest.SELECT_MAX_TRIES, f'rc={rc} n={len(s.clicks)}')

print('(s) 刷新角色單次嘗試（2026-10-13 改：不阻塞；底部「關閉」列只點一下、看切換鈕露出才點、看 waitpix 結果）')
ROW_BTN = {(x, y): (r, g, b) for x, y, r, g, b, *_ in quest.SIG_CLOSE_ROW}
SW_FULL = {(x, y): (r, g, b) for x, y, r, g, b, *_ in quest.SIG_SWITCH_FULL}
SW_MAIN = {(x, y): (r, g, b) for x, y, r, g, b, *_ in quest.SIG_SWITCH_MAIN}


class RowGame:
    """假遊戲（底部列 + 切換面板）：visible = 「關閉 + 頭像」列蓋著；點關閉 510,* 收起（eat = 前幾下被吃掉、stuck = 永遠收不掉、
    lag = 點中後還要再被讀幾次像素才消失）；列收起後切換鈕圖示露出（switch=False = 轉場 / 已回主畫面，圖示不在）；
    seq 點切換回 waitpix 結果（panel=True → ok、False → timeout），layout = 'full'（850,765）/ 'main'（763,760）"""

    def __init__(self, visible=True, eat=0, stuck=False, lag=0, switch=True, panel=True, layout='full'):
        self.visible, self.eat, self.stuck, self.clicks = visible, eat, stuck, []
        self.lag, self.pending = lag, False
        self.switch, self.panel, self.layout = switch, panel, layout

    def gui(self, *args, note=''):
        if args[0] == 'seq':
            self.clicks.append(args[1])
            if args[1].startswith('click 510 '):
                if self.eat > 0:
                    self.eat -= 1
                elif not self.stuck:
                    if self.lag:
                        self.pending = True
                    else:
                        self.visible = False
                return ''
            if 'waitpix' in args[1]:
                x, y = args[1].split(';')[0].split()[1:3]
                return f'click {x},{y}\n' + ('ok 120\nclick 910,578' if self.panel else 'timeout 1500\nskip click')
            return ''
        if args[0] == 'pixel':
            if self.pending:
                self.lag -= 1
                if self.lag <= 0:
                    self.visible, self.pending = False, False
            sw = SW_FULL if self.layout == 'full' else SW_MAIN
            out = []
            for p in args[1].split():
                xy = tuple(int(v) for v in p.split(','))
                if xy in ROW_BTN:
                    out.append(ROW_BTN[xy] if self.visible else (30, 120, 60))
                elif xy in quest.CLOSE_ROW_DARK:
                    out.append((50, 46, 37) if self.visible else (200, 200, 200))
                elif xy in sw and self.switch and not self.visible:
                    out.append(sw[xy])
                else:
                    out.append((0, 0, 0))
            return ' '.join('%d,%d,%d' % c for c in out)
        return ''


def n_close(g):
    return len([c for c in g.clicks if c.startswith('click 510 ')])


def n_switch(g, xy='850 765'):
    return len([c for c in g.clicks if c.startswith(f'click {xy}')])


for nm, g, want_close, want_switch, want in [
        ('有列、點一下就收 → 關閉 1 下後按切換，回 ok', RowGame(True), 1, 1, 'ok'),
        ('有列、點了沒收（被吃掉）→ 只點 1 下就回 row（不阻塞、不點切換）', RowGame(True, eat=1), 1, 0, 'row'),
        ('有列、收不掉 → 1 下、不點切換（會點到頭像）', RowGame(True, stuck=True), 1, 0, 'row'),
        ('收起動畫慢（點後讀 1 次才消失）→ 1 下後照按切換', RowGame(True, lag=1), 1, 1, 'ok'),
        ('沒有列、切換露出 → 不點關閉直接切換', RowGame(False), 0, 1, 'ok'),
        ('沒有列、切換鈕沒露出（轉場 / 已回主畫面 850,765 是組隊）→ 什麼都不點', RowGame(False, switch=False), 0, 0, 'notready'),
        ('切換後面板沒出現（waitpix timeout）→ 回 nopanel', RowGame(False, panel=False), 0, 1, 'nopanel'),
        ('有列 + 收起後切換鈕也不在（戰鬥剛結束）→ 不點切換', RowGame(True, switch=False), 1, 0, 'notready')]:
    quest.gui = g.gui
    r = quest.refresh_characters(True)
    ok &= check(nm, (n_close(g), n_switch(g), r) == (want_close, want_switch, want), f'{r} {g.clicks}')
g = RowGame(True, stuck=True)
quest.gui = g.gui
quest.refresh_characters(True, attempt=2)
ok &= check('第 3 次嘗試點關閉鈕的第 3 個點 510,725（輪流換點）', g.clicks == ['click 510 725; wait %d' % quest.CLOSE_ROW_SETTLE_MS], str(g.clicks))
g = RowGame(False, layout='main')
quest.gui = g.gui
r = quest.refresh_characters(False)
ok &= check('快速戰鬥（主畫面）刷新用 763,760、看主畫面版切換鈕', r == 'ok' and n_switch(g, '763 760') == 1 and not n_switch(g), str(g.clicks))
g = RowGame(False, layout='main')
quest.gui = g.gui
r = quest.refresh_characters(True)
ok &= check('完整戰鬥已結束回主畫面（850 版切換鈕不在，主畫面版在）→ 不點 850,765', r == 'notready' and not g.clicks, str(g.clicks))
quest.gui = lambda *a, **k: 'click 850,765' if a[0] == 'seq' else 'x'
ok &= check('像素讀不到 → 照舊直接按（seq 沒有 waitpix 結果 → unverified，算按到）', quest.refresh_characters(True) == 'unverified' and 'unverified' in quest.REFRESH_DONE)
quest.gui = RowGame(True).gui
ok &= check('close_row_visible：有列 True / 讀不到 None', quest.close_row_visible() is True and (setattr(quest, 'gui', lambda *a, **k: 'x') or quest.close_row_visible() is None))
for out, want in [('click 850,765\nok 230\nclick 910,578', 'ok'), ('click 850,765\ntimeout 1500\nskip click', 'timeout'), ('pwfail', 'pwfail'), ('', None), ('click 850,765', None)]:
    ok &= check(f'waitpix_result {out!r} → {want}', quest.waitpix_result(out) == want)
_bpx = {p: (0, 0, 0) for p in [(x, y) for x, y, *_ in quest.SIG_CLOSE_ROW] + quest.CLOSE_ROW_DARK + list(SW_FULL) + list(SW_MAIN)}
ok &= check('bottom_state：全黑 = other', quest.bottom_state(_bpx, True) == 'other' and quest.bottom_state(_bpx, False) == 'other')
ok &= check('bottom_state：850 版切換鈕 = switch（完整戰鬥）；主畫面版不算', quest.bottom_state(_bpx | SW_FULL, True) == 'switch' and quest.bottom_state(_bpx | SW_FULL, False) == 'other')
ok &= check('bottom_state：列在（切換鈕也像）= row 優先', quest.bottom_state(_bpx | SW_FULL | ROW_BTN | {p: (40, 40, 40) for p in quest.CLOSE_ROW_DARK}, True) == 'row')
ok &= check('bottom_state：關閉鈕在但右側頭像條不暗 = 不是 row', quest.bottom_state(_bpx | ROW_BTN | {p: (200, 200, 200) for p in quest.CLOSE_ROW_DARK}, True) == 'other')

print('(t) 刷新角色規則（should_refresh 純函式 + 整合）')
A = argparse.Namespace


def sr(a, boss, full=True, auto_off=False, since=99):
    return quest.should_refresh(a, boss, full, auto_off, since)


ok &= check('組隊預設：每場（路上遇敵 boss=False 也刷新）', sr(A(solo=False, fight=False, no_refresh=False), False))
ok &= check('--solo：任務戰鬥（boss）也不會有（solo 不當 boss）；路上小怪不刷新', not sr(A(solo=True, fight=False, no_refresh=False), False))
ok &= check('--fight：路上小怪不刷新、任務 / BOSS 戰刷新', not sr(A(solo=False, fight=True, no_refresh=False), False) and sr(A(solo=False, fight=True, no_refresh=False), True))
ok &= check('--no-refresh 全部不刷新', not sr(A(solo=False, fight=False, no_refresh=True), False) and not sr(A(solo=False, fight=True, no_refresh=True), True))
ok &= check('完整戰鬥自動戰鬥還關著 → 先不刷新；快速戰鬥沒有自動戰鬥鈕 → 照刷', not sr(A(solo=False, fight=False, no_refresh=False), False, True, True) and sr(A(solo=False, fight=False, no_refresh=False), False, False, False))
ok &= check('同一場未滿 REFRESH_GAP 秒不重刷、滿了才刷', not sr(A(solo=False, fight=False, no_refresh=False), False, since=quest.REFRESH_GAP - 0.5)
            and sr(A(solo=False, fight=False, no_refresh=False), False, since=quest.REFRESH_GAP))
QUICK = dict(IDLE, state='battle', full=False)
FULL_ON = {'state': 'battle', 'gold': 0, 'full': True, 'cmd': False, 'auto_off': False}
quest.gui = lambda *a, **k: ''
print('(t2) 預設模式整合：完整戰鬥（自動戰鬥先開、再刷新）/ 快速戰鬥 / 兩場各刷新一次')
s = Script([IDLE, FULL_CMD_OFF, FULL_CMD_OFF, FULL_ON, FULL_ON, FULL_ON, IDLE, IDLE, QUICK, QUICK, IDLE])   # 完整戰鬥要撐過 REFRESH_FIRST_DELAY=3.5 秒才按第一次
rc = run2(['--no-track', '--max-seconds', '13'], s)
seq = [c[1].split(';')[0] for c in s.clicks if c[1].startswith(('click 1380 600', 'click 850 765', 'click 763 760'))]
ok &= check('完整戰鬥：先按自動戰鬥、自動開了才刷新（850,765）一次；第二場快速戰鬥刷新（763,760）一次', seq == ['click 1380 600', 'click 850 765', 'click 763 760'], str(seq))
s = Script([IDLE, FULL_ON, IDLE, IDLE, IDLE])
rc = run2(['--no-track', '--no-refresh', '--max-seconds', '4'], s)
ok &= check('--no-refresh 預設模式不刷新', not has(s, 'click 850 765'))
print('(t3) --solo / --fight 快速戰鬥（只看到 VS 牌）：--solo 只能等；--fight 任務戰鬥刷新、路上小怪不刷新')
s = Script([IDLE, QUICK, QUICK, IDLE, IDLE, IDLE, IDLE])
rc = run2(['--solo', '--no-track', '--max-seconds', '6'], s)
ok &= check('--solo 快速戰鬥：不刷新也不逃（沒有點擊）', not s.clicks, str(s.clicks))
s = Script([IDLE, QUICK, QUICK, IDLE, IDLE, IDLE, IDLE])
rc = run2(['--fight', '--no-click', '--max-seconds', '6'], s)
ok &= check('--fight --no-click（任務時間窗內）快速戰鬥 → 刷新 763,760 一次', len(has(s, 'click 763 760')) == 1, str(s.clicks))
s = Script([IDLE] * 20 + [QUICK, QUICK, IDLE, IDLE, IDLE])
rc = run2(['--fight', '--no-click', '--max-seconds', '25'], s)
ok &= check('--fight --no-click 20 秒後的路上小怪（快速戰鬥）→ 不刷新', not has(s, 'click 763 760') and not has(s, 'click 850 765'), str(s.clicks))

print('(t4) 關閉列收不掉：同一場只點 CLOSE_ROW_MAX_CLICKS 次，之後只等不點（review §4.2）/ VS 牌卡死 → 42')
g = RowGame(True, stuck=True)
quest.gui = g.gui
ok &= check('click_row=False：列還在 → row_wait、零點擊', quest.refresh_characters(True, 5, click_row=False) == 'row_wait' and not g.clicks, str(g.clicks))
g = RowGame(False)
quest.gui = g.gui
ok &= check('click_row=False 但列已消失 → 照常按切換刷新', quest.refresh_characters(True, 5, click_row=False) == 'ok' and n_switch(g) == 1, str(g.clicks))
_rg = RowGame(True, stuck=True)


class RowScript(Script):
    def gui(self, *args, note=''):
        r = _rg.gui(*args, note=note)
        if args[0] == 'seq':
            self.clicks.append((round(self.t - 1000, 1), args[1]))
        return r


s = RowScript([IDLE] + [FULL_ON] * 25 + [IDLE] * 6)
rc = run2(['--no-track', '--max-seconds', '30'], s)
_nc = len([c for c in s.clicks if c[1].startswith('click 510 ')])
ok &= check(f'整合：完整戰鬥 25 秒列一直收不掉 → 關閉只點 {quest.CLOSE_ROW_MAX_CLICKS} 下（舊版每秒點一下）、不點切換', _nc == quest.CLOSE_ROW_MAX_CLICKS
            and not [c for c in s.clicks if c[1].startswith('click 850 765')], f'close={_nc} {s.clicks[:6]}')
s = Script([IDLE] + [QUICK] * 300)
rc = run2(['--no-track', '--max-seconds', '400'], s)
ok &= check(f'快速戰鬥 VS 牌 {quest.VS_STUCK_S:.0f} 秒沒結束 → 退出碼 42（呼叫端重登）', rc == quest.EXIT_VS_STUCK == 42 and quest.VS_STUCK_S <= s.t - 1000 <= quest.VS_STUCK_S + 3, f'rc={rc} t={s.t - 1000:.1f}')
s = Script([IDLE, FULL_ON] + [FULL_ON] * 120 + [IDLE] * 6)
rc = run2(['--no-track', '--max-seconds', '200', '--no-refresh'], s)
ok &= check('完整戰鬥打很久（120 秒）不算 VS 卡死', rc != quest.EXIT_VS_STUCK, f'rc={rc}')


print('(A) BOSS 戰判斷輸贏（errlog #25）：judge_boss_result 純函式')
J = quest.judge_boss_result
P = (5510, 50, 17)
ok &= check('#25 實例：同圖 5510、步驟仍是打敗龍王守衛、HP 1/551（0%）、少一人 → 32（隊伍優先）', J(P, P, 6, 6, 0, False)[0] == quest.EXIT_TEAM_LOST)
c, why = J(P, P, 6, 6, 0, True)
ok &= check('同上但隊伍完整 → 35，理由帶 HP 佐證', c == quest.EXIT_BOSS_LOST and 'HP 0%' in why, f'{c} {why}')
ok &= check('同圖同步驟、HP 正常 → 仍 35（HP 只是佐證）', J(P, P, 6, 6, 80, True)[0] == 35)
ok &= check('地圖換了 → 0', J(P, (5511, 3, 3), 6, 6, 50, True)[0] == 0)
ok &= check('地圖相同、步驟 6 → 7 → 0', J(P, P, 6, 7, 50, True)[0] == 0)
ok &= check('任務從列表消失（GONE）→ 0', J(P, P, 6, quest.GONE, 50, True)[0] == 0)
ok &= check('只給座標沒步驟（沒 --task）、地圖相同 → 36，不回 0', J(P, P, None, None, 50, True)[0] == quest.EXIT_BOSS_UNKNOWN)
ok &= check('OCR 讀不到打完後步驟、地圖相同 → 36', J(P, P, 6, None, 50, True)[0] == 36)
ok &= check('打完後讀不到座標、步驟相同 → 36', J(P, None, 6, 6, 50, True)[0] == 36)
ok &= check('讀不到座標但步驟變了 → 0', J(None, None, 6, 7, 50, True)[0] == 0)
ok &= check('被打飛回村（1000 儲存點）→ 21，不當成「地圖換了」贏', J((5510, 50, 17), (1000, 93, 99), 6, 6, 50, True)[0] == quest.EXIT_KNOCKED)
ok &= check('team_ok=None（讀不到）不擋判斷', J(P, (5511, 1, 1), 6, 6, 50, None)[0] == 0)
ok &= check('退出碼 33~36 互不重複、不與舊碼衝突', len({quest.EXIT_NO_PROGRESS, quest.EXIT_NPC_MAP, quest.EXIT_BOSS_LOST, quest.EXIT_BOSS_UNKNOWN, 20, 21, 22, 23, 24, 25, 26, 30, 31, 32}) == 14)

print('(A2) --fight 整合：BOSS 戰打完閒置後的退出碼')
quest.event = lambda m, shot=None: print(f'   {m}')
quest.stat = lambda: {'hp': 1, 'hpPct': 0}
quest.read_step_no = lambda task, fn=None: STEP_FN()
STEP_FN = lambda: 5
BASE = ['--fight', '--step', '5', '--at', '57,47', '--task', '碧青洞窟', '--max-seconds', '60']
s = Sim(battle_at=3.0)
rc = run(BASE, s, real_verify=True)
ok &= check('地圖與步驟都沒變（HP 1）→ 35，不是 0', rc == quest.EXIT_BOSS_LOST, f'rc={rc}')
STEP_FN = lambda: 6
s = Sim(battle_at=3.0)
rc = run(BASE, s, real_verify=True)
ok &= check('步驟 5 → 6 → 0', rc == 0, f'rc={rc}')
STEP_FN = lambda: 5
s = Sim(battle_at=3.0)
POS_FN = lambda: (5510, 50, 17) if s.t < 1012 else (5511, 9, 9)
rc = run(BASE, s, real_verify=True)
ok &= check('打完換地圖 → 0', rc == 0, f'rc={rc}')
POS_FN = lambda: (5510, 50, 17)
s = Sim(battle_at=3.0)
TEAM['after'] = (False, '少一人')
rc = run(BASE, s, real_verify=True)
ok &= check('打完隊伍少一人 → 32', rc == quest.EXIT_TEAM_LOST, f'rc={rc}')
del TEAM['after']
s = Sim(battle_at=3.0)
rc = run(['--fight', '--npc', '50,18', '--at', '50,17', '--max-seconds', '60'], s, real_verify=True)
ok &= check('--npc X,Y 沒 --task（讀不到步驟）→ 36，不回 0', rc == quest.EXIT_BOSS_UNKNOWN, f'rc={rc}')
s = Sim(battle_at=3.0)
STEP_FN = lambda: 5
rc = run(['--fight', '--npc', '50,18', '--at', '50,17', '--task', '碧青洞窟', '--max-seconds', '60'], s, real_verify=True)
ok &= check('--npc X,Y + --task：點前補讀步驟 5、打完仍 5、同圖 → 35', rc == quest.EXIT_BOSS_LOST, f'rc={rc}')


print('(B) 對話無進展：卡坦事故（同一黃問號 722,318 循環）')
ok &= check('SELECT_LOOP_MAX / EXIT_SELECT_LOOP = 29（對話 ↔ 選擇面板循環保護）', quest.SELECT_LOOP_MAX == 6 and quest.EXIT_SELECT_LOOP == 29)
ok &= check('stalled 純函式：輪數 >= STALL_MAX 且同標記才停', quest.STALL_MAX == 4 and not quest.stalled(3, True) and quest.stalled(4, True) and not quest.stalled(10, False))
MK = lambda: {'x': 722, 'y': 318, 'w': 12, 'h': 14, 'n': 90}
CYCLE = [IDLE, DIALOG, DIALOG]        # 主迴圈 idle → 點黃問號 → 反應迴圈看到對話 → 主迴圈對話（按左鈕）→ 下一輪 idle
TAIL = [IDLE] * 3
NOTRACK = lambda *a, **k: False          # 黃問號用完 / 領獎後掃追蹤列表：找不到（不影響判斷）


def lclicks(s):
    return len(has(s, 'click 948 461'))


def mclicks(s):
    return len([c for c in s.clicks if 'click 722' in c[1]])


s = Script(CYCLE * 30)
rc = run2(['--task', '卡坦的願望', '--max-seconds', '300'], s, marker=MK, track=NOTRACK)
ok &= check('第 4 輪對話停手：退出碼 33，只按了 3 次左鈕（第 4 次不按）、點黃問號 4 次', rc == quest.EXIT_NO_PROGRESS and lclicks(s) == 3 and mclicks(s) == 4, f'rc={rc} 左鈕={lclicks(s)} 問號={mclicks(s)}')
mks = iter([{'x': 722 + 40 * (i % 2), 'y': 318, 'w': 12, 'h': 14, 'n': 90} for i in range(200)])
s = Script(CYCLE * 12 + TAIL)
rc = run2(['--task', '卡坦的願望', '--max-seconds', '120'], s, marker=lambda: next(mks), track=NOTRACK)
ok &= check('黃問號座標每輪換（差 > 10px）→ 輪數歸零，不誤停', rc != quest.EXIT_NO_PROGRESS and lclicks(s) == 12, f'rc={rc} 左鈕={lclicks(s)}')
s = Script(CYCLE * 2 + [IDLE, DIALOG, DIALOG, REWARD, IDLE, IDLE, IDLE] + CYCLE * 3 + TAIL)
rc = run2(['--task', '卡坦的願望', '--max-seconds', '60'], s, marker=MK, track=NOTRACK)
ok &= check('中間領獎 → 歸零：前 3 輪 + 領獎 + 3 輪 = 不停（沒有 33）', rc != quest.EXIT_NO_PROGRESS, f'rc={rc} 左鈕={lclicks(s)}')
s = Script(CYCLE * 3 + [WALK, IDLE] + CYCLE * 3 + TAIL)
rc = run2(['--task', '卡坦的願望', '--max-seconds', '60'], s, marker=MK, track=NOTRACK)
ok &= check('中間 Auto Walking → 歸零', rc != quest.EXIT_NO_PROGRESS and lclicks(s) == 6, f'rc={rc} 左鈕={lclicks(s)}')
s = Script(CYCLE * 3 + [FULL_ON, FULL_ON, IDLE, IDLE] + CYCLE * 3 + TAIL)
rc = run2(['--task', '卡坦的願望', '--max-seconds', '60', '--no-stop-after-boss'], s, marker=MK, track=NOTRACK)
ok &= check('中間戰鬥 → 歸零', rc != quest.EXIT_NO_PROGRESS and lclicks(s) == 6, f'rc={rc} 左鈕={lclicks(s)}')
maps = iter([(m, 1, 1) for m in range(1, 100) for _ in range(3)])
s = Script(CYCLE * 7 + TAIL)
rc = run2(['--task', '卡坦的願望', '--max-seconds', '60'], s, marker=MK, pos=lambda: next(maps), track=NOTRACK)
ok &= check('每次進對話都換了地圖 → 歸零，不停', rc != quest.EXIT_NO_PROGRESS and lclicks(s) == 7, f'rc={rc} 左鈕={lclicks(s)}')
s = Script([DIALOG] * 8 + TAIL)
rc = run2(['--task', '卡坦的願望', '--no-track', '--max-seconds', '40'], s)
ok &= check('多頁對話（連續 8 頁，中間沒閒置）→ 不誤停，每頁都按左鈕', rc == 0 and lclicks(s) == 8, f'rc={rc} 左鈕={lclicks(s)}')
s = Script([DIALOG, IDLE] * 7 + TAIL)
rc = run2(['--task', '卡坦的願望', '--no-track', '--max-seconds', '40'], s)
ok &= check('多頁對話頁與頁之間閃過 1 格閒置（沒點問號、閒置 < 2.5 秒）→ 不誤停', rc == 0 and lclicks(s) == 7, f'rc={rc} 左鈕={lclicks(s)}')


print('(D) 預設模式：BOSS 戰結束就停（errlog #68）+ 不可逆對話防護')
BATTLE = dict(FULL_CMD_OFF, cmd=False, auto_off=False)
BOSS_SEQ = [IDLE, DIALOG, BATTLE, BATTLE, IDLE, IDLE, IDLE, IDLE, IDLE]     # 對話後 1 秒內開打 = 任務戰；之後閒置 2.5 秒確認
TEAM['ret'] = (True, 'fake 滿 5 人')
TEAM['calls'].clear()
TEAM.pop('after', None)
s = Script(BOSS_SEQ)
rc = run2(['--no-track', '--max-seconds', '60'], s, team=True)
ok &= check('一般任務（沒 --boss-team-check，2026-10-17）：任務戰打完不停、不開切換面板（只有開始前），rc 0', rc == 0 and [t for _, t in TEAM['calls']] == ['開始前：'], f'rc={rc} {TEAM["calls"]}')
TEAM['calls'].clear()
s = Script(BOSS_SEQ)
rc = run2(['--no-track', '--max-seconds', '60', '--boss-team-check'], s, team=True)
ok &= check('任務戰打完 + 滿 5 人 → 37，BOSS 戰後驗過隊伍、沒點追蹤 / 黃問號', rc == quest.EXIT_BOSS_DONE and any(t.startswith('BOSS 戰後') for _, t in TEAM['calls']) and not any('click 722' in c[1] for c in s.clicks), f'rc={rc} {TEAM["calls"]}')
TEAM['ret'] = (True, 'x')
TEAM['after'] = (False, '隊長 DKBO、隊員 [DKBO2]、不在隊 [DKBO3, DKBO4, DKBO5]')
s = Script(BOSS_SEQ)
rc = run2(['--no-track', '--max-seconds', '60', '--boss-team-check'], s, team=True)
ok &= check('任務戰打完 + 隊伍不滿 → 38（不是 37、不是 0）', rc == quest.EXIT_BOSS_TEAM, f'rc={rc}')
TEAM['after'] = (None, '切換面板沒打開')
s = Script(BOSS_SEQ)
rc = run2(['--no-track', '--max-seconds', '60', '--boss-team-check'], s, team=True)
ok &= check('隊伍檢查讀不到 → 38（保守）', rc == quest.EXIT_BOSS_TEAM, f'rc={rc}')
del TEAM['after']
s = Script([IDLE, DIALOG, BATTLE, BATTLE, DIALOG, DIALOG] + [IDLE] * 4)
rc = run2(['--no-track', '--max-seconds', '60', '--no-stop-after-boss', '--team-size', '0'], s)
ok &= check('--no-stop-after-boss：不停，連跑到下一段對話（共 3 次按左鈕）', rc == 0 and lclicks(s) == 3, f'rc={rc} 左鈕={lclicks(s)}')
s = Script([IDLE] * 3 + [BATTLE, BATTLE] + [IDLE] * 6)
rc = run2(['--no-track', '--max-seconds', '60'], s)
ok &= check('一般遇敵（沒有對話 / 黃問號在前）→ 不停（rc 0 時間到）', rc == 0, f'rc={rc}')
s = Script([DIALOG, WALK, BATTLE, BATTLE] + [IDLE] * 6)
rc = run2(['--no-track', '--max-seconds', '60'], s)
ok &= check('對話後又 Auto Walking、之後遇敵 = 路上小怪 → 不停', rc == 0, f'rc={rc}')
s = Script([DIALOG, IDLE, IDLE] + [IDLE] * 8)
# 對話後 20 秒才開打（超過 QUEST_BATTLE_WINDOW）
s = Script([DIALOG] + [IDLE] * 20 + [BATTLE, BATTLE] + [IDLE] * 6)
rc = run2(['--no-track', '--max-seconds', '90', '--no-marker'], s)
ok &= check('對話後超過 15 秒才開打 → 不算 BOSS，不停', rc == 0, f'rc={rc}')
s = Script(BOSS_SEQ)
rc = run2(['--no-track', '--max-seconds', '60', '--team-size', '0', '--boss-team-check'], s)
ok &= check('--boss-team-check --team-size 0（不驗隊伍）：BOSS 戰後仍停 37，事件註明未檢查', rc == quest.EXIT_BOSS_DONE, f'rc={rc}')
s = Script([DIALOG, BATTLE, BATTLE, IDLE, IDLE, IDLE, IDLE])
rc = run2(['--fight', '--no-click', '--no-track', '--max-seconds', '60', '--team-size', '0'], s, real_verify=False)
ok &= check('--fight 不受影響（照舊回 verify_boss_result 的 0，不是 37）', rc == 0, f'rc={rc}')

print('--- 不可逆對話防護')
ok &= check('find_irreversible：關鍵字命中 / 空白容忍 / 無害文字不中', quest.find_irreversible(['進行轉 生的儀式']) == ['轉生'] and quest.find_irreversible(['完成', '再見']) == [] and '封印' in quest.find_irreversible(['使用封印書']) and set(quest.IRREVERSIBLE_KEYWORDS) >= {'轉生', '寵物轉生', '封印', '刪除', '丟棄'})
ok &= check('find_irreversible：挑戰機暴(轉生任務) 放行（含全形括號 / 空白），其他轉生字樣照擋', quest.find_irreversible(['hello welcome to be here!', '挑戰機暴(轉生任務)', '再見']) == [] and quest.find_irreversible(['挑戰機暴（轉生 任務)']) == [] and quest.find_irreversible(['挑战机暴转生任务']) == [] and quest.find_irreversible(['進行轉生的儀式', '挑戰機暴(轉生任務)']) == ['轉生'])
RB = {'body': ['你真是厲害，居然打敗了帖拉所伊朵來到我這裏。', '那我就如你所願，來進行轉生的儀式吧。'], 'buttons': ['完成', '再見'], 'body_ok': True}
for name, texts in (('內文含轉生、按鈕只寫「完成」（精靈王第 2 頁實況）', RB),
                    ('按鈕含「寵物轉生」', {'body': ['你想做什麼'], 'buttons': ['寵物轉生', '再見'], 'body_ok': True}),
                    ('內文含「丟棄」', {'body': ['確定要丟棄嗎'], 'buttons': ['完成', '再見'], 'body_ok': True}),
                    ('內文讀不到（OCR 失敗，重讀 2 次仍讀不到）→ 保守不按', {'body': [], 'buttons': ['完成', '再見'], 'body_ok': False})):
    DLG.clear(); DLG.update(texts)
    s = Script([DIALOG, DIALOG, DIALOG, IDLE, IDLE, IDLE, IDLE])
    rc = run2(['--no-track', '--max-seconds', '60', '--team-size', '0'], s)
    ok &= check(f'{name} → 39、沒按左鈕', rc == quest.EXIT_IRREVERSIBLE and lclicks(s) == 0, f'rc={rc} 左鈕={lclicks(s)}')
DLG.clear(); DLG.update(RB)
s = Script([DIALOG, DIALOG, IDLE, IDLE, IDLE, IDLE])
rc = run2(['--no-track', '--max-seconds', '60', '--team-size', '0', '--allow-irreversible'], s)
ok &= check('--allow-irreversible 放行：照按（兩頁都按、rc 0）', rc == 0 and lclicks(s) == 2, f'rc={rc} 左鈕={lclicks(s)}')
n0 = len(DLG_READS)
ok &= check('--allow-irreversible 不做 OCR（read_dialog_texts 沒被呼叫）', len(DLG_READS) == n0)
DLG.clear(); DLG.update({'body': ['hello welcome to be here!'], 'buttons': ['漆黑洞窟', '再見'], 'body_ok': True})
s = Script([DIALOG, IDLE, IDLE, IDLE, IDLE])
rc = run2(['--no-track', '--max-seconds', '60', '--team-size', '0'], s)
ok &= check('精靈王第 1 頁（無關鍵字）照按', rc == 0 and lclicks(s) == 1, f'rc={rc} 左鈕={lclicks(s)}')
DLG.clear(); DLG.update({'body': ['你要進入裏面嗎？那趕緊通過吧！'], 'buttons': ['完成', '再見'], 'body_ok': True})

print('--- 讀不到對話框內文 → 先重讀再判 39（2026-10-17 p3 火的守護獸 OCR 偶發誤擋）')
UNREAD = {'body': [], 'buttons': [], 'body_ok': False}
SAFE = {'body': ['你要進入裏面嗎？那趕緊通過吧！'], 'buttons': ['完成', '再見'], 'body_ok': True}
BASEARGS = ['--no-track', '--max-seconds', '60', '--team-size', '0']
DLG.clear(); DLG.update(SAFE)
DLG_SEQ[:] = [UNREAD]; DLG_ZOOMS.clear()
s = Script([DIALOG, DIALOG, IDLE] + [IDLE] * 4)
n0 = len(DLG_READS)
rc = run2(BASEARGS, s)
ok &= check('讀不到內文、重讀第 1 次讀到 → 照常按（OCR 2 次、左鈕 1 次、rc 0）', rc == 0 and lclicks(s) == 1 and len(DLG_READS) - n0 == 2, f'rc={rc} 左鈕={lclicks(s)} OCR={len(DLG_READS) - n0}')
ok &= check('重讀換倍率（第 1 次預設、重讀用 DIALOG_RETRY_ZOOMS[0]）', DLG_ZOOMS == [None, quest.DIALOG_RETRY_ZOOMS[0]], str(DLG_ZOOMS))
DLG_SEQ[:] = [UNREAD, UNREAD]
s = Script([DIALOG, DIALOG, DIALOG, IDLE] + [IDLE] * 4)
n0 = len(DLG_READS)
rc = run2(BASEARGS, s)
ok &= check('讀不到內文、重讀第 2 次才讀到 → 照常按（OCR 3 次、左鈕 1 次）', rc == 0 and lclicks(s) == 1 and len(DLG_READS) - n0 == 3, f'rc={rc} 左鈕={lclicks(s)} OCR={len(DLG_READS) - n0}')
DLG_SEQ[:] = [UNREAD, UNREAD, UNREAD]
s = Script([DIALOG, DIALOG, DIALOG, IDLE] + [IDLE] * 4)
n0 = len(DLG_READS)
rc = run2(BASEARGS, s)
ok &= check('三次都讀不到（第 1 次 + 重讀 2 次）→ 39、沒按', rc == quest.EXIT_IRREVERSIBLE and lclicks(s) == 0 and len(DLG_READS) - n0 == 1 + quest.DIALOG_UNREAD_RETRIES, f'rc={rc} 左鈕={lclicks(s)} OCR={len(DLG_READS) - n0}')
DLG_SEQ[:] = [{'body': ['確定要丟棄嗎'], 'buttons': ['完成', '再見'], 'body_ok': True}]
s = Script([DIALOG, DIALOG, DIALOG, IDLE] + [IDLE] * 4)
n0 = len(DLG_READS)
rc = run2(BASEARGS, s)
ok &= check('命中不可逆關鍵字 → 不重讀、立刻 39（OCR 1 次）', rc == quest.EXIT_IRREVERSIBLE and lclicks(s) == 0 and len(DLG_READS) - n0 == 1, f'rc={rc} OCR={len(DLG_READS) - n0}')
DLG_SEQ[:] = [UNREAD, {'body': ['使用封印書'], 'buttons': ['完成', '再見'], 'body_ok': True}]
s = Script([DIALOG, DIALOG, IDLE] + [IDLE] * 4)
rc = run2(BASEARGS, s)
ok &= check('讀不到 → 重讀讀到關鍵字 → 39、沒按', rc == quest.EXIT_IRREVERSIBLE and lclicks(s) == 0, f'rc={rc} 左鈕={lclicks(s)}')
DLG_SEQ[:] = [UNREAD]
s = Script([DIALOG, IDLE] + [IDLE] * 6)
n0 = len(DLG_READS)
rc = run2(BASEARGS, s)
ok &= check('讀不到 → 重讀前對話框已關 → 不按、不 39，回主迴圈（rc 0、OCR 1 次）', rc == 0 and lclicks(s) == 0 and len(DLG_READS) - n0 == 1, f'rc={rc} 左鈕={lclicks(s)} OCR={len(DLG_READS) - n0}')
DLG_SEQ[:] = []

print('--- 快速連按對話框（--fast-dialog，2026-10-17 改無腦第二下）')
_REAL_FP = quest.read_dialog_fp
_fp_calls = []
quest.read_dialog_fp = lambda: _fp_calls.append(1) or None
FASTARGS = BASEARGS + ['--fast-dialog']
DLG.clear(); DLG.update(SAFE)
s = Script([DIALOG, IDLE] + [IDLE] * 4)
n0 = len(DLG_READS)
rc = run2(FASTARGS, s)
ok &= check('fast：OCR 過的頁按完 → 隔 FAST_DIALOG_GAP 無腦再按 1 次（左鈕 2 次、OCR 1 次、不讀指紋）', rc == 0 and lclicks(s) == 2 and len(DLG_READS) - n0 == 1 and not _fp_calls, f'rc={rc} 左鈕={lclicks(s)} OCR={len(DLG_READS) - n0} 指紋={len(_fp_calls)}')
gaps = [round(b[0] - a_[0], 1) for a_, b in zip(has(s, 'click 948 461'), has(s, 'click 948 461')[1:])]
ok &= check('fast：兩下間隔 = FAST_DIALOG_GAP 1.0 秒', gaps == [quest.FAST_DIALOG_GAP], str(gaps))
s = Script([DIALOG, DIALOG, DIALOG, IDLE] + [IDLE] * 4)
n0 = len(DLG_READS)
rc = run2(FASTARGS, s)
ok &= check('fast：每次主迴圈看到對話框都照舊 OCR（3 次讀到 dialog → OCR 3 次、左鈕 6 次）', rc == 0 and lclicks(s) == 6 and len(DLG_READS) - n0 == 3, f'rc={rc} 左鈕={lclicks(s)} OCR={len(DLG_READS) - n0}')
s = Script([DIALOG] * 30)
quest.read_screen, quest.gui = s.screen, s.gui
quest.time.time, quest.time.sleep = s.time, s.sleep
i0 = s.i
n, why = quest.fast_dialog_chain(None, 1)
ok &= check('fast_dialog_chain：只按 1 次、不讀畫面（read_screen 沒被呼叫）', n == 1 and lclicks(s) == 1 and s.i == i0 and abs(s.t - 1000 - quest.FAST_DIALOG_GAP) < 1e-9, f'{n} {why} 讀畫面 {s.i - i0}')
s = Script([DIALOG, DIALOG, DIALOG, IDLE] + [IDLE] * 4)
n0 = len(DLG_READS)
rc = run2(BASEARGS, s)
ok &= check('非 fast（沒帶旗標）：每頁照舊 OCR、不補按（3 頁 3 次）', lclicks(s) == 3 and len(DLG_READS) - n0 == 3, f'左鈕={lclicks(s)} OCR={len(DLG_READS) - n0}')
DLG.clear(); DLG.update({'body': ['要接這個任務嗎'], 'buttons': ['接受', '再見'], 'body_ok': True})
s = Script([DIALOG, DIALOG, IDLE] + [IDLE] * 4)
n0 = len(DLG_READS)
rc = run2(FASTARGS, s)
ok &= check('fast：剛 OCR 那頁按鈕是「接受」→ 不補按（每頁 OCR）', lclicks(s) == 2 and len(DLG_READS) - n0 == 2, f'左鈕={lclicks(s)} OCR={len(DLG_READS) - n0}')
DLG.clear(); DLG.update(RB)
s = Script([DIALOG, DIALOG, IDLE] + [IDLE] * 4)
rc = run2(FASTARGS, s)
ok &= check('fast：第 1 頁含轉生 → 照擋 39、沒按（防護不受 fast 影響）', rc == quest.EXIT_IRREVERSIBLE and lclicks(s) == 0, f'rc={rc}')
DLG.clear(); DLG.update(SAFE)
s = Script([DIALOG, DIALOG, IDLE] + [IDLE] * 4)
rc = run2(FASTARGS + ['--allow-irreversible'], s)
ok &= check('fast + --allow-irreversible → 不快（照主迴圈每頁按 1 次）', lclicks(s) == 2, f'左鈕={lclicks(s)}')
quest.read_dialog_fp = _REAL_FP

# read_dialog_texts：用假 ps_json 驗證兩塊區域與參數；內文失敗會重試
_calls = []
def _fake_ps(script, *args):
    _calls.append((script,) + args)
    return {'ok': True, 'lines': [{'text': '轉生', 'x': 1, 'y': 1}] if '-Light' in args else [{'text': '完成', 'x': 1, 'y': 1}]}
_keep_ps, _keep_rdt = quest.ps_json, quest.read_dialog_texts
quest.ps_json, quest.read_dialog_texts = _fake_ps, REAL_READ_DLG
t = quest.read_dialog_texts()
ok &= check('read_dialog_texts：內文用 -Light、按鈕用 -Dark，各一次', t == {'body': ['轉生'], 'buttons': ['完成'], 'body_ok': True} and sum('-Light' in c for c in _calls) == 1 and sum('-Dark' in c for c in _calls) == 1, str(_calls))
_calls.clear()
quest.ps_json = lambda script, *args: (_calls.append(args) or {'ok': False})
quest.time.sleep = lambda d: None
t = quest.read_dialog_texts()
ok &= check('內文讀不到：重試 DIALOG_OCR_TRIES 次後 body_ok False', not t['body_ok'] and sum('-Light' in c for c in _calls) == quest.DIALOG_OCR_TRIES, str(_calls))
quest.ps_json, quest.read_dialog_texts = _keep_ps, _keep_rdt

print('(C) --npc-map / 反查 NPC 地圖：不同圖 → 退出碼 34；非戰鬥步警告')
ok &= check('npc_map_of_xy：碧青洞窟 (57,48) → 30305；不存在座標 → None', quest.npc_map_of_xy('碧青洞窟', (57, 48)) == 30305 and quest.npc_map_of_xy('碧青洞窟', (1, 1)) is None)
POS_FN = lambda: (5510, 50, 17)
s = Sim(battle_at=3.0)
rc = run(['--fight', '--npc', '57,48', '--npc-map', '30305', '--max-seconds', '30'], s)
ok &= check('--npc X,Y --npc-map（目前 5510、NPC 30305）→ 34，沒點 NPC', rc == quest.EXIT_NPC_MAP and not has(s, 'click 1215'), f'rc={rc} {s.clicks}')
s = Sim(battle_at=3.0)
rc = run(['--fight', '--npc', '57,48', '--task', '碧青洞窟', '--max-seconds', '30'], s)
ok &= check('--npc X,Y + --task 反查地圖 30305 → 34', rc == quest.EXIT_NPC_MAP and not s.clicks, f'rc={rc} {s.clicks}')
s = Sim(battle_at=3.0)
rc = run(['--fight', '--step', '5', '--task', '碧青洞窟', '--max-seconds', '30'], s)
ok &= check('--npc auto / --step 5 不同圖 → 34（不再是 4）', rc == quest.EXIT_NPC_MAP, f'rc={rc}')
POS_FN = lambda: (30305, 57, 47)
s = Sim(battle_at=3.0)
rc = run(['--fight', '--npc', '57,48', '--task', '碧青洞窟', '--max-seconds', '30'], s)
ok &= check('同一張圖照常點 NPC', rc != quest.EXIT_NPC_MAP and bool(s.clicks), f'rc={rc}')
POS_FN = lambda: (5510, 50, 17)
EV = []
quest.event = lambda m, shot=None: EV.append(m)
quest.warn_not_battle(next(t for t in quest.walk.psa.task_steps('碧青洞窟')[1] if t.get('step') == 6))
quest.warn_not_battle(next(t for t in quest.walk.psa.task_steps('碧青洞窟')[1] if t.get('step') == 5))
ok &= check('步 6（對話）警告、步 5（戰鬥）不警告', len(EV) == 1 and '第 6 步不是戰鬥步' in EV[0], str(EV))
quest.event = lambda m, shot=None: print(f'   {m}')

# ---- ps_json：唯讀逾時回 {'ok': False}、rc=125 寫警告 ----
import subprocess as _sp, types as _ty
_real_run_ps, _real_log = quest.winenv.run_ps, quest.log
_LOGS = []
quest.ps_json = _REAL_PS_JSON
quest.log = lambda m, act=True: _LOGS.append(m)
def _raise(*a, **k): raise _sp.TimeoutExpired('ps', 1)
quest.winenv.run_ps = _raise
r = quest.ps_json('ocr.ps1', 1, 2, 3, 4)
ok &= check('ps_json 唯讀逾時 → ok False、不丟例外', r.get('ok') is False and any('逾時' in m for m in _LOGS), str(r))
_LOGS.clear()
quest.winenv.run_ps = lambda *a, **k: _ty.SimpleNamespace(returncode=125, stdout='', stderr='boom')
r = quest.ps_json('findmark.ps1')
ok &= check('ps_json rc=125 → 寫警告、ok False', r.get('ok') is False and any('rc=125' in m for m in _LOGS), str(r))
quest.winenv.run_ps = lambda *a, **k: _ty.SimpleNamespace(returncode=0, stdout='noise\n{"ok": true, "lines": []}\n', stderr='')
ok &= check('ps_json 正常解析', quest.ps_json('ocr.ps1').get('ok') is True)
quest.winenv.run_ps, quest.log = _real_run_ps, _real_log


# ---- 2026-10-11 冗餘修正（馬祖快遞 16:29～16:39）----
print('(W) 自動走路不計入 --max-seconds：WalkClock 純函式 + 整合')
wc = quest.WalkClock(10, 0.0)
for t in range(1, 401):
    wc.tick('walking', float(t))
ok &= check('WalkClock：連續巡路 400 秒（cap 900）→ 一直沒到時限、walked 約 399', not wc.expired(400.0) and 398 <= wc.walked <= 400, f'walked={wc.walked}')
for t in range(401, 411):
    wc.tick('idle', float(t))
ok &= check('WalkClock：之後連續閒置 10 秒才到時限', wc.expired(410.5) and not wc.expired(405.0), f'end={wc.end}')
wc = quest.WalkClock(10, 0.0)
seq_ = ['walking', 'walking', 'unknown', 'walking', 'unknown', 'unknown', 'walking', 'walking']
for i, st_ in enumerate(seq_, 1):
    wc.tick(st_, float(i))
ok &= check('WalkClock：巡路中途 unknown 1～2 次又回 walking 仍算巡路（時限不縮）', abs(wc.end - (10 + len(seq_) - 1)) < 1e-6, f'end={wc.end}')
wc = quest.WalkClock(10, 0.0)
for i, st_ in enumerate(['walking', 'walking', 'unknown', 'unknown', 'unknown', 'unknown'], 1):
    wc.tick(st_, float(i))
ok &= check('WalkClock：unknown 連續 3 次以上 = 不再算巡路（第 3 次起耗時限）', wc.end == 10 + 3 and wc.walked == 3, f'end={wc.end} walked={wc.walked}')
wc = quest.WalkClock(10, 0.0, cap=50)
for t in range(1, 201):
    wc.tick('walking', float(t))
ok &= check('WalkClock：單次巡路超過 cap 就不再延長（防卡死）', wc.expired(200.0) and wc.walked <= 51, f'walked={wc.walked}')
wc = quest.WalkClock(10, 0.0)
wc.tick('idle', 5.0)
wc.tick('walking', 6.0)
ok &= check('WalkClock：走路前的閒置時間不被補回（只補 walking 期間）', wc.end == 10.0, f'end={wc.end}')
ok &= check('questrun 與 quest 的 WALK_CAP_S 一致', __import__('questrun').WALK_CAP_S == quest.WALK_CAP_S)
s = Script([WALK] * 30 + [IDLE] * 40)
rc = run2(['--no-track', '--max-seconds', '10'], s)
ok &= check('整合：--max-seconds 10、巡路 30 秒不計 → 約 40 秒才「時間到」（舊行為 10 秒就切）', rc == 0 and 38 <= s.t - 1000 <= 44, f'rc={rc} t={s.t - 1000}')
s = Script([IDLE] * 40)
rc = run2(['--no-track', '--max-seconds', '10'], s)
ok &= check('整合：沒巡路 → 照樣 10 秒到', rc == 0 and 9 <= s.t - 1000 <= 12, f't={s.t - 1000}')

print('(X) 對話 / 領獎結束後一律先點追蹤，卡片不在 / 沒反應才找黃問號')


def order_case(screens, track_res, marker_res, argv_extra=()):
    s_ = Script(screens)
    mark = lambda: (s_.clicks.append((0, 'MARK')), marker_res)[1]
    trk = lambda *a, **k: (s_.clicks.append((0, 'TRACK')), track_res)[1]
    rc_ = run2(['--task', 'x', '--max-seconds', '25'] + list(argv_extra), s_, marker=mark, track=trk)
    return rc_, [c[1] for c in s_.clicks]


rc, seq = order_case([IDLE, IDLE, DIALOG, IDLE, IDLE, IDLE, IDLE, IDLE], True, None)
i = seq.index('click 948 461')
ok &= check('對話框按完 → 下一個動作是 TRACK（中間沒有 MARK）', seq[i + 1] == 'TRACK', str(seq))
ok &= check('開始時（沒對話過）仍是先找黃問號（MARK 在第一個 TRACK 前）', seq.index('MARK') < seq.index('TRACK'), str(seq))
mk722 = {'x': 722, 'y': 318, 'w': 12, 'h': 14, 'n': 90}
rc, seq = order_case([IDLE, DIALOG, DIALOG, IDLE, IDLE, IDLE, IDLE, IDLE], False, mk722)
i = seq.index('click 948 461')
ok &= check('追蹤欄沒有該任務卡片（False）→ 同一輪接著 MARK 並點黃問號', seq[i + 1] == 'TRACK' and seq[i + 2] == 'MARK' and any(c.startswith('click 1215 18; wait 100; click 722 ') or 'click 722' in c for c in seq[i + 3:]), str(seq))
rc, seq = order_case([IDLE, DIALOG] + [IDLE] * 40, True, None)
ok &= check('追蹤點了卻一直沒反應：改找黃問號（MARK）後仍沒反應才退出碼 3（不是第一輪就 3）', rc == 3 and seq.count('TRACK') >= 3 and 'MARK' in seq[seq.index('click 948 461'):], f'rc={rc} {seq}')
rc, seq = order_case([IDLE, REWARD, IDLE, IDLE, IDLE, IDLE, IDLE], True, None, ['--no-marker'])
ok &= check('領獎後：照舊先掃追蹤列表（TRACK）', 'TRACK' in seq[seq.index('click 720 572'):][:2], str(seq))

print('(Y) 隊伍檢查：面板開後等卡片內容穩定再判斷；全部不在隊先重讀')
ALLO = {r: 'other' for r in quest.TEAM_CARDS}
GOOD = dict(ALLO, DKBO='leader', DKBO2='member', DKBO3='member', DKBO4='member', DKBO5='member')
_rt, _rs_ = quest.read_team_labels, quest.time.time
reads = iter([ALLO, ALLO, GOOD, GOOD, GOOD])
quest.read_team_labels = lambda: next(reads)
clk = {'t': 0.0}
quest.time.time, quest.time.sleep = (lambda: clk['t']), (lambda d: clk.__setitem__('t', clk['t'] + d))
got = quest.read_team_labels_stable()
ok &= check('剛開面板 5 人都讀成不在隊 → 繼續等，內容載入（GOOD 連 2 次）才回傳', got == GOOD, str(got))
reads = iter([ALLO] * 20)
clk['t'] = 0.0
got = quest.read_team_labels_stable()
ok &= check('一直全部不在隊 → 最多等 1.5 秒、至少重讀 2 次才回（交給 judge 判失敗）', got == ALLO and 0.5 <= clk['t'] <= 2.1, f't={clk["t"]}')
ok &= check('全部不在隊 → judge_team 判失敗；穩定後的 GOOD → 通過', not quest.judge_team(ALLO, 5)[0] and quest.judge_team(GOOD, 5)[0])
quest.read_team_labels = lambda: None
ok &= check('讀不到像素 → None', quest.read_team_labels_stable() is None)
quest.read_team_labels = _rt
quest.time.time, quest.time.sleep = _rs_, (lambda d: None)

print('(t4) 時序（假時鐘）：進完整戰鬥後 ≤ 3 秒內確實刷新；失敗 1 秒後重試，不等 REFRESH_GAP；關閉列一次只點一下')
FULL_ON2 = {'state': 'battle', 'gold': 0, 'full': True, 'cmd': False, 'auto_off': False}


class Timed(RowGame):
    """假時鐘完整戰鬥：bs～be 秒是戰鬥。early = 開戰 early 秒內按切換 → 面板不開、還把「關閉 + 頭像」列叫出來（2026-10-13 actions.log 實況）；
    row_until = 列到第幾秒自己消失（None = 只能點關閉收，eat 下被吃掉）；panel_fail = 前幾次切換面板不開"""

    def __init__(self, bs=2.0, be=30.0, early=1.0, row=False, eat=0, stuck=False, row_until=None, panel_fail=0):
        super().__init__(visible=row, eat=eat, stuck=stuck)
        self.t, self.bs, self.be, self.early, self.row_until, self.panel_fail = 1000.0, bs, be, early, row_until, panel_fail
        self.log = []

    def time(self):
        return self.t

    def sleep(self, d):
        self.t += d

    def rel(self):
        return self.t - 1000

    def screen(self):
        return dict(FULL_ON2) if self.bs <= self.rel() < self.be else dict(IDLE)

    def gui(self, *args, note=''):
        if self.row_until is not None and self.rel() >= self.row_until:
            self.visible = False
        if args[0] == 'seq' and 'waitpix' in args[1]:
            self.clicks.append(args[1])
            self.log.append((round(self.rel(), 2), 'switch'))
            if self.rel() - self.bs < self.early:
                self.visible = True                      # 太早按：沒開面板，叫出關閉列
                self.sleep(1.5)
                return 'click 850,765\ntimeout 1500\nskip click'
            if self.panel_fail > 0:
                self.panel_fail -= 1
                self.sleep(1.5)
                return 'click 850,765\ntimeout 1500\nskip click'
            self.sleep(0.7)
            self.log.append((round(self.rel(), 2), 'refreshed'))
            return 'click 850,765\nok 200\nclick 910,578'
        if args[0] == 'seq' and args[1].startswith('click 510 '):
            self.log.append((round(self.rel(), 2), 'close'))
            self.sleep(0.5)
        return super().gui(*args, note=note)


def first_refresh(g):
    return next((t for t, k in g.log if k == 'refreshed'), None)


g = Timed()
rc = run2(['--no-track', '--max-seconds', '12'], g)
fr = first_refresh(g)
ok &= check(f'一般情況：開戰後 ≤ REFRESH_FIRST_DELAY+1={quest.REFRESH_FIRST_DELAY + 1:g} 秒刷新成功、之前沒有失敗的切換（不在開戰瞬間亂按叫出關閉列）',
            fr is not None and fr - g.bs <= quest.REFRESH_FIRST_DELAY + 1.0 and [k for _, k in g.log][:2] == ['switch', 'refreshed'], f'{g.log}')
g = Timed(early=99.0, panel_fail=0)
g.early = 0.0
g.panel_fail = 2
rc = run2(['--no-track', '--max-seconds', '14'], g)
sw = [t for t, k in g.log if k == 'switch']
ok &= check(f'面板前 2 次沒開 → 約 1～2.5 秒後重試（不等 REFRESH_GAP），第 3 次成功仍在開戰 ≤ REFRESH_FIRST_DELAY+6={quest.REFRESH_FIRST_DELAY + 6:g} 秒內',
            len(sw) >= 3 and all(0.9 <= b - a <= 3.2 for a, b in zip(sw, sw[1:3])) and first_refresh(g) is not None and first_refresh(g) - g.bs <= quest.REFRESH_FIRST_DELAY + 6.0, f'{g.log}')
g = Timed(row=True, eat=1)
rc = run2(['--no-track', '--max-seconds', '14'], g)
cl = [t for t, k in g.log if k == 'close']
ok &= check(f'開戰就有關閉列、第 1 下被吃 → 每輪只點 1 下，第 2 下收起後立刻刷新（開戰 ≤ REFRESH_FIRST_DELAY+3={quest.REFRESH_FIRST_DELAY + 3:g} 秒；舊版 4 下 × 4.5 秒 ≈ 18 秒）',
            len(cl) == 2 and first_refresh(g) is not None and first_refresh(g) - g.bs <= quest.REFRESH_FIRST_DELAY + 3.0 and first_refresh(g) - cl[-1] < 1.5, f'{g.log}')
g = Timed(row=True, eat=2)
rc = run2(['--no-track', '--max-seconds', '14'], g)
cl = [t for t, k in g.log if k == 'close']
ok &= check(f'前 2 下都被吃（收不掉）→ 點滿 CLOSE_ROW_MAX_CLICKS={quest.CLOSE_ROW_MAX_CLICKS} 下就停、不再點（2026-10-13 review §4.2：等列自己消失）',
            len(cl) == quest.CLOSE_ROW_MAX_CLICKS == 2 and first_refresh(g) is None, f'{g.log}')
g = Timed(row=True, stuck=True, row_until=10.0)
rc = run2(['--no-track', '--max-seconds', '16'], g)
ok &= check('關閉列點不掉、第 10 秒自己消失 → 消失後 ≤ 2 秒內刷新（舊版要等收列 4 下 + REFRESH_GAP）',
            first_refresh(g) is not None and 10.0 <= first_refresh(g) <= 12.0, f'{g.log}')
g = Timed(bs=2.0, be=12.0)
rc = run2(['--no-track', '--max-seconds', '14'], g)
rf = [t for t, k in g.log if k == 'refreshed']
ok &= check(f'成功後同一場仍照 REFRESH_GAP={quest.REFRESH_GAP:g}（10 秒戰鬥成功刷新 1～{int(10 / quest.REFRESH_GAP) + 1} 次、間隔 ≥ GAP，不是每秒）',
            1 <= len(rf) <= int(10 / quest.REFRESH_GAP) + 1 and all(b - a >= quest.REFRESH_GAP for a, b in zip(rf, rf[1:])), f'{rf}')
ok &= check('刷新 seq（6be1498）：第一次點切換 → 短等 SWITCH_FIRST_WAIT_MS 沒開 → 同一個 seq 內 ifnok 再點一次（算一次嘗試），結果取最後一個 waitpix',
            any(f'waitpix {quest.SWITCH_FIRST_WAIT_MS} ' in c and 'ifnok click 850 765' in c for c in g.clicks)
            and quest.waitpix_result('timeout 400\nclick 850,765\nok 200\nclick 910,578') == 'ok'
            and quest.waitpix_result('ok 100\nskip click\ntimeout 1500') == 'timeout', str(g.clicks[:1]))
print('(t5) should_refresh 開戰延遲：完整戰鬥未滿 REFRESH_FIRST_DELAY 不按、快速戰鬥不等')
_a = A(solo=False, fight=False, no_refresh=False)
ok &= check(f'完整戰鬥開戰 0.5 秒不按、REFRESH_FIRST_DELAY={quest.REFRESH_FIRST_DELAY:g} 秒按', not quest.should_refresh(_a, False, True, False, 99, 0.5) and quest.should_refresh(_a, False, True, False, 99, quest.REFRESH_FIRST_DELAY))
ok &= check('快速戰鬥開戰 0 秒就按', quest.should_refresh(_a, False, False, False, 99, 0.0))

print('(盜賊) 「戰鬥 / 再見」兩鈕對話框後備判斷（強盜的洞穴；classify 判 idle 時用按鈕字旁像素 + 按鈕 OCR）')
BEIGE = {p: quest.DIALOG_BTN_BEIGE for p in quest.DIALOG_BTN_PROBES}
_keep_ps2, _keep_gui2 = quest.ps_json, quest.gui
OCR_CALLS = []


def fake_btn_ocr(text):
    def f(script, *args):
        OCR_CALLS.append(script)
        return {'lines': [{'text': text}] if text else []}
    return f


quest.gui = fake_pixel_gui({**HUD_COL, **BEIGE})
quest.ps_json = fake_btn_ocr('戰鬥 再見')
r = REAL_READ_SCREEN()
ok &= check('idle + 鈕旁米色 + OCR「戰鬥 再見」→ state dialog', r['state'] == 'dialog' and r.get('fight_fallback'), str(r))
quest.ps_json = fake_btn_ocr('完成 再見')
ok &= check('OCR 左鈕不是戰鬥（完成 / 再見）→ 維持 idle，不當對話框', REAL_READ_SCREEN()['state'] == 'idle')
quest.ps_json = fake_btn_ocr('再見 戰鬥')
ok &= check('「戰鬥」在「再見」之後（左鈕不是戰鬥）→ 維持 idle', REAL_READ_SCREEN()['state'] == 'idle')
quest.ps_json = fake_btn_ocr('')
ok &= check('OCR 讀不到 → 維持 idle（保守）', REAL_READ_SCREEN()['state'] == 'idle')
del OCR_CALLS[:]
quest.gui = fake_pixel_gui(dict(HUD_COL))
quest.ps_json = fake_btn_ocr('戰鬥 再見')
ok &= check('主畫面（鈕旁不是米色）→ idle、不跑 OCR', REAL_READ_SCREEN()['state'] == 'idle' and not OCR_CALLS)
quest.gui = fake_pixel_gui({**HUD_COL, **{p: quest.DIALOG_BTN_BEIGE for p in quest.DIALOG_BTN_PROBES[:2]}})
ok &= check('鈕旁只有 2 點米色（< 3）→ idle、不跑 OCR', REAL_READ_SCREEN()['state'] == 'idle' and not OCR_CALLS)
# 真對話框（SIG_DIALOG 命中）照舊 dialog，不跑後備 OCR
DLG_COL = {(x, y): (r, g, b) for x, y, r, g, b, *_ in quest.SIG_DIALOG}
quest.gui = fake_pixel_gui({**DLG_COL, **BEIGE})
ok &= check('SIG_DIALOG 命中 → dialog、不是後備', REAL_READ_SCREEN()['state'] == 'dialog' and not OCR_CALLS and not REAL_READ_SCREEN().get('fight_fallback'))
# 主迴圈：後備 dialog → 按左鈕 948,461；不可逆內文仍擋
s = Sim(dialog_at=2.0)
DLG.update(body=['盜賊：想搶走東西就打倒我吧！'], buttons=['戰鬥', '再見'])
rc = run(['--no-track', '--max-seconds', '20'], s)
ok &= check('主迴圈：戰鬥 / 再見對話框 → 按左鈕 948,461', bool(has(s, 'click 948 461')), str(s.clicks[:3]))
DLG.update(body=['要進行轉生的儀式嗎？'], buttons=['戰鬥', '再見'])
s = Sim(dialog_at=2.0)
rc = run(['--no-track', '--max-seconds', '20'], s)
ok &= check('內文含「轉生」即使左鈕是戰鬥 → 不按、退出碼 39', rc == 39 and not has(s, 'click 948 461'), f'rc={rc}')
DLG.update(body=['你要進入裏面嗎？那趕緊通過吧！'], buttons=['完成', '再見'])
quest.ps_json, quest.gui = _keep_ps2, _keep_gui2
quest.read_screen = REAL_READ_SCREEN

# ---- 自動巡路卡住解卡（2026-10-12 吉魯島 300:121,170 Auto Walking 站 40 分鐘）----
print('(w) WalkStuck 巡路卡住偵測 / pick_unstick 選地面')
ok &= check('卡住解卡第 1 次先刷新角色、之後不再', quest.unstick_refresh_due(1) and not quest.unstick_refresh_due(2) and not quest.unstick_refresh_due(3))
ws = quest.WalkStuck(stuck_s=40, every=5)
seq = [('walking', (300, 121, 170), t) for t in range(0, 45, 5)]
hits = [ws.feed(p_, t) for st_, p_, t in seq if ws.due(st_, t)]
ok &= check('同座標 walking 40 秒 → stuck', hits[-1] is True and not any(hits[:-1]), str(hits))
ws = quest.WalkStuck(stuck_s=40, every=5)
hits = [ws.feed((300, 121 + t // 10, 170), t) for t in range(0, 60, 5) if ws.due('walking', t)]
ok &= check('座標有在變 → 不算卡住', not any(hits))
ws = quest.WalkStuck(stuck_s=40, every=5)
for t in range(0, 35, 5):
    if ws.due('walking', t):
        ws.feed((300, 121, 170), t)
ws.due('unknown', 36)                                  # 讀圖失敗一次不重設
ok &= check('中途 unknown 不重設、40 秒到 → stuck', ws.due('walking', 40) and ws.feed((300, 121, 170), 40))
ws.due('idle', 41)
ok &= check('閒置 → 重設', ws.pos is None)
ws = quest.WalkStuck(stuck_s=40, every=5)
ok &= check('讀不到座標不算', not any(ws.feed(None, t) for t in range(0, 100, 5)))
cs = quest.walk._cells(300)
d = quest.walk.pick_unstick(cs, quest.walk.exits_of(300), 121, 170)
ok &= check('吉魯島 121,170：選通行格、離出口 122,170 / 守門人 118,171 ≥ 2 格', d is not None and cs[2][(170 + d[1]) * cs[0] + 121 + d[0]] == 1
            and max(abs(121 + d[0] - 122), abs(170 + d[1] - 170)) >= 2 and max(abs(121 + d[0] - 118), abs(170 + d[1] - 171)) >= 2, str(d))
ok &= check('沒有通行格資料 → None（不亂點）', quest.walk.pick_unstick(None, set(), 1, 1) is None)
ok &= check('slice_defer：戰鬥 / 對話中時間到不收片、閒置收片、超過 180 秒放棄', quest.slice_defer('battle', 5) and quest.slice_defer('dialog', 0) and not quest.slice_defer('idle', 5) and not quest.slice_defer('battle', 181))
import uikit as _uk
_px = {(x, y): (r, g, b) for x, y, r, g, b, t in _uk.PLAYERPICK.sig}
ok &= check('PLAYERPICK 特徵：自己的取樣值吻合；「選擇對象」面板外框色（104,79,48）不吻合', all(_uk.screen_sigs.close(_px[(x, y)], (r, g, b), t) for x, y, r, g, b, t in _uk.PLAYERPICK.sig)
            and not all(_uk.screen_sigs.close((104, 79, 48), (r, g, b), t) for x, y, r, g, b, t in _uk.PLAYERPICK.sig[:2]))
ok &= check('pick_unstick 預設半徑先 4 格（離隊友遠）', quest.walk.pick_unstick.__defaults__[0][0] == 4)
ok &= check('nearest_exit：琉璃 9 樓 45,45 → 47,47（10 樓）、同圖出口不算、太遠 None', (quest.walk.nearest_exit(21009, 45, 45) or {}).get('tMap') == 21010 and quest.walk.nearest_exit(21009, 30, 30) is None)
ok &= check('pick_stepoff：出口格相鄰通行非出口格 / 無資料 None', quest.walk.pick_stepoff(quest.walk._cells(21002), quest.walk.exits_of(21002), 40, 25) == (39, 26) and quest.walk.pick_stepoff(None, set(), 1, 1) is None)
w_, h_ = 7, 7
ok &= check('四周全是障礙 → None', quest.walk.pick_unstick((w_, h_, bytes([2]) * (w_ * h_), set()), set(), 3, 3) is None)


class WalkSim(Sim):
    """Auto Walking 一直站著不動，直到點了地面（非引子、非 UI 的 click）才停下變閒置"""

    def __init__(self):
        super().__init__()
        self.unstuck = False

    def gui(self, *args, note=''):
        out = super().gui(*args, note=note)
        if 'click 459 410' in (args[1] if args[0] == 'seq' else ''):
            self.unstuck = True
        return out

    def screen(self):
        return dict(IDLE) if self.unstuck else {'state': 'walking', 'gold': 26, 'full': False, 'cmd': False, 'auto_off': False}


ERRS = []
_keep_err = quest._errlog
quest._errlog = lambda m, fixed=None: ERRS.append((m, fixed))
s = WalkSim()
s.pos = lambda: (300, 121, 170)
rc = run(['--no-track', '--max-seconds', '30'], s)
clk = [c for c in s.clicks if 'click 459 410' in c[1]]
ok &= check('主迴圈：walking 座標 40 秒不變 → 點地面 459,410 一次、記 errlog', len(clk) == 1 and 40 <= clk[0][0] <= 50 and len(ERRS) == 1, f'rc={rc} {clk} {ERRS}')
# 座標讀不到（地圖名兩行，HUD 座標 OCR 失敗）→ 改比世界畫面取樣；實機樣本 fixtures/world_px.json
import json as _json2
_W = _json2.loads((Path(__file__).resolve().parent / 'fixtures' / 'world_px.json').read_text(encoding='utf-8'))['images']
_h = lambda L: [tuple(int(x[i:i + 2], 16) for i in (0, 2, 4)) for x in L]
for _k, _v in _W.items():
    ok &= check(f'world_same 實機 {_k}：同一張 True、鏡頭捲 1 格 False', quest.world_same(_h(_v['base']), _h(_v['base'])) and not quest.world_same(_h(_v['base']), _h(_v['moved'])))
_black = [(5, 5, 5)] * len(quest.WORLD_PTS)
ok &= check('world_same：全黑（洞窟虛空）不當證據 → False', not quest.world_same(_black, _black))
ws = quest.WalkStuck(stuck_s=40, every=5)
_base = _h(next(iter(_W.values()))['base'])
ok &= check('feed_sig：畫面 40 秒不變 → stuck、pos = screen', [ws.feed_sig(_base, t) for t in range(0, 45, 5)][-1] and ws.pos == 'screen')
ERRS.clear()
quest._errlog = lambda m, fixed=None: ERRS.append((m, fixed))
_keep_ws, _keep_tt = quest.read_world_sig, quest.track_task
TT = []
quest.read_world_sig = lambda: _base
quest.track_task = lambda want, *a_, **k_: TT.append(want) or True
s = WalkSim()
rc = run(['--task', '某任務', '--team-fresh', '--max-seconds', '30'], s)
ok &= check('主迴圈：座標讀不到、畫面 40 秒不變 → 不點地面、直接重點追蹤 1 次', not [c for c in s.clicks if 'waitstill 2000' in c[1]] and TT[:1] == ['某任務'] and len(ERRS) >= 1, f'rc={rc} TT={TT} {ERRS[:1]}')
quest.read_world_sig, quest.track_task = _keep_ws, _keep_tt
quest._errlog = _keep_err

print('(RW) 獲得物品：按確認後驗證視窗消失；沒消失重按（2026-10-10 / 10-12 紅暴步 8 按了沒關）')
s = Script([DIALOG, REWARD] + [REWARD] * 6 + [IDLE] * 6)            # 第 1 下被吃掉：之後 1.5 秒內仍是 reward（5 次輪詢），第 2 下才關
rc = run2(['--stop-after-rewards', '1', '--no-track', '--max-seconds', '60'], s)
n_ok = len([c for c in s.clicks if c[1] == 'click 720 572'])
ok &= check('第 1 下沒關 → 重按 1 次就關，rc 0（只算 1 次獎勵）', rc == 0 and n_ok == 2, f'rc={rc} 確認鈕 {n_ok} 次 {s.clicks}')
s = Script([DIALOG, REWARD, IDLE, IDLE, IDLE, IDLE])
rc = run2(['--stop-after-rewards', '1', '--no-track', '--max-seconds', '60'], s)
ok &= check('一下就關 → 只按 1 次', rc == 0 and len([c for c in s.clicks if c[1] == 'click 720 572']) == 1, f'rc={rc} {s.clicks}')
s = Script([DIALOG, REWARD])                                         # 一直都在
rc = run2(['--stop-after-rewards', '1', '--no-track', '--max-seconds', '60'], s)
ok &= check(f'按 {quest.REWARD_CLICK_MAX} 次都還在 → 退出碼 {quest.EXIT_REWARD_STUCK}、不點別的', rc == quest.EXIT_REWARD_STUCK
            and [c[1] for c in s.clicks] == ['click 948 461'] + ['click 720 572'] * quest.REWARD_CLICK_MAX, f'rc={rc} {s.clicks}')
s = Script([DIALOG, REWARD, IDLE, REWARD, IDLE, IDLE, IDLE, IDLE, IDLE])   # 兩個連續領獎窗（中間有空檔）→ 各算 1 次
rc = run2(['--stop-after-rewards', '2', '--no-track', '--max-seconds', '60'], s)
ok &= check('連續兩個領獎窗（中間讀到主畫面）→ 各按 1 次、算 2 次獎勵', rc == 0 and len([c for c in s.clicks if c[1] == 'click 720 572']) == 2, f'rc={rc} {s.clicks}')
# 2026-10-13 紅暴步 8：石幣動畫讓 close_reward 單次讀成「不是 reward」→ 當成已關；--stop-after-rewards 停手前 settle_reward 再看 2 秒
s = Script([DIALOG, REWARD, IDLE, REWARD, IDLE, IDLE, IDLE, IDLE, IDLE, IDLE, IDLE, IDLE])
rc = run2(['--stop-after-rewards', '1', '--no-track', '--max-seconds', '60'], s)
ok &= check('步 8 誤判已關：停手前又看到領獎窗 → 再按確認一次、rc 0（不留給人手點 720,572）',
            rc == 0 and len([c for c in s.clicks if c[1] == 'click 720 572']) == 2, f'rc={rc} {s.clicks}')
s = Script([DIALOG, REWARD, IDLE, REWARD])                           # 誤判已關後窗一直在
rc = run2(['--stop-after-rewards', '1', '--no-track', '--max-seconds', '60'], s)
ok &= check(f'停手前領獎窗又出現且一直關不掉 → 退出碼 {quest.EXIT_REWARD_STUCK}、只點確認鈕', rc == quest.EXIT_REWARD_STUCK
            and set(c[1] for c in s.clicks) == {'click 948 461', 'click 720 572'}, f'rc={rc} {s.clicks}')
s = Script([DIALOG, REWARD, IDLE, IDLE, IDLE, IDLE, IDLE, IDLE, IDLE, IDLE])
rc = run2(['--stop-after-rewards', '1', '--no-track', '--max-seconds', '60'], s)
ok &= check('真的關了：settle 2 秒內沒再出現 → 只按 1 次、rc 0', rc == 0 and len([c for c in s.clicks if c[1] == 'click 720 572']) == 1, f'rc={rc} {s.clicks}')

print('(BYE) 只有「再見」一顆鈕的閒聊對話（2026-10-12 紅暴步 1 誤報 rc 2）')
# 實機像素（quest-log/140941-UNKNOWN.png、140927-dialog.png、battle-samples/vs_1.png、141940-reward.png；SIG_BYE 9 點的順序）
_BYE_PX = {
    '閒聊（只有再見）': ([(107, 70, 44), (107, 70, 44), (111, 73, 47), (108, 70, 44), (107, 70, 44), (107, 70, 44), (229, 200, 161), (235, 201, 159), (234, 200, 159)], True),
    '一般兩鈕對話': ([(107, 70, 44), (107, 70, 44), (229, 199, 157), (229, 198, 154), (235, 201, 159), (234, 197, 157), (108, 71, 44), (155, 113, 80), (235, 201, 159)], False),
    '快速戰鬥 VS（最多中 7 點）': ([(125, 110, 41), (104, 84, 38), (103, 78, 37), (111, 79, 32), (105, 88, 40), (107, 94, 42), (244, 232, 157), (98, 83, 49), (109, 84, 41)], False),
    '獲得物品': ([(0, 0, 0), (41, 48, 48), (255, 229, 90), (0, 0, 0), (134, 121, 100), (0, 0, 0), (0, 0, 0), (0, 0, 0), (0, 0, 0)], False),
}
for _nm, (_cols, _want) in _BYE_PX.items():
    _px = {(x, y): c for (x, y, *_), c in zip(quest.SIG_BYE, _cols)}
    ok &= check(f'bye_probe_ok {_nm} → {_want}', quest.bye_probe_ok(_px) == _want)
ok &= check('bye_probe_ok 缺點 → False', not quest.bye_probe_ok({}))
for _t, _want in [('再見', True), ('戰鬥再見', False), ('再見再見', False), ('', False), ('再', False), ('A再見', False)]:
    ok &= check(f'bye_text_only {_t!r} → {_want}', quest.bye_text_only(_t) == _want)

BYE = dict(IDLE, state='bye')


class KeySim(Script):
    def gui(self, *args, note=''):
        if args[0] == 'key':
            self.clicks.append((round(self.t - 1000, 1), 'key ' + args[1]))
            return ''
        return super().gui(*args, note=note)


SELECT_S = dict(IDLE, state='select')
_keep_hsp = quest.handle_select_panel
quest.handle_select_panel = lambda: True                    # 選擇對象面板：假裝點到一張卡
s = KeySim([DIALOG, REWARD, IDLE, SELECT_S, BYE, IDLE, IDLE, IDLE, IDLE, IDLE])
rc = run2(['--stop-after-dialog', '--task', 'x', '--max-seconds', '60'], s)
ok &= check('領獎後選擇對象面板點到閒聊（紅暴步 1）→ ESC 1 次、回原流程（--stop-after-dialog 閒置後停 0）', rc == 0 and [c[1] for c in s.clicks].count('key {ESC}') == 1, f'rc={rc} {s.clicks}')
s = KeySim([DIALOG] + [SELECT_S, BYE, IDLE] * 3 + [BYE] * 12)
rc = run2(['--stop-after-dialog', '--task', 'x', '--max-seconds', '120'], s)
ok &= check(f'選擇對象 → 閒聊一直出現 → 第 {quest.BYE_MAX} 次退出碼 40（不是 rc 2 疑似驗證）', rc == quest.EXIT_BYE_ONLY and [c[1] for c in s.clicks].count('key {ESC}') == quest.BYE_MAX, f'rc={rc} {s.clicks}')
quest.handle_select_panel = _keep_hsp
s = KeySim([IDLE, IDLE, WALK, WALK, BYE, IDLE, IDLE])
rc = run2(['--task', 'x', '--max-seconds', '120', '--no-marker'], s, track=lambda *a, **k: True)
ok &= check('點追蹤巡路抵達任務 NPC、只有再見（2026-10-13 老人薩頓）→ ESC 後退出碼 40、沒點任何鈕', rc == quest.EXIT_BYE_ONLY
            and [c[1] for c in s.clicks if c[1].startswith('key')] == ['key {ESC}'] and not [c for c in s.clicks if c[1].startswith('click 948') or c[1].startswith('click 1220')], f'rc={rc} {s.clicks}')
s = KeySim([IDLE, IDLE, WALK, BYE, BYE, IDLE])
rc = run2(['--task', 'x', '--max-seconds', '120', '--no-marker'], s, track=lambda *a, **k: True)
ok &= check('ESC 後對話框還在 → 再 ESC 一次（只 ESC）', rc == quest.EXIT_BYE_ONLY and [c[1] for c in s.clicks].count('key {ESC}') == 2, f'rc={rc} {s.clicks}')

print('(BYE-OCR) 按鈕區 OCR 每個倍率分開判（-Zooms 2,3 同一顆「再見」讀兩次）')
for _lines, _want, _nm in [([{'text': '再見', 'zoom': 2}, {'text': '再見', 'zoom': 3}], True, '兩倍率各一次再見（老人薩頓實測）'),
                           ([{'text': '再見', 'zoom': 2}], True, '只有一個倍率讀到'),
                           ([{'text': '再 見', 'zoom': 2}, {'text': '', 'zoom': 3}], True, '空白 / 空行忽略'),
                           ([{'text': '再見', 'zoom': 2}, {'text': '戰鬥再見', 'zoom': 3}], False, '另一倍率多讀到戰鬥'),
                           ([{'text': '進入採石場', 'zoom': 2}, {'text': '再見', 'zoom': 2}], False, '同倍率兩顆鈕（看門者）'),
                           ([{'text': '再', 'zoom': 2}], False, '讀不完整'), ([], False, '讀不到'), ([{'text': '再見再見', 'zoom': 2}], False, '同倍率重複')]:
    ok &= check(f'bye_lines_only {_nm} → {_want}', quest.bye_lines_only(_lines) == _want)
_keep_ps3 = quest.ps_json
quest.ps_json = lambda script, *a: {'ok': True, 'lines': [{'text': '再見', 'x': 1084, 'y': 462, 'zoom': 2}, {'text': '再見', 'x': 1084, 'y': 462, 'zoom': 3}]}
ok &= check('bye_button_only：ocr.ps1 兩倍率各回「再見」→ True（舊版接成「再見再見」→ False，誤報 rc 9）', quest.bye_button_only())
quest.ps_json = _keep_ps3

print('(STRAY) 2026-10-13 誤報樣本（fixtures/stray_px.json，tools/.cache 實機截圖取點）')
import screen_sigs as _S  # noqa: E402
import bag as _bag  # noqa: E402
_FX = _json.loads((Path(__file__).resolve().parent / 'fixtures' / 'stray_px.json').read_text(encoding='utf-8'))


def _fxpx(rel):
    return {tuple(int(v) for v in k.split(',')): tuple(c) for k, c in _FX['images'][rel]['px'].items()}


def _chrome(px):
    return all(_S.close(px[(x, y)], (r, g, b), t) for x, y, r, g, b, t in _bag.CHROME)


for _rel, _img in _FX['images'].items():
    _px = _fxpx(_rel)
    _kind = _img['note'].split('（')[0].split(' ')[0]
    _cls = _S.classify(_px)['state']
    _strict = _S.panel_strict(_px)
    _bye = quest.bye_probe_ok(_px)
    if _kind == 'bye':
        ok &= check(f'{_rel}：classify 不認得、SIG_BYE 9 點全中、OCR 記錄 → 只有再見', _cls == 'unknown' and _bye and _strict is None
                    and (_rel not in _FX['ocr_btn'] or quest.bye_lines_only(_FX['ocr_btn'][_rel])), f'{_cls} {_bye} {_strict}')
    elif _kind == 'bag':
        ok &= check(f'{_rel}：舊 classify（points 只有切換面板）不認得；panel_strict = bag 且背包外框兩顆鈕在 → 可點 ✕ 關', _S.classify({k: v for k, v in _px.items() if k in set(_S.points())})['state'] == 'unknown'
                    and _strict == 'bag' and _chrome(_px) and not _bye, f'{_strict} {_chrome(_px)}')
    else:
        ok &= check(f'{_rel}（{_img["note"]}）：不是背包可關 / 不是只有再見', _strict is None and not _bye, f'{_strict} {_bye}')
    ok &= check(f'{_rel}：信封發亮 = {"發亮" in _img["note"]}', _S.mail_glow(_px) == ('發亮' in _img['note']))

print('(STRAY-2) close_stray_panel / clear_leftovers：已知面板點 ✕、對話框 ESC、不認得不碰')
import uikit as _uk  # noqa: E402
_keep = (_uk.is_open, _uk.known_panel, _uk.close_panel, quest.read_screen, quest.gui, quest.snap, quest.event, quest.close_reward, quest.time.sleep)
_log = []
_uk.is_open = lambda p: False
_uk.close_panel = lambda p, known_open=False: (_log.append(('close', p.name)), True)[1]
quest.snap, quest.event, quest.time.sleep = (lambda tag: 'sim.png'), (lambda m, shot=None: _log.append(('event', m))), (lambda d: None)
_uk.known_panel = lambda: 'bag'
ok &= check('close_stray_panel：背包面板殘留 → 點背包 ✕（bag.BAGANY）', quest.close_stray_panel() and ('close', 'BAGANY') in _log, str(_log))
_uk.known_panel = lambda: None
del _log[:]
ok &= check('close_stray_panel：不是已知面板 → False、什麼都不點', not quest.close_stray_panel() and not [x for x in _log if x[0] == 'close'])
_seq = ['dialog', 'bye', 'unknown', 'idle']
_kp = ['bag']
quest.read_screen = lambda: {'state': _seq.pop(0) if len(_seq) > 1 else _seq[0]}
quest.gui = lambda *a, **k: _log.append(('gui',) + a) or ''
_uk.known_panel = lambda: _kp.pop(0) if _kp else None
del _log[:]
_st = quest.clear_leftovers()
ok &= check('clear_leftovers：對話框 ESC → 再見 ESC → 背包面板 ✕ → idle', _st == 'idle' and [x[2] for x in _log if x[0] == 'gui'] == ['{ESC}', '{ESC}'] and ('close', 'BAGANY') in _log, f'{_st} {_log}')
_seq = ['unknown']
del _log[:]
_st = quest.clear_leftovers()
ok &= check('clear_leftovers：真的不認得 → 回 unknown、沒按任何鍵', _st == 'unknown' and not [x for x in _log if x[0] in ('gui', 'close')], f'{_st} {_log}')
_seq = ['reward', 'idle']
quest.close_reward = lambda: (True, 1)
del _log[:]
ok &= check('clear_leftovers：獲得物品 → close_reward → idle', quest.clear_leftovers() == 'idle')
(_uk.is_open, _uk.known_panel, _uk.close_panel, quest.read_screen, quest.gui, quest.snap, quest.event, quest.close_reward, quest.time.sleep) = _keep

print('(HP) 片內連戰 HP 檢查 / BOSS 戰後時間到延後（2026-10-13 四寶玉之謎 DKBO3 / DKBO5 HP 0 被踢）')
ok &= check('slice_defer：主畫面 + BOSS 待確認 → 延後；超過上限不延後；沒 BOSS 照舊', quest.slice_defer('idle', 5, True) and not quest.slice_defer('idle', 5, False)
            and not quest.slice_defer('idle', quest.SLICE_DEFER_MAX_S + 1, True) and quest.slice_defer('battle', 5))
_A = lambda **k: type('A', (), dict(dict(hp_check_min=60, hp_check_every=1, solo=False, fight=False), **k))()
ok &= check('hp_check_due：任務戰 1 場 + 閒置確認 → True；沒打 / 沒閒置確認 / 沒開 / --solo / --fight → False',
            quest.hp_check_due(_A(), 1, 0, True) and not quest.hp_check_due(_A(), 0, 0, True) and not quest.hp_check_due(_A(), 1, 0, False)
            and not quest.hp_check_due(_A(hp_check_min=0), 3, 3, True) and not quest.hp_check_due(_A(solo=True), 1, 1, True) and not quest.hp_check_due(_A(fight=True), 1, 1, True))
_A3 = lambda **k: type('A', (), dict(dict(hp_check_min=60, solo=False, fight=False), **k))()
ok &= check('hp_check_due：路上一般戰鬥預設每 3 場才讀（review §5.4）；--hp-check-every 1 每場；0 = 一般戰鬥不讀',
            quest.HP_CHECK_EVERY == 3 and not quest.hp_check_due(_A3(), 0, 2, True) and quest.hp_check_due(_A3(), 0, 3, True)
            and quest.hp_check_due(_A(hp_check_every=1), 0, 1, True) and not quest.hp_check_due(_A(hp_check_every=0), 0, 9, True) and quest.hp_check_due(_A(hp_check_every=0), 1, 0, True))
ok &= check('hp_low_roles：低於門檻才算、讀不出不算', quest.hp_low_roles({'DKBO': 100, 'DKBO3': 0, 'DKBO5': None, 'DKBO4': 59}, 60) == {'DKBO3': 0, 'DKBO4': 59})
FULL_ON = {'state': 'battle', 'gold': 0, 'full': True, 'cmd': False, 'auto_off': False}
_hp_calls = []
_keep_hp = quest.read_team_hp
quest.read_team_hp = lambda: (_hp_calls.append(1), (0, {'DKBO': 90, 'DKBO2': 80, 'DKBO3': 0, 'DKBO4': 100, 'DKBO5': 30}))[1]
s = Script([FULL_ON, FULL_ON, IDLE, IDLE, IDLE, IDLE, IDLE])
rc = run2(['--no-track', '--max-seconds', '120', '--no-refresh', '--no-stop-after-boss', '--hp-check-min', '60', '--hp-check-every', '1'], s)
ok &= check('打完一場、閒置確認 → 讀全隊 HP → DKBO3 0 / DKBO5 30 < 60 → 退出碼 41', rc == quest.EXIT_HP_LOW and len(_hp_calls) == 1, f'rc={rc} n={len(_hp_calls)}')
quest.read_team_hp = lambda: (_hp_calls.append(1), (0, {r: 100 for r in ('DKBO', 'DKBO2', 'DKBO3', 'DKBO4', 'DKBO5')}))[1]
del _hp_calls[:]
s = Script([FULL_ON, IDLE, IDLE, IDLE, IDLE, FULL_ON, IDLE, IDLE, IDLE, IDLE] + [IDLE] * 4)
rc = run2(['--no-track', '--max-seconds', '14', '--no-refresh', '--no-stop-after-boss', '--hp-check-min', '60', '--hp-check-every', '1'], s)
ok &= check('HP 都夠 → 不停；--hp-check-every 1 每打完一場讀一次（2 場 = 2 次）', rc == 0 and len(_hp_calls) == 2, f'rc={rc} n={len(_hp_calls)}')
del _hp_calls[:]
s = Script([FULL_ON, IDLE, IDLE, IDLE, IDLE, FULL_ON, IDLE, IDLE, IDLE, IDLE] + [IDLE] * 4)
rc = run2(['--no-track', '--max-seconds', '14', '--no-refresh', '--no-stop-after-boss', '--hp-check-min', '60'], s)
ok &= check('預設（每 3 場一般戰鬥）：路上 2 場 → 不讀 HP（舊版 2 次 × 8 秒）', rc == 0 and not _hp_calls, f'rc={rc} n={len(_hp_calls)}')
del _hp_calls[:]
s = Script([DIALOG, FULL_ON, FULL_ON, REWARD] + [IDLE] * 10)
rc = run2(['--no-track', '--max-seconds', '14', '--no-refresh', '--no-stop-after-boss', '--hp-check-min', '60'], s)
ok &= check('預設：任務戰（對話後開打）打完 → 讀 1 次', len(_hp_calls) == 1, f'rc={rc} n={len(_hp_calls)}')
del _hp_calls[:]
s = Script([FULL_ON, IDLE, IDLE, IDLE, IDLE, IDLE])
rc = run2(['--no-track', '--max-seconds', '8', '--no-refresh', '--no-stop-after-boss'], s)
ok &= check('沒給 --hp-check-min → 不讀 HP', not _hp_calls)
quest.read_team_hp = _keep_hp
s = Script([DIALOG, FULL_ON, FULL_ON, REWARD, IDLE, IDLE, IDLE, IDLE, IDLE, IDLE])
rc = run2(['--no-track', '--max-seconds', '3', '--no-refresh', '--boss-team-check'], s)
ok &= check('--boss-team-check：任務 BOSS 戰打完領獎後 slice 時間到 → 延後到閒置確認，回 37（舊版回 0「時間到」，questrun 不做 BOSS 後補血）', rc == quest.EXIT_BOSS_DONE, f'rc={rc} t={s.t - 1000:.1f}')

print('(t4b) 戰鬥底部列拖移（2026-10-15 p2 實測：拖「關閉」鈕整條列移走，之後每場都在新位置）')
quest.CLOSE_ROW_DRAG_TRIES = 2


class DragGame(RowGame):
    def gui(self, *args, note=''):
        if args[0] == 'seq' and args[1].startswith('drag '):
            self.clicks.append(args[1])
            if not self.stuck:
                self.visible = False
            return ''
        return super().gui(*args, note=note)


g = DragGame(True)
quest.gui = g.gui
r = quest.refresh_characters(True)
ok &= check('有列 → 先拖一次（510,780→510,560），列移走後按切換、零點關閉', r == 'ok' and g.clicks[0].startswith('drag 510 780 510 560') and n_close(g) == 0 and n_switch(g) == 1, str(g.clicks))
g = DragGame(False)
quest.gui = g.gui
r = quest.refresh_characters(True)
ok &= check('列已在新位置（不在原位）→ 不拖、直接切換', r == 'ok' and not any(c.startswith('drag') for c in g.clicks), str(g.clicks))
g = DragGame(True, stuck=True)
quest.gui = g.gui
r = quest.refresh_characters(True, attempt=0)
ok &= check('拖不走 → 回 row（不點切換）', r == 'row' and n_switch(g) == 0 and len(g.clicks) == 1, str(g.clicks))
g = DragGame(True, stuck=True)
quest.gui = g.gui
r = quest.refresh_characters(True, attempt=2)
ok &= check('拖過 2 次還在 → 退回點「關閉」', r == 'row' and n_close(g) == 1 and not any(c.startswith('drag') for c in g.clicks), str(g.clicks))
quest.CLOSE_ROW_DRAG_TRIES = 0

# ---- (s) --solo-talk（2026-10-17 精簡 questrun --solo 對話步）：單人段 → team.form → 對話段同一支程序；假 _run / team.form，不碰遊戲 ----
print('(s) --solo-talk：單人巡路 → 組隊 → 對話 → 解散 一次跑完')
import io as _io  # noqa: E402
import contextlib as _ctx  # noqa: E402
import team as _team  # noqa: E402
_keep_s = (quest._run, quest.clear_leftovers, _team.form, quest.disband_team, quest.ensure_task_tab, quest.event)


def solo_talk_case(phase_rcs, form_rc=0):
    """phase_rcs = [單人段 rc, 對話段 rc]；回 (rc, 每段 args 摘要, 呼叫順序, stdout 行)"""
    runs, order = [], []
    q = list(phase_rcs)

    def fake_run(a):
        runs.append({'solo': a.solo, 'sad': a.stop_after_dialog, 'disband': a.disband_after, 'fresh': a.team_fresh, 'max': a.max_seconds})
        order.append('run')
        quest.WALK['clock'] = quest.WalkClock(a.max_seconds, 0.0)
        quest.WALK['clock'].walked = 10.0
        quest.STATS['battles'] = 1
        rc_ = q.pop(0)
        if not a.solo and a.disband_after and rc_ in (0, 24):
            quest.finish(a)                                            # 真的 finish（disband_team 假的）
        return rc_
    quest._run = fake_run
    quest.clear_leftovers = lambda *a: order.append('clear') or 'idle'
    _team.form = lambda *a, **k: order.append('form') or form_rc
    quest.disband_team = lambda *a, **k: order.append('disband') or 0
    quest.ensure_task_tab = lambda: order.append('task_tab')
    quest.event = lambda m, shot=None: None
    quest.layout.current = lambda: '2880x1659'
    for d_ in (quest.CARRY, quest.DISBAND, quest.PHASE, quest.STATS, quest.WALK):
        d_.clear()
    sys.argv = ['quest.py', '--solo-talk', '--task', '英雄島前傳', '--max-seconds', '900', '--talk-seconds', '120']
    buf = _io.StringIO()
    with _ctx.redirect_stdout(buf):
        rc_ = quest.main()
    return rc_, runs, order, buf.getvalue().splitlines()


rc, runs, order, out = solo_talk_case([20, 0])
ok &= check('--solo-talk happy：單人段（--solo、900 秒）→ 清殘留 → team.form → 對話段（--stop-after-dialog --disband-after --team-fresh、120 秒）→ 解散 → 切回任務分頁',
            rc == 0 and runs[0]['solo'] and runs[0]['max'] == 900 and not runs[1]['solo'] and runs[1]['sad'] and runs[1]['disband'] and runs[1]['fresh']
            and runs[1]['max'] == 120 and order == ['run', 'clear', 'form', 'run', 'disband', 'task_tab'], f'{rc} {runs} {order}')
ok &= check('--solo-talk 結尾印 階段 talk + 已驗證解散 + 兩段合計巡路 / 戰鬥', 'solo-talk 階段：talk' in out and quest.DISBAND_OK_LINE in out
            and '走路不計時 20 秒' in out and '本片戰鬥 2 場' in out, str(out))
for want, rcs in ((21, [21]), (5, [5]), (2, [2]), (39, [39]), (0, [0])):
    rc, runs, order, out = solo_talk_case(rcs)
    ok &= check(f'--solo-talk 單人段回 {want} → 原樣回、不組隊、階段 walk', rc == want and order == ['run'] and 'solo-talk 階段：walk' in out
                and quest.DISBAND_OK_LINE not in out, f'{rc} {order}')
rc, runs, order, out = solo_talk_case([20], form_rc=43)
ok &= check('--solo-talk 到 NPC 後 team.form 43 → 44、不跑對話段、階段 form', rc == quest.EXIT_SOLO_FORM and order == ['run', 'clear', 'form'] and 'solo-talk 階段：form' in out, f'{rc} {order}')
rc, runs, order, out = solo_talk_case([20], form_rc=9)
ok &= check('--solo-talk team.form 9（驗證視窗）→ 9 透傳', rc == 9 and order == ['run', 'clear', 'form'], f'{rc} {order}')
rc, runs, order, out = solo_talk_case([20, 26])
ok &= check('--solo-talk 對話段 26（解散沒做成）→ 26、不印已驗證解散', rc == 26 and quest.DISBAND_OK_LINE not in out, f'{rc} {out}')
sys.argv = ['quest.py', '--solo-talk', '--task', 'x', '--fight']
with _ctx.redirect_stdout(_io.StringIO()):
    ok &= check('--solo-talk 與 --fight 並用 → 4', quest.main() == 4)
quest._run, quest.clear_leftovers, _team.form, quest.disband_team, quest.ensure_task_tab, quest.event = _keep_s

print('全部通過' if ok else '有失敗')
sys.exit(0 if ok else 1)
