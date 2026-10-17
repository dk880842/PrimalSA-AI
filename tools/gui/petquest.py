#!/usr/bin/env python3
"""寵物任務總控（恐龍博士 2016 / 卡坦的願望 2019 / 猜謎三兄弟 3003）：（恐龍 / 卡坦）存第 2 格 → 抓 / 分 / 練 → 接取 → 交 → 丟獎勵寵 → 換回原戰寵。只用標準函式庫。
**只有離線測試（test_petquest.py），整支實機未跑過**；各段呼叫的既有腳本（questrun / pet_catch / pet / petwatch / petdrop / grind / ass）各自有實機紀錄，見 psa-pet-quest SKILL.md。

用法（專案根目錄；WSL / Windows 原生相同）：
  uv run --no-project python tools/gui/petquest.py plan 2016|2019|3003                 # 不碰遊戲：印每段要跑的指令
  uv run --no-project python tools/gui/petquest.py run 2016|2019|3003 [--confirm-drop] [--dry-run] [--from 段] [--to 段] [--fresh]
    （誘餌不夠一律自動買：手上現有的誘餌照用，外掛捉寵設置「+」只買缺額 N − 現有 次可抓捕數，每按一次 50,000 石幣；**不需旗標、不設次數上限**（使用者 2026-10-15）；
     不讀石幣；保險：按前讀不到鑽石 → 不按、163 停；每按一次可抓捕數必須 +1、按後鑽石讀不到 / 有變 → 163 停（鐵則 3）。鑽石用像素點陣讀，見 catchbuy.py）
    --confirm-buy-bait  無作用（no-op，舊呼叫端相容；postrebirth 傳也無害）
    --confirm-drop      准丟獎勵寵（恐龍博士 布克布克、卡坦步 1 修寶、猜謎三兄弟 左迪洛斯；petdrop 驗名 + 只丟 1 級）；沒給 → 到丟寵段 168 停
    --from / --to       只跑某幾段（段名見 plan）；--fresh 不管進度檔從頭（預設：進度檔 tools/.cache/petquest.json 24 小時內記錄過的段直接跳過）
    --dry-run           = plan
    --keep-autoswap     （恐龍博士 2016 專用，postrebirth 在後面還要解卡坦時傳）train 結束先不關外掛「自動轉換戰寵」（進度檔留 autoswap_on，卡坦 train 看到就不再勾），
                        restore 段整段跳過（不取回第 2 格的寵物 / 不重鎖 / 不改一般動作）；第 2 格紀錄（進度檔頂層 slot2_stored：名字 / 等級 / ts，恐龍博士 prep 存倉後寫）留著給卡坦 prep 沿用，
                        由卡坦 restore 統一換回並清掉紀錄、train 結束照常關
    --verify-defer      內部 questrun 帶 --verify defer（postrebirth 傳；沒風險事件的逐人驗證延到 postrebirth 收尾，交寵物仍是風險事件 → 當場驗）
  可 import：petquest.run(qid, tools=…, confirm_drop=…) → 退出碼（confirm_buy 參數保留、無作用）；結果在 petquest.LAST

流程（各段失敗就停在該段、印手動指令；畫面不認得 9 / 斷線 10 一律透傳；進度檔記完成的段，重跑 = 續跑）：
  恐龍博士 2016 / 卡坦的願望 2019（使用者 2026-10-12 S5 / S6 做法；卡坦步 1 鯊、步 2 雞兩輪；2026-10-15 使用者改順序：先存第 2 格 → 抓 / 分 / 練 → 才接任務）
    段順序：恐龍 prep → catch → distribute → train → accept → turnin → drop → restore；
            卡坦 prep → catch1 → distribute1 → train1 → accept → turnin1 → drop1 → catch2 → distribute2 → train2 → turnin2 → store_reward → restore
            （第 2 輪〔雞〕要第 1 輪交完、追蹤進步 2 才能進）
    prep        （不先接任務）關原地遇敵 + 等戰鬥結束 → 解散隊伍（使用者 2026-10-16 精簡：不讀追蹤步號、不取消鎖定戰寵、不檢查空格數）
                → 進度檔頂層有 slot2_stored（24 小時內）= 恐龍博士 prep 已存過第 2 格 → 沿用紀錄，**不讀不存**（卡坦接在恐龍博士後面就是這樣）
                → 沒有（單獨跑 / 恐龍博士）才做：pet.py list 讀每人寵物欄**第 2 格**（pet.py list slot == 2，1 起算；第 1 格 = 騎寵位置）
                的寵物，名字 + 等級記進度檔 battle / orig（各角色可不同：p1 朵拉比斯、p2 迪基格斯；續跑沿用已記的不重讀）
                保險：第 2 格空 / 名字讀不出 / 等級讀不到 / 是騎寵（騎乘中、名字像騎寵）→ 162 停手、一隻都不存
                → 第 2 格的寵物存個人倉庫（同名的人一組 store-many；不碰騎寵）→ 寫 slot2_stored（restore 成功才清）；抓寵溢出的自動進個人倉庫
    catch[N]    **一次抓滿本輪總隻數 N（正常 5，不分批）→ 改名 → 存公共 → 取個人倉庫溢出的改名**（使用者 2026-10-16 最簡流程：
                「抓完先把各角色的數字寵都改完名、馬上存入公倉，之後再把個人倉庫的拿出來改名，這樣抓的那隻人物就有自己需要的寵物」）。
                外掛捉寵設置已勾「自動存倉庫」，寵物欄滿了多抓的自動進抓寵者個人寵物倉庫（在欄 = min(N, 4)、其餘溢出；prep 後空格固定 4〔騎寵 + 4 空〕，不讀寵物欄）。
                小步（進度檔 sub_r<輪>.step，中斷從下一小步接，不重新盤點）：
                  抓前  [只有第 2 輪 / catch 單獨續跑才 solo（關遇敵 + 解散）；第 1 輪接在 prep 後不重複；不讀寵物欄] → pet_catch.py --stages bait（每輪每人只取 / 拆一次；不夠 → 現有照用、外掛「+」只買缺額，
                        不讀石幣、鑽石前後不變，不夠 163）→ pet_catch.py --stages setup,wait（wait 第一次輪詢 N×20+20 秒、之後 60 秒）→ [caught]（不存回誘餌：只取 / 買剛好 N，使用者 2026-10-16）
                  1.    pet.py reset-name --role 抓寵者（寵物欄成長字串名字 → 物種名；費用字樣 67 → 165 停手）→ [renamed]
                  2.    一次 pet.py store-many --plan "r:物種×在欄隻數,…" --depot public --pick last（面板開一次、左欄頭像連續換人；騎寵不碰；已存完的人記 stored_roles，續跑只做剩下的）→ [stored]
                  3.    溢出的（N − 在欄）：pet.py take-many --depot personal --plan "r:?"（溢出的那隻自動進倉、從沒改名，卡上是成長字串：取「沒名字」的卡，
                        不認物種 / 不比縮圖；沒名字的卡多於溢出隻數 → pet 72 不猜，2026-10-16 卡坦 p2）→ reset-name 取回者
                        （溢出 > 1 才再 store-many 多的進公共，欄只留 1 隻自用）→ [taken_personal]
                抓寵者寵物欄剩自己要的 1 隻。**拿掉**（舊版）：catch-pre 快照、register 名字驗證 / 成長字串登錄備援、recount（depot-list 三處清點 / pre_store / 冪等重算）。
                中斷後重跑：已抓完（caught 之後）直接從下一小步接；抓到一半失敗（進度檔 catch_started 旗標有、沒 caught）→ 164 請人處理（不讀寵物欄、不自動盤點）。
    distribute[N]  其他人從公共倉庫取自己缺的種類：pet.py take-many --depot public --plan "角色:物種,…"（take_plan：每人每種 1 隻，抓寵者自己那種不取）→ [distributed_taken]
                → **只驗**：pet.py list，每人寵物欄有寵物的格數 = 1 + 本輪種類數（恐龍博士 2 種 → 3 格：騎寵 + 魯尼帖斯 + 貝魯卡；卡坦每輪 4 種 → 5 格）→ [distributed]；
                不比名字 / 縮圖 / 成長字串、不數倉庫。take-many 中途失敗：進度檔記已取到的，重跑只補沒取到的（165）。
    train[N]    （2026-10-16 精簡）自動轉換戰寵 on（轉換級數使用者設 30；**整個任務只勾一次**：進度檔頂層 autoswap_on 已有就不跑）→ 5 人第 2 格 set-state-slot 出戰（不認物種）（本身已驗證，失敗就停；不跑 verify-battle）
                → grind.py start --spot 波拉島（使用者 2026-10-15 指定：恐龍博士 / 卡坦練寵固定 80 級練功區「波拉島」，固定點、不起 follow）
                → 每 POLL_S（10）秒只讀每人「最後一格」等級（2026-10-16：自動轉換戰寵依序換寵，最後一格達標 = 前面都先過；不認寵物、不呼叫 pet.py list）：
                  pet.py levels --slots <最後一格 = 1 + 本輪種類數>（恐龍博士第 3 格 ≥ 30、卡坦第 5 格 ≥ 25；門檻 = 本輪 need 最大值）；讀取失敗下一輪再讀；
                  每人連兩次 ≥ 門檻就鎖定，5 人全部鎖定結束，最多 45 分
                → 立刻 pet.py set-state-slot --slots <最後一格> 等待（只改最後那一格，前面的已被自動轉換換下；不認物種）→ 關遇敵（成功記進度檔 rested）→ 自動轉換戰寵 off **只在整個任務最後**（卡坦第 2 輪 train 結束 / 恐龍博士沒帶 --keep-autoswap 的 train 結束；卡坦第 1 輪不關）
    accept      （第 1 輪 train 的 rest-all 之後）questrun.py run <ID> --after none：接取後停在寵物步（115 manual / 155 / 117 對話 ↔ 選擇循環）；不讀追蹤步號（2026-10-16 起）；
                0 = 任務已完成 → 其餘段跳過，只做 restore（第 2 格照樣取回、出戰、鎖定；練好的任務寵留在寵物欄）
    turnin[N]   questrun.py run <ID> --after none --pet-turnin [--rested]（train 段 30 分內 rest-all 成功才帶：questrun 交件前不重做 rest-all）
                （恐龍：解散逐人 pet_turnin；卡坦：隊長交一次）；卡坦第 1 輪交完讀步號 = 2 才算
                卡坦 turnin1 可跳過（2026-10-17）：accept 回 155 且輸出「需先抓 / 練寵：步 2」= 接取對話已把第 1 步（鯊魚）交掉 → 記進度檔 turned、turnin1 直接略過進 drop1（不再白跑 questrun 36 秒）；
                恐龍博士 accept 回 115（步 1 manual 不交寵）→ turnin 才是真正交件，不能省
    drop[N]     （--confirm-drop）petdrop.py all <獎勵寵> --confirm-name <獎勵寵> --max-level 1（恐龍 布克布克；卡坦第 1 輪 修寶）
    store_reward（卡坦）獎勵朵拉比斯（Lv1）5 人存個人倉庫
    restore     （2026-10-16 精簡）pet.py take-many --depot personal --plan "角色:第 2 格名字@原等級"（prep 記的；成功記進度檔 restore_taken，續跑看記號跳過、不讀寵物欄）
                → pet.py set-state-slot --role all --slots 2 出戰（一律第 2 格處理，不認名字、無例外）
                → pet_catch.py --lock 戰寵 --battle-pet 名字 --normal 攻擊（外掛面板每組只開一次：逐人鎖定戰寵 + 一般動作 = 攻擊；同名一組 --roles，讀回）
                → pet.py list 驗 5 人各自戰寵 1 隻、出戰、等級 = 原等級（保留）
                （舊進度檔沒跑 prep、進度檔沒戰寵名而任務已完成：用當下出戰寵當戰寵，只收尾）
  猜謎三兄弟 3003（使用者 2026-10-12 / 10-13 做法）
    accept      questrun.py run 3003 --after none（步 1 manual → 115；步 2 需練寵 → 155；0 = 已完成）
    step1       追蹤步號 = 1 才做：quest.py --task 猜謎三兄弟 --stop-after-rewards 1（10-12 / 10-13 點追蹤自動巡到 810 伊那多拿金豬，沒爬塔）
                → pet.py list 驗 5 人都有金布伊；沒有 → 161（點任務追蹤重試 / 人工處理）
    prep        關遇敵 → pet.py list 記原戰寵（朵拉比斯）等級 → 取消鎖定戰寵 → 金布伊 5 人出戰 → pet_catch.py --lock 戰寵 --battle-pet 金布伊
    train       去練功 grind.py start（不帶 --spot：依等級選點，未滿地雷區背景起 follow；petwatch 在跑時 follow 自動暫停）→ petwatch.py --pet 金布伊 --level 77 --back 朵拉比斯 --exp-fruit（練前 depot_use 吃 2倍智慧果；到 77 自動換回朵拉比斯 + 重鎖）
    turnin      關遇敵 → questrun.py run 3003 --after none（交金豬 → 會員證 → 藍暴）
    drop        （--confirm-drop）petdrop.py all 左迪洛斯 --confirm-name 左迪洛斯 --max-level 1
    restore     pet_catch.py --lock 戰寵 --battle-pet 朵拉比斯 --normal 攻擊（面板只開一次）→ pet.py list 驗朵拉比斯出戰、等級 ≥ 原等級（練功中可能升級）
  --keep-autoswap 的安全結論（2026-10-15 讀程式）：恐龍博士 restore = 取回第 2 格的戰寵（p1 朵拉比斯）→ 出戰 → 鎖定戰寵 → 一般動作；自動轉換戰寵（外掛，轉換級數 30）開著時，
    剛換回的高等朵拉比斯會被外掛當「超過轉換級數」又換掉，且卡坦 prep 緊接著又要把朵拉比斯存個人倉庫，換回根本白做 → 帶旗標時 dino restore 整段跳過，
    朵拉比斯留在個人倉庫、原等級用進度檔頂層共用紀錄 slot2_stored 交給卡坦 prep（卡坦 prep 看到紀錄〔24 小時內〕就不讀寵物欄、不存倉）；
    卡坦 restore 照常換回 + 鎖定 + 關自動轉換（train 結束就關）。slot2_stored = {qid, orig, battle, ts}，restore 真正換回原寵成功才清。中斷保險見 postrebirth.py 檔頭。
  不做：恢復掛機（交給呼叫端 / postrebirth 收尾的 grind.py start）。

退出碼（共用 0 / 1 / 2 / 8 / 9 / 10 見 uikit；petquest 自己 160～169）：
  160 參數錯 / 任務 ID 不支援 / 進度不一致（例：restore 要原等級但進度檔沒有）
  161 接取失敗（questrun 非預期退出碼）/ 猜謎步 1 沒拿到金布伊
  162 準備失敗（關遇敵、解散、讀寵物欄、第 2 格空 / 名字讀不出 / 等級讀不到 / 是騎寵〔恐龍 / 卡坦〕、讀不到出戰寵名字〔猜謎〕、取消鎖定、存第 2 格、金布伊出戰 / 鎖定）
  163 買可抓捕數失敗（按前讀不到鑽石 → 沒按；「+」按了可抓捕數沒 +1；按後鑽石讀不到 / 有變；外掛數 < 背包誘餌）
  164 抓寵失敗（pet_catch 非 0：14 系別物種選不到、103 取誘餌 / 設定 / 逾時…；抓前寵物欄空格不夠；上次中斷且寵物欄已有任務寵）
  165 分配失敗（reset-name / store-many / take-many 非 0；分配後每人寵物欄格數不是 1 + 本輪種類數）/ 還原名字讀到費用字樣（pet 67，鐵則 3）
  166 練寵失敗（自動轉換戰寵、出戰、grind、等級逾時、petwatch、rest-all）
  167 交寵物失敗（questrun 非預期退出碼、卡坦第 1 輪交完步號不是 2）
  168 丟獎勵寵失敗 / 沒給 --confirm-drop
  169 換回原戰寵失敗（存獎勵寵朵拉比斯〔REWARD_PET，與戰寵無關〕、取回、出戰、鎖定、一般動作、讀回驗證）
"""
import argparse
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import charstate  # noqa: E402
import clients  # noqa: E402
import questdefs  # noqa: E402
import uikit  # noqa: E402

