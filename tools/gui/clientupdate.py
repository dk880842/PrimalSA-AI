#!/usr/bin/env python3
"""伺服器改版後「重開客戶端 → 熱更新 → 登入 → 回掛機」（AGENTS.md §7 腳本化，使用者 2026-10-16）。只用標準函式庫。

觸發：登入畫面按「登錄」後頂端閃一條黑條「登錄失敗！版本錯誤！」（約 0.5 秒，netwatch.watch_version 偵測）；
伺服器維修時會先跳「提示：伺服器已關閉！」（確定 715,557）→ 登入畫面。netwatch 命令列（--once / --watch）看到版本錯誤會自動接本腳本；
腳本迴圈裡的 netwatch.guard 只 halt（退 10）並提示跑本腳本。

用法（專案根目錄；WSL / Windows 原生指令相同；多視窗加 PSA_CLIENT=<程序名>，只動那個視窗的程序）：
  uv run --no-project python tools/gui/clientupdate.py run [--no-grind] [--restart] [--dry-run]
  run         每輪看畫面決定下一步（可重跑、從任一階段接上）：程序沒開 → 開；小視窗（1366×768）→ 更新提示 / 重啟 / 公告 / 最大化；
              2880×1659 → 提示窗（伺服器已關閉 / 網路異常）按確定、登入畫面 → netwatch.relogin（重打帳號欄 → 登錄 → 一鍵全登 → 隊伍檢查 → grind ensure）、
              選角面板 → 一鍵全登、已在遊戲 → grind ensure
  --restart   一開始先關本視窗程序再開（已知要更新時用；不加 = 只有登錄版本錯誤才關）
  --no-grind  進遊戲後不跑 grind.py ensure（交給呼叫端）
  --dry-run   只讀畫面 / 程序狀態，印下一步會做什麼，不點、不關、不開

流程（2026-10-16 p1 17:09～17:21 手動走過；p2 開起來已是新版、沒有下載提示，直接到公告）：
  1 關本視窗程序：Get-Process -Name <程序名>（精確比對，同名多個 → 不動）→ CloseMainWindow 等 15 秒 → 不行才 Stop-Process -Force
  2 Start-Process GameClient\\<程序名>.exe（WorkingDirectory GameClient）；全視窗共用更新鎖 tools/.cache/client-update.lock：
    同一時間只有一個視窗在「開程序 → 更新 → 最大化」（三個視窗共用同一份遊戲檔，同時下載會互相覆蓋）
  3 視窗一開是 1366×768（截圖 683×384，watch「版面不支援」），整窗 OCR 認提示（每次點擊前都先讀到對應文字才點）：
      Tip「download file:N size:XM」→ OK（340,252）→ 下載中只等（最多 DOWNLOAD_MAX_S）
      「更新完畢需要重啟用戶端」→ 重啟（340,257）→ 程序自己結束、不會自動重開 → 回第 2 步再開
      「最新公告」（標題在畫面上方）→ 右上 X（573,48）→ gui max（2880×1659）→ gui end 還前景
      都沒有、也不像下載中 → SMALL_IDLE_S 秒後直接 max / end
  4 2880×1659：登入畫面 → netwatch.relogin(on_version='return', clear_halt=True)：重打帳號欄（不核對）→ 刪本視窗 netwatch.halt →
    登錄（590,585）→ 版本錯誤（黑條 / 停在登入畫面 15 秒）→ 回第 1 步（最多 MAX_RESTARTS 次）；選角「一鍵全登」→ 主畫面 → 隊伍檢查 → grind ensure
鐵則 2：密碼欄不碰、帳號名不進 log（登入畫面的點擊全在 netwatch.relogin）；登錄出錯（密碼錯、封號、維護、驗證碼）= netwatch halt → 退 10。
鐵則 5：本視窗驗證停手旗標存在 → 退 9 什麼都不做；2880×1659 畫面答題介面正面命中 → 設旗標退 9。小視窗沒有面板特徵：只點 OCR 剛讀到的那個提示的按鈕。
不跑 uikit.preflight：它的版面檢查擋 1366×768、netwatch.guard 會自己處理登入畫面（版本錯誤時 halt）；改成本檔 _guard（verify-halt + 答題介面）+ netwatch 各自的檢查。

退出碼（共用 0 完成 / 1 參數 / 9 驗證停手 / 10 netwatch halt / 11 連續登錄失敗；本腳本 210～219）：
  210 程序操作失敗（查不到程序清單 / 同名多個程序 / 關不掉 / 找不到 GameClient\\<程序名>.exe / Start-Process 失敗）
  211 開程序後 WINDOW_WAIT_S 秒等不到遊戲視窗
  212 小視窗階段卡住（下載超過 DOWNLOAD_MAX_S / 按重啟後程序不結束又關不掉 / 認得的提示點了沒反應 3 次）
  213 最大化 MAX_MAX 次後版面仍不是 2880×1659
  214 2880×1659 出現不認得的提示窗（不是伺服器已關閉 / 網路異常；不點，留給人類）
  215 重開 MAX_RESTARTS 次後登錄仍版本錯誤
  216 畫面不明 / 載入超過 STUCK_S 秒沒有進展
  217 別的視窗正在更新（client-update.lock）超過 LOCK_WAIT_S 秒，或 netwatch 動作鎖一直被佔用
  218 選角面板按一鍵全登後 CHARSEL_WAIT_S 秒沒進遊戲
  219 進遊戲了，但 grind ensure 失敗（rc 見訊息）
未實機（只有離線測試，2026-10-16）：整段自動流程；黑條像素特徵（沒有黑條當下的截圖，只知道 y≈188 置中）；小視窗 OCR 關鍵字
（座標來自 p1 手動，畫面沒留截圖）；伺服器已關閉提示的 OCR。判斷都保守：認不得就等 / 停手不點。
"""
import argparse
import os
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import actlog  # noqa: E402
import clients  # noqa: E402
import errlog  # noqa: E402
import netwatch  # noqa: E402
import uikit  # noqa: E402
import verifyhalt  # noqa: E402
import winenv  # noqa: E402

