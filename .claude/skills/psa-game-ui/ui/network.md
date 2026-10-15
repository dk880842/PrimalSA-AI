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
`relogin.py`（主動全員重登，含 questrun / rebirth 卡住時的 `--stuck` 自動重登）多視窗時一開始就 **109**、什麼都不點（登出後回不來）；有帳號對照設定檔時不擋（見下節）。
各視窗的 halt / 狀態檔各自一份：主視窗 `tools/.cache/netwatch.*`，其他 `tools/.cache/clients/<程序名>/netwatch.*`。
**以上是「沒有帳號對照設定檔」時的行為**；有設定檔時改走下一節。

## 帳號核對（2026-10-15 使用者新規則；離線測試 test_accounts.py，**未實機**）
每個視窗有固定帳號；登入畫面帳號欄對得上才自動按「登錄」。兩個帳號密碼相同，**密碼欄絕對不碰**。
- **設定檔**：`tools/gui/accounts.local.json`（`.gitignore` 的 `tools/gui/*.local.json`；repo 公開，帳號名不得出現在程式 / 測試 / 文件 / log）。格式：`{"PrimalSA": "<主視窗帳號>", "PrimalSA2": "<第二視窗帳號>"}`（鍵 = 程序名稱同 PSA_CLIENT，值只收英數 / 底線 1～32 字）。`accounts.py check` 印哪些視窗有設定（只印長度）；兩個帳號在容錯正規化後相同 = 設定檔無效。測試用 `PSA_ACCOUNTS_FILE` 換路徑（testenv 固定指到不存在的檔）。worktree 裡沒有這個檔 → 照舊行為。
- **判斷誰來管**（`netwatch.login_mode()`）：設定檔有本視窗 → 帳號核對（**單 / 多視窗一樣，不看程序清單**）；沒設定檔 / 本視窗不在對照表 / 格式錯 → `auto_login_check()` 舊行為逐字不變。
- **讀帳號欄**：`ocr.ps1` 框 `610,392,360,40`、`-Dark 120 -Zooms 2,3,4`，三個倍數各自的整欄文字正規化後**全部一致**（至少 2 個有字）才算讀得出，讀不出重讀一次（`accounts.classify`）。正規化只合併「字母 ↔ 數字」易混字（小寫、去空白、o→0、i / l / | → 1），**數字之間不合併**，所以只差尾碼 1 / 2 的兩個帳號不會混淆。實測（fixture `tools/.cache/net5.png`，主視窗登入畫面）：Windows OCR 把帳號的 o 讀成 0，2～6 倍、Dark 0 / 100 / 120 / 150 結果都一樣。
- **流程**（`netwatch.relogin`，netwatch 自動登錄、`relogin.py`、questrun / rebirth `--stuck` 共用）：帳密欄都有字（舊規則）→ 讀帳號欄：
  - 符合 → 按登錄 590,585（之後同舊流程：一鍵全登 → 等進遊戲 → recover）。
  - 不符（帳號記憶共用，常態）→ 拿全視窗共用輸入鎖 `tools/.cache/login-input.lock`（等最多 90 秒，120 秒沒放視為持有者死了）→ 確認還是登入畫面、密碼欄有字 → 點帳號欄右段空白 **930,411** → `{END}{BS}×40{HOME}{DEL}×40` 清空 → 數深色點確認空（< 10）→ `gui.ps1 typeq <本視窗帳號>` → 再讀一次 = 符合、密碼欄仍有字、仍是登入畫面 → 按登錄 → 放鎖。
  - 讀不出 / 清不掉 / 重打後不符或讀不出 / 密碼欄變空 / 畫面變了 / 輸入鎖等不到 → **halt**（退出碼 10），不按登錄。
  - log / errlog / halt 檔只寫「帳號欄核對：符合 / 不符 / 讀不出」「（重打後）：…」，不寫帳號名、不寫 OCR 讀到的字。
