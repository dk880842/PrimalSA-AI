#!/usr/bin/env python3
"""petimg_match 離線測試（不碰遊戲）。用法：uv run --no-project python tools/gui/test_petimg_match.py
需要 tools/.cache/pet-images/（tools/extract/pet_images.py 匯出）；沒匯出就整個略過（回 0）。
截圖回歸（bn_0.png / catch-m0/dep1.png / f0.png）檔案不在就略過該項。"""
import sys
import time
import types
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import petimg_match as M  # noqa: E402
import pngread  # noqa: E402

CACHE = HERE.parents[1] / 'tools' / '.cache'
fails = 0
BG = (110, 72, 44)          # 寵物格底色（深棕）


def check(name, cond, extra=''):
    global fails
    print(('PASS' if cond else 'FAIL'), name, extra)
    if not cond:
        fails += 1


def fake_cell(iid, kind, cx, cy, shift=(0, 0), tag=True, recolor=None):
    """依樣板畫一格假縮圖：棕底 + 頭像（可位移）+ 左上紅色狀態標（slot）→ {(x,y): rgb}"""
    k = M.KINDS[kind]
    x0, y0, x1, y1 = k['clip']
    cells = {(cx + dx, cy + dy): BG for dy in range(y0, y1 + 1) for dx in range(x0, x1 + 1)}
    ox, oy = cx + k['center'][0] + shift[0], cy + k['center'][1] + shift[1]
    for dx, dy, r, g, b in M.template(iid, kind):
        p = (ox + dx, oy + dy)
        if p in cells:
            cells[p] = recolor((r, g, b)) if recolor else (r, g, b)
    if tag and kind == 'slot':
        for dy in range(y0, y0 + 30):
            for dx in range(x0, x0 + 30 - (dy - y0)):
                cells[(cx + dx, cy + dy)] = (200, 30, 30)
    return cells


