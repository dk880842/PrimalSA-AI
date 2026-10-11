#!/usr/bin/env python3
"""pet.py（list / set-state / rest-all）+ petmatch 離線測試：不碰遊戲，假 gui 依設定畫寵物面板（fake_pet.Game）。
用法：uv run --no-project python tools/gui/test_pet.py"""
import contextlib
import io
import json
import sys
import tempfile
import types
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import errlog  # noqa: E402
import fake_pet  # noqa: E402
import heal  # noqa: E402
import petmatch  # noqa: E402
import uikit  # noqa: E402
from fake_pet import Game, install, mk_pets  # noqa: E402
import pet  # noqa: E402

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
rc, out, err = run(pet.take, 'DKBO', 'personal', 5, None)
check('take 空格 → 72、取出鈕 0 次', rc == 72 and depot_free(g) == 0, f'rc={rc}')
fresh_tpl()
g = new(pets=mk_pets(DKBO=[{'name': '瑪斯貝卡', 'state': '騎乘', 'level': 128}, {'name': '迪基格斯', 'state': '出戰', 'level': 130}, {'name': '魯尼帖斯', 'state': '等待', 'level': 20}, {'name': '魯尼帖斯', 'state': '等待', 'level': 20}, {'name': '魯尼帖斯', 'state': '等待', 'level': 20}]))
rc, out, err = run(pet.take, 'DKBO', 'personal', 1, None)
check('寵物欄滿 → 77、倉庫分頁都不開', rc == 77 and not g.depot_clicks and depot_free(g) == 0, f'rc={rc}')
fresh_tpl()
g = new()
g.btn_ocr_override = ['存入寵物']
rc, out, err = run(pet.take, 'DKBO', 'personal', 1, None)
check('take：按鈕文字不是「取出寵物」→ 75、0 次', rc == 75 and depot_free(g) == 0, f'rc={rc}')
fresh_tpl()
g = new()
g.store_dead = True
rc, out, err = run(pet.take, 'DKBO', 'personal', 1, None)
check('取出鈕沒反應 → 76，只點 1 次', rc == 76 and depot_free(g) == 1, f'rc={rc}')
fresh_tpl()
g = new()
g.confirm_on_take = True
rc, out, err = run(pet.take, 'DKBO', 'personal', 1, None)
check('take 遇到未預期的提示視窗 → 點取消（不點確定）、76、取出鈕只點 1 次', rc == 76 and g.dialog_clicks == [pet.CONFIRM_CANCEL_XY] and depot_free(g) == 1, f'rc={rc} {g.dialog_clicks}')
for bad_idx in (0, 21):
    g = new()
    rc, out, err = run(pet.take, 'DKBO', 'personal', bad_idx, None)
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


print(f'\n{fails} 項失敗' if fails else '\n全部通過')
sys.exit(1 if fails else 0)
