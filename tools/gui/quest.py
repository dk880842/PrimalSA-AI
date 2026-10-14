#!/usr/bin/env python3
"""解任務監測：任務靠遊戲內建自動巡路（Auto Walking），這支腳本每 1 秒截圖判斷狀態，只處理「對話要按確認」與「戰鬥按刷新角色加速」。

用法（專案根目錄；WSL / Windows 原生指令相同）：
  uv run --no-project python tools/gui/quest.py --task 黃金羚羊之謎   # 一直監測，最長 15 分鐘（--task = 追蹤列表上的任務名，必填）
  uv run --no-project python tools/gui/quest.py --once          # 只看一次、做一個動作就結束（除錯用）
  uv run --no-project python tools/gui/quest.py --max-seconds 600 --stop-after-rewards 2
  --max-seconds 的計時（2026-10-11）：自動走路（Auto Walking = 任務進行中）不計入；只有連續非 walking 的閒置 / 其他狀態才耗時限（WalkClock；巡路中途短暫 unknown 1～2 次又回 walking 仍算巡路；單次連續巡路超過 WALK_CAP_S=900 秒不再延長，防卡死）。結束時印「走路不計時 N 秒」，questrun 據此扣總時限。
  巡路卡住解卡（2026-10-12）：walking 期間每 WALK_POS_EVERY=5 秒讀一次座標（walk.pos，digitmatch），座標連續 WALK_STUCK_S=40 秒不變（座標讀不到時改看世界畫面 WORLD_PTS 取樣 ≥90% 不變 = 鏡頭沒動）→ 存 snap walk-stuck、
           點附近安全地面一下（walk.unstick_click：通行格、離 NPC / 出口 ≥ 2 格、不在 UI 上；沒有通行格資料 / 只有畫面判斷沒座標就直接重點追蹤卡片）→ 停下後照「對話後先點追蹤」重點追蹤；
           事件 log + errlog 各記一筆；同一次執行解卡超過 WALK_UNSTICK_MAX=3 次 → 退出碼 19（27～29 是舊外掛逃跑碼，不重用）。
  對話結束後一律先按追蹤（2026-10-11）：對話框 / 領獎關閉回主畫面後，第一個動作是點追蹤欄該任務卡片（標題相符才點，post_track_try）；卡片不在、或點了約 5 秒（TRACK_RETRY_SECS ×2）沒反應才改找黃色問號（沒反應不再直接退出碼 3；黃問號也沒用，之後照舊 2 次追蹤失敗才退出碼 3）。沒對話過的啟動 / 一般閒置仍是先找黃問號、再追蹤。
  選項：--task 任務名（要點追蹤時，先用 OCR 認出追蹤列表每一格的標題，名稱相符才點；不符就捲動列表再找，找不到退出碼 5，絕不點其他任務。
          沒給 --task 又沒給 --no-track 會直接拒絕執行）、--no-marker（不找 NPC 頭上的黃色問號）、
        --every 1.0（輪詢秒數；2026-10-10 起預設 1 秒，所有「連續 N 次」的規則已改成以秒計，見 IDLE_CONFIRM_SECS 等常數）、--no-track（不主動點任務追蹤，只處理對話 / 戰鬥）、--no-refresh（戰鬥不按刷新角色）、
        --stop-after-rewards N（領到第 N 次「獲得物品」確認窗後停；避免自動接下一個任務。成人儀式 = 2）
  --solo   單人逃跑風格（/psa-quest-solo）：**一律手動逃跑**（2026-10-10 使用者：外掛「自動逃跑」不再使用、不看那個勾選框）。
           遇敵 → 完整戰鬥下指令階段按右上「逃跑」1283,168；自動戰鬥開著（指令框不出現）先按 1380,600 關掉再逃；
           逃跑失敗（還在戰鬥）下一回合再按。要先把 DKB0 外掛的原地遇敵 / 快速戰鬥 / 自動戰鬥關（完整戰鬥畫面才有逃跑鈕；只看到 VS 牌 = 快速戰鬥還開著，只能等，印警告）。
           路上小怪只逃、不刷新角色。到 NPC 跳出對話框 → ESC 關掉（不按任何選項）後停下，退出碼 20；被打飛（回到薩姆吉爾村 1000 儲存點附近）→ 退出碼 21。
  --stop-after-dialog  對話步（組隊後單步）：按完對話框、閒置滿 2.5 秒（連續 2 次以上）就結束退出碼 0（有獲得物品視窗的步驟改用 --stop-after-rewards 1）
  --fight  戰鬥步（假設已站在 NPC 旁，**不點追蹤、不巡路**）：--npc X,Y（NPC 地圖座標）或 --npc auto（--task 目前步驟的 NPC，讀追蹤條目說明行對任務表；兩步文字相似時先用「目前所在地圖」分辨，仍分不出退出碼 31；見 --step）→ 依自己座標算畫面位置點 NPC（--at X,Y 可手動給自己座標）
           → 先處理「選擇對象」面板（見下）→ 對話框按左鈕 → 開打。戰鬥分類：開始時距離最後一次點 NPC / 按對話框 <= QUEST_BATTLE_WINDOW(15) 秒 = 任務 / BOSS 戰
           （確保自動戰鬥開 + 刷新角色；打完閒置滿 IDLE_CONFIRM_SECS 秒（且連續 2 次）印「BOSS 戰結束」後**判斷輸贏**（verify_boss_result / judge_boss_result：點 NPC 前記下座標與任務步驟，打完重驗隊伍 / 座標 / 步驟 / HP）：贏 = 退出碼 0；少人 32；沒打贏 35；判斷不了 36；不繼續巡路）；
           否則 = 路上小怪：手動逃跑（自動戰鬥開著先關再按逃跑），不刷新角色。
           點 NPC 後 12 秒沒對話框也沒戰鬥 → 退出碼 22（沒點到 NPC）；對話後 15 秒沒開打 → 23；被打飛 21。
           範例：quest.py --fight --task 英雄島前傳 --npc auto --max-seconds 300
  --npc-map M  --fight --npc X,Y 用：NPC 所在地圖（有 --task 時不給會用任務表反查）；與目前地圖不同 → 退出碼 34（「目前在地圖 A，NPC 在地圖 B」），不點
  --disband-after  這步完成（搭配 --stop-after-dialog / --stop-after-rewards）後立刻解散隊伍；分頁沒切到組隊 / 選單沒彈出 / 解散後隊長紅標還在 → 不亂點，退出碼 26；已是單人（組隊分頁沒隊長紅標）→ 不點任何東西，退出碼 0
  --stop-after-dialog 的停止規則：只要這步已對話或領獎過，之後閒置不再點追蹤 / 黃問號，閒置滿 2.5 秒（連續 2 次以上）就停（退出碼 0）；遊戲自己又開始 Auto Walking → 退出碼 24
  --step N  --fight 用：明確指定任務第 N 步的 NPC（= --npc auto 但不 OCR 追蹤條目；需 --task）。--npc auto 不給 --step 時，改讀追蹤條目「標題正下方那行說明」
           （OCR）對照 Task 表 explandTn 找目前步驟的 endNpc；讀不到 / 對不到（或兩步相似且 NPC 不同）→ 先用「目前所在地圖只對應唯一一個打 BOSS / 對話步驟」反查（事件 log 註明地圖反查），仍不行 → 退出碼 31，不點任何東西，絕不退回「第一個戰鬥步」
  --team-size N  隊伍人數檢查（預設 5；0 或 1 = 跳過；切換面板開啟後等卡片內容穩定再讀：連 2 次讀到相同標籤才算，最多 TEAM_STABLE_MAX_S=1.5 秒，全部「不在隊」時至少重讀才判失敗 = read_team_labels_stable）：只在必要時檢查（2026-10-11）：開始前、--fight 點 NPC 前、領獎後（一步結束要去下一步 / 交任務）點追蹤前、任務 / BOSS 戰打完後的下一次點之前；其他點擊（每次點追蹤 / 黃問號）不檢查。開切換面板（uikit.open_panel / close_panel，輪詢驗證；打不開原地重試 CHECK_TEAM_TRIES=3 次、間隔 1 秒、先確認是主畫面）763,760，
           讀 5 張卡片的隊伍標籤，要「1 隊長 + (N-1) 隊員」（N=5 即 5 人都要在隊）；面板上其他卡片是單人 / 不在隊（例如單人 DKB0）不算錯；隊員不夠 / 隊長不是 1 個 / 讀不到 → 不點、事件 log 寫出誰不在隊、關面板（✕ 1064,208）；--fight 開打前退出碼 30、執行中發現脫隊退出碼 32。
           --solo / --fight --no-click 不檢查。--team-fresh（questrun 用：它在 30 秒內剛驗過隊伍）→ 只略過「開始前」那一次。**開始前一定先驗**：非 --solo 模式（含 --no-track / --stop-after-*）第一次點 / 按對話框前先驗一次（不受 GAP 限制），不符退出碼 30；啟動時對話框已開 → 先 ESC 再驗（2026-10-10 18:44 事件：--solo 後單人直接 --stop-after-rewards 只有 DKB0 交任務）。聊天「離開了隊伍」OCR 不可靠（只顯示最新 2 則、會被洗掉），所以脫隊偵測改用這個「點之前先驗隊伍」的做法
  戰鬥鎖檔  所有模式一進戰鬥就寫 tools/.cache/battle.lock（pid + 開始時間），戰鬥結束 / 程式結束（finally）刪除；ass.py 看到有效鎖檔 = 戰鬥中，不改外掛設定（見 ui/ass.md）
  組隊預設模式（非 --solo / --fight）：**每一場戰鬥**（完整戰鬥或快速戰鬥、不分任務 / 路上）都刷新角色；完整戰鬥自動戰鬥鈕是關的 → 先按 1380,600；同一場按 4 次仍關（寵物指令視窗等）→ 退出碼 25
  刷新角色規則：--solo / --fight 只有任務 / BOSS 戰（點 NPC / 對話後 QUEST_BATTLE_WINDOW 內開始）刷新，路上小怪直接逃、不刷新；預設模式每場都刷新（--no-refresh 全關）。「刷新成功」後同一場最多每 REFRESH_GAP=8 秒再按一次；沒成功 REFRESH_RETRY=1 秒後就重試（主迴圈睡到到期為止，不多等一整輪）。
           2026-10-13 改（使用者：進戰鬥十幾秒才刷新）：完整戰鬥偵測到後等 REFRESH_FIRST_DELAY=1.5 秒才按第一次（actions.log 實證：一偵測到就按切換 850,765，5 場面板都沒開、接著底部冒出「關閉 + 頭像」列，舊版再花 4 下 × 約 4.5 秒收列）；快速戰鬥不等。refresh_characters 每次只做一次嘗試、不阻塞：讀底部列（bottom_bar）→ 「關閉 + 頭像」列（綠字「如果遇到下指令出錯等問題…」）蓋著就只點一下左側「關閉」（輪流 510,745 / 745 / 725 / 765）、等 0.5 秒再讀，還在 → 回 row；切換鈕圖示（screen_sigs.SIG_SWITCH_FULL 850,765 / SIG_SWITCH_MAIN 763,760）沒露出 → 不點（回 notready；完整戰鬥剛結束時主畫面 850,765 是「組隊」，圖示不同所以不會點到）；露出才按切換 → waitpix 等面板 → 刷新角色 910,578，**看 waitpix 結果**：面板沒開回 nopanel（舊版不看結果，沒按到也記「按刷新角色」）。同一場連續 REFRESH_STUCK_SNAP=10 次沒成功存一張 close-row-stuck / refresh-fail 圖 + errlog。
           2026-10-13 review §4.2（30 場有 14 場一直點關閉、十幾下都收不掉）：同一場「關閉」點 CLOSE_ROW_MAX_CLICKS=2 次列還在 → 之後只讀不點（回 row_wait），等列自己消失才刷新。
           看 14 張 close-row-stuck 圖（推測，未實證）：列出現時 5 格頭像都打勾、上方是「播放中」或「N回合 剩餘時間 70」＝全員指令已送出、等回合結算 / 播放動畫時的指令狀態列，這段期間點「關閉」無效。
  VS 牌卡死：快速戰鬥（頭上 VS 牌、沒有完整戰鬥畫面）開戰 VS_STUCK_S=90 秒還沒結束 → 存 snap vs-stuck、結束本片，退出碼 42（questrun 全員重登 relogin.py 後續片）。
  選擇對象面板（點 NPC 後右側跳出的米色面板：頭像卡片 + 名字，NPC 是黃 / 金字、隊友白字）：偵測到就依黃字位置點 NPC 那張卡片（不寫死第一格），再等對話框；--fight 點 NPC 後與對話步（--stop-after-dialog 點 NPC / 黃問號）都處理。
  模擬測試：uv run --no-project python tools/gui/test_quest_fight.py
  事件記錄：notes/quest-events.log（每行一筆，附截圖路徑 tools/.cache/quest-log/）；啟動時自動刪 tools/.cache/quest-log/ 內超過 3 天的圖檔（cleanup_old_shots）。

狀態判斷（都是背景截圖讀像素，座標為 2880×1659 → 截圖 1440×830；細節與實測見 .claude/skills/psa-game-ui/ui/quest.md）：
  對話框   右側棕底 + 兩顆米色鈕 → 點左鈕 948,461（接受 / 完成 / 成人勾玉 等推進鈕；右鈕 1220,461 是「再見」不點）
  獲得物品 藍色「確認」鈕 720,572 + 米色底 → 點它，並輪詢確認視窗消失（每次最多 1.5 秒；沒消失再按，最多 3 次 → 仍在 = 退出碼 18）。
           2026-10-10 / 10-12 紅暴步 8 按一次沒關、--stop-after-rewards 隨即結束 → 都要手動補點，所以領獎一定要驗證關閉才算數；
           2026-10-13 根因補充：步 8 開窗時石幣動畫飛過視窗，close_reward 單次讀成「不是領獎窗」就當已關、--stop-after-rewards 立刻結束 →
           停手前再看 REWARD_SETTLE_S=2 秒（settle_reward），領獎窗又出現（沒真的關 / 任務完成的第 2 個窗）就再關，仍關不掉 = 18
  只有再見 只有一顆「再見」鈕的對話框（SIG_BYE 9 點 + OCR 按鈕區每個倍率的字都剛好是「再見」，bye_lines_only）→ ESC 關閉（不回答）：
           - 點「選擇對象」卡片後 BYE_SELECT_WINDOW=15 秒內出現 = 點到別人的閒聊（2026-10-12 紅暴步 1）→ 回原流程（最多 BYE_MAX=3 次，第 3 次退出碼 40）；
           - 其他（點追蹤 / 黃問號 / 巡路抵達）= 任務 NPC 只剩再見（2026-10-13 老人薩頓：頭盔因背包滿進了信箱）→ 退出碼 40（任務接不下去，questrun 查背包 / 信箱）。
           2026-10-13 06:08 / 06:33 誤報 rc 9 的根因：ocr.ps1 -Zooms 2,3 同一顆鈕讀兩次，舊版整串接成「再見再見」≠「再見」
  殘留面板 不認得的畫面連 2 次時先 close_stray_panel：選人小窗 ESC、組隊 / 切換面板、uikit.known_panel 的已知面板（標題板字 + ✕ 都命中；背包另要外框兩顆鈕）→ 點 ✕，記事件
           （2026-10-13 07:59 / 08:04 背包 / 倉庫面板殘留誤報 rc 9）；clear_leftovers() 給 questrun 交接用（對話框 / 再見 / 選擇對象 ESC、獲得物品確認、已知面板 ✕，不認得不碰）
  片內 HP --hp-check-min N（questrun 傳 --team-hp-min）：預設模式打完 1 場任務戰（--no-stop-after-boss 時；平常 BOSS 戰由 37 交 questrun 讀），或路上一般戰鬥每 --hp-check-every 場（預設 3；0 = 不讀，2026-10-13 起，舊版每場都讀 8 秒）、回主畫面閒置確認後讀全隊 HP（bag.team_hp_pct，開背包約 8 秒），
           任一人 < N% → 退出碼 41（questrun 補血後續片）。任務 BOSS 戰打完、閒置確認前 slice 時間到也延後收片（slice_defer boss_pending，最多 180 秒），
           確保回 37 讓 questrun 做 BOSS 後補血（2026-10-13 07:36 / 07:38 四寶玉之謎：守護獸打完領獎後下一輪就「時間到」回 0 → 沒補血連打 → DKBO3 / DKBO5 HP 0 被踢）
  戰鬥     完整戰鬥畫面（上方棕框標籤）或頭上綠色 VS 牌（快速戰鬥）→ 切換（完整 850,765 / 快速 763,760）→ 刷新角色 910,578（按完面板自己關；規則見上「刷新角色規則」）
  巡路中   畫面中央金黃色「Auto Walking」字樣
  主畫面   外掛鈕紅字 ASS（沒對話框 / 巡路 / 戰鬥時）→ 檢測方針（使用者指定）：
           1. 場景裡有黃色「?」「!」任務標記 → 優先點它（findmark.ps1 找黃色色塊，點標記下方的 NPC）
           2. 沒有 → 在追蹤列表先用標題圖片樣板比對（titlematch，0.7 秒）、沒樣板 / 沒找到才用 OCR（ocr.ps1，成功會存樣板）找 --task 那一格，必要時捲動列表，確認標題相符才點 → 開始（繼續）巡路
  轉場     載入畫面（「加載中」字形 / 英文版「Loading...」綠橘雙進度條〔進度無關，綠條剛開始很短也認〕/ 舊三點）或全黑 → 等待、不點、不計入不認得（screen_sigs.transition）；
           同一串連續超過 LOADING_MAX_S=60 秒 → 存 snap loading-stuck、退出碼 43（questrun / rebirth 重跑同一片，stuckrecover.RETRY_RC）。
  不認得   連續 3 次且滿 UNKNOWN_CONFIRM_SECS 秒都不是以上任何狀態（答題 / 驗證視窗、讀取中卡住…）→ 存圖、印警告、退出碼 2（鐵則 5：交給使用者）；
           每一串的第 1 次另存 *-unknown1.png（事後看得到前面是什麼畫面）。第 2 次起先試 close_stray_panel（已知殘留面板 / 快速組隊「提示」只點 ✕）
  追蹤沒反應 點了任務追蹤約 5 秒（TRACK_RETRY_SECS 重點一次、再等一輪）都沒進入巡路 / 對話 / 戰鬥 → 退出碼 3，改手動（walk.py + 點 NPC）
  預設模式 BOSS 戰收尾（errlog #68，2026-10-11）：非 --solo / --fight 時，任務戰（對話框 / 黃問號後 QUEST_BATTLE_WINDOW 秒內開打；打到一半又開始 Auto Walking 的後續遇敵不算）打完、閒置滿 IDLE_CONFIRM_SECS 後
           **先驗隊伍（check_team）再停手、不點追蹤 / 黃問號、不接下一步**：滿員 = 退出碼 37、不滿 / 讀不到 = 38（事件 log 寫誰不在隊；重打流程由呼叫端做：char.py switch 被打飛者當單人隊長 → 追蹤自動傳送 → 重打 → 切回 DKBO → team.form）。
           `--no-stop-after-boss` = 不停、照舊連跑（--team-size 0 / 1 仍會停 37，只是沒驗隊伍）。路上一般遇敵不算 BOSS 戰；對話後 15 秒以上才開打也不算（Auto Walking 抵達直接開打的 BOSS 偵測不到，那種步驟請用 --fight）。--disband-after 在 BOSS 停手時不執行。
  不可逆對話防護（errlog #68）：每次按對話框左鈕前先 OCR 內文（ocr.ps1 -Light）+ 兩顆按鈕（-Dark），含 IRREVERSIBLE_KEYWORDS（轉生 / 寵物轉生 / 封印 / 刪除 / 丟棄；先移除 IRREVERSIBLE_ALLOW 放行片語「挑戰機暴(轉生任務)」，2026-10-12 使用者定）或內文讀不到 → **不按、不 ESC、對話框維持開著**，存 snap（*-irreversible.png），退出碼 39。
           實證：精靈王第 2 頁左鈕只寫「完成」，轉生字樣在內文（「…進行轉生的儀式吧」）→ 只看按鈕擋不住，所以兩塊都讀。確認要做才加 `--allow-irreversible`（不做 OCR、全放行）。--solo 只 ESC 不按，不受影響。
結束時印「走路不計時 N 秒」「本片戰鬥 N 場」兩行（questrun 解析：巡路不計時、沒打仗才沿用全隊 HP）。
退出碼：43 載入 / 轉場畫面連續 LOADING_MAX_S 秒（結束本片，呼叫端重跑）、42 快速戰鬥 VS 牌卡死 VS_STUCK_S 秒（結束本片，呼叫端重登）、40 任務 NPC 只有「再見」（已 ESC，任務接不下去）、41 --hp-check-min 片內戰鬥後全隊 HP 偏低（結束本片）、37 預設模式 BOSS 戰結束且隊伍滿員（已停手）、38 預設模式 BOSS 戰結束但隊伍不滿 / 讀不到（已停手，看事件 log）、29 對話 / 選擇對象面板循環 SELECT_LOOP_MAX 次沒進展（已停手）、39 對話框含不可逆關鍵字或讀不到內文（沒按）、33 對話無進展（同一黃問號「點 → 對話」STALL_MAX=4 輪沒領獎 / 戰鬥 / 巡路 / 換圖，沒按對話框就停）、34 --fight 自己所在地圖與 NPC 地圖不同（沒點）、35 --fight BOSS 戰打完但地圖與任務步驟都沒變（沒打贏；事件 log 附 HP 佐證）、36 --fight BOSS 戰打完判斷不了輸贏（OCR 讀不到步驟 / 沒給 --task；**不回 0**，請人工看畫面）、30 隊伍不符（開始前第一次點 / 按對話框前驗隊伍；含 --fight 點 NPC 前）、31 --npc auto 取不到目前步驟、32 執行中脫隊（點追蹤 / 黃問號 / 領獎後追蹤前的隊伍檢查）、20 --solo 到達 NPC（已 ESC 關對話框）、21 被打飛回村（--solo / --fight）、22 --fight 沒點到 NPC、23 --fight 對話後沒開打、24 --stop-after-dialog 停止時遊戲自己已在 Auto Walking、25 組隊完整戰鬥自動戰鬥按 4 次仍關、26 --disband-after 解散沒做成、18 獲得物品按確認 3 次仍關不掉、19 自動巡路卡住（Auto Walking 但座標 WALK_STUCK_S 秒不變）自動點地面解卡 WALK_UNSTICK_MAX 次仍卡、0 正常結束（--fight 只有**判定打贏**才回 0；任務完成〔領過獎勵後整個追蹤列表掃完沒有 --task，印「任務完成」〕/ 時間到 / 做完對話或領獎後連續 2 次閒置提前結束 / --once / 達到 --stop-after-rewards）、2 不認得的畫面、3 追蹤沒反應、4 版面不支援 / 參數錯、5 追蹤列表掃完（到頂 + 到底）找不到 --task 的任務且沒領過獎勵（沒點任何東西）。
（27 / 28 / 29 = 舊外掛自動逃跑專用，2026-10-10 移除，不再使用。）
只透過 gui.ps1 背景截圖 / 點擊，不碰遊戲記憶體。
"""
import argparse
import os
import difflib
import json
import subprocess
import sys
import time
from pathlib import Path

import battleguard
import screen_sigs
import layout
import netwatch
import winenv
import walk
from walk import ROOT, gui, log, PRIMER, stat
from screen_sigs import (SIG_CMD, SIG_AUTO_OFF, SIG_CLOSE_ROW, SIG_SELECT, SIG_DIALOG, SIG_REWARD, SIG_PANEL, SIG_HUD,  # noqa: F401
                         SIG_SWITCH_FULL, SIG_SWITCH_MAIN, SIG_BATTLE, VS_PROBE, VS_COLOR, AW_POINTS, AW_MIN, TOL, close)
import re

