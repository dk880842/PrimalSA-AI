#!/usr/bin/env python3
"""截圖端 ps1（stat / digitmatch / ocr / titlematch / findmark）的座標換算離線測試（不碰遊戲；P2，計畫 notes/plan-display-scale.md）。
用合成圖（標準函式庫寫 PNG）經各腳本的 -Image 讀入：
  ① 2880×1659（筆電）：預設輸出 == PSA_GEOM=off（舊程式路徑）的輸出（逐位元組，去掉 ms）——換算層對筆電是恆等；
  ② 1728×995（同比例）：同一個畫面（以邏輯座標畫）讀得出相同的內容——血條 % / 黃色色塊位置 / OCR 裁切內容 / HUD 點陣欄位大小 / 標題樣板；
  ③ PSA_GEOM=off 的 1728×995：舊行為（不支援）；樣板未就緒（titlematch 實體尺寸子資料夾不存在）回 notpl、不誤判。
舊版（git HEAD）與新版在真實截圖上的逐位元組比對在 P2 實作時做過，結果記在計畫檔 P2 段。
用法：uv run --no-project python tools/gui/test_capture_scale.py"""
import json
import os
import shutil
import struct
import sys
import zlib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import testenv  # noqa: E402,F401
import pngread  # noqa: E402
import winenv  # noqa: E402

GUI = Path(__file__).resolve().parent
TMP = GUI.parent / '.cache' / 'test-capture-scale'
fails = 0


def check(name, ok, detail=''):
    global fails
    print(('PASS ' if ok else 'FAIL ') + name + ('' if ok else f'  {detail}'))
    if not ok:
        fails += 1


# ---------- 合成圖 ----------
def write_png(path: Path, w: int, h: int, px) -> None:
    """px(x, y) → (r, g, b)；8 bit RGB"""
    raw = bytearray()
    for y in range(h):
        raw.append(0)
        for x in range(w):
            raw += bytes(px(x, y))

    def chunk(t, d):
        return struct.pack('>I', len(d)) + t + d + struct.pack('>I', zlib.crc32(t + d) & 0xffffffff)
    path.write_bytes(b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', w, h, 8, 2, 0, 0, 0))
                     + chunk(b'IDAT', zlib.compress(bytes(raw), 1)) + chunk(b'IEND', b''))


BG = (60, 40, 30)
EMPTY = (123, 97, 65)        # 血條空槽
RED = (200, 40, 40)          # 血條填滿
GOLD = (255, 200, 40)        # 黃色標記
INK = (20, 20, 20)           # 標題黑字
PAPER = (240, 225, 190)      # 標題卡片底
HUD_BOX = (340, 92, 200, 44)   # HUD HP 欄（邏輯客戶區像素）
HP_Y, BAR_X0, BAR_X1 = 112, 344, 532
PATTERN = ['1111000011110000111100001111',      # 標題樣板：粗筆畫，縮放後仍認得（每格 = 截圖座標 3×3）
           '1001000010010000100100001001',
           '1111011110011110111100001111',
           '1001000010010000100100001001',
           '1001000011110000111100001111']
TITLE_AT = (110, 300)       # 樣板左上角（截圖座標）
GOLD_AT = (700, 285, 14, 24)  # 黃色標記（截圖座標 x, y, w, h）


