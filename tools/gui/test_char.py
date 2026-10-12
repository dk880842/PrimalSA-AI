#!/usr/bin/env python3
"""char.py（current / switch / ensure）離線測試：不碰遊戲，假 gui 依設定畫切換面板 + 加載畫面（fake_switch.Game）。
用法：uv run --no-project python tools/gui/test_char.py"""
import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import testenv  # noqa: E402,F401  紀錄檔轉向暫存（不污染真 actions.log / quest-events.log / errlog）
import charstate  # noqa: E402
import errlog  # noqa: E402
import namematch  # noqa: E402
import uikit  # noqa: E402
import watchstate  # noqa: E402
from fake_switch import NAMES, OCR_REAL, Game, install, mk, run  # noqa: E402
import char  # noqa: E402

errlog.LOG = Path(tempfile.mkdtemp()) / 'errlog.jsonl'
namematch.TPL_DIR = Path(tempfile.mkdtemp())          # 不讀真實樣板（走順序 + OCR 交叉確認）
watchstate.CURCHAR_FILE = Path(tempfile.mkdtemp()) / 'current-char.json'     # 不動真實旁路檔
uikit.watch_state = lambda max_age=1.0: None          # 預設不讀真實 watch（快路徑測試自己給）
uikit.watch_screen = lambda max_age=1.0: None
fails = 0


def check(name, cond, extra=''):
    global fails
    print(('PASS' if cond else 'FAIL'), name, extra)
    if not cond:
        fails += 1


def last_json(out):
    return json.loads(out.strip().splitlines()[-1])


def fake_time(g):
    """假時鐘：每次讀 +0.05 s（sleep 不真睡，逾時邏輯照跑）"""
    t = [0.0]

    def clk():
        t[0] += 0.05
        return t[0]
    uikit.clock = clk


def cur_of(g):
    return next(c['name'] for c in g.cards if c['status'] == 'current')


def click_pos(i):
    x0, y = char.team.SLOTS[i]
    return (x0 + char.CLICK_DX, y)


# ---- 純函式 ----
check('exit code 常數 60～65', (char.EXIT_PANEL, char.EXIT_NO_CARD, char.EXIT_NOT_SWITCHED, char.EXIT_CUR_COUNT, char.EXIT_CONFLICT, char.EXIT_NO_HUD) == (60, 61, 62, 63, 64, 65))

# ---- current ----
g = install(Game(mk()))
fake_time(g)
rc, out = run(char.current)
j = last_json(out)
check('current：DKBO 當前 rc 0、JSON current=DKBO、0 次面板內點擊、面板已關', rc == 0 and j['current'] == 'DKBO' and j['ok'] and g.inner_clicks() == [] and not g.panel, out.strip())
check('current 寫 charstate', (charstate.read() or {}).get('name') == 'DKBO' and charstate.read()['src'] == 'char.py')
g = install(Game(mk(current=2)))
rc, out = run(char.current, True)
check('current：當前 DKBO3', rc == 0 and last_json(out)['current'] == 'DKBO3' and out.strip().count('\n') == 0)
g = install(Game(mk(current=0)))
for c in g.cards:
    c['status'] = 'online'
rc, out = run(char.current)
check('current：沒有當前框 → 63', rc == 63 and last_json(out)['current'] is None, out.strip())
g = install(Game(mk()))
g.cards[3]['status'] = 'current'
rc, out = run(char.current)
check('current：兩個當前框 → 63', rc == 63)
g = install(Game(mk(), ocr={**OCR_REAL, 'DKBO3': ['D02']}))
rc, out = run(char.current)
check('current：OCR 與順序矛盾 → 64', rc == 64)
g = install(Game(mk(), ocr={}))
rc, out = run(char.current)
check('current：名字完全沒證據（OCR 空）→ 61，不寫 charstate', rc == 61 and last_json(out)['current'] is None, out.strip())
g = install(Game(mk(), hud=False))
rc, out = run(char.current)
check('current：HUD 不在 → 60、0 次點擊', rc == 60 and g.clicks == [], str(g.clicks))

# ---- ensure / switch：已是目標 → 不點 ----
g = install(Game(mk()))
fake_time(g)
rc, out = run(char.switch, 'DKBO')
j = last_json(out)
check('ensure DKBO 已是 → 0、changed false、面板內 0 次點擊', rc == 0 and not j['changed'] and g.inner_clicks() == [], out.strip())
rc, out = run(char.switch, 'DKB0')
check('輸入 DKB0（數字 0）正規化成 DKBO，不點', rc == 0 and last_json(out)['target'] == 'DKBO' and g.inner_clicks() == [])
rc, out = run(char.switch, 'dkb02')
check('輸入 dkb02 = DKBO2（目標存在）→ 切', rc == 0 and last_json(out)['target'] == 'DKBO2')

