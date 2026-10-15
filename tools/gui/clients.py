#!/usr/bin/env python3
"""多視窗（多客戶端）身分（只用標準函式庫）。

同機多開時每個遊戲視窗用不同名稱的執行檔（GameClient/PrimalSA.exe、PrimalSA2.exe + 目錄連結 PrimalSA2_Data …），
所以「哪個視窗」= 程序名稱。環境變數 PSA_CLIENT 指定要操作的程序名稱，不設 = PrimalSA（主視窗，原本的單視窗行為）。
PowerShell 端的同一套規則在 psawin.ps1（Get-PsaClient / Find-PsaProcess）；兩邊的正規化要一致。

  import clients
  clients.name()          # 'PrimalSA' / 'PrimalSA2'（去空白、去 .exe）
  clients.is_default()    # 是不是主視窗
  clients.log_tag()       # 操作 log 前綴：主視窗 ''；其他 '[PrimalSA2] '
  clients.roster()        # 這個視窗的角色名單（寫死；後續階段去硬編碼用，目前還沒有程式用它）

每個視窗自己的狀態檔（第 3a 步，2026-10-15）：
  clients.cache_dir()     # 主視窗 = tools/.cache（原路徑，零遷移）；其他 = tools/.cache/clients/<程序名>/
  clients.cpath('grind.lock')          # cache_dir() / 檔名
  clients.notes_dir()     # 主視窗 = notes；其他 = notes/clients/<程序名>/（quest-events.log、quest-log.md）
  clients.npath('quest-events.log')
  clients.SHARED_CACHE    # 全部視窗共用的 tools/.cache（樣板、圖庫、errlog、actions.log、verify-halt.json…）
  clients.running()       # 正在執行的遊戲程序名稱（PrimalSA、PrimalSA2…；查不到 None）
  clients.multi_window()  # 這個程序是不是「多視窗」情境（非主視窗，或還有別的 PrimalSA* 在跑；查不到當作是）
路徑在 import 時依 PSA_CLIENT 決定（一個程序只操作一個視窗）；沒設 PSA_CLIENT 時所有路徑與改版前逐字相同。

命令列：python tools/gui/clients.py   → 印目前 PSA_CLIENT 對應的名稱、名單、狀態資料夾
"""
import os
import re
import subprocess
import sys
from pathlib import Path

DEFAULT = 'PrimalSA'
ROOT = Path(__file__).resolve().parents[2]
SHARED_CACHE = ROOT / 'tools' / '.cache'      # 全部視窗共用（主視窗的狀態檔也在這裡：零遷移）
NOTES_DIR = ROOT / 'notes'
GAME_RE = re.compile(r'^PrimalSA\d*$', re.I)  # 遊戲程序名稱（PrimalSA、PrimalSA2、PrimalSA3…）
NAME_RE = re.compile(r'^[A-Za-z0-9_.-]{1,64}$')   # 與 psawin.ps1 相同：只收程序名稱

# 程序名稱 → 角色名單（2026-10-15 使用者確認，寫死即可、不自動讀名單；真名是字母 O）。
# 第 1 個是隊長。目前只供後續階段（角色名去硬編碼）使用，P1 / P2 沒有程式讀它。
ROSTERS = {
    'PrimalSA': ['DKBO', 'DKBO2', 'DKBO3', 'DKBO4', 'DKBO5'],
    'PrimalSA2': ['DKBO6', 'DKBO7', 'DKBO8', 'DKBO9', 'DKBO10'],
}


def normalize(raw: str | None) -> str:
    """去空白、去結尾 .exe；空的 = PrimalSA。不驗格式（驗證交給 valid() / psawin.ps1）"""
    n = (raw or '').strip()
    if n.lower().endswith('.exe'):
        n = n[:-4]
    return n or DEFAULT


def name(env=None) -> str:
    env = os.environ if env is None else env
    return normalize(env.get('PSA_CLIENT'))


def valid(n: str) -> bool:
    return bool(NAME_RE.fullmatch(n))


def is_default(n: str | None = None) -> bool:
    return (name() if n is None else normalize(n)).lower() == DEFAULT.lower()


def log_tag(n: str | None = None) -> str:
    n = name() if n is None else normalize(n)
    return '' if is_default(n) else f'[{n}] '


def roster(n: str | None = None) -> list[str]:
    """寫死的名單；查不到回空 list（大小寫不分）"""
    n = name() if n is None else normalize(n)
    for k, v in ROSTERS.items():
        if k.lower() == n.lower():
            return list(v)
    return []


