#!/usr/bin/env python3
"""監測 5 個角色的練功寵（預設「金布伊」）等級，到門檻就把該角色的出戰 / 鎖定戰寵換回原戰寵（預設「朵拉比斯」）。加 --heal 才兼做 heal.py --watch 的血量檢查。

用法（專案根目錄；一次只能跑一支，同時也不要跑 heal.py --watch，兩邊會搶畫面）：
  uv run --no-project python tools/gui/petwatch.py                     # 常駐：每 30 秒掃一輪，連 2 輪都 ≥ 77 級就換回；5 人都換完（或放棄）就結束
  uv run --no-project python tools/gui/petwatch.py --once              # 只掃一輪（只讀，不換、不補血；加 --apply 才會換：≥ 門檻的人會馬上再掃一次確認）
  uv run --no-project python tools/gui/petwatch.py --interval 30 --target-level 77 [--spot 點名]
  uv run --no-project python tools/gui/petwatch.py --pet 金布伊 --level 77 --back 朵拉比斯 --pet-slot 3   # 全部參數（以上是預設值）
  --pet / --level（= --target-level）：被監測的練功寵名與換回門檻；--back：換回的戰寵名；--pet-slot：練功寵在寵物欄第幾格（1～5，5 個角色排列要一樣，只用來讀等級）。
  --back-slot 已不用（2026-10-13 起換回改用 pet.py 依名字找格、外掛下拉依 OCR 文字選；保留參數相容）。
  --max-tries N：同一角色換回失敗幾次就放棄（預設 2；放棄的人寫 errlog、不再重試，最後退出碼 4）
  uv run --no-project python tools/gui/petwatch.py --heal              # 兼做補血檢查（HP < --hp% / MP < --mp% 連 2 次 → heal_trip 補血再回練功點）
  --spot：補血後回去的練功點；預設不給（2026-10-15 起不寫死地雷區）= 開跑時所在的練功點 → 現在所在的練功點 → 依隊長等級 auto（spots.auto_spot，
    轉數取 grind 快取 / HUD）；都決定不了就不補血、記 errlog（heal_spot）
  --exp-fruit：開練前先跑 `depot_use.py DKBO 2倍智慧果`（由它讀 buff 圖示決定吃不吃；2026-10-13 play agent 憑印象判斷「已有 buff」沒吃、實際已過期，所以不要自己判斷跳過）；
    失敗（95 沒看到 buff / 倉庫沒有果）只記 errlog 照常監測，9 / 10 驗證視窗 / 斷線才停
  補血預設**關**（2026-10-13 起；使用者規定練功不自動補血，psa-grind-no-auto-heal）；--no-heal 保留相容（= 預設，no-op）

換回流程（2026-10-13 改：舊版盲點外掛下拉「第 2 項」，下拉順序每人不同 → DKBO2 / 3 / 5 又鎖回金布伊、每輪關開遇敵無限迴圈）：
  到門檻的人**一批**做：關原地遇敵一次 → 等戰鬥結束 →
  ① 外掛取消「鎖定戰寵」（rebirth_pets.Tools.lock_set_many = pet_catch --unlock 戰寵，勾著才點、讀回）→
  ② 寵物面板戰寵按「出戰」（pet.set_state_many，依名字找格、點完讀回；鎖定還勾著會回 74）→
  ③ 外掛重勾「鎖定戰寵」= 戰寵（pet_catch.relock 同一套：下拉 OCR 讀字找剛好 1 列、讀回欄位才勾）→
  全部做完才把遇敵開回來（只開一次）。每步「某人失敗就停」的批次工具，失敗的人記原因後**跳過他繼續做其他人**；
  ② 失敗的人會試著把鎖定戰寵勾回練功寵（恢復原狀）。每人最多 --max-tries 次，放棄就寫 errlog、不再重試（不無限迴圈）。
  失敗原因寫在 log / errlog：取消鎖定失敗（外掛 rc）/ 出戰 74（鎖定戰寵還勾著 → `pet_catch.py --unlock 戰寵 --roles 角色`）/
  72（寵物欄找不到唯一一隻戰寵）/ 78（戰鬥中）/ 重勾鎖定失敗（下拉讀不到戰寵名）。
讀等級（2026-10-13 改）：pet.level_from_rows（單字樣板 → 三組 OCR 共識且不跟樣板認得的字矛盾；讀不準回 None，不回錯值；
  舊版最後退回單組 OCR，會把 33 讀成 10 / 17）。到門檻要**連續兩輪讀值都 ≥ 門檻且相差 ≤ 2** 才換（STABLE_DIFF）。
「鎖定戰寵」= 外掛 ASS →「一般設置」→ 鎖定戰寵（勾選框 + 下拉選寵物），鎖定後寵物面板的出戰 / 休息會被擋
（「你已鎖定戰寵，請取消後再操作」）。戰鬥中寵物面板也不能換（「戰鬥中禁止當前操作」）。
座標只量過 2880×1659；見 .claude/skills/psa-game-ui/ui/pet.md。只透過 gui.ps1 / ocr.ps1 / stat.ps1 操作畫面；不碰放生 / 回爐 / 垃圾桶。
退出碼：0 全部換回 / --once 結束；2 參數 / 版面不對；3 已有另一支在跑；4 有人換回失敗達上限被放棄（見 errlog）；
  1 補血失敗；heal.EXIT_VERIFY 驗證視窗逾時；uikit 9 / 10（驗證視窗 / 斷線）換回途中遇到就整個停（不再動任何人）。
"""
import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import actlog
import charstate
import clients
import errlog
import heal
import layout
import netwatch
import watchstate
import winenv
from walk import gui, log

