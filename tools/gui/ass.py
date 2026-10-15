#!/usr/bin/env python3
"""外掛 ASS 左欄戰鬥設定的讀 / 設工具（只用標準庫，經 walk.gui → winenv → gui.ps1；背景操作）。

用法（專案根目錄；WSL / Windows 原生指令相同）：
  uv run --no-project python tools/gui/ass.py get DKBO                    # 印四項狀態（開 / 關）
  uv run --no-project python tools/gui/ass.py get DKBO 原地遇敵 自動戰鬥     # 只印指定項目
  uv run --no-project python tools/gui/ass.py set DKBO 原地遇敵 on 自動戰鬥 on 快速戰鬥 off
  uv run --no-project python tools/gui/ass.py pet DKBO get                # 戰寵 首次動作（勾選 + 值）/ 一般動作（值）
  uv run --no-project python tools/gui/ass.py pet DKBO first 防禦          # 首次動作 = 防禦 並勾選
  uv run --no-project python tools/gui/ass.py pet DKBO first off normal 攻擊   # 首次動作取消勾選（值不動）、一般動作 = 攻擊
  uv run --no-project python tools/gui/ass.py pet all normal 防禦        # 多人：5 人戰寵 一般動作 = 防禦（也可 DKBO,DKBO3 指定幾人；選項依文字找，可填已學的寵物技能名）
  uv run --no-project python tools/gui/ass.py battle all [--dry-run]       # 解任務前戰鬥設定（QUEST_BATTLE）：5 人自動戰鬥開、DKBO 人物首次動作 風的精靈Lv.5 打勾；
        一次開面板逐人讀、只改不對的、讀回確認（值不對不改，回 13）；不關遇敵、戰鬥中不開（8）。questrun 交接 / bossretry 重打前自動跑（battle_check）
  uv run --no-project python tools/gui/ass.py points all get [--no-plan]   # 唯讀：便捷功能 → 特色設定 自定義加點 / 同步加點 勾選 + SET 視窗讀方案（按取消）
  uv run --no-project python tools/gui/ass.py points DKBO set              # 隊長方案 = 速度80 / 體力50 / 腕力999 / 耐力0 才勾自定義 + 同步加點；方案不同 → 15 不改（輸入流程未實測）
        （2026-10-15 寫成，**未實機**：OCR 框推估；做完一律切回右半「戰鬥設置」）
    多人流程（--pause）：關原地遇敵 + 等戰鬥結束 → 一次開面板逐人（讀現值 → 不同才改 → 讀回確認；隊長最後）→ grind.py ensure 恢復掛機。
    預設不暫停遇敵（快速戰鬥中開外掛面板不用停遇敵，2026-10-12 使用者；戰鬥打斷 rc 6 / 12 自動等 3 秒重試 2 次）。旗標：--pause 強制先關遇敵 + 等戰鬥結束、改完 grind ensure 恢復、--no-resume 搭 --pause 時不恢復、--dry-run 只讀不改。只動「一般動作」，首次動作 / 對象都不碰。
角色：這個視窗的名單（主視窗 DKBO / DKBO2～DKBO5；PSA_CLIENT=PrimalSA2 為 DKBO6～DKBO10；真名字母 O；DKB0… 同義；不分大小寫）。頭像位置依名單第 1～5 個。
項目：原地遇敵(encounter) / 快速戰鬥(fast) / 自動戰鬥(auto) / 夥伴助戰(partner)。
（2026-10-10 起不再支援外掛「自動逃跑」：使用者要求外掛自動逃跑一律不用、不看那個勾選框；逃跑改由 quest.py 手動按戰鬥畫面逃跑鈕。）
流程：開外掛 → 驗證面板真的開了 → 選角色並驗證 → pixel 讀四項 → （set：只點與目標不同的，再讀確認）→ 關面板（X 1318,90）並驗證。
安全：每次點面板內座標前都先 pixel 驗證面板還開著（面板沒開時點這些座標會穿透到地面讓角色走掉）；
      主畫面看不到外掛鈕（對話 / 載入中）或被擋 → 等待重試，最多 OPEN_TIMEOUT 秒，失敗回報、不亂點。
退出碼：0 成功 / 1 參數錯 / 2 面板打不開 / 3 選不到角色（面板開著但頭像被遮住 / 點了不變）/ 4 設定確認失敗（點了沒變，不再補點）/ 5 版面不是 2880×1659 / 6 面板中途消失（讀不到；選角色時面板被遊戲關掉、重開 2 次仍不行）/ 7 右半面板不在頂端（pet：戰寵動作標題讀不到，不點）/
        12 多人 pet：下拉找不到指定選項（不點、停在該角色）/ 13 battle：人物首次動作的值確定不對（不自動改）/
        15 points：加點方案不是 POINTS_PLAN（目標值輸入流程未實測 = 座標待量測，不改不勾）/ 16 points：特色設定分頁 / 加點視窗 OCR 讀不到（不點勾選）/ 8 戰鬥中（BATTLE_WAIT 秒內沒等到戰鬥結束，或加了 --no-wait）：沒開面板、沒改任何設定。
戰鬥中保護（2026-10-10 碧青洞窟事故：BOSS 戰開始 1 秒後外掛設定被改動 → 隊長脫隊）：get / set / pet 一律先判斷是不是戰鬥中
  （戰鬥畫面像素 = battleguard.screen_in_battle，或 quest.py 寫的鎖檔 tools/.cache/battle.lock 有效〔pid 活著且 30 分鐘內〕），
  是 → 不開面板、不改任何勾選，等戰鬥結束（連續 2 次讀到非戰鬥才算，最多 BATTLE_WAIT=90 秒）再做；逾時回退出碼 8。
  --no-wait：戰鬥中不等，直接回退出碼 8（排程 / 腳本不想卡住時用）。面板已經開著時視為不在戰鬥（外掛面板戰鬥中打不開）。
勾選判讀（2026-10-10 實測）：未勾 = 框心 255,255,255；已勾 = 其他值（30,30,30 / 151 / 223 視打勾筆劃而定）。
只動點到的角色；不改其他角色，不碰其他項目。外掛面板不能用 ESC 關。
給其他腳本 import：ass.get_states(role) / ass.set_states(role, {項目: bool}) → (rc, 狀態 dict 或 None, 訊息)；
ass.set_many({角色: {項目: bool} 或 None}) 一次開面板逐人讀 / 改 → (rc, {角色: 狀態}, 訊息, info)（P8，grind 用）。
選角色（select_role）頭像被不透明東西（EXP 橫幅文字）蓋住會先等一下、沒選中會重試、第 3 次起改點名字標籤（2026-10-11 DKBO3 選不到的修正；失敗時面板開著存 tools/.cache/ass-select-fail-<角色>.png）。
選角色時面板整個消失（不是被遮住；2026-10-14 08:13 斷線、08:15 重登後隊員陸續上線，點 DKBO3 後外掛面板被遊戲關掉 → 舊版誤報 rc 3「頭像 sel」= 讀到地圖黑底）：
  select_role_reopen 先等戰鬥結束、重開面板（REOPEN_TIMEOUT 15 秒）再選，最多 PANEL_REOPEN=2 次；已讀 / 改好的前面角色不重做。仍不行 → 6（不是 3）。
頂部跑馬燈（伺服器公告「恭喜玩家…」「翻倍成功」，左端綠髮啦啦隊吉祥物）疊在外掛面板上、剛好蓋住 DKBO3 頭像並吃掉點擊（2026-10-11 rc 52 的根因，
失敗截圖 4 / 4 都是它）：select_role 偵測到就不往吉祥物上點、等它消失（最多 MARQUEE_WAIT 秒）；set_many 遇到時先把 DKBO3 挪到隊長前面最後做；
跑馬燈在時 selected_role 用其他 4 人推斷（4 人都沒選中 = 選中的是被蓋住的 DKBO3）。
"""
import argparse
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
import battleguard  # noqa: E402
import clients  # noqa: E402
import layout  # noqa: E402
from walk import gui, log  # noqa: E402

ASS_BTN = (1300, 760)            # 主畫面「外掛」
CLOSE_BTN = (1318, 90)           # 面板右上 X（不能 ESC）
HUD_PROBE = (1300, 745, 254, 0, 0)   # 主畫面外掛鈕紅字（同 quest.SIG_HUD；對話框開著時整個 UI 隱藏）

# 角色頭像圓鈕：第 1～5 個的位置固定（主視窗 DKBO～DKBO5；PrimalSA2 DKBO6～DKBO10，依 clients.roster() 順序配；真名字母 O；DKB0 同義，norm_role 容錯）
ROLE_XY = [(137, 151), (298, 151), (461, 151), (137, 204), (298, 204)]
ROLES = clients.by_slot(ROLE_XY)
LEADER = clients.leader() or ''
# 左欄戰鬥設定勾選框（框心）；每個角色各自設定
ITEMS = {'原地遇敵': (146, 343), '快速戰鬥': (484, 343), '自動戰鬥': (146, 400), '夥伴助戰': (315, 400)}
ALIASES = {'encounter': '原地遇敵', 'fast': '快速戰鬥', 'quick': '快速戰鬥',
           'auto': '自動戰鬥', 'partner': '夥伴助戰', 'assist': '夥伴助戰'}

# 面板開著的特徵：右上橘 X + 五個角色圓鈕（選中 0,0,0、沒選中 197,227,255；有 EXP 橫幅可能蓋住 DKB03，容許 1 個不符）
X_SIG = (1318, 90, 195, 127, 8)
AVATAR_SEL = (0, 0, 0)
AVATAR_OFF = (197, 227, 255)
TOL = 25
UNCHECKED = (255, 255, 255)      # 框心純白 = 未勾；其他 = 已勾

