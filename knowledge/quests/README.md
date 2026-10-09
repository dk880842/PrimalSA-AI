# 任務總覽

- [guides.md](guides.md) 主要任務攻略說明
- [tasks.md](tasks.md) 全部任務鏈：接取 / 回報 NPC 位置、條件、獎勵、導航終點
- [answers.md](answers.md) 答題題庫（防腳本驗證）
- NPC 腳本 / 對話：

| 檔案 | 腳本 ID |
|---|---|
| [npc-scripts-1.md](npc-scripts-1.md) | 1000 ~ 3137 |
| [npc-scripts-2.md](npc-scripts-2.md) | 3138 ~ 3487 |
| [npc-scripts-3.md](npc-scripts-3.md) | 3488 ~ 1000067 |
| [npc-scripts-4.md](npc-scripts-4.md) | 1000068 ~ 999999999 |

## 腳本功能（NpcScript.script.func）

| func | 意義 |
|---|---|
| NpcAnwser | 問答 |
| addBeautyBuff | 加魅力 Buff |
| addLuckBuff | 加運氣 Buff |
| enterDungeo | 進入副本 |
| farJoinTeam | 遠端組隊 |
| fightBattle | 戰鬥 |
| itemPetCompose | 道具/寵物合成 |
| itemShopSell | 道具收購 |
| itemUp | 道具強化 |
| joinAirPlan | 搭乘飛行/交通 |
| kangxingCheck | 抗性檢查 |
| killPet | 寵物獻祭 |
| newItemMake | 道具製作 |
| npcFightTimesGet | 限次戰鬥 |
| npcTimesGet | 限次領取 |
| openItemDepot | 道具倉庫 |
| openPetDepot | 寵物倉庫 |
| petFusion | 寵物融合 |
| petRecycle | 寵物回收 |
| petTransBeforeInfo | 寵物轉生資訊 |
| pickupPetNpc | 領寵 |
| pkSystem | PK 系統 |
| reserveHpMp | 補血補氣 |
| savePoint | 記錄點 |
| studyPetSkill | 學寵物技能 |
| studyRideLevel | 學騎乘 |
| swapSpiritStone | 交換精靈石 |
| taskAccept | 接任務 |
| taskBattle | 任務戰鬥 |
| taskFinish | 任務完成 |
| transferRole | 傳送 |
| transmigraPet | 寵物轉生 |
| watchVideos | 看錄影 |

任務狀態（TaskStatus）：-1 等待、0 無、1 已接、2 完成、3 放棄。任務類型（TaskType）：1 對話、2 打怪、3 巡邏、4 戰鬥、5 任務道具、6 道具、7 寵物、8 使用道具、9 答題、12 代碼。
