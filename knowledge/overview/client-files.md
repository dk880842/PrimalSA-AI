# 遊戲客戶端檔案分類

> GameClient 內容分類與格式說明（供維護與進一步分析用）。

## 資料夾結構（GameClient，唯讀）
- `PrimalSA.exe`：遊戲主程式（Unity 2022.3.62f3，IL2CPP）
- `GameAssembly.dll`：IL2CPP 編譯的原生程式碼；`PrimalSA_Data/il2cpp_data/Metadata/global-metadata.dat`：IL2CPP 中繼資料
- `PrimalSA_Data/StreamingAssets/AssetBundles/`：**所有遊戲資源與設定表**（2,700+ 個 bundle）
- `PrimalSA_Data/*.assets`、`level0~2`：開機場景與內建資源
- 遊戲邏輯在熱更新組件 `HotUpdate.dll`（HybridCLR），放在 hotupdate.dll.assetbundle 裡，會隨熱更新替換。

## AssetBundle 分類
| 前綴 | 類別 | 數量 | 大小 | 內容 | 範例 |
|---|---|---|---|---|---|
| mapdata | 地圖 | 1464 | 7.4 MB | 地圖資料（LS2MAP：寬高、地面層、物件層） | mapdata_1.assetbundle、mapdata_100.assetbundle、mapdata_1000.assetbundle… |
| ui* | 介面 | 449 | 372.2 MB | UI 介面預製物（*_yhkrn = 韓版 UI），見 ui-screens.md | activelog_yhkrn.assetbundle、activepopup_yhkrn.assetbundle、chatdetailspanel_yhkrn.assetbundle… |
| char | 角色 | 358 | 100.8 MB | 角色 / 寵物 / 怪物 / NPC 影格圖（char{圖號}） | char100000.assetbundle、char1000021000.assetbundle、char1000021100.assetbundle… |
| gsound | 音效 | 206 | 2.6 MB | 音效 | gsound_1.assetbundle、gsound_10.assetbundle、gsound_100.assetbundle… |
| mapbg | 地圖 | 87 | 100.3 MB | 地圖背景大圖 | mapbg100.assetbundle、mapbg10001.assetbundle、mapbg10002.assetbundle… |
| mapbuild | 地圖 | 76 | 30.9 MB | 地圖建築 / 物件圖素 | mapbuild_0.assetbundle、mapbuild_10000.assetbundle、mapbuild_10100.assetbundle… |
| newarua | 角色 | 54 | 10.1 MB | 光環特效 | newarua_201210.assetbundle、newarua_201211.assetbundle、newarua_201212.assetbundle… |
| chardata | 角色 | 48 | 0.3 MB | 48 種基本人物的動畫表 / 位移表 | chardata100000.assetbundle、chardata100005.assetbundle、chardata100010.assetbundle… |
| chname | 角色 | 42 | 46.6 MB | 稱號 / 名稱特效 | chname_aoshi.assetbundle、chname_aoshi2.assetbundle、chname_aoshi_krn.assetbundle… |
| pe | 特效 | 32 | 4.3 MB | 粒子特效 | pe_balloonpopexplosion.assetbundle、pe_bloodexplosion2d.assetbundle、pe_blowingleaves.assetbundle… |
| itemalt | 圖示 | 28 | 3.7 MB | 道具圖示（Sprite 名 = Item.imageId） | itemalt_0.assetbundle、itemalt_100.assetbundle、itemalt_1000.assetbundle… |
| bgm | 音效 | 27 | 31.9 MB | 背景音樂 | bgm_0.assetbundle、bgm_1.assetbundle、bgm_10.assetbundle… |
| particle | 特效 | 19 | 12.0 MB | 粒子特效 | particle_0.assetbundle、particle_1.assetbundle、particle_10.assetbundle… |
| maptile | 地圖 | 17 | 7.8 MB | 地圖地面圖素 | maptile.assetbundle、maptile_0.assetbundle、maptile_1000.assetbundle… |
| roletile | 角色 | 12 | 14.2 MB | 角色動畫影格 | roletile_10.assetbundle、roletile_12.assetbundle、roletile_13.assetbundle… |
| twname | 角色 | 10 | 11.2 MB | 稱號特效 | twname_aoshi.assetbundle、twname_dandan.assetbundle、twname_fugui.assetbundle… |
| tx | 地圖 | 9 | 3.9 MB | 地圖特效 | tx_mapbg10002.assetbundle、tx_mapbg1042.assetbundle、tx_mapbg201.assetbundle… |
| npcstaticpic | 圖示 | 5 | 1.2 MB | NPC 立繪 | npcstaticpic_0.assetbundle、npcstaticpic_16000.assetbundle、npcstaticpic_16461.assetbundle… |
| particlefx | 特效 | 5 | 0.3 MB | 粒子特效 | particlefx_line_rotate_hit_a.assetbundle、particlefx_summoner_body_a.assetbundle、particlefx_summoner_box_a.assetbundle… |
| hofix | 程式/資料 | 2 | 3.0 MB | 熱更新依賴的 .NET 組件 | hofix_dll.assetbundle、hofix_dll.assetbundle1 |
| hotupdate.dll | 程式/資料 | 2 | 1.7 MB | 熱更新程式 HotUpdate.dll（遊戲邏輯，HybridCLR） | hotupdate.dll.assetbundle、hotupdate.dll.assetbundle1 |
| newtail | 角色 | 2 | 0.3 MB | 拖尾特效 | newtail_01.assetbundle、newtail_02.assetbundle |
| rolebattlebuffeffect |  | 2 | 0.0 MB |  | rolebattlebuffeffect.assetbundle、rolebattlebuffeffect2.assetbundle |
| MD |  | 1 | 0.3 MB |  | MD5 |
| app.ver |  | 1 | 0.0 MB |  | app.ver |
| battledamageheal |  | 1 | 0.0 MB |  | battledamageheal.assetbundle |
| battlejingling |  | 1 | 0.9 MB |  | battlejingling.assetbundle |
| battlemagiceffect | 特效 | 1 | 0.0 MB | 戰鬥魔法特效 | battlemagiceffect.assetbundle |
| battleroleuimgr |  | 1 | 0.0 MB |  | battleroleuimgr.assetbundle |
| battleweapon |  | 1 | 0.0 MB |  | battleweapon.assetbundle |
| chaticon | 圖示 | 1 | 0.1 MB | 聊天圖示 | chaticon.assetbundle |
| configs | 程式/資料 | 1 | 1.0 MB | **全部設定表**（Tabtoy 二進位，TextAsset `Configs`） | configs.assetbundle |
| crit |  | 1 | 0.0 MB |  | crit_attack.assetbundle |
| datepicker - date range |  | 1 | 0.7 MB |  | datepicker - date range.assetbundle |
| emojiicon | 圖示 | 1 | 0.1 MB | 聊天表情 | emojiicon.assetbundle |
| enchantmenteffect |  | 1 | 0.7 MB |  | enchantmenteffect.assetbundle |
| foldreusescrollview |  | 1 | 0.0 MB |  | foldreusescrollview.assetbundle |
| fontskorean | 介面 | 1 | 31.0 MB | 韓文字型 | fontskorean.assetbundle |
| gameframe |  | 1 | 0.0 MB |  | gameframe.assetbundle |
| gameuimanager |  | 1 | 0.0 MB |  | gameuimanager.assetbundle |
| hudmanager |  | 1 | 0.0 MB |  | hudmanager.assetbundle |
| hudnpctalk |  | 1 | 0.0 MB |  | hudnpctalk.assetbundle |
| hudrolename |  | 1 | 0.0 MB |  | hudrolename.assetbundle |
| hudrolestatus |  | 1 | 0.0 MB |  | hudrolestatus.assetbundle |
| hudroletalk |  | 1 | 0.0 MB |  | hudroletalk.assetbundle |
| hudtaskstatus |  | 1 | 0.0 MB |  | hudtaskstatus.assetbundle |
| itemaltlist | 圖示 | 1 | 0.0 MB | imageId 範圍 → itemalt bundle 對照 | itemaltlist.assetbundle |
| itemtypeicon | 圖示 | 1 | 0.0 MB | 道具類型圖示 | itemtypeicon.assetbundle |
| loadimportantfunc |  | 1 | 0.0 MB |  | loadimportantfunc.assetbundle |
| lotterysound | 音效 | 1 | 0.3 MB | 抽獎音效 | lotterysound.assetbundle |
| mapbuilding | 地圖 | 1 | 0.0 MB | 地圖建築預製物 | mapbuilding.assetbundle |
| newbattledamageheal |  | 1 | 0.0 MB |  | newbattledamageheal.assetbundle |
| numbericon | 圖示 | 1 | 0.0 MB | 數字圖 | numbericon.assetbundle |
| outlineauradi |  | 1 | 0.0 MB |  | outlineauradi.assetbundle |
| outlineaurafeng |  | 1 | 0.0 MB |  | outlineaurafeng.assetbundle |
| outlineaurahei |  | 1 | 0.0 MB |  | outlineaurahei.assetbundle |
| outlineaurahuo |  | 1 | 0.0 MB |  | outlineaurahuo.assetbundle |
| outlineaurashui |  | 1 | 0.0 MB |  | outlineaurashui.assetbundle |
| particlesnow |  | 1 | 0.0 MB |  | particlesnow.assetbundle |
| petgroupicon | 圖示 | 1 | 0.1 MB | 寵物系別圖示 | petgroupicon.assetbundle |
| petstaticpic | 圖示 | 1 | 4.2 MB | 寵物立繪 | petstaticpic.assetbundle |
| randombadgedata | 程式/資料 | 1 | 0.0 MB | 隨機徽章像素資料 | randombadgedata.assetbundle |
| reusescrollview |  | 1 | 0.0 MB |  | reusescrollview.assetbundle |
| rolebattle | 角色 | 1 | 0.9 MB | 戰鬥中的角色預製物 | rolebattle.assetbundle |
| rolebattlearuaeffect |  | 1 | 0.0 MB |  | rolebattlearuaeffect.assetbundle |
| rolebattlebf |  | 1 | 0.9 MB |  | rolebattlebf.assetbundle |
| rolenormal | 角色 | 1 | 0.0 MB | 地圖上的角色預製物 | rolenormal.assetbundle |
| rolenormalui |  | 1 | 0.0 MB |  | rolenormalui.assetbundle |
| roleuimgr |  | 1 | 0.2 MB |  | roleuimgr.assetbundle |
| rolewarp |  | 1 | 0.1 MB |  | rolewarp.assetbundle |
| skillicon | 圖示 | 1 | 1.4 MB | 技能圖示 | skillicon.assetbundle |
| soulexplosiongreen |  | 1 | 0.3 MB |  | soulexplosiongreen.assetbundle |
| spritemask |  | 1 | 0.0 MB |  | spritemask.assetbundle |
| synsound | 音效 | 1 | 0.0 MB | 合成音效 | synsound.assetbundle |
| updateui |  | 1 | 1.1 MB |  | updateui.assetbundle |
| warp | 地圖 | 1 | 0.1 MB | 傳送點特效 | warp.assetbundle |
| warppoint | 地圖 | 1 | 0.0 MB | 傳送點 | warppoint.assetbundle |
| warppointpub | 地圖 | 1 | 0.1 MB | 傳送點(公用) | warppointpub.assetbundle |
| weathersystem | 地圖 | 1 | 0.0 MB | 天氣系統 | weathersystem.assetbundle |

