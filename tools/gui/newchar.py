#!/usr/bin/env python3
"""新角色 0 轉 1 級開局（照 2026-10-09 主視窗手動紀錄 notes/new-account.md、notes/leveling.md 腳本化）。只用標準函式庫。

**實機驗證狀態（2026-10-15 寫成時）：整支只有離線測試（test_newchar.py，假 Tools）**——寫的當下另一個 agent 正在操作 PrimalSA2，
完全沒碰遊戲畫面。各步呼叫的既有工具：bag.py（use_item 實機過；wear / store-items 是同日新增、未實機）、pet.py set-state-many、
ass.py set_many（實機過）/ points（同日新增、未實機）、team.py form、quest.py、grind.go。

用法（專案根目錄；WSL / Windows 原生指令相同；PSA_CLIENT=PrimalSA2 → 名單 DKBO6～DKBO10）：
  uv run --no-project python tools/gui/newchar.py plan [--confirm-buy] [--no-grind] [--skip 步驟,...]          # 只印步驟 / 狀態 / 退出碼，完全不碰遊戲（= run --dry-run）
  uv run --no-project python tools/gui/newchar.py run [--from 步驟] [--to 步驟] [--fresh] [--confirm-buy] [--no-grind] [--skip 步驟,...] [--dry-run]
    --from / --to    只做這段（中斷後接著做；已完成的步驟記在進度檔 newchar.json〔12 小時內有效〕，重跑自動跳過；--from 指定的那步一定重做）
    --fresh          不看進度檔，從頭（每步本身也會先看狀態：已開的禮盒 / 已穿的裝備 / 已存的道具 / 已是目標的寵物與勾選都不重做）
    --confirm-buy    花石幣買溫蒂妮Lv5的金幣 + 隊長人物首次動作 風的精靈：**目前未支援**（shopbuy 只會買耐久力回複藥）→ 該步記「未支援」跳過、最後回 199
    --no-grind       最後不去練功
    --skip 步驟[,步驟]  被 skip 的步驟完全不執行（不開任何面板），記為「略過（--skip）」；視為滿足 --from 的前置檢查；
                     不影響退出碼（199 只給待手動 / 未支援）；plan 也標出（例：--skip points = 自動加點這次不做）
  可 import：newchar.run(...) → 退出碼；結果 dict 在 newchar.LAST

步驟（名單 = clients.roster()，第 1 個是隊長；每步驗證 → 點 → 驗證，失敗不重點）：
  preflight  uikit.preflight（驗證視窗 9 / 斷線 10 / 其他腳本佔用 8 直接停）→ 當前角色 = 隊長（char.ensure）
  boxes      背包面板開一次、左欄頭像逐人：bag.find_items 盤點 → 認得的開局禮盒（迎新助力禮盒 90334）才使用（其他禮盒如
             「2轉新手禮盒」等級條件不符 → 跳過、只記錄，不算錯誤）→ 使用「石幣2萬」→ 穿 新手棍棒 / 新手鎧甲 / 新手頭盔（bag.wear_item；背包沒有 = 已穿上）
  pets       寵物面板：迪基格斯 → 出戰、瑪斯貝卡 → 騎乘（pet.set_state_many；騎乘要 allow_mount；已是目標狀態不點）
  store      背包面板開一次逐人：寵物誘餌 / 離線水晶 / 2倍智慧果 / 安撫之素 → 公共倉庫；1轉新手禮盒（banPubDepot）→ 個人倉庫（bag.depot_store_items；沒有的略過）
  battle     外掛 5 人「自動戰鬥」開（ass.set_many，隊長最後；快速戰鬥在村長家被禁，練功時 grind 再開）
  heal       外掛 戰鬥設置 → 自動補血 → 精靈補血 5 人打勾（ass.heal_set；OCR 找「精靈補血」標籤列再點勾選框，已勾不點、點後驗證；
             失敗 = 195（info.ass_rc / ass_step = heal；ass 17 = 找不到標籤）；**未實機**；舊進度檔沒有此步驟也能續跑）
  points     外掛自動加點（ass.points_set：速度80 / 體力50 / 腕力999 / 耐力0 + 同步加點）。**座標待量測**：加點視窗改目標值的輸入流程
             沒實測（ui/ass.md），腳本不改方案 —— 方案已是這套才勾自定義 + 同步加點；不是（新角色一定不是）→ ass 15 →
             本步記「待手動」跳過、繼續後面的步驟、最後回 199；OCR 讀不到 → ass 16，同樣跳過。不會盲點座標
  team       team.form（隊長 = 名單第 1 個、人數 = 名單人數）
  quest      初入石器（任務 1000，2 步都在 薩姆吉爾的村長家 1006:18,22 老村長）：quest.py --task 初入石器 → --task 覲見村長
             （組隊預設模式，隊長對話、5 人都拿獎勵；quest.py 回 5 = 追蹤欄沒有該卡 = 已做完，跳過）
  buy        溫蒂妮Lv5的金幣（競技場道具屋 500 石幣）+ 隊長外掛人物首次動作 = 風的精靈Lv.5：**未支援**；沒給 --confirm-buy = 不做；
             給了 = 記「未支援」跳過（最後 199），要人手動（notes/leveling.md 2026-10-09 03:11）
  grind      grind.go：依當下等級選點（不寫死地點；新角色 3 級 → 柯奧龜洞一帶）、5 人快速 + 自動戰鬥、開遇敵、未滿地雷區背景起 follow

退出碼（共用 0 / 1 / 2 / 8 / 9 / 10 見 uikit；其他工具 40～184；本檔 190～199，2026-10-15 grep 過沒人用）：
  190 參數 / 名單（PSA_CLIENT 沒有寫死的名單）/ --from 的前置步驟沒做
  191 preflight 失敗（切不回隊長）
  192 boxes 失敗（info.bag_rc：90～96 見 bag.py）
  193 pets 失敗（info.pet_rc：70～78 見 pet.py）
  194 store 失敗（info.bag_rc）
  195 battle / heal 失敗（info.ass_rc；heal 另有 info.ass_step = heal）
  196 team 失敗（info.team_rc：40～47）
  197 quest 失敗（info.quest_rc；quest.py 2 = 不認得的畫面 → 改回 9 停手）
  198 grind 失敗（info.grind_rc：50～59）
  199 其他步驟都完成，但有「待手動 / 未支援」被跳過（points 座標待量測、--confirm-buy 未支援；清單在 info.pending）
  8 / 9 / 10：任何一步的工具回這三個 → 原碼停手（佔用 / 疑似驗證視窗 / 斷線，鐵則 5）
"""
import argparse
import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import clients  # noqa: E402
import logpaths  # noqa: E402
import uikit  # noqa: E402

