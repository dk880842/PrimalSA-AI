#!/usr/bin/env python3
"""視窗 → 帳號對照（斷線重登核對帳號欄用；只用標準函式庫）。

使用者 2026-10-15 規則：每個遊戲視窗有固定帳號，登入畫面帳號欄對得上才能自動按「登錄」；
帳號記憶是所有視窗共用的，帳號欄是別的帳號時只清空並重打帳號欄（密碼欄絕對不碰，兩個帳號密碼相同）。

**帳號名不進 git**（repo 公開）：對照放在本機設定檔 `tools/gui/accounts.local.json`（.gitignore 排除 `*.local.json`），
格式（鍵 = 程序名稱，同 PSA_CLIENT；值 = 帳號）：
    {"PrimalSA": "<主視窗帳號>", "PrimalSA2": "<第二視窗帳號>"}
環境變數 PSA_ACCOUNTS_FILE 可換路徑（離線測試用；testenv 一律指到不存在的檔 = 沒設定檔）。
本模組與呼叫端都**不把帳號名寫進任何 log / errlog / 截圖檔名**（log 只寫「帳號欄核對：符合 / 不符 / 讀不出」）。

  import accounts
  st, acct = accounts.for_client()     # ('ok', 帳號) / ('none', '') 沒設定檔 / ('missing', '') 這個視窗不在對照表 / ('invalid', 理由)
  accounts.classify(texts, acct)       # OCR 各倍數讀到的字 → 'self'（= 本視窗帳號）/ 'other'（讀得出但不是）/ 'unreadable'
  accounts.classify(texts, acct, caret=True, others=accounts.all_accounts())   # 欄位有文字游標時（重打後）：字尾游標字元容錯
  accounts.canon('DKB0-01')            # 容錯正規化：小寫、去空白、o→0、i / l / | → 1（只合併 OCR 易混字，數字之間不合併）

命令列（不印帳號名）：
  python tools/gui/accounts.py check    → 設定檔在不在、哪些視窗有設定（只印長度）、容錯後能不能互相區分；退出碼 0 可用 / 1 沒設定檔 / 2 格式錯
"""
import json
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import clients  # noqa: E402

DEFAULT_PATH = Path(__file__).resolve().parent / 'accounts.local.json'
ENV = 'PSA_ACCOUNTS_FILE'
ACCT_RE = re.compile(r'^[A-Za-z0-9_]{1,32}$')     # 只收英數 + 底線（WM_CHAR 逐字打；不收大括號等 SendKeys 特殊字）
# OCR 易混字：只在「字母 ↔ 數字」之間合併（Windows OCR 把帳號裡的小寫 o 讀成 0，實測 2026-10-15 主視窗登入畫面 fixture 2 / 3 / 4 / 5 / 6 倍都一樣）。
# 數字與數字之間絕不合併（1 / 2 / 7 讀錯 = 不符 → 重打 → 再不符就停手），所以兩個帳號只差尾碼也不會混淆。
_CONFUSE = str.maketrans({'o': '0', 'i': '1', 'l': '1', '|': '1'})


def path() -> Path:
    p = os.environ.get(ENV)
    return Path(p) if p else DEFAULT_PATH


def canon(s: str) -> str:
    return re.sub(r'\s+', '', s or '').lower().translate(_CONFUSE)


def load() -> tuple:
    """→ ('ok', {程序名小寫: 帳號}) / ('none', {}) / ('invalid', 理由)。理由不含帳號名"""
    p = path()
    if not p.exists():
        return 'none', {}
    try:
        d = json.loads(p.read_text(encoding='utf-8-sig'))
    except (OSError, ValueError) as e:
        return 'invalid', f'設定檔讀不了 / 不是 JSON（{type(e).__name__}）'
    if not isinstance(d, dict) or not d:
        return 'invalid', '設定檔要是 {"程序名稱": "帳號", ...} 物件'
    out = {}
    for k, v in d.items():
        if not isinstance(k, str) or not clients.valid(clients.normalize(k)):
            return 'invalid', '設定檔有不合法的程序名稱'
        if not isinstance(v, str) or not ACCT_RE.fullmatch(v):
            return 'invalid', f'{clients.normalize(k)} 的帳號格式不對（只收英數 / 底線，1～32 字）'
        out[clients.normalize(k).lower()] = v
    cs = [canon(v) for v in out.values()]
    if len(set(cs)) != len(cs):
        return 'invalid', '有兩個視窗的帳號容錯正規化後相同（o/0、l/1 混淆），無法區分'
    return 'ok', out


