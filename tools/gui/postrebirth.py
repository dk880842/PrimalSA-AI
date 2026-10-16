#!/usr/bin/env python3
"""轉生後任務重做總控（2 轉 → 3 轉之間等）：盤點 → 成人儀式 → 彌生和日美子 → 紅暴 → 1.82 前段 → 清背包① → 1.82 後段 → 清背包② → 四大洞窟
→ 恐龍博士 → 卡坦的願望 → 猜謎三兄弟 → 收尾（去練功：依等級選點，未滿地雷區背景起 follow）。只用標準函式庫。順序是使用者 2026-10-13 定案（notes/plan-post2-quests.md「使用者決定」9～12）。
**只有離線測試（test_postrebirth.py），整支未實機**；每段呼叫的 questrun / petquest / bag / grind 各自的實機狀態見各檔。

用法（專案根目錄；WSL / Windows 原生相同）：
  uv run --no-project python tools/gui/postrebirth.py plan                                  # 不碰遊戲：印完整順序與每段指令
  uv run --no-project python tools/gui/postrebirth.py run [--from 段] [--to 段] [--confirm-drop] [--confirm-buy-bait] [--wear-hero-items] [--spot 點名] [--fresh] [--dry-run]
    --confirm-drop      准做不可逆的丟 / 刪：紅暴的巴朵蘭恩（petdrop 1 級）+ 薩姆吉爾的首飾（bag.purge）、清背包（bag.purge 白名單）、
                        寵物任務的獎勵寵（布克布克 / 修寶 / 左迪洛斯）。沒給 → 紅暴不丟、清背包只 --dry-run 列出要刪的（空格不夠就 174 停）、寵物任務到丟寵段 168 停
    （紅暴的薩姆吉爾的首飾依轉數自動判斷，使用者 2026-10-16：**0 轉 → 不刪、拿到的人 bag.py wear 戴上**；**1～5 轉 → 照舊刪**（--drop-items，要 --confirm-drop）；
                        讀不出轉數 → 不刪也不戴、首飾留背包並記 warning。轉數來源：盤點段 exp.py read 的 5 人轉數（全同才算）> 本視窗 tools/.cache[/clients/<程序>]/trans.json（grind.load_trans）；
                        hero 段開跑前判斷、plan 也會顯示。巴朵蘭恩一律照丟。戴的動作實機未驗證）
    --wear-hero-items   強制覆寫判斷：不管轉數一律不刪、改戴（舊旗標保留）
    --confirm-buy-bait  無作用（照傳給 petquest 也無害）：2026-10-15 起 petquest 誘餌不夠一律自動用外掛「+」買缺額，不需旗標（按前讀不到鑽石 / 鑽石有變就停）
    --spot 點名         收尾固定練功點（預設不給 = 去練功 grind.py start：依等級選點 + 未滿地雷區起 follow；2026-10-15 起不寫死地雷區）
    --from / --to       只跑某幾段（段名見 plan）；進度檔 tools/.cache/postrebirth.json 記完成的段（24 小時內），重跑 = 續跑；--fresh 從頭
  可 import：postrebirth.run(tools=…, …) → 退出碼；結果在 postrebirth.LAST

規則：龍王的守護依 questdefs.NO_DRAGON（questrun 一律帶 --dragon，彌生和日美子 / 猜謎三兄弟 / 恐龍博士 / 卡坦的願望 不吃；紅暴 dragon_required 必吃）；
  每段 questrun 都 --after none（中段不回練功），只有收尾 grind.py start。任一段失敗就停在該段、印該段指令（修好後 `run --from 該段` 續跑）。
  驗證視窗 9 / 斷線 10 一律透傳。

段（SEGMENTS）與退出碼（共用 0 / 1 / 2 / 8 / 9 / 10 見 uikit；postrebirth 自己 170～179）：
  inventory  唯讀盤點：exp.py read、bag.py list all、pet.py list --role all（失敗只警告；9 / 10 停）；開頭先 quiet（2026-10-15：follow 停 + 關原地遇敵 + 等戰鬥結束，共用 questrun.Tools.encounter_off_wait / wait_battle_end）
  bag1 / bag2 開頭同樣先 quiet（失敗 174）；questrun / petquest 各段交接自己會關遇敵，不重複
  adult      questrun.py run 2999 --after none --dragon                                       失敗 172
  yayoi      questrun.py run 2017 --after none --dragon（NO_DRAGON：實際不吃）                  失敗 172
  hero       questrun.py run 2031 --after none [--drop-reward 巴朵蘭恩 … --drop-items 薩姆吉爾的首飾 …]
             （耐久力回複藥 NPC 會給，不檢查不買）；156（背包 / 公共倉庫都沒有龍王）→ **自動改跑單人逃跑**
             questrun.py run 2031 --solo …（同樣的丟棄 / 買藥參數；psa-quest-solo：解散 → quest.py --solo 跑到 NPC → 組隊對話 → 步 6 便捷傳送組隊 --fight
             → 步 7 / 8 組隊 → 英雄的祝福存個人 / 龍王的守護存公共 → 丟巴朵蘭恩 / 刪首飾 → DKBO 戰寵改回；2026-10-14 02:41～02:55 手動流程）；
             單人逃跑也失敗 → 173；其他 172
  q182a      questrun.py run 2015 2027 2018 2011 2024 2023 2020 2028 --after none --dragon    失敗 172
  bag1       清背包①：bag.py list all → 有人空格 < 6（1.82 後段最大 bag_slots 5 + 龍王 1）才刪 PURGE1 白名單（龍的魅力之笛只在該人有龍之槍 / 鎧 / 衣時一起刪）
             → 先 purge --dry-run、再實刪（要 --confirm-drop）→ 重讀仍不足 174
  q182b      questrun.py run 2025 2010 2014 2012 2013 2021 --after none --dragon（摩娜西普存個人 / 人龍隨機蛋存公共由 questdefs post 自動做）  失敗 172
  bag2       清背包②：同上，門檻 8 格（四大洞窟中間品 + 四件產物），名單 PURGE2 = PURGE1 + 杉的手環 / 月光的手鐲 / 巴巴洛的許可證；四大洞窟產物 bag.PURGE_FORBID 永不刪
  caves      questrun.py run 2000 2003 2001 2002 --after none --dragon --max-min 45           失敗 172
  dino       petquest.py run 2016 [--confirm-drop]（先存第 2 格 → 抓 / 練 → 才接任務，見 petquest.py 檔頭）  失敗 175
             後面還會解卡坦（katan 在本次 --from / --to 範圍內、進度檔沒完成）→ 帶 `--keep-autoswap`：train 結束不關外掛「自動轉換戰寵」、restore 整段跳過
             （自動轉換開著會把剛換回的戰寵換掉、卡坦 prep 又要存倉；第 2 格名字 + 原等級留在 petquest 進度檔共用紀錄 slot2_stored，卡坦 prep 直接沿用、由卡坦 restore 統一換回並清掉，見 petquest.py 檔頭）；
             只跑 dino（--to dino 等）照舊關。dino 成功帶旗標後進度檔記 autoswap_pending，katan 成功才清。
             **中斷保險（選「提示 + finish 自動關」）**：dino 之後卡坦沒跑完就停（失敗 / --to 擋掉 / 手動中斷）→ 結束時 event + LAST['warnings'] 提示
             「自動轉換戰寵還開著、朵拉比斯在個人倉庫」與續跑指令，不在失敗現場自動操作遊戲（可能是斷線 / 驗證視窗 / 戰鬥中）；
             之後 `--from finish`（沒走卡坦就收尾）時 finish 段開頭若 autoswap_pending 還在 → 自動 pet_catch.py --autoswap off（冪等）再收尾
  katan      petquest.py run 2019 …                                                            失敗 175
  quiz       petquest.py run 3003 …（練金布伊前 petwatch --exp-fruit 吃 2倍智慧果）            失敗 175
  finish     questrun.py status --role all <全部任務>（全員完成的任務自動移出 questrun 待驗清單）→ not_done 不空 → questrun.py verify <落後任務> --role <落後者>
             （進行中 → 交接 → bossretry --who 補人 → 再讀；待接取 / 補不上 108）→ pet.py list（5 人各 1 隻戰寵出戰 + 騎寵騎乘）→ 去練功 grind.py start（不帶 --spot；--spot 給了才帶）
             （原地遇敵 + 5 人快戰確認）。失敗 176
  逐人驗證：questrun 段一律 --verify defer、petquest 帶 --verify-defer（2026-10-13 review 1013b §2.1）：沒風險事件的任務不在各段結束各驗一次（每次 115～154 秒），
             延到收尾那一次 status --role all；有風險事件（30 / 32 / 38 / 21 / 41 / bossretry / 重登 / BOSS 後 HP 0 / 交寵物）照舊當場驗，依賴任務接取前照舊先驗前置
  170 參數 / 段名不認得；171 保留不用（盤點失敗只警告）
"""
import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import clients  # noqa: E402
import uikit  # noqa: E402

