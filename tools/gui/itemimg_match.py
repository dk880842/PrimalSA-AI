#!/usr/bin/env python3
"""背包 / 倉庫道具格縮圖 ↔ GameClient 道具 Sprite 的像素比對（只用標準函式庫）。2026-10-14 階段 2（notes/plan-item-icon-match.md）。

接線（2026-10-14 階段 3 / 4）：bag.py 的 find_item / find_items / list_all / item_slots 先用本模組挑格（bag.ITEM_MATCH / 環境變數 PSA_ITEM_MATCH=auto|icon|ocr），
動作類（use / store / take / drop / purge）照舊開彈窗 / 提示窗核對名稱。比對核心與寵物縮圖（petimg_match）共用 imgmatch.py。

圖示來源：tools/extract/item_images.py 抽出的 tools/.cache/item-images/<imageId>.png + index.tsv（不進 git；沒抽就丟 FileNotFoundError）。
版面（2880×1659 客戶區 = 1440×830 截圖座標；tools/.cache 既有背包 / 倉庫截圖離線量的）：
  背包格 bag.SLOT_X / SLOT_Y（5×3）：圖示中心 = 格心 (+2, +2)；倉庫格 bag.DEPOT_X / DEPOT_Y（5×4）：(+1, +1)。
  兩邊倍率都是 0.90（80×80 Sprite → 72×72）；Sprite 是固定畫布、中心固定，所以位移只搜 ±2。
  「顯示道具名」開著時名字白字疊在圖示上半部、右下有數量白字 → 遮掉畫面上「三通道最小值 > 200」或「總和 < 90（深色描邊）」的點。
  空格：沿用 bag.slot_occupied（格心周圍 25 點偏離空格棕）；倉庫格離線實測同一個棕色、同一套判法（空格 0 點、有道具 ≥ 8 點）。

判定（identify）：
  - 樣板去掉「顏色接近空格棕」的點（那些點對任何格都吻合，會讓棕色系圖示到處拿高分）。
  - 候選 pool = 道具名清單 → imageId 集合（一個名字可能有多個 imageId；不屬於任何道具的 Sprite 一律排除）。
    pool=None 為開集（全部道具圖，先粗篩），結果標 guess=True：開集分差很小，不能當名稱用。
  - 最佳分數 ≥ MIN_SCORE 且與第二名（不同 imageId）差 ≥ MARGIN → ok；前兩名都過門檻但太近 → imgmatch.tiebreak 投票。
  - 遮擋偵測（背包格）：格子左右內緣變暗的棕色點 ≥ OCCLUDED_MIN → occluded=True、ok=False（浮動「獲得 EXP」橫幅 / 半透明遮罩）。
  - match_slots 會把每個要找的圖的 lookalikes（換色版 / 相似圖）加進候選，避免「要找的不在格裡、換色版冒充」；
    直接呼叫 identify 只給 1 個候選時沒有這層保護。
  - 不過門檻 → imageId=None（不猜）。**不過門檻 ≠ 沒有這個道具**（EXP 橫幅 / 閃光會蓋住格子），呼叫端要重拍或走 OCR / 彈窗備援。
  - 圖示只能認到 imageId：同圖多名（例：龍王的守護 = 合成石 7 = 壞石 = 不明的石頭）→ ambiguous=True，有動作前要開彈窗核對名稱。

用法（專案根目錄；WSL / Windows 原生相同；唯讀、不碰遊戲）：
  uv run --no-project python tools/gui/itemimg_match.py shot <截圖.png> [--kind bag|depot|both] [--names 龍王的守護,千年龜的殼] [--json]
      對截圖每個有道具的格印結果；--names 不給 = 開集（全部道具圖，第一次建粗樣板快取約 10 秒）
  uv run --no-project python tools/gui/itemimg_match.py ids 龍王的守護      # 名稱 → imageId、同圖別名
退出碼：0 成功；1 沒有 tools/.cache/item-images（先跑 tools/extract/item_images.py）或截圖讀不到；2 名稱查無道具圖
程式介面：
  identify(img, kind, slot, pool=None) → {'slot','imageId','best','score','second','second_id','ok','name','names','ambiguous',
                                          'guess','occluded','dark','tie','by','missing','ranked'}
    imageId = 判定結果（不過門檻 / 被遮擋 = None）；name = pool 裡唯一對應這張圖的名稱；names = 用這張圖的全部道具名
  match_slots(img, kind, want_names, pool=None, slots=None, expand=True) → {'hits': {名稱: [格號…]（分數高到低）},
                                          'cells': {格號: identify 結果}, 'missing': [沒圖的名稱], 'pool': 實際候選}
  lookalikes(imageId) → 相似圖 imageId；名稱可寫「#24054」直接指定 imageId
  occupancy(img, kind) → [bool]；cells_of(kind) → [(格號 0 起, cx, cy)]；ids_for_name(name)；names_for_id(iid)
  img 可以是 get(x,y)、{(x,y): rgb}、pngread.decode 結果或 PNG 路徑；格號與 bag.py 相同（0 起）。
"""
import argparse
import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))
sys.path.append(str(ROOT / 'tools' / 'extract'))     # 放最後：避免 extract/ 的模組蓋過 gui/ 的同名模組
import bag  # noqa: E402  （只用常數與純函式 slot_occupied，不開面板）
import imgmatch  # noqa: E402
import item_images  # noqa: E402  （索引讀取；本身只用標準函式庫，UnityPy 只在匯出時載入）

