#!/usr/bin/env python3
"""petglyph 離線測試（實機 2026-10-14 擷取的二值點陣 fixtures/petglyph_samples.json；不碰遊戲）。
跑法：uv run --no-project python tools/gui/test_petglyph.py"""
import testenv  # noqa: F401  （紀錄檔轉暫存）
import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import petglyph as G  # noqa: E402
import petmatch  # noqa: E402

petmatch.TPL_DIR = Path(tempfile.mkdtemp())          # 學到的字形寫暫存，不碰 tools/.cache
G.load_tpl(reload=True)
FX = json.loads(G.SAMPLES_FILE.read_text(encoding='utf-8'))
fails = 0


def check(name, ok, extra=''):
    global fails
    print(('PASS ' if ok else 'FAIL ') + name + (f'  {extra}' if extra and not ok else ''))
    fails += 0 if ok else 1


def drop(rows, seg):
    x0, y0, g = seg
    r2 = [list(r) for r in rows]
    for j, row in enumerate(g):
        for i, c in enumerate(row):
            if c == '1':
                r2[y0 + j][x0 + i] = '0'
    return [''.join(r) for r in r2]


# ---- 讀字 ----
for s in FX['cream']:
    check(f'名字框成長字串 {s["want"]}', G.read_growth(s['rows'], 'cream') == s['want'], G.read_growth(s['rows'], 'cream'))
for s in FX['cream_none']:
    check(f'被橫幅蓋住的名字框 {s["key"]} → None（不猜）', G.read_growth(s['rows'], 'cream') is None)
for s in FX['white']:
    check(f'卡片白字成長字串 {s["want"]}', G.read_growth(s['rows'], 'white') == s['want'])
for s in FX['name']:
    check(f'卡片名字整塊圖 {s["want"]}', G.read_card_name(s['rows'])[0] == s['want'])
    check(f'卡片名字 {s["want"]} 不會被讀成成長字串', G.read_growth(s['rows'], 'white') is None)
for s in FX['green']:
    check(f'卡片綠字等級 {s["want"]}', G.read_card_level(s['rows']) == s['want'], G.read_card_level(s['rows']))

# ---- 少一個字（被蓋掉）→ 一律 None，不會讀成別的合法字串（49/10/8/1 掉 0 → 49/1/8/1 也要擋：字距）----
n = bad = 0
for kind, key, fn in (('cream', 'cream', lambda r: G.read_growth(r, 'cream')), ('white', 'white', lambda r: G.read_growth(r, 'white')),
                      ('green', 'green', G.read_card_level)):
    for s in FX[key]:
        for seg in G.segs_of(s['rows']):
            n += 1
            bad += fn(drop(s['rows'], seg)) is not None
check(f'少一個字 → None（{n} 種）', bad == 0, f'{bad} 種讀出值')

# ---- 位移（置中檢查）----
s = FX['cream'][0]
shifted = ['0' * 8 + r[:-8] for r in s['rows']]
check('名字框字串整體右移 8 px（不置中）→ None', G.read_growth(shifted, 'cream') is None)

# ---- 學字：拿掉某字的樣板 → 讀不出 → 用可信標籤學 → 讀得出；標籤矛盾 → 不學 ----
tpl = G.load_tpl()
s = next(x for x in FX['cream'] if '2' in x['want'])
saved = tpl['cream'].pop('2')
G._MATCHERS.clear()
check('拿掉 cream「2」→ 讀不出', G.read_growth(s['rows'], 'cream') is None)
wrong = s['want'].replace('8', '3', 1)
check('標籤跟已認得的字矛盾（8 標成 3）→ 不學', G.learn_growth(s['rows'], wrong, 'cream') == 0)
check('可信標籤 → 學到新字', G.learn_growth(s['rows'], s['want'], 'cream') >= 1)
check('學完讀得出', G.read_growth(s['rows'], 'cream') == s['want'])
check('學到的寫在 petmatch.TPL_DIR（暫存）', G.learn_file().exists() and str(G.learn_file()).startswith(str(petmatch.TPL_DIR)))
check('種子檔沒被改', '2' in json.loads(G.SEED_FILE.read_text(encoding='utf-8'))['cream'])
G.learn_file().unlink()
G.load_tpl(reload=True)

# ---- 綠字等級學字（只學等級數字）----
s = next(x for x in FX['green'] if x['want'] >= 100)
tpl = G.load_tpl()
digit = str(s['want'])[1]
saved = tpl['green'].pop(digit)
G._MATCHERS.clear()
check(f'拿掉 green「{digit}」→ 等級讀不出', G.read_card_level(s['rows']) is None)
check('等級標籤學字', G.learn_card_level(s['rows'], s['want']) >= 1 and G.read_card_level(s['rows']) == s['want'])
G.learn_file().unlink()
G.load_tpl(reload=True)

# ---- 卡片名字學整塊圖：別的名字已很像 → 不學 ----
a, b = FX['name'][0], FX['name'][1]
check('卡片名字已有樣板 → 再學同名不重複', G.learn_card_name(a['rows'], a['want'], save=False) is False)
check('卡片名字標成別人（跟既有樣板太像）→ 不學', G.learn_card_name(a['rows'], b['want'], save=False) is False)
check('數字片段不當名字學', G.learn_card_name(a['rows'], '65', save=False) is False)

# ---- parse_cards：一次 pixel 的顏色 → 每張卡（用二值點陣反推顏色）----
def cols_of(rows, kind):
    on = {'white': (255, 255, 255), 'green': (40, 240, 0)}[kind]
    return [on if c == '1' else (60, 30, 20) for r in rows for c in r]


