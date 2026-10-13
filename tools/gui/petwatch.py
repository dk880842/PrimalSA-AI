#!/usr/bin/env python3
"""監測 5 個角色的練功寵（預設「金布伊」）等級，到門檻就把該角色的鎖定戰寵換回原戰寵（預設「朵拉比斯」）。加 --heal 才兼做 heal.py --watch 的血量檢查。

用法（專案根目錄；一次只能跑一支，同時也不要跑 heal.py --watch，兩邊會搶畫面）：
  uv run --no-project python tools/gui/petwatch.py                     # 常駐：每 30 秒掃一輪，≥ 77 級就換回；5 人都換完就結束
  uv run --no-project python tools/gui/petwatch.py --once              # 只掃一輪（只讀，不換、不補血；加 --apply 才會換）
  uv run --no-project python tools/gui/petwatch.py --interval 30 --target-level 77 --spot 地雷區
  uv run --no-project python tools/gui/petwatch.py --pet 金布伊 --level 77 --back 朵拉比斯 --pet-slot 3 --back-slot 2   # 全部參數（以上是預設值）
  --pet / --level（= --target-level）：被監測的練功寵名與換回門檻；--back：換回的戰寵名；--pet-slot / --back-slot：
  兩隻在寵物欄的第幾格（1～4，預設 練功寵 3、戰寵 2；轉生後 布拉奇多斯騎寵第 1 格、朵拉比斯第 2 格；5 個角色排列要一樣）。
  換回時外掛下拉項目 y = 419 + 42×(戰寵格 − 1)（下拉順序 = 寵物欄順序）；寵物名只比對前 2 字（OCR 容錯）
  uv run --no-project python tools/gui/petwatch.py --heal              # 兼做補血檢查（HP < --hp% / MP < --mp% 連 2 次 → heal_trip 補血再回 --spot）
  補血預設**關**（2026-10-13 起；使用者規定練功不自動補血，psa-grind-no-auto-heal）；--no-heal 保留相容（= 預設，no-op）

「鎖定戰寵」= 外掛 ASS →「一般設置」→ 鎖定戰寵（勾選框 + 下拉選寵物），鎖定後寵物面板的出戰 / 休息會被擋
（「你已鎖定戰寵，請取消後再操作」）。所以換寵物流程是：取消鎖定 → 寵物面板「出戰」→ 外掛下拉選寵物 → 重新勾選。
戰鬥中寵物面板也不能換（「戰鬥中禁止當前操作」）→ 換之前先關原地遇敵、等 VS 牌消失，換完再開回來。
座標只量過 2880×1659；見 .claude/skills/psa-game-ui/ui/pet.md。讀等級用 ocr.ps1 -Light（白色數字）；
單一位數（1～9）Windows OCR 讀不出來 → 回 None，記錄但不動作（讀得到 2 位數才會判斷）。
只透過 gui.ps1 / ocr.ps1 / stat.ps1 操作畫面；不碰放生 / 回爐 / 垃圾桶（座標完全不會點到）。
"""
import argparse
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

import actlog
import charstate
import errlog
import heal
import layout
import netwatch
import watchstate
import winenv
from walk import gui, log

CACHE = Path(__file__).resolve().parents[1] / '.cache'
STATE = CACHE / 'petwatch.json'
LOCK = CACHE / 'petwatch.lock'

