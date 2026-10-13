#!/usr/bin/env python3
"""relogin.py 離線測試（不碰遊戲）：全部以假函式替換 uikit / netwatch / team / char。
用法：uv run --no-project python tools/gui/test_relogin.py"""
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent))
import testenv  # noqa: E402,F401
import charstate  # noqa: E402
import errlog  # noqa: E402
import netwatch  # noqa: E402
import relogin  # noqa: E402
import team  # noqa: E402
import char  # noqa: E402
import uikit  # noqa: E402

errlog.LOG = Path(tempfile.mkdtemp()) / 'errlog.jsonl'
tmp = Path(tempfile.mkdtemp())
netwatch.ACT_LOCK = tmp / 'act.lock'
relogin.sleep = lambda *_: None
relogin.log = lambda *_: None
uikit.snap = lambda *_: None
uikit.fail = lambda src, rc, msg: rc
charstate.clear = lambda *a, **k: True
relogin.actlog.add = lambda *a, **k: None
fails = 0


def check(name, cond, extra=''):
    global fails
    print(('PASS ' if cond else 'FAIL ') + name + (' ' + str(extra) if not cond else ''))
    if not cond:
        fails += 1


class World:
    """腳本化的假遊戲：clicks 記錄；dialog / login 由設定決定"""
    def __init__(self, **kw):
        self.o = dict(state='idle', panel_ok=True, btn_ok=True, dialog_after_click=True, prompt='是否登出全部角色?',
                      login_after_confirm=True, relogin={'status': 'reconnected'}, check=[0], form=0, ensure=0, preflight=0,
                      dialog_again=False)
        self.o.update(kw)
        self.clicks, self.calls = [], []
        self.logged_out = False
        self.confirmed = False

    def install(self):
        o = self.o
        uikit.preflight = lambda src, fast=True: o['preflight']
        uikit.screen = lambda full=False: {'state': o['state'], 'panel': 'setting' if o['state'] == 'panel' else None, 'full': o.get('full', False)}
        uikit.open_panel = lambda p, timeout=4.0: o['panel_ok']
        uikit.close_panel = lambda p, known_open=False: True
        uikit.px = lambda pts: [(198, 85, 53)] * len(list(pts)) if o['btn_ok'] else [(0, 0, 0)] * len(list(pts))
        uikit.is_open = lambda p: True

        def gui(*a, note=''):
            self.clicks.append((a, note))
            if a[0] == 'click' and (int(a[1]), int(a[2])) == netwatch.CONFIRM:
                self.confirmed = True
            return ''
        uikit.gui = gui
        relogin.uikit.gui = gui

        def match(sig):
            clicked_logout = any(n == '全員登出' for _, n in self.clicks) or any(c[0][0] == 'seq' and '517' in c[0][1] for c in self.clicks)
            if sig == netwatch.SIG_DIALOG:
                if self.confirmed:
                    return o['dialog_again']
                return clicked_logout and o['dialog_after_click']
            if sig == netwatch.SIG_LOGIN:
                return self.confirmed and o['login_after_confirm']
            return False
        relogin._match = match
        relogin._read_prompt = lambda: o['prompt']

        def safe_click(x, y, panel, note='', allow=(), wait_ms=300):
            uikit.check_forbidden(panel, x, y, allow)
            self.clicks.append((('click', x, y), note))
            return True
        uikit.safe_click = safe_click
        netwatch.relogin = lambda src, **kw: (self.calls.append(('relogin', kw)), o['relogin'])[1]
        checks = list(o['check'])
        team.check = lambda size, leader=None, ocr=True: (self.calls.append(('check', size, leader)), checks.pop(0) if len(checks) > 1 else checks[0])[1]
        team.form = lambda leader=None, size=5, **k: (self.calls.append(('form', leader)), o['form'])[1]
        char.ensure = lambda name: (self.calls.append(('ensure', name)), o['ensure'])[1]
        return self


def run(**kw):
    w = World(**{k: v for k, v in kw.items() if k not in ('confirm', 'dry', 'check_team', 'stuck')}).install()
    rc = relogin.run(kw.get('confirm', True), kw.get('dry', False), 'DKBO', 5, kw.get('check_team', True), kw.get('stuck', False))
    return rc, w


def clicked(w, xy):
    return any(c[0][0] == 'click' and (int(c[0][1]), int(c[0][2])) == xy for c in w.clicks)


