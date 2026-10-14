#!/usr/bin/env python3
"""縮圖辨識測試用的固定截圖（只用標準函式庫）。

問題（2026-10-14）：test_pet_img / test_petimg_match 直接讀 tools/.cache/*.png，那些檔名（s3.png…）是 agent 隨手截圖的暫存名，
會被覆蓋（s3.png 10-14 09:47 被新截圖蓋掉 → 兩支測試失敗）。改成 tools/gui/fixtures/petimg/ 的固定檔（進 git）。

固定檔 = 原截圖「只留測試真的讀到的像素（外擴 PAD 格），其餘塗黑」：同尺寸 1440×830、座標不變，PNG 壓縮後每張只有幾十 KB。
讀到哪些像素是實際跑一次兩支測試記下來的（pngread.decode 回傳會記錄切片的列），所以測試邏輯改了要重產。

用法：
  測試裡：CACHE = shotfix.SHOTS；CACHE / 'z.png' → 有固定檔用固定檔，沒有退回 tools/.cache（環境變數 PSA_SHOTFIX=0 強制用 tools/.cache）
  重產：uv run --no-project python tools/gui/shotfix.py build [檔名 …]     # 從 tools/.cache 原截圖重做（原檔要還在、而且是對的那張）
"""
import os
import struct
import sys
import zlib
from pathlib import Path

HERE = Path(__file__).resolve().parent
CACHE_DIR = HERE.parent / '.cache'
FIX_DIR = HERE / 'fixtures' / 'petimg'
PAD = 2
NAMES = ['bn_0.png', 's0.png', 's4.png', 's5.png', 'z.png', 'dep.png', 'dep2.png', 'f0.png', 'm7.png', 'catch-m0/dep1.png', 'k1.png']


class _Shots:
    """CACHE / 檔名 → 固定檔（fixtures/petimg/，子資料夾 / 換成 __）優先，沒有就 tools/.cache 原檔"""

    def __truediv__(self, name) -> Path:
        fx = FIX_DIR / str(name).replace('/', '__')
        if os.environ.get('PSA_SHOTFIX') != '0' and fx.exists():
            return fx
        return CACHE_DIR / name


SHOTS = _Shots()


class _RecRow(bytearray):
    """記錄被切片讀過的位元組範圍（rows_getter 用 rows[y][x*bpp:x*bpp+3]）"""
    __slots__ = ('hits',)

    def __getitem__(self, k):
        if isinstance(k, slice):
            self.hits.add((k.start or 0, k.stop if k.stop is not None else len(self)))
        else:
            self.hits.add((k, k + 1))
        return bytearray.__getitem__(self, k)


def encode_png(w: int, h: int, bpp: int, rows) -> bytes:
    """8 bit RGB / RGBA、filter 0 的 PNG（純標準函式庫）"""
    def chunk(t, d):
        return struct.pack('>I', len(d)) + t + d + struct.pack('>I', zlib.crc32(t + d) & 0xffffffff)
    raw = b''.join(b'\x00' + bytes(r) for r in rows)
    ihdr = struct.pack('>IIBBBBB', w, h, 8, 6 if bpp == 4 else 2, 0, 0, 0)
    return b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', ihdr) + chunk(b'IDAT', zlib.compress(raw, 9)) + chunk(b'IEND', b'')


def build(names=None) -> int:
    """跑兩支測試（強制讀 tools/.cache 原截圖）記下讀到的像素 → 寫 fixtures/petimg/*.png"""
    import contextlib
    import io
    import pngread
    names = names or NAMES
    rec: dict = {}
    real = pngread.decode

    def decode(data):
        w, h, bpp, rows = real(data)
        for fn in names:
            p = CACHE_DIR / fn
            if p.exists() and p.stat().st_size == len(data) and p.read_bytes() == data:
                if fn not in rec:
                    rr = [_RecRow(r) for r in rows]
                    for r in rr:
                        r.hits = set()
                    rec[fn] = (w, h, bpp, rr)
                return rec[fn]
        return w, h, bpp, rows
    os.environ['PSA_SHOTFIX'] = '0'
    pngread.decode = decode
    sys.path.insert(0, str(HERE))
    try:
        import test_pet_img
        import test_petimg_match
        for mod in (test_pet_img, test_petimg_match):
            with contextlib.redirect_stdout(io.StringIO()):
                mod.main()
    finally:
        pngread.decode = real
    FIX_DIR.mkdir(parents=True, exist_ok=True)
    for fn, (w, h, bpp, rows) in rec.items():
        keep = [bytearray(len(r)) for r in rows]
        n = 0
        for y, r in enumerate(rows):
            for a, b in r.hits:
                xa, xb = max(0, a // bpp - PAD), min(w, -(-b // bpp) + PAD)
                for yy in range(max(0, y - PAD), min(h, y + PAD + 1)):
                    keep[yy][xa * bpp:xb * bpp] = bytearray.__getitem__(rows[yy], slice(xa * bpp, xb * bpp))
                n += 1
        out = FIX_DIR / fn.replace('/', '__')
        out.write_bytes(encode_png(w, h, bpp, keep))
        print(f'{out.relative_to(HERE.parent.parent)}：{n} 段讀取、{out.stat().st_size // 1024} KB')
    miss = [fn for fn in names if fn not in rec]
    if miss:
        print(f'沒用到 / 不在 tools/.cache：{miss}')
    return 0


if __name__ == '__main__':
    if len(sys.argv) >= 2 and sys.argv[1] == 'build':
        sys.exit(build(sys.argv[2:] or None))
    print(__doc__)
    sys.exit(2)
