# 介面索引

實測基準：2026-10-09，客戶區 2880×1659（`gui.sh max`），截圖 1440×830。座標都是截圖座標。
**1920×1080 螢幕**（最大化後客戶區 1920×1017、截圖 960×508）另有一套座標：[layout-1920x1017.md](layout-1920x1017.md)（主畫面已量、換算規則、各工具支援狀態）。
bundle 名對應 `knowledge/overview/ui-screens.md`。紅區規則在 [../SKILL.md](../SKILL.md)。

## 依功能找
| 功能 | 檔案 | 入口（主畫面座標） | 狀態 |
|---|---|---|---|
| 主畫面按鈕總表、收合、關閉方式 | [home.md](home.md) | — | 實測 |
| 1920×1017 版面座標（主畫面、換算規則） | [layout-1920x1017.md](layout-1920x1017.md) | — | 主畫面實測，其他面板待量 |
| 人物資訊（屬性、抗性、潛力點） | [role.md](role.md) | 頭像 119,68 | 實測 |
| 切換角色、**快速組隊**、組隊面板、**解散隊伍** | [team.md](team.md) | 切換 763,760／組隊 850,760 | 實測（組隊、解散都成功） |
| 任務面板、任務詳情、**自動巡路 / 解任務監測 quest.py（--task、黃色問號、追蹤列表 OCR；--solo / --fight 單人逃跑、完整戰鬥逃跑鈕 1283,168 / 自動戰鬥鈕 1380,600）** | [quest.md](quest.md) | 左側 148,236／詳情 368,328／追蹤 205,325 | 實測（成人儀式） |
| 背包、倉庫、材料圖鑑 | [bag.md](bag.md) | 背包 1120,760 | 實測（`bag.py` find / hp / list / purge / store --all-copies 2026-10-12 實機；purge 提示窗核對 2026-10-14 改綠字二值化 + 漏行過濾，未實機；drop / swap-weapon 未實機） |
| 每日任務（委託接取）：醫院 1005 NPC、5 環合成提交、1009 / 2009 便利店 | [daily.md](daily.md) | 醫院 1005 (41,42) 點 NPC | 探路實測，腳本離線測試（未實機） |
| 漆黑洞窟轉生任務一行腳本 | [rebirth.md](rebirth.md) | — | 離線測試（實機未驗證） |
| 寵物面板（出戰 / 騎乘 / 休息、技能、成長、還原名字） | [pet.md](pet.md) | 寵物頭像 318,80 | 實測（設定出戰、騎乘；修改名字視窗座標 2026-10-14） |
| 地圖傳送（大陸／練級／便捷／英雄戰場） | [transfer.md](transfer.md) | 圓形傳送鈕 1340,65 | 實測（練級傳送實際等級門檻已全測） |
| 設置（聲音、畫面、其他、聊天） | [setting.md](setting.md) | 設置 1210,760 | 只看過 |
| 外掛 ASS（自動戰鬥、補血、抓寵） | [ass.md](ass.md) | 外掛 1300,760 | 只看過，未改設定 |
| **開始練功完整流程**（依等級選點 → 傳送 → 遇敵 → 5 人戰鬥設定） | `/psa-grind-start` skill（`../psa-grind-start/SKILL.md`） | — | 步驟 1、4、6 已驗證 |
| 聊天、信件、通知 | [social.md](social.md) | 95/178/260,583 | 實測 |
| 排行榜、家族 | [social.md](social.md) | 940,760／1030,760 | 只看過 |
| 商城、贊助、交易所、LuckyCard（多為紅區） | [shop.md](shop.md) | 上排 605～880,70 | 只看過 |
| 網路異常提示、斷線、登入畫面 | [network.md](network.md) | 確定 715,557、登錄 590,585、一鍵全登 740,640 | 已實測（登錄 → 選角 → 全登 → 進遊戲；使用者授權只按登錄）|
| 尚未實測（NPC、戰鬥、移動、驗證視窗） | [todo.md](todo.md) | — | 待補 |

