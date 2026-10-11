#!/usr/bin/env python3
"""背包 / 倉庫腳本化（rebirth.py 用）：讀等級、找道具、使用、穿戴、丟棄、公共倉庫取出 / 存入、換武器。只用標準函式庫。

**實機驗證狀態（2026-10-11 寫成時）：整支沒有在遊戲上跑過**（寫的當下遊戲被別的 agent 佔用）。座標 / 特徵取自
ui/bag.md 的實測記錄與既有截圖（背包外框特徵由 tools/.cache 的 4 張背包截圖 + 倉庫 / 寵物面板負例比對），
彈窗 / 提示窗 / 等級讀取 / buff 圖示的特徵只有單張樣本，第一次實跑要看 snap（tools/.cache/ui-log/）修正。
所有動作都是「驗證 → 點 → 驗證」，驗證不過就停、回退出碼、不重點（絕不盲點，見 ui/bag.md 的「取出 732,648 誤進刪除管理」事故）。

用法（專案根目錄；WSL / Windows 原生相同；角色名 DKBO / DKB0 都收）：
  uv run --no-project python tools/gui/bag.py level DKBO|all              # 唯讀：「N轉M級」（背包中間名牌下方）
  uv run --no-project python tools/gui/bag.py hp DKBO|all                 # 唯讀：每人 HP（背包頁 HP 條上的「目前/最大」；回 [目前, 最大, %]）
  uv run --no-project python tools/gui/bag.py find DKBO 精靈王之弓 [名稱…]    # 唯讀：每個名稱在背包哪一格（空格用像素判；「顯示道具名」被關會點開一次）
  uv run --no-project python tools/gui/bag.py use DKBO 龍王的守護           # 背包 → 彈窗名稱核對 → 使用（隊長吃龍王的守護）
  uv run --no-project python tools/gui/bag.py swap-weapon DKBO [--keep-old] # 穿精靈王之弓、丟舊武器（名稱防護）
  uv run --no-project python tools/gui/bag.py take DKBO 龍王的守護 [--depot public|personal]   # 倉庫取出（整疊）
  uv run --no-project python tools/gui/bag.py store DKBO 龍王的守護 [--depot public|personal]  # 倉庫存入
  uv run --no-project python tools/gui/bag.py drop DKBO 名稱 --confirm-name 名稱               # 丟棄背包道具（名稱必須完全對上）
最後一行 JSON {"ok","rc",...}；給其他腳本 import：bag.levels / hps / find_items / use_item / swap_weapon / depot_take / depot_store / drop_item。

退出碼（共用 0 / 1 / 2 / 8 / 9 / 10 見 uikit；bag 自己 90～96）：
  90 背包面板打不開 / 分頁不對 / 中途消失（沒點面板內座標）
  91 左欄角色沒選到（黃框不對 / 名牌不是該角色）
  92 找不到指定道具（背包或倉庫沒有）
  93 防護擋下（要丟的名稱是精靈王之弓 / 不是預期名稱 / 沒給舊武器名稱…），零丟棄點擊
  94 倉庫 / 背包滿
  95 動作後驗證失敗（不重點；請人看 snap）
  96 彈窗 / 提示窗名稱 OCR 對不上或讀不到（不點確定）

防護原則：
  - 丟棄：彈窗名稱與提示窗名稱都必須模糊吻合「預期名稱」，且不能吻合 PROTECT（精靈王之弓…）；任何一塊讀不到 = 不丟。
  - 紅區（uikit.Panel.forbidden）：刪除管理、擴容、丟棄鈕；只有 drop_item 內 allow=('discard',) 才點丟棄鈕。
  - 道具浮窗按鈕座標依按鈕文字（OCR）決定：裝備 穿戴 618,662 / 丟棄 826,662；消耗品 使用 628,648 / 丟棄 838,648；
    可疊加 使用 618,648 / 更多 825,648；只有一顆 使用 732,648；倉庫取出 消耗品 732,648 / 裝備 722,662（ui/bag.md）。
"""
import argparse
import difflib
import json
import re
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import charstate  # noqa: E402
import petmatch  # noqa: E402
import uikit  # noqa: E402

SRC = 'bag'
EXIT_PANEL, EXIT_SELECT, EXIT_ITEM, EXIT_GUARD, EXIT_FULL, EXIT_VERIFY, EXIT_NAME = 90, 91, 92, 93, 94, 95, 96

# ---- 版面（2880×1659 截圖座標）----
BAG_BTN, CLOSE_XY = (1120, 760), (1280, 113)
TAB_BAG, TAB_DEPOT = (1318, 265), (1318, 467)
SUB_XY = {'personal': (307, 200), 'public': (547, 200)}
SUB_PROBE = {'personal': (230, 200), 'public': (480, 200)}        # 選中 = 亮黃 (251,219,135)；沒選 = (171,127,84)
SUB_ON = (251, 219, 135)
SLOT_X, SLOT_Y = [752, 860, 966, 1072, 1180], [245, 352, 460]     # 背包格 5×3 可見（ui/bag.md 寫 5×4；第 4 列 / 捲動未量）
DEPOT_X, DEPOT_Y = [237, 331, 425, 520, 614], [290, 385, 480, 575]
WEAPON_SLOT = (233, 372)                                            # 裝備格左欄第 3 個（弓箭圖示）
SLOT_NAME_R = (52, 44, 104, 52)                                     # 格子名稱 OCR 框 = (x-52, y-44, 104, 52)
POPUP_NAME_BOX = (590, 133, 240, 40)
POPUP_BTN_BOX = (560, 625, 380, 60)
LEVEL_BOX = (330, 203, 200, 28)                                     # 「0轉133級」綠字
HP_BOX = (260, 540, 150, 24)                                        # 背包頁左下 HP 條上的「440/571」白字（選中角色的；2026-10-12 實測 OCR 3 種門檻都讀得到）
NAME_BOX = (330, 176, 200, 26)                                      # 名牌「DKBO」
BUFF_BOX = (78, 150, 40, 40)                                        # 龍王的守護 buff 圖示（左上、任務欄上方，約 97,170）
DISCARD_OK = (612, 551)                                             # 提示窗確定 / 丟棄（ui/bag.md 612,544；pet 提示窗 615,557 → 取中間）

