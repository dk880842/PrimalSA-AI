#!/usr/bin/env python3
"""寵物面板腳本化（P6：list / set-state / rest-all；store / take 留 P7）。計畫：notes/plan-scriptify.md §5。只用標準函式庫。

用法（專案根目錄；WSL / Windows 原生指令相同；角色名 DKB0 / DKBO 都收，輸出用真名 DKBO）：
  uv run --no-project python tools/gui/pet.py list [--role DKBO|all] [--json]           # 唯讀：每格 名字 / 狀態 / 等級
  uv run --no-project python tools/gui/pet.py set-state DKBO 迪基格斯 出戰|等待|騎乘 [--slot N] [--allow-mount]
  uv run --no-project python tools/gui/pet.py rest-all [--role all] [--keep 瑪斯貝卡] [--only 名,名] [--dry-run]
  共用旗標：--pause-encounter（先關原地遇敵、等戰鬥結束，做完再開回；預設不動遇敵，戰鬥中直接退 78）、--no-learn（不學樣板）、--timing
  最後一行一律印 JSON：{"ok", "rc", ...}；給其他腳本 import：pet.list_roles / set_state / rest_all 回退出碼，結果 dict 在 pet.LAST。

做法（P-I5 實測 2026-10-11，數據見 notes/plan-scriptify.md）：
  - 面板內一律經 uikit.safe_click（面板沒開 → 不點；紅區 FORBIDDEN 一律 ForbiddenClick）。**面板沒開絕不點頭像**（會點到任務追蹤）。
  - 選角色：點左欄頭像 → 黃框（頭像上緣 x=83）必須「剛好只有該角色」；頭像下名字有樣板就要吻合（沒有樣板就學一次）。
  - 空格：爪印 4 點顏色；選中：格子左邊框黃色；**點空格不會改變選取**（畫面仍停在上一隻寵物，所以不能靠名字判斷空格）。
  - 名字：petmatch 整塊圖樣板（同名 IoU = 1.000）→ 沒樣板才 OCR（-Dark 0 -Zooms 2,3,4 精確命中 Monster 表才學）；
    等級：黃字切字 + 單字樣板 → 沒樣板才 OCR（三組設定共識才學）。名字 / 等級都讀不出來 → None，**不猜**。
  - 狀態：下方三顆鈕（出戰 / 騎乘 / 休息）亮的（棕底）就是目前狀態。
  - 騎寵（uikit.MOUNTS = 瑪斯貝卡）：名字「像」騎寵（is_mount_like，鬆）或狀態 = 騎乘 → set-state / rest-all 不動（73），要動需 --allow-mount。

退出碼（共用 0 / 1 / 2 / 8 / 9 / 10 見 uikit；pet 自己 70～78）：
  70 寵物面板打不開 / 中途消失（沒點任何面板內座標）
  71 左欄角色或寵物格沒選到（黃框不對 / 頭像名字樣板不符）
  72 寵物名字對不上（Monster 表 / 找不到指定寵物 / 同名多隻沒給 --slot）→ 拒絕
  73 禁止操作（騎寵 / 目標是騎乘鈕，沒給 --allow-mount）
  74 狀態點了沒變（多半是外掛鎖定戰寵：「你已鎖定戰寵，請取消後再操作」；或戰鬥中）→ 不自動去外掛解鎖（計畫 §9 第 9 條），只點 1 次
  78 戰鬥中（預設不動遇敵；--pause-encounter 才會關遇敵等戰鬥結束）
  （75～77 留給 P7 store / take）
"""
import time

_T_START = time.time()
import argparse  # noqa: E402
import json  # noqa: E402
import sys  # noqa: E402
from pathlib import Path  # noqa: E402

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import charstate  # noqa: E402
import petmatch  # noqa: E402
import uikit  # noqa: E402

SRC = 'pet'
EXIT_PANEL, EXIT_SELECT, EXIT_NAME, EXIT_FORBID, EXIT_NOCHANGE, EXIT_BATTLE = 70, 71, 72, 73, 74, 78

SLOT_X = 250
SLOT_Y = [200, 322, 445, 567, 690]                  # 寵物欄 1～5 格
BTN_XY = {'出戰': (390, 702), '騎乘': (532, 702), '等待': (672, 702)}      # 狀態鈕（ui/pet.md）；「休息」鈕 = 等待
STATES = ('出戰', '騎乘', '等待')
STATE_ALIAS = {'出戰': '出戰', '戰鬥': '出戰', 'fight': '出戰', '騎乘': '騎乘', '騎': '騎乘', 'ride': '騎乘',
               '等待': '等待', '休息': '等待', 'rest': '等待', 'wait': '等待'}
