# AGENTS.md — 精靈王石器（PrimalSA）AI 遊玩專案規範

所有 AI 代理（Claude Code、Codex、其他 agent）在這個專案工作前都要先讀完本檔。

## 1. 專案目標
讓 AI 遊玩《精靈王石器》（PrimalSA，Unity 製作的石器時代類回合制網路遊戲，韓版客戶端 `yhkrn`）。
遊戲客戶端放在 `GameClient/`；從客戶端整理出的遊戲知識放在 `knowledge/`，AI 玩遊戲時用來檢索。
角色真名 DKBO、DKBO2～5（字母 O）；文件中的 DKB0～DKB05（數字 0）同義，程式比對 O / 0 視為相同（`tools/gui/charname.canon`、`charstate.same / display`），輸出 / 顯示用真名。

## 2. 目錄結構
```
PrimalSA-AI/
  AGENTS.md            本檔：專案規範 + 遊戲規則摘要
  PLAYBOOK.md          方法手冊：怎麼讓 AI 玩遊戲（給其他 AI / 想照做的人）
  GameClient/          遊戲本體（唯讀！見第 3 節）
  knowledge/           遊戲知識庫（自動產生，勿手動修改）
    README.md          知識庫索引：分類目錄、全部文件清單、查詢方法
    overview/          遊戲常數、程式列舉、客戶端檔案分類與格式、UI 畫面清單
    items/             道具（武器 / 防具 / 飾品 / 藥品 / 材料 / 寵物裝備 / 任務 / 其他）、套裝
    pets/              寵物與怪物（依系別分檔）、取得方式、騎乘、經驗表
    skills/            戰鬥技能、戰鬥狀態 Buff、角色 Buff、技能學習 NPC
    world/             地圖、出口 / 傳送點、NPC（依地圖分組）、交通 / 傳送服務
    quests/            任務鏈、攻略說明、NPC 腳本與對話、答題題庫
    crafting/          合成配方、材料圖鑑、製作、強化、回爐
    economy/           NPC 商店、商城、抽獎、活動 / 副本、公告、儲值（參考）
    text/              遊戲文字（繁中 / 韓文對照，用來看懂畫面訊息）
    data/              機器可讀原始資料：tables/*.jsonl（全部設定表）、maps.bin（通行格）、schema.tsv、enums.tsv
  tools/
    extract/           匯出器：GameClient → knowledge（extract.py、tabtoy.py、docs.py）；uimock.py = 答題介面（npcanswer）prefab 合成模擬圖 → tools/.cache/npcanswer-extract/（screen_sigs.quiz_screen 選點 / 測試用，2026-10-16）
    schemadump/        SchemaDump.cs：從 HotUpdate.dll 抽 Tabtoy 欄位對照與列舉（ReflectionOnly，不執行遊戲程式）
    query/psa.py       知識庫查詢工具（搜尋、交叉查詢、跨地圖路線、通行格）
    gui/gui.sh         遊戲畫面操作（截圖、點擊、拖曳、按鍵）；用法與按鈕地圖見 .claude/skills/psa-game-ui/
                       固定流程腳本（先跑腳本、非 0 才手動；退出碼見各檔開頭）：team.py（組隊 status/check/form/disband）、char.py（切換當前角色）、grind.py（開始 / 恢復練功；`start` 不給 --spot = 去練功：依等級選點、未滿地雷區背景起 follow 到地雷區自己結束，任何腳本不寫死地雷區，2026-10-15；選點看隊伍 5 人最低等級、傳送被擋「未達到N轉M級」自動退點並記上限，2026-10-16）、pet.py（寵物 list/set-state/rest-all/store/take；reset-name 成長字串還原物種名〔鉛筆 → 輸入框留空 → 確認，費用字樣 67 停手〕、store 前自動還原、depot-fix-names 修倉庫卡）、ass.py（外掛勾選，含 set_many、battle 解任務戰鬥設定檢查、heal 精靈補血勾選〔2026-10-15，未實機〕）、questrun.py（1.82 任務驅動器：`plan` / `run 2999 2017 2015`，資料表 questdefs.py，每任務只開一次任務詳情；紅暴 `run 2031` **預設單人逃跑**〔2026-10-17 使用者：解任務預設不用龍王的守護 → 不給 --dragon 時自動走 `--solo`，不吃不讀 buff、不回 156；`--dragon` opt-in 才組隊打到底（龍王必要、步 6 便捷傳送 + --fight），沒龍王 156 → `--solo`；獎勵存倉 / `--drop-items` 丟首飾；postrebirth hero 段直接帶 --solo；耐久力回複藥 NPC 會給，不檢查不買、`--buy-missing` 已是 no-op〕；未實機〕；交接先查外掛戰鬥設定 `ass.py battle`（30 分內沿用）、龍王的守護預設不吃、不讀 buff、不取 / 不存（2026-10-17；`--dragon` opt-in：除彌生和日美子 / 猜謎三兄弟 / 恐龍博士 / 卡坦的願望外都吃，剩的留 DKBO 背包、run 結束存回）、逐人驗證 `--verify risk`（風險事件才當場驗、其餘 run 結束批次驗）、VS 牌卡死 / 巡路卡住自動 `relogin.py --stuck`、`--pet-turnin` 交寵物、`--drop-reward` 丟 1 級獎勵寵（後兩者未實機）；實機驗證成人儀式 / 彌生和日美子 / 亞姆的斧頭；VS 牌卡死自動重登 2879d59 僅離線；`questdetail roles` 逐人唯讀讀任務列；depot_use 以 buff 圖示驗證 e7e5a72；2026-10-13 起2026-10-14 起任務之間不讀血量〔--team-hp-min 預設 0，只看隊長 HUD；完成判斷不開任務詳情：quest.py「任務完成」或回 5 = 完成〕、任務 NPC 只有「再見」〔quest.py 40〕或信封發亮 → 背包滿刪白名單 bag.AUTO_PURGE + mail.py 領「丟失的物品」續跑〔失敗 153 / 154〕、交接先清殘留對話框 / 背包等已知面板；2026-10-14：連 4 片 quest.py 3 / 30 座標在一對出口間來回 / 原地 → 全員重登 + walk.leave_junction 走開〔stuckrecover.no_progress〕、3 時步號前進不算卡住、交接 / form 失敗遇戰鬥先等打完、龍王失敗後收尾關面板，均未實機）、relogin.py（主動全員重登：設置全員登出 → 登錄 → 一鍵全登 → 檢查隊伍，`--confirm`，退出碼 100～108，設置面板判斷已實機修過 27d970e）、clientupdate.py（伺服器改版「登錄失敗！版本錯誤！」→ 關本視窗程序 → 重開 → 熱更新（1366×768 小視窗下載 OK / 重啟 / 公告 X → max）→ 帳號核對登錄 → 一鍵全登 → grind ensure：`run [--no-grind] [--restart] [--dry-run]`，退出碼 210～219，netwatch 命令列看到版本錯誤自動接；帳號核對改容許字尾文字游標；整段未實機，2026-10-16）、rebirth.py（漆黑洞窟轉生任務 2004～2008 整段，含 accept 接任務、heal 段不再設戰寵忠犬〔2026-10-17，`--pet-action` 明確給值才設〕、卡住 19 / 42 自動重登〔共用 stuckrecover.py，questrun 同一份〕、龍王的守護預設不吃（2026-10-17；`--dragon` opt-in 才在 enter 進洞前吃一次、cleanup 存回）、boss20 打完後新階段 storepets〔2026-10-16，未實機〕把 5 人寵物欄全存個人倉庫〔pet.py store-all，不驗名字 / 不擋騎寵〕、cleanup 一～四轉丟獎勵寵〔固定動作：逐人直接丟第 1 格，不讀名字 / 等級，petdrop.drop_first_slot / `--first-slot`，2026-10-16〕、五轉獎勵寵機暴存個人倉庫絕不丟、多給的弓 bag.py drop-spare-bow，退出碼 77 倉庫滿 + 80～89 + 97，含 bag.py 背包 / 倉庫、petdrop.py 丟寵物，實機未驗證）、rebirth_pets.py（轉生後寵物重整〔boxes 2026-10-17 分階段批次：背包面板只開一次，倉庫取 5 人 → 背包使用 5 人 → 公共存 5 人 → 個人存 5 人，未實機；取出前背包占用改開彈窗前讀〔p2 二轉 rc 101，彈窗暗幕全判有〕〕〔2026-10-16 起沒有 store 段，舊寵物已由 rebirth.py storepets 全存；`--store-mount` 無作用〕，`--confirm-buy-catch` 石幣「+」買可抓捕數〔共用 catchbuy.py，petquest 同一份〕、戰寵逐隻驗 Lv1、抓完 reset-name 還原名字〔learn-species 只當備援、鎖定下拉先比物種名〕，退出碼 100～109）；
                       postrebirth.py（轉生後任務重做總控：`plan|run [--confirm-drop] [--from 段]`，questrun 各段不帶 --dragon（2026-10-17 不用龍王），盤點 → 成人儀式 → 彌生和日美子 → 紅暴（直接 --solo 單人逃跑）→ 清背包⓪ → 1.82 前段 → 清背包① → 1.82 後段 → 清背包② → 四大洞窟 → 恐龍博士 → 卡坦 → 猜謎三兄弟 → 收尾 grind 地雷區，進度檔續跑，退出碼 170～176，只有離線測試）；
                       petquest.py（寵物任務總控：`run 2016|2019|3003 [--confirm-drop]`；恐龍 / 卡坦先存每人寵物欄第 2 格（名字 + 等級記進度檔；空 / 騎寵 / 讀不出 162）→ 一次抓滿（不分批；寵物欄放不下的自動進個人倉庫，抓完取回；reset-name 還原名字 → 名字驗證，成長字串登錄只當備援；誘餌不夠自動用外掛「+」買缺額，不需旗標，`--confirm-buy-bait` 保留為 no-op）/ 公共倉庫分配 / 練寵 → rest-all 後才接任務 → 交 → 丟獎勵寵 → 取回第 2 格的寵物出戰，進度檔續跑，退出碼 160～169，只有離線測試）；
                       newchar.py（新角色 0 轉 1 級開局：`plan|run [--from 步驟] [--confirm-buy] [--no-grind]`，名單依 PSA_CLIENT；開迎新助力禮盒 / 石幣2萬 / 穿新手裝〔bag.py wear〕後同一個背包面板接著分階段存倉〔公共輪 5 人 → 個人輪 5 人，2026-10-17，未實機〕→ 迪基格斯出戰、瑪斯貝卡騎乘 → 5 人自動戰鬥 → 精靈補血打勾〔ass.py heal，未實機，失敗 195〕→ 自動加點〔ass.py points，方案輸入座標待量測 → 方案不對就跳過記待手動〕→ 組隊 → 初入石器 → grind 去練功；→ 買溫蒂妮金幣步驟呼叫 buywendy.py；進度檔續跑，退出碼 190～199，**未實機**，只有離線測試）；
                       buywendy.py（買「溫蒂妮Lv5的金幣」〔競技場道具屋 500 石幣〕→ 穿 → 外掛隊長人物首次動作 = 風的精靈Lv.5 打勾 → 回村 → 組隊 → 去練功：`plan|run --confirm-buy [--no-form] [--no-grind]`，已有金幣不買、每步看遊戲現況可重跑，退出碼 200～209；便利店面板不在 screen_sigs，商店內動作壓在約 6 秒內避免 watch 判驗證視窗；手動探路只做到選好商品，**購買 / 穿戴 / 首次動作 / 回村組隊已用 p2 實機走過（腳本的買前核對與走嚮導未實機）**；ass.LEADER_FIRST 加 PrimalSA2 = 風的精靈）；
                       daily.py（每日任務〔委託接取，薩姆吉爾醫院 1005〕：`read-all|plan|show|run [--roles] [--from 段] [--confirm-buy] [--fresh] [--dry-run] [--no-grind] [--regroup pull|gather]`，各買各的、各合成各的；醫院段隊長一人走 38,40 → 快速組隊不解散、隊員不走路直接點 NPC，便利店段組隊帶進店再解散（使用者 2026-10-17）：prep → read → plan → sam〔薩村 1009 買料〕→ mid〔回醫院合成 / 提交〕→ fish〔瑪麗娜絲 2009 買料〕→ final〔回醫院取料合成提交到 5/5〕→ finish〔組隊去練功〕；不讀石幣 / 鑽石 / 背包倉庫格數〔鐵則 3 每日例外〕，買到沒看數量框歸 0 + 背包名稱，背包用「材料種類上限 13」模型決定存個人倉庫〔滿才公倉並記 in_public〕；胡椒由使用者先放公倉、只取用不買；進度檔每視窗每人一份可續跑、跨 00:00 → 220；退出碼 220～229；dailyplan.py 純函式、shopkit.py 便利店共用〔從 buywendy 抽出〕、ocrfix.py OCR 修正表；**整支未實機**，只有離線測試 test_daily.py，2026-10-17）；
                       bufftime.py（唯讀讀 buff 剩餘時間 + 預計到期：`read [--kind exp|dragon|all]`，點頭像下方 buff 圖示開浮窗 OCR 後再點關，p1 / p2 皆可，退出碼 130～134，2026-10-15 實機驗證；預計到期寫本視窗 `bufftime.json` 給 psa-hud 倒數；depot_use 吃下 2倍智慧果〔6 小時〕/ 龍王的守護〔10 分鐘〕並驗到圖示後也直接寫入〔`bufftime.record_eaten`，src=eat，不用再 read〕）；
                       exp.py（唯讀讀 5 人經驗 + 升級時間估計：`read` / `eta --target 131`，人物資訊面板開一次逐人切頭像、經驗表交叉驗證，歷史 tools/.cache/exp-history.jsonl，退出碼 100～102）；
                       操作 log：actlog.py（寫 `.cache/actions.log` 最新 2000 行 + 按小時分檔 `.cache/actions/YYYY-MM-DD_HH.log` 保留 14 天；`actlog.py show [--date] HH:MM-HH:MM [--grep]` 查舊細節；gui.ps1 同步寫分檔）；
                       共用模組：clients.py（多視窗身分 PSA_CLIENT / 每視窗狀態資料夾 cache_dir）、accounts.py（斷線重登的視窗 → 帳號對照，讀本機 accounts.local.json〔不進 git〕，帳號欄核對 / 重打，未實機）、verifyhalt.py（每視窗驗證停手旗標，只停出事的視窗；畫面恢復正常穩定 5 秒自動清）、spots.py（練級傳送點表，heal 也用）、uikit.py（面板規格 / 禁區保護 / preflight）、charstate.py（當前角色旁路檔）、namematch.py / petmatch.py / digitmatch.py（名字、寵物、HUD 數字的圖樣板比對）；petglyph.py（名字框成長字串 / 倉庫卡字與等級的字形樣板讀字，取代 OCR、倉庫卡不用選卡；種子 fixtures/pet_glyph_tpl.json）；petimg_match.py（寵物縮圖比知識庫頭像認物種；2026-10-14 晚起 pet.py 名字為主：名字讀到物種名就不比縮圖，縮圖只在名字讀不出時補，衝突 = 不確定）；itemname_match.py（道具格「顯示道具名」白字整名樣板，2026-10-14 起 bag.py 道具辨識第一層，彈窗核對過才學）；itemimg_match.py（道具格縮圖比 GameClient 道具圖，名字沒認出的格才用，PSA_ITEM_MATCH）；imgmatch.py（兩者共用的比對核心）；netwatch.py（斷線重連 / 自動登錄，重登後自動 grind ensure）
                       watch.py（零輸入即時狀態監看 → tools/.cache/state.json，psa-hud 啟動；HUD 數值用 digitmatch.py 樣板比對為主、stat.ps1 OCR 補漏；state 只供顯示，不能當點擊依據）、serve.ps1（常駐 server，winenv.GuiServer 啟動；WSL 預設開、Windows 原生需 PSA_GUI_SERVER=1、=0 關閉）、bench.py（唯讀量測 / soak）、shotcache.py（tools/.cache 截圖樣本的分類索引 shots-index.json + 取點快取；screen_sigs 挑點 / make_fixtures 用，`build|stats|list|relabel|bench`）、test_*（離線測試）
    web/               靜態查詢網站：build.py 讀 knowledge/ 產生 site/（不進 git），static/ 是前端；deploy.sh 建置並發布到 Cloudflare Pages
    .cache/            匯出時的暫存（HotUpdate.dll 等），可刪
```
網站：Cloudflare Pages 專案 `psa-wiki`（https://psa-wiki.pages.dev/），只上傳 site/；原始碼在 GitHub repo https://github.com/dk880842/PrimalSA-AI（2026-10-09～10-10 曾公開、曾有 1 個 fork，2026-10-10 改回私有，2026-10-11 再改為公開）。仍照公開標準：不要 commit 帳號機密、角色私人資訊、`notes/` 遊玩紀錄；`GameClient/` 不進 repo。`.gitignore` 排除 `GameClient/`、`tools/.cache/`、`site/`、`notes/`。

