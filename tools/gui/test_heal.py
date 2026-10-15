#!/usr/bin/env python3
"""heal.py 離線測試：補完回哪個練功點的決策（resolve_return_spot）與 CLI 分派。不碰遊戲：
here / auto / heal_trip / layout / winenv 全換成替身，不會呼叫 powershell / gui.ps1。
用法：uv run --no-project python tools/gui/test_heal.py"""
import os
import sys
from pathlib import Path

os.environ.setdefault("PSA_LAYOUT", "2880x1659")
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import testenv  # noqa: E402,F401
import heal  # noqa: E402

fails = 0


def check(name, cond, extra=''):
    global fails
    print(('PASS' if cond else 'FAIL'), name, extra)
    if not cond:
        fails += 1


# 全部換替身：不可真的送出任何動作
def _boom(*a, **k):
    raise AssertionError('測試不該呼叫真的 gui / stat')


heal.gui = _boom
heal.stat = _boom
heal.log = lambda *a, **k: None
heal.layout.current = lambda: heal.layout.SUPPORTED[0]
heal.winenv.enable_server = lambda: None

# ---- resolve_return_spot ----
R = heal.resolve_return_spot
check('--spot 指定照舊（不呼叫 here / auto）', R('波拉島2', here=_boom, auto=_boom) == '波拉島2')
check('所在練功點優先', R(None, here=lambda: '地雷區', auto=lambda: '波拉島') == '地雷區')
check('不在練功點 → 依等級', R(None, here=lambda: None, auto=lambda: '波拉島') == '波拉島')
check('here 丟例外 → 依等級', R(None, here=lambda: 1 / 0, auto=lambda: '波拉島') == '波拉島')
check('表外名稱不採用', R(None, here=lambda: '亂寫', auto=lambda: None) is None)
check('都判斷不了 → None', R(None, here=lambda: None, auto=lambda: None) is None)
check('auto 丟例外 → None', R(None, here=lambda: None, auto=lambda: 1 / 0) is None)

# ---- CLI 分派 ----
calls = []
heal.heal_trip = lambda spot, no_return=False, reopen=True: calls.append((spot, no_return))
orig = heal.resolve_return_spot


def run(argv, spot):
    calls.clear()
    heal.resolve_return_spot = lambda s=None, here=None, auto=None: orig(s, here=lambda: spot, auto=lambda: None)
    sys.argv = ['heal.py'] + argv
    return heal.main()


check('CLI 無 --spot：回所在點', run([], '地雷區') == 0 and calls == [('地雷區', False)], str(calls))
check('CLI --spot 照舊', run(['--spot', '波拉島2'], '地雷區') == 0 and calls == [('波拉島2', False)], str(calls))
rc = run([], None)
check('CLI 判斷不了：不補血、退出 3', rc == heal.EXIT_NO_SPOT == 3 and calls == [], f'{rc} {calls}')
check('CLI --no-return 不判斷點', run(['--no-return'], None) == 0 and len(calls) == 1 and calls[0][1] is True, str(calls))
check('CLI --no-return + --watch 仍拒絕', run(['--no-return', '--watch'], '地雷區') == 2 and calls == [])

print('FAIL 數:', fails)
sys.exit(1 if fails else 0)
