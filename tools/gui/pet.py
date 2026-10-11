#!/usr/bin/env python3
"""寵物面板腳本化（P6：list / set-state / rest-all；P7：store / take）。計畫：notes/plan-scriptify.md §5。只用標準函式庫。

用法（專案根目錄；WSL / Windows 原生指令相同；角色名 DKB0 / DKBO 都收，輸出用真名 DKBO）：
  uv run --no-project python tools/gui/pet.py list [--role DKBO|all] [--json]           # 唯讀：每格 名字 / 狀態 / 等級
  uv run --no-project python tools/gui/pet.py set-state DKBO 迪基格斯 出戰|等待|騎乘 [--slot N] [--allow-mount]
  uv run --no-project python tools/gui/pet.py rest-all [--role all] [--keep 瑪斯貝卡] [--only 名,名] [--dry-run]
  uv run --no-project python tools/gui/pet.py store DKBO 迪基格斯 [--depot personal|public] [--slot N] [--allow-slot1] [--allow-mount-store 名字]
  uv run --no-project python tools/gui/pet.py take DKBO --depot personal --index N [--expect 迪基格斯]
  uv run --no-project python tools/gui/pet.py store-many --role all|DKBO,DKBO3 --pets 迪基格斯,瑪斯貝卡 [--depot personal|public] [--allow-slot1] [--allow-mount-store 瑪斯貝卡] [--skip-missing] [--pick first|last]
  uv run --no-project python tools/gui/pet.py take DKBO --depot public --pet 朵拉比斯        # 不給格號：現場逐張選卡讀名字找（沒名字的卡靠成長字串登錄檔）
  uv run --no-project python tools/gui/pet.py take-many --role all --pets 朵拉比斯 [--depot personal|public] [--skip-missing]
  uv run --no-project python tools/gui/pet.py learn-species DKBO2 1 布拉奇多斯 --confirm-growth 49/9/8/2   # 登錄「這格沒名字的寵物是什麼物種」（縮圖 + 成長字串）
  共用旗標：--pause-encounter（先關原地遇敵、等戰鬥結束，做完再開回；預設不動遇敵，戰鬥中直接退 78）、--no-learn（不學樣板）、--timing
  最後一行一律印 JSON：{"ok", "rc", ...}；給其他腳本 import：pet.list_roles / set_state / rest_all 回退出碼，結果 dict 在 pet.LAST。

做法（P-I5 實測 2026-10-11，數據見 notes/plan-scriptify.md）：
  - 面板內一律經 uikit.safe_click（面板沒開 → 不點；紅區 FORBIDDEN 一律 ForbiddenClick）。**面板沒開絕不點頭像**（會點到任務追蹤）。
  - 選角色：點左欄頭像 → 黃框（頭像上緣 x=83）必須「剛好只有該角色」；頭像下名字有樣板就要吻合（沒有樣板就學一次）。
  - 空格：爪印 4 點顏色；選中：格子左邊框黃色；**點空格不會改變選取**（畫面仍停在上一隻寵物，所以不能靠名字判斷空格）。
  - 名字：petmatch 整塊圖樣板（同名 IoU = 1.000）→ 沒樣板才 OCR（-Dark 0 -Zooms 2,3,4 精確命中 Monster 表才學）；
    等級：黃字切字 + 單字樣板 → 沒樣板才 OCR（三組設定共識才學）。名字 / 等級都讀不出來 → None，**不猜**。
  - 狀態：下方三顆鈕（出戰 / 騎乘 / 休息）亮的（棕底）就是目前狀態。
  - 騎寵（uikit.MOUNTS = 瑪斯貝卡 / 布拉奇多斯）：名字「像」騎寵（is_mount_like，鬆）或狀態 = 騎乘 → set-state / rest-all 不動（73），要動需 --allow-mount。

沒名字的新寵物（#87 / #92，2026-10-11；離線驗證，實機待驗）：剛抓到的寵物名字框顯示「成長字串」a/b/c/d（實測 49/9/8/2、49/9/7/2、48/9/7/1、47/10/7/1、45/10/8/1），
  名字樣板與 Monster 表 OCR 都認不出。list 會給 name=None、unnamed='49/9/8/2'、raw_name='?(49/9/8/2)'（OCR ≥ 2 行完整相同才採用，否則不當字串）。
  物種（species）靠「縮圖簽名 + 成長字串登錄檔」多重確認（tools/.cache/pet-tpl/species.json，學出來的）：學法 = learn-species（呼叫端要有可信標籤，
  並給 --confirm-growth 當第二重確認）；store 時會把「成長字串 → 物種」記進登錄檔，倉庫卡（沒縮圖）之後靠字串認。沒登錄 = 不知道是什麼 → --pet 物種名找不到（72）、store 拒絕（73）。
  物種是騎寵（布拉奇多斯）→ mountlike，store 要 --allow-mount-store 完全同名。
退出碼（共用 0 / 1 / 2 / 8 / 9 / 10 見 uikit；pet 自己 70～78）：
  70 寵物面板打不開 / 中途消失（沒點任何面板內座標）
  71 左欄角色或寵物格沒選到（黃框不對 / 頭像名字樣板不符）
  72 寵物名字對不上（Monster 表 / 找不到指定寵物 / 同名多隻沒給 --slot）→ 拒絕
  73 禁止操作（騎寵 / 目標是騎乘鈕，沒給 --allow-mount）
  74 狀態點了沒變（多半是外掛鎖定戰寵：「你已鎖定戰寵，請取消後再操作」；或戰鬥中）→ 不自動去外掛解鎖（計畫 §9 第 9 條），只點 1 次
  78 戰鬥中（預設不動遇敵；--pause-encounter 才會關遇敵等戰鬥結束）
  75 倉庫分頁 / 子分頁 / 按鈕文字（存入寵物 / 取出寵物）/ 選取 / 縮圖簽名不符 → 不點存取鈕（零點擊）
  76 存 / 取後驗證失敗（**不重點**，請人看 snap；take 名字不符也是 76 / 72，不自動存回）。store 的驗證不認固定格位（倉庫存入後會重排，#84）：寵物欄空格 +1、倉庫張數 +1、倉庫逐張選卡讀名字找得到該寵物（沒名字的比成長字串）
  77 倉庫滿（store）或寵物欄滿（take）→ 零點擊
  store 的硬性禁止（73，零存取點擊）：名字是 / 像騎寵（瑪斯貝卡 / 布拉奇多斯，含 OCR 錯字）、狀態 = 騎乘、第 1 格（要 --allow-slot1 才放行）、名字讀不出來
  例外 --allow-mount-store <名字>（只有使用者當次明講才用）：只放行「名字完全等於此值」的騎寵（像但不同仍擋）、且該寵物狀態必須已是等待（騎乘中仍 73，先 set-state ... 等待 --allow-mount）；
    第 1 格另需 --allow-slot1；沒帶旗標時行為不變；縮圖簽名 / 按鈕文字 / 確認視窗驗證都照舊
  store / take 的存入 / 取出鈕（530,697）每次呼叫最多單擊 1 次；只在「倉庫分頁特徵 + 個人 / 公共分頁 + 按鈕底色 + 按鈕 OCR 文字」全部吻合時才點
  （注意：寵物分頁的「騎乘」鈕 532,702 與倉庫分頁的存入鈕 530,697 幾乎同位置，點錯分頁會換騎寵，所以按鈕前一定現場驗證）
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
EXIT_DEPOT, EXIT_VERIFY, EXIT_FULL = 75, 76, 77

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

# ---- 倉庫分頁（P-I6 實測 2026-10-11）----
PET_TAB_XY, DEPOT_TAB_XY = (1365, 265), (1365, 440)            # 右側「寵物」/「倉庫」分頁
SUBTAB_XY = {'personal': (897, 170), 'public': (1160, 170)}      # 個人 / 公共
SUBTAB_PROBE = {'personal': (780, 170), 'public': (1250, 170)}   # 子分頁底色：亮 (251,219,135) / 暗 (171,127,84)（文字像素不穩，不要用 897 / 1160）
DEPOT_SIG = [(1195, 690, 68, 112, 167, 24), (1215, 720, 72, 120, 179, 24)]    # 倉庫頁「擴容」藍鈕兩點（寵物分頁同位置是米色）
DEPOT_BTN_XY = (530, 697)                                        # 存入寵物 / 取出寵物（同一顆鈕，依選取對象變字）；舊 skill 的取出 675,703 是錯的
BTN_BOX = (440, 670, 180, 55)                                    # 按鈕文字 OCR 框：`-Light 150 -Zooms 2,3,4` 實測 6 / 6 讀對
BTN_BODY = [(450, 680), (450, 715), (460, 697), (480, 672), (520, 672), (560, 672), (600, 680), (600, 715)]   # 按鈕本體（避開字）：存入 = 紅 (≈177,65,38)、取出 = 金 (≈185,125,62)
CARD_X = [818, 924, 1030, 1136, 1242]                            # 倉庫格 5×4（私人倉庫 1/1，20 格）
CARD_Y = [275, 381, 488, 594]                                    # 倉庫格中心（爪印 / 選取框用）
CARD_CLICK_DY = 8                                                # 點擊略往下，離忠誠 ± 的禁區矩形（y 204～264）遠一點
CARD_SEL = [(-43, -25), (-43, 0), (-43, 25)]                     # 選中框：左緣內側三點 ≈ (209,151,13)；沒選 = 暗棕
THUMB_X, THUMB_DY = [250, 265, 280, 292], [-20, -8, 4, 12]       # 寵物格縮圖簽名點（避開左上狀態標 / 右下等級數字）
THUMB_TOL, THUMB_NEED = 24, 14                                   # 每通道容差、16 點至少幾點相符
STORE_WAIT_S = 3.0
# 存入「戰鬥 / 騎乘狀態」寵物會跳「提示：當前寵物為戰鬥或騎乘狀態，確定要存入倉庫?」（P-I9 實測）：確定 615,557 / 取消 813,557 / ✕ 946,208
CONFIRM_SIG = [(946, 208, 197, 73, 49, 24), (550, 545, 58, 105, 167, 24), (670, 545, 66, 113, 171, 24), (750, 545, 179, 69, 44, 24),
               (870, 545, 193, 87, 53, 24), (700, 460, 243, 215, 179, 24)]
CONFIRM_OK_XY, CONFIRM_CANCEL_XY = (615, 557), (813, 557)
CONFIRM_BOX = (500, 335, 430, 110)
CONFIRM = uikit.Panel('PETCONFIRM', None, CONFIRM_SIG, (946, 208))
TAB_WAIT_S = 2.0

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


def resolve_name(name_rows, ctx: dict) -> tuple:
    """名字框的點陣 → (名字或 None, 'tpl' / 'ocr' / None, OCR 原文清單)。樣板優先；沒樣板才 OCR（精確命中 Monster 表才學）。
    名字框是「成長字串」（沒名字的新寵物）→ (None, 'growth', 原文)，字串用 resolve_ident 取"""
    r = resolve_ident(name_rows, ctx)
    return r['name'], r['via'], r['raw']


def resolve_ident(name_rows, ctx: dict) -> dict:
    """名字框 → {'name', 'via', 'raw', 'growth'}。growth = 成長字串 'a/b/c/d'（名字框顯示這個 = 沒名字的新寵物，name 一定是 None、不猜物種；
    OCR 至少 2 行完整相同才採用；同一張圖用 ctx['gcache'] 記住，不重複 OCR）"""
    tpl = ctx['tpl']
    label, sc, _ = petmatch.match_whole('name', name_rows, tpl)
    if label:
        return {'name': label, 'via': 'tpl', 'raw': None, 'growth': None}
    gc = ctx.setdefault('gcache', {})
    key = hash('\n'.join(name_rows)) if name_rows else None
    if key is not None and key in gc:
        return {'name': None, 'via': 'growth', 'raw': None, 'growth': gc[key]}
    if petmatch.ink(name_rows) >= petmatch.MIN_INK['name']:
        nm, raw, exact = ocr_pet_name()
        if not nm:
            g = petmatch.parse_growth(raw)
            if g:
                gc[key] = g
                return {'name': None, 'via': 'growth', 'raw': raw, 'growth': g}
        if nm and exact and ctx['learn']:
            again, _ = petmatch.grab([petmatch.BOX_NAME + ('name',)])
            if again and again[0] == name_rows and petmatch.learn_whole('name', nm, name_rows, tpl, log):    # 前後兩次截圖相同才學（避免畫面還沒換）
                ctx['dirty'] = True
        return {'name': nm, 'via': 'ocr' if nm else None, 'raw': raw, 'growth': None}
    return {'name': None, 'via': None, 'raw': None, 'growth': None}


def species_reg(ctx: dict) -> dict:
    if 'reg' not in ctx:
        ctx['reg'] = petmatch.load_species()
    return ctx['reg']


def ident_species(i: int, growth: str | None, ctx: dict) -> str | None:
    """沒名字的寵物（在寵物欄第 i 格，0 起算）→ 物種：縮圖簽名 + 成長字串登錄檔多重確認；沒登錄 = None（不猜）"""
    cols = uikit.px(thumb_pts(i))
    return petmatch.identify_species(cols, growth, species_reg(ctx))


def slot_ident(sl: dict):
    """格子的有效身分名：有名字用名字；沒名字但物種已確認 → 物種；否則 None"""
    return sl.get('name') or (sl.get('species') if sl.get('unnamed') else None)


def ident_matches(ident: dict, sl: dict) -> bool:
    """現場讀到的名字框（resolve_ident 結果）是不是 sl 這隻：有名字比名字；沒名字比成長字串（同一隻固定）"""
    if sl.get('unnamed'):
        return ident.get('growth') == sl['unnamed']
    return bool(sl.get('name')) and ident.get('name') == sl['name']


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
    ident = resolve_ident(name_rows, ctx)
    d['name'], d['via'], raw = ident['name'], ident['via'], ident['raw']
    if raw:
        d['ocr'] = raw
    if ident['growth']:                                  # 沒名字的新寵物：成長字串 = 這隻的身分；物種由縮圖 / 登錄檔確認
        d['unnamed'] = ident['growth']
        d['raw_name'] = f'?({ident["growth"]})'
        d['species'] = ident_species(i, ident['growth'], ctx)
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
    d['mountlike'] = any(uikit.is_mount_like(t) for t in ocr_texts) or d.get('species') in uikit.MOUNTS
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
        if depot_visible() and not goto_pet_tab():
            self.rc = uikit_fail(EXIT_PANEL, '面板停在倉庫分頁且切不回寵物分頁')
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
    if ctx.get('rdirty'):
        try:
            petmatch.save_species(ctx['reg'])
        except OSError as e:
            log(f'物種登錄檔存檔失敗：{e}')
        ctx['rdirty'] = False
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
    nm = s.get('name') or (s.get('raw_name', '?') + (f'≈{s["species"]}' if s.get('species') else ''))
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


def find_slot(slots: list, want: str, slot_no: int | None, pick: str | None = None) -> tuple:
    """slots 中名字 = want 的格 → (slot dict | None, 訊息)。slot_no（1 起算）指定時該格名字必須吻合；同名多隻沒給 slot_no → None"""
    if slot_no is not None:
        sl = next((x for x in slots if x['slot'] == slot_no), None)
        if sl is None or sl.get('empty'):
            return None, f'第 {slot_no} 格是空的'
        return (sl, '') if slot_ident(sl) == want else (None, f'第 {slot_no} 格是 {sl.get("name") or sl.get("raw_name") or "?"}，不是 {want}')
    hits = [x for x in slots if not x.get('empty') and slot_ident(x) == want]
    if len(hits) == 1:
        return hits[0], ''
    if len(hits) > 1 and pick in ('first', 'last'):          # store-many --pick：同物種的新寵物互相可替換，取最前 / 最後一格
        return (hits[0] if pick == 'first' else hits[-1]), ''
    if len(hits) > 1:
        return None, f'有 {len(hits)} 隻 {want}（格 {[h["slot"] for h in hits]}），請用 --slot 指定'
    unk = [x['slot'] for x in slots if not x.get('empty') and not slot_ident(x)]
    unn = [f'{x["slot"]}:{x["raw_name"]}' for x in slots if x.get('unnamed') and not x.get('species')]
    return None, f'找不到 {want}' + (f'（格 {unk} 名字讀不出來' + (f'；沒名字且物種未確認：{unn}，先 learn-species' if unn else '') + '）' if unk else '')


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


# ================= 倉庫：store / take（P7）=================
def is_tab_on(c) -> bool:
    return c[0] > 235 and c[1] > 200 and 110 < c[2] < 165


def is_card_sel(cols) -> bool:
    """左緣內側三點至少兩點橘黃；選取框會呼吸閃動，實測在 (209,151,13) ～ (249,185,1) 之間"""
    return sum(1 for c in cols if c[0] > 195 and 140 < c[1] < 200 and c[2] < 30) >= 2


def is_body_store(c) -> bool:
    return c[0] > 150 and c[1] < 90 and c[2] < 70


def is_body_take(c) -> bool:
    return c[0] > 160 and c[1] > 100 and c[2] < 90


def body_kind(cols):
    """按鈕本體 8 點：全部紅 → 'store'；全部金 → 'take'；其他（混色 / 不是這顆鈕）→ None"""
    if cols and all(is_body_store(c) for c in cols):
        return 'store'
    if cols and all(is_body_take(c) for c in cols):
        return 'take'
    return None


def thumb_pts(i: int) -> list:
    return [(x, SLOT_Y[i] + dy) for dy in THUMB_DY for x in THUMB_X]


def thumb_same(a, b) -> bool:
    if not a or not b or len(a) != len(b):
        return False
    ok = sum(1 for c, d in zip(a, b) if all(abs(u - v) <= THUMB_TOL for u, v in zip(c, d)))
    return ok >= THUMB_NEED


def mount_same(a, b) -> bool:
    """騎寵位縮圖比對：只比內側 3 欄（x 250 / 265 / 280），不比最右欄 x 292 —— 那欄會被「選中框」的橘色光暈蓋到
    （2026-10-11 P8 實機：存走第 2 格後選取移到騎寵格，x 292 那 4 點 (167,55,10)→(209,119,5)，其餘 12 點逐位元組相同，
    舊的 14 / 16 門檻誤報 76）。12 點至少 11 點相符（實作在 petmatch.inner_same，物種辨識共用）"""
    return petmatch.inner_same(a, b, len(THUMB_X), THUMB_TOL)


def _card_pts() -> list:
    pts = []
    for cy in CARD_Y:
        for cx in CARD_X:
            pts.extend((cx + x - 250, cy + dy) for x, dy, _ in PAW)
            pts.extend((cx + dx, cy + dy) for dx, dy in CARD_SEL)
    return pts


def scan_depot() -> dict | None:
    """一次 pixel → {'sig': 倉庫分頁特徵, 'tab': 'personal'/'public'/None, 'btn': 'store'/'take'/None（本體底色）,
    'empty': [20 格是否空], 'sel': [20 格是否選中]}；讀不到 None。倉庫格依 CARD_Y 列優先排列（index 0 起算）"""
    pts = [(x, y) for x, y, *_ in DEPOT_SIG] + [SUBTAB_PROBE['personal'], SUBTAB_PROBE['public']] + BTN_BODY + _card_pts()
    cols = uikit.px(pts)
    if cols is None:
        return None
    k = 0
    sig = all(uikit.screen_sigs.close(c, (r, g, b), t) for c, (_, _, r, g, b, t) in zip(cols[k:k + len(DEPOT_SIG)], DEPOT_SIG))
    k += len(DEPOT_SIG)
    left, right = is_tab_on(cols[k]), is_tab_on(cols[k + 1])
    k += 2
    tab = 'personal' if left and not right else 'public' if right and not left else None
    btn = body_kind(cols[k:k + len(BTN_BODY)])
    k += len(BTN_BODY)
    empty, sel = [], []
    for _ in range(20):
        empty.append(is_paw(cols[k:k + len(PAW)]))
        k += len(PAW)
        sel.append(is_card_sel(cols[k:k + len(CARD_SEL)]))
        k += len(CARD_SEL)
    return {'sig': sig, 'tab': tab, 'btn': btn, 'empty': empty, 'sel': sel}


def depot_visible() -> bool:
    d = scan_depot()
    return bool(d and d['sig'])


def btn_text() -> str | None:
    """按鈕文字 OCR：'store'（存入寵物）/ 'take'（取出寵物）/ None（讀不出、或兩種都出現 = 不確定）。最多讀 2 次"""
    pw = _petwatch()
    for _ in range(2):
        lines = pw.ocr(BTN_BOX, '-Light', 150, '-Zooms', '2,3,4')
        has_s, has_t = any('存入' in t for t in lines), any('取出' in t for t in lines)
        if has_s != has_t:
            return 'store' if has_s else 'take'
    return None


def card_xy(idx: int) -> tuple:
    return CARD_X[idx % 5], CARD_Y[idx // 5]


def click_card(idx: int, note: str) -> bool:
    x, y = card_xy(idx)
    return click(x, y + CARD_CLICK_DY, note)


def goto_pet_tab() -> bool:
    """倉庫分頁 → 點「寵物」分頁並等倉庫特徵消失。面板必須開著（click 會驗）；已在寵物分頁不點"""
    d = scan_depot()
    if d is None:
        return False
    if not d['sig']:
        return True
    for _ in range(2):
        if not click(PET_TAB_XY[0], PET_TAB_XY[1], 'pet 切回寵物分頁'):
            return False
        end = uikit.clock() + TAB_WAIT_S
        while uikit.clock() < end:
            d = scan_depot()
            if d is not None and not d['sig']:
                return True
            uikit.sleep(POLL_S)
    return False


def open_depot(depot: str) -> tuple:
    """寵物分頁 → 倉庫分頁 → 指定子分頁（個人 / 公共），每步現場驗證。→ (rc, scan_depot 結果或 None)。rc 75 = 沒切到（此時沒點存取鈕）"""
    for attempt in range(2):
        d = scan_depot()
        if d is not None and d['sig']:
            break
        if not click(DEPOT_TAB_XY[0], DEPOT_TAB_XY[1], 'pet 開倉庫分頁'):
            return uikit_fail(EXIT_PANEL, '寵物面板特徵不在，沒點倉庫分頁'), None
        end = uikit.clock() + TAB_WAIT_S
        while uikit.clock() < end:
            d = scan_depot()
            if d is not None and d['sig']:
                break
            uikit.sleep(POLL_S)
        if d is not None and d['sig']:
            break
    else:
        uikit.snap('pet-depot-tab')
        return uikit_fail(EXIT_DEPOT, '點了「倉庫」分頁但看不到倉庫特徵（擴容鈕藍色）；沒點存取鈕'), None
    if d['tab'] != depot:
        for attempt in range(2):
            if not click(SUBTAB_XY[depot][0], SUBTAB_XY[depot][1], f'pet 倉庫 {depot} 子分頁'):
                return uikit_fail(EXIT_PANEL, '寵物面板特徵不在，沒點子分頁'), None
            end = uikit.clock() + TAB_WAIT_S
            while uikit.clock() < end:
                d = scan_depot()
                if d is not None and d['sig'] and d['tab'] == depot:
                    break
                uikit.sleep(POLL_S)
            if d is not None and d['sig'] and d['tab'] == depot:
                break
        else:
            uikit.snap('pet-depot-subtab')
            return uikit_fail(EXIT_DEPOT, f'切不到倉庫「{depot}」子分頁（讀到 {d and d["tab"]}）；沒點存取鈕'), None
    uikit.mark(f'depot {depot}')
    return 0, d


def read_name_now(ctx: dict, retries: int = BANNER_RETRIES, wait: float = BANNER_WAIT_S):
    """名字框現在顯示的名字（寵物分頁 = 選中寵物；倉庫分頁 = 選中的寵物 / 倉庫卡）。EXP 橫幅 / 「完成對寵物的操作」浮字蓋住時等 wait 秒重讀。→ (名字或 None, 原文)"""
    for attempt in range(retries + 1):
        rows, _ = petmatch.grab([petmatch.BOX_NAME + ('name',)])
        if rows is None:
            return None, None
        nm, via, raw = resolve_name(rows[0], ctx)
        if nm or attempt == retries or petmatch.ink(rows[0]) < petmatch.MIN_INK['name']:
            return nm, raw
        uikit.sleep(wait)
    return None, None


def read_ident(ctx: dict, retries: int = BANNER_RETRIES, wait: float = BANNER_WAIT_S) -> dict:
    """名字框現在顯示的身分（read_name_now 的完整版）→ resolve_ident 的 dict（讀不到像素 → 全 None）。
    EXIT 橫幅 / 浮字蓋住時等 wait 秒重讀（名字框有墨但名字 / 成長字串都認不出）"""
    ident = {'name': None, 'via': None, 'raw': None, 'growth': None}
    for attempt in range(retries + 1):
        rows, _ = petmatch.grab([petmatch.BOX_NAME + ('name',)])
        if rows is None:
            return ident
        ident = resolve_ident(rows[0], ctx)
        if ident['name'] or ident['growth'] or attempt == retries or petmatch.ink(rows[0]) < petmatch.MIN_INK['name']:
            return ident
        uikit.sleep(wait)
    return ident


def guard_store(sl: dict, allow_slot1: bool, allow_mount_store: str | None = None) -> str | None:
    """存倉硬性禁止：回拒絕原因（None = 可以）。騎寵絕不存；唯一例外 allow_mount_store = 該寵物的「正式名」且 sl 名字完全相同（不接受像）、
    狀態須已是等待（騎乘 / 出戰都擋，先 set-state 等待）；其餘規則（名字 / 狀態讀不出、第 1 格要 --allow-slot1）照舊"""
    nm = slot_ident(sl)
    if not nm:
        if sl.get('unnamed'):
            return f'{sl.get("raw_name")} 沒名字且物種未確認（縮圖 / 成長字串登錄檔對不上；可能是騎寵），拒絕存倉；先 learn-species'
        return '名字讀不出來（不猜，拒絕存倉）'
    if sl.get('state') == '騎乘':
        return f'{nm} 正在騎乘中（騎寵），絕不存倉'
    if allow_mount_store and nm == allow_mount_store:                          # 名字完全相同才放行，且必須已是「等待」
        if sl.get('state') != '等待':
            return f'{nm} 狀態是 {sl.get("state")}（--allow-mount-store 只放行「等待」中的；先 set-state {nm} 等待 --allow-mount）'
    elif sl.get('mountlike') or uikit.is_mount_like(nm) or nm in uikit.MOUNTS:
        return f'{nm} 是 / 像騎寵（{"/".join(uikit.MOUNTS)}），絕不存倉'
    if sl.get('slot') == 1 and not allow_slot1:
        return '第 1 格預設禁止存倉（騎寵位置）；確定要存加 --allow-slot1'
    if sl.get('state') is None:
        return f'{nm} 的狀態讀不出來（無法排除騎乘），拒絕存倉'
    return None


def btn_ready(kind: str) -> tuple:
    """存取鈕按下前最後一關：倉庫特徵 + 按鈕本體底色 + 按鈕 OCR 文字三者一致 = kind（'store'/'take'）。→ (ok, 說明)"""
    d = scan_depot()
    if d is None or not d['sig']:
        return False, '倉庫分頁特徵不在'
    if d['btn'] != kind:
        return False, f'按鈕底色是 {d["btn"]}（要 {kind}）'
    t = btn_text()
    if t != kind:
        return False, f'按鈕文字 OCR 是 {t}（要 {kind}）'
    return True, ''


def confirm_text_ok() -> bool:
    """確認視窗文字軟檢查：讀得到字就必須含「存入」或「倉庫」；讀不到（OCR 空）不擋（視窗特徵 + 事前已確認寵物不是騎寵）"""
    pw = _petwatch()
    seen = []
    for opts in (('-Dark', 120, '-Zooms', '2,3'), ('-Dark', 0, '-Zooms', '2,3,4')):
        seen += [t for t in pw.ocr(CONFIRM_BOX, *opts) if t.strip()]
        if any('存入' in t or '倉庫' in t or '戰鬥' in t for t in seen):
            return True
    return not seen


def handle_confirm(info: dict) -> bool:
    """存入戰鬥狀態寵物的確認視窗：特徵在 → 驗文字 → 單擊「確定」一次；文字不對就點「取消」。回 True = 這次有處理"""
    if not uikit.is_open(CONFIRM):
        return False
    info['confirm_seen'] = True
    if confirm_text_ok():
        if uikit.safe_click(CONFIRM_OK_XY[0], CONFIRM_OK_XY[1], CONFIRM, note='pet 存入確認 → 確定'):
            info['confirm_clicked'] = True
    else:
        uikit.snap('pet-confirm-text')
        uikit.safe_click(CONFIRM_CANCEL_XY[0], CONFIRM_CANCEL_XY[1], CONFIRM, note='pet 存入確認文字不符 → 取消')
        info['confirm_cancelled'] = True
    return True


def wait_counts(depot: str, want_pets_empty: int, want_cards_filled: int, info: dict | None = None, allow_confirm: bool = False):
    """等寵物欄空格數 / 倉庫已用格數同時到目標；→ (成功, 寵物 scan_frames, scan_depot)。
    allow_confirm=True（store）：看到「戰鬥 / 騎乘狀態存入確認」視窗就處理一次（單擊確定）；take 不預期有視窗 → 看到就取消並失敗"""
    end = uikit.clock() + STORE_WAIT_S
    f = d = None
    handled = False
    while True:
        if not handled and info is not None and uikit.is_open(CONFIRM):
            if allow_confirm:
                handled = handle_confirm(info)
                end = uikit.clock() + STORE_WAIT_S
            else:
                info['confirm_seen'] = True
                uikit.snap('pet-take-confirm')
                uikit.safe_click(CONFIRM_CANCEL_XY[0], CONFIRM_CANCEL_XY[1], CONFIRM, note='pet take 出現未預期的提示 → 取消')
                info['confirm_cancelled'] = True
                return False, f, d
        f, d = scan_frames(), scan_depot()
        if f and d and d['sig'] and d['tab'] == depot and sum(f['empty']) == want_pets_empty and (20 - sum(d['empty'])) == want_cards_filled:
            return True, f, d
        if uikit.clock() >= end:
            return False, f, d
        uikit.sleep(POLL_S)


def _depot_prologue(role_arg: str, depot: str, cmd: str) -> tuple:
    roles = role_list(role_arg)
    info = {'role': roles[0] if roles and len(roles) == 1 else None, 'depot': depot, 'cmd': cmd, 'clicked': False}
    if not roles or len(roles) != 1:
        print(f'pet：角色 {role_arg!r} 不認得或不是單一角色', file=sys.stderr)
        return None, info
    if depot not in ('personal', 'public'):
        print(f'pet：--depot {depot!r} 不認得（personal / public）', file=sys.stderr)
        return None, info
    return roles[0], info


def store(role_arg: str, pet_text: str, depot: str = 'personal', slot_no: int | None = None, allow_slot1: bool = False,
          pause: bool = False, learn: bool = True, allow_mount_store: str | None = None) -> int:
    """寵物 → 倉庫（計畫 §5.3）。硬性禁止（騎寵 / 騎乘 / 第 1 格 / 名字讀不出）→ 73 且完全不碰倉庫與存入鈕；存入鈕每次最多點 1 次"""
    t0 = time.time()
    role, info = _depot_prologue(role_arg, depot, 'store')
    if role is None:
        return _out(uikit.EXIT_USAGE, info, t0, '角色或倉庫參數不對')
    want = uikit.snap_pet(pet_text)
    info['pet'] = want
    am = None                                                                       # --allow-mount-store：參數名 / 旗標值 / 正式名三者 norm 後必須完全相同
    if allow_mount_store:
        k = uikit._pet_key(allow_mount_store)
        if want and k and k == uikit._pet_key(pet_text) == uikit._pet_key(want):
            am = want
        else:
            rc = uikit_fail(EXIT_FORBID, f'拒絕存倉：--allow-mount-store {allow_mount_store!r} 與寵物名 {pet_text!r} 不完全相同；零點擊')
            return _out(rc, info, t0, '--allow-mount-store 與寵物名不符')
    info['allow_mount_store'] = am
    if am is None and (uikit.is_mount_like(pet_text) or (want and want in uikit.MOUNTS)):    # 連名字都像騎寵（含 OCR 錯字「瑪斯貝卞」）→ 完全不開面板
        rc = uikit_fail(EXIT_FORBID, f'拒絕存倉：{pet_text!r} 是 / 像騎寵（{"/".join(uikit.MOUNTS)}），絕不存倉；零點擊')
        return _out(rc, info, t0, '騎寵不能存倉')
    if not want:
        rc = uikit_fail(EXIT_NAME, f'寵物名 {pet_text!r} 對不到 Monster 表，拒絕')
        return _out(rc, info, t0, '寵物名對不上')
    ctx = load_ctx(learn)
    with Session(pause, need_calm=True) as s:
        if s.rc:
            return _out(s.rc, info, t0)
        try:
            rc = _store_body(role, want, depot, slot_no, allow_slot1, ctx, info, am)
        finally:
            save_ctx(ctx)
            _back_to_pet_tab()
    return _out(rc, info, t0, info.get('msg', ''))


def _back_to_pet_tab() -> None:
    try:
        if uikit.is_open(uikit.PET):
            goto_pet_tab()
    except Exception:
        pass


def _store_body(role: str, want: str, depot: str, slot_no, allow_slot1: bool, ctx: dict, info: dict, am: str | None = None,
                pre: tuple | None = None) -> int:
    def bad(rc, msg):
        info['msg'] = msg
        return uikit_fail(rc, msg)

    rc, slots = pre if pre is not None else list_role(role, ctx)      # pre = store-many 已讀好的 (rc, slots)
    info['slots'] = slots
    if rc:
        return rc
    sl, why = find_slot(slots, want, slot_no)
    if sl is None:
        return bad(EXIT_NAME, why)
    i = sl['slot'] - 1
    info['slot'] = sl['slot']
    reason = guard_store(sl, allow_slot1, am)
    if reason:
        return bad(EXIT_FORBID, f'拒絕存倉：{reason}')
    pets_empty = sum(1 for x in slots if x.get('empty'))
    # 離開寵物分頁前：重新選該格、讀名字 / 狀態、記縮圖簽名（目標格 + 第 1 格騎寵位）
    f = scan_frames()
    if f is None:
        return bad(EXIT_PANEL, '讀不到面板像素')
    rc = select_slot(i, f)
    if rc:
        return rc
    cur = read_slot(i, ctx)
    cur_sl = {**sl, **{k: cur.get(k) for k in ('name', 'state', 'mountlike', 'unnamed', 'raw_name', 'species')}}
    reason = guard_store(cur_sl, allow_slot1, am)
    if reason or slot_ident(cur_sl) != want or (sl.get('unnamed') and cur_sl.get('unnamed') != sl['unnamed']):
        return bad(EXIT_FORBID if reason else EXIT_NAME, f'選中第 {sl["slot"]} 格後重讀：{reason or "名字是 " + str(cur.get("name") or cur.get("raw_name"))}，不存')
    sl = cur_sl
    pre_cols = uikit.px(thumb_pts(i) + thumb_pts(0))
    if pre_cols is None:
        return bad(EXIT_PANEL, '讀不到縮圖簽名')
    pre_t, pre_mount = pre_cols[:16], pre_cols[16:]
    # 倉庫分頁 → 個人 / 公共
    rc, d = open_depot(depot)
    if rc:
        info['msg'] = '倉庫分頁沒切成功'
        return rc
    if not any(d['empty']):
        return bad(EXIT_FULL, f'{depot} 倉庫滿了（20 / 20），沒有點存入鈕')
    depot_before = 20 - sum(d['empty'])
    free_idx = d['empty'].index(True)
    # 按鈕前最後一關：該格被選中、名字仍是目標、縮圖沒變（沒補位換人）、騎寵位沒動、按鈕底色 + 文字 = 存入
    f = scan_frames()
    if f is None or not (f['sel'] == [k == i for k in range(5)]):
        rc = select_slot(i, f or {'sel': [False] * 5})
        if rc:
            return rc
    ident = read_ident(ctx)
    if not ident_matches(ident, sl):
        return bad(EXIT_DEPOT, f'倉庫分頁中選取的是 {ident["name"] or ident["growth"]}（要 {want}），不點存入')
    now_cols = uikit.px(thumb_pts(i) + thumb_pts(0))
    if now_cols is None or not thumb_same(pre_t, now_cols[:16]) or (i != 0 and not mount_same(pre_mount, now_cols[16:])):
        uikit.snap('pet-store-thumb')
        return bad(EXIT_DEPOT, '縮圖簽名與切分頁前不符（寵物欄變動 / 補位換人？），不點存入')
    ok, why = btn_ready('store')
    if not ok:
        uikit.snap('pet-store-btn')
        return bad(EXIT_DEPOT, f'存入鈕驗證失敗：{why}；不點')
    # 單擊一次
    if not click(DEPOT_BTN_XY[0], DEPOT_BTN_XY[1], f'pet store {role} {want} → {depot}'):
        return bad(EXIT_PANEL, '面板特徵不在，沒點存入鈕')
    info['clicked'] = True
    uikit.mark('store click')
    ok, f2, d2 = wait_counts(depot, pets_empty + 1, depot_before + 1, info, allow_confirm=True)
    if not ok:
        path = uikit.snap('pet-store-nochange')
        return bad(EXIT_VERIFY, f'點了存入但寵物欄 / 倉庫張數沒照預期變（寵物空格 {f2 and sum(f2["empty"])}→要 {pets_empty + 1}；倉庫 {d2 and 20 - sum(d2["empty"])}→要 {depot_before + 1}）：可能戰鬥中被擋或倉庫滿；不重點，請人看截圖{"：" + path if path else ""}')
    # 事後：騎寵位沒動；新倉庫格的名字 = want
    m_cols = uikit.px(thumb_pts(0))
    if i != 0 and (m_cols is None or not mount_same(pre_mount, m_cols)):        # 存第 1 格（--allow-slot1）時後面的寵物會補位上來，不比
        uikit.snap('pet-store-mount')
        return bad(EXIT_VERIFY, '存入後第 1 格（騎寵）縮圖變了！請人立刻看截圖確認')
    # 事後驗證（#84）：倉庫存入後會重新排序，不能認固定格位 → 寵物欄空格 +1 / 倉庫張數 +1（上面 wait_counts 已確認）
    # 再「現場逐張選卡讀名字」確認倉庫裡找得到這隻（先看新增的那格，再依序其他格）；沒名字的寵物比成長字串
    new_idx = next((k for k in range(20) if not d2['empty'][k] and d['empty'][k]), free_idx)
    found = find_card(d2, depot, lambda idn: ident_matches(idn, sl), ctx, first=new_idx, info=info)
    info['depot_index'] = None if found is None else found + 1
    if found is None:
        uikit.snap('pet-store-notfound')
        return bad(EXIT_VERIFY, f'存入後寵物欄 / 倉庫張數都對，但倉庫 {depot} 裡逐張看不到 {want}（{sl.get("raw_name") or want}）！請人看截圖')
    if sl.get('unnamed') and sl.get('species'):                  # 記住這隻的成長字串 → 物種（倉庫卡沒縮圖，之後取出靠字串認）
        if petmatch.learn_species(species_reg(ctx), sl['species'], None, sl['unnamed']):
            ctx['rdirty'] = True
    uikit.mark('store verified')
    print(f'pet：{role} 的 {want}（原第 {sl["slot"]} 格）存入{"個人" if depot == "personal" else "公共"}倉庫第 {found + 1} 格')
    return 0


def wait_for_card(idx: int, depot: str):
    end = uikit.clock() + SELECT_WAIT_S
    d = None
    while True:
        d = scan_depot()
        if d and d['sig'] and d['tab'] == depot and d['sel'] == [k == idx for k in range(20)]:
            return d, True
        if uikit.clock() >= end:
            return d, False
        uikit.sleep(POLL_S)


def card_is(idn: dict, want: str | None, reg: dict) -> bool:
    """倉庫卡 / 名字框身分 idn 是不是 want：有名字比名字；沒名字比「成長字串 → 登錄檔物種」（沒登錄 = 不是，不猜）"""
    if not want:
        return False
    if idn.get('name'):
        return idn['name'] == want
    g = idn.get('growth')
    return bool(g) and (reg.get('growth') or {}).get(g) == want


def card_order(filled: list, first: int | None) -> list:
    """逐張驗證的順序：first（新增 / 優先的那格）先，其餘已用格照序（純函式）"""
    idxs = [k for k, f in enumerate(filled) if f]
    if first is not None and first in idxs:
        idxs.remove(first)
        idxs.insert(0, first)
    return idxs


def find_card(d: dict, depot: str, pred, ctx: dict, first: int | None = None, info: dict | None = None):
    """倉庫（d = scan_depot 結果）逐張選卡讀名字框，pred(ident) 成立的第一格 index（0 起算）；找不到 / 面板消失 → None。
    選卡只是選取（無副作用）；每張卡先等選取框移過去才讀（讀到上一張的名字是舊資料）。info['cards'] 記讀到的每張（debug / take 用）"""
    seen = {}
    for k in card_order([not e for e in d['empty']], first):
        if not click_card(k, f'pet 找倉庫卡 第 {k + 1} 格'):
            break
        g, ok = wait_for_card(k, depot)
        if not ok:
            continue
        idn = read_ident(ctx, 4, 1.0)
        seen[k + 1] = idn['name'] or (f'?({idn["growth"]})' if idn['growth'] else None)
        if pred(idn):
            if info is not None:
                info['cards'] = seen
            return k
    if info is not None:
        info['cards'] = seen
    return None


def take(role_arg: str, depot: str = 'personal', index: int | None = None, expect: str | None = None,
         pause: bool = False, learn: bool = True, pet_name: str | None = None) -> int:
    """倉庫第 index 格（1 起算）→ 寵物欄。名字框會顯示選中倉庫卡的名字：有 --expect 時先驗名字（不符不點）、取出後再驗新寵物名字（不符 76，不自動存回）。
    pet_name（--pet）：不給格號，現場逐張選卡讀名字找第一張吻合的（沒名字的卡比成長字串 → 登錄檔物種）；找不到 72、不點取出"""
    t0 = time.time()
    role, info = _depot_prologue(role_arg, depot, 'take')
    if role is None:
        return _out(uikit.EXIT_USAGE, info, t0, '角色或倉庫參數不對')
    if pet_name and index is None:
        expect = expect or pet_name
    elif index is None or not 1 <= index <= 20:
        print('pet：--index 要 1～20（倉庫格，列優先、1 起算），或給 --pet 名字', file=sys.stderr)
        return _out(uikit.EXIT_USAGE, info, t0, '--index 不對')
    want = None
    if expect:
        want = uikit.snap_pet(expect)
        if not want:
            rc = uikit_fail(EXIT_NAME, f'--expect {expect!r} 對不到 Monster 表，拒絕')
            return _out(rc, info, t0, '寵物名對不上')
    info.update(index=index, expect=want)
    ctx = load_ctx(learn)
    with Session(pause, need_calm=True) as s:
        if s.rc:
            return _out(s.rc, info, t0)
        try:
            rc = _take_body(role, depot, None if index is None else index - 1, want, ctx, info)
        finally:
            save_ctx(ctx)
            _back_to_pet_tab()
    return _out(rc, info, t0, info.get('msg', ''))


def _take_body(role: str, depot: str, idx, want, ctx: dict, info: dict) -> int:
    def bad(rc, msg):
        info['msg'] = msg
        return uikit_fail(rc, msg)

    rc, slots = list_role(role, ctx)
    info['slots'] = slots
    if rc:
        return rc
    free_slots = [x['slot'] for x in slots if x.get('empty')]
    if not free_slots:
        return bad(EXIT_FULL, '寵物欄 5 / 5 滿了，沒有點取出鈕')
    pets_empty = len(free_slots)
    rc, d = open_depot(depot)
    if rc:
        info['msg'] = '倉庫分頁沒切成功'
        return rc
    if idx is None:                                            # --pet：現場逐張找
        idx = find_card(d, depot, lambda idn: card_is(idn, want, species_reg(ctx)), ctx, info=info)
        if idx is None:
            if ctx.get('skip_missing'):                        # take-many --skip-missing：這個角色倉庫沒有，略過（不記 errlog）
                info['missing'] = True
                info['msg'] = f'{depot} 倉庫沒有 {want}（讀到 {info.get("cards")}）'
                return EXIT_NAME
            return bad(EXIT_NAME, f'{depot} 倉庫裡逐張看不到 {want}（讀到 {info.get("cards")}）；沒取出')
        info['index'] = idx + 1
    if d['empty'][idx]:
        return bad(EXIT_NAME, f'{depot} 倉庫第 {idx + 1} 格是空的，沒有點')
    depot_before = 20 - sum(d['empty'])
    if not click_card(idx, f'pet 選倉庫第 {idx + 1} 格'):
        return bad(EXIT_PANEL, '面板特徵不在，沒點倉庫格')
    g, ok = wait_for_card(idx, depot)
    if not ok:
        uikit.snap('pet-take-select')
        return bad(EXIT_DEPOT, f'點了倉庫第 {idx + 1} 格但選取框沒到那格；不點取出')
    idn = read_ident(ctx)
    nm = idn['name'] or (f'?({idn["growth"]})' if idn['growth'] else None)
    info['depot_name'] = nm
    if want and nm and not card_is(idn, want, species_reg(ctx)):
        return bad(EXIT_NAME, f'倉庫第 {idx + 1} 格是 {nm}，不是 {want}；沒取出（請人確認 --index）')
    ok, why = btn_ready('take')
    if not ok:
        uikit.snap('pet-take-btn')
        return bad(EXIT_DEPOT, f'取出鈕驗證失敗：{why}；不點')
    if not click(DEPOT_BTN_XY[0], DEPOT_BTN_XY[1], f'pet take {role} 倉庫第 {idx + 1} 格 {nm or ""}'):
        return bad(EXIT_PANEL, '面板特徵不在，沒點取出鈕')
    info['clicked'] = True
    uikit.mark('take click')
    ok, f2, d2 = wait_counts(depot, pets_empty - 1, depot_before - 1, info)
    if not ok:
        path = uikit.snap('pet-take-nochange')
        return bad(EXIT_VERIFY, f'點了取出但寵物欄 / 倉庫張數沒照預期變；不重點，請人看截圖{"：" + path if path else ""}')
    new_slot = free_slots[0]
    info['slot'] = new_slot
    rc = select_slot(new_slot - 1, f2)
    if rc:
        return bad(EXIT_VERIFY, f'取出後選不到新寵物所在的第 {new_slot} 格')
    idn2 = read_ident(ctx, 4, 1.0)
    nm2 = idn2['name'] or (f'?({idn2["growth"]})' if idn2['growth'] else None)
    info['name'] = nm2
    if idn2['growth']:                                         # 沒名字：縮圖確認物種（取出的新寵物縮圖在寵物欄，倉庫分頁也看得到）
        sp = ident_species(new_slot - 1, idn2['growth'], ctx)
        info['species'] = sp
        if sp and petmatch.learn_species(species_reg(ctx), sp, None, idn2['growth']):
            ctx['rdirty'] = True
        if want and sp != want and not (sp is None and card_is(idn2, want, species_reg(ctx))):
            return bad(EXIT_VERIFY, f'取出來的是 {nm2}（第 {new_slot} 格，物種 {sp}），不是預期的 {want}！停手交人處理，不自動存回')
    elif want and nm2 != want:
        return bad(EXIT_VERIFY, f'取出來的是 {nm2}（第 {new_slot} 格），不是預期的 {want}！停手交人處理，不自動存回')
    uikit.mark('take verified')
    print(f'pet：{role} 倉庫第 {idx + 1} 格 → 寵物欄第 {new_slot} 格：{nm2 or nm or "?"}（取出的寵物預設「等待」）')
    return 0


def roles_multi(arg: str) -> list | None:
    """'all' / 'DKBO,DKBO3'（逗號分隔多個角色）→ 白名單順序的角色清單；任一不認得 → None"""
    if str(arg).lower() == 'all':
        return role_list('all')
    out = []
    for t in str(arg).split(','):
        r = role_list(t.strip())
        if not r:
            return None
        if r[0] not in out:
            out.append(r[0])
    return out or None


def _many_prologue(role_arg: str, pets_text, depot: str, cmd: str, t0: float):
    roles = roles_multi(role_arg)
    names = [uikit.snap_pet(x) for x in pets_text]
    info = {'cmd': cmd, 'depot': depot, 'roles': roles, 'pets': names, 'ops': []}
    if not roles or depot not in ('personal', 'public') or not pets_text or None in names:
        bad = [t for t, n in zip(pets_text, names) if n is None]
        print(f'pet：{cmd} 參數不對（角色 {role_arg!r}、倉庫 {depot!r}、寵物名對不到 Monster 表：{bad}）', file=sys.stderr)
        return None, info
    return (roles, names), info


def store_many(role_arg: str, pets_text: list, depot: str = 'personal', allow_slot1: bool = False, allow_mount_store: list | None = None,
               skip_missing: bool = False, pause: bool = False, learn: bool = True, pick: str | None = None) -> int:
    """多角色 × 多寵物連續存倉：同一個 Session（面板只開一次）、每次直接點左欄頭像換角色（黃框 + 頭像名字驗證在 select_role）；
    每隻都走 store 同一套驗證（名字 / 縮圖 / 按鈕 / 計數 / 倉庫逐張找得到），失敗立即停（不重點）。
    騎寵只放行 allow_mount_store 名單內的名字（名字必須完全相同、且已是等待；第 1 格另需 allow_slot1）；其他規則同 store"""
    t0 = time.time()
    prep, info = _many_prologue(role_arg, pets_text, depot, 'store-many', t0)
    if prep is None:
        return _out(uikit.EXIT_USAGE, info, t0, '參數不對')
    roles, names = prep
    ams = [uikit.snap_pet(x) or x for x in (allow_mount_store or [])]
    for nm in names:
        if (nm in uikit.MOUNTS or uikit.is_mount_like(nm)) and nm not in ams:
            rc = uikit_fail(EXIT_FORBID, f'拒絕存倉：{nm} 是 / 像騎寵，--allow-mount-store 沒列它；零點擊')
            return _out(rc, info, t0, '騎寵不能存倉')
    ctx = load_ctx(learn)
    final = 0
    with Session(pause, need_calm=True) as s:
        if s.rc:
            return _out(s.rc, info, t0)
        try:
            for r in roles:
                for nm in names:
                    op = {'role': r, 'pet': nm, 'depot': depot, 'clicked': False}
                    info['ops'].append(op)
                    _back_to_pet_tab()
                    rc, slots = list_role(r, ctx)
                    if not rc:
                        sl, why = find_slot(slots, nm, None, pick)
                        if sl is None and skip_missing and not any(x.get('unnamed') and not x.get('species') for x in slots):
                            op['skipped'] = why
                            print(f'pet：{r} 沒有 {nm}，略過')
                            continue
                        rc = _store_body(r, nm, depot, sl['slot'] if sl else None, allow_slot1, ctx, op, nm if nm in ams else None, pre=(0, slots))
                    op['rc'] = rc
                    if rc:
                        final = rc
                        break
                if final:
                    break
        finally:
            save_ctx(ctx)
            _back_to_pet_tab()
    return _out(final, info, t0, next((o.get('msg', '') for o in info['ops'] if o.get('rc')), ''))


def take_many(role_arg: str, pets_text: list, depot: str = 'personal', skip_missing: bool = False, pause: bool = False, learn: bool = True) -> int:
    """多角色 × 多寵物連續取出（倉庫 → 寵物欄）：同 store_many，現場逐張找名字（沒名字的卡靠成長字串 → 登錄檔）、取出後驗新寵物"""
    t0 = time.time()
    prep, info = _many_prologue(role_arg, pets_text, depot, 'take-many', t0)
    if prep is None:
        return _out(uikit.EXIT_USAGE, info, t0, '參數不對')
    roles, names = prep
    ctx = load_ctx(learn)
    ctx['skip_missing'] = skip_missing
    final = 0
    with Session(pause, need_calm=True) as s:
        if s.rc:
            return _out(s.rc, info, t0)
        try:
            for r in roles:
                for nm in names:
                    op = {'role': r, 'pet': nm, 'depot': depot, 'clicked': False}
                    info['ops'].append(op)
                    _back_to_pet_tab()
                    rc = _take_body(r, depot, None, nm, ctx, op)
                    op['rc'] = rc
                    if rc and op.get('missing') and skip_missing:
                        op['skipped'] = op.pop('msg', '')
                        op['rc'] = 0
                        print(f'pet：{r} 倉庫沒有 {nm}，略過')
                        continue
                    if rc:
                        final = rc
                        break
                if final:
                    break
        finally:
            save_ctx(ctx)
            _back_to_pet_tab()
    return _out(final, info, t0, next((o.get('msg', '') for o in info['ops'] if o.get('rc')), ''))


def learn_species_cmd(role_arg: str, slot_no: int, species_text: str, confirm_growth: str, pause: bool = False) -> int:
    """登錄「這隻沒名字的寵物是 X 物種」：選取只讀（無副作用）。要求呼叫端給 --confirm-growth（= 該格名字框現在的成長字串，第二重確認，避免格位弄錯）、
    物種名必須在 Monster 表、該格必須真的是沒名字的寵物；縮圖已被別的物種樣板吻合 → 拒絕"""
    t0 = time.time()
    roles = role_list(role_arg)
    sp = uikit.snap_pet(species_text)
    info = {'cmd': 'learn-species', 'role': roles[0] if roles and len(roles) == 1 else None, 'slot': slot_no, 'species': sp}
    if not roles or len(roles) != 1 or not sp or not 1 <= slot_no <= 5:
        print('pet：learn-species 參數不對（單一角色、格 1～5、物種名要在 Monster 表）', file=sys.stderr)
        return _out(uikit.EXIT_USAGE, info, t0, '參數不對')
    role = roles[0]
    ctx = load_ctx(True)
    with Session(pause) as s:
        if s.rc:
            return _out(s.rc, info, t0)
        rc = select_role(role, ctx)
        if rc:
            return _out(rc, info, t0)
        f = scan_frames()
        if f is None or f['empty'][slot_no - 1]:
            rc = uikit_fail(EXIT_NAME, f'第 {slot_no} 格是空的或讀不到')
            return _out(rc, info, t0, '格位是空的')
        rc = select_slot(slot_no - 1, f)
        if rc:
            return _out(rc, info, t0)
        cur = read_slot(slot_no - 1, ctx)
        info['read'] = {k: cur.get(k) for k in ('name', 'unnamed', 'species', 'state')}
        if not cur.get('unnamed'):
            rc = uikit_fail(EXIT_NAME, f'第 {slot_no} 格不是「沒名字」的寵物（名字 {cur.get("name")}），不登錄')
            return _out(rc, info, t0, '不是沒名字的寵物')
        if cur['unnamed'] != confirm_growth.strip():
            rc = uikit_fail(EXIT_NAME, f'第 {slot_no} 格的成長字串是 {cur["unnamed"]}，與 --confirm-growth {confirm_growth} 不符，不登錄')
            return _out(rc, info, t0, '成長字串不符')
        cols = uikit.px(thumb_pts(slot_no - 1))
        reg = species_reg(ctx)
        if cols is None or (petmatch.species_by_thumb(cols, reg) not in (None, sp)):
            rc = uikit_fail(EXIT_NAME, '縮圖讀不到，或已被別的物種樣板吻合（標籤可疑），不登錄')
            return _out(rc, info, t0, '縮圖衝突')
        if petmatch.learn_species(reg, sp, cols, cur['unnamed']):
            ctx['rdirty'] = True
        save_ctx(ctx)
        print(f'pet：{role} 第 {slot_no} 格 {cur["raw_name"]} 登錄為 {sp}')
    return _out(0, info, t0)


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
    p = sub.add_parser('store', help='寵物 → 倉庫（騎寵 / 第 1 格 / 騎乘中一律拒絕）', parents=[cp])
    p.add_argument('role')
    p.add_argument('pet')
    p.add_argument('--depot', default='personal', choices=['personal', 'public'])
    p.add_argument('--slot', type=int, default=None, help='同名多隻時指定第幾格（1 起算）')
    p.add_argument('--allow-slot1', action='store_true', help='允許存第 1 格的寵物（仍擋騎寵 / 騎乘中）')
    p.add_argument('--allow-mount-store', default=None, metavar='名字', help='只放行名字完全等於此值的騎寵存倉（須已是等待；第 1 格另加 --allow-slot1）；只有使用者當次明講才用')
    p = sub.add_parser('store-many', help='多角色 × 多寵物連續存倉（同一個面板 session，直接換頭像）', parents=[cp])
    p.add_argument('--role', required=True, help='all 或逗號分隔 DKBO,DKBO3')
    p.add_argument('--pets', required=True, help='寵物名（逗號分隔）；沒名字的新寵物用物種名（須已 learn-species）')
    p.add_argument('--depot', default='personal', choices=['personal', 'public'])
    p.add_argument('--allow-slot1', action='store_true')
    p.add_argument('--allow-mount-store', default=None, metavar='名,名', help='放行存倉的騎寵名單（名字完全相同、須已是等待）；只有使用者當次明講才用')
    p.add_argument('--skip-missing', action='store_true', help='角色沒有這隻就略過（預設 72 停手）')
    p.add_argument('--pick', default=None, choices=['first', 'last'], help='同物種有多隻時取最前 / 最後一格（預設 72 停手）')
    p = sub.add_parser('take-many', help='多角色 × 多寵物連續取出（現場逐張找名字）', parents=[cp])
    p.add_argument('--role', required=True)
    p.add_argument('--pets', required=True)
    p.add_argument('--depot', default='personal', choices=['personal', 'public'])
    p.add_argument('--skip-missing', action='store_true')
    p = sub.add_parser('learn-species', help='登錄「某格沒名字的寵物是什麼物種」（縮圖 + 成長字串）', parents=[cp])
    p.add_argument('role')
    p.add_argument('slot', type=int)
    p.add_argument('species')
    p.add_argument('--confirm-growth', required=True, metavar='49/9/8/2', help='該格名字框現在的成長字串（第二重確認）')
    p = sub.add_parser('take', help='倉庫第 N 格 → 寵物欄（取出的寵物預設等待）', parents=[cp])
    p.add_argument('role')
    p.add_argument('--depot', default='personal', choices=['personal', 'public'])
    p.add_argument('--index', type=int, default=None, help='倉庫格 1～20（列優先，每列 5 格）')
    p.add_argument('--pet', default=None, help='不給格號：現場逐張找這個名字（沒名字的卡靠成長字串登錄檔）')
    p.add_argument('--expect', default=None, help='預期的寵物名（取出前 / 後都驗，不符不自動存回）')
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
    if a.cmd == 'store':
        return store(a.role, a.pet, a.depot, a.slot, a.allow_slot1, a.pause_encounter, learn, a.allow_mount_store)
    if a.cmd == 'take':
        return take(a.role, a.depot, a.index, a.expect, a.pause_encounter, learn, a.pet)
    csv = lambda t: [x.strip() for x in (t or '').split(',') if x.strip()]    # noqa: E731
    if a.cmd == 'store-many':
        return store_many(a.role, csv(a.pets), a.depot, a.allow_slot1, csv(a.allow_mount_store), a.skip_missing, a.pause_encounter, learn, a.pick)
    if a.cmd == 'take-many':
        return take_many(a.role, csv(a.pets), a.depot, a.skip_missing, a.pause_encounter, learn)
    if a.cmd == 'learn-species':
        return learn_species_cmd(a.role, a.slot, a.species, a.confirm_growth, a.pause_encounter)
    split = lambda t: None if t is None else [x.strip() for x in t.split(',') if x.strip()]    # noqa: E731
    return rest_all(a.role, split(a.keep), split(a.only), a.dry_run, a.pause_encounter, learn)


if __name__ == '__main__':
    sys.exit(main())