## 腳本工具一覽（固定流程先跑腳本，非 0 才手動；退出碼 / 細節見各檔開頭或對應 ui/*.md）
| 工具（`uv run --no-project python tools/gui/…`） | 做什麼 | 文件 |
|---|---|---|
| `team.py status / check / form / disband` | 隊伍唯讀 / 檢查 / 快速組隊（已組好不點）/ 解散；退出碼 40～47 | [team.md](team.md) |
| `char.py current / switch / ensure` | 當前角色讀取 / 切換並驗證；退出碼 60～65 | [team.md](team.md) |
| `grind.py start / ensure / check` | 開始 / 恢復練功（選點傳送、外掛 5 人 `ass.set_many`、開遇敵、2 次 EXP 確認）；`start` 不給 --spot = 去練功（依等級選點、未滿地雷區背景起 follow）；退出碼 50～58；`--heal` 支援 `spots.py` 全部 9 點 | `../psa-grind-start/SKILL.md`、[transfer.md](transfer.md) |
| `pet.py list / set-state / rest-all / store / take / reset-name / depot-fix-names` | 寵物面板讀 / 狀態 / 存取（硬性擋騎寵）/ 成長字串還原物種名（名字為主）；退出碼 66 / 67、70～78；**store / take 掛機中要加 `--pause-encounter`**（戰鬥中操作會被吃掉） | [pet.md](pet.md) |
| `rebirth.py [--trans N] [--from 階段] [--dry-run]` | 漆黑洞窟轉生任務（2004～2008）整段：前置檢查 → 進洞 → 兩場 BOSS → 換弓 → 補血（2026-10-17 起不設忠犬）→ 精靈王轉生 → 收尾；退出碼 80～89；**新寫的 bag.py / petdrop.py 實機沒驗證** | [rebirth.md](rebirth.md) |
| `ass.py get / set / pet`（API：`set_many`） | 外掛面板讀 / 設四項勾選與戰寵動作；`select_role` 內建等遮擋 + 重試（頂部跑馬燈蓋住 DKBO3 → 等它消失）| [ass.md](ass.md) |
| `daily.py read-all / plan / show / run [--confirm-buy] [--from 段] [--fresh] [--dry-run] [--no-grind]` | 每日任務（委託接取）：全隊一起移動、各買各的、各合成各的（prep → read → plan → sam → mid → fish → final → finish）；不讀石幣 / 鑽石 / 格數；退出碼 220～229（**未實機**，離線 test_daily.py） | [daily.md](daily.md) |
| `netwatch.py`（`guard` 已接進 quest / petwatch / heal --watch） | 斷線重連 / 自動登錄；重登後清 charstate、`team.form`、自動 `grind.ensure` | [network.md](network.md) |
| `clientupdate.py run [--no-grind] [--restart] [--dry-run]` | 伺服器改版「登錄失敗！版本錯誤！」→ 重開本視窗客戶端 → 熱更新 → 登入 → grind ensure（退出碼 210～219，未實機） | [network.md](network.md) |
| 多視窗 `PSA_CLIENT=PrimalSA2 …`（`clients.py` 印名稱 / 名單 / 狀態資料夾） | 選要操作的遊戲視窗（程序名稱，不設 = PrimalSA）；click / drag 有全域點擊鎖（逾時 exit 7）；狀態檔各視窗一份（主視窗路徑不變，其他在 `tools/.cache/clients/<程序名>/`、`notes/clients/<程序名>/`）；多視窗不自動登錄、每視窗驗證停手旗標 `verifyhalt.py`（只停出事的視窗；畫面恢復正常穩定 5 秒自動清）；PrimalSA2 目前可用 gui.sh / mirror.sh / 讀圖 .ps1 / walk.py / watch.py / netwatch.py（--no-team --no-grind）/ heal.py | [SKILL.md「多視窗」](../SKILL.md)、[network.md](network.md) |
| 共用模組（不直接跑）：`spots.py`（練級傳送點表，唯一來源，heal 也用）、`uikit.py`（面板規格 / safe_click / preflight / 退出碼）、`charstate.py`（當前角色旁路檔）、`namematch.py`（角色名整名樣板）、`petmatch.py`（寵物名 / 等級樣板）、`petimg_match.py`（縮圖比頭像認物種，pet.py 名字認不出時的備援）、`itemname_match.py`（道具格名字白字整名樣板，bag.py 道具辨識的第一層）、`itemimg_match.py` + `imgmatch.py`（道具格縮圖比 GameClient 道具圖，名字沒認出才用；見 bag.md「道具辨識以名字為主」）、`digitmatch.py`（HUD 數字樣板） | 判斷畫面、比對名字 / 數字、禁區保護 | 各檔開頭 |

