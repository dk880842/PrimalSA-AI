#!/usr/bin/env python3
"""pet.py（list / set-state / rest-all）+ petmatch 離線測試：不碰遊戲，假 gui 依設定畫寵物面板（fake_pet.Game）。
用法：uv run --no-project python tools/gui/test_pet.py"""
import contextlib
import io
import json
import sys
import tempfile
import time
import types
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import testenv  # noqa: E402,F401  紀錄檔轉向暫存（不污染真 actions.log / quest-events.log / errlog）
import errlog  # noqa: E402
import fake_pet  # noqa: E402
import heal  # noqa: E402
import petmatch  # noqa: E402
import uikit  # noqa: E402
from fake_pet import Game, install, mk_pets  # noqa: E402
import pet  # noqa: E402
import winenv  # noqa: E402
winenv.long_args_ok = lambda script='gui.ps1': True   # 模擬 pet.py main 的常駐 server 路徑：大塊取樣一次送完（fake_pet 的 EXP 橫幅以「單次 >5000 點」計次；不走 server 時 uikit.px 會分批，見 test_char）

errlog.LOG = Path(tempfile.mkdtemp()) / 'errlog.jsonl'
sys.modules['grind'] = types.SimpleNamespace(_other_running=lambda: None)      # 不讀真實鎖檔 / /proc
fails = 0
GAMES = []


def check(name, cond, extra=''):
    global fails
    print(('PASS' if cond else 'FAIL'), name, extra)
    if not cond:
        fails += 1


def fresh_tpl():
    petmatch.TPL_DIR = Path(tempfile.mkdtemp())


def new(**kw):
    g = install(Game(**kw))
    pet.RENAME_ON = False          # 本檔測舊流程（成長字串卡 = --no-rename）；存倉前還原名字 / reset-name / depot-fix-names 見 test_pet_rename.py
    GAMES.append(g)
    return g


def run(fn, *a, **k):
    buf, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(err):
        rc = fn(*a, **k)
    return rc, buf.getvalue(), err.getvalue()


def last_json(out):
    return json.loads(out.strip().splitlines()[-1])


def btn_clicks(g):
    return [c for c in g.clicks if c[1] == 702]


# ---------------- 純函式 ----------------
check('退出碼常數 70～74、78', (pet.EXIT_PANEL, pet.EXIT_SELECT, pet.EXIT_NAME, pet.EXIT_FORBID, pet.EXIT_NOCHANGE, pet.EXIT_BATTLE) == (70, 71, 72, 73, 74, 78))
check('role_list：all / 單一角色照舊（主視窗）', pet.role_list('all') == ['DKBO', 'DKBO2', 'DKBO3', 'DKBO4', 'DKBO5'] and pet.role_list('dkb03') == ['DKBO3'] and pet.role_list('DKBO6') is None)
check('role_list 逗號清單（檔頭範例 DKBO,DKBO3）→ 照名單順序', pet.role_list('DKBO3,DKB0') == ['DKBO', 'DKBO3'] and pet.role_list('DKBO,DKBO9') is None)
check('狀態別名：休息 = 等待、戰鬥 = 出戰、亂字 = None', (pet.norm_state('休息'), pet.norm_state('戰鬥'), pet.norm_state('騎乘'), pet.norm_state('跑')) == ('等待', '出戰', '騎乘', None))
ON, OFF = (182, 124, 60), (245, 225, 192)
check('btn_state：只有出戰亮', pet.btn_state({'出戰': [ON, ON], '騎乘': [OFF, OFF], '等待': [OFF, OFF]}) == '出戰')
check('btn_state：兩顆都亮 / 都不亮 / 只亮一點 → None', pet.btn_state({'出戰': [ON, ON], '騎乘': [ON, ON], '等待': [OFF, OFF]}) is None
      and pet.btn_state({'出戰': [OFF, OFF], '騎乘': [OFF, OFF], '等待': [OFF, OFF]}) is None
      and pet.btn_state({'出戰': [ON, OFF], '騎乘': [OFF, OFF], '等待': [OFF, OFF]}) is None)
check('實測色：騎乘亮 (186,129,64)、未亮 (245,225,194)', pet.is_btn_on((186, 129, 64)) and not pet.is_btn_on((245, 225, 194)) and pet.is_btn_on((178, 112, 51)))
check('格子框：選中 (251,146,4)/(248,184,5) 是、(196,183,155) 否', pet.is_frame_sel((251, 146, 4)) and pet.is_frame_sel((248, 184, 5)) and not pet.is_frame_sel((196, 183, 155)))
check('頭像黃框：(243,195,74) 是、(211,191,163) 否', pet.is_avatar_sel((243, 195, 74)) and not pet.is_avatar_sel((211, 191, 163)))
check('爪印：4 點 = 預期色 → 空格；有一點差很多 → 不是', pet.is_paw([c for _, _, c in pet.PAW]) and not pet.is_paw([(30, 60, 90)] + [c for _, _, c in pet.PAW][1:]))
sl = lambda n, name, st, **k: dict({'slot': n, 'empty': False, 'name': name, 'state': st, 'mountlike': False}, **k)    # noqa: E731
todo, ref = pet.plan_rest([sl(1, '瑪斯貝卡', '騎乘', mountlike=True), sl(2, '迪基格斯', '出戰'), sl(3, '魯尼帖斯', '等待'), {'slot': 4, 'empty': True}], ['瑪斯貝卡'], None)
check('plan_rest：只動出戰的非騎寵', [x['slot'] for x in todo] == [2] and ref == [])
todo, ref = pet.plan_rest([sl(1, '瑪斯貝卡', '出戰', mountlike=True), sl(2, '迪基格斯', '出戰')], ['瑪斯貝卡'], None)
check('plan_rest：keep 名單內即使出戰也不動', [x['slot'] for x in todo] == [2])
todo, ref = pet.plan_rest([sl(1, None, '出戰'), sl(2, '迪基格斯', '出戰')], ['瑪斯貝卡'], None)
check('plan_rest：出戰但名字讀不出來 → 拒絕（不猜）', [x['slot'] for x in todo] == [2] and [r[0]['slot'] for r in ref] == [1])
todo, ref = pet.plan_rest([sl(1, '迪基格斯', '出戰'), sl(2, '魯尼帖斯', '出戰')], ['瑪斯貝卡'], ['魯尼帖斯'])
check('plan_rest：--only 只處理指定名字', [x['slot'] for x in todo] == [2])
todo, ref = pet.plan_rest([sl(1, '迪基格斯', '出戰', mountlike=True)], [], None)
check('plan_rest：名字「像」騎寵（mountlike）不動', todo == [])
_u = dict(sl(1, None, '出戰'), img_species='貝魯卡', img_score=0.93)
todo, ref = pet.plan_rest([_u, sl(2, '迪基格斯', '出戰')], ['瑪斯貝卡'], None)
check('plan_rest：名字讀不出但縮圖認得（貝魯卡，S5 恐龍博士）→ 照改等待', [x['slot'] for x in todo] == [1, 2] and ref == [], str(ref))
todo, ref = pet.plan_rest([dict(sl(1, None, '出戰'), img_species='瑪斯貝卡')], ['瑪斯貝卡'], None)
check('plan_rest：縮圖認成騎寵 / keep → 不當成可改（拒絕，不猜）', todo == [] and [r[0]['slot'] for r in ref] == [1])
todo, ref = pet.plan_rest([_u, sl(2, '魯尼帖斯', '出戰')], ['瑪斯貝卡'], ['魯尼帖斯'])
check('plan_rest：--only 用縮圖物種比（貝魯卡不在清單 → 不動）', [x['slot'] for x in todo] == [2] and ref == [])

# ---------------- petmatch ----------------
fresh_tpl()
rows_a = [''.join('1' if v else '0' for v in r) for r in fake_pet.blob_bitmap('甲', 200, 45)]
rows_b = [''.join('1' if v else '0' for v in r) for r in fake_pet.blob_bitmap('乙', 200, 45)]
stride = 200 + 2 * petmatch.PAD
check('整塊圖 IoU：同圖 1.0、不同圖 < 0.5', petmatch.iou(petmatch.pack(rows_a), petmatch.pack(rows_a), stride) == 1.0 and petmatch.iou(petmatch.pack(rows_a), petmatch.pack(rows_b), stride) < 0.5)
tpl = petmatch.load_tpl()
check('沒檔 → 空樣板、match 回 None', tpl == {'name': {}, 'avatar': {}, 'digit': {}} and petmatch.match_whole('name', rows_a, tpl)[0] is None)
check('learn_whole：新標籤成功、重複不再存', petmatch.learn_whole('name', '甲', rows_a, tpl) and not petmatch.learn_whole('name', '甲', rows_a, tpl) and len(tpl['name']['甲']) == 1)
check('learn_whole：同一張圖想學成別的標籤 → 拒絕（標籤可疑）', not petmatch.learn_whole('name', '丙', rows_a, tpl) and '丙' not in tpl['name'])
petmatch.learn_whole('name', '乙', rows_b, tpl)
check('match_whole：甲 / 乙 各命中自己', petmatch.match_whole('name', rows_a, tpl)[0] == '甲' and petmatch.match_whole('name', rows_b, tpl)[0] == '乙')
shifted = [r[1:] + '0' for r in rows_a]
check('平移 1 px 仍命中甲', petmatch.match_whole('name', shifted, tpl)[0] == '甲')
check('墨點太少 → None', petmatch.match_whole('name', ['0' * 200] * 45, tpl)[0] is None)
petmatch.save_tpl(tpl)
check('save / load 往返', petmatch.load_tpl()['name'].keys() == tpl['name'].keys())


def lvl_rows(n):
    return [''.join('1' if v else '0' for v in r) for r in fake_pet.lvl_bitmap(n)]


tpl = petmatch.load_tpl()
check('沒學過單字 → read_level None', petmatch.read_level(lvl_rows(128), tpl) is None)
check('learn_level(128) 學到 1 2 8 轉', petmatch.learn_level(lvl_rows(128), 128, tpl) == 4 and set(tpl['digit']) == {'1', '2', '8', '轉'})
check('學過的值讀回 128', petmatch.read_level(lvl_rows(128), tpl) == 128)
check('只學過 1 2 8 → 130 含沒學過的 3 / 0 → None（不會讀成別的）', petmatch.read_level(lvl_rows(130), tpl) is None)
petmatch.learn_level(lvl_rows(130), 130, tpl)
check('再學 130 後 130 / 128 / 28 都讀得對（28 = 2 位數）', [petmatch.read_level(lvl_rows(n), tpl) for n in (130, 128, 28)] == [130, 128, 28])
check('少一位不會讀錯：學過 1 2 8 3 0；遮掉最左邊的字（只剩 28 + 轉）也只會是 28 不是 128', petmatch.read_level(lvl_rows(28), tpl) == 28)
check('單字樣板已能高分認出就不重複存', petmatch.learn_level(lvl_rows(128), 128, tpl) == 0)
check('空畫面 → None', petmatch.read_level(['0' * 110] * 34, tpl) is None)

# ---------------- 等級樣板污染（2026-10-13 卡坦練雞：33 讀成 10 / 17）----------------
import copy  # noqa: E402
POISON = json.load(open(HERE / 'fixtures' / 'pet_digit_poisoned.json', encoding='utf-8'))['digit']


def compose(glyphs, h=34, gap=3):
    """實機單字樣板（fixture）排成「0轉NN」一列點陣（BOX_LVL 寬 110）"""
    grid = [['0'] * petmatch.BOX_LVL[2] for _ in range(h)]
    x = 8
    for g in glyphs:
        y0 = h - 4 - len(g)
        for yy, r in enumerate(g):
            for xx, c in enumerate(r):
                if c == '1':
                    grid[y0 + yy][x + xx] = '1'
        x += len(g[0]) + gap
    return [''.join(r) for r in grid]


rows33 = compose([POISON['0'][0], POISON['轉'][2], POISON['3'][0], POISON['3'][0]])
t = {'digit': copy.deepcopy(POISON)}
pr = petmatch.prune_digits(t)
check('prune_digits：實機樣板清掉 1 的 9 / 3 字形、轉 裡的 2（共 3 個），其他不動',
      sorted((c, i) for c, i, _ in pr) == [('1', 1), ('1', 3), ('轉', 1)] and len(t['digit']['2']) == 2 and len(t['digit']['轉']) == 3, str(pr))
check('prune_digits：清完再跑一次沒東西可清', petmatch.prune_digits(t) == [])
check('清完讀 33 仍是 33', petmatch.read_level(rows33, t) == 33)
check('level_consistent：33 對、10 / 17 / 3 / 133 都矛盾', petmatch.level_consistent(rows33, 33, t)
      and not any(petmatch.level_consistent(rows33, v, t) for v in (10, 17, 3, 133)))
check('learn_level：OCR 錯值 17 學不進去（字已被 3 認出 → 標籤可疑，整次不學）', petmatch.learn_level(rows33, 17, t) == 0 and len(t['digit']['1']) == 2)
t0 = {'digit': {'1': copy.deepcopy(POISON['1'][:1]) + [POISON['1'][2]], '轉': [POISON['轉'][2]], '0': POISON['0']}}
check('learn_level：沒有 3 的樣板時，3 想學成 1（跟既有的 1 都不像）→ 不學', petmatch.learn_level(rows33, 13, t0) == 0 and len(t0['digit']['1']) == 2)
damaged = compose([POISON['0'][0], POISON['轉'][2], [r[:4] + '0' * (len(r) - 4) for r in POISON['3'][0]], POISON['3'][0]])   # 第一個 3 被浮字蓋掉一半
check('第一個 3 被蓋住 → 樣板讀不出（None，不猜）', petmatch.read_level(damaged, t) is None)
check('蓋住時 OCR 共識 17 / 3 → 跟畫面矛盾（不採用）', not petmatch.level_consistent(damaged, 17, t) and not petmatch.level_consistent(damaged, 3, t))
_ocr_real = pet.ocr_level_consensus
ctx_l = {'tpl': t, 'learn': False, 'dirty': False}
pet.ocr_level_consensus = lambda: 17
check('level_from_rows：樣板讀不出 + OCR 17 矛盾 → (None, ocr-conflict:17)', pet.level_from_rows(damaged, ctx_l) == (None, 'ocr-conflict:17'))
half = compose([POISON['0'][0], POISON['轉'][2], [r[:7] + '0' * (len(r) - 7) for r in POISON['3'][0]], POISON['3'][0]])    # 左半個 3 還在（切得出、認不出）
check('第一個 3 剩左半（認不出）→ 樣板 None', petmatch.read_level(half, t) is None)
pet.ocr_level_consensus = lambda: 33
check('level_from_rows：認不出的字不算矛盾，OCR 33 → (33, ocr)', pet.level_from_rows(half, ctx_l) == (33, 'ocr'))
pet.ocr_level_consensus = lambda: 17
check('level_from_rows：OCR 17 跟認得的 3 矛盾 → None', pet.level_from_rows(half, ctx_l)[0] is None)
check('level_from_rows：樣板讀得到 → tpl（不呼叫 OCR）', pet.level_from_rows(rows33, ctx_l) == (33, 'tpl'))
pet.ocr_level_consensus = lambda: None
check('level_from_rows：都讀不到 → (None, None)', pet.level_from_rows(damaged, ctx_l) == (None, None))
pet.ocr_level_consensus = _ocr_real
_d = Path(tempfile.mkdtemp())
petmatch.TPL_DIR = _d
petmatch.save_tpl({'name': {}, 'avatar': {}, 'digit': copy.deepcopy(POISON)})
c2 = pet.load_ctx(False)
check('load_ctx：讀到被污染的樣板 → 清掉並標 dirty（save_ctx 寫回）', c2['dirty'] and '轉' in c2['tpl']['digit'] and len(c2['tpl']['digit']['1']) == 2)
pet.save_ctx(c2)
check('save_ctx 後檔案是清過的', len(petmatch.load_tpl()['digit']['1']) == 2 and not pet.load_ctx(False)['dirty'])

# ---------------- 實機 fixture（P-I5 2026-10-11）----------------
R = json.load(open(HERE / 'fixtures' / 'pet_real.json', encoding='utf-8'))
tc = lambda l: [tuple(c) for c in l]    # noqa: E731
check('實測色：三顆鈕各自亮時 btn_state 正確（出戰 / 騎乘 / 休息）',
      [pet.btn_state({s: tc(R['btn'][s]) if s == on else tc(R['btn_off'][{'出戰': '出戰_騎乘亮時', '騎乘': '騎乘_出戰亮時', '等待': '休息_出戰亮時'}[s]]) for s in pet.STATES}) for on in pet.STATES] == ['出戰', '騎乘', '等待'])
check('實測色：選中 / 沒選的格框、5 個頭像黃框、非選中頭像', all(pet.is_frame_sel(tuple(c)) for c in R['frame_sel']) and not any(pet.is_frame_sel(tuple(c)) for c in R['frame_off'])
      and all(pet.is_avatar_sel(tuple(c)) for c in R['avatar_sel'].values()) and not any(pet.is_avatar_sel(tuple(c)) for c in R['avatar_off']))
