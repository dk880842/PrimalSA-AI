#!/usr/bin/env python3
"""離線測試共用：假寵物面板（Game）。pet 的測試用它：假 gui 依設定畫寵物面板像素（名字圖 / 等級黃字 / 狀態鈕 / 格子框 / 爪印 / 頭像框），
點擊會改狀態（選角色 / 選格 / 狀態鈕；鎖定戰寵 / 戰鬥中時狀態鈕沒反應）。不碰遊戲。"""
import hashlib
import random
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import pet  # noqa: E402
import petmatch  # noqa: E402
import screen_sigs  # noqa: E402
import uikit  # noqa: E402

ROLES = list(petmatch.AVATAR_Y)
INK_NAME, BG_NAME = (240, 224, 128), (176, 128, 80)
INK_LVL, BG_LVL = (255, 240, 0), (80, 120, 40)
INK_BROWN, BG_AV = (100, 70, 50), (240, 220, 190)
BTN_ON, BTN_OFF = (182, 124, 60), (245, 225, 192)
FRAME_SEL, FRAME_OFF = (251, 146, 4), (196, 183, 155)
AV_SEL, AV_OFF = (243, 195, 74), (211, 191, 163)

# 5×7 數字字型（x2 放大 → 10×14，高度 ≥ 5 才不會被 digitmatch.segment 當雜訊）
FONT = {
    '0': ['01110', '10001', '10001', '10001', '10001', '10001', '01110'],
    '1': ['00100', '01100', '00100', '00100', '00100', '00100', '01110'],
    '2': ['01110', '10001', '00001', '00110', '01000', '10000', '11111'],
    '3': ['11110', '00001', '00001', '01110', '00001', '00001', '11110'],
    '4': ['00010', '00110', '01010', '10010', '11111', '00010', '00010'],
    '5': ['11111', '10000', '11110', '00001', '00001', '10001', '01110'],
    '6': ['00110', '01000', '10000', '11110', '10001', '10001', '01110'],
    '7': ['11111', '00001', '00010', '00100', '01000', '01000', '01000'],
    '8': ['01110', '10001', '10001', '01110', '10001', '10001', '01110'],
    '9': ['01110', '10001', '10001', '01111', '00001', '00010', '01100'],
    '車': ['11111', '10101', '11111', '10101', '11111', '00100', '11111'],     # 「轉」左半（假）
    '專': ['11110', '01001', '11111', '01001', '11110', '01000', '11000'],     # 「轉」右半（假）
}


def _bits(rows):
    return [''.join(c * 2 for c in r) for r in rows for _ in range(2)]


_lvl_cache: dict = {}


def lvl_bitmap(level: int) -> list:
    if level not in _lvl_cache:
        _lvl_cache[level] = _lvl_bitmap(level)
    return _lvl_cache[level]


def _lvl_bitmap(level: int) -> list:
    """假的「0轉N」黃字點陣（w=petmatch.BOX_LVL 寬 × 高）：0、車、專、數字，字間 2 px、置中"""
    glyphs = [_bits(FONT[c]) for c in ('0', '車', '專') + tuple(str(level))]
    gw = len(glyphs[0][0])
    total = len(glyphs) * gw + (len(glyphs) - 1) * 3
    w, h = petmatch.BOX_LVL[2], petmatch.BOX_LVL[3]
    grid = [[0] * w for _ in range(h)]
    x0 = (w - total) // 2
    for k, g in enumerate(glyphs):
        for y, r in enumerate(g):
            for x, c in enumerate(r):
                if c == '1':
                    grid[8 + y][x0 + k * (gw + 3) + x] = 1
    return grid


_name_cache: dict = {}


def blob_bitmap(label: str, w: int, h: int, density: float = 0.12) -> list:
    """標籤 → 固定的偽隨機點陣（同標籤永遠相同、不同標籤 IoU 很低）"""
    key = (label, w, h)
    if key not in _name_cache:
        rnd = random.Random(int(hashlib.md5(label.encode()).hexdigest()[:8], 16))
        _name_cache[key] = [[1 if rnd.random() < density else 0 for _ in range(w)] for _ in range(h)]
    return _name_cache[key]


def mk_pets(**kw):
    """預設每個角色：1 瑪斯貝卡（騎乘 128）、2 迪基格斯（出戰 130）、其餘空。kw[role] = 5 格清單覆寫"""
    base = [{'name': '瑪斯貝卡', 'state': '騎乘', 'level': 128}, {'name': '迪基格斯', 'state': '出戰', 'level': 130}, None, None, None]
    return {r: [dict(p) if p else None for p in kw.get(r, base)] for r in ROLES}