SRC = 'petquest'
ROOT = uikit.ROOT
import logpaths  # noqa: E402
EVENT_LOG = logpaths.p(clients.npath('quest-events.log'))     # 主視窗 = notes/quest-events.log；其他 = notes/clients/<程序名>/
PROGRESS = logpaths.p(uikit.CACHE / 'petquest.json')

(EXIT_ARGS, EXIT_ACCEPT, EXIT_PREP, EXIT_BAIT, EXIT_CATCH, EXIT_DIST, EXIT_TRAIN, EXIT_TURNIN, EXIT_DROP,
 EXIT_RESTORE) = range(160, 170)
PASS = (uikit.EXIT_UNKNOWN_SCREEN, uikit.EXIT_HALT)                  # 驗證視窗 / 斷線：一律透傳
ALL_ROLES = clients.roster()          # 這個視窗（PSA_CLIENT）的名單：主視窗 DKBO、DKBO2～5；PrimalSA2 = DKBO6～10；第 1 個 = 隊長
LEADER = ALL_ROLES[0] if ALL_ROLES else ''

_r = questdefs.roster_at              # 抓寵分配用卡位（_r(1) = 名單第 2 個）而不是寫死 DKBO2…
BATTLE_PET = '朵拉比斯'            # 猜謎 / 已完成收尾讀不到出戰寵時的退路名字（p1 的戰寵；只在寵物欄確實有這隻時才用）
BATTLE_SLOT = 2                    # 恐龍博士 / 卡坦 prep 記並存倉的格（pet.py list slot 1 起算；第 1 格 = 騎寵位置），名字 / 等級記進度檔 battle / orig
REWARD_PET = '朵拉比斯'            # 卡坦任務的獎勵寵（Lv1，與各角色戰寵無關；存個人倉庫）
BAIT_ITEM = 92                     # bag.EXIT_ITEM：誘餌不夠 / 倉庫沒有
PET_FEE = 67                       # pet.EXIT_FEE：還原名字時讀到費用字樣（鐵則 3）
import catchbuy  # noqa: E402  外掛「+」買可抓捕數的共用邏輯（rebirth_pets 同一份）
PLUS_XY, PLUS_COST, MONEY_BOX = catchbuy.PLUS_XY, catchbuy.PLUS_COST, catchbuy.MONEY_BOX      # 紅區：只有誘餌不夠時 buy_plus 才點（鑽石讀不到 / 有變就停）
POLL_S = 10.0                      # 練寵讀等級間隔（2026-10-15 使用者改 10 秒；是 sleep 間隔，每輪讀 5 人另需約 30 秒；總時限看 TRAIN_MAX_S 牆鐘不看輪數；舊版 30 / 120 秒）
RESTED_S = 30 * 60                 # train 段 rest-all 成功後這麼久內的 turnin 段帶 --rested（questrun 交件前不重做）
TRAIN_MAX_S = 45 * 60             # 練寵最多等這麼久（S5 約 9 分、S6 約 5 分）
PROGRESS_TRUST_S = 24 * 3600
TRAIN_SPOT = '波拉島'           # 恐龍博士 / 卡坦練寵：使用者 2026-10-15 指定固定在 80 級練功區（spots「波拉島」）
QUIZ_SPOT = None                # 猜謎三兄弟練金布伊：去練功（grind.py start 不帶 --spot，依等級選點 + follow）；不寫死地雷區
LAST: dict = {}

# 每任務的設定（物種 / 門檻 / 抓寵者取自 questdefs.pet_prep 與 psa-pet-quest SKILL.md 具體寵物表）；抓寵者用名單卡位（_r(1) = 第 2 個人），不寫死名字
QUESTS = {
    2016: dict(kind='catch', track='恐龍博士', rounds=[
        dict(assign=[(_r(1), '呼拔拔系', '魯尼帖斯'), (_r(2), '老虎系', '貝魯卡')], need={'魯尼帖斯': 18, '貝魯卡': 30}, drop='布克布克')],
        count=len(ALL_ROLES) or 5),
    2019: dict(kind='catch', track='卡坦的願望', rounds=[
        dict(assign=[(_r(1), '鯊魚系', '克邦凱斯'), (_r(2), '鯊魚系', '加克拉'), (_r(3), '鯊魚系', '加格'), (_r(4), '鯊魚系', '邦恩吉')],
             need={'克邦凱斯': 25, '加克拉': 25, '加格': 25, '邦恩吉': 25}, drop='修寶', step=1),
        dict(assign=[(_r(1), '火雞系', '火雞'), (_r(2), '火雞系', '克克洛斯'), (_r(3), '火雞系', '霍爾克'), (_r(4), '火雞系', '奇寶')],
             need={'火雞': 25, '克克洛斯': 25, '霍爾克': 25, '奇寶': 25}, drop=None, step=2)],
        count=len(ALL_ROLES) or 5, store_reward=REWARD_PET),
    3003: dict(kind='quiz', track='猜謎三兄弟', pet='金布伊', level=77, drop='左迪洛斯'),
}


def stages_of(qid: int) -> list:
    q = QUESTS[qid]
    if q['kind'] == 'quiz':
        return ['accept', 'step1', 'prep', 'train', 'turnin', 'drop', 'restore']
    out = ['prep']                                                       # 使用者 2026-10-15：prep 不先接任務；第 1 輪練完、rest-all 之後才接（accept）
    n = len(q['rounds'])
    for i, rd in enumerate(q['rounds'], 1):
        sfx = str(i) if n > 1 else ''
        out += [f'catch{sfx}', f'distribute{sfx}', f'train{sfx}'] + (['accept'] if i == 1 else []) + [f'turnin{sfx}']
        if rd.get('drop'):
            out.append(f'drop{sfx}')
    if q.get('store_reward'):
        out.append('store_reward')
    return out + ['restore']


def accept_turned_in(rc: int, tail, q: dict) -> int:
    """接取那次 questrun 的退出碼 / 輸出判斷「第 1 輪已在接取對話交完」→ 回輪號（1）；否則 0。
    條件：多輪 catch 任務（卡坦）、rc 155、輸出「需先抓 / 練寵：步 N」的 N 已超過第 1 輪的步（rounds[0]['step']）。
    恐龍博士（步 1 manual → 115，接取不交寵）、猜謎 → 一律 0"""
    rounds = q.get('rounds') or []
    if rc != 155 or len(rounds) < 2:
        return 0
    m = re.search(r'需先抓 / 練寵：步 (\d+)', '\n'.join(tail or []))
    if m and int(m.group(1)) > (rounds[0].get('step') or 1):
        return 1
    return 0


def stage_round(stage: str) -> int:
    """'catch2' → 2；'catch' → 1"""
    m = re.search(r'(\d+)$', stage)
    return int(m.group(1)) if m else 1


ROUND_STAGES = ('catch', 'distribute', 'train', 'turnin', 'drop')


def stage_base(stage: str) -> str:
    """'catch2' → 'catch'；'step1'（猜謎步 1，不是輪次）維持原名"""
    b = re.sub(r'\d+$', '', stage)
    return b if b in ROUND_STAGES else stage


