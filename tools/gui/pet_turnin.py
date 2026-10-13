#!/usr/bin/env python3
"""交寵物任務（逐人，會跳「選擇」寵物視窗的那種）：恐龍博士（2016）步 1（魯尼帖斯）、步 2（貝魯卡）。

2026-10-12 手動做完 DKBO 後寫成（DKBO2～5 起用本腳本）。只用標準函式庫。

用法（專案根目錄；WSL / Windows 原生相同；角色名 DKBO / DKB0 都收）：
  uv run --no-project python tools/gui/pet_turnin.py dino DKBO2 [DKBO3 ...] [--dry-run] [--no-switch] [--steps 1,2]
  最後一行 JSON {"ok","rc","roles":{角色:{"step1":bool,"step2":bool}}}

流程（每人）：char.ensure（切換面板換成該角色；--no-switch 不切，當前角色就是要交的人）→ 點追蹤列表「恐龍博士」（自動走到 NPC 開對話）→
  對話框左鈕（「恐龍博士」→「完成」；步 2 直接是「完成」）→「選擇」視窗：OCR 讀每張寵物卡的名字，**依名字**點卡（順序每人不同），
  卡片變黃底才按「確定」706,614；視窗消失 = 交出。寵物被收走由呼叫端 pet.py list 驗。
前提（呼叫端負責）：隊伍已解散（逐人交）、任務寵都在寵物欄、等級夠（魯尼帖斯 ≥18、貝魯卡 ≥30）、任務寵都已「等待」（pet.py rest-all）、
  已接任務（questrun run 2016 步 1、2 是 manual 會停下）。
**不切回 DKBO**：全部交完由呼叫端 char.py ensure DKBO。

退出碼（共用 0 / 1 / 2 / 8 / 9 / 10 見 uikit；自己 120～125）：
  120 切換角色失敗（char 的退出碼在 roles[角色].char_rc）
  121 追蹤列表找不到「恐龍博士」（任務已完成 / 沒接 / 被擋）。2026-10-13 起：剛切換角色時追蹤列表還沒載入（讀到 0 列）不算沒找到，
      等 TRACK_RETRY_S 秒重掃、最多等 TRACK_LOAD_MAX_S 秒；列表有內容但沒有該任務要連續 TRACK_MISS_MAX 次才判 121
      （實機：DKBO2～5 第一次跑都 121、重跑就過 —— 追蹤列表沒載入）
  122 一直等不到對話框 / 選擇視窗
  123 選擇視窗裡找不到指定名字的寵物卡（OCR 讀不到 / 寵物不在寵物欄）→ 零點擊確定
  124 點了卡片但沒變黃底（不按確定）
  125 按了確定後視窗沒消失
"""
import argparse
import difflib
import json
import re
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
import charname  # noqa: E402
import uikit  # noqa: E402

SRC = 'pet_turnin'
EXIT_CHAR, EXIT_TRACK, EXIT_WAIT, EXIT_CARD, EXIT_SELECT, EXIT_CONFIRM = 120, 121, 122, 123, 124, 125

TASK_TITLE = '恐龍博士'
STEPS = {1: '魯尼帖斯', 2: '貝魯卡'}
KNOWN_PETS = ['朵拉比斯', '魯尼帖斯', '貝魯卡']       # 本帳號寵物欄可能出現的名字（OCR 後 snap）

# ---- 版面（2880×1659 截圖座標；2026-10-12 實測）----
DIALOG_LEFT_BTN = (948, 461)            # 對話框左鈕（恐龍博士 / 完成）
TITLE_BOX = (590, 195, 240, 45)         # 選擇視窗標題「選擇」（米白字深底：-Dark 0 不二值化才讀得到）
CARDS_BOX = (570, 305, 300, 245)        # 寵物卡名字（深棕字；綠色等級字被二值化丟掉）
CARD_CLICK_X, CARD_CLICK_DY = 700, 10   # 點卡：x、名字行 y + DY
CARD_PROBE_X = 900                      # 卡片底色探點 x（y = 點卡 y）
CONFIRM_BTN = (706, 614)                # 確定
LIST_DRAG = (700, 520, 700, 400)        # 卡片清單往下捲
RECOGNIZE_CUTOFF = 0.6
TRACK_RETRY_S = 4.0                     # 追蹤列表沒找到 → 隔這麼久重掃（舊版 12 秒才掃一次、第一次沒找到就 121）
TRACK_MISS_MAX = 3                      # 列表有內容但沒有該任務：連續這麼多次才判 121
TRACK_LOAD_MAX_S = 40.0                 # 列表一直讀到 0 列（還沒載入）最多等這麼久，之後也判 121