def scene(w: int, h: int):
    """邏輯座標畫的畫面（2880×1659 座標系 → 乘 w/2880、h/1659）：血條填到 50%、HUD HP 欄白字塊、黃色標記、標題卡片 + 黑字樣板"""
    fx, fy = w / 2880, h / 1659

    def inbox(x, y, bx, by, bw, bh):    # 實體像素是否落在邏輯框 (bx,by,bw,bh) 內
        return bx * fx <= x < (bx + bw) * fx and by * fy <= y < (by + bh) * fy

    def px(x, y):
        # 血條：中線 ±2 px 一條；左半紅、右半空槽（x 在邏輯 344～532，填到 438 = 50%）
        if inbox(x, y, BAR_X0, HP_Y - 4, BAR_X1 - BAR_X0, 8):
            return RED if x < 438 * fx else EMPTY
        # HUD HP 欄：一塊白字（亮字二值化後全是 1），位置在欄內 (60,26,80,16)，避開血條中線的 8 列
        if inbox(x, y, HUD_BOX[0] + 60, HUD_BOX[1] + 26, 80, 16):
            return (255, 255, 255)
        if inbox(x, y, GOLD_AT[0] * 2, GOLD_AT[1] * 2, GOLD_AT[2] * 2, GOLD_AT[3] * 2):
            return GOLD
        # 標題卡片（截圖座標 90,290 起 220×30）米色底 + 樣板黑字
        if inbox(x, y, 180, 580, 440, 60):
            for r, row in enumerate(PATTERN):
                for c, ch in enumerate(row):
                    if ch == '1' and inbox(x, y, (TITLE_AT[0] + c * 3) * 2, (TITLE_AT[1] + r * 3) * 2, 6, 6):
                        return INK
            return PAPER
        return BG
    return px


def pattern_tpl(path: Path) -> None:
    """標題樣板圖（灰階，截圖座標 1 格 = 3 px）；周圍留 1 px 米色邊"""
    rows = [''.join(ch * 3 for ch in row) for row in PATTERN for _ in range(3)]
    w, h = len(rows[0]) + 2, len(rows) + 2
    write_png(path, w, h, lambda x, y: INK if 1 <= x <= w - 2 and 1 <= y <= h - 2 and rows[y - 1][x - 1] == '1' else PAPER)


def ps(script, *args, geom_off=False, env=None):
    old = os.environ.get('PSA_GEOM')
    if geom_off:
        os.environ['PSA_GEOM'] = 'off'
    else:
        os.environ.pop('PSA_GEOM', None)
    saved = {}
    if env:
        saved['WSLENV'] = os.environ.get('WSLENV')
        os.environ['WSLENV'] = ':'.join(env)     # winenv.child_env 會保留既有 WSLENV 再補 PSA_GEOM
    for k, v in (env or {}).items():
        saved.setdefault(k, None)
        saved[k] = os.environ.get(k)
        os.environ[k] = v
    try:
        r = winenv.run_ps(script, *[str(a) for a in args], timeout=240)
    finally:
        for k, v in saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        if old is None:
            os.environ.pop('PSA_GEOM', None)
        else:
            os.environ['PSA_GEOM'] = old
    return r.stdout


def js(out):
    try:
        return json.loads(out.strip().splitlines()[-1])
    except (ValueError, IndexError):
        return {'ok': False, 'raw': out[:200]}


def strip_ms(s):
    import re
    return re.sub(r'"ms":\d+,?', '', s)


def win(p: Path):
    return str(winenv.to_windows(p))


