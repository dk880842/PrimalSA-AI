#!/usr/bin/env python3
"""多視窗 P1 / P2 離線測試（不碰遊戲、不呼叫真的 powershell.exe）：
  clients.py 名稱 / 名單；winenv.client_env、一次性呼叫帶 PSA_CLIENT（WSL 加 WSLENV）；常駐 server 請求帶 client；
  actlog 非主視窗加 [程序名]；gui.sh / mirror.sh 轉傳 PSA_CLIENT。
整支測試期間 PATH 最前面放假的 powershell.exe（記錄每次呼叫）：預期會呼叫的測試讀完就清空，最後確認沒有任何意外的呼叫。
PowerShell 端（psawin.ps1 選程序、點擊鎖）見 test_psawin.ps1。
  uv run --no-project python tools/gui/test_multiclient.py
"""
import json
import os
import stat
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import testenv  # noqa: E402,F401  紀錄檔轉向暫存
import actlog  # noqa: E402
import clients  # noqa: E402
import winenv  # noqa: E402

GUI = Path(__file__).resolve().parent
failed = 0


def check(name, ok, detail=''):
    global failed
    print(('PASS ' if ok else 'FAIL ') + name + (f'  {detail}' if detail and not ok else ''))
    if not ok:
        failed += 1


# ---- 假 powershell.exe（PATH 最前面）----
tmp = Path(tempfile.mkdtemp(prefix='psa-mc-'))
bindir = tmp / 'bin'
bindir.mkdir()
calls = tmp / 'ps-calls.jsonl'
fake = bindir / 'powershell.exe'
fake.write_text('#!' + sys.executable + '\n'
                'import json, os, sys\n'
                f'open({str(calls)!r}, "a", encoding="utf-8").write(json.dumps({{"argv": sys.argv[1:], '
                '"PSA_CLIENT": os.environ.get("PSA_CLIENT"), "WSLENV": os.environ.get("WSLENV")}) + "\\n")\n'
                'print("fake ok")\n', encoding='utf-8')
fake.chmod(fake.stat().st_mode | stat.S_IXUSR)
os.environ['PATH'] = str(bindir) + os.pathsep + os.environ.get('PATH', '')
os.environ.pop('PSA_CLIENT', None)
os.environ['PSA_GUI_SERVER'] = '0'      # 一次性路徑（server 另外用假 server 測）


def take_calls():
    if not calls.exists():
        return []
    out = [json.loads(x) for x in calls.read_text(encoding='utf-8').splitlines() if x.strip()]
    calls.unlink()
    return out


# ---- clients.py ----
check('沒設 = PrimalSA', clients.name({}) == 'PrimalSA' and clients.is_default('') and clients.log_tag('') == '')
check('去空白 / .exe', clients.normalize(' PrimalSA2.exe ') == 'PrimalSA2')
check('PrimalSA2 log 標籤', clients.log_tag('PrimalSA2') == '[PrimalSA2] ')
check('主視窗大小寫不分', clients.is_default('primalsa') and clients.log_tag('PRIMALSA') == '')
check('名單寫死：PrimalSA2 = DKBO6～10', clients.roster('PrimalSA2') == ['DKBO6', 'DKBO7', 'DKBO8', 'DKBO9', 'DKBO10'])
check('名單寫死：主視窗 = DKBO～5', clients.roster('PrimalSA') == ['DKBO', 'DKBO2', 'DKBO3', 'DKBO4', 'DKBO5'])
check('不認得的程序 → 空名單', clients.roster('PrimalSA9') == [])
check('名稱驗證擋萬用字元', clients.valid('PrimalSA2') and not clients.valid('Primal*') and not clients.valid('a b'))

# ---- winenv.client_env ----
check('沒設 PSA_CLIENT → None（照舊繼承）', winenv.client_env({'PATH': 'x'}, 'wsl') is None
      and winenv.client_env({'PSA_CLIENT': '  '}, 'wsl') is None)