def norm(t: str) -> str:
    return re.sub(r'\s+', '', t or '')


def snap_name(text: str, names=KNOWN_PETS, cutoff: float = RECOGNIZE_CUTOFF):
    """OCR 文字 → 已知寵物名（最像的一個；差太多 None）。純函式"""
    t = norm(text)
    if not t:
        return None
    best, score = None, 0.0
    for n in names:
        r = difflib.SequenceMatcher(None, t, n).ratio()
        if n in t:
            r = max(r, 0.95)
        if r > score:
            best, score = n, r
    return best if score >= cutoff else None


def pick_card(lines: list, want: str):
    """OCR 行 [(文字, x, y)] → 名字 snap 後 == want 的那一行 (x, y)；沒有 / 多於一行都 None（多行 = 同名多張，不猜）。純函式"""
    hits = []
    for t, x, y in lines:                      # 兩個放大倍數各讀一次會重複：y 相差 <= 15 視為同一張卡
        if snap_name(t) == want and not any(abs(y - hy) <= 15 for _, hy in hits):
            hits.append((x, y))
    return hits[0] if len(hits) == 1 else None


def is_yellow(rgb) -> bool:
    """被選中的卡片底色（黃）：R、G 高、B 明顯低（沒選中是米白 B>190）。純函式"""
    r, g, b = rgb
    return r > 200 and g > 180 and b < 170


def ocr_box(box, *opts) -> list:
    import subprocess
    import winenv
    try:
        r = winenv.run_ps('ocr.ps1', *map(str, box), *map(str, opts))
        d = json.loads((r.stdout.strip().splitlines() or [''])[-1])
    except (subprocess.TimeoutExpired, ValueError):
        return []
    return [(ln['text'], ln.get('x', 0), ln.get('y', 0)) for ln in d.get('lines', [])] if d.get('ok') else []


def log(msg: str) -> None:
    print(f'{time.strftime("%H:%M:%S")} {SRC}：{msg}', flush=True)


def select_window_open() -> bool:
    txt = norm(''.join(t for t, _, _ in ocr_box(TITLE_BOX, '-Zooms', '2,3', '-Dark', 0)))
    return '選擇' in txt or '选择' in txt


def pick_in_window(want: str, dry_run: bool = False) -> int:
    """選擇視窗已開：依名字點卡 → 變黃才按確定 → 視窗消失。回退出碼"""
    lines, pt = [], None
    for attempt in range(3):
        lines = ocr_box(CARDS_BOX, '-Zooms', '2,3', '-Dark', 150)
        pt = pick_card(lines, want)
        if pt:
            break
        if attempt < 2:
            uikit.gui('drag', *map(str, LIST_DRAG), note='選擇視窗：清單往下捲找卡')
            uikit.sleep(0.8)
    if not pt:
        log(f'選擇視窗找不到「{want}」（讀到 {[t for t, _, _ in lines]}），不點確定')
        uikit.snap('pet-turnin-nocard')
        return EXIT_CARD
    cy = pt[1] + CARD_CLICK_DY
    log(f'選擇視窗：「{want}」卡在 y={pt[1]}（讀到 {[t for t, _, _ in lines]}）')
    if dry_run:
        return 0
    uikit.gui('click', str(CARD_CLICK_X), str(cy), note=f'選擇視窗：點「{want}」卡')
    uikit.sleep(0.8)
    cols = uikit.px([(CARD_PROBE_X, cy)])
    if not cols or not is_yellow(cols[0]):
        log(f'點卡後底色 {cols} 不是黃色（沒選中），不按確定')
        uikit.snap('pet-turnin-notsel')
        return EXIT_SELECT
    uikit.gui('click', str(CONFIRM_BTN[0]), str(CONFIRM_BTN[1]), note='選擇視窗：確定')
    uikit.sleep(2.0)
    if select_window_open():
        log('按確定後選擇視窗還在')
        uikit.snap('pet-turnin-confirm')
        return EXIT_CONFIRM
    return 0