IMG_DIR = ROOT / 'tools' / '.cache' / 'item-images'
COARSE_DIR = ROOT / 'tools' / '.cache'

SCALE = 0.90
KINDS = {
    'bag': {'xs': bag.SLOT_X, 'ys': bag.SLOT_Y, 'center': (2, 2), 'search': (2, 2), 'ring': (-41, -39, 41, 43)},
    # 倉庫格比背包格窄，左右邊緣直接是格框（深棕），遮擋偵測的邊緣取樣不適用 → ring=None（不偵測；沒有倉庫被橫幅蓋住的樣本）
    'depot': {'xs': bag.DEPOT_X, 'ys': bag.DEPOT_Y, 'center': (1, 1), 'search': (2, 2), 'ring': None},
}
CLIP = (-40, -40, 42, 42)     # 一格要讀的範圍（相對格心）：72 px 圖示 + 中心偏移 + 搜尋 ±2
TOL = imgmatch.TOL
MIN_SCORE = 0.50    # 最佳分數門檻（離線 43 格：對的 ≥ 0.542〔大地的羈絆，名字疊住〕）
MARGIN = 0.06       # 與第二名（不同 imageId）至少差這麼多（離線閉集最小分差 0.077）
SHORTLIST = 6       # 候選多於這個數時先粗篩留這麼多個再細比
COARSE_STRIDE = 7   # 粗篩樣板每 N 點取 1
# 遮擋偵測（浮動「獲得 EXP」橫幅 / 半透明遮罩）：背包格左右內緣 4 條直線（ring 的 dx、dy = -30～36 每 3 點）本來是空格棕，
# 被橫幅蓋住會變暗棕。離線：正常格暗棕 ≤ 6 點（96 點中），bag0 橫幅蓋住的 3 格 29～58 點、b3 / b4 半透明遮罩 62～96 點
RING_BROWN = (101, 72, 46)
OCCLUDED_MIN = 15
DROP_BG_LIKE = True
LOOK_K = 8          # match_slots 擴充候選：每個要找的圖加幾個最像的圖
LOOK_MIN = 0.45     # 相似圖粗分門檻

