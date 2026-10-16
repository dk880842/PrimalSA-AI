#!/usr/bin/env python3
"""postrebirth.py 離線測試：完全不碰遊戲（假子程序）。用法：uv run --no-project python tools/gui/test_postrebirth.py"""
import contextlib
import io
import json
import os
import sys
import tempfile
from pathlib import Path

os.environ.setdefault('PSA_LAYOUT', '2880x1659')
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import testenv  # noqa: E402,F401  紀錄檔轉向暫存
import errlog  # noqa: E402
import postrebirth as pr  # noqa: E402

TMP = Path(tempfile.mkdtemp())
pr.PROGRESS, pr.EVENT_LOG = TMP / 'pr.json', TMP / 'ev.log'
errlog.LOG = TMP / 'errlog.jsonl'
fails = 0


def check(name, cond, extra=''):
    global fails
    print(('PASS' if cond else 'FAIL'), name, extra)
    if not cond:
        fails += 1


def bags(free, items=None):
    return {r: {'slots': {str(i): n for i, n in enumerate((items or {}).get(r, []))}, 'free': free.get(r, 14) if isinstance(free, dict) else free}
            for r in pr.ALL_ROLES}


def pets_ok_json():
    return {'roles': {r: [{'name': '布拉奇多斯', 'state': '騎乘'}, {'name': '朵拉比斯', 'state': '出戰', 'level': 125}] for r in pr.ALL_ROLES}}


class Fake:
    """rcs：{(腳本, 第一個參數): rc 或 [rc…]}；bag_lists：bag.py list 依序回傳的 bags dict"""

    def __init__(self, rcs=None, bag_lists=None, not_done=None, pets=None, not_done_ids=None, trans=1, exp_trans=None):
        self.trans, self.exp_trans = trans, exp_trans      # trans = trans.json 快取（預設 1 轉）；exp_trans = 盤點 exp.py read 回報的 5 人轉數
        self.calls, self.rcs = [], dict(rcs or {})
        self.not_done_ids = list(not_done_ids or [])
        self.bag_lists = list(bag_lists or [])
        self.not_done = not_done or {}
        self.pets = pets or pets_ok_json()

    def cached_trans(self):
        return self.trans

    def sub(self, script, args, timeout=0):
        args = [str(a) for a in args]
        self.calls.append((script, tuple(args)))
        k = (script, args[0] if args else '')
        v = self.rcs.get(k, 0)
        rc = (v.pop(0) if len(v) > 1 else v[0]) if isinstance(v, list) else v
        if script == 'bag.py' and args[0] == 'list':
            b = self.bag_lists.pop(0) if len(self.bag_lists) > 1 else (self.bag_lists[0] if self.bag_lists else bags(14))
            return rc, [json.dumps({'bags': b, 'rc': rc}, ensure_ascii=False)]
        if script == 'questrun.py' and args[0] == 'status':
            return rc, [json.dumps({'rc': rc, 'not_done': self.not_done, 'not_done_ids': self.not_done_ids}, ensure_ascii=False)]
        if script == 'exp.py' and self.exp_trans is not None:
            return rc, [json.dumps({'rc': rc, 'roles': {r: ({'trans': t} if t is not None else None) for r, t in zip(pr.ALL_ROLES, self.exp_trans)}})]
        if script == 'pet.py' and args[0] == 'list':
            return rc, [json.dumps(dict(self.pets, rc=rc), ensure_ascii=False)]
        return rc, []

    def seq(self):
        return [(s, a[0] if a else '') for s, a in self.calls]


def go(f, **kw):
    if kw.pop('reset', True):
        pr.PROGRESS.unlink(missing_ok=True)
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        return pr.run(tools=f, **kw)


