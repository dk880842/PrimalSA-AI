#!/usr/bin/env python3
"""寵物面板腳本化（P6：list / set-state / rest-all；P7：store / take）。計畫：notes/plan-scriptify.md §5。只用標準函式庫。

用法（專案根目錄；WSL / Windows 原生指令相同；角色名 DKB0 / DKBO 都收，輸出用真名 DKBO）：
  uv run --no-project python tools/gui/pet.py list [--role DKBO|all] [--json]           # 唯讀：每格 名字 / 狀態 / 等級
  uv run --no-project python tools/gui/pet.py levels [--role all] [--slots 2,3,4,5] [--json]   # 唯讀：只讀等級 + 名字框點陣指紋 nh（練寵輪詢；不認名字）
  uv run --no-project python tools/gui/pet.py set-state DKBO 迪基格斯 出戰|等待|騎乘 [--slot N] [--allow-mount]
  uv run --no-project python tools/gui/pet.py rest-all [--role all] [--keep 瑪斯貝卡] [--only 名,名] [--dry-run]
  uv run --no-project python tools/gui/pet.py store DKBO 迪基格斯 [--depot personal|public] [--slot N] [--allow-slot1] [--allow-mount-store 名字]
  uv run --no-project python tools/gui/pet.py take DKBO --depot personal --index N --expect 迪基格斯|--expect-growth 35/7/3/8|--expect-level 126   # --index 一定要配 --expect-*（不准盲取）
  uv run --no-project python tools/gui/pet.py store-many --role all|DKBO,DKBO3 --pets 迪基格斯,瑪斯貝卡 [--depot personal|public] [--allow-slot1] [--allow-mount-store 瑪斯貝卡] [--skip-missing] [--pick first|last]
  uv run --no-project python tools/gui/pet.py take DKBO --depot public --pet 朵拉比斯        # 不給格號：現場逐張選卡讀名字找（沒名字的卡靠成長字串登錄檔）
  uv run --no-project python tools/gui/pet.py take-many --role all --pets 朵拉比斯 [--depot personal|public] [--skip-missing]
  uv run --no-project python tools/gui/pet.py take-many --depot public --plan "DKBO2:克邦凱斯,DKBO3:#35/7/3/8,DKBO:朵拉比斯@126"   # 每人不同目標
  uv run --no-project python tools/gui/pet.py set-state-many --role all 朵拉比斯 出戰 [--allow-mount]   # 多人同一隻寵物改狀態（面板只開一次）
  批次（2026-10-12）：面板開一次 → 倉庫分頁 / 子分頁切一次 → 左欄頭像換角色連續做 → 關一次。目標字串 = 名字 / 名字@等級 / #成長字串 / 名字#成長字串@等級
  uv run --no-project python tools/gui/pet.py learn-species DKBO2 1 布拉奇多斯 --confirm-growth 49/9/8/2   # 登錄「這格沒名字的寵物是什麼物種」（縮圖 + 成長字串）
  uv run --no-project python tools/gui/pet.py depot-list --depot public[,personal] [--role DKBO2,DKBO3] [--candidates 魯尼帖斯,貝魯卡]   # 唯讀：倉庫卡片 + 各物種張數（只選卡不存取）
  名字框讀不出（2026-10-14 40/9/6/5：Windows OCR 把「40」讀成「姍」）：先加讀 -Zooms 5,6；仍讀不出 → list 給 unreadable=True、guess=候選字串（只有一種完整字串、
    其餘行不矛盾），候選字串已登錄成 X 且縮圖也認成 X（且 X 不是騎寵）→ 當作沒名字的 X（species_src='img+reg-guess'，store / take 身分可用）；
    learn-species 對讀不出的格也可用（只收第 2～5 格、等待中、非騎寵，--confirm-growth 要跟現場 OCR 行不矛盾、縮圖不矛盾）
  共用旗標：--pause-encounter（先關原地遇敵、等戰鬥結束，做完再開回；預設不動遇敵，戰鬥中直接退 78）、--no-learn（不學樣板）、--no-img（不用縮圖認物種）、--timing、
    --no-icache（不用身分跨程序快取：成長字串以名字框點陣完全相同為鍵、縮圖結果以整格像素 + 候選為鍵；只在 list / levels / set-state-many / rest-all 用，
    存倉 / 取出 / 丟寵 / learn-species 一律現場 OCR；tools/.cache/pet-tpl/ident-cache-<版面>.json，7 天過期，2026-10-13 review 1013b §1.1）、
    --candidates 物種,物種（任務候選：沒名字的寵物 / 倉庫卡只在這些之間比縮圖，inlier + 主色都同意才算；有把握且登錄檔不矛盾 → 當 species，2026-10-13 卡坦 4 鯊 / 4 雞）
  最後一行一律印 JSON：{"ok", "rc", ...}；給其他腳本 import：pet.list_roles / set_state / rest_all 回退出碼，結果 dict 在 pet.LAST。

做法（P-I5 實測 2026-10-11，數據見 notes/plan-scriptify.md）：
  - 面板內一律經 uikit.safe_click（面板沒開 → 不點；紅區 FORBIDDEN 一律 ForbiddenClick）。**面板沒開絕不點頭像**（會點到任務追蹤）。
  - 選角色：點左欄頭像 → 黃框（頭像上緣 x=83）必須「剛好只有該角色」；頭像下名字有樣板就要吻合（沒有樣板就學一次）。
  - 空格：爪印 4 點顏色；選中：格子左邊框黃色；**點空格不會改變選取**（畫面仍停在上一隻寵物，所以不能靠名字判斷空格）。
  - 名字：petmatch 整塊圖樣板（同名 IoU = 1.000）→ 沒樣板才 OCR（-Dark 0 -Zooms 2,3,4 精確命中 Monster 表才學）；
    等級：黃字切字 + 單字樣板 → 沒樣板才 OCR（三組設定共識、且跟樣板認得的字不矛盾才採用 / 學；level_from_rows）。名字 / 等級都讀不出來 → None，**不猜**。
    2026-10-13：實機等級樣板被 OCR 錯值污染（'1' 混進 3 / 9、'轉' 混進 2）→ load_ctx 讀檔時 petmatch.prune_digits 自動清、有清就寫回。
  - 狀態：下方三顆鈕（出戰 / 騎乘 / 休息）亮的（棕底）就是目前狀態。
  - 騎寵（uikit.MOUNTS = 瑪斯貝卡 / 布拉奇多斯）：名字「像」騎寵（is_mount_like，鬆）或狀態 = 騎乘 → set-state / rest-all 不動（73），要動需 --allow-mount。

縮圖認物種（2026-10-12 接線 petimg_match）：read_slot 名字樣板 / OCR / 登錄檔都認不出時，比寵物格縮圖與知識庫頭像 → img_species / img_score /
  species_src='img'（只當顯示與「更嚴」騎寵判斷，不寫進 species，store / set-state 身分不放寬）；take 找卡 / 取前 / 取後驗名在名字框認不出時可用（img_target）。--no-img 關。
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
import hashlib  # noqa: E402
import json  # noqa: E402
import re  # noqa: E402
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
OCR_GROWTH_EXTRA = ('-Dark', 0, '-Zooms', '5,6')     # 名字框像成長字串但兩組都湊不齊時加讀一組：2026-10-14 實測 40/9/6/5 在 -Zooms 2 / 4 讀成「姍/9/6/5」「姍/6/5」，
                                                     # 只有 3 倍讀對（1 行不夠 parse_growth 採用）→ 5,6 倍也讀對 → 2 行同意
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
    exact_names = [e for e in (_exact(t) for t in raw) if e]            # 倉庫分頁名字框 OCR 常噪：至少 2 行「精確命中 Monster 表」且是同一個名字才採用（2026-10-12 #258 朵拉比斯）
    if exact_names and len(set(exact_names)) == 1 and len(exact_names) >= 2:
        return exact_names[0], raw, False
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


def level_from_rows(lvl_rows, ctx: dict) -> tuple:
    """選中寵物「0轉N」黃字點陣 → (等級或 None, 來源)。來源：'tpl'（單字樣板）/ 'ocr'（三組 OCR 共識、且不跟樣板認得的字矛盾）/
    None（沒墨點或讀不到）/ 'ocr-conflict:N'（OCR 共識 N 跟畫面上認得的字矛盾 → 不採用，回 None）。讀不準一律 None，不回錯值。
    OCR 值要學樣板時再截一次確認畫面沒變（learn_level 本身也會拒絕可疑標籤）。petwatch 也用這支（同一套規則）"""
    tpl = ctx['tpl']
    lv = petmatch.read_level(lvl_rows, tpl)
    if lv is not None:
        return lv, 'tpl'
    if petmatch.ink(lvl_rows) < petmatch.MIN_INK['lvl']:
        return None, None
    v = ocr_level_consensus()
    if v is None:
        return None, None
    if not petmatch.level_consistent(lvl_rows, v, tpl):
        log(f'等級 OCR 共識 {v} 跟樣板認得的字矛盾 → 不採用（回 None）')
        return None, f'ocr-conflict:{v}'
    if ctx.get('learn'):
        again, _ = petmatch.grab([petmatch.BOX_LVL + ('lvl',)])
        if again and again[0] == lvl_rows and petmatch.learn_level(lvl_rows, v, tpl):
            ctx['dirty'] = True
    return v, 'ocr'


# ---- 身分跨程序快取（2026-10-13 review 1013b §1.1）：同一張點陣不再 OCR / 比縮圖第二次 ----
# 沒名字的寵物（騎寵布拉奇多斯、剛抓的任務寵）每讀一格要 OCR 成長字串（2 組設定）+ 縮圖比對約 2.5～3 秒，petquest 每段都是新的 pet.py 子程序。
# 快取只做「完全相同的輸入 → 上次的結果」：成長字串以名字框二值化點陣（完全相同）為鍵、縮圖結果以整格 4537 點像素 + 候選名單為鍵，
# 不改任何判定規則；OCR 讀錯的字串本來就過不了 parse_growth（≥ 2 行相同），不會進快取。
# 只在 list / levels / set-state-many / rest-all 開（load_ctx(use_icache=True)）；store / take / petdrop / learn-species / rebirth_pets（抓寵登錄）
# 一律現場 OCR，不用快取（丟寵、存倉的現場驗名不變）。檔案：petmatch.TPL_DIR / ident-cache-<版面>.json，含版本、每筆時間（7 天過期、各留最近 400 筆）。
ICACHE_VER = 1
ICACHE_TTL_S = 7 * 24 * 3600
ICACHE_MAX = 400


def rows_key(rows) -> str | None:
    """二值化點陣列 → 穩定的 hash（跨程序相同；Python 內建 hash() 每個程序不同不能用）"""
    return hashlib.sha1('\n'.join(rows).encode()).hexdigest()[:24] if rows else None


def icache_path() -> Path:
    return petmatch.TPL_DIR / f'ident-cache-{petmatch.LAYOUT}.json'


def load_icache(now: float | None = None) -> dict:
    """→ {'growth': {點陣鍵: [成長字串, ts]}, 'img': {像素鍵: [結果 dict, ts]}}；版本不符 / 壞檔 → 空；過期的丟掉"""
    now = time.time() if now is None else now
    try:
        d = json.loads(icache_path().read_text(encoding='utf-8'))
    except (OSError, ValueError):
        d = {}
    if not isinstance(d, dict) or d.get('ver') != ICACHE_VER:
        d = {}
    out = {}
    for sec in ('growth', 'img'):
        v = d.get(sec) if isinstance(d.get(sec), dict) else {}
        out[sec] = {k: e for k, e in v.items() if isinstance(e, list) and len(e) == 2 and now - (e[1] or 0) <= ICACHE_TTL_S}
    return out


def save_icache(c: dict) -> None:
    d = {'ver': ICACHE_VER}
    for sec in ('growth', 'img'):
        items = sorted((c.get(sec) or {}).items(), key=lambda kv: kv[1][1])[-ICACHE_MAX:]
        d[sec] = dict(items)
    p = icache_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix('.tmp')
    tmp.write_text(json.dumps(d, ensure_ascii=False), encoding='utf-8')
    tmp.replace(p)


def icache(ctx: dict) -> dict | None:
    """ctx 有開快取（use_icache）→ 快取 dict（第一次用才讀檔）；沒開 → None"""
    if not ctx.get('use_icache'):
        return None
    if 'icache' not in ctx:
        ctx['icache'] = load_icache()
    return ctx['icache']


def icache_put(ctx: dict, sec: str, key, val) -> None:
    c = icache(ctx)
    if c is None or key is None:
        return
    c[sec][key] = [val, time.time()]
    ctx['idirty'] = True


def growth_known(name_rows, ctx: dict) -> bool:
    """這張名字框點陣已知是成長字串（本程序讀過 / 快取有）→ 不是被橫幅蓋住的名字（read_slot 不必等橫幅重讀）"""
    k = rows_key(name_rows)
    return k is not None and (k in ctx.get('gcache', {}) or k in ((icache(ctx) or {}).get('growth') or {}))


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
    key = rows_key(name_rows)
    if key is not None and key in gc:
        return {'name': None, 'via': 'growth', 'raw': None, 'growth': gc[key]}
    hit = ((icache(ctx) or {}).get('growth') or {}).get(key) if key else None
    if hit:                                                     # 跨程序快取：點陣完全相同 = 畫面文字完全相同
        gc[key] = hit[0]
        ctx['icache_hits'] = ctx.get('icache_hits', 0) + 1
        return {'name': None, 'via': 'growth', 'raw': None, 'growth': hit[0], 'cached': True}
    if petmatch.ink(name_rows) >= petmatch.MIN_INK['name']:
        nm, raw, exact = ocr_pet_name()
        if not nm:
            g = petmatch.parse_growth(raw)
            if not g and petmatch.growth_like(raw):               # 像成長字串但湊不齊（兩位數被讀成漢字）→ 加讀一組放大倍數（見 OCR_GROWTH_EXTRA）
                raw = raw + [t for t in _petwatch().ocr(petmatch.BOX_NAME, *OCR_GROWTH_EXTRA) if uikit._pet_key(t)]
                g = petmatch.parse_growth(raw)
            if g:
                gc[key] = g
                icache_put(ctx, 'growth', key, g)
                return {'name': None, 'via': 'growth', 'raw': raw, 'growth': g}
            guess = petmatch.growth_guess(raw)                     # 仍讀不出：只留候選字串（read_slot 要「已登錄 + 縮圖同物種」才採用）
            if guess:
                return {'name': None, 'via': None, 'raw': raw, 'growth': None, 'guess': guess}
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
    """沒名字的寵物（在寵物欄第 i 格，0 起算）→ 物種：縮圖簽名 + 成長字串登錄檔多重確認；沒登錄 = None（不猜）。
    有任務候選（ctx['img_only']，--candidates / pet_catch register）時改成：候選內相對比較（petimg_match.rank_among，inlier + 主色）
    有把握 → 登錄檔沒記這個字串、或記的是同一隻 → 採用；登錄檔記的是別隻 → 矛盾 None。沒把握 → 退回舊規則。
    （2026-10-13 卡坦 4 鯊 / 4 雞是換色版：16 點縮圖簽名分不開 → 舊規則常 None，只好人工比腹部顏色）"""
    reg = species_reg(ctx)
    if ctx.get('img_only'):
        im = img_ident('slot', i, ctx)
        if im:
            ctx.setdefault('img_cache', {})[i] = im
            sp = im.get('img_species')
            sg = (reg.get('growth') or {}).get(growth) if growth else None
            if sp:
                return sp if sg in (None, sp) else None
    cols = uikit.px(thumb_pts(i))
    return petmatch.identify_species(cols, growth, reg)


# ---- 縮圖 ↔ 知識庫頭像（petimg_match，2026-10-12 接線）：名字 / 成長字串登錄檔都認不出時的物種備援 ----
# 結果只放 img_species / img_score / species_src='img'，**不寫進 species**：species 是 store / set-state / take / rebirth_pets 的身分依據，
# img 只當顯示與「更嚴」的騎寵判斷（img 認成騎寵 → mountlike），不放寬任何不可逆動作的驗名。
IMG_ON = True                                  # --no-img 關；fake_pet.install 也關（假面板沒畫頭像）
IMG_ONLY: list | None = None                   # --candidates：任務候選物種（縮圖只在這些之間相對比較；load_ctx 預設帶入）
IMG_EXTRA = ['朵拉比斯', '迪基格斯', '金布伊']
ICACHE_ON = True                               # --no-icache 關（身分跨程序快取，見 rows_key 上方說明）    # 一定放進候選的常用物種（另加騎寵、名字樣板、物種登錄檔裡的）


def img_candidates(ctx: dict) -> list:
    """第一輪候選：騎寵 + IMG_EXTRA + 名字樣板學過的 + 物種登錄檔裡的（只留有頭像的）；ctx 快取"""
    if 'img_names' not in ctx:
        import petimg_match
        reg = species_reg(ctx)
        names = list(uikit.MOUNTS) + IMG_EXTRA + list((ctx.get('tpl') or {}).get('name') or {}) \
            + list(reg.get('thumb') or {}) + list((reg.get('growth') or {}).values())
        have = {n for ns in petimg_match.index().values() for n in ns}
        ctx['img_names'] = [n for n in dict.fromkeys(names) if n in have]
    return ctx['img_names']


def img_match(cells, kind: str, cx: int, cy: int, ctx: dict) -> dict:
    """已讀好的一格像素 → {'img_species'（ok 才有值，否則 None）, 'img_score', 'img_best', 'img_second', 'img_stage'}。
    第 1 輪已知物種；過門檻 → 第 2 輪加上第一名的同系別（換色版）再比一次，以第 2 輪為準（避免只有兄弟在候選時誤認）；
    第 1 輪連門檻都沒過（真物種不在已知清單）→ 放寬到全部 Monster（每格多約 1.3 s）。都不 ok → None，不猜"""
    import petimg_match as M
    if ctx.get('img_only'):                                  # 任務候選：只在候選之間相對比較（+ 主色），不擴到同系 / 全部 Monster
        r = M.rank_among(cells, kind, cx, cy, ctx['img_only'])
        return {'img_species': r['species'] if r['ok'] else None, 'img_score': r['score'], 'img_best': r['best_species'],
                'img_second': [r['second_species'], r['second']], 'img_hist': [r['hist'], r['hist_second']], 'img_stage': 'task'}
    known = img_candidates(ctx)
    r, stage = M.match(cells, kind, cx, cy, known), 'known'
    if r['score'] >= M.MIN_SCORE[kind]:
        fam = list(dict.fromkeys(known + M.family([r['best_species']])))
        if len(fam) > len(known):
            r, stage = M.match(cells, kind, cx, cy, fam), 'family'
    else:
        r, stage = M.match(cells, kind, cx, cy, None), 'all'
    return {'img_species': r['species'] if r['ok'] else None, 'img_score': r['score'], 'img_best': r['best_species'],
            'img_second': [r['second_species'], r['second']], 'img_stage': stage}


def img_ident(kind: str, idx: int, ctx: dict) -> dict | None:
    """現場讀寵物欄第 idx 格（kind='slot'）/ 倉庫第 idx 張卡（'card'）縮圖認物種（唯讀；一次 uikit.px 約 7000 點）。
    IMG_ON 關、沒有頭像匯出（tools/.cache/pet-images）、讀不到像素 → None"""
    if not IMG_ON or ctx.get('no_img'):
        return None
    try:
        import petimg_match as M
        M.index()
    except (OSError, ImportError) as e:
        if not ctx.get('img_warned'):
            log(f'縮圖認物種停用（{e}；先跑 tools/extract/pet_images.py）')
            ctx['img_warned'] = True
        return None
    _, cx, cy = M.cells_of(kind)[idx]
    t = time.time()
    cells = M.read_cell(kind, cx, cy)
    if cells is None:
        return None
    ikey = None
    if icache(ctx) is not None:                              # 跨程序快取：整格像素 + 候選名單完全相同 → 比對結果必然相同
        names = ctx.get('img_only') or img_candidates(ctx)
        h = hashlib.sha1(f'{kind}|{cx},{cy}|{",".join(names)}|'.encode())
        for pt in sorted(cells):
            h.update(bytes(int(v) & 255 for v in cells[pt]))
        ikey = h.hexdigest()[:24]
        hit = ctx['icache']['img'].get(ikey)
        if hit:
            ctx['icache_hits'] = ctx.get('icache_hits', 0) + 1
            r = dict(hit[0], img_ms=int((time.time() - t) * 1000), img_cached=True)
            uikit.mark(f'img {kind} {idx + 1} (cache)')
            return r
    try:
        r = img_match(cells, kind, cx, cy, ctx)
    except KeyError as e:                                   # --candidates 給了知識庫頭像沒有的名字
        if not ctx.get('img_warned'):
            log(f'縮圖認物種：{e}')
            ctx['img_warned'] = True
        return None
    r['img_ms'] = int((time.time() - t) * 1000)
    if ikey:
        icache_put(ctx, 'img', ikey, {k: v for k, v in r.items() if k != 'img_ms'})
    uikit.mark(f'img {kind} {idx + 1}')
    return r


def slot_ident(sl: dict):
    """格子的有效身分名：有名字用名字；沒名字但物種已確認 → 物種；否則 None"""
    return sl.get('name') or (sl.get('species') if sl.get('unnamed') else None)


def ident_matches(ident: dict, sl: dict) -> bool:
    """現場讀到的名字框（resolve_ident 結果）是不是 sl 這隻：有名字比名字；沒名字比成長字串（同一隻固定）。
    sl 是「名字框讀不出、靠候選字串 + 登錄檔 + 縮圖」認的（sl['guess']）→ 現場也讀不出時比候選字串"""
    if sl.get('unnamed'):
        if ident.get('growth') == sl['unnamed']:
            return True
        return sl.get('guess') == sl['unnamed'] and not ident.get('growth') and ident.get('guess') == sl['unnamed']
    return bool(sl.get('name')) and ident.get('name') == sl['name']


# ---- 名字框讀不出時的身分確認（寵物分頁 / 倉庫分頁 / 倉庫卡共用，2026-10-14）----
# 規則只有一條：候選成長字串（現場讀到的 guess，或呼叫端已知的字串）跟現場 OCR 每一行都不矛盾、已登錄成物種 X、
# 現場縮圖（寵物格 / 倉庫卡，petimg_match）也認成 X、X 不是騎寵 → X。少任一條 → None（不猜）。只有縮圖照舊不算。
def candidate_species(lines, cands, img_species, reg: dict) -> str | None:
    """純函式：見上方規則。lines = 名字框 OCR 原文（None / 空 = 不比對 OCR，只給 read_slot 已確認過的 guess 用）"""
    growth = reg.get('growth') or {}
    hits = {growth.get(g) for g in cands or [] if g and growth.get(g) and (not lines or petmatch.growth_consistent(lines, g))}
    if len(hits) != 1:
        return None
    x = hits.pop()
    return x if x not in uikit.MOUNTS and img_species == x else None


def guess_species(d: dict, reg: dict) -> str | None:
    """純函式：名字框讀不出的格（read_slot 的 d，有 unreadable + guess）→ 物種或 None（candidate_species，縮圖 = d['img_species']）"""
    if not d.get('unreadable') or d.get('name') or d.get('unnamed') or not d.get('guess'):
        return None
    return candidate_species(d.get('ocr'), [d['guess']], d.get('img_species'), reg)


def unreadable_species(idn: dict, kind: str, idx: int, ctx: dict, cands=()) -> str | None:
    """現場名字框（resolve_ident 結果）讀不出（沒名字、沒成長字串）→ candidate_species(現場 OCR, [guess] + cands, 現場縮圖)。
    kind / idx = 現場縮圖位置（'slot' 寵物格 0 起算 / 'card' 倉庫卡 0 起算）。有名字或成長字串 → None（照原本規則比）。
    候選都沒登錄 → 不讀縮圖直接 None"""
    if idn.get('name') or idn.get('growth') or not idn.get('raw'):
        return None
    cs = [g for g in dict.fromkeys([idn.get('guess'), *cands]) if g]
    reg = species_reg(ctx)
    if not any((reg.get('growth') or {}).get(g) for g in cs):
        return None
    im = img_ident(kind, idx, ctx)
    return candidate_species(idn['raw'], cs, im and im.get('img_species'), reg)


def ident_confirms(ident: dict, sl: dict, kind: str, idx: int, ctx: dict) -> bool:
    """現場名字框 ident 是不是 sl 這隻（store 存前 / 存後找卡共用）：ident_matches；或名字框讀不出時，
    sl 的成長字串跟現場 OCR 不矛盾（現場的 guess 若有也要相同）+ 登錄成 sl 的物種 + 現場縮圖同物種（unreadable_species）"""
    if ident_matches(ident, sl):
        return True
    g, sp = sl.get('unnamed'), sl.get('species')
    if not (g and sp) or ident.get('guess') not in (None, g):
        return False
    return unreadable_species(dict(ident, guess=None), kind, idx, ctx, [g]) == sp


def unreadable_target(idn: dict, kind: str, idx: int, t: dict, ctx: dict) -> bool:
    """take 的身分確認（找卡 / 取前 / 取後共用）：名字框讀不出時 unreadable_species 認出的物種 == 目標名字；
    目標有成長字串時候選只用它、且現場 OCR 要跟它不矛盾。目標沒名字也沒字串（只給等級）→ False（照原規則）"""
    if not (t.get('name') or t.get('growth')):
        return False
    if t.get('growth'):
        if idn.get('guess') not in (None, t['growth']):
            return False
        sp = unreadable_species(dict(idn, guess=None), kind, idx, ctx, [t['growth']])
    else:
        sp = unreadable_species(idn, kind, idx, ctx)
    return bool(sp) and t.get('name') in (None, sp)


def read_slot(i: int, ctx: dict) -> dict:
    """目前選中的寵物（已確認是第 i 格）→ {'slot','name','via','ocr','state','level','lv_via','mountlike'}"""
    tpl = ctx['tpl']
    probes = [p for s in STATES for p in BTN_PROBES[s]]
    for attempt in range(BANNER_RETRIES + 1):
        rows, extra = petmatch.grab([petmatch.BOX_NAME + ('name',), petmatch.BOX_LVL + ('lvl',)], extra=probes)
        if rows is None:
            break
        known = (tpl.get('name') and petmatch.match_whole('name', rows[0], tpl)[0] is None and not growth_known(rows[0], ctx)) \
            or (tpl.get('digit') and petmatch.read_level(rows[1], tpl) is None)
        if not known or attempt == BANNER_RETRIES:
            break
        uikit.sleep(BANNER_WAIT_S)              # 樣板都有卻對不上：多半是 EXP 橫幅 / 浮字蓋住（掛機中常見），等它消失再讀
        uikit.mark('banner-retry')
    d = {'slot': i + 1, 'empty': False, 'name': None, 'via': None, 'state': None, 'level': None}
    ctx.pop('img_cache', None)                             # 縮圖結果只給「這一格」用（ident_species → 下面的補充顯示）
    if rows is None:
        d['err'] = '讀不到像素'
        return d
    d['state'] = btn_state({s: extra[2 * k:2 * k + 2] for k, s in enumerate(STATES)})
    name_rows, lvl_rows = rows
    d['nh'] = rows_key(name_rows)                            # 名字框點陣指紋：levels 輪詢比對「同一格還是同一隻」用
    ident = resolve_ident(name_rows, ctx)
    d['name'], d['via'], raw = ident['name'], ident['via'], ident['raw']
    if raw:
        d['ocr'] = raw
    if ident['growth']:                                  # 沒名字的新寵物：成長字串 = 這隻的身分；物種由縮圖 / 登錄檔確認
        d['unnamed'] = ident['growth']
        d['raw_name'] = f'?({ident["growth"]})'
        d['species'] = ident_species(i, ident['growth'], ctx)
    elif not d['name'] and petmatch.ink(name_rows) >= petmatch.MIN_INK['name']:     # 名字框有字但名字 / 成長字串都讀不出（2026-10-14 40/9/6/5）
        d['unreadable'] = True
        if ident.get('guess'):
            d['guess'] = ident['guess']
    lv, via = level_from_rows(lvl_rows, ctx)
    if lv is not None:
        d['level'], d['lv_via'] = lv, via
    elif via:
        d['lv_reject'] = via
    if d.get('species'):
        d['species_src'] = 'reg'
    if d.get('species') and (ctx.get('img_cache') or {}).get(i, {}).get('img_species') == d['species']:
        d.update(ctx['img_cache'][i])
        d['species_src'] = 'img+reg' if species_reg(ctx).get('growth', {}).get(d.get('unnamed')) else 'img'
    if not d['name'] and not d.get('species'):              # 名字樣板 / OCR / 物種登錄檔都認不出 → 縮圖比知識庫頭像（只當補充，見 img_ident）
        im = (ctx.get('img_cache') or {}).get(i) or img_ident('slot', i, ctx)
        if im:
            d.update(im)
            if im['img_species']:
                d['species_src'] = 'img'
    gs = guess_species(d, species_reg(ctx))
    if gs:                                                   # 名字框讀不出：候選字串已登錄 + 縮圖同物種 → 當作沒名字的該物種（store / take 身分可用）
        d.update(unnamed=d['guess'], raw_name=f'?({d["guess"]})', species=gs, species_src='img+reg-guess')
    ocr_texts = ([d['name']] if d['name'] else []) + d.get('ocr', [])
    d['mountlike'] = any(uikit.is_mount_like(t) for t in ocr_texts) or d.get('species') in uikit.MOUNTS \
        or d.get('img_species') in uikit.MOUNTS                # img 認成騎寵只會更嚴（多擋），不會放行
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


def load_ctx(learn: bool, img_only=None, use_icache: bool = False) -> dict:
    """讀樣板（順手清掉被錯標籤污染的等級單字樣板，有清就標 dirty、save_ctx 時寫回）。
    img_only = 縮圖認物種只在這些物種之間做相對比較（任務候選，例：卡坦 4 鯊 / 4 雞；見 img_match）。
    use_icache = 開身分跨程序快取（只給唯讀 / 改狀態的指令；存倉 / 取出 / 丟寵不開，見 ICACHE_VER 上方說明）"""
    tpl = petmatch.load_tpl()
    pruned = petmatch.prune_digits(tpl)
    if pruned:
        log(f'等級單字樣板清掉 {len(pruned)} 個可疑變體：{pruned}')
    ctx = {'tpl': tpl, 'learn': learn, 'dirty': bool(pruned), 'use_icache': bool(use_icache) and ICACHE_ON}
    img_only = img_only or IMG_ONLY
    if img_only:
        ctx['img_only'] = list(img_only)
    return ctx


def save_ctx(ctx: dict) -> None:
    if ctx.get('idirty'):
        try:
            save_icache(ctx['icache'])
        except OSError as e:
            log(f'身分快取存檔失敗：{e}')
        ctx['idirty'] = False
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
    nm = s.get('name') or (s.get('raw_name', '?') + (f'≈{s["species"]}' if s.get('species') else
                                                      f'≈{s["img_species"]}(圖{s["img_score"]:.2f})' if s.get('img_species') else ''))
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
    ctx = load_ctx(learn, use_icache=True)
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
    info['icache_hits'] = ctx.get('icache_hits', 0)
    return _out(0, info, t0)


def read_level_slot(i: int, ctx: dict) -> dict:
    """目前選中的寵物（已確認是第 i 格）→ 只讀等級：{'slot','empty','level','lv_via','nh'}（nh = 名字框點陣指紋，不認名字 / 身分、不 OCR 名字）。
    等級樣板對不上時照 read_slot 等 EXP 橫幅消失再讀（最多 BANNER_RETRIES 次）"""
    tpl = ctx['tpl']
    rows = None
    for attempt in range(BANNER_RETRIES + 1):
        rows, _ = petmatch.grab([petmatch.BOX_NAME + ('name',), petmatch.BOX_LVL + ('lvl',)])
        if rows is None or not tpl.get('digit') or petmatch.read_level(rows[1], tpl) is not None or attempt == BANNER_RETRIES:
            break
        uikit.sleep(BANNER_WAIT_S)
        uikit.mark('banner-retry')
    d = {'slot': i + 1, 'empty': False, 'level': None}
    if rows is None:
        d['err'] = '讀不到像素'
        return d
    d['nh'] = rows_key(rows[0])
    lv, via = level_from_rows(rows[1], ctx)
    if lv is not None:
        d['level'], d['lv_via'] = lv, via
    elif via:
        d['lv_reject'] = via
    return d


def levels_role(role: str, ctx: dict, slots=None) -> tuple:
    """面板已開：選角色 → 每個非空格（slots 有給 = 只讀這些格，1 起算）選取 + 只讀等級 → (rc, [格])。不改任何狀態"""
    rc = select_role(role, ctx)
    if rc:
        return rc, []
    f = scan_frames()
    if f is None:
        return uikit_fail(EXIT_PANEL, '讀不到面板像素'), []
    out = []
    for i in range(5):
        if f['empty'][i]:
            out.append({'slot': i + 1, 'empty': True})
            continue
        if slots and i + 1 not in slots:
            continue
        rc = select_slot(i, f)
        if rc:
            return rc, out
        out.append(read_level_slot(i, ctx))
        f = scan_frames() or f
    uikit.mark(f'levels {role}')
    return 0, out


def list_levels(role_arg: str = 'all', slots=None, as_json: bool = False, pause: bool = False, learn: bool = True) -> int:
    """唯讀：只讀等級（練寵輪詢用，2026-10-13 review 1013b §2.3）。不認名字 / 身分（呼叫端用上一次 list 的格位 + nh 指紋比對同一隻）"""
    t0 = time.time()
    roles = role_list(role_arg)
    if not roles:
        print(f'pet：角色 {role_arg!r} 不認得（DKBO、DKBO2～5 或 all）', file=sys.stderr)
        return _out(uikit.EXIT_USAGE, {'roles': {}}, t0, '角色名不認得')
    if slots and not all(1 <= x <= 5 for x in slots):
        return _out(uikit.EXIT_USAGE, {'roles': {}}, t0, f'--slots {slots} 要 1～5')
    info = {'roles': {}}
    ctx = load_ctx(learn, use_icache=True)
    with Session(pause) as s:
        if s.rc:
            return _out(s.rc, info, t0)
        for r in roles:
            rc, sl = levels_role(r, ctx, slots)
            info['roles'][r] = sl
            if rc:
                save_ctx(ctx)
                return _out(rc, info, t0)
            if not as_json:
                print(f'{r}：' + '、'.join(f'{x["slot"]}:' + ('空' if x.get('empty') else f'Lv{x.get("level") if x.get("level") is not None else "?"}') for x in sl))
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


def shift_slots(slots: list, stored: int) -> list:
    """存走第 stored 格（1 起算）後的寵物欄推算（純函式）：後面的往前補位、最後一格變空（實機 P8：存入後寵物欄補位、空格留在後面）"""
    rest = [dict(x) for x in slots if x['slot'] != stored]
    for k, x in enumerate(rest):
        x['slot'] = k + 1
    return rest + [{'slot': len(rest) + 1, 'empty': True}]


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


def set_state_many(role_arg: str, pet_text: str, state_text: str, allow_mount: bool = False, pause: bool = False, learn: bool = True) -> int:
    """多角色同一隻寵物改狀態（2026-10-12 A）：面板開一次，左欄頭像逐人切 → 讀寵物欄 → 只點 1 次狀態鈕並讀回 → 關一次。
    規則同 set_state（騎寵保護、同名多隻 72、已是目標不點）；某人失敗立即停（不往下做）。回退出碼，逐人結果在 LAST['ops']"""
    t0 = time.time()
    roles = roles_multi(role_arg)
    target = norm_state(state_text)
    want = uikit.snap_pet(pet_text)
    info = {'cmd': 'set-state-many', 'pet': want, 'target': target, 'ops': []}
    if not roles or target not in STATES or not want:
        print(f'pet：set-state-many 參數不對（角色 {role_arg!r}、狀態 {state_text!r}、寵物 {pet_text!r}）', file=sys.stderr)
        return _out(uikit.EXIT_USAGE, info, t0, '參數不對')
    ctx = load_ctx(learn, use_icache=True)
    final = 0
    with Session(pause, need_calm=True) as s:
        if s.rc:
            return _out(s.rc, info, t0)
        try:
            for r in roles:
                op = {'role': r, 'changed': False}
                info['ops'].append(op)
                rc, slots = list_role(r, ctx)
                if not rc:
                    sl, why = find_slot(slots, want, None)
                    if sl is None:
                        rc = uikit_fail(EXIT_NAME, f'{r}：{why}')
                    else:
                        op['slot'], op['from'] = sl['slot'], sl.get('state')
                        bad = guard_mount(sl, target, allow_mount)
                        if bad:
                            rc = uikit_fail(EXIT_FORBID, f'{r} 拒絕：{bad}')
                        elif sl.get('state') != target:
                            rc, msg = apply_state(r, sl, target, ctx)
                            op['changed'] = rc == 0
                            if rc:
                                op['msg'] = msg
                            else:
                                print(f'pet：{r} 的 {want}（第 {sl["slot"]} 格）{sl.get("state")} → {target}')
                        else:
                            print(f'pet：{r} 的 {want} 本來就是「{target}」，沒有點擊')
                op['rc'] = rc
                if rc:
                    final = rc
                    break
        finally:
            save_ctx(ctx)
    return _out(final, info, t0, next((o.get('msg', '') for o in info['ops'] if o.get('rc')), ''))


def plan_rest(slots: list, keep: list, only: list | None) -> tuple:
    """rest-all 的決策（純函式）→ (要改的格 [slot dict], 拒絕 [(slot, 原因)])。
    只動狀態 = 出戰 的格；名字 = keep、像騎寵、狀態 = 騎乘 不動；--only 時只處理名字在清單內的；出戰但名字讀不出來 → 拒絕（不猜）。
    例外（2026-10-12 S5 恐龍博士：剛抓的貝魯卡沒名字、rest-all 拒絕，只好 set-state 逐人改）：名字讀不出、但縮圖比對認得物種
    （img_species，且不是騎寵）→ 照改等待（改等待可逆；身分只用來顯示與 --only / keep 判斷，不拿去存倉）"""
    todo, refuse = [], []
    for s in slots:
        if s.get('empty') or s.get('state') != '出戰':
            continue
        nm = s.get('name')
        if s.get('mountlike') or (nm and nm in keep):
            continue
        if not nm and s.get('img_species') and s['img_species'] not in keep and s['img_species'] not in uikit.MOUNTS:
            nm = s['img_species']                                     # 縮圖認得：用來比 --only，下面照常判斷
        elif not nm:
            refuse.append((s, '名字讀不出來（OCR / 樣板 / 縮圖都沒結果）'))
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
    ctx = load_ctx(learn, use_icache=True)
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
            names = [f'第 {x["slot"]} 格 {x["name"] or "≈" + str(x.get("img_species"))}' for x in todo]
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


def _img_hint(sl: dict) -> str:
    """拒絕訊息附註：縮圖比頭像的結果只供人參考（不當存倉依據）"""
    return f'（縮圖比對像 {sl["img_species"]} {sl.get("img_score")}，只供參考、不當存倉依據）' if sl.get('img_species') else ''


def guard_store(sl: dict, allow_slot1: bool, allow_mount_store: str | None = None) -> str | None:
    """存倉硬性禁止：回拒絕原因（None = 可以）。騎寵絕不存；唯一例外 allow_mount_store = 該寵物的「正式名」且 sl 名字完全相同（不接受像）、
    狀態須已是等待（騎乘 / 出戰都擋，先 set-state 等待）；其餘規則（名字 / 狀態讀不出、第 1 格要 --allow-slot1）照舊"""
    nm = slot_ident(sl)
    if not nm:
        if sl.get('unnamed'):
            return f'{sl.get("raw_name")} 沒名字且物種未確認（縮圖 / 成長字串登錄檔對不上；可能是騎寵），拒絕存倉；先 learn-species' + _img_hint(sl)
        return '名字讀不出來（不猜，拒絕存倉）' + _img_hint(sl)
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
    cur_sl = {**sl, **{k: cur.get(k) for k in ('name', 'state', 'mountlike', 'unnamed', 'raw_name', 'species', 'guess', 'unreadable')}}
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
    if not ident_confirms(ident, sl, 'slot', i, ctx):
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
    found = find_card(d2, depot, lambda idn, k: ident_confirms(idn, sl, 'card', k, ctx), ctx, first=new_idx, info=info)
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


def img_target(kind: str, idx: int, idn: dict, t: dict, ctx: dict, info: dict | None = None) -> bool:
    """take 的補充驗名：名字框認不出目標時（沒名字 / 名字讀不出、成長字串登錄檔不知道），縮圖認出的物種 == 目標名字 → True。
    只用在 take（可逆：取出後還會再驗）；目標有指定成長字串、或卡片有名字 / 登錄檔已知成長字串時一律 False（照原規則）"""
    if not t.get('name') or t.get('growth') or idn.get('name'):
        return False
    if idn.get('growth') and (species_reg(ctx).get('growth') or {}).get(idn['growth']):
        return False
    if idn.get('guess') and (species_reg(ctx).get('growth') or {}).get(idn['guess']) not in (None, t['name']):   # 讀不出但候選字串登錄成別的物種 → 不靠縮圖放行
        return False
    im = img_ident(kind, idx, ctx)
    if info is not None and im:
        info.setdefault('img', []).append({'kind': kind, 'index': idx + 1, 'species': im['img_species'], 'score': im['img_score']})
    return bool(im) and im['img_species'] == t['name']


def card_order(filled: list, first: int | None) -> list:
    """逐張驗證的順序：first（新增 / 優先的那格）先，其餘已用格照序（純函式）"""
    idxs = [k for k, f in enumerate(filled) if f]
    if first is not None and first in idxs:
        idxs.remove(first)
        idxs.insert(0, first)
    return idxs


def find_card(d: dict, depot: str, pred, ctx: dict, first: int | None = None, info: dict | None = None):
    """倉庫（d = scan_depot 結果）逐張選卡讀名字框，pred(ident, 卡 index) 成立的第一格 index（0 起算）；找不到 / 面板消失 → None。
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
        if pred(idn, k):
            if info is not None:
                info['cards'] = seen
            return k
    if info is not None:
        info['cards'] = seen
    return None


