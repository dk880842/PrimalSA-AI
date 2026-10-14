#!/usr/bin/env python3
"""寵物縮圖 ↔ 知識庫頭像的像素比對（認物種；只用標準函式庫）。2026-10-12 離線設計 + 驗證；2026-10-14 起是 pet.py 的主要辨識（judge：候選限定 +
遮擋偵測，名字 / 成長字串當第二道確認），比對核心與道具縮圖（itemimg_match）共用 imgmatch.py（逐格同分回歸 359 / 359）。

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
  6. 任務候選相對比較 rank_among（2026-10-13）：只在任務候選（例：卡坦 4 鯊 / 4 雞）之間比，逐點 inlier 分差 ≥ REL_MARGIN
     且「主色直方圖」（color_score）第一名同一隻、分差 ≥ HIST_MARGIN 才判定；pet.py 有 ctx['img_only']（--candidates / pet_catch register）時改用它。
  7. 候選集：呼叫端給這次任務需要的物種名 + --family（同系別換色版，避免「只給一隻」時兄弟物種也過門檻）；
     不給就是全部 Monster。候選 > SHORTLIST 時先粗比對留 SHORTLIST 個再細比。

用法（專案根目錄；WSL / Windows 原生相同）：
  uv run --no-project python tools/gui/petimg_match.py shot <截圖.png> [--names 火雞,奇寶,...] [--family] [--json]   # 離線：截圖裡每個非空格 / 倉庫卡
  uv run --no-project python tools/gui/petimg_match.py shot <截圖.png> --names 火雞,克克洛斯,霍爾克,奇寶 --among         # 任務候選相對比較（+ 主色）
  uv run --no-project python tools/gui/petimg_match.py live slot 3 [--names ...]                         # 唯讀：經 uikit.px 讀現場（寵物格 4537 點約 0.2 s）
程式介面：
  match(get, kind, cx, cy, names=None) → {'species', 'imageId', 'score', 'second', 'second_species', 'ok', 'tie', 'ranked'}；
    get(x, y) → (r,g,b)（截圖座標）；ok=False 時 species=None（不猜）。
  rank_among(get, kind, cx, cy, names) → 任務候選相對比較（多 'hist' / 'hist_second'）。match_rows(rows, bpp, kind, cx, cy, names) → 同上（PNG 解碼列）。read_cell(kind, cx, cy) → dict（經 uikit.px，一次讀整格）。
  family(names) → 同系別（Monster.petType）全部有頭像的物種名。cells_of(kind) → [(格號, cx, cy)]。is_empty(get, cx, cy) → 空格（爪印）。
  judge(get, kind, cx, cy, names, keep=(), family_stage=True, quick=False) → rank_among 欄位 + occ / occluded / stage / keep_scores（pet.py 主判定）。
  occlusion(get, kind, cx, cy) → 格子外圍被壓暗的點數（≥ OCC_MIN = 被浮字橫幅蓋住）。
"""
import argparse
import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import imgmatch  # noqa: E402  （共用核心：樣板 / 分數 / 位置 / 判定 / 主色 / 投票 / 遮擋 / 粗篩快取，道具 itemimg_match 也用）
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
    pts = imgmatch.template(imgmatch.decode(IMG_DIR / 'head' / _HEAD[iid]), KINDS[kind]['scale'], ALPHA_MIN)
    _TPL[key] = pts
    return pts


def coarse_templates(kind: str) -> dict:
    """全部頭像的粗樣板 {imageId: [(dx,dy,r,g,b)]}（樣板每 COARSE_STRIDE 點取 1）；全部 Monster 模式粗篩用。
    第一次要解碼 1000+ 張頭像（約 10 s），之後讀快取 tools/.cache/petimg-coarse-<kind>.bin（index.tsv 或倍率變了自動重算）"""
    if kind in _COARSE:
        return _COARSE[kind]
    stamp = f"{(IMG_DIR / 'index.tsv').stat().st_mtime_ns}:{KINDS[kind]['scale']}:{COARSE_STRIDE}"
    out = imgmatch.coarse_cache(COARSE_DIR / f'petimg-coarse-{kind}.bin', stamp, list(index()),
                                lambda i: template(i, kind)[::COARSE_STRIDE])
    _COARSE[kind] = out
    return out


