#!/usr/bin/env python3
"""腳本化流程（team / grind / char / pet）共用零件（只用標準函式庫）。計畫：notes/plan-scriptify.md §1.2。

安全原則（鐵則 2~5、SKILL.md）：
- 面板內點擊一律經 safe_click：面板特徵不在 → 不點（回 False，避免背景點擊穿透到地面走路）；點到 FORBIDDEN 矩形 → 丟 ForbiddenClick。
- preflight：版面、netwatch、戰鬥鎖、畫面連 3 次不認得（疑似驗證視窗）→ 退出 9 停手通知使用者。
- 名字比對「對不上就拒絕」：人物名走 charstate.norm_char（= charname 的正規化，與 watch 同一套）；寵物名 snap_pet 對 Monster 表。
所有會碰遊戲的函式都走模組層級的 gui / sleep / clock（測試可替換）；匯入本模組不會碰遊戲。
"""
import difflib
import json
import re
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import charstate  # noqa: E402
import screen_sigs  # noqa: E402
import winenv  # noqa: E402

ROOT = HERE.parents[1]
CACHE = ROOT / 'tools' / '.cache'
SHOT_DIR = CACHE / 'ui-log'
SHOT_KEEP_DAYS = 3
MONSTER_TABLE = ROOT / 'knowledge' / 'data' / 'tables' / 'Monster.jsonl'

# ---- 退出碼（共用；各工具自己的段：team 40～47、grind 50～59、char 60～65、pet 70～79）----
EXIT_OK, EXIT_USAGE, EXIT_LAYOUT = 0, 1, 2
EXIT_IN_BATTLE = 8               # 戰鬥中或 quest 鎖檔（同 ass.EXIT_IN_BATTLE 語意）
EXIT_UNKNOWN_SCREEN = 9          # 疑似驗證 / 不認得的畫面：停手通知使用者
EXIT_HALT = 10                   # netwatch halt（netwatch.guard 自己 sys.exit）
LAYOUT = '2880x1659'

UNKNOWN_N = 3                    # 連幾次 unknown 才算
UNKNOWN_GAP_S = 5.0              # 兩次讀之間至少間隔（避開轉場一瞬間）

sleep = time.sleep               # 測試時可替換
clock = time.time


# ---- 分段計時（--timing 用；關著時 mark 幾乎零成本）----
_stages: list | None = None
_stage_t = 0.0


def timing_start() -> None:
    global _stages, _stage_t
    _stages, _stage_t = [], clock()


def mark(label: str) -> None:
    """記下「距上一個 mark（或 timing_start）」的毫秒；沒開計時就什麼都不做"""
    global _stage_t
    if _stages is not None:
        now = clock()
        _stages.append([label, int((now - _stage_t) * 1000)])
        _stage_t = now


def timing_get() -> list:
    return list(_stages or [])


class ForbiddenClick(AssertionError):
    """要點的座標落在該面板的紅區 / 禁區矩形內（程式 bug，不是執行期狀況）"""


# ---- 遊戲存取（薄包裝，測試替換 uikit.gui）----
def gui(*args: str, note: str = '') -> str:
    import walk
    return walk.gui(*args, note=note)


def px(points) -> list | None:
    """一次讀多點 → [(r,g,b), ...]；失敗 / 數量不符回 None（同 ass._px）"""
    pts = list(points)
    out = gui('pixel', ' '.join(f'{x},{y}' for x, y in pts)).split()
    try:
        cols = [tuple(int(v) for v in c.split(',')) for c in out]
    except ValueError:
        return None
    return cols if len(cols) == len(pts) and all(len(c) == 3 for c in cols) else None


def sig_match(sig) -> bool:
    """screen_sigs 格式的特徵（6 元素 tuple 清單）現場讀圖比對；讀不到 = False"""
    cols = px([(x, y) for x, y, *_ in sig])
    return bool(cols) and all(screen_sigs.close(c, (r, g, b), tol) for c, (_, _, r, g, b, tol) in zip(cols, sig))