check('實測色：空格爪印 3 格都判空；有寵物的 2 格都判非空', all(pet.is_paw(tc(v)) for v in R['paw'].values()) and not any(pet.is_paw(tc(v)) for v in R['pet_px'].values()))
fresh_tpl()
tpl = petmatch.load_tpl()
nm, lv = R['name_rows'], R['lvl_rows']
ps = lambda a, b: petmatch.iou(petmatch.pack(a), petmatch.pack(b), len(a[0]) + 2 * petmatch.PAD)    # noqa: E731
check('實測名字圖：瑪斯貝卡 vs 迪基格斯 IoU < 0.5（實測 0.366）', ps(nm['瑪斯貝卡'], nm['迪基格斯']) < 0.5, f'{ps(nm["瑪斯貝卡"], nm["迪基格斯"]):.3f}')
petmatch.learn_whole('name', '瑪斯貝卡', nm['瑪斯貝卡'], tpl)
petmatch.learn_whole('name', '迪基格斯', nm['迪基格斯'], tpl)
check('實測名字圖：各自命中自己', petmatch.match_whole('name', nm['瑪斯貝卡'], tpl)[0] == '瑪斯貝卡' and petmatch.match_whole('name', nm['迪基格斯'], tpl)[0] == '迪基格斯')
check('實測等級黃字：沒學過 → None；學 128 後 128 讀得對、130（沒學過 3 / 0）→ None 不會讀成別的',
      petmatch.read_level(lv['128'], tpl) is None and petmatch.learn_level(lv['128'], 128, tpl) >= 3 and petmatch.read_level(lv['128'], tpl) == 128 and petmatch.read_level(lv['130'], tpl) is None)
petmatch.learn_level(lv['130'], 130, tpl)
check('實測等級黃字：再學 130 → 兩個都讀對', [petmatch.read_level(lv['128'], tpl), petmatch.read_level(lv['130'], tpl)] == [128, 130])

# ---------------- list ----------------
fresh_tpl()
g = new()
rc, out, err = run(pet.list_roles, 'all')
j = last_json(out)
check('list all：rc 0、5 角色 × 5 格', rc == 0 and list(j['roles']) == fake_pet.ROLES and all(len(v) == 5 for v in j['roles'].values()), out[-300:])
d = j['roles']['DKBO2']
check('list：DKBO2 第 1 格 瑪斯貝卡 騎乘 128、第 2 格 迪基格斯 出戰 130、3～5 空',
      (d[0]['name'], d[0]['state'], d[0]['level'], d[1]['name'], d[1]['state'], d[1]['level']) == ('瑪斯貝卡', '騎乘', 128, '迪基格斯', '出戰', 130) and all(x['empty'] for x in d[2:]))
check('list：瑪斯貝卡 mountlike', d[0]['mountlike'] is True and d[1]['mountlike'] is False)
check('list：沒有任何狀態鈕點擊', btn_clicks(g) == [] and g.state_clicks == [])
check('list：面板本來沒開 → 結束時關掉', not g.panel and g.clicks[-1] == uikit.PET.close_xy, str(g.clicks[-3:]))
check('list：第一次靠 OCR 學樣板、之後走樣板（DKBO3 起 via=tpl）', j['roles']['DKBO'][0]['via'] == 'ocr' and j['roles']['DKBO3'][0]['via'] == 'tpl' and j['roles']['DKBO3'][0]['lv_via'] == 'tpl', str(j['roles']['DKBO3'][0]))
tp = petmatch.load_tpl()
check('樣板檔：2 個名字、數字 1 2 8 3 0 轉、頭像名 4 個（DKBO5 沒有）', set(tp['name']) == {'瑪斯貝卡', '迪基格斯'} and {'1', '2', '8', '3', '0', '轉'} <= set(tp['digit']) and set(tp['avatar']) == {'DKBO', 'DKBO2', 'DKBO3', 'DKBO4'}, str(set(tp['avatar'])))
n0 = len(g.ocr_calls)
rc, out, err = run(pet.list_roles, 'DKBO4')
check('第二次 list：完全不用 OCR（樣板）', rc == 0 and len(g.ocr_calls) == n0, f'{len(g.ocr_calls) - n0} 次 OCR')
check('list --role DKB04（舊寫法）也收', run(pet.list_roles, 'DKB04')[0] == 0)
check('list 不認得的角色 → 1、0 次點擊', run(pet.list_roles, 'DKBO9')[0] == 1)
g = new(panel=True)
rc, out, err = run(pet.list_roles, 'DKBO')
check('面板本來就開著：list 成功、結束不關', rc == 0 and g.panel)
g = new(hud=False)
rc, out, err = run(pet.list_roles, 'all')
check('主畫面 HUD 看不到（面板打不開）→ 70、0 次點擊（頭像絕不點）', rc == 70 and g.clicks == [], f'rc={rc} clicks={g.clicks}')
g = new()
g.avatar_dead = True
rc, out, err = run(pet.list_roles, 'DKBO3')
check('點頭像沒反應 → 71，頭像點 2 次（重試一次）、沒點寵物格 / 狀態鈕', rc == 71 and g.clicks.count((83, 450)) == 2 and btn_clicks(g) == [] and (250, 200) not in g.clicks, str(g.clicks))
g = new()
g.avatar_label = {'DKBO2': 'DKBO3'}                      # 左欄順序變了：DKBO2 頭像下寫的是別人
rc, out, err = run(pet.list_roles, 'DKBO2')
check('頭像名字樣板不符 → 71（樣板已存在時）', rc == 71, f'rc={rc}')
g = new()
g.slot_dead = True
rc, out, err = run(pet.list_roles, 'DKBO')
check('點寵物格沒反應（黃框沒移）→ 71（第 1 格預設已選中不點；第 2 格點 2 次）', rc == 71 and g.clicks.count((250, 322)) == 2, str(g.clicks))
g = new()
pets = mk_pets()
pets['DKBO'][2] = {'name': '魯尼帖斯', 'state': '等待', 'level': 18}
g = new(pets=pets)
rc, out, err = run(pet.list_roles, 'DKBO')
check('等待狀態 + 新名字 / 兩位數等級（第 3 格）', rc == 0 and [(x.get('name'), x.get('state'), x.get('level')) for x in last_json(out)['roles']['DKBO'][:3]] ==
      [('瑪斯貝卡', '騎乘', 128), ('迪基格斯', '出戰', 130), ('魯尼帖斯', '等待', 18)], out[-400:])
g = new()
g.ocr_name_override = ['瑪斯貝卞']                         # OCR 錯字：樣板還沒有這張圖時讀不出名字
fresh_tpl()
rc, out, err = run(pet.list_roles, 'DKBO', learn=True)
s0 = last_json(out)['roles']['DKBO'][0]
check('OCR 錯字 → 名字 None（不猜）但 mountlike（fail-safe）、不學樣板', s0['name'] is None and s0['mountlike'] is True and petmatch.load_tpl()['name'] == {})
g = new()
g.ocr_level_mode = 'bad'
fresh_tpl()
rc, out, err = run(pet.list_roles, 'DKBO')
check('等級 OCR 三組各讀不同值 → level None、不學數字', last_json(out)['roles']['DKBO'][0]['level'] is None and petmatch.load_tpl()['digit'] == {})
g = new()
fresh_tpl()
rc, out, err = run(pet.list_roles, 'DKBO', learn=False)
check('--no-learn：不存樣板檔', rc == 0 and not petmatch.tpl_path().exists())

# ---------------- EXP 橫幅蓋住名字框（掛機中） ----------------
g = new()
run(pet.list_roles, 'DKBO')                                  # 先學樣板
g = new()
g.banner = 2
rc, out, err = run(pet.list_roles, 'DKBO')
d = last_json(out)['roles']['DKBO']
check('橫幅蓋住 2 次取樣 → 等 0.8 s 重讀，名字仍從樣板讀對', rc == 0 and [x.get('name') for x in d[:2]] == ['瑪斯貝卡', '迪基格斯'] and d[0]['via'] == 'tpl')
g = new()
g.banner = 99
g.ocr_name_override = ['？？']
tpl_before = json.dumps(petmatch.load_tpl()['name'], sort_keys=True)
rc, out, err = run(pet.list_roles, 'DKBO')
d = last_json(out)['roles']['DKBO']
check('橫幅一直蓋住 → 名字 None（不猜）、rc 0、不學垃圾樣板', rc == 0 and d[0]['name'] is None and d[1]['name'] is None and json.dumps(petmatch.load_tpl()['name'], sort_keys=True) == tpl_before)
g = new()
g.banner = 99
g.ocr_name_override = ['？？']
rc, out, err = run(pet.set_state, 'DKBO', '迪基格斯', '等待')
check('橫幅一直蓋住時 set-state → 72、不點狀態鈕', rc == 72 and btn_clicks(g) == [])

# ---------------- set-state ----------------
fresh_tpl()
g = new()
rc, out, err = run(pet.set_state, 'DKBO3', '迪基格斯', '等待')
j = last_json(out)
check('set-state 出戰 → 等待：rc 0、狀態變、只點 1 次休息鈕 (672,702)', rc == 0 and g.pets['DKBO3'][1]['state'] == '等待' and btn_clicks(g) == [(672, 702)] and j['changed'] and j['from'] == '出戰', str(g.clicks))
check('其他角色沒被動', all(g.pets[r][1]['state'] == '出戰' for r in fake_pet.ROLES if r != 'DKBO3'))
rc, out, err = run(pet.set_state, 'DKBO3', '迪基格斯', '出戰')
check('再改回出戰：往返 OK、出戰鈕 (390,702) 點 1 次', rc == 0 and g.pets['DKBO3'][1]['state'] == '出戰' and btn_clicks(g)[-1] == (390, 702) and g.state_clicks == [('DKBO3', 1, '等待'), ('DKBO3', 1, '出戰')])
n = len(g.state_clicks)
rc, out, err = run(pet.set_state, 'DKBO3', '迪基格斯', '出戰')
check('已是目標狀態 → 0、不點狀態鈕', rc == 0 and len(g.state_clicks) == n and not last_json(out)['changed'])
rc, out, err = run(pet.set_state, 'DKB04', '迪基格斯', '休息')
check('舊寫法 DKB04 + 休息 也收', rc == 0 and g.pets['DKBO4'][1]['state'] == '等待')
g = new()
g.locked = True
rc, out, err = run(pet.set_state, 'DKBO', '迪基格斯', '等待')
j = last_json(out)
check('鎖定戰寵（狀態鈕沒反應）→ 74、狀態鈕只點 1 次、不去碰外掛', rc == 74 and btn_clicks(g) == [(672, 702)] and not j['changed'] and j['clicked'] and '鎖定戰寵' in j['msg'], f'rc={rc} clicks={btn_clicks(g)}')
g = new()
g.slow_ui = 3
rc, out, err = run(pet.set_state, 'DKBO', '迪基格斯', '等待')
check('畫面慢幾拍才反映 → 輪詢等到、仍只點 1 次', rc == 0 and btn_clicks(g) == [(672, 702)])
g = new()
g.battle = True
rc, out, err = run(pet.set_state, 'DKBO', '迪基格斯', '等待')
check('戰鬥中（VS 牌）→ 78、0 次點擊（沒開面板、沒點狀態鈕）', rc == 78 and g.clicks == [], str(g.clicks))
g = new()
rc, out, err = run(pet.set_state, 'DKBO', '瑪斯貝卡', '等待')
check('騎寵 瑪斯貝卡 → 等待：73、0 次狀態鈕', rc == 73 and btn_clicks(g) == [] and g.pets['DKBO'][0]['state'] == '騎乘')
rc, out, err = run(pet.set_state, 'DKBO', '瑪斯貝卡', '出戰')
check('騎寵 → 出戰 也是 73', rc == 73 and btn_clicks(g) == [])
rc, out, err = run(pet.set_state, 'DKBO', '迪基格斯', '騎乘')
check('目標「騎乘」沒給 --allow-mount → 73、0 次狀態鈕', rc == 73 and btn_clicks(g) == [])
rc, out, err = run(pet.set_state, 'DKBO', '迪基格斯', '騎乘', allow_mount=True)
check('--allow-mount 才點騎乘鈕 (532,702)（原騎寵被換下）', rc == 0 and btn_clicks(g) == [(532, 702)] and g.pets['DKBO'][1]['state'] == '騎乘' and g.pets['DKBO'][0]['state'] == '等待')
g = new()
pets = mk_pets()
pets['DKBO'][1]['state'] = '騎乘'
pets['DKBO'][0]['state'] = '等待'                         # 騎乘中的是迪基格斯（別隻也算騎寵）
g = new(pets=pets)
rc, out, err = run(pet.set_state, 'DKBO', '迪基格斯', '出戰')
check('正在騎乘中的別隻 → 73（狀態 = 騎乘）', rc == 73 and btn_clicks(g) == [])
g = new()
rc, out, err = run(pet.set_state, 'DKBO', '魯尼帖斯', '等待')
check('寵物欄沒有這隻 → 72、0 次狀態鈕', rc == 72 and btn_clicks(g) == [])
g = new()
rc, out, err = run(pet.set_state, 'DKBO', '不存在的寵物名', '等待')
check('寵物名對不到 Monster 表 → 72、完全不碰面板（0 次點擊）', rc == 72 and g.clicks == [], str(rc))
g = new()
fresh_tpl()
g.ocr_name_override = ['迪基格']                           # 名字讀不準（短片段、且沒樣板）
rc, out, err = run(pet.set_state, 'DKBO', '迪基格斯', '等待')
check('名字讀不出 / 對不上 → 72、不點狀態鈕', rc == 72 and btn_clicks(g) == [], f'rc={rc}')
g = new()
fresh_tpl()
pets = mk_pets()
pets['DKBO'][2] = {'name': '迪基格斯', 'state': '等待', 'level': 30}
g = new(pets=pets)
rc, out, err = run(pet.set_state, 'DKBO', '迪基格斯', '等待')
check('同名多隻沒給 --slot → 72、不點', rc == 72 and btn_clicks(g) == [] and '--slot' in err)
rc, out, err = run(pet.set_state, 'DKBO', '迪基格斯', '出戰', slot_no=3)
check('--slot 3 指定第 3 隻 → 只動第 3 格（原出戰的第 2 格不變）', rc == 0 and g.pets['DKBO'][2]['state'] == '出戰' and g.pets['DKBO'][1]['state'] == '出戰' and btn_clicks(g) == [(390, 702)])
rc, out, err = run(pet.set_state, 'DKBO', '迪基格斯', '等待', slot_no=1)
check('--slot 指到名字不符的格（瑪斯貝卡）→ 72', rc == 72)
g = new()
rc, out, err = run(pet.set_state, 'DKBO', '迪基格斯', '跑步')
check('狀態亂寫 → 1', rc == 1 and g.clicks == [])
g = new()
rc, out, err = run(pet.set_state, 'all', '迪基格斯', '等待')
check('set-state 角色 all → 1（只收單一角色）', rc == 1)
g = new()
g.ocr_name_override = ['瑪斯貝卞']
fresh_tpl()
rc, out, err = run(pet.set_state, 'DKBO', '瑪斯貝卡', '等待')
check('名字 OCR 成「瑪斯貝卞」+ 騎乘中：找不到對應名字 → 72 或 73，絕不點狀態鈕', rc in (72, 73) and btn_clicks(g) == [], f'rc={rc}')

# ---------------- pause-encounter ----------------
fresh_tpl()
g = new()
ev = []
heal.encounter_on = lambda: True
heal.set_encounter = lambda on: ev.append(('enc', on))
rc, out, err = run(pet.set_state, 'DKBO', '迪基格斯', '等待', pause=True)
check('--pause-encounter：先關遇敵 → 改狀態 → 開回遇敵', rc == 0 and ev == [('enc', False), ('enc', True)] and g.pets['DKBO'][1]['state'] == '等待', str(ev))
ev.clear()
g = new()
g.locked = True
rc, out, err = run(pet.set_state, 'DKBO', '迪基格斯', '等待', pause=True)
check('失敗（74）時也把遇敵開回', rc == 74 and ev == [('enc', False), ('enc', True)])
ev.clear()
g = new()
g.battle = True
rc, out, err = run(pet.set_state, 'DKBO', '迪基格斯', '等待', pause=True)
check('等不到戰鬥結束 → 78、遇敵開回', rc == 78 and ev == [('enc', False), ('enc', True)] and btn_clicks(g) == [], str(ev))
ev.clear()
g = new()
rc, out, err = run(pet.list_roles, 'DKBO', pause=True)
check('list --pause-encounter 也關 / 開遇敵', rc == 0 and ev == [('enc', False), ('enc', True)])
heal.encounter_on = lambda: False
ev.clear()
g = new()
rc, out, err = run(pet.set_state, 'DKBO', '迪基格斯', '等待', pause=True)
check('遇敵本來就關 → 不動遇敵（也不開）', rc == 0 and ev == [])

# ---------------- rest-all ----------------
fresh_tpl()


def rest_pets():
    p = mk_pets()
    for r in fake_pet.ROLES:
        p[r][2] = {'name': '魯尼帖斯', 'state': '出戰', 'level': 18}
        p[r][3] = {'name': '貝魯卡', 'state': '等待', 'level': 30}
    p['DKBO'][1]['state'] = '等待'                          # DKBO：迪基格斯本來就等待
    return p


g = new(pets=rest_pets())
rc, out, err = run(pet.rest_all, 'all')
j = last_json(out)
check('rest-all all：rc 0', rc == 0, err[-300:])
check('rest-all：出戰的非騎寵全變等待（DKBO2～5 的迪基格斯 + 魯尼帖斯；DKBO 的魯尼帖斯）',
      all(p is None or p['state'] != '出戰' for r in fake_pet.ROLES for p in g.pets[r]))