## 依情境找
| 想做的事 | 去哪 |
|---|---|
| 不碰遊戲就看目前狀態（畫面種類、等級 / HP、疑似驗證警報） | `uv run --no-project python tools/gui/watch.py --get`（需 psa-hud 在跑；僅供參考，不能當點擊依據；說明見 [../SKILL.md](../SKILL.md)「即時狀態監看」） |
| 單人逃跑解任務（跑 NPC → 組隊 → 對話 / 打；紅暴 2031） | `/psa-quest-solo` skill（介面 / 逃跑鈕座標見 [quest.md](quest.md#單人逃跑解任務questpy---solo----fight2026-10-10流程見-psa-quest-solo-skill)） |
| 5 個角色組成一隊 | 先跑 `team.py form`，非 0 再 `/psa-quick-team` skill（介面參考 [team.md](team.md#快速組隊)） |
| 解散隊伍 | `/psa-disband-team` skill（介面參考 [team.md](team.md#解散隊伍)） |
| 面板 ESC 關不掉 | [home.md](home.md#關閉方式) |
| 看目前操作的是哪個角色 | [team.md](team.md#切換角色) |
| 設定寵物出戰 / 騎乘（多角色） | 先跑 `pet.py list / set-state / rest-all`；手動流程 [pet.md](pet.md#操作設定出戰--騎乘2026-10-09-實測)、像素判斷 [pet.md](pet.md#腳本化-pety-像素--樣板判斷p-i5-實測2026-10-11) |
| 道具存倉庫（公共 / 個人） | [bag.md](bag.md#倉庫2026-10-09-實測) |
| 丟棄道具（紅區，使用者授權才做） | [bag.md](bag.md#丟棄物品2026-10-09-實測使用者授權丟新手棍棒) |
| 自動戰鬥的動作、對象、補血 / 回魔 / 復活門檻 | [ass.md](ass.md#戰鬥設置分頁2026-10-09-實測只看沒改) |
| 角色自動加點方案、同步加點 | [ass.md](ass.md#便捷功能--特色設定角色自動加點2026-10-09-實測) |
| 鎖定 / 解除鎖定騎寵、戰寵 | [ass.md](ass.md#鎖定騎寵--鎖定戰寵2026-10-09-實測使用者授權) |
| 新角色 0 轉 1 級開局（開禮盒 / 穿裝 / 寵物 / 存倉 / 外掛 / 組隊 / 初入石器 / 練功） | `tools/gui/newchar.py plan|run`（未實機；手動流程 notes/new-account.md、[bag.md](bag.md)、[ass.md](ass.md) 的 points 段） |
| 多角色處理背包 / 寵物 | 面板左欄頭像直接切換（[bag.md](bag.md)、[pet.md](pet.md)），不用切換面板 |
| 看角色在哪 | 主畫面右上 1195,65「地圖名 ID:x,y」 |
| 「網路異常，是否重連?」/ 回到登入畫面 | [network.md](network.md) → 點確定；登入畫面 netwatch 自動按登錄（授權範圍見該檔）|
| 出現要選答案的視窗 | [todo.md](todo.md#答題驗證) → 停手通知使用者 |

### watch 認得的畫面（`state.json` 的 `screen`；`screen_sigs.py` 的特徵，2026-10-11）
| `screen.state` / `panel` / `annot` | label | 備註 |
|---|---|---|
| `idle` | 主畫面 | 外掛紅字 / 底部圖示列 / 右下按鈕任一組命中；**不代表沒有驗證視窗** |
| `walking` `dialog` `reward` `select` `battle` | 自動跑路中 / 對話框 / 獲得物品視窗 / 選擇對象面板 / 戰鬥中 | 舊有 |
| `panel` + `pet` / `bag` / `ass` / `team` / `qteam` / `switch` / `setting` / `transfer` / `quest` / `role` | 面板：寵物 / 背包 / 外掛 / 組隊 / 快速組隊 / 切換角色 / 設置 / 傳送 / 任務 / 人物資訊（主畫面點頭像開出，✕ 1335,112） | **主判據 = 頂部標題板的字**（`PANEL_TITLE`，每面板 8 點中 7；各面板標題位置各自固定，只有寵物 / 人物資訊共用同一塊牛角板；字被蓋不到、不怕 EXP 浮字蓋框線）；標題都不中才退回 ✕ + 8 點框線備援；認得的面板不計入 unknown 計時、不產生 verify_suspect。右側直式分頁（寵物 / 倉庫 / 圖鑑、基礎 / 精靈）是子分頁、有選中 / 未選中兩種外觀，不作判據。切換角色標題在 EXP 橫幅出現時會被蓋（走備援）。改 screen_sigs 後 watch 要重啟才生效 |
| `panel` + `shop`（2026-10-15） | 面板：NPC 商店 | 便利店 / 道具商店等 NPC 商店（木框 + 商品格 + 紅卷軸 + 數量 −/＋ + 藍「購買」鈕 + 右上紅 ✕ 1207,107）。**不看標題字**（隨 NPC 不同），看結構色：✕ + 16 點（卷軸紅邊 6、數量 ±黃符號 2、購買鈕藍 3、下緣米色帶 3、商品格暗框 2）中 12 點命中（`SHOP_PTS`，`panel_strict` 要 14）。樣本只有 p2 競技場便利店 2 張；2550 張負例（含商城 / 交易所 / LuckyCard / 贊助）最多命中 1 / 16。不計 unknown、不產生 verify_suspect；`uikit.close_known_panel` 可點 ✕ 關（不會買東西）。商城（紅區）框架不同，仍不認得 |
| `unknown` + annot `login` / `charsel` / `loading` / `black` | 登入畫面 / 選角畫面 / 載入畫面（「加載中」字形 / 英文版「Loading...」綠橘雙進度條，進度無關）/ 黑畫面（轉場） | 已知畫面，不計 unknown；quest.py / uikit.preflight 轉場最多等 60 秒（見 ui/quest.md「轉場等待與上限」）。登入 / 選角 / 載入也算驗證停手旗標自動清的正常畫面（2026-10-16） |
| annot `net_lost`（2026-10-16） | 網路異常窗（交給 netwatch） | 「提示：網路異常，是否重連?」：NET_DIALOG 框 + 白字字形（`screen_sigs.net_lost`，比像素不用 OCR；樣本 net1 + 10-16 08:00 三視窗）。已知畫面、不設旗標；持續 3 秒 watch 另開 `netwatch.py --once`。同框的任務條件不達標 / 刪除確認窗照舊。見 ui/network.md |
| annot `quiz`（2026-10-16，**未實機**） | 答題 / 驗證視窗（停手，請人工處理） | npcanswer 介面正面命中（`screen_sigs.quiz_screen`，GameClient prefab 推出的特徵）→ 不管 classify 判成什麼都先標、**立刻**設驗證停手旗標（watch / preflight / quest.py）。見 ui/network.md |
| `unknown` + annot `popup_keypad` / `popup_qty` / `popup_confirm` + `over_bag` / `over_pet`（2026-10-12） | 面板：背包＋數字鍵盤 / 面板：背包＋數量輸入視窗 / 面板：寵物＋確定 / 取消提示窗 | 模態彈窗把底下整個畫面壓暗成約 ×0.5（實測背包 ×0.50、寵物 ×0.47）。**兩個條件都成立才認**：①底下是壓暗的背包或寵物面板（標題板 8 點同一比例 k ∈ 0.40～0.56）②彈窗本身 8 點中 7 吻合三種之一（拆分數字鍵盤、「數量輸入」、確定藍 / 取消橘兩顆鈕的「提示」確認窗＝丟寵 / 存入戰鬥寵）。已知畫面，不計 unknown。驗證視窗、網路異常提示（只有一顆確定）等其他彈窗疊在面板上仍是 unknown → 10 s 照報（道具詳情彈窗 2026-10-16 起見下一列 popup_item）。樣本 `fixtures/popup_px.json`（正例 20 張：鍵盤 3 / 數量輸入 7 / 確認窗 10；負例 9 張），tools/.cache 1306 張 1440×830 截圖 0 誤判（errlog #243 #244 #254 #261 #264 都是這三種彈窗，不是切換面板） |
| `unknown` + annot `popup_delok` + `over_bag`（2026-10-15） | 面板：背包＋刪除確認窗 | 背包「刪除管理 → 刪除選中」跳出的單鈕「提示」窗（綠字 `名稱*數量\|` 清單 + 「是否批量刪除道具?」+ 確定）。這個窗框和網路異常 / 任務條件不達標等單鈕提示窗**完全相同**，所以**四個條件全成立才認**（`screen_sigs.bag_delok`）：①窗框 8 點中 7 ②窗外是**壓暗 ×0.48 的刪除模式背包**（紅框右 / 下緣、刪除選中 / 取消刪除鈕、✕，6 點中 5）③背包標題板壓暗（dim_panel = bag）④窗內有亮綠字清單（y 356 / 366 / 376 / 386 × x 642～786 每 6 px 的 100 點中 ≥ 4 點亮綠；1～5 行清單都會穿過）。驗證 / 答題視窗（選項是圖片）、網路異常提示、疊在普通背包或其他面板上的提示窗都不符 → 照舊 unknown。樣本 `fixtures/bag_del_px.json`（確認窗 9 / 刪除模式 3 / 負例 8）；tools/.cache 3034 張 1440×830 截圖：確認窗 12 張全認、0 誤判。**刪除模式本身**（紅框、還沒按刪除選中）背包標題板照常露出 → 本來就是「面板：背包」 |
| `unknown` + annot `popup_item` + `over_bag`（2026-10-16） | 面板：背包＋道具說明彈窗 | 背包 / 倉庫頁點道具格跳出的說明彈窗（圖示 + 名稱 + 詳細介紹 + 拆分 / 丟棄 / 穿戴 / 取出 / 存入鈕）。把背包壓暗 ×0.60（消耗品）/ ×0.45（裝備），不在 dim_panel 範圍、標題常被跑馬燈蓋 → 舊版 unknown，10-16 p2 三次誤設驗證停手旗標。**三個條件全成立才認**（`screen_sigs.bag_itempop`）：①窗外背包 8 點（✕、刪除管理、整理背包、右半米色底）同一比例壓暗（k 0.40～0.66，8 中 7）②彈窗金框左右兩邊（消耗品 x 492 / 968、裝備 x 482 / 958，y 520 / 600 / 690）一版 6 點全中 ③底部有藍色按鈕（y 640 / 650 兩列 ≥ 6 點）。`uikit.preflight` 遇到已知彈窗（popup_*）也不計 unknown（`known_popup_now`）。樣本 `fixtures/bag_itempop_px.json`（正例 22 / 負例 12）；tools/.cache 3056 張 1440×830 截圖：22 張命中全是道具彈窗、0 誤判 |
| `unknown`（其餘） | 不認得的畫面 | 連續 10 s → `alerts.unknown_long`（自動存截圖 `tools/.cache/watch-alerts/`）+ `flags.unknown_screen`，**不設旗標**（2026-10-18 起沒有 3 分鐘兜底，久留也不設旗標、不亮 verify_suspect） |

**還沒樣本、所以 watch 不認得（出現會算 unknown，10 s 後截圖報「不認得的畫面」，不設旗標）**：人物 / 角色資訊（頭像 119,68）、寵物管理以外的圖鑑、商城 / 贊助 / 交易所 / LuckyCard（NPC 商店已認得，見上表）、家族、排行榜、信箱 / 鈴鐺、聲音設置小窗、面板上疊的其他彈窗（網路異常提示、背包 / 寵物以外面板上的彈窗；背包 / 寵物上的數字鍵盤 / 數量輸入 / 確認窗 / 道具說明彈窗已認得，見上表）。要補：開該面板時 `gui.sh shot watch-panels/<名>-0.png`（存 tools/.cache/watch-panels/），再把檔案加進 `make_fixtures.py` 的 `PANEL_POS` 並重學特徵。挑點 / 統計樣本時用 `tools/gui/shotcache.py`（離線）：`build` 增量更新索引 `tools/.cache/shots-index.json`（每張圖的畫面標籤與來源 manual / fixture / rule / auto），`stats` / `list --label pet --suspect` 查分類，`iter_shots(label)` 取 (路徑, 標籤, 取點函式)；取過的點存在點快取，同一組點重跑全部樣本 < 1 秒；新截圖丟進 tools/.cache 後再 `build` 即可。

## 新增 / 更新規則
- 驗證過、會重複執行的流程拆成獨立 skill（`.claude/skills/psa-<流程>/SKILL.md`），功能檔與兩邊索引改成引用它。目前有：`psa-quick-team`、`psa-disband-team`、`psa-grind-start`、`psa-quest-solo`。
- 一個功能（或一組相關面板）一個檔；新檔要加進上面兩張表。
- 每檔開頭放座標基準說明；寫「入口」→「畫面內容」→「操作步驟」→「注意 / 失敗訊息」。
- 沒實測的寫「未實測」或「推測」，實測後改掉並更新索引的「狀態」欄。
- 第一次碰到的新畫面：截圖記錄，從 [todo.md](todo.md) 移到對應檔。
