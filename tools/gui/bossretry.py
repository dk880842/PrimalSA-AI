#!/usr/bin/env python3
"""BOSS 戰後隊伍不滿 5 人（quest.py 38 / 21，questrun 114）→ 被打飛的人自己追上進度 → 切回 DKBO 重組 5 人。只用標準函式庫。

規則來源：memory psa-team-check-after-boss（2026-10-11 使用者規定）—— 被打飛的人當隊長（char.py switch）按任務追蹤，
遊戲會自動傳送回 BOSS 處重打；補完後切回 DKBO、team.py form、check 滿 5 人才往下；重打失敗或仍不滿就停手回報。
這是「當前角色維持 DKBO」的例外，結束（不論成敗）一律切回 DKBO。

用法（專案根目錄；WSL / Windows 原生相同）：
  uv run --no-project python tools/gui/bossretry.py plan --track 琉璃洞窟                 # 不碰遊戲：印流程與退出碼
  uv run --no-project python tools/gui/bossretry.py run --track 琉璃洞窟 [--max-tries 2] [--max-slices 6] [--slice-s 300] [--hp-min 50] [--dry-run]
  uv run --no-project python tools/gui/bossretry.py status                                 # 唯讀：開切換面板，印隊長 / 不在隊的人
  可 import：bossretry.run(track, tools=None, ...) → 退出碼；結果 dict 在 bossretry.LAST
  --dry-run = 同 plan（完全不碰遊戲）。重跑 = 續跑：每次都從現場狀態（隊伍卡片、各人任務步號）重新判斷，不靠進度檔。

流程（追趕法：被打飛的人的任務步號追到「留在隊上的隊長」的步號為止）：
  1 確認   team.check(5) = 0 → 其實沒缺人（38 可能只是讀不到）→ 回 0、不動
  2 找人   切換面板卡片：label 不是隊長 / 隊員的 = 掉隊者（名字讀不出 → 140）；隊長 = 參考者 ref（沒有隊長 = 全滅 / 全員單人 → 140）
  3 參考步號 當前切到 ref（通常就是 DKBO，不用切）→ quest.read_step_no(追蹤標題)；讀不到重讀 1 次，仍 None → 142（無法判斷誰落後，不盲打）
  4 每個掉隊者（依序，各自單人；team.form 不能指定子隊伍成員，所以多人掉隊不組小隊，逐一單人追）：
      char.switch(掉隊者) → 讀他的步號：== ref（或兩者都 GONE）→ 不用重打（只補血）
      HUD HP < --hp-min → heal.heal_trip --no-return（小護士；被打飛通常 HP 1）
      落後 → 迴圈（≤ --max-slices 片）：quest.py --task <追蹤> --max-seconds N --team-size 1（預設模式：點追蹤 = 自動傳送 / 巡路，
             對話按確認、任務戰開自動戰鬥 + 刷新，BOSS 戰後停 37）→ 讀步號：== ref 完成；BOSS 戰後步號沒變 = 輸了一次 → 補血再打
             （≤ --max-tries 次）；被打飛（21）同樣算一次
  5 收尾   ref 不是 DKBO → 切到 ref 解散舊隊伍；char.ensure DKBO → team.form(regroup=True) → team.check(5) = 0 才回 0
  任何失敗（含中途）都會先 char.ensure DKBO 再回退出碼（9 驗證視窗 / 10 斷線除外：立即停、不再點任何東西）。

退出碼（共用 0 / 1 / 2 / 8 / 9 / 10 見 uikit；本檔 140～149，grep 過不與其他工具衝突）：
  0   隊伍已滿 5 人（含「其實沒缺人」）
  140 讀不到隊伍 / 掉隊者名字讀不出 / 沒有隊長（全滅或全員單人）
  141 切換角色失敗（char.switch / ensure）
  142 任務步號讀不到（參考者或掉隊者），無法判斷落後與否 → 不盲打
  143 補血失敗
  144 重打失敗：次數用完仍落後 / 片數用完 / 步號比隊長還前面（不合理）/ quest.py 非預期退出碼
  145 重組失敗：解散舊隊伍 / team.form / 最後 team.check 不滿 5 人
  146 quest.py 回需要人看的碼（39 不可逆對話、33 / 29 對話無進展、25 自動戰鬥卡住、19 巡路卡住、3 追蹤沒反應、5 找不到任務但隊長沒完成）
安全：只用 char / team / quest / heal 現有的驗證流程，不加任何新的點擊座標；不做不可逆動作；驗證視窗（9）/ 斷線（10）立即透傳。

實機驗證狀態（2026-10-12 寫成）：**只有離線測試（test_bossretry.py，假 Tools）**。待實機確認：
  ① 被打飛的人任務步號是否真的沒前進（若遊戲照樣給進度，步號 == ref → 只補血重組，不重打）
  ② 單人（1 角色 + 戰寵）打得過洞窟守護獸嗎（打不過 → 144，停手交人）
  ③ 掉隊者在村子、隊伍在洞窟深處時 team.form 快速組隊能不能跨地圖（不能 → 145；可能要先讓 DKBO 隊伍也按追蹤到同一處）
  ④ ref 不是 DKBO（DKBO 自己被打飛）時的解散路徑

待接線（questrun.py；等 play agent 結束、主 agent 通知才改，現在 questrun 6 檔禁改）：
  questrun.Tools 加：
      def boss_retry(self, track):
          import bossretry
          rc = bossretry.run(track)
          return rc, dict(bossretry.LAST)
  questrun.Run.run_task 迴圈前加 `boss_retries = 0`；把 `act == 'knocked'` 與 `act == 'boss_team'` 兩個 return self.fail(EXIT_TEAM, …) 換成：
      if act in ('knocked', 'boss_team'):
          if not self.o.get('boss_retry', True) or boss_retries >= BOSS_RETRY_MAX:          # BOSS_RETRY_MAX = 3（每個任務）
              return self.fail(EXIT_TEAM, f'任務 {tid}：BOSS 戰後隊伍不滿（quest.py {rc}），自動重打已用完 / 關閉', quest_rc=rc)
          boss_retries += 1
          brc, binfo = T.boss_retry(track)
          self.info.setdefault('boss_retry', []).append(binfo)
          if brc in (uikit.EXIT_UNKNOWN_SCREEN, uikit.EXIT_HALT):
              return brc
          if brc:
              return self.fail(EXIT_TEAM, f'任務 {tid}：bossretry 退出碼 {brc}：{binfo.get("msg", "")}', quest_rc=rc, boss_retry_rc=brc)
          self.team_ok_at = time.time()                                                       # bossretry 最後 team.check 滿 5 人
          rc = self.hp_gate(f'任務 {tid} 重打補人後')
          if rc:
              return rc
          continue
  run() / main() 加 `--no-boss-retry`（opts['boss_retry']=False）；檔頭 114 說明改「bossretry 失敗（info.boss_retry_rc = 140～146）」；
  print_plan 的 BOSS 行改「38 → bossretry.py 自動補人」；test_questrun 的 Fake 加 boss_retry（回 (0, {}) / (144, {...})）並補兩個案例。
"""
import argparse
import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import uikit  # noqa: E402

