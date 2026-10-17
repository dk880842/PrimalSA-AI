#!/usr/bin/env python3
"""uikit / charstate 離線測試（不碰遊戲）：假 gui 模擬畫面像素與點擊。
用法：uv run --no-project python tools/gui/test_uikit.py"""
import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import testenv  # noqa: E402,F401  紀錄檔轉向暫存（不污染真 actions.log / quest-events.log / errlog）
import charstate  # noqa: E402
import screen_sigs  # noqa: E402
import uikit  # noqa: E402

fails = 0


def check(name, cond, extra=''):
    global fails
    print(('PASS' if cond else 'FAIL'), name, extra)
    if not cond:
        fails += 1


class Game:
    """假畫面：painted = {(x,y): (r,g,b)}；其餘點回黑色。gui('seq') 只記錄點擊，click 後可由 on_click 改畫面"""

    def __init__(self, hud=True, panel=False, unknown=False):
        self.painted, self.clicks, self.keys, self.t = {}, [], [], 0.0
        self.hud, self.panel, self.unknown = hud, panel, unknown
        self.reads = 0

    def paint(self, sig, on=True):
        for x, y, r, g, b, _ in sig:
            if on:
                self.painted[(x, y)] = (r, g, b)
            else:
                self.painted.pop((x, y), None)

    def sync(self):
        self.paint(screen_sigs.SIG_HUD, self.hud and not self.unknown)
        self.paint(screen_sigs.SIG_PANEL, self.panel)

    def gui(self, *args, note=''):
        if args[0] == 'pixel':
            self.reads += 1
            self.sync()
            pts = [tuple(int(v) for v in p.split(',')) for p in args[1].split()]
            return ' '.join('%d,%d,%d' % self.painted.get(p, (0, 0, 0)) for p in pts)
        if args[0] == 'seq':
            for part in args[1].split(';'):
                w = part.split()
                if w and w[0] == 'click':
                    xy = (int(w[1]), int(w[2]))
                    self.clicks.append(xy)
                    if xy == uikit.SWITCH.open_xy and self.hud:
                        self.panel = True
                    elif xy == uikit.SWITCH.close_xy:
                        self.panel = False
                elif w and w[0] == 'key':
                    self.keys.append(w[1])
                    if w[1] == '{ESC}':
                        self.panel = False
        return ''


def install(g):
    uikit.gui = g.gui
    uikit.sleep = lambda s: setattr(g, 't', g.t + s)
    uikit.clock = lambda: g.t
    return g


# ---- norm_char（與 watch 的 charname 同一套）----
cases = [('DKBO', 'DKBO'), ('DKBO', 'DKBO'), ('0KB0', 'DKBO'), ('0KBO', 'DKBO'), ('dkb02', 'DKBO2'), ('DKB 03', 'DKBO3'),
         ('0KB05', 'DKBO5'), ('DKBO5', 'DKBO5'), ('DKBO6', None), ('', None), (None, None), ('KB05', None), ('DKBO 2 x', None)]
for src, want in cases:
    got = uikit.norm_char(src)
    check(f'norm_char({src!r}) = {want!r}', got == want, f'got {got!r}')
check('norm_char 與 charname 規則一致（canon）', uikit.norm_char('0KBO') == charstate.norm_char('0KBO'))
check('norm_char 自訂白名單撞名 → None', uikit.norm_char('DKBO', names=['DKB0', 'DKBO']) is None)

# ---- snap_pet ----
names = {'迪基格斯': '迪基格斯', '瑪斯貝卡': '瑪斯貝卡', '金布伊': '金布伊', '火雞': '火雞', '烏力烏力': '烏力烏力', '烏力烏拉': '烏力烏拉', '布魯布魯伊': '布魯布魯伊'}
snaps = [('迪基格斯', '迪基格斯'), (' 迪基 格斯 ', '迪基格斯'), ('布魯布魯尹', '布魯布魯伊'), ('迪基格期', None), ('', None), ('XYZ', None),
         ('烏力烏', None),                        # 兩個都一樣像 → 拒絕
         ('金布', None), ('瑪斯貝卞', None)]      # 太短 / 低於 0.8 → 拒絕（騎寵另用 is_mount_like）
for src, want in snaps:
    got = uikit.snap_pet(src, names=names)
    check(f'snap_pet({src!r}) = {want!r}', got == want, f'got {got!r}')
check('is_mount_like 瑪斯貝卞', uikit.is_mount_like('瑪斯貝卞'))
check('is_mount_like 瑪斯貝卡', uikit.is_mount_like('瑪斯貝卡'))
check('is_mount_like 迪基格斯 = False', not uikit.is_mount_like('迪基格斯'))
real = uikit.pet_names()
check('Monster 表有名字', len(real) > 100, f'{len(real)} 筆')
check('snap_pet 真表：瑪斯貝卡', uikit.snap_pet('瑪斯貝卡') == '瑪斯貝卡')
check('snap_pet 真表：迪基格斯', uikit.snap_pet('迪基格斯') == '迪基格斯')