EXIT_REWARD_STUCK = 18               # 「獲得物品」按確認 REWARD_CLICK_MAX 次、每次等 REWARD_GONE_S 秒視窗都還在（沒亂點別的，存 *-reward-stuck.png）
EXIT_AT_NPC = 20                     # --solo：到達 NPC（對話框已 ESC 關閉）
EXIT_KNOCKED = 21                    # 被打飛回薩姆吉爾儲存點
EXIT_NO_NPC = 22                     # --fight：點 NPC 後 NPC_WAIT 秒內沒對話框也沒戰鬥（沒點到 NPC / 被小怪打斷）
EXIT_NO_BATTLE = 23                  # --fight：有對話但 QUEST_BATTLE_WINDOW 秒內沒開打（這步其實不戰鬥？）
EXIT_AUTOWALK = 24                   # --stop-after-dialog：這步對話完，遊戲自己又開始 Auto Walking（腳本沒點追蹤；呼叫端要馬上處理，例如解散）
EXIT_BATTLE_STUCK = 25               # 組隊預設模式：完整戰鬥按了自動戰鬥好幾次仍是關的（寵物指令視窗 / 其他卡住畫面）→ 人工處理
EXIT_DISBAND_FAIL = 26               # --disband-after：解散沒做成（分頁沒切過去 / 選單沒彈出 / 解散後畫面沒變），沒亂點
# 27 / 28 / 29（外掛自動逃跑專用）已於 2026-10-10 移除，編號保留不重用
EXIT_TEAM_MISMATCH = 30              # --fight / 預設模式點 NPC 前：切換面板的隊伍標籤不是「1 隊長 + (N-1) 隊員」（有人脫隊 / 單人）→ 沒點 NPC
EXIT_STEP_UNKNOWN = 31               # --npc auto：讀不到追蹤條目的目前步驟文字，或對不到任務表的步驟（不退回第一個戰鬥步）
EXIT_TEAM_LOST = 32                  # 預設模式 / --fight 執行中：點追蹤 / 點 NPC 前的隊伍檢查發現有人脫隊（停下，不繼續點）
EXIT_SELECT_LOOP = 29                # 「對話 → 選擇對象面板 → 對話」循環 SELECT_LOOP_MAX 次沒領獎 / 戰鬥 / 巡路（2026-10-12 卡坦步 2 沒雞還按完成：54 次；停手人工看對話 / 任務條件）
EXIT_NO_PROGRESS = 33                # 對話無進展：同一黃問號反覆「點 → 對話 → 閒置」STALL_MAX 輪沒領獎 / 戰鬥 / 巡路 / 換圖（卡坦事故）→ 停手
EXIT_NPC_MAP = 34                    # --fight：自己所在地圖與 NPC 所在地圖不同（--fight 不巡路）→ 沒點 NPC
EXIT_BOSS_LOST = 35                  # --fight BOSS 戰打完閒置，但地圖與任務步驟都沒變 = 沒打贏（例：#25 龍王守衛 HP 1/551 被團滅）
EXIT_BOSS_UNKNOWN = 36               # --fight BOSS 戰打完，判斷不了輸贏（OCR 讀不到步驟 / 沒給 --task）→ 不回 0，請人工看畫面
EXIT_BOSS_DONE = 37                  # 預設模式：任務 BOSS 戰打完（閒置確認），隊伍檢查滿員 → 停手，呼叫端確認戰果再繼續下一步（不自動接下一步 / 轉生；--no-stop-after-boss 可關）
EXIT_BOSS_TEAM = 38                  # 預設模式：任務 BOSS 戰打完，但隊伍不滿 / 讀不到 → 停手，事件 log 寫誰不在隊；呼叫端做重打流程（char.py switch 單人隊長 → 追蹤傳送 → 重打 → 切回 → team.form）
EXIT_IRREVERSIBLE = 39               # 對話框文字含不可逆關鍵字（轉生 / 封印 / 刪除 / 丟棄…）或讀不到對話文字 → 沒按、對話框維持開著，存 snap；人 / agent 看圖確認後用 --allow-irreversible 放行
EXIT_BYE_ONLY = 40                   # 任務接不下去：任務 NPC 的對話框只有一顆「再見」鈕（OCR 確認）→ 已 ESC 關、不亂點，交給呼叫端（questrun 查背包滿 / 信箱，否則回報）
EXIT_HP_LOW = 41                     # --hp-check-min：戰鬥後回主畫面讀全隊 HP（bag.team_hp_pct），有人低於門檻 → 結束本片，呼叫端補血後續片
EXIT_VS_STUCK = 42                   # 快速戰鬥頭上 VS 牌 VS_STUCK_S 秒還沒結束（伺服器端卡死，刷新角色無效）→ 結束本片，呼叫端（questrun）全員重登 relogin.py
VS_STUCK_S = 90.0                    # 快速戰鬥正常 1～3 秒、刷新後幾秒內結束；超過這麼久仍是 VS 牌（沒有完整戰鬥畫面）= 卡死（2026-10-12 碧青 12 樓）
STALL_MAX = 4                        # 對話無進展幾輪就停
STALL_MARKER_PX = 10                 # 兩次點的黃問號座標差超過這麼多 px = 不同標記（輪數歸零）
AUTO_STUCK_MAX = 4                   # 同一場戰鬥最多按幾次自動戰鬥鈕
NPC_WAIT = 12.0                      # --fight 點 NPC 後最多等幾秒看有沒有反應（走過去 + 開對話框）
import logpaths  # noqa: E402
LOG_FILE = logpaths.p(ROOT / 'notes' / 'quest-events.log')
SHOT_DIR = ROOT / 'tools' / '.cache' / 'quest-log'
SHOT_KEEP_DAYS = 3                   # 啟動時清掉 SHOT_DIR 內超過幾天的圖檔
SHOT_EXTS = ('.png', '.jpg', '.jpeg')

# ---- 「連續 N 次」規則改以秒計（預設輪詢間隔 2.5 → 1.0 秒後，維持原本的實際等待時間；2026-10-10）----
DEFAULT_EVERY = 1.0                  # --every 預設（一般 / --solo / --fight 都是；舊值 2.5 / 1.5）
IDLE_CONFIRM_SECS = 2.5              # 連續閒置至少這麼久（且連續 >= 2 次）才算「這步結束 / 戰鬥打完」（舊：2 次 × 2.5 秒）
UNKNOWN_CONFIRM_SECS = 5.0           # 連續 3 次不認得 + 至少這麼久才停手（舊：3 次 × 2.5 秒 ≈ 5 秒；鐵則 5 的 3 次規則仍在，只是多一道時間條件）
SELECT_LOOP_MAX = 6                 # 選擇對象面板在「沒領獎 / 戰鬥 / 巡路」期間累計點幾次就停（退出碼 29）
SELECT_MAX_TRIES = 4                # 「選擇對象」面板連續出現幾輪還沒消失就不再點（交給不認得規則）
TRACK_RETRY_SECS = 2.5               # 點了任務追蹤後，等這麼久沒反應才算 1 次失敗（重點一次；連續 2 次失敗退出碼 3，約 5 秒）

# ---- 座標與特徵色（2880×1659 版面，截圖座標；2026-10-09 實測）----
TRACKER = (205, 325)                 # 左側任務追蹤第一條：點了自動尋路到任務 NPC
SWITCH_BTN = (763, 760)              # 主畫面「切換」（快速戰鬥 = 主畫面）
SWITCH_FULL = (850, 765)             # 完整戰鬥畫面的「切換」（戰鬥時最右「遇敵」鈕消失，按鈕列右移；2026-10-10 實測）
REFRESH_GAP = 8.0                    # 同一場戰鬥「刷新成功」後最多每幾秒再按一次
REFRESH_FIRST_DELAY = 1.5            # 偵測到戰鬥後至少等幾秒才按第一次（2026-10-13 actions.log：一偵測到就按切換 850,765 共 5 場 5 場面板都沒開，隨後底部出現「關閉 + 頭像」列；開戰約 2 秒後按的成功）
REFRESH_RETRY = 1.0                  # 刷新沒成功（面板沒開 / 關閉列還在 / 切換鈕沒露出）幾秒後重試（舊版要等 REFRESH_GAP 8 秒）
REFRESH_STUCK_SNAP = 10              # 同一場連續幾次沒成功就存一張 close-row-stuck / refresh-fail 圖（只存一次）
REFRESH_BTN = (910, 578)             # 切換角色面板「刷新角色」（綠色，最右；按完面板自己關）
QUEST_BATTLE_WINDOW = 15.0           # 最後一次「按對話框 / 點 NPC / 點問號」後幾秒內開始的戰鬥 = 任務戰鬥（才按刷新角色）
ESCAPE_BTN = (1283, 168)             # 完整戰鬥下指令畫面右上角指令框的「逃跑」（跑步小人，第 2 排最右；2026-10-10 實測，點了出現 Escape! 泡泡）
AUTO_BTN = (1380, 600)               # 戰鬥畫面右側「自動戰鬥」鈕（點一下切換開 / 關，同外掛 ASS 的自動戰鬥；日誌「你已開啟 / 關閉自動戰鬥」）
# 下指令階段（右上指令框 + 上方「N回合 / 剩餘時間」）：播放中框會消失，用框的底色 / 邊框 + 逃跑鈕判斷（2026-10-10 實測，容差 25）
# SIG_CMD（下指令階段）/ SIG_AUTO_OFF（自動戰鬥鈕關）：特徵與容差在 screen_sigs.py（2026-10-10 實測，容差 25 / 20）
SAVE_POINT = (1000, 93, 99)          # 薩姆吉爾的儲存點巫女 1000:94,99、復活 / 傳送落點 92,99 附近（知識庫 Npc 3014）
KO_RADIUS = 8                        # 地圖 1000 且離儲存點這麼近（格）才可能是「被打飛」
# 戰鬥中底部「關閉」直式鈕 + 5 個角色頭像列（上方有綠字「如果遇到下指令出錯等問題，可使用下方[切換]按鈕切換至其他角色」）：它蓋住「切換」鈕，刷新前要先點左側「關閉」收起來。
# 實機樣本 tools/.cache/battle-samples/cmd_a.png（2026-10-10）：關閉鈕半透明灰米色 ≈(188,162,134)（容差 22）、右側深色頭像條（RGB 都 < 95）；21 張戰鬥樣本全中、其餘 455 張截圖（含主畫面 / 對話 / 選擇面板）0 誤判
CLOSE_ROW_BTN = (510, 745)
# SIG_CLOSE_ROW（容差 22）在 screen_sigs.py
CLOSE_ROW_DARK = [(555, 745), (1085, 745)]
# 「選擇對象」面板（點 NPC 後右側跳出的米色面板：頭像卡片，名字在卡片下方，NPC 是黃 / 金字 (255,2xx,0)、隊友白字）。
# 實機樣本 tools/.cache/quest-log/172356-no-npc.png（2026-10-10，碧青 8 樓水的守護獸）：面板外框 1106～1420 × 230～560，左右棕色邊框 + 內部米色漸層；
# 8 點（容差 40）全中，其餘 475 張截圖 0 誤判。名字黃字用 findmark.ps1 的黃色色塊找（NPC 名字拆成十來塊 w<=16 h<=16）。
# SIG_SELECT（8 點，容差 40）在 screen_sigs.py
SELECT_BOX = (1115, 235, 1415, 555)  # 面板內部（找黃字名字的範圍）
SELECT_NAME_DY = 48                  # 名字中心往上 48 = 那張卡片的頭像中心（實測：名字 y=337、頭像中心 y≈285~290）
SELECT_MIN_N = 30                    # 一排黃字色塊的像素總數至少這麼多才算名字（單字名也 > 40；頭像高光 < 20）
DIALOG_NEXT = (948, 461)             # NPC 對話框左鈕
REWARD_OK = (720, 572)               # 「獲得物品」視窗的藍色確認鈕
# ---- 不可逆對話防護（errlog #68，2026-10-11 精靈王轉生事故）----
# 實測（tools/.cache/quest-log/094532 / 094534-dialog.png）：精靈王第 1 頁內文「hello welcome to be here!」、左鈕「漆黑洞窟」；
# 第 2 頁內文「…進行轉生的儀式吧。轉生是把你最強的力量…」、左鈕只寫「完成」。→ 轉生字樣在**內文**不在按鈕，按「完成」就轉生了，
# 所以防護要讀「內文 + 按鈕」兩塊文字，任一塊含關鍵字就停（只看按鈕擋不住）。
IRREVERSIBLE_KEYWORDS = ('寵物轉生', '轉生', '转生', '封印', '刪除', '删除', '丟棄', '丢弃')
# 放行片語（使用者 2026-10-12 定：「挑戰機暴不算轉生」）：比對前先從文字移除，只是開打 BOSS 的選項。
# 實測 2026-10-12 22:07 帖拉所伊朵(機暴) 對話：內文「hello welcome to be here!」、左鈕「挑戰機暴(轉生任務)」、右鈕「再見」。
# 去空白後 regex 移除（OCR 括號全形 / 半形混用、括號漏讀、簡繁都收）；移除後其他地方仍有關鍵字照樣擋。
IRREVERSIBLE_ALLOW = (r'挑[戰战][機机]暴[(（]?[轉转]生任[務务][)）]?',)
DIALOG_BODY_BOX = (805, 285, 565, 115)     # 對話框內文區（淺米色字在棕底上，截圖座標 x,y,w,h；2026-10-11 實測字色 min(R,G,B) >= 170、底色 <= 64）
DIALOG_BTN_BOX = (815, 428, 540, 68)       # 兩顆米色鈕（深棕字：max(R,G,B) <= 100）
DIALOG_BODY_LIGHT = 140                    # ocr.ps1 -Light 門檻（亮字）
DIALOG_BTN_DARK = 140                      # ocr.ps1 -Dark 門檻（深字）
# 盜賊式「戰鬥 / 再見」對話框後備判斷（強盜的洞穴 2026-10-09 實測 classify 判成 idle；樣本已清掉，原因是推斷：SIG_DIALOG 取樣點 y=445 離鈕中心 461 近，
# 「戰鬥」深字筆畫可能壓到點，或內文棕底取樣點不同）：classify 判 idle / unknown 時，再看兩顆鈕「字旁」4 點是否都是米色（>= 3 點），是才 OCR 按鈕，
# 左鈕是「戰鬥」才當 dialog（只允許「戰鬥」，其他兩鈕對話框仍不處理；不可逆關鍵字照舊由主迴圈 check_dialog_irreversible 擋）。**未用樣本驗證，需實機確認**
DIALOG_BTN_PROBES = [(880, 461), (1010, 461), (1150, 461), (1290, 461)]
DIALOG_BTN_BEIGE = (229, 197, 155)
DIALOG_BTN_BEIGE_TOL = 40
DIALOG_BTN_NEED = 3
FIGHT_BUTTON = '戰鬥'
DIALOG_OCR_TRIES = 2                       # 內文讀不到時最多重讀幾次；仍讀不到 = 無法確認 → 不按（保守）
# 「只有一顆再見鈕」的閒聊對話（2026-10-12 紅暴步 1：領獎後又跳選擇對象面板，點到同 NPC 的閒聊「可不可以給我耐久力回復藥…」[再見]）：
# 兩顆鈕的位置（948 / 1220,445）變成棕底、中間 1085,445 一顆米色寬鈕；classify 判 unknown → 舊版連 3 次不認得 rc 2（誤警報）。
# 9 點全中（容差 40）才算候選，tools/.cache 1587 張 1440×830 截圖只有這次的 2 張（quest-log/140941-UNKNOWN、watch-alerts/unknown-1791785384）全中、其餘 0；
# 戰鬥 VS 樣本最多中 7 點。候選還要 OCR 按鈕區**整串只有「再見」**才處理（安全閘：驗證 / 答題視窗不會只有一顆再見鈕），處理 = ESC（不回答任何選項）
_BROWN, _BEIGE = (107, 70, 44), (229, 197, 155)
SIG_BYE = [(1360, 300) + _BROWN, (1100, 350) + _BROWN, (948, 445) + _BROWN, (1220, 445) + _BROWN, (880, 461) + _BROWN,
           (1290, 461) + _BROWN, (1085, 445) + _BEIGE, (1010, 461) + _BEIGE, (1150, 461) + _BEIGE]
SIG_BYE_TOL = 40
BYE_BUTTON = '再見'
BYE_MAX = 3                                # 「選擇對象面板點到閒聊」最多自動 ESC 幾次；超過 → 退出碼 40（避免 選擇對象 → 閒聊 無限循環）
BYE_SELECT_WINDOW = 15.0                   # 點「選擇對象」卡片後這麼多秒內出現的「只有再見」= 點到別人的閒聊（紅暴步 1）→ ESC 回原流程；
                                           # 其他時候（點追蹤 / 黃問號 / 巡路抵達）出現 = 任務 NPC 只剩再見 → ESC 後退出碼 40（2026-10-13 老人薩頓：頭盔進信箱，交不了）
# 「獲得物品」確認：按完要驗證視窗消失（2026-10-10 / 10-12 紅暴步 8 兩次按了沒關，--stop-after-rewards 直接結束沒人再按 → 都要手動補點）
REWARD_GONE_S = 1.5                        # 按確認後最多等這麼久看視窗消失（期間只要有一次不是 reward 就算關了）
REWARD_POLL_S = 0.3
REWARD_CLICK_MAX = 3                       # 最多按幾次確認（第 1 次 + 重試 2 次）
REWARD_SETTLE_S = 2.0                      # --stop-after-rewards 停手前再看這麼久：獲得物品視窗又出現 → 再 close_reward（2026-10-13 紅暴步 8：
                                           # 開窗時大量石幣動畫飛過視窗，close_reward 單次讀成「不是 reward」就當已關 → 腳本立刻結束、視窗留著要人點 720,572。
                                           # 不把 close_reward 改成「連續 2 次才算關」：會把緊接著出現的第 2 個領獎窗當同一個，--stop-after-rewards 2 少算）
# 對話框：棕底 2 點 + 兩顆米色鈕（heal.py 同款）。主畫面沙地很像米色，所以一定要配棕底
# SIG_DIALOG / SIG_REWARD / SIG_PANEL / SIG_HUD（容差 40）在 screen_sigs.py
# 完整戰鬥畫面（2026-10-10 實測，下指令 / 播放中兩種都量過）：上方中央棕框標籤（播放中 → 米色字；下指令 → 「N回合」+ 下方「剩餘時間 90」倒數），
# 標籤文字會變，所以只取「外框」9 點（兩種畫面像素相同）；主畫面 / 對話 / 獲得物品 / 地圖載入在這些點都不同。9 點同時符合（容差 25）才算。
# 完整戰鬥時 HUD 的 ASS 紅字還在，所以要排在 idle 之前
# SIG_BATTLE / VS_PROBE / AW_POINTS / AW_MIN 也在 screen_sigs.py（完整戰鬥特徵來自 battleguard）

# ---- 任務追蹤列表（左側，「任務 / 組隊」分頁下方；一格一個任務，標題 + 步驟說明，可上下捲動）----
LIST_BOX = (75, 270, 260, 180)       # OCR 區域 x,y,w,h（截圖座標）：標題深棕字
LIST_Y_MAX = 432                     # 標題中心 y 超過這個 = 標題字本身被列表框裁掉，不認（舊 425；樣板量到的 y 會比 OCR 大 1 px，例 426 vs 425，2026-10-12 放寬；點擊另看 LIST_CLICK_Y_MAX）
CARD_DY = 16                         # 點擊位置 = 標題中心往下一點（格子中心）
# 標題中心 y 超過這個 = 卡片下半截被列表框裁掉，正下方就是黃色 ▼ 捲動箭頭（y 442～458）：
# 2026-10-12 解救老爺爺：標題 y=425 → 點 205,441 只讓列表往下捲一格（卡片移到 y=366），沒有開始巡路，白花 18 秒重找。
# 所以這種卡先把列表往下捲一格（卡片會整張露出）再點；捲不動才改點標題本身（不點卡片中心）。
LIST_CLICK_Y_MAX = 405
SCROLL_UP = (200, 420, 200, 300)     # 往上拖 120px ≈ 捲一格（列表往下走）
SCROLL_DOWN = (200, 300, 200, 420)   # 反向
# 列表上下的黃色捲動箭頭（2026-10-12 用 tools/.cache 634 張截圖核對：有 ▼ 的全是「第 2 張卡被裁掉」，只有 1 張卡的列表沒有 ▼；
# ▲ 在任務完成、卡片變少後可能殘留〔例 quest-log/*-task-done.png 只剩 1 張卡仍有 ▲〕→ ▲ 只當「可能可以往上捲」，沒有 ▲ / ▼ 才當「那個方向捲不動」）
ARROW_UP_PTS = [(x, y) for y in (280, 284, 288) for x in (199, 205, 211)]     # ▲ 本體（黃 ≈ ffe800）
ARROW_DOWN_PTS = [(x, y) for y in (446, 450, 454) for x in (199, 205, 211)]   # ▼ 本體
ARROW_SANITY = (130, 222)            # 「任務」分頁鈕亮米色（≈ dfc39b 以上）：暗掉 = 有半透明遮罩（領獎視窗等），箭頭顏色不可信
ARROW_MIN = 3                        # 9 點裡至少幾點是黃色才算有箭頭（實測 ▲ 5 點、▼ 7 點，沒箭頭 0 點）


def read_screen() -> dict:
    """一次 gui pixel 讀完所有特徵點 → screen_sigs.classify 判斷狀態（判定邏輯與特徵都在 screen_sigs.py）"""
    pts = screen_sigs.points()
    allp = pts + [p for p in DIALOG_BTN_PROBES if p not in pts]
    allp += [(x, y) for x, y, *_ in SIG_BYE if (x, y) not in allp]
    out = gui('pixel', ' '.join(f'{x},{y}' for x, y in allp)).split()
    cols = [tuple(int(v) for v in c.split(',')) for c in out]
    if len(cols) != len(allp):
        return {'state': 'error', 'raw': out[:3]}
    px = dict(zip(allp, cols))
    r = screen_sigs.classify(px)
    if r['state'] in ('idle', 'unknown') and button_probe_ok(px) and fight_button_open():
        r = dict(r, state='dialog', fight_fallback=True)
    elif r['state'] in ('idle', 'unknown') and bye_probe_ok(px) and bye_button_only():
        r = dict(r, state='bye')
    return r


def bye_probe_ok(px: dict) -> bool:
    """純函式：SIG_BYE 9 點全中（單顆米色寬鈕 + 兩側棕底的對話框）；缺點 = False"""
    return all((x, y) in px and screen_sigs.close(px[(x, y)], (r, g, b), SIG_BYE_TOL) for x, y, r, g, b in SIG_BYE)


def bye_text_only(flat: str) -> bool:
    """純函式：按鈕區 OCR（已去空白）整串就是「再見」才 True（多一個字、讀錯、讀不到都 False → 照不認得處理）"""
    return flat == BYE_BUTTON


def bye_lines_only(lines) -> bool:
    """純函式：按鈕區 OCR 的行（ocr.ps1 每行帶 zoom）→ 每個「有讀到字」的倍率，該倍率的字串起來都剛好是「再見」才 True。
    根因（2026-10-13 06:08 / 06:33 老人薩頓誤報 rc 9）：-Zooms 2,3 同一顆鈕兩個倍率各讀一次「再見」，舊版整串接起來 =「再見再見」≠「再見」
    → 不當閒聊、連 3 次不認得。任何一個倍率多讀到別的字（例「戰鬥」）、或全部讀不到 → False（照不認得處理）"""
    by = {}
    for ln in lines or []:
        t = re.sub(r'\s+', '', str((ln or {}).get('text', '')))
        if t:
            by.setdefault((ln or {}).get('zoom'), []).append(t)
    return bool(by) and all(bye_text_only(''.join(v)) for v in by.values())


def bye_button_only() -> bool:
    """OCR 按鈕區：只有「再見」一顆鈕才回 True（每個倍率分開判，見 bye_lines_only）"""
    return bye_lines_only(dialog_button_lines())


def transition_screen() -> str | None:
    """現場讀一次 → 地圖轉場畫面種類（screen_sigs.transition：'loading' 任一種載入圖〔加載中字形 / 英文版 Loading 雙進度條 / 舊三點〕、'black' 全黑）或 None"""
    pts = screen_sigs.transition_points()
    try:
        out = gui('pixel', ' '.join(f'{x},{y}' for x, y in pts)).split()
        cols = [tuple(int(v) for v in c.split(',')) for c in out]
    except Exception:
        return None
    return screen_sigs.transition(dict(zip(pts, cols))) if len(cols) == len(pts) else None


def loading_screen() -> bool:
    """相容舊名：是不是轉場畫面（載入圖 / 全黑）"""
    return transition_screen() is not None


def transition_wait(t0: float, now: float) -> bool:
    """純函式：這一串轉場畫面（從 t0 起）還能繼續等嗎？超過 LOADING_MAX_S → False（當卡住，退出碼 EXIT_LOADING_STUCK）"""
    return now - t0 < LOADING_MAX_S


def button_probe_ok(px: dict) -> bool:
    """兩顆鈕字旁 4 點至少 DIALOG_BTN_NEED 點是米色（純像素，便宜；主畫面沙地偶爾也像，所以還要 OCR 確認）"""
    n = sum(1 for p in DIALOG_BTN_PROBES if p in px and screen_sigs.close(px[p], DIALOG_BTN_BEIGE, DIALOG_BTN_BEIGE_TOL))
    return n >= DIALOG_BTN_NEED


