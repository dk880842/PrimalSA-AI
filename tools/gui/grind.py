#!/usr/bin/env python3
"""開始 / 恢復練功（P5）。計畫：notes/plan-scriptify.md §3。取代 psa-grind-start 的手動截圖流程。只用標準函式庫。

用法（專案根目錄；WSL / Windows 原生指令相同）：
  uv run --no-project python tools/gui/grind.py start [--trans N] [--no-follow] [--heal] [--confirm-secs 30] [--no-fix]   # 「去練功」（= --spot auto，見下）
  uv run --no-project python tools/gui/grind.py start --spot 地雷區2|here [--heal] [--confirm-secs 30] [--no-fix]          # 固定點（不起 follow；有 follow 在跑先停）
  uv run --no-project python tools/gui/grind.py ensure [--confirm-secs 30] [--no-fix]   # 不傳送：補血回來 / 任務後 / 重登後用
  uv run --no-project python tools/gui/grind.py follow [--every 15] [--buffer 0] [--until-level N] [--dry-run] | --stop   # 依等級自動換練功點（常駐；見 follow.py）
  uv run --no-project python tools/gui/grind.py check                                   # 唯讀：5 人快速戰鬥 / 自動戰鬥 + 遇敵鈕，不改任何東西
最後一行是 JSON（rc、耗時、各步秒數、EXP 命中數…）；同內容寫 tools/.cache/grind.json。

去練功（使用者 2026-10-15；`start` 不給 --spot 或 --spot auto；可 import：grind.go(trans=None, trans_hint=None, …)）：
  有 follow 在跑先停（它持 grind.lock）→ 依當下隊長等級選點（spots.auto_spot = AUTO 表 + spots.learn 學到的門檻）→ 傳送 → 外掛 → 遇敵 → EXP 確認 →
  選到最高一檔（地雷區 ≥120，spots.is_top）→ 結束，不起 follow；未滿 → 背景常駐 `grind.py follow --no-heal --trans N`（follow.ensure_running：
  winenv.spawn_detached，已有同轉數的在跑不重開；輸出 tools/.cache/follow.log），follow 換到地雷區確認掛機後自己結束。follow 起不來只記 errlog（退出碼仍 0）。
  轉數（HUD 轉數位會讀錯，不用）：--trans 明講 > 背包讀隊長等級字（bag.levels，成功寫 tools/.cache/trans.json）> trans_hint > 快取 > HUD（警告）。
  JSON 帶 trans / trans_src / level_num / follow（{'action': none|skip|running|started|fail, 'pid'}）；notes/quest-events.log 記一行「grind：去練功…」。
  任何腳本都不寫死 --spot 地雷區（四轉後寫死導致在 1 級點掛 6 小時）；只有使用者指定的固定點（恐龍博士 / 卡坦練寵 = 波拉島）才帶 --spot。

退出碼（共用 0 / 1 / 2 / 8 / 9 / 10 見 uikit；grind 自己 50～58）：
  0  已確認掛機中（start / ensure：30 秒內看到 ≥2 次 EXP 橫幅；check：5 人設定都對 + 遇敵開）
  50 隊伍不全且 team.form 失敗（info.team_rc 是 team 的退出碼）
  51 傳送失敗：依表預判等級不夠（不送出）、傳送後地圖沒變、或 --spot 讀不到目前地圖
  52 外掛設定失敗（info.role / ass_rc）；check 時 = 有人快速戰鬥 / 自動戰鬥是關的
  53 此地圖禁止快速戰鬥（ass 回 4 且項目是快速戰鬥）
  54 原地遇敵開不起來（check 時 = 遇敵鈕是關的）
  55 確認視窗內沒看到 ≥2 次 EXP 橫幅（遇敵開著但沒戰鬥 / 沒經驗）；只看到 1 次時自動再延長一輪（遇敵稀疏的點，累計 ≥2 次算 ok）。JSON：from_map = 換點前地圖、to_map = 換點後、map_mismatch = 結束地圖與目標不符
  56 看到完整戰鬥畫面（有人沒快速戰鬥）；--fix（預設開）會先自動重設一次再確認，仍看到才回 56
  57 補血失敗（heal RuntimeError）
  58 當前角色切不回隊長（char.ensure 失敗，info.char_rc）
  59 follow 專用：連續讀不到等級（follow 其他退出碼見 follow.py 檔頭）

流程（與計畫 §3.3 的差異：外掛設定「先讀 5 人、只改不對的」，不是 5 人全點）：
  preflight → char.ensure(隊長) → 關遇敵 + 等戰鬥結束 → team.check / form → [start：選點 / 補血 / 傳送]
  （2026-10-12：char.ensure 與 team.check 合併成一次開切換面板 = leader_team_read：當前是隊長且隊伍完整、關遇敵後 TEAM_REUSE_S 秒內沒打仗 → 不再 team.check；
   watch 名牌已確認是隊長 / 讀不準 / 當前不是隊長 → 照舊兩步）
  → 一次開外掛面板（ass.set_many）逐人讀快速戰鬥 + 自動戰鬥、只點不對的 → 隊長開遇敵（主畫面鈕，紅龍頭確認）
  → 確認視窗（1 s 一次 pixel）：EXP 橫幅 ≥2 次 → 成功；完整戰鬥連 2 次 → 56（--fix 重設一次）；unknown 連 3 次 → 9。
外掛只動 快速戰鬥 / 自動戰鬥 兩項；傳送、遇敵鈕屬紅區，使用者要求練功 / 掛機就等於授權（psa-grind-start）。
鎖：tools/.cache/grind.lock（pid）；battle.lock（quest）有效 / petwatch.lock 的 pid 活著 / 另一支 heal --watch（Linux /proc 掃描，盡力偵測）→ 退出 8。

EXP 橫幅（P-R1 實測 2026-10-11）：矩形稀疏掃 y 140～262 每 6 px、x 450～1000 每 4 px（約 2900 點，一次 pixel 約 0.1 s），
紫色 100≤r≤200、g<110、b>180、b−g>90，≥8 點 = 有橫幅（正例 19～24 點、負例 0 點）。橫幅有兩種版型、進場位置會滑動，所以不用固定列。
"""
import argparse
import json
import os
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import ass  # noqa: E402
import battleguard  # noqa: E402
import char  # noqa: E402
import charstate  # noqa: E402
import heal  # noqa: E402
import screen_sigs  # noqa: E402
import spots  # noqa: E402
import team  # noqa: E402
import clients  # noqa: E402
import uikit  # noqa: E402
import walk  # noqa: E402

