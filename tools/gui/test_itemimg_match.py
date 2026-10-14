#!/usr/bin/env python3
"""itemimg_match / imgmatch 離線測試（不碰遊戲）。用法：
  uv run --no-project python tools/gui/test_itemimg_match.py                  # 跑測試
  uv run --no-project python tools/gui/test_itemimg_match.py --make-fixtures  # 從 tools/.cache 截圖重做 fixtures（維護用）
  uv run --no-project python tools/gui/test_itemimg_match.py --make-noname-fixtures  # 只重做名字關著的實樣 fixtures
需要 tools/.cache/item-images/（tools/extract/item_images.py 匯出，不進 git）；沒匯出就整個略過（回 0）。
回歸樣本不依賴 tools/.cache 的截圖：每格裁成 85×85 小圖拼在 fixtures/itemimg_cells.png，格資料在 fixtures/itemimg_cells.json。

樣本（2026-10-14，notes/plan-item-icon-match.md §2.4）：
  計畫 39 格（b5 / bag2 / b6 / d_pers450 / dep0 / d_pub450，名字從截圖讀得到）+ bag-names-off 4 格（名字關著，推定）
  + dep0 右側背包 3 格（千年龜的殼）+ 空格 6 格 + bag0 浮動「獲得 EXP」橫幅 5 格（格 0～2 被蓋住）。
「顯示道具名」關著的實樣（2026-10-14，tools/.cache/itemident/*-noname.png）另存 fixtures/itemimg_noname.png / .json（NONAME，裁 ±50 含格間米色縫）：
  倉庫空格 / 有道具的格被 EXP 橫幅蓋住（要判 covered、不比對）、旁邊沒被蓋的格（不能誤判）、空心細線的風的鎖（舊 25 點探針漏判）。
"""
import random
import struct
import sys
import tempfile
import time
import zlib
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import imgmatch  # noqa: E402
import itemimg_match as M  # noqa: E402

FIX_PNG = HERE / 'fixtures' / 'itemimg_cells.png'
FIX_JSON = HERE / 'fixtures' / 'itemimg_cells.json'
CACHE = HERE.parents[1] / 'tools' / '.cache'
PAD0, PAD1 = -41, 43          # 裁切範圍（相對格心）：涵蓋 CLIP、SLOT_PROBE、遮擋偵測 ring
TILE = PAD1 - PAD0 + 1
COLS = 8

# 期望 imageId（None = 空格，'?' = 被橫幅蓋住、看不出來）
TRUTH = {
    'b5.png': ('bag', {0: '22026', 1: '22011', 2: '22016', 3: '22124', 4: '24314', 5: '23907', 6: '23907', 7: '23907', 8: '24049',
                       9: None, 14: None}),
    'bag2.png': ('bag', {0: '22026', 1: '22011', 2: '22016', 3: '22124', 4: '24314', 5: '24049'}),
    'b6.png': ('bag', {5: '50055', 0: None}),
    'd_pers450.png': ('depot', {0: '50055', 1: '24053', 2: None}),
    'dep0.png': ('depot', {0: '24054', 1: '22356', 3: '24154', 10: '50220', 14: '24236', 2: None}),
    'd_pub450.png': ('depot', {0: '23907', 1: '22356', 2: '23907', 3: '24154', 4: '23907', 5: '23907', 6: '23907', 7: '23907',
                               8: '23907', 9: '23907', 10: '50220', 11: '23907', 12: '24054', 13: '23907', 14: '24236', 15: '24049',
                               19: None}),
    'bag-names-off.png': ('bag', {0: '24169', 1: '22013', 2: '22050', 3: '22082'}),
}
EXTRA = {'dep0.png': ('bag', {4: '23907', 5: '23907', 6: '23907'})}          # 倉庫畫面右側的背包格
BANNER = {'bag0.png': ('bag', {0: '?', 1: '22026', 2: '22011', 3: '22016', 4: '22124'})}
NAMES_OFF = 'bag-names-off.png'
# 名字關著的實樣：{檔名: [(kind, 格, 期望狀態 True 有 / False 空 / None 被蓋住, 期望名稱 或 None)]}
NONAME_DIR = 'itemident'
NONAME = {
    'depot-personal-DKBO4-noname.png': [('depot', 3, None, None), ('depot', 4, None, None), ('depot', 2, True, None),
                                        ('depot', 1, True, '英雄的祝福'), ('depot', 5, False, None), ('depot', 8, False, None)],
    'depot-public-DKBO2-noname.png': [('depot', 3, None, None), ('depot', 4, None, None), ('depot', 2, True, '龍王的守護'),
                                      ('depot', 0, True, '2倍智慧果'), ('depot', 10, True, '人龍隨機蛋')],
    'depot-personal-DKBO3-noname.png': [('depot', 3, None, None), ('depot', 4, None, None)],
    'depot-public-DKBO-noname.png': [('depot', 3, True, '安撫之素'), ('depot', 4, False, None), ('depot', 1, True, '離線水晶')],
    'bag-DKBO-noname.png': [('bag', 6, True, '風的鎖'), ('bag', 5, False, None), ('bag', 1, None, None), ('bag', 7, True, '水的戒指')],
    'bag-DKBO2-noname.png': [('bag', 5, True, '風的鎖'), ('bag', 9, False, None)],
}
NONAME_PNG = HERE / 'fixtures' / 'itemimg_noname.png'
NONAME_JSON = HERE / 'fixtures' / 'itemimg_noname.json'
NPAD0, NPAD1 = -50, 50        # 含倉庫格左右的米色縫（−47 / +50）
# 計畫離線實驗的閉集（同系首飾 / 戒指 / 手環換色版、石頭類）
POOL_IDS = ['22084', '22124', '22016', '22026', '22011', '22013', '22050', '22082', '24053', '24054', '22356', '24169', '23907',
            '24049', '50055', '50220', '24154', '24236', '24314', '24055', '24052', '22014', '22015', '22051', '22052', '22083',
            '22125', '22123', '24237', '24238']

