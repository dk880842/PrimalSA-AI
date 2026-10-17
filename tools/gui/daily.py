#!/usr/bin/env python3
"""每日任務（委託接取）腳本：薩姆吉爾醫院 1005 的「委託接取」NPC，5 環 × 2 項成品，各項「快速合成」→ 兩項 1/1 綠 →「提交委託」→ 5/5 領裝備升級石。只用標準函式庫。

倉庫批次（2026-10-17 使用者：取一個就切回背包又關面板太冗餘，未實機）：同一人的存倉 / 取料一次做完——`evict_many`（room 清單先批次存個人、個人滿 95 的再批次存公倉並記 in_public）、
`take_many`（final 取料）→ `Tools.depot_store_many / depot_take_many` = `bag.depot_store_many / depot_take_items`：面板只開 1 次、倉庫子分頁各只切 1 次、每樣不切回背包頁，整批後核對 1 次；
每樣成功後立刻更新 ledger / 進度檔；批次沒取 / 存到的（找不到 92 / 失敗 / 沒處理）退回單樣流程（含 94 背包滿重試、胡椒原本錯誤語意）。

設計（notes/plan-daily.md v3 §4，使用者 2026-10-17 定案；**全程未實機**，只有離線測試）：各買各的、各合成各的，不經公倉轉手（胡椒除外）。
移動 / 組隊（使用者 2026-10-17 新定案，取代「解散後各自走到醫院」；play-p1-daily2 實測：組隊不退隊、不走路也點得開委託 NPC）：
  醫院段（read / mid / final）開頭 gather_hospital：隊長 DKBO **一人**走到 1005:38,40（hosp_solo：傳送落點 92,99 → 一個 seq 固定點擊
          〔村子 5 段 = heal.VILLAGE_FAST → 換圖 PRIMER → 醫院 25,65 起 5 段，每段 waitstill 4000、段 2 起 ifok，play-p1-route 實測 19.2～19.4 秒〕，
          最後讀一次座標，不對才 hosp_route 逐段 step_to；在醫院入口只走醫院段）
          → 快速組隊（隊員被拉到 38,47）→ **不解散**：DKBO2 → DKBO3 → DKBO4 → DKBO5 → DKBO 切角色（切前先關面板），每人不走路直接點 NPC
          （點位 walk.npc_screen((41,42), 讀到的座標)；讀不到用 38,47 的 651,197；沒開再點一次）
  便利店段（sam / fish）開頭 into_shop：組隊（已組不點）→ 全隊傳送 → 帶隊走進 1009 / 2009、到第一家店員前 → 解散 → 每人切角色各自在店內走、買
          買完不在本段回醫院：下一個醫院段的 gather_hospital 由隊長一人走回（薩村段從 1009 走出口回村；漁村段先傳送薩姆吉爾）→ 快速組隊把隊員拉過來
          （play-p1-route 實測：隊員在 2009、隊長在 1005:38,40 form 成功，4 人落 38,47；--regroup gather = 先在店內組隊再帶隊走，保留備援、預設不用）
  續跑：team.form（已組好 = 0 不點、不完整 → 解散重組）/ team.disband（沒隊伍 = 0 不點）本身看現況，所以每段開頭照上面的流程呼叫即可
        （fish 買到一半斷 → 隊伍是散的，重跑 into_shop 先組隊再解散；醫院合成到一半斷 → 隊伍組著，form 不點）
  店內買序（2026-10-17 p1 兩次 227 修）：dailyplan.store_route 與 buy_at 都把店內商品依該店清單 index 由小到大排（只往下捲、不回頭；不再「早環先買」）；
          shopkit.select_item 目標在視野上方時 scroll_top 歸零再找。存倉由 make_room / choose_evict 決定，與買序無關；bought 以名稱記，續跑不重買。
  買後背包名稱核對不擋（2026-10-17 p1 DKBO5 水分多的香草「多早」OCR 不確定 → 誤 227 + 重買 500 修，離線測試、未實機）：數量框判 bought 當下就記 bought / ledger（本來就是），
          背包名稱核對找不到只寫 log（不 pop bought、不 227）；只有 zeroish（歸 0 但字認不出）才當硬閘。舊進度檔香草沒記 bought → `daily.py mark-bought DKBO5 水分多的香草 <數量>` 補記再續跑。
  背包放不下（2026-10-17 p1 DKBO3 fish 227 修，離線測試、未實機）：每家店先 dp.buy_batches 排批——存倉順序 **材料（最晚環才用的先）→ 成品（最晚提交環的先）**；
          存完還放不下（這家店種類太多）→ 分批：買放得下的清單前綴 → 關店存倉（剛買、最晚才用的）→ 再進店買剩下的；連一種都放不下才 227（訊息寫背包帳 / 店種類 / 上限）。
          成品存倉後 mid 不提交該環（products_away），final fetch_materials 連成品一起從倉庫取回再提交。
  prep    停練功 / 關遇敵 / 等戰鬥 → 組隊（練功時本來就組著，不點）→ 全隊傳送薩姆吉爾（不解散）
  read    gather_hospital → 輪流 char.switch：點 NPC 開委託面板 → 讀 5 環 × 上 / 下 → daily-<角色>.json
          成品名讀法（2026-10-17 修 225）：名稱框 OCR -Zooms 2,3,4,5 -Dark 0 → dp.vote_lines **逐倍率各自 snap 投票**（舊版把各倍率 join 成一串 →「成弓箭8口成弓箭8」）；
          數字尾碼（合成爪 7 / 3）要 ≥2 倍率同意才確定，否則開快速合成彈窗讀大字 + 材料列 → dp.resolve_name（同族只差數字的用材料列分）；仍不確定 → 225 不猜
          快速合成彈窗（第二輪，p1 樣本 99 張）：大字框 380,398,204,50；材料列整欄一次讀（dp.pop_rows 依 y 分列）；▼ 亮（材料 4 種以上）且還分不出 → 材料列內拖一次再讀（pop_scroll）；
          合成前（craft_item，2026-10-17 改）：**大字不再是合成閘門**——只讀一次大字寫 log；明確投給「別的已知成品」才 229（防點錯項），讀空 / 讀不出一律放行；
          不讀材料列、不捲動。保留：彈窗開了（QCRAFT）、計數紅字像素 popup_short（紅 = 不合成）、合成後該項變綠、提交前兩項綠。dp.pop_check 仍給 read 段 peek_item / resolve_name 用
          read 段 peek_item 用 pop_name：投不出名字隔 0.5 秒只重讀大字、最多 3 次（craft_item 不再用）
          大字 OCR 帶 -Small 1（POP_NAME_OPTS）：實機先縮成跟截圖同一張 1440 縮圖再裁（根因：實機原生 2880 取像讀空、截圖讀得出，2026-10-17 dev-pop-live）
  翻頁（2026-10-17 dev-shop-title，未實機）：goto_page 讀頁碼（dp.page_vote 各倍率一致才收）到目標頁再等 0.4 秒重讀確認，盲翻後也要讀到頁碼；
          mid / final 每項合成前、提交前都 goto_page（修：翻頁 4 → 5 立刻讀成 5、面板其實在 4/5 → 點第 5 環項 229 彈窗沒開）
  final-close（2026-10-17 p1 play-p1-daily5 三個實機問題，離線測試、未實機）：
          ① 5 環全提交後面板沒有藍色合成鈕 → uikit.DAILY 特徵（含兩顆合成鈕）不中，daily_close / char.clear_panels 判「沒開」不關 → 切下一人 rc 9。
            修：daily.DAILY_BASE（DAILY_SIG 去掉合成鈕兩點）判開著；daily_close 兩輪關彈窗 + 面板並回是否關掉；Tools.close_panels（switch_to / leader_current 切角色前都呼叫）先用它關
          ② craft_item 點合成後彈窗最晚約 4 秒才浮出（舊版只等 1.6 秒 → 229）：輪詢 POP_WAIT_N = 18 × 0.25 秒，失敗前再等 1 秒重檢
          ③ Tools.walk_to 走出口拋 RuntimeError（卡在中間座標 72,103）但 wait_map(exit_map) 已在目標地圖（2009）→ 算成功（寫 log），不再 224
  mid / final 每人開頭 sync_greens：還沒記 crafted 的項先看面板計數（STATE_GRID 字區 → dp.count_area），已 1/1 綠 → 記 crafted 不開彈窗；兩項都綠 → 直接提交
  plan    離線：每人 10 項 → 配方 → 薩村 1009 / 漁村 2009 / 公倉胡椒 → 每人購買清單（不讀背包 / 倉庫格數）；沒給 --confirm-buy 停 221
  （便利店選商品：shopkit.select_item 標題逐倍率比對該店清單投票 title_is，第二輪離線 132/132；標題 OCR 帶 -Small 1〔dev-shop-title 修 2009 長名 227〕、選不到存 ui-log shop-select-fail 並寫各倍率原字）
  sam     into_shop → 5 人輪流沿櫃檯逐店買自己的薩村料（背包材料種類模型放不下 → 存個人倉庫；個人倉庫滿 → 公倉並記 in_public）
  mid     gather_hospital → 5 人輪流（組隊中）：材料齊的項先合成、該環兩項都綠就提交（沒人有事可做就整段跳過）
  fish    into_shop → 5 人輪流買漁村料
  final   gather_hospital → 5 人輪流（組隊中）：每環先從個人倉庫 / 公倉取料（含已合成但存倉的成品）→ 合成 → 提交，直到 5/5（胡椒從公倉取整疊、用完整疊存回）
  finish  組隊（已組著不點）→ grind.go（--no-grind 略）
順序固定 DKBO2 → DKBO3 → DKBO4 → DKBO5 → DKBO（clients.leader_last；結束時當前角色 = 隊長，不用另外切回）。

用法（專案根目錄；WSL / Windows 原生指令相同；PSA_CLIENT=PrimalSA2 → DKBO6～10）：
  uv run --no-project python tools/gui/daily.py read-all [--roles DKBO,DKBO2]      # 只做 prep + read（不花錢）
  uv run --no-project python tools/gui/daily.py plan [--roles ...]                  # 離線：讀進度檔印每人計畫與石幣估算
  uv run --no-project python tools/gui/daily.py show                                # 離線：每人各段 / 各環狀態
  uv run --no-project python tools/gui/daily.py mark <角色> <環> <上|下> crafted|submitted   # 離線：手動補完後同步進度檔（submitted 整環、上下不看）
  uv run --no-project python tools/gui/daily.py mark-bought <角色> <材料> <數量>      # 離線：數量框 / 遊戲日誌證明已買、進度檔沒記時補記（防重買）
  uv run --no-project python tools/gui/daily.py run [--roles ...] [--from 段] [--confirm-buy] [--fresh] [--dry-run] [--no-grind] [--regroup pull|gather]
    --confirm-buy  買材料（500 / 個）與合成（1000 / 項）都花石幣：沒給 = 讀完清單 + 印計畫就停（221）
    --from 段      prep / read / plan / sam / mid / fish / final / finish；預設從進度檔續跑（段內跳過已完成的人 / 已買的種類 / 已合成的項）
    --fresh        丟掉進度檔重來（跨過 00:00 後想重做時用；材料還在身上 / 倉庫，plan 不知道 → 人要先看過）
    --dry-run      同 plan（不碰遊戲）
    --regroup      買完回醫院的組隊方式：pull（預設）= 隊長一人走回 38,40 再快速組隊；gather = 先在店內組隊再帶隊走（pull 拉不過來時用）
  可 import：daily.run(roles=None, confirm_buy=False, from_stage=None, fresh=False, dry_run=False, grind=True, tools=None, regroup='pull') → 退出碼；結果 dict 在 daily.LAST

鐵則：3（每日任務例外，使用者 2026-10-17）**不讀石幣、不讀鑽石**：買到沒看數量框歸 0 + 背包名稱；不拆疊、不丟東西、不碰寵物、不買胡椒 1～3（dp.PEPPERS；塔姆塔姆產的胡椒 2825 有賣，當一般材料照買）。
      5 答題介面 → uikit.preflight 正面命中即停；不 clear 旗標。委託面板 / 快速合成 / 便利店內只用 uikit.safe_click（禁區：提交委託 / 彈窗合成 / 獎勵箭頭，動作內 allow 放行）。
      不認得的畫面 / 面板打不開 → 停手，不亂點；絕不點空白處（倉庫左下擴容 = 鑽石提示）。
退出碼：0 / 1 / 2 / 8 / 9 / 10 共用（uikit，原碼回傳）；本檔 220～229（dailyplan.EXIT_NAMES）：
  220 參數 / 沒名單 / 今天全部已完成 / 跨過 00:00   221 要花石幣沒給 --confirm-buy   222 胡椒公倉取不到   223 停練功 / 傳送 / 解散 / 組隊（訊息帶 --regroup gather 提示）/ 切角色失敗
  224 隊長走不到醫院 38,40 / 走不進 1009 / 2009 店員前、委託面板開不了（隊員不走路，點不開就停）   225 讀清單失敗   226 某人全部環都不支援   227 購買失敗（含背包放不下）
  228 個人倉庫 / 公倉存取失敗   229 合成 / 提交失敗（兩項不是 1/1 綠不提交；提交後 n/5 沒 +1；5/5 驗證不過）
有環被跳過（不支援）不算失敗：該人其他環照做，結束 rc 0；環不用依序提交（遊戲沒規定）。
"""
import argparse
import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import clients  # noqa: E402
import dailyplan as dp  # noqa: E402
import logpaths  # noqa: E402
import shopkit  # noqa: E402
import uikit  # noqa: E402

