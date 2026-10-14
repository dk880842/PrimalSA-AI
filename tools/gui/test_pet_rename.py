#!/usr/bin/env python3
"""pet.py 還原名字（reset-name / store 前還原 / depot-fix-names）+ 名字為主 離線測試：不碰遊戲，假寵物面板 fake_pet.Game 加「修改名字」視窗。
用法：uv run --no-project python tools/gui/test_pet_rename.py
驗：鉛筆 → 固定等 1 秒 → 確認（視窗特徵守門）→ 視為成功；按確認後跳提示 / 視窗沒關才讀字：費用字樣 67（按取消、停手）、其他失敗 66；
鉛筆鈕在 PET 禁區只有 allow 才點；store 前成長字串先還原（--no-rename 關）；倉庫成長字串卡取出 → 還原 → 存回原倉庫、寵物欄滿跳過；
名字為主：名字框讀到物種名就不跑縮圖（寵物格 / 倉庫卡），名字讀不出才用縮圖。"""
import contextlib
import io
import json
import sys
import tempfile
import types
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import testenv  # noqa: E402,F401  紀錄檔轉向暫存
import errlog  # noqa: E402
import fake_pet  # noqa: E402
import petmatch  # noqa: E402
import uikit  # noqa: E402
from fake_pet import Game, install, mk_pets, mk_depot  # noqa: E402
import pet  # noqa: E402
import winenv  # noqa: E402
winenv.long_args_ok = lambda script='gui.ps1': True

errlog.LOG = Path(tempfile.mkdtemp()) / 'errlog.jsonl'
sys.modules['grind'] = types.SimpleNamespace(_other_running=lambda: None)
fails = 0
BRA = '布拉奇多斯'
GS = ['49/9/8/2', '51/9/8/1', '48/10/7/2', '49/9/7/1', '49/10/8/1']


def check(name, cond, extra=''):
    global fails
    print(('PASS' if cond else 'FAIL'), name, extra)
    if not cond:
        fails += 1


def fresh_tpl():
    petmatch.TPL_DIR = Path(tempfile.mkdtemp())


def new(**kw):
    g = install(Game(**kw))
    pet.RENAME_ON = True
    return g


def run(fn, *a, **k):
    buf, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(err):
        rc = fn(*a, **k)
    return rc, buf.getvalue(), err.getvalue()


def last_json(out):
    return json.loads(out.strip().splitlines()[-1])


def unn(i, state='騎乘', name=BRA):
    return {'name': name, 'unnamed': GS[i], 'species': name, 'state': state, 'level': 1}


def five(state='騎乘'):
    """5 人：第 1 格沒名字的布拉奇多斯（成長字串各不同）、第 2 格朵拉比斯（有名字）"""
    return mk_pets(**{r: [unn(i, state), {'name': '朵拉比斯', 'state': '出戰', 'level': 1}, None, None, None] for i, r in enumerate(fake_pet.ROLES)})


def pencil(g):
    return [c for c in g.clicks if c == pet.PENCIL_XY]


# ---------------- 純函式 / 常數
check('退出碼 66 / 67', (pet.EXIT_RENAME, pet.EXIT_FEE) == (66, 67))
check('fee_words：鑽石 / 石幣 / 費用 讀得到、確認 / 修改名字 不算', pet.fee_words(['修改名字', '需要花費 100 鑽石']) == ['花費', '鑽', '鑽石']
      and pet.fee_words(['扣除石幣 3000']) == ['扣除', '石幣'] and pet.fee_words(['修改名字', '確詔', '取消']) == [])
todo, skip = pet.rename_targets([{'slot': 1, 'unnamed': '1/2/3/4'}, {'slot': 2, 'name': '朵拉比斯'}, {'slot': 3, 'unreadable': True, 'guess': '4/3/2/1'},
                                 {'slot': 4, 'unreadable': True}, {'slot': 5, 'empty': True}])
check('rename_targets：成長字串 / 像成長字串的讀不出 → 要還原；有名字不動；讀不出也不像 → 略過', [x['slot'] for x in todo] == [1, 3] and [x['slot'] for x, _ in skip] == [4])
check('rename_targets --slot 3 只挑第 3 格', [x['slot'] for x in pet.rename_targets([{'slot': 1, 'unnamed': 'a'}, {'slot': 3, 'unnamed': 'b'}], 3)[0]] == [3])
check('鉛筆鈕在 PET 禁區 rename（人物面板改名鈕另在 exp.ROLEINFO 禁區）', uikit.in_rect(*pet.PENCIL_XY, uikit.PET.forbidden['rename']))
try:
    uikit.check_forbidden(uikit.PET, *pet.PENCIL_XY)
    ok = False