SRC = 'postrebirth'
ROOT = uikit.ROOT
import logpaths  # noqa: E402
EVENT_LOG = logpaths.p(clients.npath('quest-events.log'))     # 主視窗 = notes/quest-events.log；其他 = notes/clients/<程序名>/
PROGRESS = logpaths.p(uikit.CACHE / 'postrebirth.json')

EXIT_ARGS, EXIT_INV, EXIT_QUEST, EXIT_HERO, EXIT_BAG, EXIT_PET, EXIT_FINISH = 170, 171, 172, 173, 174, 175, 176
PASS = (uikit.EXIT_UNKNOWN_SCREEN, uikit.EXIT_HALT)
ALL_ROLES = clients.roster()        # 這個視窗（PSA_CLIENT）的名單：主視窗 DKBO、DKBO2～5；PrimalSA2 = DKBO6～10
PROGRESS_TRUST_S = 24 * 3600
NODRAGON_RC = 156                  # questrun.EXIT_NODRAGON
LAST: dict = {}

Q182A = [2015, 2027, 2018, 2011, 2024, 2023, 2020, 2028]
Q182B = [2025, 2010, 2014, 2012, 2013, 2021]
CAVES = [2000, 2003, 2001, 2002]
ALL_TASKS = [2999, 2017, 2031] + Q182A + Q182B + CAVES + [2016, 2019, 3003]
# 清背包名單（ui/bag.md 白名單；使用者 10-12 / 10-13 核准；notes/plan-post2-quests.md 第 7 / 8 / 12 點）
PURGE1 = ['儀之兜', '龍之槍', '龍之鎧', '龍之衣', '薩頓家的秘藥', '山賊的羽飾', '亞姆亞姆的斧頭', '空想的衣服', '老爺爺的護身符',
          '仙尼亞的花', '郵寄物', '切繩石', '馬祖的斧頭', '馬祖的矛', '馬祖的棍棒', '空想的帽子', '空想的豎琴']