FORBID = {'delete_mgr': (700, 598, 540, 56), 'expand': (190, 646, 170, 74)}
CHROME = [(1280, 113, 197, 70, 43, 30), (730, 688, 50, 95, 150, 30), (730, 625, 168, 55, 32, 30)]
TAB_BAG_SIG = [(230, 683, 223, 187, 147, 24), (520, 683, 223, 187, 147, 24)]
TAB_DEPOT_SIG = [(230, 683, 135, 100, 66, 24), (520, 683, 78, 60, 42, 24)]
POPUP_SIG = [(958, 250, 200, 138, 69, 22), (958, 400, 197, 136, 67, 22), (720, 718, 169, 117, 58, 22), (700, 480, 46, 36, 30, 25)]
BAGANY = uikit.Panel('BAGANY', BAG_BTN, CHROME, CLOSE_XY, forbidden=FORBID)
BAG = uikit.Panel('BAG', None, CHROME + TAB_BAG_SIG, CLOSE_XY, forbidden=FORBID)
DEPOT = uikit.Panel('BAGDEPOT', None, CHROME + TAB_DEPOT_SIG, CLOSE_XY, forbidden=FORBID)
# 第二組：右下框線 + 彈窗內暗底兩點（多行說明的倉庫取出彈窗；2倍智慧果實測，樣本 tools/.cache/ui-log/110407-bag-depot-nopopup.png 為無彈窗負例）。
POPUP_SIG2 = [(968, 500, 183, 127, 64, 25), (730, 230, 38, 28, 22, 22), (600, 600, 35, 26, 22, 22)]
# 第三組：說明只有 1 行的短彈窗（龍王的守護，標題 y≈270、框高約 228～704）：左 / 右 / 下三邊金框（2026-10-11 實測）。
POPUP_SIG3 = [(492, 400, 189, 130, 65, 25), (968, 400, 184, 127, 64, 25), (700, 704, 196, 133, 65, 25)]
# 第四組：裝備彈窗（穿戴 / 丟棄，高框 y≈137～718，右框 x=958、下框 y=718，2026-10-11 實測馬祖的斧頭）；前三組都不吻合 → close_popup 以為沒彈窗不送 ESC，彈窗留著擋住後續點格
POPUP_SIG4 = [(958, 160, 185, 128, 66, 22), (958, 300, 185, 128, 66, 22), (700, 718, 187, 128, 63, 22), (800, 718, 187, 128, 63, 22)]


def _popup_sig_open() -> bool:
    """三種彈窗高度（多行 / 中 / 短說明）任一組特徵吻合就算彈窗開著"""
    return any(uikit.sig_match(g) for g in (POPUP_SIG, POPUP_SIG2, POPUP_SIG3, POPUP_SIG4))


POPUP = uikit.Panel('BAGPOPUP', None, POPUP_SIG, None, forbidden={'discard': (770, 625, 130, 60)}, is_open_fn=_popup_sig_open)

# 絕不能丟 / 存的名稱（模糊吻合就擋）
PROTECT = ['精靈王之弓']
WAIT_S = 2.0
POLL_S = 0.15
LAST: dict = {}


def log(msg: str) -> None:
    print(f'bag：{msg}', file=sys.stderr, flush=True)


# ---- 名稱比對（純函式）----
def norm_name(t) -> str:
    """去空白 / 標點 / 方括號內容（[地] [水]…）；OCR 常把空白、全半形弄亂"""
    s = re.sub(r'[\[【（(][^\]】）)]*[\]】）)]', '', str(t or ''))
    return re.sub(r'[\s\W_]+', '', s)


def name_match(text, want, cutoff: float = 0.72) -> bool:
    """text（OCR 文字，可含多行）是否吻合 want：完全包含，或整體相似度 >= cutoff（OCR 錯一兩字仍過）"""
    a, w = norm_name(text), norm_name(want)
    if not a or not w:
        return False
    if w in a:
        return True
    if difflib.SequenceMatcher(None, a, w).ratio() >= cutoff:
        return True
    # 名字被兩行切開或前後多字：用最佳子字串視窗
    n = len(w)
    return any(difflib.SequenceMatcher(None, a[i:i + n], w).ratio() >= cutoff for i in range(max(1, len(a) - n + 1)))


def protected(text) -> str | None:
    for p in PROTECT:
        if name_match(text, p, 0.8):
            return p
    return None


def parse_level(text) -> tuple | None:
    """'0轉133級' → (0, 133)；讀不出 None（容許 OCR 把「轉」讀成別字）"""
    t = re.sub(r'\s+', '', str(text or ''))
    m = re.search(r'(\d)轉(\d{1,3})級', t) or re.search(r'(\d)\D{1,2}(\d{1,3})級', t)
    return (int(m[1]), int(m[2])) if m else None


def parse_hp(lines) -> tuple | None:
    """OCR 各行 → (目前 HP, 最大 HP)：每行抓「數字/數字」、目前 ≤ 最大 > 0，取出現最多次的那組（OCR 偶爾把 440 讀成「4姍」）；讀不出 None"""
    votes = {}
    for t in lines or []:
        m = re.search(r'(\d{1,5})\s*/\s*(\d{1,5})', str(t))
        if m:
            v = (int(m[1]), int(m[2]))
            if 0 < v[1] and v[0] <= v[1]:
                votes[v] = votes.get(v, 0) + 1
    return max(votes, key=lambda v: (votes[v], v[1])) if votes else None