# ---------------------------------------------------------------- 純函式（測試直接餵）
def last_json(lines) -> dict:
    """子程序輸出最後一個 JSON 物件行 → dict；沒有 → {}"""
    for ln in reversed(list(lines or [])):
        ln = str(ln).strip()
        if ln.startswith('{') and ln.endswith('}'):
            try:
                return json.loads(ln)
            except ValueError:
                continue
    return {}


def slot_species(sl: dict) -> str | None:
    """pet.py list 的一格 → 名字或已登錄 / 縮圖認得的物種（空格 None）"""
    if not sl or sl.get('empty'):
        return None
    return sl.get('name') or sl.get('species') or sl.get('img_species')


def strict_species(sl: dict) -> str | None:
    """pet.py list 的一格 → 嚴格身分（名字；或名字框讀不出但成長字串登錄 + 縮圖一致才填的 species）。只有縮圖 img_species 不算（空格 / 認不出 None）"""
    if not sl or sl.get('empty'):
        return None
    return sl.get('name') or (sl.get('species') if sl.get('unnamed') else None)


SUB_STEPS = ('caught', 'renamed', 'stored', 'taken_personal', 'distributed_taken', 'distributed')      # catch / distribute 小步（進度檔 sub_r<輪>.step）


def sub_key(stage: str) -> str:
    """catch2 / distribute2 → 'sub_r2'（同一輪的 catch 與 distribute 共用一份小步進度）"""
    return f'sub_r{stage_round(stage)}'


def sub_at(st: dict, step: str) -> bool:
    """小步進度 st 是否已做到（含）step"""
    cur = (st or {}).get('step')
    return cur in SUB_STEPS and SUB_STEPS.index(cur) >= SUB_STEPS.index(step)


def bar_count_bad(roles_slots: dict, want: int, roles=ALL_ROLES) -> dict:
    """純函式（distribute 唯一的驗證）：每人寵物欄有寵物的格數應 = want → {角色: 實際格數}（不對的才列；沒讀到的角色 = None）"""
    out = {}
    for r in roles:
        slots = (roles_slots or {}).get(r)
        n = None if slots is None else sum(1 for s in slots if s and not s.get('empty'))
        if n != want:
            out[r] = n
    return out


CATCH_FREE = 4                                                       # prep 後抓寵者寵物欄空格（騎寵 + 4 空；卡坦第 2 輪前 4 隻鯊已交出也是 4）


def free_slots(slots, size: int = 5) -> int:
    """寵物欄空格數（pet.py list 的格：empty 或沒列到的都算空）"""
    return size - sum(1 for s in slots or [] if s and not s.get('empty'))


def count_species(slots, sp: str) -> int:
    return sum(1 for s in slots or [] if slot_species(s) == sp)


def battle_levels(roles_slots: dict, pet: str = BATTLE_PET) -> dict:
    """{角色: [格]} → {角色: 該寵物等級（出戰的優先；讀不到 None；沒有該寵物不列）}"""
    out = {}
    for r, slots in (roles_slots or {}).items():
        hits = [s for s in slots or [] if slot_species(s) == pet]
        if not hits:
            continue
        hit = next((s for s in hits if s.get('state') == '出戰'), hits[0])
        out[r] = hit.get('level')
    return out


def battle_levels_by(roles_slots: dict, names: dict) -> dict:
    """{角色: [格]} + {角色: 戰寵名} → {角色: 該角色戰寵等級（出戰的優先；沒有 / 讀不到 None 不列）}"""
    out = {}
    for r, nm in (names or {}).items():
        lv = battle_levels({r: (roles_slots or {}).get(r)}, nm)
        if r in lv:
            out[r] = lv[r]
    return out


def pick_slot2(roles_slots: dict, roles=None) -> tuple:
    """純函式：恐龍博士 / 卡坦 prep 讀每人寵物欄「第 2 格」的寵物（使用者 2026-10-15）→ ({角色: 名字}, {角色: 等級}, {角色: 失敗原因})。
    「第 2 格」= pet.py list 的 slot == BATTLE_SLOT（2；slot 從 1 起算 = 面板寵物欄由上往下第 2 張卡）。第 1 格是騎寵位置
    （pet.guard_store 預設不存第 1 格）；p1 第 2 格 = 朵拉比斯（出戰，截圖 ui-log/005319-pet-slot-1.png）、p2 新角色 = 迪基格斯（出戰，瑪斯貝卡騎乘）。
    保險：第 2 格空 / 沒讀 / 名字讀不出（嚴格身分 strict_species，只有縮圖不算）/ 等級讀不到 → 失敗原因；
    第 2 格是騎寵（狀態 = 騎乘、名字像騎寵 uikit.is_mount_like）→ 失敗原因（存倉不碰騎寵），由呼叫端 162 停手、一隻都不存"""
    names, levels, bad = {}, {}, {}
    for r in (roles if roles is not None else ALL_ROLES):
        s2 = next((s for s in (roles_slots or {}).get(r) or [] if s and s.get('slot') == BATTLE_SLOT), None)
        if not s2 or s2.get('empty'):
            bad[r] = f'第 {BATTLE_SLOT} 格是空的'
            continue
        if s2.get('skipped'):
            bad[r] = f'第 {BATTLE_SLOT} 格沒讀到'
            continue
        nm = strict_species(s2)
        raw = nm or s2.get('raw_name') or s2.get('img_species') or ''
        if s2.get('state') == '騎乘' or s2.get('mountlike') or (raw and (raw in uikit.MOUNTS or uikit.is_mount_like(raw))):
            bad[r] = f'第 {BATTLE_SLOT} 格是騎寵（{raw or "?"}，狀態 {s2.get("state")}）→ 存倉不碰騎寵'
            continue
        if not nm:
            bad[r] = f'第 {BATTLE_SLOT} 格名字讀不出'
            continue
        if not s2.get('level'):
            bad[r] = f'第 {BATTLE_SLOT} 格 {nm} 等級讀不到'
            continue
        names[r], levels[r] = nm, s2['level']
    return names, levels, bad


def pick_battle_names(roles_slots: dict, roles=None, fallback: str = BATTLE_PET) -> tuple:
    """純函式：prep 讀每人當下「出戰」的寵物名字 → ({角色: 名字}, {角色: 失敗原因})
    名字要「名字框 / 登錄」認得的嚴格身分（strict_species；只有縮圖認出的不算）；恰好 1 隻出戰才採用。
    沒有出戰時退路：寵物欄確實有 fallback（朵拉比斯）才用它，否則不猜、記原因（由調用端停手）"""
    names, bad = {}, {}
    for r in (roles if roles is not None else ALL_ROLES):
        slots = [s for s in (roles_slots or {}).get(r) or [] if s and not s.get('empty')]
        on = [s for s in slots if s.get('state') == '出戰']
        if len(on) == 1:
            nm = strict_species(on[0])
            if nm:
                names[r] = nm
            else:
                bad[r] = '出戰寵名字讀不出'
        elif len(on) > 1:
            bad[r] = f'出戰寵 {len(on)} 隻（無法判斷哪隻是戰寵）'
        elif any(strict_species(s) == fallback for s in slots):
            names[r] = fallback
        else:
            bad[r] = '沒有出戰寵、寵物欄也沒有' + fallback
    return names, bad


def group_by_name(names: dict, roles=None) -> list:
    """{角色: 戰寵名} → [(名字, [角色…])]（照名單順序、名字第一次出現順序；沒記名字的角色不列）"""
    out: dict = {}
    for r in (roles if roles is not None else ALL_ROLES):
        if names.get(r):
            out.setdefault(names[r], []).append(r)
    return list(out.items())


def take_plan(assign, roles=ALL_ROLES) -> list:
    """每人每物種要 1 隻；抓寵者自己留的那隻不取 → [(角色, 物種)]"""
    catcher = {sp: r for r, _, sp in assign}
    return [(r, sp) for r in roles for _, _, sp in assign if catcher[sp] != r]


def train_status(roles_slots: dict, need: dict, roles=ALL_ROLES) -> tuple:
    """→ (全部達標?, {角色: {物種: 等級 | None}} 未達標 / 讀不到的)"""
    lag = {}
    for r in roles:
        slots = (roles_slots or {}).get(r) or []
        for sp, lv in need.items():
            hits = [s for s in slots if slot_species(s) == sp]
            v = max((s.get('level') or 0 for s in hits), default=None) if hits else None
            if not v or v < lv:
                lag.setdefault(r, {})[sp] = v
    return not lag, lag


def levels_of(lv: dict, smap: dict) -> dict:
    """pet.py list / levels 結果 {角色: [格]} → {(角色, 物種): 等級或 None}（該物種各格取最高；變空 / 沒讀到 = None）"""
    out = {}
    for (r, sp), nums in smap.items():
        got = {x.get('slot'): x for x in (lv or {}).get(r) or []}
        vals = [got[n].get('level') for n in nums if n in got and not got[n].get('empty')]
        out[(r, sp)] = max((v for v in vals if v is not None), default=None)
    return out


class TrainConfirm:
    """練寵達標確認：每隻（角色, 物種）連兩次讀值 ≥ 門檻就鎖定（防讀錯；鎖定後不清）；讀到 < 門檻 → 連續次數歸零；讀不到（None）→ 不動。全部鎖定即結束"""

    def __init__(self, need: dict):
        self.need = need
        self.locked, self.streak = set(), {}

    def update(self, cur: dict) -> None:
        for k, v in cur.items():
            lv = self.need.get(k[1])
            if k in self.locked or v is None or lv is None:
                continue
            if v < lv:
                self.streak.pop(k, None)
            elif self.streak.get(k):
                self.locked.add(k)
            else:
                self.streak[k] = True

    def done(self, keys) -> bool:
        keys = list(keys)
        return bool(keys) and all(k in self.locked for k in keys)


parse_money = catchbuy.parse_money


def bait_ok_roles(lines) -> set:
    """pet_catch --stages bait 的輸出 →「背包誘餌 = N」成功的角色"""
    out = set()
    for ln in lines or []:
        m = re.search(r'([A-Za-z0-9]+)\s*背包誘餌\s*=\s*\d+', str(ln))
        hit = charstate.norm_char(m.group(1), ALL_ROLES) if m else None    # 名單內的名字（DKBO10 也行；舊版 DKB[O0]\d? 只吃 1 位數）
        if hit:
            out.add(hit)
    return out


def bait_short_counts(lines) -> dict:
    """pet_catch --stages bait --keep-short-bait 的輸出 →「背包誘餌不足 = n」的角色 → 現有誘餌數（現有的留在背包照用）"""
    out = {}
    for ln in lines or []:
        m = re.search(r'([A-Za-z0-9]+)\s*背包誘餌不足\s*=\s*(\d+)', str(ln))
        hit = charstate.norm_char(m.group(1), ALL_ROLES) if m else None
        if hit:
            out[hit] = int(m.group(2))
    return out


def csv_assign(assign) -> str:
    return ','.join(f'{r}:{f}:{sp}' for r, f, sp in assign)


def species_csv(assign) -> str:
    return ','.join(sp for _, _, sp in assign)


# ---------------------------------------------------------------- 紀錄 / 進度
def event(msg: str) -> None:
    line = f'{time.strftime("%Y-%m-%d %H:%M:%S")} [petquest] {msg}'
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


def clear_progress(reason: str = '') -> bool:
    """整個進度檔作廢（轉生後 / postrebirth --fresh）：舊轉的 battle / orig / slot2_stored 不能沿用（2026-10-17 p2 一轉後
    猜謎三兄弟沿用 0 轉記的「迪基格斯」→ petwatch --back 迪基格斯 5 人換回失敗）。回 True = 有刪檔"""
    try:
        PROGRESS.unlink()
    except OSError:
        return False
    event(f'進度檔已清空（{reason or "手動"}）：{PROGRESS}')
    return True


