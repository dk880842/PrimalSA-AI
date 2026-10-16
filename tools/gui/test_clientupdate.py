#!/usr/bin/env python3
"""clientupdate.py 離線測試（不碰遊戲、不開關程序）：假的「程序 / 視窗 / 畫面」狀態機跑完整流程，
外加 netwatch 版本錯誤黑條偵測（version_bar / relogin on_version / clear_halt）、伺服器已關閉提示、命令列接 clientupdate。
用法：uv run --no-project python tools/gui/test_clientupdate.py"""
import contextlib
import io
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import testenv  # noqa: E402,F401
import clientupdate as cu  # noqa: E402
import netwatch  # noqa: E402

tmp = Path(tempfile.mkdtemp())
netwatch.CACHE = tmp
netwatch.HALT = tmp / 'netwatch.halt'
netwatch.STATE = tmp / 'netwatch.json'
netwatch.ACT_LOCK = tmp / 'act.lock'
netwatch.log = lambda *a, **k: None
netwatch.errlog.add = lambda *a, **k: 1
netwatch.errlog.fix = lambda *a, **k: None
netwatch.actlog.add = lambda *a, **k: None
cu.UPDATE_LOCK = tmp / 'client-update.lock'
cu.errlog.add = lambda *a, **k: 1
cu.actlog.add = lambda *a, **k: None

fails = 0


def check(name, cond, extra=''):
    global fails
    print(('PASS ' if cond else 'FAIL ') + name + (f' {extra}' if extra and not cond else ''))
    if not cond:
        fails += 1


# ---------------- 純函式 ----------------
L = lambda t, y=200: {'text': t, 'y': y, 'x': 340}     # noqa: E731
check('small_kind：Tip download file / size → tip', cu.small_kind([L('Tip'), L('download file:3 size:12.5M')]) == 'tip')
check('small_kind：更新完畢需要重啟用戶端 → restart', cu.small_kind([L('更新完畢需要重啟用戶端'), L('重啟')]) == 'restart')
check('small_kind：上方「最新公告」→ notice', cu.small_kind([L('最新公告', 40)]) == 'notice')
check('small_kind：登入畫面左下木牌「最新 公告」（y≈330）不算公告窗', cu.small_kind([L('最新 公告', 330), L('登錄', 290)]) is None)
check('small_kind：下載進度 % → busy', cu.small_kind([L('45%')]) == 'busy')
check('small_kind：空 → None', cu.small_kind([]) is None and cu.small_kind(None) is None)
check('server_closed_text：「提示：伺服 器已關閉！」→ True', netwatch.server_closed_text('提示：伺服 器已關閉！'))
check('server_closed_text：網路異常 → False', not netwatch.server_closed_text('網路異常，是否重連?'))

N = len(netwatch.VERSION_PTS)
LOGO = [(200, 160, 60)] * N
BAR = [(20, 20, 20)] * N
check('version_bar：Logo → 黑條 = True', netwatch.version_bar(LOGO, BAR))
check('version_bar：沒變化 = False', not netwatch.version_bar(LOGO, LOGO))
check('version_bar：基準本來就暗（暗 → 暗）= False', not netwatch.version_bar(BAR, BAR))
check('version_bar：只有幾點變暗（字 / 游標）= False', not netwatch.version_bar(LOGO, BAR[:3] + LOGO[3:]))
check('version_bar：基準讀不到 + 幾乎全黑 = True；讀不到 cols = False', netwatch.version_bar(None, [(10, 10, 10)] * N)
      and not netwatch.version_bar(LOGO, None))


# ---------------- netwatch.relogin 版本錯誤 ----------------
class Login:
    """假登入畫面：按登錄後 flash = 黑條；stay = 一直停在登入畫面"""
    def __init__(self, flash=True, stay=True):
        self.flash, self.stay, self.calls, self.clicked = flash, stay, [], False
        self.halt_at_click = None

    def gui(self, *a, note=''):
        self.calls.append(a)
        if a[0] == 'click' and (a[1], a[2]) == tuple(map(str, netwatch.LOGIN_BTN)):
            self.clicked = True
            self.halt_at_click = netwatch.HALT.exists()
        return ''

    def match(self, sig):
        return sig == netwatch.SIG_LOGIN and (self.stay or not self.clicked)

    def pixels(self, pts):
        return BAR if (self.clicked and self.flash) else LOGO


T = [0.0]
netwatch.time.sleep = lambda s: T.__setitem__(0, T[0] + s)
netwatch.time.time = lambda: T.__setitem__(0, T[0] + 0.05) or T[0]