# ---- FORBIDDEN ----
g = install(Game(panel=True))
for xy, nm in [((708, 565), 'trash'), ((372, 610), 'recycle'), ((708, 630), 'lock'), ((1195, 705), 'depot_expand')]:
    try:
        uikit.safe_click(*xy, uikit.PET)
        check(f'PET 禁區 {nm} 丟 ForbiddenClick', False)
    except uikit.ForbiddenClick:
        check(f'PET 禁區 {nm} 丟 ForbiddenClick', True)
check('禁區不點擊（0 次）', g.clicks == [])
try:
    uikit.safe_click(716, 578, uikit.SWITCH)
    check('SWITCH 全部登錄預設禁止', False)
except uikit.ForbiddenClick:
    check('SWITCH 全部登錄預設禁止', True)
g.clicks.clear()
check('allow=login_all 才放行', uikit.safe_click(716, 578, uikit.SWITCH, allow=('login_all',)) and g.clicks == [(716, 578)])
g.clicks.clear()
check('刷新鈕 910,578 不在禁區', uikit.safe_click(910, 578, uikit.SWITCH) and g.clicks == [(910, 578)])
# 掃：所有 PET 卡片 / 按鈕常用座標不在禁區
for xy in [(250, 200), (390, 702), (532, 702), (672, 702), (82, 322), (1365, 440), (530, 697)]:
    try:
        uikit.check_forbidden(uikit.PET, *xy)
        ok = True
    except uikit.ForbiddenClick:
        ok = False
    check(f'PET 正常座標 {xy} 不在禁區', ok)

# ---- 面板沒開不點 ----
g = install(Game(panel=False))
check('面板沒開 safe_click 回 False', uikit.safe_click(620, 300, uikit.SWITCH) is False)
check('面板沒開 0 次點擊', g.clicks == [])
g = install(Game(panel=False, hud=False))
check('HUD 不在（對話框等）不點開啟鈕、open_panel 失敗', uikit.open_panel(uikit.SWITCH, timeout=2) is False and g.clicks == [], str(g.clicks))
# errlog #32：HUD 暫時不在（戰鬥）→ 等 HUD 回來才點；不點任何東西直到 HUD 出現
g = install(Game(panel=False, hud=False))
_orig_gui = g.gui


def _gui_hud_back(*args, note=''):
    if g.t >= 6.0:
        g.hud = True                         # 6 s 後戰鬥結束
    return _orig_gui(*args, note=note)


uikit.gui = _gui_hud_back
check('hud_wait：HUD 6 s 後回來 → 開成功、只點 1 次開啟鈕', uikit.open_panel_ex(uikit.SWITCH, hud_wait=15)[0] is True and g.clicks == [uikit.SWITCH.open_xy], str(g.clicks))
check('hud_wait：LAST_OPEN 記 hud_seen / clicked 1', uikit.LAST_OPEN.get('hud_seen') and uikit.LAST_OPEN.get('clicked') == 1, str(uikit.LAST_OPEN))
g = install(Game(panel=False, hud=False))
check('hud_wait：HUD 一直不在 → 失敗、0 次點擊、記錄等了多久', uikit.open_panel_ex(uikit.SWITCH, hud_wait=15)[0] is False and g.clicks == []
      and uikit.LAST_OPEN.get('hud_seen') is False and uikit.LAST_OPEN.get('hud_waited', 0) >= 14, str(uikit.LAST_OPEN))
g = install(Game(panel=False, hud=False))
check('hud_wait=0（預設）HUD 不在仍 4 s 逾時、不等', uikit.open_panel_ex(uikit.SWITCH)[0] is False and g.t < 5, str(g.t))
g = install(Game(panel=False, hud=True))
check('HUD 在 → 點開啟鈕開成功', uikit.open_panel(uikit.SWITCH) is True and g.clicks == [uikit.SWITCH.open_xy], str(g.clicks))
check('is_open 開著', uikit.is_open(uikit.SWITCH))
check('close_panel 成功', uikit.close_panel(uikit.SWITCH) is True and not g.panel)
g = install(Game(panel=True))
g.sync()
uikit.SWITCH.close_xy  # noqa: B018
check('已開著 open_panel 不再點', uikit.open_panel(uikit.SWITCH) is True and g.clicks == [])


class EatFirst(Game):
    """第一下開啟鈕被吃掉（面板沒開）；記錄每次點擊的虛擬時間"""

    def __init__(self, **kw):
        super().__init__(**kw)
        self.times, self.eat = [], 1

    def gui(self, *args, note=''):
        if args[0] == 'seq' and 'click' in args[1]:
            self.times.append(self.t)
            self.t += 0.2                                 # 實機每次 seq（PowerShell 往返）約 0.1～0.3 s
            if self.eat > 0:
                self.eat -= 1
                self.clicks.append(uikit.SWITCH.open_xy)
                if 'waitpix' in args[1]:                  # 實機：面板沒開時 waitpix 會等滿 WAIT_OPEN_MS 才回來（舊假畫面不耗時，漏掉 S3 rc 40 的根因）
                    self.t += uikit.WAIT_OPEN_MS / 1000
                return ''
        return super().gui(*args, note=note)