SRC = 'grind'
EXIT_TEAM, EXIT_TELEPORT, EXIT_ASS, EXIT_NO_FAST, EXIT_ENC, EXIT_NO_EXP, EXIT_FULL_BATTLE, EXIT_HEAL, EXIT_CHAR = 50, 51, 52, 53, 54, 55, 56, 57, 58
LEADER = clients.leader() or ''       # 隊長 = 這個視窗名單第 1 個（主視窗 DKBO，真名字母 O；DKB0 同義；PrimalSA2 DKBO6）
ROLE_ORDER = clients.leader_last()    # 讀 / 改順序：隊長最後，結束時外掛面板選在隊長（主視窗 DKBO2～DKBO5, DKBO）
BANNER_WAIT = 8.0
WANT = {'快速戰鬥': True, '自動戰鬥': True}
CACHE = uikit.CACHE
LOCK = CACHE / 'grind.lock'
OUT = CACHE / 'grind.json'

# ---- EXP 橫幅偵測（P-R1）----
EXP_YS = list(range(140, 263, 6))
EXP_XS = list(range(450, 1001, 4))
EXP_PTS = [(x, y) for y in EXP_YS for x in EXP_XS]
EXP_MIN = 8                           # 稀疏版門檻：正例最低 19、負例最高 0


def is_exp_purple(c) -> bool:
    r, g, b = c
    return 100 <= r <= 200 and g < 110 and b > 180 and b - g > 90


def exp_banner(px: dict) -> int:
    """px = {(x, y): (r, g, b)}（含 EXP_PTS）→ 紫色點數；≥ EXP_MIN 才算有橫幅（純函式，fixture 測）"""
    return sum(1 for p in EXP_PTS if p in px and is_exp_purple(px[p]))


# ---- 確認視窗 ----
CONFIRM_SECS = 30.0
EXP_NEED = 2                          # 視窗內要看到幾次橫幅（rising edge，且距上一次 ≥ EXP_GAP 秒）
EXP_GAP = 2.0
FULL_N = 2                            # 完整戰鬥連幾次 → 56
UNKNOWN_N = 3                         # unknown 連幾次 → 9
ENC_OFF_N = 3                         # 遇敵鈕連幾次是關的 → 54
POLL = 1.0
ACTIVE = False                        # grind.run 執行中（netwatch.recover 巢狀時不重入）
sleep = time.sleep                    # 測試替換
clock = time.time

_marks: list = []
_t0 = 0.0
LAST: dict = {}                       # 最近一次 run 的 {'info': {...}}（go() / 呼叫端 / 測試讀）


ass.wait_cover_hook = lambda timeout=BANNER_WAIT: wait_banner_gone(timeout)     # ass.select_role 頭像被遮住時，先用 EXP 橫幅偵測等


def lap(label: str) -> None:
    """記下距上一個 lap 的秒數"""
    global _t0
    now = clock()
    _marks.append([label, round(now - _t0, 1)])
    _t0 = now


def log(msg: str) -> None:
    print(f'grind：{msg}', flush=True)


TEAM_REUSE_S = 5.0                    # 開頭那次切換面板讀過隊伍，關遇敵 + 等戰鬥在這麼多秒內結束（沒打仗）→ 沿用結果，不再 team.check（完整 = 跳過；不完整 = 直接 form）


def leader_team_read() -> dict | None:
    """一次開切換面板同時確認「當前 = 隊長」與「5 人隊伍完整」（取代 char.ensure + team.check 各開一次；2026-10-12 questrun 收尾連開 2 次）。
    → {'current', 'team_rc', 'desc', 't'}；watch 名牌已確認是隊長（char.ensure 快路徑不開面板）/ 面板打不開 / 名字讀不準 → None（呼叫端照舊兩步）"""
    if char.watch_confirms(LEADER):
        return None
    r, a = char.read_analyse(LEADER)
    if not r.get('ok') or a is None or a['rc']:
        return None
    code, desc = team.judge(r['cards'], 5, LEADER)
    return {'current': a['current'], 'team_rc': code, 'desc': desc, 't': clock()}