def dialog_button_lines() -> list:
    """OCR 對話框按鈕區（深字，-Zooms 2,3）→ ocr.ps1 的 lines（每行 text / zoom）；讀不到回 []"""
    tx, ty, tw, th = DIALOG_BTN_BOX
    r = ps_json('ocr.ps1', tx, ty, tw, th, '-Zooms', '2,3', '-Dark', DIALOG_BTN_DARK)
    return [ln for ln in (r.get('lines') or []) if isinstance(ln, dict)]


def dialog_button_text() -> str:
    """OCR 對話框按鈕區（深字）→ 去掉空白的整串文字（兩個倍率串在一起）；讀不到回空字串"""
    return re.sub(r'\s+', '', ''.join(ln.get('text', '') for ln in dialog_button_lines()))


def fight_button_open() -> bool:
    """OCR 兩顆鈕：左鈕是「戰鬥」（在「再見」之前）才回 True；讀不到 / 別的字一律 False（保守，不當對話框）"""
    flat = dialog_button_text()
    i = flat.find(FIGHT_BUTTON)
    if i < 0:
        return False
    j = flat.find('再見')
    return j < 0 or i < j


def ps_json(script: str, *args) -> dict:
    """跑 tools/gui 的 PowerShell 腳本（ocr.ps1 / findmark.ps1）→ 解析輸出的 JSON；失敗回 {'ok': False}"""
    try:
        r = winenv.run_ps(script, *[str(a) for a in args])
    except subprocess.TimeoutExpired:
        # ocr.ps1 / findmark.ps1 都是唯讀：逾時（server 已重開）當這一輪讀圖失敗，呼叫端進下一輪
        log(f'警告：唯讀 {script} 逾時（server 已重開），視同讀圖失敗', act=False)
        return {'ok': False, 'error': f'{script} 逾時'}
    if r.returncode == 125:
        log(f'警告：{script} 時常駐 server 中途結束（rc=125），視同讀圖失敗')
    try:
        return json.loads(r.stdout.strip().splitlines()[-1])
    except (ValueError, IndexError):
        return {'ok': False, 'error': (r.stderr or r.stdout)[:200]}


def norm(t: str) -> str:
    """任務名比對前的正規化：去空白、括號 / 版本字尾（例「黃金羚羊之謎(1.82)」→「黃金羚羊之謎」）"""
    import re
    return re.sub(r'[\s\(（\[【].*$', '', t)


def match_title(want: str, got: str) -> bool:
    """OCR 讀到的標題 got 是不是任務 want：完整包含，或相似度 >= 0.75（OCR 偶爾錯 1 個字）"""
    w, g = norm(want), norm(got)
    if not w or not g:
        return False
    return w in g or (len(g) >= 3 and g in w) or difflib.SequenceMatcher(None, w, g).ratio() >= 0.75


# OCR 把卡片的虛線分隔 / 木框花紋讀成的「字」：單筆畫的橫豎撇點、破折號、標點（2026-10-12 解救老爺爺：虛線被讀成「一乛乛」，
# 被當成第 2 張卡 → 「只有 1 張卡 = 沒捲動空間」的規則沒觸發，完成判斷多捲 4 下 8 秒）
NOISE_CHARS = set('一乛丨丿乀乚亅丶ノ丄丅〡〢〣－—–‐_-~～ー=＝.。,，:：;；|｜/\\\'"`·•、…()（）[]【】<>《》^＾*＊+＋')


def is_noise_title(t: str) -> bool:
    """OCR 讀到的一行是不是雜訊（不是任務標題）：去掉空白與 NOISE_CHARS 後剩不到 2 個字。任務標題最短也是 2 個實字（例「伐木證書」4 字）"""
    return len([c for c in t if not c.isspace() and c not in NOISE_CHARS]) < 2


def read_list_titles() -> list[dict]:
    """OCR 追蹤列表的標題行 → [{y, texts: [各倍數讀到的字]}]（依 y 排序）。
    Windows OCR 對同一張圖換放大倍數，結果差很多（有時整行讀不到、有時只讀到右半），
    所以一次 ocr.ps1 跑放大 2～7 倍、把 y 相近（<14px）的行併成一格，比對時只要任一種讀法符合即可。"""
    x, y, w, h = LIST_BOX
    r = ps_json('ocr.ps1', x, y, w, h, '-Zooms', '2,3,4,5,6,7', '-Dark', 150)
    rows: list[dict] = []
    for ln in sorted(r.get('lines', []), key=lambda o: o['y']):
        if is_noise_title(ln['text']):
            continue
        for row in rows:
            if abs(row['y'] - ln['y']) < 14:
                row['texts'].append(ln['text'])
                break
        else:
            rows.append({'y': ln['y'], 'texts': [ln['text']]})
    return rows


def list_signature() -> list[tuple]:
    """追蹤列表區域的像素取樣（判斷捲動有沒有動、是否到盡頭用；比 OCR 穩）"""
    pts = ' '.join(f'{x},{y}' for y in range(285, 445, 14) for x in range(90, 330, 20))
    return gui('pixel', pts).split()


NO_SCROLL_ROWS_MAX = 1               # 目前頁標題列 ≤ 這個數且目標不在 → 列表沒有捲動空間（一頁至少放得下 2 張卡），不捲、一輪判不在
# 「只有 1 列」還要那一列在列表最上面一格（標題 y ≤ 這個）才算沒有捲動空間：卡片間距約 115 px、列表框約 1.5 張高，
# 捲到底時最後一張的標題在 y≈366、上一張的標題已捲出框外（2026-10-12 解救老爺爺實測）→ 這時只看得到 1 列，但上面還有卡。
# 推算：只有 1 張卡時它一定在頂格 y≈310；≥2 張卡時頂格那張下面一定還看得到第 2 列（y≈425）→ 單列且在頂格 ⇔ 整個列表就 1 張卡。
NO_SCROLL_TOP_Y = 335
LAST_SCAN_NO_SCROLL = False          # 最近一次 track_task 是否因「沒有捲動空間」直接判目標不在（呼叫端據此一輪就判任務完成）
_PAGE_ROWS_N = None                  # 最近一次 OCR 讀到的標題列數（已濾掉雜訊列）
_PAGE_ROWS = None                    # 最近一次 OCR 讀到的標題列（[{y, texts}]）
_HIT_MODE = ''                       # 最近一次命中用的方法（tpl / ocr）；auto 模式記實際用到的那個


class _Interrupted(Exception):
    """掃描途中畫面不再是主畫面（跳出對話 / 戰鬥 / 領獎）"""


def scroll_list(drag: tuple[int, int, int, int], note: str, before: list) -> tuple[bool, list]:
    """捲動追蹤列表一格；回傳（畫面有沒有變, 捲完的像素取樣）。before = 捲動前的取樣（呼叫端沿用上一次的，省一次截圖）；沒變 = 已到盡頭"""
    gui('seq', 'drag %d %d %d %d; wait 1400' % drag, note=note)
    after = list_signature()
    return after != before, after


def classify_arrows(cols) -> dict | None:
    """純函式：ARROW_UP_PTS + ARROW_DOWN_PTS + ARROW_SANITY 的顏色 → {'up': 有 ▲, 'down': 有 ▼}。
    「任務」分頁鈕暗掉（領獎視窗等半透明遮罩）或點數不對 → None（箭頭顏色不可信，呼叫端照舊靠拖曳 + 像素取樣判斷到頂 / 到底）"""
    nu, nd = len(ARROW_UP_PTS), len(ARROW_DOWN_PTS)
    if not cols or len(cols) < nu + nd + 1:
        return None
    s = cols[nu + nd]
    if s[0] < 180 or s[1] < 150:
        return None

    def yel(c):
        return c[0] > 220 and c[1] > 170 and c[2] < 80
    return {'up': sum(1 for c in cols[:nu] if yel(c)) >= ARROW_MIN, 'down': sum(1 for c in cols[nu:nu + nd] if yel(c)) >= ARROW_MIN}


def list_arrows() -> dict | None:
    """一次 pixel 讀追蹤列表的 ▲ / ▼ 捲動箭頭（約 0.1 秒）→ classify_arrows；讀不到 None"""
    pts = ARROW_UP_PTS + ARROW_DOWN_PTS + [ARROW_SANITY]
    try:
        cols = [tuple(int(v) for v in c.split(',')[:3]) for c in gui('pixel', ' '.join(f'{x},{y}' for x, y in pts)).split()]
    except (ValueError, AttributeError):
        return None
    return classify_arrows(cols)


def _find_on_page(want: str, mode: str) -> int | None:
    """目前這一頁追蹤列表上 want 的標題中心 y（沒有回 None）；畫面不是主畫面 → _Interrupted。
    tpl = 標題圖片樣板（約 0.7 秒）；ocr = Windows OCR（3～7 秒），認出目標就存樣板；
    auto = 先樣板、這頁沒命中**同一頁**就改 OCR（不先把整個列表捲一輪；2026-10-12 樣板剛點完卡片 / 剛領完獎的約 10 秒內會暫時比不中，
    舊做法樣板整輪捲完才退 OCR，每次白拖 4 下 12～14 秒）。名稱不符絕不回傳。"""
    global _PAGE_ROWS_N, _HIT_MODE
    if read_screen()['state'] != 'idle':
        raise _Interrupted()
    if mode in ('tpl', 'auto'):
        ty = _tm_find(want)
        if ty is not None and ty <= LIST_Y_MAX:
            _HIT_MODE = 'tpl'
            return ty
        if mode == 'tpl':
            return None
        log(f'標題樣板這頁沒命中「{want}」→ 同一頁改用 OCR')
    rows = read_list_titles()
    if not rows:                                           # 整個列表讀不到（剛換圖 / 捲動慣性中）→ 等一下再讀一次
        time.sleep(1.0)
        rows = read_list_titles()
    log(f'追蹤列表標題：{[r["texts"][0] for r in rows]}')
    global _PAGE_ROWS
    _PAGE_ROWS, _PAGE_ROWS_N = rows, len(rows)
    for row in rows:
        if row['y'] <= LIST_Y_MAX and any(match_title(want, t) for t in row['texts']):
            _tm_learn(want, row['y'])                      # OCR 認出了 → 存標題樣板，下次不必 OCR
            _HIT_MODE = 'ocr'
            return row['y']
    return None


def no_scroll_room(mode: str, arrows: dict | None = None) -> bool:
    """目前頁沒找到目標時：列表是否沒有捲動空間 = 標題只有 1 列（雜訊列已在 read_list_titles 濾掉）、那一列在頂格（y ≤ NO_SCROLL_TOP_Y），
    且看得到箭頭時沒有 ▼。tpl 模式沒讀過標題，補讀一次 OCR（約 3～7 秒，仍比捲兩輪快）。"""
    global _PAGE_ROWS_N, _PAGE_ROWS
    if _PAGE_ROWS is None:
        _PAGE_ROWS = read_list_titles()
        _PAGE_ROWS_N = len(_PAGE_ROWS)
    rows = _PAGE_ROWS
    if not 1 <= len(rows) <= NO_SCROLL_ROWS_MAX:
        return False
    if any(r['y'] > NO_SCROLL_TOP_Y for r in rows):
        return False                                       # 捲到底時的最後一張（上面還有卡，只是標題捲出框外）
    return not (arrows and arrows.get('down'))


def _scan_track(want: str, mode: str, max_scrolls: int) -> tuple:
    """掃一遍追蹤列表找 want（先看目前頁 → 往上捲到頂 → 往下捲到底）→ (y 或 None, 上捲格數, 下捲格數)；畫面不是主畫面 → _Interrupted。
    捲動前先看 ▲ / ▼ 箭頭（list_arrows）：沒有 ▲ 就不往上拖、沒有 ▼ 就不往下拖；拖完箭頭消失 = 已到頂 / 到底，不再多拖一下確認。
    箭頭讀不到 / 與標題列矛盾（沒箭頭卻不像只有 1 張卡）→ 不信箭頭，照舊拖到像素取樣不變為止。"""
    sig = list_signature()
    global _PAGE_ROWS_N, _PAGE_ROWS, LAST_SCAN_NO_SCROLL
    _PAGE_ROWS_N = _PAGE_ROWS = None
    y = _find_on_page(want, mode)
    ups = pages = 0
    if y is not None:
        return y, 0, 0
    arr = list_arrows()
    if no_scroll_room(mode, arr):
        LAST_SCAN_NO_SCROLL = True
        log(f'追蹤列表只有 {_PAGE_ROWS_N} 張卡（在頂格）且沒有「{want}」→ 沒有捲動空間，不捲')
        return None, 0, 0
    if arr is not None and not arr['up'] and not arr['down']:
        log(f'追蹤列表看不到 ▲ / ▼ 但標題列（{_PAGE_ROWS_N} 列）不像只有 1 張卡 → 不信箭頭，照舊拖到盡頭')
        arr = None
    trust = arr is not None
    if not trust or arr['up']:
        while ups < max_scrolls:                       # 往上到頂
            moved, sig = scroll_list(SCROLL_DOWN, f'任務追蹤列表往上捲一格找「{want}」', sig)
            if not moved:
                break
            ups += 1
            if (y := _find_on_page(want, mode)) is not None:
                break
            if trust and (arr := list_arrows() or arr) and not arr['up']:
                break                                  # ▲ 消失 = 到頂
    if y is None and trust:
        arr = list_arrows() or arr
    if y is None and (not trust or arr['down']):
        for i in range(max_scrolls * 2):               # 往下到底；前 ups 格是剛看過的頁，不重看
            moved, sig = scroll_list(SCROLL_UP, f'任務追蹤列表往下捲一格找「{want}」', sig)
            if not moved:
                break
            pages += 1
            if i + 1 > ups and (y := _find_on_page(want, mode)) is not None:
                break
            if trust and (arr := list_arrows() or arr) and not arr['down']:
                if i + 1 >= ups:
                    break                              # ▼ 消失 = 到底（還在走回剛看過的頁時不會發生）
    return y, ups, pages


def _reveal_low_card(want: str, y: int) -> tuple[int, int]:
    """目標卡片的標題在列表下緣（y > LIST_CLICK_Y_MAX，卡片下半截被裁掉、正下方是 ▼）：先把列表往下捲一格讓整張露出，再重找 →
    回 (要點的 x, y)。捲不動 / 捲完找不到 / 還是太低 → 點標題本身（不點卡片中心，避開 ▼）。畫面變了 → _Interrupted"""
    moved, _ = scroll_list(SCROLL_UP, f'「{want}」卡片在列表下緣被裁掉 → 先往下捲一格再點', list_signature())
    if moved:
        y2 = _find_on_page(want, 'auto' if _tm_has(want) else 'ocr')
        if y2 is not None and y2 <= LIST_CLICK_Y_MAX:
            return 205, y2 + CARD_DY
        if y2 is not None:
            y = y2
    log(f'「{want}」捲不上來（y={y}）→ 點標題本身，不點卡片中心（避開 ▼）')
    return 205, y


def close_stray_panel() -> bool:
    """畫面停在已知的誤開 / 殘留面板 → 點它的 ✕ 關掉並回 True；都不是回 False（照舊當不認得 / 疑似驗證視窗）。
    認得：選人小窗（ESC）、組隊 / 切換面板、uikit.known_panel 的已知面板（標題板字 + ✕ 都命中才算；背包另要外框兩顆鈕，
    2026-10-13 07:59 / 08:04 depot_use 中斷留下背包 / 倉庫面板 → 舊版連 3 次不認得誤報 rc 9）。只點 ✕（必要時 ESC），不點面板內容"""
    try:
        import uikit
        if uikit.is_open(uikit.PLAYERPICK):                 # 選人小窗（點地面點到隊友）：ESC 關；它會擋住自動巡路
            event('畫面上有「選人小窗」（解卡點地面點到隊友）→ ESC 關閉')
            gui('key', '{ESC}')
            time.sleep(0.6)
            return not uikit.is_open(uikit.PLAYERPICK)
        if uikit.is_open(uikit.QTEAM):                     # 快速組隊「提示」（5 人名單 + 組隊鈕）：重登 / team.form 中斷殘留（errlog #700）→ 只點 ✕，絕不按組隊
            shot = snap('stray-qteam')
            ok_ = uikit.close_panel(uikit.QTEAM, known_open=True)
            event('畫面上有快速組隊「提示」視窗（重登 / 組隊中斷殘留）→ 點 ✕ 關閉（不按組隊）' + ('' if ok_ else '，但關不掉'), shot)
            return ok_
        for p in (uikit.TEAMPANEL, uikit.SWITCH):
            if uikit.is_open(p):
                event(f'誤開了「{p.name}」面板（戰鬥剛結束時刷新鈕點到主畫面按鈕）→ 點 ✕ 關閉')
                return uikit.close_panel(p, known_open=True)
        name = uikit.known_panel()
        if name:
            label = screen_sigs.PANEL_NAMES.get(name, name)
            shot = snap(f'stray-{name}')
            p = uikit.known_panel_obj(name)
            ok_ = bool(p) and uikit.close_panel(p, known_open=True)
            event(f'畫面停在「{label}」面板（別的工具中斷殘留）→ 點 ✕ 關閉' + ('' if ok_ else '，但關不掉'), shot)
            return ok_
    except Exception as e:
        log(f'close_stray_panel 失敗：{e}')
    return False


CLEAR_ROUNDS = 5                     # clear_leftovers 最多處理幾輪（對話框多頁 / 面板疊兩層）


def clear_leftovers(rounds: int = CLEAR_ROUNDS) -> str:
    """交接 / 開跑前清掉上次中斷留下的東西，回最後的畫面狀態（idle / walking / battle / unknown …）：
    NPC 對話框、只有「再見」的對話、選擇對象面板 → ESC（不回答任何選項）；獲得物品 → close_reward（按確認並驗證消失）；
    已知面板 / 選人小窗 → close_stray_panel（只點 ✕）。不認得的畫面（可能是驗證視窗）一律不碰、直接回 'unknown'（鐵則 5）"""
    st = 'error'
    for _ in range(rounds):
        st = read_screen()['state']
        if st in ('dialog', 'bye', 'select'):
            what = {'dialog': 'NPC 對話框', 'bye': '只有再見的對話框', 'select': '選擇對象面板'}[st]
            gui('key', '{ESC}', note=f'清殘留：{what} → ESC（不回答）')
            event(f'清殘留：畫面停在{what}（上次中斷）→ ESC 關閉（不回答任何選項）')
            time.sleep(0.8)
            continue
        if st == 'reward':
            gone, n = close_reward()
            event(f'清殘留：獲得物品視窗 → 按確認（{n} 次）' + ('，已關' if gone else '，仍關不掉'))
            if not gone:
                return 'reward'
            continue
        if st in ('panel', 'unknown') and close_stray_panel():
            time.sleep(0.5)
            continue
        return st
    return read_screen()['state']


# ---- 追蹤卡片位置快取（2026-10-13 review 1013b §1.4）：同一張卡通常沒移動 → 先只在上次的 y 比一次標題列像素，命中才點 ----
# 「樣板」= 上次掃描（titlematch / OCR 確認標題相符）命中那一刻在該 y 讀的標題列像素（5 列 × 120 點、每 2 px 一點）；最多留 3 個變體（選中 / 未選中底色）。
# 名稱不符絕不點仍成立：點之前一定要現場像素跟「確認過標題的那張卡」**每一點**都吻合（每通道差 ≤ 16，且有字的深色點）；
# 只差一個筆畫（漆黑洞窟(一轉) / (二轉)）也會有多點不同 → 對不上 → 退回整輪掃描（只是慢，不會點錯）。
TRACK_POS = logpaths.p(ROOT / 'tools' / '.cache' / 'track-pos.json')        # 測試時 testenv 轉向暫存
TRACK_POS_TTL_S = 6 * 3600
TRACK_SIG_TOL, TRACK_SIG_NEED, TRACK_SIG_INK = 16, 1.0, 12
TRACK_SIG_MAX = 3


def track_sig_pts(y: int) -> list:
    return [(x, y + dy) for dy in (-6, -3, 0, 3, 6) for x in range(90, 330, 2)]


def read_track_sig(y: int) -> list | None:
    """現場讀追蹤列表 y 那一列標題的像素（唯讀，一次 pixel）；讀不到 / 點數不對 → None"""
    pts = track_sig_pts(y)
    try:
        out = gui('pixel', ' '.join(f'{x},{yy}' for x, yy in pts)).split()
        cols = [[int(v) for v in c.split(',')] for c in out]
    except Exception:
        return None
    return cols if len(cols) == len(pts) and all(len(c) == 3 for c in cols) else None


def track_sig_match(a, b) -> bool:
    """純函式：兩組標題列像素吻合（點數相同、兩邊都有字、≥ TRACK_SIG_NEED 的點每通道差 ≤ TRACK_SIG_TOL）"""
    if not a or not b or len(a) != len(b):
        return False
    ink = lambda sig: sum(1 for c in sig if sum(c) < 330)          # noqa: E731  深棕標題字
    if ink(a) < TRACK_SIG_INK or ink(b) < TRACK_SIG_INK:
        return False
    ok = sum(1 for c, d in zip(a, b) if all(abs(u - v) <= TRACK_SIG_TOL for u, v in zip(c, d)))
    return ok >= TRACK_SIG_NEED * len(a)


def load_track_pos() -> dict:
    try:
        d = json.loads(Path(TRACK_POS).read_text(encoding='utf-8'))
        return d if isinstance(d, dict) else {}
    except (OSError, ValueError):
        return {}


def remember_track(want: str, y: int, sig) -> None:
    """掃描確認標題相符的卡 → 記 y + 標題列像素（同 y 累積變體，換了 y 就重來）"""
    if not sig:
        return
    d = load_track_pos()
    e = d.get(want) or {}
    sigs = e.get('sigs') if e.get('y') == y else []
    if not any(track_sig_match(sig, x) for x in sigs or []):
        sigs = (list(sigs or []) + [sig])[-TRACK_SIG_MAX:]
    d[want] = {'y': y, 'sigs': sigs, 'ts': time.time()}
    try:
        Path(TRACK_POS).parent.mkdir(parents=True, exist_ok=True)
        Path(TRACK_POS).write_text(json.dumps(d, ensure_ascii=False), encoding='utf-8')
    except OSError:
        pass


def track_fast(want: str) -> tuple:
    """上次的位置還是同一張卡？→ (y 或 None, 現場讀到的像素)。沒記錄 / 過期 / 讀不到 / 不吻合 → (None, …)"""
    e = load_track_pos().get(want) or {}
    y = e.get('y')
    if not isinstance(y, int) or y > LIST_CLICK_Y_MAX or time.time() - (e.get('ts') or 0) > TRACK_POS_TTL_S or not e.get('sigs'):
        return None, None
    cur = read_track_sig(y)
    if cur and any(track_sig_match(cur, x) for x in e['sigs']):
        return y, cur
    return None, cur