# ---------------- 純函式
plan, short = pr.purge_plan(bags({'DKBO': 4, 'DKBO3': 9}, {'DKBO': ['龍之槍', '儀之兜', '大地的羈絆', '亞姆的斧頭'], 'DKBO3': ['儀之兜']}), 6, pr.PURGE1)
check('purge_plan：只刪空格 < 門檻的人；龍之X 在 → 笛子一起；亞姆的斧頭（畫面名）吻合；四大洞窟產物不在名單', short == {'DKBO': 4} and set(plan) == {'DKBO'}
      and {'龍之槍', '儀之兜', '亞姆亞姆的斧頭', pr.FLUTE} <= set(plan['DKBO']) and '大地的羈絆' not in plan['DKBO'], str(plan))
plan, _ = pr.purge_plan(bags({'DKBO2': 2}, {'DKBO2': ['龍的魅力之笛', '山賊的羽飾']}), 6, pr.PURGE1)
check('purge_plan：沒有龍之槍 / 鎧 / 衣 → 笛子不刪（ui/bag.md 條件）', plan == {'DKBO2': ['山賊的羽飾']}, str(plan))
check('group_by_names：名單相同的人一起刪、空名單略過', pr.group_by_names({'DKBO': ['a'], 'DKBO2': ['a'], 'DKBO3': [], 'DKBO4': ['b']})
      == [(['DKBO', 'DKBO2'], ['a']), (['DKBO4'], ['b'])])
check('PURGE1 含 2026-10-14 核准的 8 項', {'仙尼亞的花', '郵寄物', '切繩石', '馬祖的斧頭', '馬祖的矛', '馬祖的棍棒', '空想的帽子', '空想的豎琴'} <= set(pr.PURGE1) and not [n for n in pr.PURGE1 if __import__('bag').purge_guard(n)])
check('PURGE1 / PURGE2 含千年龜的殼（使用者 2026-10-17）', '千年龜的殼' in pr.PURGE1 and '千年龜的殼' in pr.PURGE2)
check('PURGE2 = PURGE1 + 杉的手環 / 月光的手鐲 / 巴巴洛的許可證；都不是保護名稱', set(pr.PURGE2) - set(pr.PURGE1) == {'杉的手環', '月光的手鐲', '巴巴洛的許可證'}
      and not [n for n in pr.PURGE2 if __import__('bag').purge_guard(n)])
check('pets_ok：朵拉比斯出戰 1 隻 + 騎乘', pr.pets_ok(pets_ok_json()['roles']) == {} and 'DKBO' in pr.pets_ok({'DKBO': [{'name': '朵拉比斯', 'state': '等待'}]}))
check('順序 = 使用者定案（猜謎三兄弟在卡坦之後、紅暴在 1.82 前段之前、三次清背包⓪①②）', pr.SEGMENTS == ['inventory', 'adult', 'yayoi', 'hero', 'bag0', 'q182a', 'bag1', 'q182b', 'bag2',
                                                                                 'caves', 'dino', 'katan', 'quiz', 'finish'])

# ---------------- happy path
f = Fake()
rc = go(f, confirm_drop=True)
qr = [a for s, a in f.calls if s == 'questrun.py' and a[0] == 'run']
check('happy：rc 0、14 段全跑', rc == 0 and pr.LAST['ran'] == pr.SEGMENTS, f'rc={rc} {pr.LAST}')
check('questrun 每段 --after none；成人儀式 / 1.82 / 洞窟帶 --dragon；紅暴帶丟寵 / 丟首飾旗標', all('--after' in a and a[a.index('--after') + 1] == 'none' for a in qr)
      and all('--dragon' in a for a in qr if a[1] in ('2999', '2015', '2025', '2000')) and '--drop-items' in qr[2] and '巴朵蘭恩' in qr[2], str(qr))
check('1.82 前段 / 後段 / 洞窟的任務順序', qr[3][1:9] == tuple(map(str, pr.Q182A)) and qr[4][1:7] == tuple(map(str, pr.Q182B))
      and qr[5][1:5] == ('2000', '2003', '2001', '2002') and '--max-min' in qr[5])
