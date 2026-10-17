#!/usr/bin/env python3
"""daily.py / dailyplan.py / shopkit.py 離線測試（假 Tools 模擬遊戲世界；0 次 powershell、不碰遊戲）。
用法：uv run --no-project python tools/gui/test_daily.py"""
import contextlib
import io
import json
import subprocess
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

# ---------------- 快速合成彈窗第二輪（fixtures/daily_pop_ocr.json = p1 2026-10-17 樣本 50 項 + ▼ 項的捲動版；成品名框 380,398,204,50、材料列整欄 686,228,234,402）----------------
PX = json.loads((Path(__file__).resolve().parent / 'fixtures' / 'daily_pop_ocr.json').read_text(encoding='utf-8'))
TRUTHS = sorted({dp.norm(c['truth']) for c in PX['cases']})
bad, wrong, partial_first = [], [], 0
for c in PX['cases']:
    t = dp.norm(c['truth'])
    first = {k: c[k] for k in ('name', 'list', 'down', 'up')}
    info = dp.pop_mats(first, RECIPES)
    partial_first += dp.mats_fit(t, info, RECIPES) == 'partial'
    if dp.resolve_name(dp.vote_lines([], RECIPES), dp.vote_lines(c['name'], RECIPES), info, RECIPES) != t or dp.pop_check(t, first, RECIPES) is not True:
        bad.append((c['img'], t))
    wrong += [(c['img'], o) for o in TRUTHS if o != t and dp.pop_check(o, first, RECIPES) is True]
check(f'彈窗 50 項（第一眼不捲）：resolve_name / pop_check 全對（{len(PX["cases"])} 項）', len(PX['cases']) == 50 and not bad, str(bad[:3]))
check('彈窗 50 項：拿其他 39 個成品名去核對一律不是（0 誤認，含材料相同的厚肉塊串燒 / 鹽味獸肉串燒、葉子烤蕃薯 / 半熟的芋頭）', not wrong, str(wrong[:3]))
check('彈窗：▼ 亮 ⇔ 第一眼看不到石幣列（材料 4 種以上）；第一眼只看到前 4 列 → partial', all(c['down'] == (dp.COIN not in dp.pop_rows(c['list'], RECIPES)) for c in PX['cases'])
      and partial_first == sum(c['down'] for c in PX['cases']) == 16, str(partial_first))
sc = [c for c in PX['cases'] if 'list2' in c]
full2 = [c for c in sc if dp.mats_fit(c['truth'], dp.pop_mats(c, RECIPES), RECIPES) == 'full' and dp.pop_check(c['truth'], c, RECIPES) is True]
check(f'彈窗：▼ 項捲一次後兩張依序合併 → 材料列完整且吻合配方（{len(sc)} 項）', len(sc) == 15 and len(full2) == len(sc), f'{len(full2)}/{len(sc)}')
check('彈窗：大字讀不到 → pop_check 一律不是 True（材料相同的不同成品不能只靠材料認）',
      all(dp.pop_check(o, dict(c, name=[]), RECIPES) is not True for c in PX['cases'] for o in TRUTHS))
T = PX['trap_up_overlap']
check('彈窗：▲ 蓋住第 1 列（「有光澤的地瓜」只剩「有光澤的」）→ up=True 時不收該行，不會變成「有光澤的皮」',
      '有光澤的皮' not in dp.pop_rows(T['list'], RECIPES, up=T['up']) and '有光澤的皮' in dp.pop_rows(T['list'], RECIPES, up=False) and T['up'])
c0 = next(c for c in PX['cases'] if dp.norm(c['truth']) == '厚肉塊串燒')
check('pop_check：材料相同的鹽味獸肉串燒 → False（大字投給厚肉塊串燒）', dp.pop_check('鹽味獸肉串燒', c0, RECIPES) is False and dp.pop_check('厚肉塊串燒', c0, RECIPES) is True)
check('mats_fit：看到整張卻少一列 → False（不當 partial）', dp.mats_fit('特製2倍厚肉片', {'seq': ['幹燥肉', '粗鹽', '燃燒完全的炭'], 'complete': True}, RECIPES) is False
      and dp.mats_fit('特製2倍厚肉片', {'seq': ['幹燥肉', '大的大蒜'], 'complete': False}, RECIPES) == 'partial'
      and dp.mats_fit('特製2倍厚肉片', {'seq': ['大的大蒜', '幹燥肉'], 'complete': False}, RECIPES) is False)
check('arrow_on：黃 → True；米色 / None → False', dp.arrow_on([(251, 228, 20)]) and not dp.arrow_on([(255, 221, 188)]) and not dp.arrow_on(None))

# ---------------- 快速合成彈窗：實機材料齊（1/1 綠）+ 大字讀空重讀（p1 2026-10-17 20:09 229）----------------
LV = PX['live_full']
check('實機材料齊（1/1 綠）彈窗：成品名仍是黃字、同參數讀得出 → pop_check 合成弓箭8 True、計數不判紅',
      dp.vote_lines(LV['name'], RECIPES)['sure'] and dp.pop_check(LV['truth'], LV, RECIPES) is True and not LV['short'] and not dp.popup_short([tuple(c) for c in LV['counts']]))
