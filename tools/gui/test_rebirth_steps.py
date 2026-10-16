#!/usr/bin/env python3
"""stuckrecover.py / catchbuy.py / rebirth_steps.py 離線測試（完全不碰遊戲）。
用法：uv run --no-project python tools/gui/test_rebirth_steps.py"""
import contextlib
import io
import os
import sys
import tempfile
from pathlib import Path

os.environ.setdefault('PSA_LAYOUT', '2880x1659')
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import testenv  # noqa: E402,F401
import catchbuy  # noqa: E402
import rebirth_steps as rs  # noqa: E402
import stuckrecover as sr  # noqa: E402
import uikit  # noqa: E402

fails = 0


def check(name, cond, extra=''):
    global fails
    print(('PASS' if cond else 'FAIL'), name, extra)
    if not cond:
        fails += 1


def quiet(fn, *a, **k):
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        return fn(*a, **k)


# ================= stuckrecover =================
check('is_stuck：19 / 42 才算', sr.is_stuck(19) and sr.is_stuck(42) and not sr.is_stuck(0) and not sr.is_stuck(37) and not sr.is_stuck(31))
check('allowed：每階段 / 任務最多 2 次', sr.allowed(0) and sr.allowed(1) and not sr.allowed(2) and sr.RELOGIN_MAX == 2)
logs = []
check('relogin_team：0 → ok', sr.relogin_team(lambda: 0, lambda: 1 / 0, logs.append) == ('ok', 0))
check('relogin_team：105 → 重組成功 → ok；重組失敗 → regroup_fail；重組遇 9 / 10 → halt',
      sr.relogin_team(lambda: 105, lambda: 0, logs.append) == ('ok', 105)
      and sr.relogin_team(lambda: 105, lambda: 43, logs.append) == ('regroup_fail', 43)
      and sr.relogin_team(lambda: 105, lambda: 9, logs.append) == ('halt', 9)
      and sr.relogin_team(lambda: 105, lambda: 10, logs.append) == ('halt', 10))
check('relogin_team：9 / 10 → halt 原碼；其他碼 → relogin_fail；重組函式不被呼叫',
      sr.relogin_team(lambda: 9, lambda: 1 / 0, logs.append) == ('halt', 9) and sr.relogin_team(lambda: 10, lambda: 1 / 0, logs.append) == ('halt', 10)
      and sr.relogin_team(lambda: 104, lambda: 1 / 0, logs.append) == ('relogin_fail', 104) and sr.relogin_team(lambda: 11, lambda: 1 / 0, logs.append) == ('relogin_fail', 11))
import questrun  # noqa: E402
check('questrun 與 rebirth 共用同一份常數', questrun.RELOGIN_MAX == sr.RELOGIN_MAX and questrun.RELOGIN_TEAM == sr.RELOGIN_TEAM)

# ================= catchbuy =================
check('parse_money：依 x 排序、去逗號', catchbuy.parse_money([('0', 520, 23), ('3,264,500', 335, 23)]) == (3264500, 0) and catchbuy.parse_money([]) == (None, None))
check('parse_money：多組 OCR 重複的石幣（x 差 < 80）合併、活力 x≈808 不當鑽石、鑽石讀不到 = None（2026-10-13 三轉誤停）',
      catchbuy.parse_money([('4,884,500', 335, 23), ('4,884,500', 340, 23), ('346', 808, 23)]) == (4884500, None)
      and catchbuy.parse_money([('4,884,500', 335, 23), ('0', 560, 23), ('346', 808, 23)]) == (4884500, 0))
check('parse_count_zero：「可抓捕數:」後沒數字 + zero_ok → 0（2026-10-13 三轉 163）；沒 zero_ok → None；有數字照讀',
      catchbuy.parse_count_zero('自動抓寵自動存倉庫可抓捕數:+', True) == 0 and catchbuy.parse_count_zero('自動抓寵自動存倉庫可抓捕數:+', False) is None
      and catchbuy.parse_count_zero('可抓捕數：2 +', True) == 2)
check('parse_count_zero：沒讀到「可抓捕數」字樣 → None（不猜 0）', catchbuy.parse_count_zero('自動抓寵 自動存倉庫', True) is None and catchbuy.parse_count_zero('', True) is None)


class Shop:
    """假外掛 + 假石幣：每按 +1 扣 cost；可注入異常"""
    def __init__(self, stone=3000000, diamond=0, count=0, cost=50000, dia_drop=0, rc=0, noop=False):
        self.stone, self.diamond, self.count, self.cost, self.dia_drop, self.rc, self.noop = stone, diamond, count, cost, dia_drop, rc, noop
        self.presses = 0

    def money(self):
        return self.stone, self.diamond

    def press(self, role, limit=None, min_before=None):
        if self.rc:
            return self.rc, self.count, None
        if limit is not None and self.count >= limit:
            return 0, self.count, self.count
        b = self.count
        if min_before is not None and b < min_before:
            return catchbuy.EXIT_BAIT, b, None
        self.presses += 1
        if not self.noop:
            self.count += 1
        self.stone -= self.cost
        self.diamond -= self.dia_drop
        return 0, b, self.count


