---
name: psa-game-ui
description: Use when operating the PrimalSA (精靈王石器) game client by screen — taking screenshots, clicking buttons, opening panels, reading what is on screen, or deciding which UI element does what before playing.
---

# 精靈王石器 介面操作

## 概觀
AI 只透過「截圖 → 看圖 → 點擊 / 按鍵 → 再截圖確認」操作遊戲（AGENTS.md 第 3 節第 4 條）。
工具核心是 `tools/gui/gui.ps1`（Windows PowerShell）。兩種環境都能用：WSL（Ubuntu）的 Claude Code、Claude 桌面 App（Windows 原生，Git Bash 當 shell）。
- 手打指令用 `bash tools/gui/gui.sh ...`（WSL / Git Bash 都行；自動用 wslpath 或 cygpath 換路徑）。
- Python 腳本（`walk.py`、`heal.py`）兩邊指令相同：`uv run --no-project python tools/gui/walk.py ...`，它們直接呼叫 `powershell.exe -File gui.ps1`（平台判斷與路徑換算在 `tools/gui/winenv.py`），不經 bash。
  - **常駐 server（WSL 預設開；Windows 原生需 `PSA_GUI_SERVER=1`；`PSA_GUI_SERVER=0` 關閉）**：長程序（quest / heal / petwatch / walk 主流程）已呼叫 `winenv.enable_server()`；會走常駐 `serve.ps1`（WSL 預設；Windows 原生未量測，設 `PSA_GUI_SERVER=1` 才走）（每個程序各自一個，程序結束一定會一起結束：atexit / quest.main finally 送 quit + 關 stdin、卡住時 kill 並用 Windows PID taskkill、SIGTERM / SIGHUP 也先關、閒置 3 分鐘自動結束、下次起 server 會清掉「擁有者已死」的殘留；pixel 0.6 s → 0.09 s）。`PSA_GUI_SERVER=0` 一律關閉。`gui.sh` 與 psa-hud 的 stat.ps1 維持一次性（psa-hud 另外自動 spawn watch.py，由 watch 自己用常駐 server，見下方「即時狀態監看」）。server 的 stderr 在 `tools/.cache/gui-server.err`。孤兒 server 查法：`powershell.exe -NoProfile -Command "Get-CimInstance Win32_Process -Filter \"Name='powershell.exe'\" | ? { $_.CommandLine -match 'serve\.ps1' } | select ProcessId"`，再 `taskkill.exe /pid <pid> /f`（登記檔 `tools/.cache/gui-server.pids`；`uv run --no-project python -c "import sys; sys.path.insert(0,'tools/gui'); import winenv; print(winenv.reap_orphans())"` 手動清擁有者已死的）。
- Windows 原生需先裝 uv：`winget install astral-sh.uv`；設定細節見 AGENTS.md「在 Claude 桌面 App（Windows 原生）執行」。
**背景操作（預設）**：`shot` 用 PrintWindow 背景截圖；`click`/`dclick`/`drag` 不搶前景，只把游標瞬移到目標點完再移回（約 0.15 秒），`key` 完全不動游標。使用者可以同時用其他視窗。
- 原理：PostMessage 假焦點 + 按鍵訊息；Unity 的滑鼠位置讀真實游標，所以游標仍要移過去（細節見 gui.ps1 開頭註解）。
- **使用者怎麼動都不影響自動操作**：點擊那 0.15 秒用低階滑鼠鉤子吞掉使用者實體滑鼠的移動 / 按下（放開放行），游標一定停在目標上；鍵盤訊息直接送遊戲視窗，使用者打字、切視窗都不干擾。不用等使用者閒置。
  - 鉤子執行緒各自保存自己的 hook（自己裝自己拆）、最多活 2 秒自動解除；click / dclick / drag 的 BgBegin…BgEnd 在 try/finally 內，出錯也會還原游標並停 Guard；Stop Join 逾時寫 actions.log。離線測試：`powershell.exe -NoProfile -ExecutionPolicy Bypass -File tools\gui\test_guard.ps1`。
- 背景點擊沒反應時改用 `fg click ...`（舊的前景模式：把遊戲拉到前景並留著，**用過 `fg` / `max` 一定要跑 `end`** 還原）。
按鈕位置與每個畫面的內容見同資料夾 [ui/README.md](ui/README.md)（索引，依功能拆檔）。

