---
name: psa-grind-start
description: Use when the PrimalSA (精靈王石器) party must start or resume 掛機練功 — the user asks to 開始練功 / 去練功 / 掛機練級, or after 補血回來 / 做完任務 / 斷線重登 when 原地遇敵、快速戰鬥、自動戰鬥 may be off.
---

# 開始練功（選點 → 傳送 → 遇敵 → 5 人戰鬥設定）

**REQUIRED BACKGROUND:** 先載入 psa-game-ui（工具、紅區、驗證視窗立刻停手、不花鑽石）。座標是截圖座標（客戶區 2880×1659）。`G="bash tools/gui/gui.sh"`，在專案根目錄執行。
外掛勾選 / 傳送屬紅區：**使用者要求練功 / 掛機就等於授權**；否則先問。外掛面板細節 `../psa-game-ui/ui/ass.md`，傳送 `ui/transfer.md`。


## 0. 先跑腳本（推薦；下面 1～6 是手動退路）
```bash
uv run --no-project python tools/gui/grind.py start                    # 「去練功」：依當下等級選點 → 傳送 → 外掛 → 遇敵 → 確認；未滿地雷區背景起 follow
uv run --no-project python tools/gui/grind.py start --spot 波拉島        # 固定點（使用者指定才用；不起 follow，有 follow 在跑先停）
uv run --no-project python tools/gui/grind.py ensure                     # 不傳送：補血回來 / 任務後 / 斷線重登後，重查並補好（約 25 s）
uv run --no-project python tools/gui/grind.py check                      # 唯讀：5 人快速 / 自動戰鬥 + 遇敵鈕（約 9 s）
```
- **去練功（使用者 2026-10-15）= `grind.py start` 不給 --spot（= `--spot auto`；import：`grind.go()`）**：依當下**隊伍最低等級**選點（`spots.auto_spot` = AUTO 表 + `spots.learn` 學到的門檻；使用者 2026-10-16：p3 隊長 0 轉 46 級、隊友不到 45，選五兄弟洞窟被擋 rc 51）。
  隊伍最低 = 同一趟背包讀等級字順便讀 5 人（`grind.read_team_bag` = `bag.levels(uikit.CHARS)`，開一次背包逐人點頭像，約 8 秒；比只讀隊長多 4 次頭像點擊，不另開面板），`spots.team_min` 先比轉數再比等級；
  選點用的有效等級 = 隊長 / 隊伍最低 / 被擋上限（`spots.effective`）取小，JSON 多 `team_min / eff / cap`。讀不到隊伍（背包失敗 / 用 --trans / 快取）= 只看隊長（舊行為）。
  **保險（傳送被擋退點）**：傳送失敗（rc 51）後讀聊天區「XXX 未達到 N轉M級禁止傳送」（`follow.read_block_msg`，要求 ≤ 隊長 = 是隊友擋）→ `spots.set_cap`（`<狀態資料夾>/team-cap.json`，每視窗一份、30 分鐘失效、只往低改）
  記下上限 (N轉 M-1 級) → 自動退到下一個門檻較低的點重試（最多 3 次，JSON `retreat`）；聊天沒有未達訊息 / 要求比隊長還高（隊長自己不夠）→ 照舊 51。
  轉數不信 HUD（轉數位會讀錯）：`--trans N` 明講 > 背包讀隊長等級字（bag.levels，成功寫 `tools/.cache/trans.json`）> 呼叫端提示 > 快取 > HUD（警告）。
  選到最高一檔（**地雷區 ≥120**）→ 確認掛機就結束、**不起 follow**；未滿 120 → 確認掛機後背景常駐 `grind.py follow --no-heal --trans N`
  （`follow.ensure_running` → `winenv.spawn_detached`：WSL setsid、Windows DETACHED_PROCESS；已有同轉數的在跑不重開、轉數不同先停再起；輸出 `tools/.cache/follow.log`），
  follow 換到地雷區並確認掛機後自己結束（退出 0、quest-events.log 一行）。開始前有 follow 在跑會先停（它持 grind.lock）。`--no-follow` = 不起 follow。
  JSON 帶 `trans / trans_src / level_num / follow.action`（none / skip / running / started / fail；fail 只記 errlog，退出碼仍 0）。
  **任何腳本都不寫死 `--spot 地雷區`**（四轉後寫死導致在錯的點掛了 6 小時）：questrun --after grind、postrebirth 收尾、petquest 猜謎三兄弟、rebirth_pets 結束都改成去練功；
  例外：恐龍博士 / 卡坦練寵固定 `--spot 波拉島`（使用者指定 80 級練功區）。