SRC = 'bossretry'
(EXIT_TEAM_READ, EXIT_SWITCH, EXIT_STEP, EXIT_HEAL, EXIT_REFIGHT, EXIT_REGROUP, EXIT_QUEST_MANUAL) = range(140, 147)
LEADER = 'DKBO'
HP_MIN = 50                      # 掉隊者 HUD HP 低於這個 % 才補血（被打飛通常 HP 1）
MAX_TRIES = 2                    # 每個掉隊者最多「輸 / 被打飛」幾次（第 1 次 + 重試）
MAX_SLICES = 6                   # 每個掉隊者最多跑幾片 quest.py
SLICE_S = 300
WALK_CAP_S = 900                 # 同 questrun.WALK_CAP_S（子程序逾時 = slice + 這個 + 120）
GONE = 'GONE'                    # = quest.GONE
MANUAL_RC = {39: '不可逆對話', 33: '對話無進展', 29: '對話 / 選擇面板循環', 25: '完整戰鬥自動戰鬥卡住', 19: '自動巡路卡住', 3: '追蹤沒反應'}
LAST: dict = {}


# ---------------------------------------------------------------- 純函式
def team_roles(cards) -> tuple:
    """切換面板卡片 → (隊長名或 None, 掉隊者名單)。卡片 label 不是 leader / member = 掉隊（名字 None 也列進去，呼叫端擋）"""
    leaders = [c.name for c in cards if c.label == 'leader']
    missing = [c.name for c in cards if c.label not in ('leader', 'member')]
    return (leaders[0] if len(leaders) == 1 else None), missing


