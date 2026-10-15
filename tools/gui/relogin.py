#!/usr/bin/env python3
"""主動「全員重登」（AGENTS.md §7 腳本化）：設置 → 全員登出 → 確認 → 登入畫面只按「登錄」→ 一鍵全登 → 檢查隊伍 / 當前角色。只用標準函式庫。

用途：伺服器端卡死（全隊頭上 VS 牌、「戰鬥中禁止當前操作」、刷新無效）時，登出再登入把狀態洗乾淨。
實測（2026-10-12 手動一次成功）：重登後隊伍沒散；netwatch 不介入，所以不會 grind ensure（要練功再跑 grind.py ensure）。

用法（專案根目錄；WSL / Windows 原生指令相同）：
  uv run --no-project python tools/gui/relogin.py --confirm [--leader DKBO] [--size 5] [--no-team]
  uv run --no-project python tools/gui/relogin.py --dry-run     # 只做前置檢查（唯讀、不點任何東西），印會做的步驟
  --stuck：起始畫面除了主畫面，也接受「自動巡路中」（Auto Walking 卡住）與「快速戰鬥 VS 牌」（伺服器端卡死）；完整戰鬥畫面一律不動（107）。
           questrun 在 quest.py 19 / 42 / VS 牌卡住時用（relogin.run(confirm=True, stuck=True)）
登出是**不可逆動作（所有角色下線，進行中的任務 / 戰鬥中斷）**：沒有 --confirm 一律不動（退出碼 1）。

流程與畫面驗證（座標 = 截圖座標 1440x830）：
  1 preflight（版面 / netwatch halt / battle.lock / 畫面不是 unknown）→ 畫面必須是主畫面（或設置面板已開；--stuck 另收巡路中 / 快速戰鬥 VS 牌）
  2 開設置面板（1210,760，標題板特徵 + ✕）→ 讀「全員登出」鈕顏色（橘紅，樣本 p4/panel_setting.png 量得）才點 517,731
  3 「是否登出全部角色?」提示：像素特徵（米色單鈕提示窗，同網路異常）+ OCR 訊息含「登 / 出 / 全」（OCR 讀不出就信任像素；讀到別的字 → 不點）→ 確定 715,557
  4 等回登入畫面（≤ 60 s）→ netwatch.relogin：帳密欄有內容才點「登錄」590,585（帳密欄空 / 登錄後提示窗 / 連續 3 次失敗 = halt）→ 選角面板「一鍵全登」740,640 → 等進遊戲（約 20 s）
  5 team.check（5 人、隊長 DKBO）；全員單人才 team.form；最後 char.ensure DKBO（重登後當前角色會變 DKBO5）
鐵則 2：登入畫面只點「登錄」（遊戲自動帶入的帳密）；不輸入 / 清除帳密欄、不點鑰匙 / 註冊、不把帳號寫進 log、登入畫面不存截圖。
鐵則 5：出現驗證 / 答題視窗 → 不處理、停手通知使用者。

退出碼（共用 0 / 1 / 2 / 8 / 9 / 10 見 uikit，11 = netwatch 連續登錄失敗；relogin 自己 100～108）：
  100 設置面板打不開，或「全員登出」鈕特徵不符（沒點任何登出相關座標）
  101 點了全員登出但確認提示窗 4 s 內沒出現（不點確定、不重點）
  102 提示窗訊息 OCR 讀到的不是「登出」（不點，留給人類看）
  103 點確定後 60 s 沒回到登入畫面，或中途又冒出提示窗（停手看畫面）
  104 登入畫面階段 netwatch.relogin 沒成功但不是 halt（忙碌中 / 讀不到畫面）；halt / fatal 分別是 10 / 11
  105 重登進遊戲了，但隊伍檢查 / 組隊失敗（team.py 的 41 / 42 / 43 …，訊息有詳情）
  106 重登進遊戲了，但當前角色切回隊長失敗（char.py 的退出碼，訊息有詳情）
  107 起始畫面不是主畫面（戰鬥 / 其他面板 / 對話；--stuck 時只擋完整戰鬥 / 面板 / 對話）→ 不動
  108 netwatch 動作鎖被別的腳本佔用 → 不動
  109 多視窗不自動重登（netwatch.auto_login_check：非主視窗，或主視窗時還有別的 PrimalSA* 在跑 / 查不到程序清單）→ 什麼都不點（登出後回不來，2026-10-15 使用者決定）
未實機驗證（只有離線測試）：設置面板標題板 / ✕ 特徵（樣本有，沿用 screen_sigs）、全員登出鈕顏色、確認提示窗的像素特徵與 OCR 框（假設與網路異常提示同款單鈕窗；
首次手動登出時使用者只給了座標 715,557）、「等回登入畫面」的時序。這些判斷都保守：不符就停手不點。
"""
import argparse
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import actlog  # noqa: E402
import charstate  # noqa: E402
import clients  # noqa: E402
import netwatch  # noqa: E402
import screen_sigs  # noqa: E402
import uikit  # noqa: E402

