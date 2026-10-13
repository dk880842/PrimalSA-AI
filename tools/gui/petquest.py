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
  可 import：petquest.run(qid, tools=…, confirm_buy=…, confirm_drop=…) → 退出碼；結果在 petquest.LAST

流程（各段失敗就停在該段、印手動指令；畫面不認得 9 / 斷線 10 一律透傳；進度檔記完成的段，重跑 = 續跑）：
  恐龍博士 2016 / 卡坦的願望 2019（使用者 2026-10-12 S5 / S6 做法；卡坦步 1 鯊、步 2 雞兩輪）
    accept      questrun.py run <ID> --after none：接取後停在寵物步（115 manual / 155 需先抓寵 / 117 對話 ↔ 選擇循環）；0 = 任務已完成 → 只做收尾
                卡坦接取後讀追蹤步號：已在步 2 → 跳過第 1 輪
    prep        關原地遇敵 + 等戰鬥結束 → 解散隊伍 → pet.py list 記 5 人原戰寵（朵拉比斯，出戰）等級 → 取消鎖定戰寵 → 朵拉比斯 5 人存個人倉庫
                （寵物欄只剩騎寵 + 4 空格；抓寵 / 練寵都不帶原戰寵）
    catch[N]    每輪每批可抓 = 抓寵者寵物欄空格（最少那人；正常 4）：分批抓到 5 隻，滿了會自動進個人倉庫（沒縮圖、成長字串沒登錄就取不出來）→ 所以一批 ≤ 空格數：
                pet_catch.py --stages bait（公共倉庫誘餌取 k 拆 k）→ 有人誘餌不夠（92）且 --confirm-buy-bait → 外掛「+」買 k 次（見上）→
                pet_catch.py --stages setup,wait,register --count k（register = 依抓寵者登錄成長字串）→ 抓寵者把這批存公共（最後一批留 1 隻）
                pet.py store-many --pick last --skip-missing --candidates 本輪物種 → pet.py list 驗數量
    distribute[N]  pet.py take-many --depot public --plan "角色:物種,…" --candidates 本輪物種（每人每物種 1 隻；抓寵者自己留的那隻不取）→ list 驗每人每物種 1 隻
    train[N]    自動轉換戰寵 on（轉換級數使用者設 30）→ 第一種任務寵 5 人出戰 → pet_catch.py --verify-battle → grind.py start --spot 柯奧4F龜洞
                → 每 POLL_S 秒 pet.py list 讀等級，全部 ≥ 門檻（恐龍 魯尼帖斯 18 / 貝魯卡 30；卡坦 25）→ 關遇敵 → 自動轉換戰寵 off → pet.py rest-all（任務寵改等待）
    turnin[N]   questrun.py run <ID> --after none --pet-turnin（恐龍：解散逐人 pet_turnin；卡坦：隊長交一次）；卡坦第 1 輪交完讀步號 = 2 才算
    drop[N]     （--confirm-drop）petdrop.py all <獎勵寵> --confirm-name <獎勵寵> --max-level 1（恐龍 布克布克；卡坦第 1 輪 修寶）
    store_reward（卡坦）獎勵朵拉比斯（Lv1）5 人存個人倉庫
    restore     pet.py take-many --depot personal --plan "角色:朵拉比斯@原等級" → 朵拉比斯 5 人出戰 → pet_catch.py --lock 戰寵 --battle-pet 朵拉比斯（讀回）
                → ass.py pet all normal 攻擊 --no-resume（一般動作 = 攻擊、讀回）→ pet.py list 驗 5 人朵拉比斯出戰且等級 = 原等級
  猜謎三兄弟 3003（使用者 2026-10-12 / 10-13 做法）
    accept      questrun.py run 3003 --after none（步 1 manual → 115；步 2 需練寵 → 155；0 = 已完成）
    step1       追蹤步號 = 1 才做：quest.py --task 猜謎三兄弟 --stop-after-rewards 1（10-12 / 10-13 點追蹤自動巡到 810 伊那多拿金豬，沒爬塔）
                → pet.py list 驗 5 人都有金布伊；沒有 → 161（爬塔備援 quiztower.py，人工確認）
    prep        關遇敵 → pet.py list 記原戰寵（朵拉比斯）等級 → 取消鎖定戰寵 → 金布伊 5 人出戰 → pet_catch.py --lock 戰寵 --battle-pet 金布伊
    train       grind.py start --spot 地雷區 → petwatch.py --pet 金布伊 --level 77 --back 朵拉比斯 --exp-fruit（練前 depot_use 吃 2倍智慧果；到 77 自動換回朵拉比斯 + 重鎖）
    turnin      關遇敵 → questrun.py run 3003 --after none（交金豬 → 會員證 → 藍暴）
    drop        （--confirm-drop）petdrop.py all 左迪洛斯 --confirm-name 左迪洛斯 --max-level 1
    restore     pet_catch.py --lock 戰寵 --battle-pet 朵拉比斯 → ass.py pet all normal 攻擊 --no-resume → pet.py list 驗朵拉比斯出戰、等級 ≥ 原等級（練功中可能升級）
  不做：恢復掛機（交給呼叫端 / postrebirth 收尾的 grind.py start）。

