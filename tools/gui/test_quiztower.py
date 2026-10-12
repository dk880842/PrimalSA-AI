#!/usr/bin/env python3
"""quiztower.py 離線測試（不碰遊戲）：題庫、安全閘、選項圖比對（合成選項圖）、假 gui 模擬整座塔（巡路沒反應退回 walk、續跑、各種停手）。
沒有 10-09 爬塔時的答題視窗截圖（tools/.cache 已被覆蓋），選項畫面用 tools/.cache/pet-images/static/ 的靜態圖合成：
縮放 / 平移 / 亮度 / 雜訊 / 底色 / 卡片框都隨機。
用法：uv run --no-project python tools/gui/test_quiztower.py [--full]   （--full = 比對準確度跑全部題庫 × 3 次 × 2 組難度，約 1.5 分鐘）"""
import os
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import testenv  # noqa: E402,F401  紀錄檔轉向暫存
os.environ.setdefault('PSA_LAYOUT', '2880x1659')   # import quest（不可逆關鍵字）時不去問遊戲視窗大小
import quiztower as q  # noqa: E402

FAILS = []


def check(name, cond, detail=''):
    print(('OK  ' if cond else 'FAIL') + f' {name}' + (f'  ({detail})' if detail and not cond else ''))
    if not cond:
        FAILS.append(name)


BANK = q.build_bank()

# ---------------------------------------------------------------- 題庫
seen = {'諾克斯': 100917, '加格': 100341, '烏寶寶': 100263, '朵洛將恩': 100392, '哥斯哥斯': 100892}   # 10-09 實際出現、全部答對的題
for n, img in seen.items():
    check(f'題庫：{n} 正解 {img}', n in BANK and BANK[n]['correct'] == img, BANK.get(n))
    check(f'題庫：{n} 有靜態圖', q.static_path(img) is not None and q.static_path(img).exists())
check('題庫：系別 / 不是 / 屬於 題不收', all(q.name_of_title(t) is None for t in
                                         ('以下哪個不是人龍系?', '以下哪只寵物屬於烏龜系？', '下列圖片中哪只寵物不是烏力系？', '四聖獸中水屬性的聖獸是?')))
check('題庫：玄武（選項沒有叫玄武的圖）不收；白虎有同圖怪物叫白虎 → 收', '玄武' not in BANK and BANK['白虎']['correct'] == 100872)
check('題庫：斑尼迪克多組選項合併成 5 張候選', len(BANK['斑尼迪克']['cands']) == 5)

# ---------------------------------------------------------------- 樓層資料與知識庫核對
sys.path.insert(0, str(q.ROOT / 'tools' / 'query'))
import psa  # noqa: E402
warps = psa.T('MapWarp')
npcs = psa.T('Npc')
for m in q.QUIZ_FLOORS:
    fi = q.floor_info(m)
    ex = [(w['fX'], w['fY']) for w in warps if w.get('fMap') == m and w.get('tMap') == fi['up']]
    check(f'{m}：出口 {fi["exit"]} → {fi["up"]}', fi['exit'] in ex, ex)
    ent = [(w['tX'], w['tY']) for w in warps if w.get('tMap') == m and w.get('fMap') == m - 1 and m > 800]
    if m > 800:
        check(f'{m}：進場 {fi["entry"]}', fi['entry'] in ent, ent)
    gd = [(n.get('x'), n.get('y')) for n in npcs if n.get('mapId', n.get('map')) == m]
    if gd and gd[0][0] is not None:
        check(f'{m}：守衛 {fi["guard"]} 在 Npc 表', fi['guard'] in gd, gd)

# ---------------------------------------------------------------- 題目解析
P = q.parse_question
check('題目：原句', P(['以下哪只寵物的名字叫做“諾克斯”'], BANK)[0] == '諾克斯')
check('題目：OCR 斷行 + 雜字', P(['知識答題', '以下哪只寵物的名字', '叫做「諾克斯」', 'A B C D', '確認'], BANK)[0] == '諾克斯')
check('題目：句型二（加格）', P(['下列圖片中哪只寵物叫加格？'], BANK)[0] == '加格')
check('題目：句型三（烏寶寶）', P(['以下哪只寵物叫做烏寶寶?'], BANK)[0] == '烏寶寶')
check('題目：加比 / 加比奧 取長名', P(['以下哪只是加比奧？'], BANK)[0] == '加比奧')
check('題目：加比', P(['以下哪只是加比？'], BANK)[0] == '加比')
check('題目：不是 X → 不認', P(['以下哪只寵物不是諾克斯'], BANK)[0] is None)
check('題目：名字不在題庫 → 不認', P(['以下哪只寵物的名字叫做“烏力烏力”'], BANK)[0] is None)
check('題目：沒有「哪只」→ 不認', P(['請選出諾克斯'], BANK)[0] is None)
check('題目：驗證視窗樣的字 → 不認', P(['防外掛驗證', '請點選正確的圖片'], BANK)[0] is None)

