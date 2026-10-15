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

命令列：python tools/gui/clients.py   → 印目前 PSA_CLIENT 對應的名稱與名單
"""
import os
import re
import sys

DEFAULT = 'PrimalSA'
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


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    n = name()
    print(f'PSA_CLIENT → {n}{"（主視窗）" if is_default(n) else ""}{"" if valid(n) else "（名稱不合法）"}')
    print('名單：', ' '.join(roster(n)) or '（沒有寫死的名單）')