CHARS = ['DKBO', 'DKBO2', 'DKBO3', 'DKBO4', 'DKBO5']   # 真名字母 O；舊 petwatch.json 的 DKB0… 在 load_state 轉成真名
AVATAR_Y = {'DKBO': 195, 'DKBO2': 322, 'DKBO3': 450, 'DKBO4': 580, 'DKBO5': 700}   # 寵物面板左欄頭像 x=83
ASS_RADIO = {'DKBO': (137, 151), 'DKBO2': (298, 151), 'DKBO3': (461, 151), 'DKBO4': (137, 204), 'DKBO5': (298, 204)}
PET_BTN, ASS_BTN, ASS_TAB = (318, 80), (1300, 760), (850, 212)
SLOT_Y = [200, 322, 445, 567]                      # 寵物欄 1～4 格（x=250）
SLOT_X = 250
BTN_FIGHT = (390, 702)                             # 出戰
LOCK_BOX, LOCK_DROP = (656, 377), (1285, 377)      # 外掛一般設置：鎖定戰寵 勾選框 / 下拉鈕
LOCK_ITEM_X, LOCK_ITEM_Y0, LOCK_ITEM_DY = 1050, 419, 42   # 外掛鎖定戰寵下拉項目（第 n 格 y = Y0 + DY×(n−1)，順序 = 寵物欄順序，本帳號實測 419 / 461 / 503 / 545）
SIG_PET = '1310,108,197,71,49'                     # 寵物面板右上紅 ✕
SIG_ASS = '1318,90,195,127,8'                      # 外掛面板右上橘 ✕
NAME_BOX = (430, 160, 200, 45)                     # 寵物面板選中寵物的名字
LVL_BOXES = [(245, y, 60, 40) for y in (210, 332, 455, 577)]   # 每格右下角等級數字（白字）
LEVEL_BOX = (470, 620, 130, 36)                  # 選中寵物模型下方的「0轉N」
LOCK_NAME_BOX = (880, 358, 300, 38)                # 外掛鎖定戰寵欄目前顯示的寵物名


VERIFY_NAME = False
SLOT_CACHE: dict = {}                              # 角色 → 練功寵所在格（0 起算）
# 可由命令列改：練功寵名 / 所在格（1 起算）、換回的戰寵名 / 所在格。預設 = 轉生後的狀態（金布伊第 3 格、朵拉比斯第 2 格）
PET_NAME, PET_SLOT = '金布伊', 3
BACK_NAME, BACK_SLOT = '朵拉比斯', 2


def configure(pet: str = '金布伊', pet_slot: int = 3, back: str = '朵拉比斯', back_slot: int = 2) -> None:
    """設定練功寵 / 戰寵（格號 1～4）；格號超出範圍丟 ValueError"""
    global PET_NAME, PET_SLOT, BACK_NAME, BACK_SLOT
    for n in (pet_slot, back_slot):
        if not 1 <= n <= len(SLOT_Y):
            raise ValueError(f'寵物格 {n} 超出 1～{len(SLOT_Y)}')
    if pet_slot == back_slot:
        raise ValueError('練功寵與戰寵不能同一格')
    if not pet.strip() or not back.strip():
        raise ValueError('寵物名不能空白')
    PET_NAME, PET_SLOT, BACK_NAME, BACK_SLOT = pet.strip(), pet_slot, back.strip(), back_slot
    SLOT_CACHE.clear()


def name_key(name: str) -> str:
    """OCR 比對用的寵物名關鍵字：前 2 字（金布伊 → 金布；朵拉比斯 → 朵拉；OCR 常掉字 / 錯字）"""
    return name[:2]


def lock_item_xy(slot: int) -> tuple:
    """外掛鎖定戰寵下拉：寵物欄第 slot 格（1 起算）的項目座標"""
    return (LOCK_ITEM_X, LOCK_ITEM_Y0 + LOCK_ITEM_DY * (slot - 1))


def ocr(box, *opts) -> list:
    try:
        r = winenv.run_ps('ocr.ps1', *map(str, box), *map(str, opts))
    except subprocess.TimeoutExpired:
        return []          # 讀圖逾時視同讀不到，呼叫端進下一輪
    line = (r.stdout.strip().splitlines() or [''])[-1]
    try:
        d = json.loads(line)
    except json.JSONDecodeError:
        return []
    return [l['text'] for l in d.get('lines', [])] if d.get('ok') else []