SRC = 'newchar'
EVENT_LOG = logpaths.p(clients.npath('quest-events.log'))     # 主視窗 = notes/；其他 = notes/clients/<程序名>/
PROGRESS = logpaths.p(uikit.CACHE / 'newchar.json')          # 主視窗 = tools/.cache；其他 = tools/.cache/clients/<程序名>/
PROGRESS_TRUST_S = 12 * 3600

EXIT_ARGS, EXIT_PRE, EXIT_BOX, EXIT_PET, EXIT_STORE, EXIT_BATTLE, EXIT_TEAM, EXIT_QUEST, EXIT_GRIND, EXIT_PENDING = range(190, 200)
PASS = (uikit.EXIT_IN_BATTLE, uikit.EXIT_UNKNOWN_SCREEN, uikit.EXIT_HALT)   # 8 / 9 / 10 原碼停手

STAGES = ['preflight', 'boxes', 'pets', 'store', 'battle', 'heal', 'points', 'team', 'quest', 'buy', 'grind']
ALL_ROLES = clients.roster()          # 這個視窗的名單：主視窗 DKBO、DKBO2～5；PrimalSA2 = DKBO6～10；第 1 個 = 隊長
LEADER = ALL_ROLES[0] if ALL_ROLES else ''

OPEN_BOXES = ['迎新助力禮盒']                                  # 認得、0 轉 1 級就能開的開局禮盒（Item 90334，無 levelLimit）
SKIP_BOXES = [f'{n}轉新手禮盒' for n in range(2, 5)]            # 有等級條件（levelLimit [N轉, 1級]）→ 0 轉不開，看到只記錄（PrimalSA2 背包第 0 格實機看到 2轉新手禮盒）
COIN = '石幣2萬'
GEAR = ['新手棍棒', '新手鎧甲', '新手頭盔']
BATTLE_PET, MOUNT_PET = '迪基格斯', '瑪斯貝卡'
NEXT_BOX = '1轉新手禮盒'                                       # banPubDepot = 1 → 個人倉庫
from rebirth_pets import BOX_CONTENTS  # noqa: E402            # 寵物誘餌 / 離線水晶 / 2倍智慧果 / 安撫之素 → 公共（同轉生禮盒內容）
STORE_ITEMS = [(n, 'public') for n in BOX_CONTENTS] + [(NEXT_BOX, 'personal')]
QUEST_TASKS = ['初入石器', '覲見村長']                          # 任務 1000 兩步的追蹤卡標題（ui/quest.md「新角色任務進度」）
QUEST_SLICE_S = 300
QUEST_NOT_FOUND = 5                                           # quest.py：追蹤欄掃完找不到 --task（沒點任何東西）= 這步已做完
QUEST_UNKNOWN = 2                                             # quest.py：不認得的畫面（可能是驗證視窗）→ 9
LAST: dict = {}