pq = [a for s, a in f.calls if s == 'petquest.py']
check('寵物任務 恐龍 → 卡坦 → 猜謎，帶 --confirm-drop', [a[1] for a in pq] == ['2016', '2019', '3003'] and all('--confirm-drop' in a for a in pq))
check('收尾：status --role all 全部任務 → pet list → grind start 去練功（不帶 --spot，最後一步）', f.calls[-1] == ('grind.py', ('start',))
      and any(s == 'questrun.py' and a[0] == 'status' and '2031' in a for s, a in f.calls))
f2 = Fake()
go(f2, from_seg='finish', spot='波拉島')
check('收尾 --spot 波拉島 → grind start --spot 波拉島（固定點）', f2.calls[-1] == ('grind.py', ('start', '--spot', '波拉島')), str(f2.calls[-1:]))
check('空格都夠 → 清背包不刪（沒有 purge）', not [a for s, a in f.calls if s == 'bag.py' and a[0] == 'purge'])
check('全部完成後進度清空', json.loads(pr.PROGRESS.read_text(encoding='utf-8'))['done'] == [])

# ---------------- 清背包
f = Fake(bag_lists=[bags({'DKBO': 3}, {'DKBO': ['儀之兜', '山賊的羽飾', '龍之鎧']}), bags(14)])
rc = go(f, confirm_drop=True, from_seg='bag1', to_seg='bag1')
pu = [a for s, a in f.calls if s == 'bag.py' and a[0] == 'purge']
check('清背包①：DKBO 空 3 < 6 → 先 --dry-run 再實刪（只刪 DKBO、白名單 + 笛子）→ 重讀 OK', rc == 0 and len(pu) == 3 and pu[0][-1] == '--dry-run'
      and all(x[1] == 'DKBO' and '--dry-run' not in x for x in pu[1:]) and '龍的魅力之笛' in ','.join(x[3] for x in pu[1:]), f'rc={rc} {pu}')
f = Fake(bag_lists=[bags({'DKBO': 3}, {'DKBO': ['儀之兜']})])
rc = go(f, from_seg='bag1', to_seg='bag1')
pu = [a for s, a in f.calls if s == 'bag.py' and a[0] == 'purge']
check('沒 --confirm-drop → 只 --dry-run、174 停並印 purge 指令', rc == pr.EXIT_BAG and len(pu) == 1 and pu[0][-1] == '--dry-run' and 'purge DKBO' in pr.LAST['info']['manual'])
f = Fake(bag_lists=[bags({'DKBO': 3}, {'DKBO': ['儀之兜']}), bags({'DKBO': 4}, {'DKBO': ['某種沒核准的道具']})])
rc = go(f, confirm_drop=True, from_seg='bag2', to_seg='bag2')
check('刪完白名單仍不足 → 174（名單外不刪）', rc == pr.EXIT_BAG and '仍有人空格' in pr.LAST['info']['msg'])

f = Fake(bag_lists=[bags({'DKBO': 4}, {'DKBO': ['儀之兜']}), bags(14)])
rc = go(f, confirm_drop=True, from_seg='bag0', to_seg='bag0')
pu = [a for s, a in f.calls if s == 'bag.py' and a[0] == 'purge']
check('清背包⓪：空 4 < 5 → 刪；NEED0 = 5', rc == 0 and pr.NEED0 == 5 and len(pu) == 2 and pu[0][-1] == '--dry-run', f'rc={rc} {pu}')
f = Fake(bag_lists=[bags({'DKBO': 5}, {'DKBO': ['儀之兜']})])
rc = go(f, from_seg='bag0', to_seg='bag0')
check('清背包⓪：空 5 ≥ 5 → 不刪', rc == 0 and not [a for s, a in f.calls if s == 'bag.py' and a[0] == 'purge'])