OPEN_TIMEOUT = 40.0              # 等外掛面板能開的最長秒數（戰鬥 / 載入中 / 對話會擋）
OPEN_RETRY_GAP = 1.5
CONFIRM_WAIT = 0.5               # 點勾選後第一次讀回的等待
CONFIRM_WAIT2 = 0.9              # 還沒變就多等一次（不補點，避免切回去）

EXIT_OK, EXIT_USAGE, EXIT_NO_PANEL, EXIT_NO_ROLE, EXIT_CONFIRM, EXIT_LAYOUT, EXIT_PANEL_LOST, EXIT_NOT_TOP = 0, 1, 2, 3, 4, 5, 6, 7
EXIT_NO_OPTION = 12              # 多人戰寵動作：下拉找不到指定選項（不亂點）
EXIT_IN_BATTLE = 8               # 戰鬥中：等不到結束（或 --no-wait）→ 不開面板、不改設定
BATTLE_WAIT = 90.0               # 戰鬥中最多等幾秒（一般一場 < 60 秒；BOSS 戰約 20~40 秒）
BATTLE_POLL = 1.5                # 等待時的輪詢秒數
BATTLE_CLEAR_N = 2               # 連續幾次讀到「非戰鬥」才算戰鬥結束（避開轉場一瞬間）

sleep = time.sleep               # 測試時可替換
clock = time.time


def _px(pts):
    out = gui('pixel', ' '.join(f'{x},{y}' for x, y in pts)).split()
    try:
        cols = [tuple(int(v) for v in c.split(',')) for c in out]
    except ValueError:
        return None
    return cols if len(cols) == len(pts) else None


def _close(c, ref, tol=TOL):
    return all(abs(a - b) <= tol for a, b in zip(c, ref))


# 頂部跑馬燈（伺服器公告：「恭喜玩家【…】」「翻倍成功」等，文字由右往左捲；一則約 7～10 秒，可能接連多則）。
# 左端綠髮啦啦隊吉祥物約 x 400～490、y 60～178，疊在所有面板之上、吃掉點擊，剛好蓋住外掛面板 DKBO3 頭像 (461,151)；
# 吉祥物衣服是淡藍（195,225,251 一帶），單點讀頭像會被誤判成 off / dim。偵測用吉祥物頭髮 6 點：
# 2026-10-11 掃 tools/.cache 767 張 1440×830 截圖，有跑馬燈 59 張 = 6/6 點綠、沒有的 708 張 = 0/6（含外掛面板開著、綠色草地地圖）。
MARQUEE_PTS = ((428, 98), (432, 94), (434, 94), (452, 94), (456, 98), (460, 98))
MARQUEE_MIN = 3                  # 6 點至少幾點是頭髮綠才算跑馬燈在
MARQUEE_X = (395, 495)           # 吉祥物橫向範圍：頭像 x 落在裡面的角色會被蓋住（= DKBO3）
MARQUEE_ROLES = tuple(r for r, (x, _) in ROLES.items() if MARQUEE_X[0] <= x <= MARQUEE_X[1])
MARQUEE_WAIT = 20.0              # 等跑馬燈消失的上限（一則 7～10 s；超過 = 接連多則，回 3 交給呼叫端稍後重試）
MARQUEE_POLL = 0.5


def _hair(c) -> bool:
    r, g, b = c[:3]
    return g > 130 and g - r > 50 and g - b > 50


def _marquee(cols) -> bool:
    return sum(1 for c in cols if _hair(c)) >= MARQUEE_MIN


def marquee_on() -> bool | None:
    """頂部跑馬燈（綠髮吉祥物）在不在；讀不到 None"""
    cols = _px(list(MARQUEE_PTS))
    return None if not cols else _marquee(cols)


def panel_open() -> bool:
    """外掛面板是否真的開著（X + 至少 4 個角色圓鈕合理）。讀不到 = False"""
    pts = [(X_SIG[0], X_SIG[1])] + list(ROLES.values())
    cols = _px(pts)
    if not cols or not _close(cols[0], X_SIG[2:], TOL):
        return False
    good = sum(1 for c in cols[1:] if _close(c, AVATAR_SEL, 8) or _close(c, AVATAR_OFF, 8))
    return good >= 4


def hud_visible() -> bool:
    cols = _px([HUD_PROBE[:2]])
    return bool(cols) and _close(cols[0], HUD_PROBE[2:], 40)


def in_battle() -> str | None:
    """現在是不是戰鬥中：鎖檔有效 → 'lock'；戰鬥畫面像素 → 'screen'；否則 None。外掛面板已開著 = 不在戰鬥（戰鬥中開不了面板）"""
    if battleguard.locked():
        return 'lock'
    if panel_open():
        return None
    return 'screen' if battleguard.screen_in_battle(gui) else None


def wait_not_battle(no_wait: bool = False, timeout: float = None) -> tuple[bool, str]:
    """戰鬥保護：戰鬥中 → 不動作，等到連續 BATTLE_CLEAR_N 次非戰鬥（最多 timeout 秒）。回 (可以動作, 訊息)。no_wait=True 戰鬥中直接 False"""
    timeout = BATTLE_WAIT if timeout is None else timeout
    why = in_battle()
    if not why:
        return True, ''
    if no_wait:
        return False, f'戰鬥中（{"quest.py 鎖檔" if why == "lock" else "戰鬥畫面"}），--no-wait → 沒開面板、沒改任何設定'
    log(f'ass：戰鬥中（{"鎖檔" if why == "lock" else "畫面"}），等戰鬥結束再動作（最多 {timeout:.0f} 秒）')
    end, clear = clock() + timeout, 0
    while clock() < end:
        sleep(BATTLE_POLL)
        if in_battle():
            clear = 0
            continue
        clear += 1
        if clear >= BATTLE_CLEAR_N:
            return True, ''
    return False, f'戰鬥中等了 {timeout:.0f} 秒仍未結束 → 沒開面板、沒改任何設定'


def open_panel(timeout: float = None) -> bool:
    """開外掛面板並驗證；已開著就直接成功。只在看到主畫面外掛鈕時才點（避免點到別的東西）；等待重試有上限"""
    timeout = OPEN_TIMEOUT if timeout is None else timeout
    end = clock() + timeout
    clicked = 0
    while True:
        if panel_open():
            return True
        if hud_visible() and clicked < 6:
            gui('seq', f'click {ASS_BTN[0]} {ASS_BTN[1]}; wait 900', note='ass.py 開外掛面板')
            clicked += 1
            if panel_open():
                return True
        if clock() >= end:
            return False
        sleep(OPEN_RETRY_GAP)


CLOSE_WAIT = 2.5                 # 點 X 後等面板消失的上限（秒）；與 uikit.CLOSE_WAIT_MS 一致
CLOSE_POLL = 0.15


def close_panel() -> bool:
    """點 X 關面板並驗證消失：點完每 0.15 秒讀一次，最多 2.5 秒，消失即返回；逾時且仍開著才再點（最多 2 次，第二次前先確認仍開著）"""
    for _ in range(2):
        if not panel_open():
            return True
        gui('seq', f'click {CLOSE_BTN[0]} {CLOSE_BTN[1]}', note='ass.py 關外掛面板')
        end = clock() + CLOSE_WAIT
        while clock() < end:
            sleep(CLOSE_POLL)
            if not panel_open():
                return True
    return not panel_open()


def selected_role() -> str | None:
    """目前選中的角色；讀不到 / 不確定回 None。
    跑馬燈蓋住 DKBO3 時那一點讀的是吉祥物（黑邊可能被當成選中、淡藍衣服像沒選中），改看其他 4 人：
    其中剛好 1 人選中 → 就是他；4 人都清楚是「沒選中」→ 選中的是被蓋住的那位（角色圓鈕是單選，面板上永遠有 1 人選中）；其他 → None"""
    n = len(ROLES)
    cols = _px(list(ROLES.values()) + list(MARQUEE_PTS))
    if not cols:
        return None
    av, mq = cols[:n], cols[n:]
    if _marquee(mq) and MARQUEE_ROLES:
        vis = [(r, c) for r, c in zip(ROLES, av) if r not in MARQUEE_ROLES]
        sel = [r for r, c in vis if _close(c, AVATAR_SEL, 8)]
        if len(sel) == 1:
            return sel[0]
        if not sel and len(MARQUEE_ROLES) == 1 and all(_close(c, AVATAR_OFF, 8) for _, c in vis):
            return MARQUEE_ROLES[0]
        return None
    sel = [r for r, c in zip(ROLES, av) if _close(c, AVATAR_SEL, 8)]
    return sel[0] if len(sel) == 1 else None


SELECT_TRIES = 4                 # 選角色最多點幾次
SELECT_TIMEOUT = 35.0            # 選角色總上限（含等遮擋 / 跑馬燈消失；跑馬燈最多等 MARQUEE_WAIT）
COVER_WAIT = 4.0                 # 頭像被不透明東西遮住時，每圈最多等幾秒（等不到也照點：點在面板內，無害）
LABEL_DX = 50                    # 頭像右邊的名字標籤（備援點擊；點在自己那列的標籤上）
DIM_MAX = 45                     # 半透明橫幅蓋住時頭像顏色比正常暗多少以內仍算「dim」（實測 off 197,227,255 → 189,219,243）
wait_cover_hook = None           # 呼叫端可設 fn(timeout)：等 EXP 橫幅消失（grind 的偵測；ass 不能 import grind）


