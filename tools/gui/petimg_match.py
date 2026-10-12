#!/usr/bin/env python3
"""寵物縮圖 ↔ 知識庫頭像的像素比對（認物種；只用標準函式庫）。2026-10-12 離線設計 + 驗證；同日接線到 pet.py（img_ident：名字 / 登錄檔都認不出時的備援），實機唯讀 list 驗證寵物格。

為什麼：沒名字的新寵物（名字框顯示成長字串 49/9/8/2）認物種要靠 learn-species 先登錄，而且成長字串會撞
（48/9/5/3 兩個物種相同）。寵物面板每格縮圖、倉庫卡縮圖畫的就是 Monster.imageId 的頭像 Sprite
（tools/extract/pet_images.py 匯出到 tools/.cache/pet-images/head/），所以可以直接拿頭像比像素認物種，不用先登錄。

版面（2880×1659 客戶區 = 1440×830 截圖座標；catch-m0 / at_* / bn_* 等 217 張寵物面板截圖量的）：
  寵物欄格（pet.SLOT_X=250、SLOT_Y=200/322/445/567/690）：頭像以約 1.05 倍（截圖 px / Sprite px）畫在格心偏右下 (+6,+2)；
    左上紅色狀態標（騎乘 / 等待 / 戰鬥）、右下白字等級、選中時外框橘光 → 遮掉不比。
  倉庫卡（pet.CARD_X / CARD_Y，5×4）：**倉庫卡有縮圖**（同一張頭像），約 1.26 倍、格心 (+5,+1)；
    上方白字名字 / 成長字串（y < 格心−25）、下方綠字「0轉N級」（y > 格心+25）→ 只丟字本身的像素（白 / 綠 / 深色描邊），
    字縫間照比（火雞系的冠毛就在名字那一條：克克洛斯 黃冠 / 奇寶 紅冠只差在這裡）。
  頭像 PNG 是 UnityPy 裁過透明邊的（高多半 80、寬 66～80 不一），裁切偏移量沒匯出 → 每個物種都在格心附近 ±8 / ±4 px 內找最佳位置。

比對法：
  1. 頭像依倍率縮成截圖格點的樣板（只取 alpha ≥ 250 的不透明點）。
  2. 每個候選在位移視窗內先粗找（樣板每 3 點取 1、位移步 2）再細找（全點、±1）：
     分數 = 不透明點中「與畫面每通道平均差 ≤ TOL」的比例（inlier 比例，對狀態標 / 數字 / 光暈等殘留遮擋穩健）。
  3. 同 imageId 的多筆 Monster（例：火雞 190～193、346、685…）視為同一物種，只比一次。
  4. 最佳分數 < MIN_SCORE[kind] 或與第二名（**不同物種**；「2D」版頭像算同物種）差 < MARGIN → 回 None，不猜。
  5. 前兩名分差不夠但都過門檻 → 第二關 _tiebreak：只看兩樣板顏色明顯不同的點投票（≥ TIE_MIN_PTS 點、贏家 ≥ TIE_RATIO）才判定，否則 None。
  6. 候選集：呼叫端給這次任務需要的物種名 + --family（同系別換色版，避免「只給一隻」時兄弟物種也過門檻）；
     不給就是全部 Monster。候選 > SHORTLIST 時先粗比對留 SHORTLIST 個再細比。

用法（專案根目錄；WSL / Windows 原生相同）：
  uv run --no-project python tools/gui/petimg_match.py shot <截圖.png> [--names 火雞,奇寶,...] [--family] [--json]   # 離線：截圖裡每個非空格 / 倉庫卡
  uv run --no-project python tools/gui/petimg_match.py live slot 3 [--names ...]                         # 唯讀：經 uikit.px 讀現場（寵物格 4537 點約 0.2 s）
程式介面：
  match(get, kind, cx, cy, names=None) → {'species', 'imageId', 'score', 'second', 'second_species', 'ok', 'tie', 'ranked'}；
    get(x, y) → (r,g,b)（截圖座標）；ok=False 時 species=None（不猜）。
  match_rows(rows, bpp, kind, cx, cy, names) → 同上（PNG 解碼列）。read_cell(kind, cx, cy) → dict（經 uikit.px，一次讀整格）。
  family(names) → 同系別（Monster.petType）全部有頭像的物種名。cells_of(kind) → [(格號, cx, cy)]。is_empty(get, cx, cy) → 空格（爪印）。
"""
import argparse
import json
import sys
import struct
import time
import zlib
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import pngread  # noqa: E402

