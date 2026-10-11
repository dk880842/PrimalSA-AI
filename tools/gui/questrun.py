#!/usr/bin/env python3
"""1.82 任務驅動器（P2：驅動器骨架 + 純巡路任務；計畫 notes/plan-182-script.md）。只用標準函式庫。

用法（專案根目錄；WSL / Windows 原生相同）：
  uv run --no-project python tools/gui/questrun.py plan [任務ID …]            # 不碰遊戲：印交接 / 每任務步驟 / 指令 / 預估 / 退出碼（沒給 ID = questdefs 全部）
  uv run --no-project python tools/gui/questrun.py run 2999 2017 2015 [--dry-run] [--after grind|none] [--no-dragon] [--spot 地雷區]
        [--max-slices 12] [--slice-s 300] [--max-min 30] [--hp-min 50]
  uv run --no-project python tools/gui/questrun.py status [任務ID …]          # 唯讀（要開 / 關任務詳情面板）：印各任務目前狀態
  可 import：questrun.run(ids, dry_run=False, after='grind', tools=None, ...) → 退出碼；結果 dict 在 questrun.LAST

任務資料在 questdefs.py（id / 詳情標題 / 追蹤標題 / 特殊步驟）。全部組隊模式（使用者 2026-10-11）；解任務靠遊戲自動巡路（quest.py 點追蹤、對話按確認、每場戰鬥刷新角色）。

流程：
  交接（整次 run 一次）  follow 還在跑就停（已停用，只防呆）→ 關原地遇敵 + 等戰鬥結束 → char.ensure DKBO → team.form 滿 5 人
  每個任務
    1 preflight    背包空位（defs.bag_slots）、隊長 HP < --hp-min% → heal 後重組隊
    2 接取         team.form → questdetail.accept(skip_ok, verify=False)：**整個任務只開一次詳情**，同一趟捲動讀狀態（已完成 → 跳過、進行中 → 續跑、待接取 → 傳送 → NPC 對話 → 接受，不重開詳情驗證，看對話框收起）；失敗 119
    3 跑步驟       迴圈（每片 ≤ --slice-s 秒，總計 ≤ --max-min 分，片數 ≤ --max-slices）：
                   龍王的守護（人形圖示不在才吃：depot_use 公共倉庫取出 → 吃 1 顆 → 剩的存回；吃完再關原地遇敵）
                   → defs.steps 有 manual 步驟時 quest.read_step_no 讀步號 → 115；kind=walk 是備援：quest.py 先點追蹤讓遊戲自動巡路，只有回 3（追蹤沒反應 = 原地不動）才用 questhandlers.walk_step 走到定點
                   → quest.py --task <追蹤標題> --max-seconds N，依退出碼分支（見下）
    4 收尾         進度檔記已完成（2 小時內）→ 重跑直接跳過；quest.py 印「任務完成」（領獎後追蹤欄沒有該任務）即完成，不開詳情；沒有該字樣才讀一次詳情確認 → 進度檔 tools/.cache/questrun.json、notes/quest-log.md 追加一筆
  交接回去（全部成功才做）--after grind（預設）= grind.py start --spot 地雷區（不重啟 follow）；none = 不動。**失敗退出一律不恢復掛機**（畫面狀態未知）

quest.py 退出碼分支：0 → tail 有「任務完成」= 結束；否則讀一次詳情：已完成 = 結束、進行中 = 下一片；37 BOSS 戰贏且滿 5 人 → 下一片；38 BOSS 後隊伍不滿 → 114 停手（重打流程 P3，現在照 psa-team-check-after-boss 手動）；
  （2026-10-11）quest.py 的 slice 時限不計自動巡路時間（它結束時印「走路不計時 N 秒」，questrun 把 N 加回 t0 = 不計入 --max-min；子程序逾時 = slice + WALK_CAP_S + 120）；
  quest.py 回 0 且 tail 有「時間到」（單純 slice 到期、任務還在追蹤欄）→ 不開詳情，直接下一片（完成由下一片 quest.py「任務完成」或回 5 時才讀詳情確認）；回 0 但沒有「任務完成」也不是「時間到」（模糊）才讀一次詳情
  3 追蹤沒反應 → 有 walk 步驟先走，否則 112；5 找不到任務 → 看詳情狀態（已完成 = 結束，否則 112）；30 / 32 隊伍不符 → 原地 form()（失敗先關誤開面板再重試 3 次）再起一片，最多 3 輪仍不行才 111（不退出整套）；
  33 對話無進展 → 117；25 完整戰鬥自動戰鬥卡住 → 118；39 不可逆對話 → 116（不放行）；2 不認得的畫面（疑似驗證視窗）→ 9 停手通知（鐵則 5）；10 斷線（netwatch）→ 10；21 被打飛 → 114；其他 → 112

退出碼（共用 0 / 1 / 2 / 8 / 9 / 10 見 uikit；其他工具 20～107、120～129；questrun 自己 110～119）：
  110 preflight 失敗（任務不認得 / 讀不到狀態 / 背包空位不足 / 當前角色不是 DKBO）
  111 交接 / 組隊失敗（follow 停不掉、關遇敵、team.form、補血）
  112 步驟卡住（追蹤沒反應又沒 walk 步驟、walk 走不到、找不到任務但狀態不是已完成、quest.py 非預期退出碼）
  113 片數 / 時間上限到了任務還沒完成
  114 BOSS 後隊伍不滿 / 被打飛（P3 才有自動重打）
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
import charstate  # noqa: E402
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

LEADER = rebirth.LEADER
ALL_ROLES = rebirth.ALL_ROLES
DRAGON = rebirth.DRAGON
DRAGON_REEAT_S = rebirth.DRAGON_REEAT_S
SLICE_S, MAX_SLICES, MAX_MIN, HP_MIN = 300, 12, 30, 50
WALK_CAP_S = 900.0              # quest.py 單次連續自動巡路最多不計時這麼久（要與 quest.WALK_CAP_S 相同；子程序逾時 = slice + 這個 + 120）
DEFAULT_SPOT = '地雷區'
FORM_TRIES = 3                  # team.form 原地重試次數（小錯不退出）
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

    def grind_start(self, spot):
        import grind
        return grind.run('start', spot)


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


# ---------------------------------------------------------------- 純函式
def classify(rc: int, tail=()) -> str:
    """quest.py 退出碼 → 動作字串（測試直接餵）：done? / boss / stuck3 / gone / team / stall / battle / irrev / verify / halt / knocked / other"""
    return {0: 'check', 37: 'boss', 38: 'boss_team', 3: 'no_track', 5: 'gone', 30: 'team', 32: 'team', 33: 'stall', 25: 'battle',
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
    for ln in ('follow 還在跑就 grind.py follow --stop（已停用，只防呆）', '關原地遇敵 + 等戰鬥結束', 'char.ensure DKBO（面板左欄「當前登錄」）',
               'team.form 滿 5 人'):
        print('  - ' + ln)
    for d in defs:
        print(f'[任務 {d["id"]}] {d["detail"]}（追蹤標題「{d["track"]}」，接取 {d["accept_npc"]}，{d["steps_total"]} 步，預估 {d.get("est_min", "?")} 分）')
        print('  - team.form → questdetail.accept（只開一次詳情）：已完成 → 跳過；待接取 → 接受（不重開詳情）；進行中 → 續跑')
        if d.get('bag_slots'):
            print(f'  - 背包空位：5 人各 ≥ {d["bag_slots"]} 格（bag.find_items）')
        print(f'  - 隊長 HP < {opts["hp_min"]}% → heal.heal_trip --no-return + team.form')
        for st, sd in sorted((d.get('steps') or {}).items()):
            if sd['kind'] == 'walk':
                print(f'  - 步 {st}：kind=walk（備援）：先讓遊戲自動巡路，quest.py 回 3 才走到 {sd["map"]}:{sd["xy"][0]},{sd["xy"][1]}'
                      f'（{sd.get("npc", "")}；walk.py 中斷外層重試）')
            else:
                print(f'  - 步 {st}：kind={sd["kind"]} → 停下交人（115）')
        if d.get('boss'):
            print('  - 有任務戰 / BOSS 戰：quest.py 預設模式打完回 37（滿 5 人 → 繼續）/ 38（不滿 → 114，重打流程 P3）')
        if opts.get('dragon', True):
            print(f'  - 每片前：龍王的守護（buff 列看不到人形圖示才吃；depot_use 公共倉庫取出 → 吃 → 存回 → 關遇敵）')
        print(f'  - 迴圈：quest.py --task {d["track"]} --max-seconds {opts["slice_s"]}（≤ {opts["max_slices"]} 片、≤ {opts["max_min"]} 分），依退出碼分支')
        print('  - 收尾：quest.py「任務完成」（追蹤欄沒有該任務）→ 進度檔 + notes/quest-log.md（沒有該字樣才開詳情確認）')
    if opts['after'] == 'grind':
        print(f'[交接回去] 全部成功 → grind.py start --spot {opts["spot"]}（不重啟 follow）；失敗退出不恢復')
    else:
        print('[交接回去] --after none：不動')
    print('退出碼：110 preflight 111 交接/組隊 112 步驟卡住 113 片數/時間上限 114 BOSS後隊伍不滿 115 manual 116 不可逆對話 117 對話無進展 118 戰鬥卡住 119 接取失敗；9 驗證視窗 10 斷線')


# ---------------------------------------------------------------- 驅動器
class Run:
    def __init__(self, T, opts: dict):
        self.T, self.o = T, opts
        self.st = load_progress()
        self.st.setdefault('tasks', {})
        self.info: dict = {}
        self.warnings: list = []
        self.pending = None

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
        """team.form 原地重試（可恢復的小錯：切換面板偶爾讀到 0 張卡片 rc 42、誤開面板）：失敗 → 關誤開面板 → 等 2 秒 → 再組；
        9（驗證視窗）/ 10（斷線）立即透傳；超過 tries 次才回最後一個失敗碼"""
        rc = 0
        for i in range(tries):
            rc = self.T.team_form()
            if not rc or rc in (uikit.EXIT_UNKNOWN_SCREEN, uikit.EXIT_HALT):
                return rc
            event(f'{what}：team.form 失敗 rc={rc}（{i + 1}/{tries}）→ 關誤開面板、2 秒後原地重試')
            cs = getattr(self.T, 'close_stray', None)
            if cs:
                try:
                    cs()
                except Exception as e:
                    event(f'close_stray 例外：{e}')
            self.T.sleep(2)
        return rc

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
        self.st['dragon_used'] = self.st.get('dragon_used', 0) + 1
        self.run_dragons = getattr(self, 'run_dragons', 0) + 1
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
        rc, cur = T.current()
        if rc or not cur or not charstate.same(cur, LEADER):
            rc2 = T.char_ensure(LEADER)
            if rc2:
                return self.fail(EXIT_HANDOVER, f'當前角色不是 {LEADER}（讀到 {cur}），切換失敗 rc={rc2}')
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
        hp = self.T.hp_pct()
        self.info['hp_pct'] = hp
        if hp is not None and hp < self.o['hp_min']:
            event(f'隊長 HP {hp}% < {self.o["hp_min"]}% → 補血')
            try:
                self.T.heal()
            except RuntimeError as e:
                return self.fail(EXIT_HANDOVER, f'補血失敗：{e}')
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
        if step is None or step == self.T.gone():
            return None, 'default', None
        sd = d['steps'].get(step)
        return step, (sd['kind'] if sd else 'default'), sd

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
        rc = self.form('接取前')                                       # 接取 / 對話前一定先快速組隊；切換面板偶爾讀到 0 張卡片（rc 42）→ form 內原地重試
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
            return 0
        t0 = time.time()
        ts.update(state='running', started=time.strftime('%H:%M:%S'), slices=0)
        self.save()
        if state == 'accepted':
            rc = self.form('接取後')                                    # 傳送後確認隊伍還在
            if rc:
                return self.fail(EXIT_HANDOVER, f'接取後 team.form 失敗 rc={rc}')
            event(f'任務 {tid} 已接取（不重開詳情，直接點追蹤欄卡片）')
        team_retry = 0
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
            rc, tail = T.quest(['--task', track, '--max-seconds', self.o['slice_s']], self.o['slice_s'] + WALK_CAP_S + 120)
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
            if act == 'knocked':
                return self.fail(EXIT_TEAM, f'任務 {tid}：被打飛回村（quest.py 21），重打流程 P3', quest_rc=rc)
            if act == 'boss_team':
                return self.fail(EXIT_TEAM, f'任務 {tid}：BOSS 戰後隊伍不滿 5 人（quest.py 38）；重打流程 P3，現在請依 psa-team-check-after-boss 手動處理', quest_rc=rc)
            if act == 'boss':
                event(f'任務 {tid}：BOSS 戰贏且滿 5 人，下一片')
                team_retry = 0
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
                return self.fail(EXIT_STEP, f'任務 {tid}：追蹤沒反應（quest.py 3）且目前步驟（{st2}）沒有 walk 設定', quest_rc=rc)
            if act in ('check', 'gone'):
                if act == 'check' and any('任務完成' in str(x) for x in tail):   # quest.py：領獎後追蹤欄掃完沒有該任務 → 完成，不開詳情
                    ts.update(state='done', ended=time.strftime('%H:%M:%S'), ended_ts=time.time(), secs=int(time.time() - t0))
                    self.save()
                    event(f'任務 {tid}「{d["detail"]}」已完成（quest.py 任務完成；{int(time.time() - t0)} 秒、{k + 1} 片）')
                    return 0
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
                    return 0
                if act == 'gone':
                    return self.fail(EXIT_STEP, f'任務 {tid}：quest.py 找不到追蹤列表上的任務，詳情狀態是 {s2}', quest_rc=rc, status=s2)
                if s2 == PENDING:
                    return self.fail(EXIT_STEP, f'任務 {tid}：詳情狀態是待接取（沒接成？）', status=s2)
                continue                                               # 進行中：下一片
            return self.fail(EXIT_STEP, f'任務 {tid}：quest.py 非預期退出碼 {rc}', quest_rc=rc)
        return self.fail(EXIT_SLICES, f'任務 {tid}：{self.o["max_slices"]} 片後仍未完成')

    def write_log(self, d, t0: float):
        ts = self.st['tasks'].get(str(d['id']), {})
        if ts.get('skipped'):
            return
        lines = [f'\n## {d["id"]} {d["detail"]} — questrun.py 自動跑完（{time.strftime("%Y-%m-%d %H:%M")}）',
                 f'- 任務詳情開啟 {ts.get("detail_opens")} 次；耗時 {int(time.time() - t0)} 秒（{ts.get("started")}～{ts.get("ended")}），quest.py {ts.get("slices")} 片，最後退出碼 {ts.get("last_rc")}；'
                 f'龍王的守護累計吃 {self.st.get("dragon_used", 0)} 顆（剩的都存回公共倉庫）',
                 '- 手動介入：0 次（若有，人工在這裡補記）']
        if self.warnings:
            lines.append('- 警告：' + '；'.join(self.warnings))
        try:
            with open(QUEST_LOG, 'a', encoding='utf-8') as f:
                f.write('\n'.join(lines) + '\n')
        except OSError:
            pass


def run(ids=None, dry_run: bool = False, after: str = 'grind', tools=None, use_dragon: bool = True, spot: str = DEFAULT_SPOT,
        max_slices: int = MAX_SLICES, slice_s: int = SLICE_S, max_min: int = MAX_MIN, hp_min: int = HP_MIN, trust_progress: bool = True) -> int:
    LAST.clear()
    defs, bad = questdefs.resolve(ids)
    if bad:
        print(f'questrun：不認得的任務 ID {bad}（questdefs 有：{questdefs.DEFAULT_ORDER}）', file=sys.stderr)
        return uikit.EXIT_USAGE
    if after not in ('grind', 'none'):
        print('questrun：--after 要 grind 或 none', file=sys.stderr)
        return uikit.EXIT_USAGE
    opts = dict(after=after, dragon=use_dragon, spot=spot, max_slices=max_slices, slice_s=slice_s, max_min=max_min, hp_min=hp_min, trust_progress=trust_progress)
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
    LAST.update(ok=rc == 0, rc=rc, done=done, info=r.info, warnings=r.warnings, dragon_used=r.st.get('dragon_used', 0))
    event(f'結束 rc={rc}，完成 {done}' + ('；失敗退出，不恢復掛機' if rc else ''))
    r.save()
    return rc


def cmd_status(ids) -> int:
    defs, bad = questdefs.resolve(ids)
    if bad:
        print(f'questrun：不認得的任務 ID {bad}', file=sys.stderr)
        return uikit.EXIT_USAGE
    import questdetail
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
    p.add_argument('--no-trust-progress', action='store_true', help='不信進度檔的「已完成」（預設 2 小時內的完成記錄直接跳過）')
    a = ap.parse_args()
    if a.cmd == 'status':
        return cmd_status(a.ids)
    dry = a.cmd == 'plan' or a.dry_run
    kw = dict(max_slices=getattr(a, 'max_slices', MAX_SLICES), slice_s=getattr(a, 'slice_s', SLICE_S),
              max_min=getattr(a, 'max_min', MAX_MIN), hp_min=getattr(a, 'hp_min', HP_MIN))
    rc = run(a.ids, dry, a.after, use_dragon=not a.no_dragon, spot=a.spot, trust_progress=not getattr(a, 'no_trust_progress', False), **kw)
    if not dry:
        print(json.dumps(LAST, ensure_ascii=False, default=str))
    return rc


if __name__ == '__main__':
    sys.exit(main())