check('實機材料齊彈窗：拿其他成品名核對一律不是（0 誤認）', not [o for o in TRUTHS if o != dp.norm(LV['truth']) and dp.pop_check(o, LV, RECIPES) is True])
check('實機材料齊彈窗：大字讀空 → pop_check 不是 True（不放寬大字證據）', dp.pop_check(LV['truth'], dict(LV, name=[]), RECIPES) is not True)
_kp = (uikit.ocr_lines, uikit.is_open, uikit.sleep, uikit.safe_click, uikit.px, uikit.snap, uikit.gui)
_seq, _ocr_n, _sl, _clicks, _snaps = [], [], [], [], []
try:
    _open = [True]
    uikit.ocr_lines = lambda box, *o: (_ocr_n.append(box), (_seq.pop(0) if _seq else []) if tuple(box) == daily.POP_NAME_BOX else LV['list'])[1]
    uikit.is_open = lambda p: _open[0]
    uikit.sleep = lambda t: _sl.append(t)
    _seq[:] = [[], [], LV['name']]
    got = daily.Tools().pop_name()
    check('pop_name：前 2 次讀空 → 等 0.5 秒重讀，第 3 次讀到合成弓箭8', got == LV['name'] and len(_ocr_n) == 3 and _sl == [daily.POP_NAME_WAIT] * 2, f'{len(_ocr_n)} {_sl}')
    _ocr_n.clear(); _sl.clear(); _seq[:] = [LV['name']]
    check('pop_name：第一次就讀到 → 不重讀、不等', daily.Tools().pop_name() == LV['name'] and len(_ocr_n) == 1 and not _sl)
    _ocr_n.clear(); _sl.clear(); _seq[:] = []
    check('pop_name：3 次都空 → 回空、只讀 3 次', daily.Tools().pop_name() == [] and len(_ocr_n) == daily.POP_NAME_TRIES == 3 and len(_sl) == 2)
    _ocr_n.clear(); _sl.clear(); _open[0] = False
    check('pop_name：彈窗不在 → 不重讀', daily.Tools().pop_name() == [] and len(_ocr_n) == 1 and not _sl)
    # craft_item：大字 3 次全空 → 不按合成、存現場圖、回失敗（229 路徑）
    _open[0] = True; _seq[:] = []
    uikit.safe_click = lambda x, y, panel=None, note='', **k: (_clicks.append(note), True)[1]
    uikit.px = lambda pts, cmd='pixel': [(223, 187, 147)] * len(pts)
    uikit.snap = lambda tag: (_snaps.append(tag), 'tools/.cache/ui-log/x.png')[1]
    uikit.gui = lambda *a, **k: ''
    ok, why = daily.Tools().craft_item(0, '合成弓箭8')
    check('craft_item：大字 3 次全空 → 不合成、存現場圖、原因帶圖路徑',
          not ok and not any('1000 石幣' in n for n in _clicks) and _snaps == ['daily-pop-fail'] and 'ui-log/x.png' in why, f'{ok} {why} {_clicks}')
    # craft_item：剛開讀空、重讀到大字 → 照常合成（按合成鈕）
    _clicks.clear(); _snaps.clear(); _seq[:] = [[], LV['name']]
    def _px(pts, cmd='pixel'):
        if list(pts) == [daily.STATE_PX[0]]:
            return [(0, 200, 0)]                                     # 合成後該項綠
        if list(pts) == daily.POP_COUNT_PX:
            return [tuple(c) for c in LV['counts']]
        return [(223, 187, 147)] * len(pts)
    uikit.px = _px
    ok, why = daily.Tools().craft_item(0, '合成弓箭8')
    check('craft_item：剛開大字讀空、重讀到 → 照常按合成（花 1000 石幣）且不存失敗圖',
          any('1000 石幣' in n for n in _clicks) and not _snaps, f'{ok} {why} {_clicks}')
finally:
    uikit.ocr_lines, uikit.is_open, uikit.sleep, uikit.safe_click, uikit.px, uikit.snap, uikit.gui = _kp

# ---------------- 便利店標題（fixtures/daily_shop_titles.json = p1 2026-10-17 11 間店 × 12 張）----------------
SX = json.loads((Path(__file__).resolve().parent / 'fixtures' / 'daily_shop_titles.json').read_text(encoding='utf-8'))
STORES, _ = dp.load_stores()
bad, wrong = [], []
for c in SX['cases']:
    order = STORES[c['npc']].items
    v = shopkit.title_vote(c['lines'], order)
    if v['name'] != dp.norm(c['truth']) or not shopkit.title_is(c['lines'], c['truth'], order):
        bad.append((c['img'], c['truth'], v['texts']))
    wrong += [(c['img'], o) for o in order if o != dp.norm(c['truth']) and shopkit.title_is(c['lines'], o, order)]
check(f'便利店標題 132 張逐倍率比對該店清單投票全對（{len(SX["cases"])} 張，含霍特爾產的馬鈴薯）', len(SX['cases']) == 132 and not bad, str(bad[:3]))
check('便利店標題：拿同店其他商品去核對一律不是（0 誤認）', not wrong, str(wrong[:3]))
check('便利店標題：舊讀法（各倍率 join 一串再 title_match）在同一批樣本會失敗', sum(shopkit.title_match(''.join(ln['text'] for ln in c['lines'] if isinstance(ln['zoom'], int)), c['truth']) for c in SX['cases']) < 132)
LZ = lambda *ts: [{'text': t, 'x': 990, 'zoom': z} for z, t in enumerate(ts, 2)]  # noqa: E731
ORD = ['普通的青椒', '大的青椒', '有光澤的青椒']
check('title_vote：4 票對 1 票 → 多數決收；1 對 1 → None', shopkit.title_vote(LZ('普通的青椒', '普通的青椒', '大的青椒', '普通的青椒', '普通的青椒'), ORD)['name'] == '普通的青椒'
      and shopkit.title_vote(LZ('普通的青椒', '大的青椒'), ORD)['name'] is None)
check('title_is：字串（舊介面）走 title_match；清單沒給只比 want', shopkit.title_is('硬的 殼', '硬的殼') and shopkit.title_is(LZ('溫蒂妮Lv5的金幣'), '溫蒂妮Lv5的金幣') and not shopkit.title_is(None, '硬的殼'))

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
def _monotone(route):
    return all([st.items.index(n) for n, _ in v] == sorted(st.items.index(n) for n, _ in v) for st, v in route)


check('store_route：店內依商品清單 index 由小到大（227 修；不再早環先買）', _monotone(R_SAM) and _monotone(R_FISH))
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

# ---------------- 便利店數量框：像素字形（numglyph kind shop；fixtures/numglyph_samples.json = 真截圖裁切；2026-10-17 p1 OCR 讀「1」全空 → 227）----------------
import json  # noqa: E402
import numglyph  # noqa: E402
_NFX = [x for x in json.loads((HERE / 'fixtures' / 'numglyph_samples.json').read_text(encoding='utf-8'))['samples'] if x['kind'] == 'shop']