PURGE2 = PURGE1 + ['杉的手環', '月光的手鐲', '巴巴洛的許可證']
FLUTE, DRAGON_GEAR = '龍的魅力之笛', ('龍之槍', '龍之鎧', '龍之衣')
NEED1, NEED2 = 6, 8                # 清背包①（1.82 後段最大 bag_slots 5 + 龍王 1）/ ②（四大洞窟，使用者建議 ≥ 8）
HERO_SOLO = ['--solo']            # questrun 156（沒龍王）→ 單人逃跑重跑同一段（2026-10-14 起自動，不再停 173 交人）
HERO_DROP_PET = ['--drop-reward', '巴朵蘭恩', '--confirm-drop', '巴朵蘭恩']
HERO_DROP_ITEMS = ['--drop-items', '薩姆吉爾的首飾', '--confirm-drop-items', '薩姆吉爾的首飾']
HERO_DROP = HERO_DROP_PET + HERO_DROP_ITEMS
HERO_RING = '薩姆吉爾的首飾'       # 飾品（Item type 10、level / transLimit 0 = 0 轉也能戴；運 / 魅 / 閃避 +5、附複活光精靈）；PURGE1 / PURGE2 / bag.AUTO_PURGE 都不含


def team_trans(trans_by_role: dict | None):
    """5 人轉數（{角色: 轉數 | None}）→ 全部讀到且相同才回該轉數，否則 None（不猜）"""
    vals = [v for v in (trans_by_role or {}).values()]
    if not vals or any(not isinstance(v, int) for v in vals) or len(set(vals)) != 1:
        return None
    return vals[0]


def hero_mode(o: dict, trans) -> str:
    """紅暴首飾處理：'wear' 戴（0 轉或 --wear-hero-items 強制）/ 'drop' 刪（1～5 轉）/ 'keep' 不刪不戴（讀不出轉數）"""
    if o.get('wear_hero_items') or trans == 0:
        return 'wear'
    return 'drop' if isinstance(trans, int) and 1 <= trans <= 5 else 'keep'


def hero_drop(o: dict) -> list:
    """紅暴的丟棄旗標：--confirm-drop 才丟；o['hero_mode'] 不是 'drop'（0 轉戴 / 讀不出轉數留著）→ 只丟巴朵蘭恩，首飾不刪。沒判斷過（None）= 'keep'"""
    if not o.get('confirm_drop'):
        return []
    return list(HERO_DROP if o.get('hero_mode') == 'drop' else HERO_DROP_PET)

PURGE_CHUNK = 3
SEGMENTS = ['inventory', 'adult', 'yayoi', 'hero', 'q182a', 'bag1', 'q182b', 'bag2', 'caves', 'dino', 'katan', 'quiz', 'finish']
TITLES = {'inventory': '盤點交接', 'adult': '成人儀式', 'yayoi': '彌生和日美子', 'hero': '紅暴（英雄島前傳）', 'q182a': '1.82 前段',
          'bag1': '清背包①', 'q182b': '1.82 後段', 'bag2': '清背包②', 'caves': '四大洞窟', 'dino': '恐龍博士', 'katan': '卡坦的願望',
          'quiz': '猜謎三兄弟', 'finish': '收尾'}


# ---------------------------------------------------------------- 純函式
def last_json(lines) -> dict:
    for ln in reversed(list(lines or [])):
        ln = str(ln).strip()
        if ln.startswith('{') and ln.endswith('}'):
            try:
                return json.loads(ln)
            except ValueError:
                continue
    return {}


def purge_plan(bags: dict, need: int, names: list) -> tuple:
    """bag.py list 的 {角色: {'slots': {格: 名稱}, 'free': n}} → (要刪的 {角色: [名稱…]}, 空格不足的 {角色: free})。
    只對空格 < need 的人刪；龍的魅力之笛只在該人背包有龍之槍 / 鎧 / 衣時一起刪（ui/bag.md 條件）；名稱比對交給 bag.purge（這裡只決定名單）"""
    import bag
    plan, short = {}, {}
    for r, d in (bags or {}).items():
        free = (d or {}).get('free')
        if free is None or free >= need:
            continue
        short[r] = free
        items = [str(t) for t in ((d or {}).get('slots') or {}).values()]
        have = [n for n in names if any(bag.name_match(t, n) for t in items)]
        if any(any(bag.name_match(t, g) for t in items) for g in DRAGON_GEAR):
            have.append(FLUTE)
        plan[r] = have
    return plan, short


def group_by_names(plan: dict) -> list:
    """{角色: [名稱]} → [(角色清單, 名稱清單)]（名單相同的人一起刪，背包面板開一次）；名單空的人略過"""
    groups = {}
    for r, ns in plan.items():
        if ns:
            groups.setdefault(tuple(ns), []).append(r)
    return [(rs, list(ns)) for ns, rs in groups.items()]