def nw_run(sc, **kw):
    netwatch.gui = sc.gui
    netwatch._match = sc.match
    netwatch._pixels = sc.pixels
    netwatch._dark_count = lambda box: 50
    netwatch.hud_ok = lambda: False
    netwatch.STATE.write_text('{"fails": 0}')
    with contextlib.redirect_stdout(io.StringIO()):
        return netwatch.relogin('t', **kw)


LOGIN = ('click', *map(str, netwatch.LOGIN_BTN))
netwatch.HALT.write_text('old')
s = Login(flash=True)
r = nw_run(s, on_version='return', clear_halt=True)
check('relogin on_version=return：黑條 → status version、flash', r.get('status') == 'version' and r.get('flash') is True, r)
check('  clear_halt：按登錄前已刪 netwatch.halt、之後沒再寫', s.halt_at_click is False and not netwatch.HALT.exists())
check('  只點了登錄（沒點帳號 / 密碼欄）', s.calls == [LOGIN], s.calls)
check('  版本錯誤不算登錄失敗（login_fails 沒加）', netwatch._load().get('login_fails', 0) == 0)
s = Login(flash=True)
r = nw_run(s)
check('relogin 預設（guard）：黑條 → halt、帶 version、理由提示 clientupdate', r.get('status') == 'halt' and r.get('version')
      and 'clientupdate' in r.get('reason', '') and netwatch.VERSION_HALT in netwatch.HALT.read_text(encoding='utf-8'), r)
netwatch.HALT.unlink(missing_ok=True)
s = Login(flash=False, stay=True)
r = nw_run(s, on_version='return')
check('relogin on_version=return：沒黑條但停在登入畫面 15 秒 → version（flash False）', r.get('status') == 'version' and r.get('flash') is False, r)
netwatch.HALT.write_text('old')
s = Login(flash=False, stay=True)
r = nw_run(s, on_version='return', clear_halt=False)
check('clear_halt=False：netwatch.halt 不刪', s.halt_at_click is True)
netwatch.HALT.unlink(missing_ok=True)


# ---------------- clientupdate 狀態機 ----------------
class World:
    """程序 / 視窗 / 畫面。stages：開程序後依序經過的小視窗畫面；update=True 時第一次開要下載 + 重啟"""
    def __init__(self, running=True, size='2880x1659', screen='login', update=True, versions=1, grind_rc=0):
        self.running, self.size, self.screen = running, size, screen
        self.update, self.versions, self.grind_rc = update, versions, grind_rc
        self.small = None                  # 小視窗目前畫面：tip / download / restart / notice / blank
        self.acts = []
        self.relogins = 0
        self.dl_left = 0

    # 程序
    def proc_count(self):
        return 1 if self.running else 0

    def close_proc(self):
        self.acts.append('close')
        was, self.running = self.running, False
        return 'closed' if was else 'none'

    def start_proc(self):
        self.acts.append('start')
        self.running, self.size = True, '1366x768'
        self.small = 'tip' if self.update else 'notice'
        return True

    def client_size(self):
        return self.size if self.running else None

    def ocr_small(self):
        txt = {'tip': [L('Tip', 180), L('download file:3 size:12M', 220)], 'download': [L('45%', 300)],
               'restart': [L('更新完畢需要重啟用戶端', 220)], 'notice': [L('最新公告', 40)], 'blank': []}
        if self.small == 'download':
            self.dl_left -= 1
            if self.dl_left <= 0:
                self.small = 'restart'
                return txt['restart']
        return txt[self.small]

    def gui(self, *a, note=''):
        self.acts.append(a if a[0] != 'click' else ('click', int(a[1]), int(a[2])))
        if a[0] == 'click' and self.size != '2880x1659':
            xy = (int(a[1]), int(a[2]))
            if xy == cu.TIP_OK and self.small == 'tip':
                self.small, self.dl_left = 'download', 2
            elif xy == cu.RESTART_BTN and self.small == 'restart':
                self.running, self.update = False, False          # 程序自己結束，不會自己重開
            elif xy == cu.NOTICE_X and self.small == 'notice':
                self.small = 'blank'
        elif a[0] == 'max':
            self.size, self.screen = '2880x1659', 'login'
        elif a[0] == 'click' and self.screen == 'dialog' and (int(a[1]), int(a[2])) == netwatch.CONFIRM:
            self.screen = 'login'
        elif a[0] == 'click' and self.screen == 'charsel':
            self.screen = 'game'
        return ''

    def full_kind(self):
        return self.screen

    def relogin(self, src, grind_ensure=True, on_version='halt', clear_halt=False):
        self.relogins += 1
        self.acts.append(('relogin', on_version, clear_halt, grind_ensure))
        if self.versions > 0:
            self.versions -= 1
            return {'status': 'version', 'flash': True}
        self.screen = 'game'
        return {'status': 'reconnected', 'recover': {'grind': {'rc': self.grind_rc} if grind_ensure else None}}

    def grind(self):
        self.acts.append('grind')
        return self.grind_rc