sh = Shop()
k, msg, rc, bought = catchbuy.buy('DKBO2', 5, sh.money, sh.press, lambda m: None)
check('buy 5 次：ok、石幣少 250,000、鑽石不變、紀錄 5 筆', k == 'ok' and sh.stone == 2750000 and sh.diamond == 0 and len(bought) == 5 and sh.count == 5)
sh = Shop(count=3)
k, msg, rc, bought = catchbuy.buy_to('DKBO2', 5, sh.money, sh.press, lambda m: None)
check('buy_to：已有 3 → 只按 2 次；已夠就不再按', k == 'ok' and sh.presses == 2 and sh.count == 5 and catchbuy.buy_to('DKBO2', 5, sh.money, sh.press, lambda m: None)[0] == 'ok' and sh.presses == 2)
sh = Shop(stone=120000)
k, msg, rc, bought = catchbuy.buy_to('DKBO2', 5, sh.money, sh.press, lambda m: None)
check('石幣不讀、不擋：石幣少也照按', k == 'ok' and sh.count == 5)
sh = Shop(cost=10000)
k, msg, *_ = catchbuy.buy('DKBO2', 1, sh.money, sh.press, lambda m: None)
check('石幣扣多少不檢查', k == 'ok')
sh = Shop(dia_drop=5)
k, msg, *_ = catchbuy.buy('DKBO2', 1, sh.money, sh.press, lambda m: None)
check('鑽石有變 → fail（鐵則 3）', k == 'fail' and '鑽石' in msg)
sh = Shop(noop=True)
k, msg, *_ = catchbuy.buy('DKBO2', 1, sh.money, sh.press, lambda m: None)
check('可抓捕數沒 +1 → fail', k == 'fail' and '不是 +1' in msg)
sh = Shop(rc=4)
k, msg, rc_, _ = catchbuy.buy('DKBO2', 1, sh.money, sh.press, lambda m: None)
check('press 回非 0 → pass（原碼）', k == 'pass' and rc_ == 4)
k, msg, *_ = catchbuy.buy('DKBO2', 1, lambda: (None, 0), Shop().press, lambda m: None)
check('讀不到石幣不擋（鑽石讀得到就照按）', k == 'ok')
sh = Shop()
k, msg, *_ = catchbuy.buy('DKBO2', 1, lambda: (None, None), sh.press, lambda m: None)
check('按前讀不到鑽石 → fail、不按（2026-10-15：鑽石檢查要能生效）', k == 'fail' and sh.presses == 0 and '讀不到鑽石' in msg, msg)
sh = Shop()
_seq = iter([(None, '0'), (None, None)])
k, msg, *_ = catchbuy.buy('DKBO2', 1, lambda: next(_seq), sh.press, lambda m: None)
check('按後讀不到鑽石 → fail（已按 1 次）', k == 'fail' and sh.presses == 1 and '讀不到鑽石' in msg, msg)
_seq = iter([(None, 'px:aaa'), (None, 'px:bbb')])
k, msg, *_ = catchbuy.buy('DKBO2', 1, lambda: next(_seq), Shop().press, lambda m: None)
check('鑽石點陣指紋前後不同 → fail（鑽石有變）', k == 'fail' and '有變' in msg, msg)
sh = Shop(count=3)
k, msg, rc, bought = catchbuy.buy_to('DKBO5', 5, sh.money, sh.press, lambda m: None, min_before=3)
check('誘餌不夠只買缺額：背包 3 個、要 5 → 外掛顯示 3、只按 2 次、扣 100,000', k == 'ok' and sh.presses == 2 and sh.count == 5 and sh.stone == 3000000 - 2 * 50000 and len(bought) == 2)
sh = Shop(count=0)
k, msg, rc, bought = catchbuy.buy_to('DKBO5', 5, sh.money, sh.press, lambda m: None, min_before=3)
check('外掛顯示 0 < 背包誘餌 3（不能相加）→ fail、一次都不按', k == 'fail' and sh.presses == 0 and '不能相加' in msg)
sh = Shop(count=3)
k, msg, rc, bought = catchbuy.buy_to('DKBO5', 5, lambda: (None, 0), sh.press, lambda m: None, min_before=3)
check('讀不到石幣不擋（誘餌不夠情境）', k == 'ok' and sh.presses == 2)
# 鑽石點陣（2026-10-15：鑽石 0 時 OCR 漏讀單獨的「0」→ 一路 None；改讀像素）
_Z = ['0' * 10 + r.replace('.', '0').replace('#', '1') + '0' * 8 for r in catchbuy.DIA_ZERO]
_rows = ['0' * 25] * 5 + _Z + ['0' * 25] * 4
check('dia_from_rows：單獨「0」的字形（ui-log 截圖量的）→ \'0\'；位置平移也一樣', catchbuy.dia_from_rows(_rows) == '0'
      and catchbuy.dia_from_rows(['0' * 3 + r[10:] for r in _rows]) == '0')
check('dia_from_rows：沒有白字 → None；別的形狀 → px:指紋（同圖同值、不同圖不同值）', catchbuy.dia_from_rows(['0' * 25] * 22) is None and catchbuy.dia_from_rows([]) is None
      and catchbuy.dia_from_rows(['0110', '1111']).startswith('px:') and catchbuy.dia_from_rows(['0110', '1111']) == catchbuy.dia_from_rows(['00110', '01111'])
      and catchbuy.dia_from_rows(['0110', '1111']) != catchbuy.dia_from_rows(['0110', '1101']))
