#!/usr/bin/env python3
"""多視窗第 3b 步離線測試：PSA_CLIENT=PrimalSA2 時基本工具改用該視窗名單（DKBO6～DKBO10，字母 O）。
不碰遊戲：假 gui（fake_switch / fake_pet）+ 測試期間 PATH 最前面放假 powershell.exe，最後確認 0 次意外呼叫。
主視窗（沒設 PSA_CLIENT）的行為由各模組原本的 test_*.py 保證不變；這支只測 PrimalSA2 情境，另外在子程序比對主視窗常數。
  uv run --no-project python tools/gui/test_roster.py
"""
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

os.environ['PSA_CLIENT'] = 'PrimalSA2'          # 必須在 import 任何 tools/gui 模組之前（名單在 import 時決定）
os.environ['PSA_TEST_PROCS'] = 'PrimalSA,PrimalSA2'
os.environ['PSA_LAYOUT'] = '2880x1659'           # layout.current() 不呼叫 gui.ps1 info（walk import 時會問）
os.environ.pop('PSA_LEADER_FIRST', None)
os.environ.pop('PSA_MOUNTS', None)

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

# ---- 假 powershell.exe（PATH 最前面，記錄每次呼叫；本測試預期 0 次）----
_tmp = Path(tempfile.mkdtemp(prefix='psa-roster-'))
(_tmp / 'bin').mkdir()
_calls = _tmp / 'ps-calls.jsonl'
_fake = _tmp / 'bin' / 'powershell.exe'
_fake.write_text('#!' + sys.executable + '\nimport json, sys\n'
                 f'open({str(_calls)!r}, "a").write(json.dumps(sys.argv[1:]) + "\\n")\nsys.exit(1)\n', encoding='utf-8')
_fake.chmod(0o755)
os.environ['PATH'] = str(_tmp / 'bin') + os.pathsep + os.environ.get('PATH', '')

import testenv  # noqa: E402,F401  紀錄檔轉向暫存
import clients  # noqa: E402
import watchstate  # noqa: E402

watchstate.CONFIG_FILE = _tmp / 'watch-config.json'          # 不讀真實設定檔
watchstate.CURCHAR_FILE = _tmp / 'current-char.json'

import charname  # noqa: E402
import charstate  # noqa: E402
import errlog  # noqa: E402
import namematch  # noqa: E402
import uikit  # noqa: E402
import team  # noqa: E402
import char  # noqa: E402
import ass  # noqa: E402
import petmatch  # noqa: E402
import pet  # noqa: E402
import petwatch  # noqa: E402
import bag  # noqa: E402
import exp  # noqa: E402
import grind  # noqa: E402
import fake_switch  # noqa: E402

errlog.LOG = _tmp / 'errlog.jsonl'
namematch.TPL_DIR = _tmp / 'name-tpl'
uikit.watch_state = lambda max_age=1.0: None
uikit.watch_screen = lambda max_age=1.0: None
P2 = ['DKBO6', 'DKBO7', 'DKBO8', 'DKBO9', 'DKBO10']
MAIN = ['DKBO', 'DKBO2', 'DKBO3', 'DKBO4', 'DKBO5']
fails = 0


def check(name, cond, extra=''):
    global fails
    print(('PASS' if cond else 'FAIL'), name, extra if not cond else '')
    if not cond:
        fails += 1


# ---- clients helper ----
check('clients.name = PrimalSA2', clients.name() == 'PrimalSA2' and not clients.is_default())
check('roster = DKBO6～DKBO10', clients.roster() == P2)
check('leader = DKBO6', clients.leader() == 'DKBO6' and clients.leader('PrimalSA') == 'DKBO')
check('leader 沒有名單 → None', clients.leader('PrimalSA9') is None)
check('index_of：DKBO10 / DKB010 / dkbo 10 → 4', [clients.index_of(x) for x in ('DKBO10', 'DKB010', 'dkbo 10')] == [4, 4, 4])
check('index_of：DKBO7 / DKB07 → 1', clients.index_of('DKBO7') == 1 and clients.index_of('DKB07') == 1)
check('index_of：DKBO1 / DKBO / DKBO5 / 空 → None（不在本視窗名單）',
      [clients.index_of(x) for x in ('DKBO1', 'DKBO', 'DKBO5', '')] == [None] * 4)
