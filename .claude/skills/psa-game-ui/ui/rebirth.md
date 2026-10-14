# 漆黑洞窟轉生任務腳本（rebirth.py）

> 2026-10-11 寫成。流程取自 2004 一轉實跑（notes/quest-log.md 2004 段、notes/plan-qihei.md）。**bag.py / petdrop.py 是新寫的，實機完全沒驗證**；其餘串接既有已驗證工具。

一行指令：`uv run --no-project python tools/gui/rebirth.py [--trans N] [--from 階段] [--to 階段] [--dry-run] [--keep-old-weapon] [--confirm-rebirth] [--pet-action 忠犬|攻擊|防禦|none] [--no-dragon] [--read-levels]`
- 任務組 = 2004 + N - 1（一轉 2004、二轉 2005、三轉 2006、四轉 2007、五轉 2008；NPC / 步驟 / 四件證明都相同，只有第 6 步交的守護獸不同：大地 / 水 / 火 / 風，五轉要四隻）。
- 等級門檻：N=1～4 為 131、N=5 為 140；每轉前置要 (N-1) 轉。`--trans` 預設 = DKBO 目前轉數 + 1。
- 先 `--dry-run` 看計畫（完全不碰遊戲）。可 import：`rebirth.run(...)`，結果 dict 在 `rebirth.LAST`。
- 進度：`tools/.cache/rebirth.json`（階段狀態、龍王最後吃的時間、顆數）；事件：`notes/quest-events.log`（行首 `[rebirth]`）；失敗另寫 errlog。中斷後 `--from <失敗階段> --trans N` 接著做。

## 階段（STAGES）
| 階段 | 做什麼 | 失敗碼 |
|---|---|---|
| preflight | 先關原地遇敵（`heal.set_encounter(False)`，已關不點；練功中 EXP 橫幅擋讀字）→ 當前角色 = DKBO（面板左欄頭像紅字「當前登錄」，不看頭頂名牌）、`team.form` 滿 5 人（`Run.form`：非 0 / 非 9 → 等 3 秒 `team.check`，滿 5 就算，不滿再 form 一次）、背包 / 寵物欄空位 ≥2 → **點追蹤卡 = 等級檢查**（2026-10-14 使用者說法，`rebirth_steps.level_gate`，未實機）：傳送到吉魯島 300 / 漆黑 = 5 人達標（accept 跳過）→ `heal --no-return`（補血排在門檻後；補血前已到守門人對話框 → 警告、不補直接 enter）；跳「未達到 / 禁止傳送 / 條件不足 / 等級不足」提示窗 → 點 ✕ 關、原地遇敵開回、留在練功點 → 80（`info.gate.who` 誰不夠）；讀不懂的視窗 → 9；追蹤欄沒卡 → `bag.levels`。`--read-levels` = 舊行為（`bag.levels` 讀 5 人轉數 / 等級，不點卡）。單獨跑：`rebirth_steps.py gate --trans N`（先自己關遇敵 / 組隊） | 83 / 82 / 80 / 9 / 84 / 87 |
| accept | preflight 點卡已傳送（任務進行中）→ 跳過；否則 `rebirth_steps.accept_task`（先看任務追蹤欄：有標題精確相符的「漆黑洞窟(N轉)」卡片（titlematch 樣板，不用 OCR）→ `quest.track_task` 點卡巡路到村長 → 選單翻頁 → 接受 → 驗進行中；沒卡 / 不確定 / 點卡 20 秒沒對話框才退回 `questdetail.accept(「漆黑洞窟(N轉)」, skip_ok=True)`）：任務詳情列表 / 中間標題樣板精確比對（(三轉) / (五轉) 分得開，對不上不傳送）→ 傳送村長 → 選單頁左鈕「漆黑洞窟」翻頁 → 「接受」→ 重開詳情驗進行中；已進行中略過、已完成不接 | 97 |
| enter | `quest.py --stop-after-dialog` 最多 3 輪：吉魯島守門人 → 守門人２ → 漆黑 1F（32001） | 84 |
| boss10 | 龍王的守護 → `quest.py` 預設模式到 10F BOSS，退出碼 37（滿員）/ 38（不滿）→ 確認在 11F 以上（32011～32021，`past_boss10`，地圖為準；37 的「戰鬥 N」計數不可靠） | 85 / 84 |
| bow16 | 龍王 → `--stop-after-rewards 1`：16F 守門人收 4 件證明、每人得精靈王之弓（32016）。進度看地圖（`bow16_progress`）：17～20F = 弓已拿到 → 0；21F = 20F 帖拉所伊朵也打完 → `after_boss` 確認滿 5 人 → 記 `boss20_done`（進度檔）→ heal / boss20 跳過 | 84 / 85 |
| swap | 5 人各自：背包選弓 → 穿戴 → 武器格確認是弓 → 丟舊武器；武器格本來就是弓（上一轉的）→ 背包裡 16F 新給的那把是多的，`bag.drop_spare_bow` 丟掉 | 86 |
| heal | （`boss20_done` → 跳過）`heal --no-return` → `ass.set_pet` 5 人戰寵一般動作 → 便捷傳送「漆黑20樓」790,248 → `team.form` | 87 / 83 |
| boss20 | （`boss20_done` → 跳過）龍王 → 預設模式到 20F 帖拉所伊朵（37 / 38）→ 確認回到 32021:29,57 附近；追蹤沒走回 20F 時備援走回（見下） | 85 / 84 |
| rebirth | `team.form` → 預設模式（守門人 → 精靈王）→ 39 停 → OCR 判斷 → 放行 → 確認 5 人轉數 = N | 88 / 89 |
| cleanup | 丟 5 人轉生獎勵寵（一轉烏力斯坦 / 二轉奇娜，petdrop 名稱 + Lv1；三轉起 rebirth 階段先拍寵物欄快照、這裡 diff 找剛好 1 隻新 Lv1，不確定 98） → 龍王存回公共倉庫 → 確認原地遇敵關 → `char.ensure DKBO` → 寫 quest-log 摘要 | 86 |