## 工具
```bash
bash tools/gui/gui.sh info                 # 視窗大小
bash tools/gui/gui.sh max                  # 最大化 → 客戶區 2880×1659（ui/ 座標的基準）
bash tools/gui/gui.sh shot [out.png]       # 預設存 tools/.cache/shot.png，再用 Read 看圖（不能存到 /tmp，WSL 路徑會 GDI+ Save 例外；用預設路徑或 Windows 可寫路徑）
bash tools/gui/gui.sh click X Y [right]
bash tools/gui/gui.sh dclick X Y          # 雙擊（倉庫存入）
bash tools/gui/gui.sh drag X1 Y1 X2 Y2
bash tools/gui/gui.sh key '{ESC}'          # SendKeys 語法：{ENTER} {TAB} 一般字元
bash tools/gui/gui.sh fg click X Y         # 前景模式備案（背景點擊沒反應時）
bash tools/gui/gui.sh end                  # 用過 fg / max 後還原前景視窗與游標（背景模式跑了也無害）
bash tools/gui/gui.sh seq "click 763 760; wait 400; shot"   # 同一個行程連跑多個動作（快）
powershell.exe -NoProfile -ExecutionPolicy Bypass -File tools\gui\stat.ps1   # （WSL 要用 "$(wslpath -w tools/gui/stat.ps1)"；Windows / Git Bash 直接給 Windows 路徑，在專案根目錄執行）OCR 讀 HUD → 一行 JSON（等級 / HP / MP / 寵物 / 地圖座標），不用看圖、不搶焦點
uv run --no-project python tools/gui/bench.py [--ab --old-dir 舊版目錄 | --srv-ab | --server | --soak] [-n 5] [--only stat,ocr_zooms]   # 唯讀量測各指令耗時（中位數 / min / max）；--ab 與舊版交錯並比對輸出、--srv-ab 一次性 vs 常駐 server 交錯、--soak 長跑看 GDI / 記憶體；只在沒有任務在跑時用
uv run --no-project python tools/gui/test_binarize.py   # ocr / stat 二值化（LockBits）與舊 GetPixel 版逐位元組比對（離線）；test_netwatch.py = netwatch 三態 mock 測試；test_errlog.py = errlog 多程序寫入；其餘離線測試：test_winenv_server.py（server 協定）、test_quest_fight.py、test_ass.py（皆 `uv run --no-project python tools/gui/<檔名>`）、test_guard.ps1（Guard）
bash tools/gui/mirror.sh                   # 給使用者看的即時畫面鏡像視窗（DWM 縮圖：幀數同遊戲、CPU ≈ 0；可縮放、右鍵 / 標題列選單置頂）
bash tools/gui/gui.sh pixel "X,Y X,Y"      # 背景截圖讀像素顏色（腳本判斷畫面狀態用，例：遇敵開關）；seq 裡用 X,Y/X,Y
bash tools/gui/gui.sh seq "click 1340 65; waitpix 1500 1290,97,197,73,49; ifok click 259 314"   # 輪詢到面板出現（點顏色符合）才點下一步，取代固定 wait
bash tools/gui/gui.sh seq "click 459 456; waitstill 4000"   # 點地面走路後等鏡頭停下來（剛好等到走完）
uv run --no-project python tools/gui/walk.py 1000 81 66 [--exit 1005]   # 走到某地圖座標：OCR 讀起點 → maps.bin 自動找路 → 連點 + waitstill → 終點驗證（--exit = 終點是出口）
uv run --no-project python tools/gui/walk.py --path "1000:86,88 84,81 83,73 81,66" [--exit 1005]   # 照手動 waypoint 走（沒有通行格資料的圖用）
uv run --no-project python tools/gui/walk.py --plan 1000 81 66 [--from 92,99]   # 只印找路結果（每段要點的截圖座標），不動
uv run --no-project python tools/gui/heal.py [--spot 波拉島] [--watch --hp 40 --mp 20 --every 15]   # 回村補血再回練功點（約 21～24 秒）；--watch 看血條比例（%）自動補（watch 活著時讀 state.hud 的 hpPct / mpPct，0 次額外 stat；不可用退回現場 stat；疑似驗證視窗暫停）
uv run --no-project python tools/gui/heal.py --no-return   # 補完血停在醫院，不傳回練功點、不開遇敵（解任務被打飛後用）
uv run --no-project python tools/gui/quest.py --solo --task 任務名   # 單人逃跑：遇怪按逃跑，到 NPC ESC 對話框退出碼 20，被打飛退出碼 21；--fight = 戰鬥步按自動戰鬥，退出碼 0 才是打贏（35 沒贏 / 36 不確定 / 33 對話無進展 / 34 不同圖，見 /psa-quest-solo）
uv run --no-project python tools/gui/team.py status|check|disband   # 隊伍狀態（唯讀）/ 檢查 1 隊長 + 4 隊員（0 = 符合）/ `form` 快速組隊（0 = 已組好，已組好時不點；41 要 `--regroup`、42 要 `--login-all`）/ 解散（當前須為隊長；隊長標 2026-10-12 起是小「L」，舊紅「隊」字也認，實機 rc 0）；退出碼 40～47 見 ui/team.md；名字用 namematch.py 整名樣板比對（`namematch.py learn|read|list`，見 ui/team.md）
uv run --no-project python tools/gui/char.py current|switch DKBO2|ensure DKBO   # 當前角色：唯讀讀取 / 切過去並驗證（點前 namematch 確認名字 + 線上，點後等加載 → HUD → 重開面板確認；成功寫 current-char.json；最後一行 JSON 含 changed）；退出碼 60～65 見 ui/team.md；不會自動切回 DKBO，呼叫端負責 ensure；`--timing` 看分段、ensure 有 watch 名牌快路徑（1.1 s）、可 import（char.LAST）；耗時與條件見 ui/team.md；離線測試 test_char.py（假面板在 fake_switch.py，test_team 共用）
uv run --no-project python tools/gui/grind.py start --spot 地雷區2|auto|here [--heal] | ensure | check | follow [--trans 1] [--until-level N] [--stop]   # follow = 常駐依等級自動換練功點（見 psa-grind-start）； 開始 / 恢復練功：char.ensure 隊長 → 關遇敵 → team.check/form（2026-10-12 起前兩步合併成一次開切換面板 leader_team_read，見 ui/team.md） → [start：選點傳送] → 外掛一次讀 5 人（快速 + 自動戰鬥）、只改不對的 → 開遇敵 → 30 s 內看到 2 次 EXP 橫幅才算成功；check 唯讀；ensure 約 25 s；退出碼 50～58 見 grind.py 檔頭；點表 spots.py（唯一來源 ui/transfer.md）；最後一行 JSON + tools/.cache/grind.json；不要和 heal --watch / petwatch / quest 同跑（退 8）
uv run --no-project python tools/gui/ass.py pet all normal 防禦 [--dry-run] [--no-resume]   # 5 人（或 DKBO,DKBO3）戰寵「一般動作」一次改：關遇敵 → 逐人讀 / 改 / 讀回 → grind ensure 恢復掛機；選項依 OCR 文字找，找不到退出碼 12（ui/ass.md）
uv run --no-project python tools/gui/pet.py list [--role DKBO|all] | set-state DKBO 迪基格斯 出戰|等待|騎乘 | rest-all [--keep 瑪斯貝卡] [--only 名,名] [--dry-run] | store DKBO 迪基格斯 [--depot personal|public] [--allow-slot1] [--allow-mount-store 名字（只有使用者當次明講才用）] | take DKBO --depot personal --pet 名[ --expect-level N] | --index N --expect 名|--expect-growth 字串|--expect-level N（**不准盲取**：--index 一定配 --expect-*，取前讀該格核對）   # 寵物面板：list 唯讀（5 人 × 每格 名字 / 狀態 / 等級；2026-10-14 字形樣板後 5 人各 2 隻掛機中 14～17 s〔舊 22～27 s〕，EXP 橫幅蓋住名字框時每 0.3 s 重讀）/ set-state 只點 1 次狀態鈕並讀回確認 / rest-all 交寵物任務前「出戰的非騎寵」全改等待（`--dry-run` 只列不點）；騎寵（瑪斯貝卡 / 名字像它 / 狀態=騎乘）一律不動（73，要動加 `--allow-mount`）；鎖定戰寵 → 74（不自動去外掛解鎖）；戰鬥中 → 78（`--pause-encounter` 才關遇敵等戰鬥結束再開回）；名字對不上 → 72；退出碼 70～78 見 pet.py 檔頭；名字 / 等級用 petmatch.py 圖樣板（學出來的，存 tools/.cache/pet-tpl/；`--no-learn` 不學；2026-10-13 起等級單字樣板讀檔時自動清掉錯標籤污染〔prune_digits〕、OCR 共識值要跟樣板認得的字不矛盾才採用 / 學，讀不準 None 不給錯值）；離線測試 test_pet.py（假面板 fake_pet.py）；**store / take（P7，2026-10-11 實機各 1 次）**：store 硬性禁止（73、零倉庫點擊）名字是 / 像騎寵（含 OCR 錯字）、狀態=騎乘、第 1 格（`--allow-slot1` 才放行）、名字讀不出來；進倉庫分頁後再驗「倉庫特徵 + 子分頁 + 縮圖簽名（防補位換人）+ 按鈕底色 + 按鈕 OCR 文字」才單擊存入鈕 530,697（存入戰鬥 / 騎乘狀態寵物會跳確認視窗，驗文字後單擊「確定」一次）；take 倉庫卡有名字（名字框會顯示選中卡的名字），有 `--expect` 取出前後都驗、不符不自動存回；驗證失敗不重點（76）、倉庫 / 寵物欄滿 77、按鈕 / 分頁 / 簽名不符 75；取出的寵物預設等待（要出戰另跑 set-state）；store 約 8 s、take 約 9 s；**掛機中（遇敵開）store / take 一律加 `--pause-encounter`**：2026-10-11 實機不加時 take 點了取出沒反應（戰鬥中操作被吃掉，rc 76、沒副作用），加了就 rc 0；騎寵位縮圖只比內側 3 欄（選取光暈會蓋到最右欄，舊版誤報 76）
# 共用模組（P1～P8，只被上面幾支 import，不直接跑）：spots.py = 練級傳送點表（唯一來源，heal.SPOTS 就是它的 HEAL_SPOTS，9 點）；uikit.py = 面板規格 / safe_click 禁區保護 / preflight / 共用退出碼 / snap；charstate.py = current-char.json 旁路檔（netwatch 重登時 clear）；namematch.py（角色名）/ petmatch.py（寵物名、等級）/ digitmatch.py（HUD 數字）= 學出來的圖樣板比對；petglyph.py = 名字框成長字串 / 倉庫卡白字（名字、成長字串）/ 綠字等級的字形樣板（種子 fixtures/pet_glyph_tpl.json + 執行中學；pet.py list / depot-list / 找卡 / 卡片等級先用它、讀不出才 OCR；倉庫卡不用選卡就讀得到，掛機中選卡會被戰鬥結束刷新跳回第 1 格；`--no-glyph` 關；見 ui/pet.md「字形樣板讀字」）；petimg_match.py = 寵物格 / 倉庫卡縮圖比知識庫頭像認物種（**2026-10-14 晚起 pet.py 改「名字為主」：名字框 / 卡片白字讀到物種名就採用、不跑縮圖，縮圖只在名字讀不出時補**；以下規則用在名字讀不出的格 / `--img-first`）（候選限定 judge + 遮擋偵測；名字 / 成長字串當第二道確認，衝突 → 不確定 72；沒名字字串沒登錄時縮圖可升為物種；被浮字蓋住等它消失重拍、仍蓋住時只比沒蓋住的列〔區塊比對，門檻較嚴，只跟文字互相確認 / 抓衝突，不單獨升為身分〕；開集只給 list 顯示 img_guess；`--no-img` 關；見 ui/pet.md「縮圖為主」）；itemname_match.py = 背包 / 倉庫格「顯示道具名」白字整名樣板（學出來的 tools/.cache/item-name-tpl/，彈窗核對過 / OCR 精確命中 Item 表才學；同名每欄各一個變體），**2026-10-14 起 bag.py 道具辨識以它為主**；itemimg_match.py = 背包 / 倉庫格縮圖比 GameClient 道具圖（tools/extract/item_images.py 抽圖），名字沒認出的格才用（bag.py 的 find / find_items / team_read / list / find_item；`PSA_ITEM_MATCH=auto（名字 → 縮圖 → OCR）|name|iconocr（舊 auto）|icon|ocr`；動作類照舊彈窗核對；見 ui/bag.md「道具辨識以名字為主」與其後一節）；兩者共用比對核心 imgmatch.py；縮圖截圖共用 `uikit.shot_getter`（離線測試環境一律不截真畫面）；ass.set_many({角色: {項目: bool}|None}) = 一次開外掛面板逐人讀 / 改（grind 用；select_role 內建等遮擋 + 重試；選角色時面板被遊戲關掉（斷線 / 隊員上線）→ 重開面板再選最多 2 次，仍不行 rc 6；頂部跑馬燈吉祥物蓋住 DKBO3 時不點、等它消失，set_many 先做後面的人）
# relogin.py：主動全員重登（設置 → 全員登出 → 確認 → 登錄 → 一鍵全登 → team.check / char.ensure；`--confirm` 才動、`--dry-run` 唯讀；退出碼 100～108；用於伺服器端卡死，見 ui/network.md；`--stuck` 起始畫面也收巡路中 / 快速戰鬥 VS 牌，questrun 卡住自動重登用）；test_relogin.py 離線測試
# netwatch：重登成功後自動 `grind.run('ensure')` 一次（失敗只記 errlog，不重試；`netwatch.py --no-grind` 關閉）
uv run --no-project python tools/gui/pet.py store-many --role all --pets 迪基格斯,瑪斯貝卡 [--depot personal|public] [--allow-mount-store 瑪斯貝卡] [--skip-missing] [--pick first|last] | take --pet 名 | take-many --role all --pets 朵拉比斯 [--depot ...] | take-many --depot public --plan "DKBO2:克邦凱斯,DKBO4:#34/7/4/8~7,DKBO:朵拉比斯@126"（`~N` 格號提示：撞號時指定哪張，取走前面的卡自動 -1，不符以身分重新定位、唯一才取，2026-10-14）| set-state-many --role all 朵拉比斯 出戰 | learn-species DKBO2 1 布拉奇多斯 --confirm-growth 49/9/8/2 | depot-list --depot public[,personal] [--role DKBO2,DKBO3] [--candidates 物種,…]（唯讀：倉庫卡片 + 各物種張數，只選卡）   # 名字框讀不出（40/9/6/5 被 OCR 讀成「姍」，2026-10-14）：先加讀 -Zooms 5,6，仍不行 → unreadable + 候選字串，「候選已登錄 + 縮圖同物種」才當該物種（store / take 可用），learn-species 對讀不出的格也可用（第 2～5 格、等待、非騎寵）；見 ui/pet.md； 批次存取（2026-10-11，離線驗證、實機待驗）：同一個 session 直接點左欄頭像換角色連續存 / 取（黃框 + 頭像名字驗證在 select_role；每次存取前都現場驗倉庫分頁 + 個人 / 公共子分頁）；take --pet / take-many 不用格號，現場逐張選卡讀名字找；**沒名字的新寵物**（剛抓到的，名字框顯示成長字串如 49/9/8/2）list 顯示 `?(49/9/8/2)`，物種要先 learn-species 登錄（縮圖簽名 + 成長字串，登錄檔 tools/.cache/pet-tpl/species.json）才能用物種名找 / 存 / 設狀態；抓寵後 `pet_catch.py` 的 register 階段會依「誰抓的」自動登錄；同系換色版（卡坦 4 鯊 / 4 雞）加共用旗標 `--candidates 物種,物種…`：縮圖只在任務候選之間相對比較（inlier + 主色都同意才算），跟登錄檔矛盾 / 沒把握 → 不認（72，不亂分）；store 後驗證改成「空格數 + 倉庫張數 + 逐張找得到」（#84 不再誤報 76）；見 ui/pet.md
uv run --no-project python tools/gui/pet.py reset-name [--role all|DKBO2,DKBO3] [--slot N] [--dry-run] | depot-fix-names --depot public[,personal] [--role DKBO|all] [--limit N] [--dry-run]   # 還原名字（2026-10-14 使用者實測；實機 reset-name 15.7 s / depot-fix-names 1 張 57.7 s，皆 --pause-encounter）：名字框是成長字串的寵物 → 鉛筆 700,180 →「修改名字」視窗驗標題 / 沒有費用字樣 / 輸入框空 → 確認 607,520 → 重讀名字必須是 Monster 物種名；費用字樣（鑽石 / 石幣…）→ 取消 822,520、退出碼 67 停手（鐵則 3），其他失敗 66；store / store-many 存倉前自動先還原（`--no-rename` 關）；depot-fix-names = 倉庫成長字串卡取出 → 還原 → 存回原倉庫（寵物欄沒空格就跳過列出）；之後辨識**名字為主**（`--img-first` 回縮圖為主）；見 ui/pet.md「還原名字 + 名字為主」
uv run --no-project python tools/gui/rebirth_pets.py [--trans N] [--mount-species 布拉奇多斯] [--battle-pet 朵拉比斯] [--catcher DKBO2] [--count 5] [--store-mount 瑪斯貝卡（使用者當次明講才用）] [--from 階段] [--to 階段] [--dry-run] [--confirm-buy-catch（使用者規定騎寵用石幣「+」買可抓捕數，每個 50,000）]   # 轉生後寵物重整一行跑完：preflight → boxes → store → catch → distribute → ride → battle → lock → cleanup；戰寵取 Lv1（同名多隻讀不出等級 → 逐隻取出驗 Lv1、不對存回）、禮盒 bag 95 自動重試；退出碼 100～109；**只有離線測試（test_rebirth_pets.py），外掛捉寵 / 鎖定 / 拆分誘餌的 OCR 框待實機量**；見 psa-pet-quest SKILL.md「轉生後寵物重整」；2026-10-13 三轉實跑寫回（rebirth bow16 / boss10 地圖判斷、preflight 關遇敵 / form 先 check；rebirth_pets 格號 / 漏段 / 雷龍系 / 面板殘留 / 可抓捕數 0）見 ui/rebirth.md
uv run --no-project python tools/gui/bag.py store|take all|DKBO2,DKBO3 名稱 --depot public [--skip-missing] [--all-copies]   # 多人存 / 取同一道具：背包面板只開一次逐人切頭像（2026-10-12；沒有的人 --skip-missing 略過；--all-copies = 不疊加的同名多格全存，千年龜的殼 13 個實機 4 分 49 秒）
uv run --no-project python tools/gui/bag.py list all | purge all|DKBO2,DKBO3 --names 名稱,名稱 [--dry-run]   # list 唯讀列每人背包 + 空格；purge = 刪除管理批次刪：只勾名單內（精靈王之弓 / 四大洞窟產物等 PURGE_FORBID 永不勾）、像素勾選 = 目標、提示窗清單是名單子集且條數相符才按確定，否則 X 停手（2026-10-12 實機 4 人 29.8 s；見 ui/bag.md）
uv run --no-project python tools/gui/pet_catch.py --lock 騎寵,戰寵 [--battle-pet 朵拉比斯] [--mount-species 布拉奇多斯] | --unlock 戰寵 | --autoswap on|off | --verify-battle | --assign ... --stages register [--reuse-setup] [--poll 秒] | --catch-off [--roles DKBO2,DKBO3]   # 2026-10-14：register 不登錄第 1 格 / 騎寵 / 抓寵前就在的寵物（catch-pre.json 快照 diff），新寵物讀不出 → 16；setup / wait 失敗自動取消自動抓寵； wait 預設第一次 k×20+20 秒、之後 60 秒；--reuse-setup 第 2 批沿用捉寵設置（讀回驗證照舊）；register = 抓完依抓寵者登錄成長字串 → 物種（縮圖候選內交叉驗證，矛盾退出碼 15）；外掛鎖定重勾（下拉 OCR 讀字選、讀回欄位與勾選，每人順序不同 #257）/ 自動轉換戰寵；外掛面板只開一次
**多人操作一律用批次版（2026-10-12 使用者要求）**：面板開一次 → 左欄 / 左上頭像切角色 → 連續做完 → 關一次；倉庫分頁 / 公共子分頁只切一次。不要寫「開面板 → 角色 1 → 關 → 開 → 角色 2 → 關」。實測前後（actions.log 07:58～08:01 take 一人約 15～20 s、12～14 下點擊 → 批次假面板 4 人 23 下，預估一人 7～9 s）見 ui/pet.md「批次取出」。
uv run --no-project python tools/gui/exp.py read|eta [--role all|DKBO,…] [--target 131] [--interval 300] [--from-history] [--dry-run]   # 唯讀：人物資訊面板開一次逐人讀 轉數等級 + 目前經驗/本級所需（底部 EXP 條 + 經驗表交叉驗證，讀不出給 None）；eta 讀兩次算每分鐘經驗與到目標等級的預估時間，歷史寫 tools/.cache/exp-history.jsonl；快戰掛機中不停遇敵；退出碼 100～102（2026-10-12 實機）
uv run --no-project python tools/gui/bag.py hp all | find DKBO 名稱…   # 唯讀：5 人 HP（背包頁逐人點頭像讀「目前/最大」，約 8 s，questrun 補血檢查用）/ 道具在哪格（空格用像素判；「顯示道具名」被關會點開 1 次；2026-10-12 實機）；其餘 use / take / store / drop 見 ui/bag.md
uv run --no-project python tools/gui/rebirth.py [--trans N] [--from 階段] [--to 階段] [--dry-run] [--keep-old-weapon] [--confirm-rebirth] [--pet-action 忠犬]   # 漆黑洞窟轉生任務（2004～2008）一行跑完：preflight → accept（questdetail 接任務，含選單頁翻頁）→ enter → boss10 → bow16 → swap → heal → boss20 → rebirth → cleanup；37 / 38 BOSS 戰後處理、精靈王 39 對話 OCR 判斷（寵物轉生擋下）、換弓丟舊武器名稱防護、龍王的守護取 / 吃 / 存回；卡住（quest 19 / 42）自動全員重登（stuckrecover，每階段 2 次）、轉生獎勵寵三轉起用前後寵物欄 diff；退出碼 80～89 + 97 接任務 / 98 獎勵寵不確定（bag.py 90～96）；**bag.py / petdrop.py 實機未驗證**，離線測試 test_rebirth.py / test_rebirth_steps.py；見 ui/rebirth.md
uv run --no-project python tools/gui/petwatch.py [--once [--apply]] [--interval 30] [--level 77] [--pet 金布伊 --pet-slot 3] [--back 朵拉比斯] [--max-tries 2]   # 監測 5 人練功寵等級（預設金布伊第 3 格，--target-level 同義），**連 2 輪**讀值 ≥ 門檻（相差 ≤ 2）才換回戰寵（預設 轉生後的朵拉比斯；轉生前舊流程 --back 迪基格斯）。換回（2026-10-13 改）= 到門檻的人一批：遇敵關一次 → 外掛取消鎖定戰寵 → pet.py set-state-many 戰寵出戰（依名字找格）→ pet_catch relock 重勾鎖定戰寵（下拉 OCR 讀字選，不再盲點第 N 項；舊版下拉順序每人不同 → DKBO2/3/5 鎖回金布伊、每輪關開遇敵無限迴圈）→ 全部做完開回遇敵一次；某人失敗記原因（74 = 鎖定戰寵還勾著 → `pet_catch.py --unlock 戰寵`）、跳過他做其他人，同一人失敗 --max-tries 次就放棄（errlog、退出碼 4），不無限迴圈；`--back-slot` 只收不用（相容）；等級讀不準回 None（拿掉單組 OCR 退路）（維持原地遇敵；補血檢查 2026-10-13 起**預設關**，`--heal` 才做（練功不自動補血），`--no-heal` 相容 no-op；加 --heal 時不要和 heal.py --watch 同跑）
```