STATUS = {   # 步驟實作狀態（plan 顯示）
    'preflight': '完成', 'boxes': '完成（bag.wear 未實機）', 'pets': '完成', 'store': '完成（bag.store-items 未實機）', 'battle': '完成',
    'heal': '未實機（ass.heal 同日新增）',
    'points': '座標待量測', 'team': '完成', 'quest': '完成', 'buy': '未支援', 'grind': '完成',
}


# ---- 純函式 ----
def present(found: dict, names) -> list:
    """bag.find_items 的結果 → 背包裡有的名稱（照 names 順序）"""
    return [n for n in names if found.get(n) is not None]


def quest_args(task: str, team_size: int) -> list:
    return ['--task', task, '--max-seconds', QUEST_SLICE_S, '--team-size', team_size]


def plan(o: dict) -> list:
    """(步驟, 狀態, [動作]) —— plan / --dry-run 用"""
    n = len(ALL_ROLES)
    return [
        ('preflight', STATUS['preflight'], [f'preflight（9 / 10 / 8 停手）', f'當前角色 = {LEADER}（char.ensure）']),
        ('boxes', STATUS['boxes'], [f'{n} 人（背包開一次逐人）：使用 {"/".join(OPEN_BOXES)}（{"/".join(SKIP_BOXES)} 等級不符 → 跳過只記錄）',
                                   f'使用 {COIN}', f'穿 {" / ".join(GEAR)}（背包沒有 = 已穿上）']),
        ('pets', STATUS['pets'], [f'{BATTLE_PET} → 出戰、{MOUNT_PET} → 騎乘（allow_mount；已是目標不點）']),
        ('store', STATUS['store'], [f'公共：{" / ".join(BOX_CONTENTS)}', f'個人：{NEXT_BOX}（禁止存公共）', '沒有的略過']),
        ('battle', STATUS['battle'], [f'外掛 {n} 人自動戰鬥開（隊長最後）']),
        ('heal', STATUS['heal'], [f'外掛 戰鬥設置 → 自動補血 → 精靈補血 {n} 人打勾（ass.heal_set；OCR 找標籤列、已勾不點、點後驗證；失敗 195）']),
        ('points', STATUS['points'], ['外掛自動加點：速度80 / 體力50 / 腕力999 / 耐力0 + 同步加點（隊長設、其他人看勾選）',
                                     '方案目標值輸入流程未實測 → 方案不是這套就不改不勾（ass 15）、讀不到（ass 16）→ 記待手動、跳過、最後 199']),
        ('team', STATUS['team'], [f'team.form（隊長 {LEADER}、{n} 人）']),
        ('quest', STATUS['quest'], [f'quest.py --task {t}（回 5 = 已做完）' for t in QUEST_TASKS]),
        ('buy', STATUS['buy'], ['溫蒂妮Lv5的金幣（競技場道具屋 500 石幣）+ 隊長人物首次動作 風的精靈Lv.5：未支援（shopbuy 只會買耐久力回複藥）',
                               '給了 --confirm-buy → 記未支援跳過、最後 199' if o.get('confirm_buy') else '沒給 --confirm-buy → 不做']),
        ('grind', STATUS['grind'], ['（--no-grind 跳過）'] if o.get('no_grind') else ['grind.go：依等級選點傳送、5 人快速 + 自動戰鬥、開遇敵、未滿地雷區起 follow']),
    ]


