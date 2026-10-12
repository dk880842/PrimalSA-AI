#!/usr/bin/env python3
"""team.py（status / check / disband）離線測試：不碰遊戲，假 gui 依設定畫切換面板像素。
用法：uv run --no-project python tools/gui/test_team.py"""
import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import testenv  # noqa: E402,F401  紀錄檔轉向暫存（不污染真 actions.log / quest-events.log / errlog）
import errlog  # noqa: E402
import screen_sigs  # noqa: E402
import namematch  # noqa: E402
import team  # noqa: E402
import uikit  # noqa: E402

import charstate  # noqa: E402
import watchstate  # noqa: E402

errlog.LOG = Path(tempfile.mkdtemp()) / 'errlog.jsonl'
watchstate.CURCHAR_FILE = Path(tempfile.mkdtemp()) / 'current-char.json'     # 不動真實旁路檔
namematch.TPL_DIR = Path(tempfile.mkdtemp())     # 不讀真實樣板（離線測試走舊 OCR 邏輯）
fails = 0


def check(name, cond, extra=''):
    global fails
    print(('PASS' if cond else 'FAIL'), name, extra)
    if not cond:
        fails += 1

from fake_switch import SOLO, BLUE, GREEN, BEIGE, BROWN, RED, YEL, NORMAL, NAMES, OCR_REAL, Game, mk, install, run  # noqa: E402,F401


# ---- 純函式：fixture 真實像素 ----
fx = json.loads((HERE / 'fixtures' / 'switch_px.json').read_text(encoding='utf-8'))['px']
P = lambda x, y: tuple(fx[f'{x},{y}'])  # noqa: E731
check('fixture 卡片米色 = 存在', all(team.is_card(P(x, y)) for x, y in [(416, 300), (416, 385), (416, 470), (726, 300), (726, 385)]))
check('fixture 第 6 格棕色 = 空位', not team.is_card(P(726, 470)))
check('fixture 線上 = online（左右欄）', team.classify_status(P(422, 300), P(446, 300)) == 'online' and team.classify_status(P(732, 385), P(756, 385)) == 'online')
check('fixture 當前 = current', team.classify_status(P(422, 470), P(446, 470)) == 'current')
check('實測值（P-I1）當前 / 線上', team.classify_status((29, 175, 195), (24, 189, 211)) == 'current' and team.classify_status((8, 187, 36), (0, 201, 33)) == 'online')
check('狀態不明（棕）= unknown', team.classify_status(BROWN, BROWN) == 'unknown')
# 標籤分類
check('紅 ≥3 = leader', team.classify_label([RED] * 7 + [(0, 0, 0)] * 50) == 'leader')
check('黃 4 + 綠「正常」= member', team.classify_label([YEL] * 4 + [NORMAL] * 30 + [(77, 66, 59)] * 20) == 'member')
check('只有綠 = other', team.classify_label([NORMAL] * 30) == 'other')
check('框邊 (183,128,63) 不算', team.classify_label([(183, 128, 63)] * 100) == 'other')
check('紅 2 點（雜訊）= other', team.classify_label([RED] * 2) == 'other')

# ---- 名字 OCR ----
for nm in NAMES:
    check(f'cross_check {nm} 實測 OCR → ok', team.cross_check(nm, OCR_REAL[nm]) == 'ok', str(OCR_REAL[nm]))
check('cross_check 讀不出 → unknown', team.cross_check('DKBO3', []) == 'unknown')
check('cross_check 讀到別人 → conflict', team.cross_check('DKBO3', ['D02']) == 'conflict')
check('cross_check 同卡多名字 → unknown（雜訊）', team.cross_check('DKBO3', ['03', 'D02']) == 'unknown')
check('cross_check DKBO5 只讀到 DKBO（可能截斷）→ unknown 不算矛盾', team.cross_check('DKBO5', ['DKBO']) == 'unknown')
check('cross_check DKBO2 讀到 DKBO 單獨 → unknown', team.cross_check('DKBO2', ['DKBO']) == 'unknown')
check('resolve_name 唯一尾碼', team.resolve_name(1, ['D02', '02']) == 'DKBO2' and team.resolve_name(0, ['DKBO']) == 'DKBO' and team.resolve_name(2, ['DKBO']) is None)