except uikit.ForbiddenClick:
    ok = True
check('沒給 allow 點鉛筆 → ForbiddenClick；allow=(rename,) 才放行', ok and uikit.check_forbidden(uikit.PET, *pet.PENCIL_XY, allow=('rename',)) is None)
import exp  # noqa: E402
check('人物面板改名鈕 573,180 仍是紅區', any(uikit.in_rect(573, 180, r) for r in exp.ROLEINFO.forbidden.values()))
check('改名視窗按鈕都不在 PET 禁區外的危險位置：確認 / 取消不跟垃圾桶 / 回爐重疊', not any(uikit.in_rect(*xy, uikit.PET.forbidden[k]) for xy in (pet.RENAME_OK_XY, pet.RENAME_CANCEL_XY)
                                                                         for k in ('trash', 'recycle', 'lock')))

# ---------------- reset-name happy：5 人第 1 格（騎寵、騎乘中）還原名字
fresh_tpl()
g = new(pets=five())
rc, out, err = run(pet.reset_names, 'all')
j = last_json(out)
check('reset-name all：rc 0、5 人第 1 格都還原成布拉奇多斯、沒有成長字串', rc == 0 and all(g.pets[r][0]['name'] == BRA and 'unnamed' not in g.pets[r][0] for r in fake_pet.ROLES),
      f'rc={rc} {err[-300:]}')
check('  每人只點 1 次鉛筆 + 1 次確認、0 次取消、0 次狀態鈕、騎乘狀態不變', len(pencil(g)) == 5 and g.rename_clicks.count(pet.RENAME_OK_XY) == 5
      and pet.RENAME_CANCEL_XY not in g.rename_clicks and g.state_clicks == [] and all(g.pets[r][0]['state'] == '騎乘' for r in fake_pet.ROLES))
check('  ops 每人 rename_from = 成長字串（不再填 new_name）', [o.get('new_name') for o in j['ops']] == [None] * 5 and [o.get('rename_from') for o in j['ops']] == GS)
rc, out, err = run(pet.reset_names, 'all')
check('再跑一次：沒有成長字串 → 不點鉛筆、rc 0', rc == 0 and len(pencil(g)) == 5)
rc, out, err = run(pet.list_roles, 'DKBO3')
j = last_json(out)['roles']['DKBO3']
check('還原後 list：名字 = 布拉奇多斯、species_src name（名字為主）', j[0]['name'] == BRA and j[0].get('species_src') == 'name' and not j[0].get('unnamed'), str(j[0]))

g = new(pets=five())
rc, out, err = run(pet.reset_names, 'DKBO2,DKBO4', dry_run=True)
check('--dry-run：只列 2 人、零鉛筆點擊', rc == 0 and pencil(g) == [] and [o['role'] for o in last_json(out)['ops']] == ['DKBO2', 'DKBO4'])
rc, out, err = run(pet.reset_names, 'DKBO2', slot_no=2)
check('--slot 2（有名字的朵拉比斯）→ 沒有要還原的、零鉛筆', rc == 0 and pencil(g) == [])

# ---------------- 失敗：費用字樣 / 輸入框不空 / 視窗沒出現 / 確認後跳提示 / 名字不是物種名
g = new(pets=five())
g.rename_dead = True
rc, out, err = run(pet.reset_names, 'DKBO')
check('點鉛筆沒出現視窗 → 66、只點 1 次鉛筆', rc == 66 and len(pencil(g)) == 1, f'rc={rc}')
g = new(pets=five())
g.rename_after_popup = ['改名需要消耗 50,000 石幣，確定嗎?']
rc, out, err = run(pet.reset_names, 'DKBO')
check('按確認後跳提示有「石幣」→ 67、提示按取消（813,557）', rc == 67 and pet.CONFIRM_CANCEL_XY in g.dialog_clicks and pet.CONFIRM_OK_XY not in g.dialog_clicks
      and not g.dialog, f'rc={rc} {g.dialog_clicks}')
g = new(pets=five())
g.rename_after_popup = ['名字不能為空']
rc, out, err = run(pet.reset_names, 'DKBO')
check('按確認後跳提示沒有費用字樣 → 66、按取消', rc == 66 and pet.CONFIRM_CANCEL_XY in g.dialog_clicks, f'rc={rc}')
g = new(pets=five())
g.rename_keep = True
rc, out, err = run(pet.reset_names, 'DKBO')
check('確認後視窗不關 → 66、按取消', rc == 66 and pet.RENAME_CANCEL_XY in g.rename_clicks and not g.rename, f'rc={rc}')