SRC = 'clientupdate'
EXIT_OK, EXIT_ARGS, EXIT_VERIFY, EXIT_HALT, EXIT_FATAL = 0, 1, 9, 10, 11
(EXIT_PROC, EXIT_WINDOW, EXIT_SMALL, EXIT_MAX, EXIT_DIALOG, EXIT_VERSION,
 EXIT_STUCK, EXIT_BUSY, EXIT_CHARSEL, EXIT_GRIND) = range(210, 220)

FULL = '2880x1659'
GAME_DIR = clients.ROOT / 'GameClient'
UPDATE_LOCK = clients.SHARED_CACHE / 'client-update.lock'   # 全視窗共用：同一時間只有一個視窗在開程序 / 更新
LOCK_STALE_S = 900
LOCK_WAIT_S = 600

# 小視窗（1366×768 → 截圖 683×384）的按鈕（2026-10-16 p1 手動點過）
SMALL_OCR = (0, 0, 683, 384)
SMALL_OCR_OPTS = ('-Dark', '0', '-Zooms', '2,3')
TIP_OK = (340, 252)                  # Tip「download file:N size:XM」的 OK
RESTART_BTN = (340, 257)             # 「更新完畢需要重啟用戶端」的重啟
NOTICE_X = (573, 48)                 # 「最新公告」右上 X
NOTICE_TOP_Y = 120                   # 公告標題在畫面上方；登入畫面左下木牌也寫「最新公告」（y≈324），不能當公告窗
TIP_KEYS = ('download', 'size:')
RESTART_KEYS = ('重啟', '更新完畢', '重新啟動')
BUSY_KEYS = ('%', 'download', '下載')   # 下載中（進度字樣；猜的，未實機）