_seq = iter([(None, 'px:a'), (None, 'px:a')])
check('read_dia_stable：字串讀值兩次一致才採用', catchbuy.read_dia_stable(lambda: next(_seq)) == 'px:a')
seq = iter([(0, 0), (6720000, 0), (6720000, 0)])
check('石幣讀到 0 → 重讀、連續兩次一致才採用（2026-10-15 單次讀成 0 → 163）', catchbuy.read_money_stable(lambda: next(seq), lambda s: None) == (6720000, 0))
seq = iter([(6720000, 0), (6720500, 0), (6720000, 0), (6720500, 0), (6720000, 0)])
check('兩次不一致一直讀不穩 → (None, None)', catchbuy.read_money_stable(lambda: next(seq), lambda s: None) == (None, None))
check('一直讀 0 / None → (None, None)（不買）', catchbuy.read_money_stable(lambda: (0, 0), lambda s: None) == (None, None) and catchbuy.read_money_stable(lambda: (None, None), None) == (None, None))
seq = iter([(6720000, 0), (6720000, 5)])
check('石幣一致但鑽石不一致 → 鑽石 None（不當 0）', catchbuy.read_money_stable(lambda: next(seq), None) == (6720000, None))
seq = iter([(None, 0), (None, 0)])
check('read_dia_stable：兩次一致才採用', catchbuy.read_dia_stable(lambda: next(seq), None) == 0)
seq = iter([(1, 0), (1, 5), (1, 0)])
check('read_dia_stable：不一致 / 讀不到 → None', catchbuy.read_dia_stable(lambda: next(seq), None) is None and catchbuy.read_dia_stable(lambda: (1, None), None) is None)

# ---- 可抓捕數讀值（2026-10-16 p2 DKBO7：OCR 把 20 讀成 2 → 以為 2 < 5 按了「+」→ 讀「2 → 21」判非 +1 停手，白花 50,000）----
import json  # noqa: E402
import ass  # noqa: E402
import numglyph  # noqa: E402
import rebirth_pets as rp  # noqa: E402
_seed = json.loads((HERE / 'fixtures' / 'num_glyph_tpl.json').read_text(encoding='utf-8'))['ass']
_BG, _INK = (221, 221, 219), (30, 30, 30)


def _ass_px(n):
    """外掛捉寵設置可抓捕數框：用種子字形畫出 n（字距 2 px，y 308 起，同實機位置）"""
    bx, by, bw, bh = numglyph.ASS_COUNT_BOX
    pic = {(bx + i, by + j): _BG for j in range(bh) for i in range(bw)}
    x = 1200
    for ch in str(n):
        g = _seed[ch][0]
        for j, r in enumerate(g):
            for i, c in enumerate(r):
                if c == '1':
                    pic[(x + i, 308 + j)] = _INK
        x += len(g[0]) + 2
    return pic


class Ass:
    """假外掛面板：可抓捕數 count（像素照 count 畫），OCR 固定讀 ocr_txt（模擬掉字）；點「+」→ count + 1"""
    def __init__(self, count, ocr_txt):
        self.count, self.ocr_txt, self.clicks = count, ocr_txt, []

    def px(self, pts):
        pic = _ass_px(self.count)
        return [pic.get(p, _BG) for p in pts]

    def gui(self, *a, note=''):
        if a and a[0] == 'seq' and 'click 1295 315' in a[1]:
            self.clicks.append(note)
            self.count += 1
        return ''


_keep = (uikit.px, uikit.gui, uikit.sleep, rp.ocr_lines, rp.Tools._ass_open, ass.panel_open, ass.close_panel)
try:
    rp.Tools._ass_open = lambda self, role, tab: 0
    ass.panel_open, ass.close_panel, uikit.sleep = (lambda: True), (lambda: True), (lambda s: None)
    fa = Ass(20, '自動抓寵 自動存倉庫 可抓捕數: 2 +')
    uikit.px, uikit.gui = fa.px, fa.gui
    rp.ocr_lines = lambda box, *o: [(fa.ocr_txt or f'可抓捕數: {fa.count} +', 0, 0)]      # ocr_txt None = OCR 讀對
    r = quiet(catchbuy.press_plus, 'DKBO7', 5, 0)
    check('外掛顯示 20、OCR 讀成「2」：像素字形讀 20 ≥ 5 → 不按「+」（10-16 p2 白花 50,000 的情境）', r == (0, 20, 20) and not fa.clicks, f'{r} {fa.clicks}')
    fa = Ass(20, '可抓捕數: 2 +')
    uikit.px, uikit.gui = fa.px, fa.gui
    r = quiet(catchbuy.press_plus, 'DKBO7', 25, 0)
    check('要 25：按 1 次，讀 20 → 21（不是「2 → 21」）', r == (0, 20, 21) and len(fa.clicks) == 1, f'{r}')
    k, msg, rc_, bought = catchbuy.buy_to('DKBO7', 21, lambda: (None, '0'), lambda role, lim=None, mb=None: quiet(catchbuy.press_plus, role, lim, mb),
                                          lambda m: None, min_before=0)
    check('buy_to 21：已是 21 → 不再按、ok', k == 'ok' and len(fa.clicks) == 1, msg)
    # 樣板認不全（ass 字型清空）→ 只能靠 OCR：OCR「2」位數 ≠ 像素 2 字 → 讀不出 → 不按
    _keep_tpl = numglyph.load_tpl
    _empty = {k: ({} if k == 'ass' else v) for k, v in _keep_tpl().items()}
    numglyph.load_tpl = lambda reload=False: _empty
    fa = Ass(20, '可抓捕數: 2 +')
    uikit.px, uikit.gui = fa.px, fa.gui
    r = quiet(catchbuy.press_plus, 'DKBO7', 25, 0)
    check('樣板認不出 + OCR 掉字「2」→ 按前讀不出（None）→ EXIT_BAIT、不按', r[0] == catchbuy.EXIT_BAIT and r[1] is None and not fa.clicks, f'{r}')
    fa.ocr_txt = None
    r = quiet(catchbuy.press_plus, 'DKBO7', 25, 0)
    check('樣板認不出 + OCR 讀對 20（位數 = 2 字）→ 採用、按 1 次、20 → 21', r == (0, 20, 21) and len(fa.clicks) == 1, f'{r}')
    numglyph.load_tpl = _keep_tpl
    numglyph.load_tpl(reload=True)
