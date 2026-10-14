#!/usr/bin/env python3
"""圖示 ↔ 畫面像素比對的共用核心（純函式、只用標準函式庫）。2026-10-14 階段 2（notes/plan-item-icon-match.md）；
同日階段 6：petimg_match.py（寵物格 / 倉庫卡）也改用本模組，道具與寵物共用同一套核心。

使用者：itemimg_match.py（道具格：背包 / 倉庫）、petimg_match.py（寵物格 / 倉庫卡）。
  1. 樣板：Sprite 依倍率縮成截圖格點，只取 alpha ≥ alpha_min 的不透明點 → [(dx, dy, r, g, b)]（相對 Sprite 中心）。
  2. 分數：樣板放在 (ox, oy) 時，不透明點中「與畫面三通道差總和 ≤ 3×tol」的比例（inlier 比例；被遮掉 / 讀不到的點不算分母）。
  3. 位置：期望中心附近先粗找（位移步 coarse_step、樣板每 coarse_stride 點取 1）再細找（全點、±1）。
  4. 判定 classify：第一名 ≥ 門檻且與第二名（不同 group）差 ≥ margin；前兩名都過門檻但太近 → tiebreak（只看兩樣板顏色差很大的點投票）。
  5. 候選內相對比較 rank_among：逐點 inlier + 主色直方圖（color_score）都同意才判定，分差不夠再 tiebreak（換色版：卡坦鯊 / 雞）。
  6. 遮擋偵測 occlusion / covered_rows / keep_rows：格子外圍「本來是固定底色」的點被浮動 EXP 橫幅 / 半透明遮罩壓暗 → 點數 ≥ 門檻 = 被蓋住，呼叫端不硬認、等它消失重讀。
     取點 / 判斷式由呼叫端給（背包格、寵物格、倉庫卡各一套）；dimmed_beige 是寵物面板米色底被壓暗的共用判斷式。
     區塊比對（2026-10-14）：covered_rows 找出被蓋住的列、keep_rows 只留沒蓋住的列再比（寵物 judge 被蓋住時的退路，門檻較嚴）；
     道具格離線評估後不用（只比下半時不在候選的圖冒充變多，見 ui/bag.md）。
  7. 大量樣板的粗篩快取：coarse_cache 把 {key: 粗樣板} 壓縮存到磁碟，戳記不符自動重算。

本模組不讀任何遊戲畫面、不知道版面；版面（倍率 / 中心偏移 / 遮罩 / 遮擋取點）由呼叫端決定。
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


# ---- 畫面格（加速用）----
class Grid(dict):
    """{(x, y): rgb} 再附一份平面陣列（score 用索引取點、不建 tuple 鍵，約快 2 倍；結果與 dict 完全相同）。
    其他函式（tiebreak / color_score / placed 比對）照舊當 dict 用"""

    def __init__(self, d: dict):
        super().__init__(d)
        if d:
            xs = [q[0] for q in d]
            ys = [q[1] for q in d]
            self.x0, self.y0 = min(xs), min(ys)
            self.w, self.h = max(xs) - self.x0 + 1, max(ys) - self.y0 + 1
        else:
            self.x0 = self.y0 = 0
            self.w = self.h = 0
        flat = [None] * (self.w * self.h)
        for (x, y), c in d.items():
            flat[(y - self.y0) * self.w + (x - self.x0)] = c
        self.flat = flat


# ---- 分數 / 位置 ----
def score(tpl, cells: dict, ox: int, oy: int, tol: int = TOL, step: int = 1, min_n: int = MIN_N):
    """樣板放在 (ox, oy) 的 inlier 比例 → (比例, 有效點數)；有效點 < min_n → 0.0。cells 是 Grid 時走平面陣列（結果相同）"""
    lim = 3 * tol
    hit = n = 0
    if isinstance(cells, Grid):
        flat, w, h = cells.flat, cells.w, cells.h
        bx, by = ox - cells.x0, oy - cells.y0
        for dx, dy, r, gg, b in (tpl[::step] if step > 1 else tpl):
            x, y = bx + dx, by + dy
            if x < 0 or y < 0 or x >= w or y >= h:
                continue
            c = flat[y * w + x]
            if c is None:
                continue
            n += 1
            if abs(c[0] - r) + abs(c[1] - gg) + abs(c[2] - b) <= lim:
                hit += 1
        return (hit / n if n >= min_n else 0.0), n
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
             min_n: int = MIN_N, coarse_min_n: int | None = None):
    """粗找（coarse_pos）→ 細找（全點、粗找最佳位置 ±1）→ (分數, ox, oy)。
    search=(2,2)、coarse_step=2 時粗找 9 點 + 細找 9 點，涵蓋全部 25 個位移。
    coarse_min_n = 粗找的有效點下限（預設 min_n // coarse_stride；petimg 沿用舊值 40）"""
    cmin = max(1, min_n // coarse_stride) if coarse_min_n is None else coarse_min_n
    _, bx, by = coarse_pos(tpl, cells, ex, ey, search, tol, coarse_step, coarse_stride, cmin)
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


def classify(cells: dict, ranked, tpl_of, min_score: float, margin: float, group=None, gate: bool = True) -> dict:
    """前兩名判定（道具 identify、寵物 match 共用）。ranked = [(分數, key, (s, ox, oy))]（分數高到低）；tpl_of(key) → 樣板；
    group(key) → 比較鍵（第二名取「不同 group」裡最高的；None = key 本身）；gate=False（例：被遮擋）→ 不判定也不投票。
    → {'ok', 'top': (s, key, pos), 'second': (s, key, pos)（沒有 = (0.0, None, None)）, 'tie': tiebreak 結果或 None}"""
    grp = group or (lambda k: k)
    top = ranked[0]
    gk = grp(top[1])
    sec = next((r for r in ranked[1:] if grp(r[1]) != gk), (0.0, None, None))
    ok = gate and top[0] >= min_score and top[0] - sec[0] >= margin
    tie = None
    if gate and not ok and sec[1] is not None and min(top[0], sec[0]) >= min_score:
        t = tiebreak(cells, placed(tpl_of(top[1]), top[2][1], top[2][2]), placed(tpl_of(sec[1]), sec[2][1], sec[2][2]))
        tie = {'winner': (top[1], sec[1])[t['winner']] if t['winner'] is not None else None, 'votes': t['votes']}
        if t['winner'] is not None:
            ok = True
            if t['winner'] == 1:
                top, sec = sec, top
    return {'ok': ok, 'top': top, 'second': sec, 'tie': tie}


# ---- 主色直方圖（換色版：同輪廓不同配色，逐點 inlier 分差小、主色分得開）----
HIST_LEVELS = 4     # 每通道量化成 4 級（64 格）


def _q(c, levels: int = HIST_LEVELS) -> tuple:
    return tuple(min(levels - 1, v * levels // 256) for v in c)


def color_score(cells: dict, tpl, pos, levels: int = HIST_LEVELS) -> float:
    """樣板放在 pos=(s, ox, oy)：「樣板不透明點的顏色分布」與「畫面同位置的顏色分布」的量化直方圖交集（0～1）"""
    from collections import Counter
    _, ox, oy = pos
    ht, hc = Counter(), Counter()
    g = cells.get
    for dx, dy, r, gg, b in tpl:
        c = g((ox + dx, oy + dy))
        if c is None:
            continue
        ht[_q((r, gg, b), levels)] += 1
        hc[_q(c, levels)] += 1
    n = sum(ht.values())
    return sum(min(ht[k], hc[k]) for k in ht) / n if n else 0.0


def rank_among(cells: dict, keys, tpl_of, ex: int, ey: int, search, min_score: float, rel_margin: float,
               hist_margin: float, group=None, tol: int = TOL, coarse_min_n: int | None = None, memo: dict | None = None) -> dict:
    """候選內相對比較：每個 key 找最佳位置 → 逐點 inlier 分數 + 主色分數。兩個特徵都要同意才 ok：
    ① inlier 第一名 ≥ min_score 且與第二名（不同 group）差 ≥ rel_margin；② 主色第一名同 group、且與主色第二名（不同 group）差 ≥ hist_margin。
    兩特徵方向一致、只差分差不夠 → 第三關 tiebreak（贏家要是同一個）。
    memo = {key: (pos, 主色分數)}：同一格分兩輪比（先候選、再加同系別）時共用，已算過的 key 不重算。
    → {'ok', 'top': (s, key), 'second': (s, key|None), 'hist', 'hist_second', 'hist_best', 'tie', 'sc': {key: (s, h)}, 'pos': {key: pos}}"""
    grp = group or (lambda k: k)
    sc, pos_of = {}, {}
    memo = {} if memo is None else memo
    for k in keys:
        if k not in memo:
            tpl = tpl_of(k)
            p = best_pos(tpl, cells, ex, ey, search, tol, coarse_min_n=coarse_min_n)
            memo[k] = (p, color_score(cells, tpl, p))
        p, h = memo[k]
        sc[k] = (p[0], h)
        pos_of[k] = p
    ranked = sorted(((v[0], k) for k, v in sc.items()), reverse=True)
    top_s, top_k = ranked[0]
    tg = grp(top_k)
    sec_s, sec_k = next(((s_, k) for s_, k in ranked[1:] if grp(k) != tg), (0.0, None))
    hr = sorted(((v[1], k) for k, v in sc.items()), reverse=True)
    h_top = hr[0][1]
    h_sec = next((h for h, k in hr[1:] if grp(k) != grp(h_top)), 0.0)
    agree = top_s >= min_score and grp(h_top) == tg
    ok = agree and top_s - sec_s >= rel_margin and sc[top_k][1] - h_sec >= hist_margin
    tie = None
    if agree and not ok and sec_k is not None:
        t = tiebreak(cells, placed(tpl_of(top_k), pos_of[top_k][1], pos_of[top_k][2]),
                     placed(tpl_of(sec_k), pos_of[sec_k][1], pos_of[sec_k][2]))
        tie = {'winner': (top_k, sec_k)[t['winner']] if t['winner'] is not None else None, 'votes': t['votes']}
        ok = tie['winner'] == top_k
    return {'ok': ok, 'top': (top_s, top_k), 'second': (sec_s, sec_k), 'hist': sc[top_k][1], 'hist_second': h_sec,
            'hist_best': h_top, 'tie': tie, 'sc': sc, 'pos': pos_of, 'ranked': ranked}


# ---- 遮擋偵測（浮動「獲得 EXP」橫幅 / 半透明遮罩）----
def occlusion(get, cx: int, cy: int, pts, pred) -> int:
    """格子外圍取點 pts（相對格心 [(dx, dy)]，那些點本來是固定底色）中 pred(rgb) 成立（= 被壓暗）的點數。
    讀不到的點不算。門檻由呼叫端定（道具背包格 ≥ 15、寵物格 / 倉庫卡見 petimg_match.OCC_MIN）"""
    get = as_getter(get)
    n = 0
    for dx, dy in pts:
        c = get(cx + dx, cy + dy)
        if c is not None and pred(c):
            n += 1
    return n


def covered_rows(get, cx: int, cy: int, pts, pred, pad: int) -> set:
    """遮擋取點 pts（相對格心）中 pred 成立（被壓暗）的點 → 被橫幅蓋住的列（相對格心的 dy，各 ±pad）。
    浮字橫幅是一條橫帶：取點在格子左右兩側每隔幾列一點，pad 補上取點之間的列"""
    get = as_getter(get)
    bad = set()
    for dx, dy in pts:
        c = get(cx + dx, cy + dy)
        if c is not None and pred(c):
            bad.update(range(dy - pad, dy + pad + 1))
    return bad


def keep_rows(cells: dict, cy: int, drop=(), y_min=None, y_max=None):
    """區塊比對（只比部分列）：丟掉 dy（相對格心 cy）在 drop 裡、或 < y_min、或 > y_max 的點 → Grid。
    樣板落在被丟掉的點上不算分母（score 只數讀得到的點），所以等於只用剩下的列比對。
    離線評估（2026-10-14，notes 見 ui/pet.md「區塊比對」）：沒被蓋住時只比下半會讓易混組分差變小、不在候選的冒充變多 → 只當被蓋住時的退路"""
    drop = set(drop)
    return Grid({q: c for q, c in cells.items() if (q[1] - cy) not in drop
                 and (y_min is None or q[1] - cy >= y_min) and (y_max is None or q[1] - cy <= y_max)})


def dimmed_beige(c) -> bool:
    """寵物面板米色底（約 (216～248, 191～233, 158～200)）被半透明深色橫幅壓暗後的顏色：灰棕、平均 70～165、r ≥ g ≥ b、r−b ≤ 60。
    正常米色（平均 ≥ 185）、選取黃框（r−b ≈ 200）、頭像本身不在取點範圍 → 不算"""
    r, g, b = c[0], c[1], c[2]
    m = (r + g + b) / 3
    return 70 <= m <= 165 and r >= g >= b and r - b <= 60


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