操作 log：click / dclick / drag / key / max / end（含 seq 裡的）以及 walk.py / heal.py / quest.py 的動作，都會寫一行到 `tools/.cache/actions.log`（只留最新 2000 行，不進 git；寫入程式 `tools/gui/actlog.py`）；同時按小時分檔 `tools/.cache/actions/YYYY-MM-DD_HH.log`（不截斷、保留 14 天，舊細節查這裡）：`uv run --no-project python tools/gui/actlog.py show [--date 2026-10-13] HH:MM-HH:MM [--grep 字串]`（跨小時檔合併、結束早於開始＝跨午夜），背景記錄用，psa-hud pane 不顯示它（pane 顯示下面的錯誤 / 改進紀錄）。想附註用途：`PSA_NOTE="對話確認" bash tools/gui/gui.sh click 948 461`（Python 呼叫 `walk.gui(..., note="...")`）；shot / pixel / wait* 不記。

**即時進度區**（psa-hud pane，狀態行與錯誤紀錄之間，每 3 s 讀 `notes/quest-events.log` / `tools/.cache/actions.log` / `state.json`，≤6 行，讀不到顯示「—」）：`練功中：<點>（快速戰鬥）`（取代任務行；最後一筆 questrun 之後 actions.log 最新的「原地遇敵」是「開」、state 沒有 enc_on=false、地圖沒離開最近一次「grind 傳送到 X id」、無 state 時遇敵開在 2 小時內；快速戰鬥 = 各角色最後一筆 ass 快戰紀錄全為開，沒紀錄不標；有更新的 questrun 行就回任務顯示；session 標題同步成 `PSA｜練功中 <點>`，純函式 `grindActivity`）或 `任務：<名> 進行中|已完成|失敗 rc=N|接手中（questrun rc=N，questrun 失敗後還有別的事件行）`（沿用 titleFromLog；名字只取本 run「開始：任務」行之後）、最近 3 行事件（去日期 / 截圖路徑 / [questrun]，每行 ≤56 字）、`動作 HH:MM:SS 描述（N 秒前）`（超過 120 s 標黃「閒置 N 分」）、有 alerts / verify_suspect 時一行紅字警報。純函式 `progressLines`（`tools/mods/psa-hud/hooks/register.tsx`），改完要 `/reload-plugins`；測試 `claude plugin test tools/mods/psa-hud`。