shutil.rmtree(TMP, ignore_errors=True)
TMP.mkdir(parents=True)
try:
    LAP, EXT = TMP / 'lap.png', TMP / 'ext.png'
    write_png(LAP, 2880, 1659, scene(2880, 1659))
    write_png(EXT, 1728, 995, scene(1728, 995))
    tdir = TMP / 'tpl'
    tdir.mkdir()
    pattern_tpl(tdir / 'T@1.png')
    L, E = win(LAP), win(EXT)

    # ① 筆電恆等：預設 == PSA_GEOM=off（舊路徑）
    for name, args in (('digitmatch', ['-Image', L]), ('findmark', ['-Image', L]),
                       ('titlematch', ['-Image', L, '-Mode', 'match', '-Dir', win(tdir), '-Thr', '0.5']),
                       ('ocr', ['-Image', L, '75', '270', '260', '180', '-Zooms', '2,3', '-Dark', '150']),
                       ('stat', ['-Image', L])):
        a = strip_ms(ps(f'{name}.ps1', *args)); b = strip_ms(ps(f'{name}.ps1', *args, geom_off=True))
        check(f'筆電 2880x1659：{name}.ps1 預設輸出 == PSA_GEOM=off（逐位元組）', a == b and '"ok":true' in a, f'{a[:120]} | {b[:120]}')
    # findmark -Crop 存圖：位元組相同
    fa, fb = TMP / 'crop_a.png', TMP / 'crop_b.png'
    ps('findmark.ps1', '-Image', L, '-Crop', '690,280,40,40', '-Out', win(fa))
    ps('findmark.ps1', '-Image', L, '-Crop', '690,280,40,40', '-Out', win(fb), geom_off=True)
    check('筆電：findmark -Crop 裁圖 == PSA_GEOM=off（位元組）', fa.exists() and fa.read_bytes() == fb.read_bytes())

    # ② 1728×995：內容讀得出
    d_lap, d_ext = js(ps('digitmatch.ps1', '-Image', L)), js(ps('digitmatch.ps1', '-Image', E))
    check('digitmatch 筆電：hpPct = 50±2', abs(d_lap.get('hpPct', -1) - 50) <= 2, str(d_lap.get('hpPct')))
    check('digitmatch 1728x995：ok、layout = 實體尺寸（樣板用）、logical = 2880x1659、hpPct = 50±2',
          d_ext.get('ok') and d_ext.get('layout') == '1728x995' and d_ext.get('logical') == '2880x1659' and abs(d_ext.get('hpPct', -1) - 50) <= 2, str({k: d_ext.get(k) for k in ('ok', 'layout', 'logical', 'hpPct')}))
    check('digitmatch 筆電輸出沒有 logical 欄位（與舊輸出相同）', 'logical' not in d_lap)
    hp = lambda d: d['fields']['hp'].split(',')   # noqa: E731
    rows_l, rows_e = hp(d_lap), hp(d_ext)
    check('digitmatch HP 欄尺寸：筆電 200x44、1728x995 ≈ 120x26（0.6 倍）', (len(rows_l[0]), len(rows_l)) == (200, 44) and abs(len(rows_e[0]) - 120) <= 1 and abs(len(rows_e) - 26) <= 1, f'{len(rows_e[0])}x{len(rows_e)}')
    ink_l = sum(r.count('1') for r in rows_l); ink_e = sum(r.count('1') for r in rows_e)
    check(f'digitmatch HP 欄白字塊：筆電 {ink_l} 點（80x16=1280）、1728x995 {ink_e} 點 ≈ 0.36 倍', ink_l == 1280 and abs(ink_e - 1280 * 0.36) <= 1280 * 0.36 * 0.1, f'{ink_e}')
    b_ext = js(ps('digitmatch.ps1', '-Image', E, '-Boxes', '340,92,200,44,1;2220,150,360,46,0'))
    check('digitmatch -Boxes 1728x995：邏輯框換成實體像素（HP 欄 ≈ 120x26、白字塊 ≈ 0.36 倍）',
          b_ext.get('ok') and abs(len(b_ext['fields']['b0'].split(',')[0]) - 120) <= 1 and abs(b_ext['fields']['b0'].count('1') - 1280 * 0.36) <= 60 and b_ext.get('logical') == '2880x1659', str(b_ext)[:200])
    b_lap = js(ps('digitmatch.ps1', '-Image', L, '-Boxes', '340,92,200,44,1'))
    check('digitmatch -Boxes 筆電：原樣 200x44', len(b_lap['fields']['b0'].split(',')[0]) == 200 and len(b_lap['fields']['b0'].split(',')) == 44)

    f_lap, f_ext = js(ps('findmark.ps1', '-Image', L)), js(ps('findmark.ps1', '-Image', E))
    gx, gy = GOLD_AT[0] + GOLD_AT[2] / 2, GOLD_AT[1] + GOLD_AT[3] / 2
    def near(bl):   # noqa: E306
        return [b for b in bl.get('blobs', []) if abs(b['x'] - gx) <= 3 and abs(b['y'] - gy) <= 3 and b['w'] >= 11 and b['h'] >= 20]
    check('findmark 筆電 / 1728x995：黃色標記都在截圖座標 (707,297) 附近、大小約 14x24（截圖座標，兩邊可比）', len(near(f_lap)) == 1 and len(near(f_ext)) == 1,
          f'lap={near(f_lap)} ext={near(f_ext)}')
    fc = TMP / 'crop_e.png'
    ps('findmark.ps1', '-Image', E, '-Crop', '690,280,40,40', '-Out', win(fc))
    w, h, bpp, rows = pngread.decode(fc.read_bytes())
    gold_px = sum(1 for r in rows for x in range(w) if tuple(r[x * bpp:x * bpp + 3]) == GOLD)
    check(f'findmark -Crop 1728x995：輸出 {w}x{h} = 40*4 平方；裁到黃色標記（金色佔 14*24/1600 ≈ 21%，實 {gold_px / (w * h):.0%}）', (w, h) == (160, 160) and 0.17 <= gold_px / (w * h) <= 0.25)
    off = js(ps('findmark.ps1', '-Image', E, geom_off=True))
    check('findmark PSA_GEOM=off 的 1728x995：舊行為（取每 2x2 左上點；位置 / 大小 ≈ 筆電的 864/830 比例，不等於換算後）', off.get('ok') and not near(off))

    # OCR 裁切內容：用 OCR_DEBUG 存放大後的圖，量裁到的黑 / 白比例。框 (110,296,100,30) 截圖座標 = 邏輯 (220,592,200,60)
    def ocr_crop(img, geom_off=False):
        dbg = TMP / ('ocr_off.png' if geom_off else 'ocr_dbg.png')
        dbg.unlink(missing_ok=True)
        r = js(ps('ocr.ps1', '-Image', img, '110', '296', '100', '30', '-Zoom', '3', '-Dark', '150', geom_off=geom_off, env={'OCR_DEBUG': win(dbg)}))
        if not dbg.exists():
            return r, None
        w, h, bpp, rows = pngread.decode(dbg.read_bytes())
        ink = sum(1 for rr in rows for x in range(w) if rr[x * bpp] < 128)
        return r, (w, h, ink / (w * h))
    r_l, c_l = ocr_crop(L); r_e, c_e = ocr_crop(E)
    check('ocr 筆電 / 1728x995：輸出尺寸相同（100*3+80 x 30*3+80）', r_l.get('ok') and r_e.get('ok') and c_l and c_e and c_l[:2] == c_e[:2] == (380, 170), f'{c_l} {c_e}')
    check(f'ocr 1728x995：黑字比例與筆電相近（{c_l[2]:.3f} vs {c_e[2]:.3f}，裁到同一塊標題字）' if c_l and c_e else 'ocr 黑字比例', bool(c_l and c_e and c_l[2] > 0.02 and abs(c_l[2] - c_e[2]) <= 0.35 * c_l[2]), f'{c_l} {c_e}')
    s_lap = js(ps('stat.ps1', '-Image', L)); s_ext = js(ps('stat.ps1', '-Image', E)); s_off = js(ps('stat.ps1', '-Image', E, geom_off=True))
    check('stat 筆電 / 1728x995：ok、hpPct = 50±2（血條掃描線換算）', s_lap.get('ok') and s_ext.get('ok') and abs(s_lap.get('hpPct', -1) - 50) <= 2 and abs(s_ext.get('hpPct', -1) - 50) <= 2, f'{s_lap.get("hpPct")} {s_ext.get("hpPct")}')
    check('stat PSA_GEOM=off 的 1728x995：舊行為 = 不支援（ok=false、訊息含 1728x995）', s_off.get('ok') is False and '1728x995' in s_off.get('error', ''))
    d_off = js(ps('digitmatch.ps1', '-Image', E, geom_off=True))
    check('digitmatch PSA_GEOM=off 的 1728x995：不支援', d_off.get('ok') is False)

    # ③ titlematch：筆電命中；1728x995 沒有實體尺寸樣板子資料夾 → notpl（不拿筆電樣板硬比）；有子資料夾才比，位置在截圖座標
    t_lap = js(ps('titlematch.ps1', '-Image', L, '-Mode', 'match', '-Dir', win(tdir), '-Thr', '0.5'))
    cx, cy = TITLE_AT[0] + len(PATTERN[0]) * 3 / 2 + 1, TITLE_AT[1] + len(PATTERN) * 3 / 2 + 1
    h0 = (t_lap.get('hits') or [{}])[0]
    check(f'titlematch 筆電：命中 T、位置 ≈ ({cx:.0f},{cy:.0f})、score ≥ 0.9', h0.get('name') == 'T@1' and abs(h0['x'] - cx) <= 3 and abs(h0['y'] - cy) <= 3 and h0['score'] >= 0.9, str(t_lap)[:200])
    t_ext = js(ps('titlematch.ps1', '-Image', E, '-Mode', 'match', '-Dir', win(tdir), '-Thr', '0.5'))
    check('titlematch 1728x995 沒有 <樣板>\\1728x995\\：ok、hits 空、notpl = true', t_ext.get('ok') and t_ext.get('hits') == [] and t_ext.get('notpl') is True, str(t_ext)[:200])
    (tdir / '1728x995').mkdir()
    pattern_tpl(tdir / '1728x995' / 'T@1.png')
    t_ext2 = js(ps('titlematch.ps1', '-Image', E, '-Mode', 'match', '-Dir', win(tdir), '-Thr', '0.5'))
    h1 = (t_ext2.get('hits') or [{}])[0]
    check(f'titlematch 1728x995 有實體尺寸子資料夾：命中、位置同為截圖座標 ≈ ({cx:.0f},{cy:.0f})（正規化成 1440x830 後比）', h1.get('name') == 'T@1' and abs(h1['x'] - cx) <= 3 and abs(h1['y'] - cy) <= 3 and 'notpl' not in t_ext2, str(t_ext2)[:200])
    t_off = js(ps('titlematch.ps1', '-Image', E, '-Mode', 'match', '-Dir', win(tdir), '-Thr', '0.5', geom_off=True))
    check('titlematch PSA_GEOM=off 的 1728x995：舊行為（不縮放、不看子資料夾、不回 notpl）', t_off.get('ok') and 'notpl' not in t_off)
    img1440 = TMP / 'n1440.png'
    write_png(img1440, 1440, 830, scene(1440, 830))
    t_n = js(ps('titlematch.ps1', '-Image', win(img1440), '-Mode', 'match', '-Dir', win(tdir), '-Thr', '0.5'))
    check('titlematch 1440x830 測試圖（已正規化）：不看子資料夾、照舊命中', t_n.get('ok') and t_n.get('hits') and 'notpl' not in t_n, str(t_n)[:200])
finally:
    shutil.rmtree(TMP, ignore_errors=True)

# 靜態：BOM、不再有寫死的 ×2 / 縮半
for f in ('stat.ps1', 'ocr.ps1', 'digitmatch.ps1', 'titlematch.ps1', 'findmark.ps1', 'psageom.ps1'):
    check(f'{f} 有 BOM', (GUI / f).read_bytes()[:3] == b'\xef\xbb\xbf')
    check(f'{f} 走 psageom.ps1', 'psageom.ps1' in (GUI / f).read_text(encoding='utf-8-sig') or f == 'psageom.ps1')
check('winenv 白名單：stat / ocr / findmark 有 Image；server 監看 psageom.ps1', all('Image' in winenv.SERVER_NAMED[k] for k in ('stat', 'ocr', 'findmark')))

print('OK' if not fails else f'FAIL {fails} 項')
sys.exit(1 if fails else 0)