e = winenv.client_env({'PSA_CLIENT': 'PrimalSA2'}, 'wsl')
check('WSL：WSLENV 加 PSA_CLIENT', e['WSLENV'] == 'PSA_CLIENT' and e['PSA_CLIENT'] == 'PrimalSA2')
e = winenv.client_env({'PSA_CLIENT': 'PrimalSA2', 'WSLENV': 'FOO/p:BAR'}, 'wsl')
check('WSL：保留原本 WSLENV', e['WSLENV'] == 'FOO/p:BAR:PSA_CLIENT')
e = winenv.client_env({'PSA_CLIENT': 'PrimalSA2', 'WSLENV': 'PSA_CLIENT/u'}, 'wsl')
check('WSL：已列過不重複', e['WSLENV'] == 'PSA_CLIENT/u')
e = winenv.client_env({'PSA_CLIENT': 'PrimalSA2'}, 'windows')
check('Windows 原生：不動 WSLENV', 'WSLENV' not in e and e['PSA_CLIENT'] == 'PrimalSA2')

# ---- 一次性呼叫（假 powershell.exe）----
r = winenv.run_ps('gui.ps1', 'info')
c = take_calls()
check('沒設：一次性呼叫不帶 PSA_CLIENT', r.returncode == 0 and len(c) == 1 and c[0]['PSA_CLIENT'] is None
      and c[0]['argv'][-1] == 'info', str(c))
os.environ['PSA_CLIENT'] = 'PrimalSA2'
r = winenv.run_ps('gui.ps1', 'click', '10', '20')
c = take_calls()
wsl = winenv.platform_kind() == 'wsl'
check('PSA_CLIENT=PrimalSA2：一次性呼叫帶下去' + ('（WSLENV 含 PSA_CLIENT）' if wsl else ''),
      len(c) == 1 and c[0]['PSA_CLIENT'] == 'PrimalSA2' and (not wsl or 'PSA_CLIENT' in (c[0]['WSLENV'] or '').split(':')), str(c))
os.environ.pop('PSA_CLIENT')

# ---- 常駐 server：請求帶 client（假 server 回顯請求）----
FAKE_SRV = r'''
import sys, json, os
out = sys.stdout.buffer
def send(o): out.write(b'\n\x1ePSA ' + json.dumps(o).encode('utf-8') + b'\n'); out.flush()
send({'ready': True, 'pid': os.getpid()})
for line in sys.stdin:
    q = json.loads(line)
    if q.get('cmd') == 'quit':
        send({'id': q['id'], 'rc': 0, 'out': 'bye', 'err': ''}); break
    send({'id': q['id'], 'rc': 0, 'out': json.dumps(q), 'err': ''})
'''
fs = tmp / 'fake_srv.py'
fs.write_text(FAKE_SRV, encoding='utf-8')
srv = winenv.GuiServer(argv=[sys.executable, str(fs)])
try:
    q0 = json.loads(srv.call('gui.ps1', ['pixel', '1', '2'], 10).stdout)
    os.environ['PSA_CLIENT'] = ' PrimalSA2 '
    q1 = json.loads(srv.call('gui.ps1', ['click', '1', '2'], 10).stdout)
    os.environ['PSA_CLIENT'] = 'PrimalSA3'
    q2 = json.loads(srv.call('gui.ps1', ['pixel', '1', '2'], 10).stdout)
    os.environ.pop('PSA_CLIENT')
    q3 = json.loads(srv.call('gui.ps1', ['pixel', '1', '2'], 10).stdout)
    check('server 請求：沒設 client = 空字串（serve.ps1 移除 PSA_CLIENT = 主視窗）', q0.get('client') == '' and q3.get('client') == '', f'{q0} {q3}')
    check('server 請求：同一個 server 依呼叫當下的 PSA_CLIENT 帶 client', q1.get('client') == 'PrimalSA2' and q2.get('client') == 'PrimalSA3', f'{q1} {q2}')
finally:
    srv.close()

