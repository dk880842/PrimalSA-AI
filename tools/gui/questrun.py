#!/usr/bin/env python3
"""1.82 任務驅動器（P2：驅動器骨架 + 純巡路任務；計畫 notes/plan-182-script.md）。只用標準函式庫。

用法（專案根目錄；WSL / Windows 原生相同）：
  uv run --no-project python tools/gui/questrun.py plan [任務ID …]            # 不碰遊戲：印交接 / 每任務步驟 / 指令 / 預估 / 退出碼（沒給 ID = questdefs 全部）
  uv run --no-project python tools/gui/questrun.py run 2999 2017 2015 [--dry-run] [--after grind|none] [--dragon [--dragon-all]] [--spot 地雷區]
        [--max-slices 60] [--slice-s 60] [--max-min 30] [--hp-min 50] [--team-hp-min 60] [--hp-check-every 3] [--no-boss-retry]
        [--verify risk|each|off] [--no-verify-all] [--verify-skipped] [--no-battle-check] [--battle-check-always]
        [--pet-turnin] [--drop-reward 左迪洛斯,巴朵蘭恩 --confirm-drop 左迪洛斯,巴朵蘭恩]
  龍王的守護（2026-10-12 起）預設**不吃**，要吃加 --dragon；--no-dragon 保留相容（= 預設，no-op）。
  --dragon（2026-10-13 起）只對 questdefs 標 dragon（巡路 ≥ 120 秒：馬祖快遞 / 伐木證書 / 四寶玉 / 黃金羚羊 / 四大洞窟）的任務吃，--dragon-all 全吃；
  第一次從公共倉庫整疊取出，剩的**留在 DKBO 背包**，run 結束（成功或失敗；9 / 10 / 116 / 152 等畫面要留給人看的除外）才整疊存回公共倉庫；
  中斷沒存到 → 進度檔 dragon_in_bag，下次 questrun 開頭（不吃時）/ 結束補存。depot_use 判 buff 已在（skip）不計「已吃」
  uv run --no-project python tools/gui/questrun.py status [任務ID …]          # 唯讀（要開 / 關任務詳情面板）：印各任務目前狀態（當前角色）
  uv run --no-project python tools/gui/questrun.py status --role all|DKBO3,DKBO5 [任務ID …]   # 逐人：每人 char.switch → 開一次詳情讀這些任務 → 最後切回 DKBO（詳情面板沒有頭像列，只能切角色）
  可 import：questrun.run(ids, dry_run=False, after='grind', tools=None, ...) → 退出碼；結果 dict 在 questrun.LAST

任務資料在 questdefs.py（id / 詳情標題 / 追蹤標題 / 特殊步驟）。全部組隊模式（使用者 2026-10-11）；解任務靠遊戲自動巡路（quest.py 點追蹤、對話按確認、每場戰鬥刷新角色）。

流程：
  交接（整次 run 一次）  follow 還在跑就停（已停用，只防呆）→ 清殘留（quest.clear_leftovers：NPC 對話框 / 只有再見 / 選擇對象 → ESC 不回答、獲得物品 → 確認、
                        已知面板〔背包 / 倉庫、組隊、切換、寵物…；標題板字 + ✕ 都命中〕→ 點 ✕；preflight 回 9 時也先清一次再重驗；清不掉的不認得畫面 → 9）
                        → 關原地遇敵 + 等戰鬥結束 → 再清一次殘留（2026-10-13 08:00 / 08:01 背包面板、NPC 對話窗殘留 → ass 選不到頭像 / 外掛面板打不開 109）→ team.form 滿 5 人（同一次切換面板讀「當前」，不是 DKBO 才 char.ensure；
                        2026-10-12 起不另跑 char.current，省 1～2 次開關面板）
                        → （2026-10-12 四寶玉之謎 DKBO 人物首次動作「風的精靈Lv.5」沒勾、BOSS 戰 2 人陣亡）戰鬥設定檢查 ass.battle_check：
                        一次開外掛面板、左欄頭像逐人（隊長最後）讀 5 人自動戰鬥 + DKBO 人物首次動作（值 風的精靈 + 打勾），只改不對的勾選、讀回確認；
                        值不對 / 改不動 → 109（不自動改下拉）；放在關遇敵 + 等戰鬥結束之後（戰鬥中不開外掛面板，ass 回 8 → 109）；--no-battle-check 關。
                        bossretry 重打前也查一次（同一份設定，失敗 147）。2026-10-13 起 30 分內查過 OK 且之後沒有重登 / bossretry → 沿用不開外掛面板（進度檔 battle_ok_at；--battle-check-always 關快取）
  每個任務
    1 preflight    背包空位（defs.bag_slots = 任務道具最多同時佔的格數，questdefs.bag_need 由 Task 表推、test 核對；--dragon 要吃且龍王還不在背包 → DKBO +1）：不足的人先自動刪 bag.AUTO_PURGE
                   （ui/bag.md 白名單去掉有條件的龍的魅力之笛 / 亞姆亞姆的斧頭），仍不足才 110；補血檢查 hp_gate：隊長 HUD HP < --hp-min% 或全隊任一人 < --team-hp-min%（預設 60；開背包逐人讀 HP，約 8 秒）
                   → heal（小護士補整隊）後重組隊；quest.py 37（BOSS 戰贏、滿 5 人）後下一片之前也做一次（BOSS 後一定讀；有人 HP 0 / 讀不出 = 風險事件）。
                   2026-10-13：背包空格與全隊 HP 同一次開背包讀（bag.team_scan）；全隊 HP 5 分內確認過（讀了沒人偏低 / 剛補血）且之間 quest.py 說「本片戰鬥 0 場」→ 沿用不讀
    2 接取         team.form（距上次組隊 / 驗隊伍 ≤ TEAM_FRESH_S 秒就略過，例：交接剛組完）→ questdetail.accept(skip_ok, verify=False)：**整個任務只開一次詳情**，同一趟捲動讀狀態（已完成 → 跳過、進行中 → 續跑、待接取 → 傳送 → NPC 對話 → 接受，不重開詳情驗證，看對話框收起）；失敗 119
    3 跑步驟       迴圈（每片 ≤ --slice-s 秒，總計 ≤ --max-min 分，片數 ≤ --max-slices）：
                   （--dragon 且 questdefs dragon 的長巡路任務才做）龍王的守護（人形圖示不在才吃：第一次 depot_use 公共倉庫整疊取出 → 吃 1 顆 → 剩的留在 DKBO 背包，之後直接從背包吃；吃完再關原地遇敵；
                   遊戲還在自動巡路就這片先不吃 —— 2026-10-13 08:04 開背包途中抵達 NPC、對話框把背包藏起來 → depot_use 90）
                   → defs.steps 有 manual 步驟時 quest.read_step_no 讀步號 → 115（defs 有 turnin 且加 --pet-turnin：改跑交寵物，見下）；kind=walk 是備援：quest.py 先點追蹤讓遊戲自動巡路，只有回 3（追蹤沒反應 = 原地不動）才用 questhandlers.walk_step 走到定點
                   → quest.py --task <追蹤標題> --max-seconds N，依退出碼分支（見下）；
                     questrun 在 TEAM_FRESH_S 秒內驗過隊伍（接取後 form、quest.py 37 的 BOSS 後檢查、30 / 32 後 form）→ 加 --team-fresh，quest.py 開始前不再開切換面板
                     （領獎後 / 任務戰後的隊伍檢查、37 / 38 照舊）；--team-hp-min > 0 時加 --hp-check-min + --hp-check-every（片內：任務戰後、路上一般戰鬥每 N 場〔預設 3，
                     questdefs hp_every 覆寫：四寶玉之謎 1〕回主畫面讀全隊 HP，偏低 → 41）
                   → 每片 0 / 37 後看主畫面信封鈕發亮（screen_sigs.MAIL_GLOW，會閃 → 讀 4 次）→ 背包 / 信箱處理（見下「背包滿進信箱」）
    4 逐人驗證     （2026-10-12，四寶玉之謎隊長完成、DKBO3 / DKBO5 被打飛沒完成卻沒發現）其他 4 人逐一 char.switch 讀任務詳情
                   （questdetail.status_all，每人開一次詳情、一趟捲動讀多個任務）；有人不是「已完成」→ bossretry --who 落後者（落後者當隊長組 5 人重打 → 切回 DKBO 重組）
                   → 再讀一次那幾個人；仍沒完成 / 讀不到 / 待接取（沒接到）→ 108 停手。
                   何時驗（--verify，2026-10-13 review §2：10-13 驗 20 次共 43 分、0 次抓到落後者）：
                     risk（預設）本任務有風險事件 —— quest.py 30 / 32 / 38 / 21 / 41、bossretry、全員重登、BOSS 後有人 HP 0 或讀不出、交寵物 —— 才完成時當場驗；
                                 沒有 → 記進進度檔 verify_pending，全部任務結束後一次批次驗；下一個任務的前置（questdefs.prereqs，Task 表 finishTasks）在待驗清單 → 接取前先批次驗；
                                 失敗退出時待驗清單留在進度檔，下次 questrun 結束再驗（超過 2 小時的丟掉）
                     each        舊行為：每任務完成當場驗；off / --no-verify-all 不驗。詳情一開就已完成而跳過的任務預設不驗（--verify-skipped 才當場驗）
    5 收尾         進度檔記已完成（2 小時內）→ 重跑直接跳過；quest.py 印「任務完成」（領獎後追蹤欄沒有該任務）即完成，不開詳情；沒有該字樣才讀一次詳情確認 → 進度檔 tools/.cache/questrun.json、notes/quest-log.md 追加一筆
  交寵物（--pet-turnin，預設關 = manual 步照舊 115；**未實機**）
                 defs.turnin（目前只有恐龍博士 2016：步 1 魯尼帖斯 / 步 2 貝魯卡，逐人「選擇」視窗）：pet.py rest-all（任務寵改等待）→ team.disband
                 → pet_turnin.run 5 人逐人（char.ensure → 點追蹤 → 對話 → 依名字點卡 → 確定）→ char.ensure DKBO → team.form → 讀詳情；失敗 150。
                 defs.rest_pets（卡坦的願望 2019：隊長交一次 5 人完成，quest.py 預設流程交）：接取後第一片前先 pet.py rest-all。每任務只試一次
  丟獎勵寵（--drop-reward 名字,… 且 --confirm-drop 同一串，缺一不做；**不可逆、未實機**）全部任務成功後、恢復掛機前：
                 每個名字 petdrop.drop('all', 名字, max_level=1)（只丟名字完全相同、等級讀得到且 = 1 的；騎寵 / 第 1 格 / 出戰 / 騎乘一律擋）；失敗 151、不恢復掛機
  交接回去（全部成功才做）--after grind（預設）= grind.py start --spot 地雷區（不重啟 follow）；none = 不動。**失敗退出一律不恢復掛機**（畫面狀態未知）

quest.py 退出碼分支：0 → tail 有「任務完成」= 結束；「時間到」/「提前結束」（步驟結束後閒置，review §6.1）→ 不開詳情直接下一片；其他才讀一次詳情：已完成 = 結束、進行中 = 下一片；37 BOSS 戰贏且滿 5 人 → 下一片；38 BOSS 後隊伍不滿 / 21 被打飛 → bossretry.py 自動補人（落後者當隊長組 5 人按追蹤回 BOSS 處全隊重打 → 切回 DKBO 重組；每任務最多 BOSS_RETRY_MAX 次，0 → 補血檢查後下一片；--no-boss-retry 關）；
  （2026-10-11）quest.py 的 slice 時限不計自動巡路時間（它結束時印「走路不計時 N 秒」，questrun 把 N 加回 t0 = 不計入 --max-min；子程序逾時 = slice + WALK_CAP_S + 120）；
  quest.py 回 0 且 tail 有「時間到」（單純 slice 到期、任務還在追蹤欄）→ 不開詳情，直接下一片（完成由下一片 quest.py「任務完成」或回 5 時才讀詳情確認）；回 0 但沒有「任務完成」也不是「時間到」（模糊）才讀一次詳情
  3 追蹤沒反應 → 有 walk 步驟先走，否則 112；5 找不到任務 → 看詳情狀態（已完成 = 結束，否則 112）；30 / 32 隊伍不符 → 原地 form()（失敗先關誤開面板再重試 3 次）再起一片，最多 3 輪仍不行才 111（不退出整套）；
  41 片內戰鬥後全隊 HP 偏低 → 補血（小護士）+ team.form → 下一片（每任務最多 HP_LOW_MAX=5 次，超過 111）；
  40 任務 NPC 只有「再見」（quest.py 已 ESC）→ 背包 / 信箱處理：背包空格 < 1 的人刪白名單 → mail.py claim 領「丟失的物品」→ 續跑（不重置任務；每任務最多 BYE_RECOVER_MAX=2 次）；
     背包沒滿且信箱沒有丟失信（mail 112）→ 153；背包刪不出空位 / mail 114 等 → 154；
  19 自動巡路卡住（quest.py 已刷新角色 + 點地面解卡 3 次）→ questrun 再「刷新 + 走上附近出口」最多 2 次，仍不行 → 全員重登（見下）；
  42 快速戰鬥 VS 牌卡死 90 秒 → 全員重登；3 追蹤沒反應連 2 次以上且全隊頭上 VS 牌卡住 → 全員重登。
     全員重登 = relogin.run(confirm=True, stuck=True)（起始畫面可以是巡路 / 快速戰鬥；登入畫面只按遊戲已帶入帳密的「登錄」，鐵則 2）→ relogin 的 team.check
     （105 隊伍不對 → team.form --regroup）→ 關原地遇敵 → 戰鬥設定檢查 → 續片；每任務最多 RELOGIN_MAX=2 次，再卡 / 重登失敗 → 112；
  33 對話無進展 → 117；29 對話 ↔ 選擇對象循環（交寵物任務多半是寵物沒湊齊）→ 117；25 完整戰鬥自動戰鬥卡住 → 118；39 不可逆對話 → 116（不放行）；2 不認得的畫面（疑似驗證視窗）→ 9 停手通知（鐵則 5）；10 斷線（netwatch）→ 10；21 被打飛 → 同 38 走 bossretry；其他 → 112

退出碼（共用 0 / 1 / 2 / 8 / 9 / 10 見 uikit；其他工具 20～107、120～129；questrun 自己 108、110～119）：
  109 戰鬥設定檢查失敗（ass.battle_check：人物首次動作的值不對 13 / 勾選改不動 4 / 面板問題 2～7 / 戰鬥中 8；info.battle）
  108 逐人驗證：有人任務沒完成，bossretry 補人後仍沒完成 / 補人失敗 / 讀不到某人的詳情 / 某人是待接取（info.laggards、info.verify）
  110 preflight 失敗（任務不認得 / 讀不到狀態 / 背包空位不足 / 當前角色不是 DKBO）
  111 交接 / 組隊失敗（follow 停不掉、關遇敵、team.form、補血）
  112 步驟卡住（追蹤沒反應又沒 walk 步驟、walk 走不到、找不到任務但狀態不是已完成、quest.py 非預期退出碼）
  113 片數 / 時間上限到了任務還沒完成
  114 BOSS 後隊伍不滿 / 被打飛，bossretry 失敗或次數用完 / --no-boss-retry（info.boss_retry_rc = bossretry 的 140～146）
  115 kind=manual 的步驟（停下交人）
  116 quest.py 回 39（不可逆對話，沒按）
  117 對話無進展（quest.py 33）
  118 完整戰鬥自動戰鬥卡住（quest.py 25）
  119 接取失敗（info.accept_rc 是 questdetail 的 120～128）
  150 交寵物失敗（--pet-turnin：rest-all / 解散 / pet_turnin 120～125 / 切回 DKBO / 重組；info.turnin）
  151 丟獎勵寵失敗（--drop-reward：petdrop 70～79，73 = 防護擋下；info.drop）
  153 任務接不下去：quest.py 40（任務 NPC 只有「再見」）且背包有空、信箱沒有丟失的物品（或處理 2 次後 NPC 仍只有再見）→ 停手回報（條件不符？請人看）
  154 背包滿自動處理失敗：讀空格 / 刪白名單失敗、刪完仍滿、mail.py 領取失敗（114 = 領了沒消失）
  背包滿進信箱（2026-10-13 強盜的洞穴步 3：5 人背包滿 15 格，薩頓家的頭盔進系統郵件「這是您丟失的物品」→ 老人薩頓只剩再見）：
                 觸發 = quest.py 40 或片後信封發亮；做法 = make_room（空格 < 1 的人 bag.purge AUTO_PURGE）→ mail.run('claim')（帳號共用信箱一次領完）→ 續跑；
                 信封發亮但沒有丟失信（112）→ 本次 run 不再因發亮開信箱
  152 領獎視窗關不掉：quest.py 回 18（獲得物品按確認 3 次仍在）→ questrun 先重試關窗（只有畫面仍是 reward 才按確認 720,572 並驗證消失；已不是 reward 就不點，當成已關）
      成功就續跑下一片；重試仍關不掉、或同一任務重試已達 REWARD_RETRY_MAX 次 → 152「請人工處理」，存 snap questrun-reward-stuck，不恢復掛機（info.reward_retry）
"""
import argparse
import json
import os
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import questdefs  # noqa: E402
import questhandlers  # noqa: E402
import rebirth  # noqa: E402
import uikit  # noqa: E402

