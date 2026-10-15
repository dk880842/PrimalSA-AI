#!/usr/bin/env python3
"""namematch / team 名字辨識在 PrimalSA3（DKBO11～DKBO15，兩位數尾碼）的離線測試。不碰遊戲。
fixtures/name_tpl_p3.json = 2026-10-16 p3 實機切換面板 5 張卡的名字圖（digitmatch.ps1 -Boxes 原生解析度二值化）。
OCR 字串 = 同一次實機 team.ocr_names 的結果（DKBO14 讀成 '001A' / 'D0'）與快速組隊提示視窗 qt1.png 離線重跑 ocr.ps1 -Image 的結果。
用法：uv run --no-project python tools/gui/test_namematch_p3.py"""
import json
import os
import sys
import tempfile
from pathlib import Path

os.environ['PSA_CLIENT'] = 'PrimalSA3'          # 必須在 import 任何 tools/gui 模組之前（名單在 import 時決定）
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import testenv  # noqa: E402,F401  紀錄檔轉向暫存
import charstate  # noqa: E402
import namematch as nm  # noqa: E402
import team  # noqa: E402

fails = 0


def check(name, cond, extra=''):
    global fails
    print(('PASS' if cond else 'FAIL'), name, extra)
    if not cond:
        fails += 1


nm.TPL_DIR = Path(tempfile.mkdtemp())
NAMES = ['DKBO11', 'DKBO12', 'DKBO13', 'DKBO14', 'DKBO15']
FIX = json.loads((HERE / 'fixtures' / 'name_tpl_p3.json').read_text(encoding='utf-8'))
ROWS = {i: nm.int_to_rows(int(FIX[n][0], 16)) for i, n in enumerate(NAMES)}
# 實機 team.ocr_names（2026-10-16 p3 切換面板）
OCR_SW = {0: ['011', '011', '011', '011'], 1: ['012', 'DB012', 'DKB012', 'DB012'], 2: ['0013', 'B013', '013', '013', '013'],
          3: ['001A', 'D0', 'D0'], 4: ['0015', '015', 'DKB015', '015', '015']}

check('名單 = DKBO11～15、隊長 DKBO11', charstate.chars() == NAMES and charstate.LEAD == 'DKBO11')
check('實機 OCR：DKBO14 卡讀成 001A / D0 → unknown（OCR 學不到的原因）', team.cross_check('DKBO14', OCR_SW[3]) == 'unknown')
check('實機 OCR：其他 4 張尾碼 11/12/13/15 → ok', all(team.cross_check(NAMES[s], OCR_SW[s]) == 'ok' for s in (0, 1, 2, 4)))

# ---- 樣板：沒有 DKBO14 時的現況（4 個學到、DKBO14 沒有）----
tpl4 = {n: FIX[n] for n in NAMES if n != 'DKBO14'}
hits4 = {s: d['name'] for s, d in nm.match_rows(ROWS, tpl4).items()}
check('缺 DKBO14 樣板：slot0/1/2/4 命中、slot3 = None（不誤認成別人）', hits4 == {0: 'DKBO11', 1: 'DKBO12', 2: 'DKBO13', 3: None, 4: 'DKBO15'}, str(hits4))

# ---- plan_labels：其他 4 張樣板都命中且符合順序 → DKBO14 依格位學 ----
logs = []
lab = nm.plan_labels(list(range(5)), NAMES, OCR_SW, hits4, tpl4, logs.append)
check('plan_labels：DKBO14 依格位交叉確認 → 要學 slot3', lab is not None and lab.get(3) == 'DKBO14' and any('依格位學' in s for s in logs), f'{lab} {logs}')
t = {k: list(v) for k, v in tpl4.items()}
n_new = nm.learn_from(ROWS, lab, t, logs.append)
check('learn_from 只新增 DKBO14 一個變體（其他重複不加）', n_new == 1 and len(t['DKBO14']) == 1 and all(len(t[n]) == 1 for n in NAMES), str(n_new))
hits5 = {s: d['name'] for s, d in nm.match_rows(ROWS, t).items()}
check('學完 5 張全部樣板命中', hits5 == dict(enumerate(NAMES)), str(hits5))
sc = nm.score_all(int(FIX['DKBO14'][0], 16), {n: [int(h, 16) for h in v] for n, v in t.items() if n != 'DKBO14'})
check('DKBO14 名字圖與其他 4 人樣板 IoU 都 < HIT_MIN - MARGIN（唯一）', max(sc.values()) < nm.HIT_MIN - nm.MARGIN, str(sc))