- **打字只進本視窗**：`gui.ps1 typeq` 逐字 PostMessage `WM_CHAR` 到 `$h`（`Find-PsaProcess` 依 PSA_CLIENT 找到的 hwnd；常駐 server 每個請求帶 client，hwnd 快取鍵含 client），fg 模式也不用 SendKeys（SendKeys 送前景視窗）；操作 log 只記「typeq（N 字，內容不記錄）」；`winenv.redact` 讓 server 逾時的 errlog 也遮掉內容；驗證停手旗標同樣擋 typeq。key（PostMessage）本來就不需要點擊鎖，跨視窗的序列化靠上面的登入輸入鎖。
- `relogin.py`：有設定檔時多視窗也照跑（`login_mode` 回 account），否則照舊 109。
- **未實機的地方**：點帳號欄後 Unity 輸入框的游標位置 / 是否全選、`{END}` / `{HOME}` / `{DEL}` 在背景 PostMessage 下是否有效（`{BS}` 已實測一次刪一字）、點欄位會不會跳出帳號下拉清單、背景視窗的 InputField 收不收 WM_CHAR。這些不符時都會停在「清不掉」或「重打後核對不符」而 halt，不會按登錄。
- **安全實測法（不用真的斷線）**：①人在某個視窗自己登出到登入畫面（或剛開的遊戲停在登入畫面），跑 `PSA_CLIENT=<程序名> uv run --no-project python -c "import sys; sys.path.insert(0,'tools/gui'); import netwatch, accounts; print(netwatch.read_account(accounts.for_client()[1]))"`（唯讀，只印 self / other / unreadable）；②人把帳號欄改成另一個帳號再跑一次應得 other；③在 ② 的狀態下改呼叫 `netwatch.retype_account(...)`（會點帳號欄 / 清空 / 打字，不按登錄），回空字串 = 重打成功，人看畫面確認；④最後才 `netwatch.py --once` 整套（會按登錄）。

## 每視窗驗證停手旗標（verifyhalt.py，2026-10-15；同日下午改成各自視窗停手）
某個視窗疑似驗證 / 答題視窗（`uikit.preflight` / `uikit.fail` 回 9、watch 的 unknown_long / quest 警報轉述、quest.py 連 3 次不認得、follow 不認得超過 10 分鐘）時，**多視窗情境**（同上判斷）會寫**那個視窗自己的**旗標：
主視窗 `tools/.cache/verify-halt.json`（原路徑）、其他 `tools/.cache/clients/<程序名>/verify-halt.json`（= `clients.cache_dir()`）。只停出事的視窗，其他視窗照常（13:48 p2 把便利店畫面當不認得 → 舊版全部視窗一起停的誤報，使用者因此改規則）。
存在時（只看本視窗 = PSA_CLIENT）：`netwatch.check_and_reconnect` 回 `verify`、`netwatch.guard` → `sys.exit(9)`（quest / follow / heal --watch / petwatch / grind 迴圈每輪都會呼叫）；`uikit.preflight` 9（watch 沒在跑時先現場連讀，見下方自動清）；`VerifyGuard` 停止；`gui.ps1` 的 click / dclick / drag / key / typeq 不送、exit 9（最後一道保險；`psawin.ps1 Get-PsaVerifyHalt` 依這個請求的 client 算路徑，常駐 serve.ps1 每請求設 PSA_CLIENT）；watch 照常監看，`state.flags.verify_halt = true`；psa-hud 在該視窗段落紅字。
**自動清（使用者 2026-10-16：偵測保留、旗標自動清；當天 p1 / p2 / p3 被刪除確認窗、道具說明彈窗、手動開的面板、新視窗剛開等誤設 7 次以上）**：旗標存在時，畫面連續 5 秒（`verifyhalt.AUTO_CLEAR_S`）且至少 6 次讀圖（`AUTO_CLEAR_N`）都是已知正常畫面（`screen_sigs.normal_screen`：idle / walking / battle / 認得的面板，且沒有提示視窗等附註；或面板上疊已知彈窗 popup_*）→ 清掉。判斷只有一份 `verifyhalt.AutoClear`：watch.py 每輪餵（主要清除者，零輸入）；watch 沒在跑（state 不新鮮）時 `uikit.preflight` 自己現場連讀（`uikit.verify_screen`，間隔 1 s），通過就清掉繼續、任何一次不正常就照舊 9（watch 在跑時 preflight 不讀，交給 watch）。**絕不清**：unknown（可能是驗證視窗）、對話框（驗證視窗是 NpcScript，可能長得像 NPC 對話框）、獲得物品、選擇對象、登入 / 選角、載入 / 全黑、主畫面帶提示視窗、最小化 / 讀不到——任何一次都歸零；讀圖時間早於旗標時間不算；`set` 手動設的（src=manual）不自動清。清時：actions.log `verifyhalt 自動清除（畫面已恢復：<狀態>）`、quest-events.log 一行、設旗標時那筆 errlog（id 存在旗標 `err_id`）補 fix（psa-hud 錯誤表顯示已改進）、watch 的 `state.flags.verify_autoclear = {ts, label}`；psa-hud 紅字第二行「畫面恢復 5 秒自動清；手動：…」。
手動清保留：`uv run --no-project python tools/gui/verifyhalt.py clear <程序名>`（不給 = 本視窗 PSA_CLIENT、`all` = 全清）；`status [程序名|all]` 列各視窗（不給 = all，退出碼 9 = 有任一個）。單一視窗不寫旗標，行為與以前相同（只有自己 = 各自停手）。
**舊格式**（改版前全部視窗共用 `tools/.cache/verify-halt.json`，非主視窗寫的內含 `client` 欄）：client 不是主視窗 → 歸屬那個視窗（那個視窗照樣停，主視窗不受影響；Python 與 gui.ps1 同規則），`status` 會註明；`clear <那個程序名>` 清掉，或主視窗之後要寫自己的旗標時自動搬到該視窗資料夾。壞檔 / 沒有 client 欄 = 主視窗的（保守停手）。