def track_task(want: str, max_scrolls: int = 12, click: bool = True) -> bool | None:
    """掃一遍追蹤列表找標題 = want 的那一格並點它（開始巡路）。名稱不符絕不點。
    回傳：True 找到（click=True 時已點）、False 整個列表掃完沒有、None 途中畫面不再是主畫面（交回主迴圈，不算找不到）。
    一輪有明確終點：先看目前這頁 → 往上捲到頂（每頁都看）→ 再往下捲到底（已看過的頁不重看）；到頂 / 到底看 ▲ / ▼ 箭頭（讀不到才用像素取樣沒變判斷），不來回。
    辨識：該任務有標題樣板 → 每頁先用樣板比對（0.7 秒 / 頁，錯配率 0），沒命中**同一頁**改 OCR（3～7 秒，認出會學新樣板）；沒樣板 → 直接 OCR。
    （2026-10-12 前是樣板整輪捲完才退 OCR 再捲一輪，一次多拖 4 下 12～14 秒。）
    點擊：標題太靠下緣（> LIST_CLICK_Y_MAX）的卡先捲上來再點（_reveal_low_card）。
    click=True 時先試位置快取（track_fast：上次確認過標題的 y，標題列像素每點吻合才點；2026-10-13 review 1013b §1.4），不中才整輪掃描。"""
    gui('seq', PRIMER)
    ensure_task_tab()
    mode = 'auto' if _tm_has(want) else 'ocr'
    t0 = time.time()
    global LAST_SCAN_NO_SCROLL, _HIT_MODE
    LAST_SCAN_NO_SCROLL = False
    _HIT_MODE = mode
    miss_sig = None
    if click:
        fy, miss_sig = track_fast(want)
        if fy is not None:
            if read_screen()['state'] != 'idle':
                return None
            _HIT_MODE = 'pos'
            gui('seq', f'click 205 {fy + CARD_DY}', note=f'點追蹤「{want}」（位置快取 y={fy}，標題列像素吻合；--task {want}）')
            event(f'追蹤列表「{want}」位置快取命中（y={fy}，{time.time() - t0:.1f}s）→ 點 205,{fy + CARD_DY}')
            return True
    try:
        y, ups, pages = _scan_track(want, mode, max_scrolls)
        cx = 205
        cy = None if y is None else y + CARD_DY
        if click and y is not None and y > LIST_CLICK_Y_MAX:
            cx, cy = _reveal_low_card(want, y)
    except _Interrupted:
        return None
    log(f'追蹤列表掃描（{_HIT_MODE}）{"找到 y=%d" % y if y is not None else "沒找到"}，上 {ups} 格 / 下 {pages} 格，耗時 {time.time() - t0:.1f}s')
    if y is None:
        return False
    if click and y <= LIST_CLICK_Y_MAX and cy == y + CARD_DY:          # 標題確認過、沒經過下緣捲動 → 記位置（快取沒中時現場讀的像素同一 y 就直接用）
        fy0 = (load_track_pos().get(want) or {}).get('y')
        remember_track(want, y, miss_sig if (miss_sig and fy0 == y and ups == 0 and pages == 0) else read_track_sig(y))
    if click:
        gui('seq', f'click {cx} {cy}', note=f'點追蹤「{want}」（{_HIT_MODE}，--task {want}）')
        event(f'追蹤列表找到「{want}」（{_HIT_MODE}）→ 點 {cx},{cy}')
    return True


TAB_TASK = (148, 236)                # 左側面板「任務」分頁鈕
TAB_TEAM = (260, 236)                # 左側面板「組隊」分頁鈕
# 分頁選中判斷（2026-10-10 組隊狀態實機量測）：選中的分頁底是亮米色（R≈205~221），沒選中是深棕（R≈80~90）；
# 只取分頁鈕「文字上方 y=222、文字下方 y=250」兩排（y=226~246 會踩到「任務 / 組隊」字，讀數亂跳）。
# 任務分頁 x=130、組隊分頁 x=270；四點全部一致才算（組隊選中：(130,*)≈(87,68,41) 且 (270,*)≈(215,183,135)；任務選中相反）
TAB_PROBE = ((130, 222), (130, 250), (270, 222), (270, 250))
# 隊長列頭像左上角的隊長標（組隊分頁、自己是隊長才有）。2026-10-10 是寬約 45 px 的紅「隊」字標（舊四點 (100..130, 306..312) ≈(217,33,33)）；
# 2026-10-12 S3 起變成約 16×16 的小紅框黃「L」標（x 96～111、y 298～313），舊四點全落空 → disband 誤判「已是單人」（errlog #242）。
# 改成在頭像左上區域 x 90～136、y 296～318 每 2 px 取樣數「純紅」點（R>170、G<50、B<50）：
# 新 L 標 16 點、舊隊字標 130 點；沒有標的頭像（橘髮最紅處 G≥0x80）與已解散畫面 0 點（fixtures/leader_badge_px.json）
LEADER_BADGE_PTS = [(x, y) for y in range(296, 319, 2) for x in range(90, 137, 2)]
LEADER_BADGE_MIN = 8
LEADER_BADGE = LEADER_BADGE_PTS                          # 舊名稱（相容）


def leader_badge_red(cols) -> int:
    """純函式：LEADER_BADGE_PTS 各點顏色 → 純紅點數"""
    return sum(1 for r, g, b in cols if r > 170 and g < 50 and b < 50)


def tab_state() -> str | None:
    """左側面板目前分頁：'team'（組隊亮、任務暗）/ 'task'（任務亮、組隊暗）/ None（讀不準）。四點都要一致"""
    try:
        out = gui('pixel', ' '.join(f'{x},{y}' for x, y in TAB_PROBE)).split()
        (t1, _, _), (t2, _, _), (g1, _, _), (g2, _, _) = [tuple(int(v) for v in c.split(',')) for c in out]
    except Exception:
        return None
    if min(g1, g2) > 190 and max(t1, t2) < 120:
        return 'team'
    if min(t1, t2) > 190 and max(g1, g2) < 120:
        return 'task'
    return None


def has_leader_badge() -> bool | None:
    """組隊分頁隊長列頭像左上有沒有隊長標（舊紅「隊」字 / 新小「L」都算：純紅點 ≥ LEADER_BADGE_MIN）；讀不到回 None"""
    try:
        out = gui('pixel', ' '.join(f'{x},{y}' for x, y in LEADER_BADGE_PTS)).split()
        cols = [tuple(int(v) for v in c.split(',')) for c in out]
        if len(cols) != len(LEADER_BADGE_PTS):
            return None
        return leader_badge_red(cols) >= LEADER_BADGE_MIN
    except Exception:
        return None


def ensure_task_tab() -> None:
    """左側面板停在「組隊」分頁時追蹤列表看不到任務（OCR 只讀到「創建隊伍」→ 誤判找不到）。
    只在「組隊亮、任務暗」很明確時點「任務」分頁；讀不準就不動。"""
    try:
        if tab_state() == 'team':
            gui('seq', f'click {TAB_TASK[0]} {TAB_TASK[1]}; wait 600', note='左側面板在「組隊」分頁 → 切回「任務」')
            event('左側面板在組隊分頁，已切回任務分頁')
    except Exception as e:
        log(f'ensure_task_tab 失敗：{e}')


DISBAND_LEADER = (210, 320)          # 組隊分頁隊長那一列
DISBAND_BTN = (200, 372)             # 點隊長列後彈出選單的「解散隊伍」


def disband_team(expect_leader: bool = False) -> int:
    """對話步完成後立刻解散（/psa-disband-team 的自動版）。每一步都驗證，驗不過就停、不再點（寧可退出碼 26 也不亂點，
    避免點到 y≈325 的任務追蹤條目觸發自動巡路）：
    1. 切組隊分頁 260,236 → tab_state()=='team'（四點像素；沒切過去再點一次；換圖後第一下點擊常被吃掉）
    2. 隊長列有隊長標（舊紅「隊」字 / 新小「L」，has_leader_badge）才繼續；沒有 = 已是單人（只剩「創建隊伍」）或不是隊長 → 不點任何東西，退出碼 0
       expect_leader=True（team.py disband：切換面板已確認當前是隊長）時沒有標 = 互相矛盾（標樣式又變了？S3 的 L 標就是這樣誤判成單人 → team rc 45）→ 不點，退出碼 26
    3. 點隊長列 210,320 → 左側面板像素必須變了（選單彈出）才點解散；分頁又變回任務 = 點到別的東西 → 停
    4. 點解散 200,372 → 分頁仍是組隊、面板像素變了、隊長紅標消失才算成功"""
    for attempt in range(2):
        gui('seq', f'{PRIMER}; click {TAB_TEAM[0]} {TAB_TEAM[1]}; wait 700', note='--disband-after：切左側組隊分頁')
        if tab_state() == 'team':
            break
    else:
        event(f'--disband-after：左側分頁沒切到「組隊」（連點 2 次）→ 不點解散，退出碼 {EXIT_DISBAND_FAIL}', snap('disband-no-tab'))
        return EXIT_DISBAND_FAIL
    badge = has_leader_badge()
    if badge is None:
        event(f'--disband-after：讀不到隊長紅標像素 → 不點解散，退出碼 {EXIT_DISBAND_FAIL}', snap('disband-no-badge-read'))
        return EXIT_DISBAND_FAIL
    if not badge and expect_leader:
        event(f'解散：切換面板說當前是隊長，但組隊分頁隊長列沒有隊長標（紅「隊」字 / 小「L」；標樣式可能又變了）→ 不點，退出碼 {EXIT_DISBAND_FAIL}', snap('disband-badge-mismatch'))
        return EXIT_DISBAND_FAIL
    if not badge:
        event('--disband-after：組隊分頁沒有隊長紅「隊」標（已是單人，或不是隊長）→ 沒點任何東西、未解散，視為無需解散（退出碼 0）', snap('disband-already-solo'))
        return 0
    sig0 = list_signature()
    gui('seq', f'click {DISBAND_LEADER[0]} {DISBAND_LEADER[1]}; wait 500', note='--disband-after：點隊長列')
    sig1 = list_signature()
    if tab_state() != 'team' or sig1 == sig0:
        event(f'--disband-after：點隊長列後選單沒彈出（或分頁變了）→ 不點解散，退出碼 {EXIT_DISBAND_FAIL}', snap('disband-no-menu'))
        return EXIT_DISBAND_FAIL
    gui('seq', f'click {DISBAND_BTN[0]} {DISBAND_BTN[1]}; wait 800', note='--disband-after：解散隊伍')
    if tab_state() != 'team' or list_signature() == sig1 or has_leader_badge() is not False:
        event(f'--disband-after：點解散後未確認成功（畫面沒變 / 隊長紅標還在）→ 退出碼 {EXIT_DISBAND_FAIL}（請 shot 看左側是否只剩「創建隊伍」）', snap('disband-unverified'))
        return EXIT_DISBAND_FAIL
    event('--disband-after：已解散隊伍（左側組隊分頁隊長紅標消失、面板像素已變）', snap('disbanded'))
    return 0


def finish(a, rc: int = 0) -> int:
    """一步完成的收尾：--disband-after 時先解散（失敗回 26），否則回 rc"""
    if a.disband_after:
        d = disband_team()
        return d or rc
    return rc


def _tm_has(want: str) -> bool:
    try:
        import titlematch
        return titlematch.has_templates(want)
    except Exception as e:                                 # 樣板模組壞了 → 退回 OCR
        log(f'titlematch 不可用：{e}')
        return False


def _tm_find(want: str) -> int | None:
    try:
        import titlematch
        return titlematch.find(want)
    except Exception as e:
        log(f'titlematch.find 失敗：{e}')
        return None


def _tm_learn(want: str, y: int) -> None:
    try:
        import titlematch
        d = titlematch.learn(want, y)
        if d:
            log(f'新增標題樣板 {d.name}')
    except Exception as e:
        log(f'titlematch.learn 失敗：{e}')


# ---- 黃色「?」任務標記（NPC 頭上；findmark.ps1 找黃色連通色塊，形狀 / 位置過濾在這裡）----
# 實測（2026-10-10，庫伊老爺爺頭上）：「?」金黃色，因高光被切成 3 塊（單位 = 截圖座標）：
#   上半彎鉤 18x15 n≈117、中間竪 5x10 n≈24、下面圓點 6x7 n≈27；整體 w≈18 h≈33。
#   「!」（可接任務）是 8x15 + 7x9 兩塊、寬度 ≤ 8，與「?」的彎鉤（寬 ≥ 14）明確不同；使用者只要「?」。
#   NPC 名字黃字拆成 n≤13 的小碎塊、Auto Walking 金黃字大又寬（w > 24），都不符。
MARK_HEAD = dict(w=(14, 24), h=(11, 20), n=(70, 200))      # 「?」上半彎鉤
MARK_DOT = dict(w=(4, 9), h=(5, 10), n=(15, 45))           # 「?」下面的圓點
MARK_NPC_DYS = (96, 135)              # 連續第 1、2 次嘗試的偏移；2 次都沒反應就改走追蹤列表（精靈之木這種大樹，身體在標記下 ~270，點標記下方會點到樹冠 / 隊友）
MARK_NPC_DY = 96                      # 彎鉤中心往下 96 = NPC 身體（實測：看門者彎鉤 y=296 → 點 y=392 開對話；+90 與 +45 名字牌上都沒反應）
# 場景區外的 UI（左側任務面板 / 左上 HUD / 右上地圖鈕 / 左下聊天 / 底部按鈕列 / 右側遇敵鈕）不算
MARK_EXCLUDE = [(0, 0, 560, 140), (60, 190, 400, 470), (1060, 0, 1440, 230), (0, 550, 540, 830), (700, 700, 1440, 830), (1300, 600, 1440, 830)]


def _in(b: dict, spec: dict) -> bool:
    return all(spec[k][0] <= b[k] <= spec[k][1] for k in ('w', 'h', 'n'))


def find_marker() -> dict | None:
    """場景區有沒有黃色「?」：找得到「彎鉤 + 正下方圓點」的組合才算；回傳彎鉤色塊（含 x,y,n）或 None"""
    r = ps_json('findmark.ps1')
    bl = r.get('blobs', [])
    for b in sorted((b for b in bl if _in(b, MARK_HEAD)), key=lambda b: -b['n']):
        if any(x0 <= b['x'] <= x1 and y0 <= b['y'] <= y1 for x0, y0, x1, y1 in MARK_EXCLUDE):
            continue
        if any(_in(d, MARK_DOT) and abs(d['x'] - b['x']) <= 6 and 15 <= d['y'] - b['y'] <= 30 for d in bl):
            return b
    return None


def event(msg: str, shot: str | None = None) -> None:
    """印出並寫進 notes/quest-events.log"""
    log(msg)
    try:
        LOG_FILE.parent.mkdir(exist_ok=True)
        with open(LOG_FILE, 'a', encoding='utf-8') as f:
            f.write(f'{time.strftime("%Y-%m-%d %H:%M:%S")} {msg}' + (f' [{shot}]' if shot else '') + '\n')
    except OSError:
        pass


def cleanup_old_shots(days: int = SHOT_KEEP_DAYS, folder: Path = None, now: float | None = None) -> int:
    """刪掉 folder（預設 SHOT_DIR）內修改時間超過 days 天的圖檔（.png / .jpg / .jpeg）；只看該資料夾第一層，不進子資料夾、
    不碰其他副檔名。任何錯誤都吞掉（不影響主流程）；回傳刪掉幾張"""
    folder = SHOT_DIR if folder is None else folder
    now = time.time() if now is None else now
    n = 0
    try:
        for f in folder.iterdir():
            try:
                if f.is_file() and f.suffix.lower() in SHOT_EXTS and now - f.stat().st_mtime > days * 86400:
                    f.unlink()
                    n += 1
            except OSError:
                pass
    except OSError:
        pass
    return n


def idle_confirmed(streak: int, since: float, now: float) -> bool:
    """連續閒置是否已夠久：>= 2 次且從第一次閒置起 >= IDLE_CONFIRM_SECS 秒（輪詢間隔變短也維持同樣等待時間）"""
    return streak >= 2 and now - since >= IDLE_CONFIRM_SECS


WALK_CAP_S = 900.0                   # 單次連續巡路最多不計時這麼久（防卡死：一直 walking 但其實卡住）；questrun 的 WALK_CAP_S 要相同
WALK_GRACE_READS = 2                 # 巡路中途連續 unknown 最多這麼多次（1～2 次）仍算巡路中


WALK: dict = {}                      # 本次執行的 WalkClock（main 結束時印「走路不計時 N 秒」給 questrun 扣總時限）
STATS: dict = {}                     # 本次執行的統計：battles = 打完幾場戰鬥（main 結束時印「本片戰鬥 N 場」給 questrun 判斷全隊 HP 能不能沿用）


SLICE_DEFER_STATES = ('battle', 'dialog', 'reward', 'select')
SLICE_DEFER_MAX_S = 180.0          # 時間到後最多再等這麼久（戰鬥 / 對話收尾）；超過就照舊收片


def slice_defer(st: str, over_s: float, boss_pending: bool = False) -> bool:
    """純函式：slice 時間到了但畫面正在戰鬥 / 對話 / 領獎 / 選擇對象 → True（先不結束，讓這一段在同一個程序收尾；over_s = 超時秒數，超過上限就放棄延後）。
    boss_pending = 預設模式打過任務 BOSS 戰、還沒閒置確認停手（退出碼 37 / 38）→ 任何狀態都延後（2026-10-13 07:36 / 07:38 四寶玉之謎：
    守護獸打完領獎後下一輪就「時間到」回 0，questrun 不做 BOSS 後補血，下一片連打 → DKBO3 / DKBO5 HP 0 被踢）"""
    return (st in SLICE_DEFER_STATES or boss_pending) and over_s < SLICE_DEFER_MAX_S


HP_CHECK_EVERY = 3                     # --hp-check-every 預設：路上一般戰鬥每打完幾場（回主畫面閒置確認後）讀一次全隊 HP；0 = 一般戰鬥不讀


def hp_check_due(a, quest_n: int, road_n: int, idle_ok: bool) -> bool:
    """純函式：--hp-check-min 開著、預設模式（非 --solo / --fight）、主畫面閒置確認（不在巡路中，開背包才安全），且
    打完 >= 1 場任務戰（quest_n；預設模式 BOSS 戰通常已由 37 / 38 停手交給 questrun 讀，這裡管 --no-stop-after-boss 的情況），
    或路上一般戰鬥打完 >= --hp-check-every 場（road_n；0 = 一般戰鬥不讀）。
    2026-10-13 review §5.4：舊版每打完 1 場（含路上小怪）就開背包讀 8 秒，49 場 ≈ 6.5 分；連戰任務（questdefs hp_every=1）由 questrun 傳 1"""
    if not (getattr(a, 'hp_check_min', 0) and not (a.solo or a.fight) and idle_ok):
        return False
    every = getattr(a, 'hp_check_every', HP_CHECK_EVERY)
    return quest_n >= 1 or (every > 0 and road_n >= every)


def hp_low_roles(pct, thr: int) -> dict:
    """純函式：{角色: % | None} → 低於 thr 的 {角色: %}（讀不出的 None 不算）"""
    return {r: v for r, v in (pct or {}).items() if v is not None and v < thr}


EXIT_UNKNOWN, EXIT_HALT_CODE = 9, 10   # bag / uikit 共用碼：疑似驗證視窗 / 斷線（同 uikit.EXIT_UNKNOWN_SCREEN / EXIT_HALT）


def read_team_hp() -> tuple:
    """全隊 HP%（bag.team_hp_pct：開背包逐人點頭像讀 HP 條字，約 8 秒，讀完關背包）→ (rc, {角色: % | None})"""
    import bag
    return bag.team_hp_pct()


class WalkClock:
    """slice 計時：自動走路（Auto Walking = 任務進行中）不計入 --max-seconds；只有「連續非 walking 的閒置 / 其他狀態」才耗時限。
    巡路中途短暫 unknown 1～2 次又回 walking（過場 / 讀圖失敗）也算巡路；單次連續巡路超過 cap 就不再延長（防卡死）。
    純邏輯（時間由呼叫端傳入），離線可測。walked = 已不計入的秒數（給呼叫端扣總時限）"""

    def __init__(self, max_seconds: float, now: float, cap: float = WALK_CAP_S, grace: int = WALK_GRACE_READS):
        self.end, self.prev, self.cap, self.grace = now + max_seconds, now, cap, grace
        self.was_walk, self.gap, self.period_t0, self.walked = False, 0, now, 0.0

    def tick(self, st: str, now: float) -> None:
        dt, self.prev = now - self.prev, now
        if st == 'walking':
            in_walk, self.gap = True, 0
        else:
            self.gap += 1
            in_walk = self.was_walk and st in ('unknown', 'error') and self.gap <= self.grace
        if in_walk and not self.was_walk:
            self.period_t0 = now
        if in_walk and self.was_walk and now - self.period_t0 <= self.cap:
            self.end += dt
            self.walked += dt
        self.was_walk = in_walk

    def expired(self, now: float) -> bool:
        return now >= self.end


WALK_STUCK_S = 40.0                  # Auto Walking 但座標連續這麼久沒變 = 巡路卡住（2026-10-12 吉魯島 121,170 站了 40 分鐘；正常巡路每 1～2 秒就換格，換圖讀取 ≤ 3 秒）
WALK_POS_EVERY = 5.0                 # 巡路中每隔這麼久讀一次座標（digitmatch 約 0.1 秒）
def unstick_refresh_due(tries: int) -> bool:
    """巡路卡住解卡的第 1 次先按「刷新角色」（使用者 2026-10-12：漆黑 1F 戰鬥後角色定在 11,46 動不了，疑似戰鬥後狀態沒同步），之後才點地面 / 重點追蹤"""
    return tries == 1


WALK_UNSTICK_MAX = 3                 # 同一次 quest.py 最多自動解卡這麼多次，再卡 → 退出碼 19（交人；27～29 舊碼不重用）
EXIT_WALK_STUCK = 19
# 地圖轉場（載入圖 / 全黑）：等它過去、不點任何東西、不計入不認得次數；連續超過 LOADING_MAX_S 秒 → 當卡住，退出碼 43（呼叫端重跑；stuckrecover.RETRY_RC）
LOADING_MAX_S = screen_sigs.TRANSITION_MAX_S
EXIT_LOADING_STUCK = 43


def _errlog(msg: str, fixed: str | None = None) -> None:
    """寫 errlog 一筆（psa-hud pane 顯示）；失敗不影響主流程"""
    try:
        import errlog
        errlog.add(msg, fix=fixed, source='quest')
    except Exception as e:
        log(f'errlog 寫入失敗：{e}')


class WalkStuck:
    """自動巡路卡住偵測（純邏輯，時間 / 座標由呼叫端傳入）：狀態一直是 walking、座標 (地圖, x, y) 連續 stuck_s 秒不變 → feed 回 True。
    中途短暫 unknown / error 不重設（讀圖失敗）；其他狀態（閒置、對話、戰鬥…）= 不是在巡路 → 重設。讀不到座標的那次不算"""

    def __init__(self, stuck_s: float = WALK_STUCK_S, every: float = WALK_POS_EVERY):
        self.stuck_s, self.every = stuck_s, every
        self.pos, self.t0, self.read_t, self.tries = None, 0.0, -1e9, 0
        self.sig = None                                  # 座標讀不到時的備援：世界畫面取樣（WORLD_PTS）

    def reset(self) -> None:
        self.pos, self.t0, self.read_t, self.sig = None, 0.0, -1e9, None

    def due(self, st: str, now: float) -> bool:
        """這一輪要不要讀座標（walking 且距上次讀 >= every）；非巡路狀態順便重設"""
        if st != 'walking':
            if st not in ('unknown', 'error'):
                self.reset()
            return False
        return now - self.read_t >= self.every

    def feed(self, pos, now: float) -> bool:
        self.read_t = now
        if not pos:
            return False
        if pos != self.pos:
            try:                                          # 地圖換了就記進 maphist（questrun 在出口卡住時用它避開「回頭」的出口）
                if pos != 'screen' and (self.pos in (None, 'screen') or pos[0] != self.pos[0]):
                    walk.note_map(pos[0])
            except Exception:                             # noqa: BLE001
                pass
            self.pos, self.t0 = pos, now
            return False
        return now - self.t0 >= self.stuck_s

    def feed_sig(self, sig, now: float) -> bool:
        """座標讀不到（地圖名兩行等，HUD 座標 OCR 失敗）時改看畫面：世界畫面取樣點 ≥ WORLD_SAME_RATIO 跟起點一樣 = 鏡頭沒動
        （巡路中鏡頭跟著角色捲動，幾乎每點都會變）；連續 stuck_s 秒 → True。self.pos 記 'screen' 表示是畫面判斷"""
        self.read_t = now
        if not sig:
            return False
        if self.sig is None or not world_same(self.sig, sig):
            self.sig, self.pos, self.t0 = sig, 'screen', now
            return False
        return now - self.t0 >= self.stuck_s

    def stuck_for(self, now: float) -> float:
        return now - self.t0 if self.pos else 0.0


# 世界畫面取樣點（避開左側面板 x<400、右上地圖 / 傳送、底部按鈕列、聊天框，以及角色本身 ME 715,410 附近 ±90 的原地走路動畫）
WORLD_PTS = [(x, y) for x in range(460, 1261, 100) for y in range(160, 601, 55)
             if not (625 <= x <= 805 and 320 <= y <= 500)]
WORLD_TOL, WORLD_SAME_RATIO = 12, 0.9


WORLD_DARK, WORLD_MIN_INFO = 40, 15


def world_same(a, b) -> bool:
    """純函式：兩次世界畫面取樣是否「鏡頭沒動」：只看「不是兩次都全黑」的點（洞窟的黑色虛空捲動前後都黑，不能當證據），
    這種點要 ≥ WORLD_MIN_INFO 個，且 ≥ WORLD_SAME_RATIO 每色差 ≤ WORLD_TOL（水 / 火把等小動畫容許）；不夠就回 False（不判卡住）"""
    if not a or not b or len(a) != len(b):
        return False
    info = [(p, q) for p, q in zip(a, b) if max(p) > WORLD_DARK or max(q) > WORLD_DARK]
    if len(info) < WORLD_MIN_INFO:
        return False
    same = sum(1 for p, q in info if all(abs(u - v) <= WORLD_TOL for u, v in zip(p, q)))
    return same >= WORLD_SAME_RATIO * len(info)


