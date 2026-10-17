#!/usr/bin/env python3
"""daily.py / dailyplan.py / shopkit.py 離線測試（假 Tools 模擬遊戲世界；0 次 powershell、不碰遊戲）。
用法：uv run --no-project python tools/gui/test_daily.py"""
import contextlib
import io
import os
import sys
from pathlib import Path

os.environ.setdefault('PSA_CLIENT', 'PrimalSA')
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import testenv  # noqa: E402,F401  紀錄檔 / 進度檔轉向暫存
import winenv  # noqa: E402
import uikit  # noqa: E402

PS_CALLS = []


def _no_ps(*a, **k):
    PS_CALLS.append(a)
    raise RuntimeError('離線測試不准呼叫 powershell')


winenv.run_ps = _no_ps
GUI_LOG = []


def fake_gui(*a, **k):
    GUI_LOG.append(a)
    return 'ok'


uikit.gui = fake_gui
uikit.snap = lambda *a, **k: None
import errlog  # noqa: E402
errlog.add = lambda *a, **k: 0
import dailyplan as dp  # noqa: E402
import shopkit  # noqa: E402
import daily  # noqa: E402
import screen_sigs  # noqa: E402

fails = 0


def check(name, cond, extra=''):
    global fails
    print(('PASS' if cond else 'FAIL'), name, extra if not cond else '')
    if not cond:
        fails += 1


def quiet(fn, *a, **k):
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
        rc = fn(*a, **k)
    return rc, buf.getvalue()


RECIPES = dp.load_recipes()
STORES, WHERE = dp.load_stores()
TODAY_ITEMS = [['厚肉塊串燒', '熱的魚味噌湯'], ['幹柿子', '合成爪 7'], ['烤焦的魚串燒', '合成爪 3'], ['葉子烤蕃薯', '大補飯團'], ['貝類飯', '特製2倍厚肉片']]

# ---------------- 知識庫 / 名稱 ----------------
check('load_recipes 去空白鍵 + 合成爪7 兩個材料', RECIPES['合成爪7'][0] == [('硬的殼', 1), ('猛獸的牙', 1)], str(RECIPES.get('合成爪7')))
check('load_stores 只收 1009 / 2009、共 11 間', len(STORES) == 11 and {s.map for s in STORES.values()} == {1009, 2009}, str(len(STORES)))
check('店員座標 / 商品順序（素材屋(貝、鱗) 2812 @27,28，第 1 項砂色的貝殼）', (STORES[2812].x, STORES[2812].y) == (27, 28) and STORES[2812].items[0] == '砂色的貝殼')
check('材料歸屬：硬的殼 → 素材屋(貝、鱗)；好吃的米 → 米店 2824', WHERE['硬的殼'] == 2812 and WHERE['好吃的米'] == 2824, f'{WHERE.get("硬的殼")} {WHERE.get("好吃的米")}')
check('norm 去空白', dp.norm(' 合成爪 7 ') == '合成爪7')
check('snap_item：完全相等（去空白）', dp.snap_item('合成爪 7', RECIPES) == '合成爪7')
check('snap_item：ocrfix 雙字部首（蛋氵十 → 蛋汁）先修正', dp.snap_item('蛋氵十', ['蛋汁', '蛋白']) == '蛋汁')
check('snap_item：掉一字仍吻合（厚肉塊串烤 → 厚肉塊串燒）', dp.snap_item('厚肉塊串烤', RECIPES) == '厚肉塊串燒')
check('snap_item：數字不同的同族不互認（合成爪 3 vs 7）', dp.snap_item('合成爪 3', ['合成爪7']) is None)
check('snap_item：歧義 / 讀不到 → None', dp.snap_item('', RECIPES) is None and dp.snap_item('xyz', RECIPES) is None and dp.snap_item(None, RECIPES) is None)
check('snap_item：兩個近似候選相差 < 0.05 → 歧義不猜', dp.snap_item('厚肉塊', ['厚肉塊串燒', '厚肉塊串烤']) is None)

# ---------------- 成品名 OCR：逐倍率投票（fixtures/daily_names_ocr.json = p1 2026-10-17 5 人 × 5 環 × 2 項真截圖的 OCR 原始行）----------------
import json  # noqa: E402
FX = json.loads((Path(__file__).resolve().parent / 'fixtures' / 'daily_names_ocr.json').read_text(encoding='utf-8'))
bad = [(c['role'], c['page'], c['item'], c['truth'], dp.vote_lines(c['lines'], RECIPES)) for c in FX['cases']]
bad = [b for b in bad if not (b[4]['name'] == dp.norm(b[3]) and b[4]['sure'])]
check(f'vote_lines：50 項真截圖 OCR 全部確定且正確（{len(FX["cases"])} 項）', len(FX['cases']) == 50 and not bad, str(bad[:3]))
old = [c for c in FX['cases'] if dp.snap_item(''.join(ln['text'] for ln in c['lines']), RECIPES) == dp.norm(c['truth'])]
check('舊讀法（各倍率 join 成一串再 snap）在同一批樣本大多失敗（重現 225 根因）', len(old) <= 5, str(len(old)))
L = lambda *ts: [{'text': t, 'x': 400, 'zoom': z} for z, t in enumerate(ts, 2)]  # noqa: E731
v = dp.vote_lines(L('合成弓箭8', '口成弓箭8'), RECIPES)
check('vote_lines：「合成弓箭8 / 口成弓箭8」兩倍率 → 合成弓箭8 確定（舊 join = 成弓箭8口成弓箭8 失敗）', v['name'] == '合成弓箭8' and v['sure'], str(v))
v = dp.vote_lines(L('合成弓箭8', '合成弓箭3'), RECIPES)
check('vote_lines：同族數字兩倍率不同（8 / 3）→ 衝突、None', v['name'] is None and v['conflict'], str(v))
v = dp.vote_lines(L('合成爪7', '合成爪', '爪7'), RECIPES)
check('vote_lines：數字尾碼只有 1 票 → 不確定（要開彈窗核對）', v['name'] == '合成爪7' and not v['sure'], str(v))
v = dp.vote_lines(L('葉子烤', '葉烤薯', '葉子烤蕃薯'), RECIPES)
check('vote_lines：無數字名 1 票即確定（葉子烤蕃薯，其他倍率掉字不投票）', v['name'] == '葉子烤蕃薯' and v['sure'], str(v))
check('vote_lines：壞字 / 空 / None → None', all(dp.vote_lines(x, RECIPES)['name'] is None for x in (L('？？？', 'xyz'), [], None, '')))
check('vote_lines：同倍率分兩行依 x 拼起來', dp.vote_lines([{'text': '弓箭8', 'x': 450, 'zoom': 3}, {'text': '合成', 'x': 400, 'zoom': 3}], RECIPES)['name'] == '合成弓箭8')
check('digit_family：合成爪 7 → 合成爪1～10；無數字 → 自己', len(dp.digit_family('合成爪 7', RECIPES)) == 10 and dp.digit_family('貝類飯', RECIPES) == ['貝類飯'])
P = FX['popup'][0]
check('彈窗真截圖（12-craft 貝類飯）：材料列讀出好吃的米 / 大的貝、resolve_name = 貝類飯', dp.snap_mats(P['mats'], RECIPES) == ['好吃的米', '大的貝']
      and dp.resolve_name(dp.vote_lines([], RECIPES), dp.vote_lines(P['name'], RECIPES), dp.snap_mats(P['mats'], RECIPES), RECIPES) == '貝類飯')