SRC = 'daily'
EVENT_LOG = logpaths.p(clients.npath('quest-events.log'))
ROLES = clients.roster()
LEADER = ROLES[0] if ROLES else ''
PASS = (uikit.EXIT_IN_BATTLE, uikit.EXIT_UNKNOWN_SCREEN, uikit.EXIT_HALT)        # 8 / 9 / 10：原碼停手
(EXIT_ARGS, EXIT_NOBUY, EXIT_PEPPER, EXIT_PREP, EXIT_WALK, EXIT_READ, EXIT_NOROLE, EXIT_BUY, EXIT_DEPOT, EXIT_CRAFT) = (
    dp.EXIT_ARGS, dp.EXIT_NOBUY, dp.EXIT_PEPPER, dp.EXIT_PREP, dp.EXIT_WALK, dp.EXIT_READ, dp.EXIT_NOROLE, dp.EXIT_BUY, dp.EXIT_DEPOT, dp.EXIT_CRAFT)

# ---- 版面（截圖 1440×830，鏡頭最左；notes/daily-probe.md M1～M13）----
HOSPITAL, VILLAGE, MARINAS_MAP = 1005, 1000, 2000
HOSP_ENTRY = (25, 65)                                            # 醫院 → 村子的出口格（站上去會被傳回村）
HOSP_IN = (26, 65)                                               # heal.walk_village 進醫院後實際站的格（play-p1-daily2 實測）
HOSP_WAYPOINTS = [(31, 60), (36, 60), (38, 55), (38, 48), (38, 40)]   # 醫院無通行格資料：照探路走出來的 waypoint（直接 36,50 會卡在 31,60；不能再合併：點擊會落在上排 UI）
HOSP_STAND = (38, 40)                                            # 隊長站位（2026-10-17 使用者定案；組隊後隊員落在 MEMBER_SPOT）
MEMBER_SPOT = (38, 47)                                           # 隊長在 38,40 快速組隊後 4 個隊員的落點（實測 1 次；隊長 38,48 時是 38,54 → 推測 = 隊長身後約 7 格）
DAILY_NPC = (41, 42)
NPC_FALLBACK_XY = (651, 197)                                     # = walk.npc_screen(DAILY_NPC, MEMBER_SPOT)：隊員座標讀不到時點這裡（實測 4 人一擊開面板）
HOSP_PATH = [HOSP_ENTRY] + HOSP_WAYPOINTS                         # 入口 → 站位的折線（hosp_route 找「目前在哪一段」）
# 固定點擊路線（play-p1-route 2026-10-17 實測；截圖座標，每段 = 點地面 + waitstill 4000，整串一個 seq、段 2 起 ifok；route_seq 組字串）：
#   村子傳送落點 92,99 → 醫院入口：= heal.VILLAGE_FAST 逐段位移（最後一段用 waitpix 醫院畫面 + HUD 結束）
#   換圖後再 PRIMER → 醫院 25,65 → 38,40 五段（落點 26,65 時第 1 段同點也到 31,60）
#   整串 19.2～19.4 秒（3 次都沒退慢速）；只走醫院段約 9.6 秒。最後讀一次座標，不是站位才 hosp_route 逐段 step_to
VILLAGE_CLICK_ROUTE = [(459, 456), (427, 249), (427, 295), (427, 249), (427, 295)]
HOSP_CLICK_ROUTE = [(747, 157), (875, 295), (619, 249), (491, 249), (459, 226)]
CLICK_ROUTE_WAIT_MS = 4000
VILLAGE_HOSP_EXIT = (81, 66)                                     # 村子 → 醫院的出口格（= heal.VILLAGE_FAST 最後一點；不在傳送點時 walk.walk_to 用）
SAM_EXIT = (10, 25)                                              # 便利商店 1009 → 村子 1000:106,91 的出口格（psa.py route）
POS_SETTLE_S = 1.5                                               # 切角色後 HUD 座標慢半拍（≥3 秒才準）：隔這麼久連讀兩次一樣才採用
REGROUP_MODES = ('pull', 'gather')                               # 買完回醫院：pull = 隊長一人走回 38,40 再快速組隊把隊員拉過來（預設，使用者定案；
REGROUP_DEFAULT = 'pull'                                         #   play-p1-route 實測隊員在 2009 也被拉到 1005:38,47）；gather = 先在店內組隊再帶隊走（保留的備援，預設不用）


def route_steps(clicks, first_ifok: bool = False, end_sig: str = '') -> list:
    """固定點擊 → seq 指令：每段 click + waitstill CLICK_ROUTE_WAIT_MS；第 2 段起（或 first_ifok）加 ifok（上一段沒走動就跳過後面，免得越點越偏）；
    end_sig = 最後一段改 waitpix 這個特徵（換地圖那段：醫院畫面 + HUD）"""
    out = []
    for i, (x, y) in enumerate(clicks):
        k = 'ifok ' if (i or first_ifok) else ''
        out.append(f'{k}click {x} {y}')
        out.append(f'{k}waitpix 5000 {end_sig} 25' if end_sig and i == len(clicks) - 1 else f'{k}waitstill {CLICK_ROUTE_WAIT_MS}')
    return out


def route_seq(primer: str, village: bool, hosp_sig: str = '') -> str:
    """一個 seq 的固定點擊路線字串。village=True：傳送落點 92,99 → 村子 5 段（最後 waitpix hosp_sig）→ ifok PRIMER → 醫院 5 段（全 ifok）；
    village=False：PRIMER → 醫院 25,65 / 26,65 起 5 段"""
    parts = [primer]
    if village:
        parts += route_steps(VILLAGE_CLICK_ROUTE, end_sig=hosp_sig)
        parts += ['ifok ' + c.strip() for c in primer.split(';')]
        parts += route_steps(HOSP_CLICK_ROUTE, first_ifok=True)
    else:
        parts += route_steps(HOSP_CLICK_ROUTE)
    return '; '.join(parts)
MARINAS_XY = (553, 625)                                          # 傳送面板尼斯大陸分頁的「瑪麗娜絲」→ 2000:65,58（ui/transfer.md）
SAM_WALK = (1000, 106, 91)                                       # 薩村 → 1009 出口
FISH_WALK = (2000, 73, 103)                                      # 瑪麗娜絲 → 2009 出口（快速走路卡 67,90 → walk 自動慢速）
NAME_BOXES = [(382, 236, 240, 36), (382, 340, 240, 36)]          # 第 1 / 2 項名稱（x386～、y242～268 / 346～372；寬 200 會切掉「肉丸」的丸）
NAME_OPTS = ('-Zooms', '2,3,4,5', '-Dark', '0')                   # 褐字米色底：不二值化，4 倍率逐倍率 snap 投票（dp.vote_lines；離線 50/50，2026-10-17）
# 委託面板的基本特徵（不含兩顆藍色合成鈕）：最後一環提交後面板沒有合成鈕，uikit.DAILY 不中（2026-10-17 play-p1-daily5）
DAILY_BASE = uikit.Panel('DAILY', None, uikit.DAILY.sig[:-2], uikit.DAILY.close_xy, forbidden=uikit.DAILY.forbidden)
POP_WAIT_N = 18                                                  # 點合成後等快速合成彈窗：18 × 0.25 秒 + 失敗前再 1 秒重檢
MERGE_XY = [(735, 265), (735, 370)]                              # 兩顆「合成」藍鈕
STATE_PX = [(390, 291), (390, 396)]                              # 兩項計數「0」紅字像素（舊單點；只留給文件 / 測試對照，判色改用 STATE_GRID）
# 兩項計數第一個字的字區格點（x 386～402、y 285～299 每 2 點，各 9×8 = 72 點）→ dp.count_area。
# 紅「0」量過 x 390～398 × y 284～299（dp-*.png 30 張）；綠「1/1」沒有實機樣本（2026-10-17），單點 390 可能落在「1」細筆畫外 → 用字區（dev-pop-live）
STATE_GRID = [[(x + dx, y + dy) for dy in range(-6, 9, 2) for dx in range(-4, 13, 2)] for x, y in STATE_PX]
PAGE_BOX = (520, 672, 70, 45)                                    # 頁碼「n/5」
PREV_XY, NEXT_XY = (363, 692), (745, 692)
GOTO_PAGE_TRIES = 8                                               # goto_page 最多幾輪（每輪讀一次頁碼 + 翻一頁 / 確認）
SUBMIT_XY = (1015, 685)
REWARD_BOX = (960, 350, 110, 45)                                 # 「完成所有任務額外獎勵」計數 n/5（綠字 986～1044 × 358～387）
POP_NAME_BOX = (380, 398, 204, 50)                               # 彈窗成品名黃字（置中 x≈481、y 415～431；8 字「精心燉煮過的肉丸」404～557，框容得下 item-book 最長 10 字名；
                                                                 #   離線 99 張 0 誤認：舊框 392,404,180,38 97/99、加寬但不加高的框掉到 83～89，2026-10-17 第二輪）
POP_NAME_TRIES, POP_NAME_WAIT = 3, 0.5                          # 大字投票讀不出 → 只重讀大字（最多 3 次、隔 0.5 秒）：p1 2026-10-17 20:09 229 彈窗剛開大字 4 倍率全空、
                                                                 #   同一彈窗 20:12 實機圖（材料 1/1 綠）用同參數讀得出且字色與舊樣本相同（黃字黑邊，不是白字）→ 推測剛開時還沒畫好 / OCR 逾時回空
# 彈窗大字專用：ocr.ps1 -Small 1 = 先縮成 gui shot 同一張 1440 縮圖再裁（2026-10-17 dev-pop-live 修 229 根因）。
# 實機 ocr.ps1 預設從客戶區原生 2880 裁框縮放，-Image 讀的是 1440 截圖：20:24 現場圖 -Image 讀得出「合成弓箭8」，實機重讀 3 次全空；
# 把截圖放大 2 倍模擬原生 → 3/4/5 倍全掉（同 2e224bc numglyph px vs spixel）。加 -Small 後實機取像 = 存證截圖 = 離線樣本。
POP_NAME_OPTS = NAME_OPTS + ('-Small', '1')
POP_LIST_BOX = (686, 228, 234, 402)                              # 彈窗材料列整欄一次讀（每行帶 y → dp.pop_rows 分列；視野 y 228～630、列距 92；99 張 0 誤認）
POP_DOWN_PX = [(812, 626), (820, 626), (828, 626)]               # 材料列下緣黃 ▼（還有更多列；5 種材料 + 石幣要捲）
POP_UP_PX = [(812, 242), (820, 242), (828, 242)]                 # 材料列上緣黃 ▲（拖過後才出現；短清單也會冒、會蓋住第 1 列右半）
POP_SCROLL = (820, 520, 820, 280)                                # 材料列內往上拖一次 → 捲到底（play p1 2026-10-17 樣本手勢）
POP_SCROLL_MS = 1800                                             # 拖完等慣性停（樣本等 1.8 秒）
POP_COUNT_PX = [(695, 287), (695, 378), (695, 470), (695, 562)]  # 彈窗前 4 列計數（紅 0/1 = 不足；石幣列是綠 1000；第 5 列材料要捲才看得到，不檢查）
POP_CRAFT_XY = (480, 552)
STONE = '裝備升級石'                                              # 5/5 獎勵（Item 93016）
SHOP_STAND_DX = -2                                               # 店員 (27, y) 前 2 格站 (25, y)；點 NPC 會自己走近