check('index_of 指定主視窗：DKB0 → 0、DKBO10 → None', clients.index_of('DKB0', 'PrimalSA') == 0 and clients.index_of('DKBO10', 'PrimalSA') is None)
check('by_slot 依名單位置配', clients.by_slot([1, 2, 3, 4, 5]) == dict(zip(P2, [1, 2, 3, 4, 5])))
check('leader_last', clients.leader_last() == P2[1:] + P2[:1] and clients.leader_last('PrimalSA') == MAIN[1:] + MAIN[:1])
check('all_names = 兩個名單聯集', clients.all_names() == MAIN + P2)

# ---- charname / charstate ----
canons = [charname.canon(x) for x in MAIN + P2]
check('10 個名字正規化後不撞（DKBO10 = DKB010 不與別人相同）', len(set(canons)) == 10, str(canons))
check('canon_map 不丟任何名字', len(charname.canon_map(MAIN + P2)) == 10)
check('charstate.DEFAULT_CHARS / LEAD', charstate.DEFAULT_CHARS == P2 and charstate.LEAD == 'DKBO6')
check('uikit.CHARS = 名單', uikit.CHARS == P2)
check('norm_char：DKB010 / dkbo10 / 0KB010 → DKBO10', [charstate.norm_char(x) for x in ('DKB010', 'dkbo10', '0KB010')] == ['DKBO10'] * 3)
check('norm_char：主視窗的 DKBO / DKBO2 → None（不在本視窗名單）', charstate.norm_char('DKBO') is None and charstate.norm_char('DKBO2') is None)
check('norm_char：DKBO1 → None', charstate.norm_char('DKBO1') is None)
check('display：DKB06 / dkb010 → 真名', charstate.display('DKB06') == 'DKBO6' and charstate.display('dkb010') == 'DKBO10')
check('display：主視窗名字也認（DKB02 → DKBO2）', charstate.display('DKB02') == 'DKBO2')
check('chars()：沒有設定檔 → 名單', charstate.chars() == P2)
check('watch_chars()：沒有設定檔也用名單（非主視窗）', charstate.watch_chars() == P2)
watchstate.CONFIG_FILE.write_text(json.dumps({'chars': MAIN}), encoding='utf-8')
check('chars()：設定檔寫主視窗名字 → 全部濾掉、回名單', charstate.chars() == P2)
watchstate.CONFIG_FILE.write_text(json.dumps({'chars': ['DKB06', 'DKBO7', 'DKBO2']}), encoding='utf-8')
check('chars()：設定檔只留名單內的（DKB06 → DKBO6；DKBO2 丟掉）', charstate.chars() == ['DKBO6', 'DKBO7'])
watchstate.CONFIG_FILE.unlink()
check('write：DKB010 → current-char.json 寫 DKBO10', charstate.write('DKB010', src='test') and charstate.read()['name'] == 'DKBO10')
check('write：主視窗名字 DKBO 不寫', not charstate.write('DKBO', src='test'))
tr = charname.NameTracker(charstate.watch_chars())
tr.feed(['DKB08'], 100.0)
tr.feed(['DKBO8'], 103.0)
check('watch NameTracker：連 2 次讀到 DKB08 → DKBO8', tr.ocr_name == 'DKBO8')

# ---- team：尾碼 / OCR 交叉確認 ----
check('suffix_tails 主視窗 = 02～05', team.suffix_tails(MAIN) == {'02': 'DKBO2', '03': 'DKBO3', '04': 'DKBO4', '05': 'DKBO5'})
check('suffix_tails PrimalSA2 = 06～09、010', team.suffix_tails(P2) == {'06': 'DKBO6', '07': 'DKBO7', '08': 'DKBO8', '09': 'DKBO9', '010': 'DKBO10'}
      or team.suffix_tails(P2) == {'07': 'DKBO7', '08': 'DKBO8', '09': 'DKBO9', '010': 'DKBO10'}, str(team.suffix_tails(P2)))
check('name_hits：07 → DKBO7', team.name_hits(['07'])[0] == {'DKBO7'})
check('name_hits：010 / D010 → DKBO10', team.name_hits(['010'])[0] == {'DKBO10'} and team.name_hits(['D010'])[0] == {'DKBO10'})
check('name_hits：10 太短 → 不認', team.name_hits(['10'])[0] == set())
check('name_hits：DKBO6 = 隊長 → bare', team.name_hits(['DKBO6']) == (set(), True))
check('name_hits：主視窗名字 DKBO2 / 02 → 不認', team.name_hits(['DKBO2'])[0] == set() and team.name_hits(['02'])[0] == set())
check('cross_check：順序 DKBO10、OCR DKB010 → ok', team.cross_check('DKBO10', ['DKB010']) == 'ok')
check('cross_check：順序 DKBO9、OCR 07 → conflict', team.cross_check('DKBO9', ['07']) == 'conflict')
check('cross_check：順序 DKBO6、OCR DKBO6 → ok', team.cross_check('DKBO6', ['DKBO6']) == 'ok')
check('fake_switch 名單 = PrimalSA2', fake_switch.NAMES == P2 and set(fake_switch.OCR_REAL) == set(P2))


