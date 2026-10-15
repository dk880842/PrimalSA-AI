#!/usr/bin/env python3
"""多視窗第 3a 步離線測試（不碰遊戲、不呼叫真的 powershell.exe）：
  clients 狀態資料夾（cache_dir / notes_dir / dir_name）；沒設 PSA_CLIENT 時各模組路徑常數與改版前逐字相同、PrimalSA2 全部落在 clients/PrimalSA2；
  verifyhalt（多視窗才寫、preflight / netwatch.guard / VerifyGuard / uikit.fail）；netwatch 多視窗不按登錄、relogin.py 109；
  spawn_detached 把 PSA_CLIENT 傳給子程序；errlog client 欄；gui.sh 退出碼（pipefail）與相對截圖路徑；gui.ps1 / psawin.ps1 靜態檢查。
整支測試期間 PATH 最前面放假的 powershell.exe（記錄每次呼叫）：預期會呼叫的測試讀完就清空，最後確認沒有任何意外的呼叫。
  uv run --no-project python tools/gui/test_clientctx.py
"""
import json
import os
import stat
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import testenv  # noqa: E402,F401  紀錄檔 / verify-halt.json 轉向暫存；PSA_TEST_PROCS=PrimalSA（單視窗）
import clients  # noqa: E402

GUI = Path(__file__).resolve().parent
ROOT = GUI.parents[1]
failed = 0


def check(name, ok, detail=''):
    global failed
    print(('PASS ' if ok else 'FAIL ') + name + (f'  {detail}' if detail and not ok else ''))
    if not ok:
        failed += 1


# ---- 假 powershell.exe（PATH 最前面；FAKE_PS_RC 決定退出碼）----
tmp = Path(tempfile.mkdtemp(prefix='psa-cc-'))
bindir = tmp / 'bin'
bindir.mkdir()
calls = tmp / 'ps-calls.jsonl'
fake = bindir / 'powershell.exe'
fake.write_text('#!' + sys.executable + '\n'
                'import json, os, sys\n'
                f'open({str(calls)!r}, "a", encoding="utf-8").write(json.dumps({{"argv": sys.argv[1:], '
                '"PSA_CLIENT": os.environ.get("PSA_CLIENT")}) + "\\n")\n'
                'print("fake ok")\n'
                'sys.exit(int(os.environ.get("FAKE_PS_RC", "0")))\n', encoding='utf-8')
fake.chmod(fake.stat().st_mode | stat.S_IXUSR)
os.environ['PATH'] = str(bindir) + os.pathsep + os.environ.get('PATH', '')
os.environ.pop('PSA_CLIENT', None)
os.environ['PSA_GUI_SERVER'] = '0'


def take_calls():
    if not calls.exists():
        return []
    out = [json.loads(x) for x in calls.read_text(encoding='utf-8').splitlines() if x.strip()]
    calls.unlink()
    return out


# ================================================================ 1) clients 狀態資料夾
SH = ROOT / 'tools' / '.cache'
# 離線測試（testenv）時每視窗狀態檔一律在暫存資料夾（2026-10-15：主工作樹 test_roster 讀到真的 PrimalSA2 grind.lock → rc 8）
_TS = Path(os.environ['PSA_LOG_DIR']) / 'state'
check('testenv：test_state_dir = <PSA_LOG_DIR>/state', clients.test_state_dir() == _TS)
check('testenv：主視窗 cache_dir → 暫存 state（不讀真的 tools/.cache 鎖檔）', clients.cache_dir('') == _TS and clients.SHARED_CACHE == SH)
check('testenv：PrimalSA2 cache_dir → 暫存 state/clients/PrimalSA2', clients.cache_dir('PrimalSA2') == _TS / 'clients' / 'PrimalSA2'
      and clients.cpath('grind.lock', 'PrimalSA2') == _TS / 'clients' / 'PrimalSA2' / 'grind.lock')