SRC = 'questrun'
ROOT = uikit.ROOT
EVENT_LOG = rebirth.EVENT_LOG
QUEST_LOG = rebirth.QUEST_LOG
PROGRESS = rebirth.logpaths.p(uikit.CACHE / 'questrun.json')

(EXIT_PREFLIGHT, EXIT_HANDOVER, EXIT_STEP, EXIT_SLICES, EXIT_TEAM, EXIT_MANUAL,
 EXIT_IRREV, EXIT_STALL, EXIT_BATTLE, EXIT_ACCEPT) = range(110, 120)
EXIT_LAGGARD = 108                                                   # 逐人驗證後仍有人沒完成（grep 過 108 沒被其他工具用）
EXIT_BATTLESET = 109                                                 # 戰鬥設定檢查失敗（rebirth_pets 也有 109，但兩者不互相呼叫）
EXIT_REWARD = 152                                                    # 領獎視窗關不掉（quest.py 18 → 重試仍失敗；152 grep 過沒被用）
REWARD_RETRY_MAX = 3                                                 # 每個任務最多重試關領獎窗幾次（避免無限迴圈）
EXIT_TURNIN, EXIT_DROP = 150, 151                                    # 交寵物 / 丟獎勵寵失敗（150～151 grep 過沒被用）
EXIT_BYE, EXIT_BAGMAIL = 153, 154                                    # 任務 NPC 只有再見（背包 / 信箱都不是原因）/ 背包滿自動處理失敗（153～154 grep 過沒被用）
BYE_RECOVER_MAX = 2             # 每個任務 quest.py 40（NPC 只有再見）時最多做幾次「背包 / 信箱」處理
HP_LOW_MAX = 5                  # 每個任務 quest.py 41（片內 HP 偏低）最多補血幾次，超過 111
DROP_MAX_LEVEL = 1                                                   # --drop-reward 只丟這個等級以下（剛拿到的獎勵寵是 1 級）

LEADER = rebirth.LEADER
ALL_ROLES = rebirth.ALL_ROLES
DRAGON = rebirth.DRAGON
DRAGON_REEAT_S = rebirth.DRAGON_REEAT_S
SLICE_S, MAX_SLICES, MAX_MIN, HP_MIN = 60, 60, 30, 50
BOSS_RETRY_MAX = 3              # 每個任務 38 / 21 時最多呼叫幾次 bossretry（四大洞窟每個 2～5 場 BOSS）
TEAM_HP_MIN = 60                # 全隊任一人 HP < 這個 % → 補血（2026-10-12 四寶玉之謎：只看隊長 HP，隊員約 50% 連打 BOSS 被打死踢隊 4 次 38）；0 = 不讀全隊
WALK_CAP_S = 900.0              # quest.py 單次連續自動巡路最多不計時這麼久（要與 quest.WALK_CAP_S 相同；子程序逾時 = slice + 這個 + 120）
DEFAULT_SPOT = '地雷區'
MAIL_GLOW_READS, MAIL_GLOW_GAP = 4, 0.3                              # 信封發亮會閃：讀 4 次（約 1 秒）任一次亮就算有信
FORM_TRIES = 3                  # team.form 原地重試次數（小錯不退出）
TEAM_FRESH_S = 30.0             # 隊伍在這麼多秒內驗過（form 成功 / quest.py 37）→ 接取前不重組、quest.py 加 --team-fresh（2026-10-12 解救老爺爺：開始前 4 次 + quest.py 啟動 1 次開關切換面板）
DONE_TRUST_S = 2 * 3600         # 進度檔記「已完成」且在這段時間內 → 重啟續跑直接跳過（超過視為可能轉生 / 封印書重置過，重新讀一次詳情）
DONE, DOING, PENDING = '已完成', '進行中', '待接取'
VERIFY_MODES = ('risk', 'each', 'off')
BATTLE_OK_S = 30 * 60           # 戰鬥設定檢查 OK 後這麼久內（之間沒有重登 / bossretry）沿用，不再開外掛面板（review §5.1：19 次 run 開頭每次 11 秒）
HP_FRESH_S = 5 * 60             # 全隊 HP 讀過（且沒人偏低）/ 剛補完血後這麼久內、之間沒有戰鬥 → 任務開始前沿用（review §5.2）
HP_EVERY = 3                    # quest.py --hp-check-every 預設（路上一般戰鬥每幾場讀一次全隊 HP；questdefs hp_every 可覆寫，連戰任務 1）
RELOGIN_MAX = 2                 # 每個任務最多自動全員重登幾次（VS 牌卡死 / 巡路卡住解不開）
RELOGIN_TEAM = 105              # relogin.py：重登進遊戲了但隊伍檢查 / 組隊失敗 → questrun 再 team.form --regroup
BAG_ITEM = 92                   # bag.EXIT_ITEM：背包 / 倉庫找不到該道具
NO_TOUCH = (uikit.EXIT_USAGE, uikit.EXIT_UNKNOWN_SCREEN, uikit.EXIT_HALT, 116, 152)   # 失敗退出時畫面要留給人看（驗證視窗 / 斷線 / 不可逆對話 / 領獎窗）→ 不再開背包存龍王
LAST: dict = {}


# ---------------------------------------------------------------- 真實工具（測試換成 Fake，介面相同）
class Tools(rebirth.Tools):
    """沿用 rebirth.Tools 的 quest / read_pos / team_* / char_* / track / snap，補 questrun 要的"""

    def follow_active(self):
        import follow
        return follow.alive_other()

    def follow_stop(self):
        import follow
        return follow.stop_other()

    def screen_state(self):
        return uikit.screen().get('state')

    def esc(self):
        uikit.gui('key', '{ESC}', note='questrun 交接：關閉殘留的對話窗')

    def encounter_off_wait(self):
        """關原地遇敵並等這場戰鬥打完（關遇敵不會中止正在打的那場）"""
        import heal
        heal.set_encounter(False)
        heal.gui('seq', f'waitpix 20000 {heal.SIG_NO_BATTLE} 40')

    def task_status(self, detail):
        import questdetail
        return questdetail.task_status(detail)

    def accept(self, detail):
        """每任務只開一次詳情：→ (rc, state)；state = 'done' / 'doing' / 'accepted'（不重開詳情驗證）"""
        import questdetail
        rc = questdetail.accept(detail, skip_ok=True, verify=False)
        return rc, questdetail.LAST.get('state')

    def read_step(self, track):
        import quest
        return quest.read_step_no(track)

    def gone(self):
        import quest
        return quest.GONE

    def hp_pct(self):
        import quest
        return quest.stat().get('hpPct')

    def team_hp(self):
        """5 人 HP%（bag.team_hp_pct：開背包逐人點頭像讀 HP 條字，約 8 秒）→ (rc, {角色: % | None})；HUD / 切換面板 / 組隊面板都只有當前角色或沒有 HP"""
        import bag
        return bag.team_hp_pct(ALL_ROLES)

    def heal(self):
        import heal
        heal.heal_trip('波拉島', True, False)

    def team_regroup(self):
        """解散不完整的隊伍後重組（team.form --regroup；掉隊者被打飛 / 回村時用）"""
        import team
        return team.form(regroup=True)

    def bag_free(self, roles):
        """5 人背包空格（bag.team_scan 像素判空格，開背包一次）→ (rc, {角色: 空格 | None})"""
        rc, d = self.team_scan(roles, True, False)
        return rc, {r: (v or {}).get('free') for r, v in d.items()}

    def team_scan(self, roles, free=True, hp=True):
        """同一次開背包讀 5 人空格 + HP%（bag.team_scan）→ (rc, {角色: {'free', 'hp'}})"""
        import bag
        return bag.team_scan(list(roles), free=free, hp=hp)

    def dragon(self, have=False):
        """（have=False 時公共倉庫整疊取出）→ 吃 1 顆 → 剩的**留在 DKBO 背包**（restore=False，run 結束才 dragon_store 存回；review §3.1）；回 (rc, info)。
        吃完不開遇敵（跑任務時要關）"""
        import depot_use
        return depot_use.run(LEADER, DRAGON, 'public', restore=False, have=have, reopen=False)

    def dragon_store(self):
        """DKBO 背包剩的龍王的守護整疊存回公共倉庫 → bag 退出碼（92 = 背包沒有，已吃完）"""
        import bag
        return bag.depot_store(LEADER, DRAGON, 'public')

    def close_stray(self):
        """誤開的組隊 / 切換面板 → 點 ✕ 關（已知面板才關；不認得的畫面不碰）"""
        import quest
        return quest.close_stray_panel()

    def clear_screen(self):
        """交接前清殘留（NPC 對話框 / 只有再見 / 獲得物品 → ESC 或確認；已知面板 → ✕）→ 最後畫面狀態；不認得的不碰"""
        import quest
        return quest.clear_leftovers()

    def bag_purge(self, roles):
        """背包滿：只刪 bag.AUTO_PURGE（ui/bag.md 白名單去掉有條件的）→ (rc, {角色: info})"""
        import bag
        return bag.purge(list(roles), bag.AUTO_PURGE)

    def mail_claim(self):
        """信箱領「丟失的物品」（帳號共用，一次領完）→ mail 退出碼（0 / 112 沒有丟失信 / 114 領了沒消失…）"""
        import mail
        return mail.run('claim')

    def mail_glow(self):
        """主畫面信封鈕有沒有發亮（有新信；會閃 → 讀 MAIL_GLOW_READS 次任一次亮就算）"""
        import screen_sigs
        pts = [(x, y) for x, y, *_ in screen_sigs.MAIL_GLOW]
        for i in range(MAIL_GLOW_READS):
            if i:
                time.sleep(MAIL_GLOW_GAP)
            cols = uikit.px(pts)
            if cols and screen_sigs.mail_glow(dict(zip(pts, cols))):
                return True
        return False

    def dragon_active(self):
        """buff 列有龍王的人形圖示嗎（True / False）；讀不到 None。與 depot_use 同一個判斷（bag.buff_state）"""
        import bag
        return bag.buff_state(bag.buff_kind(DRAGON))

    def walk_to(self, m, x, y):
        import walk
        return walk.walk_to(m, x, y)

    def unfreeze(self):
        """自動巡路停住後角色凍住：刷新角色；站在出口格上沒換圖則踏出再踏回 → 換圖後 (map,x,y) / None"""
        import quest as _q
        import walk
        _q.refresh_characters()
        return walk.rewarp_if_on_exit()

    def reward_retry(self) -> str:
        """quest.py 回 18 後再關一次領獎窗：'not_reward'（畫面已不是領獎窗，不點）/ 'closed'（按確認後驗證消失）/ 'stuck'（仍關不掉）"""
        import quest as _q
        if _q.read_screen().get('state') != 'reward':
            return 'not_reward'
        ok, _n = _q.close_reward()
        return 'closed' if ok else 'stuck'

    def vs_stuck(self) -> bool:
        """全隊頭上 VS 牌卡死：連續 3 次（間隔 1 s）讀到「快速戰鬥 VS 牌、沒有完整戰鬥畫面」且 VS 牌一直在"""
        import quest as _q
        for i in range(3):
            if i:
                time.sleep(1.0)
            r = _q.read_screen()
            if r.get('state') != 'battle' or r.get('full'):
                return False
        return True

    def relogin(self) -> int:
        """全員重登（stuck=True：起始畫面可以是巡路卡住 / 快速戰鬥 VS 牌卡死；登入畫面只按「登錄」，鐵則 2）"""
        import relogin
        return relogin.run(confirm=True, stuck=True)

    def unstick_exit(self):
        import quest as _q
        import walk
        _q.refresh_characters()
        return walk.rewarp_if_on_exit() or walk.walk_onto_nearby_exit(2)

    def grind_start(self, spot):
        import grind
        return grind.run('start', spot)

    def boss_retry(self, track, who=None, check=True):
        """BOSS 戰後不滿 5 人 / 逐人驗證有人沒完成（who = 落後者名單）：落後者當隊長組 5 人重打 → 切回 DKBO 重組（bossretry.py）→ (rc, 結果 dict)。
        check = 重打前查戰鬥設定（ass.battle_check；questrun --no-battle-check 時 False）"""
        import bossretry
        rc = bossretry.run(track, who=who, battle_check=check)
        return rc, dict(bossretry.LAST)

    def battle_check(self):
        """解任務的戰鬥設定（ass.QUEST_BATTLE）：一次開外掛面板逐人讀、只改不對的 → (rc, {角色: 狀態}, 訊息, info)"""
        import ass
        return ass.battle_check()

    def pet_rest_all(self):
        """5 人任務寵改「等待」（騎寵不動）→ 退出碼"""
        import pet
        return pet.rest_all('all')

    def team_disband(self):
        import team
        return team.disband()

    def pet_turnin(self, kind, roles, steps):
        """逐人交寵物（pet_turnin.run；會 char.ensure 每個人，不切回 DKBO）→ (rc, {角色: 結果})"""
        import pet_turnin
        return pet_turnin.run(list(roles), tuple(steps), switch=True)

    def pet_drop(self, name, max_level):
        """5 人丟名字 = name 且等級 ≤ max_level 的寵物（petdrop.drop）→ (rc, petdrop.LAST)"""
        import petdrop
        rc = petdrop.drop('all', name, name, max_level=max_level)
        return rc, dict(petdrop.LAST)

    def status_all(self, details, roles):
        """逐人讀任務詳情（char.switch + 每人開一次詳情、一趟捲動讀完 details 全部，最後切回 DKBO）→ (rc, {角色: {標題: 狀態} 或 None})"""
        import questdetail
        return questdetail.status_all(list(details), roles=roles, leader=LEADER)