def avatar_state(role: str) -> str | None:
    """該角色頭像圓鈕：'sel' 選中 / 'off' 沒選中 / 'dim' 被半透明橫幅蓋著但看得出是未選中（實測點得穿，可以直接點）/
    'cover' 被不透明的東西蓋住（EXP 橫幅文字 / 「NEW」/ 浮字）/ 'marquee' 被頂部跑馬燈吉祥物蓋住（點擊會被吃掉，要等它消失）/ None 讀不到"""
    cols = _px([ROLES[role]] + list(MARQUEE_PTS))
    if not cols:
        return None
    c = cols[0]
    if role in MARQUEE_ROLES and _marquee(cols[1:]):
        return 'marquee'        # 先判：吉祥物淡藍衣服會像 off / dim、黑邊會像 sel
    if _close(c, AVATAR_SEL, 8):
        return 'sel'
    if _close(c, AVATAR_OFF, 8):
        return 'off'
    if all(-8 <= r - v <= DIM_MAX for r, v in zip(AVATAR_OFF, c)) and c[2] > c[1] > c[0]:
        return 'dim'
    return 'cover'


def wait_uncovered(role: str, timeout: float = COVER_WAIT) -> bool:
    """頭像被不透明東西蓋住就等（先呼叫 wait_cover_hook 等 EXP 橫幅，再輪詢頭像像素）；
    回 True = 可以點了（sel / off / dim）；面板消失 / 逾時回 False。
    2026-10-11 實機：EXP 橫幅（一場戰鬥 3 行疊在 x 450～1000、y 130～270）剛好蓋住 DKBO3 頭像（461,151），
    半透明部分點得穿（實測 dim 時點擊選得中），不透明部分 / 「成功」浮字 點不到；掛機中橫幅幾乎接連出現，所以不能死等乾淨。"""
    end = clock() + timeout
    hooked = False
    while True:
        st = avatar_state(role)
        if st in ('sel', 'off', 'dim'):
            return True
        if st == 'marquee':
            return False        # 跑馬燈由 wait_marquee_gone 處理（select_role 先叫）
        if not panel_open():
            return False
        if clock() >= end:
            return False
        if st == 'cover' and wait_cover_hook and not hooked:
            hooked = True
            wait_cover_hook(min(4.0, timeout))
            continue
        sleep(0.4)


def wait_marquee_gone(timeout: float = MARQUEE_WAIT) -> bool:
    """等頂部跑馬燈消失（連 2 次讀到沒有才算，間隔 MARQUEE_POLL）。回 True = 消失；面板消失 / 逾時 / 讀不到 False"""
    end = clock() + timeout
    clear = 0
    while True:
        m = marquee_on()
        clear = clear + 1 if m is False else 0
        if clear >= 2:
            return True
        if not panel_open() or clock() >= end:
            return False
        sleep(MARQUEE_POLL)


def select_role(role: str, tries: int = SELECT_TRIES, timeout: float = SELECT_TIMEOUT) -> bool:
    """選外掛面板角色並驗證。內建：頭像被頂部跑馬燈吉祥物蓋住 → 不點、等它消失（最多 MARQUEE_WAIT）；
    被其他不透明東西蓋住先等一下（EXP 橫幅 / 浮字，等不到也照點）；點了沒選中就重試（面板還開著才重點）；
    第 3 次起改點頭像右邊的名字標籤（備援）。回 False = 選不到（面板消失 / 逾時 / 跑馬燈一直在）"""
    if selected_role() == role:
        return True
    end = clock() + timeout
    x, y = ROLES[role]
    for k in range(tries):
        if not panel_open():
            return False
        if role in MARQUEE_ROLES and avatar_state(role) == 'marquee':
            log(f'ass：{role} 頭像被頂部跑馬燈蓋住（點了會被吃掉），等它消失')
            if not wait_marquee_gone(min(MARQUEE_WAIT, max(0.0, end - clock()))):
                return False    # 不往吉祥物上點：點了也沒用（2026-10-11 實機 4 / 4 次點頭像、名字標籤都被吃掉）
            if selected_role() == role:
                return True
        wait_uncovered(role, min(COVER_WAIT, max(0.0, end - clock())))
        if not panel_open():
            return False
        cx = x + LABEL_DX if k >= 2 else x
        gui('seq', f'click {cx} {y}; wait 600', note=f'ass.py 選角色 {role}')
        if selected_role() == role:
            return True
        if clock() >= end:
            break
        sleep(0.3)
    return False


def read_checks(items=None) -> dict | None:
    """面板開著、角色已選好時讀四項（或指定項）勾選狀態：True = 開；讀不到回 None"""
    items = list(items or ITEMS)
    cols = _px([ITEMS[i] for i in items])
    if not cols:
        return None
    return {i: c != UNCHECKED for i, c in zip(items, cols)}


def norm_item(name: str) -> str | None:
    n = name.strip()
    n = ALIASES.get(n.lower(), n)
    return n if n in ITEMS else None


def norm_role(name: str) -> str | None:
    i = clients.index_of(name)                       # O / 0、大小寫、空白視為相同（DKBO10 = DKB010）
    return list(ROLES)[i] if i is not None and i < len(ROLES) else None


def _apply_changes(role: str, states: dict, changes: dict | None):
    """面板開著、角色已選好、已讀到 states：只點與目標不同的項目並逐項讀回確認（不補點）。回 (退出碼, 狀態 dict, 訊息)"""
    for item, want in (changes or {}).items():
        if states[item] == want:
            continue
        if not panel_open() or selected_role() != role:
            return EXIT_PANEL_LOST, states, f'點 {item} 前面板已不在 / 角色不對 → 不點'
        x, y = ITEMS[item]
        gui('seq', f'click {x} {y}; wait 300', note=f'ass.py {role} {item} → {"開" if want else "關"}')
        for w in (CONFIRM_WAIT, CONFIRM_WAIT2):
            sleep(w)
            if not panel_open():
                return EXIT_PANEL_LOST, states, f'點 {item} 後面板消失'
            now = read_checks([item])
            if now and now[item] == want:
                break
        else:
            return EXIT_CONFIRM, read_checks(), f'{item} 點了仍是 {"開" if states[item] else "關"}（可能是地圖禁止快速戰鬥等；不補點）'
        states = read_checks() or states
        log(f'ass：{role} {item} → {"開" if want else "關"}（已確認）')
    return EXIT_OK, states, ''


def _session(role: str, changes: dict | None, items=None, no_wait: bool = False):
    """（戰鬥保護）開面板 → 選角色 → 讀 →（有 changes 就設定並確認）→ 關面板。回 (退出碼, 狀態 dict 或 None, 訊息)"""
    ok_, why = wait_not_battle(no_wait)
    if not ok_:
        return EXIT_IN_BATTLE, None, why
    if not open_panel():
        return EXIT_NO_PANEL, None, f'外掛面板 {OPEN_TIMEOUT:.0f} 秒內打不開（戰鬥 / 對話 / 載入中擋住？）；沒點任何面板內座標'
    rc, states, msg = EXIT_OK, None, ''
    try:
        rc_, why = select_role_reopen(role, no_wait)
        if rc_:
            return rc_, None, why
        states = read_checks()
        if states is None:
            return EXIT_PANEL_LOST, None, '讀不到勾選框像素'
        rc, states, msg = _apply_changes(role, states, changes)
        return rc, states, msg
    finally:
        if not close_panel():
            print('警告：外掛面板沒關成功（請 shot 看畫面，手動點 X 1318,90）', flush=True)


# ---- 戰寵動作（戰鬥設置分頁頂端，未捲動；2026-10-10 實測）----
PET_FIRST_CHK = (656, 463)       # 戰寵 首次動作 勾選框
PET_DD = {'first': (1137, 463), 'normal': (1137, 514)}      # 下拉 ▼
PET_FIELD = {'first': (805, 445, 280, 40), 'normal': (805, 495, 280, 40)}   # 欄位文字 OCR 區（x y w h）
PET_TITLE_BOX = (640, 400, 120, 28)  # 「戰寵動作」標題；OCR 讀到「戰寵」才表示面板在頂端
PET_OPTS = ['攻擊', '防禦', '忠犬']   # 下拉前三項固定順序；第 n 項在欄位 y + 42×(n+1)，x 944（學會的技能排後面，不支援）
PET_OPT_DY, PET_OPT_X = 42, 944
OPT_ALIASES = {'attack': '攻擊', 'defend': '防禦', 'defense': '防禦', 'guard': '防禦'}


def _ocr(box, *opts) -> str:
    """區域 OCR，回傳所有行文字接起來（可替換給測試）"""
    import json
    import winenv
    import subprocess
    try:
        r = winenv.run_ps('ocr.ps1', *map(str, box), *map(str, opts))
    except subprocess.TimeoutExpired:
        return ''          # 讀圖逾時視同讀不到
    try:
        return ''.join(l['text'] for l in json.loads(r.stdout.strip().splitlines()[-1])['lines'])
    except (ValueError, KeyError, IndexError):
        return ''


def pet_on_top() -> bool:
    return '戰寵' in _ocr(PET_TITLE_BOX, '-Zooms', '2,3,4')


def read_pet_value(which: str) -> str | None:
    """OCR 欄位文字，對到 PET_OPTS 之一就回該值；讀不到 / 不在三項內回 None"""
    txt = _ocr(PET_FIELD[which], '-Zooms', '2,3,4')
    hits = [o for o in PET_OPTS if o in txt]
    return hits[0] if len(hits) == 1 else None


def read_pet() -> dict | None:
    cols = _px([PET_FIRST_CHK])
    if not cols:
        return None
    return {'first_on': cols[0] != UNCHECKED, 'first': read_pet_value('first'), 'normal': read_pet_value('normal')}


