#!/usr/bin/env python3
"""便利店 / NPC 商店共用動作（從 buywendy.py 抽出，2026-10-17；buywendy 改 import、行為不變；daily.py 也用）。只用標準函式庫。

內容：
  純函式   parse_coin / coin_delta_ok（buywendy 沿用）、title_vote / title_is（商品標題**逐倍率各自比對該店商品清單投票**，2026-10-17 第二輪：
           舊版各倍率 join 成一串；p1 樣本 11 間店 132 張 → 主讀法 130 對、備援補讀後 132 對、0 誤認）、title_match（字串模糊比對，舊介面 / 無清單時）、
           visible_candidates（清單定位候選列）、qty_digit_xy（數字鍵盤鍵位）
  座標     商店面板固定座標（ui/shop.md、notes/daily-probe.md M11～M13；截圖 1440×830、鏡頭最左）
  動作     shop_open（✕ 紅圓像素）、read_title（回 OCR 原始行；主讀法投不出就 TITLE_FALLBACK 補讀；全部帶 -Small 1 = 實機取像同截圖，2026-10-17 dev-shop-title）、
           select_item（名稱定位 + 捲動；失敗存 ui-log shop-select-fail、log 寫各倍率原字）、set_qty（＋ / － 鈕；數字鍵盤留 set_qty_keypad 備援）、buy_once（購買 → 提示確定）、
           qty_now（讀數量框：**像素字形 numglyph kind 'shop'**，2026-10-17 改；OCR 只當位數相符的備援）、close_shop（✕ 1207,107；買完還疊提示窗再補）
鐵則 3：本模組不讀石幣 / 鑽石（buywendy 自己用 parse_coin 讀石幣；daily 不讀）；只在呼叫端明確要買時才按「購買」。
數量框（2026-10-17 p1 正式跑 227 修）：Windows OCR 讀單獨一個白色「1」各種參數都回空 → 改 numglyph 像素切字 + 樣板（fixtures/num_glyph_tpl.json 'shop'；
  樣本只有 0 1 3 的話其他數字 = 讀不出 None → 呼叫端不買 / 不判買到；OCR 讀到且位數 = 切出字數才採用並學字；讀不出存圖 ui-log/*-shop-qty-unread.png 供人工補樣板）。
  set_qty（2026-10-17 改用數量框兩側「＋ 1112,466 / － 880,466」鈕，不開數字鍵盤）：先讀一次，已是 n 不點；否則 ＋ (n−起點) 次再讀回 == n 才算成功；
    讀得到但不是 n → ＋ / － 補差一次；讀不出（數字沒樣板）→ 不猜，用 － 退回起點、回 False，呼叫端（daily.buy_item）改「每次買 1 個、買 n 次」。
    起點 = 讀到的值，讀不出用 start（開店 / 選商品後預設 1；買完一次後框歸 0 → 傳 0）。n 的每位數字都認得才一次 ＋ 到 n 買（qty_chunks）。
    實機遇到新數字：看 ui-log/*-shop-qty-unread.png 後 `numglyph.py label <圖> shop <值>` 補樣板 → 下次自動走一次買。
  現場讀像素走 gui spixel（numglyph.LIVE_SRC shop = 'shot'，跟截圖同一段縮圖）：dd6f945 用 gui pixel（原生單點）實機 4 次全 None、
  同一畫面截圖讀得出 1 → 227（2026-10-17 19:27 / 19:29，dev-shop-qty2 修）。
  qty_chunks：數量每位數字都有樣板 → 一次 ＋ 到 n 買；有不認得的數字才拆成「每位數字都有樣板」的幾次（樣板只有 1 3 時 7 → 3+3+1、20 → 13+3+3+1），學到新數字自動變少次。
  buy_checked：購買前後各讀一次數量框 → 'bought'（讀到 0）/ 'zeroish'（變成一個認不出的字：ui/shop.md 競技場實機「購買後數量框自動變 0」，
  0 尚無樣板 → 視為買到，**呼叫端要用背包名稱核對把關**）/ 'not_bought'（點陣跟買前完全一樣 = 仍是原數量）/ 'unknown'（其他：不確定，不重買）。
選商品一次到位（2026-10-18 dev-shop-speed；依據 10-13～10-18 actions log 的選商品列位統計）：實測每拖 114 px 約捲 2 列（連拖 n 次 ≈ 2n 列，偏差 ±1，到底夾住；最後一列落視野第 4 列）。
  舊流程逐列：拖一次 → 點列 → 核對 → 不對換鄰近列 → 不夠再拖，第 19 項 / 第 26 項這種要 4～6 次點擊（10～15 秒）。
  新流程 _select_direct：plan_scroll（純函式：index → 最少拖數、到底夾 max_off、預測視野列）→ 連拖（中間只等 DRAG_CHAIN_MS）→ 點預測列一次、title_is 核對中就選到；
  沒中 = 點到的是清單裡另一個商品 → read_idx 讀出它是第幾項 → 反推實際視野偏移（st['off']）→ 直接點正確列，最多 3 次點擊；st['off'] 留給下一項（店內 index 由小到大買，同視野不再拖、往後只補需要的拖數）。
  讀不出是哪個商品 / 預測出視野 / 3 次不中 → 退回舊的逐列鄰近流程 _select_scan（行為不變）。標題核對保留，買錯不可能。
  等待縮短：購買 → 確定後固定等 900 → 250 ms、buy_checked 改輪詢數量框點陣變了就繼續（最多約 3 秒；沒變才判 not_bought）；close_shop 點 ✕ 後輪詢紅圓消失（原固定 500 ms）。
  **未實機**：捲動偏差 ±1 是 log 統計值；DRAG_CHAIN_MS（連拖間隔 1.2 s，原 1.5 s）的慣性未量；輪詢的實機節奏待下次每日任務 fish 段看 log。
選商品（2026-10-17 227 修）：呼叫端（dailyplan.store_route / daily.buy_at）店內依清單 index 由小到大買；select_item 目標在視野上方時 scroll_top 歸零再找。
**未實機**（select_item / set_qty 的座標取自 daily-probe 探路量測，2026-10-17；shop_open / 購買 / 確定 = 既有實測值）。
"""
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import dailyplan  # noqa: E402  （vote_lines / norm：標題逐倍率投票）
import numglyph  # noqa: E402  （數量框像素字形）
import uikit  # noqa: E402

