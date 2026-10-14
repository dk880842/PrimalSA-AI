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
import re
import sys
from collections import Counter
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
        if kind == 'name' and uikit.is_name_fragment(label):     # 數字 / 斜線片段不是名字（舊樣板污染，見 prune_names）
            continue
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
    if not rows or ink(rows) < MIN_INK[kind] or (kind == 'name' and uikit.is_name_fragment(label)):
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


DIGIT_GAP_MAX = 6                        # 「轉」與數字、數字之間的字距（實機 pet_real.json 1～3 px；少一個字會空出約 10 px）


def read_level(rows, tpl: dict):
    """黃字「0轉N」→ 等級 int；任何一步不確定 → None（呼叫端退回 OCR 共識）。
    由右往左收數字，遇到「轉」（轉 字右半）才算完整；沒學過的字 / 字距 > DIGIT_GAP_MAX / 超過 3 位 / 值不在 1～200 → None"""
    if not rows or ink(rows) < MIN_INK['lvl'] or not tpl.get('digit'):
        return None
    segs = digitmatch.segment(rows)
    if len(segs) < 2:
        return None
    m = level_matcher(tpl)
    digits = ''
    right = None                                       # 上一個（右邊）字的左緣 x
    for x0, _, g in reversed(segs):
        if right is not None and right - (x0 + len(g[0])) > DIGIT_GAP_MAX:
            return None                                # 字距太大 = 中間有字被蓋掉 / 沒切出來（33 只剩一個 3 → 會讀成 3）
        right = x0
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


def level_consistent(rows, value: int, tpl: dict) -> bool:
    """OCR 共識讀到的等級 value 跟畫面上「認得出來的字」矛不矛盾（純函式）：
    最右 len(value) 個字裡，樣板有把握認出的字一定要等於 value 對應位數；再左一個字樣板有把握認成數字（不是「轉」）
    = 畫面上的數字比 value 多一位 → 矛盾。完全認不出的字不算矛盾（沒樣板時照舊信 OCR 共識）。
    2026-10-13 卡坦練雞：等級 33 被讀成 10 / 17（OCR 共識錯 + 樣板被錯標籤污染），所以 OCR 的值要先過這關才採用 / 學樣板"""
    if not rows or not tpl.get('digit'):
        return True
    segs = digitmatch.segment(rows)
    s = str(int(value))
    if len(segs) < len(s) + 1:
        return False                                   # 字數不夠（轉 + 數字）→ 畫面跟 value 對不起來
    tail = segs[-len(s) - 1:]
    if any(b[0] - (a[0] + len(a[2][0])) > DIGIT_GAP_MAX for a, b in zip(tail, tail[1:])):
        return False                                   # 「轉」到數字之間有空缺 = 少一個字（value 位數跟畫面對不起來）
    m = level_matcher(tpl)
    for ch, (_, _, g) in zip(s, segs[-len(s):]):
        got, _, _ = m.classify(g)
        if got is not None and got != ch:
            return False
    got, _, _ = m.classify(segs[-len(s) - 1][2])
    return got is None or got == '轉'


# 樣板污染清理（2026-10-13 實機樣板：'1' 混進 3 / 9 的字形、'轉' 混進一個 2 —— OCR 共識錯值被拿去學）
CONFLICT_IOU = digitmatch.HIT_MIN      # 不同標籤的兩個變體 IoU 到這裡 = classify 會互相打架
OUTLIER_IOU = 0.70                     # 同標籤、同尺寸的變體之間至少要這麼像（同字型實測 0.83～0.88；錯標籤 ≤ 0.6）


def _same_size(a, b) -> bool:
    return abs(a[1] - b[1]) <= 3 and abs(a[2] - b[2]) <= 3


def prune_names(tpl: dict) -> list:
    """清掉標籤是數字 / 斜線片段的名字樣板（就地改 tpl['name']）→ 被刪的標籤（2026-10-14 學到「65」：取出後名字框暫時只顯示成長字串殘段）"""
    book = tpl.get('name') or {}
    bad = [k for k in book if uikit.is_name_fragment(k)]
    for k in bad:
        del book[k]
    return bad