# ---- 取出目標（2026-10-12 B：不准盲取格號；errlog #294 --index 盲取遞補後的格子取到左迪洛斯）----
TARGET_RE = re.compile(r'^(?P<name>[^#@]*?)\s*(?:#\s*(?P<growth>\d{1,3}/\d{1,3}/\d{1,3}/\d{1,3}))?\s*(?:@\s*(?:[Ll][Vv])?(?P<level>\d{1,3}))?$')
CARD_LVL_BOX = (-50, 18, 100, 26)        # 倉庫卡下緣綠字「0轉129級」：相對卡心 (dx, dy, w, h)（depot5.png 實測位置；OCR 待實機量）
CARD_LVL_OPTS = [('-Dark', 0, '-Zooms', '2,3,4')]


def parse_target(text):
    """取出目標字串 → {'name', 'growth', 'level'}（純函式）。
    '朵拉比斯' / '朵拉比斯@126'（同名多隻用等級分）/ '#35/7/3/8'（沒名字的新寵物，成長字串）/ '克邦凱斯#35/7/3/8@1'。
    名字對不到 Monster 表、格式錯、三者全空 → None"""
    m = TARGET_RE.match(str(text or '').strip())
    if not m:
        return None
    raw = m['name'].strip()
    name = uikit.snap_pet(raw) if raw else None
    if raw and not name:
        return None
    t = {'name': name, 'growth': m['growth'], 'level': int(m['level']) if m['level'] else None}
    return t if (t['name'] or t['growth'] or t['level'] is not None) else None