def dir_name(n: str | None = None) -> str:
    """視窗的資料夾名：名單裡有的用名單的寫法（大小寫不分 → 同一個資料夾）；不合法 / 全是點的名稱換成安全字元，
    絕不讓 PSA_CLIENT 跳出 clients/ 資料夾（psawin.ps1 本來就不會操作不合法的名稱）"""
    n = name() if n is None else normalize(n)
    for k in ROSTERS:
        if k.lower() == n.lower():
            return k
    n = re.sub(r'[^A-Za-z0-9_.-]', '_', n)[:64]
    return '_' + n if set(n) <= {'.'} else n


def _ensure(d: Path, n) -> Path:
    """非主視窗、問的是自己（n=None）時先建好資料夾：各模組寫狀態檔前多半沒有 mkdir（主視窗的 tools/.cache / notes 本來就在）。
    離線測試（testenv 的 psatest- 暫存）不建，免得測試在真的 tools/.cache 留下空資料夾；建不起來不丟例外（寫檔那步自己會失敗）"""
    if n is None and 'psatest-' not in os.environ.get('PSA_LOG_DIR', ''):
        try:
            d.mkdir(parents=True, exist_ok=True)
        except OSError:
            pass
    return d


def cache_dir(n: str | None = None) -> Path:
    """這個視窗的狀態資料夾：主視窗 = tools/.cache（與改版前相同）；其他 = tools/.cache/clients/<程序名>（自己的會先建好）"""
    return SHARED_CACHE if is_default(n) else _ensure(SHARED_CACHE / 'clients' / dir_name(n), n)


def cpath(fname: str, n: str | None = None) -> Path:
    return cache_dir(n) / fname


def notes_dir(n: str | None = None) -> Path:
    """事件 log 資料夾：主視窗 = notes（與改版前相同，psa-hud 標題照讀）；其他 = notes/clients/<程序名>"""
    return NOTES_DIR if is_default(n) else _ensure(NOTES_DIR / 'clients' / dir_name(n), n)


def npath(fname: str, n: str | None = None) -> Path:
    return notes_dir(n) / fname


# ---- 正在執行的遊戲程序（多視窗判斷：netwatch 自動登錄、verify-halt）----
PS_LIST = ("[Diagnostics.Process]::GetProcesses() | Where-Object { $_.ProcessName -match '^PrimalSA\\d*$' } | "
           "ForEach-Object { $_.ProcessName }")
TEST_ENV = 'PSA_TEST_PROCS'       # 離線測試（testenv）用：逗號分隔的假程序清單，不呼叫 powershell


def running(timeout: float = 15.0) -> list[str] | None:
    """正在執行的遊戲程序名稱（排序、去重）。PowerShell 失敗 / 逾時 → None（呼叫端當作「不確定」）。
    只讀程序清單，不碰遊戲。測試：環境變數 PSA_TEST_PROCS（testenv 預設 'PrimalSA' = 單視窗）"""
    fake = os.environ.get(TEST_ENV)
    if fake is not None:
        return sorted({x.strip() for x in fake.split(',') if GAME_RE.match(x.strip())})
    try:
        r = subprocess.run(['powershell.exe', '-NoProfile', '-NonInteractive', '-Command', PS_LIST],
                           capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=timeout)
    except (OSError, subprocess.SubprocessError):
        return None
    if r.returncode != 0:
        return None
    return sorted({x.strip() for x in (r.stdout or '').splitlines() if GAME_RE.match(x.strip())})


def others_running(n: str | None = None, procs: list | None = None) -> list[str] | None:
    """除了這個視窗以外還在跑的遊戲程序；查不到 None"""
    n = name() if n is None else normalize(n)
    procs = running() if procs is None else procs
    if procs is None:
        return None
    return [p for p in procs if p.lower() != n.lower()]


def multi_window(n: str | None = None, procs: list | None = None) -> bool:
    """多視窗情境：非主視窗一律是；主視窗看有沒有別的 PrimalSA* 程序在跑（查不到 → 當作是，保守）"""
    if not is_default(n):
        return True
    o = others_running(n, procs)
    return o is None or bool(o)


def proc_client(pid) -> str | None:
    """Linux /proc：別的程序的 PSA_CLIENT（正規化後；沒設 = PrimalSA）；讀不到 None（不是 Linux / 沒權限 / 程序已結束）。
    grind 掃 heal --watch 用：只把同一個視窗的當成衝突"""
    try:
        raw = Path(f'/proc/{int(pid)}/environ').read_bytes()
    except (OSError, ValueError):
        return None
    for kv in raw.split(b'\0'):
        if kv.startswith(b'PSA_CLIENT='):
            return normalize(kv[11:].decode('utf-8', 'replace'))
    return DEFAULT


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    n = name()
    print(f'PSA_CLIENT → {n}{"（主視窗）" if is_default(n) else ""}{"" if valid(n) else "（名稱不合法）"}')
    print('名單：', ' '.join(roster(n)) or '（沒有寫死的名單）')
    print('狀態資料夾：', cache_dir(n), '｜事件 log：', notes_dir(n))