即時狀態監看（第 2～7 階段已完成）：psa-hud 的 session.start 會自動 spawn `watch.py`（只管自己 spawn 的子程序：結束退避 2/5/15/30/60 s 重開、連續 5 次跑不到 30 s 停並顯示「監看啟動失敗」、退出碼 3 / 6 只讀、卡住 10 s（starting 45 s）return() 後重開），pane 頂端狀態行每 1 s 讀 state.json（label + 「N 秒前」>3 s 才顯示 + 監看未執行 / 另一平台 / 啟動失敗提示）；`/psa-hud watch on|off|status` 開關（持久化 `tools/.cache/psa-hud.json`，off 會呼叫 `watch.py --stop` 且不再重開；兩平台同時開 session 時只有一邊有即時狀態，另一邊在對方結束後要 `/psa-hud watch on`）。`/psa-hud` / `/psa-hud on` 開 pane 並立即更新，`/psa-hud off` 只關 pane（監看照跑）；熱重載（`/reload-plugins`、存檔）後 session.start 沒重發時，下一次 `/psa-hud` 指令會補初始化（路徑、計時器、監督 watch），pane 畫不出來時至少顯示紅字「psa-hud 繪製失敗：原因」，不會整片空白（2026-10-13 修：jsxFactory 是 `h`，render 裡箭頭函式參數不可叫 `h`，否則有提示行時整個 pane 空白）；等級字串沒有數字（寵物等級 OCR 讀成 `o級`）顯示 `?級`；2026-10-13 起 watch 只收「N轉M級」格式的 OCR 等級（`Watcher.hud_value_ok`，不合格 = 沒讀到，pane 顯示 `?`），寵物等級 digitmatch 切字先丟掉貼框頂的頭像白塊（`digitmatch.EDGE_BLOB_FIELDS`，根因：二轉後換的寵物頭像白臉掉進 plv 框頂、與「轉125」合成一塊 → 認不出 → 退回 stat OCR「o級」；改完要重開 watch〔`/psa-hud watch off` → `on` 或下個 session〕才生效）。等級 / HP 行：watch 活著時讀 `state.hud`（watch 每 3 s 讀 HUD：`digitmatch.py` 字元樣板比對第一順位〔樣板 `tools/.cache/digit-tpl/<版面>.json`，約 95 ms〕，讀不出的欄位才用 stat.ps1 補，`state.hud.src` 標每欄來源 digit / ocr；每分鐘最多一次用 stat 當標籤自動補樣板〔兩張圖相同、與 digit 讀值一致或 digit 為 None、與既有樣板不衝突、每字最多 6 變體〕，沒有樣板的版面〔如 1920×1017〕先全走 stat 並背景累積，不動視窗；`watch.py --bench N` 會印來源計數；只在主畫面 / 行走 / 快速戰鬥讀；被蓋住、完整戰鬥、最小化時保留舊值並標 stale，pane 顯示「（原因 · N s 前）」，欄位帶各自時間戳），HUD 此時不再 spawn stat.ps1；**頭像下方 buff（2倍智慧果 / 龍王的守護）**：watch 每 12 s 在 idle / walking 另送一次 675 點 pixel（約 86 ms，唯讀）交給 `bag.buff_classify`，寫 `state.hud.buffs = {v: ['exp'|'dragon'…], ts, stale}`（沒 buff = `[]`；面板 / 戰鬥 / 對話蓋住時不讀、保留舊值並 stale = true，讀失敗也保留），pane 等級行尾顯示 `|  EXP×2 龍王（不遇敵）`（stale 每項加 ?）；**遇敵狀態行**（`encText`，等級行下一行）讀 `screen.enc_on`：true 綠字「遇敵中」、false 黃字「不遇敵」（掛機可能停了）、戰鬥 / 面板蓋住時 enc_on=null 沿用最後已知值並加 ?；有龍王 buff 時並列說明（遇敵中 + 龍王 → 「推測實際不遇敵」，未實測），練功中那行加 `＋EXP×2`（純函式 `buffText`）；watch 不在才退回 15 s 一次的 stat.ps1。手動：`uv run --no-project python tools/gui/watch.py` 常駐（單例鎖；同平台已有 → 退出碼 3、別平台 → 6），每 0.5 s 只送 `gui pixel / info -NoRestore 1`（**零輸入**、最小化不還原），把畫面狀態寫進 `tools/.cache/state.json`（內容變了才寫 + 每 1 s 心跳）。讀取：`watch.py --get [--max-age 2]`、`--status`；結束：`--stop`；跨平台殘鎖：`--unlock`。Python 讀取 API 在 `tools/gui/watchstate.py`（`fresh()` / `screen(max_age, after=)`）。**state 只能用來顯示 / 決定要不要再看，不能當點擊依據；idle 不代表沒有驗證視窗**（點擊前照舊現場讀圖）。**警示（第 5 階段）**：watch 只標出、不點任何東西：畫面 `unknown`（登入 / 選角 / 載入畫面 / 全黑轉場 / **認得的面板**除外）連續 10 s → `alerts.unknown_long` + `flags.verify_suspect`（HUD 紅字；觸發時 watch 自動唯讀 `gui shot` 存一張到 `tools/.cache/watch-alerts/unknown-<時間>.png`〔只留最新 10 張〕，路徑填進 `alerts[].shot` 與 errlog；寫 errlog 一筆，連續 5 s 回到已知畫面自動清除並補 fix）；讀 `notes/quest-events.log` 啟動後新增行，轉述 quest 的「Clef 判斷可能是答題 / 驗證視窗」與「連續 3 次遇到不認得的畫面」（`/psa-hud ack` 或 `watch.py --ack` 清除）；`annotate` 上線的：提示視窗（黃字）、登入畫面、選角畫面、載入畫面（`SIG_LOADING`）、全黑轉場（HUD 各處 10 點全暗，只有合成測試沒有實測樣本）、遇敵鈕（`screen.enc_on`）；通用彈窗（提示 / 數量輸入 / 道具詳情疊在面板上）與驗證視窗沒有可靠特徵、不上線（仍是 unknown，10 s 後報警，這是刻意的）。
**面板辨識（2026-10-11）**：`screen.state = panel` + `screen.panel` = 名稱，label「面板：寵物」。認得的面板：pet 寵物（含倉庫 / 圖鑑分頁）、bag 背包、ass 外掛、team 組隊、qteam 快速組隊、switch 切換角色、setting 設置、transfer 傳送（地圖傳送 / 練級 / 便捷）、quest 任務詳情。特徵 = 右上 ✕ 紅圓（tol 40；pet / team / qteam / switch 沿用 uikit 量好的，ass 橘 ✕）必中 + 該面板 8 個框 / 標題板 / 邊緣點至少 6 個在 tol 16 內（`screen_sigs.PANEL_X / PANEL_PTS`，用 tools/.cache 767 張樣本學出，全部樣本 0 誤判；樣本與凍結結果在 `fixtures/panel_px.json`，`make_fixtures.py` 產生）。**面板上疊已知彈窗（2026-10-12）**：模態彈窗會把底下壓暗約 ×0.5；底下是壓暗的背包 / 寵物面板，而且彈窗是拆分數字鍵盤、「數量輸入」或確定 / 取消確認窗（丟寵 / 存入戰鬥寵）時，annot = `popup_*` + `over_bag|over_pet`，算已知畫面、不報警（label 例：面板：背包＋數量輸入視窗）。其他彈窗（驗證視窗、道具詳情、網路異常）疊在面板上仍是 unknown，10 s 照報（`screen_sigs.popup_over_panel`，樣本 `fixtures/popup_px.json`；errlog #243 #244 #254 #261 #264 的誤報都是這類彈窗，不是切換面板）。**沒有樣本、不認得的**：人物 / 角色資訊、圖鑑 / 商城 / 家族 / 排行榜 / 信箱 / 聲音等小面板、面板上疊彈窗（見 ui/README.md）。腳本用的 `uikit.screen()` / `quest.read_screen()` 仍只讀舊的點（只認切換面板），要連新面板一起判斷用 `uikit.screen(full=True)`；`uikit.watch_preflight_ok` 遇到 watch 認得的「其他面板」不走快路徑（腳本行為不變）。
**主畫面判斷改多組（2026-10-11）**：idle = 外掛紅字（舊 SIG_HUD）、底部圖示列 6 點（切換～外掛七顆圓鈕的框，允許 1 點不符）、右下按鈕區 6 點，任一組命中；暗地圖 / 特效蓋住紅字時另外兩組不受地圖影響。**刻意不用左上血條框 / 右上地圖名框當單獨判據**：寵物 / 背包等大面板開著時它們仍露在外面，會把沒認得的面板（含驗證視窗）當主畫面；底部圖示列與右下按鈕會被所有大面板蓋住。
**follow 抵達判斷**：換點傳送失敗（EXIT_TELEPORT）後以 HUD 地圖 ID 對 spots.SPOTS 為準（`follow.arrived_at`），ID 讀不到才退回地圖名 OCR（連續 4 字吻合且唯一）；ID 不吻合 = 沒到 → on_blocked 學門檻（2026-10-13 海底通路被誤認五兄弟洞窟的修正）。