def seg_cmds(seg: str, o: dict) -> list:
    """段 → [(腳本, 參數)]（plan 顯示與 run 共用）"""
    pq = (['--confirm-drop'] if o.get('confirm_drop') else []) + (['--confirm-buy-bait'] if o.get('confirm_buy') else []) + ['--verify-defer']
    vd = ['--verify', 'defer']         # 逐人驗證延到收尾（review 1013b §2.1）：有風險事件的任務 questrun 照舊當場驗
    return {
        'inventory': [('exp.py', ['read']), ('bag.py', ['list', 'all']), ('pet.py', ['list', '--role', 'all', '--json'])],
        'adult': [('questrun.py', ['run', 2999, '--after', 'none', '--dragon'] + vd)],
        'yayoi': [('questrun.py', ['run', 2017, '--after', 'none', '--dragon'] + vd)],
        'hero': [('questrun.py', ['run', 2031, '--after', 'none'] + vd + hero_drop(o))],
        'q182a': [('questrun.py', ['run'] + Q182A + ['--after', 'none', '--dragon'] + vd)],
        'bag1': [('bag.py', ['list', 'all']), ('bag.py', ['purge', '<不足的人>', '--names', ','.join(PURGE1) + '[,龍的魅力之笛]', '--dry-run']), ('bag.py', ['purge', '…（要 --confirm-drop）'])],
        'q182b': [('questrun.py', ['run'] + Q182B + ['--after', 'none', '--dragon'] + vd)],
        'bag2': [('bag.py', ['list', 'all']), ('bag.py', ['purge', '<不足的人>', '--names', ','.join(PURGE2) + '[,龍的魅力之笛]', '--dry-run']), ('bag.py', ['purge', '…（要 --confirm-drop）'])],
        'caves': [('questrun.py', ['run'] + CAVES + ['--after', 'none', '--dragon', '--max-min', 45] + vd)],
        'dino': [('petquest.py', ['run', 2016] + pq + (['--keep-autoswap'] if o.get('keep_autoswap') else []))],
        'katan': [('petquest.py', ['run', 2019] + pq)],
        'quiz': [('petquest.py', ['run', 3003] + pq)],
        'finish': [('questrun.py', ['status', '--role', 'all'] + ALL_TASKS), ('pet.py', ['list', '--role', 'all', '--json']),
                   ('grind.py', ['start'] + (['--spot', o['spot']] if o.get('spot') else [])),
                   ('questrun.py', ['verify', '<落後的任務 ID>', '--role', '<落後者>'])],
    }[seg]


def katan_follows(from_seg, to_seg, done=()) -> bool:
    """本次 run 在 dino 之後還會跑 katan 嗎（範圍內、且沒被進度檔跳過）→ dino 帶 --keep-autoswap"""
    i0 = SEGMENTS.index(from_seg) if from_seg else 0
    i1 = SEGMENTS.index(to_seg) if to_seg else len(SEGMENTS) - 1
    k = SEGMENTS.index('katan')
    return i0 <= k <= i1 and (bool(from_seg) or 'katan' not in done)


def fmt(script, args) -> str:
    return f'uv run --no-project python tools/gui/{script} ' + ' '.join(map(str, args))


def pets_ok(roles_slots: dict, battle: str | None = None) -> dict:
    """收尾：每人剛好 1 隻出戰（battle 有給才再核對名字；預設不限名字 —— 各視窗戰寵不同，p1 朵拉比斯、p2 迪基格斯）+ 有一隻騎乘 → 不對的 {角色: 原因}"""
    bad = {}
    for r in ALL_ROLES:
        slots = [s for s in (roles_slots or {}).get(r) or [] if s and not s.get('empty')]
        b = [s for s in slots if s.get('state') == '出戰' and (not battle or (s.get('name') or s.get('species')) == battle)]
        ride = [s for s in slots if s.get('state') == '騎乘']
        why = []
        if len(b) != 1:
            why.append(f'{battle or ""}出戰 {len(b)} 隻')
        if not ride:
            why.append('沒有騎乘中的騎寵')
        if why:
            bad[r] = '、'.join(why)
    return bad


# ---------------------------------------------------------------- 紀錄 / 進度
def event(msg: str) -> None:
    line = f'{time.strftime("%Y-%m-%d %H:%M:%S")} [postrebirth] {msg}'
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


class Tools:
    def cached_trans(self):
        """本視窗 trans.json 的隊長轉數（grind.load_trans，背包讀字 / 轉生確認時寫）；沒有 None"""
        import grind
        return grind.load_trans()

    def quiet(self) -> int:
        """開面板前先靜下來（共用 questrun 交接的同一套）：follow 還在跑先停 → 關原地遇敵並等這場打完（Tools.encounter_off_wait）
        → 畫面還是戰鬥就等到結束（wait_battle_end，最多 BATTLE_WAIT_S）。→ 0 = 靜了；非 0 = 失敗（調用端決定警告或停）。
        2026-10-15 19:09：p2 在地雷區掛機中被 exp.py 開人物資訊讀經驗，快戰 / 轉場疊上來 → preflight 連 3 次不認得 → 9 + 停手旗標"""
        import questrun
        qt = questrun.Tools()
        if qt.follow_active():
            qt.follow_stop()
            if qt.follow_active():
                return 1
        try:
            qt.encounter_off_wait()
        except RuntimeError:
            return 2
        return 0 if questrun.wait_battle_end(qt, '開面板前') else 3

    def sub(self, script: str, args, timeout: float = 6 * 3600) -> tuple:
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