## 3. 鐵則（必須遵守）
1. **`GameClient/` 是唯讀的**：不得新增、修改、刪除、搬移、重新命名其中任何檔案或資料夾，也不要把任何輸出寫進去。
   工具只能讀取它；所有產出寫到 `knowledge/` 或 `tools/.cache/`。遊戲自己更新 / 下載資源不在此限。
2. **不碰帳號機密**：不讀取、不輸出、不記錄密碼與登入資訊（例：`AssetBundles/savepwd.txt`、登錄檔 PlayerPrefs 的 `LastPassword_*`、`LastCdkey_*`、`LastAccount_*`）。需要登入時由人類操作。
   例外：斷線回到登入畫面時，可以自動按「登錄」（只用遊戲已自動帶入的帳密；**密碼欄絕對不碰**、不點鑰匙 / 註冊、不把帳號名寫進 log / 程式 / 文件 / commit）。
   帳號重打（使用者 2026-10-15 訂、**2026-10-16 改：不核對**）：每個視窗有固定帳號，依**本機設定檔的視窗 → 帳號對照**（`tools/gui/accounts.local.json`，不進 git）：
   不再 OCR 核對帳號欄，一律只清空並重打帳號欄成本視窗帳號（拿全視窗輸入鎖、確認仍是登入畫面且密碼欄有字、清空後像素確認已空），打完不核對、直接按登錄（密碼欄仍絕對不碰）。log 只寫「帳號欄已重打（不核對）」。
   帳密欄是空的、帳號欄清不掉 / 密碼欄變空 / 畫面不是登入畫面、登錄出錯（密碼錯誤、封號、維護、驗證碼）或連續失敗 3 次 → 停手通知使用者。
   沒有設定檔 / 視窗不在對照表：同機多個遊戲視窗時一律不自動按登錄（可能登錯帳號互踢），單一視窗照舊只按登錄。實作見 `tools/gui/netwatch.py`、`accounts.py`（帳號重打未實機）。