def screen(full: bool = False) -> dict:
    """一次讀 screen_sigs.points() → classify（同 quest.read_screen；不 import quest）。讀不到 → {'state': 'error'}。
    full=True 多讀 panel_points()（寵物 / 背包 / 外掛等面板與主畫面多組特徵，watch 用的同一套）：認得的面板回 state=panel + panel 名。
    預設 False（腳本沿用舊判斷：只認切換角色面板）；follow 判斷「使用者開的面板」才用 full=True"""
    pts = screen_sigs.points() + (screen_sigs.panel_points() if full else [])
    cols = px(pts)
    if cols is None:
        return {'state': 'error'}
    return screen_sigs.classify(dict(zip(pts, cols)))


def hud_visible() -> bool:
    return sig_match(screen_sigs.SIG_HUD)


# ---- preflight ----
WATCH_MAX_AGE_S = 2.0            # watch 畫面區段夠新才採用（watch 心跳 1 s，畫面取樣 0.5 s，≤1.5 s 才算正常；1.0 會常常落空）
WATCH_OK_STATES = ('idle', 'panel', 'walking')
NETWATCH_HALT = CACHE / 'netwatch.halt'


def watch_screen(max_age: float = WATCH_MAX_AGE_S):
    """同平台 watch 的畫面區段（夠新才回；watch 不在 / 太舊 / 跨平台 → None）。測試可替換"""
    import watchstate
    return watchstate.screen(max_age=max_age)


def watch_state(max_age: float = WATCH_MAX_AGE_S):
    """同平台 watch 的完整 state（夠新、watcher 在跑才回；不等待）。測試可替換"""
    import watchstate
    return watchstate.fresh(max_age, wait=0)


def watch_preflight_ok() -> bool:
    """快路徑：watch 狀態夠新（≤1 s）、畫面是 idle / panel / walking（不是 unknown / 戰鬥 / 對話框）、
    沒有 verify_suspect / alerts、沒有 annot（登入 / 提示視窗）、版面 2880x1659 且遊戲在跑、netwatch 沒 halt 檔 → True，否則 False（走完整檢查）。
    只讀 state 檔不碰遊戲；watch 認得的畫面有限，所以只是省掉重複讀圖，不改變停手規則"""
    try:
        if NETWATCH_HALT.exists():
            return False
        st, sc = watch_state(), watch_screen()
    except Exception:
        return False
    if not st or not sc or sc.get('state') not in WATCH_OK_STATES or sc.get('annot'):
        return False
    if sc.get('state') == 'panel' and sc.get('panel') not in (None, 'switch'):
        return False                              # watch 認得的其他面板（寵物 / 背包…）：腳本維持舊行為，走完整檢查（它只認切換面板）
    fl = st.get('flags') or {}
    if fl.get('verify_suspect') or fl.get('netwatch_halt') or st.get('alerts'):
        return False
    g = st.get('game') or {}
    # watch 算好的守衛結果（layout.evaluate）；舊 state 沒有 screen_supported 就退回「實體版面 == 2880x1659」
    if not g.get('screen_supported', g.get('layout') == LAYOUT) or not g.get('running'):
        return False
    import layout
    layout.prime(g['layout'], g.get('logical'))                     # 後面 import walk（uikit.gui 第一次呼叫）時不必再問一次版面
    return True