# ---- serve.ps1 每個請求都重設 PSA_CLIENT（靜態檢查，真的 server 要 powershell）----
sv = (GUI / 'serve.ps1').read_text(encoding='utf-8-sig')
check('serve.ps1：有 client 設 env、沒有就移除', '$env:PSA_CLIENT = $__psa_client' in sv and 'Remove-Item Env:PSA_CLIENT' in sv)

# ---- actlog ----
log = Path(os.environ['PSA_LOG_DIR']) / 'actions.log'
actlog.add('walk', '主視窗', path=log)
os.environ['PSA_CLIENT'] = 'PrimalSA2'
actlog.add('walk', '第二視窗', path=log)
os.environ['PSA_CLIENT'] = 'PrimalSA'
actlog.add('walk', '明設主視窗', path=log)
os.environ.pop('PSA_CLIENT')
ls = log.read_text(encoding='utf-8').splitlines()
check('actlog：主視窗格式不變', ls[-3][8:] == ' walk 主視窗' and ls[-1][8:] == ' walk 明設主視窗', str(ls[-3:]))
check('actlog：非主視窗加 [PrimalSA2]', ls[-2][8:] == ' [PrimalSA2] walk 第二視窗', ls[-2])
hourly = list(actlog.hourly_dir(log).glob('*.log'))
check('actlog：分檔同樣有標籤', hourly and '[PrimalSA2] walk 第二視窗' in hourly[0].read_text(encoding='utf-8'))
gp = (GUI / 'gui.ps1').read_text(encoding='utf-8-sig')
check('gui.ps1 ActLog：非主視窗加 [程序名]（同規則）', "Test-PsaDefaultClient $Client" in gp and '"[$Client] "' in gp)

# ---- gui.sh / mirror.sh 轉傳 ----
def run_sh(script, *args, env_extra=None):
    env = dict(os.environ)
    env.pop('WSLENV', None)
    env.update(env_extra or {})
    return subprocess.run(['bash', str(GUI / script), *args], capture_output=True, text=True, env=env, timeout=30)


run_sh('gui.sh', 'info')
c = take_calls()
check('gui.sh 沒設：不加 WSLENV、不帶 PSA_CLIENT', len(c) == 1 and c[0]['PSA_CLIENT'] is None and not c[0]['WSLENV'], str(c))
run_sh('gui.sh', 'key', '{ESC}', env_extra={'PSA_CLIENT': 'PrimalSA2', 'WSLENV': 'FOO'})
c = take_calls()
check('gui.sh PSA_CLIENT=PrimalSA2：WSLENV=FOO:PSA_CLIENT', len(c) == 1 and c[0]['PSA_CLIENT'] == 'PrimalSA2'
      and c[0]['WSLENV'] == 'FOO:PSA_CLIENT' and c[0]['argv'][-2:] == ['key', '{ESC}'], str(c))
run_sh('mirror.sh', env_extra={'PSA_CLIENT': 'PrimalSA2'})
c = take_calls()
check('mirror.sh PSA_CLIENT=PrimalSA2：WSLENV 帶 PSA_CLIENT', len(c) == 1 and c[0]['PSA_CLIENT'] == 'PrimalSA2'
      and c[0]['WSLENV'] == 'PSA_CLIENT', str(c))

# ---- .ps1 不再有寫死的 Get-Process PrimalSA ----
left = [p.name for p in GUI.glob('*.ps1') if 'Get-Process PrimalSA' in p.read_text(encoding='utf-8-sig', errors='replace')
        or 'GetProcessesByName("PrimalSA")' in p.read_text(encoding='utf-8-sig', errors='replace')]
check('tools/gui/*.ps1 沒有寫死的 PrimalSA 程序比對', not left, str(left))
nobom = [p.name for p in GUI.glob('*.ps1') if not p.read_bytes().startswith(b'\xef\xbb\xbf')]
check('tools/gui/*.ps1 都是 UTF-8 with BOM', not nobom, str(nobom))

# ---- 守門：沒有意外的 powershell 呼叫 ----
c = take_calls()
check('沒有任何意外的 powershell.exe 呼叫', not c, str(c))

print('全部通過' if not failed else f'失敗 {failed} 項')
sys.exit(1 if failed else 0)