class Run:
    def __init__(self, T, o: dict):
        self.T, self.o = T, o
        p = load_progress()
        if o.get('fresh') or time.time() - (p.get('ts') or 0) > PROGRESS_TRUST_S:
            p = {}
        p.setdefault('done', [])
        self.p = p
        self.info: dict = {}
        self.warnings: list = []

    def save(self):
        self.p['ts'] = time.time()
        save_progress(self.p)

    def fail(self, rc: int, msg: str, manual: str = '') -> int:
        self.info.update(msg=msg, manual=manual)
        event(f'失敗 rc={rc}：{msg}' + (f'｜手動 / 續跑：{manual}' if manual else ''))
        try:
            import errlog
            errlog.add(f'postrebirth：{msg}', source='postrebirth')
        except Exception:                                              # noqa: BLE001
            pass
        return rc

    def sub(self, script, args, timeout=6 * 3600):
        event(f'→ {fmt(script, args)}')
        rc, lines = self.T.sub(script, list(args), timeout)
        event(f'← {script} rc={rc}')
        return rc, lines

    def quiet(self, where: str) -> int:
        """面板類段落（inventory / bag1 / bag2）開頭：關遇敵 + 等戰鬥結束（T.quiet；測試用 Fake 沒有就略過）→ 0 或失敗碼"""
        q = getattr(self.T, 'quiet', None)
        if q is None:
            return 0
        rc = q()
        event(f'{where}：開面板前關原地遇敵 + 等戰鬥結束 → ' + ('OK' if not rc else f'失敗 rc={rc}（1 follow 停不掉 / 2 關遇敵失敗 / 3 等不到戰鬥結束）'))
        return rc

    def s_inventory(self) -> int:
        if self.quiet('盤點'):
            self.warnings.append('盤點前關遇敵 / 等戰鬥沒成功（照跑）')
        for script, args in seg_cmds('inventory', self.o):
            rc, lines = self.sub(script, args, 1800)
            if rc in PASS:
                return rc
            if rc:
                self.warnings.append(f'盤點 {script} rc={rc}')
                event(f'盤點：{script} rc={rc}（只警告，照跑）')
            elif script == 'exp.py':
                t = team_trans({r: (d or {}).get('trans') for r, d in (last_json(lines).get('roles') or {}).items()})
                if t is not None:
                    self.p['trans'] = t
                    self.save()
            elif script == 'bag.py':
                self.p['bags_start'] = {r: (d or {}).get('free') for r, d in (last_json(lines).get('bags') or {}).items()}
        return 0

    def resolve_hero_mode(self) -> str:
        """hero 段開跑前判斷首飾怎麼處理（盤點 exp.py 的轉數 > trans.json 快取）→ 寫進 self.o['hero_mode']"""
        t, src = self.p.get('trans'), '盤點 exp.py'
        if not isinstance(t, int):
            try:
                t, src = getattr(self.T, 'cached_trans', lambda: None)(), 'trans.json'
            except Exception:                                          # noqa: BLE001
                t = None
        m = hero_mode(self.o, t)
        self.o['hero_mode'] = m
        event(f'紅暴首飾：轉數 {t if isinstance(t, int) else "讀不出"}（{src if isinstance(t, int) else "-"}）→ ' + {'wear': f'戴上（不刪）', 'drop': '刪除', 'keep': '不刪也不戴（留背包）'}[m])
        if m == 'keep':
            self.warnings.append(f'紅暴首飾：讀不出隊伍轉數，「{HERO_RING}」不刪也不戴（留背包；0 轉手動 bag.py wear、1 轉以上手動 bag.py purge）')
        return m

    def wear_hero_items(self) -> None:
        """hero_mode == 'wear'：紅暴成功後，背包有首飾的人 bag.py wear 戴上（既有 bag.wear_item）。失敗只記 warning，不讓紅暴段失敗"""
        def warn(m):
            self.warnings.append(m)
            event('警告：' + m)
        if self.quiet('戴首飾'):
            return warn(f'紅暴首飾：開背包前關遇敵 / 等戰鬥沒成功，沒戴（首飾留背包；手動 bag.py wear <角色> {HERO_RING}）')
        rc, lines = self.sub('bag.py', ['list', 'all'], 1200)
        if rc:
            return warn(f'紅暴首飾：bag.py list rc={rc}，沒戴（手動 bag.py wear all {HERO_RING}）')
        bags = last_json(lines).get('bags') or {}
        who = [r for r in ALL_ROLES if any(str(v).replace('(同圖)', '') == HERO_RING for v in ((bags.get(r) or {}).get('slots') or {}).values())]  # 圖示辨識的格名字會帶「(同圖)」
        event(f'紅暴首飾：背包有「{HERO_RING}」的人 {who}')
        for r in who:
            rc, _ = self.sub('bag.py', ['wear', r, HERO_RING])
            if rc:
                warn(f'紅暴首飾：{r} 戴「{HERO_RING}」失敗 rc={rc}（首飾留背包，之後手動 bag.py wear {r} {HERO_RING}）')

    def s_quest(self, seg) -> int:
        if seg == 'hero':
            self.resolve_hero_mode()
        (script, args), = seg_cmds(seg, self.o)
        rc, _ = self.sub(script, args)
        if not rc:
            if seg == 'hero' and self.o.get('hero_mode') == 'wear':
                self.wear_hero_items()
            if seg == 'dino' and self.o.get('keep_autoswap'):
                self.p['autoswap_pending'] = True                      # 自動轉換戰寵留著開，等卡坦解完才關
                self.save()
            elif seg == 'katan' and self.p.get('autoswap_pending'):
                self.p['autoswap_pending'] = False                     # 卡坦 train 結束已關
                self.save()
            return 0
        if seg == 'hero' and rc == NODRAGON_RC:                        # 2026-10-14：沒龍王 → 自動改單人逃跑（同一串參數加 --solo）
            sargs = list(args) + HERO_SOLO
            event('紅暴：questrun 156 = 背包 / 公共倉庫都沒有龍王的守護 → 自動改走單人逃跑（questrun --solo，psa-quest-solo）')
            rc, _ = self.sub(script, sargs)
            if not rc:
                if self.o.get('hero_mode') == 'wear':
                    self.wear_hero_items()
                return 0
            return rc if rc in PASS else self.fail(EXIT_HERO, f'紅暴單人逃跑：questrun --solo 退出碼 {rc}（意義見 questrun.py 檔頭）；做完後 `run --from q182a` 續跑',
                                                   f'{fmt(script, sargs)}；或照 psa-quest-solo §4 手動；修好後 postrebirth.py run --from hero')
        code = EXIT_PET if script == 'petquest.py' else EXIT_QUEST
        return rc if rc in PASS else self.fail(code, f'{TITLES[seg]}：{script} 退出碼 {rc}（意義見該腳本檔頭）', f'{fmt(script, args)}；修好後 postrebirth.py run --from {seg}')

    def s_bag(self, seg) -> int:
        need, names = (NEED1, PURGE1) if seg == 'bag1' else (NEED2, PURGE2)
        if self.quiet(TITLES[seg]):
            return self.fail(EXIT_BAG, f'{TITLES[seg]}：開背包前關遇敵 / 等戰鬥結束失敗（請人看畫面）', f'postrebirth.py run --from {seg}')
        rc, lines = self.sub('bag.py', ['list', 'all'], 1200)
        if rc:
            return rc if rc in PASS else self.fail(EXIT_BAG, f'{TITLES[seg]}：bag.py list rc={rc}', fmt('bag.py', ['list', 'all']))
        bags = last_json(lines).get('bags') or {}
        plan, short = purge_plan(bags, need, names)
        if not short:
            event(f'{TITLES[seg]}：每人空格都 ≥ {need}（{ {r: (d or {}).get("free") for r, d in bags.items()} }）→ 不刪')
            return 0
        groups = group_by_names(plan)
        event(f'{TITLES[seg]}：空格不足 {need} 的人 {short}；可刪 {plan}')
        for roles, ns in groups:
            args = ['purge', ','.join(roles), '--names', ','.join(ns)]
            rc, _ = self.sub('bag.py', args + ['--dry-run'], 1200)
            if rc:
                return rc if rc in PASS else self.fail(EXIT_BAG, f'{TITLES[seg]}：purge --dry-run rc={rc}', fmt('bag.py', args + ['--dry-run']))
            if not self.o.get('confirm_drop'):
                continue
            for i in range(0, len(ns), PURGE_CHUNK):           # 2026-10-15：一次勾 10 件提示窗清單超出一頁讀不全（96）→ 每次最多 PURGE_CHUNK 個名字
                cargs = ['purge', ','.join(roles), '--names', ','.join(ns[i:i + PURGE_CHUNK])]
                rc, _ = self.sub('bag.py', cargs, 1200)
                if rc:
                    return rc if rc in PASS else self.fail(EXIT_BAG, f'{TITLES[seg]}：purge rc={rc}（93 防護 / 96 提示窗清單對不上）', fmt('bag.py', cargs))
        if not self.o.get('confirm_drop'):
            return self.fail(EXIT_BAG, f'{TITLES[seg]}：空格不足 {short}（要 ≥ {need}），刪道具要 --confirm-drop（只 --dry-run 列了 {plan}）',
                             '; '.join(fmt('bag.py', ['purge', ','.join(rs), '--names', ','.join(ns)]) for rs, ns in groups) or '人工清背包')
        rc, lines = self.sub('bag.py', ['list', 'all'], 1200)
        if rc:
            return rc if rc in PASS else self.fail(EXIT_BAG, f'{TITLES[seg]}：刪完重讀 rc={rc}')
        _, short2 = purge_plan(last_json(lines).get('bags') or {}, need, names)
        if short2:
            return self.fail(EXIT_BAG, f'{TITLES[seg]}：刪完白名單仍有人空格 < {need}：{short2} → 名單外的不刪，請人看（存倉 / 決定丟什麼）', fmt('bag.py', ['list', 'all']))
        return 0

    def s_finish(self) -> int:
        if self.p.get('autoswap_pending'):                             # dino 留著開、卡坦沒走完就收尾 → 先關（冪等）
            event('收尾：恐龍博士留著開的自動轉換戰寵還沒關（卡坦沒完成）→ pet_catch.py --autoswap off')
            rc, _ = self.sub('pet_catch.py', ['--autoswap', 'off'], 900)
            if rc:
                return rc if rc in PASS else self.fail(EXIT_FINISH, f'收尾關自動轉換戰寵失敗 rc={rc}', fmt('pet_catch.py', ['--autoswap', 'off']))
            self.p['autoswap_pending'] = False
            self.save()
        cmds = seg_cmds('finish', self.o)
        script, args = cmds[0]
        rc, lines = self.sub(script, args, 3600)
        res = last_json(lines)
        nd = res.get('not_done')
        if rc in PASS:
            return rc
        if rc or nd is None:
            return self.fail(EXIT_FINISH, f'收尾逐人讀任務狀態失敗 rc={rc}', fmt(script, args))
        if nd:                                                         # 落後者（延後驗證才發現的）→ questrun verify：bossretry --who 補人 → 再讀（review 1013b §2.1）
            ids = res.get('not_done_ids') or []
            who = sorted({r for v in nd.values() for r in v})
            if not ids:
                return self.fail(EXIT_FINISH, f'收尾：還有任務沒全員完成 {nd}（questrun 沒給 not_done_ids）', fmt(script, args))
            vargs = ['verify'] + ids + ['--role', ','.join(who)]
            event(f'收尾：還有任務沒全員完成 {nd} → questrun verify 補人（bossretry --who）')
            rc, _ = self.sub('questrun.py', vargs, 3 * 3600)
            if rc:
                return rc if rc in PASS else self.fail(EXIT_FINISH, f'收尾：落後者補不上 {nd}（questrun verify rc={rc}；108 = 待接取 / 補人後仍沒完成）', fmt('questrun.py', vargs))
        script, args = cmds[1]
        rc, lines = self.sub(script, args, 900)
        if rc:
            return rc if rc in PASS else self.fail(EXIT_FINISH, f'收尾讀寵物欄 rc={rc}', fmt(script, args))
        bad = pets_ok(last_json(lines).get('roles') or {})
        if bad:
            return self.fail(EXIT_FINISH, f'收尾寵物狀態不對：{bad}', '看 pet.py list；戰寵出戰、騎寵騎乘後 --from finish 續跑')
        script, args = cmds[2]
        rc, _ = self.sub(script, args, 1800)
        if rc:
            return rc if rc in PASS else self.fail(EXIT_FINISH, f'grind start 失敗 rc={rc}（50～58 見 grind.py）', fmt(script, args))
        return 0

    def do(self, seg) -> int:
        if seg == 'inventory':
            return self.s_inventory()
        if seg in ('bag1', 'bag2'):
            return self.s_bag(seg)
        if seg == 'finish':
            return self.s_finish()
        return self.s_quest(seg)