def fake_time():
    t = [0.0]

    def clk():
        t[0] += 0.05
        return t[0]
    uikit.clock = clk


# status：5 張卡、順序 + OCR 交叉確認
g = fake_switch.install(fake_switch.Game(fake_switch.mk()))
fake_time()
r = team.read_state(True)
names = [c.name for c in r['cards']]
checks = [c.check for c in r['cards']]
check('team.read_state：5 張卡名字 = DKBO6～10、OCR 都 ok', r['ok'] and names == P2 and checks == ['ok'] * 5, f'{names} {checks}')
rc, out = fake_switch.run(team.check, 5, None, True)
check('team.check：預設隊長 DKBO6 → 0', rc == 0, out[-300:])
rc, out = fake_switch.run(team.check, 5, 'DKBO7', True)
check('team.check --leader DKBO7 → 43（隊長不是 DKBO7）', rc == team.EXIT_OCR_CONFLICT, out[-300:])

# 卡片 < 5（DKBO8 離線，補位）：只靠 OCR
g = fake_switch.install(fake_switch.Game(fake_switch.mk(names=['DKBO6', 'DKBO7', 'DKBO9', 'DKBO10'])))
r = team.read_state(True)
check('卡片 4 張：OCR 解出 DKBO6 / 7 / 9 / 10', [c.name for c in r['cards']] == ['DKBO6', 'DKBO7', 'DKBO9', 'DKBO10'], str([c.name for c in r['cards']]))

# form：全員單人 → 快速組隊，隊長 DKBO6
g = fake_switch.install(fake_switch.Game(fake_switch.mk(labels=('solo',) * 5, current=2)))
fake_time()
rc, out = fake_switch.run(team.form)
labels = [c['label'] for c in g.cards]
check('team.form（PrimalSA2）：全員單人 → 隊長 DKBO6 + 4 隊員', rc == 0 and labels == ['leader'] + ['member'] * 4, out[-400:])
check('form 後當前 = DKBO6、旁路檔寫 DKBO6', g.cards[0]['status'] == 'current' and charstate.read()['name'] == 'DKBO6')

# form 隊長 DKBO10（第 5 張：上排要往左拖）
g = fake_switch.install(fake_switch.Game(fake_switch.mk(labels=('solo',) * 5, current=4)))
fake_time()
rc, out = fake_switch.run(team.form, 'DKB010')
check('team.form --leader DKB010：第 5 張拖完 OCR 確認 → 隊長 DKBO10', rc == 0 and g.cards[4]['label'] == 'leader', out[-400:])

# char.switch
g = fake_switch.install(fake_switch.Game(fake_switch.mk()))
fake_time()
rc, out = fake_switch.run(char.switch, 'DKB09')
check('char.switch DKB09 → 當前 DKBO9', rc == 0 and g.cards[3]['status'] == 'current', out[-300:])
rc, out = fake_switch.run(char.switch, 'DKBO2')
check('char.switch 主視窗名字 DKBO2 → 用法錯誤、不點', rc == uikit.EXIT_USAGE, out[-300:])

# ---- namematch：新名字第一次學（OCR 精確命中才學）+ 存檔不洗掉別視窗的樣板 ----
import random  # noqa: E402


def rows_for(label):
    rnd = random.Random(label)
    return [''.join('1' if rnd.random() < 0.15 else '0' for _ in range(namematch.CW_)) for _ in range(namematch.CH_)]


