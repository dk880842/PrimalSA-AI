#!/usr/bin/env python3
"""切換「當前角色」（P3）。計畫：notes/plan-scriptify.md §4。只用標準函式庫。

用法（專案根目錄；WSL / Windows 原生指令相同；角色名 DKB0 / DKBO 兩種寫法都收，輸出用真名 DKBO）：
  uv run --no-project python tools/gui/char.py current [--json]    # 唯讀：開切換面板讀「當前」是誰（讀得到名字就更新 current-char.json）
  uv run --no-project python tools/gui/char.py switch DKBO2        # 切過去並確認；已經是就不點
  uv run --no-project python tools/gui/char.py ensure DKBO         # 同 switch（語意：是就不動、不是才切；grind / pet-quest 收尾用）
  最後一行一律印 JSON：{"ok", "rc", "current", "target", "changed", "ms", ...}；加 --timing 多一個 "t"（各階段毫秒）；ensure 走 watch 快路徑時有 "via": "watch"
  給其他腳本 import：char.current() / char.switch(name) / char.ensure(name) 回退出碼，結果 dict 在 char.LAST（同一行程只付一次起 server 的 0.85 s）

不會自動切回 DKBO（計畫 §9 第 10 條）：切到別人之後由呼叫端負責 `ensure DKBO`。
切換後畫面換成那個角色的位置（可能不同地圖），之後的走路 / 點擊以新角色為準；隊伍身分不變（P-I3 實測）。

退出碼（共用 0 / 1 / 2 / 8 / 9 / 10 見 uikit；char 自己 60～65）：
  60 切換面板打不開或讀圖中途消失（沒點任何面板內座標）
  61 目標卡片找不到：名字沒有被 namematch 樣板（或 OCR 一致）確認、或該卡不是「線上」（離線 / 狀態不明）→ 不點，不猜
  62 點了卡片但驗證時當前不是目標（不重點第二次）
  63 當前框數量 ≠ 1（讀不準）
  64 名字矛盾（樣板與順序不同、OCR 讀到別人）
  65 點了卡片但「加載中」後 HUD 6 s 內沒回來（可能是別的視窗，停手看畫面）

流程（P-I3 實測 2026-10-11）：點卡片後切換面板一定自己關；加載畫面約 0.25～0.5 s，HUD 在點擊返回後約 0.6 s 回來（整體約 1.2～1.4 s）。
所以：點卡片前 team.read_state(keep_open) 讀一次，名字確認 + 狀態線上才點；點完先等加載特徵出現（≤1.5 s）再等 SIG_HUD（≤6 s）；
最後重開面板（read_state）以「當前框 + 名字」驗證，沒到就再等 1.5 s 重讀一次（唯讀，不重點）。成功才寫 charstate。
加速（2026-10-11）：preflight 用 watch 快路徑、waitpix 開關面板、namematch 全命中不 OCR；ensure 在 watch 名牌與旁路檔都已是目標且夠新（見 watch_confirms）時完全不開面板。耗時見 ui/team.md。
"""
import time

_T_START = time.time()                # --timing 的「import」段起點（含 uv 啟動後的模組載入）
import argparse  # noqa: E402
import json  # noqa: E402
import sys  # noqa: E402
from pathlib import Path  # noqa: E402

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import charstate  # noqa: E402
import screen_sigs  # noqa: E402
import team  # noqa: E402
import uikit  # noqa: E402

SRC = 'char'
EXIT_PANEL, EXIT_NO_CARD, EXIT_NOT_SWITCHED, EXIT_CUR_COUNT, EXIT_CONFLICT, EXIT_NO_HUD = 60, 61, 62, 63, 64, 65
CLICK_WAIT_MS = 100                  # 點卡片後 seq 內固定等待（舊 300；之後有 wait_switched 等 HUD）
CLICK_DX = 204                       # 點卡片中段（左欄 620、右欄 930；ui/team.md 的卡片座標）
LOADING_SEEN_S = 1.5                 # 點完最多等這麼久看加載畫面出現
HUD_TIMEOUT_S = 6.0
VERIFY_RETRY_S = 1.5
POLL_S = 0.05
LOADING_GRACE_S = 1.0                # 沒看到加載畫面時，點擊後這麼久才接受 HUD（避免面板剛自關、加載還沒出現那一瞬間的 HUD）
FAST_NAME_MAX_AGE_S = 8.0            # ensure 快路徑：頭頂名牌多新才採用（watch 名牌每 3～9 s 才核對一次；另外要求名牌核對時間在目前畫面狀態開始之後）
FAST_CHAR_MAX_AGE_S = 1800.0         # ensure 快路徑：current-char.json 多新才採用
RETRY_RC = (EXIT_NO_CARD, EXIT_CUR_COUNT)  # 暫時性讀不準：飄字 / 戰鬥淡入剛好蓋住卡片（掛機遇敵開著時常見），重讀就好
READ_TRIES = 3
READ_RETRY_S = 0.8
LAST: dict = {}                      # 最近一次 current / switch / ensure 的結果 dict（可 import 的呼叫端讀這個，同最後一行 JSON）


