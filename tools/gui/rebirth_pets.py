#!/usr/bin/env python3
"""轉生後寵物重整（舊寵物已在轉生前由 rebirth.py 全存個人倉庫）→ DKBO2 抓 N 隻騎寵（預設布拉奇多斯）→ 經公共倉庫分給 5 人 → 設騎乘 → 取出戰寵（預設朵拉比斯）設出戰
→ 外掛重新鎖定騎寵 / 戰寵。2026-10-11 第一次手動做完（notes/quest-log.md「轉生後寵物重整」），本檔是把它腳本化。只用標準函式庫。

**實機驗證狀態（2026-10-11 寫成時）**：只有離線測試（test_rebirth_pets.py，假 Tools）。寫的當下遊戲被別的 agent 接手掛機，沒能實機跑。
- 寵物存取 / 設狀態 / 認沒名字的新寵物 = pet.py（pet 的新功能也只有離線驗證；store / take 舊功能實機驗證過）。
- 背包 / 公共倉庫道具 = bag.py（另一位 dev 寫的，同樣沒實機驗證）；**拆分誘餌**（拆分鈕 + 數量鍵盤）是本檔自己寫的，座標取自 notes/plan-dino-katan.md 的手動實測。
- **外掛「捉寵設置」與「鎖定騎寵 / 戰寵」是本檔自己寫的**：座標取自 ui/ass.md 與 plan-dino-katan.md 的手動實測，但下拉清單的「讀字找列」範圍
  （CATCH_LIST_FAMILY / CATCH_LIST_PET / LOCK_LIST_* / 各 OCR 框）是**猜的**，第一次實跑要看 snap 修正；所有點擊前都先 OCR 驗證（讀不到就停、不盲點），
  下拉選項用 ocr.ps1 回傳的文字座標點（不是固定列距）。這些框沒量過 → 標「待實機量」，見 ui/ass.md。
**三轉實跑（2026-10-13 21:47～22:19）寫回的修正（只有離線測試）**：pet_take_lv1_scan 先用原格號（實機存回後格號不變）、72 才試遞補格號；
鎖定騎寵成長字串漏段比對（growth_partial，同角色別隻吻合 = 歧義停）；系別清單雷龍系被上緣切半 → plain_row 寬鬆比對 + family_below_action
（大象系 y - 42 位置備援、往回捲最多 2 次、不震盪）；選不到時收下拉 + ass_close_hard 保險關面板；catchbuy 可抓捕數 0 讀不到 → parse_count_zero。

**2026-10-16 起沒有 store 段**：舊寵物（含騎寵）在 rebirth.py 的 storepets（boss20 後、轉生前）已全存個人倉庫，轉生獎勵寵也在 rebirth cleanup 丟掉（五轉存倉）；
本腳本從空寵物欄開始（preflight → boxes → catch …）。`--store-mount` 保留為無作用參數（印一行提示）；舊的 `--from store` 改從 catch。battle 從個人倉庫取 Lv1 戰寵照舊。

用法（專案根目錄；WSL / Windows 原生指令相同）：
  uv run --no-project python tools/gui/rebirth_pets.py [--trans N] [--mount-species 布拉奇多斯] [--battle-pet 朵拉比斯] [--catcher DKBO2] [--count 5]
        [--family 雷龍系] [--store-mount 瑪斯貝卡] [--from 階段] [--to 階段] [--dry-run] [--no-boxes] [--confirm-buy-catch] [--direct-catch] [--keep-lock] [--no-grind]
    --trans N          剛轉到第 N 轉（開「N轉新手禮盒」；預設 1；下一個 N+1 轉新手禮盒存個人）
    --mount-species    要抓 / 設騎乘 / 鎖定的物種（預設 布拉奇多斯；也是 pet.py 的 MOUNTS 之一）
    --family           外掛捉寵設置的系別（預設依物種：布拉奇多斯 = 雷龍系；其他物種要明講）
    --battle-pet       戰寵（預設 朵拉比斯，從個人倉庫取、設出戰、鎖定）
    --catcher          負責抓的角色（預設 DKBO2；不是當前角色，勾自動抓寵也照抓）
    --count N          共要幾隻（預設 5，每人 1 隻；DKBO 以外 4 人由公共倉庫分）
    --store-mount 名   無作用參數（2026-10-16 起沒有 store 段；給了只印一行提示）
    --from 階段        從這個階段開始（中斷後接著做；進度記在 tools/.cache/rebirth_pets.json）；--to 階段 = 做到該階段（含）就停
    --confirm-buy-catch catch：外掛捉寵設置「+」花石幣買可抓捕數到 count（每個 50,000 石幣；使用者規定騎寵這樣抓，二轉 5 次 = 250,000）。沿用 petquest 的
                       catchbuy.buy_to：不讀石幣；按前讀不到鑽石不按、按後鑽石讀不到 / 有變就停、可抓捕數 +1 才繼續，買到 = count 後走 --direct-catch
                       （不取誘餌、不試抓、直接抓）。不給 = 舊行為（取誘餌）。**紅區（花石幣）：只有使用者明講才加**
    --direct-catch     catch：可抓捕數已買好 = count，不取誘餌、不試抓，直接抓（--confirm-buy-catch 隱含）
    --keep-lock        preflight 不先取消外掛鎖定（遊戲沒擋）
    --no-grind         全部階段完成後不去練功（預設：cleanup 成功、--to 是 cleanup → grind.go 去練功，見下「之後」）
    --dry-run          只印計畫（階段 / 動作 / 退出碼），完全不碰遊戲
  可 import：rebirth_pets.run(trans=1, ..., tools=None) → 退出碼；結果 dict 在 rebirth_pets.LAST

階段：
  preflight   當前角色 = DKBO（不是就 char.ensure）→ team.disband（沒隊伍 = 不點）→ 外掛鎖定騎寵 / 戰寵 5 人先取消 → 讀 5 人寵物欄（舊寵物清單）
  boxes       （bag 95 = 動作後驗證失敗：使用 / 每項存倉各自動重試 1 次，二轉 DKBO4 重跑才過的處理）5 人各：背包找「N轉新手禮盒」→ 使用 → 內容（寵物誘餌 / 離線水晶8H / 2倍智慧果 / 安撫之素）存公共；「N+1轉新手禮盒」禁止存公共 → 存個人（--no-boxes 跳過）
  catch       catcher 從公共取誘餌（拆分只留 1）→ 外掛捉寵設置（系別 → 物種 → 可抓捕數 = 1）→ 勾自動存倉庫 / 自動抓寵 → 等抓完 →
              → pet.reset_soft(catcher) 還原名字（成長字串 → 物種名）→ 確認多 1 隻新寵物、名字 = 物種 → 再留 N-1 個誘餌重複 → 還原名字 → 確認共 N 隻
              名字為主（2026-10-14 晚，離線測試；reset-name 本身實機驗過 8 隻布拉奇多斯）：learn-species（登錄縮圖 / 成長字串）只在還原失敗、
              名字框仍是成長字串時才做（備援）；還原讀到費用字樣（pet 67）→ 103 停手（鐵則 3）；9 / 10 透傳；其他還原失敗 → 記事件、走備援。
              還原前的成長字串記進度檔 data.growths（鎖定下拉備援）。--confirm-buy-catch / --direct-catch 一樣：抓完還原 → 名字驗 → 名字讀不出才縮圖 + learn-species
  distribute  catcher 把 N-1 隻（取最後格）存公共 → 其他 4 人各從公共取 1 隻（pet.py take-many，以名字找卡；名字讀不出的卡才靠成長字串登錄檔）
  ride        5 人把騎乘物種設騎乘（pet.py set-state --allow-mount，以名字找）
  battle      5 人從個人倉庫取戰寵 Lv1（pet.py take-many 目標「名字@1」）→ 設出戰；倉庫同名多隻、卡片等級讀不出（72）→ 對沒拿到的人逐隻取出（--index + 取後驗 Lv1），
              不是 Lv1 就存回個人倉庫換下一隻（Tools.pet_take_lv1_scan；二轉 DKBO2 手動 --index 的自動化）
  lock        5 人外掛：鎖定騎寵 = 騎乘寵（騎寵已還原名字 → ident ('name', 物種)；下拉找不到物種名才退回 catch 記的成長字串比對 growth / growth_partial，
              **待實機確認**：改名後下拉是否顯示物種名是推測；騎寵仍沒名字 → 照舊成長字串）、鎖定戰寵 = 戰寵（名字）→ 兩項都勾
  cleanup     catcher 背包多餘誘餌存回公共 → 確認當前 DKBO、遇敵關 → 讀最後寵物欄 → 寫 notes/quest-log.md 摘要
  之後        （2026-10-15，--no-grind 關）去練功 = grind.go(trans_hint=--trans)：背包讀隊長轉數 → 依等級選點傳送 → 外掛 → 遇敵 → EXP 確認 →
              未滿地雷區背景起 `grind.py follow --no-heal --trans N`（跟著等級換點，到地雷區自己結束）。rebirth → rebirth_pets → 練功連成一條。
              失敗回 grind 的退出碼（50～59 / 8 / 9 / 10；info.grind_rc），寵物重整本身已完成（進度檔照記）

退出碼（共用 0 / 1 / 2 / 8 / 9 / 10 見 uikit；其他工具 40～79 / 80～89 rebirth / 90～96 bag；本檔 100～109）：
  100 preflight 失敗（當前角色切不回 DKBO、解散失敗、外掛解鎖失敗、讀寵物欄失敗）
  101 boxes 失敗（背包 / 倉庫操作，info.bag_rc）
  102 保留不用（原 store 段，2026-10-16 拿掉）
  103 catch 失敗（取誘餌 / 外掛設定 / 抓寵逾時 / 新寵物數量不對 / 名字不是該物種 / 物種登錄失敗 / 欄位不夠 / 還原名字讀到費用字樣 pet 67）
  104 distribute 失敗
  105 ride 失敗
  106 battle 失敗（倉庫沒有戰寵、取出 / 出戰失敗）
  107 lock 失敗（OCR 找不到該下拉選項、勾選點了沒變）
  108 cleanup 失敗
  109 參數 / 進度檔不一致（--from 的階段前置沒做、角色名不認得）
驗證視窗（uikit 回 9）→ 一律回 9 並停手（鐵則 5）；斷線（netwatch halt）→ 10；其他腳本佔用畫面 → 8。

安全：捉寵設置的「+」（買可抓捕數，花石幣）只有 --confirm-buy-catch 才按（catchbuy，前後驗石幣 / 鑽石）；不碰「丟棄不滿足條件的寵物」區塊；
  只點讀字確認過的下拉選項；沒給 --confirm-buy-catch 不花石幣 / 鑽石（誘餌用禮盒送的）。
"""
import argparse
import json
import re
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import clients  # noqa: E402
import uikit  # noqa: E402

SRC = 'rebirth_pets'
ROOT = uikit.ROOT
import logpaths  # noqa: E402
EVENT_LOG = logpaths.p(clients.npath('quest-events.log'))     # 主視窗 = notes/；其他 = notes/clients/<程序名>/
QUEST_LOG = logpaths.p(clients.npath('quest-log.md'))
PROGRESS = logpaths.p(uikit.CACHE / 'rebirth_pets.json')

EXIT_PRE, EXIT_BOX, EXIT_STORE, EXIT_CATCH, EXIT_DIST, EXIT_RIDE, EXIT_BATTLE, EXIT_LOCK, EXIT_CLEAN, EXIT_ARGS = 100, 101, 102, 103, 104, 105, 106, 107, 108, 109

