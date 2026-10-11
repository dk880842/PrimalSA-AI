#!/usr/bin/env python3
"""shotcache 離線測試（不碰遊戲）：
1. 點快取取點與 pngread 逐點一致（真實樣本抽樣 + 合成 RGB / RGBA PNG）
2. 增量更新：新圖才解碼、改過的圖重建、刪掉的圖從索引與點快取移除、沒變的圖不重做
3. 標籤優先序 manual > fixture > rule > auto；非 1440×830 = offsize、不進點快取
用法：uv run --no-project python tools/gui/test_shotcache.py"""
import random
import struct
import sys
import tempfile
import zlib
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import testenv  # noqa: E402,F401  紀錄檔轉向暫存（不污染真 actions.log / quest-events.log / errlog）
import pngread  # noqa: E402
import shotcache as S  # noqa: E402

fails = 0


def check(name, ok, info=''):
    global fails
    print(('PASS ' if ok else 'FAIL ') + name + ('' if ok or not info else f'  [{info}]'))
    fails += 0 if ok else 1


def write_png(path: Path, w: int, h: int, fn, alpha: bool = False, ftype: int = 0):
    """合成 PNG；fn(x, y) → (r, g, b)；ftype = 每列 filter（0 none / 1 sub / 2 up，Python 端算）"""
    bpp = 4 if alpha else 3
    raw, prev = bytearray(), bytearray(w * bpp)
    for y in range(h):
        cur = bytearray()
        for x in range(w):
            cur += bytes(fn(x, y)) + (b'\xff' if alpha else b'')
        f = bytearray(cur)
        if ftype == 1:
            for i in range(len(cur)):
                f[i] = (cur[i] - (cur[i - bpp] if i >= bpp else 0)) & 255
        elif ftype == 2:
            for i in range(len(cur)):
                f[i] = (cur[i] - prev[i]) & 255
        raw += bytes([ftype]) + f
        prev = cur

    def chunk(t, d):
        return struct.pack('>I', len(d)) + t + d + struct.pack('>I', zlib.crc32(t + d) & 0xffffffff)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', w, h, 8, 6 if alpha else 2, 0, 0, 0)) + chunk(b'IDAT', zlib.compress(bytes(raw))) + chunk(b'IEND', b''))


# ---- 1. 與 pngread 逐點一致 ----
random.seed(7)
real = [r for r in sorted(S.load_index()) if S.load_index()[r]['label'] != 'offsize']
if len(real) < 20:
    check('真實樣本索引存在（先跑 shotcache.py build）', False, str(len(real)))
else:
    sample = random.sample(real, 12)
    bad = 0
    pts = [(random.randrange(1440), random.randrange(830)) for _ in range(60)] + [(0, 0), (1439, 829)]
    for rel in sample:
        w, h, bpp, rows = pngread.decode((S.CACHE / rel).read_bytes())
        want = pngread.pixels(rows, bpp, pts)
        shot = S.get(rel)
        if shot.pixels(pts) != want or any(shot(x, y) != want[(x, y)] for x, y in pts[:5]):
            bad += 1
        if S.get(rel).pixels(pts) != want:          # 第二次走點快取
            bad += 1
    check('真實樣本 12 張 × 62 點與 pngread 一致（冷 / 熱）', bad == 0, str(bad))
    try:
        S.get(real[0])(1440, 0)
        check('越界丟 IndexError', False)
    except IndexError:
        check('越界丟 IndexError', True)