- `--spot`：點名（`tools/gui/spots.py`，資料唯一來源是 `ui/transfer.md`）= 固定點、不起 follow；`here`（不傳送）。已在該點（或 auto 的同檔點，例 地雷區 / 地雷區2）不會傳送；0 轉等級不夠依表預判就擋（退出碼 51）。
- `--heal`：先回村補血（點需在 heal.SPOTS，柯奧龜洞 / 阿布龜洞 / 五兄弟洞窟暫不支援）；血量 < 40% 也會自動補。`--no-fix`：看到完整戰鬥時不自動重設 5 人。
- 成功 = 退出碼 0 且 30 秒內看到 ≥2 次 EXP 橫幅（只看到 1 次會自動再延長 30 秒，遇敵稀疏的點不再誤報 55；JSON from_map 換點前 / to_map 換點後地圖）。非 0：50 隊伍不全且組不起來 / 51 傳送失敗或等級不夠 / 52 外掛設定失敗 / 53 此地圖禁止快速戰鬥 / 54 遇敵開不起來 / 55 沒看到 EXP / 56 仍看到完整戰鬥 / 57 補血失敗 / 58 切不回隊長；8 別的工具在用畫面 / 9 疑似驗證視窗（**立刻停手通知使用者**）/ 10 netwatch halt。最後一行 JSON 看細節。
- **依等級自動換點（常駐）**：`grind.py follow [--trans 1] [--every 15] [--buffer 0] [--until-level N] [--dry-run]`、`follow --stop`。換點表（實測真門檻）：1 柯奧龜洞 / 10 阿布龜洞 / 20 海主人隧道 / 45 五兄弟洞窟 / 60 柯奧4F龜洞 / 80 波拉島 / 120 地雷區（1 轉未實測）。讀 state.hud.level 的「N級」（轉數位會讀錯，改用 `--trans`；轉生後重啟並改 `--trans`）、連 2 次一致才採用；到門檻（**隊長想換點時才讀一次 5 人等級取最低**：背包讀、成功快取 `follow.TEAM_TTL` 300 秒、失敗 60 秒後再試，不每輪開面板；隊友不夠就不換、夠了才換）就 `grind.run('start')`；被擋 → errlog + 記隊伍上限（`team-cap.json`，之後不再選到該點、follow 不結束；0 轉沒有 learn，靠這個擋住無限重試）+ 門檻修正存 `tools/.cache/spot-thresholds.json` + 留原點；血低回村補血；每 20 分鐘 `check` 並自動 ensure；有 battle.lock / 別的 grind 在動就暫停；watch 標 verify_suspect 時先現場讀畫面：主畫面算誤報；已知面板（寵物 / 背包 / 人物資訊…）= 暫停該輪；**畫面不認得 = 進入 unknown 暫停**（不點擊、不補血、不 ensure，只讀 state；第一次寫 errlog「畫面不認得，follow 暫停中，請人工確認」並附 watch 警報截圖路徑，之後不重複寫；不累計 BAD_MAX；畫面恢復成主畫面 / 已知面板就自動繼續並 log 一行），連續超過 `follow.UNKNOWN_STOP_MIN`（10 分鐘）才停（9）。狀態 `tools/.cache/follow.json`，事件寫 `notes/quest-events.log`。平常由「去練功」自動起（見上）；手動背景跑（WSL）：`nohup setsid uv run --no-project python tools/gui/grind.py follow --no-heal --trans N > tools/.cache/follow.log 2>&1 &`。換到 / 已在地雷區（≥120）並確認掛機 → 自己結束（0）。退出碼 59 = 連續讀不到等級。**follow 在跑時不要另外手動跑 grind start / heal**（會互相搶；要手動就先 `--stop`）。
- 只動快速戰鬥 / 自動戰鬥 / 主畫面遇敵鈕，先讀再改（已開不點）；不要和 `heal.py --watch`、`petwatch.py`、`quest.py` 同跑。
- **吃 2倍智慧果 / 龍王的守護一律跑 `uv run --no-project python tools/gui/depot_use.py DKBO 2倍智慧果`（龍王同理，換道具名）**：由它讀 buff 圖示決定吃不吃（已有就 skip、沒有才取出吃並驗圖示，沒驗到回 95）；**不要憑印象或 state.json / watch 的 buff 顯示判斷「已經有」而跳過**（2026-10-13 play agent 判斷 DKBO 有 buff 沒吃，實際已過期）。練寵掛機可加 `petwatch.py --exp-fruit` 讓它開練前自己跑。

## 1. 讀目前等級與位置（手動退路）
```bash
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "$(wslpath -w tools/gui/stat.ps1)"   # Windows 原生：直接給 Windows 路徑
```
看 `level`（例「0轉128級」）、`pos`（「60049:30,25」）。以**隊長 DKB0** 的等級為準（伺服器擋的是隊長）。已在合適練功點（地圖 ID 對得上下表）→ 跳過步驟 2～3，直接做 4。

## 2. 依等級選練功區（0 轉；1 轉以上門檻未實測）
座標與傳送點擊位置以 `ui/transfer.md`「練級傳送」表為唯一來源；`tools/gui/heal.py` 的 `SPOTS` 是其中幾個點的程式版。

