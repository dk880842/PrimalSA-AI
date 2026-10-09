# 遊戲常數（Config 表）

> Config 表唯一一列：伺服器 / 客戶端共用的遊戲常數。

| 欄位 | 說明 | 值 |
|---|---|---|
| battleSpeed | 戰鬥速度倍率 | 1.5 |
| normalSpeed | 一般移動速度倍率 | 1.3 |
| emojiList |  | ["<sprite name=emoji_0>", "<sprite name=emoji_1>", "<sprite name=emoji_2>", "<sprite name=emoji_3>", "<sprite name=emoji_4>", "<sprite name=emoji_5>", "<sprite name=emoji_6>", "<sprite name=emoji_7>", "<sprite name=emoji_8>", "<sprite name=emoji_9>", "<sprite name=emoji_10>", "<sprite name=emoji_11>… |
| maxRole | 最多角色數 | 5 |
| initRoleNum | 初始角色欄 | 5 |
| openRoleCost |  | [0, 0, 0, 50, 100, 200] |
| petSkillMax | 寵物技能欄上限 | 7 |
| maxItemPlace | 背包頁數上限 | 15 |
| initItemPlace | 初始背包格 | 15 |
| unlockBag |  | [{"num": 1, "price": 1000}, {"num": 1, "price": 1000}, {"num": 1, "price": 1000}, {"num": 1, "price": 1000}, {"num": 1, "price": 1000}] |
| guildCreateNeed | 建立家族費用 | {"currencyType": 3, "currencyValue": 300000} |
| guildShowPerPage |  | 6 |
| eatSpriteStonePet |  | [1479, 2545, 2547] |
| petMaxLevel | 寵物等級上限 | [140, 140, 140] |
| perCritAgile |  | 0.0 |
| perDodgeAgile |  | 0.0 |
| perHitAgile |  | 0.0 |
| maxItemDepotPlace | 道具倉庫頁上限 | 5 |
| perItemDepotNum | 每頁倉庫格數 | 20 |
| unlockItemDepotPrice |  | 100 |
| maxPetDepotPlace | 寵物倉庫頁上限 | 5 |
| perPetDepotNum |  | 20 |
| unlockPetDepotPrice |  | 100 |
| manorFightMap |  | [{"manorId": 1, "map": 1042, "x": 16, "y": 26, "outmap": 1040, "outx": 46, "cdkeySameNum": 5, "outy": 26}, {"manorId": 2, "map": 2032, "x": 5, "y": 15, "outmap": 2030, "outx": 50, "cdkeySameNum": 2, "outy": 50}, {"manorId": 3, "map": 3032, "x": 5, "y": 15, "outmap": 3030, "outx": 37, "cdkeySameNum":… |
| nameFirst |  | ["赵", "钱", "孙", "李", "周", "吴", "郑", "王", "冯", "陈", "褚", "卫", "蒋", "沈", "韩", "杨", "朱", "秦", "许", "何", "吕", "施", "张", "孔", "牛", "严", "华", "金", "魏", "陶", "姜", "戚", "谢", "邹", "喻", "柏", "水", "窦", "章", "云", "苏", "潘", "葛", "奚", "范", "彭", "郎", "鲁", "韦", "昌", "马", "苗", "凤", "花", "方", "傅", "韩", "唐", "白", "康",… |
| nameLast |  | ["明志", "伟豪", "杰熊", "雄俊", "熊彬", "豪泽", "波胜", "勇斌", "钢龙", "宇杰", "剑雄", "然浩", "俊杰", "辰辉", "旭威", "妮雅", "美婷", "雨洁", "倩敏", "婷嫣", "玉莹", "花容", "霞婷", "菲菲", "宝姿", "慧娟", "雪婷", "琪琪", "娟娟", "美娥", "明", "伟", "杰", "雄", "熊", "豪", "波", "勇", "钢", "宇", "剑", "然", "俊", "辰", "旭", "妮", "美", "雨", "倩", "婷", "玉", "花", "霞", "菲",… |
| nameFirstTw |  | ["趙", "錢", "孫", "李", "周", "吳", "鄭", "王", "馮", "陳", "褚", "衛", "蔣", "沈", "韓", "楊", "朱", "秦", "許", "何", "呂", "施", "張", "孔", "牛", "嚴", "華", "金", "魏", "陶", "薑", "戚", "謝", "鄒", "喻", "柏", "水", "竇", "章", "雲", "蘇", "潘", "葛", "奚", "範", "彭", "郎", "魯", "韋", "昌", "馬", "苗", "鳳", "花", "方", "傅", "韓", "唐", "白", "康",… |
| nameLastTw |  | ["明志", "偉豪", "傑熊", "雄俊", "熊彬", "豪澤", "波勝", "勇斌", "鋼龍", "宇傑", "劍雄", "然浩", "俊傑", "辰輝", "旭威", "妮雅", "美婷", "雨潔", "倩敏", "婷嫣", "玉瑩", "花容", "霞婷", "菲菲", "寶姿", "慧娟", "雪婷", "琪琪", "娟娟", "美娥", "明", "偉", "傑", "雄", "熊", "豪", "波", "勇", "鋼", "宇", "劍", "然", "俊", "辰", "旭", "妮", "美", "雨", "倩", "婷", "玉", "花", "霞", "菲",… |
| pickupPet |  | 300020 |
| pickupPetTip |  | 600008 |
| chatColors |  | ["white", "FF3333", "FFAB28", "FFF000", "_51FF51", "_29FFF7", "_3EA6FF", "DB5DFF"] |
| initWeight | 初始負重 | 9999 |
| eggEatCount | 吃蛋次數上限 | 40 |
| firstRechargeItem |  | [{"itemId": 92153, "itemNum": 5}, {"itemId": 90816, "itemNum": 1}, {"itemId": 90335, "itemNum": 1}, {"itemId": 90639, "itemNum": 2}] |
| autoPlayOverTimeout |  | 3 |
| AutoCountTime |  | 1 |
| banReHeating |  | [101444, 101445, 101446, 101447, 101452, 101453, 101454, 101455, 101456, 101457, 101458, 101459, 101460, 101461, 101462, 101463, 101467, 101465, 101466, 101464, 101468, 101469, 101470, 101471, 101472, 101473, 101474, 101475, 101476, 101477, 101478, 101479, 101480, 101481, 101482, 101483, 101484, 101… |
| checkRate |  | [5, 10, 10, 10] |
| reHeatFiveDiscount |  | 0.8 |
| reHeatTenDiscount |  | 0.7 |
| itemRecycleList |  | ["70091-70145", "70176-70185", "70187-70196", "70198-70217", "70219-70223", "70226-70230", "70232-70236", "70244-70248", "70250-70254", "70256-70260", "70262-70266", "70268-70272", "70274-70278", "70392-70441"] |
| itemRecycleScNum |  | 1054 |
| itemRecycleLReward |  | 70512 |
| baseExp | 基礎經驗倍率 | 3 |
| weekExp |  | 3 |
| metamoHbNum |  | [0, 80, 0] |
| P_maxItemDepotPlace |  | 99 |
| P_perItemDepotNum |  | 20 |
| P_unlockItemDepotPrice |  | 200 |
| P_maxPetDepotPlace |  | 20 |
| P_perPetDepotNum |  | 20 |
| P_unlockPetDepotPrice |  | 200 |
| fullAttrDenar |  | [100, 200, 400, 800] |
| fullAttrLockDenar |  | [1000, 2000, 4000, 8000] |
| fullArgOpen |  | 0 |
| petLevelUpFeed |  | [0, 0, 0] |
| maxActive |  | 100 |
| isTradeLimit |  | 0 |
| ridePetTranLimit |  | 1 |
| rolePointSaveCost | 保存配點方案費用 | 1000 |
| petSaveMaxCount |  | 0 |
| petSaveCost |  | 5000 |
| changeZc |  | {"petNum": 5, "currencyType": 3, "currencyValue": 20000} |
| tranItemCost |  | [{"itemNum": 1, "petNum": 200, "currencyValue": 1288}, {"itemNum": 201, "petNum": 400, "currencyValue": 2500}, {"itemNum": 401, "petNum": 600, "currencyValue": 3750}, {"itemNum": 601, "petNum": 800, "currencyValue": 5000}, {"itemNum": 801, "petNum": 1000, "currencyValue": 6250}] |
| tranPetCost |  | [{"itemNum": 1, "currencyValue": 500}, {"itemNum": 2, "currencyValue": 1000}, {"itemNum": 3, "currencyValue": 2000}, {"itemNum": 4, "currencyValue": 3500}, {"itemNum": 5, "currencyValue": 5000}, {"itemNum": 6, "currencyValue": 5000}, {"itemNum": 7, "currencyValue": 6666}] |
| randTaskCost |  | 50 |
| weekCard |  | [{"currencyType": 8, "currencyValue": 50}, {"buffId": 90008001}] |
| monthCard |  | [{"currencyType": 1, "currencyValue": 100}, {"itemId": 72361, "itemNum": 500}, {"buffId": 14}] |
| jiCard |  | [{"currencyType": 1, "currencyValue": 500}, {"itemId": 72361, "itemNum": 500}, {"buffId": 15}] |
| yearCard |  | [{"currencyType": 8, "currencyValue": 200}, {"buffId": 90009001}, {"itemId": 71460, "itemNum": 1}] |
| luckDrawExtra |  | [{"itemString": "70592#70592", "drawNum": 500}] |
| upStarPointCost |  | [{"pointa": 1, "starNum": 1, "currencyType": 1, "currencyValue": 10}, {"pointa": 2, "starNum": 1, "currencyType": 1, "currencyValue": 20}, {"pointa": 3, "starNum": 1, "currencyType": 1, "currencyValue": 50}, {"pointa": 4, "starNum": 1, "currencyType": 1, "currencyValue": 100}, {"pointa": 5, "starNum… |
| makeJpCost |  | 999999999 |
| banRecyclePet |  | [2407, 2408, 20237, 1991, 1900, 1901, 1902, 1903, 20348, 20349, 20350, 20351, 20352, 20353, 20354, 20355, 20356, 20357, 20358, 20359, 20370, 23859, 23860, 23864] |
| resetSxCost |  | [200, 0, 0] |
| btServer |  | 0 |
| petZfMaxNum |  | 10 |
| fireWall |  | 0 |
| newEmailPageNum |  | 4 |
| isTaiwanServer |  | 0 |
| studentMaxNum |  | 50 |
| afkInfo |  | [{"trans": 0, "level": 30, "value": 600}, {"trans": 0, "level": 80, "value": 600}, {"trans": 0, "level": 100, "value": 600}, {"trans": 0, "level": 110, "value": 600}, {"trans": 0, "level": 120, "value": 600}, {"trans": 1, "value": 600}, {"trans": 2, "value": 600}, {"trans": 3, "value": 600}, {"trans… |
| videosUrl |  | "https://web.idealsa.org/video/" |
| upStarExp |  | [{"itemId": 70513, "itemNum": 5, "currencyType": 8, "currencyValue": 50, "oneExp": 500, "needExp": 5000, "star": 2}, {"itemId": 70513, "itemNum": 10, "currencyType": 8, "currencyValue": 50, "oneExp": 500, "needExp": 5000, "star": 3}, {"itemId": 70513, "itemNum": 15, "currencyType": 8, "currencyValue… |
| banString |  | ["!", "#", "$", "%", "^", "&", "*", "(", ")", "#", "_", "+", "-", "+", "\\", "[", "]", "{", "}", ";", "'", ":", "\"", "<", ">", ",", ".", "/", "?", "`", "~", "@", "｝", "］", "）", "｜", "（", "）"] |
| unlockPetTransVip |  | 8 |
| yearMonthCardExtra |  | [{"itemId": 70021, "itemNum": 1}, {"itemId": 71002, "itemNum": 1}, {"itemId": 71863, "itemNum": 10}] |
| yearMonthCardExtraTime |  | 1647628875 |
| phoneCodeReg |  | 0 |
| mmBoxUnlockDenar |  | 300 |
| petBoxUnlockDenar |  | 300 |
| petBoxUnlockTime |  | 30 |
| petBoxMaxNum |  | 5 |
| mmBoxEatInfo |  | [{"itemId": 19625, "itemNum": 10, "star": 1}, {"itemId": 19626, "itemNum": 10, "star": 2}, {"itemId": 19627, "itemNum": 10, "star": 3}, {"itemId": 19628, "itemNum": 10, "star": 4}] |
| mmBoxEatTime |  | 6 |
| chrismaOpen |  | 1 |
| newShopTax |  | [5, 10, 10, 10] |
| vipSystemOpen |  | 0 |
| petUpstarOldSystem |  | 1 |
| petUpstarNewSystem |  | 1 |
| petRankOpenTwoTran |  | 0 |
| catchPetItem | 捕捉寵物道具費用 | {"currencyType": 3, "currencyValue": 100000} |
| cardTimeSystem |  | 0 |
| monthCardAfkTime |  | 0 |
| jiCardAfkTime |  | 0 |
| lcShopSystem |  | 1 |
| openUnderSuit |  | 1 |
| openBuildingTransparent |  | 1 |
| oldAhFlg |  | 0 |
| mmBoxSpeedInfo |  | {"currencyType": 8, "currencyValue": 1} |
| familyIconDiyCost |  | {"currencyType": 8, "currencyValue": 1000} |
| familyDecDiyCost |  | {"currencyType": 8, "currencyValue": 1000} |
| changeName | 改名費用 | 1000 |
| familyMaxMemberCount | 家族人數上限 | 100 |
| petReheatDiscount |  | [{"petNum": 10, "rate": 9}, {"petNum": 20, "rate": 8}, {"petNum": 30, "rate": 7}, {"petNum": 40, "rate": 6}, {"petNum": 50, "rate": 5}] |
| unloadPetZfSave |  | {"currencyType": 1, "currencyValue": 200} |
| roleFaceUpFlg |  | 1 |
| randomPkMap | 隨機 PK 地圖 | 67002 |
| newShopBoothUpItemMaxNum |  | 20 |
| newShopBoothUpPetMaxNum |  | 20 |
| newItemDepotOpen |  | 1 |
| oldItemDepotOpen |  | 0 |
| randomPkOpen |  | 1 |
| petEquipOpen |  | 1 |
| newUnlockRoleFeed |  | [{"itemNum": 4, "currencyType": 8, "currencyValue": 500}, {"itemNum": 5, "currencyType": 8, "currencyValue": 1000}, {"itemNum": 6, "currencyType": 1, "currencyValue": 5000}] |
| changeChatNameFeed |  | {"currencyType": 1, "currencyValue": 1000} |
| recycleReheatPetSnum |  | 0.6 |
| delPetCollectOneFeed |  | {"currencyType": 8, "currencyValue": 500} |
| delPetCollectAllFeed |  | {"currencyType": 8, "currencyValue": 1000} |
| openPetCollect |  | 1 |
| openNewPetDepot |  | 1 |
| openItemlevelUpBtn |  | 0 |
| sendEmailThingFee |  | {"currencyType": 3, "currencyValue": 100000} |
| rechargeGiveItem |  | 0 |
| autoEatExpItemList | 自動吃的經驗道具 | [90398, 90399, 90638, 90639] |
| autoTalkFee |  | [{"currencyType": 3, "currencyValue": 100000, "serverTime": 1}, {"currencyType": 3, "currencyValue": 50000, "serverTime": 5}, {"currencyType": 3, "currencyValue": 20000, "serverTime": 10}, {"currencyType": 3, "currencyValue": 10000, "serverTime": 20}, {"currencyType": 3, "currencyValue": 2000, "serv… |
| wtaskTimeList |  | [60, 120, 180, 360, 480, 600] |
| wtaskLowLimitValue |  | [{"currencyType": 1, "currencyValue": 100}, {"currencyType": 2, "currencyValue": 500}, {"currencyType": 3, "currencyValue": 1000000}, {"currencyType": 8, "currencyValue": 500}] |
| MMWatchSceneFlg |  | 0 |
| PVPShowEnemyRoleInfo |  | 0 |
| WatchShowEnemyRoleInfo |  | 0 |
| MMWatchOneKeyCost |  | [{"currencyType": 2, "currencyValue": 1}, {"currencyType": 3, "currencyValue": 100000}] |
| newTaskCheckFlg |  | 1 |
| newPetSkillRule |  | 1 |
| aliyunDunDomain |  | "114.132.164.233" |
| wgNormalRoleHealList |  | [10111] |
| MD5Version | 資料版本 | 20260518 |
| randomPkMap_New |  | 1005 |
| itemGemOffCost |  | {"currencyType": 2, "currencyValue": 50} |
| mustOutBattleMap | 必須脫離戰鬥的地圖 | [1005] |
| rechargeRankFlg |  | 1 |
| tileAttrMaxNum |  | 99 |
| aruaAttrMaxNum |  | 99 |
| skinAttrMaxNum |  | 99 |
| LJCardItemId |  | 92107 |