# ---- 比對 ----
def cell_points(kind: str, cx: int, cy: int) -> list:
    """一格要讀的點（可見範圍、去掉遮罩），截圖座標"""
    k = KINDS[kind]
    x0, y0, x1, y1 = k['clip']
    return [(cx + dx, cy + dy) for dy in range(y0, y1 + 1) for dx in range(x0, x1 + 1) if not k['mask'](dx, dy)]


MIN_N = 40          # 有效點少於這個數 → 分數 0（粗找也用同一個下限，沿用 2026-10-12 的行為）


def _ex(kind: str, cx: int, cy: int) -> tuple:
    k = KINDS[kind]
    return cx + k['center'][0], cy + k['center'][1]


def _score(tpl, get_d, ox, oy, step):
    """樣板放在 (ox, oy)（頭像中心的截圖座標）的 inlier 比例（imgmatch.score）；get_d = {(x,y): rgb}（已去遮罩 / 可見範圍）"""
    return imgmatch.score(tpl, get_d, ox, oy, TOL, step, MIN_N)


def _coarse_score(tpl, cells, kind, cx, cy, step=4, stride=1):
    """位移步 step 的粗找 → (最佳分數, ox, oy)（imgmatch.coarse_pos）"""
    ex, ey = _ex(kind, cx, cy)
    return imgmatch.coarse_pos(tpl, cells, ex, ey, KINDS[kind]['search'], TOL, step, stride, MIN_N)


def _best_pos(tpl, cells, kind, cx, cy):
    ex, ey = _ex(kind, cx, cy)
    return imgmatch.best_pos(tpl, cells, ex, ey, KINDS[kind]['search'], TOL, 2, 3, MIN_N, coarse_min_n=MIN_N)


def _cells(get, kind: str, cx: int, cy: int) -> dict:
    """一格的可比像素 {(x,y): rgb}（可見範圍、去遮罩、去倉庫卡字）"""
    pts = cell_points(kind, cx, cy)
    cells = get if isinstance(get, dict) else {p: tuple(get(*p)) for p in pts}
    return imgmatch.Grid({p: cells[p] for p in pts if p in cells and not _text_px(kind, p[0] - cx, p[1] - cy, cells[p])})


def match(get, kind: str, cx: int, cy: int, names=None) -> dict:
    """get(x, y) → (r,g,b) 截圖座標（或 dict）；names = 候選物種名（None = 全部 Monster，先直方圖粗篩）。
    → {'species', 'imageId', 'score', 'second', 'second_species', 'ok', 'ranked'}；ok=False 時 species / imageId = None"""
    cells = _cells(get, kind, cx, cy)
    ids = ids_for(names) if names else list(index())
    if len(ids) > SHORTLIST:
        co = coarse_templates(kind) if not names else {i: template(i, kind)[::COARSE_STRIDE] for i in ids}
        ids = sorted(ids, key=lambda i: _coarse_score(co[i], cells, kind, cx, cy)[0], reverse=True)[:SHORTLIST]
    pos = {i: _best_pos(template(i, kind), cells, kind, cx, cy) for i in ids}
    ranked = sorted(((p[0], i, p) for i, p in pos.items()), key=lambda t: (t[0], t[1]), reverse=True)
    # 第二名 = 「不同物種」裡最高的（同 imageId 已合併；2D 版視為同物種）；分差不夠 → 第二關投票（imgmatch.classify）
    c = imgmatch.classify(cells, ranked, lambda i: template(i, kind), MIN_SCORE[kind], MARGIN, group=_group)
    (top_s, top_i, _), (sec_s, sec_i, _) = c['top'], c['second']
    ok = c['ok']
    return {'species': species_name(top_i) if ok else None, 'imageId': top_i if ok else None,
            'best_species': species_name(top_i), 'score': round(top_s, 3), 'second': round(sec_s, 3),
            'second_species': species_name(sec_i) if sec_i else None, 'ok': ok, 'tie': c['tie'],
            'ranked': [(species_name(i), round(s, 3)) for s, i, _ in ranked[:5]]}


# ---- 任務候選內的相對比較（2026-10-13 卡坦 4 鯊 / 4 雞：同系換色版，全 Monster / --family 會混進長得像的別系）----
REL_MARGIN = 0.06   # 候選內第一、第二名（不同物種）inlier 分差至少這麼多（離線實測最小 0.089：倉庫卡 克克洛斯 vs 奇寶）
HIST_LEVELS = imgmatch.HIST_LEVELS   # 主色直方圖：每通道量化成 4 級（64 格）
HIST_MARGIN = 0.05  # 主色直方圖交集分數，第一、第二名至少差這麼多（離線實測最小 0.082）