# ---------------- 時機一：store 前還原名字
fresh_tpl()
pets3 = mk_pets(DKBO=[{'name': '瑪斯貝卡', 'state': '騎乘', 'level': 1}, {'name': '朵拉比斯', 'state': '出戰', 'level': 1},
                      {'name': '魯尼帖斯', 'unnamed': '40/9/6/5', 'species': '魯尼帖斯', 'state': '等待', 'level': 1}, None, None])
g = new(pets=pets3)
rc, out, err = run(pet.learn_species_cmd, 'DKBO', 3, '魯尼帖斯', '40/9/6/5')
check('（準備）learn-species 第 3 格 40/9/6/5 = 魯尼帖斯', rc == 0, f'rc={rc} {err[-200:]}')
rc, out, err = run(pet.store, 'DKBO', '魯尼帖斯', 'public')
j = last_json(out)
card = next(c for c in g.depot['DKBO']['public'] if c)
check('store 成長字串的魯尼帖斯 → 先還原名字再存：rc 0、倉庫卡有名字沒成長字串、鉛筆 1 次', rc == 0 and card['name'] == '魯尼帖斯' and 'unnamed' not in card
      and len(pencil(g)) == 1 and 'new_name' not in j, f'rc={rc} {card} {err[-300:]}')
fresh_tpl()
g = new(pets=mk_pets(DKBO=[{'name': '瑪斯貝卡', 'state': '騎乘', 'level': 1}, {'name': '朵拉比斯', 'state': '出戰', 'level': 1},
                           {'name': '魯尼帖斯', 'unnamed': '40/9/6/5', 'species': '魯尼帖斯', 'state': '等待', 'level': 1}, None, None]))
run(pet.learn_species_cmd, 'DKBO', 3, '魯尼帖斯', '40/9/6/5')
pet.RENAME_ON = False
rc, out, err = run(pet.store, 'DKBO', '魯尼帖斯', 'public')
card = next(c for c in g.depot['DKBO']['public'] if c)
check('--no-rename：照舊存成長字串卡、零鉛筆', rc == 0 and card.get('unnamed') == '40/9/6/5' and pencil(g) == [], f'rc={rc}')
pet.RENAME_ON = True
fresh_tpl()
g = new(pets=mk_pets(DKBO=[{'name': '瑪斯貝卡', 'state': '騎乘', 'level': 1}, {'name': '朵拉比斯', 'state': '出戰', 'level': 1},
                           {'name': '魯尼帖斯', 'unnamed': '40/9/6/5', 'species': '魯尼帖斯', 'state': '等待', 'level': 1}, None, None]))
run(pet.learn_species_cmd, 'DKBO', 3, '魯尼帖斯', '40/9/6/5')
g.rename_after_popup = ['花費 1000 鑽石，確定嗎?']
rc, out, err = run(pet.store, 'DKBO', '魯尼帖斯', 'public')
check('store 前還原名字確認後跳費用提示 → 67、不存（零存入點擊）', rc == 67 and not any(g.depot['DKBO']['public']) and g.store_clicks == [], f'rc={rc}')
g = new(pets=mk_pets(DKBO=[{'name': '瑪斯貝卡', 'state': '騎乘', 'level': 1}, {'name': '朵拉比斯', 'state': '出戰', 'level': 1},
                           {'name': '魯尼帖斯', 'unnamed': '40/9/6/5', 'species': '魯尼帖斯', 'state': '等待', 'level': 1}, None, None]))
rc, out, err = run(pet.store, 'DKBO', '瑪斯貝卡', 'public')
check('store 騎寵（被擋 73）→ 不會先去改名', rc == 73 and pencil(g) == [])

# store-many --pick last：同物種 3 隻新寵物，存 2 隻進公共 → 每隻存前還原名字；take-many 以名字取回
fresh_tpl()
g = new(pets=mk_pets(DKBO=[{'name': '朵拉比斯', 'state': '出戰', 'level': 1}, unn(0, '等待'), unn(1, '等待'), unn(2, '等待'), None]))
run(pet.learn_species_cmd, 'DKBO', 2, BRA, GS[0])
rc, out, err = run(pet.store_many, 'DKBO', [BRA, BRA], 'public', False, [BRA], pick='last')
pub = [c for c in g.depot['DKBO']['public'] if c]
left = [p for p in g.pets['DKBO'] if p]
check('store-many --pick last：存的 2 隻都先還原名字（公共卡有名字）、留下的第 2 格仍是成長字串', rc == 0 and len(pub) == 2 and all(c['name'] == BRA and 'unnamed' not in c for c in pub)
      and left[1].get('unnamed') == GS[0] and len(pencil(g)) == 2, f'rc={rc} {pub} {err[-300:]}')