**follow 的互動**：`follow.py` 每輪先看 watch 的 `screen.state == panel`（使用者開著面板）→ 暫停這一輪（不讀 HUD 等級、不算「讀不到等級」、不點任何東西，最多 30 分鐘；之後照常跑）；`verify_suspect` 旗標觸發時現場讀 `uikit.screen(full=True)`，主畫面 = 誤報繼續、面板 = 暫停、不認得才退出 9。`heal.py --watch`、`petwatch.py` 每輪先看 state：疑似驗證視窗 → 暫停動作並印警告，**暫停超過 10 分鐘就停止（heal 退出碼 11，寫 errlog，不自動恢復）**；state 不可用時行為不變。errlog.add / fix 已改 O_EXCL 鎖 + 原子寫（多程序不互蓋，`test_errlog.py`）。**人物名 / 寵物名（第 7 階段）**：HUD 沒有名字，所以人物名 = 頭頂名牌 OCR（框 660,420,120x30、`-Light 200`）只在白名單 `tools/.cache/watch-config.json` 的 `chars`（`{"chars":["DKBO","DKBO2",…]}`，真名字母 O；舊設定寫 DKB0… 讀入時經 `charstate.display` 轉真名，不進 git）內完全比對；OCR 常把 DKB0 讀成「DKBO」，所以先正規化（全部 O→0、首字 0→D）；連續 2 次一致才採用，讀不到沿用舊值（`state.hud.name.stale`，HUD 顯示 `DKB0?`），完整戰鬥 / 對話 / 面板不讀；沒有白名單也沒有旁路 = `?`。旁路：切換**當前角色**的流程（點切換面板卡片）點完要呼叫 `uv run --no-project python tools/gui/watch.py --set-char DKB02`（寫 `tools/.cache/current-char.json`；watch 以它為主、OCR 核對，兩者不同時較新的勝出並標 conflict，HUD 顯示 `DKB05!`；ass.py 的 select_role 只切 ASS 面板的角色、不算）。寵物名：HUD 只有頭像，用 `watch.py --learn-pet 迪基格斯`（主畫面時、只讀 pixel）把當下頭像存進 `tools/.cache/pet-avatars.json`，之後自動比對，沒學過 / 太像 = `?`。注意：watch 強制用常駐 server（Windows 原生預設關也強制開；`PSA_GUI_SERVER=0` 才關）；除 pixel / info 外只多送 digitmatch.ps1 / stat.ps1（唯讀截圖 / OCR）。

