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
check('id 不重複', len(questdefs.BY_ID) == len(questdefs.Q182))
for d in questdefs.Q182:
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
check('P2 順序：2999 排第一', questdefs.DEFAULT_ORDER[0] == 2999)
print(f'\n{"全部通過" if not fails else f"失敗 {fails} 項"}')
sys.exit(1 if fails else 0)