CACHE = clients.cache_dir()          # 每個視窗一份（主視窗 = tools/.cache，與改版前相同）
STATE = CACHE / 'petwatch.json'
LOCK = CACHE / 'petwatch.lock'

CHARS = ['DKBO', 'DKBO2', 'DKBO3', 'DKBO4', 'DKBO5']   # 真名字母 O；舊 petwatch.json 的 DKB0… 在 load_state 轉成真名
AVATAR_Y = {'DKBO': 195, 'DKBO2': 322, 'DKBO3': 450, 'DKBO4': 580, 'DKBO5': 700}   # 寵物面板左欄頭像 x=83
PET_BTN = (318, 80)
SLOT_Y = [200, 322, 445, 567, 690]                 # 寵物欄 1～5 格（x=250）
SLOT_X = 250
SIG_PET = '1310,108,197,71,49'                     # 寵物面板右上紅 ✕
NAME_BOX = (430, 160, 200, 45)                     # 寵物面板選中寵物的名字
LEVEL_BOX = (470, 620, 130, 36)                    # 選中寵物模型下方的「0轉N」（OCR 框；pet.ocr_level_consensus 用）
STABLE_DIFF = 2                                    # 連續兩輪讀值相差 ≤ 這個才算穩定（練功中兩輪之間可能升 1 級）
MAX_TRIES = 2                                      # 同一角色換回失敗幾次就放棄
EXIT_GAVE_UP = 4
STOP_RCS = (9, 10)                                 # uikit 驗證視窗 / 斷線：換回途中遇到就整個停


VERIFY_NAME = False
SLOT_CACHE: dict = {}                              # 角色 → 練功寵所在格（0 起算）
# 可由命令列改：練功寵名 / 所在格（1 起算）、換回的戰寵名。預設 = 轉生後的狀態（金布伊第 3 格、朵拉比斯）
PET_NAME, PET_SLOT = '金布伊', 3
BACK_NAME, BACK_SLOT = '朵拉比斯', 2
MOUNT_SPECIES = '布拉奇多斯'                       # 只給 rebirth_pets.lock_items 的參數（只鎖戰寵時用不到）


def configure(pet: str = '金布伊', pet_slot: int = 3, back: str = '朵拉比斯', back_slot: int = 2) -> None:
    """設定練功寵 / 戰寵（格號 1～5；back_slot 只做相容檢查，換回時依名字找格）；格號超出範圍丟 ValueError"""
    global PET_NAME, PET_SLOT, BACK_NAME, BACK_SLOT
    for n in (pet_slot, back_slot):
        if not 1 <= n <= len(SLOT_Y):
            raise ValueError(f'寵物格 {n} 超出 1～{len(SLOT_Y)}')
    if pet_slot == back_slot:
        raise ValueError('練功寵與戰寵不能同一格')
    if not pet.strip() or not back.strip():
        raise ValueError('寵物名不能空白')
    if pet.strip() == back.strip():
        raise ValueError('練功寵與戰寵不能同名')
    PET_NAME, PET_SLOT, BACK_NAME, BACK_SLOT = pet.strip(), pet_slot, back.strip(), back_slot
    SLOT_CACHE.clear()