def _group(iid: str) -> str:
    """imageId → 物種比較鍵（同物種的 2D 版算同一隻）"""
    return species_key(species_name(iid))


def color_score(cells: dict, kind: str, iid: str, pos) -> float:
    """頭像主色特徵（imgmatch.color_score）：樣板放在最佳位置 pos，比「樣板不透明點的顏色分布」與「畫面同位置的顏色分布」（量化直方圖交集，0～1）。
    對換色版（鯊魚系 4 隻、火雞系 4 隻：同輪廓不同配色）比逐點 inlier 更分得開（鯊魚實測分差 0.27～0.68）"""
    return imgmatch.color_score(cells, template(iid, kind), pos, HIST_LEVELS)


def rank_among(get, kind: str, cx: int, cy: int, names) -> dict:
    """只在 names（這次任務的候選物種，例：pet_catch --assign 的物種）之間做相對比較，不擴到同系 / 全部 Monster（imgmatch.rank_among）。
    兩個特徵都要同意才 ok：① 逐點 inlier（match 同一套）第一名 ≥ MIN_SCORE[kind] 且與第二名（不同物種）差 ≥ REL_MARGIN；
    ② 主色直方圖（color_score）第一名是同一隻、且與第二名差 ≥ HIST_MARGIN。兩特徵方向一致、只是分差不夠
    （倉庫卡 奇寶 / 克克洛斯：冠毛被成長字串蓋住，inlier 差 0.02、主色差 0.03）→ 第三關投票（贏家要是同一隻；2026-10-14 卡坦 21 張全判對、0 誤判）。
    任一不成立 → ok=False、species=None（不猜）。
    → {'species', 'imageId', 'best_species', 'score', 'second', 'second_species', 'hist', 'hist_second', 'ok', 'ranked'}"""
    return _among_ids(_cells(get, kind, cx, cy), kind, cx, cy, ids_for(names))


def _among_ids(cells: dict, kind: str, cx: int, cy: int, ids, memo: dict | None = None) -> dict:
    ex, ey = _ex(kind, cx, cy)
    r = imgmatch.rank_among(cells, ids, lambda i: template(i, kind), ex, ey, KINDS[kind]['search'], MIN_SCORE[kind],
                            REL_MARGIN, HIST_MARGIN, group=_group, tol=TOL, coarse_min_n=MIN_N, memo=memo)
    (top_s, top_i), (sec_s, sec_i) = r['top'], r['second']
    ok, sc = r['ok'], r['sc']
    return {'species': species_name(top_i) if ok else None, 'imageId': top_i if ok else None, 'tiebreak': r['tie'],
            'best_species': species_name(top_i), 'score': round(top_s, 3), 'second': round(sec_s, 3),
            'second_species': species_name(sec_i) if sec_i else None,
            'hist': round(sc[top_i][1], 3), 'hist_second': round(r['hist_second'], 3), 'hist_best': species_name(r['hist_best']),
            'ok': ok, 'ranked': [(species_name(i), round(s_, 3), round(sc[i][1], 3)) for s_, i in r['ranked'][:5]]}


# ---- 候選限定主判定 judge（2026-10-14：pet.py 縮圖升為主要辨識）----
# 遮擋偵測：格子外圍本來是面板米色底的點（寵物格左右外側 dx ±50、倉庫卡左右框 dx ±46，各 dy −40～40 每 4 點，共 42 點），
# 被浮動「獲得 EXP」橫幅 / 半透明遮罩蓋住會壓暗成灰棕（imgmatch.dimmed_beige）。離線（262 張寵物面板截圖、非空格）：
# 正常寵物格 0～1 點、正常倉庫卡 0～10 點；play agent 2026-10-14 thumb-DKBO2 / DKBO3 被橫幅蓋住的 4 張卡 16～29 點（其中 3 張限定候選判不出）。
OCC_PTS = {'slot': [(dx, dy) for dx in (-50, 50) for dy in range(-40, 41, 4)],
           'card': [(dx, dy) for dx in (-46, 46) for dy in range(-40, 41, 4)]}
OCC_MIN = {'slot': 12, 'card': 14}     # 寵物格沒有被蓋住的實例（門檻照倉庫卡比例推，待實機補樣本）
JUDGE_SHORT = 4                        # 候選多於這個數時先粗比對留這麼多個（+ 一定要比的 keep）再做 rank_among
JUDGE_QUICK = 2                        # quick 模式：keep 之外只留同系別粗比對前 2 個
_FAMILY = {}