def fmt_target(t: dict) -> str:
    return (t.get('name') or '') + (f'#{t["growth"]}' if t.get('growth') else '') + (f'@{t["level"]}' if t.get('level') is not None else '')


def target_ok(idn: dict, t: dict, reg: dict) -> bool:
    """名字框身分 idn 是不是目標 t（名字 / 成長字串；等級另外驗）。t 只有等級（--index + --expect-level）→ 身分不設限 True"""
    if t.get('name') and not card_is(idn, t['name'], reg):
        return False
    if t.get('growth') and idn.get('growth') != t['growth']:
        return False
    return True


def parse_card_level(lines) -> int | None:
    """倉庫卡綠字 OCR 行 → 等級（純函式）：各行「轉N」的 N 全部相同才採用；沒有 / 不一致 → None（不猜）"""
    vals = {int(m[1]) for t in (lines or []) for m in [re.search(r'轉\s*(\d{1,3})', str(t))] if m}
    return vals.pop() if len(vals) == 1 else None


def card_level_now(idx: int) -> int | None:
    """倉庫第 idx 格（0 起算）卡片下緣的等級（OCR；倉庫分頁中間沒有等級欄，只有卡片綠字）。讀不到 None"""
    cx, cy = card_xy(idx)
    dx, dy, w, h = CARD_LVL_BOX
    lines = []
    for opts in CARD_LVL_OPTS:
        lines += _petwatch().ocr((cx + dx, cy + dy, w, h), *opts)
    return parse_card_level(lines)