def lag(ref, who) -> str:
    """參考步號 ref 與掉隊者步號 who → 'same' / 'behind' / 'ahead' / 'unknown'。GONE = 任務已完成（追蹤列表沒有）"""
    if ref is None or who is None:
        return 'unknown'
    if ref == who:
        return 'same'
    if who == GONE:
        return 'ahead'                       # 掉隊者已完成、隊長還沒：不合理
    if ref == GONE:
        return 'behind'
    try:
        return 'behind' if int(who) < int(ref) else 'ahead'
    except (TypeError, ValueError):
        return 'unknown'


def classify_quest(rc: int) -> str:
    """quest.py 退出碼（單人追趕片）→ 'verify' / 'halt' / 'boss' / 'slice' / 'knocked' / 'gone' / 'manual' / 'other'"""
    if rc in (2, uikit.EXIT_UNKNOWN_SCREEN):
        return 'verify'
    if rc == uikit.EXIT_HALT:
        return 'halt'
    if rc in (37, 38):
        return 'boss'
    if rc == 0:
        return 'slice'
    if rc == 21:
        return 'knocked'
    if rc == 5:
        return 'gone'
    if rc in MANUAL_RC:
        return 'manual'
    return 'other'


def plan_text(track: str, o: dict) -> list:
    return [
        f'1 team.check(5)：0 = 沒缺人 → 結束（不動）',
        '2 切換面板讀卡片：隊長 = 參考者、不在隊的 = 掉隊者（名字讀不出 / 沒隊長 → 140）',
        f'3 參考者（不是當前就 char.switch）讀「{track}」步號（讀不到 → 142）',
        f'4 每個掉隊者：char.switch → 讀步號 → HP < {o["hp_min"]}% 補血（heal --no-return）→ 落後就 quest.py --task {track} --team-size 1 '
        f'--max-seconds {o["slice_s"]}（≤ {o["max_slices"]} 片、輸 / 被打飛 ≤ {o["max_tries"]} 次）直到步號 = 參考者',
        f'5 參考者不是 {LEADER} → 切過去解散；char.ensure {LEADER} → team.form --regroup → team.check(5)',
        '退出碼：0 滿 5 人；140 隊伍讀不到 / 沒隊長；141 切角色；142 步號讀不到；143 補血；144 重打失敗；145 重組失敗；146 quest.py 要人看；9 驗證視窗；10 斷線',
    ]


# ---------------------------------------------------------------- 真實工具（測試換成 Fake）
def _tools_base():
    import questrun
    return questrun.Tools


class Tools(_tools_base()):
    """沿用 questrun.Tools（current / char_switch / char_ensure / team_check / team_cards / quest / read_step / hp_pct / snap / sleep）"""

    def team_form_regroup(self):
        import team
        return team.form(regroup=True)

    def team_disband(self):
        import team
        return team.disband()

    def heal(self):
        import heal
        heal.heal_trip('波拉島', True, False)          # 補完停在醫院，不傳回、不開遇敵；之後 quest.py 按追蹤自己巡路回去