def preflight(src: str, fast: bool = True) -> int:
    """開跑前檢查，回退出碼（0 = 可以動）：版面不是 2880x1659 → 2；netwatch halt → 直接 sys.exit(10)；
    battle.lock（quest 跑著）→ 8；畫面連 3 次（間隔 ≥5 s）unknown / 讀不到 → 9（疑似驗證視窗，停手通知使用者）。
    fast=True 且 watch 狀態夠新時（watch_preflight_ok）省掉 layout / netwatch / 畫面連讀（約 0.36 s → 約 0.02 s）；battle.lock 一律檢查"""
    import battleguard
    fast_ok = fast and watch_preflight_ok()
    if not fast_ok:
        import layout
        ok, why = layout.supported()
        if not ok:
            print(f'{src}：版面不支援：{why}', file=sys.stderr)
            return EXIT_LAYOUT
        import netwatch
        netwatch.guard(src)
    lk = battleguard.locked()
    if lk:
        print(f'{src}：battle.lock 有效（{lk.get("note", "")} pid {lk.get("pid")}），別的腳本在用畫面，不搶', file=sys.stderr)
        return EXIT_IN_BATTLE
    if fast_ok:
        mark('preflight(watch)')
        return EXIT_OK
    for i in range(UNKNOWN_N):
        if screen().get('state') not in ('unknown', 'error'):
            mark('preflight')
            return EXIT_OK
        if i < UNKNOWN_N - 1:
            sleep(UNKNOWN_GAP_S)
    print(f'{src}：畫面連 {UNKNOWN_N} 次不認得（疑似驗證視窗），停手通知使用者（鐵則 5）', file=sys.stderr)
    return EXIT_UNKNOWN_SCREEN


# ---- 面板 ----
def rect(cx: int, cy: int, r: int = 30) -> tuple:
    """以 (cx, cy) 為中心、半徑 r 的矩形 (x, y, w, h)"""
    return (cx - r, cy - r, 2 * r, 2 * r)


@dataclass
class Panel:
    name: str
    open_xy: tuple | None            # 主畫面開啟鈕（只在 SIG_HUD 在時點）
    sig: list | None                 # 面板開著的特徵（screen_sigs 格式）；None = 還沒量過 → 不能開 / 判定
    close_xy: tuple | None = None
    esc_close: bool = True           # 點 ✕ 後仍開 → 再按 ESC
    forbidden: dict = field(default_factory=dict)    # 名稱 → (x, y, w, h)；safe_click 不准點（allow= 明確放行的除外）
    settle_ms: int = 700             # 點開啟鈕後等多久再看
    is_open_fn: object = None        # 覆寫（例：ASS 沿用 ass.panel_open）
    open_fn: object = None
    close_fn: object = None


SWITCH = Panel('SWITCH', (763, 760), screen_sigs.SIG_PANEL, (1064, 208),
               forbidden={'login_all': rect(716, 578, 40)})                  # 全部登錄會讓角色上線（要問；--login-all 才 allow）
PET = Panel('PET', (318, 80), [screen_sigs.X_PET], (1310, 108),     # ✕ 特徵與 watch 的面板辨識共用（screen_sigs.X_PET）
            forbidden={'trash': rect(708, 565), 'recycle': rect(372, 610), 'loyal_minus': rect(1140, 234), 'loyal_plus': rect(1265, 234),
                       'lock': rect(708, 630), 'depot_expand': rect(1195, 705),
                       'depot_prev': rect(805, 703, 35), 'depot_next': rect(1055, 703, 35),     # 倉庫頁箭頭（P-I6 量到 私人倉庫1/1 兩側；用途未知，先禁）
                       })     # 取出狀態右下的白色方塊（668～733 × 670～720，舊 skill 的「取出 675,703」其實是它）與「休息」鈕 672,702 重疊，無法列禁區；只靠 pet.py 不點倉庫分頁的該位置
# 組隊面板（850,760）：P-I4 實測（2026-10-11，5 人隊）。✕ 在 1250,77（與切換面板 1064,208 不同）；
# 特徵 = ✕ 紅圓 + 標題條兩點 + 米底 + 「解散隊伍」鈕紅橘（有隊伍才有；無隊伍時是藍色「創建隊伍」，所以單人時特徵會不符 → 沒做過單人量測，只在有隊伍時可靠）。
# 解散鈕 720,670 列入禁區：解散一律走 quest.disband_team（左側分頁，逐步像素驗證），不從這個面板點。
TEAMPANEL = Panel('TEAMPANEL', (850, 760),
                  [screen_sigs.X_TEAM, (720, 75, 147, 89, 57, screen_sigs.TOL), (600, 60, 149, 92, 60, screen_sigs.TOL),
                   (1300, 400, 255, 229, 191, screen_sigs.TOL), (720, 670, 187, 73, 43, screen_sigs.TOL)],
                  (1250, 77), forbidden={'disband': rect(720, 670, 60)})
