#!/usr/bin/env python3
"""寵物任務總控（恐龍博士 2016 / 卡坦的願望 2019 / 猜謎三兄弟 3003）：接取 → 抓 / 分 / 練 → 交 → 丟獎勵寵 → 換回原戰寵。只用標準函式庫。
**只有離線測試（test_petquest.py），整支實機未跑過**；各段呼叫的既有腳本（questrun / pet_catch / pet / petwatch / petdrop / grind / ass）各自有實機紀錄，見 psa-pet-quest SKILL.md。

用法（專案根目錄；WSL / Windows 原生相同）：
  uv run --no-project python tools/gui/petquest.py plan 2016|2019|3003                 # 不碰遊戲：印每段要跑的指令
  uv run --no-project python tools/gui/petquest.py run 2016|2019|3003 [--confirm-buy-bait] [--confirm-drop] [--dry-run] [--from 段] [--to 段] [--fresh]
    --confirm-buy-bait  公共倉庫誘餌不夠時，准用外掛捉寵設置「+」買可抓捕數（每按一次 50,000 石幣；按前 / 按後讀寵物面板頂部石幣，
                        扣款不是剛好 50,000（或鑽石有變）就停手；沒給這個旗標 → 誘餌不夠就 163 停）
    --confirm-drop      准丟獎勵寵（恐龍博士 布克布克、卡坦步 1 修寶、猜謎三兄弟 左迪洛斯；petdrop 驗名 + 只丟 1 級）；沒給 → 到丟寵段 168 停
    --from / --to       只跑某幾段（段名見 plan）；--fresh 不管進度檔從頭（預設：進度檔 tools/.cache/petquest.json 24 小時內記錄過的段直接跳過）
    --dry-run           = plan
    --verify-defer      內部 questrun 帶 --verify defer（postrebirth 傳；沒風險事件的逐人驗證延到 postrebirth 收尾，交寵物仍是風險事件 → 當場驗）
  可 import：petquest.run(qid, tools=…, confirm_buy=…, confirm_drop=…) → 退出碼；結果在 petquest.LAST

流程（各段失敗就停在該段、印手動指令；畫面不認得 9 / 斷線 10 一律透傳；進度檔記完成的段，重跑 = 續跑）：
  恐龍博士 2016 / 卡坦的願望 2019（使用者 2026-10-12 S5 / S6 做法；卡坦步 1 鯊、步 2 雞兩輪）
    accept      questrun.py run <ID> --after none：接取後停在寵物步（115 manual / 155 需先抓寵 / 117 對話 ↔ 選擇循環）；0 = 任務已完成 → 只做收尾
                卡坦接取後讀追蹤步號：已在步 2 → 跳過第 1 輪
    prep        關原地遇敵 + 等戰鬥結束 → 解散隊伍 → pet.py list 記 5 人原戰寵（朵拉比斯，出戰）等級 → 取消鎖定戰寵 → 朵拉比斯 5 人存個人倉庫
                （寵物欄只剩騎寵 + 4 空格；抓寵 / 練寵都不帶原戰寵）
    catch[N]    每輪每批可抓 = 抓寵者寵物欄空格（最少那人；正常 4）：分批抓到 5 隻，滿了會自動進個人倉庫（沒縮圖、成長字串沒登錄就取不出來）→ 所以一批 ≤ 空格數：
                pet_catch.py --stages bait（公共倉庫誘餌取 k 拆 k）→ 有人誘餌不夠（92）且 --confirm-buy-bait → 外掛「+」買 k 次（見上）→
                pet_catch.py --stages setup,wait,rename,register --count k [--reuse-setup：第 2 批起沿用捉寵設置]（wait 第一次輪詢 k×20+20 秒、之後 60 秒）
                名字為主（2026-10-14 晚）：rename = pet.reset_soft 還原抓寵者寵物欄的成長字串名字（鉛筆 → 確認，免費）→ register = 名字驗證：
                比抓寵前快照 catch-pre.json，新多出來的寵物名字 = 該抓寵者 --assign 的物種、隻數 = k → 通過；名字是別的物種 → 15、隻數不對 → 17；
                只有還原失敗 / 名字讀不出的那隻才走舊的成長字串登錄（備援，16 / 17 / 15 照舊）。
                還原讀到費用字樣（pet_catch 67）→ 165 停手（鐵則 3）；9 / 10 透傳；其他還原失敗 → pet_catch 印 RENAME_FAIL_TAG、記 errlog、走備援，
                petquest 記事件、這批 store-many 加 --no-rename（不再試改名卡住）→ 抓寵者把這批存公共（最後一批留 1 隻）
                pet.py store-many --pick last --skip-missing --candidates 本輪物種（名字為主；--candidates 縮圖只在名字讀不出時補）→ pet.py list 驗數量
                中途失敗（2026-10-14 恐龍博士：DKBO3 物種選不到、DKBO2 已勾自動抓寵照抓）：pet_catch 失敗時自己把自動抓寵勾掉；
                續跑（進度檔 catch_started / 抓寵者寵物欄已有任務寵）→ pet.py depot-list 數實際已抓（寵物欄 + 公共 + 抓寵者個人倉庫，recount_plan）→
                個人倉庫溢出的取回、寵物欄的存公共（夠了就留 1 隻）→ 只補剩餘隻數（剩餘相同的抓寵者一組），進度檔 got_<段> = 每人已抓
    distribute[N]  冪等（2026-10-14 恐龍博士：重跑重複取、DKBO5 取不到 72）：先 pet.py list 讀 5 人寵物欄，用嚴格身分（名字 / 登錄成長字串 + 縮圖一致；只有縮圖不算）數每人每物種已持有 →
                多的先 store-many --pick last 存回公共 → pet.py take-many --depot public --plan 只放還缺的（抓寵者自己留的那隻不取；都齊了不取）→ list 驗每人每物種 1 隻
                → 還有名字框是成長字串的任務寵（備援取出的）→ pet.py reset-name --role 那些人（交寵物「選擇」視窗依名字點卡；67 → 165、其他失敗只記事件）
                take-many 中途失敗：訊息帶已取到的；重跑自動只補缺的（卡坦兩輪同樣套用）
    train[N]    自動轉換戰寵 on（轉換級數使用者設 30）→ 第一種任務寵 5 人出戰 → pet_catch.py --verify-battle → grind.py start --spot 波拉島
                （使用者 2026-10-15 指定：恐龍博士 / 卡坦練寵固定 80 級練功區「波拉島」，固定點、不起 follow；舊版柯奧4F龜洞）
                → 每 POLL_S（30）秒讀等級：第一次 pet.py list（身分 + 格位 + 名字框指紋 nh），之後只 pet.py levels --slots <任務寵格>（不認名字），
                  levels 那格變空 / nh 不同 → 改讀完整 list；全部連兩輪 ≥ 門檻（恐龍 魯尼帖斯 18 / 貝魯卡 30；卡坦 25；逐隻累積：某隻連兩次 ≥ 門檻即鎖定、之後不清；不限升級幅度，誤讀 > 門檻+60 忽略；未鎖定者超過門檻+15 → 強制再讀完整 list，全 ≥ 門檻就結束）
                → 關遇敵 → 自動轉換戰寵 off → pet.py rest-all（任務寵改等待；成功記進度檔 rested）
    turnin[N]   questrun.py run <ID> --after none --pet-turnin [--rested]（train 段 30 分內 rest-all 成功才帶：questrun 交件前不重做 rest-all）
                （恐龍：解散逐人 pet_turnin；卡坦：隊長交一次）；卡坦第 1 輪交完讀步號 = 2 才算
    drop[N]     （--confirm-drop）petdrop.py all <獎勵寵> --confirm-name <獎勵寵> --max-level 1（恐龍 布克布克；卡坦第 1 輪 修寶）
    store_reward（卡坦）獎勵朵拉比斯（Lv1）5 人存個人倉庫
    restore     pet.py take-many --depot personal --plan "角色:朵拉比斯@原等級" → 朵拉比斯 5 人出戰 → pet_catch.py --lock 戰寵 --battle-pet 朵拉比斯（讀回）
                → ass.py pet all normal 攻擊 --no-resume（一般動作 = 攻擊、讀回）→ pet.py list 驗 5 人朵拉比斯出戰且等級 = 原等級
  猜謎三兄弟 3003（使用者 2026-10-12 / 10-13 做法）
    accept      questrun.py run 3003 --after none（步 1 manual → 115；步 2 需練寵 → 155；0 = 已完成）
    step1       追蹤步號 = 1 才做：quest.py --task 猜謎三兄弟 --stop-after-rewards 1（10-12 / 10-13 點追蹤自動巡到 810 伊那多拿金豬，沒爬塔）
                → pet.py list 驗 5 人都有金布伊；沒有 → 161（點任務追蹤重試 / 人工處理）
    prep        關遇敵 → pet.py list 記原戰寵（朵拉比斯）等級 → 取消鎖定戰寵 → 金布伊 5 人出戰 → pet_catch.py --lock 戰寵 --battle-pet 金布伊
    train       去練功 grind.py start（不帶 --spot：依等級選點，未滿地雷區背景起 follow；petwatch 在跑時 follow 自動暫停）→ petwatch.py --pet 金布伊 --level 77 --back 朵拉比斯 --exp-fruit（練前 depot_use 吃 2倍智慧果；到 77 自動換回朵拉比斯 + 重鎖）
    turnin      關遇敵 → questrun.py run 3003 --after none（交金豬 → 會員證 → 藍暴）
    drop        （--confirm-drop）petdrop.py all 左迪洛斯 --confirm-name 左迪洛斯 --max-level 1
    restore     pet_catch.py --lock 戰寵 --battle-pet 朵拉比斯 → ass.py pet all normal 攻擊 --no-resume → pet.py list 驗朵拉比斯出戰、等級 ≥ 原等級（練功中可能升級）
  不做：恢復掛機（交給呼叫端 / postrebirth 收尾的 grind.py start）。

退出碼（共用 0 / 1 / 2 / 8 / 9 / 10 見 uikit；petquest 自己 160～169）：
  160 參數錯 / 任務 ID 不支援 / 進度不一致（例：restore 要原等級但進度檔沒有）
  161 接取失敗（questrun 非預期退出碼）/ 猜謎步 1 沒拿到金布伊
  162 準備失敗（關遇敵、解散、讀寵物欄、取消鎖定、存原戰寵、金布伊出戰 / 鎖定）
  163 誘餌不夠且沒給 --confirm-buy-bait / 買可抓捕數失敗（石幣讀不到 / 不夠、「+」按了可抓捕數沒變、扣款不是 50,000、鑽石有變）
  164 抓寵失敗（pet_catch 非 0：14 系別物種選不到、15 新寵物名字 / 縮圖是別的物種、16 名字讀不出（還原失敗、成長字串也讀不出）、17 新寵物隻數不對 / 沒登錄、103 取誘餌 / 設定 / 逾時…）
  165 分配失敗（store-many / take-many 非 0、數量驗不過）/ 還原名字讀到費用字樣（pet_catch / pet 67，鐵則 3）
  166 練寵失敗（自動轉換戰寵、出戰、verify-battle、grind、等級逾時、petwatch、rest-all）
  167 交寵物失敗（questrun 非預期退出碼、卡坦第 1 輪交完步號不是 2）
  168 丟獎勵寵失敗 / 沒給 --confirm-drop
  169 換回原戰寵失敗（存獎勵朵拉比斯、取回、出戰、鎖定、一般動作、讀回驗證）
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
import clients  # noqa: E402
import uikit  # noqa: E402

SRC = 'petquest'
ROOT = uikit.ROOT
import logpaths  # noqa: E402
EVENT_LOG = logpaths.p(clients.npath('quest-events.log'))     # 主視窗 = notes/quest-events.log；其他 = notes/clients/<程序名>/
PROGRESS = logpaths.p(uikit.CACHE / 'petquest.json')

(EXIT_ARGS, EXIT_ACCEPT, EXIT_PREP, EXIT_BAIT, EXIT_CATCH, EXIT_DIST, EXIT_TRAIN, EXIT_TURNIN, EXIT_DROP,
 EXIT_RESTORE) = range(160, 170)
PASS = (uikit.EXIT_UNKNOWN_SCREEN, uikit.EXIT_HALT)                  # 驗證視窗 / 斷線：一律透傳
LEADER = 'DKBO'
ALL_ROLES = ['DKBO', 'DKBO2', 'DKBO3', 'DKBO4', 'DKBO5']
BATTLE_PET = '朵拉比斯'
BAIT_ITEM = 92                     # bag.EXIT_ITEM：誘餌不夠 / 倉庫沒有
PET_FEE = 67                       # pet.EXIT_FEE：還原名字時讀到費用字樣（鐵則 3）
import catchbuy  # noqa: E402  外掛「+」買可抓捕數的共用邏輯（rebirth_pets 同一份）
PLUS_XY, PLUS_COST, MONEY_BOX = catchbuy.PLUS_XY, catchbuy.PLUS_COST, catchbuy.MONEY_BOX      # 紅區：只有 --confirm-buy-bait 才點
POLL_S = 30.0                      # 練寵讀等級間隔（2026-10-13 review 1013b §2.3：只讀等級 pet.py levels，跟 petwatch 一樣 30 秒；舊版 120 秒 + 每次讀 5 人全部身分 91 秒）
TRAIN_MISREAD_UP = 60            # 讀值 > 門檻 + 這麼多視為誤讀忽略；TRAIN_OVER：未鎖定的寵物超過門檻這麼多 → 強制再讀完整 list（防過度練）
TRAIN_OVER = 15
PET_MAX_LEVEL = 140
RESTED_S = 30 * 60                 # train 段 rest-all 成功後這麼久內的 turnin 段帶 --rested（questrun 交件前不重做）
TRAIN_MAX_S = 45 * 60              # 練寵最多等這麼久（S5 約 9 分、S6 約 5 分）
PROGRESS_TRUST_S = 24 * 3600
TRAIN_SPOT = '波拉島'           # 恐龍博士 / 卡坦練寵：使用者 2026-10-15 指定固定在 80 級練功區（spots「波拉島」）
QUIZ_SPOT = None                # 猜謎三兄弟練金布伊：去練功（grind.py start 不帶 --spot，依等級選點 + follow）；不寫死地雷區
LAST: dict = {}

# 每任務的設定（物種 / 門檻 / 抓寵者取自 questdefs.pet_prep 與 psa-pet-quest SKILL.md 具體寵物表）
QUESTS = {
    2016: dict(kind='catch', track='恐龍博士', rounds=[
        dict(assign=[('DKBO2', '呼拔拔系', '魯尼帖斯'), ('DKBO3', '老虎系', '貝魯卡')], need={'魯尼帖斯': 18, '貝魯卡': 30}, drop='布克布克')],
        count=5),
    2019: dict(kind='catch', track='卡坦的願望', rounds=[
        dict(assign=[('DKBO2', '鯊魚系', '克邦凱斯'), ('DKBO3', '鯊魚系', '加克拉'), ('DKBO4', '鯊魚系', '加格'), ('DKBO5', '鯊魚系', '邦恩吉')],
             need={'克邦凱斯': 25, '加克拉': 25, '加格': 25, '邦恩吉': 25}, drop='修寶', step=1),
        dict(assign=[('DKBO2', '火雞系', '火雞'), ('DKBO3', '火雞系', '克克洛斯'), ('DKBO4', '火雞系', '霍爾克'), ('DKBO5', '火雞系', '奇寶')],
             need={'火雞': 25, '克克洛斯': 25, '霍爾克': 25, '奇寶': 25}, drop=None, step=2)],
        count=5, store_reward=BATTLE_PET),
    3003: dict(kind='quiz', track='猜謎三兄弟', pet='金布伊', level=77, drop='左迪洛斯'),
}


def stages_of(qid: int) -> list:
    q = QUESTS[qid]
    if q['kind'] == 'quiz':
        return ['accept', 'step1', 'prep', 'train', 'turnin', 'drop', 'restore']
    out = ['accept', 'prep']
    n = len(q['rounds'])
    for i, rd in enumerate(q['rounds'], 1):
        sfx = str(i) if n > 1 else ''
        out += [f'catch{sfx}', f'distribute{sfx}', f'train{sfx}', f'turnin{sfx}']
        if rd.get('drop'):
            out.append(f'drop{sfx}')
    if q.get('store_reward'):
        out.append('store_reward')
    return out + ['restore']


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


def held_counts(slots, species) -> dict:
    """寵物欄 → {物種: 嚴格身分隻數}（只列 species）"""
    ids = [strict_species(s) for s in slots or []]
    return {sp: sum(1 for i in ids if i == sp) for sp in species}


def distribute_actions(assign, roles_slots: dict, roles=ALL_ROLES) -> tuple:
    """純函式（distribute 冪等）：每人每物種剛好 1 隻 →
    (extras {角色: {物種: 多的隻數}}（要先存回公共）, takes [(角色, 物種)]（還缺的；抓寵者自己那種不取，缺了留給事後驗證報錯）)"""
    catcher = {sp: r for r, _, sp in assign}
    sps = [sp for _, _, sp in assign]
    extras, takes = {}, []
    for r in roles:
        held = held_counts((roles_slots or {}).get(r), sps)
        for sp in sps:
            if held[sp] > 1:
                extras.setdefault(r, {})[sp] = held[sp] - 1
            elif held[sp] == 0 and catcher[sp] != r:
                takes.append((r, sp))
    return extras, takes


RENAME_FAIL_TAG = '還原名字沒全部成功'          # pet_catch.RENAME_FAIL_TAG（rename 階段一般失敗時印；不 import pet_catch 以免子程序外多載模組）


def rename_failed(lines) -> bool:
    """pet_catch 輸出有 RENAME_FAIL_TAG → 這批還原名字沒全部成功（已走成長字串登錄備援）"""
    return any(RENAME_FAIL_TAG in str(ln) for ln in lines or [])


def unnamed_roles(roles_slots: dict, species) -> list:
    """寵物欄還有名字框是成長字串（沒名字、身分靠登錄檔 / 縮圖）的任務寵的角色（照 ALL_ROLES 順序）"""
    sps = set(species)
    return [r for r in ALL_ROLES if any(not s.get('empty') and not s.get('name') and (s.get('unnamed') or s.get('guess'))
                                        and slot_species(s) in sps for s in (roles_slots or {}).get(r) or [])]


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


def recount_plan(assign, roles_slots: dict, public: dict, personal: dict, count: int) -> dict:
    """純函式（抓寵續跑）：每個抓寵者實際已抓 = 寵物欄任務寵 + 公共倉庫該物種 + 從個人倉庫取得回來的（自動存倉庫溢出）→
    {角色: {'sp', 'slots', 'public', 'personal', 'take_personal', 'store', 'take_public', 'got'}}。
    整理目標：還要抓（got < count）→ 寵物欄的全存公共（下一批從 0 開始、最後一批留 1）；已夠 → 寵物欄剛好留 1 隻（多的存公共、沒有就從公共取 1）。
    假設每個物種只有一個抓寵者（恐龍 / 卡坦都是）；公共倉庫裡原本就有的同物種也算（Lv1 任務寵，分配時一樣能用）"""
    out = {}
    for r, _, sp in assign:
        slots = (roles_slots or {}).get(r) or []
        n_s, n_pub, n_per = count_species(slots, sp), int((public or {}).get(sp, 0)), int(((personal or {}).get(r) or {}).get(sp, 0))
        tp = min(n_per, free_slots(slots))
        n2 = n_s + tp
        got = n2 + n_pub
        if got < count:
            store, take = n2, 0
        else:
            store, take = max(0, n2 - 1), (1 if n2 == 0 else 0)
        out[r] = dict(sp=sp, slots=n_s, public=n_pub, personal=n_per, take_personal=tp, store=store, take_public=take, got=got)
    return out


def batches(count: int, free: int) -> list:
    """純函式：每人要抓 count 隻、寵物欄空格 free → 每批隻數（每批 ≤ free；寵物欄滿了會自動進個人倉庫、沒縮圖取不出來）"""
    if count <= 0 or free <= 0:
        return []
    out, left = [], count
    while left > 0:
        k = min(free, left)
        out.append(k)
        left -= k
    return out


def store_after_batch(k: int, last: bool) -> int:
    """這批抓完抓寵者要存公共幾隻：最後一批留 1 隻自己用，其他批全存（空出寵物欄給下一批）"""
    return max(0, k - 1) if last else k


def take_plan(assign, roles=ALL_ROLES) -> list:
    """每人每物種要 1 隻；抓寵者自己留的那隻不取 → [(角色, 物種)]"""
    catcher = {sp: r for r, _, sp in assign}
    return [(r, sp) for r in roles for _, _, sp in assign if catcher[sp] != r]


def missing_pets(roles_slots: dict, species, roles=ALL_ROLES) -> dict:
    """每人每物種應剛好 1 隻 → {角色: {物種: 實際隻數}}（不對的才列）"""
    out = {}
    for r in roles:
        slots = (roles_slots or {}).get(r) or []
        bad = {sp: count_species(slots, sp) for sp in species if count_species(slots, sp) != 1}
        if bad:
            out[r] = bad
    return out


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


def task_levels(roles_slots: dict, need: dict, roles=ALL_ROLES) -> dict:
    """{角色: [格]} → {(角色, 物種): 等級或 None}（每人每個任務物種取最高；沒有該物種 = None）"""
    out = {}
    for r in roles:
        slots = (roles_slots or {}).get(r) or []
        for sp in need:
            hits = [s.get('level') for s in slots if slot_species(s) == sp]
            out[(r, sp)] = max((v for v in hits if v is not None), default=None)
    return out


class TrainConfirm:
    """練寵達標確認（逐隻累積，鎖定後不清）。鍵 = (角色, 物種)。
    某隻連兩次讀值都 ≥ 門檻 → 鎖定為達標，之後讀不到 / 點陣不同 / 改讀 list 都不清掉；全部鎖定即結束。
    讀值 > 門檻 + TRAIN_MISREAD_UP 或 > 140 視為誤讀，忽略（不計入連續次數、不清既有進度）；讀到 < 門檻 → 連續次數歸零；讀不到（None）→ 不動。
    不再限制兩次之間的升級幅度（高速練功一輪升 >10 級正常）。
    over = 有未鎖定的寵物已超過門檻 + TRAIN_OVER（過度練的安全上限）→ 呼叫端應立刻再讀一次完整 list"""

    def __init__(self, need: dict):
        self.need = need
        self.locked, self.streak = set(), {}

    def update(self, cur: dict) -> tuple:
        """本輪讀值 {(角色, 物種): 等級或 None} → (本輪新鎖定的鍵, 第一次讀到達標等下一次確認的鍵)"""
        new, pending = [], []
        for k, v in cur.items():
            lv = self.need.get(k[1])
            if k in self.locked or v is None or lv is None:
                continue
            if v > lv + TRAIN_MISREAD_UP or v > PET_MAX_LEVEL:
                continue
            if v < lv:
                self.streak.pop(k, None)
                continue
            if self.streak.get(k):
                self.locked.add(k)
                new.append(k)
            else:
                self.streak[k] = True
                pending.append(k)
        return new, pending

    def done(self, keys) -> bool:
        keys = list(keys)
        return bool(keys) and all(k in self.locked for k in keys)

    def over(self, cur: dict) -> bool:
        return any(k not in self.locked and v is not None and self.need.get(k[1]) is not None
                   and self.need[k[1]] + TRAIN_OVER < v <= PET_MAX_LEVEL for k, v in cur.items())


def merge_levels(base: dict, lv: dict, need: dict) -> tuple:
    """上一次完整 list 的格（身分）+ pet.py levels 只讀的等級 → (合併後 {角色: [格]}, None) 或 (None, 原因)。
    任務寵那格在 levels 裡變空 / 沒讀到 / 名字框點陣指紋 nh 跟上次不同（換了隻、或被浮字蓋住）→ 不合併，呼叫端改讀完整 list"""
    out = {}
    for r, slots in (base or {}).items():
        got = {x.get('slot'): x for x in (lv or {}).get(r) or []}
        row = []
        for s in slots or []:
            if slot_species(s) in need:
                x = got.get(s.get('slot'))
                if not x or x.get('empty'):
                    return None, f'{r} 第 {s.get("slot")} 格（{slot_species(s)}）levels 讀不到 / 變空格'
                if s.get('nh') and x.get('nh') != s['nh']:
                    return None, f'{r} 第 {s.get("slot")} 格名字框點陣跟上次不同（換了隻 / 被浮字蓋住）'
                s = dict(s, level=x.get('level'))
            row.append(s)
        out[r] = row
    return out, None


def task_slots(roles_slots: dict, need: dict) -> list:
    """任務寵所在的格號（各角色聯集，1 起算）→ pet.py levels --slots"""
    return sorted({s.get('slot') for slots in (roles_slots or {}).values() for s in slots or [] if slot_species(s) in need and s.get('slot')})


parse_money = catchbuy.parse_money


def bait_ok_roles(lines) -> set:
    """pet_catch --stages bait 的輸出 →「背包誘餌 = N」成功的角色"""
    out = set()
    for ln in lines or []:
        m = re.search(r'(DKB[O0]\d?)\s*背包誘餌\s*=\s*\d+', str(ln))
        if m:
            out.add(m.group(1).replace('DKB0', 'DKBO'))
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

    def save_catch_pre(self, rs) -> None:
        """抓寵前寵物欄快照給 pet_catch register 用（排除騎寵 / 抓寵前就在的寵物）"""
        import pet_catch
        pet_catch.save_pre(rs)

    def money(self) -> tuple:
        """寵物面板頂部資源列 → (石幣, 鑽石)；面板打不開 / 讀不到 → (None, None)"""
        return catchbuy.money()

    def press_plus(self, role) -> tuple:
        """外掛「+」按一次（紅區：只有 petquest --confirm-buy-bait 的 buy_plus 會呼叫）→ (rc, 按前, 按後)"""
        return catchbuy.press_plus(role)


# ---------------------------------------------------------------- 驅動
class Run:
    def __init__(self, qid: int, T, o: dict):
        self.qid, self.T, self.o = qid, T, o
        self.q = QUESTS[qid]
        allp = load_progress()
        p = allp.get(str(qid)) or {}
        if o.get('fresh') or time.time() - (p.get('ts') or 0) > PROGRESS_TRUST_S:
            p = {}
        self.all, self.p = allp, p
        self.p.setdefault('done', [])
        self.info: dict = {}

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
        rc, _ = self.sub('questrun.py', ['run', self.qid, '--after', 'none'] + self.verify_args(), 4 * 3600)
        if rc == 0:
            event(f'任務 {self.qid}：questrun 回 0 = 任務已完成 → 跳過抓 / 練 / 交，只做收尾')
            self.p['already_done'] = True
            return 0
        if rc in (115, 155, 117):
            if self.q['kind'] == 'catch' and len(self.q['rounds']) > 1:
                st = self.T.read_step(self.q['track'])
                self.p['step'] = st
                if st == 2:                                            # 卡坦步 1 已交：第 1 輪全部跳過
                    event(f'任務 {self.qid}：追蹤步號 = 2 → 第 1 輪（{self.q["rounds"][0]["assign"][0][2]} 等）已交，跳過')
                    for s in stages_of(self.qid):
                        if s.endswith('1') and s not in self.p['done']:
                            self.p['done'].append(s)
            if self.q['kind'] == 'quiz':
                self.p['step'] = self.T.read_step(self.q['track'])
            return 0
        return self.pass_or(rc, EXIT_ACCEPT, f'接取：questrun 退出碼 {rc}（預期 0 / 115 / 155 / 117）',
                            f'uv run --no-project python tools/gui/questrun.py run {self.qid} --after none')

    def record_orig(self) -> int:
        rc, rs = self.pet_list()
        if rc:
            return self.pass_or(rc, EXIT_PREP, f'讀寵物欄失敗 pet rc={rc}', 'uv run --no-project python tools/gui/pet.py list --role all')
        lv = battle_levels(rs)
        miss = [r for r in ALL_ROLES if not lv.get(r)]
        if miss:
            return self.fail(EXIT_PREP, f'{miss} 寵物欄找不到{BATTLE_PET}或等級讀不到（換回時要用 --expect-level 原等級）：{lv}',
                             'uv run --no-project python tools/gui/pet.py list --role all（看清楚後手動記下等級）')
        self.p['orig'] = lv
        event(f'原戰寵 {BATTLE_PET} 等級：{lv}')
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

    def s_prep(self) -> int:
        if self.p.get('already_done'):
            return 0
        rc = self.encounter_off()
        if rc:
            return rc
        if self.q['kind'] == 'catch':
            rc = self.solo(EXIT_PREP)
            if rc:
                return rc
        if not self.p.get('orig'):
            rc = self.record_orig()
            if rc:
                return rc
        rc, _ = self.sub('pet_catch.py', ['--unlock', '戰寵'], 900)
        if rc:
            return self.pass_or(rc, EXIT_PREP, f'取消鎖定戰寵失敗 rc={rc}', 'uv run --no-project python tools/gui/pet_catch.py --unlock 戰寵')
        if self.q['kind'] == 'quiz':
            pet = self.q['pet']
            rc, _ = self.sub('pet.py', ['set-state-many', '--role', 'all', pet, '出戰'], 900)
            if rc:
                return self.pass_or(rc, EXIT_PREP, f'{pet} 5 人出戰失敗 pet rc={rc}', f'uv run --no-project python tools/gui/pet.py set-state-many --role all {pet} 出戰')
            rc, _ = self.sub('pet_catch.py', ['--lock', '戰寵', '--battle-pet', pet], 900)
            if rc:
                return self.pass_or(rc, EXIT_PREP, f'鎖定戰寵 = {pet} 失敗 rc={rc}', f'uv run --no-project python tools/gui/pet_catch.py --lock 戰寵 --battle-pet {pet}')
            return 0
        rc, _ = self.sub('pet.py', ['store-many', '--role', 'all', '--pets', BATTLE_PET, '--depot', 'personal', '--skip-missing'], 1200)   # 續跑時已存過的人略過
        if rc:
            return self.pass_or(rc, EXIT_PREP, f'{BATTLE_PET} 存個人倉庫失敗 pet rc={rc}（寵物欄要空出 4 格）',
                                f'uv run --no-project python tools/gui/pet.py store-many --role all --pets {BATTLE_PET} --depot personal')
        return 0

    def round_conf(self, stage) -> dict:
        return self.q['rounds'][stage_round(stage) - 1]

    def buy_plus(self, role, n) -> int:
        """外掛「+」買 n 個可抓捕數（catchbuy.buy：每按一次前後讀石幣，要剛好少 PLUS_COST、鑽石不變，否則停）"""
        kind, msg, rc, bought = catchbuy.buy(role, n, self.T.money, self.T.press_plus, event)
        self.info.setdefault('bought', []).extend(bought)
        if kind == 'ok':
            return 0
        return self.pass_or(rc, EXIT_BAIT, msg) if kind == 'pass' else self.fail(EXIT_BAIT, msg)

    def s_catch(self, stage) -> int:
        """每人要 count 隻：進度檔 got_<段> = 每人已抓（並存好）幾隻。中途失敗續跑時（catch_started 標記，或抓寵者寵物欄已有任務寵）
        先數實際數量（寵物欄 + 公共倉庫 + 抓寵者個人倉庫，pet.py depot-list），整理成「寵物欄 0 隻、其餘在公共」再照剩餘隻數分組補抓（不重抓）"""
        if self.p.get('already_done'):
            return 0
        rd, count = self.round_conf(stage), self.q.get('count', 5)
        assign, cand = rd['assign'], species_csv(rd['assign'])
        catchers = [r for r, _, _ in assign]
        gkey, skey = f'got_{stage}', f'catch_started_{stage}'
        old = self.p.get(f'caught_{stage}', 0)                        # 舊版進度檔：每人同一個數
        got = dict(self.p.get(gkey) or {r: old for r in catchers})
        if all(got.get(r, 0) >= count for r in catchers):
            return 0
        rc = self.solo(EXIT_CATCH)                                     # 抓寵前一定關遇敵 + 解散（卡坦第 2 輪前 questrun 交完是組隊狀態）
        if rc:
            return rc
        rc, rs = self.pet_list(catchers, cand)                         # 每批 ≤ 抓寵者寵物欄空格（最少的那人；例：獎勵寵沒丟 → 3 格）
        if rc:
            return self.pass_or(rc, EXIT_CATCH, f'抓前讀寵物欄失敗 pet rc={rc}')
        if self.p.get(skey) or any(count_species(rs.get(r), sp) for r, _, sp in assign):
            rc, got = self.recount(stage, assign, rs, cand, count)
            if rc:
                return rc
            self.p[gkey] = got
            self.save()
            if all(got[r] >= count for r in catchers):
                event(f'{stage}：實際數量已夠 {got} → 不再抓')
                return 0
            rc, rs = self.pet_list(catchers, cand)
            if rc:
                return self.pass_or(rc, EXIT_CATCH, f'整理後讀寵物欄失敗 pet rc={rc}')
        self.p[skey] = True
        self.save()
        groups: dict = {}
        for r, f, sp in assign:                                         # 剩餘隻數相同的抓寵者一起抓（pet_catch --count 每人同一個數）
            if count - got.get(r, 0) > 0:
                groups.setdefault(count - got.get(r, 0), []).append((r, f, sp))
        for need, sub in sorted(groups.items(), reverse=True):
            rc, rs = self.catch_batches(stage, sub, need, rs, cand, got)
            if rc:
                return rc
        return 0

    def recount(self, stage, assign, rs, cand, count) -> tuple:
        """續跑：數各抓寵者實際已抓（寵物欄 + 公共倉庫 + 個人倉庫）→ 整理（個人倉庫的取回、寵物欄的存公共 / 夠了留 1 隻）→ (rc, {角色: 已抓})"""
        catchers = ','.join(r for r, _, _ in assign)
        rc, lines = self.sub('pet.py', ['depot-list', '--depot', 'public,personal', '--role', catchers, '--candidates', cand], 1800)
        if rc:
            return self.pass_or(rc, EXIT_CATCH, f'續跑數倉庫失敗 pet depot-list rc={rc}', f'uv run --no-project python tools/gui/pet.py depot-list --depot public,personal --role {catchers} --candidates {cand}'), None
        c = last_json(lines).get('counts') or {}
        plan = recount_plan(assign, rs, c.get('public') or {}, c.get('personal') or {}, count)
        unk = (c.get('public') or {}).get('null') or (c.get('public') or {}).get(None)
        event(f'{stage}：續跑實際數量 ' + '、'.join(f'{r} {v["sp"]} 欄 {v["slots"]} 公共 {v["public"]} 個人 {v["personal"]}' for r, v in plan.items())
              + (f'；公共倉庫有 {unk} 張認不出物種' if unk else ''))
        for r, v in plan.items():
            steps = [(['take-many', '--depot', 'personal', '--plan', ','.join([f'{r}:{v["sp"]}'] * v['take_personal'])], v['take_personal']),
                     (['store-many', '--role', r, '--pets', ','.join([v['sp']] * v['store']), '--depot', 'public', '--pick', 'last'], v['store']),
                     (['take-many', '--depot', 'public', '--plan', f'{r}:{v["sp"]}'], v['take_public'])]
            for args, n in steps:
                if not n:
                    continue
                rc, _ = self.sub('pet.py', args + ['--candidates', cand], 1800)
                if rc:
                    return self.pass_or(rc, EXIT_DIST, f'續跑整理寵物失敗 pet {args[0]} rc={rc}', 'uv run --no-project python tools/gui/pet.py ' + ' '.join(args + ['--candidates', cand])), None
        return 0, {r: v['got'] for r, v in plan.items()}

    def catch_batches(self, stage, assign, need, rs, cand, got) -> tuple:
        """這組抓寵者（剩餘隻數都是 need、寵物欄沒有任務寵）分批抓：每批 ≤ 寵物欄空格，最後一批留 1 隻、其餘存公共。→ (rc, 最新寵物欄)"""
        free = min(free_slots(rs.get(r)) for r, _, _ in assign)
        plan = batches(need, free)
        if not plan:
            return self.fail(EXIT_CATCH, f'抓寵者寵物欄沒有空格（{ {r: free_slots(rs.get(r)) for r, _, _ in assign} }）→ 先存 / 丟寵物', 'uv run --no-project python tools/gui/pet.py list --role all'), rs
        event(f'{stage}：{[r for r, _, _ in assign]} 還要 {need} 隻，寵物欄空格 {free} → 分批 {plan}')
        for bi, k in enumerate(plan):
            last = bi == len(plan) - 1
            rc, lines = self.sub('pet_catch.py', ['--assign', csv_assign(assign), '--count', k, '--stages', 'bait'], 1800)
            if rc and rc != BAIT_ITEM:
                return self.pass_or(rc, EXIT_CATCH, f'取誘餌失敗 pet_catch rc={rc}', f'uv run --no-project python tools/gui/pet_catch.py --assign "{csv_assign(assign)}" --count {k} --stages bait'), rs
            if rc == BAIT_ITEM:
                short = [r for r, _, _ in assign if r not in bait_ok_roles(lines)]
                if not self.o.get('confirm_buy'):
                    return self.fail(EXIT_BAIT, f'公共倉庫誘餌不夠：{short} 各缺 {k} 個（每個可抓捕數用「+」買要 {PLUS_COST} 石幣）→ 沒給 --confirm-buy-bait，停手',
                                     f'確認要買就重跑加 --confirm-buy-bait（或手動補誘餌到公共倉庫後重跑）'), rs
                for r in short:
                    rc = self.buy_plus(r, k)
                    if rc:
                        return rc, rs
            self.save_pre(rs)                                           # 抓寵前寵物欄快照（pet_catch register 排除騎寵 / 舊寵物，不必再讀一次）
            reuse = ['--reuse-setup'] if bi > 0 else []                 # 第 2 批起沿用第 1 批的捉寵設置（讀回驗證照舊，review 1013b §2.5-A）
            # 2026-10-14 名字為主：setup,wait → rename（reset-name 抓寵者：成長字串還原成物種名）→ register（名字驗證；名字讀不出的才登錄成長字串）
            rc, lines = self.sub('pet_catch.py', ['--assign', csv_assign(assign), '--count', k, '--stages', 'setup,wait,rename,register'] + reuse, 3600)
            if rc == PET_FEE:                                           # 還原名字讀到費用字樣（已按取消）→ 停手（鐵則 3）
                return self.fail(EXIT_DIST, f'抓完還原名字時讀到費用字樣（pet_catch rc={rc}）→ 已按取消、停手（鐵則 3）',
                                 '看 tools/.cache/ui-log/*pet-rename* 截圖，確認改名是否收費'), rs
            if rc:                                                      # pet_catch 失敗時自己會取消自動抓寵（9 / 10 除外）；續跑會先數實際數量
                return self.pass_or(rc, EXIT_CATCH, f'抓寵失敗 pet_catch rc={rc}（14 系別 / 物種選不到、15 新寵物名字 / 縮圖是別的物種、16 名字讀不出（還原失敗、成長字串也讀不出）、'
                                    f'17 新寵物數量不對 / 沒登錄、103 設定 / 逾時）；已取消自動抓寵，重跑會先數實際已抓（含倉庫）再補',
                                    f'uv run --no-project python tools/gui/petquest.py run {self.qid} --from {stage}（或 pet_catch.py --catch-off 後手動）'), rs
            soft = rename_failed(lines)                                 # 還原名字一般失敗（pet_catch 已走成長字串登錄備援）→ 這批存公共不再試改名
            if soft:
                event(f'{stage}：第 {bi + 1} 批還原名字沒全部成功 → 存公共加 --no-rename（名字讀不出的靠成長字串登錄 + 縮圖備援）')
            n_store = store_after_batch(k, last)
            if n_store:
                pets = ','.join(sp for _, _, sp in assign for _ in range(n_store))
                catchers = ','.join(r for r, _, _ in assign)
                rc, _ = self.sub('pet.py', ['store-many', '--role', catchers, '--pets', pets, '--depot', 'public', '--pick', 'last', '--skip-missing',
                                            '--candidates', cand] + (['--no-rename'] if soft else []), 1800)
                if rc:
                    return self.pass_or(rc, EXIT_DIST, f'抓寵者存公共倉庫失敗 pet rc={rc}', f'uv run --no-project python tools/gui/pet.py store-many --role {catchers} --pets {pets} --depot public --pick last --skip-missing --candidates {cand}'), rs
            rc, rs = self.pet_list([r for r, _, _ in assign], cand)
            if rc:
                return self.pass_or(rc, EXIT_CATCH, f'抓完讀寵物欄失敗 pet rc={rc}'), rs
            keep = 1 if last else 0
            bad = {r: count_species(rs.get(r), sp) for r, _, sp in assign if count_species(rs.get(r), sp) != keep}
            if bad:
                return self.fail(EXIT_DIST, f'第 {bi + 1} 批後抓寵者寵物欄隻數不對（應各 {keep}）：{bad}（沒存完 / 多抓 / 有寵物進了個人倉庫？）',
                                 f'uv run --no-project python tools/gui/pet.py list --role all；重跑 petquest.py run {self.qid} --from {"catch" if stage == "catch" else stage} 會先數實際數量'), rs
            for r, _, _ in assign:
                got[r] = got.get(r, 0) + k
            self.p[f'got_{stage}'] = got
            self.p[f'caught_{stage}'] = min(got.values())
            self.save()
            event(f'{stage}：第 {bi + 1}/{len(plan)} 批抓 {k} 隻完成（累計 {got}）')
        return 0, rs

    def reset_names(self, roles) -> int:
        """pet.py reset-name --role <角色>（distribute 後補還原：寵物欄還有名字框是成長字串的任務寵 → 交寵物「選擇」視窗要靠名字點卡）。
        費用字樣（pet 67）→ 停手（鐵則 3）；驗證視窗 / 斷線透傳；其他失敗只記事件、照常往下（名字讀不出的靠登錄檔 + 縮圖備援）"""
        rc, _ = self.sub('pet.py', ['reset-name', '--role', ','.join(roles)], 900)
        if rc in PASS:
            return rc
        if rc == PET_FEE:
            return self.fail(EXIT_DIST, f'還原名字時讀到費用字樣（pet rc={rc}）→ 已按取消、停手（鐵則 3）', '看 tools/.cache/ui-log/*pet-rename* 截圖，確認改名是否收費')
        if rc:
            event(f'還原名字失敗 pet rc={rc}（{",".join(roles)}）→ 照常往下（存倉前會再試、成長字串登錄檔備援）')
        return 0

    def save_pre(self, rs) -> None:
        fn = getattr(self.T, 'save_catch_pre', None)
        if fn:
            try:
                fn(rs)
            except OSError as e:
                event(f'抓寵前快照存檔失敗：{e}（pet_catch 會自己再讀一次）')

    def s_distribute(self, stage) -> int:
        if self.p.get('already_done'):
            return 0
        assign = self.round_conf(stage)['assign']
        cand = species_csv(assign)
        rc, rs = self.pet_list(ALL_ROLES, cand)                  # 冪等：先讀 5 人寵物欄，已持有的不重取、多的先存回公共
        if rc:
            return self.pass_or(rc, EXIT_DIST, f'分配前讀寵物欄失敗 pet rc={rc}')
        extras, takes = distribute_actions(assign, rs)
        for r, d in extras.items():
            pets = ','.join(sp for sp, n in d.items() for _ in range(n))
            event(f'{stage}：{r} 持有多餘任務寵 {d} → 存回公共倉庫')
            rc, _ = self.sub('pet.py', ['store-many', '--role', r, '--pets', pets, '--depot', 'public', '--pick', 'last', '--candidates', cand], 1800)
            if rc:
                return self.pass_or(rc, EXIT_DIST, f'多取的任務寵存回公共失敗 pet rc={rc}',
                                    f'uv run --no-project python tools/gui/pet.py store-many --role {r} --pets {pets} --depot public --pick last --candidates {cand}')
        if not takes:
            event(f'{stage}：5 人都已持有各物種 → 不取')
        else:
            plan = ','.join(f'{r}:{sp}' for r, sp in takes)
            event(f'{stage}：還缺 {len(takes)} 隻 → take-many {plan}')
            rc, lines = self.sub('pet.py', ['take-many', '--depot', 'public', '--plan', plan, '--candidates', cand], 3600)
            if rc:
                done = [f'{o.get("role")}:{o.get("pet") or o.get("target") or o.get("name")}' for o in (last_json(lines).get('ops') or []) if isinstance(o, dict) and o.get('ok')]
                return self.pass_or(rc, EXIT_DIST, f'公共倉庫分配 take-many 失敗 pet rc={rc}' + (f'（已取到 {done}）' if done else '') + '；重跑會先讀寵物欄只補缺的',
                                    f'重跑 uv run --no-project python tools/gui/petquest.py run {self.qid} --from {stage}（自動只補缺的）')
        rc, rs = self.pet_list(ALL_ROLES, cand)
        if rc:
            return self.pass_or(rc, EXIT_DIST, f'分配後讀寵物欄失敗 pet rc={rc}')
        miss = missing_pets(rs, [sp for _, _, sp in assign])
        if miss:
            return self.fail(EXIT_DIST, f'分配後每人每物種不是剛好 1 隻：{miss}', 'uv run --no-project python tools/gui/pet.py list --role all --candidates ' + cand)
        un = unnamed_roles(rs, [sp for _, _, sp in assign])
        if un:                                                          # 備援取出的成長字串寵物 → 交寵物前還原名字（pet_turnin 選擇視窗依名字點卡）
            event(f'{stage}：{un} 還有名字框是成長字串的任務寵 → reset-name')
            rc = self.reset_names(un)
            if rc:
                return rc
        return 0

    def s_train(self, stage) -> int:
        if self.p.get('already_done'):
            return 0
        if self.q['kind'] == 'quiz':
            return self.train_quiz()
        rd = self.round_conf(stage)
        cand = species_csv(rd['assign'])
        first = rd['assign'][0][2]
        for script, args, why in (('pet_catch.py', ['--autoswap', 'on'], '自動轉換戰寵 on'),
                                  ('pet.py', ['set-state-many', '--role', 'all', first, '出戰', '--candidates', cand], f'{first} 5 人出戰'),
                                  ('pet_catch.py', ['--verify-battle'], '5 人都有出戰寵'),
                                  ('grind.py', ['start', '--spot', TRAIN_SPOT], f'grind start {TRAIN_SPOT}')):
            rc, _ = self.sub(script, args, 1800)
            if rc:
                return self.pass_or(rc, EXIT_TRAIN, f'練寵準備：{why} 失敗 rc={rc}', f'uv run --no-project python tools/gui/{script} {" ".join(map(str, args))}')
        t0 = self.T.clock()
        need = rd['need']
        tc = TrainConfirm(need)
        base = None                                          # base = 最近一次完整 list（身分 + 格位 + nh）；之後只讀等級
        while True:
            self.T.sleep(POLL_S)
            if base is None:
                rc, rs = self.pet_list(ALL_ROLES, cand)
                if not rc:
                    base = rs
            else:
                rc, lv = self.pet_levels(task_slots(base, need))
                rs, why = merge_levels(base, lv, need) if not rc else (None, None)
                if why:
                    event(f'{stage}：{why} → 改讀完整 list')
                    rc, rs = self.pet_list(ALL_ROLES, cand)
                    base = rs if not rc else None
            if rc in PASS:
                return rc
            if rc:
                cur, lag = {}, {'讀取失敗': rc}
                base = None
            else:
                cur = task_levels(rs, need)
                lag = {f'{r}:{sp}': v for (r, sp), v in cur.items() if v is None or v < need[sp]}
            new, pending = tc.update(cur)
            if not rc and not tc.done(cur) and tc.over(cur):
                big = {f'{r}:{sp}': v for (r, sp), v in cur.items() if v is not None and v > need[sp] + TRAIN_OVER}
                event(f'{stage}：已有寵物超過門檻 +{TRAIN_OVER}（{big}）→ 強制再讀完整 list 確認')
                rc2, rs2 = self.pet_list(ALL_ROLES, cand)
                if rc2 in PASS:
                    return rc2
                if not rc2:
                    base = rs2
                    cur = task_levels(rs2, need)
                    lag = {f'{r}:{sp}': v for (r, sp), v in cur.items() if v is None or v < need[sp]}
                    tc.update(cur)
                    if cur and all(v is not None and v >= need[k[1]] for k, v in cur.items()):
                        tc.locked.update(cur)               # 安全上限：完整 list 全部 ≥ 門檻 → 直接結束，不再等第二次
            ok = tc.done(cur)
            event(f'{stage}：5 人任務寵全部達標（逐隻連兩次確認）' if ok else
                  f'{stage}：練寵進度 未達標 {lag}' + (f'；第一次讀到達標、待確認 {len(pending)} 隻' if pending else '') + f'（已鎖定 {len(tc.locked)}）')
            if ok:
                break
            if self.T.clock() - t0 > TRAIN_MAX_S:
                return self.fail(EXIT_TRAIN, f'練寵 {TRAIN_MAX_S // 60} 分鐘仍未達標：{lag}', '看 pet.py list；沒出戰寵就 set-state 出戰，達標後 --from turnin 續跑')
        rc = self.encounter_off()
        if rc:
            return rc
        for script, args, why in (('pet_catch.py', ['--autoswap', 'off'], '自動轉換戰寵 off'),
                                  ('pet.py', ['rest-all', '--candidates', cand], '任務寵改等待（rest-all）')):
            rc, _ = self.sub(script, args, 1800)
            if rc:
                return self.pass_or(rc, EXIT_TRAIN, f'練完：{why} 失敗 rc={rc}', f'uv run --no-project python tools/gui/{script} {" ".join(map(str, args))}')
        self.p['rested'] = {'stage': stage.replace('train', 'turnin'), 'ts': self.T.clock()}   # 交件段帶 --rested（questrun 不重做 rest-all）
        self.save()
        return 0

    def train_quiz(self) -> int:
        q = self.q
        gargs = ['start'] + (['--spot', QUIZ_SPOT] if QUIZ_SPOT else [])
        rc, _ = self.sub('grind.py', gargs, 1800)
        if rc:
            return self.pass_or(rc, EXIT_TRAIN, f'grind {" ".join(gargs)}（去練功）失敗 rc={rc}', f'uv run --no-project python tools/gui/grind.py {" ".join(gargs)}')
        args = ['--pet', q['pet'], '--level', q['level'], '--back', BATTLE_PET, '--exp-fruit']
        rc, _ = self.sub('petwatch.py', args, 4 * 3600)
        if rc:
            return self.pass_or(rc, EXIT_TRAIN, f'petwatch 失敗 rc={rc}（4 = 有人換回失敗被放棄）',
                                f'uv run --no-project python tools/gui/petwatch.py {" ".join(map(str, args))}；放棄的人：pet_catch.py --unlock 戰寵 --roles X → pet.py set-state X {BATTLE_PET} 出戰 → pet_catch.py --lock 戰寵 --roles X --battle-pet {BATTLE_PET}')
        return 0

    def s_step1(self) -> int:
        if self.p.get('already_done'):
            return 0
        if self.p.get('step') not in (1, None):
            event(f'猜謎三兄弟：追蹤步號 {self.p.get("step")} ≠ 1 → 步 1 已過，跳過')
            return 0
        pet = self.q['pet']
        rc, _ = self.sub('quest.py', ['--task', self.q['track'], '--stop-after-rewards', 1, '--max-seconds', 900], 2400)
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
        if self.q['kind'] == 'catch' and not self.p.get('already_done'):
            if [r for r in ALL_ROLES if not orig.get(r)]:
                return self.fail(EXIT_ARGS, f'進度檔沒有 5 人原{BATTLE_PET}等級 {orig} → 不盲取（同名多隻）', '手動 pet.py take-many --depot personal --plan "DKBO:朵拉比斯@等級,…"')
            rc0, rs0 = self.pet_list()                                    # 續跑：已有原等級的戰寵在寵物欄的人不再取（take-many 對同名多隻會取到別隻，2026-10-14 恐龍博士手動取回後續跑）
            have = {r for r in ALL_ROLES if rc0 == 0 and any(slot_species(s) == BATTLE_PET and s.get('level') == orig[r] for s in rs0.get(r) or [])}
            todo = [r for r in ALL_ROLES if r not in have]
            plan = ','.join(f'{r}:{BATTLE_PET}@{orig[r]}' for r in todo)
            if todo:
                rc, _ = self.sub('pet.py', ['take-many', '--depot', 'personal', '--plan', plan], 1800)
                if rc:
                    return self.pass_or(rc, EXIT_RESTORE, f'取回原{BATTLE_PET}失敗 pet rc={rc}', f'uv run --no-project python tools/gui/pet.py take-many --depot personal --plan "{plan}"')
            rc, _ = self.sub('pet.py', ['set-state-many', '--role', 'all', BATTLE_PET, '出戰'], 900)
            if rc:
                return self.pass_or(rc, EXIT_RESTORE, f'{BATTLE_PET} 出戰失敗 pet rc={rc}', f'uv run --no-project python tools/gui/pet.py set-state-many --role all {BATTLE_PET} 出戰')
        for script, args, why in (('pet_catch.py', ['--lock', '戰寵', '--battle-pet', BATTLE_PET], f'鎖定戰寵 = {BATTLE_PET}'),
                                  ('ass.py', ['pet', 'all', 'normal', '攻擊', '--no-resume'], '戰寵一般動作 = 攻擊')):
            rc, _ = self.sub(script, args, 1200)
            if rc:
                return self.pass_or(rc, EXIT_RESTORE, f'{why} 失敗 rc={rc}', f'uv run --no-project python tools/gui/{script} {" ".join(map(str, args))}')
        rc, rs = self.pet_list()
        if rc:
            return self.pass_or(rc, EXIT_RESTORE, f'收尾讀寵物欄失敗 pet rc={rc}')
        bad = {}
        for r in ALL_ROLES:
            hits = [s for s in rs.get(r) or [] if slot_species(s) == BATTLE_PET]
            st = [(s.get('state'), s.get('level')) for s in hits]
            want = orig.get(r)
            okv = len(hits) == 1 and hits[0].get('state') == '出戰' and (not want or hits[0].get('level') is None
                                                                        or (hits[0]['level'] >= want if self.q['kind'] == 'quiz' else hits[0]['level'] == want))
            if not okv:
                bad[r] = st
        if bad:
            return self.fail(EXIT_RESTORE, f'收尾驗證：{BATTLE_PET} 不是剛好 1 隻出戰 / 等級不對（原 {orig}）：{bad}', 'uv run --no-project python tools/gui/pet.py list --role all')
        event(f'收尾：5 人 {BATTLE_PET} 出戰、鎖定戰寵、一般動作攻擊')
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
    print(f'petquest 計畫：任務 {qid}（{q["track"]}）段 {stages_of(qid)}；--confirm-buy-bait {bool(o.get("confirm_buy"))}、--confirm-drop {bool(o.get("confirm_drop"))}')
    if q['kind'] == 'quiz':
        print(f'  accept   questrun.py run {qid} --after none（115 / 155 / 0）')
        print(f'  step1    （步號 1）quest.py --task {q["track"]} --stop-after-rewards 1 → pet.py list 5 人有{q["pet"]}')
        print(f'  prep     關遇敵 → pet.py list 記{BATTLE_PET}等級 → pet_catch --unlock 戰寵 → set-state-many {q["pet"]} 出戰 → pet_catch --lock 戰寵 --battle-pet {q["pet"]}')
        print(f'  train    grind.py start{" --spot " + QUIZ_SPOT if QUIZ_SPOT else "（去練功，依等級選點 + follow）"} → petwatch.py --pet {q["pet"]} --level {q["level"]} --back {BATTLE_PET} --exp-fruit')
        print(f'  turnin   關遇敵 → questrun.py run {qid} --after none')
        print(f'  drop     petdrop.py all {q["drop"]} --confirm-name {q["drop"]} --max-level 1（要 --confirm-drop）')
        print(f'  restore  pet_catch --lock 戰寵 --battle-pet {BATTLE_PET} → ass.py pet all normal 攻擊 --no-resume → pet.py list 驗')
    else:
        print(f'  accept   questrun.py run {qid} --after none（115 / 155 / 117；0 = 已完成）' + ('；讀步號 = 2 → 跳過第 1 輪' if len(q['rounds']) > 1 else ''))
        print(f'  prep     關遇敵 → team.py disband → pet.py list 記{BATTLE_PET}等級 → pet_catch --unlock 戰寵 → pet.py store-many --role all --pets {BATTLE_PET} --depot personal')
        for i, rd in enumerate(q['rounds'], 1):
            sfx = str(i) if len(q['rounds']) > 1 else ''
            a = rd['assign']
            print(f'  catch{sfx}   每批 ≤ 4 隻（{batches(q.get("count", 5), 4)}）：pet_catch.py --assign "{csv_assign(a)}" --count k --stages bait'
                  f' → [誘餌不夠且 --confirm-buy-bait：外掛「+」買 k 次，每次讀石幣扣 {PLUS_COST}] → --stages setup,wait,rename,register（第 2 批 --reuse-setup；第一次輪詢 k×20+20 秒、之後 60 秒；'
                  f'rename = 抓寵者 reset-name、register = 名字驗證，名字讀不出才登錄成長字串）→ pet.py store-many（抓寵者存公共，最後一批留 1）→ list 驗')
            print(f'  distribute{sfx} pet.py take-many --depot public --plan "{",".join(f"{r}:{sp}" for r, sp in take_plan(a))}" --candidates {species_csv(a)} → list 驗每人每物種 1 隻')
            print(f'  train{sfx}   autoswap on → set-state-many {a[0][2]} 出戰 → verify-battle → grind.py start --spot {TRAIN_SPOT} → 每 {POLL_S:.0f} 秒讀等級'
                  f'（第一次 pet.py list，之後 pet.py levels --slots 任務寵格；連兩輪 ≥ 門檻 {rd["need"]}）→ 關遇敵 → autoswap off → rest-all')
            print(f'  turnin{sfx}  questrun.py run {qid} --after none --pet-turnin --rested{" --verify defer" if o.get("verify_defer") else ""}'
                  + ('（下一輪前讀步號要進到下一步）' if i < len(q['rounds']) else '（預期 0）'))
            if rd.get('drop'):
                print(f'  drop{sfx}    petdrop.py all {rd["drop"]} --confirm-name {rd["drop"]} --max-level 1（要 --confirm-drop）')
        if q.get('store_reward'):
            print(f'  store_reward pet.py store-many --role all --pets {q["store_reward"]} --depot personal（獎勵 Lv1）')
        print(f'  restore  pet.py take-many --depot personal --plan "角色:{BATTLE_PET}@原等級" → set-state-many {BATTLE_PET} 出戰 → pet_catch --lock 戰寵 → ass.py pet all normal 攻擊 --no-resume → list 驗')
    print('退出碼：160 參數 161 接取 162 準備 163 誘餌 / 買 164 抓 165 分配 166 練 167 交 168 丟 169 換回；9 驗證視窗 10 斷線')


def run(qid, tools=None, confirm_buy: bool = False, confirm_drop: bool = False, from_stage: str | None = None, to_stage: str | None = None,
        fresh: bool = False, dry_run: bool = False, verify_defer: bool = False) -> int:
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
    o = dict(confirm_buy=confirm_buy, confirm_drop=confirm_drop, fresh=fresh, verify_defer=verify_defer)
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
        r.p = {'done': [], 'finished': time.time(), 'orig': r.p.get('orig')}   # 整套做完：清進度（下一轉重做從頭）
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
    ap.add_argument('--confirm-buy-bait', action='store_true', help='誘餌不夠時准用外掛「+」買（每次 50,000 石幣，按前後驗石幣）')
    ap.add_argument('--confirm-drop', action='store_true', help='准丟獎勵寵（布克布克 / 修寶 / 左迪洛斯，只丟 1 級）')
    ap.add_argument('--from', dest='from_stage', default=None)
    ap.add_argument('--to', dest='to_stage', default=None)
    ap.add_argument('--fresh', action='store_true', help='不管進度檔，從頭')
    ap.add_argument('--verify-defer', action='store_true', help='內部 questrun 帶 --verify defer（沒風險事件的逐人驗證延到呼叫端收尾；postrebirth 用）')
    ap.add_argument('--dry-run', action='store_true')
    a = ap.parse_args(argv)
    if a.cmd == 'run' and not a.dry_run:
        import winenv
        winenv.enable_server()
    rc = run(a.qid, confirm_buy=a.confirm_buy_bait, confirm_drop=a.confirm_drop, from_stage=a.from_stage, to_stage=a.to_stage,
             fresh=a.fresh, dry_run=a.cmd == 'plan' or a.dry_run, verify_defer=a.verify_defer)
    if a.cmd == 'run' and not a.dry_run:
        print(json.dumps(LAST, ensure_ascii=False, default=str))
    return rc


if __name__ == '__main__':
    sys.exit(main())
