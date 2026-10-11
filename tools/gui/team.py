#!/usr/bin/env python3
"""組隊狀態檢查 / 快速組隊 / 解散（P2 + P4）。計畫：notes/plan-scriptify.md §2。只用標準函式庫。

用法（專案根目錄；WSL / Windows 原生指令相同）：
  uv run --no-project python tools/gui/team.py status [--json] [--no-ocr]   # 唯讀：開切換面板 → 每人 當前 / 線上、隊長 / 隊員 / 其他
  uv run --no-project python tools/gui/team.py check [--size 5] [--leader DKBO] [--no-ocr]   # 0 = 1 隊長 + (size-1) 隊員
  uv run --no-project python tools/gui/team.py form [--leader DKBO] [--size 5] [--login-all] [--regroup]   # 快速組隊（已組好 = 0 不點）
  uv run --no-project python tools/gui/team.py disband                      # 解散隊伍（當前角色必須是隊長）

退出碼（共用 0 / 1 / 2 / 8 / 9 / 10 見 uikit；team 自己 40～47）：
  40 切換面板打不開或讀圖中途消失（沒點任何面板內座標）
  41 隊伍不完整（有隊長 / 隊員但不是 1 隊長 + (size-1) 隊員，或隊長不是 --leader）；form 沒加 --regroup 就停手
  42 卡片數 < size（有角色不在線）；form 沒加 --login-all 就停手（加了仍缺也回 42）
  43 OCR 名字與卡片順序 / --leader 矛盾（讀到別人的名字才算；讀不出不算矛盾）；form 最後確認：像素不符、OCR 矛盾、超過 1 張名字讀不出、按組隊後提示視窗不消失
  45 解散沒做成（quest.disband_team 失敗，或解散後仍有隊伍）
  46 當前角色不是隊長（解散要隊長；不點）
  47 全員單人（沒有任何隊伍）；disband 遇到這個回 0
  44 form 專用：快速組隊提示視窗沒出現 / 隊長卡名字讀不出 / 隊長或隊員標籤點了沒亮（在按「組隊」前就停，關提示、不按組隊）

判斷依據（P-I1 / P-I4 實測，2026-10-11；座標 = 截圖座標）：
- 卡片存在：卡片米色 (249,231,203) vs 空位棕 (169,127,84)，看卡片左緣 (416 / 726, y)。順序固定 DKBO, DKBO2, DKBO3, DKBO4, DKBO5（真名是字母 O；DKB0 同義）
  （左欄 y 300 / 385 / 470、右欄 +310；有人離線時卡片會往前補位 → 卡片數 < 5 就不能靠順序，只能靠 OCR 名字）。
- 當前 / 線上：卡片左側狀態框 (x+6, y)、(x+30, y)：藍（B>150、G<200、R<60）= 當前、綠（G>160、B<60）= 線上；用門檻不比精確值。
- 隊伍標籤：框左上角（左欄 452,y-25、右欄 762,y-25）內 x+4..+34、y+4..+34 全像素掃描計數：紅 (255,0,7)「隊長」/ 黃 (255,210,0)「隊員」；
  同框的綠「正常」(41,255,0) 不計。單點取色不可靠（字很細）。「單人」字色 = 淡青 (109,219,215)（P-I2 實測，框內約 93 點）→ label 'solo'；
  既不紅、不黃、也不青 → 'other'（離線 / 讀不出）。
  （quest.read_team_labels 是 15x8 間隔 2 的稀疏取樣，實測 P-I1 說單點不可靠，這裡改密掃，不改 quest.py。）
- 名字（2026-10-11 起）：先用 namematch.py 整名圖樣板比對（IoU，保守，None = 不確定）；命中就採用（卡片 < 5 也行）。
  None 的卡片才退回下面的舊邏輯：以卡片順序為主；OCR（-Zooms 2,3,4,5,6 合併）只當交叉確認：norm_char 命中，或尾碼 02～05 符合即可。
  OCR 讀不出不算矛盾、讀到別人的名字才算矛盾；單獨讀到 DKBO（可能是 DKBO5 被截斷）不當矛盾證據。
"""
import argparse
import json
import re
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import charstate  # noqa: E402
import namematch  # noqa: E402
import uikit  # noqa: E402

SRC = 'team'
EXIT_PANEL, EXIT_INCOMPLETE, EXIT_MISSING, EXIT_OCR_CONFLICT = 40, 41, 42, 43
EXIT_DISBAND_FAIL, EXIT_NOT_LEADER, EXIT_NO_TEAM = 45, 46, 47