# ---------------- 失敗 / 續跑
f = Fake(rcs={('questrun.py', 'run'): [0, 0, 156, 0]})
rc = go(f, confirm_drop=True, to_seg='hero')
hr = [a for s, a in f.calls if s == 'questrun.py' and a[0] == 'run' and a[1] == '2031']
check('紅暴 156（沒龍王）→ 自動改跑 questrun --solo（同樣的丟棄參數）→ 0', rc == 0 and len(hr) == 2 and '--solo' not in hr[0] and '--solo' in hr[1]
      and '--buy-missing' not in hr[0] and '--buy-missing' not in hr[1] and '--drop-items' in hr[1] and pr.LAST['ran'][-1] == 'hero', str(hr))
f = Fake(rcs={('questrun.py', 'run'): [0, 0, 156, 112]})
rc = go(f, confirm_drop=True)
check('紅暴單人逃跑也失敗 → 173、訊息帶 --solo 指令、後面不跑', rc == pr.EXIT_HERO and '--solo' in pr.LAST['info']['manual'] and pr.LAST['ran'] == ['inventory', 'adult', 'yayoi']
      and not any(s == 'petquest.py' for s, _ in f.calls))
f2 = Fake()
rc = go(f2, confirm_drop=True, reset=False)
check('重跑 = 從紅暴續跑（前 3 段進度檔跳過）', rc == 0 and pr.LAST['ran'][0] == 'hero' and not any(a[1] == '2999' for s, a in f2.calls if s == 'questrun.py' and a[0] == 'run'))
f = Fake(rcs={('questrun.py', 'run'): [0, 0, 156, 9]})
check('紅暴單人逃跑回 9（驗證視窗）→ 透傳', go(f, confirm_drop=True) == 9)
f = Fake(rcs={('questrun.py', 'run'): [0, 0, 0, 112]})
rc = go(f)
check('1.82 前段 questrun 112 → 172、手動指令含 --from q182a', rc == pr.EXIT_QUEST and '--from q182a' in pr.LAST['info']['manual'])
f = Fake(rcs={('petquest.py', 'run'): [0, 168]})
rc = go(f)
check('卡坦 petquest 168（沒 --confirm-drop）→ 175、停在 katan', rc == pr.EXIT_PET and pr.LAST['ran'][-1] == 'dino')
f = Fake(rcs={('questrun.py', 'run'): 9})
rc = go(f)
check('questrun 回 9（驗證視窗）→ 透傳 9', rc == 9)
f = Fake(rcs={('exp.py', 'read'): 101})
rc = go(f, to_seg='inventory')
check('盤點失敗只警告（不擋）', rc == 0 and pr.LAST['warnings'])
f = Fake(not_done={'英雄島前傳（必做）': ['DKBO4'], '馬祖快遞(1.82)': ['DKBO2', 'DKBO4']}, not_done_ids=[2031, 2018])
rc = go(f, from_seg='finish')
vc = [a for s, a in f.calls if s == 'questrun.py' and a[0] == 'verify']
check('收尾：status 有人沒完成 → questrun verify 落後任務 --role 落後者（bossretry 補）→ 補上 → 照樣 grind', rc == 0
      and vc == [('verify', '2031', '2018', '--role', 'DKBO2,DKBO4')] and f.calls[-1][0] == 'grind.py', str(f.calls))
f = Fake(not_done={'英雄島前傳（必做）': ['DKBO4']}, not_done_ids=[2031], rcs={('questrun.py', 'verify'): 108})
rc = go(f, from_seg='finish')
check('收尾：補人失敗（verify 108）→ 176、不 grind', rc == pr.EXIT_FINISH and not any(s == 'grind.py' for s, _ in f.calls) and 'verify' in pr.LAST['info']['manual'])
f = Fake(not_done={'英雄島前傳（必做）': ['DKBO4']}, not_done_ids=[2031], rcs={('questrun.py', 'verify'): 9})
check('收尾：verify 回 9（驗證視窗）→ 透傳', go(f, from_seg='finish') == 9)
f = Fake()
go(f, confirm_drop=True)
qr = [a for s, a in f.calls if s == 'questrun.py' and a[0] == 'run']
pq = [a for s, a in f.calls if s == 'petquest.py']
check('questrun 段一律 --verify defer、petquest 帶 --verify-defer（逐人驗證延到收尾）', qr and all('--verify' in a and a[a.index('--verify') + 1] == 'defer' for a in qr)
      and pq and all('--verify-defer' in a for a in pq), str(qr[:2]))