def name_key(name: str) -> str:
    """OCR 比對用的寵物名關鍵字：前 2 字（金布伊 → 金布；朵拉比斯 → 朵拉；OCR 常掉字 / 錯字）"""
    return name[:2]


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


_LV_CTX: dict = {}


def ocr_level(slot: int | None = None) -> int | None:
    """讀「目前選中寵物」模型下方黃字「0轉70」的等級：pet.level_from_rows（petmatch 單字樣板 → 三組 OCR 共識、且不跟樣板認得的字矛盾）。
    讀不準一律 None（2026-10-13 起拿掉舊的「單組 OCR 重試」：它會把 33 讀成 10 / 17、128 讀成 28）。
    slot 參數保留給呼叫端相容，沒用到。樣板 ctx 整支程式共用一份（有學到新字 / 清掉污染就存檔）"""
    try:
        import pet
        import petmatch
        if not _LV_CTX:
            _LV_CTX.update(pet.load_ctx(True))
        rows, _ = petmatch.grab([petmatch.BOX_LVL + ('lvl',)])
        if not rows:
            return None
        v, _ = pet.level_from_rows(rows[0], _LV_CTX)
        pet.save_ctx(_LV_CTX)
        return v
    except Exception as e:
        log(f'讀等級失敗：{e}')
        return None


def confirm_due(res: dict, prev: dict, target: int) -> tuple:
    """純函式：本輪讀值 res、上一輪讀值 prev → (確定到門檻的角色, 這輪第一次到門檻、要再讀一次確認的角色)。
    確定 = 本輪與上一輪都 ≥ target 且相差 ≤ STABLE_DIFF（OCR 偶發錯值不會連兩輪一樣；練功中兩輪間可能升 1 級）"""
    due, pending = [], []
    for c, v in res.items():
        if v is None or v < target:
            continue
        p = prev.get(c)
        if p is not None and p >= target and abs(v - p) <= STABLE_DIFF:
            due.append(c)
        else:
            pending.append(c)
    return due, pending


def seq(steps: str) -> str:
    return gui('seq', steps)


def ok_last(out: str) -> bool:
    lines = [l for l in out.splitlines() if l.startswith(('ok', 'timeout'))]
    return bool(lines) and lines[-1].startswith('ok')


def open_pet() -> bool:
    out = seq(f'key {{ESC}}; wait 300; click {PET_BTN[0]} {PET_BTN[1]}; waitpix 1500 {SIG_PET}')
    return ok_last(out)


def close_panel() -> None:
    gui('key', '{ESC}')


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


# ---------------- 換回原戰寵（重用 pet.py / pet_catch / rebirth_pets 的批次工具）----------------
def tools():
    """碰遊戲的批次工具（rebirth_pets.Tools：外掛 lock_set_many、pet_set_state_many、pets_list）；測試換成假的"""
    import rebirth_pets
    return rebirth_pets.Tools()


def why_state(rc: int, msg: str = '') -> str:
    """pet.set_state_many 的退出碼 → 給人看的原因（純函式）"""
    hint = {74: '點了出戰沒變：鎖定戰寵還勾著（先 `pet_catch.py --unlock 戰寵 --roles 角色`）或戰鬥中',
            72: f'寵物欄找不到唯一一隻{BACK_NAME}（名字讀不出 / 同名多隻 / 不在寵物欄）',
            73: '騎寵保護擋下', 78: '戰鬥中（寵物面板不能換）', 71: '寵物面板左欄角色 / 寵物格沒選到', 70: '寵物面板打不開 / 中途消失'}
    return f'出戰 rc {rc}：' + hint.get(rc, msg or '寵物面板操作失敗')