def prune_digits(tpl: dict) -> list:
    """清掉被錯標籤污染的單字樣板（就地改 tpl['digit']）→ 被刪的 [(標籤, 變體序號, 原因)]（序號是原清單位置）。
    規則：① 某變體跟「同尺寸的同標籤變體」都不像（< OUTLIER_IOU）、而同標籤另有 ≥ 2 個同尺寸變體彼此很像 → 離群，刪；
    ② 不同標籤兩變體 IoU ≥ CONFLICT_IOU：刪掉「同標籤裡沒有相像的同尺寸變體」那個（另一個有同標籤變體支持）；
       兩個都有 / 都沒有支持 → 兩個都刪（分不出誰對，留著只會讓 classify 打架；之後 OCR 共識 + level_consistent 會再學回來）。
    尺寸差 > 3 px 的變體是不同字形（「轉」整字 / 右半），不互相比"""
    book = tpl.get('digit') or {}
    items = [(ch, i, digitmatch.glyph_int(g)) for ch, vs in book.items() for i, g in enumerate(vs)]
    gi = {(ch, i): (v, w, h, n) for ch, i, (v, w, h, n) in items}

    def sib(key):
        ch, i = key
        a = gi[key]
        return [digitmatch.iou(a[0], a[3], b[0], b[3]) for (c2, j), b in gi.items() if c2 == ch and j != i and _same_size((0, a[1], a[2]), (0, b[1], b[2]))]

    def supported(key):
        s = sib(key)
        return bool(s) and max(s) >= OUTLIER_IOU

    drop = {}
    for key in gi:                                                    # ① 離群（同標籤其他同尺寸變體彼此很像，只有它不像）
        ch, i = key
        s = sib(key)
        others = [k for k in gi if k[0] == ch and k != key and _same_size((0, gi[k][1], gi[k][2]), (0, gi[key][1], gi[key][2]))]
        if len(others) >= 2 and max(s) < OUTLIER_IOU:
            ok_pairs = [digitmatch.iou(gi[a][0], gi[a][3], gi[b][0], gi[b][3]) for a in others for b in others if a < b]
            if ok_pairs and max(ok_pairs) >= OUTLIER_IOU:
                drop[key] = '同標籤離群'
    keys = sorted(gi)
    for x, ka in enumerate(keys):                                     # ② 不同標籤互相打架
        for kb in keys[x + 1:]:
            if ka[0] == kb[0] or ka in drop or kb in drop:
                continue
            a, b = gi[ka], gi[kb]
            if not _same_size((0, a[1], a[2]), (0, b[1], b[2])) or digitmatch.iou(a[0], a[3], b[0], b[3]) < CONFLICT_IOU:
                continue
            sa, sb = supported(ka), supported(kb)
            if sb and not sa:
                drop[ka] = f'與 {kb[0]} 打架、同標籤沒有相像的變體'
            elif sa and not sb:
                drop[kb] = f'與 {ka[0]} 打架、同標籤沒有相像的變體'
            else:
                drop[ka] = drop[kb] = f'{ka[0]} / {kb[0]} 互相打架、分不出誰對'
    for ch in list(book):
        book[ch] = [g for i, g in enumerate(book[ch]) if (ch, i) not in drop]
        if not book[ch]:
            del book[ch]
    return [(ch, i, why) for (ch, i), why in sorted(drop.items())]