退出碼（共用 0 / 1 / 2 / 8 / 9 / 10 見 uikit；petquest 自己 160～169）：
  160 參數錯 / 任務 ID 不支援 / 進度不一致（例：restore 要原等級但進度檔沒有）
  161 接取失敗（questrun 非預期退出碼）/ 猜謎步 1 沒拿到金布伊
  162 準備失敗（關遇敵、解散、讀寵物欄、取消鎖定、存原戰寵、金布伊出戰 / 鎖定）
  163 誘餌不夠且沒給 --confirm-buy-bait / 買可抓捕數失敗（石幣讀不到 / 不夠、「+」按了可抓捕數沒變、扣款不是 50,000、鑽石有變）
  164 抓寵失敗（pet_catch 非 0：14 系別物種選不到、15 register 縮圖矛盾、103 取誘餌 / 設定 / 逾時…）
  165 分配失敗（store-many / take-many 非 0、數量驗不過）
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
import uikit  # noqa: E402

SRC = 'petquest'
ROOT = uikit.ROOT
import logpaths  # noqa: E402
EVENT_LOG = logpaths.p(ROOT / 'notes' / 'quest-events.log')
PROGRESS = logpaths.p(uikit.CACHE / 'petquest.json')

(EXIT_ARGS, EXIT_ACCEPT, EXIT_PREP, EXIT_BAIT, EXIT_CATCH, EXIT_DIST, EXIT_TRAIN, EXIT_TURNIN, EXIT_DROP,
 EXIT_RESTORE) = range(160, 170)
PASS = (uikit.EXIT_UNKNOWN_SCREEN, uikit.EXIT_HALT)                  # 驗證視窗 / 斷線：一律透傳
LEADER = 'DKBO'
ALL_ROLES = ['DKBO', 'DKBO2', 'DKBO3', 'DKBO4', 'DKBO5']
BATTLE_PET = '朵拉比斯'
BAIT_ITEM = 92                     # bag.EXIT_ITEM：誘餌不夠 / 倉庫沒有
PLUS_XY = (1295, 315)              # 外掛捉寵設置「可抓捕數 +」（紅區：只有 --confirm-buy-bait 才點；每按一次 +1、扣 50,000 石幣，2026-10-12 實測）
PLUS_COST = 50000
MONEY_BOX = (250, 5, 700, 40)      # 寵物面板頂部資源列（石幣 x≈335,y≈23，右邊依序鑽石 / 活力 / 聲望；ui/pet.md）—— OCR 框**待實機量**；讀不到就不買
POLL_S = 120.0                     # 練寵讀等級間隔（每次開寵物面板約 15 秒）
TRAIN_MAX_S = 45 * 60              # 練寵最多等這麼久（S5 約 9 分、S6 約 5 分）
PROGRESS_TRUST_S = 24 * 3600
TRAIN_SPOT = '柯奧4F龜洞'
QUIZ_SPOT = '地雷區'
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