# ---- 座標（截圖 1440×830）----
SHOP_BTN = (948, 461)                            # NPC 對話框「道具商店」（競技場 / 1009 實測）
SHOP_CLOSE = (1207, 107)                         # 便利店右上 ✕（紅圓 190,74,49）
BUY_BTN, CONFIRM_BTN = (995, 592), (615, 557)    # 購買 / 提示「確定」（同 shopbuy）
COIN_BOX = (285, 8, 130, 30)                     # 頂端資源列石幣（buywendy 專用；daily 不讀）
TITLE_BOX = (870, 180, 254, 54)                  # 右側標題（選中的商品名；紅底黃字 255,255,106，字 x 889～1104 × y 194～217，9 字店名都容得下）
# -Small 1（2026-10-17 dev-shop-title 修 227）：實機 ocr 先縮成 gui shot 同一張 1440 縮圖再裁 = 跟 132 張樣本（-Image 1440，-Small 無作用）同一種像素。
# 根因：參數是用 1440 截圖調的，實機從原生 2880 取像時長名字（卡魯它那產海藻 7 字）各倍率常只讀到「藻」→ 投不出 → 227；
# 用使用者原生截圖重建 2880 畫面離線量：主讀法 不帶 0/5 票、帶 2/5 票；備援 1 不帶 0、帶 4/5；備援 2 不帶 1/5、帶 5/5（同 daily POP_NAME_OPTS、ocr.ps1 檔頭）
TITLE_OPTS = ('-Zooms', '2,3,4,5,6', '-Dark', '0', '-Small', '1')   # 不二值化、5 倍率**逐倍率各自比對該店商品清單投票**（title_vote；p1 2026-10-17 132 張 130 對 0 誤認，2 張全倍率讀空 → 備援）
TITLE_FALLBACK = (((880, 185, 230, 45), ('-Zooms', '2,3,4,5,6', '-Dark', '0', '-Small', '1')),   # 主讀法投不出名字才依序補讀（倍率鍵加前綴、各自投票）
                  ((880, 185, 230, 45), ('-Zooms', '2,3,4,5,6', '-Light', '92', '-Small', '1')))