check('rest-all：騎寵瑪斯貝卡一律還在騎乘', all(g.pets[r][0]['state'] == '騎乘' for r in fake_pet.ROLES))
check('rest-all：只點休息鈕 (672,702)，次數 = 4×2 + 1 = 9；沒點出戰 / 騎乘鈕', btn_clicks(g) and set(btn_clicks(g)) == {(672, 702)} and len(btn_clicks(g)) == 9, f'{len(btn_clicks(g))}')
check('rest-all：已是等待的不點（貝魯卡）', all(s[1] in (1, 2) for s in g.state_clicks) and all(s[2] == '等待' for s in g.state_clicks), str(g.state_clicks))
check('rest-all JSON rested 記錄', j['rested']['DKBO'] == [3] and j['rested']['DKBO2'] == [2, 3] and not j['dry_run'])
g = new(pets=rest_pets())
rc, out, err = run(pet.rest_all, 'all', dry_run=True)
j = last_json(out)
check('--dry-run：rc 0、0 次狀態鈕、狀態都沒變、仍列出會改的', rc == 0 and g.state_clicks == [] and g.pets['DKBO2'][1]['state'] == '出戰' and j['rested']['DKBO2'] == [2, 3] and '[dry-run' in out, out[-300:])
g = new(pets=rest_pets())
rc, out, err = run(pet.rest_all, 'DKBO2', only=['魯尼帖斯'])
check('--only 魯尼帖斯：只動它（迪基格斯仍出戰）、只有 DKBO2', rc == 0 and g.pets['DKBO2'][2]['state'] == '等待' and g.pets['DKBO2'][1]['state'] == '出戰' and g.state_clicks == [('DKBO2', 2, '等待')])
g = new(pets=rest_pets())
rc, out, err = run(pet.rest_all, 'DKBO2', keep=['瑪斯貝卡', '迪基格斯'])
check('--keep 迪基格斯：它不動、魯尼帖斯改等待', rc == 0 and g.pets['DKBO2'][1]['state'] == '出戰' and g.pets['DKBO2'][2]['state'] == '等待')
g = new(pets=rest_pets())
g.locked = True
rc, out, err = run(pet.rest_all, 'all')
check('rest-all 遇鎖定戰寵 → 74、只點 1 次就停（不連點）', rc == 74 and len(g.state_clicks) == 1, str(g.state_clicks))
g = new(pets=rest_pets())
g.battle = True
rc, out, err = run(pet.rest_all, 'all')
check('rest-all 戰鬥中 → 78、0 次點擊', rc == 78 and g.clicks == [])
g = new(pets=rest_pets())
rc, out, err = run(pet.rest_all, 'DKBO9')
check('rest-all 角色不認得 → 1', rc == 1)
pets = rest_pets()
fresh_tpl()
g = new(pets=pets)
g.ocr_name_override = ['？？']                             # 名字全讀不出來（沒樣板）
rc, out, err = run(pet.rest_all, 'DKBO2')
check('出戰寵名字讀不出來 → 不動它、rc 72', rc == 72 and g.state_clicks == [] and g.pets['DKBO2'][1]['state'] == '出戰', f'rc={rc}')
g = new(pets=rest_pets())
fresh_tpl()
rc, out, err = run(pet.rest_all, 'DKBO', keep=[])
check('--keep 空清單：騎寵仍因 mountlike / 狀態=騎乘 不動', rc == 0 and g.pets['DKBO'][0]['state'] == '騎乘')


# ---------------- store / take（P7）----------------
DEPOT_X = set(pet.CARD_X)


def depot_free(g):
    """store / take 以外都不該點的存取鈕：回 530,697 點擊數"""
    return len([c for c in g.clicks if c == pet.DEPOT_BTN_XY])


check('退出碼常數 75 / 76 / 77', (pet.EXIT_DEPOT, pet.EXIT_VERIFY, pet.EXIT_FULL) == (75, 76, 77))
check('常數：存入鈕 530,697 不在 PET 禁區；倉庫頁箭頭 / 擴容在禁區', all(True for _ in [uikit.check_forbidden(uikit.PET, *pet.DEPOT_BTN_XY)])
      and all(any(uikit.in_rect(*xy, r) for r in uikit.PET.forbidden.values()) for xy in [(805, 703), (1055, 703), (1195, 705)]))
check('倉庫格點擊座標都不在禁區（20 格）', not any(uikit.in_rect(pet.CARD_X[c], pet.CARD_Y[r] + pet.CARD_CLICK_DY, rr) for c in range(5) for r in range(4) for rr in uikit.PET.forbidden.values()))
check('按鈕底色：實測紅 / 金', pet.body_kind([(177, 65, 38)] * 8) == 'store' and pet.body_kind([(185, 125, 62)] * 8) == 'take' and pet.body_kind([(245, 225, 192)] * 8) is None
      and pet.body_kind([(177, 65, 38)] * 7 + [(185, 125, 62)]) is None)
check('子分頁亮度：亮 (251,219,135)、暗 (171,127,84)', pet.is_tab_on((251, 219, 135)) and pet.is_tab_on((255, 217, 131)) and not pet.is_tab_on((171, 127, 84)))
check('倉庫格選中色 (209,151,13) ～ (249,185,1)（呼吸閃動）三點兩點即可；暗棕 / 米色不算', pet.is_card_sel([(209, 151, 13), (205, 151, 14), (106, 70, 45)]) and pet.is_card_sel([(249, 185, 1), (245, 185, 1), (249, 189, 1)])
      and not pet.is_card_sel([(106, 70, 45)] * 3) and not pet.is_card_sel([(225, 197, 147)] * 3))
a16 = [(100 + i, 80, 60) for i in range(16)]
check('縮圖簽名：相同 / 小差異 OK、差很多不同', pet.thumb_same(a16, a16) and pet.thumb_same(a16, [(c[0] + 8, c[1], c[2]) for c in a16]) and not pet.thumb_same(a16, [(10, 200, 10)] * 16))
check('guard_store：騎乘 / 像騎寵 / 第 1 格 / 名字 None / 狀態 None 都拒絕；第 2 格出戰放行',
      all(pet.guard_store(x, False) for x in [sl(2, '魯尼帖斯', '騎乘'), sl(2, '瑪斯貝卡', '等待'), sl(2, '瑪斯貝卞', '等待', mountlike=True), sl(1, '迪基格斯', '出戰'), sl(2, None, '出戰'), sl(2, '迪基格斯', None)])
      and pet.guard_store(sl(2, '迪基格斯', '出戰'), False) is None and pet.guard_store(sl(1, '迪基格斯', '出戰'), True) is None
      and pet.guard_store(sl(1, '瑪斯貝卡', '騎乘'), True))

# --- store 成功（個人倉庫，騎寵不動）---
fresh_tpl()
g = new()
rc, out, err = run(pet.store, 'DKBO', '迪基格斯', 'personal')
j = last_json(out)
check('store 迪基格斯 → rc 0；寵物欄只剩瑪斯貝卡（騎乘不動）；個人倉庫第 4 格有迪基格斯', rc == 0 and [p and p['name'] for p in g.pets['DKBO'][:2]] == ['瑪斯貝卡', None]
      and g.pets['DKBO'][0]['state'] == '騎乘' and g.depot['DKBO']['personal'][3]['name'] == '迪基格斯', f'rc={rc} {err[-200:]}')
check('store：存入鈕只點 1 次、沒有任何狀態鈕被點到（沒換騎寵）、depot_index = 4', depot_free(g) == 1 and g.state_clicks == [] and len(g.store_clicks) == 1 and j.get('depot_index') == 4, str(j.get('depot_index')))
j_store = j
check('store：結束回寵物分頁、第 1 格從沒被選取點擊', g.view == 'pet' and (pet.SLOT_X, pet.SLOT_Y[0]) not in g.clicks[g.clicks.index(pet.DEPOT_TAB_XY):], str(g.view))
check('store：點擊順序 = 倉庫分頁 → 存入鈕 → 驗證倉庫格 → 切回寵物分頁', g.clicks.index(pet.DEPOT_TAB_XY) < g.clicks.index(pet.DEPOT_BTN_XY) < len(g.clicks) - 1)
check('store 迪基格斯（出戰）會跳確認視窗：確定只點 1 次、存入鈕 1 次', g.dialog_clicks == [pet.CONFIRM_OK_XY] and j_store.get('confirm_clicked') is True, str(g.dialog_clicks))
fresh_tpl()
g = new(pets=mk_pets(DKBO=[{'name': '瑪斯貝卡', 'state': '騎乘', 'level': 128}, {'name': '迪基格斯', 'state': '等待', 'level': 130}, None, None, None]))
rc, out, err = run(pet.store, 'DKBO', '迪基格斯', 'personal')
check('store 等待中的寵物：不跳視窗、不點確定', rc == 0 and g.dialog_clicks == [] and depot_free(g) == 1, f'rc={rc}')
fresh_tpl()
g = new()
g.confirm_text = ['這是別的視窗，請點取消']
rc, out, err = run(pet.store, 'DKBO', '迪基格斯', 'personal')
check('確認視窗文字不是存入倉庫 → 點取消（不點確定）、76、寵物沒動', rc == 76 and g.dialog_clicks == [pet.CONFIRM_CANCEL_XY] and g.pets['DKBO'][1] is not None, f'rc={rc} {g.dialog_clicks}')
fresh_tpl()
g = new()
g.confirm_text = []                                              # OCR 讀不出視窗文字：特徵吻合 + 事前驗過非騎寵 → 照樣點確定（軟檢查）
rc, out, err = run(pet.store, 'DKBO', '迪基格斯', 'personal')
check('確認視窗 OCR 讀不出字 → 仍單擊確定完成存入', rc == 0 and g.dialog_clicks == [pet.CONFIRM_OK_XY], f'rc={rc}')
# --- 騎寵保護：零倉庫點擊 ---
for label, text in [('瑪斯貝卡', '瑪斯貝卡'), ('讀成瑪斯貝卞', '瑪斯貝卞')]:
    fresh_tpl()
    g = new()
    rc, out, err = run(pet.store, 'DKBO', text, 'personal')
    check(f'store {label} → 73、零點擊（連面板都不開）', rc == 73 and g.clicks == [] and depot_free(g) == 0, f'rc={rc} clicks={g.clicks[:3]}')
fresh_tpl()
g = new()
g.ocr_name_override = ['瑪斯貝卞'] * 3                      # 面板上名字讀成錯字（沒樣板）：要存迪基格斯 → 找不到名字，絕不存
rc, out, err = run(pet.store, 'DKBO', '迪基格斯', 'personal')
check('名字 OCR 讀成「瑪斯貝卞」→ 不存（72），倉庫 / 存入鈕 0 次', rc == 72 and not g.depot_clicks and depot_free(g) == 0, f'rc={rc}')
fresh_tpl()
pets = mk_pets(DKBO=[{'name': '瑪斯貝卡', 'state': '等待', 'level': 128}, {'name': '迪基格斯', 'state': '出戰', 'level': 130}, {'name': '魯尼帖斯', 'state': '騎乘', 'level': 20}, None, None])
g = new(pets=pets)
rc, out, err = run(pet.store, 'DKBO', '魯尼帖斯', 'personal')
check('狀態 = 騎乘的別隻 → 73、倉庫零點擊', rc == 73 and not g.depot_clicks and depot_free(g) == 0, f'rc={rc}')
fresh_tpl()
pets = mk_pets(DKBO=[{'name': '迪基格斯', 'state': '出戰', 'level': 130}, {'name': '瑪斯貝卡', 'state': '騎乘', 'level': 128}, None, None, None])
g = new(pets=pets)
rc, out, err = run(pet.store, 'DKBO', '迪基格斯', 'personal')
check('第 1 格（名字不像騎寵）→ 73、倉庫零點擊', rc == 73 and not g.depot_clicks and depot_free(g) == 0, f'rc={rc}')
fresh_tpl()
g = new(pets=mk_pets(DKBO=[{'name': '迪基格斯', 'state': '出戰', 'level': 130}, {'name': '瑪斯貝卡', 'state': '騎乘', 'level': 128}, None, None, None]))
rc, out, err = run(pet.store, 'DKBO', '迪基格斯', 'personal', allow_slot1=True)
check('--allow-slot1 → 放行（rc 0），騎乘寵仍在', rc == 0 and g.pets['DKBO'][0]['name'] == '瑪斯貝卡' and g.pets['DKBO'][0]['state'] == '騎乘' and depot_free(g) == 1, f'rc={rc}')
fresh_tpl()
g = new()
rc, out, err = run(pet.store, 'DKBO', '迪基格斯', 'personal', slot_no=1)
check('--slot 1 指到瑪斯貝卡但名字不符 → 72、零倉庫點擊', rc == 72 and not g.depot_clicks, f'rc={rc}')
# --- 按鈕 / 分頁 / 簽名驗證 ---
fresh_tpl()
g = new()
g.btn_ocr_override = ['取出寵物']
rc, out, err = run(pet.store, 'DKBO', '迪基格斯', 'personal')
check('按鈕文字是「取出寵物」→ 75、存入鈕 0 次、寵物沒動', rc == 75 and depot_free(g) == 0 and g.pets['DKBO'][1] is not None, f'rc={rc}')
fresh_tpl()
g = new()
g.btn_ocr_override = ['存入', '取出寵物']                       # 兩種字都出現 = 不確定
rc, out, err = run(pet.store, 'DKBO', '迪基格斯', 'personal')
check('按鈕文字兩種都出現（不確定）→ 75、0 次', rc == 75 and depot_free(g) == 0, f'rc={rc}')
fresh_tpl()
g = new()
g.btn_ocr_override = []
rc, out, err = run(pet.store, 'DKBO', '迪基格斯', 'personal')
check('按鈕 OCR 讀不出 → 75、0 次', rc == 75 and depot_free(g) == 0, f'rc={rc}')
fresh_tpl()
g = new()
g.on_depot = lambda gm: gm.pets['DKBO'][1].update(level=99)    # 進倉庫分頁時寵物欄被改（名字同、縮圖變）：模擬補位換人
rc, out, err = run(pet.store, 'DKBO', '迪基格斯', 'personal')
check('補位 / 縮圖簽名不符 → 75、存入鈕 0 次', rc == 75 and depot_free(g) == 0 and g.depot['DKBO']['personal'][3] is None, f'rc={rc} {err[-120:]}')
fresh_tpl()
g = new()


def swap(gm):
    p = gm.pets['DKBO']
    p[1], p[2] = None, p[1]                                     # 迪基格斯被移到第 3 格（選取的第 2 格變空）
g.on_depot = swap
rc, out, err = run(pet.store, 'DKBO', '迪基格斯', 'personal')
check('寵物欄位移（原選取格變空）→ 不存、存入鈕 0 次', rc != 0 and depot_free(g) == 0, f'rc={rc}')
fresh_tpl()
g = new()
g.depot_dead = True
rc, out, err = run(pet.store, 'DKBO', '迪基格斯', 'personal')
check('倉庫分頁打不開 → 75；存入鈕 0 次、沒有狀態鈕被點（530,697 在寵物分頁是「騎乘」鈕附近）', rc == 75 and depot_free(g) == 0 and g.state_clicks == [], f'rc={rc}')
fresh_tpl()
g = new()
g.store_dead = True
rc, out, err = run(pet.store, 'DKBO', '迪基格斯', 'personal')
check('存入鈕沒反應 → 76，且只點 1 次（不重點）', rc == 76 and depot_free(g) == 1 and len(g.store_clicks) == 1, f'rc={rc} 點={depot_free(g)}')
fresh_tpl()
g = new(depot=fake_pet.mk_depot(DKBO={'personal': ['摩娜西普'] * 20}))
rc, out, err = run(pet.store, 'DKBO', '迪基格斯', 'personal')
check('個人倉庫滿 → 77、存入鈕 0 次', rc == 77 and depot_free(g) == 0 and g.pets['DKBO'][1] is not None, f'rc={rc}')
fresh_tpl()
g = new(depot=fake_pet.mk_depot(DKBO={'personal': ['摩娜西普'] * 20}))
rc, out, err = run(pet.store, 'DKBO', '迪基格斯', 'public')
check('--depot public：切公共子分頁後存入（個人滿不影響）', rc == 0 and g.depot['DKBO']['public'][0]['name'] == '迪基格斯' and g.dtab == 'public' and pet.SUBTAB_XY['public'] in g.clicks, f'rc={rc}')
fresh_tpl()
g = new()
g.battle = True
rc, out, err = run(pet.store, 'DKBO', '迪基格斯', 'personal')
check('戰鬥中（面板外判斷）→ 78 / 沒有任何點擊', rc == 78 or g.clicks == [], f'rc={rc}')
# --- take ---
fresh_tpl()
g = new()
rc, out, err = run(pet.take, 'DKBO', 'personal', 1, '摩娜西普')
check('take index 1 --expect 摩娜西普 → rc 0；寵物欄第 3 格 = 摩娜西普（等待）；倉庫第 1 格清空', rc == 0 and g.pets['DKBO'][2] and g.pets['DKBO'][2]['name'] == '摩娜西普' and g.pets['DKBO'][2]['state'] == '等待'
      and g.depot['DKBO']['personal'][0] is None and depot_free(g) == 1 and g.state_clicks == [], f'rc={rc} {err[-200:]}')