def each_batch(roles: list, fn) -> tuple:
    """「某人失敗就停」的批次工具（fn(角色清單) → (rc, 出錯的角色 | None)）逐段跑完：失敗的人記下、從他後面接著做。
    → (成功的角色, {失敗角色: rc}, 停手 rc 或 0)。出錯角色是 None（面板打不開等，整批都沒做）→ 剩下的人全記失敗；
    rc 是驗證視窗 / 斷線（STOP_RCS）→ 立刻停、回停手 rc（純流程，測試直接餵假 fn）"""
    ok, bad, rest = [], {}, list(roles)
    while rest:
        rc, who = fn(rest)
        if not rc:
            ok += rest
            break
        if rc in STOP_RCS:
            if who in rest:
                ok += rest[:rest.index(who)]
                rest = rest[rest.index(who):]
            for r in rest:
                bad[r] = rc
            return ok, bad, rc
        if who not in rest:
            for r in rest:
                bad[r] = rc
            break
        k = rest.index(who)
        ok += rest[:k]
        bad[who] = rc
        rest = rest[k + 1:]
    return ok, bad, 0


def swap_back_many(roles: list, T=None) -> tuple:
    """一批角色的「練功寵 → 戰寵」換回（呼叫前要先關原地遇敵、等戰鬥結束）。→ ({角色: (成功?, 原因)}, 停手 rc 或 0)。
    ① 取消鎖定戰寵 → ② 戰寵出戰 → ③ 重勾鎖定戰寵 = 戰寵（下拉讀字選）；② 失敗的人試著把鎖定戰寵勾回練功寵（恢復原狀，盡力）"""
    import rebirth_pets as rp
    T = T or tools()
    out = {}
    ok1, bad, stop = each_batch(roles, lambda rs: T.lock_set_many([(r, '戰寵', False, None) for r in rs]))
    for r, rc in bad.items():
        out[r] = (False, f'取消鎖定戰寵失敗（外掛 rc {rc}）')
    if stop:
        return out, stop
    state_rc = {}

    def fight(rs):
        import pet
        rc, who = T.pet_set_state_many(rs, BACK_NAME, '出戰')
        if rc and who:
            state_rc[who] = (rc, next((o.get('msg', '') for o in pet.LAST.get('ops', []) if o.get('role') == who), ''))
        return rc, who
    ok2, bad, stop = each_batch(ok1, fight)
    restore = []
    for r, rc in bad.items():
        out[r] = (False, why_state(*state_rc.get(r, (rc, ''))))
        restore.append(r)
    if stop:
        return out, stop
    ok3, stop = [], 0
    if ok2:
        rc, pets = T.pets_list(ok2)
        if rc in STOP_RCS:
            return out, rc
        if rc:
            for r in ok2:
                out[r] = (False, f'重勾鎖定前讀寵物欄失敗（rc {rc}）；出戰已換、鎖定戰寵沒勾')
        else:
            items = []
            for r in ok2:
                it, why = rp.lock_items(pets, [r], MOUNT_SPECIES, BACK_NAME, ('戰寵',))
                if it:
                    items += it
                else:
                    out[r] = (False, f'重勾鎖定：{why}；出戰已換、鎖定戰寵沒勾')
            by = {it[0]: it for it in items}
            ok3, bad, stop = each_batch(list(by), lambda rs: T.lock_set_many([by[r] for r in rs]))
            for r, rc in bad.items():
                out[r] = (False, f'重勾鎖定戰寵 = {BACK_NAME} 失敗（外掛 rc {rc}：下拉讀不到 / 欄位讀回不對）；出戰已換、鎖定戰寵沒勾')
            for r in ok3:
                out[r] = (True, '')
    if restore and not stop:                                     # ② 失敗：鎖定已取消、練功寵還在出戰 → 盡力勾回練功寵（不算成功）
        rc, pets = T.pets_list(restore)
        if not rc:
            items = []
            for r in restore:
                it, _ = rp.lock_items(pets, [r], MOUNT_SPECIES, PET_NAME, ('戰寵',))
                items += it
            if items:
                _, bad2, _ = each_batch([i[0] for i in items], lambda rs: T.lock_set_many([i for i in items if i[0] in rs]))
                for r in restore:
                    if r in bad2 or r not in [i[0] for i in items]:
                        out[r] = (False, out[r][1] + '；鎖定戰寵也沒能勾回練功寵（目前沒鎖）')
    return out, stop


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


def here_spot():
    """現在所在練功點（grind.here_spot：HUD 地圖 ID → spots）；測試替換"""
    import grind
    return grind.here_spot()


def heal_spot(a):
    """補血後回去的點（heal.SPOTS 內才算）：--spot 明講 > 開跑時所在練功點（a.home）> 現在所在練功點 > 依隊長等級 auto（grind.auto_spot_now）> None"""
    if a.spot:
        return a.spot
    for sp in (getattr(a, 'home', None), here_spot()):
        if sp in heal.SPOTS:
            return sp
    import grind
    sp = grind.auto_spot_now()
    return sp if sp in heal.SPOTS else None


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