def learn_level(rows, value: int, tpl: dict) -> int:
    """用可信的等級值學單字樣板：最右 len(value) 個字 = 數字、再左一個 = 「轉」。已能高分認出的字不重複存。回新增數。
    標籤可疑就整次不學（回 0；比照 learn_whole）：某個字已被別的標籤樣板認出（classify 有把握且不同）、
    或該標籤已有同尺寸變體但新字跟它們都不像（< OUTLIER_IOU）—— 2026-10-13 樣板 '1' 混進 3 / 9 字形就是 OCR 錯值學進去的"""
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
    pairs = list(zip(labels, glyphs)) + [('轉', (0, 0, zhuan[2]))]
    for ch, (_, _, g) in pairs:                                      # 先整批檢查標籤，任何一個可疑就全部不學
        got, sc, _ = m.classify(g)
        if got is not None and got != ch:
            return 0
        v, w, h, nv = digitmatch.glyph_int(g)
        same = [digitmatch.iou(v, nv, bv, bn) for bv, bw, bh, bn in (digitmatch.glyph_int(x) for x in book.get(ch, []))
                if abs(bw - w) <= 3 and abs(bh - h) <= 3]
        if same and max(same) < OUTLIER_IOU:
            return 0
    n = 0
    for ch, (_, _, g) in pairs:
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


# ---- 沒有名字的新寵物（errlog #87 / #92）----
# 剛抓到的寵物（或沒取過名的）名字框顯示的是「成長字串」a/b/c/d（實測 2026-10-11 布拉奇多斯 Lv1：49/9/8/2、49/9/7/2、48/9/7/1、47/10/7/1、45/10/8/1），
# 整塊圖樣板（以名字為標籤）和 Monster 表 OCR 都認不出。同一隻寵物的字串固定、不同隻不同，所以字串 = 這隻的身分（不是物種）。
# 物種靠「縮圖簽名」（寵物格縮圖 16 點，同物種同姿勢 = 相同）與「成長字串 → 物種」登錄檔多重確認；登錄檔是學出來的（learn-species，
# 呼叫端必須有可信標籤，例如外掛捉寵設置只選了單一物種、且該格是剛抓到的新寵物），沒登錄 = 不知道是什麼 → 一律不猜。
GROWTH_RE = re.compile(r'^\s*(\d{1,3})\s*/\s*(\d{1,3})\s*/\s*(\d{1,3})\s*/\s*(\d{1,3})\s*$')
THUMB_N, THUMB_TOL = 4, 24               # 縮圖每列 4 點（pet.THUMB_X）、每通道容差


_GROWTH_JUNK = re.compile(r"[\s'\"`.,:;|_~\-]")


def growth_norm(t) -> str:
    """OCR 行正規化：去空白與雜點標點（2026-10-14 40/9/5/6 讀成「姍/5/'6」），保留數字、/、漢字（漢字 = 被讀壞的欄）"""
    return _GROWTH_JUNK.sub('', str(t or ''))


def growth_fields(t) -> list:
    """'姍/9/6/5' → ['姍', '9', '6', '5']（去空白後以 / 切欄）"""
    return re.sub(r'\s+', '', str(t)).split('/')


def growth_compatible(line, whole: str) -> bool:
    """OCR 殘行 line 跟完整成長字串 whole 不矛盾（純函式）：
    (1) 去空白後是 whole 的子序列（掉字，#258 '34/8/8'）；或
    (2) 以 / 切欄、對齊完整字串的某一段連續欄（開頭或結尾被切掉都行），含數字的欄必須逐欄完全相等，不含數字的欄（Windows OCR 把兩位數讀成一個漢字，
        2026-10-14 實測 40/9/6/5 在寵物分頁讀成「姍/9/6/5」「姍/6/5」、倉庫分頁「姍/9/6」）當萬用欄；萬用欄最多 1 個、至少 2 欄數字相等"""
    t = growth_norm(line)
    if not t:
        return False
    it = iter(whole)
    if '/' in t and all(ch in it for ch in t):                    # 掉字子序列；至少要有 /（只剩「65」這種單段太短，什麼都像，2026-10-14）
        return True
    fs, ws = growth_fields(t), whole.split('/')
    if len(fs) > len(ws) or any(not f for f in fs):
        return False
    for off in range(len(ws) - len(fs) + 1):                    # 殘行 = 完整字串中連續幾欄（頭 / 尾被切掉都可能，2026-10-14 倉庫分頁「姍/9/6」）
        wild = same = 0
        for f, w in zip(fs, ws[off:off + len(fs)]):
            if not re.search(r'\d', f):
                wild += 1
            elif f == w or (f.isdigit() and str(int(f)) == w):
                same += 1
            else:
                break
        else:
            if wild <= 1 and same >= 2:
                return True
    return False


