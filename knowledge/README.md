# 精靈王石器（PrimalSA）遊戲知識庫

本資料夾由 `tools/extract/extract.py` 從 `GameClient/` 自動產生（**請勿手動修改**，重新匯出會覆蓋）。
產生時間：2026-10-09 12:08；遊戲資料版本（Config.MD5Version）：20260518；客戶端版本（app.ver）：1.0.0。

## 分類目錄
| 資料夾 | 內容 | 主要來源表 |
|---|---|---|
| [overview/](overview/) | 遊戲常數、程式列舉、客戶端檔案分類 / 格式、UI 畫面清單 | Config、HotUpdate.dll |
| [items/](items/README.md) | 道具 10390 件（武器、防具、飾品、藥品、材料、寵物裝備、任務、其他）、套裝 | Item、Suit |
| [pets/](pets/README.md) | 寵物 / 怪物 3980 種（依系別分檔）、取得方式、騎乘、經驗表 | Monster、PetData、PetBaby、Ride、Exp |
| [skills/](skills/README.md) | 戰鬥技能 1206、狀態 609、角色 Buff、技能學習 NPC | SkillBattle、Skill、SkillStatus、RoleBuff |
| [world/](world/README.md) | 地圖 1467 張、出口 5003 個、NPC 3973 個（依地圖分組）、交通 / 傳送 | MapName、MapWarp、Npc、Transfer |
| [quests/](quests/README.md) | 任務 373 步、攻略說明、NPC 腳本 / 對話 1268 個、答題題庫 | Task、TaskExplan、NpcScript、Answer |
| [crafting/](crafting/README.md) | 合成配方 1894、材料圖鑑、製作、強化、回爐 | ExchangeItem、ItemBook、ItemUp |
| [economy/](economy/README.md) | NPC 商店、商城、抽獎、活動 / 副本、公告、儲值 | Npc.npcArgs、ShopMall、Lottery、Activity |
| [text/](text/README.md) | 遊戲文字 6777 條（繁中 / 韓文對照） | NewLanguage、NewLanguagePublic |
| [data/](data/) | 機器可讀原始資料（見下） | — |

## 原始資料（data/）
- `tables/<表名>.jsonl`：全部設定表，一行一筆 JSON（含 Cn/Tn/Kr 三語全部欄位）。**要精確查欄位用這個**，例如 `grep '"ID":1610,' knowledge/data/tables/Monster.jsonl`。
- `schema.tsv`：Tabtoy 欄位對照（類別、tag、欄位名|型別）；`enums.tsv`：程式列舉。
- `maps.bin`：每張地圖通行格（格式見 tools/query/psa.py）；`mapinfo.json`：地圖寬高。
- `ItemAltList.csv`、`bundles.tsv`：圖示 bundle 對照、bundle 清單。

## 怎麼查（給 AI）
1. **先 grep 名稱**：`grep -rn "烏力" knowledge/ --include=*.md`（繁中名或韓文名都可以）。
2. **用查詢工具**（交叉關聯 + 路線）：
   - `uv run --no-project python tools/query/psa.py find 關鍵字`
   - `... psa.py item <名稱|ID>`：能力、誰賣、怎麼合成、拿去合成什麼、哪個抽獎有
   - `... psa.py pet <名稱|ID>`、`npc <名稱|ID>`、`map <名稱|ID>`、`skill <名稱|ID>`、`task <名稱|ID>`
   - `... psa.py route <起點地圖> <x> <y> <終點地圖> [x y]`：跨地圖路線（經過哪些出口）
   - `... psa.py grid <地圖> <x> <y> [半徑]`：印出座標附近的通行格
3. ID 慣例：SkillBattle ID = skillId×1000+等級；Buff ID = type×1000+level；Monster.petType 0~28 系別、100 敵方；地圖 ID 以 mapdata 檔名為準。

## 全部文件