# 6 個卡片位置（slot 順序 = 面板上的先後）：(卡片左緣 x, 卡片 y)。左欄 slot 0/2/4、右欄 slot 1/3/5
CARD_X = (416, 726)
CARD_Y = (300, 385, 470)
SLOTS = [(CARD_X[i % 2], CARD_Y[i // 2]) for i in range(6)]
EXIST_BEIGE = (249, 231, 203)
EXIST_TOL = 30                       # 與空位棕 (169,127,84) 差 80 以上，門檻放中間
LABEL_DX, LABEL_DY = 36, -25         # 標籤框左上 = (x0+36, y-25)：452,275 / 762,275 …
LABEL_SCAN = range(4, 35)            # 框內 x+4..+34、y+4..+34（31x31 全掃）
SOLO_MIN_PX = 20                     # 「單人」淡青字實測約 93 點；門檻 20 避開雜訊
LABEL_MIN_PX = 3                     # 純色字像素 ≥ 3 才算（同框綠「正常」不計；雜訊像素不會是 (255,0,7) / (255,210,0)）
NAME_BOX_DX, NAME_BOX_DY, NAME_BOX_W, NAME_BOX_H = 149, -24, 90, 24    # 左欄 565,276,90,24；右欄 x +310（x0 差 310 已含在 x0）
OCR_ZOOMS = '2,3,4,5,6'


# ---- 純函式（離線測試用）----
def is_card(c) -> bool:
    return all(abs(a - b) <= EXIST_TOL for a, b in zip(c, EXIST_BEIGE))


def classify_status(c1, c2) -> str:
    """兩個狀態框邊線點 → 'current'（藍）/ 'online'（綠）/ 'unknown'。兩點都要符合"""
    if all(b > 150 and g < 200 and r < 60 for r, g, b in (c1, c2)):
        return 'current'
    if all(g > 160 and b < 60 for r, g, b in (c1, c2)):
        return 'online'
    return 'unknown'


def classify_label(cols) -> str:
    """標籤框掃描色 → 'leader'（紅 255,0,7）/ 'member'（黃 255,210,0）/ 'solo'（淡青 109,219,215，≥20 點）/ 'other'"""
    red = sum(1 for r, g, b in cols if r > 200 and g < 40 and b < 60)
    yel = sum(1 for r, g, b in cols if r > 230 and 190 < g < 235 and b < 40)
    if red >= LABEL_MIN_PX and red > yel:
        return 'leader'
    if yel >= LABEL_MIN_PX:
        return 'member'
    if sum(1 for r, g, b in cols if 95 <= r <= 125 and 205 <= g <= 235 and 200 <= b <= 230) >= SOLO_MIN_PX:
        return 'solo'
    return 'other'


def name_hits(texts) -> tuple:
    """OCR 各行文字 → (強證據名字集合, 是否讀到單獨的 DKBO)。
    強證據 = norm_char 命中 DKBO2～5（含 OCR 常見錯字還原），或尾碼 0[2-5]（D02 / 03 / B04 / 05；O / 0 視為相同）。
    單獨的 DKBO（norm_char 命中 DKBO）可能是 DKBO5 被截斷，另外回傳，不當矛盾證據。"""
    strong, bare = set(), False
    known = charstate.chars()
    for t in texts:
        t = str(t or '')
        hit = charstate.norm_char(t)
        if hit:
            if hit == charstate.LEAD:
                bare = True
            else:
                strong.add(hit)
            continue
        m = re.search(r'0([2-5])\s*$', t.replace('O', '0').replace('o', '0').strip())
        if m:
            cand = charstate.LEAD + m.group(1)
            hit = next((k for k in known if charstate.same(k, cand)), None)
            if hit:
                strong.add(hit)
    return strong, bare


def cross_check(expect, texts) -> str:
    """順序推得的名字 expect vs OCR → 'ok'（讀到且一致）/ 'unknown'（讀不出或證據不足）/ 'conflict'（讀到別人的名字）"""
    strong, bare = name_hits(texts)
    if expect in strong:
        return 'ok' if len(strong) == 1 else 'unknown'      # 同卡讀出多個不同名字 = OCR 雜訊，不採信
    if strong:
        return 'conflict'
    if bare and charstate.same(expect, charstate.LEAD):
        return 'ok'
    return 'unknown'


def resolve_name(slot: int, texts):
    """卡片數 < 5 時順序不可靠：只靠 OCR。唯一強證據 → 該名字；slot 0 讀到單獨 DKBO → DKBO；其餘 None"""
    strong, bare = name_hits(texts)
    if len(strong) == 1:
        return next(iter(strong))
    if not strong and bare and slot == 0:
        return charstate.LEAD
    return None


@dataclass
class Card:
    slot: int
    status: str = 'unknown'          # current / online / unknown
    label: str = 'other'             # leader / member / solo / other
    name: str | None = None          # 順序（5 張時）或 OCR 解出；None = 不知道
    ocr: list = field(default_factory=list)
    check: str = 'unread'            # ok / unknown / conflict / unread（沒做 OCR）
    via: str = ''                    # 名字來源：tpl（namematch）/ 空 = 順序或 OCR

    def d(self) -> dict:
        return {'slot': self.slot, 'name': self.name, 'status': self.status, 'label': self.label, 'ocr': self.ocr, 'ocr_check': self.check, 'via': self.via}


def build_cards(px_cols: list, ocr_texts: dict | None = None, matched: dict | None = None) -> list:
    """px_cols = read_pixels 回的整串顏色（順序：每 slot 先 card、s1、s2、再 LABEL 掃描）→ 存在的 Card 清單（照面板順序）。
    ocr_texts = {slot: [文字…]}；None = 沒做 OCR。matched = namematch 的 {slot: 名字或 None}（優先於順序 / OCR；None 才退回舊邏輯）。卡片位置不連續（空位在中間）視為異常 → 只回前面連續的那段"""
    per = 3 + len(LABEL_SCAN) ** 2
    cards = []
    order = charstate.chars()
    for i in range(len(SLOTS)):
        seg = px_cols[i * per:(i + 1) * per]
        if not is_card(seg[0]):
            break
        c = Card(i, status=classify_status(seg[1], seg[2]), label=classify_label(seg[3:]))
        cards.append(c)
    full = len(cards) == len(order)
    matched = matched or {}
    for c in cards:
        if ocr_texts is not None:
            c.ocr = list(ocr_texts.get(c.slot, []))
        hit = matched.get(c.slot)
        if hit:
            c.name, c.via = hit, 'tpl'
            # 5 張時順序可靠：樣板與順序不同 = 矛盾（judge 回 43）
            c.check = 'conflict' if full and hit != order[c.slot] else 'ok'
            continue
        if full:
            c.name = order[c.slot]
            if ocr_texts is not None:
                c.check = cross_check(c.name, c.ocr)
        elif ocr_texts is not None:
            c.name = resolve_name(c.slot, c.ocr)
            c.check = 'ok' if c.name else 'unknown'
    return cards


def summarize(cards: list) -> dict:
    lead = [c for c in cards if c.label == 'leader']
    mem = [c for c in cards if c.label == 'member']
    cur = [c for c in cards if c.status == 'current']
    return {'n': len(cards), 'leaders': len(lead), 'members': len(mem), 'others': len(cards) - len(lead) - len(mem),
            'solos': sum(1 for c in cards if c.label == 'solo'),
            'leader': lead[0].name if len(lead) == 1 else None, 'current': cur[0].name if len(cur) == 1 else None,
            'current_slot': cur[0].slot if len(cur) == 1 else None, 'leader_slot': lead[0].slot if len(lead) == 1 else None}


def judge(cards: list, size: int, leader=None) -> tuple:
    """純函式：→ (退出碼, 說明)。優先序：42 卡片不足 > 47 全單人 / 41 不完整 > 43 OCR 矛盾 / --leader 對不上"""
    s = summarize(cards)
    desc = f'卡片 {s["n"]}、隊長 {s["leaders"]}、隊員 {s["members"]}、其他 {s["others"]}'
    if s['n'] < size:
        names = [c.name or '?' for c in cards]
        return EXIT_MISSING, f'{desc}：卡片數 {s["n"]} < {size}（有角色不在線；在線卡片 {names}）'
    if s['leaders'] + s['members'] == 0:
        return EXIT_NO_TEAM, f'{desc}：全員單人，沒有隊伍'
    if not (s['leaders'] == 1 and s['members'] == size - 1):
        return EXIT_INCOMPLETE, f'{desc}：不是 1 隊長 + {size - 1} 隊員（隊伍不完整）'
    bad = [c for c in cards if c.check == 'conflict']
    if bad:
        return EXIT_OCR_CONFLICT, f'{desc}：OCR 名字與卡片順序矛盾 ' + '、'.join(f'slot{c.slot}={c.name} 但 OCR {c.ocr}' for c in bad)
    if leader and not charstate.same(s['leader'], leader):
        return EXIT_OCR_CONFLICT, f'{desc}：隊長是 {s["leader"] or "?（名字無法確認）"}，不是 {leader}'
    return 0, f'{desc}：隊伍完整（隊長 {s["leader"] or "?"}、當前 {s["current"] or "?"}）'


# ---- 讀面板（要碰遊戲）----
def read_pixels() -> list | None:
    """切換面板開著時一次 pixel 讀 6 張卡片的存在 / 狀態 / 標籤掃描點；失敗 None"""
    pts = []
    for x0, y in SLOTS:
        pts += [(x0, y), (x0 + 6, y), (x0 + 30, y)]
        lx, ly = x0 + LABEL_DX, y + LABEL_DY
        pts += [(lx + dx, ly + dy) for dy in LABEL_SCAN for dx in LABEL_SCAN]
    cols = uikit.px(pts)
    return cols


def ocr_names(n_cards: int, only=None) -> dict:
    """逐張卡片名字 OCR（-Zooms 2,3,4,5,6 合併；預設 Dark 150，-Light 讀不到）→ {slot: [行…]}；only = 只讀這些 slot"""
    out = {}
    for i in range(n_cards):
        if only is not None and i not in only:
            continue
        x0, y = SLOTS[i]
        out[i] = uikit.ocr((x0 + NAME_BOX_DX, y + NAME_BOX_DY, NAME_BOX_W, NAME_BOX_H), '-Zooms', OCR_ZOOMS)
    return out


OPEN_HUD_WAIT_S = 15.0           # 開切換面板時 HUD 不在（戰鬥 / 轉場）最多等這麼久；errlog #32


def read_state(ocr: bool = True, keep_open: bool = False) -> dict:
    """開切換面板 → 讀 → 關（只關自己開的；keep_open=True 讀完不關，char.py 要接著點卡片，呼叫端負責關）。回 {'ok': bool, 'cards': [...], 'summary': {...}, 'err': str, 'ms': {...}}。
    面板打不開 / 讀圖中途消失 → ok=False（呼叫端回 40）。不點任何面板內座標（開關只用 open_panel / close_panel 的開啟鈕與 ✕）"""
    res = {'ok': False, 'cards': [], 'summary': {}, 'err': '', 'ms': {}}
    t0 = time.time()
    opened, was_open = uikit.open_panel_ex(uikit.SWITCH, hud_wait=OPEN_HUD_WAIT_S)
    uikit.mark('open')
    if not opened:
        lo = uikit.LAST_OPEN
        why = (f'HUD 不在（等了 {lo.get("hud_waited", 0)} s 沒回來，可能在戰鬥 / 對話 / 驗證視窗，沒點任何東西）' if not lo.get('hud_seen')
               else f'點了開啟鈕 {lo.get("clicked", 0)} 次，面板特徵沒出現' + ('（點完 HUD 曾消失）' if lo.get('hud_lost_after_click') else ''))
        res['err'] = '切換面板打不開（' + why + '）'
        uikit.snap('team-panel-open-fail')
        return res
    res['ms']['open'] = int((time.time() - t0) * 1000)
    try:
        t1 = time.time()
        cols = read_pixels()
        res['ms']['pixel'] = int((time.time() - t1) * 1000)
        uikit.mark('pixel')
        if cols is None:
            res['err'] = '讀不到面板像素'
            return res
        n = len(build_cards(cols))
        matched = {}
        if ocr:                                   # --no-ocr = 完全不讀名字（維持舊行為：快、只靠順序）
            t3 = time.time()
            matched = namematch.read_names()
            res['ms']['tpl'] = int((time.time() - t3) * 1000)
            uikit.mark('namematch')
        texts = None
        if ocr:
            need = [i for i in range(n) if not matched.get(i)]
            if need:                              # 樣板沒命中的卡才 OCR（全命中就完全不跑 OCR）
                t2 = time.time()
                texts = ocr_names(n, only=need)
                res['ms']['ocr'] = int((time.time() - t2) * 1000)
                uikit.mark('ocr')
            else:
                texts = {}
        if not uikit.is_open(uikit.SWITCH):       # 像素 + 名字都讀完才確認一次面板還在（讀的過程中被關 = 資料不可信）
            res['err'] = '讀名字中面板消失'
            return res
        uikit.mark('verify-open')
        cards = build_cards(cols, texts, matched)
        res.update(ok=True, cards=cards, summary=summarize(cards))
        return res
    finally:
        if not was_open and not (keep_open and res['ok']):
            uikit.close_panel(uikit.SWITCH, known_open=res['ok'])
            uikit.mark('close')


def _line(c: Card) -> str:
    st = {'current': '當前', 'online': '線上', 'unknown': '？'}[c.status]
    lb = {'leader': '隊長', 'member': '隊員', 'solo': '單人', 'other': '單人/其他'}[c.label]
    ck = {'ok': 'OCR 一致', 'unknown': 'OCR 讀不出', 'conflict': 'OCR 矛盾', 'unread': ''}[c.check]
    if c.via == 'tpl':
        ck = {'ok': '樣板命中', 'conflict': '樣板與順序矛盾'}.get(c.check, '樣板')
    return f'slot{c.slot} {c.name or "?":6} {st} {lb:6} {ck} {c.ocr or ""}'.rstrip()


def status(as_json: bool = False, ocr: bool = True) -> int:
    rc = uikit.preflight(SRC)
    if rc:
        return rc
    t0 = time.time()
    r = read_state(ocr)
    if not r['ok']:
        uikit.snap('team-status-fail')
        return uikit.fail(SRC, EXIT_PANEL, r['err'])
    ms = int((time.time() - t0) * 1000)
    if as_json:
        print(json.dumps({'cards': [c.d() for c in r['cards']], 'summary': r['summary'], 'ms': ms, 'stage_ms': r['ms']}, ensure_ascii=False))
    else:
        for c in r['cards']:
            print(_line(c))
        s = r['summary']
        print(f'共 {s["n"]} 張：隊長 {s["leaders"]}、隊員 {s["members"]}、其他 {s["others"]}；隊長 {s["leader"] or "-"}、當前 {s["current"] or "-"}（{ms} ms {r["ms"]}）')
    return 0


def check(size: int = 5, leader=None, ocr: bool = True) -> int:
    rc = uikit.preflight(SRC)
    if rc:
        return rc
    if leader:
        leader = charstate.norm_char(leader)
        leader = charstate.display(leader) if leader else None
        if not leader:
            print('team：--leader 不在白名單', file=sys.stderr)
            return uikit.EXIT_USAGE
    r = read_state(ocr)
    if not r['ok']:
        uikit.snap('team-check-fail')
        return uikit.fail(SRC, EXIT_PANEL, r['err'])
    code, desc = judge(r['cards'], size, leader)
    for c in r['cards']:
        print(_line(c))
    print(f'check：{desc}（退出碼 {code}）')
    if code == EXIT_OCR_CONFLICT:
        uikit.snap('team-check-conflict')
        uikit.fail(SRC, code, desc)
    return code


# ---- form：快速組隊（P4；提示視窗座標 / 顏色為 P-I2 實測 2026-10-11）----
EXIT_QT = 44
QT_BTN = (520, 578)                  # 切換面板內「快速組隊」
QT_LOGIN_ALL = (716, 578)            # 「全部登錄」（紅區：只在 --login-all）
QT_GO = (720, 665)                   # 提示視窗「組隊」
QT_LEADER_Y, QT_MEMBER_Y = 320, 520  # 上排（隊長）/ 下排（隊員）卡片中心 y
QT_X0, QT_DX = 549, 133              # 卡片中心 x = 549 + 133 * 欄；上排只看得到 4 欄（第 5 位被切掉，不支援當隊長）
QT_LEADER_BADGE = [(520, 243), (530, 243), (505, 255)]       # 上排第 0 欄「隊長」紅帶（233,4,3）/（245,4,0）/（185,3,0）
QT_MEMBER_BADGE = [(505, 458), (520, 447), (530, 447)]       # 下排第 0 欄「隊員」藍帶（3,74,255）；未選 = 棕 (169,117,70)
QT_NAME_BOX = (-40, 30, 80, 30)      # 上排卡片名字 OCR 框 = (x-40, 350, 80, 30)（黑字白邊；-Zooms 2,3,4 讀得到）
QT_NAME_Y = 350
QT_OCR_ZOOMS = '2,3,4'
QT_WAIT_PROMPT_S = 1.5
QT_WAIT_DONE_S = 8.0                 # 按組隊後提示視窗消失 + HUD 回來（leader ≠ 當前時有加載畫面）
QT_POLL_S = 0.1


def badge_state(c) -> str:
    """提示視窗卡片角標像素 → 'red'（隊長）/ 'blue'（隊員）/ 'none'"""
    r, g, b = c
    if r > 180 and g < 40 and b < 40:
        return 'red'
    if b > 200 and r < 40 and g < 130:
        return 'blue'
    return 'none'


def _badge_pts(pts, col: int) -> list:
    return [(x + QT_DX * col, y) for x, y in pts]


def read_badges(leader_col: int, member_cols: list):
    """一次 pixel 讀 → (隊長角標狀態, [各隊員角標狀態])；三點都同色才算（任一點不同 = 'none'）；讀不到回 None"""
    pts = _badge_pts(QT_LEADER_BADGE, leader_col)
    for j in member_cols:
        pts += _badge_pts(QT_MEMBER_BADGE, j)
    cols = uikit.px(pts)
    if not cols or len(cols) != len(pts):
        return None
    states = [badge_state(c) for c in cols]
    out = []
    for i in range(1 + len(member_cols)):
        seg = set(states[i * 3:i * 3 + 3])
        out.append(next(iter(seg)) if len(seg) == 1 else 'none')
    return out[0], out[1:]


def prompt_name_ok(col: int, leader: str) -> bool:
    """上排第 col 欄名字 OCR 必須確認是 leader（cross_check ok）；讀不出 / 讀到別人都拒絕"""
    x = QT_X0 + QT_DX * col
    texts = uikit.ocr((x + QT_NAME_BOX[0], QT_NAME_Y, QT_NAME_BOX[2], QT_NAME_BOX[3]), '-Zooms', QT_OCR_ZOOMS)
    return cross_check(leader, texts) == 'ok'


def _qt_abort(why: str, snap_tag: str) -> int:
    """快速組隊中途失敗：關提示（沒按組隊鈕）→ 關切換面板 → snap / errlog，回 44"""
    uikit.snap(snap_tag)
    if uikit.is_open(uikit.QTEAM):
        uikit.close_panel(uikit.QTEAM, known_open=True)
    uikit.close_panel(uikit.SWITCH)
    return uikit.fail(SRC, EXIT_QT, why)


def _wait_prompt_gone(timeout: float = QT_WAIT_DONE_S) -> tuple:
    """按組隊後：等提示視窗消失且 HUD 回來。→ (完成, 秒數)"""
    import screen_sigs
    t0 = uikit.clock()
    hud = [(x, y) for x, y, *_ in screen_sigs.SIG_HUD]
    qt = [(x, y) for x, y, *_ in uikit.QTEAM.sig]
    while True:
        cols = uikit.px(qt + hud)
        el = uikit.clock() - t0
        if cols:
            prompt_up = all(screen_sigs.close(c, (r, g, b), t) for c, (_, _, r, g, b, t) in zip(cols[:len(qt)], uikit.QTEAM.sig))
            hud_ok = all(screen_sigs.close(c, (r, g, b), t) for c, (_, _, r, g, b, t) in zip(cols[len(qt):], screen_sigs.SIG_HUD))
            if not prompt_up and hud_ok:
                return True, el
        if el >= timeout:
            return False, el
        uikit.sleep(QT_POLL_S)


def _quick_team_prompt(leader: str, col: int, size: int) -> int:
    """切換面板開著、全員單人、leader 卡在第 col 欄。點快速組隊 → 逐步讀再點 → 組隊。→ 0 或 44 / 43"""
    if not uikit.safe_click(*QT_BTN, uikit.SWITCH, note='team form 快速組隊', wait_ms=100):
        return _qt_abort('點快速組隊前切換面板特徵不在，沒點', 'team-form-nopanel')
    uikit.mark('click-quickteam')
    t0 = uikit.clock()
    while not uikit.is_open(uikit.QTEAM):                      # 提示視窗特徵（✕ + 組隊鈕 + 隊長標籤）
        if uikit.clock() - t0 > QT_WAIT_PROMPT_S:
            return _qt_abort('快速組隊提示視窗 1.5 s 內沒出現（沒再點任何東西）', 'team-form-noprompt')
        uikit.sleep(QT_POLL_S)
    uikit.mark('prompt')
    if not prompt_name_ok(col, leader):
        return _qt_abort(f'提示視窗上排第 {col + 1} 欄名字 OCR 無法確認是 {leader}，不點', 'team-form-leadername')
    uikit.mark('ocr-leader')
    # 隊長：先讀再點（切換式）；已經是紅帶就不點
    b = read_badges(col, [])
    if b is None:
        return _qt_abort('讀不到隊長角標像素', 'team-form-badge')
    if b[0] != 'red':
        if not uikit.safe_click(QT_X0 + QT_DX * col, QT_LEADER_Y, uikit.QTEAM, note=f'team form 選隊長 {leader}', wait_ms=100):
            return _qt_abort('點隊長前提示視窗特徵不在，沒點', 'team-form-leader-gone')
        b = read_badges(col, [])
        if b is None or b[0] != 'red':
            return _qt_abort(f'點了隊長但紅「隊長」角標沒出現（{b}）', 'team-form-leader-nobadge')
    uikit.mark('leader')
    # 下排 size-1 張隊員：每張先讀（藍 = 已選，不點），沒選才點，點完再讀確認
    mcols = list(range(size - 1))
    b = read_badges(col, mcols)
    if b is None:
        return _qt_abort('讀不到隊員角標像素', 'team-form-badge')
    for j in mcols:
        if b[1][j] == 'blue':
            continue
        if not uikit.safe_click(QT_X0 + QT_DX * j, QT_MEMBER_Y, uikit.QTEAM, note=f'team form 選隊員（下排第 {j + 1} 張）', wait_ms=100):
            return _qt_abort('點隊員前提示視窗特徵不在，沒點', 'team-form-member-gone')
        one = read_badges(col, [j])
        if one is None or one[1][0] != 'blue':
            return _qt_abort(f'點了下排第 {j + 1} 張但藍「隊員」角標沒出現（{one}），不按組隊', 'team-form-member-nobadge')
    uikit.mark('members')
    # 按組隊前最後一次全讀：提示還在、1 紅 + (size-1) 藍
    b = read_badges(col, mcols)
    if b is None or b[0] != 'red' or any(s != 'blue' for s in b[1]) or not uikit.is_open(uikit.QTEAM):
        return _qt_abort(f'按組隊前最後確認不符（{b}），不按組隊', 'team-form-final')
    uikit.mark('final-check')
    if not uikit.safe_click(*QT_GO, uikit.QTEAM, note='team form 按組隊', wait_ms=0):
        return _qt_abort('按組隊前提示視窗特徵不在，沒點', 'team-form-go-gone')
    uikit.mark('click-go')
    ok, sec = _wait_prompt_gone()
    uikit.mark('wait-done')
    if not ok:
        uikit.snap('team-form-stuck')
        return uikit.fail(SRC, EXIT_OCR_CONFLICT, f'按組隊後 {QT_WAIT_DONE_S:.0f} s 提示視窗仍在或 HUD 沒回來（可能是 33231「地圖不支持一鍵組隊」或別的視窗）；沒有再點，請看畫面')
    return 0


def _strict_unknown(cards: list) -> bool:
    """最終確認的名字規則（計畫決定 3）：名字 OCR / 樣板讀不出的卡片最多 1 張（>1 → 不可信）"""
    return sum(1 for c in cards if c.check == 'unknown') > 1


def form(leader=None, size: int = 5, login_all: bool = False, regroup: bool = False) -> int:
    """快速組隊（計畫 §2.3）。已組好（1 隊長 = leader + size-1 隊員）→ 0 不點；
    不完整隊伍 → 41（--regroup 才解散重組）；卡片不足 → 42（--login-all 才按「全部登錄」）；全員單人才走快速組隊。
    成功後隊長變當前（必要時 char.ensure），寫 charstate。"""
    rc = uikit.preflight(SRC)
    if rc:
        return rc
    if not 2 <= size <= len(charstate.chars()):
        print(f'team：--size {size} 不合理', file=sys.stderr)
        return uikit.EXIT_USAGE
    hit = charstate.norm_char(leader or charstate.LEAD)
    leader = charstate.display(hit) if hit else None
    if not leader:
        print('team：--leader 不在白名單', file=sys.stderr)
        return uikit.EXIT_USAGE
    t0 = time.time()
    did_login = did_regroup = False
    while True:
        r = read_state(True, keep_open=True)
        if not r['ok']:
            uikit.snap('team-form-fail')
            return uikit.fail(SRC, EXIT_PANEL, r['err'])
        cards, s = r['cards'], r['summary']
        code, desc = judge(cards, size)
        if code == 0 and not charstate.same(s['leader'], leader):
            code, desc = EXIT_INCOMPLETE, f'{desc}：隊長是 {s["leader"] or "?"}，不是 {leader}'
        if code == 0 and _strict_unknown(cards):
            code, desc = EXIT_OCR_CONFLICT, f'{desc}：超過 1 張卡片名字讀不出，不可信'
        print(f'form：現況 {desc}（{code}）')
        if code == 0:                                       # 已組好：不點；當前不是隊長才用 char.ensure 切
            uikit.close_panel(uikit.SWITCH, known_open=True)
            return _finish(leader, s, t0, formed=False)
        if code == EXIT_MISSING:
            if not login_all or did_login:
                uikit.close_panel(uikit.SWITCH, known_open=True)
                return uikit.fail(SRC, EXIT_MISSING, desc + ('；已按過「全部登錄」仍缺' if did_login else '；要補登入請加 --login-all'))
            if not uikit.safe_click(*QT_LOGIN_ALL, uikit.SWITCH, note='team form 全部登錄（--login-all）', allow=('login_all',), wait_ms=4000):
                return uikit.fail(SRC, EXIT_PANEL, '按全部登錄前切換面板特徵不在')
            did_login = True
            uikit.close_panel(uikit.SWITCH)
            continue
        if code == EXIT_INCOMPLETE:
            if not regroup or did_regroup:
                uikit.close_panel(uikit.SWITCH, known_open=True)
                return uikit.fail(SRC, EXIT_INCOMPLETE, desc + '；要解散重組請加 --regroup')
            uikit.close_panel(uikit.SWITCH, known_open=True)
            d = disband()
            if d:
                return d
            did_regroup = True
            continue
        if code != EXIT_NO_TEAM:                            # 43：名字矛盾 / 未知
            uikit.close_panel(uikit.SWITCH, known_open=True)
            uikit.snap('team-form-conflict')
            return uikit.fail(SRC, code, desc)
        break
    # 全員單人：每張都要「單人」標籤（淡青）、狀態 = 線上 / 當前
    bad = [c for c in cards if c.label != 'solo' or c.status not in ('online', 'current')]
    if bad or len(cards) < size:
        uikit.close_panel(uikit.SWITCH, known_open=True)
        return uikit.fail(SRC, EXIT_INCOMPLETE, '全員單人檢查不過（標籤 / 狀態讀不準）：' + '、'.join(f'slot{c.slot}={c.label}/{c.status}' for c in bad))
    if _strict_unknown(cards):
        uikit.close_panel(uikit.SWITCH, known_open=True)
        return uikit.fail(SRC, EXIT_OCR_CONFLICT, '超過 1 張卡片名字讀不出，不組隊')
    lc = next((c for c in cards if c.name and c.check == 'ok' and charstate.same(c.name, leader)), None)
    if lc is None:
        uikit.close_panel(uikit.SWITCH, known_open=True)
        return uikit.fail(SRC, EXIT_QT, f'找不到名字確認過的 {leader} 卡片，不組隊')
    if lc.slot > 3:
        uikit.close_panel(uikit.SWITCH, known_open=True)
        return uikit.fail(SRC, EXIT_QT, f'{leader} 在第 {lc.slot + 1} 張卡，提示視窗上排只看得到前 4 欄（未實測拖曳），不組隊')
    uikit.mark('read-done')
    rc = _quick_team_prompt(leader, lc.slot, size)
    if rc:
        return rc
    # 最終確認：重開切換面板，像素 1 隊長 + (size-1) 隊員、隊長 = leader、名字不矛盾
    r = read_state(True)
    if not r['ok']:
        uikit.snap('team-form-verify-fail')
        return uikit.fail(SRC, EXIT_PANEL, '組隊後驗證：' + r['err'])
    code, desc = judge(r['cards'], size, leader)
    if code == 0 and _strict_unknown(r['cards']):
        code, desc = EXIT_OCR_CONFLICT, f'{desc}：超過 1 張卡片名字讀不出'
    if code:
        uikit.snap('team-form-verify-fail')
        extra = '；全員仍單人，可能是地圖禁止一鍵組隊（33231）' if code == EXIT_NO_TEAM else ''
        return uikit.fail(SRC, EXIT_OCR_CONFLICT, f'組隊後驗證不符（原碼 {code}）：{desc}{extra}')
    warn = [c.slot for c in r['cards'] if c.check == 'unknown']
    if warn:
        print(f'form：警告 slot{warn} 名字讀不出（像素與順序都符合）')
    return _finish(leader, r['summary'], t0, formed=True)


def _finish(leader: str, s: dict, t0: float, formed: bool) -> int:
    """成功收尾：隊長 = leader；當前不是 leader 就 char.ensure；寫 charstate"""
    cur = s.get('current')
    if not charstate.same(cur, leader):
        import char
        rc = char.ensure(leader)
        if rc:
            return rc
        cur = leader
    charstate.write(leader, src='team.py')
    print(f'form：{"已組好" if formed else "本來就組好了（沒有任何點擊）"}：隊長 {leader}、當前 {cur}（{int((time.time() - t0) * 1000)} ms）')
    return 0


def disband() -> int:
    """解散隊伍。先唯讀確認（沒有隊伍 → 0 不點；當前不是隊長 → 46 不點），再交給 quest.disband_team（左側分頁，逐步像素驗證），
    解散後重開切換面板確認沒有隊長 / 隊員，最後把左側分頁切回「任務」。"""
    rc = uikit.preflight(SRC)
    if rc:
        return rc
    r = read_state(ocr=False)
    if not r['ok']:
        uikit.snap('team-disband-fail')
        return uikit.fail(SRC, EXIT_PANEL, r['err'])
    s = r['summary']
    if s['leaders'] + s['members'] == 0:
        print('disband：本來就沒有隊伍，沒做任何點擊（退出碼 0）')
        return 0
    cur = [c for c in r['cards'] if c.status == 'current']
    if len(cur) != 1 or cur[0].label != 'leader':
        uikit.snap('team-disband-not-leader')
        return uikit.fail(SRC, EXIT_NOT_LEADER, f'當前角色不是隊長（當前 {s["current"] or "?"}、隊長 {s["leader"] or "?"}）：不點，先切到隊長再解散')
    import quest
    d = quest.disband_team()
    if d:
        uikit.snap('team-disband-quest-fail')
        return uikit.fail(SRC, EXIT_DISBAND_FAIL, f'quest.disband_team 回 {d}（解散沒做成）')
    r = read_state(ocr=False)
    if not r['ok']:
        uikit.snap('team-disband-verify-fail')
        return uikit.fail(SRC, EXIT_PANEL, '解散後驗證：' + r['err'])
    s = r['summary']
    if s['leaders'] + s['members']:
        uikit.snap('team-disband-still')
        return uikit.fail(SRC, EXIT_DISBAND_FAIL, f'解散後仍有隊伍（隊長 {s["leaders"]}、隊員 {s["members"]}）')
    quest.ensure_task_tab()
    print('disband：已解散（切換面板全員單人 / 其他），左側分頁已確認在任務')
    return 0


def main() -> int:
    import winenv
    winenv.enable_server()
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    sub = ap.add_subparsers(dest='cmd', required=True)
    p = sub.add_parser('status', help='唯讀：顯示每人當前 / 隊長 / 隊員')
    p.add_argument('--json', action='store_true')
    p.add_argument('--no-ocr', action='store_true', help='不做名字 OCR 交叉確認（快）')
    p = sub.add_parser('check', help='0 = 1 隊長 + (size-1) 隊員')
    p.add_argument('--size', type=int, default=5)
    p.add_argument('--leader', help='隊長必須是這個角色（名字）')
    p.add_argument('--no-ocr', action='store_true')
    p = sub.add_parser('form', help='快速組隊（已組好 = 0 不點）')
    p.add_argument('--leader', help='隊長角色（預設 DKBO）')
    p.add_argument('--size', type=int, default=5)
    p.add_argument('--login-all', action='store_true', help='有角色離線時按「全部登錄」（預設不按，回 42）')
    p.add_argument('--regroup', action='store_true', help='已有不完整隊伍時解散重組（預設回 41）')
    sub.add_parser('disband', help='解散隊伍（當前必須是隊長）')
    a = ap.parse_args()
    if a.cmd == 'status':
        return status(a.json, not a.no_ocr)
    if a.cmd == 'check':
        return check(a.size, a.leader, not a.no_ocr)
    if a.cmd == 'form':
        return form(a.leader, a.size, a.login_all, a.regroup)
    return disband()


if __name__ == '__main__':
    sys.exit(main())