fresh_tpl()
g = new()
rc, out, err = run(pet.take, 'DKBO', 'personal', 1, '朵拉比斯')
check('take：倉庫第 1 格是摩娜西普、--expect 朵拉比斯 → 72、取出鈕 0 次、不存回', rc == 72 and depot_free(g) == 0 and g.depot['DKBO']['personal'][0] is not None, f'rc={rc}')
fresh_tpl()
g = new()
rc, out, err = run(pet.take, 'DKBO', 'personal', 1, None, False, True, None, '1/1/1/1')
check('take --expect-growth 不符（格子遞補後盲取別隻）→ 72、取出鈕 0 次（2026-10-12 左迪洛斯事故）', rc == 72 and depot_free(g) == 0 and g.depot['DKBO']['personal'][0] is not None, f'rc={rc}')
fresh_tpl()
g = new()
rc, out, err = run(pet.take, 'DKBO', 'personal', 1, '摩娜西普', False, True, None, None, 99)
check('take --expect-level 不符 → 76（取出後驗等級，不自動存回；朵拉比斯 Lv126 / Lv1 事故）', rc == 76 and last_json(out).get('level') != 99, f'rc={rc}')
fresh_tpl()
g = new()
rc, out, err = run(pet.take, 'DKBO', 'personal', 5, '摩娜西普')
check('take 空格 → 72、取出鈕 0 次', rc == 72 and depot_free(g) == 0, f'rc={rc}')
fresh_tpl()
g = new(pets=mk_pets(DKBO=[{'name': '瑪斯貝卡', 'state': '騎乘', 'level': 128}, {'name': '迪基格斯', 'state': '出戰', 'level': 130}, {'name': '魯尼帖斯', 'state': '等待', 'level': 20}, {'name': '魯尼帖斯', 'state': '等待', 'level': 20}, {'name': '魯尼帖斯', 'state': '等待', 'level': 20}]))
rc, out, err = run(pet.take, 'DKBO', 'personal', 1, '摩娜西普')
check('寵物欄滿 → 77、倉庫分頁都不開', rc == 77 and not g.depot_clicks and depot_free(g) == 0, f'rc={rc}')
fresh_tpl()
g = new()
g.btn_ocr_override = ['存入寵物']
rc, out, err = run(pet.take, 'DKBO', 'personal', 1, '摩娜西普')
check('take：按鈕文字不是「取出寵物」→ 75、0 次', rc == 75 and depot_free(g) == 0, f'rc={rc}')
fresh_tpl()
g = new()
g.store_dead = True
rc, out, err = run(pet.take, 'DKBO', 'personal', 1, '摩娜西普')
check('取出鈕沒反應 → 76，只點 1 次', rc == 76 and depot_free(g) == 1, f'rc={rc}')
fresh_tpl()
g = new()
g.confirm_on_take = True
rc, out, err = run(pet.take, 'DKBO', 'personal', 1, '摩娜西普')
check('take 遇到未預期的提示視窗 → 點取消（不點確定）、76、取出鈕只點 1 次', rc == 76 and g.dialog_clicks == [pet.CONFIRM_CANCEL_XY] and depot_free(g) == 1, f'rc={rc} {g.dialog_clicks}')
for bad_idx in (0, 21):
    g = new()
    rc, out, err = run(pet.take, 'DKBO', 'personal', bad_idx, '摩娜西普')
    check(f'take --index {bad_idx} → 1（參數）、零點擊', rc == 1 and g.clicks == [], f'rc={rc}')
# --- 往返：store → take 回來 ---
fresh_tpl()
g = new()
rc, out, err = run(pet.store, 'DKBO', '迪基格斯', 'personal')
idx = last_json(out).get('depot_index')
rc2, out2, err2 = run(pet.take, 'DKBO', 'personal', idx, '迪基格斯')
check('往返：store 後 take --index <depot_index> --expect 迪基格斯 → 迪基格斯回到寵物欄第 2 格（等待）、騎寵沒動', rc == 0 and rc2 == 0 and g.pets['DKBO'][1]['name'] == '迪基格斯' and g.pets['DKBO'][1]['state'] == '等待'
      and g.pets['DKBO'][0]['name'] == '瑪斯貝卡' and g.pets['DKBO'][0]['state'] == '騎乘' and g.state_clicks == [], f'{rc} {rc2} {err2[-200:]}')

# ---------------- 全測試掃：任何點擊都不在禁區、且都在白名單座標 ----------------
allowed_x = {83, pet.SLOT_X, 390, 532, 672, 318, 1310, 1365, 897, 1160, 530, 615, 813} | set(pet.CARD_X)
bad_forbidden, bad_allowed, total = [], [], 0
for gm in GAMES:
    for c in gm.clicks:
        total += 1
        for nm, r in uikit.PET.forbidden.items():
            if uikit.in_rect(c[0], c[1], r):
                bad_forbidden.append((nm, c))
        if c[0] not in allowed_x:
            bad_allowed.append(c)
check(f'FORBIDDEN 全測試掃（{total} 次點擊）：垃圾桶 / 回爐 / 忠誠 / 鎖頭 / 擴容 = 0 次', not bad_forbidden, str(bad_forbidden[:5]))
check('所有點擊都在白名單 x（頭像 83 / 寵物格 250 / 三顆狀態鈕 / 開關面板 / 倉庫分頁 / 倉庫格 / 存取鈕）', not bad_allowed, str(bad_allowed[:5]))
check('常數：PET 禁區涵蓋 垃圾桶 / 回爐 / 忠誠± / 鎖頭 / 擴容', set(uikit.PET.forbidden) >= {'trash', 'recycle', 'loyal_minus', 'loyal_plus', 'lock', 'depot_expand'})
for nm, xy in pet.BTN_XY.items():
    try:
        uikit.check_forbidden(uikit.PET, *xy)
        ok = True
    except uikit.ForbiddenClick:
        ok = False
    check(f'狀態鈕 {nm} {xy} 不在 PET 禁區', ok)
try:
    uikit.check_forbidden(uikit.PET, 708, 565)
    ok = False
except uikit.ForbiddenClick:
    ok = True
check('垃圾桶 708,565 真的會被 safe_click 擋', ok)

# ---- P8 實機：存走第 2 格後選取移到騎寵格，最右欄 x 292 變橘色（光暈）不能誤報 ----
base = [(221, 50, 0), (207, 195, 180), (232, 59, 1), (167, 55, 10),
        (123, 110, 100), (225, 112, 14), (180, 132, 118), (167, 74, 10),
        (128, 104, 70), (187, 159, 102), (246, 235, 232), (142, 69, 10),
        (197, 191, 188), (249, 233, 198), (183, 170, 167), (141, 74, 10)]
glow = [c if k % 4 != 3 else (209, 125, 5) for k, c in enumerate(base)]
check('mount_same：x 292 欄選取光暈（實測值）→ 相同', pet.mount_same(base, glow) and not pet.thumb_same(base, glow))
inner = [c if k % 4 == 3 or k > 4 else (10, 200, 10) for k, c in enumerate(base)]
check('mount_same：內側欄真的換了（補位換人）→ 不同', not pet.mount_same(base, inner))
one = list(base)
one[0] = (0, 0, 0)
check('mount_same：內側 1 點雜訊可容忍、2 點不行', pet.mount_same(base, one) and not pet.mount_same(base, [(0, 0, 0)] * 2 + base[2:]))
check('mount_same：長度不符 / 空 → False', not pet.mount_same(base, base[:8]) and not pet.mount_same(None, base))

# ---------------- D0：--allow-mount-store / MOUNTS 加布拉奇多斯 ----------------
check('MOUNTS = 瑪斯貝卡 + 布拉奇多斯', uikit.MOUNTS == ['瑪斯貝卡', '布拉奇多斯'])
check('is_mount_like：布拉奇多斯 / 錯字布拉奇多卡 / 瑪斯貝卡 = True', all(uikit.is_mount_like(t) for t in ['布拉奇多斯', '布拉奇多卡', '瑪斯貝卡']))
check('is_mount_like：朵拉比斯 / 迪基格斯 / 魯尼帖斯 / 左迪洛斯 / 烏力斯坦 = False（不誤擋）', not any(uikit.is_mount_like(t) for t in ['朵拉比斯', '迪基格斯', '魯尼帖斯', '左迪洛斯', '烏力斯坦']))
check('guard_store 騎寵新名字：布拉奇多斯 等待 → 擋；加 allow_mount_store 同名 → 放行', pet.guard_store(sl(2, '布拉奇多斯', '等待'), False) and pet.guard_store(sl(2, '布拉奇多斯', '等待'), False, '布拉奇多斯') is None)
check('guard_store allow_mount_store：名字不同 / 像但不同 / 騎乘中 / 出戰中 / 第 1 格沒 slot1 → 擋',
      all(pet.guard_store(x, False, am) for x, am in [(sl(2, '瑪斯貝卡', '等待'), '布拉奇多斯'), (sl(2, '瑪斯貝卞', '等待', mountlike=True), '瑪斯貝卡'), (sl(2, '瑪斯貝卡', '騎乘'), '瑪斯貝卡'),
                                                     (sl(2, '瑪斯貝卡', '出戰'), '瑪斯貝卡'), (sl(1, '瑪斯貝卡', '等待'), '瑪斯貝卡')])
      and pet.guard_store(sl(1, '瑪斯貝卡', '等待'), True, '瑪斯貝卡') is None)
todo, ref = pet.plan_rest([sl(1, '布拉奇多斯', '出戰', mountlike=True), sl(2, '迪基格斯', '出戰')], list(uikit.MOUNTS), None)
check('plan_rest 預設 keep=MOUNTS：布拉奇多斯不動、迪基格斯要改', [s['slot'] for s in todo] == [2] and not ref)


def mount_game(state='等待', first='瑪斯貝卡', second='迪基格斯'):
    return new(pets=mk_pets(DKBO=[{'name': first, 'state': state, 'level': 128}, {'name': second, 'state': '等待', 'level': 130}, None, None, None]))


def depot_names(g):
    return [d['name'] for d in g.depot['DKBO']['personal'] if d]


MS = dict(allow_slot1=True, allow_mount_store='瑪斯貝卡')
fresh_tpl()
g = mount_game()
rc, out, err = run(pet.store, 'DKBO', '瑪斯貝卡', 'personal', **MS)
check('allow-mount-store：瑪斯貝卡 第 1 格 等待 + slot1 + 同名 → rc 0、存進個人倉庫、存入鈕 1 次', rc == 0 and '瑪斯貝卡' in depot_names(g) and depot_free(g) == 1 and g.pets['DKBO'][0]['name'] == '迪基格斯', f'rc={rc} {err[-200:]} {out[-200:]}')
check('allow-mount-store：沒有任何狀態鈕被點', g.state_clicks == [])
fresh_tpl()
g = mount_game()
rc, out, err = run(pet.store, 'DKBO', '瑪斯貝卡', 'personal', allow_slot1=True)
check('只有 --allow-slot1、沒帶 --allow-mount-store → 73、零點擊', rc == 73 and g.clicks == [] and depot_free(g) == 0, f'rc={rc}')
g = mount_game()
rc, out, err = run(pet.store, 'DKBO', '瑪斯貝卡', 'personal', allow_mount_store='瑪斯貝卡')
check('第 1 格沒帶 --allow-slot1 → 73、倉庫存入鈕 0 次', rc == 73 and depot_free(g) == 0 and not g.depot_clicks and g.pets['DKBO'][0]['name'] == '瑪斯貝卡', f'rc={rc}')
g = mount_game(state='騎乘')
rc, out, err = run(pet.store, 'DKBO', '瑪斯貝卡', 'personal', **MS)
check('騎乘中 → 73、存入鈕 0 次', rc == 73 and depot_free(g) == 0 and g.pets['DKBO'][0]['state'] == '騎乘' and '瑪斯貝卡' not in depot_names(g), f'rc={rc}')
g = mount_game()
rc, out, err = run(pet.store, 'DKBO', '瑪斯貝卡', 'personal', allow_slot1=True, allow_mount_store='布拉奇多斯')
check('旗標名字不同（布拉奇多斯 vs 瑪斯貝卡）→ 73、零點擊', rc == 73 and g.clicks == [] and depot_free(g) == 0, f'rc={rc}')
g = mount_game()
rc, out, err = run(pet.store, 'DKBO', '瑪斯貝卞', 'personal', allow_slot1=True, allow_mount_store='瑪斯貝卡')
check('參數名「像但不同」（瑪斯貝卞）→ 73、零點擊', rc == 73 and g.clicks == [] and depot_free(g) == 0, f'rc={rc}')
g = mount_game()
rc, out, err = run(pet.store, 'DKBO', '瑪斯貝卞', 'personal', allow_slot1=True, allow_mount_store='瑪斯貝卞')
check('旗標與參數都是「像」的錯字（瑪斯貝卞）→ 73、零點擊（snap 的正式名與其不同）', rc == 73 and g.clicks == [] and depot_free(g) == 0, f'rc={rc}')
fresh_tpl()
g = mount_game()
g.ocr_name_override = ['瑪斯貝卞'] * 3
rc, out, err = run(pet.store, 'DKBO', '瑪斯貝卡', 'personal', **MS)
check('面板上名字讀成「像」的錯字（沒樣板）→ 不存（72 / 73）、存入鈕 0 次', rc in (72, 73) and depot_free(g) == 0, f'rc={rc}')
g = mount_game(first='迪基格斯', second='瑪斯貝卡')
rc, out, err = run(pet.store, 'DKBO', '迪基格斯', 'personal', allow_slot1=True, allow_mount_store='瑪斯貝卡')
check('旗標名字與要存的寵物不同（要存迪基格斯、旗標瑪斯貝卡）→ 73、零點擊（旗標只對同名寵物有意義）', rc == 73 and g.clicks == [] and depot_free(g) == 0, f'rc={rc}')
fresh_tpl()
g = mount_game(first='迪基格斯', second='布拉奇多斯')
rc, out, err = run(pet.store, 'DKBO', '布拉奇多斯', 'personal')
check('MOUNTS 新名字：store 布拉奇多斯（無旗標）→ 73、零點擊', rc == 73 and g.clicks == [] and depot_free(g) == 0, f'rc={rc}')
g = mount_game(first='迪基格斯', second='布拉奇多斯')
rc, out, err = run(pet.store, 'DKBO', '布拉奇多斯', 'personal', allow_mount_store='布拉奇多斯')
check('布拉奇多斯 第 2 格 等待 + 同名旗標 → rc 0、存進倉庫', rc == 0 and '布拉奇多斯' in depot_names(g) and depot_free(g) == 1, f'rc={rc} {err[-200:]}')
# set-state 瑪斯貝卡 等待 --allow-mount（流程第 2 步）→ 接著 store
fresh_tpl()
g = mount_game(state='騎乘')
rc, out, err = run(pet.set_state, 'DKBO', '瑪斯貝卡', '等待', allow_mount=True)
check('set-state 瑪斯貝卡 等待 --allow-mount：只點休息鈕 1 次、騎乘 → 等待', rc == 0 and btn_clicks(g) == [(672, 702)] and g.pets['DKBO'][0]['state'] == '等待', f'rc={rc} {err[-200:]}')
rc, out, err = run(pet.store, 'DKBO', '瑪斯貝卡', 'personal', **MS)
check('接著 store --allow-mount-store：rc 0、不跳確認視窗（等待）、倉庫有瑪斯貝卡', rc == 0 and '瑪斯貝卡' in depot_names(g) and g.dialog_clicks == [], f'rc={rc} {err[-200:]}')


# ---------------- 沒名字的新寵物 / 存倉驗證 / store-many / take-many（2026-10-11）----------------
check('parse_growth：實測 OCR 3 行（2 行相同 + 殘行）→ 49/9/8/2', petmatch.parse_growth(['49/9/8/2', '49/9/8/2', '49/8']) == '49/9/8/2')
check('parse_growth：只有 1 行完整且無殘行 / 兩個不同字串各 1 行 / 空 → None（不猜）；1 完整 + 1 子序列殘行 → 採用（2026-10-12 放寬，#258）', petmatch.parse_growth(['49/9/8/2', '49/8']) == '49/9/8/2' and petmatch.parse_growth(['49/9/8/2']) is None
      and petmatch.parse_growth(['49/9/8/2', '48/9/7/1']) is None and petmatch.parse_growth([]) is None and petmatch.parse_growth(['迪基格斯'] * 3) is None)
check('parse_growth：空白 / 前導 0 正規化', petmatch.parse_growth([' 47 / 10/7/1', '47/10/7/01']) == '47/10/7/1')
cols_a = [(100 + i, 80, 60) for i in range(16)]
cols_b = [(20 + 7 * i, 200, 150) for i in range(16)]
reg0 = {'thumb': {}, 'growth': {}}
check('identify_species：沒登錄 → None', petmatch.identify_species(cols_a, '49/9/8/2', reg0) is None)
check('learn_species：縮圖 + 字串登錄、再學同物種不動', petmatch.learn_species(reg0, '布拉奇多斯', cols_a, '49/9/8/2') and not petmatch.learn_species(reg0, '布拉奇多斯', cols_a, '49/9/8/2'))
check('identify_species：同縮圖 → 物種；不同縮圖 → None；沒縮圖（倉庫卡）靠字串；字串矛盾 → None',
      petmatch.identify_species(cols_a, '45/10/8/1', reg0) == '布拉奇多斯' and petmatch.identify_species(cols_b, '45/10/8/1', reg0) is None
      and petmatch.identify_species(None, '49/9/8/2', reg0) == '布拉奇多斯' and petmatch.identify_species(None, '1/1/1/1', reg0) is None
      and petmatch.identify_species(cols_a, '49/9/8/2', {'thumb': reg0['thumb'], 'growth': {'49/9/8/2': '朵拉比斯'}}) is None)
_regc = {'thumb': {'甲': [cols_a]}, 'growth': {'1/1/1/1': '甲'}}
check('learn_species：成長字串撞到別的物種 → 刪掉該字串（只靠縮圖），之後新物種縮圖仍可辨識（2026-10-12 實機）',
      petmatch.learn_species(_regc, '乙', cols_b, '1/1/1/1') and '1/1/1/1' not in _regc['growth'] and petmatch.identify_species(cols_b, '1/1/1/1', _regc) == '乙')
class _PW:
    def __init__(self, seq):
        self.seq = list(seq)

    def ocr(self, box, *o):
        return self.seq.pop(0) if self.seq else []


_orig_pw = pet._petwatch
pet._petwatch = lambda: _PW([['朵拉斯', '朵拉比斯'], ['朵拉比斯', '朵拉斯'], ['剁立斯']])
_nm = pet.ocr_pet_name()
check('ocr_pet_name：噪聲中有 ≥2 行精確同名 → 採用（不精確、不學）（#258）', _nm[0] == '朵拉比斯' and _nm[2] is False)
pet._petwatch = lambda: _PW([['朵拉斯', '剁立斯']])
check('ocr_pet_name：只噪聲 → None', pet.ocr_pet_name()[0] is None)
pet._petwatch = _orig_pw
check('parse_growth：1 行完整 + ≥2 行掉字殘行（子序列）→ 採用；殘行對不上 → None（#258）',
      petmatch.parse_growth(['34/8/3/8', '34/8/8', '34/8/8']) == '34/8/3/8' and petmatch.parse_growth(['34/8/3/8', '35/1/1']) is None and petmatch.parse_growth(['33/7/4/8', '33/4/8']) == '33/7/4/8' and petmatch.parse_growth(['33/7/4/8']) is None and petmatch.parse_growth(['34/8/3/8', '99/9/9', '99/9']) is None)