錯誤 / 改進紀錄（psa-hud pane 顯示這個）：遇到錯誤、失誤、卡關（點錯、工具中斷、誤判、漏做、白等）時，**當下**用 `tools/gui/errlog.py` 記一筆；之後改了程式 / 流程 / 文件，再補上改進。沒改進的會在 pane 標「待改進」。
```
uv run --no-project python tools/gui/errlog.py add "錯誤描述" [--fix "改進"] [--source quest]   # 印出 #id
uv run --no-project python tools/gui/errlog.py fix <id|last> "改進內容"
uv run --no-project python tools/gui/errlog.py list
```
存 `tools/.cache/errlog.jsonl`（最新 100 筆，不進 git）；Python 裡 `import errlog; i = errlog.add(...); errlog.fix(i, ...)`。一筆寫一件事、寫具體（發生什麼 + 為什麼），改進寫「改了什麼檔 / 之後怎麼做」。
- 遊戲**不能最小化**（Unity 最小化不繪製）；每個指令遇到最小化會用 SW_SHOWNOACTIVATE 還原（不搶焦點）；**例外**：`gui.ps1 pixel|info ... -NoRestore 1`（watch 唯讀監看用）遇到最小化不還原，印 `minimized`、exit 3。放在其他視窗後面沒關係。
- **座標 = 截圖座標**：截圖固定縮成客戶區的 1/2（`-Scale 2`，不隨視窗大小變），click 內部 ×2。實測客戶區 2880×1659 → 截圖 1440×830。
- `ui/` 的座標只在這個大小有效。**每次開始操作先跑 `info`**，不是 2880×1659 就跑 `max`；`max` 後仍不同（換螢幕 / 解析度）時不要等比例換算（UI 縮放與錨點會變，例：1436×1644 時背包在 558,790），以新截圖重新目測。
- **1920×1080 螢幕**（`max` 後 `client=1920x1017`、截圖 960×508）：用 [ui/layout-1920x1017.md](ui/layout-1920x1017.md) 的座標；`stat.ps1`、`walk.py`、`heal.py` 會自動切換（`tools/gui/layout.py`）。
- 只有 `fg` / `max` 會讓遊戲佔著前景（使用者打字可能打進遊戲），之後要跑 `end`。習慣上任務結束仍跑 `end`，沒狀態時它什麼都不做。
- 背景模式 `dclick`（倉庫存入）、`key` 打字（含中文）都實測可用（2026-10-09）。`key` 語法：一般字元 = 打進輸入框；`{ESC}` `{BS}` 等 = 按鍵；`{a}` = 只按 a 鍵（快捷鍵用）。
- `gui.ps1` 必須保持 **UTF-8 with BOM**（PowerShell 5.1 讀無 BOM 檔會把中文當 Big5，整支解析失敗）。

## 移動：先用 walk.py（不要自己算座標點地面）
- **鏡頭高度一律拉到最左**（設置 → 畫面設置，見 [ui/setting.md](ui/setting.md)）：walk.py 的每格位移只在這個鏡頭下準，與視窗大小無關；滾輪會改鏡頭高度，**不要在遊戲畫面上滾滾輪**。走路 / 補血一直走錯格時先檢查這個。
- 要走到某格 → `walk.py <地圖> <x> <y>`；要走進出口 → 加 `--exit <下一張地圖>`；要點 NPC → 腳本裡用 `walk.npc_steps` / `walk.talk_npc`（直接點 NPC 會自己走過去開對話）。
- walk.py 做的事：先點引子 1215,18（換地圖後第一下左鍵會被吃掉）→ 讀起點（`walk.pos()`：現場 digitmatch 字元樣板比對約 0.1 s 為主，認不出 / 沒樣板 / 逾時才退回 stat.ps1 OCR；不讀 watch 的 state.hud，因為 watch 每 3 s 才更新、拿不到點擊之後的新值）→ 有 `knowledge/data/maps.bin` 通行格就找路
  （每段 ≤ 10 格、點擊不落在左側面板等 UI 上、離牆遠一點、點擊次數少的方向優先）→ 一個 `seq` 連點，每段之間 `waitstill` 等鏡頭停，
  某段沒動（`nomove`）就用 `ifok` 跳過後面 → 終點 OCR 驗證 → 沒到就從目前位置重新找路、改慢速逐段走（每段 OCR，沒動就格數減半）。
- 通行格對不上的圖（例：醫院 1005）會自動改成直線分段讓遊戲自己繞；固定路線可以用 `--path` 寫死 waypoint。
- 原地遇敵開著時隨時會進戰鬥（快速戰鬥只有頭上綠色 VS 牌）；戰鬥中傳送會被擋，走路會不會被擋未實測 → 要移動先關遇敵、等 VS 牌消失（heal.py 的做法），走完記得開回來。
- 常數（每格位移、最多格數、UI 禁點範圍、每格秒數）集中在 walk.py 開頭；規則說明見 [ui/home.md](ui/home.md)「走路」。
- 在 Python 腳本裡：`import walk`（同資料夾），`walk.walk_to(1000, 81, 66, exit_map=1005)`、`walk.walk_path(...)`、`walk.plan(...)`、`walk.prime()`（heal.py 是範例）。