# ---- 鎖 ----
def _other_running() -> str | None:
    """另一支會搶畫面的工具在跑 → 回名稱。petwatch / grind 看鎖檔 pid（鎖檔每個視窗一份）；heal --watch 沒有鎖檔，Linux 掃 /proc（盡力）。
    多視窗：別的視窗（環境變數 PSA_CLIENT 不同）的 heal --watch 不算衝突；讀不到對方環境照舊當衝突"""
    for name, lock in (('grind', LOCK), ('petwatch', CACHE / 'petwatch.lock')):
        try:
            pid = int(lock.read_text().strip())
        except (OSError, ValueError):
            continue
        if pid != os.getpid() and battleguard.pid_alive(pid):
            return f'{name}（pid {pid}）'
    proc = Path('/proc')
    if proc.is_dir() and clients.test_state_dir() is None:   # 離線測試不掃真實程序（主工作樹可能真的有 heal --watch 在跑）
        me = str(os.getpid())
        try:
            for d in proc.iterdir():
                if d.name.isdigit() and d.name != me:
                    try:
                        cmd = (d / 'cmdline').read_bytes().split(b'\0')
                    except OSError:
                        continue
                    if any(c.endswith(b'heal.py') for c in cmd) and b'--watch' in cmd:
                        other = clients.proc_client(d.name)
                        if other is not None and other.lower() != clients.name().lower():
                            continue                       # 別的視窗的 heal --watch
                        return f'heal --watch（pid {d.name}）'
        except OSError:
            pass
    return None


def take_lock() -> bool:
    try:
        LOCK.parent.mkdir(parents=True, exist_ok=True)
        LOCK.write_text(str(os.getpid()))
        return True
    except OSError:
        return False


def release_lock() -> None:
    try:
        if LOCK.read_text().strip() == str(os.getpid()):
            LOCK.unlink()
    except OSError:
        pass


# ---- 外掛 5 人讀 / 改 ----
def read_all(no_wait: bool = False) -> tuple:
    """一次開外掛面板，逐人選角色讀 快速戰鬥 / 自動戰鬥 / 原地遇敵（只讀，不點勾選）= ass.set_many 全部 None。
    回 (ass 退出碼, {角色: 狀態 dict}, 訊息, {角色: 秒})；面板中途消失 / 選不到角色 → 非 0 且已讀到的照回"""
    rc, states, msg, info = ass.set_many({r: None for r in ROLE_ORDER}, no_wait=no_wait)
    return rc, states, msg, info['secs']


def wrong_of(states: dict) -> dict:
    """{角色: [不對的項目]}（快速戰鬥 / 自動戰鬥不是開）"""
    out = {}
    for role, st in states.items():
        bad = [i for i, want in WANT.items() if st.get(i) != want]
        if bad:
            out[role] = bad
    return out


# ---- 遇敵 / 畫面 ----
def enc_on_screen() -> bool:
    return bool(heal.encounter_on())


def read_screen() -> tuple:
    """一次 pixel：EXP 稀疏點 + screen_sigs.points + 遇敵鈕 → (exp 點數, classify 結果, 遇敵鈕開?)；讀不到 → (0, {'state': 'error'}, None)"""
    pts = list(dict.fromkeys(EXP_PTS + screen_sigs.points() + [(x, y) for x, y, *_ in screen_sigs.ENC_ON]))
    cols = uikit.px(pts)
    if cols is None:
        return 0, {'state': 'error'}, None
    px = dict(zip(pts, cols))
    return exp_banner(px), screen_sigs.classify(px), screen_sigs.match(px, screen_sigs.ENC_ON)


def confirm(secs: float) -> dict:
    """確認視窗：回 {'result': 'ok' | 'no_exp' | 'full_battle' | 'unknown' | 'enc_off', 'events': n, 'polls': n, 'max_px': 最高紫點數}"""
    end = clock() + secs
    events, last_event, prev_hit = 0, None, False
    full = unk = off = polls = 0
    max_px = 0
    while True:
        t = clock()
        n, c, enc = read_screen()
        polls += 1
        max_px = max(max_px, n)
        hit = n >= EXP_MIN
        if hit and not prev_hit and (last_event is None or t - last_event >= EXP_GAP):
            events += 1
            last_event = t
        prev_hit = hit
        if events >= EXP_NEED:
            return {'result': 'ok', 'events': events, 'polls': polls, 'max_px': max_px}
        full = full + 1 if c.get('full') else 0
        unk = unk + 1 if (c.get('state') in ('unknown', 'error') and not hit and not (c.get('state') == 'unknown' and uikit.transition_now())) else 0   # 載入圖 / 全黑轉場不算
        off = off + 1 if enc is False else 0
        if full >= FULL_N:
            return {'result': 'full_battle', 'events': events, 'polls': polls, 'max_px': max_px}
        if unk >= UNKNOWN_N:
            return {'result': 'unknown', 'events': events, 'polls': polls, 'max_px': max_px}
        if off >= ENC_OFF_N:
            return {'result': 'enc_off', 'events': events, 'polls': polls, 'max_px': max_px}
        if clock() >= end:
            return {'result': 'no_exp', 'events': events, 'polls': polls, 'max_px': max_px}
        sleep(POLL)