_keep_tsd = clients.test_state_dir
clients.test_state_dir = lambda: None             # 以下檢查真正（非測試）的路徑規則
check('主視窗 cache_dir = tools/.cache（不變）', clients.cache_dir('') == SH == clients.SHARED_CACHE and clients.cache_dir('PrimalSA') == SH)
check('主視窗大小寫 / .exe 不分', clients.cache_dir('primalsa.exe') == SH and clients.notes_dir('PRIMALSA') == ROOT / 'notes')
check('PrimalSA2 → tools/.cache/clients/PrimalSA2', clients.cache_dir('PrimalSA2') == SH / 'clients' / 'PrimalSA2')
check('名單裡的大小寫統一（primalsa2 → PrimalSA2 同一資料夾）', clients.cache_dir('primalsa2') == SH / 'clients' / 'PrimalSA2')
check('notes：PrimalSA2 → notes/clients/PrimalSA2', clients.npath('quest-events.log', 'PrimalSA2') == ROOT / 'notes' / 'clients' / 'PrimalSA2' / 'quest-events.log')
check('不合法名稱不會跳出 clients/', clients.dir_name('../x') == '.._x' and clients.dir_name('..') == '_..' and clients.dir_name('a b') == 'a_b'
      and clients.cache_dir('..').parent == SH / 'clients')
check('cpath = cache_dir / 檔名', clients.cpath('grind.lock', 'PrimalSA3') == SH / 'clients' / 'PrimalSA3' / 'grind.lock')
check('問別的視窗（給 n）不建資料夾', not (SH / 'clients' / 'PrimalSA3').exists())
clients.test_state_dir = _keep_tsd

# running / multi_window（PSA_TEST_PROCS，不呼叫 powershell）
os.environ['PSA_TEST_PROCS'] = 'PrimalSA'
check('單視窗：running = [PrimalSA]、主視窗不是多視窗', clients.running() == ['PrimalSA'] and not clients.multi_window())
os.environ['PSA_TEST_PROCS'] = 'PrimalSA,PrimalSA2,notepad'
check('兩個視窗：others = [PrimalSA2]、主視窗是多視窗', clients.others_running() == ['PrimalSA2'] and clients.multi_window())
check('非主視窗一律是多視窗', clients.multi_window('PrimalSA2', procs=['PrimalSA2']))
_run = clients.running
clients.running = lambda timeout=15.0: None
check('查不到程序清單 → others None、主視窗當作多視窗（保守）', clients.others_running('PrimalSA') is None and clients.multi_window('PrimalSA'))
clients.running = _run
# rostered_running（psa-hud 多視窗偵測，第 3d 步）：只列 ROSTERS 有登錄的、資料夾名寫法、照 ROSTERS 順序
check('rostered_running：PrimalSA3 / notepad 不列、大小寫換成名單寫法', clients.rostered_running(['primalsa2', 'PrimalSA3', 'PrimalSA']) == ['PrimalSA', 'PrimalSA2'])
clients.running = lambda timeout=15.0: None
check('rostered_running：查不到程序清單 → None', clients.rostered_running() is None)
clients.running = _run
import subprocess as _sp  # noqa: E402
_cli = _sp.run([sys.executable, str(GUI / 'clients.py'), 'running', '--rostered'], capture_output=True, text=True, encoding='utf-8',
               env={**os.environ, 'PSA_TEST_PROCS': 'PrimalSA2,PrimalSA3,PrimalSA'})
check('clients.py running --rostered（CLI）：一行一個、退出碼 0', _cli.returncode == 0 and _cli.stdout.split() == ['PrimalSA', 'PrimalSA2'], repr(_cli.stdout))
os.environ['PSA_TEST_PROCS'] = 'PrimalSA'
check('proc_client：自己的程序沒設 PSA_CLIENT = PrimalSA', sys.platform != 'linux' or clients.proc_client(os.getpid()) == 'PrimalSA')
check('proc_client：讀不到 → None', clients.proc_client(99999999) is None)