m7 = [n for n, _ in RECIPES['合成爪7'][0]]
m3 = [n for n, _ in RECIPES['合成爪3'][0]]
pv1 = dp.vote_lines(L('合成爪3'), RECIPES)                       # 面板 / 彈窗都讀成 3（單票）
check('resolve_name：大字讀成 3 但材料列是 7 的配方 → 合成爪7（材料列為準）', dp.resolve_name(pv1, pv1, dp.snap_mats(m7 + ['石幣'], RECIPES), RECIPES) == '合成爪7')
check('resolve_name：材料列是 3 的配方 → 合成爪3', dp.resolve_name(dp.vote_lines(L('合成爪7'), RECIPES), pv1, m3, RECIPES) == '合成爪3')
check('resolve_name：材料列讀不到、面板 7 彈窗 3 → None（不猜）', dp.resolve_name(dp.vote_lines(L('合成爪7'), RECIPES), pv1, [], RECIPES) is None)
check('resolve_name：材料列讀不到、大字只有 1 票數字 → None', dp.resolve_name(dp.vote_lines([], RECIPES), pv1, [], RECIPES) is None)
check('resolve_name：材料列讀不到、面板與彈窗同為 7 → 合成爪7', dp.resolve_name(dp.vote_lines(L('合成爪7'), RECIPES), dp.vote_lines(L('合成爪7'), RECIPES), [], RECIPES) == '合成爪7')
check('resolve_name：什麼都讀不到 → None', dp.resolve_name(dp.vote_lines([], RECIPES), dp.vote_lines([], RECIPES), [], RECIPES) is None)
check('resolve_name：材料列和所有候選矛盾 → None', dp.resolve_name(pv1, pv1, ['好吃的米', '大的貝'], RECIPES) is None)
check('pop_is：材料列吻合 7 → 是合成爪7、不是合成爪3', dp.pop_is('合成爪 7', {'name': L('合成爪3'), 'mats': m7}, RECIPES)
      and not dp.pop_is('合成爪 3', {'name': L('合成爪3', '合成爪3'), 'mats': m7}, RECIPES))
check('pop_is：沒材料列 → 大字 2 倍率同意才算', dp.pop_is('合成爪 7', {'name': L('合成爪7', '合成爪7'), 'mats': []}, RECIPES)
      and not dp.pop_is('合成爪 7', {'name': L('合成爪7'), 'mats': []}, RECIPES)
      and not dp.pop_is('合成爪 7', {'name': L('合成爪7', '合成爪1'), 'mats': []}, RECIPES))
check('pop_is：真截圖貝類飯 → True；當成大補飯團 → False', dp.pop_is('貝類飯', P, RECIPES) and not dp.pop_is('大補飯團', P, RECIPES))

# ---------------- 純函式：畫面讀值 ----------------
check('count_state 紅 / 綠 / 其他', dp.count_state((255, 0, 0)) == 'red' and dp.count_state((135, 255, 91)) == 'green' and dp.count_state((90, 62, 41)) == '?' and dp.count_state(None) == '?')
check('popup_short：任一紅 → 不足', dp.popup_short([(255, 0, 0), (255, 255, 255)]) and not dp.popup_short([(135, 255, 91), (255, 255, 255)]) and not dp.popup_short(None))
check('parse_reward / parse_page', dp.parse_reward('完成所有任務額外獎勵 0/5') == 0 and dp.parse_reward('3 / 5 3/5') == 3 and dp.parse_reward('abc') is None
      and dp.parse_page('1/5') == 1 and dp.parse_page('5 / 5') == 5 and dp.parse_page('') is None)

# ---------------- 計畫（fixture：今天 DKBO 10 項，plan §4.3-5）----------------
P = dp.plan_role(TODAY_ITEMS, RECIPES, WHERE, STORES)
check('fixture：5 環都支援', P['supported_rings'] == [1, 2, 3, 4, 5])
check('fixture：薩村 4 格（猛獸的牙 / 折斷的牙 / 硬的殼 / 有裂痕的殼 各 1）', P['buy']['sam'] == {'猛獸的牙': 1, '折斷的牙': 1, '硬的殼': 1, '有裂痕的殼': 1}, str(P['buy']['sam']))
check('fixture：漁村 24 格、28 個', len(P['buy']['fish']) == 24 and sum(P['buy']['fish'].values()) == 28, f'{len(P["buy"]["fish"])} {sum(P["buy"]["fish"].values())}')
check('fixture：石幣 材料 16,000 + 合成 10,000 = 26,000', P['cost'] == {'mat': 16000, 'craft': 10000, 'total': 26000}, str(P['cost']))
check('fixture：沒有胡椒', P['pepper'] == {})
R_SAM = dp.store_route('sam', P['buy']['sam'], WHERE, STORES, P['first_use'])
R_FISH = dp.store_route('fish', P['buy']['fish'], WHERE, STORES, P['first_use'])
check('store_route：薩村 2 間、漁村 7 間；店員 y 由小到大', len(R_SAM) == 2 and len(R_FISH) == 7 and [s.y for s, _ in R_FISH] == sorted(s.y for s, _ in R_FISH)
      and [s.y for s, _ in R_SAM] == [17, 28], str([(s.name, s.y) for s, _ in R_FISH]))
check('store_route：店內早環材料先買（米店：好吃的米(貝類飯 第5環) 排在 銳利的串(第1環) 之後）',
      [n for n, _ in dict((s.npc, v) for s, v in R_FISH)[2824]].index('銳利的串') < [n for n, _ in dict((s.npc, v) for s, v in R_FISH)[2824]].index('好吃的米'))
check('remaining_buy：扣掉已買', dp.remaining_buy(P, 'sam', {'硬的殼': 1, '猛獸的牙': 1}) == {'折斷的牙': 1, '有裂痕的殼': 1})
lines = dp.plan_lines('DKBO', P, STORES, WHERE)
check('plan_lines 有薩姆吉爾 / 瑪麗娜絲 / 26,000', any('26,000' in ln for ln in lines) and any('瑪麗娜絲 2009：24 種' in ln for ln in lines))

# 不支援環：配方材料是合成品（不在任何店）→ 整環跳過、其他照算；done（已 1/1 綠）不算進購買
FR = {'甲': [[('石頭', 1)]], '乙': [[('合成品X', 1)]], '丙': [[('石頭', 2)]], '丁': [[('石頭', 1)]]}
FW = {'石頭': 2810}
FS = {2810: dp.Store('素材屋', 2810, 1009, 27, 17, ['石頭'])}
P2 = dp.plan_role([['甲', '乙'], ['丙', '丁'], [None, '甲'], ['甲', '甲'], ['甲', '甲']], FR, FW, FS, done=[[False, False], [True, False], [False, False], [False, False], [False, False]])
check('不支援：第 1 環（乙是合成品）跳過、第 3 環（沒讀到名稱）跳過', not P2['rings'][0]['supported'] and not P2['rings'][2]['supported'] and P2['supported_rings'] == [2, 4, 5], str(P2['supported_rings']))
check('不支援：跳過的環不買；已完成的項（丙）不買', P2['buy']['sam'] == {'石頭': 1 + 2 + 2}, str(P2['buy']))
check('不支援原因寫得出來', '合成品X' in (P2['rings'][0]['reason'] or '') and '沒讀到名稱' in (P2['rings'][2]['reason'] or ''))
P3 = dp.plan_role([['甲', '甲']] * 5, {'甲': [[('黑胡椒', 1), ('石頭', 1)]]}, FW, FS)
check('胡椒：不買（不在 buy）、列在 pepper、環仍支援', P3['pepper'] == {'黑胡椒': 10} and P3['buy']['sam'] == {'石頭': 10} and len(P3['supported_rings']) == 5, str(P3))

