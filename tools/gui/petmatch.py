#!/usr/bin/env python3
"""寵物面板「圖樣板」比對（只用標準函式庫；唯讀：只經 `gui pixel` 讀像素，不點擊）。P-I5 實測 2026-10-11，計畫 notes/plan-scriptify.md §5。

為什麼：寵物名 / 等級 OCR 不穩（等級「0轉128」常讀成 28 / 1 / 134，名字 -Dark 120 常讀成空字串或少一個字），
但遊戲的渲染是固定的 —— 同一個名字 / 同一個數字的像素圖每次都一樣（5 角色 × 同名寵物 IoU = 1.000，不同名 0.366）。
作法：`gui pixel` 一次讀一大塊點（9000 點約 0.17 s）→ 依字色二值化 → 與 tools/.cache/pet-tpl/<版面>.json 的樣板比對。

三種樣板（同一個 JSON）：
  name   寵物名整塊圖（面板選中寵物的名字框；奶油色字）→ 標籤 = Monster 表正式名
  digit  等級黃字「0轉N」切字後的單字樣板（digitmatch.segment / Matcher；標籤 0～9 與「轉」＝ 轉 字右半）
         讀法：由右往左收數字，遇到「轉」才算讀完；中途遇到沒學過的字 → None（不會把 128 讀成 28）
  avatar 左欄頭像下的角色名整塊圖（咖啡色字；第 5 個頭像的名字被面板切掉，沒有）
樣板是**學出來的**（沒有預建檔）：呼叫端用可信的標籤（OCR 精確命中 Monster 表、等級多組 OCR 設定共識）呼叫 learn_*。
學習很保守：與既有「別的標籤」IoU 也高 → 視為標籤可疑，整次不學；同一標籤最多 MAX_VARIANTS 個變體。
測試可替換 petmatch.TPL_DIR；所有碰遊戲的呼叫都走 uikit.px。
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import digitmatch  # noqa: E402
import uikit  # noqa: E402

LAYOUT = '2880x1659'
TPL_DIR = uikit.CACHE / 'pet-tpl'

# ---- 取樣框（截圖座標 x, y, w, h；P-I5 實測）----
BOX_NAME = (430, 160, 200, 45)          # 選中寵物名字（奶油色字、棕木牌底）
BOX_LVL = (490, 620, 110, 34)           # 選中寵物模型下方「0轉N」黃字
AVATAR_Y = {'DKBO': 195, 'DKBO2': 322, 'DKBO3': 450, 'DKBO4': 580, 'DKBO5': 700}     # 左欄頭像中心（同 petwatch）
AVATAR_NAME_DY = 52                      # 頭像名字框 y = 頭像中心 + 52（高 24、寬 54、x 56）；第 5 個頭像的名字在面板外
AVATAR_TOP_Y = {'DKBO': 156, 'DKBO2': 285, 'DKBO3': 413, 'DKBO4': 542, 'DKBO5': 671}   # 選中黃框上緣（x=83；各 3 px 高）

# ---- 二值化條件（col = (r, g, b)）----
PREDS = {
    'name': lambda c: c[0] > 215 and c[1] > 190 and c[2] < 175 and c[0] - c[2] > 55,     # 奶油色字 ≈ (240,224,128)
    'lvl': lambda c: c[0] > 220 and c[1] > 200 and c[2] < 110,                           # 黃字
    'brown': lambda c: c[0] < 170 and c[1] < 130 and c[2] < 100,                         # 咖啡字（同 namematch 模式 2）
}
MIN_INK = {'name': 150, 'avatar': 100, 'lvl': 100}
HIT_MIN = 0.93                           # 整塊圖樣板命中門檻（實測同名 1.000）
MARGIN = 0.05                            # 與次佳「別的標籤」至少差這麼多
SHIFT = 1                                # 平移 ±1 px
PAD = 2
MAX_VARIANTS = 4
DUP_IOU = 0.995


def avatar_box(role: str) -> tuple:
    return (56, AVATAR_Y[role] + AVATAR_NAME_DY, 54, 24)


# ---- 讀圖 ----
def grab(specs, extra=()):
    """specs = [(x, y, w, h, 條件名)]；extra = [(x, y)] 額外點。一次 `gui pixel`（點多時約 0.2 s）。
    → ([每框的 '0'/'1' 字串列], [額外點 (r,g,b)])；讀不到回 (None, None)"""
    pts = []
    for x, y, w, h, _ in specs:
        pts.extend((x + i, y + j) for j in range(h) for i in range(w))
    n = len(pts)
    pts.extend(extra)
    cols = uikit.px(pts)
    if cols is None:
        return None, None
    out, k = [], 0
    for x, y, w, h, kind in specs:
        pred = PREDS[kind]
        out.append([''.join('1' if pred(cols[k + j * w + i]) else '0' for i in range(w)) for j in range(h)])
        k += w * h
    return out, cols[n:]


def ink(rows) -> int:
    return sum(r.count('1') for r in rows)


# ---- 整塊圖 <-> 大整數 ----
def pack(rows) -> int:
    """'0'/'1' 字串列 → 大整數（bit = (y+PAD)*stride + x+PAD；stride = 寬 + 2*PAD）"""
    if not rows:
        return 0
    stride = len(rows[0]) + 2 * PAD
    v = 0
    for y, r in enumerate(rows):
        for x, c in enumerate(r):
            if c == '1':
                v |= 1 << ((y + PAD) * stride + x + PAD)
    return v


def iou(a: int, b: int, stride: int) -> float:
    """a 平移 ±SHIFT 後與 b 的最大 IoU"""
    best = 0.0
    nb = b.bit_count()
    na = a.bit_count()
    for dy in range(-SHIFT, SHIFT + 1):
        for dx in range(-SHIFT, SHIFT + 1):
            s = dy * stride + dx
            sa = a << s if s >= 0 else a >> -s
            inter = (sa & b).bit_count()
            if inter:
                best = max(best, inter / (na + nb - inter))
    return best


# ---- 樣板檔 ----
def tpl_path(layout: str = LAYOUT) -> Path:
    return TPL_DIR / f'{layout}.json'


def load_tpl(layout: str = LAYOUT) -> dict:
    """{'name': {標籤: [hex]}, 'avatar': {標籤: [hex]}, 'digit': {字元: [點陣列字串]}}；沒檔 / 壞檔 → 空"""
    try:
        d = json.loads(tpl_path(layout).read_text(encoding='utf-8'))
    except (OSError, ValueError):
        d = {}
    return {k: d.get(k) if isinstance(d.get(k), dict) else {} for k in ('name', 'avatar', 'digit')}


def save_tpl(tpl: dict, layout: str = LAYOUT) -> None:
    TPL_DIR.mkdir(parents=True, exist_ok=True)
    p = tpl_path(layout)
    tmp = p.with_suffix('.tmp')
    tmp.write_text(json.dumps(tpl, ensure_ascii=False), encoding='utf-8')
    tmp.replace(p)


# ---- 整塊圖：名字 / 頭像名 ----
def match_whole(kind: str, rows, tpl: dict):
    """→ (標籤或 None, 最佳分, 次佳「別的標籤」分)。墨點太少 / 沒樣板 → (None, 0, 0)"""
    book = tpl.get(kind) or {}
    if not rows or ink(rows) < MIN_INK[kind] or not book:
        return None, 0.0, 0.0
    stride = len(rows[0]) + 2 * PAD
    img = pack(rows)
    best: dict = {}
    for label, vs in book.items():
        for h in vs:
            s = iou(img, int(h, 16), stride)
            if s > best.get(label, 0):
                best[label] = s
    if not best:
        return None, 0.0, 0.0
    rk = sorted(best.items(), key=lambda kv: -kv[1])
    sc = rk[0][1]
    second = rk[1][1] if len(rk) > 1 else 0.0
    if sc < HIT_MIN or sc - second < MARGIN:
        return None, sc, second
    return rk[0][0], sc, second


def learn_whole(kind: str, label: str, rows, tpl: dict, log=None) -> bool:
    """把整塊圖加進樣板。標籤可疑（別的標籤 IoU 也 ≥ HIT_MIN）/ 墨點不足 / 已有幾乎相同變體 / 變體已滿 → False（不改 tpl）"""
    if not rows or ink(rows) < MIN_INK[kind]:
        return False
    stride = len(rows[0]) + 2 * PAD
    img = pack(rows)
    book = tpl.setdefault(kind, {})
    for other, vs in book.items():
        if other != label and any(iou(img, int(h, 16), stride) >= HIT_MIN for h in vs):
            if log:
                log(f'petmatch：{kind} 標籤 {label!r} 但與既有 {other!r} 樣板 IoU ≥ {HIT_MIN}，標籤可疑，不學')
            return False
    vs = book.setdefault(label, [])
    if len(vs) >= MAX_VARIANTS or any(iou(img, int(h, 16), stride) >= DUP_IOU for h in vs):
        return False
    vs.append(format(img, 'x'))
    return True


# ---- 等級：切字 + 單字樣板 ----
def level_matcher(tpl: dict) -> digitmatch.Matcher:
    return digitmatch.Matcher(tpl.get('digit') or {})


def read_level(rows, tpl: dict):
    """黃字「0轉N」→ 等級 int；任何一步不確定 → None（呼叫端退回 OCR 共識）。
    由右往左收數字，遇到「轉」（轉 字右半）才算完整；沒學過的字 / 超過 3 位 / 值不在 1～200 → None"""
    if not rows or ink(rows) < MIN_INK['lvl'] or not tpl.get('digit'):
        return None
    segs = digitmatch.segment(rows)
    if len(segs) < 2:
        return None
    m = level_matcher(tpl)
    digits = ''
    for _, _, g in reversed(segs):
        ch, _, _ = m.classify(g)
        if ch is None:
            return None
        if ch == '轉':
            break
        digits = ch + digits
        if len(digits) > 3:
            return None
    else:
        return None
    return int(digits) if digits and 1 <= int(digits) <= 200 else None


def learn_level(rows, value: int, tpl: dict) -> int:
    """用可信的等級值學單字樣板：最右 len(value) 個字 = 數字、再左一個 = 「轉」。已能高分認出的字不重複存。回新增數"""
    if not rows or ink(rows) < MIN_INK['lvl']:
        return 0
    segs = digitmatch.segment(rows)
    s = str(int(value))
    if len(segs) < len(s) + 1:
        return 0
    labels = list(s)
    glyphs = segs[-len(s):]
    zhuan = segs[-len(s) - 1]
    book = tpl.setdefault('digit', {})
    m = level_matcher(tpl)
    n = 0
    for ch, (_, _, g) in list(zip(labels, glyphs)) + [('轉', (0, 0, zhuan[2]))]:
        got, sc, _ = m.classify(g)
        if got == ch and sc >= digitmatch.KNOWN_IOU:
            continue
        vs = book.setdefault(ch, [])
        v, _, _, nv = digitmatch.glyph_int(g)
        if len(vs) >= digitmatch.MAX_VARIANTS or any(digitmatch.iou(v, nv, bv, bn) >= digitmatch.SAME_IOU
                                                     for bv, _, _, bn in (digitmatch.glyph_int(h) for h in vs)):
            continue
        vs.append(g)
        n += 1
    return n