# running() 真的呼叫 powershell 時（假的回 PrimalSA / PrimalSA2）
saved = os.environ.pop('PSA_TEST_PROCS')
fake2 = bindir / 'powershell.exe'
r = clients.running()
c = take_calls()
check('running() 真呼叫：一次 powershell -Command（假 powershell 輸出「fake ok」→ 沒有遊戲程序）', r == [] and len(c) == 1 and '-Command' in c[0]['argv'], f'{r} {c}')
os.environ['FAKE_PS_RC'] = '1'
check('running() powershell 失敗 → None（呼叫端當不確定）', clients.running() is None)
os.environ.pop('FAKE_PS_RC')
take_calls()
os.environ['PSA_TEST_PROCS'] = saved

# ================================================================ 2) 路徑快照：沒設 PSA_CLIENT 時與改版前逐字相同；PrimalSA2 全在 clients/PrimalSA2
SNAP = r'''
import json, os, sys
from pathlib import Path
gui = Path(sys.argv[1]); root = gui.parents[1]
sys.path.insert(0, str(gui))
import clients
clients._ensure = lambda d, n: d                 # 快照不建資料夾
T = {'uikit': 'CACHE SHOT_DIR TMP_SHOT_DIR NETWATCH_HALT',
     'watchstate': 'CACHE STATE_FILE LOCK_FILE STOP_FILE HUD_CFG BATTLE_LOCK HALT_FILE ACK_FILE CONFIG_FILE CURCHAR_FILE PET_AVATARS_FILE QUEST_LOG',
     'battleguard': 'LOCK_FILE', 'netwatch': 'HALT STATE ACT_LOCK WATCH_LOCK', 'petwatch': 'STATE LOCK',
     'grind': 'LOCK OUT TRANS_FILE', 'follow': 'PID_FILE STOP_FILE STATE_FILE LOG_FILE EVENT_LOG', 'exp': 'HISTORY',
     'petmatch': 'TPL_DIR', 'petglyph': 'CAP_DIR', 'petquest': 'PROGRESS EVENT_LOG', 'postrebirth': 'PROGRESS EVENT_LOG',
     'rebirth': 'PROGRESS EVENT_LOG QUEST_LOG', 'rebirth_pets': 'PROGRESS EVENT_LOG QUEST_LOG', 'questrun': 'PROGRESS',
     'rebirth_steps': 'SNAPSHOT', 'quest': 'LOG_FILE SHOT_DIR TRACK_POS', 'questdetail': 'CACHE', 'walk': 'MAPHIST',
     'actlog': 'LOG', 'errlog': 'LOG', 'spots': 'THRESH_FILE', 'namematch': 'TPL_DIR', 'digitmatch': 'TPL_DIR MISMATCH_DIR',
     'itemname_match': 'TPL_DIR', 'titlematch': 'TPL_DIR', 'winenv': 'PIDS_FILE', 'verifyhalt': 'FILE'}
out = {}
import importlib
for m, attrs in T.items():
    mod = importlib.import_module(m)
    for a in attrs.split():
        out[f'{m}.{a}'] = Path(getattr(mod, a)).resolve().relative_to(root).as_posix()
import pet_catch
out['pet_catch.src_path()'] = pet_catch.src_path().relative_to(root).as_posix()
out['pet_catch.pre_path()'] = pet_catch.pre_path().relative_to(root).as_posix()
print(json.dumps(out))
'''
C = 'tools/.cache'
OLD = {   # 改版前（git 5416595）各常數的值：主視窗必須逐字相同
    'uikit.CACHE': C, 'uikit.SHOT_DIR': f'{C}/ui-log', 'uikit.TMP_SHOT_DIR': f'{C}/tmp', 'uikit.NETWATCH_HALT': f'{C}/netwatch.halt',
    'watchstate.CACHE': C, 'watchstate.STATE_FILE': f'{C}/state.json', 'watchstate.LOCK_FILE': f'{C}/watch.lock', 'watchstate.STOP_FILE': f'{C}/watch.stop',
    'watchstate.HUD_CFG': f'{C}/psa-hud.json', 'watchstate.BATTLE_LOCK': f'{C}/battle.lock', 'watchstate.HALT_FILE': f'{C}/netwatch.halt',
    'watchstate.ACK_FILE': f'{C}/watch.ack', 'watchstate.CONFIG_FILE': f'{C}/watch-config.json', 'watchstate.CURCHAR_FILE': f'{C}/current-char.json',
    'watchstate.PET_AVATARS_FILE': f'{C}/pet-avatars.json', 'watchstate.QUEST_LOG': 'notes/quest-events.log',
    'battleguard.LOCK_FILE': f'{C}/battle.lock', 'netwatch.HALT': f'{C}/netwatch.halt', 'netwatch.STATE': f'{C}/netwatch.json',
    'netwatch.ACT_LOCK': f'{C}/netwatch.act.lock', 'netwatch.WATCH_LOCK': f'{C}/netwatch.lock', 'petwatch.STATE': f'{C}/petwatch.json',
    'petwatch.LOCK': f'{C}/petwatch.lock', 'grind.LOCK': f'{C}/grind.lock', 'grind.OUT': f'{C}/grind.json', 'grind.TRANS_FILE': f'{C}/trans.json',
    'follow.PID_FILE': f'{C}/follow.pid', 'follow.STOP_FILE': f'{C}/follow.stop', 'follow.STATE_FILE': f'{C}/follow.json',
    'follow.LOG_FILE': f'{C}/follow.log', 'follow.EVENT_LOG': 'notes/quest-events.log', 'exp.HISTORY': f'{C}/exp-history.jsonl',
    'petmatch.TPL_DIR': f'{C}/pet-tpl', 'petglyph.CAP_DIR': f'{C}/petident/samples', 'petquest.PROGRESS': f'{C}/petquest.json',
    'petquest.EVENT_LOG': 'notes/quest-events.log', 'postrebirth.PROGRESS': f'{C}/postrebirth.json', 'postrebirth.EVENT_LOG': 'notes/quest-events.log',
    'rebirth.PROGRESS': f'{C}/rebirth.json', 'rebirth.EVENT_LOG': 'notes/quest-events.log', 'rebirth.QUEST_LOG': 'notes/quest-log.md',
    'rebirth_pets.PROGRESS': f'{C}/rebirth_pets.json', 'rebirth_pets.EVENT_LOG': 'notes/quest-events.log', 'rebirth_pets.QUEST_LOG': 'notes/quest-log.md',
    'questrun.PROGRESS': f'{C}/questrun.json', 'rebirth_steps.SNAPSHOT': f'{C}/rebirth_pets_before.json', 'quest.LOG_FILE': 'notes/quest-events.log',
    'quest.SHOT_DIR': f'{C}/quest-log', 'quest.TRACK_POS': f'{C}/track-pos.json', 'questdetail.CACHE': C, 'walk.MAPHIST': f'{C}/maphist.json',
    'actlog.LOG': f'{C}/actions.log', 'errlog.LOG': f'{C}/errlog.jsonl', 'spots.THRESH_FILE': f'{C}/spot-thresholds.json',
    'namematch.TPL_DIR': f'{C}/name-tpl', 'digitmatch.TPL_DIR': f'{C}/digit-tpl', 'digitmatch.MISMATCH_DIR': f'{C}/digit-mismatch',
    'itemname_match.TPL_DIR': f'{C}/item-name-tpl', 'titlematch.TPL_DIR': f'{C}/task-titles', 'winenv.PIDS_FILE': f'{C}/gui-server.pids',
    'verifyhalt.FILE': f'{C}/verify-halt.json',
    'pet_catch.src_path()': f'{C}/pet-tpl/catch-src.json', 'pet_catch.pre_path()': f'{C}/pet-tpl/catch-pre.json',
}
# 全部視窗共用（PSA_CLIENT 設什麼都不變）：樣板 / 圖庫 / 共用 log / 全域旗標
SHARED = {'actlog.LOG', 'errlog.LOG', 'spots.THRESH_FILE', 'namematch.TPL_DIR', 'digitmatch.TPL_DIR', 'digitmatch.MISMATCH_DIR',
          'itemname_match.TPL_DIR', 'titlematch.TPL_DIR', 'winenv.PIDS_FILE', 'verifyhalt.FILE', 'petmatch.TPL_DIR', 'petglyph.CAP_DIR',
          'watchstate.PET_AVATARS_FILE'}


