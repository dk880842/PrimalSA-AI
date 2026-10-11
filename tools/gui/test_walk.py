#!/usr/bin/env python3
"""walk.py 版面常數離線測試（不碰遊戲）：常數在 import 時依 layout 選，所以每種版面開一個子行程用 PSA_LAYOUT 指定。
- 筆電 2880×1659 / 1920×1017：常數、waitstill、不做畫面邊界檢查（維持原行為）
- 外接 1728×995（WORLD_PHYS，2026-10-11 實機量測）：每格 53.3×38.3、ME、NPC_DY、固定等待、點擊點不出畫面、實機驗證過的點擊座標
用法：uv run --no-project python tools/gui/test_walk.py
"""
import json
import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
fails = 0


def check(name, cond, extra=''):
    global fails
    print(('PASS' if cond else 'FAIL'), name, extra)
    if not cond:
        fails += 1


PROBE = r'''
import json, sys
sys.path.insert(0, %r)
import walk
off = [(dx, dy) for dx in range(-10, 11) for dy in range(-10, 11)
       if not (0 <= walk.screen(dx, dy)[0] < 1440 and 0 <= walk.screen(dx, dy)[1] < 830)]
print(json.dumps({
    'ME': walk.ME, 'TX': walk.TILE_X, 'TY': walk.TILE_Y, 'NPC_DY': walk.NPC_DY, 'still': walk.USE_WAITSTILL,
    'shot': walk.SHOT, 'settle5': walk.settle(5), 'settle0': walk.settle(0), 'ok_phys': list(walk.WORLD_OK_PHYS),
    'off_safe': [p for p in off if walk.safe(*walk.screen(*p))],
    'reach': {f'{dx},{dy}': max([k for k in range(1, 11) if walk.reachable(dx * k, dy * k)] or [0])
              for dx in (-1, 0, 1) for dy in (-1, 0, 1) if dx or dy},
    'pts': {'x+2': walk.screen(2, 0), 'y-3': walk.screen(0, -3), '6,0': walk.screen(6, 0), '-2,-2': walk.screen(-2, -2),
            'npc': walk.npc_screen((94, 101), (92, 99)), '-6,6': walk.screen(-6, 6)},
    'plan': walk.plan(1000, (92, 99), (86, 90)),
}))
''' % str(HERE)


def probe(lay: str) -> dict:
    env = dict(os.environ, PSA_LAYOUT=lay, PSA_GUI_SERVER='0')
    r = subprocess.run([sys.executable, '-c', PROBE], env=env, capture_output=True, text=True, encoding='utf-8', timeout=120)
    if r.returncode:
        print(r.stderr)
    return json.loads(r.stdout.strip().splitlines()[-1])


# ---- 筆電 2880×1659：原常數不變 ----
a = probe('2880x1659')
check('筆電：ME / TILE / NPC_DY 原值', a['ME'] == [715, 410] and a['TX'] == [32, -23] and a['TY'] == [32, 23] and a['NPC_DY'] == -29)
check('筆電：用 waitstill（settle = waitstill 4000）', a['still'] and a['settle5'] == 'waitstill 4000' and a['settle0'] == 'waitstill 4000')
check('筆電：不做畫面邊界檢查（SHOT=None，維持原 STEP_COST / plan）', a['shot'] is None)
check('筆電：右下 / 正右 10 格可一次點', a['reach']['1,1'] == 10 and a['reach']['1,0'] == 10, a['reach'])

# ---- 1920×1017：原常數不變 ----
b = probe('1920x1017')
check('1920：ME / TILE / NPC_DY 原值', b['ME'] == [477, 251] and b['TX'] == [21.2, -15.2] and b['NPC_DY'] == -19 and b['still'] and b['shot'] is None)

# ---- 外接 1728×995 ----
c = probe('1728x995')
check('外接：WORLD_OK_PHYS 含 1728x995', '1728x995' in c['ok_phys'])
check('外接：每格 53.3×38.3（筆電 × 2/1.2）', abs(c['TX'][0] - 32 * 2 / 1.2) < 0.01 and abs(c['TX'][1] + 23 * 2 / 1.2) < 0.01
      and c['TY'][0] == c['TX'][0] and c['TY'][1] == -c['TX'][1])
check('外接：ME 712,407、NPC_DY -48', c['ME'] == [712, 407] and c['NPC_DY'] == -48)
check('外接：不用 waitstill，固定等待 500 + 220 × 格數（0 格當 1 格）',
      not c['still'] and c['settle5'] == 'wait 1600' and c['settle0'] == 'wait 720')
check('外接：畫面外的點一律不 safe（-6,+6 = y 867 不可點）', not c['off_safe'] and c['pts']['-6,6'][1] > 830 and c['shot'] == [1440, 830])
# 實機（2026-10-11）點過、落點正確的座標
check('外接：x+2 → 819,330（實機 843,318 落在 +2 格）', c['pts']['x+2'] == [819, 330])
check('外接：6,0 → 1032,177、-2,-2 → 499,407（薩姆吉爾村 3 段走路實際點擊）', c['pts']['6,0'] == [1032, 177] and c['pts']['-2,-2'] == [499, 407])
check('外接：站 92,99 點巫女 94,101 → 925,359（實機開出對話框）', c['pts']['npc'] == [925, 359])
check('外接：一次可點格數因畫面變少（往右上 ≤ 5、右下 ≤ 6）', c['reach']['1,-1'] <= 5 and c['reach']['1,1'] <= 6, c['reach'])
check('外接：92,99 → 86,90 有路線且每段點擊都 safe', bool(c['plan']), c['plan'])

print('\n全部通過' if not fails else f'\n{fails} 項失敗')
sys.exit(1 if fails else 0)