g = install(EatFirst(panel=False, hud=True))
ok_ = uikit.open_panel(uikit.SWITCH, timeout=4.0)
check('開面板第 1 下被吃掉：隔 >= RECLICK_S 才點第 2 下（不連點）並在 4 s timeout 內開成功（S3 rc 40 根因：舊版第 2 下要等 waitpix 1.5 s + 2.5 s，超過 timeout）',
      ok_ is True and len(g.times) == 2 and uikit.RECLICK_S <= g.times[1] - g.times[0] < 4.0, f'times={g.times}')
g = install(EatFirst(panel=False, hud=True))
g.eat = 99
ok_ = uikit.open_panel(uikit.SWITCH, timeout=4.0)
check('一直點不開：timeout 4 秒內最多 2 下、每下間隔 >= RECLICK_S', ok_ is False and len(g.times) <= 2 and all(b - a >= uikit.RECLICK_S for a, b in zip(g.times, g.times[1:])), f'times={g.times}')


class AcceptGap(EatFirst):
    """2026-10-12 解救老爺爺 / 龍的巢穴 / 夢幻洞窟：任務「接受」後開切換面板，第 1 下被吃掉，之後 HUD 有一段時間不在（點擊後 1.5～6 s）"""

    def gui(self, *args, note=''):
        if self.times:
            dt = self.t - self.times[0]
            self.hud = not (1.5 <= dt < 6.0)
        return super().gui(*args, note=note)


g = install(AcceptGap(panel=False, hud=True))
ok_ = uikit.open_panel_ex(uikit.SWITCH, hud_wait=15)[0]
check('接受後 HUD 消失：hud_wait 時不逾時，HUD 回來後補點第 2 下並開成功（舊版 4 s 逾時 rc 40）', ok_ is True and len(g.times) == 2 and g.times[1] - g.times[0] >= 6.0
      and uikit.LAST_OPEN.get('hud_lost_after_click') is True, f'times={g.times} {uikit.LAST_OPEN}')
g = install(AcceptGap(panel=False, hud=True))
ok_ = uikit.open_panel_ex(uikit.SWITCH)[0]
check('同情況 hud_wait=0（一般面板）→ 照舊 4 s 逾時、只點 1 下（不改變其他面板行為）', ok_ is False and len(g.times) == 1, f'times={g.times}')
g = install(AcceptGap(panel=False, hud=True))
g.eat = 99
ok_ = uikit.open_panel_ex(uikit.SWITCH, hud_wait=15)[0]
check('HUD 回來後一直點不開 → 最多 3 下就放棄（不無限等）', ok_ is False and len(g.times) <= 3 and g.t < 30, f'times={g.times} t={g.t}')
check('TEAMPANEL 有特徵、✕ 在 1250,77', bool(uikit.TEAMPANEL.sig) and uikit.TEAMPANEL.close_xy == (1250, 77))
check('切換面板開著時 TEAMPANEL 不會誤判開著', uikit.is_open(uikit.TEAMPANEL) is False)
try:
    uikit.safe_click(720, 670, uikit.TEAMPANEL)
    check('TEAMPANEL 解散鈕 720,670 在禁區', False)
except uikit.ForbiddenClick:
    check('TEAMPANEL 解散鈕 720,670 在禁區', True)

# ---- preflight ----
import battleguard  # noqa: E402
import layout  # noqa: E402
import netwatch  # noqa: E402

layout.current = lambda: '2880x1659'
netwatch.guard = lambda src, **kw: {'status': 'ok'}
battleguard.LOCK_FILE = Path(tempfile.mkdtemp()) / 'battle.lock'

g = install(Game(hud=True))
uikit.watch_state = lambda max_age=1.0: None            # 預設 watch 不可用 → 走完整檢查
uikit.watch_screen = lambda max_age=1.0: None
check('preflight 主畫面 = 0', uikit.preflight('t') == 0)
import verifyhalt  # noqa: E402
_TRIPS = []
_real_vh_trip = verifyhalt.trip
verifyhalt.trip = lambda reason, src='', **kw: _TRIPS.append((reason, src)) or True
g = install(Game(unknown=True))
g.painted[screen_sigs.BLACK_PTS[0]] = (90, 90, 90)          # 假畫面其餘點是黑色 = 會被當全黑轉場；點亮一點 = 真的不認得
rc = uikit.preflight('t')
check('preflight unknown 連 3 次 → 9（每次多讀轉場特徵 + 已知彈窗 + 已知面板殘留各一次，最後 trip_verify 再現場確認一次答題介面）',
      rc == 9 and g.reads == 13 and g.t >= 10.0, f'rc={rc} reads={g.reads} t={g.t}')
check('preflight unknown 時 0 點擊', g.clicks == [])
check('preflight unknown 連 3 次但沒認出答題介面 → 不設驗證停手旗標（2026-10-16：不設旗標，2026-10-18 拿掉 watch 兜底）', _TRIPS == [], str(_TRIPS))
# 答題介面（合成模擬圖，fixtures/verify_px.json）：preflight 第一次 unknown 就 9 + 設旗標，不等 3 次
_vfx = json.loads((Path(__file__).resolve().parent / 'fixtures' / 'verify_px.json').read_text(encoding='utf-8'))
_vpts = [tuple(p) for p in _vfx['points']]