f = Fake(pets={'roles': {r: [{'name': '朵拉比斯', 'state': '等待'}] for r in pr.ALL_ROLES}})
rc = go(f, from_seg='finish')
check('收尾：寵物狀態不對 → 176', rc == pr.EXIT_FINISH and '寵物狀態' in pr.LAST['info']['msg'])
f = Fake()
rc = go(f, confirm_drop=False, from_seg='hero', to_seg='hero')
check('沒 --confirm-drop：紅暴不帶丟寵 / 丟首飾旗標', rc == 0 and '--drop-items' not in f.calls[0][1])
# ---------------- --wear-hero-items
f = Fake()
rc = go(f, confirm_drop=True, wear_hero_items=True, from_seg='hero', to_seg='hero')
hr = [a for s, a in f.calls if s == 'questrun.py' and a[0] == 'run']
ws = [a for s, a in f.calls if s == 'bag.py' and a[0] == 'wear']
check('--wear-hero-items：紅暴帶丟巴朵蘭恩、不帶 --drop-items；背包沒首飾 → 不戴', rc == 0 and '--drop-reward' in hr[0] and '--drop-items' not in hr[0] and not ws, str(hr))
rich = bags(14, {'DKBO': [pr.HERO_RING], 'DKBO3': ['儀之兜', pr.HERO_RING]})
f = Fake(rcs={('questrun.py', 'run'): [156, 0]}, bag_lists=[rich])
rc = go(f, confirm_drop=True, wear_hero_items=True, from_seg='hero', to_seg='hero')
hr = [a for s, a in f.calls if s == 'questrun.py' and a[0] == 'run']
ws = [a for s, a in f.calls if s == 'bag.py' and a[0] == 'wear']
check('156 改單人逃跑也不帶 --drop-items，成功後只對背包有首飾的人 bag.py wear', rc == 0 and len(hr) == 2 and '--solo' in hr[1] and all('--drop-items' not in a for a in hr)
      and ws == [('wear', 'DKBO', pr.HERO_RING), ('wear', 'DKBO3', pr.HERO_RING)], str(ws))
f = Fake(rcs={('bag.py', 'wear'): [92, 0]}, bag_lists=[rich])
rc = go(f, confirm_drop=True, wear_hero_items=True, from_seg='hero', to_seg='hero')
check('戴失敗只警告、紅暴段仍成功、另一人照戴', rc == 0 and len(pr.LAST['warnings']) == 1 and '戴' in pr.LAST['warnings'][0]
      and len([1 for s, a in f.calls if s == 'bag.py' and a[0] == 'wear']) == 2)
f = Fake(rcs={('questrun.py', 'run'): [112]}, bag_lists=[rich])
rc = go(f, confirm_drop=True, wear_hero_items=True, from_seg='hero', to_seg='hero')
check('紅暴失敗 → 不戴', rc != 0 and not [1 for s, a in f.calls if s == 'bag.py' and a[0] == 'wear'])
f = Fake(bag_lists=[rich])
rc = go(f, confirm_drop=False, wear_hero_items=True, from_seg='hero', to_seg='hero')
check('沒 --confirm-drop + --wear-hero-items：什麼都不丟、仍戴首飾', rc == 0 and '--drop-reward' not in f.calls[0][1] and '--drop-items' not in f.calls[0][1]
      and any(a[0] == 'wear' for s, a in f.calls if s == 'bag.py'))
buf = io.StringIO()
with contextlib.redirect_stdout(buf):
    pr.run(confirm_drop=True, wear_hero_items=True, dry_run=True)
check('plan 顯示 --wear-hero-items 強制效果、hero 指令不含 --drop-items', '--wear-hero-items' in buf.getvalue() and 'bag.py wear' in buf.getvalue()
      and '--drop-items' not in buf.getvalue().split('[hero]')[1].split('[q182a]')[0].split('（首飾')[0])