# ---- 以下用暫存目錄，不動真實索引 ----
with tempfile.TemporaryDirectory() as td:
    td = Path(td)
    S.CACHE, S.INDEX, S.PTS = td, td / 'shots-index.json', td / 'shotcache' / 'points.pkl'
    S._TABLE, S._DIRTY = None, False
    fx = {'fx/panel.png': 'pet', 'both.png': 'bag'}
    S._fixture_tables = lambda: (dict(fx), {'neg.png'})
    W, H = S.SIZE
    solid = lambda c: (lambda x, y: c)                                  # noqa: E731
    grad = lambda x, y: ((x * 7) & 255, (y * 3) & 255, (x + y) & 255)   # noqa: E731
    write_png(td / 'a.png', W, H, grad, ftype=2)
    write_png(td / 'b_rgba.png', W, H, grad, alpha=True, ftype=1)
    write_png(td / 'fx' / 'panel.png', W, H, solid((10, 20, 30)))
    write_png(td / 'both.png', W, H, solid((40, 50, 60)))
    write_png(td / 'quest-log' / '010101-dialog.png', W, H, solid((1, 2, 3)))
    write_png(td / 'neg.png', W, H, solid((9, 9, 9)))
    write_png(td / 'small.png', 100, 50, solid((5, 5, 5)))
    write_png(td / 'pet-images' / 'skip.png', W, H, solid((5, 5, 5)))
    r = S.build(verbose=False, workers=1)
    idx = S.load_index()
    check('合成：掃描排除 pet-images、7 張進索引', sorted(idx) == ['a.png', 'b_rgba.png', 'both.png', 'fx/panel.png', 'neg.png', 'quest-log/010101-dialog.png', 'small.png'], str(sorted(idx)))
    check('非 1440×830 = offsize 不進點快取', idx['small.png']['label'] == 'offsize' and idx['small.png']['sha1'] not in S._table())
    check('首次建置 new=7', r['new'] == 7 and r['offsize'] == 1, str(r))
    # 合成圖逐點一致（RGB / RGBA、filter 1 / 2）
    ok = True
    for rel, fn in (('a.png', grad), ('b_rgba.png', grad)):
        sh = S.get(rel)
        for x, y in [(0, 0), (5, 7), (1439, 829), (700, 400), (33, 1)]:
            ok &= sh(x, y) == tuple(fn(x, y))
    check('合成 RGB / RGBA PNG 取點正確', ok)
    # 標籤優先序
    check('fixture 標籤優先於 auto', (idx['fx/panel.png']['label'], idx['fx/panel.png']['label_src']) == ('pet', 'fixture'))
    check('rule（quest-log -dialog）', (idx['quest-log/010101-dialog.png']['label'], idx['quest-log/010101-dialog.png']['label_src']) == ('dialog', 'rule'))
    check('無規則 = auto', idx['a.png']['label_src'] == 'auto')
    check('PANEL_NEG 記 not_panel', idx['neg.png'].get('not_panel') is True)
    S.relabel('both.png', 'idle')                       # manual 蓋過 fixture 的 bag
    S.build(verbose=False, workers=1)
    check('manual 優先於 fixture、重建後保留', S.label_of('both.png') == ('idle', 'manual'), str(S.label_of('both.png')))
    S.relabel('quest-log/010101-dialog.png', 'reward')
    S.build(verbose=False, workers=1)
    check('manual 優先於 rule', S.label_of('quest-log/010101-dialog.png') == ('reward', 'manual'))
    # 增量
    before = {k: dict(v) for k, v in S.load_index().items()}
    r = S.build(verbose=False, workers=1)
    check('沒變：new=0、索引不變', r['new'] == 0 and S.load_index() == before, str(r))
    write_png(td / 'new.png', W, H, solid((77, 88, 99)))
    r = S.build(verbose=False, workers=1)
    check('新增一張：只 new=1', r['new'] == 1 and r['removed'] == 0, str(r))
    check('新圖可取點', S.get('new.png')(10, 10) == (77, 88, 99))
    sha_old = S.load_index()['a.png']['sha1']
    write_png(td / 'a.png', W, H, solid((200, 100, 50)))
    r = S.build(verbose=False, workers=1)
    check('改過的圖：重建、sha1 變、取到新像素', r['new'] == 1 and S.load_index()['a.png']['sha1'] != sha_old and S.get('a.png')(3, 3) == (200, 100, 50), str(r))
    check('舊 sha1 的點快取已清', sha_old not in S._table())
    (td / 'new.png').unlink()
    r = S.build(verbose=False, workers=1)
    check('刪圖：從索引移除', r['removed'] == 1 and 'new.png' not in S.load_index(), str(r))
    S.flush()
    S._TABLE = None
    check('點快取落盤後重載仍可用', S.get('a.png')(3, 3) == (200, 100, 50) and S.PTS.exists())
    check('iter_shots 濾標籤 / 來源', [x[0] for x in S.iter_shots(label='pet')] == ['fx/panel.png'] and 'both.png' in [x[0] for x in S.iter_shots(src='manual')])

S._TABLE, S._DIRTY = None, False      # 暫存目錄已刪：不要讓 atexit flush 寫回
print('失敗 %d' % fails if fails else '全部通過')
sys.exit(1 if fails else 0)