CLOSE_WAIT_MS = 15000
WINDOW_WAIT_S = 90
SELF_EXIT_S = 60                     # 按重啟後等程序自己結束
DOWNLOAD_MAX_S = 900
SMALL_IDLE_S = 8                     # 小視窗沒有認得的提示多久才直接最大化
MAX_MAX = 3
MAX_RESTARTS = 2
MAX_SAME_CLICK = 3
STUCK_S = 180
CHARSEL_WAIT_S = 90
TOTAL_S = 1800
POLL_S = 2.0

sleep = time.sleep
clock = time.time


def log(msg: str) -> None:
    print(time.strftime('%H:%M:%S'), f'{SRC}：{msg}', flush=True)
    try:
        actlog.add(SRC, msg)
    except Exception:
        pass


class Stop(Exception):
    """流程結束（rc + 理由）"""
    def __init__(self, rc: int, why: str = ''):
        super().__init__(why)
        self.rc, self.why = rc, why


# ---------------- 程序（只動本視窗 PSA_CLIENT 的程序名；精確比對）----------------
def _pwsh(cmd: str, timeout: float = 40) -> str | None:
    """跑一段 PowerShell 指令 → stdout 最後一行；失敗 / 逾時 None。測試替換"""
    try:
        r = subprocess.run(['powershell.exe', '-NoProfile', '-NonInteractive', '-Command', cmd], capture_output=True,
                           text=True, encoding='utf-8', errors='replace', timeout=timeout)
    except (OSError, subprocess.SubprocessError):
        return None
    if r.returncode != 0:
        return None
    lines = [x.strip() for x in (r.stdout or '').replace('\r', '').splitlines() if x.strip()]
    return lines[-1] if lines else ''


def _name() -> str:
    n = clients.name()
    if not clients.valid(n) or not clients.GAME_RE.match(n):
        raise Stop(EXIT_ARGS, f'PSA_CLIENT={n!r} 不是遊戲程序名稱（PrimalSA / PrimalSA2 …）')
    return n


def proc_count() -> int | None:
    """本視窗程序有幾個（Get-Process -Name 精確比對，不吃萬用字元）；查不到 None"""
    out = _pwsh(f"@(Get-Process -Name '{_name()}' -ErrorAction SilentlyContinue).Count")
    try:
        return int(out)
    except (TypeError, ValueError):
        return None


def close_proc() -> str:
    """CloseMainWindow 等 15 秒 → 還在才 Stop-Process -Force。→ 'none' / 'closed' / 'killed' / 'multi' / 'fail'"""
    n = _name()
    cmd = (f"$p = @(Get-Process -Name '{n}' -ErrorAction SilentlyContinue); "
           "if ($p.Count -eq 0) { 'none'; exit } if ($p.Count -gt 1) { 'multi'; exit }; $p = $p[0]; "
           f"[void]$p.CloseMainWindow(); if ($p.WaitForExit({CLOSE_WAIT_MS})) {{ 'closed' }} "
           "else { Stop-Process -Id $p.Id -Force; Start-Sleep -Milliseconds 1500; "
           "if (Get-Process -Id $p.Id -ErrorAction SilentlyContinue) { 'fail' } else { 'killed' } }")
    out = _pwsh(cmd, timeout=CLOSE_WAIT_MS / 1000 + 30)
    return out if out in ('none', 'closed', 'killed', 'multi', 'fail') else 'fail'


def start_proc() -> bool:
    """Start-Process GameClient\\<程序名>.exe（WorkingDirectory GameClient）。只讀 GameClient、不寫（鐵則 1）"""
    n = _name()
    exe = GAME_DIR / f'{n}.exe'
    if not exe.exists():
        raise Stop(EXIT_PROC, f'找不到 {exe}（多開執行檔由使用者自己建立）')
    w_exe, w_dir = winenv.to_windows(exe), winenv.to_windows(GAME_DIR)
    out = _pwsh(f"Start-Process -FilePath '{w_exe}' -WorkingDirectory '{w_dir}'; 'started'")
    return out == 'started'