# ---- 像素探針（P-I5 實測，2880×1659 截圖座標）----
FRAME_DX, FRAME_DY = 200, -30                       # 格子左邊框：選中 = 橘黃 (251,146,4)/(248,184,5)；沒選 ≈ (196,183,155)
PAW = [(250, 2, (155, 123, 82)), (250, -5, (179, 145, 98)), (230, 15, (179, 145, 98)), (270, -15, (155, 122, 82))]   # 空格爪印底（x, 相對格心 y, 顏色）
PAW_TOL = 14
BTN_PROBES = {'出戰': [(345, 702), (440, 702)], '騎乘': [(487, 702), (580, 702)], '等待': [(627, 702), (700, 702)]}   # 亮 = 棕底
SELECT_WAIT_S = 1.5
STATE_WAIT_S = 2.0
POLL_S = 0.2
CLICK_WAIT_MS = 250
LAST: dict = {}

BANNER_RETRIES, BANNER_WAIT_S = 2, 0.8
OCR_NAME = [('-Dark', 0, '-Zooms', '2,3,4'), ('-Dark', 120, '-Zooms', '2,3')]
OCR_LEVEL = [('-Dark', 0, '-Zooms', '2,3,4'), ('-Dark', 50, '-Zooms', '2,3,4'), ('-Dark', 70, '-Zooms', '2,3,4')]


def log(msg: str) -> None:
    print(f'pet：{msg}', file=sys.stderr, flush=True)


# ---- 像素判斷（純函式，測試直接餵顏色）----
def is_frame_sel(c) -> bool:
    return c[0] > 235 and c[1] > 120 and c[2] < 60


def is_avatar_sel(c) -> bool:
    return c[0] > 235 and 150 < c[1] < 215 and c[2] < 110


def is_btn_on(c) -> bool:
    return c[0] < 205 and c[1] < 150 and c[2] < 100


def is_paw(cols) -> bool:
    return len(cols) == len(PAW) and all(all(abs(a - b) <= PAW_TOL for a, b in zip(c, ref)) for c, (_, _, ref) in zip(cols, PAW))


def btn_state(cols_by_state: dict):
    """{狀態: [兩點顏色]} → 剛好一顆亮（兩點都亮）= 該狀態；其他 = None"""
    on = [s for s, cs in cols_by_state.items() if cs and all(is_btn_on(c) for c in cs)]
    return on[0] if len(on) == 1 else None


def norm_state(text):
    return STATE_ALIAS.get(str(text or '').strip().lower())


# ---- 讀面板 ----
def _scan_points() -> tuple:
    pts = []
    for cy in SLOT_Y:
        pts.append((FRAME_DX, cy + FRAME_DY))
    for cy in SLOT_Y:
        pts.extend((x, cy + dy) for x, dy, _ in PAW)
    roles = list(petmatch.AVATAR_Y)
    for r in roles:
        pts.append((83, petmatch.AVATAR_TOP_Y[r]))
    for s in STATES:
        pts.extend(BTN_PROBES[s])
    return pts, roles


def scan_frames() -> dict | None:
    """一次 pixel（約 40 點）→ {'sel': [5 格是否選中], 'empty': [5 格是否空格], 'avatar': [5 個頭像是否選中], 'state': 目前選中寵物的狀態或 None}；讀不到 None"""
    pts, roles = _scan_points()
    cols = uikit.px(pts)
    if cols is None:
        return None
    k = 0
    sel = [is_frame_sel(c) for c in cols[k:k + 5]]
    k += 5
    empty = []
    for _ in SLOT_Y:
        empty.append(is_paw(cols[k:k + len(PAW)]))
        k += len(PAW)
    av = [is_avatar_sel(c) for c in cols[k:k + len(roles)]]
    k += len(roles)
    st = {}
    for s in STATES:
        st[s] = cols[k:k + 2]
        k += 2
    return {'sel': sel, 'empty': empty, 'avatar': av, 'state': btn_state(st), 'roles': roles}


def panel_ok() -> bool:
    return uikit.is_open(uikit.PET)