def read_world_sig() -> list | None:
    try:
        out = gui('pixel', ' '.join(f'{x},{y}' for x, y in WORLD_PTS)).split()
        cols = [tuple(int(v) for v in c.split(',')) for c in out]
        return cols if len(cols) == len(WORLD_PTS) else None
    except Exception:
        return None


def find_irreversible(texts: list[str], keywords=None) -> list[str]:
    """對話框文字（內文 / 按鈕各行）→ 命中的不可逆關鍵字清單（去空白後子字串比對，先移除 IRREVERSIBLE_ALLOW 放行片語；沒命中回 []）"""
    kws = IRREVERSIBLE_KEYWORDS if keywords is None else keywords
    flat = re.sub(r'\s+', '', ''.join(texts))
    for a in IRREVERSIBLE_ALLOW:
        flat = re.sub(a, '', flat)
    return [k for k in kws if k in flat]


def read_dialog_texts() -> dict:
    """OCR 目前對話框：內文（亮字，-Light）與兩顆按鈕（深字，-Dark）。回 {'body': [行], 'buttons': [行], 'body_ok': 內文有讀到字}
    內文每次都有字，所以 body 空 = 讀圖失敗（呼叫端保守不按）。ocr.ps1 只讀不點。"""
    out = {'body': [], 'buttons': [], 'body_ok': False}
    bx, by, bw, bh = DIALOG_BODY_BOX
    for _ in range(DIALOG_OCR_TRIES):
        r = ps_json('ocr.ps1', bx, by, bw, bh, '-Zooms', '2,3', '-Light', DIALOG_BODY_LIGHT)
        out['body'] = [ln['text'] for ln in r.get('lines', []) if ln.get('text')]
        if out['body']:
            out['body_ok'] = True
            break
        time.sleep(0.3)
    tx, ty, tw, th = DIALOG_BTN_BOX
    r = ps_json('ocr.ps1', tx, ty, tw, th, '-Zooms', '2,3', '-Dark', DIALOG_BTN_DARK)
    out['buttons'] = [ln['text'] for ln in r.get('lines', []) if ln.get('text')]
    return out


def check_dialog_irreversible() -> dict:
    """按對話框前的防護：回 {'blocked': bool, 'reason': 說明, 'hits': [關鍵字], 'body': [...], 'buttons': [...]}
    命中關鍵字 → blocked；內文讀不到 → blocked（無法確認不是不可逆選項）。"""
    t = read_dialog_texts()
    hits = find_irreversible(t['body'] + t['buttons'])
    if hits:
        why = f'對話框文字含不可逆關鍵字 {hits}'
    elif not t['body_ok']:
        why = '讀不到對話框內文（OCR 失敗），無法確認不是不可逆選項'
    else:
        why = ''
    return dict(t, blocked=bool(why), reason=why, hits=hits)


def close_reward() -> tuple[bool, int]:
    """按「獲得物品」確認並驗證視窗消失 → (已關, 按了幾次)。
    每按一次後輪詢最多 REWARD_GONE_S 秒，期間只要讀到一次不是 reward（主畫面 / 對話 / 下一個領獎窗之前的空檔）就算關了；
    整段都還是 reward（開窗動畫中點擊被吃掉，2026-10-10 / 10-12 紅暴步 8）→ 再按，最多 REWARD_CLICK_MAX 次。
    單次讀錯（石幣動畫蓋住特徵點）會誤判已關 → 主迴圈下一輪會再看到 reward 再關；--stop-after-rewards 停手前由 settle_reward 補看"""
    for n in range(1, REWARD_CLICK_MAX + 1):
        gui('seq', f'click {REWARD_OK[0]} {REWARD_OK[1]}')
        t_end = time.time() + REWARD_GONE_S
        while True:
            time.sleep(REWARD_POLL_S)
            if read_screen()['state'] != 'reward':
                return True, n
            if time.time() >= t_end:
                break
        log(f'獲得物品視窗按確認後 {REWARD_GONE_S}s 仍在（第 {n} 次）' + ('→ 再按一次' if n < REWARD_CLICK_MAX else ''))
    return False, REWARD_CLICK_MAX


def settle_reward(secs: float = REWARD_SETTLE_S) -> tuple[bool, int]:
    """--stop-after-rewards 停手前：再看 secs 秒，獲得物品視窗又出現（上一次其實沒關 / 任務完成的第 2 個領獎窗）→ close_reward。
    → (畫面上已沒有領獎窗, 額外關了幾個)；關不掉 → (False, n)。只有畫面是 reward 才點確認（不認得的畫面不碰）"""
    extra = 0
    t_end = time.time() + secs
    while time.time() < t_end:
        if read_screen()['state'] == 'reward':
            gone, _n = close_reward()
            if not gone:
                return False, extra
            extra += 1
            t_end = time.time() + secs                     # 關了一個再看一輪（第 2 個窗通常緊接著出現）
            if extra >= REWARD_CLICK_MAX:
                break
            continue
        time.sleep(REWARD_POLL_S)
    return True, extra


def snap(tag: str) -> str:
    SHOT_DIR.mkdir(parents=True, exist_ok=True)
    p = SHOT_DIR / f'{time.strftime("%H%M%S")}-{tag}.png'
    gui('shot', winenv.to_windows(p))
    return str(p.relative_to(ROOT))


def is_quest_battle(last_action: float, now: float, window: float = QUEST_BATTLE_WINDOW) -> bool:
    """戰鬥開始時離最後一次任務互動（按對話框 / 點 NPC / 點問號）夠近 → 任務戰鬥。巡路途中的隨機遇敵不算"""
    return last_action > 0 and now - last_action <= window


def plan_battle_action(s: dict, boss: bool, since_click: float, party: bool = False) -> str | None:
    """完整戰鬥畫面該做什麼（純函式，方便模擬測試）：
    BOSS 戰 → 自動戰鬥鈕是「關」才點（'auto_on'）；小怪 → 下指令階段按逃跑（'escape'），
    自動戰鬥是開著（鈕不是靜止紅圖示、也沒有指令框）就先關（'auto_off'，指令框下一回合才會出現）。
    party=True（組隊預設模式，不逃跑）：完整戰鬥、自動戰鬥鈕是「關」→ 'auto_on'（小怪也讓全隊自動打完）。
    沒有完整戰鬥畫面（快速戰鬥）或點擊間隔不夠 → None。"""
    if not s.get('full'):
        return None
    if party:
        return 'auto_on' if s.get('auto_off') and since_click >= 3.0 else None
    if boss:
        return 'auto_on' if s.get('auto_off') and since_click >= 3.0 else None
    if s.get('cmd'):
        return 'escape' if since_click >= 1.2 else None
    if not s.get('auto_off') and since_click >= 3.0:
        return 'auto_off'
    return None


def should_refresh(a, boss_now: bool, full: bool, auto_off: bool, since_refresh: float, since_start: float | None = None) -> bool:
    """這一輪戰鬥要不要按刷新角色（純函式）：--no-refresh 不按；--solo / --fight（手動逃跑）只有任務 / BOSS 戰（boss_now）才按，路上小怪不按；
    組隊預設模式每一場都按。完整戰鬥自動戰鬥還是關的（正要先按自動戰鬥）時先不刷新；完整戰鬥偵測到未滿 REFRESH_FIRST_DELAY 秒（since_start）先不按
    （快速戰鬥一場只有 1～3 秒、按的是主畫面切換 763,760，不等）；
    同一場距上次（成功；失敗時主迴圈把時間往前調成 REFRESH_RETRY 後到期）滿 REFRESH_GAP 秒才再按"""
    if a.no_refresh or ((a.solo or a.fight) and not boss_now):
        return False
    if full and auto_off:
        return False
    if full and since_start is not None and since_start < REFRESH_FIRST_DELAY:
        return False
    return since_refresh >= REFRESH_GAP


def close_row_visible() -> bool | None:
    """底部「關閉 + 5 頭像」列是否出現（關閉鈕 4 點灰米色 + 右側頭像條 2 點深色）；讀不到回 None"""
    b = bottom_bar(True)
    return None if b is None else b == 'row'


def bottom_state(px: dict, full: bool) -> str:
    """純函式：底部列的取樣色 → 'row'（「關閉 + 頭像」列蓋住切換鈕）/ 'switch'（切換鈕圖示露出，可以點）/ 'other'（都不是：轉場、
    被別的視窗蓋住、完整戰鬥已結束回主畫面〔850,765 是「組隊」〕）。full = 完整戰鬥版面（切換在 850,765），否則主畫面版（763,760）"""
    if all(close(px[(x, y)], (r, g, b), t) for x, y, r, g, b, t in SIG_CLOSE_ROW) and all(max(px[p]) < 95 for p in CLOSE_ROW_DARK):
        return 'row'
    sig = SIG_SWITCH_FULL if full else SIG_SWITCH_MAIN
    return 'switch' if all(close(px[(x, y)], (r, g, b), t) for x, y, r, g, b, t in sig) else 'other'


def bottom_bar(full: bool) -> str | None:
    """一次 gui pixel 讀底部列 → bottom_state；讀不到回 None"""
    sig = SIG_SWITCH_FULL if full else SIG_SWITCH_MAIN
    pts = [(x, y) for x, y, *_ in SIG_CLOSE_ROW] + CLOSE_ROW_DARK + [(x, y) for x, y, *_ in sig]
    try:
        cols = [tuple(int(v) for v in c.split(',')) for c in gui('pixel', ' '.join(f'{x},{y}' for x, y in pts)).split()]
    except Exception:
        return None
    if len(cols) != len(pts) or any(len(c) != 3 for c in cols):
        return None
    return bottom_state(dict(zip(pts, cols)), full)


CLOSE_ROW_CLICKS = [(510, 745), (510, 745), (510, 725), (510, 765)]   # 都在「關閉」直式鈕範圍內（約 y 686～783）；每次嘗試輪流換一個點（errlog #61）
CLOSE_ROW_SETTLE_MS = 500            # 點「關閉」後等多久再讀一次底部列（只點一下就回主迴圈，不再阻塞等 3 秒 × 4 下）
BATTLE_OVER_STATES = ('idle', 'walking', 'dialog', 'reward')   # 看到這些 = 戰鬥已結束（850,765 / 510,745 這時會點到主畫面的「組隊」鈕 / 地面）
REFRESH_DONE = ('ok', 'unverified')  # refresh_characters 這兩種結果算「按到了」（unverified = seq 沒回 waitpix 結果，只有假遊戲 / 測試會這樣）


def battle_over() -> bool:
    """現場讀一次畫面：已經回到主畫面 / 對話 / 領獎 / 巡路（戰鬥剛結束）= True；仍在戰鬥或讀不懂（unknown / error）= False（維持舊行為）"""
    try:
        return read_screen()['state'] in BATTLE_OVER_STATES
    except Exception:
        return False


def waitpix_result(out: str) -> str | None:
    """純函式：gui seq 輸出裡 waitpix 那行 → 'ok' / 'timeout' / 'pwfail'；沒有 waitpix 結果（假遊戲 / 輸出空）→ None"""
    for ln in (out or '').splitlines():
        head = ln.split()[0] if ln.split() else ''
        if head in ('ok', 'timeout', 'pwfail'):
            return head
    return None


def panel_visible() -> bool:
    """切換角色面板是否開著（✕ + 刷新鈕深綠；直接讀像素，戰鬥中 read_screen 會判成 battle 看不出面板）"""
    pts = [(x, y) for x, y, *_ in SIG_PANEL]
    try:
        cols = [tuple(int(v) for v in c.split(',')) for c in gui('pixel', ' '.join(f'{x},{y}' for x, y in pts)).split()]
    except Exception:
        return False
    return len(cols) == len(pts) and all(close(c, (r, g, b)) for c, (_, _, r, g, b, _t) in zip(cols, SIG_PANEL))


CLOSE_ROW_MAX_CLICKS = 2             # 同一場戰鬥「關閉」點了這麼多次列還在 → 不再點，等列自己消失（review §4.2：一場連點十幾下都收不掉）


def refresh_characters(full: bool = False, attempt: int = 0, click_row: bool = True) -> str:
    """戰鬥中按「刷新角色」加速，**只做一次嘗試、不阻塞**（2026-10-13 改；舊版收「關閉」列最多 4 下 × 約 4.5 秒，每場卡 15～20 秒）：
    1. 讀底部列（一次 gui pixel）：
       - 「關閉 + 頭像」列蓋住切換鈕 → 點一下「關閉」（CLOSE_ROW_CLICKS[attempt % 4]）、等 CLOSE_ROW_SETTLE_MS 再讀；還在 → 回 'row'（主迴圈 REFRESH_RETRY 秒後再試）
       - 切換鈕圖示沒露出（轉場 / 被蓋 / 完整戰鬥已結束回主畫面，850,765 是「組隊」）→ 不點，回 'notready'
       - 讀不到像素 → 照舊直接按（不卡住刷新）
    2. 切換（完整戰鬥 850,765 / 快速戰鬥 763,760）→ waitpix 等面板 → 刷新角色 910,578；**看 waitpix 結果**：面板沒出現 → 回 'nopanel'（沒點刷新，主迴圈很快重試）。
       面板還開著就點 ✕。按到了回 'ok'（seq 沒有 waitpix 結果時回 'unverified'，視同按到）。
    click_row=False（本場已點 CLOSE_ROW_MAX_CLICKS 次收不掉）→ 列還在就只回 'row_wait'、不點（等它自己消失；推測是全員指令已送出、等回合結算 / 播放中時的狀態列，點「關閉」無效）。
    主迴圈只把 REFRESH_DONE 當成刷新成功（才開始算 REFRESH_GAP）"""
    b = bottom_bar(full)
    if b == 'row' and not click_row:
        return 'row_wait'
    if b == 'row':
        x, y = CLOSE_ROW_CLICKS[attempt % len(CLOSE_ROW_CLICKS)]
        gui('seq', f'click {x} {y}; wait {CLOSE_ROW_SETTLE_MS}', note='戰鬥底部列：點「關閉」收起頭像列')
        (event if attempt == 0 else log)(f'刷新前底部有「關閉 + 頭像」列 → 點關閉收起（{x},{y}，第 {attempt + 1} 次嘗試）')
        b = bottom_bar(full)
        if b == 'row':
            return 'row'
    if b == 'other':
        return 'notready'
    sw = SWITCH_FULL if full else SWITCH_BTN
    sig = screen_sigs.sig_str(SIG_PANEL)
    out = gui('seq', f'click {sw[0]} {sw[1]}; waitpix 1500 {sig} 40; ifok click {REFRESH_BTN[0]} {REFRESH_BTN[1]}; wait 500')
    w = waitpix_result(out)
    if w is not None and w != 'ok':
        return 'nopanel'
    if panel_visible():
        gui('seq', f'click {PANEL_CLOSE[0]} {PANEL_CLOSE[1]}; wait 500', note='刷新後面板還開著 → 點 ✕ 關')
    return 'ok' if w == 'ok' else 'unverified'


def pick_select_card(blobs: list) -> tuple[int, int] | None:
    """純函式：「選擇對象」面板上，從 findmark 的黃色色塊找 NPC 名字（黃 / 金字；隊友白字不會被抓），回該卡片頭像中心 (x, y)，找不到回 None。
    只取面板內部（SELECT_BOX）、色塊不大（w,h <= 16，排除頭像大片高光）；把 y 相近（相鄰差 <= 12）的色塊併成一排、再把 x 相近（相鄰間隔 <= 30）的併成一個名字，
    像素總數 >= SELECT_MIN_N 才算名字；多個名字取最上排最左一個。點的位置 = 名字外框水平中心、名字中心往上 SELECT_NAME_DY（卡片頭像，不寫死第一格）"""
    x0, y0, x1, y1 = SELECT_BOX
    bs = sorted((b for b in blobs if x0 <= b['x'] <= x1 and y0 <= b['y'] <= y1 and b['w'] <= 16 and b['h'] <= 16), key=lambda b: b['y'])
    rows: list[list[dict]] = []
    for b in bs:
        if rows and b['y'] - rows[-1][-1]['y'] <= 12:
            rows[-1].append(b)
        else:
            rows.append([b])
    for row in rows:
        names: list[list[dict]] = []
        for b in sorted(row, key=lambda b: b['x']):
            if names and b['x'] - b['w'] / 2 - max(c['x'] + c['w'] / 2 for c in names[-1]) <= 30:
                names[-1].append(b)
            else:
                names.append([b])
        for nm in names:
            if sum(b['n'] for b in nm) >= SELECT_MIN_N:
                left, right = min(b['x'] - b['w'] / 2 for b in nm), max(b['x'] + b['w'] / 2 for b in nm)
                cy = sum(b['y'] for b in nm) / len(nm)
                return int(round((left + right) / 2)), int(round(cy)) - SELECT_NAME_DY
    return None


def handle_select_panel() -> bool:
    """「選擇對象」面板開著：用顏色找黃字名字的卡片並點它（之後等對話框）。找不到黃字 → 不點，回 False（呼叫端當不認得，不亂點）"""
    r = ps_json('findmark.ps1')
    pt = pick_select_card(r.get('blobs', []))
    if pt is None:
        log('選擇對象面板：找不到黃 / 金字名字（NPC 不在面板？）→ 不點')
        return False
    gui('seq', f'click {pt[0]} {pt[1]}', note='選擇對象面板：點黃字名字（NPC）那張卡片')
    event(f'選擇對象面板 → 點黃字名字的卡片 {pt[0]},{pt[1]}')
    return True


PANEL_CLOSE = (1064, 208)            # 切換角色面板右上 ✕


# ---- 切換角色面板的隊伍標籤（2026-10-10 實測；面板只列線上角色）----
# 每張卡片左側有「當前 / 線上」標籤 + 深棕小框，框內是隊伍字樣：「隊長」紅字 ≈(217,33,33)、「隊員」黃字、「單人」（沒量過，顏色不明）。
# 框內取樣 15×8 點（x 間隔 2、y 間隔 2），紅點 >= TEAM_MIN_PX → 隊長；黃點 >= TEAM_MIN_PX → 隊員；都不是 → 'other'（單人 / 離線 / 卡片不存在）。
# 左欄卡片（DKB0 / DKB03 / DKB05）框左上 ≈ (452, 卡片 y)；右欄（DKB02 / DKB04）= 左欄 +310。2026-10-10 實機：隊長 DKB0 紅點 30、隊員黃點 42~44。
TEAM_CARDS = {'DKBO': (452, 275), 'DKBO2': (762, 275), 'DKBO3': (452, 360), 'DKBO4': (762, 360), 'DKBO5': (452, 445)}   # 真名字母 O；DKB0… 同義
TEAM_SAMPLE = [(dx, dy) for dy in range(8, 23, 2) for dx in range(6, 35, 2)]
TEAM_MIN_PX = 8
TEAM_CHECK_GAP = 20.0                # （舊：兩次檢查最短間隔；2026-10-11 起改為只在必要時檢查，不再用這個間隔，保留常數給舊測試 / 文件參照）
CHECK_TEAM_TRIES = 3                 # check_team 開不起切換面板時原地重試次數（間隔 CHECK_TEAM_GAP 秒，先確認非戰鬥 / 非對話）
CHECK_TEAM_GAP = 1.0


def classify_team_label(cols: list) -> str:
    """一張卡片隊伍標籤框內的取樣色 → 'leader' / 'member' / 'other'"""
    red = sum(1 for r, g, b in cols if r > 170 and g < 100 and b < 100)
    yel = sum(1 for r, g, b in cols if r > 170 and g > 140 and b < 110)
    if red >= TEAM_MIN_PX and red > yel:
        return 'leader'
    if yel >= TEAM_MIN_PX:
        return 'member'
    return 'other'


def read_team_labels() -> dict | None:
    """切換面板已開著時，一次 pixel 讀 5 張卡片 → {角色: 'leader'|'member'|'other'}；讀不到回 None"""
    pts = [(ax + dx, ay + dy) for ax, ay in TEAM_CARDS.values() for dx, dy in TEAM_SAMPLE]
    try:
        out = gui('pixel', ' '.join(f'{x},{y}' for x, y in pts)).split()
        cols = [tuple(int(v) for v in c.split(',')) for c in out]
    except Exception:
        return None
    if len(cols) != len(pts):
        return None
    n = len(TEAM_SAMPLE)
    return {r: classify_team_label(cols[i * n:(i + 1) * n]) for i, r in enumerate(TEAM_CARDS)}


TEAM_STABLE_MAX_S = 1.5              # 切換面板剛開，卡片內容還沒載入（5 人都讀成「不在隊」，2026-10-11 16:31 馬祖快遞）：最多等這麼久讓內容穩定
TEAM_STABLE_GAP = 0.3


def read_team_labels_stable(max_s: float = TEAM_STABLE_MAX_S, gap: float = TEAM_STABLE_GAP) -> dict | None:
    """面板開啟後等卡片內容穩定再回：連 2 次讀到相同標籤、且不是「全部 other」才算穩（全 other 可能是還在載入，繼續等到 max_s）；
    到時限仍全 other / 不穩 → 回最後一次讀到的（呼叫端據此判斷；全 other 時已經重讀過至少一次才會判失敗）。讀不到像素回 None"""
    t_end = time.time() + max_s
    prev = read_team_labels()
    while True:
        if prev is None:
            return None
        time.sleep(gap)
        cur = read_team_labels()
        if cur is None:
            return None
        if cur == prev and any(v != 'other' for v in cur.values()):
            return cur
        prev = cur
        if time.time() >= t_end:
            return cur


def judge_team(labels: dict, size: int) -> tuple[bool, str]:
    """純函式：labels 是否有「1 隊長 + (size-1) 隊員」。回 (符合, 說明；不符時列出誰不在隊)。
    只看隊伍本身：面板上其他卡片是單人 / 不在隊（'other'，例如單人 DKB0 或離線的人）不算錯（--team-size 4 時第 5 人單人沒關係；size=5 時 5 人都要在隊，因為隊員數要 4）"""
    lead = [r for r, v in labels.items() if v == 'leader']
    mem = [r for r, v in labels.items() if v == 'member']
    out = [r for r, v in labels.items() if v == 'other']
    desc = f'隊長 {lead or "無"}、隊員 {mem or "無"}、不在隊 / 單人 / 離線 {out or "無"}'
    ok = len(lead) == 1 and len(mem) == size - 1
    return ok, desc


def check_team(size: int, tag: str = '') -> tuple[bool | None, str]:
    """開切換面板 → 讀 5 張卡片的隊伍標籤 → 關面板。開 / 關走 uikit.open_panel_ex / close_panel（輪詢驗證，不用固定 wait）。
    回 (True 隊伍符合 / False 不符 / None 面板沒開或讀不到, 說明)。開不起來（切換面板偶發打不開）原地重試 CHECK_TEAM_TRIES 次、間隔 CHECK_TEAM_GAP 秒，
    每次重試前確認畫面是主畫面（idle）；戰鬥 / 對話 / 其他畫面不點、等下一次；只在面板特徵出現後才讀面板內座標。"""
    import uikit
    res: tuple[bool | None, str] = (None, '切換面板沒打開')
    for i in range(CHECK_TEAM_TRIES):
        if i:
            log(f'{tag}隊伍檢查：切換面板沒打開，{CHECK_TEAM_GAP:.0f} 秒後重試（{i + 1}/{CHECK_TEAM_TRIES}）')
            time.sleep(CHECK_TEAM_GAP)
        state = read_screen()['state']
        if state == 'panel':
            opened = True                                  # 已開著（殘留）：直接讀
        elif state != 'idle':
            res = (None, f'畫面是 {state}（不是主畫面），不開切換面板')
            continue
        else:
            note = f'{tag}隊伍檢查：開切換面板'
            log(note)
            opened = uikit.open_panel(uikit.SWITCH, 4.0)
        if not opened:
            res = (None, '切換面板沒打開')
            continue
        labels = read_team_labels_stable()
        if labels is None:
            res = (None, '讀不到隊伍標籤像素')
        else:
            res = judge_team(labels, size)
        if not uikit.close_panel(uikit.SWITCH, known_open=True) and read_screen()['state'] == 'panel':
            gui('key', '{ESC}')
        return res
    return res


def read_pos() -> tuple[int, int, int] | None:
    """stat.ps1 OCR 讀右上角「地圖ID:x,y」→ (地圖, x, y)；讀不到回 None"""
    m = re.match(r'(\d+):(\d+),(\d+)', stat().get('pos') or '')
    return (int(m[1]), int(m[2]), int(m[3])) if m else None


