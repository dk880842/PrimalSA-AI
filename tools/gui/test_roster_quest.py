#!/usr/bin/env python3
"""多視窗第 3c 步離線測試：任務 / 轉生腳本改用 PSA_CLIENT 視窗名單（clients.roster()）。不碰遊戲、不呼叫真的 powershell.exe。
  - 沒設 PSA_CLIENT：各腳本的名單常數、隊長、抓寵分配、切換面板卡位、預設值與改版前逐字相同（快照）
  - PSA_CLIENT=PrimalSA2：全部換成 DKBO6～DKBO10（隊長 DKBO6、抓寵者 DKBO7），角色參數只認自己名單（DKBO2 不認）
  - 名單沒登錄的視窗（PrimalSA9）：CLI 拒跑、不點任何東西
名單常數在 import 時決定，所以每個情境開子程序（--child <情境>）算，母程序比對。
整支測試 PATH 最前面放假的 powershell.exe（記錄每次呼叫），最後確認沒有任何呼叫。
  uv run --no-project python tools/gui/test_roster_quest.py
"""
import json
import os
import stat
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

OLD_ROLES = ['DKBO', 'DKBO2', 'DKBO3', 'DKBO4', 'DKBO5']
NEW_ROLES = ['DKBO6', 'DKBO7', 'DKBO8', 'DKBO9', 'DKBO10']
OLD_CARDS = {'DKBO': (452, 275), 'DKBO2': (762, 275), 'DKBO3': (452, 360), 'DKBO4': (762, 360), 'DKBO5': (452, 445)}
OLD_ASSIGN = {2016: ['DKBO2:呼拔拔系:魯尼帖斯', 'DKBO3:老虎系:貝魯卡'],
              2019: ['DKBO2:鯊魚系:克邦凱斯,DKBO3:鯊魚系:加克拉,DKBO4:鯊魚系:加格,DKBO5:鯊魚系:邦恩吉',
                     'DKBO2:火雞系:火雞,DKBO3:火雞系:克克洛斯,DKBO4:火雞系:霍爾克,DKBO5:火雞系:奇寶']}