def print_plan(o: dict, from_stage: str, to_stage: str, done=()) -> None:
    skip = o.get('skip') or ()
    print(f'newchar：名單 {ALL_ROLES}（隊長 {LEADER}；PSA_CLIENT={clients.name()}）')
    on = False
    for st, status, acts in plan(o):
        on = on or st == from_stage
        mark = '✓' if st in done else ('→' if on else '·')
        if st in skip:
            mark, status = '－', '略過（--skip）'
        print(f'  {mark} {st}［{status}］')
        if on and st not in skip:
            for a in acts:
                print(f'      - {a}')
        if st == to_stage:
            on = False
    print('  退出碼：190 參數 / 191 preflight / 192 boxes / 193 pets / 194 store / 195 battle / heal / 196 team / 197 quest / 198 grind / '
          '199 完成但有待手動 / 未支援步驟；8 / 9 / 10 原碼停手')


# ---- 紀錄 ----
def event(msg: str) -> None:
    line = f'{time.strftime("%Y-%m-%d %H:%M:%S")} [newchar] {msg}'
    print(line, flush=True)
    try:
        EVENT_LOG.parent.mkdir(parents=True, exist_ok=True)
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


# ---- 碰遊戲的動作（既有工具的薄包裝；測試換成 FakeTools）----
class Tools:
    def preflight(self):
        return uikit.preflight(SRC)

    def char_ensure(self, name):
        import char
        return char.ensure(name)

    def snap(self, tag):
        return uikit.snap(tag)

    def sleep(self, s):
        uikit.sleep(s)

    def bag_session(self):
        import bag
        return bag.Session()

    def find_items(self, role, names):
        import bag
        return bag.find_items(role, names)

    def use(self, role, name):
        import bag
        return bag.use_item(role, name)

    def wear(self, role, name):
        import bag
        return bag.wear_item(role, name)

    def store_items(self, roles, items):
        import bag
        return bag.depot_store_items(roles, items, True)

    def pet_state_many(self, roles, pet, state, allow_mount=False):
        import pet as petmod
        return petmod.set_state_many(','.join(roles), pet, state, allow_mount, False, True)

    def ass_set_many(self, plan_):
        import ass
        return ass.set_many(plan_)

    def ass_heal_set(self, roles):
        import ass
        return ass.heal_set(roles, True)

    def points_set(self, leader, verify):
        import ass
        return ass.points_set(leader, verify)

    def team_form(self, leader, size):
        import team
        return team.form(leader, size)

    def quest(self, args):
        import postrebirth                                   # 共用子程序跑法（輸出即時印出、回最後幾行）
        rc, _ = postrebirth.Tools().sub('quest.py', args, QUEST_SLICE_S + 900 + 120)
        return rc

    def grind_go(self):
        import grind
        return grind.go()


ITEM_MISSING, ITEM_VERIFY = 92, 95                            # bag.EXIT_ITEM / EXIT_VERIFY（不 import bag：測試不載入）


