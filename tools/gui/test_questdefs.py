#!/usr/bin/env python3
"""questdefs.py 離線測試：資料表與 knowledge/data/tables（Task / TaskExplan）核對，不碰遊戲。
用法：uv run --no-project python tools/gui/test_questdefs.py"""
import json
import os
import sys
from pathlib import Path

os.environ.setdefault('PSA_LAYOUT', '2880x1659')
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import testenv  # noqa: E402,F401  紀錄檔轉向暫存（不污染真 actions.log / quest-events.log / errlog）
import questdefs  # noqa: E402

TABLES = questdefs.ROOT / 'knowledge' / 'data' / 'tables'
fails = 0


def check(name, cond, extra=''):
    global fails
    print(('PASS' if cond else 'FAIL'), name, extra)
    if not cond:
        fails += 1


def rows(name):
    return [json.loads(ln) for ln in (TABLES / f'{name}.jsonl').read_text(encoding='utf-8').splitlines() if ln.strip()]


tasks, explan = rows('Task'), {r['ID']: r for r in rows('TaskExplan')}
check('id 不重複', len(questdefs.BY_ID) == len(questdefs.ALL))
for d in questdefs.ALL:
    tid = d['id']
    ts = sorted((t for t in tasks if t.get('group') == tid), key=lambda t: t.get('step', 0))
    check(f'{tid} Task 表有此任務組且步數 = steps_total', len(ts) == d['steps_total'], f'表 {len(ts)} / 資料 {d["steps_total"]}')
    e = explan.get(tid)
    check(f'{tid} detail = TaskExplan.nameTn', bool(e) and e.get('nameTn') == d['detail'], str(e and e.get('nameTn')))
    check(f'{tid} track = Task 表 name（無 (1.82) 後綴）', bool(ts) and d['track'] == (ts[0].get('nameTn') or ts[0].get('name')) and '(1.82)' not in d['track'],
          str(ts and (ts[0].get('nameTn'), ts[0].get('name'))))
    for st, sd in (d.get('steps') or {}).items():
        check(f'{tid} 步 {st} 在步數範圍內、kind 合法', 1 <= st <= d['steps_total'] and sd['kind'] in questdefs.STEP_KINDS)
        if sd['kind'] in ('walk', 'fight'):
            check(f'{tid} 步 {st} {sd["kind"]} 有 map / xy', isinstance(sd.get('map'), int) and len(sd.get('xy', ())) == 2)
        if sd['kind'] == 'fight':
            check(f'{tid} 步 {st} fight 有便捷傳送 warp / warp_name，且 Task 表該步是戰鬥（type 4）', len(sd.get('warp', ())) == 2 and sd.get('warp_name')
                  and ts[st - 1].get('type') == 4)
# 2999 步 1 的終點 NPC 座標必須與 walk 目標一致（Npc 表 map / x / y）
npcs = {n['ID']: n for n in rows('Npc')}
t2999 = sorted((t for t in tasks if t.get('group') == 2999), key=lambda t: t.get('step', 0))
n1 = npcs.get(t2999[0].get('endNpc'))
sd = questdefs.get(2999)['steps'][1]
check('2999 步 1 walk 目標 = 差使 NPC 座標', bool(n1) and (n1.get('map'), n1.get('x'), n1.get('y')) == (sd['map'], sd['xy'][0], sd['xy'][1]), str(n1 and (n1.get('map'), n1.get('x'), n1.get('y'))))
# resolve / step_kind
ds, bad = questdefs.resolve(['2017', 2015, 'x'])
check('resolve：保留順序、回報不認得', [d['id'] for d in ds] == [2017, 2015] and bad == ['x'])
check('resolve：空 = 全部預設順序', [d['id'] for d in questdefs.resolve([])[0]] == questdefs.DEFAULT_ORDER)
check('step_kind', questdefs.step_kind(questdefs.get(2999), 1) == 'walk' and questdefs.step_kind(questdefs.get(2999), 2) == 'default'
      and questdefs.step_kind(questdefs.get(2017), 1) == 'default')
check('洞窟不進預設順序', not ({2000, 2001, 2002, 2003} & set(questdefs.DEFAULT_ORDER)) and questdefs.get(2002)['boss'])
check('3003 步 1 / 2016 步 1、2 為 manual', questdefs.step_kind(questdefs.get(3003), 1) == 'manual' and questdefs.step_kind(questdefs.get(3003), 2) == 'default'
      and questdefs.step_kind(questdefs.get(2016), 1) == 'manual' and questdefs.step_kind(questdefs.get(2016), 2) == 'manual')