def click(x: int, y: int, note: str) -> bool:
    return uikit.safe_click(x, y, uikit.PET, note=note, wait_ms=CLICK_WAIT_MS)


def wait_for(pred, secs: float):
    """每 POLL_S 讀一次 scan_frames，pred(f) 成立就回 f；逾時回最後一次（可能 None）"""
    end = uikit.clock() + secs
    f = None
    while True:
        f = scan_frames()
        if f is not None and pred(f):
            return f, True
        if uikit.clock() >= end:
            return f, False
        uikit.sleep(POLL_S)


# ---- 選角色 / 選格 ----
def _petwatch():
    import petwatch
    return petwatch


def check_avatar_name(role: str, ctx: dict) -> bool:
    """頭像下名字樣板核對：有樣板 → 必須吻合；沒有 → 學一次（OCR 讀到別人就不學並判不符）。第 5 個頭像名字在面板外 → 不核對"""
    if role not in petmatch.AVATAR_Y or role == 'DKBO5':
        return True
    box = petmatch.avatar_box(role)
    rows, _ = petmatch.grab([box + ('brown',)])
    if not rows:
        return True                              # 讀不到不當不符（主證據是黃框）
    label, sc, _ = petmatch.match_whole('avatar', rows[0], ctx['tpl'])
    if label:
        return charstate.same(label, role)
    if petmatch.ink(rows[0]) < petmatch.MIN_INK['avatar']:
        return True
    if ctx['learn']:
        for t in _petwatch().ocr(box, '-Dark', 150, '-Zooms', '2,3,4'):
            hit = charstate.norm_char(t)
            if hit and not charstate.same(hit, role):
                log(f'頭像名字 OCR 讀到 {hit}，與點的 {role} 矛盾')
                return False
        if petmatch.learn_whole('avatar', role, rows[0], ctx['tpl'], log):
            ctx['dirty'] = True
    return True


def select_role(role: str, ctx: dict) -> int:
    """點頭像 → 黃框剛好只有該角色（一次重點）。0 / 70 / 71。呼叫前面板必須開著（safe_click 會再驗）"""
    idx = list(petmatch.AVATAR_Y).index(role)
    f = None
    for attempt in range(2):
        if not click(83, petmatch.AVATAR_Y[role], f'pet 選角色 {role}'):
            return uikit_fail(EXIT_PANEL, '寵物面板特徵不在，沒點頭像')
        f, ok = wait_for(lambda f: f['avatar'] == [i == idx for i in range(len(f['avatar']))], SELECT_WAIT_S)
        if ok:
            break
    else:
        uikit.snap(f'pet-select-{role}')
        return uikit_fail(EXIT_SELECT, f'點了 {role} 頭像但黃框不對（讀到 {f and f["avatar"]}）')
    uikit.mark(f'select {role}')
    if not check_avatar_name(role, ctx):
        uikit.snap(f'pet-avatar-name-{role}')
        return uikit_fail(EXIT_SELECT, f'{role} 頭像下的名字與樣板不符（左欄順序變了？）')
    return 0


def select_slot(i: int, f: dict) -> int:
    """選第 i 格（0 起算）；已選中不點。0 / 70 / 71"""
    if f['sel'][i] and sum(f['sel']) == 1:
        return 0
    for attempt in range(2):
        if not click(SLOT_X, SLOT_Y[i], f'pet 選第 {i + 1} 格'):
            return uikit_fail(EXIT_PANEL, '寵物面板特徵不在，沒點寵物格')
        g, ok = wait_for(lambda g, i=i: g['sel'] == [k == i for k in range(5)], SELECT_WAIT_S)
        if ok:
            return 0
    uikit.snap(f'pet-slot-{i + 1}')
    return uikit_fail(EXIT_SELECT, f'點了第 {i + 1} 格但黃框沒移過去（讀到 {g and g["sel"]}）')


def uikit_fail(rc: int, msg: str) -> int:
    return uikit.fail(SRC, rc, msg)


# ---- 名字 / 等級（樣板優先，OCR 備援並學習）----
def _exact(text):
    names = uikit.pet_names()
    return names.get(uikit._pet_key(text))


