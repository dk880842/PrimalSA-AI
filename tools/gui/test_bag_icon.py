#!/usr/bin/env python3
"""bag.py ↔ itemimg_match 接線離線測試（不碰遊戲）：2026-10-14 計畫 notes/plan-item-icon-match.md 階段 3（唯讀）+ 階段 4（find_item 排序）。
用法：uv run --no-project python tools/gui/test_bag_icon.py
需要 tools/.cache/item-images（tools/extract/item_images.py 抽圖）；沒有就整個略過（回 0）。
畫面 = fixtures/itemimg_cells.png 的格子裁片拼回原座標（其他位置當空格棕），uikit.shot_getter 換成它；面板 / 選角色 / OCR / 彈窗全換假的。
驗：find_items 縮圖命中不 OCR、沒命中只 OCR 沒認出的格、icon 模式不 OCR、ocr 模式不截圖；list（read_bag_items）縮圖名 + 同圖多名標 ambiguous；
find_item 只開縮圖命中那格的彈窗；橫幅蓋住 → 重拍、仍蓋住 → 那格走 OCR；名稱帶 [地] 的道具（大地的羈絆）也查得到圖。"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import testenv  # noqa: E402,F401  紀錄檔轉向暫存
import bag  # noqa: E402
import itemimg_match as IM  # noqa: E402
import test_itemimg_match as TI  # noqa: E402
import uikit  # noqa: E402

fails = 0
EMPTY = bag.SLOT_EMPTY


def check(name, cond, extra=''):
    global fails
    print(('PASS' if cond else 'FAIL'), name, extra)
    if not cond:
        fails += 1


def screen(src, kind='bag'):
    """fixtures 裡 src 這張截圖的格子裁片拼回原座標 → get(x, y)（其他位置 = 空格棕）"""
    tiles = [c for c in TI.load_fixtures() if c['src'] == src and c['kind'] == kind]

    def get(x, y):
        for c in tiles:
            v = c['get'](x, y)
            if v is not None:
                return v
        return EMPTY
    return get, {c['slot']: c['expect'] for c in tiles}


class FakeSession:
    rc = 0

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def install(get, texts=None, popups=None):
    """假環境：shot_getter → get；read_slot_name → texts；彈窗名稱 → popups[格]"""
    st = {'shots': 0, 'ocr': [], 'popup': []}

    def shot(tag='img'):
        st['shots'] += 1
        g = st.get('seq')
        return g.pop(0) if g else get
    uikit.shot_getter = shot
    uikit.sleep = lambda s: None
    uikit.mark = lambda *a: None
    bag.Session = FakeSession
    bag.select_role = lambda role, ctx=None: 0
    bag.read_slot_name = lambda i, depot=False: (st['ocr'].append(i), (texts or {}).get(i, ''))[1]
    bag.ensure_names_shown = lambda occ=None: True
    bag.slot_occupancy = lambda: None
    cur = {'i': None}
    bag.open_slot_popup = lambda i, depot=False: (st['popup'].append(i), cur.__setitem__('i', i), True)[2]
    bag.popup_name = lambda want=None: (popups or {}).get(cur['i'], '')
    bag.close_popup = lambda: True
    bag.icon_match_slots = lambda want, depot=False: []
    return st


def main() -> int:
    try:
        IM.index()
    except FileNotFoundError:
        print('SKIP 沒有 tools/.cache/item-images（先跑 tools/extract/item_images.py）')
        return 0
    bag.ITEM_MATCH = 'auto'
    get, truth = screen('b5.png')
    # b5：0 大地的羈絆、1 火的羽毛飾品、2 風的鎖、3 水的戒指、4 一號簽類、5～7 千年龜的殼、8 寵物誘餌、9 / 14 空
    st = install(get)
    r = bag._names_in_bag(['寵物誘餌', '千年龜的殼'])
    check('find：縮圖命中 → 寵物誘餌 8、千年龜的殼 5～7 之一，零 OCR、1 張截圖',
          r['found']['寵物誘餌'] == 8 and r['found']['千年龜的殼'] in (5, 6, 7) and not st['ocr'] and st['shots'] == 1
          and r['by'] == {'寵物誘餌': 'icon', '千年龜的殼': 'icon'}, r)
    check('find：空格數用同一張截圖（15 格 9 有道具 → 6）', r['free'] == 6, r['free'])
    check('find：寵物誘餌與寶石夾同圖 → ambiguous', '寵物誘餌' in r['ambiguous'], r['ambiguous'])
    st = install(get)
    r = bag._names_in_bag(['大地的羈絆', '龍王的守護'])
    check('名稱不帶 [地]（大地的羈絆）也找得到圖 → 0', r['found']['大地的羈絆'] == 0, r['found'])
    check('龍王的守護不在：縮圖每格都認得（工作集）時不 OCR → None', r['found']['龍王的守護'] is None and not st['ocr'], st['ocr'])
    st = install(get)
    r = bag._names_in_bag(['表演證'])
    check('同圖（一號簽 / 表演證 / 郵寄物 共用 24314）→ 命中但標 ambiguous（動作前要彈窗核對）', r['found']['表演證'] == 4 and '表演證' in r['ambiguous'], r)
    st = install(get, texts={4: '一號簽'})
    r = bag._names_in_bag(['拉魯的項鍊'])
    check('道具圖索引查不到的名稱 → 沒被縮圖認成別的要找名稱的格全部 OCR', sorted(st['ocr']) == [i for i in range(9)], st['ocr'])
    bag.ITEM_MATCH = 'icon'
    st = install(get)
    r = bag._names_in_bag(['龍王的守護'])
    check('icon 模式：不 OCR', not st['ocr'] and r['found']['龍王的守護'] is None)
    bag.ITEM_MATCH = 'ocr'
    st = install(get, texts={8: '寵物誘餌'})
    bag.read_bag_names_ocr = lambda: ([i < 9 for i in range(15)], {i: bag.read_slot_name(i) for i in range(9)})
    r = bag._names_in_bag(['寵物誘餌'])
    check('ocr 模式：不截圖、照舊 OCR', st['shots'] == 0 and r['found']['寵物誘餌'] == 8 and r['by'] == {'寵物誘餌': 'ocr'}, (st, r))
    bag.ITEM_MATCH = 'auto'

    # ---- list：read_bag_items ----
    st = install(get, texts={4: '一號簽'})
    d = bag.read_bag_items()
    check('list：縮圖認得的格給名稱（by icon）、千年龜的殼 5～7（同圖未知的殼 → 標同圖）', all(d['slots'].get(i) == '千年龜的殼(同圖)' and d['by'][i] == 'icon' for i in (5, 6, 7)), d['slots'])
    check('list：寵物誘餌格同圖多名 → icons.ambiguous', d['icons'][8]['ambiguous'] is True and d['slots'][8] == '寵物誘餌(同圖)', d['icons'].get(8))
    check('list：全部格縮圖認得 → 零 OCR、free 6', not st['ocr'] and d['free'] == 6 and not d['unread'], st['ocr'])
    check('list：首飾（大地的羈絆 [地]）用縮圖名', d['slots'].get(0, '').startswith('大地的羈絆'), d['slots'].get(0))
    gb, _ = screen('bag0.png')
    st = install(gb, texts={1: '火的羽毛飾品[火]'})
    d = bag.read_bag_items()
    check('list：橫幅蓋住的格 OCR 補（by ocr）、讀不到的列 unread', d['by'].get(1) == 'ocr' and d['slots'][1] == '火的羽毛飾品[火]' and 2 in d['unread']
          and 1 in st['ocr'] and 2 in st['ocr'], (d['by'], d['unread'], st['ocr']))

    # ---- find_item：只開縮圖命中那格的彈窗 ----
    st = install(get, popups={8: '寵物誘餌'})
    i = bag.find_item('寵物誘餌')
    check('find_item：縮圖命中第 9 格 → 只開那 1 格彈窗核對', i == 8 and st['popup'] == [8], st['popup'])
    st = install(get, popups={8: '寶石夾'})
    i = bag.find_item('寵物誘餌', popup_fallback=False)
    check('find_item：彈窗名稱不符（同圖的寶石夾）→ 不採用', i is None and 8 in st['popup'], st['popup'])
    st = install(get, popups={5: '千年龜的殼', 6: '千年龜的殼', 7: '千年龜的殼'})
    check('item_slots：千年龜的殼 3 格（縮圖）', bag.item_slots('千年龜的殼') == [5, 6, 7])

    # ---- 倉庫格 ----
    gd, _ = screen('dep0.png', 'depot')
    st = install(gd, popups={0: '龍王的守護'})
    i = bag.find_item('龍王的守護', depot=True)
    check('find_item 倉庫：龍王的守護在第 1 格、只開 1 格', i == 0 and st['popup'] == [0], st['popup'])

    # ---- 橫幅蓋住：重拍；仍蓋住 → 那格 OCR ----
    gb, tb = screen('bag0.png')
    st = install(gb, texts={0: '大地的羈絆[地]'})
    r = bag._names_in_bag(['大地的羈絆'])
    check('橫幅一直蓋住第 1 格 → 重拍 ICON_OCC_RETRIES 次、那格改 OCR 找到', st['shots'] == bag.ICON_OCC_RETRIES + 1 and r['found']['大地的羈絆'] == 0
          and r['by'].get('大地的羈絆') == 'ocr', (st['shots'], r))
    st = install(gb)
    st['seq'] = [gb, get]                                  # 第 2 張橫幅消失（換成 b5 同位置的畫面）
    r = bag._names_in_bag(['大地的羈絆'])
    check('橫幅第 2 張消失 → 縮圖認出、零 OCR', st['shots'] == 2 and r['found']['大地的羈絆'] == 0 and not st['ocr'], (st['shots'], r))

    print('全部通過' if not fails else f'{fails} 項失敗')
    return 1 if fails else 0


if __name__ == '__main__':
    sys.exit(main())