def _paint(g, rel):
    _h = next(s_ for s_ in _vfx['samples'] if s_['f'] == rel)['px']
    g.painted.update({pt: (int(_h[i * 6:i * 6 + 2], 16), int(_h[i * 6 + 2:i * 6 + 4], 16), int(_h[i * 6 + 4:i * 6 + 6], 16)) for i, pt in enumerate(_vpts)})


g = install(Game(unknown=True))
_paint(g, 'npcanswer-extract/mock_battle_k10546_+0+0.png')
_TRIPS.clear()
rc = uikit.preflight('t')
check('preflight 答題介面 → 立刻 9（不等 3 次、不睡）+ 設旗標、0 點擊', rc == 9 and g.reads <= 3 and g.t < 5.0 and g.clicks == [] and len(_TRIPS) == 1
      and '答題' in _TRIPS[0][0], f'rc={rc} reads={g.reads} t={g.t} {_TRIPS}')
_TRIPS.clear()
check('trip_verify：現場認出答題介面 → 設旗標', uikit.trip_verify('測試', 't') is True and len(_TRIPS) == 1 and '正面命中' in _TRIPS[0][0])
g = install(Game(unknown=True))
_paint(g, 'kr322.png')
_TRIPS.clear()
check('trip_verify：別的提示窗（任務條件不達標）→ 不設旗標、回 False', uikit.trip_verify('測試', 't') is False and _TRIPS == [])
_keep_qn = uikit.quiz_now
uikit.quiz_now = lambda: (_ for _ in ()).throw(RuntimeError('讀不到'))
check('trip_verify：讀畫面例外 → 當沒認出、不設旗標', uikit.trip_verify('測試', 't') is False and _TRIPS == [])
uikit.quiz_now = _keep_qn
_TRIPS.clear()
g = install(Game(unknown=True))
_paint(g, 'net1.png')
rc = uikit.preflight('t')
check('preflight 網路異常窗（netwatch.guard 沒處理掉時）→ 照舊 9、不設旗標、0 點擊', rc == 9 and _TRIPS == [] and g.clicks == [], f'rc={rc} {_TRIPS}')
verifyhalt.trip = _real_vh_trip
# 背包上疊道具說明彈窗（2026-10-16 p2 02:40:05 誤停那張，真實取點）：已知彈窗 → 0、不計次、不點
_ifx = json.loads((Path(__file__).resolve().parent / 'fixtures' / 'bag_itempop_px.json').read_text(encoding='utf-8'))
_ipts = [tuple(p) for p in _ifx['points']]
for _f, _want in (('clients/PrimalSA2/watch-alerts/unknown-1792089604.png', 0), ('clients/PrimalSA2/s2.png', 0), ('kr322.png', 9)):
    _h = next(s for s in _ifx['samples'] if s['f'] == _f)['px']
    g = install(Game(unknown=True))
    g.painted.update({pt: (int(_h[i * 6:i * 6 + 2], 16), int(_h[i * 6 + 2:i * 6 + 4], 16), int(_h[i * 6 + 4:i * 6 + 6], 16)) for i, pt in enumerate(_ipts)})
    rc = uikit.preflight('t')
    check(f'preflight {_f.split("/")[-1]}（{"道具彈窗 / 數量輸入窗" if _want == 0 else "提示窗"}）→ {_want}、0 點擊', rc == _want and g.clicks == [], f'rc={rc}')

# 轉場（載入圖 / 全黑）：不計次、等它過去；超過 TRANSITION_MAX_S 才照舊計次 → 9
_bfx = json.loads((Path(__file__).resolve().parent / 'fixtures' / 'loading_bar_px.json').read_text(encoding='utf-8'))
_load_px = {tuple(pt): tuple(c) for pt, c in zip(_bfx['pts'], next(x for x in _bfx['samples'] if x['file'] == 'p4/tpS0.png')['px'])}


class Loading(Game):
    """前 until 秒是英文版載入圖（真實取點 tpS0），之後回主畫面"""

    def __init__(self, until):
        super().__init__(unknown=True)
        self.until = until

    def sync(self):
        self.unknown = self.t < self.until
        super().sync()
        for pt, c in _load_px.items():
            if self.unknown:
                self.painted[pt] = c
            else:
                self.painted.pop(pt, None)


g = install(Loading(20.0))
rc = uikit.preflight('t')
check('preflight 載入圖 20 秒後回主畫面 → 0（載入期間不計次）', rc == 0 and g.t >= 20.0 and g.clicks == [], f'rc={rc} t={g.t}')
g = install(Loading(1e9))
rc = uikit.preflight('t')
check('preflight 載入圖一直不結束 → 上限後照舊計次 → 9', rc == 9 and g.t >= screen_sigs.TRANSITION_MAX_S and g.clicks == [], f'rc={rc} t={g.t}')