def client_size() -> str | None:
    """本視窗客戶區 'WxH'（gui.ps1 info；每次現場問，不用 layout 的程序內快取）；視窗不在 None"""
    try:
        out = winenv.run_ps('gui.ps1', 'info', timeout=30).stdout
    except Exception:
        return None
    import re
    m = re.search(r'client=(\d+)x(\d+)', out or '')
    return f'{m[1]}x{m[2]}' if m and m[1] != '0' else None


def gui(*a, note: str = '') -> str:
    from walk import gui as _g
    return _g(*a, note=note)


# ---------------- 鎖 ----------------
def take_update_lock(wait: float = LOCK_WAIT_S) -> bool:
    if netwatch._take_wait(UPDATE_LOCK, LOCK_STALE_S, wait):
        return True
    return False


def release_update_lock() -> None:
    try:
        if UPDATE_LOCK.exists() and UPDATE_LOCK.read_text().split()[0] == str(os.getpid()):
            UPDATE_LOCK.unlink()
    except (OSError, IndexError):
        pass


# ---------------- 畫面判斷（純函式，測試用）----------------
def small_kind(lines: list) -> str | None:
    """小視窗整窗 OCR 行 → 'restart' / 'tip' / 'notice' / 'busy' / None（什麼都不像）"""
    texts = [(str(l.get('text', '')), l.get('y', 999)) for l in lines or [] if isinstance(l, dict)]
    joined = ''.join(t for t, _ in texts).replace(' ', '')
    low = joined.lower()
    if any(k in joined for k in RESTART_KEYS):
        return 'restart'
    if all(k in low for k in TIP_KEYS) or ('download' in low and 'file' in low):
        return 'tip'
    if any('公告' in t.replace(' ', '') and isinstance(y, (int, float)) and y < NOTICE_TOP_Y for t, y in texts):
        return 'notice'
    if any(k in low for k in BUSY_KEYS):
        return 'busy'
    return None


def ocr_small() -> list:
    return uikit.ocr_lines(SMALL_OCR, *SMALL_OCR_OPTS)


def _guard() -> None:
    """每輪：本視窗驗證停手旗標 → 9（什麼都不做）"""
    vh = verifyhalt.active()
    if vh:
        raise Stop(EXIT_VERIFY, verifyhalt.message(vh))


def _quiz_check() -> None:
    """2880×1659：答題介面正面命中 → 設本視窗旗標、退 9（鐵則 5）"""
    ra = uikit.screen_annot()
    if ra and 'quiz' in ra[1]:
        verifyhalt.trip('答題 / 驗證介面正面命中（clientupdate）', SRC)
        raise Stop(EXIT_VERIFY, '答題 / 驗證視窗 → 停手通知使用者（鐵則 5）')


def full_kind() -> str:
    """2880×1659 畫面 → 'dialog' / 'login' / 'charsel' / 'game' / 'other'（讀不到也算 other）"""
    if netwatch._match(netwatch.SIG_DIALOG) is True:
        return 'dialog'
    if netwatch._match(netwatch.SIG_LOGIN) is True:
        return 'login'
    if netwatch._match(netwatch.SIG_CHARSEL) is True:
        return 'charsel'
    if netwatch.hud_ok():
        return 'game'
    return 'other'


def dialog_kind() -> str:
    """2880×1659 提示窗 → 'server_closed' / 'net_lost' / 'other'"""
    if netwatch.net_glyph() is True:
        return 'net_lost'
    txt = ''.join(netwatch._ocr(netwatch.MSG_BOX, '-Light', 200, '-Zooms', '2,3'))
    if netwatch.server_closed_text(txt):
        return 'server_closed'
    if txt and any(k in txt for k in netwatch.MSG_KEYS):
        return 'net_lost'
    return 'other'


def grind_ensure() -> int | None:
    import grind
    return grind.run('ensure', ignore_watchers=True)