# ---------------------------------------------------------------- 紀錄
def event(msg: str) -> None:
    line = f'{time.strftime("%Y-%m-%d %H:%M:%S")} [questrun] {msg}'
    print(line, flush=True)
    try:
        EVENT_LOG.parent.mkdir(exist_ok=True)
        with open(EVENT_LOG, 'a', encoding='utf-8') as f:
            f.write(line + '\n')
    except OSError:
        pass


def load_progress() -> dict:
    try:
        return json.loads(PROGRESS.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return {}


def save_progress(d: dict) -> None:
    try:
        PROGRESS.parent.mkdir(parents=True, exist_ok=True)
        PROGRESS.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding='utf-8')
    except OSError:
        pass


def retry_form(T, form_fn, what: str, tries: int = FORM_TRIES) -> int:
    """team.form 原地重試（可恢復的小錯：切換面板偶爾讀到 0 張卡片 rc 42、誤開面板）：失敗 → 關誤開面板 → 等 2 秒 → 再組；
    9（驗證視窗）/ 10（斷線）立即透傳；超過 tries 次才回最後一個失敗碼。questrun.Run.form 與 bossretry.form_as 共用"""
    rc = 0
    for i in range(tries):
        rc = form_fn()
        if not rc or rc in (uikit.EXIT_UNKNOWN_SCREEN, uikit.EXIT_HALT):
            return rc
        event(f'{what}：team.form 失敗 rc={rc}（{i + 1}/{tries}）→ 關誤開面板、2 秒後原地重試')
        cs = getattr(T, 'close_stray', None)
        if cs:
            try:
                cs()
            except Exception as e:
                event(f'close_stray 例外：{e}')
        T.sleep(2)
    return rc


# ---------------------------------------------------------------- 純函式
def classify(rc: int, tail=()) -> str:
    """quest.py 退出碼 → 動作字串（測試直接餵）：done? / boss / stuck3 / gone / team / stall / select_loop / battle / irrev / verify / halt / knocked / bye / hp_low / vs_stuck / other"""
    return {0: 'check', 37: 'boss', 38: 'boss_team', 3: 'no_track', 5: 'gone', 30: 'team', 32: 'team', 33: 'stall', 29: 'select_loop', 25: 'battle',
            39: 'irrev', 18: 'reward_stuck', 2: 'verify', uikit.EXIT_UNKNOWN_SCREEN: 'verify', uikit.EXIT_HALT: 'halt', 21: 'knocked',
            40: 'bye', 41: 'hp_low', 42: 'vs_stuck'}.get(rc, 'other')


def early_end(tail) -> bool:
    """quest.py 是「步驟結束 …，提前結束」（做完對話 / 領獎後連續閒置）：任務多半還有下一步 → questrun 直接下一片，不開詳情（review §6.1）"""
    return any('提前結束' in str(x) for x in (tail or []))


def battles_in(tail):
    """quest.py 結尾印的「本片戰鬥 N 場」→ N；沒有這行（舊版 / 被砍）→ None（當成可能打過仗）"""
    import re
    for ln in reversed(list(tail or [])):
        m = re.search(r'本片戰鬥\s*(\d+)\s*場', str(ln))
        if m:
            return int(m.group(1))
    return None


def walk_secs(tail) -> int:
    """quest.py 結尾印的「走路不計時 N 秒」→ N（沒有 = 0）"""
    import re
    for ln in reversed(list(tail or [])):
        m = re.search(r'走路不計時\s*(\d+)\s*秒', str(ln))
        if m:
            return int(m.group(1))
    return 0


def time_up(tail) -> bool:
    """quest.py 是因為 slice 時間到而結束（事件行「時間到，結束」）"""
    return any('時間到' in str(x) for x in (tail or []))


def rest_hint(rc: int) -> str:
    """pet.py rest-all 失敗碼 → 給人看的提示（2026-10-12 S5 / S6：沒名字的任務寵、外掛鎖定戰寵都讓 rest-all 改不了）"""
    return {72: '（有出戰寵名字 / 縮圖都認不出，沒動它 → pet.py list 看是哪隻、set-state 手動改等待）',
            74: '（狀態點了沒變：多半是外掛「鎖定戰寵」還勾著 → 先取消鎖定再跑，交完用 pet_catch.py --lock 重勾）',
            78: '（戰鬥中：原地遇敵沒關？）'}.get(rc, '')


def est_total(defs) -> int:
    return sum(d.get('est_min', 0) for d in defs)


def print_plan(defs, opts: dict) -> None:
    print(f'questrun 計畫：{len(defs)} 個任務，預估 {est_total(defs)} 分鐘（組隊模式；0 轉 123 級 5 人隊實測值，1 轉可能更久）')
    print(f'選項：{opts}')
    print('[交接]')
    for ln in ('follow 還在跑就 grind.py follow --stop（已停用，只防呆）', '關原地遇敵 + 等戰鬥結束',
               ('戰鬥設定檢查 ass.battle_check（一次開外掛面板逐人：5 人自動戰鬥開、DKBO 人物首次動作 風的精靈 打勾；只改不對的勾選、讀回確認；失敗 109；'
                f'{BATTLE_OK_S // 60} 分內查過且沒重登 / bossretry → 沿用，--battle-check-always 一定查）'
                if opts.get('battle_check', True) else '戰鬥設定檢查：--no-battle-check 不做'),
               'team.form 滿 5 人（同一次切換面板讀「當前登錄」，不是 DKBO 才 char.ensure）'):
        print('  - ' + ln)
    for d in defs:
        print(f'[任務 {d["id"]}] {d["detail"]}（追蹤標題「{d["track"]}」，接取 {d["accept_npc"]}，{d["steps_total"]} 步，預估 {d.get("est_min", "?")} 分）')
        print(f'  - team.form（{TEAM_FRESH_S:.0f} 秒內剛確認過就略過）→ questdetail.accept（只開一次詳情）：已完成 → 跳過；待接取 → 接受（不重開詳情）；進行中 → 續跑')
        if d.get('bag_slots'):
            print(f'  - 背包空位：5 人各 ≥ {d["bag_slots"]} 格（bag.find_items；不足先刪 bag.AUTO_PURGE 白名單，仍不足 110）')
        print(f'  - 補血檢查（任務開始前、每次 BOSS 戰後）：隊長 HUD HP < {opts["hp_min"]}% 或全隊（bag.hps）任一人 < {opts.get("team_hp_min", TEAM_HP_MIN)}% → heal.heal_trip --no-return（小護士補整隊）+ team.form')
        for st, sd in sorted((d.get('steps') or {}).items()):
            if sd['kind'] == 'walk':
                print(f'  - 步 {st}：kind=walk（備援）：先讓遊戲自動巡路，quest.py 回 3 才走到 {sd["map"]}:{sd["xy"][0]},{sd["xy"][1]}'
                      f'（{sd.get("npc", "")}；walk.py 中斷外層重試）')
            elif d.get('turnin') and opts.get('pet_turnin'):
                print(f'  - 步 {st}：kind={sd["kind"]} → --pet-turnin：pet.py rest-all → team.disband → pet_turnin {d["turnin"]["kind"]} 5 人逐人交'
                      f'（pet_turnin 步 {list(d["turnin"]["steps"].get(st, ()))}）→ char.ensure DKBO → team.form；失敗 150')
            else:
                print(f'  - 步 {st}：kind={sd["kind"]} → 停下交人（115）' + ('（加 --pet-turnin 可自動交，未實機）' if d.get('turnin') else ''))
        if d.get('rest_pets'):
            print('  - 交寵物前：' + ('--pet-turnin：接取後第一片前 pet.py rest-all（任務寵改等待）' if opts.get('pet_turnin') else
                                      '任務寵要先改等待（手動 pet.py rest-all，或加 --pet-turnin 自動）'))
        if d.get('reward_pets'):
            print(f'  - 獎勵寵：{"、".join(d["reward_pets"])}（要丟用 --drop-reward / --confirm-drop，只丟 1 級）')
        if d.get('boss'):
            print(f'  - 有任務戰 / BOSS 戰：quest.py 預設模式打完回 37（滿 5 人 → 繼續）/ 38（不滿 → bossretry.py 落後者當隊長 5 人重打 + 重組，每任務最多 {BOSS_RETRY_MAX} 次；失敗 114）')
        if opts.get('dragon', False) and (opts.get('dragon_all') or d.get('dragon')):
            print(f'  - 每片前：龍王的守護（巡路 {d.get("walk_s")} 秒；buff 列看不到人形圖示才吃；第一次公共倉庫整疊取出，剩的留在 {LEADER} 背包，run 結束存回）')
        elif opts.get('dragon', False):
            print(f'  - 龍王的守護：不吃（巡路 {d.get("walk_s")} 秒 < {questdefs.DRAGON_WALK_MIN} 秒或沒量過；--dragon-all 才吃）')
        print(f'  - 迴圈：quest.py --task {d["track"]} --max-seconds {opts["slice_s"]}'
              + (f' --hp-check-min {opts.get("team_hp_min", TEAM_HP_MIN)} --hp-check-every {d.get("hp_every", opts.get("hp_every", HP_EVERY))}'
                 f'（片內：任務戰後 / 路上一般戰鬥每 N 場讀全隊 HP，偏低 41 → 補血續片）' if opts.get('team_hp_min', TEAM_HP_MIN) > 0 else '')
              + f'（≤ {opts["max_slices"]} 片、≤ {opts["max_min"]} 分），依退出碼分支；NPC 只有再見 40 / 信封發亮 → 背包滿刪白名單 + 領信續跑（153 / 154）')
        print('  - 收尾：quest.py「任務完成」（追蹤欄沒有該任務）→ 進度檔 + notes/quest-log.md（沒有該字樣才開詳情確認）')
        pre = questdefs.prereqs(d['id'])
        print(f'  - 逐人驗證（--verify {opts.get("verify", "risk")}）：' + {
            'risk': '本任務有風險事件（30/32/38/21/41、bossretry、重登、BOSS 後 HP 0、交寵物）才當場驗，否則延後到 run 結束批次驗'
                    + (f'；接取前先批次驗待驗的前置任務 {pre}' if pre else ''),
            'each': '完成後當場逐人驗（舊行為）', 'off': '不驗'}[opts.get('verify', 'risk')])
    if not opts.get('dragon', False):
        print('[龍王的守護] 預設不吃（要吃加 --dragon；只對 questdefs 標 dragon 的長巡路任務吃，--dragon-all 全吃）')
    else:
        print(f'[龍王的守護] 剩的整疊留在 {LEADER} 背包，run 結束（含失敗）存回公共倉庫；中斷沒存到 → 進度檔 dragon_in_bag，下次 questrun 補存')
    if opts.get('verify', 'risk') == 'risk':
        print('[逐人驗證] 沒風險事件的任務延後：全部任務結束後其他 4 人每人開一次詳情批次讀（失敗退出留進度檔，下次 run 結束再驗）')
    if opts.get('drop_reward'):
        print(f'[丟獎勵寵] 全部成功後：{"、".join(opts["drop_reward"])} 各 petdrop.drop all（名字完全相同、等級 ≤ {DROP_MAX_LEVEL}、非騎寵 / 第 1 格 / 出戰；失敗 151）')
    if opts['after'] == 'grind':
        print(f'[交接回去] 全部成功 → grind.py start --spot {opts["spot"]}（不重啟 follow）；失敗退出不恢復')
    else:
        print('[交接回去] --after none：不動')
    print('退出碼：108 逐人驗證 109 戰鬥設定 150 交寵物 151 丟獎勵寵 152 領獎窗關不掉 153 NPC 只有再見（背包 / 信箱都不是原因）154 背包滿自動處理失敗；110 preflight 111 交接/組隊 112 步驟卡住 113 片數/時間上限 114 BOSS後補人失敗 115 manual 116 不可逆對話 117 對話無進展 118 戰鬥卡住 119 接取失敗；9 驗證視窗 10 斷線')