# ---- check（唯讀）----
def run_check(info: dict) -> int:
    rc, states, msg, secs = read_all(no_wait=False)
    info['role_secs'] = secs
    if rc:
        info['msg'] = msg
        return uikit.fail(SRC, rc if rc == ass.EXIT_IN_BATTLE else EXIT_ASS, f'讀外掛失敗（ass 退出碼 {rc}）：{msg}')
    info['states'] = {r: {i: bool(v) for i, v in s.items() if i in ('快速戰鬥', '自動戰鬥', '原地遇敵')} for r, s in states.items()}
    bad = wrong_of(states)
    enc = enc_on_screen()
    info['enc_button_on'] = enc
    info['wrong'] = bad
    for role in ROLE_ORDER[-1:] + ROLE_ORDER[:-1]:
        s = states.get(role)
        if s:
            log(f'{role}：{ass.fmt(s)}')
    log(f'遇敵鈕：{"開（取消遇敵）" if enc else "關（遇敵）"}')
    if bad:
        return uikit.fail(SRC, EXIT_ASS, '快速戰鬥 / 自動戰鬥不是全開：' + '、'.join(f'{r} {"+".join(v)}' for r, v in bad.items()))
    if not enc:
        return uikit.fail(SRC, EXIT_ENC, '原地遇敵鈕是關的')
    return 0


# ---- start / ensure ----
def wait_banner_gone(timeout: float = BANNER_WAIT) -> bool:
    """等最後一場的 EXP 橫幅消失（連 2 次沒有）。橫幅的位置（x 450～1000、y 140～262）剛好蓋住外掛面板的 DKBO3 頭像（461,151），
    開面板時還在就選不到角色（2026-10-11 ensure 實測）。逾時回 False（照樣往下走，讓 read_all 的重試處理）"""
    end, clear = clock() + timeout, 0
    while clock() < end:
        n, _, _ = read_screen()
        clear = clear + 1 if n < EXP_MIN else 0
        if clear >= 2:
            return True
        sleep(0.5)
    return False


def fix_settings(info: dict) -> int:
    """一次開面板：5 人逐人讀、只點不對的項目（ass.set_many）；回 0 或 52 / 53 / ass 的 8。隊長在最後，結束時面板選在隊長"""
    wait_banner_gone()
    rc, states, msg, ainfo = ass.set_many({r: dict(WANT) for r in ROLE_ORDER})
    info['role_secs'] = ainfo['secs']
    fixed = info.setdefault('fixed', {})
    fixed.update(ainfo['changed'])
    for role, items in ainfo['changed'].items():
        log(f'{role}：{"、".join(items)} 沒開 → 已設定')
    lap('外掛修正' if fixed else '外掛讀 5 人（無需修正）')
    if rc:
        info['ass_rc'] = rc
        if ainfo['role']:
            info['role'] = ainfo['role']
        if rc == ass.EXIT_IN_BATTLE:
            return rc
        if rc == ass.EXIT_CONFIRM and '快速戰鬥' in ainfo['changed'].get(ainfo['role'], []):
            return uikit.fail(SRC, EXIT_NO_FAST, f'{ainfo["role"]} 快速戰鬥點了沒變：此地圖可能禁止快速戰鬥（{msg}）')
        return uikit.fail(SRC, EXIT_ASS, f'外掛設定失敗（ass 退出碼 {rc}，{ainfo["role"] or "?"}）：{msg}')
    return 0


# ---- 隊長轉數（去練功 auto 選點 / follow --trans 用）----
TRANS_FILE = CACHE / 'trans.json'


def save_trans(trans: int, level=None, src: str = '') -> None:
    """記下最近一次可靠讀到的隊長轉數（背包讀字 / rebirth 轉生確認）；寫檔失敗不丟例外"""
    try:
        TRANS_FILE.parent.mkdir(parents=True, exist_ok=True)
        TRANS_FILE.write_text(json.dumps({'trans': int(trans), 'level': level, 'src': src, 'ts': int(time.time())}, ensure_ascii=False), encoding='utf-8')
    except (OSError, ValueError, TypeError):
        pass


def load_trans() -> int | None:
    try:
        t = json.loads(TRANS_FILE.read_text(encoding='utf-8')).get('trans')
        return t if isinstance(t, int) and 0 <= t <= 5 else None
    except (OSError, ValueError, AttributeError):
        return None


def read_leader_bag():
    """背包面板讀隊長等級字（bag.levels，rebirth 判轉數用的同一套）→ (轉, 級) 或 None（測試替換）"""
    import bag
    rc, lv = bag.levels([LEADER])
    return None if rc else lv.get(LEADER)