def hosp_route(p) -> tuple:
    """（隊長）走到醫院站位 38,40 的備援（固定點擊路線沒到時）：依目前位置算還要走的 waypoint，**不回頭重走**（從 38,48 重走 31,60 會卡 35,54～35,55）。
    回 (要先走進醫院 bool, [剩下的 waypoint])。
      p 讀不到 / 不在醫院 1005 → (True, 全部 waypoint)（呼叫端先 heal.walk_village 進醫院，入口 25,65）
      已在站位 38,40 或離委託 NPC 3 格內 → (False, [])（點得到 NPC，不走）
      在醫院 → 找離 p 最近的折線段（入口 → 31,60 → 36,60 → 38,55 → 38,48 → 38,40），從該段終點的 waypoint 開始；離 p 1 格內的 waypoint 視為已到"""
    if not p or p[0] != HOSPITAL:
        return True, list(HOSP_WAYPOINTS)
    x, y = p[1], p[2]
    if at_stand(p):
        return False, []
    best, bi = None, 0
    for i in range(len(HOSP_PATH) - 1):
        (ax, ay), (bx, by) = HOSP_PATH[i], HOSP_PATH[i + 1]
        dx, dy = bx - ax, by - ay
        t = max(0.0, min(1.0, ((x - ax) * dx + (y - ay) * dy) / float(dx * dx + dy * dy)))
        d = (x - (ax + t * dx)) ** 2 + (y - (ay + t * dy)) ** 2
        if best is None or d < best - 2.0:                     # 差距不大取靠前的段（偏保守：多經過一個 waypoint，不會從卡點直奔下下個）
            best, bi = d, i
    rest = HOSP_WAYPOINTS[bi:]
    while len(rest) > 1 and max(abs(rest[0][0] - x), abs(rest[0][1] - y)) <= 1:
        rest = rest[1:]
    return False, list(rest)


def at_stand(p) -> bool:
    """p 是醫院站位 38,40 或離委託 NPC 3 格內（隊長不用再走）"""
    return bool(p) and p[0] == HOSPITAL and ((p[1], p[2]) == HOSP_STAND or max(abs(p[1] - DAILY_NPC[0]), abs(p[2] - DAILY_NPC[1])) <= 3)


MAT_PRICE_TXT = f'{dp.MAT_PRICE:,}'
LAST: dict = {}


_RECIPES: dict = {}


def _recipes() -> dict:
    """配方表（Tools.craft_item 核對彈窗用；只讀一次）"""
    if not _RECIPES:
        _RECIPES.update(dp.load_recipes())
    return _RECIPES


def event(msg: str) -> None:
    line = f'{time.strftime("%Y-%m-%d %H:%M:%S")} [daily] {msg}'
    print(line, flush=True)
    try:
        EVENT_LOG.parent.mkdir(parents=True, exist_ok=True)
        with open(EVENT_LOG, 'a', encoding='utf-8') as f:
            f.write(line + '\n')
    except OSError:
        pass