# ---------------- 背包 / 倉庫模型 ----------------
led = dp.Ledger()
for i in range(13):
    led.buy(f'材{i:02d}', 1)
rings_all = [{'crafted': [False, False], 'submitted': False} for _ in range(5)]
FP = dp.plan_role([['甲', '甲']] * 5, {'甲': [[('石頭', 1)]]}, FW, FS)
check('Ledger.kinds / buy / evict / take', led.kinds() == 13 and led.evict('材00', 'personal') == 1 and led.kinds() == 12 and led.take('材00', 'personal') == 1 and led.kinds() == 13)
check('make_room：13 種 + 新 2 種 > 13 → 要存 2 種（最晚才用到 / 沒用到的先）', dp.make_room(led, FP, rings_all, ['新1', '新2']) is not None and len(dp.make_room(led, FP, rings_all, ['新1', '新2'])) == 2)
check('make_room：incoming 已在背包的不增格', dp.make_room(led, FP, rings_all, ['材01']) == [])
check('make_room：不存成品 / protect / 胡椒（只剩這些 → None）', dp.make_room(dp.Ledger({'bag': {dp.PRODUCT_PREFIX + 'X': 1, '黑胡椒': 1, '石頭': 1}}), FP, rings_all, ['a'], cap=3, protect={'石頭'}) is None
      and dp.make_room(dp.Ledger({'bag': {dp.PRODUCT_PREFIX + 'X': 1, '黑胡椒': 1, '石頭': 1}}), FP, rings_all, ['a'], cap=3) == ['石頭'])
# choose_evict：最晚環才用到的先存
PE = dp.plan_role([['甲', '丙'], ['乙', '乙'], ['乙', '乙'], ['乙', '乙'], ['乙', '乙']],
                  {'甲': [[('A', 1)]], '丙': [[('B', 1)]], '乙': [[('C', 1)]]}, {'A': 2810, 'B': 2810, 'C': 2810}, FS)
LL = dp.Ledger({'bag': {'A': 1, 'B': 1, 'C': 1}})
check('choose_evict：最晚環才用的 C（第 2 環起）先存；A / B（第 1 環）後存', dp.choose_evict(LL, PE, rings_all) == 'C' and dp.choose_evict(LL, PE, rings_all, protect={'C'}) == 'B')
check('Ledger.craft：扣材料加成品、材料不夠 → False 不動、胡椒不扣', (lambda l: (l.craft([('A', 1), ('黑胡椒', 1)], '甲'), l.bag.get('A'), l.bag.get(dp.PRODUCT_PREFIX + '甲'))[1:])(dp.Ledger({'bag': {'A': 1}})) == (None, 1)
      and not dp.Ledger({'bag': {'A': 1}}).craft([('A', 2)], '甲'))
check('craftable：mid 只算背包且胡椒不行；final 背包 + 倉庫 + 胡椒', dp.craftable({'mats': [('A', 1)]}, dp.Ledger({'bag': {'A': 1}}), True) and not dp.craftable({'mats': [('A', 1)]}, dp.Ledger({'personal': {'A': 1}}), True)
      and dp.craftable({'mats': [('A', 1)]}, dp.Ledger({'personal': {'A': 1}}), False) and not dp.craftable({'mats': [('黑胡椒', 1)]}, dp.Ledger(), True) and dp.craftable({'mats': [('黑胡椒', 1)]}, dp.Ledger(), False))

# ---------------- 進度檔 ----------------
st = dp.new_role_state('DKBO', '2026-10-17')
st['bought']['硬的殼'] = 1
dp.save(dp.role_path('DKBO'), st)
check('進度檔 round trip（原子寫入、無 .tmp 殘留）', dp.load(dp.role_path('DKBO'))['bought'] == {'硬的殼': 1} and not list(dp.role_path('DKBO').parent.glob('*.tmp')))
check('check_date / stale：同日 True、跨日 False、沒檔案 True', dp.check_date(st, '2026-10-17') and not dp.check_date(st, '2026-10-18') and dp.check_date(None, '2026-10-18'))
check('load_role：沒檔案 → 新的；fresh → 新的', dp.load_role('DKBO2')['read'] is False and dp.load_role('DKBO', '2026-10-17', fresh=True)['bought'] == {})
check('每視窗各自一份（主視窗 daily-<角色>.json）', dp.role_path('DKBO').name == 'daily-DKBO.json' and dp.team_path().name == 'daily-team.json')
check('退出碼 220～229 不重複、名稱齊', sorted(dp.EXIT_NAMES) == list(range(220, 230)))

# ---------------- shopkit 純函式 / 面板特徵 ----------------
check('shopkit.parse_coin / coin_delta_ok 與 buywendy 同一份', shopkit.parse_coin('150,000') == 150000 and shopkit.coin_delta_ok(150000, 149500) is True)
check('title_match：容錯 / 數字不同不算 / 空', shopkit.title_match('硬的 殼', '硬的殼') and shopkit.title_match('猛獸的牙齒說明', '猛獸的牙') and not shopkit.title_match('合成爪 3', '合成爪 7') and not shopkit.title_match('', '硬的殼'))
check('visible_candidates：第 0 次拖、第 3 項（row 1）→ [1, 2, 0, 3]；視野外 → []', shopkit.visible_candidates(3, 0) == [1, 2, 0, 3] and shopkit.visible_candidates(40, 0) == [] and shopkit.visible_candidates(13, 0) == [])
check('visible_candidates：拖 3 次後第 14 項（row 7）預測視野第 1 列', shopkit.visible_candidates(14, 3)[0] == 1)
check('qty_digit_xy：12 → 1、2 鍵；0 → 0 鍵；超範圍 ValueError', shopkit.qty_digit_xy(12) == [shopkit.KEYPAD['1'], shopkit.KEYPAD['2']] and shopkit.qty_digit_xy(0) == [shopkit.KEYPAD['0']])
try:
    shopkit.qty_digit_xy(1000)
    check('qty_digit_xy(1000) 要丟 ValueError', False)
except ValueError:
    check('qty_digit_xy(1000) 要丟 ValueError', True)
check('parse_qty', shopkit.parse_qty('0') == 0 and shopkit.parse_qty('x') is None and shopkit.parse_qty('12') == 12)

# select_item：假讀標題 → 預測列先點、不對再試鄰近、視野外先拖
ORDER = [f'商品{i:02d}' for i in range(20)]


def run_select(want, truth_first_row_of_drag=lambda d: d * 2):
    GUI_LOG.clear()
    state = {'drags': 0}
    clicked = []

    def reader():
        # 最後一次 click 的卡片 → 顯示的商品：由「已拖次數」推視野第一列
        last = [a for a in GUI_LOG if a and a[0] == 'seq' and a[1].startswith('click')]
        x, y = [int(v) for v in last[-1][1].split(';')[0].split()[1:3]]
        col = 0 if x < 540 else 1
        row_pos = round((y - shopkit.ROW_Y0) / shopkit.ROW_PITCH)
        idx = (truth_first_row_of_drag(state['drags']) + row_pos) * 2 + col
        clicked.append(idx)
        return ORDER[idx] if idx < len(ORDER) else ''
    ok = shopkit.select_item(want, ORDER, state, reader=reader)
    return ok, state['drags'], clicked