def is_knocked(last: tuple[int, int, int] | None, cur: tuple[int, int, int] | None) -> bool:
    """被打飛 = 現在在薩姆吉爾村 1000 的儲存點附近，而且「上次不在那裡」（換了地圖，或位置突然跳了 > KO_RADIUS 以上）。
    任務本來就在儲存點附近開始時，last 也在附近 → 不算（要真的被傳走才算）；不知道上次位置（last=None）也不算。"""
    if not cur or cur[0] != SAVE_POINT[0]:
        return False
    near = lambda p: p[0] == SAVE_POINT[0] and max(abs(p[1] - SAVE_POINT[1]), abs(p[2] - SAVE_POINT[2])) <= KO_RADIUS
    if not near(cur):
        return False
    return last is not None and not near(last)


STEP_TEXT_BOX = (80, 270, 245, 175)  # 追蹤列表 OCR 區（標題 + 說明行；深棕字，Dark 170 才讀得到較淺的說明行）
STEP_MIN_RATIO = 0.8                 # 說明文字與任務表 explandTn 的相似度門檻（OCR 偶爾錯 1 字）


def norm_step(t: str) -> str:
    """步驟說明比對前的正規化：去空白與標點"""
    return re.sub(r'[\s·・,.:：，。、!！?？「」『』()（）\[\]【】~～\-—]+', '', t or '')


def read_step_ocr(task: str) -> tuple[bool | None, list[str]]:
    """OCR 追蹤列表第一頁區塊。回 (標題找到嗎, 標題下方說明行的各種讀法)；整塊什麼字都讀不到 → (None, [])（OCR 失敗，不能當「任務消失」）。
    不捲動、不點任何東西（純讀）。實測（碧青洞窟）：標題 y≈309、說明行 y≈341（差約 32px）。"""
    x, y, w, h = STEP_TEXT_BOX
    r = ps_json('ocr.ps1', x, y, w, h, '-Zooms', '2,3,4', '-Dark', 170)
    lines = sorted(r.get('lines', []), key=lambda o: o['y'])
    if not lines:
        return None, []
    titles = [ln for ln in lines if len(ln['text']) >= 2 and match_title(task, ln['text'])]
    if not titles:
        return False, []
    ty = min(t['y'] for t in titles)
    return True, [ln['text'] for ln in lines if ty + 18 <= ln['y'] <= ty + 50 and len(ln['text']) >= 2]


def read_step_texts(task: str) -> list[str]:
    """追蹤列表上 task 那一格「正下方那行說明」的各種讀法（Zoom 2/3/4）；標題不在目前這頁 / 讀不到 → []"""
    return read_step_ocr(task)[1]


def skel_step(t: str) -> str:
    """步驟說明的「骨架」：把「數字 + 樓」（OCR 常把「9樓」讀成單字「婁」、「14樓」讀成「楼」之類）收成同一個符號，其餘不變。
    例「通過碧青9樓的挑戰」「通過碧青婁的」→「通過碧青#的挑戰」「通過碧青#的」"""
    return re.sub(r'[0-9０-９]*[樓婁楼樓]', '#', norm_step(t))


STEP_PREFIX_MIN = 5                  # 說明行被面板邊緣截斷時，用「前綴」比對至少要這麼多字（太短會誤配很多步）
STEP_PREFIX_FACTOR = 0.95            # 前綴比對的折扣（完整相符 1.0 仍優先）
STEP_SKEL_FACTOR = 0.9               # 骨架比對（忽略「數字 + 樓」）的折扣：數字讀對的完整文字要贏過「只剩骨架相同」（9樓 vs 14樓 差 >= 0.05 才分得出來）


def step_score(a: str, b: str) -> float:
    """OCR 讀到的說明 a 與任務表說明 b 的相似度（兩者都已 norm_step）：取下列的最大值——
    ① 原文比對；② 說明被截斷時的原文前綴比對（追蹤條目寬度有限，後半段常被截掉或讀不到；a >= STEP_PREFIX_MIN 字才用，打 STEP_PREFIX_FACTOR 折）；
    ③ 骨架比對（把「數字 + 樓」收成同一符號，OCR 常把「9樓」讀成單字「婁」；打 STEP_SKEL_FACTOR 折，避免「通過碧青9樓」「通過碧青14樓」骨架相同時蓋過數字讀對的結果）；④ 骨架前綴（兩個折扣相乘）。
    骨架相同而 NPC 不同的步驟（碧青步 2 / 3）會平手 → match_step 交給「目前所在地圖」判定，判不了才退出碼 31"""
    if a == b:
        return 1.0
    sa, sb = skel_step(a), skel_step(b)
    sm = lambda x, y: difflib.SequenceMatcher(None, x, y).ratio()
    r = max(sm(a, b), sm(sa, sb) * STEP_SKEL_FACTOR)
    if len(a) >= STEP_PREFIX_MIN and len(b) > len(a):
        r = max(r, sm(a, b[:len(a)]) * STEP_PREFIX_FACTOR)
    if len(sa) >= STEP_PREFIX_MIN and len(sb) > len(sa):
        r = max(r, sm(sa, sb[:len(sa)]) * STEP_SKEL_FACTOR * STEP_PREFIX_FACTOR)
    return r


def _npc_map_of(row: dict):
    try:
        return (walk.psa.by_id('Npc').get(row.get('endNpc')) or {}).get('map')
    except Exception:
        return None


def match_step(ts: list, texts: list[str], cur_map_fn=None) -> tuple[dict | None, str]:
    """純函式：追蹤條目說明文字 texts（OCR 各種讀法）對任務表各步的 explandTn / explandCn。
    取相似度（step_score：原文 / 忽略「數字+樓」誤讀 / 說明被截斷的前綴）最高且 >= STEP_MIN_RATIO 的步驟。
    有另一個「不同 NPC」的步驟相似度差 < 0.05 → 視為對不準；但若給了 cur_map_fn（回傳目前所在地圖 ID 或 None），
    就用「--fight 本來就站在 NPC 旁」這個事實，只留 NPC 在目前地圖的候選：剛好剩 1 個 NPC（可能多步同 NPC，取最前一步）才採用，其他情況回 None（退出碼 31）。回 (步驟列或 None, 說明)"""
    best: dict[int, float] = {}
    for tx in texts:
        a = norm_step(tx)
        if not a:
            continue
        for k, t in enumerate(ts):
            for fld in ('explandTn', 'explandCn'):
                b = norm_step(t.get(fld))
                if b:
                    best[k] = max(best.get(k, 0.0), step_score(a, b))
    if not best:
        return None, '追蹤條目說明文字讀不到'
    rank = sorted(best.items(), key=lambda kv: (-kv[1], kv[0]))
    k0, r0 = rank[0]
    if r0 < STEP_MIN_RATIO:
        return None, f'說明文字 {texts} 對不到任務表任何一步（最像 第 {ts[k0].get("step")} 步，相似度 {r0:.2f} < {STEP_MIN_RATIO}）'
    close_ks = [k for k, r in rank if r0 - r < 0.05]
    if len({ts[k].get('endNpc') for k in close_ks}) > 1:
        steps = '、'.join(str(ts[k].get('step')) for k in close_ks)
        cur = cur_map_fn() if cur_map_fn else None
        same = [k for k in close_ks if cur and _npc_map_of(ts[k]) == cur]
        if len({ts[k].get('endNpc') for k in same}) == 1:
            k0 = same[0]
            return ts[k0], f'說明文字 {texts} 相似步驟 {steps}（NPC 不同）→ 依目前所在地圖 {cur} 判定第 {ts[k0].get("step")} 步（相似度 {best[k0]:.2f}）'
        return None, f'說明文字 {texts} 同時像第 {steps} 步（NPC 不同），無法判定；請改用 --step N'
    return ts[k0], f'說明文字 {texts} → 第 {ts[k0].get("step")} 步（相似度 {r0:.2f}）'


def warn_not_battle(row: dict) -> None:
    """--fight 點 NPC 前：任務表這一步不是戰鬥步（talk / monster）→ 印警告（可能是步驟抓錯，或這步其實只要對話）"""
    kind, why = walk.psa.classify_step(row)
    if kind != 'battle':
        event(f'警告：第 {row.get("step")} 步不是戰鬥步（{kind}；{why}）→ 點 NPC 後可能不開打（退出碼 {EXIT_NO_BATTLE}）；確認步驟對不對')


def npc_map_of_xy(task: str, xy: tuple[int, int]):
    """--npc X,Y 有 --task 時：用任務表各步 endNpc 的座標反查該 NPC 的地圖（座標只對到一張圖才回；對不到 / 多張圖 → None）"""
    try:
        g, ts, _ = walk.psa.task_steps(task)
        npcs = walk.psa.by_id('Npc')
        maps = {(npcs.get(t.get('endNpc')) or {}).get('map') for t in ts
                if (npcs.get(t.get('endNpc')) or {}).get('x') == xy[0] and (npcs.get(t.get('endNpc')) or {}).get('y') == xy[1]}
    except Exception:
        return None
    maps.discard(None)
    return maps.pop() if len(maps) == 1 else None


def step_by_map(ts: list, cur_map) -> tuple[dict | None, str]:
    """純函式：追蹤文字讀不到 / 對不到時的備援——目前所在地圖 cur_map 剛好只對應任務的「一個」打 BOSS / 對話步驟（endNpc 在該圖，
    打怪(人工) 步不算）才採用；對應 0 個或多個 → None（呼叫端回 31）。例：漆黑洞窟(二轉) 在 32020 → 步 4 帖拉所伊朵 20,9；32021 有步 5 / 6 → 不採用"""
    if not cur_map:
        return None, '讀不到目前所在地圖'
    cand = [t for t in ts if _npc_map_of(t) == cur_map and walk.psa.classify_step(t)[0] in ('battle', 'talk')]
    if len(cand) == 1:
        return cand[0], f'地圖 {cur_map} 只對應第 {cand[0].get("step")} 步'
    return None, (f'地圖 {cur_map} 沒有對應的打 BOSS / 對話步驟' if not cand else f'地圖 {cur_map} 對應多個步驟（{[t.get("step") for t in cand]}），無法判定')


def resolve_npc(a) -> tuple[int, int] | None:
    """--fight 的 NPC 地圖座標：--npc X,Y，或 --npc auto = 「目前步驟」的 endNpc（--task 任務；--step N 明確指定，不給就 OCR 追蹤條目下方的說明行
    對照 Task 表 explandTn）。讀不到 / 對不到 → 不退回第一個戰鬥步（2026-10-10 抓錯 8 樓守護獸的事故），a.resolve_rc = EXIT_STEP_UNKNOWN，回 None"""
    a.resolve_rc = 4
    if a.npc.lower() == 'auto':
        if not a.task:
            log('--npc auto 需要 --task（用任務步驟找目前步驟的 NPC）')
            return None
        g, ts, _ = walk.psa.task_steps(a.task)
        if not ts:
            log(f'任務表找不到「{a.task}」')
            a.resolve_rc = EXIT_STEP_UNKNOWN
            return None
        if a.step:
            row = next((t for t in ts if t.get('step') == a.step), None)
            why = f'--step {a.step}'
        else:
            row, why = match_step(ts, read_step_texts(a.task), None if a.at else (lambda: (read_pos() or (None,))[0]))
            if row is None and not a.at and (why.startswith('追蹤條目說明文字讀不到') or '對不到任務表' in why):
                # 備援：追蹤文字 OCR 失敗 → 用目前所在地圖反查（只對應唯一一個打 BOSS / 對話步驟才採用；2026-10-12 漆黑洞窟(二轉) 32020 實機）
                row2, why2 = step_by_map(ts, (read_pos() or (None,))[0])
                if row2 is not None:
                    row, why = row2, f'追蹤文字失敗（{why}）→ 地圖反查：{why2}'
                    event(f'--npc auto：{why}')
                else:
                    why = f'{why}；地圖反查也不行（{why2}）'
        if row is None:
            event(f'--npc auto 取不到目前步驟：{why} → 不點 NPC，退出碼 {EXIT_STEP_UNKNOWN}（請 shot 看追蹤條目，改用 --step N 或 --npc X,Y）')
            a.resolve_rc = EXIT_STEP_UNKNOWN
            return None
        n = walk.psa.by_id('Npc').get(row.get('endNpc'))
        if not n:
            event(f'--npc auto：第 {row.get("step")} 步（{why}）沒有 endNpc → 退出碼 {EXIT_STEP_UNKNOWN}')
            a.resolve_rc = EXIT_STEP_UNKNOWN
            return None
        kind = walk.psa.classify_step(row)[0]
        warn_not_battle(row)
        event(f'--npc auto：目前步驟 = 第 {row.get("step")} 步（{why}；{kind}）→ {walk.psa.nm(n)} @ 地圖 {n.get("map")}:{n.get("x")},{n.get("y")}')
        a.npc_map = n.get('map')
        a.step_no = row.get('step')           # 點 NPC 前的步驟（BOSS 戰後比對輸贏用）
        return (n['x'], n['y'])
    m = re.fullmatch(r'(\d+)[,:](\d+)', a.npc.strip())
    if not m:
        log('--fight 要給 --npc X,Y（NPC 地圖座標）/ --npc auto（用 --task 查），或加 --no-click（已自己點過 NPC）')
        return None
    xy = (int(m[1]), int(m[2]))
    a.npc_map = getattr(a, 'npc_map_arg', None) or (npc_map_of_xy(a.task, xy) if a.task else None)
    return xy


GONE = 'GONE'                        # 步驟比對：任務已不在追蹤列表（= 任務完成）
HP_LOW_PCT = 3                       # BOSS 戰後血量 < 這個 % 或 hp==1 → 輸掉的佐證（不單獨判輸贏）


def judge_boss_result(pos0, pos1, step0, step1, hp_pct, team_ok) -> tuple[int, str]:
    """純函式：BOSS 戰打完（閒置）後判斷輸贏，回 (退出碼, 理由)。
    pos0 / pos1 = 點 NPC 前 / 打完後的 (地圖, x, y) 或 None；step0 / step1 = 任務步驟編號、GONE（任務已從追蹤列表消失）或 None（讀不到）；
    hp_pct = 打完後角色血量 %（None = 讀不到；< HP_LOW_PCT 只當佐證寫進理由）；team_ok = 隊伍檢查（False 少人 / None 讀不到）。
    順序：隊伍不完整 32 → 被打飛回村 21 → 地圖換了 0 → 步驟變了 / 任務消失 0 → 地圖與步驟都讀到且相同 35 → 其他 36（判斷不了，不回 0）"""
    hp_note = f'；HP {hp_pct}%（偏低）' if hp_pct is not None and hp_pct < HP_LOW_PCT else ''
    if team_ok is False:
        return EXIT_TEAM_LOST, f'打完後隊伍不完整（有人脫隊 / 陣亡被踢）{hp_note}'
    if pos0 and pos1 and is_knocked(pos0, pos1):
        return EXIT_KNOCKED, f'被打飛回村 {pos0} → {pos1}'
    if pos0 and pos1 and pos0[0] != pos1[0]:
        return 0, f'地圖換了 {pos0[0]} → {pos1[0]}（贏）'
    if step0 is not None and step1 is not None and step1 != step0:
        return 0, ('任務已從追蹤列表消失（贏，任務完成）' if step1 == GONE else f'任務步驟 {step0} → {step1}（贏）')
    if pos0 and pos1 and step0 is not None and step1 is not None:
        return EXIT_BOSS_LOST, f'地圖 {pos1[0]} 與任務步驟 {step0} 都沒變 → 沒打贏{hp_note}'
    miss = '、'.join(n for n, v in (('點 NPC 前座標', pos0), ('打完後座標', pos1), ('點 NPC 前步驟', step0), ('打完後步驟', step1)) if v is None)
    return EXIT_BOSS_UNKNOWN, f'判斷不了輸贏（{miss} 讀不到；沒給 --task 或 OCR 失敗）{hp_note}'


def stalled(rounds: int, same_marker: bool, limit: int = STALL_MAX) -> bool:
    """純函式：對話無進展 = 同一個黃問號已經「點 → 對話」了 limit 輪，期間沒有領獎 / 戰鬥 / 巡路 / 換圖（卡坦事故：722,318 循環 21 次）"""
    return same_marker and rounds >= limit


def read_step_no(task: str, cur_map_fn=None, reveal: bool = True):
    """OCR 追蹤列表判斷目前任務步驟編號：Task.step / GONE（標題不在第一頁區塊，但 OCR 有讀到別的字）/ None（讀不到、對不準）。
    reveal = 標題讀到但說明行被下緣裁掉時，把追蹤列表往下捲一格再讀（只拖列表）"""
    if not task:
        return None
    g, ts, _ = walk.psa.task_steps(task)
    if not ts:
        return None
    found, texts = read_step_ocr(task)
    if found is None:
        return None
    if not found:
        return GONE
    if not texts and reveal:
        # 標題在追蹤列表下緣、說明行被裁掉（2026-10-12 bossretry 實機：DKBO3 的「四寶玉之謎」是第 2 張卡，只露標題 → 一直 None 142）
        # → 列表往下捲一格讓整張露出再讀一次（只拖追蹤列表，不點任何卡片）
        moved, _ = scroll_list(SCROLL_UP, f'「{task}」卡片說明行被裁掉 → 追蹤列表往下捲一格再讀步號', list_signature())
        if moved:
            found, texts = read_step_ocr(task)
            if found is None:
                return None
            if not found:
                return GONE
    row, _why = match_step(ts, texts, cur_map_fn)
    return row.get('step') if row else None


def capture_pre(a) -> dict:
    """--fight 點 NPC 前記下座標與步驟（BOSS 戰後比對）。--npc auto / --step 已有 a.step_no；--npc X,Y 有 --task 時補讀說明行"""
    pre = {'pos': read_pos(), 'step': getattr(a, 'step_no', None)}
    if pre['step'] is None and a.task and not a.no_click:
        v = read_step_no(a.task, lambda: (pre['pos'] or (None,))[0])
        pre['step'] = None if v == GONE else v
        if pre['step'] is not None:
            row = next((t for t in walk.psa.task_steps(a.task)[1] if t.get('step') == pre['step']), None)
            if row:
                warn_not_battle(row)
    return pre


def verify_boss_result(a, pre: dict, team_size: int, team_on: bool) -> int:
    """--fight BOSS 戰打完閒置後：重驗隊伍 / 座標 / 步驟 / 血量，依 judge_boss_result 回退出碼並寫事件 log"""
    team_ok = check_team(team_size, 'BOSS 戰後：')[0] if team_on else None
    pos1 = None
    for _ in range(3):
        if (pos1 := read_pos()):
            break
        time.sleep(1.0)
    step1 = read_step_no(a.task, lambda: (pos1 or (None,))[0]) if a.task else None
    st = stat()
    hp_pct = st.get('hpPct')
    if st.get('hp') == 1:
        hp_pct = 0
    rc, why = judge_boss_result(pre.get('pos'), pos1, pre.get('step'), step1, hp_pct, team_ok)
    event(f'BOSS 戰結果判斷：{why} → 退出碼 {rc}（點前 {pre.get("pos")} 步驟 {pre.get("step")}；後 {pos1} 步驟 {step1}；hp {st.get("hp")} / {hp_pct}%）', None if rc == 0 else snap('boss-result'))
    return rc


def click_npc(npc: tuple[int, int], a) -> bool:
    """依自己的座標算 NPC 的畫面位置並點一下（走路函式 walk.npc_screen；不巡路、不亂走）。座標讀不到 / 太遠 / 地圖不符 → False"""
    if a.at:
        m = re.fullmatch(r'(\d+),(\d+)', a.at.strip())
        cur = (getattr(a, 'npc_map', None), int(m[1]), int(m[2])) if m else None
    else:
        cur = None
        for _ in range(3):
            if (cur := read_pos()):
                break
            time.sleep(1.0)
    if not cur:
        log('讀不到自己的座標（--at X,Y 可手動給）')
        return False
    want_map = getattr(a, 'npc_map', None)
    if want_map and cur[0] and cur[0] != want_map:
        event(f'目前在地圖 {cur[0]}，NPC 在地圖 {want_map}：不在同一張圖，先傳送 / 走過去（--fight 不巡路）→ 沒點 NPC，退出碼 {EXIT_NPC_MAP}')
        a.click_rc = EXIT_NPC_MAP
        return False
    at = (cur[1], cur[2])
    dx, dy = npc[0] - at[0], npc[1] - at[1]
    if not walk.reachable(dx, dy):
        log(f'NPC {npc} 離我 {at} 太遠或點擊位置落在 UI 上（dx={dx}, dy={dy}）→ 先走近一點再跑 --fight')
        return False
    nx, ny = walk.npc_screen(npc, at)
    gui('seq', f'{PRIMER}; click {nx} {ny}', note=f'--fight 點 NPC {npc}（我在 {at}）')
    event(f'--fight 點 NPC {npc}（我在 {at}）→ 畫面 {nx},{ny}')
    return True