def confirmed(c) -> bool:
    """卡片名字是否「有證據」：namematch 樣板命中且與順序不矛盾，或舊 OCR 交叉一致。順序單獨推得的名字（check unknown / unread）不算"""
    return bool(c.name) and c.check == 'ok'


def analyse(r: dict, target=None) -> dict:
    """純函式：team.read_state 結果 → {'rc', 'msg', 'current', 'target_card'}。rc 0 = 讀得準（current 已確認名字）
    順序：名字矛盾 64 > 當前框 ≠ 1 → 63 > 當前名字沒確認 61；target_card = 目標卡（確認名字 + 線上）或 None"""
    cards = r['cards']
    bad = [c for c in cards if c.check == 'conflict']
    if bad:
        return {'rc': EXIT_CONFLICT, 'msg': '名字矛盾：' + '、'.join(f'slot{c.slot}={c.name} OCR {c.ocr}' for c in bad), 'current': None, 'target_card': None}
    cur = [c for c in cards if c.status == 'current']
    if len(cur) != 1:
        return {'rc': EXIT_CUR_COUNT, 'msg': f'當前框 {len(cur)} 個（要剛好 1 個）', 'current': None, 'target_card': None}
    cc = cur[0]
    tc = next((c for c in cards if target and confirmed(c) and c.status == 'online' and charstate.same(c.name, target)), None)
    if not confirmed(cc):
        return {'rc': EXIT_NO_CARD, 'msg': f'當前框在 slot{cc.slot}，但名字無法確認（樣板 / OCR 都沒證據）', 'current': None, 'target_card': tc}
    return {'rc': 0, 'msg': '', 'current': charstate.display(cc.name), 'target_card': tc}


def read_analyse(target=None, keep_open: bool = False) -> tuple:
    """team.read_state + analyse；rc 61 / 63（名字沒證據 / 當前框數不對）多半是掛機飄字（恢復血量、獲得 EXP 等半透明橫條）
    或戰鬥淡入剛好蓋住卡片，重讀最多 READ_TRIES 次（每次間隔 READ_RETRY_S，不點任何東西）；矛盾（64）不重試。→ (r, a)"""
    r = a = None
    for i in range(READ_TRIES):
        r = team.read_state(True, keep_open=keep_open)
        if not r['ok']:
            return r, None
        a = analyse(r, target)
        if a['rc'] not in RETRY_RC:
            break
        if i + 1 < READ_TRIES:
            print(f'char：讀卡片 rc {a["rc"]}（{a["msg"]}），{READ_RETRY_S} s 後重讀（{i + 1}/{READ_TRIES}）')
            uikit.sleep(READ_RETRY_S)
    return r, a


def wait_switched(loading_s: float = LOADING_SEEN_S, hud_s: float = HUD_TIMEOUT_S) -> tuple:
    """點卡片後：一次 pixel 同時讀「加載畫面」與 SIG_HUD 的點（每圈約 60 ms）。
    加載畫面出現過後 HUD 回來 = 切換完成；一直沒看到加載畫面（太快錯過）→ 點擊後 LOADING_GRACE_S 才接受 HUD。
    → (看到加載, HUD 回來, 秒數)；hud_s 內 HUD 沒回來 → (seen, False, 秒數)"""
    t0 = uikit.clock()
    load_pts = [(x, y) for x, y, *_ in screen_sigs.SIG_LOADING]
    hud_pts = [(x, y) for x, y, *_ in screen_sigs.SIG_HUD]
    nl = len(load_pts)
    seen = False
    while True:
        cols = uikit.px(load_pts + hud_pts)
        el = uikit.clock() - t0
        if cols:
            if all(screen_sigs.close(c, (r, g, b), t) for c, (_, _, r, g, b, t) in zip(cols[:nl], screen_sigs.SIG_LOADING)):
                seen = True
            elif all(screen_sigs.close(c, (r, g, b), t) for c, (_, _, r, g, b, t) in zip(cols[nl:], screen_sigs.SIG_HUD)):
                if seen or el >= min(loading_s, LOADING_GRACE_S):
                    return seen, True, el
        if el >= hud_s:
            return seen, False, el
        uikit.sleep(POLL_S)