ROOT = HERE.parents[1]
IMG_DIR = ROOT / 'tools' / '.cache' / 'pet-images'
LAYOUT = '2880x1659'

# ---- 版面（截圖座標；cx, cy = pet.py 的格心）----
# scale：截圖 px / 頭像 px；center：頭像中心相對格心；search：位移搜尋半徑 (dx, dy)
# clip：縮圖可見範圍（相對格心）；mask(dx, dy) → True = 遮掉（狀態標 / 等級字 / 名字字串）
KINDS = {
    'slot': {'scale': 1.05, 'center': (6, 2), 'search': (8, 4), 'clip': (-42, -44, 42, 44),
             'mask': lambda dx, dy: (dx + 50) + (dy + 52) < 75 or (dx > 5 and dy > 10)},
    'card': {'scale': 1.26, 'center': (5, 1), 'search': (8, 4), 'clip': (-45, -45, 45, 45),
             'mask': lambda dx, dy: False},
}


def _text_px(kind: str, dx: int, dy: int, c) -> bool:
    """倉庫卡上下兩條字（上：白字名字 / 成長字串，下：綠字「0轉N級」，都有深色描邊）→ 只丟字的像素，字縫間的頭像照比
    （整條遮掉會把火雞類的冠毛遮光：克克洛斯 黃冠 / 奇寶 紅冠只差在這裡）"""
    if kind != 'card' or -25 <= dy <= 25:
        return False
    r, g, b = c
    if r + g + b < 150:                                  # 描邊
        return True
    if dy < -25:
        return min(r, g, b) > 200                        # 白字
    return g > 170 and r < 170 and b < 140               # 綠字


SLOT_X, SLOT_Y = 250, [200, 322, 445, 567, 690]          # 同 pet.SLOT_X / SLOT_Y（不 import pet：它正被改動，且很重）
CARD_X, CARD_Y = [818, 924, 1030, 1136, 1242], [275, 381, 488, 594]
PAW = [(0, 2, (155, 123, 82)), (0, -5, (179, 145, 98)), (-20, 15, (179, 145, 98)), (20, -15, (155, 122, 82))]   # 空格爪印（同 pet.PAW）
PAW_TOL = 14

TOL = 40            # 每點平均通道差 ≤ TOL 算吻合
ALPHA_MIN = 250
MIN_SCORE = {'slot': 0.70, 'card': 0.55}   # 最佳分數門檻（離線實測對的：寵物格 ≥ 0.84、倉庫卡 ≥ 0.57；不在候選的寵物格最高 0.555）
MARGIN = 0.08       # 與第二名（不同物種）至少差這麼多
SHORTLIST = 8       # 候選多於這個數（--family / 全部 Monster）時，先粗比對（位移步 4、樣板每 10 點取 1）留這麼多個再細比
TIE_MIN_PTS = 12    # 前兩名分差不夠時的第二關投票：有效票至少這麼多
TIE_GOOD = 60       # 有效票：畫面點至少跟其中一個樣板很像（三通道差總和 ≤ 60）
TIE_GAP = 60        #         且兩個樣板對它的差距相差 ≥ 60（分得出是誰）
TIE_RATIO = 0.7     # 贏家得票比例 ≥ 這個值才判定；否則仍 None（倉庫卡 克克洛斯 0.82～0.90、奇寶 0.62～0.85，後者 3/17 不判）