class Flaky(Game):
    """前兩次 unknown、第三次恢復 → 不退 9"""

    def gui(self, *a, **k):
        if a[0] == 'pixel':
            self.unknown = self.reads < 2
        return super().gui(*a, **k)


g = install(Flaky())
check('preflight unknown 2 次後恢復 → 0', uikit.preflight('t') == 0)
layout.current = lambda: '1920x1017'
check('preflight 版面不符 → 2', uikit.preflight('t') == 2)
layout.current = lambda: '2880x1659'
battleguard.LOCK_FILE.write_text(json.dumps({'pid': __import__('os').getpid(), 'start': __import__('time').time(), 'note': 'x'}), encoding='utf-8')
g = install(Game())
check('preflight battle.lock 有效 → 8', uikit.preflight('t') == 8)
battleguard.LOCK_FILE.unlink()

# ---- preflight 快路徑（watch 狀態夠新才採用）----
import time as _t  # noqa: E402


def wst(state='idle', annot=None, alerts=None, verify=False, layout_='2880x1659', running=True):
    return ({'flags': {'verify_suspect': verify}, 'alerts': alerts or [], 'game': {'layout': layout_, 'running': running}},
            {'state': state, 'annot': annot or []})


def fastcase(label, want, **kw):
    st, sc = wst(**kw)
    uikit.watch_state = lambda max_age=1.0: st
    uikit.watch_screen = lambda max_age=1.0: sc
    g = install(Game(hud=False, unknown=True))      # 畫面全是 unknown：走完整檢查會退 9；走快路徑不讀圖
    rc = uikit.preflight('t')
    check(f'preflight 快路徑 {label}', (rc == 0 and g.reads == 0) if want else (rc == 9), f'rc={rc} reads={g.reads}')


fastcase('idle 且無警報 → 採用、0 次讀圖', True)
fastcase('panel 也可', True, state='panel')
fastcase('unknown → 不採用', False, state='unknown')
fastcase('battle → 不採用', False, state='battle')
fastcase('有 annot（登入 / 提示視窗）→ 不採用', False, annot=['login'])
fastcase('verify_suspect → 不採用', False, verify=True)
fastcase('alerts 非空 → 不採用', False, alerts=[{'kind': 'verify'}])
fastcase('版面不符 → 不採用', False, layout_='1920x1017')
fastcase('遊戲沒跑 → 不採用', False, running=False)
uikit.watch_state = lambda max_age=1.0: None
g = install(Game(hud=False, unknown=True))
check('watch 不在 → 完整檢查（退 9）', uikit.preflight('t') == 9)
st, sc = wst()
uikit.watch_state = lambda max_age=1.0: st
uikit.watch_screen = lambda max_age=1.0: sc
battleguard.LOCK_FILE.write_text(json.dumps({'pid': __import__('os').getpid(), 'start': _t.time(), 'note': 'x'}), encoding='utf-8')
check('快路徑也檢查 battle.lock → 8', uikit.preflight('t') == 8)
battleguard.LOCK_FILE.unlink()
uikit.watch_state = lambda max_age=1.0: None
uikit.watch_screen = lambda max_age=1.0: None

# ---- open / close 用 waitpix 取代固定等待 ----
class WaitGame(Game):
    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        self.seqs = []

    def gui(self, *args, note=''):
        if args[0] == 'seq':
            self.seqs.append(args[1])
        return super().gui(*args, note=note)


g = install(WaitGame(hud=True))
check('open_panel_ex 回 (True, 本來沒開)', uikit.open_panel_ex(uikit.SWITCH) == (True, False))
check('開面板 seq 用 waitpix、不再 wait 700', any('waitpix' in q and 'click 763 760' in q for q in g.seqs) and not any('wait 700' in q for q in g.seqs), str(g.seqs))
g.seqs.clear()
check('close_panel(known_open) 用 waitpix ✕ 消失、成功', uikit.close_panel(uikit.SWITCH, known_open=True) is True and not g.panel and any('waitpix' in q and '!' in q for q in g.seqs), str(g.seqs))
# ---- close_panel 等待拉長：面板延遲關閉 ----
class DelayGame(Game):
    """點 ✕ 後 delay 秒才關（None = 永遠不關）；waitpix 依假時鐘模擬輪詢，回 ok 行或逾時空字串"""

    def __init__(self, delay, **k):
        super().__init__(**k)
        self.delay, self.close_at, self.seqs = delay, None, []

    def _tick(self):
        if self.close_at is not None and self.t >= self.close_at:
            self.panel, self.close_at = False, None

    def gui(self, *args, note=''):
        self._tick()
        if args[0] == 'seq':
            self.seqs.append(args[1])
            out = ''
            for part in args[1].split(';'):
                w = part.split()
                if w and w[0] == 'click':
                    xy = (int(w[1]), int(w[2]))
                    self.clicks.append(xy)
                    if xy == uikit.SWITCH.close_xy and self.panel and self.delay is not None:
                        self.close_at = self.t + self.delay
                elif w and w[0] == 'waitpix':
                    limit = int(w[1]) / 1000
                    if self.close_at is not None and self.close_at - self.t <= limit:
                        self.t = self.close_at
                        self._tick()
                        out = 'ok 0'
                    else:
                        self.t += limit
                        self._tick()
            return out
        return super().gui(*args, note=note)