def take(role_arg: str, depot: str = 'personal', index: int | None = None, expect: str | None = None,
         pause: bool = False, learn: bool = True, pet_name: str | None = None, expect_growth: str | None = None, expect_level: int | None = None) -> int:
    """倉庫 → 寵物欄（單一角色、單隻；多人 / 多隻用 take_plan）。**一定要給目標**（2026-10-12 B）：
    - 找：--pet 名字 及 / 或 --expect-growth 成長字串（+ 可選 --expect-level）→ 現場逐張選卡讀名字框找；同名多隻且等級讀不出來 → 72 不取。
    - 指定格：--index N 只能和 --expect / --expect-growth / --expect-level 至少一個一起用；取前讀該格核對，不符 72 不取。
    取出後再驗新寵物（名字 / 成長字串；有等級目標且取前沒讀到卡片等級 → 切回寵物分頁讀等級），不符 76（不自動存回）"""
    t0 = time.time()
    role, info = _depot_prologue(role_arg, depot, 'take')
    if role is None:
        return _out(uikit.EXIT_USAGE, info, t0, '角色或倉庫參數不對')
    if index is not None and not 1 <= index <= 20:
        print('pet：--index 要 1～20（倉庫格，列優先、1 起算）', file=sys.stderr)
        return _out(uikit.EXIT_USAGE, info, t0, '--index 不對')
    if index is not None and not (expect or expect_growth or expect_level is not None):
        print('pet：--index 不准盲取，要加 --expect 名字 / --expect-growth 成長字串 / --expect-level 等級（至少一個）', file=sys.stderr)
        return _out(uikit.EXIT_USAGE, info, t0, '--index 沒給 --expect-*')
    if index is None and not (pet_name or expect or expect_growth):
        print('pet：要給目標：--pet 名字 或 --expect-growth 成長字串（或 --index N + --expect-*）', file=sys.stderr)
        return _out(uikit.EXIT_USAGE, info, t0, '沒給目標')
    nm_text = pet_name or expect
    want = uikit.snap_pet(nm_text) if nm_text else None
    if nm_text and not want:
        rc = uikit_fail(EXIT_NAME, f'寵物名 {nm_text!r} 對不到 Monster 表，拒絕')
        return _out(rc, info, t0, '寵物名對不上')
    tgt = {'name': want, 'growth': expect_growth, 'level': expect_level}
    info.update(index=index, expect=want, expect_growth=expect_growth, expect_level=expect_level)
    ctx = load_ctx(learn)
    with Session(pause, need_calm=True) as s:
        if s.rc:
            return _out(s.rc, info, t0)
        try:
            rc = select_role(role, ctx)
            if not rc:
                rc = _take_in_depot(role, depot, None if index is None else index - 1, tgt, ctx, info, {})
        finally:
            save_ctx(ctx)
            _back_to_pet_tab()
    return _out(rc, info, t0, info.get('msg', ''))