# ---------------- 主流程 ----------------
class Runner:
    def __init__(self, grind: bool = True, restart: bool = False, dry_run: bool = False):
        self.grind, self.restart, self.dry = grind, restart, dry_run
        self.restarts = 0          # 版本錯誤後重開的次數
        self.maxes = 0
        self.tip_at = None         # 按了下載 OK 的時間（下載中）
        self.idle_at = None        # 小視窗沒認出東西的起點
        self.nowin_at = None
        self.stuck_at = None
        self.started = False       # 本輪由本腳本開的程序
        self.last_click = ('', 0)
        self.locked = False

    # --- 動作 ---
    def _lock(self) -> None:
        if self.locked:
            try:
                UPDATE_LOCK.touch()                        # 下載可能很久：持續更新 mtime，別的視窗才不會當成死鎖接手
            except OSError:
                pass
        else:
            if not take_update_lock():
                raise Stop(EXIT_BUSY, f'別的視窗正在更新（{UPDATE_LOCK.name}）超過 {LOCK_WAIT_S} 秒')
            self.locked = True

    def _unlock(self) -> None:
        if self.locked:
            release_update_lock()
            self.locked = False

    def kill(self, why: str) -> None:
        log(f'關本視窗程序 {clients.name()}（{why}）')
        r = close_proc()
        log(f'關程序：{r}')
        if r in ('multi', 'fail'):
            raise Stop(EXIT_PROC, f'關程序失敗（{r}：同名多個 / 強制結束後仍在）')

    def launch(self) -> None:
        self._lock()
        log(f'開 GameClient\\{clients.name()}.exe')
        if not start_proc():
            raise Stop(EXIT_PROC, 'Start-Process 失敗')
        self.started, self.nowin_at, self.idle_at, self.tip_at = True, clock(), None, None
        sleep(5)

    def click_small(self, kind: str, xy: tuple, note: str) -> None:
        k, n = self.last_click
        n = n + 1 if k == kind else 1
        self.last_click = (kind, n)
        if n > MAX_SAME_CLICK:
            raise Stop(EXIT_SMALL, f'小視窗「{kind}」點了 {MAX_SAME_CLICK} 次仍在')
        gui('click', str(xy[0]), str(xy[1]), note=note)

    def maximize(self) -> None:
        self.maxes += 1
        if self.maxes > MAX_MAX:
            raise Stop(EXIT_MAX, f'最大化 {MAX_MAX} 次後版面仍不是 {FULL}')
        log('最大化遊戲視窗（gui max → end 還前景）')
        gui('max')
        sleep(1.5)
        gui('end')
        sleep(2)

    # --- 每一輪 ---
    def step(self) -> int | None:
        """做一步；回退出碼 = 結束，None = 繼續"""
        _guard()
        n = proc_count()
        if n is None:
            raise Stop(EXIT_PROC, '查不到程序清單（PowerShell 失敗）')
        if n > 1:
            raise Stop(EXIT_PROC, f'同名程序 {clients.name()} 有 {n} 個，不猜是哪一個')
        if self.restart and n:
            if self.dry:
                return self._plan('--restart：關本視窗程序再開')
            self.restart = False
            self.kill('--restart')
            return None
        self.restart = False
        if n == 0:
            if self.dry:
                return self._plan('程序沒開 → Start-Process 開本視窗')
            self.launch()
            return None
        size = client_size()
        if size is None:
            if self.dry:
                return self._plan('程序在、還沒有遊戲視窗 → 等')
            self.nowin_at = self.nowin_at or clock()
            if clock() - self.nowin_at > WINDOW_WAIT_S:
                raise Stop(EXIT_WINDOW, f'開程序後 {WINDOW_WAIT_S} 秒等不到遊戲視窗')
            sleep(POLL_S)
            return None
        self.nowin_at = None
        if size != FULL:
            return self.small(size)
        self._unlock()
        return self.full()

    def _plan(self, what: str) -> int:
        log(f'[dry-run] 下一步：{what}（不動）')
        return EXIT_OK

    def small(self, size: str) -> int | None:
        if not self.dry:
            self._lock()                                   # 下載 / 重啟 / 最大化期間佔著共用更新鎖（不同視窗不要同時下載同一份檔）
        lines = ocr_small()
        kind = small_kind(lines)
        if self.dry:
            return self._plan(f'小視窗 {size}，畫面像「{kind or "沒認出"}」→ '
                              + {'restart': '按重啟', 'tip': '按下載 OK', 'notice': '關公告 → 最大化', 'busy': '等下載'}.get(kind, '等一下再最大化'))
        if kind == 'restart':
            log('「更新完畢需要重啟用戶端」→ 按重啟（程序會自己結束、不會自動重開）')
            self.click_small('restart', RESTART_BTN, 'clientupdate 更新完畢 → 重啟')
            self.tip_at = None
            end = clock() + SELF_EXIT_S
            while clock() < end:
                sleep(POLL_S)
                if proc_count() == 0:
                    log('程序已自己結束 → 重開')
                    return None
            self.kill(f'按重啟後 {SELF_EXIT_S} 秒沒結束')
            return None
        if kind == 'tip':
            log('Tip「download file … size …」→ 按 OK 開始下載更新')
            self.click_small('tip', TIP_OK, 'clientupdate 更新提示 → OK')
            self.tip_at = clock()
            sleep(3)
            return None
        if kind == 'notice':
            log('「最新公告」→ 按右上 X')
            self.click_small('notice', NOTICE_X, 'clientupdate 關最新公告')
            sleep(1.5)
            self.maximize()
            return None
        if self.tip_at is not None or kind == 'busy':
            self.tip_at = self.tip_at or clock()           # 下載中：只等「重啟」，不最大化（最大化後提示窗座標就不對了）
            if clock() - self.tip_at > DOWNLOAD_MAX_S:
                raise Stop(EXIT_SMALL, f'下載 / 更新超過 {DOWNLOAD_MAX_S} 秒沒出現「重啟」')
            sleep(3)
            return None
        self.idle_at = self.idle_at or clock()
        if clock() - self.idle_at >= SMALL_IDLE_S:
            self.idle_at = None
            self.maximize()
        else:
            sleep(POLL_S)
        return None

    def full(self) -> int | None:
        _quiz_check()
        kind = full_kind()
        if self.dry:
            return self._plan(f'{FULL}，畫面「{kind}」→ ' + {
                'dialog': '提示窗：伺服器已關閉 / 網路異常才按確定', 'login': 'netwatch.relogin（重打帳號欄 → 登錄；版本錯誤就重開）',
                'charsel': '一鍵全登', 'game': '已在遊戲 → ' + ('grind ensure' if self.grind else '結束（--no-grind）'),
                'other': '等（載入 / 不明）'}[kind])
        if kind != 'other':
            self.stuck_at = None
        if kind == 'dialog':
            d = dialog_kind()
            if d == 'other':
                raise Stop(EXIT_DIALOG, '提示窗不是「伺服器已關閉 / 網路異常」，不點（留給人類看）')
            log(f'提示窗（{"伺服器已關閉" if d == "server_closed" else "網路異常"}）→ 按確定')
            gui('click', str(netwatch.CONFIRM[0]), str(netwatch.CONFIRM[1]), note=f'clientupdate 提示窗（{d}）→ 確定')
            sleep(3)
            return None
        if kind == 'login':
            return self.login()
        if kind == 'charsel':
            return self.charsel()
        if kind == 'game':
            return self.in_game()
        self.stuck_at = self.stuck_at or clock()
        if clock() - self.stuck_at > STUCK_S:
            raise Stop(EXIT_STUCK, f'{STUCK_S} 秒畫面不明 / 載入沒有進展')
        sleep(POLL_S)
        return None

    def login(self) -> int | None:
        log('登入畫面 → netwatch.relogin（重打帳號欄 → 登錄 → 一鍵全登 → 隊伍檢查' + (' → grind ensure）' if self.grind else '）'))
        r = netwatch.relogin(SRC, grind_ensure=self.grind, on_version='return', clear_halt=True)
        st = r.get('status')
        if st == 'version':
            if self.restarts >= MAX_RESTARTS:
                raise Stop(EXIT_VERSION, f'重開 {MAX_RESTARTS} 次後登錄仍版本錯誤')
            self.restarts += 1
            errlog.add(f'登錄版本錯誤（{"黑條" if r.get("flash") else "停在登入畫面"}）→ clientupdate 重開客戶端（第 {self.restarts} 次）', source=SRC)
            self.kill('登錄版本錯誤')
            return None
        if st == 'reconnected':
            g = ((r.get('recover') or {}).get('grind') or {})
            if self.grind and g.get('rc') != 0:
                raise Stop(EXIT_GRIND, f'進遊戲了，但 grind ensure 失敗（{g}）')
            log('登入完成' + ('、grind ensure 完成' if self.grind else ''))
            return EXIT_OK
        if st == 'halt':
            raise Stop(EXIT_HALT, f'netwatch halt：{r.get("reason", "")}')
        if st == 'fatal':
            raise Stop(EXIT_FATAL, r.get('reason', '連續登錄失敗'))
        if r.get('busy'):
            self.stuck_at = self.stuck_at or clock()
            if clock() - self.stuck_at > STUCK_S:
                raise Stop(EXIT_BUSY, 'netwatch 動作鎖一直被佔用')
        sleep(POLL_S)
        return None

    def charsel(self) -> int | None:
        log('選角面板 → 一鍵全登')
        gui('click', str(netwatch.ALL_LOGIN_BTN[0]), str(netwatch.ALL_LOGIN_BTN[1]), note='clientupdate 一鍵全登')
        end = clock() + CHARSEL_WAIT_S
        while clock() < end:
            sleep(POLL_S)
            if netwatch.hud_ok():
                netwatch._release(netwatch.HALT)
                netwatch._forget_char()
                info = netwatch.recover(SRC, grind_ensure=self.grind)
                g = info.get('grind') or {}
                if self.grind and g.get('rc') != 0:
                    raise Stop(EXIT_GRIND, f'進遊戲了，但 grind ensure 失敗（{g}）')
                return EXIT_OK
        raise Stop(EXIT_CHARSEL, f'一鍵全登後 {CHARSEL_WAIT_S} 秒沒進遊戲')

    def in_game(self) -> int:
        if netwatch.HALT.exists():
            netwatch._release(netwatch.HALT)          # 已在遊戲裡 = 已登入（同 check_and_reconnect 的「人類登入回來」）
        if not self.grind:
            log('已在遊戲裡（--no-grind，結束）')
            return EXIT_OK
        log('已在遊戲裡 → grind.py ensure')
        rc = grind_ensure()
        if rc != 0:
            raise Stop(EXIT_GRIND, f'grind ensure 退出碼 {rc}')
        return EXIT_OK


