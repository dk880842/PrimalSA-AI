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

import shotfix  # noqa: E402
CACHE = shotfix.SHOTS          # 固定截圖 tools/gui/fixtures/petimg/（tools/.cache 的暫存截圖會被覆蓋，2026-10-14 s3.png）
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


OCC_X0, OCC_Y0 = 765, 225      # fixtures/petimg/occ_<角色>.png = thumb-<角色>-personal.png 裁 (765,225)～(1295,330)：倉庫第 1 排 5 張卡


def occ_getter(role):
    """2026-10-14 play agent 被浮字橫幅蓋住的倉庫分頁（DKBO2 卡 1、2 蓋上半；DKBO3 卡 1、2 幾乎整張）→ get(x, y)（截圖座標）"""
    p = HERE / 'fixtures' / 'petimg' / f'occ_{role}.png'
    if not p.exists():
        return None
    w, h, bpp, rows = pngread.decode(p.read_bytes())

    def get(x, y):
        if 0 <= x - OCC_X0 < w and 0 <= y - OCC_Y0 < h:
            return tuple(rows[y - OCC_Y0][(x - OCC_X0) * bpp:(x - OCC_X0) * bpp + 3])
        return None
    return get


def darkened(get, cx, cy, bottom, k=0.56):
    """合成浮字橫幅：格心上方到 dy=bottom 的列乘 k（實測橫幅 ≈ 原色 × 0.56）"""
    def g(x, y):
        c = get(x, y)
        if c is not None and y - cy <= bottom and abs(x - cx) <= 62:
            return tuple(int(v * k) for v in c)
        return c
    return g


