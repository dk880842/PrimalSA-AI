#!/usr/bin/env python3
"""遊戲視窗版面判斷（只用標準函式庫）：依客戶區大小決定用哪一套截圖座標。

支援的版面：
  '2880x1659'  原本的基準（2880×1659 客戶區 → 截圖 1440×830），ui/ 文件與各腳本的預設常數都以它為準
  '1920x1017'  1920×1080 螢幕最大化（截圖 960×508）；UI 約為 2880×1659 的 0.613 倍，座標見 ui/layout-1920x1017.md

  import layout
  layout.current()        # 實體客戶區 → '2880x1659' | '1920x1017' | 其他 'WxH' | None（遊戲沒開）；同一個行程只問一次（physical() 同義）
  layout.logical()        # 換算層認定的邏輯版面：與 2880×1659 同長寬比（例 1728×995）→ '2880x1659'
  layout.resolve()        # 套哪套座標常數：邏輯版面在 SUPPORTED 內就用它，否則 DEFAULT
  layout.template_layout()  # 樣板該存哪一份：實體尺寸在 SUPPORTED 內才有，否則 None（樣板未就緒）
  layout.SUPPORTED        # 支援的版面

P1（2026-10-11）：外接螢幕可用 `gui.sh fit` 把視窗設成 2880×1659 同比例（1728×995），gui.ps1 的換算層讓 1440×830 截圖座標仍然成立，
所以 resolve() / logical() 認它是 '2880x1659'（座標常數）；但 current() 仍回實體 '1728x995'，各腳本的 `current() != '2880x1659'` 守衛照舊擋下
（樣板 / 像素特徵未驗，P4 才放行）。

環境變數 PSA_LAYOUT=1920x1017 可直接指定（不問遊戲；例：遊戲沒開時用 walk.py --plan 試算）。
命令列：python tools/gui/layout.py   → 印出目前版面
"""
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import winenv  # noqa: E402

SUPPORTED = ('2880x1659', '1920x1017')
DEFAULT = '2880x1659'
_cache: list = []   # [{'phys': 'WxH', 'logical': 'WxH' | None, 'info': 原始 info 文字}]；空 = 還沒問


def _load() -> dict:
    if not _cache:
        try:
            out = winenv.run_ps('gui.ps1', 'info', timeout=30).stdout
        except Exception:   # 不是 Windows / WSL、powershell 逾時…
            out = ''
        m = re.search(r'client=(\d+)x(\d+)', out)
        lg = re.search(r'layout=(\d+x\d+)', out)   # P1 起 gui.ps1 info 追加的邏輯版面；舊輸出 / PSA_GEOM=off 沒有
        _cache.append({'phys': f'{m[1]}x{m[2]}' if m else None, 'logical': lg[1] if lg else None})
    return _cache[0]


def current() -> str | None:
    """目前遊戲客戶區「實體」大小 'WxH'（gui.ps1 info）；PSA_LAYOUT 優先。遊戲沒開或讀不到回 None。
    各腳本的版面守衛（`current() != '2880x1659'`）看的是它：同比例但非 2880×1659 的視窗（例 1728×995）目前仍判不支援（樣板 / 特徵未就緒，P4 再放行）"""
    env = os.environ.get('PSA_LAYOUT')
    if env:
        return env
    return _load()['phys']


physical = current   # 別名：明講「實體尺寸」


def logical() -> str | None:
    """「套哪套座標常數」用的邏輯版面：gui.ps1 的換算層認定與 2880×1659 同長寬比 → '2880x1659'（座標一律用 1440×830 截圖座標，換算在 gui.ps1）；
    其他回實體大小。PSA_LAYOUT 優先；info 沒有 layout=（舊版 / PSA_GEOM=off / prime 預填）時退回實體大小"""
    env = os.environ.get('PSA_LAYOUT')
    if env:
        return env
    d = _load()
    return d['logical'] or d['phys']


def prime(value: str) -> None:
    """已有可信來源（例：watch state 的 game.layout 剛讀到、≤2 s）時預先填快取，省掉 gui.ps1 info 那次呼叫（約 0.6 s）。已有快取就不蓋。
    只填實體大小（logical 之後由 logical() 退回實體大小）"""
    if not _cache and value:
        _cache.append({'phys': value, 'logical': None})


def resolve() -> str:
    """給腳本選座標常數用（第一個判斷）：邏輯版面在 SUPPORTED 內原樣回傳；遊戲沒開 / 不支援的大小回 DEFAULT（維持原本行為）。
    同比例的 1728×995 → '2880x1659'（gui.ps1 負責換算）"""
    cur = logical()
    return cur if cur in SUPPORTED else DEFAULT


def template_layout() -> str | None:
    """樣板該存哪一份（第二個判斷）：樣板（digit / name / pet / title…）依「實體」尺寸渲染；實體大小在 SUPPORTED 內才有樣板，
    其他（含同比例的 1728×995）回 None = 樣板未就緒（P3 之後才會有 `<root>/<phys>/`）"""
    cur = current()
    return cur if cur in SUPPORTED else None


def status() -> dict:
    """三個判斷合在一起，給 info 顯示 / 上層決定降級用：
    phys 實體大小；coords 座標常數用哪套；scaled = 換算層在縮放（同比例但非 2880×1659）；templates = 樣板是否就緒"""
    cur = current()
    return {'phys': cur, 'coords': resolve(), 'scaled': bool(cur and cur != DEFAULT and logical() == DEFAULT),
            'templates': template_layout() is not None}


if __name__ == '__main__':
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    cur = current()
    st = status()
    print(f'客戶區 {cur}；座標常數 {st["coords"]}；樣板 {"就緒" if st["templates"] else "未就緒"}'
          + ('（換算層縮放中：同比例視窗，座標可用但腳本守衛仍擋，P4 前不放行）' if st['scaled'] else ('' if cur in SUPPORTED else '（不支援的大小，沿用預設；請最大化遊戲視窗或 gui.sh fit）')))