# ======================================================================================
# 碰遊戲的動作（既有工具的薄包裝；離線測試換成 FakeTools）
# ======================================================================================
class Tools:
    # ---- 一般 ----
    def preflight(self):
        return uikit.preflight(SRC)

    def sleep(self, s):
        uikit.sleep(s)

    def lock(self) -> bool:
        """持 grind.lock：grind.run / netwatch 的 grind ensure 看到鎖就不搶畫面（結束 / finish 前 unlock）"""
        import grind
        return grind.take_lock()

    def unlock(self) -> None:
        import grind
        grind.release_lock()

    def stop_follow(self) -> bool:
        import grind
        return grind.stop_follow('每日任務（要離開練功點、解散隊伍）')

    def encounter_off(self) -> None:
        import heal
        heal.set_encounter(False)
        heal.gui('seq', f'waitpix 30000 {heal.SIG_NO_BATTLE} 40')

    def pos(self):
        import walk
        return walk.pos()

    def wait_map(self, map_id, tries=10) -> bool:
        import walk
        p = walk.wait_pos(tries, map_id, 0.6)
        return bool(p and p[0] == map_id)

    def to_town(self) -> bool:
        """城鎮傳送薩姆吉爾（1000:92,99）；heal.teleport 內建重試"""
        import heal
        try:
            heal.teleport(heal.TAB_TOWN, heal.SAMUGIL, heal.VILLAGE, '薩姆吉爾', want_xy=heal.VILLAGE_START)
        except RuntimeError as e:
            print(f'{SRC}：{e}', file=sys.stderr)
            return False
        return True

    def to_marinas(self) -> bool:
        import heal
        try:
            heal.teleport(heal.TAB_TOWN, MARINAS_XY, MARINAS_MAP, '瑪麗娜絲')
        except RuntimeError as e:
            print(f'{SRC}：{e}', file=sys.stderr)
            return False
        return True

    def close_panels(self) -> list:
        """切角色前一定先關面板（2026-10-17 使用者）：便利店 ✕ → char.clear_panels（快速合成彈窗 / 委託面板 / 背包等已知面板，點 ✕）。回關掉的名字"""
        import char
        shut = ['shop'] if shopkit.shop_open() and shopkit.close_shop(2) else []
        if self.daily_open_any():                              # 5/5 後面板長相變了（藍色合成鈕消失）→ uikit.DAILY 特徵不中、char.clear_panels 認不得（2026-10-17 play-p1-daily5）
            self.daily_close()
            shut.append('daily')
        return shut + char.clear_panels()

    def ensure(self, role) -> int:
        import char
        return char.ensure(role)

    def switch(self, role) -> int:
        """char.switch（switch 內也會先關已知面板、驗證不對重試一次；面板開著時以前會切不成，play-p1-daily2）"""
        import char
        return char.switch(role)

    def form(self) -> int:
        """快速組隊（已組好 = 0 不點；不完整隊伍 → 解散重組 regroup=True：續跑時隊伍狀態不明也接得上）"""
        import team
        return team.form(LEADER, len(ROLES), regroup=True)

    def disband(self) -> int:
        import team
        rc = team.disband()
        if rc == 40:                                           # 切換面板剛換地圖後第一下常打不開（buywendy 2026-10-15 實機）→ 等一下再來一次
            uikit.sleep(2.0)
            rc = team.disband()
        return rc

    # ---- 走路 ----
    def walk_to(self, map_id, x, y, exit_map=None) -> bool:
        import walk
        try:
            walk.walk_to(map_id, x, y, exit_map=exit_map)
        except RuntimeError as e:
            if exit_map is not None and self.wait_map(exit_map, 3):   # 走路回報卡在中間座標、其實已進目標地圖（play-p1-daily5：2000:73,103 → 2009:21,35）→ 算成功
                event(f'daily 走到 {map_id}:{x},{y} 回報失敗（{e}），但現在已在地圖 {exit_map} → 算成功')
                return True
            print(f'{SRC}：走到 {map_id}:{x},{y} 失敗：{e}', file=sys.stderr)
            return False
        return True

    def click_route(self, village: bool):
        """送一個 seq 的固定點擊路線（route_seq）→ 讀一次座標回傳（讀不到 None）"""
        import heal
        import walk
        walk.gui('seq', route_seq(walk.PRIMER, village, f'{heal.SIG_HUD}/{heal.SIG_HOSPITAL}'),
                 note=f'daily 固定點擊路線（{"傳送落點 → 醫院 38,40" if village else "醫院入口 → 38,40"}）')
        return walk.wait_pos(4)

    def hosp_solo(self) -> bool:
        """（當前 = 隊長）自己走到醫院站位 38,40（2026-10-17 使用者定案；組隊中就帶著隊伍走，沒組就一個人走）：
          便利商店 1009 → 走出口 10,25 回村；不在村子 / 醫院（瑪麗娜絲 2000 / 2009、練功點…）→ 城鎮傳送薩姆吉爾（落點 92,99）
          在傳送落點 92,99 → 一個 seq 走完村子 + 醫院（route_seq，約 19 秒）；村子別處 → walk.walk_to 出口 81,66 進醫院
          醫院入口 25,65 / 26,65 → 醫院段固定點擊 5 段；最後讀一次座標，不是站位才 hosp_route 逐段 step_to"""
        import heal
        import walk
        try:
            p = walk.wait_pos(4)
            if p and p[0] == dp.SAM_MAP:
                walk.walk_to(dp.SAM_MAP, *SAM_EXIT, exit_map=VILLAGE)
                p = walk.wait_pos(4, VILLAGE)
            if not p or p[0] not in (VILLAGE, HOSPITAL):
                if not self.to_town():
                    return False
                p = walk.wait_pos(4, VILLAGE)
            if p and p[0] == VILLAGE and (p[1], p[2]) == heal.VILLAGE_START:
                p = self.click_route(True)
            if p and p[0] == VILLAGE:                         # 不在傳送落點，或整串路線沒進醫院
                walk.walk_to(VILLAGE, *VILLAGE_HOSP_EXIT, exit_map=HOSPITAL)
                p = walk.wait_pos(4, HOSPITAL)
            if not p or p[0] != HOSPITAL:
                print(f'{SRC}：沒進醫院（現在 {p}）', file=sys.stderr)
                return False
            if (p[1], p[2]) in (HOSP_ENTRY, HOSP_IN):
                p = self.click_route(False) or walk.wait_pos(4, HOSPITAL)
            if at_stand(p):
                return True
            print(f'{SRC}：醫院固定點擊路線沒到 {HOSP_STAND}（現在 {p}）→ 逐段 step_to', file=sys.stderr)
            _, route = hosp_route(p)
            for wx, wy in route:
                walk.step_to(HOSPITAL, wx, wy)
            p = walk.wait_pos(4, HOSPITAL)
        except RuntimeError as e:
            print(f'{SRC}：走到醫院站位失敗：{e}', file=sys.stderr)
            return False
        return at_stand(p)

    def talk(self, npc, at, then='') -> bool:
        """點 NPC → 輪詢對話框 → then；剛走到第 1 下常被吃掉，最多 3 次"""
        import walk
        for _ in range(3):
            if walk.talk_npc(npc, at, then=then):
                return True
        return False

    # ---- 委託面板 ----
    def settled_pos(self):
        """切角色後 HUD 座標慢半拍（play-p1-daily2：切完約 3 秒才準）→ 隔 POS_SETTLE_S 連讀到兩次一樣才採用（最多 4 次；仍不一致回最後一次）"""
        import walk
        last = None
        for i in range(4):
            p = walk.wait_pos(3)
            if p and p == last:
                return p
            last = p
            if i < 3:
                uikit.sleep(POS_SETTLE_S)
        return last

    def daily_open(self, may_walk: bool = False) -> bool:
        """點委託接取 NPC 開面板（2026-10-17 使用者定案：組隊不解散，隊員不走路直接點）。
        點位 = walk.npc_screen(DAILY_NPC, 讀到的座標)（settled_pos）；讀不到 / 點位落在 UI 上 / 離 NPC > 8 格 →
        may_walk（隊長）先 step_to 站位 38,40 再點；隊員用 38,47 的 NPC_FALLBACK_XY 651,197（不在醫院 → False，隊員不自己走）。
        點 → 等面板特徵；沒開再點一次（共 2 次；進醫院後右側小框會吃第一下）"""
        import walk
        for _ in range(2):
            if uikit.is_open(uikit.DAILY):
                return True
            p = self.settled_pos()
            xy = None
            if p and p[0] == HOSPITAL:
                at = (p[1], p[2])
                cand = walk.npc_screen(DAILY_NPC, at)
                if walk.safe(*cand) and max(abs(at[0] - DAILY_NPC[0]), abs(at[1] - DAILY_NPC[1])) <= 8:
                    xy = cand
            elif p:
                print(f'{SRC}：點委託 NPC 時不在醫院（{p}）', file=sys.stderr)
                return False
            if xy is None and may_walk:
                try:
                    walk.step_to(HOSPITAL, *HOSP_STAND)
                except RuntimeError as e:
                    print(f'{SRC}：走回 {HOSP_STAND} 失敗：{e}', file=sys.stderr)
                    return False
                xy = walk.npc_screen(DAILY_NPC, HOSP_STAND)
            if xy is None:
                xy = NPC_FALLBACK_XY
            uikit.gui('seq', f'click {xy[0]} {xy[1]}; wait 700', note=f'daily 點委託接取 NPC（站 {p}）')
            for _i in range(8):
                if uikit.is_open(uikit.DAILY):
                    return True
                uikit.sleep(0.2)
        return uikit.is_open(uikit.DAILY)

    def daily_open_any(self) -> bool:
        """委託面板或快速合成彈窗開著（含 5/5 後沒有藍色合成鈕的面板：用 DAILY_BASE 特徵）"""
        return uikit.is_open(uikit.QCRAFT) or uikit.is_open(DAILY_BASE)

    def daily_close(self) -> bool:
        """✕ 關面板（先關快速合成彈窗）；絕不點空白處。用 DAILY_BASE（不看藍色合成鈕）判開著：
        最後一環提交後面板沒有合成鈕，uikit.DAILY 特徵不中 → 以前判「沒開」不關 → 切角色 rc 9（play-p1-daily5）。回是否已全關"""
        for _ in range(2):
            if uikit.is_open(uikit.QCRAFT):
                uikit.safe_click(*uikit.QCRAFT.close_xy, uikit.QCRAFT, note='daily 關快速合成彈窗', wait_ms=500)
            if uikit.is_open(DAILY_BASE):
                uikit.close_panel(DAILY_BASE, known_open=True)
            if not self.daily_open_any():
                return True
        return False

    def panel_open(self) -> bool:
        return uikit.is_open(uikit.DAILY)

    def page_no(self):
        """頁碼「n/5」：各倍率各自 parse、一致才收（dp.page_vote）；讀不出 / 不一致 → None"""
        return dp.page_vote(uikit.ocr_lines(PAGE_BOX, '-Zooms', '2,3'))

    def goto_page(self, page: int) -> bool:
        """翻到第 page 頁且**讀頁碼確認**才回 True（2026-10-17 dev-shop-title 修 mid 229：翻頁 4 → 5 後立刻讀成 5、面板其實停在 4/5 → 點到別環 → 彈窗沒開）。
        讀到 page → 等 0.4 秒再讀一次也是 page 才算到（翻頁動畫 / 漏點）；讀到別頁 → 照差距點上 / 下一頁（每次 wait 600 後重讀）；
        連 2 次讀不出 → 盲翻一次（上一頁 4 次到第 1 頁〔第 1 頁再按假設夾住〕再下一頁 page-1 次）後照樣要讀到頁碼確認。
        最多 GOTO_PAGE_TRIES 輪仍不確定 → False（呼叫端 229「翻不到第 N 頁」），log 寫各次讀值"""
        seen, miss, blind = [], 0, False
        for _ in range(GOTO_PAGE_TRIES):
            cur = self.page_no()
            seen.append(cur)
            if cur == page:
                self.sleep(0.4)
                again = self.page_no()
                seen.append(again)
                if again == page:
                    return True
                continue
            if cur is None:
                miss += 1
                if miss >= 2 and not blind:
                    blind = True
                    event(f'daily 頁碼讀不出 → 盲翻到第 {page} 頁')
                    for _i in range(dp.RINGS - 1):
                        if not uikit.safe_click(*PREV_XY, uikit.DAILY, note='daily 盲翻：上一頁', wait_ms=400):
                            return False
                    for _i in range(page - 1):
                        if not uikit.safe_click(*NEXT_XY, uikit.DAILY, note='daily 盲翻：下一頁', wait_ms=400):
                            return False
                else:
                    self.sleep(0.5)
                continue
            miss = 0
            x, y = NEXT_XY if cur < page else PREV_XY
            if not uikit.safe_click(x, y, uikit.DAILY, note=f'daily 翻頁 {cur} → {page}', wait_ms=600):
                return False
        event(f'daily 翻不到第 {page} 頁（頁碼各次讀值 {seen}）')
        return False

    def next_page(self) -> bool:
        return uikit.safe_click(*NEXT_XY, uikit.DAILY, note='daily 下一頁', wait_ms=500)

    def read_page(self) -> dict:
        """目前頁：{'names': [OCR 原始行 ×2（uikit.ocr_lines，多倍率）], 'states': ['red'|'green'|'?' ×2]}（呼叫端 dp.vote_lines 逐倍率投票）"""
        names = [uikit.ocr_lines(box, *NAME_OPTS) for box in NAME_BOXES]
        return {'names': names, 'states': self.item_states()}

    def peek_item(self, k: int, panel: dict | None = None) -> dict:
        """名稱不確定時：開該項快速合成彈窗讀成品名大字 + 材料列（不按彈窗合成）→ 關彈窗。
        ▼ 亮（材料 4 種以上、第一眼看不全）且第一眼還分不出（dp.resolve_name None）→ 材料列內捲一次再讀（pop_scroll）。
        panel = 面板名稱的 dp.vote_lines 結果（判斷要不要捲）。回 pop dict（呼叫端 dp.resolve_name + dp.pop_mats）；彈窗沒開 → {'name': [], 'list': []}"""
        out = {'name': [], 'list': []}
        if not uikit.safe_click(*MERGE_XY[k], uikit.DAILY, note=f'daily 開第 {k + 1} 項快速合成（讀名稱）', wait_ms=700):
            return out
        for _ in range(6):
            if uikit.is_open(uikit.QCRAFT):
                out = self.pop_read()
                rc = _recipes()
                if out.get('down') and dp.resolve_name(panel or dp.vote_lines([], rc), dp.vote_lines(out['name'], rc), dp.pop_mats(out, rc), rc) is None:
                    self.pop_scroll(out)
                break
            uikit.sleep(0.2)
        if uikit.is_open(uikit.QCRAFT):
            uikit.safe_click(*uikit.QCRAFT.close_xy, uikit.QCRAFT, note='daily 關快速合成彈窗', wait_ms=500)
        return out

    def pop_read(self) -> dict:
        """（快速合成彈窗開著，剛開、還沒捲）成品名大字 + 材料列整欄的 OCR 原始行 + ▼ / ▲（dp.pop_mats / pop_check 吃這個 dict）"""
        cols = uikit.px(POP_DOWN_PX + POP_UP_PX) or []
        n = len(POP_DOWN_PX)
        return {'name': self.pop_name(), 'list': uikit.ocr_lines(POP_LIST_BOX, *NAME_OPTS),
                'down': dp.arrow_on(cols[:n]), 'up': dp.arrow_on(cols[n:])}

    def pop_name(self) -> list:
        """彈窗成品名大字 OCR 原始行；dp.vote_lines 投不出名字就等 POP_NAME_WAIT 秒重讀，最多 POP_NAME_TRIES 次（彈窗不在就不重讀）。
        回最後一次的原始行（pop_check 照舊要大字證據，不放寬）"""
        known = _recipes()
        for i in range(POP_NAME_TRIES):
            lines = uikit.ocr_lines(POP_NAME_BOX, *POP_NAME_OPTS)
            if dp.vote_lines(lines, known)['name'] or i == POP_NAME_TRIES - 1 or not uikit.is_open(uikit.QCRAFT):
                return lines
            uikit.sleep(POP_NAME_WAIT)
        return []

    def pop_scroll(self, pop: dict) -> dict:
        """材料列內往上拖一次（捲到底）→ 等 1.8 秒 → 再讀材料列，存進 pop['list2'] / pop['up2']（dp.pop_mats 依序合併兩張）。彈窗不在就不拖"""
        if not uikit.is_open(uikit.QCRAFT):
            return pop
        uikit.gui('seq', 'drag {} {} {} {}; wait {}'.format(*POP_SCROLL, POP_SCROLL_MS), note='daily 快速合成材料列捲一次')
        pop['list2'] = uikit.ocr_lines(POP_LIST_BOX, *NAME_OPTS)
        pop['up2'] = dp.arrow_on(uikit.px(POP_UP_PX))
        return pop

    def reward_count(self):
        return dp.parse_reward(''.join(uikit.ocr(REWARD_BOX, '-Zooms', '2,3')))

    def craft_item(self, k: int, name: str) -> tuple:
        """第 k 項快速合成：開彈窗 → 大字只防點錯項（讀空放行）→ 材料計數不是紅字 → 彈窗「合成」（花 1000 石幣）→ 關彈窗 → 該項變綠。回 (ok, 原因)"""
        if not uikit.safe_click(*MERGE_XY[k], uikit.DAILY, note=f'daily 開第 {k + 1} 項快速合成「{name}」', wait_ms=700):
            return False, '委託面板不在，沒點'
        for _ in range(POP_WAIT_N):                            # 彈窗有時 4 秒才浮出（play-p1-daily5 DKBO3 第 2 環 229）→ 輪詢到約 4.5 秒
            if uikit.is_open(uikit.QCRAFT):
                break
            uikit.sleep(0.25)
        else:
            if not uikit.is_open(uikit.QCRAFT):                # 失敗前再等一下重檢一次
                uikit.sleep(1.0)
            if not uikit.is_open(uikit.QCRAFT):
                return False, '快速合成彈窗沒開'

        def close_pop():
            uikit.safe_click(*uikit.QCRAFT.close_xy, uikit.QCRAFT, note='daily 關快速合成彈窗', wait_ms=500)
        # 成品名大字只寫 log + 防點錯項：讀空 / 讀不出一律放行（2026-10-17：實機大字一直讀空 → mid 229；
        # 點的是面板第 k 項的合成鈕，彈窗必然是那一項，名字 read 段已核對過）。不讀材料列、不捲動
        lines = uikit.ocr_lines(POP_NAME_BOX, *POP_NAME_OPTS)
        gv = dp.vote_lines(lines, _recipes())
        event(f'daily 合成「{name}」彈窗大字 {gv["texts"]} → {gv["name"] or "讀不出（放行）"}')
        other = dp.pop_wrong(name, lines, _recipes())
        if other:
            shot = uikit.snap('daily-pop-fail')                   # 明確是別的成品 → 點錯項，不合成
            close_pop()
            return False, f'彈窗大字明確是別的成品「{other}」（要合成「{name}」，沒合成；現場圖 {shot}）'
        if dp.popup_short(uikit.px(POP_COUNT_PX)):
            close_pop()
            return False, '彈窗材料計數有紅字（材料不足，沒合成）'
        if not uikit.safe_click(*POP_CRAFT_XY, uikit.QCRAFT, note=f'daily 合成「{name}」（1000 石幣）', allow=('craft',), wait_ms=1200):
            return False, '彈窗特徵不在，沒按合成'
        close_pop()
        for _ in range(8):
            if uikit.is_open(uikit.DAILY) and self.item_states()[k] == 'green':
                return True, ''
            uikit.sleep(0.3)
        return False, '合成後該項沒變綠'

    def submit(self) -> bool:
        return uikit.safe_click(*SUBMIT_XY, uikit.DAILY, note='daily 提交委託', allow=('submit',), wait_ms=1500)

    def item_states(self) -> list:
        """兩項計數 → ['red'|'green'|'?' ×2]：字區格點（STATE_GRID）一次取色、dp.count_area 判"""
        n = len(STATE_GRID[0])
        cols = uikit.px([p for g in STATE_GRID for p in g]) or []
        if len(cols) != n * len(STATE_GRID):
            return ['?'] * len(STATE_GRID)
        return [dp.count_area(cols[i * n:(i + 1) * n]) for i in range(len(STATE_GRID))]

    # ---- 便利店 ----
    def shop_enter(self, store) -> bool:
        """走到店員前 2 格 → 點店員 → 「道具商店」→ 等便利店面板（最多 3 輪）"""
        stand = (store.x + SHOP_STAND_DX, store.y)
        if not self.walk_to(store.map, *stand):
            return False
        for _ in range(3):
            if not self.talk((store.x, store.y), stand, then=f'click {shopkit.SHOP_BTN[0]} {shopkit.SHOP_BTN[1]}'):
                continue
            for _i in range(8):
                if shopkit.shop_open():
                    return True
                uikit.sleep(0.4)
        return False

    def shop_select(self, name, store, state) -> bool:
        return shopkit.select_item(name, store.items, state, log=event)

    def shop_set_qty(self, q, start=None) -> bool:
        return shopkit.set_qty(q, start=start)

    def shop_chunks(self, q):
        return shopkit.qty_chunks(q)

    def shop_buy_checked(self, n) -> str:
        return shopkit.buy_checked(n, log=event)

    def shop_close(self) -> bool:
        return shopkit.close_shop()

    # ---- 背包 / 倉庫 ----
    def bag_check(self, role, names) -> tuple:
        """背包名稱核對：回 (找不到的名稱 list, 沒認出的格數)。bag.Session 開關背包"""
        import bag
        with bag.Session() as s:
            if s.rc:
                return list(names), -s.rc
            rc = bag.select_role(role)
            if rc:
                return list(names), -rc
            r = bag._names_in_bag(list(names))
        return [n for n in names if r['found'].get(n) is None], len(r.get('unread') or [])

    def depot_store(self, role, name, sub) -> int:
        import bag
        return bag.depot_store(role, name, depot=sub)

    def depot_take(self, role, name, sub) -> int:
        import bag
        return bag.depot_take(role, name, depot=sub)

    def depot_store_many(self, role, items, on_item=None) -> tuple:
        """批次存倉（一個 Session、分頁只切一次）：items = [(遊戲名, sub)] → (rc, {名: rc})"""
        import bag
        return bag.depot_store_many(role, items, on_item=on_item)

    def depot_take_many(self, role, items, on_item=None) -> tuple:
        """批次取倉：items = [(遊戲名, sub)] → (rc, {名: rc})"""
        import bag
        return bag.depot_take_items(role, items, on_item=on_item)

    # ---- 收尾 ----
    def cleanup(self) -> None:
        """失敗收尾：關快速合成 / 委託面板 / 便利店（都用 ✕）；不認得的畫面不碰"""
        try:
            self.daily_close()
            shopkit.close_shop(2)
        except Exception:                                      # noqa: BLE001
            pass

    def grind_go(self) -> int:
        import grind
        return grind.go()


# ======================================================================================
# 流程
# ======================================================================================
class Stop(Exception):
    def __init__(self, rc: int, msg: str):
        super().__init__(msg)
        self.rc, self.msg = rc, msg