def cu_run(w, dialog='server_closed', quiz=False, vh=None, **kw):
    cu.proc_count, cu.close_proc, cu.start_proc = w.proc_count, w.close_proc, w.start_proc
    cu.client_size, cu.ocr_small, cu.gui, cu.full_kind = w.client_size, w.ocr_small, w.gui, w.full_kind
    cu.dialog_kind = lambda: dialog
    cu.netwatch.relogin = w.relogin
    cu.grind_ensure = w.grind
    cu.netwatch.hud_ok = lambda: w.screen == 'game'
    cu.netwatch.recover = lambda src, grind_ensure=True, **k: {'grind': {'rc': w.grind_rc}} if grind_ensure else {}
    cu.netwatch._forget_char = lambda: None
    cu.verifyhalt.active = lambda: vh
    tripped = []
    cu.verifyhalt.trip = lambda why, src: tripped.append(why)
    cu.uikit.screen_annot = lambda: ({}, ['quiz'] if quiz else [])
    cu.winenv.enable_server = lambda: None
    t = [0.0]
    cu.sleep = lambda s: t.__setitem__(0, t[0] + s)
    cu.clock = lambda: t.__setitem__(0, t[0] + 0.01) or t[0]
    with contextlib.redirect_stdout(io.StringIO()) as buf:
        rc = cu.run(**kw)
    w.out, w.tripped = buf.getvalue(), tripped
    return rc


clicks = lambda w: [a[1:] for a in w.acts if isinstance(a, tuple) and a[0] == 'click']   # noqa: E731

# A 完整：登入畫面版本錯誤 → 關 → 開 → 下載 OK → 下載 → 重啟 → 再開 → 公告 X → max → 登入 → grind
w = World(running=True, screen='login', update=True, versions=1)
rc = cu_run(w)
seq = [a if isinstance(a, str) else a[0] for a in w.acts]
check('A 完整更新流程 → 0', rc == 0, f'rc={rc} {w.out}')
check('A  順序：relogin(版本) → close → start → OK → 重啟 → start → 公告 X → max → end → relogin',
      seq == ['relogin', 'close', 'start', 'click', 'click', 'start', 'click', 'max', 'end', 'relogin'], seq)
check('A  點的都是小視窗提示鈕（OK / 重啟 / X），依序', clicks(w) == [cu.TIP_OK, cu.RESTART_BTN, cu.NOTICE_X], clicks(w))
check('A  relogin 用 on_version=return、clear_halt=True、grind_ensure=True', w.acts[0] == ('relogin', 'return', True, True), w.acts[0])
check('A  共用更新鎖用完已放', not cu.UPDATE_LOCK.exists())

# B 已是新版（p2 情況）：程序沒開 → 開 → 公告 → max → 登入
w = World(running=False, update=False, versions=0)
rc = cu_run(w, grind=False)
seq = [a if isinstance(a, str) else a[0] for a in w.acts]
check('B 沒更新：start → 公告 X → max → end → relogin（--no-grind）→ 0', rc == 0 and seq == ['start', 'click', 'max', 'end', 'relogin']
      and w.acts[-1] == ('relogin', 'return', True, False), seq)

# B2 小視窗沒有任何提示 → 等 SMALL_IDLE_S 後直接 max
w = World(running=True, size='1366x768', screen='login', update=False, versions=0)
w.small = 'blank'
rc = cu_run(w)
check('B2 小視窗沒提示 → 直接 max → 登入 → 0（沒點遊戲）', rc == 0 and not clicks(w) and ('max',) in w.acts, w.acts)

# C 一直版本錯誤 → 重開 MAX_RESTARTS 次後 215
w = World(running=True, update=False, versions=99)
rc = cu_run(w)
check(f'C 重開 {cu.MAX_RESTARTS} 次仍版本錯誤 → 215', rc == cu.EXIT_VERSION and w.acts.count('close') == cu.MAX_RESTARTS
      and w.relogins == cu.MAX_RESTARTS + 1, f'rc={rc} close={w.acts.count("close")}')

# D 驗證旗標 → 9、什麼都不做
w = World()
rc = cu_run(w, vh={'reason': 'x'})
check('D verify-halt → 9、沒有任何動作', rc == cu.EXIT_VERIFY and not w.acts, w.acts)