## 退出碼
80 等級不足（點追蹤卡被未達條件視窗擋：已關窗、遇敵開回、留練功點；`--read-levels` / 沒卡時 bag.levels 不符或讀不到） · 81 保留不用（原缺四件證明，2026-10-13 起 preflight 不再檢查；16F 守門人自己收，缺證明卡住由 quest.py 退出碼處理） · 82 背包 / 寵物欄空位不足 · 83 隊伍 / 當前角色 · 84 quest.py 階段沒完成（非預期碼 / 地圖不對 / 逾時）· 85 BOSS 輸 / 重打失敗 / 補不滿 · 86 背包 / 寵物操作失敗 · 87 補血 / 外掛 / 傳送失敗 · 88 精靈王對話不是角色轉生（或轉生後轉數沒變）· 97 接任務失敗 · 98 轉生獎勵寵無法確認（三轉起 diff 不確定，一律不丟）· 89 `--confirm-rebirth` 停下等人。
共用：1 參數錯、2 版面、8 戰鬥鎖、9 疑似驗證視窗（quest 回 2 也轉成 9，鐵則 5 停手通知）、10 斷線（netwatch halt）。底層碼：quest 20～39、team 40～47、char 60～65、pet 70～79、bag 90～96（見各檔開頭）。

## 規則與設計
- **BOSS 戰後**（quest 預設模式 37 / 38）：先看位置是不是勝利落點（10F → 地圖 32011；20F → 32021:29,57），再 `team.check`。不滿 → `team.read_state` 找不在隊的人（名字讀不出就停）→ `char.switch <他>` → 點任務追蹤（`quest.track_task`）自動傳送 → 等到 BOSS 地圖停住 → `quest.py --fight --npc auto --team-size 1`（rc 0 才是贏）→ 確認落點 → `char.ensure DKBO` → `team.form` → `team.check`。不論成敗都切回隊長。
- **boss20 往回走**：便捷傳送「漆黑20樓」落在 32021:31,29（21 樓精靈王旁），機暴（帖拉所伊朵）在上一層 32020:20,9。一轉時 quest.py 點追蹤自動巡路會自己走回去；若 quest.py 退出碼不是 37 / 38（例 3 no_track、19 巡路卡住、逾時 0）且人仍在 32021 非勝利落點 → 備援一次（`Run.walk_back_20f` / `backtrack_fight`）：`uikit.preflight` → 三段：①北區（y<50，落點 31,29 與南出口被一條**同圖傳送帶**隔開，`walk.py --plan 32021 28 59 --from 31,29` 走不到）先 `walk_to(32021, 31,47)` 踩傳送帶（出口格 28～34,47～49 → 同圖 31,53），**同一張地圖 ID，看座標 y ≥ 50（`SOUTH_Y`）判斷**，輪詢 `read_pos` 最多 8 秒，沒進南區 → 84（`backtrack=band`）；已在南區（BOSS 戰後落點 29,57 等）跳過此段 ②`walk_to(32021, 28,59, exit_map=32020)`（南出口）③ → `team.check`（散了 `team.form`，失敗 83）→ preflight → `walk 32020 20,11` → `quest.py --fight --task … --npc auto` 點帖拉所伊朵 → 0 / 37 / 38 照 BOSS 戰後處理（滿 5 人 / 補人）。走不過傳送帶 / 出口、走不到 20,11 → 84（`info.backtrack` = band / exit / spot）；開打沒贏 → 85；備援只試一次。被打飛者重打（refight）若追蹤把人傳到 21F 也先走回 20F（單人，不 team.check）再 `--fight`。quest 回 2（驗證視窗）→ 9，不走備援。實機未驗證。
- **龍王的守護**：隊長吃（整隊 10 分鐘不遇敵，左上約 95,170 有藍色小圖示、無剩餘時間）；距上次 >9 分鐘才吃；`quest.py` 每段最長 540 秒，逾時回 0 → 強制再吃再跑。背包沒有 → 公共倉庫取出（整疊）。使用 / 取出失敗只警告（沒有也能跑，只是會遇敵）。cleanup 把剩下的存回公共倉庫（背包沒有 = 略過）。
- **精靈王轉生**：quest 預設模式遇「完成」頁會因內文含「轉生」停 39（對話框維持開著）。rebirth OCR 內文 + 按鈕 + 讀位置：含「寵物轉生 / 瑪雷菲雅」→ 88；讀不到內文 / 沒有「儀式」或「出生」字樣 / 位置不在 32021 y≈28 → 88；確認是角色轉生 → 預設直接按完成（948,461）並用 `quest.py --no-track --allow-irreversible` 收尾（領獎窗），再用 bag 讀 5 人轉數 = N；加 `--confirm-rebirth` 改成停 89。
- **換弓**：穿之前先讀武器格彈窗名稱當「舊武器」；穿後再讀武器格確認是弓；丟棄前彈窗名稱與提示窗名稱都必須吻合舊武器名、且不吻合精靈王之弓，任何一塊讀不到 = 不丟；武器格本來就是弓 = 略過（續跑安全）。`--keep-old-weapon` 不丟。
- **外掛忠犬**：`ass.py` 讀回 OCR 認不得「忠犬」會回 4（讀回 None）——實測其實設成功；rebirth 當警告（summary 會列），讀回是別的值才算失敗。要事後人眼確認。
- 當前角色一律維持 DKBO；單人重打才切走，結束必切回。