def leader_trans(hint=None) -> tuple:
    """→ (轉數或 None, 背包讀到的等級或 None, 來源 'bag' | 'hint' | 'cache' | '')。
    順序：背包讀隊長（可靠，成功順便寫快取）→ 呼叫端給的 hint（rebirth_pets 的 --trans）→ tools/.cache/trans.json → 都沒有 None"""
    try:
        v = read_leader_bag()
    except Exception as e:                    # 讀不到不擋練功：退回下一個來源
        log(f'背包讀隊長轉數失敗：{e}')
        v = None
    if v and v[0] is not None:
        save_trans(v[0], v[1], 'bag')
        return v[0], v[1], 'bag'
    if hint is not None:
        return int(hint), None, 'hint'
    c = load_trans()
    if c is not None:
        return c, None, 'cache'
    return None, None, ''


def choose_spot(spot: str, trans: int, level: int, cur_map) -> tuple:
    """→ (目的點名或 None = 不傳送, 錯誤訊息或 '')。here = 不傳送；auto 依等級；已在同點 / 同檔點 = 不傳送"""
    if spot == 'here':
        return None, ''
    if spot == 'auto':
        name = spots.auto_spot(trans, level)
        if not name:
            return None, f'等級 {level} 不到可練功點'
        if trans:
            log(f'警告：{trans} 轉的練功點門檻{spots.UNTESTED}')
    else:
        name = spot
    if spots.too_low(name, trans, level):
        return None, f'{name} 門檻 0轉{spots.SPOTS[name][3]}級，隊長 {trans}轉{level}級 → 依表會被擋，不送出傳送'
    cur = spots.spot_of_map(cur_map)
    if cur and (cur == name or (spot == 'auto' and spots.same_tier(cur, name))):
        return None, ''
    return name, ''


def read_map() -> int | None:
    p = walk.wait_pos(4, None, 0.5)
    return p[0] if p else None


def here_spot() -> str | None:
    """現在所在的練功點名（heal.stat 的 pos 地圖 ID → spots.spot_of_map）；讀不到 / 不在練功點 None"""
    try:
        return spots.spot_of_map(map_id_of_pos(heal.stat().get('pos')))
    except Exception:
        return None


def auto_spot_now() -> str | None:
    """不開面板的「依等級該去哪」：HUD 等級數字 + 轉數（快取 tools/.cache/trans.json，沒有才用 HUD 轉數位）→ spots.auto_spot；讀不到 None。
    petwatch 補血後決定回哪用（不傳送、不讀背包）"""
    try:
        txt = heal.stat().get('level')
    except Exception:
        return None
    level = spots.level_num(txt)
    if not level:
        return None
    t = load_trans()
    if t is None:
        lv = spots.parse_level(txt)
        t = lv[0] if lv else 0
    return spots.auto_spot(t, level)


def map_id_of_pos(pos) -> int | None:
    """'60049:30,25' → 60049（讀不到 None）"""
    try:
        return int(str(pos).split(':')[0])
    except (ValueError, TypeError):
        return None


def finish(rc: int, mode: str, info: dict, t_start: float) -> int:
    info.update(rc=rc, mode=mode, secs=round(clock() - t_start, 1), laps=_marks, ts=int(time.time()))
    if rc not in (uikit.EXIT_IN_BATTLE, uikit.EXIT_UNKNOWN_SCREEN, uikit.EXIT_HALT):     # 這幾種不再碰畫面
        try:
            s = heal.stat()
            info.update(map=s.get('pos'), level=s.get('level'), hpPct=s.get('hpPct'))
            to = map_id_of_pos(s.get('pos'))
            info['to_map'] = to                     # 換點「後」的地圖 ID（驗證用）
            want = spots.SPOTS[info['spot']][2] if info.get('spot') in spots.SPOTS else None
            if rc == 0 and want and to and to != want and not spots.same_tier(spots.spot_of_map(to) or '', info['spot']):
                info['map_mismatch'] = {'want': want, 'got': to}
                print(f'警告：目標 {info["spot"]}（地圖 {want}）但結束時在地圖 {to}', flush=True)
        except Exception:
            pass
    try:
        OUT.write_text(json.dumps(info, ensure_ascii=False), encoding='utf-8')
    except OSError:
        pass
    print(json.dumps(info, ensure_ascii=False), flush=True)
    return rc


def run(mode: str, spot: str | None = None, confirm_secs: float = CONFIRM_SECS, fix: bool = True, do_heal: bool = False,
        ignore_watchers: bool = False, trans: int | None = None, trans_hint: int | None = None, post=None) -> int:
    """ignore_watchers：呼叫端本身就是 petwatch / heal --watch / netwatch（正卡在 guard 裡、不會同時動），略過它們的偵測；
    quest 的 battle.lock 仍然有效（由 uikit.preflight 擋）。
    trans：start --spot auto 用的隊長轉數（明講就用；沒給 → leader_trans：背包讀 → trans_hint → 快取）。
    post(info) → 退出碼：成功（0）後、印最後一行 JSON 前呼叫（go() 用來起 follow，結果一起寫進 JSON）"""
    global _t0, ACTIVE
    t_start = _t0 = clock()
    _marks.clear()
    info: dict = {}
    LAST.clear()
    LAST['info'] = info
    other = None if ignore_watchers else _other_running()
    if other:
        print(f'{SRC}：{other} 在跑，會搶畫面 → 不動作', file=sys.stderr)
        return finish(uikit.EXIT_IN_BATTLE, mode, info, t_start)
    if not take_lock():
        return finish(uikit.EXIT_IN_BATTLE, mode, info, t_start)
    ACTIVE = True
    try:
        rc = _run(mode, spot, confirm_secs, fix, do_heal, info, trans, trans_hint)
        if rc == 0 and post:
            rc = post(info)
        return finish(rc, mode, info, t_start)
    except SystemExit as e:                  # netwatch.guard 停手（10）
        finish(int(e.code or 0) or uikit.EXIT_HALT, mode, info, t_start)
        raise
    finally:
        ACTIVE = False
        release_lock()