| 隊長等級 | 練功點（練級傳送標籤） | 抵達地圖 | 狀態 |
|---|---|---|---|
| 1～19 | 柯奧龜洞（無門檻；阿布龜洞也可） | 11001 / 10001 | 實測 |
| 20～44 | 海主人隧道 | 31401:91,29 | 實測 |
| 45～59 | 五兄弟洞窟 | 31706:35,20 | 實測 |
| 60～79 | 柯奧4F龜洞 | 11004:7,8 | 實測（經驗比波拉島高） |
| 80～119 | 波拉島（柯奧4F 經驗更高；波拉島2 502 未試） | 500:212,344 | 實測（掉血很快，要補血） |
| 120+ | 地雷區（地雷區2 60050 未試） | 60049:30,25 | 實測（約波拉島 2.6 倍經驗、血量穩） |

- 門檻被擋：日誌「DKB0未達到0轉N級禁止傳送」，面板保持開著 → 改選低一級的點。
- 標籤 Lv 不是實際門檻，以上表為準。隊員等級會不會擋未實測。
- 想換更適合的點（例 1 轉後）：用 `uv run --no-project python tools/query/psa.py map <ID>` 看地圖，標「未實測」回報。

## 3. 傳送
- 要先**組成五人隊**（隊員跟著隊長過去）：未組隊 → `/psa-quick-team`。
- **戰鬥中傳送被擋**（「非正常狀態不能傳送」；快速戰鬥時角色頭上綠色 VS 牌）：先關遇敵（主畫面「取消遇敵」1365,660），等 VS 牌消失再傳。
- 指令：`$G seq "click 1215 18; wait 100; click 1340 65; wait 800; click 259 314; wait 600; click <目的地X> <目的地Y>; wait 2500; key {ESC}"`（點擊位置見 transfer.md 表）。**面板外的點擊會穿透到場景**，被擋後先 ESC 再重開。
- 抵達後 `stat.ps1` 確認 `pos` 的地圖 ID；沒變就再傳一次。換地圖後第一下左鍵會被吃掉（所以先點 1215,18 當引子）。

## 4. 開原地遇敵並確認（只在隊長）
1. 截圖看主畫面右下鈕：寫「**遇敵**」= 沒開；「**取消遇敵**」= 已開（別再點，會變關閉）。
2. 沒開 → 點 1365,660，日誌應出現「你已開啟原地遇敵」，鈕變「取消遇敵」。兩者都要截圖看到才算數。

## 5. 5 個角色逐一檢查（DKB0~DKB05 都要）
開外掛 1300,760（預設停在 DKB0 戰鬥設定頁，不用切頁）。頭像：DKB0 137,151 / DKB02 298,151 / DKB03 461,151 / DKB04 137,204 / DKB05 298,204。
- **確認真的切過去**：`$G pixel "<頭像座標>"`，選中 = 0,0,0、沒選中 = 197,227,255。
- **快速戰鬥 484,343**：255,255,255 = 沒勾 → 點 484,343 → 再讀 223,223,223 = 已勾。已勾別點（切換式，先讀再點）。
- **自動戰鬥 146,400**：30,30,30 = 已勾；其他值才 shot 確認，沒勾才點，點完再讀（訊息「你已開啟自動戰鬥」）。
- **原地遇敵框 146,343**（只看隊長）：151,151,151 = 已開；隊員 255,255,255 正常，遇敵只由隊長開，隊員不用開。
- 補血後（heal.py 不管 5 人設定）可一次 `pixel` 讀完五人，值不對的才處理，不必逐人截圖。
- 訊息「**當前地圖禁止使用快速戰鬥功能**」= 此地圖不能快速戰鬥（例：村長家 1006）→ 換練功點或回報使用者，不要硬掛。
- 面板被戰鬥打斷就等那場結束再開。**關面板點右上 X 1318,90**（外掛面板按 ESC 無效）。

## 6. 觀察確認
關面板後看 10～15 秒：**頭上綠 VS 牌 + 日誌「獲得 EXP」橫幅** = 快速戰鬥正常；出現完整戰鬥畫面（敵我排列）= 有人沒勾快速戰鬥 → 回 5 找出是誰。再跑一次 `stat.ps1` 確認 hpPct 沒狂掉（地雷區 128 級補血後約 1 分鐘 100→55，單次讀數跳動大，看趨勢；補血週期要短）；血量低用 `heal.py --spot <練功點>`（`--watch` 常駐）。最後 `$G end` 還前景。

## 一律要重做 4～6 的時機
補血回來（heal.py 會重開遇敵，但不管 5 人設定）、做完任務、傳送換點、**斷線重登**（5 人快速戰鬥全被重設，自動戰鬥保留；見 `ui/network.md`）。

## 失敗對照
| 現象 | 處理 |
|---|---|
| 「未達到…禁止傳送」 | 等級不夠，選低一級的點 |
| 點了「遇敵」沒反應 / 鈕仍寫遇敵 | 可能點到穿透或正在戰鬥；等戰鬥結束再點、截圖確認 |
| 出現答題 / 驗證視窗 | 依 psa-game-ui：立刻停手通知使用者 |