## 新寫、實機沒驗證的部分（第一次跑要在旁邊看，失敗會存 snap 到 tools/.cache/ui-log/）
- `bag.py`：背包 / 倉庫分頁特徵（來自 4 張既有背包截圖 + 倉庫 / 寵物負例）、道具彈窗特徵與名稱框 / 按鈕列框（只有裝備彈窗 1 張樣本）、等級名牌 OCR 框（`0轉133級` 在 330,203）、buff 圖示偵測（1 張樣本，讀不到只警告）、格名稱 OCR（15 格；背包第 4 列 / 捲動未量）、倉庫格座標、便捷傳送分頁選中色（185,411）。
- `petdrop.py`：垃圾桶 → 提示窗流程（2004 手動做過，沒腳本化過）；提示窗確定鈕取 615,551（ui/bag.md 寫 612,544、pet 寫 615,557）。
- `rebirth.py` 本身：整段串接沒在遊戲跑過；離線測試只驗順序、續跑、38 / 39 分支、名稱防護、存回。

## 二轉實跑經驗（`rebirth.py --trans 2`，2026-10-12 21:41～22:21，5 人 1轉131 → 2轉1級；詳細流水在 notes/quest-log.md「漆黑洞窟(二轉)」）
全程約 40 分鐘，整體照一轉流程可走通，手動介入點與對策：
- **接任務**：`questdetail.py accept` 回 126——村長對話框第 1 頁是選單（「漆黑洞窟 / 再見」），腳本只認「接受」不點。手動點「漆黑洞窟」948,461 → 第 2 頁「接受」948,461，任務卡「漆黑洞窟(二轉)」出現。（腳本尚未處理選單頁。）
- **boss10 卡在 1F 11,46**：1F 戰鬥後角色定在 32001:11,46（旁邊 9,46 出口前是無地面缺口），Auto Walking 站著不動，點地面 / 傳送圈 / 刷新角色 / 重點追蹤都無效，quest.py 解卡 rc 19。解法是 `relogin.py --confirm`（約 1 分，隊伍沒散），重跑 boss10 從 14,41 起約 5 分鐘到 11F。quest.py 現在卡住第一次會先刷新角色（`unstick_refresh_due`）。
- **boss20「挑戰機暴(轉生任務)」**：對話框被 quest.py 不可逆防護擋（rc 39；已由 1fcf5e0 放行）。手動點左鈕沒開戰、對話框會關，改用 `quest.py --fight --task 漆黑洞窟(二轉) --step 4`（`--npc auto` 因追蹤文字 OCR 失敗回 31）打贏，落 32021:29,57，再 `team.check` 滿 5 人。
- **16F 多拿的精靈王之弓（DROP2）**：每人背包第 1 格多一把，用 `bag.py drop --allow-protected` 丟 1 把（武器格穿著的不動）。bag 丟棄提示窗版型與 pet.CONFIRM 不同：丟棄 613,543 / 取消 820,543，腳本回 95 時手動點 613,543。
- **轉生**：`--from rebirth`（不加 `--confirm-rebirth`）守門人 → 精靈王（rc 39）→ OCR 判角色轉生 → 完成；落 1006:12,20，5 人 2轉1級。轉生後每人得奇娜 Lv1（寵物欄第 3 格）用 `petdrop.py` 丟（名稱 + Lv1）。
- **新手禮盒**：2轉新手禮盒在個人倉庫（先 `bag.py take --depot personal`）；內容寵物誘餌 / 離線水晶 / 2倍智慧果 / 安撫之素存公共，3轉新手禮盒存個人。離線水晶的道具名稱是「離線水晶」，不是「離線水晶8H」（已改 `rebirth_pets` 常數）。
- **舊寵物存倉**：不必先解外掛鎖定，遊戲沒擋。舊騎寵（轉生後變「等待」、名字讀不出）：先 `pet.py learn-species`，或 `rebirth_pets` 以縮圖比對認物種（`stores_for`：沒名字 + mountlike + 縮圖分數 ≥0.9 + 物種 = `--store-mount`，才放行；測試見 test_rebirth_pets.py）。
- **誘餌「+」要錢**：外掛捉寵設置裡可抓捕數「+」每按一次 +1，扣 **50,000 石幣**（鑽石不動），5 次 = 250,000 石幣。用 `rebirth_pets.py --direct-catch` 直接抓 5 隻（雷龍系 / 布拉奇多斯 約 1 分 10 秒），DKBO2 留 1、存 4 公共、其他 4 人取；每次按「+」前要確定石幣夠。戰寵 Lv1 朵拉比斯從個人倉庫取（`--expect-level 1`；同名多隻時卡片等級讀不出，指定 `--index` 取後驗 Lv1）。
- **收尾練功**：吃 2倍智慧果 → `team.form` → `grind.py start 柯奧龜洞` → `grind.py follow --trans 2 --no-heal`。
  **2026-10-15 起自動**：`rebirth_pets.py` 全部階段完成後自己接「去練功」（`grind.go`：背包讀隊長轉數 → 依等級選點 → 未滿地雷區背景起 `follow --no-heal --trans N`，到地雷區自己結束；`--no-grind` 關）；
  rebirth.py 結束只提示下一步 `rebirth_pets.py --trans N`，不再寫死練功點。