class Run:
    def __init__(self, T, o: dict):
        self.T, self.o = T, o
        p = {} if o.get('fresh') else load_progress()
        if time.time() - (p.get('ts') or 0) > PROGRESS_TRUST_S or p.get('client') != clients.name():
            p = {}
        p.setdefault('done', [])
        p.setdefault('pending', {})
        p['client'] = clients.name()
        self.p = p
        self.info: dict = {}

    def save(self):
        self.p['ts'] = time.time()
        save_progress(self.p)

    def done(self, stage: str, **data):
        if stage not in self.p['done']:
            self.p['done'].append(stage)
        self.p['pending'].pop(stage, None)
        self.p.setdefault('data', {}).update(data)
        self.save()
        event(f'步驟 {stage} 完成')
        return 0

    def pending(self, stage: str, why: str, **data):
        """待手動 / 未支援：記下來、跳過、繼續後面的步驟（最後回 199）"""
        self.p['pending'][stage] = why
        self.p.setdefault('data', {}).update(data)
        self.save()
        event(f'步驟 {stage} 跳過（待手動 / 未支援）：{why}')
        return 0

    def stop(self, rc: int, msg: str, **extra):
        self.info.update(extra, msg=msg)
        event(f'失敗 rc={rc}：{msg}')
        try:
            import errlog
            errlog.add(f'newchar：{msg}', source=SRC)
        except Exception:                                    # noqa: BLE001
            pass
        self.T.snap('newchar-fail')
        return rc

    def fail(self, rc: int, code: int, msg: str, **extra):
        """工具回 rc：8 / 9 / 10 原碼停手，其他 → 本步退出碼"""
        return self.stop(rc if rc in PASS else code, msg, **extra)

    # ---- 步驟 ----
    def preflight(self):
        rc = self.T.preflight()
        if rc:
            return self.fail(rc, EXIT_PRE, f'preflight rc {rc}')
        rc = self.T.char_ensure(LEADER)
        if rc:
            return self.fail(rc, EXIT_PRE, f'當前角色切不回 {LEADER}（char rc {rc}）', char_rc=rc)
        event(f'preflight OK：當前 {LEADER}')
        return 0

    def _use_once(self, role, name) -> int:
        """使用一次並驗證背包沒有了；95（彈窗沒關）或用完還在 → 等 2 秒重用一次（rebirth_pets 禮盒同一處理）；仍在 → 95"""
        for k in range(2):
            rc = self.T.use(role, name)
            if rc and rc != ITEM_VERIFY:
                return rc
            rc2, f = self.T.find_items(role, [name])
            if rc2:
                return rc2
            if f.get(name) is None:
                return 0
            if k == 0:
                event(f'{role}：使用「{name}」後背包還有 → 等 2 秒再用一次')
                self.T.sleep(2)
        return ITEM_VERIFY

    def boxes(self):
        T = self.T
        res = {}
        with T.bag_session() as s:
            if s.rc:
                return self.fail(s.rc, EXIT_BOX, f'背包面板打不開（bag rc {s.rc}）', bag_rc=s.rc)
            for r in ALL_ROLES:
                info = res.setdefault(r, {'used': [], 'worn': [], 'skipped': []})
                rc, f = T.find_items(r, OPEN_BOXES + SKIP_BOXES + [COIN] + GEAR)
                if rc:
                    return self.fail(rc, EXIT_BOX, f'{r} 盤點背包失敗（bag rc {rc}）', bag_rc=rc, boxes=res)
                open_slots = {f[o] for o in present(f, OPEN_BOXES)}
                # 迎新助力禮盒與 N轉新手禮盒縮圖同圖（imageId 50055）：同一格兩個名稱都命中 = 其實是迎新助力禮盒（2026-10-15 PrimalSA2 實機：彈窗名稱核對）
                info['skipped'] = [n for n in present(f, SKIP_BOXES) if f[n] not in open_slots]
                if info['skipped']:
                    event(f'{r}：背包有 {info["skipped"]}（等級條件不符，不開）')
                opened = False
                for b in present(f, OPEN_BOXES):
                    rc = self._use_once(r, b)
                    if rc:
                        return self.fail(rc, EXIT_BOX, f'{r} 開「{b}」失敗（bag rc {rc}）', bag_rc=rc, boxes=res)
                    info['used'].append(b)
                    opened = True
                if opened:                                   # 禮盒開出來的東西要重新盤點
                    rc, f = T.find_items(r, [COIN] + GEAR)
                    if rc:
                        return self.fail(rc, EXIT_BOX, f'{r} 開禮盒後盤點失敗（bag rc {rc}）', bag_rc=rc, boxes=res)
                if f.get(COIN) is not None:
                    rc = self._use_once(r, COIN)
                    if rc:
                        return self.fail(rc, EXIT_BOX, f'{r} 使用「{COIN}」失敗（bag rc {rc}）', bag_rc=rc, boxes=res)
                    info['used'].append(COIN)
                for g in present(f, GEAR):
                    rc = T.wear(r, g)
                    if rc == ITEM_MISSING:                   # 剛被別的動作處理掉 / 讀錯：當作已穿上
                        continue
                    if rc:
                        return self.fail(rc, EXIT_BOX, f'{r} 穿「{g}」失敗（bag rc {rc}）', bag_rc=rc, boxes=res)
                    info['worn'].append(g)
                event(f'{r}：使用 {info["used"] or "（無）"}、穿上 {info["worn"] or "（無，已穿 / 沒有）"}')
        return self.done('boxes', boxes=res)

    def pets(self):
        for pet, state, mount in ((BATTLE_PET, '出戰', False), (MOUNT_PET, '騎乘', True)):
            rc = self.T.pet_state_many(ALL_ROLES, pet, state, mount)
            if rc:
                return self.fail(rc, EXIT_PET, f'{pet} → {state} 失敗（pet rc {rc}）', pet_rc=rc)
        return self.done('pets')

    def store(self):
        rc, res = self.T.store_items(ALL_ROLES, STORE_ITEMS)
        if rc:
            return self.fail(rc, EXIT_STORE, f'存倉失敗（bag rc {rc}）', bag_rc=rc, stored=res)
        return self.done('store', stored=res)

    def battle(self):
        plan_ = {r: {'自動戰鬥': True} for r in clients.leader_last()}
        rc, sts, msg, info = self.T.ass_set_many(plan_)
        if rc:
            return self.fail(rc, EXIT_BATTLE, f'外掛自動戰鬥失敗（ass rc {rc}）：{msg}', ass_rc=rc)
        return self.done('battle', battle_changed=info.get('changed', {}))

    def heal(self):
        rc, sts, msg, info = self.T.ass_heal_set(clients.leader_last())
        if rc:
            return self.fail(rc, EXIT_BATTLE, f'外掛精靈補血打勾失敗（ass rc {rc}）：{msg}', ass_rc=rc, ass_step='heal')
        return self.done('heal', heal_changed=info.get('changed', {}))

    def points(self):
        rc, sts, msg, info = self.T.points_set(LEADER, [r for r in ALL_ROLES if r != LEADER])
        if rc in PASS:
            return self.fail(rc, EXIT_PENDING, f'自動加點 rc {rc}')
        if rc:
            return self.pending('points', f'自動加點沒做（ass rc {rc}：{msg}）；方案請手動設 速度80 / 體力50 / 腕力999 / 耐力0 + 勾自定義 / 同步加點（ui/ass.md）',
                                points_rc=rc)
        return self.done('points', points=sts)

    def team(self):
        rc = self.T.team_form(LEADER, len(ALL_ROLES))
        if rc:
            return self.fail(rc, EXIT_TEAM, f'組隊失敗（team rc {rc}）', team_rc=rc)
        return self.done('team')

    def quest(self):
        res = {}
        for task in QUEST_TASKS:
            rc = self.T.quest(quest_args(task, len(ALL_ROLES)))
            res[task] = rc
            if rc == QUEST_NOT_FOUND:
                event(f'{task}：追蹤欄沒有（已做完）→ 跳過')
                continue
            if rc == QUEST_UNKNOWN:
                return self.stop(uikit.EXIT_UNKNOWN_SCREEN, f'{task}：quest.py 回 2（不認得的畫面，可能是驗證視窗）→ 停手', quest_rc=rc, quest=res)
            if rc:
                return self.fail(rc, EXIT_QUEST, f'{task}：quest.py rc {rc}（見 quest.py 檔頭）', quest_rc=rc, quest=res)
        return self.done('quest', quest=res)

    def buy(self):
        if not self.o.get('confirm_buy'):
            event('buy：沒給 --confirm-buy → 不買（溫蒂妮Lv5的金幣 / 風的精靈）')
            return self.done('buy', buy='skipped')
        return self.pending('buy', '未支援：溫蒂妮Lv5的金幣（競技場道具屋 500 石幣）+ 隊長外掛人物首次動作 風的精靈Lv.5 請手動（shopbuy 只會買耐久力回複藥）')

    def grind(self):
        if self.o.get('no_grind'):
            return self.done('grind', grind='skipped')
        rc = self.T.grind_go()
        if rc:
            return self.fail(rc, EXIT_GRIND, f'去練功失敗（grind rc {rc}）', grind_rc=rc)
        return self.done('grind')