def ocr_pet_name() -> tuple:
    """OCR 名字 → (正式名或 None, 原始文字清單, 是否「精確命中 Monster 表」)。
    精確：某組設定的所有非空行都精確命中同一名字；否則所有 OCR 行 snap 到同一名字且至少 2 行同意（不精確，不拿去學樣板）"""
    pw = _petwatch()
    raw = []
    for opts in OCR_NAME:
        lines = [t for t in pw.ocr(petmatch.BOX_NAME, *opts) if uikit._pet_key(t)]
        raw += lines
        ex = {_exact(t) for t in lines}
        if lines and None not in ex and len(ex) == 1:
            return ex.pop(), raw, True
        if len(ex - {None}) > 1:
            return None, raw, False
    snapped = [uikit.snap_pet(t) for t in raw]
    good = [s for s in snapped if s]
    if good and len(set(good)) == 1 and len(good) >= 2 and len(good) == len(snapped):
        return good[0], raw, False
    return None, raw, False


def ocr_level_consensus():
    """三組 OCR 設定各自投票（該組讀到的最常見值，並列 / 沒讀到 = 棄權）；某值 ≥ 2 票且領先 → 該值，否則 None。
    等級 OCR 很不穩（128 讀成 28 / 1、130 讀成 134），所以要多組共識才拿去學樣板"""
    import re
    from collections import Counter
    pw = _petwatch()
    votes: Counter = Counter()
    for opts in OCR_LEVEL:
        vals = Counter(int(m[1]) for t in pw.ocr(pw.LEVEL_BOX, *opts) for m in [re.search(r'轉(\d{1,3})', t)] if m)
        if not vals:
            continue
        top = vals.most_common()
        if len(top) > 1 and top[0][1] == top[1][1]:
            continue
        votes[top[0][0]] += 1
        rk = votes.most_common()
        if rk[0][1] >= 2 and (len(rk) == 1 or rk[0][1] > rk[1][1]):
            return rk[0][0]
    rk = votes.most_common()
    return rk[0][0] if rk and rk[0][1] >= 2 and (len(rk) == 1 or rk[0][1] > rk[1][1]) else None


def read_slot(i: int, ctx: dict) -> dict:
    """目前選中的寵物（已確認是第 i 格）→ {'slot','name','via','ocr','state','level','lv_via','mountlike'}"""
    tpl = ctx['tpl']
    probes = [p for s in STATES for p in BTN_PROBES[s]]
    for attempt in range(BANNER_RETRIES + 1):
        rows, extra = petmatch.grab([petmatch.BOX_NAME + ('name',), petmatch.BOX_LVL + ('lvl',)], extra=probes)
        if rows is None:
            break
        known = (tpl.get('name') and petmatch.match_whole('name', rows[0], tpl)[0] is None) or (tpl.get('digit') and petmatch.read_level(rows[1], tpl) is None)
        if not known or attempt == BANNER_RETRIES:
            break
        uikit.sleep(BANNER_WAIT_S)              # 樣板都有卻對不上：多半是 EXP 橫幅 / 浮字蓋住（掛機中常見），等它消失再讀
        uikit.mark('banner-retry')
    d = {'slot': i + 1, 'empty': False, 'name': None, 'via': None, 'state': None, 'level': None}
    if rows is None:
        d['err'] = '讀不到像素'
        return d
    d['state'] = btn_state({s: extra[2 * k:2 * k + 2] for k, s in enumerate(STATES)})
    name_rows, lvl_rows = rows
    label, sc, _ = petmatch.match_whole('name', name_rows, tpl)
    if label:
        d['name'], d['via'] = label, 'tpl'
    elif petmatch.ink(name_rows) >= petmatch.MIN_INK['name']:
        nm, raw, exact = ocr_pet_name()
        d['name'], d['via'], d['ocr'] = nm, ('ocr' if nm else None), raw
        if nm and exact and ctx['learn']:
            again, _ = petmatch.grab([petmatch.BOX_NAME + ('name',)])
            if again and again[0] == name_rows and petmatch.learn_whole('name', nm, name_rows, tpl, log):    # 前後兩次截圖相同才學（避免畫面還沒換）
                ctx['dirty'] = True
    lv = petmatch.read_level(lvl_rows, tpl)
    if lv is not None:
        d['level'], d['lv_via'] = lv, 'tpl'
    elif petmatch.ink(lvl_rows) >= petmatch.MIN_INK['lvl']:
        v = ocr_level_consensus()
        if v is not None:
            d['level'], d['lv_via'] = v, 'ocr'
            if ctx['learn']:
                again, _ = petmatch.grab([petmatch.BOX_LVL + ('lvl',)])
                if again and again[0] == lvl_rows and petmatch.learn_level(lvl_rows, v, tpl):
                    ctx['dirty'] = True
    ocr_texts = ([d['name']] if d['name'] else []) + d.get('ocr', [])
    d['mountlike'] = any(uikit.is_mount_like(t) for t in ocr_texts)
    return d