SRC = 'relogin'
ROLES = clients.roster() or list(charstate.DEFAULT_CHARS)   # 這個視窗（PSA_CLIENT）的名單：隊長 = 第 1 個、隊伍人數 = 名單人數（主視窗 DKBO、5 人）
(EXIT_PANEL, EXIT_NO_PROMPT, EXIT_PROMPT_OTHER, EXIT_NO_LOGIN, EXIT_RELOGIN_FAIL,
 EXIT_TEAM, EXIT_CHAR, EXIT_NOT_IDLE, EXIT_BUSY, EXIT_MULTI) = range(100, 110)

LOGOUT_BTN = (517, 731)              # 設置面板底部「全員登出」
LOGOUT_SIG = [(517, 722, 195, 89, 57, 30), (517, 731, 201, 82, 50, 30)]   # 橘紅鈕面（p4/panel_setting.png / set_DKBO.png 量得）
OTHER_BTNS = {'fix': uikit.rect(290, 731, 40), 'save_point': uikit.rect(921, 731, 40), 'offline': uikit.rect(1145, 731, 40)}
SETTING_SIG = [(x, y, r, g, b, screen_sigs.PANEL_TOL) for x, y, r, g, b in screen_sigs.PANEL_PTS['setting']] + [
    (1340, 85, 197, 73, 49, 40)]                                           # 面板邊緣 / 底板 8 點 + 右上 ✕（標題板字點會隨底下地圖 / 動畫變色，實機 rc 100，不用）
SETTING = uikit.Panel('SETTING', (1210, 760), SETTING_SIG, (1340, 85),
                      forbidden=dict(OTHER_BTNS, logout_all=uikit.rect(*LOGOUT_BTN, 40)))   # 全員登出只有本腳本 allow
PROMPT_BOX = (500, 300, 430, 160)    # 提示窗訊息 OCR 框（同背包批量刪除提示窗）
PROMPT_KEYS = ('登', '出', '全')
PROMPT_WAIT_S = 4.0
LOGIN_WAIT_S = 60.0
POLL_S = 1.0

_match = netwatch._match             # 三態（True / False / None）；測試替換
sleep = time.sleep


def log(msg: str) -> None:
    print(f'{SRC}：{msg}', flush=True)


def _read_prompt() -> str:
    """提示窗訊息 OCR（讀不出回 ''）；測試替換"""
    return ''.join(uikit.ocr(PROMPT_BOX, '-Light', 200, '-Zooms', '2,3'))


def _logout_btn_ok() -> bool:
    cols = uikit.px([(x, y) for x, y, *_ in LOGOUT_SIG])
    return bool(cols) and all(screen_sigs.close(c, (r, g, b), t) for c, (_, _, r, g, b, t) in zip(cols, LOGOUT_SIG))