def run_swaps(due: list, done: set, gave: set, tries: dict, st: dict, levels: dict, max_tries: int = MAX_TRIES,
              reopen: bool = True, T=None) -> int:
    """到門檻的一批角色換回：原地遇敵只關一次 → 等戰鬥結束 → swap_back_many → 全部做完才開回一次（不每人 / 每輪反覆開關）。
    成功 → done；失敗 → tries +1、寫 errlog（含原因）；達 max_tries → gave（放棄、之後不掃不換）。
    → 停手 rc（驗證視窗 / 斷線 = STOP_RCS，遇敵不開回）或 0。reopen=False（--once 且本來沒開）→ 不開遇敵"""
    was_on = heal.encounter_on()
    stop = 0
    try:
        if was_on:
            heal.set_encounter(False)
        if not battle_free():
            log('等不到戰鬥結束，這輪不換（不計失敗次數）')
            return 0
        res, stop = swap_back_many(due, T)
        for c in due:
            ok, why = res.get(c, (False, '沒有結果（批次中斷）'))
            if ok:
                done.add(c)
                log(f'{c}：已換回{BACK_NAME}（出戰 + 鎖定戰寵；{PET_NAME} {levels.get(c)} 級）')
                continue
            tries[c] = tries.get(c, 0) + 1
            errlog.add(f'petwatch：{c} 換回{BACK_NAME}失敗（第 {tries[c]} / {max_tries} 次）：{why}', source='petwatch')
            log(f'{c}：換回失敗（第 {tries[c]} / {max_tries} 次）：{why}')
            if tries[c] >= max_tries:
                gave.add(c)
                errlog.add(f'petwatch：{c} 換回{BACK_NAME}失敗 {tries[c]} 次，放棄（請人工：pet_catch.py --unlock 戰寵 --roles {c} → '
                           f'pet.py set-state {c} {BACK_NAME} 出戰 → pet_catch.py --lock 戰寵 --roles {c} --battle-pet {BACK_NAME}）', source='petwatch')
        st['done'] = sorted(done)
        st['gave_up'] = sorted(gave)
        save_state(st)
        if stop:
            log(f'換回途中遇到驗證視窗 / 斷線（rc {stop}）→ 整個停手，不開回遇敵')
        return stop
    finally:
        if (was_on or reopen) and not stop:
            try:
                heal.set_encounter(True)
            except RuntimeError as e:
                errlog.add(f'petwatch 開回原地遇敵失敗：{e}', source='petwatch')