namematch.TPL_DIR.mkdir(parents=True, exist_ok=True)
main_tpl = {n: [format(namematch.rows_to_int(rows_for(n)), 'x')] for n in MAIN}
namematch.tpl_path().write_text(json.dumps(main_tpl), encoding='utf-8')
check('load_tpl：只載入本視窗名單（主視窗樣板不載入）', namematch.load_tpl() == {})
g = fake_switch.install(fake_switch.Game(fake_switch.mk()))
g.panel = True
g.ocr_map = dict(fake_switch.OCR_REAL, DKBO9=[])                # DKBO9 OCR 讀不出
namematch.capture = lambda: {i: rows_for(P2[i]) for i in range(5)}
logs = []
rc = namematch.learn(logs.append)
saved = json.loads(namematch.tpl_path().read_text(encoding='utf-8'))
check('learn：OCR 確認的 4 人學起來、DKBO9 讀不出先不學', rc == 0 and set(namematch.load_tpl()) == {'DKBO6', 'DKBO7', 'DKBO8', 'DKBO10'}, '\n'.join(logs))
check('learn 存檔：主視窗 DKBO～DKBO5 樣板原樣保留', all(saved.get(n) == main_tpl[n] for n in MAIN), str(list(saved)))
g.ocr_map = dict(fake_switch.OCR_REAL)
rc = namematch.learn(logs.append)
check('再學一次（DKBO9 OCR 讀到了）→ 5 人都有樣板', rc == 0 and set(namematch.load_tpl()) == set(P2))
check('read_names：5 張全命中', namematch.read_names({i: rows_for(P2[i]) for i in range(5)}) == dict(enumerate(P2)))

# ---- 座標表依名單位置 ----
check('petmatch.AVATAR_Y 依名單', petmatch.AVATAR_Y == dict(zip(P2, petmatch.AVATAR_YS)) and petmatch.AVATAR_TOP_Y == dict(zip(P2, petmatch.AVATAR_TOP_YS)))
check('petmatch.avatar_box(DKBO10) = 第 5 個位置', petmatch.avatar_box('DKBO10') == (56, 700 + petmatch.AVATAR_NAME_DY, 54, 24))
check('petwatch.CHARS / AVATAR_Y', petwatch.CHARS == P2 and petwatch.AVATAR_Y['DKBO8'] == 450)
check('ass.ROLES：DKBO8 在第 3 個頭像 (461,151)', list(ass.ROLES) == P2 and ass.ROLES['DKBO8'] == (461, 151))
check('ass.MARQUEE_ROLES = 第 3 個（DKBO8）', ass.MARQUEE_ROLES == ('DKBO8',))
check('ass.norm_role：dkb010 → DKBO10；DKBO → None', ass.norm_role('dkb010') == 'DKBO10' and ass.norm_role('DKBO') is None)
check('ass.ordered_roles：隊長 DKBO6 放最後', ass.ordered_roles(P2) == P2[1:] + ['DKBO6'])
check('ass.QUEST_BATTLE：PrimalSA2 只查 5 人自動戰鬥（隊長首次動作沒量過、不查）',
      ass.QUEST_BATTLE == {r: {'自動戰鬥': True} for r in P2[1:] + ['DKBO6']} and list(ass.QUEST_BATTLE)[-1] == 'DKBO6')
os.environ['PSA_LEADER_FIRST'] = '水的精靈'
qb = ass.quest_battle()
check('PSA_LEADER_FIRST 覆寫隊長首次動作', qb['DKBO6'] == {'自動戰鬥': True, 'first': '水的精靈', 'first_on': True})
del os.environ['PSA_LEADER_FIRST']
check('quest_battle(None) 不查首次動作', 'first' not in ass.quest_battle(None)['DKBO6'])
check('ass.main 用法：主視窗名字 DKBO2 → 1', fake_switch.run(ass.main, ['get', 'DKBO2'])[0] == ass.EXIT_USAGE)
check('pet.role_list(all) = 名單', pet.role_list('all') == P2 and pet.role_list('DKB010') == ['DKBO10'] and pet.role_list('DKBO') is None)
check('pet.roles_multi', pet.roles_multi('DKBO7,dkb010') == ['DKBO7', 'DKBO10'])
check('bag._roles(all) = 名單', bag._roles('all') == P2 and bag._roles('DKBO2') is None)
check('exp.ROLES / norm_roles', exp.ROLES == P2 and exp.norm_roles('dkb06,DKB010') == ['DKBO6', 'DKBO10'])
try:
    exp.norm_roles('DKBO')
    ok = False
except ValueError:
    ok = True
check('exp.norm_roles 主視窗名字 → ValueError', ok)
check('grind.LEADER / ROLE_ORDER', grind.LEADER == 'DKBO6' and grind.ROLE_ORDER == P2[1:] + ['DKBO6'])
check('pet.depot_fix_names 預設角色 = 隊長', pet.depot_fix_names.__defaults__[0] == 'DKBO6')