class Daily:
    def __init__(self, T, o: dict, roles: list, recipes=None, stores=None, where=None):
        self.T, self.o, self.roles = T, o, list(roles)
        self.recipes = recipes if recipes is not None else dp.load_recipes()
        if stores is None or where is None:
            stores, where = dp.load_stores()
        self.stores, self.where = stores, where
        self.zeroish = set()                                   # {(角色, 材料)}：數量框歸 0 但字認不出的購買（背包核對才是硬閘）
        order = [r for r in clients.leader_last() if r in self.roles] or list(self.roles)
        self.order = order                                     # DKBO2 → … → DKBO（隊長最後）
        self.leader = LEADER if LEADER in self.roles else self.order[-1]
        self.info = {}
        self.team = {}
        self.st = {}                                           # role → 進度 dict

    # ---- 共用 ----
    def fail(self, rc, msg, **kw):
        self.info.update(kw)
        raise Stop(rc, msg)

    def tool_fail(self, tool_rc, my_rc, msg, **kw):
        """工具回 8 / 9 / 10 → 原碼；其他 → 本檔對應碼"""
        self.fail(tool_rc if tool_rc in PASS else my_rc, msg, **kw)

    def save_role(self, role):
        dp.save(dp.role_path(role), self.st[role])

    def save_team(self):
        dp.save(dp.team_path(), self.team)

    def check_day(self):
        if not dp.check_date(self.team):
            self.fail(EXIT_ARGS, f'跨過 00:00（進度檔日期 {self.team.get("date")}，現在 {dp.today()}）：遊戲環數已清 0，停手；人看過再決定 --fresh', crossed=True)

    def plan_of(self, role) -> dict:
        return role_plan(self.st[role], self.recipes, self.where, self.stores)

    def role_complete(self, role) -> bool:
        st = self.st[role]
        if st.get('reward') == dp.RINGS:
            return True
        if not st.get('items'):
            return False
        plan = self.plan_of(role)
        return all(st['rings'][r['ring'] - 1].get('submitted') for r in plan['rings'] if r['supported']) and bool(plan['supported_rings'])

    def switch_to(self, role):
        self.T.close_panels()                                  # 切角色前一定先關面板（2026-10-17 使用者；char.switch 內也會再關一次）
        rc = self.T.switch(role)
        if rc:
            self.tool_fail(rc, EXIT_PREP, f'切當前角色到 {role} 失敗（char rc {rc}）', char_rc=rc)

    # ---- 搬移（組隊帶隊走）----
    def leader_current(self):
        self.T.close_panels()
        rc = self.T.ensure(self.leader)
        if rc:
            self.tool_fail(rc, EXIT_PREP, f'當前角色切不到隊長 {self.leader}（char rc {rc}）', char_rc=rc)

    def form_team(self, hint: str = ''):
        rc = self.T.form()
        if rc:
            self.tool_fail(rc, EXIT_PREP, f'組隊失敗（team rc {rc}）{hint}', team_rc=rc)

    def disband_team(self):
        rc = self.T.disband()
        if rc:
            self.tool_fail(rc, EXIT_PREP, f'解散隊伍失敗（team rc {rc}）', team_rc=rc)

    def go_town(self, where_: str):
        """（隊長當前，組隊中 = 全隊一起）→ 傳送到目的地的城鎮（hospital / sam → 薩姆吉爾村；fish → 瑪麗娜絲）。已在該城鎮或目的建築內就不傳"""
        T = self.T
        town = MARINAS_MAP if where_ == 'fish' else VILLAGE
        inside = {'hospital': HOSPITAL, 'sam': dp.SAM_MAP, 'fish': dp.FISH_MAP}[where_]
        p = T.pos()
        if p and p[0] in (town, inside):
            return
        if not (T.to_marinas() if where_ == 'fish' else T.to_town()):
            self.fail(EXIT_PREP, f'傳送{"瑪麗娜絲" if where_ == "fish" else "薩姆吉爾"}失敗')
        T.sleep(1.0)

    def go_spot(self, role, where_: str):
        """（當前角色 = role）走進便利店地圖：sam / fish = 1009 / 2009 店內（店員前由 shop_enter 走）。組隊中隊長走 = 全隊跟著。走不到 → 224（帶座標）"""
        T = self.T
        target = dp.SAM_MAP if where_ == 'sam' else dp.FISH_MAP
        town, walk_ = (VILLAGE, SAM_WALK) if where_ == 'sam' else (MARINAS_MAP, FISH_WALK)
        p = T.pos()
        if p and p[0] == target:
            return
        if not p or p[0] != town:
            if not (T.to_town() if where_ == 'sam' else T.to_marinas()):
                self.fail(EXIT_PREP, f'{role} 傳送{"薩姆吉爾" if where_ == "sam" else "瑪麗娜絲"}失敗', role=role)
            T.sleep(1.0)
        if not T.walk_to(*walk_, exit_map=target):
            self.fail(EXIT_WALK, f'{role} 走不進 {target}（目前 {T.pos()}）', role=role)

    def gather_hospital(self):
        """醫院段開頭（read / mid / final；2026-10-17 使用者定案）：隊長自己走到 1005:38,40（hosp_solo）→ 快速組隊（team.form：已組好不點）→ **不解散**。
        已在站位就不走（續跑 / 上一段已組好）。regroup='gather'（fallback）：隊長出發前先在原地組隊、帶隊走（隊員在別張地圖拉不過來時用）"""
        self.check_day()
        self.leader_current()
        if not at_stand(self.T.pos()):
            if self.o.get('regroup') == 'gather':
                self.form_team()
            if not self.T.hosp_solo():
                self.fail(EXIT_WALK, f'{self.leader} 走不到醫院站位 {HOSP_STAND}（目前 {self.T.pos()}）', role=self.leader)
        self.form_team('' if self.o.get('regroup') == 'gather' else '；隊員在別張地圖拉不過來時改用 --regroup gather（先在店內組隊再帶隊走）')

    def open_daily(self, role):
        """（組隊、當前 = role）不走路直接點委託 NPC 開面板（隊長讀不到可點的點位時才走回 38,40）；打不開 → 224"""
        if not self.T.daily_open(may_walk=(role == self.leader)):
            self.fail(EXIT_WALK, f'{role} 委託面板打不開（目前 {self.T.pos()}）', role=role)

    # ---- 階段 ----
    def stage_prep(self):
        T = self.T
        rc = T.preflight()
        if rc:
            self.tool_fail(rc, EXIT_PREP, f'preflight 失敗（rc {rc}）')
        if not T.lock():
            event('警告：拿不到 grind.lock（netwatch 重登後可能搶畫面）')
        if not T.stop_follow():
            self.fail(EXIT_PREP, 'follow 停不掉（60 秒內沒結束）')
        T.encounter_off()
        self.leader_current()
        self.form_team()                                       # 練功時本來就組著（不點）；沒組的話先組 → 全隊一起傳送
        self.go_town('hospital')

    def stage_read(self):
        if any(not self.st[r].get('read') for r in self.order):
            self.gather_hospital()
        for role in self.order:
            st = self.st[role]
            if st.get('read'):
                continue
            self.check_day()
            self.switch_to(role)
            self.read_role(role)
            self.save_role(role)
            event(f'read {role}：' + ' | '.join(f'{a}/{b}' for a, b in st['items']))
        if all(self.role_complete(r) for r in self.order):
            self.info['all_done'] = True
            self.fail(EXIT_ARGS, '今天所有角色都已完成每日委託（5/5）', all_done=True)

    def read_role(self, role):
        """（當前角色 = role）開面板 → 讀獎勵計數 → 1～5 頁 × 2 項。名稱 snap 不到 → 開快速合成彈窗讀大字再 snap；仍不行 → 225"""
        T, st = self.T, self.st[role]
        self.open_daily(role)
        try:
            st['reward'] = T.reward_count()
            if st['reward'] == dp.RINGS:                        # 今天 5/5 已完成：清單畫面可能不是 5 環 × 2 項，不讀、記成已讀
                st.update(read=True, items=[], done=[])
                return
            if T.page_no() not in (None, 1) and not T.goto_page(1):
                self.fail(EXIT_READ, f'{role} 翻不到第 1 頁')
            items, dones = [], []
            for page in range(1, dp.RINGS + 1):
                pg = T.read_page()
                pair = []
                for k in range(2):
                    v = dp.vote_lines(pg['names'][k], self.recipes)
                    nm = v['name'] if v['sure'] else None       # 單票的數字尾碼（合成爪 7 / 3）不算確定 → 開彈窗核對大字 + 材料列
                    if nm is None:
                        pk = T.peek_item(k, v) or {}
                        nm = dp.resolve_name(v, dp.vote_lines(pk.get('name'), self.recipes), dp.pop_mats(pk, self.recipes), self.recipes)
                    if nm is None:
                        self.fail(EXIT_READ, f'{role} 第 {page} 環第 {k + 1} 項讀不出成品名（OCR 各倍率 {v["texts"]!r} 票 {v["votes"]}，彈窗也不行）', read_page=page)
                    pair.append(nm)
                items.append(pair)
                dones.append([s == 'green' for s in pg['states']])
                if page < dp.RINGS and not T.next_page():
                    self.fail(EXIT_READ, f'{role} 第 {page} 頁後翻不了下一頁')
            st['items'], st['done'], st['read'] = items, dones, True
        finally:
            T.daily_close()

    def stage_plan(self):
        plans = {}
        total = 0
        for role in self.order:
            if self.role_complete(role):
                print(f'{role}：今天已完成 5/5，略過')
                continue
            plan = self.plan_of(role)
            plans[role] = plan
            for ln in dp.plan_lines(role, plan, self.stores, self.where):
                print(ln)
            for r in plan['rings']:
                if not r['supported']:
                    event(f'{role} 第 {r["ring"]} 環跳過：{r["reason"]}')
            total += plan['cost']['total']
        print(f'全隊石幣估算約 {total:,}（材料 {MAT_PRICE_TXT} / 個 + 合成 1,000 / 項；不讀石幣，只供參考）')
        self.info['cost_estimate'] = total
        for role in plans:
            if not plans[role]['supported_rings']:
                self.fail(EXIT_NOROLE, f'{role} 全部環都不支援（見上面各環原因）；不動作', role=role)
        if time.localtime().tm_hour == 23 and time.localtime().tm_min >= 50:
            event('警告：接近 00:00，預計跑不完（遊戲每日 0 點環數清 0）')
        if not self.o.get('confirm_buy'):
            self.fail(EXIT_NOBUY, '買材料 / 合成要花石幣，沒給 --confirm-buy → 不動作（已印計畫）')

    def stage_buy(self, stage: str):
        who = [r for r in self.order if dp.remaining_buy(self.plan_of(r), stage, self.st[r]['bought']) and not self.role_complete(r)]
        if not who:
            event(f'{stage}：沒有人要買 → 跳過')
            return
        self.into_shop(stage, who[0])
        for role in who:
            self.check_day()
            self.switch_to(role)
            self.buy_role(role, stage)
            self.st[role]['stages'][stage] = True
            self.save_role(role)

    def into_shop(self, stage, first_role):
        """便利店段開頭（2026-10-17 使用者定案）：隊長組隊（已組好不點）→ 傳送城鎮 → 帶隊走進店、到第一個要買的人的第一家店員前 → 解散；
        之後每人切角色各自在店內走、買。買完不在這裡回醫院：下一個醫院段（mid / final）的 gather_hospital 由隊長一人走回 38,40 再組隊
        （mid 沒事做被跳過時省一趟；漁村段 hosp_solo 先傳送回薩姆吉爾）"""
        self.check_day()
        self.leader_current()
        self.form_team()
        self.go_town(stage)
        self.go_spot(self.leader, stage)
        plan = self.plan_of(first_role)
        route = dp.store_route(stage, dp.remaining_buy(plan, stage, self.st[first_role]['bought']), self.where, self.stores, plan['first_use'])
        if route:
            store = route[0][0]
            if not self.T.walk_to(store.map, store.x + SHOP_STAND_DX, store.y):
                event(f'{stage}：帶隊走到「{store.name}」店員前沒到（{self.T.pos()}），解散後各自走')
        self.disband_team()

    def evict(self, role, mat):
        """背包 → 個人倉庫（滿 → 公倉並記 in_public）；成功更新 ledger。mat 可以是成品鍵（PRODUCT_PREFIX + 名；遊戲裡用名字存）"""
        T, st = self.T, self.st[role]
        led = dp.Ledger(st['ledger'])
        game = mat[len(dp.PRODUCT_PREFIX):] if mat.startswith(dp.PRODUCT_PREFIX) else mat
        rc = T.depot_store(role, game, 'personal')
        sub = 'personal'
        if rc:
            if rc in PASS:
                self.fail(rc, f'存倉遇到 rc {rc}', bag_rc=rc)
            event(f'{role} 個人倉庫存「{mat}」失敗（bag rc {rc}）→ 改存公共倉庫')
            rc = T.depot_store(role, game, 'public')
            sub = 'public'
            if rc:
                self.tool_fail(rc, EXIT_DEPOT, f'{role}「{mat}」個人倉庫和公共倉庫都存不進（bag rc {rc}）', bag_rc=rc)
        led.evict(mat, sub)
        key = 'in_personal' if sub == 'personal' else 'in_public'
        if mat not in st[key]:
            st[key].append(mat)
        st['ledger'] = led.to_dict()
        self.save_role(role)
        event(f'{role} 背包「{mat}」→ {"個人" if sub == "personal" else "公共"}倉庫')

    def evict_many(self, role, mats):
        """批次存倉（2026-10-17：一次開面板、倉庫分頁只切一次）：mats 全部先試個人倉庫，個人滿（95）的再批次改存公倉並記 in_public；
        每樣成功後立刻更新 ledger / 進度檔。失敗語意同 evict（PASS 類 rc 直接停、其餘 EXIT_DEPOT）；批次沒處理到的樣退回單樣 evict"""
        mats = list(mats)
        if len(mats) <= 1:
            for m in mats:
                self.evict(role, m)
            return
        st = self.st[role]
        game_of = {m: (m[len(dp.PRODUCT_PREFIX):] if m.startswith(dp.PRODUCT_PREFIX) else m) for m in mats}
        mat_of = {g: m for m, g in game_of.items()}
        done = set()

        def record(game, sub, rc):
            if rc:
                return
            mat = mat_of[game]
            led = dp.Ledger(st['ledger'])
            led.evict(mat, sub)
            key = 'in_personal' if sub == 'personal' else 'in_public'
            if mat not in st[key]:
                st[key].append(mat)
            st['ledger'] = led.to_dict()
            self.save_role(role)
            done.add(mat)
            event(f'{role} 背包「{mat}」→ {"個人" if sub == "personal" else "公共"}倉庫')

        rc, res = self.T.depot_store_many(role, [(game_of[m], 'personal') for m in mats], on_item=record)
        if rc and rc in PASS:
            self.fail(rc, f'存倉遇到 rc {rc}', bag_rc=rc)
        todo = [m for m in mats if m not in done]
        if todo:
            pub = [m for m in todo if res.get(game_of[m]) in (None, 95)]      # 個人滿 / 沒處理到 → 公倉批次
            if pub:
                event(f'{role} 個人倉庫存不進（bag rc {rc}）→ 「{"、".join(pub)}」改存公共倉庫')
                rc2, res2 = self.T.depot_store_many(role, [(game_of[m], 'public') for m in pub], on_item=record)
                if rc2 and rc2 in PASS:
                    self.fail(rc2, f'存倉遇到 rc {rc2}', bag_rc=rc2)
        for m in mats:                                       # 還沒成功的（92 沒有 / 批次中斷）→ 單樣流程，語意同舊版
            if m not in done:
                self.evict(role, m)

    def buy_role(self, role, stage):
        T, st = self.T, self.st[role]
        plan = self.plan_of(role)
        self.go_spot(role, stage)
        route = dp.store_route(stage, dp.remaining_buy(plan, stage, st['bought']), self.where, self.stores, plan['first_use'])
        for store, mats in route:
            led = dp.Ledger(st['ledger'])
            mats = sorted(mats, key=lambda nq: (store.items.index(nq[0]) if nq[0] in store.items else 999, nq[0]))
            batches = dp.buy_batches(led, plan, st['rings'], mats)    # 放不下 → 先存倉（材料最晚用的優先、成品次之）；還不夠 → 分批買、批間存剛買最晚用的
            if batches is None:
                prot = [m for m, v in led.bag.items() if v > 0 and m in dp.PEPPERS]
                self.fail(EXIT_BUY, f'{role} 背包放不下「{store.name}」的材料：背包帳上 {led.kinds()} 種（胡椒 {len(prot)} 種不存）、'
                          f'這家店要 {len(mats)} 種、上限 {dp.BAG_KINDS_MAX} 種，分批也排不出', role=role)
            if len(batches) > 1:
                event(f'{role}「{store.name}」{len(mats)} 種放不下 → 分 {len(batches)} 批買：'
                      + ' / '.join(f'存{"、".join(r) or "（無）"}→買{len(b)}種' for r, b in batches))
            for i, (_, bmats) in enumerate(batches):
                if i:                                           # 後幾批：照現在的帳重算要存的（前一批可能有反應式存倉）
                    led = dp.Ledger(st['ledger'])
                    later = {n for _, bb in batches[i + 1:] for n, _ in bb}
                    nb = dp.buy_batches(led, plan, st['rings'], bmats, protect=later)
                    room = nb[0][0] if nb and len(nb[0][1]) == len(bmats) else None
                    if room is None:
                        self.fail(EXIT_BUY, f'{role}「{store.name}」第 {i + 1} 批 {len(bmats)} 種放不下（背包帳上 {led.kinds()} 種、上限 {dp.BAG_KINDS_MAX}）', role=role)
                else:
                    room = batches[0][0]
                self.evict_many(role, room)
                self.buy_at(role, plan, store, bmats)

    def buy_at(self, role, plan, store, mats):
        T, st = self.T, self.st[role]
        rc = T.preflight()
        if rc:
            self.tool_fail(rc, EXIT_BUY, f'preflight 失敗（rc {rc}）')
        if not T.shop_enter(store):
            T.cleanup()
            self.fail(EXIT_WALK, f'{role} 走不到 / 點不開「{store.name}」（{store.map}:{store.x},{store.y}）的道具商店', role=role)
        done = []
        mats = sorted(mats, key=lambda nq: (store.items.index(nq[0]) if nq[0] in store.items else 999, nq[0]))   # 店內依清單 index 由小到大買（只往下捲、不回頭；2026-10-17 227 修）
        try:
            nav = {'drags': 0}
            for name, q in mats:
                ok = self.buy_item(role, plan, store, name, q, nav, protect={n for n, _ in mats})
                if not ok:
                    self.fail(EXIT_BUY, f'{role} 在「{store.name}」買「{name}」×{q} 失敗（不重買、已關店）', role=role, item=name)
                done.append(name)
        finally:
            T.shop_close()
        led_now = dp.Ledger(st['ledger'])
        check_names = [n for n in done if led_now.bag.get(n, 0) > 0]          # 買完又被存倉的（反應式存倉）不核對背包
        missing, unread = T.bag_check(role, check_names) if check_names else ([], 0)
        if missing:
            if unread < 0:
                self.tool_fail(-unread, EXIT_BUY, f'{role} 買完核對背包失敗（bag rc {-unread}）', role=role)
            # 數量框判 bought（買前 → 買後歸 0）= 已證明買到（bought / ledger 買的當下已寫進度檔，不 pop、不重買）→ 背包名稱 OCR 找不到只記 log；
            # 只有 zeroish（歸 0 但字認不出、沒有證據）才把背包核對當硬閘（2026-10-17 p1 DKBO5 水分多的香草「多早」OCR 不確定 → 誤 227 + 重買修）
            weak = [n for n in missing if (role, n) in self.zeroish]
            soft = [n for n in missing if n not in weak]
            if soft:
                event(f'{role} 背包名稱核對：{"、".join(soft)} 沒認出（有 {unread} 格沒讀出名字；數量框已判買到 → 視為已買，不 227、bought 保留）')
            if weak and len(weak) > unread:                     # zeroish 且比「沒認出名字的格」還多 → 確定缺
                led = dp.Ledger(st['ledger'])
                for n in weak:
                    st['bought'].pop(n, None)
                    led.bag.pop(n, None)
                st['ledger'] = led.to_dict()
                self.save_role(role)
                self.fail(EXIT_BUY, f'{role} 在「{store.name}」買完，但背包找不到 {"、".join(weak)}（數量框歸 0 但認不出字；不重買，請人看）', role=role, missing=weak)
            elif weak:
                event(f'{role} 背包名稱核對：{"、".join(weak)} 沒認出（有 {unread} 格沒讀出名字，視為已買）')
        event(f'{role} {store.name} 買完：' + '、'.join(f'{n}×{dict(mats)[n]}' for n in done))

    def buy_item(self, role, plan, store, name, q, nav, protect=()) -> bool:
        """店內一項：選商品（標題核對）→ 數量每位數字都認得就 ＋ 到 n 一次買、不認得才拆（shopkit.qty_chunks）；＋ 後讀不回 → 改每次買 1 個 → 每次：數量 c（＋ / － 鈕）→ 購買 → 看數量框（shopkit.buy_checked）。
        bought / zeroish（歸 0 但 0 還沒樣板；每間店買完的背包名稱核對把關）= 記 ledger；not_bought（仍是原數量，可能背包放不下）→ 存最晚環的材料再試一次（只一次）；
        unknown（不確定有沒有買到）→ 不重買、回 False（呼叫端 227）。每買到一次就記 bought / ledger（中斷可續跑）"""
        T, st = self.T, self.st[role]
        left = int(q)
        for attempt in range(2):
            if not T.shop_select(name, store, nav):
                event(f'{role} 選不到商品「{name}」（{store.name}）')
                return False
            chunks = T.shop_chunks(left)
            if not chunks:
                event(f'{role} 數量 {left} 拆不出認得的數字（{name}；數量框樣板不足）')
                return False
            chunks, start, i = list(chunks), 1, 0              # 開店 / 選商品後數量預設 1；買完一次框歸 0（start 給 set_qty 當讀不出時的起點）
            while i < len(chunks):
                c = chunks[i]
                if not T.shop_set_qty(c, start):
                    if c > 1:                                   # ＋ 到 c 讀不回（數字沒樣板）→ 已退回起點，改每次買 1 個
                        event(f'{role} 數量 ＋ 到 {c} 讀回不對（{name}）→ 改每次買 1 個')
                        chunks[i:i + 1] = [1] * c
                        continue
                    event(f'{role} 數量 {c} 讀回不對（{name}）')
                    return False
                v = T.shop_buy_checked(c)
                if v in ('bought', 'zeroish'):
                    led = dp.Ledger(st['ledger'])
                    led.buy(name, c)
                    st['ledger'] = led.to_dict()
                    st['bought'][name] = int(st['bought'].get(name, 0)) + c
                    self.save_role(role)
                    left -= c
                    start, i = 0, i + 1
                    if v == 'zeroish':
                        self.zeroish.add((role, name))           # 只有「認不出的字」才讓背包核對當硬閘；bought 已證明買到 → 背包核對只記 log
                        event(f'{role} 買「{name}」×{c}：數量框變成認不出的字（應為 0，尚無樣板）→ 視為買到，等背包名稱核對')
                    continue
                if v != 'not_bought':                           # 不確定有沒有買到 → 不重買（避免買兩次），呼叫端 227
                    event(f'{role} 買「{name}」×{c} 後數量框讀不出 / 怪值 → 不確定有沒有買到，不重買')
                    return False
                break
            if left <= 0:
                return True
            event(f'{role} 買「{name}」後數量框仍是原數量（應為 0；還差 {left}）' + ('；背包可能已滿 → 存倉再試一次' if attempt == 0 else ''))
            if attempt == 0:
                led = dp.Ledger(st['ledger'])
                m = dp.choose_evict(led, plan, st['rings'], protect={name} | set(protect))
                if m is None:                                   # 同店其他材料以外沒東西可存 → 連同店材料一起考慮
                    m = dp.choose_evict(led, plan, st['rings'], protect={name})
                if m is None:
                    return False
                T.shop_close()                                  # 存倉要開背包（便利店面板擋住）→ 先關店再回來
                self.evict(role, m)
                if not T.shop_enter(store):
                    return False
                nav['drags'] = 0
        return False

    # ---- 合成 / 提交 ----
    def craft_work(self, role, final: bool) -> bool:
        """這個人現在有沒有事可做（mid：背包材料齊的項或該環已可提交；final：任何還沒提交的支援環）"""
        if self.role_complete(role):
            return False
        st, plan = self.st[role], self.plan_of(role)
        led = dp.Ledger(st['ledger'])
        for r, rs in zip(plan['rings'], st['rings']):
            if not r['supported'] or rs.get('submitted'):
                continue
            if final or (dp.ring_ready(rs, r['items']) and not dp.products_away(r, rs, led)):
                return True
            for k, it in enumerate(r['items']):
                if not it['done'] and not rs['crafted'][k] and dp.craftable(it, led, bag_only=True):
                    return True
        return False

    def stage_craft(self, final: bool):
        stage = 'final' if final else 'mid'
        who = [r for r in self.order if self.craft_work(r, final)]
        if not who:
            event(f'{stage}：沒有人有可合成 / 可提交的項 → 跳過')
            return
        self.gather_hospital()
        for role in who:
            self.check_day()
            self.switch_to(role)
            self.craft_role(role, final)
            self.st[role]['stages'][stage] = True
            self.save_role(role)

    def sync_greens(self, role, plan, final: bool) -> bool:
        """開每環前先看面板：還沒記 crafted 的項，面板已 1/1 綠（例：上次手動補合成、進度檔沒記）→ 記 crafted、不開彈窗。
        只看有這種項的環；開了面板回 True（呼叫端接著用、最後關）。兩項都綠 → 後面 ring_ready 直接提交"""
        T, st = self.T, self.st[role]
        rings = [(r, rs) for r, rs in zip(plan['rings'], st['rings']) if r['supported'] and not rs.get('submitted')
                 and any(not it['done'] and not rs['crafted'][k] for k, it in enumerate(r['items']))]
        if not rings:
            return False
        self.open_daily(role)
        for r, rs in rings:
            if not T.goto_page(r['ring']):
                self.fail(EXIT_CRAFT, f'{role} 翻不到第 {r["ring"]} 頁', role=role)
            states = T.item_states()
            for k, it in enumerate(r['items']):
                if not it['done'] and not rs['crafted'][k] and states[k] == 'green':
                    msg = dp.mark_item(st, r, k, 'crafted')
                    self.save_role(role)
                    event(f'{stage_name(final)} {role} 第 {r["ring"]} 環{"上下"[k]}項面板已 1/1 綠 → 跳過不開彈窗（{msg}）')
        return True

    def craft_role(self, role, final: bool):
        T, st = self.T, self.st[role]
        plan = self.plan_of(role)
        opened = False
        try:
            opened = self.sync_greens(role, plan, final)
            for r, rs in zip(plan['rings'], st['rings']):
                if not r['supported'] or rs.get('submitted'):
                    continue
                ri = r['ring']
                led = dp.Ledger(st['ledger'])
                todo = [k for k, it in enumerate(r['items']) if not it['done'] and not rs['crafted'][k]
                        and (final or dp.craftable(it, led, bag_only=True))]
                away = dp.products_away(r, rs, led)             # 已合成但存倉的成品（背包放不下時存的；提交要在背包）
                if not todo and not dp.ring_ready(rs, r['items']):
                    continue
                if not final and away and not todo:             # mid：成品在倉庫 → 這環留給 final 取回再提交
                    continue
                if final and (todo or away):
                    if opened:
                        T.daily_close()
                        opened = False
                    self.fetch_materials(role, plan, r, todo)
                if not opened:
                    self.open_daily(role)
                    opened = True
                for k in todo:
                    if not T.goto_page(ri):                     # 每項合成前都讀頁碼確認在第 ri 頁（2026-10-17 停在 4/5 點第 5 環 → 229）
                        self.fail(EXIT_CRAFT, f'{role} 翻不到第 {ri} 頁', role=role)
                    it = r['items'][k]
                    ok, why = T.craft_item(k, it['name'])
                    if not ok:
                        self.fail(EXIT_CRAFT, f'{role} 第 {ri} 環「{it["name"]}」合成失敗：{why}', role=role, ring=ri)
                    led = dp.Ledger(st['ledger'])
                    led.craft(it['mats'], it['name'])
                    st['ledger'] = led.to_dict()
                    rs['crafted'][k] = True
                    self.save_role(role)
                    event(f'{stage_name(final)} {role} 第 {ri} 環「{it["name"]}」合成完成')
                if dp.ring_ready(rs, r['items']) and (final or not dp.products_away(r, rs, dp.Ledger(st['ledger']))):
                    if not T.goto_page(ri):                     # 提交前也確認頁碼（提交的是目前頁那環）
                        self.fail(EXIT_CRAFT, f'{role} 提交前翻不到第 {ri} 頁', role=role)
                    self.submit_ring(role, r, rs)
                    peppers = [n for n, _ in sum((it['mats'] for it in r['items']), []) if n in dp.PEPPERS]
                    if peppers and final:
                        T.daily_close()
                        opened = False
                        self.return_peppers(role, sorted(set(peppers)))
        finally:
            if opened:
                T.daily_close()
        if final:
            self.verify_complete(role, plan)

    def fetch_materials(self, role, plan, ring, todo):
        """final：這環要合成的項的材料、以及已合成但存倉的成品（提交要在背包）先到背包（個人倉庫 / in_public 的公倉 / 胡椒的公倉）。
        panel 已關。背包放不下 → 先存最晚環的材料（成品次之；這環要的都受保護）"""
        T, st = self.T, self.st[role]
        led = dp.Ledger(st['ledger'])
        rs = st['rings'][ring['ring'] - 1]
        need = {}
        for k in todo:
            for n, q in ring['items'][k]['mats']:
                need[n] = need.get(n, 0) + q
        for k, it in enumerate(ring['items']):
            if not it['done'] and rs['crafted'][k]:
                key = dp.PRODUCT_PREFIX + it['name']
                need[key] = need.get(key, 0) + 1
        take = []
        for n, q in need.items():
            if n in dp.PEPPERS:
                if led.bag.get(n, 0) <= 0:
                    take.append((n, 'public'))
            elif led.bag.get(n, 0) < q:
                sub = 'personal' if led.personal.get(n, 0) > 0 else ('public' if led.public.get(n, 0) > 0 else None)
                if sub is None:
                    self.fail(EXIT_DEPOT, f'{role} 第 {ring["ring"]} 環要「{n}」×{q}，背包只有 {led.bag.get(n, 0)}、倉庫帳上也沒有', role=role, item=n)
                take.append((n, sub))
        if not take:
            return
        room = dp.make_room(led, plan, st['rings'], [n for n, _ in take], protect=set(need))
        if room is None:
            self.fail(EXIT_BUY, f'{role} 背包放不下第 {ring["ring"]} 環的材料，又沒有可存倉的材料', role=role)
        self.evict_many(role, room)
        batch_rc = self.take_many(role, take)
        for n, sub in take:
            game = n[len(dp.PRODUCT_PREFIX):] if n.startswith(dp.PRODUCT_PREFIX) else n
            if n in batch_rc.get('done', ()):
                continue                                         # 批次已取到、ledger 已更新
            rc = T.depot_take(role, game, sub)
            for _ in range(3):                                   # 94 = 背包滿（模型比實際寬鬆，例：背包原本就有雜物）→ 多存一種不需要的再取
                if rc != 94:
                    break
                led = dp.Ledger(st['ledger'])
                m = dp.choose_evict(led, plan, st['rings'], protect=set(need) | {n})
                if m is None:
                    break
                event(f'{role} 取「{n}」時背包滿（bag rc 94）→ 先把「{m}」存倉再取')
                self.evict(role, m)
                rc = T.depot_take(role, game, sub)
            if rc:
                if n in dp.PEPPERS:
                    self.fail(EXIT_PEPPER if rc not in PASS else rc, f'{role} 公共倉庫取不到「{n}」（bag rc {rc}；胡椒要使用者先放公倉，腳本不買）', role=role, item=n, bag_rc=rc)
                self.tool_fail(rc, EXIT_DEPOT, f'{role} 從{sub}倉庫取「{n}」失敗（bag rc {rc}）', role=role, item=n, bag_rc=rc)
            led = dp.Ledger(st['ledger'])
            if n in dp.PEPPERS:
                led.bag[n] = max(1, led.bag.get(n, 0))           # 整疊取出，量未知（使用者備的）；帳上記 1 當「在背包」旗標
            else:
                led.take(n, sub)
                key = 'in_personal' if sub == 'personal' else 'in_public'
                if n in st[key]:
                    st[key].remove(n)
            st['ledger'] = led.to_dict()
            self.save_role(role)
            event(f'final {role} 取回「{game}」（{"個人" if sub == "personal" else "公共"}倉庫 → 背包）')

    def take_many(self, role, take) -> dict:
        """final 取料批次（2026-10-17）：take = [(帳上名, sub)]，一個 Session、倉庫分頁各切一次、每樣不切回背包頁；
        每樣成功後立刻更新 ledger / 進度檔，回 {'done': {帳上名}}。批次沒取到的（找不到 / 失敗 / 沒處理）交回呼叫端走單樣流程（含 94 背包滿重試、胡椒 / 倉庫失敗的原本錯誤語意）"""
        st = self.st[role]
        if len(take) <= 1:
            return {'done': set()}
        game_of = {n: (n[len(dp.PRODUCT_PREFIX):] if n.startswith(dp.PRODUCT_PREFIX) else n) for n, _ in take}
        name_of = {g: n for n, g in game_of.items()}
        done = set()

        def record(game, sub, rc):
            if rc:
                return
            n = name_of[game]
            led = dp.Ledger(st['ledger'])
            if n in dp.PEPPERS:
                led.bag[n] = max(1, led.bag.get(n, 0))           # 整疊取出，量未知；帳上記 1 當「在背包」旗標
            else:
                led.take(n, sub)
                key = 'in_personal' if sub == 'personal' else 'in_public'
                if n in st[key]:
                    st[key].remove(n)
            st['ledger'] = led.to_dict()
            self.save_role(role)
            done.add(n)
            event(f'final {role} 取回「{game}」（{"個人" if sub == "personal" else "公共"}倉庫 → 背包）')

        rc, _ = self.T.depot_take_many(role, [(game_of[n], sub) for n, sub in take], on_item=record)
        if rc and rc in PASS:
            self.fail(rc, f'取倉遇到 rc {rc}', bag_rc=rc)
        return {'done': done}

    def return_peppers(self, role, peppers):
        """胡椒用完整疊存回公共倉庫（借出的道具要還）"""
        T, st = self.T, self.st[role]
        for n in peppers:
            led = dp.Ledger(st['ledger'])
            if led.bag.get(n, 0) <= 0:
                continue
            rc = T.depot_store(role, n, 'public')
            if rc:
                self.tool_fail(rc, EXIT_DEPOT, f'{role}「{n}」存回公共倉庫失敗（bag rc {rc}）；胡椒還在背包，請人處理', role=role, item=n, bag_rc=rc)
            led.bag.pop(n, None)
            st['ledger'] = led.to_dict()
            self.save_role(role)
            event(f'final {role} 胡椒「{n}」整疊存回公共倉庫')

    def submit_ring(self, role, ring, rs):
        """兩項都 1/1 綠才提交；提交後 n/5 +1（讀不到計數才退而求其次看兩項不再是綠）"""
        T, st = self.T, self.st[role]
        states = T.item_states()
        if states != ['green', 'green']:
            self.fail(EXIT_CRAFT, f'{role} 第 {ring["ring"]} 環兩項不是 1/1 綠（{states}）→ 不提交', role=role, ring=ring['ring'])
        before = T.reward_count()
        if not T.submit():
            self.fail(EXIT_CRAFT, f'{role} 提交委託點不到（面板特徵不在）', role=role)
        T.sleep(0.5)
        after = T.reward_count()
        ok = (after == before + 1) if (before is not None and after is not None) else (T.item_states() != ['green', 'green'])
        if not ok:
            self.fail(EXIT_CRAFT, f'{role} 第 {ring["ring"]} 環提交後計數 {before} → {after}（應 +1）', role=role, ring=ring['ring'])
        rs['submitted'] = True
        led = dp.Ledger(st['ledger'])
        led.submit([it['name'] for it in ring['items'] if not it['done']])
        st['ledger'] = led.to_dict()
        if after is not None:
            st['reward'] = after
        self.save_role(role)
        event(f'提交 {role} 第 {ring["ring"]} 環（獎勵計數 {before} → {after}）')

    def verify_complete(self, role, plan):
        """final 後：支援的環都提交了嗎；全 5 環支援時獎勵計數要 5、讀不到才看背包有沒有裝備升級石（兩訊號取一，只是參考）"""
        st = self.st[role]
        left = [r['ring'] for r in plan['rings'] if r['supported'] and not st['rings'][r['ring'] - 1].get('submitted')]
        if left:
            self.fail(EXIT_CRAFT, f'{role} 還有環沒提交：{left}', role=role)
        n_sub = len(plan['supported_rings'])
        cnt = st.get('reward')
        if len(plan['supported_rings']) == dp.RINGS:
            if cnt is not None and cnt != dp.RINGS:
                self.fail(EXIT_CRAFT, f'{role} 5 環都提交了，但獎勵計數是 {cnt}/5', role=role)
            if cnt is None:
                miss, unread = self.T.bag_check(role, [STONE])
                if miss and unread == 0:
                    self.fail(EXIT_CRAFT, f'{role} 5/5 驗證：獎勵計數讀不到、背包也沒有「{STONE}」', role=role)
        event(f'final {role} 完成（{n_sub} 環提交）' + ('' if n_sub == dp.RINGS else f'；{dp.RINGS - n_sub} 環不支援已跳過'))

    def stage_finish(self):
        T = self.T
        self.leader_current()
        T.unlock()
        self.form_team()                                       # 醫院段結束時已組著 → 不點，直接去練功
        if self.o.get('grind', True):
            rc = T.grind_go()
            if rc:
                self.tool_fail(rc, EXIT_PREP, f'去練功失敗（grind rc {rc}）', grind_rc=rc)

    # ---- 主流程 ----
    def go(self) -> int:
        o = self.o
        today = dp.today()
        team = None if o.get('fresh') else dp.load(dp.team_path())
        if team and dp.stale(team, today):
            if team.get('complete'):
                team = None                                      # 昨天的 run 已經跑完 → 今天新的一輪
            else:
                self.team = team
                self.fail(EXIT_ARGS, f'進度檔是 {team.get("date")} 的、當時沒跑完（今天 {today}）：遊戲環數已清 0，停手；人看過再決定 --fresh')
        if team and team.get('complete') and not o.get('from_stage'):
            self.team = team
            self.fail(EXIT_ARGS, f'今天（{today}）已經完成過一輪（進度檔 complete）；要重跑用 --from 段 或 --fresh', all_done=True)
        if not team or set(team.get('roles') or []) != set(self.roles):
            team = dp.new_team_state(self.roles, today)
            fresh_roles = True
        else:
            fresh_roles = bool(o.get('fresh'))
        self.team = team
        for role in self.roles:
            self.st[role] = dp.load_role(role, today, fresh=fresh_roles)
            if dp.stale(self.st[role], today):
                self.st[role] = dp.new_role_state(role, today)
        stages = list(dp.STAGES)
        start = o.get('from_stage')
        if not start:
            start = next((s for s in stages if s not in team.get('done', [])), 'finish')
        if start not in stages:
            self.fail(EXIT_ARGS, f'--from {start!r} 不是段名 {stages}')
        team.setdefault('done', [])
        stop_after = o.get('stop_after')
        try:
            for s in stages[stages.index(start):]:
                team['stage'] = s
                self.save_team()
                event(f'段 {s} 開始')
                self.dispatch(s)
                if s not in team['done']:
                    team['done'].append(s)
                self.save_team()
                if stop_after and s == stop_after:
                    break
            if stages[-1] in team['done']:
                team['complete'] = True
                self.save_team()
        except Stop as e:
            self.info['stop'] = e.msg
            raise
        return 0

    def dispatch(self, s):
        if s in ('sam', 'fish'):
            self.stage_buy(s)
        elif s == 'mid':
            self.stage_craft(False)
        elif s == 'final':
            self.stage_craft(True)
        else:
            getattr(self, 'stage_' + s)()


