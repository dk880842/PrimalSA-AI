#!/usr/bin/env python3
"""外接 1728×995 的 heal / bag / walk 玩家選單離線測試（不碰遊戲；OCR 用樣本圖經 ocr.ps1 -Image 離線讀，沒樣本 / 沒 powershell 的項目 SKIP）。
2026-10-12：heal 版面守衛走 layout.supported()、no_battle_sig 外接多點、talk_nurse 外接等待與站位；bag 彈窗按鈕列 OCR 外接門檻（根因：
筆電 -Light 170 對 0.6 倍縮小的白字全空）；walk.dismiss_player_popup 只在 5 點全中時才按 ESC。
用法：uv run --no-project python tools/gui/test_ext_heal_bag.py"""
import json
import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
fails = 0


def check(name, ok, extra=''):
    global fails
    print(('PASS ' if ok else 'FAIL ') + name, extra)
    fails += 0 if ok else 1


def skip(name, why):
    print('SKIP', name, why)


def run(lay: str, code: str):
    """子行程（常數在 import 時依 PSA_LAYOUT 決定）；最後一行是 JSON"""
    env = dict(os.environ, PSA_LAYOUT=lay, PSA_GUI_SERVER='0')
    r = subprocess.run([sys.executable, '-c', 'import sys; sys.path.insert(0, %r)\n' % str(HERE) + code], env=env,
                       capture_output=True, text=True, encoding='utf-8', timeout=180)
    if r.returncode:
        print(r.stderr)
    return json.loads(r.stdout.strip().splitlines()[-1])


# ---- heal：版面守衛、no_battle_sig、站位 / 路線 ----
HEAL = r'''
import json, heal, screen_sigs
sent = []
heal.gui = lambda *a, **k: (sent.append(a), '')[1]
heal.log = lambda *a, **k: None
import layout
heal.layout.supported = lambda: (True, '')
import uikit, os
if os.environ['PSA_LAYOUT'] == '1728x995':      # 離線沒有遊戲：模擬 uikit.sync_sig_layout 認出外接縮放視窗後套覆寫
    uikit.sync_sig_layout = lambda: screen_sigs.set_layout('1728x995')
import walk
print(json.dumps({'nb': heal.no_battle_sig(), 'spot': heal.HOSPITAL_SPOT, 'fast': heal.VILLAGE_FAST, 'phys': walk.PHYS,
                  'old_single': heal.SIG_NO_BATTLE, 'probes': screen_sigs.VS_PROBES, 'tol': screen_sigs.VS_TOL, 'layout': heal.LAYOUT}))
'''
a = run('2880x1659', HEAL)
check('heal 筆電：no_battle_sig = 原單點 SIG_NO_BATTLE、站位 / 路線不變', a['nb'] == a['old_single'] == '706,295,122,227,0!' and a['spot'] == [23, 62] and a['fast'][0] == [87, 96], a)
c = run('1728x995', HEAL)
exp = '/'.join(f'{x},{y},122,227,0!' for x, y in c['probes'])
check('heal 外接：no_battle_sig = VS_PROBES 多點全部「不是 VS 綠」（與 screen_sigs.vs_on 同一組點）', c['nb'] == exp and exp.count('/') >= 2, c['nb'])
check('heal 外接：小護士站位 (22,60)（點擊點 x ≥ 400）、村子路線第一段 (89,98)（(90,97) 點了不動）', c['spot'] == [22, 60] and c['fast'][0] == [89, 98] and c['fast'][1] == [87, 96], c)