# 快速組隊「提示」視窗（P-I2 實測 2026-10-11）：疊在切換面板上方（切換面板的 SIG_PANEL 此時被暗化而不成立）。
# 特徵 = ✕ 紅圓 (1052,167) + 下方藍色「組隊」鈕兩點 + 左側「隊長」標籤米色；ESC 只關提示（切換面板仍在，再 ESC 才關它）。
# 沒有自己的開啟鈕（在切換面板內點 520,578 開）；close_panel 會點 ✕ 1052,167 並等它消失。
QTEAM = Panel('QTEAM', None,
              [screen_sigs.X_QTEAM, (720, 665, 66, 113, 171, screen_sigs.TOL), (448, 325, 251, 223, 187, screen_sigs.TOL)],
              (1052, 167))
ASS = Panel('ASS', None, None, None)                                          # 見 _ass_panel()


def _ass_panel() -> Panel:
    import ass
    return Panel('ASS', None, None, None, is_open_fn=ass.panel_open, open_fn=ass.open_panel, close_fn=ass.close_panel)


def is_open(p: Panel) -> bool:
    """面板現在是不是真的開著（現場讀特徵；讀不到 / 沒特徵 = False）"""
    if p.is_open_fn:
        return bool(p.is_open_fn())
    return bool(p.sig) and sig_match(p.sig)


POLL_S = 0.1                     # 等面板 / 畫面的輪詢間隔（舊 0.5 s）
RECLICK_S = 2.5                  # open_panel_ex：點開啟鈕後至少隔這麼久（期間只輪詢確認）才准再點第 2 下，避免短時間連點（2026-10-11 任務詳情 1 秒內點 2 次）
WAIT_OPEN_MS = 1500


def _uniform_tol(sig) -> int | None:
    tols = {t for *_, t in sig}
    return tols.pop() if len(tols) == 1 else None


def _seq_ok(out: str) -> bool:
    """gui seq 輸出裡有 waitpix 成功行（ok <ms>）"""
    return any(ln.startswith('ok') for ln in (out or '').splitlines())


def _probe(p: Panel) -> tuple:
    """一次 pixel 讀 → (面板開著, HUD 在)；讀不到 = (False, False)"""
    pts = [(x, y) for x, y, *_ in p.sig] + [(x, y) for x, y, *_ in screen_sigs.SIG_HUD]
    cols = px(pts)
    if not cols:
        return False, False
    n = len(p.sig)
    return (all(screen_sigs.close(c, (r, g, b), t) for c, (_, _, r, g, b, t) in zip(cols[:n], p.sig)),
            all(screen_sigs.close(c, (r, g, b), t) for c, (_, _, r, g, b, t) in zip(cols[n:], screen_sigs.SIG_HUD)))


LAST_OPEN: dict = {}             # 最近一次 open_panel_ex 的過程：clicked（點開啟鈕次數）/ hud_seen / hud_waited（等 HUD 回來的秒數）；失敗訊息分辨原因用