def _qpaint(s):
    x, y, w, h = s['box']
    hx = s['px']
    return {(x + i % w, y + i // w): tuple(int(hx[i * 6 + k:i * 6 + k + 2], 16) for k in (0, 2, 4)) for i in range(w * h)}


check('shop 樣本 6 張（1 ×2、3、鍵盤開著、實機 227 存證 ×2）', len(_NFX) == 6 and tuple(numglyph.SHOP_QTY_BOX) == shopkit.QTY_BOX)
check('shop 現場取像素走 spixel（跟截圖同一段縮圖；dev-shop-qty2）', numglyph.LIVE_SRC['shop'] == 'shot')
_keep_px, _keep_ocrl, _keep_sleep, _keep_buy = uikit.px, uikit.ocr_lines, uikit.sleep, shopkit.buy_once
_keep_gui0 = uikit.gui
_qp, _ocr_calls, _gcmds = {}, [], []


def _fake_gui(cmd, arg='', note=''):
    """模擬 gui.ps1 這一層（uikit.px / spx 真的跑）：spixel = 截圖縮圖取色（= fixture）；pixel = 原生單點（點陣跟截圖不同，這裡回框底色 → 0 字）"""
    _gcmds.append(cmd)
    pts = [tuple(int(v) for v in t.split(',')) for t in arg.split()]
    if cmd == 'spixel':
        return ' '.join('%d,%d,%d' % _qp.get(pt, (223, 187, 147)) for pt in pts)
    if cmd == 'pixel':
        return ' '.join('223,187,147' for _ in pts)
    return ''


try:
    uikit.gui = _fake_gui
    _qp.update(_qpaint(next(x for x in _NFX if x['f'].endswith('192744-shop-qty-unread.png'))))
    check('模擬實機：qty_now 經 uikit.spx → gui spixel 讀 227 存證 = 1', shopkit.qty_now() == 1 and 'spixel' in _gcmds and 'pixel' not in _gcmds, str(_gcmds))
    _gcmds.clear()
    check('模擬實機：buy_checked 前後讀也走 spixel', numglyph.read_box('shop')['value'] == 1 and _gcmds == ['spixel'], str(_gcmds))
    _gcmds.clear()
    check('對照：qty 仍走 pixel（LIVE_SRC px；點多會分批）', numglyph.read_box('qty')['n'] == 0 and set(_gcmds) == {'pixel'}, str(_gcmds))
    uikit.gui = _keep_gui0
    _qp.clear()
    uikit.px = lambda pts, cmd='pixel': [_qp.get(pt, (223, 187, 147)) for pt in pts]
    uikit.ocr_lines = lambda box, *o: (_ocr_calls.append(box), [])[1]       # OCR 一律讀空（實機就是這樣）
    uikit.sleep = lambda t: None
    for smp in _NFX:
        _qp.clear()
        _qp.update(_qpaint(smp))
        got = shopkit.qty_now()
        check(f'qty_now 讀真截圖 {smp["f"]} → {smp["value"]!r}（OCR 全空也讀得到）', got == smp['value'], repr(got))
    check('數量框認得 1、3（種子樣板）', {'1', '3'} <= shopkit.known_digits())
    # set_qty（＋ / － 鈕）：已是 1 → 不點；要 3 → ＋ ×2；差一 → －/＋ 補差；讀不出 → 退回起點 False；鍵盤備援仍在
    one = next(x for x in _NFX if x['value'] == 1)
    three = next(x for x in _NFX if x['value'] == 3)
    _qp.clear(); _qp.update(_qpaint(one))
    calls = []
    keep_gui = uikit.gui
    uikit.gui = lambda *a, **k: (calls.append(a), '')[1]
    nclk = lambda xy: sum(a[1].count(f'click {xy[0]} {xy[1]};') for a in calls)
    check('set_qty(1)：數量框已是 1 → 不點', shopkit.set_qty(1) and not calls, str(calls))
    reads = iter([1, 3])
    check('set_qty(3)：讀到 1 → ＋ ×2 → 讀回 3 = 成功；沒點鍵盤', shopkit.set_qty(3, reader=lambda: next(reads)) and nclk(shopkit.QTY_PLUS) == 2 and nclk(shopkit.QTY_XY) == 0, str(calls))
    calls.clear(); reads = iter([1, 33])
    check('set_qty(33)：＋ ×32，批次 ≤ 25 下 / seq', shopkit.set_qty(33, reader=lambda: next(reads)) and nclk(shopkit.QTY_PLUS) == 32 and len(calls) == 2, str(len(calls)))
    calls.clear(); reads = iter([1, 4, 3])
    check('set_qty(3)：＋ ×2 後讀到 4（多一）→ － ×1 補差 → 讀回 3', shopkit.set_qty(3, reader=lambda: next(reads)) and nclk(shopkit.QTY_PLUS) == 2 and nclk(shopkit.QTY_MINUS) == 1, str(calls))
    calls.clear(); reads = iter([1, 2, 3])
    check('set_qty(3)：＋ ×2 後讀到 2（少一）→ ＋ ×1 補差', shopkit.set_qty(3, reader=lambda: next(reads)) and nclk(shopkit.QTY_PLUS) == 3, str(calls))
    calls.clear(); reads = iter([1, None])
    check('set_qty(3)：＋ 後讀不出 → 不猜、－ ×2 退回起點、False', (not shopkit.set_qty(3, reader=lambda: next(reads))) and nclk(shopkit.QTY_PLUS) == 2 and nclk(shopkit.QTY_MINUS) == 2, str(calls))
    calls.clear()
    check('set_qty：起點讀不出又沒給 start → False 不點', not shopkit.set_qty(2, reader=lambda: None) and not calls, str(calls))
    calls.clear(); reads = iter([None, 1])
    check('set_qty(1, start=0)：框讀不出（買完歸 0）→ ＋ ×1 → 讀回 1', shopkit.set_qty(1, reader=lambda: next(reads), start=0) and nclk(shopkit.QTY_PLUS) == 1, str(calls))
    calls.clear(); reads = iter([1, 3])
    check('set_qty_keypad（備援）：讀到 1 → 鍵盤輸入 → 讀回 3', shopkit.set_qty_keypad(3, reader=lambda: next(reads)) and nclk(shopkit.QTY_XY) == 1 and nclk(shopkit.QTY_PLUS) == 0, str(calls))
    # buy_checked（buy_once 換成「把框換成下一張圖」）：買後一樣 / 認得但不是 0 / 沒字
    seq = []
    shopkit.buy_once = lambda: (_qp.clear(), _qp.update(seq.pop(0)))
    seq[:] = [_qpaint(one)]
    _qp.clear(); _qp.update(_qpaint(one))
    check('buy_checked：買後點陣跟買前一樣 → not_bought', shopkit.buy_checked(1) == 'not_bought')
    seq[:] = [_qpaint(three)]
    _qp.clear(); _qp.update(_qpaint(one))
    check('buy_checked：買 1 後讀到 3（認得但不是 0）→ unknown', shopkit.buy_checked(1) == 'unknown')
    seq[:] = [{}]
    _qp.clear(); _qp.update(_qpaint(one))
    check('buy_checked：買後框內沒字（被蓋住）→ unknown（等過也沒字）', shopkit.buy_checked(1) == 'unknown')
    uikit.gui = keep_gui
finally:
    uikit.px, uikit.ocr_lines, uikit.sleep, shopkit.buy_once = _keep_px, _keep_ocrl, _keep_sleep, _keep_buy
    uikit.gui = _keep_gui0

# buy_verdict（純函式）
R1, R0 = ['01'], ['10']
check('buy_verdict：讀到 0 → bought', shopkit.buy_verdict({'value': 1, 'n': 1, 'rows': R1}, {'value': 0, 'n': 1, 'rows': R0}, 1) == 'bought')
check('buy_verdict：認不出的單字、點陣變了 → zeroish（交背包核對）', shopkit.buy_verdict({'value': 1, 'n': 1, 'rows': R1}, {'value': None, 'n': 1, 'rows': R0}, 1) == 'zeroish')
check('buy_verdict：買前就讀不出 → 不能判 zeroish / not_bought → unknown',
      shopkit.buy_verdict({'value': None, 'n': 1, 'rows': R1}, {'value': None, 'n': 1, 'rows': R0}, 1) == 'unknown'
      and shopkit.buy_verdict({'value': None, 'n': 1, 'rows': R1}, {'value': None, 'n': 1, 'rows': R1}, 1) == 'unknown')
check('buy_verdict：2 個認不出的字 → unknown', shopkit.buy_verdict({'value': 13, 'n': 2, 'rows': R1}, {'value': None, 'n': 2, 'rows': R0}, 13) == 'unknown')
# qty_chunks：只用認得的數字
check('qty_chunks：{1,3} 7 → 3+3+1、20 → 13+3+3+1、1 → [1]、33 → [33]',
      shopkit.qty_chunks(7, {'1', '3'}) == [3, 3, 1] and shopkit.qty_chunks(20, {'1', '3'}) == [13, 3, 3, 1]
      and shopkit.qty_chunks(1, {'1', '3'}) == [1] and shopkit.qty_chunks(33, {'1', '3'}) == [33])
check('qty_chunks：全認得 → 一次；沒有 1 拆不出 → None；1500 → 999+…',
      shopkit.qty_chunks(256, set('0123456789')) == [256] and shopkit.qty_chunks(2, {'3'}) is None
      and shopkit.qty_chunks(1500, set('0123456789')) == [999, 501])
check('qty_vote：各倍率一致才收、單一倍率 / 不一致 → None（不把「1」「1」併成 11）',
      shopkit.qty_vote([{'text': '12', 'zoom': 2}, {'text': '12', 'zoom': 3}]) == 12
      and shopkit.qty_vote([{'text': '1', 'zoom': 2}]) is None
      and shopkit.qty_vote([{'text': '1', 'zoom': 2}, {'text': '7', 'zoom': 3}]) is None)

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
# 227 重現：目標在視野上方（舊版只會往下拖 → 選不到）→ 捲回頂端歸零再找
def run_select_back(want, start_drags, top_resets=True):
    GUI_LOG.clear()
    state = {'drags': start_drags}
    off = {'d': start_drags}                                  # 真實視野第一列 = d×2；scroll_top 的 DRAG_DOWN 拖回 0

    def reader():
        last = [a for a in GUI_LOG if a and a[0] == 'seq' and a[1].startswith('click')]
        x, y = [int(v) for v in last[-1][1].split(';')[0].split()[1:3]]
        col = 0 if x < 540 else 1
        idx = (off['d'] * 2 + round((y - shopkit.ROW_Y0) / shopkit.ROW_PITCH)) * 2 + col
        return ORDER[idx] if 0 <= idx < len(ORDER) else ''
    for a in list(GUI_LOG):
        pass
    orig = uikit.gui

    def fake(*a, **k):
        r = orig(*a, **k)
        if a and a[0] == 'seq' and a[1].startswith('drag'):
            off['d'] = 0 if (top_resets and a[1].split()[2] == str(shopkit.DRAG_DOWN[1])) else off['d'] + 1
        return r
    uikit.gui = fake
    try:
        ok = shopkit.select_item(want, ORDER, state, reader=reader)
    finally:
        uikit.gui = orig
    return ok, state['drags']


ok, drags = run_select_back('商品01', 3)
check('select_item：目標在視野上方（已拖 3 次、要第 1 項）→ 捲回頂端後選到', ok and drags == 0, f'{ok} {drags}')
ok, drags = run_select_back('商品04', 2)
check('select_item：已拖 2 次、要第 4 項（上方）→ 選到', ok, f'{ok} {drags}')
check('select_item：不在清單 → False', not shopkit.select_item('沒這個', ORDER, {'drags': 0}, reader=lambda: ''))


# 整店模擬：商店清單（2 欄先左後右）、視野第一列 = min(拖次數×2, 最大偏移)；依 store_route 的店內順序逐項 select_item，全部要選得到
def sim_shop(store, mats, nav_state=None):
    order = store.items
    max_off = max(0, (len(order) + 1) // 2 - shopkit.VIEW_ROWS + 1)
    off = {'d': 0}
    cur = {'c': None}
    orig = uikit.gui

    def fake(*a, **k):
        if a and a[0] == 'seq':
            cmd = a[1].split(';')[0].split()
            if cmd[0] == 'drag':
                off['d'] = max(0, min(max_off, off['d'] + (2 if int(cmd[2]) == shopkit.DRAG_UP[1] else -2 * 99)))
            elif cmd[0] == 'click':
                x, y = int(cmd[1]), int(cmd[2])
                cur['c'] = ((off['d'] + round((y - shopkit.ROW_Y0) / shopkit.ROW_PITCH)) * 2 + (0 if x < 540 else 1))
        return ''
    uikit.gui = fake
    res = []
    try:
        st = {'drags': 0}
        for name, q in mats:
            res.append(shopkit.select_item(name, order, st, reader=lambda: order[cur['c']] if cur['c'] is not None and 0 <= cur['c'] < len(order) else ''))
    finally:
        uikit.gui = orig
    return res


def sim_role_items(items):
    pl = dp.plan_role(items, RECIPES, WHERE, STORES)
    bad = []
    for stage in ('sam', 'fish'):
        for store, mats in dp.store_route(stage, pl['buy'].get(stage) or {}, WHERE, STORES, pl['first_use']):
            if not _monotone([(store, mats)]) or not all(sim_shop(store, mats)):
                bad.append((store.name, [n for n, _ in mats]))
    return bad


P1_DKBO2 = [['合成弓箭8', '合成投擲斧頭2'], ['原始肉的經濟套餐', '原始粽子'], ['合成弓箭5', '精心燉煮過的肉丸'], ['鹽味的油炸螃蟹', '半熟的芋頭'], ['大補飯團', '合成兜3']]
check('227 重現：p1 DKBO2 今天清單（球石 / 薄的皮 …）修後每店全部選得到、順序單調', sim_role_items(P1_DKBO2) == [], str(sim_role_items(P1_DKBO2)))
_main_cache = Path(HERE).parents[1] / '.cache'
if not _main_cache.exists():
    _gc = subprocess.run(['git', 'rev-parse', '--git-common-dir'], capture_output=True, text=True, cwd=str(HERE)).stdout.strip()
    _main_cache = (Path(_gc) if Path(_gc).is_absolute() else Path(HERE) / _gc).resolve().parent / 'tools' / '.cache'
_n = 0
for _r in ('DKBO', 'DKBO2', 'DKBO3', 'DKBO4', 'DKBO5'):
    _f = _main_cache / f'daily-{_r}.json'
    if _f.exists():
        _it = json.load(open(_f, encoding='utf-8')).get('items')
        if _it and all(all(x for x in row) for row in _it):
            _n += 1
            check(f'今天 {_r} 清單：店內順序單調 + 全部選得到', sim_role_items(_it) == [], str(sim_role_items(_it)))
print(f'  （今天進度檔實際模擬 {_n} 人）')

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
        self.rpos = {r: (1000, 0, 0) for r in roles}   # 每人位置（組隊中隊長移動 = 全隊一起；解散後只動當前角色）
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

    @property
    def map(self):
        return self.rpos[self.cur][0]

    @map.setter
    def map(self, m):
        """移動：組隊中且當前是隊長 → 全隊同一張地圖；否則只有當前角色"""
        who = self.roles if (self.team and self.cur == self.roles[0]) else [self.cur]
        for r in who:
            self.rpos[r] = (m, 0, 0)


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
    def pos(self): return self.W.rpos[self.W.cur]
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
        assert not self.W.panel and not self.W.shop, '切回隊長時面板 / 商店還開著'
        self.W.cur = role
        return 0

    def close_panels(self):
        self.L('close_panels')
        self.W.panel = False
        self.W.shop = None
        return []

    def switch(self, role):
        assert not self.W.panel and not self.W.shop, '切角色時面板 / 商店還開著'
        self.W.cur = role
        self.L('switch', role)
        return self.inj.get('switch_rc', 0) if self.inj.get('switch_role') == role else 0

    @property
    def inj(self): return self.W.inj

    def form(self):
        W = self.W
        lead = W.roles[0]
        self.L('form', W.rpos[lead][0])
        if W.team:
            return 0                                           # 已組好：不點
        if self.inj.get('no_cross_pull') and any(W.rpos[r][0] != W.rpos[lead][0] for r in W.roles):
            return 43                                          # 隊員在別張地圖拉不過來（假設情境）
        lm, lx, ly = W.rpos[lead]
        for r in W.roles[1:]:
            W.rpos[r] = (lm, 38, 47) if (lm, lx, ly) == (1005, 38, 40) else (lm, 0, 0)
        W.team = True
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

    def hosp_solo(self):
        W = self.W
        assert W.cur == W.roles[0], '走醫院的不是隊長'
        assert not W.panel and not W.shop
        self.L('hosp_solo', W.team)
        W.map = 1005
        W.rpos[W.cur] = (1005, 38, 40)
        if W.team:
            for r in W.roles[1:]:
                W.rpos[r] = (1005, 38, 47)
        return True

    def talk(self, npc, at, then=''): return True

    # -- 委託面板 --
    def daily_open(self, may_walk=False):
        W = self.W
        assert W.map == 1005 and W.team, f'開委託面板：不在醫院或沒組隊（{W.rpos[W.cur]} team={W.team}）'
        assert may_walk == (W.cur == W.roles[0]), '只有隊長可以走'
        self.L('daily_open', W.cur, W.rpos[W.cur])
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

    def peek_item(self, k, panel=None):
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

    def shop_set_qty(self, q, start=None):
        if self.inj.get('plus_unread') and q > 1:             # 模擬 ＋ 到 q 讀不回（數字沒樣板）→ 已退回起點、回 False
            self.L('plus_unread', q)
            return False
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

    def shop_chunks(self, q):
        # 預設一次買完；inj chunks=True → 用真的 shopkit.qty_chunks（種子樣板只認得 1 3 → 分次）
        return shopkit.qty_chunks(q) if self.inj.get('chunks') else [q]

    def shop_buy_checked(self, n):
        before = self.W.qty
        self.shop_buy()                                        # 走 self.shop_buy（情境 8 會換掉它）
        got = self.inj.get('verdict_once')
        if got and got[0] == (self.W.cur, self.W.shop_item):
            self.inj.pop('verdict_once')
            return got[1]
        if self.W.qty == 0:
            return 'zeroish' if self.inj.get('zeroish') else 'bought'
        return 'not_bought' if self.W.qty == before else 'unknown'

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

# ---------------- 情境 13：組隊不解散、隊長一人走 38,40（使用者 2026-10-17 新定案）----------------
H = 1005
WP = [(31, 60), (36, 60), (38, 55), (38, 48), (38, 40)]
for name, pos, want_v, want in [
    ('村裡（1000:74,72）→ 先進醫院、走全部 waypoint', (1000, 74, 72), True, WP),
    ('位置讀不到 → 同不在醫院', None, True, WP),
    ('醫院入口 25,65 → 全部 waypoint', (H, 25, 65), False, WP),
    ('醫院 26,64 → 全部', (H, 26, 64), False, WP),
    ('31,60 已到 → 不回頭、從 36,60 起', (H, 31, 60), False, WP[1:]),
    ('35,55（卡點）→ 從 38,55 起，不回 31,60', (H, 35, 55), False, WP[2:]),
    ('38,55 → 38,48、38,40', (H, 38, 55), False, WP[3:]),
    ('38,48 → 只剩 38,40', (H, 38, 48), False, WP[4:]),
    ('38,46 → 只剩 38,40', (H, 38, 46), False, WP[4:]),
    ('38,40 站位 → 不走', (H, 38, 40), False, []),
    ('NPC 3 格內 40,44 → 不走', (H, 40, 44), False, []),
]:
    v, r = daily.hosp_route(pos)
    check(f'hosp_route {name}', v == want_v and r == want, f'{v} {r}')
check('at_stand：38,40 / NPC 3 格內 是；38,47（隊員落點）/ 村子 / None 不是',
      daily.at_stand((H, 38, 40)) and daily.at_stand((H, 40, 44)) and not daily.at_stand((H, 38, 47)) and not daily.at_stand((1000, 38, 40)) and not daily.at_stand(None))

import layout  # noqa: E402
layout.prime(uikit.LAYOUT)                   # import walk 時不問遊戲版面（不呼叫 powershell）
import walk as _real_walk  # noqa: E402  只用純函式（screen / npc_screen / safe）
check('HOSP_CLICK_ROUTE = 25,65 起逐段 walk.screen 位移（play-p1-route：747,157 → … → 459,226）',
      daily.HOSP_CLICK_ROUTE == [_real_walk.screen(b[0] - a[0], b[1] - a[1]) for a, b in zip([daily.HOSP_ENTRY] + WP[:-1], WP)]
      == [(747, 157), (875, 295), (619, 249), (491, 249), (459, 226)], str(daily.HOSP_CLICK_ROUTE))
import heal as _real_heal  # noqa: E402
check('VILLAGE_CLICK_ROUTE = 92,99 起 heal.VILLAGE_FAST 逐段位移（與 heal.walk_village 同路）',
      daily.VILLAGE_CLICK_ROUTE == [_real_walk.screen(b[0] - a[0], b[1] - a[1]) for a, b in zip([_real_heal.VILLAGE_START] + _real_heal.VILLAGE_FAST[:-1], _real_heal.VILLAGE_FAST)],
      str(daily.VILLAGE_CLICK_ROUTE))
_rs = daily.route_seq('click 1215 18; wait 100', True, 'SIG').split('; ')
check('route_seq 整串：PRIMER → 村子 5 段（段 2 起 ifok、最後 waitpix 醫院特徵）→ ifok PRIMER → 醫院 5 段全 ifok',
      _rs[:3] == ['click 1215 18', 'wait 100', 'click 459 456'] and _rs[3] == 'waitstill 4000' and _rs[4] == 'ifok click 427 249'
      and _rs[11] == 'ifok waitpix 5000 SIG 25' and _rs[12:14] == ['ifok click 1215 18', 'ifok wait 100']
      and _rs[14] == 'ifok click 747 157' and _rs[-2:] == ['ifok click 459 226', 'ifok waitstill 4000'] and len(_rs) == 2 + 10 + 2 + 10, str(_rs))
_rs = daily.route_seq('click 1215 18; wait 100', False).split('; ')
check('route_seq 醫院段：PRIMER → 747,157（第 1 段沒 ifok）→ 段 2 起 ifok', _rs[:4] == ['click 1215 18', 'wait 100', 'click 747 157', 'waitstill 4000'] and _rs[4] == 'ifok click 875 295' and len(_rs) == 12, str(_rs))
check('NPC_FALLBACK_XY = npc_screen(委託 NPC, 38,47) = 651,197', daily.NPC_FALLBACK_XY == _real_walk.npc_screen(daily.DAILY_NPC, daily.MEMBER_SPOT) == (651, 197))
check('站位 38,40 點 NPC 的點位不在 UI 上', _real_walk.safe(*_real_walk.npc_screen(daily.DAILY_NPC, daily.HOSP_STAND)))


class _Mod:
    pass


class FakeGeo:
    """Tools.hosp_solo / daily_open 用的假 walk / heal 模組：位置隨動作改變，記下每個動作"""

    def __init__(self, pos, click_to=None, stuck_step=False):
        self.p, self.log, self.click_to, self.stuck_step = pos, [], click_to, stuck_step
        w, h = _Mod(), _Mod()
        w.PRIMER = 'click 1215 18; wait 100'
        w.wait_pos = lambda tries=6, want_map=None, gap=0.5: self.p
        w.screen, w.npc_screen, w.safe = _real_walk.screen, _real_walk.npc_screen, _real_walk.safe
        w.gui = self.gui
        w.walk_to = self.walk_to
        w.step_to = self.step_to
        h.VILLAGE_START = (92, 99)
        h.SIG_HUD, h.SIG_HOSPITAL = 'HUD', 'HOSP'
        h.walk_village = self.walk_village
        self.walk, self.heal = w, h

    def gui(self, *a, note=''):
        self.log.append(('seq', a[1].count('waitstill'), a[1].count('click 1215 18')))
        if self.click_to:
            self.p = self.click_to.pop(0) if isinstance(self.click_to, list) else self.click_to
        return ''

    def walk_to(self, m, x, y, exit_map=None):
        self.log.append(('walk_to', m, x, y, exit_map))
        self.p = {(1009, 10, 25): (1000, 106, 91), (1000, 81, 66): (1005, 26, 65)}.get((m, x, y), (exit_map or m, x, y))

    def step_to(self, m, x, y, exit_map=None):
        self.log.append(('step', m, x, y))
        if self.stuck_step:
            raise RuntimeError('走不動')
        self.p = (m, x, y)

    def walk_village(self):
        self.log.append(('village',))
        self.p = (1005, 26, 65)

    def __enter__(self):
        self.old = (sys.modules.get('walk'), sys.modules.get('heal'))
        sys.modules['walk'], sys.modules['heal'] = self.walk, self.heal
        return self

    def __exit__(self, *e):
        for k, v in zip(('walk', 'heal'), self.old):
            if v is None:
                sys.modules.pop(k, None)
            else:
                sys.modules[k] = v


class GeoTools(daily.Tools):
    def __init__(self, geo):
        self.geo = geo

    def to_town(self):
        self.geo.log.append('to_town')
        self.geo.p = (1000, 92, 99)
        return True


for name, pos, click_to, want in [
    ('傳送落點 92,99 → 一個 seq 走完（村子 4 waitstill + 醫院 5、PRIMER 2 次）', (1000, 92, 99), (H, 38, 40), [('seq', 9, 2)]),
    ('整串沒進醫院（停在村子 84,81）→ walk_to 出口 → 醫院段 5 段', (1000, 92, 99), [(1000, 84, 81), (H, 38, 40)],
     [('seq', 9, 2), ('walk_to', 1000, 81, 66, 1005), ('seq', 5, 1)]),
    ('便利商店 1009 → 走出口回村 → walk_to 村子出口 → 醫院段', (1009, 25, 17), (H, 38, 40),
     [('walk_to', 1009, 10, 25, 1000), ('walk_to', 1000, 81, 66, 1005), ('seq', 5, 1)]),
    ('瑪麗娜絲 2009 → 傳送薩姆吉爾 → 一個 seq 走完', (2009, 10, 25), (H, 38, 40), ['to_town', ('seq', 9, 2)]),
    ('已在站位 → 不動', (H, 38, 40), None, []),
    ('醫院入口 25,65 → 醫院段', (H, 25, 65), (H, 38, 40), [('seq', 5, 1)]),
    ('入口固定點擊沒到（停在 38,48）→ hosp_route 逐段 step_to', (H, 26, 65), (H, 38, 48), [('seq', 5, 1), ('step', H, 38, 40)]),
    ('醫院內別處（35,55）→ 不點固定路線、直接逐段', (H, 35, 55), None, [('step', H, 38, 55), ('step', H, 38, 48), ('step', H, 38, 40)]),
]:
    with FakeGeo(pos, click_to) as g:
        ok = GeoTools(g).hosp_solo()
    check(f'Tools.hosp_solo {name}', ok and g.log == want, f'{ok} {g.log}')
with FakeGeo((H, 35, 55), stuck_step=True) as g:
    ok = GeoTools(g).hosp_solo()
check('Tools.hosp_solo 逐段也走不動 → False（不 raise）', ok is False, str(g.log))

# daily_open：不走路直接點（隊員）
_keep_ui = (uikit.is_open, uikit.gui, uikit.sleep)


def open_case(pos, opens_after=1, may_walk=False):
    clicks = []
    st = {'n': 0}
    uikit.is_open = lambda p: st['n'] >= opens_after
    uikit.gui = lambda *a, note='': clicks.append(a[1].split(';')[0]) or ''
    uikit.sleep = lambda s: None

    def count_gui(*a, note=''):
        clicks.append(a[1].split(';')[0])
        st['n'] += 1
        return ''
    uikit.gui = count_gui
    with FakeGeo(pos) as g:
        ok = GeoTools(g).daily_open(may_walk=may_walk)
    uikit.is_open, uikit.gui, uikit.sleep = _keep_ui
    return ok, clicks, g.log


ok, clicks, lg = open_case((H, 38, 47))
check('daily_open 隊員在 38,47：點 651,197 一次就開、沒走路', ok and clicks == ['click 651 197'] and not any(a[0] == 'step' for a in lg), f'{ok} {clicks} {lg}')
ok, clicks, lg = open_case((H, 38, 47), opens_after=2)
check('daily_open 第一下被吃 → 再點一次（共 2 次）', ok and clicks == ['click 651 197', 'click 651 197'], f'{ok} {clicks}')
ok, clicks, lg = open_case((H, 38, 47), opens_after=9)
check('daily_open 點 2 次都沒開 → False（不點第 3 次）', not ok and len(clicks) == 2, f'{ok} {clicks}')
ok, clicks, lg = open_case(None)
check('daily_open 座標讀不到 → 用 38,47 的 651,197', ok and clicks == ['click 651 197'], f'{ok} {clicks}')
ok, clicks, lg = open_case((H, 38, 40), may_walk=True)
check('daily_open 隊長在 38,40：點 npc_screen(38,40)、不走', ok and clicks == ['click %d %d' % _real_walk.npc_screen((41, 42), (38, 40))] and not lg, f'{ok} {clicks} {lg}')
ok, clicks, lg = open_case((H, 38, 54), may_walk=True)
check('daily_open 隊長點位落在 UI 上（38,54）→ 先 step_to 38,40 再點', ok and lg == [('step', H, 38, 40)] and clicks == ['click %d %d' % _real_walk.npc_screen((41, 42), (38, 40))], f'{ok} {clicks} {lg}')
ok, clicks, lg = open_case((H, 38, 54))
check('daily_open 隊員點位落在 UI 上 → 不走、改點 651,197', ok and not lg and clicks == ['click 651 197'], f'{ok} {clicks} {lg}')
ok, clicks, lg = open_case((1000, 92, 99))
check('daily_open 隊員不在醫院 → False、不點', not ok and clicks == [], f'{ok} {clicks}')

# 整段流程：組隊不解散、醫院段隊長一人走、店內各自買
fresh_dir()
W = scenario()
rc, out, _ = go(W)
lg = W.log
names = [a[0] for a in lg]
check('新流程全程 rc 0、5 人 5/5', rc == 0 and all(W.reward[r] == 5 for r in W.roles), f'{rc} {out[-300:]}')
first_open = names.index('daily_open')
check('prep / read：讀清單前沒有解散；hosp_solo 一次 + 組隊後才開面板',
      'disband' not in names[:first_open] and names[:first_open].count('hosp_solo') == 1 and names.index('hosp_solo') < max(i for i in range(first_open) if names[i] == 'form'), str(names[:first_open]))
opens = [a for a in lg if a[0] == 'daily_open']
check('隊員開面板都站 38,47（不走路）、隊長站 38,40', all(a[2] == ((1005, 38, 40) if a[1] == 'DKBO' else (1005, 38, 47)) for a in opens), str(opens[:6]))
check('醫院段（read / mid / final）各 hosp_solo 一次、共 3 次；mid / final 的 hosp_solo 是單人（隊伍已解散）',
      [a[1] for a in lg if a[0] == 'hosp_solo'] == [True, False, False], str([a for a in lg if a[0] == 'hosp_solo']))
check('解散只在便利店段（sam / fish 各一次）', names.count('disband') == 2, str(names.count('disband')))
dis_i = [i for i, n in enumerate(names) if n == 'disband']
check('每次解散後才有人進店買（shop_enter 都在解散後、下一次組隊前）',
      all(any(dis_i[k] < i for k in range(len(dis_i))) for i, n in enumerate(names) if n == 'shop_enter'))
check('每次切角色前都先 close_panels', all(names[i - 1] == 'close_panels' for i, n in enumerate(names) if n == 'switch'))
check('finish：已組著 → form 不點、直接 grind', names[-1] == 'form' and _.grind_called == 1, str(names[-3:]))

# pull 拉不過來（假設情境）→ 223 帶 --regroup gather 提示；--regroup gather 完成
fresh_dir()
W = scenario()
W.inj['no_cross_pull'] = True
rc, out, _ = go(W)
check('pull：隊員在 1009 拉不過來 → 223、訊息提示 --regroup gather', rc == 223 and '--regroup gather' in out, f'{rc} {out[-300:]}')
fresh_dir()
W = scenario()
W.inj['no_cross_pull'] = True
rc, out, _ = go(W, regroup='gather')
names = [a[0] for a in W.log]
check('--regroup gather：先在店內組隊再帶隊走 → 完成', rc == 0 and all(W.reward[r] == 5 for r in W.roles) and [a[1] for a in W.log if a[0] == 'hosp_solo'] == [True, True, True], f'{rc} {out[-300:]}')
rc, out, _ = go(scenario(), regroup='nope')
check('--regroup 不是 pull / gather → 220', rc == 220)

# 續跑：漁村買到一半斷（隊伍是散的）→ 重跑 into_shop 先組隊再解散、接著買；醫院段斷（隊伍組著）→ form 不點
fresh_dir()
W = scenario()
W.inj['boom_enter'] = ('DKBO4', 2823)
T = FakeTools(W)
try:
    go(W, T)
except RuntimeError:
    pass
check('漁村 / 薩村買到一半斷：當下隊伍是散的', not W.team)
n0 = len(W.log)
rc, out, _ = go(W, T)
tail = [a[0] for a in W.log[n0:]]
check('續跑：先組隊（拉回）→ 解散 → 接著買 → 完成', rc == 0 and tail.index('form') < tail.index('disband') < tail.index('shop_enter') and all(W.reward[r] == 5 for r in W.roles), f'{rc} {tail[:12]}')

# ---------------- 情境：數量框只認得 1 3（真 qty_chunks 分次買）/ 買後歸 0 但 0 沒樣板（zeroish）/ 讀不出 ----------------
fresh_dir()
W = scenario()
T = FakeTools(W)
T.inj['chunks'] = True
rc, out, _ = go(W, T)
nbuy = sum(1 for a in W.log if a[0] == 'buy')
check('分次買（7 → 3+3+1 等）：照樣 5/5、總共買 160 個、按購買次數變多', rc == 0 and W.bought_n == 160 and all(W.reward[r] == 5 for r in W.roles) and nbuy > 5 * 30, f'{rc} {nbuy} {out[-300:]}')
check('分次買每次數量的位數都只有 1 / 3', all(set(str(a[3])) <= {'1', '3'} for a in W.log if a[0] == 'buy'), str([a[3] for a in W.log if a[0] == 'buy'][:10]))
fresh_dir()
W = scenario()
T = FakeTools(W)
T.inj['zeroish'] = True
rc, out, _ = go(W, T)
check('買後數量框是認不出的字（zeroish）→ 視為買到、背包核對通過 → 完成', rc == 0 and all(W.reward[r] == 5 for r in W.roles), f'{rc} {out[-300:]}')
fresh_dir()
W = scenario()
T = FakeTools(W)
T.inj['verdict_once'] = None                                              # 第一次購買回 unknown
_orig_sb = T.shop_buy


def _sb():
    if T.inj.get('verdict_once') is None and W.shop_item:
        T.inj['verdict_once'] = ((W.cur, W.shop_item), 'unknown')
    _orig_sb()


T.shop_buy = _sb
rc, out, _ = go(W, T)
first = next(a for a in W.log if a[0] == 'buy')
check('買後數量框讀不出（unknown）→ 227、該項不重買', rc == 227 and sum(1 for a in W.log if a[0] == 'buy' and a[1:3] == first[1:3]) == 1, f'{rc} {out[-300:]}')

fresh_dir()
W = scenario()
T = FakeTools(W)
T.inj['plus_unread'] = True                                               # ＋ 到 >1 讀不回 → 退回每次買 1 個
rc, out, _ = go(W, T)
buys = [a for a in W.log if a[0] == 'buy']
check('＋ 讀不回 → 每次買 1 個、買 n 次：照樣 5/5、總共買 160 個、每次數量都是 1', rc == 0 and W.bought_n == 160 and all(W.reward[r] == 5 for r in W.roles) and all(a[3] == 1 for a in buys), f'{rc} {out[-300:]}')

# ---------------- 結尾 ----------------
check("0 次 powershell（全測試）", not PS_CALLS, str(PS_CALLS[:3]))
print('ALL PASS' if not fails else f'FAILED {fails}')
sys.exit(1 if fails else 0)