def role_plan(st, recipes, where, stores) -> dict:
    """每人進度（items + done）→ dp.plan_role 計畫（Daily.plan_of 與 mark 共用）"""
    done = [[bool(d) for d in pair] for pair in (st.get('done') or [])] or None
    return dp.plan_role(st['items'], recipes, where, stores, done)


def mark_bought(role, name, qty) -> int:
    """離線補記「已買」（不碰遊戲）：數量框 / 遊戲日誌證明買到、但進度檔沒記（舊版背包核對失敗會 pop bought）→ 續跑才不會重買。
    bought[材料] 與 ledger.bag[材料] 都設成 qty（已有就覆寫成這個量，不累加）；材料名須在某家便利店清單裡"""
    try:
        qty = int(qty)
    except ValueError:
        qty = 0
    if qty < 1:
        print(f'{SRC}：用法 daily.py mark-bought <角色> <材料> <數量 ≥1>', file=sys.stderr)
        return EXIT_ARGS
    st = dp.load(dp.role_path(role))
    if not st or not st.get('read'):
        print(f'{SRC}：{role} 沒有已讀清單的進度檔，不用補記', file=sys.stderr)
        return EXIT_ARGS
    if dp.stale(st):
        print(f'{SRC}：{role} 進度檔日期 {st.get("date")} 不是今天，不補記', file=sys.stderr)
        return EXIT_ARGS
    stores, where = dp.load_stores()
    if name not in where:
        print(f'{SRC}：「{name}」不在任何便利店清單，不補記（名字要與商店清單完全一樣）', file=sys.stderr)
        return EXIT_ARGS
    st['bought'][name] = qty
    led = dp.Ledger(st['ledger'])
    if led.bag.get(name, 0) < qty and led.personal.get(name, 0) + led.public.get(name, 0) == 0:
        led.bag[name] = qty
    st['ledger'] = led.to_dict()
    dp.save(dp.role_path(role), st)
    event(f'mark-bought {role} 「{name}」×{qty}：已寫入 bought / ledger')
    print(f'{role}「{name}」已記為買到 ×{qty}（bought + 背包帳）')
    return 0


