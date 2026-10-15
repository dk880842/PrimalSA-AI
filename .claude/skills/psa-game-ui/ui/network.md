# 網路異常 / 斷線重連

## 實測流程（2026-10-10）
1. 遊戲中央跳出米色「提示」視窗：白字「網路異常，是否重連?」，只有一顆藍色「確定」**715,557**。
2. 點確定 → 不會自動重連，約 1.5 秒內回到登入畫面（帳號 / 密碼欄**由遊戲自動帶入**、橘色「登錄」590,585、藍色「註冊」、鑰匙圖示、「同意用戶協議」）。
3. **使用者授權（鐵則 2 的例外，只限這樣做）：AI 可以只點「登錄」，用遊戲自動帶入的帳密重新進遊戲。**
   - 只允許：點登錄、（登錄後）點「一鍵全登」。**絕不**輸入 / 修改 / 清除帳號密碼欄、不點鑰匙圖示與註冊、不讀 savepwd.txt / 登錄檔 PlayerPrefs、不把帳號名稱寫進 log / errlog / 文件 / 截圖檔名（log 只寫「按登錄」；截圖含帳號欄，不要存成會被分享的檔）。
   - 帳號或密碼欄是空的 → 不按，halt 通知使用者。
   - 登錄後出現提示視窗（密碼錯誤、帳號被封、維護中、需要驗證碼 / 答題驗證…）→ 不點、不重試，halt 通知使用者。
   - 連續登錄失敗 3 次（`netwatch.json` 的 `login_fails`）→ halt，退出碼 11。
4. 登錄後實際經過的畫面（約 15 秒）：
   1. **「選擇角色」面板**（5 張角色卡 DKB0 / 02 / 03 / 04 / 05、右上紅 X、下方「一鍵全登」橘鈕 **740,640**；卡片右側垃圾桶是刪除角色，**不要點**）→ 點一鍵全登。
   2. **載入畫面**：「完成登陸…」轉圈圈，約 10 秒；久了會出現「強制退出」鈕（不要點，繼續等）。
   3. 直接回到遊戲主畫面（沒有公告 / 活動彈窗）。
5. **登入後狀態全部保留**（伺服器端狀態）：5 人同隊（DKB0 隊長）、人還在斷線前的地圖（庫塔伊洞窟地下一樓 60049）、原地遇敵開著（「取消遇敵」鈕在）、戰鬥照常（快速戰鬥、戰寵迪基格斯）。登入後「當前」角色是 DKB05（之前是 DKB0，隊長不變）。
   若哪天隊伍散了：`netwatch.recover` 會先點切換面板「全部登錄」716,578，全員單人才呼叫 `team.form()` 快速組隊（P8；舊的盲點座標序列已刪）。

## 多視窗時不自動登錄（2026-10-15 使用者決定；離線測試 test_clientctx.py，未實機）
遊戲「記住的帳號」是所有視窗共用的（同一個 GameClient 資料夾），斷線的視窗按「登錄」可能登進別的帳號、把另一個視窗踢下線。所以 `netwatch.auto_login_check()`：
- **非主視窗**（`PSA_CLIENT` ≠ PrimalSA，例 PrimalSA2）：一律不按登錄。
- **主視窗**（沒設 PSA_CLIENT）：查目前在跑的遊戲程序（`clients.running()`，PowerShell 列 `PrimalSA\d*` 程序名，只讀）；**還有別的 PrimalSA* 在跑 → 不按登錄**。查不到程序清單 = 讀取失敗：本輪不點，連續 5 輪（`read_fails`）才 halt。
- 只有單一視窗時維持上面的自動登錄（行為不變）。
擋下時照樣偵測斷線、點「網路異常」提示的確定 715,557，回到登入畫面就 **halt**（errlog / halt 檔「多視窗不自動按登錄：…」，退出碼 10）→ 請人登入；人登入回來後 HUD 出現，下一次 netwatch 檢查會自己清 halt、做 recover（隊伍 / grind ensure，跟人類登入回來相同）。
`relogin.py`（主動全員重登，含 questrun / rebirth 卡住時的 `--stuck` 自動重登）多視窗時一開始就 **109**、什麼都不點（登出後回不來）。
各視窗的 halt / 狀態檔各自一份：主視窗 `tools/.cache/netwatch.*`，其他 `tools/.cache/clients/<程序名>/netwatch.*`。

## 全視窗驗證停手旗標（verifyhalt.py，2026-10-15）
任一視窗疑似驗證 / 答題視窗（`uikit.preflight` / `uikit.fail` 回 9、watch 的 unknown_long / quest 警報轉述、quest.py 連 3 次不認得、follow 不認得超過 10 分鐘）時，**多視窗情境**（同上判斷）會寫 `tools/.cache/verify-halt.json`（全部視窗共用一份）。
存在時：`netwatch.check_and_reconnect` 回 `verify`、`netwatch.guard` → `sys.exit(9)`（quest / follow / heal --watch / petwatch / grind 迴圈每輪都會呼叫）；`uikit.preflight` 一開始就 9；`VerifyGuard` 停止；`gui.ps1` 的 click / dclick / drag / key 不送、exit 9（最後一道保險）；watch 照常監看，`state.flags.verify_halt = true`。
旗標**不會自己消失**：人處理完驗證視窗後 `uv run --no-project python tools/gui/verifyhalt.py clear`（`status` 看內容，退出碼 9 = 有旗標）。單一視窗不寫旗標，行為與以前相同。