QTY_XY = (995, 465)                              # 數量框：點它跳出數字鍵盤（備援 set_qty_keypad 用）
QTY_MINUS, QTY_PLUS = (880, 466), (1112, 466)    # 數量框兩側綠色「－」「＋」圓鈕（ui/shop.md 競技場實測、daily-probe M13 同版面）
PLUS_GAP_MS, PLUS_BATCH = 150, 25                # ＋ / － 每下間隔（同鍵盤節奏）/ 每個 seq 最多連點幾下
QTY_BOX = numglyph.SHOP_QTY_BOX                  # (968, 450, 56, 32) 數量白字 bbox 989～1002 × 455～477（numglyph kind 'shop'）
KEY_CLEAR, KEY_ENTER = (910, 455), (910, 572)    # 鍵盤 ✕（清除）/ ↵（確定）
KEYPAD = {'1': (490, 333), '2': (615, 333), '3': (743, 333), '0': (863, 333),
          '4': (490, 455), '5': (615, 455), '6': (740, 455),
          '7': (490, 572), '8': (615, 572), '9': (740, 572)}
# 清單：兩欄卡片（先左後右），第 1 列卡中心 y=214、列距 114、可見 4 列 + 半列；拖 114 px ≈ 捲 224 px（約 2 列，有慣性）
COL_X = (404, 671)
ROW_Y0, ROW_PITCH, VIEW_ROWS = 214, 114, 5
DRAG_UP = (540, 560, 540, 446)                   # 往上拖 114 px = 清單往下捲約 2 列
DRAG_DOWN = (540, 446, 540, 560)                 # 往回拖（捲到頂用）
DRAG_SETTLE_MS = 1500                            # 慣性停下後才讀（實測 ≥1.2 s）
ROWS_PER_DRAG = 2
DRAG_CHAIN_MS = 1200                             # 連拖時前幾次拖完等多久再拖下一次（最後一次仍等 DRAG_SETTLE_MS）；只縮 0.3 s、**慣性是否跟 1.5 s 一致未實機量**（落點偏差有標題核對 + 讀名反推偏移兜底）
CLOSE_POLL_MAX = 4                               # close_shop 每次點 ✕ 後輪詢面板是否關掉的次數（間隔 0.15 秒）
BUY_POLL_MAX = 10                                # buy_checked 買後輪詢數量框最多幾次（每次間隔 0.3 秒 + 讀框）
CONFIRM_WAIT_MS = 250                            # 按「確定」後只等這麼久，之後由 buy_checked 輪詢數量框（買完會變 0 = 特徵出現就繼續），不再固定等 900
SELECT_WAIT_MS = 450                             # 點商品卡後等標題換好再讀


