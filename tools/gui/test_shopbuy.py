#!/usr/bin/env python3
"""shopbuy.py 離線測試：完全不碰遊戲（bag / heal / team / char / buy_one 全換假的）。
用法：uv run --no-project python tools/gui/test_shopbuy.py"""
import os
import sys
from pathlib import Path

os.environ.setdefault('PSA_LAYOUT', '2880x1659')
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import testenv  # noqa: E402,F401  紀錄檔轉向暫存
import bag  # noqa: E402
import char  # noqa: E402
import heal  # noqa: E402
import shopbuy  # noqa: E402
import team  # noqa: E402

fails = 0
calls = []
have = {}


def check(name, cond, extra=''):
    global fails
    print(('PASS' if cond else 'FAIL'), name, extra)
    if not cond:
        fails += 1


def team_read(roles, names=(), level=False):
    calls.append(('team_read',))
    return 0, {r: {'have': {n: have.get(r, True) for n in names}} for r in roles}


def buy(role, log):
    calls.append(('buy', role))
    have[role] = True
    return 0


bag.team_read = team_read
heal.heal_trip = lambda spot, no_return=False, reopen=True: calls.append(('heal', no_return, reopen))
team.disband = lambda: (calls.append(('disband',)), 0)[1]
team.form = lambda *a, **k: (calls.append(('form',)), 0)[1]
char.ensure = lambda r: (calls.append(('ensure', r)), 0)[1]
shopbuy.buy_one = buy
R = ['DKBO', 'DKBO2', 'DKBO3', 'DKBO4', 'DKBO5']

have = {'DKBO2': False, 'DKBO4': False}
rc, info = shopbuy.run(R, confirm_spend=False)
check('沒 confirm_spend → 只列誰缺、不動', rc == 0 and info['missing'] == ['DKBO2', 'DKBO4'] and calls == [('team_read',)], str(calls))
calls.clear()
rc, info = shopbuy.run(R, confirm_spend=True)
names = [c[0] for c in calls]
check('confirm_spend：回村進醫院（no_return、不開遇敵）→ 解散 → 逐人買 → 切回 DKBO → 組隊 → 重讀 → 0', rc == 0 and info['bought'] == ['DKBO2', 'DKBO4']
      and names == ['team_read', 'heal', 'disband', 'buy', 'buy', 'ensure', 'form', 'team_read'] and ('heal', True, False) in calls and not info['still_missing'], str(calls))
calls.clear()
have = {'DKBO3': False}
shopbuy.buy_one = lambda role, log: (calls.append(('buy', role)), shopbuy.EXIT_BUY)[1]
rc, info = shopbuy.run(R, confirm_spend=True)
check('某人買不到 → 182、仍切回 DKBO、不組隊', rc == shopbuy.EXIT_BUY and ('ensure', 'DKBO') in calls and ('form',) not in calls, str(calls))
calls.clear()
shopbuy.buy_one = lambda role, log: (calls.append(('buy', role)), 0)[1]     # 按了但沒買到
rc, info = shopbuy.run(R, confirm_spend=True)
check('買完重讀仍缺 → 183', rc == shopbuy.EXIT_STILL and info['still_missing'] == ['DKBO3'])
calls.clear()
heal.heal_trip = lambda *a, **k: (_ for _ in ()).throw(RuntimeError('傳送失敗'))
rc, info = shopbuy.run(R, confirm_spend=True)
check('回村失敗 → 181、不解散', rc == shopbuy.EXIT_PRE and ('disband',) not in calls)
heal.heal_trip = lambda spot, no_return=False, reopen=True: None
team.disband = lambda: 9
rc, info = shopbuy.run(R, confirm_spend=True)
check('解散時遇到驗證視窗（9）→ 透傳 9', rc == 9)

print(f'\n{"全部通過" if not fails else f"失敗 {fails} 項"}')
sys.exit(1 if fails else 0)