def shift_cache(cache: dict, idx: int) -> None:
    """取走倉庫第 idx 格後，後面的卡會往前遞補（#294 實機）：快取的格號跟著 -1（只當「先看哪格」的猜測，取之前一定現場重讀）"""
    moved = {(k - 1 if k > idx else k): v for k, v in cache.items() if k != idx}
    cache.clear()
    cache.update(moved)


def _ensure_depot(depot: str) -> tuple:
    """現在在倉庫分頁且子分頁 = depot → (0, d)；不是就切（open_depot 每步驗證）"""
    d = scan_depot()
    if d is not None and d['sig'] and d['tab'] == depot:
        return 0, d
    return open_depot(depot)


def _find_target_card(d: dict, depot: str, t: dict, ctx: dict, info: dict, cache: dict) -> tuple:
    """逐張選卡讀名字框找目標 → (index 或 None, 說明)。順序：快取裡像目標的格 → 沒讀過的格 → 其他（快取只是猜測，每張都現場讀）。
    有等級目標：名字 / 字串吻合的卡再 OCR 卡片綠字等級，相等就選；讀不到等級的候選只有 1 張 → 選它（取出後再驗）；≥ 2 張讀不到 → None（不盲取）"""
    reg = species_reg(ctx)
    filled = [k for k in range(20) if not d['empty'][k]]
    hit = [k for k in filled if k in cache and target_ok(cache[k], t, reg)]
    unk = [k for k in filled if k not in cache]
    rest = [k for k in filled if k not in hit and k not in unk]
    seen, cands = {}, []
    for k in hit + unk + rest:
        if not click_card(k, f'pet 找倉庫卡 第 {k + 1} 格'):
            break
        g, ok = wait_for_card(k, depot)
        if not ok:
            continue
        idn = read_ident(ctx, 4, 1.0)
        cache[k] = {'name': idn['name'], 'growth': idn['growth']}
        seen[k + 1] = idn['name'] or (f'?({idn["growth"]})' if idn['growth'] else None)
        if not (target_ok(idn, t, reg) and (idn['name'] or idn['growth'])):
            if unreadable_target(idn, 'card', k, t, ctx):              # 名字框讀不出：候選字串登錄 + 縮圖一致（共用規則）
                seen[k + 1] = f'?≈{fmt_target(t)}(登錄+圖)'
            elif img_target('card', k, idn, t, ctx, info):              # 名字框認不出 → 縮圖比頭像（取出後還會再驗）
                seen[k + 1] = f'{seen[k + 1] or "?"}≈{t["name"]}(圖)'
            else:
                continue
        if t.get('level') is None:
            info['cards'] = seen
            return k, ''
        lv = card_level_now(k)
        seen[k + 1] = f'{seen[k + 1]}@{lv}'
        if lv == t['level']:
            info['cards'], info['pre_level'] = seen, lv
            return k, ''
        if lv is None:
            cands.append(k)
    info['cards'] = seen
    if len(cands) == 1:
        info['level_unverified'] = True
        return cands[0], ''
    if len(cands) > 1:
        return None, f'{depot} 倉庫有 {len(cands)} 張 {fmt_target(t)} 候選（格 {[c + 1 for c in cands]}）但卡片等級讀不出來，不盲取'
    return None, f'{depot} 倉庫裡逐張看不到 {fmt_target(t)}（讀到 {seen}）'