def growth_consistent(lines, whole: str) -> bool:
    """OCR 各行全部跟 whole 不矛盾（完整行必須等於它、殘行 growth_compatible），且至少 1 行有內容（純函式）。
    名字框讀不出時拿「已知的成長字串」（寵物欄讀到的 / 登錄檔的）來核對現場這張是不是同一個字串用"""
    ls = [growth_norm(t) for t in lines or [] if growth_norm(t)]
    if not ls or not GROWTH_RE.match(whole or ''):
        return False
    for t in ls:
        m = GROWTH_RE.match(t)
        if m:
            if '/'.join(str(int(g)) for g in m.groups()) != whole:
                return False
        elif not growth_compatible(t, whole):
            return False
    return True


def _growth_full(lines) -> Counter:
    full = Counter()
    for t in lines or []:
        m = GROWTH_RE.match(growth_norm(t))
        if m:
            full['/'.join(str(int(g)) for g in m.groups())] += 1
    return full


def parse_growth(lines) -> str | None:
    """OCR 各行 → 成長字串 'a/b/c/d'：完整吻合的行至少 2 行相同且沒有別的完整字串 → 該字串；否則 None（實測 5 / 5 個角色有 ≥ 2 行相同，另有殘行如「49/8」）。
    只有 1 行完整：其餘殘行至少 1 行、且全部跟它不矛盾（growth_compatible：掉字子序列，或某一欄被讀成漢字）才採用"""
    full = _growth_full(lines)
    if not full:
        return None
    top = full.most_common()
    if len(top) == 1 and top[0][1] == 1:                       # 只有 1 行完整（2026-10-12 #258 '34/8/3/8' + 2 行 '34/8/8'；2026-10-14 '40/9/6/5' + '姍/9/6/5' + '姍/6/5'）
        whole = top[0][0]
        rest = [t for t in lines if growth_norm(t) and not GROWTH_RE.match(growth_norm(t))]
        if len(rest) >= 1 and all(growth_compatible(r, whole) for r in rest):
            return whole
        return None
    if top[0][1] < 2 or (len(top) > 1 and top[1][1] >= top[0][1]):
        return None
    return top[0][0]


def growth_guess(lines) -> str | None:
    """比 parse_growth 寬：只有一種完整字串（1 行也行）、其餘行都不矛盾 → 該字串；否則 None。
    **只當候選**：名字框讀不出時，候選字串已登錄某物種、且縮圖認出同一物種，才當作該物種（pet.read_slot 三重確認），不單獨當身分"""
    full = _growth_full(lines)
    if len(full) != 1:
        return None
    whole = next(iter(full))
    rest = [t for t in lines if growth_norm(t) and not GROWTH_RE.match(growth_norm(t))]
    return whole if all(growth_compatible(r, whole) for r in rest) else None


def growth_like(lines) -> bool:
    """OCR 行裡有沒有「像成長字串」的（含 / 且有數字）：名字框讀不出時要不要再加一組 OCR 設定重讀"""
    return any('/' in str(t) and re.search(r'\d', str(t)) for t in lines or [])


def inner_same(a, b, n: int = THUMB_N, tol: int = THUMB_TOL) -> bool:
    """縮圖比對：只比每列前 n-1 點（最右欄會被選取框光暈蓋到，P8 實測），至少全部 - 1 點相符"""
    if not a or not b or len(a) != len(b) or len(a) % n:
        return False
    pairs = [(c, d) for k, (c, d) in enumerate(zip(a, b)) if k % n < n - 1]
    ok = sum(1 for c, d in pairs if all(abs(u - v) <= tol for u, v in zip(c, d)))
    return ok >= len(pairs) - 1