def run(from_stage: str = 'preflight', to_stage: str = 'grind', dry_run: bool = False, tools=None, fresh: bool = False,
        confirm_buy: bool = False, no_grind: bool = False, skip=()) -> int:
    LAST.clear()
    skip = tuple(skip or ())
    o = dict(fresh=fresh, confirm_buy=confirm_buy, no_grind=no_grind, skip=skip)
    if not ALL_ROLES:
        print(f'{SRC}：PSA_CLIENT={clients.name()} 沒有寫死的名單（clients.ROSTERS）', file=sys.stderr)
        return EXIT_ARGS
    if from_stage not in STAGES or to_stage not in STAGES or STAGES.index(from_stage) > STAGES.index(to_stage):
        print(f'{SRC}：--from / --to 不對（{STAGES}）', file=sys.stderr)
        return EXIT_ARGS
    if [s for s in skip if s not in STAGES or s == 'preflight']:
        print(f'{SRC}：--skip 不對（{STAGES[1:]}；preflight 不能略過）', file=sys.stderr)
        return EXIT_ARGS
    if dry_run:
        print_plan(o, from_stage, to_stage, () if fresh else load_progress().get('done', []))
        LAST.update(ok=True, rc=0, dry_run=True, plan=[(s, st) for s, st, _ in plan(o)])
        return 0
    R = Run(tools or Tools(), o)
    before = STAGES[1:STAGES.index(from_stage)]
    missing = [s for s in before if s not in R.p['done'] and s not in R.p['pending'] and s not in skip and s != 'heal']   # heal 是後加的步驟：舊進度檔沒有它不算前置缺漏
    if missing:
        print(f'{SRC}：--from {from_stage} 但進度檔沒有完成 {missing}（先照順序跑，或 --fresh 從頭）', file=sys.stderr)
        return EXIT_ARGS
    event(f'開始：名單 {ALL_ROLES}（{clients.name()}）from={from_stage} to={to_stage} {o}')
    rc = 0
    todo = STAGES[STAGES.index(from_stage):STAGES.index(to_stage) + 1]
    if 'preflight' not in todo:
        todo = ['preflight'] + todo                          # preflight 每次都跑（不記進度）
    for st in todo:
        if st in skip:
            event(f'步驟 {st} 略過（--skip）')
            continue
        if st not in ('preflight', from_stage) and st in R.p['done']:      # --from 指定的那步一定重做（想重做某步就 --from 它）
            event(f'步驟 {st} 進度檔已完成 → 跳過')
            continue
        rc = getattr(R, st)()
        if rc:
            break
    pend = dict(R.p['pending'])
    if not rc and pend:
        rc = EXIT_PENDING
        event(f'完成，但有待手動 / 未支援步驟：{pend}')
    elif not rc:
        event('全部完成')
    LAST.update(R.info, ok=rc == 0, rc=rc, done=list(R.p['done']), pending=pend, skipped=[s for s in todo if s in skip])
    return rc