# ================================================================ 子程序：算一個情境的值 → JSON
def child(case: str) -> None:
    import io
    import contextlib
    import testenv  # noqa: F401  紀錄檔轉向暫存
    import bossretry
    import petquest
    import postrebirth
    import quest
    import questdefs
    import questdetail
    import questrun
    import rebirth
    import rebirth_pets
    import rebirth_steps
    import relogin
    import shopbuy

    out = {}
    out['roles'] = {m.__name__: list(m.ALL_ROLES) for m in (rebirth, questrun, rebirth_steps, postrebirth, questdetail, petquest, rebirth_pets)}
    out['roles']['bossretry'] = list(bossretry.ROLES)
    out['roles']['shopbuy'] = list(shopbuy.ROLES)
    out['leader'] = {m.__name__: m.LEADER for m in (rebirth, questrun, petquest, rebirth_pets, bossretry, shopbuy)}
    out['team_size'] = bossretry.TEAM_SIZE
    out['cards'] = {k: list(v) for k, v in quest.TEAM_CARDS.items()}
    out['assign'] = {d['id']: [v.get('assign') for v in d['pet_prep'].values()] for d in questdefs.ALL
                     if d.get('pet_prep') and any(v.get('assign') for v in d['pet_prep'].values())}
    out['pq_assign'] = {q: [[list(a) for a in r['assign']] for r in v['rounds']] for q, v in petquest.QUESTS.items() if v.get('rounds')}
    out['pq_count'] = {q: v.get('count') for q, v in petquest.QUESTS.items()}
    out['rp_defaults'] = {k: rebirth_pets.DEFAULTS[k] for k in ('catcher', 'count', 'mount_species', 'battle_pet')}
    out['relogin'] = [relogin.ROLES[0] if relogin.ROLES else '', len(relogin.ROLES), relogin.run.__defaults__[2:4]]
    out['bait'] = sorted(petquest.bait_ok_roles(['rebirth_pets：DKBO2 背包誘餌 = 4', 'rebirth_pets：DKB03 背包誘餌 = 4',
                                                 'rebirth_pets：DKBO7 背包誘餌 = 4', 'rebirth_pets：DKB010 背包誘餌 = 3', 'x']))
    out['parse'] = {t: questrun.parse_roles(t) for t in ('all', 'DKB03,dkbo5', 'DKB08,dkbo10', 'DKBO2')}
    out['gate_who'] = (rebirth_steps.judge_gate_text('DKB07未達到1轉131級禁止傳送') or {}).get('who')

    # questdetail.status_all：假工具，記錄切誰 / 最後切回誰
    class T:
        def __init__(self):
            self.calls = []

        def current(self):
            return 0, out['leader']['rebirth'] or None

        def switch(self, who):
            self.calls.append(['switch', who])
            return 0

        def ensure(self, who):
            self.calls.append(['ensure', who])
            return 0

        def read(self, names, dy=None):
            return 0, {n: '已完成' for n in names}

    t = T()
    rc, res = questdetail.status_all(['成人儀式'], tools=t)
    out['status_all'] = [rc, sorted(res), t.calls]

    # CLI：名單外的角色參數 / 沒有名單的視窗
    buf = io.StringIO()
    with contextlib.redirect_stderr(buf), contextlib.redirect_stdout(io.StringIO()):
        out['rp_catcher_DKBO2'] = rebirth_pets.run(1, dry_run=True, catcher='DKBO2')
        out['rp_catcher_DKB07'] = rebirth_pets.run(1, dry_run=True, catcher='DKB07')
        out['boss_who'] = bossretry.main(['plan', '--track', '琉璃洞窟', '--who', 'DKBO3'])
        out['shop_roles'] = shopbuy.main(['medicine', '--roles', 'DKBO8', '--dry-run']) if case == 'none' else None
        out['main_rc'] = {
            'questrun': _main_rc(questrun.main, ['questrun.py', 'plan', '2017']),
            'rebirth': _main_rc(rebirth.main, ['rebirth.py', '--dry-run']),
            'postrebirth': postrebirth.main(['plan', '--dry-run']) if case == 'unknown' else None,
            'petquest': petquest.main(['plan', '2016', '--dry-run']) if case == 'unknown' else None,
            'bossretry': bossretry.main(['plan', '--track', '琉璃洞窟']) if case == 'unknown' else None,
        } if case == 'unknown' else None
    out['stderr'] = buf.getvalue()[-600:]

    # plan 文字（dry-run）帶隊長名字
    pbuf = io.StringIO()
    with contextlib.redirect_stdout(pbuf), contextlib.redirect_stderr(io.StringIO()):
        if case != 'unknown':
            out['qr_plan_rc'] = [questrun.run([2016], dry_run=True, pet_turnin=True), questrun.run([2031], dry_run=True, solo=True)]
            rebirth_pets.run(1, dry_run=True)
            bossretry.run('琉璃洞窟', dry_run=True)
    out['plan'] = pbuf.getvalue()
    print('###JSON ' + json.dumps(out, ensure_ascii=False))


def _main_rc(fn, argv):
    old = sys.argv
    sys.argv = argv
    try:
        return fn()
    except SystemExit as e:
        return e.code
    finally:
        sys.argv = old


if len(sys.argv) > 2 and sys.argv[1] == '--child':
    child(sys.argv[2])
    sys.exit(0)


# ================================================================ 母程序
failed = 0


def check(name, ok, detail=''):
    global failed
    print(('PASS ' if ok else 'FAIL ') + name + (f'  {detail}' if detail and not ok else ''))
    if not ok:
        failed += 1


tmp = Path(tempfile.mkdtemp(prefix='psa-rq-'))
bindir = tmp / 'bin'
bindir.mkdir()
calls = tmp / 'ps-calls.jsonl'
fake = bindir / 'powershell.exe'
fake.write_text('#!' + sys.executable + '\n'
                'import json, os, sys\n'
                f'open({str(calls)!r}, "a", encoding="utf-8").write(json.dumps({{"argv": sys.argv[1:], '
                '"PSA_CLIENT": os.environ.get("PSA_CLIENT")}) + "\\n")\n'
                'print("fake ok")\nsys.exit(1)\n', encoding='utf-8')
fake.chmod(fake.stat().st_mode | stat.S_IXUSR)


