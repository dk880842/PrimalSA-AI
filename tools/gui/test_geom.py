#!/usr/bin/env python3
"""座標換算層離線測試（不碰遊戲）：
  ① test_geom.ps1：psageom.ps1 的換算數學 / 2880×1659 恆等（與舊公式、舊 DrawImage 路徑逐位元組相同）/ 往返誤差 / PSA_GEOM=off / fit 尺寸計算；
  ② layout.py 的三個判斷（座標常數 / 樣板 / 守衛）用假的 gui.ps1 info 輸出驗證；
  ③ gui.ps1 的靜態檢查（座標都走換算層、fit 指令與 info 欄位存在、BOM）。
用法：uv run --no-project python tools/gui/test_geom.py"""
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import testenv  # noqa: E402,F401
import layout  # noqa: E402
import winenv  # noqa: E402

GUI = Path(__file__).resolve().parent
fails = 0


def check(name, ok, detail=''):
    global fails
    print(('PASS ' if ok else 'FAIL ') + name + ('' if ok else f'  {detail}'))
    if not ok:
        fails += 1


# ① PowerShell 端數學
r = winenv.run_ps('test_geom.ps1', timeout=300)
ps_pass = len(re.findall(r'^PASS ', r.stdout, re.M))
ps_fail = [ln for ln in r.stdout.splitlines() if ln.startswith('FAIL')]
m = re.search(r'SUMMARY (\d+)/(\d+)', r.stdout)
check(f'test_geom.ps1 全過（{m[1]}/{m[2]}）' if m else 'test_geom.ps1 有 SUMMARY', bool(m) and m[1] == m[2] and not ps_fail and r.returncode == 0,
      '\n'.join(ps_fail) + r.stderr[-500:])
print(f'   （PowerShell 端 {ps_pass} 項）')

# ② layout.py
os.environ.pop('PSA_LAYOUT', None)


class FakeRun:
    def __init__(self, out):
        self.out = out

    def __call__(self, script, *args, timeout=None):
        class R:
            stdout = self.out
        return R()


def with_info(out):
    layout._cache.clear()
    winenv_run = layout.winenv.run_ps
    layout.winenv.run_ps = FakeRun(out)
    try:
        return dict(phys=layout.current(), logical=layout.logical(), resolve=layout.resolve(), tpl=layout.template_layout(), st=layout.status())
    finally:
        layout.winenv.run_ps = winenv_run


lap = with_info('client=2880x1659 origin=(0,45) scale=2 shot=1440x830 foreground=False layout=2880x1659 phys=2880x1659 sx=2 sy=2 proportional=True\n')
check('筆電：phys / logical / resolve / 樣板都是 2880x1659、不縮放', lap['phys'] == lap['logical'] == lap['resolve'] == lap['tpl'] == '2880x1659' and not lap['st']['scaled'] and lap['st']['templates'])
old = with_info('client=2880x1659 origin=(0,45) scale=2 shot=1440x830 foreground=False\n')
check('舊格式 info（沒有 layout=）：行為同筆電', old['phys'] == old['logical'] == old['resolve'] == '2880x1659' and old['tpl'] == '2880x1659')
ext = with_info('client=1728x995 origin=(96,31) scale=1.2 shot=1440x830 foreground=False layout=2880x1659 phys=1728x995 sx=1.2 sy=1.1995 proportional=True\n')
check('1728x995：current 仍回實體、座標常數 2880x1659、樣板就緒（P3 TEMPLATE_PHYS）、縮放中、守衛放行',
      ext['phys'] == '1728x995' and ext['logical'] == '2880x1659' and ext['resolve'] == '2880x1659' and ext['tpl'] == '1728x995' and ext['st']['scaled'] and ext['st']['templates'] and ext['st']['ok'], str(ext))