- **四轉實跑（2026-10-15 00:31～00:49）寫回的兩個修正（離線測試，待實機）**：
  ① preflight 點追蹤卡「漆黑洞窟(N轉)」時任務其實還沒接 → 被傳到瑪麗娜絲村長選單「漆黑洞窟 / 再見」（舊版 84）：`rebirth_steps.level_gate` 認得選單就在對話框接任務
  （`questdetail._after_transfer`：左鈕翻頁 → 接受 → 重開詳情驗進行中）→ 再點卡做門檻（結果帶 accepted）；別的對話框照舊 84、接取失敗 97。`--from accept` 被同一個對話框擋住（舊版 97）：
  `accept_task` 先看畫面上有沒有對話框，是村長選單就直接接，別的對話框不點、97。
  ② heal 階段 5 人戰寵一般動作「忠犬」：剛轉生 Lv1 戰寵下拉只有「攻擊 / 防禦」（舊版 `ass.set_pet` 盲點第 3 列 → 讀回攻擊 → 87）→ 改 `ass.set_pet_many(skip_missing=True)`：
  下拉依 OCR 文字找選項，找不到就點回下拉鈕收起、記警告、跳過該人（不失敗）。

## 2026-10-13 二轉後續：模組化與自動化（離線測試 test_rebirth.py / test_rebirth_steps.py / test_rebirth_pets.py；**實機未驗證**）
可獨立呼叫的小模組（rebirth.py 只串階段）：
- **`stuckrecover.py`**：quest.py 回 19 / 42（巡路卡住 / VS 牌卡死）→ `relogin_team`（relogin.py --stuck --confirm；105 → team.form）→ 呼叫端善後。questrun（每任務 2 次）與 rebirth（`Run.quest` 內，每階段 2 次，重登後 team.check / form、重吃龍王、重跑同一指令；`--fight` 單人重打不重登）共用。二轉 boss10 因手動 relogin 損失 13 分鐘。重登遇 9 / 10 原碼停手；失敗 / 仍卡 → 84（info.relogin_rc）。
- **`catchbuy.py`**：外掛捉寵設置「+」買可抓捕數（`parse_money / money / press_plus / buy / buy_to`），petquest（`--confirm-buy-bait`）與 rebirth_pets（`--confirm-buy-catch`）同一份；每次按前後讀石幣（剛好少 50,000、鑽石不變、可抓捕數 +1 才繼續）。CLI：`catchbuy.py DKBO2 5 --confirm-buy`（紅區花石幣，沒旗標只印計畫）。
- **`rebirth_steps.py`**：`accept --trans N` 接任務、`snapshot` / `drop-reward --trans N [--dry-run]` 轉生獎勵寵（見上）。三轉起 diff：每人要剛好 1 隻新出現的 Lv1、名字讀得出、狀態不是騎乘 / 出戰、不在第 1 格，先全員驗過才動手，任何不確定 → 98。
- **`bag.py drop-spare-bow <角色>`**：武器格是精靈王之弓時丟背包多的那把（`--allow-protected`；武器格不是弓 → 93 不丟）。
- boss20 備援 / 單人重打的 `quest.py --fight` 一律帶 `--step 4`（10F 為 `--step 2`），不靠追蹤文字 OCR（二轉 22:15 回 31）。
- **team.form 回 9**（二轉 22:20，BOSS 戰後；16 秒後原指令就過）：9 = `uikit.preflight` 畫面連 3 次不認得；無法重現當時畫面（事後無 snap），判斷是過場 / 結算畫面暫時認不得。rebirth 的 `Run.form` 改成回 9 時等 20 秒只讀重試一次，第 2 次仍 9 = 驗證視窗，照鐵則 5 停手。
- rebirth_pets：`--confirm-buy-catch`（買到 count → `--direct-catch`）；戰寵取「名字@1」，同名多隻卡片等級讀不出（72）→ `pet_take_lv1_scan` 逐隻 `--index` 取出驗 Lv1、不對（讀得到等級但不是 1）存回個人倉庫換下一隻；boxes 的使用 / 存倉遇 bag 95（動作後驗證失敗）各自動重試 1 次（原因在二轉沒留下 snap，無法確認根因；92 視為已存好）。
- 退出碼新增：rebirth 97 / 98（80～89 已用完，借 bag 90～96 後面空的）。