def _take_in_depot(role: str, depot: str, idx, t: dict, ctx: dict, info: dict, cache: dict) -> int:
    """取出一隻（角色已選好；倉庫分頁不在就切）。idx = 指定格（0 起算，取前核對）/ None = 找目標。cache = 這個倉庫的卡片身分快取（批次共用）。
    零點擊條件：寵物欄滿 77、找不到 / 不符 72、按鈕驗證 75；取出後驗證不符 76（不自動存回）"""
    def bad(rc, msg):
        info['msg'] = msg
        return uikit_fail(rc, msg)

    reg = species_reg(ctx)
    f = scan_frames()
    if f is None:
        return bad(EXIT_PANEL, '讀不到面板像素')
    free_slots = [i + 1 for i, e in enumerate(f['empty']) if e]          # 只看空格（爪印），不逐格讀名字 / 等級（舊版 list_role 每格約 3.5 s）
    info['free'] = free_slots
    if not free_slots:
        return bad(EXIT_FULL, '寵物欄 5 / 5 滿了，沒有點取出鈕')
    rc, d = _ensure_depot(depot)
    if rc:
        info['msg'] = '倉庫分頁沒切成功'
        return rc
    if idx is None:
        idx, why = _find_target_card(d, depot, t, ctx, info, cache)
        if idx is None:
            if ctx.get('skip_missing') and '看不到' in why:      # take-many --skip-missing：這個倉庫沒有，略過（不記 errlog）
                info['missing'] = True
                info['msg'] = why
                return EXIT_NAME
            return bad(EXIT_NAME, why + '；沒取出')
        info['index'] = idx + 1
    if d['empty'][idx]:
        return bad(EXIT_NAME, f'{depot} 倉庫第 {idx + 1} 格是空的，沒有點')
    depot_before = 20 - sum(d['empty'])
    g = scan_depot()
    if not (g and g['sel'] == [k == idx for k in range(20)]):           # 找的時候最後選的不是這張（等級候選）/ 指定格：選它
        if not click_card(idx, f'pet 選倉庫第 {idx + 1} 格'):
            return bad(EXIT_PANEL, '面板特徵不在，沒點倉庫格')
        g, ok = wait_for_card(idx, depot)
        if not ok:
            uikit.snap('pet-take-select')
            return bad(EXIT_DEPOT, f'點了倉庫第 {idx + 1} 格但選取框沒到那格；不點取出')
    idn = read_ident(ctx)                                                # 取前核對（每次都現場重讀，同一格連續取也一樣）
    cache[idx] = {'name': idn['name'], 'growth': idn['growth']}
    nm = idn['name'] or (f'?({idn["growth"]})' if idn['growth'] else None)
    info['depot_name'] = nm
    img_ok = not (nm and target_ok(idn, t, reg)) and (unreadable_target(idn, 'card', idx, t, ctx) or img_target('card', idx, idn, t, ctx, info))
    if img_ok:
        info['img_pre'] = True
    if not nm and not img_ok:
        return bad(EXIT_NAME, f'倉庫第 {idx + 1} 格名字框讀不出來；沒取出')
    if not target_ok(idn, t, reg) and not img_ok:
        return bad(EXIT_NAME, f'倉庫第 {idx + 1} 格是 {nm}，不是 {fmt_target(t)}；沒取出（格子可能遞補了，重讀倉庫或改用 --pet 找）')
    if t.get('level') is not None and info.get('pre_level') is None and not info.get('level_unverified'):
        lv = card_level_now(idx)
        if lv is not None and lv != t['level']:
            return bad(EXIT_NAME, f'倉庫第 {idx + 1} 格 {nm} 卡片等級是 {lv}，不是 {t["level"]}；沒取出')
        info['pre_level'] = lv
    ok, why = btn_ready('take')
    if not ok:
        uikit.snap('pet-take-btn')
        return bad(EXIT_DEPOT, f'取出鈕驗證失敗：{why}；不點')
    if not click(DEPOT_BTN_XY[0], DEPOT_BTN_XY[1], f'pet take {role} 倉庫第 {idx + 1} 格 {nm}'):
        return bad(EXIT_PANEL, '面板特徵不在，沒點取出鈕')
    info['clicked'] = True
    uikit.mark('take click')
    shift_cache(cache, idx)
    ok, f2, d2 = wait_counts(depot, len(free_slots) - 1, depot_before - 1, info)
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
    want = t.get('name')
    if idn2['growth']:                                         # 沒名字：縮圖確認物種（取出的新寵物縮圖在寵物欄，倉庫分頁也看得到）
        sp = ident_species(new_slot - 1, idn2['growth'], ctx)
        info['species'] = sp
        if sp and petmatch.learn_species(reg, sp, None, idn2['growth']):
            ctx['rdirty'] = True
        if want and sp != want and not (sp is None and (card_is(idn2, want, reg) or img_target('slot', new_slot - 1, idn2, t, ctx, info))):
            return bad(EXIT_VERIFY, f'取出來的是 {nm2}（第 {new_slot} 格，物種 {sp}），不是預期的 {want}！停手交人處理，不自動存回')
        if t.get('growth') and idn2['growth'] != t['growth']:
            return bad(EXIT_VERIFY, f'取出來的是 {nm2}（第 {new_slot} 格），成長字串不是 {t["growth"]}！停手交人處理，不自動存回')
    elif nm2 is None and unreadable_target(idn2, 'slot', new_slot - 1, t, ctx):   # 名字框讀不出：候選字串登錄 + 縮圖一致（共用規則）
        info['species'] = t.get('name')
    elif (want and nm2 != want and not (nm2 is None and img_target('slot', new_slot - 1, idn2, t, ctx, info))) or t.get('growth'):
        return bad(EXIT_VERIFY, f'取出來的是 {nm2}（第 {new_slot} 格），不是預期的 {fmt_target(t)}！停手交人處理，不自動存回')
    el = t.get('level')
    if el is not None and info.get('pre_level') != el:        # 取前卡片等級沒讀到：切回寵物分頁讀新寵物等級（倉庫分頁中間沒有等級欄）
        if not goto_pet_tab():
            return bad(EXIT_VERIFY, '取出後切不回寵物分頁驗等級')
        f3 = scan_frames()
        rc = select_slot(new_slot - 1, f3 or {'sel': [False] * 5})
        lv = None if rc else read_slot(new_slot - 1, ctx).get('level')
        info['level'] = lv
        if lv != el:
            return bad(EXIT_VERIFY, f'取出來的第 {new_slot} 格等級是 {lv}，不是預期的 {el}！停手交人處理（存回再取另一隻），不自動存回')
    else:
        info['level'] = info.get('pre_level')
    uikit.mark('take verified')
    print(f'pet：{role} 倉庫第 {idx + 1} 格 → 寵物欄第 {new_slot} 格：{nm2 or nm}（取出的寵物預設「等待」）')
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
                slots, predicted = None, False                         # 每個角色只完整讀一次寵物欄（每格約 3.5 s）；存走一隻後用 shift_slots 推算，_store_body 選格後會重讀核對
                for nm in names:
                    op = {'role': r, 'pet': nm, 'depot': depot, 'clicked': False}
                    info['ops'].append(op)
                    _back_to_pet_tab()
                    for attempt in range(2):
                        rc = 0
                        if slots is None:
                            rc, slots = list_role(r, ctx)
                            predicted = False
                        if rc:
                            break
                        sl, why = find_slot(slots, nm, None, pick)
                        unknown = [x for x in slots if (x.get('unnamed') or x.get('unreadable')) and not x.get('species') and not x.get('name')
                                   and not (x.get('state') == '騎乘' and nm not in uikit.MOUNTS)]   # 名字框讀不出的格也算不知道是什麼 → 不略過（2026-10-14 40/9/6/5）；騎乘中的不可能是非騎寵目標（2026-10-12 DKBO2 騎寵 ?(49/9/7/2)）
                        if sl is None and skip_missing and not predicted and not unknown:
                            op['skipped'] = why
                            print(f'pet：{r} 沒有 {nm}，略過')
                            break
                        if sl is None and predicted:                   # 推算的欄位找不到：重讀一次再判斷
                            slots = None
                            continue
                        rc = _store_body(r, nm, depot, sl['slot'] if sl else None, allow_slot1, ctx, op, nm if nm in ams else None, pre=(0, slots))
                        if rc in (EXIT_NAME, EXIT_FORBID, EXIT_SELECT) and not op['clicked'] and predicted and attempt == 0:
                            log(f'{r}：推算的寵物欄與現場不符（{op.get("msg")}），重讀一次')
                            uikit.mark('store-many relist')
                            slots = None
                            _back_to_pet_tab()
                            op.pop('msg', None)
                            continue
                        break
                    if op.get('skipped'):
                        continue
                    op['rc'] = rc
                    if rc:
                        final = rc
                        break
                    slots, predicted = shift_slots(slots, op['slot']), True
                if final:
                    break
        finally:
            save_ctx(ctx)
            _back_to_pet_tab()
    return _out(final, info, t0, next((o.get('msg', '') for o in info['ops'] if o.get('rc')), ''))