def list_role(role: str, ctx: dict) -> tuple:
    """面板已開。選角色 → 每個非空格選取 + 讀 → (rc, [slot dict])。最後停在最後一隻寵物（沒有任何狀態改動）"""
    rc = select_role(role, ctx)
    if rc:
        return rc, []
    f = scan_frames()
    if f is None:
        return uikit_fail(EXIT_PANEL, '讀不到面板像素'), []
    slots = []
    for i in range(5):
        if f['empty'][i]:
            slots.append({'slot': i + 1, 'empty': True})
            continue
        rc = select_slot(i, f)
        if rc:
            return rc, slots
        slots.append(read_slot(i, ctx))
        f = scan_frames() or f
    uikit.mark(f'list {role}')
    return 0, slots


# ---- 面板 / 戰鬥 / 遇敵 ----
def battle_free_now() -> bool:
    """面板關著時用 VS 牌顏色判斷沒在戰鬥（面板開著會蓋住這個點，不能用）"""
    import heal
    out = uikit.gui('seq', f'waitpix 0 {heal.SIG_NO_BATTLE} 40')
    return any(ln.startswith('ok') for ln in (out or '').splitlines())


class Session:
    """開面板（若本來沒開）、用完關；--pause-encounter 時先關遇敵等戰鬥結束、最後開回。with 內回傳 rc 在 self.rc"""

    def __init__(self, pause: bool = False, need_calm: bool = False):
        self.pause, self.need_calm = pause, need_calm
        self.rc, self.was_open, self.enc_was = 0, False, False

    def __enter__(self):
        import heal
        self.rc = uikit.preflight(SRC)
        if self.rc:
            return self
        try:
            import grind
            other = grind._other_running()
            if other:
                log(f'{other} 在跑，會搶畫面 → 不動作')
                self.rc = uikit.EXIT_IN_BATTLE
                return self
        except Exception:
            pass
        self.was_open = uikit.is_open(uikit.PET)
        if self.pause and not self.was_open:
            self.enc_was = heal.encounter_on()
            if self.enc_was:
                try:
                    heal.set_encounter(False)
                except RuntimeError as e:
                    self.rc = uikit_fail(EXIT_BATTLE, f'關原地遇敵失敗：{e}')
                    return self
            heal.gui('seq', f'waitpix 25000 {heal.SIG_NO_BATTLE} 40')
            uikit.mark('pause-encounter')
        if not self.was_open and (self.pause or self.need_calm) and not battle_free_now():
            self.rc = uikit_fail(EXIT_BATTLE, '戰鬥中（VS 牌在），預設不動遇敵；加 --pause-encounter 或等戰鬥結束')
            return self
        ok, _ = uikit.open_panel_ex(uikit.PET)
        uikit.mark('open PET')
        if not ok:
            self.rc = uikit_fail(EXIT_PANEL, '寵物面板打不開（沒看到主畫面 HUD 或面板特徵）；沒點任何面板內座標')
        return self

    def __exit__(self, *exc):
        import heal
        if not self.was_open and uikit.is_open(uikit.PET):
            uikit.close_panel(uikit.PET, known_open=True)
            uikit.mark('close PET')
        if self.enc_was:
            try:
                heal.set_encounter(True)
            except RuntimeError as e:
                log(f'開回原地遇敵失敗：{e}（請人工確認遇敵鈕）')
        return False


def load_ctx(learn: bool) -> dict:
    return {'tpl': petmatch.load_tpl(), 'learn': learn, 'dirty': False}


def save_ctx(ctx: dict) -> None:
    if ctx['dirty']:
        try:
            petmatch.save_tpl(ctx['tpl'])
        except OSError as e:
            log(f'樣板存檔失敗：{e}')
        ctx['dirty'] = False


def _out(rc: int, info: dict, t0: float, msg: str = '', as_json_only: bool = False) -> int:
    info.update(ok=rc == 0, rc=rc, ms=int((time.time() - t0) * 1000))
    if msg:
        info['msg'] = msg
    if uikit._stages is not None:
        info['t'] = uikit.timing_get()
    LAST.clear()
    LAST.update(info)
    print(json.dumps(info, ensure_ascii=False))
    return rc