finally:
    uikit.px, uikit.gui, uikit.sleep, rp.ocr_lines, rp.Tools._ass_open, ass.panel_open, ass.close_panel = _keep
k, msg, *_ = catchbuy.buy('DKBO2', 1, lambda: (None, '0'), lambda r, l=None, m=None: (0, 20, None), lambda m: None)
check('按後可抓捕數讀值不可信（None）→ fail「讀值不可信」（不當成非 +1 的數字）', k == 'fail' and '不可信' in msg, msg)
for _s in json.loads((HERE / 'fixtures' / 'numglyph_samples.json').read_text(encoding='utf-8'))['samples']:
    if _s['kind'] != 'ass':
        continue
    _x, _y, _w, _h = _s['box']
    _cols = [(int(_s['px'][i * 6:i * 6 + 2], 16), int(_s['px'][i * 6 + 2:i * 6 + 4], 16), int(_s['px'][i * 6 + 4:i * 6 + 6], 16)) for i in range(_w * _h)]
    check(f'外掛實際截圖 {_s["f"].split("/")[-1]} 可抓捕數像素讀 {_s["value"]}', numglyph.read_rows(numglyph.binarize(_cols, _w, _h, 'ass'), 'ass')['value'] == _s['value'])
check('CLI：沒給 --confirm-buy 只印計畫、不碰遊戲', quiet(catchbuy.main, ['DKBO2', '5']) == 0)
import petquest  # noqa: E402
check('petquest 與 catchbuy 共用常數 / parse_money', petquest.PLUS_COST == catchbuy.PLUS_COST and petquest.PLUS_XY == catchbuy.PLUS_XY and petquest.parse_money is catchbuy.parse_money
      and petquest.EXIT_BAIT == catchbuy.EXIT_BAIT)

# ================= rebirth_steps：接任務 =================
class AccT:
    def __init__(self, rc=0, st='accepted'):
        self.rc, self.st, self.titles = rc, st, []

    def accept(self, title):
        self.titles.append(title)
        return self.rc

    def accept_state(self):
        return self.st


a = AccT()
check('accept_task：任務名 = 漆黑洞窟(三轉)、成功 0', quiet(rs.accept_task, 3, a) == 0 and a.titles == ['漆黑洞窟(三轉)'])
check('accept_task：已進行中 → 0（跳過）', quiet(rs.accept_task, 2, AccT(0, 'doing')) == 0)
check('accept_task：已完成 → 97（不接）', quiet(rs.accept_task, 2, AccT(0, 'done')) == 97)
check('accept_task：questdetail 126 → 97；9 / 10 透傳', quiet(rs.accept_task, 2, AccT(126, None)) == 97 and quiet(rs.accept_task, 2, AccT(9, None)) == 9 and quiet(rs.accept_task, 2, AccT(10, None)) == 10)
class CardT(AccT):
    def __init__(self, card, card_rc=0, **k):
        super().__init__(**k)
        self.card, self.card_rc, self.cards = card, card_rc, []

    def card_visible(self, title):
        return self.card

    def accept_card(self, title):
        self.cards.append(title)
        return self.card_rc


c = CardT(True, st='accepted')
check('accept_task：追蹤欄有卡 → 走卡片路徑、不開詳情', quiet(rs.accept_task, 3, c) == 0 and c.cards == ['漆黑洞窟(三轉)'] and c.titles == [] and rs.LAST.get('via') == 'tracker')
c = CardT(False)
check('accept_task：追蹤欄沒卡 → fallback questdetail', quiet(rs.accept_task, 3, c) == 0 and c.cards == [] and c.titles == ['漆黑洞窟(三轉)'] and rs.LAST.get('via') == 'detail')
c = CardT(True, card_rc=125)
check('accept_task：點卡後沒對話框(125) → 退回 questdetail', quiet(rs.accept_task, 2, c) == 0 and len(c.cards) == 1 and c.titles == ['漆黑洞窟(二轉)'] and rs.LAST.get('via') == 'detail')
c = CardT(True, card_rc=126)
check('accept_task：卡片路徑對話防護 126 → 97、不 fallback', quiet(rs.accept_task, 2, c) == 97 and c.titles == [])
check('accept_task：卡片路徑 9 透傳', quiet(rs.accept_task, 2, CardT(True, card_rc=9)) == 9)
check('task_name 各轉', [rs.task_name(i) for i in range(1, 6)] == [f'漆黑洞窟({c}轉)' for c in '一二三四五'])