# ---------------------------------------------------------------- 驅動器
class Run:
    def __init__(self, T, opts: dict):
        self.T, self.o = T, opts
        self.st = load_progress()
        self.st.setdefault('tasks', {})
        self.info: dict = {}
        self.warnings: list = []
        self.pending = None
        self.run_dragons = 0                                           # 本次 run 吃的龍王的守護（LAST.dragon_used；進度檔累計另放 dragon_used_total）
        self.task_dragons = 0                                          # 目前任務吃的（quest-log 摘要用）
        self.team_ok_at = 0.0                                          # 最近一次確認 5 人隊伍完整的時間（form 成功 / quest.py 37）；0 = 不新鮮
        self.mail_no_lost = False                                      # 信封發亮但信箱沒有「丟失的物品」（mail 112）→ 本次 run 不再因發亮開信箱
        self.hp_ok_at = 0.0                                            # 全隊 HP 確認夠的時間（讀了沒人偏低 / 剛補血）；有戰鬥 / 重登 / bossretry → 0（HP_FRESH_S）
        self.rested = None                                             # 本次 run 已 rest-all 過的任務 ID（do_turnin 不重做）
        self.risk: list = []                                           # 目前任務的風險事件（有 → 完成時當場逐人驗；沒有 → 延後批次驗）
        self.st.setdefault('verify_pending', {})                       # {任務 ID: 完成時間}：完成但還沒逐人驗（進度檔，失敗中斷也留著）

    # -- 共用 --
    def save(self):
        self.st['info'] = self.info
        save_progress(self.st)

    def fail(self, rc: int, msg: str, **kw) -> int:
        self.info.update(kw)
        self.info['msg'] = msg
        event(f'失敗 rc={rc}：{msg}')
        try:
            import errlog
            errlog.add(f'questrun：{msg}', source='questrun')
        except Exception:
            pass
        return rc

    def form(self, what: str, tries: int = FORM_TRIES) -> int:
        """team.form 原地重試（見 retry_form）；成功記 team_ok_at"""
        rc = retry_form(self.T, self.T.team_form, what, tries)
        if not rc:
            self.team_ok_at = time.time()
        return rc

    def regroup_after_split(self, tid) -> int:
        """BOSS / 連戰後隊伍散了（quest.py 30 / 32）：先讀全隊 HP（掉隊者多半被打飛回村、HP 0）→ 任一人 < team_hp_min 先補血（小護士補整隊）→
        team.form --regroup（解散重組）。2026-10-13 四寶玉之謎：DKBO3 / DKBO5 戰後掉隊，舊流程 team.form 沒加 --regroup、回 41 三次就失敗"""
        self.hp_ok_at = 0.0
        thr = self.o.get('team_hp_min', TEAM_HP_MIN)
        low = {}
        if thr > 0:
            rc, pct = self.T.team_hp()
            if rc in (uikit.EXIT_UNKNOWN_SCREEN, uikit.EXIT_HALT):
                return rc
            if not rc and pct:
                self.info['team_hp'] = pct
                low = {r: v for r, v in pct.items() if v is not None and v < thr}
                event(f'任務 {tid} 隊伍散了：全隊 HP {pct}')
        if low:
            event(f'任務 {tid} 隊伍散了：HP 偏低 {low} → 補血（小護士補整隊）後再 team.form --regroup')
            try:
                self.T.heal()
            except RuntimeError as e:
                return self.fail(EXIT_HANDOVER, f'補血失敗：{e}')
            self.info['heals'] = self.info.get('heals', 0) + 1
            self.hp_ok_at = time.time()
        fn = getattr(self.T, 'team_regroup', None) or self.T.team_form
        rc = retry_form(self.T, fn, f'任務 {tid} 隊伍散了（--regroup）')
        if not rc:
            self.team_ok_at = time.time()
        return rc

    def team_fresh(self) -> bool:
        """隊伍在 TEAM_FRESH_S 秒內確認過完整（中間沒有傳送 / 戰鬥）→ 不必再開切換面板"""
        return bool(self.team_ok_at) and time.time() - self.team_ok_at <= TEAM_FRESH_S

    def warn(self, msg: str):
        self.warnings.append(msg)
        event(f'警告：{msg}')

    def mark_risk(self, why: str):
        """記一筆本任務的風險事件（完成時要當場逐人驗）"""
        if why not in self.risk:
            self.risk.append(why)

    def hp_fresh(self) -> bool:
        return bool(self.hp_ok_at) and time.time() - self.hp_ok_at <= HP_FRESH_S

    def dragon_wanted(self, d) -> bool:
        """--dragon 且（--dragon-all 或 questdefs 標 dragon = 長巡路任務）"""
        return bool(self.o.get('dragon')) and (bool(self.o.get('dragon_all')) or bool((d or {}).get('dragon')))

    def ensure_dragon(self, d=None, force: bool = False):
        """隊長吃龍王的守護（第一次公共倉庫整疊取出 → 吃 1 顆 → 剩的留在 DKBO 背包，之後直接從背包吃；run 結束 dragon_return 才存回）；
        失敗只警告（沒有也能跑，只是會遇敵）；buff 列看到人形圖示就不吃、看不到就吃一顆（不看時間）。只對 dragon_wanted 的任務吃"""
        if not self.dragon_wanted(d):
            return
        active = self.T.dragon_active()                                # bag.buff_state：人形圖示在 = 還有效（不看時間）；2倍智慧果的 EXP 圖示不會誤判
        if not force and active:
            return
        if self.T.screen_state() == 'walking':                         # 2026-10-13 08:04：片「時間到」時遊戲還在自動巡路，開背包吃龍王途中抵達 NPC → 對話框蓋住背包（depot_use 90）
            event('龍王的守護：遊戲還在自動巡路（開背包途中抵達 NPC 會被對話框打斷）→ 這片先不吃，下一片再看')
            return
        have = bool(self.st.get('dragon_in_bag'))
        rc, info = self.T.dragon(have)
        info = info or {}
        if rc == BAG_ITEM and have:                                    # 進度檔說在 DKBO 背包、其實沒有（吃完了 / 人工存回）→ 改從公共倉庫取
            event('龍王的守護：進度檔記在 DKBO 背包但背包找不到 → 改從公共倉庫取出')
            self.st['dragon_in_bag'] = False
            rc, info = self.T.dragon(False)
            info = info or {}
        if rc:
            self.info['dragon_rc'] = rc
            if 'warn' in info or info.get('step') in ('use', 'verify'):
                self.st['dragon_in_bag'] = True                        # 取出後才失敗：龍王在 DKBO 背包，下次跳過取出、run 結束存回
            self.warn(f'龍王的守護失敗 rc={rc} {info}；這段不用龍王（會遇敵）')
            self.save()
            return
        if info.get('step') == 'skip':                                 # depot_use 關遇敵、等戰鬥結束後再讀 buff 列已有圖示（review §3.4：舊版照算「已吃」）
            event('龍王的守護：depot_use 讀到 buff 列已有人形圖示（questrun 剛才讀時多半在戰鬥 / 轉場）→ 沒吃，不計數')
            return
        self.st['dragon_in_bag'] = True                                # 剩的整疊留在 DKBO 背包（最後一顆吃完也無妨：存回時 92 = 背包沒有）
        self.st['last_eat'] = time.time()
        self.st['dragon_used'] = self.st.get('dragon_used', 0) + 1      # 進度檔累計（跨 run）
        self.run_dragons += 1                                           # 本次 run
        self.task_dragons += 1                                          # 本任務
        event(f'已吃龍王的守護（本次第 {self.run_dragons} 顆，累計 {self.st["dragon_used"]} 顆；剩的留在 {LEADER} 背包，run 結束存回公共倉庫）')
        self.save()

    def dragon_return(self, where: str) -> int:
        """進度檔記龍王在 DKBO 背包 → 整疊存回公共倉庫（借出的道具要還）。成功 / 背包已沒有（92）→ 清旗標；失敗只警告、旗標留著（下次 questrun 再存）"""
        if not self.st.get('dragon_in_bag'):
            return 0
        rc = self.T.dragon_store()
        if rc in (0, BAG_ITEM):
            self.st['dragon_in_bag'] = False
            event(f'{where}：' + ('龍王的守護剩的已存回公共倉庫' if rc == 0 else f'{LEADER} 背包已沒有龍王的守護（吃完了），不用存'))
        else:
            self.warn(f'{where}：龍王的守護存回公共倉庫失敗 bag rc={rc}（還在 {LEADER} 背包，下次 questrun 開頭 / 結束會再存）')
        self.save()
        return rc

    # -- 交接 --
    def handover(self) -> int:
        T = self.T
        if T.follow_active():
            event('follow 還在跑 → 停掉（已停用，只防呆）')
            T.follow_stop()
            if T.follow_active():
                return self.fail(EXIT_HANDOVER, 'follow 停不掉')
        rc = T.preflight()
        if rc == uikit.EXIT_UNKNOWN_SCREEN:                         # 不認得：先看是不是上次中斷留下的已知面板 / 對話框（清得掉才重驗；真的不認得照舊 9）
            if self.clear_leftovers('交接前（preflight 不認得）') != 'unknown':
                rc = T.preflight()
        if rc:
            return rc
        if self.clear_leftovers('交接前') == 'unknown':             # 上次中斷在 NPC 對話窗 / 背包面板等（HUD 不在，外掛面板打不開）：ESC / ✕ 關掉（不回答）
            return self.fail(uikit.EXIT_UNKNOWN_SCREEN, '交接前畫面不認得（疑似驗證視窗）→ 停手通知使用者（鐵則 5）')
        try:
            T.encounter_off_wait()
        except RuntimeError as e:
            return self.fail(EXIT_HANDOVER, f'關原地遇敵失敗：{e}')
        if self.clear_leftovers('戰鬥設定檢查前') == 'unknown':     # 2026-10-13 08:00 / 08:01：背包面板 / NPC 對話窗殘留 → ass 選不到頭像 / 外掛面板打不開（109）
            return self.fail(uikit.EXIT_UNKNOWN_SCREEN, '戰鬥設定檢查前畫面不認得（疑似驗證視窗）→ 停手通知使用者（鐵則 5）')
        rc = self.battle_gate('交接')                                   # 戰鬥已結束（上一步等過）才開外掛面板
        if rc:
            return rc
        # 當前角色 = DKBO 由 team.form 同一次讀切換面板時確認（不是才 char.ensure，team._finish）；不再另跑 char.current（2026-10-12：多開關 1～2 次面板）
        rc = self.form('交接')
        if rc:
            if rc in (uikit.EXIT_UNKNOWN_SCREEN, uikit.EXIT_HALT):
                return rc                                               # 驗證視窗 / 斷線透傳
            return self.fail(EXIT_HANDOVER, f'team.form 沒成功 rc={rc}（要滿 5 人）', team_rc=rc)
        return 0

    def clear_leftovers(self, where: str) -> str:
        """清掉上次中斷留下的對話框 / 已知面板（quest.clear_leftovers）→ 最後畫面狀態；有動到才記事件"""
        st = self.T.clear_screen()
        if st not in ('idle', 'walking'):
            event(f'{where}：清殘留後畫面是 {st}')
        return st

    def battle_gate(self, where: str) -> int:
        """戰鬥設定檢查（ass.battle_check：5 人自動戰鬥、DKBO 人物首次動作 風的精靈 打勾）；只改不對的勾選。
        --no-battle-check → 0。值讀不準只警告；9 / 10 透傳；其他非 0 → 109"""
        if not self.o.get('battle_check', True):
            return 0
        last = self.st.get('battle_ok_at') or 0
        if self.o.get('battle_cache', True) and last and 0 <= time.time() - last <= BATTLE_OK_S:
            event(f'{where}：戰鬥設定 {int((time.time() - last) / 60)} 分前查過 5 人 OK（{BATTLE_OK_S // 60} 分內、之後沒有重登 / bossretry）→ 沿用，不開外掛面板')
            return 0
        rc, sts, msg, info = self.T.battle_check()
        self.info['battle'] = {'rc': rc, 'changed': (info or {}).get('changed'), 'msg': msg}
        for r, st in (sts or {}).items():
            if 'first_unsure' in (st or {}):
                self.warn(f'{where}：{r} 人物首次動作讀到「{st["first_unsure"]}」，認不出是不是風的精靈（勾選照查；請找時間開外掛看一眼）')
        if (info or {}).get('changed'):
            event(f'{where}：戰鬥設定不對已修正並讀回確認 {info["changed"]}')
        if rc in (uikit.EXIT_UNKNOWN_SCREEN, uikit.EXIT_HALT):
            return rc
        if rc:
            return self.fail(EXIT_BATTLESET, f'{where}：戰鬥設定檢查失敗 ass rc={rc}（{(info or {}).get("role") or "?"}）：{msg}', battle_rc=rc)
        event(f'{where}：戰鬥設定 5 人 OK')
        self.st['battle_ok_at'] = time.time()
        self.save()
        return 0

    def br_kw(self) -> dict:
        """呼叫 bossretry 的額外參數（--no-battle-check 才傳 check=False；預設不傳，讓 bossretry 重打前自己查）"""
        return {} if self.o.get('battle_check', True) else {'check': False}

    def do_turnin(self, d, step) -> int:
        """--pet-turnin：交寵物步驟（defs.turnin）。rest-all → 解散 → pet_turnin 5 人逐人 → char.ensure DKBO → team.form。失敗 150"""
        T, tid, tdef = self.T, d['id'], d['turnin']
        steps = tdef['steps'].get(step) or tdef['steps'].get(min(tdef['steps']))
        event(f'任務 {tid} 步 {step}：--pet-turnin → rest-all → 解散 → pet_turnin {tdef["kind"]} 5 人（pet_turnin 步 {list(steps)}）')
        if self.rested == tid:                                         # 接取後（rest_pets）剛做過 rest-all：不重做（13～30 秒）
            rc = 0
            event(f'任務 {tid}：接取後已 rest-all 過 → 不重做')
        else:
            rc = T.pet_rest_all()
        if rc in (uikit.EXIT_UNKNOWN_SCREEN, uikit.EXIT_HALT):
            return rc
        if rc:
            return self.fail(EXIT_TURNIN, f'任務 {tid}：交寵物前 pet.py rest-all 失敗 rc={rc}' + rest_hint(rc), turnin={'stage': 'rest_all', 'rc': rc})
        rc = T.team_disband()
        if rc in (uikit.EXIT_UNKNOWN_SCREEN, uikit.EXIT_HALT):
            return rc
        if rc:
            return self.fail(EXIT_TURNIN, f'任務 {tid}：交寵物前解散隊伍失敗 rc={rc}', turnin={'stage': 'disband', 'rc': rc})
        self.team_ok_at = 0.0
        rc, res = T.pet_turnin(tdef['kind'], ALL_ROLES, steps)
        self.info['turnin'] = {'stage': 'turnin', 'rc': rc, 'roles': res}
        if rc in (uikit.EXIT_UNKNOWN_SCREEN, uikit.EXIT_HALT):
            return rc
        crc = T.char_ensure(LEADER)                                    # 失敗也先切回 DKBO（pet_turnin 不切回）
        if rc:
            return self.fail(EXIT_TURNIN, f'任務 {tid}：pet_turnin rc={rc}（{res}）；切回 {LEADER} rc={crc}', turnin=self.info['turnin'])
        if crc:
            return self.fail(EXIT_TURNIN, f'任務 {tid}：交完切回 {LEADER} 失敗 rc={crc}', turnin=self.info['turnin'])
        rc = self.form('交寵物後')
        if rc:
            return self.fail(EXIT_TURNIN, f'任務 {tid}：交完重組 team.form 失敗 rc={rc}', turnin=self.info['turnin'])
        event(f'任務 {tid}：5 人交寵物完成 {res}')
        return 0

    def drop_rewards(self) -> int:
        """--drop-reward：全部任務成功後丟指定獎勵寵（petdrop.drop all，只丟等級 ≤ DROP_MAX_LEVEL）。失敗 151"""
        for name in self.o.get('drop_reward') or []:
            event(f'丟獎勵寵：{name}（5 人，只丟名字完全相同且 ≤{DROP_MAX_LEVEL} 級）')
            rc, info = self.T.pet_drop(name, DROP_MAX_LEVEL)
            self.info.setdefault('drop', {})[name] = {'rc': rc, **(info or {})}
            if rc in (uikit.EXIT_UNKNOWN_SCREEN, uikit.EXIT_HALT):
                return rc
            if rc:
                return self.fail(EXIT_DROP, f'丟「{name}」失敗 petdrop rc={rc}（73 = 防護擋下：等級不是 1 / 讀不出 / 像騎寵 / 出戰…）', drop=self.info['drop'])
            event(f'丟「{name}」：丟了 {(info or {}).get("dropped", [])}，本來就沒有 {(info or {}).get("already", [])}')
        return 0

    # -- 任務 --
    def status_of(self, d) -> tuple:
        rc, s = self.T.task_status(d['detail'])
        return rc, s

    def bag_short(self, need: int, extra=None, free=None) -> tuple:
        """讀 5 人背包空格（free = 已讀好的就不再開背包）→ (rc, {角色: 空格}, {不足 need（+ extra[角色]）的角色: 空格})；讀不出的（None）不算不足"""
        if free is None:
            rc, free = self.T.bag_free(ALL_ROLES)
            if rc:
                return rc, free or {}, {}
        self.info['bag_free'] = free
        return 0, free, {r: v for r, v in free.items() if v is not None and v < need + (extra or {}).get(r, 0)}

    def make_room(self, need: int, where: str, extra=None, free=None) -> tuple:
        """背包空格不足 need 的人 → 只刪 bag.AUTO_PURGE（白名單）→ 重讀 → (rc, 仍不足 {角色: 空格})。rc = bag 的讀 / 刪退出碼（9 / 10 透傳）。
        extra = {角色: 多要的格數}（--dragon 時 DKBO 要多 1 格放龍王的守護）"""
        rc, free, short = self.bag_short(need, extra, free)
        if rc or not short:
            return rc, short
        event(f'{where}：背包空格不足 {need}：{short} → 自動刪白名單道具（bag.AUTO_PURGE）')
        prc, pinfo = self.T.bag_purge(sorted(short))
        self.info['purge'] = {'rc': prc, 'roles': {r: (i or {}).get('deleted') for r, i in (pinfo or {}).items()}}
        if prc:
            return prc, short
        event(f'{where}：已刪 {self.info["purge"]["roles"]}')
        rc, free, short = self.bag_short(need, extra)
        return rc, short

    def preflight_task(self, d) -> int:
        """任務開始前：背包空格（questdefs.bag_slots；--dragon 且這任務要吃、龍王還不在背包 → DKBO 多 1 格）+ 全隊 HP。
        兩樣都要讀時同一次開背包（bag.team_scan，review §5.3）；全隊 HP 在 HP_FRESH_S 內確認過、之間沒戰鬥 → 沿用（review §5.2）"""
        need = d.get('bag_slots') or 0
        extra = {LEADER: 1} if self.dragon_wanted(d) and not self.st.get('dragon_in_bag') else {}
        pre = None
        if need or extra:
            free = None
            if self.o.get('team_hp_min', TEAM_HP_MIN) > 0 and not self.hp_fresh():
                rc, scan = self.T.team_scan(ALL_ROLES, True, True)
                if rc in (uikit.EXIT_UNKNOWN_SCREEN, uikit.EXIT_HALT):
                    return rc
                pre = (rc, {r: (v or {}).get('hp') for r, v in (scan or {}).items()})
                if not rc and scan:
                    free = {r: (v or {}).get('free') for r, v in scan.items()}
            rc, short = self.make_room(need, f'{d["detail"]} 開始前', extra, free)
            if rc in (uikit.EXIT_UNKNOWN_SCREEN, uikit.EXIT_HALT):
                return rc
            if rc:
                return self.fail(EXIT_PREFLIGHT, f'讀背包空位 / 自動刪白名單道具失敗 bag rc={rc}', bag_rc=rc)
            if short:
                return self.fail(EXIT_PREFLIGHT, f'{d["detail"]} 要每人背包空 ≥{need} 格（questdefs.bag_slots，任務道具最多同時佔的格數'
                                 + (f'；{LEADER} 另 +1 放龍王的守護' if extra else '') + f'），刪完白名單仍不足：{short}', bag_short=short)
        return self.hp_gate('任務開始前', pre=pre)

    def recover_items(self, tid, why: str) -> int:
        """背包滿 → 任務道具進信箱的處理（不重置任務）：背包空格 < 1 的人先刪白名單道具 → mail.py 領「丟失的物品」。
        why='bye'（quest.py 40：NPC 只有再見）時，背包沒滿又沒有丟失信 = 不是這個原因 → 153 回報；
        why='glow'（信封發亮）時沒有丟失信只記住、不失敗。回 0 = 處理完可以續跑"""
        rc, short = self.make_room(1, f'任務 {tid} 背包 / 信箱處理')
        if rc in (uikit.EXIT_UNKNOWN_SCREEN, uikit.EXIT_HALT):
            return rc
        if rc:
            return self.fail(EXIT_BAGMAIL, f'任務 {tid}：背包滿處理失敗（讀空格 / 刪白名單 bag rc={rc}）', bag_rc=rc)
        if short:
            return self.fail(EXIT_BAGMAIL, f'任務 {tid}：背包仍是滿的 {short}（白名單沒有可刪的）→ 信箱領不進來，請人清背包', bag_short=short)
        mrc = self.T.mail_claim()
        self.info['mail_rc'] = mrc
        if mrc in (uikit.EXIT_UNKNOWN_SCREEN, uikit.EXIT_HALT):
            return mrc
        if mrc == 0:
            event(f'任務 {tid}：信箱「丟失的物品」已領（mail rc 0）→ 續跑')
            return 0
        if mrc == 112:                                                 # 有信但沒有「丟失」字樣 / 沒信：不是背包滿的問題
            self.mail_no_lost = True
            if why == 'bye':
                return self.fail(EXIT_BYE, f'任務 {tid}：NPC 只有「再見」，背包有空、信箱沒有丟失的物品 → 任務接不下去（條件不符？），請人看', quest_rc=40)
            event(f'任務 {tid}：信封發亮但沒有「丟失的物品」→ 不領，本次不再因發亮開信箱')
            return 0
        return self.fail(EXIT_BAGMAIL, f'任務 {tid}：信箱領取失敗 mail rc={mrc}（114 = 領了沒消失，背包還滿？）', mail_rc=mrc)

    def hp_gate(self, where: str, boss: bool = False, pre=None) -> int:
        """補血檢查（任務開始前、BOSS 戰後下一片之前）：隊長 HUD HP < --hp-min，或全隊（bag.hps）任一人 < --team-hp-min → heal 全隊（小護士補整隊）+ team.form。
        全隊讀不到（背包打不開 / 選不到角色）→ 只看隊長並記事件；某人 HP 讀不出 = 不知道，不單獨觸發補血。
        pre = (rc, {角色: %}) 呼叫端已讀好（team_scan）；非 BOSS 後且 HP_FRESH_S 內確認過、之間沒戰鬥 → 沿用不讀。
        boss=True（BOSS 戰後）有人 HP 0 或讀不出 → 記風險事件（任務完成時當場逐人驗）"""
        hp = self.T.hp_pct()
        self.info['hp_pct'] = hp
        low = {}
        if hp is not None and hp < self.o['hp_min']:
            low[LEADER] = hp
        read_ok = False
        if self.o.get('team_hp_min', TEAM_HP_MIN) > 0:
            if pre is None and not boss and self.hp_fresh():
                event(f'{where}：全隊 HP {time.time() - self.hp_ok_at:.0f} 秒前確認過、之間沒有戰鬥 → 沿用（不開背包）')
                rc, pct = 0, None                                      # 沿用不刷新 hp_ok_at（不然會一直沿用下去）
            else:
                rc, pct = pre if pre is not None else self.T.team_hp()
            if rc in (uikit.EXIT_UNKNOWN_SCREEN, uikit.EXIT_HALT):
                return rc
            if pct is not None:
                self.info['team_hp'] = pct
                if rc or not pct:
                    event(f'{where}：讀不到全隊 HP（bag rc={rc}）→ 只看隊長 HP {hp}%')
                    if boss:
                        self.mark_risk('BOSS 戰後讀不到全隊 HP')
                else:
                    read_ok = True
                    unread = [r for r, v in pct.items() if v is None]
                    low.update({r: v for r, v in pct.items() if v is not None and v < self.o['team_hp_min']})
                    event(f'{where}：全隊 HP {pct}' + (f'（讀不出 {unread}）' if unread else ''))
                    if boss and (unread or any(v == 0 for v in pct.values())):
                        self.mark_risk(f'BOSS 戰後 HP 0 / 讀不出 {[r for r, v in pct.items() if not v]}')
        if not low:
            if read_ok:
                self.hp_ok_at = time.time()
            return 0
        event(f'{where}：HP 偏低 {low}（隊長門檻 {self.o["hp_min"]}%、全隊門檻 {self.o.get("team_hp_min", TEAM_HP_MIN)}%）→ 補血（小護士補整隊）')
        return self.heal_form()

    def heal_form(self) -> int:
        """補血（小護士補整隊）→ team.form；失敗 111"""
        try:
            self.T.heal()
        except RuntimeError as e:
            return self.fail(EXIT_HANDOVER, f'補血失敗：{e}')
        self.info['heals'] = self.info.get('heals', 0) + 1
        self.hp_ok_at = time.time()                                    # 小護士補整隊 = 全滿
        rc = self.form('補血後')
        if rc:
            return self.fail(EXIT_HANDOVER, f'補血後 team.form 失敗 rc={rc}')
        return 0

    def special_step(self, d):
        """defs 有特殊步驟時讀目前步號 → (步號, kind, sd)；讀不到 / 沒有特殊步驟 → (None, 'default', None)"""
        if not d.get('steps'):
            return None, 'default', None
        if self.pending:                                               # 上一片 quest.py 回 3 時已讀到的步驟（不重讀）
            got, self.pending = self.pending, None
            return got
        step = self.T.read_step(d['track'])
        if step is not None and step != self.T.gone():
            sd = d['steps'].get(step)
            return step, (sd['kind'] if sd else 'default'), sd
        if step is None and len(d['steps']) >= d.get('steps_total', 0) and all(v.get('kind') == 'manual' for v in d['steps'].values()):
            # 步號讀不到、但這個任務每一步都是 manual（例：恐龍博士，追蹤文字「圖鑒抓狗，練至18級+」沒有步驟樣板）→ 當 manual 停下交人，
            # 不要落到 quest.py 去對話（2026-10-12 實機：quest.py 對吉魯「恐龍博士」按鈕空轉 → 117）
            return 0, 'manual', {'kind': 'manual'}
        return None, 'default', None

    def do_walk(self, d, step, sd) -> int:
        event(f'步 {step} kind=walk → 走到 {sd["map"]}:{sd["xy"]}')
        rc, info = questhandlers.walk_step(self.T, d['track'], sd, log=event, on_loop=self.ensure_dragon)
        self.info['walk'] = info
        if rc:
            return self.fail(EXIT_STEP, f'步 {step} walk 失敗：{info.get("msg")}', walk=info)
        return 0

    def opens(self, ts, n=1):
        ts['detail_opens'] = ts.get('detail_opens', 0) + n

    def run_task(self, d) -> int:
        T = self.T
        tid, track = d['id'], d['track']
        ts = self.st['tasks'].setdefault(str(tid), {})
        ts['detail_opens'] = 0
        self.risk = []
        if self.o.get('trust_progress', True) and ts.get('state') == 'done' and time.time() - ts.get('ended_ts', 0) < DONE_TRUST_S:
            event(f'任務 {tid}「{d["detail"]}」進度檔記錄已完成（{time.strftime("%H:%M:%S", time.localtime(ts["ended_ts"]))}）→ 直接跳過，不開詳情')
            ts['skipped'] = True
            return 0
        ts.pop('skipped', None)
        pend = [int(k) for k in (self.st.get('verify_pending') or {}) if int(k) in questdefs.prereqs(tid)]
        if pend:                                                       # 前置任務還沒逐人驗：有人沒完成前置 → 接不到這個任務（待接取 108），先批次驗
            rc = self.flush_verify(f'接取 {tid} 前（前置任務 {pend} 還沒逐人驗）')
            if rc:
                return rc
        rc = self.preflight_task(d)
        if rc:
            return rc
        if self.team_fresh():                                          # 交接剛組完（同一秒內連開 2 次切換面板，2026-10-12）→ 沿用
            event(f'接取前：{time.time() - self.team_ok_at:.0f} 秒前剛確認 5 人隊伍 → 不重開切換面板')
        else:
            rc = self.form('接取前')                                   # 接取 / 對話前一定先快速組隊；切換面板偶爾讀到 0 張卡片（rc 42）→ form 內原地重試
            if rc:
                return self.fail(EXIT_HANDOVER, f'接取前 team.form 失敗 rc={rc}')
        # 整個任務只開一次詳情：同一趟捲動讀狀態（已完成 → 跳過、進行中 → 續跑、待接取 → 接取）
        rc, state = T.accept(d['detail'])
        self.opens(ts)
        if rc in (uikit.EXIT_UNKNOWN_SCREEN, uikit.EXIT_HALT):
            return rc
        if rc:
            return self.fail(EXIT_ACCEPT, f'接取「{d["detail"]}」失敗 questdetail rc={rc}', accept_rc=rc)
        event(f'任務 {tid}「{d["detail"]}」詳情結果：{state}')
        if state == 'done':
            ts.update(state='done', skipped=True, ended_ts=time.time())
            event(f'任務 {tid} 已完成，跳過')
            self.save()
            if self.o.get('verify_skipped') and not ts.get('all_done'):
                return self.verify_many([d])
            return 0
        t0 = time.time()
        ts.update(state='running', started=time.strftime('%H:%M:%S'), slices=0, all_done=False)
        self.save()
        if state == 'accepted':
            self.team_ok_at = 0.0                                      # 傳送過 → 之前的確認不算
            rc = self.form('接取後')                                    # 傳送後確認隊伍還在
            if rc:
                return self.fail(EXIT_HANDOVER, f'接取後 team.form 失敗 rc={rc}')
            event(f'任務 {tid} 已接取（不重開詳情，直接點追蹤欄卡片）')
        if self.o.get('pet_turnin') and d.get('rest_pets'):            # 卡坦的願望：隊長一次交，交前任務寵都要等待（10-10 一隻出戰 → 按完成 21 次不前進）
            rc = T.pet_rest_all()
            if rc in (uikit.EXIT_UNKNOWN_SCREEN, uikit.EXIT_HALT):
                return rc
            if rc:
                return self.fail(EXIT_TURNIN, f'任務 {tid}：交寵物前 pet.py rest-all 失敗 rc={rc}' + rest_hint(rc), turnin={'stage': 'rest_all', 'rc': rc})
            self.rested = tid
            event(f'任務 {tid}：--pet-turnin → 5 人任務寵已改等待（rest-all）')
        team_retry = 0
        rewarps = 0
        relogins = 0
        boss_retries = 0
        reward_retries = 0
        bye_recovers = 0
        hp_lows = 0
        turnin_tried = False
        for k in range(self.o['max_slices']):
            if time.time() - t0 > self.o['max_min'] * 60:
                return self.fail(EXIT_SLICES, f'任務 {tid} 超過 {self.o["max_min"]} 分鐘仍未完成')
            ts['slices'] = k + 1
            self.ensure_dragon(d)
            from_pending = self.pending is not None
            step, kind, sd = self.special_step(d)
            if kind == 'manual' and d.get('turnin') and self.o.get('pet_turnin') and not turnin_tried:
                turnin_tried = True                                    # 每任務只試一次：交完還停在 manual = 有人沒交到 → 下一圈 115
                rc = self.do_turnin(d, step)
                if rc:
                    return rc
                rc, s2 = self.status_of(d)
                self.opens(ts)
                if rc:
                    return rc if rc in (uikit.EXIT_UNKNOWN_SCREEN, uikit.EXIT_HALT) else self.fail(EXIT_PREFLIGHT, f'{d["detail"]} 交寵物後讀狀態失敗 rc={rc}')
                if s2 == DONE:
                    ts.update(state='done', ended=time.strftime('%H:%M:%S'), ended_ts=time.time(), secs=int(time.time() - t0))
                    self.save()
                    event(f'任務 {tid}「{d["detail"]}」交寵物後已完成')
                    self.mark_risk('交寵物（解散逐人交）')                 # 5 人各自交，有人沒交到要當場抓
                    return self.task_done(d, ts)
                continue
            if kind == 'manual':
                return self.fail(EXIT_MANUAL, f'任務 {tid} 步 {step} kind=manual：停下交人', step=step)
            if kind == 'walk' and from_pending:                         # 自動巡路優先：quest.py 回 3（追蹤沒反應）才用 walk 備援（2026-10-11 實測點追蹤會傳送 + 巡路）
                rc = self.do_walk(d, step, sd)
                if rc:
                    return rc
            qargs = ['--task', track, '--max-seconds', self.o['slice_s']]
            if self.team_fresh():
                qargs.append('--team-fresh')                           # 剛驗過隊伍：quest.py 開始前不再開切換面板（之後的領獎後 / 任務戰後檢查照舊）
            if self.o.get('team_hp_min', TEAM_HP_MIN) > 0:
                qargs += ['--hp-check-min', self.o.get('team_hp_min', TEAM_HP_MIN),   # 片內戰鬥後驗全隊 HP（四寶玉之謎連戰被打死踢隊）
                          '--hp-check-every', d.get('hp_every', self.o.get('hp_every', HP_EVERY))]   # 路上一般戰鬥每 N 場才讀（review §5.4）
            rc, tail = T.quest(qargs, self.o['slice_s'] + WALK_CAP_S + 120)
            self.team_ok_at = time.time() if rc == 37 else 0.0         # 37 = quest.py 剛驗過滿 5 人；其他結束方式隊伍狀態未知
            if battles_in(tail) != 0:                                  # 打過仗（或 quest.py 沒說）→ 全隊 HP 不能沿用
                self.hp_ok_at = 0.0
            walked = walk_secs(tail)
            if walked:
                t0 += walked                                           # 自動巡路 = 任務進行中：不計入 --max-min（quest.py 自己的 slice 時限也不計巡路）
                event(f'任務 {tid} 本片自動巡路 {walked} 秒，不計入時限')
            self.info['quest_rc'] = rc
            ts['last_rc'] = rc
            act = classify(rc, tail)
            event(f'任務 {tid} 第 {k + 1} 片 quest.py 退出碼 {rc}（{act}）')
            if act == 'verify':
                T.snap('questrun-verify')
                return self.fail(uikit.EXIT_UNKNOWN_SCREEN, 'quest.py 看到不認得的畫面（疑似驗證視窗）→ 停手通知使用者（鐵則 5）', quest_rc=rc)
            if act == 'halt':
                return uikit.EXIT_HALT
            if act in ('check', 'boss') and not self.mail_no_lost and T.mail_glow():   # 信封發亮 = 可能有道具因背包滿進了信箱 → 先騰空位再領（不等 NPC 只剩再見）
                event(f'任務 {tid}：主畫面信封發亮（可能是背包滿、任務道具進了信箱）→ 背包 / 信箱處理')
                rc2 = self.recover_items(tid, 'glow')
                if rc2:
                    return rc2
            if act == 'reward_stuck':                                   # quest.py 18：領獎窗按確認 3 次沒關 → 重試關窗一次，成功續跑，否則停手交人
                reward_retries += 1
                if reward_retries > REWARD_RETRY_MAX:
                    T.snap('questrun-reward-stuck')
                    return self.fail(EXIT_REWARD, f'任務 {tid}：領獎視窗關不掉（已重試 {REWARD_RETRY_MAX} 次），請人工處理', quest_rc=rc, reward_retry=reward_retries - 1)
                rr = T.reward_retry()
                event(f'任務 {tid}：quest.py 18 領獎窗關不掉 → 重試關窗（第 {reward_retries}/{REWARD_RETRY_MAX} 次）：{rr}')
                if rr == 'stuck':
                    T.snap('questrun-reward-stuck')
                    return self.fail(EXIT_REWARD, f'任務 {tid}：領獎視窗關不掉，請人工處理', quest_rc=rc, reward_retry=reward_retries)
                continue
            if act == 'hp_low':                                        # quest.py 41：片內戰鬥後全隊 HP 偏低 → 補血 + 重組再續片
                hp_lows += 1
                self.mark_risk('片內 HP 偏低補血（quest.py 41）')
                if hp_lows > HP_LOW_MAX:
                    return self.fail(EXIT_HANDOVER, f'任務 {tid}：片內 HP 偏低已補血 {HP_LOW_MAX} 次仍一直偏低（quest.py 41），停手交人', quest_rc=rc)
                event(f'任務 {tid}：quest.py 41 片內戰鬥後全隊 HP 偏低 → 補血（第 {hp_lows}/{HP_LOW_MAX} 次）後續片')
                rc = self.heal_form()
                if rc:
                    return rc
                continue
            if act == 'bye':                                           # quest.py 40：任務 NPC 只有「再見」→ 查背包滿 / 信箱（2026-10-13 薩頓家的頭盔進信箱）
                bye_recovers += 1
                if bye_recovers > BYE_RECOVER_MAX:
                    T.snap('questrun-bye')
                    return self.fail(EXIT_BYE, f'任務 {tid}：NPC 只有「再見」，背包 / 信箱處理 {BYE_RECOVER_MAX} 次後仍一樣 → 任務接不下去，請人看', quest_rc=rc)
                event(f'任務 {tid}：quest.py 40 任務 NPC 只有「再見」→ 查背包滿 / 信箱（第 {bye_recovers}/{BYE_RECOVER_MAX} 次）')
                rc = self.recover_items(tid, 'bye')
                if rc:
                    return rc
                continue
            if act == 'irrev':
                T.snap('questrun-irrev')
                return self.fail(EXIT_IRREV, f'任務 {tid}：對話含不可逆字樣（quest.py 39），沒按、對話框維持開著，請人看圖', quest_rc=rc)
            if act == 'stall':
                return self.fail(EXIT_STALL, f'任務 {tid}：對話無進展（quest.py 33）', quest_rc=rc)
            if act == 'select_loop':                                   # 2026-10-12 卡坦步 2：雞還沒抓齊就按完成，對話 ↔ 選擇對象循環 54 次
                why = '（交寵物任務：這一步要交的寵物沒湊齊 / 等級不夠 / 還在出戰？）' if (d.get('turnin') or d.get('rest_pets')) else '（任務條件不符？）'
                return self.fail(EXIT_STALL, f'任務 {tid}：對話 ↔ 選擇對象面板循環沒進展（quest.py 29）{why}，停手交人', quest_rc=rc)
            if act == 'battle':
                return self.fail(EXIT_BATTLE, f'任務 {tid}：完整戰鬥自動戰鬥卡住（quest.py 25）', quest_rc=rc)
            if act == 'vs_stuck':                                      # quest.py 42：快速戰鬥 VS 牌卡死（刷新無效）→ 全員重登
                if relogins >= RELOGIN_MAX:
                    return self.fail(EXIT_STEP, f'任務 {tid}：VS 牌卡死（quest.py 42），本任務已全員重登 {relogins} 次，停手交人', quest_rc=rc)
                relogins += 1
                rc2 = self.relogin_recover(tid, '快速戰鬥 VS 牌卡死（quest.py 42）', relogins)
                if rc2:
                    return rc2
                rewarps = 0
                continue
            if act in ('knocked', 'boss_team'):                         # 38 BOSS 後不滿 5 人 / 21 被打飛 → bossretry 自動補人（psa-team-check-after-boss）
                what = '被打飛回村（quest.py 21）' if act == 'knocked' else 'BOSS 戰後隊伍不滿 5 人（quest.py 38）'
                self.mark_risk(what)
                if not self.o.get('boss_retry', True):
                    return self.fail(EXIT_TEAM, f'任務 {tid}：{what}；--no-boss-retry，請依 psa-team-check-after-boss 手動處理', quest_rc=rc)
                if boss_retries >= BOSS_RETRY_MAX:
                    return self.fail(EXIT_TEAM, f'任務 {tid}：{what}；bossretry 已用 {boss_retries} 次，停手交人', quest_rc=rc)
                boss_retries += 1
                event(f'任務 {tid}：{what} → bossretry 第 {boss_retries}/{BOSS_RETRY_MAX} 次')
                brc, binfo = T.boss_retry(track, **self.br_kw())
                self.info.setdefault('boss_retry', []).append(binfo)
                self.st['battle_ok_at'] = 0                            # bossretry 換過隊長、打過仗 → 戰鬥設定 / HP 都不沿用
                self.hp_ok_at = 0.0
                if brc in (uikit.EXIT_UNKNOWN_SCREEN, uikit.EXIT_HALT):
                    return brc
                if brc:
                    return self.fail(EXIT_TEAM, f'任務 {tid}：{what}；bossretry 退出碼 {brc}：{(binfo or {}).get("msg", "")}', quest_rc=rc, boss_retry_rc=brc)
                self.team_ok_at = time.time()                          # bossretry 最後 team.check 滿 5 人
                rc = self.hp_gate(f'任務 {tid} 補人後', boss=True)
                if rc:
                    return rc
                continue
            if act == 'boss':
                event(f'任務 {tid}：BOSS 戰贏且滿 5 人，下一片')
                team_retry = 0
                rc = self.hp_gate(f'任務 {tid} BOSS 戰後', boss=True)  # 連戰不補血 → 隊員被打死踢隊（2026-10-12 四寶玉之謎 4 次 38）
                if rc:
                    return rc
                continue
            if act == 'team':
                self.mark_risk(f'隊伍散了（quest.py {rc}）')
                if team_retry >= 3:                                    # 對話剛收起時切換面板偶爾打不開（2026-10-11 小豬愛情故事最後一段），多給幾次
                    return self.fail(EXIT_HANDOVER, f'任務 {tid}：隊伍檢查連續失敗（quest.py {rc}）', quest_rc=rc)
                team_retry += 1
                rc2 = self.regroup_after_split(tid)
                if rc2:
                    return self.fail(EXIT_HANDOVER, f'任務 {tid}：team.form 失敗 rc={rc2}')
                continue
            if act == 'no_track':
                st2, kind2, sd2 = self.special_step(d)
                if kind2 == 'walk':
                    self.pending = (st2, kind2, sd2)
                    continue                                           # 下一圈 special_step 會走 walk
                if rewarps >= 2 and relogins < RELOGIN_MAX and self.T.vs_stuck():   # 刷新 + 點追蹤都無效且全隊頭上 VS 牌卡住（無戰鬥介面）→ 主動全員重登（碧青 12 樓 2026-10-12）
                    relogins += 1
                    rc2 = self.relogin_recover(tid, f'VS 牌卡住（無戰鬥介面、刷新 {rewarps} 次無效）', relogins)
                    if rc2:
                        return rc2
                    rewarps = 0
                    continue
                if rewarps < 6:                                        # 自動巡路停住後角色凍住（琉璃洞窟 / 奇喀喀村 2026-10-12）：先刷新角色解凍，
                    rewarps += 1                                       # 再（若站在出口格上沒換圖）踏出再踏回，然後重點追蹤
                    try:
                        r = self.T.unfreeze() or self.T.unstick_exit()
                        event(f'任務 {tid}：追蹤沒反應 → 刷新角色' + (f' + 出口格重踏 → {r[0]}:{r[1]},{r[2]}' if r else '') + f'，重點追蹤（第 {rewarps} 次）')
                    except Exception as e:                             # noqa: BLE001
                        event(f'任務 {tid} 解凍失敗：{e}')
                    continue
                return self.fail(EXIT_STEP, f'任務 {tid}：追蹤沒反應（quest.py 3）且目前步驟（{st2}）沒有 walk 設定', quest_rc=rc)
            if act in ('check', 'gone'):
                if act == 'check' and any('任務完成' in str(x) for x in tail):   # quest.py：領獎後追蹤欄掃完沒有該任務 → 完成，不開詳情
                    ts.update(state='done', ended=time.strftime('%H:%M:%S'), ended_ts=time.time(), secs=int(time.time() - t0))
                    self.save()
                    event(f'任務 {tid}「{d["detail"]}」已完成（quest.py 任務完成；{int(time.time() - t0)} 秒、{k + 1} 片）')
                    return self.task_done(d, ts)
                if act == 'check' and time_up(tail):                    # quest.py 只是 slice 時間到（任務還在追蹤欄、沒說完成）：不開詳情，直接下一片；
                    continue                                           # 真的完成會在下一片由 quest.py 回 5（追蹤欄沒有該任務）或「任務完成」→ 那時才讀詳情確認
                if act == 'check' and early_end(tail):                 # 「步驟結束 …，提前結束」：還有下一步 → 直接下一片（真的完成時下一片回「任務完成」/ 5）
                    event(f'任務 {tid}：quest.py 步驟結束提前收片 → 不開詳情，直接下一片')
                    continue
                rc, s2 = self.status_of(d)                              # 沒有「任務完成」字樣、也不是時間到 / 提前結束（模糊）→ 才讀一次詳情
                self.opens(ts)
                if rc:
                    return rc if rc in (uikit.EXIT_UNKNOWN_SCREEN, uikit.EXIT_HALT) else self.fail(EXIT_PREFLIGHT, f'{d["detail"]} 完成確認讀狀態失敗 rc={rc}')
                if s2 == DONE:
                    ts.update(state='done', ended=time.strftime('%H:%M:%S'), ended_ts=time.time(), secs=int(time.time() - t0))
                    self.save()
                    event(f'任務 {tid}「{d["detail"]}」已完成（{int(time.time() - t0)} 秒、{k + 1} 片）')
                    return self.task_done(d, ts)
                if act == 'gone':
                    return self.fail(EXIT_STEP, f'任務 {tid}：quest.py 找不到追蹤列表上的任務，詳情狀態是 {s2}', quest_rc=rc, status=s2)
                if s2 == PENDING:
                    return self.fail(EXIT_STEP, f'任務 {tid}：詳情狀態是待接取（沒接成？）', status=s2)
                continue                                               # 進行中：下一片
            if rc == 19:                                               # quest.py 已「刷新角色 + 點地面 / 重點追蹤」解卡 3 次仍卡
                if rewarps < 2:                                        # 先試刷新 + 走上最近的換圖出口（出口附近打轉），再重點追蹤
                    rewarps += 1
                    try:
                        r = self.T.unstick_exit()
                        event(f'任務 {tid}：巡路卡住（quest.py 19）→ 刷新 + 走上附近出口 → {r}，重點追蹤（第 {rewarps} 次）')
                    except Exception as e:                             # noqa: BLE001
                        event(f'任務 {tid} 走上附近出口失敗：{e}')
                        r = None
                    if r:
                        continue
                if relogins < RELOGIN_MAX:                             # 解卡全無效 → 全員重登洗掉伺服器端狀態（登入只按「登錄」，鐵則 2）
                    relogins += 1
                    rc2 = self.relogin_recover(tid, '自動巡路卡住（quest.py 19：刷新角色 + 點地面 + 走出口都無效）', relogins)
                    if rc2:
                        return rc2
                    rewarps = 0
                    continue
                return self.fail(EXIT_STEP, f'任務 {tid}：自動巡路卡住，解卡與全員重登 {relogins} 次都無效（quest.py 19），請人看 snap walk-stuck', quest_rc=rc)
            return self.fail(EXIT_STEP, f'任務 {tid}：quest.py 非預期退出碼 {rc}', quest_rc=rc)
        return self.fail(EXIT_SLICES, f'任務 {tid}：{self.o["max_slices"]} 片後仍未完成')

    def relogin_recover(self, tid, why: str, n: int) -> int:
        """全員重登（relogin.py --confirm，stuck=True）→ 隊伍檢查（relogin 自己 team.check；105 = 隊伍不對 → team.form --regroup）→ 關遇敵 → 戰鬥設定檢查。
        回 0 = 可以續片；9 / 10 透傳；其他 112"""
        T = self.T
        event(f'任務 {tid}：{why} → 全員重登 relogin.py --confirm（第 {n}/{RELOGIN_MAX} 次；登入畫面只按已帶入帳密的「登錄」）')
        self.mark_risk('全員重登')
        self.st['battle_ok_at'] = 0                                    # 重登過 → 戰鬥設定 / HP / 隊伍都不沿用
        self.hp_ok_at = 0.0
        self.team_ok_at = 0.0
        rr = T.relogin()
        event(f'任務 {tid}：全員重登 rc={rr}')
        if rr in (uikit.EXIT_UNKNOWN_SCREEN, uikit.EXIT_HALT):
            return rr
        if rr not in (0, RELOGIN_TEAM):
            return self.fail(EXIT_STEP, f'任務 {tid}：{why}；全員重登失敗 rc={rr}（relogin 100～108 / 11 見 relogin.py）', relogin_rc=rr)
        if rr == RELOGIN_TEAM:                                         # 重登進遊戲了但隊伍不對 → 解散重組
            fn = getattr(T, 'team_regroup', None) or T.team_form
            rc = retry_form(T, fn, f'任務 {tid} 重登後（--regroup）')
            if rc:
                return rc if rc in (uikit.EXIT_UNKNOWN_SCREEN, uikit.EXIT_HALT) else self.fail(EXIT_STEP, f'任務 {tid}：重登後重組隊伍失敗 rc={rc}', relogin_rc=rr)
        self.team_ok_at = time.time()
        try:
            T.encounter_off_wait()                                     # 重登後外掛原地遇敵狀態未知 → 關掉（任務中要關）
        except RuntimeError as e:
            self.warn(f'重登後關原地遇敵失敗：{e}')
        return self.battle_gate(f'任務 {tid} 重登後')

    def task_done(self, d, ts) -> int:
        """任務完成後的逐人驗證（review §2-B）：--verify each = 當場驗；risk（預設）= 本任務有風險事件（30 / 32 / 38 / 21 / 41 / bossretry / 重登 /
        BOSS 後 HP 0 / 交寵物）才當場驗，否則記進 verify_pending（進度檔），run 結束 / 依賴它的任務接取前批次驗；off = 不驗"""
        mode = self.o.get('verify', 'risk')
        if mode == 'off':
            return 0
        tid = d['id']
        if mode == 'each' or self.risk:
            if mode != 'each':
                event(f'任務 {tid}：本任務有風險事件 {self.risk} → 當場逐人驗')
            return self.verify_many([d])
        self.st.setdefault('verify_pending', {})[str(tid)] = time.time()
        self.save()
        event(f'任務 {tid}：沒有風險事件 → 逐人驗證延後（run 結束 / 依賴它的任務接取前一次批次驗）')
        return 0

    def flush_verify(self, where: str) -> int:
        """把 verify_pending 的任務一次批次逐人驗（每人開一次詳情讀全部）；驗過的移出清單。超過 DONE_TRUST_S 的舊紀錄丟掉（可能轉生 / 封印書重置過）"""
        pend = self.st.setdefault('verify_pending', {})
        if not pend or self.o.get('verify', 'risk') == 'off':
            return 0
        now = time.time()
        for k in [k for k, t in pend.items() if now - (t or 0) > DONE_TRUST_S or not questdefs.get(int(k))]:
            pend.pop(k, None)
            event(f'{where}：待驗任務 {k} 已超過 {DONE_TRUST_S // 3600} 小時（或不認得），不驗、移出清單')
        ds = [questdefs.get(int(k)) for k in pend]
        if not ds:
            self.save()
            return 0
        event(f'{where}：批次逐人驗證 {[d["id"] for d in ds]}（其他 4 人每人開一次詳情讀全部）')
        rc = self.verify_many(ds)
        for d in ds:
            if self.st['tasks'].get(str(d['id']), {}).get('all_done'):
                pend.pop(str(d['id']), None)
        self.save()
        return rc

    def verify_many(self, ds) -> int:
        """逐人驗證（隊長本人剛確認過，不再讀）：其他 4 人各開一次詳情讀 ds 全部任務 → 有人不是「已完成」→ 進行中的 bossretry --who 落後者 → 再讀那幾個人那幾個任務；
        仍不行 / 讀不到 / 待接取 → 108"""
        T = self.T
        roles = [r for r in ALL_ROLES if r != LEADER]
        todo = list(ds)
        for attempt in range(2):                                    # 0 = 第一次驗；1 = bossretry 補人後再驗
            ids = [d['id'] for d in todo]
            rc, res = T.status_all([d['detail'] for d in todo], roles)
            self.info.setdefault('verify', []).append({'tasks': ids, 'roles': roles, 'rc': rc, 'res': res})
            if rc in (uikit.EXIT_UNKNOWN_SCREEN, uikit.EXIT_HALT):
                return rc
            unread = [r for r in roles if not (res or {}).get(r)]
            if unread:
                return self.fail(EXIT_LAGGARD, f'任務 {ids}：逐人驗證讀不到 {unread} 的任務詳情（status_all rc={rc}），無法確認是否都完成；不盲打', laggards=unread)
            lags = []
            for d in todo:
                sts = {r: res[r].get(d['detail']) for r in roles}
                lag = [r for r in roles if sts[r] != DONE]
                event(f'任務 {d["id"]}「{d["detail"]}」逐人驗證{"（補人後）" if attempt else ""}：{sts}')
                if not lag:
                    self.st['tasks'].setdefault(str(d['id']), {})['all_done'] = True
                    continue
                pend = [r for r in lag if sts[r] != DOING]
                if pend:
                    self.info['laggards'] = lag
                    self.save()
                    return self.fail(EXIT_LAGGARD, f'任務 {d["id"]}：{pend} 的狀態是 {[sts[r] for r in pend]}（不是進行中，bossretry 幫不上），停手交人', laggards=lag)
                lags.append((d, lag))
            self.save()
            if not lags:
                return 0
            self.info['laggards'] = lags[0][1] if len(lags) == 1 else {d['id']: lag for d, lag in lags}
            if attempt or not self.o.get('boss_retry', True):
                why = '補人後仍沒完成' if attempt else '--no-boss-retry'
                return self.fail(EXIT_LAGGARD, f'任務 {[(d["id"], lag) for d, lag in lags]} 仍是進行中（{why}），停手交人', laggards=self.info['laggards'])
            for d, lag in lags:
                event(f'任務 {d["id"]}：{lag} 沒完成 → bossretry --who（落後者當隊長組 5 人重打 → 切回 DKBO 重組）')
                brc, binfo = T.boss_retry(d['track'], who=lag, **self.br_kw())
                self.info.setdefault('boss_retry', []).append(binfo)
                self.st['battle_ok_at'] = 0
                self.hp_ok_at = 0.0
                if brc in (uikit.EXIT_UNKNOWN_SCREEN, uikit.EXIT_HALT):
                    return brc
                if brc:
                    return self.fail(EXIT_LAGGARD, f'任務 {d["id"]}：{lag} 沒完成，bossretry 退出碼 {brc}：{(binfo or {}).get("msg", "")}', laggards=lag, boss_retry_rc=brc)
                self.team_ok_at = time.time()                          # bossretry 最後 team.check 滿 5 人
            todo = [d for d, _ in lags]
            roles = [r for r in ALL_ROLES if any(r in lag for _, lag in lags)]
        return EXIT_LAGGARD

    def write_log(self, d, t0: float):
        ts = self.st['tasks'].get(str(d['id']), {})
        if ts.get('skipped'):
            return
        lines = [f'\n## {d["id"]} {d["detail"]} — questrun.py 自動跑完（{time.strftime("%Y-%m-%d %H:%M")}）',
                 f'- 任務詳情開啟 {ts.get("detail_opens")} 次；耗時 {int(time.time() - t0)} 秒（{ts.get("started")}～{ts.get("ended")}），quest.py {ts.get("slices")} 片，最後退出碼 {ts.get("last_rc")}；'
                 f'龍王的守護本任務吃 {self.task_dragons} 顆（本次 run 共 {self.run_dragons} 顆；剩的留在 {LEADER} 背包，run 結束存回公共倉庫）',
                 '- 手動介入：0 次（若有，人工在這裡補記）']
        if self.warnings:
            lines.append('- 警告：' + '；'.join(self.warnings))
        try:
            with open(QUEST_LOG, 'a', encoding='utf-8') as f:
                f.write('\n'.join(lines) + '\n')
        except OSError:
            pass


