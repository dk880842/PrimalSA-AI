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
  uv run --no-project python tools/gui/bag.py use DKBO 龍王的守護 [--no-reopen]  # 背包 → 彈窗名稱核對 → 使用（隊長吃龍王的守護）。buff 道具（龍王 / 2倍智慧果）走 eatbuff.eat_have：
                                                                    # 關遇敵 + 等戰鬥結束 → 讀吃前 buff 剩餘 → 使用 → 關背包 → 剩餘時間沒增加 = 95（不比數量）→ 開回遇敵
  uv run --no-project python tools/gui/bag.py weapon all                  # 唯讀：逐人讀武器格名稱
  uv run --no-project python tools/gui/bag.py swap-weapon DKBO [--keep-old] # 穿精靈王之弓、丟舊武器（名稱防護）
  uv run --no-project python tools/gui/bag.py take DKBO 龍王的守護 [--depot public|personal]   # 倉庫取出（整疊）
  uv run --no-project python tools/gui/bag.py store DKBO 龍王的守護 [--depot public|personal]  # 倉庫存入
  uv run --no-project python tools/gui/bag.py store all 人龍隨機蛋 --depot public [--skip-missing]   # 多人（all / DKBO2,DKBO3）：背包面板只開一次逐人存（take 同）
  uv run --no-project python tools/gui/bag.py drop DKBO 名稱 --confirm-name 名稱               # 丟棄背包道具（名稱必須完全對上）
  uv run --no-project python tools/gui/bag.py drop-spare-bow DKBO                                  # 武器格已是精靈王之弓時，丟背包裡多的那一把（轉生任務 16F 多給的；武器格不動）
  uv run --no-project python tools/gui/bag.py list all|DKBO,DKBO3                                  # 唯讀：每人背包每格名稱 + 空格數（面板開一次逐人切頭像）
  uv run --no-project python tools/gui/bag.py purge all|DKBO2,DKBO3 --names 名稱,名稱 [--dry-run]   # 刪除管理批次刪：只勾名單內道具 → 提示窗綠字清單逐條核對 = 勾選名稱（del_list_check）才按確定，否則存圖 + X 停手
  uv run --no-project python tools/gui/bag.py store all 千年龜的殼 --depot public --all-copies --skip-missing   # 同名多格（不疊加）全部存
  uv run --no-project python tools/gui/bag.py wear all 新手棍棒 新手鎧甲 新手頭盔 [--strict]          # 多人穿裝備（面板開一次逐人；背包沒有 = 已穿上，預設略過；2026-10-15，實機未驗證）
  uv run --no-project python tools/gui/bag.py store-items all --public 寵物誘餌,離線水晶 --personal 1轉新手禮盒 [--strict]   # 多人存多樣（面板開一次、每人一次存完；沒有的略過；實機未驗證）
最後一行 JSON {"ok","rc",...}；給其他腳本 import：bag.levels / hps / team_hp_pct / team_read（等級 + 有沒有某道具，開一次）/ find_items / list_all / purge / use_item / wear_item / wear_many / swap_weapon / depot_take / depot_store / depot_store_items / drop_item。
背包面板一律用 Session 開：自己開的那層在 with 結束（含任何失敗出口）時 close_leftover —— 道具彈窗 ESC → NPC 對話框蓋住背包 ESC（不回答）→ 點 ✕ 關背包（2026-10-13）。
AUTO_PURGE：背包滿時 questrun 可以不問人自動刪的名單（ui/bag.md 白名單去掉有條件的一項；2026-10-17 加千年龜的殼：同名多格全勾、「未知的殼」同圖不誤刪）。
道具辨識以名字為主（2026-10-14）：find / find_items / team_read / list / item_slots / find_item 一次截圖 →
① 名字樣板（itemname_match：「顯示道具名」白字整名圖，學出來的，tools/.cache/item-name-tpl/）認得的格 = 確定名稱 →
② 沒認出的格才比 GameClient 道具圖（itemimg_match，只認得到 imageId，同圖多名）→ ③ 還是沒認出 / 被浮字蓋住的格才名稱 OCR。
名字樣板只在「彈窗核對過名稱」或「格名稱 OCR 精確命中 Item 表」時學（同角色、同頁、120 秒內那張截圖；縮圖矛盾 / 跟別的名稱太像不學）。
名稱含數字（1～5轉新手禮盒，縮圖都是 50055；2026-10-17，離線測試，未實機）：name_match 同位置數字不同 = 不吻合（digits_conflict）；
格名 / 彈窗沒讀到那個數字（紅角標蓋住）= 不確定（digit_unsure）→ find_item 開彈窗核對、彈窗也要讀到同一個數字；
find_item 只跳過「確定是別的道具」的格（_may_be：只差數字 / 同圖多名都不跳），同圖多名的格名沒精確吻合一律開彈窗。
動作類（use / store / take / drop / purge）照舊開彈窗 / 提示窗核對名稱，不省。
PSA_ITEM_MATCH=auto（預設：名字 → 縮圖 → OCR）| name（只用名字樣板）| iconocr（舊 auto：縮圖 → OCR）| icon（只縮圖）| ocr（最舊：全 OCR）。

退出碼（共用 0 / 1 / 2 / 8 / 9 / 10 見 uikit；bag 自己 90～96）：
  90 背包面板打不開 / 分頁不對 / 中途消失（沒點面板內座標）
  91 左欄角色沒選到（黃框不對 / 名牌不是該角色）
  92 找不到指定道具（背包或倉庫沒有）
  93 防護擋下（要丟的名稱是精靈王之弓 / 不是預期名稱 / 沒給舊武器名稱…），零丟棄點擊；purge：名單含保護道具、像素勾選與目標不一致（已取消刪除）
  94 倉庫 / 背包滿
  95 動作後驗證失敗（不重點；請人看 snap）
  96 彈窗 / 提示窗名稱 OCR 對不上或讀不到（不點確定）；purge：提示窗清單核對不過（有保護 / 名單外道具、判不出、條數不符；已存圖、按 X、取消刪除）

防護原則：
  - 丟棄：彈窗名稱與提示窗名稱都必須模糊吻合「預期名稱」，且不能吻合 PROTECT（精靈王之弓…）；任何一塊讀不到 = 不丟。
  - 紅區（uikit.Panel.forbidden）：刪除管理、擴容、丟棄鈕；只有 drop_item 內 allow=('discard',) 才點丟棄鈕。
  - 道具浮窗按鈕座標依按鈕文字（OCR）決定：裝備 穿戴 618,662 / 丟棄 826,662；消耗品 使用 628,648 / 丟棄 838,648；
    可疊加 使用 618,648 / 更多 825,648；只有一顆 使用 732,648；倉庫取出 消耗品 732,648 / 裝備 722,662（ui/bag.md）。