# ---- pet：頭像名字樣板（非主視窗第一次學要 OCR 精確命中）----
import fake_pet  # noqa: E402
petmatch.TPL_DIR = _tmp / 'pet-tpl'
pg = fake_pet.install(fake_pet.Game(panel=True))
check('fake_pet 預設角色 = DKBO6', pg.role == 'DKBO6' and set(pg.pets) == set(P2))
ctx = {'tpl': {}, 'learn': True, 'dirty': False}
check('check_avatar_name：OCR 讀不到 → 不學、不當不符', pet.check_avatar_name('DKBO7', ctx) and not ctx['tpl'].get('avatar'))
pg.avatar_ocr = True
check('OCR 讀到 DKBO7 → 學', pet.check_avatar_name('DKBO7', ctx) and 'DKBO7' in ctx['tpl'].get('avatar', {}))
pg.avatar_label = {'DKBO8': 'DKBO9'}
check('OCR 讀到別人（DKBO9）→ 不符', not pet.check_avatar_name('DKBO8', ctx) and 'DKBO8' not in ctx['tpl']['avatar'])
check('第 5 個頭像（DKBO10）名字在面板外 → 不核對', pet.check_avatar_name('DKBO10', ctx) and 'DKBO10' not in ctx['tpl']['avatar'])

# ---- 主視窗常數不變（子程序，不設 PSA_CLIENT）----
code = ('import sys; sys.path.insert(0, %r); import testenv, json, charstate, ass, petmatch, petwatch, grind, exp, uikit; '
        'print(json.dumps([charstate.DEFAULT_CHARS, charstate.LEAD, ass.ROLES, ass.QUEST_BATTLE, list(ass.MARQUEE_ROLES), '
        'petmatch.AVATAR_Y, petmatch.AVATAR_TOP_Y, petwatch.CHARS, petwatch.AVATAR_Y, grind.LEADER, grind.ROLE_ORDER, exp.ROLES, uikit.MOUNTS]))') % str(HERE)
env = {k: v for k, v in os.environ.items() if k not in ('PSA_CLIENT',)}
env['PSA_TEST_PROCS'] = 'PrimalSA'
p = subprocess.run([sys.executable, '-c', code], capture_output=True, text=True, env=env, cwd=str(HERE))
want = [MAIN, 'DKBO',
        {'DKBO': [137, 151], 'DKBO2': [298, 151], 'DKBO3': [461, 151], 'DKBO4': [137, 204], 'DKBO5': [298, 204]},
        {'DKBO2': {'自動戰鬥': True}, 'DKBO3': {'自動戰鬥': True}, 'DKBO4': {'自動戰鬥': True}, 'DKBO5': {'自動戰鬥': True},
         'DKBO': {'自動戰鬥': True, 'first': '風的精靈', 'first_on': True}}, ['DKBO3'],
        {'DKBO': 195, 'DKBO2': 322, 'DKBO3': 450, 'DKBO4': 580, 'DKBO5': 700},
        {'DKBO': 156, 'DKBO2': 285, 'DKBO3': 413, 'DKBO4': 542, 'DKBO5': 671},
        MAIN, {'DKBO': 195, 'DKBO2': 322, 'DKBO3': 450, 'DKBO4': 580, 'DKBO5': 700},
        'DKBO', ['DKBO2', 'DKBO3', 'DKBO4', 'DKBO5', 'DKBO'], MAIN, ['瑪斯貝卡', '布拉奇多斯']]
try:
    got = json.loads(p.stdout.strip().splitlines()[-1])
except (ValueError, IndexError):
    got = None
check('主視窗（沒設 PSA_CLIENT）：名單 / 隊長 / 座標表 / QUEST_BATTLE / 騎寵名單與改版前逐字相同', got == want, f'{got} {p.stderr[-500:]}')
check('主視窗 QUEST_BATTLE 順序（隊長最後）', got is not None and list(got[3]) == ['DKBO2', 'DKBO3', 'DKBO4', 'DKBO5', 'DKBO'])
env['PSA_MOUNTS'] = '烏力,瑪斯貝卡'
p = subprocess.run([sys.executable, '-c', 'import sys; sys.path.insert(0, %r); import testenv, uikit; print(uikit.MOUNTS)' % str(HERE)],
                   capture_output=True, text=True, env=env, cwd=str(HERE))
check('PSA_MOUNTS 追加騎寵（不重複）', p.stdout.strip() == "['瑪斯貝卡', '布拉奇多斯', '烏力']", p.stdout + p.stderr[-300:])

calls = _calls.read_text(encoding='utf-8').splitlines() if _calls.exists() else []
check('假 powershell.exe 0 次意外呼叫', not calls, str(calls[:3]))
print(f'失敗 {fails}')
sys.exit(1 if fails else 0)