g = install(DelayGame(0.0, hud=True, panel=True))
t0 = g.t
check('點完立即消失 → 立即返回、只點 1 次、不耗時', uikit.close_panel(uikit.SWITCH, known_open=True) is True and g.clicks.count(uikit.SWITCH.close_xy) == 1 and g.t - t0 < 0.2, f'{g.clicks} t={g.t}')
g = install(DelayGame(1.2, hud=True, panel=True))
check('面板 1.2 秒才關 → 只點 1 次 ✕、成功', uikit.close_panel(uikit.SWITCH, known_open=True) is True and g.clicks.count(uikit.SWITCH.close_xy) == 1 and 1.1 < g.t < 1.5, f'{g.clicks} t={g.t}')
g = install(DelayGame(None, hud=True, panel=True))
r = uikit.close_panel(uikit.SWITCH, known_open=True)
check('面板一直不關 → 點 2 次 ✕ 後失敗', r is False and g.clicks.count(uikit.SWITCH.close_xy) == 2, f'{r} {g.clicks}')
g = install(DelayGame(2.6, hud=True, panel=True))
uikit.close_panel(uikit.SWITCH, known_open=True)
check('逾時邊界：2.6 秒才關 → 逾時後重讀已關（不點第二次 ✕ 到空處）或至多 2 次', g.clicks.count(uikit.SWITCH.close_xy) <= 2 and not g.panel, str(g.clicks))
g = install(DelayGame(0.0, hud=True, panel=False))
check('面板本來就沒開 → 不點', uikit.close_panel(uikit.SWITCH) is True and g.clicks == [])

g = install(WaitGame(hud=True, panel=True))
check('已開著 open_panel_ex → (True, True)、不點', uikit.open_panel_ex(uikit.SWITCH) == (True, True) and g.clicks == [])
uikit.timing_start()
uikit.mark('a')
check('mark 記分段', uikit.timing_get()[0][0] == 'a')
uikit._stages = None

# ---- fail / snap 檔清理 ----
import errlog  # noqa: E402

errlog.LOG = Path(tempfile.mkdtemp()) / 'errlog.jsonl'
check('fail 回 rc 並寫 errlog', uikit.fail('t', 42, '測試') == 42 and errlog.LOG.exists())
d = Path(tempfile.mkdtemp())
(d / 'old.png').write_bytes(b'x')
(d / 'new.png').write_bytes(b'x')
(d / 'keep.txt').write_bytes(b'x')
import os  # noqa: E402
import time  # noqa: E402

os.utime(d / 'old.png', (time.time() - 5 * 86400,) * 2)
check('cleanup_old_shots 只刪舊 png', uikit.cleanup_old_shots(folder=d) == 1 and (d / 'new.png').exists() and (d / 'keep.txt').exists())

# ---- charstate（格式 = watchstate.write_current_char）----
tmp = Path(tempfile.mkdtemp()) / 'current-char.json'
import watchstate  # noqa: E402

watchstate.CURCHAR_FILE = tmp
check('charstate.write 正規化後寫入', charstate.write('0KBO', src='test', path=tmp) and json.loads(tmp.read_text(encoding='utf-8'))['name'] == 'DKBO')
d = charstate.read(path=tmp)
check('charstate.read 欄位 name/ts/src', d and d['name'] == 'DKBO' and d['src'] == 'test' and isinstance(d['ts'], float))
check('watchstate.read_current_char 同格式可讀', watchstate.read_current_char(tmp) == d)
check('charstate.read max_age 過期 → None', charstate.read(max_age=10, path=tmp, now=lambda: d['ts'] + 11) is None and charstate.read(max_age=10, path=tmp, now=lambda: d['ts'] + 5))
check('不在白名單不寫', charstate.write('DKBO9', path=tmp) is False and charstate.read(path=tmp)['name'] == 'DKBO')
check('charstate.clear（未知）→ read None；重複 clear 也成功', charstate.clear(tmp) and charstate.read(path=tmp) is None and charstate.clear(tmp))
check('無暫存檔殘留', not list(tmp.parent.glob('*.tmp')))

# ---- 角色真名 DKBO（字母 O）：DKB0 / DKBO 寫法都要對到真名 ----
import ass  # noqa: E402
check('白名單預設是真名 DKBO…', charstate.DEFAULT_CHARS == ['DKBO', 'DKBO2', 'DKBO3', 'DKBO4', 'DKBO5'] and uikit.CHARS == charstate.DEFAULT_CHARS)
for src in ('DKB0', 'DKBO', 'dkbo', '0KBO', 'DKB 0'):
    check(f'norm_char({src!r}) → DKBO', charstate.norm_char(src) == 'DKBO')
    check(f'display({src!r}) → DKBO', charstate.display(src) == 'DKBO')