STAGES = ['preflight', 'boxes', 'catch', 'distribute', 'ride', 'battle', 'lock', 'cleanup']
ALL_ROLES = clients.roster()          # 這個視窗（PSA_CLIENT）的名單：主視窗 DKBO、DKBO2～5；PrimalSA2 = DKBO6～10；第 1 個 = 隊長
LEADER = ALL_ROLES[0] if ALL_ROLES else ''
FAMILY_NEIGHBORS = {'鯊魚系': (('犀牛', '牛系'), ('飛天蛙', '飛夭蛙', '蛙系'))}          # 外掛系別清單的上下鄰居（2026-10-12 實機）
FAMILY_BELOW = {'雷龍系': '大象系'}                         # 系別清單中該列正下方的列（該列被清單上緣切掉時用下一列的位置判斷要往回捲）
FAMILY_ROW_H = 42                                          # 系別清單列距（FAMILY_NEIGHBORS 兩列約 70～100）；往回捲後目標列仍讀不到字 → 用下一列 y - 列距點，點完照樣讀欄位驗證
FAMILY_BACK_MAX = 2                                        # 往回捲最多幾次；捲過仍找不到就停（2026-10-13 實機：往回捲 → 往下捲來回震盪 3 輪沒選到）
SPECIES_ORDER = {'鯊魚系': ['克邦凱斯', '加克拉', '加格', '邦恩吉'], '火雞系': ['火雞', '克克洛斯', '霍爾克', '奇寶'], '老虎系': ['貝魯卡', '貝魯伊卡', '格魯西斯']}   # 寵物下拉的列順序（第一列 y=421、列距 42、x=1115）；選中的藍底白字 OCR 讀不到時用位置
FAMILY_OF = {'布拉奇多斯': '雷龍系'}            # 物種 → 外掛捉寵設置的系別（PetData 第 27 組；其他物種用 --family）
BAIT = '寵物誘餌'
BOX_CONTENTS = ['寵物誘餌', '離線水晶', '2倍智慧果', '安撫之素']      # 1轉新手禮盒內容（quest-log 實測）；存公共
CATCH_POLL_S, CATCH_TIMEOUT_S = 120.0, 1200.0              # 輪詢間隔 2 分（2026-10-13：30 秒一次開外掛面板 15 次，面板開著會擋住戰鬥畫面 / 捕捉；5 隻本來就要數分鐘）
EXIT_CATCH_PICK = 14                                       # 捉寵設置：系別 / 物種下拉選不到或讀回對不上（ass 12 / 13 之外；不默默關面板，pet_catch 印出原因）
PICK_RETRY = 3                                             # 物種下拉（不捲動）讀不到目標列時的重試次數：等清單渲染 / 清單空白就再點下拉
LAST: dict = {}

# ---- 外掛座標（ui/ass.md / plan-dino-katan.md 手動實測；2880×1659 截圖座標）----
ASS_TAB = {'general': (850, 212), 'catch': (984, 212), 'battle': (696, 206)}
LOCK_XY = {'騎寵': {'check': (656, 313), 'dd': (1285, 312)}, '戰寵': {'check': (656, 377), 'dd': (1285, 377)}}
CATCH_XY = {'auto': (656, 315), 'store': (820, 315), 'family_dd': (921, 377), 'pet_dd': (1283, 377), 'scroll': ((750, 650), (750, 480))}
# 下面全是「待實機量」的 OCR 框（x, y, w, h）：讀字用，錯了只會讀不到 → 停手，不會亂點
OCR_TAB_GENERAL = (640, 295, 520, 110)          # 一般設置：含 鎖定騎寵 / 鎖定戰寵 兩列
OCR_TAB_CATCH = (640, 296, 700, 40)             # 捉寵設置：自動抓寵 / 自動存倉庫 / 可抓捕數 那一列
OCR_FAMILY_FIELD = (640, 360, 230, 34)           # 2026-10-12 實機量：欄位 x 637～868（舊框 780 起切掉字）
OCR_PET_FIELD = (1000, 360, 230, 34)              # 欄位 x 1000～1230
CATCH_LIST_FAMILY = (700, 400, 300, 300)        # 系別下拉清單（8 項可見，要拖曳捲）
CATCH_LIST_PET = (1040, 400, 320, 300)          # 寵物下拉清單
LOCK_FIELD_W, LOCK_LIST_W, LOCK_LIST_H = 330, 330, 260   # 鎖定下拉：欄位 / 清單寬高（欄位 x 從 940 起，欄位 y ± 17；清單從欄位下方 +22 起）
LOCK_LIST_X = 940

GROWTH_RE = re.compile(r'(\d{1,3})\s*/\s*(\d{1,3})\s*/\s*(\d{1,3})\s*/\s*(\d{1,3})')


# ---- 純函式（測試直接餵）----
def scan_candidates(cards: dict, name: str) -> list:
    """pet.take 失敗時 LAST['cards']（{倉庫格: 「名字@等級」}）→ 名字吻合、等級讀不出（@None）的格號（1 起算，由小到大）。純函式"""
    out = []
    for k, v in (cards or {}).items():
        t = str(v)
        if name in t and t.endswith('@None'):
            try:
                out.append(int(k))
            except (TypeError, ValueError):
                pass
    return sorted(out)


def level_n(trans) -> int:
    return max(1, int(trans))


def box_names(trans: int) -> tuple:
    """(這次要開的禮盒, 開出來的下一個禮盒)"""
    return f'{trans}轉新手禮盒', f'{trans + 1}轉新手禮盒'


def family_for(species: str, family: str | None) -> str | None:
    return family or FAMILY_OF.get(species)


def parse_growth_line(text) -> str | None:
    """一行 OCR 文字 → 'a/b/c/d'（整行恰好是成長字串才算；多一堆別的字 → None）"""
    import petmatch
    t = petmatch.growth_norm(text)                                    # 同 pet.py 名字框：去空白 / 雜點標點（共用正規化）
    m = GROWTH_RE.fullmatch(t)
    return '/'.join(str(int(g)) for g in m.groups()) if m else None


def growth_partial(text, val: str) -> bool:
    """OCR 漏段的成長字串是否「可能是」val（純函式）：切成 4 段、讀到的段 ≥ 3 段且都與 val 相同、漏掉的段（空字串）當萬用。
    例：'48/10//2'、'48//7/2' 都可能是 '48/10/7/2'（2026-10-13 三轉 DKBO3 / DKBO5 實機）；整段讀錯（'48/10/8/2'）不算"""
    got = re.sub(r'\s+', '', str(text or '')).split('/')
    want = val.split('/')
    return len(got) == len(want) == 4 and sum(1 for g in got if g) >= 3 and all(not g or g == w for g, w in zip(got, want))


def pick_row(lines: list, ident: tuple) -> tuple:
    """下拉選項 [(文字, x, y)] 與身分 ('name', 名[, (), 備援成長字串…]) / ('growth', 'a/b/c/d'[, 同角色其他沒名字寵物的成長字串]) → (命中的 (文字, x, y) | None, 說明)。
    必須「剛好一列」吻合：名字用 uikit.snap_pet 對到同一個正式名；成長字串整行完全相同。0 列或 ≥ 2 列 → None（不猜）。
    成長字串沒有整行相同的列時才用漏段萬用（growth_partial）：吻合的列也可能是同角色別隻（ident 第 3 項）→ 有歧義就停，不選。
    名字找不到且有第 4 項（備援成長字串：還原名字前的字串，lock_items 給）→ 退回逐個成長字串比對，剛好一列吻合才選
    （**待實機確認**：寵物還原名字後外掛下拉是否顯示物種名是推測；若下拉仍顯示成長字串就走這條）"""
    kind, val = ident[0], ident[1]
    if kind == 'name' and len(ident) > 3 and ident[3]:
        hit, why = pick_row(lines, ('name', val))
        if hit:
            return hit, ''
        gs = tuple(ident[3])
        hits = []
        for g in gs:
            h, _ = pick_row(lines, ('growth', g, tuple(o for o in gs if o != g)))
            if h and not any(abs(h[2] - x[2]) <= 15 for x in hits):
                hits.append(h)
        if len(hits) == 1:
            return hits[0], ''
        return None, f'{why}；退回成長字串 {list(gs)} 比對吻合 {len(hits)} 列（要剛好 1 列）'
    others = tuple(ident[2]) if len(ident) > 2 else ()
    hits = []
    for t, x, y in lines:
        if kind == 'growth':
            ok = parse_growth_line(t) == val
        else:
            ok = uikit.snap_pet(t) == val
        if ok and not any(abs(y - h[2]) <= 15 for h in hits):          # 多個放大倍數會重複回同一列：y 差 ≤ 15 併成一個（2026-10-12）
            hits.append((t, x, y))
    if not hits and kind == 'growth':                                  # OCR 常漏整段數字（'49/10/8/1' → '49//8/1'）：4 段裡讀到的 ≥ 3 段都相同、漏的當萬用，且只有一列這樣吻合才用（2026-10-13 DKBO5 / DKBO3 實機）
        import petmatch

        def loose(t, v):                                               # 漏段（'49//8/1'）或某段被讀成漢字（'姍/9/5/6'，petmatch 共用規則；限 4 段）
            return growth_partial(t, v) or (len(petmatch.growth_fields(petmatch.growth_norm(t))) == 4 and petmatch.growth_compatible(t, v))
        for t, x, y in lines:
            if not loose(t, val):
                continue
            amb = [o for o in others if o != val and loose(t, o)]
            if amb:                                                    # 漏的那段剛好是兩隻的差別 → 分不出來，停
                return None, f'{kind} {val!r}：下拉「{t}」漏段，也可能是同角色的 {amb}（歧義，不選）'
            if not any(abs(y - h[2]) <= 15 for h in hits):
                hits.append((t, x, y))
    if len(hits) == 1:
        return hits[0], ''
    return None, f'{kind} {val!r}：下拉讀到 {[t for t, _, _ in lines]}，吻合 {len(hits)} 列（要剛好 1 列）'


def plain_row(lines: list, plain: str):
    """系別清單 OCR 行 → 剛好一列是 plain 的 (文字, x, y)，否則 None（純函式）。先找含完整字串的列；沒有才用寬鬆比對
    （首字在、至少 len-1 個字吻合、字數不多於 len+2；2026-10-13 雷龍系 半列讀不全），多個放大倍數同一列（y 差 ≤ 15）併成一個"""
    def uniq(pred):
        hits = []
        for t, x, y in lines:
            if pred(str(t)) and not any(abs(y - h[2]) <= 15 for h in hits):
                hits.append((t, x, y))
        return hits
    hits = uniq(lambda t: plain in t)
    if not hits:
        hits = uniq(lambda t: plain[0] in t and sum(c in t for c in plain) >= len(plain) - 1 and len(t.strip()) <= len(plain) + 2)
    return hits[0] if len(hits) == 1 else None


def family_below_action(lines: list, plain: str, backed: int, list_top: int) -> tuple:
    """系別目標列讀不到時，看正下方那列（FAMILY_BELOW）決定（純函式）→ (動作, 位置備援的 (名, x, y) | None)：
    'pick' = 下一列在清單內夠低（y - FAMILY_ROW_H ≥ 清單上緣 + 20，目標列整列露出只是 OCR 沒讀到）→ 點下一列 y - FAMILY_ROW_H（點完照樣讀欄位驗證）；
    'back' = 下一列貼著清單上緣（目標被切半）、還沒捲滿 FAMILY_BACK_MAX 次 → 往回捲一點；
    'stop' = 已往回捲過仍不行 → 不再往下捲（避免來回震盪）；'' = 沒看到下一列，照常往下捲"""
    below = FAMILY_BELOW.get(plain)
    ys = sorted((y, x) for t, x, y in lines if below and below in str(t))
    if not ys:
        return ('stop', None) if backed else ('', None)
    y, x = ys[0]
    if y - FAMILY_ROW_H >= list_top + 20:
        return 'pick', (plain, x, y - FAMILY_ROW_H)
    if backed < FAMILY_BACK_MAX:
        return 'back', None
    return 'stop', None


def role_ident(slots: list, species: str, battle_pet: str, which: str, growths=()) -> tuple | None:
    """鎖定下拉要選誰：騎寵 = 該角色寵物欄中物種 = species 的那隻（沒名字 → ('growth', 成長字串)；有名字 → ('name', 名)）；戰寵 = ('name', battle_pet)。
    growths = 這次抓的騎寵還原名字前的成長字串（catch 階段記在進度檔）：騎寵有名字時 ident = ('name', 名, (), growths) → 下拉沒有物種名才退回成長字串比對
    （名字為主 2026-10-14；**待實機確認**下拉顯示什麼）。找不到 / 有多隻 → None"""
    if which == '戰寵':
        n = sum(1 for s in slots if not s.get('empty') and s.get('name') == battle_pet)
        return ('name', battle_pet) if n == 1 else None             # 同名 2 隻（朵拉比斯 Lv126 / Lv1）下拉分不出來 → 不鎖、交人
    hits = [s for s in slots if not s.get('empty') and ((s.get('unnamed') and s.get('species') == species) or s.get('name') == species)]
    if not hits:                                                   # 物種沒登錄（縮圖 / 字串認不出）：退而用「目前騎乘中」的那隻（唯一才用；2026-10-12 實機 DKBO ?(49/9/8/2)）
        hits = [s for s in slots if not s.get('empty') and s.get('state') == '騎乘' and (s.get('unnamed') or s.get('name'))]
    if len(hits) != 1:
        return None
    s = hits[0]
    if not s.get('unnamed'):
        return ('name', s['name'], (), tuple(growths)) if growths else ('name', s['name'])
    others = tuple(x['unnamed'] for x in slots if not x.get('empty') and x.get('unnamed') and x is not s)
    return ('growth', s['unnamed'], others) if others else ('growth', s['unnamed'])   # 第 3 項：同角色其他沒名字寵物（pick_row 漏段萬用時排除歧義）