check('P2 順序：2999 排第一', questdefs.DEFAULT_ORDER[0] == 2999)
# 背包空位需求（2026-10-13 強盜的洞穴步 3 頭盔因 5 人背包滿進了信箱）：bag_slots >= Task 表推出的同時佔用格數
for d in questdefs.ALL:
    need = questdefs.bag_need(d['id'], tasks)
    check(f'{d["id"]} bag_slots {d["bag_slots"]} >= Task 表推算 {need}', d['bag_slots'] >= need)
check('bag_need 強盜的洞穴 = 4（衣服 / 斧頭 / 頭盔 / 盜賊們的足跡；交完只剩秘藥）', questdefs.bag_need(2020, tasks) == 4)
check('bag_need 四寶玉之謎 = 5（4 寶玉 + 條件道具 2764）', questdefs.bag_need(2010, tasks) == 5)
check('bag_need 交寵物任務（只給寵物 / 石幣）= 0', questdefs.bag_need(2016, tasks) == 0 and questdefs.bag_need(2019, tasks) == 0)
# 背包滿自動刪（bag.AUTO_PURGE）：每個都在 ui/bag.md 白名單表、不在保護名單、不是任何任務的條件道具
import bag  # noqa: E402
import re as _re  # noqa: E402
md = (questdefs.ROOT / '.claude' / 'skills' / 'psa-game-ui' / 'ui' / 'bag.md').read_text(encoding='utf-8')
sec = md.split('## 可刪除道具白名單', 1)[1].split('保留 / 存公共倉庫', 1)[0]
white = {m.group(1).strip() for m in _re.finditer(r'^\|\s*([^|]+?)\s*\|', sec, _re.M)} - {'道具名稱', '---'}
items = {r['ID']: r.get('nameTn') for r in rows('Item')}
cond_names = {items.get(c['itemId']) for t in tasks if t.get('group') in questdefs.BY_ID for c in (t.get('condition') or []) if c and c.get('itemId')}
check('AUTO_PURGE 每個都在 bag.md 白名單表', set(bag.AUTO_PURGE) <= white, str(set(bag.AUTO_PURGE) - white))
check('AUTO_PURGE 不含有條件的「龍的魅力之笛」「亞姆亞姆的斧頭」', not ({'龍的魅力之笛', '亞姆亞姆的斧頭'} & set(bag.AUTO_PURGE)) and {'龍的魅力之笛', '亞姆亞姆的斧頭'} <= white)
check('AUTO_PURGE 含仙尼亞的花 / 郵寄物 / 切繩石（使用者 2026-10-14 決定）且在白名單表', {'仙尼亞的花', '郵寄物', '切繩石'} <= set(bag.AUTO_PURGE) and {'仙尼亞的花', '郵寄物', '切繩石'} <= white)
check('AUTO_PURGE 含馬祖 / 空想獎勵裝備', {'馬祖的斧頭', '馬祖的矛', '馬祖的棍棒', '空想的帽子', '空想的豎琴'} <= set(bag.AUTO_PURGE))
check('Item 表每個新增名稱只有一個 ID（無同名陷阱）', all(sum(1 for r in rows('Item') if r.get('nameTn') == n) == 1 for n in ['仙尼亞的花', '郵寄物', '切繩石', '馬祖的斧頭', '馬祖的矛', '馬祖的棍棒', '空想的帽子', '空想的豎琴']))
check('AUTO_PURGE 沒有保護名稱（PROTECT / PURGE_FORBID）', not [n for n in bag.AUTO_PURGE if bag.purge_guard(n)])
check('AUTO_PURGE 不是任何 questdefs 任務的條件道具（不會刪到要交的東西）', not (set(bag.AUTO_PURGE) & cond_names), str(set(bag.AUTO_PURGE) & cond_names))
# 龍王：除 4 個任務外全吃（使用者 2026-10-13）/ 前置依賴（Task 表 finishTasks）
check('dragon = 不在 NO_DRAGON（使用者 10-13：除 4 個任務外全吃）', all(d['dragon'] == (d['id'] not in questdefs.NO_DRAGON) for d in questdefs.ALL))
check('短巡路也吃（亞姆的斧頭 / 夢幻洞窟 / 成人儀式）；馬祖快遞 / 伐木證書 / 四大洞窟吃',
      all(questdefs.get(i)['dragon'] for i in (2015, 2011, 2999, 2018, 2025, 2000, 2001, 2002, 2003)))
