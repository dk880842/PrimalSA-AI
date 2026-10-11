#!/usr/bin/env python3
"""重做 fixtures/item_icons.json（道具圖示樣板，bag.icon_match_slots 用）。需要遊戲開著、該道具在公共倉庫第 1 格。
流程：開背包 → 倉庫公共頁取第 1 格當 depot 樣板 → 取出 → 背包頁找格取 bag 樣板 → 存回。用法：uv run --no-project python tools/gui/make_item_icons.py 龍王的守護"""
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
    icons[name] = {}
    bag.ICON_FILE.write_text(json.dumps(icons, ensure_ascii=False), encoding='utf-8')     # 先清掉舊樣板，下面找格走名稱 / 彈窗核對
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
        bag.ICON_FILE.write_text(json.dumps(icons, ensure_ascii=False), encoding='utf-8')
        print('depot 格', i, 'bag 格', j, '存回 rc', bag.depot_store('DKBO', name))
    return 0 if 'bag' in icons[name] else 4


if __name__ == '__main__':
    sys.exit(main(sys.argv[1]))