def run_case(case: str, client):
    env = dict(os.environ, PATH=str(bindir) + os.pathsep + os.environ.get('PATH', ''), PSA_GUI_SERVER='0',
               PYTHONIOENCODING='utf-8', PSA_LAYOUT='2880x1659')
    env.pop('PSA_CLIENT', None)
    if client:
        env['PSA_CLIENT'] = client
    r = subprocess.run([sys.executable, __file__, '--child', case], env=env, capture_output=True, text=True, encoding='utf-8', timeout=300)
    line = [ln for ln in r.stdout.splitlines() if ln.startswith('###JSON ')]
    if r.returncode or not line:
        print(r.stdout[-2000:], r.stderr[-3000:])
        return None
    return json.loads(line[-1][8:])


# ---- 1) 沒設 PSA_CLIENT：與改版前逐字相同 ----
d = run_case('none', None)
check('主視窗：子程序跑完', d is not None)
if d:
    check('主視窗：7 支腳本 ALL_ROLES = DKBO～DKBO5', all(v == OLD_ROLES for v in d['roles'].values()), str(d['roles']))
    check('主視窗：隊長全是 DKBO', set(d['leader'].values()) == {'DKBO'}, str(d['leader']))
    check('主視窗：bossretry TEAM_SIZE 5', d['team_size'] == 5)
    check('主視窗：quest.TEAM_CARDS 與改版前相同', d['cards'] == {k: list(v) for k, v in OLD_CARDS.items()}, str(d['cards']))
    check('主視窗：questdefs 抓寵分配字串與改版前相同', d['assign'] == {str(k): v for k, v in OLD_ASSIGN.items()}, str(d['assign']))
    check('主視窗：petquest 2016 分配 DKBO2 / DKBO3', d['pq_assign']['2016'] == [[['DKBO2', '呼拔拔系', '魯尼帖斯'], ['DKBO3', '老虎系', '貝魯卡']]])
    check('主視窗：petquest 2019 分配 DKBO2～5', [a[0] for a in d['pq_assign']['2019'][0]] == OLD_ROLES[1:]
          and [a[0] for a in d['pq_assign']['2019'][1]] == OLD_ROLES[1:])
    check('主視窗：petquest count 5', d['pq_count']['2016'] == 5 and d['pq_count']['2019'] == 5)
    check('主視窗：rebirth_pets 預設 catcher DKBO2、count 5', d['rp_defaults'] == {'catcher': 'DKBO2', 'count': 5, 'mount_species': '布拉奇多斯', 'battle_pet': '朵拉比斯'}, str(d['rp_defaults']))
    check('主視窗：relogin 預設 隊長 DKBO / 5 人', d['relogin'] == ['DKBO', 5, ['DKBO', 5]], str(d['relogin']))
    check('主視窗：bait_ok_roles 只認 DKBO～5', d['bait'] == ['DKBO2', 'DKBO3'], str(d['bait']))
    check('主視窗：等級門檻視窗 DKB07 → who = DKBO7（名單外照舊正規化）', d['gate_who'] == 'DKBO7', str(d['gate_who']))
    check('主視窗：parse_roles', d['parse'] == {'all': OLD_ROLES, 'DKB03,dkbo5': ['DKBO3', 'DKBO5'], 'DKB08,dkbo10': None, 'DKBO2': ['DKBO2']}, str(d['parse']))
    check('主視窗：status_all 切 DKBO2～5、最後切回 DKBO', d['status_all'][0] == 0 and d['status_all'][2] == [['switch', r] for r in OLD_ROLES[1:]] + [['ensure', 'DKBO']],
          str(d['status_all']))
    check('主視窗：rebirth_pets --catcher DKBO2 dry-run = 0', d['rp_catcher_DKBO2'] == 0)
    check('主視窗：rebirth_pets --catcher DKB07 不認得 = 109', d['rp_catcher_DKB07'] == 109)
    check('主視窗：bossretry --who DKBO3 plan = 0', d['boss_who'] == 0, d['stderr'])
    check('主視窗：shopbuy --roles DKBO8 不在名單 = 用法錯', d['shop_roles'] not in (0, None))
    check('主視窗：plan 文字是 DKBO（char.ensure DKBO、確認當前 = DKBO、char.ensure DKBO → team.form）',
          'char.ensure DKBO → team.form' in d['plan'] and '確認當前 = DKBO' in d['plan'] and 'DKBO2' in d['plan'] and 'DKBO6' not in d['plan'])

