#!/usr/bin/env python3
"""P3（外接螢幕樣板分版面存放）離線測試，不碰遊戲：
- 各樣板模組依 layout.tpl_key() 選檔：2880×1659 = 原檔（筆電不變）、1728×995 = 另一份（digit / name / pet / species / title / questdetail / item icon）
- namematch 墨點門檻依面積比縮放、capture 只收 2880 / TEMPLATE_PHYS 版面
- digitmatch 切字縮放（seg_scale）：scale=1 與原行為相同；1728×995 實機點陣切出的字數 = 標籤字數（冒號 / 級 / 寵物等級框）
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import testenv  # noqa: E402,F401
import layout  # noqa: E402

fails = 0


def check(name, cond, extra=''):
    global fails
    print(('PASS' if cond else 'FAIL'), name, extra)
    if not cond:
        fails += 1


real_cur = layout.current


def use(phys):
    layout.current = lambda: phys


import bag  # noqa: E402
import digitmatch  # noqa: E402
import namematch  # noqa: E402
import petmatch  # noqa: E402
import questdetail  # noqa: E402
import titlematch  # noqa: E402

# ---- 筆電：全部原檔 ----
use('2880x1659')
check('筆電 tpl_key = 2880x1659', layout.tpl_key() == '2880x1659')
check('筆電 petmatch 樣板 = pet-tpl/2880x1659.json、species.json', petmatch.tpl_path().name == '2880x1659.json' and petmatch.species_path().name == 'species.json')
check('筆電 titlematch 樣板資料夾 = task-titles 根目錄', titlematch.tpl_dir() == titlematch.TPL_DIR)
check('筆電 questdetail 樣板 = fixtures/questdetail_tpl.json', questdetail.tpl_file() == questdetail.TPL_FILE)
check('筆電 bag 道具圖示 = fixtures/item_icons.json', bag.icon_file() == bag.ICON_FILE)
check('筆電 namematch 墨點門檻不變', namematch.min_ink('2880x1659') == namematch.MIN_INK)

# ---- 外接 1728×995：另一份 ----
use('1728x995')
check('外接 tpl_key = 1728x995', layout.tpl_key() == '1728x995')
check('外接 petmatch 樣板 = pet-tpl/1728x995.json、species-1728x995.json', petmatch.tpl_path().name == '1728x995.json' and petmatch.species_path().name == 'species-1728x995.json')
check('外接 titlematch 樣板資料夾 = task-titles/1728x995', titlematch.tpl_dir() == titlematch.TPL_DIR / '1728x995')
qf = questdetail.tpl_file()
check('外接 questdetail 樣板在 tools/.cache（不寫進 fixture）', qf != questdetail.TPL_FILE and '.cache' in qf.parts and qf.name == '1728x995.json')
bf = bag.icon_file()
check('外接 bag 道具圖示在 tools/.cache/item-icons/1728x995.json', bf != bag.ICON_FILE and bf.parent.name == 'item-icons' and bf.name == '1728x995.json')
check('外接 namematch 墨點門檻依面積比縮（150 → 54）', namematch.min_ink('1728x995') == 54)
check('namematch 只收 2880 / TEMPLATE_PHYS 的截圖', namematch.layout_ok('2880x1659') and namematch.layout_ok('1728x995') and not namematch.layout_ok('1920x1017'))

# ---- 沒學過樣板的同比例尺寸：退回原檔鍵（守衛本來就擋） ----
use('1584x912')
check('沒樣板的尺寸 tpl_key 退回 2880x1659（守衛另外擋）', layout.tpl_key() == '2880x1659' and layout.template_layout() is None)
layout.current = real_cur

# ---- digitmatch 切字縮放 ----
check('seg_scale：2880 / None / 怪字串 = 1.0、1728 = 0.6', digitmatch.seg_scale('2880x1659') == 1.0 and digitmatch.seg_scale(None) == 1.0
      and digitmatch.seg_scale('abc') == 1.0 and abs(digitmatch.seg_scale('1728x995') - 0.6) < 1e-9)
fx = json.loads((HERE / 'fixtures' / 'digit_1728x995_rows.json').read_text(encoding='utf-8'))
sc = digitmatch.seg_scale(fx['layout'])
for k, lab in fx['labels'].items():
    rows = fx['fields'][k]
    n1 = len(digitmatch.segment(rows, k == 'pos', sc))
    n0 = len(digitmatch.segment(rows, k == 'pos'))
    check(f'外接實機 {k}「{lab}」：縮放切字 {n1} 字 = 標籤字數（不縮放 {n0} 字，舊常數切壞）', n1 == len(lab) and n0 != len(lab))
# scale = 1 與預設呼叫逐位元相同（筆電）
same = all(digitmatch.segment(fx['fields'][k], k == 'pos') == digitmatch.segment(fx['fields'][k], k == 'pos', 1.0) for k in fx['fields'])
check('segment(scale=1.0) 與預設呼叫結果相同', same)

# ---- walk 世界倍率守衛：量過的外接尺寸（WORLD_OK_PHYS）放行，沒量過的同比例縮放視窗不點地面 ----
import os  # noqa: E402
import walk  # noqa: E402
env = os.environ.pop('PSA_LAYOUT')
rl = layout.logical
layout.current, layout.logical = (lambda: '1728x995'), (lambda: '2880x1659')
try:
    walk.world_guard()
    check('walk.world_guard：外接 1728x995（已量世界倍率）放行', '1728x995' in walk.WORLD_OK_PHYS)
except RuntimeError:
    check('walk.world_guard：外接 1728x995（已量世界倍率）放行', False)
layout.current = lambda: '1584x912'
try:
    walk.world_guard()
    check('walk.world_guard：沒量過的同比例 1584x912 → RuntimeError', False)
except RuntimeError as e:
    check('walk.world_guard：沒量過的同比例 1584x912 → RuntimeError', '1584x912' in str(e))
layout.current, layout.logical = (lambda: '2880x1659'), (lambda: '2880x1659')
try:
    walk.world_guard()
    check('walk.world_guard：筆電 2880x1659 不擋', True)
except RuntimeError:
    check('walk.world_guard：筆電 2880x1659 不擋', False)
layout.current, layout.logical = real_cur, rl
os.environ['PSA_LAYOUT'] = env

print('\n全部通過' if not fails else f'\n{fails} 項失敗')
sys.exit(1 if fails else 0)