check('彌生和日美子 / 猜謎三兄弟 / 恐龍博士 / 卡坦的願望 不吃', not any(questdefs.get(i)['dragon'] for i in (2017, 3003, 2016, 2019)))
check('prereqs：1.82 任務要先完成成人儀式；成人儀式 / 洞窟沒有前置', questdefs.prereqs(2017, tasks) == [2999] and questdefs.prereqs(2999, tasks) == []
      and questdefs.prereqs(2000, tasks) == [])
check('四寶玉之謎 hp_every = 1（連戰）', questdefs.get(2010).get('hp_every') == 1)

# pet_prep：需先抓 / 練寵的步驟提示（questrun 追蹤沒反應 → 155）
for _tid, _st in ((2019, 1), (2019, 2), (2016, 1), (2016, 2), (3003, 2)):
    _h = questdefs.pet_prep_hint(questdefs.get(_tid), _st)
    check(f'{_tid} 步 {_st} 有 pet_prep 提示', bool(_h) and '需先抓 / 練寵' in _h and f'questrun run {_tid}' in _h, str(_h))
check('2019 步 2 提示 = pet_catch 火雞系', 'pet_catch.py' in questdefs.pet_prep_hint(questdefs.get(2019), 2) and '火雞系' in questdefs.pet_prep_hint(questdefs.get(2019), 2))
check('3003 步 2 提示 = petwatch --exp-fruit', 'petwatch.py' in questdefs.pet_prep_hint(questdefs.get(3003), 2) and '--exp-fruit' in questdefs.pet_prep_hint(questdefs.get(3003), 2))
check('沒設 pet_prep 的任務 / 步 → None', questdefs.pet_prep_hint(questdefs.get(2017), 1) is None and questdefs.pet_prep_hint(questdefs.get(2019), 3) is None)

# 紅暴 2031（2026-10-13 納入）
d31 = questdefs.get(2031)
check('2031 在 questdefs、不進預設順序、dragon_required、步 6 fight、每步收片', d31 and 2031 not in questdefs.DEFAULT_ORDER and d31.get('dragon_required')
      and questdefs.step_kind(d31, 6) == 'fight' and d31.get('stop_after_rewards') == 1)
n31 = npcs.get(sorted((t for t in tasks if t.get('group') == 2031), key=lambda t: t.get('step', 0))[5].get('endNpc'))
check('2031 步 6 BOSS NPC（龍王的守衛）在 fight map、距落點 ≤ 3 格', bool(n31) and n31.get('map') == d31['steps'][6]['map']
      and abs(n31.get('x') - d31['steps'][6]['xy'][0]) <= 3 and abs(n31.get('y') - d31['steps'][6]['xy'][1]) <= 3, str(n31 and (n31.get('map'), n31.get('x'), n31.get('y'))))
check('2031 前置：成人儀式 / 80 級 / 耐久力回複藥（Task 表步 1 條件）', questdefs.prereqs(2031, tasks) == [2999] and d31.get('min_level') == 80
      and '耐久力回複藥' in d31.get('need_items', []))
check('2031 獎勵：步 7 龍王的守護 / 步 8 英雄的祝福、薩姆吉爾的首飾 都在 Task 表獎勵', {'龍王的守護', '英雄的祝福', '薩姆吉爾的首飾'}
      <= {items.get(r.get('itemId')) for t in tasks if t.get('group') == 2031 for r in (t.get('reward') or []) if r and r.get('itemId')})
alld = {n for d in questdefs.ALL for n in d.get('drop_items') or []}
check('drop_items 不在 AUTO_PURGE（要明確旗標）、不是保護名稱、在 bag.md 白名單表', not (alld & set(bag.AUTO_PURGE)) and not [n for n in alld if bag.purge_guard(n)]
      and alld <= white, str(alld - white))
check('post 存倉的道具都是保護 / 保留類（不會被 purge）：龍王的守護在 PURGE_FORBID', bag.purge_guard('龍王的守護'))

print(f'\n{"全部通過" if not fails else f"失敗 {fails} 項"}')
sys.exit(1 if fails else 0)