def track_miss_action(misses: int, rows_n, waited_s: float) -> str:
    """追蹤列表掃完沒找到任務時怎麼辦（純函式）：rows_n = 最後一頁讀到幾列標題（quest._PAGE_ROWS_N；0 / None = 列表還沒載入）。
    → 'wait'（還沒載入、不計次）/ 'retry'（有內容但沒找到，計次未滿）/ 'fail'（連續 TRACK_MISS_MAX 次、或等載入超過 TRACK_LOAD_MAX_S）"""
    if not rows_n:
        return 'fail' if waited_s >= TRACK_LOAD_MAX_S else 'wait'
    return 'fail' if misses >= TRACK_MISS_MAX else 'retry'


def turnin_step(want: str, dry_run: bool = False) -> int:
    """一步：點追蹤 → 對話 → 選擇視窗交 want。0 = 交出。
    追蹤列表剛切完角色可能還沒載入：沒找到不馬上判 121，見 track_miss_action"""
    import quest
    t0 = time.time()
    t_end = t0 + 90
    tracked_at = 0.0
    retry_at = 0.0
    misses = 0
    while time.time() < t_end:
        if select_window_open():
            return pick_in_window(want, dry_run)
        st = quest.read_screen().get('state')
        if st == 'dialog':
            if dry_run:
                log('對話框開著（dry-run 不點）')
                return 0
            uikit.gui('click', str(DIALOG_LEFT_BTN[0]), str(DIALOG_LEFT_BTN[1]), note='對話框左鈕（恐龍博士 / 完成）')
            uikit.sleep(1.2)
            continue
        if st == 'idle' and time.time() - tracked_at > 12 and time.time() >= retry_at:
            found = quest.track_task(TASK_TITLE, click=not dry_run)
            tracked_at = time.time()
            if found is False:
                rows_n = getattr(quest, '_PAGE_ROWS_N', None)
                misses += 1 if rows_n else 0
                act = track_miss_action(misses, rows_n, time.time() - t0)
                if act == 'fail':
                    log(f'追蹤列表沒有「{TASK_TITLE}」（{"連續 %d 次" % misses if rows_n else "列表一直是空的 / 沒載入"}）')
                    uikit.snap('pet-turnin-notrack')
                    return EXIT_TRACK
                log(f'追蹤列表沒找到「{TASK_TITLE}」（讀到 {rows_n or 0} 列，{"列表還沒載入" if act == "wait" else f"第 {misses} 次"}）→ {TRACK_RETRY_S:.0f} 秒後重掃')
                tracked_at = 0.0
                retry_at = time.time() + TRACK_RETRY_S
                continue
            misses = 0
            if dry_run:
                return 0
            uikit.sleep(2.0)
            continue
        uikit.sleep(1.0)
    log('等不到對話框 / 選擇視窗')
    uikit.snap('pet-turnin-wait')
    return EXIT_WAIT


def run(roles: list, steps=(1, 2), switch: bool = True, dry_run: bool = False) -> tuple:
    rc0 = uikit.preflight(SRC)
    if rc0:
        return rc0, {}
    import char
    res = {}
    for role in roles:
        canon = charname.canon(role)
        res[canon] = {}
        if switch and not dry_run:
            rc = char.ensure(canon)
            if rc:
                res[canon]['char_rc'] = rc
                return EXIT_CHAR, res
        for s in steps:
            log(f'{canon} 步 {s}：交 {STEPS[s]}')
            rc = turnin_step(STEPS[s], dry_run)
            res[canon][f'step{s}'] = rc == 0
            if rc:
                return rc, res
    return 0, res


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('kind', choices=['dino'])
    ap.add_argument('roles', nargs='+')
    ap.add_argument('--dry-run', action='store_true')
    ap.add_argument('--no-switch', action='store_true')
    ap.add_argument('--steps', default='1,2')
    a = ap.parse_args(argv)
    try:
        import winenv
        winenv.enable_server()
    except Exception:
        pass
    steps = tuple(int(x) for x in a.steps.split(',') if x.strip())
    rc, res = run(a.roles, steps, switch=not a.no_switch, dry_run=a.dry_run)
    print(json.dumps({'ok': rc == 0, 'rc': rc, 'roles': res}, ensure_ascii=False))
    return rc


if __name__ == '__main__':
    sys.exit(main())