def species_path() -> Path:
    return TPL_DIR / 'species.json'


# ---- 成長字串 → 物種 登錄檔（2026-10-14 v2：一個字串可對多個物種）----
# 舊版 'growth' = {字串: 物種} 單值：撞號時 learn_species 刪掉、下一次又被另一種登回去 →「後登覆蓋前登」（卡坦 distribute1 rc 76：
# 49/10/6/3 登錄成克邦凱斯，DKBO5 同字串的寵物縮圖是邦恩吉 0.94；50/10/6/3 加格 / 邦恩吉同字串）。
# v2：'growth_src' = {字串: [{species, catcher, ts, score, src}…]}（每個物種一筆，附來源），撞號永遠記得；
# 'growth' 改成**推導出來的唯一對照**（只放只對到 1 個物種的字串），舊讀者（.get('growth')）看到撞號字串 = 沒登錄 → 退回縮圖 / 不確定。
# 判定一律：字串只當「候選過濾」（growth_species），候選 ≥ 2 種 → 只有縮圖在這幾種之間有把握（rank_among：inlier + 主色都過分差）才算，否則 None（不准存取）。
# 舊格式（沒有 growth_src）讀檔時自動遷移（src = 'legacy'），存檔寫 v2。
SPECIES_VER = 2


def _ensure_src(reg: dict) -> dict:
    """reg 沒有 growth_src（舊格式 / 測試直接給的 dict）→ 由 growth 遷移；回 growth_src"""
    src = reg.get('growth_src')
    if not isinstance(src, dict):
        src = {g: [{'species': sp, 'src': 'legacy'}] for g, sp in (reg.get('growth') or {}).items() if sp}
        reg['growth_src'] = src
    return src


def _derive(reg: dict) -> None:
    """growth_src → growth（只留唯一物種的字串）。直接寫進 reg['growth'] 但 growth_src 沒有的（舊程式路徑）先補進來"""
    src = _ensure_src(reg)
    for g, sp in list((reg.get('growth') or {}).items()):
        if sp and g not in src:
            src[g] = [{'species': sp, 'src': 'direct'}]
    reg['growth'] = {g: es[0]['species'] for g, es in src.items() if len({e['species'] for e in es}) == 1}


def growth_species(reg: dict, growth: str | None) -> list:
    """成長字串的所有候選物種（登錄順序；沒登錄 → []）。≥ 2 個 = 撞號，要靠縮圖決勝"""
    if not growth:
        return []
    src = reg.get('growth_src')
    if not isinstance(src, dict):
        sp = (reg.get('growth') or {}).get(growth)
        return [sp] if sp else []
    return list(dict.fromkeys(e['species'] for e in src.get(growth) or []))


def growth_add(reg: dict, growth: str, species: str, catcher=None, score=None, src: str | None = None, ts: str | None = None) -> bool:
    """登錄「growth 這個字串有一隻是 species」（附來源）。同物種已有 → 只更新來源；新物種 → 追加（撞號，不刪、不覆蓋）。回是否新增了物種"""
    import time as _t
    gs = _ensure_src(reg)
    es = gs.setdefault(growth, [])
    e = {'species': species, 'ts': ts or _t.strftime('%Y-%m-%d %H:%M:%S')}
    if catcher:
        e['catcher'] = catcher
    if score is not None:
        e['score'] = score
    if src:
        e['src'] = src
    old = next((x for x in es if x['species'] == species), None)
    if old is not None:
        old.update(e)
        _derive(reg)
        return False
    es.append(e)
    _derive(reg)
    return True