check('1728x995：不被當成 SUPPORTED（上層 current() in SUPPORTED 守衛不放行）', ext['phys'] not in layout.SUPPORTED)
off = with_info('client=1728x995 origin=(96,31) scale=2 shot=864x498 foreground=False\n')   # PSA_GEOM=off：沒有 layout=
check('PSA_GEOM=off 的 1728x995：logical 退回實體、座標常數 DEFAULT（與舊行為相同）、不算縮放、守衛擋', off['logical'] == '1728x995' and off['resolve'] == '2880x1659' and not off['st']['scaled'] and not off['st']['ok'])
w19 = with_info('client=1920x1017 origin=(0,23) scale=2 shot=960x508 foreground=False layout=1920x1017 phys=1920x1017 sx=2 sy=2 proportional=False\n')
check('1920x1017 舊版面：座標常數 / 樣板都是 1920x1017', w19['resolve'] == w19['tpl'] == '1920x1017' and not w19['st']['scaled'])
n19 = with_info('client=1920x1009 origin=(0,23) scale=2 shot=960x504 foreground=False layout=1920x1009 phys=1920x1009 sx=2 sy=2 proportional=False\n')
check('1920x1009（最大化外接）：座標常數 DEFAULT、樣板 None', n19['resolve'] == '2880x1659' and n19['tpl'] is None and not n19['st']['scaled'])
layout._cache.clear()

# ③ gui.ps1 靜態檢查
g = (GUI / 'gui.ps1').read_text(encoding='utf-8-sig')
check('gui.ps1 / psageom.ps1 / test_geom.ps1 都有 BOM', all((GUI / f).read_bytes()[:3] == b'\xef\xbb\xbf' for f in ('gui.ps1', 'psageom.ps1', 'test_geom.ps1')))
check('gui.ps1 dot-source psageom.ps1', "psageom.ps1" in g and "$Gm = Get-PsaGeom" in g)
body = re.sub(r'(?m)^\s*#.*$', '', g)
check('gui.ps1 座標換算不再直接 × $Scale（只剩 Get-PsaGeom 傳入與 info / -Scale 判斷）', len(re.findall(r'\*\s*\$Scale', body)) == 0, str(re.findall(r'.*\*\s*\$Scale.*', body)))
check('gui.ps1 有 fit 指令與 PSA_GEOM / Sample 參數', "'fit' {" in g and "$env:PSA_GEOM" in g and "[string]$Sample" in g)
check('gui.ps1 fit 不搶前景（SW_SHOWNOACTIVATE / SWP_NOACTIVATE）、不呼叫 Focus / SetFg', "ShowWindow($h, 4)" in g and '0x0014' in g and not re.search(r"'fit' \{[^}]*?\bFocus\b", g.split("'fit' {")[1].split("'key' {")[0]))
check('winenv 白名單含 Sample、INPUT_CMDS 含 fit', 'Sample' in winenv.SERVER_NAMED['gui'] and 'fit' in winenv.INPUT_CMDS)

# ④ PSA_GEOM 經 WSLENV 帶進 powershell.exe（WSL 才需要）
_old = {k: os.environ.get(k) for k in ('PSA_GEOM', 'WSLENV')}
os.environ['PSA_GEOM'] = 'off'; os.environ['WSLENV'] = 'FOO/p'
e = winenv.child_env()
if winenv.platform_kind() == 'wsl':
    check('child_env：WSL 把 PSA_GEOM 加進 WSLENV（保留原有項目）', e['WSLENV'].split(':') == ['FOO/p', 'PSA_GEOM'], e['WSLENV'])
else:
    check('child_env：非 WSL 不動 WSLENV', e['WSLENV'] == 'FOO/p')
del os.environ['PSA_GEOM']
check('child_env：沒設 PSA_GEOM 不動 WSLENV', winenv.child_env().get('WSLENV') == 'FOO/p')
for k, v in _old.items():
    if v is None:
        os.environ.pop(k, None)
    else:
        os.environ[k] = v

print('OK' if not fails else f'FAIL {fails} 項')
sys.exit(1 if fails else 0)
