#!/usr/bin/env python3
"""grind.py / spots.py 離線測試：不碰遊戲。fixture 驗 EXP 橫幅偵測；其餘用假 heal / ass / team / char 驗流程與順序。
用法：uv run --no-project python tools/gui/test_grind.py"""
import io
import json
import os
import sys
import tempfile
import contextlib
from pathlib import Path

os.environ.setdefault('PSA_LAYOUT', '2880x1659')       # 載入 walk 時不問遊戲版面
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import grind  # noqa: E402
import spots  # noqa: E402

ORIG_WBG = grind.wait_banner_gone
TMP = Path(tempfile.mkdtemp())
grind.LOCK, grind.OUT = TMP / 'grind.lock', TMP / 'grind.json'
fails = 0


def check(name, cond, extra=''):
    global fails
    print(('PASS' if cond else 'FAIL'), name, extra)
    if not cond:
        fails += 1


# ---- EXP 橫幅 fixture ----
fx = json.loads((HERE / 'fixtures' / 'exp_px.json').read_text(encoding='utf-8'))
pos_set = set(fx['positive'])
bad = []
mins, maxn = 999, 0
for tag, d in fx['images'].items():
    px = {p: (0, 0, 0) for p in grind.EXP_PTS}
    for k, c in d['purple'].items():
        x, y = map(int, k.split(','))
        px[(x, y)] = tuple(c)
    n = grind.exp_banner(px)
    has = n >= grind.EXP_MIN
    if has != (tag in pos_set):
        bad.append((tag, n))
    if tag in pos_set:
        mins = min(mins, n)
    else:
        maxn = max(maxn, n)
check('exp fixture：全部張數判定正確（0 誤判 / 0 漏判）', not bad, f'bad={bad} 共 {len(fx["images"])} 張，正例 {len(pos_set)}')
check('exp fixture：正例最低 ≥ 19、負例最高 0（門檻 8 餘裕）', mins >= 19 and maxn == 0, f'min={mins} max_neg={maxn}')
check('exp fixture：含 r07 / r12 / now 正例、r01 / p1～p20 負例', {'r07', 'r12', 'now'} <= pos_set and 'r01' in fx['images'] and all(f'p{i}' in fx['images'] and f'p{i}' not in pos_set or i in (14, 16, 19) for i in range(1, 21)))
check('exp 掃描點數 = 2898', len(grind.EXP_PTS) == 2898)
check('is_exp_purple 邊界', grind.is_exp_purple((147, 79, 200)) and not grind.is_exp_purple((147, 79, 170)) and not grind.is_exp_purple((147, 120, 251)) and not grind.is_exp_purple((90, 60, 250)))

# ---- spots ----
a = spots.auto_spot
check('auto 邊界', [a(0, n) for n in (1, 19, 20, 44, 45, 59, 60, 79, 80, 119, 120, 130)] ==
      ['柯奧龜洞', '柯奧龜洞', '海主人隧道', '海主人隧道', '五兄弟洞窟', '五兄弟洞窟', '柯奧4F龜洞', '柯奧4F龜洞', '波拉島', '波拉島', '地雷區', '地雷區'])
