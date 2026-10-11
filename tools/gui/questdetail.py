#!/usr/bin/env python3
"""任務詳情面板：讀列表（標題 + 狀態）、接取任務（P1，計畫 notes/plan-182-script.md）。只用標準函式庫。

用法（專案根目錄；WSL / Windows 原生指令相同）：
  uv run --no-project python tools/gui/questdetail.py status [--json] [--all]       # 開面板讀 主線 + 支線 全部列 → 1.82 清單（含 2999）各任務狀態；--all 連其他任務也列
  uv run --no-project python tools/gui/questdetail.py list [--tab 主線|支線] [--json] # 讀單一分頁全部列
  uv run --no-project python tools/gui/questdetail.py accept "彌生和日美子(1.82)" [--dry-run]   # 接取一個「待接取」任務（傳送 → NPC 對話 → 接受）
  uv run --no-project python tools/gui/questdetail.py read-image 檔.png              # 離線：讀一張截圖（不碰遊戲）
  uv run --no-project python tools/gui/questdetail.py learn-image 檔.png "標題1,標題2,…" [--head 標題]   # 離線建樣板：依列順序（只算完整可見的列）給標題
程式用：questdetail.read_list(tab) / status() / task_status(title) → (rc, 狀態) / accept(title, dry_run=False) / parse(img)（純函式，離線可測）。

退出碼（共用 0 / 1 / 2 / 8 / 9 / 10 見 uikit；questdetail 自己 120～129）：
  120 面板打不開 / 讀圖失敗（沒點任何面板內座標）
  121 列表裡找不到該任務（或分頁切不過去 / 列表捲不動）
  122 點了列之後，中間標題與目標不符（或讀不出）→ 不傳送
  123 該任務狀態不是「待接取」（進行中 / 已完成）→ 不傳送、不接（status 欄印出目前狀態）
  124 中間按鈕不是藍色「傳送」（例：進行中任務是金色「重置任務」，同一位置！）→ 不點
  125 按了傳送，逾時沒出現 NPC 對話框
  126 對話框防護：內文 / 按鈕讀不到、含不可逆關鍵字、左鈕不是「接受」→ 沒按，對話框維持開著，存 snap
  127 按了接受，但重開任務詳情讀到的狀態不是「進行中」（沒接成 / 讀不到）
  128 按了傳送後跳「提示」視窗（接取任務條件不達標：前置任務 / 等級 / 道具不足；2026-10-11 實測 2017 在 2999 未完成時）→ 已關視窗、沒接

畫面特徵（2026-10-11 以 tools/.cache 既有截圖實測；座標 = 截圖座標 1440×830）：
- 列表 x 160～385、y 237～712；每列約 80 px：標題一行 + 狀態條（棕 (169,139,110)，高約 23 px，x=180 取色找 run）。標題中心 ≈ 狀態條上緣 - 23。
  狀態條字色：進行中 = 黃（右邊有箭頭鈕）、待接取 = 白、已完成 = 綠（右邊有綠勾）。
- 列表可捲動時，上緣有 ▲（y 237～262）、下緣有 ▼（y 710～735）蓋住列，所以只讀「標題中心 ≥ 262 且狀態條完整（≥ 20 px）」的列；
  同一列在不同捲動位置的標題圖相同（以狀態條上緣對齊取圖），所以逐頁讀、依標題去重合併。
- 捲動（2026-10-11）：預設一次捲「可見列數 − 1 列」（page_dy：5 列 → 4 × 80 / 2.17 ≈ dy 147，上限 MAX_DY 150；舊的固定 dy=100 只捲約 2.75 列），scroll_page 捲後檢查上一頁最後一列標題是否仍在新頁（overlaps）；沒有 = 跳太多（可能漏列）→ 往上捲回、改小步 dy=DEFAULT_DY(100) 重捲，仍沒重疊才照這頁走（merge_pages 記 gaps）。read_list 結果多 'fallbacks'（退回小步次數）。--dy 給了就固定用那個量（仍做重疊檢查）。
- 標題辨識 = 圖樣板（深色字二值化，IoU，namematch.iou 共用）為主；沒樣板才 OCR（ocr.ps1）→ 對 TaskExplan 表名稱 snap → 自動存樣板。
- 中間頂端（624,205 附近）是「目前選中任務」標題（淺字），點列後用它驗證點對了；右下 / 中間 624,670 的藍鈕「傳送」只有待接取任務才有，
  進行中任務同一位置是金色「重置任務」（點了會重置任務！）→ accept 只在藍鈕、標題相符才點，且不在 uikit 的一般點擊範圍（forbidden center_btn）。
"""
import argparse
import difflib
import hashlib
import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import namematch  # noqa: E402
import pngread  # noqa: E402
import screen_sigs  # noqa: E402
import uikit  # noqa: E402
import winenv  # noqa: E402

ROOT = HERE.parents[1]
CACHE = ROOT / 'tools' / '.cache'
TPL_FILE = HERE / 'fixtures' / 'questdetail_tpl.json'
TASK_TABLE = ROOT / 'knowledge' / 'data' / 'tables' / 'TaskExplan.jsonl'

EXIT_NO_PANEL, EXIT_NOT_FOUND, EXIT_HEAD_MISMATCH, EXIT_NOT_PENDING = 120, 121, 122, 123
EXIT_NOT_TRANSFER, EXIT_NO_DIALOG, EXIT_DIALOG_GUARD, EXIT_NOT_ACCEPTED, EXIT_NOT_QUALIFIED = 124, 125, 126, 127, 128