ok, drags, clicked = run_select('商品03')
check('select_item：第 3 項不用捲、點一下就對', ok and drags == 0 and clicked == [3], f'{ok} {drags} {clicked}')
ok, drags, clicked = run_select('商品13')
check('select_item：第 13 項（row 6）拖 1 次後預測列（視野第 4 列）一點就中', ok and drags == 1 and clicked == [13], f'{ok} {drags} {clicked}')
ok, drags, clicked = run_select('商品17')
check('select_item：第 17 項（row 8）拖 2 次、預測列命中', ok and drags == 2 and clicked == [17], f'{ok} {drags} {clicked}')
ok, drags, clicked = run_select('商品19', truth_first_row_of_drag=lambda d: min(d * 2, 5))     # 到底夾住：實際視野第一列最多 5
check('select_item：到底夾住（實際偏移比預測小）→ 鄰近列也試、仍命中', ok, f'{ok} {drags} {clicked}')
check('select_item：不在清單 → False', not shopkit.select_item('沒這個', ORDER, {'drags': 0}, reader=lambda: ''))

# 面板特徵（單張探路樣本）：有 tools/.cache/daily-probe 的 PNG 才驗（主工作樹才有；worktree 沒有就略過）
try:
    import pngread
    probe = None
    for base in (HERE.parents[1] / 'tools' / '.cache' / 'daily-probe', Path('/mnt/c/games/PrimalSA-AI/tools/.cache/daily-probe'), Path('C:/games/PrimalSA-AI/tools/.cache/daily-probe')):
        if (base / '07-npc.png').exists():
            probe = base
            break
    if probe:
        def sig_ok(png, sig):
            w, h, bpp, rows = pngread.decode((probe / png).read_bytes())
            px = pngread.pixels(rows, bpp, [(x, y) for x, y, *_ in sig])
            return all(screen_sigs.close(px[(x, y)], (r, g, b), t) for x, y, r, g, b, t in sig)
        check('DAILY_SIG 命中探路截圖 07（委託面板）', sig_ok('07-npc.png', screen_sigs.DAILY_SIG))
        check('QCRAFT_SIG 命中探路截圖 12（快速合成彈窗）', sig_ok('12-craft.png', screen_sigs.QCRAFT_SIG))
        check('DAILY_SIG 不命中主畫面 / 便利店截圖（14 / 17）', not sig_ok('14-closed.png', screen_sigs.DAILY_SIG) and not sig_ok('17-shop.png', screen_sigs.DAILY_SIG)
              and not sig_ok('14-closed.png', screen_sigs.QCRAFT_SIG))
    else:
        print('SKIP 探路截圖不在（worktree）：DAILY_SIG / QCRAFT_SIG 取色比對略過')
except ImportError:
    print('SKIP pngread 不在')
check('uikit.DAILY / QCRAFT 規格：✕ 座標、提交 / 彈窗合成列禁區', uikit.DAILY.close_xy == (1193, 98) and 'submit' in uikit.DAILY.forbidden and 'craft' in uikit.QCRAFT.forbidden)
try:
    uikit.check_forbidden(uikit.DAILY, 1015, 685)
    check('safe_click 預設擋提交委託', False)
except uikit.ForbiddenClick:
    check('safe_click 預設擋提交委託', True)
uikit.check_forbidden(uikit.DAILY, 1015, 685, allow=('submit',))
check('allow=("submit",) 放行', True)


# ======================================================================================
# 假遊戲世界：FakeTools
# ======================================================================================
class World:
    """每人：bag{名稱: 量}（種類數 + 成品 ≤ bag_cap）、personal{}（種類 ≤ personal_cap）；公倉全隊共用 {名稱: 量}（≤ public_cap 種）。
    委託面板：每人 5 環 × 2 項（items_by_role）、n/5 計數、每項 crafted（綠）。"""

    def __init__(self, items_by_role, roles, bag_cap=15, personal_cap=40, public_cap=40, public_init=None, junk=0):
        self.roles = list(roles)
        self.items = items_by_role
        self.bag = {r: {f'雜物{i}': 1 for i in range(junk)} for r in roles}
        self.personal = {r: {} for r in roles}
        self.public = dict(public_init or {})
        self.bag_cap, self.personal_cap, self.public_cap = bag_cap, personal_cap, public_cap
        self.green = {r: [[False, False] for _ in range(5)] for r in roles}
        self.reward = {r: 0 for r in roles}
        self.submitted = {r: [False] * 5 for r in roles}
        self.cur = roles[0]
        self.map = 1000
        self.team = True
        self.panel = False
        self.page = 1
        self.shop = None
        self.shop_item = None
        self.qty = 0
        self.log = []                              # 動作序列（測試用）
        self.spent = 0                             # 石幣花費估算（買 500 / 合成 1000）
        self.bought_n = 0
        self.crafted_n = 0
        self.inj = {}                              # 失敗注入
        self.recipes = RECIPES                     # 假合成用的配方（情境可換）