def open_panel_ex(p: Panel, timeout: float = 4.0, hud_wait: float = 0.0) -> tuple:
    """開面板並驗證 → (成功, 一開始就開著)。**只在主畫面（SIG_HUD）看得到時才點開啟鈕**；面板特徵沒出現就回 False，絕不點面板內座標。
    點開啟鈕用 seq「click; waitpix 面板特徵」代替固定等待（面板約 0.1～0.3 s 就出現；舊的固定 wait 700 + 輪詢 0.5 s）
    hud_wait > 0：一直沒看到 HUD 也沒點過（戰鬥 / 轉場 / 對話蓋住）時，最多再等這麼久讓 HUD 回來（不點任何東西），
    HUD 一出現才開始算 timeout；errlog #32：掛機中剛好在戰鬥，4 s 逾時就誤報打不開。"""
    LAST_OPEN.clear()
    LAST_OPEN.update(clicked=0, hud_seen=False, hud_waited=0.0)
    if p.open_fn:
        return bool(p.open_fn()), False
    if p.sig is None or p.open_xy is None:
        return False, False
    t_start = clock()
    end = t_start + timeout
    hud_deadline = t_start + hud_wait
    clicked = 0
    last_click_t = 0.0
    was_open = None
    tol = _uniform_tol(p.sig)
    while True:
        opened, hud = _probe(p)
        if hud and not LAST_OPEN['hud_seen']:
            LAST_OPEN['hud_seen'] = True
            if clicked == 0 and hud_wait > 0:
                end = max(end, clock() + timeout)        # HUD 剛回來：從現在起算開面板的 timeout
        if was_open is None:
            was_open = opened
        if opened:
            return True, was_open
        if hud and clicked < 3 and (clicked == 0 or clock() - last_click_t >= RECLICK_S):
            if tol is not None:
                out = gui('seq', f'click {p.open_xy[0]} {p.open_xy[1]}; waitpix {WAIT_OPEN_MS} {screen_sigs.sig_str(p.sig)} {tol}', note=f'uikit 開 {p.name} 面板')
                clicked += 1
                last_click_t = clock()
                LAST_OPEN['clicked'] = clicked
                if _seq_ok(out) or is_open(p):
                    return True, was_open
            else:
                gui('seq', f'click {p.open_xy[0]} {p.open_xy[1]}; wait {p.settle_ms}', note=f'uikit 開 {p.name} 面板')
                clicked += 1
                last_click_t = clock()
                LAST_OPEN['clicked'] = clicked
                if is_open(p):
                    return True, was_open
        if clicked == 0 and not hud and clock() < hud_deadline:
            LAST_OPEN['hud_waited'] = round(clock() - t_start, 1)
            sleep(POLL_S)                                # 還沒看到 HUD、沒點過：繼續等（不點）
            continue
        if clock() >= end:
            if clicked:                                  # 點過但特徵沒出現：最後再等一下看是不是晚開（不再點）
                sleep(0.5)
                if is_open(p):
                    return True, was_open
            return False, was_open
        sleep(POLL_S)


def open_panel(p: Panel, timeout: float = 4.0) -> bool:
    """開面板並驗證；已開著就成功（見 open_panel_ex）"""
    ok = open_panel_ex(p, timeout)[0]
    mark(f'open {p.name}')
    return ok


def _gone_sig(p: Panel):
    """關閉後用來確認面板消失的單點特徵（✕ 那一點）；找不到回 None（退回固定等待）"""
    if p.sig and p.close_xy:
        for x, y, r, g, b, t in p.sig:
            if (x, y) == tuple(p.close_xy):
                return f'{x},{y},{r},{g},{b}!', t
    return None


CLOSE_WAIT_MS = 2500             # 點 ✕ 後等面板消失的上限（快速戰鬥掛機中面板可能 1 秒以上才關；正常 0.1 s 內消失就立即返回）


def _wait_closed(p: Panel, wait_s: float = CLOSE_WAIT_MS / 1000) -> bool:
    """每 POLL_S 讀一次特徵，最多 wait_s 秒，面板消失就立即回 True"""
    end = clock() + wait_s
    while True:
        if not is_open(p):
            return True
        if clock() >= end:
            return False
        sleep(POLL_S)