rc, out, err = run(pet.take_many, 'DKBO', [BRA], 'public')
check('take-many 以名字取回布拉奇多斯（不靠登錄檔 / 縮圖）', rc == 0 and g.pets['DKBO'][2] and g.pets['DKBO'][2]['name'] == BRA and 'unnamed' not in g.pets['DKBO'][2], f'rc={rc} {err[-200:]}')

# ---------------- 時機二：depot-fix-names
fresh_tpl()
U = lambda gs, nm='魯尼帖斯': {'name': nm, 'unnamed': gs, 'species': nm, 'level': 1}    # noqa: E731
dep = mk_depot(DKBO={'public': ['朵拉比斯', U('43/9/6/5'), U('41/9/6/5', '貝魯卡')], 'personal': [U('47/9/8/1', BRA), '摩娜西普']},
               DKBO2={'personal': [U('40/9/5/6')]})
g = new(pets=mk_pets(), depot=dep)
rc, out, err = run(pet.depot_fix_names, 'DKBO', ['public', 'personal'], dry_run=True)
j = last_json(out)
check('depot-fix-names --dry-run：列出公共 2 張 + DKBO 個人 1 張、零取出 / 零鉛筆', rc == 0 and len(j['todo']) == 3 and g.store_clicks == [] and pencil(g) == [],
      f'rc={rc} {j.get("todo")} {err[-200:]}')
rc, out, err = run(pet.depot_fix_names, 'DKBO,DKBO2', ['public', 'personal'])
j = last_json(out)
pub = [c for c in g.depot['DKBO']['public'] if c]
per = [c for c in g.depot['DKBO']['personal'] if c]
per2 = [c for c in g.depot['DKBO2']['personal'] if c]
check('depot-fix-names：rc 0、公共 3 張都有名字（魯尼帖斯 / 貝魯卡）、個人的布拉奇多斯有名字、張數不變',
      rc == 0 and len(pub) == 3 and all('unnamed' not in c for c in pub) and sorted(c['name'] for c in pub) == ['朵拉比斯', '貝魯卡', '魯尼帖斯']
      and len(per) == 2 and all('unnamed' not in c for c in per) and len(per2) == 1 and per2[0]['name'] == '魯尼帖斯' and 'unnamed' not in per2[0],
      f'rc={rc} {pub} {per} {per2} {err[-400:]}')
check('  fixed 4 筆（公共 2、DKBO 個人 1、DKBO2 個人 1）、寵物欄回到原樣', len(j['fixed']) == 4 and [x['depot'] for x in j['fixed']].count('public') == 2
      and all([p and p['name'] for p in g.pets[r]] == ['瑪斯貝卡', '迪基格斯', None, None, None] for r in ('DKBO', 'DKBO2')), str(j['fixed']))
check('  個人倉庫的布拉奇多斯（騎寵種，剛取出、等待中）存回個人', any(x['depot'] == 'personal' and x.get('species') == BRA or x.get('growth') == '47/9/8/1' for x in j['fixed']))
fresh_tpl()
dep = mk_depot(DKBO={'public': [U('43/9/6/5'), U('41/9/6/5', '貝魯卡')]})
g = new(pets=mk_pets(), depot=dep)
rc, out, err = run(pet.depot_fix_names, 'DKBO', ['public'], limit=1)
j = last_json(out)
check('--limit 1：只修 1 張就停（另一張仍是成長字串）', rc == 0 and len(j['fixed']) == 1 and sum(1 for c in g.depot['DKBO']['public'] if c and c.get('unnamed')) == 1, f'rc={rc} {j["fixed"]}')
# 寵物欄滿 → 跳過、列出
fresh_tpl()
full = [{'name': n, 'state': '等待', 'level': 1} for n in ('瑪斯貝卡', '迪基格斯', '朵拉比斯', '摩娜西普', '巴朵蘭恩')]
g = new(pets=mk_pets(DKBO=full), depot=mk_depot(DKBO={'public': [U('43/9/6/5')]}))
rc, out, err = run(pet.depot_fix_names, 'DKBO', ['public'])
j = last_json(out)
check('寵物欄沒空格 → rc 0、skipped 列出那張、零取出 / 零存入、不為騰位子存別的寵物', rc == 0 and len(j['skipped']) == 1 and '空格' in j['skipped'][0]['why']
      and g.store_clicks == [] and pencil(g) == [] and j['fixed'] == [], f'rc={rc} {j}')