def plan_hero_mode(o: dict) -> tuple:
    """plan 用：不碰遊戲，只看進度檔 / trans.json 快取判斷首飾處理 → (模式, 轉數或 None)"""
    t = load_progress().get('trans')
    if not isinstance(t, int):
        try:
            t = Tools().cached_trans()
        except Exception:                                              # noqa: BLE001
            t = None
    return hero_mode(o, t), t


def print_plan(o: dict) -> None:
    o = dict(o)
    o['hero_mode'], ptrans = plan_hero_mode(o)
    print(f'postrebirth 計畫：{len(SEGMENTS)} 段（--confirm-drop {bool(o.get("confirm_drop"))}；--wear-hero-items（強制戴）{bool(o.get("wear_hero_items"))}；誘餌不夠 petquest 自動買缺額，不需旗標）')
    for seg in SEGMENTS:
        print(f'[{seg}] {TITLES[seg]}')
        for script, args in seg_cmds(seg, o):
            print('  ' + fmt(script, args))
        if seg in ('bag1', 'bag2'):
            print(f'  （空格 < {NEED1 if seg == "bag1" else NEED2} 的人才刪；龍的魅力之笛只在該人有龍之槍 / 鎧 / 衣時；四大洞窟產物 / 龍王 / 誘餌等 bag.PURGE_FORBID 永不刪）')
        if seg == 'hero':
            m = o['hero_mode']
            how = {'wear': f'0 轉 / 強制 → 只丟巴朵蘭恩、不帶 --drop-items；紅暴成功後 bag.py list all → 背包有「{HERO_RING}」的人 bag.py wear <角色> {HERO_RING}；戴失敗只警告',
                   'drop': f'1～5 轉 → 帶 --drop-items 刪「{HERO_RING}」', 'keep': f'讀不出轉數 → 不刪也不戴、首飾留背包（開跑時盤點 exp.py 會再讀一次轉數）'}[m]
            print(f'  （首飾：轉數 {ptrans if isinstance(ptrans, int) else "讀不出"}；{how}）' + ('' if o.get('confirm_drop') else '（沒 --confirm-drop：巴朵蘭恩也不丟）'))
            print('  （156 沒龍王 → 自動改跑 ' + fmt('questrun.py', seg_cmds('hero', o)[0][1] + HERO_SOLO) + '；仍失敗 173）' + ('' if o.get('confirm_drop') else '；沒 --confirm-drop：巴朵蘭恩 / 首飾不丟（之後寵物欄少 1 格，petquest 分批會變小）'))
    print('退出碼：170 參數（171 保留：盤點只警告）172 任務段 173 紅暴單人逃跑失敗 174 清背包 175 寵物任務段 176 收尾；9 驗證視窗 10 斷線')