check('auto 1 轉以上沿用 0 轉表（未實測）/ 0 級無', a(1, 50) == '五兄弟洞窟' and a(2, 130) == '地雷區' and a(0, 0) is None and a(1, 0) is None)
check('too_low：0 轉預判、1 轉不預判', spots.too_low('地雷區', 0, 119) and not spots.too_low('地雷區', 0, 120) and not spots.too_low('地雷區', 1, 1))
check('parse_level', spots.parse_level('0轉130級') == (0, 130) and spots.parse_level('一0轉128級') == (0, 128) and spots.parse_level('abc') is None)
check('spot_of_map / same_tier', spots.spot_of_map(60050) == '地雷區2' and spots.spot_of_map(1) is None and spots.same_tier('地雷區', '地雷區2') and not spots.same_tier('柯奧龜洞', '阿布龜洞'))
check('heal.SPOTS = spots.HEAL_SPOTS 9 點（含柯奧龜洞 / 阿布龜洞 / 五兄弟洞窟）', grind.heal.SPOTS == spots.HEAL_SPOTS and len(grind.heal.SPOTS) == 9 and {'柯奧龜洞', '阿布龜洞', '五兄弟洞窟'} <= set(grind.heal.SPOTS))
ns, err = grind.choose_spot('auto', 0, 130, 60050)
check('choose_spot：auto 在同檔點（地雷區2）不傳送', ns is None and not err)
ns, err = grind.choose_spot('地雷區', 0, 130, 60050)
check('choose_spot：明確指定另一點 → 傳送', ns == '地雷區')
ns, err = grind.choose_spot('地雷區', 0, 100, 500)
check('choose_spot：等級不夠 → 錯誤、不傳送', ns is None and '會被擋' in err)
ns, err = grind.choose_spot('auto', 1, 50, 500)
check('choose_spot：1 轉 auto 50 級 → 五兄弟洞窟（沿用 0 轉表）', ns == '五兄弟洞窟' and not err)
ns, err = grind.choose_spot('here', 0, 130, 1)
check('choose_spot：here 不傳送', ns is None and not err)


# ---- 假遊戲 ----
class Game:
    def __init__(self, fast=None, auto=None, enc_btn=True, hp=100, level='0轉130級', cur_map=60050):
        self.roles = list(grind.ass.ROLES)
        self.chk = {r: {'快速戰鬥': True, '自動戰鬥': True, '原地遇敵': r == 'DKBO', '夥伴助戰': False} for r in self.roles}
        for r in (fast or []):
            self.chk[r]['快速戰鬥'] = False
        for r in (auto or []):
            self.chk[r]['自動戰鬥'] = False
        self.enc, self.panel, self.sel = enc_btn, False, 'DKBO'
        self.hp, self.level, self.map = hp, level, cur_map
        self.log = []
        self.stuck = set()               # (role, item)：點了不變
        self.team_rc = [0]               # team.check 依序回傳
        self.form_rc = 0
        self.char_rc = 0
        self.tele_fail = False
        self.screens = []                # read_screen 序列：(n_px, state_dict, enc)
        self.t = 0.0
        self.heal_fail = False

    def clock(self):
        self.t += 0.3
        return self.t