## 功能索引（要做某件事時先讀對應檔）
| 要做的事 | 讀這個 |
|---|---|
| 認主畫面按鈕、收合、面板關不掉 | [ui/home.md](ui/home.md) |
| 5 個角色組一隊 | **先跑 `team.py form`**，非 0 再 **`/psa-quick-team` skill**（介面參考 [ui/team.md](ui/team.md)） |
| 開始 / 恢復練功（選練功區、傳送、開遇敵、5 人快速 + 自動戰鬥檢查） | **先跑 `grind.py start|ensure|check`**，非 0 再 **`/psa-grind-start` skill**（手動流程當退路） |
| 解散隊伍 | **先跑 `team.py disband`**，非 0 再 **`/psa-disband-team` skill**（介面參考 [ui/team.md](ui/team.md)） |
| 確認誰是「當前」角色 | [ui/team.md](ui/team.md) |
| 看角色屬性 / 抗性 / 潛力點 | [ui/role.md](ui/role.md) |
| 看任務進度、任務詳情、自動巡路解任務（`tools/gui/quest.py --task 任務名`；檢測方針：黃色「?」優先，否則追蹤列表任務名（每頁先標題樣板、沒中同頁 OCR；看 ▲ / ▼ 決定捲不捲；下緣被裁的卡先捲上來再點）核對再點；`ocr.ps1` / `findmark.ps1`；**預設模式任務 BOSS 戰打完先驗隊伍再停：退出碼 37 滿員 / 38 不滿（slice 時間到也延後到停手），`--no-stop-after-boss` 才連跑；任務 NPC 只有「再見」→ ESC、退出碼 40；`--hp-check-min N` 戰鬥後全隊 HP 偏低 → 41；殘留的已知面板（背包等）點 ✕ 關、不算驗證視窗；對話框內文 / 按鈕含轉生 / 封印 / 刪除 / 丟棄 → 不按、退出碼 39，確認後 `--allow-irreversible`**，errlog #68） | [ui/quest.md](ui/quest.md) |
| **單人逃跑解任務**（DKB0 單人跑 NPC、遇怪逃跑 → 組隊對話 / 打；紅暴 2031 只在 questrun 回 156〔沒有龍王的守護〕時用，平常 `questrun.py run 2031` 組隊打到底；`quest.py --solo / --fight`、`psa.py steps`、`heal.py --no-return`） | **`/psa-quest-solo` skill**（介面參考 [ui/quest.md](ui/quest.md#單人逃跑解任務questpy---solo----fight2026-10-10流程見-psa-quest-solo-skill)） |
| **1.82 任務驅動器**（`questrun.py plan / run <任務ID…>`，每任務只開一次詳情、自動巡路優先；**紅暴 2031**（2026-10-13，未實機）：前置 5 人 ≥80 級 + 耐久力回複藥（110）、龍王必要（沒 buff 就吃，都沒有 156 → 單人逃跑）、每步 `--stop-after-rewards 1`、步 6 kind=fight（隊長 HP 檢查 → 便捷傳送龍王守衛 → `--fight --step 6` → team.check）、完成後英雄的祝福存個人 / 龍王存公共（157）、`--drop-items 薩姆吉爾的首飾`（bag.purge）+ `--drop-reward 巴朵蘭恩`；交接先查外掛戰鬥設定（`ass.py battle all`：5 人自動戰鬥 + DKBO 人物首次動作 風的精靈 打勾，只改勾選，失敗 109，`--no-battle-check` 關）；龍王的守護**預設不吃**（`--dragon` 才吃，除彌生和日美子 / 猜謎三兄弟 / 恐龍博士 / 卡坦的願望（questdefs.NO_DRAGON）外都吃、`--dragon-all` 全吃；看 buff 人形圖示；剩的留 DKBO 背包、run 結束存回公共倉庫）；戰鬥設定 30 分內查過沿用；`--pet-turnin` 自動交寵物（恐龍博士 / 卡坦，未實機）、`--drop-reward X --confirm-drop X` 完成後丟 1 級獎勵寵；**任務之間不讀血量（2026-10-14 使用者定：`--team-hp-min` 預設 0，只看隊長 HUD HP；背包前置只讀空格；>0 才回舊行為讀全隊 + quest.py `--hp-check-min`）**；完成判斷不開任務詳情（quest.py「任務完成」或回 5 = 完成，時間到 / 模糊 = 下一片）；quest.py「提前結束」不開詳情直接下一片；VS 牌卡死（quest.py 42）/ 巡路卡住解不開（19）→ 自動 `relogin.py --confirm --stuck` 每任務最多 2 次；載入畫面（加載中 / 英文版 Loading 雙進度條，2026-10-14）不算不認得、最多等 60 秒，卡住 quest.py 43 → 重跑同一片（不重登）；quest.py 巡路座標 40 s 不動自動點地面解卡，3 次仍卡退出碼 19；交接先清殘留對話框 / 已知面板；任務 NPC 只有「再見」quest.py 40 / 信封發亮 → 背包滿刪白名單 + `mail.py claim` 續跑，不是背包問題 153、處理失敗 154（2026-10-13，未實機）） | [ui/quest.md](ui/quest.md) 的 questrun 段；**BOSS 戰後不滿 5 人**：questrun 38 / 21 自動跑 `bossretry.py`（落後者當隊長組 5 人回 BOSS 處全隊重打 → 切回 DKBO 重組 → check 滿 5 人；退出碼 140～147（147 = 重打前戰鬥設定檢查失敗）；`--no-boss-retry` 關；單獨：`bossretry.py run --track <追蹤標題> [--who DKBO3,DKBO5] | plan | status`；`--who` 2026-10-12 實機驗過）；**逐人驗**（`--verify risk` 預設：有風險事件〔30/32/38/21/41、bossretry、重登、交寵物〕的任務完成時當場驗，其餘 run 結束 / 依賴任務接取前批次驗一次；`--verify each` 舊行為、`off` / `--no-verify-all` 關；`--verify defer`（postrebirth / petquest 用）= risk 但 run 結束不驗，留給收尾 `status --role all` → `questrun.py verify <ID…> --role <落後者>`；沒完成 → bossretry --who，仍不行 108；唯讀 `questrun.py status --role all`）；**加速（2026-10-13 review 1013b，離線測試，未實機）**：`--rested`（petquest 練完已 rest-all → 交件前不重做）、追蹤卡片位置快取（上次的 y 標題列像素每點吻合才直接點，否則整輪掃描）、詳情捲動等待 0.8 秒 + 沒 ▲ 不往上捲 |
| **轉生後任務重做總控**（`postrebirth.py plan|run [--confirm-drop] [--from 段]`：盤點 → 成人儀式 → 彌生和日美子 → 紅暴 → 1.82 前段 → 清背包① → 1.82 後段 → 清背包② → 四大洞窟 → 恐龍博士 → 卡坦 → 猜謎三兄弟 → 收尾回地雷區；退出碼 170～176；未實機；questrun 段一律 `--verify defer`、petquest 帶 `--verify-defer`，逐人驗證延到收尾 `status --role all`，有落後者 `questrun.py verify` → bossretry 補，補不上才 176） | [ui/quest.md](ui/quest.md) 的 postrebirth 段 |
| **任務詳情讀取 / 接取**（1.82 各任務狀態、接取一個待接取任務；`questdetail.py status / list / accept`，退出碼 120～128；**詳情「傳送」鈕位置進行中任務是「重置任務」，只有腳本驗證後才點**） | [ui/quest.md](ui/quest.md) 的 questdetail 段 |
| 背包、道具、倉庫、材料圖鑑 | [ui/bag.md](ui/bag.md) |
| 看 / 改寵物出戰 · 等待（不碰存倉） | **先跑 `pet.py list` / `levels`（只讀等級）/ `set-state` / `rest-all`**（名字框是成長字串的先 `pet.py reset-name` 還原物種名）（沒名字寵物的成長字串 / 縮圖結果有跨程序快取，只用在這幾個指令，存倉 / 取出 / 丟寵照舊現場驗名；介面參考 [ui/pet.md](ui/pet.md)） |
| **交寵物類任務**（恐龍博士 2016 / 卡坦的願望 2019 / 猜謎三兄弟 3003：外掛自動抓寵、共用倉庫分配、練寵、交任務；轉生 / 封印書後要重做；總控 `petquest.py run 2016\|2019\|3003 [--confirm-buy-bait] [--confirm-drop]`，退出碼 160～169，未實機） | **`/psa-pet-quest` skill** |
| 寵物出戰 / 騎乘 / 休息、寵物技能 | [ui/pet.md](ui/pet.md) |
| 傳送到別的地圖 / 練級點 | [ui/transfer.md](ui/transfer.md) |
| 遊戲設定、離線時間 | [ui/setting.md](ui/setting.md) |
| 自動戰鬥、補血、抓寵、遇敵 | [ui/ass.md](ui/ass.md) |
| 聊天、信件、通知、排行榜、家族 | [ui/social.md](ui/social.md) |
| 商城、交易所、抽獎（多為紅區） | [ui/shop.md](ui/shop.md) |
| 「網路異常，是否重連?」提示、斷線後登入畫面（`tools/gui/netwatch.py`；已接進 quest / petwatch / heal --watch；點確定會回登入畫面 → 自動按「登錄」重登（使用者授權，只按登錄；欄位空 / 錯誤提示 / 連 3 次失敗才停手）） | [ui/network.md](ui/network.md) |
| 沒見過的畫面、答題驗證 | [ui/todo.md](ui/todo.md) |
全部清單與「依情境找」見 [ui/README.md](ui/README.md)。學到新畫面或新流程時，照 README 的「新增 / 更新規則」寫進對應檔並更新兩邊索引。

## 操作迴圈
0. （選用）先看即時狀態：`uv run --no-project python tools/gui/watch.py --get --max-age 2`（有 psa-hud 在跑才有；沒有 / 太舊就回退碼 1，照下面 shot 流程）。給你「現在是哪種畫面、等級 / HP、有沒有警報」的**參考**，**不能當點擊依據**：點擊前一律現場 shot / pixel；`idle` 只代表「沒偵測到已知視窗」，**不代表沒有驗證視窗**；`alerts` / `verify_suspect` 出現就立刻停手回報。watch 本身零輸入（只送 pixel / info / stat），由開 psa-hud 的那個 session 管理（單一管理者）；殘鎖（別平台 / 已死）用 `watch.py --unlock`，同平台擁有者還活著要 `--stop` 或 `--unlock --force`；兩個平台同時開 session 時只有一邊有即時狀態。
1. `shot` → Read 圖，先判斷**目前在哪個畫面**（主畫面 / 某面板 / 對話 / 戰鬥 / 驗證）。
2. **速度**：遊戲響應很快（實測傳送面板 / 分頁 / NPC 對話框 / 遇敵圖示都在 0.05～0.15 秒內出現；傳送 Loading 1.0～2.2 秒）；每次呼叫 gui.sh 要多花約 0.4 秒啟動 PowerShell（gui.sh 維持一次性；Python 長程序可用常駐 server 省掉，見上方「常駐 server」）。
   - 腳本裡能用 `waitpix`（等指定點變成某顏色）/ `waitstill`（等走路停）就不要固定 `wait`；`ifok` / `ifnok` 依上一個 waitpix 結果決定做不做，面板沒出現就不會點穿。
   - **換地圖後第一下左鍵會被吃掉**：先點 1215,18（狀態列空白）當引子（ui/home.md「走路」；walk.py `PRIMER`）。
   - **已知流程**（座標都驗證過）：用 `seq` 把多個動作串成一次呼叫，動作之間 `wait 150～500`，只在**分歧點**（要判斷畫面才能決定下一步）和**結尾**截圖。
   - **陌生畫面**：一次一個動作，`seq "click X Y; wait 400; shot"`，看完再決定下一步。
3. 不要盲點：至少在結尾截圖驗證；流程中途需要事後查錯的，在 seq 裡多存一張 `shot <檔名>`（不用 Read，失敗時再看；相對檔名一律存到 `tools/.cache/`，單獨 shot 與 seq 內都一樣，絕對路徑照用）。
4. **面板開著時只點面板範圍內**：點面板外會穿透到遊戲場景（走路、點到 NPC）。要重開面板先 ESC。
5. 關閉面板：優先 `key '{ESC}'`；ESC 關不掉的（聊天面板、小地圖浮窗、收合狀態）見 ui/home.md「關閉方式」。
6. 收合鈕（`<` `>`）按下後會**換位置**，再點同一座標會點空，要重新截圖找。
7. 任務結束（成功、失敗或停下來問使用者）→ `bash tools/gui/gui.sh end`。

## 紅區（絕對不點）
| 東西 | 原因 |
|---|---|
| 贊助、商城的「購買」、LuckyCard「抽1次 / 抽10次 / 購買獎券」、任何 NT$ / 鑽石價格鈕 | 付費（鐵則 3） |
| 設置面板底部：全員登出、離線掛機、回記錄點 | 會讓角色登出或傳送，改變全隊狀態（回記錄點＝無確認框直接回村長家，使用者交代時才按） |
| 背包道具的「丟棄」、刪除管理 | 不可逆 |
| 外掛（ASS）裡任何勾選、下拉選單、數值與 SET 鈕；主畫面「遇敵」 | 會改變自動戰鬥 / 遇敵行為。開面板看可以，改任何東西都要使用者同意 |
| 設置面板「解決異常」 | 作用未知，要先問 |
| 地圖傳送的目的地 | 會整隊傳送（實測不扣石幣），屬遊玩決策；英雄戰場有儲值門檻，不點 |
| 交易所的上架 / 購買 | 交易 |

開面板、切分頁、點道具看說明都可以自由做。
花**石幣**的操作（NPC 商店、傳送、商城石幣分頁）不違反鐵則，但屬於遊玩決策，只有在執行使用者交代的任務時才做。
任務條目（點了可能自動尋路）屬於執行任務，使用者沒交代任務時不點。

**出現答題 / 驗證視窗（npcanswer，選項是圖片）→ 立刻停手並通知使用者**（鐵則 5）。
**出現「網路異常，是否重連?」→ 跑 `netwatch.py --once`（或腳本內建 guard）點確定；點完會回到登入畫面，netwatch 會自動按「登錄」（使用者授權：只點登錄 / 一鍵全登，帳密由遊戲自動帶入，AI 絕不輸入或讀取帳密；帳密欄空、登錄後有任何提示 / 驗證視窗、連續 3 次失敗 → 停手通知使用者）**（[ui/network.md](ui/network.md)）。

## 判讀注意
- 截圖是視窗自己的畫面，不會截到通知。背景點擊的訊息直接送進遊戲視窗，遊戲被其他視窗蓋住也點得到，不會點到別的視窗。
- 背景點擊如果 UI 沒收到（例：假焦點失效），點擊會**穿透到地面讓隊伍走路**、原地遇敵也會被取消；看到這種情況就改 `fg`。
- 角色頭頂名字很密集、會互相重疊，不要靠名字定位自己；自己腳下有藍色光圈。
- 右上角「地圖名 + 地圖ID:x,y」是目前位置，可直接對 `tools/query/psa.py map/route/grid`。
- 本帳號是多角色同時登入（真名 DKBO、DKBO2～5，字母 O；文件舊寫法 DKB0… 同義，程式比對 O / 0 視為相同）。目前操作的角色：人物資訊 / 背包左欄有黃框的頭像、設置面板的「暱稱」、切換角色面板標「當前」的那個。面板左欄可切換正在看的角色。