check('learn_species：縮圖已屬別的物種 → 拒絕（標籤可疑）', not petmatch.learn_species(reg0, '朵拉比斯', cols_a, '1/2/3/4') and '朵拉比斯' not in reg0['thumb'])
check('card_order：新增格先、其餘照序、空格不列', pet.card_order([True, False, True, True, False], 3) == [3, 0, 2] and pet.card_order([False, True], None) == [1])

BRA = '布拉奇多斯'
GS = ['49/9/8/2', '49/9/7/2', '48/9/7/1', '47/10/7/1', '45/10/8/1']


def unn(i, state='騎乘', species=BRA):
    return {'name': BRA, 'unnamed': GS[i], 'species': species, 'state': state, 'level': 1}


def five(state='騎乘'):
    """5 人：第 1 格沒名字的布拉奇多斯（成長字串各不同）、第 2 格 朵拉比斯（有名字）"""
    return mk_pets(**{r: [unn(i, state), {'name': '朵拉比斯', 'state': '出戰', 'level': 1}, None, None, None] for i, r in enumerate(fake_pet.ROLES)})


fresh_tpl()
g = new(pets=five())
rc, out, err = run(pet.list_roles, 'DKBO2')
j = last_json(out)['roles']['DKBO2']
g.panel, g.sel = True, 0
check('list：沒名字的寵物 → name None、unnamed = 成長字串、物種 None（沒登錄不猜）、顯示 ?(…)', rc == 0 and j[0]['name'] is None and j[0]['unnamed'] == GS[1] and j[0]['species'] is None and j[0]['raw_name'] == f'?({GS[1]})'
      and j[0]['state'] == '騎乘' and j[1]['name'] == '朵拉比斯', str(j[0]))
check('fmt_slot 顯示 ?(49/9/7/2)', '?(49/9/7/2)' in pet.fmt_slot(j[0]) and '≈' not in pet.fmt_slot(j[0]))
n0 = len(g.ocr_calls)
ctx = pet.load_ctx(True)
rows, _ = petmatch.grab([petmatch.BOX_NAME + ('name',)])
r1 = pet.resolve_ident(rows[0], ctx)
n1 = len(g.ocr_calls)
r2 = pet.resolve_ident(rows[0], ctx)
check('resolve_ident：第一次 OCR、第二次走 gcache（0 次 OCR）', r1['growth'] and r1['growth'] == r2['growth'] and len(g.ocr_calls) == n1 and n1 > n0)
rc, out, err = run(pet.set_state, 'DKBO2', BRA, '等待', allow_mount=True)
check('沒登錄物種 → find_slot 找不到 布拉奇多斯（72）、零狀態點擊、訊息提 learn-species', rc == 72 and g.state_clicks == [] and 'learn-species' in last_json(out)['msg'], last_json(out).get('msg', ''))
g = new(pets=five())
rc, out, err = run(pet.learn_species_cmd, 'DKBO2', 1, BRA, '1/1/1/1')
check('learn-species：--confirm-growth 不符 → 72、registry 沒檔', rc == 72 and not petmatch.species_path().exists())
rc, out, err = run(pet.learn_species_cmd, 'DKBO2', 2, BRA, '1/1/1/1')
check('learn-species：第 2 格是有名字的朵拉比斯 → 72', rc == 72 and not petmatch.species_path().exists())
rc, out, err = run(pet.learn_species_cmd, 'DKBO2', 1, '不存在的寵', GS[1])
check('learn-species：物種名不在 Monster 表 → 1（用法錯）', rc == 1)
rc, out, err = run(pet.learn_species_cmd, 'DKBO2', 1, BRA, GS[1])
reg = petmatch.load_species()
check('learn-species：成功 → registry 有縮圖 + 字串，面板只有選取沒有任何狀態 / 存取點擊', rc == 0 and BRA in reg['thumb'] and reg['growth'] == {GS[1]: BRA} and g.state_clicks == [] and depot_free(g) == 0, f'rc={rc} {err[-200:]}')
rc, out, err = run(pet.list_roles, 'all')
j = last_json(out)['roles']
check('登錄後 list all：5 人第 1 格都認出物種 布拉奇多斯（縮圖樣板，字串不同也行）、mountlike',
      all(j[r][0]['species'] == BRA and j[r][0]['mountlike'] and j[r][0]['name'] is None for r in fake_pet.ROLES), str([j[r][0].get('species') for r in fake_pet.ROLES]))
check('fmt_slot：?(…)≈布拉奇多斯', '≈布拉奇多斯' in pet.fmt_slot(j['DKBO3'][0]))
rc, out, err = run(pet.set_state, 'DKBO3', BRA, '騎乘', allow_mount=True)
check('set-state --pet 布拉奇多斯（沒名字但物種確認）→ 找得到、本來就是騎乘不點', rc == 0 and g.state_clicks == [] and last_json(out)['slot'] == 1, f'rc={rc}')
rc, out, err = run(pet.set_state, 'DKBO3', BRA, '等待')
check('沒給 --allow-mount：布拉奇多斯（物種確認 = 騎寵）→ 73', rc == 73 and g.state_clicks == [])
# 縮圖被換成別種 → 不再認得
g.pets['DKBO4'][0]['species'] = '烏力斯坦'
rc, out, err = run(pet.list_roles, 'DKBO4')
check('縮圖不同（別的物種）→ species None（不把別種當布拉奇多斯）', last_json(out)['roles']['DKBO4'][0]['species'] is None)
g.pets['DKBO4'][0]['species'] = BRA

# ---- store：沒名字的騎寵 ----
g = new(pets=five(state='等待'))
rc, out, err = run(pet.store, 'DKBO2', BRA, 'personal', allow_slot1=True)
check('store 沒名字的布拉奇多斯（物種確認、無旗標）→ 73 零存入點擊', rc == 73 and depot_free(g) == 0, f'rc={rc}')
rc, out, err = run(pet.store, 'DKBO2', BRA, 'personal', allow_slot1=True, allow_mount_store=BRA)
dn = g.depot['DKBO2']['personal']
check('store --allow-mount-store 布拉奇多斯（沒名字、等待、第 1 格 + slot1）→ rc 0、倉庫 1 張、存入鈕 1 次', rc == 0 and depot_free(g) == 1 and sum(1 for x in dn if x) == 1 and dn[0].get('unnamed') == GS[1], f'rc={rc} {err[-300:]}')
check('  倉庫逐張驗證找到（depot_index 有值）', last_json(out)['depot_index'] == 1)
fresh_tpl()
g = new(pets=five(state='等待'))
rc, out, err = run(pet.store, 'DKBO2', BRA, 'personal', allow_slot1=True, allow_mount_store=BRA)
check('登錄檔是空的（物種未知）：store 沒名字的 → 72（找不到）零存入點擊', rc == 72 and depot_free(g) == 0, f'rc={rc}')
check('  且 --pet 不會把「沒名字」當成任何物種', 'learn-species' in last_json(out)['msg'])

# ---- #84：倉庫存入後重新排序 ----
fresh_tpl()
dep0 = fake_pet.mk_depot(DKBO={'personal': ['摩娜西普', '朵拉比斯', '巴朵蘭恩']})
g = new(pets=mk_pets(DKBO=[{'name': '瑪斯貝卡', 'state': '騎乘', 'level': 1}, {'name': '迪基格斯', 'state': '等待', 'level': 1}, None, None, None]), depot=dep0)
g.resort = True
rc, out, err = run(pet.store, 'DKBO', '迪基格斯', 'personal')
names = [c['name'] for c in g.depot['DKBO']['personal'] if c]
check('倉庫存入後重新排序：store 仍 rc 0（不再誤報 76）、倉庫逐張找得到迪基格斯', rc == 0 and '迪基格斯' in names and names != ['摩娜西普', '朵拉比斯', '巴朵蘭恩', '迪基格斯'], f'rc={rc} names={names} {err[-200:]}')
check('  騎寵沒動、存入鈕 1 次', depot_free(g) == 1 and g.pets['DKBO'][0]['name'] == '瑪斯貝卡')
# 倉庫裡真的找不到（存入鈕按了但被別人拿走）→ 76
g = new(pets=mk_pets(DKBO=[{'name': '瑪斯貝卡', 'state': '騎乘', 'level': 1}, {'name': '迪基格斯', 'state': '等待', 'level': 1}, None, None, None]), depot=fake_pet.mk_depot())
orig = g._store_or_take


def vanish():
    orig()
    for k, c in enumerate(g.depot['DKBO']['personal']):
        if c and c['name'] == '迪基格斯':
            c['name'] = '別的寵'                               # 張數對、但名字不是它（模擬倉庫裡找不到）
g._store_or_take = vanish
rc, out, err = run(pet.store, 'DKBO', '迪基格斯', 'personal')
check('倉庫張數對但逐張看不到該寵物 → 76（不重點）', rc == 76 and depot_free(g) == 1, f'rc={rc}')

# ---- store-many / take-many ----
fresh_tpl()
mkdp = lambda: fake_pet.mk_depot(**{r: {'personal': ['朵拉比斯']} for r in fake_pet.ROLES})    # noqa: E731
mk = lambda: mk_pets(**{r: [{'name': '瑪斯貝卡', 'state': '等待', 'level': 1}, {'name': '迪基格斯', 'state': '出戰', 'level': 1}, {'name': '魯尼帖斯', 'state': '等待', 'level': 1}, None, None] for r in fake_pet.ROLES})   # noqa: E731
g = new(pets=mk(), depot=mkdp())
rc, out, err = run(pet.store_many, 'all', ['迪基格斯', '魯尼帖斯'], 'personal')
j = last_json(out)
nm_of = lambda r: [c['name'] for c in g.depot[r]['personal'] if c]    # noqa: E731
ok_all = all(nm_of(r).count('迪基格斯') == 1 and nm_of(r).count('魯尼帖斯') == 1 for r in fake_pet.ROLES)
check('store-many all × 2 隻：rc 0、10 次存入、每人倉庫各多 2 張、寵物欄剩 瑪斯貝卡', rc == 0 and len(j['ops']) == 10 and depot_free(g) == 10 and ok_all
      and all([x['name'] for x in g.pets[r] if x] == ['瑪斯貝卡'] for r in fake_pet.ROLES), f'rc={rc} {err[-300:]}')
check('  面板只開關一次（只有 1 次 ✕）、5 個頭像都點過', g.clicks.count(uikit.PET.close_xy) == 1 and all((83, petmatch.AVATAR_Y[r]) in g.clicks for r in fake_pet.ROLES))
check('  瑪斯貝卡 5 人都沒動（沒點狀態鈕）', g.state_clicks == [])
g = new(pets=mk(), depot=mkdp())
rc, out, err = run(pet.store_many, 'DKBO,DKBO3', ['瑪斯貝卡'], 'personal')
check('store-many 騎寵沒在 --allow-mount-store 名單 → 73 零點擊', rc == 73 and g.clicks == [], f'rc={rc}')
rc, out, err = run(pet.store_many, 'DKBO,DKBO3', ['瑪斯貝卡'], 'personal', allow_slot1=True, allow_mount_store=['瑪斯貝卡'])
check('store-many 騎寵 + 名單 + slot1：2 人各存 1 隻（狀態 = 等待）', rc == 0 and depot_free(g) == 2 and '瑪斯貝卡' in [c['name'] for c in g.depot['DKBO3']['personal'] if c], f'rc={rc} {err[-200:]}')
g = new(pets=mk(), depot=mkdp())
rc, out, err = run(pet.store_many, 'DKBO,DKBO2', ['烏力斯坦'], 'personal', skip_missing=True)
check('store-many --skip-missing：角色沒有就略過 rc 0、0 存入', rc == 0 and depot_free(g) == 0 and all(o.get('skipped') for o in last_json(out)['ops']), f'rc={rc}')
rc, out, err = run(pet.store_many, 'DKBO,DKBO2', ['烏力斯坦'], 'personal')
check('store-many 沒 --skip-missing：沒有 → 72', rc == 72 and depot_free(g) == 0)
check('store-many 角色不認得 / 寵物名不在 Monster 表 → 1', run(pet.store_many, 'DKBO9', ['迪基格斯'])[0] == 1 and run(pet.store_many, 'all', ['亂碼寵'])[0] == 1)
g = new(pets=mk(), depot=mkdp())
for r in fake_pet.ROLES:
    g.pets[r] = [x for x in g.pets[r] if x and x['name'] == '瑪斯貝卡'] + [None] * 4
rc, out, err = run(pet.take_many, 'all', ['朵拉比斯'], 'personal')
j = last_json(out)
check('take-many all：5 人各從個人倉庫取出 朵拉比斯（現場逐張找）、寵物欄第 2 格、預設等待、倉庫清空', rc == 0 and len(j['ops']) == 5 and all(g.pets[r][1] and g.pets[r][1]['name'] == '朵拉比斯' and g.pets[r][1]['state'] == '等待' for r in fake_pet.ROLES)
      and all(not [c for c in g.depot[r]['personal'] if c] for r in fake_pet.ROLES), f'rc={rc} {err[-300:]}')
check('  取出鈕只點 5 次、面板只關 1 次', depot_free(g) == 5 and g.clicks.count(uikit.PET.close_xy) == 1)
g = new(pets=mk(), depot=mkdp())
rc, out, err = run(pet.take_many, 'DKBO', ['迪基格斯'], 'personal')
check('take-many 倉庫沒有 → 72、零取出點擊', rc == 72 and depot_free(g) == 0, f'rc={rc}')
rc, out, err = run(pet.take_many, 'DKBO,DKBO2', ['迪基格斯'], 'personal', skip_missing=True)
check('take-many --skip-missing：略過 rc 0', rc == 0 and depot_free(g) == 0 and all(o.get('skipped') for o in last_json(out)['ops']), f'rc={rc}')
g = new(pets=five(state='等待'), depot=fake_pet.mk_depot(DKBO2={'public': [{'name': BRA, 'unnamed': GS[1], 'species': BRA, 'level': 1}, '朵拉比斯']}))
g.pets['DKBO'] = [None] * 5
rc, out, err = run(pet.take, 'DKBO', 'public', None, None, False, True, BRA)
check('take --pet 布拉奇多斯：登錄檔空 → 倉庫裡只有沒名字的卡 → 72、零取出點擊', rc == 72 and depot_free(g) == 0, f'rc={rc}')
reg = {'thumb': {BRA: [[(1, 2, 3)] * 16]}, 'growth': {GS[1]: BRA}}
petmatch.save_species(reg)
g.pets['DKBO2'] = [None] * 5
g.role = 'DKBO2'
rc, out, err = run(pet.take, 'DKBO2', 'public', None, None, False, True, BRA)
check('take --pet 布拉奇多斯：成長字串在登錄檔 → 找到並取出；取出後縮圖物種不符登錄樣板（縮圖空登錄）→ 仍因字串吻合通過', rc == 0 and depot_free(g) == 1 and g.pets['DKBO2'][0] and g.pets['DKBO2'][0].get('unnamed') == GS[1], f'rc={rc} {err[-300:]}')
check('take 沒給 --index 也沒給 --pet → 1', run(pet.take, 'DKBO', 'public')[0] == 1)

# ---- store-many --pick：同物種多隻新寵物 ----
fresh_tpl()
g = new(pets=mk_pets(DKBO=[{'name': '朵拉比斯', 'state': '出戰', 'level': 1}, unn(0, '等待'), unn(1, '等待'), unn(2, '等待'), None]))
rc, out, err = run(pet.learn_species_cmd, 'DKBO', 2, BRA, GS[0])
check('pick 前置：learn-species 第 2 格', rc == 0, f'rc={rc}')
rc, out, err = run(pet.store_many, 'DKBO', [BRA, BRA], 'public', False, [BRA])
check('同物種 3 隻、沒給 --pick → 72（同名多隻要指定）零存入點擊', rc == 72 and depot_free(g) == 0, f'rc={rc}')
rc, out, err = run(pet.store_many, 'DKBO', [BRA, BRA], 'public', False, [BRA], pick='last')
left = [p for p in g.pets['DKBO'] if p]
pub = [c for c in g.depot['DKBO']['public'] if c]
check('--pick last：存最後 2 隻進公共，欄位留 朵拉比斯 + 第 1 隻布拉奇多斯（成長字串 49/9/8/2）', rc == 0 and len(pub) == 2 and [p.get('unnamed') for p in left] == [None, GS[0]], f'rc={rc} {[p.get("unnamed") for p in left]} {err[-300:]}')
check('  存的是 slot 3 / 4 的（成長字串 49/9/7/2、48/9/7/1）', sorted(c['unnamed'] for c in pub) == sorted([GS[1], GS[2]]))
rc, out, err = run(pet.take_many, 'DKBO', [BRA], 'public')
check('take-many 從公共取回 1 隻沒名字的布拉奇多斯（成長字串靠登錄檔）', rc == 0 and g.pets['DKBO'][2] is not None and g.pets['DKBO'][2].get('unnamed') in (GS[1], GS[2]), f'rc={rc} {err[-200:]}')