def ocr_name(box=NAME_BOX) -> str:
    """寵物名。選中寵物的名字框先用 petmatch 整塊圖樣板（同名 IoU 1.000，約 0.2 s）；沒樣板才 OCR：
    -Dark 0 -Zooms 2,3,4（不二值化直接放大，P-I5 實測 6/6 精確；舊的 -Dark 120 約一半讀成空字串或少字）→ 沒結果再退回 -Dark 120"""
    if tuple(box) == NAME_BOX:
        try:
            import petmatch
            rows, _ = petmatch.grab([petmatch.BOX_NAME + ('name',)])
            if rows:
                label, _, _ = petmatch.match_whole('name', rows[0], petmatch.load_tpl())
                if label:
                    return label
        except Exception:
            pass
    for opts in (('-Dark', 0, '-Zooms', '2,3,4'), ('-Dark', 120, '-Zooms', '2,3')):
        t = ocr(box, *opts)
        if t:
            return t[0]
    return ''


def ocr_level(slot: int | None = None) -> int | None:
    """讀「目前選中寵物」模型下方黃字「0轉70」的等級。順序：petmatch 單字樣板（0.1 s、不會把 128 讀成 28）→
    pet.ocr_level_consensus（三組 OCR 設定共識）→ 舊的單組重試（-Dark 90 / 120 / 70；單組會把 128 讀成 28，只當最後手段）。
    寵物格右下白色數字單位數 OCR 讀不出來，所以不用它（slot 參數保留給呼叫端相容，沒用到）。"""
    try:
        import petmatch
        rows, _ = petmatch.grab([petmatch.BOX_LVL + ('lvl',)])
        if rows:
            v = petmatch.read_level(rows[0], petmatch.load_tpl())
            if v is not None:
                return v
        import pet
        v = pet.ocr_level_consensus()
        if v is not None:
            return v
    except Exception:
        pass
    for dark, zooms in ((90, '2'), (120, '2,3'), (70, '2,3,4')):   # 同一張畫面換門檻 / 倍數重試（實測單次偶爾讀不到）
        for t in ocr(LEVEL_BOX, '-Dark', dark, '-Zooms', zooms):
            m = re.search(r'轉(\d{1,3})', t)
            if m:
                return int(m[1])
    return None


def seq(steps: str) -> str:
    return gui('seq', steps)


def ok_last(out: str) -> bool:
    lines = [l for l in out.splitlines() if l.startswith(('ok', 'timeout'))]
    return bool(lines) and lines[-1].startswith('ok')


def open_pet() -> bool:
    out = seq(f'key {{ESC}}; wait 300; click {PET_BTN[0]} {PET_BTN[1]}; waitpix 1500 {SIG_PET}')
    return ok_last(out)


def open_ass() -> bool:
    out = seq(f'key {{ESC}}; wait 300; click {ASS_BTN[0]} {ASS_BTN[1]}; waitpix 1500 {SIG_ASS}; '
              f'ifok click {ASS_TAB[0]} {ASS_TAB[1]}; ifok wait 400')
    return ok_last(out.replace('ok', 'ok', 1)) or 'ok' in out.split()


def close_panel() -> None:
    gui('key', '{ESC}')


def find_slot(want: str, max_slot: int = 4) -> int | None:
    """目前選的角色：逐格點開寵物欄，用名字找 want（回傳 0 起算的格號）。順便把該格選起來。"""
    for i in range(max_slot):
        seq(f'click {SLOT_X} {SLOT_Y[i]}; wait 350')
        if want in ocr_name():
            return i
    return None


def lock_checked() -> bool:
    """鎖定戰寵勾選框中心是黑色（勾）還是白色（沒勾）"""
    px = heal.pixels([LOCK_BOX])[0]
    return max(px) < 100