# ---- switch 成功 ----
g = install(Game(mk()))
fake_time(g)
rc, out = run(char.switch, 'DKBO3')
j = last_json(out)
check('switch DKBO3：rc 0、changed、current DKBO3、只點一次卡片', rc == 0 and j['changed'] and j['current'] == 'DKBO3' and g.inner_clicks() == [click_pos(2)], f'{out.strip()} {g.clicks}')
check('switch 看到加載畫面、charstate = DKBO3、面板已關', j['loading_seen'] and (charstate.read() or {}).get('name') == 'DKBO3' and not g.panel)
g = install(Game(mk(current=2)))
fake_time(g)
rc, out = run(char.ensure, 'DKB0')
check('ensure DKB0（從 DKBO3 切回）→ 0、點 slot0', rc == 0 and last_json(out)['current'] == 'DKBO' and g.inner_clicks() == [click_pos(0)], str(g.clicks))
g = install(Game(mk()))
g.after_load = 0
rc, out = run(char.switch, 'DKBO2')
check('加載太快沒看到 → 仍 0（驗證以面板為準）', rc == 0 and last_json(out)['current'] == 'DKBO2')

# ---- 失敗路徑 ----
g = install(Game(mk()))
fake_time(g)
g.card_moves = False
rc, out = run(char.switch, 'DKBO4')
check('點了當前框沒動 → 62、只點一次、changed true', rc == 62 and len(g.inner_clicks()) == 1 and last_json(out)['changed'], f'{out.strip()} {g.clicks}')
g = install(Game(mk()))
fake_time(g)
g.stuck = True
rc, out = run(char.switch, 'DKBO4')
check('點了 HUD 不回來 → 65、只點一次', rc == 65 and len(g.inner_clicks()) == 1, out.strip())
n = len(g.clicks)
rc, out = run(char.switch, 'XYZ')
check('名字不在白名單 → 1、不碰面板', rc == 1 and len(g.clicks) == n)
g = install(Game(mk(('leader', 'member', 'member', 'member'), names=['DKBO', 'DKBO2', 'DKBO4', 'DKBO5'])))
fake_time(g)
rc, out = run(char.switch, 'DKBO3')
check('目標離線（卡片 4 張沒有 DKBO3）→ 61、0 次點擊、面板已關', rc == 61 and g.inner_clicks() == [] and not g.panel, out.strip())
g = install(Game(mk(('leader', 'member', 'member', 'member'), names=['DKBO', 'DKBO2', 'DKBO4', 'DKBO5'])))
fake_time(g)
rc, out = run(char.switch, 'DKBO4')
check('有人離線卡片位移：依名字 OCR 點 DKBO4 在 slot2', rc == 0 and last_json(out)['current'] == 'DKBO4' and g.inner_clicks() == [click_pos(2)], str(g.clicks))
g = install(Game(mk(), ocr={**OCR_REAL, 'DKBO5': ['0KB05']}))
fake_time(g)
rc, out = run(char.switch, 'DKBO5')
check('OCR 讀成 0KB05 → 正規化 DKBO5，點 slot4', rc == 0 and g.inner_clicks() == [click_pos(4)], out.strip())
g = install(Game(mk(), ocr={}))
fake_time(g)
rc, out = run(char.switch, 'DKBO3')
check('名字沒證據（順序單獨推得）→ 61、不點', rc == 61 and g.inner_clicks() == [])
g = install(Game(mk(), ocr={**OCR_REAL, 'DKBO3': ['D02']}))
rc, out = run(char.switch, 'DKBO3')
check('OCR 與順序矛盾 → 64、不點', rc == 64 and g.inner_clicks() == [])
g = install(Game(mk()))
g.cards[2]['status'] = 'unknown'
fake_time(g)
rc, out = run(char.switch, 'DKBO3')
check('目標卡狀態不是線上（離線）→ 61、不點', rc == 61 and g.inner_clicks() == [], out.strip())
g = install(Game(mk()))
g.vanish_after_label = True
rc, out = run(char.switch, 'DKBO2')
check('讀圖後面板消失 → 60、不點', rc == 60 and g.inner_clicks() == [])
# 失敗有寫 errlog
check('失敗有寫 errlog', errlog.LOG.exists() and errlog.LOG.read_text(encoding='utf-8').count('"source"') >= 5)

# ---- ensure 快路徑（watch 名牌 + current-char.json）----
import time as _time  # noqa: E402


def wstate(name='DKBO', src='both', age=0.5, stale=False):
    return {'hud': {'name': {'v': name, 'ts': _time.time() - age, 'src': src, 'stale': stale}}}


def fast_case(label, st, cur_name='DKBO', cur_age=0.0, want_fast=True, target='DKBO', fn=None, since_ago=100.0):
    g = install(Game(mk()))
    uikit.watch_state = lambda max_age=1.0: st
    uikit.watch_screen = lambda max_age=1.0: {'state': 'idle', 'since': _time.time() - since_ago}
    charstate.clear()
    if cur_name:
        watchstate.write_current_char(cur_name, src='char.py', now=lambda: _time.time() - cur_age)
    rc, out = run(fn or char.ensure, target)
    j = last_json(out)
    fast = j.get('via') == 'watch'
    check(f'快路徑 {label}：{"走" if want_fast else "不走"}', rc == 0 and fast == want_fast and (g.clicks == [] if want_fast else True) and g.inner_clicks() == [], out.strip()[-120:])
    uikit.watch_state = lambda max_age=1.0: None
    uikit.watch_screen = lambda max_age=1.0: None