_INDEX = None       # imageId → {'names': [...], 'w', 'h'}（只收屬於道具的 Sprite）
_BYNAME = None      # 繁中名 → [imageId…]
_MISSING = None     # 沒有 Sprite 的道具名 → [imageId…]
_BYNORM = None      # 正規化名（去掉 [地] 這類方括號 / 空白）→ [imageId…]（「大地的羈絆」對「大地的羈絆[地]」）
_RAW = {}           # imageId → 原始樣板（全部不透明點）
_TPL = {}           # imageId → 比對樣板（去掉接近空格棕的點）
_LOOK = {}          # (imageId, k, min) → 相似圖
_COARSE = None


# ---- 索引 ----
def index() -> dict:
    global _INDEX, _BYNAME, _MISSING, _BYNORM
    if _INDEX is None:
        rows = item_images.read_index(str(IMG_DIR))
        if rows is None:
            raise FileNotFoundError(f'沒有 {IMG_DIR}/index.tsv；先跑 uv run --no-project --with UnityPy python tools/extract/item_images.py')
        idx, byname = {}, {}
        for r in rows:
            if not r['names']:
                continue                        # 不屬於任何道具的 Sprite（皮膚、寵物用…）→ 排除
            idx[r['imageId']] = {'names': r['names'], 'w': r['w'], 'h': r['h']}
            for n in r['names']:
                byname.setdefault(n, []).append(r['imageId'])
        miss = {}
        p = IMG_DIR / 'missing.tsv'
        if p.exists():
            for ln in p.read_text(encoding='utf-8').splitlines()[1:]:
                c = ln.split('\t')
                for n in c[2].split('、'):
                    if n:
                        miss.setdefault(n, []).append(c[0])
        bynorm = {}
        for n, ids in byname.items():
            for i in ids:
                bynorm.setdefault(norm(n), [])
                if i not in bynorm[norm(n)]:
                    bynorm[norm(n)].append(i)
        _INDEX, _BYNAME, _MISSING, _BYNORM = idx, byname, miss, bynorm
    return _INDEX


def norm(name: str) -> str:
    """名稱正規化：去掉 [地] / 【…】/（…）括號段與空白（同 bag.norm_name 的括號規則）"""
    import re
    return re.sub(r'\s+', '', re.sub(r'[\[【（(][^\]】）)]*[\]】）)]', '', str(name or '')))


def ids_for_name(name: str) -> list:
    """道具繁中名（完全相同）→ 有 Sprite 的 imageId 清單；道具存在但沒圖 → []；查無此名 → KeyError。
    「#24054」形式直接指定 imageId（測試 / 除錯用）"""
    index()
    if name.startswith('#') and name[1:] in _INDEX:
        return [name[1:]]
    if name in _BYNAME:
        return list(_BYNAME[name])
    if name in _MISSING:
        return []
    if norm(name) in _BYNORM:                       # 「大地的羈絆」→「大地的羈絆[地]」
        return list(_BYNORM[norm(name)])
    raise KeyError(f'道具圖索引找不到「{name}」')


def names_for_id(iid: str) -> list:
    """imageId → 用這張圖的全部道具名（去重）"""
    return list(index().get(str(iid), {}).get('names', []))


def ids_for(names) -> tuple:
    """名稱清單 → (imageId 清單（去重、保序）, 沒圖的名稱)"""
    out, miss = [], []
    for n in names:
        ids = ids_for_name(n)
        if not ids:
            miss.append(n)
        out += [i for i in ids if i not in out]
    return out, miss


# ---- 樣板 ----
def raw_template(iid: str) -> list:
    """imageId → 截圖格點樣板（0.90 倍、相對 Sprite 中心、全部不透明點）；非 80×80 的 Sprite 推測同樣以中心對齊（待量）"""
    if iid not in _RAW:
        _RAW[iid] = imgmatch.template(imgmatch.decode(IMG_DIR / f'{iid}.png'), SCALE, round_size=True)
    return _RAW[iid]