# ---------------- 2026-10-12：批次取出 / 不准盲取 / set-state-many ----------------
fresh_tpl()
check('parse_target：名字 / @等級 / #成長字串 / 組合 / 錯字', pet.parse_target('朵拉比斯') == {'name': '朵拉比斯', 'growth': None, 'level': None}
      and pet.parse_target('朵拉比斯@126')['level'] == 126 and pet.parse_target('朵拉比斯@Lv1')['level'] == 1
      and pet.parse_target('#35/7/3/8') == {'name': None, 'growth': '35/7/3/8', 'level': None}
      and pet.parse_target('克邦凱斯#35/7/3/8@1') == {'name': '克邦凱斯', 'growth': '35/7/3/8', 'level': 1}
      and pet.parse_target('亂碼寵') is None and pet.parse_target('') is None and pet.parse_target('#35/7/3') is None)
check('parse_plan / group_ops：同角色排在一起、保持順序', [r for r, _ in pet.group_ops(pet.parse_plan('DKBO2:朵拉比斯,DKBO3:#1/2/3/4,DKBO2:迪基格斯'))] == ['DKBO2', 'DKBO2', 'DKBO3']
      and pet.parse_plan('DKBO9:朵拉比斯') is None and pet.parse_plan('DKBO2朵拉比斯') is None)
sl = [{'slot': 1, 'name': 'A'}, {'slot': 2, 'name': 'B'}, {'slot': 3, 'name': 'C'}, {'slot': 4, 'empty': True}, {'slot': 5, 'empty': True}]
check('shift_slots：存走第 2 格 → 後面補位、最後空', [(x['slot'], x.get('name')) for x in pet.shift_slots(sl, 2)] == [(1, 'A'), (2, 'C'), (3, None), (4, None), (5, None)])
check('parse_card_level：一致才採用', pet.parse_card_level(['0轉126級', '轉126']) == 126 and pet.parse_card_level(['0轉126級', '0轉12級']) is None and pet.parse_card_level([]) is None)
cache = {0: 'a', 1: 'b', 2: 'c'}
pet.shift_cache(cache, 1)
check('shift_cache：取走第 2 格 → 後面格號 -1', cache == {0: 'a', 1: 'c'})
g = new()
rc, out, err = run(pet.take, 'DKBO', 'personal', 1, None)
check('B：take --index 沒給 --expect-* → 1（不准盲取）、零點擊', rc == 1 and g.clicks == [], f'rc={rc}')
# 批次：4 人各從公共取不同目標（面板 / 倉庫分頁 / 子分頁只切一次）
pub = {'DKBO2': ['左迪洛斯', '加克拉'], 'DKBO3': ['加克拉', '左迪洛斯'], 'DKBO4': ['左迪洛斯', {'name': '加格', 'unnamed': '34/7/4/8', 'level': 1}], 'DKBO5': ['朵拉比斯']}
g = new(pets=mk_pets(**{r: [{'name': '瑪斯貝卡', 'state': '騎乘', 'level': 1}, None, None, None, None] for r in fake_pet.ROLES}),
        depot=fake_pet.mk_depot(**{r: {'public': v} for r, v in pub.items()}))
rc, out, err = run(pet.take_plan, pet.parse_plan('DKBO2:加克拉,DKBO3:加克拉,DKBO4:#34/7/4/8,DKBO5:朵拉比斯'), 'public')
j = last_json(out)
check('take_plan：4 人各取對的那隻（成長字串取沒名字的）', rc == 0 and [g.pets[r][1] and (g.pets[r][1].get('unnamed') or g.pets[r][1]['name']) for r in ('DKBO2', 'DKBO3', 'DKBO4', 'DKBO5')] == ['加克拉', '加克拉', '34/7/4/8', '朵拉比斯']
      and [c['name'] for c in g.depot['DKBO2']['public'] if c] == ['左迪洛斯'], f'rc={rc} {err[-300:]}')
check('  面板開 / 關各 1 次、倉庫分頁點 1 次、公共子分頁點 1 次、切回寵物分頁 1 次、每人頭像 1 次',
      g.clicks.count(uikit.PET.close_xy) == 1 and g.clicks.count(pet.DEPOT_TAB_XY) == 1 and g.clicks.count(pet.SUBTAB_XY['public']) == 1
      and g.clicks.count(pet.PET_TAB_XY) == 1 and all(g.clicks.count((83, petmatch.AVATAR_Y[r])) == 1 for r in ('DKBO2', 'DKBO3', 'DKBO4', 'DKBO5')), f'{len(g.clicks)} clicks')
check('  沒有逐格讀寵物欄（點寵物格只有取出後選新寵物那 4 下）', sum(1 for c in g.clicks if c[0] == pet.SLOT_X) == 4, str([c for c in g.clicks if c[0] == pet.SLOT_X]))
print(f'      （批次取 4 隻共 {len(g.clicks)} 下點擊）')
# 同名多隻：等級讀不出來 → 不盲取；讀得到 → 取對的
# ---- 2026-10-14 格號遞補（errlog #843～851 卡坦分配：公共倉庫取出一隻後後面的卡往前補位，沿用舊格號就對不上）----
check('parse_target ~N 格號提示：只在有名字 / 成長字串時收；超出 1～20 拒絕；fmt 往返',
      pet.parse_target('加克拉~4') == {'name': '加克拉', 'growth': None, 'level': None, 'hint': 4}
      and pet.parse_target('#34/7/4/8@1~12')['hint'] == 12 and pet.parse_target('@1~3') is None and pet.parse_target('加克拉~21') is None
      and pet.parse_target('朵拉比斯') == {'name': '朵拉比斯', 'growth': None, 'level': None}
      and pet.fmt_target(pet.parse_target('加克拉#34/7/4/8@1~5')) == '加克拉#34/7/4/8@1~5')
_h = {0: 3, 1: 4, 2: 2, 3: 9}
pet.shift_hints(_h, [0, 1, 2], 3)
check('shift_hints：同倉庫取走第 3 格 → 提示 4 變 3、≤3 不動、別的倉庫（項 3）不動', _h == {0: 3, 1: 3, 2: 2, 3: 9}, str(_h))
pet.shift_hints(_h, [0, 1, 2], None)
check('shift_hints：取走哪格不明 → 不動（取前仍會核對身分）', _h == {0: 3, 1: 3, 2: 2, 3: 9})
_U = lambda g_, lv=1: {'name': '加格', 'unnamed': g_, 'level': lv}       # noqa: E731  沒名字的新寵物卡（名字框 = 成長字串）
_MOUNT = [{'name': '瑪斯貝卡', 'state': '騎乘', 'level': 1}, None, None, None, None]


def _ctake(cards, plan):
    g_ = new(pets=mk_pets(DKBO2=list(_MOUNT)), depot=fake_pet.mk_depot(DKBO2={'public': cards}))
    g_.compact = True                                                  # 實機：取出後後面的卡往前遞補
    rc_, out_, err_ = run(pet.take_plan, pet.parse_plan(plan), 'public')
    return g_, rc_, last_json(out_), err_


g, rc, j, err = _ctake(['左迪洛斯', _U('34/7/4/8'), _U('31/7/4/8'), '加克拉', '摩娜西普'], 'DKBO2:#31/7/4/8~3,DKBO2:加克拉~4')
check('遞補：先取第 3 格 → 第 4 格的加克拉補到第 3 格；計畫提示 ~4 自動 -1 → 直接取第 3 格、不用重新定位',
      rc == 0 and [p and (p.get('unnamed') or p['name']) for p in g.pets['DKBO2'][1:3]] == ['31/7/4/8', '加克拉']
      and [o.get('index') for o in j['ops']] == [3, 3] and not any(o.get('relocated') for o in j['ops'])
      and [c and (c.get('unnamed') or c['name']) for c in g.depot['DKBO2']['public'][:3]] == ['左迪洛斯', '34/7/4/8', '摩娜西普'], f'rc={rc} {j["ops"]} {err[-200:]}')
g, rc, j, err = _ctake(['左迪洛斯', '加克拉', '摩娜西普'], 'DKBO2:加克拉~3')
check('提示過期（第 3 格是摩娜西普）→ 重讀倉庫以身分定位到唯一的加克拉（第 2 格）取出',
      rc == 0 and g.pets['DKBO2'][1]['name'] == '加克拉' and j['ops'][0]['relocated']['from'] == 3 and j['ops'][0]['relocated']['to'] == 2 and depot_free(g) == 1, f'rc={rc} {j["ops"]}')
g, rc, j, err = _ctake(['左迪洛斯', _U('34/7/4/8'), '加克拉', _U('34/7/4/8')], 'DKBO2:#34/7/4/8~1')
check('提示過期且同字串 2 張（撞號）→ 72、取出鈕 0 次（不猜）', rc == 72 and depot_free(g) == 0 and '2 張' in j['ops'][0].get('msg', ''), f'rc={rc} {j["ops"]}')
g, rc, j, err = _ctake(['左迪洛斯', _U('34/7/4/8', 1), '加克拉', _U('34/7/4/8', 2)], 'DKBO2:#34/7/4/8~4')
check('同字串 2 張、提示指對那張 → 取提示的第 4 張（Lv2），不是第一張吻合的', rc == 0 and g.pets['DKBO2'][1]['level'] == 2 and g.depot['DKBO2']['public'][1]['level'] == 1, f'rc={rc} {j["ops"]}')
g, rc, j, err = _ctake(['左迪洛斯', '加克拉'], 'DKBO2:加克拉~7')
check('提示指到空格（遞補後已沒那麼多張）→ 以身分定位取第 2 格', rc == 0 and g.pets['DKBO2'][1]['name'] == '加克拉' and j['ops'][0]['relocated']['to'] == 2, f'rc={rc} {j["ops"]}')
g = new(pets=mk_pets(DKBO2=list(_MOUNT)), depot=fake_pet.mk_depot(DKBO2={'public': ['左迪洛斯', '加克拉']}))
g.compact = True
rc, out, err = run(pet.take, 'DKBO2', 'public', 1, '加克拉')
check('單次 take --index 不受影響：第 1 格不是加克拉 → 72 不取、不自動改找（身分照驗）', rc == 72 and depot_free(g) == 0 and not last_json(out).get('relocated'), f'rc={rc}')
g, rc, j, err = _ctake(['左迪洛斯', _U('34/7/4/8'), _U('31/7/4/8'), '加克拉'], 'DKBO2:#34/7/4/8,DKBO2:#31/7/4/8,DKBO2:加克拉')
check('沒給提示的 take-many：每隻都現場以身分找（取走後遞補也取對）', rc == 0 and [p and (p.get('unnamed') or p['name']) for p in g.pets['DKBO2'][1:4]] == ['34/7/4/8', '31/7/4/8', '加克拉'], f'rc={rc} {j["ops"]}')

twin = {'DKBO': {'personal': [{'name': '朵拉比斯', 'level': 126}, {'name': '朵拉比斯', 'level': 1}]}}
g = new(pets=mk_pets(DKBO=[{'name': '瑪斯貝卡', 'state': '騎乘', 'level': 1}, None, None, None, None]), depot=fake_pet.mk_depot(**twin))
rc, out, err = run(pet.take, 'DKBO', 'personal', None, None, False, True, '朵拉比斯', None, 1)
check('B：同名 2 隻（Lv126 / Lv1）卡片等級讀不出來 → 72、取出鈕 0 次', rc == 72 and depot_free(g) == 0, f'rc={rc}')
g = new(pets=mk_pets(DKBO=[{'name': '瑪斯貝卡', 'state': '騎乘', 'level': 1}, None, None, None, None]), depot=fake_pet.mk_depot(**twin))
g.card_lvl_ocr = True
rc, out, err = run(pet.take, 'DKBO', 'personal', None, None, False, True, '朵拉比斯', None, 1)
check('B：卡片等級讀得到 → 取 Lv1 那隻（不是第 1 格的 Lv126）', rc == 0 and g.pets['DKBO'][1]['level'] == 1 and g.depot['DKBO']['personal'][0]['level'] == 126, f'rc={rc} {err[-200:]}')
g = new(pets=mk_pets(DKBO=[{'name': '瑪斯貝卡', 'state': '騎乘', 'level': 1}, None, None, None, None]), depot=fake_pet.mk_depot(**twin))
g.card_lvl_ocr = True
rc, out, err = run(pet.take, 'DKBO', 'personal', 1, '朵拉比斯', False, True, None, None, 1)
check('B：--index 1 --expect 朵拉比斯 --expect-level 1，第 1 格是 Lv126 → 取前就擋 72', rc == 72 and depot_free(g) == 0, f'rc={rc}')

# ---- 2026-10-14 卡坦 restore：個人倉庫朵拉比斯 Lv123 卡讀成 23（掉百位）被排除、Lv130 讀不出 → 只剩它被取出（76）----
P = pet.parse_card_level
check('parse_card_level：掉百位的尾巴併成最長值（129×2 + 29 → 129）', P(['0轉129級', '0轉129級', '0轉29級']) == 129)
check('parse_card_level：只讀到尾巴 → 回尾巴（由 level_uncertain 當不確定）', P(['0轉26級', '0轉26級', '0轉6']) == 26)
check('parse_card_level：最長值只有 1 行 → 不採用（1 讀成 11 不能變 11）', P(['0轉1級', '0轉11級']) is None)
check('parse_card_level：l / I 當 1、超出 140 丟掉', P(['0轉l23級', '0轉123級']) == 123 and P(['0轉199級']) is None and P(['0轉0級']) is None)
U = pet.level_uncertain
check('level_uncertain：讀不到 / 尾巴（23、3 vs 123）不確定；130、1 vs 123 確定不是；相等不是不確定',
      U(None, 123) and U(23, 123) and U(3, 123) and not U(130, 123) and not U(1, 123) and not U(123, 123) and not U(12, 123) and not U(5, None))
twin2 = {'DKBO': {'personal': [{'name': '朵拉比斯', 'level': 130}, {'name': '朵拉比斯', 'level': 123}]}}
mount_only = mk_pets(DKBO=[{'name': '瑪斯貝卡', 'state': '騎乘', 'level': 1}, None, None, None, None])


def bad_lvl(idx, c, opts):
    """實機重現：Lv130 讀不出、Lv123 每組都讀成 23"""
    return [] if c['level'] == 130 else ['0轉23級', '0轉23級']


g = new(pets=mount_only, depot=fake_pet.mk_depot(**twin2))
g.card_lvl_fn = bad_lvl
rc, out, err = run(pet.take, 'DKBO', 'personal', None, None, False, True, '朵拉比斯', None, 123)
check('卡坦 restore 重現：Lv130 讀不出、Lv123 讀成 23 → 兩張都不確定 → 72 不取（舊版取到 Lv130）', rc == 72 and depot_free(g) == 0, f'rc={rc} {err[-200:]}')


def extra_ok(idx, c, opts):
    """第一組讀成 23、加讀（CARD_LVL_EXTRA）讀對"""
    if tuple(opts) in [tuple(o) for o in pet.CARD_LVL_EXTRA]:
        return [f'0轉{c["level"]}級'] * 2
    return [] if c['level'] == 130 else ['0轉23級', '0轉23級']


g = new(pets=mount_only, depot=fake_pet.mk_depot(**twin2))
g.card_lvl_fn = extra_ok
rc, out, err = run(pet.take, 'DKBO', 'personal', None, None, False, True, '朵拉比斯', None, 123)
check('不確定的卡逐張加讀 → 讀到 123 那張就取它（不是 Lv130）', rc == 0 and g.pets['DKBO'][1]['level'] == 123 and g.depot['DKBO']['personal'][0]['level'] == 130, f'rc={rc} {err[-200:]}')
g = new(pets=mount_only, depot=fake_pet.mk_depot(**{'DKBO': {'personal': [{'name': '朵拉比斯', 'level': 123}]}}))
g.card_lvl_fn = bad_lvl
rc, out, err = run(pet.take, 'DKBO', 'personal', None, None, False, True, '朵拉比斯', None, 123)
check('同名只有 1 張、等級讀成 23 → 取它，取出後讀等級驗過', rc == 0 and g.pets['DKBO'][1]['level'] == 123, f'rc={rc} {err[-200:]}')
g = new(pets=mount_only, depot=fake_pet.mk_depot(**twin2))
g.card_lvl_fn = bad_lvl
rc, out, err = run(pet.take, 'DKBO', 'personal', 2, '朵拉比斯', False, True, None, None, 123)
check('--index 2 --expect-level 123：卡片讀成 23 不再當「不是」擋掉（取出後驗等級）', rc == 0 and g.pets['DKBO'][1]['level'] == 123, f'rc={rc} {err[-200:]}')
g = new(pets=mount_only, depot=fake_pet.mk_depot(**{'DKBO': {'personal': [{'name': '朵拉比斯', 'level': 130}, {'name': '朵拉比斯', 'level': 123}]}}))
g.card_lvl_ocr = True
rc, out, err = run(pet.take_plan, pet.parse_plan('DKBO:朵拉比斯@123'), 'personal')
check('take-many --plan DKBO:朵拉比斯@123：同名多隻依卡片等級選 123', rc == 0 and g.pets['DKBO'][1]['level'] == 123, f'rc={rc} {err[-200:]}')
# set-state-many
g = new()
rc, out, err = run(pet.set_state_many, 'all', '迪基格斯', '等待')
check('set-state-many all 迪基格斯 等待：5 人各點 1 次、面板關 1 次、騎寵沒動', rc == 0 and len(g.state_clicks) == 5 and g.clicks.count(uikit.PET.close_xy) == 1
      and all(g.pets[r][1]['state'] == '等待' and g.pets[r][0]['state'] == '騎乘' for r in fake_pet.ROLES), f'rc={rc} {g.state_clicks}')
