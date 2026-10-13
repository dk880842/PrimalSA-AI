#!/usr/bin/env python3
"""圖示 ↔ 畫面像素比對的共用核心（純函式、只用標準函式庫）。2026-10-14 階段 2（notes/plan-item-icon-match.md）。

給 itemimg_match.py（道具格）用；petimg_match.py 目前仍用自己的那一份（是否改用本模組待使用者決定，計畫階段 6）。
演算法與 petimg_match 相同：
  1. 樣板：Sprite 依倍率縮成截圖格點，只取 alpha ≥ alpha_min 的不透明點 → [(dx, dy, r, g, b)]（相對 Sprite 中心）。
  2. 分數：樣板放在 (ox, oy) 時，不透明點中「與畫面三通道差總和 ≤ 3×tol」的比例（inlier 比例；被遮掉 / 讀不到的點不算分母）。
  3. 位置：期望中心附近先粗找（位移步 coarse_step、樣板每 coarse_stride 點取 1）再細找（全點、±1）。
  4. 前兩名太近時 tiebreak：只看兩樣板顏色差很大的點投票。
  5. 大量樣板的粗篩快取：coarse_cache 把 {key: 粗樣板} 壓縮存到磁碟，戳記不符自動重算。

本模組不讀任何遊戲畫面、不知道版面；版面（倍率 / 中心偏移 / 遮罩）由呼叫端決定。
"""
import struct
import zlib
from pathlib import Path

import pngread

ALPHA_MIN = 250
TOL = 40            # 每點平均通道差 ≤ TOL 算吻合（三通道總和 ≤ 3×TOL）
MIN_N = 40          # 有效點少於這個數 → 分數 0（避免幾乎全被遮掉時亂給高分）


# ---- 影像來源 ----
def decode(src):
    """PNG 路徑 / bytes → (w, h, bpp, rows)"""
    if isinstance(src, (str, Path)):
        src = Path(src).read_bytes()
    return pngread.decode(src)


def rows_getter(rows, bpp: int):
    """pngread 解碼列 → get(x, y) → (r, g, b)"""
    return lambda x, y: tuple(rows[y][x * bpp:x * bpp + 3])


def as_getter(img):
    """統一成 get(x, y) → (r,g,b)：接受 callable、{(x,y): rgb} dict、pngread.decode 的 (w,h,bpp,rows)、PNG 路徑"""
    if callable(img):
        return img
    if isinstance(img, dict):
        return lambda x, y: img.get((x, y))
    if isinstance(img, (str, Path)):
        img = decode(img)
    w, h, bpp, rows = img
    return rows_getter(rows, bpp)