def _out(rc: int, info: dict, t0: float, msg: str = '') -> int:
    info.setdefault('changed', False)
    info.update(ok=rc == 0, rc=rc, ms=int((time.time() - t0) * 1000))
    if msg:
        info['msg'] = msg
    if uikit._stages is not None:
        info['t'] = uikit.timing_get()
    LAST.clear()
    LAST.update(info)
    print(json.dumps(info, ensure_ascii=False))
    return rc


def _record(name) -> None:
    if name:
        charstate.write(name, src='char.py')


def current(as_json: bool = False) -> int:
    """唯讀：讀當前是誰；名字確認才寫 charstate"""
    t0 = time.time()
    rc = uikit.preflight(SRC)
    if rc:
        return _out(rc, {'current': None}, t0)
    r, a = read_analyse()
    if not r['ok']:
        uikit.snap('char-current-fail')
        uikit.fail(SRC, EXIT_PANEL, r['err'])
        return _out(EXIT_PANEL, {'current': None}, t0, r['err'])
    if a['rc']:
        uikit.snap('char-current-fail')
        uikit.fail(SRC, a['rc'], a['msg'])
        return _out(a['rc'], {'current': None}, t0, a['msg'])
    _record(a['current'])
    if not as_json:
        print(f'當前角色：{a["current"]}')
    return _out(0, {'current': a['current']}, t0)


def watch_confirms(target: str) -> bool:
    """ensure 快路徑條件：watch 頭頂名牌（hud.name 非 stale、src = both / ocr、≤8 s、核對時間晚於目前畫面狀態的開始時間 screen.since
    ——切換角色會經過加載畫面使 since 重置，所以「換人之前的舊名牌」不會被採用）與 current-char.json（≤30 分）都等於 target。
    任一不符 / watch 不在 / 太舊 → False（呼叫端照舊開面板確認）。只讀檔，不碰遊戲"""
    try:
        st = uikit.watch_state()
        sc = uikit.watch_screen() if st else None
    except Exception:
        return False
    since = (sc or {}).get('since')
    if not isinstance(since, (int, float)):
        return False
    nm = ((st or {}).get('hud') or {}).get('name') or {}
    ts = nm.get('ts')
    if nm.get('stale') or nm.get('src') not in ('both', 'ocr') or not isinstance(ts, (int, float)) or time.time() - ts > FAST_NAME_MAX_AGE_S:
        return False
    if ts < since or not charstate.same(nm.get('v'), target):
        return False
    cc = charstate.read(max_age=FAST_CHAR_MAX_AGE_S)
    return bool(cc) and charstate.same(cc.get('name'), target)


