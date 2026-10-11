#!/usr/bin/env python3
"""重做 fixtures/item_icons.json（道具圖示樣板，bag.icon_match_slots 用）。需要遊戲開著、該道具在公共倉庫第 1 格。
流程：開背包 → 倉庫公共頁取第 1 格當 depot 樣板 → 取出 → 背包頁找格取 bag 樣板 → 存回。注意：筆電樣板取自被選取框圍住的格子，未選取格只吻合約 0.56（bag 已放寬到 0.45 擋著）。
樣板檔依版面（bag.icon_file()）：2880×1659 = fixtures/item_icons.json，外接 1728×995 = tools/.cache/item-icons/1728x995.json。

用法：
  uv run --no-project python tools/gui/make_item_icons.py 龍王的守護                          # 全自動：取出 → 取樣 → 存回（用 bag.depot_take / depot_store）
  uv run --no-project python tools/gui/make_item_icons.py 龍王的守護 --grab bag|depot --slot N [--sel]   # 唯讀：背包 / 倉庫頁已開著時取第 N 格（1 起算），不點任何東西
--grab：未選取 → 'bag' / 'depot'（icon_match_slots 用的鍵）；--sel（點過、黃框圍住）→ 'bag_sel' / 'depot_sel'（參考用，bag.py 目前不讀）；
兩種都有時印出互相吻合比例。2026-10-11 外接 1728×995 實機：龍王的守護 背包 / 倉庫 選取 vs 未選取 = 1.0（黃框在格邊 ±48，不在取樣 ±16 內），
嚴格門檻命中背包第 1 格 / 倉庫第 1 格、其他道具不中。外接時 bag.depot_take / depot_store 的彈窗按鈕列 OCR 讀不到（退出碼 96，見計畫檔），
當次取出 / 存回是手動點（先截圖核對彈窗名稱），樣板用 --grab 取。"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import bag  # noqa: E402
import uikit  # noqa: E402


def grab(cx, cy):
    pts = [(cx + dx, cy + dy) for dy in range(-16, 17, 4) for dx in range(-16, 17, 4)]
    return [[x - cx, y - cy, *c] for (x, y), c in zip(pts, uikit.px(pts))]


def main(name):
    import winenv
    winenv.enable_server()
    import heal
    heal.set_encounter(False)                       # 戰鬥中存取倉庫會被擋
    heal.gui('seq', f'waitpix 20000 {heal.SIG_NO_BATTLE} 40')
    icons = bag.load_icons()
    out = bag.icon_file()                           # 依版面：2880×1659 = fixtures/item_icons.json，外接 = tools/.cache/item-icons/<實體尺寸>.json
    out.parent.mkdir(parents=True, exist_ok=True)
    icons[name] = {}
    out.write_text(json.dumps(icons, ensure_ascii=False), encoding='utf-8')     # 先清掉舊樣板，下面找格走名稱 / 彈窗核對
    with bag.Session() as s:
        if s.rc or bag.select_role('DKBO') or bag.open_depot('public'):
            return 1
        i = bag.find_item(name, depot=True)
        if i is None:
            return 2
        icons[name]['depot'] = grab(*bag.depot_xy(i))
        if bag.depot_take('DKBO', name):
            return 3
        j = bag.find_item(name)
        if j is not None:
            icons[name]['bag'] = grab(*bag.slot_xy(j))
        out.write_text(json.dumps(icons, ensure_ascii=False), encoding='utf-8')
        print('depot 格', i, 'bag 格', j, '存回 rc', bag.depot_store('DKBO', name))
    return 0 if 'bag' in icons[name] else 4


def grab_cmd(name: str, kind: str, slot: int, sel: bool) -> int:
    """唯讀取樣：背包 / 倉庫頁要已開著（不開面板、不點格子）；寫進目前版面的樣板檔"""
    import winenv
    winenv.enable_server()
    panel = bag.DEPOT if kind == 'depot' else bag.BAG
    if not uikit.is_open(panel):
        print(f'{kind} 頁沒開著（不點任何東西）', file=sys.stderr)
        return 1
    xy = bag.depot_xy(slot - 1) if kind == 'depot' else bag.slot_xy(slot - 1)
    icons = bag.load_icons()
    d = icons.setdefault(name, {})
    key = kind + ('_sel' if sel else '')
    d[key] = grab(*xy)
    out = bag.icon_file()
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(icons, ensure_ascii=False), encoding='utf-8')
    print(f'寫入 {out} 「{name}」{key}（第 {slot} 格 {xy}）')
    if kind in d and kind + '_sel' in d:
        print(f'{kind} 選取 vs 未選取 吻合比例 {ratio(d[kind], d[kind + "_sel"]):.2f}')
    return 0


def ratio(a, b) -> float:
    """兩份取樣（同點序）在 bag.ICON_TOL 內的點比例"""
    return sum(all(abs(x - y) <= bag.ICON_TOL for x, y in zip(p[2:], q[2:])) for p, q in zip(a, b)) / max(1, len(a))


if __name__ == '__main__':
    import argparse
    ap = argparse.ArgumentParser(description='道具圖示樣板')
    ap.add_argument('name')
    ap.add_argument('--grab', choices=['bag', 'depot'], help='唯讀：從已開著的背包 / 倉庫頁取一格')
    ap.add_argument('--slot', type=int, default=1, help='--grab 的格號（1 起算）')
    ap.add_argument('--sel', action='store_true', help='--grab 時該格是選取狀態（黃框）→ 存 *_sel')
    a = ap.parse_args()
    sys.exit(grab_cmd(a.name, a.grab, a.slot, a.sel) if a.grab else main(a.name))
