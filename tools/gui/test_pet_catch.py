#!/usr/bin/env python3
"""pet_catch.py 離線測試（假 Tools，不碰遊戲）。用法：uv run --no-project python tools/gui/test_pet_catch.py"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import testenv  # noqa: E402,F401
import pet_catch  # noqa: E402
import rebirth_pets as rp  # noqa: E402
import petmatch  # noqa: E402

fails = 0


def check(name, ok):
    global fails
    print(('PASS ' if ok else 'FAIL ') + name)
    fails += 0 if ok else 1


check('parse_assign', pet_catch.parse_assign('DKBO2:鯊魚系:克邦凱斯,DKBO3:鯊魚系:加克拉') == [('DKBO2', '鯊魚系', '克邦凱斯'), ('DKBO3', '鯊魚系', '加克拉')])
try:
    pet_catch.parse_assign('DKBO2:鯊魚系')
    check('parse_assign 格式錯 → ValueError', False)
except ValueError:
    check('parse_assign 格式錯 → ValueError', True)


class FakeT:
    def __init__(self, fail_at=None):
        self.calls, self.fail_at = [], fail_at

    def _r(self, tag, role):
        self.calls.append((tag, role))
        return 7 if self.fail_at == (tag, role) else 0

    def bait_take(self, role, keep):
        return self._r('bait', role)

    def catch_setup(self, role, fam, sp, count):
        return self._r('setup', role)

    def catch_start(self, role, count):
        return self._r('start', role)

    def sleep(self, s):
        pass


A = [('DKBO2', '鯊魚系', '克邦凱斯'), ('DKBO3', '鯊魚系', '加克拉')]
f = FakeT()
check('dry-run 零呼叫', pet_catch.run(A, dry_run=True, tools=f) == 0 and not f.calls)
f = FakeT()
rc = pet_catch.run(A, stages=('setup',), tools=f)
check('setup：逐人 setup + start', rc == 0 and f.calls == [('setup', 'DKBO2'), ('start', 'DKBO2'), ('setup', 'DKBO3'), ('start', 'DKBO3')])
f = FakeT(fail_at=('setup', 'DKBO2'))
check('setup 失敗 → 該 rc、不繼續下一人', pet_catch.run(A, stages=('setup',), tools=f) == 7 and f.calls == [('setup', 'DKBO2')])
f = FakeT(fail_at=('bait', 'DKBO2'))
check('bait 失敗 → rc、不繼續', pet_catch.run(A, stages=('bait',), tools=f) == 7 and f.calls == [('bait', 'DKBO2')])

# register_growths：撞到別的物種 → 刪除（只靠縮圖）
import tempfile
reg = {'thumb': {}, 'growth': {'1/1/1/1': '甲'}}
petmatch.load_species = lambda: reg
petmatch.save_species = lambda r: None
dropped = pet_catch.register_growths({'1/1/1/1': '乙', '2/2/2/2': '乙'})
check('register_growths：新字串登錄、撞別種的刪掉並計數', dropped == 1 and reg['growth'] == {'2/2/2/2': '乙'})

# rebirth_pets 純函式：系別清單鄰居備援表、物種列順序
check('FAMILY_NEIGHBORS / SPECIES_ORDER 有鯊魚系與火雞系', '鯊魚系' in rp.FAMILY_NEIGHBORS and rp.SPECIES_ORDER['鯊魚系'][0] == '克邦凱斯' and rp.SPECIES_ORDER['火雞系'][3] == '奇寶')
class FT2:
    def __init__(self, pets):
        self.pets = pets

    def pets_list(self, roles):
        return 0, self.pets


_ok = {'DKBO': [{'empty': False, 'state': '騎乘'}, {'empty': False, 'state': '出戰'}], 'DKBO4': [{'empty': False, 'state': '騎乘'}, {'empty': False, 'state': '等待'}, {'empty': True}]}
check('missing_battle：騎乘 / 等待 / 空格都不算出戰', pet_catch.missing_battle(_ok) == ['DKBO4'])
check('verify_battle：有人沒出戰寵 → 105；全有 → 0', pet_catch.verify_battle(['DKBO', 'DKBO4'], FT2(_ok)) == 105
      and pet_catch.verify_battle(['DKBO'], FT2({'DKBO': _ok['DKBO']})) == 0)
print('\n失敗 %d' % fails if fails else '\n全部通過')
sys.exit(1 if fails else 0)