# 2026-10-15 四轉：--from accept 被 preflight 留下的村長對話框擋住（97）→ 認得選單就直接在對話框接
check('is_menu_dialog：漆黑洞窟 / 再見 = 選單；接受 / 再見、完成、空 → 不是', rs.is_menu_dialog(['漆黑洞窟', '再見'], '漆黑洞窟(四轉)')
      and not rs.is_menu_dialog(['接受', '再見'], '漆黑洞窟(四轉)') and not rs.is_menu_dialog(['完成'], '漆黑洞窟(四轉)')
      and not rs.is_menu_dialog([], '漆黑洞窟(四轉)') and not rs.is_menu_dialog(['漆黑洞窟'], '漆黑洞窟(四轉)') and not rs.is_menu_dialog(None, '漆黑洞窟(四轉)'))


class DlgT(CardT):
    def __init__(self, btns, dlg_rc=0, **k):
        super().__init__(True, **k)
        self.btns, self.dlg_rc, self.dlg = btns, dlg_rc, []

    def open_dialog_buttons(self):
        return self.btns

    def accept_open_dialog(self, title):
        self.dlg.append(title)
        return self.dlg_rc


c = DlgT(['漆黑洞窟', '再見'])
check('accept_task：對話框開著是村長選單 → 直接在對話框接，不點卡、不開詳情', quiet(rs.accept_task, 4, c) == 0 and c.dlg == ['漆黑洞窟(四轉)'] and not c.cards and not c.titles
      and rs.LAST.get('via') == 'dialog')
c = DlgT(['確定'])
check('accept_task：對話框開著但不是村長選單 → 97、什麼都不點', quiet(rs.accept_task, 4, c) == 97 and not c.dlg and not c.cards and not c.titles)
c = DlgT(['漆黑洞窟', '再見'], dlg_rc=127)
check('accept_task：對話框接取失敗 127 → 97；9 透傳', quiet(rs.accept_task, 4, c) == 97 and quiet(rs.accept_task, 4, DlgT(['漆黑洞窟', '再見'], dlg_rc=9)) == 9)
c = DlgT(None)
check('accept_task：沒有對話框 → 照舊點卡', quiet(rs.accept_task, 4, c) == 0 and c.cards == ['漆黑洞窟(四轉)'] and not c.dlg)

# ================= rebirth_steps：獎勵寵 diff =================
def P(slot, name=None, level=None, state='等待', empty=False, mountlike=False):
    return {'slot': slot, 'empty': empty, 'name': name, 'level': level, 'state': state, 'unnamed': None, 'mountlike': mountlike}


BEF = [P(1, '布拉奇多斯', 130, '騎乘', mountlike=True), P(2, '朵拉比斯', 130, '出戰'), P(3, empty=True), P(4, empty=True), P(5, empty=True)]
AFT = [P(1, '布拉奇多斯', 1, '等待', mountlike=True), P(2, '朵拉比斯', 1, '出戰'), P(3, '某獎勵寵', 1), P(4, empty=True), P(5, empty=True)]
cand, why = rs.find_new_lv1(BEF, AFT)
check('find_new_lv1：新出現的第 3 格 Lv1 → 剛好 1 隻', [c['slot'] for c in cand] == [3] and why == '')
cand, why = rs.find_new_lv1(BEF, BEF)
check('find_new_lv1：沒有新寵 → 0 隻、理由', cand == [] and '沒有新出現' in why)
cand, why = rs.find_new_lv1(BEF, AFT[:3] + [P(4, '另一隻', 1), P(5, empty=True)])
check('find_new_lv1：兩隻新 Lv1 → 不確定', len(cand) == 2 and '剛好 1 隻' in why)
cand, why = rs.find_new_lv1(BEF, AFT[:2] + [P(3, '某獎勵寵', None)] + AFT[3:])
check('find_new_lv1：等級讀不出 → 不算候選', cand == [] and '等級' in why)
cand, why = rs.find_new_lv1(BEF, AFT[:2] + [P(3, '某獎勵寵', 12)] + AFT[3:])
check('find_new_lv1：新寵不是 Lv1 → 不算候選', cand == [])
cand, why = rs.find_new_lv1(BEF, AFT[:2] + [P(3, None, 1)] + AFT[3:])
check('find_new_lv1：名字讀不出 → 不算候選', cand == [] and '名字' in why)
cand, why = rs.find_new_lv1(BEF, AFT[:2] + [P(3, '某獎勵寵', 1, '出戰')] + AFT[3:])
check('find_new_lv1：新寵狀態出戰 / 騎乘 → 不算候選（不碰戰寵 / 騎寵）', cand == [])
cand, why = rs.find_new_lv1(BEF, AFT[:2] + [P(3, empty=True), P(4, empty=True), P(5, empty=True)])
check('find_new_lv1：已存在的 Lv1（名字相同的舊格）不算新', all(c['slot'] != 1 for c in cand) and cand == [])
cand, why = rs.find_new_lv1([P(1, empty=True)] + BEF[1:], AFT)
check('find_new_lv1：新寵在第 1 格 → 不丟（第 1 格通常是騎寵）', all(c['slot'] != 1 for c in cand))
snap = rs.snapshot_pets({'DKBO': [dict(slot=1, name='x', level=5, state='等待', empty=False, img_species='y')]})
check('snapshot_pets 可存 json', snap['DKBO'][0]['name'] == 'x' and 'img_species' not in snap['DKBO'][0])


class PetT:
    def __init__(self, after, drop_rc=0):
        self.after, self.drop_rc, self.drops, self.reads = after, drop_rc, [], 0

    def pets(self, roles):
        self.reads += 1
        return 0, {r: [dict(s) for s in self.after.get(r, AFT)] for r in roles}

    def drop(self, role, name, slot=None, dry_run=False):
        self.drops.append((role, name, slot))
        return self.drop_rc


