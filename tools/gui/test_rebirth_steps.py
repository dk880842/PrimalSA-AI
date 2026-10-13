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

    def press(self, role, limit=None):
        if self.rc:
            return self.rc, self.count, None
        if limit is not None and self.count >= limit:
            return 0, self.count, self.count
        b = self.count
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
check('石幣不夠 → fail 且沒再按', k == 'fail' and sh.count == 2 and '不夠' in msg)
sh = Shop(cost=10000)
k, msg, *_ = catchbuy.buy('DKBO2', 1, sh.money, sh.press, lambda m: None)
check('石幣扣的不是 50,000 → fail', k == 'fail' and '不是剛好扣' in msg)
sh = Shop(dia_drop=5)
k, msg, *_ = catchbuy.buy('DKBO2', 1, sh.money, sh.press, lambda m: None)
check('鑽石有變 → fail（鐵則 3）', k == 'fail' and '鑽石' in msg)
sh = Shop(noop=True)
k, msg, *_ = catchbuy.buy('DKBO2', 1, sh.money, sh.press, lambda m: None)
check('可抓捕數沒 +1 → fail', k == 'fail' and '不是 +1' in msg)
sh = Shop(rc=4)
k, msg, rc_, _ = catchbuy.buy('DKBO2', 1, sh.money, sh.press, lambda m: None)
check('press 回非 0 → pass（原碼）', k == 'pass' and rc_ == 4)
k, msg, *_ = catchbuy.buy('DKBO2', 1, lambda: (None, None), Shop().press, lambda m: None)
check('讀不到石幣 → fail 且不按', k == 'fail' and '讀不到石幣' in msg)
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

print(f'\n{"全部通過" if not fails else f"失敗 {fails} 項"}')
sys.exit(1 if fails else 0)