def _pet_session(role: str, want: dict | None, no_wait: bool = False):
    """want: {'first_on': bool?, 'first': 值?, 'normal': 值?}。回 (退出碼, 狀態 dict 或 None, 訊息)"""
    ok_, why = wait_not_battle(no_wait)
    if not ok_:
        return EXIT_IN_BATTLE, None, why
    if not open_panel():
        return EXIT_NO_PANEL, None, f'外掛面板 {OPEN_TIMEOUT:.0f} 秒內打不開；沒點任何面板內座標'
    st = None
    try:
        rc_, why = select_role_reopen(role, no_wait)
        if rc_:
            return rc_, None, why
        if not pet_on_top():
            return EXIT_NOT_TOP, None, '右半面板不在頂端（讀不到「戰寵動作」標題）；不點。請先 shot 看畫面、手動捲回頂端'
        st = read_pet()
        if st is None:
            return EXIT_PANEL_LOST, None, '讀不到勾選框像素'
        for key in ('first', 'normal'):
            v = (want or {}).get(key)
            if v is None or st[key] == v:
                continue
            if not panel_open() or selected_role() != role or not pet_on_top():
                return EXIT_PANEL_LOST, st, f'選 {key} 前面板已不在 / 角色不對 / 被捲動 → 不點'
            x, y = PET_DD[key]
            gui('seq', f'click {x} {y}; wait 500', note=f'ass.py {role} 戰寵{key} 開下拉')
            oy = y + PET_OPT_DY * (PET_OPTS.index(v) + 1)
            if not panel_open():
                return EXIT_PANEL_LOST, st, '開下拉後面板消失'
            gui('seq', f'click {PET_OPT_X} {oy}; wait 500', note=f'ass.py {role} 戰寵{key} → {v}')
            for w in (CONFIRM_WAIT, CONFIRM_WAIT2):
                sleep(w)
                if not panel_open():
                    return EXIT_PANEL_LOST, st, f'選 {key} 後面板消失'
                if read_pet_value(key) == v:
                    break
            else:
                st = read_pet() or st
                return EXIT_CONFIRM, st, f'戰寵 {key} 選了 {v} 但讀回仍是 {st.get(key)}（不補點；請 shot 確認，OCR 也可能誤讀）'
            st = read_pet() or st
            log(f'ass：{role} 戰寵{key} → {v}（已確認）')
        f_on = (want or {}).get('first_on')
        if f_on is not None and st['first_on'] != f_on:
            if not panel_open() or selected_role() != role or not pet_on_top():
                return EXIT_PANEL_LOST, st, '點首次動作勾選前面板已不在 / 角色不對 / 被捲動 → 不點'
            gui('seq', f'click {PET_FIRST_CHK[0]} {PET_FIRST_CHK[1]}; wait 300', note=f'ass.py {role} 戰寵首次動作勾選 → {"勾" if f_on else "不勾"}')
            for w in (CONFIRM_WAIT, CONFIRM_WAIT2):
                sleep(w)
                if not panel_open():
                    return EXIT_PANEL_LOST, st, '點勾選後面板消失'
                now = read_pet()
                if now and now['first_on'] == f_on:
                    break
            else:
                return EXIT_CONFIRM, read_pet(), '首次動作勾選點了沒變（不補點）'
            st = read_pet() or st
            log(f'ass：{role} 戰寵首次動作勾選 → {"勾" if f_on else "不勾"}（已確認）')
        return EXIT_OK, st, ''
    finally:
        if not close_panel():
            print('警告：外掛面板沒關成功（請 shot 看畫面，手動點 X 1318,90）', flush=True)


def get_pet(role: str, no_wait: bool = False):
    return _pet_session(role, None, no_wait)


def set_pet(role: str, want: dict, no_wait: bool = False):
    return _pet_session(role, want, no_wait)


def get_states(role: str, no_wait: bool = False):
    return _session(role, None, None, no_wait)


def set_states(role: str, changes: dict, no_wait: bool = False):
    return _session(role, changes, None, no_wait)


def _visit_checks(changes):
    """set_many 的逐人動作：讀四項勾選、只點不對的。回 (退出碼, 狀態 dict, 訊息, 改了哪些項目)"""
    def visit(role):
        st = read_checks()
        if st is None:
            return EXIT_PANEL_LOST, None, f'{role} 讀不到勾選框像素', []
        todo = [i for i, w in (changes or {}).items() if st.get(i) != w]
        if not todo:
            return EXIT_OK, st, '', []
        rc, st, msg = _apply_changes(role, st, changes)
        return rc, st, msg, todo
    return visit


PANEL_REOPEN = 2                 # 選角色時面板被關掉（不是我們關的）→ 重開面板再選的次數上限
REOPEN_TIMEOUT = 15.0            # 重開時等外掛鈕出現的上限（斷線回登入畫面時不要卡滿 OPEN_TIMEOUT 40 秒）


def select_role_reopen(role: str, no_wait: bool = False, info: dict | None = None) -> tuple:
    """set_many / battle_check 逐人選角色：select_role；選的過程中**面板整個消失**（不是被遮住）→ 等戰鬥結束、重開面板再選（最多 PANEL_REOPEN 次）。
    2026-10-14 08:13 / 08:15 questrun 交接 rc 109（ass rc 3「選不到 DKBO3（頭像 sel）」）根因：點 DKBO3 頭像後外掛面板被遊戲關掉
    （08:13 是斷線回登入畫面、08:15 是重登後隊員陸續上線 / 原地遇敵剛切換時），舊版不分「面板消失」與「被遮住」直接回 3，
    且面板消失後讀的是地圖黑底 → 誤報「頭像 sel」。已選好、已讀改的前面角色不受影響（設定存在伺服器，重開面板照樣在）。
    回 (0, '') 成功；(EXIT_IN_BATTLE, 訊息) 重開前等戰鬥逾時；(EXIT_PANEL_LOST, 訊息) 面板重開不了 / 重開後又消失；(EXIT_NO_ROLE, 訊息) 面板開著但選不到"""
    if select_role(role):
        return 0, ''
    n = 0
    while not panel_open() and n < PANEL_REOPEN:
        n += 1
        if info is not None:
            info.setdefault('reopen', []).append(role)
        log(f'ass：選 {role} 時外掛面板消失（斷線 / 開戰 / 隊員上線刷新 UI？）→ 重開面板再選（第 {n} 次）')
        ok_, why = wait_not_battle(no_wait)
        if not ok_:
            return EXIT_IN_BATTLE, f'選 {role} 時外掛面板消失，重開前：{why}'
        if not open_panel(REOPEN_TIMEOUT):
            gui('shot', f'ass-select-fail-{role}.png')
            return EXIT_PANEL_LOST, (f'選 {role} 時外掛面板消失，重開 {REOPEN_TIMEOUT:.0f} 秒內打不開（斷線回登入畫面 / 載入中 / 對話擋住？'
                                     f'截圖 tools/.cache/ass-select-fail-{role}.png）')
        if select_role(role):
            log(f'ass：重開外掛面板後選到 {role}')
            return 0, ''
    gui('shot', f'ass-select-fail-{role}.png')          # tools/.cache/；之後看是什麼蓋住
    if not panel_open():
        return EXIT_PANEL_LOST, f'選 {role} 時外掛面板一再消失（重開 {n} 次仍不行；截圖 tools/.cache/ass-select-fail-{role}.png）'
    st_ = avatar_state(role)
    why = (f'頭像被頂部跑馬燈（綠髮吉祥物公告）蓋住，等了 {MARQUEE_WAIT:.0f} 秒仍沒消失' if st_ == 'marquee'
           else f'頭像 {st_}；面板開著但被遮住 / 重試 {SELECT_TRIES} 次仍沒選中')
    return EXIT_NO_ROLE, f'選不到角色 {role}（{why}）'


def set_many(plan: dict, no_wait: bool = False) -> tuple:
    """一次開外掛面板，依 plan 的順序逐人選角色、讀勾選、（有 changes 就只點不對的並確認）、最後關面板。
    plan = {角色: {項目: bool} 或 None（只讀）}；選角色走 select_role（內建等遮擋 + 重試）。
    回 (退出碼, {角色: 狀態 dict}, 訊息, info)；info = {'secs': {角色: 秒}, 'changed': {角色: [項目]}, 'role': 出錯的角色或 None}。
    出錯時已讀到的照回、不再往下；面板一律關。最後選到的角色 = plan 最後一個（呼叫端把隊長放最後）。
    輪到被跑馬燈蓋住的角色（DKBO3）時若吉祥物正在，先挪到最後一位前面再做（只挪一次；成功時回傳的 dict 仍照 plan 順序）。"""
    return _many(plan, lambda role: _visit_checks(plan[role])(role), no_wait)


def _many(plan: dict, visit, no_wait: bool = False) -> tuple:
    """set_many / set_pet_many 共用：開面板 → 逐人 select_role → visit(role) → 關面板。
    visit(role) → (退出碼, 狀態 dict 或 None, 訊息, 改了哪些項目)；plan 只提供角色順序與 key。"""
    info = {'secs': {}, 'changed': {}, 'role': None}
    ok_, why = wait_not_battle(no_wait)
    if not ok_:
        return EXIT_IN_BATTLE, {}, why, info
    if not open_panel():
        return EXIT_NO_PANEL, {}, f'外掛面板 {OPEN_TIMEOUT:.0f} 秒內打不開（戰鬥 / 對話 / 載入中擋住？）；沒點任何面板內座標', info
    out: dict = {}
    order, deferred = list(plan), set()
    try:
        i = 0
        while i < len(order):
            role = order[i]
            # 跑馬燈正蓋著 DKBO3：先做後面的人（每人約 1.3 s），把它挪到最後一位（隊長）前面，等跑馬燈的時間被別人用掉
            if (role in MARQUEE_ROLES and role not in deferred and i < len(order) - 2
                    and marquee_on() and selected_role() != role):
                deferred.add(role)
                order.insert(len(order) - 2, order.pop(i))
                log(f'ass：{role} 頭像被頂部跑馬燈蓋住，先做後面的人、{role} 挪到 {order[-1]} 前面')
                continue
            i += 1
            t = clock()
            rc_, why = select_role_reopen(role, no_wait, info)
            if rc_:
                info['role'] = role
                return rc_, out, why, info
            rc, st, msg, todo = visit(role)
            if todo:
                info['changed'][role] = todo
            if rc:
                info['role'] = role
                if st:
                    out[role] = st
                return rc, out, msg, info
            out[role] = st
            info['secs'][role] = round(clock() - t, 2)
        return EXIT_OK, {r: out[r] for r in plan}, '', info
    finally:
        if not close_panel():
            print('警告：外掛面板沒關成功（請 shot 看畫面，手動點 X 1318,90）', flush=True)