# ---- 樣板 ----
def template(decoded, scale: float, alpha_min: int = ALPHA_MIN, round_size: bool = False) -> list:
    """Sprite（pngread.decode 結果）縮成截圖格點的樣板 [(dx, dy, r, g, b)]，dx/dy 相對 Sprite 中心（截圖 px，整數）。
    round_size=False：輸出尺寸 int(w*scale)（petimg 用法）；True：round（道具 80×0.9 = 72）。最近鄰取樣"""
    w, h, bpp, rows = decoded
    tw, th = (int(round(w * scale)), int(round(h * scale))) if round_size else (int(w * scale), int(h * scale))
    pts = []
    for ty in range(th):
        sy = min(h - 1, int((ty + 0.5) / scale))
        for tx in range(tw):
            sx = min(w - 1, int((tx + 0.5) / scale))
            p = rows[sy][sx * bpp:sx * bpp + bpp]
            if bpp == 4 and p[3] < alpha_min:
                continue
            pts.append((tx - tw // 2, ty - th // 2, p[0], p[1], p[2]))
    return pts


def placed(tpl, ox: int, oy: int) -> dict:
    """樣板放在 (ox, oy) → {(x, y): (r, g, b)}"""
    return {(ox + dx, oy + dy): (r, g, b) for dx, dy, r, g, b in tpl}


# ---- 畫面區塊 ----
def region(get, cx: int, cy: int, clip, drop=None) -> dict:
    """讀一格可比的像素 {(x,y): rgb}：clip = (x0, y0, x1, y1) 相對 (cx, cy)；
    drop(rgb, dx, dy) → True 的點丟掉（文字 / 角標等遮擋）。get 回 None 的點也丟掉"""
    get = as_getter(get)
    x0, y0, x1, y1 = clip
    out = {}
    for dy in range(y0, y1 + 1):
        for dx in range(x0, x1 + 1):
            c = get(cx + dx, cy + dy)
            if c is None or (drop and drop(c, dx, dy)):
                continue
            out[(cx + dx, cy + dy)] = c
    return out


# ---- 分數 / 位置 ----
def score(tpl, cells: dict, ox: int, oy: int, tol: int = TOL, step: int = 1, min_n: int = MIN_N):
    """樣板放在 (ox, oy) 的 inlier 比例 → (比例, 有效點數)；有效點 < min_n → 0.0"""
    lim = 3 * tol
    hit = n = 0
    g = cells.get
    for i in range(0, len(tpl), step):
        dx, dy, r, gg, b = tpl[i]
        c = g((ox + dx, oy + dy))
        if c is None:
            continue
        n += 1
        if abs(c[0] - r) + abs(c[1] - gg) + abs(c[2] - b) <= lim:
            hit += 1
    return (hit / n if n >= min_n else 0.0), n


def coarse_pos(tpl, cells: dict, ex: int, ey: int, search, tol: int = TOL, step: int = 2, stride: int = 3,
               min_n: int = MIN_N):
    """粗找：(ex, ey) ± search 內位移步 step、樣板每 stride 點取 1 → (分數, ox, oy)"""
    sx, sy = search
    best = (-1.0, ex, ey)
    for oy in range(ey - sy, ey + sy + 1, step):
        for ox in range(ex - sx, ex + sx + 1, step):
            s, _ = score(tpl, cells, ox, oy, tol, stride, min_n)
            if s > best[0]:
                best = (s, ox, oy)
    return best


def best_pos(tpl, cells: dict, ex: int, ey: int, search, tol: int = TOL, coarse_step: int = 2, coarse_stride: int = 3,
             min_n: int = MIN_N):
    """粗找（coarse_pos）→ 細找（全點、粗找最佳位置 ±1）→ (分數, ox, oy)。
    search=(2,2)、coarse_step=2 時粗找 9 點 + 細找 9 點，涵蓋全部 25 個位移"""
    _, bx, by = coarse_pos(tpl, cells, ex, ey, search, tol, coarse_step, coarse_stride, max(1, min_n // coarse_stride))
    fine = (-1.0, bx, by)
    for oy in range(by - 1, by + 2):
        for ox in range(bx - 1, bx + 2):
            s, _ = score(tpl, cells, ox, oy, tol, 1, min_n)
            if s > fine[0]:
                fine = (s, ox, oy)
    return fine


# ---- 第二關：前兩名太近時投票 ----
TIE_GOOD = 60       # 有效票：畫面點至少跟其中一個樣板很像（三通道差總和 ≤ 60）
TIE_GAP = 60        #         且兩個樣板對它的差距相差 ≥ 60（分得出是誰）
TIE_MIN_PTS = 12    # 有效票至少這麼多
TIE_RATIO = 0.7     # 贏家得票比例 ≥ 這個值才判定


def tiebreak(cells: dict, ta: dict, tb: dict, good: int = TIE_GOOD, gap: int = TIE_GAP,
             min_pts: int = TIE_MIN_PTS, ratio: float = TIE_RATIO) -> dict:
    """ta / tb = placed() 後的兩個樣板。每個畫面點「明顯比較像誰」就投給誰。
    → {'winner': 0（a）/ 1（b）/ None, 'votes': [a 票, b 票]}"""
    va = vb = 0
    for q, c in cells.items():
        ca, cb = ta.get(q), tb.get(q)
        if ca is None or cb is None:
            continue
        da = abs(c[0] - ca[0]) + abs(c[1] - ca[1]) + abs(c[2] - ca[2])
        db = abs(c[0] - cb[0]) + abs(c[1] - cb[1]) + abs(c[2] - cb[2])
        if min(da, db) > good or abs(da - db) < gap:
            continue
        if da < db:
            va += 1
        else:
            vb += 1
    n = va + vb
    win = None
    if n >= min_pts:
        if va / n >= ratio:
            win = 0
        elif vb / n >= ratio:
            win = 1
    return {'winner': win, 'votes': [va, vb]}


# ---- 粗樣板磁碟快取 ----
def _pack(d: dict) -> bytes:
    blob = bytearray()
    for key, pts in d.items():
        b = str(key).encode()
        blob += bytes([len(b)]) + b + struct.pack('<H', len(pts))
        for t in pts:
            blob += struct.pack('<bbBBB', *t)
    return bytes(blob)


def _unpack(body: bytes) -> dict:
    out, pos = {}, 0
    while pos < len(body):
        ln = body[pos]
        key = body[pos + 1:pos + 1 + ln].decode()
        n = struct.unpack_from('<H', body, pos + 1 + ln)[0]
        pos += 3 + ln
        out[key] = list(struct.iter_unpack('<bbBBB', body[pos:pos + 5 * n]))
        pos += 5 * n
    return out


def coarse_cache(path, stamp: str, keys, builder) -> dict:
    """{key: 粗樣板} 的磁碟快取（zlib）。檔頭戳記 = stamp 且 key 集合相同才用快取；否則 builder(key) 逐一重算並寫回
    （寫不進去不算錯）。樣板 dx/dy 必須在 -128～127、key 長度 < 256"""
    keys = [str(k) for k in keys]
    path = Path(path)
    st = stamp.encode()
    try:
        raw = zlib.decompress(path.read_bytes())
        head, body = raw.split(b'\n', 1)
        if head == st:
            out = _unpack(body)
            if set(out) == set(keys):
                return out
    except (OSError, ValueError, zlib.error, struct.error):
        pass
    out = {k: builder(k) for k in keys}
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(zlib.compress(st + b'\n' + _pack(out)))
    except OSError:
        pass
    return out