def run(tools=None, from_seg: str | None = None, to_seg: str | None = None, confirm_drop: bool = False, confirm_buy: bool = False,
        spot: str | None = None, fresh: bool = False, dry_run: bool = False, wear_hero_items: bool = False) -> int:
    LAST.clear()
    for s in (from_seg, to_seg):
        if s and s not in SEGMENTS:
            print(f'postrebirth：段名 {s!r} 不在 {SEGMENTS}', file=sys.stderr)
            return EXIT_ARGS
    o = dict(confirm_drop=confirm_drop, confirm_buy=confirm_buy, spot=spot, fresh=fresh, wear_hero_items=wear_hero_items)
    if dry_run:
        o['keep_autoswap'] = katan_follows(from_seg, to_seg)
        print_plan(o)
        return 0
    T = tools or Tools()
    r = Run(T, o)
    o['keep_autoswap'] = katan_follows(from_seg, to_seg, r.p['done'])
    i0 = SEGMENTS.index(from_seg) if from_seg else 0
    i1 = SEGMENTS.index(to_seg) if to_seg else len(SEGMENTS) - 1
    event(f'開始：段 {SEGMENTS[i0:i1 + 1]}（進度檔已完成 {r.p["done"]}）')
    rc, ran = 0, []
    for seg in SEGMENTS[i0:i1 + 1]:
        if seg in r.p['done'] and not from_seg:
            event(f'[{seg}] {TITLES[seg]}：進度檔記已完成 → 跳過')
            continue
        event(f'== [{seg}] {TITLES[seg]} ==')
        rc = r.do(seg)
        if rc:
            break
        ran.append(seg)
        if seg not in r.p['done']:
            r.p['done'].append(seg)
        r.save()
    if not rc and SEGMENTS[i1] == SEGMENTS[-1]:
        r.p = {'done': [], 'finished': time.time()}                   # 全部做完：清進度（下一轉從頭）
        r.save()
    if r.p.get('autoswap_pending') and not (SEGMENTS[i1] == SEGMENTS[-1] and not rc):   # 中斷保險：dino 留著開，卡坦沒完成就停
        w = ('恐龍博士帶 --keep-autoswap：外掛「自動轉換戰寵」還開著、原朵拉比斯在個人倉庫（petquest 進度檔 slot2_stored 記原等級）→ 續跑 '
             'postrebirth.py run --from katan（卡坦 train 結束會關、restore 換回）；不解卡坦就 pet_catch.py --autoswap off 再手動換回朵拉比斯')
        r.warnings.append(w)
        event('警告：' + w)
    LAST.update(ok=rc == 0, rc=rc, ran=ran, info=r.info, warnings=r.warnings)
    event(f'結束 rc={rc}，跑了 {ran}' + (f'；停在 [{seg}] {TITLES[seg]}，修好後 postrebirth.py run --from {seg}' if rc else ''))
    return rc