# ---- 多人戰寵 一般動作（選項依 OCR 文字找，不寫死列序：各寵物學的技能不同）----
PET_LIST_DY, PET_LIST_H = 22, 330        # 下拉清單 OCR 區：欄位 y +22 起、高 330（最多約 7 列）
PET_LIST_X, PET_LIST_W = 805, 280


def _ocr_lines(box, *opts) -> list:
    """ocr.ps1 → [(文字, x, y)]（x / y = 文字中心，截圖座標）；逾時 / 失敗回 []（可替換給測試）"""
    import json
    import subprocess
    import winenv
    try:
        r = winenv.run_ps('ocr.ps1', *map(str, box), *map(str, opts))
        d = json.loads((r.stdout.strip().splitlines() or [''])[-1])
    except (subprocess.TimeoutExpired, ValueError):
        return []
    return [(ln['text'], ln.get('x', 0), ln.get('y', 0)) for ln in d.get('lines', [])] if d.get('ok') else []


def find_option(key: str, want: str) -> tuple | None:
    """下拉已展開：OCR 清單，回選項文字中心 (x, y)；完全相等優先，其次唯一包含；找不到 / 有歧義回 None"""
    y0 = PET_DD[key][1] + PET_LIST_DY
    lines = _ocr_lines((PET_LIST_X, y0, PET_LIST_W, PET_LIST_H), '-Zooms', '2,3,4')
    exact = [(x, y) for t, x, y in lines if t.replace(' ', '') == want]
    hits = exact or [(x, y) for t, x, y in lines if want in t.replace(' ', '')]
    return hits[0] if len(hits) == 1 or (exact and len(set(exact)) == 1) else None


def read_pet_text(which: str) -> str:
    return _ocr(PET_FIELD[which], '-Zooms', '2,3,4').replace(' ', '')


def _field_is(which: str, want: str) -> bool:
    return want in read_pet_text(which)


def _visit_pet_normal(want: str, dry_run: bool, skip_missing: bool = False):
    """多人戰寵 一般動作的逐人動作。回 (退出碼, {'normal': 值}, 訊息, 改了哪些)。
    skip_missing：下拉裡找不到該選項（例：剛轉生 Lv1 戰寵只有「攻擊 / 防禦」，2026-10-15 四轉 rebirth heal 階段 87）→
    點回下拉鈕收起清單、狀態帶 'skipped': want、回 0 繼續下一個人（不失敗、不亂點清單）"""
    def visit(role):
        if not pet_on_top():
            return EXIT_NOT_TOP, None, f'{role}：右半面板不在頂端（讀不到「戰寵動作」標題）；不點', []
        txt = read_pet_text('normal')
        cur = want if want in txt else next((o for o in PET_OPTS if o in txt), txt or '?')
        if cur == want or dry_run:
            return EXIT_OK, {'normal': cur}, '', []
        if not panel_open() or selected_role() != role or not pet_on_top():
            return EXIT_PANEL_LOST, {'normal': cur}, f'{role}：開下拉前面板已不在 / 角色不對 / 被捲動 → 不點', []
        x, y = PET_DD['normal']
        gui('seq', f'click {x} {y}; wait 500', note=f'ass.py {role} 戰寵normal 開下拉')
        pos = find_option('normal', want)
        if pos is None and skip_missing:
            gui('seq', f'click {x} {y}; wait 500', note=f'ass.py {role} 戰寵normal 收下拉（沒有「{want}」）')
            log(f'ass：{role} 戰寵一般動作下拉沒有「{want}」→ 收下拉、跳過（維持 {cur}）')
            return EXIT_OK, {'normal': cur, 'skipped': want}, '', []
        if pos is None:
            return EXIT_NO_OPTION, {'normal': cur}, f'{role}：下拉裡找不到唯一的「{want}」選項（該寵物沒學這技能？OCR 讀不到？）；不亂點，下拉隨面板關閉', []
        if not panel_open():
            return EXIT_PANEL_LOST, {'normal': cur}, f'{role}：開下拉後面板消失', []
        gui('seq', f'click {PET_OPT_X} {pos[1]}; wait 500', note=f'ass.py {role} 戰寵normal → {want}')
        for w in (CONFIRM_WAIT, CONFIRM_WAIT2):
            sleep(w)
            if not panel_open():
                return EXIT_PANEL_LOST, {'normal': cur}, f'{role}：選 {want} 後面板消失', ['normal']
            if _field_is('normal', want):
                log(f'ass：{role} 戰寵normal {cur} → {want}（已確認）')
                return EXIT_OK, {'normal': want}, '', ['normal']
        return EXIT_CONFIRM, {'normal': cur}, f'{role}：戰寵 normal 選了 {want} 但讀回仍是 {cur}（不補點；請 shot 確認）', ['normal']
    return visit