def _run(mode: str, spot, confirm_secs: float, fix: bool, do_heal: bool, info: dict, trans=None, trans_hint=None) -> int:
    rc = uikit.preflight(SRC)
    if rc:
        return rc
    lap('preflight')
    if mode == 'check':
        return run_check(info)
    # 1) 當前角色 = 隊長（遇敵鈕作用在當前角色）；同一次讀面板順便看隊伍（leader_team_read）
    pre = leader_team_read()
    if pre and charstate.same(pre['current'], LEADER):
        charstate.write(LEADER, src='grind.py')
        log(f'當前已是 {LEADER}；隊伍 {pre["desc"]}（一次開面板）')
        lap('當前 + 隊伍（一次讀）')
    else:
        rc = char.ensure(LEADER)
        lap('char.ensure')
        if rc:
            info['char_rc'] = rc
            return rc if rc in (uikit.EXIT_IN_BATTLE, uikit.EXIT_UNKNOWN_SCREEN, uikit.EXIT_HALT) else EXIT_CHAR
        pre = None
    # 2) 先關遇敵再設外掛（外掛面板在戰鬥中打不開）；等戰鬥結束（VS 牌消失）
    heal.set_encounter(False)
    heal.gui('seq', f'waitpix 20000 {heal.SIG_NO_BATTLE} 40')
    lap('關遇敵 + 等戰鬥結束')
    # 3) 隊伍（開頭那次讀過、中間沒打仗 → 沿用結果，不再開面板；不完整就直接 form）
    rc = None
    if pre and clock() - pre['t'] <= TEAM_REUSE_S:
        rc = pre['team_rc']
        log(f'隊伍沿用開頭那次讀到的結果（{pre["desc"]}，退出碼 {rc}），不再開切換面板')
    if rc is None:
        rc = team.check(5, LEADER)
    if rc:
        if rc in (uikit.EXIT_IN_BATTLE, uikit.EXIT_UNKNOWN_SCREEN, uikit.EXIT_HALT):
            return rc
        log(f'隊伍檢查沒過（team 退出碼 {rc}）→ 嘗試快速組隊')
        rc2 = team.form(LEADER, 5)
        info['team_rc'] = rc2
        if rc2 in (uikit.EXIT_IN_BATTLE, uikit.EXIT_UNKNOWN_SCREEN, uikit.EXIT_HALT):
            return rc2
        if rc2 or team.check(5, LEADER):
            return uikit.fail(SRC, EXIT_TEAM, f'隊伍不全且組隊失敗（team 退出碼 {rc2 or rc}）')
    lap('隊伍')
    # 4) 選點 / 傳送（只有 start）
    if mode == 'start':
        s = heal.stat()
        lv = spots.parse_level(s.get('level'))
        cur = read_map()
        info.update(level=s.get('level'), from_map=cur)     # from_map = 換點「前」所在地圖（舊名 cur_map 易誤認為換點後）
        if spot == 'auto':
            # 去練功：轉數不信 HUD（轉數位會讀錯）→ 明講 > 背包讀隊長 > trans_hint > 快取 > HUD（警告）；等級用 HUD 數字，讀不到用背包讀到的
            level, src, blevel = spots.level_num(s.get('level')), 'arg', None
            if trans is None:
                trans, blevel, src = leader_trans(trans_hint)
            if trans is None and lv:
                trans, src = lv[0], 'hud'
                log(f'警告：背包 / 快取都讀不到隊長轉數，改用 HUD 的「{lv[0]}轉」（轉數位可能讀錯）')
            level = level or blevel
            if trans is None or not level:
                return uikit.fail(SRC, uikit.EXIT_USAGE, f'讀不到隊長{"轉數" if trans is None else "等級"}，無法依等級選點（auto）')
            info.update(trans=trans, trans_src=src, level_num=level)
            log(f'隊長 {trans}轉{level}級（轉數來源 {src}）')
            name, err = choose_spot(spot, trans, level, cur)
        else:
            trans, level = lv if lv else (0, 0)
            if spot != 'here' and not lv:
                log('警告：讀不到隊長等級，不預判門檻，直接送出傳送')
            name, err = choose_spot(spot, trans if lv else 1, level, cur)
        if err:
            return uikit.fail(SRC, uikit.EXIT_USAGE if 'auto' in err or '不到可練功點' in err else EXIT_TELEPORT, err)
        target = name or spots.spot_of_map(cur) or spot
        info['spot'] = target
        if do_heal or (isinstance(s.get('hpPct'), int) and s['hpPct'] < 40):
            if target in heal.SPOTS:
                try:
                    heal.heal_trip(target, reopen=False)      # 不開遇敵：外掛設定前遇敵本來就要關
                except RuntimeError as e:
                    return uikit.fail(SRC, EXIT_HEAL, f'補血失敗：{e}')
                info['healed'] = True
                heal.gui('seq', f'waitpix 20000 {heal.SIG_NO_BATTLE} 40')
                lap('補血')
            elif do_heal:
                return uikit.fail(SRC, uikit.EXIT_USAGE, f'{target} 不在 heal.SPOTS（目前版面沒有這點的傳送座標），--heal 不支援；要補血請先跑 heal.py')
            else:
                log(f'警告：血量 {s.get("hpPct")}% < 40 但 {target} 不在 heal.SPOTS，不自動補血')
        if name and not info.get('healed'):
            x, y, mp = spots.SPOTS[name][:3]
            try:
                heal.teleport(heal.TAB_LEVEL, (x, y), mp, name, want_xy=heal.SPOT_XY.get(mp))
            except RuntimeError as e:
                return uikit.fail(SRC, EXIT_TELEPORT, f'傳送 {name} 失敗：{e}')
            lap('傳送')
        elif not name:
            log('已在練功地圖，不傳送' if spot != 'here' else '--spot here：不傳送')
    # 5) 外掛 5 人
    rc = fix_settings(info)
    if rc:
        return rc
    # 6) 開遇敵 + 確認；看到完整戰鬥時重設一次（--fix）
    tries = 2 if fix else 1
    res = {}
    for k in range(tries):
        try:
            heal.set_encounter(True)
        except RuntimeError:
            return uikit.fail(SRC, EXIT_ENC, '原地遇敵開不起來')
        if not enc_on_screen():
            return uikit.fail(SRC, EXIT_ENC, '點了遇敵但紅龍頭沒亮')
        lap('開遇敵')
        res = confirm(confirm_secs)
        if res['result'] == 'no_exp' and res['events'] >= 1:
            # 看到 1 次 EXP 橫幅 = 有在戰鬥，只是這點遇敵稀疏（2026-10-12 海主人隧道 30 秒 1 次 → rc 55，其實一分鐘內連升 5 級）：再給一輪
            r2 = confirm(confirm_secs)
            r2['events'] += res['events']
            r2['polls'] += res['polls']
            r2['max_px'] = max(r2['max_px'], res['max_px'])
            if r2['result'] == 'no_exp' and r2['events'] >= EXP_NEED:
                r2['result'] = 'ok'
            res = r2
        lap('確認視窗')
        info['confirm'] = res
        if res['result'] != 'full_battle' or k == tries - 1:
            break
        log('看到完整戰鬥畫面（有人沒快速戰鬥）→ 重設一次 5 人再確認')
        info['refixed'] = True
        heal.set_encounter(False)
        heal.gui('seq', f'waitpix 20000 {heal.SIG_NO_BATTLE} 40')
        rc = fix_settings(info)
        if rc:
            return rc
    r = res['result']
    if r == 'ok':
        log(f'掛機中：{res["events"]} 次 EXP 橫幅（{res["polls"]} 次讀圖，最高紫點 {res["max_px"]}）')
        return 0
    if r == 'full_battle':
        return uikit.fail(SRC, EXIT_FULL_BATTLE, '看到完整戰鬥畫面：有人沒開快速戰鬥（或此地圖不支援）')
    if r == 'unknown':
        return uikit.fail(SRC, uikit.EXIT_UNKNOWN_SCREEN, '畫面連 3 次不認得（疑似驗證視窗），停手通知使用者（鐵則 5）')
    if r == 'enc_off':
        return uikit.fail(SRC, EXIT_ENC, '確認期間遇敵鈕被關掉了')
    return uikit.fail(SRC, EXIT_NO_EXP, f'{confirm_secs:.0f} 秒內只看到 {res["events"]} 次 EXP 橫幅（需 {EXP_NEED}）：遇敵開著但沒戰鬥 / 沒經驗？請 shot 看畫面')