class FakeTools:
    def __init__(self, W: World):
        self.W = W
        self.locked = False
        self.grind_called = 0
        self.cleanups = 0

    # -- 輔助 --
    def L(self, *a):
        self.W.log.append(a)

    def kinds(self, role):
        return len([1 for v in self.W.bag[role].values() if v > 0])

    # -- 一般 --
    def preflight(self): return 0
    def sleep(self, s): pass

    def lock(self):
        self.locked = True
        return True

    def unlock(self): self.locked = False
    def stop_follow(self): return True
    def encounter_off(self): pass
    def pos(self): return (self.W.map, 0, 0)
    def wait_map(self, m, tries=10): return self.W.map == m

    def to_town(self):
        self.L('to_town')
        self.W.map = 1000
        return True

    def to_marinas(self):
        self.L('to_marinas')
        self.W.map = 2000
        return True

    def ensure(self, role):
        self.W.cur = role
        return 0

    def switch(self, role):
        assert not self.W.panel and not self.W.shop, '切角色時面板 / 商店還開著'
        self.W.cur = role
        self.L('switch', role)
        return self.inj.get('switch_rc', 0) if self.inj.get('switch_role') == role else 0

    @property
    def inj(self): return self.W.inj

    def form(self):
        self.L('form')
        self.W.team = True
        return 0

    def disband(self):
        self.L('disband')
        assert self.W.cur == self.W.roles[0], '解散時當前角色不是隊長'
        self.W.team = False
        return 0

    def walk_to(self, m, x, y, exit_map=None):
        assert self.W.team or self.W.cur, ''
        self.L('walk_to', m, x, y)
        self.W.map = exit_map if exit_map else m
        return True

    def into_hospital(self):
        self.L('into_hospital')
        self.W.map = 1005
        return True

    def talk(self, npc, at, then=''): return True

    # -- 委託面板 --
    def daily_open(self):
        assert self.W.map == 1005 and not self.W.team, '開委託面板：不在醫院或還組著隊'
        if self.inj.get('panel_fail'):
            return False
        self.W.panel = True
        self.W.page = 1
        return True

    def daily_close(self):
        self.W.panel = False

    def panel_open(self): return self.W.panel

    def page_no(self):
        assert self.W.panel
        return self.W.page

    def goto_page(self, p):
        assert self.W.panel
        self.W.page = p
        return True

    def next_page(self):
        assert self.W.panel
        self.W.page += 1
        return True

    def read_page(self):
        assert self.W.panel
        r, pg = self.W.cur, self.W.page - 1
        names = [[{'text': n, 'x': 400, 'zoom': z} for z in (2, 3)] for n in self.W.items[r][pg]]   # 兩倍率都讀對
        if self.inj.get('noise') == (r, pg):
            names[1] = [{'text': '？？？', 'x': 400, 'zoom': 2}]          # 名稱 OCR 壞掉 → 要走 peek
        return {'names': names, 'states': ['green' if g else 'red' for g in self.W.green[r][pg]]}

    def peek_item(self, k):
        self.L('peek', self.W.cur, self.W.page, k)
        if self.inj.get('peek_fail'):
            return {'name': [], 'mats': []}
        nm = self.W.items[self.W.cur][self.W.page - 1][k]
        return {'name': [{'text': nm, 'x': 480, 'zoom': z} for z in (2, 3)], 'mats': []}

    def reward_count(self):
        assert self.W.panel
        return None if self.inj.get('reward_none') else self.W.reward[self.W.cur]

    def craft_item(self, k, name):
        W = self.W
        assert W.panel and W.map == 1005
        r, pg = W.cur, W.page - 1
        assert dp.norm(W.items[r][pg][k]) == dp.norm(name), f'合成的不是這頁第 {k + 1} 項：{name}'
        if self.inj.get('craft_fail') == (r, name):
            return False, '假：材料不足'
        mats = W.recipes[dp.norm(name)][0]
        bag = W.bag[r]
        for n, q in mats:
            if n in dp.PEPPERS:
                if bag.get(n, 0) <= 0:
                    return False, f'假：背包沒有胡椒 {n}'
            elif bag.get(n, 0) < q:
                return False, f'假：背包沒有 {n}'
        for n, q in mats:
            if n not in dp.PEPPERS:
                bag[n] -= q
                if bag[n] <= 0:
                    del bag[n]
        bag['成品:' + dp.norm(name)] = bag.get('成品:' + dp.norm(name), 0) + 1
        W.green[r][pg][k] = True
        W.crafted_n += 1
        W.spent += 1000
        self.L('craft', r, name)
        return True, ''

    def item_states(self):
        r, pg = self.W.cur, self.W.page - 1
        return ['green' if g else 'red' for g in self.W.green[r][pg]]

    def submit(self):
        W = self.W
        r, pg = W.cur, W.page - 1
        assert W.panel and all(W.green[r][pg]), '兩項沒全綠就提交'
        if self.inj.get('submit_noop') == r:
            return True
        W.reward[r] += 1
        W.submitted[r][pg] = True
        for k in range(2):
            key = '成品:' + dp.norm(W.items[r][pg][k])
            W.bag[r][key] -= 1
            if W.bag[r][key] <= 0:
                del W.bag[r][key]
        W.green[r][pg] = [False, False]                       # 提交後該環重置顯示
        self.L('submit', r, W.page)
        return True

    # -- 便利店 --
    def shop_enter(self, store):
        W = self.W
        assert W.map == store.map and not W.team and not W.panel, f'進店：地圖 {W.map}、隊伍 {W.team}'
        if self.inj.get('boom_enter') == (W.cur, store.npc):
            self.inj.pop('boom_enter')
            raise RuntimeError('假：進店時世界爆炸（模擬腳本被砍）')
        W.shop, W.shop_item, W.qty = store, None, 0
        self.L('shop_enter', W.cur, store.npc)
        return True

    def shop_select(self, name, store, state):
        assert self.W.shop is store and name in store.items, f'{name} 不在 {store.name}'
        self.W.shop_item = name
        return True

    def shop_set_qty(self, q):
        self.W.qty = q
        return True

    def shop_buy(self):
        W = self.W
        r = W.cur
        assert W.shop and W.shop_item
        if self.inj.get('buy_fail_once') == (r, W.shop_item):
            self.inj.pop('buy_fail_once')
            self.L('buy_denied', r, W.shop_item)
            return                                             # 沒買到：數量框不歸 0
        new = W.shop_item not in W.bag[r]
        if new and self.kinds(r) >= W.bag_cap:
            self.L('buy_full', r, W.shop_item)
            return                                             # 背包滿：買不進，數量框不歸 0
        W.bag[r][W.shop_item] = W.bag[r].get(W.shop_item, 0) + W.qty
        W.spent += 500 * W.qty
        W.bought_n += W.qty
        self.L('buy', r, W.shop_item, W.qty)
        W.qty = 0
        if self.inj.get('buy_boom') == (r, W.shop_item):
            raise RuntimeError('假：買完後世界爆炸（模擬腳本被砍）')

    def shop_qty(self): return self.W.qty

    def shop_close(self):
        self.W.shop = None
        return True

    # -- 背包 / 倉庫 --
    def bag_check(self, role, names):
        assert not self.W.shop and not self.W.panel, '核對背包時商店 / 面板還開著'
        miss = [n for n in names if self.W.bag[role].get(n, 0) <= 0]
        return miss, 0

    def depot_store(self, role, name, sub):
        W = self.W
        assert not W.shop and not W.panel, f'存倉時商店 / 面板還開著（{name}）'
        if W.bag[role].get(name, 0) <= 0:
            return 92
        if sub == 'personal':
            if self.inj.get('personal_full') or len(W.personal[role]) >= W.personal_cap:
                return 95
            W.personal[role][name] = W.personal[role].get(name, 0) + W.bag[role].pop(name)
        else:
            if len(W.public) >= W.public_cap and name not in W.public:
                return 95
            W.public[name] = W.public.get(name, 0) + W.bag[role].pop(name)
        self.L('store', role, name, sub)
        return 0

    def depot_take(self, role, name, sub):
        W = self.W
        assert not W.shop and not W.panel, f'取倉時商店 / 面板還開著（{name}）'
        src = W.personal[role] if sub == 'personal' else W.public
        if src.get(name, 0) <= 0:
            return 92
        if name not in W.bag[role] and self.kinds(role) >= W.bag_cap:
            return 94
        W.bag[role][name] = W.bag[role].get(name, 0) + src.pop(name)
        self.L('take', role, name, sub)
        return 0

    def cleanup(self):
        self.cleanups += 1
        self.W.panel = False
        self.W.shop = None

    def grind_go(self):
        self.grind_called += 1
        return 0


ROLES5 = ['DKBO', 'DKBO2', 'DKBO3', 'DKBO4', 'DKBO5']


def fresh_dir():
    """每個情境換一個乾淨的進度檔資料夾（testenv 的暫存根）"""
    import shutil
    d = Path(os.environ['PSA_LOG_DIR'])
    for p in d.glob('state/daily-*.json'):
        p.unlink()
    for p in d.glob('daily-*.json'):
        p.unlink()
    shutil.rmtree(d / 'state', ignore_errors=True)


def scenario(items=None, roles=None, **world_kw):
    roles = roles or ROLES5
    it = items or {r: [list(p) for p in TODAY_ITEMS] for r in roles}
    return World(it, roles, **world_kw)


def go(W, T=None, **kw):
    T = T or FakeTools(W)
    daily.ROLES[:] = W.roles
    daily.LEADER = W.roles[0]
    kw.setdefault('confirm_buy', True)
    rc, out = quiet(daily.run, roles=W.roles, tools=T, recipes=RECIPES, stores=STORES, where=WHERE, **kw)
    return rc, out, T