def slot_xy(i: int) -> tuple:
    return SLOT_X[i % 5], SLOT_Y[i // 5]


def depot_xy(i: int) -> tuple:
    return DEPOT_X[i % 5], DEPOT_Y[i // 5]


def popup_buttons(text) -> dict:
    """彈窗按鈕列文字 → {'kind', 按鈕: (x, y)}（依 ui/bag.md 的座標表；kind = equip / stack / consumable / single / depot）"""
    t = re.sub(r'\s+', '', str(text or ''))
    d = {}
    if '穿戴' in t:
        d.update(kind='equip', 穿戴=(618, 662), 丟棄=(826, 662))
    elif '取出' in t:
        d.update(kind='depot', 取出=(732, 648))
    elif '存入' in t:
        d.update(kind='depot', 存入=(732, 648))
    elif '使用' in t and '更多' in t:
        d.update(kind='stack', 使用=(618, 648))
    elif '使用' in t and '丟棄' in t:
        d.update(kind='consumable', 使用=(628, 648), 丟棄=(838, 648))
    elif '使用' in t:
        d.update(kind='single', 使用=(732, 648))
    return d


# ---- 遊戲存取縫（測試替換）----
def _avatar_sel(role: str) -> bool:
    """左欄頭像黃框剛好只有該角色（與寵物面板同版面：petmatch.AVATAR_TOP_Y）"""
    import pet
    roles = list(petmatch.AVATAR_Y)
    cols = uikit.px([(83, petmatch.AVATAR_TOP_Y[r]) for r in roles])
    if not cols:
        return False
    sel = [pet.is_avatar_sel(c) for c in cols]
    return sel == [r == role for r in roles]


def _sub_on(sub: str) -> bool:
    cols = uikit.px([SUB_PROBE[sub]])
    return bool(cols) and all(abs(a - b) <= 24 for a, b in zip(cols[0], SUB_ON))


BUFF_SLOTS = [(76 + 46 * k, 150, 44, 45) for k in range(3)]      # 左上 buff 列（頭像下方）：每格約 46 px 寬，最多 3 格並排
BUFF_STEP = 3


def buff_classify(getpx) -> list:
    """純函式：getpx(x, y) → (r, g, b)；回每個 buff 格的種類 'dragon'（龍王的守護：深藍底 + 青白發光人形剪影）/ 'exp'（2倍智慧果：藍底 + 白色 EXP 字與箭頭）/ None（空格）。
    1440×830 截圖實測（2026-10-11，tools/gui/fixtures/buff_row.png）：人形 青 cyan(r<140,g>110,b>140) 約 280/2025 點（EXP 143）、深藍 navy 805（EXP 422）、白 white(>200) 10（EXP 283）→
    以 white 分：white 多 = EXP；cyan 夠多且 white 少 = 人形；兩者都不夠 = 空格。步距 3 px 取樣（點數 /9）"""
    out = []
    for x0, y0, w, h in BUFF_SLOTS:
        cyan = navy = white = 0
        for y in range(y0, y0 + h, BUFF_STEP):
            for x in range(x0, x0 + w, BUFF_STEP):
                r, g, b = getpx(x, y)
                cyan += r < 140 and g > 110 and b > 140
                navy += r < 60 and g < 70 and b < 110
                white += r > 200 and g > 200 and b > 200
        if white >= 12:
            out.append('exp')
        elif cyan >= 15 and navy >= 40 and white <= 6:
            out.append('dragon')
        else:
            out.append(None)
    return out


def buff_row() -> list | None:
    """現場讀 buff 列 → buff_classify 結果；讀不到 None"""
    pts = [(x, y) for x0, y0, w, h in BUFF_SLOTS for y in range(y0, y0 + h, BUFF_STEP) for x in range(x0, x0 + w, BUFF_STEP)]
    cols = uikit.px(pts)
    if not cols:
        return None
    d = dict(zip(pts, cols))
    return buff_classify(lambda x, y: d[(x, y)])


def _buff_icon() -> bool:
    """龍王的守護人形圖示在 buff 列嗎（不會被 2倍智慧果 EXP 圖示騙到）；讀不到 = False"""
    return 'dragon' in (buff_row() or [])


def _click(x: int, y: int, panel, note: str, allow=(), wait_ms: int = 350) -> bool:
    return uikit.safe_click(x, y, panel, note=note, allow=allow, wait_ms=wait_ms)


def _wait(pred, secs: float = WAIT_S) -> bool:
    end = uikit.clock() + secs
    while True:
        if pred():
            return True
        if uikit.clock() >= end:
            return False
        uikit.sleep(POLL_S)


def _fail(rc: int, msg: str, tag: str = '') -> int:
    if tag:
        uikit.snap(tag)
    return uikit.fail(SRC, rc, msg)


def _ocr_join(box, optsets) -> str:
    seen = []
    for o in optsets:
        seen += [t for t in uikit.ocr(box, *o) if t.strip()]
        if seen:
            break
    return ' '.join(seen)


NAME_OPTS = [('-Light', 170, '-Zooms', '2,3'), ('-Dark', 0, '-Zooms', '2,3,4')]
SLOT_OPTS = [('-Light', 170, '-Zooms', '2,3'), ('-Dark', 120, '-Zooms', '2,3')]
LEVEL_OPTS = [('-Dark', 0, '-Zooms', '2,3,4'), ('-Light', 120, '-Zooms', '2,3')]
HP_OPTS = [('-Light', 200, '-Zooms', '2,3,4'), ('-Dark', 0, '-Zooms', '2,3')]
BTN_OPTS = [('-Dark', 140, '-Zooms', '2,3'), ('-Light', 170, '-Zooms', '2,3')]


# ---- 面板 ----
class Session:
    """開背包（本來沒開才開 / 才關）並確保在背包分頁；with 後看 self.rc"""

    def __init__(self):
        self.rc, self.was_open = 0, False

    def __enter__(self):
        self.was_open = uikit.is_open(BAGANY)            # 已開著（外層 Session / 呼叫端開的）就不再 preflight：背包開著時 screen() 會判 unknown，巢狀進入會誤報驗證視窗
        if not self.was_open:
            self.rc = uikit.preflight(SRC)
            if self.rc:
                return self
            ok, _ = uikit.open_panel_ex(BAGANY)
            if not ok:
                self.rc = _fail(EXIT_PANEL, '背包面板打不開（沒看到主畫面 HUD 或背包外框特徵）；沒點任何面板內座標', 'bag-open-fail')
                return self
        if not uikit.is_open(BAG):
            self.rc = goto_page('bag')
        return self

    def __exit__(self, *exc):
        if not self.was_open and uikit.is_open(BAGANY):
            uikit.close_panel(BAGANY, known_open=True)
        return False


def goto_page(page: str) -> int:
    """切背包 / 倉庫分頁並驗證（0 / 90）"""
    panel, xy = (BAG, TAB_BAG) if page == 'bag' else (DEPOT, TAB_DEPOT)
    if uikit.is_open(panel):
        return 0
    if not _click(xy[0], xy[1], BAGANY, f'bag 切到{page}分頁'):
        return _fail(EXIT_PANEL, '背包外框特徵不在，沒點分頁', 'bag-tab')
    if not _wait(lambda: uikit.is_open(panel)):
        return _fail(EXIT_PANEL, f'點了{page}分頁但特徵沒出現', 'bag-tab')
    return 0


def select_role(role: str, ctx: dict | None = None) -> int:
    """左欄點頭像 → 黃框剛好只有該角色 + 名牌 OCR 是該角色（0 / 91）"""
    if role not in petmatch.AVATAR_Y:
        return _fail(uikit.EXIT_USAGE, f'角色 {role!r} 不在五人白名單')
    for _ in range(2):
        if not _click(83, petmatch.AVATAR_Y[role], BAGANY, f'bag 選角色 {role}', wait_ms=500):
            return _fail(EXIT_PANEL, '背包外框特徵不在，沒點頭像', 'bag-avatar')
        if _wait(lambda: _avatar_sel(role), 1.5):
            break
    else:
        return _fail(EXIT_SELECT, f'點了 {role} 頭像但黃框不對', f'bag-select-{role}')
    txt = _ocr_join(NAME_BOX, NAME_OPTS)
    hit = charstate.norm_char(txt) if txt else None
    if hit and not charstate.same(hit, role):
        return _fail(EXIT_SELECT, f'名牌 OCR 是 {hit}，點的是 {role}', f'bag-name-{role}')
    return 0


# ---- 讀 ----
def read_level(role: str) -> tuple | None:
    """目前選中角色的 (轉數, 等級)；讀不出 None"""
    for _ in range(2):
        v = parse_level(_ocr_join(LEVEL_BOX, LEVEL_OPTS))
        if v:
            return v
        uikit.sleep(0.5)
    return None


def levels(roles) -> tuple:
    """→ (rc, {role: (trans, level) | None})"""
    out = {}
    with Session() as s:
        if s.rc:
            return s.rc, out
        for r in roles:
            rc = select_role(r)
            if rc:
                return rc, out
            out[r] = read_level(r)
    return 0, out


def read_hp() -> tuple | None:
    """目前選中角色的 (目前 HP, 最大 HP)（背包頁 HP 條上的字）；讀不出 None"""
    for o in HP_OPTS:
        v = parse_hp(uikit.ocr(HP_BOX, *o))
        if v:
            return v
    return None


def hps(roles) -> tuple:
    """唯讀：開背包逐人點左欄頭像讀 HP → (rc, {role: (目前, 最大) | None})。
    給 questrun 任務之間 / BOSS 後檢查全隊血量（HUD 只有當前角色的 HP；切換面板 / 組隊面板沒有 HP）"""
    out = {}
    with Session() as s:
        if s.rc:
            return s.rc, out
        for r in roles:
            rc = select_role(r)
            if rc:
                return rc, out
            out[r] = read_hp()
    return 0, out


def read_slot_name(i: int, depot: bool = False) -> str:
    x, y = depot_xy(i) if depot else slot_xy(i)
    dx, dy, w, h = SLOT_NAME_R
    return _ocr_join((x - dx, y - dy, w, h), SLOT_OPTS)


POPUP_NAME_ALT = (600, 250, 330, 45)                                # 說明越長標題越高（2倍智慧果 y≈270）；只含標題列


def popup_name() -> str:
    """兩個標題框都讀、串起來（短彈窗時 y133 框在彈窗外，讀到的是 HUD / 聊天雜訊而非空字串，不能「讀不到才用備援」）"""
    return (_ocr_join(POPUP_NAME_BOX, NAME_OPTS) + ' ' + _ocr_join(POPUP_NAME_ALT, NAME_OPTS)).strip()


def is_pair_layout() -> bool:
    """彈窗按鈕列是「使用（藍）+ 更多（橘）」並排：取按鈕左側空白處（不踩到字）560,648 藍、775,648 橘（2026-10-11 龍王的守護實測 (55,106,163) / (183,115,54)；
    單鈕版這兩點是暗底 / 藍）。舊版取 619 / 825 剛好踩到「使用」「更多」的字，永遠判成單鈕 → 點 732 沒反應"""
    cols = uikit.px([(560, 648), (775, 648)]) or []
    if len(cols) != 2:
        return False
    (r, g, b), (r2, g2, b2) = cols
    return b > 130 and r < 110 and r2 > 150 and b2 < 100 and r2 - b2 > 80


def popup_open() -> bool:
    return uikit.is_open(POPUP)


def close_popup() -> bool:
    if not popup_open():
        return True
    uikit.gui('seq', 'key {ESC}; wait 300', note='bag ESC 關道具浮窗')
    return _wait(lambda: not popup_open(), 1.5)


def open_slot_popup(i: int, depot: bool = False) -> bool:
    x, y = depot_xy(i) if depot else slot_xy(i)
    panel = DEPOT if depot else BAG
    if not _click(x, y, panel, f'bag 點{"倉庫" if depot else "背包"}第 {i + 1} 格'):
        return False
    return _wait(popup_open, 1.2)


def n_slots(depot: bool = False) -> int:
    return 20 if depot else 15


# ---- 背包格有沒有東西（像素）/「顯示道具名」開關（2026-10-12 S3：find 回全 null、_free 15 的根因）----
# 「顯示道具名」是背包頁右下的開關鈕（968,561），關掉時格子只剩圖示、沒有名稱 → 格名稱 OCR 全空，
# 舊 find_items 把「OCR 空白」當空格 → 5 人都回 _free 15、全 null（store 走圖示樣板 + 彈窗核對，所以正常）。
# 改成：空格用像素判（空格內部是均勻棕 (104,74,49)，實測兩張樣本 15 格全中、有道具的格 ≥2 點偏離（最窄的小瓶子圖示實測 4 點、空格 0 點）），
# 有道具但名稱 OCR 全空 = 開關被關 → 點一次開關、驗證名稱出現。
NAMES_BTN = (968, 561)
SLOT_EMPTY = (104, 74, 49)
SLOT_EMPTY_TOL = 14
SLOT_PROBE = [(dx, dy) for dx in (-24, -12, 0, 12, 24) for dy in (-20, -10, 0, 10, 20)]   # 格中心周圍 25 點（避開右下數量字）
SLOT_OCC_MIN = 2


def slot_occupied(cols) -> bool:
    """純函式：某格 SLOT_PROBE 各點顏色 → 有沒有道具（≥ SLOT_OCC_MIN 點偏離空格棕）"""
    return sum(1 for c in cols if any(abs(a - b) > SLOT_EMPTY_TOL for a, b in zip(c, SLOT_EMPTY))) >= SLOT_OCC_MIN


def slot_occupancy() -> list | None:
    """背包頁 15 格各有沒有道具（一次 uikit.px）；讀不到 None"""
    pts = [(x + dx, y + dy) for i in range(n_slots()) for x, y in [slot_xy(i)] for dx, dy in SLOT_PROBE]
    cols = uikit.px(pts)
    if not cols or len(cols) != len(pts):
        return None
    k = len(SLOT_PROBE)
    return [slot_occupied(cols[i * k:(i + 1) * k]) for i in range(n_slots())]


def names_hidden(occ, texts) -> bool:
    """純函式：有道具的格至少 1 格、而且全部名稱 OCR 都是空白 → 「顯示道具名」被關了"""
    full = [i for i, o in enumerate(occ or []) if o]
    return bool(full) and all(not str(texts.get(i) or '').strip() for i in full)


def ensure_names_shown(occ: list | None = None) -> bool | None:
    """背包頁：名稱沒顯示就點「顯示道具名」一次並驗證（第一個有道具的格名稱 OCR 讀得到）。
    → True（本來就顯示 / 點了後出現）、False（點了仍讀不到，不再點）、None（沒有道具，無從判斷）"""
    occ = occ if occ is not None else slot_occupancy()
    first = next((i for i, o in enumerate(occ or []) if o), None)
    if first is None:
        return None
    if read_slot_name(first).strip():
        return True
    if not _click(NAMES_BTN[0], NAMES_BTN[1], BAG, 'bag 背包名稱沒顯示 → 點「顯示道具名」', wait_ms=600):
        return False
    ok = _wait(lambda: bool(read_slot_name(first).strip()), 2.0)
    log('已打開「顯示道具名」' if ok else '點了「顯示道具名」名稱仍讀不到')
    return ok


ICON_FILE = HERE / 'fixtures' / 'item_icons.json'         # {名稱: {'bag': [[dx,dy,r,g,b],…], 'depot': […]}}：格子中心周圍 9×9 點的圖示顏色（背包格與倉庫格圖示大小不同，各一份）
POPUP_SETTLE_S = 1.0
ICON_TOL, ICON_RATIO, ICON_RATIO_LOOSE = 40, 0.85, 0.45


def load_icons() -> dict:
    try:
        return json.loads(ICON_FILE.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return {}


def icon_match_slots(want: str, depot: bool = False) -> list | None:
    """兩段式找道具的第一段：用圖示樣板（格子中心周圍像素）比對所有格，回吻合的格號（0 起算，可為空）。
    沒有該道具的樣板 → None（呼叫端改走名稱 OCR / 彈窗核對）。一次 uikit.px 讀完所有格，只讀不點"""
    tpl = (load_icons().get(want) or {}).get('depot' if depot else 'bag')
    if not tpl:
        return None
    pts, owner = [], []
    for i in range(n_slots(depot)):
        cx, cy = depot_xy(i) if depot else slot_xy(i)
        for d in tpl:
            pts.append((cx + d[0], cy + d[1]))
            owner.append(i)
    cols = uikit.px(pts)
    if not cols:
        return []
    hit = {}
    for k, (i, c) in enumerate(zip(owner, cols)):
        d = tpl[k % len(tpl)]
        hit[i] = hit.get(i, 0) + (all(abs(a - b) <= ICON_TOL for a, b in zip(c, d[2:])))
    strict = [i for i in range(n_slots(depot)) if hit.get(i, 0) >= ICON_RATIO * len(tpl)]
    if strict:
        return strict
    # 嚴格比對一格都不中（堆疊數 / 格位背景不同會掉到約 0.55，其他道具實測 ≤ 0.32）→ 放寬一次；
    # 後面一定有彈窗標題 + 按鈕列核對，放寬只多開幾個候選格，不會誤用
    return sorted((i for i in range(n_slots(depot)) if hit.get(i, 0) >= ICON_RATIO_LOOSE * len(tpl)),
                  key=lambda i: -hit.get(i, 0))


def find_item(want: str, depot: bool = False, popup_fallback: bool = True) -> int | None:
    """want 在目前頁（背包 / 倉庫左半）的格號（0 起算）。
    有圖示樣板：① 圖示比對只挑吻合的格（不掃全部格）→ ② 點進去核對彈窗名稱，相符才回傳（不靠格名 OCR，不逐格開彈窗）。
    沒樣板：逐格 OCR 名稱；找不到再逐格開彈窗讀名稱（慢、保險）"""
    cand = icon_match_slots(want, depot)
    if cand is not None:
        for i in cand:
            if not open_slot_popup(i, depot):
                continue
            nm = popup_name()
            close_popup()
            if nm and name_match(nm, want):
                return i
        return None
    if not depot:
        ensure_names_shown()                          # 名稱被關掉時格名稱 OCR 全空，只能逐格開彈窗（慢）
    unread = []
    for i in range(n_slots(depot)):
        t = read_slot_name(i, depot)
        if t and name_match(t, want):
            return i
        unread.append((-sum(1 for c in set(norm_name(want)) if c in norm_name(t)), i))
    if not popup_fallback:
        return None
    for _, i in sorted(unread):                       # 名稱 OCR 有重疊字的格先開（龍王的守護格曾被讀成「守 4-0」）
        if not open_slot_popup(i, depot):
            continue                                  # 空格不會開彈窗
        nm = popup_name()
        close_popup()
        if nm and name_match(nm, want):
            return i
    return None


def find_items(role: str, names) -> tuple:
    """唯讀（唯一可能的點擊是「顯示道具名」開關）：→ (rc, {名稱: 格號 | None, '_free': 空格數, '_unread': 有道具但名稱讀不到的格號})。
    空格用像素判（slot_occupancy），只對有道具的格做名稱 OCR；名稱全空 = 「顯示道具名」被關 → 點開再讀（2026-10-12 S3 根因）。
    像素讀不到時退回舊法（OCR 空白 = 空格，可能高估）"""
    out = {}
    with Session() as s:
        if s.rc:
            return s.rc, out
        rc = select_role(role)
        if rc:
            return rc, out
        occ = slot_occupancy()
        idx = [i for i in range(n_slots()) if occ is None or occ[i]]
        texts = {i: read_slot_name(i) for i in idx}
        if occ is not None and names_hidden(occ, texts):
            if ensure_names_shown(occ):
                texts = {i: read_slot_name(i) for i in idx}
        todo = list(names)
        for i in idx:
            t = texts[i]
            for nm in list(todo):
                if t and name_match(t, nm):
                    out[nm] = i
                    todo.remove(nm)
        for nm in todo:
            out[nm] = None
        if occ is None:
            out['_free'] = sum(1 for i in idx if not texts[i].strip())
        else:
            out['_free'] = occ.count(False)
            out['_unread'] = [i for i in idx if not texts[i].strip()]
    return 0, out


# ---- 彈窗動作 ----
def click_popup_button(label: str, allow=()) -> tuple:
    """彈窗開著：OCR 按鈕列 → 依文字決定座標 → 點 label。回 (rc, kind)"""
    txt = _ocr_join(POPUP_BTN_BOX, BTN_OPTS)
    b = popup_buttons(txt)
    if label not in b:
        return _fail(EXIT_NAME, f'彈窗按鈕列 OCR 是 {txt!r}，找不到「{label}」鈕（不點）', 'bag-popup-btn'), b.get('kind')
    x, y = b[label]
    if label == '使用' and b.get('kind') == 'single' and is_pair_layout():
        x = 619                                       # OCR 漏讀「更多」→ 誤判單鈕，732 點在兩鈕中間沒反應（2026-10-11 龍王的守護根因）
    uikit.sleep(POPUP_SETTLE_S)                       # 彈窗動畫期間點按鈕會落空
    if not _click(x, y, POPUP, f'bag 彈窗 {label}', allow=allow, wait_ms=500):
        return _fail(EXIT_PANEL, '彈窗特徵消失，沒點按鈕', 'bag-popup-gone'), b.get('kind')
    return 0, b['kind']


def use_item(role: str, want: str, verify_buff: bool = False) -> int:
    """背包找 want → 彈窗名稱核對 → 使用。verify_buff = 用 buff 圖示確認（找不到只警告，不重點）。結果 LAST['buff']"""
    LAST.clear()
    with Session() as s:
        if s.rc:
            return s.rc
        rc = select_role(role)
        if rc:
            return rc
        i = find_item(want)
        if i is None:
            return _fail(EXIT_ITEM, f'{role} 背包找不到「{want}」', 'bag-noitem')
        if not open_slot_popup(i):
            return _fail(EXIT_PANEL, f'點第 {i + 1} 格沒開彈窗', 'bag-nopopup')
        nm = popup_name()
        if not name_match(nm, want):
            close_popup()
            return _fail(EXIT_NAME, f'彈窗名稱 OCR 是 {nm!r}，不是「{want}」（不使用）', 'bag-popup-name')
        rc, _ = click_popup_button('使用')
        if rc:
            close_popup()
            return rc
        if not _wait(lambda: not popup_open(), 2.0):
            if not verify_buff:
                return _fail(EXIT_VERIFY, '按了使用但彈窗沒關（不重點）', 'bag-use-verify')
            close_popup()                                # 疊加道具使用後彈窗可能還開著：ESC 關掉，不重點，成敗交給 buff 圖示判斷
            LAST['popup_stayed'] = True
        if verify_buff:
            LAST['buff'] = _wait(_buff_icon, 3.0)
            if not LAST['buff']:
                log('警告：使用後沒看到 buff 圖示（特徵只有單張樣本，可能讀不到；不重點）')
                uikit.snap('bag-buff-unseen')
    return 0


def equipped_name() -> str | None:
    """武器格彈窗名稱（空格 = 沒彈窗 → None）；讀完 ESC 關"""
    if not _click(WEAPON_SLOT[0], WEAPON_SLOT[1], BAG, 'bag 點武器格'):
        return None
    if not _wait(popup_open, 1.2):
        return None
    nm = popup_name()
    close_popup()
    return nm or None


def discard_item(role: str, slot: int, expect: str, forbid=None) -> int:
    """丟棄背包第 slot 格（假設已選好角色、在背包分頁）。彈窗名稱與提示窗名稱都必須吻合 expect 且不吻合 PROTECT / forbid。
    丟棄鈕只有這裡用 allow=('discard',) 點。成功 = 提示窗關了且該格名稱不再吻合"""
    bad = list(PROTECT) + list(forbid or [])
    if protected(expect) or any(name_match(expect, b, 0.8) for b in bad):
        return _fail(EXIT_GUARD, f'要丟的名稱「{expect}」在保護名單（{bad}）內，拒絕')
    if not open_slot_popup(slot):
        return _fail(EXIT_PANEL, f'第 {slot + 1} 格沒開彈窗（空格？），不丟', 'bag-drop-nopopup')
    nm = popup_name()
    if not nm or not name_match(nm, expect) or any(name_match(nm, b, 0.8) for b in bad):
        close_popup()
        return _fail(EXIT_NAME, f'彈窗名稱 OCR 是 {nm!r}，不是預期的「{expect}」（或在保護名單）→ 不丟', 'bag-drop-name')
    rc, kind = click_popup_button('丟棄', allow=('discard',))
    if rc:
        close_popup()
        return rc
    import pet
    if not _wait(lambda: uikit.is_open(pet.CONFIRM), 2.0):
        return _fail(EXIT_VERIFY, '按了丟棄但提示窗沒出現（不重點）', 'bag-drop-noconfirm')
    ct = _ocr_join(pet.CONFIRM_BOX, [('-Dark', 0, '-Zooms', '2,3,4'), ('-Dark', 120, '-Zooms', '2,3')])
    if not ct or not name_match(ct, expect) or any(name_match(ct, b, 0.8) for b in bad):
        uikit.safe_click(813, 557, pet.CONFIRM, note='bag 丟棄提示窗名稱不符 → 取消')
        return _fail(EXIT_NAME, f'提示窗名稱 OCR 是 {ct!r}，不是預期的「{expect}」→ 已取消', 'bag-drop-confirm-name')
    if not uikit.safe_click(DISCARD_OK[0], DISCARD_OK[1], pet.CONFIRM, note=f'bag 丟棄「{expect}」確定', wait_ms=600):
        return _fail(EXIT_VERIFY, '提示窗特徵消失，沒點確定', 'bag-drop-confirm-gone')
    if not _wait(lambda: not uikit.is_open(pet.CONFIRM), 2.5):
        return _fail(EXIT_VERIFY, '按了確定但提示窗沒關（不重點）', 'bag-drop-verify')
    left = read_slot_name(slot)
    if left and name_match(left, expect):
        return _fail(EXIT_VERIFY, f'丟完第 {slot + 1} 格仍讀到「{expect}」', 'bag-drop-still')
    LAST['dropped'] = expect
    return 0


def drop_item(role: str, want: str, confirm_name: str) -> int:
    """CLI / 外部呼叫：want 與 confirm_name 必須相同才動手（防手誤）"""
    if norm_name(want) != norm_name(confirm_name):
        return _fail(EXIT_GUARD, f'--confirm-name {confirm_name!r} 與名稱 {want!r} 不同，不丟')
    LAST.clear()
    with Session() as s:
        if s.rc:
            return s.rc
        rc = select_role(role)
        if rc:
            return rc
        i = find_item(want)
        if i is None:
            return _fail(EXIT_ITEM, f'{role} 背包找不到「{want}」', 'bag-noitem')
        return discard_item(role, i, want)


def swap_weapon(role: str, bow: str = '精靈王之弓', keep_old: bool = False) -> int:
    """穿 bow、確認武器格是 bow、（預設）丟舊武器。舊武器名稱 = 穿之前武器格彈窗名稱；讀不到就不丟。結果 LAST"""
    LAST.clear()
    with Session() as s:
        if s.rc:
            return s.rc
        rc = select_role(role)
        if rc:
            return rc
        cur = equipped_name()
        LAST['old'] = cur
        if cur and name_match(cur, bow):
            LAST['already'] = True
            return 0                                    # 已經是弓（續跑）；舊武器早丟過
        i = find_item(bow)
        if i is None:
            return _fail(EXIT_ITEM, f'{role} 背包找不到「{bow}」', 'bag-nobow')
        if not open_slot_popup(i):
            return _fail(EXIT_PANEL, f'點第 {i + 1} 格沒開彈窗', 'bag-nopopup')
        nm = popup_name()
        if not name_match(nm, bow):
            close_popup()
            return _fail(EXIT_NAME, f'彈窗名稱 OCR 是 {nm!r}，不是「{bow}」（不穿）', 'bag-popup-name')
        rc, _ = click_popup_button('穿戴')
        if rc:
            close_popup()
            return rc
        if not _wait(lambda: not popup_open(), 2.0):
            return _fail(EXIT_VERIFY, '按了穿戴但彈窗沒關', 'bag-equip-verify')
        now = equipped_name()
        if not now or not name_match(now, bow):
            return _fail(EXIT_VERIFY, f'穿戴後武器格彈窗名稱是 {now!r}，不是「{bow}」（不丟舊武器）', 'bag-equip-verify')
        LAST['equipped'] = True
        if keep_old:
            LAST['kept_old'] = True
            return 0
        if not cur:
            return 0                                    # 原本沒武器，沒東西可丟
        if name_match(cur, bow, 0.8):
            return _fail(EXIT_GUARD, '舊武器名稱吻合弓，不丟')
        j = find_item(cur)
        if j is None:
            return _fail(EXIT_ITEM, f'穿弓後背包找不到舊武器「{cur}」（不丟別的東西）', 'bag-noold')
        rc = discard_item(role, j, cur, forbid=[bow])
        if rc:
            return rc
    return 0


# ---- 倉庫 ----
def open_depot(sub: str) -> int:
    rc = goto_page('depot')
    if rc:
        return rc
    if _sub_on(sub):
        return 0
    if not _click(SUB_XY[sub][0], SUB_XY[sub][1], DEPOT, f'bag 倉庫切到{sub}'):
        return _fail(EXIT_PANEL, '倉庫特徵不在，沒點子分頁', 'bag-depot-sub')
    if not _wait(lambda: _sub_on(sub), 2.0):
        return _fail(EXIT_PANEL, f'點了 {sub} 子分頁但底色沒變', 'bag-depot-sub')
    return 0


def depot_take(role: str, want: str, depot: str = 'public', kind: str = 'consumable') -> int:
    """倉庫取出 want（整疊）。kind=equip 時取出鈕在 722,662。成功 = 倉庫左半該格不再吻合，且切回背包能找到"""
    LAST.clear()
    with Session() as s:
        if s.rc:
            return s.rc
        rc = select_role(role)
        if rc:
            return rc
        rc = open_depot(depot)
        if rc:
            return rc
        i = find_item(want, depot=True)
        if i is None:
            return _fail(EXIT_ITEM, f'{depot} 倉庫找不到「{want}」', 'bag-depot-noitem')
        if not open_slot_popup(i, depot=True):
            return _fail(EXIT_PANEL, f'點倉庫第 {i + 1} 格沒開彈窗（空格不要點取出，會進刪除管理）', 'bag-depot-nopopup')
        nm = popup_name()
        if not name_match(nm, want):
            close_popup()
            return _fail(EXIT_NAME, f'倉庫彈窗名稱 OCR 是 {nm!r}，不是「{want}」（不取）', 'bag-depot-name')
        txt = _ocr_join(POPUP_BTN_BOX, BTN_OPTS)
        if '取出' not in re.sub(r'\s+', '', txt):
            close_popup()
            return _fail(EXIT_NAME, f'倉庫彈窗按鈕列 OCR 是 {txt!r}，沒有「取出」', 'bag-depot-btn')
        uikit.sleep(POPUP_SETTLE_S)                      # 彈窗出現動畫期間點「取出」會落空（2026-10-11 實測：彈窗關了但道具沒動）
        x, y = (722, 662) if kind == 'equip' else (732, 648)
        if not _click(x, y, POPUP, f'bag 倉庫取出「{want}」', allow=(), wait_ms=700):
            return _fail(EXIT_PANEL, '彈窗特徵消失，沒點取出', 'bag-depot-gone')
        if not _wait(lambda: not popup_open(), 2.5):
            return _fail(EXIT_VERIFY, '按了取出但彈窗沒關（不重點）', 'bag-depot-verify')
        rc = goto_page('bag')
        if rc:
            return rc
        # 切回背包頁後格子要約 1～3 秒才更新（2026-10-11 實測：立刻找會找不到而誤判失敗並回滾存回），輪詢最多 4 秒
        if not _wait(lambda: find_item(want) is not None, 4.0):
            return _fail(EXIT_VERIFY, f'取出後背包讀不到「{want}」', 'bag-depot-verify')
    return 0


def depot_store(role: str, want: str, depot: str = 'public') -> int:
    """背包 want 存入倉庫（彈窗「存入」鈕；整疊）。沒有 want = 已存過（回 92，呼叫端自行判斷）。PROTECT 名稱一律不存"""
    LAST.clear()
    if protected(want):
        return _fail(EXIT_GUARD, f'「{want}」在保護名單，不存倉')
    with Session() as s:
        if s.rc:
            return s.rc
        rc = select_role(role)
        if rc:
            return rc
        i = find_item(want)
        if i is None:
            return _fail(EXIT_ITEM, f'{role} 背包找不到「{want}」', 'bag-noitem')
        rc = open_depot(depot)
        if rc:
            return rc
        # 倉庫頁右半是背包，座標同背包頁；面板特徵要用倉庫頁的（背包頁特徵在倉庫頁不吻合，safe_click 會擋）
        x, y = slot_xy(i)
        if not _click(x, y, DEPOT, f'bag 倉庫頁點背包第 {i + 1} 格') or not _wait(popup_open, 1.5):
            return _fail(EXIT_PANEL, f'倉庫頁點背包第 {i + 1} 格沒開彈窗', 'bag-store-nopopup')
        nm = popup_name()
        if not name_match(nm, want):
            close_popup()
            return _fail(EXIT_NAME, f'彈窗名稱 OCR 是 {nm!r}，不是「{want}」（不存）', 'bag-store-name')
        txt = _ocr_join(POPUP_BTN_BOX, BTN_OPTS)
        if '存入' not in re.sub(r'\s+', '', txt):
            close_popup()
            return _fail(EXIT_NAME, f'彈窗按鈕列 OCR 是 {txt!r}，沒有「存入」（不點）', 'bag-store-btn')
        uikit.sleep(POPUP_SETTLE_S)                      # 同取出：彈窗動畫期間點會落空
        if not _click(732, 648, POPUP, f'bag 存入「{want}」', wait_ms=700):
            return _fail(EXIT_PANEL, '彈窗特徵消失，沒點存入', 'bag-store-gone')
        if not _wait(lambda: not popup_open(), 2.5):
            return _fail(EXIT_VERIFY, '按了存入但彈窗沒關（不重點）', 'bag-store-verify')
        rc = goto_page('bag')
        if rc:
            return rc
        if not _wait(lambda: find_item(want) is None, 4.0):      # 同上：背包頁更新有延遲，輪詢到消失
            return _fail(EXIT_VERIFY, f'存入後背包仍找到「{want}」', 'bag-store-verify')
    return 0


# ---- CLI ----
def _roles(arg: str):
    if str(arg).lower() == 'all':
        return [charstate.display(c) for c in charstate.chars()]
    hit = charstate.norm_char(arg)
    return [charstate.display(hit)] if hit else None


def _out(rc: int, info: dict) -> int:
    info.update(ok=rc == 0, rc=rc, **{k: v for k, v in LAST.items() if k not in info})
    print(json.dumps(info, ensure_ascii=False))
    return rc


def main() -> int:
    import winenv
    winenv.enable_server()
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    sub = ap.add_subparsers(dest='cmd', required=True)
    p = sub.add_parser('level'); p.add_argument('role')
    p = sub.add_parser('hp'); p.add_argument('role')
    p = sub.add_parser('find'); p.add_argument('role'); p.add_argument('names', nargs='+')
    p = sub.add_parser('use'); p.add_argument('role'); p.add_argument('name')
    p = sub.add_parser('swap-weapon'); p.add_argument('role'); p.add_argument('--keep-old', action='store_true'); p.add_argument('--bow', default='精靈王之弓')
    for n in ('take', 'store'):
        p = sub.add_parser(n); p.add_argument('role'); p.add_argument('name'); p.add_argument('--depot', default='public', choices=['public', 'personal'])
        p.add_argument('--kind', default='consumable', choices=['consumable', 'equip'])
    p = sub.add_parser('drop'); p.add_argument('role'); p.add_argument('name'); p.add_argument('--confirm-name', required=True)
    a = ap.parse_args()
    roles = _roles(a.role)
    if not roles:
        print(f'bag：角色 {a.role!r} 不認得', file=sys.stderr)
        return _out(uikit.EXIT_USAGE, {})
    r = roles[0]
    if a.cmd == 'level':
        rc, d = levels(roles)
        return _out(rc, {'levels': {k: v for k, v in d.items()}})
    if a.cmd == 'hp':
        rc, d = hps(roles)
        return _out(rc, {'hp': {k: (list(v) + [round(100 * v[0] / v[1])] if v else None) for k, v in d.items()}})
    if a.cmd == 'find':
        rc, d = find_items(r, a.names)
        return _out(rc, {'slots': d})
    if a.cmd == 'use':
        return _out(use_item(r, a.name, verify_buff=True), {})
    if a.cmd == 'swap-weapon':
        return _out(swap_weapon(r, a.bow, a.keep_old), {})
    if a.cmd == 'take':
        return _out(depot_take(r, a.name, a.depot, a.kind), {})
    if a.cmd == 'store':
        return _out(depot_store(r, a.name, a.depot), {})
    return _out(drop_item(r, a.name, a.confirm_name), {})


if __name__ == '__main__':
    sys.exit(main())