BEFORE = {r: BEF for r in rs.ALL_ROLES}
T = PetT({})
check('drop_rewards 第 1 轉：對照表 → petdrop all 烏力斯坦（不讀寵物欄、不 diff）', quiet(rs.drop_rewards, 1, None, T) == 0 and T.drops == [('all', '烏力斯坦', None)] and T.reads == 0)
T = PetT({})
check('drop_rewards 第 2 轉：奇娜', quiet(rs.drop_rewards, 2, None, T) == 0 and T.drops == [('all', '奇娜', None)])
T = PetT({}, drop_rc=73)
check('drop_rewards 對照表：petdrop 失敗碼原樣回（呼叫端對應）', quiet(rs.drop_rewards, 1, None, T) == 73)
T = PetT({})
check('drop_rewards 第 3 轉：5 人各剛好 1 隻新 Lv1 → 逐人 --slot 丟、名字傳給 petdrop', quiet(rs.drop_rewards, 3, BEFORE, T) == 0
      and T.drops == [(r, '某獎勵寵', 3) for r in rs.ALL_ROLES], str(T.drops))
T = PetT({})
check('drop_rewards 第 3 轉：沒有快照 → 98、零丟棄', quiet(rs.drop_rewards, 3, None, T) == 98 and T.drops == [])
T = PetT({'DKBO3': BEF})
check('drop_rewards 第 3 轉：有一人沒新寵 → 98 且全員都不丟（先全驗再動手）', quiet(rs.drop_rewards, 3, BEFORE, T) == 98 and T.drops == [])
T = PetT({'DKBO': AFT[:2] + [P(3, '甲', 1), P(4, '乙', 1), P(5, empty=True)]})
check('drop_rewards 第 3 轉：某人兩隻 Lv1 → 98 全不丟', quiet(rs.drop_rewards, 3, BEFORE, T) == 98 and T.drops == [])
T = PetT({}, drop_rc=76)
check('drop_rewards 第 3 轉：petdrop 失敗 → 98', quiet(rs.drop_rewards, 3, BEFORE, T) == 98 and len(T.drops) == 1)
T = PetT({}, drop_rc=9)
check('drop_rewards 第 3 轉：petdrop 9 透傳', quiet(rs.drop_rewards, 3, BEFORE, T) == 9)
tmp = Path(tempfile.mkdtemp()) / 'snap.json'
rs.save_snapshot(BEFORE, tmp)
check('快照存讀 json', rs.load_snapshot(tmp) == BEFORE and rs.load_snapshot(tmp.parent / 'none.json') == {})
check('reward_name 對照表', rs.reward_name(1) == '烏力斯坦' and rs.reward_name(2) == '奇娜' and rs.reward_name(3) is None)
check('rebirth 的 URISTAN 常數 = 對照表一轉', __import__('rebirth').URISTAN == '烏力斯坦')

# ---- 等級門檻：點追蹤卡（level_gate / judge_gate_text）----
J = rs.judge_gate_text
j = J('DKB04 未達到 3轉 131級禁止傳送')
check('judge_gate：讀出誰 / 轉數 / 等級（DKB04 → 真名 DKBO4）', j and j['who'] == 'DKBO4' and j['trans'] == 3 and j['level'] == 131, str(j))
check('judge_gate：條件不足,無法傳送 → 被擋（誰讀不到）', J('條件不足,無法傳送') and J('條件不足,無法傳送')['who'] is None)
check('judge_gate：等級不足 → 被擋', J('等級不足') is not None)
check('judge_gate：不相干 / 空字 → None', J('請選擇正確的圖片') is None and J('') is None and J(None) is None)
check('past_gate：吉魯島 / 漆黑 1F～21F', rs.past_gate((300, 1, 1)) and rs.past_gate((32001, 1, 1)) and rs.past_gate((32021, 1, 1)) and not rs.past_gate((1000, 1, 1)) and not rs.past_gate(None))


class GateT:
    def __init__(self, pos=(1200, 50, 50), card=True, after=None, notice_at=None, notice_text='', state='walking', unknown_text='', chat='', dismiss_ok=True):
        self.t = 0.0
        self.p, self.card, self.after = pos, card, after or []
        self.notice_at, self.ntext, self.st, self.utext, self.chat, self.dok = notice_at, notice_text, state, unknown_text, chat, dismiss_ok
        self.calls = []

    def clock(self): return self.t
    def sleep(self, s): self.t += s
    def pos(self):
        if self.after and self.t >= self.after[0][0]:
            self.p = self.after.pop(0)[1]
        return self.p
    def click_card(self, title): self.calls.append(('card', title)); return self.card
    def notice(self): return self.notice_at is not None and self.t >= self.notice_at
    def notice_text(self): return self.ntext
    def dismiss(self): self.calls.append('dismiss'); return self.dok
    def state(self): return self.st
    def transition(self): return None
    def center_text(self): self.calls.append('center'); return self.utext
    def chat_text(self): self.calls.append('chat'); return self.chat
    def dialog_buttons(self): self.calls.append('buttons'); return getattr(self, 'btns', ['確定'])

    def accept_dialog(self, title):
        self.calls.append(('accept', title))
        rc = getattr(self, 'acc_rc', 0)
        if not rc:
            self.st, self.p = getattr(self, 'st_after', 'walking'), (2000, 54, 97)     # 接完：對話框收起、人在瑪麗娜絲村
            self.after = list(getattr(self, 'after2', []))
        return rc