def snap(client):
    env = {k: v for k, v in os.environ.items() if k not in ('PSA_LOG_DIR', 'PSA_CLIENT')}   # 不轉向：看真正的路徑常數
    env['PSA_LAYOUT'] = '2880x1659'           # walk.py import 時讀版面：給定值，不呼叫 gui.ps1 info
    if client:
        env['PSA_CLIENT'] = client
    r = subprocess.run([sys.executable, '-c', SNAP, str(GUI)], capture_output=True, text=True, env=env, timeout=120)
    try:
        return json.loads(r.stdout.strip().splitlines()[-1])
    except (ValueError, IndexError):
        return {'error': r.stderr[-500:]}


s0 = snap('')
diff0 = {k: (s0.get(k), v) for k, v in OLD.items() if s0.get(k) != v}
check(f'沒設 PSA_CLIENT：{len(OLD)} 個路徑常數與改版前逐字相同', not diff0, str(diff0 or s0.get('error')))
s2 = snap('PrimalSA2')
bad = {}
for k, v in OLD.items():
    want = v if k in SHARED else (v.replace(C, f'{C}/clients/PrimalSA2', 1) if v.startswith(C) else v.replace('notes/', 'notes/clients/PrimalSA2/', 1))
    if s2.get(k) != want:
        bad[k] = (s2.get(k), want)
