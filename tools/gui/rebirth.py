#!/usr/bin/env python3
"""漆黑洞窟轉生任務（任務組 2004 一轉、2005 二轉、2006 三轉、2007 四轉、2008 五轉；結構相同）一行跑完。只用標準函式庫。

**實機驗證狀態（2026-10-11 寫成時）**：流程取自 2004 一轉實跑（notes/quest-log.md 2004 段）。quest / team / char / heal / ass 的呼叫都是既有已驗證工具；
**bag.py / petdrop.py（讀等級、找道具、使用龍王的守護、穿弓丟舊武器、公共倉庫取出 / 存入、丟烏力斯坦）是新寫的，實機完全沒驗證**，
離線測試只驗流程與防護（test_rebirth.py）。第一次實跑請在旁邊看。
**三轉實跑（2026-10-13 21:26～21:47）寫回的修正**：preflight 先關原地遇敵（EXP 橫幅擋讀字）；team.form 非 0 先 team.check（42 但其實滿 5 人）；
boss10 / bow16 進度一律看地圖（boss10 回 37「戰鬥 0」仍以 11F 以上為勝；bow16 給弓沒算到獎勵、一路打完 20F 回 37 → 人在 21F 就記 boss20_done，
swap 後 heal / boss20 跳過直接 rebirth）。這三項只有離線測試。

用法（專案根目錄；WSL / Windows 原生相同）：
  uv run --no-project python tools/gui/rebirth.py [--trans N] [--from 階段] [--dry-run] [--keep-old-weapon] [--confirm-rebirth] [--pet-action 忠犬|攻擊|防禦|none]
    --trans N        這次要轉到第 N 轉（預設 = 目前轉數 + 1；從 preflight 以外階段續跑時用上次進度檔的 N，沒有就要明講）
                     任務組 = 2004 + N - 1；等級門檻 N=1～4 為 131、N=5 為 140（knowledge/quests/tasks.md）
    --from 階段      從這個階段開始（中斷後接著做）：preflight accept enter boss10 bow16 swap heal boss20 rebirth cleanup；--to 階段 = 跑到該階段（含）就停
    --dry-run        只印計畫（階段 / 要跑的指令 / 退出碼），完全不碰遊戲
    --keep-old-weapon 換弓後不丟舊武器
    --confirm-rebirth 精靈王轉生頁確認是「角色轉生」後停下（退出碼 89，對話框維持開著）等人；預設不停直接轉（使用者 2026-10-11：不用停）
    --pet-action 值  換弓後把 5 人戰寵「一般動作」設成這個（預設忠犬；none = 不動）
    --no-dragon      不用龍王的守護
  可 import：rebirth.run(trans=None, from_stage='preflight', dry_run=False, ..., tools=None) → 退出碼；結果 dict 在 rebirth.LAST

階段（每階段開始 / 結束都寫 notes/quest-events.log、tools/.cache/rebirth.json；失敗另寫 errlog）：
  preflight 前置檢查：先關原地遇敵（heal.set_encounter(False)，已關不點；練功中 EXP 橫幅會擋讀字）、當前角色 = DKBO、team.form 滿 5 人（form 非 0 → 先 team.check，滿 5 就算）、5 人轉數 / 等級（不再查四大洞窟證明：2026-10-13 find_items 讀字不穩兩次誤判 81；16F 守門人自己收，缺證明卡住由 quest.py 退出碼處理）、
            背包 / 寵物欄空位 ≥ 2、heal 補滿
  accept    接「漆黑洞窟(N轉)」：rebirth_steps.accept_task（先看任務追蹤欄：有精確標題卡片 → 點卡片巡路到村長；沒有 / 不確定才 questdetail.accept：任務詳情標題精確樣板比對 → 傳送瑪麗娜絲村長 → 選單頁左鈕「漆黑洞窟」翻頁 → 「接受」→ 驗進行中；已進行中略過；失敗 97）
  enter     quest.py 點追蹤（--stop-after-dialog，最多 3 輪）→ 吉魯島守門人 → 漆黑 1F（地圖 32001）
  boss10    龍王的守護（背包沒有就從公共倉庫取）→ quest.py 預設模式到 10F BOSS（37 / 38）→ 38 走「被打飛者重打」→ 確認在 11F 以上（32011～32021，地圖為準）
  bow16     龍王的守護 → quest.py --stop-after-rewards 1：11F→16F 守門人收 4 件證明、每人得精靈王之弓（地圖 32016）。
            進度看地圖（bow16_progress）：開始時 / quest 回任何碼（2、9、10 除外）後人在 17～20F = 弓已拿到 → 0；在 21F = 20F 帖拉所伊朵也打完
            （三轉實測：給弓時沒算到獎勵，巡路一路打完回 37）→ after_boss 確認滿 5 人（不滿走被打飛者重打）→ 記 boss20_done → heal / boss20 跳過
  swap      5 人各自：背包選弓 → 穿戴 → 武器格確認是弓 → 丟舊武器（名稱防護；--keep-old-weapon 跳過）；
            武器格本來就是弓（already：上一轉的弓）→ 背包裡 16F 新給的那把是多的，bag.drop_spare_bow 丟掉（--allow-protected，武器格不動，二轉實測要丟）
  heal      （boss20_done → 跳過）heal.py --no-return → ass.py 5 人戰寵一般動作 → 便捷傳送「漆黑20樓」→ team.form
  boss20    （boss20_done → 跳過）龍王的守護 → quest.py 預設模式到 20F 帖拉所伊朵（37 / 38，同上）→ 確認回到 32021:29,57 附近
            便捷傳送落在 32021:31,29（21 樓精靈王旁），BOSS 在上一層 32020:20,9。quest.py 退出碼不是 37 / 38 且人仍在 32021（追蹤沒走回去，如 3 / 19）→
            備援一次：preflight → 在北區（y<50，便捷傳送落點 31,29）先 walk 32021 傳送帶 31,47（同圖傳到 31,53，看座標 y>=50 判斷，逾時 84 backtrack=band；已在南區跳過）→ walk 32021 南出口 28,59（換圖 32020）→ team.check（散了 form）→ walk 32020 20,11 → quest.py --fight --npc auto → after_boss（37 / 38 同上）。
            走不回 / 換圖失敗 → 84（info.backtrack = band / exit / spot）；被打飛者重打（refight）若追蹤把人傳到 21F 也先走回 20F（單人不 team.check）
  rebirth   team.form → quest.py 預設模式（守門人 → 精靈王）→ 39 時 OCR 對話判斷：「角色轉生」才放行（點完成 + quest.py --allow-irreversible 收尾），
            「寵物轉生」/ 讀不到 / 位置不在精靈王旁 → 88；--confirm-rebirth → 89；放行後確認 5 人轉數 = N
  cleanup   丟 5 人轉生獎勵寵（一轉烏力斯坦 / 二轉奇娜：petdrop 名稱 + Lv1；三轉起：rebirth 階段先拍寵物欄快照、這裡 diff 找「剛好 1 隻新出現的 Lv1」，
            名字 + Lv1 驗過才丟，任何不確定 → 98，不碰騎寵 / 戰寵）→ 龍王的守護存回公共倉庫 → 確認原地遇敵關 → 回 DKBO → 寫 notes/quest-log.md 摘要

退出碼（共用 0 / 1 / 2 / 8 / 9 / 10 見 uikit；其他工具 40～79、90～96；rebirth 自己 80～89）：
  80 等級 / 轉數不符（info.levels 看誰）或讀不到等級
  81 保留不用（原「缺四件證明」，2026-10-13 起 preflight 不再檢查）
  82 背包 / 寵物欄空位不足
  83 隊伍 / 當前角色（不是 DKBO、team.form 失敗、補隊失敗）
  84 quest.py 階段沒完成（非預期退出碼 / 地圖不對 / 逾時；info.quest_rc、info.pos）
  85 BOSS 戰輸 / 被打飛者重打失敗 / 隊伍補不滿
  86 背包 / 寵物操作失敗（換弓、丟舊武器、丟烏力斯坦、龍王倉庫取存；info.bag_rc 是 bag.py / petdrop.py 的碼）
  87 補血 / 外掛戰寵動作 / 便捷傳送失敗
  88 精靈王對話不是「角色轉生」（寵物轉生 / 讀不到 / 位置不對），或轉生後驗證轉數沒變
  89 --confirm-rebirth 停下等人
  97 接任務失敗（info.accept_rc = questdetail 退出碼；已完成 / 條件不達標 / 標題對不上都不亂點）
  98 轉生獎勵寵無法確認（三轉起：沒快照 / 0 或多隻候選 / 名字或 Lv 讀不出）→ 一律不丟，人看寵物欄
載入畫面卡住：quest.py 回 43（載入 / 轉場畫面 60 秒）→ 不重登、重跑同一指令（每階段最多 2 次）。
卡住自動重登：任何階段的 quest.py 回 19（自動巡路卡住）/ 42（VS 牌卡死）→ stuckrecover.relogin_team（relogin.py --stuck --confirm，只按已帶入帳密的「登錄」；105 → team.form）→
team.check / form → 重吃龍王 → 重跑同一個 quest.py 指令；每階段最多 2 次（info.relogin_rc 記重登碼），仍卡 / 重登失敗 → 84；重登遇 9 / 10 → 原碼停手。--fight（單人重打）不重登。
驗證視窗（quest 回 2 / uikit 回 9）→ 一律回 9 並停手（鐵則 5）；斷線（netwatch halt）→ 10。
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
import charstate  # noqa: E402
import rebirth_steps  # noqa: E402  接任務 / 轉生獎勵寵（可獨立呼叫的小步驟）
import stuckrecover  # noqa: E402  卡住自動重登（questrun 同一份）
import uikit  # noqa: E402

SRC = 'rebirth'
ROOT = uikit.ROOT
import logpaths  # noqa: E402
EVENT_LOG = logpaths.p(ROOT / 'notes' / 'quest-events.log')
QUEST_LOG = logpaths.p(ROOT / 'notes' / 'quest-log.md')
PROGRESS = logpaths.p(uikit.CACHE / 'rebirth.json')

EXIT_LEVEL, EXIT_ITEMS, EXIT_SPACE, EXIT_TEAM, EXIT_QUEST, EXIT_BOSS, EXIT_BAG, EXIT_SETUP, EXIT_REBIRTH, EXIT_CONFIRM = 80, 81, 82, 83, 84, 85, 86, 87, 88, 89
EXIT_ACCEPT, EXIT_REWARD = rebirth_steps.EXIT_ACCEPT, rebirth_steps.EXIT_REWARD    # 97 接任務失敗 / 98 轉生獎勵寵無法確認（80～89 已用完）

STAGES = ['preflight', 'accept', 'enter', 'boss10', 'bow16', 'swap', 'heal', 'boss20', 'rebirth', 'cleanup']
LEADER = 'DKBO'
ALL_ROLES = ['DKBO', 'DKBO2', 'DKBO3', 'DKBO4', 'DKBO5']
CN = {1: '一', 2: '二', 3: '三', 4: '四', 5: '五'}
CERTS = ['大地的羈絆', '水的戒指', '火的羽毛飾品', '風的鎖']
BOW = '精靈王之弓'
DRAGON = '龍王的守護'
URISTAN = rebirth_steps.REWARD[1]       # 一轉獎勵寵（二轉 奇娜；三轉起用轉生前後寵物欄 diff，見 rebirth_steps）
DRAGON_REEAT_S = 540.0               # 效果約 10 分鐘（2026-10-11 實測）；超過 9 分鐘再吃
SLICE_S = 540                        # quest.py 單次最長秒數（到點回 0 = 逾時，吃新的龍王再繼續）
MAP_1F, MAP_10F, MAP_11F, MAP_16F, MAP_20F, MAP_21F = 32001, 32010, 32011, 32016, 32020, 32021
WIN_21F = (MAP_21F, 29, 57)          # 20F BOSS 贏了傳到 32021:29,57
BOSS20_EXIT = (28, 59)               # 32021 南出口 → 32020:20,10（要在南區 y >= SOUTH_Y 才走得到）
BAND_SPOT = (31, 47)                 # 32021 同圖傳送帶（出口格 28～34,47～49 → 同圖 31,53）；便捷傳送落點 31,29 在北區，要先踩這裡
SOUTH_Y = 50                         # 傳送後 y >= 50 算進南區（同一張地圖 ID，只能看座標）
BAND_POLLS = 8                       # 踩傳送帶後輪詢座標次數（每次 sleep 1 秒）
BOSS20_SPOT = (20, 11)               # 32020 帖拉所伊朵（20,9）旁
KING_Y = 28                          # 精靈王 32021:31,28
LAST: dict = {}


def level_min(n: int) -> int:
    return 140 if n >= 5 else 131


def task_name(n: int) -> str:
    return f'漆黑洞窟({CN[n]}轉)'


def task_group(n: int) -> int:
    return 2004 + n - 1


def pet_names(n: int) -> list:
    one = {1: ['大地守護獸'], 2: ['水的守護獸'], 3: ['火的守護獸'], 4: ['風的守護獸']}
    return one.get(n, ['大地守護獸', '水的守護獸', '火的守護獸', '風的守護獸'])


def near(pos, want, tol: int = 6) -> bool:
    return bool(pos) and pos[0] == want[0] and abs(pos[1] - want[1]) <= tol and abs(pos[2] - want[2]) <= tol


# ---- 純函式（測試直接餵）----
def judge_rebirth_dialog(texts: dict, pos) -> tuple:
    """精靈王對話框文字（quest.read_dialog_texts 的 {'body','buttons','body_ok'}）+ 位置 → ('role'|'pet'|'unknown', 理由)。
    寵物轉生 / 瑪雷菲雅 → pet；內文含「轉生」且含「儀式」或「出生」、且（位置讀得到時）在精靈王旁 32021 y≈28 → role；其他 unknown"""
    flat = ''.join(texts.get('body', []) + texts.get('buttons', [])).replace(' ', '')
    if '寵物轉生' in flat or '瑪雷菲雅' in flat:
        return 'pet', '對話含「寵物轉生」'
    if not texts.get('body_ok'):
        return 'unknown', '讀不到對話內文'
    if '轉生' not in flat or not ('儀式' in flat or '出生' in flat):
        return 'unknown', f'內文沒有角色轉生儀式字樣：{flat[:40]}'
    if pos and not (pos[0] == MAP_21F and abs(pos[2] - KING_Y) <= 8):
        return 'unknown', f'位置 {pos} 不在精靈王旁（32021 y≈{KING_Y}）'
    return 'role', '內文是角色轉生儀式'


def floor_of(pos) -> int | None:
    """座標 → 漆黑洞窟樓層（32001～32021 → 1～21）；不在漆黑 / 讀不到 → None。純函式"""
    if not pos or not (MAP_1F <= pos[0] <= MAP_21F):
        return None
    return pos[0] - MAP_1F + 1


def past_boss10(pos) -> bool:
    """10F BOSS 已打過 = 人在 11F 以上（11～21F；以地圖為準，不看 quest.py 的戰鬥計數，2026-10-13 三轉 boss10 回 37 時「戰鬥 0」）"""
    f = floor_of(pos)
    return f is not None and f >= 11


def bow16_progress(pos) -> str:
    """bow16 階段用地圖判斷進度（純函式）→ 'boss20'（已在 21F = 20F 帖拉所伊朵也打完；bow16 前不會便捷傳送，能到 21F 只有打贏）/
    'bow'（17～20F = 16F 守門人已收證明給弓）/ 'todo'（16F 以下 / 不在漆黑 / 讀不到）"""
    f = floor_of(pos)
    if f == 21:
        return 'boss20'
    if f is not None and f >= 17:
        return 'bow'
    return 'todo'


def missing_members(cards) -> list:
    """切換面板卡片 → 不在隊上的角色名（label 不是隊長 / 隊員）；名字讀不出的回 None 元素"""
    return [c.name for c in cards if c.label not in ('leader', 'member')]


def parse_plan_stage(a: str) -> str | None:
    return a if a in STAGES else None


# ---- 真實工具（測試換成 FakeTools，介面相同）----
class Tools:
    def sleep(self, s):
        uikit.sleep(s)

    def preflight(self):
        return uikit.preflight(SRC)

    def current(self):
        import char
        rc = char.current(True)
        return rc, char.LAST.get('current')

    def char_switch(self, name):
        import char
        return char.switch(name)

    def char_ensure(self, name):
        import char
        return char.ensure(name)

    def team_form(self):
        import team
        return team.form()

    def team_check(self):
        import team
        return team.check(5)

    def team_cards(self):
        import team
        r = team.read_state(True)
        return (r['cards'] if r.get('ok') else None), r.get('err', '')

    def levels(self, roles):
        import bag
        return bag.levels(roles)

    def find_items(self, role, names):
        import bag
        return bag.find_items(role, names)

    def pet_empties(self):
        import pet
        ctx = pet.load_ctx(True)
        out = {}
        with pet.Session(False, True) as s:
            if s.rc:
                return s.rc, out
            for r in pet.role_list('all'):
                rc, slots = pet.list_role(r, ctx)
                if rc:
                    pet.save_ctx(ctx)
                    return rc, out
                out[r] = sum(1 for x in slots if x.get('empty'))
            pet.save_ctx(ctx)
        return 0, out

    def heal(self):
        import heal
        heal.heal_trip('波拉島', True)

    def ass_pet(self, role, action):
        import ass
        return ass.set_pet(role, {'normal': action})

    def teleport20(self):
        import heal
        tab = (259, 432)                                        # 便捷傳送分頁（ui/transfer.md）
        heal.SIG_TAB.setdefault(tab, '185,411,243,174,63')       # 分頁選中橘色（同練級 / 尼斯分頁的規律，未實測）
        return heal.teleport(tab, (790, 248), MAP_21F, '漆黑20樓', want_xy=(31, 29))

    def quest(self, args, timeout=1500):
        """子程序跑 quest.py（它自己管戰鬥鎖 / server）；回 (退出碼, 最後幾行輸出)"""
        cmd = [sys.executable, str(HERE / 'quest.py')] + [str(x) for x in args]
        env = dict(os.environ, PYTHONIOENCODING='utf-8')
        tail = []
        p = subprocess.Popen(cmd, cwd=str(ROOT), stdout=subprocess.PIPE, stderr=subprocess.STDOUT, env=env, text=True, encoding='utf-8', errors='replace')
        t0 = time.time()
        try:
            for ln in p.stdout:
                ln = ln.rstrip()
                print(ln, flush=True)
                tail.append(ln)
                del tail[:-30]
                if time.time() - t0 > timeout:
                    p.kill()
                    break
        finally:
            p.wait()
        return p.returncode, tail

    def read_pos(self):
        import quest
        return quest.read_pos()

    def walk(self, map_id, x, y, exit_map=None):
        """walk.walk_to（有通行格自動找路）；成功回 (地圖, x, y)，丟例外 / 讀不到座標回 None"""
        import walk
        try:
            return walk.walk_to(map_id, x, y, exit_map=exit_map)
        except (RuntimeError, OSError) as e:
            event(f'walk {map_id}:{x},{y} 失敗：{e}')
            return None

    def track(self, task):
        import quest
        quest.ensure_task_tab()
        return quest.track_task(task)

    def dialog_texts(self):
        import quest
        return quest.read_dialog_texts()

    def press_dialog(self):
        import quest
        uikit.gui('seq', f'click {quest.DIALOG_NEXT[0]} {quest.DIALOG_NEXT[1]}; wait 800', note='rebirth 精靈王對話按左鈕（角色轉生）')

    def bag_use(self, role, name):
        import bag
        return bag.use_item(role, name, verify_buff=True), dict(bag.LAST)

    def bag_take(self, role, name):
        import bag
        return bag.depot_take(role, name, 'public')

    def bag_store(self, role, name):
        import bag
        return bag.depot_store(role, name, 'public')

    def swap_weapon(self, role, keep_old):
        import bag
        return bag.swap_weapon(role, BOW, keep_old), dict(bag.LAST)

    def accept(self, n):
        return rebirth_steps.accept_task(n)

    def relogin(self):
        return stuckrecover.real_relogin()

    def pet_snapshot(self):
        """轉生前 5 人寵物欄快照（只在沒有獎勵寵對照表的轉數用）→ (rc, 快照 dict)"""
        rc, pets = rebirth_steps._PetTools().pets(ALL_ROLES)
        return rc, rebirth_steps.snapshot_pets(pets)

    def drop_pet(self, name):
        """對照表內的獎勵寵：名稱完全相同 + Lv1（--max-level 1）才丟，5 人"""
        return rebirth_steps._PetTools().drop('all', name, None)

    def drop_new_lv1(self, n, before):
        """沒有對照表：轉生前後寵物欄 diff（rebirth_steps.drop_rewards）"""
        rc = rebirth_steps.drop_rewards(n, before)
        return rc, dict(rebirth_steps.LAST)

    def encounter_on(self):
        import heal
        return heal.encounter_on()

    def encounter_off(self):
        import heal
        heal.set_encounter(False)

    def snap(self, tag):
        return uikit.snap(tag)


# ---- 紀錄 ----
def event(msg: str) -> None:
    line = f'{time.strftime("%Y-%m-%d %H:%M:%S")} [rebirth] {msg}'
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


class Run:
    def __init__(self, n: int, T, opts: dict):
        self.n, self.T, self.o = n, T, opts
        self.task = task_name(n)
        self.st = load_progress()
        if self.st.get('trans') != n:
            self.st = {'trans': n, 'stages': {}}
        self.st.setdefault('stages', {})
        self.info: dict = {}
        self.warnings: list = []
        self.backtracked = False                        # 32021 走回 32020 的備援只試一次
        self.relogins: dict = {}                        # 階段 → 已自動全員重登次數（每階段最多 stuckrecover.RELOGIN_MAX）
        self.retries: dict = {}                         # 階段 → quest.py 43（載入畫面卡住）已重跑次數（每階段最多 stuckrecover.RELOGIN_MAX）
        self.cur = ''                                   # 目前階段名

    # -- 紀錄 --
    def save(self):
        self.st['info'] = self.info
        self.st['warnings'] = self.warnings
        save_progress(self.st)

    def begin(self, name):
        self.cur = name
        self.st['stages'][name] = {'status': 'running', 't0': time.strftime('%H:%M:%S')}
        event(f'階段 {name} 開始（{self.task}）')
        self.save()

    def end(self, name, rc):
        d = self.st['stages'].setdefault(name, {})
        d.update(status='ok' if rc == 0 else 'fail', rc=rc, t1=time.strftime('%H:%M:%S'))
        event(f'階段 {name} 結束 rc={rc}' + (f' info={json.dumps(self.info, ensure_ascii=False)[:300]}' if rc else ''))
        self.save()

    def fail(self, rc: int, msg: str, **kw) -> int:
        self.info.update(kw)
        self.info['msg'] = msg
        event(f'失敗 rc={rc}：{msg}')
        try:
            import errlog
            errlog.add(f'rebirth：{msg}', source='rebirth')
        except Exception:
            pass
        return rc

    def warn(self, msg: str):
        self.warnings.append(msg)
        event(f'警告：{msg}')

    # -- 共用步驟 --
    def quest(self, args, timeout=1500):
        """跑 quest.py。回 19（巡路卡住）/ 42（VS 牌卡死）→ 全員重登後重跑同一指令（每階段最多 2 次，stuckrecover）；--fight（單人重打）不重登。
        重登失敗 → 回原退出碼（階段 84，info.relogin_rc）；重登遇驗證視窗 / 斷線 → 回 9 / 10（一律停手）"""
        recoverable = getattr(self.T, 'relogin', None) is not None and '--fight' not in args
        while True:
            event('quest.py ' + ' '.join(str(a) for a in args))
            rc, tail = self.T.quest(args, timeout)
            self.info['quest_rc'] = rc
            event(f'quest.py 退出碼 {rc}')
            if stuckrecover.is_retry(rc) and stuckrecover.allowed(self.retries.get(self.cur, 0)):   # 43 載入畫面卡住：不重登，重跑同一指令
                self.retries[self.cur] = self.retries.get(self.cur, 0) + 1
                event(f'{self.cur}：quest.py 43 載入畫面卡住 → 重跑同一指令（第 {self.retries[self.cur]}/{stuckrecover.RELOGIN_MAX} 次）')
                continue
            if not (recoverable and stuckrecover.is_stuck(rc) and stuckrecover.allowed(self.relogins.get(self.cur, 0))):
                return rc, tail
            n = self.relogins[self.cur] = self.relogins.get(self.cur, 0) + 1
            rr = self.relogin_recover(rc, n)
            if rr:
                self.info['relogin_rc'] = rr
                return (rr if rr in stuckrecover.HALT_RC else rc), tail

    def relogin_recover(self, rc: int, n: int) -> int:
        """quest.py 卡住 → 全員重登（登入畫面只按已帶入帳密的「登錄」，鐵則 2）→ team.check / form → 重吃龍王。回 0 = 可重跑同階段；否則退出碼"""
        T = self.T
        event(f'{self.cur}：quest.py 退出碼 {rc}（巡路卡住 / VS 牌卡死）→ 全員重登 relogin.py --stuck --confirm（第 {n}/{stuckrecover.RELOGIN_MAX} 次）')
        status, code = stuckrecover.relogin_team(T.relogin, T.team_form, event)
        if status != 'ok':
            event(f'{self.cur}：重登失敗 {status} rc={code}')
            return code or 1
        rc2 = T.team_check()
        if rc2:
            event(f'{self.cur}：重登後 team.check rc={rc2} → team.form')
            rc2 = T.team_form()
            if rc2:
                event(f'{self.cur}：重登後 team.form 失敗 rc={rc2}')
                return rc2
        self.st.pop('last_eat', None)                          # 重登後 buff 狀態不明 → 下一次 ensure_dragon 重吃
        self.ensure_dragon(force=True)
        return 0

    def quest_stop(self, rc, where: str):
        """quest 非預期退出碼 → 本階段退出碼（2 = 疑似驗證視窗 → 9，鐵則 5）"""
        if rc == 2:
            return self.fail(uikit.EXIT_UNKNOWN_SCREEN, f'{where}：quest.py 看到不認得的畫面（疑似驗證視窗），停手通知使用者', quest_rc=rc)
        if rc in stuckrecover.HALT_RC:                           # 自動重登遇驗證視窗 / 斷線（9 / 10）：原碼透傳
            return self.fail(rc, f'{where}：自動重登時{"看到驗證視窗" if rc == 9 else "斷線"}，停手', quest_rc=rc)
        return self.fail(EXIT_QUEST, f'{where}：quest.py 非預期退出碼 {rc}', quest_rc=rc)

    def ensure_dragon(self, force: bool = False):
        """隊長吃龍王的守護（背包沒有就從公共倉庫取）。失敗只警告（沒有也能跑，只是遇敵）；10 分鐘內不重吃"""
        if not self.o.get('dragon', True):
            return
        now = time.time()
        if not force and now - self.st.get('last_eat', 0) < DRAGON_REEAT_S:
            return
        rc, d = self.T.bag_use(LEADER, DRAGON)
        if rc == 92:                                           # 背包沒有 → 公共倉庫
            event('背包沒有龍王的守護，從公共倉庫取出')
            r2 = self.T.bag_take(LEADER, DRAGON)
            if r2:
                self.info['bag_rc'] = r2
                self.warn(f'龍王的守護取出失敗（bag rc {r2}），這段不用龍王')
                return
            self.st['dragon_taken'] = True
            rc, d = self.T.bag_use(LEADER, DRAGON)
        if rc:
            self.info['bag_rc'] = rc
            self.warn(f'龍王的守護使用失敗（bag rc {rc}），這段不用龍王')
            return
        self.st['last_eat'] = time.time()
        self.st['dragon_used'] = self.st.get('dragon_used', 0) + 1
        if d.get('buff') is False:
            self.warn('吃了龍王的守護但沒看到 buff 圖示（偵測特徵只有單張樣本，不一定是失敗）')
        event(f'已吃龍王的守護（第 {self.st["dragon_used"]} 顆）')
        self.save()

    def read_pos(self):
        return self.T.read_pos()

    def form(self) -> int:
        """team.form。回 9（uikit.preflight 畫面連 3 次不認得）時等 20 秒只重試一次：二轉 22:20 剛打完 BOSS 回 9、16 秒後原指令就過（過場 / 結算畫面暫時認不得，非驗證視窗）；
        真的驗證視窗會一直在 → 第 2 次仍 9 就停手（鐵則 5）。重試期間不點任何東西（preflight 只讀）"""
        rc = self.T.team_form()
        if rc == uikit.EXIT_UNKNOWN_SCREEN:
            event('team.form 回 9（畫面連 3 次不認得）→ 等 20 秒只讀重試一次（過場畫面可能；驗證視窗不會自己消失）')
            self.T.sleep(20)
            rc = self.T.team_form()
        elif rc:                                                  # 2026-10-13 三轉 preflight：form 回 42 但 team.py status 其實滿 5 人（讀卡片那一下被橫幅 / 過場擋）
            event(f'team.form 回 {rc} → 等 3 秒先 team.check（唯讀；滿 5 人就算數），不滿才再 form 一次')
            self.T.sleep(3)
            if self.T.team_check() == 0:
                event('team.check 滿 5 人 → 視為組隊成功')
                return 0
            rc = self.T.team_form()
        return rc

    # -- BOSS 後處理 --
    def after_boss(self, name: str, won, boss_map: int) -> int:
        pos = self.read_pos()
        self.info['pos'] = pos
        if not won(pos):
            return self.fail(EXIT_BOSS, f'{name}：BOSS 戰後位置 {pos} 不是勝利落點（沒贏？），不往下', pos=pos)
        rc = self.T.team_check()
        if rc == 0:
            return 0
        event(f'{name}：BOSS 戰後 team.check rc={rc}，隊伍不滿 → 找被打飛的人重打')
        return self.fix_team(name, won, boss_map)

    def fix_team(self, name: str, won, boss_map: int) -> int:
        cards, err = self.T.team_cards()
        if cards is None:
            return self.fail(EXIT_BOSS, f'{name}：讀不到隊伍狀態：{err}')
        miss = missing_members(cards)
        if not miss or any(m is None for m in miss):
            return self.fail(EXIT_BOSS, f'{name}：不滿 5 人但找不出被打飛的人（不在隊名單 {miss}）', missing=miss)
        self.info['missing'] = miss
        event(f'{name}：不在隊上 {miss}')
        for who in miss:
            rc = self.refight(name, who, won, boss_map)
            self.T.char_ensure(LEADER)                         # 不論成敗都切回隊長
            if rc:
                return rc
        rc = self.form()
        if rc:
            return self.fail(EXIT_TEAM, f'{name}：重打後 team.form 失敗 rc={rc}')
        rc = self.T.team_check()
        if rc:
            return self.fail(EXIT_BOSS, f'{name}：重打後隊伍仍不滿 5 人（team.check rc={rc}）')
        return 0

    def refight(self, name: str, who: str, won, boss_map: int) -> int:
        """被打飛者：char.switch 當單人隊長 → 點任務追蹤自動傳送 → quest.py --fight 重打 → 確認落點"""
        rc = self.T.char_switch(who)
        if rc:
            return self.fail(EXIT_TEAM, f'{name}：切到 {who} 失敗 rc={rc}')
        pos = self.read_pos()
        if won(pos):
            event(f'{name}：{who} 已在勝利落點 {pos}，不用重打')
            return 0
        res = self.T.track(self.task)
        if not res:
            return self.fail(EXIT_BOSS, f'{name}：{who} 點任務追蹤沒成功（{res}）')
        arrive_maps = {boss_map} | ({MAP_21F} if boss_map == MAP_20F else set())   # 20F BOSS：追蹤可能把人傳到 21F
        arrived, last = 0, None
        for _ in range(60):
            self.T.sleep(3)
            p = self.read_pos()
            if p and p[0] in arrive_maps and p == last:
                arrived += 1
                if arrived >= 2:
                    break
            else:
                arrived = 0
            last = p
        else:
            return self.fail(EXIT_BOSS, f'{name}：{who} 傳送 / 巡路後沒到 BOSS 地圖 {boss_map}（最後位置 {last}）')
        if last and last[0] == MAP_21F and boss_map == MAP_20F:
            self.backtracked = False                            # 每個被打飛者各自可備援一次
            rc = self.walk_back_20f(f'{name}/{who}', team=False)
            if rc:
                return rc
        rc, _ = self.quest(['--fight', '--task', self.task, '--npc', 'auto', '--step', 4 if boss_map == MAP_20F else 2, '--team-size', '1', '--max-seconds', '300'], 400)   # --step 明講：不靠追蹤文字 OCR（二轉 22:15 回 31）
        if rc == 2:
            return self.quest_stop(rc, f'{who} 重打')
        if rc:
            return self.fail(EXIT_BOSS, f'{name}：{who} 重打 quest.py --fight 退出碼 {rc}（0 才是贏）', fight_rc=rc)
        pos = self.read_pos()
        if not won(pos):
            return self.fail(EXIT_BOSS, f'{name}：{who} 重打後位置 {pos} 不是勝利落點')
        event(f'{name}：{who} 重打贏了 {pos}')
        return 0

    def walk_back_20f(self, name: str, team: bool = True) -> int:
        """人在 32021（便捷傳送 / 巡路落在精靈王旁）→ 往回走：南出口 28,59 換圖 32020 → 20,11（BOSS 旁）。
        成功回 0；失敗回 84（info.backtrack 記哪一步）；preflight 非 0 原碼回傳。同一 Run 只試一次（self.backtracked）"""
        if self.backtracked:
            return self.fail(EXIT_QUEST, f'{name}：已備援過一次走回 32020，不再重試', pos=self.read_pos())
        self.backtracked = True
        event(f'{name}：人在 32021，往回走：傳送帶 {BAND_SPOT}（→ 南區 y>={SOUTH_Y}）→ 南出口 {BOSS20_EXIT} → 32020 {BOSS20_SPOT}')
        rc = self.T.preflight()
        if rc:
            return rc
        pos = self.read_pos()
        if not (pos and pos[0] == MAP_21F and pos[2] >= SOUTH_Y):      # 已在南區（BOSS 戰後落點 29,57 等）跳過第 1 段
            r = self.T.walk(MAP_21F, BAND_SPOT[0], BAND_SPOT[1])
            for _ in range(BAND_POLLS):
                pos = self.read_pos()
                if pos and pos[0] == MAP_21F and pos[2] >= SOUTH_Y:
                    break
                self.T.sleep(1)
            else:
                return self.fail(EXIT_QUEST, f'{name}：走到傳送帶 {BAND_SPOT}（{r}）後座標沒進南區 y>={SOUTH_Y}（{pos}）', backtrack='band', pos=pos)
        rc = self.T.preflight()
        if rc:
            return rc
        r = self.T.walk(MAP_21F, BOSS20_EXIT[0], BOSS20_EXIT[1], exit_map=MAP_20F)
        if not r or r[0] != MAP_20F:
            return self.fail(EXIT_QUEST, f'{name}：走 32021 南出口沒換到 32020（{r}）', backtrack='exit', pos=self.read_pos())
        if team:
            rc = self.T.team_check()
            if rc:
                event(f'{name}：換圖後 team.check rc={rc}，team.form')
                rc = self.form()
                if rc:
                    return self.fail(EXIT_TEAM, f'{name}：走回 32020 後 team.form 失敗 rc={rc}', backtrack='team')
        rc = self.T.preflight()
        if rc:
            return rc
        r = self.T.walk(MAP_20F, BOSS20_SPOT[0], BOSS20_SPOT[1])
        if not r or r[0] != MAP_20F:
            return self.fail(EXIT_QUEST, f'{name}：走到 32020 {BOSS20_SPOT} 失敗（{r}）', backtrack='spot', pos=self.read_pos())
        return 0

    def backtrack_fight(self, name: str, won, boss_map: int) -> int:
        """備援：走回 32020 → quest.py --fight 點帖拉所伊朵 → 照 37 / 38 處理（after_boss：滿 5 人 / 補人）"""
        rc = self.walk_back_20f(name)
        if rc:
            return rc
        rc, _ = self.quest(['--fight', '--task', self.task, '--npc', 'auto', '--step', 4, '--max-seconds', SLICE_S], SLICE_S + 120)   # 20F BOSS = 第 4 步；--step 明講，不靠追蹤文字 OCR
        if rc == 2:
            return self.quest_stop(rc, f'{name} 備援開打')
        if rc in (0, 37, 38):
            return self.after_boss(name, won, boss_map)
        return self.fail(EXIT_BOSS, f'{name}：備援 quest.py --fight 退出碼 {rc}', fight_rc=rc)

    def boss_stage(self, name: str, won, boss_map: int, slices: int = 3, backtrack: bool = False) -> int:
        for k in range(slices):
            self.ensure_dragon()
            rc, _ = self.quest(['--task', self.task, '--max-seconds', SLICE_S], SLICE_S + 120)
            if rc in (37, 38):
                return self.after_boss(name, won, boss_map)
            pos = self.read_pos()
            if backtrack and rc != 2 and not self.backtracked and pos and pos[0] == MAP_21F and not won(pos):
                event(f'{name}：quest 退出碼 {rc} 但人仍在 32021 {pos}（追蹤沒走回 20F）→ 備援')
                return self.backtrack_fight(name, won, boss_map)
            if rc == 0:
                if won(pos):                                   # 逾時回 0；10F 已到 11F = BOSS 贏了（偵測不到對話後開打的 BOSS）
                    event(f'{name}：quest 回 0 且位置 {pos} 已是勝利落點，視為 BOSS 已打贏')
                    return self.after_boss(name, won, boss_map)
                event(f'{name}：第 {k + 1} 段 {SLICE_S}s 到了還沒打完 BOSS（位置 {pos}），再吃龍王繼續')
                self.ensure_dragon(force=True)
                continue
            return self.quest_stop(rc, name)
        return self.fail(EXIT_QUEST, f'{name}：跑了 {slices} 段仍沒打到 BOSS（逾時）', pos=self.read_pos())

    # ---- 階段 ----
    def s_preflight(self) -> int:
        T = self.T
        rc = T.preflight()
        if rc:
            return rc
        try:                                                    # 練功中接著跑：EXP 橫幅會擋背包 / 等級讀字（2026-10-13 三轉），先關原地遇敵（已關就不點）
            T.encounter_off()
        except RuntimeError as e:
            return self.fail(EXIT_SETUP, f'preflight 關原地遇敵失敗：{e}')
        T.sleep(3)                                              # 正在打的那場打完、橫幅消失
        rc, cur = T.current()
        if rc or not cur or not charstate.same(cur, LEADER):
            return self.fail(EXIT_TEAM, f'當前角色不是 {LEADER}（讀到 {cur}，rc {rc}）；判斷看面板左欄頭像紅字「當前登錄」', current=cur)
        rc = self.form()
        if rc:
            return self.fail(EXIT_TEAM, f'team.form 沒成功 rc={rc}（要滿 5 人）')
        rc, lv = T.levels(ALL_ROLES)
        if rc:
            return self.fail(EXIT_LEVEL, f'讀等級失敗 bag rc={rc}', bag_rc=rc)
        self.info['levels'] = {r: list(v) if v else None for r, v in lv.items()}
        bad = {r: v for r, v in lv.items() if not v or v[0] != self.n - 1 or v[1] < level_min(self.n)}
        if bad:
            return self.fail(EXIT_LEVEL, f'要「{self.n - 1}轉 ≥{level_min(self.n)} 級」才能做 {self.task}；不符 / 讀不到：{bad}', bad=bad)
        space = {}
        for r in ALL_ROLES:
            rc, it = T.find_items(r, [])        # 只讀空格數；不查四大洞窟證明（2026-10-13：讀字不穩誤判 81）
            if rc:
                return self.fail(EXIT_SPACE, f'{r} 讀背包空格失敗 bag rc={rc}', bag_rc=rc)
            space[r] = it.get('_free')
        self.info['bag_free'] = space
        short = {r: v for r, v in space.items() if v is not None and v < 2}
        rc, pe = T.pet_empties()
        if rc:
            return self.fail(EXIT_SPACE, f'讀寵物欄失敗 pet rc={rc}', pet_rc=rc)
        self.info['pet_empty'] = pe
        pshort = {r: v for r, v in pe.items() if v < 2}
        if short or pshort:
            return self.fail(EXIT_SPACE, f'空位不足（要各 ≥2）：背包 {short}、寵物欄 {pshort}', bag_short=short, pet_short=pshort)
        try:
            T.heal()
        except RuntimeError as e:
            return self.fail(EXIT_SETUP, f'補血失敗：{e}')
        return 0

    def s_accept(self) -> int:
        """接「漆黑洞窟(N轉)」（rebirth_steps.accept_task：任務詳情精確標題 → 傳送村長 → 選單頁翻頁 → 接受 → 驗進行中；已進行中跳過）"""
        rc = self.T.accept(self.n)
        if rc in stuckrecover.HALT_RC:
            return self.fail(rc, f'接任務：{"看到驗證視窗" if rc == 9 else "斷線"}，停手')
        if rc:
            return self.fail(EXIT_ACCEPT, f'接「{self.task}」失敗（rc {rc}；見 questdetail 紀錄 / snap）', accept_rc=rc)
        return 0

    def s_enter(self) -> int:
        for k in range(3):
            pos = self.read_pos()
            if pos and pos[0] == MAP_1F:
                event(f'已在漆黑 1F {pos}')
                return 0
            rc, _ = self.quest(['--task', self.task, '--stop-after-dialog', '--max-seconds', 240], 360)
            if rc not in (0, 24):
                return self.quest_stop(rc, 'enter')
        pos = self.read_pos()
        self.info['pos'] = pos
        if pos and pos[0] == MAP_1F:
            return 0
        return self.fail(EXIT_QUEST, f'enter：3 輪後仍不在漆黑 1F（{pos}）', pos=pos)

    def s_boss10(self) -> int:
        return self.boss_stage('boss10', past_boss10, MAP_10F)   # 勝利 = 11F 以上（地圖為準；quest.py 37 的「戰鬥 N」計數不可靠）

    def s_bow16(self) -> int:
        """16F 守門人收證明給弓。進度以地圖為準（bow16_progress）：2026-10-13 三轉 16F 給弓時 quest.py 沒算到獎勵（--stop-after-rewards 不停），
        一路巡路打完 20F 帖拉所伊朵回 37、人已在 32021 → 舊版當 84。現在：17～20F = 弓已拿到；21F = boss20 也打完（after_boss 確認滿 5 人 /
        補人）→ 記 st['boss20_done']，swap 之後 heal / boss20 直接跳過"""
        self.st.pop('boss20_done', None)
        pos = self.read_pos()
        if bow16_progress(pos) != 'todo':                       # 續跑：已過 16F
            return self.bow16_beyond(pos, None)
        for k in range(2):
            self.ensure_dragon()
            rc, _ = self.quest(['--task', self.task, '--stop-after-rewards', 1, '--max-seconds', SLICE_S], SLICE_S + 120)
            pos = self.read_pos()
            if rc == 2 or rc in stuckrecover.HALT_RC:
                return self.quest_stop(rc, 'bow16')
            if bow16_progress(pos) != 'todo':
                return self.bow16_beyond(pos, rc)
            if rc != 0:
                return self.quest_stop(rc, 'bow16')
            if pos and pos[0] == MAP_16F:
                return 0
            event(f'bow16：quest 回 0 但位置 {pos} 不在 16F（逾時？）再跑一段')
        return self.fail(EXIT_QUEST, 'bow16：沒在 16F 領到精靈王之弓', pos=self.read_pos())

    def bow16_beyond(self, pos, rc) -> int:
        """bow16 時人已過 16F：17～20F → 弓已拿到（回 0，照常 swap → heal → boss20）；21F → 20F BOSS 也打贏了：
        after_boss（勝利 = 在 21F；不滿 5 人走被打飛者重打）→ 記 boss20_done。背包的弓只讀來記錄（find_items 讀字不穩，不當判斷依據；swap 會再驗）"""
        prog = bow16_progress(pos)
        event(f'bow16：quest 退出碼 {rc}、位置 {pos}（{floor_of(pos)}F）→ 已過 16F 守門人（弓已拿到）' + ('，且 20F 帖拉所伊朵已打完' if prog == 'boss20' else ''))
        if prog != 'boss20':
            return 0
        rc2 = self.after_boss('bow16/boss20', lambda p: bool(p) and p[0] == MAP_21F, MAP_20F)
        if rc2:
            return rc2
        r, it = self.T.find_items(LEADER, [BOW])
        self.info['bow_in_bag'] = None if r else it.get(BOW)
        if r or it.get(BOW) is None:
            self.warn(f'{LEADER} 背包沒讀到多的{BOW}（bag rc {r}）；只記錄，swap 階段會再驗')
        self.st['boss20_done'] = True
        self.save()
        event('bow16：20F 已打完 → swap 之後跳過 heal / boss20，直接 rebirth')
        return 0

    def s_swap(self) -> int:
        res = {}
        for r in ALL_ROLES:
            rc, d = self.T.swap_weapon(r, self.o.get('keep_old', False))
            res[r] = {'rc': rc, **{k: v for k, v in d.items() if k in ('old', 'already', 'kept_old', 'dropped', 'spare')}}
            self.info['swap'] = res
            event(f'換弓 {r}：{res[r]}')
            if rc:
                return self.fail(EXIT_BAG, f'{r} 換弓 / 丟舊武器失敗 bag rc={rc}', bag_rc=rc, role=r)
        return 0

    def s_heal(self) -> int:
        T = self.T
        if self.st.get('boss20_done'):
            event('heal：bow16 時已打完 20F（人在 21F）→ 跳過補血 / 戰寵動作 / 便捷傳送')
            return 0
        try:
            T.heal()
        except RuntimeError as e:
            return self.fail(EXIT_SETUP, f'補血失敗：{e}')
        act = self.o.get('pet_action', '忠犬')
        if act and act != 'none':
            for r in ALL_ROLES:
                rc, st, msg = T.ass_pet(r, act)
                if rc == 0:
                    continue
                if rc == 4 and (not st or st.get('normal') is None):
                    self.warn(f'{r} 戰寵一般動作設 {act}：OCR 讀回 None（認不得「{act}」，2026-10-11 實測其實設成功），請事後人眼確認')
                    continue
                return self.fail(EXIT_SETUP, f'{r} 戰寵一般動作 {act} 失敗 ass rc={rc}：{msg}', role=r)
        try:
            T.teleport20()
        except RuntimeError as e:
            return self.fail(EXIT_SETUP, f'便捷傳送漆黑20樓失敗：{e}')
        rc = self.form()
        if rc:
            return self.fail(EXIT_TEAM, f'傳到 20F 後 team.form 失敗 rc={rc}')
        return 0

    def s_boss20(self) -> int:
        if self.st.get('boss20_done'):
            event('boss20：bow16 時已打完 20F 帖拉所伊朵 → 跳過')
            return 0
        return self.boss_stage('boss20', lambda p: near(p, WIN_21F), MAP_20F, backtrack=True)

    def s_rebirth(self) -> int:
        T = self.T
        rc = self.form()
        if rc:
            return self.fail(EXIT_TEAM, f'rebirth：team.form 失敗 rc={rc}')
        if not rebirth_steps.reward_name(self.n) and not self.st.get('pets_before'):    # 沒有獎勵寵對照表 → 轉生前先拍寵物欄快照（cleanup 做 diff）
            rc, snap = T.pet_snapshot()
            if rc:
                return self.fail(EXIT_REWARD, f'轉生前讀寵物欄快照失敗（pet rc {rc}）；沒快照轉生後認不出獎勵寵，先不轉', pet_rc=rc)
            self.st['pets_before'] = snap
            self.save()
            event('轉生前寵物欄快照已存（第 %d 轉沒有獎勵寵對照表，cleanup 用 diff 找新出現的 Lv1 寵物）' % self.n)
        rc, _ = self.quest(['--task', self.task, '--max-seconds', 420], 540)
        if rc != 39:
            if rc == 0 and self.rebirth_done():
                return 0
            return self.quest_stop(rc, 'rebirth（預期停在 39：精靈王轉生頁）')
        texts = T.dialog_texts()
        pos = self.read_pos()
        verdict, why = judge_rebirth_dialog(texts, pos)
        self.info['dialog'] = {'verdict': verdict, 'why': why, 'pos': pos, 'body': texts.get('body'), 'buttons': texts.get('buttons')}
        event(f'精靈王對話判斷：{verdict}（{why}）')
        if verdict != 'role':
            T.snap('rebirth-dialog-' + verdict)
            return self.fail(EXIT_REBIRTH, f'對話不是角色轉生：{why}；沒按任何鈕、對話框維持開著，請人看圖')
        if self.o.get('confirm_rebirth'):
            return self.fail(EXIT_CONFIRM, '--confirm-rebirth：確認是角色轉生頁，停下等人（對話框維持開著；要繼續請不加 --confirm-rebirth 重跑 --from rebirth）')
        T.press_dialog()
        T.sleep(3)
        rc, _ = self.quest(['--task', self.task, '--no-track', '--team-size', 0, '--allow-irreversible', '--max-seconds', 40], 120)
        if rc == 2:
            return self.quest_stop(rc, 'rebirth 收尾')
        return 0 if self.rebirth_done() else self.fail(EXIT_REBIRTH, f'按了完成但 5 人轉數沒到 {self.n}（見 info.levels）')

    def rebirth_done(self) -> bool:
        for k in range(4):
            rc, lv = self.T.levels(ALL_ROLES)
            self.info['levels_after'] = {r: list(v) if v else None for r, v in lv.items()}
            if not rc and all(v and v[0] == self.n for v in lv.values()):
                event(f'轉生確認：5 人 {self.info["levels_after"]}')
                return True
            self.T.sleep(8)
        return False

    def s_cleanup(self) -> int:
        T = self.T
        name = rebirth_steps.reward_name(self.n)
        if name:                                                # 一轉烏力斯坦 / 二轉奇娜：名稱完全相同 + Lv1 才丟
            rc = T.drop_pet(name)
            if rc:
                return self.fail(EXIT_BAG, f'丟{name}失敗 petdrop rc={rc}（沒碰騎寵 / 戰寵）', bag_rc=rc)
        else:                                                   # 三轉起：轉生前後寵物欄 diff，找「剛好 1 隻新出現的 Lv1」，名字 + Lv1 驗過才丟
            rc, d = T.drop_new_lv1(self.n, self.st.get('pets_before'))
            self.info['reward_drop'] = d
            if rc in stuckrecover.HALT_RC:
                return self.fail(rc, '丟轉生獎勵寵時看到驗證視窗 / 斷線，停手')
            if rc:
                return self.fail(EXIT_REWARD if rc == EXIT_REWARD else EXIT_BAG, f'丟轉生獎勵寵失敗 rc={rc}（{d.get("why", "")}；一律沒碰騎寵 / 戰寵）', bag_rc=rc)
        rc = T.bag_store(LEADER, DRAGON)
        if rc not in (0, 92):
            return self.fail(EXIT_BAG, f'{DRAGON}存回公共倉庫失敗 bag rc={rc}', bag_rc=rc)
        self.info['dragon_stored'] = rc == 0
        if T.encounter_on():
            T.encounter_off()
            self.warn('原地遇敵是開的，已關（轉生後維持關閉、不練功）')
        T.char_ensure(LEADER)
        self.write_log()
        return 0

    def write_log(self):
        lines = [f'\n## {task_group(self.n)} {self.task} — rebirth.py 自動跑完（{time.strftime("%Y-%m-%d %H:%M")}）',
                 f'- 階段：' + '、'.join(f'{k}={v.get("status")}' for k, v in self.st['stages'].items()),
                 f'- 轉生後：{self.info.get("levels_after")}；龍王的守護吃了 {self.st.get("dragon_used", 0)} 顆、存回公共 {self.info.get("dragon_stored")}',
                 f'- 換弓：{self.info.get("swap")}']
        if self.warnings:
            lines.append('- 警告：' + '；'.join(self.warnings))
        lines.append('- 待辦：重組隊、瑪斯貝卡改回騎乘、選練功點（1 轉門檻未測，`grind --spot auto` 不能用）、1.82 清單 / 四大洞窟 / 2031 紅暴要重做。')
        try:
            with open(QUEST_LOG, 'a', encoding='utf-8') as f:
                f.write('\n'.join(lines) + '\n')
        except OSError:
            pass


DRY_PLAN = {
    'preflight': ['heal.set_encounter(False)：關原地遇敵（已關不點；87）', 'char.current = DKBO（面板左欄「當前登錄」）', 'team.form 滿 5 人（非 0 → team.check 滿 5 就算，否則再 form 一次）', 'bag.levels：5 人 (N-1)轉 ≥{lv} 級（80）', '背包 / 寵物欄空位各 ≥2（82）', 'heal.heal_trip --no-return（87）'],
    'accept': ['questdetail.accept {t}（任務詳情列表 / 中間標題精確樣板比對 → 傳送瑪麗娜絲村長 → 對話選單頁左鈕「漆黑洞窟」翻頁 → 「接受」→ 重開詳情驗證進行中；已進行中略過）（97）'],
    'enter': ['quest.py --task {t} --stop-after-dialog --max-seconds 240（最多 3 輪）→ 地圖 32001'],
    'boss10': ['龍王的守護：bag.use_item（沒有 → 公共倉庫 take → use）', 'quest.py --task {t} --max-seconds 540 → 37 / 38', '38 → team.cards 找不在隊的人 → char.switch → track → quest.py --fight --npc auto --team-size 1 → char.ensure DKBO → team.form / check（85）', '確認在 11F 以上（32011～32021，地圖為準）'],
    'bow16': ['龍王的守護（距上次 >9 分鐘才吃）', 'quest.py --task {t} --stop-after-rewards 1 --max-seconds 540 → 地圖 32016', '已過 16F 看地圖：17～20F = 弓已拿到；21F = 20F 也打完 → after_boss（滿 5 人）→ boss20_done，heal / boss20 跳過'],
    'swap': ['5 人：bag.swap_weapon（選弓 → 穿戴 → 武器格確認 → 丟舊武器；--keep-old-weapon 不丟）（86）'],
    'heal': ['heal.heal_trip --no-return', 'ass.set_pet 5 人 normal={act}（rc 4 且讀回 None = 警告不算失敗）', '便捷傳送 漆黑20樓 790,248（87）', 'team.form（83）'],
    'boss20': ['龍王的守護', 'quest.py --task {t} --max-seconds 540 → 37 / 38（同 boss10）→ 確認 32021:29,57 附近', '人仍在 32021 追蹤沒動 → 備援一次：walk 傳送帶 31,47（北區才走）→ 32021 28,59（出口）→ 32020 → team.check → walk 20,11 → quest.py --fight --npc auto（84 / 85）'],
    'rebirth': ['team.form', '沒有獎勵寵對照表的轉數（三轉起）：先拍 5 人寵物欄快照（98）', 'quest.py --task {t} --max-seconds 420 → 39（精靈王轉生頁）', 'OCR 對話：角色轉生才放行（寵物轉生 / 讀不到 / 位置不對 → 88；--confirm-rebirth → 89）',
                '點完成 + quest.py --no-track --allow-irreversible 收尾 → bag.levels 確認 5 人轉數 = N'],
    'cleanup': ['丟轉生獎勵寵：一轉烏力斯坦 / 二轉奇娜（petdrop 5 人，名稱完全相同 + Lv1）；三轉起 = 寵物欄 diff 剛好 1 隻新 Lv1、名字 + Lv1 驗過才丟，不確定 98', '龍王的守護存回公共倉庫（背包沒有 = 略過）', '原地遇敵確認關閉', 'char.ensure DKBO', '寫 notes/quest-log.md 摘要'],
}


def print_plan(n: int, from_stage: str, opts: dict) -> None:
    print(f'rebirth 計畫：轉到第 {n} 轉（任務組 {task_group(n)}「{task_name(n)}」，門檻 {level_min(n)} 級，交守護獸 {pet_names(n)}）')
    print(f'選項：{opts}')
    for s in STAGES[STAGES.index(from_stage):]:
        print(f'[{s}]')
        for ln in DRY_PLAN[s]:
            print('  - ' + ln.format(t=task_name(n), lv=level_min(n), act=opts.get('pet_action')))
    print('退出碼：80 等級 (81 保留) 82 空位 83 隊伍 84 quest 階段 85 BOSS 86 背包/寵物 87 補血/外掛/傳送 88 轉生對話 89 等人 97 接任務 98 獎勵寵不確定；9 驗證視窗 10 斷線')
    print('quest.py 回 19 / 42（巡路卡住 / VS 牌卡死）→ 全員重登（stuckrecover）後重跑同階段，每階段最多 2 次')


def run(trans=None, from_stage: str = 'preflight', dry_run: bool = False, keep_old_weapon: bool = False, confirm_rebirth: bool = False,
        pet_action: str = '忠犬', use_dragon: bool = True, tools=None, to_stage: str = 'cleanup') -> int:
    LAST.clear()
    if from_stage not in STAGES or to_stage not in STAGES or STAGES.index(to_stage) < STAGES.index(from_stage):
        print(f'rebirth：--from / --to 要是 {STAGES} 之一，且 to 不早於 from', file=sys.stderr)
        return uikit.EXIT_USAGE
    opts = {'keep_old': keep_old_weapon, 'confirm_rebirth': confirm_rebirth, 'pet_action': pet_action, 'dragon': use_dragon}
    T = tools or Tools()
    if dry_run:
        print_plan(trans or 1, from_stage, opts)
        return 0
    if trans is None:
        prog = load_progress()
        if from_stage != 'preflight' and prog.get('trans'):
            trans = prog['trans']
        elif from_stage == 'preflight':
            rc, lv = T.levels([LEADER])
            v = lv.get(LEADER) if not rc else None
            if not v:
                print(f'rebirth：讀不到 {LEADER} 的轉數（bag rc {rc}），請用 --trans N 明講', file=sys.stderr)
                return uikit.EXIT_USAGE if not rc else rc
            trans = v[0] + 1
        else:
            print('rebirth：從中途階段續跑但沒有進度檔，請用 --trans N 明講', file=sys.stderr)
            return uikit.EXIT_USAGE
    if trans not in CN:
        print(f'rebirth：--trans 要 1～5（任務組 2004～2008），收到 {trans}', file=sys.stderr)
        return uikit.EXIT_USAGE
    r = Run(trans, T, opts)
    event(f'開始：轉到第 {trans} 轉（{r.task}），從階段 {from_stage}，選項 {opts}')
    rc = 0
    for s in STAGES[STAGES.index(from_stage):STAGES.index(to_stage) + 1]:
        r.begin(s)
        r.info = {}
        try:
            rc = getattr(r, 's_' + s)()
        except SystemExit:
            r.end(s, uikit.EXIT_HALT)
            raise
        r.end(s, rc)
        if rc:
            break
    LAST.clear()
    LAST.update(ok=rc == 0, rc=rc, trans=trans, stages=r.st['stages'], info=r.info, warnings=r.warnings)
    event(f'結束 rc={rc}' + (f'；續跑：--from {s} --trans {trans}' if rc else ''))
    return rc


def main() -> int:
    import winenv
    winenv.enable_server()
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--trans', type=int, default=None)
    ap.add_argument('--from', dest='from_stage', default='preflight', choices=STAGES)
    ap.add_argument('--to', dest='to_stage', default='cleanup', choices=STAGES, help='跑到這個階段（含）就停（預設 cleanup）')
    ap.add_argument('--dry-run', action='store_true')
    ap.add_argument('--keep-old-weapon', action='store_true')
    ap.add_argument('--confirm-rebirth', action='store_true')
    ap.add_argument('--pet-action', default='忠犬', choices=['忠犬', '攻擊', '防禦', 'none'])
    ap.add_argument('--no-dragon', action='store_true')
    a = ap.parse_args()
    rc = run(a.trans, a.from_stage, a.dry_run, a.keep_old_weapon, a.confirm_rebirth, a.pet_action, not a.no_dragon, to_stage=a.to_stage)
    if not a.dry_run:
        print(json.dumps(LAST, ensure_ascii=False, default=str))
    return rc


if __name__ == '__main__':
    sys.exit(main())