## 檔案格式（逆向結果）
- **Bundle 混淆**：檔頭前塞了約 330 bytes 假資料（含多個 `UnityFS` 簽章）；真正 bundle = 前 1024 bytes 內**最後一個** `UnityFS` 起算。資料區塊 LZMA、block info LZ4。
- **configs.assetbundle** → TextAsset `Configs`，Tabtoy v3 二進位（`TABTOY` 檔頭；tag=(型別<<16)|欄位索引；型別 1 int32、2 int64、5 float、6 string、7 bool、8 enum、9 struct、10 表列）。
  表名 / 欄位名來自 HotUpdate.dll 的 `Data.*Define.Deserialize()`，由 tools/schemadump 產生 `data/schema.tsv`。
- **mapdata_{地圖ID}** → TextAsset `LS2MAP`（大端序：名稱 GBK、寬、高、地面層 uint16[]、物件層 uint16[]）；圖素編號對 MapOffset 表的 walkable。地圖 ID 以檔名為準。
- **itemalt_\*** Sprite 名 = Item.imageId；**headicon\*** Sprite 名 = Monster.imageId；**char{圖號}** 角色影格。
- 文字有三語：`*Cn` 簡中、`*Tn` 繁中、`*Kr/*Krn` 韓文。本知識庫以繁中為主、附韓文（韓版客戶端畫面可能顯示韓文）。