def mark(role, ring, which, what) -> int:
    """離線補記進度檔（不碰遊戲）：手動在遊戲裡補完某項合成 / 提交後同步，續跑才不會再做一次。
    ring = 1～5；which = 上 / 下（submitted 是整環，上下不看）；what = crafted / submitted（dp.mark_item）"""
    k = {'上': 0, '下': 1}.get(str(which))
    try:
        ring = int(ring)
    except ValueError:
        ring = 0
    if k is None or not 1 <= ring <= dp.RINGS or what not in ('crafted', 'submitted'):
        print(f'{SRC}：用法 daily.py mark <角色> <環 1～{dp.RINGS}> <上|下> crafted|submitted', file=sys.stderr)
        return EXIT_ARGS
    st = dp.load(dp.role_path(role))
    if not st or not st.get('read'):
        print(f'{SRC}：{role} 沒有已讀清單的進度檔，不用補記', file=sys.stderr)
        return EXIT_ARGS
    if dp.stale(st):
        print(f'{SRC}：{role} 進度檔日期 {st.get("date")} 不是今天，不補記', file=sys.stderr)
        return EXIT_ARGS
    stores, where = dp.load_stores()
    rp = role_plan(st, dp.load_recipes(), where, stores)['rings'][ring - 1]
    msg = dp.mark_item(st, rp, k, what)
    if msg:
        dp.save(dp.role_path(role), st)
        event(f'mark {role} 第 {ring} 環{which}項 {what}：{msg}')
    print(f'{role} 第 {ring} 環{which}項 {what}：{msg or "進度檔已是這個狀態，不變"}')
    return 0


