#!/usr/bin/env python3
"""layout.py 離線測試（不碰遊戲）：evaluate / supported 守衛判斷、template_layout(phys)、status。"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import layout  # noqa: E402

fails = 0


def check(name, cond, extra=''):
    global fails
    print(('PASS' if cond else 'FAIL'), name, extra)
    if not cond:
        fails += 1


E_ = layout.evaluate
check('筆電 2880x1659 → ok', E_('2880x1659', '2880x1659') == (True, ''))
check('筆電 logical 缺（舊輸出）也 ok', E_('2880x1659', None)[0])
check('同比例 1728x995（P3 樣板已就緒，TEMPLATE_PHYS）→ ok', E_('1728x995', '2880x1659') == (True, '') and '1728x995' in layout.TEMPLATE_PHYS)
ok, why = E_('1584x912', '2880x1659')
check('同比例但沒學過樣板的尺寸（1584x912）→ 擋、理由含樣板', not ok and '樣板' in why and '1584x912' in why, why)
check('1920x1017 → 擋（舊路徑不經此守衛）', not E_('1920x1017', '1920x1017')[0])
check('非同比例 1728x995（logical 不是 2880）→ 擋', not E_('1728x995', '1728x995')[0])
check('遊戲沒開 → 擋', not E_(None, None)[0])
real = layout.template_layout
layout.template_layout = lambda phys=None: phys
check('模擬樣板就緒：同比例 1728x995 → ok', E_('1728x995', '2880x1659') == (True, ''))
check('模擬樣板就緒：非同比例仍擋', not E_('1728x995', '1728x995')[0])
layout.template_layout = real
check('template_layout(phys)：2880 / 1920 / 1728 有、1584 無', real('2880x1659') == '2880x1659' and real('1920x1017') == '1920x1017' and real('1728x995') == '1728x995' and real('1584x912') is None)
check('tpl_key：1728 → 1728x995、2880 → 2880x1659、不支援 → DEFAULT', layout.tpl_key('1728x995') == '1728x995' and layout.tpl_key('2880x1659') == '2880x1659' and layout.tpl_key('1584x912') == layout.DEFAULT)

# supported() / status() 走 current() / logical()
rc, rl = layout.current, layout.logical
layout.current, layout.logical = (lambda: '1728x995'), (lambda: '2880x1659')
check('supported() 1728x995 → 放行（P3 樣板就緒）', layout.supported() == (True, ''))
st = layout.status()
check('status 1728x995：scaled、樣板就緒、ok True', st['scaled'] and st['templates'] and st['ok'] is True and not st['reason'], str(st))
layout.current = lambda: '1584x912'
check('supported() 1584x912（同比例、沒樣板）→ 擋', layout.supported()[0] is False)
st = layout.status()
check('status 1584x912：scaled、樣板未就緒、ok False + reason', st['scaled'] and not st['templates'] and st['ok'] is False and st['reason'], str(st))
layout.current = lambda: '2880x1659'
layout.logical = lambda: (_ for _ in ()).throw(AssertionError('2880 不該問 logical'))
check('supported() 2880x1659 不問 logical', layout.supported() == (True, ''))
layout.current, layout.logical = rc, rl
layout.prime  # 存在
print('\n全部通過' if not fails else f'\n{fails} 項失敗')
sys.exit(1 if fails else 0)
