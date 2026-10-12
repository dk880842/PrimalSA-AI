#!/usr/bin/env python3
"""BOSS 戰後隊伍不滿 5 人（quest.py 38 / 21，questrun 114）→ 由落後者當隊長組滿 5 人、按追蹤回 BOSS 處全隊重打 → 切回 DKBO 重組。只用標準函式庫。

規則來源：memory psa-team-check-after-boss（2026-10-11 使用者規定；2026-10-12 更正）—— 照 0 轉龍王任務（英雄島前傳 2031 步 6，
notes/quest-log.md 10-10 兩段：第一次輸、5 人 HP 1 原地；第二次 5 人一隊從 5510:50,17 `--fight --npc auto` 打贏）的做法：
**被打飛（步號落後）的人 char.switch 當隊長、組滿 5 人隊，按任務追蹤自動傳送回 BOSS 處，5 人一起打**（不是掉隊者單人去打）；
補完切回 DKBO 當隊長重組 5 人、check 滿 5 人才往下；重打失敗或仍不滿就停手回報。這是「當前角色維持 DKBO」的例外，結束一律切回 DKBO。

用法（專案根目錄；WSL / Windows 原生相同）：
  uv run --no-project python tools/gui/bossretry.py plan --track 琉璃洞窟                 # 不碰遊戲：印流程與退出碼
  uv run --no-project python tools/gui/bossretry.py run --track 琉璃洞窟 [--max-tries 2] [--max-slices 6] [--slice-s 300] [--hp-min 60] [--dry-run]
  uv run --no-project python tools/gui/bossretry.py run --track 四寶玉之謎 --who DKBO3,DKBO5 [--ref-step done|N]   # 指定落後者（隊伍滿的也照跑）：
        逐人驗證發現有人任務沒完成時用（questrun 每任務完成後 verify_all 自動呼叫）；--ref-step 預設 done = 其他人已完成，落後者要打到任務完成
  uv run --no-project python tools/gui/bossretry.py status                                 # 唯讀：開切換面板，印隊長 / 不在隊的人
  可 import：bossretry.run(track, tools=None, who=None, ref_step=None, ...) → 退出碼；結果 dict 在 bossretry.LAST
  --dry-run = 同 plan（完全不碰遊戲）。重跑 = 續跑：每次都從現場狀態（隊伍卡片、各人任務步號）重新判斷，不靠進度檔。

流程：
  1 確認     team.check(5) = 0 → 其實沒缺人（38 可能只是讀不到）→ 回 0、不動
  2 找人     切換面板卡片：label 不是隊長 / 隊員的 = 掉隊者（名字讀不出 → 140）；隊長 = 參考者 ref（沒有隊長 = 全滅 / 全員單人 → 140）
  3 參考步號 當前切到 ref（通常就是 DKBO）→ quest.read_step_no(追蹤標題)；讀不到重讀 1 次，仍 None → 142（無法判斷誰落後，不盲打）
             → ref 解散舊隊伍（之後 team.form 要全員單人；解散要「當前 = 隊長」，所以趁 ref 是當前時解）
  4 每個掉隊者（依序）：char.switch(掉隊者) → 讀他的步號：== ref（或都 GONE）→ 不用重打；
     落後 → team.form(leader=掉隊者) 組滿 5 人 → 全隊 HP（bag.hps）任一 < --hp-min% → 補血（小護士補整隊）→
     迴圈（≤ --max-slices 片）：quest.py --task <追蹤> --team-size 5（預設模式：點追蹤 = 自動傳送 / 巡路、對話按確認、BOSS 戰開自動戰鬥 + 刷新，戰後停 37 / 38）
       追蹤沒反應（3）→ 改 quest.py --fight --task <追蹤> --npc auto --team-size 5（站在 BOSS 旁直接點 NPC，英雄島前傳步 6 的打法）
       → 讀掉隊者步號：== ref 追上；BOSS 戰後步號沒前進 / 被打飛（21）/ --fight 35 = 輸一次 → 補血 → 重組 → 再打（≤ --max-tries 次）；
          38 / 30 / 32（隊伍又散）→ 原地重組再起一片
     → 追上後由掉隊者（隊長）解散這隊；多人掉隊就逐一以每個落後者為隊長重複（已完成的人陪打，預期不影響進度；2026-10-12 2010 實機成功）
  5 收尾     char.ensure DKBO → team.form() → team.check(5) = 0 才回 0
  --who 模式（2026-10-12，逐人驗證用）：不看 team.check / 掉隊卡片，落後者 = --who 名單、參考步號 = --ref-step（預設 GONE = 已完成）；
             有隊伍就先由原隊長解散，之後同步驟 4、5。
  任何失敗都會先（能的話）解散臨時隊伍、char.ensure DKBO 再回退出碼（9 驗證視窗 / 10 斷線除外：立即停、不再點任何東西）。

退出碼（共用 0 / 1 / 2 / 8 / 9 / 10 見 uikit；本檔 140～149，grep 過不與其他工具衝突）：
  0   隊伍已滿 5 人（含「其實沒缺人」）
  140 讀不到隊伍 / 掉隊者名字讀不出 / 沒有隊長（全滅或全員單人）
  141 切換角色失敗（char.switch / ensure）
  142 任務步號讀不到（參考者或掉隊者），無法判斷落後與否 → 不盲打
  143 補血失敗
  144 重打失敗：輸到 --max-tries / 片數用完 / 步號比隊長還前面（不合理）/ quest.py 非預期退出碼
  145 組隊 / 解散失敗：舊隊解散、以掉隊者為隊長組隊、最後 DKBO 重組或 team.check 不滿 5 人
  146 quest.py 回需要人看的碼（39 不可逆對話、33 / 29 對話無進展、25 自動戰鬥卡住、19 巡路卡住、3 追蹤沒反應且 --fight 也點不到、5 找不到任務但隊長沒完成）
安全：只用 char / team / quest / heal / bag 現有的驗證流程，不加任何新的點擊座標；不做不可逆動作；驗證視窗（9）/ 斷線（10）立即透傳。

實機驗證狀態：離線測試（test_bossretry.py，假 Tools）+ 2026-10-12 09:37～10:23 在 2010 實機成功（--who 補完四寶玉之謎）。原待確認項目：
  ① 被打飛的人任務步號是否真的沒前進（若遊戲照樣給進度，步號 == ref → 不重打，只重組）
  ② 已完成該步的 4 人陪打，進度 / 獎勵會不會出怪事（例：對話選項不同、BOSS 不出現）
  ③ 掉隊者在村子（被打飛）、其他人在洞窟深處時，team.form 快速組隊能不能跨地圖（不能 → 145；組成後按追蹤是否把全隊傳回 BOSS 處）
  ④ ref 不是 DKBO（DKBO 自己被打飛）時的解散路徑；掉隊者在第 5 張卡（DKBO5）時 team.form 會因提示視窗上排只看前 4 欄而 44（team.py 限制）
  ⑤ 補血 heal_trip 由非 DKBO 隊長觸發是否正常
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
TEAM_SIZE = 5
HP_MIN = 60                      # 全隊任一人 HP 低於這個 % → 補血（同 questrun.TEAM_HP_MIN）
MAX_TRIES = 2                    # 每個掉隊者最多「輸 / 被打飛」幾次
MAX_SLICES = 6                   # 每個掉隊者最多跑幾片 quest.py
MAX_REFORM = 3                   # 每個掉隊者打的過程中隊伍又散（38 / 30 / 32）最多重組幾次
SLICE_S = 300
WALK_CAP_S = 900                 # 同 questrun.WALK_CAP_S（子程序逾時 = slice + 這個 + 120）
GONE = 'GONE'                    # = quest.GONE
MANUAL_RC = {39: '不可逆對話', 33: '對話無進展', 29: '對話 / 選擇面板循環', 25: '完整戰鬥自動戰鬥卡住', 19: '自動巡路卡住', 31: '--npc auto 取不到目前步驟',
             22: '--fight 沒點到 NPC', 23: '--fight 對話後沒開打', 34: '--fight 不在 NPC 地圖', 36: '--fight 輸贏判斷不了'}
PASS = (uikit.EXIT_UNKNOWN_SCREEN, uikit.EXIT_HALT)
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


def classify_quest(rc: int, fight: bool = False) -> str:
    """quest.py 退出碼 → 'verify' / 'halt' / 'boss' / 'slice' / 'won' / 'lost' / 'knocked' / 'team' / 'no_track' / 'gone' / 'manual' / 'other'。
    fight = 這片是 --fight（0 = 判定打贏、35 = 沒打贏）"""
    if rc in (2, uikit.EXIT_UNKNOWN_SCREEN):
        return 'verify'
    if rc == uikit.EXIT_HALT:
        return 'halt'
    if fight and rc == 0:
        return 'won'
    if fight and rc == 35:
        return 'lost'
    if rc in (37, 38):
        return 'boss'
    if rc == 0:
        return 'slice'
    if rc == 21:
        return 'knocked'
    if rc in (30, 32):
        return 'team'
    if rc == 3:
        return 'no_track'
    if rc == 5:
        return 'gone'
    if rc in MANUAL_RC:
        return 'manual'
    return 'other'


def plan_text(track: str, o: dict) -> list:
    if o.get('who'):
        return [
            f'--who 模式：落後者 {o["who"]}、參考步號 {o.get("ref_step") or GONE}（GONE = 其他人已完成）；不看 team.check',
            '1 切換面板讀卡片：有隊長 → 切到隊長解散（全員單人才能以落後者為隊長快速組隊）',
            f'2 每個落後者：char.switch → 讀「{track}」步號；落後 → team.form 以他為隊長組滿 5 人 → 全隊 HP < {o["hp_min"]}% 補血 → '
            f'quest.py --task {track} --team-size 5 全隊打（≤ {o["max_slices"]} 片、輸 ≤ {o["max_tries"]} 次）直到步號 = 參考 → 解散這隊',
            f'3 char.ensure {LEADER} → team.form → team.check(5)',
            '退出碼同下：140～146；9 驗證視窗；10 斷線',
        ]
    return [
        '1 team.check(5)：0 = 沒缺人 → 結束（不動）',
        '2 切換面板讀卡片：隊長 = 參考者、不在隊的 = 掉隊者（名字讀不出 / 沒隊長 → 140）',
        f'3 參考者（不是當前就 char.switch）讀「{track}」步號（讀不到 → 142）→ 參考者解散舊隊伍',
        f'4 每個掉隊者：char.switch → 讀步號；落後 → team.form 以他為隊長組滿 5 人 → 全隊 HP < {o["hp_min"]}% 補血 → '
        f'quest.py --task {track} --team-size 5（追蹤沒反應改 --fight --npc auto）全隊打（≤ {o["max_slices"]} 片、輸 ≤ {o["max_tries"]} 次）'
        '直到步號 = 參考者 → 解散這隊',
        f'5 char.ensure {LEADER} → team.form → team.check(5)',
        '退出碼：0 滿 5 人；140 隊伍讀不到 / 沒隊長；141 切角色；142 步號讀不到；143 補血；144 重打失敗；145 組隊 / 解散失敗；146 quest.py 要人看；9 驗證視窗；10 斷線',
    ]


# ---------------------------------------------------------------- 真實工具（測試換成 Fake）
def _tools_base():
    import questrun
    return questrun.Tools


class Tools(_tools_base()):
    """沿用 questrun.Tools（current / char_switch / char_ensure / team_check / team_cards / quest / read_step / team_hp / heal / snap / sleep）"""

    def team_form_as(self, leader):
        """以 leader 為隊長組滿 5 人（全員單人時走快速組隊；成功後當前 = leader）"""
        import team
        return team.form(leader=leader, size=TEAM_SIZE)

    def team_disband(self):
        import team
        return team.disband()


# ---------------------------------------------------------------- 流程
class Run:
    def __init__(self, T, track: str, o: dict):
        self.T, self.track, self.o = T, track, o
        self.info: dict = {'track': track, 'missing': [], 'ref': None, 'ref_step': None, 'done': {}, 'tries': {}}
        self.team_leader = None                  # 目前存在的隊伍的隊長（收尾解散用）；None = 全員單人 / 不知道
        self.keep = None                         # --who 續跑：這個落後者已帶著 5 人隊 → refight 不重組

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

    def passthru(self, rc: int, code: int, msg: str) -> int:
        return rc if rc in PASS else self.fail(code, msg)

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

    def disband(self, leader: str) -> int:
        """leader 帶的隊伍解散（當前必須是 leader：team.disband 的規定）"""
        rc = self.switch(leader)
        if rc:
            return self.passthru(rc, EXIT_SWITCH, f'切到隊長 {leader} 要解散失敗 rc={rc}')
        rc = self.T.team_disband()
        if rc:
            return self.passthru(rc, EXIT_REGROUP, f'{leader} 解散隊伍失敗 team rc={rc}')
        self.team_leader = None
        return 0

    def disband_actual(self, why: str) -> int:
        """隊伍散掉後，現在的隊長不一定是我們組隊時指定的人（2026-10-12 實機：DKBO3 當隊長打火雞，DKBO2 / DKBO3 陣亡踢出，
        剩下的隊伍隊長自動變成 DKBO → 舊流程切到 DKBO3 解散 → team 46 → 145）。讀切換面板找真正的隊長 → 切過去解散；沒有隊伍 → 0"""
        cards, err = self.T.team_cards()
        if cards is not None and not any(c.label in ('leader', 'member', 'solo') for c in cards):
            self.T.sleep(2)                                    # 全部讀成 other（轉場 / 補血傳送中）→ 等一下重讀（2026-10-12 實機：誤判沒隊伍 → form 41 ×3）
            cards, err = self.T.team_cards()
        if cards is None:
            return self.fail(EXIT_TEAM_READ, f'{why}：讀不到隊伍狀態：{err}')
        lead, _ = team_roles(cards)
        if not lead and not all(c.label == 'solo' for c in cards):
            return self.fail(EXIT_REGROUP, f'{why}：隊伍標籤讀不準（{[c.label for c in cards]}），不解散也不組隊')
        if not lead:
            if any(c.label in ('leader', 'member') for c in cards):
                return self.fail(EXIT_REGROUP, f'{why}：有隊伍標籤但找不到唯一隊長，不解散')
            self.team_leader = None
            return 0
        if lead != self.team_leader:
            self.event(f'{why}：現在的隊長是 {lead}（不是 {self.team_leader}）→ 由 {lead} 解散')
        return self.disband(lead)

    def form_as(self, who: str) -> int:
        """以 who 為隊長組 5 人；可恢復的小錯（切換面板讀到 0 張卡片 42 等）原地重試 3 次（questrun.retry_form，2026-10-12 實機 42）"""
        import questrun
        rc = questrun.retry_form(self.T, lambda: self.T.team_form_as(who), f'bossretry 以 {who} 為隊長組隊')
        if rc:
            return self.passthru(rc, EXIT_REGROUP, f'以 {who} 為隊長組 5 人失敗 team rc={rc}（掉隊者與其他人在不同地圖時快速組隊可能不支援，待實機）')
        cards, err = self.T.team_cards()                       # 組完再驗一次：隊長真的是 who、其他 4 人都是隊員（使用者 2026-10-12 要求）
        lead, miss = team_roles(cards) if cards is not None else (None, ['?'])
        if lead != who or miss:
            self.team_leader = lead
            return self.fail(EXIT_REGROUP, f'以 {who} 為隊長組隊後驗證不符：隊長 {lead}、不在隊 {miss}（{err}）')
        self.team_leader = who
        return 0

    def hp_gate(self, where: str) -> int:
        """全隊 HP（bag.hps）任一 < hp_min → 補血（小護士補整隊）；讀不到 → 補（被打飛的人通常 HP 1，寧可多補）"""
        rc, pct = self.T.team_hp()
        if rc in PASS:
            return rc
        low = {r: v for r, v in (pct or {}).items() if v is not None and v < self.o['hp_min']}
        if not rc and pct and not low:
            self.event(f'{where}：全隊 HP {pct}，不用補')
            return 0
        self.event(f'{where}：全隊 HP {pct}（rc {rc}；偏低 {low}）→ 補血（小護士補整隊）')
        try:
            self.T.heal()
        except RuntimeError as e:
            return self.fail(EXIT_HEAL, f'{where}：補血失敗：{e}')
        self.info['heals'] = self.info.get('heals', 0) + 1
        return 0

    def refight(self, who: str, ref_step) -> int:
        """掉隊者已是當前角色：讀步號 → 落後就以他為隊長組 5 人打到追上 → 解散這隊。→ 0 / 退出碼"""
        st = self.read_step(who)
        k = lag(ref_step, st)
        if k == 'unknown':
            return self.fail(EXIT_STEP, f'{who} 的步號讀不到（{st}），無法判斷要不要重打；不盲打')
        if k == 'ahead':
            return self.fail(EXIT_REFIGHT, f'{who} 步號 {st} 比隊長 {ref_step} 還前面（不合理），停手請人看')
        if k == 'same':
            self.event(f'{who} 步號與隊長相同（{st}）→ 不用重打')
            self.info['done'][who] = 'same'
            return 0
        if self.keep == who:
            self.event(f'{who} 步號 {st} 落後 {ref_step} → 沿用 {who} 帶的 5 人隊重打')
            self.keep = None
        else:
            self.event(f'{who} 步號 {st} 落後隊長 {ref_step} → 以 {who} 為隊長組 5 人重打')
            rc = self.form_as(who)
            if rc:
                return rc
        rc = self.hp_gate(f'{who} 隊重打前')
        if rc:
            return rc
        losses = reforms = 0
        fight_next = False
        for n in range(self.o['max_slices']):
            if fight_next:
                args = ['--fight', '--task', self.track, '--npc', 'auto', '--team-size', TEAM_SIZE, '--max-seconds', self.o['slice_s']]
            else:
                args = ['--task', self.track, '--max-seconds', self.o['slice_s'], '--team-size', TEAM_SIZE]
            qrc, tail = self.T.quest(args, self.o['slice_s'] + WALK_CAP_S + 120)
            act = classify_quest(qrc, fight_next)
            self.event(f'{who} 隊第 {n + 1} 片 quest.py{" --fight" if fight_next else ""} 退出碼 {qrc}（{act}）')
            was_fight, fight_next = fight_next, False
            if act == 'verify':
                self.T.snap('bossretry-verify')
                self.info['msg'] = 'quest.py 看到不認得的畫面（疑似驗證視窗）→ 停手（鐵則 5）'
                return uikit.EXIT_UNKNOWN_SCREEN
            if act == 'halt':
                return uikit.EXIT_HALT
            if act == 'no_track':
                if was_fight:
                    return self.fail(EXIT_QUEST_MANUAL, f'{who} 隊：追蹤沒反應，--fight 也沒成功（quest.py {qrc}），請人看')
                self.event(f'{who} 隊：追蹤沒反應（3）→ 下一片改 --fight --npc auto（站在 BOSS 旁直接點）')
                fight_next = True
                continue
            if act == 'manual':
                self.T.snap('bossretry-manual')
                return self.fail(EXIT_QUEST_MANUAL, f'{who} 隊 quest.py {qrc}（{MANUAL_RC[qrc]}），請人看')
            if act == 'other':
                return self.fail(EXIT_REFIGHT, f'{who} 隊 quest.py 非預期退出碼 {qrc}')
            st2 = GONE if act == 'gone' else self.read_step(who)
            k = lag(ref_step, st2)
            if k == 'same':
                self.event(f'{who} 追上了（步號 {st2}）')
                self.info['done'][who] = 'caught_up'
                return self.disband(who)
            if k == 'ahead':
                return self.fail(EXIT_REFIGHT, f'{who} 重打後步號 {st2} 超過隊長 {ref_step}（不合理），停手')
            if act == 'gone':
                return self.fail(EXIT_QUEST_MANUAL, f'{who} 的追蹤列表找不到「{self.track}」，但隊長步號是 {ref_step}')
            if k == 'unknown':
                return self.fail(EXIT_STEP, f'{who} 重打後步號讀不到（{st2}）；不盲打')
            lost = act in ('knocked', 'lost') or (act == 'boss' and st2 == st)
            broke = qrc in (38, 30, 32) or act == 'knocked'
            if lost:
                losses += 1
                self.info['tries'][who] = losses
                self.event(f'{who} 隊第 {losses} 次{"被打飛" if act == "knocked" else "沒打贏（步號沒前進）"}')
                if losses >= self.o['max_tries']:
                    self.T.snap('bossretry-lost')
                    return self.fail(EXIT_REFIGHT, f'{who} 隊重打 {losses} 次仍沒追上（步號 {st2}，隊長 {ref_step}），停手交人')
            if broke or lost:
                if broke:
                    reforms += 1
                    if reforms > MAX_REFORM:
                        return self.fail(EXIT_REGROUP, f'{who} 隊打的過程中隊伍散了 {reforms} 次，停手')
                rc = self.T.team_check()
                if rc in PASS:
                    return rc
                if rc:
                    self.event(f'{who} 隊不滿 5 人（team.check {rc}）→ 由現在的隊長解散 → 以 {who} 為隊長重組')
                    rc = self.disband_actual(f'{who} 隊散了')
                    if rc:
                        return rc
                    rc = self.form_as(who)
                    if rc:
                        return rc
            if act in ('boss', 'won', 'lost', 'knocked'):
                # 每場 BOSS / 任務戰之後（贏輸都算）、隊伍重組之後才看全隊 HP（2026-10-12 實機 DKBO5：步 2 / 3 贏了但有人陣亡，
                # 重組後沒看 HP 就打步 4 → 全滅；舊版輸了才補、而且是重組前補，只補到隊長那幾個人）
                rc = self.hp_gate(f'{who} 隊{"輸了" if lost else "打完 BOSS"}之後')
                if rc:
                    return rc
            st = st2
        return self.fail(EXIT_REFIGHT, f'{who} 隊跑了 {self.o["max_slices"]} 片仍沒追上（步號 {st}，隊長 {ref_step}）')

    def go(self) -> int:
        T = self.T
        rc = T.preflight()
        if rc:
            return rc
        if self.o.get('who'):
            return self.go_who()
        rc = T.team_check()
        if rc == 0:
            self.event('team.check 滿 5 人 → 其實沒缺人，不動')
            self.info['noop'] = True
            return 0
        if rc in PASS:
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
        self.team_leader = ref
        self.event(f'隊長 {ref}、掉隊 {miss}')
        rc = self.switch(ref)
        if rc:
            return self.passthru(rc, EXIT_SWITCH, f'切到隊長 {ref} 失敗 rc={rc}')
        ref_step = self.read_step(ref)
        self.info['ref_step'] = ref_step
        if ref_step is None:
            return self.fail(EXIT_STEP, f'隊長 {ref} 的「{self.track}」步號讀不到；無法判斷誰落後，不盲打')
        rc = self.disband(ref)                                   # 之後要以掉隊者為隊長快速組隊（全員單人才走得通）
        if rc:
            return rc
        return self.fix_each(miss, ref_step)

    def go_who(self) -> int:
        """--who：呼叫端已知誰落後（逐人讀任務詳情）。隊伍可能是滿的 → 有隊長就先由他解散，之後同一般流程"""
        who, ref_step = list(self.o['who']), self.o.get('ref_step') or GONE
        self.info.update(missing=who, ref_step=ref_step, mode='who')
        cards, err = self.T.team_cards()
        if cards is None:
            return self.fail(EXIT_TEAM_READ, f'讀不到隊伍狀態：{err}')
        ref, out = team_roles(cards)
        self.info['ref'] = ref
        self.event(f'指定落後者 {who}（參考步號 {ref_step}）；目前隊長 {ref or "無（全員單人）"}')
        if ref in who and not out:                                # 已是「落後者當隊長的 5 人隊」（中斷後續跑）→ 不拆，先處理他
            self.event(f'隊伍已由落後者 {ref} 帶滿 5 人 → 沿用，不解散重組')
            self.team_leader = self.keep = ref
            who.remove(ref)
            who.insert(0, ref)
            return self.fix_each(who, ref_step)
        if ref:
            self.team_leader = ref
            rc = self.disband(ref)
            if rc:
                return rc
        return self.fix_each(who, ref_step)

    def fix_each(self, miss, ref_step) -> int:
        """每個落後者：切過去 → refight（落後才以他為隊長組 5 人重打）→ 最後切回 DKBO 組 5 人 + check"""
        T = self.T
        for who in miss:
            rc = self.switch(who)
            if rc:
                return self.passthru(rc, EXIT_SWITCH, f'切到 {who} 失敗 rc={rc}')
            rc = self.refight(who, ref_step)
            if rc:
                return rc
        rc = T.char_ensure(LEADER)
        if rc:
            return self.passthru(rc, EXIT_SWITCH, f'切回 {LEADER} 失敗 rc={rc}')
        rc = self.form_as(LEADER)
        if rc:
            return rc
        rc = T.team_check()
        if rc:
            return self.passthru(rc, EXIT_REGROUP, f'重組後 team.check 仍不滿 5 人 rc={rc}')
        return 0

    def cleanup(self) -> None:
        """失敗收尾：臨時隊伍（隊長不是 DKBO）先解散，再切回 DKBO。都只盡力，不覆蓋原退出碼"""
        try:
            if self.team_leader and self.team_leader != LEADER:
                if self.disband_actual('失敗收尾'):
                    self.event(f'失敗收尾：解散臨時隊伍（{self.team_leader}）失敗，請人看')
            if self.T.char_ensure(LEADER):
                self.event(f'失敗收尾切回 {LEADER} 也失敗，請人看')
        except Exception as e:
            self.event(f'失敗收尾例外：{e}')


def run(track: str, tools=None, dry_run: bool = False, max_tries: int = MAX_TRIES, max_slices: int = MAX_SLICES,
        slice_s: int = SLICE_S, hp_min: int = HP_MIN, who=None, ref_step=None) -> int:
    """who = 指定落後者名單（--who 模式，不看 team.check）；ref_step = 參考步號（None / 'done' = GONE 已完成）"""
    LAST.clear()
    if ref_step in (None, 'done', 'DONE'):
        ref_step = GONE
    o = dict(max_tries=max_tries, max_slices=max_slices, slice_s=slice_s, hp_min=hp_min, who=list(who or []), ref_step=ref_step)
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
        if rc not in (0,) + PASS:                                # 失敗也切回 DKBO（驗證視窗 / 斷線不再點）
            R.cleanup()
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
        p.add_argument('--who', default='', help='指定落後者（逗號分隔，例 DKBO3,DKBO5）：隊伍滿的也照跑')
        p.add_argument('--ref-step', default='done', help='--who 的參考步號：done（其他人已完成，預設）或步號數字')
    sub.add_parser('status')
    a = ap.parse_args(argv)
    if a.cmd == 'status':
        import winenv
        winenv.enable_server()
        return status()
    import charstate
    who = []
    for n in [x.strip() for x in a.who.split(',') if x.strip()]:
        hit = charstate.norm_char(n)
        if not hit:
            print(f'bossretry：--who 的 {n} 不在角色白名單', file=sys.stderr)
            return uikit.EXIT_USAGE
        who.append(charstate.display(hit))
    ref = int(a.ref_step) if str(a.ref_step).isdigit() else a.ref_step
    kw = dict(max_tries=a.max_tries, max_slices=a.max_slices, slice_s=a.slice_s, hp_min=a.hp_min, who=who, ref_step=ref)
    if a.cmd == 'plan' or a.dry_run:
        return run(a.track, dry_run=True, **kw)
    import winenv
    winenv.enable_server()
    return run(a.track, **kw)


if __name__ == '__main__':
    sys.exit(main())