def template(iid: str) -> list:
    """比對用樣板 = raw_template 去掉「顏色接近空格棕」的點（DROP_BG_LIKE）：那些點不管格子裡是什麼都會吻合，
    只會讓棕色系圖示（橡樹果、章魚…）對任何格都拿高分（離線：去掉後閉集最小分差 0.077 → 0.205、開集錯判 3 → 0）"""
    if iid not in _TPL:
        pts = raw_template(iid)
        if DROP_BG_LIKE:
            lim = 3 * TOL
            br, bgc, bb = RING_BROWN
            pts = [t for t in pts if abs(t[2] - br) + abs(t[3] - bgc) + abs(t[4] - bb) > lim] or pts
        _TPL[iid] = pts
    return _TPL[iid]


def lookalikes(iid: str, k: int = LOOK_K, min_score: float = LOOK_MIN) -> list:
    """跟 iid 長得像的其他道具圖（換色版、同形不同色）：把 iid 畫在空格棕底上，全部道具圖的粗樣板放上去打分，
    取 ≥ min_score 的前 k 名 → [imageId…]。match_slots 用來擴充候選：只給「要找的那一個」時，
    不在候選裡的換色版會過門檻（離線：山賊的羽飾格只找青貝首飾的換色版 22014 → 0.572 誤判；加進來就由正確的圖勝出）"""
    key = (iid, k, min_score)
    if key not in _LOOK:
        disk = _look_disk()
        dk = f'{iid}|{k}|{min_score}'
        if dk in disk:
            _LOOK[key] = list(disk[dk])
            return list(_LOOK[key])
        cell = {(dx, dy): RING_BROWN for dy in range(-37, 38) for dx in range(-37, 38)}
        cell.update(imgmatch.placed(raw_template(iid), 0, 0))
        sc = []
        for j, pts in coarse_templates().items():
            if j == iid:
                continue
            v, _ = imgmatch.score(pts, cell, 0, 0, TOL, 1, 8)
            if v >= min_score:
                sc.append((v, j))
        _LOOK[key] = [j for _, j in sorted(sc, reverse=True)[:k]]
        disk[dk] = _LOOK[key]
        _look_save(disk)
    return list(_LOOK[key])


_LOOKDISK = None


def _look_stamp() -> str:
    return f"{(IMG_DIR / 'index.tsv').stat().st_mtime_ns}:{SCALE}:{COARSE_STRIDE}:{DROP_BG_LIKE}:{TOL}"


def _look_disk() -> dict:
    """lookalikes 的磁碟快取 tools/.cache/itemimg-look.json（戳記 = index.tsv / 倍率 / 粗樣板設定；不符就丟掉重算）。
    list_all 對整個工作集（約 40 個名稱）擴充相似圖，第一次每個約 0.1 秒，之後讀檔"""
    global _LOOKDISK
    if _LOOKDISK is None:
        try:
            d = json.loads((COARSE_DIR / 'itemimg-look.json').read_text(encoding='utf-8'))
            _LOOKDISK = d['look'] if d.get('stamp') == _look_stamp() else {}
        except (OSError, ValueError, KeyError, TypeError):
            _LOOKDISK = {}
    return _LOOKDISK


def _look_save(d: dict) -> None:
    try:
        (COARSE_DIR / 'itemimg-look.json').write_text(json.dumps({'stamp': _look_stamp(), 'look': d}, ensure_ascii=False), encoding='utf-8')
    except OSError:
        pass


def coarse_templates() -> dict:
    """全部道具圖的粗樣板（每 COARSE_STRIDE 點取 1）；磁碟快取 tools/.cache/itemimg-coarse.bin（index.tsv / 倍率變了自動重算）"""
    global _COARSE
    if _COARSE is None:
        stamp = f"{(IMG_DIR / 'index.tsv').stat().st_mtime_ns}:{SCALE}:{COARSE_STRIDE}:{DROP_BG_LIKE}:{TOL}"
        _COARSE = imgmatch.coarse_cache(COARSE_DIR / 'itemimg-coarse.bin', stamp, sorted(index()),
                                        lambda i: template(i)[::COARSE_STRIDE])
    return _COARSE