# ---------------------------------------------------------------- 安全閘四條件
G = q.gate
T0 = 1000.0
good = ['知識答題', '以下哪只寵物的名字叫做“諾克斯”']
check('閘：四條件都符合 → 作答', G(803, T0, T0 + 2, good, BANK) == (True, '諾克斯'))
check('閘：810 也算塔內', G(810, T0, T0 + 2, good, BANK)[0])
r = G(1000, T0, T0 + 2, good, BANK)
check('閘缺①：地圖不是 800～810 → 停', not r[0] and r[1].startswith('①'), r)
r = G(None, T0, T0 + 2, good, BANK)
check('閘缺①：地圖讀不到 → 停', not r[0] and r[1].startswith('①'), r)
r = G(803, None, T0 + 2, good, BANK)
check('閘缺②：沒按過「猜謎答題」→ 停', not r[0] and r[1].startswith('②'), r)
r = G(803, T0, T0 + q.GATE_WINDOW_S + 1, good, BANK)
check('閘缺②：按「猜謎答題」太久以前 → 停', not r[0] and r[1].startswith('②'), r)
r = G(803, T0, T0 + 2, ['以下哪只寵物的名字叫做“諾克斯”'], BANK)
check('閘缺③：沒有「知識答題」標題 → 停', not r[0] and r[1].startswith('③'), r)
r = G(803, T0, T0 + 2, ['防腳本驗證', '以下哪只寵物的名字叫做“諾克斯”'], BANK)
check('閘缺③：標題是「防腳本驗證」→ 停', not r[0] and r[1].startswith('③'), r)
r = G(803, T0, T0 + 2, ['知識答題', '四聖獸中水屬性的聖獸是?'], BANK)
check('閘缺④：不是名字題 → 停', not r[0] and r[1].startswith('④'), r)
r = G(803, T0, T0 + 2, ['知識答題', '以下哪個不是人龍系?'], BANK)
check('閘缺④：「不是」題 → 停', not r[0] and r[1].startswith('④'), r)

# ---------------------------------------------------------------- decide（純矩陣）
d = q.decide([[0.9, 0.5, 0.4, 0.3], [0.5, 0.9, 0.4, 0.3], [0.4, 0.4, 0.9, 0.3], [0.3, 0.3, 0.3, 0.9]], [1, 2, 3, 4], 3)
check('decide：明確 → 選 C', d['ok'] and d['choice'] == 2, d)
d = q.decide([[0.80, 0.5, 0.79, 0.3], [0.5, 0.9, 0.4, 0.3], [0.79, 0.4, 0.80, 0.3], [0.3, 0.3, 0.3, 0.9]], [1, 2, 3, 4], 3)
check('decide：兩格幾乎一樣 → 不明確', not d['ok'], d)
d = q.decide([[0.4] * 4] * 4, [1, 2, 3, 4], 3)
check('decide：全部一樣 → 不明確', not d['ok'], d)
d = q.decide([[0.9, 0.5, 0.4, 0.3]] * 4, [1, 2, 3], 3)
check('decide：候選不足 → 不作答', not d['ok'] and d['choice'] is None, d)