# ---- 去練功（使用者 2026-10-15）----
def stop_follow(why: str) -> bool:
    """有 follow 在跑就請它結束（它持 grind.lock，不停 grind.run 會回 8）；回 True = 現在沒有 follow 在跑"""
    import follow
    pid = follow.alive_other()
    if not pid:
        return True
    log(f'follow（pid {pid}）在跑 → 先停（{why}）')
    follow.stop_other()
    return not follow.alive_other()


def note_event(msg: str) -> None:
    """寫 notes/quest-events.log 一行（「grind：…」）；失敗不丟例外"""
    try:
        import follow
        follow.EVENT_LOG.parent.mkdir(exist_ok=True)
        with open(follow.EVENT_LOG, 'a', encoding='utf-8') as f:
            f.write(f'{time.strftime("%Y-%m-%d %H:%M:%S")} grind：{msg}\n')
    except OSError:
        pass


def go(trans: int | None = None, trans_hint: int | None = None, confirm_secs: float = CONFIRM_SECS, fix: bool = True,
       do_heal: bool = False, follow_ok: bool = True) -> int:
    """「去練功」= 依當下隊長等級選點（spots.auto_spot：AUTO 表 + spots.learn 學到的門檻；轉數見 leader_trans）→ 傳送 → 5 人外掛 → 開遇敵 → EXP 確認。
    選到最高一檔（地雷區，spots.is_top）→ 確認掛機就結束，不起 follow；未滿 → 確認掛機後背景常駐 `grind.py follow --no-heal --trans N`
    （follow.ensure_running：已有同轉數的在跑就不重開），follow 換到地雷區並確認後自己結束。
    開始前若有 follow 在跑先停（它持 grind.lock）。follow 起不來只記 errlog / 警告，不影響退出碼（掛機已確認）。follow_ok=False = 不起 follow"""
    if not stop_follow('去練功：依當下等級重新選點，未滿最高點會再起新的'):
        print(f'{SRC}：follow 停不掉（60 秒內沒結束），不動作', file=sys.stderr)
        return uikit.EXIT_IN_BATTLE

    def post(info: dict) -> int:
        target, t = info.get('spot'), info.get('trans')
        lvtxt = f'{t}轉{info.get("level_num")}級'
        if spots.is_top(target):
            info['follow'] = {'action': 'none', 'why': '最高練功點'}
            log(f'{lvtxt} 在最高練功點 {target} 掛機中 → 不起 follow')
            note_event(f'去練功：{lvtxt} → {target}（最高點，不起 follow）')
            return 0
        if not follow_ok:
            info['follow'] = {'action': 'skip', 'why': '--no-follow'}
            log(f'{lvtxt} 在 {target} 掛機中；--no-follow → 不起 follow（之後要自己換點）')
            note_event(f'去練功：{lvtxt} → {target}（--no-follow）')
            return 0
        import follow
        r = follow.ensure_running(t)
        info['follow'] = r
        if r['action'] == 'fail':
            import errlog
            errlog.add(f'去練功：{target} 掛機中，但背景 follow 起不來（{r.get("why")}）；不會跟著等級換點，請手動 grind.py follow --no-heal --trans {t}', source=SRC)
            log(f'警告：follow 起不來（{r.get("why")}）')
        else:
            log(f'{lvtxt} 在 {target} 掛機中 → follow {"已在跑" if r["action"] == "running" else "已在背景啟動"}（pid {r.get("pid")}，--trans {t} --no-heal）')
        note_event(f'去練功：{lvtxt} → {target}；follow {r["action"]}（pid {r.get("pid")}）')
        return 0

    return run('start', 'auto', confirm_secs, fix, do_heal, trans=trans, trans_hint=trans_hint, post=post)


