#!/usr/bin/env python3
"""1.82 任務驅動器（P2：驅動器骨架 + 純巡路任務；計畫 notes/plan-182-script.md）。只用標準函式庫。

用法（專案根目錄；WSL / Windows 原生相同）：
  uv run --no-project python tools/gui/questrun.py plan [任務ID …]            # 不碰遊戲：印交接 / 每任務步驟 / 指令 / 預估 / 退出碼（沒給 ID = questdefs 全部）
  uv run --no-project python tools/gui/questrun.py run 2999 2017 2015 [--dry-run] [--after grind|none] [--no-dragon] [--spot 地雷區]
        [--max-slices 60] [--slice-s 60] [--max-min 30] [--hp-min 50] [--team-hp-min 60] [--no-boss-retry] [--no-verify-all] [--verify-skipped]
  uv run --no-project python tools/gui/questrun.py status [任務ID …]          # 唯讀（要開 / 關任務詳情面板）：印各任務目前狀態（當前角色）
  uv run --no-project python tools/gui/questrun.py status --role all|DKBO3,DKBO5 [任務ID …]   # 逐人：每人 char.switch → 開一次詳情讀這些任務 → 最後切回 DKBO（詳情面板沒有頭像列，只能切角色）
  可 import：questrun.run(ids, dry_run=False, after='grind', tools=None, ...) → 退出碼；結果 dict 在 questrun.LAST

任務資料在 questdefs.py（id / 詳情標題 / 追蹤標題 / 特殊步驟）。全部組隊模式（使用者 2026-10-11）；解任務靠遊戲自動巡路（quest.py 點追蹤、對話按確認、每場戰鬥刷新角色）。

流程：
  交接（整次 run 一次）  follow 還在跑就停（已停用，只防呆）→ 關原地遇敵 + 等戰鬥結束 → team.form 滿 5 人（同一次切換面板讀「當前」，不是 DKBO 才 char.ensure；
                        2026-10-12 起不另跑 char.current，省 1～2 次開關面板）
  每個任務
    1 preflight    背包空位（defs.bag_slots）、補血檢查 hp_gate：隊長 HUD HP < --hp-min% 或全隊任一人 < --team-hp-min%（預設 60；bag.hps 開背包逐人讀 HP，約 8 秒）
                   → heal（小護士補整隊）後重組隊；quest.py 37（BOSS 戰贏、滿 5 人）後下一片之前也做一次
    2 接取         team.form（距上次組隊 / 驗隊伍 ≤ TEAM_FRESH_S 秒就略過，例：交接剛組完）→ questdetail.accept(skip_ok, verify=False)：**整個任務只開一次詳情**，同一趟捲動讀狀態（已完成 → 跳過、進行中 → 續跑、待接取 → 傳送 → NPC 對話 → 接受，不重開詳情驗證，看對話框收起）；失敗 119
    3 跑步驟       迴圈（每片 ≤ --slice-s 秒，總計 ≤ --max-min 分，片數 ≤ --max-slices）：
                   龍王的守護（人形圖示不在才吃：depot_use 公共倉庫取出 → 吃 1 顆 → 剩的存回；吃完再關原地遇敵）
                   → defs.steps 有 manual 步驟時 quest.read_step_no 讀步號 → 115；kind=walk 是備援：quest.py 先點追蹤讓遊戲自動巡路，只有回 3（追蹤沒反應 = 原地不動）才用 questhandlers.walk_step 走到定點
                   → quest.py --task <追蹤標題> --max-seconds N，依退出碼分支（見下）；
                     questrun 在 TEAM_FRESH_S 秒內驗過隊伍（接取後 form、quest.py 37 的 BOSS 後檢查、30 / 32 後 form）→ 加 --team-fresh，quest.py 開始前不再開切換面板
                     （領獎後 / 任務戰後的隊伍檢查、37 / 38 照舊）
    4 逐人驗證     （2026-10-12，四寶玉之謎隊長完成、DKBO3 / DKBO5 被打飛沒完成卻沒發現）隊長判完成後，其他 4 人逐一 char.switch 讀任務詳情
                   （questdetail.status_all，每人約 10～40 秒）；有人不是「已完成」→ bossretry --who 落後者（落後者當隊長組 5 人重打 → 切回 DKBO 重組）
                   → 再讀一次那幾個人；仍沒完成 / 讀不到 / 待接取（沒接到）→ 108 停手。--no-verify-all 關；詳情一開就已完成而跳過的任務預設不驗（--verify-skipped 才驗）
    5 收尾         進度檔記已完成（2 小時內）→ 重跑直接跳過；quest.py 印「任務完成」（領獎後追蹤欄沒有該任務）即完成，不開詳情；沒有該字樣才讀一次詳情確認 → 進度檔 tools/.cache/questrun.json、notes/quest-log.md 追加一筆
  交接回去（全部成功才做）--after grind（預設）= grind.py start --spot 地雷區（不重啟 follow）；none = 不動。**失敗退出一律不恢復掛機**（畫面狀態未知）

quest.py 退出碼分支：0 → tail 有「任務完成」= 結束；否則讀一次詳情：已完成 = 結束、進行中 = 下一片；37 BOSS 戰贏且滿 5 人 → 下一片；38 BOSS 後隊伍不滿 / 21 被打飛 → bossretry.py 自動補人（落後者當隊長組 5 人按追蹤回 BOSS 處全隊重打 → 切回 DKBO 重組；每任務最多 BOSS_RETRY_MAX 次，0 → 補血檢查後下一片；--no-boss-retry 關）；
  （2026-10-11）quest.py 的 slice 時限不計自動巡路時間（它結束時印「走路不計時 N 秒」，questrun 把 N 加回 t0 = 不計入 --max-min；子程序逾時 = slice + WALK_CAP_S + 120）；
  quest.py 回 0 且 tail 有「時間到」（單純 slice 到期、任務還在追蹤欄）→ 不開詳情，直接下一片（完成由下一片 quest.py「任務完成」或回 5 時才讀詳情確認）；回 0 但沒有「任務完成」也不是「時間到」（模糊）才讀一次詳情
  3 追蹤沒反應 → 有 walk 步驟先走，否則 112；5 找不到任務 → 看詳情狀態（已完成 = 結束，否則 112）；30 / 32 隊伍不符 → 原地 form()（失敗先關誤開面板再重試 3 次）再起一片，最多 3 輪仍不行才 111（不退出整套）；
  19 自動巡路卡住解卡 3 次仍卡 → 112；33 對話無進展 → 117；25 完整戰鬥自動戰鬥卡住 → 118；39 不可逆對話 → 116（不放行）；2 不認得的畫面（疑似驗證視窗）→ 9 停手通知（鐵則 5）；10 斷線（netwatch）→ 10；21 被打飛 → 同 38 走 bossretry；其他 → 112

退出碼（共用 0 / 1 / 2 / 8 / 9 / 10 見 uikit；其他工具 20～107、120～129；questrun 自己 108、110～119）：
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

LEADER = rebirth.LEADER
ALL_ROLES = rebirth.ALL_ROLES
DRAGON = rebirth.DRAGON
DRAGON_REEAT_S = rebirth.DRAGON_REEAT_S
SLICE_S, MAX_SLICES, MAX_MIN, HP_MIN = 60, 60, 30, 50
BOSS_RETRY_MAX = 3              # 每個任務 38 / 21 時最多呼叫幾次 bossretry（四大洞窟每個 2～5 場 BOSS）
TEAM_HP_MIN = 60                # 全隊任一人 HP < 這個 % → 補血（2026-10-12 四寶玉之謎：只看隊長 HP，隊員約 50% 連打 BOSS 被打死踢隊 4 次 38）；0 = 不讀全隊
WALK_CAP_S = 900.0              # quest.py 單次連續自動巡路最多不計時這麼久（要與 quest.WALK_CAP_S 相同；子程序逾時 = slice + 這個 + 120）
DEFAULT_SPOT = '地雷區'
FORM_TRIES = 3                  # team.form 原地重試次數（小錯不退出）
TEAM_FRESH_S = 30.0             # 隊伍在這麼多秒內驗過（form 成功 / quest.py 37）→ 接取前不重組、quest.py 加 --team-fresh（2026-10-12 解救老爺爺：開始前 4 次 + quest.py 啟動 1 次開關切換面板）
DONE_TRUST_S = 2 * 3600         # 進度檔記「已完成」且在這段時間內 → 重啟續跑直接跳過（超過視為可能轉生 / 封印書重置過，重新讀一次詳情）
DONE, DOING, PENDING = '已完成', '進行中', '待接取'
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
        """5 人 HP%（開背包逐人點頭像讀 HP 條字，約 8 秒）→ (rc, {角色: % | None})；HUD / 切換面板 / 組隊面板都只有當前角色或沒有 HP"""
        import bag
        rc, d = bag.hps(ALL_ROLES)
        return rc, {r: (round(100 * v[0] / v[1]) if v else None) for r, v in d.items()}

    def heal(self):
        import heal
        heal.heal_trip('波拉島', True, False)

    def bag_free(self, roles):
        import bag
        out = {}
        for r in roles:
            rc, it = bag.find_items(r, [])
            if rc:
                return rc, out
            out[r] = it.get('_free')
        return 0, out

    def dragon(self, have=False):
        """公共倉庫取出 → 吃 1 顆 → 剩的存回；回 (rc, info)。吃完把原地遇敵關回去（depot_use 會開）"""
        import depot_use
        rc, info = depot_use.run(LEADER, DRAGON, 'public', True, have, False)   # 吃完不開遇敵（跑任務時要關）
        return rc, info

    def close_stray(self):
        """誤開的組隊 / 切換面板 → 點 ✕ 關（已知面板才關；不認得的畫面不碰）"""
        import quest
        return quest.close_stray_panel()

    def dragon_active(self):
        """buff 列有龍王的人形圖示嗎（True / False）；讀不到 None"""
        import bag
        row = bag.buff_row()
        return None if row is None else 'dragon' in row

    def walk_to(self, m, x, y):
        import walk
        return walk.walk_to(m, x, y)

    def unfreeze(self):
        """自動巡路停住後角色凍住：刷新角色；站在出口格上沒換圖則踏出再踏回 → 換圖後 (map,x,y) / None"""
        import quest as _q
        import walk
        _q.refresh_characters()
        return walk.rewarp_if_on_exit()

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
        import relogin
        return relogin.run(confirm=True)

    def unstick_exit(self):
        import quest as _q
        import walk
        _q.refresh_characters()
        return walk.rewarp_if_on_exit() or walk.walk_onto_nearby_exit(2)

    def grind_start(self, spot):
        import grind
        return grind.run('start', spot)

    def boss_retry(self, track, who=None):
        """BOSS 戰後不滿 5 人 / 逐人驗證有人沒完成（who = 落後者名單）：落後者當隊長組 5 人重打 → 切回 DKBO 重組（bossretry.py）→ (rc, 結果 dict)"""
        import bossretry
        rc = bossretry.run(track, who=who)
        return rc, dict(bossretry.LAST)

    def status_all(self, detail, roles):
        """逐人讀任務詳情（char.switch + 每人開一次詳情，最後切回 DKBO）→ (rc, {角色: {標題: 狀態} 或 None})"""
        import questdetail
        return questdetail.status_all([detail], roles=roles, leader=LEADER)


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
    """quest.py 退出碼 → 動作字串（測試直接餵）：done? / boss / stuck3 / gone / team / stall / battle / irrev / verify / halt / knocked / other"""
    return {0: 'check', 37: 'boss', 38: 'boss_team', 3: 'no_track', 5: 'gone', 30: 'team', 32: 'team', 33: 'stall', 29: 'stall', 25: 'battle',
            39: 'irrev', 2: 'verify', uikit.EXIT_UNKNOWN_SCREEN: 'verify', uikit.EXIT_HALT: 'halt', 21: 'knocked'}.get(rc, 'other')


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


def est_total(defs) -> int:
    return sum(d.get('est_min', 0) for d in defs)


def print_plan(defs, opts: dict) -> None:
    print(f'questrun 計畫：{len(defs)} 個任務，預估 {est_total(defs)} 分鐘（組隊模式；0 轉 123 級 5 人隊實測值，1 轉可能更久）')
    print(f'選項：{opts}')
    print('[交接]')
    for ln in ('follow 還在跑就 grind.py follow --stop（已停用，只防呆）', '關原地遇敵 + 等戰鬥結束',
               'team.form 滿 5 人（同一次切換面板讀「當前登錄」，不是 DKBO 才 char.ensure）'):
        print('  - ' + ln)
    for d in defs:
        print(f'[任務 {d["id"]}] {d["detail"]}（追蹤標題「{d["track"]}」，接取 {d["accept_npc"]}，{d["steps_total"]} 步，預估 {d.get("est_min", "?")} 分）')
        print(f'  - team.form（{TEAM_FRESH_S:.0f} 秒內剛確認過就略過）→ questdetail.accept（只開一次詳情）：已完成 → 跳過；待接取 → 接受（不重開詳情）；進行中 → 續跑')
        if d.get('bag_slots'):
            print(f'  - 背包空位：5 人各 ≥ {d["bag_slots"]} 格（bag.find_items）')
        print(f'  - 補血檢查（任務開始前、每次 BOSS 戰後）：隊長 HUD HP < {opts["hp_min"]}% 或全隊（bag.hps）任一人 < {opts.get("team_hp_min", TEAM_HP_MIN)}% → heal.heal_trip --no-return（小護士補整隊）+ team.form')
        for st, sd in sorted((d.get('steps') or {}).items()):
            if sd['kind'] == 'walk':
                print(f'  - 步 {st}：kind=walk（備援）：先讓遊戲自動巡路，quest.py 回 3 才走到 {sd["map"]}:{sd["xy"][0]},{sd["xy"][1]}'
                      f'（{sd.get("npc", "")}；walk.py 中斷外層重試）')
            else:
                print(f'  - 步 {st}：kind={sd["kind"]} → 停下交人（115）')
        if d.get('boss'):
            print(f'  - 有任務戰 / BOSS 戰：quest.py 預設模式打完回 37（滿 5 人 → 繼續）/ 38（不滿 → bossretry.py 落後者當隊長 5 人重打 + 重組，每任務最多 {BOSS_RETRY_MAX} 次；失敗 114）')
        if opts.get('dragon', True):
            print(f'  - 每片前：龍王的守護（buff 列看不到人形圖示才吃；depot_use 公共倉庫取出 → 吃 → 存回 → 關遇敵）')
        print(f'  - 迴圈：quest.py --task {d["track"]} --max-seconds {opts["slice_s"]}（≤ {opts["max_slices"]} 片、≤ {opts["max_min"]} 分），依退出碼分支')
        print('  - 收尾：quest.py「任務完成」（追蹤欄沒有該任務）→ 進度檔 + notes/quest-log.md（沒有該字樣才開詳情確認）')
    if opts['after'] == 'grind':
        print(f'[交接回去] 全部成功 → grind.py start --spot {opts["spot"]}（不重啟 follow）；失敗退出不恢復')
    else:
        print('[交接回去] --after none：不動')
    print('退出碼：110 preflight 111 交接/組隊 112 步驟卡住 113 片數/時間上限 114 BOSS後補人失敗 115 manual 116 不可逆對話 117 對話無進展 118 戰鬥卡住 119 接取失敗；9 驗證視窗 10 斷線')


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

    def team_fresh(self) -> bool:
        """隊伍在 TEAM_FRESH_S 秒內確認過完整（中間沒有傳送 / 戰鬥）→ 不必再開切換面板"""
        return bool(self.team_ok_at) and time.time() - self.team_ok_at <= TEAM_FRESH_S

    def warn(self, msg: str):
        self.warnings.append(msg)
        event(f'警告：{msg}')

    def ensure_dragon(self, force: bool = False):
        """隊長吃龍王的守護（公共倉庫取出 → 吃 1 顆 → 剩的存回）；失敗只警告（沒有也能跑，只是會遇敵）；buff 列看到人形圖示就不吃、看不到就吃一顆（不看時間）"""
        if not self.o.get('dragon', True):
            return
        active = self.T.dragon_active()                                # 人形圖示在 = 還有效（不看時間）；2倍智慧果的 EXP 圖示不會誤判
        if not force and active:
            return
        have = bool(self.st.get('dragon_in_bag'))
        rc, d = self.T.dragon(have)
        if rc:
            self.info['dragon_rc'] = rc
            if 'warn' in (d or {}):
                self.st['dragon_in_bag'] = True                        # 取出後失敗：龍王還在背包，下次跳過取出
            self.warn(f'龍王的守護失敗 rc={rc} {d}；這段不用龍王（會遇敵）')
            self.save()
            return
        self.st['dragon_in_bag'] = False
        self.st['last_eat'] = time.time()
        self.st['dragon_used'] = self.st.get('dragon_used', 0) + 1      # 進度檔累計（跨 run）
        self.run_dragons += 1                                           # 本次 run
        self.task_dragons += 1                                          # 本任務
        event(f'已吃龍王的守護（本次第 {self.run_dragons} 顆，累計 {self.st["dragon_used"]} 顆；剩的已存回公共倉庫）')
        self.save()

    # -- 交接 --
    def handover(self) -> int:
        T = self.T
        if T.follow_active():
            event('follow 還在跑 → 停掉（已停用，只防呆）')
            T.follow_stop()
            if T.follow_active():
                return self.fail(EXIT_HANDOVER, 'follow 停不掉')
        rc = T.preflight()
        if rc:
            return rc
        if T.screen_state() == 'dialog':                            # 上次中斷在 NPC 對話窗（HUD 不在，面板打不開）：ESC 關掉（不回答），quest.py 之後會再點 NPC 開
            event('畫面停在 NPC 對話窗（上次中斷）→ ESC 關閉後再交接')
            T.esc()
            T.sleep(1)
        try:
            T.encounter_off_wait()
        except RuntimeError as e:
            return self.fail(EXIT_HANDOVER, f'關原地遇敵失敗：{e}')
        # 當前角色 = DKBO 由 team.form 同一次讀切換面板時確認（不是才 char.ensure，team._finish）；不再另跑 char.current（2026-10-12：多開關 1～2 次面板）
        rc = self.form('交接')
        if rc:
            if rc in (uikit.EXIT_UNKNOWN_SCREEN, uikit.EXIT_HALT):
                return rc                                               # 驗證視窗 / 斷線透傳
            return self.fail(EXIT_HANDOVER, f'team.form 沒成功 rc={rc}（要滿 5 人）', team_rc=rc)
        return 0

    # -- 任務 --
    def status_of(self, d) -> tuple:
        rc, s = self.T.task_status(d['detail'])
        return rc, s

    def preflight_task(self, d) -> int:
        if d.get('bag_slots'):
            rc, free = self.T.bag_free(ALL_ROLES)
            if rc:
                return self.fail(EXIT_PREFLIGHT, f'讀背包空位失敗 bag rc={rc}', bag_rc=rc)
            self.info['bag_free'] = free
            short = {r: v for r, v in free.items() if v is not None and v < d['bag_slots']}
            if short:
                return self.fail(EXIT_PREFLIGHT, f'{d["detail"]} 要每人背包空 ≥{d["bag_slots"]} 格，不足：{short}', bag_short=short)
        return self.hp_gate('任務開始前')

    def hp_gate(self, where: str) -> int:
        """補血檢查（任務開始前、BOSS 戰後下一片之前）：隊長 HUD HP < --hp-min，或全隊（bag.hps）任一人 < --team-hp-min → heal 全隊（小護士補整隊）+ team.form。
        全隊讀不到（背包打不開 / 選不到角色）→ 只看隊長並記事件；某人 HP 讀不出 = 不知道，不單獨觸發補血"""
        hp = self.T.hp_pct()
        self.info['hp_pct'] = hp
        low = {}
        if hp is not None and hp < self.o['hp_min']:
            low[LEADER] = hp
        if self.o.get('team_hp_min', TEAM_HP_MIN) > 0:
            rc, pct = self.T.team_hp()
            if rc in (uikit.EXIT_UNKNOWN_SCREEN, uikit.EXIT_HALT):
                return rc
            self.info['team_hp'] = pct
            if rc or not pct:
                event(f'{where}：讀不到全隊 HP（bag rc={rc}）→ 只看隊長 HP {hp}%')
            else:
                unread = [r for r, v in pct.items() if v is None]
                low.update({r: v for r, v in pct.items() if v is not None and v < self.o['team_hp_min']})
                event(f'{where}：全隊 HP {pct}' + (f'（讀不出 {unread}）' if unread else ''))
        if not low:
            return 0
        event(f'{where}：HP 偏低 {low}（隊長門檻 {self.o["hp_min"]}%、全隊門檻 {self.o.get("team_hp_min", TEAM_HP_MIN)}%）→ 補血（小護士補整隊）')
        try:
            self.T.heal()
        except RuntimeError as e:
            return self.fail(EXIT_HANDOVER, f'補血失敗：{e}')
        self.info['heals'] = self.info.get('heals', 0) + 1
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
        rc = self.preflight_task(d)
        if rc:
            return rc
        if self.o.get('trust_progress', True) and ts.get('state') == 'done' and time.time() - ts.get('ended_ts', 0) < DONE_TRUST_S:
            event(f'任務 {tid}「{d["detail"]}」進度檔記錄已完成（{time.strftime("%H:%M:%S", time.localtime(ts["ended_ts"]))}）→ 直接跳過，不開詳情')
            ts['skipped'] = True
            ts['detail_opens'] = 0
            return 0
        ts.pop('skipped', None)
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
                return self.verify_all(d, ts)
            return 0
        t0 = time.time()
        ts.update(state='running', started=time.strftime('%H:%M:%S'), slices=0)
        self.save()
        if state == 'accepted':
            self.team_ok_at = 0.0                                      # 傳送過 → 之前的確認不算
            rc = self.form('接取後')                                    # 傳送後確認隊伍還在
            if rc:
                return self.fail(EXIT_HANDOVER, f'接取後 team.form 失敗 rc={rc}')
            event(f'任務 {tid} 已接取（不重開詳情，直接點追蹤欄卡片）')
        team_retry = 0
        rewarps = 0
        relogins = 0
        boss_retries = 0
        for k in range(self.o['max_slices']):
            if time.time() - t0 > self.o['max_min'] * 60:
                return self.fail(EXIT_SLICES, f'任務 {tid} 超過 {self.o["max_min"]} 分鐘仍未完成')
            ts['slices'] = k + 1
            self.ensure_dragon()
            from_pending = self.pending is not None
            step, kind, sd = self.special_step(d)
            if kind == 'manual':
                return self.fail(EXIT_MANUAL, f'任務 {tid} 步 {step} kind=manual：停下交人', step=step)
            if kind == 'walk' and from_pending:                         # 自動巡路優先：quest.py 回 3（追蹤沒反應）才用 walk 備援（2026-10-11 實測點追蹤會傳送 + 巡路）
                rc = self.do_walk(d, step, sd)
                if rc:
                    return rc
            qargs = ['--task', track, '--max-seconds', self.o['slice_s']]
            if self.team_fresh():
                qargs.append('--team-fresh')                           # 剛驗過隊伍：quest.py 開始前不再開切換面板（之後的領獎後 / 任務戰後檢查照舊）
            rc, tail = T.quest(qargs, self.o['slice_s'] + WALK_CAP_S + 120)
            self.team_ok_at = time.time() if rc == 37 else 0.0         # 37 = quest.py 剛驗過滿 5 人；其他結束方式隊伍狀態未知
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
            if act == 'irrev':
                T.snap('questrun-irrev')
                return self.fail(EXIT_IRREV, f'任務 {tid}：對話含不可逆字樣（quest.py 39），沒按、對話框維持開著，請人看圖', quest_rc=rc)
            if act == 'stall':
                return self.fail(EXIT_STALL, f'任務 {tid}：對話無進展（quest.py 33）', quest_rc=rc)
            if act == 'battle':
                return self.fail(EXIT_BATTLE, f'任務 {tid}：完整戰鬥自動戰鬥卡住（quest.py 25）', quest_rc=rc)
            if act in ('knocked', 'boss_team'):                         # 38 BOSS 後不滿 5 人 / 21 被打飛 → bossretry 自動補人（psa-team-check-after-boss）
                what = '被打飛回村（quest.py 21）' if act == 'knocked' else 'BOSS 戰後隊伍不滿 5 人（quest.py 38）'
                if not self.o.get('boss_retry', True):
                    return self.fail(EXIT_TEAM, f'任務 {tid}：{what}；--no-boss-retry，請依 psa-team-check-after-boss 手動處理', quest_rc=rc)
                if boss_retries >= BOSS_RETRY_MAX:
                    return self.fail(EXIT_TEAM, f'任務 {tid}：{what}；bossretry 已用 {boss_retries} 次，停手交人', quest_rc=rc)
                boss_retries += 1
                event(f'任務 {tid}：{what} → bossretry 第 {boss_retries}/{BOSS_RETRY_MAX} 次')
                brc, binfo = T.boss_retry(track)
                self.info.setdefault('boss_retry', []).append(binfo)
                if brc in (uikit.EXIT_UNKNOWN_SCREEN, uikit.EXIT_HALT):
                    return brc
                if brc:
                    return self.fail(EXIT_TEAM, f'任務 {tid}：{what}；bossretry 退出碼 {brc}：{(binfo or {}).get("msg", "")}', quest_rc=rc, boss_retry_rc=brc)
                self.team_ok_at = time.time()                          # bossretry 最後 team.check 滿 5 人
                rc = self.hp_gate(f'任務 {tid} 補人後')
                if rc:
                    return rc
                continue
            if act == 'boss':
                event(f'任務 {tid}：BOSS 戰贏且滿 5 人，下一片')
                team_retry = 0
                rc = self.hp_gate(f'任務 {tid} BOSS 戰後')            # 連戰不補血 → 隊員被打死踢隊（2026-10-12 四寶玉之謎 4 次 38）
                if rc:
                    return rc
                continue
            if act == 'team':
                if team_retry >= 3:                                    # 對話剛收起時切換面板偶爾打不開（2026-10-11 小豬愛情故事最後一段），多給幾次
                    return self.fail(EXIT_HANDOVER, f'任務 {tid}：隊伍檢查連續失敗（quest.py {rc}）', quest_rc=rc)
                team_retry += 1
                rc2 = self.form('隊伍檢查失敗後')
                if rc2:
                    return self.fail(EXIT_HANDOVER, f'任務 {tid}：team.form 失敗 rc={rc2}')
                continue
            if act == 'no_track':
                st2, kind2, sd2 = self.special_step(d)
                if kind2 == 'walk':
                    self.pending = (st2, kind2, sd2)
                    continue                                           # 下一圈 special_step 會走 walk
                if rewarps >= 2 and relogins < 1 and self.T.vs_stuck():  # 刷新 + 點追蹤都無效且全隊頭上 VS 牌卡住（無戰鬥介面）→ 主動全員重登（碧青 12 樓 2026-10-12）
                    relogins += 1
                    event(f'任務 {tid}：VS 牌卡住（無戰鬥介面、刷新 {rewarps} 次無效）→ 全員重登（relogin.py）')
                    rr = self.T.relogin()
                    event(f'任務 {tid}：全員重登 rc={rr}')
                    if rr:
                        return self.fail(EXIT_STEP, f'任務 {tid}：VS 卡住後全員重登失敗 rc={rr}', quest_rc=rc)
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
                    return self.verify_all(d, ts)
                if act == 'check' and time_up(tail):                    # quest.py 只是 slice 時間到（任務還在追蹤欄、沒說完成）：不開詳情，直接下一片；
                    continue                                           # 真的完成會在下一片由 quest.py 回 5（追蹤欄沒有該任務）或「任務完成」→ 那時才讀詳情確認
                rc, s2 = self.status_of(d)                              # 沒有「任務完成」字樣、也不是單純時間到 → 才有疑慮 → 才讀一次詳情
                self.opens(ts)
                if rc:
                    return rc if rc in (uikit.EXIT_UNKNOWN_SCREEN, uikit.EXIT_HALT) else self.fail(EXIT_PREFLIGHT, f'{d["detail"]} 完成確認讀狀態失敗 rc={rc}')
                if s2 == DONE:
                    ts.update(state='done', ended=time.strftime('%H:%M:%S'), ended_ts=time.time(), secs=int(time.time() - t0))
                    self.save()
                    event(f'任務 {tid}「{d["detail"]}」已完成（{int(time.time() - t0)} 秒、{k + 1} 片）')
                    return self.verify_all(d, ts)
                if act == 'gone':
                    return self.fail(EXIT_STEP, f'任務 {tid}：quest.py 找不到追蹤列表上的任務，詳情狀態是 {s2}', quest_rc=rc, status=s2)
                if s2 == PENDING:
                    return self.fail(EXIT_STEP, f'任務 {tid}：詳情狀態是待接取（沒接成？）', status=s2)
                continue                                               # 進行中：下一片
            if rc == 19 and rewarps < 6:                               # 自動巡路在出口附近打轉：刷新角色 + 走上最近的換圖出口，再重點追蹤
                rewarps += 1
                try:
                    r = self.T.unstick_exit()
                    event(f'任務 {tid}：巡路卡住（quest.py 19）→ 刷新 + 走上附近出口 → {r}，重點追蹤（第 {rewarps} 次）')
                except Exception as e:                                 # noqa: BLE001
                    event(f'任務 {tid} 走上附近出口失敗：{e}')
                    r = None
                if r:
                    continue
            if rc == 19:
                return self.fail(EXIT_STEP, f'任務 {tid}：自動巡路卡住，quest.py 自動點地面解卡 3 次仍卡（quest.py 19），請人看 snap walk-stuck', quest_rc=rc)
            return self.fail(EXIT_STEP, f'任務 {tid}：quest.py 非預期退出碼 {rc}', quest_rc=rc)
        return self.fail(EXIT_SLICES, f'任務 {tid}：{self.o["max_slices"]} 片後仍未完成')

    def verify_all(self, d, ts) -> int:
        """隊長判完成後逐人驗（隊長本人剛確認過，不再讀）：有人沒「已完成」→ bossretry --who 落後者 → 再讀那幾個人；仍不行 108"""
        if not self.o.get('verify_all', True):
            return 0
        T, tid, detail = self.T, d['id'], d['detail']
        roles = [r for r in ALL_ROLES if r != LEADER]
        for attempt in range(2):                                    # 0 = 完成後第一次驗；1 = bossretry 補人後再驗
            rc, res = T.status_all(detail, roles)
            self.info.setdefault('verify', []).append({'roles': roles, 'rc': rc, 'res': res})
            if rc in (uikit.EXIT_UNKNOWN_SCREEN, uikit.EXIT_HALT):
                return rc
            unread = [r for r in roles if not (res or {}).get(r)]
            if unread:
                return self.fail(EXIT_LAGGARD, f'任務 {tid}：逐人驗證讀不到 {unread} 的任務詳情（status_all rc={rc}），無法確認是否都完成；不盲打', laggards=unread)
            sts = {r: res[r].get(detail) for r in roles}
            lag = [r for r in roles if sts[r] != DONE]
            event(f'任務 {tid}「{detail}」逐人驗證{"（補人後）" if attempt else ""}：{sts}')
            if not lag:
                ts['all_done'] = True
                self.save()
                return 0
            self.info['laggards'] = lag
            pend = [r for r in lag if sts[r] != DOING]
            if pend:
                return self.fail(EXIT_LAGGARD, f'任務 {tid}：{pend} 的狀態是 {[sts[r] for r in pend]}（不是進行中，bossretry 幫不上），停手交人', laggards=lag)
            if attempt or not self.o.get('boss_retry', True):
                why = '補人後仍沒完成' if attempt else '--no-boss-retry'
                return self.fail(EXIT_LAGGARD, f'任務 {tid}：{lag} 仍是進行中（{why}），停手交人', laggards=lag)
            event(f'任務 {tid}：{lag} 沒完成 → bossretry --who（落後者當隊長組 5 人重打 → 切回 DKBO 重組）')
            brc, binfo = T.boss_retry(d['track'], who=lag)
            self.info.setdefault('boss_retry', []).append(binfo)
            if brc in (uikit.EXIT_UNKNOWN_SCREEN, uikit.EXIT_HALT):
                return brc
            if brc:
                return self.fail(EXIT_LAGGARD, f'任務 {tid}：{lag} 沒完成，bossretry 退出碼 {brc}：{(binfo or {}).get("msg", "")}', laggards=lag, boss_retry_rc=brc)
            self.team_ok_at = time.time()                              # bossretry 最後 team.check 滿 5 人
            roles = lag
        return EXIT_LAGGARD

    def write_log(self, d, t0: float):
        ts = self.st['tasks'].get(str(d['id']), {})
        if ts.get('skipped'):
            return
        lines = [f'\n## {d["id"]} {d["detail"]} — questrun.py 自動跑完（{time.strftime("%Y-%m-%d %H:%M")}）',
                 f'- 任務詳情開啟 {ts.get("detail_opens")} 次；耗時 {int(time.time() - t0)} 秒（{ts.get("started")}～{ts.get("ended")}），quest.py {ts.get("slices")} 片，最後退出碼 {ts.get("last_rc")}；'
                 f'龍王的守護本任務吃 {self.task_dragons} 顆（本次 run 共 {self.run_dragons} 顆；剩的都存回公共倉庫）',
                 '- 手動介入：0 次（若有，人工在這裡補記）']
        if self.warnings:
            lines.append('- 警告：' + '；'.join(self.warnings))
        try:
            with open(QUEST_LOG, 'a', encoding='utf-8') as f:
                f.write('\n'.join(lines) + '\n')
        except OSError:
            pass


def run(ids=None, dry_run: bool = False, after: str = 'grind', tools=None, use_dragon: bool = True, spot: str = DEFAULT_SPOT,
        max_slices: int = MAX_SLICES, slice_s: int = SLICE_S, max_min: int = MAX_MIN, hp_min: int = HP_MIN, trust_progress: bool = True,
        team_hp_min: int = TEAM_HP_MIN, boss_retry: bool = True, verify_all: bool = True, verify_skipped: bool = False) -> int:
    LAST.clear()
    defs, bad = questdefs.resolve(ids)
    if bad:
        print(f'questrun：不認得的任務 ID {bad}（questdefs 有：{questdefs.DEFAULT_ORDER}）', file=sys.stderr)
        return uikit.EXIT_USAGE
    if after not in ('grind', 'none'):
        print('questrun：--after 要 grind 或 none', file=sys.stderr)
        return uikit.EXIT_USAGE
    opts = dict(after=after, dragon=use_dragon, spot=spot, max_slices=max_slices, slice_s=slice_s, max_min=max_min, hp_min=hp_min, trust_progress=trust_progress,
                team_hp_min=team_hp_min, boss_retry=boss_retry, verify_all=verify_all, verify_skipped=verify_skipped)
    if dry_run:
        print_plan(defs, opts)
        return 0
    T = tools or Tools()
    r = Run(T, opts)
    event(f'開始：任務 {[d["id"] for d in defs]}，選項 {opts}')
    rc = r.handover()
    done = []
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
    if not rc and after == 'grind':
        event(f'全部完成 → 恢復掛機：grind.py start --spot {spot}')
        rc = T.grind_start(spot)
        if rc:
            r.fail(rc, f'恢復掛機失敗 grind rc={rc}')
    LAST.update(ok=rc == 0, rc=rc, done=done, info=r.info, warnings=r.warnings, dragon_used=r.run_dragons, dragon_used_total=r.st.get('dragon_used', 0))
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
    p = sub.add_parser('plan')
    p.add_argument('ids', nargs='*')
    p.add_argument('--after', default='grind', choices=['grind', 'none'])
    p.add_argument('--no-dragon', action='store_true')
    p.add_argument('--spot', default=DEFAULT_SPOT)
    p = sub.add_parser('status')
    p.add_argument('ids', nargs='*')
    p.add_argument('--role', default='', help='逐人讀：all 或 DKBO3,DKBO5（每人 char.switch 一次，最後切回 DKBO）')
    p = sub.add_parser('run')
    p.add_argument('ids', nargs='*')
    p.add_argument('--dry-run', action='store_true')
    p.add_argument('--after', default='grind', choices=['grind', 'none'])
    p.add_argument('--no-dragon', action='store_true')
    p.add_argument('--spot', default=DEFAULT_SPOT)
    p.add_argument('--max-slices', type=int, default=MAX_SLICES)
    p.add_argument('--slice-s', type=int, default=SLICE_S)
    p.add_argument('--max-min', type=int, default=MAX_MIN)
    p.add_argument('--hp-min', type=int, default=HP_MIN)
    p.add_argument('--team-hp-min', type=int, default=TEAM_HP_MIN, help='全隊任一人 HP 低於這個 %% 就補血（任務開始前 / BOSS 戰後；0 = 不讀全隊，只看隊長）')
    p.add_argument('--no-boss-retry', action='store_true', help='BOSS 戰後不滿 5 人（38 / 21）不自動補人，直接 114 停手')
    p.add_argument('--no-trust-progress', action='store_true', help='不信進度檔的「已完成」（預設 2 小時內的完成記錄直接跳過）')
    p.add_argument('--no-verify-all', action='store_true', help='任務完成後不逐人驗證（預設驗：其他 4 人逐一讀詳情，有人沒完成就 bossretry --who）')
    p.add_argument('--verify-skipped', action='store_true', help='詳情一開就已完成而跳過的任務也逐人驗（預設只驗本次跑完的）')
    a = ap.parse_args()
    if a.cmd == 'status':
        return cmd_status(a.ids, a.role)
    dry = a.cmd == 'plan' or a.dry_run
    kw = dict(max_slices=getattr(a, 'max_slices', MAX_SLICES), slice_s=getattr(a, 'slice_s', SLICE_S),
              max_min=getattr(a, 'max_min', MAX_MIN), hp_min=getattr(a, 'hp_min', HP_MIN),
              team_hp_min=getattr(a, 'team_hp_min', TEAM_HP_MIN), boss_retry=not getattr(a, 'no_boss_retry', False),
              verify_all=not getattr(a, 'no_verify_all', False), verify_skipped=getattr(a, 'verify_skipped', False))
    rc = run(a.ids, dry, a.after, use_dragon=not a.no_dragon, spot=a.spot, trust_progress=not getattr(a, 'no_trust_progress', False), **kw)
    if not dry:
        print(json.dumps(LAST, ensure_ascii=False, default=str))
    return rc


if __name__ == '__main__':
    sys.exit(main())