class Game:
    def __init__(self, pets=None, hud=True, panel=False, depot=None):
        self.pets = pets or mk_pets()
        self.depot = depot or mk_depot(DKBO={'personal': ['摩娜西普', '朵拉比斯', '巴朵蘭恩']})
        self.view = 'pet'                # pet | depot
        self.dtab = 'personal'
        self.sel_kind = 'pet'            # pet | card（最後選的是哪種；右側面板與按鈕依它）
        self.sel_card = None
        self.resort = False              # 存入後倉庫依名字重新排序（實機 #84）
        self.compact = False             # 取出後後面的卡往前遞補（實機 #294 / #843：倉庫沒有空洞）；預設 False = 留空格（舊測試）
        self.store_dead = False          # 存入 / 取出鈕沒反應
        self.on_depot = None             # 進倉庫分頁時執行的 callback（模擬寵物欄被別人改動）
        self.btn_ocr_override = None
        self.dialog = False              # 「戰鬥 / 騎乘狀態存入確認」視窗
        self.confirm_on_store = True     # 存入戰鬥 / 騎乘狀態寵物會跳確認視窗（實機行為）
        self.confirm_on_take = False     # 測試用：取出也跳視窗（未預期）
        self.confirm_text = ['當前寵物為戰鬥或騎乘狀態，確定要存入倉庫?']
        self.dialog_clicks = []
        self.dialog_pending = None
        self.depot_dead = False          # 點「倉庫」分頁沒反應
        self.store_clicks, self.depot_clicks = [], []
        self.hud, self.panel = hud, panel
        self.role = 'DKBO'
        self.sel = 0
        self.locked = False              # 外掛鎖定戰寵：狀態鈕沒反應
        self.battle = False              # 戰鬥中（VS 牌在；狀態鈕沒反應）
        self.avatar_dead = False         # 點頭像沒反應（測 71）
        self.slot_dead = False           # 點寵物格沒反應
        self.avatar_label = {}           # 角色 → 覆寫頭像下名字圖用的標籤（測頭像名字樣板不符）
        self.clicks, self.keys, self.seqs = [], [], []
        self.state_clicks = []           # (角色, 格, 狀態) 每次點狀態鈕
        self.ocr_calls = []
        self.ocr_name_override = None    # 名字 OCR 回傳覆寫（list）
        self.ocr_level_mode = 'good'     # good | bad（三組都亂讀）| none
        self.card_lvl_ocr = False        # 倉庫卡綠字等級 OCR 讀得到（預設讀不到，實機未量）
        self.card_lvl_fn = None          # 倉庫卡綠字等級 OCR 改寫：fn(格 0 起算, 卡 dict, opts) → OCR 行（模擬 123 讀成 23、只有某組設定讀對）
        self.banner = 0                  # >0：接下來這麼多次「大塊取樣」（>5000 點）名字框被 EXP 橫幅蓋住（雜訊）
        self._banner_now = False
        self.slow_ui = 0                 # >0：點完先延遲這麼多次 pixel 才反映
        self._pending = []

    # ---- 畫面 ----
    def cur(self):
        return self.pets[self.role][self.sel]

    def color_at(self, x, y):
        if (x, y) == (1300, 745):
            return (254, 0, 0) if self.hud and not self.panel else (0, 0, 0)
        if (x, y) == (1310, 108):
            return (197, 71, 49) if self.panel else (0, 0, 0)
        if (x, y) == (706, 295):
            return (122, 227, 0) if self.battle and not self.panel else (0, 0, 0)
        if not self.panel:
            return (0, 0, 0)
        dv = self.view == 'depot'
        if self.dialog:
            for sx, sy, sr, sg, sb, _ in pet.CONFIRM_SIG:
                if (x, y) == (sx, sy):
                    return (sr, sg, sb)
        if (x, y) in _special_pts():
          for sx, sy, sr, sg, sb, _ in pet.DEPOT_SIG:
              if (x, y) == (sx, sy):
                  return (sr, sg, sb) if dv else (153, 125, 96)
          if (x, y) == pet.SUBTAB_PROBE['personal']:
              return (251, 219, 135) if dv and self.dtab == 'personal' else (171, 127, 84)
          if (x, y) == pet.SUBTAB_PROBE['public']:
              return (251, 219, 135) if dv and self.dtab == 'public' else (171, 127, 84)
          if (x, y) in pet.BTN_BODY:
              if not dv:
                  return (245, 225, 192)
              return (177, 65, 38) if self.sel_kind == 'pet' else (185, 125, 62)
          for c in range(5):
              for r in range(4):
                  cx, cy = pet.CARD_X[c], pet.CARD_Y[r]
                  idx = r * 5 + c
                  for px, dy, col in pet.PAW:
                      if (x, y) == (cx + px - 250, cy + dy):
                          return col if dv and self.depot[self.role][self.dtab][idx] is None else (30, 60, 90)
                  for dx, dy in pet.CARD_SEL:
                      if (x, y) == (cx + dx, cy + dy):
                          return (209, 151, 13) if dv and self.sel_kind == 'card' and self.sel_card == idx else (106, 70, 45)
        for i, cy in enumerate(pet.SLOT_Y):
            if x in pet.THUMB_X and (y - cy) in pet.THUMB_DY:
                return thumb_color(self.pets[self.role][i])
        for i, cy in enumerate(pet.SLOT_Y):
            if (x, y) == (pet.FRAME_DX, cy + pet.FRAME_DY):
                return FRAME_SEL if self.sel == i and self.cur() and self.sel_kind == 'pet' else FRAME_OFF
            for px, dy, col in pet.PAW:
                if (x, y) == (px, cy + dy):
                    return col if self.pets[self.role][i] is None else (30, 60, 90)
        for r in ROLES:
            if (x, y) == (83, petmatch.AVATAR_TOP_Y[r]):
                return AV_SEL if r == self.role else AV_OFF
        p = self.cur()
        if dv and self.sel_kind == 'card' and self.sel_card is not None:
            p = dict(self.depot[self.role][self.dtab][self.sel_card], state='等待', level=1)
        for s, pts in pet.BTN_PROBES.items():
            if (x, y) in pts:
                return BTN_ON if p and p['state'] == s else BTN_OFF
        bx, by, bw, bh = petmatch.BOX_NAME
        if bx <= x < bx + bw and by <= y < by + bh:
            if not p:
                return BG_NAME
            if self._banner_now:
                return INK_NAME if blob_bitmap('banner', bw, bh, 0.3)[y - by][x - bx] else BG_NAME
            return INK_NAME if blob_bitmap(p.get('unnamed') or p['name'], bw, bh)[y - by][x - bx] else BG_NAME
        bx, by, bw, bh = petmatch.BOX_LVL
        if bx <= x < bx + bw and by <= y < by + bh:
            if not p:
                return BG_LVL
            return INK_LVL if lvl_bitmap(p['level'])[y - by][x - bx] else BG_LVL
        for r in ROLES:
            ax, ay, aw, ah = petmatch.avatar_box(r)
            if ax <= x < ax + aw and ay <= y < ay + ah:
                lab = self.avatar_label.get(r, r)
                return INK_BROWN if blob_bitmap('AV' + lab, aw, ah, 0.2)[y - ay][x - ax] else BG_AV
        return (0, 0, 0)

    # ---- gui 假實作 ----
    def _apply(self, fn):
        if self.slow_ui:
            self._pending.append([self.slow_ui, fn])
        else:
            fn()

    def _tick(self):
        for it in list(self._pending):
            it[0] -= 1
            if it[0] <= 0:
                it[1]()
                self._pending.remove(it)

    def gui(self, *args, note=''):
        if args[0] == 'pixel':
            self._tick()
            self._banner_now = False
            pts = [tuple(int(v) for v in p.split(',')) for p in args[1].split()]
            if len(pts) > 5000 and self.banner > 0:
                self.banner -= 1
                self._banner_now = True
            return ' '.join('%d,%d,%d' % self.color_at(*p) for p in pts)
        if args[0] == 'seq':
            self.seqs.append(args[1])
            out = []
            for part in args[1].split(';'):
                w = part.split()
                if not w:
                    continue
                if w[0] == 'click':
                    xy = (int(w[1]), int(w[2]))
                    self.clicks.append(xy)
                    self._click(xy)
                elif w[0] == 'key':
                    self.keys.append(w[1])
                    if w[1] == '{ESC}':
                        self.panel = False
                elif w[0] == 'waitpix':
                    out.append(self._waitpix(w))
            return '\n'.join(out)
        return ''

    def _waitpix(self, w):
        tol = int(w[3]) if len(w) > 3 else 40
        ok = True
        for p in w[2].split('/'):
            neg = p.endswith('!')
            x, y, r, g, b = (int(v) for v in p.rstrip('!').split(','))
            c = self.color_at(x, y)
            near = all(abs(a - b_) <= tol for a, b_ in zip(c, (r, g, b)))
            ok = ok and (not near if neg else near)
        return 'ok 10' if ok else 'timeout'

    def _click(self, xy):
        x, y = xy
        if not self.panel:
            if xy == uikit.PET.open_xy and self.hud:
                self.panel = True
            return
        if self.dialog:
            self.dialog_clicks.append(xy)
            if xy == pet.CONFIRM_OK_XY:
                self.dialog = False
                fn, self.dialog_pending = self.dialog_pending, None
                if fn:
                    fn()
            elif xy in (pet.CONFIRM_CANCEL_XY, (946, 208)):
                self.dialog, self.dialog_pending = False, None
            return
        if xy == uikit.PET.close_xy:
            self.panel = False
            return
        if xy == pet.DEPOT_TAB_XY:
            self.depot_clicks.append(xy)
            if not self.depot_dead:
                self.view = 'depot'
                if self.on_depot:
                    self.on_depot(self)
            return
        if xy == pet.PET_TAB_XY:
            self.view = 'pet'
            return
        if self.view == 'depot':
            self.depot_clicks.append(xy)
            if xy in pet.SUBTAB_XY.values():
                self.dtab = 'personal' if xy == pet.SUBTAB_XY['personal'] else 'public'
                return
            for c in range(5):
                for r in range(4):
                    if abs(x - pet.CARD_X[c]) < 50 and abs(y - pet.CARD_Y[r] - pet.CARD_CLICK_DY) < 50:
                        if self.depot[self.role][self.dtab][r * 5 + c] is not None:
                            self.sel_card, self.sel_kind = r * 5 + c, 'card'
                        return
            if xy == pet.DEPOT_BTN_XY:
                self.store_clicks.append((self.role, self.sel_kind, self.sel, self.sel_card))
                if not self.store_dead and not self.battle:
                    self._store_or_take()
                return
        if x == 83:
            for r in ROLES:
                if abs(y - petmatch.AVATAR_Y[r]) <= 40 and not self.avatar_dead:
                    def f(r=r):
                        self.role, self.sel, self.sel_kind, self.sel_card = r, 0, 'pet', None
                    self._apply(f)
                    return
        if x == pet.SLOT_X and not self.slot_dead:
            for i, cy in enumerate(pet.SLOT_Y):
                if abs(y - cy) <= 50 and self.pets[self.role][i] is not None:
                    self._apply(lambda i=i: (setattr(self, 'sel', i), setattr(self, 'sel_kind', 'pet')))
                    return
        if abs(y - 702) <= 8 and self.view == 'pet':       # 寵物分頁的狀態鈕（含 530,697：與倉庫存入鈕同位置，點錯分頁會換騎寵）
            for s, (bx, by) in pet.BTN_XY.items():
                if abs(x - bx) <= 60:
                    p = self.cur()
                    self.state_clicks.append((self.role, self.sel, s))
                    if p and not self.locked and not self.battle:
                        def f(p=p, s=s):
                            if s == '騎乘':
                                for q in self.pets[self.role]:
                                    if q and q['state'] == '騎乘':
                                        q['state'] = '等待'
                            p['state'] = s
                        self._apply(f)
                    return

    def _store_or_take(self):
        pets, dep = self.pets[self.role], self.depot[self.role][self.dtab]
        if self.sel_kind == 'pet':
            p = pets[self.sel]
            if p is None or None not in dep:
                return

            def do(p=p):
                dep[dep.index(None)] = {k: p[k] for k in ('name', 'level', 'unnamed', 'species') if k in p}
                pets.pop(pets.index(p))
                pets.append(None)
                if self.resort:
                    fl = sorted([c for c in dep if c], key=lambda c: c['name'] + str(c.get('unnamed', '')))
                    dep[:] = fl + [None] * (len(dep) - len(fl))
            if self.confirm_on_store and p['state'] in ('出戰', '騎乘'):
                self.dialog, self.dialog_pending = True, do
                return
            do()
        elif self.confirm_on_take and self.sel_card is not None:
            self.dialog, self.dialog_pending = True, None
        elif self.sel_card is not None and None in pets:
            c = dep[self.sel_card]
            pets[pets.index(None)] = dict(c, state='等待')
            if self.compact:
                dep.pop(self.sel_card)
                dep.append(None)
            else:
                dep[self.sel_card] = None
            self.sel_card = None

    # ---- OCR ----
    def ocr(self, box, *opts):
        self.ocr_calls.append((tuple(box), opts))
        if tuple(box) == pet.BTN_BOX:
            if self.btn_ocr_override is not None:
                return list(self.btn_ocr_override)
            if self.view != 'depot':
                return ['出戰', '騎乘', '休息']
            return ['存入寵物'] if self.sel_kind == 'pet' else ['取出寵物']
        if tuple(box) == pet.CONFIRM_BOX:
            return list(self.confirm_text) if self.dialog else []
        if self.view == 'depot' and len(box) == 4 and tuple(box[2:]) == tuple(pet.CARD_LVL_BOX[2:]):     # 倉庫卡下緣綠字等級
            for idx in range(20):
                cx, cy = pet.card_xy(idx)
                if (box[0], box[1]) == (cx + pet.CARD_LVL_BOX[0], cy + pet.CARD_LVL_BOX[1]):
                    c = self.depot[self.role][self.dtab][idx]
                    if c and self.card_lvl_fn:
                        return list(self.card_lvl_fn(idx, c, opts))
                    return [f'0轉{c["level"]}級'] * 2 if c and self.card_lvl_ocr else []
            return []
        p = self.cur()
        if self.view == 'depot' and self.sel_kind == 'card' and self.sel_card is not None and tuple(box) == petmatch.BOX_NAME:
            p = dict(self.depot[self.role][self.dtab][self.sel_card])
        if tuple(box) == petmatch.BOX_NAME:
            if self.ocr_name_override is not None:
                return list(self.ocr_name_override)
            if p and p.get('unnamed'):
                return [p['unnamed'], p['unnamed'], p['unnamed'].rsplit('/', 2)[0] + '/' + p['unnamed'].split('/')[-1]]
            return [p['name']] * 3 if p else []
        import petwatch
        if tuple(box) == tuple(petwatch.LEVEL_BOX) and p:
            if self.ocr_level_mode == 'none':
                return []
            if self.ocr_level_mode == 'bad':                  # 三組各讀出不同值
                return ['0轉' + str(p['level'] + 1 + len(self.ocr_calls) % 7)]
            lv = p['level']
            dark = opts[opts.index('-Dark') + 1] if '-Dark' in opts else 0
            if dark == 70:                                    # 實測：-Dark 70 會把 128 讀成 1
                return [f'0轉{str(lv)[0]}', f'0轉{lv}']
            return [f'0轉{lv}', f'轉{lv}']
        return []