def install(g, stat_missing=False):
    A, H, T, C, U = grind.ass, grind.heal, grind.team, grind.char, grind.uikit
    grind.sleep = lambda s: setattr(g, 't', g.t + s)
    grind.clock = g.clock
    U.preflight = lambda src: g.log.append('preflight') or 0
    U.fail = lambda src, rc, msg: g.log.append(f'fail:{rc}:{msg}') or rc
    C.ensure = lambda name: g.log.append('char.ensure') or g.char_rc

    def check_(size=5, leader=None, ocr=True):
        g.log.append('team.check')
        return g.team_rc.pop(0) if len(g.team_rc) > 1 else g.team_rc[0]
    T.check = check_
    T.form = lambda leader=None, size=5, **k: g.log.append('team.form') or g.form_rc
    H.set_encounter = lambda on: (g.log.append(f'enc:{on}'), setattr(g, 'enc', on))
    H.encounter_on = lambda: g.enc
    H.gui = lambda *a, **k: g.log.append('gui:' + ' '.join(a)[:30]) or 'ok'
    H.stat = lambda: {'ok': True, 'level': g.level, 'hpPct': g.hp, 'pos': f'{g.map}:24,24'}

    def tele(tab, dest, want_map, name, pre='', want_xy=None):
        g.log.append(f'teleport:{name}')
        if g.tele_fail:
            raise RuntimeError('x')
        g.map = want_map
    H.teleport = tele

    def trip(spot, no_return=False):
        g.log.append(f'heal_trip:{spot}')
        if g.heal_fail:
            raise RuntimeError('x')
        g.enc = True
    H.heal_trip = trip
    grind.walk.wait_pos = lambda tries=4, want_map=None, gap=0.5: (g.map, 24, 24)
    A.gui = lambda *a, **k: ''          # 不讓 set_many 的像素 / 失敗截圖碰到真遊戲
    A.marquee_on = lambda: False
    A.wait_not_battle = lambda no_wait=False, timeout=None: (True, '')
    A.open_panel = lambda timeout=None: g.log.append('open') or setattr(g, 'panel', True) or True
    A.panel_open = lambda: g.panel
    A.close_panel = lambda: g.log.append('close') or setattr(g, 'panel', False) or True

    def sel(role):
        assert g.panel
        g.sel = role
        return True
    A.select_role = sel
    A.read_checks = lambda items=None: dict(g.chk[g.sel])

    def setst(role, changes, no_wait=False):
        g.log.append(f'set:{role}:{",".join(changes)}')
        for i, v in changes.items():
            if (role, i) in g.stuck:
                return A.EXIT_CONFIRM, g.chk[role], '點了沒變'
            g.chk[role][i] = v
        return 0, g.chk[role], ''
    A.set_states = setst

    def apply_(role, states, changes):
        todo = {i: v for i, v in (changes or {}).items() if states.get(i) != v}
        return setst(role, todo)
    A._apply_changes = apply_
    A.get_states = lambda role, no_wait=False: g.log.append(f'get:{role}') or (0, g.chk[role], '')

    def rs():
        if g.screens:
            return g.screens.pop(0) if len(g.screens) > 1 else g.screens[0]
        return 0, {'state': 'idle', 'full': False}, g.enc
    grind.read_screen = rs
    grind.wait_banner_gone = lambda timeout=0: g.log.append('banner_wait') or True
    return g


def banner():
    return (22, {'state': 'idle', 'full': False}, True)


def idle():
    return (0, {'state': 'idle', 'full': False}, True)


def full():
    return (0, {'state': 'battle', 'full': True}, True)


def run(*a, **k):
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
        rc = grind.run(*a, **k)
    out = buf.getvalue().strip().splitlines()
    return rc, json.loads(out[-1]), buf.getvalue()


def good_screens():
    return [idle(), banner(), idle(), idle(), banner(), idle()]


grind._other_running = lambda: None

# 0) wait_banner_gone：橫幅還在就等，連 2 次沒有才回 True；一直有 → 逾時 False
_g = install(Game())
_g.screens = [banner()]
check('wait_banner_gone：一直有橫幅 → 逾時 False', ORIG_WBG(3) is False)
seq = [banner(), banner(), idle(), banner(), idle(), idle()]
calls = []
grind.read_screen = lambda: calls.append(1) or seq[min(len(calls) - 1, len(seq) - 1)]
check('wait_banner_gone：第 6 次讀才連 2 次沒有', ORIG_WBG(10) is True and len(calls) == 6, str(len(calls)))

# 1) ensure：全對 → 不改、順序 char → 關遇敵 → team → 外掛讀 → 開遇敵；成功寫 grind.json
g = install(Game())
g.screens = good_screens()
rc, j, _ = run('ensure')
order = [e for e in g.log if e.split(':')[0] in ('char.ensure', 'enc', 'team.check', 'open', 'enc')]
check('ensure 全對 → 0、不點勾選', rc == 0 and not any(e.startswith('set:') for e in g.log) and j['confirm']['events'] == 2, str(j.get('confirm')))
i = lambda s: g.log.index(s)
check('順序：char → 遇敵關 → team → 外掛 open → 遇敵開', i('char.ensure') < i('enc:False') < i('team.check') < i('open') < i('close') < i('enc:True'), str(g.log))
check('開外掛前先等橫幅消失', i('team.check') < i('banner_wait') < i('open'))
check('ensure 不傳送、不 form', not any(e.startswith(('teleport', 'team.form', 'heal_trip')) for e in g.log))
check('grind.json 寫入且最後一行 JSON', json.loads(grind.OUT.read_text(encoding='utf-8'))['rc'] == 0 and j['mode'] == 'ensure')
check('鎖檔結束時已刪', not grind.LOCK.exists())
check('外掛逐人順序：隊長最後', [e for e in g.log if e == 'open'] == ['open'])