# ---- 版面 ----
TAB_MAIN, TAB_SUB = (215, 215), (330, 215)
TAB_COLOR_PT = {'主線': (215, 198), '支線': (330, 198)}   # 選中分頁 = 橘黃 (243,178,64)，未選中 = 棕 (139,100,69)
TAB_ACTIVE, TAB_TOL = (243, 178, 64), 20
DETAIL_BTN = (368, 328)                                  # 左側任務面板的「詳情」
CLOSE_X = (1360, 80)
LIST_X0, LIST_X1 = 172, 385
BAR_X = 180                                              # 狀態條取色 x
BAR_COLOR, BAR_TOL, BAR_MIN_H = (169, 139, 110), 10, 20
LIST_Y0, LIST_Y1 = 232, 722
TITLE_MIN_CY = 262                                       # 標題中心至少這麼低（未捲動時第一列在 266）
TITLE_MIN_CY_ARROW = 276                                 # 頂端有 ▲ 時：▲ 會蓋住 y ≤ 262 附近的標題上緣
TITLE_X0, TITLE_W = 200, 172
TITLE_DY0, TITLE_H = -35, 24                             # 標題圖 y = 狀態條上緣 + DY0 起、高 TITLE_H
TITLE_INK = 150                                          # max(r,g,b) < 這個 = 字
HEAD_X0, HEAD_Y0, HEAD_W, HEAD_H = 500, 192, 250, 26     # 中間頂端選中標題
HEAD_INK = 170                                           # min(r,g,b) > 這個 = 字
PAD, SHIFT = 3, 2
LOCAL_WIN, LOCAL_MAX, LOCAL_GAP, DIL_MIN, SHORTLIST = 16, 14, 4, 0.85, 4   # 比對門檻（見 _local_miss / match_title）
DUP_IOU = 0.985
MAX_VARIANTS = 4
MIN_INK = 60
ROW_CLICK_X = 275
BTN = (624, 670)                                         # 傳送 / 重置任務 同位置
BTN_PTS = ((540, 655), (540, 690), (700, 655), (700, 690))
DRAG_DOWN = (272, 650, 272, 400)                         # 往下捲（內容上移）；x 取這裡的 272，起點 y 650、距離 dy（--dy 調）
TOP_DY = 300                                              # 往上捲到頂用較大的距離（過頭沒關係）
DEFAULT_DY = 100                                         # 小步捲動拖曳距離（實測 dy 120 → 列表移 260 px ≈ 3 列；dy 250 一次跳超過一頁會漏列）；也是「大步漏列」時退回重捲的小步
ROW_PITCH = 80                                           # 列距（px）
SCROLL_RATIO = 2.17                                      # 列表位移 / 拖曳距離（實測 dy 120 → 260 px）
MAX_DY = 150                                             # 自動大步的上限
SETTLE_S = 1.5                                           # 拖曳慣性
MAX_PAGES = 14


def page_dy(n_rows: int) -> int:
    """一次捲「可見列數 − 1 列」的拖曳距離（至少留一列重疊）：5 列 → 4 × 80 / 2.17 ≈ 147；夾在 [DEFAULT_DY, MAX_DY]"""
    px = max(1, n_rows - 1) * ROW_PITCH
    return max(DEFAULT_DY, min(MAX_DY, round(px / SCROLL_RATIO)))

DONE, DOING, PENDING, UNKNOWN = '已完成', '進行中', '待接取', '?'
MAIN_IDS = {1000, 2999, 2004, 2005, 2006, 2007, 2008}     # 主線分頁的任務（其餘在支線）

sleep = time.sleep
clock = time.time                # 測試時可替換


# ---------------------------------------------------------------- 像素 / 圖
class Img:
    """截圖像素存取：img(x, y) → (r, g, b)；可從 PNG 檔或位元組建立"""

    def __init__(self, rows, bpp: int):
        self.rows, self.bpp = rows, bpp

    @classmethod
    def from_file(cls, path):
        _, _, bpp, rows = pngread.decode(Path(path).read_bytes())
        return cls(rows, bpp)

    def __call__(self, x: int, y: int):
        r = self.rows[y]
        i = x * self.bpp
        return r[i], r[i + 1], r[i + 2]


def _near(c, ref, tol: int) -> bool:
    return all(abs(a - b) <= tol for a, b in zip(c, ref))


def live() -> Img | None:
    """背景截圖 → Img；失敗回 None"""
    CACHE.mkdir(parents=True, exist_ok=True)
    p = CACHE / 'questdetail-live.png'
    p.unlink(missing_ok=True)
    uikit.gui('shot', winenv.to_windows(p))
    try:
        return Img.from_file(p)
    except Exception:
        return None


def bitmap(img, x0: int, y0: int, w: int, h: int, ink) -> int:
    """區域 → 二值大整數（bit = (y+PAD)*stride + x+PAD；stride = w + 2*PAD），與 namematch 同格式"""
    stride = w + 2 * PAD
    v = 0
    for y in range(h):
        for x in range(w):
            if ink(img(x0 + x, y0 + y)):
                v |= 1 << ((y + PAD) * stride + x + PAD)
    return v


def _ink_dark(c) -> bool:
    return max(c) < TITLE_INK


def _ink_light(c) -> bool:
    return min(c) > HEAD_INK


def title_bitmap(img, top: int) -> int:
    return bitmap(img, TITLE_X0, top + TITLE_DY0, TITLE_W, TITLE_H, _ink_dark)


def head_bitmap(img) -> int:
    return bitmap(img, HEAD_X0, HEAD_Y0, HEAD_W, HEAD_H, _ink_light)


def _iou(a: int, b: int, w: int) -> float:
    return namematch.iou(a, b, w + 2 * PAD, SHIFT)