3. **不付費**：不得進行任何儲值、購買鑽石、月卡、抽獎扣鑽等花真錢或鑽石的操作；`economy/recharge.md` 只供參考。
   **石幣（遊戲幣）可以花**：例如 NPC 商店、傳送、外掛捉寵設置「+」買可抓捕數（每次 50,000）。會自動花石幣的腳本動作要用明確旗標控制（`--confirm-buy-catch`／`--confirm-buy`），並保留鑽石不變的檢查，鑽石有變就停手。（使用者 2026-10-11、10-15）
   例外：每日任務（daily.py）不讀石幣、不讀鑽石，不做鑽石不變檢查（便利店材料 / 快速合成只扣石幣；買到沒改看數量框 + 背包名稱，使用者 2026-10-17）。
   寵物任務（petquest）買可抓捕數不需旗標（使用者 2026-10-15）：誘餌不夠只買缺額，讀不到鑽石或鑽石有變就停手（`--confirm-buy-bait` 保留為無作用參數）。
4. **不修改遊戲行為**：不改遊戲檔案、不注入、不寫入遊戲記憶體、不竄改 / 偽造封包、不使用加速或修改器。
   AI 只能透過正常的畫面操作（看畫面、點擊、鍵盤）遊玩。
5. **防腳本驗證要交給人類**：遊戲有伺服器觸發的答題驗證（NpcScript「防腳本驗證」、`quests/answers.md` 題庫，選項是圖片），
   公告寫明違規「最高永久封停所有帳戶」。**一旦出現答題 / 驗證視窗，立刻停止自動操作並通知使用者**，不要自己亂猜答案。
   偵測方式（使用者 2026-10-16 定案：**正面辨識**；2026-10-18 使用者拿掉「3 分鐘沒有進度」兜底）：答題介面（npcanswer，`screen_sigs.quiz_screen`，特徵由 GameClient prefab 推出、未實機）一出現就立刻設驗證停手旗標；
   其他不認得的畫面腳本照樣自己停下不點，watch 只截圖存證、HUD 顯示「不認得的畫面」，**不設旗標**（設旗標只剩答題介面正面命中）。網路異常窗交給 netwatch（不設旗標）。