TALK = r'''
import json, heal, walk
sent = []
def fake(*a, **k):
    sent.append(a)
    return 'ok 60' if a and a[0] == 'seq' and 'ifok' in a[1] else ''
heal.gui = fake
heal.log = lambda *a, **k: None
heal.wait_pos = lambda *a, **k: (1005, 25, 65)
heal.step_to = lambda m, x, y: (sent.append(('step_to', x, y)), (m, x, y))[1]
heal.talk_nurse((1005, 25, 65))
seq = [a[1] for a in sent if a[0] == 'seq'][0]
print(json.dumps({'seq': seq, 'steps': [a for a in sent if a[0] == 'step_to'], 'waitstill': walk.USE_WAITSTILL}))
'''
t = run('2880x1659', TALK)
check('talk_nurse 筆電：一次點 (23,62)、waitstill 2500（舊行為不變）', 'waitstill 2500' in t['seq'] and not t['steps'], t['seq'])
t = run('1728x995', TALK)
check('talk_nurse 外接：一次點不到就 step_to 分段走到 (22,60)，不用 waitstill', t['steps'] == [['step_to', 22, 60]] and 'waitstill' not in t['seq'], t)

# heal main 守衛：1920 照舊放行、外接走 layout.supported()、不支援的尺寸擋下
GUARD = r'''
import json, sys, heal
heal.log = lambda *a, **k: None
heal.winenv.enable_server = lambda: None
heal.heal_trip = lambda *a, **k: None
sys.argv = ['heal.py']
res = {}
for name, cur, sup in [('lap', '2880x1659', (True, '')), ('1920', '1920x1017', (False, 'x')), ('ext_ok', '1728x995', (True, '')), ('bad', '1584x912', (False, '樣板未就緒'))]:
    heal.layout.current = lambda c=cur: c
    heal.layout.supported = lambda s=sup: s
    res[name] = heal.main()
print(json.dumps(res))
'''
g = run('2880x1659', GUARD)
check('heal 守衛：筆電 / 1920 / 外接放行（rc 0），不支援尺寸 rc 2', g == {'lap': 0, '1920': 0, 'ext_ok': 0, 'bad': 2}, g)

# ---- bag：外接彈窗按鈕列 OCR ----
BTN = r'''
import json, bag, layout
res = {}
for name, st in [('lap', {'scaled': False}), ('ext', {'scaled': True})]:
    layout.status = lambda s=st: s
    res[name] = [list(o) for o in bag.btn_opts()]
res['base'] = [list(o) for o in bag.BTN_OPTS]
print(json.dumps(res))
'''
b = run('2880x1659', BTN)
check('bag 筆電：btn_opts() = 原 BTN_OPTS（不變）', b['lap'] == b['base'])
check('bag 外接：btn_opts() 先試低門檻 + 大倍數，再退回原組', b['ext'][:3] == [['-Light', 150, '-Zooms', '3,4,5'], ['-Light', 140, '-Zooms', '3,4'], ['-Light', 120, '-Zooms', '3']] and b['ext'][3:] == b['base'])

SAMPLES = {'depot': ROOT / 'tools/.cache/p4/depot_popup_dragon_full.png', 'bag': ROOT / 'tools/.cache/p4/bag_popup_dragon_full.png'}
OCR = r'''
import json, sys, bag, uikit
img = sys.argv[1] if len(sys.argv) > 1 else %r
'''
if all(p.exists() for p in SAMPLES.values()):
    code = r'''
import json, bag, uikit, layout
layout.status = lambda: {'scaled': True}
orig = uikit.ocr
res = {}
for name, img in %r.items():
    uikit.ocr = lambda box, *o, _i=img: orig(box, *o, '-Image', uikit.winenv.to_windows(_i))
    txt = bag._ocr_join(bag.POPUP_BTN_BOX, bag.btn_opts())
    old = bag._ocr_join(bag.POPUP_BTN_BOX, bag.BTN_OPTS)
    res[name] = {'txt': txt, 'btn': {k: v for k, v in bag.popup_buttons(txt).items()}, 'old': old}
print(json.dumps(res, ensure_ascii=False))
''' % {k: str(v) for k, v in SAMPLES.items()}
    try:
        o = run('2880x1659', code)
        check('bag 外接倉庫彈窗樣本（龍王的守護，單鈕）：按鈕列讀到「取出」→ kind depot、取出 732,648',
              '取出' in o['depot']['txt'] and o['depot']['btn'].get('kind') == 'depot' and o['depot']['btn'].get('取出') == [732, 648], o['depot'])
        check('bag 外接背包彈窗樣本（使用 + 更多並排）：讀到使用 / 更多 → kind stack、使用 618,648',
              '使用' in o['bag']['txt'] and '更多' in o['bag']['txt'] and o['bag']['btn'].get('kind') == 'stack', o['bag'])
        print('  （對照：筆電原門檻 BTN_OPTS 讀同一張外接樣本 →', repr(o['depot']['old']), '；根因見 errlog）')
    except Exception as e:   # 沒有 powershell / Windows OCR（非 Windows 環境）
        skip('bag OCR 樣本', repr(e))