def occlusion(get, kind: str, cx: int, cy: int) -> int:
    """格子外圍被壓暗的點數（≥ OCC_MIN[kind] = 被橫幅 / 遮罩蓋住；imgmatch.occlusion + dimmed_beige）"""
    if isinstance(get, dict):
        d = get
        get = lambda x, y: d.get((x, y))           # noqa: E731
    return imgmatch.occlusion(get, cx, cy, OCC_PTS[kind], imgmatch.dimmed_beige)


def family_of(name: str) -> list:
    """family([name]) 的快取版（讀 Monster.jsonl 一次 / 名字）"""
    if name not in _FAMILY:
        _FAMILY[name] = family([name])
    return _FAMILY[name]


def _shortlist(cells, kind, cx, cy, ids, keep_ids, n=JUDGE_SHORT) -> list:
    if len(ids) <= n:
        return list(ids)
    co = {i: template(i, kind)[::COARSE_STRIDE] for i in ids}
    pre = sorted(ids, key=lambda i: _coarse_score(co[i], cells, kind, cx, cy)[0], reverse=True)
    out = pre[:n]
    return out + [i for i in keep_ids if i not in out]


def judge(get, kind: str, cx: int, cy: int, names, keep=(), family_stage: bool = True, quick: bool = False) -> dict:
    """候選限定的主判定（pet.py 縮圖為主用）：
      1. 遮擋偵測：被浮字橫幅 / 遮罩蓋住 → occluded=True、ok=False（不硬認；呼叫端等它消失重讀）。
      2. 候選 names（沒有頭像的名字略過）粗篩留 JUDGE_SHORT 個（keep = 文字說的物種，一定留著比）→ rank_among（inlier + 主色 + 投票）。
      3. family_stage：第一名過門檻 → 加第一名的同系別（換色版）再比一次，以第二輪為準
         （候選裡只有兄弟時防兄弟頂替；例：克克洛斯 對 [奇寶] 單獨比 0.76；文字說奇寶時也一樣要比，否則兄弟會被「確認」）。
      keep_scores = {keep 物種: 它自己的最佳 inlier 分數}：呼叫端用來判斷「文字說的物種縮圖根本不像」（見 pet.combine_ident 的 KEEP_FLOOR）。
    quick=True 且有 keep（大量唯讀清點，例：depot-list 卡片字已讀出名字）：候選只用 keep + 同系別前 JUDGE_QUICK 個（不比其他已知物種），
      約快 2 倍；文字整個讀錯成別系物種時只剩 KEEP_FLOOR（縮圖不像）擋得到，所以存取前的確認不要用 quick。
    開集（全部 Monster）不在這裡：只當參考，不准據以存取（見 match(names=None)）。
    → rank_among 的欄位 + {'occ', 'occluded', 'stage': 'cand'|'family'|'occluded'|'none'}"""
    occ = occlusion(get, kind, cx, cy)
    empty = {'species': None, 'imageId': None, 'best_species': None, 'score': 0.0, 'second': 0.0, 'second_species': None,
             'hist': 0.0, 'hist_second': 0.0, 'hist_best': None, 'ok': False, 'ranked': [], 'tiebreak': None, 'occ': occ}
    if occ >= OCC_MIN[kind]:
        return dict(empty, occluded=True, stage='occluded')
    have = {n for ns in index().values() for n in ns}
    if quick and any(n in have for n in keep):
        names = []
    names = [n for n in dict.fromkeys(list(names) + list(keep)) if n in have]
    if not names:
        return dict(empty, occluded=False, stage='none')
    keep = [n for n in keep if n in have]
    cells = _cells(get, kind, cx, cy)
    ids, keep_ids = ids_for(names), ids_for(keep) if keep else []
    memo = {}
    short = _shortlist(cells, kind, cx, cy, ids, keep_ids)
    r, stage = _among_ids(cells, kind, cx, cy, short, memo), 'cand'
    if family_stage and r['score'] >= MIN_SCORE[kind]:
        fam = [n for n in family_of(r['best_species']) if n not in names]
        if fam:
            top = ids_for([r['best_species']])
            more = [i for i in ids_for(fam) if i not in short]
            short2 = _shortlist(cells, kind, cx, cy, short + more, list(dict.fromkeys(keep_ids + top)), JUDGE_QUICK if quick else JUDGE_SHORT + 2)
            r, stage = _among_ids(cells, kind, cx, cy, short2, memo), 'family'
    ks = {n: round(max(memo[i][0][0] for i in ids_for([n]) if i in memo), 3) for n in keep
          if any(i in memo for i in ids_for([n]))}
    return dict(r, occ=occ, occluded=False, stage=stage, keep_scores=ks)


