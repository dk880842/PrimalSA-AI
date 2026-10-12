#!/usr/bin/env python3
"""信箱領取「丟失的物品」系統郵件（背包滿時任務道具會進信箱）。只用標準函式庫。

用法（專案根目錄；WSL / Windows 原生指令相同）：
  uv run --no-project python tools/gui/mail.py status                 # 唯讀：開信件面板 → 系統郵件列數 / 哪幾列是「丟失的物品」
  uv run --no-project python tools/gui/mail.py claim [--dry-run] [--max N]   # 逐封點右側藍「領取」（只領文字含「丟失」的郵件）

實機事實（2026-10-13）：
- 信箱是帳號共用的：用任何一個當前角色開，每封郵件領下去會發給「該郵件所屬角色」（畫面頂橫幅「角色【DKBO2】獲得道具【薩頓家的頭盔】x1」），
  所以 5 人的信一次領完，不用切角色（面板也沒有切角色的頭像列）。
- 流程：主畫面信封 178,583 → 「好友消息」分頁（預設）→ 左側「系統郵件」385,300（紅數字 = 封數）→ 右側每列 y=277 + 109*i（i=0..3），
  藍「領取」鈕 1160,y；領完該列消失、下面的列上移 → 每次都重新讀圖、只點第 0 列（或第一個合格列）。每頁 4 列、1/N 頁；下一頁箭頭 1033,718。
- 關閉：ESC。領的道具進當事人背包；背包還滿就不會成功（列不會消失 → 退出碼 114）。

退出碼（共用 0 / 1 / 2 / 8 / 9 / 10 見 uikit；mail 自己 111～115）：
  0   領完（或本來就沒有可領的）
  111 信件面板打不開 / 系統郵件分頁點不開
  112 有郵件但沒有一封文字含「丟失」（不領其他種信，只回報）
  113 --max 達上限仍有可領（只是提醒）
  114 領了郵件沒消失（背包滿 / 點擊沒吃到）→ 停手
  115 面板中途消失 / 讀圖失敗
"""
import argparse
import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import uikit  # noqa: E402

OPEN_XY = (178, 583)
SYS_TAB_XY = (385, 300)
CLAIM_X = 1160
ROW_Y = [277, 386, 496, 605]
TEXT_BOX = (720, 255, 270, 70)     # 每列文字（要加 dy）
NEXT_XY = (1033, 718)
# 開啟特徵：✕ 紅圓、好友消息分頁（橘）、黑名單鈕（米）、左側列表底（棕）；不含右側標題條（沒選系統郵件前是空白米色）
SIG = [(1304, 95, 197, 73, 49, 24), (275, 200, 253, 183, 72, 24), (1100, 110, 245, 225, 195, 20), (300, 550, 123, 93, 66, 20)]
BLUE = (66, 110, 171)              # 領取鈕本體取樣 (1100, y+13)
MAIL = uikit.Panel('MAIL', OPEN_XY, SIG, (1304, 95),
                   forbidden={'blacklist': (1010, 80, 240, 60), 'chat_set': (740, 80, 230, 60)})
LOST_KEYS = ('丟失', '丢失', '領取')


def row_has_claim(cols_row) -> bool:
    import screen_sigs
    return bool(cols_row) and screen_sigs.close(cols_row, BLUE, 40)


def read_rows() -> list:
    """每列的藍鈕有無（4 個 bool）；讀不到 → None"""
    cols = uikit.px([(1100, y + 13) for y in ROW_Y])
    return None if cols is None else [row_has_claim(c) for c in cols]


def row_text(i: int) -> str:
    x, y, w, h = TEXT_BOX
    return ''.join(uikit.ocr((x, y + ROW_Y[i] - ROW_Y[0], w, h)))


def lost_text(t: str) -> bool:
    return '丟失' in t or '丢失' in t or '遺失' in t


def open_system() -> int:
    """開面板 + 點系統郵件；成功 0"""
    if not uikit.open_panel(MAIL):
        return 111
    uikit.safe_click(*SYS_TAB_XY, MAIL, note='mail 系統郵件')
    time.sleep(0.6)
    rows = read_rows()
    return 111 if rows is None else 0


def run(cmd: str, dry: bool = False, max_n: int = 30) -> int:
    rc = uikit.preflight('mail')
    if rc:
        return rc
    rc = open_system()
    if rc:
        uikit.close_panel(MAIL)
        return rc
    claimed, skipped_nolost = 0, 0
    result = 0
    while True:
        rows = read_rows()
        if rows is None or not uikit.is_open(MAIL):
            result = 115
            break
        idx = [i for i, ok in enumerate(rows) if ok]
        pick = None
        for i in idx:
            t = row_text(i)
            print(f'mail：第 {i} 列文字 {t!r}')
            if lost_text(t):
                pick = i
                break
        if pick is None:
            if idx:
                skipped_nolost = len(idx)
                result = 112
            break
        if cmd == 'status' or dry:
            print(f'mail：可領 第 {pick} 列（{"--dry-run" if dry else "status"} 不點）')
            break
        if claimed >= max_n:
            result = 113
            break
        before = rows
        if not uikit.safe_click(CLAIM_X, ROW_Y[pick] + 13, MAIL, note=f'mail 領取第 {pick} 列', wait_ms=700):
            result = 115
            break
        time.sleep(0.5)
        after = read_rows()
        if after == before:                 # 列沒消失：再等一下（移除有延遲）
            time.sleep(0.8)
            after = read_rows()
        if after is None:
            result = 115
            break
        if after == before and sum(after) == 4:     # 第 1 頁滿 4 列領完會補上第 2 頁的列 → 狀態相同不代表失敗，用 OCR 文字不同判斷太貴；
            pass                                     # 4 列滿的情況用封數紅字不可讀，只能多等一次並以列文字變化輔助
        elif after == before:
            result = 114
            break
        claimed += 1
        print(f'mail：已領 {claimed} 封')
    uikit.close_panel(MAIL)
    print(json.dumps({'claimed': claimed, 'skipped_not_lost': skipped_nolost, 'rc': result}, ensure_ascii=False))
    return result


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description='信箱領取丟失的物品')
    ap.add_argument('cmd', choices=['status', 'claim'])
    ap.add_argument('--dry-run', action='store_true')
    ap.add_argument('--max', type=int, default=30)
    a = ap.parse_args(argv)
    return run(a.cmd, dry=a.dry_run, max_n=a.max)


if __name__ == '__main__':
    sys.exit(main())