## 偵測特徵（2880×1659 截圖座標，容差 25）
- 提示視窗：`520,570` `880,570` `600,300` `600,557` `830,557` 米色（243,215,175 上下）+ `640,557` 藍（61,106,167）；兩側米色確保是「單鈕」提示。再用 ocr.ps1 讀訊息 `585,370,260,40`（`-Light 200`）：讀到文字卻不含 網/路/異/重/連 就當別種提示不點（OCR 讀不到則信任像素；OCR 未實測）。
- 登入畫面：`500,570` 橘（179,127,63）、`760,565` 藍（93,137,187）、`440,520` 米色。
- 注意：`stat.ps1` 在登入畫面也回 `ok:true`（欄位全空），判斷「在遊戲裡」要看 pos / level 非空。

## 工具：tools/gui/netwatch.py
- `netwatch.guard('腳本名')`：腳本迴圈每輪呼叫。已接進 `quest.py`（畫面判斷為 unknown 時先交給它）、`petwatch.py`（每輪）、`heal.py --watch`（每輪）。偵測到「網路異常」提示 → 點確定；偵測到登入畫面 → 自動 `relogin()`（檢查帳密欄非空 → 登錄 → 一鍵全登 → 等載入 → `recover`），成功回傳 `reconnected`（各腳本重設狀態：quest 重找追蹤、petwatch 立刻重掃）；失敗（上面 3 種情況）才 halt → `sys.exit(10 / 11)`。walk.py 沒有長迴圈，未接。
- 「帳密欄非空」= 在帳號框 700-900,400-425、密碼框 690-880,484-502 數深棕色像素（≥10 個），**只判斷有沒有字，不讀內容**。
- **讀取失敗三態（2026-10-10）**：`_match` 回 True / False / None（`gui.ps1` 失敗、空輸出、`pwfail` 重試一次仍失敗 = None；waitpix / waitstill 的 PrintWindow 失敗會印 `pwfail`）。None = 「不確定」：不點、不宣告重連 / 登錄成功（`hud_ok()` 只在確定不是登入畫面時才 True）。`login_fields_filled()` 讀不到回 None，**不當成「欄位空」halt**：本輪不點登錄、回 `{'status':'ok','failed':True}`，連續 5 輪（`netwatch.json` 的 `read_fails`）讀不到才 halt（理由「讀不到帳密欄 / 遊戲畫面」）。errlog 限頻：同一段連續失敗只記一筆，恢復後補一筆「已恢復」。測試：`tools/gui/test_netwatch.py`（mock，不碰遊戲）。
- 單獨掛機：`uv run --no-project python tools/gui/netwatch.py --watch --interval 10`（`--once` 只查一次、`--status` 看 halt 狀態）。與其他腳本共用 `netwatch.act.lock`，同時只有一方處理；`--watch` 有單例鎖 `netwatch.lock`。
- 退出碼：10 = halt（要使用者處理）、11 = 連續失敗、9 = 全視窗驗證停手旗標、2 = 版面不支援。
- halt 檔 `tools/.cache/netwatch.halt`：halt 時寫入，之後所有腳本一啟動就退出 10，**不會自己再按登錄**（避免錯誤提示被重試）。使用者處理完 / 人類自己登入後，再跑任何腳本（或 `netwatch.py --once`）偵測到 HUD 回來會自動清除 halt；也可手動刪檔。
- `recover()`（P8 起）：`team_report()` 逐張卡片 OCR（整塊一起讀不準；單張標籤 450/730,272/357/442 寬 70 高 32，缺字會算 unknown）→ 有「單人」才 `fix_team()`（全部登錄 → 全員單人才 `team.form()`）→ **重登 / 人類登入回來時自動跑 `grind.py ensure` 一次**（`grind.run('ensure', ignore_watchers=True)`：當前角色 → 隊長、5 人快速 + 自動戰鬥只補不對的、開遇敵、確認 2 次 EXP 橫幅；約 25 秒）→ ensure 失敗才退回舊的「原地遇敵沒開就開」。ensure 失敗（退出碼非 0）只記 errlog + 印警告、**不重試、不 halt**；quest 的 battle.lock 有效時 grind 回 8（不搶畫面）；grind 已在執行（巢狀）時略過；SystemExit（停手）照常往外丟。純網路異常確定後 HUD 就回來（沒經過登入畫面）的重連不跑 ensure。`netwatch.py --no-grind` 關掉自動 ensure。
- 重登（relogin 成功 / 人類登入回來）時一律先 `charstate.clear()`（重登後當前角色會變 DKBO5，旁路檔舊值作廢；之後 char.ensure 現場讀切換面板）。
- 每次事件寫 errlog（來源 netwatch）與 actions.log。選擇角色面板特徵 `SIG_CHARSEL`（640,640 橘 / 500,250 米 / 1186,190 紅 X / 350,330 棕）。
- 實測限制：登錄流程的畫面順序是人工驗證過一次（本次斷線後第一次登錄）；`relogin()` 的自動判斷（欄位非空、選角面板偵測、HUD 回來）分段驗過，整套自動跑尚未遇到第二次斷線。**主動登出（2026-10-12 手動實測成功一次）**：設置 → 底部「全員登出」517,731 → 提示「是否登出全部角色?」（有確認框，確定 715,557）→ 回登入畫面 → 只點登錄 590,585 → 選角面板「一鍵全登」740,640 → 約 20 秒進遊戲；重登後隊伍沒散，netwatch 不介入所以沒有 grind ensure。已寫成腳本 `tools/gui/relogin.py --confirm`（見下節）。