check('PSA_CLIENT=PrimalSA2：每視窗的檔全在 clients/PrimalSA2、共用的不動', not bad, str(bad or s2.get('error')))
c = take_calls()
check('快照沒有呼叫 powershell', not c, str(c)[:400])

# ================================================================ 3) verifyhalt
import verifyhalt  # noqa: E402
VH = verifyhalt.FILE
check('旗標檔轉向暫存（不碰真的 tools/.cache）', 'psatest-' in str(VH))
os.environ['PSA_TEST_PROCS'] = 'PrimalSA'
check('單一視窗 trip → 不寫（行為不變）', verifyhalt.trip('x', 't') is False and not VH.exists() and verifyhalt.active() is None)
os.environ['PSA_TEST_PROCS'] = 'PrimalSA,PrimalSA2'
check('主視窗 + 還有 PrimalSA2 → trip 寫旗標', verifyhalt.trip('畫面不認得', 'test') is True and VH.exists())
d = verifyhalt.active()
check('旗標內容：client / src / reason', d and d['client'] == 'PrimalSA' and d['src'] == 'test' and d['reason'] == '畫面不認得', str(d))
check('已有旗標 → 再 trip 不覆蓋第一筆', verifyhalt.trip('第二次', 'x') and verifyhalt.active()['reason'] == '畫面不認得')
check('status 退出碼 9', verifyhalt.main(['status']) == 9)

# 有旗標時各消費端都停
import uikit  # noqa: E402
import netwatch  # noqa: E402
import watchstate  # noqa: E402
screen_reads = []
uikit.screen = lambda *a, **k: screen_reads.append(1) or {'state': 'idle'}
check('uikit.preflight → 9（不讀畫面）', uikit.preflight('t') == uikit.EXIT_UNKNOWN_SCREEN and not screen_reads)
check('uikit.watch_preflight_ok → False', uikit.watch_preflight_ok() is False)
r = netwatch.check_and_reconnect(src='t')
check('netwatch.check_and_reconnect → status verify（不點）', r['status'] == 'verify')
try:
    netwatch.guard('t')
    code = None
except SystemExit as e:
    code = e.code
check('netwatch.guard → sys.exit(9)', code == 9)
vg = watchstate.VerifyGuard('t', log=lambda *_: None, reader=lambda: False)
check('VerifyGuard.check → timeout（呼叫端停止）', vg.check() == 'timeout')
check('clear → 消失', verifyhalt.clear() and verifyhalt.active() is None and verifyhalt.main(['status']) == 0)
check('clear 沒有旗標 → False', verifyhalt.clear() is False)

