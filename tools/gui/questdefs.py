#!/usr/bin/env python3
"""1.82 任務系列資料表（questrun.py 用；計畫 notes/plan-182-script.md §2.3）。只用標準函式庫。

一任務一筆 dict：
  id          任務組 ID（Task / TaskExplan 的 ID）
  detail      任務詳情列表的標題（TaskExplan.nameTn，1.82 任務有「(1.82)」後綴）
  track       追蹤列表的標題（= Task 表 name，沒有「(1.82)」後綴；quest.py --task 用）
  accept_npc  接取任務的 NPC（只給 plan 顯示；實際由 questdetail.accept 用「傳送」直達）
  steps_total 步數（test_questdefs 與 Task.jsonl 核對）
  steps       {步號: dict(kind=...)}；沒列的步驟 = 預設（quest.py 預設模式：點追蹤 → 巡路 → 對話 → 戰鬥）
              kind：walk（備援：預設先讓遊戲自動巡路，quest.py 回 3 = 原地不動才用 walk.py 走到 map / xy；handler 在 questhandlers.py）
                    manual（停下交人，退出碼 115）
                    fight（BOSS 步不巡路：全隊 HP 檢查〔門檻 hp_min，低就補血〕→ 不在 map / xy 附近就便捷傳送 warp=(分頁內座標) / warp_name
                           → team.form → quest.py --fight --task 追蹤標題 --step N；贏 + 滿 5 人 = 37、不滿 = 38（bossretry）、輸 35 → 補血重打 1 次；紅暴步 6）
  bag_slots   開始前每人背包至少要有幾格空位（0 = 不檢查）。2026-10-13 起 >= bag_need(id)（Task 表各步獎勵道具、扣掉交出去的條件道具，
              同時佔用的最多格數；強盜的洞穴 = 衣服 / 斧頭 / 頭盔 / 足跡 4 格 —— 當天頭盔因背包滿進了信箱）；test_questdefs 核對。
              questrun preflight 不足 → 先自動刪 bag.AUTO_PURGE 白名單道具，仍不足才 110
  boss        True = 有任務戰 / BOSS 戰（quest.py 預設模式打完回 37 / 38；P2 只收資料，不實跑）
  est_min     預估分鐘（quest-log 0 轉 123 級 5 人隊實跑）
  live        P2 實機驗證過：True；只有資料沒實跑：False
  note        坑 / 提醒
  turnin      （選填）交寵物步驟：dict(kind=pet_turnin 的種類, steps={任務步號: (pet_turnin 步…)})；questrun --pet-turnin 時 manual 步改跑 pet_turnin 5 人逐人交
  rest_pets   （選填）True = 交寵物前任務寵要先「等待」：questrun --pet-turnin 時接取後第一片前 pet.py rest-all
  reward_pets （選填）任務獎勵寵物名（只給 plan 顯示；要丟由使用者下 --drop-reward / --confirm-drop，questrun 只丟 1 級）
  stop_after_rewards（選填）每片 quest.py 加 --stop-after-rewards N：每步領完獎就收片（下一片前 questrun 讀步號，好在 fight 步之前停下補血 / 傳送）
  dragon_required（選填）True = 這任務一定要有龍王的守護 buff 才組隊跑（不看 --dragon）：開始前沒 buff 就吃；背包 / 公共倉庫都沒有 → 156（改走單人逃跑 psa-quest-solo）
  min_level   （選填）5 人等級下限（bag.read_level；任一人不到 / 讀不到 → 110）
  post        （選填）任務完成後自動處理獎勵（questrun --no-post 關）：store_personal=[道具…] 5 人存個人倉庫、store_public=[道具…] 5 人存公共倉庫、
              pets_personal=[寵物…] 5 人存個人寵物倉庫（使用者 2026-10-13：英雄的祝福存個人、龍王剩的 / 人龍隨機蛋存公共、摩娜西普存個人）
  drop_items  （選填）可丟的獎勵道具（只給 plan 顯示；要丟由使用者下 --drop-items / --confirm-drop-items，questrun 用 bag.purge 只刪名單內、背包內的，穿著的不動）
  hp_every    （選填）片內全隊 HP 每幾場一般戰鬥讀一次（quest.py --hp-check-every；沒填 = questrun --hp-check-every 預設 3）；連戰任務填 1
  walk_s      （自動）2026-10-13 二轉後實跑 quest.py 自報的巡路秒數合計（WALK_S；沒量到 = None）
  dragon      （自動）不在 NO_DRAGON 才 True：questrun --dragon 對這些任務吃龍王的守護（buff 還在就跳過）
              （使用者 2026-10-13 定：除了 彌生和日美子 / 猜謎三兄弟 / 恐龍博士 / 卡坦的願望 之外全部都吃；
               review §3.2 曾改成只吃長巡路，使用者否決。walk_s 仍保留供參考）
前置依賴：prereqs(id) 讀 Task 表第 1 步的 finishTasks（1.82 全部要先完成成人儀式 2999）；questrun 逐人驗證延後時，依賴任務接取前先批次驗
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))
import clients  # noqa: E402


def roster_at(i: int) -> str:
    """這個視窗（PSA_CLIENT）名單第 i 個（0 起算；主視窗 0 = DKBO、1 = DKBO2…；PrimalSA2 1 = DKBO7）；
    名單不夠長 → '#i+1'（不是真名，用到的腳本 preflight 會擋）。交寵物任務的抓寵分配用卡位，不寫死名字"""
    r = clients.roster()
    return r[i] if i < len(r) else f'#{i + 1}'


def _assign(*pairs) -> str:
    """抓寵分配字串 '角色:系別:物種,…'：pairs = (卡位, 系別, 物種)，卡位經 roster_at 轉這個視窗的名字"""
    return ','.join(f'{roster_at(i)}:{fam}:{sp}' for i, fam, sp in pairs)

Q182 = [
    dict(id=2999, detail='成人儀式', track='成人儀式', accept_npc='儀式的審判 10204:14,6', steps_total=2,
         steps={1: dict(kind='walk', map=10204, xy=(188, 13), npc='儀式審判的差使')},
         bag_slots=1, boss=False, est_min=7, live=True,
         note='1.82 全部任務的前置。步 1（去差使拿儀的玉×15）2026-10-11 實測點追蹤會傳送進 10204 並自動巡路（10-09 從 14,6 原地點才不動）→ walk 只當備援；步 2 點追蹤自動巡路回儀式的審判'),
    dict(id=2017, detail='彌生和日美子(1.82)', track='彌生和日美子', accept_npc='彌生 2000:54,97', steps_total=1,
         steps={}, bag_slots=1, boss=False, est_min=3, live=True, note='純巡路（日美子 1000:57,124）'),
    dict(id=2015, detail='亞姆的斧頭(1.82)', track='亞姆的斧頭', accept_npc='亞姆亞姆 1400:69,89', steps_total=2,
         steps={}, bag_slots=1, boss=False, est_min=5, live=True,
         note='純巡路（馬提 1300:18,42 → 亞姆亞姆）；詳情列表拖動有慣性，questdetail 已等 1.5 秒並驗右側標題'),
    dict(id=2027, detail='小豬愛情故事(1.82)', track='小豬愛情故事', accept_npc='烏力斯凱 20401:14,10', steps_total=2,
         steps={}, bag_slots=2, boss=False, est_min=5, live=False, note='純巡路（烏力美 20406:36,34 → 烏力斯凱）；接受要按 2 次'),
    dict(id=2018, detail='馬祖快遞(1.82)', track='馬祖快遞', accept_npc='馬祖 1300:70,51', steps_total=3,
         steps={}, bag_slots=1, boss=False, est_min=11, live=False, note='純巡路（房子主人 120 → 迷宮 119 卡伊特 → 馬祖）；多層迷宮'),
    dict(id=2011, detail='夢幻洞窟(1.82)', track='夢幻洞窟', accept_npc='村中的老人 6000:73,54', steps_total=2,
         steps={}, bag_slots=1, boss=True, est_min=9, live=False,
         note='步 1 任務戰（卡卡金寶）；每轉解一次即可；追蹤清單要先捲到目標（quest.py 已用 titlematch）'),
    dict(id=2024, detail='龍的巢穴(1.82)', track='龍的巢穴', accept_npc='守護者 20801:13,63', steps_total=4,
         steps={}, bag_slots=3, boss=True, est_min=7, live=True,
         note='巡路 + 對話 + 3 場任務戰（疾速 / 剛氣 / 鋼格之龍，2026-10-11 實測；10-10 舊紀錄「無戰鬥」有誤）；終點 7 樓 20807:23,7 剛氣龍；追蹤名「龍的巢穴」，漆黑洞窟(二轉) 不可誤點'),
    dict(id=2020, detail='強盜的洞穴(1.82)', track='強盜的洞穴', accept_npc='老人薩頓 1112:16,15', steps_total=4,
         steps={}, bag_slots=4, boss=True, est_min=13, live=False,
         note='3 場任務戰（怪力的小陣 10701 / 鐵壁的小守 10703 / 疾風的咪雅 10705，各得一件傳家寶）；盜賊對話框是「戰鬥 / 再見」，左鈕 948,461 = 戰鬥；10-09 quest.py 判成 idle 沒按（quest.py 已加按鈕 OCR 後備，未用樣本驗證，需實機確認）；末步回薩頓交付（薩頓家的秘藥、聲望 2）'),
    dict(id=2023, detail='解救老爺爺(1.82)', track='解救老爺爺', accept_npc='村莊小姑娘 3110:16,15', steps_total=2,
         steps={}, bag_slots=1, boss=False, est_min=5, live=False,
         note='純巡路（哈羅山的醫生 20105:16,20 拿藥 → 村莊小姑娘交藥）；攻略名「塔姆塔姆村的草藥」'),
    dict(id=2028, detail='強恩一族(1.82)', track='強恩一族', accept_npc='吉德的朋友 3400:59,66', steps_total=10,
         steps={}, bag_slots=1, boss=True, est_min=10, live=False,
         note='3 場任務戰（4～6 樓山賊守衛）+ 強恩 / 妻 / 莎拉對話；接取左鈕要按「接受」2 次（questdetail presses=2）；每步結束 quest.py 會提前結束 → questrun 迴圈續跑；獎勵山賊的羽飾（可丟）'),
    dict(id=2025, detail='伐木證書(1.82)', track='伐木證書', accept_npc='樵夫巴爾 3300:60,75', steps_total=6,
         steps={}, bag_slots=3, boss=False, est_min=23, live=False,
         note='純巡路 + 對話（哈恩 20508 / 科巴爾特 20507 地下 7F / 巴爾 / 加加村賽尚 3000:114,69）；中間道具 2～3 件（空壺 / 水壺 / 斧頭）→ 背包留空位；10-10 步 1 曾跳「接取任務條件不達標」（原因沒查到）→ questrun 停 119 / 128 時先關提示重試 1 次；獎勵杉的手環（可丟）'),
    dict(id=2010, detail='四寶玉之謎(1.82)', track='四寶玉之謎', accept_npc='村子的學者 6000:58,44', steps_total=5,
         steps={}, bag_slots=5, boss=True, est_min=18, live=False, hp_every=1,
         note='4 場守護獸任務戰（薩伊那斯 / 加魯卡 / 吉魯島 / 沙姆島，完整戰鬥畫面，5 人自動戰鬥要開）；步 5 回奇努伊村學者；接取前先關原地遇敵較穩；獎勵月光的手鐲（可丟）'),
    dict(id=2014, detail='黃金羚羊之謎(1.82)', track='黃金羚羊之謎', accept_npc='採石所管理人 31902:9,7', steps_total=11,
         steps={}, bag_slots=3, boss=False, est_min=14, live=False, post=dict(pets_personal=['摩娜西普']),
         note='純巡路 + 對話（採石場 → 達那 / 福爾德長老 → 庫伊老爺爺）；精靈之木（大樹）點不到 → 走追蹤列表；頭上黃「!」不是任務目標；獎勵寵物摩娜西普（佔寵物欄 → 存個人倉庫）'),
    dict(id=2012, detail='五兄弟之謎(1.82)', track='五兄弟之謎', accept_npc='吉諾 31701:29,44', steps_total=8,
         steps={}, bag_slots=5, boss=True, est_min=22, live=False, post=dict(store_public=['人龍隨機蛋']),
         note='步 7 浦魯德任務戰（其餘為對話）；中間 5 張答案用紙佔背包（bag_slots 5）；10-10 完成未被認出 → 現在以「領獎後追蹤列表找不到 = 完成」判斷；獎勵人龍隨機蛋 → 存公共倉庫'),
    dict(id=2013, detail='礦工的比賽(1.82)', track='礦工的比賽', accept_npc='帖尼姆 31805:19,21', steps_total=6,
         steps={}, bag_slots=2, boss=True, est_min=4, live=True,
         note='全自動（10-10 實測約 4 分）：巴巴洛 / 礦山 3F 原石任務戰 / 礦工巴卡斯任務戰 + 對話；完整戰鬥畫面自動戰鬥打完'),
    dict(id=2021, detail='夢德洞窟(1.82)', track='夢德洞窟', accept_npc='村姑 1200:96,75', steps_total=6,
         steps={}, bag_slots=2, boss=False, est_min=3, live=True,
         note='純巡路 + 對話（卡坦 / 霍爾特 / 盜賊基地最底層夢德族長，10-10 實測約 3 分）'),
    dict(id=3003, detail='猜謎三兄弟(1.82)', track='猜謎三兄弟', accept_npc='受理A 811:30,20', steps_total=3,
         steps={1: dict(kind='manual')}, bag_slots=1, boss=False, est_min=50, live=False, reward_pets=['左迪洛斯'],
         pet_prep={2: dict(need='金布伊 Lv77（練寵）', petwatch='petwatch.py --pet 金布伊 --level 77 --back 朵拉比斯 --exp-fruit')},
         note='步 1 爬塔（811→810 共 11 層，810 屬 noTaskNavigate 不能自動巡路）+ 金布伊 Lv77 要人 / 手動：每層點守衛 →「猜謎答題」→ 4 張寵物圖選一（玩家觸發的任務答題，准許查 quests/answers.md 作答；若不是此畫面一律當驗證停手）。'
              '接取：詳情 →「接藍暴任務」→「接受」要按 2 次，questdetail.accept 預設 presses=2 已支援；questrun 接取後進步 1 即停 115。'
              '步 2、3 預設：金布伊練到 77（約 9 分）後 `questrun run 3003` 續跑，點追蹤直接巡到 810 伊那多，不用重爬塔；交接前 5 人戰寵換金布伊；獎勵左迪洛斯（丟）'),
    dict(id=2016, detail='恐龍博士(1.82)', track='恐龍博士', accept_npc='恐龍博士哈魯 11006:11,11', steps_total=2,
         steps={1: dict(kind='manual'), 2: dict(kind='manual')}, bag_slots=0, boss=False, est_min=45, live=False,
         turnin=dict(kind='dino', steps={0: (1, 2), 1: (1, 2), 2: (2,)}), rest_pets=True, reward_pets=['布克布克'],
         pet_prep={1: dict(need='魯尼帖斯（呼拔拔系）Lv18+ 每人 1 隻', assign=_assign((1, '呼拔拔系', '魯尼帖斯')), count=5),
                   2: dict(need='貝魯卡（老虎系）Lv30+ 每人 1 隻', assign=_assign((2, '老虎系', '貝魯卡')), count=5)},
         note='交寵物類（Task type=7，要抓魯尼帖斯 Lv18+ ×5 / 貝魯卡 Lv30+ ×5，見 psa-pet-quest skill）：questrun 預設只負責接取，之後步 1、2 都停 115 交人（加 --pet-turnin：rest-all → 解散 → pet_turnin dino 5 人逐人交 → DKBO 重組，未實機）；交時解散逐人交，跳「選擇寵物」視窗要看名字點卡片（quest.py 不處理）；交前寵物改「等待」；獎勵布克布克（丟）'),
    dict(id=2019, detail='卡坦的願望(1.82)', track='卡坦的願望', accept_npc='卡坦 100:230,180', steps_total=2,
         steps={}, bag_slots=0, boss=False, est_min=80, live=False, rest_pets=True, reward_pets=['修寶', '朵拉比斯'],
         pet_prep={1: dict(need='4 色鯊魚各 Lv25+，每人各 1 隻', assign=_assign((1, '鯊魚系', '克邦凱斯'), (2, '鯊魚系', '加克拉'), (3, '鯊魚系', '加格'), (4, '鯊魚系', '邦恩吉')), count=5),
                   2: dict(need='4 色火雞各 Lv25+，每人各 1 隻（步 1 交完、修寶丟掉、寵物欄空出後才抓）', assign=_assign((1, '火雞系', '火雞'), (2, '火雞系', '克克洛斯'), (3, '火雞系', '霍爾克'), (4, '火雞系', '奇寶')), count=5)},
         note='交寵物（4 色鯊魚 / 4 色雞各 ≥25 級）；**交前先 `pet.py rest-all`**（10-10 一隻在出戰 → 按完成 21 次不前進）；隊長交一次 5 人完成；步 1 獎勵修寶（丟）、步 2 朵拉比斯（存個人倉庫）；寵物準備是手動流程'),
]

# 四大洞窟（二轉前置；詳情 / 追蹤標題都沒有 (1.82) 後綴）。放獨立表：不進 DEFAULT_ORDER（questrun 空 ids 的「全部」仍只跑 1.82），指定 ID 才用
QCAVE = [
    dict(id=2000, detail='琉璃洞窟', track='琉璃洞窟', accept_npc='拉魯 3413:16,18', steps_total=5,
         steps={}, bag_slots=2, boss=True, est_min=15, live=False,
         note='組隊 + 自動巡路走得通（10-10 實測 14 分）；步 3、4 守護獸、步 5 女神 2 場；開跑前 5 人自動戰鬥 on（DKBO 關著會卡在下指令）；接取後別誤觸左側面板'),
    dict(id=2003, detail='深紅洞窟', track='深紅洞窟', accept_npc='真紅 5106:26,15', steps_total=5,
         steps={}, bag_slots=1, boss=True, est_min=20, live=False,
         note='步 1 拉多拉山山頂不死鳥路長遇敵多（適合吃龍王的守護）；直接組隊跑，不要單人逃跑（10-10 解散失敗）；步 3、4 守護獸、步 5 伊拉 2 場'),
    dict(id=2001, detail='玄黃洞窟', track='玄黃洞窟', accept_npc='卡坦的村長 1406:22,14', steps_total=10,
         steps={}, bag_slots=1, boss=True, est_min=40, live=False,
         note='5 場戰鬥（8F / 14F 守護獸打兩輪 + 唐）；步 10 對話後又開戰，questrun 會再起一片；建議 --max-min 45'),
    dict(id=2002, detail='碧青洞窟', track='碧青洞窟', accept_npc='水的使者 3400:63,72', steps_total=11,
         steps={}, bag_slots=2, boss=True, est_min=40, live=False,
         note='5 場戰鬥；10-10 在戰鬥中開外掛「自動逃跑」→ DKBO 脫隊（現已廢除，跑洞窟期間任何 agent 不准開外掛面板）；BOSS 後照 37 / 38 查滿 5 人；建議 --max-min 45'),
]

# 其他每轉必做的任務（不進 DEFAULT_ORDER；指定 ID 才用）
QOTHER = [
    dict(id=2031, detail='英雄島前傳（必做）', track='英雄島前傳', accept_npc='走失孫女的老爺爺 5500:12,18', steps_total=8,
         steps={6: dict(kind='fight', map=5510, xy=(50, 17), warp=(1160, 646), warp_name='龍王守衛', npc='龍王的守衛 5510:53,17', hp_min=80)},
         bag_slots=6, boss=True, est_min=20, live=False, dragon_required=True, stop_after_rewards=1, min_level=80,
         reward_pets=['巴朵蘭恩'], post=dict(store_personal=['英雄的祝福'], store_public=['龍王的守護']), drop_items=['薩姆吉爾的首飾'],
         solo=dict(group_from=7),   # --solo（沒龍王 156 的退路）：步 1～5 單人逃跑到 NPC 再組隊對話、步 6 fight、步 7 / 8 組隊跑（2026-10-14 02:41～02:55 手動）
         note='紅暴（每轉必解）。使用者 2026-10-13：有龍王效果就組隊打到底（dragon_required，不看 --dragon；完全沒龍王可吃 → 156 改走單人逃跑 psa-quest-solo）。'
              '前置：成人儀式、5 人 ≥80 級；耐久力回複藥 NPC 會給，不檢查不買。接取標題「英雄島前傳（必做）」。'
              '每步 --stop-after-rewards 1（步 1～5 對話 + 勾玉；步 1 點到同 NPC 閒聊只有再見 → quest.py ESC 回原流程）；'
              '步 6 kind=fight：HP 檢查（<80% 補血）→ 便捷傳送「龍王守衛」5510:50,17 → quest.py --fight --step 6（贏了地圖換 5511）；'
              '步 7 龍王對話每人得龍王的守護 ×2 + 巴朵蘭恩 Lv1（寵物欄滿會卡）；步 8 老爺爺的孫女 1013:14,16，獎勵窗（英雄的祝福 ×5 + 薩姆吉爾的首飾）石幣動畫多，quest.py settle_reward 補關。'
              '完成後 post：英雄的祝福存個人、龍王的守護存公共；巴朵蘭恩 --drop-reward、首飾 --drop-items 要明確旗標'),
]

# 2026-10-13 二轉後重做實測：每任務 quest.py 自報「走路不計時」秒數合計（notes/review-redundancy-1013.md §1）
WALK_S = {2999: 43, 2017: 2, 2015: 7, 2027: 79, 2018: 316, 2011: 9, 2024: 63, 2020: 93, 2023: 43, 2028: 81, 2025: 589,
          2010: 136, 2014: 141, 2012: 35, 2013: 18, 2021: 70, 2000: 320, 2003: 220, 2001: 374, 2002: 678}
DRAGON_WALK_MIN = 120           # （僅參考，不再決定吃不吃）長巡路門檻
NO_DRAGON = {2017, 3003, 2016, 2019}   # 不吃龍王的任務：彌生和日美子、猜謎三兄弟、恐龍博士、卡坦的願望（使用者 2026-10-13）

ALL = Q182 + QCAVE + QOTHER
for _d in ALL:
    _d['walk_s'] = WALK_S.get(_d['id'])
    _d['dragon'] = _d['id'] not in NO_DRAGON
BY_ID = {d['id']: d for d in ALL}
DEFAULT_ORDER = [d['id'] for d in Q182]
STEP_KINDS = ('walk', 'manual', 'fight')


def pet_prep_hint(d: dict, step) -> str | None:
    """d['pet_prep'] 有這一步 → 「需先抓 / 練寵」訊息（含下一步該跑的指令）；沒有 → None。
    pet_prep[步] = dict(need=說明, assign='角色:系別:物種,…' + count=誘餌數 → pet_catch.py 指令 / petwatch='練寵指令')"""
    pp = (d.get('pet_prep') or {}).get(step)
    if not pp:
        return None
    if pp.get('petwatch'):
        cmd = f'uv run --no-project python tools/gui/{pp["petwatch"]}'
    elif pp.get('assign'):
        cmd = f'uv run --no-project python tools/gui/pet_catch.py --assign "{pp["assign"]}" --count {pp.get("count", 5)}（先關原地遇敵、解散隊伍）'
    else:
        cmd = '見 psa-pet-quest SKILL.md'
    return (f'需先抓 / 練寵：步 {step} {pp["need"]}；下一步跑：{cmd}；寵物備妥後 `questrun run {d["id"]} --after none` 續跑'
            f'（或整套交給總控：uv run --no-project python tools/gui/petquest.py run {d["id"]} --confirm-drop）')


_ROWS: list = []


def load_rows() -> list:
    """Task.jsonl 整張表（第一次讀後快取）"""
    if not _ROWS:
        import json
        p = ROOT / 'knowledge' / 'data' / 'tables' / 'Task.jsonl'
        _ROWS.extend(json.loads(ln) for ln in p.read_text(encoding='utf-8').splitlines() if ln.strip())
    return _ROWS


def task_rows(task_id: int, rows=None) -> list:
    """Task.jsonl 該任務組的各步（依 step 排序）；rows = 已讀好的整張表（測試 / 重複呼叫用）"""
    if rows is None:
        rows = load_rows()
    return sorted((r for r in rows if r.get('group') == int(task_id)), key=lambda r: r.get('step', 0))


def prereqs(task_id: int, rows=None) -> list:
    """接這個任務前要先完成的任務組（Task 表第 1 步 finishTasks）；表讀不到 → []"""
    try:
        ts = task_rows(task_id, rows)
    except (OSError, ValueError):
        return []
    return [int(x) for x in (ts[0].get('finishTasks') or [])] if ts else []


def bag_need(task_id: int, rows=None) -> int:
    """這個任務最多同時佔幾格背包（只算道具 itemId，不算石幣 / 經驗 / 寵物）：每步「交出前」= 手上 ∪ 本步條件道具（條件道具可能來自對話 / 掉落，表上沒有獎勵也先算進來），
    「交出後」= 扣掉條件道具 + 本步獎勵；取兩者最大值。同名疊加只算 1 格；任務進行中已持有的不另扣（保守）"""
    held, peak = set(), 0
    for t in task_rows(task_id, rows):
        cond = {c['itemId'] for c in (t.get('condition') or []) if c and c.get('itemId')}
        got = {r['itemId'] for r in (t.get('reward') or []) if r and r.get('itemId')}
        peak = max(peak, len(held | cond))
        held = (held - cond) | got
        peak = max(peak, len(held))
    return peak


def get(task_id: int) -> dict | None:
    return BY_ID.get(int(task_id))


def resolve(ids) -> tuple:
    """→ (任務資料列表, 不認得的輸入列表)；ids 空 = 預設順序（全部）；保留輸入順序"""
    if not ids:
        return list(Q182), []
    out, bad = [], []
    for x in ids:
        try:
            d = BY_ID.get(int(x))
        except (TypeError, ValueError):
            d = None
        if d:
            out.append(d)
        else:
            bad.append(x)
    return out, bad


def step_kind(d: dict, step) -> str:
    """步號 → kind（沒列 = 'default'）"""
    return (d.get('steps') or {}).get(step, {}).get('kind', 'default')