# ---------------- 依轉數自動判斷（使用者 2026-10-16）
check('hero_mode：0 轉 wear / 1～5 轉 drop / None keep / 強制 wear', pr.hero_mode({}, 0) == 'wear' and all(pr.hero_mode({}, n) == 'drop' for n in range(1, 6))
      and pr.hero_mode({}, None) == 'keep' and pr.hero_mode({'wear_hero_items': True}, 3) == 'wear')
check('team_trans：全同才算；混合 / 缺 / 空 → None', pr.team_trans({'a': 2, 'b': 2}) == 2 and pr.team_trans({'a': 0, 'b': 0}) == 0
      and pr.team_trans({'a': 0, 'b': 1}) is None and pr.team_trans({'a': 1, 'b': None}) is None and pr.team_trans({}) is None)
rich = bags(14, {'DKBO': [pr.HERO_RING], 'DKBO3': [pr.HERO_RING]})
f = Fake(trans=0, bag_lists=[rich])
rc = go(f, confirm_drop=True, from_seg='hero', to_seg='hero')
hr = [a for s, a in f.calls if s == 'questrun.py' and a[0] == 'run']
ws = [a for s, a in f.calls if s == 'bag.py' and a[0] == 'wear']
check('0 轉（trans.json）：不帶 --drop-items、丟巴朵蘭恩、背包有首飾的人戴', rc == 0 and '--drop-items' not in hr[0] and '--drop-reward' in hr[0]
      and ws == [('wear', 'DKBO', pr.HERO_RING), ('wear', 'DKBO3', pr.HERO_RING)], str(ws))
f = Fake(trans=1, bag_lists=[rich])
rc = go(f, confirm_drop=True, from_seg='hero', to_seg='hero')
hr = [a for s, a in f.calls if s == 'questrun.py' and a[0] == 'run']
check('1 轉：照舊 --drop-items 刪、不戴', rc == 0 and '--drop-items' in hr[0] and not [1 for s, a in f.calls if s == 'bag.py' and a[0] == 'wear'])
f = Fake(trans=None, bag_lists=[rich])
rc = go(f, confirm_drop=True, from_seg='hero', to_seg='hero')
hr = [a for s, a in f.calls if s == 'questrun.py' and a[0] == 'run']
check('讀不出轉數：不刪也不戴、仍丟巴朵蘭恩、記 warning', rc == 0 and '--drop-items' not in hr[0] and '--drop-reward' in hr[0]
      and not [1 for s, a in f.calls if s == 'bag.py'] and any('讀不出' in w for w in pr.LAST['warnings']), str(pr.LAST['warnings']))
f = Fake(trans=1, exp_trans=[0] * 5, bag_lists=[rich])
rc = go(f, confirm_drop=True, from_seg='inventory', to_seg='hero')
hr = [a for s, a in f.calls if s == 'questrun.py' and a[0] == 'run' and a[1] == '2031']
check('盤點 exp.py 回報 5 人 0 轉優先於 trans.json（1 轉）→ 戴', rc == 0 and '--drop-items' not in hr[0] and any(a[0] == 'wear' for s, a in f.calls if s == 'bag.py'))
f = Fake(trans=0, exp_trans=[2, 2, 2, 2, 2], bag_lists=[rich])
rc = go(f, confirm_drop=True, from_seg='inventory', to_seg='hero')
hr = [a for s, a in f.calls if s == 'questrun.py' and a[0] == 'run' and a[1] == '2031']
check('盤點 5 人 2 轉 → 刪', rc == 0 and '--drop-items' in hr[0])
f = Fake(trans=1, exp_trans=[0, 0, 1, 0, 0], bag_lists=[rich])
rc = go(f, confirm_drop=True, from_seg='inventory', to_seg='hero')
hr = [a for s, a in f.calls if s == 'questrun.py' and a[0] == 'run' and a[1] == '2031']
check('盤點轉數混合 → 退回 trans.json 快取（1 轉）→ 刪', rc == 0 and '--drop-items' in hr[0])
check('清背包名單不含首飾', pr.HERO_RING not in pr.PURGE2)
check('段名不認得 → 170', go(Fake(), from_seg='xx') == pr.EXIT_ARGS)
buf = io.StringIO()
with contextlib.redirect_stdout(buf):
    pr.run(dry_run=True, confirm_drop=True)