"""
import argparse
import difflib
import json
import os
import re
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import charstate  # noqa: E402
import petmatch  # noqa: E402
import screen_sigs  # noqa: E402
import uikit  # noqa: E402

SRC = 'bag'
EXIT_PANEL, EXIT_SELECT, EXIT_ITEM, EXIT_GUARD, EXIT_FULL, EXIT_VERIFY, EXIT_NAME = 90, 91, 92, 93, 94, 95, 96

# ---- 版面（2880×1659 截圖座標）----
BAG_BTN, CLOSE_XY = (1120, 760), (1280, 113)
TAB_BAG, TAB_DEPOT = (1318, 265), (1318, 467)
SUB_XY = {'personal': (307, 200), 'public': (547, 200)}
SUB_ON = (251, 219, 135)
# 子分頁列五點 → tab_state：個人 230,200 / 400,210（個人分頁本體）、公共 436,205（左緣）/ 480,200 / 640,200（中段）。
# 沒選 = (171,127,84)；沒選但游標停在上面 = hover 淡色 (177,141,106)。
# 浮動「獲得 EXP」橫幅（掛機戰鬥的寵物 / 人物經驗、恢復魔力；3 行固定位置 y≈140～270、x≈440～1000，掛機中幾乎一直有）會蓋住公共分頁中段、
# 而且會吃掉點擊（2026-10-14 errlog 877/878、2026-10-16 13:17 / 13:21 / 13:26 p1 depot_use rc 90 都是點 547,200 沒切過去）。
# 2026-10-16 改：狀態只看「個人」兩點 + 公共左緣（tools/.cache 30 張倉庫頁截圖，含 6 張橫幅蓋住公共分頁的，這三點全部乾淨）——
# 個人亮 = personal、個人沒選 = public（兩分頁互斥），公共中段被蓋住不影響判斷；公共中段讀得懂才拿來交叉檢查。
SUB_OFF = ((171, 127, 84), (177, 141, 106))
SUB_TABS = [(230, 200), (400, 210), (436, 205), (480, 200), (640, 200)]
SUB_PERSONAL_N = 2                                  # SUB_TABS 前幾點屬於個人分頁
SUB_EDGE_XY = (440, 210)                            # 公共分頁左緣：橫幅從沒蓋到（同上 30 張），中段被蓋住 / 點了沒切過去時改點這裡
SUB_TOL = 24
SUB_MID_TOL = 8           # 公共中段交叉檢查 / 判斷沒被蓋住用嚴格容差：橫幅半透明壓暗的亮黃 (188,164,102) 離 hover 淡色只差 23，寬容差會誤認
SUB_CLEAR_WAIT_S = 4.0     # 子分頁列讀不懂（面板被其他東西蓋住）時最多等多久
SUB_RETRIES = 2            # 點了沒切過去（點擊被橫幅吃掉）→ 改點分頁左緣再點，最多再點幾次（切分頁可重複點，無副作用）
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
# 丟棄提示窗另一種版型（2026-10-12 實機 22:17 漆黑洞窟 16F 丟精靈王之弓，樣本 tools/.cache/ui-log/221743-bag-drop-noconfirm.png）：
# 兩顆鈕「丟棄」613,543（藍）/「取消」820,543（橘）、名字黃字在圖示下方 y≈436；鈕上緣 y≈515（pet.CONFIRM 版鈕在 y 557 ±20，上緣 537）→ 取 y=523 兩點區分
DROP2_OK, DROP2_CANCEL, DROP2_NAME_BOX = (613, 543), (820, 543), (540, 412, 360, 50)
DROP2_SIG = [(946, 208, 198, 65, 41, 24), (645, 523, 81, 121, 177, 28), (870, 523, 195, 87, 56, 28), (645, 543, 57, 106, 163, 24),
             (870, 543, 178, 75, 46, 24), (700, 460, 243, 213, 177, 24), (520, 300, 237, 213, 175, 24)]
DROP2 = uikit.Panel('BAGDROP2', None, DROP2_SIG, (946, 208), esc_close=False)
DISCARD_OK = (612, 551)                                             # 提示窗確定 / 丟棄（ui/bag.md 612,544；pet 提示窗 615,557 → 取中間）

FORBID = {'delete_mgr': (700, 598, 540, 56), 'expand': (190, 646, 170, 74)}
# 特徵點一律避開底部「關閉 + 頭像」列（戰鬥按刷新角色叫出的列，戰後可能殘留；約 x 150～780、y 672～800，疊在所有面板上）：
# 2026-10-14 08:21 舊點 730,688（整理背包左端）/ 230,683 / 520,683 被它蓋住 → BAGANY 認不出 → depot_use rc 90、quest close_stray_panel 不關 → rc 9。
# 改用整理背包 / 刪除管理的右段 x=1150（鈕上的字只到 x≈1015）與分頁內容 180,390 / 660,510（tools/.cache 2552 張 1440×830 截圖重驗：
# 舊點吻合的 164 張新點全吻合、另多認出 3 張被關閉列蓋住的；刪除模式 4 張（1150,688 = 金 191,127,63）照舊不算；背包頁 90 / 倉庫頁 77 張各點色差 ≤ 16）
CHROME = [(1280, 113, 197, 70, 43, 30), (1150, 688, 58, 106, 162, 30), (1150, 625, 177, 70, 38, 30)]
TAB_BAG_SIG = [(180, 390, 20, 13, 5, 24), (660, 510, 241, 215, 179, 24)]       # 背包頁：左欄裝備框暗邊 / 人物圖下緣米色
TAB_DEPOT_SIG = [(180, 390, 223, 187, 147, 24), (660, 510, 92, 63, 39, 24)]    # 倉庫頁：同兩點是倉庫格米色底 / 暗棕
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


OCR_CONFUSE = str.maketrans({'百': '首'})


def name_match(text, want, cutoff: float = 0.72) -> bool:
    """text（OCR 文字，可含多行）是否吻合 want：完全包含，或整體相似度 >= cutoff（OCR 錯一兩字仍過）"""
    a, w = norm_name(text), norm_name(want)
    if not a or not w:
        return False
    a, w = a.translate(OCR_CONFUSE), w.translate(OCR_CONFUSE)   # 「首 / 百」等 OCR 常混淆字先對齊（薩姆吉爾的首飾 常讀成 薩姆百爾的百飾）
    if digits_conflict(a, w):                       # 「4轉新手禮盒」≠「5轉新手禮盒」（模糊比對只差一字會過，2026-10-17 p1 根因）
        return False
    if w in a:
        return True
    if difflib.SequenceMatcher(None, a, w).ratio() >= cutoff:
        return True
    # 名字被兩行切開或前後多字：用最佳子字串視窗
    n = len(w)
    return any(difflib.SequenceMatcher(None, a[i:i + n], w).ratio() >= cutoff for i in range(max(1, len(a) - n + 1)))


# ---- 名稱裡的數字（2026-10-17 p1 rebirth_pets 5轉新手禮盒）----
# 1～5 轉新手禮盒只差一個數字、縮圖一樣（imageId 50055）：name_match 的模糊比對（相似度 0.72）會把「4轉新手禮盒」當成「5轉新手禮盒」，
# 彈窗核對因此把 1／2／4 轉的格學成「3轉新手禮盒」名字樣板 → 之後倉庫第 1 格（5轉）被樣板認成 3轉、整格跳過 → 「倉庫找不到」。
def _digit_ctx(s: str) -> list:
    """純函式：s 裡每段數字 → [(數字, 前一字, 後一字)]（沒有前 / 後字給 ''）"""
    return [(m.group(), s[m.start() - 1:m.start()], s[m.end():m.end() + 1]) for m in re.finditer(r'\d+', s)]


def _same_pos_digits(text: str, want: str) -> list:
    """純函式（輸入已 norm_name）：want 每段數字 → text 裡「前一字或後一字相同」位置讀到的數字清單 [(want 數字, [text 數字…])]"""
    tc = _digit_ctx(text)
    return [(d, [td for td, tp, tn in tc if (n and tn == n) or (p and tp == p)]) for d, p, n in _digit_ctx(want)]


def digits_conflict(text, want) -> bool:
    """純函式：want 的數字（「5轉」的 5）在 text 同一位置（前一字或後一字相同）讀到的全是別的數字 → True（確定不是 want）。
    text 那個位置沒讀到數字（被紅角標蓋住 / OCR 漏字）→ False（不確定，交給 digit_unsure / 彈窗）"""
    a, w = norm_name(text), norm_name(want)
    return any(got and d not in got for d, got in _same_pos_digits(a, w))


def digit_unsure(text, want) -> bool:
    """純函式：want 含數字，但 text 同一位置沒讀到相同數字（「轉新手禮盒」「?轉新手禮盒」）→ True（名字吻合也要開彈窗核對才算數）"""
    a, w = norm_name(text), norm_name(want)
    return any(d not in got for d, got in _same_pos_digits(a, w))


def strip_digits(t) -> str:
    """純函式：norm_name 後去掉數字（「5轉新手禮盒」→「轉新手禮盒」）"""
    return re.sub(r'\d+', '', norm_name(t))


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


BANNER_SAFE_DY = 33        # 背包第 1 列格心 y=245 在浮字橫幅（y≈140～270）裡、會被吃掉點擊 → 倉庫存取改點格子下緣 y=278（格框到 y≈292，仍在格內）


def store_click_xy(i: int) -> tuple:
    """倉庫頁點 / 雙擊背包第 i 格的座標：第 1 列改點下緣（避開浮字橫幅，2026-10-16 未實機），其他列照格心"""
    x, y = slot_xy(i)
    return (x, y + BANNER_SAFE_DY) if i < 5 else (x, y)


def popup_buttons(text) -> dict:
    """彈窗按鈕列文字 → {'kind', 按鈕: (x, y)}（依 ui/bag.md 的座標表；kind = equip / stack / consumable / single / depot）"""
    t = re.sub(r'\s+', '', str(text or ''))
    d = {}
    if '穿戴' in t or '穿' in t:       # OCR 常把「穿戴」讀成「穿 穿」
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


def _near(c, t, tol: int = SUB_TOL) -> bool:
    return all(abs(a - b) <= tol for a, b in zip(c, t))


def tab_state(cols) -> str | None:
    """純函式：SUB_TABS 五點顏色 → 'personal' / 'public' / None（讀不懂 = 面板被蓋住 / 不在倉庫頁）。
    只靠個人分頁兩點 + 公共左緣（浮字橫幅蓋不到）：個人兩點都亮且公共左緣沒選 → personal；個人兩點都沒選且公共左緣亮 → public。
    公共中段兩點只做交叉檢查：讀得懂（亮 / 沒選）而且跟結論矛盾才回 None；被橫幅蓋住（讀不懂）不影響"""
    if not cols or len(cols) != len(SUB_TABS):
        return None
    on = [_near(c, SUB_ON) for c in cols]
    off = [any(_near(c, t) for t in SUB_OFF) for c in cols]
    k = SUB_PERSONAL_N
    if all(on[:k]) and off[k]:
        st = 'personal'
    elif all(off[:k]) and on[k]:
        st = 'public'
    else:
        return None
    mid = cols[k + 1:]
    if st == 'personal' and any(_near(c, SUB_ON, SUB_MID_TOL) for c in mid):
        return None
    if st == 'public' and any(_near(c, t, SUB_MID_TOL) for c in mid for t in SUB_OFF):
        return None
    return st


def public_mid_clear(cols) -> bool:
    """純函式：公共分頁中段兩點讀得懂（沒被橫幅蓋住）→ 點中心 547,200 安全；否則改點左緣 SUB_EDGE_XY"""
    if not cols or len(cols) != len(SUB_TABS):
        return False
    return all(_near(c, SUB_ON, SUB_MID_TOL) or any(_near(c, t, SUB_MID_TOL) for t in SUB_OFF) for c in cols[SUB_PERSONAL_N + 1:])


def sub_click_xy(sub: str, attempt: int, cols) -> tuple:
    """純函式：第 attempt 次（0 起）點子分頁的座標。個人分頁橫幅蓋不到 → 一律中心；
    公共：第 1 次且中段沒被蓋住 → 中心 547,200，其餘（中段被蓋住 / 重點）→ 左緣 440,210"""
    if sub != 'public' or (attempt == 0 and public_mid_clear(cols)):
        return SUB_XY[sub]
    return SUB_EDGE_XY


def _tab_cols():
    return uikit.px(SUB_TABS)


def _tab_state() -> str | None:
    return tab_state(_tab_cols())


def _sub_on(sub: str) -> bool:
    return _tab_state() == sub


def _wait_tab_clear(secs: float = SUB_CLEAR_WAIT_S) -> str | None:
    """輪詢到子分頁列讀得懂 → 目前分頁；secs 內一直讀不懂 → None"""
    end = uikit.clock() + secs
    while True:
        st = _tab_state()
        if st is not None or uikit.clock() >= end:
            return st
        uikit.sleep(POLL_S)


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


# 吃了會在 buff 列出現圖示的道具 → buff_classify 的種類；使用後成敗以圖示為準（buff 列被背包面板蓋住，要關背包後才看得到）
BUFF_KIND = {'龍王的守護': 'dragon', '2倍智慧果': 'exp'}


def buff_kind(item: str) -> str | None:
    """道具名稱 → buff 種類（BUFF_KIND；名稱先 norm_name）；不是 buff 道具 = None"""
    return BUFF_KIND.get(norm_name(item))


def buff_state(kind: str) -> bool | None:
    """buff 列有 kind（'dragon' / 'exp'）圖示嗎 → True / False；像素讀不到 = None。
    questrun（要不要吃龍王）與 depot_use（吃前跳過 / 吃後驗證）共用這一個判斷（2026-10-13 review §3.4：兩邊各讀各的，曾一邊說沒有、一邊說有）"""
    row = buff_row()
    return None if row is None else kind in row


def has_buff(kind: str) -> bool:
    """buff 列有 kind（'dragon' / 'exp'）圖示嗎；讀不到 = False（buff_state 的 bool 版）"""
    return bool(buff_state(kind))


def _buff_icon() -> bool:
    """龍王的守護人形圖示在 buff 列嗎（不會被 2倍智慧果 EXP 圖示騙到）；讀不到 = False"""
    return has_buff('dragon')


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
        self.rc, self.was_open, self.opened = 0, False, False

    def __enter__(self):
        self.was_open = uikit.is_open(BAGANY)            # 已開著（外層 Session / 呼叫端開的）就不再 preflight：背包開著時 screen() 會判 unknown，巢狀進入會誤報驗證視窗
        if not self.was_open and stuck_in_delmode():
            # 上次 purge 中斷、背包停在刪除模式 / 刪除確認窗（BAGANY 外框不認得）：舊版會走 preflight → 連 3 次 unknown → 誤設驗證停手旗標（10-15 23:33）
            log('背包停在刪除模式 / 刪除確認窗（上次中斷？）→ X / 取消刪除，回普通背包頁（不按確定）')
            if not _leave_delmode():
                self.rc = _fail(EXIT_PANEL, '背包停在刪除模式，按 X / 取消刪除後仍回不到普通背包頁', 'bag-delmode-stuck')
                return self
            self.opened = True                           # 殘留的面板當成自己開的：結束時關掉
        elif not self.was_open and popup_open():
            # 上次中斷 / 人手動留下的道具說明彈窗（背包被壓暗 ×0.45～0.60，BAGANY 外框不認得）：ESC 關掉就回普通背包頁
            # （2026-10-16 p2：舊版走 preflight → 連 3 次 unknown → 誤設驗證停手旗標；watch 現在也認得 screen_sigs.bag_itempop）
            log('背包上留著道具說明彈窗（上次中斷？）→ ESC 關掉（不按拆分 / 丟棄）')
            close_popup()
            if uikit.is_open(BAGANY):
                self.opened = True                       # 殘留的面板當成自己開的：結束時關掉
            else:
                self.rc = _fail(EXIT_PANEL, '道具說明彈窗 ESC 後回不到背包頁', 'bag-popup-stuck')
                return self
        elif not self.was_open:
            self.rc = uikit.preflight(SRC)
            if self.rc:
                return self
            ok, _ = uikit.open_panel_ex(BAGANY)
            if not ok:
                self.rc = _fail(EXIT_PANEL, '背包面板打不開（沒看到主畫面 HUD 或背包外框特徵）；沒點任何面板內座標', 'bag-open-fail')
                return self
            self.opened = True
        if not uikit.is_open(BAG):
            self.rc = goto_page('bag')
        return self

    def __exit__(self, *exc):
        if not self.was_open:
            close_leftover(dialog_esc=self.opened)
            _SHOT.clear()
            _CUR.clear()
        return False


LEFTOVER_ROUNDS = 3


def close_leftover(dialog_esc: bool = True) -> str:
    """Session 結束（含任何失敗出口）一定把自己開的背包關掉 → 回做了什麼（'' / 'closed' / 'dialog+closed' / 'dialog' …，給 log / 測試）。
    根因（2026-10-13 08:04 depot_use rc 90）：吃龍王的守護時自動巡路還在走，隊伍走到看門者 → NPC 對話框跳出、整個 UI（含背包面板）被藏起來；
    use_item 點格子沒開彈窗（90）、depot_store 開不了背包（90），舊版 __exit__ 只在「看得到背包外框」時才關 → 沒關；
    之後 quest.py ESC 掉對話框，背包面板又露出來 → 連 3 次不認得誤報 rc 9。
    做法（每輪現場讀圖、只做認得的動作）：道具彈窗開著 → close_popup（ESC）；NPC 對話框（screen_sigs.SIG_DIALOG）蓋著 → ESC（不回答任何選項）；
    看得到背包外框 → 點 ✕ 1280,113（uikit.close_panel）。不認得的畫面不碰。dialog_esc=False（這次根本沒開成背包）→ 不碰對話框"""
    did = []
    for _ in range(LEFTOVER_ROUNDS):
        if popup_open():
            close_popup()
            did.append('popup')
            continue
        if stuck_in_delmode():                            # 刪除模式 / 刪除確認窗：BAGANY 不認得、✕ 不知道會怎樣 → 先 X / 取消刪除（不按確定）
            _leave_delmode()
            did.append('delmode')
            continue
        if uikit.is_open(BAGANY):
            uikit.close_panel(BAGANY, known_open=True)
            did.append('closed')
            continue
        if dialog_esc and uikit.screen().get('state') == 'dialog':
            uikit.gui('seq', 'key {ESC}; wait 600', note='bag：NPC 對話框蓋住背包（巡路抵達）→ ESC（不回答），再關背包')
            log('NPC 對話框蓋住背包面板（自動巡路抵達 NPC？）→ ESC 關對話框（不回答）後再關背包')
            did.append('dialog')
            continue
        break
    return '+'.join(did)


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
        return _fail(uikit.EXIT_USAGE, f'角色 {role!r} 不在這個視窗的名單')
    for k in range(2):
        if k == 0 and _avatar_sel(role):                  # 已經選著（批次連續操作同一人）就不再點頭像（2026-10-13：取誘餌流程一人點 4 次）
            break
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
    if _CUR.get('role') != role:
        _SHOT.clear()                                     # 換人：之前的截圖不能拿來學名字樣板
    _CUR['role'] = role
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


def team_scan(roles=None, free: bool = True, hp: bool = True) -> tuple:
    """唯讀：開背包一次、逐人點左欄頭像，同一次讀背包空格（free：slot_occupancy 像素判，不做名稱 OCR）與 HP（hp：背包頁 HP 條字）
    → (rc, {角色: {'free': 空格數 | None, 'hp': % | None, 'hp_raw': (目前, 最大) | None}})。
    2026-10-13 review §5.3：questrun 任務開始前「背包空格 bag.find_items 逐人開關一次 + 全隊 HP 再開一次」22～26 秒 → 合成一次（約 8～10 秒）。
    空格像素讀不到時 free = None（呼叫端當「不知道」，不算不足）"""
    out = {}
    with Session() as s:
        if s.rc:
            return s.rc, out
        for r in list(roles or uikit.CHARS):
            rc = select_role(r)
            if rc:
                return rc, out
            d = {}
            if free:
                occ = slot_occupancy()
                d['free'] = None if occ is None else occ.count(False)
            if hp:
                v = read_hp()
                d['hp_raw'] = v
                d['hp'] = round(100 * v[0] / v[1]) if v and v[1] else None
            out[r] = d
    return 0, out


def team_read(roles=None, names=(), level: bool = True) -> tuple:
    """唯讀：開背包一次、逐人點左欄頭像讀「N轉M級」+ 背包有沒有 names 裡的道具（名稱 OCR 模糊比對）+ 空格
    → (rc, {角色: {'level': (轉, 級) | None, 'have': {名稱: bool}, 'free': 空格 | None}})。
    questrun 任務前置（紅暴 2031：5 人 ≥80 級、背包各有耐久力回複藥）用；讀不到的道具名稱算 False（呼叫端當「沒有 / 讀不到」停手）"""
    out = {}
    with Session() as s:
        if s.rc:
            return s.rc, out
        for r in list(roles or uikit.CHARS):
            rc = select_role(r)
            if rc:
                return rc, out
            d = {}
            if level:
                d['level'] = read_level(r)
            if names:
                nb = _names_in_bag(names)
                d['have'] = {n: nb['found'][n] is not None for n in names}
                d['free'] = nb['free'] if nb['occ'] is not None else None
                d['by'] = nb['by']
            out[r] = d
    return 0, out


def hps(roles) -> tuple:
    """唯讀：開背包逐人點左欄頭像讀 HP → (rc, {role: (目前, 最大) | None})。
    給 questrun 任務之間 / BOSS 後檢查全隊血量（HUD 只有當前角色的 HP；切換面板 / 組隊面板沒有 HP）；實作 = team_scan(free=False)"""
    rc, d = team_scan(roles, free=False, hp=True)
    return rc, {r: v.get('hp_raw') for r, v in d.items()}


def team_hp_pct(roles=None) -> tuple:
    """全隊 HP 百分比（hps 換算）→ (rc, {角色: % | None})；roles 預設五人。questrun（任務前 / BOSS 後 / 隊伍散了）與 quest.py --hp-check-min 共用"""
    rc, d = hps(list(roles or uikit.CHARS))
    return rc, {r: (round(100 * v[0] / v[1]) if v and v[1] else None) for r, v in d.items()}


def read_slot_name(i: int, depot: bool = False) -> str:
    x, y = depot_xy(i) if depot else slot_xy(i)
    dx, dy, w, h = SLOT_NAME_R
    return _ocr_join((x - dx, y - dy, w, h), SLOT_OPTS)


POPUP_NAME_ALT = (600, 250, 330, 45)                                # 說明越長標題越高（2倍智慧果 y≈270）；只含標題列


def _ocr_all(box, optsets) -> str:
    """每組 OCR 參數都讀、全部串起來（_ocr_join 是第一組讀到字就停）"""
    return ' '.join(t for o in optsets for t in uikit.ocr(box, *o) if t.strip())


def popup_name(want: str | None = None) -> str:
    """兩個標題框都讀、串起來（短彈窗時 y133 框在彈窗外，讀到的是 HUD / 聊天雜訊而非空字串，不能「讀不到才用備援」）。
    want = 要核對的名稱：第一組 OCR 參數讀到的字不吻合時，再用其餘參數讀、吻合才採用（2026-10-12 千年龜的殼存入彈窗
    `-Light 170` 讀成「三三」、`-Dark 0` 才讀到名稱，舊版第一組有字就停 → 96）。不給 want（例：讀武器格舊武器名稱當身分）維持只用第一組，
    不把多組雜訊串進名稱"""
    base = (_ocr_join(POPUP_NAME_BOX, NAME_OPTS) + ' ' + _ocr_join(POPUP_NAME_ALT, NAME_OPTS)).strip()
    if want is None or (name_match(base, want) and not digit_unsure(base, want)):
        return base
    more = (_ocr_all(POPUP_NAME_BOX, NAME_OPTS[1:]) + ' ' + _ocr_all(POPUP_NAME_ALT, NAME_OPTS[1:])).strip()
    if name_match(more, want) and (not digit_unsure(more, want) or not name_match(base, want)):
        return more                                     # 第一組數字讀不清（「轉新手禮盒」）而其餘參數讀到數字 → 採用（_popup_verify 再判數字）
    return base


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
# 格心周圍 13×13 = 169 點（dx −30～30 每 5、dy −24～24 每 4；背包格 / 倉庫格空格內部都是平的棕色）。
# 2026-10-14：舊的 5×5 = 25 點（每 12 / 10 px）漏掉空心細線的「風的鎖」（DKBO 背包格號 6 = 860,352，25 點全落在空心處，3 張截圖都漏）；
# 離線 171 張背包頁 + 88 張倉庫頁截圖（4325 格）：空格 0 點（無一誤判）、有道具最少 25 點（耐久力回複藥；風的鎖 35 點）；dy 不超過 ±24 是避開
# 取出動畫時上一格飄下來的圖示（p4/after_take_depot.png 第 12 格，dy ≤ −26）
SLOT_PROBE = [(dx, dy) for dx in range(-30, 31, 5) for dy in range(-24, 25, 4)]
SLOT_OCC_MIN = 2
# 數量字帶（2026-10-16）：每格右下都有疊數白字（數量 1 也顯示），在格子下緣、浮動「獲得 EXP」橫幅（y≈140～270）蓋不到的地方。
# 背包第 1 列（y=245）的 SLOT_PROBE（y 221～269）整片在橫幅裡 → 空格被橫幅壓暗也算「有道具」→ 存入驗證「格子變空」永遠等不到（p1 13:27 shot.png：
# 第 3 格已空，主探點 0 點吻合空格棕 → 誤判有；數量字帶 0 點偏離 → 空）。倉庫第 1 列（y=290）的名字 / 圖示也被橫幅的第 3 行蓋到。
# 規則：主探點說有、而且數量字帶也有 ≥ SLOT_QTY_MIN 點偏離空格棕 才算有道具。背包格 / 倉庫格大小不同各一組
SLOT_QTY_PROBE = [(dx, dy) for dx in range(-36, 41, 3) for dy in range(26, 41, 2)]
DEPOT_QTY_PROBE = [(dx, dy) for dx in range(-30, 37, 3) for dy in range(16, 35, 2)]
SLOT_QTY_MIN = 3


def _dev_n(cols) -> int:
    return sum(1 for c in cols if any(abs(a - b) > SLOT_EMPTY_TOL for a, b in zip(c, SLOT_EMPTY)))


def slot_occupied(cols, qty_cols=None) -> bool:
    """純函式：某格 SLOT_PROBE 各點顏色 → 有沒有道具（≥ SLOT_OCC_MIN 點偏離空格棕）。
    qty_cols（數量字帶各點）有給 → 還要字帶 ≥ SLOT_QTY_MIN 點偏離才算有（擋浮字橫幅蓋住的空格）"""
    if _dev_n(cols) < SLOT_OCC_MIN:
        return False
    return qty_cols is None or _dev_n(qty_cols) >= SLOT_QTY_MIN


def _occupancy(depot: bool) -> list | None:
    xy, qp = (depot_xy, DEPOT_QTY_PROBE) if depot else (slot_xy, SLOT_QTY_PROBE)
    probes = SLOT_PROBE + qp
    pts = [(x + dx, y + dy) for i in range(n_slots(depot)) for x, y in [xy(i)] for dx, dy in probes]
    cols = uikit.px(pts)
    if not cols or len(cols) != len(pts):
        return None
    k, m = len(SLOT_PROBE), len(probes)
    return [slot_occupied(cols[i * m:i * m + k], cols[i * m + k:(i + 1) * m]) for i in range(n_slots(depot))]


def slot_occupancy() -> list | None:
    """背包頁（或倉庫頁右半，同座標）15 格各有沒有道具（一次 uikit.px；主探點 + 數量字帶，不受浮字橫幅影響）；讀不到 None"""
    return _occupancy(False)


def depot_occupancy() -> list | None:
    """倉庫頁左半 20 格各有沒有道具（同 slot_occupancy）；讀不到 None"""
    return _occupancy(True)


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


# ---- 道具格辨識：名字樣板 → 縮圖 → OCR（2026-10-14）----
# 一次背包截圖（uikit.shot_getter，約 0.2 s）→ 空格（像素）→ ① 名字樣板（itemname_match：「顯示道具名」的白字整名圖，同欄同名 IoU 1.0，
# 認得就是確定的名稱）→ ② 名字沒認出的格才比 GameClient 道具圖（itemimg_match，工作集 = 呼叫端名稱 + item_pool() + 相似圖；
# 只能認到 imageId，同圖多名標 ambiguous）→ ③ 還是沒認出 / 被蓋住的格才名稱 OCR。
# **動作類（use / store / take / drop / purge）照舊開彈窗 / 提示窗核對名稱**，名字樣板 / 縮圖只決定「先開哪一格」。
# 被浮字橫幅蓋住（itemimg_match 遮擋偵測，兩層共用）→ 等 ICON_OCC_WAIT_S 重拍，最多 ICON_OCC_RETRIES 次，仍蓋住 → 那幾格走 OCR（auto）。
# 認不出 ≠ 沒有：auto 模式對「沒認出 / 被蓋住」的格（與沒有道具圖的名稱）照舊 OCR / 開彈窗再確認才說沒有。
# 名字樣板是學出來的（tools/.cache/item-name-tpl/）：彈窗名稱核對過（_learn_verified）或格名稱 OCR 精確命中 Item 表（_learn_ocr）時，
# 用同一個角色、同一頁、ITEM_SHOT_MAX_AGE_S 內的那張截圖學那一格；縮圖認出的圖不屬於這個名稱 / 跟別的名稱樣板太像 → 不學。
# ITEM_MATCH（環境變數 PSA_ITEM_MATCH 覆寫）：
#   auto = 名字樣板 → 縮圖 → OCR（預設）；name = 只用名字樣板（不比縮圖、不 OCR）；
#   iconocr = 2026-10-14 前的 auto（縮圖 → OCR，不看名字樣板、不學）；icon = 只用縮圖（不 OCR）；ocr = 最舊行為（每格 OCR）。
ITEM_MATCH = (os.environ.get('PSA_ITEM_MATCH') or 'auto').strip().lower()
ITEM_MODES = ('auto', 'name', 'iconocr', 'icon', 'ocr')
ITEM_POOL_EXTRA = ['龍王的守護', '2倍智慧果', '千年龜的殼', '寵物誘餌', '耐久力回複藥', '人龍隨機蛋', '薩姆吉爾的首飾',
                   '龍的魅力之笛', '英雄的祝福', '離線水晶', '安撫之素', '2轉新手禮盒']


def _use_name() -> bool:
    return ITEM_MATCH in ('auto', 'name')


def _use_icon() -> bool:
    return ITEM_MATCH in ('auto', 'iconocr', 'icon')


def _use_ocr() -> bool:
    """截圖辨識不到的格要不要再名稱 OCR（ocr 模式本來就全 OCR，不走這裡）"""
    return ITEM_MATCH in ('auto', 'iconocr')


def item_pool() -> list:
    """縮圖工作集（常在背包的道具）= PROTECT + AUTO_PURGE + PURGE_FORBID + ITEM_POOL_EXTRA（去重）"""
    return list(dict.fromkeys(PROTECT + AUTO_PURGE + PURGE_FORBID + ITEM_POOL_EXTRA))
ICON_OCC_RETRIES, ICON_OCC_WAIT_S = 2, 1.5
ITEM_SHOT_MAX_AGE_S = 120.0        # 學名字樣板時用的截圖最多多舊（同角色、同頁）
_IM = {'mod': None, 'warned': False}
_NM = {'mod': None, 'warned': False}
_CUR: dict = {}                    # {'role': 目前左欄選中的角色}（select_role 設）
_SHOT: dict = {}                   # {kind: {'get', 't', 'role', 'cells'}}：最近一次辨識用的截圖（學名字樣板用）


def _imgmod():
    """itemimg_match 模組（模式不用縮圖 / 沒抽道具圖 tools/.cache/item-images → None，呼叫端走 OCR）"""
    if not _use_icon():
        return None
    if _IM['mod'] is None:
        try:
            import itemimg_match
            itemimg_match.index()
            _IM['mod'] = itemimg_match
        except (OSError, ImportError) as e:
            if not _IM['warned']:
                log(f'道具縮圖比對停用（{e}）→ 走名稱 OCR')
                _IM['warned'] = True
            return None
    return _IM['mod']


def _namemod(learning: bool = False):
    """itemname_match 模組（模式不用名字樣板 → None）。learning=False 時沒有任何樣板也回 None（省掉整頁比對）"""
    if not _use_name():
        return None
    if _NM['mod'] is None:
        try:
            import itemname_match
            _NM['mod'] = itemname_match
        except ImportError as e:
            if not _NM['warned']:
                log(f'道具名字樣板停用（{e}）')
                _NM['warned'] = True
            return None
    NM = _NM['mod']
    return NM if learning or NM.n_templates() else None


def _known(IM, names) -> list:
    """名稱清單去掉道具圖索引查無此名的（ids_for_name 會丟 KeyError）；保序去重"""
    out = []
    for n in dict.fromkeys(n for n in names if n):
        try:
            IM.ids_for_name(n)
            out.append(n)
        except KeyError:
            pass
    return out


def _occ_of(get, kind: str) -> list:
    """每格 True 有 / False 空 / None 被橫幅蓋住（itemimg_match.occupancy；沒抽道具圖也能用）"""
    import itemimg_match
    return itemimg_match.occupancy(get, kind)


def _name_cell(c: dict) -> dict:
    """名字樣板命中的格 → 與 itemimg_match.identify 同形的結果（by 'name'；名稱確定，不是 ambiguous）"""
    return {'slot': c['slot'], 'by': 'name', 'ok': True, 'name': c['name'], 'names': [c['name']], 'ambiguous': False,
            'imageId': None, 'score': c['score'], 'second': c['second'], 'occluded': False}


def _blank_cell(i: int, occluded: bool) -> dict:
    return {'slot': i, 'by': None, 'ok': False, 'name': None, 'names': [], 'ambiguous': False, 'imageId': None,
            'score': 0.0, 'second': 0.0, 'occluded': occluded}


def icon_read(kind: str = 'bag', want=(), pool=None, expand: bool = True) -> dict | None:
    """唯讀：一次截圖辨識目前頁的道具格（kind = 'bag' 背包 15 格 / 'depot' 倉庫 20 格）：名字樣板先、沒認出的格才比縮圖。
    want = 要找的名稱（縮圖一定在候選、會加相似圖）；pool = 其他可能同時在的道具（預設 item_pool()）。
    → {'occ': [True/False/None], 'cells': {格: 結果（by 'name' / 'icon'）}, 'hits': {名稱: [格…]（名字樣板命中在前，各自分數高到低）},
       'named': {格: 名字樣板認出的名稱}, 'unresolved': [有道具但沒認出 / 被蓋住的格], 'missing': [沒有道具圖的名稱], 'known': [縮圖查得到的 want],
       'names_hidden': 「顯示道具名」關著, 'shots': 截圖次數, 'ms'}；兩層都不能用（ocr 模式 / 沒樣板也沒抽圖 / 截不到）→ None"""
    NM = _namemod()
    IM = _imgmod()
    if NM is None and IM is None:
        return None
    t0 = time.time()
    want = list(dict.fromkeys(n for n in want if n))
    wk = _known(IM, want) if IM else []
    pk = _known(IM, item_pool() if pool is None else pool) if IM else []
    shots = 0
    for attempt in range(ICON_OCC_RETRIES + 1):
        get = uikit.shot_getter('bagimg')
        shots += 1
        if get is None:
            return None
        page = NM.read_page(get, kind) if NM else None
        occ = page['occ'] if page else _occ_of(get, kind)
        named = {i: c for i, c in (page['cells'] if page else {}).items() if c['name']}
        rest = [i for i, o in enumerate(occ) if o is not False and i not in named]
        if IM:
            r = IM.match_slots(get, kind, wk, pool=pk, slots=rest, expand=expand)
        else:
            r = {'cells': {i: _blank_cell(i, occ[i] is None) for i in rest}, 'hits': {}, 'missing': []}
        if not any(o is None for o in occ) or attempt == ICON_OCC_RETRIES:
            break
        uikit.mark('icon-occluded')
        uikit.sleep(ICON_OCC_WAIT_S)                   # 浮動 EXP 橫幅蓋住格子：等它消失重拍
    cells = dict(r['cells'])
    cells.update({i: _name_cell(c) for i, c in named.items()})
    hits = {}
    for n in dict.fromkeys(want + list(r['hits'])):
        by_name = sorted((i for i, c in named.items() if NM.same_name(c['name'], n)), key=lambda i: -named[i]['score']) if NM else []
        hits[n] = by_name + [i for i in r['hits'].get(n) or [] if i not in by_name]
    out = {'occ': occ, 'cells': dict(sorted(cells.items())), 'hits': hits, 'missing': r['missing'], 'known': wk,
           'named': {i: c['name'] for i, c in named.items()}, 'names_hidden': bool(page and page['hidden']),
           'unresolved': sorted(i for i, c in cells.items() if not c['ok']), 'shots': shots, 'ms': int((time.time() - t0) * 1000)}
    _SHOT[kind] = {'get': get, 't': uikit.clock(), 'role': _CUR.get('role'), 'cells': out['cells']}
    uikit.mark(f'icon {kind}' + (f' name {len(named)}' if named else ''))
    return out


def _learn_verified(kind: str, slot: int, name: str, src: str = '彈窗') -> bool:
    """名稱核對過（彈窗 / 提示窗，或 OCR 精確命中 Item 表）→ 用最近一次辨識的截圖學那一格的名字樣板。
    不學：模式不用名字樣板 / 沒有同角色、ITEM_SHOT_MAX_AGE_S 內的截圖 / 那格名字樣板已認得 / 縮圖認出的圖不屬於這個名稱 /
    itemname_match.learn 的保守規則（沒道具、被蓋住、白點不足、跟別的名稱樣板太像、變體滿）。學習失敗不影響主流程"""
    NM = _namemod(learning=True)
    sh = _SHOT.get(kind)
    if NM is None or not sh or not name or sh['role'] != _CUR.get('role') or uikit.clock() - sh['t'] > ITEM_SHOT_MAX_AGE_S:
        return False
    c = sh['cells'].get(slot) or {}
    if c.get('by') == 'name':
        if not NM.same_name(c.get('name'), name):
            log(f'警告：{kind} 格 {slot} 名字樣板認成「{c.get("name")}」，{src}核對是「{name}」（不學；樣板可能有誤）')
        return False
    if c.get('ok') and c.get('names') and not any(NM.same_name(n, name) for n in c['names']):
        log(f'{kind} 格 {slot}：{src}核對是「{name}」但縮圖認成 {c["names"][:3]}（不學名字樣板）')
        return False
    try:
        ok = NM.learn(sh['get'], kind, slot, name, log=log)
    except Exception as e:                              # 學習是附帶的，壞掉不影響主流程
        log(f'名字樣板學習失敗（{e}）')
        return False
    if ok:
        c.update({'by': 'name', 'ok': True, 'name': name, 'names': [name], 'ambiguous': False})
    return ok


def ocr_exact_name(text) -> str | None:
    """格名稱 OCR（可能兩行、重複片段）去重 / 正規化後**完全等於** Item 表某個名稱 → 那個名稱（norm_name 後）；否則 None"""
    t = norm_name(dedup_text(text))
    return t if t and t in _item_name_set() else None


_item_set = None


def _item_name_set() -> set:
    global _item_set
    if _item_set is None:
        _item_set = set(item_names())
    return _item_set


def _learn_ocr(kind: str, texts: dict) -> int:
    """OCR 精確命中 Item 表的格 → 學名字樣板（_learn_verified 同一套規則）。回學到幾格"""
    if _namemod(learning=True) is None:
        return 0
    n = 0
    for i, t in texts.items():
        nm = ocr_exact_name(t)
        if nm:
            n += _learn_verified(kind, i, nm, 'OCR ')
    return n


def icon_label(c: dict) -> str:
    """identify 結果 → 顯示名：工作集裡唯一對應的名稱（同圖還有別的道具名 → 後面加「(同圖)」，只是推定）；沒有 → 前 3 個同圖名用 / 連起來"""
    if c.get('name'):
        return c['name'] + ('(同圖)' if c.get('ambiguous') else '')
    ns = c.get('names') or []
    return '/'.join(ns[:3]) + ('…' if len(ns) > 3 else '')


def _names_in_bag(names) -> dict:
    """背包頁（角色已選好）：names 各在哪格 → {'found': {名稱: 格 | None}, 'by': {名稱: 'name'|'icon'|'ocr'}, 'free', 'unread', 'ambiguous', 'occ', 'icon_ms'}。
    auto：一次截圖 → 名字樣板 → 縮圖；沒命中的名稱，若還有「沒認出 / 被蓋住」的格或名稱沒有道具圖 → 只對那些格名稱 OCR
    （名字樣板已認出是別的名稱的格不 OCR；名稱被關才點開「顯示道具名」；OCR 精確命中 Item 表的格順便學名字樣板）。
    name / icon：不 OCR。ocr / 不能用截圖辨識：舊法（每格名稱 OCR）"""
    names = list(names)
    ir = icon_read('bag', names) if ITEM_MATCH != 'ocr' else None
    found, by, amb = {}, {}, []
    if ir is None:                                     # 舊法
        occ, texts = read_bag_names_ocr()
        idx = sorted(texts)
        for nm in names:
            hit = next((i for i in idx if texts[i] and name_match(texts[i], nm)), None)
            found[nm] = hit
            if hit is not None:
                by[nm] = 'ocr'
        free = occ.count(False) if occ is not None else sum(1 for i in idx if not texts[i].strip())
        unread = [i for i in idx if not texts[i].strip()] if occ is not None else []
        return {'found': found, 'by': by, 'free': free, 'unread': unread, 'ambiguous': amb, 'occ': occ, 'icon_ms': None}
    occ = ir['occ']
    named = ir.get('named') or {}
    missing = set(ir['missing']) | {n for n in names if n not in ir['known']}     # 沒有道具圖 / 道具圖索引查不到的名稱 → 名字樣板沒中就只能 OCR
    for nm in names:
        hits = ir['hits'].get(nm) or []
        found[nm] = hits[0] if hits else None
        if hits:
            by[nm] = ir['cells'][hits[0]].get('by') or 'icon'
            if ir['cells'][hits[0]].get('ambiguous'):
                amb.append(nm)
    todo = [n for n in names if found[n] is None]
    unresolved = list(ir['unresolved'])
    ocr_cells = []
    if todo and _use_ocr():
        hit_cells = {h for v in ir['hits'].values() for h in v} | set(named)
        if any(n in missing for n in todo):          # 沒有道具圖的名稱：名字樣板 / 縮圖已認出的格以外，全部 OCR
            ocr_cells = [i for i, o in enumerate(occ) if o is not False and i not in hit_cells]
        else:
            ocr_cells = unresolved
        ocr_cells = sorted(set(ocr_cells))
    texts = {}
    if ocr_cells:
        texts = {i: read_slot_name(i) for i in ocr_cells}
        if names_hidden([i in ocr_cells for i in range(n_slots())], texts) and ensure_names_shown(occ):
            texts = {i: read_slot_name(i) for i in ocr_cells}
        for nm in todo:
            hit = next((i for i in ocr_cells if texts[i] and name_match(texts[i], nm)), None)
            if hit is not None:
                found[nm], by[nm] = hit, 'ocr'
        _learn_ocr('bag', texts)
    unread = [i for i in unresolved if not str(texts.get(i) or '').strip()]
    return {'found': found, 'by': by, 'free': occ.count(False), 'unread': unread, 'ambiguous': amb, 'occ': occ, 'icon_ms': ir['ms']}


def _popup_verify(i: int, depot: bool, want: str, tried: set) -> bool:
    """開第 i 格彈窗讀名稱核對 want（吻合 → 學名字樣板）；ESC 關。沒開成 → False"""
    if not open_slot_popup(i, depot):
        return False
    tried.add(i)
    nm = popup_name(want)
    close_popup()
    if nm and name_match(nm, want) and not digit_unsure(nm, want):     # 名稱含數字（N轉新手禮盒）：彈窗要讀到同一個數字才算（2026-10-17）
        _learn_verified('depot' if depot else 'bag', i, want)
        return True
    if nm and name_match(nm, want):
        log(f'第 {i + 1} 格彈窗「{nm}」讀不到「{want}」的數字 → 不算吻合（不學樣板）')
    return False


def _may_be(name, want) -> bool:
    """名字樣板 / 格名 OCR 讀到 name 時，這格還**不能排除**是 want：同名、扣掉數字後相同（1～5轉新手禮盒，紅角標蓋住數字 / 數字讀錯），
    或兩個名稱共用同一張縮圖（同圖多名一律以彈窗核對為準，2026-10-17）。只有確定是別的道具才回 False"""
    if _same_item(name, want) or (strip_digits(want) and strip_digits(name) == strip_digits(want)):
        return True
    IM = _imgmod()
    if IM is None:
        return False
    try:
        return bool(set(IM.ids_for_name(name)) & set(IM.ids_for_name(want)))
    except KeyError:
        return False


def find_item(want: str, depot: bool = False, popup_fallback: bool = True, hint: int | None = None) -> int | None:
    """want 在目前頁（背包 / 倉庫左半）的格號（0 起算）。hint = 上一次找到的格號：先只點那格核對彈窗名稱，吻合就直接回傳（省掉逐格開彈窗 + ESC，2026-10-13）。
    2026-10-14 名字樣板 → 縮圖（ITEM_MATCH auto / name / iconocr / icon）：一次截圖 → 名字樣板認出 want 的格直接回（呼叫端動作前照舊開彈窗核對）；
    縮圖（只比 want + 相似圖）命中的格照分數排：圖只屬於 want → 直接回；同圖多名 → 讀那格名字（名字沒顯示才開彈窗）。
    auto / iconocr 沒命中 → 照舊路徑（圖示樣板 / 格名 OCR / 逐格彈窗）。彈窗 / OCR 精確核對過的格順便學名字樣板（_learn_verified）。
    有圖示樣板：① 圖示比對只挑吻合的格（不掃全部格）→ ② 點進去核對彈窗名稱，相符才回傳（不靠格名 OCR，不逐格開彈窗）。
    沒樣板：逐格 OCR 名稱；找不到再逐格開彈窗讀名稱（慢、保險）"""
    kind = 'depot' if depot else 'bag'
    tried = set()
    if hint is not None and 0 <= hint < n_slots(depot) and _popup_verify(hint, depot, want, tried):
        return hint
    ir = icon_read(kind, [want], pool=[]) if ITEM_MATCH != 'ocr' else None   # 只比 want + 相似圖（彈窗會核對，不用整個工作集）
    named = {}
    if ir is not None:                                 # 名字樣板 / 縮圖（GameClient 道具圖）挑格 → 呼叫端開彈窗核對名稱（通常 1 格）
        named = ir.get('named') or {}
        LAST['icon_hits'] = ir['hits'].get(want) or []
        for i in ir['hits'].get(want) or []:
            if i in tried:
                continue
            c = ir['cells'][i]
            if c.get('by') == 'name' or not c.get('ambiguous'):
                return i                               # 名字樣板認出 / 這張圖只屬於 want（呼叫端動作前照舊開彈窗核對名稱）
            t = read_slot_name(i, depot)               # 同圖多名（千年龜的殼 / 未知的殼 / 1～5轉新手禮盒…）：先讀這格名字（約 0.2 s）
            if t.strip() and name_match(t, want) and not digit_unsure(t, want):
                _learn_ocr(kind, {i: t})
                return i
            if _popup_verify(i, depot, want, tried):   # 格名沒讀到 / 讀成別的 / 數字讀不清：同圖多名一律開彈窗核對（2026-10-17 改：舊版讀成別的名字就跳過）
                return i
        if not _use_ocr():
            return None
        # auto：沒中 ≠ 沒有（被蓋住 / 沒學過名字 / 沒有道具圖 / 分數不夠）→ 照舊路徑再確認
    skip = tried | {i for i, n in named.items() if not _may_be(n, want)}    # 名字樣板認出「確定是別的道具」的格不必再開（只差數字 / 同圖多名不算，2026-10-17）
    cand = icon_match_slots(want, depot)
    if cand is not None:
        for i in cand:
            if i in skip:
                continue
            if _popup_verify(i, depot, want, tried):
                return i
        return None
    if not depot:
        ensure_names_shown()                          # 名稱被關掉時格名稱 OCR 全空，只能逐格開彈窗（慢）
    unread = []
    for i in range(n_slots(depot)):
        if i in skip:
            continue
        t = read_slot_name(i, depot)
        if t and name_match(t, want):
            if not digit_unsure(t, want):
                _learn_ocr(kind, {i: t})
                return i
            if _popup_verify(i, depot, want, tried):  # 格名吻合但數字讀不清（「轉新手禮盒」）→ 彈窗核對
                return i
            continue
        unread.append((-sum(1 for c in set(norm_name(want)) if c in norm_name(t)), i))
    if not popup_fallback:
        return None
    for _, i in sorted(unread):                       # 名稱 OCR 有重疊字的格先開（龍王的守護格曾被讀成「守 4-0」）
        if _popup_verify(i, depot, want, tried):      # 空格不會開彈窗
            return i
    return None


# ---- 同名多疊：讀每疊數量 / 依數量選格（2026-10-15 petquest 恐龍博士：背包同時有「要留的 4 個」與「要存回的 46 個」兩疊，find_item 只回第一格 → 存錯疊）----
SPLIT_QTY_BOX = (670, 430, 170, 45)     # 拆分「數量輸入」視窗裡的疊數（2026-10-12 實機量）
SPLIT_CANCEL = (828, 545)               # 數量輸入視窗的取消鈕


def parse_qty(texts) -> int | None:
    """純函式：OCR 文字（字串或清單）→ 第一個 1～3 位數；沒有 None"""
    if not isinstance(texts, str):
        texts = ' '.join(str(t) for t in texts)
    m = re.search(r'\d{1,3}', texts)
    return int(m.group()) if m else None


SPLIT_ICON_QTY_BOX = (690, 325, 60, 50)  # 數量輸入視窗上方道具圖示角落的白色疊數（2026-10-15 實機）


def slot_count(i: int) -> dict:
    """背包頁第 i 格右下角疊數（彈窗開之前讀；numglyph 'slot' 像素字形，唯讀）→ {'value': int | None, 'n': 字數}。
    第一次樣板沒全認出就再讀一次（EXP 橫幅飄過）"""
    import numglyph
    r = {'value': None, 'n': -1}
    for _ in range(2):
        r = numglyph.read_box('slot', numglyph.slot_box(i))
        if r['value'] is not None:
            break
        uikit.sleep(0.3)
    return {'value': r['value'], 'n': r['n']}


def split_qty_read(slot_read: dict | None = None) -> int | None:
    """「數量輸入」視窗開著：讀整疊數量（2026-10-16 改，bag.stack_qty 與 rebirth_pets._split 共用）。
    numglyph 'qty' 像素切字為主（字數一定準），樣板認不全才用 OCR（-Dark 0 / -Light 180 / 圖示角落疊數），**OCR 位數必須等於像素字數**才採用；
    slot_read = 開彈窗前讀的背包格疊數（slot_count）：讀得到值就必須相等、只讀到字數就位數必須相等，否則不採用 → None（呼叫端不猜）。
    根因：10-16 p2 _split 用 OCR 預設參數讀成空（rc 164）；同類 OCR 會把 20 讀成 2"""
    import numglyph
    reads = [lambda: parse_qty(uikit.ocr(SPLIT_QTY_BOX, '-Dark', '0', '-Zooms', '2,3,4')),   # 2026-10-15 實機：預設 Dark 150 讀成空，不二值化才讀得到
             lambda: parse_qty(uikit.ocr(SPLIT_QTY_BOX, '-Light', '180', '-Zooms', '3,4')),
             lambda: parse_qty(uikit.ocr(SPLIT_ICON_QTY_BOX, '-Light', '180', '-Zooms', '4,8'))]
    r = numglyph.read_number('qty', numglyph.QTY_BOX, reads, uikit.sleep, tries=2, log=log)
    q = r['value']
    if q is None or not slot_read:
        return q
    sv, sn = slot_read.get('value'), slot_read.get('n') or 0
    if sv is not None and sv != q:
        log(f'數量輸入框讀 {q}，背包格疊數讀 {sv}：不一致 → 不採用')
        return None
    if sv is None and sn > 0 and len(str(q)) != sn:
        log(f'數量輸入框讀 {q}（{len(str(q))} 位），背包格疊數 {sn} 個字：位數不一致 → 不採用')
        return None
    return q


def stack_qty(i: int, want: str) -> int | None:
    """背包第 i 格（want）的疊數：開彈窗核對名稱 → 有「拆分」鈕才點、讀數量輸入視窗、按取消（不改變任何東西）；沒有「拆分」鈕 = 單個 → 1。
    名稱不符 / 開不了 / 讀不出 → None（呼叫端不可當 0 或猜值）。數量用 split_qty_read（像素字形 + 與背包格疊數交叉核對）"""
    sc = slot_count(i)
    if not open_slot_popup(i):
        return None
    try:
        if not name_match(popup_name(want), want):
            return None
        txt = re.sub(r'\s+', '', _ocr_join(POPUP_BTN_BOX, BTN_OPTS))
        if '拆分' not in txt:
            return 1
        if not _click(628, 648, POPUP, f'bag 讀疊數：拆分 {want}', wait_ms=700):
            return None
        q = split_qty_read(sc)
        uikit.gui('seq', f'click {SPLIT_CANCEL[0]} {SPLIT_CANCEL[1]}; wait 600', note='bag 讀疊數：取消數量輸入')
        return q
    finally:
        if popup_open():
            close_popup()


def stacks_of(want: str) -> list:
    """背包頁目前角色：同名道具每疊 → [(格號, 疊數 | None)]（格號由小到大）。名稱用格名 OCR（只讀有道具的格），再逐疊 stack_qty"""
    occ, texts = read_bag_names_ocr()
    idx = [i for i in range(n_slots()) if (occ is None or occ[i]) and texts.get(i) and name_match(texts[i], want)]
    return [(i, stack_qty(i, want)) for i in idx]


def pick_stack(stacks, pick: str | None = None, want_count: int | None = None):
    """純函式：[(格, 疊數)] → 選定格號 | None。want_count = 只要疊數剛好等於它的格（多個取格號小的；沒有 None）；
    pick = 'largest' / 'smallest'（疊數讀不出的不參與）；都沒給 = 第一格。"""
    if want_count is not None:
        return next((i for i, q in stacks if q == want_count), None)
    known = [(i, q) for i, q in stacks if q is not None]
    if pick == 'largest':
        return max(known, key=lambda t: (t[1], -t[0]))[0] if known else None
    if pick == 'smallest':
        return min(known, key=lambda t: (t[1], t[0]))[0] if known else None
    return stacks[0][0] if stacks else None


def _same_item(a, b) -> bool:
    """名稱相同（norm_name 後完全相等）"""
    na, nb = norm_name(a), norm_name(b)
    return bool(na) and na == nb


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
        r = _names_in_bag(names)
        out.update(r['found'])
        out['_free'] = r['free']
        if r['occ'] is not None:
            out['_unread'] = r['unread']
        out['_by'] = r['by']
        if r['ambiguous']:
            out['_ambiguous'] = r['ambiguous']
    return 0, out


def dedup_text(t) -> str:
    """純函式：格名稱 OCR 會把 zoom 2 / 3 兩次結果串起來（「杉的手環 杉的手環」）→ 去掉重複的片段"""
    seen = []
    for w in str(t or '').split():
        if w not in seen:
            seen.append(w)
    return ' '.join(seen)


def read_bag_names() -> tuple:
    """目前選中角色、背包頁：→ (occ | None, {格號: 名稱 OCR})（purge 用：勾選目標要名稱 OCR，提示窗清單再核對；不走縮圖）"""
    return read_bag_names_ocr()


def read_bag_names_ocr() -> tuple:
    """目前選中角色、背包頁：→ (occ | None, {格號: 名稱 OCR})；只讀有道具的格（像素判空格），名稱全空 = 「顯示道具名」被關 → 點開一次再讀"""
    occ = slot_occupancy()
    idx = [i for i in range(n_slots()) if occ is None or occ[i]]
    texts = {i: read_slot_name(i) for i in idx}
    if occ is not None and names_hidden(occ, texts) and ensure_names_shown(occ):
        texts = {i: read_slot_name(i) for i in idx}
    return occ, texts


def list_all(roles) -> tuple:
    """唯讀：逐人列背包每格名稱（Session 開一次）→ (rc, {角色: {'slots': {格號: 名稱}, 'free': 空格數, 'unread': [格號]}})。
    只看可見 15 格（3 列；2026-10-12 刪除模式紅框也只框 3 列）"""
    out = {}
    with Session() as s:
        if s.rc:
            return s.rc, out
        for r in roles:
            rc = select_role(r)
            if rc:
                return rc, out
            out[r] = read_bag_items()
    return 0, out


def read_bag_items() -> dict:
    """背包頁（角色已選好）每格是什麼 → {'slots': {格: 名稱}, 'free', 'unread': [格], 'by': {格: 'name'|'icon'|'ocr'}, 'icons': {格: {imageId, score, ambiguous}}}。
    auto：一次截圖 → 名字樣板認得的格用樣板名稱（確定）→ 其餘比 item_pool()（+ 相似圖）縮圖（同圖多名 → 「名(同圖)」並標 ambiguous，只是推定）
    → 還是沒認出 / 被蓋住的格才名稱 OCR（精確命中 Item 表的順便學名字樣板）。name / icon：認不出的格列 unread。ocr / 不能用截圖辨識：舊法（每格 OCR）"""
    ir = icon_read('bag', item_pool(), pool=[]) if ITEM_MATCH != 'ocr' else None
    if ir is None:
        occ, texts = read_bag_names_ocr()
        return {'slots': {i: dedup_text(t) for i, t in texts.items() if t.strip()},
                'free': occ.count(False) if occ else None,
                'unread': [i for i, t in texts.items() if not t.strip()], 'by': {i: 'ocr' for i, t in texts.items() if t.strip()}}
    occ, cells = ir['occ'], ir['cells']
    slots, by, icons = {}, {}, {}
    for i, c in sorted(cells.items()):
        if c['ok']:
            slots[i], by[i] = icon_label(c), c.get('by') or 'icon'
            if by[i] == 'icon':
                icons[i] = {'imageId': c['imageId'], 'score': c['score'], 'ambiguous': c['ambiguous']}
    unres = [i for i in ir['unresolved']]
    unread = []
    if unres and _use_ocr():
        texts = {i: read_slot_name(i) for i in unres}
        if names_hidden([i in unres for i in range(n_slots())], texts) and ensure_names_shown(occ):
            texts = {i: read_slot_name(i) for i in unres}
        for i in unres:
            t = dedup_text(texts[i])
            if t.strip():
                slots[i], by[i] = t, 'ocr'
            else:
                unread.append(i)
        _learn_ocr('bag', texts)
    else:
        unread = unres
    return {'slots': dict(sorted(slots.items())), 'free': occ.count(False), 'unread': unread, 'by': by, 'icons': icons,
            'icon_ms': ir['ms'], 'names_hidden': ir.get('names_hidden', False)}


def item_slots(want: str) -> list:
    """背包頁：want 的所有格號（同名多格，例：千年龜的殼不疊加、每個佔一格）。auto / name / icon：名字樣板 + 縮圖命中的格（名字樣板在前、各自分數高到低）；
    auto / iconocr 一格都沒中 → 名稱 OCR（舊法）。只是候選：動作前照舊開彈窗核對"""
    ir = icon_read('bag', [want], pool=[]) if ITEM_MATCH != 'ocr' else None
    if ir is not None and (ir['hits'].get(want) or not _use_ocr()):
        return sorted(ir['hits'].get(want) or [])
    _, texts = read_bag_names_ocr()
    return [i for i, t in sorted(texts.items()) if t.strip() and name_match(t, want)]


# ---- 刪除管理（bag.py purge，2026-10-12 實機量測：DKBO2 巴巴洛的許可證）----
# 普通模式下方三鈕：顯示道具名 968,561 / 刪除管理 968,625（紅區）/ 整理背包 968,688（藍）。
# 按刪除管理 → 刪除模式：道具區紅框、鈕變「刪除選中」968,625（紅）/「取消刪除」968,688（黃）；單擊格子 = 勾 / 取消勾（不開彈窗），
# 勾選標記 = 格子右上紅圓白勾（中心約 格中心 +29,-27，紅 (243,69,84)）。「刪除選中」→「提示」窗：綠字 `名稱*數量|…|` + 「是否批量刪除道具?」，
# 只有一顆「確定」715,557、右上 X 947,208（X 後仍在刪除模式、勾選保留）。**968,688 在普通模式是「整理背包」**，只准在 DELMODE 特徵吻合時點。
DEL_BTN, DEL_CANCEL = (968, 625), (968, 688)
DELOK_XY, DELX_XY = (715, 557), (947, 208)
# 特徵定義在 screen_sigs（watch 同一份，2026-10-15 改）：
#  刪除模式 = 紅框左 / 右 / 下緣 + 取消刪除（金）/ 刪除選中右段 + ✕，7 中 6；舊點 965,192（紅框上緣）會被快速戰鬥的「獲得 EXP」橫幅蓋住
#  （10-15 23:32 DKBO2 勾到第 4 格判「刪除模式特徵消失」rc 90、取消刪除也沒按 → 背包卡在刪除模式 → 重跑時 preflight 誤設驗證停手旗標）。
#  提示窗 = 「提示」單鈕窗框 8 中 7（避開清單 / 問句：舊點 690,470 在 4 行清單時是問句白字、520,300 在 5 行時是綠字）；
#  560,545 是米黃（丟寵等兩顆鈕的提示窗這裡是藍「確定」→ 不會混淆 pet.CONFIRM）。單鈕窗框和網路 / 任務提示窗相同，按確定前靠清單 OCR 核對。
DELMODE_SIG = screen_sigs.BAG_DELMODE_SIG
DELMODE = uikit.Panel('BAGDEL', None, DELMODE_SIG, None, esc_close=False, forbidden={'delete_sel': FORBID['delete_mgr'], 'expand': FORBID['expand']},
                      is_open_fn=lambda: uikit.sig_need(DELMODE_SIG, screen_sigs.BAG_DELMODE_NEED))
DELCONFIRM_SIG = screen_sigs.BAG_DELOK_FRAME
DELCONFIRM = uikit.Panel('BAGDELOK', None, DELCONFIRM_SIG, DELX_XY, esc_close=False,
                         is_open_fn=lambda: uikit.sig_need(DELCONFIRM_SIG, screen_sigs.BAG_DELOK_NEED))


def _delok_strict() -> bool:
    """嚴格的刪除確認窗（screen_sigs.bag_delok：單鈕窗框 + 壓暗的刪除模式背包 + 背包標題壓暗 + 綠字清單）。
    清殘留時用：只靠窗框會把網路 / 任務提示窗也當成刪除確認窗去點 X"""
    pts = screen_sigs.delok_points()
    cols = uikit.px(pts)
    return bool(cols) and screen_sigs.bag_delok(dict(zip(pts, cols)))


DELOK_STRICT = uikit.Panel('BAGDELOK_STRICT', None, None, None, esc_close=False, is_open_fn=_delok_strict)


def stuck_in_delmode() -> bool:
    """背包停在刪除模式或刪除確認窗（Session 開頭 / close_leftover 清殘留用）"""
    return uikit.is_open(DELMODE) or uikit.is_open(DELOK_STRICT)


DEL_LIST_BOX = (500, 300, 430, 160)
# 提示窗清單 OCR（2026-10-14 根因）：清單是亮綠字 (40,240,0)、置中、名稱會在行尾斷開（「…|龍」+「的魅力之笛*1|…」），3 種以上就 2～3 行。
# 舊版 `-Dark 0` 不二值化、每個 zoom 各叫一次 ocr.ps1：Windows OCR 常整行漏讀（062858 樣本 zoom 2 / 3 / 5 都漏中間行）→ 條數不符 96；
# 單條時又常把「馬」讀成「1丐」、豎琴只讀到「的豎琴」→ 「的豎琴」被當成保護的「風的豎琴」→ 96。
# 改成：第一輪 `-Green 150`（只留綠字，白色問句與米黃底全白）4 個 zoom 一次 ocr.ps1；判不過再加 `-Dark 0` 一輪合併判（見 del_list_ok）。
DEL_LIST_PASSES = [('g', ('-Green', 150, '-Zooms', '2,3,4,5')), ('d', ('-Dark', 0, '-Zooms', '2,3,4,5'))]
DEL_LINE_TOL = 12                                           # 同一行的 y 容差（行距實測 41）
MARK_DXY = (29, -27)
MARK_PROBE = [(dx, dy) for dx in (-6, -3, 0, 3, 6) for dy in (-6, -3, 0, 3, 6)]
MARK_MIN = 12                                   # 25 點至少幾點是紅（實測勾了 ≈ 20、沒勾 0：名稱字是黑白）
# purge 永遠不勾的名稱（PROTECT 之外）：二轉要交的四大洞窟產物與中間品（plan-182-finish §2.3）
PURGE_FORBID = ['大地的羈絆', '火的羽毛飾品', '風的鎖', '水的戒指', '雅哈奴的日記', '拉魯的項鍊', '不死鳥的羽毛', '風的豎琴',
                '深藍色石頭', '群青的水', '碧青水晶', '龍王的守護', '2倍智慧果', '離線水晶', '安撫之素', '寵物誘餌', '2轉新手禮盒']
# 背包滿時可以「不問人」自動 purge 的名單（questrun 背包滿 → 信箱流程用）= ui/bag.md「可刪除道具白名單」表，
# 但排除有條件的一項：「亞姆亞姆的斧頭」（任務完成後才刪；
# 2026-10-15 使用者：「龍的魅力之笛」（龍的巢穴解完就可刪）、「不可思議的貝殼」（彌生和日美子獎勵）可刪，已列入。
# 仙尼亞的花 / 郵寄物 / 切繩石是任務途中中間品（2017 / 2018），Task 表查不到是否為下一步條件；2026-10-14 使用者已知任務中途誤刪的風險並接受，仍列入。
# 而且同名有兩個道具：2448 是步 2 獎勵、2416 是步 1 要交的條件道具，用名稱刪會刪到進行中的任務道具）。
# test_questdefs 核對：每個名稱都在 bag.md 白名單表、不在 PROTECT / PURGE_FORBID、也不是任何 questdefs 任務的條件道具（不會刪到任務要交的東西）
MAZU_FAMILY = ['馬祖的斧頭', '馬祖的矛', '馬祖的棍棒']
AUTO_PURGE = ['儀之兜', '杉的手環', '龍之鎧', '龍之槍', '龍之衣', '月光的手鐲', '巴巴洛的許可證', '空想的衣服',
              '老爺爺的護身符', '薩頓家的秘藥', '山賊的羽飾',
              '馬祖的斧頭', '馬祖的矛', '馬祖的棍棒', '空想的帽子', '空想的豎琴',
              '仙尼亞的花', '郵寄物', '切繩石', '龍的魅力之笛', '不可思議的貝殼',
              '千年龜的殼']       # 2026-10-17 使用者加：不疊加、每個佔一格（同名多格 purge_role 全勾；「未知的殼」同圖但不在名單）


def mark_red(c) -> bool:
    r, g, b = c
    return r > 200 and g < 110 and b < 120


def slot_marked(cols) -> bool:
    """純函式：MARK_PROBE 各點顏色 → 這格有沒有被勾"""
    return sum(1 for c in cols if mark_red(c)) >= MARK_MIN


def marked_slots() -> list | None:
    """刪除模式：15 格哪些被勾（一次 uikit.px）；讀不到 None"""
    pts = [(x + MARK_DXY[0] + dx, y + MARK_DXY[1] + dy) for i in range(n_slots()) for x, y in [slot_xy(i)] for dx, dy in MARK_PROBE]
    cols = uikit.px(pts)
    if not cols or len(cols) != len(pts):
        return None
    k = len(MARK_PROBE)
    return [i for i in range(n_slots()) if slot_marked(cols[i * k:(i + 1) * k])]


def purge_guard(text) -> str | None:
    """名稱（OCR）吻合 PROTECT / PURGE_FORBID → 回吻合的保護名；否則 None"""
    for p in list(PROTECT) + PURGE_FORBID:
        if name_match(text, p, 0.8):
            return p
    return None


def purge_target(text, names) -> str | None:
    """純函式：格名稱 OCR → 吻合名單內哪個名稱（不吻合 / 被保護 → None）"""
    t = dedup_text(text)
    if not t.strip() or purge_guard(t):
        return None
    return next((n for n in names if name_match(t, n)), None)


DEL_SPLIT = re.compile(r"[*+'’‘`´]\s*[0-9lI]*\s*[|丨｜]?|[|丨｜]")      # 條目結尾「*1|」：* 常讀成 + / '，| 常讀成 丨 / l，數量偶爾掉
DEL_QUESTION = re.compile(r'是否|批量|刪除道具|删除道具|道具[?？]')


def del_entries(lines) -> list:
    """純函式：提示窗某一個 zoom 的 OCR 行（依 y 排好）→ 條目清單。行與行直接串起來（名稱會在行尾斷開），
    「是否批量刪除道具?」問句從出現處截掉（不二值化時偶爾和清單黏成同一行），再用 *數量| 切、去數量"""
    body = ''
    for t in lines or []:
        t = re.sub(r'\s+', '', str(t))
        m = DEL_QUESTION.search(t)
        body += t[:m.start()] if m else t
    out = []
    for e in DEL_SPLIT.split(body):
        e = e.strip().lstrip('lI').rstrip('0123456789*')
        if norm_name(e):
            out.append(e)
    return out


_item_names: list | None = None


def item_names() -> list:
    """Item 表所有繁中名稱（norm_name 後去重）；讀不到 = []（只剩保護名單當「別的道具」）"""
    global _item_names
    if _item_names is None:
        out = set()
        try:
            with open(uikit.ROOT / 'knowledge' / 'data' / 'tables' / 'Item.jsonl', encoding='utf-8') as f:
                for ln in f:
                    m = re.search(r'"nameTn"\s*:\s*"([^"]*)"', ln)
                    if m and norm_name(m.group(1)):
                        out.add(norm_name(m.group(1)))
        except OSError:
            pass
        _item_names = sorted(out)
    return _item_names


def _subseq(a: str, b: str) -> bool:
    """a 的字依序都出現在 b 裡（OCR 掉字後的片段）"""
    it = iter(b)
    return all(c in it for c in a)


def _ratio(a: str, b: str) -> float:
    return difflib.SequenceMatcher(None, a, b).ratio()


def _window(a: str, b: str) -> float:
    """b 在 a 裡的最佳子字串視窗相似度（同 name_match 的視窗；a 比 b 短時就是整段比）"""
    n = len(b)
    return max(_ratio(a[i:i + n], b) for i in range(max(1, len(a) - n + 1)))


def del_classify(entry, names, others=None) -> tuple:
    """純函式：提示窗一個條目 → ('target', 名稱) / ('protected', 保護名) / ('other', 別的道具名) / ('unknown', None)。
    names = 這次勾的名稱；others = 其他道具名（預設 Item 表全部，扣掉 names）。規則（2026-10-14 重寫）：
      - 條目是某個勾選名稱的「片段」（字依序都在名稱裡，例：「的豎琴」⊂ 空想的豎琴）時，不會被判成保護 / 別的道具，
        但同時也是保護 / 別的道具的片段（「的豎琴」⊂ 風的豎琴）→ unknown（要靠別的 zoom 讀全名）
      - 吻合保護名稱（PROTECT + PURGE_FORBID，相似度或視窗 ≥ 0.8）且不是勾選名稱的片段 → protected（整批不刪）
      - 對勾選名稱相似度 ≥ 0.72 且嚴格高於任何別的道具 → target；條目不得比名稱長 2 字以上（兩條黏在一起）
      - 掉字片段（≥ 60% 長）只是某勾選名稱的片段、不是任何別的道具 / 保護名的片段 → target
      - 對別的道具相似度 ≥ 0.8 且高於勾選名稱 → other
    條目開頭的數字 / l 會試「去掉」與「保留」兩種讀法（「1丐祖的矛」→「丐祖的矛」；2倍智慧果 的 2 要保留）"""
    e0 = norm_name(entry).translate(OCR_CONFUSE)
    vs = [v for v in dict.fromkeys([e0, e0.lstrip('0123456789lI')]) if len(v) >= 2]
    if not vs:
        return 'unknown', None
    prot = [norm_name(p).translate(OCR_CONFUSE) for p in list(PROTECT) + PURGE_FORBID]
    tgt = {}
    for n in names:
        w = norm_name(n).translate(OCR_CONFUSE)
        if w and w not in prot and not purge_guard(n):
            tgt.setdefault(w, n)
    if not tgt:
        return 'unknown', None
    oth = [o.translate(OCR_CONFUSE) for o in (item_names() if others is None else [norm_name(x) for x in others])]
    oth = [o for o in dict.fromkeys(oth) if o and o not in tgt and o not in prot]

    frag_t = any(_subseq(v, w) for v in vs for w in tgt)
    t_best, t_name = 0.0, None
    for v in vs:
        for w, n in tgt.items():
            if len(v) <= len(w) + 2:
                r = _ratio(v, w)
                if r > t_best:
                    t_best, t_name = r, n
    t_frag = next((n for v in vs for w, n in tgt.items() if _subseq(v, w) and len(v) >= -(-len(w) * 3 // 5)), None)

    p_best, p_name = 0.0, None
    for v in vs:
        for w, p in zip(prot, list(PROTECT) + PURGE_FORBID):
            r = max(_ratio(v, w), _window(v, w))
            if r > p_best:
                p_best, p_name = r, p
    p_frag = any(_subseq(v, w) for v in vs for w in prot)
    if p_best >= 0.8 and not frag_t:
        return 'protected', p_name

    o_best, o_name = 0.0, None
    for v in vs:
        for o in oth:
            if len(v) > len(o) + 2 or len(o) > len(v) * 3:
                continue
            sm = difflib.SequenceMatcher(None, v, o)
            if sm.real_quick_ratio() <= o_best or sm.quick_ratio() <= o_best:
                continue
            r = sm.ratio()
            if r > o_best:
                o_best, o_name = r, o
    o_frag = any(_subseq(v, o) and len(v) >= -(-len(o) * 3 // 5) for v in vs for o in oth)

    if p_best >= 0.8 and p_best >= t_best:
        return 'unknown', None                        # 勾選名稱與保護名稱共有的片段：不判
    if t_best >= 0.72 and t_best > max(o_best, p_best):
        return 'target', t_name
    if t_frag and not o_frag and not p_frag:
        return 'target', t_frag
    if o_best >= 0.8 and o_best > t_best and not frag_t:
        return 'other', o_name
    return 'unknown', None


def del_entry_name(entry, names, others=None) -> str | None:
    """純函式：條目是不是名單內某個名稱 → 名稱 / None（見 del_classify；保護 / 別的道具 / 判不出都 None）"""
    kind, n = del_classify(entry, names, others)
    return n if kind == 'target' else None


def _reading_texts(lines) -> list:
    """一個 zoom 的行（str 或 ocr.ps1 的 dict）→ 依 y 排序的文字（str 沒有 y，維持原順序）"""
    ds = [ln if isinstance(ln, dict) else {'text': ln} for ln in lines or []]
    if all('y' in d for d in ds):
        ds = sorted(ds, key=lambda d: d['y'])
    return [str(d.get('text', '')) for d in ds]


def _reading_ys(lines) -> list | None:
    """一個 zoom 有字（去掉問句後）的行的 y；行是純 str（測試 / 舊格式）→ None（不做完整度檢查）"""
    ys = []
    for ln in lines or []:
        if not isinstance(ln, dict) or 'y' not in ln:
            return None
        t = re.sub(r'\s+', '', str(ln.get('text', '')))
        m = DEL_QUESTION.search(t)
        if norm_name(t[:m.start()] if m else t):
            ys.append(ln['y'])
    return ys


def del_list_ok(readings, names, n_marked: int, others=None) -> tuple:
    """純函式：{讀法: 行} → (ok, 說明)。讀法 = (pass, zoom) 或 zoom 字串；行 = str 或 ocr.ps1 的 dict（有 y 才做漏行檢查）。
    1. 任何讀法、任何條目吻合保護名稱 → 不過。
    2. 行數：所有讀法有字的行依 y 分群，≥ 2 個讀法讀到的群才算真的行；漏任何一行的讀法不採用（Windows OCR 會整行漏讀）。
    3. 候選讀法 = 沒漏行、條目數 == 勾選數（像素勾選）。沒有候選 → 不過。
    4. 逐位置合併：每個位置至少一個候選讀法判成勾選名稱、沒有候選把它判成別的名稱 / 別的道具；位置名稱的多重集合 == 勾選名稱多重集合。
    names = 每個勾選格的名稱（同名多格就重複列）"""
    want = list(names)
    # 2026-10-15：馬祖的斧頭 / 矛 / 棍棒同圖（背包縮圖只能推定其一）→ 提示窗讀到同家族的名字視為同一類（都是 AUTO_PURGE 白名單）
    fam = [n for n in MAZU_FAMILY if n in want]
    want_cls = want + [n for n in MAZU_FAMILY if fam and n not in want]
    ents = {k: del_entries(_reading_texts(v)) for k, v in readings.items()}
    cls = {k: [del_classify(e, want_cls, others) for e in es] for k, es in ents.items()}
    for k, cs in cls.items():
        for e, (kind, n) in zip(ents[k], cs):
            if kind == 'protected':
                return False, f'讀法 {k} 條目 {e!r} 吻合保護道具 {n}'
    if not any(ents.values()):
        return False, '提示窗讀不到任何條目'
    ys = {k: _reading_ys(v) for k, v in readings.items()}
    groups = []                                             # [y, 讀到的讀法集合]
    for k, yy in ys.items():
        for y in yy or []:
            g = next((g for g in groups if abs(g[0] - y) <= DEL_LINE_TOL), None)
            if g:
                g[1].add(k)
            else:
                groups.append([y, {k}])
    real = [g for g in groups if len(g[1]) >= 2] or groups
    complete = {k for k in readings if ys[k] is None or all(k in g[1] for g in real)}
    cand = [k for k in readings if k in complete and len(ents[k]) == n_marked]
    if not cand:
        return False, f'沒有完整讀法的條目數 = 勾選數 {n_marked}（各讀法條目數 { {str(k): len(v) for k, v in ents.items()} }，行數 {len(real)}）'
    got = []
    for i in range(n_marked):
        cs = [cls[k][i] for k in cand]
        tn = {n for kind, n in cs if kind == 'target'}
        bad = [(kind, n) for kind, n in cs if kind in ('other', 'protected')]
        if bad:
            return False, f'第 {i + 1} 條被判成別的道具 {bad}（讀到 {[ents[k][i] for k in cand]}）'
        if len(tn) != 1:
            return False, f'第 {i + 1} 條判不出唯一名稱 {sorted(tn)}（讀到 {[ents[k][i] for k in cand]}）'
        got.append(tn.pop())
    def _fam(n):
        return '馬祖的' if n in MAZU_FAMILY else n
    if sorted(map(_fam, got)) != sorted(map(_fam, want)):
        return False, f'條目 {got} 與勾選 {want} 不一致'
    return True, f'條目 {got}（候選讀法 {len(cand)} 個）'


def del_list_read(passes=None) -> dict:
    """提示窗開著：依 passes 讀清單 → {(pass, zoom): [行 dict]}（每個 pass 一次 ocr.ps1、4 個 zoom）"""
    out = {}
    for tag, opts in passes or DEL_LIST_PASSES:
        for ln in uikit.ocr_lines(DEL_LIST_BOX, *opts):
            out.setdefault((tag, ln.get('zoom')), []).append(ln)
    return out


def del_list_check(names, n_marked: int) -> tuple:
    """提示窗開著：綠字一輪判；不過再加不二值化一輪合併判 → (ok, 說明, {讀法: [文字]})"""
    rd = del_list_read(DEL_LIST_PASSES[:1])
    ok, why = del_list_ok(rd, names, n_marked)
    if not ok:
        rd.update(del_list_read(DEL_LIST_PASSES[1:]))
        ok, why = del_list_ok(rd, names, n_marked)
    return ok, why, {f'{k[0]}{k[1]}': [str(d.get('text', '')) for d in v] for k, v in rd.items()}


def _leave_delmode() -> bool:
    """刪除模式 / 提示窗開著 → X / 取消刪除，回到普通背包頁；回 True = 已回到普通模式"""
    if uikit.is_open(DELCONFIRM):
        uikit.safe_click(DELX_XY[0], DELX_XY[1], DELCONFIRM, note='bag purge 提示窗 X（取消）', wait_ms=500)
        _wait(lambda: not uikit.is_open(DELCONFIRM), 1.5)
    if uikit.is_open(DELMODE) or (not uikit.is_open(BAG) and _wait(lambda: uikit.is_open(DELMODE), 1.5)):   # 一時被 EXP 橫幅等蓋住：多等 1.5 s 再看
        uikit.safe_click(DEL_CANCEL[0], DEL_CANCEL[1], DELMODE, note='bag purge 取消刪除', wait_ms=500)
    return _wait(lambda: uikit.is_open(BAG), 2.0)


PURGE_BATCH = 5      # 提示窗一次勾太多件 OCR 讀不全（p3 2026-10-16 勾 8～9 件核對不過）→ 每批最多 5 件


def purge_role(role: str, names, dry_run: bool = False, _only=None) -> tuple:
    """單人（背包已開、在背包頁）：只勾名單內道具 → 讀提示窗清單核對 → 確定。→ (rc, {'targets': {格號: 名稱}, 'deleted': [名稱], 'skipped_unread': [格號]})"""
    info = {'targets': {}, 'deleted': []}
    rc = select_role(role)
    if rc:
        return rc, info
    occ, texts = read_bag_names()
    tg = {i: purge_target(t, names) for i, t in texts.items()}
    tg = {i: n for i, n in sorted(tg.items()) if n}
    if _only is not None:
        tg = {i: n for i, n in tg.items() if i in _only}
    elif len(tg) > PURGE_BATCH and not dry_run:          # 分批：先刪前 PURGE_BATCH 件，再遞迴處理剩下的
        rc, info = purge_role(role, names, dry_run, _only=set(list(tg)[:PURGE_BATCH]))
        if rc:
            return rc, info
        rc2, info2 = purge_role(role, names, dry_run)
        info['deleted'] = info.get('deleted', []) + info2.get('deleted', [])
        info['targets'] = {**info.get('targets', {}), **info2.get('targets', {})}
        return rc2, info
    info['targets'] = tg
    info['skipped_unread'] = [i for i, t in texts.items() if not t.strip()]
    guarded = {i: purge_guard(dedup_text(t)) for i, t in texts.items() if t.strip() and purge_guard(dedup_text(t))}
    if guarded:
        info['protected'] = guarded
    if not tg or dry_run:
        return 0, info
    want = sorted(tg)
    if not _click(DEL_BTN[0], DEL_BTN[1], BAG, f'bag purge {role} 刪除管理', allow=('delete_mgr',), wait_ms=500):
        return _fail(EXIT_PANEL, '背包頁特徵不在，沒按刪除管理', 'bag-purge-nobag'), info
    if not _wait(lambda: uikit.is_open(DELMODE), 2.0):
        return _fail(EXIT_PANEL, '按了刪除管理但沒看到刪除模式（紅框 / 取消刪除鈕）', 'bag-purge-nodel'), info
    pre = marked_slots()
    if pre is None or pre:
        _leave_delmode()
        return _fail(EXIT_GUARD, f'剛進刪除模式就有勾選 {pre}（或讀不到），不動', 'bag-purge-premark'), info
    for i in want:
        x, y = slot_xy(i)
        note = f'bag purge {role} 勾第 {i + 1} 格 {tg[i]}'
        if not _click(x, y, DELMODE, note, wait_ms=250) and not (_wait(lambda: uikit.is_open(DELMODE), 2.0) and _click(x, y, DELMODE, note, wait_ms=250)):
            # 特徵一時不在（EXP 橫幅等）先等 2 s 再試一次；還是不在才放棄
            _leave_delmode()
            return _fail(EXIT_PANEL, '刪除模式特徵消失，停止勾選', 'bag-purge-gone'), info
    uikit.sleep(0.3)
    got = marked_slots() or []
    for i in [i for i in want if i not in got]:            # 勾選偶爾沒吃到（ui/bag.md）：補點一次
        x, y = slot_xy(i)
        _click(x, y, DELMODE, f'bag purge {role} 補勾第 {i + 1} 格', wait_ms=300)
    got = marked_slots() if [i for i in want if i not in got] else got
    if got != want:
        _leave_delmode()
        return _fail(EXIT_GUARD, f'像素勾選 {got} 與目標 {want} 不一致 → 取消刪除', f'bag-purge-mark-{role}'), info
    for k in range(3):                                      # 「戰鬥中無法操作」時提示窗不出來：隔 2.5 s 再按（勾選保留）
        if not _click(DEL_BTN[0], DEL_BTN[1], DELMODE, f'bag purge {role} 刪除選中', allow=('delete_sel',), wait_ms=500):
            break
        if _wait(lambda: uikit.is_open(DELCONFIRM), 2.0):
            break
        uikit.sleep(2.5)
    if not uikit.is_open(DELCONFIRM):
        _leave_delmode()
        return _fail(EXIT_VERIFY, '按了刪除選中但提示窗沒出現', 'bag-purge-noconfirm'), info
    ok, why, info['confirm_ocr'] = del_list_check([tg[i] for i in want], len(want))
    if not ok:
        shot = uikit.snap(f'bag-purge-list-{role}')         # 提示窗還開著時存圖（舊版 X 之後才存，看不到清單）
        _leave_delmode()
        ocr_s = json.dumps(info['confirm_ocr'], ensure_ascii=False)[:600]
        return _fail(EXIT_NAME, f'{role} 提示窗清單核對不過：{why} → 按 X 取消；OCR {ocr_s}；截圖 {shot}'), info
    log(f'{role} 提示窗清單核對通過：{why}')
    _SHOT.clear()                                         # 格子內容要變了：之前的截圖不能再拿來學名字樣板
    if not uikit.safe_click(DELOK_XY[0], DELOK_XY[1], DELCONFIRM, note=f'bag purge {role} 確定刪除 {[tg[i] for i in want]}', wait_ms=700):
        _leave_delmode()
        return _fail(EXIT_VERIFY, '提示窗特徵消失，沒按確定', 'bag-purge-confirm-gone'), info
    if not _wait(lambda: not uikit.is_open(DELCONFIRM), 2.5):
        return _fail(EXIT_VERIFY, '按了確定但提示窗沒關（不重點）', 'bag-purge-confirm-stay'), info
    if not _leave_delmode():
        return _fail(EXIT_PANEL, '刪除後回不到普通背包頁', 'bag-purge-leave'), info
    if not _wait(lambda: not any((slot_occupancy() or [True] * n_slots())[i] for i in want), 4.0):
        return _fail(EXIT_VERIFY, f'刪除後第 {[i + 1 for i in want]} 格仍有道具', f'bag-purge-verify-{role}'), info
    info['deleted'] = [tg[i] for i in want]
    return 0, info


def purge(roles, names, dry_run: bool = False) -> tuple:
    """多人刪除管理（背包面板開一次、左欄頭像切人）。names 有任何一個是保護名稱 → 93 零點擊。→ (rc, {角色: info})；某人失敗立即停"""
    out = {}
    bad = [n for n in names if purge_guard(n)]
    if bad:
        return _fail(EXIT_GUARD, f'名單含保護道具 {bad}，拒絕'), out
    with Session() as s:
        if s.rc:
            return s.rc, out
        for r in roles:
            rc, out[r] = purge_role(r, names, dry_run)
            if rc:
                return rc, out
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
    _SHOT.clear()                                     # 使用 / 丟棄 / 穿戴後格子內容會變：之前的截圖不能再拿來學名字樣板
    if not _click(x, y, POPUP, f'bag 彈窗 {label}', allow=allow, wait_ms=500):
        return _fail(EXIT_PANEL, '彈窗特徵消失，沒點按鈕', 'bag-popup-gone'), b.get('kind')
    return 0, b['kind']


def use_item(role: str, want: str, verify_buff: bool = False) -> int:
    """背包找 want → 彈窗名稱核對 → 使用。回 0 只代表「按了使用、彈窗關了」，不代表伺服器真的扣了道具（2026-10-12 2倍智慧果
    按了使用、彈窗關了卻沒吃到）。verify_buff = 關背包後用 buff 圖示確認（BUFF_KIND 有的道具才看；找不到只警告，不重點）；
    要當成敗判準的呼叫端（depot_use.run）自己在關背包後看 has_buff。巢狀在外層 Session 裡（背包還開著）時 buff 列被蓋住，不看。結果 LAST['buff']"""
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
        nm = popup_name(want)
        if not name_match(nm, want):
            close_popup()
            return _fail(EXIT_NAME, f'彈窗名稱 OCR 是 {nm!r}，不是「{want}」（不使用）', 'bag-popup-name')
        _learn_verified('bag', i, want)
        rc, _ = click_popup_button('使用')
        if rc:
            close_popup()
            return rc
        if not _wait(lambda: not popup_open(), 2.0):
            if not verify_buff:
                return _fail(EXIT_VERIFY, '按了使用但彈窗沒關（不重點）', 'bag-use-verify')
            close_popup()                                # 疊加道具使用後彈窗可能還開著：ESC 關掉，不重點，成敗交給 buff 圖示判斷
            LAST['popup_stayed'] = True
    kind = buff_kind(want)
    if verify_buff and kind and not uikit.is_open(BAGANY):   # 背包關了才看得到 buff 列（舊版在 Session 裡看，永遠被面板蓋住）
        LAST['buff'] = _wait(lambda: has_buff(kind), 4.0)
        if not LAST['buff']:
            log(f'警告：使用後 buff 列沒看到 {kind} 圖示（不重點）')
            uikit.snap('bag-buff-unseen')
    return 0


def wear_item(role: str, want: str) -> int:
    """背包找裝備 want → 彈窗名稱核對 → 按「穿戴」→ 驗那一格不再是 want（穿上後格子變空、其他道具不移位；原本有同部位裝備時舊的換到那格，ui/bag.md）。
    背包沒有 = 92（呼叫端判斷：已穿上 / 這人沒有）。按鈕列不是裝備版型（沒有「穿戴」）= 96 不點。
    新角色開局（newchar.py）穿新手棍棒 / 鎧甲 / 頭盔用；**2026-10-15 寫成，實機未驗證**（座標同 2026-10-09 手動穿戴實測 618,662）。結果 LAST['slot']"""
    LAST.clear()
    with Session() as s:
        if s.rc:
            return s.rc
        rc = select_role(role)
        if rc:
            return rc
        i = find_item(want)
        if i is None:
            return _fail(EXIT_ITEM, f'{role} 背包找不到「{want}」（已穿上？）', 'bag-noitem')
        LAST['slot'] = i
        if not open_slot_popup(i):
            return _fail(EXIT_PANEL, f'點第 {i + 1} 格沒開彈窗', 'bag-nopopup')
        nm = popup_name(want)
        if not name_match(nm, want):
            close_popup()
            return _fail(EXIT_NAME, f'彈窗名稱 OCR 是 {nm!r}，不是「{want}」（不穿）', 'bag-popup-name')
        _learn_verified('bag', i, want)
        rc, _ = click_popup_button('穿戴')
        if rc:
            close_popup()
            return rc
        if not _wait(lambda: not popup_open(), 2.0):
            return _fail(EXIT_VERIFY, '按了穿戴但彈窗沒關（不重點）', 'bag-wear-verify')

        def worn(i=i):
            occ = slot_occupancy()
            if occ and not occ[i]:
                return True                              # 格子變空 = 穿上了
            return find_item(want, popup_fallback=False) != i   # 換下的舊裝備佔了那格：那格不再是 want 也算
        if not _wait(worn, 4.0):                         # 背包頁更新有延遲（同存入 / 取出）
            return _fail(EXIT_VERIFY, f'按了穿戴但第 {i + 1} 格仍是「{want}」（不重點）', 'bag-wear-verify')
    return 0


def wear_many(roles, names, skip_missing: bool = True) -> tuple:
    """多人穿多件（背包面板只開一次，逐人切頭像穿完）。skip_missing：背包沒有（92 = 已穿上 / 沒有）略過。
    → (rc, {角色: {名稱: rc}})；某人其他失敗立即停"""
    out: dict = {}
    with Session() as s:
        if s.rc:
            return s.rc, out
        for r in roles:
            res = out.setdefault(r, {})
            for nm in names:
                rc = wear_item(r, nm)
                res[nm] = rc
                if rc == EXIT_ITEM and skip_missing:
                    continue
                if rc:
                    return rc, out
    return 0, out


def equipped_name() -> str | None:
    """武器格彈窗名稱（空格 = 沒彈窗 → None）；讀完 ESC 關"""
    if not _click(WEAPON_SLOT[0], WEAPON_SLOT[1], BAG, 'bag 點武器格'):
        return None
    if not _wait(popup_open, 1.2):
        return None
    nm = popup_name()
    close_popup()
    return nm or None


def discard_item(role: str, slot: int, expect: str, forbid=None, allow_protected: bool = False) -> int:
    """丟棄背包第 slot 格（假設已選好角色、在背包分頁）。彈窗名稱與提示窗名稱都必須吻合 expect 且不吻合 PROTECT / forbid。
    丟棄鈕只有這裡用 allow=('discard',) 點。成功 = 提示窗關了且該格名稱不再吻合"""
    bad = ([] if allow_protected else list(PROTECT)) + list(forbid or [])
    if not allow_protected and (protected(expect) or any(name_match(expect, b, 0.8) for b in bad)):
        return _fail(EXIT_GUARD, f'要丟的名稱「{expect}」在保護名單（{bad}）內，拒絕')
    if not open_slot_popup(slot):
        return _fail(EXIT_PANEL, f'第 {slot + 1} 格沒開彈窗（空格？），不丟', 'bag-drop-nopopup')
    nm = popup_name(expect)
    if not nm or not name_match(nm, expect) or any(name_match(nm, b, 0.8) for b in bad):
        close_popup()
        return _fail(EXIT_NAME, f'彈窗名稱 OCR 是 {nm!r}，不是預期的「{expect}」（或在保護名單）→ 不丟', 'bag-drop-name')
    _learn_verified('bag', slot, expect)
    rc, kind = click_popup_button('丟棄', allow=('discard',))
    if rc:
        close_popup()
        return rc
    import pet
    # 兩種版型都認：DROP2（丟棄 613,543 / 取消 820,543）優先，其次 pet.CONFIRM（確定 612,551 / 取消 813,557）；名稱驗證兩版都要過才按
    if not _wait(lambda: uikit.is_open(DROP2) or uikit.is_open(pet.CONFIRM), 2.0):
        return _fail(EXIT_VERIFY, '按了丟棄但提示窗沒出現（兩種版型都不吻合；不重點）', 'bag-drop-noconfirm')
    kind2 = 'drop2' if uikit.is_open(DROP2) else 'pet'
    pan = DROP2 if kind2 == 'drop2' else pet.CONFIRM
    box = DROP2_NAME_BOX if kind2 == 'drop2' else pet.CONFIRM_BOX
    ok_xy, cancel_xy = (DROP2_OK, DROP2_CANCEL) if kind2 == 'drop2' else (DISCARD_OK, (813, 557))
    ct = _ocr_join(box, [('-Dark', 0, '-Zooms', '2,3,4'), ('-Dark', 120, '-Zooms', '2,3')])
    if not ct or not name_match(ct, expect) or any(name_match(ct, b, 0.8) for b in bad):
        uikit.safe_click(cancel_xy[0], cancel_xy[1], pan, note='bag 丟棄提示窗名稱不符 → 取消')
        return _fail(EXIT_NAME, f'提示窗名稱 OCR 是 {ct!r}，不是預期的「{expect}」→ 已取消', 'bag-drop-confirm-name')
    LAST['drop_confirm'] = kind2
    if not uikit.safe_click(ok_xy[0], ok_xy[1], pan, note=f'bag 丟棄「{expect}」確定（{kind2} 版提示窗）', wait_ms=600):
        return _fail(EXIT_VERIFY, '提示窗特徵消失，沒點確定', 'bag-drop-confirm-gone')
    if not _wait(lambda: not uikit.is_open(pan), 2.5):
        return _fail(EXIT_VERIFY, '按了確定但提示窗沒關（不重點）', 'bag-drop-verify')
    left = read_slot_name(slot)
    if left and name_match(left, expect):
        return _fail(EXIT_VERIFY, f'丟完第 {slot + 1} 格仍讀到「{expect}」', 'bag-drop-still')
    LAST['dropped'] = expect
    return 0


def drop_item(role: str, want: str, confirm_name: str, allow_protected: bool = False) -> int:
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
        return discard_item(role, i, want, allow_protected=allow_protected)


def weapons(roles) -> tuple:
    """唯讀：開背包一次、逐人點左欄頭像讀武器格彈窗名稱（讀完 ESC 關，不按任何彈窗按鈕）→ (rc, {role: 名稱 | None})"""
    out = {}
    with Session() as s:
        if s.rc:
            return s.rc, out
        for r in roles:
            rc = select_role(r)
            if rc:
                return rc, out
            out[r] = equipped_name()
            sp = uikit.snap(f'weapon-{r}')              # 留證：複製成 tools/.cache/weapon-<角色>.png
            if sp:
                try:
                    import shutil
                    shutil.copyfile(uikit.ROOT / sp, uikit.CACHE / f'weapon-{r}.png')
                except OSError:
                    pass
    return 0, out


def _drop_spare(role: str, bow: str) -> int:
    """（Session 內、已選好角色、武器格已確認是 bow）背包裡還有 bow → 丟一把（--allow-protected 的精靈王之弓；武器格穿著的不在背包格）。
    背包沒有 = 已丟過（LAST['spare'] = 0）。每次只丟一把；丟完再找，還有 → 失敗（不連丟，防誤判武器格）"""
    j = find_item(bow)
    if j is None:
        LAST['spare'] = 0
        return 0
    rc = discard_item(role, j, bow, allow_protected=True)
    if rc:
        return rc
    LAST['spare'] = 1
    if find_item(bow) is not None:
        return _fail(EXIT_VERIFY, f'{role} 丟了一把「{bow}」後背包仍有（不連丟）', 'bag-spare-more')
    return 0


def drop_spare_bow(role: str, bow: str = '精靈王之弓') -> int:
    """獨立呼叫 / CLI：先確認武器格穿的就是 bow（不是就不丟）→ 丟背包裡多的那一把。結果 LAST（old / spare）"""
    LAST.clear()
    with Session() as s:
        if s.rc:
            return s.rc
        rc = select_role(role)
        if rc:
            return rc
        cur = equipped_name()
        LAST['old'] = cur
        if not cur or not name_match(cur, bow):
            return _fail(EXIT_GUARD, f'{role} 武器格不是「{bow}」（讀到 {cur!r}）→ 不丟背包裡的弓（可能是唯一一把）', 'bag-spare-noweapon')
        return _drop_spare(role, bow)


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
            LAST['already'] = True                      # 已經是弓（續跑 / 16F 直接穿上）；舊武器早丟過
            if keep_old:
                return 0
            return _drop_spare(role, bow)               # 16F 多給的那把（背包裡）要丟；武器格穿著的不動
        i = find_item(bow)
        if i is None:
            return _fail(EXIT_ITEM, f'{role} 背包找不到「{bow}」', 'bag-nobow')
        if not open_slot_popup(i):
            return _fail(EXIT_PANEL, f'點第 {i + 1} 格沒開彈窗', 'bag-nopopup')
        nm = popup_name(bow)
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
        cur = cur.split()[0] if cur.split() else cur      # 彈窗 OCR 可能連內文一起讀進來（p2 實測「新手棍棒 新手棍棒 新手棍棒 25」）→ 只取第一段名稱
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
    if _CUR.get('depot') != sub:
        _SHOT.pop('depot', None)                          # 個人 / 公共倉庫內容不同：舊的倉庫格截圖不能拿來學名字樣板
        _CUR['depot'] = sub
    if _sub_on(sub):
        return 0
    for attempt in range(SUB_RETRIES + 1):
        if _wait_tab_clear() == sub:                    # 子分頁列讀不懂（面板被蓋住）→ 等一下；已經是 sub 就不點
            return 0
        x, y = sub_click_xy(sub, attempt, _tab_cols())  # 公共中段被浮字橫幅蓋住 / 重點 → 改點左緣（橫幅會吃掉點擊）
        where = '' if (x, y) == SUB_XY[sub] else f'（左緣 {x},{y}）'
        if not _click(x, y, DEPOT, f'bag 倉庫切到{sub}{where}' + (f'（第 {attempt + 1} 次）' if attempt else '')):
            return _fail(EXIT_PANEL, '倉庫特徵不在，沒點子分頁', 'bag-depot-sub')
        if _wait(lambda: _sub_on(sub), 2.0):
            return 0
        log(f'點了 {sub} 子分頁沒切過去（目前 {_tab_state() or "讀不懂"}；可能被浮字橫幅吃掉點擊），改點分頁左緣再點')
    return _fail(EXIT_PANEL, f'點了 {sub} 子分頁 {SUB_RETRIES + 1} 次都沒切過去（目前 {_tab_state() or "讀不懂"}）', 'bag-depot-sub')


DCLICK = os.environ.get('PSA_DEPOT_DCLICK', '1') != '0'     # 雙擊存取（0 = 一律走彈窗 + 按鈕）


def _dclick_move(i: int, want: str, take: bool) -> bool:
    """**雙擊存取（2026-10-15 使用者指示，未實機）**：雙擊道具格整疊搬到另一邊，不開彈窗、不按存入 / 取出鈕。
    take=True：目前在倉庫頁，雙擊倉庫左半第 i 格；take=False：目前在倉庫頁，雙擊右半（背包）第 i 格。
    雙擊前先讀該格名稱核對 = want（讀不出 / 不符 → False 走原彈窗流程）；雙擊後驗證：
    - 取出：倉庫該格名稱不再吻合 want，切回背包頁後背包讀得到 want；
    - 存入：切回背包頁後該格像素變空（沒像素時退回「背包找不到 want」）。
    雙擊後若彈出了道具彈窗 / 驗證不到 → 關彈窗、回 False（呼叫端退回原流程；原流程自己再核對，已搬走的會回 92 / 名稱不符，不會重複搬）。
    成功 → True（存入時已在背包頁）。要拆分的情境不走這裡（雙擊一次搬整疊）。PSA_DEPOT_DCLICK=0 關閉"""
    if not DCLICK:
        return False
    nm = read_slot_name(i, True) if take else read_slot_name(i, False)
    if not (nm and name_match(nm, want)):
        return False
    x, y = depot_xy(i) if take else store_click_xy(i)  # 倉庫第 1 列 y=290 在橫幅下方；背包第 1 列改點下緣
    before = slot_occupancy() if take else None        # 倉庫頁右半 = 背包格（同座標）：取出後背包「多一格有東西」也算取到（名字被浮字橫幅蓋住讀不到時）
    _SHOT.clear()
    if not uikit.safe_dclick(x, y, DEPOT, f'bag 雙擊{"取出" if take else "存入"}「{want}」第 {i + 1} 格', wait_ms=900):
        return False
    if popup_open():                                   # 雙擊變成開了彈窗：不再補點，關掉退回原流程
        close_popup()
        return False
    if take:
        if not _wait(lambda: _depot_slot_left(i, want), 3.0):
            return False
        if goto_page('bag'):
            return False
        return _wait(lambda: _bag_gained(before) or find_item(want) is not None, 4.0)
    if goto_page('bag'):
        return False

    def gone():
        occ = slot_occupancy()
        return (not occ[i]) if occ else find_item(want) is None
    return _wait(gone, 4.0)


def _depot_slot_left(i: int, want: str) -> bool:
    """取出後倉庫第 i 格已不是 want：像素看該格變空（數量字帶，浮字橫幅蓋不到）或名字不再吻合"""
    occ = depot_occupancy()
    if occ and not occ[i]:
        return True
    return not name_match(read_slot_name(i, True) or '', want)


def _bag_gained(before) -> bool:
    """背包頁：跟 before（取出前的 slot_occupancy）比，多了一格有道具 → 取到了（不靠名字，浮字橫幅蓋住第 1 列名字時也判得出）"""
    now = slot_occupancy()
    return bool(before and now and len(before) == len(now) and any(n and not b for b, n in zip(before, now)))


def _take_via_popup(i: int, want: str, kind: str) -> int:
    """倉庫第 i 格 → 彈窗核對名稱 / 按鈕 → 按「取出」→ 切回背包頁驗證（原流程，已實機）"""
    if not open_slot_popup(i, depot=True):
        return _fail(EXIT_PANEL, f'點倉庫第 {i + 1} 格沒開彈窗（空格不要點取出，會進刪除管理）', 'bag-depot-nopopup')
    nm = popup_name(want)
    if not name_match(nm, want):
        close_popup()
        return _fail(EXIT_NAME, f'倉庫彈窗名稱 OCR 是 {nm!r}，不是「{want}」（不取）', 'bag-depot-name')
    _learn_verified('depot', i, want)
    txt = _ocr_join(POPUP_BTN_BOX, BTN_OPTS)
    if '取出' not in re.sub(r'\s+', '', txt):
        close_popup()
        return _fail(EXIT_NAME, f'倉庫彈窗按鈕列 OCR 是 {txt!r}，沒有「取出」', 'bag-depot-btn')
    uikit.sleep(POPUP_SETTLE_S)                      # 彈窗出現動畫期間點「取出」會落空（2026-10-11 實測：彈窗關了但道具沒動）
    x, y = (722, 662) if kind == 'equip' else (732, 648)
    before = slot_occupancy()                        # 彈窗疊在倉庫頁上，右半背包格仍看得到（彈窗在中間偏左，蓋不到右半的數量字帶時才有值）
    _SHOT.clear()                                    # 取出後倉庫 / 背包格內容會變
    if not _click(x, y, POPUP, f'bag 倉庫取出「{want}」', allow=(), wait_ms=700):
        return _fail(EXIT_PANEL, '彈窗特徵消失，沒點取出', 'bag-depot-gone')
    if not _wait(lambda: not popup_open(), 2.5):
        return _fail(EXIT_VERIFY, '按了取出但彈窗沒關（不重點）', 'bag-depot-verify')
    rc = goto_page('bag')
    if rc:
        return rc
    # 切回背包頁後格子要約 1～3 秒才更新（2026-10-11 實測：立刻找會找不到而誤判失敗並回滾存回），輪詢最多 4 秒
    if not _wait(lambda: _bag_gained(before) or find_item(want) is not None, 4.0):
        return _fail(EXIT_VERIFY, f'取出後背包讀不到「{want}」', 'bag-depot-verify')
    return 0


def depot_take(role: str, want: str, depot: str = 'public', kind: str = 'consumable', hint: int | None = None) -> int:
    """倉庫取出 want（整疊）。**雙擊取出為主（未實機）**：先 `_dclick_move`，驗證不到才退回彈窗 + 取出鈕。kind=equip 時取出鈕在 722,662。成功 = 倉庫左半該格不再吻合，且切回背包能找到"""
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
        i = find_item(want, depot=True, hint=hint) if hint is not None else find_item(want, depot=True)   # 沒 hint 維持舊呼叫形式（測試替身 / 其他呼叫端）
        if i is None:
            return _fail(EXIT_ITEM, f'{depot} 倉庫找不到「{want}」', 'bag-depot-noitem')
        LAST['depot_slot'] = i                           # 呼叫端（多人取同一物）下一人當 hint
        if _dclick_move(i, want, True):                  # 雙擊取出（2026-10-15，未實機）：成功 = 倉庫該格不再是 want，切回背包頁讀得到 want
            return 0
        if DCLICK:                                       # 雙擊失敗可能已切回背包頁 → 回倉庫頁再走彈窗
            rc = open_depot(depot)
            if rc:
                return rc
        rc = _take_via_popup(i, want, kind)
        if rc:
            return rc
    return 0


def _store_via_popup(i: int, want: str) -> int:
    """目前在倉庫頁：點右半（背包）第 i 格 → 彈窗核對名稱 / 按鈕 → 按「存入」→ 切回背包頁（原流程，已實機）"""
    # 倉庫頁右半是背包，座標同背包頁；面板特徵要用倉庫頁的（背包頁特徵在倉庫頁不吻合，safe_click 會擋）
    x, y = store_click_xy(i)
    if not _click(x, y, DEPOT, f'bag 倉庫頁點背包第 {i + 1} 格') or not _wait(popup_open, 1.5):
        return _fail(EXIT_PANEL, f'倉庫頁點背包第 {i + 1} 格沒開彈窗', 'bag-store-nopopup')
    nm = popup_name(want)
    if not name_match(nm, want):
        close_popup()
        return _fail(EXIT_NAME, f'彈窗名稱 OCR 是 {nm!r}，不是「{want}」（不存）', 'bag-store-name')
    _learn_verified('bag', i, want)                  # 倉庫頁右半 = 背包格（同座標同渲染）
    txt = _ocr_join(POPUP_BTN_BOX, BTN_OPTS)
    if '存入' not in re.sub(r'\s+', '', txt):
        close_popup()
        return _fail(EXIT_NAME, f'彈窗按鈕列 OCR 是 {txt!r}，沒有「存入」（不點）', 'bag-store-btn')
    uikit.sleep(POPUP_SETTLE_S)                      # 同取出：彈窗動畫期間點會落空
    _SHOT.clear()                                    # 存入後背包 / 倉庫格內容會變
    if not _click(732, 648, POPUP, f'bag 存入「{want}」', wait_ms=700):
        return _fail(EXIT_PANEL, '彈窗特徵消失，沒點存入', 'bag-store-gone')
    if not _wait(lambda: not popup_open(), 2.5):
        return _fail(EXIT_VERIFY, '按了存入但彈窗沒關（不重點）', 'bag-store-verify')
    rc = goto_page('bag')
    if rc:
        return rc
    return 0


def depot_store(role: str, want: str, depot: str = 'public', keep_ok: bool = False, all_copies: bool = False, pick: str | None = None, want_count: int | None = None) -> int:
    """背包 want 存入倉庫（**雙擊存入為主，未實機**：`_dclick_move` 雙擊整疊、驗該格變空，驗證不到才退回彈窗「存入」鈕；整疊）。keep_ok = 背包另有同名道具（拆分後的新疊）時不驗「消失」。沒有 want = 已存過（回 92，呼叫端自行判斷）。PROTECT 名稱一律不存。
    all_copies = 同名多格（不疊加的道具，例：千年龜的殼每個佔一格）一格一格存到背包沒有為止。
    同名多疊（2026-10-15）：pick = 'largest' / 'smallest' 或 want_count = 疊數剛好 N 的那疊（例：存回 46 個那疊、留下 4 個那疊）；
    指定時先逐疊讀疊數（stack_qty，拆分視窗讀完取消）選格，存之前再讀一次選中格疊數，對不上（或讀不出）→ 不按存入、回 95（EXIT_VERIFY）；找不到符合的疊 → 92。
    驗證：存後輪詢到「那一格變空」（像素；存入後不補位，ui/bag.md）——舊版等「背包找不到」，同名多格時誤報 95；像素讀不到才退回「找不到」。結果 LAST['stored']"""
    LAST.clear()
    if protected(want):
        return _fail(EXIT_GUARD, f'「{want}」在保護名單，不存倉')
    stored = 0
    with Session() as s:
        if s.rc:
            return s.rc
        rc = select_role(role)
        if rc:
            return rc
        while True:
            qty_i = None
            if pick or want_count is not None:
                stks = stacks_of(want)
                i = pick_stack(stks, pick, want_count)
                qty_i = dict(stks).get(i) if i is not None else None
                if i is not None and qty_i is None:
                    return _fail(EXIT_VERIFY, f'{role}「{want}」第 {i + 1} 格疊數讀不出（不存）', 'bag-store-qty')
                if i is not None and want_count is not None and any(q is None for _, q in stks):
                    return _fail(EXIT_VERIFY, f'{role}「{want}」有疊數讀不出的格（不存）', 'bag-store-qty')
            else:
                i = find_item(want)
            if i is None:
                if stored:
                    break
                return _fail(EXIT_ITEM, f'{role} 背包找不到「{want}」' + (f'（指定 {pick or want_count}）' if pick or want_count is not None else ''), 'bag-noitem')
            if qty_i is not None:                            # 存之前再讀一次選中格疊數（背包頁；格座標與倉庫頁右半相同）
                q2 = stack_qty(i, want)
                if q2 != qty_i or (want_count is not None and q2 != want_count):
                    return _fail(EXIT_VERIFY, f'{role}「{want}」第 {i + 1} 格疊數 {q2}（預期 {want_count if want_count is not None else qty_i}），不存', 'bag-store-qty')
            rc = open_depot(depot)
            if rc:
                return rc
            if _dclick_move(i, want, False):             # 雙擊存入（未實機）：成功時已切回背包頁且該格已空
                stored += 1
                LAST['stored'] = stored
                if keep_ok or not all_copies:
                    return 0
                continue
            if DCLICK:                                   # 雙擊失敗可能已切回背包頁 → 回倉庫頁（open_depot 已在該頁時不動）再走彈窗
                rc = open_depot(depot)
                if rc:
                    return rc
            rc = _store_via_popup(i, want)
            if rc:
                return rc
            if keep_ok:
                return 0
            def gone(i=i):
                occ = slot_occupancy()
                return (not occ[i]) if occ else find_item(want) is None
            if not _wait(gone, 4.0):                         # 同上：背包頁更新有延遲，輪詢到那格變空
                LAST['stored'] = stored
                try:
                    uikit.snap(f'bag-store-verify-{role}')        # 2026-10-16 p1 存不進去根因不明：留一張現場截圖
                except Exception:                                 # noqa: BLE001
                    pass
                return _fail(EXIT_VERIFY, f'存入後背包「{want}」格數沒減少（倉庫滿？已存 {stored} 個）', 'bag-store-verify')
            stored += 1
            LAST['stored'] = stored
            if not all_copies:
                break
    return 0


def depot_many(op: str, roles, want: str, depot: str = 'public', kind: str = 'consumable', skip_missing: bool = False, all_copies: bool = False) -> tuple:
    """多人倉庫存 / 取同一樣道具（2026-10-12 批次化）：背包面板只開一次（外層 Session；depot_store / depot_take 內的 Session 巢狀時不重開、不關），
    逐人左欄頭像切換。op = 'store' / 'take'。skip_missing：該人沒有（92）就略過。all_copies：store 時同名多格全存。
    → (rc, {角色: rc})；每人存了幾格在 LAST['stored_by']；某人其他失敗立即停"""
    out, stored = {}, {}
    with Session() as s:
        if s.rc:
            return s.rc, out
        for r in roles:
            rc = depot_store(r, want, depot, all_copies=all_copies) if op == 'store' else depot_take(r, want, depot, kind)
            out[r] = rc
            if op == 'store':
                stored[r] = LAST.get('stored', 0)
            if rc == EXIT_ITEM and skip_missing:
                log(f'{r} 沒有「{want}」，略過')
                continue
            if rc:
                LAST['stored_by'] = stored
                return rc, out
    LAST['stored_by'] = stored
    return 0, out


def depot_store_items(roles, items, skip_missing: bool = True) -> tuple:
    """多人存多樣道具（2026-10-15，新角色開局 newchar.py 用）：背包面板只開一次，逐人切頭像、該人的道具一次存完
    （公共的先存、個人的後存 → 倉庫子分頁每人最多切 2 次）。items = [(名稱, 'public' | 'personal')]。
    skip_missing：該人沒有（92 = 已存過 / 沒拿到）就略過。動作後驗證失敗（95）等 2 秒重存一次（rebirth_pets 二轉 DKBO4 重跑才過的同一處理；
    重存回 92 = 第一次其實存進去了）。→ (rc, {角色: {名稱: rc}})；某人其他失敗立即停"""
    out: dict = {}
    order = sorted(items, key=lambda t: t[1] != 'public')
    with Session() as s:
        if s.rc:
            return s.rc, out
        for r in roles:
            res = out.setdefault(r, {})
            for nm, dep in order:
                rc = depot_store(r, nm, dep)
                if rc == EXIT_VERIFY:
                    uikit.sleep(2)
                    rc = depot_store(r, nm, dep)
                    if rc == EXIT_ITEM:
                        rc = 0
                res[nm] = rc
                if rc == EXIT_ITEM and skip_missing:
                    log(f'{r} 沒有「{nm}」，略過')
                    continue
                if rc:
                    return rc, out
    return 0, out


# ---- CLI ----
def _roles(arg: str):
    """'all' / 'DKBO' / 'DKBO2,DKBO3'（逗號 = 多人）→ 角色清單；任一不認得 → None"""
    if str(arg).lower() == 'all':
        return [charstate.display(c) for c in charstate.chars()]
    out = []
    for t in str(arg).split(','):
        hit = charstate.norm_char(t.strip())
        if not hit:
            return None
        out.append(charstate.display(hit))
    return out or None


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
    p = sub.add_parser('weapon'); p.add_argument('role')
    p = sub.add_parser('find'); p.add_argument('role'); p.add_argument('names', nargs='+')
    p = sub.add_parser('list'); p.add_argument('role')
    p = sub.add_parser('purge'); p.add_argument('role'); p.add_argument('--names', required=True); p.add_argument('--dry-run', action='store_true')
    p = sub.add_parser('use'); p.add_argument('role'); p.add_argument('name')
    p.add_argument('--no-reopen', action='store_true', help='吃 buff 道具後不開回原地遇敵（預設開回；跑任務時用）')
    p = sub.add_parser('wear'); p.add_argument('role'); p.add_argument('names', nargs='+')
    p.add_argument('--strict', action='store_true', help='背包沒有某件就失敗（92）；預設略過（已穿上）')
    p = sub.add_parser('store-items'); p.add_argument('role')
    p.add_argument('--public', default='', help='存公共倉庫的道具（逗號分隔）'); p.add_argument('--personal', default='', help='存個人倉庫的道具（逗號分隔）')
    p.add_argument('--strict', action='store_true', help='某人沒有某道具就失敗（92）；預設略過')
    p = sub.add_parser('drop-spare-bow'); p.add_argument('role'); p.add_argument('--bow', default='精靈王之弓')
    p = sub.add_parser('swap-weapon'); p.add_argument('role'); p.add_argument('--keep-old', action='store_true'); p.add_argument('--bow', default='精靈王之弓')
    for n in ('take', 'store'):
        p = sub.add_parser(n); p.add_argument('role'); p.add_argument('name'); p.add_argument('--depot', default='public', choices=['public', 'personal'])
        p.add_argument('--kind', default='consumable', choices=['consumable', 'equip'])
        p.add_argument('--skip-missing', action='store_true', help='多人（all / 逗號）時沒有該道具的人略過')
        p.add_argument('--all-copies', action='store_true', help='store：同名多格（不疊加）全部存')
        p.add_argument('--quiet', action='store_true', help='先關原地遇敵並等戰鬥結束（掛機快戰中浮字 / 戰鬥演出會吃掉點擊，2026-10-16 p1 / p2 倉庫存取失敗），做完開回（--no-reopen 不開回）')
        p.add_argument('--no-reopen', action='store_true', help='--quiet 時做完不開回原地遇敵')
    p = sub.add_parser('drop'); p.add_argument('role'); p.add_argument('name'); p.add_argument('--confirm-name', required=True); p.add_argument('--allow-protected', action='store_true', help='允許丟保護名單道具（例 背包多拿的精靈王之弓；武器格穿著的不在背包格，不受影響）')
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
    if a.cmd == 'weapon':
        rc, d = weapons(roles)
        return _out(rc, {'weapons': d})
    if a.cmd == 'find':
        rc, d = find_items(r, a.names)
        return _out(rc, {'slots': d})
    if a.cmd == 'list':
        rc, d = list_all(roles)
        return _out(rc, {'bags': d})
    if a.cmd == 'purge':
        names = [n.strip() for n in a.names.replace('，', ',').split(',') if n.strip()]
        rc, d = purge(roles, names, a.dry_run)
        return _out(rc, {'purge': d, 'dry_run': a.dry_run})
    if a.cmd == 'use':
        if buff_kind(a.name):                          # 2倍智慧果 / 龍王：關遇敵等戰鬥結束 → 用 buff 剩餘時間判斷吃到沒（eatbuff.py）
            import eatbuff
            rc, info = eatbuff.eat_have(r, a.name, reopen=not a.no_reopen)
            return _out(rc, info)
        return _out(use_item(r, a.name, verify_buff=True), {})
    if a.cmd == 'wear':
        rc, d = wear_many(roles, a.names, not a.strict)
        return _out(rc, {'wear': d})
    if a.cmd == 'store-items':
        sp = lambda s: [n.strip() for n in s.replace('，', ',').split(',') if n.strip()]   # noqa: E731
        items = [(n, 'public') for n in sp(a.public)] + [(n, 'personal') for n in sp(a.personal)]
        if not items:
            print('bag：store-items 要給 --public 或 --personal', file=sys.stderr)
            return _out(uikit.EXIT_USAGE, {})
        rc, d = depot_store_items(roles, items, not a.strict)
        return _out(rc, {'stored': d})
    if a.cmd == 'drop-spare-bow':
        return _out(drop_spare_bow(r, a.bow), {})
    if a.cmd == 'swap-weapon':
        return _out(swap_weapon(r, a.bow, a.keep_old), {})
    if a.cmd in ('take', 'store') and getattr(a, 'quiet', False):
        import heal
        try:
            heal.encounter_off_wait()
            return _depot_cli(a, roles, r)
        finally:
            if not getattr(a, 'no_reopen', False):
                try:
                    heal.set_encounter(True)
                except RuntimeError as e:
                    log(f'開回遇敵失敗：{e}')
    return _depot_cli(a, roles, r)


def _depot_cli(a, roles, r) -> int:
    if a.cmd in ('take', 'store') and len(roles) > 1:
        rc, d = depot_many(a.cmd, roles, a.name, a.depot, a.kind, a.skip_missing, a.all_copies)
        return _out(rc, {'roles': d})
    if a.cmd == 'take':
        return _out(depot_take(r, a.name, a.depot, a.kind), {})
    if a.cmd == 'store':
        return _out(depot_store(r, a.name, a.depot, all_copies=a.all_copies), {})
    return _out(drop_item(r, a.name, a.confirm_name, allow_protected=a.allow_protected), {})


if __name__ == '__main__':
    sys.exit(main())