def role_list(arg: str) -> list | None:
    """'all' → 全部頭像角色（照白名單順序）；其他 → 單一角色（寬鬆正規化）；不認得 → None"""
    if str(arg).lower() == 'all':
        return [r for r in (charstate.display(c) for c in charstate.chars()) if r in petmatch.AVATAR_Y]
    hit = charstate.norm_char(arg)
    r = charstate.display(hit) if hit else None
    return [r] if r in petmatch.AVATAR_Y else None


def fmt_slot(s: dict) -> str:
    if s.get('empty'):
        return f'  {s["slot"]}  （空）'
    nm = s.get('name') or '?'
    lv = s.get('level')
    return f'  {s["slot"]}  {nm:<8} {s.get("state") or "?":<3} Lv{lv if lv is not None else "?"}'


# ---- 指令 ----
def list_roles(role_arg: str = 'all', as_json: bool = False, pause: bool = False, learn: bool = True) -> int:
    t0 = time.time()
    roles = role_list(role_arg)
    if not roles:
        print(f'pet：角色 {role_arg!r} 不認得（DKBO、DKBO2～5 或 all）', file=sys.stderr)
        return _out(uikit.EXIT_USAGE, {'roles': {}}, t0, '角色名不認得')
    info = {'roles': {}}
    ctx = load_ctx(learn)
    with Session(pause) as s:
        if s.rc:
            return _out(s.rc, info, t0)
        for r in roles:
            rc, slots = list_role(r, ctx)
            info['roles'][r] = slots
            if rc:
                save_ctx(ctx)
                return _out(rc, info, t0)
            if not as_json:
                print(f'{r}：')
                for sl in slots:
                    print(fmt_slot(sl))
        save_ctx(ctx)
    return _out(0, info, t0)


def find_slot(slots: list, want: str, slot_no: int | None) -> tuple:
    """slots 中名字 = want 的格 → (slot dict | None, 訊息)。slot_no（1 起算）指定時該格名字必須吻合；同名多隻沒給 slot_no → None"""
    if slot_no is not None:
        sl = next((x for x in slots if x['slot'] == slot_no), None)
        if sl is None or sl.get('empty'):
            return None, f'第 {slot_no} 格是空的'
        return (sl, '') if sl.get('name') == want else (None, f'第 {slot_no} 格是 {sl.get("name") or "?"}，不是 {want}')
    hits = [x for x in slots if not x.get('empty') and x.get('name') == want]
    if len(hits) == 1:
        return hits[0], ''
    if len(hits) > 1:
        return None, f'有 {len(hits)} 隻 {want}（格 {[h["slot"] for h in hits]}），請用 --slot 指定'
    unk = [x['slot'] for x in slots if not x.get('empty') and not x.get('name')]
    return None, f'找不到 {want}' + (f'（格 {unk} 名字讀不出來）' if unk else '')


def apply_state(role: str, sl: dict, target: str, ctx: dict) -> tuple:
    """選該格 → 點狀態鈕（只點 1 次）→ 讀回確認。→ (rc, 訊息)。呼叫前呼叫端已擋騎寵 / 已是目標"""
    f = scan_frames()
    if f is None:
        return uikit_fail(EXIT_PANEL, '讀不到面板像素'), ''
    rc = select_slot(sl['slot'] - 1, f)
    if rc:
        return rc, '選不到該格'
    x, y = BTN_XY[target]
    if not click(x, y, f'pet {role} 第 {sl["slot"]} 格 → {target}'):
        return uikit_fail(EXIT_PANEL, '點狀態鈕前面板特徵不在，沒點'), ''
    g, ok = wait_for(lambda g: g['state'] == target, STATE_WAIT_S)
    if ok:
        uikit.mark(f'state {target}')
        return 0, ''
    path = uikit.snap('pet-state-nochange')
    msg = f'點了「{target}」但狀態沒變（讀到 {g and g["state"]}）：多半是外掛鎖定戰寵（「你已鎖定戰寵，請取消後再操作」）或戰鬥中；不自動去外掛解鎖（計畫 §9 第 9 條）'
    return uikit_fail(EXIT_NOCHANGE, msg), msg + (f'；截圖 {path}' if path else '')