# 設旗標的入口：uikit.fail(…, 9) / preflight 連 3 次不認得（多視窗才寫）
import errlog  # noqa: E402
uikit.fail('t', uikit.EXIT_UNKNOWN_SCREEN, '畫面連 3 次不認得')
check('多視窗：uikit.fail(9) → 設旗標', verifyhalt.active() is not None and verifyhalt.active()['src'] == 't')
verifyhalt.clear()
uikit.fail('t', 50, '別的錯')
check('uikit.fail 其他退出碼 → 不設', verifyhalt.active() is None)
os.environ['PSA_TEST_PROCS'] = 'PrimalSA'
uikit.fail('t', uikit.EXIT_UNKNOWN_SCREEN, '單視窗')
check('單一視窗：uikit.fail(9) → 不設（行為不變）', verifyhalt.active() is None)
os.environ['PSA_TEST_PROCS'] = 'PrimalSA,PrimalSA2'
uikit.watch_preflight_ok = lambda: False
uikit.layout_ok = None
import layout  # noqa: E402
_lc = layout.current
layout.current = lambda *a, **k: uikit.LAYOUT
_ng = netwatch.guard
netwatch.guard = lambda src, **k: {'status': 'ok'}
uikit.screen = lambda *a, **k: {'state': 'unknown'}
uikit.transition_now = lambda: False
uikit.sleep = lambda *_: None
check('多視窗：preflight 連 3 次不認得 → 9 且設旗標', uikit.preflight('pf') == 9 and (verifyhalt.active() or {}).get('src') == 'pf')
verifyhalt.clear()
layout.current, netwatch.guard = _lc, _ng

# watch.py：unknown_long / quest 警報兩處都 trip，state.flags 帶 verify_halt（靜態）
ws = (GUI / 'watch.py').read_text(encoding='utf-8')
check('watch.py：unknown_long 與 quest 轉述警報都呼叫 trip_verify、flags 有 verify_halt',
      ws.count('trip_verify(') == 3 and "'verify_halt': verifyhalt.active() is not None" in ws)
qs = (GUI / 'quest.py').read_text(encoding='utf-8')
check('quest.py：連續 3 次不認得 → verifyhalt.trip', "verifyhalt.trip('quest.py 連續 3 次遇到不認得的畫面" in qs)

# ================================================================ 4) netwatch 多視窗不按登錄 / relogin.py 109
os.environ['PSA_TEST_PROCS'] = 'PrimalSA'
check('auto_login_check：單一視窗 → ok', netwatch.auto_login_check() == ('ok', ''))
os.environ['PSA_TEST_PROCS'] = 'PrimalSA,PrimalSA2'
how, why = netwatch.auto_login_check()
check('auto_login_check：主視窗 + PrimalSA2 在跑 → block', how == 'block' and 'PrimalSA2' in why and why.startswith(netwatch.MULTI_HALT), why)
os.environ['PSA_CLIENT'] = 'PrimalSA2'
how, why = netwatch.auto_login_check()
check('auto_login_check：非主視窗 → block（不看程序清單）', how == 'block' and '非主視窗 PrimalSA2' in why, why)
os.environ.pop('PSA_CLIENT')
_orig_others = clients.others_running
clients.others_running = lambda n=None, procs=None: None
check('auto_login_check：others_running None → unknown', netwatch.auto_login_check()[0] == 'unknown')