- [crafting/README.md](crafting/README.md) — 合成 / 製作總覽
- [crafting/enhance.md](crafting/enhance.md) — 道具強化 / 升級
- [crafting/exchange.md](crafting/exchange.md) — 合成 / 兌換配方（ExchangeItem）：合成介面（UIHeCheng）用的配方。isSeletItemIndex 的材料是「多選一」。共 1894 筆。
- [crafting/huilu.md](crafting/huilu.md) — 回爐（Huilu）：寵物 / 道具回爐的花費表。
- [crafting/item-book.md](crafting/item-book.md) — 材料圖鑑製作（ItemBook）：材料圖鑑（UICaiLiaoTuJian）。
- [crafting/item-make.md](crafting/item-make.md) — 道具製作
- [economy/README.md](economy/README.md) — 經濟 / 商店 / 活動總覽
- [economy/activities.md](economy/activities.md) — 活動 / 副本 / VIP
- [economy/lottery.md](economy/lottery.md) — 抽獎（Lottery）：抽獎 / 扭蛋內容與權重。
- [economy/mall.md](economy/mall.md) — 商城
- [economy/notices.md](economy/notices.md) — 遊戲公告（Notice）：開服公告：基礎設定（經驗倍率、離線時間、月卡 / 季卡效果等）。
- [economy/npc-shops.md](economy/npc-shops.md) — NPC 商店：每個販售 NPC 的商品與價格（Npc.npcArgs）。貨幣：1=鑽石、2=金幣、3=石幣、8=綁定鑽石、10=活躍度、11=積分。
- [economy/recharge.md](economy/recharge.md) — 儲值（僅供參考，AI 不得進行任何付費操作）
- [items/README.md](items/README.md) — 道具總覽：Item 表共 10390 件道具，依類型分檔。
- [items/accessories.md](items/accessories.md) — 道具：飾品（手環 / 樂器 / 項鍊 / 戒指 / 耳環 / 護身符）：共 1192 件。能力欄：攻/防/敏/HP/MP/運/魅/閃避/爆擊/抗性；「取得」= NPC 販售或合成/圖鑑配方（細節見 crafting/、economy/npc-shops.md）。
- [items/armor.md](items/armor.md) — 道具：防具（頭盔 / 鎧甲 / 盾 / 鞋 / 手套 / 腰帶）：共 1712 件。能力欄：攻/防/敏/HP/MP/運/魅/閃避/爆擊/抗性；「取得」= NPC 販售或合成/圖鑑配方（細節見 crafting/、economy/npc-shops.md）。
- [items/consumables.md](items/consumables.md) — 道具：藥品 / 料理：共 388 件。能力欄：攻/防/敏/HP/MP/運/魅/閃避/爆擊/抗性；「取得」= NPC 販售或合成/圖鑑配方（細節見 crafting/、economy/npc-shops.md）。
- [items/materials.md](items/materials.md) — 道具：材料 / 寶石 / 行李：共 955 件。能力欄：攻/防/敏/HP/MP/運/魅/閃避/爆擊/抗性；「取得」= NPC 販售或合成/圖鑑配方（細節見 crafting/、economy/npc-shops.md）。
- [items/misc.md](items/misc.md) — 道具：其他道具（卷軸、蛋、禮包、經驗果、活動道具…）：共 3046 件。能力欄：攻/防/敏/HP/MP/運/魅/閃避/爆擊/抗性；「取得」= NPC 販售或合成/圖鑑配方（細節見 crafting/、economy/npc-shops.md）。
- [items/pet-equipment.md](items/pet-equipment.md) — 道具：寵物裝備 / 陣法：共 103 件。能力欄：攻/防/敏/HP/MP/運/魅/閃避/爆擊/抗性；「取得」= NPC 販售或合成/圖鑑配方（細節見 crafting/、economy/npc-shops.md）。
- [items/quest-items.md](items/quest-items.md) — 道具：任務道具：共 424 件。能力欄：攻/防/敏/HP/MP/運/魅/閃避/爆擊/抗性；「取得」= NPC 販售或合成/圖鑑配方（細節見 crafting/、economy/npc-shops.md）。
- [items/suits.md](items/suits.md) — 道具：套裝：套裝表 Suit，275 組。
- [items/weapons.md](items/weapons.md) — 道具：武器：共 2570 件。能力欄：攻/防/敏/HP/MP/運/魅/閃避/爆擊/抗性；「取得」= NPC 販售或合成/圖鑑配方（細節見 crafting/、economy/npc-shops.md）。
- [overview/client-files.md](overview/client-files.md) — 遊戲客戶端檔案分類：GameClient 內容分類與格式說明（供維護與進一步分析用）。
- [overview/enums.md](overview/enums.md) — 程式列舉（HotUpdate.dll enums）：從熱更新程式抽出的列舉：道具類型、戰鬥指令、方向、角色類型、任務狀態…。名稱是程式原文（英文 / 拼音）。
- [overview/game-config.md](overview/game-config.md) — 遊戲常數（Config 表）：Config 表唯一一列：伺服器 / 客戶端共用的遊戲常數。
- [overview/ui-screens.md](overview/ui-screens.md) — 遊戲介面（UI 畫面）：由 ui*_yhkrn.assetbundle 檔名整理的介面清單；用途是依拼音 / 英文推測。NPC 的 openUIName 會直接開這些畫面。
- [pets/README.md](pets/README.md) — 寵物 / 怪物總覽：Monster 表 3980 筆（含可捕捉寵物與敵方怪物）。
- [pets/enemies-1.md](pets/enemies-1.md) — 怪物 / NPC 戰鬥單位（1）：Monster 表 petType=100：戰鬥中出現的敵人、BOSS、NPC 單位，ID 154 ~ 2264。
- [pets/enemies-2.md](pets/enemies-2.md) — 怪物 / NPC 戰鬥單位（2）：Monster 表 petType=100：戰鬥中出現的敵人、BOSS、NPC 單位，ID 2265 ~ 20054。
- [pets/enemies-3.md](pets/enemies-3.md) — 怪物 / NPC 戰鬥單位（3）：Monster 表 petType=100：戰鬥中出現的敵人、BOSS、NPC 單位，ID 20055 ~ 24247。
- [pets/levels.md](pets/levels.md) — 等級經驗表：Exp：角色升到下一級所需經驗；MonsterExp：該等級怪物給的經驗基數。
- [pets/pet-sources.md](pets/pet-sources.md) — 寵物取得方式 / 強化：寵物從哪裡來：圖鑑分組來源說明、固定領取點、獻祭與強化。抽獎蛋見 economy/lottery.md。
- [pets/ride.md](pets/ride.md) — 騎乘（Ride）：可騎乘寵物清單。needlearn=1 代表要先在 NPC 學騎乘（NpcScript func=studyRideLevel）。
- [pets/type-00.md](pets/type-00.md) — 寵物：烏力系（petType=0）：同一系別的寵物 / 怪物。成長參數 growArg：初始值 initArg、每級基數 levelUpArg、體腕耐速檔數（總檔越高越強）。
- [pets/type-01.md](pets/type-01.md) — 寵物：布伊系（petType=1）：同一系別的寵物 / 怪物。成長參數 growArg：初始值 initArg、每級基數 levelUpArg、體腕耐速檔數（總檔越高越強）。
- [pets/type-02.md](pets/type-02.md) — 寵物：特洛昆系（petType=2）：同一系別的寵物 / 怪物。成長參數 growArg：初始值 initArg、每級基數 levelUpArg、體腕耐速檔數（總檔越高越強）。
- [pets/type-03.md](pets/type-03.md) — 寵物：兔子系（petType=3）：同一系別的寵物 / 怪物。成長參數 growArg：初始值 initArg、每級基數 levelUpArg、體腕耐速檔數（總檔越高越強）。
- [pets/type-04.md](pets/type-04.md) — 寵物：凱比系（petType=4）：同一系別的寵物 / 怪物。成長參數 growArg：初始值 initArg、每級基數 levelUpArg、體腕耐速檔數（總檔越高越強）。
- [pets/type-05.md](pets/type-05.md) — 寵物：布克系（petType=5）：同一系別的寵物 / 怪物。成長參數 growArg：初始值 initArg、每級基數 levelUpArg、體腕耐速檔數（總檔越高越強）。
- [pets/type-06.md](pets/type-06.md) — 寵物：加美系（petType=6）：同一系別的寵物 / 怪物。成長參數 growArg：初始值 initArg、每級基數 levelUpArg、體腕耐速檔數（總檔越高越強）。
- [pets/type-07.md](pets/type-07.md) — 寵物：烏寶寶系（petType=7）：同一系別的寵物 / 怪物。成長參數 growArg：初始值 initArg、每級基數 levelUpArg、體腕耐速檔數（總檔越高越強）。
- [pets/type-08.md](pets/type-08.md) — 寵物：飛天蛙系（petType=8）：同一系別的寵物 / 怪物。成長參數 growArg：初始值 initArg、每級基數 levelUpArg、體腕耐速檔數（總檔越高越強）。
- [pets/type-09.md](pets/type-09.md) — 寵物：飛龍系（petType=9）：同一系別的寵物 / 怪物。成長參數 growArg：初始值 initArg、每級基數 levelUpArg、體腕耐速檔數（總檔越高越強）。
- [pets/type-10.md](pets/type-10.md) — 寵物：大舌頭系（petType=10）：同一系別的寵物 / 怪物。成長參數 growArg：初始值 initArg、每級基數 levelUpArg、體腕耐速檔數（總檔越高越強）。
- [pets/type-11.md](pets/type-11.md) — 寵物：烏龜系（petType=11）：同一系別的寵物 / 怪物。成長參數 growArg：初始值 initArg、每級基數 levelUpArg、體腕耐速檔數（總檔越高越強）。
- [pets/type-12.md](pets/type-12.md) — 寵物：鯊魚系（petType=12）：同一系別的寵物 / 怪物。成長參數 growArg：初始值 initArg、每級基數 levelUpArg、體腕耐速檔數（總檔越高越強）。
- [pets/type-120.md](pets/type-120.md) — 寵物：類型120（petType=120）：同一系別的寵物 / 怪物。成長參數 growArg：初始值 initArg、每級基數 levelUpArg、體腕耐速檔數（總檔越高越強）。
- [pets/type-13.md](pets/type-13.md) — 寵物：海主人系（petType=13）：同一系別的寵物 / 怪物。成長參數 growArg：初始值 initArg、每級基數 levelUpArg、體腕耐速檔數（總檔越高越強）。
- [pets/type-14.md](pets/type-14.md) — 寵物：魚龍系（petType=14）：同一系別的寵物 / 怪物。成長參數 growArg：初始值 initArg、每級基數 levelUpArg、體腕耐速檔數（總檔越高越強）。
- [pets/type-15.md](pets/type-15.md) — 寵物：呼拔拔系（petType=15）：同一系別的寵物 / 怪物。成長參數 growArg：初始值 initArg、每級基數 levelUpArg、體腕耐速檔數（總檔越高越強）。
- [pets/type-16.md](pets/type-16.md) — 寵物：人龍系（petType=16）：同一系別的寵物 / 怪物。成長參數 growArg：初始值 initArg、每級基數 levelUpArg、體腕耐速檔數（總檔越高越強）。
- [pets/type-17.md](pets/type-17.md) — 寵物：犀牛系（petType=17）：同一系別的寵物 / 怪物。成長參數 growArg：初始值 initArg、每級基數 levelUpArg、體腕耐速檔數（總檔越高越強）。
- [pets/type-18.md](pets/type-18.md) — 寵物：雷龍系（petType=18）：同一系別的寵物 / 怪物。成長參數 growArg：初始值 initArg、每級基數 levelUpArg、體腕耐速檔數（總檔越高越強）。
- [pets/type-19.md](pets/type-19.md) — 寵物：暴龍系（petType=19）：同一系別的寵物 / 怪物。成長參數 growArg：初始值 initArg、每級基數 levelUpArg、體腕耐速檔數（總檔越高越強）。
- [pets/type-20.md](pets/type-20.md) — 寵物：洛克斯系（petType=20）：同一系別的寵物 / 怪物。成長參數 growArg：初始值 initArg、每級基數 levelUpArg、體腕耐速檔數（總檔越高越強）。
- [pets/type-21.md](pets/type-21.md) — 寵物：猩猩系（petType=21）：同一系別的寵物 / 怪物。成長參數 growArg：初始值 initArg、每級基數 levelUpArg、體腕耐速檔數（總檔越高越強）。
- [pets/type-22.md](pets/type-22.md) — 寵物：茄子系（petType=22）：同一系別的寵物 / 怪物。成長參數 growArg：初始值 initArg、每級基數 levelUpArg、體腕耐速檔數（總檔越高越強）。
- [pets/type-23.md](pets/type-23.md) — 寵物：老虎系（petType=23）：同一系別的寵物 / 怪物。成長參數 growArg：初始值 initArg、每級基數 levelUpArg、體腕耐速檔數（總檔越高越強）。
- [pets/type-24.md](pets/type-24.md) — 寵物：大象系（petType=24）：同一系別的寵物 / 怪物。成長參數 growArg：初始值 initArg、每級基數 levelUpArg、體腕耐速檔數（總檔越高越強）。
- [pets/type-25.md](pets/type-25.md) — 寵物：火雞系（petType=25）：同一系別的寵物 / 怪物。成長參數 growArg：初始值 initArg、每級基數 levelUpArg、體腕耐速檔數（總檔越高越強）。
- [pets/type-26.md](pets/type-26.md) — 寵物：羚羊系（petType=26）：同一系別的寵物 / 怪物。成長參數 growArg：初始值 initArg、每級基數 levelUpArg、體腕耐速檔數（總檔越高越強）。
- [pets/type-27.md](pets/type-27.md) — 寵物：穿山甲系（petType=27）：同一系別的寵物 / 怪物。成長參數 growArg：初始值 initArg、每級基數 levelUpArg、體腕耐速檔數（總檔越高越強）。
- [pets/type-28.md](pets/type-28.md) — 寵物：融合系（petType=28）：同一系別的寵物 / 怪物。成長參數 growArg：初始值 initArg、每級基數 levelUpArg、體腕耐速檔數（總檔越高越強）。
- [pets/type-other.md](pets/type-other.md) — 寵物：未分類（petType=-1）：同一系別的寵物 / 怪物。成長參數 growArg：初始值 initArg、每級基數 levelUpArg、體腕耐速檔數（總檔越高越強）。
- [quests/README.md](quests/README.md) — 任務總覽
- [quests/answers.md](quests/answers.md) — 答題題庫（Answer）：伺服器觸發的答題（含「防腳本驗證」）。選項是圖片（answerInfo.img），客戶端看不到正解。出現答題視窗時須由人類處理或謹慎作答。
- [quests/guides.md](quests/guides.md) — 任務攻略說明（TaskExplan）：主要任務鏈的攻略說明（成人儀式、轉生等）。
- [quests/npc-scripts-1.md](quests/npc-scripts-1.md) — NPC 腳本 / 對話（1000 ~ 3137）：NpcScript：NPC 點下去的功能（接任務、戰鬥、傳送、合成…）與對話內容。func 對照見 quests/README.md。
- [quests/npc-scripts-2.md](quests/npc-scripts-2.md) — NPC 腳本 / 對話（3138 ~ 3487）：NpcScript：NPC 點下去的功能（接任務、戰鬥、傳送、合成…）與對話內容。func 對照見 quests/README.md。
- [quests/npc-scripts-3.md](quests/npc-scripts-3.md) — NPC 腳本 / 對話（3488 ~ 1000067）：NpcScript：NPC 點下去的功能（接任務、戰鬥、傳送、合成…）與對話內容。func 對照見 quests/README.md。
- [quests/npc-scripts-4.md](quests/npc-scripts-4.md) — NPC 腳本 / 對話（1000068 ~ 999999999）：NpcScript：NPC 點下去的功能（接任務、戰鬥、傳送、合成…）與對話內容。func 對照見 quests/README.md。
- [quests/tasks.md](quests/tasks.md) — 任務鏈（Task）：Task 表 373 步，依任務組(group)與步驟排列。類型：1=主線、2=支線、3=引導、4=每日、5=副本、6=突襲、7=職業/轉生、8=新手、9=家族任務1、10=家族任務2、11=家族任務3。
- [skills/README.md](skills/README.md) — 技能總覽
- [skills/battle-skills.md](skills/battle-skills.md) — 戰鬥技能（SkillBattle）：SkillBattle ID = skillId×1000 + 等級；Skill 表（ID = skillId）存類型、是否被動、目標。普通攻擊 / 防禦 / 逃跑等也在此表。
- [skills/role-buffs.md](skills/role-buffs.md) — 角色 Buff（RoleBuff，地圖上的增益）：例如月神守護（降低遇敵率）、經驗加成等，透過道具或 NPC 取得。
- [skills/skill-attr.md](skills/skill-attr.md) — 技能屬性加成（SkillAttr）：被動技能 / 光環等提供的屬性加成。
- [skills/skill-teachers.md](skills/skill-teachers.md) — 技能學習 NPC：從 Npc.npcArgs 的 skillId 整理：哪個 NPC 教哪個技能（多半是寵物技能店）。
- [skills/status-effects.md](skills/status-effects.md) — 戰鬥狀態 / Buff（SkillStatus）：戰鬥中身上狀態。錄影 / 記憶體中的 buff 以 type×1000+level 對應本表 ID。異常狀態：毒、麻痺、睡眠、石化、酒醉、混亂、暈眩。
- [text/README.md](text/README.md) — 遊戲文字總覽
- [text/strings-1.md](text/strings-1.md) — 遊戲文字（500 ~ 34550）：語言表 NewLanguage / NewLanguagePublic：介面文字、系統訊息、提示。用來對照畫面上的韓文 / 中文訊息。
- [text/strings-2.md](text/strings-2.md) — 遊戲文字（34604 ~ 80036）：語言表 NewLanguage / NewLanguagePublic：介面文字、系統訊息、提示。用來對照畫面上的韓文 / 中文訊息。
- [text/strings-3.md](text/strings-3.md) — 遊戲文字（80037 ~ 200000082）：語言表 NewLanguage / NewLanguagePublic：介面文字、系統訊息、提示。用來對照畫面上的韓文 / 中文訊息。
- [text/strings-4.md](text/strings-4.md) — 遊戲文字（200000083 ~ 70000000082）：語言表 NewLanguage / NewLanguagePublic：介面文字、系統訊息、提示。用來對照畫面上的韓文 / 中文訊息。
- [text/strings-5.md](text/strings-5.md) — 遊戲文字（70000000083 ~ 91000020014）：語言表 NewLanguage / NewLanguagePublic：介面文字、系統訊息、提示。用來對照畫面上的韓文 / 中文訊息。
- [world/README.md](world/README.md) — 世界：地圖 / NPC / 傳送總覽：地圖 1467 張、NPC 3973 個、出口 5003 個。
- [world/maps.md](world/maps.md) — 地圖一覽：MapName + mapdata 合併。名稱後有 * 表示設定表沒有名稱、用地圖檔頭的範本名（可能不準）。通行格在 data/maps.bin（用 tools/query/psa.py grid/route 查）。
- [world/npcs-01.md](world/npcs-01.md) — NPC（地圖 40 ~ 1000）：依地圖分組列出 NPC：位置、販售、教技能、功能腳本、交通路線、預設對話。
- [world/npcs-02.md](world/npcs-02.md) — NPC（地圖 1001 ~ 2006）：依地圖分組列出 NPC：位置、販售、教技能、功能腳本、交通路線、預設對話。
- [world/npcs-03.md](world/npcs-03.md) — NPC（地圖 2009 ~ 3403）：依地圖分組列出 NPC：位置、販售、教技能、功能腳本、交通路線、預設對話。
- [world/npcs-04.md](world/npcs-04.md) — NPC（地圖 3404 ~ 7001）：依地圖分組列出 NPC：位置、販售、教技能、功能腳本、交通路線、預設對話。
- [world/npcs-05.md](world/npcs-05.md) — NPC（地圖 7002 ~ 7300）：依地圖分組列出 NPC：位置、販售、教技能、功能腳本、交通路線、預設對話。
- [world/npcs-06.md](world/npcs-06.md) — NPC（地圖 7301 ~ 9031）：依地圖分組列出 NPC：位置、販售、教技能、功能腳本、交通路線、預設對話。
- [world/npcs-07.md](world/npcs-07.md) — NPC（地圖 9032 ~ 31701）：依地圖分組列出 NPC：位置、販售、教技能、功能腳本、交通路線、預設對話。
- [world/npcs-08.md](world/npcs-08.md) — NPC（地圖 31702 ~ 82021）：依地圖分組列出 NPC：位置、販售、教技能、功能腳本、交通路線、預設對話。
- [world/transport.md](world/transport.md) — 交通 / 傳送服務 / 莊園 / 挖寶：除了地圖出口以外的移動方式。
- [world/warps.md](world/warps.md) — 地圖出口 / 傳送點（MapWarp）：依出發地圖分組：站在 (x,y) 會被傳送到目的地圖座標。共 4998 個。跨地圖路線可用 tools/query/psa.py route。