def load_species() -> dict:
    """{'thumb': {物種: [[(r,g,b)×16]...]}, 'growth': {成長字串: 物種}（推導：只放唯一物種）, 'growth_src': {成長字串: [來源…]}}；
    沒檔 / 壞檔 → 空；舊格式（只有 growth）自動遷移"""
    try:
        d = json.loads(species_path().read_text(encoding='utf-8'))
    except (OSError, ValueError):
        d = {}
    th = d.get('thumb') if isinstance(d.get('thumb'), dict) else {}
    reg = {'thumb': {k: [[tuple(c) for c in v] for v in vs] for k, vs in th.items()},
           'growth': d.get('growth') if isinstance(d.get('growth'), dict) else {}}
    if isinstance(d.get('growth_src'), dict):
        reg['growth_src'] = {g: [e for e in es if isinstance(e, dict) and e.get('species')] for g, es in d['growth_src'].items() if isinstance(es, list)}
        reg['growth'] = {}                                  # v2：growth 一律由 growth_src 推導（檔案裡的 growth 只是給人看）
        _derive(reg)
        return reg
    _derive(reg)                                            # 舊格式遷移：legacy 單值 + 抓寵來源檔（catch-src.json，pet_catch register 寫的「誰抓的」）補回撞號
    try:
        cs = json.loads((TPL_DIR / 'catch-src.json').read_text(encoding='utf-8'))
    except (OSError, ValueError):
        cs = {}
    for g, es in (cs if isinstance(cs, dict) else {}).items():
        for e in es if isinstance(es, list) else [es]:
            have = growth_species(reg, g)
            if any(x in uikit.MOUNTS for x in have):          # 舊 register 把第 1 格騎寵 51/9/8/1 登錄成魯尼帖斯（10-14 已修）→ 騎寵字串不吃 catch-src
                continue
            if isinstance(e, dict) and e.get('species') and e['species'] not in have:
                growth_add(reg, g, e['species'], catcher=e.get('catcher'), src='catch-src', ts=e.get('ts'))
    return reg


def save_species(reg: dict) -> None:
    _derive(reg)
    TPL_DIR.mkdir(parents=True, exist_ok=True)
    p = species_path()
    tmp = p.with_suffix('.tmp')
    out = {'ver': SPECIES_VER, 'thumb': reg.get('thumb') or {}, 'growth': reg['growth'], 'growth_src': reg['growth_src']}
    tmp.write_text(json.dumps(out, ensure_ascii=False), encoding='utf-8')
    tmp.replace(p)


def species_by_thumb(cols, reg: dict) -> str | None:
    """縮圖 → 物種：剛好只有一個物種的樣板吻合才回；多個物種都吻合（樣板太像）→ None"""
    hits = {sp for sp, vs in (reg.get('thumb') or {}).items() if any(inner_same(cols, v) for v in vs)}
    return hits.pop() if len(hits) == 1 else None


def identify_species(cols, growth: str | None, reg: dict) -> str | None:
    """多重確認：縮圖樣板命中（有縮圖時必要）；成長字串已登錄時縮圖必須是字串的候選物種之一（矛盾 → None）；
    沒縮圖（倉庫卡，縮圖版面沒量過）時只接受「成長字串只對到 1 種」。撞號（≥ 2 種）又沒縮圖 → None"""
    cands = growth_species(reg, growth)
    if cols is None:
        return cands[0] if len(cands) == 1 else None
    st = species_by_thumb(cols, reg)
    if st and cands and st not in cands:
        return None
    return st


def learn_species(reg: dict, species: str, cols, growth: str | None = None, max_variants: int = 4) -> bool:
    """登錄物種（呼叫端要有可信標籤）。縮圖已被「別的物種」樣板吻合 → 標籤可疑，不學。回是否有改動"""
    changed = False
    if cols:
        other = species_by_thumb(cols, reg)
        if other and other != species:
            return False
        vs = reg.setdefault('thumb', {}).setdefault(species, [])
        if not any(inner_same(cols, v) for v in vs) and len(vs) < max_variants:
            vs.append([tuple(c) for c in cols])
            changed = True
    if growth and species not in growth_species(reg, growth):
        growth_add(reg, growth, species, src='learn')      # 撞號（2026-10-12 實機 48/9/5/3）→ 兩種都記著，判定時靠縮圖（舊版刪掉、下次又被登回 = 互蓋）
        changed = True
    return changed