fails = 0


def check(name, cond, extra=''):
    global fails
    print(('PASS' if cond else 'FAIL'), name, extra)
    if not cond:
        fails += 1


# ---- fixtures ----
def _png(w, h, rows) -> bytes:
    raw = b''.join(b'\x00' + bytes(r) for r in rows)
    def chunk(t, d):
        return struct.pack('>I', len(d)) + t + d + struct.pack('>I', zlib.crc32(t + d) & 0xffffffff)
    return (b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', w, h, 8, 2, 0, 0, 0))
            + chunk(b'IDAT', zlib.compress(raw, 9)) + chunk(b'IEND', b''))


def make_fixtures() -> int:
    import json
    cells, tiles = [], []
    for group, table in (('plan', TRUTH), ('extra', EXTRA), ('banner', BANNER)):
        for f, (kind, d) in table.items():
            src = CACHE / f
            if not src.exists():
                print('缺截圖', src)
                return 1
            w, h, bpp, rows = imgmatch.decode(src)
            for slot, iid in d.items():
                cx, cy = M._xy(kind, slot)
                tile = [bytes(rows[cy + dy][(cx + PAD0) * bpp:(cx + PAD1 + 1) * bpp]) for dy in range(PAD0, PAD1 + 1)]
                if bpp == 4:
                    tile = [bytes(b for i, b in enumerate(r) if i % 4 != 3) for r in tile]
                tiles.append(tile)
                cells.append({'src': f, 'kind': kind, 'slot': slot, 'cx': cx, 'cy': cy, 'expect': iid,
                              'group': 'names_off' if f == NAMES_OFF and group == 'plan' else group})
    n_rows = (len(tiles) + COLS - 1) // COLS
    W, H = COLS * TILE, n_rows * TILE
    canvas = [bytearray(W * 3) for _ in range(H)]
    for k, tile in enumerate(tiles):
        ox, oy = (k % COLS) * TILE, (k // COLS) * TILE
        for y, r in enumerate(tile):
            canvas[oy + y][ox * 3:(ox + TILE) * 3] = r
    FIX_PNG.write_bytes(_png(W, H, canvas))
    FIX_JSON.write_text(json.dumps({'note': '道具格回歸樣本：每格以格心為準裁 [%d,%d]、%d 欄拼圖（test_itemimg_match.py --make-fixtures 產生，2026-10-14）'
                                    % (PAD0, PAD1, COLS), 'tile': TILE, 'cols': COLS, 'pad0': PAD0, 'cells': cells},
                                   ensure_ascii=False, indent=0), encoding='utf-8')
    print(f'{len(cells)} 格 → {FIX_PNG}（{FIX_PNG.stat().st_size // 1024} KB）')
    return 0


def make_noname_fixtures() -> int:
    import json
    cells, tiles = [], []
    t = NPAD1 - NPAD0 + 1
    for f, lst in NONAME.items():
        src = CACHE / NONAME_DIR / f
        if not src.exists():
            print('缺截圖', src)
            return 1
        w, h, bpp, rows = imgmatch.decode(src)
        for kind, slot, state, name in lst:
            cx, cy = M._xy(kind, slot)
            tile = [bytes(rows[cy + dy][(cx + NPAD0) * bpp:(cx + NPAD1 + 1) * bpp]) for dy in range(NPAD0, NPAD1 + 1)]
            if bpp == 4:
                tile = [bytes(b for i, b in enumerate(r) if i % 4 != 3) for r in tile]
            tiles.append(tile)
            cells.append({'src': f, 'kind': kind, 'slot': slot, 'cx': cx, 'cy': cy, 'state': state, 'name': name})
    n_rows = (len(tiles) + COLS - 1) // COLS
    W, H = COLS * t, n_rows * t
    canvas = [bytearray(W * 3) for _ in range(H)]
    for k, tile in enumerate(tiles):
        ox, oy = (k % COLS) * t, (k // COLS) * t
        for y, r in enumerate(tile):
            canvas[oy + y][ox * 3:(ox + t) * 3] = r
    NONAME_PNG.write_bytes(_png(W, H, canvas))
    NONAME_JSON.write_text(json.dumps({'note': '「顯示道具名」關著的實樣（2026-10-14 itemident/*-noname.png）：每格以格心為準裁 [%d,%d]、%d 欄拼圖；'
                                       'state = true 有道具 / false 空 / null 被 EXP 橫幅蓋住（test_itemimg_match.py --make-fixtures 產生）'
                                       % (NPAD0, NPAD1, COLS), 'tile': t, 'cols': COLS, 'pad0': NPAD0, 'cells': cells},
                                      ensure_ascii=False, indent=0), encoding='utf-8')
    print(f'{len(cells)} 格 → {NONAME_PNG}（{NONAME_PNG.stat().st_size // 1024} KB）')
    return 0


def load_fixtures(png=FIX_PNG, js=FIX_JSON):
    import json
    meta = json.loads(js.read_text(encoding='utf-8'))
    w, h, bpp, rows = imgmatch.decode(png)
    out = []
    for k, c in enumerate(meta['cells']):
        tx, ty = (k % meta['cols']) * meta['tile'], (k // meta['cols']) * meta['tile']
        x0, y0 = c['cx'] + meta['pad0'], c['cy'] + meta['pad0']
        t = meta['tile']

        def get(x, y, tx=tx, ty=ty, x0=x0, y0=y0, t=t):
            if not (0 <= x - x0 < t and 0 <= y - y0 < t):
                return None
            i = (tx + x - x0) * bpp
            return tuple(rows[ty + y - y0][i:i + 3])
        out.append(dict(c, get=get))
    return out


# ---- 測試 ----
def test_core():
    # score / best_pos：畫一個 10×10 方塊在 (5, 3) 位移
    tpl = [(dx, dy, 200, 30, 30) for dy in range(-5, 5) for dx in range(-5, 5)]
    cells = {(x, y): (104, 74, 49) for x in range(-20, 21) for y in range(-20, 21)}
    cells.update({(5 + dx, 3 + dy): (205, 35, 25) for dx, dy, *_ in tpl})
    s, ox, oy = imgmatch.best_pos(tpl, cells, 4, 4, (2, 2), min_n=10)
    check('imgmatch.best_pos 找到位移', (round(s, 3), ox, oy) == (1.0, 5, 3), (s, ox, oy))
    check('imgmatch.score 有效點不足 → 0', imgmatch.score(tpl, {}, 0, 0)[0] == 0.0)
    ta = imgmatch.placed([(0, 0, 200, 0, 0)] * 1, 0, 0)
    vote_cells = {(0, 0): (198, 2, 0)}
    t = imgmatch.tiebreak(vote_cells, ta, {(0, 0): (0, 0, 200)}, min_pts=1)
    check('imgmatch.tiebreak 投給像的那一邊', t['winner'] == 0, t)
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / 'c.bin'
        built = []
        b = lambda k: built.append(k) or [(-3, 4, 1, 2, 3), (int(k) % 100, 0, 9, 9, 9)]
        a1 = imgmatch.coarse_cache(p, 's1', ['1', '22'], b)
        a2 = imgmatch.coarse_cache(p, 's1', ['1', '22'], b)
        check('imgmatch.coarse_cache 第二次讀快取', a1 == a2 and built == ['1', '22'], built)
        imgmatch.coarse_cache(p, 's2', ['1', '22'], b)
        check('imgmatch.coarse_cache 戳記不同重算', built == ['1', '22', '1', '22'])


def test_index():
    check('龍王的守護 → 24054', M.ids_for_name('龍王的守護') == ['24054'], M.ids_for_name('龍王的守護'))
    check('24054 同圖 4 個名字', set(M.names_for_id('24054')) == {'合成石 7', '壞石', '龍王的守護', '不明的石頭'}, M.names_for_id('24054'))
    check('不屬於道具的 Sprite 不進索引', all(M.names_for_id(i) for i in M.index()))
    missing = next(iter(M._MISSING))
    check('沒圖的道具 → []', M.ids_for_name(missing) == [], missing)
    try:
        M.ids_for_name('不存在的道具名')
        check('查無此名 → KeyError', False)
    except KeyError:
        check('查無此名 → KeyError', True)
    check('相似圖：青貝首飾 / 白貝首飾互為換色版', '22014' in M.lookalikes('22013') and '22013' in M.lookalikes('22014'))


def test_regression(fx):
    pool = ['#' + i for i in POOL_IDS if i in M.index()]
    named = [c for c in fx if c['group'] in ('plan', 'names_off', 'extra') and c['expect']]
    t0 = time.time()
    res = [(c, M.identify(c['get'], c['kind'], c['slot'], pool)) for c in named]
    dt = time.time() - t0
    for grp, label in (('plan', '計畫 39 格'), ('names_off', '名字關掉 4 格（推定）'), ('extra', 'dep0 背包 3 格')):
        rs = [(c, r) for c, r in res if c['group'] == grp]
        good = sum(1 for c, r in rs if r['imageId'] == c['expect'])
        bad = [(c['src'], c['slot'], c['expect'], r['best'], r['score']) for c, r in rs if r['imageId'] != c['expect']]
        check(f'{label} 閉集全對', good == len(rs), f'{good}/{len(rs)} {bad}')
    gaps = [r['score'] - r['second'] for _, r in res]
    tops = [r['score'] for _, r in res]
    check('閉集最小分差 ≥ 0.06', min(gaps) >= 0.06, f'最小分差 {min(gaps):.3f}；正確分數 {min(tops):.3f}～{max(tops):.3f}'
          f'（平均 {sum(tops) / len(tops):.3f}）；第二名最高 {max(r["second"] for _, r in res):.3f}；'
          f'{len(res)} 格 × {len(pool)} 候選 {dt:.2f}s（{dt / len(res) * 1000:.0f} ms/格）')
    # 名稱 API：match_slots 用真名
    by_src = {}
    for c in named:
        by_src.setdefault((c['src'], c['kind']), []).append(c)
    want = {'24054': '龍王的守護', '23907': '千年龜的殼', '24049': '寵物誘餌', '50220': '人龍隨機蛋', '24154': '安撫之素',
            '24236': '2倍智慧果（綁定）', '22356': '離線水晶（8H）', '24169': '薩頓家的秘藥', '22013': '山賊的羽飾',
            '22050': '杉的手環', '22082': '月光的手鐲'}
    ok = True
    t_ms = []
    for (src, kind), cs in by_src.items():
        g = lambda x, y, cs=cs: next((v for v in (c['get'](x, y) for c in cs) if v is not None), (104, 74, 49))
        names = sorted({want[c['expect']] for c in cs if c['expect'] in want})
        if not names:
            continue
        t = time.time()
        r = M.match_slots(g, kind, names, slots=[c['slot'] for c in cs])
        t_ms.append((time.time() - t) / len(cs))
        for n in names:
            exp = sorted(c['slot'] for c in cs if want.get(c['expect']) == n)
            if sorted(r['hits'][n]) != exp:
                ok = False
                print('   ', src, n, '期望', exp, '得到', r['hits'][n])
    check('match_slots 用道具名找格（11 種名字）', ok, f'平均 {sum(t_ms) / len(t_ms) * 1000:.0f} ms/格（含相似圖擴充）')
    r = M.identify(next(c for c in named if c['expect'] == '24054')['get'], 'depot', 0, ['龍王的守護'])
    check('同圖多名 → ambiguous（龍王的守護）', r['ok'] and r['ambiguous'] and r['name'] == '龍王的守護', r['names'])
    c = next(c for c in named if c['expect'] == '24169')
    r = M.identify(c['get'], c['kind'], c['slot'], ['薩頓家的秘藥'])
    check('唯一圖 → 不 ambiguous（薩頓家的秘藥）', r['ok'] and not r['ambiguous'], r['names'])


def test_absent(fx):
    """要找的道具不在格裡（格裡是別的）→ match_slots 不能回報命中（換色版 / 相似圖冒充）"""
    named = [c for c in fx if c['group'] in ('plan', 'names_off', 'extra') and c['expect']]
    ids = [i for i in POOL_IDS if i in M.index()]
    rnd = random.Random(14)
    fp, n = [], 0
    t0 = time.time()
    for c in named:
        wants = [i for i in ids if i != c['expect']]
        wants = sorted(set(rnd.sample(wants, 6) + [i for i in ('22014', '22084', '22052', '24237') if i != c['expect']]))
        for i in wants:
            r = M.match_slots(c['get'], c['kind'], ['#' + i], slots=[c['slot']])
            n += 1
            if r['hits']['#' + i]:
                fp.append((c['src'], c['slot'], c['expect'], i))
    check('要找的不在格裡 → 0 誤判', not fp, f'{len(fp)}/{n} {fp[:5]}（{time.time() - t0:.1f}s）')


def test_empty_and_banner(fx):
    empties = [c for c in fx if c['expect'] is None]
    occ = [M.occupied(c['get'], c['kind'], c['slot']) for c in empties]
    check(f'空格 {len(empties)} 格判成空', not any(occ), occ)
    full = [c for c in fx if c['expect']]
    check('有道具的格判成有', all(M.occupied(c['get'], c['kind'], c['slot']) for c in full))
    g = lambda x, y: next((v for v in (c['get'](x, y) for c in empties if c['kind'] == 'bag') if v is not None), (104, 74, 49))
    r = M.match_slots(g, 'bag', ['龍王的守護'], slots=[c['slot'] for c in empties if c['kind'] == 'bag'])
    check('match_slots 排除空格', not r['cells'] and r['hits'] == {'龍王的守護': []})
    pool = ['#' + i for i in POOL_IDS if i in M.index()]
    wrong, none = [], []
    for c in (c for c in fx if c['group'] == 'banner'):
        r = M.identify(c['get'], c['kind'], c['slot'], pool)
        if r['imageId'] is None:
            none.append((c['slot'], r['dark']))
        elif r['imageId'] != c['expect']:
            wrong.append((c['slot'], c['expect'], r['imageId'], r['score']))
    check('EXP 橫幅：蓋住的格回 None、不錯判', not wrong and {s for s, _ in none} >= {0, 1, 2},
          f'None {none}；錯判 {wrong}')
    c = next(c for c in fx if c['group'] == 'banner' and c['slot'] == 1)
    r = M.match_slots(c['get'], 'bag', ['大地的羈絆[地]'], slots=[1])
    check('EXP 橫幅：match_slots 不當作有（也不當作沒有，cells 標 occluded）',
          r['hits']['大地的羈絆[地]'] == [] and r['cells'][1]['occluded'], r['cells'][1]['dark'])


def test_names_band():
    """2026-10-14 實機（DKBO5 背包，名字開著）：兩行名字蓋住圖示上半。第 1 格巴巴洛的許可證第一輪輸給火山岩碎片 → 第二輪整列丟字救回；
    第 2 格大地的羈絆、第 3 格不可思議的貝殼（不在工作集）第二輪也不准冒充（貝殼曾被認成橡樹果 0.58）→ None 交給 OCR"""
    p = HERE / 'fixtures' / 'itemimg_live_names.png'
    w, h, bpp, rows = imgmatch.decode(p)
    X0, Y0 = 707, 200

    def get(x, y):
        if 0 <= x - X0 < w and 0 <= y - Y0 < h:
            return tuple(rows[y - Y0][(x - X0) * bpp:(x - X0) * bpp + 3])
        return None
    import bag
    pool = [n for n in bag.item_pool() if n in M._BYNAME or M.norm(n) in M._BYNORM]
    r = M.match_slots(get, 'bag', pool, pool=[], slots=[0, 1, 2])
    c = r['cells']
    check('名字疊圖：巴巴洛的許可證第二輪（整列丟字）認出 24222', c[0]['imageId'] == '24222' and c[0].get('band'), (c[0]['imageId'], c[0]['score']))
    check('名字疊圖：大地的羈絆 / 不在工作集的貝殼 → None（不冒充，交給 OCR）', c[1]['imageId'] is None and c[2]['imageId'] is None,
          [(c[i]['best'], c[i]['score']) for i in (1, 2)])


def test_noname(pool):
    """2026-10-14 名字關著的實樣：倉庫格遮擋偵測（正負例）、被蓋住的格不判 occupancy / 不比對、風的鎖不漏判"""
    fx = load_fixtures(NONAME_PNG, NONAME_JSON)
    bad_state, bad_name, fake = [], [], []
    for c in fx:
        st = M.cell_state(c['get'], c['kind'], c['slot'])
        if st is not c['state']:
            bad_state.append((c['src'][:-12], c['kind'], c['slot'], c['state'], st, M.occlusion(c['get'], c['kind'], c['slot'])))
        r = M.identify(c['get'], c['kind'], c['slot'], pool)
        if c['state'] is None and (r['ok'] or not r['occluded'] or r['ranked']):
            fake.append((c['src'][:-12], c['slot'], r['names'][:2], r['score']))
        if c['name'] and not (r['ok'] and any(M.norm(c['name']) == M.norm(n) for n in r['names'])):
            bad_name.append((c['src'][:-12], c['kind'], c['slot'], c['name'], r['names'][:2], r['score']))
    cov = [c for c in fx if c['state'] is None]
    check(f'名字關著實樣：{len(fx)} 格 occupancy 三態（有 / 空 / 被蓋住）全對（被蓋住 {len(cov)} 格、沒被蓋的鄰格不誤判）', not bad_state, bad_state)
    check('被蓋住的格不比對（ok=False、occluded、不排名；舊版倉庫空格被認成 2倍智慧果 0.585）', not fake, fake)
    check('名字關著實樣：認得出的格名稱全對（含空心細線的風的鎖 2 格）', not bad_name, bad_name)
    by = {}
    for c in fx:
        by.setdefault((c['src'], c['kind']), []).append(c)
    ok = True
    for (src, kind), cs in by.items():
        g = lambda x, y, cs=cs: next((v for v in (c['get'](x, y) for c in cs) if v is not None), None)
        r = M.match_slots(g, kind, ['2倍智慧果'], pool=pool, slots=[c['slot'] for c in cs])
        hit = r['hits']['2倍智慧果']
        exp = [c['slot'] for c in cs if c['name'] == '2倍智慧果']
        covered = [c['slot'] for c in cs if c['state'] is None]
        if hit != exp or any(not r['cells'][i]['occluded'] for i in covered):
            ok = False
            print('   ', src, '命中', hit, '期望', exp)
    check('match_slots：被蓋住的格放進 cells 標 occluded（呼叫端重拍），不算命中', ok)


def main() -> int:
    if '--make-fixtures' in sys.argv:
        return make_fixtures() or make_noname_fixtures()
    if '--make-noname-fixtures' in sys.argv:
        return make_noname_fixtures()
    if not (M.IMG_DIR / 'index.tsv').exists():
        print('SKIP 沒有 tools/.cache/item-images（先跑 uv run --no-project --with UnityPy python tools/extract/item_images.py）')
        return 0
    test_core()
    test_index()
    fx = load_fixtures()
    test_regression(fx)
    test_absent(fx)
    test_empty_and_banner(fx)
    test_names_band()
    import bag
    test_noname([n for n in dict.fromkeys(bag.item_pool() + ['風的鎖', '水的戒指', '英雄的祝福', '2倍智慧果', '龍王的守護', '人龍隨機蛋',
                                                               '安撫之素', '離線水晶'])
                 if n in M._BYNAME or M.norm(n) in M._BYNORM])
    print('全部通過' if not fails else f'{fails} 項失敗')
    return 1 if fails else 0


if __name__ == '__main__':
    sys.exit(main())