# ---- 版面 ----
def cells_of(kind: str) -> list:
    """kind 的全部格 [(格號 0 起, cx, cy)]（同 bag.slot_xy / depot_xy）"""
    k = KINDS[kind]
    n = len(k['xs']) * len(k['ys'])
    return [(i, k['xs'][i % 5], k['ys'][i // 5]) for i in range(n)]


def _xy(kind: str, slot) -> tuple:
    if isinstance(slot, tuple):
        return slot
    _, cx, cy = cells_of(kind)[slot]
    return cx, cy


def text_px(c, dx=0, dy=0) -> bool:
    """名字 / 數量白字與深色描邊 → True（不比）"""
    return min(c) > 200 or c[0] + c[1] + c[2] < 90


BAND_MIN_WHITE = 3     # 名字字列：一列（dy −40～+9）白字點（三通道最小 > 200）≥ 這麼多 → 那一列 ±BAND_PAD 列整條不比
BAND_MIN_SCORE, BAND_MARGIN = 0.62, 0.12   # 第二輪點少、棕色圖容易冒充（不在候選的貝殼被認成橡樹果 0.58）→ 門檻比第一輪嚴
BAND_PAD = 2           # （2026-10-14 實機：兩行名字「巴巴洛的許可證」「大地的羈絆[地]」蓋住圖示上半，只丟字本身的點時反鋸齒殘邊讓別的圖拿高分 → 第二輪整列丟）


def band_region(img, cx: int, cy: int, cells: dict) -> dict:
    """第二輪比對用：cells 再丟掉「有名字白字的整列」（± BAND_PAD）。名字關掉 / 沒疊到的格不變"""
    get = imgmatch.as_getter(img)
    x0, y0, x1, y1 = CLIP
    bad = set()
    for dy in range(y0, 10):
        n = 0
        for dx in range(x0, x1 + 1):
            c = get(cx + dx, cy + dy)
            if c is not None and min(c) > 200:
                n += 1
        if n >= BAND_MIN_WHITE:
            bad.update(range(dy - BAND_PAD, dy + BAND_PAD + 1))
    if not bad:
        return cells
    return imgmatch.Grid({q: c for q, c in cells.items() if (q[1] - cy) not in bad})


def occupied(img, kind: str, slot) -> bool:
    """有沒有道具（bag.slot_occupied：格心周圍 25 點偏離空格棕；倉庫格同一套）"""
    get = imgmatch.as_getter(img)
    cx, cy = _xy(kind, slot)
    return bag.slot_occupied([get(cx + dx, cy + dy) for dx, dy in bag.SLOT_PROBE])


def _dark_brown(c) -> bool:
    r, g, b = c
    return 35 <= r <= 82 and 22 <= g <= 60 and 10 <= b <= 42 and r > g > b


def occlusion(img, kind: str, slot) -> int:
    """格子左右內緣「變暗的棕色」點數（≥ OCCLUDED_MIN = 被橫幅 / 遮罩蓋住）；kind 沒有 ring 設定回 0"""
    ring = KINDS[kind]['ring']
    if not ring:
        return 0
    cx, cy = _xy(kind, slot)
    return imgmatch.occlusion(img, cx, cy, [(dx, dy) for dx in ring for dy in range(-30, 37, 3)], _dark_brown)


def occupancy(img, kind: str) -> list:
    get = imgmatch.as_getter(img)
    return [occupied(get, kind, i) for i, _, _ in cells_of(kind)]


# ---- 比對 ----
def _rank(cells, kind, cx, cy, ids, coarse=None):
    """→ [(分數, imageId, (s, ox, oy))]（分數高到低）"""
    k = KINDS[kind]
    ex, ey = cx + k['center'][0], cy + k['center'][1]
    if len(ids) > SHORTLIST:
        co = coarse or {i: template(i)[::COARSE_STRIDE] for i in ids}
        pre = sorted(ids, key=lambda i: imgmatch.coarse_pos(co[i], cells, ex, ey, k['search'], TOL, 2, 1, 8)[0],
                     reverse=True)
        ids = pre[:SHORTLIST]
    pos = {i: imgmatch.best_pos(template(i), cells, ex, ey, k['search'], TOL) for i in ids}
    return sorted(((p[0], i, p) for i, p in pos.items()), key=lambda t: -t[0])


def identify(img, kind: str, slot, pool=None, cells=None) -> dict:
    """一格是哪個道具圖。slot = 格號（0 起）或 (cx, cy)；pool = 候選道具名（None = 開集，結果 guess=True）。
    空格也會照比（呼叫端先用 occupied 排除；match_slots 會排除）"""
    cx, cy = _xy(kind, slot)
    occ = occlusion(img, kind, slot) if cells is None else 0
    second_pass = cells is None
    if cells is None:
        cells = imgmatch.Grid(imgmatch.region(img, cx, cy, CLIP, text_px))
    if pool is None:
        ids, miss, coarse = list(index()), [], coarse_templates()
    else:
        (ids, miss), coarse = ids_for(pool), None
    res = {'slot': slot, 'kind': kind, 'by': 'icon', 'guess': pool is None, 'missing': miss,
           'occluded': occ >= OCCLUDED_MIN, 'dark': occ}
    if not ids:
        return dict(res, imageId=None, best=None, score=0.0, second=0.0, second_id=None, ok=False, name=None,
                    names=[], ambiguous=False, tie=None)
    ranked = _rank(cells, kind, cx, cy, ids, coarse)
    c = imgmatch.classify(cells, ranked, template, MIN_SCORE, MARGIN, gate=not res['occluded'])   # 被遮擋 → 不判定也不投票
    if second_pass and not c['ok'] and not res['occluded']:
        bc = band_region(img, cx, cy, cells)                # 第二輪：名字字列整列丟掉再比（只救第一輪判不出的格）
        if bc is not cells:
            ranked2 = _rank(bc, kind, cx, cy, ids, coarse)
            c2 = imgmatch.classify(bc, ranked2, template, BAND_MIN_SCORE, BAND_MARGIN)
            if c2['ok']:
                ranked, c = ranked2, c2
                res['band'] = True
    (top_s, top_i, _), (sec_s, sec_i, _) = c['top'], c['second']
    ok, tie = c['ok'], c['tie']
    names = names_for_id(top_i) if ok else []
    in_pool = [n for n in (pool or []) if not n.startswith('#') and top_i in ids_for_name(n)] if ok else []
    return dict(res, imageId=top_i if ok else None, best=top_i, score=round(top_s, 3), second=round(sec_s, 3),
                second_id=sec_i, ok=ok, name=in_pool[0] if len(in_pool) == 1 else None, names=names,
                ambiguous=ok and len(names) > 1, tie=tie,
                ranked=[(i, round(s, 3)) for s, i, _ in ranked[:5]])


def match_slots(img, kind: str, want_names, pool=None, slots=None, expand: bool = True) -> dict:
    """want_names 各在哪幾格（只認 identify ok、imageId 屬於該名稱的格）。
    pool = 工作集（比對候選；want_names 一定在內。建議把可能同時在背包的道具一起放進來）；
    expand=True：再加上每個要找的圖的 lookalikes（換色版 / 相似圖），避免「要找的不在格裡、換色版冒充」；
    slots = 只看這些格（None = 全部有道具的格）。
    → {'hits': {名稱: [格號…]（分數高到低）}, 'cells': {格號: 結果}, 'missing': [沒圖的名稱], 'pool': 實際候選}"""
    get = imgmatch.as_getter(img)
    pool = list(dict.fromkeys(list(want_names) + list(pool or [])))
    if expand:
        have = set(ids_for(pool)[0])
        for i in ids_for(want_names)[0]:
            pool += ['#' + j for j in lookalikes(i) if j not in have and not have.add(j)]
    slots = [i for i, _, _ in cells_of(kind)] if slots is None else list(slots)
    cells = {}
    for i in slots:
        if occupied(get, kind, i):
            cells[i] = identify(get, kind, i, pool)
    hits = {}
    for n in want_names:
        ids = ids_for_name(n)
        got = sorted((r['score'], i) for i, r in cells.items() if r['ok'] and r['imageId'] in ids)
        hits[n] = [i for _, i in reversed(got)]
    _, miss = ids_for(want_names)
    return {'hits': hits, 'cells': cells, 'missing': miss, 'pool': pool}


def scan(img, kind: str, pool=None) -> list:
    """每個有道具的格 identify → [結果（多 ms）]"""
    get = imgmatch.as_getter(img)
    out = []
    for i, _, _ in cells_of(kind):
        if not occupied(get, kind, i):
            continue
        t = time.time()
        r = identify(get, kind, i, pool)
        r['ms'] = round((time.time() - t) * 1000)
        out.append(r)
    return out


def main(argv=None) -> int:
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    ap = argparse.ArgumentParser(description='背包 / 倉庫道具格縮圖比對（離線、唯讀；尚未接線到 bag.py）')
    sub = ap.add_subparsers(dest='cmd', required=True)
    a = sub.add_parser('shot', help='對一張截圖印每格結果')
    a.add_argument('png')
    a.add_argument('--kind', choices=['bag', 'depot', 'both'], default='bag')
    a.add_argument('--names', default='', help='候選道具名（逗號分隔）；不給 = 開集（全部道具圖，結果只是猜測）')
    a.add_argument('--json', action='store_true')
    b = sub.add_parser('ids', help='名稱 → imageId 與同圖別名')
    b.add_argument('name')
    args = ap.parse_args(argv)
    try:
        index()
    except FileNotFoundError as e:
        print(json.dumps({'ok': False, 'rc': 1, 'msg': str(e)}, ensure_ascii=False))
        return 1
    if args.cmd == 'ids':
        try:
            ids = ids_for_name(args.name)
        except KeyError as e:
            print(json.dumps({'ok': False, 'rc': 2, 'msg': str(e)}, ensure_ascii=False))
            return 2
        out = {i: names_for_id(i) for i in ids}
        for i, ns in out.items():
            print(f"{args.name} → imageId {i}（同圖 {len(ns)} 個名字：{'、'.join(ns[:12])}{'…' if len(ns) > 12 else ''}）")
        if not ids:
            print(f'{args.name}：有這個道具但 GameClient 沒有它的圖（走 OCR / 彈窗備援）')
        print(json.dumps({'ok': True, 'rc': 0, 'ids': out}, ensure_ascii=False))
        return 0
    try:
        img = imgmatch.decode(args.png)
    except (OSError, ValueError) as e:
        print(json.dumps({'ok': False, 'rc': 1, 'msg': f'截圖讀不到：{e}'}, ensure_ascii=False))
        return 1
    pool = [n for n in args.names.split(',') if n] or None
    try:
        if pool:
            ids_for(pool)
    except KeyError as e:
        print(json.dumps({'ok': False, 'rc': 2, 'msg': str(e)}, ensure_ascii=False))
        return 2
    res = []
    for kind in (['bag', 'depot'] if args.kind == 'both' else [args.kind]):
        res += scan(img, kind, pool)
    if not args.json:
        for r in res:
            nm = r['name'] or ('/'.join(r['names'][:3]) + ('…' if len(r['names']) > 3 else '') if r['ok'] else '?')
            flag = ('（猜測）' if r['guess'] else '') + ('（同圖多名）' if r['ambiguous'] else '')
            print(f"{r['kind']:5} {r['slot']:>2}  {r['imageId'] or '?(' + str(r['best']) + ')'}  {nm}{flag}  "
                  f"{r['score']:.3f} / 第二 {r['second_id']} {r['second']:.3f}  {r['ms']}ms")
    print(json.dumps({'ok': True, 'rc': 0, 'cells': [{k: v for k, v in r.items() if k != 'ranked'} for r in res]},
                     ensure_ascii=False))
    return 0


if __name__ == '__main__':
    sys.exit(main())