# ---- 2) PSA_CLIENT=PrimalSA2 ----
d = run_case('p2', 'PrimalSA2')
check('PrimalSA2：子程序跑完', d is not None)
if d:
    check('PrimalSA2：7 支腳本 ALL_ROLES = DKBO6～DKBO10', all(v == NEW_ROLES for v in d['roles'].values()), str(d['roles']))
    check('PrimalSA2：隊長全是 DKBO6', set(d['leader'].values()) == {'DKBO6'}, str(d['leader']))
    check('PrimalSA2：quest.TEAM_CARDS 卡位相同、名字 DKBO6～10', list(d['cards']) == NEW_ROLES and list(d['cards'].values()) == [list(v) for v in OLD_CARDS.values()], str(d['cards']))
    check('PrimalSA2：questdefs 抓寵分配 DKBO7～10',
          d['assign'] == {str(k): [x.replace('DKBO5', 'DKBO10').replace('DKBO4', 'DKBO9').replace('DKBO3', 'DKBO8').replace('DKBO2', 'DKBO7') for x in v] for k, v in OLD_ASSIGN.items()},
          str(d['assign']))
    check('PrimalSA2：petquest 2019 分配 DKBO7～10', [a[0] for a in d['pq_assign']['2019'][0]] == NEW_ROLES[1:])
    check('PrimalSA2：rebirth_pets 預設 catcher DKBO7', d['rp_defaults']['catcher'] == 'DKBO7' and d['rp_defaults']['count'] == 5)
    check('PrimalSA2：relogin 預設隊長 DKBO6', d['relogin'] == ['DKBO6', 5, ['DKBO6', 5]], str(d['relogin']))
    check('PrimalSA2：bait_ok_roles 認 DKBO7、DKBO10（兩位數），不認 DKBO2 / DKBO3', d['bait'] == ['DKBO10', 'DKBO7'], str(d['bait']))
    check('PrimalSA2：等級門檻視窗 DKB07 → who = DKBO7', d['gate_who'] == 'DKBO7', str(d['gate_who']))
    check('PrimalSA2：parse_roles 只認自己名單', d['parse'] == {'all': NEW_ROLES, 'DKB03,dkbo5': None, 'DKB08,dkbo10': ['DKBO8', 'DKBO10'], 'DKBO2': None}, str(d['parse']))
    check('PrimalSA2：status_all 切 DKBO7～10、最後切回 DKBO6', d['status_all'][2] == [['switch', r] for r in NEW_ROLES[1:]] + [['ensure', 'DKBO6']], str(d['status_all']))
    check('PrimalSA2：rebirth_pets --catcher DKBO2（別的視窗）= 109', d['rp_catcher_DKBO2'] == 109)
    check('PrimalSA2：rebirth_pets --catcher DKB07 = 0（O / 0 同義）', d['rp_catcher_DKB07'] == 0)
    check('PrimalSA2：bossretry --who DKBO3（別的視窗）= 用法錯', d['boss_who'] not in (0, None))
    check('PrimalSA2：plan 文字換成 DKBO6 / DKBO7，沒有 DKBO2',
          'char.ensure DKBO6 → team.form' in d['plan'] and '確認當前 = DKBO6' in d['plan'] and 'DKBO7' in d['plan']
          and 'DKBO2' not in d['plan'] and '完成後 DKBO6 戰寵改回' in d['plan'], d['plan'][-800:])

# ---- 3) 名單沒登錄的視窗 ----
d = run_case('unknown', 'PrimalSA9')
check('PrimalSA9：子程序跑完', d is not None)
if d:
    check('PrimalSA9：名單空、隊長空', all(v == [] for v in d['roles'].values()) and set(d['leader'].values()) == {''}, str(d['roles']))
    check('PrimalSA9：CLI 全部拒跑（非 0）', all(v not in (0, None) for v in d['main_rc'].values()), str(d['main_rc']))
    check('PrimalSA9：訊息說沒有登錄名單', '沒有登錄角色名單' in d['stderr'], d['stderr'])
    check('PrimalSA9：TEAM_CARDS 用 #1～#5', list(d['cards']) == ['#1', '#2', '#3', '#4', '#5'])

# ---- 守門 ----
n = len(calls.read_text(encoding='utf-8').splitlines()) if calls.exists() else 0
check('假 powershell 沒有被呼叫', n == 0, calls.read_text(encoding='utf-8')[:500] if n else '')
print(f'FAIL 數: {failed}')
sys.exit(1 if failed else 0)