def stale_trans(allp: dict, cur) -> bool:
    """純函式：進度檔記的轉數（頂層 'trans'）與目前轉數都知道、而且不同 → True（舊轉的紀錄作廢）"""
    t = allp.get('trans') if isinstance(allp, dict) else None
    return isinstance(t, int) and isinstance(cur, int) and t != cur


def save_progress(d: dict) -> None:
    try:
        PROGRESS.parent.mkdir(parents=True, exist_ok=True)
        PROGRESS.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding='utf-8')
    except OSError:
        pass


# ---------------------------------------------------------------- 真實工具（測試換成 Fake）
class Tools:
    def sleep(self, s):
        uikit.sleep(s)

    def cur_trans(self):
        """目前隊長轉數（grind.load_trans：背包讀字 / rebirth 轉生確認時寫的 trans.json；讀不到 None）"""
        import grind
        return grind.load_trans()

    def clock(self):
        return time.time()

    def sub(self, script: str, args, timeout: float = 3600) -> tuple:
        """子程序跑 tools/gui/<script>（輸出即時印出）→ (退出碼, 最後 80 行)"""
        cmd = [sys.executable, str(HERE / script)] + [str(x) for x in args]
        env = dict(os.environ, PYTHONIOENCODING='utf-8')
        tail = []
        p = subprocess.Popen(cmd, cwd=str(ROOT), stdout=subprocess.PIPE, stderr=subprocess.STDOUT, env=env, text=True, encoding='utf-8', errors='replace')
        t0 = time.time()
        try:
            for ln in p.stdout:
                ln = ln.rstrip()
                print(ln, flush=True)
                tail.append(ln)
                del tail[:-80]
                if time.time() - t0 > timeout:
                    p.kill()
                    break
        finally:
            p.wait()
        return p.returncode, tail

    def encounter_off(self):
        """關原地遇敵 + 等這場戰鬥打完（questrun 交接同一個）"""
        import questrun
        questrun.Tools().encounter_off_wait()

    def read_step(self, track):
        import quest
        return quest.read_step_no(track)

    def money(self) -> tuple:
        """寵物面板頂部資源列 → (石幣, 鑽石)；面板打不開 / 讀不到 → (None, None)"""
        return catchbuy.money()

    def press_plus(self, role, limit=None, min_before=None) -> tuple:
        """外掛「+」按一次（紅區：只有 buy_plus〔誘餌不夠時買缺額〕會呼叫）→ (rc, 按前, 按後)"""
        return catchbuy.press_plus(role, limit, min_before)