6. **不用違規方式多開**：遊戲允許同一台電腦同時開多個視窗（使用者 2026-10-15 確認至少 3 個；做法：`GameClient` 內放改名的執行檔 `PrimalSA2.exe` 加目錄連結 `PrimalSA2_Data` → `PrimalSA_Data`，由使用者自行建立）。
   不要用虛擬機、沙盒、改硬體識別碼、改執行檔內容或注入等方式繞過遊戲或伺服器的限制。每個視窗最多 5 個角色（UISwitchRole）。
   工具用環境變數 `PSA_CLIENT=<程序名稱>`（PrimalSA2 …；不設 = PrimalSA）選視窗，點擊有全域鎖；每個視窗的狀態檔各自一份（主視窗沿用 `tools/.cache/`、`notes/`，其他在 `clients/<程序名>/` 底下）；多視窗時 netwatch 只在本機帳號對照核對通過才自動按登錄（鐵則 2），某個視窗出現驗證視窗就寫**那個視窗自己的**停手旗標（主視窗 `tools/.cache/verify-halt.json`、其他 `tools/.cache/clients/<程序名>/verify-halt.json`），只有該視窗停手、其他視窗照常（使用者 2026-10-15 改）；**設旗標只有一種情況**（使用者 2026-10-16 定案、2026-10-18 拿掉 3 分鐘兜底）：答題介面正面命中（watch / preflight / quest.py 立刻設）；不認得的畫面 10 秒只截圖存證（`tools/.cache/watch-alerts/`）、HUD 顯示「不認得的畫面」；網路異常窗（框 + 白字字形）watch 判 `net_lost` 不設旗標，持續 3 秒就另開 `netwatch.py --once` 處理（watch 自己仍零輸入）；旗標**自動清**（使用者 2026-10-16）：畫面回到已知正常狀態（主畫面 / 跑路 / 戰鬥 / 認得的面板 / 面板上疊已知彈窗 / 登入 / 選角 / 載入 / 網路異常窗）穩定 5 秒（≥6 次讀圖）會自動清（watch 每輪判斷；watch 沒在跑時腳本 preflight 現場連讀判斷），畫面仍不認得 / 對話框 / 答題介面等一律不清、照舊停手（鐵則 5 不變）；清時寫 actions.log / quest-events.log「verifyhalt 自動清除（畫面已恢復：…）」並把那筆 errlog 補 fix；手動 `verifyhalt.py clear <程序名>` 保留（`set` 手動設的不自動清），`status` 列各視窗；哪些工具已支援見 psa-game-ui SKILL.md「多視窗」。