def run(grind: bool = True, restart: bool = False, dry_run: bool = False, total_s: float = TOTAL_S) -> int:
    if not dry_run:
        winenv.enable_server()                 # 版本黑條要 0.1 秒一次的像素連讀
    r = Runner(grind=grind, restart=restart, dry_run=dry_run)
    end = clock() + total_s
    try:
        while clock() < end:
            rc = r.step()
            if rc is not None:
                log(f'結束（退出碼 {rc}）')
                return rc
        raise Stop(EXIT_STUCK, f'整段超過 {int(total_s)} 秒')
    except Stop as e:
        log(f'停手（退出碼 {e.rc}）：{e.why}')
        if e.rc not in (EXIT_OK, EXIT_ARGS) and not dry_run:
            errlog.add(f'clientupdate 停手（{e.rc}）：{e.why}', source=SRC)
        return e.rc
    finally:
        r._unlock()


def main(argv=None) -> int:
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    ap = argparse.ArgumentParser(description='伺服器改版後重開客戶端 → 熱更新 → 登入 → 回掛機')
    ap.add_argument('cmd', choices=['run'])
    ap.add_argument('--no-grind', action='store_true')
    ap.add_argument('--restart', action='store_true', help='先關本視窗程序再開')
    ap.add_argument('--dry-run', action='store_true')
    a = ap.parse_args(argv)
    return run(grind=not a.no_grind, restart=a.restart, dry_run=a.dry_run)


if __name__ == '__main__':
    sys.exit(main())