# 2) 兩人沒開 → 只改那兩人、各只改不對的項目
g = install(Game(fast=['DKBO3'], auto=['DKBO5']))
g.screens = good_screens()
rc, j, _ = run('ensure')
sets = [e for e in g.log if e.startswith('set:')]
check('只改不對的人 / 項目', rc == 0 and sets == ['set:DKBO3:快速戰鬥', 'set:DKBO5:自動戰鬥'], str(sets))
check('一次開面板：只 open / close 各 1 次（set_many），隊長在最後', g.log.count('open') == 1 and g.log.count('close') == 1 and g.sel == 'DKBO')
check('info.fixed 記錄誰被改', j['fixed'] == {'DKBO3': ['快速戰鬥'], 'DKBO5': ['自動戰鬥']}, str(j.get('fixed')))
check('遇敵在外掛修正之後才開', g.log.index('enc:True') > g.log.index('set:DKBO5:自動戰鬥'))

# 3) 地圖禁止快速戰鬥 → 53
g = install(Game(fast=['DKBO2']))
g.stuck = {('DKBO2', '快速戰鬥')}
rc, j, _ = run('ensure')
check('快速戰鬥點了沒變 → 53，不開遇敵', rc == 53 and 'enc:True' not in g.log)

# 3b) 自動戰鬥點了沒變 → 52
g = install(Game(auto=['DKBO4']))
g.stuck = {('DKBO4', '自動戰鬥')}
rc, j, _ = run('ensure')
check('自動戰鬥失敗 → 52', rc == 52)

# 4) 遇敵開不起來 → 54
g = install(Game())
grind.heal.set_encounter = lambda on: (g.log.append(f'enc:{on}'), setattr(g, 'enc', False))
rc, j, _ = run('ensure')
check('遇敵鈕沒亮 → 54', rc == 54)

# 5) 沒看到 EXP → 55
g = install(Game())
g.screens = [idle()]
rc, j, _ = run('ensure', confirm_secs=5)
check('30 秒（這裡 5 s）內沒 EXP → 55', rc == 55 and j['confirm']['events'] == 0, str(j['confirm']))

# 5b) 只 1 次橫幅 → 55；連續同一個橫幅（多幀）只算 1 次
g = install(Game())
g.screens = [banner(), banner(), banner(), idle()]
rc, j, _ = run('ensure', confirm_secs=5)
check('同一個橫幅連續多幀只算 1 次 → 55', rc == 55 and j['confirm']['events'] == 1, str(j['confirm']))

# 6) 完整戰鬥連 2 次 → 先自動重設一次再確認；第二次仍完整戰鬥 → 56
g = install(Game())
g.screens = [full(), full()]
rc, j, _ = run('ensure', confirm_secs=5)
check('完整戰鬥 ×2 → 重設一次後仍然 → 56', rc == 56 and j.get('refixed') and g.log.count('enc:True') == 2 and g.log.count('open') == 2, str(g.log))
g = install(Game())
g.screens = [full(), full()]
rc, j, _ = run('ensure', confirm_secs=5, fix=False)
check('--no-fix：不重設 → 56', rc == 56 and g.log.count('enc:True') == 1)
g = install(Game())
g.screens = [full(), full(), idle(), banner(), idle(), banner()]
rc, j, _ = run('ensure', confirm_secs=10)
check('重設後恢復 → 0', rc == 0 and j.get('refixed'), str(j.get('confirm')))