check('display(DKB05) → DKBO5', charstate.display('DKB05') == 'DKBO5')
check('same(DKB0, DKBO) / same(DKB02, DKBO2)', charstate.same('DKB0', 'DKBO') and charstate.same('DKB02', 'DKBO2') and not charstate.same('DKB02', 'DKBO3'))
check('ass.norm_role：DKB0 / DKBO / dkb05 → 真名', ass.norm_role('DKB0') == 'DKBO' and ass.norm_role('DKBO') == 'DKBO' and ass.norm_role('dkb05') == 'DKBO5' and ass.norm_role('DKB06') is None)
check('charstate.write(DKB02) 寫入真名 DKBO2', charstate.write('DKB02', path=tmp) and charstate.read(path=tmp)['name'] == 'DKBO2')

# known_panel / close_known_panel（2026-10-13 背包面板殘留誤報 rc 9；實機取點 fixtures/stray_px.json）
_fx = json.loads((HERE / 'fixtures' / 'stray_px.json').read_text(encoding='utf-8'))['images']
_keep_px, _keep_close = uikit.px, uikit.close_panel


def _use(rel):
    m = {tuple(int(v) for v in k.split(',')): tuple(c) for k, c in _fx[rel]['px'].items()}
    uikit.px = lambda pts: [m.get(tuple(p), (0, 0, 0)) for p in pts]


_use('quest-log/080443-UNKNOWN.png')
check('known_panel：背包頁殘留 → bag', uikit.known_panel() == 'bag')
_use('quest-log/075938-UNKNOWN.png')
check('known_panel：倉庫頁殘留（同一個背包面板）→ bag', uikit.known_panel() == 'bag')
import bag as _bag  # noqa: E402
check('  倉庫頁樣本：BAGDEPOT 認得、BAG 不認得（分頁特徵點 180,390 / 660,510）', uikit.is_open(_bag.DEPOT) and not uikit.is_open(_bag.BAG))
_use('quest-log/080443-UNKNOWN.png')
check('  背包頁樣本：BAG 認得、BAGDEPOT 不認得', uikit.is_open(_bag.BAG) and not uikit.is_open(_bag.DEPOT))
for _rel in ('quest-log/060801-UNKNOWN.png', 'ui-log/080426-bag-nopopup.png', 'watch-alerts/unknown-1791843913.png', 'quest-log/060732-boss-done.png'):
    _use(_rel)
    check(f'known_panel：{_rel} → None（不是可關的面板）', uikit.known_panel() is None)
for _rel in ('quest-log/082154-UNKNOWN.png', 'ui-log/082145-bag-tab.png'):
    _use(_rel)
    check(f'known_panel：背包殘留 + 底部「關閉 + 頭像」列蓋住舊點 730,688（{_rel}，2026-10-14 rc 9 / 龍王 rc 90）→ bag', uikit.known_panel() == 'bag')
    import bag as _bag
    check(f'  {_rel}：BAG（背包頁）認得、BAGDEPOT 不認得', uikit.is_open(_bag.BAG) and not uikit.is_open(_bag.DEPOT))
# 背包 / 刪除模式特徵點不准落在底部「關閉 + 頭像」列（約 x 150～780、y 672～800；戰鬥刷新角色叫出、戰後可能殘留，疊在面板上）
_ROW = (150, 672, 630, 128)
import bag as _bag  # noqa: E402
_hit = [(p.name, s[:2]) for p in (_bag.BAGANY, _bag.BAG, _bag.DEPOT, _bag.DELMODE) for s in p.sig if uikit.in_rect(s[0], s[1], _ROW)]
check('背包 / 倉庫 / 刪除模式 Panel 特徵點都不在底部關閉列範圍', not _hit, str(_hit))
uikit.px = lambda pts: None
check('known_panel：讀不到 → None', uikit.known_panel() is None)
_closed = []
uikit.close_panel = lambda p, known_open=False: (_closed.append((p.name, p.close_xy)), True)[1]
_use('quest-log/080443-UNKNOWN.png')
check('close_known_panel：背包 → 點 ✕ 1280,113（bag.BAGANY）', uikit.close_known_panel() == 'bag' and _closed == [('BAGANY', (1280, 113))], str(_closed))
check('known_panel_obj：沒專用 Panel 的（任務詳情）用 PANEL_X ✕', uikit.known_panel_obj('quest').close_xy == screen_sigs.PANEL_X['quest'][:2]
      and uikit.known_panel_obj('pet') is uikit.PET and uikit.known_panel_obj('nope') is None)