def parse_money(lines) -> tuple:
    """寵物面板頂部資源列 OCR 行 [(文字, x, y)] → (石幣, 鑽石)：數字（去逗號）依 x 排序，第一個 = 石幣、第二個 = 鑽石；讀不到 None"""
    nums = []
    for t, x, _y in lines or []:
        for m in re.finditer(r'\d[\d,]*', str(t)):
            v = m.group().replace(',', '')
            if v.isdigit():
                nums.append((x, int(v)))
    nums.sort(key=lambda a: a[0])
    return (nums[0][1] if nums else None), (nums[1][1] if len(nums) > 1 else None)


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

    def money(self) -> tuple:
        """寵物面板頂部資源列 → (石幣, 鑽石)；面板打不開 / 讀不到 → (None, None)"""
        import pet
        import rebirth_pets as rp
        with pet.Session(False, True) as s:
            if s.rc:
                return None, None
            return parse_money(rp.ocr_lines(MONEY_BOX, '-Zooms', '2,3'))

    def press_plus(self, role) -> tuple:
        """外掛 → 選角色 → 捉寵設置 → 讀可抓捕數 → 點「+」一次 → 讀回 → 關面板 → (rc, 按前, 按後)。
        按前讀不到可抓捕數 → 不點。**紅區按鈕**：只有 petquest --confirm-buy-bait 的 buy_plus 會呼叫"""
        import ass
        import rebirth_pets as rp
        rt = rp.Tools()
        rc = rt._ass_open(role, 'catch')
        try:
            if rc:
                return rc, None, None
            read = lambda: rp.parse_count(''.join(t for t, _, _ in rp.ocr_lines(rp.OCR_TAB_CATCH, '-Zooms', '2,3,4')))   # noqa: E731
            before = read()
            if before is None or not ass.panel_open():
                return EXIT_BAIT, before, None
            uikit.gui('seq', f'click {PLUS_XY[0]} {PLUS_XY[1]}; wait 800', note=f'petquest {role} 捉寵設置「+」買 1 個可抓捕數（--confirm-buy-bait）')
            after = read()
            return 0, before, after
        finally:
            try:
                ass.close_panel()
            except Exception:                                          # noqa: BLE001
                pass


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

    def pet_list(self, roles=ALL_ROLES, cand=None) -> tuple:
        args = ['list', '--role', 'all' if list(roles) == ALL_ROLES else ','.join(roles), '--json']
        if cand:
            args += ['--candidates', cand]
        rc, lines = self.sub('pet.py', args, 600)
        d = last_json(lines)
        return rc, (d.get('roles') or {})

    # -- 段 --
    def s_accept(self) -> int:
        rc, _ = self.sub('questrun.py', ['run', self.qid, '--after', 'none'], 4 * 3600)
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
        """外掛「+」買 n 個可抓捕數（每按一次前後讀石幣：要剛好少 PLUS_COST、鑽石不變，否則停）"""
        for i in range(n):
            s0, d0 = self.T.money()
            if s0 is None:
                return self.fail(EXIT_BAIT, f'{role} 買可抓捕數前讀不到石幣（寵物面板頂部，MONEY_BOX 待實機量）→ 不按「+」')
            if s0 < PLUS_COST:
                return self.fail(EXIT_BAIT, f'石幣 {s0} 不夠 {PLUS_COST} → 不買')
            rc, before, after = self.T.press_plus(role)
            if rc:
                return self.pass_or(rc, EXIT_BAIT, f'{role} 外掛「+」失敗 rc={rc}（按前可抓捕數 {before}）')
            if after != (before or 0) + 1:
                return self.fail(EXIT_BAIT, f'{role}「+」按了可抓捕數 {before} → {after}（不是 +1）→ 停手')
            s1, d1 = self.T.money()
            self.info.setdefault('bought', []).append({'role': role, 'stone': [s0, s1], 'diamond': [d0, d1]})
            if s1 != s0 - PLUS_COST:
                return self.fail(EXIT_BAIT, f'{role}「+」後石幣 {s0} → {s1}（不是剛好扣 {PLUS_COST}）→ 停手（可能扣了別的貨幣）')
            if d0 is not None and d1 is not None and d1 != d0:
                return self.fail(EXIT_BAIT, f'{role}「+」後鑽石 {d0} → {d1} 有變 → 停手（鐵則 3）')
            event(f'{role} 買可抓捕數 1 個（第 {i + 1}/{n}）：石幣 {s0} → {s1}、可抓捕數 {before} → {after}')
        return 0

    def s_catch(self, stage) -> int:
        if self.p.get('already_done'):
            return 0
        rd, count = self.round_conf(stage), self.q.get('count', 5)
        assign, cand = rd['assign'], species_csv(rd['assign'])
        key = f'caught_{stage}'
        caught = self.p.setdefault(key, 0)                             # 這一輪每人已抓（並存好）幾隻
        if caught >= count:
            return 0
        rc = self.solo(EXIT_CATCH)                                     # 抓寵前一定關遇敵 + 解散（卡坦第 2 輪前 questrun 交完是組隊狀態）
        if rc:
            return rc
        rc, rs = self.pet_list([r for r, _, _ in assign], cand)        # 每批 ≤ 抓寵者寵物欄空格（最少的那人；例：獎勵寵沒丟 → 3 格）
        if rc:
            return self.pass_or(rc, EXIT_CATCH, f'抓前讀寵物欄失敗 pet rc={rc}')
        free = min(free_slots(rs.get(r)) for r, _, _ in assign)
        plan = batches(count - caught, free)
        if not plan:
            return self.fail(EXIT_CATCH, f'抓寵者寵物欄沒有空格（{ {r: free_slots(rs.get(r)) for r, _, _ in assign} }）→ 先存 / 丟寵物', 'uv run --no-project python tools/gui/pet.py list --role all')
        event(f'{stage}：抓寵者寵物欄空格 {free} → 分批 {plan}')
        for bi, k in enumerate(plan):
            last = bi == len(plan) - 1
            rc, lines = self.sub('pet_catch.py', ['--assign', csv_assign(assign), '--count', k, '--stages', 'bait'], 1800)
            if rc and rc != BAIT_ITEM:
                return self.pass_or(rc, EXIT_CATCH, f'取誘餌失敗 pet_catch rc={rc}', f'uv run --no-project python tools/gui/pet_catch.py --assign "{csv_assign(assign)}" --count {k} --stages bait')
            if rc == BAIT_ITEM:
                short = [r for r, _, _ in assign if r not in bait_ok_roles(lines)]
                if not self.o.get('confirm_buy'):
                    return self.fail(EXIT_BAIT, f'公共倉庫誘餌不夠：{short} 各缺 {k} 個（每個可抓捕數用「+」買要 {PLUS_COST} 石幣）→ 沒給 --confirm-buy-bait，停手',
                                     f'確認要買就重跑加 --confirm-buy-bait（或手動補誘餌到公共倉庫後重跑）')
                for r in short:
                    rc = self.buy_plus(r, k)
                    if rc:
                        return rc
            rc, _ = self.sub('pet_catch.py', ['--assign', csv_assign(assign), '--count', k, '--stages', 'setup,wait,register'], 3600)
            if rc:
                return self.pass_or(rc, EXIT_CATCH, f'抓寵失敗 pet_catch rc={rc}（14 系別 / 物種選不到、15 縮圖矛盾、103 設定 / 逾時）',
                                    f'uv run --no-project python tools/gui/pet_catch.py --assign "{csv_assign(assign)}" --count {k} --stages setup,wait,register')
            n_store = store_after_batch(k, last)
            if n_store:
                pets = ','.join(sp for _, _, sp in assign for _ in range(n_store))
                catchers = ','.join(r for r, _, _ in assign)
                rc, _ = self.sub('pet.py', ['store-many', '--role', catchers, '--pets', pets, '--depot', 'public', '--pick', 'last', '--skip-missing',
                                            '--candidates', cand], 1800)
                if rc:
                    return self.pass_or(rc, EXIT_DIST, f'抓寵者存公共倉庫失敗 pet rc={rc}', f'uv run --no-project python tools/gui/pet.py store-many --role {catchers} --pets {pets} --depot public --pick last --skip-missing --candidates {cand}')
            rc, rs = self.pet_list([r for r, _, _ in assign], cand)
            if rc:
                return self.pass_or(rc, EXIT_CATCH, f'抓完讀寵物欄失敗 pet rc={rc}')
            keep = 1 if last else 0
            bad = {r: count_species(rs.get(r), sp) for r, _, sp in assign if count_species(rs.get(r), sp) != keep}
            if bad:
                return self.fail(EXIT_DIST, f'第 {bi + 1} 批後抓寵者寵物欄隻數不對（應各 {keep}）：{bad}（沒存完 / 多抓 / 有寵物進了個人倉庫？）',
                                 'uv run --no-project python tools/gui/pet.py list --role all，人工整理後 --from distribute 續跑')
            caught += k
            self.p[key] = caught
            self.save()
            event(f'{stage}：第 {bi + 1}/{len(plan)} 批抓 {k} 隻完成（累計每人 {caught}）')
        return 0

    def s_distribute(self, stage) -> int:
        if self.p.get('already_done'):
            return 0
        assign = self.round_conf(stage)['assign']
        cand = species_csv(assign)
        plan = ','.join(f'{r}:{sp}' for r, sp in take_plan(assign))
        rc, _ = self.sub('pet.py', ['take-many', '--depot', 'public', '--plan', plan, '--candidates', cand], 3600)
        if rc:
            return self.pass_or(rc, EXIT_DIST, f'公共倉庫分配 take-many 失敗 pet rc={rc}', f'uv run --no-project python tools/gui/pet.py take-many --depot public --plan "{plan}" --candidates {cand}')
        rc, rs = self.pet_list(ALL_ROLES, cand)
        if rc:
            return self.pass_or(rc, EXIT_DIST, f'分配後讀寵物欄失敗 pet rc={rc}')
        miss = missing_pets(rs, [sp for _, _, sp in assign])
        if miss:
            return self.fail(EXIT_DIST, f'分配後每人每物種不是剛好 1 隻：{miss}', 'uv run --no-project python tools/gui/pet.py list --role all --candidates ' + cand)
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
        while True:
            self.T.sleep(POLL_S)
            rc, rs = self.pet_list(ALL_ROLES, cand)
            if rc in PASS:
                return rc
            ok, lag = train_status(rs, rd['need']) if not rc else (False, {'讀取失敗': rc})
            event(f'{stage}：練寵進度 未達標 {lag}' if lag else f'{stage}：5 人任務寵全部達標')
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
        return 0

    def train_quiz(self) -> int:
        q = self.q
        rc, _ = self.sub('grind.py', ['start', '--spot', QUIZ_SPOT], 1800)
        if rc:
            return self.pass_or(rc, EXIT_TRAIN, f'grind start {QUIZ_SPOT} 失敗 rc={rc}', f'uv run --no-project python tools/gui/grind.py start --spot {QUIZ_SPOT}')
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
        if rc:
            return self.pass_or(rc, EXIT_ACCEPT, f'步 1（巡到 810 伊那多拿金豬）quest.py rc={rc}',
                                '點追蹤沒直接巡到 810 時改爬塔：uv run --no-project python tools/gui/quiztower.py run（答題前人工確認）')
        rc, rs = self.pet_list()
        if rc:
            return self.pass_or(rc, EXIT_ACCEPT, f'步 1 後讀寵物欄失敗 pet rc={rc}')
        miss = [r for r in ALL_ROLES if not count_species(rs.get(r), pet)]
        if miss:
            return self.fail(EXIT_ACCEPT, f'步 1 後 {miss} 沒有{pet}', 'uv run --no-project python tools/gui/pet.py list --role all；沒拿到就人工處理（爬塔 quiztower.py）')
        return 0

    def s_turnin(self, stage) -> int:
        if self.p.get('already_done'):
            return 0
        if self.q['kind'] == 'quiz':
            rc = self.encounter_off()
            if rc:
                return rc
            rc, _ = self.sub('questrun.py', ['run', self.qid, '--after', 'none'], 3600)
            return 0 if not rc else self.pass_or(rc, EXIT_TURNIN, f'交金豬 questrun rc={rc}', f'uv run --no-project python tools/gui/questrun.py run {self.qid} --after none')
        rounds = self.q['rounds']
        r = stage_round(stage)
        last = r == len(rounds)
        rc, _ = self.sub('questrun.py', ['run', self.qid, '--after', 'none', '--pet-turnin'], 3600)
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
            plan = ','.join(f'{r}:{BATTLE_PET}@{orig[r]}' for r in ALL_ROLES)
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
        print(f'  train    grind.py start --spot {QUIZ_SPOT} → petwatch.py --pet {q["pet"]} --level {q["level"]} --back {BATTLE_PET} --exp-fruit')
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
                  f' → [誘餌不夠且 --confirm-buy-bait：外掛「+」買 k 次，每次讀石幣扣 {PLUS_COST}] → --stages setup,wait,register'
                  f' → pet.py store-many（抓寵者存公共，最後一批留 1）→ list 驗')
            print(f'  distribute{sfx} pet.py take-many --depot public --plan "{",".join(f"{r}:{sp}" for r, sp in take_plan(a))}" --candidates {species_csv(a)} → list 驗每人每物種 1 隻')
            print(f'  train{sfx}   autoswap on → set-state-many {a[0][2]} 出戰 → verify-battle → grind.py start --spot {TRAIN_SPOT} → 每 {POLL_S:.0f} 秒 list 讀等級（門檻 {rd["need"]}）'
                  f' → 關遇敵 → autoswap off → rest-all')
            print(f'  turnin{sfx}  questrun.py run {qid} --after none --pet-turnin' + ('（下一輪前讀步號要進到下一步）' if i < len(q['rounds']) else '（預期 0）'))
            if rd.get('drop'):
                print(f'  drop{sfx}    petdrop.py all {rd["drop"]} --confirm-name {rd["drop"]} --max-level 1（要 --confirm-drop）')
        if q.get('store_reward'):
            print(f'  store_reward pet.py store-many --role all --pets {q["store_reward"]} --depot personal（獎勵 Lv1）')
        print(f'  restore  pet.py take-many --depot personal --plan "角色:{BATTLE_PET}@原等級" → set-state-many {BATTLE_PET} 出戰 → pet_catch --lock 戰寵 → ass.py pet all normal 攻擊 --no-resume → list 驗')
    print('退出碼：160 參數 161 接取 162 準備 163 誘餌 / 買 164 抓 165 分配 166 練 167 交 168 丟 169 換回；9 驗證視窗 10 斷線')


def run(qid, tools=None, confirm_buy: bool = False, confirm_drop: bool = False, from_stage: str | None = None, to_stage: str | None = None,
        fresh: bool = False, dry_run: bool = False) -> int:
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
    o = dict(confirm_buy=confirm_buy, confirm_drop=confirm_drop, fresh=fresh)
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
    ap.add_argument('--dry-run', action='store_true')
    a = ap.parse_args(argv)
    if a.cmd == 'run' and not a.dry_run:
        import winenv
        winenv.enable_server()
    rc = run(a.qid, confirm_buy=a.confirm_buy_bait, confirm_drop=a.confirm_drop, from_stage=a.from_stage, to_stage=a.to_stage,
             fresh=a.fresh, dry_run=a.cmd == 'plan' or a.dry_run)
    if a.cmd == 'run' and not a.dry_run:
        print(json.dumps(LAST, ensure_ascii=False, default=str))
    return rc


if __name__ == '__main__':
    sys.exit(main())