def main(argv=None) -> int:
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('cmd', choices=['plan', 'run'])
    ap.add_argument('--from', dest='from_seg', default=None)
    ap.add_argument('--to', dest='to_seg', default=None)
    ap.add_argument('--confirm-drop', action='store_true', help='准丟 / 刪（紅暴巴朵蘭恩 + 首飾、清背包白名單、寵物任務獎勵寵）')
    ap.add_argument('--confirm-buy-bait', action='store_true', help='無作用（no-op，相容舊指令）：petquest 誘餌不夠一律自動買缺額')
    ap.add_argument('--wear-hero-items', action='store_true', help='強制覆寫：紅暴首飾不管轉數一律不刪、改戴（預設依轉數：0 轉戴、1～5 轉刪、讀不出留著）')
    ap.add_argument('--spot', default=None, help='收尾固定練功點（預設不給 = 去練功：依等級選點 + follow）')
    ap.add_argument('--fresh', action='store_true')
    ap.add_argument('--dry-run', action='store_true')
    a = ap.parse_args(argv)
    if not ALL_ROLES:
        print(f'postrebirth：PSA_CLIENT={clients.name()} 沒有登錄角色名單（clients.ROSTERS），不跑', file=sys.stderr)
        return EXIT_ARGS
    rc = run(from_seg=a.from_seg, to_seg=a.to_seg, confirm_drop=a.confirm_drop, confirm_buy=a.confirm_buy_bait, spot=a.spot,
             fresh=a.fresh, dry_run=a.cmd == 'plan' or a.dry_run, wear_hero_items=a.wear_hero_items)
    if a.cmd == 'run' and not a.dry_run:
        print(json.dumps(LAST, ensure_ascii=False, default=str))
    return rc


if __name__ == '__main__':
    sys.exit(main())