# ---------------------------------------------------------------- 流程
class Run:
    def __init__(self, T, track: str, o: dict):
        self.T, self.track, self.o = T, track, o
        self.info: dict = {'track': track, 'missing': [], 'ref': None, 'ref_step': None, 'done': {}, 'tries': {}}

    def event(self, msg: str):
        try:
            import questrun
            questrun.event(f'[bossretry] {msg}')
        except Exception:
            print(f'bossretry：{msg}', flush=True)

    def fail(self, rc: int, msg: str) -> int:
        self.info['msg'] = msg
        self.event(f'失敗 rc={rc}：{msg}')
        try:
            import errlog
            errlog.add(f'bossretry：{msg}', source=SRC)
        except Exception:
            pass
        return rc

    def switch(self, who: str) -> int:
        rc, cur = self.T.current()
        if not rc and cur == who:
            return 0
        return self.T.char_switch(who)

    def read_step(self, who: str):
        st = self.T.read_step(self.track)
        if st is None:
            self.T.sleep(1.5)
            st = self.T.read_step(self.track)
        self.event(f'{who} 的「{self.track}」步號 = {st}')
        return st

    def heal_if_low(self, who: str) -> int:
        hp = self.T.hp_pct()
        if hp is not None and hp >= self.o['hp_min']:
            return 0
        self.event(f'{who} HP {hp}%（< {self.o["hp_min"]}% 或讀不到）→ 補血（小護士，停在醫院）')
        try:
            self.T.heal()
        except RuntimeError as e:
            return self.fail(EXIT_HEAL, f'{who} 補血失敗：{e}')
        self.info.setdefault('heals', []).append(who)
        return 0

    def catch_up(self, who: str, ref_step) -> int:
        """掉隊者已是當前角色：追到 ref_step。→ 0 / 退出碼"""
        st = self.read_step(who)
        k = lag(ref_step, st)
        if k == 'unknown':
            return self.fail(EXIT_STEP, f'{who} 的步號讀不到（{st}），無法判斷要不要重打；不盲打')
        if k == 'ahead':
            return self.fail(EXIT_REFIGHT, f'{who} 步號 {st} 比隊長 {ref_step} 還前面（不合理），停手請人看')
        rc = self.heal_if_low(who)
        if rc:
            return rc
        if k == 'same':
            self.event(f'{who} 步號與隊長相同（{st}）→ 不用重打')
            self.info['done'][who] = 'same'
            return 0
        losses = 0
        for n in range(self.o['max_slices']):
            args = ['--task', self.track, '--max-seconds', self.o['slice_s'], '--team-size', '1']
            qrc, tail = self.T.quest(args, self.o['slice_s'] + WALK_CAP_S + 120)
            act = classify_quest(qrc)
            self.event(f'{who} 追趕第 {n + 1} 片 quest.py 退出碼 {qrc}（{act}）')
            if act == 'verify':
                self.T.snap('bossretry-verify')
                self.info['msg'] = 'quest.py 看到不認得的畫面（疑似驗證視窗）→ 停手（鐵則 5）'
                return uikit.EXIT_UNKNOWN_SCREEN
            if act == 'halt':
                return uikit.EXIT_HALT
            if act == 'manual':
                self.T.snap('bossretry-manual')
                return self.fail(EXIT_QUEST_MANUAL, f'{who} 追趕時 quest.py {qrc}（{MANUAL_RC[qrc]}），請人看')
            if act == 'other':
                return self.fail(EXIT_REFIGHT, f'{who} 追趕時 quest.py 非預期退出碼 {qrc}')
            st2 = self.read_step(who) if act != 'gone' else GONE
            k = lag(ref_step, st2)
            if k == 'same':
                self.event(f'{who} 追上了（步號 {st2}）')
                self.info['done'][who] = 'caught_up'
                return 0
            if k == 'ahead':
                return self.fail(EXIT_REFIGHT, f'{who} 追趕後步號 {st2} 超過隊長 {ref_step}（不合理），停手')
            if act == 'gone':
                return self.fail(EXIT_QUEST_MANUAL, f'{who} 的追蹤列表找不到「{self.track}」，但隊長步號是 {ref_step}')
            if k == 'unknown':
                return self.fail(EXIT_STEP, f'{who} 追趕後步號讀不到（{st2}）；不盲打')
            lost = act == 'knocked' or (act == 'boss' and st2 == st)
            if lost:
                losses += 1
                self.info['tries'][who] = losses
                self.event(f'{who} 第 {losses} 次{"被打飛" if act == "knocked" else "BOSS 戰後步號沒前進（輸）"}')
                if losses >= self.o['max_tries']:
                    self.T.snap('bossretry-lost')
                    return self.fail(EXIT_REFIGHT, f'{who} 重打 {losses} 次仍沒追上（步號 {st2}，隊長 {ref_step}），單人打不過？停手交人')
                rc = self.heal_if_low(who)
                if rc:
                    return rc
            st = st2
        return self.fail(EXIT_REFIGHT, f'{who} 跑了 {self.o["max_slices"]} 片仍沒追上（步號 {st}，隊長 {ref_step}）')

    def regroup(self, ref: str) -> int:
        T = self.T
        if ref != LEADER:                                              # 舊隊伍隊長不是 DKBO：team.form 的解散要「當前 = 隊長」→ 先切到 ref 解散
            rc = self.switch(ref)
            if rc:
                return rc if rc in (uikit.EXIT_UNKNOWN_SCREEN, uikit.EXIT_HALT) else self.fail(EXIT_SWITCH, f'切到舊隊長 {ref} 解散失敗 rc={rc}')
            rc = T.team_disband()
            if rc:
                return rc if rc in (uikit.EXIT_UNKNOWN_SCREEN, uikit.EXIT_HALT) else self.fail(EXIT_REGROUP, f'{ref} 解散舊隊伍失敗 team rc={rc}')
        rc = T.char_ensure(LEADER)
        if rc:
            return rc if rc in (uikit.EXIT_UNKNOWN_SCREEN, uikit.EXIT_HALT) else self.fail(EXIT_SWITCH, f'切回 {LEADER} 失敗 rc={rc}')
        rc = T.team_form_regroup()
        if rc:
            return rc if rc in (uikit.EXIT_UNKNOWN_SCREEN, uikit.EXIT_HALT) else self.fail(EXIT_REGROUP, f'team.form --regroup 失敗 rc={rc}（掉隊者與隊伍在不同地圖時快速組隊可能不支援，待實機）')
        rc = T.team_check()
        if rc:
            return rc if rc in (uikit.EXIT_UNKNOWN_SCREEN, uikit.EXIT_HALT) else self.fail(EXIT_REGROUP, f'重組後 team.check 仍不滿 5 人 rc={rc}')
        return 0

    def go(self) -> int:
        T = self.T
        rc = T.preflight()
        if rc:
            return rc
        rc = T.team_check()
        if rc == 0:
            self.event('team.check 滿 5 人 → 其實沒缺人，不動')
            self.info['noop'] = True
            return 0
        if rc in (uikit.EXIT_UNKNOWN_SCREEN, uikit.EXIT_HALT):
            return rc
        cards, err = T.team_cards()
        if cards is None:
            return self.fail(EXIT_TEAM_READ, f'讀不到隊伍狀態：{err}')
        ref, miss = team_roles(cards)
        self.info.update(ref=ref, missing=miss)
        if ref is None:
            return self.fail(EXIT_TEAM_READ, f'沒有隊長（全滅 / 全員單人？），掉隊名單 {miss}；不重打')
        if not miss or any(m is None for m in miss):
            return self.fail(EXIT_TEAM_READ, f'不滿 5 人但找不出掉隊者（名單 {miss}）')
        self.event(f'隊長 {ref}、掉隊 {miss}')
        rc = self.switch(ref)
        if rc:
            return rc if rc in (uikit.EXIT_UNKNOWN_SCREEN, uikit.EXIT_HALT) else self.fail(EXIT_SWITCH, f'切到隊長 {ref} 失敗 rc={rc}')
        ref_step = self.read_step(ref)
        self.info['ref_step'] = ref_step
        if ref_step is None:
            return self.fail(EXIT_STEP, f'隊長 {ref} 的「{self.track}」步號讀不到；無法判斷誰落後，不盲打')
        for who in miss:
            rc = self.switch(who)
            if rc:
                return rc if rc in (uikit.EXIT_UNKNOWN_SCREEN, uikit.EXIT_HALT) else self.fail(EXIT_SWITCH, f'切到 {who} 失敗 rc={rc}')
            rc = self.catch_up(who, ref_step)
            if rc:
                return rc
        return self.regroup(ref)