_INDEX = None       # imageId → [名字...]（index.tsv 順序）
_HEAD = {}          # imageId → head 檔名
_TPL = {}           # (imageId, kind) → 樣板點 [(dx, dy, r, g, b)]（相對頭像中心，已乘倍率）
_COARSE = {}        # kind → {imageId: 粗樣板}（全部 Monster 模式粗篩用；磁碟快取見 coarse_templates）
COARSE_DIR = ROOT / 'tools' / '.cache'
COARSE_STRIDE = 10


# ---- 知識庫頭像 ----
def index() -> dict:
    """讀 pet-images/index.tsv → {imageId: [繁中名…]}；沒匯出就丟 FileNotFoundError（請先跑 tools/extract/pet_images.py）"""
    global _INDEX
    if _INDEX is None:
        idx = {}
        lines = (IMG_DIR / 'index.tsv').read_text(encoding='utf-8').splitlines()[1:]
        for ln in lines:
            c = ln.split('\t')
            if len(c) < 6 or not c[5]:
                continue
            idx.setdefault(c[4], [])
            if c[1] not in idx[c[4]]:
                idx[c[4]].append(c[1])
            _HEAD.setdefault(c[4], c[5])
        _INDEX = idx
    return _INDEX


def species_name(iid: str) -> str:
    return index()[iid][0]


def species_key(name: str) -> str:
    """物種比較鍵：「2D貝魯卡」與「貝魯卡」是同一隻的兩版頭像（不同 imageId、圖幾乎相同）→ 同一物種"""
    return name[2:] if name.startswith('2D') else name


def ids_for(names) -> list:
    """物種名（繁中，完全相同）→ imageId 清單（同名多個 imageId 全收；同 imageId 合併）。找不到的名字丟 KeyError"""
    idx = index()
    out = []
    for n in names:
        hit = [iid for iid, ns in idx.items() if n in ns]
        if not hit:
            raise KeyError(f'知識庫頭像找不到「{n}」')
        out += [i for i in hit if i not in out]
    return out


def family(names) -> list:
    """同系別（Monster.petType 相同，例：鯊魚系 12、火雞系 25）且有頭像的全部物種名；含原本的名字。
    接線時的建議候選集：只給「要找的那一隻」會讓同系的換色版也過門檻（克克洛斯 對 [奇寶] 單獨比 0.76），
    所以至少要把同系的換色版一起放進來，讓分差 / 第二關去分辨。petType 100（敵方 / NPC）不算一系"""
    types, by_type = set(), {}
    with open(ROOT / 'knowledge' / 'data' / 'tables' / 'Monster.jsonl', encoding='utf-8') as f:
        for ln in f:
            r = json.loads(ln)
            n, t = r.get('nameTn') or '', r.get('petType')
            by_type.setdefault(t, set()).add(n)
            if n in names and t != 100:
                types.add(t)
    have = {n for ns in index().values() for n in ns}
    out = list(dict.fromkeys(names))
    for t in sorted(types):
        out += sorted(n for n in by_type[t] if n in have and n not in out)
    return out