def _tiebreak(cells, kind, a, b) -> dict:
    """前兩名（不同物種）分數太近時的第二關（imgmatch.tiebreak）：a / b = (imageId, (s, ox, oy))，兩個樣板各放在自己的最佳位置，
    每個畫面點「明顯比較像誰」就投給誰。例：倉庫卡上 克克洛斯（黃冠）/ 奇寶（紅冠）只差在被名字字串蓋住一半的冠毛。
    → {'winner': imageId 或 None, 'votes': [a 票, b 票]}"""
    t = imgmatch.tiebreak(cells, imgmatch.placed(template(a[0], kind), a[1][1], a[1][2]),
                          imgmatch.placed(template(b[0], kind), b[1][1], b[1][2]), TIE_GOOD, TIE_GAP, TIE_MIN_PTS, TIE_RATIO)
    return {'winner': (a[0], b[0])[t['winner']] if t['winner'] is not None else None, 'votes': t['votes']}


def rows_getter(rows, bpp: int):
    return imgmatch.rows_getter(rows, bpp)


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
    """現場讀一格（唯讀，經 uikit.px 一次讀完；寵物格 4537 點 + 遮擋取點 42 點，常駐 server 約 0.2 s，2026-10-12 實機）→ dict 可直接餵 match / judge；讀不到 None"""
    import uikit
    pts = cell_points(kind, cx, cy) + [(cx + dx, cy + dy) for dx, dy in OCC_PTS[kind]]
    cols = uikit.px(pts)
    return dict(zip(pts, cols)) if cols else None


def is_depot(get) -> bool:
    """倉庫分頁特徵（同 pet.DEPOT_SIG：擴容藍鈕兩點）"""
    return all(all(abs(a - b) <= 24 for a, b in zip(get(x, y), c)) for x, y, c in
               [(1195, 690, (68, 112, 167)), (1215, 720, (72, 120, 179))])


def scan_shot(path, names=None, among: bool = False) -> list:
    """離線：一張 1440×830 截圖裡全部非空寵物格（+ 倉庫分頁時的倉庫卡）→ [{kind, index, ...match}]；among=True 用 rank_among"""
    w, h, bpp, rows = pngread.decode(Path(path).read_bytes())
    get = rows_getter(rows, bpp)
    kinds = ['slot'] + (['card'] if is_depot(get) else [])
    out = []
    for kind in kinds:
        for i, cx, cy in cells_of(kind):
            if is_empty(get, cx, cy):
                continue
            t = time.time()
            r = rank_among(get, kind, cx, cy, names) if among else match(get, kind, cx, cy, names)
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
        p.add_argument('--among', action='store_true', help='改用任務候選相對比較 rank_among（要給 --names；inlier + 主色直方圖都同意才判定）')
        p.add_argument('--json', action='store_true')
    args = ap.parse_args(argv)
    names = [n for n in args.names.split(',') if n] or None
    if names and args.family:
        names = family(names)
    if args.among and not names:
        ap.error('--among 要配 --names')
    if args.cmd == 'shot':
        res = scan_shot(args.png, names, among=args.among)
    else:
        _, cx, cy = cells_of(args.kind)[args.index - 1]
        cells = read_cell(args.kind, cx, cy)
        if cells is None:
            print(json.dumps({'ok': False, 'rc': 1, 'msg': '讀不到像素'}, ensure_ascii=False))
            return 1
        fn = rank_among if args.among else match
        res = [dict(fn(cells, args.kind, cx, cy, names), kind=args.kind, index=args.index)]
    if not args.json:
        for r in res:
            print(f"{r['kind']}{r['index']:>3}  {r['species'] or '?(' + r['best_species'] + ')'}  "
                  f"{r['score']:.3f} / 第二 {r['second_species']} {r['second']:.3f}  {r.get('ms', '')}ms")
    print(json.dumps({'ok': True, 'rc': 0, 'cells': [{k: v for k, v in r.items() if k != 'ranked'} for r in res]},
                     ensure_ascii=False))
    return 0


if __name__ == '__main__':
    sys.exit(main())