def _wait_prompt() -> bool:
    end = time.time() + PROMPT_WAIT_S
    while True:
        if _match(netwatch.SIG_DIALOG) is True:
            return True
        if time.time() >= end:
            return False
        sleep(0.3)


def logout_all() -> int:
    """設置 → 全員登出 → 確認，回到登入畫面（SIG_LOGIN）才算成功。回 0 或 100～103"""
    if not uikit.open_panel(SETTING):
        uikit.snap('relogin-setting-fail')
        return uikit.fail(SRC, EXIT_PANEL, '設置面板打不開（標題板 / ✕ 特徵沒出現），沒點任何登出相關座標')
    if not _logout_btn_ok():
        uikit.snap('relogin-btn-fail')
        uikit.close_panel(SETTING, known_open=True)
        return uikit.fail(SRC, EXIT_PANEL, '設置面板的「全員登出」鈕顏色不符，不點')
    log('設置面板 → 點「全員登出」')
    if not uikit.safe_click(LOGOUT_BTN[0], LOGOUT_BTN[1], SETTING, note='全員登出', allow=('logout_all',)):
        return uikit.fail(SRC, EXIT_PANEL, '點全員登出前設置面板特徵消失，不點')
    if not _wait_prompt():
        uikit.snap('relogin-noprompt')
        return uikit.fail(SRC, EXIT_NO_PROMPT, f'點了全員登出但 {PROMPT_WAIT_S:.0f} s 內沒出現確認提示窗，不點確定（請看畫面）')
    txt = _read_prompt()
    if txt and not any(k in txt for k in PROMPT_KEYS):
        uikit.snap('relogin-prompt-other')
        return uikit.fail(SRC, EXIT_PROMPT_OTHER, f'提示窗訊息是「{txt}」不像「是否登出全部角色?」，不點確定')
    log(f'確認提示窗（訊息「{txt or "OCR 讀不出，信任像素"}」）→ 確定')
    actlog.add(SRC, '全員登出（主動重登）')
    uikit.gui('click', str(netwatch.CONFIRM[0]), str(netwatch.CONFIRM[1]), note='登出全部角色→確定')
    end = time.time() + LOGIN_WAIT_S
    while time.time() < end:
        sleep(POLL_S)
        if _match(netwatch.SIG_LOGIN) is True:
            return 0
        if _match(netwatch.SIG_DIALOG) is True:
            return uikit.fail(SRC, EXIT_NO_LOGIN, '確定後又冒出提示窗（可能是別種提示 / 驗證），不處理，請使用者看畫面')
    return uikit.fail(SRC, EXIT_NO_LOGIN, f'點確定後 {LOGIN_WAIT_S:.0f} s 沒回到登入畫面（登入畫面不存截圖，請使用者看畫面）')


def relogin_stage() -> int:
    """登入畫面 → 只按登錄 → 一鍵全登 → 進遊戲（全交給 netwatch.relogin，帳密規則都在那裡）"""
    r = netwatch.relogin(SRC, grind_ensure=False, encounter=False, team=False)
    st = r.get('status')
    if st == 'reconnected':
        return 0
    if st == 'halt':
        return uikit.EXIT_HALT
    if st == 'fatal':
        return netwatch.EXIT_FATAL
    return uikit.fail(SRC, EXIT_RELOGIN_FAIL, f'登入畫面階段沒成功（{r}），請看畫面')