def run(track: str, tools=None, dry_run: bool = False, max_tries: int = MAX_TRIES, max_slices: int = MAX_SLICES,
        slice_s: int = SLICE_S, hp_min: int = HP_MIN) -> int:
    LAST.clear()
    o = dict(max_tries=max_tries, max_slices=max_slices, slice_s=slice_s, hp_min=hp_min)
    if not track:
        print('bossretry：要 --track 任務追蹤標題', file=sys.stderr)
        return uikit.EXIT_USAGE
    if dry_run:
        for ln in plan_text(track, o):
            print(ln)
        LAST.update(rc=0, dry_run=True)
        return 0
    T = tools or Tools()
    R = Run(T, track, o)
    t0 = time.time()
    rc = 0
    try:
        rc = R.go()
    finally:
        if rc not in (0, uikit.EXIT_UNKNOWN_SCREEN, uikit.EXIT_HALT):     # 失敗也切回 DKBO（驗證視窗 / 斷線不再點）
            try:
                if T.char_ensure(LEADER):
                    R.event(f'失敗收尾切回 {LEADER} 也失敗，請人看')
            except Exception as e:
                R.event(f'失敗收尾切回 {LEADER} 例外：{e}')
    LAST.update(R.info, rc=rc, secs=int(time.time() - t0))
    print(json.dumps(LAST, ensure_ascii=False, default=str))
    return rc