7. **`knowledge/` 不要手動改**：它由工具產生，重新匯出會覆蓋。要補充攻略心得、遊玩紀錄，請另外放在 `notes/`（自行建立）。
8. 對使用者回報時說實話：查不到的資料就說查不到，推測的內容要標明是推測。

## 4. 遊戲規則摘要（玩之前先懂這些）
細節以 `knowledge/` 為準；以下是快速參考。

### 4.1 基本
- 回合制石器時代類 MMORPG。主城 / 新手村：**薩姆吉爾村**（地圖 1000），村長家（1006）接新手主線「初入石器」。
- 寵物等級上限 140（Config.petMaxLevel）；經驗表 Exp 列到 200 級（`pets/levels.md`）。角色可**轉生**（transLimit / trans 條件），2 轉以上線上每 10 分鐘得 1 點活力。
- 角色四項基礎點：體力 Vitality、腕力 Strength、耐力 Stamina、速度 Speed（升級配點，可自動加點 / 存方案）。
- 伺服器設定（開服公告）：1.5 倍基礎經驗；每次登入有離線時間（一般 2 小時）。

### 4.2 貨幣
| 代碼 | 名稱 | 用途 |
|---|---|---|
| 3 | 石幣 | 主要遊戲貨幣：NPC 商店、傳送、委託任務、合成。賣寵物 / 道具、答題、刷樓取得 |
| 1 | 鑽石 | 儲值貨幣（**AI 不得花費**） |
| 8 | 綁定鑽石 | 不可交易的鑽石 |
| 2 | 金幣 | 強化等 |
| 10 | 活躍度 / 活力 | 每日活動累積，合成、精工用 |
| — | 聲望 | 練寵掛機升級取得，用於回爐、合成、購買門票 |