# ---------------------------------------------------------------- 名稱表 / 樣板
_names: list | None = None


def known_names(path=None) -> dict:
    """TaskExplan 表：名稱 → {'id','is182'}（詳情列表的任務名；含 (1.82) 字尾）"""
    global _names
    p = Path(path) if path else TASK_TABLE
    out = {}
    try:
        for ln in p.read_text(encoding='utf-8').splitlines():
            if ln.strip():
                d = json.loads(ln)
                if d.get('nameTn'):
                    out[d['nameTn']] = {'id': d['ID'], 'is182': bool(d.get('is182Task'))}
    except (OSError, ValueError):
        pass
    return out


def set_182() -> list:
    """「1.82 清單」= is182Task 全部 + 2999 成人儀式（前置）；依表順序"""
    return [n for n, d in known_names().items() if d['is182'] or d['id'] == 2999]


def tab_of(title: str) -> str:
    d = known_names().get(title)
    return '主線' if d and d['id'] in MAIN_IDS else '支線'


def norm_title(t: str) -> str:
    """比較用：全形括號轉半形、去空白"""
    return ''.join(str(t or '').replace('（', '(').replace('）', ')').split())


def snap_name(text: str, cutoff: float = 0.7) -> str | None:
    names = known_names()
    t = norm_title(text)
    if not t:
        return None
    by_norm = {norm_title(n): n for n in names}
    if t in by_norm:
        return by_norm[t]
    m = difflib.get_close_matches(t, list(by_norm), n=1, cutoff=cutoff)
    return by_norm[m[0]] if m else None