def eat_exp_fruit() -> int:
    """開練前吃 2倍智慧果：一律交給 depot_use（讀 buff 圖示決定吃不吃，不憑印象 / state.json 判斷）→ 退出碼（0 = 已有 / 吃到）"""
    import depot_use
    rc, info = depot_use.run('DKBO', '2倍智慧果')
    if rc:
        i = errlog.add(f'petwatch --exp-fruit：depot_use 2倍智慧果 rc={rc}（{info.get("step")}）', source='petwatch')
        log(f'2倍智慧果沒吃到 rc={rc}（errlog #{i}），照常監測')
    else:
        log('2倍智慧果：' + ('buff 已在，沒重吃' if info.get('step') == 'skip' else '已吃（buff 圖示確認）'))
    return rc


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
    ap.add_argument('--pet-slot', type=int, default=3, help='練功寵在寵物欄第幾格 1～5（預設 3；只用來讀等級）')
    ap.add_argument('--back', default='朵拉比斯', help='換回的戰寵名（預設 朵拉比斯；轉生前的舊流程是 迪基格斯）')
    ap.add_argument('--back-slot', type=int, default=2, help='相容舊指令（換回改依名字找格、下拉讀字選，不再用格號）')
    ap.add_argument('--max-tries', type=int, default=MAX_TRIES, help=f'同一角色換回失敗幾次就放棄（預設 {MAX_TRIES}）')
    ap.add_argument('--spot', default=None, choices=heal.SPOTS, help='補血後回去的練功點（預設：開跑時所在練功點 → 現在所在 → 依等級 auto）')
    ap.add_argument('--heal', action='store_true', help='兼做補血檢查（預設關：練功不自動補血）')
    ap.add_argument('--no-heal', action='store_true', help='相容舊指令：= 預設（不補血），no-op')
    ap.add_argument('--heal-every', type=int, default=15, help='補血檢查間隔秒數（預設 15）')
    ap.add_argument('--hp', type=int, default=40)
    ap.add_argument('--mp', type=int, default=20)
    ap.add_argument('--exp-fruit', action='store_true', help='開練前先 depot_use DKBO 2倍智慧果（讀 buff 圖示決定吃不吃）')
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
    if a.exp_fruit:
        frc = eat_exp_fruit()
        if frc in (9, 10):                                   # 驗證視窗 / 斷線：整個停
            try:
                LOCK.unlink()
            except OSError:
                pass
            return frc
    if not a.no_heal and not a.once and not a.spot:
        a.home = here_spot()                            # 開跑時所在練功點 = 補血後回去的點
        log(f'補血後回 {a.home or "（目前不在練功點，補血時再依位置 / 等級決定）"}')
    st = load_state()
    done = set(st['done'])
    gave: set = set()                                   # 本次執行放棄的角色（不寫回下次：重跑 petwatch = 人工處理過、再試）
    tries: dict = {}
    prev: dict = {}                                     # 上一輪讀值（連續兩輪確認用）
    rc_final = 0
    end = time.time() + a.duration if a.duration else None
    next_scan = 0.0
    vg = watchstate.VerifyGuard('petwatch', log=log)   # watch 標出疑似驗證視窗 → 暫停動作，最多 10 分鐘（超過停止、寫 errlog，不自動恢復）
    log(f'開始：每 {a.interval} 秒掃一輪，{PET_NAME} 連 2 輪 ≥ {a.target_level} 級就換回{BACK_NAME}；已完成 {sorted(done) or "無"}')
    try:
        while len(done | gave) < len(CHARS) and (end is None or time.time() < end):
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
                sp = heal_spot(a) if hits >= 2 else None
                if hits >= 2 and not sp:
                    i = errlog.add('petwatch 要補血但決定不了回哪個練功點（不在練功點、讀不到等級），這次不補血', source='petwatch')
                    log(f'血 / 魔太低但不知道補完回哪個練功點 → 不補血（errlog #{i}）；可用 --spot 指定')
                elif hits >= 2:
                    log(f'血 / 魔太低（HP {s.get("hpPct")}%，MP {s.get("mpPct")}%），回村補血，補完回 {sp}')
                    try:
                        heal.heal_trip(sp)
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
                res = scan(done | gave)
                next_scan = time.time() + a.interval
                if res is None:
                    log('寵物面板開不起來（戰鬥 / 對話中？），跳過這輪')
                else:
                    log(f'{PET_NAME}等級：' + '、'.join(f'{c} {v if v is not None else "?"}' for c, v in res.items()))
                    st['levels'] = {**st.get('levels', {}), **{c: v for c, v in res.items() if v is not None}}
                    st['ts'] = time.strftime('%H:%M:%S')
                    save_state(st)
                    due, pending = confirm_due(res, prev, a.target_level)
                    prev = {**prev, **{c: v for c, v in res.items() if v is not None}}      # 讀不到的人保留上次讀值（不因一輪讀不到重置確認）
                    if pending:
                        log(f'{pending} 第一次讀到 ≥ {a.target_level}，下一輪再讀一次確認（讀值不穩不換）')
                        next_scan = time.time() + min(a.interval, 8)
                    if a.once and pending and a.apply:                      # --once --apply：第一次到門檻的人馬上再讀一次確認
                        res2 = scan(done | gave | set(due))
                        if res2:
                            due2, _ = confirm_due(res2, prev, a.target_level)
                            due = due + [c for c in due2 if c not in due]
                            res = {**res, **res2}
                    if due and (not a.once or a.apply):
                        stop = run_swaps(due, done, gave, tries, st, res, a.max_tries, reopen=not a.once)
                        if stop:
                            return stop
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
    if gave:
        log(f'{sorted(gave)} 換回失敗 {a.max_tries} 次已放棄（原因見 errlog）；其餘 {sorted(done)} 已換回')
        rc_final = EXIT_GAVE_UP
    return rc_final


if __name__ == '__main__':
    sys.exit(main())