# ---------------------------------------------------------------- 合成選項畫面
def render(opts, rng, bg=(229, 197, 155), frame=(120, 80, 40), scale=(0.9, 1.6), noise=6, shift=4, bright=(0.95, 1.05),
           w=1090, h=520):
    """opts = 4 張 Img（或 None = 空格）→ 只畫選項區的假截圖（座標同真截圖）"""
    px = [bg + (255,)] * (w * h)
    for i, img in enumerate(opts):
        cx, cy = q.OPT_XS[i], q.OPT_Y
        fx0, fy0 = cx - 68, cy - 68
        if frame:
            for k in range(136):
                for t in range(2):
                    for (x, y) in ((fx0 + k, fy0 + t), (fx0 + k, fy0 + 135 - t), (fx0 + t, fy0 + k), (fx0 + 135 - t, fy0 + k)):
                        px[y * w + x] = frame + (255,)
        if img is None:
            continue
        s = rng.uniform(*scale)
        tw, th = max(1, int(img.w * s)), max(1, int(img.h * s))
        if max(tw, th) > 120:
            f = 120 / max(tw, th)
            tw, th = int(tw * f), int(th * f)
        ox, oy = cx - tw // 2 + rng.randint(-shift, shift), cy - th // 2 + rng.randint(-shift, shift)
        b = rng.uniform(*bright)
        for y in range(th):
            sy = min(img.h - 1, int(y * img.h / th))
            for x in range(tw):
                sx = min(img.w - 1, int(x * img.w / tw))
                r_, g_, b_, a = img.px[sy * img.w + sx]
                if a == 0:
                    continue
                al = a / 255
                o = px[(oy + y) * w + ox + x]
                px[(oy + y) * w + ox + x] = tuple(max(0, min(255, int(v * b * al + o[j] * (1 - al) + rng.randint(-noise, noise))))
                                                  for j, v in enumerate((r_, g_, b_))) + (255,)
    return q.Img(w, h, px)


def scene(name, rng, **kw):
    """→ (假截圖, 正解在第幾格)"""
    e = BANK[name]
    others = [c for c in e['cands'] if c != e['correct']]
    rng.shuffle(others)
    shown = [e['correct']] + others[:3]
    rng.shuffle(shown)
    return render([q.load_png(q.static_path(c)) for c in shown], rng, **kw), shown.index(e['correct'])


def accuracy(names, trials, rng, **kw):
    res = {'對': 0, '錯': 0, '不明確': 0}
    for n in names:
        for _ in range(trials):
            shot, want = scene(n, rng, **kw)
            r = q.answer_from_image(shot, n, BANK)
            res['對' if r.get('ok') and r['choice'] == want else '錯' if r.get('ok') else '不明確'] += 1
    return res


rng = random.Random(20261012)
for n in seen:
    shot, want = scene(n, rng)
    r = q.answer_from_image(shot, n, BANK)
    check(f'比對：{n} 選對（第 {"ABCD"[want]} 格）', r.get('ok') and r['choice'] == want, r)
# 兩格放同一張正解圖 → 不明確（不猜）
e = BANK['諾克斯']
imgs = [q.load_png(q.static_path(c)) for c in (e['correct'], e['correct'], 100916, 100918)]
r = q.answer_from_image(render(imgs, rng), '諾克斯', BANK)
check('比對：兩格都像正解 → 不明確停手', not r.get('ok'), r)
# 正解根本不在畫面上（四格都是別的寵物）→ 不該高信心選
imgs = [q.load_png(q.static_path(c)) for c in (100916, 100918, 100919, 100916)]
r = q.answer_from_image(render(imgs, rng), '諾克斯', BANK)
check('比對：正解不在畫面 → 不明確停手', not r.get('ok'), r)
# 空格（框位置不對）→ 讀不到
imgs = [q.load_png(q.static_path(c)) for c in (100916, 100917, 100918)] + [None]
r = q.answer_from_image(render(imgs, rng), '諾克斯', BANK)
check('比對：有一格裁不到圖 → 不作答', not r.get('ok') and 'S' not in r, r)

full = '--full' in sys.argv
names = sorted(BANK)
if full:
    for label, kw in (('一般', dict()), ('嚴苛', dict(scale=(0.6, 2.0), noise=14, shift=8, bright=(0.85, 1.15)))):
        res = accuracy(names, 3, random.Random(7), **kw)
        print(f'準確度（{label}，題庫 {len(names)} 題 × 3）：{res}')
        check(f'準確度（{label}）：0 錯', res['錯'] == 0, res)