def guard_mount(sl: dict, target: str, allow_mount: bool) -> str | None:
    """騎寵保護：回拒絕原因（或 None = 可以動）"""
    if allow_mount:
        return None
    if target == '騎乘':
        return '目標狀態是「騎乘」（會換騎寵），沒給 --allow-mount'
    if sl.get('state') == '騎乘':
        return f'{sl.get("name")} 正在騎乘中（騎寵），沒給 --allow-mount'
    if sl.get('mountlike') or uikit.is_mount_like(sl.get('name')):
        return f'{sl.get("name") or "名字像騎寵"} 像騎寵（{"/".join(uikit.MOUNTS)}），沒給 --allow-mount'
    return None


def set_state(role_arg: str, pet_text: str, state_text: str, slot_no: int | None = None, allow_mount: bool = False,
              pause: bool = False, learn: bool = True) -> int:
    t0 = time.time()
    roles = role_list(role_arg)
    target = norm_state(state_text)
    want = uikit.snap_pet(pet_text)
    info = {'role': roles[0] if roles and len(roles) == 1 else None, 'pet': want, 'target': target, 'changed': False}
    if not roles or len(roles) != 1:
        print(f'pet：角色 {role_arg!r} 不認得或不是單一角色', file=sys.stderr)
        return _out(uikit.EXIT_USAGE, info, t0, '角色名不認得')
    if target not in STATES:
        print(f'pet：狀態 {state_text!r} 不認得（出戰 / 騎乘 / 等待）', file=sys.stderr)
        return _out(uikit.EXIT_USAGE, info, t0, '狀態不認得')
    role = roles[0]
    if not want:
        rc = uikit_fail(EXIT_NAME, f'寵物名 {pet_text!r} 對不到 Monster 表，拒絕')
        return _out(rc, info, t0, '寵物名對不上')
    ctx = load_ctx(learn)
    with Session(pause, need_calm=True) as s:
        if s.rc:
            return _out(s.rc, info, t0)
        rc, slots = list_role(role, ctx)
        info['slots'] = slots
        save_ctx(ctx)
        if rc:
            return _out(rc, info, t0)
        sl, why = find_slot(slots, want, slot_no)
        if sl is None:
            rc = uikit_fail(EXIT_NAME, why)
            return _out(rc, info, t0, why)
        info['slot'], info['from'] = sl['slot'], sl.get('state')
        bad = guard_mount(sl, target, allow_mount)
        if bad:
            rc = uikit_fail(EXIT_FORBID, f'拒絕：{bad}')
            return _out(rc, info, t0, bad)
        if sl.get('state') == target:
            print(f'pet：{role} 的 {want} 本來就是「{target}」，沒有點擊')
            return _out(0, info, t0)
        rc, msg = apply_state(role, sl, target, ctx)
        info['changed'] = rc == 0
        info['clicked'] = True
        if rc:
            return _out(rc, info, t0, msg)
        print(f'pet：{role} 的 {want}（第 {sl["slot"]} 格）{sl.get("state")} → {target}')
    return _out(0, info, t0)


def plan_rest(slots: list, keep: list, only: list | None) -> tuple:
    """rest-all 的決策（純函式）→ (要改的格 [slot dict], 拒絕 [(slot, 原因)])。
    只動狀態 = 出戰 的格；名字 = keep、像騎寵、狀態 = 騎乘 不動；--only 時只處理名字在清單內的；出戰但名字讀不出來 → 拒絕（不猜）"""
    todo, refuse = [], []
    for s in slots:
        if s.get('empty') or s.get('state') != '出戰':
            continue
        nm = s.get('name')
        if s.get('mountlike') or (nm and nm in keep):
            continue
        if not nm:
            refuse.append((s, '名字讀不出來（OCR / 樣板都沒結果）'))
            continue
        if only is not None and nm not in only:
            continue
        todo.append(s)
    return todo, refuse


