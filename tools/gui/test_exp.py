#!/usr/bin/env python3
"""exp.py 離線測試（不碰遊戲）：OCR 文字用 2026-10-12 實機讀到的樣本（含錯字行）；跨級速率、讀不出 None。
用法：uv run --no-project python tools/gui/test_exp.py"""
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import testenv  # noqa: E402,F401
import exp  # noqa: E402
import uikit  # noqa: E402

fails = 0


def check(name, cond, extra=''):
    global fails
    print(('PASS' if cond else 'FAIL'), name, extra)
    if not cond:
        fails += 1


T = exp.load_table()
check('經驗表 128 級 = 69,487,425（實測分母）', T[128] == 69487425)
check('parse_exp 正常', exp.parse_exp('58756681/69487425') == (58756681, 69487425))
check('parse_exp 目前 > 所需 → None', exp.parse_exp('99999999/69487425') is None)
check('parse_exp 無斜線 → None', exp.parse_exp('58756681') is None)
check('parse_level', exp.parse_level('1轉128級(10001154)') == (1, 128) and exp.parse_level('1蓄128級') == (1, 128) and exp.parse_level('xx') is None)
lines = ['69043763/69487425', '643763/69487425', '69043763/69487425', '691244/69487425']
check('vote 取多數（多 zoom 錯字行）', exp.vote(lines, exp.parse_exp) == (69043763, 69487425))
check('reconcile 本級所需對得上表', exp.reconcile((1, 128), (58756681, 69487425), T)['total'] == exp.cum_before(128, T) + 58756681)
check('reconcile 本級所需對不上表 → None（不猜）', exp.reconcile((1, 128), (5, 12345), T) is None)
check('reconcile 缺等級 / 缺經驗 → None', exp.reconcile(None, (1, 2), T) is None and exp.reconcile((1, 128), None, T) is None)

# 速率：同級
a = {'trans': 1, 'level': 128, 'cur': 58756681, 'ts': 1000.0}
b = {'trans': 1, 'level': 128, 'cur': 58756681 + 600000, 'ts': 1300.0}
check('同級速率 = 120000/min', round(exp.rate_per_min(a, b, T)) == 120000)
# 跨級：128 → 129
c = {'trans': 1, 'level': 129, 'cur': 100000, 'ts': 1300.0}
exp_d = (T[128] - 58756681) + 100000
check('跨級速率用經驗表補算', round(exp.rate_per_min(a, c, T)) == round(exp_d / 300 * 60))
check('轉數不同 → None', exp.rate_per_min(a, dict(c, trans=2), T) is None)
check('時間倒退 → None', exp.rate_per_min(b, a, T) is None)

# 剩餘與 ETA
rem = exp.remaining(128, 58756681, 131, T)
check('剩餘 = T[128]-cur + T[129] + T[130]', rem == T[128] - 58756681 + T[129] + T[130])
check('已達標 remaining 0', exp.remaining(131, 5, 131, T) == 0 and exp.remaining(140, 5, 131, T) == 0)
check('eta_minutes', exp.eta_minutes(1200000, 120000) == 10 and exp.eta_minutes(1000, None) is None and exp.eta_minutes(0, None) == 0.0)
check('fmt_min', exp.fmt_min(125) == '2 小時 5 分' and exp.fmt_min(None) == '—')
res = exp.build_eta({'DKBO': a, 'DKBO2': None}, {'DKBO': dict(b, need=T[128], total=0), 'DKBO2': dict(b, need=T[128], total=0), 'DKBO3': None}, 131, T)
check('build_eta：有第一筆有速率、沒有第一筆速率 None、讀不出 None', res['DKBO']['rate_per_min'] == 120000 and res['DKBO2']['rate_per_min'] is None and res['DKBO3'] is None)
check('eta_min 合理', res['DKBO']['eta_min'] == round(res['DKBO']['remaining'] / 120000, 1))

# read_current：假 OCR
shown = {'lv': ['1轉128級(10001154)', '1轉128級(10001154)'], 'ex': ['69043763/69487425', '643763/69487425']}
orig_ocr, orig_sleep = uikit.ocr, uikit.sleep


def fake_ocr(box, *o):
    return shown['lv'] if tuple(box) == exp.LEVEL_BOX else shown['ex']


uikit.ocr, uikit.sleep = fake_ocr, lambda s: None
r = exp.read_current(T)
check('read_current 正常', r and r['level'] == 128 and r['cur'] == 69043763)
shown['ex'] = ['', 'abc']
check('read_current 經驗讀不出 → None', exp.read_current(T) is None)
shown['ex'] = ['58756681/69487425']
shown['lv'] = ['']
check('read_current 等級讀不出 → None（不反推）', exp.read_current(T) is None)
shown['lv'], shown['ex'] = ['1轉128級'], ['69043763/12345678']
check('read_current 所需對不上表 → None', exp.read_current(T) is None)
uikit.ocr, uikit.sleep = orig_ocr, orig_sleep

# 歷史
tmp = Path(tempfile.mkdtemp()) / 'h.jsonl'
exp.history_add({'role': 'DKBO', 'trans': 1, 'level': 128, 'cur': 1, 'ts': 100.0}, tmp)
exp.history_add({'role': 'DKBO', 'trans': 1, 'level': 128, 'cur': 2, 'ts': 500.0}, tmp)
exp.history_add({'role': 'DKBO', 'trans': 0, 'level': 128, 'cur': 3, 'ts': 590.0}, tmp)
h = exp.history_load(tmp)
check('history 讀回 3 筆', len(h) == 3)
check('history_pick：同轉數、≥ min_age 的最新', exp.history_pick(h, 'DKBO', 1, 600.0, 60)['cur'] == 2 and exp.history_pick(h, 'DKBO', 1, 600.0, 200)['cur'] == 1 and exp.history_pick(h, 'DKBO', 1, 600.0, 900) is None)

# 角色名 / 禁區
check('norm_roles', exp.norm_roles('all') == exp.ROLES and exp.norm_roles('DKB0,DKB03') == ['DKBO', 'DKBO3'])
for k, rc in exp.FORBID.items():
    try:
        uikit.check_forbidden(exp.ROLEINFO, rc[0] + 2, rc[1] + 2)
        check(f'禁區 {k} 擋點擊', False)
    except uikit.ForbiddenClick:
        check(f'禁區 {k} 擋點擊', True)
check('dry-run 不碰遊戲', exp.main(['read', '--dry-run']) == 0 and exp.main(['eta', '--dry-run']) == 0)

print('失敗', fails)
sys.exit(1 if fails else 0)