def load_tpl(path=None) -> dict:
    p = Path(path) if path else TPL_FILE
    try:
        d = json.loads(p.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        d = {}
    return {'row': dict(d.get('row', {})), 'head': dict(d.get('head', {}))}


def save_tpl(tpl: dict, path=None) -> None:
    p = Path(path) if path else TPL_FILE
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix('.tmp')
    tmp.write_text(json.dumps(tpl, ensure_ascii=False, indent=0, sort_keys=True), encoding='utf-8')
    tmp.replace(p)


def _dil(v: int, w: int) -> int:
    """膨脹 1 px（8 鄰域）：容許同一標題在不同捲動位置因子像素位移造成的筆畫粗細差"""
    st = w + 2 * PAD
    out = v
    for d in (1, -1, st, -st, st + 1, st - 1, -st + 1, -st - 1):
        out |= (v << d) if d >= 0 else (v >> -d)
    return out


def _shift(v: int, dx: int, dy: int, w: int) -> int:
    s = dy * (w + 2 * PAD) + dx
    return v << s if s >= 0 else v >> -s


def _local_miss(a: int, b: int, w: int, h: int, win: int = LOCAL_WIN) -> tuple:
    """a 對 b 的比對（先找膨脹後 IoU 最大的平移）→ (膨脹 IoU, 任一 win 欄寬視窗內「對方 1 px 內沒有對應」的墨點數最大值)。
    同標題 <= 約 11；只差一個字的標題（漆黑洞窟(三轉) vs (五轉)）>= 17，所以不能只看整體 IoU（兩者都 0.9 以上）"""
    da, db = _dil(a, w), _dil(b, w)
    best = (-1.0, 0, 0)
    for dy in range(-SHIFT, SHIFT + 1):
        for dx in range(-SHIFT, SHIFT + 1):
            sa = _shift(da, dx, dy, w)
            inter = (sa & db).bit_count()
            u = sa.bit_count() + db.bit_count() - inter
            sc = inter / u if u else 0.0
            if sc > best[0]:
                best = (sc, dx, dy)
    sc, dx, dy = best
    sa = _shift(a, dx, dy, w)
    miss = (sa & ~db) | (b & ~_shift(da, dx, dy, w))
    st, mask = w + 2 * PAD, (1 << w) - 1
    cols = [0] * w
    for y in range(h):
        r = (miss >> ((y + PAD) * st + PAD)) & mask
        if r:
            for x, ch in enumerate(format(r, 'b')[::-1]):
                if ch == '1':
                    cols[x] += 1
    run = mx = sum(cols[:win])
    for x in range(win, w):
        run += cols[x] - cols[x - win]
        mx = max(mx, run)
    return sc, mx


def match_title(bm: int, kind: str, tpl: dict) -> tuple:
    """標題圖 → (名稱或 None, 最佳分, 次佳分)；分 = 100 - 局部缺漏墨點（越大越像）。保守：缺漏 > LOCAL_MAX、膨脹 IoU 太低、
    或與次佳名稱差距 < LOCAL_GAP 都回 None（寧可退回 OCR）。先用 namematch.iou 挑前 SHORTLIST 個名稱再做局部比對（省時間）"""
    w, h = (TITLE_W, TITLE_H) if kind == 'row' else (HEAD_W, HEAD_H)
    if bm.bit_count() < MIN_INK:
        return None, 0.0, 0.0
    quick = sorted(((max(_iou(bm, int(x, 16), w) for x in vs), n) for n, vs in tpl[kind].items() if vs), reverse=True)[:SHORTLIST]
    res = []
    for _, n in quick:
        best = min(((m, -sc) for sc, m in (_local_miss(bm, int(x, 16), w, h) for x in tpl[kind][n])), default=None)
        if best:
            res.append((best[0], -best[1], n))
    res.sort()
    if not res:
        return None, 0.0, 0.0
    (m1, sc1, n1), second = res[0], (res[1] if len(res) > 1 else None)
    s1 = 100.0 - m1
    s2 = 100.0 - second[0] if second else 0.0
    if m1 > LOCAL_MAX or sc1 < DIL_MIN or (second and second[0] - m1 < LOCAL_GAP):
        return None, s1, s2
    return n1, s1, s2


def learn_tpl(tpl: dict, kind: str, name: str, bm: int) -> bool:
    """存一個變體（與既有幾乎一樣就不存；每名最多 MAX_VARIANTS）。回是否新增"""
    w = TITLE_W if kind == 'row' else HEAD_W
    vs = tpl[kind].setdefault(name, [])
    if len(vs) >= MAX_VARIANTS or bm.bit_count() < MIN_INK or any(_iou(bm, int(h, 16), w) >= DUP_IOU for h in vs):
        return False
    vs.append(format(bm, 'x'))
    return True


# ---------------------------------------------------------------- 解析（純函式）
def find_bars(img) -> list:
    """列表區狀態條：[(top, bottom)]，只留高度 >= BAR_MIN_H 的 run"""
    out, start = [], None
    for y in range(LIST_Y0, LIST_Y1):
        ok = _near(img(BAR_X, y), BAR_COLOR, BAR_TOL)
        if ok and start is None:
            start = y
        elif not ok and start is not None:
            if y - start >= BAR_MIN_H:
                out.append((start, y - 1))
            start = None
    return out


def status_of(img, top: int, bottom: int) -> str:
    """狀態條字色：綠 = 已完成、黃 = 進行中、白 = 待接取（像素計數，單點不可靠）"""
    g = yl = wh = 0
    for y in range(top, bottom + 1):
        for x in range(225, 330):
            r, gg, b = img(x, y)
            if gg > 180 and r < 90 and b < 90:
                g += 1
            elif r > 220 and gg > 190 and b < 80:
                yl += 1
            elif min(r, gg, b) > 215:
                wh += 1
    if g >= 60:
        return DONE
    if yl >= 60:
        return DOING
    if wh >= 40:
        return PENDING
    return UNKNOWN


def arrow_up(img) -> bool:
    """列表可往上捲時，頂端有黃色 ▲（x 255～290、y 240～258）蓋住第一列標題上緣"""
    n = sum(1 for y in range(240, 259, 2) for x in range(255, 291, 2)
            if img(x, y)[0] > 220 and img(x, y)[1] > 160 and img(x, y)[2] < 90)
    return n >= 12


def visible_rows(img) -> list:
    """目前畫面上完整可讀的列：[{top, cy, status, bm}]（cy = 標題中心 y）"""
    rows = []
    min_cy = TITLE_MIN_CY_ARROW if arrow_up(img) else TITLE_MIN_CY
    for top, bottom in find_bars(img):
        cy = top - 23
        if cy < min_cy:
            continue
        rows.append({'top': top, 'cy': cy, 'status': status_of(img, top, bottom), 'bm': title_bitmap(img, top)})
    return rows


def tab_active(img) -> str | None:
    on = [t for t, (x, y) in TAB_COLOR_PT.items() if _near(img(x, y), TAB_ACTIVE, TAB_TOL)]
    return on[0] if len(on) == 1 else None


def transfer_button(img) -> bool:
    """中間按鈕是藍色「傳送」（4 點皆 b - r >= 60）；金色「重置任務」/ 沒按鈕 = False"""
    return all(img(x, y)[2] - img(x, y)[0] >= 60 and img(x, y)[2] >= 140 for x, y in BTN_PTS)


def parse(img, tpl: dict | None = None, ocr_fn=None) -> list:
    """一張截圖 → 列 [{title, status, cy, top, bm, how}]；how = 'tpl' / 'ocr' / None（title 為 None = 不認得）。
    ocr_fn(top) → 文字（沒給就不 OCR）；OCR 結果 snap 到表名，成功才採用（並由呼叫端決定要不要學）"""
    tpl = load_tpl() if tpl is None else tpl
    out = []
    for r in visible_rows(img):
        name, best, second = match_title(r['bm'], 'row', tpl)
        how = 'tpl' if name else None
        if not name and ocr_fn:
            name = snap_name(ocr_fn(r['top']) or '')
            how = 'ocr' if name else None
        out.append(dict(r, title=name, how=how, score=round(best, 3)))
    return out


def find_row(rows: list, title: str) -> dict | None:
    w = norm_title(title)
    return next((r for r in rows if r['title'] and norm_title(r['title']) == w), None)


def same_row(a: dict, b: dict) -> bool:
    """兩次讀到的是同一列：標題相同（認得時）或標題圖 IoU 幾乎一樣（不認得時）"""
    if a['title'] and b['title']:
        return a['title'] == b['title']
    if a['title'] or b['title']:
        return False
    return _iou(a['bm'], b['bm'], TITLE_W) >= 0.93


def merge_pages(pages: list) -> tuple:
    """逐頁（由上往下）合併列：→ (rows, gaps)；gaps = 相鄰兩頁完全沒有共同列的次數（可能漏列）"""
    rows, gaps = [], 0
    prev = None
    for pg in pages:
        if prev is not None and pg and not any(same_row(a, b) for a in prev for b in pg):
            gaps += 1
        for r in pg:
            if not any(same_row(r, x) for x in rows):
                rows.append(r)
        if pg:
            prev = pg
    return rows, gaps


# ---------------------------------------------------------------- 面板
def _panel_sig() -> list:
    t = screen_sigs.PANEL_TITLE['quest'][:6]
    return [screen_sigs.PANEL_X['quest']] + [(x, y, r, g, b, screen_sigs.TITLE_TOL) for x, y, r, g, b in t]


PANEL = uikit.Panel('QUESTDETAIL', DETAIL_BTN, _panel_sig(), CLOSE_X,
                    forbidden={'center_btn': uikit.rect(BTN[0], BTN[1], 60),            # 傳送 / 重置任務：只准 accept 驗證後放行
                               'reset_zone': (880, 130, 480, 600)})                      # 右側任務介紹區：不需點


def open_detail() -> bool:
    return uikit.open_panel(PANEL, timeout=4.0)


def close_detail() -> bool:
    return uikit.close_panel(PANEL)


def _ocr_title(img_top: int) -> str:
    """列標題 OCR（只在樣板沒命中時；活畫面）"""
    return _best_line(uikit.ocr((TITLE_X0, img_top + TITLE_DY0, TITLE_W, TITLE_H), '-Dark', 150, '-Zooms', '2,3,4'))


def _ocr_head() -> str:
    return _best_line(uikit.ocr((HEAD_X0, HEAD_Y0, HEAD_W, HEAD_H), '-Light', HEAD_INK, '-Zooms', '2,3,4'))


def _best_line(lines: list) -> str:
    """ocr.ps1 -Zooms 每個倍數回一行（同一個標題讀好幾次，可能有幾行是亂碼）：挑 snap 得到表名且出現最多次的那行；都不行回空字串"""
    votes: dict = {}
    for t in lines:
        n = snap_name(t)
        if n:
            votes[n] = votes.get(n, 0) + 1
    return max(votes, key=votes.get) if votes else ''


def _stable_shot(max_tries: int = 4):
    """等列表停住（連兩張狀態條位置相同）再回圖"""
    prev = None
    img = None
    for _ in range(max_tries):
        img = live()
        if img is None:
            return None
        cur = find_bars(img)
        if prev is not None and cur == prev:
            return img
        prev = cur
        sleep(0.4)
    return img


def _learn_page(img, rows: list, tpl: dict) -> None:
    """OCR 才認出的列 → 存樣板，下次走圖樣板"""
    changed = False
    for r in rows:
        if r['how'] == 'ocr' and r['title']:
            changed |= learn_tpl(tpl, 'row', r['title'], r['bm'])
    if changed:
        try:
            save_tpl(tpl)
        except OSError:
            pass


def select_tab(tab: str) -> bool:
    """切到 主線 / 支線（已在就不點）；點完驗證分頁色"""
    img = live()
    if img is None:
        return False
    if tab_active(img) == tab:
        return True
    x, y = TAB_MAIN if tab == '主線' else TAB_SUB
    if not uikit.safe_click(x, y, PANEL, note=f'questdetail 切 {tab} 分頁', wait_ms=800):
        return False
    img = live()
    return img is not None and tab_active(img) == tab


def scroll(down: bool, dy: int = DEFAULT_DY) -> None:
    """拖曳捲動（往下 = 內容上移）；起點在列表內、避開 ▲▼（x 272 y 262 以下 / 710 以上）；之後等慣性"""
    x1, _, x2, _ = DRAG_DOWN
    y1b = 650
    y2b = y1b - dy
    a, b = (y1b, y2b) if down else (y2b, y1b)
    uikit.gui('drag', str(x1), str(a), str(x2), str(b), note='questdetail 捲動列表')
    sleep(SETTLE_S)


def overlaps(prev: list, cur: list) -> bool:
    """捲動後有沒有漏列：上一頁最後一列仍在新頁（它在最下面，最後才會被捲出去；仍在 = 中間沒跳過列）。任一頁沒讀到列就當沒問題（交給原本的到底判斷）"""
    if not prev or not cur:
        return True
    return any(same_row(prev[-1], r) for r in cur)


def scroll_page(prev_rows: list, tpl: dict, dy: int | None = None) -> tuple:
    """往下捲一頁並讀 → (img, rows, fell_back)。dy=None：捲「可見列數 − 1 列」的量（page_dy）；捲後上一頁最後一列沒出現在新頁 =
    跳太多（可能漏列）→ 先往上捲回、改小步（DEFAULT_DY）重捲，仍沒重疊就照這頁回傳（merge_pages 會記 gaps）。截圖失敗 img = None"""
    big = page_dy(len(prev_rows)) if dy is None else dy
    scroll(True, big)
    img = _stable_shot()
    if img is None:
        return None, [], False
    rows = parse(img, tpl, _ocr_title)
    if big <= DEFAULT_DY or overlaps(prev_rows, rows):
        return img, rows, False
    scroll(False, big)                                    # 退回原位再小步重捲
    scroll(True, DEFAULT_DY)
    img = _stable_shot()
    if img is None:
        return None, [], True
    return img, parse(img, tpl, _ocr_title), True


def scroll_top(dy: int = TOP_DY) -> bool:
    """捲到列表最上（連兩頁狀態條位置 + 狀態相同 = 到頂；最多 MAX_PAGES 次）。截圖失敗回 False"""
    last = None
    for _ in range(MAX_PAGES):
        img = _stable_shot()
        if img is None:
            return False
        sig = [(r['top'], r['status']) for r in visible_rows(img)]
        if sig == last:
            return True
        last = sig
        scroll(False, dy)
    return True


def read_list(tab: str = '支線', dy: int | None = None, learn: bool = True) -> dict:
    """面板已開著：切到 tab → 捲到最上 → 逐頁讀到底 → {'ok','rows','gaps','tab','pages'}。
    rows = [{title, status, how}]（依列表順序）；title 為 None = 不認得（樣板與 OCR 都失敗）。gaps > 0 = 相鄰頁沒交集，可能漏列"""
    if not select_tab(tab):
        return {'ok': False, 'why': f'切不到 {tab} 分頁', 'rows': [], 'gaps': 0, 'tab': tab, 'pages': 0}
    tpl = load_tpl()
    if not scroll_top():
        return {'ok': False, 'why': '截圖失敗', 'rows': [], 'gaps': 0, 'tab': tab, 'pages': 0}
    pages = []
    last = None
    fallbacks = 0
    img = _stable_shot()
    rows = None
    for _ in range(MAX_PAGES):
        if rows is not None:                                  # 第 2 頁起：一次捲「可見列數 − 1 列」，漏列就退回小步（scroll_page）
            img, rows, fb = scroll_page(rows, tpl, dy)
            fallbacks += fb
        if img is None:
            return {'ok': False, 'why': '截圖失敗', 'rows': [], 'gaps': 0, 'tab': tab, 'pages': len(pages)}
        if rows is None:
            rows = parse(img, tpl, _ocr_title)
        if learn:
            _learn_page(img, rows, tpl)
        key = [(r['title'], r['status']) for r in rows]
        if key == last:
            break
        last = key
        pages.append(rows)
    merged, gaps = merge_pages(pages)
    return {'ok': bool(merged), 'rows': [{'title': r['title'], 'status': r['status'], 'how': r['how']} for r in merged],
            'gaps': gaps, 'tab': tab, 'pages': len(pages), 'fallbacks': fallbacks}


def status(want: list | None = None, dy: int | None = None) -> dict:
    """開面板讀主線 + 支線 → {'ok','tasks': {名稱: 狀態或 None（列表裡沒有）}, 'unknown': 不認得的列數, 'gaps'}；結束關面板"""
    src = 'questdetail'
    rc = uikit.preflight(src)
    if rc:
        return {'ok': False, 'rc': rc}
    if not open_detail():
        return {'ok': False, 'rc': EXIT_NO_PANEL, 'why': '任務詳情打不開'}
    try:
        rows, unknown, gaps = [], 0, 0
        for tab in ('主線', '支線'):
            r = read_list(tab, dy)
            if not r['ok']:
                return {'ok': False, 'rc': EXIT_NOT_FOUND, 'why': r.get('why', '讀不到列表'), 'tab': tab}
            rows += r['rows']
            gaps += r['gaps']
    finally:
        close_detail()
    unknown = sum(1 for r in rows if not r['title'])
    want = list(want) if want else set_182()
    got = {r['title']: r['status'] for r in rows if r['title']}
    return {'ok': True, 'rc': 0, 'tasks': {n: got.get(n) for n in want}, 'others': {n: s for n, s in got.items() if n not in want},
            'unknown': unknown, 'gaps': gaps}


# ---------------------------------------------------------------- 接取
def task_status(title: str, dy: int | None = None) -> tuple:
    """單一任務狀態（questrun 用）：開面板 → 只讀該任務所在分頁 → 關面板 → (rc, 狀態)；
    狀態 = 已完成 / 進行中 / 待接取，列表裡找不到 = None（rc 仍 0）；rc 非 0 = 面板打不開 / 讀失敗（uikit.preflight 的碼也原樣回）"""
    src = 'questdetail'
    name = snap_name(title, 0.9)
    if not name:
        return uikit.fail(src, uikit.EXIT_USAGE, f'「{title}」不在任務表（TaskExplan）名稱裡'), None
    rc = uikit.preflight(src)
    if rc:
        return rc, None
    if not open_detail():
        return uikit.fail(src, EXIT_NO_PANEL, '任務詳情打不開'), None
    try:
        r = read_list(tab_of(name), dy)
    finally:
        close_detail()
    if not r['ok']:
        return uikit.fail(src, EXIT_NOT_FOUND, f'讀不到列表：{r.get("why")}'), None
    row = find_row(r['rows'], name)
    return 0, (row['status'] if row else None)


def _read_head(img, tpl: dict) -> tuple:
    """中間頂端選中標題 → (名稱或 None, how)：樣板優先，沒命中才 OCR（命中 snap 才算）"""
    name, _, _ = match_title(head_bitmap(img), 'head', tpl)
    if name:
        return name, 'tpl'
    t = snap_name(_ocr_head())
    return (t, 'ocr') if t else (None, None)


def _dialog_screen() -> dict:
    return uikit.screen()


LAST: dict = {}                    # accept 的結果：state = 'done' / 'doing'（skip_ok 略過）/ 'accepted'


def accept(title: str, dry_run: bool = False, dy: int | None = None, presses: int = 2, skip_ok: bool = False, verify: bool = True) -> int:
    """接取「待接取」任務 title（完整名稱，例 彌生和日美子(1.82)）：找列 → 點 → 驗中間標題 → 驗藍色傳送鈕 → 傳送 → 等 NPC 對話框 →
    驗對話框（內文 / 按鈕可讀、無不可逆字、左鈕是「接受」）→ 按左鈕（最多 presses 次）→ 重開詳情驗證「進行中」。
    任何驗證不過都不往下點；回退出碼（見檔頭）。dry_run 只做到「驗證傳送鈕」為止（不點傳送）。
    questrun 用（每任務只開一次詳情）：skip_ok=True → 列表裡該任務已完成 / 進行中時不當錯誤：關面板、回 0，LAST['state'] = 'done' / 'doing'；
    verify=False → 按完接受後不再重開詳情確認（改看畫面：對話框已收起），成功回 0、LAST['state'] = 'accepted'（呼叫端直接點追蹤欄卡片）"""
    src = 'questdetail'
    LAST.clear()
    name = snap_name(title, 0.9)
    if not name:
        return uikit.fail(src, uikit.EXIT_USAGE, f'「{title}」不在任務表（TaskExplan）名稱裡')
    rc = uikit.preflight(src)
    if rc:
        return rc
    if not open_detail():
        return uikit.fail(src, EXIT_NO_PANEL, '任務詳情打不開')
    tab = tab_of(name)
    tpl = load_tpl()
    clicked_transfer = False
    try:
        if not select_tab(tab):
            return uikit.fail(src, EXIT_NOT_FOUND, f'切不到 {tab} 分頁')
        if not scroll_top():
            return uikit.fail(src, EXIT_NO_PANEL, '截圖失敗')
        row = None
        prev_sig = None
        img = _stable_shot()
        rows = None
        for _ in range(MAX_PAGES):
            if rows is not None:                              # 第 2 頁起一次捲「可見列數 − 1 列」，漏列退回小步
                img, rows, _fb = scroll_page(rows, tpl, dy)
            if img is None:
                return uikit.fail(src, EXIT_NO_PANEL, '截圖失敗')
            if rows is None:
                rows = parse(img, tpl, _ocr_title)
            _learn_page(img, rows, tpl)
            row = find_row(rows, name)
            if row:
                break
            sig = [(r['title'], r['status']) for r in rows]
            if sig == prev_sig:
                break
            prev_sig = sig
        if not row:
            return uikit.fail(src, EXIT_NOT_FOUND, f'列表裡找不到「{name}」')
        if skip_ok and row['status'] in (DONE, DOING):
            LAST['state'] = 'done' if row['status'] == DONE else 'doing'
            print(f'{src}：「{name}」狀態 {row["status"]}，不接（關面板）')
            return 0
        if row['status'] != PENDING:
            return uikit.fail(src, EXIT_NOT_PENDING, f'「{name}」狀態是 {row["status"]}，不是待接取，不接（不傳送）')
        if not uikit.safe_click(ROW_CLICK_X, row['cy'], PANEL, note=f'questdetail 選 {name}', wait_ms=int(SETTLE_S * 1000)):
            return uikit.fail(src, EXIT_NO_PANEL, '面板特徵消失，沒點')
        img = _stable_shot()
        if img is None:
            return uikit.fail(src, EXIT_NO_PANEL, '點列後截圖失敗')
        head, how = _read_head(img, tpl)
        if head != name:
            return uikit.fail(src, EXIT_HEAD_MISMATCH, f'點列後中間標題是「{head}」，不是「{name}」→ 不傳送')
        if how == 'ocr':
            if learn_tpl(tpl, 'head', name, head_bitmap(img)):
                save_tpl(tpl)
        if not transfer_button(img):
            return uikit.fail(src, EXIT_NOT_TRANSFER, '中間按鈕不是藍色「傳送」（可能是「重置任務」）→ 不點')
        if dry_run:
            print(f'{src}：dry-run：「{name}」待接取、標題相符、藍色傳送鈕在 → 會點傳送 {BTN}（沒點）')
            return 0
        if not uikit.safe_click(BTN[0], BTN[1], PANEL, note=f'questdetail 傳送到 {name} 的接取 NPC', allow=('center_btn',), wait_ms=500):
            return uikit.fail(src, EXIT_NO_PANEL, '面板特徵消失，沒點傳送')
        clicked_transfer = True
    finally:
        if not clicked_transfer:
            close_detail()
    return _after_transfer(src, name, presses, verify)


NOTICE_OK, NOTICE_X = (714, 557), (946, 208)            # 「提示」視窗的確定鈕 / ✕


def notice_open() -> bool:
    """米色「提示」視窗（例：接取任務條件不達標）開著"""
    return uikit.sig_match(screen_sigs.NET_DIALOG)


def dismiss_notice() -> bool:
    """點提示視窗的 ✕ 關掉並確認消失（確定鈕與 ✕ 效果相同；用 ✕ 不會誤觸視窗後面）"""
    for _ in range(2):
        uikit.gui('seq', f'click {NOTICE_X[0]} {NOTICE_X[1]}; wait 600', note='questdetail 關提示視窗')
        if not notice_open():
            return True
    return False


def _dialog_wait(timeout: float = 20.0) -> str | None:
    """傳送後等：回 'dialog'（NPC 對話框）/ 'notice'（提示視窗，例：條件不達標）/ None（逾時）"""
    end = clock() + timeout
    while clock() < end:
        if notice_open():
            return 'notice'
        s = uikit.screen()
        if s.get('state') == 'dialog':
            return 'dialog'
        sleep(0.5)
    return None


def _after_transfer(src: str, name: str, presses: int, verify: bool = True) -> int:
    got = _dialog_wait()
    if got == 'notice':
        shot = uikit.snap('questdetail-notice')
        dismiss_notice()
        close_detail()
        return uikit.fail(src, EXIT_NOT_QUALIFIED, f'傳送後跳「提示」視窗（多半是「接取任務條件不達標」：前置任務 / 等級 / 道具不足）→ 已關閉，沒接 [{shot}]')
    if not got:
        close_detail()
        return uikit.fail(src, EXIT_NO_DIALOG, f'傳送後 20 秒內沒出現 NPC 對話框（「{name}」）；不點，請看畫面')
    import quest
    for i in range(presses):
        g = quest.check_dialog_irreversible()
        btns = ''.join(g.get('buttons', []))
        if g['blocked'] or '接受' not in btns:
            shot = uikit.snap('questdetail-dialog')
            why = g['reason'] or f'左鈕不是「接受」（讀到 {g.get("buttons")}）'
            return uikit.fail(src, EXIT_DIALOG_GUARD, f'對話框防護：{why}；內文 {g.get("body")} → 沒按任何鈕 [{shot}]')
        uikit.gui('seq', f'click {quest.DIALOG_NEXT[0]} {quest.DIALOG_NEXT[1]}; wait 1200', note=f'questdetail 對話框「接受」{name}')
        s = uikit.screen()
        if s.get('state') != 'dialog':
            break
    if not verify:
        sleep(1.0)
        if uikit.screen().get('state') == 'dialog':
            return uikit.fail(src, EXIT_NOT_ACCEPTED, '按了接受但對話框還在（沒接成？），不重點')
        LAST['state'] = 'accepted'
        print(f'{src}：「{name}」已按接受（對話框已收起；不重開詳情驗證）')
        return 0
    # 驗證：重開詳情看狀態
    sleep(1.0)
    if not open_detail():
        return uikit.fail(src, EXIT_NOT_ACCEPTED, '接受後任務詳情打不開，無法驗證')
    try:
        tpl = load_tpl()
        if not select_tab(tab_of(name)):
            return uikit.fail(src, EXIT_NOT_ACCEPTED, '接受後切不到分頁，無法驗證')
        r = read_list(tab_of(name))
    finally:
        close_detail()
    row = find_row(r['rows'], name)
    if row and row['status'] == DOING:
        print(f'{src}：「{name}」已接取（進行中）')
        return 0
    return uikit.fail(src, EXIT_NOT_ACCEPTED, f'接受後讀到狀態 {row["status"] if row else "找不到"}，不是進行中')


# ---------------------------------------------------------------- CLI
def _fmt_status(res: dict, show_all: bool) -> str:
    lines = []
    for n, s in res['tasks'].items():
        lines.append(f'{n}\t{s or "（列表沒有）"}')
    if show_all:
        lines.append('--- 其他 ---')
        lines += [f'{n}\t{s}' for n, s in res['others'].items()]
    if res.get('unknown'):
        lines.append(f'（{res["unknown"]} 列標題不認得）')
    if res.get('gaps'):
        lines.append(f'（警告：{res["gaps"]} 次相鄰頁沒有共同列，可能漏列）')
    return '\n'.join(lines)


def cmd_read_image(path: str) -> int:
    img = Img.from_file(path)
    tpl = load_tpl()
    print('active tab:', tab_active(img), '| 傳送鈕:', transfer_button(img))
    head, _, _ = match_title(head_bitmap(img), 'head', tpl)
    print('head:', head)
    for r in parse(img, tpl):
        print(f'y={r["cy"]:4d} {r["status"]}\t{r["title"]}\t({r["how"]} {r["score"]})')
    return 0


def cmd_learn_image(path: str, titles: list, head: str | None) -> int:
    img = Img.from_file(path)
    tpl = load_tpl()
    rows = visible_rows(img)
    if len(rows) != len(titles):
        print(f'列數 {len(rows)} ≠ 給的標題數 {len(titles)}', file=sys.stderr)
        return 1
    n = 0
    for r, t in zip(rows, titles):
        name = snap_name(t, 0.9)
        if not name:
            print(f'「{t}」不在任務表', file=sys.stderr)
            return 1
        n += learn_tpl(tpl, 'row', name, r['bm'])
    if head:
        h = snap_name(head, 0.9)
        if not h:
            print(f'head「{head}」不在任務表', file=sys.stderr)
            return 1
        n += learn_tpl(tpl, 'head', h, head_bitmap(img))
    save_tpl(tpl)
    print(f'新增 {n} 個樣板')
    return 0


def main() -> int:
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest='cmd', required=True)
    p = sub.add_parser('status'); p.add_argument('--json', action='store_true'); p.add_argument('--all', action='store_true')
    p.add_argument('--dy', type=int, default=None)
    p = sub.add_parser('list'); p.add_argument('--tab', default='支線', choices=['主線', '支線']); p.add_argument('--json', action='store_true')
    p.add_argument('--dy', type=int, default=None)
    p = sub.add_parser('accept'); p.add_argument('title'); p.add_argument('--dry-run', action='store_true')
    p.add_argument('--dy', type=int, default=None); p.add_argument('--presses', type=int, default=2)
    p = sub.add_parser('read-image'); p.add_argument('path')
    p = sub.add_parser('learn-image'); p.add_argument('path'); p.add_argument('titles'); p.add_argument('--head')
    a = ap.parse_args()
    if a.cmd == 'read-image':
        return cmd_read_image(a.path)
    if a.cmd == 'learn-image':
        return cmd_learn_image(a.path, [t for t in a.titles.split(',') if t], a.head)
    if a.cmd == 'accept':
        return accept(a.title, a.dry_run, a.dy, a.presses)
    rc = uikit.preflight('questdetail')
    if rc:
        return rc
    if a.cmd == 'status':
        res = status(dy=a.dy)
        if a.json:
            print(json.dumps(res, ensure_ascii=False, indent=1))
        elif res.get('ok'):
            print(_fmt_status(res, a.all))
        else:
            print(f'questdetail：失敗 {res}', file=sys.stderr)
        return 0 if res.get('ok') else res.get('rc', EXIT_NO_PANEL)
    # list
    if not open_detail():
        return uikit.fail('questdetail', EXIT_NO_PANEL, '任務詳情打不開')
    try:
        r = read_list(a.tab, a.dy)
    finally:
        close_detail()
    if a.json:
        print(json.dumps(r, ensure_ascii=False, indent=1))
    else:
        for x in r['rows']:
            print(f'{x["title"] or "?"}\t{x["status"]}')
        if r['gaps']:
            print(f'（警告：{r["gaps"]} 次相鄰頁沒有共同列）')
    return 0 if r['ok'] else EXIT_NOT_FOUND


if __name__ == '__main__':
    sys.exit(main())