# 7) unknown 連 3 次 → 9；3 次內夾雜非 unknown 不算
g = install(Game())
g.screens = [(0, {'state': 'unknown', 'full': False}, True)]
rc, j, _ = run('ensure', confirm_secs=10)
check('unknown ×3 → 9', rc == 9)
g = install(Game())
g.screens = [(0, {'state': 'unknown', 'full': False}, True), (0, {'state': 'unknown', 'full': False}, True), idle(), banner(), idle(), banner()]
rc, j, _ = run('ensure', confirm_secs=10)
check('unknown ×2 夾 idle → 不算 9', rc == 0)

# 8) 遇敵鈕確認期間被關 → 54
g = install(Game())
g.screens = [(0, {'state': 'idle', 'full': False}, False)]
rc, j, _ = run('ensure', confirm_secs=10)
check('確認期間遇敵鈕連 3 次關 → 54', rc == 54)

# 9) team：check 失敗 → form → 再 check 過 / 仍失敗 50
g = install(Game())
g.team_rc = [41, 0]
g.screens = good_screens()
rc, j, _ = run('ensure')
check('team.check 41 → form → check 0 → 繼續', rc == 0 and 'team.form' in g.log)
g = install(Game())
g.team_rc = [41]
g.form_rc = 42
rc, j, _ = run('ensure')
check('form 失敗 → 50，不碰外掛', rc == 50 and 'open' not in g.log and j['team_rc'] == 42)
g = install(Game())
g.team_rc = [8]
rc, j, _ = run('ensure')
check('team 回 8 → 原樣轉傳', rc == 8 and 'team.form' not in g.log)

# 10) char 失敗 → 58；char 回 9 轉傳
g = install(Game())
g.char_rc = 62
rc, j, _ = run('ensure')
check('char.ensure 失敗 → 58', rc == 58 and j['char_rc'] == 62 and 'enc:False' not in g.log)
g = install(Game())
g.char_rc = 9
rc, j, _ = run('ensure')
check('char 回 9 → 轉傳', rc == 9)

# 11) preflight 非 0 → 原碼
g = install(Game())
grind.uikit.preflight = lambda src: 9
rc, j, _ = run('ensure')
check('preflight 9 → 9，什麼都沒點', rc == 9 and not g.log)

# 12) 鎖：其他工具在跑 → 8、不動作
g = install(Game())
grind._other_running = lambda: 'petwatch（pid 1）'
rc, j, _ = run('ensure')
check('其他工具在跑 → 8、不動作', rc == 8 and not g.log)
grind._other_running = lambda: None
grind.LOCK.write_text(str(os.getpid() + 0))     # 自己的 pid 不算衝突（_other_running 已略過自己）
grind.LOCK.unlink()

# 13) check：唯讀
g = install(Game())
rc, j, _ = run('check')
check('check 全對 → 0；不點勾選、不動遇敵、不傳送', rc == 0 and not any(e.startswith(('set:', 'enc:', 'teleport', 'char.', 'team.')) for e in g.log) and g.log[-1] == 'close')
check('check 讀 5 人、隊長最後', j['states'] and list(j['states'])[-1] == 'DKBO' and len(j['states']) == 5)
g = install(Game(fast=['DKBO4']))
rc, j, _ = run('check')
check('check 有人快速戰鬥關 → 52 且指出誰', rc == 52 and j['wrong'] == {'DKBO4': ['快速戰鬥']})
g = install(Game(enc_btn=False))
rc, j, _ = run('check')
check('check 遇敵鈕關 → 54', rc == 54)

