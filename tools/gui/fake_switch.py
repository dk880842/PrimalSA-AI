#!/usr/bin/env python3
"""離線測試共用：假切換面板（Game）。team / char 的測試都用它：假 gui 依設定畫切換面板像素，不碰遊戲。"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import clients  # noqa: E402
import screen_sigs  # noqa: E402
import team  # noqa: E402
import uikit  # noqa: E402


BLUE, GREEN = (29, 175, 195), (8, 187, 36)
BEIGE, BROWN = (249, 231, 203), (169, 127, 84)
RED, YEL, NORMAL = (255, 0, 7), (255, 210, 0), (41, 255, 0)
SOLO = (109, 219, 215)               # 「單人」字色（P-I2 實測）
Q_RED, Q_BLUE, Q_BROWN = (233, 4, 3), (3, 74, 255), (169, 117, 70)     # 快速組隊提示視窗角帶
# 名單依 PSA_CLIENT（clients.roster()）：主視窗 DKBO～DKBO5；PrimalSA2 DKBO6～DKBO10（第 3b 步）
NAMES = clients.roster() or ['DKBO', 'DKBO2', 'DKBO3', 'DKBO4', 'DKBO5']
# OCR 假資料（P-I1 實測：Zooms 2~6 合併結果）
OCR_MAIN = {'DKBO': ['DKBO'], 'DKBO2': ['DKBO2', 'D02', '02'], 'DKBO3': ['03', '003'], 'DKBO4': ['DKBO4', 'B04'], 'DKBO5': ['05']}
# PrimalSA2（未實機，比照主視窗的讀法：整名 / 只剩尾碼 / 數字 0 混淆 DKB010）
OCR_P2 = {'DKBO6': ['DKBO6'], 'DKBO7': ['07', '007'], 'DKBO8': ['DKB08', 'B08'], 'DKBO9': ['09'], 'DKBO10': ['DKB010', '010']}
OCR_REAL = OCR_P2 if NAMES and NAMES[0] == 'DKBO6' else OCR_MAIN


class Game:
    """cards = [{'name','status','label'}]（照面板順序；數量 = 在線人數）。painted 由 color_at 即時算"""

    def __init__(self, cards, hud=True, ocr=None):
        self.cards, self.hud, self.panel = cards, hud, False
        self.clicks, self.keys, self.ocr_boxes = [], [], []
        self.ocr_map = OCR_REAL if ocr is None else ocr
        self.vanish_after_label = False
        self.on_disband = None
        self.loading = 0              # >0：加載畫面（SIG_HUD 不成立、SIG_LOADING 成立），每次 pixel 呼叫減 1
        self.after_load = 2           # 點卡片後加載畫面持續幾次 pixel 呼叫
        self.card_moves = True        # False = 點卡片沒反應（當前不動，測 62）
        self.stuck = False            # True = 點卡片後 HUD 一直不回來（測 65）
        self.hud_never = False
        # 快速組隊提示視窗（P-I2）：prompt = 視窗開著；q_leader = 上排選中的欄；q_members = 下排選中的欄
        self.prompt, self.q_leader, self.q_members = False, None, set()
        self.q_dead_member = None     # 下排這一欄點了不亮（測 44）
        self.q_no_prompt = False      # 點快速組隊沒反應（測 44）
        self.q_33231 = False          # 按組隊後什麼都沒發生、提示視窗仍在（測 stuck）
        self.q_leader_dead = False    # 點隊長沒反應
        self.q_noop = False           # 按組隊後提示關了但沒組成（全員仍單人）
        self.q_preselect = set()      # 提示視窗一開就已選好的下排欄
        self.prompt_ocr = None        # 提示視窗上排名字 OCR 覆寫（測矛盾）
        self.q_shift = 0              # 上排被往左拖的量（拖到底 = team.QT_TOP_SHIFT；2026-10-12 實機）
        self.q_dark_edge = False      # 隊長角帶第 3 點是暗紅 (131,2,0)（2026-10-12 實機第 3 欄）

    def _prompt_color(self, x, y):
        if (x, y) == (1052, 167):
            return (195, 73, 49)
        if (x, y) in ((720, 665), (600, 665)):
            return (66, 113, 171)
        if (x, y) == (448, 325):
            return (251, 223, 187)
        for col in range(5):
            d = 133 * col - self.q_shift
            if (x, y) in [(px + d, py) for px, py in ((520, 243), (530, 243), (505, 255))]:
                if self.q_leader == col and self.q_dark_edge and y == 255:
                    return (131, 2, 0)
                return Q_RED if self.q_leader == col else Q_BROWN
            d = 133 * col
            if col < 4 and (x, y) in [(px + d, py) for px, py in ((505, 458), (520, 447), (530, 447))]:
                return Q_BLUE if col in self.q_members else Q_BROWN
        return None

    def color_at(self, x, y):
        if self.prompt:
            c = self._prompt_color(x, y)
            if c:
                return c
            if (x, y) == (1300, 745):
                return (127, 0, 0)        # 暗化的 HUD（SIG_HUD 不成立）
            if self.panel:
                for px, py, r, g, b, _ in screen_sigs.SIG_PANEL:
                    if (x, y) == (px, py):
                        return (37, 14, 9)
            return (0, 0, 0)
        if self.hud and not self.loading and not self.hud_never and (x, y) == (1300, 745):
            return (254, 0, 0)
        if self.loading or self.hud_never:
            for px, py, r, g, b, _ in screen_sigs.SIG_LOADING:
                if (x, y) == (px, py):
                    return (r, g, b)
        if self.panel:
            for px, py, r, g, b, _ in screen_sigs.SIG_PANEL:
                if (x, y) == (px, py):
                    return (r, g, b)
        for i, (x0, cy) in enumerate(team.SLOTS):
            if (x, y) == (x0, cy):
                return BEIGE if self.panel and i < len(self.cards) else BROWN
            if self.panel and i < len(self.cards):
                c = self.cards[i]
                if (x, y) in ((x0 + 6, cy), (x0 + 30, cy)):
                    return BLUE if c['status'] == 'current' else GREEN if c['status'] == 'online' else BROWN
                lx, ly = x0 + team.LABEL_DX, cy + team.LABEL_DY
                if c['label'] in ('leader', 'member') and ly + 10 <= y <= ly + 12 and lx + 10 <= x <= lx + 14:
                    return RED if c['label'] == 'leader' else YEL
                if c['label'] == 'solo' and ly + 24 <= y <= ly + 26 and lx + 4 <= x <= lx + 30:
                    return SOLO
                if ly + 20 <= y <= ly + 22 and lx + 10 <= x <= lx + 20:
                    return NORMAL
        return (0, 0, 0)

    def gui(self, *args, note=''):
        if args[0] == 'pixel':
            pts = [tuple(int(v) for v in p.split(',')) for p in args[1].split()]
            out = ' '.join('%d,%d,%d' % self.color_at(*p) for p in pts)
            if self.vanish_after_label and len(pts) > 500:
                self.panel = False
            if self.loading:
                self.loading -= 1
            return out
        if args[0] == 'seq':
            for part in args[1].split(';'):
                w = part.split()
                if w and w[0] == 'click':
                    xy = (int(w[1]), int(w[2]))
                    self.clicks.append(xy)
                    if self.prompt:
                        self._prompt_click(xy)
                    elif xy == uikit.SWITCH.open_xy and self.hud:
                        self.panel = True
                    elif xy == uikit.SWITCH.close_xy:
                        self.panel = False
                    elif self.panel and xy == (520, 578):
                        if not self.q_no_prompt:
                            self.prompt, self.q_leader, self.q_members = True, None, set(self.q_preselect)
                    elif self.panel:
                        for i, (x0, cy) in enumerate(team.SLOTS):
                            if i < len(self.cards) and xy[0] in range(x0, x0 + 300) and xy[1] in range(cy - 25, cy + 25):
                                self.panel = False                       # 點卡片：面板自己關 + 加載
                                if self.card_moves:
                                    for k, c in enumerate(self.cards):
                                        c['status'] = 'current' if k == i else 'online'
                                self.loading = self.after_load
                                self.hud_never = self.stuck
                elif w and w[0] == 'drag' and self.prompt and 230 <= int(w[2]) <= 420 and int(w[3]) < int(w[1]):
                    self.q_shift = team.QT_TOP_SHIFT                 # 上排往左拖：拖到底
                elif w and w[0] == 'key':
                    self.keys.append(w[1])
                    if w[1] == '{ESC}':
                        if self.prompt:
                            self.prompt = False          # ESC 只關提示，切換面板仍在
                        else:
                            self.panel = False
        return ''

    def _prompt_click(self, xy):
        x, y = xy
        if xy == (1052, 167):
            self.prompt = False
            return
        sx = x + (self.q_shift if y == 320 else 0)
        col = round((sx - 549) / 133) if abs((sx - 549) % 133) <= 40 or abs((sx - 549) % 133) >= 93 else None
        if y == 320 and col in range(5) and (col < 4 or self.q_shift) and len(self.cards) > col:
            if not self.q_leader_dead:
                self.q_leader = None if self.q_leader == col else col
        elif y == 520 and col in range(4):
            if self.q_leader is not None and col != self.q_dead_member:
                self.q_members ^= {col}
        elif xy == (720, 665) and not self.q_33231:
            self.prompt = False
            self.panel = False
            if self.q_leader is not None and not self.q_noop:
                for i, c in enumerate(self.cards):
                    c['label'] = 'leader' if i == self.q_leader else 'solo'
                others = [i for i in range(len(self.cards)) if i != self.q_leader]
                for j in self.q_members:
                    if j < len(others):
                        self.cards[others[j]]['label'] = 'member'
                if self.cards[self.q_leader]['status'] != 'current':
                    for i, c in enumerate(self.cards):
                        c['status'] = 'current' if i == self.q_leader else 'online'
                    self.loading = self.after_load

    def ocr(self, box, *opts):
        self.ocr_boxes.append((box, opts))
        if self.prompt and box[1] == 350:
            if self.prompt_ocr is not None:
                return list(self.prompt_ocr)
            col = round((box[0] + 40 - 549 + self.q_shift) / 133)
            if 0 <= col < len(self.cards) and (col < 4 or self.q_shift):
                return list(self.ocr_map.get(self.cards[col]['name'], []))
            return []
        for i, (x0, cy) in enumerate(team.SLOTS):
            if box[0] == x0 + team.NAME_BOX_DX and box[1] == cy + team.NAME_BOX_DY and i < len(self.cards):
                nm = self.cards[i]['name']
                return list(self.ocr_map.get(nm, []))
        return []

    def inner_clicks(self):
        return [c for c in self.clicks if c not in (uikit.SWITCH.open_xy, uikit.SWITCH.close_xy)]


def mk(labels=('leader', 'member', 'member', 'member', 'member'), names=NAMES, current=0):
    return [{'name': n, 'status': 'current' if i == current else 'online', 'label': lb} for i, (n, lb) in enumerate(zip(names, labels))]


def install(g):
    uikit.gui = g.gui
    uikit.ocr = g.ocr
    uikit.sleep = lambda s: None
    uikit.preflight = lambda src: 0
    uikit.snap = lambda tag: None
    return g


def run(fn, *a, **k):
    import io
    import contextlib
    buf, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(err):
        rc = fn(*a, **k)
    return rc, buf.getvalue()
