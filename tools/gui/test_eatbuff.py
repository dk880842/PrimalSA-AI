#!/usr/bin/env python3
"""eatbuff.py 離線測試（不碰遊戲）。用法：uv run --no-project python tools/gui/test_eatbuff.py"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import testenv  # noqa: E402,F401
import bag  # noqa: E402
import bufftime  # noqa: E402
import eatbuff  # noqa: E402
import heal  # noqa: E402
import uikit  # noqa: E402

fails = 0


def check(name, ok):
    global fails
    print(('PASS ' if ok else 'FAIL ') + name)
    fails += 0 if ok else 1


H = 3600
# ---- judge ----
check('exp 吃前 0 → 吃後 5:59 = 吃到', eatbuff.judge('exp', 0, 6 * H - 60))
check('exp 疊加：吃前 3h → 吃後 8:59 = 吃到', eatbuff.judge('exp', 3 * H, 9 * H - 60))
check('exp 沒吃到：吃前 5:56 → 吃後 5:55（時間只是走）', not eatbuff.judge('exp', 6 * H - 240, 6 * H - 300))
check('exp 事件 09:52：剩餘時間沒變 → 失敗', not eatbuff.judge('exp', 3 * H, 3 * H - 40))
check('dragon 吃前 0 → 9:30 = 吃到', eatbuff.judge('dragon', 0, 570))
check('dragon 疊加：吃前 5 分 → 14:40 = 吃到', eatbuff.judge('dragon', 300, 880))
check('dragon 重置成滿：吃前 4 分 → 9:50 = 吃到', eatbuff.judge('dragon', 240, 590))
check('dragon 沒吃到：吃前 9 分 → 8 分 = 失敗', not eatbuff.judge('dragon', 540, 480))

# ---- remaining ----
bag.buff_state = lambda k: None
check('remaining 像素讀不到 → None', eatbuff.remaining('exp') == (None, bufftime.EXIT_ROW))
bag.buff_state = lambda k: False
check('remaining 沒圖示 → 0', eatbuff.remaining('exp') == (0, 0))
bag.buff_state = lambda k: True
bufftime.read = lambda kind='all', dry_run=False: {'ok': True, 'rc': 0, 'buffs': [{'kind': kind, 'remaining_s': 3 * H}], 'errors': []}
check('remaining 有圖示 → 讀 bufftime', eatbuff.remaining('exp') == (3 * H, 0))
bufftime.read = lambda kind='all', dry_run=False: {'ok': False, 'rc': 132, 'buffs': [], 'errors': ['x']}
check('remaining 時間讀不出 → None + rc', eatbuff.remaining('exp') == (None, 132))

# ---- verify / eat_have ----
bag._wait = lambda pred, secs=2.0: pred()
uikit.snap = lambda *a, **k: None
rec = []
bufftime.record_eaten = lambda kind, ts=None, path=None: (rec.append(kind), True)[1]


def setup(icons, reads, use_rc=0, bag_open=False):
    """icons：has_buff 依序回傳（最後一個重複）；reads：bufftime.read 的剩餘秒數序列（None = 讀不出）。回 calls"""
    calls = []
    ic, rd = list(icons), list(reads)
    bag.buff_state = lambda k: (ic[0] if len(ic) == 1 else ic.pop(0))
    bag.has_buff = lambda k: bool(bag.buff_state(k))

    def _read(kind='all', dry_run=False):
        v = rd.pop(0)
        return {'ok': v is not None, 'rc': 0 if v is not None else 132, 'buffs': [] if v is None else [{'kind': kind, 'remaining_s': v}], 'errors': []}
    bufftime.read = _read
    heal.encounter_off_wait = lambda: calls.append('off')
    heal.set_encounter = lambda on: calls.append(f'enc{int(on)}')
    bag.use_item = lambda r, w, verify_buff=False: (calls.append('use'), use_rc)[1]
    uikit.is_open = lambda p: bag_open and 'closeleft' not in calls
    bag.popup_open = lambda: False
    bag.close_leftover = lambda dialog_esc=True: (calls.append('closeleft'), 'closed')[1]
    return calls


# 事件 09:52：吃前有 buff 剩 3h，吃後剩餘沒增加 → 95（舊版回 ok）
calls = setup([True], [3 * H, 3 * H - 40])
rc, info = eatbuff.eat_have('DKBO6', '2倍智慧果')
check('剩餘沒增加 → 95、不回 ok', rc == bag.EXIT_VERIFY and info['buff'] is False and info['remain_before'] == 3 * H)
check('先關遇敵再 use、結束開回遇敵', calls == ['off', 'use', 'enc1'])
# 事件 12:56：吃前沒 buff → 吃後 5:59
calls = setup([False, True, True], [6 * H - 60])
rc, info = eatbuff.eat_have('DKBO6', '2倍智慧果')
check('吃前 0 → 吃後 5:59 → ok', rc == 0 and info['bufftime'] == 'read' and info['remain_after'] == 6 * H - 60)
# 吃後沒圖示（12:54）
calls = setup([False], [])
rc, info = eatbuff.eat_have('DKBO6', '2倍智慧果')
check('吃後沒圖示 → 95', rc == bag.EXIT_VERIFY and '沒看到' in info['warn_buff'])
# 吃前有圖示但讀不出時間 → 不吃
calls = setup([True], [None])
rc, info = eatbuff.eat_have('DKBO6', '2倍智慧果')
check('吃前時間讀不出 → 不吃 95', rc == bag.EXIT_VERIFY and 'use' not in calls and info['step'] == 'before')
# 吃前沒 buff、吃後時間讀不出 → 以圖示為準 + record_eaten
rec.clear()
calls = setup([False, True, True], [None])
rc, info = eatbuff.eat_have('DKBO6', '2倍智慧果')
check('吃前 0、吃後時間讀不出 → 視為吃到並 record_eaten', rc == 0 and rec == ['exp'] and 'warn_time' in info)
# 吃前有 buff、吃後時間讀不出 → 驗不出 = 失敗
calls = setup([True], [3 * H, None])
rc, info = eatbuff.eat_have('DKBO6', '2倍智慧果')
check('吃前有 buff、吃後讀不出 → 95', rc == bag.EXIT_VERIFY)
# use 失敗 → 回 use 的 rc、不驗；reopen=False 不開遇敵
calls = setup([False], [], use_rc=bag.EXIT_PANEL)
rc, info = eatbuff.eat_have('DKBO6', '龍王的守護', reopen=False)
check('use 失敗 → 回該 rc、不開回遇敵', rc == bag.EXIT_PANEL and calls == ['off', 'use'])
# use 後背包還開著 → 再關
calls = setup([False, True, True], [570], bag_open=True)
rc, info = eatbuff.eat_have('DKBO6', '龍王的守護')
check('use 後背包外框還在 → close_leftover', rc == 0 and 'closeleft' in calls and info['closed_leftover'] == 'closed')
# 非 buff 道具 → 只 use_item
calls = setup([False], [])
rc, info = eatbuff.eat_have('DKBO6', '小的爪')
check('非 buff 道具 → 只 use', rc == 0 and calls == ['off', 'use', 'enc1'])

print(f'\n{fails} 失敗' if fails else '\n全部通過')
sys.exit(1 if fails else 0)