# ---------------------------------------------------------------- 驅動
class Run:
    def __init__(self, qid: int, T, o: dict):
        self.qid, self.T, self.o = qid, T, o
        self.q = QUESTS[qid]
        allp = load_progress()
        cur = self.cur_trans()
        if stale_trans(allp, cur):
            event(f'進度檔是 {allp.get("trans")} 轉時記的（現在 {cur} 轉）→ 整個作廢、從頭（battle / orig / slot2_stored 都不沿用）')
            allp = {}
        if cur is not None:
            allp['trans'] = cur                                            # 之後 save 一起寫：下一轉一讀就知道是舊紀錄
        p = allp.get(str(qid)) or {}
        if o.get('fresh') or time.time() - (p.get('ts') or 0) > PROGRESS_TRUST_S:
            p = {}
        self.all, self.p = allp, p
        self.p.setdefault('done', [])
        self.info: dict = {}
        self.prep_ran = False                                              # 本次 run 剛做完 prep（單人 + 遇敵關）→ 第 1 輪 catch 不再 solo；不存檔

    def cur_trans(self):
        """目前隊長轉數（grind trans.json；讀不到 None = 不判斷）。測試替身可換 T.cur_trans"""
        f = getattr(self.T, 'cur_trans', None)
        try:
            return f() if f else None
        except Exception:                                              # noqa: BLE001
            return None

    def save(self):
        self.p['ts'] = time.time()
        self.all[str(self.qid)] = self.p
        save_progress(self.all)

    def fail(self, rc: int, msg: str, manual: str = '') -> int:
        self.info['msg'] = msg
        if manual:
            self.info['manual'] = manual
        event(f'任務 {self.qid} 失敗 rc={rc}：{msg}' + (f'｜手動：{manual}' if manual else ''))
        try:
            import errlog
            errlog.add(f'petquest {self.qid}：{msg}', source='petquest')
        except Exception:                                              # noqa: BLE001
            pass
        return rc

    def sub(self, script, args, timeout=3600):
        event(f'→ {script} {" ".join(map(str, args))}')
        rc, lines = self.T.sub(script, list(args), timeout)
        event(f'← {script} rc={rc}')
        return rc, lines

    def pass_or(self, rc: int, code: int, msg: str, manual: str = '') -> int:
        return rc if rc in PASS else self.fail(code, msg, manual)

    def verify_args(self) -> list:
        """--verify-defer（postrebirth 傳）→ questrun 加 --verify defer（沒風險事件的逐人驗證延到 postrebirth 收尾）"""
        return ['--verify', 'defer'] if self.o.get('verify_defer') else []

    def pet_levels(self, slots) -> tuple:
        """pet.py levels（只讀等級 + nh，不認名字）→ (rc, {角色: [格]})"""
        args = ['levels', '--role', 'all', '--json'] + (['--slots', ','.join(map(str, slots))] if slots else [])
        rc, lines = self.sub('pet.py', args, 600)
        return rc, (last_json(lines).get('roles') or {})

    def pet_list(self, roles=ALL_ROLES, cand=None) -> tuple:
        args = ['list', '--role', 'all', '--json']          # pet.py list --role 只收單一角色或 all（逗號分隔會 rc 1，2026-10-14 恐龍博士 164）→ 一律 all 再依 roles 過濾
        if cand:
            args += ['--candidates', cand]
        rc, lines = self.sub('pet.py', args, 600)
        d = last_json(lines)
        got = d.get('roles') or {}
        return rc, (got if list(roles) == ALL_ROLES else {r: v for r, v in got.items() if r in roles})

    # -- 段 --
    def s_accept(self) -> int:
        rc, tail = self.sub('questrun.py', ['run', self.qid, '--after', 'none'] + self.verify_args(), 4 * 3600)
        if rc == 0:
            event(f'任務 {self.qid}：questrun 回 0 = 任務已完成 → 跳過抓 / 練 / 交，只做收尾')
            self.p['already_done'] = True
            return 0
        if rc in (115, 155, 117):
            done1 = accept_turned_in(rc, tail, self.q)
            if done1:
                # 卡坦：接取對話時寵物已備妥 → 第 1 步當場交掉，追蹤已在步 2（2026-10-17 p3 實測 12:09:51 accept 155 訊息「步 2」）；
                # 再跑 turnin1 只是白試 36 秒（又開詳情 + 點追蹤兩次沒反應 155）→ 記起來讓 turnin1 直接跳過
                self.p['turned'] = sorted(set(self.p.get('turned') or []) | {done1})
                event(f'任務 {self.qid}：接取回 155 且追蹤已在步 {done1 + 1} → 第 {done1} 輪接取時已交完，跳過 turnin{done1}')
            if self.q['kind'] == 'quiz':
                self.p['step'] = self.T.read_step(self.q['track'])
            return 0
        return self.pass_or(rc, EXIT_ACCEPT, f'接取：questrun 退出碼 {rc}（預期 0 / 115 / 155 / 117）',
                            f'uv run --no-project python tools/gui/questrun.py run {self.qid} --after none')

    def battle_names(self) -> dict:
        """進度檔記的各角色戰寵名（prep 讀到的；沒記的角色不在內）"""
        if not self.p.get('battle') and self.p.get('orig'):               # 舊進度檔（本功能前跑到一半）只有 orig：當時全員戰寵 = 朵拉比斯，沿用
            return {r: BATTLE_PET for r in self.p['orig']}
        return self.p.get('battle') or {}

    def battle_groups(self) -> list:
        """[(戰寵名, 角色參數)]：角色參數 = 'all'（全員同名）或逗號分隔；給 pet.py / pet_catch.py 的 --role / --roles"""
        return [(nm, 'all' if rs == ALL_ROLES else ','.join(rs)) for nm, rs in group_by_name(self.battle_names())]

    def common_battle(self) -> str | None:
        """全員同名才回名字（petwatch --back 只收單一名字）"""
        g = self.battle_groups()
        return g[0][0] if len(g) == 1 and g[0][1] == 'all' else None

    def record_orig(self) -> int:
        rc, rs = self.pet_list()
        if rc:
            return self.pass_or(rc, EXIT_PREP, f'讀寵物欄失敗 pet rc={rc}', 'uv run --no-project python tools/gui/pet.py list --role all')
        if self.q['kind'] == 'catch':
            return self.record_slot2(rs)
        names = dict(self.battle_names())                                 # 續跑沿用已記的，不重讀覆蓋
        if [r for r in ALL_ROLES if not names.get(r)]:
            got, bad = pick_battle_names(rs)
            for r in ALL_ROLES:
                if not names.get(r) and got.get(r):
                    names[r] = got[r]
            miss = {r: bad.get(r, '讀不到') for r in ALL_ROLES if not names.get(r)}
            if miss:
                return self.fail(EXIT_PREP, f'讀不到出戰寵名字（不亂猜；先把戰寵設出戰 / 讓名字讀得出）：{miss}',
                                 'uv run --no-project python tools/gui/pet.py list --role all（確認每人有 1 隻出戰寵）')
        self.p['battle'] = names
        lv = battle_levels_by(rs, names)
        miss = [r for r in ALL_ROLES if not lv.get(r)]
        if miss:
            return self.fail(EXIT_PREP, f'{miss} 寵物欄找不到戰寵 {names} 或等級讀不到（換回時要用 --expect-level 原等級）：{lv}',
                             'uv run --no-project python tools/gui/pet.py list --role all（看清楚後手動記下等級）')
        self.p['orig'] = lv
        event(f'原戰寵（各角色出戰寵）：{names}；等級：{lv}')
        self.save()
        return 0

    def record_slot2(self, rs) -> int:
        """恐龍博士 / 卡坦：記每人寵物欄第 2 格（BATTLE_SLOT）的名字 + 等級 → 進度檔 battle / orig（restore 依此取回）。
        任何人第 2 格空 / 名字讀不出 / 是騎寵 → 162，一隻都不存（不猜、存倉不碰騎寵）"""
        names, lv, bad = pick_slot2(rs)
        if bad:
            return self.fail(EXIT_PREP, f'第 {BATTLE_SLOT} 格不能記 / 存（不猜、存倉不碰騎寵）：{bad}',
                             f'uv run --no-project python tools/gui/pet.py list --role all（確認每人第 {BATTLE_SLOT} 格是戰寵、名字讀得出）')
        self.p['battle'], self.p['orig'] = names, lv
        event(f'第 {BATTLE_SLOT} 格（戰寵）：{names}；等級：{lv}')
        self.save()
        return 0

    def encounter_off(self) -> int:
        try:
            self.T.encounter_off()
        except RuntimeError as e:
            return self.fail(EXIT_PREP, f'關原地遇敵失敗：{e}', '主畫面右下「遇敵」手動關')
        return 0

    def solo(self, code: int) -> int:
        """抓寵前：關原地遇敵 + 等戰鬥結束 → 解散隊伍（已全員單人 team 回 0）"""
        rc = self.encounter_off()
        if rc:
            return rc
        rc, _ = self.sub('team.py', ['disband'], 300)
        if rc:
            return self.pass_or(rc, code, f'解散隊伍失敗 team rc={rc}', 'uv run --no-project python tools/gui/team.py disband')
        return 0

    def slot2_shared(self) -> dict | None:
        """進度檔頂層共用紀錄 slot2_stored（第 2 格戰寵名 / 等級已存個人倉庫；24 小時內才算）；沒有 / 過期 → None"""
        rec = self.all.get('slot2_stored') or {}
        if rec.get('orig') and rec.get('battle') and 0 <= self.T.clock() - (rec.get('ts') or 0) <= PROGRESS_TRUST_S:
            return rec
        return None

    def s_prep(self) -> int:
        if self.p.get('already_done'):
            return 0
        rc = self.solo(EXIT_PREP) if self.q['kind'] == 'catch' else self.encounter_off()   # solo = 關遇敵 + 等戰鬥結束 + 解散
        if rc:
            return rc
        self.prep_ran = True
        if self.q['kind'] == 'catch':
            rec = self.slot2_shared()
            if rec and not self.p.get('stored'):                          # 恐龍博士 prep 已存過第 2 格：直接沿用紀錄，不讀不存（使用者 2026-10-16）
                self.p['orig'], self.p['battle'], self.p['stored'] = rec['orig'], rec['battle'], True
                event(f'第 {BATTLE_SLOT} 格戰寵 {rec["battle"]} 已存個人倉庫（共用紀錄 slot2_stored）→ 沿用原等級 {rec["orig"]}，不讀不存')
                self.save()
                return 0
        if not self.p.get('orig') or not self.battle_names():
            rc = self.record_orig()
            if rc:
                return rc
        if self.q['kind'] == 'quiz':
            pet = self.q['pet']
            rc, _ = self.sub('pet_catch.py', ['--unlock', '戰寵'], 900)   # 猜謎：金布伊要換出戰，要先解鎖（只有猜謎才取消鎖定）
            if rc:
                return self.pass_or(rc, EXIT_PREP, f'取消鎖定戰寵失敗 rc={rc}', 'uv run --no-project python tools/gui/pet_catch.py --unlock 戰寵')
            rc, _ = self.sub('pet.py', ['set-state-many', '--role', 'all', pet, '出戰'], 900)
            if rc:
                return self.pass_or(rc, EXIT_PREP, f'{pet} 5 人出戰失敗 pet rc={rc}', f'uv run --no-project python tools/gui/pet.py set-state-many --role all {pet} 出戰')
            rc, _ = self.sub('pet_catch.py', ['--lock', '戰寵', '--battle-pet', pet], 900)
            if rc:
                return self.pass_or(rc, EXIT_PREP, f'鎖定戰寵 = {pet} 失敗 rc={rc}', f'uv run --no-project python tools/gui/pet_catch.py --lock 戰寵 --battle-pet {pet}')
            return 0
        for nm, ra in self.battle_groups():                                # 第 2 格的寵物：各角色名字可不同，同名的一組存
            rc, _ = self.sub('pet.py', ['store-many', '--role', ra, '--pets', nm, '--depot', 'personal', '--skip-missing'], 1200)   # 續跑時已存過的人略過；同名多隻 → pet 72 停（不猜哪隻）
            if rc:
                return self.pass_or(rc, EXIT_PREP, f'{nm} 存個人倉庫失敗 pet rc={rc}（寵物欄要空出 4 格）',
                                    f'uv run --no-project python tools/gui/pet.py store-many --role {ra} --pets {nm} --depot personal')
        self.p['stored'] = True                                            # restore 要取回（接任務回 0 = 已完成時也要）
        self.all['slot2_stored'] = {'qid': self.qid, 'orig': self.p['orig'], 'battle': self.p['battle'], 'ts': self.T.clock()}   # 共用紀錄：接著跑的卡坦 prep 直接沿用，restore 成功才清
        self.save()
        return 0

    def round_conf(self, stage) -> dict:
        return self.q['rounds'][stage_round(stage) - 1]

    def buy_plus(self, role, need, have=0) -> int:
        """誘餌不夠只買缺額（使用者 2026-10-15）：背包現有 have 個誘餌照用，外掛「+」按到可抓捕數 = need（共 need − have 次）。
        不需旗標、不設次數上限（使用者 2026-10-15）；catchbuy.buy_to：不讀石幣；按前讀不到鑽石 → 不按停手，每按一次後鑽石讀不到 / 有變、可抓捕數不是 +1 → 停；
        按前讀到的可抓捕數 < have（外掛沒把背包誘餌算進去）→ 一次都不按、停手（不猜能不能相加）"""
        event(f'{role} 誘餌現有 {have}、要 {need} → 外掛「+」買缺額 {need - have} 次（預計最多 {(need - have) * PLUS_COST} 石幣）')
        kind, msg, rc, bought = catchbuy.buy_to(role, need, self.T.money, self.T.press_plus, event, min_before=have)
        self.info.setdefault('bought', []).extend(bought)
        if kind == 'ok':
            return 0
        return self.pass_or(rc, EXIT_BAIT, msg) if kind == 'pass' else self.fail(EXIT_BAIT, msg)

    def s_catch(self, stage) -> int:
        """catch：一次抓滿 N → 改名 → 存公共 → 取個人倉庫溢出的改名（使用者 2026-10-16 最簡流程）。
        小步進度檔 sub_r<輪>：caught → renamed → stored → taken_personal（distribute 段再 → distributed_taken → distributed）；中斷從下一小步接，不重新盤點。
        抓前 / 抓後都不讀寵物欄（在欄 = min(N, CATCH_FREE=4)、其餘溢出個人倉庫）；第 1 輪接 prep 不重複 solo。"""
        if self.p.get('already_done'):
            return 0
        rd, count = self.round_conf(stage), self.q.get('count', 5)
        assign = rd['assign']
        catchers = [r for r, _, _ in assign]
        key, skey = sub_key(stage), f'catch_started_{stage}'
        st = self.p.get(key) or {}
        if sub_at(st, 'taken_personal'):
            return 0
        if not st.get('step'):                                          # 還沒抓完：從頭（抓前檢查 → 誘餌 → 抓）
            if self.p.get(skey):                                         # 上次抓到一半（開始抓過、沒 caught）：不讀寵物欄、不盤點、不重抓 → 請人處理（使用者 2026-10-16）
                return self.fail(EXIT_CATCH, f'{stage}：上次抓寵中斷（進度檔 {skey} 有旗標、沒 caught），寵物欄可能已有任務寵（不自動盤點）→ 手動整理後重跑，或全部丟掉後 --fresh 重抓',
                                 f'uv run --no-project python tools/gui/pet.py list --role all；整理完 petquest.py run {self.qid} --from {stage} --fresh')
            if not (self.prep_ran and stage_round(stage) == 1):          # 第 1 輪 prep 剛做完 = 已單人 + 遇敵關；第 2 輪（前面 turnin 組隊）/ catch 單獨續跑才 solo
                rc = self.solo(EXIT_CATCH)
                if rc:
                    return rc
            in_bar = {r: min(count, CATCH_FREE) for r in catchers}        # prep 後抓寵者空格固定 4（騎寵 + 4 空；卡坦第 2 輪前鯊已交出也是 4）→ 不讀寵物欄
            if count - CATCH_FREE > CATCH_FREE:
                return self.fail(EXIT_CATCH, f'一次抓 {count} 隻，個人倉庫溢出 {count - CATCH_FREE} 隻超過寵物欄空格 {CATCH_FREE}（溢出的要能一次取回）', '')
            event(f'{stage}：{catchers} 一次抓滿 {count} 隻（寵物欄空格 {CATCH_FREE}，放不下的自動進個人倉庫）')
            rc = self.take_bait(assign, count)
            if rc:
                return rc
            self.p[skey] = True
            self.save()
            rc, _ = self.sub('pet_catch.py', ['--assign', csv_assign(assign), '--count', count, '--stages', 'setup,wait'], 3600)
            if rc:                                                       # pet_catch 失敗時自己會取消自動抓寵（9 / 10 除外）
                return self.pass_or(rc, EXIT_CATCH, f'抓寵失敗 pet_catch rc={rc}（14 系別 / 物種選不到、103 設定 / 逾時）；已取消自動抓寵，寵物欄沒有任務寵時重跑會從頭抓',
                                    f'uv run --no-project python tools/gui/petquest.py run {self.qid} --from {stage}（或 pet_catch.py --catch-off 後手動）')
            st = {'step': 'caught', 'in_bar': in_bar}
            self.p[key] = st
            self.save()
            # 不做 baitback（使用者 2026-10-16：誘餌只取 / 買剛好 N，抓完不會剩，不用存回）
        in_bar = st.get('in_bar') or {}
        if not sub_at(st, 'renamed'):                                    # 1. 欄內數字名（成長字串）全改回物種名
            rc = self.reset_names(catchers)
            if rc:
                return rc
            st['step'] = 'renamed'
            self.save()
        if not sub_at(st, 'stored'):                                     # 2. 改完名的馬上全部存公共（一次 store-many --plan：面板開一次、頭像連續換人；騎寵不碰）
            done = st.setdefault('stored_roles', [])
            todo = [(r, sp) for r, _, sp in assign if r not in done and in_bar.get(r, 0) > 0]
            if todo:
                plan = ','.join(f'{r}:{sp}×{in_bar[r]}' for r, sp in todo)
                rc, lines = self.sub('pet.py', ['store-many', '--plan', plan, '--depot', 'public', '--pick', 'last'], 3600)
                ops = last_json(lines).get('ops') or []
                for r, sp in todo:                                       # 已存完的人記進度（失敗也記，重跑只做剩下的人）
                    mine = [o for o in ops if isinstance(o, dict) and o.get('role') == r]
                    if len(mine) >= in_bar[r] and all(o.get('rc') == 0 for o in mine):
                        done.append(r)
                self.save()
                if rc:
                    return self.pass_or(rc, EXIT_DIST, f'存公共失敗 pet rc={rc}（已存完 {done}）；重跑只做剩下的人',
                                        f'uv run --no-project python tools/gui/pet.py store-many --plan "{plan}" --depot public --pick last')
            st['step'] = 'stored'
            self.save()
        spill = {r: count - in_bar.get(r, 0) for r in catchers if count - in_bar.get(r, 0) > 0}       # 3. 個人倉庫溢出的取出來改名（抓寵者自己就有自己那種）
        if spill:
            plan = ','.join(f'{r}:?' for r in catchers for _ in range(spill.get(r, 0)))     # 溢出的從沒改名（成長字串）：取沒名字的卡，抓寵者只抓一種 → 不認物種
            rc, _ = self.sub('pet.py', ['take-many', '--depot', 'personal', '--plan', plan], 3600)
            if rc:
                return self.pass_or(rc, EXIT_DIST, f'從個人倉庫取回溢出的任務寵失敗 pet rc={rc}（72 = 沒名字的卡找不到 / 多於溢出隻數）',
                                    f'uv run --no-project python tools/gui/pet.py take-many --depot personal --plan "{plan}"')
            rc = self.reset_names(list(spill))
            if rc:
                return rc
            extra = ','.join(f'{r}:{sp}×{spill[r] - 1}' for r, _, sp in assign if spill.get(r, 0) > 1)      # 溢出 > 1 時多的再存公共（欄只留 1 隻自用；一般情況溢出剛好 1 隻 → 不用），一次 --plan
            if extra:
                rc, _ = self.sub('pet.py', ['store-many', '--plan', extra, '--depot', 'public', '--pick', 'last'], 1800)
                if rc:
                    return self.pass_or(rc, EXIT_DIST, f'多的任務寵存公共失敗 pet rc={rc}',
                                        f'uv run --no-project python tools/gui/pet.py store-many --plan "{extra}" --depot public --pick last')
        st['step'] = 'taken_personal'
        self.save()
        event(f'{stage}：抓寵 / 改名 / 存公共 / 取個人倉庫完成')
        return 0

    def take_bait(self, assign, count) -> int:
        """誘餌：每個抓寵者這一輪一次取出並拆出 count 個（背包已剛好 → 不動）；不夠的人現有照用、只用「+」買缺額（不需旗標）"""
        rc, lines = self.sub('pet_catch.py', ['--assign', csv_assign(assign), '--count', count, '--stages', 'bait', '--keep-short-bait'], 1800)
        have = bait_short_counts(lines)
        if rc and rc != BAIT_ITEM:
            return self.pass_or(rc, EXIT_CATCH, f'取誘餌失敗 pet_catch rc={rc}', f'uv run --no-project python tools/gui/pet_catch.py --assign "{csv_assign(assign)}" --count {count} --stages bait')
        if rc == BAIT_ITEM:
            for r in [r for r, _, _ in assign if r not in bait_ok_roles(lines)]:      # have 讀不到 = 0 = 全買
                rc = self.buy_plus(r, count, have.get(r, 0))
                if rc:
                    return rc
        return 0

    def reset_names(self, roles) -> int:
        """pet.py reset-name --role <角色>：寵物欄成長字串名字 → 物種名（後面 store-many / 交寵物都靠物種名）。
        費用字樣（pet 67）→ 165 停手（鐵則 3）；驗證視窗 / 斷線透傳；其他失敗也停（不帶著沒改名的寵物往下存）"""
        rc, _ = self.sub('pet.py', ['reset-name', '--role', ','.join(roles)], 900)
        if rc in PASS:
            return rc
        if rc == PET_FEE:
            return self.fail(EXIT_DIST, f'還原名字時讀到費用字樣（pet rc={rc}）→ 已按取消、停手（鐵則 3）', '看 tools/.cache/ui-log/*pet-rename* 截圖，確認改名是否收費')
        if rc:
            return self.fail(EXIT_DIST, f'還原名字失敗 pet rc={rc}（{",".join(roles)}）',
                             f'uv run --no-project python tools/gui/pet.py reset-name --role {",".join(roles)}；之後 petquest.py run {self.qid} 從下一小步續跑')
        return 0

    def s_distribute(self, stage) -> int:
        """distribute：其他人從公共倉庫取自己缺的種類（一次 take-many）→ 只驗每人寵物欄剛好「騎寵 + 本輪種類數」格有寵物。
        格數 = 1 + 本輪物種數：恐龍博士 2 種 → 3 格（騎寵 + 魯尼帖斯 + 貝魯卡）；卡坦每輪 4 種（鯊 4 種 / 雞 4 種，每人每種各 1 隻）→ 5 格，不是 3。
        不比名字 / 縮圖 / 成長字串，不數倉庫。續跑：sub_r<輪>.taken = 已取到的 角色:物種，只補缺的"""
        if self.p.get('already_done'):
            return 0
        assign = self.round_conf(stage)['assign']
        st = self.p.setdefault(sub_key(stage), {})
        if not sub_at(st, 'distributed_taken'):
            todo = [f'{r}:{sp}' for r, sp in take_plan(assign) if f'{r}:{sp}' not in (st.get('taken') or [])]
            event(f'{stage}：從公共倉庫取 {len(todo)} 隻 → take-many {",".join(todo)}')
            rc, lines = self.sub('pet.py', ['take-many', '--depot', 'public', '--plan', ','.join(todo)], 3600)
            if rc:
                done = [f'{o.get("role")}:{o.get("pet") or o.get("target") or o.get("name")}' for o in (last_json(lines).get('ops') or []) if isinstance(o, dict) and o.get('ok')]
                st.setdefault('taken', []).extend(d for d in done if d in todo)
                self.save()
                return self.pass_or(rc, EXIT_DIST, f'公共倉庫分配 take-many 失敗 pet rc={rc}' + (f'（已取到 {done}）' if done else '') + '；重跑只補沒取到的',
                                    f'重跑 uv run --no-project python tools/gui/petquest.py run {self.qid} --from {stage}')
            st['step'] = 'distributed_taken'
            self.save()
        want = 1 + len({sp for _, _, sp in assign})
        rc, rs = self.pet_list(ALL_ROLES)
        if rc:
            return self.pass_or(rc, EXIT_DIST, f'分配後讀寵物欄失敗 pet rc={rc}')
        bad = bar_count_bad(rs, want)
        if bad:
            return self.fail(EXIT_DIST, f'分配後每人寵物欄應剛好 {want} 格有寵物（騎寵 + 本輪 {want - 1} 種）：實際 {bad}', 'uv run --no-project python tools/gui/pet.py list --role all')
        st['step'] = 'distributed'
        self.save()
        return 0

    def s_train(self, stage) -> int:
        if self.p.get('already_done'):
            return 0
        if self.q['kind'] == 'quiz':
            return self.train_quiz()
        rd = self.round_conf(stage)
        first = rd['assign'][0][2]
        steps = [('pet.py', ['set-state-slot', '--role', 'all', '--slots', str(BATTLE_SLOT), '出戰'], f'5 人第 {BATTLE_SLOT} 格出戰'),   # 不認物種（2026-10-16）：第 1 格騎寵、分配後第 2 格必是任務寵；出戰本身已驗證，失敗就停
                 ('grind.py', ['start', '--spot', TRAIN_SPOT], f'grind start {TRAIN_SPOT}')]
        if not self.autoswap_is_on():                                # 自動轉換戰寵整個任務只勾一次（卡坦第 2 輪 / 恐龍博士帶 --keep-autoswap 接過來都已勾）
            steps.insert(0, ('pet_catch.py', ['--autoswap', 'on'], '自動轉換戰寵 on'))
        for script, args, why in steps:
            rc, _ = self.sub(script, args, 1800)
            if rc == 74 and script == 'pet.py' and self.autoswap_is_on():
                # 自動轉換戰寵已開 / 戰寵鎖定（續跑時使用者或主 session 已手動設好出戰寵）：出戰鈕點了不會變，不算失敗，繼續練寵輪詢（2026-10-16 p3 實跑）
                event(f'{stage}：{why} rc=74（外掛已鎖定戰寵 / 自動轉換開著，出戰寵由外掛管）→ 略過繼續')
                continue
            if rc:
                return self.pass_or(rc, EXIT_TRAIN, f'練寵準備：{why} 失敗 rc={rc}', f'uv run --no-project python tools/gui/{script} {" ".join(map(str, args))}')
            if script == 'pet_catch.py':
                self.all['autoswap_on'] = {'qid': self.qid, 'ts': self.T.clock()}
                self.save()
        t0 = self.T.clock()
        need = rd['need']
        # 只讀每人「最後一格」的等級（2026-10-16 使用者）：自動轉換戰寵依序換寵，最後一格達標 = 前面的都先過；不認寵物、不呼叫 pet.py list
        last_slot = BATTLE_SLOT + len(need) - 1               # 第 2 格起每種任務寵一格：恐龍博士 2 種 → 第 3 格、卡坦 4 種 → 第 5 格
        gate = max(need.values())                             # 門檻 = 本輪 need 最大值（恐龍博士 30、卡坦 25）
        tc = TrainConfirm({'slot': gate})
        smap = {(r, 'slot'): [last_slot] for r in ALL_ROLES}
        while True:
            self.T.sleep(POLL_S)
            rc, lv = self.pet_levels([last_slot])
            cur = levels_of(lv, smap) if not rc else {}
            if rc in PASS:
                return rc
            tc.update(cur)                                   # 讀取失敗 = cur 空，不動，下一輪再讀
            lag = {r: v for (r, _), v in cur.items() if (r, 'slot') not in tc.locked}
            ok = tc.done(smap)
            event(f'{stage}：5 人第 {last_slot} 格全部 ≥ {gate}（逐人連兩次確認）' if ok else
                  f'{stage}：練寵進度 讀取失敗 rc={rc}' if rc else f'{stage}：第 {last_slot} 格等級 未鎖定 {lag}（門檻 {gate}，已鎖定 {len(tc.locked)}/{len(smap)}）')
            if ok:
                break
            if self.T.clock() - t0 > TRAIN_MAX_S:
                return self.fail(EXIT_TRAIN, f'練寵 {TRAIN_MAX_S // 60} 分鐘仍未達標：{lag}', '看 pet.py list；沒出戰寵就 set-state 出戰，達標後 --from turnin 續跑')
        # 第二次讀到最後一格達標就馬上改等待，只改最後那一格（前面的任務寵已被自動轉換戰寵換下、本來就是等待；使用者 2026-10-16）→ 再關遇敵
        rc, _ = self.sub('pet.py', ['set-state-slot', '--role', 'all', '--slots', str(last_slot), '等待', '--pause-encounter'], 1800)   # 自動轉換戰寵開著、練寵中戰鬥多 → rc=74 / 78（p3 實機兩次）
        if rc:
            return self.pass_or(rc, EXIT_TRAIN, f'練完：最後一格（第 {last_slot} 格）改等待失敗 rc={rc}', f'uv run --no-project python tools/gui/pet.py set-state-slot --role all --slots {last_slot} 等待')
        rc = self.encounter_off()
        if rc:
            return rc
        offs = []
        last_round = stage_round(stage) >= len(self.q['rounds'])
        if last_round and not self.o.get('keep_autoswap'):           # 整個任務最後才關：卡坦第 2 輪 / 恐龍博士沒帶 --keep-autoswap
            offs.insert(0, ('pet_catch.py', ['--autoswap', 'off'], '自動轉換戰寵 off'))
        else:
            event(f'{stage}：自動轉換戰寵先不關（卡坦第 1 輪 / --keep-autoswap 後面還有卡坦，最後才關）')
        for script, args, why in offs:
            rc, _ = self.sub(script, args, 1800)
            if rc:
                return self.pass_or(rc, EXIT_TRAIN, f'練完：{why} 失敗 rc={rc}', f'uv run --no-project python tools/gui/{script} {" ".join(map(str, args))}')
            if '--autoswap' in args:
                self.all.pop('autoswap_on', None)
        self.p['rested'] = {'stage': stage.replace('train', 'turnin'), 'ts': self.T.clock()}   # 交件段帶 --rested（questrun 不重做 rest-all）
        self.save()
        return 0

    def autoswap_is_on(self) -> bool:
        """進度檔頂層 autoswap_on（24 小時內）= 已勾過、還沒關"""
        a = self.all.get('autoswap_on') or {}
        return bool(a) and self.T.clock() - (a.get('ts') or 0) < PROGRESS_TRUST_S

    def train_quiz(self) -> int:
        q = self.q
        gargs = ['start'] + (['--spot', QUIZ_SPOT] if QUIZ_SPOT else [])
        rc, _ = self.sub('grind.py', gargs, 1800)
        if rc:
            return self.pass_or(rc, EXIT_TRAIN, f'grind {" ".join(gargs)}（去練功）失敗 rc={rc}', f'uv run --no-project python tools/gui/grind.py {" ".join(gargs)}')
        back = self.common_battle()
        if not back:
            return self.fail(EXIT_ARGS, f'各角色戰寵名不同 {self.battle_names()}：petwatch --back 只收單一名字 → 不自動練（猜謎）',
                             '手動 petwatch.py 逐人，或只對同名的人跑')
        back, rc = self.verify_back(back)
        if rc:
            return rc
        args = ['--pet', q['pet'], '--level', q['level'], '--back', back, '--exp-fruit']
        rc, _ = self.sub('petwatch.py', args, 4 * 3600)
        if rc:
            return self.pass_or(rc, EXIT_TRAIN, f'petwatch 失敗 rc={rc}（4 = 有人換回失敗被放棄）',
                                f'uv run --no-project python tools/gui/petwatch.py {" ".join(map(str, args))}；放棄的人：pet_catch.py --unlock 戰寵 --roles X → pet.py set-state X {back} 出戰 → pet_catch.py --lock 戰寵 --roles X --battle-pet {back}')
        return 0

    def verify_back(self, back: str) -> tuple:
        """petwatch --back 取值前核對 5 人寵物欄真的有 back（2026-10-17 p2：進度檔沿用 0 轉的「迪基格斯」，一轉後戰寵已是朵拉比斯 → 5 人換回失敗 rc 4）。
        → (名字, 0)：全員有 → back；有人沒有、但全員都有 BATTLE_PET（朵拉比斯）→ 改用它並更新進度檔。
        否則 (None, 退出碼)：不猜（讀寵物欄失敗照 pass_or）"""
        rc, rs = self.pet_list()
        if rc:
            return None, self.pass_or(rc, EXIT_TRAIN, f'練寵前核對 --back「{back}」：讀寵物欄失敗 pet rc={rc}', 'uv run --no-project python tools/gui/pet.py list --role all')
        has = lambda nm: [r for r in ALL_ROLES if not any(strict_species(sl) == nm for sl in (rs.get(r) or []))]   # noqa: E731
        miss = has(back)
        if not miss:
            return back, 0
        if back != BATTLE_PET and not has(BATTLE_PET):
            event(f'進度檔記的戰寵「{back}」{miss} 寵物欄沒有（舊轉紀錄？）→ 改用 5 人都有的 {BATTLE_PET}')
            self.p['battle'] = {r: BATTLE_PET for r in ALL_ROLES}
            self.save()
            return BATTLE_PET, 0
        return None, self.fail(EXIT_TRAIN, f'petwatch --back「{back}」：{miss} 寵物欄沒有這隻（進度檔可能是舊轉的紀錄）→ 不練（練完會換回失敗）',
                  'uv run --no-project python tools/gui/pet.py list --role all 確認戰寵；之後手動 petwatch.py --back 戰寵名')

    def s_step1(self) -> int:
        if self.p.get('already_done'):
            return 0
        if self.p.get('step') not in (1, None):
            event(f'猜謎三兄弟：追蹤步號 {self.p.get("step")} ≠ 1 → 步 1 已過，跳過')
            return 0
        pet = self.q['pet']
        import questrun                                                # 安全任務才快速連按對話框（questdefs.fast_dialog，2026-10-17）
        rc, _ = self.sub('quest.py', questrun.with_fast_dialog(['--task', self.q['track'], '--stop-after-rewards', 1, '--max-seconds', 900],
                                                             questdefs.fast_dialog(self.qid)), 2400)
        if rc == 3:                                                    # 2026-10-14 13:35（errlog #861）：步 1 對話給了金布伊（沒有獲得物品窗，--stop-after-rewards 不停）→
            st = self.T.read_step(self.q['track'])                     # 追蹤已進「交77金豬」、點追蹤不巡路 → quest.py 3。讀步號：已前進 = 步 1 完成
            if isinstance(st, int) and st > 1:
                event(f'猜謎三兄弟：步 1 quest.py 回 3，但追蹤步號已是 {st} → 步 1 完成（不是卡住），照常驗寵物欄')
                self.p['step'] = st
                rc = 0
        if rc:
            return self.pass_or(rc, EXIT_ACCEPT, f'步 1（巡到 810 伊那多拿金豬）quest.py rc={rc}',
                                '點任務追蹤重試（會直接傳送到 810）；仍不行就人工處理')
        rc, rs = self.pet_list()
        if rc:
            return self.pass_or(rc, EXIT_ACCEPT, f'步 1 後讀寵物欄失敗 pet rc={rc}')
        miss = [r for r in ALL_ROLES if not count_species(rs.get(r), pet)]
        if miss:
            return self.fail(EXIT_ACCEPT, f'步 1 後 {miss} 沒有{pet}', 'uv run --no-project python tools/gui/pet.py list --role all；沒拿到就點任務追蹤重試 / 人工處理')
        return 0

    def s_turnin(self, stage) -> int:
        if self.p.get('already_done'):
            return 0
        if self.q['kind'] == 'quiz':
            rc = self.encounter_off()
            if rc:
                return rc
            rc, _ = self.sub('questrun.py', ['run', self.qid, '--after', 'none'] + self.verify_args(), 3600)
            return 0 if not rc else self.pass_or(rc, EXIT_TURNIN, f'交金豬 questrun rc={rc}', f'uv run --no-project python tools/gui/questrun.py run {self.qid} --after none')
        rounds = self.q['rounds']
        r = stage_round(stage)
        last = r == len(rounds)
        if r in (self.p.get('turned') or []) and not last:
            event(f'交寵物第 {r} 輪：接取時已交完 → 跳過（不重跑 questrun）')
            return 0
        args = ['run', self.qid, '--after', 'none', '--pet-turnin']
        rs_ = self.p.get('rested') or {}
        if rs_.get('stage') == stage and 0 <= self.T.clock() - (rs_.get('ts') or 0) <= RESTED_S:   # 本輪 train 段剛 rest-all 成功 → questrun 交件前不重做（review 1013b §2.2）
            args.append('--rested')
        rc, _ = self.sub('questrun.py', args + self.verify_args(), 3600)
        manual = f'uv run --no-project python tools/gui/questrun.py run {self.qid} --after none --pet-turnin'
        if last:
            return 0 if not rc else self.pass_or(rc, EXIT_TURNIN, f'交寵物（最後一輪）questrun rc={rc}（預期 0）', manual)
        if rc not in (0, 115, 117, 155):
            return self.pass_or(rc, EXIT_TURNIN, f'交寵物第 {r} 輪 questrun rc={rc}（預期 117 / 155 停在下一步）', manual)
        st = self.T.read_step(self.q['track'])
        if st != r + 1:
            return self.fail(EXIT_TURNIN, f'交寵物第 {r} 輪後追蹤步號 {st}（要 {r + 1}）→ 沒交到？', 'questrun.py status --role all ' + str(self.qid) + '；pet.py list 看任務寵還在不在')
        event(f'交寵物第 {r} 輪完成，追蹤進步 {st}')
        return 0

    def s_drop(self, stage) -> int:
        if self.p.get('already_done'):
            return 0
        name = self.q['drop'] if self.q['kind'] == 'quiz' else self.round_conf(stage).get('drop')
        if not name:
            return 0
        manual = f'uv run --no-project python tools/gui/petdrop.py all {name} --confirm-name {name} --max-level 1'
        if not self.o.get('confirm_drop'):
            return self.fail(EXIT_DROP, f'獎勵寵「{name}」要丟：沒給 --confirm-drop（不可逆）→ 停手', manual + '（或重跑加 --confirm-drop）')
        rc, _ = self.sub('petdrop.py', ['all', name, '--confirm-name', name, '--max-level', 1], 1200)
        if rc:
            return self.pass_or(rc, EXIT_DROP, f'丟「{name}」失敗 petdrop rc={rc}（73 = 防護擋下：等級不是 1 / 讀不到 / 出戰…）', manual + ' --dry-run 先看')
        return 0

    def s_store_reward(self) -> int:
        if self.p.get('already_done'):
            return 0
        rc, _ = self.sub('pet.py', ['store-many', '--role', 'all', '--pets', self.q['store_reward'], '--depot', 'personal', '--skip-missing'], 1200)
        if rc:
            return self.pass_or(rc, EXIT_RESTORE, f'獎勵{self.q["store_reward"]}存個人倉庫失敗 pet rc={rc}',
                                f'uv run --no-project python tools/gui/pet.py store-many --role all --pets {self.q["store_reward"]} --depot personal')
        return 0

    def s_restore(self) -> int:
        orig = self.p.get('orig') or {}
        names = self.battle_names()
        shown = '、'.join(sorted(set(names.values()))) or BATTLE_PET
        # 第 2 格存過個人倉庫 → 要取回（2026-10-15 起 prep 在接任務前，接取回 0 = 已完成時也存過；舊進度檔沒有 stored → 照舊「沒完成 = 存過」）
        took = self.q['kind'] == 'catch' and bool(self.p.get('stored') or not self.p.get('already_done'))
        if self.o.get('keep_autoswap') and took:
            event(f'{shown} 先不換回（--keep-autoswap：自動轉換戰寵開著會把剛換回的換掉、卡坦 prep 又要存倉）→ 共用紀錄 slot2_stored 留著（原等級 {orig}），由卡坦 restore 統一換回並清掉')
            return 0
        if [r for r in ALL_ROLES if not names.get(r)] and self.p.get('already_done'):
            rc, rs = self.pet_list()                                      # 任務本來就完成（沒跑 prep）：用當下出戰寵當戰寵，只收尾（鎖定 + 一般動作 + 驗）
            if rc:
                return self.pass_or(rc, EXIT_RESTORE, f'讀寵物欄失敗 pet rc={rc}', 'uv run --no-project python tools/gui/pet.py list --role all')
            got, bad = pick_battle_names(rs)
            if bad:
                return self.fail(EXIT_RESTORE, f'已完成任務的收尾：讀不到出戰寵名字（不亂猜）：{bad}', 'uv run --no-project python tools/gui/pet.py list --role all')
            names = self.p['battle'] = got
        if [r for r in ALL_ROLES if not names.get(r)]:
            return self.fail(EXIT_ARGS, f'進度檔沒有 5 人的戰寵名 {names} → 不盲換（舊進度檔 / prep 沒跑）',
                             f'手動 pet.py take-many --depot personal --plan "{LEADER}:戰寵名@等級,…"；或 --fresh 從 prep 重來')
        if took:
            if [r for r in ALL_ROLES if not orig.get(r)]:
                return self.fail(EXIT_ARGS, f'進度檔沒有 5 人原戰寵等級 {orig} → 不盲取（同名多隻）', f'手動 pet.py take-many --depot personal --plan "{LEADER}:{names.get(LEADER) or BATTLE_PET}@等級,…"')
            if not self.p.get('restore_taken'):                           # 續跑看進度檔記號，不讀寵物欄（2026-10-16 使用者）：take-many 成功才記
                plan = ','.join(f'{r}:{names[r]}@{orig[r]}' for r in ALL_ROLES)
                rc, _ = self.sub('pet.py', ['take-many', '--depot', 'personal', '--plan', plan], 1800)
                if rc:
                    return self.pass_or(rc, EXIT_RESTORE, f'取回原戰寵失敗 pet rc={rc}', f'uv run --no-project python tools/gui/pet.py take-many --depot personal --plan "{plan}"')
                self.p['restore_taken'] = True
                self.save()
            # 取回的原寵物一定放進第 2 格（任務寵已交 / 改等待、第 2 格空）→ 依格號出戰，不認名字
            rc, _ = self.sub('pet.py', ['set-state-slot', '--role', 'all', '--slots', str(BATTLE_SLOT), '出戰'], 900)
            if rc:
                return self.pass_or(rc, EXIT_RESTORE, f'第 {BATTLE_SLOT} 格出戰失敗 pet rc={rc}', f'uv run --no-project python tools/gui/pet.py set-state-slot --role all --slots {BATTLE_SLOT} 出戰')
        # 鎖定戰寵 + 戰寵一般動作 = 攻擊：外掛面板每組只開一次（pet_catch --lock --normal，逐人同一次停留做完）
        steps = [('pet_catch.py', ['--lock', '戰寵', '--battle-pet', nm, '--normal', '攻擊'] + ([] if ra == 'all' else ['--roles', ra]), f'鎖定戰寵 = {nm} + 一般動作 = 攻擊')
                 for nm, ra in self.battle_groups()]
        for script, args, why in steps:
            rc, _ = self.sub(script, args, 1200)
            if rc:
                return self.pass_or(rc, EXIT_RESTORE, f'{why} 失敗 rc={rc}', f'uv run --no-project python tools/gui/{script} {" ".join(map(str, args))}')
        rc, rs = self.pet_list()
        if rc:
            return self.pass_or(rc, EXIT_RESTORE, f'收尾讀寵物欄失敗 pet rc={rc}')
        bad = {}
        for r in ALL_ROLES:
            hits = [s for s in rs.get(r) or [] if slot_species(s) == names[r]]
            st = [(s.get('state'), s.get('level')) for s in hits]
            want = orig.get(r)
            okv = len(hits) == 1 and hits[0].get('state') == '出戰' and (not want or hits[0].get('level') is None
                                                                        or (hits[0]['level'] >= want if self.q['kind'] == 'quiz' else hits[0]['level'] == want))
            if not okv:
                bad[r] = (names[r], st)
        if bad:
            return self.fail(EXIT_RESTORE, f'收尾驗證：戰寵不是剛好 1 隻出戰 / 等級不對（原 {orig}）：{bad}', 'uv run --no-project python tools/gui/pet.py list --role all')
        event(f'收尾：5 人戰寵 {names} 出戰、鎖定戰寵、一般動作攻擊')
        if self.q['kind'] == 'catch' and self.all.pop('slot2_stored', None) is not None:   # 真正換回原寵了：清共用紀錄
            self.save()
        return 0

    def do(self, stage) -> int:
        b = stage_base(stage)
        fn = {'accept': lambda: self.s_accept(), 'prep': lambda: self.s_prep(), 'step1': lambda: self.s_step1(),
              'catch': lambda: self.s_catch(stage), 'distribute': lambda: self.s_distribute(stage), 'train': lambda: self.s_train(stage),
              'turnin': lambda: self.s_turnin(stage), 'drop': lambda: self.s_drop(stage), 'store_reward': lambda: self.s_store_reward(),
              'restore': lambda: self.s_restore()}[b]
        return fn()