else:
    res = accuracy(names, 1, random.Random(7), scale=(0.6, 2.0), noise=14, shift=8, bright=(0.85, 1.15))
    print(f'準確度（嚴苛，題庫 {len(names)} 題 × 1）：{res}')
    check('準確度：0 錯、不明確 ≤ 10%', res['錯'] == 0 and res['不明確'] <= len(names) // 10, res)

# ---------------------------------------------------------------- 假 gui：整座塔
QUESTIONS = {800: ('諾克斯', '以下哪只寵物的名字叫做“諾克斯”'), 801: ('加格', '下列圖片中哪只寵物叫加格？'),
             802: ('烏寶寶', '以下哪只寵物叫做烏寶寶？'), 803: ('朵洛將恩', '以下圖中哪只寵物叫做朵洛將恩？'),
             804: ('哥斯哥斯', '下列圖中哪只寵物叫哥斯哥斯？'), 805: ('諾克斯', '以下哪只寵物的名字叫做“諾克斯”'),
             806: ('斑尼迪克', '以下哪只是斑尼迪克？'), 807: ('巴克亞司', '以下哪只寵物的名字叫做“巴克亞司”'),
             808: ('諾克斯', '以下哪只寵物的名字叫做“諾克斯”'), 809: ('奇卡寶斯', '以下哪只寵物的名字叫做“奇卡寶斯”')}
_SCENES: dict = {}


class Fake:
    """模擬猜謎三兄弟的家：座標、圍欄（答對才開）、守衛 / 伊那多對話框、答題視窗、追蹤巡路（works / dead）"""

    def __init__(self, at=(811, 29, 15), track='dead', answered=(), title='知識答題', questions=None, wrong_stays=True,
                 guard_buttons=('猜謎答題', '再見'), inado_body=('拿去吧',), walk_fail=False, pre_rc=0):
        self.m, self.x, self.y = at
        self.track_mode, self.answered = track, set(answered)
        self.title, self.questions = title, {**QUESTIONS, **(questions or {})}
        self.guard_buttons, self.inado_body = guard_buttons, inado_body
        self.walk_fail, self.pre_rc = walk_fail, pre_rc
        self.screen, self.dlg, self.picked = 'idle', None, None
        self.t, self.log, self.clicks, self.quiz_clicks, self.events = 0.0, [], [], [], []
        self.walks, self.tracks = [], 0
        self.got_pet = False

    # 時間
    def now(self):
        return self.t

    def sleep(self, s):
        self.t += s

    # 讀
    def preflight(self):
        return self.pre_rc

    def pos(self):
        return None if self.screen == 'quiz' else (self.m, self.x, self.y)

    def screen_state(self):
        return {'quiz': 'unknown'}.get(self.screen, self.screen)

    def hud_ok(self):
        return self.screen != 'quiz'

    def has_grid(self, m, a, b):
        return m != 800

    def npc_xy(self, npc, at):
        return (683, 358)

    def track(self):
        self.tracks += 1
        if self.track_mode == 'works' and self.m in q.QUIZ_FLOORS:
            fi = q.floor_info(self.m)
            if (self.m not in self.answered):
                self.x, self.y = fi['stand']
        return True

    # 動
    def _floor_up(self, m):
        self.m = m
        if m == 810:
            self.x, self.y = 28, 27
        else:
            self.x, self.y = q.floor_info(m)['entry']

    def walk_to(self, m, x, y, exit_map=None, auto=True):
        self.walks.append((m, x, y, exit_map))
        if self.walk_fail or m != self.m:
            raise RuntimeError(f'不在地圖 {m}')
        fence = m in q.QUIZ_FLOORS and m not in self.answered and y < q.floor_info(m)['guard'][1] <= self.y
        if fence:                      # 圍欄沒開：停在守衛那排南邊
            self.x, self.y = x, q.floor_info(m)['stand'][1]
            return (self.m, self.x, self.y)
        if exit_map is not None:
            self._floor_up(exit_map)
            return (self.m, self.x, self.y)
        self.x, self.y = x, y
        return (self.m, self.x, self.y)

    def ground_clicks(self, pts):
        self.log.append(('ground', tuple(pts)))
        self.x, self.y = 27, 22

    def primer(self):
        pass

    def click(self, x, y, note):
        self.clicks.append((x, y))
        if self.screen == 'idle' and self.m in q.QUIZ_FLOORS and (self.x, self.y) == q.floor_info(self.m)['stand'] \
                and (x, y) in q.GUARD_CLICKS[self.m % 2]:
            self.screen, self.dlg = 'dialog', 'guard'
        elif self.screen == 'idle' and self.m == 810 and (self.x, self.y) == q.INADO_STAND and (x, y) == (683, 358):
            self.screen, self.dlg = 'dialog', 'inado1'
        elif self.screen == 'dialog' and (x, y) == q.DIALOG_LEFT:
            if self.dlg == 'guard':
                self.screen, self.dlg, self.picked = 'quiz', None, None
            elif self.dlg == 'inado1':
                self.dlg = 'inado2'
            elif self.dlg == 'inado2':
                self.screen, self.dlg, self.got_pet = 'idle', None, True
                self.m, self.x, self.y = 811, 29, 24

    def dialog_buttons(self):
        if self.screen != 'dialog':
            return []
        words = {'guard': self.guard_buttons, 'inado1': ('拿金豬', '再見'), 'inado2': ('完成', '再見')}[self.dlg]
        return [{'text': t, 'x': 948 if i == 0 else 1220, 'y': 461} for i, t in enumerate(words)]

    def dialog_body(self):
        return list(self.inado_body) if self.dlg and self.dlg.startswith('inado') else ['回答我的問題']

    def quiz_texts(self):
        if self.screen != 'quiz':
            return []
        return [self.title, self.questions[self.m][1], 'A', 'B', 'C', 'D', '確認']

    def _scene(self):
        name = self.questions[self.m][0]
        if (self.m, name) not in _SCENES:
            _SCENES[(self.m, name)] = scene(name, random.Random(self.m))
        return _SCENES[(self.m, name)]

    def shot(self):
        return self._scene()[0] if self.screen == 'quiz' else None

    def quiz_click(self, x, y, note):
        if self.screen != 'quiz':
            return False
        self.quiz_clicks.append((x, y))
        if (x, y) == q.CONFIRM:
            want = self._scene()[1]
            if self.picked == want:
                self.answered.add(self.m)
                self.screen = 'idle'
            elif not self.wrong_stays_open():
                self.screen = 'idle'
        else:
            self.picked = q.OPT_XS.index(x)
        return True

    def wrong_stays_open(self):
        return True

    def snap(self, tag):
        return None

    def errlog(self, msg):
        self.log.append(('errlog', msg))

    def event(self, msg, shot=None):
        self.events.append(msg)


def go(fake, **kw):
    q.PROGRESS.unlink(missing_ok=True)
    return q.Runner(fake, dict(bank=BANK, no_dump=True, **kw)).run(), fake


# 整座塔：追蹤沒反應（noTaskNavigate）→ 第一次後就不再點，全程 walk
rc, f = go(Fake(track='dead'))
check('整座塔（追蹤沒反應）：rc 0、拿到金布伊', rc == 0 and f.got_pet, (rc, f.events[-3:]))
check('整座塔：10 層全部答對', f.answered == set(q.QUIZ_FLOORS), f.answered)
check('整座塔：追蹤只試 1 次（沒反應後整次改 walk.py）', f.tracks == 1, f.tracks)
check('整座塔：事件有「noTaskNavigate → 改 walk.py」', any('改 walk.py' in e for e in f.events))
check('整座塔：800 層照紀錄點地面', ('ground', tuple(q.FLOOR800_CLICKS)) in f.log, f.log)
check('整座塔：答題視窗內只點 QUIZ_CLICKS', all(c in q.QUIZ_CLICKS for c in f.quiz_clicks))
check('整座塔：每層剛好 2 下（選項 + 確認）', len(f.quiz_clicks) == 20, len(f.quiz_clicks))

# 追蹤能巡路：點追蹤就到守衛下方，不用 walk 到守衛
rc, f = go(Fake(at=(803, 32, 26), track='works'))
check('追蹤會巡路：rc 0', rc == 0 and f.got_pet, (rc, f.events[-3:]))
check('追蹤會巡路：不用 walk.py 走到守衛下方', not any(w[3] is None and (w[1], w[2]) == q.floor_info(w[0])['stand'] for w in f.walks), f.walks)
check('追蹤會巡路：每層試 1 次（803～810 = 8 次）', f.tracks == 8, f.tracks)

# 續跑：從目前樓層開始
rc, f = go(Fake(at=(805, 18, 20), track='dead'))
check('續跑：805 守衛下方開始 → rc 0', rc == 0 and f.got_pet)
check('續跑：只答 805～809（不回頭）', f.answered == set(range(805, 810)), f.answered)
check('續跑：沒在 800～804 走路', all(w[0] >= 805 for w in f.walks), f.walks)
rc, f = go(Fake(at=(806, 29, 15), track='dead'))
check('續跑：806 已在圍欄內（答過）→ 直接走出口、不點守衛', rc == 0 and 806 not in f.answered and f.walks[0] == (806, 29, 13, 807), f.walks[:2])
rc, f = go(Fake(at=(810, 28, 27), track='dead'))
check('續跑：810 → 直接找伊那多', rc == 0 and f.got_pet and not f.quiz_clicks)

# 安全閘：標題 / 題目不符 → 9、答題視窗內一下都沒點
rc, f = go(Fake(at=(802, 29, 20), title='防腳本驗證'))
check('閘（實跑）：標題不是知識答題 → rc 9、0 次答題點擊', rc == 9 and not f.quiz_clicks, (rc, f.quiz_clicks))
rc, f = go(Fake(at=(802, 29, 20), questions={802: ('諾克斯', '以下哪個不是人龍系?')}))
check('閘（實跑）：題目不是名字題 → rc 9、0 次答題點擊', rc == 9 and not f.quiz_clicks, (rc, f.quiz_clicks))
rc, f = go(Fake(at=(802, 29, 20), pre_rc=9))
check('閘（實跑）：preflight 認為有驗證視窗 → rc 9、什麼都沒點', rc == 9 and not f.clicks and not f.quiz_clicks)

# 比對不明確 → 135，視窗留著
_SCENES[(804, '哥斯哥斯')] = (render([q.load_png(q.static_path(c)) for c in (100892, 100892, 100354, 100396)], random.Random(1)), 0)
rc, f = go(Fake(at=(804, 29, 20)))
check('不明確：rc 135、答題視窗內 0 點擊', rc == q.EXIT_UNSURE and not f.quiz_clicks and f.screen == 'quiz', (rc, f.quiz_clicks))
del _SCENES[(804, '哥斯哥斯')]

# 答錯（確認後視窗沒關）→ 136：假場景故意標錯正解位置
img, want = scene('加格', random.Random(801))
_SCENES[(801, '加格')] = (img, (want + 1) % 4)
rc, f = go(Fake(at=(801, 18, 20)))
check('答錯：確認後視窗沒關 → rc 136', rc == q.EXIT_WRONG, (rc, f.events[-2:]))
del _SCENES[(801, '加格')]

# 守衛對話框不是猜謎答題 → 132
rc, f = go(Fake(at=(800, 29, 20), guard_buttons=('再見',)))
check('守衛按鈕不對：rc 132、沒按對話框', rc == q.EXIT_GUARD and q.DIALOG_LEFT not in f.clicks, rc)
# 伊那多對話含不可逆關鍵字 → 138
rc, f = go(Fake(at=(810, 28, 17), inado_body=('把寵物轉生吧',)))
check('伊那多：對話含「轉生」→ rc 138、沒按', rc == q.EXIT_IRREV and q.DIALOG_LEFT not in f.clicks, rc)
# 走路失敗 → 131
rc, f = go(Fake(at=(803, 32, 26), walk_fail=True))
check('走路失敗：rc 131', rc == q.EXIT_WALK, rc)
# 不在塔、追蹤沒反應 → 130
rc, f = go(Fake(at=(60049, 30, 25)))
check('不在塔：rc 130', rc == q.EXIT_NOT_TOWER, rc)

# 進度檔：記答過但圍欄其實沒開 → 清掉重做守衛
q.PROGRESS.unlink(missing_ok=True)
fk = Fake(at=(807, 18, 20))
rn = q.Runner(fk, dict(bank=BANK, no_dump=True))
rn.prog['floors']['807'] = {'ts': fk.now()}
rc = rn.run()
check('進度檔誤記答過：清掉後重答 807 → rc 0', rc == 0 and 807 in fk.answered, (rc, fk.events[-4:]))


# dry-run 完全不碰遊戲
class Boom:
    def __getattr__(self, k):
        raise AssertionError(f'dry-run 呼叫了 {k}')


check('dry-run：rc 0、不碰遊戲', q.run(dry_run=True, tools=Boom()) == 0)
lines = q.plan_lines(803)
check('dry-run --at 803：從 803 列到 810', lines[1].startswith('803') and lines[-2].startswith('810') and not any(ln.startswith('802') for ln in lines))

print(f'\n{"全部通過" if not FAILS else f"失敗 {len(FAILS)} 項：{FAILS}"}')
sys.exit(1 if FAILS else 0)