rc, out, err = run(pet.set_state_many, 'all', '迪基格斯', '等待')
check('  再跑一次：已是目標 → 0 次狀態鈕', rc == 0 and len(g.state_clicks) == 5)
rc, out, err = run(pet.set_state_many, 'DKBO,DKBO2', '瑪斯貝卡', '等待')
check('set-state-many 騎寵沒 --allow-mount → 73、不點', rc == 73 and len(g.state_clicks) == 5, f'rc={rc}')
# store-many：每人只完整讀一次寵物欄
fresh_tpl()
g = new(pets=mk(), depot=mkdp())
rc, out, err = run(pet.store_many, 'DKBO,DKBO2', ['迪基格斯', '魯尼帖斯'], 'personal')
check('store-many 每人 2 隻：每人頭像只點 1 次（第 2 隻用推算的欄位、選格重讀核對）', rc == 0 and depot_free(g) == 4
      and g.clicks.count((83, petmatch.AVATAR_Y['DKBO'])) == 1 and g.clicks.count((83, petmatch.AVATAR_Y['DKBO2'])) == 1, f'rc={rc} {err[-300:]}')
fresh_tpl()
g = new(pets=mk_pets(DKBO=[unn(0, '騎乘'), {'name': '朵拉比斯', 'state': '出戰', 'level': 1}, None, None, None]))
rc, out, err = run(pet.store_many, 'DKBO', ['摩娜西普'], 'public', skip_missing=True)
check('store-many --skip-missing：騎乘中的沒名字騎寵不擋「沒有就略過」', rc == 0 and depot_free(g) == 0 and last_json(out)['ops'][0].get('skipped'), f'rc={rc}')

# ---- 身分跨程序快取 + levels（2026-10-13 review 1013b §1.1 / §2.3）----
def name_ocr(g):
    return sum(1 for b, _ in g.ocr_calls if b == tuple(petmatch.BOX_NAME))


fresh_tpl()
g = new(pets=five())
rc, out, err = run(pet.list_roles, 'DKBO2')
j1 = last_json(out)
n_a = name_ocr(g)
check('icache：第 1 次 list（新程序）沒名字的騎寵要 OCR 成長字串、寫進快取檔', rc == 0 and n_a > 0 and pet.icache_path().exists()
      and json.loads(pet.icache_path().read_text(encoding='utf-8'))['ver'] == pet.ICACHE_VER, f'name OCR {n_a}')
rc, out, err = run(pet.list_roles, 'DKBO2')
j2 = last_json(out)
check('icache：第 2 次 list（另一個 ctx = 模擬新子程序）點陣相同 → 0 次名字 OCR、結果相同、icache_hits ≥ 1',
      rc == 0 and name_ocr(g) == n_a and j2['roles']['DKBO2'][0]['unnamed'] == GS[1] and j2['icache_hits'] >= 1
      and j2['roles']['DKBO2'][0]['nh'] == j1['roles']['DKBO2'][0]['nh'], f'{name_ocr(g) - n_a} 次 {j2.get("icache_hits")}')
ctx = pet.load_ctx(True)                                   # store / take / petdrop 用的 ctx：沒開快取
g.panel, g.sel = True, 0
rows, _ = petmatch.grab([petmatch.BOX_NAME + ('name',)])
n_b = name_ocr(g)
r = pet.resolve_ident(rows[0], ctx)
check('icache：store / take / petdrop 的 ctx（預設不開）→ 照樣現場 OCR（不取代存倉 / 丟寵的現場驗名）', r['growth'] == GS[1] and name_ocr(g) > n_b and not r.get('cached'))
ctx = pet.load_ctx(True, use_icache=True)
r = pet.resolve_ident(['0' * 10, '0' * 10], ctx)
check('icache：沒墨點的點陣不查不寫', r['growth'] is None and not ctx.get('idirty'))
_raw = json.loads(pet.icache_path().read_text(encoding='utf-8'))
check('icache：過期（> 7 天）的丟掉；版本不符 → 空', pet.load_icache(now=time.time() + pet.ICACHE_TTL_S + 60)['growth'] == {}
      and (pet.icache_path().write_text(json.dumps(dict(_raw, ver=0)), encoding='utf-8') or True) and pet.load_icache()['growth'] == {})
pet.icache_path().write_text(json.dumps(_raw), encoding='utf-8')
_c = {'growth': {f'k{i}': [str(i), i] for i in range(pet.ICACHE_MAX + 50)}, 'img': {}}
pet.save_icache(_c)
_l = json.loads(pet.icache_path().read_text(encoding='utf-8'))
check('icache：每區只留最近 ICACHE_MAX 筆（依時間）', len(_l['growth']) == pet.ICACHE_MAX and f'k{pet.ICACHE_MAX + 49}' in _l['growth'] and 'k0' not in _l['growth'])
pet.icache_path().write_text(json.dumps(_raw), encoding='utf-8')
pet.ICACHE_ON = False
rc, out, err = run(pet.list_roles, 'DKBO2')
check('--no-icache → 照樣 OCR', name_ocr(g) > n_b + 1 and last_json(out)['icache_hits'] == 0)
pet.ICACHE_ON = True
# 縮圖結果快取：整格像素 + 候選完全相同才沿用
import petimg_match as _M  # noqa: E402
_sv = (pet.IMG_ON, _M.index, _M.cells_of, _M.read_cell, pet.img_match)
_n = {'match': 0}
_cells = {'v': {(1, 1): (10, 20, 30), (2, 2): (40, 50, 60)}}
pet.IMG_ON = True
_M.index = lambda: {'x': ['朵拉比斯']}
_M.cells_of = lambda kind: [(i, 250, 200 + i) for i in range(5)]
_M.read_cell = lambda kind, cx, cy: dict(_cells['v'])
pet.img_match = lambda cells, kind, cx, cy, ctx, text=(), partial=True: (_n.__setitem__('match', _n['match'] + 1), {'img_species': '克邦凱斯', 'img_score': 0.9, 'img_occluded': False})[1]
try:
    c1 = pet.load_ctx(True, ['克邦凱斯', '加克拉'], use_icache=True)
    a1 = pet.img_ident('slot', 1, c1)
    pet.save_ctx(c1)
    c2 = pet.load_ctx(True, ['克邦凱斯', '加克拉'], use_icache=True)
    a2 = pet.img_ident('slot', 1, c2)
    check('縮圖快取：同一格像素 + 同候選 → 第 2 個程序不再比對（img_cached）', _n['match'] == 1 and a2['img_species'] == '克邦凱斯' and a2.get('img_cached'), str(_n))
    c3 = pet.load_ctx(True, ['克邦凱斯', '邦恩吉'], use_icache=True)
    pet.img_ident('slot', 1, c3)
    _cells['v'] = {(1, 1): (10, 20, 31), (2, 2): (40, 50, 60)}
    c4 = pet.load_ctx(True, ['克邦凱斯', '加克拉'], use_icache=True)
    pet.img_ident('slot', 1, c4)
    pet.img_ident('slot', 1, pet.load_ctx(True, ['克邦凱斯', '加克拉']))
    check('縮圖快取：候選不同 / 像素差 1 / 沒開快取 → 都重比', _n['match'] == 4, str(_n))
finally:
    pet.IMG_ON, _M.index, _M.cells_of, _M.read_cell, pet.img_match = _sv
# levels：只讀等級（不 OCR 名字），nh 與 list 相同
g = new(pets=five())
run(pet.list_roles, 'all')
n_c = name_ocr(g)
rc, out, err = run(pet.list_levels, 'all')
lv = last_json(out)['roles']
check('levels：5 人每格等級 + nh、0 次名字 OCR、沒點狀態鈕', rc == 0 and name_ocr(g) == n_c and g.state_clicks == []
      and all(x['level'] == 1 for r in lv for x in lv[r] if not x.get('empty')) and lv['DKBO2'][0]['nh'] == j1['roles']['DKBO2'][0]['nh'], f'rc={rc} {lv.get("DKBO2")}')
rc, out, err = run(pet.list_levels, 'DKBO3', [2])
sl = last_json(out)['roles']['DKBO3']
check('levels --slots 2：只讀第 2 格（空格照列）', rc == 0 and [x['slot'] for x in sl if not x.get('empty')] == [2] and any(x.get('empty') for x in sl), str(sl))
rc, out, err = run(pet.list_levels, 'DKBO3', [7])
check('levels --slots 超出 1～5 → 用法錯誤', rc == uikit.EXIT_USAGE)

# ---- 2026-10-14 恐龍博士：40/9/6/5 名字框讀不出（Windows OCR 把「40」讀成「姍」）----
L = ['姍/9/6/5', '40/9/6/5', '姍/6/5']                       # 實機 -Dark 0 -Zooms 2,3,4 讀到的三行（2 / 3 / 4 倍各一行）
check('parse_growth：1 行完整 + 開頭欄被讀成漢字的殘行 → 採用（2026-10-14）', petmatch.parse_growth(L) == '40/9/6/5')
check('growth_compatible：漢字萬用欄最多 1 個、數字欄要逐欄相等、至少 2 欄數字',
      petmatch.growth_compatible('姍/9/6/5', '40/9/6/5') and petmatch.growth_compatible('姍/6/5', '40/9/6/5')
      and not petmatch.growth_compatible('姍/8/6/5', '40/9/6/5') and not petmatch.growth_compatible('姍/姍/6/5', '40/9/6/5')
      and not petmatch.growth_compatible('姍/5', '40/9/6/5') and petmatch.growth_compatible('40/9/5', '40/9/6/5'))
check('parse_growth：殘行數字矛盾 / 兩個萬用欄 → None（不猜）', petmatch.parse_growth(['40/9/6/5', '姍/8/6/5']) is None and petmatch.parse_growth(['40/9/6/5', '姍/姍/6/5']) is None)
check('growth_guess：只有一種完整字串（1 行也行）、其餘不矛盾 → 候選；兩種完整字串 / 矛盾 → None',
      petmatch.growth_guess(['40/9/6/5']) == '40/9/6/5' and petmatch.growth_guess(['40/9/6/5', '41/9/6/5']) is None
      and petmatch.growth_guess(['40/9/6/5', '姍/8/6/5']) is None and petmatch.growth_guess(['姍/9/6/5']) is None)
check('growth_like', petmatch.growth_like(['姍/9/6/5']) and not petmatch.growth_like(['朵拉比斯']) and not petmatch.growth_like([]))
_sv2 = (pet._petwatch, petmatch.match_whole, petmatch.ink)
petmatch.match_whole = lambda *a, **k: (None, 0.0, None)
petmatch.ink = lambda rows: 999
try:
    _pw1 = _PW([['姍/9/6/5', '40/9/6/5'], [], ['40/9/6/5']])                       # 同一個實例（ocr_pet_name 與加讀共用一串回應）
    pet._petwatch = lambda: _pw1
    r = pet.resolve_ident(['1' * 5], pet.load_ctx(False))
    check('resolve_ident：兩組湊不齊但像成長字串 → 加讀 -Zooms 5,6，2 行同意 → growth', r['growth'] == '40/9/6/5' and r['raw'][-1] == '40/9/6/5', str(r))
    _pw1 = _PW([['姍/9/6/5'], [], ['姍/9/6/5']])                       # 同一個實例（ocr_pet_name 與加讀共用一串回應）
    pet._petwatch = lambda: _pw1
    r = pet.resolve_ident(['1' * 6], pet.load_ctx(False))
    check('resolve_ident：加讀後仍湊不齊、也沒完整行 → growth / guess 都 None', r['growth'] is None and not r.get('guess'), str(r))
    _pw1 = _PW([['姍/9/6/5', '40/9/6/5', '41/9/6/5'], [], []])                       # 同一個實例（ocr_pet_name 與加讀共用一串回應）
    pet._petwatch = lambda: _pw1
    r = pet.resolve_ident(['1' * 7], pet.load_ctx(False))
    check('resolve_ident：兩種完整字串 → 不給候選', r['growth'] is None and not r.get('guess'))
    _pw1 = _PW([['40/9/6/5'], [], []])                       # 同一個實例（ocr_pet_name 與加讀共用一串回應）
    pet._petwatch = lambda: _pw1
    r = pet.resolve_ident(['1' * 8], pet.load_ctx(False))
    check('resolve_ident：只有 1 行完整、沒殘行 → growth None、guess = 候選', r['growth'] is None and r.get('guess') == '40/9/6/5', str(r))
finally:
    pet._petwatch, petmatch.match_whole, petmatch.ink = _sv2
U = {'slot': 2, 'name': None, 'unreadable': True, 'guess': '40/9/6/5', 'img_species': '魯尼帖斯', 'state': '等待'}
R = {'growth': {'40/9/6/5': '魯尼帖斯'}}
check('guess_species：候選字串已登錄 + 縮圖同物種 → 物種；缺一或矛盾 / 騎寵 → None',
      pet.guess_species(U, R) == '魯尼帖斯' and pet.guess_species(dict(U, img_species=None), R) is None
      and pet.guess_species(dict(U, img_species='貝魯卡'), R) is None and pet.guess_species(U, {'growth': {}}) is None
      and pet.guess_species(dict(U, img_species='布拉奇多斯'), {'growth': {'40/9/6/5': '布拉奇多斯'}}) is None
      and pet.guess_species(dict(U, unreadable=False), R) is None)
sl = dict(U, unnamed='40/9/6/5', species='魯尼帖斯')
check('ident_matches：靠候選認的格，現場也讀不出時比候選字串；讀出成長字串照比；候選不同 → 不符',
      pet.ident_matches({'growth': None, 'guess': '40/9/6/5'}, sl) and pet.ident_matches({'growth': '40/9/6/5'}, sl)
      and not pet.ident_matches({'growth': None, 'guess': '41/9/6/5'}, sl) and not pet.ident_matches({'growth': None, 'guess': '40/9/6/5'}, {'unnamed': '40/9/6/5'}))
check('slot_ident / guard_store：三重確認後當沒名字的魯尼帖斯（第 2 格、等待）可存；只有縮圖 → 照舊拒絕',
      pet.slot_ident(sl) == '魯尼帖斯' and pet.guard_store(sl, False) is None and pet.guard_store(U, False) is not None)
C = dict(U, ocr=L)
check('unreadable_learn_reason：第 2 格等待、OCR 不矛盾、縮圖同物種 → 可登錄', pet.unreadable_learn_reason(C, 2, '魯尼帖斯', '40/9/6/5') is None)
check('unreadable_learn_reason：第 1 格 / 騎乘 / 出戰 / 騎寵物種 / 縮圖像騎寵 → 73',
      all(pet.unreadable_learn_reason(c, n, sp, '40/9/6/5')[0] == pet.EXIT_FORBID for c, n, sp in
          ((C, 1, '魯尼帖斯'), (dict(C, state='騎乘'), 2, '魯尼帖斯'), (dict(C, state='出戰'), 2, '魯尼帖斯'), (C, 2, '布拉奇多斯'),
           (dict(C, img_species='布拉奇多斯'), 2, '魯尼帖斯'), (dict(C, mountlike=True), 2, '魯尼帖斯'))))
check('unreadable_learn_reason：--confirm-growth 跟 OCR 矛盾 / OCR 有別的完整字串 / 縮圖別種 / 格式錯 → 72',
      all(pet.unreadable_learn_reason(c, 2, '魯尼帖斯', g)[0] == pet.EXIT_NAME for c, g in
          ((C, '41/9/6/5'), (dict(C, ocr=['40/9/6/5', '41/9/6/5']), '40/9/6/5'), (dict(C, img_species='貝魯卡'), '40/9/6/5'), (C, '40/9/6'))))
check('count_cards', pet.count_cards([{'species': 'a'}, {'species': 'a'}, {'species': None}]) == {'a': 2, None: 1})
_svc = (pet.img_ident, pet.species_reg)
pet.species_reg = lambda ctx: {'growth': {'40/9/6/5': '魯尼帖斯', '43/9/6/6': '貝魯卡'}}
_IMG = {'v': '魯尼帖斯'}
pet.img_ident = lambda kind, k, ctx, text=(): {'img_species': _IMG['v'], 'img_occluded': False}
try:
    check('card_ident（縮圖為主）：沒文字 → 縮圖；名字 / 登錄與縮圖一致 → img+name / img+reg；候選字串登錄成別種 → 衝突',
          pet.card_ident(0, {'name': None, 'growth': None}, {})['src'] == 'img'
          and pet.card_ident(0, {'name': None, 'growth': '40/9/6/5'}, {})['src'] == 'img+reg'
          and pet.card_ident(0, {'name': None, 'growth': None, 'guess': '43/9/6/6'}, {})['src'] == 'conflict')
    check('card_ident：名字為主（2026-10-14 晚）→ 名字讀到朵拉比斯就採用（縮圖說魯尼帖斯也不比）；登錄物種與縮圖不同 → 衝突（species None）',
          pet.card_ident(0, {'name': '朵拉比斯'}, {})['species'] == '朵拉比斯' and pet.card_ident(0, {'name': '朵拉比斯'}, {})['src'] == 'name'
          and pet.card_ident(0, {'name': None, 'growth': '43/9/6/6'}, {})['src'] == 'conflict')
    pet.NAME_FIRST = False
    check('card_ident --img-first（舊：縮圖為主）：名字與縮圖不同 → 衝突', pet.card_ident(0, {'name': '朵拉比斯'}, {})['species'] is None)
    pet.NAME_FIRST = True
    _IMG['v'] = None
    check('card_ident：縮圖沒把握 → 舊規則（名字 → 名字；成長字串登錄 → 登錄）',
          pet.card_ident(0, {'name': '朵拉比斯'}, {})['species'] == '朵拉比斯' and pet.card_ident(0, {'name': None, 'growth': '43/9/6/6'}, {})['species'] == '貝魯卡')
finally:
    pet.img_ident, pet.species_reg = _svc