def switch(target_text: str, fast: bool = False) -> int:
    """切到 target（已是就不點）。回退出碼；最後一行 JSON。
    fast=True（ensure）：watch 名牌與 current-char.json 都已是 target 且夠新就直接回 0（info['via']='watch'，不開面板、不點）；其餘照舊現場開面板確認"""
    t0 = time.time()
    hit = charstate.norm_char(target_text)
    target = charstate.display(hit) if hit else None
    if not target:
        print(f'char：角色名 {target_text!r} 不在白名單 {charstate.chars()}', file=sys.stderr)
        return _out(uikit.EXIT_USAGE, {'target': None, 'current': None}, t0, '角色名不在白名單')
    info = {'target': target, 'current': None}
    rc = uikit.preflight(SRC)
    if rc:
        return _out(rc, info, t0)
    if fast and watch_confirms(target):
        _record(target)
        uikit.mark('watch-confirm')
        info.update(current=target, via='watch')
        print(f'char：watch 名牌與旁路檔都是 {target}，沒有開面板、沒有點擊')
        return _out(0, info, t0)
    clicked = False
    try:
        r, a = read_analyse(target, keep_open=True)
        if not r['ok']:
            uikit.snap('char-switch-fail')
            uikit.fail(SRC, EXIT_PANEL, r['err'])
            return _out(EXIT_PANEL, info, t0, r['err'])
        info['current'] = a['current']
        if a['rc']:                                   # 矛盾 / 當前框數不對 / 當前名字不明：不知道來源狀態，不敢切
            uikit.snap('char-switch-fail')
            uikit.fail(SRC, a['rc'], a['msg'])
            return _out(a['rc'], info, t0, a['msg'])
        if charstate.same(a['current'], target):
            _record(target)
            print(f'char：當前已是 {target}，沒有點擊')
            return _out(0, info, t0)
        tc = a['target_card']
        if tc is None:
            names = [(c.name, c.status, c.check) for c in r['cards']]
            uikit.snap('char-switch-nocard')
            msg = f'找不到可點的 {target} 卡片（要求：名字確認 + 線上）；卡片 {names}'
            uikit.fail(SRC, EXIT_NO_CARD, msg)
            return _out(EXIT_NO_CARD, info, t0, msg)
        x0, y = team.SLOTS[tc.slot]
        uikit.mark('read-cards')
        if not uikit.safe_click(x0 + CLICK_DX, y, uikit.SWITCH, note=f'char 切到 {target}（slot{tc.slot}）', wait_ms=CLICK_WAIT_MS):
            msg = '點卡片前切換面板特徵不在，沒點'
            uikit.fail(SRC, EXIT_PANEL, msg)
            return _out(EXIT_PANEL, info, t0, msg)
        clicked = True
        uikit.mark('click')
    finally:
        if not clicked:
            uikit.close_panel(uikit.SWITCH, known_open=True)
            uikit.mark('close')
    # 面板會自己關；等加載 → HUD → 重開面板驗證（唯讀，絕不重點）
    seen, hud, sec = wait_switched()
    uikit.mark('wait-load+hud')
    info['loading_seen'] = seen
    info['changed'] = True                             # 已點擊：畫面可能已換角色，呼叫端要知道
    if not hud:
        uikit.snap('char-switch-nohud')
        msg = f'點了 {target} 卡片，但 HUD {HUD_TIMEOUT_S:.0f} s 內沒回來（可能是別的視窗）'
        uikit.fail(SRC, EXIT_NO_HUD, msg)
        return _out(EXIT_NO_HUD, info, t0, msg)
    a = {'rc': EXIT_NOT_SWITCHED, 'msg': '', 'current': None}
    for i in range(2):
        r = team.read_state(True)
        if r['ok']:
            a = analyse(r)
            if a['rc'] == 0 and charstate.same(a['current'], target):
                break
        else:
            a = {'rc': EXIT_PANEL, 'msg': r['err'], 'current': None}
        if i == 0:
            uikit.sleep(VERIFY_RETRY_S)
    info['current'] = a['current']
    if a['rc'] == 0 and charstate.same(a['current'], target):
        _record(target)
        print(f'char：已切到 {target}（加載 {"有" if seen else "沒"}看到，HUD 回來 {sec:.1f} s）')
        return _out(0, info, t0)
    rc = a['rc'] or EXIT_NOT_SWITCHED
    msg = a['msg'] or f'點了 {target} 卡片但驗證時當前是 {a["current"]}'
    uikit.snap('char-switch-verify-fail')
    uikit.fail(SRC, rc, msg)
    return _out(rc, info, t0, msg)


def ensure(target_text: str) -> int:
    """是就不動、不是才切（grind / pet-quest 收尾用）；比 switch 多一條 watch 快路徑（見 switch）"""
    return switch(target_text, fast=True)


def main() -> int:
    import winenv
    winenv.enable_server()
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    tp = argparse.ArgumentParser(add_help=False)
    tp.add_argument('--timing', action='store_true', help='最後一行 JSON 多一個 t 欄位：各階段毫秒（含 import）')
    sub = ap.add_subparsers(dest='cmd', required=True)
    p = sub.add_parser('current', help='唯讀：當前角色', parents=[tp])
    p.add_argument('--json', action='store_true', help='只印最後一行 JSON')
    for n in ('switch', 'ensure'):
        p = sub.add_parser(n, help='切到指定角色（已是就不點）', parents=[tp])
        p.add_argument('name')
    a = ap.parse_args()
    if a.timing:
        uikit.timing_start()
        uikit._stages.append(['import', int((time.time() - _T_START) * 1000)])
        uikit.gui('pixel', '1,1')                      # 暖機：本程序第一次 gui 呼叫要先起 serve.ps1（約 0.85 s，之後的呼叫才是真正的動作耗時）
        uikit.mark('server-start')
    if a.cmd == 'current':
        return current(a.json)
    return ensure(a.name) if a.cmd == 'ensure' else switch(a.name)


if __name__ == '__main__':
    sys.exit(main())