def print_plan(qid: int, o: dict) -> None:
    q = QUESTS[qid]
    print(f'petquest 計畫：任務 {qid}（{q["track"]}）段 {stages_of(qid)}；誘餌不夠自動買（不需旗標）、--confirm-drop {bool(o.get("confirm_drop"))}')
    if q['kind'] == 'quiz':
        print(f'  accept   questrun.py run {qid} --after none（115 / 155 / 0）')
        print(f'  step1    （步號 1）quest.py --task {q["track"]} --stop-after-rewards 1 → pet.py list 5 人有{q["pet"]}')
        print(f'  prep     關遇敵 → pet.py list 記各角色出戰寵名 / 等級 → pet_catch --unlock 戰寵 → set-state-many {q["pet"]} 出戰 → pet_catch --lock 戰寵 --battle-pet {q["pet"]}')
        print(f'  train    grind.py start{" --spot " + QUIZ_SPOT if QUIZ_SPOT else "（去練功，依等級選點 + follow）"} → petwatch.py --pet {q["pet"]} --level {q["level"]} --back 戰寵名 --exp-fruit')
        print(f'  turnin   關遇敵 → questrun.py run {qid} --after none')
        print(f'  drop     petdrop.py all {q["drop"]} --confirm-name {q["drop"]} --max-level 1（要 --confirm-drop）')
        print(f'  restore  pet_catch --lock 戰寵 --battle-pet 戰寵名 --normal 攻擊 → pet.py list 驗')
    else:
        print(f'  prep     （不先接任務）關遇敵 + 等戰鬥結束 → team.py disband；有共用紀錄 slot2_stored（24 小時內，恐龍博士已存）→ 到此為止，沿用不讀不存；'
              f'沒有（單獨跑）才 → pet.py list 記每人第 {BATTLE_SLOT} 格名字 / 等級（空 / 讀不出 / 騎寵 → 162）'
              f' → pet.py store-many --role <同名的人> --pets 第 {BATTLE_SLOT} 格名字 --depot personal → 寫 slot2_stored')
        for i, rd in enumerate(q['rounds'], 1):
            sfx = str(i) if len(q['rounds']) > 1 else ''
            a = rd['assign']
            print(f'  catch{sfx}   一次抓滿 {q.get("count", 5)} 隻（不分批）：{"（第 1 輪接 prep，不 solo；" + ("第 2 輪先 solo" if len(q["rounds"]) > 1 else "單獨續跑才 solo") + "；不讀寵物欄）"} → pet_catch.py --assign "{csv_assign(a)}" --count {q.get("count", 5)} --stages bait'
                  f'（每人取 / 拆一次；不夠現有照用、外掛「+」只買缺額，不讀石幣，鑽石不變）→ --stages setup,wait（不 baitback）')
            print(f'            → pet.py reset-name --role {",".join(r for r, _, _ in a)} → 一次 store-many --plan "角色:物種×在欄隻數,…" --depot public --pick last'
                  f' → 溢出的 take-many --depot personal（--candidates {species_csv(a)}）+ reset-name（溢出 > 1 才再存多的）')
            print(f'  distribute{sfx} pet.py take-many --depot public --plan "{",".join(f"{r}:{sp}" for r, sp in take_plan(a))}" → pet.py list 只驗每人寵物欄 {1 + len({sp for _, _, sp in a})} 格有寵物（騎寵 + {len({sp for _, _, sp in a})} 種）')
            print(f'  train{sfx}   autoswap on（整個任務只勾一次）→ set-state-slot 第 2 格出戰（不認物種） → grind.py start --spot {TRAIN_SPOT} → 每 {POLL_S:.0f} 秒讀等級'
                  f'（只 pet.py levels --slots 最後一格 = {BATTLE_SLOT + len(rd["need"]) - 1}、不認寵物；每人連兩次 ≥ {max(rd["need"].values())}）→ set-state-slot 最後一格等待 → 關遇敵'
                  f'{"" if (i < len(q["rounds"]) or o.get("keep_autoswap")) else " → autoswap off（整個任務最後）"}')
            if i == 1:
                print(f'  accept   questrun.py run {qid} --after none（練完 rest-all 之後才接；115 / 155 / 117；0 = 已完成 → 只做 restore；不讀步號）')
            print(f'  turnin{sfx}  questrun.py run {qid} --after none --pet-turnin --rested{" --verify defer" if o.get("verify_defer") else ""}'
                  + ('（下一輪前讀步號要進到下一步）' if i < len(q['rounds']) else '（預期 0）'))
            if rd.get('drop'):
                print(f'  drop{sfx}    petdrop.py all {rd["drop"]} --confirm-name {rd["drop"]} --max-level 1（要 --confirm-drop）')
        if q.get('store_reward'):
            print(f'  store_reward pet.py store-many --role all --pets {q["store_reward"]} --depot personal（獎勵 Lv1）')
        if o.get('keep_autoswap'):
            print(f'  restore  （--keep-autoswap：整段跳過，共用紀錄 slot2_stored 留給卡坦 prep；卡坦 restore 統一換回）')
        else:
            print(f'  restore  pet.py take-many --depot personal --plan "角色:第 {BATTLE_SLOT} 格名字@原等級" （成功記 restore_taken） → set-state-slot 第 2 格出戰 → pet_catch --lock 戰寵 --normal 攻擊（面板只開一次）→ list 驗 → 清 slot2_stored')
    print('退出碼：160 參數 161 接取 162 準備 163 誘餌 / 買 164 抓 165 分配 166 練 167 交 168 丟 169 換回；9 驗證視窗 10 斷線')