def lock_items(pets: dict, roles: list, species: str, battle_pet: str, which=('騎寵', '戰寵'), growths=()) -> tuple:
    """鎖定清單（純函式）：pets = {角色: 寵物欄} → ([(角色, 項目, True, ident)], 錯誤訊息或 '')；任一人找不到唯一一隻 → ([], 訊息)。
    growths = 騎寵還原名字前的成長字串（known_growths；鎖定騎寵下拉找不到物種名時的備援）"""
    items = []
    for r in roles:
        for w in which:
            ident = role_ident(pets.get(r) or [], species, battle_pet, w, growths if w == '騎寵' else ())
            if ident is None:
                return [], f'{r} 的{w}在寵物欄裡找不到唯一一隻（讀到 {[s.get("name") or s.get("raw_name") for s in (pets.get(r) or []) if not s.get("empty")]}）'
            items.append((r, w, True, ident))
    return items, ''


def new_pets(before: list, after: list) -> list:
    """抓寵前後寵物欄 → 新增的寵物（前一次是空格、這次有；有沒有名字都算，名字為主 2026-10-14：還原名字後新寵物有物種名）"""
    was_empty = {s['slot'] for s in before if s.get('empty')}
    return [s for s in after if not s.get('empty') and s['slot'] in was_empty]


def known_growths(prog: dict | None = None) -> list:
    """進度檔 catch 階段記的騎寵成長字串（還原名字前；{角色: [字串]} 攤平去重）→ 鎖定騎寵下拉的備援比對用"""
    d = ((load_progress() if prog is None else prog) or {}).get('data') or {}
    return list(dict.fromkeys(g for v in (d.get('growths') or {}).values() for g in v or [] if g))


def new_unnamed(before: list, after: list) -> list:
    """抓寵前後寵物欄 → 新增的沒名字寵物（slot dict 清單）：前一次是空格、這次有、且沒名字"""
    was_empty = {s['slot'] for s in before if s.get('empty')}
    return [s for s in after if not s.get('empty') and s['slot'] in was_empty and s.get('unnamed')]


def parse_count(text) -> int | None:
    """OCR「自動抓寵 自動存倉庫 可抓捕數：5 +」→ 5；讀不到 / 多個不同數字 → None"""
    m = re.search(r'可抓捕數\D{0,4}(\d{1,3})', re.sub(r'\s+', '', str(text or '')))
    return int(m.group(1)) if m else None


def plan(o: dict) -> list:
    """--dry-run / 說明用：(階段, [動作文字])"""
    sp, bp, ct, n = o['mount_species'], o['battle_pet'], o['catcher'], o['count']
    fam = family_for(sp, o.get('family')) or '（--family 必填）'
    box, nxt = box_names(o['trans'])
    return [
        ('preflight', [f'確認當前 = {LEADER}', '解散隊伍', '外掛：5 人鎖定騎寵 / 戰寵先取消', '讀 5 人寵物欄']),
        ('boxes', [f'5 人開 {box}（內容存公共，{nxt} 存個人；bag 95 驗證失敗各步自動重試 1 次）'] if not o['no_boxes'] else ['（--no-boxes 跳過）']),
        ('catch', ([f'{ct} 外掛捉寵設置「+」花石幣買可抓捕數到 {n}（--confirm-buy-catch，每個 50,000，前後驗石幣 / 鑽石）', f'外掛捉寵設置 {fam} → {sp}、可抓捕數 {n}、自動存倉庫 + 自動抓寵（直接抓，不試抓）', f'等抓完 → reset-name 還原名字、名字驗 {sp}（還原失敗才縮圖 + 成長字串登錄）', f'確認 {ct} 共 {n} 隻 {sp}'] if o.get('confirm_buy_catch') else [f'{ct} 公共倉庫取誘餌、拆到只剩 1', f'外掛捉寵設置 {fam} → {sp}、可抓捕數 1、自動存倉庫 + 自動抓寵', f'等抓完 → reset-name 還原名字、名字驗 {sp}（還原失敗才學物種）', f'再留 {n - 1} 個誘餌重複 → reset-name', f'確認 {ct} 共 {n} 隻 {sp}'])),
        ('distribute', [f'{ct} 存 {n - 1} 隻 {sp} 進公共（取最後格）', f'其他 {n - 1} 人各從公共取 1 隻']),
        ('ride', [f'5 人 {sp} 設騎乘']),
        ('battle', [f'5 人從個人倉庫取 {bp}@1（Lv1）、設出戰；同名多隻讀不出等級 → 逐隻取出驗 Lv1、不對存回換下一隻']),
        ('lock', [f'外掛 5 人：鎖定騎寵 = {sp}（下拉比物種名，找不到退回成長字串）、鎖定戰寵 = {bp}、兩項都勾']),
        ('cleanup', [f'{ct} 多餘誘餌存回公共', f'當前 {LEADER}、遇敵關', '寫 quest-log']
                    + (['（--no-grind：不去練功）'] if o.get('no_grind') else [f'去練功：grind.go(trans_hint={o["trans"]})（依等級選點；未滿地雷區背景起 follow）'])),
    ]


def print_plan(o: dict, from_stage: str, to_stage: str) -> None:
    on = False
    for st, acts in plan(o):
        on = on or st == from_stage
        print(f'  {"✓" if on else "·"} {st}')
        if on:
            for a in acts:
                print(f'      - {a}')
        if st == to_stage:
            on = False


# ---- 紀錄 ----
def event(msg: str) -> None:
    line = f'{time.strftime("%Y-%m-%d %H:%M:%S")} [rebirth_pets] {msg}'
    print(line, flush=True)
    try:
        EVENT_LOG.parent.mkdir(exist_ok=True)
        with open(EVENT_LOG, 'a', encoding='utf-8') as f:
            f.write(line + '\n')
    except OSError:
        pass


def load_progress() -> dict:
    try:
        return json.loads(PROGRESS.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return {}


def save_progress(d: dict) -> None:
    try:
        PROGRESS.parent.mkdir(parents=True, exist_ok=True)
        PROGRESS.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding='utf-8')
    except OSError:
        pass


# ---- 真實工具（測試換成 FakeTools，介面相同）----
def ocr_lines(box, *opts) -> list:
    """ocr.ps1 → [(文字, x, y)]（x / y = 文字中心，截圖座標）；逾時 / 失敗 []"""
    import subprocess
    import winenv
    try:
        r = winenv.run_ps('ocr.ps1', *map(str, box), *map(str, opts))
        d = json.loads((r.stdout.strip().splitlines() or [''])[-1])
    except (subprocess.TimeoutExpired, ValueError):
        return []
    return [(ln['text'], ln.get('x', 0), ln.get('y', 0)) for ln in d.get('lines', [])] if d.get('ok') else []