def parse_names(text) -> list:
    """'左迪洛斯,巴朵蘭恩' / 'a、b' / list → 去空白、去重的名字清單（保留順序）"""
    if not text:
        return []
    items = text if isinstance(text, (list, tuple)) else str(text).replace('、', ',').replace('，', ',').split(',')
    return list(dict.fromkeys(x.strip() for x in items if x and x.strip()))


def run(ids=None, dry_run: bool = False, after: str = 'grind', tools=None, use_dragon: bool = False, spot: str = DEFAULT_SPOT,
        max_slices: int = MAX_SLICES, slice_s: int = SLICE_S, max_min: int = MAX_MIN, hp_min: int = HP_MIN, trust_progress: bool = True,
        team_hp_min: int = TEAM_HP_MIN, boss_retry: bool = True, verify_all: bool = True, verify_skipped: bool = False,
        battle_check: bool = True, pet_turnin: bool = False, drop_reward=None, confirm_drop=None,
        verify: str = 'risk', dragon_all: bool = False, hp_every: int = HP_EVERY, battle_cache: bool = True) -> int:
    """use_dragon 預設 False（2026-10-12 起不吃龍王的守護；--dragon 只對 questdefs 標 dragon 的長巡路任務吃，dragon_all 全吃）。
    verify = risk（預設：風險事件才當場逐人驗，其餘 run 結束批次驗）/ each（舊行為：每任務完成當場驗）/ off；verify_all=False 相容舊參數 = off。
    drop_reward 要和 confirm_drop 名單完全相同才會丟（不可逆）"""
    LAST.clear()
    if not verify_all:
        verify = 'off'
    if verify not in VERIFY_MODES:
        print(f'questrun：--verify 要 {"/".join(VERIFY_MODES)}', file=sys.stderr)
        return uikit.EXIT_USAGE
    drops, confirms = parse_names(drop_reward), parse_names(confirm_drop)
    if drops and sorted(drops) != sorted(confirms):
        print(f'questrun：--drop-reward {drops} 要配同樣的 --confirm-drop（現在是 {confirms}）；不可逆動作，名單不一致就不跑', file=sys.stderr)
        return uikit.EXIT_USAGE
    bad_drop = [n for n in drops if n in uikit.MOUNTS or uikit.is_mount_like(n)]
    if bad_drop:
        print(f'questrun：--drop-reward 不能是騎寵 {bad_drop}', file=sys.stderr)
        return uikit.EXIT_USAGE
    defs, bad = questdefs.resolve(ids)
    if bad:
        print(f'questrun：不認得的任務 ID {bad}（questdefs 有：{questdefs.DEFAULT_ORDER}）', file=sys.stderr)
        return uikit.EXIT_USAGE
    if after not in ('grind', 'none'):
        print('questrun：--after 要 grind 或 none', file=sys.stderr)
        return uikit.EXIT_USAGE
    opts = dict(after=after, dragon=use_dragon, spot=spot, max_slices=max_slices, slice_s=slice_s, max_min=max_min, hp_min=hp_min, trust_progress=trust_progress,
                team_hp_min=team_hp_min, boss_retry=boss_retry, verify=verify, verify_skipped=verify_skipped,
                battle_check=battle_check, pet_turnin=pet_turnin, drop_reward=drops, dragon_all=dragon_all, hp_every=hp_every,
                battle_cache=battle_cache)
    if dry_run:
        print_plan(defs, opts)
        return 0
    T = tools or Tools()
    r = Run(T, opts)
    event(f'開始：任務 {[d["id"] for d in defs]}，選項 {opts}')
    rc = r.handover()
    done = []
    if not rc and r.st.get('dragon_in_bag') and not use_dragon:
        r.dragon_return('開始（上次 run 沒存回）')                    # 這次不吃 → 先把上次留在 DKBO 背包的龍王存回公共倉庫
    if not rc:
        for d in defs:
            t0 = time.time()
            r.info = {}
            r.task_dragons = 0
            try:
                rc = r.run_task(d)
            except SystemExit:
                raise
            if rc:
                break
            r.write_log(d, t0)
            done.append(d['id'])
    if not rc:
        rc = r.flush_verify('全部任務結束')                            # 延後的逐人驗證一次批次讀（review §2-B）
    elif r.st.get('verify_pending'):
        event(f'失敗退出：待逐人驗證 {sorted(r.st["verify_pending"])} 留在進度檔，下次 questrun 結束（或依賴任務接取前）再驗')
    if r.st.get('dragon_in_bag') and rc not in NO_TOUCH:
        r.dragon_return('結束')                                         # 借出的道具要還（失敗也存；畫面要留給人看的失敗碼不碰）
    if not rc and drops:
        rc = r.drop_rewards()
    if not rc and after == 'grind':
        event(f'全部完成 → 恢復掛機：grind.py start --spot {spot}')
        rc = T.grind_start(spot)
        if rc:
            r.fail(rc, f'恢復掛機失敗 grind rc={rc}')
    LAST.update(ok=rc == 0, rc=rc, done=done, info=r.info, warnings=r.warnings, dragon_used=r.run_dragons, dragon_used_total=r.st.get('dragon_used', 0),
                dragon_in_bag=bool(r.st.get('dragon_in_bag')), verify_pending=sorted(r.st.get('verify_pending') or {}))
    event(f'結束 rc={rc}，完成 {done}' + ('；失敗退出，不恢復掛機' if rc else ''))
    r.save()
    return rc