g = new(pets=mk_pets(DKBO=full), depot=mk_depot(DKBO={'public': [U('43/9/6/5')]}))
g.depot['DKBO2']['public'] = g.depot['DKBO']['public']          # 公共倉庫大家共用（假面板預設每人一份）
rc, out, err = run(pet.depot_fix_names, 'DKBO,DKBO2', ['public'])
j = last_json(out)
check('公共倉庫：DKBO 滿 → 改用 DKBO2（有空格）修', rc == 0 and len(j['fixed']) == 1 and j['fixed'][0]['role'] == 'DKBO2'
      and g.depot['DKBO']['public'][0] and 'unnamed' not in g.depot['DKBO']['public'][0], f'rc={rc} {j} {err[-300:]}')
# 改名費用 → 停、寵物留在寵物欄
fresh_tpl()
g = new(pets=mk_pets(), depot=mk_depot(DKBO={'public': [U('43/9/6/5')]}))
g.rename_after_popup = ['消耗 10 鑽石，確定嗎?']
rc, out, err = run(pet.depot_fix_names, 'DKBO', ['public'])
j = last_json(out)
check('depot-fix-names 改名確認後跳費用提示 → 67、寵物留在寵物欄（failed 列出）', rc == 67 and g.pets['DKBO'][2] and g.pets['DKBO'][2].get('unnamed') == '43/9/6/5'
      and len(j['failed']) == 1 and '留在寵物欄' in j['failed'][0]['why'], f'rc={rc} {j}')

# ---------------- 名字為主：讀到名字不跑縮圖；名字讀不出才用縮圖
calls = []
pet.IMG_ON = True
orig_img = pet.img_ident
pet.img_ident = lambda kind, idx, ctx, text=(): calls.append((kind, idx)) or {'img_species': '奇寶', 'img_score': 0.9, 'img_kind': kind, 'img_occluded': False}
real_ri, real_grab = pet.resolve_ident, petmatch.grab


def grab(specs, extra=()):
    rows = [['0' * w] * h for _, _, w, h, _ in specs]
    return rows, [(150, 100, 50)] * 2 + [(230, 200, 150)] * 4


petmatch.grab = grab
ctx = {'tpl': {'name': {}}, 'learn': False, 'dirty': False, 'reg': {'thumb': {}, 'growth': {}}}
pet.resolve_ident = lambda rows, c: {'name': '朵拉比斯', 'via': 'tpl', 'raw': None, 'growth': None}
d = pet.read_slot(1, ctx)
check('名字為主：名字框讀到朵拉比斯 → 不跑縮圖、species_src name、沒有衝突', calls == [] and d['name'] == '朵拉比斯' and d.get('species_src') == 'name'
      and not d.get('ident_conflict') and pet.slot_ident(d) == '朵拉比斯', str(d))
pet.resolve_ident = lambda rows, c: {'name': None, 'via': 'growth', 'raw': None, 'growth': '9/9/9/9'}
d = pet.read_slot(1, ctx)
check('名字讀不出（成長字串）→ 才跑縮圖', calls == [('slot', 1)] and d.get('species') == '奇寶' and d.get('species_src') == 'img', str(d))
pet.NAME_FIRST = False
calls.clear()
pet.resolve_ident = lambda rows, c: {'name': '朵拉比斯', 'via': 'tpl', 'raw': None, 'growth': None}
d = pet.read_slot(1, ctx)
check('--img-first（NAME_FIRST 關）：讀到名字也比縮圖 → 衝突（舊行為）', calls == [('slot', 1)] and d.get('ident_conflict'), str(d.get('ident_conflict')))
pet.NAME_FIRST = True
calls.clear()
ci = pet.card_ident(0, {'name': '加格', 'growth': None}, ctx)
check('倉庫卡：名字讀到加格 → species 加格、src name、不跑縮圖', ci['species'] == '加格' and ci['src'] == 'name' and calls == [], str(ci))
ci = pet.card_ident(0, {'name': None, 'growth': '50/10/6/9'}, ctx)
check('倉庫卡：成長字串 → 才跑縮圖', calls == [('card', 0)] and ci['species'] == '奇寶', str(ci))
calls.clear()
check('img_conflict(named=True) → 不比縮圖', pet.img_conflict('card', 0, ctx, '加格', named=True) is None and calls == [])
check('img_conflict(named=False) → 照比（成長字串登錄的身分）', bool(pet.img_conflict('card', 0, ctx, '加格')) and calls == [('card', 0)])
pet.img_ident, pet.resolve_ident, petmatch.grab = orig_img, real_ri, real_grab
pet.IMG_ON = False

print('全部通過' if not fails else f'{fails} 項失敗')
sys.exit(1 if fails else 0)
