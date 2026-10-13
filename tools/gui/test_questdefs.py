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
        if sd['kind'] == 'walk':
            check(f'{tid} 步 {st} walk 有 map / xy', isinstance(sd.get('map'), int) and len(sd.get('xy', ())) == 2)
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
check('AUTO_PURGE 沒有保護名稱（PROTECT / PURGE_FORBID）', not [n for n in bag.AUTO_PURGE if bag.purge_guard(n)])
check('AUTO_PURGE 不是任何 questdefs 任務的條件道具（不會刪到要交的東西）', not (set(bag.AUTO_PURGE) & cond_names), str(set(bag.AUTO_PURGE) & cond_names))
# 龍王只對長巡路任務吃（2026-10-13 review §3.2）/ 前置依賴（Task 表 finishTasks）
check('dragon = walk_s >= DRAGON_WALK_MIN', all(d['dragon'] == (d['walk_s'] is not None and d['walk_s'] >= questdefs.DRAGON_WALK_MIN) for d in questdefs.ALL))
check('短巡路（亞姆的斧頭 7 秒 / 夢幻洞窟 9 秒 / 成人儀式 43 秒）不吃；馬祖快遞 / 伐木證書 / 四大洞窟吃',
      not any(questdefs.get(i)['dragon'] for i in (2015, 2011, 2999, 2017)) and all(questdefs.get(i)['dragon'] for i in (2018, 2025, 2000, 2001, 2002, 2003)))
check('沒量到巡路秒數（交寵物 / 猜謎）→ 不吃', not any(questdefs.get(i)['dragon'] for i in (2016, 2019, 3003)) and questdefs.get(2016)['walk_s'] is None)
check('prereqs：1.82 任務要先完成成人儀式；成人儀式 / 洞窟沒有前置', questdefs.prereqs(2017, tasks) == [2999] and questdefs.prereqs(2999, tasks) == []
      and questdefs.prereqs(2000, tasks) == [])
check('四寶玉之謎 hp_every = 1（連戰）', questdefs.get(2010).get('hp_every') == 1)
print(f'\n{"全部通過" if not fails else f"失敗 {fails} 項"}')
sys.exit(1 if fails else 0)