w, n_ = FX['white'][0], FX['name'][0]
g1, g2 = FX['green'][0], FX['green'][1]
cols = cols_of(w['rows'], 'white') + cols_of(g1['rows'], 'green') + cols_of(n_['rows'], 'white') + cols_of(g2['rows'], 'green')
cs = G.parse_cards([0, 6], cols)
check('parse_cards 第 1 張：成長字串 + 等級', cs[0]['index'] == 1 and cs[0]['growth'] == w['want'] and cs[0]['level'] == g1['want'], cs[0])
check('parse_cards 第 7 張：名字 + 等級', cs[1]['index'] == 7 and cs[1]['name'] == n_['want'] and cs[1]['level'] == g2['want'])
idn = G.card_ident_text(cs[0])
check('card_ident_text → resolve_ident 格式', idn == {'name': None, 'via': 'card-glyph', 'raw': None, 'growth': w['want']})
check('card_points 點數 = 每張 104×25 + 104×28', len(G.card_points([0, 6])) == 2 * (104 * 25 + 104 * 28))

# ---- pet 接線：名字框成長字串不 OCR ----
import pet  # noqa: E402
import petwatch  # noqa: E402
pet.GLYPH_ON = True
calls = []
_ocr = petwatch.ocr
petwatch.ocr = lambda *a: calls.append(a) or []
ctx = {'tpl': {'name': {}, 'avatar': {}, 'digit': {}}, 'learn': False, 'use_icache': False}
s = FX['cream'][0]
r = pet.resolve_ident(s['rows'], ctx)
check('resolve_ident：字形讀出成長字串、零 OCR', r['growth'] == s['want'] and r.get('glyph') and not calls, r)
check('growth_known：字形讀得出 = 已知（read_slot 不等橫幅）', pet.growth_known(s['rows'], ctx))
r2 = pet.resolve_ident(s['rows'], ctx)
check('同一張點陣第二次走 gcache 仍標 glyph', r2['growth'] == s['want'] and r2.get('glyph'))
pet.GLYPH_ON = False
ctx2 = {'tpl': {'name': {}, 'avatar': {}, 'digit': {}}, 'learn': False, 'use_icache': False}
pet.resolve_ident(s['rows'], ctx2)
check('--no-glyph → 照舊 OCR', len(calls) >= 1)
check('--no-glyph → growth_known 不靠字形', not pet.growth_known(FX['cream'][1]['rows'], ctx2))
pet.GLYPH_ON = True
petwatch.ocr = _ocr

# ---- pet 接線：倉庫找卡先看「卡片字像目標」的那張（只決定順序；判定仍用選卡後名字框）----
cards = {0: {'index': 1, 'name': '朵拉比斯', 'growth': None, 'level': 1}, 3: {'index': 4, 'name': '摩娜西普', 'growth': None, 'level': 1},
         5: {'index': 6, 'name': '朵拉比斯', 'growth': None, 'level': 130}, 7: {'index': 8, 'name': None, 'growth': '46/9/8/2', 'level': 127}}
truth = {0: '朵拉比斯', 3: '摩娜西普', 5: '朵拉比斯', 7: None}
clicked = []
sv = (pet.glyph_cards, pet.click_card, pet.wait_for_card, pet.read_ident, pet.card_level_now, pet.species_reg)
pet.IMG_ON = False                    # 假倉庫沒有縮圖（2026-10-14 起找卡會比縮圖第二道確認；不能去截真遊戲畫面）
pet.glyph_cards = lambda d: cards
pet.click_card = lambda k, note: clicked.append(k) or True
pet.wait_for_card = lambda k, depot: ({}, True)
pet.read_ident = lambda ctx, *a: {'name': truth[clicked[-1]], 'via': 'tpl', 'raw': None,
                                  'growth': '46/9/8/2' if clicked[-1] == 7 else None}
pet.card_level_now = lambda k, extra=False: cards[k]['level']
pet.species_reg = lambda ctx: {'growth': {}}
d = {'sig': True, 'empty': [k not in cards for k in range(20)]}
info = {}
k, msg = pet._find_target_card(d, 'personal', {'name': '朵拉比斯', 'level': 130}, {'learn': False}, info, {})
check('take 找卡：卡片字 = 朵拉比斯 Lv130 的第 6 張先點、一次就中', k == 5 and clicked == [5], (k, clicked))
clicked.clear()
k, msg = pet._find_target_card(d, 'personal', {'growth': '46/9/8/2'}, {'learn': False}, info, {})
check('take 找卡：卡片字形讀到成長字串吻合 → 直接挑第 8 張、不逐張點（取前核對在 _take_in_depot）', k == 7 and clicked == [] and info.get('glyph_pick'), (k, clicked))
clicked.clear()
k, msg = pet._find_target_card(d, 'personal', {'growth': '46/9/8/2'}, {'learn': False}, {'glyph_retry': True}, {})
check('take 找卡：字形挑錯後的重找（glyph_retry）→ 照舊逐張，卡片字像目標的第 8 張先點', k == 7 and clicked == [7], (k, clicked))
clicked.clear()
cards[5]['name'] = '摩娜西普'                                 # 卡片字讀錯（假設）：照樣逐張選卡讀名字框，最後仍找得到
k, msg = pet._find_target_card(d, 'personal', {'name': '朵拉比斯', 'level': 130}, {'learn': False}, info, {})
check('卡片字讀錯也只影響順序：逐張看完仍找到真的那張', k == 5, (k, clicked))
pet.glyph_cards, pet.click_card, pet.wait_for_card, pet.read_ident, pet.card_level_now, pet.species_reg = sv

print('\n全部通過' if not fails else f'\n失敗 {fails}')
sys.exit(1 if fails else 0)