rc, w = run(confirm=False)
check('沒 --confirm → 1 且不點', rc == 1 and not w.clicks)
rc, w = run(dry=True, confirm=False)
check('--dry-run → 0 且不點', rc == 0 and not w.clicks)
rc, w = run()
check('全流程 → 0', rc == 0, rc)
check('點了登出與確定', clicked(w, relogin.LOGOUT_BTN) and clicked(w, netwatch.CONFIRM))
check('relogin 不跑 grind / encounter / team', ('relogin', {'grind_ensure': False, 'encounter': False, 'team': False}) in w.calls, w.calls)
check('收尾 check→ensure→check', [c[0] for c in w.calls if c[0] != 'relogin'] == ['check', 'ensure', 'check'], w.calls)
rc, w = run(check=[47, 0], form=0)
check('全員單人 → form', rc == 0 and ('form', 'DKBO') in w.calls, (rc, w.calls))
rc, w = run(check=[41], form=41)
check('隊伍不完整 form 失敗 → 105', rc == 105, rc)
rc, w = run(check=[43])
check('check OCR 矛盾 → 105（不 form）', rc == 105 and not any(c[0] == 'form' for c in w.calls), rc)
rc, w = run(ensure=62)
check('切回隊長失敗 → 106', rc == 106, rc)
rc, w = run(check_team=False)
check('--no-team 不檢查', rc == 0 and not any(c[0] in ('check', 'ensure') for c in w.calls))
rc, w = run(state='battle')
check('戰鬥中 → 107 不點', rc == 107 and not w.clicks)
rc, w = run(state='walking')
check('巡路中（沒 --stuck）→ 107 不點', rc == 107 and not w.clicks)
rc, w = run(state='walking', stuck=True)
check('--stuck：巡路卡住 → 照常登出重登 0', rc == 0 and clicked(w, relogin.LOGOUT_BTN), rc)
rc, w = run(state='battle', stuck=True)
check('--stuck：快速戰鬥 VS 牌卡死 → 照常登出重登 0', rc == 0 and clicked(w, relogin.LOGOUT_BTN), rc)
rc, w = run(state='battle', full=True, stuck=True)
check('--stuck：完整戰鬥畫面 → 仍 107 不點', rc == 107 and not w.clicks)
rc, w = run(state='dialog', stuck=True)
check('--stuck：對話框 → 仍 107 不點', rc == 107 and not w.clicks)
rc, w = run(preflight=8)
check('preflight 8 直接回傳', rc == 8 and not w.clicks)
rc, w = run(panel_ok=False)
check('設置打不開 → 100 不點', rc == 100 and not w.clicks)
rc, w = run(btn_ok=False)
check('登出鈕特徵不符 → 100 不點登出', rc == 100 and not clicked(w, relogin.LOGOUT_BTN))
rc, w = run(dialog_after_click=False)
check('沒出現提示窗 → 101 不點確定', rc == 101 and not clicked(w, netwatch.CONFIRM), rc)
rc, w = run(prompt='網路異常，是否重連')
check('別種訊息 → 102 不點確定', rc == 102 and not clicked(w, netwatch.CONFIRM), rc)
rc, w = run(prompt='')
check('OCR 讀不出信任像素 → 0', rc == 0, rc)
rc, w = run(login_after_confirm=False)
check('沒回登入畫面 → 103', rc == 103, rc)
rc, w = run(login_after_confirm=False, dialog_again=True)
check('確定後又冒提示窗 → 103 且不再點確定', rc == 103 and sum(1 for c in w.clicks if c[0][0] == 'click' and (int(c[0][1]), int(c[0][2])) == netwatch.CONFIRM) == 1, rc)
rc, w = run(relogin={'status': 'halt'})
check('帳密空 / 提示 halt → 10', rc == 10, rc)
rc, w = run(relogin={'status': 'fatal'})
check('連續失敗 → 11', rc == 11, rc)
rc, w = run(relogin={'status': 'ok', 'busy': True})
check('relogin 忙碌 → 104', rc == 104, rc)
check('登出後沒有 netwatch 動作鎖殘留', not netwatch.ACT_LOCK.exists())
netwatch._take(netwatch.ACT_LOCK, 300)
rc, w = run()
check('動作鎖被佔 → 108 不點', rc == 108 and not w.clicks, rc)
netwatch._release(netwatch.ACT_LOCK)
# 禁區：其他三顆底部鈕不准被 safe_click
for nm, xy in (('回記錄點', (921, 731)), ('離線掛機', (1145, 731)), ('解決異常', (290, 731))):
    try:
        uikit.check_forbidden(relogin.SETTING, xy[0], xy[1])
        check(f'{nm} 在禁區', False)
    except uikit.ForbiddenClick:
        check(f'{nm} 在禁區', True)
try:
    uikit.check_forbidden(relogin.SETTING, *relogin.LOGOUT_BTN)
    check('全員登出未 allow 時在禁區', False)
except uikit.ForbiddenClick:
    check('全員登出未 allow 時在禁區', True)
print('失敗', fails)
sys.exit(1 if fails else 0)