# ---------------- 掃描 ----------------
def scan(done: set) -> dict | None:
    """開寵物面板 → 逐角色讀練功寵等級。回傳 {角色: 等級 / None}；面板開不起來回 None（跳過這輪）"""
    if not open_pet():
        close_panel()
        return None
    res = {}
    for c in CHARS:
        if c in done:
            continue
        seq(f'click 83 {AVATAR_Y[c]}; wait 500')
        # 練功寵固定在 PET_SLOT 格（5 個角色排列相同）；名字 OCR 又慢又不穩，只在 --verify-name 時才核對
        slot = SLOT_CACHE.get(c, PET_SLOT - 1)
        seq(f'click {SLOT_X} {SLOT_Y[slot]}; wait 500')
        if VERIFY_NAME and name_key(PET_NAME) not in ocr_name():
            log(f'{c}：第 {slot + 1} 格名字不是{PET_NAME}（OCR：{ocr_name()!r}）')
        res[c] = ocr_level()
    close_panel()
    return res


# ---------------- 換回原戰寵 ----------------
def swap_back(c: str) -> bool:
    """c 的鎖定戰寵 練功寵 → BACK_NAME（預設朵拉比斯）。呼叫前要先關原地遇敵、等戰鬥結束。成功回 True。"""
    x, y = ASS_RADIO[c]
    # 1. 外掛：取消鎖定戰寵
    if not open_ass():
        log(f'{c}：外掛面板開不起來，跳過')
        close_panel()
        return False
    seq(f'click {x} {y}; wait 500')
    if lock_checked():
        seq(f'click {LOCK_BOX[0]} {LOCK_BOX[1]}; wait 400')
    if lock_checked():
        log(f'{c}：取消鎖定失敗，跳過')
        close_panel()
        return False
    # 2. 寵物面板：戰寵 出戰
    if not open_pet():
        log(f'{c}：寵物面板開不起來，跳過（鎖定已被取消！之後要重掃補回）')
        close_panel()
        return False
    seq(f'click 83 {AVATAR_Y[c]}; wait 500')
    seq(f'click {SLOT_X} {SLOT_Y[BACK_SLOT - 1]}; wait 400')      # 戰寵在 BACK_SLOT 格；用名字核對（讀兩次，OCR 偶爾空白）
    if name_key(BACK_NAME) not in ocr_name() and name_key(BACK_NAME) not in ocr_name():
        log(f'{c}：第 {BACK_SLOT} 格不像{BACK_NAME}，不動作')
        close_panel()
        return False
    seq(f'click {BTN_FIGHT[0]} {BTN_FIGHT[1]}; wait 700')
    # 3. 外掛：下拉選戰寵 + 重新勾選
    if not open_ass():
        log(f'{c}：外掛面板開不起來（出戰已換、尚未重新鎖定）')
        close_panel()
        return False
    seq(f'click {x} {y}; wait 500; click {LOCK_DROP[0]} {LOCK_DROP[1]}; wait 400; '
        f'click {lock_item_xy(BACK_SLOT)[0]} {lock_item_xy(BACK_SLOT)[1]}; wait 400')
    if not lock_checked():
        seq(f'click {LOCK_BOX[0]} {LOCK_BOX[1]}; wait 400')
    ok = lock_checked() and name_key(BACK_NAME) in ocr_name(LOCK_NAME_BOX)
    gui('shot', winenv.to_windows(CACHE / f'petwatch_{c}.png'))
    close_panel()
    return ok


def battle_free(timeout_ms: int = 20000) -> bool:
    return ok_last(seq(f'waitpix {timeout_ms} {heal.SIG_NO_BATTLE} 40'))


# ---------------- 狀態 / 互斥 ----------------
STATE_MAX_AGE_S = 3 * 3600


def load_state() -> dict:
    try:
        if time.time() - STATE.stat().st_mtime > STATE_MAX_AGE_S:      # 昨天的「已完成」不能擋今天的練功寵監測（2026-10-12 實機：舊 done 讓 petwatch 0 秒結束）
            return {'done': [], 'levels': {}}
        st = json.loads(STATE.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return {'done': [], 'levels': {}}
    # 舊紀錄的角色名是 DKB0…（數字 0）：O / 0 視為相同，轉成真名
    st['done'] = [charstate.display(c) for c in st.get('done', [])]
    st['levels'] = {charstate.display(k): v for k, v in st.get('levels', {}).items()}
    return st


def save_state(st: dict) -> None:
    CACHE.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(st, ensure_ascii=False), encoding='utf-8')