t = buf.getvalue()
check('plan：14 段、每段指令、退出碼', all(f'[{s}]' in t for s in pr.SEGMENTS) and 'petquest.py run 2019' in t and 'questrun.py run 2031' in t and '170' in t)

# ---------------- dino 帶 --keep-autoswap（後面還有卡坦）+ 中斷保險
def dino_args(f):
    return [a for s_, a in f.calls if s_ == 'petquest.py' and a[1] == '2016']


check('katan_follows：全跑 / --to katan / --from dino 帶；--to dino 不帶；katan 已完成不帶', pr.katan_follows(None, None) and pr.katan_follows('dino', 'katan')
      and not pr.katan_follows(None, 'dino') and not pr.katan_follows(None, None, ['katan']) and pr.katan_follows('katan', None, ['katan']))
f = Fake()
rc = go(f, from_seg='dino', to_seg='katan')
check('dino + katan 都在範圍 → dino 帶 --keep-autoswap、katan 不帶；成功後 pending 清掉', rc == 0 and '--keep-autoswap' in dino_args(f)[0]
      and not any('--keep-autoswap' in a for s_, a in f.calls if s_ == 'petquest.py' and a[1] == '2019') and not pr.LAST['warnings']
      and not json.loads(pr.PROGRESS.read_text(encoding='utf-8')).get('autoswap_pending'), str(f.calls))
f = Fake()
rc = go(f, from_seg='dino', to_seg='dino')
check('只跑 dino（--to dino）→ 不帶 --keep-autoswap、沒警告', rc == 0 and '--keep-autoswap' not in dino_args(f)[0] and not pr.LAST['warnings'])
f = Fake(rcs={('petquest.py', 'run'): [0, 164]})
rc = go(f, from_seg='dino', to_seg='katan')
check('dino 成功、katan 失敗 → 175、進度檔 autoswap_pending、warnings 提示續跑 + 關法', rc == pr.EXIT_PET and json.loads(pr.PROGRESS.read_text(encoding='utf-8')).get('autoswap_pending')
      and pr.LAST['warnings'] and 'autoswap off' in pr.LAST['warnings'][-1] and '--from katan' in pr.LAST['warnings'][-1], str(pr.LAST.get('warnings')))
f = Fake()
rc = go(f, from_seg='finish', reset=False)
check('--from finish 且 pending 還在（卡坦沒走完）→ 收尾先 pet_catch --autoswap off、清 pending', rc == 0 and f.calls[0] == ('pet_catch.py', ('--autoswap', 'off'))
      and not json.loads(pr.PROGRESS.read_text(encoding='utf-8')).get('autoswap_pending'), str(f.calls[:2]))
f = Fake()
rc = go(f, from_seg='finish')
check('pending 沒有 → 收尾不呼叫 autoswap off', not any(s_ == 'pet_catch.py' for s_, _ in f.calls))
buf = io.StringIO()
with contextlib.redirect_stdout(buf):
    pr.run(dry_run=True, to_seg='dino')
check('plan --to dino：不帶 --keep-autoswap', '--keep-autoswap' not in buf.getvalue())
buf = io.StringIO()
with contextlib.redirect_stdout(buf):
    pr.run(dry_run=True)
check('plan 全跑：dino 帶 --keep-autoswap', '2016' in buf.getvalue() and '--keep-autoswap' in buf.getvalue())

print(f'\n{"全部通過" if not fails else f"失敗 {fails} 項"}')
sys.exit(1 if fails else 0)