### 4.3 戰鬥
- 回合制，雙方各最多 10 格：上排人物位置 0~4、下排寵物（主人位置 +5）。每回合所有人下指令後一起演出。
- 指令（EBattleCmdType）：攻擊、技能（精靈 / 寵物技能）、捕捉、道具、防禦、換騎寵、逃跑。有下指令時限（同引擎的時光石器實測約 90 秒），可開自動戰鬥。
- **屬性相剋**（地水火風，每隻合計 100）：地剋水、水剋火、火剋風、風剋地。戰場屬性 / 結界（物理、魔法）會改變傷害。
- 異常狀態：毒、麻痺、睡眠、石化、酒醉、混亂、暈眩；裝備有對應抗性（`items/` 能力欄的「抗毒、抗麻…」）。
- 遇敵率可用道具 / Buff 調整（例：月神守護降低遇敵率，`skills/role-buffs.md`）。
- 戰鬥錄影檔：`AssetBundles/{攻方}_{守方}_{時間}_{序號}.json`（base64 JSON），在遊戲裡看過錄影才會有。

### 4.4 寵物
- 系別 petType 0~28（烏力系、布伊系…融合系），100 = 敵方 / NPC 不可當寵物（`pets/README.md`）。
- 成長檔：體 / 腕 / 耐 / 速 檔數加總為「總檔」，越高越好；依石器時代通則，同種寵物個體各項會有約 ±2 的檔次差異（本遊戲未實測）。
- 寵物技能欄上限 7；技能可在寵物技能店 NPC 學（`skills/skill-teachers.md`），或用技能罐頭 / 道具。
- 取得：野外捕捉（公告：寵物依圖鑑抓捕）、抽獎蛋、領取點、任務獎勵、合成（`pets/pet-sources.md`、`economy/lottery.md`）。
- 部分寵物可騎乘，多數需要先學騎乘（`pets/ride.md`）。

### 4.5 地圖與移動
- 座標 (x, y) 格子制，畫面為斜角視角（x 往右上、y 往右下）。方向：0 下、1 左下、2 左、3 左上、4 上、5 右上、6 右、7 右下。
- 走到地圖出口座標就會傳送（`world/warps.md`）。另有城鎮傳送、付費傳送（例如 2000 石幣）、船 / 飛行交通 NPC（`world/transport.md`）。
- NPC 常在櫃檯後方，站在 3 格內即可點擊對話。
- 有些地圖禁止組隊、禁止看錄影、禁止逃跑或必須脫離戰鬥（`world/transport.md` 的「地圖限制」）。

### 4.6 任務與活動
- 任務類型：主線、支線、引導、每日、副本、突襲、職業 / 轉生、新手、家族任務（`quests/tasks.md` 有接取 / 回報 NPC 座標與條件）。
- 每日委託、藏寶圖（挖寶點 `world/transport.md`）、閻羅殿副本、族戰（莊園）等，見 `economy/activities.md`、`economy/notices.md`。

## 5. 操作遊戲畫面
操作前先讀 `.claude/skills/psa-game-ui/SKILL.md`（工具用法、操作迴圈、紅區）與同資料夾 `ui/README.md`（功能索引；按鈕座標、各面板內容依功能拆檔）。
工具：`bash tools/gui/gui.sh shot|click|drag|key|info|max|end`（WSL / Git Bash 手打用）；走路 / 補血用 `uv run --no-project python tools/gui/walk.py ...`、`heal.py`（兩邊指令相同）。座標用截圖座標；預設背景操作（不搶前景，點擊時游標瞬移約 0.15 秒）；用過 `fg` / `max` 後要跑 `end` 把前景還給使用者。