# relogin()：block → halt、不點登錄；unknown → 本輪不點、read_fails +1
nt = Path(tempfile.mkdtemp())
netwatch.CACHE, netwatch.HALT, netwatch.STATE, netwatch.ACT_LOCK = nt, nt / 'netwatch.halt', nt / 'netwatch.json', nt / 'act.lock'
netwatch.log = lambda *a, **k: None
netwatch.actlog.add = lambda *a, **k: None
ERR = []
_eadd, _efix = errlog.add, errlog.fix
netwatch.errlog.add = lambda text, **k: (ERR.append(text), len(ERR))[1]
netwatch.errlog.fix = lambda *a, **k: None
clicks, reads = [], []
netwatch.gui = lambda *a, **k: clicks.append(a)
netwatch.login_fields_filled = lambda: reads.append(1) or True
r = netwatch.relogin('t')
check('unknown：本輪不點登錄、不讀帳密欄、read_fails=1', r == {'status': 'ok', 'failed': True} and not clicks and not reads
      and json.loads(netwatch.STATE.read_text())['read_fails'] == 1, str(r))
clients.others_running = _orig_others
os.environ['PSA_TEST_PROCS'] = 'PrimalSA,PrimalSA2'
netwatch.STATE.unlink()
r = netwatch.relogin('t')
check('多視窗：relogin → halt、不點登錄、不讀帳密欄、寫 halt 檔', r['status'] == 'halt' and netwatch.MULTI_HALT in r['reason']
      and not clicks and not reads and netwatch.HALT.exists(), str(r))
check('  errlog 記停手理由', any(netwatch.MULTI_HALT in e for e in ERR))
netwatch.HALT.unlink()
# 斷線提示 → 點確定 → 回登入畫面 → 多視窗 halt（確定照點）
seq = iter([True, False, True])      # detect：dialog 符合；點確定後 _match(SIG_LOGIN) → True
_m = netwatch._match
netwatch._match = lambda sig: (sig == netwatch.SIG_DIALOG and not clicks) or (sig == netwatch.SIG_LOGIN and bool(clicks))
netwatch._ocr = lambda *a, **k: ['網路異常，是否重連?']
netwatch.time.sleep = lambda *_: None
r = netwatch.check_and_reconnect(src='t')
check('多視窗：網路異常 → 只點確定，回登入畫面 halt（不按登錄）',
      r['status'] == 'halt' and clicks == [('click', str(netwatch.CONFIRM[0]), str(netwatch.CONFIRM[1]))] and not reads, f'{r} {clicks}')
netwatch._match = _m
netwatch.HALT.unlink(missing_ok=True)
os.environ['PSA_TEST_PROCS'] = 'PrimalSA'

# relogin.py：多視窗 → 109，什麼都不點
import relogin  # noqa: E402
os.environ['PSA_TEST_PROCS'] = 'PrimalSA,PrimalSA2'
rg = []
uikit.preflight = lambda src, fast=True: 0
uikit.gui = lambda *a, **k: rg.append(a)
uikit.screen = lambda *a, **k: {'state': 'idle'}
_uf = uikit.fail
uikit.fail = lambda src, rc, msg: rc
check('relogin.py run --confirm：多視窗 → 109、沒點任何東西', relogin.run(confirm=True) == relogin.EXIT_MULTI == 109 and not rg)
check('relogin.py --dry-run 也擋（109）', relogin.run(dry_run=True) == 109)
uikit.fail = _uf
os.environ['PSA_TEST_PROCS'] = 'PrimalSA'

# ================================================================ 5) spawn_detached 傳 PSA_CLIENT；errlog client 欄
import winenv  # noqa: E402
seen = {}


class FakeP:
    pid = 4242


def fake_popen(argv, **kw):
    seen.update(kw)
    return FakeP()


os.environ['PSA_CLIENT'] = 'PrimalSA2'
check('spawn_detached：子程序環境帶 PSA_CLIENT=PrimalSA2', winenv.spawn_detached(['x'], popen=fake_popen) == 4242 and seen['env'].get('PSA_CLIENT') == 'PrimalSA2')
os.environ.pop('PSA_CLIENT')
seen.clear()
winenv.spawn_detached(['x'], popen=fake_popen)
check('spawn_detached：沒設就不帶（與改版前相同）', 'PSA_CLIENT' not in seen['env'])