def close_panel(p: Panel, known_open: bool = False) -> bool:
    """關面板並驗證消失：先點 ✕（waitpix 輪詢 ✕ 消失，最多 CLOSE_WAIT_MS，消失即返回）、逾時才確認仍開著再點第二次、
    仍開再 ESC（各最多 2 次）；只在面板確實開著時才送（第二次點 ✕ 前一定重讀特徵，避免面板已關時點到地面 / 其他鈕）。
    known_open=True 表示呼叫端剛驗證過面板開著，省掉第一次 is_open"""
    if p.close_fn:
        return bool(p.close_fn())
    gone = _gone_sig(p)
    for i in range(2):
        if not (known_open and i == 0) and not is_open(p):
            return True
        if p.close_xy:
            if gone:
                out = gui('seq', f'click {p.close_xy[0]} {p.close_xy[1]}; waitpix {CLOSE_WAIT_MS} {gone[0]} {gone[1]}', note=f'uikit 關 {p.name} 面板')
                if _seq_ok(out):
                    return True
                if _wait_closed(p, 0.3):         # waitpix 逾時後最後再看一眼（晚一點點才關）
                    return True
            else:
                gui('seq', f'click {p.close_xy[0]} {p.close_xy[1]}', note=f'uikit 關 {p.name} 面板')
                if _wait_closed(p):
                    return True
        if p.esc_close:
            gui('seq', 'key {ESC}; wait 500', note=f'uikit ESC 關 {p.name} 面板')
    return not is_open(p)


def in_rect(x: int, y: int, r: tuple) -> bool:
    return r[0] <= x < r[0] + r[2] and r[1] <= y < r[1] + r[3]


def check_forbidden(p: Panel, x: int, y: int, allow=()) -> None:
    for nm, r in p.forbidden.items():
        if nm not in allow and in_rect(x, y, r):
            raise ForbiddenClick(f'{p.name} 面板 ({x},{y}) 落在禁區 {nm} {r}')


def safe_click(x: int, y: int, panel: Panel, note: str = '', allow=(), wait_ms: int = 300) -> bool:
    """面板內點擊的唯一入口：禁區 → ForbiddenClick（先檢查，不讀圖）；面板特徵不在 → 不點、回 False；點了回 True"""
    check_forbidden(panel, x, y, allow)
    if not is_open(panel):
        return False
    gui('seq', f'click {x} {y}; wait {wait_ms}', note=note or f'uikit {panel.name} 點 ({x},{y})')
    return True


# ---- OCR ----
def ocr(box, *opts) -> list:
    """ocr.ps1 → 文字行清單；逾時 / 失敗回 []（同 petwatch.ocr）"""
    import subprocess
    try:
        r = winenv.run_ps('ocr.ps1', *map(str, box), *map(str, opts))
    except subprocess.TimeoutExpired:
        return []
    try:
        d = json.loads((r.stdout.strip().splitlines() or [''])[-1])
    except json.JSONDecodeError:
        return []
    return [ln['text'] for ln in d.get('lines', [])] if d.get('ok') else []


# ---- 人物名（與 watch 同一套：charstate.norm_char → charname）----
CHARS = charstate.DEFAULT_CHARS
chars = charstate.chars
norm_char = charstate.norm_char


# ---- 寵物名 ----
MOUNTS = ['瑪斯貝卡', '布拉奇多斯']   # 騎寵名單（2026-10-11 加布拉奇多斯；存倉例外見 pet.py --allow-mount-store）
SNAP_CUTOFF = 0.8
_names_cache: dict = {}


def _pet_key(t: str) -> str:
    """比對用正規化：去空白 / 標點 / 括號內容"""
    t = re.sub(r'[\(（\[【].*$', '', str(t or ''))
    return re.sub(r'[\s·．.。,，:：\-_/\\|]+', '', t)