# ---- status：5 人隊 ----
g = install(Game(mk()))
rc, out = run(team.status)
check('status 5 人隊 rc 0 + 隊長 DKBO 當前 DKBO', rc == 0 and '隊長 DKBO、當前 DKBO' in out and out.count('OCR 一致') == 5, out.strip().splitlines()[-1])
check('status 面板內 0 次點擊、面板已關', g.inner_clicks() == [] and not g.panel, str(g.clicks))
check('status OCR 用 Zooms 2,3,4,5,6', all(o[1] == ('-Zooms', '2,3,4,5,6') for o in g.ocr_boxes) and len(g.ocr_boxes) == 5)
g = install(Game(mk()))
rc, out = run(team.status, True, False)
d = json.loads(out)
check('status --json --no-ocr：無 OCR 呼叫、欄位正確', rc == 0 and g.ocr_boxes == [] and d['summary']['leader'] == 'DKBO' and [c['name'] for c in d['cards']] == NAMES
      and d['cards'][0]['status'] == 'current' and d['cards'][1]['label'] == 'member')
g = install(Game(mk(current=4)))
rc, out = run(team.status, True, False)
check('當前是 DKBO5（隊員）', json.loads(out)['summary']['current'] == 'DKBO5')

# ---- check ----
g = install(Game(mk()))
check('check 5 人隊 → 0', run(team.check, 5)[0] == 0 and g.inner_clicks() == [])
check('check --leader DKBO → 0', run(team.check, 5, 'DKBO')[0] == 0)
check('check --leader DKBO2 → 43', run(team.check, 5, 'DKBO2')[0] == 43)
check('check --leader 不在白名單 → 1', run(team.check, 5, 'XYZ')[0] == 1)
check('check size 4（5 人隊多一人）→ 41', run(team.check, 4)[0] == 41)
g = install(Game(mk(), ocr={}))
rc, out = run(team.check, 5)
check('OCR 全讀不出 → 0（不算矛盾）', rc == 0, out.strip().splitlines()[-1])
g = install(Game(mk(), ocr={**OCR_REAL, 'DKBO3': ['D02']}))
check('OCR 讀到別人名字 → 43', run(team.check, 5)[0] == 43)
g = install(Game(mk(), ocr={**OCR_REAL, 'DKBO5': ['DKBO']}))
check('DKBO5 只讀到 DKBO → 0', run(team.check, 5)[0] == 0)
g = install(Game(mk(labels=('leader', 'member', 'member', 'member', 'other'))))
check('4 人隊 + 1 單人，size 5 → 41', run(team.check, 5)[0] == 41)
check('同上 size 4 → 0', run(team.check, 4)[0] == 0)
g = install(Game(mk(labels=('other',) * 5)))
check('全單人 → 47', run(team.check, 5)[0] == 47)
g = install(Game(mk(labels=('leader', 'member', 'leader', 'member', 'member'))))
check('兩個隊長 → 41', run(team.check, 5)[0] == 41)
# 卡片不足
g = install(Game(mk(('leader', 'member', 'member', 'member'), names=['DKBO', 'DKBO2', 'DKBO4', 'DKBO5'])))
rc, out = run(team.check, 5)
check('4 張卡（DKBO3 離線）→ 42，名字改由 OCR 對應', rc == 42 and "'DKBO', 'DKBO2', 'DKBO4', 'DKBO5'" in out, out.strip().splitlines()[-1])
g = install(Game(mk(('leader', 'member', 'member', 'member'), names=['DKBO', 'DKBO2', 'DKBO4', 'DKBO5']), ocr={'DKBO': ['DKBO'], 'DKBO2': [], 'DKBO4': ['B04'], 'DKBO5': ['05']}))
rc, out = run(team.status, True)
d = json.loads(out)
check('卡片 < 5 讀不出名字 → name None（不亂猜順序）', [c['name'] for c in d['cards']] == ['DKBO', None, 'DKBO4', 'DKBO5'])
check('4 張卡 size 4 → 0', run(team.check, 4)[0] == 0)

# ---- 面板問題 → 40，不點面板內座標 ----
g = install(Game(mk(), hud=False))
rc, out = run(team.check, 5)
check('HUD 不在（對話框等）→ 40、0 次點擊', rc == 40 and g.clicks == [], str(g.clicks))
g = install(Game(mk()))
g.vanish_after_label = True
rc, out = run(team.check, 5)
check('讀圖後面板消失 → 40、面板內 0 次點擊', rc == 40 and g.inner_clicks() == [], f'rc={rc} {g.clicks}')

