#!/usr/bin/env python3
"""mail.py 離線測試（不碰遊戲）。用法：uv run --no-project python tools/gui/test_mail.py"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import testenv  # noqa: E402,F401
import mail  # noqa: E402
import uikit  # noqa: E402

fails = 0


def check(name, ok):
    global fails
    print(('PASS ' if ok else 'FAIL ') + name)
    fails += 0 if ok else 1


class Fake:
    def __init__(self, n, texts=None, stuck=False):
        self.n, self.clicks, self.stuck = n, [], stuck
        self.texts = texts or ['這是您丟失的物品,請及時領取!'] * n


BLUE = (66, 110, 171)
BG = (123, 93, 66)


def install(f):
    uikit.preflight = lambda src, fast=True: 0
    uikit.open_panel = lambda p, timeout=4.0: True
    uikit.close_panel = lambda p, known_open=False: True
    uikit.is_open = lambda p: True
    uikit.px = lambda pts: [BLUE if i < f.n else BG for i in range(len(pts))]
    uikit.ocr = lambda box, *o: [f.texts[0]] if f.texts else []

    def sc(x, y, panel, note='', allow=(), wait_ms=300):
        f.clicks.append((x, y))
        if x == mail.CLAIM_X and not f.stuck:
            f.n -= 1
            f.texts = f.texts[1:]
        return True
    uikit.safe_click = sc
    mail.time.sleep = lambda s: None


f = Fake(3)
install(f)
check('3 封全領 rc 0', mail.run('claim') == 0 and f.n == 0 and len([c for c in f.clicks if c[0] == mail.CLAIM_X]) == 3)
f = Fake(2)
install(f)
check('--dry-run 不點領取', mail.run('claim', dry=True) == 0 and not [c for c in f.clicks if c[0] == mail.CLAIM_X])
f = Fake(2, texts=['每日獎勵', '每日獎勵'])
install(f)
check('不是丟失的物品 → 112 不點', mail.run('claim') == 112 and not [c for c in f.clicks if c[0] == mail.CLAIM_X])
f = Fake(2, stuck=True)
install(f)
check('領了沒消失 → 114', mail.run('claim') == 114)
f = Fake(0)
install(f)
check('沒信 → 0', mail.run('claim') == 0)
check('lost_text', mail.lost_text('這是您丟失的物品') and not mail.lost_text('活動獎勵'))
print('失敗', fails)
sys.exit(1 if fails else 0)