def test_partial(names16):
    """被蓋住時的區塊比對（imgmatch.covered_rows / keep_rows + judge partial）"""
    import imgmatch
    rows = imgmatch.covered_rows(lambda x, y: (100, 90, 80) if y < 10 else (230, 210, 180), 0, 0,
                                 [(dx, dy) for dx in (-5, 5) for dy in range(-20, 21, 4)], imgmatch.dimmed_beige, 4)
    check('covered_rows：壓暗的取點列 ±pad', min(rows) == -24 and max(rows) == 12, (min(rows), max(rows)))
    g = imgmatch.keep_rows({(0, y): (1, 1, 1) for y in range(-5, 6)}, 0, drop={-5, -4}, y_min=-3, y_max=3)
    check('keep_rows：drop + y_min / y_max', sorted(q[1] for q in g) == list(range(-3, 4)) and isinstance(g, imgmatch.Grid))
    g2 = occ_getter('DKBO2')
    g3 = occ_getter('DKBO3')
    if g2 is None or g3 is None:
        print('SKIP 沒有 fixtures/petimg/occ_DKBO2.png / occ_DKBO3.png')
        return
    want2 = {1: '布拉奇多斯', 2: '摩娜西普', 3: '摩娜西普', 4: '布拉奇多斯', 5: '迪基格斯'}
    for i, sp in want2.items():
        _, cx, cy = M.cells_of('card')[i - 1]
        r = M.judge(g2, 'card', cx, cy, names16)
        if i <= 2:
            check(f'被蓋住 DKBO2 卡 {i}：區塊比對認出 {sp}', r['occluded'] and r['partial'] and r['species'] == sp and r['stage'] == 'partial',
                  f"{r['best_species']} {r['score']} / {r['second']} vis {r.get('vis')}")
            r0 = M.judge(g2, 'card', cx, cy, names16, partial=False)
            check(f'被蓋住 DKBO2 卡 {i}：partial=False → 照舊不認', r0['occluded'] and r0['species'] is None and r0['stage'] == 'occluded')
            absent = [n for n in names16 if n not in M.family_of(sp)]
            ra = M.judge(g2, 'card', cx, cy, absent, family_stage=False)
            check(f'被蓋住 DKBO2 卡 {i}：真物種不在候選 → 不冒充', ra['species'] is None, f"{ra['best_species']} {ra['score']}")
        else:
            check(f'沒蓋住 DKBO2 卡 {i}：全圖（不是區塊比對）', not r['occluded'] and not r['partial'] and r['species'] == sp, r['score'])
    for i in (1, 2):
        _, cx, cy = M.cells_of('card')[i - 1]
        r = M.judge(g3, 'card', cx, cy, names16)
        check(f'幾乎整張被蓋住 DKBO3 卡 {i}：沒蓋住的列不夠 → 不認', r['occluded'] and r['species'] is None and r.get('vis', 1) < M.PARTIAL_MIN_VIS,
              f"vis {r.get('vis')}")
    # 合成：沒蓋住的格把上方蓋到 dy=-10 → 遮擋偵測到、區塊比對認出（全圖照舊不認）
    _, cx, cy = M.cells_of('card')[2]
    gd = darkened(g2, cx, cy, -10)
    r = M.judge(gd, 'card', cx, cy, names16)
    check('合成橫幅蓋上方 → 區塊比對認出摩娜西普', r['occluded'] and r['species'] == '摩娜西普', f"{r['score']} / {r['second']} vis {r.get('vis')}")
    r = M.judge(darkened(g2, cx, cy, 30), 'card', cx, cy, names16)
    check('合成橫幅蓋到 dy=30 → 不認', r['occluded'] and r['species'] is None, r.get('vis'))


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
    # ---- 任務候選相對比較 rank_among（inlier + 主色）：2026-10-13 卡坦分配實機截圖（每人 4 隻各一種、任務已交成功）----
    among = {
        's0.png': (turkeys, {('slot', 2): '火雞', ('slot', 3): '克克洛斯', ('slot', 4): '霍爾克', ('slot', 5): '奇寶'}),
        's4.png': (turkeys, {('slot', 2): '霍爾克', ('slot', 3): '火雞', ('slot', 4): '克克洛斯', ('slot', 5): '奇寶'}),
        's5.png': (turkeys, {('slot', 2): '奇寶', ('slot', 3): '火雞', ('slot', 4): '克克洛斯', ('slot', 5): '霍爾克'}),
        'dep2.png': (turkeys, {('slot', 2): '奇寶', ('card', 1): '火雞', ('card', 2): '霍爾克', ('card', 4): '克克洛斯',
                               ('card', 3): None, ('card', 5): None, ('card', 6): None}),          # 左迪洛斯 / 巴朵蘭恩 / 摩娜西普 不在候選
        'z.png': (sharks, {('slot', 2): '克邦凱斯', ('slot', 3): '加克拉', ('slot', 4): '邦恩吉', ('slot', 5): '加格'}),
        'dep.png': (sharks, {('slot', 2): '克邦凱斯', ('slot', 4): '邦恩吉', ('card', 1): '加格', ('card', 2): '邦恩吉',
                             ('card', 3): None, ('card', 4): None, ('card', 5): None}),
    }
    for fn, (cand, want) in among.items():
        p = CACHE / fn
        if not p.exists():
            print('SKIP 截圖不在', fn)
            continue
        res = {(r['kind'], r['index']): r for r in M.scan_shot(p, cand, among=True)}
        miss = [(k, w, res[k]['species'] if k in res else '空格?') for k, w in want.items() if k not in res or res[k]['species'] != w]
        check(f'rank_among {fn} 全部認對（不在候選 → None）', not miss, str(miss))
    # 2026-10-14 卡坦：倉庫卡 奇寶（紅冠，目視）/ 克克洛斯 inlier 差 0.02、主色差 0.03 → 舊版 None；第三關 _tiebreak 投票判對
    p = CACHE / 'k1.png'
    if p.exists():
        res = {(r['kind'], r['index']): r for r in M.scan_shot(p, turkeys, among=True)}
        r = res[('card', 2)]
        check('rank_among k1.png 卡 2 奇寶（分差不夠 → 投票）', r['species'] == '奇寶' and r['tiebreak'] and r['tiebreak']['winner'], str(r))
        check('rank_among k1.png 摩娜西普 / 巴朵蘭恩 / 左迪洛斯 卡不在候選 → None',
              all(res[('card', i)]['species'] is None for i in (5, 6, 9)))
    else:
        print('SKIP 截圖不在 k1.png')
    # 合成：換色版只差顏色（同輪廓）→ 主色直方圖分得開
    a = M.ids_for(['加克拉'])[0]
    r = M.rank_among(fake_cell(a, 'slot', cx, cy, shift=(2, -1)), 'slot', cx, cy, sharks)
    check('rank_among 合成 加克拉', r['species'] == '加克拉' and r['hist'] > r['hist_second'], str(r['ranked']))
    r = M.rank_among(fake_cell(a, 'slot', cx, cy), 'slot', cx, cy, ['加克拉'])
    check('rank_among 單一候選也要過門檻', r['species'] == '加克拉')
    r = M.rank_among(fake_cell(M.ids_for(['朵拉比斯'])[0], 'slot', cx, cy), 'slot', cx, cy, sharks)
    check('rank_among 候選裡沒有 → None', r['species'] is None and not r['ok'])
    test_partial(names16)
    print('全部通過' if not fails else f'{fails} 項失敗')
    return 1 if fails else 0


if __name__ == '__main__':
    sys.exit(main())