errlog.add, errlog.fix = _eadd, _efix
el = Path(tempfile.mkdtemp()) / 'errlog.jsonl'
errlog.add('主視窗', source='t', path=el)
os.environ['PSA_CLIENT'] = 'PrimalSA2'
errlog.add('第二視窗', source='t', path=el)
os.environ.pop('PSA_CLIENT')
rows = [json.loads(x) for x in el.read_text(encoding='utf-8').splitlines()]
check('errlog：主視窗格式不變（沒有 client 欄）、非主視窗加 client', 'client' not in rows[0] and rows[1].get('client') == 'PrimalSA2', str(rows))

# ================================================================ 6) gui.sh：pipefail 退出碼、相對截圖路徑
def run_sh(*args, env_extra=None):
    env = dict(os.environ)
    env.pop('WSLENV', None)
    env.update(env_extra or {})
    return subprocess.run(['bash', str(GUI / 'gui.sh'), *args], capture_output=True, text=True, env=env, timeout=30)


r = run_sh('info', env_extra={'FAKE_PS_RC': '7'})
take_calls()
check('gui.sh：powershell 退出碼 7 → gui.sh 也回 7（不被 | tr 吃掉）', r.returncode == 7, str(r.returncode))
r = run_sh('info')
take_calls()
check('gui.sh：成功回 0、輸出照轉', r.returncode == 0 and 'fake ok' in r.stdout)
cdir = SH / 'clients' / 'PrimalSA2'
existed, pexisted = cdir.exists(), cdir.parent.exists()
r = run_sh('shot', 'zz-cc-test.png', env_extra={'PSA_CLIENT': 'PrimalSA2'})
c = take_calls()
argp = c[0]['argv'][-1] if c else ''
check('gui.sh shot 相對檔名：PrimalSA2 → tools/.cache/clients/PrimalSA2/', argp.replace('\\', '/').endswith('.cache/clients/PrimalSA2/zz-cc-test.png'), argp)
r = run_sh('shot', 'zz-cc-test.png')
c = take_calls()
argp = c[0]['argv'][-1] if c else ''
check('gui.sh shot 相對檔名：主視窗 → tools/.cache/（不變）', argp.replace('\\', '/').endswith('tools/.cache/zz-cc-test.png'), argp)
r = run_sh('shot', 'zz.png', env_extra={'PSA_CLIENT': ' primalsa.EXE '})
c = take_calls()
check('gui.sh：PSA_CLIENT= primalsa.EXE = 主視窗資料夾', c and c[0]['argv'][-1].replace('\\', '/').endswith('tools/.cache/zz.png'), str(c))
if not existed:
    try:
        cdir.rmdir()                     # 測試建的空資料夾收掉
        if not pexisted:
            cdir.parent.rmdir()
    except OSError:
        pass

# ================================================================ 7) gui.ps1 / psawin.ps1 靜態檢查
gp = (GUI / 'gui.ps1').read_text(encoding='utf-8-sig')
pw = (GUI / 'psawin.ps1').read_text(encoding='utf-8-sig')
check('gui.ps1：click / dclick / drag / key 先看 Test-PsaVerifyHalt → exit 9', 'Test-PsaVerifyHalt' in gp and 'exit 9' in gp)
check('gui.ps1：相對截圖 / gui-session.txt 用 Get-PsaCacheDir', gp.count('Get-PsaCacheDir $Client') == 2)
check('gui.ps1：舊 server 沒新函式會重載 psawin', "Test-Path Function:\\Test-PsaVerifyHalt" in gp)
check('psawin.ps1：Get-PsaCacheDir / Test-PsaVerifyHalt（verify-halt.json）', 'function Get-PsaCacheDir' in pw and 'verify-halt.json' in pw)
for f in ('gui.ps1', 'psawin.ps1', 'test_psawin.ps1'):
    check(f'{f} 是 UTF-8 with BOM', (GUI / f).read_bytes()[:3] == b'\xef\xbb\xbf')

# ---- 守門 ----
c = take_calls()
check('沒有任何意外的 powershell.exe 呼叫', not c, str(c))
print(f'FAIL 數: {failed}')
sys.exit(1 if failed else 0)