def status() -> int:
    T = Tools()
    cards, err = T.team_cards()
    if cards is None:
        print(f'bossretry：讀不到隊伍：{err}')
        return EXIT_TEAM_READ
    ref, miss = team_roles(cards)
    print(json.dumps({'leader': ref, 'missing': miss}, ensure_ascii=False))
    return 0


def main(argv=None) -> int:
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    sub = ap.add_subparsers(dest='cmd', required=True)
    for name in ('plan', 'run'):
        p = sub.add_parser(name)
        p.add_argument('--track', required=True, help='任務追蹤標題（questdefs 的 track，例：琉璃洞窟）')
        p.add_argument('--max-tries', type=int, default=MAX_TRIES)
        p.add_argument('--max-slices', type=int, default=MAX_SLICES)
        p.add_argument('--slice-s', type=int, default=SLICE_S)
        p.add_argument('--hp-min', type=int, default=HP_MIN)
        p.add_argument('--dry-run', action='store_true')
    sub.add_parser('status')
    a = ap.parse_args(argv)
    if a.cmd == 'status':
        import winenv
        winenv.enable_server()
        return status()
    if a.cmd == 'plan' or a.dry_run:
        return run(a.track, dry_run=True, max_tries=a.max_tries, max_slices=a.max_slices, slice_s=a.slice_s, hp_min=a.hp_min)
    import winenv
    winenv.enable_server()
    return run(a.track, max_tries=a.max_tries, max_slices=a.max_slices, slice_s=a.slice_s, hp_min=a.hp_min)


if __name__ == '__main__':
    sys.exit(main())