**即時狀態**：開著 psa-hud 時有 `watch.py` 在背景零輸入監看（只送 pixel / info / digitmatch / stat），`uv run --no-project python tools/gui/watch.py --get` 可讀；它只是參考，點擊前仍要現場讀圖，`idle` 不代表沒有驗證視窗；出現 `verify_suspect` / alerts 就依鐵則 5 停手通知。`state.hud.buffs`（每 12 s 唯讀讀頭像下方 buff：`exp` = 2倍智慧果、`dragon` = 龍王的守護）+ `bufftime.py read` 寫的本視窗 `bufftime.json`（預計到期）→ pane 表格的 Buff 列顯示「智慧果 剩 H:MM · 龍王 剩 H:MM」倒數（龍王只在 Buff 列，地圖列遇敵狀態只有「遇敵中 / 不遇敵」）；有圖示沒讀過時間顯示「智慧果 ?（bufftime.py read）」/「龍王 ?」。pane 是表格 UI（2026-10-15 使用者定案）：上方每視窗一張小表上下排（表頭 p1 / p2 + 程序名；！警示 → 人物 / 寵物 / 地圖 + 遇敵 → Buff → 狀態 / 事件 / 動作），下方錯誤 / 改進紀錄表（時間 / 次數 / 來源 / 內容 / 狀態，最近 6 筆、每筆橫線），寬度依 bodyColumns、中文算 2 格，見 psa-game-ui SKILL.md「pane 版面」。只有開 psa-hud 的那個 session 管理它，兩個平台同時開 session 時只有一邊有即時狀態。多視窗時（第 3d 步，未實機）同一個 session 每個視窗各 spawn 一支 watch（非主視窗的狀態在 `tools/.cache/clients/<程序名>/state.json`，讀法 `PSA_CLIENT=PrimalSA2 uv run --no-project python tools/gui/watch.py --get`），pane 每視窗一張小表；各視窗的 verify-halt.json / verify_suspect 紅字顯示在該視窗自己那張表的「！」列，不會全部一起紅。

## 5.2 在 Claude 桌面 App（Windows 原生）執行
專案也可以用 Claude 桌面 App 的 Claude Code 開（路徑 `C:\games\PrimalSA-AI`，shell 是 Git Bash，沒有 wslpath、沒有 /mnt/c）。工具已兼容，差異如下：
- **前置**：安裝 uv for Windows：`winget install astral-sh.uv`（Python 由 uv 自動管理）。`powershell.exe`（Windows PowerShell 5.1）系統內建。
- **指令**：`uv run --no-project python tools/gui/walk.py ...`、`heal.py`、`tools/query/psa.py` 與 WSL 完全相同；`bash tools/gui/gui.sh ...` 在 Git Bash 也能用（用 cygpath 換路徑）。
- **psa-hud mod**：stat.ps1 / watch.py 路徑由 session cwd 推算，不用改程式；session.start 會自動 spawn `tools/gui/watch.py`（即時狀態 → `tools/.cache/state.json`，pane 每視窗一張小表、地圖列帶遇敵、Buff 列帶「智慧果 剩 H:MM」；`/psa-hud watch on|off` 開關）。另外會自動設 session 標題（`PSA｜四大洞窟：琉璃洞窟 進行中`，讀 notes/quest-events.log 最後一筆 [questrun] / [rebirth]（取較新者；轉生例「PSA｜漆黑洞窟(二轉) boss10 進行中」；名字只取本 run 起點之後；失敗後若還有別的事件則顯示「接手中」）；練功中改「PSA｜練功中 地雷區」（最後一筆 questrun 之後 actions.log 最新是「原地遇敵：開」，且 state 沒說遇敵關 / 沒離開傳送點；有新 questrun 就回任務標題；實作 `grindActivity`）；只覆蓋空標題或「PSA｜」開頭，/rename 的名字不動；實作 register.tsx `titleFromLog` / `autoTitle`）。多視窗（第 3d 步，未實機）：每 30 秒背景跑 `clients.py running --rostered` 偵測正在執行、ROSTERS 有登錄的視窗，只有主視窗時一切照舊；多個時每視窗一支 watch（env 帶 `PSA_CLIENT`）、pane 每視窗一張小表、標題看主視窗並加「（N 視窗）」、`/psa-hud watch on|off|status [程序名|all]`、`/psa-hud ack [程序名|all]`。載入方式在使用者層級設定（不放進專案）：Windows 版的 `CLAUDE_CODE_PLUGIN_DIRS` 設成 `C:\games\PrimalSA-AI\tools\mods\psa-hud`（WSL 版是 `/mnt/c/games/PrimalSA-AI/tools/mods/psa-hud`；兩邊各有自己的 settings.json）。
- 其他：Windows 原生 Python 的 stdout 預設 cp950，walk.py 已自行改成 UTF-8；自己寫 Python 呼叫 gui.ps1 時用 `winenv.run_ps()`。
- 紅區、背景操作、驗證視窗等規則與 WSL 相同。
- 實測狀態：WSL 完整驗證；Windows 原生用 Windows 版 Python 驗過 `walk.py --plan`、`gui info / shot / pixel`、`stat.ps1`（Git Bash 環境本身未實測）。