# ---- 純函式 ----
def parse_coin(text) -> int | None:
    """「150,000」（OCR 可能夾空白 / 句點 / 多倍率重複）→ 150000；讀不到 None。多倍率串接（-Zooms）會把同一串數字重複 2～3 次 → 整段等分重複只取一份"""
    t = re.sub(r'[\s,.，。]', '', str(text or ''))
    if not t.isdigit():
        t = ''.join(re.findall(r'\d+', t))
    for n in (4, 3, 2):
        if t and len(t) % n == 0 and len(t) // n >= 3 and t[:len(t) // n] * n == t:
            t = t[:len(t) // n]
            break
    return int(t) if t else None


def coin_delta_ok(before, after, price: int = 500) -> bool | None:
    """石幣前後差剛好 price → True；差不是 price → False；任一讀不到 → None（呼叫端改看背包有沒有道具）"""
    if before is None or after is None:
        return None
    return before - after == price


def _norm(t) -> str:
    return re.sub(r'\s+', '', str(t or ''))


def title_match(text, want: str, cutoff: float = 0.8) -> bool:
    """商店右側標題 OCR 是不是 want：去空白後完全包含 / 相等，或字元序列相似度 ≥ cutoff（OCR 掉字 / 部首拆字容錯）。
    同族名稱只差數字（合成爪 7 / 合成爪 3）要數字都一樣才算（日常材料名一般無數字，保險）"""
    a, b = _norm(text), _norm(want)
    if not a or not b:
        return False
    if a == b:
        return True
    da, db = re.findall(r'\d+', a), re.findall(r'\d+', b)
    if db and da and da != db:
        return False
    if b in a:
        return True
    import difflib
    return difflib.SequenceMatcher(None, a, b).ratio() >= cutoff


def title_vote(lines, order) -> dict:
    """標題 OCR 原始行（uikit.ocr_lines，多倍率每行帶 zoom）→ **逐倍率各自比對 order（該店商品清單）投票**（dailyplan.vote_lines，同上一輪成品名讀法）。
    舊讀法把各倍率 ''.join 成一串（「香味濃厚的油香味濃厚的油」/ 一個倍率掉字就整串不像）。
    多倍率投給不同商品（例：「的青椒」被 snap 成「大的青椒」1 票 vs「普通的青椒」4 票）→ 多數決：最高票 ≥ 2 且多於其他票總和才收；平手 / 只有 1 票對 1 票 → None。
    回 dailyplan.vote_lines 的 dict（name / votes / conflict / sure / texts）"""
    v = dailyplan.vote_lines(lines, order)
    if v['name'] is None and v['votes']:
        (top, n), *rest = sorted(v['votes'].items(), key=lambda kv: -kv[1])
        if n >= 2 and n > sum(c for _, c in rest):
            v = dict(v, name=top)
    return v


def title_is(read, want: str, order=None) -> bool:
    """標題讀值是不是 want：read = ocr_lines 原始行（逐倍率投票，order 給該店清單；沒給就只比 want）或字串（舊介面 → title_match）"""
    if read is None or isinstance(read, str):
        return title_match(read, want)
    return title_vote(read, list(order or [want]))['name'] == dailyplan.norm(want)


def card_xy(row_pos: int, col: int) -> tuple:
    """目前視野第 row_pos 列（0 起算）、第 col 欄（0 / 1）的卡片中心"""
    return COL_X[col], ROW_Y0 + ROW_PITCH * row_pos


def visible_candidates(idx: int, n_drags: int, rows: int = VIEW_ROWS) -> list:
    """商品在清單第 idx 項（0 起算、2 欄先左後右）；已往下拖 n_drags 次（每次約 ROWS_PER_DRAG 列，有慣性 / 到底夾住）
    → 目前視野裡可能的列位置 [row_pos, ...]（預測列優先）；視野外 → []。
    預測 = idx//2 − n_drags×ROWS_PER_DRAG。實際偏移 ≤ 預測（到底夾住）→ 實際列位置 ≥ 預測；慣性多滑約 1 列 → 實際列位置可能 = 預測 − 1。
    所以只試 {pred, pred+1, pred−1, pred+2} ∩ [0, rows)；預測列離視野太遠（pred−1 ≥ rows）→ [] = 呼叫端再拖一次"""
    pred = idx // 2 - n_drags * ROWS_PER_DRAG
    out = []
    for r in (pred, pred + 1, pred - 1, pred + 2):
        if 0 <= r < rows and r not in out:
            out.append(r)
    return out


def max_off(n_items: int) -> int:
    """清單最大捲動偏移（列）：總列數 − 可見 5 列（實機：拖到底最後一列落在視野第 4 列，2026-10-18 量 10-13～10-18 log）"""
    return max(0, (n_items + 1) // 2 - VIEW_ROWS)


def plan_scroll(idx: int, n_items: int, off: int) -> tuple:
    """商品第 idx 項（0 起算）、目前視野第一列 = off → (要往下拖幾次, 拖完預測偏移, 預測視野列 pos)。
    每次拖 ROWS_PER_DRAG 列、到底夾在 max_off；已在視野內 → 0 次。目標在視野上方（r < off）→ n = 0、pos 為負，呼叫端要先 scroll_top。
    用**最少拖數**讓目標落在視野第 3 / 4 列（實測 log：row 5～14 預測列命中 ≥ 8 成，偏差 ±1 列）"""
    r = idx // 2
    if r - off <= VIEW_ROWS - 1:
        return 0, off, r - off
    n = -(-(r - off - (VIEW_ROWS - 1)) // ROWS_PER_DRAG)
    new_off = min(off + n * ROWS_PER_DRAG, max(max_off(n_items), off))
    return n, new_off, r - new_off


def read_idx(lines, order) -> int | None:
    """標題讀值（OCR 原始行 / 字串）→ 它是 order 的第幾項（0 起算）；讀不出 / 投不出 → None。
    點到錯的卡片時，標題顯示的是**另一個商品** → 知道它的 index = 知道清單實際捲到哪（一次修正偏移，不用逐列試）"""
    if lines is None:
        return None
    if isinstance(lines, str):
        for i, o in enumerate(order):
            if dailyplan.norm(o) == dailyplan.norm(lines):
                return i
    name = title_vote(lines, list(order))['name']
    if not name:
        return None
    for i, o in enumerate(order):
        if name in (o, dailyplan.norm(o)):
            return i
    return None


def qty_digit_xy(n: int) -> list:
    """要輸入的數量 → 依序點的鍵位 [(x, y)...]（不含清除 / 確定）；n < 0 或超過 3 位 → ValueError"""
    if n < 0 or n > 999:
        raise ValueError(f'數量 {n} 超出 0～999')
    return [KEYPAD[c] for c in str(n)]


def parse_qty(text) -> int | None:
    """數量框 OCR → 整數；讀不到 None。多倍率重複同 parse_coin 處理"""
    return parse_coin(text) if re.search(r'\d', str(text or '')) else None


# ---- 碰遊戲的動作 ----
def shop_open() -> bool:
    """便利店面板：右上 X 紅圓（1207,107）。用 pixel 比紅色（2026-10-17 從 shopbuy._shop_open 抽出，行為相同）"""
    px = uikit.px([SHOP_CLOSE]) or []
    return bool(px) and px[0][0] > 180 and px[0][1] < 100


def read_title(order=None) -> list:
    """右側標題 OCR 原始行（多倍率，呼叫端 title_vote / title_is 逐倍率投票）。主讀法投不出 order 裡的名字 → 依 TITLE_FALLBACK 補讀
    （倍率鍵加前綴 f1-2…，不和主讀法同倍率拼在一起）；order 沒給 = 不補讀"""
    lines = uikit.ocr_lines(TITLE_BOX, *TITLE_OPTS)
    for i, (box, opts) in enumerate(TITLE_FALLBACK if order else (), 1):
        if title_vote(lines, order)['name']:
            break
        lines = lines + [dict(ln, zoom=f'f{i}-{ln.get("zoom")}') for ln in uikit.ocr_lines(box, *opts)]
    return lines


def qty_vote(lines) -> int | None:
    """數量框 OCR 原始行（多倍率）→ **每個倍率各自**取數字，至少 2 個倍率讀到且全部一致才回值；否則 None。
    不把各倍率 join 起來（「1」+「1」會變 11 → 位數湊巧對上就學錯字）"""
    by = {}
    for ln in lines or ():
        by.setdefault(ln.get('zoom'), []).append(str(ln.get('text', '')))
    vals = {''.join(re.findall(r'\d', ''.join(t))) for t in by.values()}
    vals.discard('')
    got = [z for z, t in by.items() if re.search(r'\d', ''.join(t))]
    return int(vals.pop()) if len(vals) == 1 and len(got) >= 2 else None


def _qty_ocr() -> int | None:
    """OCR 備援（單一數字常讀空；numglyph 只在位數 = 像素字數時採用並學字）"""
    return qty_vote(uikit.ocr_lines(QTY_BOX, '-Zooms', '2,3,4', '-Dark', '0'))


def qty_now(log=None) -> int | None:
    """讀目前數量框（開店 / 選商品後預設 1；購買後歸 0）。像素字形為主（numglyph 'shop'），每個字都認得才算；讀不出 None（不猜）並存圖供補樣板"""
    r = numglyph.read_number('shop', QTY_BOX, ocr_reads=(_qty_ocr,), sleep_fn=uikit.sleep, tries=2, log=log)
    if r['value'] is None and r['n'] > 0:
        uikit.snap('shop-qty-unread')                     # 有字但認不出 → 存圖（人工看了補進 fixtures/num_glyph_tpl.json）
    return r['value']


def known_digits() -> set:
    """數量框目前認得的數字（種子 + 學到的 'shop' 樣板）"""
    return {ch for ch, vs in (numglyph.load_tpl().get('shop') or {}).items() if ch.isdigit() and vs}


def qty_chunks(q: int, known=None) -> list | None:
    """q 拆成幾次購買，每次的數量每一位都在 known（認得的數字）裡、≤ 999（鍵盤 3 位）；貪婪取最大。拆不出（沒有 1）→ None"""
    known = known_digits() if known is None else set(known)
    out, rem = [], int(q)
    while rem > 0:
        c = next((c for c in range(min(rem, 999), 0, -1) if set(str(c)) <= known), None)
        if c is None:
            return None
        out.append(c)
        rem -= c
    return out


def buy_verdict(before: dict, after: dict, n: int) -> str:
    """購買前後的數量框讀值（numglyph.read_box 結果，含 rows）→ 'bought' | 'zeroish' | 'not_bought' | 'unknown'（純函式，見檔頭）"""
    if after.get('value') == 0:
        return 'bought'
    if after.get('rows') is not None and after.get('rows') == before.get('rows') and before.get('value') == n:
        return 'not_bought'
    if after.get('value') is None and after.get('n') == 1 and before.get('value') == n and after.get('rows') != before.get('rows'):
        return 'zeroish'
    return 'unknown'


def buy_checked(n: int, log=None) -> str:
    """數量框已是 n → 讀一次 → 購買 → 確定 → 再讀（字還沒出來就等，最多約 2 秒）→ buy_verdict。認不出的字存圖供補樣板"""
    before = numglyph.read_box('shop', QTY_BOX)
    buy_once()
    after = numglyph.read_box('shop', QTY_BOX)
    for _ in range(BUY_POLL_MAX):                         # 輪詢：點陣跟買前不同（框變 0 / 變別的字）= 買完了就繼續；一直沒變最多等約 BUY_POLL_MAX×0.3 秒再判 not_bought
        if after['n'] >= 1 and after.get('rows') != before.get('rows'):
            uikit.sleep(0.2)                              # 剛變的那一幀可能是淡入中 → 穩 0.2 秒再讀一次當最終值
            after = numglyph.read_box('shop', QTY_BOX)
            break
        uikit.sleep(0.3)
        after = numglyph.read_box('shop', QTY_BOX)
    v = buy_verdict(before, after, n)
    if v in ('zeroish', 'unknown') and after['n'] > 0 and after['value'] is None:
        uikit.snap('shop-qty-unread')                     # 人工看了 → numglyph.py label <圖> shop 0
    if log:
        log(f'shopkit 購買 {n}：數量框 買前 {before.get("value")!r} → 買後 {after.get("value")!r}（{after.get("n")} 字）= {v}')
    return v


def scroll_top(rows: int) -> None:
    """清單捲到頂：往回拖足夠次數（每次約 2 列）"""
    for _ in range(max(1, (rows + 1) // ROWS_PER_DRAG + 1)):
        uikit.gui('seq', 'drag {} {} {} {}; wait {}'.format(*DRAG_DOWN, DRAG_SETTLE_MS), note='shopkit 清單捲回頂端')


def select_item(want: str, order: list, state: dict | None = None, reader=None, log=None) -> bool:
    """在商店清單選 want（order = 該店商品順序 = 遊戲清單順序，2 欄先左後右；來自 npc-shops.md）。
    靠標題名稱核對定位（不算位移；標題逐倍率比對本店清單投票 title_is）：預測列優先、不對再試鄰近列、視野外就往下拖一次；最多拖 len(order)//4+2 次。
    state = {'drags': n} 跟蹤已拖次數（呼叫端開店時給 {'drags': 0}）；回傳 True = 標題已是 want（已選中）。
    開店時第 1 項自動選中；清單 ≤ 8 項（≤4 列）不用捲。reader 可換（測試）。
    目標在目前視野上方（之前往下捲過頭）→ scroll_top 往回拖到頂、drags 歸 0 再找（只歸零重找一次）；呼叫端（daily.buy_at）另依清單 index 由小到大買，正常不會觸發
    回 False 前（2026-10-17 dev-shop-title）：uikit.snap('shop-select-fail') 存現場圖、log（呼叫端給，例 daily.event）寫最後幾次標題各倍率 OCR 原字"""
    reader = reader or (lambda: read_title(order))
    st = state if state is not None else {'drags': 0}
    if want not in order:
        return False
    reads = []                                               # (視野列, 各倍率原字)：失敗時寫 log
    ok = _select_direct(want, order, st, reader, reads) or _select_scan(want, order, st, reader, reads)
    if not ok:
        shot = uikit.snap('shop-select-fail')
        if log:
            tail = '；'.join(f'列{r}:{t}' for r, t in reads[-4:]) or '（沒讀到）'
            log(f'shopkit 選不到「{want}」（第 {order.index(want) + 1} 項，讀 {len(reads)} 次），最後標題各倍率 {tail}；現場圖 {shot}')
    return ok


def _drag_down(n: int, st: dict) -> None:
    """往下拖 n 次（st['drags'] 累計）；中間只等 DRAG_CHAIN_MS（下一拖開始前慣性不必停完），最後一次等 DRAG_SETTLE_MS 才讀"""
    for k in range(n):
        wait = DRAG_SETTLE_MS if k == n - 1 else DRAG_CHAIN_MS
        uikit.gui('seq', 'drag {} {} {} {}; wait {}'.format(*DRAG_UP, wait), note='shopkit 清單往下捲')
        st['drags'] += 1


def _select_direct(want: str, order: list, st: dict, reader, reads: list) -> bool:
    """一次到位（2026-10-18）：依商品 index 算要拖幾次（plan_scroll，到底夾住）→ 連拖 → 點預測列一次、標題核對中就選到。
    沒中：點到的是清單另一個商品 → read_idx 知道它的 index → 實際偏移 = 該 idx 的列 − 被點列，直接點正確列（最多 3 次點擊）。
    st['off'] = 目前視野第一列（已知時）；沒有就用 drags×ROWS_PER_DRAG。標題核對沿用 title_is（避免買錯）。
    讀不出是哪個商品 / 預測出視野 / 3 次不中 → 回 False，呼叫端退回逐列鄰近流程（_select_scan）"""
    idx = order.index(want)
    r, col = idx // 2, idx % 2
    off = st['off'] if st.get('off') is not None else st['drags'] * ROWS_PER_DRAG
    if r < off:                                              # 目標在視野上方 → 先回頂（依已知偏移少拖幾次、多 1 次保底）
        scroll_top(max(1, off))
        st['drags'], st['off'], off = 0, 0, 0
    n, off, _ = plan_scroll(idx, len(order), off)
    _drag_down(n, st)
    st['off'] = off
    for _ in range(3):
        pos = r - off
        if not 0 <= pos < VIEW_ROWS:
            return False
        x, y = card_xy(pos, col)
        uikit.gui('seq', f'click {x} {y}; wait {SELECT_WAIT_MS}', note=f'shopkit 選商品「{want}」（第 {idx + 1} 項，視野列 {pos}）')
        lines = reader()
        if title_is(lines, want, order):
            st['last_idx'] = idx
            return True
        reads.append((pos, title_vote(lines, order)['texts']))
        got = read_idx(lines, order)
        if got is not None and got == st.get('last_idx') and st.get('last_xy') != (x, y):   # 還是上一個商品的名字：標題可能還沒換 → 等一下重讀再信
            uikit.sleep(0.5)
            lines = reader()
            if title_is(lines, want, order):
                st['last_idx'] = idx
                return True
            got = read_idx(lines, order)
        st['last_xy'] = (x, y)
        if got is None:
            return False
        off = got // 2 - pos                                  # 讀到的商品就在被點的那一列 → 反推實際視野第一列
        if off < 0:
            return False
        st['off'] = off
        if r < off:
            return False
        n, off, _ = plan_scroll(idx, len(order), off)
        _drag_down(n, st)
        st['off'] = off
    return False


def _select_scan(want: str, order: list, st: dict, reader, reads: list) -> bool:
    """select_item 的定位迴圈（每次讀標題的各倍率原字記進 reads）"""
    idx = order.index(want)
    col = idx % 2
    topped = False
    for _ in range(len(order) // (2 * ROWS_PER_DRAG) + 3):
        for r in visible_candidates(idx, st['drags']):
            x, y = card_xy(r, col)
            uikit.gui('seq', f'click {x} {y}; wait 450', note=f'shopkit 選商品「{want}」（第 {idx + 1} 項，視野列 {r}）')
            lines = reader()
            if title_is(lines, want, order):
                return True
            reads.append((r, title_vote(lines, order)['texts']))
        if idx // 2 - st['drags'] * ROWS_PER_DRAG < 0:        # 目標在視野上方（只會往下拖、之前捲過頭）→ 捲回頂端歸零再找（2026-10-17 227 修）
            scroll_top(len(order) // 2 + 1)
            st['drags'] = 0
            if topped:                                       # 已歸零重找過仍不中 → 放棄，免得無限來回
                break
            topped = True
            continue
        if st['drags'] * ROWS_PER_DRAG > idx // 2 + 2:
            break
        uikit.gui('seq', 'drag {} {} {} {}; wait {}'.format(*DRAG_UP, DRAG_SETTLE_MS), note='shopkit 清單往下捲')
        st['drags'] += 1
    return False


def _step_clicks(xy, k: int) -> None:
    """連點 ＋ / － 共 k 下（每個 seq 最多 PLUS_BATCH 下，每下間隔 PLUS_GAP_MS）"""
    while k > 0:
        m = min(k, PLUS_BATCH)
        uikit.gui('seq', '; '.join([f'click {xy[0]} {xy[1]}; wait {PLUS_GAP_MS}'] * m) + '; wait 300',
                  note=f'shopkit 數量 {"＋" if xy == QTY_PLUS else "－"} ×{m}')
        k -= m


def set_qty(n: int, reader=None, start: int | None = None) -> bool:
    """數量用「＋ / －」鈕調到 n（2026-10-17 改，不開數字鍵盤；鍵盤流程留在 set_qty_keypad 備援）。
    起點 = 先讀數量框；讀不出才用呼叫端給的 start（開店 / 選商品後預設 1；買完一次後框歸 0 → 呼叫端傳 0；不給且讀不出 = 不猜、False）。
    已是 n → 不點。否則 ＋ (n−起點) 次（負數點 －）→ 讀回：== n 成功；讀得到但不是 n → 用 ＋ / － 補差一次再讀；
    讀不出（數字沒樣板）→ 不猜：用 － / ＋ 退回起點（框回到 start）並回 False，呼叫端改「每次買 1 個」。"""
    reader = reader or qty_now
    cur = reader()
    if cur == n:
        return True
    base = cur if cur is not None else start
    if base is None or n < 0:
        return False
    d = n - base
    if d:
        _step_clicks(QTY_PLUS if d > 0 else QTY_MINUS, abs(d))
    got = reader()
    if got == n:
        return True
    if got is None:                                    # 讀不出：退回起點，不猜
        if d:
            _step_clicks(QTY_MINUS if d > 0 else QTY_PLUS, abs(d))
        return False
    d2 = n - got                                       # 讀得到但差了 → 補差一次
    _step_clicks(QTY_PLUS if d2 > 0 else QTY_MINUS, abs(d2))
    return reader() == n


def set_qty_keypad(n: int, reader=None) -> bool:
    """備援（預設不用）：先讀數量框，已是 n 不開鍵盤；否則點數量框 → 數字鍵盤：清除 → 逐位按數字 → ↵；讀回 == n 才算成功"""
    reader = reader or qty_now
    if reader() == n:
        return True
    keys = qty_digit_xy(n)
    seq = [f'click {QTY_XY[0]} {QTY_XY[1]}; wait 400', f'click {KEY_CLEAR[0]} {KEY_CLEAR[1]}; wait 150']
    seq += [f'click {x} {y}; wait 150' for x, y in keys]
    seq.append(f'click {KEY_ENTER[0]} {KEY_ENTER[1]}; wait 400')
    uikit.gui('seq', '; '.join(seq), note=f'shopkit 數量輸入（鍵盤）{n}')
    return reader() == n


def buy_once() -> None:
    """按「購買」→ 提示「確定」（同 shopbuy；呼叫端已確認商品 / 數量）"""
    uikit.gui('seq', f'click {BUY_BTN[0]} {BUY_BTN[1]}; wait 700; click {CONFIRM_BTN[0]} {CONFIRM_BTN[1]}; wait {CONFIRM_WAIT_MS}', note='shopkit 購買 → 確定')


def close_shop(tries: int = 3) -> bool:
    """點 ✕ 關便利店（絕不點空白處）；買完還疊提示窗 → 面板還在就再點（最多 tries 次）。回 True = 已關"""
    for _ in range(tries):
        if not shop_open():
            return True
        uikit.gui('seq', f'click {SHOP_CLOSE[0]} {SHOP_CLOSE[1]}; wait 150', note='shopkit 關便利店（✕）')
        for _ in range(CLOSE_POLL_MAX):                   # ✕ 紅圓消失 = 已關就繼續（不固定等 0.5 s）；沒消失才再點
            if not shop_open():
                return True
            uikit.sleep(0.15)
    return not shop_open()