def main() -> int:
    if not (M.IMG_DIR / 'index.tsv').exists():
        print('SKIP 沒有 tools/.cache/pet-images（先跑 tools/extract/pet_images.py）')
        return 0
    # ---- 索引 / 同物種合併 ----
    check('火雞多筆 Monster 合併成 1 個 imageId', M.ids_for(['火雞']) == ['100367'], M.ids_for(['火雞']))
    check('鯊魚系 4 物種 4 個 imageId', len(M.ids_for(['克邦凱斯', '加克拉', '加格', '邦恩吉'])) == 4)
    check('2D 版視為同物種', M.species_key('2D貝魯卡') == M.species_key('貝魯卡') == '貝魯卡')
    try:
        M.ids_for(['不存在的寵物'])
        check('找不到的名字丟 KeyError', False)
    except KeyError:
        check('找不到的名字丟 KeyError', True)

    # ---- 合成格：對的物種、位移容忍、不在候選 → None ----
    sharks = ['克邦凱斯', '加克拉', '加格', '邦恩吉']
    turkeys = ['火雞', '克克洛斯', '霍爾克', '奇寶']
    cx, cy = M.SLOT_X, M.SLOT_Y[1]
    for name in sharks + turkeys:
        iid = M.ids_for([name])[0]
        r = M.match(fake_cell(iid, 'slot', cx, cy, shift=(3, -2)), 'slot', cx, cy, sharks + turkeys)
        check(f'合成寵物格 {name}', r['species'] == name, f"{r['score']} / {r['second_species']} {r['second']}")
    iid = M.ids_for(['朵拉比斯'])[0]
    r = M.match(fake_cell(iid, 'slot', cx, cy), 'slot', cx, cy, sharks)
    check('候選集裡沒有 → None（不猜）', r['species'] is None and not r['ok'], r['ranked'][:2])
    ccx, ccy = M.CARD_X[2], M.CARD_Y[1]
    iid = M.ids_for(['加克拉'])[0]
    r = M.match(fake_cell(iid, 'card', ccx, ccy, shift=(-4, 2)), 'card', ccx, ccy, sharks)
    check('合成倉庫卡 加克拉', r['species'] == '加克拉', r['ranked'][:2])
    # 整張變色（例如被選取光暈 / 半透明視窗蓋住）→ 分數掉到門檻下 → None
    r = M.match(fake_cell(iid, 'card', ccx, ccy, recolor=lambda c: (255 - c[0], 255 - c[1], 255 - c[2])), 'card', ccx, ccy, sharks)
    check('畫面跟頭像對不起來 → None', r['species'] is None, r['score'])

    # ---- 第二關投票 ----
    a, b = M.ids_for(['克克洛斯'])[0], M.ids_for(['奇寶'])[0]
    cells = fake_cell(b, 'slot', cx, cy, tag=False)
    pa = M._best_pos(M.template(a, 'slot'), cells, 'slot', cx, cy)
    pb = M._best_pos(M.template(b, 'slot'), cells, 'slot', cx, cy)
    t = M._tiebreak(cells, 'slot', (a, pa), (b, pb))
    check('第二關投票選中奇寶（紅冠）', t['winner'] == b, t['votes'])
    t = M._tiebreak({}, 'slot', (a, pa), (b, pb))
    check('第二關沒有票 → None', t['winner'] is None)

    # ---- read_cell 經 uikit.px（假的）----
    fake = types.SimpleNamespace(px=lambda pts: [cells.get(p, BG) for p in pts])
    real = sys.modules.get('uikit')
    sys.modules['uikit'] = fake
    try:
        got = M.read_cell('slot', cx, cy)
        r = M.match(got, 'slot', cx, cy, turkeys)
        check('read_cell → match', r['species'] == '奇寶', r['ranked'][:2])
        fake.px = lambda pts: None
        check('px 讀不到 → read_cell None', M.read_cell('slot', cx, cy) is None)
    finally:
        if real is not None:
            sys.modules['uikit'] = real
        else:
            del sys.modules['uikit']

    # ---- 截圖回歸（實際遊戲截圖；檔案不在就略過）----
    names16 = sharks + turkeys + ['朵拉比斯', '布拉奇多斯', '摩娜西普', '迪基格斯', '左迪洛斯', '巴朵蘭恩', '瑪斯貝卡', '金布伊']
    cases = {
        'bn_0.png': {('slot', 1): '瑪斯貝卡', ('slot', 2): '奇寶', ('slot', 3): '克克洛斯', ('slot', 4): '霍爾克', ('slot', 5): '火雞',
                     ('card', 1): '加格', ('card', 2): '克邦凱斯', ('card', 3): '邦恩吉', ('card', 4): '迪基格斯', ('card', 5): '加克拉'},
        'catch-m0/dep1.png': {('slot', 1): '瑪斯貝卡', ('slot', 3): '左迪洛斯', ('slot', 4): '摩娜西普', ('slot', 5): '巴朵蘭恩',
                              ('card', 1): '迪基格斯'},
        'f0.png': {('slot', 1): '瑪斯貝卡', ('slot', 2): None, ('slot', 3): None},      # 貝魯卡 / 魯尼帖斯 不在候選 → None
    }
    for fn, want in cases.items():
        p = CACHE / fn
        if not p.exists():
            print('SKIP 截圖不在', fn)
            continue
        t0 = time.time()
        res = {(r['kind'], r['index']): r for r in M.scan_shot(p, names16)}
        ms = (time.time() - t0) * 1000 / max(1, len(res))
        wrong = [(k, w, res[k]['species']) for k, w in want.items() if k in res and res[k]['species'] not in (w, None)]
        miss = [(k, w, res[k]['species'] if k in res else '空格?') for k, w in want.items() if k not in res or res[k]['species'] != w]
        check(f'截圖 {fn} 沒有認錯', not wrong, wrong)
        check(f'截圖 {fn} 全部認對', not miss, f'{miss}  每格 {ms:.0f} ms')
    # --family：候選裡沒有騎寵瑪斯貝卡 → 同為劍齒虎的 貝魯伊卡 分數 0.555 < 寵物格門檻 0.70 → None（舊門檻 0.55 會認錯）
    p = CACHE / 'm7.png'
    if p.exists():
        res = {(r['kind'], r['index']): r for r in M.scan_shot(p, M.family(turkeys))}
        check('m7.png --family 不在候選的騎寵 → None', res[('slot', 1)]['species'] is None, res[('slot', 1)]['ranked'][:2])
        want = {1: '奇寶', 2: '火雞', 6: '克克洛斯', 10: '奇寶'}
        got = {i: res[('card', i)]['species'] for i in want}
        check('m7.png --family 倉庫卡火雞系', got == want, got)
    else:
        print('SKIP 截圖不在 m7.png')
    print('全部通過' if not fails else f'{fails} 項失敗')
    return 1 if fails else 0


if __name__ == '__main__':
    sys.exit(main())