# ---------------- 情境 1：標準全流程 ----------------
fresh_dir()
W = scenario()
rc, out, T = go(W)
check('全流程 rc 0', rc == 0, f'{rc} {out[-600:]}')
check('5 人都 5/5（提交 25 環）', all(W.reward[r] == 5 for r in W.roles) and sum(W.reward.values()) == 25, str(W.reward))
check('每人買 32 個（薩村 4 + 漁村 28）、合成 10 項：全隊 160 個 / 50 項', W.bought_n == 160 and W.crafted_n == 50, f'{W.bought_n} {W.crafted_n}')
check('石幣花費 = 160×500 + 50×1000 = 130,000（5 人 26,000，與 plan §5 估算一致）', W.spent == 130000, str(W.spent))
check('背包沒有剩成品（都提交了）', all(not any(k.startswith('成品:') for k in W.bag[r]) for r in W.roles))
check('去練功 + 解鎖（finish）', T.grind_called == 1 and not T.locked)
check('開了 mid 的合成（薩村料：合成爪 7 / 3 先做）', any(a[0] == 'craft' and a[2] in ('合成爪7', '合成爪3') for a in W.log))
seq = [a[0] for a in W.log]
check('動作順序：薩村買 → mid 合成 → 漁村買 → final 合成', seq.index('buy') < seq.index('craft') < [i for i, a in enumerate(W.log) if a[0] == 'to_marinas'][0] < max(i for i, a in enumerate(W.log) if a[0] == 'buy') < max(i for i, a in enumerate(W.log) if a[0] == 'submit'))
check('漁村每人 24 種 > 13 → 一定用到個人倉庫（有 store personal）、final 有 take 取回', any(a[0] == 'store' and a[3] == 'personal' for a in W.log) and any(a[0] == 'take' and a[3] == 'personal' for a in W.log))
check('背包種類全程沒超過 15（假世界買不進會留 buy_full，不應該出現）', not any(a[0] == 'buy_full' for a in W.log), str([a for a in W.log if a[0] == 'buy_full'][:3]))
tm = dp.load(dp.team_path())
check('全隊進度檔：complete、stage finish', tm and tm['complete'] and tm['stage'] == 'finish' and set(tm['done']) == set(dp.STAGES))
check('每人進度：5 環都 submitted、bought 不空', all(all(x['submitted'] for x in dp.load(dp.role_path(r))['rings']) and dp.load(dp.role_path(r))['bought'] for r in W.roles))
check('順序固定：read 時 DKBO2 → DKBO3 → DKBO4 → DKBO5 → DKBO', [a[1] for a in W.log if a[0] == 'switch'][:5] == ['DKBO2', 'DKBO3', 'DKBO4', 'DKBO5', 'DKBO'])
check('0 次 powershell', not PS_CALLS)
rc2, out2, _ = go(scenario())
check('同一天跑完又跑 → 220「已完成過一輪」', rc2 == 220 and daily.LAST.get('all_done'), f'{rc2} {out2[-200:]}')

# ---------------- 情境 2：沒給 --confirm-buy → 221、已印計畫；讀進度寫好 ----------------
fresh_dir()
W = scenario()
rc, out, T = go(W, confirm_buy=False)
check('沒 --confirm-buy：讀完清單印計畫就停 221（沒買沒合成）', rc == 221 and W.bought_n == 0 and W.crafted_n == 0 and '26,000' in out, f'{rc} {out[-300:]}')
check('221：5 人清單都寫進進度檔（read=True）', all(dp.load(dp.role_path(r))['read'] for r in W.roles))
rc, out, T = go(W)                                                    # 接著給旗標：從 plan 續跑，不重讀（switch 次數少）
n_read_switch = len([a for a in W.log if a[0] == 'switch'])
check('給旗標續跑（從進度檔 plan 段開始）→ 完成', rc == 0 and all(W.reward[r] == 5 for r in W.roles), f'{rc} {out[-300:]}')

# ---------------- 情境 3：買到一半被砍 → 續跑 bought 防重買 ----------------
fresh_dir()
W = scenario()
W.inj['boom_enter'] = ('DKBO3', 2823)                                      # DKBO3 進水果店（魚店 / 蔬菜店已買完記帳）時被砍
T = FakeTools(W)
try:
    go(W, T)
    boom = False
except RuntimeError:
    boom = True
check('DKBO3 進水果店時世界爆炸（模擬腳本被砍）→ 例外往上丟 + cleanup 關面板', boom and T.cleanups >= 1)
bought_before = W.bought_n
rc, out, _ = go(W, T)
check('續跑完成 rc 0', rc == 0 and all(W.reward[r] == 5 for r in W.roles), f'{rc} {out[-300:]}')
check('bought 防重買：全隊總購買數量仍是 160（前面店已記帳的沒再買一次）', W.bought_n == 160, str(W.bought_n))

# ---------------- 情境 4：背包比模型小（有雜物）→ 買不進 → 存倉再試一次 ----------------
fresh_dir()
W = scenario(junk=3)
rc, out, T = go(W)
check('背包有 3 格雜物（模型以為 13 種）：買不進 → 反應式存倉 + 重試 → 仍完成 rc 0', rc == 0 and all(W.reward[r] == 5 for r in W.roles), f'{rc} {out[-400:]}')
check('有出現過 buy_full（真的撞到背包滿）', any(a[0] == 'buy_full' for a in W.log))

# ---------------- 情境 5：個人倉庫滿 → 改存公倉（in_public）、final 同一人取回 ----------------
fresh_dir()
items1 = {'DKBO': [list(p) for p in TODAY_ITEMS]}
W = scenario(items=items1, roles=['DKBO'])
W.inj['personal_full'] = True
rc, out, T = go(W)
check('個人倉庫滿 → 改存公共倉庫並完成', rc == 0 and W.reward['DKBO'] == 5, f'{rc} {out[-400:]}')
check('有 store public 與 take public（同一人存、同一人取）', any(a[0] == 'store' and a[3] == 'public' for a in W.log) and any(a[0] == 'take' and a[3] == 'public' for a in W.log))
check('final 取回後 in_public 清空', dp.load(dp.role_path('DKBO'))['in_public'] == [])
fresh_dir()
W = scenario(items=items1, roles=['DKBO'], public_cap=0)
W.inj['personal_full'] = True
rc, out, T = go(W)
check('個人倉庫和公倉都滿 → 228', rc == 228, f'{rc} {out[-300:]}')

# ---------------- 情境 6：不支援的環跳過、其他照做、rc 0 ----------------
fresh_dir()
it6 = {'DKBO': [list(p) for p in TODAY_ITEMS]}
rec6 = dict(RECIPES)
rec6['葉子烤蕃薯'] = [[('合成品X', 1)]]                                 # 第 4 環不支援
W = scenario(items=it6, roles=['DKBO'])
quiet_rc = None
T = FakeTools(W)
daily.ROLES[:] = ['DKBO']
daily.LEADER = 'DKBO'
rc, out = quiet(daily.run, roles=['DKBO'], confirm_buy=True, tools=T, recipes=rec6, stores=STORES, where=WHERE)
check('第 4 環不支援 → 跳過、其他 4 環做完、rc 0', rc == 0 and W.reward['DKBO'] == 4 and not W.submitted['DKBO'][3], f'{rc} {W.reward} {out[-300:]}')
check('跳過記在事件（第 4 環跳過）', '第 4 環跳過' in out)
fresh_dir()
W = scenario(items=it6, roles=['DKBO'])
rec_none = {k: [[('合成品X', 1)]] for k in RECIPES}
rc, out = quiet(daily.run, roles=['DKBO'], confirm_buy=True, tools=FakeTools(W), recipes=rec_none, stores=STORES, where=WHERE)
check('全部環都不支援 → 226（不動作）', rc == 226 and W.bought_n == 0, f'{rc} {out[-200:]}')