def _dedup(t: str) -> str:
    """OCR 多倍率串接（-Zooms 2,3,4）會重複 2～3 次：整段等分重複就只留一份"""
    for n in (4, 3, 2):
        if t and len(t) % n == 0 and t[:len(t) // n] * n == t:
            return t[:len(t) // n]
    return t


def _visit_pet_get(role):
    """多人唯讀：戰寵 首次動作（勾選 + 欄位文字）/ 一般動作（欄位文字）。回 (退出碼, dict, 訊息, [])"""
    if not pet_on_top():
        return EXIT_NOT_TOP, None, f'{role}：右半面板不在頂端（讀不到「戰寵動作」標題）；不點', []
    cols = _px([PET_FIRST_CHK])
    on = None if not cols else cols[0] != UNCHECKED
    return EXIT_OK, {'first_on': on, 'first': _dedup(read_pet_text('first')) or '?', 'normal': _dedup(read_pet_text('normal')) or '?'}, '', []


def get_pet_many(roles, no_wait: bool = False) -> tuple:
    """一次開面板逐人唯讀戰寵 首次 / 一般動作（不點任何勾選 / 下拉）。回 (rc, {角色: dict}, 訊息, info)"""
    return _many({r: None for r in ordered_roles(roles)}, _visit_pet_get, no_wait)


def set_pet_many(plan: dict, no_wait: bool = False, dry_run: bool = False, skip_missing: bool = False) -> tuple:
    """一次開面板逐人改「戰寵 一般動作」：plan = {角色: {'normal': 值}}；現值不同才改、改完讀回確認。
    只動這一項（首次動作 / 勾選 / 對象都不碰）。dry_run 只讀。回值同 set_many：(rc, {角色: {'normal': 值}}, 訊息, info)。
    EXIT_NO_OPTION：該角色的下拉找不到這個選項 → 停在該角色（不亂點、不繼續往下）。
    skip_missing=True：找不到選項的人收下拉、狀態帶 'skipped'、繼續下一個人（rebirth heal 階段用：剛轉生 Lv1 戰寵沒有忠犬）。"""
    return _many(plan, lambda role: _visit_pet_normal(plan[role]['normal'], dry_run, skip_missing)(role), no_wait)


# ---- 解任務前的戰鬥設定檢查（2026-10-12 四寶玉之謎：DKBO 人物首次動作「風的精靈Lv.5」勾選不見了 → 打火雞輸、2 人陣亡）----
# 人物動作列在「戰寵動作」上方 150 px（ui/ass.md：人物首次 勾 656,313 / 下拉 1137,313；戰寵首次 656,463 / 1137,463）。
ROLE_FIRST_CHK = (656, 313)                  # 人物 首次動作 勾選框
ROLE_FIRST_FIELD = (805, 295, 280, 40)       # 人物 首次動作 欄位文字 OCR 區（= PET_FIELD['first'] 上移 150；**未實機量**）
ROLE_KNOWN = ('攻擊', '防禦', '逃跑', '滋潤')  # 讀到這些字 = 確定不是想要的精靈技能（其他文字 / 讀不到 = 不確定，只警告）
EXIT_WRONG_ACTION = 13                       # 人物首次動作的值確定不對（下拉選項依裝備而變，不自動改）
# 解任務的戰鬥設定（questrun 交接 / bossretry 重打前查）：5 人自動戰鬥開；隊長人物首次動作 = 風的精靈Lv.5 且打勾（主視窗 DKBO）。
# 快速戰鬥 / 原地遇敵不在這裡管（解任務時系統自動關快速戰鬥；遇敵由主畫面鈕關）。隊長放最後（面板結束選在隊長）。
# 隊長的人物首次動作是帳號特有設定：主視窗 = 風的精靈；其他視窗沒量過 → 不檢查首次動作（只查 5 人自動戰鬥），
# 要檢查就設環境變數 PSA_LEADER_FIRST=技能名（或 `ass.py battle all --leader-first 技能名`；空字串 = 不檢查）。
LEADER_FIRST = {'PrimalSA': '風的精靈'}
LEADER_FIRST_ENV = 'PSA_LEADER_FIRST'


def leader_first() -> str | None:
    """隊長人物首次動作期望值：環境變數 > 視窗預設；None / 空 = 不檢查首次動作"""
    import os
    v = os.environ.get(LEADER_FIRST_ENV)
    if v is not None:
        return v.strip() or None
    return LEADER_FIRST.get(clients.dir_name())


def quest_battle(first: str | None = '') -> dict:
    """解任務戰鬥設定計畫（名單順序、隊長最後）：first='' = 用 leader_first()；None = 不檢查首次動作"""
    first = leader_first() if first == '' else first
    plan = {r: {'自動戰鬥': True} for r in clients.leader_last()}
    if LEADER and first:
        plan[LEADER] = {'自動戰鬥': True, 'first': first, 'first_on': True}
    return plan


QUEST_BATTLE = quest_battle()


def read_role_first(ocr: bool = True) -> dict | None:
    """面板開著、角色已選好：人物首次動作 → {'first_on': 勾?, 'first': 欄位文字（去空白；ocr=False 時 None）}；像素讀不到回 None"""
    cols = _px([ROLE_FIRST_CHK])
    if not cols:
        return None
    return {'first_on': cols[0] != UNCHECKED, 'first': _ocr(ROLE_FIRST_FIELD, '-Zooms', '2,3,4').replace(' ', '') if ocr else None}


def first_value_verdict(text: str | None, want: str) -> str:
    """純函式：人物首次動作欄位 OCR 文字 vs 想要的值 → 'ok' / 'wrong'（確定是別的選項）/ 'unsure'（讀不到 / 認不得）"""
    t = (text or '').replace(' ', '')
    if want and want in t:
        return 'ok'
    if any(k in t for k in ROLE_KNOWN):
        return 'wrong'
    return 'unsure'


def _visit_battle(want: dict, dry_run: bool = False):
    """battle_check 的逐人動作：讀左欄勾選（只改 want 裡的項目）+（有 first / first_on 才）讀人物首次動作，勾選不對就點、讀回確認。
    首次動作的「值」不對不改（下拉選項依裝備而變），回 EXIT_WRONG_ACTION；讀不準只記 st['first_unsure']。
    回 (退出碼, 狀態 dict, 訊息, 改了哪些)；dry_run 只讀、不點，不對的列在 st['wrong']"""
    checks = {k: v for k, v in want.items() if k in ITEMS}

    def visit(role):
        st = read_checks()
        if st is None:
            return EXIT_PANEL_LOST, None, f'{role} 讀不到勾選框像素', []
        st = dict(st)
        bad = [i for i, w in checks.items() if st.get(i) != w]
        todo = []
        if bad and not dry_run:
            rc, st2, msg = _apply_changes(role, st, checks)
            st = dict(st2 or st)
            todo = list(bad)
            if rc:
                return rc, st, msg, todo
        wrong = list(bad) if dry_run else []
        fv, fon = want.get('first'), want.get('first_on')
        if fv is None and fon is None:
            if wrong:
                st['wrong'] = wrong
            return EXIT_OK, st, '', todo
        if not pet_on_top():
            return EXIT_NOT_TOP, st, f'{role}：右半面板不在頂端（讀不到「戰寵動作」標題）；不讀 / 不點人物首次動作', todo
        rf = read_role_first(ocr=fv is not None)
        if rf is None:
            return EXIT_PANEL_LOST, st, f'{role} 讀不到人物首次動作勾選框', todo
        st['人物首次動作'], st['人物首次勾選'] = rf['first'], rf['first_on']
        if fv is not None:
            verdict = first_value_verdict(rf['first'], fv)
            if verdict == 'wrong':
                st['wrong'] = wrong + ['人物首次動作']
                return EXIT_WRONG_ACTION, st, f'{role} 人物首次動作是「{rf["first"]}」不是「{fv}」；下拉選項依裝備而變，不自動改，請人看（ui/ass.md）', todo
            if verdict == 'unsure':
                st['first_unsure'] = rf['first'] or ''
        if fon is not None and rf['first_on'] != fon:
            if dry_run:
                wrong.append('人物首次勾選')
            else:
                if not panel_open() or selected_role() != role or not pet_on_top():
                    return EXIT_PANEL_LOST, st, f'{role}：點人物首次動作勾選前面板已不在 / 角色不對 / 被捲動 → 不點', todo
                gui('seq', f'click {ROLE_FIRST_CHK[0]} {ROLE_FIRST_CHK[1]}; wait 300', note=f'ass.py {role} 人物首次動作勾選 → {"勾" if fon else "不勾"}')
                todo.append('人物首次勾選')
                for w in (CONFIRM_WAIT, CONFIRM_WAIT2):
                    sleep(w)
                    if not panel_open():
                        return EXIT_PANEL_LOST, st, f'{role}：點人物首次動作勾選後面板消失', todo
                    now = read_role_first(ocr=False)
                    if now and now['first_on'] == fon:
                        st['人物首次勾選'] = fon
                        log(f'ass：{role} 人物首次動作勾選 → {"勾" if fon else "不勾"}（已確認）')
                        break
                else:
                    return EXIT_CONFIRM, st, f'{role}：人物首次動作勾選點了沒變（不補點）', todo
        if wrong:
            st['wrong'] = wrong
        return EXIT_OK, st, '', todo
    return visit


def battle_check(plan: dict | None = None, no_wait: bool = False, dry_run: bool = False) -> tuple:
    """解任務前的戰鬥設定檢查：一次開外掛面板、左欄頭像逐人（隊長最後）讀 → 只改不對的 → 讀回確認 → 關面板。
    plan 預設 QUEST_BATTLE（{角色: {'自動戰鬥': bool, 'first': 值, 'first_on': bool}}）。戰鬥中不開面板（等到結束，逾時 / no_wait 回 8）。
    回值同 set_many：(rc, {角色: 狀態}, 訊息, info)；info['changed'] = {角色: [改過的項目]}。rc 13 = 首次動作的值確定不對（不改）"""
    plan = plan or QUEST_BATTLE
    return _many(plan, lambda role: _visit_battle(plan[role], dry_run)(role), no_wait)


def ordered_roles(roles) -> list:
    """隊長（名單第 1 個，主視窗 DKBO）放最後（面板結束選在隊長），其他照 ROLES 順序"""
    rs = [r for r in ROLES if r in set(roles)]
    return [r for r in rs if r != LEADER] + [r for r in rs if r == LEADER]


NOPAUSE_RETRY = 2                # 不暫停遇敵時，面板被戰鬥打斷（6）/ 下拉在戰鬥轉場讀不到（12）→ 重試次數


def _retry_nopause(fn, pause: bool):
    """快速戰鬥中開外掛面板不用先停遇敵（2026-10-12 使用者）：不暫停時遇到戰鬥打斷（rc 6 / 12）就短暫等待重試，
    已改好的角色現值相同不會重改。pause=True（--pause）不重試。"""
    r = fn()
    n = 0
    while not pause and r[0] in (EXIT_PANEL_LOST, EXIT_NO_OPTION) and n < NOPAUSE_RETRY:
        n += 1
        sleep(3.0)
        r = fn()
    return r


def run_pet_many(roles, value: str, dry_run: bool = False, pause: bool = True, resume: bool = True,
                 no_wait: bool = False) -> tuple:
    """CLI 用完整流程：[pause：preflight → 關原地遇敵 + 等戰鬥結束（不開切換面板）] → set_pet_many → [resume：grind ensure 恢復掛機]。
    回 (退出碼, {角色: 狀態}, 訊息, info)。恢復掛機一律會做（pause 且 resume 時），即使中間失敗，免得遇敵一直關著；ensure 失敗且編輯成功時退出碼 = ensure 的退出碼。"""
    import uikit
    plan = {r: {'normal': value} for r in ordered_roles(roles)}
    rc, sts, msg, info = EXIT_OK, {}, '', {}
    if pause:
        import heal
        rc = uikit.preflight('ass')
        if rc:
            return rc, {}, f'preflight 失敗（{rc}）；沒動任何東西', {}
        # 掛機中戰鬥一場接一場，戰鬥畫面讀不到切換面板（char rc 60）→ 先關遇敵、等 VS 牌消失才開外掛面板
        nobat = f'waitpix 20000 {heal.SIG_NO_BATTLE} 40'
        heal.set_encounter(False)
        heal.gui('seq', nobat)
        # 當前角色一律維持 DKBO（使用者規定），這裡不開切換面板確認（每次確認都開關一次切換面板）；
        # 恢復掛機的 grind ensure 開頭會 char.ensure(DKBO) 驗一次，並重新確認隊伍 / 外掛 / 遇敵。
    if rc:
        sts, msg, info = {}, f'preflight 失敗（{rc}）', {}
    else:
        rc, sts, msg, info = _retry_nopause(lambda: set_pet_many(plan, no_wait, dry_run), pause)
    if pause and resume and rc != 9:          # 9 = 疑似驗證視窗：不碰遊戲，交給使用者
        import grind
        grc = grind.run('ensure')
        info['grind_rc'] = grc
        if grc and not rc:
            rc, msg = grc, f'戰寵動作已處理，但恢復掛機（grind ensure）退出碼 {grc}'
    return rc, sts, msg, info


# ---- 便捷功能 → 特色設定：角色自動加點（2026-10-15，新角色開局 newchar.py 用）----
# 座標取自 ui/ass.md「便捷功能 → 特色設定：角色自動加點」2026-10-09 實測（右上核取 / 分頁 / 勾選框 / SET / 視窗確認取消）。
# **未實機**：OCR 框（PT_FEAT_BOX / PT_DLG_TITLE_BOX / PT_ROWS_BOX）是依實測座標推估的，讀不到 → 16 停手、不點勾選；
# 視窗裡「改目標值」的輸入流程沒實測過（ui/ass.md：未實測輸入流程）→ **不自動改方案**：方案跟 POINTS_PLAN 不同 → 15，請人手動設。
# 勾「自定義加點 / 同步加點」只在讀到的方案 = POINTS_PLAN 時才做（方案不對就勾，會把點數加錯地方，點數加下去不可逆）。
RIGHT_BATTLE, RIGHT_CONV = (647, 148), (815, 148)    # 右上核取：右半顯示「戰鬥設置」/「便捷功能」那組分頁（擇一）
BATTLE_TAB = (696, 206)                             # 戰鬥設置分頁（做完還原，其他功能依賴右半在戰鬥設置頂端）
FEAT_TAB = (840, 207)                               # 便捷功能 → 特色設定分頁
PT_CUSTOM, PT_RECOMMEND, PT_SYNC = (666, 315), (666, 368), (666, 421)   # 自定義加點 / 使用推薦加點 / 同步加點 勾選框
PT_SET = (1280, 315)                                # 自定義加點 SET → 開「自定義加點設定」視窗
PT_OK, PT_CANCEL = (610, 509), (766, 509)           # 視窗 確認 / 取消（只看 → 取消）
PT_FEAT_BOX = (690, 295, 330, 150)                  # 特色設定三列標籤文字（含「加點」）；**未實機量**
PT_DLG_TITLE_BOX = (470, 185, 400, 45)              # 「自定義加點設定」標題（含「加點」）；**未實機量**
PT_ROWS_BOX = (470, 265, 380, 210)                  # 4 列：順序（屬性名 x≈540）/ 當前 669 / 目標 770；**未實機量**
PT_ROW_TOL = 18                                     # 同一列的 y 容差（列距約 52）
STAT_NAMES = ('體力', '腕力', '耐力', '速度')
POINTS_PLAN = [('速度', 80), ('體力', 50), ('腕力', 999), ('耐力', 0)]   # 本帳號方案（ui/ass.md，使用者 2026-10-09 設定，5 角色同步）
EXIT_POINTS_PLAN = 15                               # 方案不是 POINTS_PLAN：目標值輸入流程未實測（座標待量測）→ 不改、不勾，請人手動設
EXIT_POINTS_READ = 16                               # 特色設定分頁 / 加點視窗讀不到（OCR 框未實機量）→ 不點勾選


def parse_points(lines) -> list | None:
    """純函式：加點視窗 OCR 行 [(文字, x, y)] → [(屬性, 目標)]（由上往下）。一列 = y 相近（±PT_ROW_TOL）的字串依 x 接起來；
    要剛好 1 個屬性名、而且至少 2 個整數（當前 + 目標，取最後一個當目標；只讀到 1 個數字 = 分不出當前 / 目標 → 不採用）。
    讀到的列不是 4 列 → None（讀不準，不猜）"""
    rows: list = []
    for t, x, y in sorted(lines or [], key=lambda l: l[2]):
        for r in rows:
            if abs(r['y'] - y) <= PT_ROW_TOL:
                r['parts'].append((x, str(t)))
                break
        else:
            rows.append({'y': y, 'parts': [(x, str(t))]})
    out = []
    for r in rows:
        txt = ' '.join(t for _, t in sorted(r['parts']))
        names = [n for n in STAT_NAMES if n in txt]
        if len(names) != 1:
            continue
        nums = re.findall(r'\d+', txt.split(names[0], 1)[1])
        if len(nums) < 2:
            return None
        out.append((names[0], int(nums[-1])))
    return out if len(out) == 4 else None


def _points_click(role: str, xy, note: str, wait_ms: int = 400) -> bool:
    """點特色設定 / 加點視窗內的座標前先驗面板還開著、角色沒變（沒開時這些座標會穿透到地面）"""
    if not panel_open() or selected_role() != role:
        return False
    gui('seq', f'click {xy[0]} {xy[1]}; wait {wait_ms}', note=f'ass.py {role} {note}')
    return True


def _points_restore(role: str) -> None:
    """右半切回「戰鬥設置」分頁組（其他功能 pet_on_top / battle_check 依賴右半在戰鬥設置頂端）；面板不在就不點"""
    if panel_open():
        gui('seq', f'click {RIGHT_BATTLE[0]} {RIGHT_BATTLE[1]}; wait 400; click {BATTLE_TAB[0]} {BATTLE_TAB[1]}; wait 400',
            note=f'ass.py {role} 右半切回戰鬥設置')


def _points_read_plan(role: str) -> tuple:
    """特色設定頁：SET 開視窗 → 驗標題 → OCR 4 列 → 取消關窗。→ (rc, [(屬性, 目標)] | None, 訊息)"""
    if not _points_click(role, PT_SET, '自定義加點 SET（開視窗看方案）', 700):
        return EXIT_PANEL_LOST, None, f'{role}：點 SET 前面板已不在 / 角色不對 → 不點'
    if '加點' not in _ocr(PT_DLG_TITLE_BOX, '-Zooms', '2,3,4'):
        gui('key', '{ESC}', note=f'ass.py {role} 加點視窗標題讀不到 → ESC（外掛面板可能一起關）')
        return EXIT_POINTS_READ, None, f'{role}：點了 SET 但讀不到「自定義加點設定」標題（OCR 框未實機量）；已 ESC、沒改任何東西'
    plan = parse_points(_ocr_lines(PT_ROWS_BOX, '-Zooms', '2,3,4'))
    gui('seq', f'click {PT_CANCEL[0]} {PT_CANCEL[1]}; wait 500', note=f'ass.py {role} 加點視窗 取消（只看）')
    if '加點設定' in _ocr(PT_DLG_TITLE_BOX, '-Zooms', '2,3'):
        gui('key', '{ESC}', note=f'ass.py {role} 加點視窗取消後還在 → ESC')
        return EXIT_POINTS_READ, plan, f'{role}：按了取消但加點視窗還在（已 ESC）'
    if plan is None:
        return EXIT_POINTS_READ, None, f'{role}：加點視窗 4 列讀不準（OCR 框未實機量）；沒改任何東西'
    return EXIT_OK, plan, ''


def _visit_points(want_plan, apply: bool, read_plan: bool = True):
    """points_get / points_set 的逐人動作（_many 用）：右半切便捷功能 → 特色設定 → 讀兩個勾選 →（read_plan）SET 視窗讀方案 →
    （apply 且方案 = want_plan）勾自定義加點 / 同步加點、讀回確認 → 一律切回戰鬥設置。回 (退出碼, 狀態, 訊息, 改了哪些)"""
    def visit(role):
        st, todo = {}, []
        try:
            if not _points_click(role, RIGHT_CONV, '右半切便捷功能') or not _points_click(role, FEAT_TAB, '特色設定分頁', 500):
                return EXIT_PANEL_LOST, None, f'{role}：切便捷功能前面板已不在 / 角色不對 → 不點', []
            if '加點' not in _ocr(PT_FEAT_BOX, '-Zooms', '2,3,4'):
                return EXIT_POINTS_READ, None, f'{role}：特色設定分頁讀不到「加點」字樣（OCR 框未實機量）；不點勾選', []
            cols = _px([PT_CUSTOM, PT_SYNC])
            if not cols:
                return EXIT_PANEL_LOST, None, f'{role}：讀不到加點勾選框像素', []
            st['自定義加點'], st['同步加點'] = cols[0] != UNCHECKED, cols[1] != UNCHECKED
            if read_plan:
                rc, plan, msg = _points_read_plan(role)
                st['plan'] = plan
                if rc:
                    return rc, st, msg, []
            if not apply:
                return EXIT_OK, st, '', []
            if st.get('plan') != list(want_plan):
                return (EXIT_POINTS_PLAN, st, f'{role}：加點方案是 {st.get("plan")}，不是 {list(want_plan)}；視窗改目標值的輸入流程未實測（座標待量測），'
                        f'不自動改、也不勾自定義 / 同步加點 → 請人手動設定方案（ui/ass.md「自定義加點設定視窗」）', [])
            for item, xy in (('自定義加點', PT_CUSTOM), ('同步加點', PT_SYNC)):
                if st[item]:
                    continue
                if not _points_click(role, xy, f'{item} → 勾', 300):
                    return EXIT_PANEL_LOST, st, f'{role}：點 {item} 前面板已不在 / 角色不對 → 不點', todo
                todo.append(item)
                for w in (CONFIRM_WAIT, CONFIRM_WAIT2):
                    sleep(w)
                    now = _px([xy])
                    if now and now[0] != UNCHECKED:
                        st[item] = True
                        log(f'ass：{role} {item} → 勾（已確認）')
                        break
                else:
                    return EXIT_CONFIRM, st, f'{role}：{item} 點了沒變（不補點）', todo
            return EXIT_OK, st, '', todo
        finally:
            _points_restore(role)
    return visit


def points_get(roles, read_plan: bool = True, no_wait: bool = False) -> tuple:
    """唯讀：一次開面板逐人讀 自定義加點 / 同步加點 勾選（read_plan = 另開 SET 視窗讀方案、按取消）。回值同 set_many"""
    return _many({r: None for r in roles}, _visit_points(POINTS_PLAN, False, read_plan), no_wait)


def points_set(leader: str | None = None, verify=(), want_plan=None, no_wait: bool = False) -> tuple:
    """隊長（預設名單第 1 個）讀方案 = want_plan（預設 POINTS_PLAN）才勾自定義加點 + 同步加點（同步 = 其他角色套用同一方案，ui/ass.md 實測）；
    verify = 之後唯讀看哪些角色的勾選（不開視窗）。方案不同 → 15（不改、不勾）；讀不到 → 16。回值同 set_many"""
    leader = leader or LEADER
    want = list(want_plan or POINTS_PLAN)
    plan = {leader: 'set', **{r: 'get' for r in verify if r != leader}}
    visits = {'set': _visit_points(want, True, True), 'get': _visit_points(want, False, False)}
    return _many(plan, lambda role: visits[plan[role]](role), no_wait)


def _main_points(a) -> int:
    rest = [x.lower() for x in a.rest]
    if rest not in (['get'], ['set']):
        print('points 用法：ass.py points all|DKBO,DKBO2 get [--no-plan] | ass.py points DKBO set（只對隊長：方案 = 速度80 / 體力50 / 腕力999 / 耐力0 才勾自定義 + 同步加點）')
        return EXIT_USAGE
    roles = list(ROLES) if a.role.lower() == 'all' else [norm_role(r) for r in a.role.split(',')]
    if not roles or not all(roles):
        print(f'角色要是 all 或逗號分隔的 {" / ".join(ROLES)}')
        return EXIT_USAGE
    if rest == ['set'] and len(roles) != 1:
        print('points set 只給一個角色（隊長；同步加點會套用到其他角色）')
        return EXIT_USAGE
    if layout.current() != '2880x1659':
        print('ass.py 只量過 2880×1659 版面，先跑 gui.sh max')
        return EXIT_LAYOUT
    import winenv
    winenv.enable_server()
    if rest == ['get']:
        rc, sts, msg, _ = points_get(roles, not a.no_plan, a.no_wait)
    else:
        rc, sts, msg, _ = points_set(roles[0], [r for r in ROLES if r != roles[0]], None, a.no_wait)
    for r, st in sts.items():
        print(f'{r}：自定義加點={"勾" if st.get("自定義加點") else "不勾"}  同步加點={"勾" if st.get("同步加點") else "不勾"}'
              + (f'  方案={st["plan"]}' if 'plan' in st else ''))
    if rc:
        print(f'失敗（退出碼 {rc}）：{msg}')
    return rc


def fmt(states: dict, items=None) -> str:
    return '  '.join(f'{i}={"開" if states[i] else "關"}' for i in (items or ITEMS) if i in states)


def _main_pet(role: str, rest: list, no_wait: bool = False) -> int:
    want = {}
    if rest != ['get']:
        if not rest:
            print('pet 用法：get | first <攻擊|防禦|忠犬|on|off> | normal <攻擊|防禦|忠犬>（可串接）')
            return EXIT_USAGE
        i = 0
        while i < len(rest):
            k = rest[i]
            v = rest[i + 1] if i + 1 < len(rest) else ''
            v = OPT_ALIASES.get(v.lower(), v)
            if k == 'first' and v.lower() in ('on', 'off'):
                want['first_on'] = v.lower() == 'on'
            elif k == 'first' and v in PET_OPTS:
                want['first'], want['first_on'] = v, True
            elif k == 'normal' and v in PET_OPTS:
                want['normal'] = v
            else:
                print(f'參數錯：{k} {v}')
                return EXIT_USAGE
            i += 2
    if layout.current() != '2880x1659':
        print('ass.py 只量過 2880×1659 版面，先跑 gui.sh max')
        return EXIT_LAYOUT
    rc, st, msg = _pet_session(role, want or None, no_wait)
    if st:
        print(f'{role} 戰寵：首次動作={"勾" if st["first_on"] else "不勾"}/{st["first"] or "?"}  一般動作={st["normal"] or "?"}')
    if rc:
        print(f'失敗（退出碼 {rc}）：{msg}')
    return rc


def fmt_battle(st: dict) -> str:
    s = f'自動戰鬥={"開" if st.get("自動戰鬥") else "關"}'
    if '人物首次勾選' in st:
        s += f'  人物首次動作={"勾" if st["人物首次勾選"] else "不勾"}/{st.get("人物首次動作") or "?"}'
    if st.get('wrong'):
        s += f'  不對：{"、".join(st["wrong"])}'
    return s


def _main_battle(a) -> int:
    if a.role.lower() != 'all':
        print('battle 用法：ass.py battle all [--dry-run] [--no-wait]（固定檢查 QUEST_BATTLE 的 5 人）')
        return EXIT_USAGE
    if layout.current() != '2880x1659':
        print('ass.py 只量過 2880×1659 版面，先跑 gui.sh max')
        return EXIT_LAYOUT
    import winenv
    winenv.enable_server()
    plan = quest_battle(a.leader_first) if a.leader_first is not None else None
    rc, sts, msg, info = battle_check(plan, a.no_wait, a.dry_run)
    for r, st in sts.items():
        ch = info.get('changed', {}).get(r)
        print(f'{r}：{fmt_battle(st)}' + (f'（改了 {"、".join(ch)}）' if ch else ''))
    if rc:
        print(f'失敗（退出碼 {rc}）：{msg}')
    return rc


def _run_pet_get_many(roles, pause: bool, resume: bool, no_wait: bool) -> int:
    import uikit
    rc, sts, msg = EXIT_OK, {}, ''
    if pause:
        import heal
        rc = uikit.preflight('ass')
        if rc:
            print(f'preflight 失敗（{rc}）；沒動任何東西')
            return rc
        heal.set_encounter(False)
        heal.gui('seq', f'waitpix 20000 {heal.SIG_NO_BATTLE} 40')
    rc, sts, msg, _ = _retry_nopause(lambda: get_pet_many(roles, no_wait), pause)
    for r, st in sts.items():
        print(f'{r} 戰寵 首次動作={"勾" if st["first_on"] else "不勾"}/{st["first"]}  一般動作={st["normal"]}')
    if rc:
        print(f'失敗（退出碼 {rc}）：{msg}')
    if pause and resume and rc != 9:
        import grind
        grc = grind.run('ensure')
        print(f'恢復掛機 grind ensure 退出碼 {grc}')
        rc = rc or grc
    return rc


def _main_pet_many(a) -> int:
    roles = list(ROLES) if a.role.lower() == 'all' else [norm_role(r) for r in a.role.split(',')]
    if not all(roles) or len(set(roles)) != len(roles):
        print(f'角色要是 all 或逗號分隔的 {" / ".join(ROLES)}（不可重複）')
        return EXIT_USAGE
    rest = [OPT_ALIASES.get(x.lower(), x) for x in a.rest]
    if rest == ['get']:             # 唯讀：不動任何勾選；同樣先暫停遇敵、讀完恢復掛機
        if layout.current() != '2880x1659':
            print('ass.py 只量過 2880×1659 版面，先跑 gui.sh max')
            return EXIT_LAYOUT
        import winenv
        winenv.enable_server()
        return _run_pet_get_many(roles, a.pause, not a.no_resume, a.no_wait)
    if len(rest) != 2 or rest[0] != 'normal' or not rest[1]:
        print('多人 pet 用法：ass.py pet all|DKBO,DKBO2… normal <攻擊|防禦|已學寵物技能名> [--dry-run] [--pause] [--no-resume]')
        return EXIT_USAGE
    if layout.current() != '2880x1659':
        print('ass.py 只量過 2880×1659 版面，先跑 gui.sh max')
        return EXIT_LAYOUT
    import winenv
    winenv.enable_server()          # char / grind 的 main 都會開常駐 server；沒開時切換面板讀像素常逾時（rc 60）
    rc, sts, msg, info = run_pet_many(roles, rest[1], a.dry_run, a.pause, not a.no_resume, a.no_wait)
    for r, st in sts.items():
        print(f'{r} 戰寵 一般動作={st["normal"]}{"（改了）" if r in info.get("changed", {}) else ""}')
    if rc:
        print(f'失敗（退出碼 {rc}）：{msg}')
    return rc


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description='外掛 ASS 左欄戰鬥設定讀 / 設')
    ap.add_argument('cmd', choices=['get', 'set', 'pet', 'battle', 'points'])
    ap.add_argument('role', help='名單內角色：主視窗 DKBO / DKBO2~5、PrimalSA2 DKBO6~10（DKB0… 同義）')
    ap.add_argument('rest', nargs='*', help='get：項目…；set：項目 on|off 成對')
    ap.add_argument('--dry-run', action='store_true', help='多人 pet：只讀不改')
    ap.add_argument('--pause', action='store_true', help='多人 pet：先關原地遇敵 + 等戰鬥結束、改完 grind ensure 恢復（預設不暫停：快速戰鬥中開面板不用停遇敵）')
    ap.add_argument('--no-pause', action='store_true', help='（相容舊旗標；現為預設，無作用）')
    ap.add_argument('--no-resume', action='store_true', help='多人 pet：改完不跑 grind ensure 恢復掛機（遇敵會維持關閉）')
    ap.add_argument('--leader-first', default=None, help='battle：隊長人物首次動作期望值（預設主視窗 風的精靈、其他視窗不檢查；空字串 = 不檢查）')
    ap.add_argument('--no-plan', action='store_true', help='points get：不開 SET 視窗讀方案（只讀勾選）')
    ap.add_argument('--no-wait', action='store_true', help='戰鬥中不等戰鬥結束，直接退出碼 %d（預設等最多 %d 秒）' % (EXIT_IN_BATTLE, BATTLE_WAIT))
    a = ap.parse_args(argv)
    if a.cmd == 'battle':
        return _main_battle(a)
    if a.cmd == 'points':
        return _main_points(a)
    if a.cmd == 'pet' and (a.role.lower() == 'all' or ',' in a.role):
        return _main_pet_many(a)
    role = norm_role(a.role)
    if not role:
        print(f'角色要是 {" / ".join(ROLES)}')
        return EXIT_USAGE
    if a.cmd == 'pet':
        return _main_pet(role, a.rest, a.no_wait)
    changes, items = {}, []
    if a.cmd == 'get':
        for n in a.rest:
            it = norm_item(n)
            if not it:
                print(f'不認得的項目：{n}（{" / ".join(ITEMS)}）')
                return EXIT_USAGE
            items.append(it)
    else:
        if not a.rest or len(a.rest) % 2:
            print('set 要成對：項目 on|off')
            return EXIT_USAGE
        for n, v in zip(a.rest[::2], a.rest[1::2]):
            it = norm_item(n)
            if not it or v.lower() not in ('on', 'off', '開', '關'):
                print(f'參數錯：{n} {v}')
                return EXIT_USAGE
            changes[it] = v.lower() in ('on', '開')
        items = list(changes)
    if layout.current() != '2880x1659':
        print('ass.py 只量過 2880×1659 版面，先跑 gui.sh max')
        return EXIT_LAYOUT
    rc, states, msg = _session(role, changes if a.cmd == 'set' else None, None, a.no_wait)
    if states:
        print(f'{role}：{fmt(states, items or None)}')
    if rc:
        print(f'失敗（退出碼 {rc}）：{msg}')
    return rc


if __name__ == '__main__':
    sys.exit(main())