fast_case('名牌 both + 旁路檔一致', wstate())
fast_case('名牌 ocr 也可', wstate(src='ocr'))
fast_case('名牌 6 s 前核對仍可', wstate(age=6))
fast_case('名牌過舊 > 8 s', wstate(age=12), want_fast=False)
fast_case('名牌核對早於畫面狀態開始（切換 / 轉場後的舊名牌）', wstate(age=5), want_fast=False, since_ago=2.0)
fast_case('名牌 stale', wstate(stale=True), want_fast=False)
fast_case('名牌 src=None', wstate(src=None), want_fast=False)
fast_case('名牌是別人（與旁路檔不一致）', wstate(name='DKBO2'), want_fast=False)
fast_case('旁路檔是別人', wstate(), cur_name='DKBO2', want_fast=False)
fast_case('旁路檔過舊', wstate(), cur_age=4000, want_fast=False)
fast_case('沒有旁路檔', wstate(), cur_name=None, want_fast=False)
fast_case('watch 不在（None）', None, want_fast=False)
fast_case('目標是別人（名牌 DKBO、要 DKBO2）→ 不走快路徑、要點', wstate(), target='DKBO2', want_fast=False) if False else None
g = install(Game(mk()))
uikit.watch_state = lambda max_age=1.0: wstate()
uikit.watch_screen = lambda max_age=1.0: {'state': 'idle', 'since': _time.time() - 100}
charstate.write('DKBO', src='char.py')
fake_time(g)
rc, out = run(char.ensure, 'DKBO2')
check('快路徑：目標不是當前 → 照舊開面板點卡片', rc == 0 and last_json(out).get('via') is None and g.inner_clicks() != [], str(g.clicks))
uikit.watch_state = lambda max_age=1.0: wstate()
uikit.watch_screen = lambda max_age=1.0: {'state': 'idle', 'since': _time.time() - 100}
charstate.write('DKBO', src='char.py')
g = install(Game(mk()))
rc, out = run(char.switch, 'DKBO')
check('switch（非 ensure）已是 DKBO 仍開面板確認、不走 watch', rc == 0 and last_json(out).get('via') is None and g.clicks != [])
uikit.watch_state = lambda max_age=1.0: None
uikit.watch_screen = lambda max_age=1.0: None
g = install(Game(mk()))
fake_time(g)
uikit.timing_start()
rc, out = run(char.switch, 'DKBO')
check('timing：_out 帶 t 分段', 't' in last_json(out) and any(k == 'open' for k, _ in last_json(out)['t']), str(last_json(out).get('t')))
uikit._stages = None
check('LAST 帶最後一次結果', char.LAST.get('ok') is True and char.LAST.get('target') == 'DKBO')

# ---- errlog #383～#396「讀不到面板像素」：沒開常駐 server 時 pixel 參數超過 Windows 命令列上限 ----
import winenv  # noqa: E402
CMDLINE_MAX = 32767
g = install(Game(mk()))
_real_gui = g.gui
_px_calls = []


def limited_gui(*args, note=''):
    """模擬一次性 powershell.exe：參數總長超過 32767 字元就啟動失敗（輸出錯誤訊息、沒有像素）"""
    if args and args[0] == 'pixel':
        _px_calls.append(len(args[1]))
        if len(args[1]) > CMDLINE_MAX:
            return 'Program \'powershell.exe\' failed to run: The filename or extension is too long'
    return _real_gui(*args, note=note)


uikit.gui = limited_gui
_orig_long = winenv.long_args_ok
winenv.long_args_ok = lambda script='gui.ps1': False
rc, out = run(char.current)
check('沒開 server：team 5784 點分批讀 → current 成功（不再「讀不到面板像素」）', rc == 0 and max(_px_calls) <= uikit.PX_ARG_MAX, f'rc={rc} 各批字元 {_px_calls[:6]}')
_px_calls.clear()
winenv.long_args_ok = lambda script='gui.ps1': True
g = install(Game(mk()))
_real_gui = g.gui
uikit.gui = lambda *a, note='': (_px_calls.append(len(a[1])) if a and a[0] == 'pixel' else None) or _real_gui(*a, note=note)
rc, out = run(char.current)
check('走 server：大點陣一次送完（同一張截圖）', rc == 0 and max(_px_calls) > CMDLINE_MAX, f'rc={rc} 最大 {max(_px_calls)}')
winenv.long_args_ok = _orig_long
ch = uikit.px_chunks([(1000 + i % 400, 100 + i % 700) for i in range(6000)], 20000)
check('px_chunks：每批 <= 上限、合起來順序不變', all(len(' '.join(f'{x},{y}' for x, y in c)) <= 20000 for c in ch) and sum(ch, []) == [(1000 + i % 400, 100 + i % 700) for i in range(6000)] and len(ch) > 1, str([len(c) for c in ch]))
check('px_chunks：空清單 / 不切', uikit.px_chunks([], 100) == [[]] and len(uikit.px_chunks([(1, 1)] * 50, 0)) == 1)

print('失敗', fails)
sys.exit(1 if fails else 0)