# ---- 2026-10-14 續：倉庫分頁讀成 ['姍/9/6/5','姍/9/6/5','姍/9/6','40/9/6','40/9/6/5'] → store 75；身分確認共用 ----
D = ['姍/9/6/5', '姍/9/6/5', '姍/9/6', '40/9/6', '40/9/6/5']
check('parse_growth：倉庫分頁實機 5 行（尾欄被切掉的「姍/9/6」）→ 40/9/6/5', petmatch.parse_growth(D) == '40/9/6/5')
check('growth_compatible：殘行對齊完整字串任一段連續欄', petmatch.growth_compatible('姍/9/6', '40/9/6/5') and petmatch.growth_compatible('9/6/5', '40/9/6/5')
      and not petmatch.growth_compatible('姍/9/5', '40/9/6/5'))
check('growth_consistent：全部行不矛盾才 True；有別的完整字串 / 空 → False', petmatch.growth_consistent(['姍/9/6/5', '姍/9/6'], '40/9/6/5')
      and not petmatch.growth_consistent(['姍/9/6/5', '41/9/6/5'], '40/9/6/5') and not petmatch.growth_consistent([], '40/9/6/5')
      and not petmatch.growth_consistent(['姍/8/6'], '40/9/6/5'))
RG = {'growth': {'40/9/6/5': '魯尼帖斯', '51/9/8/1': '布拉奇多斯'}}
check('candidate_species：登錄 + 縮圖一致才給；縮圖不同 / 沒登錄 / 騎寵 / OCR 矛盾 → None',
      pet.candidate_species(['姍/9/6/5'], ['40/9/6/5'], '魯尼帖斯', RG) == '魯尼帖斯' and pet.candidate_species(['姍/9/6/5'], ['40/9/6/5'], None, RG) is None
      and pet.candidate_species(['姍/9/6/5'], ['41/9/6/5'], '魯尼帖斯', RG) is None and pet.candidate_species(['51/9/8/1'], ['51/9/8/1'], '布拉奇多斯', RG) is None
      and pet.candidate_species(['姍/8/6/5'], ['40/9/6/5'], '魯尼帖斯', RG) is None)
_svi = (pet.img_ident, pet.species_reg)
_img = {'v': '魯尼帖斯', 'n': 0}
pet.species_reg = lambda ctx: RG
pet.img_ident = lambda kind, k, ctx, text=(): (_img.__setitem__('n', _img['n'] + 1), {'img_species': _img['v']})[1]
try:
    SL = {'slot': 2, 'unnamed': '40/9/6/5', 'species': '魯尼帖斯'}
    bad = {'name': None, 'growth': None, 'raw': ['姍/9/6/5', '姍/9/6/5', '姍/9/6']}
    check('ident_confirms：讀得出成長字串 → 直接比（不讀縮圖）', pet.ident_confirms({'name': None, 'growth': '40/9/6/5'}, SL, 'slot', 1, {}) and _img['n'] == 0)
    check('ident_confirms：讀不出 → 字串跟 OCR 不矛盾 + 登錄 + 縮圖一致 → True', pet.ident_confirms(bad, SL, 'slot', 1, {}))
    _img['v'] = '貝魯卡'
    check('ident_confirms：縮圖不同 → False', not pet.ident_confirms(bad, SL, 'slot', 1, {}))
    _img['v'] = '魯尼帖斯'
    check('ident_confirms：sl 字串沒登錄 / 現場候選字串不同 / sl 沒物種 / 讀到別的成長字串 → False',
          not pet.ident_confirms(bad, dict(SL, unnamed='39/9/6/5'), 'slot', 1, {}) and not pet.ident_confirms(dict(bad, guess='41/9/6/5'), SL, 'slot', 1, {})
          and not pet.ident_confirms(bad, dict(SL, species=None), 'slot', 1, {}) and not pet.ident_confirms({'name': None, 'growth': '41/9/6/5'}, SL, 'slot', 1, {}))
    _img['n'] = 0
    check('unreadable_species：候選都沒登錄 → 不讀縮圖', pet.unreadable_species({'name': None, 'growth': None, 'raw': ['姍/1/1/1'], 'guess': '9/1/1/1'}, 'card', 0, {}) is None and _img['n'] == 0)
    check('unreadable_target：名字目標（靠 guess）/ 成長字串目標都可；字串目標跟 OCR 矛盾 → False；只給等級 → False',
          pet.unreadable_target(dict(bad, guess='40/9/6/5'), 'card', 0, {'name': '魯尼帖斯'}, {})
          and pet.unreadable_target(bad, 'card', 0, {'name': None, 'growth': '40/9/6/5'}, {})
          and not pet.unreadable_target(dict(bad, guess='40/9/6/5'), 'card', 0, {'name': '貝魯卡'}, {}) and not pet.unreadable_target(bad, 'card', 0, {'name': '魯尼帖斯'}, {})
          and not pet.unreadable_target({'name': None, 'growth': None, 'raw': ['姍/8/6']}, 'card', 0, {'growth': '40/9/6/5'}, {})
          and not pet.unreadable_target(bad, 'card', 0, {'level': 1}, {}))
    check('card_ident：讀不出 + 候選登錄 + 縮圖一致 → reg+img', pet.card_ident(0, dict(bad, guess='40/9/6/5'), {})['src'] == 'reg+img')
finally:
    pet.img_ident, pet.species_reg = _svi

# ---- 2026-10-14 續 2：取出後名字框讀成「65」（Monster 表有「65」這列、還被學成名字樣板）；新抓的 40/9/5/6 讀成「姍/9/5/6」「姍/5/'6」----
check('is_name_fragment：數字 / 斜線片段不是名字', uikit.is_name_fragment('65') and uikit.is_name_fragment('姍/9/5/6') and uikit.is_name_fragment('43/9/6/5')
      and not uikit.is_name_fragment('朵拉比斯') and not uikit.is_name_fragment('2D貝魯卡') and not uikit.is_name_fragment(''))
check('snap_pet / pet_names：「65」「64」不當寵物名', uikit.snap_pet('65') is None and uikit.snap_pet('姍/9/5/6') is None and '65' not in uikit.pet_names()
      and uikit.snap_pet('朵拉比斯') == '朵拉比斯')
_t = {'name': {'65': ['ff'], '朵拉比斯': ['ff']}}
check('prune_names：清掉片段標籤、留正常名字', petmatch.prune_names(_t) == ['65'] and list(_t['name']) == ['朵拉比斯'])
_rows = ['1111111111'] * 6
_t = {'name': {}}
check('learn_whole：片段標籤不學；match_whole：片段標籤（舊污染）不比', not petmatch.learn_whole('name', '65', _rows, _t) and _t['name'] == {}
      and petmatch.match_whole('name', _rows, {'name': {'65': [format(petmatch.pack(_rows), 'x')]}})[0] is None)
L2 = ['姍/9/5/6', '40/9/5/6', "姍/5/'6", '姍/9/5/6']               # 實機 DKBO2 第 2 格（含 5,6 倍加讀那行）
check('parse_growth：雜點標點（姍/5/\'6）正規化後 → 40/9/5/6', petmatch.parse_growth(L2) == '40/9/5/6' and petmatch.growth_norm("姍/5/'6") == '姍/5/6')
_sv3 = (pet._petwatch, petmatch.match_whole, petmatch.ink)
petmatch.match_whole = lambda *a, **k: (None, 0.0, None)
petmatch.ink = lambda rows: 999
try:
    _pw2 = _PW([['姍/9/5/6', '40/9/5/6', "姍/5/'6"], [], ['姍/9/5/6']])
    pet._petwatch = lambda: _pw2
    r = pet.resolve_ident(['2' * 5], pet.load_ctx(False))
    check('resolve_ident：實機 40/9/5/6 的 OCR → growth（register 用同一條路）', r['growth'] == '40/9/5/6' and r['name'] is None, str(r))
    _pw3 = _PW([['65'], ['65'], []])
    pet._petwatch = lambda: _pw3
    r = pet.resolve_ident(['3' * 5], pet.load_ctx(False))
    check('resolve_ident：名字框只讀到「65」→ 名字 None（不當名字比對）', r['name'] is None and r['growth'] is None, str(r))
finally:
    pet._petwatch, petmatch.match_whole, petmatch.ink = _sv3
_svi = (pet.img_ident, pet.species_reg)
pet.species_reg = lambda ctx: {'growth': {'43/9/6/5': '魯尼帖斯'}}
pet.img_ident = lambda kind, k, ctx, text=(): {'img_species': '魯尼帖斯'}
try:
    after = {'name': None, 'growth': None, 'raw': ['43/9/6', '姍/9/6/5']}       # 取後讀不完整
    check('take 取後：目標只給物種名 → 用取前卡片的成長字串當候選（登錄 + 縮圖一致才過）',
          pet.unreadable_target(after, 'slot', 1, {'name': '魯尼帖斯', 'growth': '43/9/6/5'}, {})
          and not pet.unreadable_target(after, 'slot', 1, {'name': '魯尼帖斯'}, {})
          and not pet.unreadable_target({'name': None, 'growth': None, 'raw': ['65']}, 'slot', 1, {'name': '魯尼帖斯', 'growth': '43/9/6/5'}, {}))
finally:
    pet.img_ident, pet.species_reg = _svi
import rebirth_pets as _rp  # noqa: E402
check('rebirth_pets.pick_row：下拉「姍/9/5/6」用同一套容錯認成 40/9/5/6；同角色別隻也像 → 歧義不選',
      _rp.pick_row([('姍/9/5/6', 10, 100)], ('growth', '40/9/5/6'))[0] is not None
      and _rp.pick_row([('姍/9/5/6', 10, 100)], ('growth', '40/9/5/6', ['41/9/5/6']))[0] is None
      and _rp.parse_growth_line("40/9/5/'6") == '40/9/5/6')

# ---- 2026-10-14 登錄檔 v2：成長字串可對多個物種（卡坦 distribute1 rc 76：50/10/6/3 加格 / 邦恩吉同字串、49/10/6/3 後登覆蓋前登）----
import json as _json  # noqa: E402
_d2 = Path(tempfile.mkdtemp())
petmatch.TPL_DIR = _d2
(_d2 / 'species.json').write_text(_json.dumps({'thumb': {}, 'growth': {'49/10/6/3': '克邦凱斯', '47/11/5/3': '加格'}}, ensure_ascii=False), encoding='utf-8')
r2 = petmatch.load_species()
check('舊格式 species.json 讀檔自動遷移（src legacy）、growth 推導不變',
      r2['growth'] == {'49/10/6/3': '克邦凱斯', '47/11/5/3': '加格'} and r2['growth_src']['49/10/6/3'] == [{'species': '克邦凱斯', 'src': 'legacy'}])
petmatch.learn_species(r2, '邦恩吉', None, '49/10/6/3')
petmatch.learn_species(r2, '克邦凱斯', None, '49/10/6/3')
check('learn_species 撞號：兩種都記著、不互蓋（舊版刪掉後又被另一種登回去）；唯一對照拿掉',
      petmatch.growth_species(r2, '49/10/6/3') == ['克邦凱斯', '邦恩吉'] and '49/10/6/3' not in r2['growth'])
petmatch.growth_add(r2, '50/10/6/3', '加格', catcher='DKBO4', score=0.91)
petmatch.save_species(r2)
raw = _json.loads((_d2 / 'species.json').read_text(encoding='utf-8'))
r3 = petmatch.load_species()
check('存檔寫 v2（ver 2 + growth_src 附抓寵者 / 分數）、重讀一致',
      raw['ver'] == 2 and raw['growth_src']['50/10/6/3'][0]['catcher'] == 'DKBO4' and raw['growth_src']['50/10/6/3'][0]['score'] == 0.91
      and petmatch.growth_species(r3, '49/10/6/3') == ['克邦凱斯', '邦恩吉'] and r3['growth'] == {'47/11/5/3': '加格', '50/10/6/3': '加格'})
check('identify_species 撞號：沒縮圖 → None；縮圖不在候選 → None',
      petmatch.identify_species(None, '49/10/6/3', r3) is None and petmatch.identify_species(None, '47/11/5/3', r3) == '加格')
check('candidate_species 撞號：縮圖（有把握）在候選裡才給，沒把握 None',
      pet.candidate_species(None, ['49/10/6/3'], '邦恩吉', r3) == '邦恩吉' and pet.candidate_species(None, ['49/10/6/3'], None, r3) is None
      and pet.candidate_species(None, ['49/10/6/3'], '加格', r3) is None)
_sv = pet.img_ident
_seen_only = []


def _fake_img(kind, idx, ctx, sp=None):
    _seen_only.append(list(ctx.get('img_only') or []))
    return {'img_species': sp, 'img_score': 0.94}


ctx2 = {'reg': r3, 'img_only': ['克邦凱斯', '加克拉', '加格', '邦恩吉']}
pet.img_ident = lambda kind, idx, ctx, text=(): _fake_img(kind, idx, ctx, None)
check('ident_species 撞號（49/10/6/3 克邦凱斯 / 邦恩吉）縮圖沒把握 → None（不准存取）', pet.ident_species(1, '49/10/6/3', ctx2) is None and _seen_only[-1] == ['克邦凱斯', '邦恩吉'])
pet.img_ident = lambda kind, idx, ctx, text=(): _fake_img(kind, idx, ctx, '邦恩吉')
check('ident_species 撞號：只在撞號的物種之間比縮圖、有把握 → 該物種', pet.ident_species(1, '49/10/6/3', ctx2) == '邦恩吉')
pet.img_ident = lambda kind, idx, ctx, text=(): _fake_img(kind, idx, ctx, '邦恩吉')
check('ident_species 唯一字串：縮圖相同 → 採用；縮圖有把握但不在字串候選 → None',
      pet.ident_species(1, '47/11/5/3', dict(ctx2)) is None and pet.ident_species(1, '9/9/9/9', dict(ctx2)) == '邦恩吉')
check('img_target 撞號：目標在候選且縮圖認成目標才 True', pet.img_target('card', 0, {'growth': '49/10/6/3'}, {'name': '邦恩吉'}, ctx2)
      and not pet.img_target('card', 0, {'growth': '49/10/6/3'}, {'name': '克邦凱斯'}, ctx2)
      and not pet.img_target('card', 0, {'growth': '49/10/6/3'}, {'name': '加格'}, ctx2))
pet.img_ident = _sv

# errlog #810：唯一字串（v2 前互蓋留下的錯單值）對上目標、但縮圖有把握是別種 → 跳過那張，取縮圖也對的那張
_d3 = Path(tempfile.mkdtemp())
petmatch.TPL_DIR = _d3
petmatch.save_species({'thumb': {}, 'growth': {'49/10/6/3': '加克拉', '46/10/5/4': '加克拉'}})
_pub = {'DKBO': {'public': [{'name': '加克拉', 'unnamed': '49/10/6/3', 'level': 1}, {'name': '加克拉', 'unnamed': '46/10/5/4', 'level': 1}]}}
g = new(pets=mk_pets(DKBO=[{'name': '瑪斯貝卡', 'state': '騎乘', 'level': 1}, None, None, None, None]), depot=fake_pet.mk_depot(**_pub))
pet.img_ident = lambda kind, idx, ctx, text=(): {'img_species': '邦恩吉' if (kind, idx) == ('card', 0) else '加克拉', 'img_score': 0.9}
rc, out, err = run(pet.take, 'DKBO', 'public', None, None, False, True, '加克拉')
pet.img_ident = _sv
check('#810：字串登錄成加克拉但縮圖有把握是邦恩吉 → 跳過第 1 張、取第 2 張（46/10/5/4）', rc == 0 and g.pets['DKBO'][1].get('unnamed') == '46/10/5/4', f'rc={rc} {err[-300:]}')

# ---- 2026-10-14 卡坦 register 漏登：選格後名字框還是上一格的字（殘影）→ list_role 重讀 ----
check('stale_suspect：跟上一格點陣相同才懷疑；上一格空 / 沒 nh 不懷疑',
      pet.stale_suspect({'nh': 'a'}, {'nh': 'a'}) and not pet.stale_suspect({'nh': 'a'}, {'nh': 'b'})
      and not pet.stale_suspect(None, {'nh': 'a'}) and not pet.stale_suspect({'nh': None}, {'nh': None}))


def _list_with(reads):
    """假 select_role / scan_frames / select_slot / read_slot：reads[格] = 依序讀到的 nh（第一次可能是殘影）"""
    sv = (pet.select_role, pet.scan_frames, pet.select_slot, pet.read_slot, uikit.sleep, uikit.mark)
    cnt = {}

    def rs(i, ctx):
        k = cnt.get(i, 0)
        cnt[i] = k + 1
        seq = reads[i]
        return {'slot': i + 1, 'empty': False, 'nh': seq[min(k, len(seq) - 1)]}
    pet.select_role = lambda role, ctx: 0
    pet.scan_frames = lambda: {'empty': [False] * len(reads) + [True] * (5 - len(reads)), 'sel': [False] * 5}
    pet.select_slot = lambda i, f: 0
    pet.read_slot = rs
    uikit.sleep = lambda s: None
    uikit.mark = lambda *a, **k: None
    try:
        return pet.list_role('DKBO2', {}), cnt
    finally:
        pet.select_role, pet.scan_frames, pet.select_slot, pet.read_slot, uikit.sleep, uikit.mark = sv


(rc, sl), cnt = _list_with([['m'], ['p'], ['p', 'q']])
check('list_role：第 3 格第一次讀到第 2 格殘影 → 重讀拿到自己的', rc == 0 and [s['nh'] for s in sl[:3]] == ['m', 'p', 'q'] and cnt[2] == 2 and sl[2].get('stale_retry'), str(sl))
(rc, sl), cnt = _list_with([['m'], ['z'], ['z']])
check('list_role：真的同字串（重讀仍相同）→ 照收、最多重讀 STALE_RETRIES 次', rc == 0 and sl[2]['nh'] == 'z' and cnt[2] == 1 + pet.STALE_RETRIES)

print(f'\n{fails} 項失敗' if fails else '\n全部通過')
sys.exit(1 if fails else 0)