## 偵測特徵（2880×1659 截圖座標，容差 25）
- 提示視窗：`520,570` `880,570` `600,300` `600,557` `830,557` 米色（243,215,175 上下）+ `640,557` 藍（61,106,167）；兩側米色確保是「單鈕」提示。再用 ocr.ps1 讀訊息 `585,370,260,40`（`-Light 200`）：讀到文字卻不含 網/路/異/重/連 就當別種提示不點（OCR 讀不到則信任像素；OCR 未實測）。
- 登入畫面：`500,570` 橘（179,127,63）、`760,565` 藍（93,137,187）、`440,520` 米色。
- 注意：`stat.ps1` 在登入畫面也回 `ok:true`（欄位全空），判斷「在遊戲裡」要看 pos / level 非空。

## 工具：tools/gui/netwatch.py
- `netwatch.guard('腳本名')`：腳本迴圈每輪呼叫。已接進 `quest.py`（畫面判斷為 unknown 時先交給它）、`petwatch.py`（每輪）、`heal.py --watch`（每輪）。偵測到「網路異常」提示 → 點確定；偵測到登入畫面 → 自動 `relogin()`（檢查帳密欄非空 → 登錄 → 一鍵全登 → 等載入 → `recover`），成功回傳 `reconnected`（各腳本重設狀態：quest 重找追蹤、petwatch 立刻重掃）；失敗（上面 3 種情況）才 halt → `sys.exit(10 / 11)`。walk.py 沒有長迴圈，未接。
- 「帳密欄非空」= 在帳號框 700-900,400-425、密碼框 690-880,484-502 數深棕色像素（≥10 個），**只判斷有沒有字，不讀內容**。
- **讀取失敗三態（2026-10-10）**：`_match` 回 True / False / None（`gui.ps1` 失敗、空輸出、`pwfail` 重試一次仍失敗 = None；waitpix / waitstill 的 PrintWindow 失敗會印 `pwfail`）。None = 「不確定」：不點、不宣告重連 / 登錄成功（`hud_ok()` 只在確定不是登入畫面時才 True）。`login_fields_filled()` 讀不到回 None，**不當成「欄位空」halt**：本輪不點登錄、回 `{'status':'ok','failed':True}`，連續 5 輪（`netwatch.json` 的 `read_fails`）讀不到才 halt（理由「讀不到帳密欄 / 遊戲畫面」）。errlog 限頻：同一段連續失敗只記一筆，恢復後補一筆「已恢復」。測試：`tools/gui/test_netwatch.py`（mock，不碰遊戲）。
- 單獨掛機：`uv run --no-project python tools/gui/netwatch.py --watch --interval 10`（`--once` 只查一次、`--status` 看 halt 狀態）。與其他腳本共用 `netwatch.act.lock`，同時只有一方處理；`--watch` 有單例鎖 `netwatch.lock`。
- 退出碼：10 = halt（要使用者處理）、11 = 連續失敗、9 = 本視窗驗證停手旗標、2 = 版面不支援。
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