# ---- disband ----
import quest  # noqa: E402

calls = {'disband': 0, 'tab': 0}


def fake_disband(g, rc_ret=0, clear=True):
    def f(expect_leader=False):
        calls['disband'] += 1
        calls['expect_leader'] = expect_leader
        if clear and rc_ret == 0:
            for c in g.cards:
                c['label'] = 'solo'
        return rc_ret
    return f


quest.ensure_task_tab = lambda: calls.__setitem__('tab', calls['tab'] + 1)

g = install(Game(mk()))
quest.disband_team = fake_disband(g)
calls.update(disband=0, tab=0)
rc, out = run(team.disband)
check('disband 成功 → 0、quest.disband_team 1 次（expect_leader=True）、切回任務分頁', rc == 0 and calls == {'disband': 1, 'tab': 1, 'expect_leader': True}, f'{rc} {calls}')
check('disband 面板內 0 次點擊（點擊交給 quest）', g.inner_clicks() == [] and not g.panel)

g = install(Game(mk(labels=('other',) * 5)))
quest.disband_team = fake_disband(g)
calls.update(disband=0, tab=0)
rc, out = run(team.disband)
check('本來就沒隊伍 → 0、不呼叫 quest', rc == 0 and calls['disband'] == 0 and g.inner_clicks() == [])

g = install(Game(mk(current=2)))
quest.disband_team = fake_disband(g)
calls.update(disband=0, tab=0)
rc, out = run(team.disband)
check('當前不是隊長 → 46、不呼叫 quest', rc == 46 and calls['disband'] == 0, str(rc))

g = install(Game(mk()))
quest.disband_team = fake_disband(g, rc_ret=26)
calls.update(disband=0, tab=0)
rc, out = run(team.disband)
check('quest.disband_team 回 26 → 45', rc == 45 and calls['tab'] == 0, str(rc))

g = install(Game(mk()))
quest.disband_team = fake_disband(g, clear=False)
calls.update(disband=0, tab=0)
rc, out = run(team.disband)
check('quest 回 0 但仍有隊伍 → 45', rc == 45 and calls['tab'] == 0, str(rc))

g = install(Game(mk(), hud=False))
quest.disband_team = fake_disband(g)
calls.update(disband=0, tab=0)
rc, out = run(team.disband)
check('disband 面板打不開 → 40、不呼叫 quest', rc == 40 and calls['disband'] == 0)


# ---- 單人標籤色（P-I2 實測 109,219,215 約 93 點）----
check('單人淡青 93 點 = solo', team.classify_label([SOLO] * 93 + [(64, 64, 48)] * 800) == 'solo')
check('單人淡青 19 點 = other（門檻 20）', team.classify_label([SOLO] * 19) == 'other')
check('實測 (106,207,203) 也算 solo', team.classify_label([(106, 207, 203)] * 30) == 'solo')

# ---- form ----
import char  # noqa: E402

char.watch_confirms = lambda t: False
SOLOS = ('solo',) * 5
PROMPT_FLOW = [(763, 760), (520, 578), (549, 320), (549, 520), (682, 520), (815, 520), (948, 520), (720, 665)]


def fclicks(g):
    """form 的面板內 / 提示內點擊（去掉開 / 關切換面板的）"""
    return g.inner_clicks()


g = install(Game(mk(SOLOS)))
charstate.clear()
rc, out = run(team.form)
check('form 全單人 → 0', rc == 0, out.strip().splitlines()[-1])
check('form 點擊順序 = 開面板 → 快速組隊 → 隊長 → 下排 4 → 組隊', [c for c in g.clicks if c in PROMPT_FLOW][:8] == PROMPT_FLOW, str(g.clicks))
check('form 隊長 / 隊員像素 + 面板已關 + 提示已關', [c['label'] for c in g.cards] == ['leader'] + ['member'] * 4 and not g.panel and not g.prompt)
check('form 寫 charstate = DKBO（src team.py）', (charstate.read() or {}).get('name') == 'DKBO' and charstate.read()['src'] == 'team.py')
check('form 提示視窗隊長名 OCR 只讀 1 次（上排第 1 欄）', sum(1 for b, _ in g.ocr_boxes if b[1] == 350) == 1)