def run(qid, tools=None, confirm_buy: bool = False, confirm_drop: bool = False, from_stage: str | None = None, to_stage: str | None = None,
        fresh: bool = False, dry_run: bool = False, verify_defer: bool = False, keep_autoswap: bool = False) -> int:
    LAST.clear()
    try:
        qid = int(qid)
    except (TypeError, ValueError):
        qid = None
    if qid not in QUESTS:
        print(f'petquest：只支援 {sorted(QUESTS)}', file=sys.stderr)
        return EXIT_ARGS
    stages = stages_of(qid)
    for s in (from_stage, to_stage):
        if s and s not in stages:
            print(f'petquest：段名 {s!r} 不在 {stages}', file=sys.stderr)
            return EXIT_ARGS
    o = dict(confirm_buy=confirm_buy, confirm_drop=confirm_drop, fresh=fresh, verify_defer=verify_defer, keep_autoswap=keep_autoswap)
    if dry_run:
        print_plan(qid, o)
        return 0
    T = tools or Tools()
    r = Run(qid, T, o)
    i0 = stages.index(from_stage) if from_stage else 0
    i1 = stages.index(to_stage) if to_stage else len(stages) - 1
    event(f'開始：任務 {qid} 段 {stages[i0:i1 + 1]}（已完成 {r.p["done"]}）')
    rc, ran = 0, []
    for st in stages[i0:i1 + 1]:
        if st in r.p['done'] and not from_stage:
            event(f'{st}：進度檔記已完成 → 跳過')
            continue
        event(f'== {st} ==')
        rc = r.do(st)
        if rc:
            break
        ran.append(st)
        if st not in r.p['done']:
            r.p['done'].append(st)
        r.save()
    if not rc and stages[i1] == stages[-1]:
        r.p = {'done': [], 'finished': time.time(), 'orig': r.p.get('orig'), 'battle': r.p.get('battle')}   # 整套做完：清進度（下一轉重做從頭）
        r.save()
    LAST.update(ok=rc == 0, rc=rc, qid=qid, ran=ran, info=r.info)
    event(f'結束 rc={rc}，跑了 {ran}' + (f'；手動：{r.info.get("manual")}' if rc and r.info.get('manual') else ''))
    return rc