check('known_panel_obj：NPC 商店用 SHOP_X ✕（1207,107）', uikit.known_panel_obj('shop').close_xy == screen_sigs.SHOP_X[:2] == (1207, 107))
_pts_shop = screen_sigs.points() + screen_sigs.panel_points()
_shop_cols = {(x, y): (r, g, b) for x, y, r, g, b in screen_sigs.SHOP_PTS}
_shop_cols[screen_sigs.SHOP_X[:2]] = screen_sigs.SHOP_X[2:5]
uikit.px = lambda pts: [_shop_cols.get(pt, (70, 70, 70)) for pt in pts]
_closed.clear()
check('close_known_panel：NPC 商店 → 點 ✕ 1207,107（只關、不碰購買鈕）', uikit.known_panel() == 'shop' and uikit.close_known_panel() == 'shop' and _closed == [('SHOP', (1207, 107))], str(_closed))
# 每日任務委託面板 / 快速合成彈窗（2026-10-17：開著時 char.switch 的 preflight 連 3 次不認得、不點卡片）
for _nm, _sig, _xy in (('daily', screen_sigs.DAILY_SIG, (1193, 98)), ('qcraft', screen_sigs.QCRAFT_SIG, (1080, 156))):
    _cols = {(x, y): (r, g, b) for x, y, r, g, b, _t in _sig}
    uikit.px = lambda pts, _c=_cols: [_c.get(tuple(pt), (70, 70, 70)) for pt in pts]
    _closed.clear()
    check(f'close_known_panel：{_nm} → 點 ✕ {_xy}', uikit.close_known_panel() == _nm and _closed == [(_nm.upper(), _xy)], str(_closed))

# preflight 遇到已知面板殘留 → 關掉再檢查、不計次（2026-10-15 PrimalSA2：bag.py 留下背包面板 → pet.py list 連 3 次不認得 → verify-halt）
_keep_pf = (uikit.screen, uikit.transition_now, uikit.sleep, uikit.trip_verify)
_pf = {'open': True, 'trip': []}
uikit.screen = lambda: {'state': 'unknown' if _pf['open'] else 'idle'}
uikit.transition_now = lambda: False
uikit.sleep = lambda s: None
uikit.trip_verify = lambda msg, src: _pf['trip'].append(msg)
_closed.clear()


def _close_stray(p, known_open=False):
    _closed.append((p.name, p.close_xy))
    _pf['open'] = False
    uikit.px = lambda pts: None                     # 關掉後面板特徵消失
    return True


uikit.close_panel = _close_stray
_use('quest-log/080443-UNKNOWN.png')
rc = uikit.preflight('t')
check('preflight：背包面板殘留（不認得）→ 點 ✕ 關掉後 0，不設驗證停手', rc == 0 and _closed == [('BAGANY', (1280, 113))] and not _pf['trip'], f'rc={rc} {_closed} {_pf}')
_closed.clear()
_pf.update(open=True, trip=[])
uikit.close_panel = lambda p, known_open=False: (_closed.append(p.name), True)[1]   # ✕ 點了但畫面還是一樣（關不掉）
_use('quest-log/080443-UNKNOWN.png')
rc = uikit.preflight('t')
check(f'preflight：已知面板關不掉 → 最多關 {uikit.PREFLIGHT_CLOSE_MAX} 次，之後照舊連 3 次 → 9', rc == 9 and len(_closed) == uikit.PREFLIGHT_CLOSE_MAX and _pf['trip'], f'rc={rc} {_closed}')
_closed.clear()
_pf.update(open=True, trip=[])
_use('quest-log/060801-UNKNOWN.png')                # 不是已知面板（可能是驗證視窗）→ 不碰
rc = uikit.preflight('t')
check('preflight：不認得且不是已知面板 → 不點、照舊 9', rc == 9 and not _closed, f'rc={rc} {_closed}')
# preflight 遇到戰鬥上疊寵物資訊浮窗（2026-10-17 p2）→ 同轉場等它消失、不計次；一直不消失 → TRANSITION_MAX_S 後照舊 9
_keep_tip = (uikit.screen_annot, uikit.clock)
_tt = {'t': 0.0, 'until': 20.0}
uikit.clock = lambda: _tt['t']
uikit.sleep = lambda s_: _tt.__setitem__('t', _tt['t'] + s_)
uikit.screen = lambda: {'state': 'unknown' if _tt['t'] < _tt['until'] else 'idle'}
uikit.screen_annot = lambda: ({'state': 'unknown'}, ['battle_tip'])
_keep_ckp = uikit.close_known_panel
uikit.close_known_panel = lambda: None
_pf.update(trip=[])
rc = uikit.preflight('t', fast=False)
check('preflight：戰鬥寵物資訊浮窗 20 秒後消失 → 等完回 0、不設停手', rc == 0 and not _pf['trip'] and _tt['t'] >= 20, f'rc={rc} t={_tt["t"]} {_pf}')
_tt.update(t=0.0, until=1e9)
rc = uikit.preflight('t', fast=False)
check('preflight：浮窗一直不消失 → TRANSITION_MAX_S 後照舊 9', rc == 9 and _tt['t'] >= screen_sigs.TRANSITION_MAX_S, f'rc={rc} t={_tt["t"]}')
uikit.screen_annot, uikit.clock = _keep_tip
uikit.close_known_panel = _keep_ckp
(uikit.screen, uikit.transition_now, uikit.sleep, uikit.trip_verify) = _keep_pf
uikit.px, uikit.close_panel = _keep_px, _keep_close

print('失敗', fails)
sys.exit(1 if fails else 0)