# ---- 交叉確認不夠時不學 ----
tpl3 = {n: FIX[n] for n in ('DKBO11', 'DKBO13', 'DKBO15')}
hits3 = {s: d['name'] for s, d in nm.match_rows(ROWS, tpl3).items()}
lab = nm.plan_labels(list(range(5)), NAMES, OCR_SW, hits3, tpl3, logs.append)
check('另一張（DKBO12）也沒樣板 → DKBO14 不依格位學（DKBO12 OCR ok 照學）', lab is not None and 3 not in lab and lab.get(1) == 'DKBO12', str(lab))
bad = {**hits4, 1: 'DKBO13'}
check('有卡樣板命中別人（與順序矛盾）→ None 整次不學', nm.plan_labels(list(range(5)), NAMES, OCR_SW, bad, tpl4, logs.append) is None)
ocr_bad = {**OCR_SW, 3: ['DKB012']}
check('DKBO14 卡 OCR 讀到別人（DKB012）→ None 整次不學', nm.plan_labels(list(range(5)), NAMES, ocr_bad, hits4, tpl4, logs.append) is None)
check('只有 1 張卡（沒有「其他人」可交叉）→ 讀不出不學', nm.plan_labels([0], ['DKBO99'], {0: []}, {}, {}, logs.append) == {})

# ---- 快速組隊提示視窗：格位 = 名單順序（名字 OCR 只記 log）----
QT1_OCR = ['DKBOII', 'DKB1', 'B011']          # qt1.png 上排第 1 欄（離線 -Image 重跑；實機原生解析度讀法不同、常確認不了 → 以前 44）
check('提示視窗 DKBO11 OCR（qt1.png）cross_check 結果只當 log，不影響格位', team.cross_check('DKBO11', QT1_OCR) in ('ok', 'unknown'))
cards = [team.Card(i) for i in range(5)]
check('leader_card：5 張卡、名字全不知道 → DKBO11 = 第 1 張、DKBO14 = 第 4 張（依名單格位）',
      team.leader_card(cards, 'DKBO11') is cards[0] and team.leader_card(cards, 'DKB014') is cards[3])
check('leader_card：名單外名字 → None', team.leader_card(cards, 'DKBO5') is None)
four = [team.Card(i, name=n, check='ok') for i, n in enumerate(['DKBO11', 'DKBO13', 'DKBO14', 'DKBO15'])]
check('leader_card：4 張卡（有人離線補位）→ 只認名字確認過的卡', team.leader_card(four, 'DKBO14') is four[2] and team.leader_card(four, 'DKBO12') is None)
four[2].check = 'unknown'
check('leader_card：4 張卡且目標卡名字沒確認 → None（不猜）', team.leader_card(four, 'DKBO14') is None)
check('_strict_unknown：5 張卡就算 3 張讀不出也不擋；4 張卡 2 張讀不出 → 擋',
      not team._strict_unknown([team.Card(i, check='unknown') for i in range(5)])
      and team._strict_unknown([team.Card(i, check='unknown') for i in range(4)][:2] + [team.Card(2, check='ok'), team.Card(3, check='ok')]))
check('team.describe(44) 有說明、未知碼空字串', '提示視窗' in team.describe(44) and team.describe(999) == '')

print('失敗', fails)
sys.exit(1 if fails else 0)
