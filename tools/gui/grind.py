#!/usr/bin/env python3
"""開始 / 恢復練功（P5）。計畫：notes/plan-scriptify.md §3。取代 psa-grind-start 的手動截圖流程。只用標準函式庫。

用法（專案根目錄；WSL / Windows 原生指令相同）：
  uv run --no-project python tools/gui/grind.py start --spot 地雷區2|auto|here [--heal] [--confirm-secs 30] [--no-fix]
  uv run --no-project python tools/gui/grind.py ensure [--confirm-secs 30] [--no-fix]   # 不傳送：補血回來 / 任務後 / 重登後用
  uv run --no-project python tools/gui/grind.py check                                   # 唯讀：5 人快速戰鬥 / 自動戰鬥 + 遇敵鈕，不改任何東西
最後一行是 JSON（rc、耗時、各步秒數、EXP 命中數…）；同內容寫 tools/.cache/grind.json。

退出碼（共用 0 / 1 / 2 / 8 / 9 / 10 見 uikit；grind 自己 50～58）：
  0  已確認掛機中（start / ensure：30 秒內看到 ≥2 次 EXP 橫幅；check：5 人設定都對 + 遇敵開）
  50 隊伍不全且 team.form 失敗（info.team_rc 是 team 的退出碼）
  51 傳送失敗：依表預判等級不夠（不送出）、傳送後地圖沒變、或 --spot 讀不到目前地圖
  52 外掛設定失敗（info.role / ass_rc）；check 時 = 有人快速戰鬥 / 自動戰鬥是關的
  53 此地圖禁止快速戰鬥（ass 回 4 且項目是快速戰鬥）
  54 原地遇敵開不起來（check 時 = 遇敵鈕是關的）
  55 確認視窗內沒看到 ≥2 次 EXP 橫幅（遇敵開著但沒戰鬥 / 沒經驗）
  56 看到完整戰鬥畫面（有人沒快速戰鬥）；--fix（預設開）會先自動重設一次再確認，仍看到才回 56
  57 補血失敗（heal RuntimeError）
  58 當前角色切不回隊長（char.ensure 失敗，info.char_rc）

流程（與計畫 §3.3 的差異：外掛設定「先讀 5 人、只改不對的」，不是 5 人全點）：
  preflight → char.ensure(隊長) → 關遇敵 + 等戰鬥結束 → team.check / form → [start：選點 / 補血 / 傳送]
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
import heal  # noqa: E402
import screen_sigs  # noqa: E402
import spots  # noqa: E402
import team  # noqa: E402
import uikit  # noqa: E402
import walk  # noqa: E402

SRC = 'grind'
EXIT_TEAM, EXIT_TELEPORT, EXIT_ASS, EXIT_NO_FAST, EXIT_ENC, EXIT_NO_EXP, EXIT_FULL_BATTLE, EXIT_HEAL, EXIT_CHAR = 50, 51, 52, 53, 54, 55, 56, 57, 58
LEADER = 'DKBO'                       # 真名字母 O（DKB0 同義）
ROLE_ORDER = ['DKBO2', 'DKBO3', 'DKBO4', 'DKBO5', 'DKBO']      # 讀 / 改順序：隊長最後，結束時外掛面板選在隊長
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


ass.wait_cover_hook = lambda timeout=BANNER_WAIT: wait_banner_gone(timeout)     # ass.select_role 頭像被遮住時，先用 EXP 橫幅偵測等


def lap(label: str) -> None:
    """記下距上一個 lap 的秒數"""
    global _t0
    now = clock()
    _marks.append([label, round(now - _t0, 1)])
    _t0 = now


def log(msg: str) -> None:
    print(f'grind：{msg}', flush=True)


# ---- 鎖 ----
def _other_running() -> str | None:
    """另一支會搶畫面的工具在跑 → 回名稱。petwatch / grind 看鎖檔 pid；heal --watch 沒有鎖檔，Linux 掃 /proc（盡力）"""
    for name, lock in (('grind', LOCK), ('petwatch', CACHE / 'petwatch.lock')):
        try:
            pid = int(lock.read_text().strip())
        except (OSError, ValueError):
            continue
        if pid != os.getpid() and battleguard.pid_alive(pid):
            return f'{name}（pid {pid}）'
    proc = Path('/proc')
    if proc.is_dir():
        me = str(os.getpid())
        try:
            for d in proc.iterdir():
                if d.name.isdigit() and d.name != me:
                    try:
                        cmd = (d / 'cmdline').read_bytes().split(b'\0')
                    except OSError:
                        continue
                    if any(c.endswith(b'heal.py') for c in cmd) and b'--watch' in cmd:
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
        unk = unk + 1 if (c.get('state') in ('unknown', 'error') and not hit) else 0
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


def choose_spot(spot: str, trans: int, level: int, cur_map) -> tuple:
    """→ (目的點名或 None = 不傳送, 錯誤訊息或 '')。here = 不傳送；auto 依等級；已在同點 / 同檔點 = 不傳送"""
    if spot == 'here':
        return None, ''
    if spot == 'auto':
        name = spots.auto_spot(trans, level)
        if not name:
            return None, ('--spot auto 只支援 0 轉（1 轉以上門檻未實測），請明確指定 --spot <點名>' if trans else f'等級 {level} 不到可練功點')
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


def finish(rc: int, mode: str, info: dict, t_start: float) -> int:
    info.update(rc=rc, mode=mode, secs=round(clock() - t_start, 1), laps=_marks, ts=int(time.time()))
    if rc not in (uikit.EXIT_IN_BATTLE, uikit.EXIT_UNKNOWN_SCREEN, uikit.EXIT_HALT):     # 這幾種不再碰畫面
        try:
            s = heal.stat()
            info.update(map=s.get('pos'), level=s.get('level'), hpPct=s.get('hpPct'))
        except Exception:
            pass
    try:
        OUT.write_text(json.dumps(info, ensure_ascii=False), encoding='utf-8')
    except OSError:
        pass
    print(json.dumps(info, ensure_ascii=False), flush=True)
    return rc


def run(mode: str, spot: str | None = None, confirm_secs: float = CONFIRM_SECS, fix: bool = True, do_heal: bool = False,
        ignore_watchers: bool = False) -> int:
    """ignore_watchers：呼叫端本身就是 petwatch / heal --watch / netwatch（正卡在 guard 裡、不會同時動），略過它們的偵測；
    quest 的 battle.lock 仍然有效（由 uikit.preflight 擋）"""
    global _t0, ACTIVE
    t_start = _t0 = clock()
    _marks.clear()
    info: dict = {}
    other = None if ignore_watchers else _other_running()
    if other:
        print(f'{SRC}：{other} 在跑，會搶畫面 → 不動作', file=sys.stderr)
        return finish(uikit.EXIT_IN_BATTLE, mode, info, t_start)
    if not take_lock():
        return finish(uikit.EXIT_IN_BATTLE, mode, info, t_start)
    ACTIVE = True
    try:
        return finish(_run(mode, spot, confirm_secs, fix, do_heal, info), mode, info, t_start)
    except SystemExit as e:                  # netwatch.guard 停手（10）
        finish(int(e.code or 0) or uikit.EXIT_HALT, mode, info, t_start)
        raise
    finally:
        ACTIVE = False
        release_lock()


def _run(mode: str, spot, confirm_secs: float, fix: bool, do_heal: bool, info: dict) -> int:
    rc = uikit.preflight(SRC)
    if rc:
        return rc
    lap('preflight')
    if mode == 'check':
        return run_check(info)
    # 1) 當前角色 = 隊長（遇敵鈕作用在當前角色）
    rc = char.ensure(LEADER)
    lap('char.ensure')
    if rc:
        info['char_rc'] = rc
        return rc if rc in (uikit.EXIT_IN_BATTLE, uikit.EXIT_UNKNOWN_SCREEN, uikit.EXIT_HALT) else EXIT_CHAR
    # 2) 先關遇敵再設外掛（外掛面板在戰鬥中打不開）；等戰鬥結束（VS 牌消失）
    heal.set_encounter(False)
    heal.gui('seq', f'waitpix 20000 {heal.SIG_NO_BATTLE} 40')
    lap('關遇敵 + 等戰鬥結束')
    # 3) 隊伍
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
        trans, level = lv if lv else (0, 0)
        cur = read_map()
        info.update(level=s.get('level'), cur_map=cur)
        if spot == 'auto' and not lv:
            return uikit.fail(SRC, uikit.EXIT_USAGE, '讀不到隊長等級，無法 auto 選點')
        if spot not in ('here', 'auto') and not lv:
            log('警告：讀不到隊長等級，不預判門檻，直接送出傳送')
            lv_known = False
        else:
            lv_known = True
        name, err = choose_spot(spot, trans if lv_known else 1, level, cur)
        if err:
            return uikit.fail(SRC, uikit.EXIT_USAGE if 'auto' in err or '不到可練功點' in err else EXIT_TELEPORT, err)
        target = name or spots.spot_of_map(cur) or spot
        info['spot'] = target
        if do_heal or (isinstance(s.get('hpPct'), int) and s['hpPct'] < 40):
            if target in heal.SPOTS:
                try:
                    heal.heal_trip(target)
                except RuntimeError as e:
                    return uikit.fail(SRC, EXIT_HEAL, f'補血失敗：{e}')
                info['healed'] = True
                heal.set_encounter(False)                       # heal_trip 結束會開遇敵；外掛設定前再關
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
    p = sub.add_parser('start', help='選點 → 傳送 → 設定 → 遇敵 → 確認', parents=[cp])
    p.add_argument('--spot', required=True, help='練功點名（見 spots.py）| auto（依等級，僅 0 轉）| here（不傳送）')
    p.add_argument('--heal', action='store_true', help='先回村補血（點需在 heal.SPOTS）')
    sub.add_parser('ensure', help='不傳送：重查 5 人設定 + 遇敵 + 確認', parents=[cp])
    sub.add_parser('check', help='唯讀檢查')
    a = ap.parse_args()
    if a.cmd == 'start' and a.spot not in spots.SPOTS and a.spot not in ('auto', 'here'):
        print(f'不認得的練功點：{a.spot}（{" / ".join(spots.SPOTS)} / auto / here）')
        return uikit.EXIT_USAGE
    return run(a.cmd, getattr(a, 'spot', None), getattr(a, 'confirm_secs', CONFIRM_SECS), not getattr(a, 'no_fix', False), getattr(a, 'heal', False))


if __name__ == '__main__':
    sys.exit(main())