## 5.1 怎麼查知識庫
1. 先看 `knowledge/README.md` 的分類目錄。
2. **用名稱 grep**（繁中、簡中、韓文都可；畫面上看到韓文就搜韓文）：
   ```
   grep -rn "烏力" knowledge --include=*.md
   ```
3. **查詢工具**（交叉關聯，推薦）：
   ```
   uv run --no-project python tools/query/psa.py find 薩姆吉爾
   uv run --no-project python tools/query/psa.py item 小的爪        # 能力 / 誰賣 / 怎麼合成 / 用途
   uv run --no-project python tools/query/psa.py pet 烏力           # 成長檔 / 屬性 / 技能 / 取得
   uv run --no-project python tools/query/psa.py npc 老村長         # 位置 / 販售 / 腳本對話 / 任務
   uv run --no-project python tools/query/psa.py map 1000           # NPC / 出口 / 入口
   uv run --no-project python tools/query/psa.py steps 2031         # 任務每一步：NPC @ 座標、對話 / 戰鬥 / 打怪（單人逃跑解任務用）
   uv run --no-project python tools/query/psa.py route 1000 92 99 1006   # 跨地圖路線（只算地圖出口）
   uv run --no-project python tools/query/psa.py grid 1000 92 99 10      # 座標附近通行格
   ```
   找不到路線時通常要搭船 / 用傳送服務；完全不相通時會立即回報，地圖相通但走不到時約需 10 秒。
4. 要精確欄位值就查原始表：`knowledge/data/tables/<表名>.jsonl`（一行一筆 JSON）。
5. ID 慣例：SkillBattle ID = skillId×1000+等級；戰鬥 Buff ID = type×1000+level；地圖 ID 以 `mapdata_<ID>` 檔名為準；
   道具圖示 Sprite 名 = Item.imageId；寵物頭像 Sprite 名 = Monster.imageId。

## 6. 更新知識庫（遊戲更新後）
遊戲啟動時會熱更新 `configs.assetbundle`、`hotupdate.dll.assetbundle` 等。更新後在專案根目錄執行：
```
uv run --no-project --with UnityPy python tools/extract/extract.py
```
約 10~30 秒，會重新產生 `knowledge/` 全部內容（schema 也會從新的 HotUpdate.dll 重抽，不用手動改欄位）。
只想重產 Markdown：`uv run --no-project python tools/extract/docs.py`。

## 7. 開發慣例
- **任務與操作一律腳本化**（2026-10-11 使用者規定）：之後每個任務、每種遊戲操作行為，都要寫成 `tools/gui/` 底下可以重跑的腳本，不能只靠 agent 手動點一次就結束。
  - 做法：第一次可以手動探路，但要邊做邊記座標、畫面特徵、例外狀況，做完就把流程寫成腳本，並補離線測試與 ui / skill 文件。
  - 腳本規範比照現有腳本（team / char / grind / pet / quest / rebirth）：開頭寫用法與分段退出碼；點擊前 `uikit.preflight` 與 `safe_click` 禁區保護；每步驗證，失敗不亂點；可 `import`；支援 `--dry-run`、中斷後可續跑；驗證視窗或斷線就停；不可逆動作（轉生、丟棄、存騎寵）要有明確旗標並先驗名字。
  - 腳本跑失敗時，先手動完成當次，再把失敗原因修進腳本，記 errlog。
- Python：查詢工具只用標準函式庫；匯出器需要 UnityPy（用 `uv run --with UnityPy` 臨時載入，不要裝進系統）。本機沒有 `python` / `py` 指令，一律用 `uv run`。
- C#：用 Windows 內建 `C:\Windows\Microsoft.NET\Framework64\v4.0.30319\csc.exe`，只支援 C# 5（不能用 `$""`、`?.`、`nameof`、`out var`）。
- 程式註解與文件用繁體中文。
- **跨平台（WSL 與 Windows 原生都要能跑）**：不寫死 `/mnt/c` 或 `C:\games\...`；Python 呼叫 PowerShell 一律經 `tools/gui/winenv.py`（`run_ps` / `to_windows`，自動判斷 WSL / Windows）；bash 腳本路徑換算先試 `wslpath -w`、再 `cygpath -w`。文件裡的指令寫成兩邊都通（`uv run --no-project python ...`）。
- 格式逆向細節：`knowledge/overview/client-files.md`。同引擎的《時光石器》工具 `C:\games\SA-tool`（CLAUDE.md 有大量逆向筆記）可作參考，但兩個遊戲的設定表欄位不同，不要直接套用它的 schema。