# E 不認得的提示窗 → 214 不點
w = World(screen='dialog')
rc = cu_run(w, dialog='other')
check('E 不認得的提示窗 → 214、沒點', rc == cu.EXIT_DIALOG and not clicks(w), w.acts)
# E2 伺服器已關閉 → 確定 → 登入
w = World(screen='dialog', versions=0)
rc = cu_run(w, dialog='server_closed')
check('E2 伺服器已關閉 → 按確定 715,557 → 登入 → 0', rc == 0 and clicks(w) == [netwatch.CONFIRM], w.acts)

# F dry-run：任何狀態都不動
for name, w in (('程序沒開', World(running=False)), ('小視窗 Tip', World(size='1366x768')), ('登入', World()), ('遊戲', World(screen='game'))):
    if name == '小視窗 Tip':
        w.small = 'tip'
    rc = cu_run(w, dry_run=True)
    check(f'F dry-run（{name}）→ 0、沒動作、印下一步', rc == 0 and not w.acts and '[dry-run]' in w.out, w.acts)
w = World()
rc = cu_run(w, dry_run=True, restart=True)
check('F dry-run --restart → 不關程序', rc == 0 and 'close' not in w.acts and '--restart' in w.out)

# G 答題介面 → 設旗標 9
w = World()
rc = cu_run(w, quiz=True)
check('G 答題介面正面命中 → trip + 9、沒點', rc == cu.EXIT_VERIFY and w.tripped and not w.acts, w.acts)

# H 已在遊戲：grind ensure；--no-grind 不跑；grind 失敗 219
w = World(screen='game')
check('H 已在遊戲 → grind ensure → 0', cu_run(w) == 0 and w.acts == ['grind'], w.acts)
w = World(screen='game')
check('H --no-grind → 0、不跑 grind', cu_run(w, grind=False) == 0 and not w.acts, w.acts)
w = World(screen='game', grind_rc=3)
check('H grind 失敗 → 219', cu_run(w) == cu.EXIT_GRIND)
w = World(versions=0, grind_rc=5)
check('H relogin 後 grind 失敗 → 219', cu_run(w) == cu.EXIT_GRIND)

# I --restart：先關再開
w = World(running=True, update=False, versions=0)
rc = cu_run(w, restart=True)
check('I --restart → close → start → … → 0', rc == 0 and w.acts[:2] == ['close', 'start'], w.acts[:3])

# J 選角面板 → 一鍵全登 → 進遊戲 → recover
w = World(screen='charsel', versions=0)
rc = cu_run(w)
check('J 選角 → 一鍵全登 740,640 → 0', rc == 0 and clicks(w) == [netwatch.ALL_LOGIN_BTN], w.acts)

# K 別的視窗佔著更新鎖 → 217（不點、不開）
cu.UPDATE_LOCK.write_text('999999 0')
import os  # noqa: E402
os.utime(cu.UPDATE_LOCK, None)
_tw = cu.netwatch._take_wait
cu.netwatch._take_wait = lambda lock, stale, wait: False
w = World(running=False)
rc = cu_run(w)
check('K 更新鎖被別的視窗佔 → 217、沒開程序', rc == cu.EXIT_BUSY and 'start' not in w.acts, w.acts)
cu.netwatch._take_wait = _tw
cu.UPDATE_LOCK.unlink(missing_ok=True)

# L 同名多個程序 → 210
w = World()
w.proc_count = lambda: 2
check('L 同名程序 2 個 → 210、不動', cu_run(w) == cu.EXIT_PROC and not w.acts)

# ---------------- netwatch 命令列接 clientupdate ----------------
called = []
netwatch.layout.current = lambda: '2880x1659'
netwatch.check_and_reconnect = lambda **kw: {'status': 'halt', 'reason': 'x', 'version': True}
netwatch.run_clientupdate = lambda grind=True: called.append(grind) or 0
for argv, want in ((['--once'], [True]), (['--once', '--no-grind'], [False]), (['--once', '--no-update'], [])):
    called.clear()
    sys.argv = ['netwatch.py', *argv]
    with contextlib.redirect_stdout(io.StringIO()):
        rc = netwatch.main()
    check(f'netwatch {" ".join(argv)}：版本錯誤 → ' + ('接 clientupdate' if want else '只 halt（10）'),
          called == want and rc == (0 if want else netwatch.EXIT_HALT), f'{called} rc={rc}')

# BOM / 檔頭
src = Path(cu.__file__).read_text(encoding='utf-8')
check('檔頭寫了退出碼 210～219', all(f'{n} ' in src for n in range(210, 220)))
check('clientupdate 不碰密碼欄座標（PWD_BOX / 帳號欄）', 'PWD_BOX' not in src and 'ACCT_FIELD' not in src and 'typeq' not in src)

print('全部通過' if not fails else f'{fails} 項失敗')
sys.exit(1 if fails else 0)