else:
    skip('bag OCR 樣本', '缺 tools/.cache/p4/*_dragon_full.png')

# ---- walk：玩家選單小窗 ----
POP = r'''
import json, walk
keys, seqs = [], []
walk.log = lambda *a, **k: None
walk.time.sleep = lambda s: None
def mk(out):
    def g(*a, **k):
        if a[0] == 'key':
            keys.append(a[1]); return ''
        seqs.append(a[1]); return out
    return g
res = {}
walk.gui = mk('ok 12'); res['hit'] = walk.dismiss_player_popup(); res['keys_hit'] = list(keys)
keys.clear(); walk.gui = mk('timeout 3'); res['miss'] = walk.dismiss_player_popup(); res['keys_miss'] = list(keys)
res['seq'] = seqs[0] if seqs else ''
# step_to：每圈開頭先檢查；沒小窗時不按任何鍵
keys.clear(); calls = []
walk.gui = mk('timeout 0')
walk.wait_pos = lambda *a, **k: (1000, 90, 90)
walk.world_guard = lambda: None
r = walk.step_to(1000, 90, 90)
res['step_keys'] = list(keys); res['step_ret'] = list(r)
print(json.dumps(res))
'''
for lay in ('2880x1659', '1728x995'):
    p = run(lay, POP)
    check(f'walk 玩家選單 {lay}：5 點特徵全中 → ESC 一次；沒中 → 不按任何鍵', p['hit'] is True and p['keys_hit'] == ['{ESC}'] and p['miss'] is False and p['keys_miss'] == [] and p['seq'].startswith('waitpix 0 ') and p['seq'].endswith(' 25'), p)
    check(f'walk 玩家選單 {lay}：step_to 到點時沒小窗就不送 ESC', p['step_keys'] == [] and p['step_ret'] == [1000, 90, 90])
p = run('1920x1017', POP)
check('walk 玩家選單 1920×1017：不檢查（座標沒量）', p['hit'] is False and p['keys_hit'] == [])

# 樣本取樣（fixtures/player_popup_px.json）：只有小窗樣本 5 點全中，其他畫面都沒有
fx = json.load(open(HERE / 'fixtures' / 'player_popup_px.json', encoding='utf-8'))
sig = [tuple(int(v) for v in seg.split(',')) for seg in a_sig.split('/')] if (a_sig := run('2880x1659', 'import walk, json; print(json.dumps(walk.PLAYER_POPUP_SIG))')) else []
tol = run('2880x1659', 'import walk, json; print(json.dumps(walk.PLAYER_POPUP_TOL))')


def hits(cols):
    return sum(all(abs(c - t) <= tol for c, t in zip(col, s[2:])) for col, s in zip(cols, sig))


check('玩家選單特徵點座標 = 樣本取樣點', [tuple(p) for p in fx['pts']] == [s[:2] for s in sig])
check('玩家選單樣本：5 點全中', hits(fx['samples']['pos']) == 5)
neg = {k: hits(v) for k, v in fx['samples'].items() if k != 'pos'}
check(f'玩家選單負例 {len(neg)} 張（設置面板 / 聊天 / 待機 / 對話 / 背包彈窗 / 寵物 / 戰鬥 / 村子…）都不到 5 點', max(neg.values()) < 5, neg)

print('\n全部通過' if not fails else f'\n{fails} 項失敗')
sys.exit(1 if fails else 0)