def rest_all(role_arg: str = 'all', keep=None, only=None, dry_run: bool = False, pause: bool = False, learn: bool = True) -> int:
    t0 = time.time()
    roles = role_list(role_arg)
    keep = [uikit.snap_pet(k) or k for k in (keep if keep is not None else uikit.MOUNTS)]
    only_n = None if only is None else [uikit.snap_pet(o) or o for o in only]
    info = {'roles': {}, 'rested': {}, 'dry_run': dry_run, 'keep': keep}
    if not roles:
        print(f'pet：角色 {role_arg!r} 不認得', file=sys.stderr)
        return _out(uikit.EXIT_USAGE, info, t0, '角色名不認得')
    ctx = load_ctx(learn)
    final_rc = 0
    with Session(pause, need_calm=not dry_run) as s:
        if s.rc:
            return _out(s.rc, info, t0)
        for r in roles:
            rc, slots = list_role(r, ctx)
            info['roles'][r] = slots
            if rc:
                save_ctx(ctx)
                return _out(rc, info, t0)
            todo, refuse = plan_rest(slots, keep, only_n)
            for sl, why in refuse:
                log(f'{r} 第 {sl["slot"]} 格（出戰）{why}，不動')
                final_rc = final_rc or EXIT_NAME
            names = [f'第 {x["slot"]} 格 {x["name"]}' for x in todo]
            info['rested'][r] = [x['slot'] for x in todo]
            print(f'{r}：' + (('改等待：' + '、'.join(names)) if todo else '沒有需要改的（出戰中的非騎寵 = 0）') + ('  [dry-run 不點]' if dry_run and todo else ''))
            if dry_run:
                continue
            for sl in todo:
                rc, msg = apply_state(r, sl, '等待', ctx)
                if rc:
                    save_ctx(ctx)
                    return _out(rc, info, t0, msg)
            if todo:                                             # 驗證：重讀這個角色，除 keep / 騎寵外沒有出戰
                rc, slots2 = list_role(r, ctx)
                info['roles'][r] = slots2
                if rc:
                    save_ctx(ctx)
                    return _out(rc, info, t0)
                left, _ = plan_rest(slots2, keep, only_n)
                if left:
                    rc = uikit_fail(EXIT_NOCHANGE, f'{r} 改完後仍有出戰中的非騎寵：{[x["slot"] for x in left]}')
                    save_ctx(ctx)
                    return _out(rc, info, t0)
        save_ctx(ctx)
    return _out(final_rc, info, t0, '有出戰寵名字讀不出來（72），沒動它' if final_rc else '')


def main() -> int:
    import winenv
    winenv.enable_server()
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    cp = argparse.ArgumentParser(add_help=False)
    cp.add_argument('--pause-encounter', action='store_true', help='先關原地遇敵、等戰鬥結束，做完開回')
    cp.add_argument('--no-learn', action='store_true', help='不學 / 不存名字與等級樣板')
    cp.add_argument('--timing', action='store_true', help='最後一行 JSON 多一個 t 欄位：各階段毫秒')
    sub = ap.add_subparsers(dest='cmd', required=True)
    p = sub.add_parser('list', help='唯讀：每格 名字 / 狀態 / 等級', parents=[cp])
    p.add_argument('--role', default='all')
    p.add_argument('--json', action='store_true', help='不印表格，只印最後一行 JSON')
    p = sub.add_parser('set-state', help='把某隻寵物改成 出戰 / 等待 / 騎乘', parents=[cp])
    p.add_argument('role')
    p.add_argument('pet')
    p.add_argument('state')
    p.add_argument('--slot', type=int, default=None, help='同名多隻時指定第幾格（1 起算）')
    p.add_argument('--allow-mount', action='store_true', help='允許動騎寵 / 設定騎乘（預設拒絕）')
    p = sub.add_parser('rest-all', help='交寵物任務前：除騎寵外「出戰」全改等待', parents=[cp])
    p.add_argument('--role', default='all')
    p.add_argument('--keep', default=None, help='不動的寵物名（逗號分隔；預設 瑪斯貝卡）')
    p.add_argument('--only', default=None, help='只處理這些名字（逗號分隔）')
    p.add_argument('--dry-run', action='store_true', help='只列出會改哪些（會開面板、選取讀名字，不按狀態鈕）')
    a = ap.parse_args()
    if a.timing:
        uikit.timing_start()
        uikit._stages.append(['import', int((time.time() - _T_START) * 1000)])
        uikit.gui('pixel', '1,1')
        uikit.mark('server-start')
    learn = not a.no_learn
    if a.cmd == 'list':
        return list_roles(a.role, a.json, a.pause_encounter, learn)
    if a.cmd == 'set-state':
        return set_state(a.role, a.pet, a.state, a.slot, a.allow_mount, a.pause_encounter, learn)
    split = lambda t: None if t is None else [x.strip() for x in t.split(',') if x.strip()]    # noqa: E731
    return rest_all(a.role, split(a.keep), split(a.only), a.dry_run, a.pause_encounter, learn)


if __name__ == '__main__':
    sys.exit(main())