def parse_plan(text: str) -> list | None:
    """'DKBO2:克邦凱斯,DKBO3:加克拉#35/7/3/8,DKBO:朵拉比斯@126' → [(角色, 目標 dict)]（純函式）；角色 / 目標不認得 → None"""
    out = []
    for part in [p.strip() for p in str(text or '').split(',') if p.strip()]:
        if ':' not in part:
            return None
        r, tt = part.split(':', 1)
        roles = role_list(r.strip())
        t = parse_target(tt)
        if not roles or len(roles) != 1 or t is None:
            return None
        out.append((roles[0], t))
    return out or None


def group_ops(ops: list) -> list:
    """同角色的取出排在一起（依角色第一次出現的順序；同角色內保持原順序）→ 每個角色只點一次頭像（純函式）"""
    order = []
    for r, _ in ops:
        if r not in order:
            order.append(r)
    return [(r, t) for o in order for r, t in ops if r == o]


def take_plan(ops: list, depot: str = 'personal', skip_missing: bool = False, pause: bool = False, learn: bool = True, cmd: str = 'take-many') -> int:
    """批次取出（2026-10-12 A）：面板開一次 → 倉庫分頁 / 子分頁切一次 → 在倉庫分頁直接點左欄頭像換角色（實機：切頭像後分頁停在原子分頁）→
    連續取完 → 切回寵物分頁 → 關一次。ops = [(角色, 目標 dict)]（parse_target）；同角色排在一起。
    每隻都走 _take_in_depot 的核對（取前讀卡、取後驗新寵物）；公共倉庫的卡片身分快取跨角色共用（只決定先看哪張，取前一定重讀）。失敗立即停（不重點）"""
    t0 = time.time()
    info = {'cmd': cmd, 'depot': depot, 'ops': []}
    if depot not in ('personal', 'public') or not ops or any(t is None for _, t in ops):
        print(f'pet：{cmd} 參數不對（倉庫 {depot!r}、目標 {ops!r}）', file=sys.stderr)
        return _out(uikit.EXIT_USAGE, info, t0, '參數不對')
    ops = group_ops(ops)
    ctx = load_ctx(learn)
    ctx['skip_missing'] = skip_missing
    caches: dict = {}
    final, cur = 0, None
    with Session(pause, need_calm=True) as s:
        if s.rc:
            return _out(s.rc, info, t0)
        try:
            for r, t in ops:
                op = {'role': r, 'pet': fmt_target(t), 'depot': depot, 'clicked': False}
                info['ops'].append(op)
                if r != cur:
                    rc = select_role(r, ctx)                       # 倉庫分頁開著也能點頭像（頭像欄在面板左側，寵物 / 倉庫分頁共用）
                    if rc:
                        op['rc'] = final = rc
                        break
                    cur = r
                rc = _take_in_depot(r, depot, None, t, ctx, op, caches.setdefault('public' if depot == 'public' else r, {}))
                op['rc'] = rc
                if rc and op.get('missing') and skip_missing:
                    op['skipped'] = op.pop('msg', '')
                    op['rc'] = 0
                    print(f'pet：{r} 的 {depot} 倉庫沒有 {fmt_target(t)}，略過')
                    continue
                if rc:
                    final = rc
                    break
        finally:
            save_ctx(ctx)
            _back_to_pet_tab()
    return _out(final, info, t0, next((o.get('msg', '') for o in info['ops'] if o.get('rc')), ''))


def card_ident(k: int, idn: dict, ctx: dict) -> dict:
    """倉庫第 k 張卡（0 起算，已選中、idn = 名字框身分）→ {'index', 'name', 'growth', 'guess', 'species', 'src'}（只供計數 / 顯示，不當取出依據）。
    物種：名字 → 名字；成長字串（或讀不出時的候選字串）已登錄 → 登錄物種；都沒有 → 縮圖（img_ident card；--candidates 時只在候選內比）"""
    reg = (species_reg(ctx).get('growth') or {})
    d = {'index': k + 1, 'name': idn.get('name'), 'growth': idn.get('growth'), 'guess': idn.get('guess'), 'species': None, 'src': None}
    if d['name']:
        d['species'], d['src'] = d['name'], 'name'
    elif d['growth'] and reg.get(d['growth']):
        d['species'], d['src'] = reg[d['growth']], 'reg'
    elif (us := unreadable_species(idn, 'card', k, ctx)):               # 讀不出：候選字串登錄 + 縮圖一致（共用規則）
        d['species'], d['src'] = us, 'reg+img'
    else:
        im = img_ident('card', k, ctx)
        if im and im.get('img_species'):
            d['species'], d['src'] = im['img_species'], 'img'
            if d['guess'] and reg.get(d['guess']) not in (None, im['img_species']):     # 候選字串登錄成別的物種 → 矛盾，不算
                d['species'], d['src'] = None, 'conflict'
    return d


def read_depot_cards(depot: str, ctx: dict) -> tuple:
    """倉庫分頁切到 depot（角色已選好）→ 逐張選卡讀身分（只選取，無副作用）→ (rc, [card_ident])"""
    rc, d = _ensure_depot(depot)
    if rc:
        return rc, []
    out = []
    for k in [i for i in range(20) if not d['empty'][i]]:
        if not click_card(k, f'pet 讀倉庫卡 第 {k + 1} 格'):
            return uikit_fail(EXIT_PANEL, '面板特徵不在，沒點倉庫格'), out
        _, ok = wait_for_card(k, depot)
        if not ok:
            out.append({'index': k + 1, 'name': None, 'growth': None, 'guess': None, 'species': None, 'src': 'select-fail'})
            continue
        out.append(card_ident(k, read_ident(ctx, 2, 0.6), ctx))
    uikit.mark(f'depot-list {depot}')
    return 0, out


def count_cards(cards: list) -> dict:
    """純函式：[card_ident] → {物種: 張數}（物種不明的記在 None）"""
    out: dict = {}
    for c in cards or []:
        out[c.get('species')] = out.get(c.get('species'), 0) + 1
    return out


def depot_list(role_arg: str, depots: list, pause: bool = False, learn: bool = True) -> int:
    """唯讀：倉庫卡片清單（公共一次；個人每個角色一次）。面板只開一次，逐張選卡讀名字框（沒名字的靠成長字串登錄檔 / 縮圖）。
    petquest 抓寵續跑用來數「各抓寵者實際已抓幾隻（含已進倉庫的）」"""
    t0 = time.time()
    roles = roles_multi(role_arg)
    info = {'cmd': 'depot-list', 'public': None, 'personal': {}, 'counts': {'public': None, 'personal': {}}}
    if not roles or not depots or any(x not in ('personal', 'public') for x in depots):
        print(f'pet：depot-list 參數不對（角色 {role_arg!r}、倉庫 {depots!r}）', file=sys.stderr)
        return _out(uikit.EXIT_USAGE, info, t0, '參數不對')
    ctx = load_ctx(learn)
    final = 0
    with Session(pause, need_calm=True) as s:
        if s.rc:
            return _out(s.rc, info, t0)
        try:
            if 'public' in depots:
                rc = select_role(roles[0], ctx)
                if not rc:
                    rc, cards = read_depot_cards('public', ctx)
                    info['public'], info['counts']['public'] = cards, count_cards(cards)
                final = final or rc
            if 'personal' in depots and not final:
                for r in roles:
                    rc = select_role(r, ctx)                       # 倉庫分頁開著也能點頭像（take_plan 同做法）
                    if not rc:
                        rc, cards = read_depot_cards('personal', ctx)
                        info['personal'][r], info['counts']['personal'][r] = cards, count_cards(cards)
                    if rc:
                        final = rc
                        break
        finally:
            save_ctx(ctx)
            _back_to_pet_tab()
    for k, v in [('public', info['counts']['public'])] + list(info['counts']['personal'].items()):
        if v is not None:
            print(f'pet：{k} 倉庫 {v}')
    return _out(final, info, t0)


def take_many(role_arg: str, pets_text: list, depot: str = 'personal', skip_missing: bool = False, pause: bool = False, learn: bool = True) -> int:
    """多角色 × 多寵物連續取出 = take_plan（每個角色取 pets_text 每一項；項目可帶 #成長字串 / @等級）"""
    roles = roles_multi(role_arg)
    tgts = [parse_target(x) for x in pets_text]
    if not roles or not pets_text or None in tgts:
        bad = [x for x, t in zip(pets_text, tgts) if t is None]
        print(f'pet：take-many 參數不對（角色 {role_arg!r}、目標對不到：{bad}）', file=sys.stderr)
        return _out(uikit.EXIT_USAGE, {'cmd': 'take-many', 'depot': depot, 'ops': []}, time.time(), '參數不對')
    return take_plan([(r, t) for r in roles for t in tgts], depot, skip_missing, pause, learn)