class Tools:
    """碰遊戲的全部動作（pet.py / bag.py / ass.py / team.py / char.py 的薄包裝；外掛捉寵 / 鎖定 / 拆分誘餌是本類自己寫的）"""

    pick_why = ''                                                  # 最近一次 _pick_dropdown 失敗原因（給呼叫端印）

    def sleep(self, s):
        uikit.sleep(s)

    def grind_go(self, trans):
        """去練功（grind.go：依等級選點、未滿地雷區背景起 follow；trans 只當提示，背包讀得到以背包為準）→ 退出碼"""
        import grind
        return grind.go(trans_hint=trans)

    def preflight(self):
        return uikit.preflight(SRC)

    def current(self):
        import char
        rc = char.current(True)
        return rc, char.LAST.get('current')

    def char_ensure(self, name):
        import char
        return char.ensure(name)

    def team_disband(self):
        import team
        return team.disband()

    def encounter_on(self):
        import heal
        return heal.encounter_on()

    def snap(self, tag):
        return uikit.snap(tag)

    # ---- 寵物（pet.py）----
    def pets_list(self, roles, img_only=None):
        """→ (rc, {角色: pet.list_role 的 slots})；寵物面板只開一次。img_only = 任務候選物種（沒名字的寵物只在這些之間比縮圖）"""
        import pet
        ctx = pet.load_ctx(True, img_only)
        out = {}
        with pet.Session(False, False) as s:
            if s.rc:
                return s.rc, out
            for r in roles:
                rc, slots = pet.list_role(r, ctx)
                if rc:
                    pet.save_ctx(ctx)
                    return rc, out
                out[r] = slots
            pet.save_ctx(ctx)
        return 0, out

    def pet_set_state(self, role, name, state, allow_mount=False):
        import pet
        return pet.set_state(role, name, state, None, allow_mount, True)

    def pet_set_state_many(self, roles, name, state, allow_mount=False):
        """→ (rc, 出錯的角色或 None)；寵物面板只開一次"""
        import pet
        rc = pet.set_state_many(','.join(roles), name, state, allow_mount, True)
        bad = next((o['role'] for o in pet.LAST.get('ops', []) if o.get('rc')), None)
        return rc, bad

    def pet_store_many(self, roles, pets, depot, allow_slot1=False, allow_mount_store=None, pick=None):
        import pet
        rc = pet.store_many(','.join(roles), pets, depot, allow_slot1, allow_mount_store or [], False, True, True, pick)
        return rc, dict(pet.LAST)

    def pet_take_many(self, roles, pets, depot):
        import pet
        rc = pet.take_many(','.join(roles), pets, depot, False, True, True)
        return rc, dict(pet.LAST)

    def pet_take_lv1_scan(self, role, name):
        """同名多隻、倉庫卡片等級讀不出（take_many 回 72）：逐隻取出（--index + --expect-level 1，取後切寵物分頁讀等級驗）→ 不是 Lv1（76）就存回個人倉庫、換下一隻。
        → (rc, info)。候選格取自 pet.take 失敗時 LAST['cards']（{格: 「名字@等級」}，@None = 等級讀不出）。
        格號：2026-10-13 三轉實機「取出 → 存回」後**其他卡的格號不變**（舊版假設遞補 idx = pos - k：DKBO2 候選 [1, 7] 取 1 存回後試 6、DKBO4 [1, 4] 試 3 都不是朵拉比斯 → 72；
        手動 take --index 7 才拿到 Lv1）→ 先用原格號；pet.take 帶名字時會先驗卡片名字（不符回 72、不取），回 72 才退一步試遞補格號 pos - 已存回數。
        某候選兩種格號都 72 → 換下一個候選；全部試完 → 72"""
        import pet
        rc = pet.take(role, 'personal', None, None, False, True, name, None, 1)
        if rc == 0:
            return 0, dict(pet.LAST)
        cands = scan_candidates(pet.LAST.get('cards') or {}, name)
        if rc != pet.EXIT_NAME or len(cands) < 2:
            return rc, dict(pet.LAST)
        info = {'cands': cands, 'tried': []}
        returned = 0                                               # 已存回幾隻（遞補備援用）
        for pos in cands:
            for idx in dict.fromkeys(i for i in (pos, pos - returned) if i >= 1):
                rc = pet.take(role, 'personal', idx, name, False, True, None, None, 1)
                info['tried'].append([idx, rc])
                if rc != pet.EXIT_NAME:                            # 72 = 卡片名字不符、沒取 → 試下一種格號
                    break
            if rc == 0:
                return 0, info
            if rc == pet.EXIT_NAME:
                continue
            lv = pet.LAST.get('level')
            if rc != pet.EXIT_VERIFY or lv in (None, 1):           # 不是「讀得到等級、但不是 1」的 76 = 別的問題（等級讀不出也不猜），不亂存回
                return rc, info
            info['tried'][-1].append(lv)
            rc2 = pet.store_many(role, [name], 'personal', False, [], False, True, True, 'last')   # 取出的不是 Lv1 → 存回，換下一隻
            if rc2:
                info['store_back_rc'] = rc2
                return rc2, info
            returned += 1
        return pet.EXIT_NAME, info

    def money(self):
        import catchbuy
        return catchbuy.money()

    def press_plus(self, role, limit=None):
        import catchbuy
        return catchbuy.press_plus(role, limit)

    def learn_species(self, role, slot, species, growth):
        import pet
        return pet.learn_species_cmd(role, slot, species, growth, True)

    def reset_names(self, roles):
        """名字框是成長字串的寵物 → 還原物種名（pet.reset_soft：67 / 9 / 10 原樣回、其他失敗 rc 0 + info['soft_rc']）→ (rc, info)"""
        import pet
        return pet.reset_soft(','.join(roles))

    # ---- 背包（bag.py + 拆分）----
    def box_open(self, role, trans):
        """開禮盒並存倉。→ (rc, info)。背包沒有禮盒 = 'skipped'（已開過，不算失敗）"""
        import bag
        box, nxt = box_names(trans)
        info = {'stored': [], 'personal': []}
        rc, found = bag.find_items(role, [box])
        if rc:
            return rc, info
        if found.get(box) is None:
            info['skipped'] = f'背包沒有 {box}'
            return 0, info
        rc = bag.use_item(role, box)
        if rc == bag.EXIT_VERIFY:                           # 95：用完驗證失敗 → 禮盒還在才重用一次（不在 = 已用掉）
            info['retry'] = ['use']
            self.sleep(2)
            rc, found = bag.find_items(role, [box])
            if not rc and found.get(box) is not None:
                rc = bag.use_item(role, box)
            elif not rc:
                rc = 0
        if rc:
            return rc, info
        for nm in BOX_CONTENTS:
            rc = bag.depot_store(role, nm, 'public')
            if rc == bag.EXIT_VERIFY:                        # 二轉 DKBO4 回 95、重跑才過：驗證失敗 → 等 2 秒再存一次（已存成功則回 92 = 找不到，視為已存）
                info.setdefault('retry', []).append(nm)
                self.sleep(2)
                rc = bag.depot_store(role, nm, 'public')
            if rc == bag.EXIT_ITEM:                          # 這次禮盒沒開出這項（或重試時已存好）
                continue
            if rc:
                info['failed'] = nm
                return rc, info
            info['stored'].append(nm)
        rc = bag.depot_store(role, nxt, 'personal')          # banPubDepot=1：禁止存公共，直接存個人
        if rc == bag.EXIT_VERIFY:
            info.setdefault('retry', []).append(nxt)
            self.sleep(2)
            rc = bag.depot_store(role, nxt, 'personal')
        if rc and rc != bag.EXIT_ITEM:
            info['failed'] = nxt
            return rc, info
        if not rc:
            info['personal'].append(nxt)
        return 0, info

    def bait_take(self, role, keep, keep_short=False):
        """每人最簡流程（2026-10-16 使用者「誘餌拆分怎那麼繁瑣」）：
        1. 背包有誘餌才讀疊數（沒有 = 第一次跑，不讀）：總數剛好 keep → 跳過（split_noop）；不是 keep → 全存回公共，再往下。
        2. 公共倉庫取整疊（沒有 → keep_short 回報現有 0、回 92，由呼叫端買「+」缺額）。
        3. 拆分（_split）：點拆分 → 只讀整疊數量 qty：< keep → 取消，keep_short 留背包照用（回 92），否則存回（回 92）；== keep → 取消、不存回；> keep → 輸入 keep 確定。
        4. 剩下那疊（qty − keep）存回公共。
        keep_short = True（petquest）：誘餌不夠時現有的照留背包、回 92 由呼叫端只買缺額 keep − split_short 次「+」。拆分座標已實機測過（notes/plan-dino-katan.md）"""
        import bag
        self.split_noop = False
        self.split_short = None
        # 先選人再讀格名（2026-10-16 p2 卡坦 catch2 根因：舊版沒選人就 find_item → 讀到背包面板剛開時顯示的「當前登錄」角色 DKBO6，
        # DKBO7 背包明明有 20 個誘餌卻當成沒有 → 去公共倉庫找不到 → 「誘餌現有 0」→ 外掛「+」白買）
        with bag.Session() as s:
            if s.rc:
                return s.rc
            rc = bag.select_role(role)
            if rc:
                return rc
            have = bag.find_item(BAIT, popup_fallback=False) is not None   # 只讀格名（名字樣板 / 縮圖 / 格名 OCR），不開彈窗
        if have:                                                  # 重跑才會有：讀疊數，剛好 keep 跳過，否則全存回重取
            rc, stacks = self._bait_stacks(role)
            if rc:
                return rc
            if stacks and all(q is not None for _, q in stacks) and sum(q for _, q in stacks) == keep:
                self.split_noop = True
                print(f'rebirth_pets：{role} 背包誘餌已剛好 {keep} 個 → 不取不拆', flush=True)
                return 0
            st = bag.depot_store(role, BAIT, 'public', all_copies=True)
            print(f'rebirth_pets：{role} 背包誘餌 {stacks} 不是 {keep} → 全存回公共 rc {st}', flush=True)
            if st:
                return st
        rc = bag.depot_take(role, BAIT, 'public', hint=getattr(self, 'bait_hint', None))
        if rc == bag.EXIT_ITEM and keep_short:                    # 公共倉庫沒有誘餌 = 現有 0 個
            self.split_short = 0
            print(f'rebirth_pets：{role} 背包誘餌不足 = 0（要 {keep}）', flush=True)
            return rc
        if rc:
            return rc
        self.bait_hint = bag.LAST.get('depot_slot')               # 下一人先點這格核對（整疊存回後多半回到同一格），不逐格掃
        rc = self._split(role, BAIT, keep)
        if self.split_noop:                                       # 整疊剛好 = keep：取消，不存回
            return 0
        if self.split_short is not None:                          # 整疊 < keep
            if keep_short:
                print(f'rebirth_pets：{role} 背包誘餌不足 = {self.split_short}（要 {keep}）→ 現有的留背包照用，缺 {keep - self.split_short} 個由外掛「+」買', flush=True)
                return rc
            st = bag.depot_store(role, BAIT, 'public', all_copies=True)
            print(f'rebirth_pets：{role} 誘餌只有 {self.split_short} 個（要 {keep}）→ 全存回公共倉庫 rc {st}', flush=True)
            return rc
        if rc:
            return rc
        return bag.depot_store(role, BAIT, 'public', keep_ok=True, want_count=self.split_qty - keep)   # 存「疊數 = 原疊 − keep」那疊；拆分後背包仍有新疊，不驗消失（2026-10-12 實機）

    def _bait_stacks(self, role):
        """→ (rc, [(格, 疊數)])：選好角色後讀背包誘餌各疊"""
        import bag
        with bag.Session() as s:
            if s.rc:
                return s.rc, []
            rc = bag.select_role(role)
            if rc:
                return rc, []
            return 0, bag.stacks_of(BAIT)

    def bait_take_many(self, roles, keep, keep_short=False):
        """多人取誘餌（2026-10-13）：背包面板只開一次（左欄頭像切人連續做完才關）；公共倉庫誘餌格號記起來，後面的人直接核對那格。
        → 0 / 第一個失敗的 rc（失敗人在 self.bait_failed）。每人流程同 bait_take（背包有誘餌先判斷、取整疊 → 只讀 qty 拆 keep → 其餘存回）"""
        import bag
        self.bait_hint, self.bait_failed = None, None
        with bag.Session() as s:
            if s.rc:
                return s.rc
            short_rc = 0
            for role in roles:
                rc = self.bait_take(role, keep, keep_short) if keep_short else self.bait_take(role, keep)
                if rc == bag.EXIT_ITEM and keep_short and self.split_short is not None:
                    short_rc, self.bait_failed = rc, role           # 不夠的人記起來，後面的人照取（公共空了就 0 個）
                    continue
                if rc:
                    self.bait_failed = role
                    return rc
                print(f'rebirth_pets：{role} 背包誘餌 = {keep}', flush=True)
        return short_rc

    def _split(self, role, name, n, slot=None):
        """背包 name → 彈窗 → 拆分 628,648 → 只讀整疊數量（670,430）：< n 取消 + split_short、回 92；== n 取消 + split_noop、回 0；> n 輸入 n 確定，split_qty = 整疊數。
        不再核對彈窗名稱 / 按鈕列 / 數量視窗標題（座標已實機測過：notes/plan-dino-katan.md、2026-10-12）。"""
        import bag
        self.split_qty = None
        if not 1 <= n <= 99:
            return uikit.fail(SRC, EXIT_CATCH, f'拆分數量 {n} 不合理')
        with bag.Session() as s:
            if s.rc:
                return s.rc
            rc = bag.select_role(role)
            if rc:
                return rc
            i = slot if slot is not None else bag.find_item(name)
            if i is None:
                return uikit.fail(SRC, bag.EXIT_ITEM, f'{role} 背包找不到 {name}（拆分）')
            sc = bag.slot_count(i)                                # 開彈窗前先讀背包格右下角疊數（像素），拆分框讀值要跟它一致
            if not bag.open_slot_popup(i):
                return uikit.fail(SRC, bag.EXIT_PANEL, '拆分：點道具沒開彈窗')
            if not bag._click(628, 648, bag.POPUP, f'rebirth_pets 拆分 {name}', wait_ms=700):
                return uikit.fail(SRC, bag.EXIT_PANEL, '拆分：彈窗特徵消失，沒點拆分')
            qty = bag.split_qty_read(sc)                          # 2026-10-16：舊版 OCR 預設參數把 20 讀成空 → 164；改像素字形 + 交叉核對
            if qty is None:
                uikit.gui('seq', 'click 828 545; wait 600', note='rebirth_pets 拆分：讀不到數量，取消')
                uikit.snap('rebirth-split-dialog')
                return uikit.fail(SRC, bag.EXIT_VERIFY, f'拆分：整疊數量讀不出 / 與背包格疊數 {sc.get("value")} 不一致（不猜）')
            self.split_qty = qty
            if qty < n:                                           # 整疊不夠：取消，呼叫端決定留背包或存回
                uikit.gui('seq', 'click 828 545; wait 600', note='rebirth_pets 拆分：整疊比要的少，取消')
                self.split_short = qty
                return uikit.fail(SRC, bag.EXIT_ITEM, f'{role} {name} 只有 {qty} 個，要 {n}（不夠）')
            if qty == n:                                          # 整疊剛好：拆分會失敗（#284「拆分失敗！」）→ 取消，不必存回
                uikit.gui('seq', 'click 828 545; wait 600', note='rebirth_pets 拆分：整疊就是要的數量，取消')
                self.split_noop = True
                return 0
            keys = {'1': (491, 334), '2': (615, 334), '3': (742, 334), '4': (491, 454), '5': (615, 454), '6': (740, 454),
                    '7': (491, 574), '8': (615, 574), '9': (740, 574), '0': (863, 334)}
            uikit.gui('seq', 'click 755 451; wait 500', note='rebirth_pets 拆分數量欄')
            for ch in str(n):
                x, y = keys[ch]
                uikit.gui('seq', f'click {x} {y}; wait 300', note=f'rebirth_pets 拆分鍵盤 {ch}')
            uikit.gui('seq', 'click 908 574; wait 500', note='rebirth_pets 拆分鍵盤 確認')
            uikit.gui('seq', 'click 610 545; wait 900', note='rebirth_pets 拆分 確定')
            if not uikit.is_open(bag.BAGANY):
                return uikit.fail(SRC, bag.EXIT_PANEL, '拆分後背包面板消失')
        return 0

    def bait_return(self, role):
        """背包還有誘餌就存回公共；沒有 = 0（不算失敗）"""
        import bag
        rc, found = bag.find_items(role, [BAIT])
        if rc:
            return rc
        if found.get(BAIT) is None:
            return 0
        return bag.depot_store(role, BAIT, 'public', all_copies=True)      # 多疊（拆分中斷留下的）全存回

    # ---- 外掛（ass 面板；本類自己寫的部分）----
    def _ass_open(self, role, tab):
        """單人：等戰鬥結束 → 開外掛 → 選角色 → 切分頁（呼叫端負責關面板）。多人一律用 ass_each（面板只開一次）"""
        import ass
        ok, why = ass.wait_not_battle(False)
        if not ok:
            return uikit.fail(SRC, uikit.EXIT_IN_BATTLE, why)
        if not ass.open_panel():
            return uikit.fail(SRC, 2, '外掛面板打不開')
        if not ass.select_role(role):
            return uikit.fail(SRC, 3, f'外掛選不到 {role}')
        return self._ass_tab(role, tab)

    def _ass_tab(self, role, tab):
        """外掛面板開著、角色已選：點分頁並 OCR 驗證分頁標題（讀不到就停，不點任何勾選）"""
        x, y = ASS_TAB[tab]
        uikit.gui('seq', f'click {x} {y}; wait 600', note=f'rebirth_pets 外掛分頁 {tab}')
        box, need = (OCR_TAB_GENERAL, ('鎖定騎寵', '鎖定戰寵')) if tab == 'general' else (OCR_TAB_CATCH, ('抓寵',))
        txt = ''.join(t for t, _, _ in ocr_lines(box, '-Zooms', '2,3,4'))
        if not all(k in txt for k in need):
            uikit.snap(f'rebirth-ass-tab-{tab}')
            return uikit.fail(SRC, 4, f'外掛分頁 {tab} OCR {txt!r} 沒有 {need}（待實機量的 OCR 框；沒點任何勾選）')
        return 0

    def ass_each(self, roles, tab, fn):
        """多人外掛批次（2026-10-12 A）：面板開一次 → 逐人 ass.select_role（左上頭像）→ 切分頁 → fn(role) → 關一次（ass._many：等戰鬥、跑馬燈避讓、失敗必關面板）。
        fn(role) → (rc, 值)。回 (rc, {角色: 值}, 出錯的角色或 None)；某人失敗立即停"""
        import ass
        def visit(role):
            rc = self._ass_tab(role, tab)
            if rc:
                return rc, None, f'{role} 外掛分頁 {tab} 不對', []
            rc, val = fn(role)
            return rc, val, '' if not rc else f'{role} 失敗 rc {rc}', []
        rc, out, msg, info = ass._many({r: None for r in roles}, visit)
        if rc and msg and not info.get('role'):
            uikit.fail(SRC, rc, msg)
        if rc:
            self.ass_close_hard()
        return rc, out, info.get('role')

    def ass_close_hard(self) -> bool:
        """失敗出口確認外掛面板關了（ass._many / catch_setup 已點過 X；這裡是保險）：還開著 → 等 0.5 秒再 ass.close_panel（點 X 1318,90 + 驗證消失），最多 2 輪。
        2026-10-13 三轉：捉寵系別下拉開著時點 X 被吃掉、面板殘留 → 下一步開寵物面板 rc 9（人手動點 X 1316,90）。仍開著 → snap + 警告，回 False"""
        import ass
        for _ in range(2):
            if not ass.panel_open():
                return True
            uikit.sleep(0.5)
            ass.close_panel()
        if not ass.panel_open():
            return True
        uikit.snap('rebirth-ass-close-fail')
        print('rebirth_pets 警告：外掛面板關不掉（請 shot 看畫面，手動點 X 1318,90）', flush=True)
        return False

    def _checked(self, xy):
        """外掛勾選框 → True 勾 / False 未勾 / None 讀不到或判讀不確定（ass.read_check 正向辨認，不確定會等一下重讀；
        2026-10-16 前是「框心不是純白 = 已勾」→ p2 自動轉換戰寵 5 人都被當成已勾、一次都沒點）"""
        import ass
        return ass.read_check(xy)

    def _toggle(self, xy, want, note):
        """讀勾選框 → 只在確定不同時點 1 次 → 讀回（還沒變多等一次，不補點）。判讀不確定 = 停手（不當已勾 / 未勾）"""
        import ass
        cur = self._checked(xy)
        if cur is None:
            uikit.snap('rebirth-ass-check-unsure')
            return uikit.fail(SRC, 6, f'{note}：勾選框 {xy[0]},{xy[1]} 讀不到 / 判讀不確定（不是白底、也不像打勾：分頁沒畫好、浮字蓋住或位置不對）→ 沒點')
        if cur == want:
            print(f'rebirth_pets：{note}：已是{"勾" if want else "未勾"}（框內讀到{"打勾筆劃" if want else "全白"}），不點', flush=True)
            return 0
        if not ass.panel_open():
            return uikit.fail(SRC, 6, f'{note}：外掛面板消失，沒點')
        uikit.gui('seq', f'click {xy[0]} {xy[1]}; wait 500', note=f'rebirth_pets {note}')
        now = self._checked(xy)
        if now is not None and now != want:
            uikit.sleep(ass.CONFIRM_WAIT2)
            now = self._checked(xy)
        if now != want:
            uikit.snap('rebirth-ass-toggle')
            return uikit.fail(SRC, 4, f'{note}：點了勾選讀回 {now}（不重點）')
        return 0

    def lock_get(self, role):
        rc, out, _ = self.lock_get_many([role])
        return rc, (out or {}).get(role)

    def lock_get_many(self, roles):
        """→ (rc, {角色: {'騎寵': bool, '戰寵': bool}})；外掛面板只開一次"""
        rc, out, _ = self.ass_each(roles, 'general', lambda r: (0, {w: self._checked(xy['check']) for w, xy in LOCK_XY.items()}))
        return rc, out

    def lock_set(self, role, which, on, ident=None):
        """which = '騎寵' / '戰寵'。on=False：只取消勾選；on=True：先（需要時）選下拉再勾。ident 見 pick_row"""
        rc, _ = self.lock_set_many([(role, which, on, ident)])
        return rc

    def lock_set_many(self, items, normal=None):
        """items = [(角色, '騎寵'|'戰寵', on, ident)]：同角色排在一起，外掛面板只開一次。→ (rc, 出錯的角色或 None)
        normal（例 '攻擊'）：每人鎖定做完後同一次停留再切「戰鬥設置」分頁把戰寵一般動作設成 normal（ass._visit_pet_normal，現值相同不改、讀回確認），
        不用再另開一次面板（petquest restore 2026-10-16）"""
        by: dict = {}
        for r, w, on, ident in items:
            by.setdefault(r, []).append((w, on, ident))

        def fn(role):
            for w, on, ident in by[role]:
                rc = self._lock_set_here(role, w, on, ident)
                if rc:
                    return rc, None
            if normal:
                import ass
                uikit.gui('seq', f'click {ASS_TAB["battle"][0]} {ASS_TAB["battle"][1]}; wait 600', note=f'rebirth_pets 外掛分頁 battle（{role} 戰寵一般動作）')
                rc, _st, msg, _ = ass._visit_pet_normal(normal, False)(role)
                if rc:
                    return uikit.fail(SRC, rc, msg or f'{role} 戰寵一般動作 = {normal} 失敗'), None
            return 0, True
        rc, _, bad = self.ass_each(list(by), 'general', fn)
        return rc, bad

    def _lock_set_here(self, role, which, on, ident=None):
        """外掛一般設置分頁已開、角色已選：鎖定騎寵 / 戰寵。下拉選項一律 OCR 讀字找「剛好一列」吻合的（每人順序不同，errlog #257 盲選第 2 項鎖錯），
        選完讀回欄位文字再勾，勾完讀回勾選框"""
        import ass
        xy = LOCK_XY[which]
        if not on:
            return self._toggle(xy['check'], False, f'{role} 取消鎖定{which}')
        if not ident:
            return uikit.fail(SRC, 7, '鎖定要有 ident（要選哪一隻）')
        dx, dy = xy['dd']
        fld = ocr_lines((LOCK_LIST_X, dy - 17, LOCK_FIELD_W, 34), '-Zooms', '2,3,4')
        if not pick_row(fld, ident)[0]:                                  # 欄位已經是目標就不開下拉
            uikit.gui('seq', f'click {dx} {dy}; wait 500', note=f'rebirth_pets {role} 鎖定{which} 下拉')
            lines = ocr_lines((LOCK_LIST_X, dy + 22, LOCK_LIST_W, LOCK_LIST_H), '-Zooms', '2,3,4')
            hit, why = pick_row(lines, ident)
            if not hit:
                uikit.snap(f'rebirth-lock-{which}')
                uikit.gui('seq', f'click {dx} {dy}; wait 400', note='rebirth_pets 收下拉（點回欄位）')
                return uikit.fail(SRC, 7, f'{role} 鎖定{which}：{why}（沒選、沒勾）')
            if not ass.panel_open():
                return uikit.fail(SRC, 6, '下拉選項點之前外掛面板消失')
            uikit.gui('seq', f'click {hit[1]} {hit[2]}; wait 500', note=f'rebirth_pets {role} 鎖定{which} 選 {hit[0]}')
            fld = ocr_lines((LOCK_LIST_X, dy - 17, LOCK_FIELD_W, 34), '-Zooms', '2,3,4')
            h2, _ = pick_row(fld, ident)
            if not h2:
                uikit.snap(f'rebirth-lock-{which}-field')
                return uikit.fail(SRC, 7, f'{role} 鎖定{which}：選了「{hit[0]}」但欄位 OCR {[t for t, _, _ in fld]} 對不上 {ident}（不勾）')
        return self._toggle(xy['check'], True, f'{role} 勾鎖定{which}')

    def catch_setup(self, role, family, species, count):
        """捉寵設置：系別 → 物種 → 讀可抓捕數 = count。**不點「+」、不碰丟棄區**。留著面板開著給 catch_start（同一個 session）"""
        rc = self._ass_open(role, 'catch')
        if rc:
            return rc
        rc = self._catch_setup_pick(role, family, species, count)
        if rc:                                                   # 失敗時關面板：下拉清單開著的狀態會讓下次點下拉變成「關」
            import ass
            ass.close_panel()
            self.ass_close_hard()
        return rc

    def catch_setup_many(self, assign, count, reuse=False):
        """多人捉寵設置 + 勾自動存倉庫 / 自動抓寵（外掛面板只開一次）。assign = [(角色, 系別, 物種)] → (rc, 出錯的角色或 None)。
        reuse=True（petquest 同一輪第 2 批起，review 1013b §2.5-A）：沿用上一批的系別 / 物種下拉 —— 欄位 OCR 讀不到字（鯊魚系常讀不出）也不重選下拉，
        只有讀到「別的字」才重選；可抓捕數 / 勾選照做，最後 _catch_verify 讀回驗證照舊"""
        conf = {r: (f, sp) for r, f, sp in assign}

        def fn(role):
            fam, sp = conf[role]
            rc = self._catch_setup_pick(role, fam, sp, count, reuse)
            if not rc:
                rc = self._catch_toggles(role)
            if not rc:
                rc = self._catch_verify(role, fam, sp)
            return rc, None if rc else True
        rc, _, bad = self.ass_each([r for r, _, _ in assign], 'catch', fn)
        return rc, bad

    def catch_poll_many(self, roles):
        """多人讀捉寵進度（唯讀，面板只開一次）→ (rc, {角色: (可抓捕數或 None, 自動抓寵勾選)})"""
        def fn(role):
            left = parse_count(''.join(t for t, _, _ in ocr_lines(OCR_TAB_CATCH, '-Zooms', '2,3,4')))
            return 0, (left, self._checked(CATCH_XY['auto']))
        rc, out, _ = self.ass_each(roles, 'catch', fn)
        return rc, out

    def _field_is(self, box, name):
        return self._text_has(' '.join(t for t, _, _ in ocr_lines(box, '-Zooms', '2,3,4')), name)

    @staticmethod
    def _text_has(txt, name):
        return bool(txt) and (name in txt or (name[0] in txt and sum(c in txt for c in name) >= len(name) - 1))

    def _field_ok(self, box, name, reuse):
        """欄位是目標 → True；reuse 時欄位 OCR 讀不到任何字也當 True（上一批已設好並讀回驗證過；最後 _catch_verify 仍會讀回）"""
        txt = ' '.join(t for t, _, _ in ocr_lines(box, '-Zooms', '2,3,4'))
        return self._text_has(txt, name) or (reuse and not txt.strip())

    def _catch_setup_pick(self, role, family, species, count, reuse=False):
        fam_ok = self._field_ok(OCR_FAMILY_FIELD, family, reuse)  # 欄位已經是目標（上次設過 / 預設）就不再開下拉（下拉開關狀態難判斷）
        pet_ok = fam_ok and self._field_ok(OCR_PET_FIELD, species, reuse)
        if fam_ok and pet_ok:
            n = parse_count(''.join(t for t, _, _ in ocr_lines(OCR_TAB_CATCH, '-Zooms', '2,3,4')))
            if n != count:
                uikit.snap('rebirth-catch-count')
                return uikit.fail(SRC, 4, f'可抓捕數讀到 {n}，要 {count}（背包誘餌數不對？不勾自動抓寵）')
            return 0
        if not fam_ok and not self._pick_dropdown(CATCH_XY['family_dd'], CATCH_LIST_FAMILY, OCR_FAMILY_FIELD, ('name', family), scroll=True, snap_tag='family', plain=family):
            return uikit.fail(SRC, EXIT_CATCH_PICK, f'{role} 捉寵系別選不到 {family}（{self.pick_why or "點了但欄位讀回不是它"}；沒勾自動抓寵）')
        if not self._pick_dropdown(CATCH_XY['pet_dd'], CATCH_LIST_PET, OCR_PET_FIELD, ('name', species), scroll=False, snap_tag='species', fam_species=SPECIES_ORDER.get(family)):
            return uikit.fail(SRC, EXIT_CATCH_PICK, f'{role} 捉寵物種選不到 {species}（{self.pick_why or "點了但欄位讀回不是它"}；沒勾自動抓寵）')
        n = parse_count(''.join(t for t, _, _ in ocr_lines(OCR_TAB_CATCH, '-Zooms', '2,3,4')))
        if n != count:
            uikit.snap('rebirth-catch-count')
            return uikit.fail(SRC, 4, f'可抓捕數讀到 {n}，要 {count}（背包誘餌數不對？不勾自動抓寵）')
        return 0

    def _pick_dropdown(self, dd, list_box, field_box, ident, scroll, snap_tag, plain=None, fam_species=None):
        import ass
        self.pick_why = ''
        lines = []
        uikit.gui('seq', f'click {dd[0]} {dd[1]}; wait 500', note=f'rebirth_pets 捉寵下拉 {snap_tag}')
        if scroll:                                              # 清單會記住上次捲動位置：先往上拖 4 次回到頂，再小步往下找（2026-10-12 實機）
            for _ in range(4):
                uikit.gui('drag', '750', '480', '750', '650', note='rebirth_pets 捉寵清單回頂')
            uikit.sleep(1.0)
        backed = 0                                                      # 已往回捲幾次（FAMILY_BELOW）
        for k in range(14):
            lines = ocr_lines(list_box, '-Zooms', '2,3,4')
            if plain:                                                   # 系別名不在 Monster 表 → 直接比文字
                hit = plain_row(lines, plain)
            else:
                hit, _ = pick_row(lines, ident)
            if not hit and plain in FAMILY_NEIGHBORS:                # OCR 讀不到這列（鯊魚系常讀不出）：上下鄰居都讀到、間距約 2 列 → 取中間
                prv, nxt = FAMILY_NEIGHBORS[plain]
                ys = {k: [(x, y) for t, x, y in lines if any(n in t for n in alts)] for k, alts in (('p', prv), ('n', nxt))}
                for (x1, y1) in ys['p']:
                    for (_, y2) in ys['n']:
                        if 70 <= y2 - y1 <= 100 and hit is None:
                            hit = (plain, x1, (y1 + y2) // 2)
            if not hit and plain in FAMILY_BELOW:
                act, pos_hit = family_below_action(lines, plain, backed, list_box[1])
                if act == 'pick':
                    hit = pos_hit
                elif act == 'back':
                    backed += 1
                    uikit.gui('drag', '750', '520', '750', '566', note=f'rebirth_pets 捉寵清單往回捲一點（{plain} 被清單上緣切掉，只露出下一列 {FAMILY_BELOW[plain]}）')   # 2026-10-13 實機：雷龍系 在大象系正上方，捲到只剩半列時 OCR 讀不到、下一步就捲過頭
                    uikit.sleep(1.0)
                    continue
                elif act == 'stop':
                    break
            if not hit and not scroll and ident[0] == 'name' and fam_species and ident[1] in fam_species:
                hit = (ident[1], 1115, 421 + 42 * fam_species.index(ident[1]))      # 位置備援：只在 OCR 沒讀到時；點完照樣讀欄位驗證
            if hit:
                if not ass.panel_open():
                    return False
                uikit.gui('seq', f'click {hit[1]} {hit[2]}; wait 500', note=f'rebirth_pets 捉寵 選 {hit[0]}')
                fld = ' '.join(t for t, _, _ in ocr_lines(field_box, '-Zooms', '2,3,4'))
                if plain:                                                    # OCR 常漏字（鯊魚系 → 鯊系）：首字在、至少吻合 len-1 個字
                    return plain[0] in fld and sum(c in fld for c in plain) >= len(plain) - 1
                return uikit.snap_pet(fld) == ident[1] or ident[1] in fld
            if not scroll:
                if k >= PICK_RETRY:
                    break
                if not any(t.strip() for t, _, _ in lines) and k >= 1:      # 清單一直空白 = 下拉沒展開（點 1 次被吃掉 / 剛好收起）→ 再點一次
                    uikit.gui('seq', f'click {dd[0]} {dd[1]}; wait 500', note=f'rebirth_pets 捉寵下拉 {snap_tag} 重點')
                else:
                    uikit.sleep(0.8)                                         # 清單還在渲染 / OCR 偶爾漏讀：等一下再讀
                continue
            if k == 13:
                break
            (x0, y0), (x1, y1) = (750, 650), (750, 600)     # 50px ≈ 2 列；大拖會慣性亂跳過目標列
            uikit.gui('drag', str(x0), str(y0), str(x1), str(y1), note='rebirth_pets 捉寵清單捲動')
            uikit.sleep(1.0)                                        # 清單有慣性滑動：等停下來再讀（不等會點到差一列的項目，2026-10-12 實機點成飛天蛙系）   # gui 參數要分開（一整串會被當成單一參數 → 不捲）
        uikit.snap(f'rebirth-catch-{snap_tag}')
        self.pick_why = f'{snap_tag} 下拉讀到 {[t for t, _, _ in lines]}，找不到 {ident[1]}'
        if scroll or any(t.strip() for t, _, _ in lines):                  # 清單開著卻沒目標列：點回欄位收起（開著時點 X 會被吃掉 → 面板殘留，2026-10-13 系別清單實機），下次不會變成「關」
            uikit.gui('seq', f'click {dd[0]} {dd[1]}; wait 400', note=f'rebirth_pets 捉寵下拉 {snap_tag} 收起')
        return False

    def _catch_verify(self, role, family, species):
        """勾完讀回：系別 / 物種欄位文字 + 自動抓寵 / 自動存倉庫勾選都對才算設好（2026-10-13：物種沒選到就關面板、事後才發現）"""
        bad = []
        for box, want, label in ((OCR_FAMILY_FIELD, family, '系別'), (OCR_PET_FIELD, species, '物種')):
            txt = ' '.join(t for t, _, _ in ocr_lines(box, '-Zooms', '2,3,4')).strip()
            if not txt:
                print(f'rebirth_pets：{role} {label}欄位 OCR 讀不到字，略過文字讀回（選取時已驗過）', flush=True)
            elif not self._text_has(txt, want):
                bad.append(f'{label}欄位 {txt!r} 不是 {want}')
        if self._checked(CATCH_XY['auto']) is not True:
            bad.append('自動抓寵沒勾')
        if self._checked(CATCH_XY['store']) is not True:
            bad.append('自動存倉庫沒勾')
        if bad:
            uikit.snap('rebirth-catch-verify')
            return uikit.fail(SRC, EXIT_CATCH_PICK, f'{role} 捉寵設置讀回不符：{"、".join(bad)}')
        return 0

    def catch_start(self, role, count):
        """面板已在捉寵設置（catch_setup 後）：自動存倉庫 → 自動抓寵 勾選，關面板"""
        import ass
        try:
            return self._catch_toggles(role)
        finally:
            ass.close_panel()

    def _catch_toggles(self, role):
        rc = self._toggle(CATCH_XY['store'], True, f'{role} 勾自動存倉庫')
        if rc:
            return rc
        return self._toggle(CATCH_XY['auto'], True, f'{role} 勾自動抓寵')

    def catch_wait(self, role, timeout=CATCH_TIMEOUT_S):
        """每 CATCH_POLL_S 重開外掛讀可抓捕數 + 自動抓寵勾選；數 = 0 且自動抓寵已被遊戲取消 → (0, 0)；逾時 (rc, 剩幾隻)"""
        import ass
        end = uikit.clock() + timeout
        left = None
        while True:
            self.sleep(CATCH_POLL_S)
            rc = self._ass_open(role, 'catch')
            if rc:
                return rc, left
            left = parse_count(''.join(t for t, _, _ in ocr_lines(OCR_TAB_CATCH, '-Zooms', '2,3,4')))
            auto = self._checked(CATCH_XY['auto'])
            ass.close_panel()
            if auto is False and left in (0, None):                       # 可抓捕數 OCR 常讀不到；遊戲抓完自己取消勾選（2026-10-12 實機）
                return 0, 0
            if uikit.clock() >= end:
                return uikit.fail(SRC, EXIT_CATCH, f'抓寵 {timeout:.0f} 秒內沒抓完（可抓捕數 {left}、自動抓寵 {auto}）'), left


# ---- 流程 ----
class Run:
    def __init__(self, T, o: dict):
        self.T, self.o = T, o
        self.prog = load_progress() if o.get('resume', True) else {}
        self.info: dict = {}

    def stop(self, rc: int, msg: str, **extra):
        self.info.update(extra, rc=rc, msg=msg)
        event(f'失敗 rc={rc}：{msg}')
        self.T.snap('rebirth-pets-fail')
        return rc

    def done(self, stage: str, **data):
        self.prog.setdefault('done', [])
        if stage not in self.prog['done']:
            self.prog['done'].append(stage)
        self.prog.setdefault('data', {}).update(data)
        save_progress(self.prog)
        event(f'階段 {stage} 完成')

    def need(self, stage: str) -> bool:
        return stage in self.prog.get('done', [])

    # ---- 階段 ----
    def preflight(self):
        T, o = self.T, self.o
        rc = T.preflight()
        if rc:
            return rc
        rc, cur = T.current()
        if rc:
            return self.stop(EXIT_PRE, f'讀不到當前角色（char rc {rc}）')
        import charstate
        if not charstate.same(cur, LEADER):
            rc = T.char_ensure(LEADER)
            if rc:
                return self.stop(EXIT_PRE, f'當前是 {cur}，切回 {LEADER} 失敗（char rc {rc}）')
        rc = T.team_disband()
        if rc:
            return self.stop(EXIT_PRE, f'解散隊伍失敗（team rc {rc}）')
        sts, todo = {}, []
        if not o.get('keep_lock'):
            rc, sts = T.lock_get_many(ALL_ROLES)                # 外掛面板只開一次讀 5 人（2026-10-12 批次化）
            if rc:
                return self.stop(EXIT_PRE, f'讀外掛鎖定狀態失敗（rc {rc}）')
            todo = [(r, w, False, None) for r in ALL_ROLES for w in ('騎寵', '戰寵') if (sts.get(r) or {}).get(w) is not False]   # 不確定（None）也進 todo：_toggle 會再讀、仍不確定就停手，不默默略過
        if todo:
            rc, bad = T.lock_set_many(todo)
            if rc:
                return self.stop(EXIT_PRE, f'{bad} 取消鎖定失敗（rc {rc}）')
        rc, pets = T.pets_list(ALL_ROLES)
        if rc:
            return self.stop(EXIT_PRE, f'讀 5 人寵物欄失敗（pet rc {rc}）')
        self.info['pets_before'] = {r: [(s.get('name') or s.get('raw_name'), s.get('state')) for s in sl if not s.get('empty')] for r, sl in pets.items()}
        if o['catcher'] not in ALL_ROLES:
            return self.stop(EXIT_ARGS, f'--catcher {o["catcher"]} 不是 {ALL_ROLES} 之一')
        self.done('preflight', pets_before=self.info['pets_before'])
        return 0

    def boxes(self):
        o = self.o
        if o['no_boxes']:
            self.done('boxes', skipped=True)
            return 0
        res = {}
        for r in ALL_ROLES:
            rc, info = self.T.box_open(r, o['trans'])
            res[r] = info
            if rc:
                return self.stop(EXIT_BOX, f'{r} 禮盒 / 存倉失敗（bag rc {rc}）', bag_rc=rc, boxes=res)
        self.done('boxes', boxes=res)
        return 0

    def catch(self):
        T, o = self.T, self.o
        sp, ct, n = o['mount_species'], o['catcher'], o['count']
        fam = family_for(sp, o.get('family'))
        if not fam:
            return self.stop(EXIT_ARGS, f'{sp} 沒有預設系別，請給 --family')
        rc, pets = T.pets_list([ct])
        if rc:
            return self.stop(EXIT_CATCH, f'讀 {ct} 寵物欄失敗（pet rc {rc}）')
        have = [s for s in pets[ct] if not s.get('empty') and (s.get('species') == sp or s.get('name') == sp)]
        empties = sum(1 for s in pets[ct] if s.get('empty'))
        need = max(0, n - len(have))
        if need == 0:
            self.done('catch', caught=len(have))
            return 0
        if empties < need:
            return self.stop(EXIT_CATCH, f'{ct} 寵物欄空格 {empties} < 還要抓的 {need}（舊寵物沒存完？rebirth.py 的 storepets 階段應已全存；寵物欄還有寵物請先清空）')
        before = pets[ct]
        if o.get('confirm_buy_catch'):                                     # 使用者規定：騎寵直接用石幣「+」買可抓捕數（每個 50,000）→ 買到 = n 再直接抓
            rc = self._buy_catch(ct, n)
            if rc:
                return rc
            return self._direct_catch(ct, fam, sp, n, before)
        if o.get('direct_catch'):                                          # 使用者 2026-10-12：外掛「+」已買好 N 個可抓捕數 → 不取誘餌、不試抓，直接抓 N 隻
            return self._direct_catch(ct, fam, sp, n, before)
        # 先試抓 1 隻
        if not any(s.get('unnamed') and s.get('species') == sp for s in before) and len(have) == 0:
            rc = self._catch_round(ct, fam, sp, 1)
            if rc:
                return rc
            rc = self._rename(ct)                                          # 名字為主：成長字串還原成物種名
            if rc:
                return rc
            rc, pets = T.pets_list([ct])
            if rc:
                return self.stop(EXIT_CATCH, f'試抓後讀寵物欄失敗（pet rc {rc}）')
            fresh = new_pets(before, pets[ct])
            if len(fresh) != 1:
                return self.stop(EXIT_CATCH, f'試抓 1 隻後寵物欄多了 {len(fresh)} 隻寵物（要剛好 1）', new=[s.get('name') or s.get('raw_name') for s in fresh])
            s0 = fresh[0]
            rc = self._check_new(ct, s0, sp, img_gate=False)                # 三重確認（備援）：外掛選的物種 + 剛好多 1 隻 + 誘餌 1 → 1；名字讀不出才登錄
            if rc:
                return rc
            need -= 1
        if need > 0:
            rc = self._catch_round(ct, fam, sp, need)
            if rc:
                return rc
            rc = self._rename(ct)
            if rc:
                return rc
        rc, pets = T.pets_list([ct])
        if rc:
            return self.stop(EXIT_CATCH, f'抓完讀寵物欄失敗（pet rc {rc}）')
        got = [s for s in pets[ct] if not s.get('empty') and (s.get('species') == sp or s.get('name') == sp)]
        if len(got) != n:
            return self.stop(EXIT_CATCH, f'{ct} 寵物欄物種確認的 {sp} 有 {len(got)} 隻，要 {n}（其他沒名字的：{[s.get("raw_name") for s in pets[ct] if s.get("unnamed") and not s.get("species")]}）')
        self.done('catch', caught=len(got), growths={ct: self._growths(ct, got)})
        return 0

    def _rename(self, ct):
        """抓完還原名字（pet.reset_soft）：67 費用字樣 → 103 停手（鐵則 3）；9 / 10 透傳；其他失敗 → 記事件、照常（名字讀不出的那隻走 learn-species 備援）。
        還原成功的成長字串記在 self.info['renamed']（鎖定騎寵下拉備援比對用）"""
        rc, info = self.T.reset_names([ct])
        if rc in (uikit.EXIT_UNKNOWN_SCREEN, uikit.EXIT_HALT):
            return rc
        if rc:
            return self.stop(EXIT_CATCH, f'{ct} 還原名字讀到費用字樣（pet rc {rc}）→ 已按取消、停手（鐵則 3：改名不該花錢，請人看 tools/.cache/ui-log/*pet-rename* 截圖）', pet_rc=rc)
        gs = (info.get('renamed') or {}).get(ct) or []
        self.info.setdefault('renamed', {}).setdefault(ct, []).extend(gs)
        if info.get('soft_rc'):
            event(f'{ct} 還原名字沒全部成功（pet rc {info["soft_rc"]}：{info.get("msg", "")}）→ 名字讀不出的新寵物走 learn-species 備援')
        elif gs:
            event(f'{ct} 還原名字 {len(gs)} 隻：{gs}')
        return 0

    def _check_new(self, ct, s0, sp, img_gate=True):
        """新寵物 s0 的身分（名字為主）：名字 = sp → 過；名字是別的 → 103；名字框是成長字串（還原失敗）→ 備援：已登錄 species = sp 就過，
        否則 learn-species 登錄（img_gate：縮圖要認得是 sp 且分數 ≥ 0.9 才登錄；試抓那隻靠「剛好多 1 隻」三重確認不看縮圖）"""
        if s0.get('name'):
            if s0['name'] == sp:
                return 0
            return self.stop(EXIT_CATCH, f'新寵物第 {s0["slot"]} 格名字是「{s0["name"]}」，不是抓的 {sp}', slot=s0['slot'])
        if s0.get('species') == sp:
            return 0
        if not s0.get('unnamed'):
            return self.stop(EXIT_CATCH, f'新寵物第 {s0["slot"]} 格名字讀不出（{s0.get("raw_name")}），也不是成長字串 → 不登錄', slot=s0['slot'])
        if img_gate and (s0.get('img_species') != sp or (s0.get('img_score') or 0) < 0.9):
            return self.stop(EXIT_CATCH, f'新寵物第 {s0["slot"]} 格縮圖認不出是 {sp}（{s0.get("img_species")} {s0.get("img_score")}）→ 不登錄', slot=s0['slot'])
        rc = self.T.learn_species(ct, s0['slot'], sp, s0['unnamed'])
        if rc:
            return self.stop(EXIT_CATCH, f'登錄物種失敗（pet rc {rc}）', pet_rc=rc)
        return 0

    def _growths(self, ct, got):
        """進度檔要記的騎寵成長字串：這次還原名字前的 + 仍沒名字的（鎖定下拉備援）"""
        return list(dict.fromkeys((self.info.get('renamed') or {}).get(ct, []) + [s.get('unnamed') for s in got if s.get('unnamed')]))

    def _buy_catch(self, ct, n):
        """catchbuy.buy_to：外掛捉寵設置「+」按到可抓捕數 = n（續跑安全：已夠就不按）。不讀石幣；按前讀不到鑽石不按、按後鑽石讀不到 / 有變、可抓捕數不是 +1 就停（鐵則 3）"""
        import catchbuy
        T = self.T
        event(f'{ct} 用石幣「+」買可抓捕數到 {n}（--confirm-buy-catch；每個 {catchbuy.PLUS_COST} 石幣，預計最多 {n * catchbuy.PLUS_COST}）')
        kind, msg, code, bought = catchbuy.buy_to(ct, n, T.money, T.press_plus, event)
        self.info['bought'] = bought
        if kind == 'ok':
            return 0
        if code in (uikit.EXIT_UNKNOWN_SCREEN, uikit.EXIT_HALT):
            return code
        return self.stop(EXIT_CATCH, f'買可抓捕數失敗：{msg}', bought=bought)

    def _direct_catch(self, ct, fam, sp, n, before):
        """直接抓 n 隻（可抓捕數已用外掛「+」買好）：捉寵設置（讀回可抓捕數 = n）→ 勾自動存倉庫 / 自動抓寵 → 等抓完 →
        多出剛好 n 隻沒名字的寵物，且縮圖比對都認得是 sp（img_species、分數 ≥ 0.9）才登錄物種（成長字串）"""
        T = self.T
        rc = T.catch_setup(ct, fam, sp, n)
        if rc:
            return self.stop(EXIT_CATCH, f'{ct} 外掛捉寵設置失敗（rc {rc}；' + ('系別 / 物種下拉選不到或讀回不符，見 snap rebirth-catch-*' if rc == EXIT_CATCH_PICK else f'可抓捕數沒讀到 {n}？') + '）')
        rc = T.catch_start(ct, n)
        if rc:
            return self.stop(EXIT_CATCH, f'{ct} 勾自動抓寵失敗（rc {rc}）')
        event(f'{ct} 開始自動抓 {n} 隻 {sp}（直接抓，不試抓）')
        rc, left = T.catch_wait(ct)
        if rc:
            return self.stop(EXIT_CATCH, f'等抓寵失敗（rc {rc}，剩 {left}）')
        rc = self._rename(ct)                                              # 名字為主：成長字串還原成物種名
        if rc:
            return rc
        rc, pets = T.pets_list([ct])
        if rc:
            return self.stop(EXIT_CATCH, f'抓完讀寵物欄失敗（pet rc {rc}）')
        fresh = new_pets(before, pets[ct])
        if len(fresh) != n:
            return self.stop(EXIT_CATCH, f'抓完寵物欄多了 {len(fresh)} 隻寵物（要 {n}）', new=[s.get('name') or s.get('raw_name') for s in fresh])
        learned = False
        for s0 in fresh:
            if not s0.get('name') and s0.get('species') != sp:
                learned = True
            rc = self._check_new(ct, s0, sp)
            if rc:
                return rc
        if learned:                                                        # 備援登錄過 → 重讀確認
            rc, pets = T.pets_list([ct])
            if rc:
                return self.stop(EXIT_CATCH, f'登錄後讀寵物欄失敗（pet rc {rc}）')
        got = [s for s in pets[ct] if not s.get('empty') and (s.get('species') == sp or s.get('name') == sp)]
        if len(got) != n:
            return self.stop(EXIT_CATCH, f'{ct} 寵物欄物種確認的 {sp} 有 {len(got)} 隻，要 {n}')
        self.done('catch', caught=len(got), growths={ct: self._growths(ct, got)})
        return 0

    def _catch_round(self, ct, fam, sp, k):
        T = self.T
        rc = T.bait_take(ct, k)
        if rc:
            return self.stop(EXIT_CATCH, f'{ct} 取 {k} 個誘餌失敗（rc {rc}）', bag_rc=rc)
        rc = T.catch_setup(ct, fam, sp, k)
        if rc:
            return self.stop(EXIT_CATCH, f'{ct} 外掛捉寵設置失敗（rc {rc}）')
        rc = T.catch_start(ct, k)
        if rc:
            return self.stop(EXIT_CATCH, f'{ct} 勾自動抓寵失敗（rc {rc}）')
        event(f'{ct} 開始自動抓 {k} 隻 {sp}')
        rc, left = T.catch_wait(ct)
        if rc:
            return self.stop(EXIT_CATCH, f'等抓寵失敗（rc {rc}，剩 {left}）')
        return 0

    def distribute(self):
        T, o = self.T, self.o
        sp, ct, n = o['mount_species'], o['catcher'], o['count']
        others = [r for r in ALL_ROLES if r != ct]
        if len(others) != n - 1:
            return self.stop(EXIT_ARGS, f'--count {n} 與其他角色數 {len(others)} 不合（要 count = 角色數）')
        rc, info = T.pet_store_many([ct], [sp] * (n - 1), 'public', allow_slot1=False, allow_mount_store=[sp], pick='last')
        if rc:
            return self.stop(EXIT_DIST, f'{ct} 存 {n - 1} 隻 {sp} 進公共失敗（pet rc {rc}：{info.get("msg", "")}）', pet_rc=rc)
        rc, info = T.pet_take_many(others, [sp], 'public')
        if rc:
            return self.stop(EXIT_DIST, f'{others} 從公共取 {sp} 失敗（pet rc {rc}：{info.get("msg", "")}）', pet_rc=rc)
        self.done('distribute')
        return 0

    def ride(self):
        T, sp = self.T, self.o['mount_species']
        rc, bad = T.pet_set_state_many(ALL_ROLES, sp, '騎乘', True)      # 寵物面板只開一次
        if rc:
            return self.stop(EXIT_RIDE, f'{bad} 設 {sp} 騎乘失敗（pet rc {rc}）', pet_rc=rc, role=bad)
        self.done('ride')
        return 0

    def battle(self):
        T, bp = self.T, self.o['battle_pet']
        rc, info = T.pet_take_many(ALL_ROLES, [bp + '@1'], 'personal')        # 只取 Lv1（倉庫可能有舊的 Lv130 同名寵）
        if rc == 72 and hasattr(T, 'pet_take_lv1_scan'):                      # 同名多隻、卡片等級讀不出：逐隻取出驗 Lv1，不對存回換下一隻（二轉 DKBO2 手動 --index）
            event(f'取 {bp}@1 回 72（同名多隻 / 等級讀不出？）→ 逐人逐隻取出驗 Lv1')
            rc, pets = T.pets_list(ALL_ROLES)
            if rc:
                return self.stop(EXIT_BATTLE, f'讀寵物欄失敗（pet rc {rc}）', pet_rc=rc)
            todo = [r for r in ALL_ROLES if not any(not s_.get('empty') and (s_.get('name') == bp) for s_ in pets[r])]
            for r in todo:
                rc, i2 = T.pet_take_lv1_scan(r, bp)
                self.info.setdefault('lv1_scan', {})[r] = i2
                if rc:
                    return self.stop(EXIT_BATTLE, f'{r} 逐隻取 Lv1 {bp} 失敗（pet rc {rc}：{i2.get("msg", i2.get("tried", ""))}）', pet_rc=rc)
        elif rc:
            return self.stop(EXIT_BATTLE, f'從個人倉庫取 {bp} 失敗（pet rc {rc}：{info.get("msg", "")}）', pet_rc=rc)
        rc, bad = T.pet_set_state_many(ALL_ROLES, bp, '出戰', False)
        if rc:
            return self.stop(EXIT_BATTLE, f'{bad} 的 {bp} 設出戰失敗（pet rc {rc}）', pet_rc=rc, role=bad)
        self.done('battle')
        return 0

    def lock(self):
        T, o = self.T, self.o
        rc, pets = T.pets_list(ALL_ROLES)
        if rc:
            return self.stop(EXIT_LOCK, f'讀寵物欄失敗（pet rc {rc}）', pet_rc=rc)
        items, why = lock_items(pets, ALL_ROLES, o['mount_species'], o['battle_pet'], growths=known_growths(self.prog))   # 騎寵有名字 → 下拉比物種名，找不到才退回成長字串（待實機確認）
        if why:
            return self.stop(EXIT_LOCK, why)
        rc, bad = T.lock_set_many(items)                       # 外掛面板只開一次（2026-10-12 批次化）
        if rc:
            return self.stop(EXIT_LOCK, f'{bad} 鎖定失敗（rc {rc}）', role=bad)
        self.done('lock')
        return 0

    def cleanup(self):
        T, o = self.T, self.o
        rc = T.bait_return(o['catcher'])
        if rc:
            return self.stop(EXIT_CLEAN, f'{o["catcher"]} 誘餌存回公共失敗（bag rc {rc}）', bag_rc=rc)
        rc, cur = T.current()
        import charstate
        if rc or not charstate.same(cur, LEADER):
            rc = T.char_ensure(LEADER)
            if rc:
                return self.stop(EXIT_CLEAN, f'收尾切回 {LEADER} 失敗（char rc {rc}）')
        try:
            if T.encounter_on():
                return self.stop(EXIT_CLEAN, '收尾時原地遇敵是開的（本流程不該開），請人確認')
        except Exception:
            pass
        rc, pets = T.pets_list(ALL_ROLES)
        final = {r: [(s.get('name') or s.get('raw_name') or '?', s.get('state')) for s in sl if not s.get('empty')] for r, sl in (pets or {}).items()} if not rc else {}
        write_quest_log(o, self.prog, final)
        self.done('cleanup', final=final)
        return 0


def write_quest_log(o: dict, prog: dict, final: dict) -> None:
    lines = [f'\n## 轉生後寵物重整（腳本 rebirth_pets.py，{time.strftime("%Y-%m-%d")}）',
             f'- 參數：轉 {o["trans"]}、騎寵 {o["mount_species"]}、戰寵 {o["battle_pet"]}、捉寵角色 {o["catcher"]}、{o["count"]} 隻。',
             f'- 完成階段：{"、".join(prog.get("done", []))}。']
    if final:
        lines.append('- 結束寵物欄：' + '；'.join(f'{r} ' + ' / '.join(f'{n}({s})' for n, s in v) for r, v in final.items()) + '。')
    try:
        with open(QUEST_LOG, 'a', encoding='utf-8') as f:
            f.write('\n'.join(lines) + '\n')
    except OSError:
        pass


# 帳號特有預設：抓寵者 = 名單第 2 個（主視窗 DKBO2、PrimalSA2 = DKBO7）；隻數 = 名單人數；騎寵 / 戰寵物種是遊玩選擇，其他視窗要不同就給 --mount-species / --battle-pet
DEFAULTS = dict(trans=1, mount_species='布拉奇多斯', battle_pet='朵拉比斯', catcher=(ALL_ROLES[1:2] or [''])[0], count=len(ALL_ROLES) or 5, family=None, store_mount=None,
                no_boxes=False, keep_lock=False, direct_catch=False, confirm_buy_catch=False, no_grind=False)


def run(trans=1, from_stage: str = 'preflight', to_stage: str = 'cleanup', dry_run: bool = False, tools=None, **kw) -> int:
    o = dict(DEFAULTS, trans=level_n(trans), **kw)
    LAST.clear()
    import charstate
    cc = charstate.norm_char(o['catcher'], ALL_ROLES)                  # 只認這個視窗（PSA_CLIENT）的名單
    if not ALL_ROLES or cc is None:
        print(f'{SRC}：--catcher {o["catcher"]!r} 不認得（這個視窗的名單：{ALL_ROLES or "沒有登錄（clients.ROSTERS）"}）', file=sys.stderr)
        return EXIT_ARGS
    o['catcher'] = cc
    if from_stage == 'store' or to_stage == 'store':                     # store 段已拿掉（2026-10-16）：舊的 --from / --to store 當作 boxes→catch 的邊界
        print(f'{SRC}：store 階段已拿掉（舊寵物改由 rebirth.py storepets 全存）；--from store 改從 catch、--to store 改到 boxes', file=sys.stderr)
        from_stage = 'catch' if from_stage == 'store' else from_stage
        to_stage = 'boxes' if to_stage == 'store' else to_stage
    if from_stage not in STAGES or to_stage not in STAGES or STAGES.index(from_stage) > STAGES.index(to_stage):
        print(f'{SRC}：--from / --to 階段不對（{STAGES}）', file=sys.stderr)
        return EXIT_ARGS
    uk = {uikit.snap_pet(o['mount_species']), uikit.snap_pet(o['battle_pet'])}
    if None in uk:
        print(f'{SRC}：--mount-species / --battle-pet 不在 Monster 表', file=sys.stderr)
        return EXIT_ARGS
    o['mount_species'], o['battle_pet'] = uikit.snap_pet(o['mount_species']), uikit.snap_pet(o['battle_pet'])
    if o['store_mount']:
        print(f'{SRC}：--store-mount 已無作用（2026-10-16 起舊寵物由 rebirth.py storepets 在轉生前全存，本腳本不再有 store 段）', file=sys.stderr)
        o['store_mount'] = None
    if o.get('confirm_buy_catch'):
        o['direct_catch'] = True                                                 # 買到 count 個可抓捕數就直接抓（不取誘餌、不試抓）
    if not 2 <= o['count'] <= 5:
        print(f'{SRC}：--count 要 2～5', file=sys.stderr)
        return EXIT_ARGS
    if dry_run:
        print(f'{SRC} --dry-run（不碰遊戲）：參數 {o}')
        print_plan(o, from_stage, to_stage)
        LAST.update(ok=True, rc=0, dry_run=True, plan=[s for s, _ in plan(o)])
        return 0
    T = tools or Tools()
    R = Run(T, o)
    if from_stage != 'preflight':                                        # 續跑：前面的階段要在進度檔裡有紀錄
        missing = [s for s in STAGES[:STAGES.index(from_stage)] if s not in R.prog.get('done', []) and not (s == 'boxes' and o['no_boxes'])]
        if missing:
            print(f'{SRC}：--from {from_stage} 但進度檔裡沒有完成 {missing}（先照順序跑，或刪 tools/.cache/rebirth_pets.json 重來）', file=sys.stderr)
            return EXIT_ARGS
    else:
        R.prog = {'done': [], 'data': {}, 'started': time.strftime('%F %T'), 'opts': {k: v for k, v in o.items()}}
    event(f'開始：from={from_stage} to={to_stage} {o}')
    rc = 0
    for st in STAGES[STAGES.index(from_stage):STAGES.index(to_stage) + 1]:
        event(f'階段 {st}')
        rc = getattr(R, st)()
        if rc:
            break
    if not rc and to_stage == STAGES[-1] and not o.get('no_grind'):
        # 全部階段完成 → 去練功（使用者 2026-10-15：rebirth → rebirth_pets → 練功連成一條；不寫死地雷區）
        event(f'全部完成 → 去練功（grind.go，轉數提示 {o["trans"]}；依等級選點，未滿地雷區背景起 follow）')
        grc = T.grind_go(o['trans'])
        R.info['grind_rc'] = grc
        event(f'去練功 rc={grc}' + ('' if not grc else '（50～59 見 grind.py；寵物重整已全部完成，只差練功）'))
        rc = grc
    LAST.update(R.info, ok=rc == 0, rc=rc)
    LAST['done'] = list(R.prog.get('done', []))
    return rc


def main(argv=None) -> int:
    import winenv
    winenv.enable_server()
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--trans', type=int, default=1)
    ap.add_argument('--mount-species', default=DEFAULTS['mount_species'])
    ap.add_argument('--battle-pet', default=DEFAULTS['battle_pet'])
    ap.add_argument('--catcher', default=DEFAULTS['catcher'])
    ap.add_argument('--count', type=int, default=DEFAULTS['count'])
    ap.add_argument('--family', default=None)
    ap.add_argument('--store-mount', default=None, help='已無作用（保留參數，印一行提示）：舊寵物改由 rebirth.py storepets 全存')
    ap.add_argument('--from', dest='from_stage', default='preflight', choices=STAGES + ['store'])
    ap.add_argument('--to', dest='to_stage', default='cleanup', choices=STAGES + ['store'])
    ap.add_argument('--dry-run', action='store_true')
    ap.add_argument('--no-boxes', action='store_true')
    ap.add_argument('--direct-catch', action='store_true', help='catch：可抓捕數已用外掛「+」買好 = count，不取誘餌、不試抓，直接抓')
    ap.add_argument('--confirm-buy-catch', action='store_true', help='catch：用外掛捉寵設置「+」花石幣買可抓捕數到 count（每個 50,000，每次前後驗石幣；使用者規定騎寵這樣抓）；隱含 --direct-catch')
    ap.add_argument('--no-grind', action='store_true', help='全部階段完成後不去練功（預設會 grind.go：依等級選點 + 未滿地雷區起 follow）')
    ap.add_argument('--keep-lock', action='store_true', help='preflight 不先取消外掛鎖定騎寵 / 戰寵（使用者 2026-10-12：直接存，遊戲真的擋才解鎖）')
    a = ap.parse_args(argv)
    rc = run(a.trans, a.from_stage, a.to_stage, a.dry_run, None, mount_species=a.mount_species, battle_pet=a.battle_pet, catcher=a.catcher,
             count=a.count, family=a.family, store_mount=a.store_mount, no_boxes=a.no_boxes, keep_lock=a.keep_lock, direct_catch=a.direct_catch, confirm_buy_catch=a.confirm_buy_catch,
             no_grind=a.no_grind)
    print(json.dumps(dict(LAST, rc=rc), ensure_ascii=False, default=str))
    return rc


if __name__ == '__main__':
    sys.exit(main())