def parse_roles(text: str):
    """--role all / DKBO3,DKBO5 → 角色名單（真名）；不認得 → None"""
    import charstate
    if not text or text == 'all':
        return list(ALL_ROLES)
    out = []
    for n in [x.strip() for x in text.split(',') if x.strip()]:
        hit = charstate.norm_char(n)
        if not hit:
            return None
        out.append(charstate.display(hit))
    return out


def cmd_status(ids, role: str = '') -> int:
    defs, bad = questdefs.resolve(ids)
    if bad:
        print(f'questrun：不認得的任務 ID {bad}', file=sys.stderr)
        return uikit.EXIT_USAGE
    import questdetail
    if role:
        roles = parse_roles(role)
        if roles is None:
            print(f'questrun：--role {role} 有不認得的角色', file=sys.stderr)
            return uikit.EXIT_USAGE
        rc, res = questdetail.status_all([d['detail'] for d in defs], roles=roles, leader=LEADER)
        print('任務\t' + '\t'.join(roles))
        for d in defs:
            print(f'{d["id"]} {d["detail"]}\t' + '\t'.join(str((res.get(r) or {}).get(d['detail'], '讀不到')) for r in roles))
        lag = {d['detail']: [r for r in roles if (res.get(r) or {}).get(d['detail']) != DONE] for d in defs}
        print(json.dumps({'rc': rc, 'not_done': {k: v for k, v in lag.items() if v}}, ensure_ascii=False))
        return rc
    res = questdetail.status([d['detail'] for d in defs])
    if not res.get('ok'):
        print(f'questrun：讀狀態失敗 {res}', file=sys.stderr)
        return res.get('rc', 1)
    for d in defs:
        print(f'{d["id"]}\t{d["detail"]}\t{res["tasks"].get(d["detail"])}')
    return 0