def main(argv=None) -> int:
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('cmd', choices=['plan', 'run'])
    ap.add_argument('--from', dest='from_stage', default='preflight', choices=STAGES)
    ap.add_argument('--to', dest='to_stage', default='grind', choices=STAGES)
    ap.add_argument('--fresh', action='store_true', help='不看進度檔，從頭（每步仍會先看狀態、已完成的不重做）')
    ap.add_argument('--confirm-buy', action='store_true', help='花石幣買溫蒂妮Lv5的金幣 + 風的精靈（目前未支援 → 記未支援、最後 199）')
    ap.add_argument('--no-grind', action='store_true', help='最後不去練功')
    ap.add_argument('--skip', default='', help='略過的步驟（逗號分隔，例 points）：完全不執行、不開面板，不影響退出碼')
    ap.add_argument('--dry-run', action='store_true', help='同 plan：只印步驟，不碰遊戲')
    a = ap.parse_args(argv)
    dry = a.dry_run or a.cmd == 'plan'
    if not dry:
        import winenv
        winenv.enable_server()
    rc = run(a.from_stage, a.to_stage, dry, None, a.fresh, a.confirm_buy, a.no_grind,
             [x.strip() for x in a.skip.split(',') if x.strip()])
    print(json.dumps(dict(LAST, rc=rc), ensure_ascii=False, default=str))
    return rc


if __name__ == '__main__':
    sys.exit(main())