def template(iid: str, kind: str) -> list:
    """頭像縮成截圖格點的樣板：[(dx, dy, r, g, b)]，dx/dy 相對頭像中心（截圖 px，整數）；只取不透明點"""
    key = (iid, kind)
    if key in _TPL:
        return _TPL[key]
    index()
    w, h, bpp, rows = pngread.decode((IMG_DIR / 'head' / _HEAD[iid]).read_bytes())
    s = KINDS[kind]['scale']
    tw, th = int(w * s), int(h * s)
    pts = []
    for ty in range(th):
        sy = min(h - 1, int((ty + 0.5) / s))
        for tx in range(tw):
            sx = min(w - 1, int((tx + 0.5) / s))
            p = rows[sy][sx * bpp:sx * bpp + bpp]
            if bpp == 4 and p[3] < ALPHA_MIN:
                continue
            pts.append((tx - tw // 2, ty - th // 2, p[0], p[1], p[2]))
    _TPL[key] = pts
    return pts


def coarse_templates(kind: str) -> dict:
    """全部頭像的粗樣板 {imageId: [(dx,dy,r,g,b)]}（樣板每 COARSE_STRIDE 點取 1）；全部 Monster 模式粗篩用。
    第一次要解碼 1000+ 張頭像（約 10 s），之後讀快取 tools/.cache/petimg-coarse-<kind>.bin（index.tsv 或倍率變了自動重算）"""
    if kind in _COARSE:
        return _COARSE[kind]
    stamp = f"{(IMG_DIR / 'index.tsv').stat().st_mtime_ns}:{KINDS[kind]['scale']}:{COARSE_STRIDE}".encode()
    path = COARSE_DIR / f'petimg-coarse-{kind}.bin'
    out = None
    try:
        raw = zlib.decompress(path.read_bytes())
        head, body = raw.split(b'\n', 1)
        if head == stamp:
            out, pos = {}, 0
            while pos < len(body):
                ln = body[pos]
                iid = body[pos + 1:pos + 1 + ln].decode()
                n = struct.unpack_from('<H', body, pos + 1 + ln)[0]
                pos += 3 + ln
                out[iid] = list(struct.iter_unpack('<bbBBB', body[pos:pos + 5 * n]))
                pos += 5 * n
    except (OSError, ValueError, zlib.error, struct.error):
        out = None
    if out is None or set(out) != set(index()):
        out = {i: template(i, kind)[::COARSE_STRIDE] for i in index()}
        blob = bytearray()
        for iid, pts in out.items():
            b = iid.encode()
            blob += bytes([len(b)]) + b + struct.pack('<H', len(pts))
            for t in pts:
                blob += struct.pack('<bbBBB', *t)
        try:
            path.write_bytes(zlib.compress(stamp + b'\n' + bytes(blob)))
        except OSError:
            pass
    _COARSE[kind] = out
    return out


# ---- 比對 ----
def cell_points(kind: str, cx: int, cy: int) -> list:
    """一格要讀的點（可見範圍、去掉遮罩），截圖座標"""
    k = KINDS[kind]
    x0, y0, x1, y1 = k['clip']
    return [(cx + dx, cy + dy) for dy in range(y0, y1 + 1) for dx in range(x0, x1 + 1) if not k['mask'](dx, dy)]


def _score(tpl, get_d, ox, oy, step):
    """樣板放在 (ox, oy)（頭像中心的截圖座標）的 inlier 比例；get_d = {(x,y): rgb}（已去遮罩 / 可見範圍）"""
    hit = n = 0
    for i in range(0, len(tpl), step):
        dx, dy, r, g, b = tpl[i]
        c = get_d.get((ox + dx, oy + dy))
        if c is None:
            continue
        n += 1
        if abs(c[0] - r) + abs(c[1] - g) + abs(c[2] - b) <= 3 * TOL:
            hit += 1
    return (hit / n if n >= 40 else 0.0), n


def _coarse_score(tpl, cells, kind, cx, cy, step=4, stride=1):
    """位移步 step 的粗找 → (最佳分數, ox, oy)"""
    k = KINDS[kind]
    ex, ey = cx + k['center'][0], cy + k['center'][1]
    sx, sy = k['search']
    best = (-1.0, ex, ey)
    for oy in range(ey - sy, ey + sy + 1, step):
        for ox in range(ex - sx, ex + sx + 1, step):
            s, _ = _score(tpl, cells, ox, oy, stride)
            if s > best[0]:
                best = (s, ox, oy)
    return best


def _best_pos(tpl, cells, kind, cx, cy):
    k = KINDS[kind]
    ex, ey = cx + k['center'][0], cy + k['center'][1]
    sx, sy = k['search']
    best = (-1.0, ex, ey)
    for oy in range(ey - sy, ey + sy + 1, 2):
        for ox in range(ex - sx, ex + sx + 1, 2):
            s, _ = _score(tpl, cells, ox, oy, 3)
            if s > best[0]:
                best = (s, ox, oy)
    _, bx, by = best
    fine = (-1.0, bx, by)
    for oy in range(by - 1, by + 2):
        for ox in range(bx - 1, bx + 2):
            s, _ = _score(tpl, cells, ox, oy, 1)
            if s > fine[0]:
                fine = (s, ox, oy)
    return fine


def match(get, kind: str, cx: int, cy: int, names=None) -> dict:
    """get(x, y) → (r,g,b) 截圖座標（或 dict）；names = 候選物種名（None = 全部 Monster，先直方圖粗篩）。
    → {'species', 'imageId', 'score', 'second', 'second_species', 'ok', 'ranked'}；ok=False 時 species / imageId = None"""
    pts = cell_points(kind, cx, cy)
    cells = get if isinstance(get, dict) else {p: tuple(get(*p)) for p in pts}
    cells = {p: cells[p] for p in pts if p in cells and not _text_px(kind, p[0] - cx, p[1] - cy, cells[p])}
    ids = ids_for(names) if names else list(index())
    if len(ids) > SHORTLIST:
        co = coarse_templates(kind) if not names else {i: template(i, kind)[::COARSE_STRIDE] for i in ids}
        ids = sorted(ids, key=lambda i: _coarse_score(co[i], cells, kind, cx, cy)[0], reverse=True)[:SHORTLIST]
    pos = {i: _best_pos(template(i, kind), cells, kind, cx, cy) for i in ids}
    ranked = sorted(((p[0], i) for i, p in pos.items()), reverse=True)
    top_s, top_i = ranked[0]
    top_k = species_key(species_name(top_i))
    # 第二名 = 「不同物種」裡最高的（同 imageId 已合併；2D 版視為同物種）
    sec_s, sec_i = next(((sc, i) for sc, i in ranked[1:] if species_key(species_name(i)) != top_k), (0.0, None))
    ok = top_s >= MIN_SCORE[kind] and top_s - sec_s >= MARGIN
    tie = None
    if not ok and sec_i and min(top_s, sec_s) >= MIN_SCORE[kind]:
        tie = _tiebreak(cells, kind, (top_i, pos[top_i]), (sec_i, pos[sec_i]))
        if tie['winner'] is not None:
            ok = True
            if tie['winner'] == sec_i:
                top_s, top_i, sec_s, sec_i = sec_s, sec_i, top_s, top_i
    return {'species': species_name(top_i) if ok else None, 'imageId': top_i if ok else None,
            'best_species': species_name(top_i), 'score': round(top_s, 3), 'second': round(sec_s, 3),
            'second_species': species_name(sec_i) if sec_i else None, 'ok': ok, 'tie': tie,
            'ranked': [(species_name(i), round(s, 3)) for s, i in ranked[:5]]}


def _tiebreak(cells, kind, a, b) -> dict:
    """前兩名（不同物種）分數太近時的第二關：兩個樣板各放在自己的最佳位置，每個畫面點「明顯比較像誰」就投給誰
    （至少像其中一個 TIE_GOOD、兩邊差距 ≥ TIE_GAP 才算票）。例：倉庫卡上 克克洛斯（黃冠）/ 奇寶（紅冠）只差在被名字字串蓋住一半的冠毛。
    → {'winner': imageId 或 None, 'votes': [a 票, b 票]}"""
    def placed(iid, p):
        _, ox, oy = p
        return {(ox + dx, oy + dy): (r, g, bb) for dx, dy, r, g, bb in template(iid, kind)}
    ta, tb = placed(*a), placed(*b)
    va = vb = 0
    for q, c in cells.items():
        ca, cb = ta.get(q), tb.get(q)
        if ca is None or cb is None:
            continue
        da, db = sum(abs(x - y) for x, y in zip(c, ca)), sum(abs(x - y) for x, y in zip(c, cb))
        if min(da, db) > TIE_GOOD or abs(da - db) < TIE_GAP:
            continue
        if da < db:
            va += 1
        else:
            vb += 1
    n = va + vb
    win = None
    if n >= TIE_MIN_PTS:
        if va / n >= TIE_RATIO:
            win = a[0]
        elif vb / n >= TIE_RATIO:
            win = b[0]
    return {'winner': win, 'votes': [va, vb]}


def rows_getter(rows, bpp: int):
    return lambda x, y: tuple(rows[y][x * bpp:x * bpp + 3])


def match_rows(rows, bpp: int, kind: str, cx: int, cy: int, names=None) -> dict:
    return match(rows_getter(rows, bpp), kind, cx, cy, names)


def is_empty(get, cx: int, cy: int) -> bool:
    return all(all(abs(a - b) <= PAW_TOL for a, b in zip(get(cx + dx, cy + dy), c)) for dx, dy, c in PAW)


def cells_of(kind: str) -> list:
    """kind 的全部格心 [(index 1 起, cx, cy)]"""
    if kind == 'slot':
        return [(i + 1, SLOT_X, y) for i, y in enumerate(SLOT_Y)]
    return [(i + 1, CARD_X[i % 5], CARD_Y[i // 5]) for i in range(20)]


def read_cell(kind: str, cx: int, cy: int):
    """現場讀一格（唯讀，經 uikit.px 一次讀完；寵物格 4537 點，常駐 server 約 0.2 s，2026-10-12 實機）→ dict 可直接餵 match；讀不到 None"""
    import uikit
    pts = cell_points(kind, cx, cy)
    cols = uikit.px(pts)
    return dict(zip(pts, cols)) if cols else None


def is_depot(get) -> bool:
    """倉庫分頁特徵（同 pet.DEPOT_SIG：擴容藍鈕兩點）"""
    return all(all(abs(a - b) <= 24 for a, b in zip(get(x, y), c)) for x, y, c in
               [(1195, 690, (68, 112, 167)), (1215, 720, (72, 120, 179))])


def scan_shot(path, names=None) -> list:
    """離線：一張 1440×830 截圖裡全部非空寵物格（+ 倉庫分頁時的倉庫卡）→ [{kind, index, ...match}]"""
    w, h, bpp, rows = pngread.decode(Path(path).read_bytes())
    get = rows_getter(rows, bpp)
    kinds = ['slot'] + (['card'] if is_depot(get) else [])
    out = []
    for kind in kinds:
        for i, cx, cy in cells_of(kind):
            if is_empty(get, cx, cy):
                continue
            t = time.time()
            r = match(get, kind, cx, cy, names)
            r.update(kind=kind, index=i, ms=round((time.time() - t) * 1000))
            out.append(r)
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description='寵物縮圖 ↔ 知識庫頭像比對（認物種）')
    sub = ap.add_subparsers(dest='cmd', required=True)
    a = sub.add_parser('shot')
    a.add_argument('png')
    b = sub.add_parser('live')
    b.add_argument('kind', choices=['slot', 'card'])
    b.add_argument('index', type=int)
    for p in (a, b):
        p.add_argument('--names', default='', help='候選物種（逗號分隔）；不給 = 全部 Monster（慢，每格約 3 s）')
        p.add_argument('--family', action='store_true', help='候選擴大到同系別（petType）全部物種')
        p.add_argument('--json', action='store_true')
    args = ap.parse_args(argv)
    names = [n for n in args.names.split(',') if n] or None
    if names and args.family:
        names = family(names)
    if args.cmd == 'shot':
        res = scan_shot(args.png, names)
    else:
        _, cx, cy = cells_of(args.kind)[args.index - 1]
        cells = read_cell(args.kind, cx, cy)
        if cells is None:
            print(json.dumps({'ok': False, 'rc': 1, 'msg': '讀不到像素'}, ensure_ascii=False))
            return 1
        res = [dict(match(cells, args.kind, cx, cy, names), kind=args.kind, index=args.index)]
    if not args.json:
        for r in res:
            print(f"{r['kind']}{r['index']:>3}  {r['species'] or '?(' + r['best_species'] + ')'}  "
                  f"{r['score']:.3f} / 第二 {r['second_species']} {r['second']:.3f}  {r.get('ms', '')}ms")
    print(json.dumps({'ok': True, 'rc': 0, 'cells': [{k: v for k, v in r.items() if k != 'ranked'} for r in res]},
                     ensure_ascii=False))
    return 0


if __name__ == '__main__':
    sys.exit(main())