def main() -> int:
    import winenv
    winenv.enable_server()
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    sub = ap.add_subparsers(dest='cmd', required=True)
    def common(p):
        p.add_argument('ids', nargs='*')
        p.add_argument('--after', default='grind', choices=['grind', 'none'])
        p.add_argument('--dragon', action='store_true', help='長巡路任務（questdefs dragon）每片前吃龍王的守護（2026-10-12 起預設不吃）')
        p.add_argument('--dragon-all', action='store_true', help='配 --dragon：每個任務都吃（不看 questdefs dragon）')
        p.add_argument('--no-dragon', action='store_true', help='相容舊指令：= 預設（不吃），no-op')
        p.add_argument('--spot', default=DEFAULT_SPOT)
        p.add_argument('--no-battle-check', action='store_true', help='交接 / bossretry 重打前不查外掛戰鬥設定（5 人自動戰鬥、DKBO 人物首次動作）')
        p.add_argument('--pet-turnin', action='store_true', help='交寵物步驟自動做（恐龍博士 pet_turnin 逐人交、卡坦交前 rest-all；未實機）；預設 manual 步停 115')
        p.add_argument('--drop-reward', default='', help='全部成功後丟這些獎勵寵（逗號分隔；只丟 1 級；要配 --confirm-drop 同一串）')
        p.add_argument('--confirm-drop', default='', help='--drop-reward 的確認（名單要完全相同）')
    p = sub.add_parser('plan')
    common(p)
    p = sub.add_parser('status')
    p.add_argument('ids', nargs='*')
    p.add_argument('--role', default='', help='逐人讀：all 或 DKBO3,DKBO5（每人 char.switch 一次，最後切回 DKBO）')
    p = sub.add_parser('run')
    common(p)
    p.add_argument('--dry-run', action='store_true')
    p.add_argument('--max-slices', type=int, default=MAX_SLICES)
    p.add_argument('--slice-s', type=int, default=SLICE_S)
    p.add_argument('--max-min', type=int, default=MAX_MIN)
    p.add_argument('--hp-min', type=int, default=HP_MIN)
    p.add_argument('--team-hp-min', type=int, default=TEAM_HP_MIN, help='全隊任一人 HP 低於這個 %% 就補血（任務開始前 / BOSS 戰後；0 = 不讀全隊，只看隊長）')
    p.add_argument('--no-boss-retry', action='store_true', help='BOSS 戰後不滿 5 人（38 / 21）不自動補人，直接 114 停手')
    p.add_argument('--no-trust-progress', action='store_true', help='不信進度檔的「已完成」（預設 2 小時內的完成記錄直接跳過）')
    p.add_argument('--no-verify-all', action='store_true', help='= --verify off（相容舊旗標）')
    p.add_argument('--verify', default='risk', choices=VERIFY_MODES,
                   help='逐人驗證：risk（預設）= 本任務有風險事件才當場驗、其餘 run 結束 / 依賴任務接取前批次驗；each = 舊行為每任務當場驗；off = 不驗')
    p.add_argument('--hp-check-every', type=int, default=HP_EVERY, help='quest.py 片內全隊 HP：路上一般戰鬥每幾場讀一次（預設 %d；questdefs hp_every 優先；0 = 只在任務戰後讀）' % HP_EVERY)
    p.add_argument('--battle-check-always', action='store_true', help='交接一定查外掛戰鬥設定（預設 30 分內查過且沒重登 / bossretry → 沿用）')
    p.add_argument('--verify-skipped', action='store_true', help='詳情一開就已完成而跳過的任務也逐人驗（預設只驗本次跑完的）')
    a = ap.parse_args()
    if a.cmd == 'status':
        return cmd_status(a.ids, a.role)
    dry = a.cmd == 'plan' or a.dry_run
    kw = dict(max_slices=getattr(a, 'max_slices', MAX_SLICES), slice_s=getattr(a, 'slice_s', SLICE_S),
              max_min=getattr(a, 'max_min', MAX_MIN), hp_min=getattr(a, 'hp_min', HP_MIN),
              team_hp_min=getattr(a, 'team_hp_min', TEAM_HP_MIN), boss_retry=not getattr(a, 'no_boss_retry', False),
              verify_all=not getattr(a, 'no_verify_all', False), verify_skipped=getattr(a, 'verify_skipped', False),
              battle_check=not a.no_battle_check, pet_turnin=a.pet_turnin, drop_reward=a.drop_reward, confirm_drop=a.confirm_drop,
              verify=getattr(a, 'verify', 'risk'), dragon_all=a.dragon_all, hp_every=getattr(a, 'hp_check_every', HP_EVERY),
              battle_cache=not getattr(a, 'battle_check_always', False))
    if a.dragon and a.no_dragon:
        print('questrun：--dragon 和 --no-dragon 不能同時給', file=sys.stderr)
        return uikit.EXIT_USAGE
    rc = run(a.ids, dry, a.after, use_dragon=a.dragon, spot=a.spot, trust_progress=not getattr(a, 'no_trust_progress', False), **kw)
    if not dry:
        print(json.dumps(LAST, ensure_ascii=False, default=str))
    return rc


if __name__ == '__main__':
    sys.exit(main())