def main(argv=None) -> int:
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('cmd', choices=['plan', 'run'])
    ap.add_argument('qid')
    ap.add_argument('--confirm-buy-bait', action='store_true', help='無作用（no-op，舊呼叫端相容）：2026-10-15 起誘餌不夠一律自動用外掛「+」買缺額，不需旗標（讀不到鑽石 / 鑽石有變就停）')
    ap.add_argument('--confirm-drop', action='store_true', help='准丟獎勵寵（布克布克 / 修寶 / 左迪洛斯，只丟 1 級）')
    ap.add_argument('--from', dest='from_stage', default=None)
    ap.add_argument('--to', dest='to_stage', default=None)
    ap.add_argument('--fresh', action='store_true', help='不管進度檔，從頭')
    ap.add_argument('--verify-defer', action='store_true', help='內部 questrun 帶 --verify defer（沒風險事件的逐人驗證延到呼叫端收尾；postrebirth 用）')
    ap.add_argument('--keep-autoswap', action='store_true', help='恐龍博士 train 結束先不關自動轉換戰寵、restore 跳過（後面還有卡坦；postrebirth 傳）')
    ap.add_argument('--dry-run', action='store_true')
    a = ap.parse_args(argv)
    if not ALL_ROLES:
        print(f'petquest：PSA_CLIENT={clients.name()} 沒有登錄角色名單（clients.ROSTERS），不跑', file=sys.stderr)
        return EXIT_ARGS
    if a.cmd == 'run' and not a.dry_run:
        import winenv
        winenv.enable_server()
    rc = run(a.qid, confirm_buy=a.confirm_buy_bait, confirm_drop=a.confirm_drop, from_stage=a.from_stage, to_stage=a.to_stage,
             fresh=a.fresh, dry_run=a.cmd == 'plan' or a.dry_run, verify_defer=a.verify_defer, keep_autoswap=a.keep_autoswap)
    if a.cmd == 'run' and not a.dry_run:
        print(json.dumps(LAST, ensure_ascii=False, default=str))
    return rc


if __name__ == '__main__':
    sys.exit(main())