def stage_name(final: bool) -> str:
    return 'final' if final else 'mid'


# ======================================================================================
def run(roles=None, confirm_buy: bool = False, from_stage=None, fresh: bool = False, dry_run: bool = False, grind: bool = True,
        tools=None, stop_after=None, recipes=None, stores=None, where=None, regroup: str = REGROUP_DEFAULT) -> int:
    LAST.clear()
    roles = list(roles) if roles else list(ROLES)
    if not roles:
        print(f'{SRC}：PSA_CLIENT={clients.name()} 沒有名單（clients.ROSTERS）', file=sys.stderr)
        return EXIT_ARGS
    T = tools or Tools()
    if regroup not in REGROUP_MODES:
        print(f'{SRC}：--regroup {regroup!r} 不是 {REGROUP_MODES}', file=sys.stderr)
        return EXIT_ARGS
    D = Daily(T, dict(confirm_buy=confirm_buy, from_stage=from_stage, fresh=fresh, grind=grind, stop_after=stop_after, regroup=regroup), roles, recipes, stores, where)
    event(f'開始：{"、".join(roles)}（{clients.name()}）confirm_buy={confirm_buy} from={from_stage} fresh={fresh} dry_run={dry_run} grind={grind} regroup={regroup}')
    rc = 0
    try:
        if dry_run:
            rc = _plan_only(D)
        else:
            rc = D.go()
    except Stop as e:
        rc = e.rc
        event(f'停手（{rc}）：{e.msg}')
        if rc not in (EXIT_ARGS, EXIT_NOBUY, EXIT_NOROLE):
            try:
                T.cleanup()
            except Exception:                                  # noqa: BLE001
                pass
    except Exception as e:                                     # noqa: BLE001  任何意外都先關面板再往上丟（不留面板擋住後面的腳本）
        try:
            T.cleanup()
        except Exception:                                      # noqa: BLE001
            pass
        event(f'例外：{type(e).__name__}: {e}')
        raise
    finally:
        if not dry_run:
            try:
                T.unlock()
            except Exception:                                  # noqa: BLE001
                pass
    LAST.update(D.info, ok=rc == 0, rc=rc, desc=dp.EXIT_NAMES.get(rc, ''))
    if not rc:
        event('完成')
    return rc


def _plan_only(D: Daily) -> int:
    """離線：讀每人進度檔印計畫（沒讀過清單的人只提示）"""
    today = dp.today()
    n = 0
    for role in D.order:
        st = dp.load_role(role, today)
        if not st.get('read'):
            print(f'{role}：尚未讀清單（先 daily.py read-all）')
            continue
        D.st[role] = st
        for ln in dp.plan_lines(role, D.plan_of(role), D.stores, D.where):
            print(ln)
        n += 1
    return 0 if n else EXIT_ARGS


def show() -> int:
    team = dp.load(dp.team_path())
    print(f'全隊：{json.dumps(team, ensure_ascii=False) if team else "（沒有進度檔）"}')
    for role in ROLES:
        st = dp.load(dp.role_path(role))
        if not st:
            print(f'{role}：（沒有進度檔）')
            continue
        rings = ' '.join(('S' if r.get('submitted') else ('c' if any(r['crafted']) else '-')) for r in st['rings'])
        print(f'{role}：日期 {st["date"]} 已讀={st["read"]} 環(S=提交 c=有合成)={rings} 獎勵計數={st.get("reward")} 已買 {len(st["bought"])} 種 '
              f'個人倉庫 {st["in_personal"]} 公倉 {st["in_public"]} 段 {sorted(st["stages"])}')
    return 0


def main(argv=None) -> int:
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('cmd', choices=['read-all', 'plan', 'show', 'run', 'mark', 'mark-bought'])
    ap.add_argument('mark_args', nargs='*', help='mark 用：<角色> <環 1～5> <上|下> crafted|submitted；mark-bought 用：<角色> <材料> <數量>')
    ap.add_argument('--roles', help='逗號分隔角色（預設本視窗名單全部）')
    ap.add_argument('--from', dest='from_stage', choices=list(dp.STAGES), help='從這一段開始（預設從進度檔續跑）')
    ap.add_argument('--confirm-buy', action='store_true', help='買材料（500 / 個）與合成（1000 / 項）；沒給 = 讀清單 + 印計畫就停（221）')
    ap.add_argument('--fresh', action='store_true', help='丟掉進度檔重來（跨過 00:00 後）')
    ap.add_argument('--dry-run', action='store_true', help='同 plan（不碰遊戲）')
    ap.add_argument('--no-grind', action='store_true', help='最後不去練功')
    ap.add_argument('--regroup', choices=list(REGROUP_MODES), default=REGROUP_DEFAULT,
                    help='買完回醫院：pull = 隊長一人走回再快速組隊（預設）；gather = 先在店內組隊再帶隊走（隊員拉不過來時的 fallback）')
    a = ap.parse_args(argv)
    if not ROLES:
        print(f'{SRC}：PSA_CLIENT={clients.name()} 沒有名單', file=sys.stderr)
        return EXIT_ARGS
    roles = [r.strip() for r in a.roles.split(',') if r.strip()] if a.roles else None
    if roles:
        import charname
        roles = [next((x for x in ROLES if charname.canon(x) == charname.canon(r)), r) for r in roles]
        bad = [r for r in roles if r not in ROLES]
        if bad:
            print(f'{SRC}：角色 {bad} 不在本視窗名單 {ROLES}', file=sys.stderr)
            return EXIT_ARGS
    if a.cmd == 'show':
        return show()
    if a.cmd == 'mark-bought':
        import charname
        role = next((x for x in ROLES if a.mark_args and charname.canon(x) == charname.canon(a.mark_args[0])), None)
        if len(a.mark_args) != 3 or not role:
            print(f'{SRC}：用法 daily.py mark-bought <角色> <材料> <數量>（角色須在本視窗名單 {ROLES}）', file=sys.stderr)
            return EXIT_ARGS
        return mark_bought(role, a.mark_args[1], a.mark_args[2])
    if a.cmd == 'mark':
        if len(a.mark_args) != 4:
            print(f'{SRC}：用法 daily.py mark <角色> <環 1～{dp.RINGS}> <上|下> crafted|submitted', file=sys.stderr)
            return EXIT_ARGS
        import charname
        role = next((x for x in ROLES if charname.canon(x) == charname.canon(a.mark_args[0])), None)
        if not role:
            print(f'{SRC}：角色 {a.mark_args[0]} 不在本視窗名單 {ROLES}', file=sys.stderr)
            return EXIT_ARGS
        return mark(role, *a.mark_args[1:])
    if a.cmd == 'plan' or a.dry_run:
        return _finish_cli(run(roles, dry_run=True))
    import winenv
    winenv.enable_server()
    if a.cmd == 'read-all':
        return _finish_cli(run(roles, from_stage='prep', fresh=a.fresh, stop_after='read', regroup=a.regroup))
    return _finish_cli(run(roles, a.confirm_buy, a.from_stage, a.fresh, False, not a.no_grind, regroup=a.regroup))


def _finish_cli(rc: int) -> int:
    print(json.dumps(dict(LAST, rc=rc), ensure_ascii=False, default=str))
    return rc


if __name__ == '__main__':
    sys.exit(main())