T = GateT(after=[(3, (300, 121, 170))])
g = quiet(rs.level_gate, 4, T)
check('level_gate：點卡（標題 漆黑洞窟(四轉)）→ 換到吉魯島 = teleport', g['kind'] == 'teleport' and ('card', '漆黑洞窟(四轉)') in T.calls, str(g))
T = GateT(pos=(32005, 1, 1))
g = quiet(rs.level_gate, 4, T)
check('level_gate：已在漆黑 → already、不點卡', g['kind'] == 'already' and not T.calls)
T = GateT(notice_at=2, notice_text='DKBO5未達到3轉131級禁止傳送')
g = quiet(rs.level_gate, 4, T)
check('level_gate：提示視窗含未達到 → blocked、點 ✕ 關、記誰', g['kind'] == 'blocked' and g['who'] == 'DKBO5' and g['closed'] and 'dismiss' in T.calls, str(g))
T = GateT(notice_at=2, notice_text='請回答下列問題')
g = quiet(rs.level_gate, 4, T)
check('level_gate：提示視窗讀不懂 → unknown、不點 ✕', g['kind'] == 'unknown' and 'dismiss' not in T.calls)
T = GateT(state='unknown', unknown_text='看圖選出正確答案')
g = quiet(rs.level_gate, 4, T)
check('level_gate：不認得的畫面讀不懂 → unknown（呼叫端 9）', g['kind'] == 'unknown' and 'center' in T.calls)
T = GateT(state='unknown', unknown_text='條件不足,無法傳送')
g = quiet(rs.level_gate, 4, T)
check('level_gate：不認得的視窗但有條件不足 → blocked、closed=False（不亂點）', g['kind'] == 'blocked' and g['closed'] is False and 'dismiss' not in T.calls)
T = GateT(card=False)
check('level_gate：追蹤欄沒卡 → nocard', quiet(rs.level_gate, 4, T)['kind'] == 'nocard')
T = GateT(card=None)
check('level_gate：掃描途中畫面變了 → screen', quiet(rs.level_gate, 4, T)['kind'] == 'screen')
T = GateT(state='dialog')
check('level_gate：直接出現對話框（沒傳送）→ dialog', quiet(rs.level_gate, 4, T)['kind'] == 'dialog')
T = GateT(state='dialog', pos=(60050, 25, 24))
T.btns = ['漆黑洞窟', '再見']
T.after2 = [(6, (300, 96, 228))]
g = quiet(rs.level_gate, 4, T)
check('level_gate：點卡被傳到村長選單（任務沒接）→ 接任務 → 再點卡 → teleport、accepted', g['kind'] == 'teleport' and g['accepted'] is True
      and [c for c in T.calls if c != 'buttons'] == [('card', '漆黑洞窟(四轉)'), ('accept', '漆黑洞窟(四轉)'), ('card', '漆黑洞窟(四轉)')], str((g, T.calls)))
T = GateT(state='dialog', pos=(60050, 25, 24))
T.btns, T.st_after = ['漆黑洞窟', '再見'], 'dialog'
g = quiet(rs.level_gate, 4, T)
check('level_gate：接完再點卡又是對話框 → dialog（只接一次）', g['kind'] == 'dialog' and g['accepted'] is True and T.calls.count(('accept', '漆黑洞窟(四轉)')) == 1, str(g))
T = GateT(state='dialog', pos=(60050, 25, 24))
T.btns, T.acc_rc = ['漆黑洞窟', '再見'], 127
g = quiet(rs.level_gate, 4, T)
check('level_gate：村長選單接取失敗 → accept_fail（rc）、不再點卡', g['kind'] == 'accept_fail' and g['rc'] == 127 and T.calls.count(('card', '漆黑洞窟(四轉)')) == 1)
T = GateT(state='dialog', pos=(60050, 25, 24))
T.btns = ['漆黑洞窟', '再見']
T.after2 = [(4, (300, 96, 228))]
T.card_seq = None
g = quiet(rs.level_gate, 4, T)
check('level_gate：接完人在村子（2000）不算 moved，等到吉魯島才 teleport', g['kind'] == 'teleport', str(g))
# 2026-10-16 p2 / 10-17 p3 一轉：點卡約 3 秒就到吉魯島守門人對話框（HUD 被藏、地圖一直讀成練功點 60049）→ 舊版當村長選單去接任務 → 84
check('is_gatekeeper_dialog：守門人「漆黑洞窟(漆黑任務) / 再見」', rs.is_gatekeeper_dialog(['漆黑洞窟(漆黑任務)', '再見'])
      and rs.is_gatekeeper_dialog(['漆黑洞窟（漆黑任務', '再 見']) and rs.is_gatekeeper_dialog(['漆黑洞窟漆黑任務', '再見']))
check('is_gatekeeper_dialog：村長選單 / 其他不算', not rs.is_gatekeeper_dialog(['漆黑洞窟', '再見']) and not rs.is_gatekeeper_dialog(['挑戰守護獸', '再見'])
      and not rs.is_gatekeeper_dialog(['漆黑洞窟(漆黑任務)']) and not rs.is_gatekeeper_dialog(None))
check('is_menu_dialog：守門人不算村長選單（不去接任務）', not rs.is_menu_dialog(['漆黑洞窟(漆黑任務)', '再見'], '漆黑洞窟(一轉)')
      and rs.is_menu_dialog(['漆黑洞窟', '再見'], '漆黑洞窟(一轉)'))