## 2026-10-13 三轉實跑寫回（`rebirth.py --trans 3` 21:26～21:47 → `rebirth_pets.py` 21:47～22:19；**以下修正只有離線測試，實機未驗證**）
- **bow16 一路打完 20F**：16F 守門人給弓時 quest.py 沒算到獎勵（`--stop-after-rewards 1` 沒停），巡路接著打完 20F 帖拉所伊朵回 37、人在 32021 → 舊版當 84，人手動 `--from swap` / `--from rebirth`。現在依地圖判斷（見階段表），21F 時 swap 後直接 rebirth。背包的弓只讀來記錄（`find_items` 讀字不穩，不當判斷依據；swap 會再驗）。
- **boss10 回 37「戰鬥 0」**：21:35 那場 BOSS 由「對話後開打」進入，quest.py 的戰鬥計數沒算到，但 after_boss 讀到人在 32011 → 判斷正確；改成 11F 以上都算勝利，與 quest 計數無關。
- **preflight team.form 回 42**（21:26，11 秒後重跑就過）：42 = 卡片數 < 5，`team.py status` 其實滿 5 人 → `Run.form` 先 `team.check`。
- **preflight 先關原地遇敵**：練功中直接接 rebirth，EXP 橫幅擋背包 / 等級讀字。
- rebirth_pets：
  - **`pet_take_lv1_scan` 格號**：實機「取出 → 存回」後其他卡**格號不變**（DKBO2 候選 [1, 7]：取 1 是 Lv130 存回後舊版試 6 → 72，手動 `take --index 7` 才拿到 Lv1；DKBO4 [1, 4] 試 3 同樣 72）。現在先用原格號，pet.take 帶名字會先驗卡片名字（不符回 72、不取）→ 才退一步試遞補格號（pos - 已存回數）；兩種都 72 換下一個候選。
  - **鎖定騎寵成長字串漏段**（errlog 584 / 585：'48/10//2'、'49//8/1'）：`growth_partial` 漏一段當萬用，只在沒有整行相同的列時用；同一列多倍數併成 1；兩列都吻合 → 停；`role_ident` 把同角色其他沒名字寵物的成長字串帶進 ident 第 3 項，漏的那段剛好是兩隻的差別 → 歧義停（不選、不勾）。
  - **捉寵系別清單雷龍系被上緣切半**：22:01～22:03 舊版「往回捲 → 往下捲」來回震盪沒選到（人手動往回捲後點 752,476）。現在 `plain_row` 寬鬆比對（讀不全的「雷龍」）、`family_below_action`：大象系夠低就點它 y - 42（點完照樣讀欄位驗證）、貼上緣才往回捲（最多 2 次）、捲過仍不行就停；系別欄位已是目標（`_field_ok`）照舊不開下拉。
  - **外掛面板失敗殘留**：下拉清單開著時點 X 會被吃掉 → 面板殘留 → 下一步寵物面板 rc 9。現在選不到時一律點回下拉欄位收起清單（系別清單也收），ass_each / catch_setup 失敗出口再 `ass_close_hard`（`ass.close_panel` 點 X 1318,90 + 驗證，最多 2 輪；仍開著 snap + 警告）。rc 14 的訊息改成「系別 / 物種下拉選不到」（舊訊息誤寫成可抓捕數）。
  - **`catchbuy` 可抓捕數 0 讀不到 → 163**：`parse_count_zero`（有「可抓捕數」字樣但沒數字 → 0；按後仍必須讀到 +1、石幣剛好 -50,000）；`parse_money` 石幣 / 鑽石依 x 分區 + 去重（活力 x≈808 不當鑽石）。