# ---------------- 情境 7：胡椒 ----------------
fresh_dir()
rec7 = dict(RECIPES)
rec7['貝類飯'] = [[('黑胡椒', 1), ('好吃的米', 1)]]
W = scenario(items=it6, roles=['DKBO'], public_init={'黑胡椒': 5})
W.recipes = rec7
T = FakeTools(W)
rc, out = quiet(daily.run, roles=['DKBO'], confirm_buy=True, tools=T, recipes=rec7, stores=STORES, where=WHERE)
check('胡椒：公倉取用 → 合成 → 用剩存回；5 環完成', rc == 0 and W.reward['DKBO'] == 5, f'{rc} {out[-300:]}')
check('胡椒存回公倉、背包沒殘留、沒買胡椒', W.public.get('黑胡椒') == 5 and '黑胡椒' not in W.bag['DKBO'] and not any(a[0] == 'buy' and a[2] == '黑胡椒' for a in W.log), str(W.public))
fresh_dir()
W = scenario(items=it6, roles=['DKBO'])                                   # 公倉沒有胡椒
rc, out = quiet(daily.run, roles=['DKBO'], confirm_buy=True, tools=FakeTools(W), recipes=rec7, stores=STORES, where=WHERE)
check('公倉取不到胡椒 → 222、不買胡椒', rc == 222 and not any(a[0] == 'buy' and a[2] == '黑胡椒' for a in W.log), f'{rc} {out[-300:]}')

# ---------------- 情境 8：跨 00:00 ----------------
fresh_dir()
W = scenario()
state = {'d': '2026-10-17'}
orig_today = dp.today
dp.today = lambda now=None: state['d']
T = FakeTools(W)
_orig_buy = T.shop_buy


def buy_then_midnight():
    _orig_buy()
    if W.bought_n >= 20:
        state['d'] = '2026-10-18'                                         # 跑到一半跨日


T.shop_buy = buy_then_midnight
rc, out, _ = go(W, T)
check('跑到一半跨過 00:00 → 220 停手（不自動重讀）', rc == 220 and daily.LAST.get('crossed'), f'{rc} {out[-300:]}')
fresh_dir()
W2 = scenario()
state['d'] = '2026-10-17'
go(W2, FakeTools(W2), confirm_buy=False)                                  # 前一天讀完沒跑完（team 沒 complete）
state['d'] = '2026-10-18'
rc, out, _ = go(W2)
check('昨天沒跑完的進度檔、今天直接跑 → 220（要 --fresh）', rc == 220, f'{rc} {out[-300:]}')
rc, out, _ = go(W2, fresh=True)
check('--fresh 丟掉重來 → 完成', rc == 0 and all(W2.reward[r] == 5 for r in W2.roles), f'{rc} {out[-300:]}')
dp.today = orig_today
# 昨天已完成 → 今天自動新的一輪
fresh_dir()
W = scenario(items=items1, roles=['DKBO'])
state['d'] = '2026-10-17'
dp.today = lambda now=None: state['d']
rc, _, _ = go(W)
state['d'] = '2026-10-18'
W3 = scenario(items=items1, roles=['DKBO'])
rc3, out3, _ = go(W3)
check('昨天已 complete → 今天自動新的一輪（不用 --fresh）', rc == 0 and rc3 == 0 and W3.reward['DKBO'] == 5, f'{rc} {rc3} {out3[-200:]}')
dp.today = orig_today

# ---------------- 情境 9：讀 / 合成 / 提交失敗 ----------------
fresh_dir()
W = scenario(items=it6, roles=['DKBO'])
W.inj['noise'] = ('DKBO', 1)                                              # 第 2 環第 2 項 OCR 壞掉 → peek 救回
rc, out, _ = go(W)
check('名稱 OCR 壞 → 開彈窗讀大字救回 → 完成', rc == 0 and W.reward['DKBO'] == 5, f'{rc} {out[-300:]}')
fresh_dir()
W = scenario(items=it6, roles=['DKBO'])
W.inj['noise'] = ('DKBO', 1)
W.inj['peek_fail'] = True
rc, out, _ = go(W)
check('名稱 OCR 壞、彈窗也讀不出 → 225（已讀的不寫成 read）', rc == 225 and not (dp.load(dp.role_path('DKBO')) or {}).get('read'), f'{rc} {out[-300:]}')
fresh_dir()
W = scenario(items=it6, roles=['DKBO'])
W.inj['panel_fail'] = True
rc, out, _ = go(W)
check('委託面板打不開 → 224', rc == 224, f'{rc} {out[-200:]}')
fresh_dir()
W = scenario(items=it6, roles=['DKBO'])
W.inj['craft_fail'] = ('DKBO', '大補飯團')
rc, out, T = go(W)
check('合成失敗 → 229、停手（不提交）、面板已關', rc == 229 and not W.panel, f'{rc} {out[-300:]}')
fresh_dir()
W = scenario(items=it6, roles=['DKBO'])
W.inj['submit_noop'] = 'DKBO'
rc, out, T = go(W)
check('提交後計數沒 +1 → 229', rc == 229, f'{rc} {out[-300:]}')
fresh_dir()
W = scenario(items=it6, roles=['DKBO'])
W.inj['reward_none'] = True
rc, out, T = go(W)
check('獎勵計數讀不到：提交以「兩項不再綠」判斷 → 仍完成（5/5 驗證退而看背包，無「裝備升級石」→ 229 or 完成）', rc in (0, 229), f'{rc} {out[-200:]}')
fresh_dir()
W = scenario(items=it6, roles=['DKBO'])
W.inj['switch_rc'], W.inj['switch_role'] = 41, 'DKBO'
rc, out, T = go(W)
check('切當前角色失敗 → 223', rc == 223, f'{rc} {out[-200:]}')

# 驗證視窗（preflight 回 9）→ 原碼停手
fresh_dir()
W = scenario(items=it6, roles=['DKBO'])
T = FakeTools(W)
T.preflight = lambda: 9
rc, out, _ = go(W, T)
check('prep preflight 回 9（驗證視窗）→ 原碼 9', rc == 9, f'{rc}')

# ---------------- 情境 10：--from 與 dry-run / plan ----------------
fresh_dir()
W = scenario(items=it6, roles=['DKBO'])
rc, out, _ = go(W, dry_run=True)
check('dry-run 沒進度檔 → 220（提示先 read-all）、不碰遊戲', rc == 220 and not W.log and '尚未讀清單' in out, f'{rc} {out[-200:]}')
rc, out, _ = go(W, confirm_buy=False)
rc, out, _ = go(W, dry_run=True)
check('dry-run：讀過清單後印計畫 rc 0、不動遊戲', rc == 0 and '26,000' in out)
n_log = len(W.log)
rc, out, _ = go(W, dry_run=True)
check('dry-run 不新增遊戲動作', len(W.log) == n_log)
rc, out = quiet(daily.show)
check('show 印每人狀態', rc == 0 and 'DKBO' in out)
rc, out, _ = go(W, from_stage='nonsense')
check('--from 不是段名 → 220', rc == 220)

# ---------------- 情境 11：read-all（只做 prep + read）----------------
fresh_dir()
W = scenario()
T = FakeTools(W)
daily.ROLES[:] = W.roles
daily.LEADER = W.roles[0]
rc, out = quiet(daily.run, roles=W.roles, from_stage='prep', stop_after='read', tools=T, recipes=RECIPES, stores=STORES, where=WHERE)
check('read-all：只讀不買不合成，rc 0', rc == 0 and W.bought_n == 0 and W.crafted_n == 0 and all(dp.load(dp.role_path(r))['read'] for r in W.roles), f'{rc} {out[-300:]}')
check('read-all 後停在 plan（team.done = prep, read）', dp.load(dp.team_path())['done'] == ['prep', 'read'])