def team_stage(leader: str, size: int) -> int:
    """重登後檢查 size 人在隊且隊長 = leader；全員單人才 form；最後當前角色切回 leader"""
    import char
    import team
    rc = team.check(size, leader)
    if rc in (team.EXIT_INCOMPLETE, team.EXIT_NO_TEAM):
        log(f'隊伍檢查 rc {rc}，嘗試快速組隊')
        rc = team.form(leader, size)
        if rc:
            return uikit.fail(SRC, EXIT_TEAM, f'重登後組隊失敗（team.form rc {rc}）')
    elif rc:
        return uikit.fail(SRC, EXIT_TEAM, f'重登後隊伍檢查失敗（team.check rc {rc}）')
    charstate.clear()
    rc = char.ensure(leader)
    if rc:
        return uikit.fail(SRC, EXIT_CHAR, f'當前角色切回 {leader} 失敗（char.ensure rc {rc}）')
    rc = team.check(size, leader)
    if rc:
        return uikit.fail(SRC, EXIT_TEAM, f'最後確認隊伍失敗（team.check rc {rc}）')
    return 0


def start_ok(st: dict, stuck: bool = False) -> bool:
    """純函式：起始畫面能不能開始登出。主畫面 / 設置面板已開 = 可以；stuck 另收自動巡路中、快速戰鬥（頭上 VS 牌，沒有完整戰鬥畫面）"""
    state = st.get('state')
    if state == 'idle' or (state == 'panel' and st.get('panel') == 'setting'):
        return True
    return bool(stuck) and (state == 'walking' or (state == 'battle' and not st.get('full')))


def run(confirm: bool = False, dry_run: bool = False, leader: str = ROLES[0], size: int = len(ROLES), check_team: bool = True,
        stuck: bool = False) -> int:
    if not confirm and not dry_run:
        print(f'{SRC}：登出會讓全部角色下線（不可逆），沒有 --confirm 不動；只想看前置檢查用 --dry-run', file=sys.stderr)
        return uikit.EXIT_USAGE
    rc = uikit.preflight(SRC)
    if rc:
        return rc
    how, why = netwatch.auto_login_check()          # 多視窗：登出後不會自動按登錄 → 根本不登出
    if how != 'ok':
        return uikit.fail(SRC, EXIT_MULTI, why if how == 'block' else f'{why}，不重登')
    st = uikit.screen(full=True)
    if not start_ok(st, stuck):
        return uikit.fail(SRC, EXIT_NOT_IDLE, f'起始畫面不是主畫面（state={st.get("state")} panel={st.get("panel")} full={st.get("full")}'
                          + ('；--stuck 也只收巡路中 / 快速戰鬥 VS 牌' if stuck else '') + '），不動')
    if dry_run:
        log('--dry-run：前置檢查通過。會做：開設置 → 全員登出 → 確認 → 登錄 → 一鍵全登'
            + (f' → team.check（{size} 人、隊長 {leader}）→ char.ensure {leader}' if check_team else ''))
        return 0
    if not netwatch._take(netwatch.ACT_LOCK, 300):
        return uikit.fail(SRC, EXIT_BUSY, 'netwatch 動作鎖被別的腳本佔用，不動')
    try:
        rc = logout_all()
    finally:
        netwatch._release(netwatch.ACT_LOCK)          # relogin 自己會拿鎖
    if rc:
        return rc
    charstate.clear()
    rc = relogin_stage()
    if rc:
        return rc
    if check_team:
        rc = team_stage(leader, size)
        if rc:
            return rc
    log('全員重登完成')
    actlog.add(SRC, '全員重登完成')
    return 0


def main() -> int:
    import winenv
    winenv.enable_server()
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--confirm', action='store_true', help='確認要全員登出（不可逆）')
    ap.add_argument('--dry-run', action='store_true', help='只做前置檢查，不點任何東西')
    ap.add_argument('--leader', default=ROLES[0])
    ap.add_argument('--size', type=int, default=len(ROLES))
    ap.add_argument('--no-team', action='store_true', help='重登後不檢查隊伍 / 當前角色')
    ap.add_argument('--stuck', action='store_true', help='卡死時用：起始畫面也接受自動巡路中 / 快速戰鬥 VS 牌（完整戰鬥仍不動）')
    a = ap.parse_args()
    return run(a.confirm, a.dry_run, a.leader, a.size, not a.no_team, a.stuck)


if __name__ == '__main__':
    sys.exit(main())