def main() -> int:
    import winenv
    winenv.enable_server()
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    sub = ap.add_subparsers(dest='cmd', required=True)
    cp = argparse.ArgumentParser(add_help=False)
    cp.add_argument('--confirm-secs', type=float, default=CONFIRM_SECS)
    cp.add_argument('--no-fix', action='store_true', help='看到完整戰鬥時不自動重設 5 人（預設會重設一次）')
    p = sub.add_parser('start', help='選點 → 傳送 → 設定 → 遇敵 → 確認（不給 --spot = 去練功：依等級選點 + 未滿最高點背景起 follow）', parents=[cp])
    p.add_argument('--spot', default='auto', help='不給 / auto = 去練功（依隊長等級選點；未滿地雷區背景起 follow）| 練功點名（見 spots.py，固定點、不起 follow）| here（不傳送）')
    p.add_argument('--trans', type=int, default=None, help='auto 用的隊長轉數（預設：背包讀隊長 → 快取；HUD 轉數位會讀錯不用）')
    p.add_argument('--no-follow', action='store_true', help='auto：未滿最高點也不起 follow')
    p.add_argument('--heal', action='store_true', help='先回村補血（點需在 heal.SPOTS）')
    sub.add_parser('ensure', help='不傳送：重查 5 人設定 + 遇敵 + 確認', parents=[cp])
    sub.add_parser('check', help='唯讀檢查')
    import follow
    follow.add_parser(sub)
    a = ap.parse_args()
    if a.cmd == 'follow':
        return follow.run(a)
    if a.cmd == 'start' and a.spot not in spots.SPOTS and a.spot not in ('auto', 'here'):
        print(f'不認得的練功點：{a.spot}（{" / ".join(spots.SPOTS)} / auto / here）')
        return uikit.EXIT_USAGE
    if a.cmd == 'start' and a.spot == 'auto':
        return go(a.trans, None, a.confirm_secs, not a.no_fix, a.heal, not a.no_follow)
    if a.cmd == 'start' and not stop_follow(f'指定 --spot {a.spot} = 固定點，不跟等級換點'):
        print(f'{SRC}：follow 停不掉（60 秒內沒結束），不動作', file=sys.stderr)
        return uikit.EXIT_IN_BATTLE
    return run(a.cmd, getattr(a, 'spot', None), getattr(a, 'confirm_secs', CONFIRM_SECS), not getattr(a, 'no_fix', False), getattr(a, 'heal', False))


if __name__ == '__main__':
    sys.exit(main())