def unreadable_learn_reason(cur: dict, slot_no: int, sp: str, confirm: str) -> tuple | None:
    """純函式：learn-species 對「名字框讀不出」的格的守門 → (退出碼, 拒絕原因) 或 None（可以登錄）；73 = 禁止動的格、72 = 身分對不上。
    不碰第 1 格 / 騎寵（物種、縮圖、名字像騎寵）/ 騎乘 / 出戰（只收等待）；--confirm-growth 要跟現場 OCR 行不矛盾
    （至少 1 行是它或它的殘行、沒有任何一行是別的完整字串）；縮圖認出的物種（有的話）要等於要登錄的物種"""
    if slot_no == 1:
        return EXIT_FORBID, '第 1 格（騎寵位置）不准登錄'
    if cur.get('state') != '等待':
        return EXIT_FORBID, f'狀態是 {cur.get("state")}（騎乘 / 出戰 / 讀不出都不准，只收等待）'
    if sp in uikit.MOUNTS or cur.get('mountlike') or cur.get('img_species') in uikit.MOUNTS:
        return EXIT_FORBID, f'是 / 像騎寵（{"/".join(uikit.MOUNTS)}）'
    if not petmatch.GROWTH_RE.match(confirm or ''):
        return EXIT_NAME, f'--confirm-growth {confirm!r} 不是 a/b/c/d'
    lines = [str(t) for t in cur.get('ocr') or [] if str(t).strip()]
    full = {'/'.join(str(int(g)) for g in m.groups()) for t in lines for m in [petmatch.GROWTH_RE.match(t)] if m}
    if full - {confirm}:
        return EXIT_NAME, f'名字框 OCR 讀到別的成長字串 {sorted(full - {confirm})}（{lines}）'
    if not any(petmatch.growth_compatible(t, confirm) for t in lines):
        return EXIT_NAME, f'名字框 OCR {lines} 沒有一行跟 {confirm} 吻合'
    if cur.get('img_species') not in (None, sp):
        return EXIT_NAME, f'縮圖認成 {cur.get("img_species")}，不是 {sp}'
    return None


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
        for _ in range(2):                                      # OCR 偶爾讀不出成長字串（名字 / 字串都 None）：重讀最多 2 次（#279 #280 #282）
            if cur.get('unnamed') or cur.get('name'):
                break
            uikit.sleep(0.6)
            cur = read_slot(slot_no - 1, ctx)
        info['read'] = {k: cur.get(k) for k in ('name', 'unnamed', 'species', 'state', 'unreadable', 'guess', 'ocr', 'img_species')}
        cg = confirm_growth.strip()
        if cur.get('unreadable') and not cur.get('name') and (not cur.get('unnamed') or cur.get('guess') == cur.get('unnamed')):
            bad = unreadable_learn_reason(cur, slot_no, sp, cg)       # 名字框讀不出的格（2026-10-14 40/9/6/5）：額外守門
            if bad:
                rc = uikit_fail(bad[0], f'第 {slot_no} 格名字框讀不出：{bad[1]}，不登錄')
                return _out(rc, info, t0, bad[1])
            cur = dict(cur, unnamed=cg, raw_name=f'?({cg})')
        if not cur.get('unnamed'):
            rc = uikit_fail(EXIT_NAME, f'第 {slot_no} 格不是「沒名字」的寵物（名字 {cur.get("name")}），不登錄')
            return _out(rc, info, t0, '不是沒名字的寵物')
        if cur['unnamed'] != cg:
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
    cp.add_argument('--no-img', action='store_true', help='不用縮圖比知識庫頭像認物種（名字認不出時的備援，petimg_match）')
    cp.add_argument('--candidates', default=None, metavar='名,名', help='任務候選物種：沒名字的寵物只在這些之間比縮圖（相對比較 + 主色；例 卡坦 4 鯊）')
    cp.add_argument('--no-icache', action='store_true', help='不用身分跨程序快取（成長字串 / 縮圖結果；只影響 list / levels / set-state-many / rest-all）')
    sub = ap.add_subparsers(dest='cmd', required=True)
    p = sub.add_parser('list', help='唯讀：每格 名字 / 狀態 / 等級', parents=[cp])
    p.add_argument('--role', default='all')
    p.add_argument('--json', action='store_true', help='不印表格，只印最後一行 JSON')
    p = sub.add_parser('levels', help='唯讀：只讀等級（不認名字 / 身分；每格附名字框點陣指紋 nh）', parents=[cp])
    p.add_argument('--role', default='all')
    p.add_argument('--slots', default=None, help='只讀這些格（1 起算，逗號分隔；空格照列）')
    p.add_argument('--json', action='store_true', help='不印表格，只印最後一行 JSON')
    p = sub.add_parser('set-state', help='把某隻寵物改成 出戰 / 等待 / 騎乘', parents=[cp])
    p.add_argument('role')
    p.add_argument('pet')
    p.add_argument('state')
    p.add_argument('--slot', type=int, default=None, help='同名多隻時指定第幾格（1 起算）')
    p.add_argument('--allow-mount', action='store_true', help='允許動騎寵 / 設定騎乘（預設拒絕）')
    p = sub.add_parser('set-state-many', help='多角色同一隻寵物改狀態（面板只開一次，左欄頭像換人）', parents=[cp])
    p.add_argument('--role', default='all')
    p.add_argument('pet')
    p.add_argument('state')
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
    p = sub.add_parser('take-many', help='批次取出：面板 / 倉庫分頁只開一次，左欄頭像換角色連續取（現場逐張找名字）', parents=[cp])
    p.add_argument('--role', default=None, help='all 或逗號分隔（配 --pets：每人取同樣的目標）')
    p.add_argument('--pets', default=None, help='目標（逗號分隔）：名字 / 名字@等級 / #成長字串 / 名字#成長字串@等級')
    p.add_argument('--plan', default=None, help='每人不同目標：DKBO2:克邦凱斯,DKBO3:#35/7/3/8,DKBO:朵拉比斯@126')
    p.add_argument('--depot', default='personal', choices=['personal', 'public'])
    p.add_argument('--skip-missing', action='store_true')
    p = sub.add_parser('depot-list', help='唯讀：倉庫卡片清單 + 各物種張數（逐張選卡讀名字；公共一次、個人每人一次）', parents=[cp])
    p.add_argument('--role', default='DKBO', help='個人倉庫要讀的角色（逗號分隔 / all）；只讀公共時用第一個角色選頭像')
    p.add_argument('--depot', default='public', help='public / personal / public,personal')
    p = sub.add_parser('learn-species', help='登錄「某格沒名字的寵物是什麼物種」（縮圖 + 成長字串）', parents=[cp])
    p.add_argument('role')
    p.add_argument('slot', type=int)
    p.add_argument('species')
    p.add_argument('--confirm-growth', required=True, metavar='49/9/8/2', help='該格名字框現在的成長字串（第二重確認）')
    p = sub.add_parser('take', help='倉庫第 N 格 → 寵物欄（取出的寵物預設等待）', parents=[cp])
    p.add_argument('role')
    p.add_argument('--depot', default='personal', choices=['personal', 'public'])
    p.add_argument('--index', type=int, default=None, help='倉庫格 1～20（列優先，每列 5 格）；一定要和 --expect / --expect-growth / --expect-level 一起用（不准盲取）')
    p.add_argument('--pet', default=None, help='不給格號：現場逐張找這個名字（沒名字的卡靠成長字串登錄檔）')
    p.add_argument('--expect', default=None, help='預期的寵物名（取出前 / 後都驗，不符不自動存回）')
    p.add_argument('--expect-level', type=int, default=None, help='取出後驗新寵物等級（同名多隻、等級不同時用；不符 76 停手）')
    p.add_argument('--expect-growth', default=None, help='沒名字的卡：預期的成長字串（取出前驗，不符不取）；盲給 --index 取沒名字寵物時一律要加')
    a = ap.parse_args()
    if a.timing:
        uikit.timing_start()
        uikit._stages.append(['import', int((time.time() - _T_START) * 1000)])
        uikit.gui('pixel', '1,1')
        uikit.mark('server-start')
    learn = not a.no_learn
    global IMG_ON, IMG_ONLY, ICACHE_ON
    if a.no_img:
        IMG_ON = False
    if a.no_icache:
        ICACHE_ON = False
    if a.candidates:
        IMG_ONLY = [uikit.snap_pet(x.strip()) or x.strip() for x in a.candidates.split(',') if x.strip()]
    if a.cmd == 'list':
        return list_roles(a.role, a.json, a.pause_encounter, learn)
    if a.cmd == 'levels':
        try:
            sl = [int(x) for x in a.slots.split(',') if x.strip()] if a.slots else None
        except ValueError:
            return _out(uikit.EXIT_USAGE, {'roles': {}}, time.time(), f'--slots {a.slots!r} 要數字')
        return list_levels(a.role, sl, a.json, a.pause_encounter, learn)
    if a.cmd == 'set-state':
        return set_state(a.role, a.pet, a.state, a.slot, a.allow_mount, a.pause_encounter, learn)
    if a.cmd == 'store':
        return store(a.role, a.pet, a.depot, a.slot, a.allow_slot1, a.pause_encounter, learn, a.allow_mount_store)
    if a.cmd == 'take':
        return take(a.role, a.depot, a.index, a.expect, a.pause_encounter, learn, a.pet, a.expect_growth, a.expect_level)
    csv = lambda t: [x.strip() for x in (t or '').split(',') if x.strip()]    # noqa: E731
    if a.cmd == 'store-many':
        return store_many(a.role, csv(a.pets), a.depot, a.allow_slot1, csv(a.allow_mount_store), a.skip_missing, a.pause_encounter, learn, a.pick)
    if a.cmd == 'take-many':
        if a.plan:
            ops = parse_plan(a.plan)
            if ops is None:
                print(f'pet：--plan {a.plan!r} 看不懂（角色:目標,角色:目標；目標 = 名字 / 名字@等級 / #成長字串）', file=sys.stderr)
                return _out(uikit.EXIT_USAGE, {'cmd': 'take-many'}, time.time(), '--plan 不對')
            return take_plan(ops, a.depot, a.skip_missing, a.pause_encounter, learn)
        if not (a.role and a.pets):
            print('pet：take-many 要 --plan，或 --role + --pets', file=sys.stderr)
            return _out(uikit.EXIT_USAGE, {'cmd': 'take-many'}, time.time(), '參數不對')
        return take_many(a.role, csv(a.pets), a.depot, a.skip_missing, a.pause_encounter, learn)
    if a.cmd == 'set-state-many':
        return set_state_many(a.role, a.pet, a.state, a.allow_mount, a.pause_encounter, learn)
    if a.cmd == 'depot-list':
        return depot_list(a.role, [x.strip() for x in a.depot.split(',') if x.strip()], a.pause_encounter, learn)
    if a.cmd == 'learn-species':
        return learn_species_cmd(a.role, a.slot, a.species, a.confirm_growth, a.pause_encounter)
    split = lambda t: None if t is None else [x.strip() for x in t.split(',') if x.strip()]    # noqa: E731
    return rest_all(a.role, split(a.keep), split(a.only), a.dry_run, a.pause_encounter, learn)


if __name__ == '__main__':
    sys.exit(main())