## 斷線重登後快速戰鬥設定會被重設（2026-10-10 實測）
重登後 5 個角色的外掛「快速戰鬥」（484,343）全部變回沒勾（自動戰鬥、鎖定騎寵 / 戰寵、全部遮罩仍保留），遇敵就變成完整戰鬥畫面。處理：開外掛逐一點頭像，`gui.sh pixel "484,343"` 255,255,255 = 沒勾才點、點完再讀確認 223,223,223（切換式，先讀再點）。P8 起 netwatch 的 `recover()` 在重登後自動跑 `grind.py ensure`（讀 5 人、只補不對的、確認 EXP）；它失敗時（errlog / 警告）請手動跑 `uv run --no-project python tools/gui/grind.py ensure`。這條自動路徑**只有離線測試**（`test_netwatch.py`，假 grind / team），不能故意斷線實測。

## 主動全員重登：tools/gui/relogin.py（2026-10-12，離線測試；畫面判斷多半未實機驗證）
用途：伺服器端卡死（全隊頭上 VS 牌、「戰鬥中禁止當前操作」、刷新無效）時，登出再登入洗乾淨狀態。
```
uv run --no-project python tools/gui/relogin.py --confirm [--leader DKBO] [--size 5] [--no-team] [--stuck]
uv run --no-project python tools/gui/relogin.py --dry-run      # 唯讀前置檢查
```
登出不可逆（全員下線）：沒有 `--confirm` 不動（退出碼 1）。流程：preflight + 畫面必須是主畫面 → 開設置面板 → 驗「全員登出」鈕顏色（橘紅，樣本量得）才點 517,731 → 確認提示窗（像素同網路異常單鈕窗 + OCR 含「登 / 出 / 全」，OCR 讀不出信任像素，讀到別的字不點）→ 確定 715,557 → 等回登入畫面（≤ 60 s）→ `netwatch.relogin(grind_ensure=False, encounter=False, team=False)`（帳密欄空 / 登錄後提示窗 / 連 3 次失敗 → halt，規則同上）→ `team.check`（5 人、隊長 DKBO；全員單人才 `team.form`）→ `char.ensure DKBO` → 再 `team.check`。
`--stuck`（2026-10-13）：起始畫面除了主畫面 / 設置面板，也收「自動巡路中」與「快速戰鬥 VS 牌」（純函式 `start_ok`；完整戰鬥 / 對話框 / 其他面板仍 107）。questrun 在 quest.py 42（VS 牌卡死 90 秒）、19（巡路卡住解不開）、3 + 全隊 VS 牌卡住時自動呼叫 `relogin.run(confirm=True, stuck=True)`，每任務最多 2 次；之後 105 → `team.form --regroup`、關原地遇敵、重查戰鬥設定再續片（見 ui/quest.md）。**實機要確認**：VS 牌 / 巡路畫面時設置鈕點得開。
退出碼：0 成功；1 缺 --confirm；2 / 8 / 9 / 10 / 11 共用；100 設置打不開或登出鈕特徵不符；101 確認窗沒出現；102 訊息不是登出；103 沒回登入畫面 / 中途冒提示窗；104 登入階段沒成功（非 halt）；105 隊伍檢查 / 組隊失敗；106 當前角色切回失敗；107 起始畫面不是主畫面；108 netwatch 動作鎖被佔；109 多視窗不自動重登（見上「多視窗時不自動登錄」）。
**未實機驗證**：設置標題板 / ✕ 特徵與登出鈕顏色（取自既有截圖樣本）、確認提示窗的像素特徵與 OCR 框（假設為單鈕提示窗）、等回登入畫面的時序；不符時一律停手不點。登入畫面階段不存截圖（含帳號欄）。測試：`tools/gui/test_relogin.py`。