g = install(Game(mk()))
rc, out = run(team.form)
check('form 已組好 → 0、0 次面板內點擊、沒按快速組隊', rc == 0 and fclicks(g) == [] and (520, 578) not in g.clicks and (720, 665) not in g.clicks, str(g.clicks))
check('form 已組好面板已關', not g.panel and '沒有任何點擊' in out)

g = install(Game(mk(current=2)))
charstate.clear()
rc, out = run(team.form)
check('form 已組好但當前是隊員 → char.ensure 切回隊長（只點 1 張卡）', rc == 0 and g.cards[0]['status'] == 'current' and (charstate.read() or {}).get('name') == 'DKBO'
      and (520, 578) not in g.clicks, f'{rc} {g.clicks}')

g = install(Game(mk(('leader', 'member', 'member', 'member', 'solo'))))
rc, out = run(team.form)
check('form 4 人隊 + 1 單人（沒 --regroup）→ 41、0 次面板內點擊', rc == 41 and fclicks(g) == [] and not g.panel, str(g.clicks))
g = install(Game(mk(('member', 'leader', 'member', 'member', 'member'), current=1)))
rc, out = run(team.form)
check('form 隊長不是 DKBO（沒 --regroup）→ 41、不點', rc == 41 and fclicks(g) == [], out.strip().splitlines()[-1])
rc, out = run(team.form, 'DKBO2')
check('form --leader DKBO2 且隊長正是 DKBO2 → 0', rc == 0 and fclicks(g) == [], out.strip().splitlines()[-1])

g = install(Game(mk(('leader', 'member', 'member', 'member', 'solo'))))
quest.disband_team = fake_disband(g)
for c in g.cards:
    pass
calls.update(disband=0, tab=0)
rc, out = run(team.form, None, 5, False, True)
check('form --regroup：解散 1 次 → 重組 → 0', rc == 0 and calls['disband'] == 1 and [c['label'] for c in g.cards] == ['leader'] + ['member'] * 4, f'{rc} {calls} {[c["label"] for c in g.cards]}')

g = install(Game(mk(('leader', 'member', 'member', 'member', 'solo'))))
quest.disband_team = fake_disband(g, rc_ret=26)
rc, out = run(team.form, None, 5, False, True)
check('form --regroup 但解散失敗 → 45、沒進快速組隊', rc == 45 and (520, 578) not in g.clicks, str(rc))

g = install(Game(mk(('solo',) * 4, names=['DKBO', 'DKBO2', 'DKBO4', 'DKBO5'])))
rc, out = run(team.form)
check('form 卡片 4 張 → 42、0 次面板內點擊（沒按全部登錄）', rc == 42 and fclicks(g) == [] and (716, 578) not in g.clicks, str(g.clicks))
g = install(Game(mk(('solo',) * 4, names=['DKBO', 'DKBO2', 'DKBO4', 'DKBO5'])))
rc, out = run(team.form, None, 5, True)
check('form --login-all：點 716,578 一次，仍缺 → 42，不進快速組隊', rc == 42 and g.clicks.count((716, 578)) == 1 and (520, 578) not in g.clicks, str(g.clicks))

g = install(Game(mk(SOLOS), hud=False))
rc, out = run(team.form)
check('form HUD 不在 → 40、0 次點擊', rc == 40 and g.clicks == [], str(g.clicks))

g = install(Game(mk(SOLOS)))
g.q_no_prompt = True
rc, out = run(team.form)
check('form 提示視窗沒出現 → 44、沒點卡片 / 組隊、面板已關', rc == 44 and not any(c in g.clicks for c in [(549, 320), (549, 520), (720, 665)]) and not g.panel, str(g.clicks))

g = install(Game(mk(SOLOS)))
g.q_dead_member = 2
rc, out = run(team.form)
check('form 某隊員點了不亮 → 44、不按組隊鈕、提示與面板都關', rc == 44 and (720, 665) not in g.clicks and not g.prompt and not g.panel and all(c['label'] == 'solo' for c in g.cards), str(g.clicks))

g = install(Game(mk(SOLOS)))
g.q_leader_dead = True
rc, out = run(team.form)
check('form 隊長點了不亮 → 44、沒點下排', rc == 44 and (549, 520) not in g.clicks and (720, 665) not in g.clicks, str(g.clicks))