def _main() -> int:
    ap = argparse.ArgumentParser(description='解任務監測：對話按確認、戰鬥按刷新角色、巡路停了重點任務追蹤')
    ap.add_argument('--once', action='store_true', help='只判斷一次、做一個動作就結束')
    ap.add_argument('--every', type=float, default=None, help='輪詢間隔秒數（預設 1.0；連續 N 次的規則已換算成秒，見 IDLE_CONFIRM_SECS 等）')
    ap.add_argument('--solo', action='store_true', help='單人逃跑風格（手動逃跑）：完整戰鬥按逃跑鈕（自動戰鬥開著先關）；路上小怪不刷新；到 NPC 出對話框 → ESC 後停下（退出碼 20）；被打飛退出碼 21')
    ap.add_argument('--stop-after-dialog', action='store_true', help='對話框按完、回主畫面連續閒置 2 次就結束（沒有獲得物品視窗的對話步用；組隊後單步對話用，避免自動點下一步追蹤開始巡路）')
    ap.add_argument('--disband-after', action='store_true', help='這步完成（--stop-after-dialog / --stop-after-rewards 結束）後立刻解散隊伍：切組隊分頁 → 點隊長列 → 解散，每步驗證，失敗退出碼 %d 且不亂點' % EXIT_DISBAND_FAIL)
    ap.add_argument('--fight', action='store_true', help='戰鬥步（要先站在 NPC 附近；不巡路）：點 NPC → 對話左鈕 → 開打；只有點 NPC / 按對話框後 %d 秒內開始的才是任務 / BOSS 戰（開自動戰鬥 + 刷新角色、打完退出碼 0）；其他戰鬥是路上小怪（關自動戰鬥、按逃跑、不刷新）；沒反應退出碼 22、對話後沒開打 23、被打飛 21' % QUEST_BATTLE_WINDOW)
    ap.add_argument('--npc', default='', help='--fight 用：NPC 的地圖座標 X,Y，或 auto（讀追蹤條目目前步驟說明對 --task 的任務表找 NPC；讀不到退出碼 31，可改 --step N）；不給 = 必須加 --no-click')
    ap.add_argument('--npc-map', type=int, default=0, help='--fight --npc X,Y 用：NPC 所在地圖 ID（不給時，有 --task 會用任務表反查該座標的 NPC 地圖）；與目前所在地圖不同 → 退出碼 %d，不點' % EXIT_NPC_MAP)
    ap.add_argument('--step', type=int, default=0, help='--fight 用：明確指定任務第 N 步（Task.step）的 endNpc 當 NPC（等於 --npc auto 但不 OCR 追蹤條目；需要 --task）')
    ap.add_argument('--team-size', type=int, default=None, help='隊伍人數檢查（預設 5）：--fight 點 NPC 前、預設模式每次點追蹤 / 黃問號前，開切換面板確認 1 隊長 + (N-1) 隊員，不符 → 不點（--fight 退出碼 %d、執行中脫隊 %d）；開始前第一次點 / 按對話框前一定先驗（不符 30）；0 或 1 = 跳過；--solo / --fight --no-click 不檢查' % (EXIT_TEAM_MISMATCH, EXIT_TEAM_LOST))
    ap.add_argument('--team-fresh', action='store_true', help='呼叫端（questrun）剛驗過 5 人隊伍（≤30 秒：team.form 成功 / 上一片 37）→ 「開始前」那次隊伍檢查略過，不開切換面板；領獎後 / 任務戰後 / BOSS 後的檢查照舊（2026-10-12）')
    ap.add_argument('--at', default='', help='--fight 用：自己目前的座標 X,Y（不給就 OCR 讀右上角）')
    ap.add_argument('--no-click', action='store_true', help='--fight 用：不點 NPC（已手動點過 / 對話已開），從現在起算開打時間窗')
    ap.add_argument('--max-seconds', type=int, default=900, help='最長執行秒數（預設 900）')
    ap.add_argument('--task', default='', help='追蹤列表上的任務名（例：黃金羚羊之謎）；點追蹤前先 OCR 核對標題，名稱不符絕不點')
    ap.add_argument('--no-marker', action='store_true', help='不找 NPC 頭上的黃色問號')
    ap.add_argument('--no-track', action='store_true', help='不主動點任務追蹤')
    ap.add_argument('--no-refresh', action='store_true', help='戰鬥不按刷新角色（預設：--solo / --fight 只在任務 / BOSS 戰刷新，組隊預設模式每場都刷新）')
    ap.add_argument('--stop-after-rewards', type=int, default=0, help='領到第 N 次獲得物品視窗後停（0 = 不停）')
    ap.add_argument('--no-stop-after-boss', action='store_true', help='預設模式（非 --solo / --fight）：任務 BOSS 戰（對話 / 黃問號後 %d 秒內開打）打完閒置確認後預設會先驗隊伍再停（退出碼 %d 滿員 / %d 不滿）；加這個旗標 = 不停、照舊一路連跑（呼叫端自己負責驗隊伍與不可逆步驟）' % (QUEST_BATTLE_WINDOW, EXIT_BOSS_DONE, EXIT_BOSS_TEAM))
    ap.add_argument('--hp-check-min', type=int, default=0, help='預設模式：每打完 --hp-check-every 場戰鬥、回主畫面閒置確認後讀全隊 HP（開背包約 8 秒），任一人低於這個 %%%% → 結束本片，退出碼 %d（questrun 補血後續片）；0 = 不檢查' % EXIT_HP_LOW)
    ap.add_argument('--hp-check-every', type=int, default=HP_CHECK_EVERY, help='--hp-check-min：路上一般戰鬥每幾場讀一次（預設 %d；0 = 只在任務戰後讀）' % HP_CHECK_EVERY)
    ap.add_argument('--allow-irreversible', action='store_true', help='不檢查對話框是否含不可逆關鍵字（%s）：預設遇到會不按、存 snap、退出碼 %d；人 / agent 看過截圖確認要做才加' % ('、'.join(IRREVERSIBLE_KEYWORDS), EXIT_IRREVERSIBLE))
    a = ap.parse_args()
    a.npc_map_arg = a.npc_map or None
    a.npc_map = None
    if a.step and not a.npc:
        a.npc = 'auto'
    if layout.current() != '2880x1659':
        log('quest.py 只量過 2880×1659 版面，先跑 gui.sh max；見 ui/layout-1920x1017.md')
        return 4
    if a.solo and a.fight:
        log('--solo（逃跑）與 --fight（打）互斥')
        return 4
    if a.disband_after and (a.solo or a.fight or not (a.stop_after_dialog or a.stop_after_rewards)):
        log('--disband-after 只能搭配 --stop-after-dialog 或 --stop-after-rewards（不可與 --solo / --fight 並用）')
        return 4
    if a.every is None:
        a.every = DEFAULT_EVERY
    npc_xy = None                        # --fight：要點的 NPC 地圖座標
    if a.fight:
        a.no_track = True                # --fight 假設已站在 NPC 旁，絕不點任務追蹤巡路
        if not a.no_click:
            npc_xy = resolve_npc(a)
            if npc_xy is None:
                return a.resolve_rc
    guard_ko = a.solo or a.fight         # 只有這兩種風格才會被打飛後要停手
    boss_stop = not (a.solo or a.fight or a.no_stop_after_boss)   # 預設模式：BOSS 戰打完就停（--no-stop-after-boss 關）
    if not a.no_track and not a.task:
        log('沒給 --task：不知道要點哪個任務追蹤（點錯任務是之前的老問題）。請加 --task 任務名，或用 --no-track（只處理對話 / 戰鬥）')
        return 4
    n_old = cleanup_old_shots()
    if n_old:
        event(f'清理 {n_old} 張 {SHOT_KEEP_DAYS} 天前截圖')
    wclock = WalkClock(a.max_seconds, time.time())       # 自動走路中不計時（只有連續非 walking 才耗 --max-seconds）
    WALK['clock'] = wclock
    STATS.clear()
    wstuck = WalkStuck()                                 # Auto Walking 但座標不動 → 點地面解卡（WALK_STUCK_S）
    marker_fail = 0              # 連續點黃色問號沒反應的次數
    task_miss = 0
    event(f'開始監測（每 {a.every}s，最長 {a.max_seconds}s）')
    unknown = 0
    unknown_t0 = 0.0             # 這一串不認得的第一次時間
    trans_t0 = 0.0               # 這一串轉場畫面（載入圖 / 全黑）的第一次時間；0 = 不在轉場
    track_fail = 0
    track_t = 0.0                # 最後一次點任務追蹤的時間（TRACK_RETRY_SECS）
    idle_t0 = 0.0                # 這一串閒置的第一次時間（IDLE_CONFIRM_SECS）
    tracked = False              # 剛點過任務追蹤，還沒看到任何反應
    rewards = 0
    checked_rewards = 0          # 已做過「領獎後完整列表檢查」的獎勵次數
    last = ''
    battles = dialogs = 0
    last_full_log = 0.0
    last_action = 0.0            # 最後一次對話框 / 點 NPC / 點問號的時間（time.time()）
    quest_battle = False         # 目前這場戰鬥是不是任務戰鬥（戰鬥開始那一刻決定）
    prev_st = ''
    idle_streak = 0
    last_pos = None                              # 上一次讀到的 (地圖, x, y)；對戰鬥畫面 OCR 會讀不到，起點最多試 3 次
    for _ in range(3 if guard_ko else 0):
        if (last_pos := read_pos()) or read_screen()['state'] == 'battle':
            break
        time.sleep(1.0)
    last_pos_t = time.time()
    ko_pending = False           # 剛打完一場 / 讀圖中 → 下次閒置時查一次位置
    last_click_t = 0.0           # 逃跑 / 自動戰鬥鈕最後一次點擊時間（避免連點）
    battle_t0 = 0.0              # 這場戰鬥開始時間
    in_battle = False            # 戰鬥中（直到看到主畫面 / 對話 / 領獎 / 巡路才算結束；中間 unknown / panel 不重新分類）
    boss = False                 # 目前這場是不是 BOSS 戰（戰鬥開始那一刻決定，打完才重設）
    boss_seen = False            # --fight：已打過 BOSS 戰
    npc_click_t = 0.0            # --fight：點 NPC 的時間
    warned_quick = False
    auto_presses = 0             # 組隊預設模式：本場戰鬥按自動戰鬥鈕的次數
    select_loops = 0             # 選擇對象面板累計次數（領獎 / 戰鬥 / 巡路歸零；對話夾在中間不歸零）
    select_tries = 0             # 連續幾輪看到「選擇對象」面板（點了還在就別一直點）
    byes = 0                     # 已 ESC 關掉的「只有再見」閒聊對話次數（BYE_MAX）
    last_select_t = 0.0          # 最後一次點「選擇對象」卡片的時間（BYE_SELECT_WINDOW：之後出現的「只有再見」= 點到別人的閒聊）
    quest_since_hp = road_since_hp = 0   # --hp-check-min：上次讀全隊 HP 之後打完的任務戰 / 路上一般戰鬥場數（hp_check_due）
    row_clicks = 0               # 本場戰鬥點「關閉」收列沒成功的次數（CLOSE_ROW_MAX_CLICKS 後只等不點）
    last_refresh_t = 0.0         # 本場戰鬥最後一次按刷新角色的時間（REFRESH_GAP）
    refresh_tries = 0            # 本場戰鬥連續幾次刷新沒成功（面板沒開 / 關閉列還在 / 切換鈕沒露出）
    if guard_ko:
        event(f'模式：{"單人逃跑 --solo" if a.solo else "戰鬥步 --fight"}；起點 {last_pos}')
    team_size = 5 if a.team_size is None else a.team_size
    team_on = team_size > 1 and not a.solo and (bool(npc_xy) if a.fight else True)     # --solo 本來就是單人跑；--fight --no-click 不點 NPC。預設模式即使 --no-track 也會按對話框 → 一樣要驗隊伍
    last_team_check = 0.0
    team_dirty = False           # 任務 / BOSS 戰剛打完（隊伍可能散）→ 下一次點追蹤 / 黃問號前要驗隊伍；平常的點擊不驗
    pre_checked = not team_on or a.team_fresh    # 第一次點任何東西 / 按對話框之前是否已驗過隊伍（不受 TEAM_CHECK_GAP 限制）；--team-fresh = 呼叫端剛驗過
    if team_on and a.team_fresh:
        log('開始前隊伍檢查略過（--team-fresh：呼叫端剛驗過 5 人隊伍）')
    stall_rounds = 0             # 對話無進展：每次從非對話進入對話 +1（領獎 / 戰鬥 / Auto Walking / 換地圖 / 換黃問號歸零）
    stall_marker = None          # 最後一次點的黃問號 (x, y)；None = 沒點過（沒點問號就不判無進展）
    stall_map = None             # 上次進對話時的地圖
    stall_leave_t = 0.0          # 最後一次離開對話狀態的時間
    stall_marker_new = False     # 離開對話後有點過黃問號（多頁對話中間閒置不計輪）
    stall_prev = ''              # 上一個迴圈的狀態
    boss_pre = {}                # --fight：點 NPC 前的座標 / 步驟（verify_boss_result 比對）
    post_track = False           # 對話框 / 領獎關閉後回到主畫面：第一個動作先點追蹤欄該任務卡片（標題相符才點）；卡片不在 / 追蹤沒反應才找黃問號
    post_track_clicked = False   # 剛才那次追蹤是 post_track 發起的（沒反應時改找黃問號，不直接退出碼 3）
    dialog_esc = 0               # 啟動時對話框已開：為了開切換面板先 ESC 關掉的次數

    def post_track_try():
        """對話框 / 領獎關閉後的第一個動作：點追蹤欄該任務卡片。回 None = 沒做（不是對話後 / 卡片不在 / 畫面變了 → 呼叫端接著找黃問號）、
        0 = 已點追蹤（等巡路）、其他 = 隊伍檢查失敗的退出碼"""
        nonlocal post_track, tracked, track_t, post_track_clicked, task_miss, stall_marker, stall_marker_new
        if not post_track:
            return None
        post_track = False
        if (rc_ := team_gate('點追蹤 / 黃問號前：', EXIT_TEAM_LOST)):
            return rc_
        res_ = track_task(a.task)
        if res_:
            tracked, track_t, post_track_clicked = True, time.time(), True
            task_miss = 0
            stall_marker, stall_marker_new = (-999, -999), True       # 無進展偵測：追蹤開始的對話也算一輪（沒有黃問號座標，用哨兵）
            return 0
        log('對話後追蹤欄沒有可點的任務卡片' + ('（畫面變了）' if res_ is None else '') + '，改找黃色問號')
        return None

    def team_gate(tag: str, code: int, force: bool = False) -> int:
        """點 NPC / 追蹤前的隊伍檢查（脫隊偵測的保底做法：聊天日誌「離開了隊伍」讀不可靠，所以每次要點之前確認隊伍還在）。
        符合（或不檢查 / 剛檢查過）回 0；隊伍不符或讀不到 → 寫事件 log 回 code（呼叫端直接 return）"""
        nonlocal last_team_check
        nonlocal team_dirty
        if not team_on or (not force and not team_dirty):
            return 0                                           # 只在必要時檢查（2026-10-11）：開始前 / --fight 點 NPC 前 / 領獎後下一步前 / 任務戰結束後；其他點擊不檢查
        ok_, desc = check_team(team_size, tag)
        last_team_check = time.time()
        if ok_:
            team_dirty = False
            log(f'隊伍檢查通過：{desc}')
            return 0
        shot = snap('team-mismatch')
        if ok_ is None:
            event(f'{tag}隊伍檢查失敗：{desc} → 無法確認隊伍完整，不點，退出碼 {code}', shot)
        else:
            event(f'{tag}隊伍不符（要 1 隊長 + {team_size - 1} 隊員）：{desc} → 有人不在隊，不點，退出碼 {code}', shot)
        print('隊伍不完整，沒有點 NPC / 追蹤', flush=True)
        return code

    if a.fight:
        if npc_xy and read_screen()['state'] == 'idle':
            rc = team_gate('--fight 點 NPC 前：', EXIT_TEAM_MISMATCH, force=True)
            if rc:
                return rc
            pre_checked = True
        if npc_xy:
            boss_pre = capture_pre(a)
            if not click_npc(npc_xy, a):
                return getattr(a, 'click_rc', 4)
            npc_click_t = last_action = time.time()
        elif a.no_click:
            boss_pre = capture_pre(a)
            last_action = time.time()
            event('--fight --no-click：不點 NPC，從現在起算 BOSS 戰時間窗')
    while True:
        nap = a.every                # 這一輪結束後睡多久（戰鬥中刷新角色快到期時縮短，見 battle 分支）
        s = read_screen()
        st = s['state']
        wclock.tick(st, time.time())
        if st in ('idle', 'walking', 'dialog', 'reward'):
            if in_battle:
                battleguard.release()          # 戰鬥結束 → 刪鎖檔，ass.py 可以動了
                STATS['battles'] = STATS.get('battles', 0) + 1
                if quest_battle:
                    quest_since_hp += 1
                    team_dirty = True          # 任務戰打完：下次點之前驗隊伍
                else:
                    road_since_hp += 1
            in_battle = False
        in_battle_new = st == 'battle' and not in_battle
        if in_battle_new:
            in_battle = True
            battleguard.acquire(f'quest.py {"--solo" if a.solo else "--fight" if a.fight else "預設"}')   # 戰鬥中鎖檔：ass.py 看到就不改外掛設定
            battle_t0 = time.time()
            quest_battle = is_quest_battle(last_action, time.time())
            boss = quest_battle
            boss_seen = boss_seen or boss
            log(f'戰鬥開始：{"任務戰鬥（對話 / 點 NPC 後 %ds 內）" % QUEST_BATTLE_WINDOW if quest_battle else "一般遇敵"}')
            if a.fight:
                event(f'--fight 戰鬥開始：{"任務 / BOSS 戰（點 NPC / 對話後 %.0f 秒）→ 自動戰鬥 + 刷新角色" % (time.time() - last_action) if boss else "路上小怪 → 手動逃跑（不刷新）"}')
        if guard_ko and prev_st == 'battle' and st != 'battle':
            ko_pending = True
        prev_st = st
        if st != 'select':
            select_tries = 0
        else:
            select_tries += 1
            if select_tries == 1:
                select_loops += 1
                if select_loops > SELECT_LOOP_MAX:
                    shot = snap('select-loop')
                    event(f'對話 → 選擇對象面板 循環 {select_loops - 1} 次沒領獎 / 沒戰鬥 / 沒巡路 → 停手，退出碼 {EXIT_SELECT_LOOP}（人工看對話內容 / 任務條件，例：寵物沒湊齊）', shot)
                    print('對話 / 選擇面板循環無進展，已停手', flush=True)
                    return EXIT_SELECT_LOOP
            if select_tries <= SELECT_MAX_TRIES and handle_select_panel():
                last_action = last_select_t = time.time()      # 點了 NPC = 任務互動（戰鬥時間窗從這裡起算）
                if npc_click_t:
                    npc_click_t = last_action                  # --fight：「點 NPC 後 12 秒沒反應」重新計時（還要等 NPC 走過來開對話框）
                if a.once:
                    return 0
                time.sleep(a.every)
                continue
            st = 'unknown'                                     # 找不到黃字 / 點了面板還在 → 不亂點，照「不認得」規則（3 次 + 5 秒 → 交給使用者）
            s = dict(s, state='unknown')
        if st in ('unknown', 'error'):
            # 先給 netwatch 看：「網路異常，是否重連?」提示 / 登入畫面（自動按登錄重登；失敗才 halt exit 10，不輸入帳密）
            nr = netwatch.guard('quest')
            if nr['status'] == 'reconnected':
                event('網路斷線後已恢復（netwatch），重新判斷畫面')
                tracked, track_fail, marker_fail, last, unknown = False, 0, 0, '', 0
                continue
            if nr.get('failed'):
                continue
        if st != last:
            log(f'狀態 {last or "-"} → {st}' + (f'（金黃點 {s["gold"]}）' if st in ('walking', 'idle') else ''))
        last = st
        if st != 'unknown':
            unknown = 0
            trans_t0 = 0.0
        if st == 'idle':
            if idle_streak == 0:
                idle_t0 = time.time()
            idle_streak += 1
        else:
            idle_streak = 0
        idle_ok = idle_confirmed(idle_streak, idle_t0, time.time())
        if st in ('dialog', 'reward', 'battle'):
            marker_fail = 0
        if st in ('reward', 'battle', 'walking'):
            stall_rounds, stall_marker = 0, None
            select_loops = 0
        if st == 'walking' and boss_stop:
            last_action = 0.0            # 預設模式：對話後又開始 Auto Walking = 之後的遇敵是路上小怪，不算 BOSS 戰
        if st != 'dialog' and stall_prev == 'dialog':
            stall_leave_t = time.time()
        if st == 'dialog' and stall_prev != 'dialog':
            # 從非對話進入對話：中間隔了閒置（>= IDLE_CONFIRM_SECS）或點過黃問號才算新的一輪（多頁對話頁與頁之間偶爾閃過一格不算）
            if stall_marker_new or time.time() - stall_leave_t >= IDLE_CONFIRM_SECS:
                stall_rounds += 1
            stall_marker_new = False
            cur_dlg = read_pos()
            if cur_dlg:
                if stall_map and cur_dlg[0] != stall_map:
                    stall_rounds, stall_marker = 0, None
                stall_map = cur_dlg[0]
            if stalled(stall_rounds, stall_marker is not None):
                shot = snap('no-progress')
                event(f'對話無進展：同一黃問號 {stall_marker} 已「點 → 對話」{stall_rounds} 輪，沒領獎 / 沒戰鬥 / 沒巡路 / 沒換圖 → 不按對話框，退出碼 {EXIT_NO_PROGRESS}（人工看對話內容 / 任務條件）', shot)
                print('對話無進展，已停手', flush=True)
                return EXIT_NO_PROGRESS
        stall_prev = st
        stuck_now = False
        if wstuck.due(st, time.time()):
            wp = walk.pos()                                    # 座標讀不到（地圖名兩行時 HUD 座標 OCR 失敗）→ 改比世界畫面取樣
            stuck_now = wstuck.feed(wp, time.time()) if wp else wstuck.feed_sig(read_world_sig(), time.time())
        if stuck_now:
            # 自動巡路卡住（2026-10-12 吉魯島 121,170：傳送落點緊鄰出口 122,170，Auto Walking 站著不動 40 分鐘，點一下地面才解開）
            wstuck.tries += 1
            secs = wstuck.stuck_for(time.time())
            shot = snap('walk-stuck')
            if wstuck.tries > WALK_UNSTICK_MAX:
                event(f'自動巡路又卡住（座標 {wstuck.pos} {secs:.0f} 秒沒變，已自動解卡 {WALK_UNSTICK_MAX} 次）→ 停手，退出碼 {EXIT_WALK_STUCK}', shot)
                _errlog(f'quest 自動巡路卡住 {wstuck.pos} 解卡 {WALK_UNSTICK_MAX} 次仍卡，退出碼 {EXIT_WALK_STUCK}')
                return EXIT_WALK_STUCK
            if unstick_refresh_due(wstuck.tries):
                event('自動巡路卡住：先按「刷新角色」再解卡')
                try:
                    refresh_characters(False)
                except Exception as e:                    # 刷新失敗不擋後面的點地面 / 重點追蹤
                    event(f'卡住時刷新角色失敗：{e}')
            xy = walk.unstick_click(*wstuck.pos) if isinstance(wstuck.pos, tuple) else None   # 畫面判斷的（沒有座標）→ 不點地面，直接重點追蹤
            if xy is None and a.task and not a.no_track:
                track_task(a.task)                         # 沒有通行格資料 / 附近沒有安全格：不點地面，直接重點追蹤卡片
            event(f'自動巡路卡住：Auto Walking 但座標 {wstuck.pos} {secs:.0f} 秒沒變 → '
                  + (f'點地面 {xy}（第 {wstuck.tries} 次），停下後重點追蹤' if xy else f'找不到安全地面，直接重點追蹤（第 {wstuck.tries} 次）'), shot)
            _errlog(f'quest 自動巡路卡住 {wstuck.pos} {secs:.0f} 秒 → ' + (f'點地面 {xy}' if xy else '重點追蹤'), fixed='quest.WalkStuck 自動解卡')
            wstuck.reset()
            post_track, tracked = True, False
            time.sleep(a.every)
            continue
        if st in ('walking', 'dialog', 'reward', 'battle'):
            if tracked:
                tracked, track_fail = False, 0
        if not pre_checked and st in ('idle', 'dialog'):
            # 啟動後第一次點 / 按之前一定先驗隊伍（2026-10-10 18:44 事件：--solo 後單人，--stop-after-rewards 啟動直接按對話框 → 只有 DKB0 交任務）
            if st == 'dialog':
                # 對話框開著蓋住切換面板鈕：先 ESC 關掉（不回答任何選項，同 --solo），回主迴圈等 idle 再驗；ESC 3 次還開著 → 無法驗證，不按
                if dialog_esc >= 3:
                    event(f'啟動時對話框開著，ESC {dialog_esc} 次仍關不掉 → 無法先驗隊伍，不按對話框，退出碼 {EXIT_TEAM_MISMATCH}', snap('team-mismatch'))
                    return EXIT_TEAM_MISMATCH
                dialog_esc += 1
                gui('key', '{ESC}', note='啟動時對話框已開：先 ESC 關閉（不回答），驗過隊伍才處理')
                time.sleep(a.every)
                continue
            if (rc := team_gate('開始前：', EXIT_TEAM_MISMATCH, force=True)):
                return rc
            pre_checked = True
        if st == 'dialog' and a.solo:
            shot = snap('npc-dialog')
            gui('key', '{ESC}', note='到達 NPC：ESC 關閉對話框（不回答任何選項）')
            event(f'--solo 到達 NPC：對話框已 ESC 關閉，停下交給組隊（退出碼 {EXIT_AT_NPC}）', shot)
            print('到達 NPC（對話框已 ESC 關閉）', flush=True)
            return EXIT_AT_NPC
        if st == 'dialog' and not a.allow_irreversible:
            # 不可逆防護（errlog #68）：內文 / 按鈕含「轉生」等關鍵字、或讀不到內文 → 不按，對話框留著，交給人 / agent 看圖
            g = check_dialog_irreversible()
            if g['blocked']:
                shot = snap('irreversible')
                event(f'不可逆對話防護：{g["reason"]}；內文 {g["body"]}、按鈕 {g["buttons"]} → 沒按任何鈕，對話框維持開著，退出碼 {EXIT_IRREVERSIBLE}（確認要做再加 --allow-irreversible）', shot)
                print('對話框含不可逆選項（轉生 / 封印 / 刪除 / 丟棄…）或讀不到文字，已停手、沒按', flush=True)
                return EXIT_IRREVERSIBLE
        if st == 'dialog':
            dialogs += 1
            shot = snap('dialog')
            gui('seq', f'click {DIALOG_NEXT[0]} {DIALOG_NEXT[1]}')
            last_action = time.time()
            post_track = True
            event(f'對話框 #{dialogs}：按左鈕 {DIALOG_NEXT}', shot)
        elif st == 'reward':
            rewards += 1
            shot = snap('reward')
            gone, n_click = close_reward()
            post_track = True
            if not gone:
                event(f'獲得物品視窗 #{rewards}：按確認 {n_click} 次（每次等 {REWARD_GONE_S}s）視窗仍在 → 停手，退出碼 {EXIT_REWARD_STUCK}（請 shot 看是不是別的視窗）', snap('reward-stuck'))
                return EXIT_REWARD_STUCK
            event(f'獲得物品視窗 #{rewards}：按確認' + (f'（按了 {n_click} 次才關）' if n_click > 1 else '') + '，已確認視窗關閉', shot)
            if a.stop_after_rewards and rewards >= a.stop_after_rewards:
                ok_, extra = settle_reward()                   # 停手前確認領獎窗真的沒了（紅暴步 8 按完又在 / 第 2 個領獎窗）→ 留著會擋下一步
                if not ok_:
                    event(f'獲得物品視窗 #{rewards}：停手前又看到領獎窗、按確認仍關不掉 → 退出碼 {EXIT_REWARD_STUCK}', snap('reward-stuck'))
                    return EXIT_REWARD_STUCK
                event(f'已領 {rewards} 次獎勵視窗，停止（--stop-after-rewards）' + (f'；停手前又關了 {extra} 個領獎窗' if extra else ''))
                return finish(a)
        elif st == 'battle':
            # 手動逃跑模式（--solo / --fight）：路上小怪只逃、不刷新；任務 / BOSS 戰（--fight 且點 NPC / 對話後 QUEST_BATTLE_WINDOW 內開始）開自動戰鬥 + 刷新角色。
            # 組隊預設模式：每一場戰鬥都刷新（完整戰鬥先確保自動戰鬥開）
            manual = a.solo or a.fight
            boss_now = a.fight and boss
            full = bool(s.get('full'))
            act = None
            if in_battle_new:
                auto_presses = 0
                last_refresh_t = 0.0
                refresh_tries = 0
                row_clicks = 0
            if not full and time.time() - battle_t0 >= VS_STUCK_S:
                # 快速戰鬥（頭上 VS 牌）這麼久還沒打完 = 伺服器端卡死（刷新角色也沒用；2026-10-12 碧青 12 樓手動全員重登才解）→ 交給呼叫端重登
                shot = snap('vs-stuck')
                event(f'快速戰鬥 VS 牌 {time.time() - battle_t0:.0f} 秒還沒結束（刷新角色無效、沒有完整戰鬥畫面）→ 結束本片，退出碼 {EXIT_VS_STUCK}（呼叫端全員重登）', shot)
                _errlog(f'quest 快速戰鬥 VS 牌卡死 {time.time() - battle_t0:.0f} 秒，退出碼 {EXIT_VS_STUCK}')
                return EXIT_VS_STUCK
            if manual and not full:
                if not boss_now and not warned_quick:
                    event(f'--{"solo" if a.solo else "fight"}：遇敵但沒有完整戰鬥畫面（只看到 VS 牌 = 快速戰鬥還開著？）→ 無法逃跑，只能等；請先關快速戰鬥')
                    warned_quick = True
            elif manual:
                act = plan_battle_action(s, boss_now, time.time() - last_click_t)
                if act:
                    xy = {'escape': ESCAPE_BTN, 'auto_off': AUTO_BTN, 'auto_on': AUTO_BTN}[act]
                    gui('seq', f'click {xy[0]} {xy[1]}', note={'escape': '完整戰鬥小怪 → 逃跑', 'auto_off': '小怪戰 → 先關自動戰鬥', 'auto_on': 'BOSS 戰 → 開自動戰鬥'}[act])
                    last_click_t = time.time()
                    battles += 1
                    event({'escape': f'{"--solo" if a.solo else "--fight 小怪"} 戰鬥中：按逃跑（第 {battles} 次）',
                           'auto_off': '--solo / 小怪戰：自動戰鬥是開的 → 先按一下關掉，下一回合再逃',
                           'auto_on': f'--fight 任務 / BOSS 戰：自動戰鬥鈕是關的 → 按一下（第 {battles} 次）'}[act])
                elif boss_now and time.time() - last_full_log > 20:
                    event('--fight 任務 / BOSS 戰中（自動戰鬥已開，等打完）')
                    last_full_log = time.time()
            elif full:
                # 組隊預設模式的完整戰鬥：自動戰鬥是關的 → 按 1380,600 讓全隊自動打完（不逃跑：組隊逃跑行為未驗證）
                act = plan_battle_action(s, False, time.time() - last_click_t, party=True)
                if act:
                    if auto_presses >= AUTO_STUCK_MAX:
                        shot = snap('battle-stuck')
                        event(f'組隊完整戰鬥：自動戰鬥鈕按了 {auto_presses} 次仍是關的（寵物指令視窗 / 其他卡住畫面？）→ 停，退出碼 {EXIT_BATTLE_STUCK}（人工：戰寵視窗先選攻擊再按選擇）', shot)
                        return EXIT_BATTLE_STUCK
                    gui('seq', f'click {AUTO_BTN[0]} {AUTO_BTN[1]}', note='組隊完整戰鬥 → 開自動戰鬥')
                    last_click_t = time.time()
                    auto_presses += 1
                    event(f'組隊完整戰鬥：自動戰鬥鈕是關的 → 按 {AUTO_BTN}（本場第 {auto_presses} 次）')
            if should_refresh(a, boss_now, full, s.get('auto_off'), time.time() - last_refresh_t, time.time() - battle_t0):
                rr = refresh_characters(full, refresh_tries, click_row=row_clicks < CLOSE_ROW_MAX_CLICKS)
                if rr == 'row':
                    row_clicks += 1
                    if row_clicks == CLOSE_ROW_MAX_CLICKS:
                        event(f'戰鬥底部「關閉 + 頭像」列點了 {row_clicks} 次收不掉 → 不再點，等它自己消失再刷新')
                kind = "完整" if full else "快速"
                if rr in REFRESH_DONE:
                    battles += 1
                    last_refresh_t = time.time()
                    event(f'戰鬥中（{kind}戰鬥）：按刷新角色（第 {battles} 次，開戰 {last_refresh_t - battle_t0:.1f} 秒' + (f'，前面 {refresh_tries} 次沒成功' if refresh_tries else '') + '）'
                          + ('' if rr == 'ok' else '（沒有 waitpix 結果，未驗證）'))
                    refresh_tries = 0
                else:
                    refresh_tries += 1
                    last_refresh_t = time.time() - REFRESH_GAP + REFRESH_RETRY     # 沒成功：REFRESH_RETRY 秒後重試，不等 REFRESH_GAP
                    why = {'row': '底部「關閉 + 頭像」列還在', 'row_wait': '底部「關閉 + 頭像」列還在（已點過收不掉，只等不點）',
                           'notready': '切換鈕沒露出（轉場 / 被蓋 / 戰鬥剛結束）→ 沒點',
                           'nopanel': '按了切換但面板沒出現 → 沒點刷新'}.get(rr, rr)
                    (event if rr == 'nopanel' or refresh_tries == 1 else log)(f'戰鬥中（{kind}戰鬥）刷新角色沒成功：{why}（本場第 {refresh_tries} 次，{REFRESH_RETRY:.0f} 秒後重試）')
                    if refresh_tries == REFRESH_STUCK_SNAP:
                        try:
                            shot = snap('close-row-stuck' if rr in ('row', 'row_wait') else 'refresh-fail')
                        except Exception:
                            shot = None
                        event(f'本場刷新角色連續 {refresh_tries} 次沒成功（最後一次：{why}）', shot)
                        _errlog(f'quest 戰鬥刷新角色連續 {refresh_tries} 次沒成功：{why}')
            elif not act and full and time.time() - last_full_log > 20:
                event('完整戰鬥畫面（自動戰鬥已開，等打完）')
                last_full_log = time.time()
            if should_refresh(a, boss_now, full, s.get('auto_off'), 1e9, 1e9):
                # 這場要刷新：下一次到期（開戰延遲 / 失敗重試 / REFRESH_GAP）比輪詢間隔早 → 只睡到到期（最少 0.2 秒），不多等一整輪
                due = max(last_refresh_t + REFRESH_GAP, battle_t0 + (REFRESH_FIRST_DELAY if full else 0.0))
                nap = min(a.every, max(0.2, due - time.time()))
        elif st == 'panel':
            gui('key', '{ESC}')
            event('切換角色面板殘留，ESC 關閉')
        elif st == 'idle' and guard_ko and (ko_pending or time.time() - last_pos_t >= 12) and not (ko_pending and not idle_ok):
            # 打完一場後（或每 12 秒）查位置：被打飛回村 → 退出碼 21。剛打完的第一次閒置先略過一輪（畫面轉場中 OCR 讀不準）
            ko_pending = False
            cur = read_pos()
            last_pos_t = time.time()
            if is_knocked(last_pos, cur):
                shot = snap('KNOCKED')
                event(f'偵測到被打飛：{last_pos} → {cur}（薩姆吉爾儲存點附近）→ 停下（退出碼 {EXIT_KNOCKED}）', shot)
                print(f'被打飛回村：{cur}', flush=True)
                return EXIT_KNOCKED
            if cur:
                last_pos = cur
        elif st == 'idle' and a.fight:
            now = time.time()
            if boss_seen:
                if idle_ok:
                    event(f'--fight BOSS 戰結束（對話 {dialogs}、獎勵 {rewards}），連續閒置 {idle_streak} 次 → 結束，不巡路')
                    print('BOSS 戰結束', flush=True)
                    return verify_boss_result(a, boss_pre, team_size, team_on)
            elif npc_click_t and not dialogs and now - npc_click_t >= NPC_WAIT:
                shot = snap('no-npc')
                event(f'--fight 點 NPC 後 {NPC_WAIT:.0f} 秒內沒對話框也沒戰鬥 → 沒點到 NPC（或被小怪打斷）→ 不亂走，退出碼 {EXIT_NO_NPC}', shot)
                print('沒點到 NPC', flush=True)
                return EXIT_NO_NPC
            elif dialogs and now - last_action >= QUEST_BATTLE_WINDOW:
                shot = snap('no-battle')
                event(f'--fight 對話後 {QUEST_BATTLE_WINDOW:.0f} 秒沒開打（這步可能不戰鬥）→ 退出碼 {EXIT_NO_BATTLE}', shot)
                print('對話後沒開打', flush=True)
                return EXIT_NO_BATTLE
        elif st == 'idle' and boss_stop and boss_seen:
            # 預設模式：任務 BOSS 戰打完。閒置確認前不點追蹤 / 黃問號（否則會直接接下一步，errlog #68）；確認後先驗隊伍再停
            if idle_ok:
                if team_on:
                    ok_, desc = check_team(team_size, 'BOSS 戰後：')
                    last_team_check = time.time()
                else:
                    ok_, desc = True, f'未檢查隊伍（--team-size {team_size}）'
                shot = snap('boss-done')
                if ok_:
                    event(f'預設模式 BOSS 戰結束（對話 {dialogs}、獎勵 {rewards}、戰鬥 {battles}）：隊伍檢查 {desc} → 停手，退出碼 {EXIT_BOSS_DONE}（呼叫端確認戰果再下一步；--no-stop-after-boss 可連跑）', shot)
                    print(f'BOSS 戰結束，隊伍滿員（退出碼 {EXIT_BOSS_DONE}）', flush=True)
                    return EXIT_BOSS_DONE
                event(f'預設模式 BOSS 戰結束（對話 {dialogs}、獎勵 {rewards}、戰鬥 {battles}）：隊伍{"不滿" if ok_ is False else "檢查失敗"}：{desc} → 停手，退出碼 {EXIT_BOSS_TEAM}（呼叫端重打流程：char.py switch 被打飛者 → 追蹤傳送 → 重打 → 切回 → team.form）', shot)
                print(f'BOSS 戰結束但隊伍不滿：{desc}（退出碼 {EXIT_BOSS_TEAM}）', flush=True)
                return EXIT_BOSS_TEAM
        elif a.stop_after_dialog and (dialogs or rewards) and st in ('idle', 'walking'):
            # 這一步已經對話 / 領獎過：從這裡起絕不點追蹤、不點 NPC 頭上黃「?」（否則會把下一步也對完、接著巡路 = 2026-10-10 深紅事故）。
            # 只等閒置 2 次就停；遊戲自己又進入 Auto Walking → 退出碼 24（呼叫端立刻處理，例如 --disband-after 已先解散）
            if st == 'walking':
                event(f'--stop-after-dialog：步驟完成後遊戲自己開始 Auto Walking（對話 {dialogs}、獎勵 {rewards}）→ 不點任何追蹤，退出碼 {EXIT_AUTOWALK}')
                return finish(a, EXIT_AUTOWALK)
            if idle_ok:
                event(f'步驟結束（對話 {dialogs}、獎勵 {rewards}），連續閒置 {idle_streak} 次 → 停（--stop-after-dialog，未點追蹤 / 黃問號）')
                return finish(a)
        elif st == 'idle' and hp_check_due(a, quest_since_hp, road_since_hp, idle_ok):
            # 片內連戰 HP 檢查（2026-10-13 四寶玉之謎：同一片連打守護獸、片內沒驗 HP，DKBO3 / DKBO5 HP 0 被踢出隊伍）
            quest_since_hp = road_since_hp = 0
            rc_hp, pct = read_team_hp()
            if rc_hp in (EXIT_UNKNOWN, EXIT_HALT_CODE):
                return rc_hp
            low = hp_low_roles(pct, a.hp_check_min) if not rc_hp else {}
            if rc_hp or not pct:
                event(f'戰鬥後讀全隊 HP 失敗（bag rc={rc_hp}）→ 這次不判斷，繼續')
            elif low:
                shot = snap('hp-low')
                event(f'戰鬥後全隊 HP {pct}：{low} 低於 {a.hp_check_min}% → 結束本片，退出碼 {EXIT_HP_LOW}（呼叫端補血後續片）', shot)
                print(f'全隊 HP 偏低：{low}', flush=True)
                return EXIT_HP_LOW
            else:
                log(f'戰鬥後全隊 HP {pct}（門檻 {a.hp_check_min}%）OK')
        elif st == 'idle':
            # 做完事（對話 / 領獎）後連續 2 次閒置 = 這一步結束，馬上結束不空等（有領過獎勵，或 --no-track 時對話過）
            if idle_ok and not (rewards and not a.no_track and a.task and not tracked and checked_rewards < rewards) and (rewards or (a.no_track and dialogs) or (a.stop_after_dialog and dialogs)):
                event(f'步驟結束（對話 {dialogs}、獎勵 {rewards}、戰鬥 {battles}），連續閒置 {idle_streak} 次，提前結束')
                return finish(a)
            wait_track = tracked and time.time() - track_t < TRACK_RETRY_SECS     # 剛點過追蹤：給遊戲時間開始巡路，不重點、不計失敗
            if tracked and not wait_track:
                track_fail += 1
                if track_fail >= 2 and post_track_clicked and not a.no_marker:
                    event('對話後先點追蹤、約 5 秒沒反應 → 改找黃色問號（不直接退出碼 3）')
                    tracked, track_fail, post_track_clicked = False, 0, False
                elif track_fail >= 2:
                    shot = snap('no-autowalk')
                    event('點了任務追蹤兩次都沒進入巡路 / 對話 / 戰鬥 → 這個任務步驟不能自動巡路或已完成，請改手動（walk.py + 點 NPC）', shot)
                    return 3
            if wait_track:
                pass
            elif rewards > checked_rewards and not a.no_track and a.task:
                # 領過獎勵後第一次回到主畫面：立刻掃整個追蹤列表。目標任務不在列表 = 任務完成（不空轉）；還在 = 下一步，順便點它
                checked_rewards = rewards
                post_track = False
                time.sleep(1.0)                              # 等獲得物品視窗收掉、列表刷新
                res = track_task(a.task, click=False)        # 先只掃不點：任務已不在列表（= 完成）就不必驗隊伍（2026-10-11：最後一步領完獎被隊伍檢查擋下，白跑一輪）
                if res:
                    if (rc := team_gate('領獎後點追蹤前：', EXIT_TEAM_LOST, force=True)):      # 還有下一步 / 要去交任務：驗一次
                        return rc
                    res = track_task(a.task)
                if res is None:
                    checked_rewards = rewards - 1            # 被打斷，下次回主畫面再查
                elif res:
                    tracked, track_t = True, time.time()
                    post_track_clicked = True
                    task_miss = 0
                else:
                    shot = snap('task-done')
                    event(f'領過 {rewards} 次獎勵後追蹤列表整個掃完沒有「{a.task}」→ 任務完成（對話 {dialogs}、獎勵 {rewards}、戰鬥 {battles}）', shot)
                    print(f'任務完成：{a.task}', flush=True)
                    return 0
            elif not a.no_track and a.task and (pt := post_track_try()) is not None:
                # 對話框收起 / 領獎後回到主畫面：第一個動作一律先點追蹤欄該任務卡片（post_track_try；標題相符才點，讓遊戲自動巡路到下一步）；
                # 卡片不在才往下找黃色問號；追蹤沒反應則由上面的 track_fail 改找黃問號
                if pt:
                    return pt
            elif not a.no_track:
                # 檢測方針：1. 場景有黃色問號 → 優先點它；2. 沒有 → 追蹤列表核對任務名再點
                if not wait_track and (rc := team_gate('點追蹤 / 黃問號前：', EXIT_TEAM_LOST)):
                    return rc
                mk = None if a.no_marker else find_marker()
                log('找黃色問號：' + (f'{mk["x"]},{mk["y"]} n={mk["n"]}' if mk else '沒有'))
                if mk and marker_fail < len(MARK_NPC_DYS):
                    dy = MARK_NPC_DYS[marker_fail]
                    tx, ty = mk['x'], mk['y'] + dy
                    if stall_marker is not None and max(abs(mk['x'] - stall_marker[0]), abs(mk['y'] - stall_marker[1])) > STALL_MARKER_PX:
                        stall_rounds = 0                     # 換了一個黃問號 → 重新累計
                    stall_marker, stall_marker_new = (mk['x'], mk['y']), True
                    gui('seq', f'{PRIMER}; click {tx} {ty}', note=f'點 NPC 頭上黃色標記下方（標記 {mk["x"]},{mk["y"]} n={mk["n"]}）')
                    last_action = time.time()
                    event(f'閒置：場景有黃色標記 {mk["x"]},{mk["y"]}（{mk["w"]}x{mk["h"]} n={mk["n"]}）→ 點 {tx},{ty}')
                    # 點 NPC = 隊伍自己走過去再開對話框，途中不會出現 Auto Walking 字樣 → 等最多 8 秒看有沒有對話 / 戰鬥 / 領獎 / 巡路
                    reacted = False
                    for _ in range(8):
                        time.sleep(1.0)
                        if read_screen()['state'] != 'idle':
                            reacted = True
                            break
                    marker_fail = 0 if reacted else marker_fail + 1       # 連續沒反應 2 次 → 這個問號點不到，改走追蹤列表
                    tracked = False
                elif (res := track_task(a.task)) is None:
                    log('找追蹤時畫面變了（對話 / 戰鬥 / 領獎），交回主迴圈')
                elif res:
                    tracked, track_t = True, time.time()
                    task_miss = 0
                else:
                    if rewards or LAST_SCAN_NO_SCROLL:   # 領過獎勵又找不到 = 完成；追蹤欄只有別的任務、沒有捲動空間 = 一輪就判完成（2026-10-11 龍的巢穴：捲兩輪浪費 1 分多）
                        shot = snap('task-done')
                        event(f'追蹤列表整個掃完沒有「{a.task}」，' + ('且已領過獎勵' if rewards else '追蹤欄無捲動空間') + ' → 任務完成', shot)
                        print(f'任務完成：{a.task}', flush=True)
                        return 0
                    task_miss += 1
                    if task_miss < 2:        # 可能剛好剛換圖 / 捲動慣性 / 標記剛出現：下一輪再來一次（會先重找黃色問號）
                        log(f'追蹤列表找不到「{a.task}」（第 {task_miss} 次），下一輪重試')
                    else:
                        shot = snap('task-not-found')
                        event(f'追蹤列表掃完（到頂 + 到底）都找不到「{a.task}」（連續 {task_miss} 次，沒領過獎勵）→ 沒點任何東西，退出', shot)
                        return 5
        elif st == 'bye':
            byes += 1
            shot = snap('bye')
            gui('key', '{ESC}', note='只有「再見」的對話框：ESC 關閉（不回答）')
            from_select = bool(last_select_t) and time.time() - last_select_t <= BYE_SELECT_WINDOW
            if from_select and byes < BYE_MAX:
                event(f'選擇對象面板點到只有「再見」的閒聊（OCR 確認）→ ESC 關閉、回原流程（第 {byes} 次；不是驗證視窗）', shot)
            else:
                time.sleep(0.8)
                if read_screen()['state'] == 'bye':            # ESC 沒吃到：再送一次（只 ESC，不點任何鈕）
                    gui('key', '{ESC}', note='只有「再見」的對話框還在：再 ESC 一次')
                why = (f'選擇對象 → 閒聊已自動關 {byes} 次仍出現' if from_select else
                       '任務 NPC 只回「再見」（任務條件不符：例如任務道具進了信箱 / 背包滿、寵物沒湊齊）')
                event(f'只有「再見」一顆鈕的對話框（OCR 確認，不是驗證視窗）：{why} → 已 ESC 關閉，任務接不下去，退出碼 {EXIT_BYE_ONLY}', shot)
                print('任務 NPC 只有「再見」，任務接不下去（已 ESC）', flush=True)
                return EXIT_BYE_ONLY
        elif st == 'unknown' and (tk := transition_screen()) and (tk == 'loading' or not trans_t0 or transition_wait(trans_t0, time.time())):
            # 2026-10-12 新插畫「加載中」、10-14 英文版 Loading 雙進度條（綠條還短時舊特徵不中）誤判 unknown 連 3 次 → 退出碼 2。
            # 載入圖（正面特徵）等超過上限 → 43（呼叫端重跑）；全黑只是「沒特徵」，等超過上限就落回下面的不認得規則（照舊 3 次 → 2，鐵則 5 從嚴）
            now = time.time()
            if not trans_t0:
                trans_t0 = now
                log(f'{"載入畫面" if tk == "loading" else "全黑轉場"}（換圖轉場）→ 等待，不點、不計入不認得畫面（上限 {LOADING_MAX_S:.0f} 秒）')
            elif not transition_wait(trans_t0, now):
                shot = snap('loading-stuck')
                event(f'載入畫面連續 {now - trans_t0:.0f} 秒沒結束 → 當卡住，沒點任何東西，退出碼 {EXIT_LOADING_STUCK}（呼叫端重跑；斷線由 netwatch 處理）', shot)
                _errlog(f'quest.py 載入畫面卡 {now - trans_t0:.0f} 秒 → 退出碼 {EXIT_LOADING_STUCK}')
                return EXIT_LOADING_STUCK
            unknown = 0
            time.sleep(1.0)
            continue
        elif st == 'unknown' or st == 'error':          # trans_t0 不在這裡清：全黑超時落到這裡後，下一輪不可再重新等 60 秒
            if unknown == 0:
                unknown_t0 = time.time()
                if st == 'unknown':
                    snap('unknown1')                     # 這一串不認得的第一張（10-14 08:12 只有第 3 次的圖，看不到前面是什麼畫面）
            unknown += 1
            log(f'不認得的畫面 {unknown}/3 {s}')
            if unknown >= 2 and close_stray_panel():       # 戰鬥剛結束時「刷新角色」的 850,765 會點到主畫面的「組隊」鈕（2026-10-11 小豬愛情故事）→ 已知面板直接關，不算驗證視窗
                unknown = 0
                continue
            if unknown >= 3 and time.time() - unknown_t0 >= UNKNOWN_CONFIRM_SECS:
                shot = snap('UNKNOWN')
                event('警告：連續 3 次遇到不認得的畫面（可能是答題 / 防腳本驗證視窗）→ 停止自動操作，請使用者處理', shot)
                print('!!! 請人工檢查畫面（鐵則 5：驗證視窗不可亂猜答案）', flush=True)
                return 2
        if a.once:
            return 0
        if wclock.expired(time.time()) and not slice_defer(st, time.time() - wclock.end, boss_stop and boss_seen):   # 戰鬥 / 對話 / 領獎中、BOSS 戰後等閒置確認中不收片（60 秒切片會切到 BOSS 戰中間，丟掉 BOSS 判斷）
            event(f'時間到，結束（對話 {dialogs}、獎勵 {rewards}、戰鬥 {battles}；巡路中不計時 {wclock.walked:.0f} 秒）')
            return 0
        time.sleep(nap)


def main() -> int:
    """包一層：不論怎麼結束（含例外 / Ctrl-C）都刪自己的戰鬥鎖檔"""
    winenv.enable_server()   # 長程序：用常駐 server 讀畫面（WSL 預設開、Windows 原生需 PSA_GUI_SERVER=1、=0 關閉）
    try:
        rc = _main()
        wc = WALK.get('clock')
        if wc is not None:
            print(f'走路不計時 {int(wc.walked)} 秒', flush=True)      # questrun 解析這行：slice / 總時限都不把巡路時間算進去
            print(f'本片戰鬥 {STATS.get("battles", 0)} 場', flush=True)  # questrun 解析這行：沒打仗 → 全隊 HP 讀數可沿用（review §5.2）
        return rc
    finally:
        battleguard.release()
        winenv.shutdown_server()   # 明確關常駐 server（送 quit + 關 stdin），不只靠 atexit


if __name__ == '__main__':
    sys.exit(main())