# ---------------- 情境 12：已 1/1 綠的項不重做 ----------------
fresh_dir()
W = scenario(items=it6, roles=['DKBO'])
W.green['DKBO'][0] = [True, True]                                         # 第 1 環遊戲裡已兩項綠（先前手動合成過，成品在背包）
W.bag['DKBO'].update({'成品:厚肉塊串燒': 1, '成品:熱的魚味噌湯': 1})
rc, out, _ = go(W)
check('讀到第 1 環已綠：不買它的材料、不合成；仍提交（5/5）', rc == 0 and W.reward['DKBO'] == 5 and not any(a[0] == 'buy' and a[2] in ('幹燥肉', '新鮮的魚') and False for a in W.log), f'{rc} {out[-300:]}')

# ---------------- 情境 13：解散後各自走（2026-10-17：隊員落點不一致）----------------
H = 1005
for name, pos, want_v, want in [
    ('村裡（1000:74,72）→ 先 walk_village、走全部 waypoint', (1000, 74, 72), True, [(31, 60), (36, 60), (38, 55), (38, 48)]),
    ('位置讀不到 → 同不在醫院', None, True, [(31, 60), (36, 60), (38, 55), (38, 48)]),
    ('醫院入口 25,65 → 全部 waypoint（不先 walk_village）', (H, 25, 65), False, [(31, 60), (36, 60), (38, 55), (38, 48)]),
    ('醫院 26,64 → 全部', (H, 26, 64), False, [(31, 60), (36, 60), (38, 55), (38, 48)]),
    ('31,60 已到 → 不回頭、從 36,60 起', (H, 31, 60), False, [(36, 60), (38, 55), (38, 48)]),
    ('35,55（卡點）→ 從 38,55 起，不回 31,60', (H, 35, 55), False, [(38, 55), (38, 48)]),
    ('35,54 → 同上', (H, 35, 54), False, [(38, 55), (38, 48)]),
    ('38,55 → 只剩 38,48', (H, 38, 55), False, [(38, 48)]),
    ('38,52 → 只剩 38,48', (H, 38, 52), False, [(38, 48)]),
    ('38,48 站位 → 不走', (H, 38, 48), False, []),
    ('NPC 3 格內 40,44 → 不走', (H, 40, 44), False, []),
]:
    v, r = daily.hosp_route(pos)
    check(f'hosp_route {name}', v == want_v and r == want, f'{v} {r}')
check('hosp_route 任何起點都不含站位以前的 31,60（除非更靠近入口）', all((31, 60) not in daily.hosp_route((H, x, y))[1] for x, y in [(36, 60), (38, 50), (37, 57)]))


class _Mod:
    pass


def fake_walk_env(pos):
    log = []
    walk, heal = _Mod(), _Mod()
    walk.wait_pos = lambda tries=6, want_map=None, gap=0.5: pos
    walk.step_to = lambda m, x, y, exit_map=None: log.append(('step', m, x, y))
    heal.walk_village = lambda: log.append(('village',))
    old = (sys.modules.get('walk'), sys.modules.get('heal'))
    sys.modules['walk'], sys.modules['heal'] = walk, heal
    return log, old


def restore_env(old):
    for k, v in zip(('walk', 'heal'), old):
        if v is None:
            sys.modules.pop(k, None)
        else:
            sys.modules[k] = v


for name, pos, want in [
    ('村裡', (1000, 74, 72), [('village',), ('step', H, 31, 60), ('step', H, 36, 60), ('step', H, 38, 55), ('step', H, 38, 48)]),
    ('醫院入口', (H, 26, 64), [('step', H, 31, 60), ('step', H, 36, 60), ('step', H, 38, 55), ('step', H, 38, 48)]),
    ('35,55', (H, 35, 55), [('step', H, 38, 55), ('step', H, 38, 48)]),
    ('38,48', (H, 38, 48), []),
]:
    log, old = fake_walk_env(pos)
    try:
        ok = daily.Tools().into_hospital()
    finally:
        restore_env(old)
    check(f'Tools.into_hospital 從{name}：走法正確', ok and log == want, f'{ok} {log}')


class SpotT:
    """go_spot 用的最小假 Tools（各自的位置 + 動作 log）"""
    def __init__(self, pos, hosp_ok=True, walk_ok=True):
        self.p, self.log, self.hosp_ok, self.walk_ok = pos, [], hosp_ok, walk_ok

    def pos(self): return self.p
    def sleep(self, s): pass

    def into_hospital(self):
        self.log.append('hospital')
        return self.hosp_ok

    def to_town(self):
        self.log.append('to_town')
        self.p = (1000, 92, 99)
        return True

    def to_marinas(self):
        self.log.append('to_marinas')
        self.p = (2000, 65, 58)
        return True

    def walk_to(self, m, x, y, exit_map=None):
        self.log.append(('walk_to', m, x, y, exit_map))
        return self.walk_ok


def spot(pos, where_, **kw):
    T = SpotT(pos, **kw)
    D = daily.Daily(T, {}, ['DKBO', 'DKBO2'], recipes=RECIPES, stores=STORES, where=WHERE)
    try:
        D.go_spot('DKBO3', where_)
        return 0, T
    except daily.Stop as e:
        return e.rc, T


rc, T = spot((1005, 38, 48), 'hospital')
check('go_spot 醫院：交給 into_hospital（pos-aware）', rc == 0 and T.log == ['hospital'])
rc, T = spot((1005, 35, 55), 'hospital', hosp_ok=False)
check('go_spot 醫院走不到 → 224 帶座標', rc == 224 and '35, 55' in str(T.pos()))
rc, T = spot((1000, 92, 99), 'sam')
check('go_spot 薩村料：在村裡 → 直接走 1009 出口、不傳送', rc == 0 and T.log == [('walk_to', 1000, 106, 91, 1009)], T.log)
rc, T = spot((1009, 25, 17), 'sam')
check('go_spot 薩村料：已在店內 → 不動', rc == 0 and T.log == [])
rc, T = spot((1005, 38, 48), 'sam')
check('go_spot 薩村料：在醫院 → 先傳送再走', rc == 0 and T.log == ['to_town', ('walk_to', 1000, 106, 91, 1009)], T.log)
rc, T = spot((2000, 70, 100), 'fish')
check('go_spot 漁村料：在瑪麗娜絲 → 走 2009 出口', rc == 0 and T.log == [('walk_to', 2000, 73, 103, 2009)], T.log)
rc, T = spot((2009, 25, 15), 'fish')
check('go_spot 漁村料：已在店內 → 不動', rc == 0 and T.log == [])
rc, T = spot((1000, 92, 99), 'sam', walk_ok=False)
check('go_spot 走不進店 → 224', rc == 224)

# 整段流程：解散前隊長不走進醫院（只傳送）、解散後每人各自 into_hospital
fresh_dir()
W = scenario()
rc, out, _ = go(W)
lg = [a[0] for a in W.log]
first_dis = lg.index('disband')
check('prep：解散前沒有 into_hospital / walk_to（只傳送）', rc == 0 and 'into_hospital' not in lg[:first_dis] and 'walk_to' not in lg[:first_dis], f'{rc} {lg[:first_dis]}')
check('read：每人切角色後各自 into_hospital', lg.count('into_hospital') >= len(W.roles), f'{lg.count("into_hospital")}')

# ---------------- 結尾 ----------------
check('0 次 powershell（全測試）', not PS_CALLS)
print('ALL PASS' if not fails else f'FAILED {fails}')
sys.exit(1 if fails else 0)