def take_lock() -> bool:
    """鎖檔：內容 = PID；PID 還活著就拒絕（WSL 用 /proc、Windows 用 tasklist 判斷）"""
    try:
        pid = int(LOCK.read_text().strip())
        alive = Path(f'/proc/{pid}').exists() if os.name != 'nt' else str(pid) in os.popen(f'tasklist /FI "PID eq {pid}"').read()
        if alive and pid != os.getpid():
            return False
    except (OSError, ValueError):
        pass
    CACHE.mkdir(parents=True, exist_ok=True)
    LOCK.write_text(str(os.getpid()))
    return True


def heal_on(a) -> bool:
    """純函式：要不要做補血檢查 —— 只有明確給 --heal 才做（--no-heal 優先、--once 不做）"""
    return bool(getattr(a, 'heal', False)) and not getattr(a, 'no_heal', False) and not getattr(a, 'once', False)


def main(argv=None, dry_args: bool = False):
    """dry_args=True：只解析參數回 Namespace（測試用，不碰遊戲）"""
    if not dry_args:
        winenv.enable_server()   # 長程序：WSL 預設啟用常駐 server（Windows 原生需 PSA_GUI_SERVER=1；=0 關閉）
    ap = argparse.ArgumentParser(description='監測練功寵（預設金布伊）等級，到門檻換回戰寵（預設朵拉比斯）')
    ap.add_argument('--once', action='store_true', help='只掃一輪（預設只讀；加 --apply 才換）')
    ap.add_argument('--apply', action='store_true', help='--once 時也執行換回')
    ap.add_argument('--interval', type=int, default=30, help='掃描間隔秒數（預設 30）')
    ap.add_argument('--target-level', '--level', dest='target_level', type=int, default=77, help='練功寵 ≥ 這個等級就換回（預設 77）')
    ap.add_argument('--pet', default='金布伊', help='被監測的練功寵名（預設 金布伊）')
    ap.add_argument('--pet-slot', type=int, default=3, help='練功寵在寵物欄第幾格 1～4（預設 3）')
    ap.add_argument('--back', default='朵拉比斯', help='換回的戰寵名（預設 朵拉比斯；轉生前的舊流程是 迪基格斯）')
    ap.add_argument('--back-slot', type=int, default=2, help='戰寵在寵物欄第幾格 1～4（預設 2；舊流程迪基格斯是第 1 格）')
    ap.add_argument('--spot', default='地雷區', choices=heal.SPOTS, help='補血後回去的練功點')
    ap.add_argument('--heal', action='store_true', help='兼做補血檢查（預設關：練功不自動補血）')
    ap.add_argument('--no-heal', action='store_true', help='相容舊指令：= 預設（不補血），no-op')
    ap.add_argument('--heal-every', type=int, default=15, help='補血檢查間隔秒數（預設 15）')
    ap.add_argument('--hp', type=int, default=40)
    ap.add_argument('--mp', type=int, default=20)
    ap.add_argument('--for', dest='duration', type=int, default=0, help='跑幾秒後自己結束（測試用）')
    a = ap.parse_args(argv)
    a.no_heal = not heal_on(a)
    if dry_args:
        return a
    try:
        configure(a.pet, a.pet_slot, a.back, a.back_slot)
    except ValueError as e:
        print(f'petwatch：參數錯誤：{e}', file=sys.stderr)
        return 2
    if layout.current() not in ('2880x1659',):
        log(f'petwatch 只量過 2880×1659，目前 {layout.current()}')
        return 2
    if not take_lock():
        log('已有另一支 petwatch 在跑（tools/.cache/petwatch.lock），結束')
        return 3
    st = load_state()
    done = set(st['done'])
    end = time.time() + a.duration if a.duration else None
    next_scan = 0.0
    vg = watchstate.VerifyGuard('petwatch', log=log)   # watch 標出疑似驗證視窗 → 暫停動作，最多 10 分鐘（超過停止、寫 errlog，不自動恢復）
    log(f'開始：每 {a.interval} 秒掃一輪，{PET_NAME} ≥ {a.target_level} 級就換回{BACK_NAME}（第 {BACK_SLOT} 格）；已完成 {sorted(done) or "無"}')
    try:
        while len(done) < len(CHARS) and (end is None or time.time() < end):
            if vg.check() == 'timeout':
                return heal.EXIT_VERIFY
            now = time.time()
            if netwatch.guard('petwatch')['status'] == 'reconnected':
                next_scan = 0.0                      # 重連後馬上重掃一輪（netwatch 已恢復原地遇敵、檢查隊伍）
            if not a.no_heal and not a.once:
                hits = 0
                last_ts = None
                for i in range(2):
                    s, last_ts = heal.read_vitals(last_ts)     # watch 活著 = 讀 state.hud；否則現場 stat
                    r = heal.low(s, a.hp, a.mp)
                    if not r:
                        break
                    hits += 1
                    if hits < 2 and last_ts is None:
                        time.sleep(3)
                if hits >= 2:
                    log(f'血 / 魔太低（HP {s.get("hpPct")}%，MP {s.get("mpPct")}%），回村補血')
                    try:
                        heal.heal_trip(a.spot)
                    except RuntimeError as e:
                        i = errlog.add(f'petwatch 補血失敗：{e}', source='petwatch')
                        log(f'補血流程失敗：{e}（errlog #{i}）；停止，請人工處理')
                        return 1
            if not a.once and not heal.encounter_on():
                log('原地遇敵沒開，重新開啟')
                try:
                    heal.set_encounter(True)
                except RuntimeError as e:
                    errlog.add(f'petwatch 開原地遇敵失敗：{e}', source='petwatch')
            if time.time() >= next_scan:
                res = scan(done)
                next_scan = time.time() + a.interval
                if res is None:
                    log('寵物面板開不起來（戰鬥 / 對話中？），跳過這輪')
                else:
                    log(f'{PET_NAME}等級：' + '、'.join(f'{c} {v if v is not None else "?"}' for c, v in res.items()))
                    st['levels'] = {**st.get('levels', {}), **{c: v for c, v in res.items() if v is not None}}
                    st['ts'] = time.strftime('%H:%M:%S')
                    save_state(st)
                    due = [c for c, v in res.items() if v is not None and v >= a.target_level]
                    if due and (not a.once or a.apply):
                        was_on = heal.encounter_on()
                        if was_on:
                            heal.set_encounter(False)
                        if not battle_free():
                            log('等不到戰鬥結束，這輪不換')
                        else:
                            for c in due:
                                if swap_back(c):
                                    done.add(c)
                                    st['done'] = sorted(done)
                                    save_state(st)
                                    log(f'{c}：鎖定戰寵已換回{BACK_NAME}（{PET_NAME} {res[c]} 級）')
                                else:
                                    i = errlog.add(f'petwatch：{c} 換回{BACK_NAME}失敗（見 tools/.cache/petwatch_{c}.png）', source='petwatch')
                        if was_on or not a.once:
                            heal.set_encounter(True)
            if a.once:
                break
            time.sleep(max(1, min(a.heal_every if not a.no_heal else a.interval, next_scan - time.time())))
    except KeyboardInterrupt:
        log('Ctrl+C，結束')
    finally:
        try:
            LOCK.unlink()
        except OSError:
            pass
        gui('end')
    if len(done) == len(CHARS):
        log(f'5 個角色都已換回{BACK_NAME}，結束')
    return 0


if __name__ == '__main__':
    sys.exit(main())