def for_client(n: str | None = None) -> tuple:
    """這個視窗的帳號：('ok', 帳號) / ('none', '') / ('missing', '') / ('invalid', 理由)"""
    st, d = load()
    if st != 'ok':
        return st, (d if st == 'invalid' else '')
    a = d.get(clients.name().lower() if n is None else clients.normalize(n).lower())
    return ('ok', a) if a else ('missing', '')


def all_accounts() -> list:
    st, d = load()
    return list(d.values()) if st == 'ok' else []


# 文字游標（重打帳號後欄位仍有焦點，字尾一條細直線；Windows OCR 讀成 | / I / l / 1 / ! / ] 之類，各倍數還不一定一樣）。
# 2026-10-16 p1 17:03、p2 17:24、p3 17:05 / 17:25 重打後核對「不符 / 讀不出」，截圖看帳號其實正確、尾端有「|」= 這個原因。
CARET_CHARS = '|Il1i!][/'
_VALID = re.compile(r'[a-z0-9_]+')


def _candidates(t: str, caret: bool) -> set:
    """一個倍數讀到的字 → 可能的帳號（正規化後）。caret=True 時字尾像游標的字元多給一個「去掉它」的候選"""
    c = canon(t)
    if not c:
        return set()
    out = {c}
    raw = re.sub(r'\s+', '', t or '')
    if caret and len(raw) > 1 and raw[-1] in CARET_CHARS:
        out.add(canon(raw[:-1]))
    return {x for x in out if _VALID.fullmatch(x)}


def classify(texts, mine: str, min_reads: int = 2, caret: bool = False, others=()) -> str:
    """OCR 結果判定。texts = 各放大倍數各自讀到的整欄文字（list）。
    一致性規則（讀錯帳號比讀不出危險得多）：至少 min_reads 個倍數讀到字、正規化後全部相同、只含英數 / 底線，才算讀得出；
    否則 'unreadable'。讀得出時 = 本視窗帳號 → 'self'，其他（別的帳號 / 認不得的字）→ 'other'。
    caret=True（重打帳號後欄位還有文字游標）：每個倍數的候選 = 原字 + 「字尾像游標的字元去掉」，各倍數候選的交集才算讀到的帳號；
    交集同時含本視窗帳號與 others（設定檔裡其他視窗的帳號）任一個 = 分不出是「本帳號 + 游標」還是「別的帳號」→ 'unreadable'（停手）"""
    if not caret:
        cs = [canon(t) for t in texts or [] if canon(t)]
        if len(cs) < min_reads or len(set(cs)) != 1 or not _VALID.fullmatch(cs[0]):
            return 'unreadable'
        return 'self' if cs[0] == canon(mine) else 'other'
    sets = [s for s in (_candidates(t, True) for t in texts or [] if canon(t)) if s]
    n_read = sum(1 for t in texts or [] if canon(t))
    if len(sets) < min_reads or len(sets) != n_read:
        return 'unreadable'
    inter = set.intersection(*sets)
    if not inter:
        return 'unreadable'
    m = canon(mine)
    if m in inter:
        rest = {canon(o) for o in others or () if canon(o) and canon(o) != m}
        return 'unreadable' if inter & rest else 'self'
    return 'other'                       # 讀得出但不是本帳號（呼叫端重打 / 停手，不會按登錄）


def main() -> int:
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    st, d = load()
    print(f'設定檔：{path()}')
    if st == 'none':
        print('沒有設定檔 → 斷線重登維持舊行為（單一視窗只按登錄、多視窗不自動登錄）')
        return 1
    if st == 'invalid':
        print(f'格式錯：{d} → 視同沒設定檔')
        return 2
    for k, v in d.items():
        print(f'  {k}：已設定（{len(v)} 字）')
    print(f'目前 PSA_CLIENT = {clients.name()}：{"有" if for_client()[0] == "ok" else "沒有"}對應帳號；容錯正規化後各帳號可互相區分')
    return 0


if __name__ == '__main__':
    sys.exit(main())