def mk_depot(**kw):
    """每個角色的倉庫：{'personal': 20 格, 'public': 20 格}（None = 空；項目 {'name','level'}）。kw[role] = {'personal': [名字...], 'public': [...]}"""
    out = {}
    for r in ROLES:
        d = kw.get(r, {})
        out[r] = {t: [((n if isinstance(n, dict) else {'name': n, 'level': 1}) if n else None) for n in (list(d.get(t, [])) + [None] * 20)[:20]] for t in ('personal', 'public')}
    return out


_SPECIAL = None


def _special_pts():
    global _SPECIAL
    if _SPECIAL is None:
        pts = {(x, y) for x, y, *_ in pet.DEPOT_SIG} | set(pet.SUBTAB_PROBE.values()) | set(pet.BTN_BODY)
        for c in range(5):
            for r in range(4):
                cx, cy = pet.CARD_X[c], pet.CARD_Y[r]
                pts |= {(cx + px - 250, cy + dy) for px, dy, _ in pet.PAW} | {(cx + dx, cy + dy) for dx, dy in pet.CARD_SEL}
        _SPECIAL = pts
    return _SPECIAL


def thumb_color(p):
    """寵物格縮圖點的顏色：同名同等級固定、不同名差很多；空格 = 爪印底"""
    if p is None:
        return (170, 138, 92)
    h = hashlib.md5(('%s/%s' % (p.get('species') or p['name'], p['level'])).encode()).digest()
    return (40 + h[0] % 180, 40 + h[1] % 180, 40 + h[2] % 180)


def install(g):
    """把假 gui / ocr 裝進 uikit / petwatch / heal；回 g。假面板沒畫頭像 → 關掉縮圖認物種（pet.IMG_ON；接線測試自己開）"""
    import heal
    import petwatch
    pet.IMG_ON = False
    pet.GLYPH_ON = False                 # 假面板的名字框 / 卡片字不是遊戲字型（字形樣板測試在 test_petglyph.py 用實機點陣）
    uikit.gui = g.gui
    uikit.sleep = lambda s: None
    t = [0.0]

    def clk():
        t[0] += 0.05
        return t[0]
    uikit.clock = clk
    uikit.preflight = lambda src: 0
    uikit.snap = lambda tag: None
    petwatch.ocr = g.ocr
    heal.gui = g.gui
    return g