T = GateT(state='dialog', pos=(60049, 30, 25))
T.btns = ['漆黑洞窟(漆黑任務)', '再見']
g = quiet(rs.level_gate, 1, T)
check('level_gate：點卡後是守門人對話框（地圖讀不到）→ teleport via gatekeeper、不接任務、只點一次卡', g['kind'] == 'teleport' and g.get('via') == 'gatekeeper'
      and not any(isinstance(c, tuple) and c[0] == 'accept' for c in T.calls) and T.calls.count(('card', '漆黑洞窟(一轉)')) == 1, str((g, T.calls)))
class _GK(GateT):
    def accept_dialog(self, title):
        rc = super().accept_dialog(title)
        self.btns = ['漆黑洞窟(漆黑任務)', '再見']              # 接完再點卡 → 傳到守門人
        return rc
T2 = _GK(state='dialog', pos=(60050, 25, 24))
T2.btns, T2.st_after = ['漆黑洞窟', '再見'], 'dialog'
g = quiet(rs.level_gate, 1, T2)
check('level_gate：村長選單接完再點卡 → 守門人對話框 → teleport、accepted', g['kind'] == 'teleport' and g['accepted'] is True and g.get('via') == 'gatekeeper', str(g))
T = GateT(after=[(2, (2006, 21, 8))])
check('level_gate：換到別張地圖 → moved', quiet(rs.level_gate, 4, T)['kind'] == 'moved')
T = GateT(state='idle', chat='系統：DKBO3未達到3轉131級禁止傳送')
g = quiet(rs.level_gate, 4, T)
check('level_gate：逾時、聊天區有未達到 → blocked via chat', g['kind'] == 'blocked' and g['via'] == 'chat' and g['who'] == 'DKBO3', str(g))
T = GateT(state='idle')
check('level_gate：逾時、什麼都沒有 → timeout', quiet(rs.level_gate, 4, T)['kind'] == 'timeout')

# ---- 2026-10-16 petdrop.drop_first_slot：固定動作逐人丟第 1 格（假 pet / uikit，不碰畫面）----
import petdrop, pet as _pet, uikit as _uk
class _FakePetUI:
    def __init__(self, empty_roles=(), stuck=False):
        self.empty_roles, self.stuck, self.cur, self.log = set(empty_roles), stuck, None, []
        self.after_ok = False
    def select_role(self, r, ctx): self.cur = r; self.log.append(('role', r)); return 0
    def scan_frames(self):
        e = r_ = self.cur in self.empty_roles
        return {'empty': [e, True, True, True, True], 'sel': [False] * 5}
    def select_slot(self, i, f): self.log.append(('slot', self.cur, i)); return 0
    def click(self, x, y, panel, note='', allow=(), wait_ms=0):
        self.log.append(('click', (x, y), self.cur))
        if (x, y) == petdrop.CONFIRM_OK and not self.stuck: self.empty_roles.add(self.cur)
        return True
def _run_first(ui, **kw):
    saved = (_pet.select_role, _pet.scan_frames, _pet.select_slot, _pet.load_ctx, _pet.save_ctx, _pet.Session, _uk.safe_click, _uk.is_open, _uk.sleep)
    class _S:
        rc = 0
        def __init__(s, *a): pass
        def __enter__(s): return s
        def __exit__(s, *a): return False
    _pet.select_role, _pet.scan_frames, _pet.select_slot = ui.select_role, ui.scan_frames, ui.select_slot
    _pet.load_ctx, _pet.save_ctx, _pet.Session = (lambda *a, **k: {}), (lambda *a, **k: None), _S
    _uk.safe_click, _uk.is_open, _uk.sleep = ui.click, (lambda p: True), (lambda s: None)
    try:
        return quiet(petdrop.drop_first_slot, 'all', **kw)
    finally:
        (_pet.select_role, _pet.scan_frames, _pet.select_slot, _pet.load_ctx, _pet.save_ctx, _pet.Session, _uk.safe_click, _uk.is_open, _uk.sleep) = saved
ui = _FakePetUI()
check('drop_first_slot：5 人逐人 選第 1 格 → 垃圾桶 → 確定，全 dropped', _run_first(ui) == 0 and petdrop.LAST.get('dropped') == list(_pet.role_list('all'))
      and [l for l in ui.log if l[0] == 'slot'] == [('slot', r, 0) for r in _pet.role_list('all')]
      and [l[1] for l in ui.log if l[0] == 'click'].count(petdrop.TRASH_XY) == 5, str(petdrop.LAST))
ui = _FakePetUI(empty_roles=[_pet.role_list('all')[1]])
check('drop_first_slot：某人第 1 格本來就空 → 跳過（already），其他照丟', _run_first(ui) == 0 and petdrop.LAST.get('already') == [_pet.role_list('all')[1]] and len(petdrop.LAST['dropped']) == 4)
ui = _FakePetUI(stuck=True)
check('drop_first_slot：確定後第 1 格沒變空 → 76、不續做下一人', _run_first(ui) == 76 and len([l for l in ui.log if l[0] == 'role']) == 1)
ui = _FakePetUI()
check('drop_first_slot dry-run：不點任何東西', _run_first(ui, dry_run=True) == 0 and not [l for l in ui.log if l[0] == 'click'] and len(petdrop.LAST['would_drop']) == 5)

print(f'\n{"全部通過" if not fails else f"失敗 {fails} 項"}')
sys.exit(1 if fails else 0)