def pet_names(path=None) -> dict:
    """Monster 表所有名稱（繁中 nameTn、簡中 nameCn、韓文 nameKr）→ 正式名（nameTn，缺就 nameCn）。同名不同寵不分（只要名字）"""
    p = Path(path) if path else MONSTER_TABLE
    if p in _names_cache:
        return _names_cache[p]
    out: dict = {}
    try:
        for ln in p.read_text(encoding='utf-8').splitlines():
            if not ln.strip():
                continue
            d = json.loads(ln)
            canon = d.get('nameTn') or d.get('nameCn')
            if not canon:
                continue
            for k in ('nameTn', 'nameCn', 'nameKr'):
                v = _pet_key(d.get(k))
                if v:
                    out.setdefault(v, canon)
    except (OSError, ValueError):
        out = {}
    _names_cache[p] = out
    return out


def snap_pet(text, names=None, cutoff: float = SNAP_CUTOFF):
    """OCR 文字 → Monster 表正式名。完全相同優先；否則 difflib 相似度 ≥ cutoff 且「最佳唯一」（第二名正式名分數必須更低）才採用；
    其他（太像多個 / 差太多 / 空字串）→ None（對不上就拒絕，不猜）"""
    key = _pet_key(text)
    if not key:
        return None
    table = names if names is not None else pet_names()
    if key in table:
        return table[key]
    if len(key) < 3:                  # 太短的片段（例「金布」）相似度不可靠，除非完全相同
        return None
    best: dict = {}
    for k, canon in table.items():
        sm = difflib.SequenceMatcher(None, key, k)
        if sm.real_quick_ratio() < cutoff or sm.quick_ratio() < cutoff:
            continue
        r = sm.ratio()
        if r >= cutoff and r > best.get(canon, 0):
            best[canon] = r
    if not best:
        return None
    ranked = sorted(best.items(), key=lambda kv: -kv[1])
    if len(ranked) > 1 and ranked[1][1] >= ranked[0][1]:
        return None
    return ranked[0][0]


def is_mount_like(text, mounts=None, cutoff: float = 0.6) -> bool:
    """fail-safe 版：OCR 文字只要「像」任何騎寵名（精確或相似度 ≥ cutoff，鬆很多）就視為騎寵 → 呼叫端一律拒絕存倉等動作。
    例：「瑪斯貝卞」（OCR 錯字，snap_pet 會拒絕）也算"""
    key = _pet_key(text)
    if not key:
        return False
    return any(difflib.SequenceMatcher(None, key, _pet_key(m)).ratio() >= cutoff for m in (mounts or MOUNTS))


# ---- 截圖 / 錯誤 ----
def cleanup_old_shots(days: int = SHOT_KEEP_DAYS, folder: Path = None, now: float | None = None) -> int:
    """刪 folder（預設 ui-log）第一層超過 days 天的 png；錯誤都吞掉"""
    folder = SHOT_DIR if folder is None else folder
    now = time.time() if now is None else now
    n = 0
    try:
        for f in folder.iterdir():
            try:
                if f.is_file() and f.suffix.lower() == '.png' and now - f.stat().st_mtime > days * 86400:
                    f.unlink()
                    n += 1
            except OSError:
                pass
    except OSError:
        pass
    return n


def snap(tag: str) -> str | None:
    """失敗現場存圖到 tools/.cache/ui-log/HHMMSS-tag.png（先清 3 天前的）；回相對專案根的路徑，失敗回 None"""
    try:
        SHOT_DIR.mkdir(parents=True, exist_ok=True)
        cleanup_old_shots()
        p = SHOT_DIR / f'{time.strftime("%H%M%S")}-{re.sub(r"[^0-9A-Za-z_-]", "_", tag)}.png'
        gui('shot', winenv.to_windows(p))
        return str(p.relative_to(ROOT))
    except Exception:
        return None


def fail(src: str, rc: int, msg: str) -> int:
    """印訊息 + errlog + 回 rc（errlog 寫失敗不影響）"""
    print(f'{src}：{msg}', file=sys.stderr)
    try:
        import errlog
        errlog.add(msg, source=src)
    except Exception:
        pass
    return rc