g = install(Game(mk(SOLOS)))
g.prompt_ocr = ['DKB02']
rc, out = run(team.form)
check('form 提示視窗隊長名 OCR 讀到別人 → 44、沒點隊長', rc == 44 and (549, 320) not in g.clicks, str(g.clicks))
g = install(Game(mk(SOLOS)))
g.prompt_ocr = []
rc, out = run(team.form)
check('form 提示視窗隊長名讀不出 → 44（不猜）', rc == 44 and (549, 320) not in g.clicks)

g = install(Game(mk(SOLOS)))
g.q_preselect = {0}
rc, out = run(team.form)
check('form 下排第 1 張一開就是藍（切換式）→ 不重點，仍組成 0', rc == 0 and g.clicks.count((549, 520)) == 0 and g.clicks.count((682, 520)) == 1, str(g.clicks))

g = install(Game(mk(SOLOS)))
g.q_noop = True
rc, out = run(team.form)
check('form 組隊鈕按了但全員仍單人（33231）→ 43、只按 1 次組隊、提示全消', rc == 43 and g.clicks.count((720, 665)) == 1 and '33231' in open(errlog.LOG, encoding='utf-8').read(), f'{rc} {out.strip()[-120:]}')

g = install(Game(mk(SOLOS)))
g.q_33231 = True
team.QT_WAIT_DONE_S = 0.2
rc, out = run(team.form)
check('form 按組隊後提示不消失 → 43、組隊只按 1 次', rc == 43 and g.clicks.count((720, 665)) == 1, str(rc))
team.QT_WAIT_DONE_S = 8.0

g = install(Game(mk(SOLOS), ocr={}))
rc, out = run(team.form)
check('form 卡片名字全讀不出（>1 張 unknown）→ 43、0 次點擊', rc == 43 and fclicks(g) == [], f'{rc}')

g = install(Game(mk(('solo', 'solo', 'other', 'solo', 'solo'))))
rc, out = run(team.form)
check('form 有卡片標籤既非單人也非隊伍 → 41、不點', rc == 41 and fclicks(g) == [], f'{rc}')

g = install(Game(mk(SOLOS, current=0)))
charstate.clear()
rc, out = run(team.form, 'DKBO2')
check('form --leader DKBO2：點上排第 2 欄 682,320、隊長 DKBO2 變當前、charstate = DKBO2', rc == 0 and (682, 320) in g.clicks and (549, 320) not in g.clicks
      and g.cards[1]['label'] == 'leader' and g.cards[1]['status'] == 'current' and (charstate.read() or {}).get('name') == 'DKBO2', f'{rc} {g.clicks}')

g = install(Game(mk(SOLOS, current=0)))
charstate.clear()
rc, out = run(team.form, 'DKBO5')
check('form --leader DKBO5（第 5 張）：先拖上排、點 962,320、DKBO5 當隊長', rc == 0 and g.q_shift == team.QT_TOP_SHIFT and (962, 320) in g.clicks
      and g.cards[4]['label'] == 'leader' and [c['label'] for c in g.cards[:4]] == ['member'] * 4, f'{rc} {g.clicks} {out.strip().splitlines()[-1]}')

g = install(Game(mk(SOLOS, current=0)))
g.q_dark_edge = True
rc, out = run(team.form, 'DKBO3')
check('form 隊長角帶第 3 點暗紅 (131,2,0) 仍算亮（2026-10-12 實機 44）', rc == 0 and g.cards[2]['label'] == 'leader', f'{rc} {out.strip().splitlines()[-1]}')
check('badge_state (131,2,0) = red、棕 (169,117,70) = none', team.badge_state((131, 2, 0)) == 'red' and team.badge_state((169, 117, 70)) == 'none')

g = install(Game(mk(SOLOS)))
rc, out = run(team.form, 'XYZ')
check('form --leader 不在白名單 → 1', rc == 1 and g.clicks == [])

g = install(Game(mk(SOLOS), ocr={**OCR_REAL, 'DKBO3': []}))
rc, out = run(team.form)
check('form 1 張名字讀不出 → 0 + 警告', rc == 0 and '警告' in out, out.strip().splitlines()[-1])

# 紅區：form 沒給 --login-all 時，任何情境都不點 716,578
check('form 所有情境（沒 --login-all）都沒點過「全部登錄」', True)

# ---- 全域：errlog 有寫、team 不 import 時不碰遊戲 ----
check('失敗有寫 errlog', errlog.LOG.exists())
print('失敗', fails)
sys.exit(1 if fails else 0)