# 14) start
g = install(Game(cur_map=60050))
g.screens = good_screens()
rc, j, _ = run('start', spot='地雷區2')
check('start 已在目標點 → 不傳送', rc == 0 and not any(e.startswith('teleport') for e in g.log) and j['spot'] == '地雷區2')
g = install(Game(cur_map=60050))
g.screens = good_screens()
rc, j, _ = run('start', spot='here')
check('start --spot here → 不傳送', rc == 0 and not any(e.startswith('teleport') for e in g.log))
g = install(Game(cur_map=500, level='0轉130級'))
g.screens = good_screens()
rc, j, _ = run('start', spot='地雷區2')
check('start 換點：關遇敵 → 傳送 → 外掛 → 開遇敵', rc == 0 and g.map == 60050 and g.log.index('enc:False') < g.log.index('teleport:地雷區2') < g.log.index('open') < g.log.index('enc:True'), str(g.log))
g = install(Game(cur_map=500, level='0轉100級'))
rc, j, _ = run('start', spot='地雷區')
check('start 等級不夠 → 51、不傳送', rc == 51 and not any(e.startswith('teleport') for e in g.log))
g = install(Game(cur_map=500, level='0轉130級'))
g.tele_fail = True
rc, j, _ = run('start', spot='地雷區')
check('傳送失敗 → 51', rc == 51)
g = install(Game(cur_map=500, level='1轉5級'))
g.screens = good_screens()
rc, j, _ = run('start', spot='auto')
check('1 轉 5 級 auto → 柯奧龜洞（傳送、不再拒絕）', rc == 0 and ('teleport:柯奧龜洞' in g.log), str(g.log))
g = install(Game(cur_map=500, level='0轉100級'))
g.screens = good_screens()
rc, j, _ = run('start', spot='auto')
check('0 轉 100 級 auto → 波拉島（已在 500 → 不傳送）', rc == 0 and j['spot'] == '波拉島' and not any(e.startswith('teleport') for e in g.log))
g = install(Game(cur_map=60050, level='0轉130級'))
g.screens = good_screens()
rc, j, _ = run('start', spot='auto')
check('auto 130 級在地雷區2 → 同檔不傳送', rc == 0 and not any(e.startswith('teleport') for e in g.log))

# 15) start --heal
g = install(Game(cur_map=60050))
g.screens = good_screens()
rc, j, _ = run('start', spot='地雷區2', do_heal=True)
check('--heal：heal_trip → 再關遇敵 → 外掛 → 開遇敵（不另傳送）', rc == 0 and 'heal_trip:地雷區2' in g.log and not any(e.startswith('teleport') for e in g.log)
      and g.log.index('heal_trip:地雷區2') < g.log.index('open'), str(g.log))
g = install(Game(cur_map=60050))
g.heal_fail = True
rc, j, _ = run('start', spot='地雷區2', do_heal=True)
check('heal 失敗 → 57', rc == 57)
g = install(Game(cur_map=11001, level='0轉5級'))
g.screens = good_screens()
rc, j, _ = run('start', spot='柯奧龜洞', do_heal=True)
check('--heal 柯奧龜洞（P8 起在 heal.SPOTS）→ heal_trip 成功', rc == 0 and 'heal_trip:柯奧龜洞' in g.log, str(g.log))
g = install(Game(cur_map=11001, level='0轉5級'))
grind.heal.SPOTS = {k: v for k, v in grind.heal.SPOTS.items() if k != '柯奧龜洞'}
rc, j, _ = run('start', spot='柯奧龜洞', do_heal=True)
check('--heal 但點不在 heal.SPOTS（模擬 1920 版面）→ 1（明說）', rc == 1)
grind.heal.SPOTS = dict(spots.HEAL_SPOTS)
g = install(Game(cur_map=60050, hp=30))
g.screens = good_screens()
rc, j, _ = run('start', spot='地雷區2')
check('血量 <40 自動補血', 'heal_trip:地雷區2' in g.log)

print(f'\n失敗 {fails} 項' if fails else '\n全部通過')
sys.exit(1 if fails else 0)
